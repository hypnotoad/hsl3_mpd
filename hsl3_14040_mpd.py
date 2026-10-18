import threading
import time
from hsl3_14040_module_loader import ModuleLoader


def inputs_to_dict(inputs):
    return {"hostname": inputs["hostname"].value.decode('ascii'),
            "port":     int(inputs["port"].value),
            "password": inputs["password"].value.decode('utf-8')}
        
class Receiver:
    def __init__(self, set_state, log):
        self.set_state = set_state
        self.log = log
        self.outputs_initialized = False

    def start(self, connection):
        # the receiver thread connects itself from within the thread
        self.stop_event = threading.Event()
        self.connection = connection
        self.receiver_thread = threading.Thread(target=self.loop)
        self.receiver_thread.start()

    def stop(self):
        self.stop_event.set()
        self.receiver_thread.join()

    def loop(self):
        import mpd
        self.log("starting receiver thread")

        if self.connection["hostname"] == "":
            return

        receiver = self.reconnect_receiver()
        
        while not self.stop_event.is_set():
            # in contrast to the sender, we try to reconnect all the
            # time with a longer period of 10 seconds
            try:
                if not self.outputs_initialized:
                    s = receiver.status()
                    self.update_playstate(s, receiver)
                    self.update_mixer(s)

                    self.outputs_initialized = True

                # block for event
                events = receiver.idle()

                if "player" in events:
                    self.update_playstate(receiver.status(), receiver)

                if "mixer" in events:
                    self.update_mixer(receiver.status())

            except mpd.ConnectionError as e:
                self.log("Connection exception while trying to receive command: {}. Reconnecting...".format(e))

                time.sleep(1) 
                self.reconnect_receiver()

            except IOError as e:
                self.log("IO exception while trying to receive command: {}. Reconnecting...".format(e))

                time.sleep(1) 
                self.reconnect_receiver()

            except mpd.MPDError as e:
                self.log("MPD error while trying to receive command: {}".format(e))

                time.sleep(1) 
                self.reconnect_receiver()

        receiver.disconnect()

        
    def reconnect_receiver(self):
        import mpd

        self.outputs_initialized = False
        self.log("Trying to connect receiver to {}".format(self.connection["hostname"]))

        try:
            receiver = mpd.MPDClient()

            receiver.connect(self.connection["hostname"], self.connection["port"])
            if self.connection["password"] != "":
                receiver.password(self.connection["password"])

            self.log("Receiver connected to MPD version {}".format(receiver.mpd_version))
            return receiver

        except (mpd.MPDError, IOError) as e:
            self.log("IO exception while trying to connect receiver: {}".format(e))

        
    def update_playstate(self, s, receiver):
        is_paused = float(s["state"] == "pause")
        self.set_state("paused", is_paused)

        is_playing = float(s["state"] == "play")
        self.set_state("playing", is_playing)
        
        if s["state"] != "stop":
            now_playing = receiver.currentsong()
        else:
            now_playing = {}
        
        if "title" in now_playing:
            self.set_state("title", now_playing["title"])
        else:
            self.set_state("title", "")

        if "artist" in now_playing:
            self.set_state("artist", now_playing["artist"])
        else:
            self.set_state("artist", "")

        if "album" in now_playing:
            self.set_state("album", now_playing["album"])
        else:
            self.set_state("album", "")        

            
    def update_mixer(self, s):
        if "volume" in s:
            volume = float(s["volume"])
            self.set_state("volume", volume)

            
