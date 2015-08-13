import requests
import json
import datetime
import os.path

class User:
    def __init__(self, user_id, slack_client):
        # The Slack ID of the user
        self.id = user_id

        # A link to the slack client for sending messages and requests
        self.slack_client = slack_client

        # The username (@username) and real name
        self.username, self.real_name = self.fetch_names()

        # A list of all exercises done by user
        self.exercise_history = []

        # A record of all exercise totals (quantity)
        self.exercises = {}

        # A record of exercise counts (# of times)
        self.exercise_counts = {}

        # A record of past runs
        self.past_workouts = {}

        # Tracks today's workouts
        # TODO remove (duplicates)
        self.exercise_board = []
        self.past_exercise_board = []

        print "New user: " + self.real_name + " (" + self.username + ")"


    def store_session(self, run_name):
        try:
            self.past_workouts[run_name] = self.exercises
        except:
            self.past_workouts = {}


        try:
            self.past_exercise_board
            self.exercise_board
        except AttributeError:
            self.past_exercise_board = []
            self.exercise_board = []

        self.past_exercise_board += self.exercise_board
        self.past_workouts[run_name] = self.exercises
        self.exercises = {}
        self.exercise_counts = {}
        self.exercise_board = []


    def fetch_names(self):
        params = {"user": self.id}
        response = self.slack_client.send_request("users.info", params=params)
        user_obj = json.loads(response.text, encoding='utf-8')["user"]

        username = user_obj["name"]
        real_name = user_obj["profile"]["real_name"]

        return username, real_name


    def get_user_handle(self):
        return ("@" + self.username).encode('utf-8')


    '''
    Returns true if a user is currently "active", else false
    '''
    def is_active(self):
        try:
            params = {"user": self.id}
            response = self.slack_client.send_request("users.getPresence", params=params)
            status = json.loads(response.text, encoding='utf-8')["presence"]

            return status == "active"
        except (requests.exceptions.ConnectionError,NameError,KeyError,ValueError):
            print "Error fetching online status for " + self.get_user_handle()
            return False

    def add_exercise(self, exercise, reps, all_channel=False):
        # Add to total counts
        self.exercises[exercise["id"]] = self.exercises.get(exercise["id"], 0) + reps
        self.exercise_counts[exercise["id"]] = self.exercise_counts.get(exercise["id"], 0) + 1

        # Add to exercise history record
        self.exercise_history.append([datetime.datetime.now().isoformat(),exercise["id"],exercise["name"],reps,exercise["units"]])

        # time, name, reps, units, completed
        try:
            self.exercise_board
        except NameError:
            self.exercise_board = []
        self.exercise_board.append([datetime.datetime.now().strftime("%I:%M%p"), exercise["name"], reps, exercise["units"], False])

    def has_done_exercise(self, exercise):
        return exercise["id"] in self.exercise_counts

    def write_to_file(self, user_dir):
        pass
