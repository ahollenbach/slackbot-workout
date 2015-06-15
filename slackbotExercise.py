import random
import time
import requests
import json
import csv
import os

# Environment variables must be set with your tokens
USER_TOKEN_STRING =  os.environ['SLACK_USER_TOKEN_STRING']
URL_TOKEN_STRING =  os.environ['SLACK_URL_TOKEN_STRING']

HASH = "%23"

DEBUG = True


# local cache of usernames
# maps userIds to usernames
user_cache = {}

# Configuration values to be set in setConfiguration
class Bot:
    def __init__(self):
        self.setConfiguration()

    '''
    Sets the configuration file.

    Runs after every callout so that settings can be changed realtime
    '''
    def setConfiguration(self):
        # Read variables fromt the configuration file
        with open('config.json') as f:
            settings = json.load(f)

            self.team_domain = settings["teamDomain"]
            self.channel_name = settings["channelName"]
            self.min_countdown = settings["timeBetweenCallouts"]["minTime"]
            self.max_countdown = settings["timeBetweenCallouts"]["maxTime"]
            self.channel_id = settings["channelId"]
            self.exercises = settings["exercises"]

        self.post_URL = "https://" + self.team_domain + ".slack.com/services/hooks/slackbot?token=%23" + URL_TOKEN_STRING + "&channel=" + HASH + self.channel_name


################################################################################


'''
Fetches a list of all slack users in the channel
'''
def fetchSlackUsers(bot):
    params = {"token": USER_TOKEN_STRING, "channel": bot.channel_id}

    # Capture Response as JSON
    response = requests.get("https://slack.com/api/channels.info", params=params)
    users = json.loads(response.text, encoding='utf-8')["channel"]["members"]

    return filter(None, list(map(fetchActiveUsers, users)))


'''
Fetches all of the active users
'''
def fetchActiveUsers(userId):
    if not isActive(userId):
        return None

    return getName(userId).encode('utf-8')


'''
Fetches the username for a given id
'''
def getName(userId):
    if userId in user_cache:
        username = user_cache[userId]
    else:
        params = {"token": USER_TOKEN_STRING, "user": userId}
        response = requests.get("https://slack.com/api/users.info",
                params=params)
        username = json.loads(response.text, encoding='utf-8')["user"]["name"]
        user_cache[userId] = username
        print "New user: " + username

    return ("@" + username).encode('utf-8')


'''
Returns true if a user is currently "active", else false
'''
def isActive(userId):
    params = {"token": USER_TOKEN_STRING, "user": userId}
    response = requests.get("https://slack.com/api/users.getPresence",
            params=params)
    status = json.loads(response.text, encoding='utf-8')["presence"]

    return status == "active"


'''
Selects a slack user from a list of slack users
'''
def selectSlackUser(bot):
    slackUsers = fetchSlackUsers(bot)

    return slackUsers[random.randrange(0, len(slackUsers))]


'''
Selects the next exercise
'''
def selectExercise(bot):
    idx = random.randrange(0, len(bot.exercises))
    return bot.exercises[idx]

'''
Selects the next time interval
'''
def selectNextTimeInterval(bot):
    return random.randrange(bot.min_countdown * 60, bot.max_countdown * 60)

'''
Selects an exercise and start time, and sleeps until the time
period has past.
'''
def selectExerciseAndStartTime(bot):
    next_time_interval = selectNextTimeInterval(bot)
    exercise = selectExercise(bot)

    # Announcement String of next lottery time
    lottery_announcement = "NEXT LOTTERY FOR " + exercise["name"] + " IS IN " + str(next_time_interval/60) + " MINUTES"

    # Announce the exercise to the thread
    if not DEBUG:
        requests.post(bot.post_URL, data=lottery_announcement)
    print lottery_announcement

    # Sleep the script until time is up
    if not DEBUG:
        time.sleep(next_time_interval)

    return exercise


'''
Selects a person to do the already-selected exercise
'''
def assignExercise(bot, exercise):
    # Select number of reps
    exercise_reps = random.randrange(exercise["minReps"], exercise["maxReps"]+1)
    winner = selectSlackUser(bot)

    winner_announcement = str(exercise_reps) + " " + str(exercise["units"]) + " " + exercise["name"] + " RIGHT NOW " + str(winner)

    if not DEBUG:
        requests.post(bot.post_URL, data=winner_announcement)
    print winner_announcement

    logExercise(winner,exercise["name"],exercise_reps,exercise["units"])


def logExercise(user,exercise,reps,units):
    with open("log.csv", 'a') as f:
        writer = csv.writer(f)
        writer.writerow([user,exercise,reps,units])


def main():
    bot = Bot()

    while True:
        # Re-fetch config file if settings have changed
        bot.setConfiguration()

        # Get an exercise to do
        exercise = selectExerciseAndStartTime(bot)

        # Assign the exercise to someone
        assignExercise(bot, exercise)


main()