class LogicModule:

    def __init__(self, hsl3):
        self.fw = hsl3
        self.debug = self.fw.create_debug_section()

        self.module_loader = ModuleLoader(self.fw)
        self.module_loader.load_zip("mpd",
                                    "python-mpd2-3.1.2.zip",
                                    "/python-mpd2-3.1.2")

        self.logger = self.fw.get_logger(host="192.168.180.6", port=514)

    def log(self, text):
        self.debug.log(text)
        self.logger.info("mpdcontrol: {}".format(text))
        
    def __enter__(self):
        return self
    
    def __exit__(self, *exc_info):
        self.sender.disconnect()
        self.receiver.stop()
        
    def on_init(self, inputs, store):
        self.state = {}
        self.prev_volume = None # defined when muted
        self.connection = inputs_to_dict(inputs)
        self.current_playlist = store["playlist_name"].value.decode("utf-8")

        self.sender = None
        self.reconnect()

        self.receiver = Receiver(self.set_state, self.log)
        self.receiver.start(self.connection)

    def on_calc(self, inputs):
        import mpd
        
        if inputs["hostname"].changed or inputs["port"].changed or inputs["password"].changed:
            self.connection = inputs_to_dict(inputs)
            self.reconnect()
            self.receiver.stop()
            self.receiver.start(self.connection)

        # Try to reconnect only on events -- up to 3 times with 1
        # second in between so we only drop commands when mpd is not
        # available
        for attempt in range(1, 10):
            try:
                self.try_send_command(inputs)
                return

            except mpd.ConnectionError as e:
                self.log("Connection exception while trying to send command: {}. Reconnecting...".format(e))

                time.sleep(1) 
                self.reconnect()

            except IOError as e:
                self.log("IO exception while trying to send command: {}. Reconnecting...".format(e))

                time.sleep(1) 
                self.reconnect()

            except mpd.MPDError as e:
                self.log("MPD error while trying to send command: {}".format(e))

                time.sleep(1) 
                self.reconnect()


    def try_send_command(self, inputs):
        # Use such that an action is carried out if None is returned (with 'not' or '!=')
        def mpd_state(output_key):
            if not output_key in self.state:
                return None
            else:
                return self.state[output_key]
        
        # comparing with out_playing and _paused, we allow stop at any
        # time, but restrict state transitions while
        if inputs["pauseplay"].changed:
            do_pause = inputs["pauseplay"].value != 0
            if do_pause != mpd_state('paused'):
                self.sender.pause(1 if do_pause else 0)

        if inputs["startstop"].changed:
            do_play = inputs["startstop"].value != 0
            if do_play != mpd_state('playing'):
                if do_play:
                    self.sender.play()
                else:
                    self.sender.stop()

        playlist = None
        if inputs["playlist"].changed:
            playlist = inputs["playlist"].value.decode("utf-8")
        if inputs["playlist_nextprev"].changed:
            playlist = self.get_playlist_name(next = inputs["playlist_nextprev"].value != 0)
        if playlist is not None:
            self.log("Loading playlist: {}".format(playlist))
            #self.sender.stop()
            self.sender.clear()
            self.sender.load(playlist)
            #self.sender.play()

            self.current_playlist = playlist
            self.fw.set_store("playlist_name", playlist.encode("utf-8"))
            self.fw.set_output("playlist_name", playlist.encode("utf-8"))
            
        if inputs["volume"].changed:
            self.sender.setvol(int(inputs["volume"].value))

        if inputs["mute"].changed:
            # remember if volume != 0 (not muted already)
            status = self.sender.status()
            vol = int(status["volume"])                        
            if (inputs["mute"].value != 0):
                # mute if not already muted
                if vol != 0:
                    self.prev_volume = vol
                    self.sender.setvol(0)
            else:
                # unmute if current volume is 0 and previous not
                if vol == 0 and not self.prev_volume is None:
                    self.sender.setvol(self.prev_volume)
                    self.prev_volume = None

        if inputs["nextprev"].changed:
            if (inputs["nextprev"].value != 0):
                self.sender.next()
            else:
                self.sender.previous()

        if inputs["repeatall"].changed:
            if (inputs["repeatall"].value != 0):
                self.sender.repeat(1)
            else:
                self.sender.repeat(0)

        if inputs["random"].changed:
            if (inputs["random"].value != 0):
                self.sender.random(1)
            else:
                self.sender.random(0)


    def reconnect(self, inputs=None):
        import mpd

        try:
            if self.sender is not None:
                self.log("Trying to disconnect")
                self.sender.disconnect()
                self.set_state("connected", 0)
        except (mpd.MPDError, IOError) as e:
            self.log("IO exception while trying to disconnect sender: {}".format(e))

        if len(self.connection["hostname"]) == 0:
            return

        try:
            self.log("Trying to connect sender to {}".format(self.connection["hostname"]))
            self.sender = mpd.MPDClient()

            self.sender.connect(self.connection["hostname"], self.connection["port"])
            if self.connection["password"] != "":
                self.sender.password(self.connection["password"])

            self.set_state("connected", 1)
            self.log("Sender connected to MPD version {}".format(self.sender.mpd_version))

        except (mpd.MPDError, IOError) as e:
            
            self.set_state("connected", 0)
            self.log("IO exception while trying to connect sender: {}".format(e))
            

    def set_state(self, key, value):
        # set output with sbc logic
        # - can be called from any thread
        # - encodes output to utf8 bytes, if not done yet
        if type(value) == str:
            value = value.encode("utf8")
        elif type(value) == bool:
            value = int(value)

        def set_sbc(self, key, value):    
            if not key in self.state or self.state[key] != value:
                self.fw.set_output(key, value)
            self.state[key] = value
        self.fw.run_in_context(set_sbc, (self, key, value))


    def get_playlist_name(self, next):
        playlists = sorted([s["playlist"] for s in self.sender.listplaylists()])
        N = len(playlists)
        self.log("available {} playlists: {}".format(N, playlists))

        if N == 0:
            return None
        
        try:
            playlist_idx = playlists.index(self.current_playlist)
        except ValueError:
            playlist_idx = 0
        
        if next:
            playlist_idx = min(playlist_idx+1, N-1)
        else:
            playlist_idx = max(playlist_idx-1, 0)
        return playlists[playlist_idx]
