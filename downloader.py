#!/usr/bin/env python
# -*- coding: utf-8 -*-
import urllib2
import json
import os
import logging
import traceback
import yaml
from datetime import datetime
from TwitterAPI import TwitterAPI
import eyed3


class Channel:
    def __init__(self, channel_id):
        self.id = channel_id        # Channel Id(Ex: euphonium)
        self.count = 0              # Count
        self.sound_url = u""        # Sound URL
        self.title = u""            # Title of Channel
        self.file_name = u""        # Original file Name
        self.updated_at = u""       # Update Date(String)
        self.thumb_url = u""       # thumbnail path(image)
        self.thumb_file_name = u""  # thumbnail file name

    # Load channel information from API
    def load_channel_info(self):
        response = urllib2.urlopen(Utils.url_get_channel_info(self.id))
        r_str = response.read().encode('utf-8')[9:-3]
        r_json = json.loads(r_str)

        self.count = int(r_json["count"])
        self.sound_url = (r_json["moviePath"])["pc"]
        self.title = r_json["title"]
        self.file_name = (r_json["moviePath"])["pc"].split("/")[-1]
        self.updated_at = r_json["update"]
        self.thumb_url = Consts.BASE_URL + r_json["thumbnailPath"]
        self.thumb_file_name = r_json["thumbnailPath"].split("/")[-1]


class Downloader:
    # Download Channel
    @staticmethod
    def downloadChannel(channel):
        response = urllib2.urlopen(channel.sound_url)

        dir_path = Utils.radio_save_path(channel)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        file_path = dir_path + channel.file_name
        if os.path.exists(file_path):
            raise BusinessException("Already Downloaded:"
                                    + file_path)

        out = open(dir_path + channel.file_name, "wb")
        out.write(response.read())

        # embed id3 tag
        Utils.embed_id3_tag(dir_path + channel.file_name, channel)

    @staticmethod
    def download_thumbnail(channel):
        response = urllib2.urlopen(channel.thumb_url)
        tmp_dir_path = Utils.tmp_dir_path()
        thumb_file_path = tmp_dir_path + channel.thumb_file_name

        if not os.path.exists(tmp_dir_path):
            os.makedirs(tmp_dir_path)

        out = open(thumb_file_path, "wb")
        out.write(response.read())

        return thumb_file_path


class Consts:
    BASE_URL = u"http://www.onsen.ag"
    BASE_URL_GET_CHANNEL_INFO = u"http://www.onsen.ag/data/api/getMovieInfo/{channel_id}"
    USER_SETTING_FILE_PATH = os.path.abspath(os.path.dirname(__file__)) + "/user_settings.yml"
    DEFAULT_ARTIST_NAME = u"onsen"
    DEFAULT_ALBUM_TITLE = u"{channel_title}"
    DEFAULT_TRACK_TITLE = u"第{count}回"


class UserSettings:
    @staticmethod
    def get(key):
        # load setting file
        setting_file = open(Consts.USER_SETTING_FILE_PATH, "r")
        settings = yaml.load(setting_file)
        if key in settings:
            return settings[key]
        else:
            return None


