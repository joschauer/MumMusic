import pymumble
import re
import time
import audioop
import re
import urllib2 as urllib
import sys
import time
import subprocess as sp

regStream       = re.compile(r"https?://.+\.mp3")
regYoutube      = re.compile(r"https?://www.youtube.com/watch\?v=.*")
regYouPlay      = re.compile(r"https?://www.youtube.com/playlist\?list=.*")
regYouPlayVid   = re.compile(r"https?://www.youtube.com/watch\?v=.*list=.*")

class BotSama:
    version = "v0.4.1"
    host = ""
    user = ""
    cert = ""


    volume = 1
    playing = False
    playlist = []
    curSong = -1
    thread = None
    preproc = None

    def __init__(self, host, user, password, help, port=64738, cert=None):
        # start bot
        self.botsama = pymumble.Mumble(host, user, port, "spice", debug=False)
        self.exit = False

        self.botsama.set_receive_sound(False)
        self.botsama.callbacks.set_callback(pymumble.constants.PYMUMBLE_CLBK_TEXTMESSAGERECEIVED, self.message_received)

        self.botsama.start()
        self.botsama.is_ready()

        self.botsama.channels.find_by_name("Botcity").move_in();
        self.botsama.users.myself.unmute()
        self.botsama.set_bandwidth(200000)

        self.loop()

    # helper
    def send_msg_channel(self, msg, channel=None):
        if not channel:
            channel = self.botsama.channels[self.botsama.users.myself['channel_id']]
        channel.send_text_message(msg)

    def send_msg_user(self, msg, user):
        self.botsama.users[user].send_message(msg)

    # adds song(s) to the playlist
    def addSong(self, parameter):
        parameter = escapeURL(parameter)

        # Check for playlist first, because a playlist can look a bit like a normal youtube video
        if (regYouPlay.match(parameter) or regYouPlayVid.match(parameter)):
            print("Adding playlist " + parameter)
            if regYouPlayVid.match(parameter):
                parameter = re.search(r"list=.*$", parameter)
                if not parameter:
                    print("Could not create a string")
                    return
                parameter = "https://www.youtube.com/playlist?" + parameter.group()
                print("Created new url " + parameter)
            songs = getPlaylistArray(parameter)
            if not songs:
                self.send_msg_channel("Could not play playlist. It's probably private or not a real one.")
                return
            print(songs)
            for song in songs:
                self.playlist.append(song)
        elif (regStream.match(parameter) or regYoutube.match(parameter)):
            print("Adding single file")
            self.playlist.append(parameter)
        else:
            print("Could not add song to playlist")
            self.send_msg_channel("Could not add the song(s) to the playlist. Format no recognized!")
            self.listPlaylist()

    def play(self, song=None):
        playing = self.playing
        self.playing = False

        if not song:
            if (playing):
                self.playing = False
                return
            if (len(self.playlist) == 0):
                self.send_msg_channel("No songs in playlist")
                return
            if (self.curSong < 0 or self.curSong >= len(self.playlist)):
                self.send_msg_channel("Playlist done; starting from beginning")
                self.curSong = 0
            song = self.playlist[self.curSong]
        else:
            self.playlist = []
            self.curSong = 0
            self.addSong(song)

        self.playcur()

    def playcur(self):
        if self.playing:
            print ("already playing, not doing anything in playcur")
            return

        preCommand = ""
        usePreCommand = False

        if(self.curSong < 0 or self.curSong > len(self.playlist)):
            self.send_msg_channel("Playlist is over")

        parameter = self.playlist[self.curSong]

        self.send_msg_channel("Starting to play \""+ parameter +"\"<br>Please wait a second...")

        if (regStream.match(parameter)):
            print("Using direct streaming");
            song = parameter
        elif (regYoutube.match(parameter)):
            print("Using youtube");
            song = "-"
            preCommand = ['youtube-dl', '-q', "--audio-quality", "0" ,'--no-warnings', '-o', '-', parameter]
            usePreCommand = True
        else:
            self.send_msg_channel("Sorry, I couldn't play the file/stream")
            print("Could not play \""+ parameter + "\"")
            return

        command = ["ffmpeg", '-v', "warning", '-nostdin', '-i', song, '-ac', '1', '-f', 's16le', '-ar', '48000', '-']

        if(usePreCommand):
            self.preproc     = sp.Popen(preCommand, stdout=sp.PIPE)
            inStream = self.preproc.stdout
            time.sleep(5)
        else:
            inStream = None
        self.thread = sp.Popen(command, stdout=sp.PIPE, stdin=inStream, bufsize=480)

        time.sleep(1)
        self.playing = True

    def stopaudio(self):
        print("Stopping audio and killing threads")
        self.playing = False
        time.sleep(0.5)
        if self.thread:
            self.thread.kill
            self.thread = None
        if self.preproc:
            self.preproc.kill
            self.preproc = None

    def listPlaylist(self):
        print(self.curSong)
        if self.playlist and len(self.playlist) > 0:
            i = 1
            msg = ""
            for song in self.playlist:
                msg += "<br>"
                msg += str(i) + ". " + song
                if ((i-1) == self.curSong):
                    msg += "  &lt;--"
                i += 1
        else:
            msg = "Playlist is empty"
        self.send_msg_channel(msg)

    def songDone(self):
        self.playing = False
        self.nextSong()

    def loop(self):
        time.sleep(5)
        emptyCount = 0
        while not self.exit:
            if (self.playing):
                enterLoop = time.time()
                while (self.botsama.sound_output.get_buffer_size() > 2):
                    time.sleep(0.01)
                if (self.botsama.sound_output.get_buffer_size() == 0):
                    emptyCount += 1
                    if (emptyCount > 20):
                        print("Starting next song")
                        self.songDone()
                        emptyCount = 0
                        break
                self.botsama.sound_output.add_sound(audioop.mul(self.thread.stdout.read(480), 2, self.volume))
            else:
                time.sleep(1)

    def nextSong(self):
        if (self.curSong < 0):
            print("no current song")
            return

        left = len(self.playlist) - (self.curSong + 1)

        if (left <= 0):
            print("no song left, stopping")
            self.stopaudio()
        else:
            self.curSong += 1
            self.send_msg_channel("Playing next song: " + self.playlist[self.curSong])
            self.playcur(self)

    # callbacks
    def message_received(self, text):
        message = text.message
        user = text.actor
        print(str(user) + ": " + message)
        if message[0] == '!':
            message = message[1:].split(' ',1)
            if len(message) > 0:
                command = message[0]
                parameter = ''
                if len(message) > 1:
                    parameter = message[1]
                # Different commands
                if      command == "echo":
                    self.send_msg_channel(parameter)
                elif    command == "help":
                    self.send_msg_user(self.help, user)
                elif    command == "play":
                    self.play(parameter)
                elif    command == "add":
                    self.addSong(parameter)
                elif    command == "stop":
                    self.stopaudio()
                elif    command == "playlist":
                    self.listPlaylist()
                elif    command == "clear":
                    self.clearPlaylist()
                elif    command == "volume":
                    self.volumeChange(parameter)
                else:
                    self.send_msg_user("Unknown command<br>Try \"!help\"", user)
            else:
                return

    def volumeChange(self, parameter):
        if parameter == '':
            self.send_msg_channel("Vol.: "+ str(self.volume*100) + "%")
        elif parameter == "up":
            if (self.volume == 1):
                return
            self.volume += .1
        elif parameter == "down":
            if (self.volume == 0):
                return
            self.volume -= .1
        else:
            volume = float(parameter)
            if volume < 0:
                volume = 0
            elif volume > 100:
                volume = 100
            elif volume < 1:
                volume *= 100
            self.volume = volume/100.0


    def clearPlaylist(self):
        self.stopaudio()
        self.playlist = []
        self.curSong = -1

