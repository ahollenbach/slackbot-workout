import random
import time
import requests
import json
import csv
from random import shuffle
import pickle
import os.path
import time
from datetime import datetime
from dateutil import parser

from User import User
from SlackClient import SlackClient

'''
The driving bot behind the workout program. Tracks
'''
class Bot:
    def __init__(self, slack_client):
        self.slack_client = slack_client
        self.set_configuration()

        self.csv_filename = "log" + time.strftime("%Y%m%d-%H%M") + ".csv"
        self.breakdown_filename = "breakdown" + time.strftime("%Y%m%d-%H%M") + ".data"
        self.first_run = True
        self.active = False

        # local cache of usernames
        # maps userIds to usernames
        self.user_cache = self.load_user_cache()

        # round robin store
        self.user_queue = []


    def load_user_cache(self):
        if os.path.isfile('user_cache.save'):
            with open('user_cache.save','rb') as f:
                self.user_cache = pickle.load(f)

                # Update slack client
                for user_id in self.user_cache:
                    self.user_cache[user_id].slack_client = self.slack_client

                print "Loading " + str(len(self.user_cache)) + " users from cache."
                return self.user_cache

        return {}

    '''
    Sets the configuration file.

    Runs after every callout so that settings can be changed realtime
    '''
    def set_configuration(self):
        # Read variables from the configuration file
        with open('config.json') as f:
            settings = json.load(f)

            self.min_countdown = settings["callouts"]["timeBetween"]["minTime"]
            self.max_countdown = settings["callouts"]["timeBetween"]["maxTime"]
            self.num_people_per_callout = settings["callouts"]["numPeople"]
            self.sliding_window_size = settings["callouts"]["slidingWindowSize"]
            self.group_callout_chance = settings["callouts"]["groupCalloutChance"]
            self.active_hours = settings["timeRestrictions"]["activeHours"][0]

            self.active_hours[0] = parser.parse(self.active_hours[0]).time()
            self.active_hours[1] = parser.parse(self.active_hours[1]).time()

            self.inactive_hours = []
            for inactive_timespan in settings["timeRestrictions"]["inactiveHours"]:
                start_time = parser.parse(inactive_timespan[0]).time()
                end_time = parser.parse(inactive_timespan[1]).time()
                self.inactive_hours.append((start_time, end_time))

            self.intro = settings["phrases"]["intro"]
            self.outro = settings["phrases"]["outro"]

            self.exercises = settings["exercises"]
            self.debug = settings["debug"]

            self.slack_client.set_info(settings["teamDomain"], settings["channelName"], settings["channelId"])


    '''
    Selects an active user from a list of users
    '''
    def select_user(self, exercise):
        active_users = self._fetch_active_users()

        # Add all active users not already in the user queue
        # Shuffles to randomly add new active users
        shuffle(active_users)
        both_arrays = set(active_users).intersection(self.user_queue)
        for user in active_users:
            if user not in both_arrays:
                self.user_queue.append(user)

        # The max number of users we are willing to look forward
        # to try and find a good match
        sliding_window = self.sliding_window_size

        # find a user to draw, priority going to first in
        for i in range(len(self.user_queue)):
            user = self.user_queue[i]

            # User should be active and not have done exercise yet
            if user in active_users and not user.has_done_exercise(exercise):
                self.user_queue.remove(user)
                return user
            elif user in active_users:
                # Decrease sliding window by one. Basically, we don't want to jump
                # too far ahead in our queue
                sliding_window -= 1
                if sliding_window <= 0:
                    break

        # If everybody has done exercises or we didn't find a person within our sliding window,
        for user in self.user_queue:
            if user in active_users:
                self.user_queue.remove(user)
                return user

        # If we weren't able to select one, just pick a random
        print "Selecting user at random (queue length was " + str(len(self.user_queue)) + ")"
        return active_users[random.randrange(0, len(active_users))]


    '''
    Fetches a list of all active users in the channel
    '''
    def _fetch_active_users(self):
        # Check for new members
        response = self.slack_client.get_channel_info()
        user_ids = json.loads(response.text, encoding='utf-8')["channel"]["members"]

        active_users = []

        for user_id in user_ids:
            # Add user to the cache if not already
            if user_id not in self.user_cache:
                self.user_cache[user_id] = User(user_id, self.slack_client)
                if not self.first_run:
                    # Push our new users near the front of the queue!
                    self.user_queue.insert(2,self.user_cache[user_id])

            if self.user_cache[user_id].is_active():
                active_users.append(self.user_cache[user_id])

        if self.first_run:
            self.first_run = False

        return active_users

    '''
    Selects an exercise and start time, and sleeps until the time
    period has past.
    '''
    def select_exercise_and_start_time(self):
        next_time_interval = self.select_next_time_interval()
        exercise = self.select_exercise()

        # Announcement String of next lottery time
        lottery_announcement = "NEXT LOTTERY FOR " + exercise["name"].upper() + " IS IN " + str(next_time_interval/60) + " MINUTES"

        # Announce the exercise to the thread
        self.slack_client.send_message(lottery_announcement, self.debug)

        # Sleep the script until time is up
        if not self.debug:
            time.sleep(next_time_interval)
        else:
            # If debugging, once every 5 seconds
            time.sleep(5)

        return exercise


    '''
    Selects the next exercise. If it's disabled, recurse ;)
    '''
    def select_exercise(self):
        idx = random.randrange(0, len(self.exercises))
        if self.exercises[idx]["enabled"]:
            return self.exercises[idx]
        return self.select_exercise()


    '''
    Selects the next time interval
    '''
    def select_next_time_interval(self):
        return random.randrange(self.min_countdown * 60, self.max_countdown * 60)


    '''
    Selects a person to do the already-selected exercise
    '''
    def assign_exercise(self, exercise):
        # Select number of reps
        exercise_reps = random.randrange(exercise["minReps"], exercise["maxReps"]+1)

        winner_announcement = str(exercise_reps) + " " + str(exercise["units"]) + " " + exercise["name"] + " RIGHT NOW "

        # EVERYBODY
        if random.random() < self.group_callout_chance:
            winner_announcement += "@channel!"

            for user_id in self.user_cache:
                user = self.user_cache[user_id]
                user.add_exercise(exercise, exercise_reps)

            self.log_exercise("@channel",exercise["name"],exercise_reps,exercise["units"])

        else:
            winners = [self.select_user(exercise) for i in range(self.num_people_per_callout)]

            # Build the list of winners
            for i in range(self.num_people_per_callout):
                winner_announcement += str(winners[i].get_user_handle())
                if i == self.num_people_per_callout - 2:
                    winner_announcement += ", and "
                elif i == self.num_people_per_callout - 1:
                    winner_announcement += "!"
                else:
                    winner_announcement += ", "

                winners[i].add_exercise(exercise, exercise_reps)
                self.log_exercise(winners[i].get_user_handle(),exercise["name"],exercise_reps,exercise["units"])

        # Announce the user
        self.slack_client.send_message(winner_announcement, self.debug)


    def log_exercise(self,username,exercise,reps,units):
        filename = self.csv_filename + "_DEBUG" if self.debug else self.csv_filename
        with open(filename, 'a') as f:
            writer = csv.writer(f)

            writer.writerow([str(datetime.now()),username,exercise,reps,units,self.debug])

    def save_users(self):
        # Write to the command console today's breakdown
        s = "```\n"
        #s += "Username\tAssigned\tComplete\tPercent
        s += "Username".ljust(15)
        for exercise in self.exercises:
            s += exercise["name"] + "  "
        s += "\n---------------------------------------------------------------\n"

        for user_id in self.user_cache:
            user = self.user_cache[user_id]
            s += user.username.ljust(15)
            for exercise in self.exercises:
                if exercise["id"] in user.exercises:
                    s += str(user.exercises[exercise["id"]]).ljust(len(exercise["name"]) + 2)
                else:
                    s += str(0).ljust(len(exercise["name"]) + 2)
            s += "\n"

            user.store_session(str(datetime.now()))

        s += "```"

        # Let's not send at the end so we can manually do it for now
        #self.slack_client.send_message(s, self.debug)

        # write to file
        with open('user_cache.save','wb') as f:
            pickle.dump(self.user_cache,f)

    '''
    Made specifically to store status while running, in the event of system crash
    '''
    def print_breakdown(self):
        s = "```\n"
        s += "Username".ljust(15)
        for exercise in self.exercises:
            s += exercise["name"] + "  "
        s += "\n---------------------------------------------------------------\n"

        for user_id in self.user_cache:
            user = self.user_cache[user_id]
            s += user.username.ljust(15)
            for exercise in self.exercises:
                if exercise["id"] in user.exercises:
                    s += str(user.exercises[exercise["id"]]).ljust(len(exercise["name"]) + 2)
                else:
                    s += str(0).ljust(len(exercise["name"]) + 2)
            s += "\n"

        s += "```"

        filename = self.breakdown_filename + "_DEBUG" if self.debug else self.breakdown_filename
        with open(filename, 'w') as f:
            f.write(s)
