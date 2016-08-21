import json
import logging
import requests
import threading
import inspect
import re
import os

from slackbot.bot import Bot, listen_to, respond_to

class TwitchBot(object):
    def __init__(self, slackclient=None):
        self.streamers = {}
        self.data_file = os.path.join(os.path.realpath(os.getcwd()), 'streamers.dat')
        self.load_streamers()

        if slackclient is None:
            slackclient = self.__get_slackclient()
        self.slackclient = slackclient
        if self.slackclient is None:
            print('Unable to retrieve slackclient instance')
            return

        # Get status
        self.get_status()

    def __get_slackclient(self):
        stack = inspect.stack()
        for frame in [f[0] for f in stack]:
            if 'self' in frame.f_locals:
                instance = frame.f_locals['self']
                if isinstance(instance, Bot):
                    return instance._client

    def load_streamers(self):
        if os.path.isfile(self.data_file):
            data_file = open(self.data_file, "r")
            stream_list = data_file.readline().split(',')
            for streamer in stream_list:
                if streamer != "":
                    self.init_streamer(streamer)
        else:
            print(self.data_file + " not found!")

    def save_streamers(self):
        data_file = open(self.data_file,'w')
        data_file.write(",".join(list(self.streamers.keys())))
        data_file.close()

    def init_streamer(self, name):
        self.streamers[name] = {
            "is_live": False,
            "game": None
        }

    def add_streamer(self, name):
        if name not in self.streamers.keys():
            self.init_streamer(name)
            self.save_streamers()

    def remove_streamer(self, name):
        self.streamers.pop(name, None)
        self.save_streamers()

    def get_status(self):
        streamer_list = ",".join(list(self.streamers.keys()))
        response = requests.get("https://api.twitch.tv/kraken/streams",
            params={'channel': streamer_list},
            headers={'content-type': 'application/json'})
        if response.status_code == 200:
            response = response.json()
            for s in self.streamers.keys():
                # Save is_live status in temp variable
                alive = False
                # Check list of streams to get update status
                for stream in response["streams"]:
                    # Get stream details
                    streamer = stream.get("channel").get("display_name")
                    game = stream.get("game")
                    url = stream.get("channel").get("url")
                    # If matched streamer name
                    if s == streamer.lower():
                        alive = True
                        # If was not live or game is different
                        if self.streamers[s]["is_live"] == False or self.streamers[s]["game"] != game:
                            # Update changes in status
                            self.streamers[s]["is_live"] = True
                            self.streamers[s]["game"] = game
                            # Send message to Slack
                            print("{} is now live playing {}!".format(streamer, game))
                            self.slackclient.send_message("general",
                                "{} is now playing {} live at {}".format(streamer, game, url))
                # If no longer live (didnt show up in list)
                if alive == False:
                    self.streamers[s]["is_live"] = False
                    self.streamers[s]["game"] = None
        else:
            print("Request Failed (Non-200 status)")
        # Poll twitch every 300 seconds once this function is started
        threading.Timer(30, self.get_status).start()


# Start the bot and events
tb = TwitchBot()
@respond_to('add (.*)')
def add(message, streamer):
    # add to streamer list
    streamer = streamer.lower().strip()
    if streamer.isalnum() and len(streamer) < 25:
        tb.add_streamer(streamer)
        message.reply('Added {} to the watch list.'.format(streamer))
    else:
        message.reply('Sorry, that username has an invalid format.')
@respond_to('remove (.*)')
def remove(message, streamer):
    # remove streamer from list
    streamer = streamer.lower().strip()
    if streamer.isalnum() and len(streamer) < 25:
        tb.remove_streamer(streamer)
        message.reply('Removed {} from the watch list.'.format(streamer))
    else:
        message.reply('Sorry, that username has an invalid format.')