# Returns the streams metadata
# TODO
def getMetadata(url):
       return regStream.match(url);

# Returns a list of all videos in a youtube playlist or None if an error occurs
def getPlaylistArray(url):
    return crawl(url)

def escapeURL(url):
    if (re.match(r"<a href=.*>.*</a>", url)):
        print("Truncating html")
        url = re.sub(r"<a href=\".+\">|</a>", "", url)
    return url


# Name: youParse.py
# Version: 1.5
# Author: pantuts
# Email: pantuts@gmail.com
# Description: Parse URLs in Youtube User's Playlist (Video Playlist not Favorites)
# Use python3 and later
# Agreement: You can use, modify, or redistribute this tool under
# the terms of GNU General Public License (GPLv3).
# This tool is for educational purposes only. Any damage you make will not affect the author.
# Usage: python3 youParse.py youtubeURLhere

def crawl(url):
    sTUBE = ''
    cPL = ''
    amp = 0
    final_url = []

    if 'list=' in url:
        eq = url.rfind('=') + 1
        cPL = url[eq:]
    else:
        print('Incorrect Playlist.')
        return None
    try:
        yTUBE = urllib.urlopen(url).read()
        sTUBE = str(yTUBE)
    except urllib.URLError as e:
        print(e.reason)

    tmp_mat = re.compile(r'watch\?v=\S+?list=' + cPL)
    mat = re.findall(tmp_mat, sTUBE)

    if mat:
        for PL in mat:
            yPL = str(PL)
            if '&' in yPL:
                yPL_amp = yPL.index('&')
            final_url.append('http://www.youtube.com/' + yPL[:yPL_amp])

        return list(set(final_url))
    else:
        print('No videos found.')
        return None 