class Utils:
    # Dir path to save channel
    @staticmethod
    def radio_save_path(channel):
        home = os.environ['HOME']
        script_dir = os.path.abspath(os.path.dirname(__file__))
        path = UserSettings.get("radio_save_path")\
                           .replace("{channel_id}", channel.id)\
                           .replace("{channel_title}", channel.title)\
                           .replace("~", home)\
                           .replace("./", script_dir + "/")
        return path

    # Dir path to save temporary files
    @staticmethod
    def tmp_dir_path():
        home = os.environ['HOME']
        script_dir = os.path.abspath(os.path.dirname(__file__))
        if UserSettings.get("tmp_dir_path") is None:
            path = script_dir + "/"
        else:
            path = UserSettings.get("tmp_dir_path")\
                               .replace("~", home)\
                               .replace("./", script_dir + "/")
        return path

    # URL to get channel info
    @staticmethod
    def url_get_channel_info(channel_id):
        return Consts.BASE_URL_GET_CHANNEL_INFO\
                     .replace("{channel_id}", channel_id)

    @staticmethod
    def embed_id3_tag(file_path, channel):
        cover_img_path = Downloader.download_thumbnail(channel)

        tag = eyed3.load(file_path).tag
        tag.version = eyed3.id3.ID3_V2_4
        tag.encoding = eyed3.id3.UTF_8_ENCODING
        tag.artist = Consts.DEFAULT_ARTIST_NAME
        tag.album_artist = Consts.DEFAULT_ARTIST_NAME
        tag.album = Consts.DEFAULT_ALBUM_TITLE\
                          .format(channel_title=channel.title)
        tag.title = Consts.DEFAULT_TRACK_TITLE\
                          .format(count=channel.count)
        tag.images.set(eyed3.id3.frames.ImageFrame.OTHER,
                       open(cover_img_path, "rb").read(),
                       "image/jpeg")

        tag.track_num = int(channel.count)
        tag.save()


class BusinessException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class Twitter:
    def __init__(self, consumer_key="", consumer_secret="", access_token_key="",
                 access_token_secret=""):
        if consumer_key and consumer_secret and access_token_key\
           and access_token_secret:
            self.enabled = True
            self.api = TwitterAPI(consumer_key, consumer_secret,
                                  access_token_key, access_token_secret)
            self.in_reply_to = None
        else:
            self.enabled = False
            self.api = None
            self.in_reply_to = None

    def post(self, message):
        if self.enabled is not True:
            return
        else:
            if self.in_reply_to is not None and self.in_reply_to != "":
                message = u"@{user_id} {message}"\
                          .format(user_id=self.in_reply_to, message=message)
            self.api.request('statuses/update', {'status': message})

    def set_in_reply_to(self, in_reply_to):
        self.in_reply_to = in_reply_to

    def notify_dl_completion(self, channel):
        message = u"録音が完了しました: 『{title} {count}話』 [{date}]"\
                  .format(title=channel.title,
                          count=channel.count,
                          date=channel.updated_at)
        self.post(message)

    def notify_dl_error(self, ch_id):
        message = u"録音中に例外が発生しました: {ch_id},{date}".format(ch_id=ch_id,
                  date=datetime.now().strftime(u"%Y/%m/%d/ %H:%M"))
        self.post(message)


class Main:
    @staticmethod
    def main():
        # Setup loggin
        logging.basicConfig(format='[%(levelname)s]%(asctime)s %(message)s',
                            filename='info.log',
                            level=logging.INFO)

        # Setup notification
        if UserSettings.get("twitter_settings") is not None:
            tw_settings = UserSettings.get("twitter_settings")
            twitter = Twitter(tw_settings["consumer_key"],
                              tw_settings["consumter_secret"],
                              tw_settings["access_token_key"],
                              tw_settings["access_token_secret"])
            if tw_settings["in_reply_to"] is not None:
                twitter.set_in_reply_to(tw_settings["in_reply_to"])
        else:
            twitter = Twitter()

        # Download all channels
        logging.info("Donwload begin.")

        channel_ids = UserSettings.get("channels")
        for c_id in channel_ids:
            logging.info("Downloading channel: " + c_id)
            try:
                c = Channel(c_id)
                c.load_channel_info()
                Downloader.downloadChannel(c)
            except BusinessException, e:
                logging.info("Not downloaded: " + c_id + ", because: " + e.value)
            except Exception, e:
                logging.error("Download interrupted: " + c_id)
                logging.error(traceback.format_exc())
                twitter.notify_dl_error(c_id)
            else:
                logging.info("Download complete: " + c_id)
                twitter.notify_dl_completion(c)

        logging.info("Download finish.")


if __name__ == "__main__":
    Main.main()
