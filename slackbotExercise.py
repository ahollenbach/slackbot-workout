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

from User import User
from Bot import Bot
from SlackClient import SlackClient


def main():
    slack_client = SlackClient()
    bot = Bot(slack_client)

    try:
        while True:
            # Re-fetch config file if settings have changed
            bot.set_configuration()

            # Get an exercise to do
            exercise = bot.select_exercise_and_start_time()
            #sleep_time = bot.select_time()

            #wait(sleep_time)

            # Assign the exercise to someone
            bot.assign_exercise(exercise)

            # Pseudo-save state after each (todo save the whole thing)
            bot.print_breakdown()
    except KeyboardInterrupt:
        bot.save_users()


main()
