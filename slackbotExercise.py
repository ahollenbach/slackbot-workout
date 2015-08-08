import random
import time
import requests
import json
import csv
from random import shuffle
import pickle
import os.path
import os
import time
from datetime import datetime, timedelta

from User import User
from Bot import Bot
from MySlackClient import MySlackClient
from slackclient import SlackClient
from MessageTracker import MessageTracker


def main():
    slack_client = MySlackClient()
    bot = Bot(slack_client)
    rtm = SlackClient(os.environ['SLACK_USER_TOKEN_STRING'])
    message_tracker = MessageTracker(bot, rtm, slack_client)

    if rtm.rtm_connect():
        try:
            while True:
                # Re-fetch config file if settings have changed
                bot.set_configuration()

                # Get an exercise to do
                now = datetime.now().time()
                if now > bot.active_hours[0] and now < bot.active_hours[1]:
                    # for inactive_timespan in bot.inactive_hours:
                    #     if inactive_timespan[0] < now and now < inactive_timespan[1]:
                    #         print "sleeping for " + str((inactive_timespan[1]-now)/1000)
                    #         sleep((inactive_timespan[1]-now)/1000) # TODO can't subtract
                    #         break

                    if not bot.active:
                        slack_client.send_message(bot.intro, bot.debug)
                        bot.active = True

                    exercise, sleep_time = bot.select_exercise_and_start_time()
                    #sleep_time = bot.select_time()
                    future_time = datetime.now() + timedelta(seconds=sleep_time)

                    while datetime.now() < future_time:
                        message_tracker.fetch_updates()
                        time.sleep(0.1)
                    #time.sleep(sleep_time)

                    # Assign the exercise to someone
                    bot.assign_exercise(exercise)
                    # else:
                    #     print now-bot.active_hours[0]
                    #     sleep(now-bot.active_hours[0])
                elif now > bot.active_hours[1] and bot.active:
                    bot.active = False
                    slack_client.send_message(bot.outro, bot.debug)

                # Pseudo-save state after each (todo save the whole thing)
                bot.print_breakdown()
        except KeyboardInterrupt:
            bot.save_users()


main()
