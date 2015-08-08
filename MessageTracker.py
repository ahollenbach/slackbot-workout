import json
from datetime import datetime, timedelta
from pprint import pprint
import re

class MessageTracker:
    def __init__(self, bot, rtm, slack_client):
        self.bot = bot
        self.rtm = rtm
        self.slack_client = slack_client

        # store of the day's messages
        self.message_store = {}

    def fetch_updates(self):
        for update in self.rtm.rtm_read():
            self.handle_update(update)

    def handle_update(self, data):
        if self.bot.debug:
            print "\n============ " + data["type"] + " ============"
            pprint(json.dumps(data))
            print "============" + "="*(len(data["type"])+2) + "============\n"

        # Filter out only update types we want to look at
        accepted_update_types = ["message", "reaction_added"]
        if data["type"] not in accepted_update_types:
            print "Ignoring update of type " + data["type"]
            return

        # Reject if date is too from from current
        if self._is_old_update(data):
            print "Ignoring historical message"
            return

        if data["type"] == "message":
            self._handle_message(data)
        elif data["type"] == "reaction_added":
            self._handle_reaction_added(data)

    def _handle_message(self, data):
        # Limit for channel
        channel = self.slack_client.channel_id
        channel = "G08GCMVNC"
        if "channel" not in data or data["channel"] != channel:
            print "Ignoring non-channel message"
            return

        if "subtype" in data and data["subtype"] == "bot_message":
            print "Ignoring bot message"
            return

        if data["user"] not in self.bot.user_cache:
            print "Ignoring message: user not found in cache"
            return

        if "@USLACKBOT" not in data["text"]:
            print "Saving message for later"
            self.message_store[data["ts"]] = { "user": data["user"], "text": data["text"] }
            return

        user = self.bot.user_cache[data["user"]]
        incoming_message = data["text"]
        payload = { "attachments": [] }
        i = 1
        done_counter = 0
        for ex in user.exercise_board:
            report = {}
            report["title"] = "[" + str(i) + "] " + ex[0] + "   " + str(ex[2]) + " " + ex[3] + " " + ex[1]
            report["fallback"] = report["title"]
            report["color"] = "#7CD197" if ex[-1] else "#F35A00" # green else red
            payload["attachments"].append(report)
            i += 1
            if ex[-1]:
                done_counter += 1

        payload["attachments"] = json.dumps(payload["attachments"])
        payload["channel"] = channel
        payload["text"] = user.get_user_handle() + "'s workouts"
        if i > 0:
            payload["text"] += " (" + str(done_counter) + "/" + str(i-1) + " complete)"
        payload["text"] += ":"
        payload["icon_emoji"] = ":bar_chart:"
        payload["username"] = "WorkoutStatusBot"

        if len(user.exercise_board) == 0:
            payload["attachments"] = json.dumps([{"title": "No workouts yet! :("}])

        #print json.dumps(payload)

        self.slack_client.send_request("chat.postMessage", payload)

    def _handle_reaction_added(self, data):
        # Limit for channel
        channel = self.slack_client.channel_id
        channel = "G08GCMVNC"
        if "channel" not in data["item"] or data["item"]["channel"] != channel:
            print "Ignoring non-channel message"
            return

        if data["item"]["ts"] in self.message_store:
            user = self.bot.user_cache[self.message_store[data["item"]["ts"]]["user"]]
            message = self.message_store[data["item"]["ts"]]["text"]
            print "Searching message: " + message

            #user = self.bot.user_cache[self.message_store[data["item"]["ts"]]]

            workout_ids = re.findall('\[([0-9]+)-*([0-9]*)\]', message)
            csv_strings = re.findall('\[([0-9]+,.*?)\]', message)
            print workout_ids
            print csv_strings
            if len(workout_ids) > 0:
                # We want to support [0] [0-9], multiple in a line
                for workout_id in workout_ids:
                    if workout_id[1] == '':
                        self._set_exercise_status(user, workout_id[0])
                    else:
                        try:
                            start = int(workout_id[0])
                            end = int(workout_id[1]) + 1
                            for i in range(start, end):
                                self._set_exercise_status(user, i)
                        except ValueError:
                            continue
            elif len(csv_strings) > 0:
                # Also support csv [1,5,6]
                for csv_string in csv_strings:
                    indices = csv_string.split(",")
                    for idx in indices:
                        self._set_exercise_status(user, idx)
            else:
                # By default, just mark the latest as done
                self._set_exercise_status(user)

    '''
    Takes an int/string and sets the user exercise to true/false (default:True)
    The index is by default 0 (-1) to set the last exercise to True.
    Does quality checking for you
    '''
    def _set_exercise_status(self, user, idx=0, state=True):
        if type(idx) is str or type(idx) is unicode:
            if idx == '':
                print "Idx was empty"
                return
            # Try to convert to an int
            try:
                idx = int(idx)
                if idx == 0:
                    # Also an unexpected behavior
                    return
            except ValueError:
                print "Invalid format found:" + idx
                return

        print "Using idx:" + str(idx)
        print type(idx)
        if idx > len(user.exercise_board):
            print idx > len(user.exercise_board)
            print idx < len(user.exercise_board)
            print "Idx exceeds board length:" +str(idx) + "|" + str(len(user.exercise_board))
            return

        print user.exercise_board[idx-1][4]
        user.exercise_board[idx-1][4] = state
        print user.exercise_board[idx-1][4]


    def _is_old_update(self, data):
        if "ts" in data:
            time_string = data["ts"]
        elif "event_ts" in data:
            time_string = data["event_ts"]
        else:
            return False

        update_time = datetime.fromtimestamp(float(time_string))

        return datetime.now() - update_time > timedelta(minutes=2)
