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
from urlparse import urljoin


# Environment variables must be set with your tokens
USER_TOKEN_STRING =  os.environ['SLACK_USER_TOKEN_STRING']
URL_TOKEN_STRING =  os.environ['SLACK_URL_TOKEN_STRING']

HASH = "%23"

'''
An API wrapper for the Slack API. All requests and messages should be sent
through this wrapper. You *must* call `set_info(...)` before you can use
this class.
'''
class MySlackClient:
    def __init__(self):
        self.api_url = "https://slack.com/api"

    def set_info(self, team_domain, channel_name, channel_id):
        self.team_domain = team_domain
        self.channel_name = channel_name
        self.channel_id = channel_id

        self.message_url = "https://" + self.team_domain + ".slack.com/services/hooks/slackbot?token=" + URL_TOKEN_STRING + "&channel=" + HASH + self.channel_name

    def send_message(self, message, debug=False):
        if not debug:
            requests.post(self.message_url, data=message)
        print "[" + str(datetime.now()) + "] " + message

    '''
    Sends a request to the slack api using the method name supplied.
    If the request requires params besides the token, you must provide them.
    '''
    def send_request(self, method_name, params={}):
        # Add token string to request
        params["token"] = USER_TOKEN_STRING

        # Send out request, return result
        return requests.get(self.api_url + "/" + method_name, params=params)

    '''
    Wrapper for sendRequest that fills in all information necessary to fetch
    the info for the set channel.
    '''
    def get_channel_info(self):
        params = {"channel": self.channel_id}
        return self.send_request("channels.info", params)
