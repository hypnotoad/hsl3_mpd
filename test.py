#!/usr/bin/python3

from dotenv import dotenv_values
from hsl3_14040_mpd import LogicModule
from hsl3.dummy import Hsl3Framework, Hsl3Slots
import logging
import unittest
import time

class ModuleTest(unittest.TestCase):
    def setUp(self):
        config = dotenv_values(".env")
        
        self.fw = Hsl3Framework("config.json")
        self.input = {"hostname": b"beocreate.lan",
                      "port": 6600,
                      "password": config["password"].encode('utf-8'),
                      "startstop":  0,
                      "pauseplay":  0,
                      "volume":  0,
                      "playlist": b"",
                      "nextprev": 0,
                      "mute": 0,
                      "repeatall": 0,
                      "random": 0,
                      "playlist_nextprev": 0
                      }
        self.store = {
            "playlist_name": b""
        }


    def create_module(self, inputs):
        store=Hsl3Slots(self.store)
        module = LogicModule(self.fw)
        self.fw.set_module(module)
        module.on_init(inputs, store)
        time.sleep(1)
        return module

    def test_initialization(self):
        inputs=Hsl3Slots(self.input)
        with self.create_module(inputs) as module:
            module.on_calc(inputs)
            self.assertEqual(self.fw.get_output("connected"), 1)

    def test_volume(self):
        inputs=Hsl3Slots(self.input)
        with self.create_module(inputs) as module:
            for volume in [34, 35, 36]:
                inputs["volume"].changed=True
                inputs["volume"].value=volume
                module.on_calc(inputs)
                time.sleep(0.5)
                self.assertEqual(self.fw.get_output("volume"), volume)

    def test_reconnect(self):
        inputs=Hsl3Slots(self.input)
        with self.create_module(inputs) as module:
            module.on_calc(inputs)
            self.assertEqual(self.fw.get_output("connected"), 1)
            
            inputs["hostname"].changed=True
            inputs["hostname"].value=b""
            module.on_calc(inputs)
            self.assertEqual(self.fw.get_output("connected"), 0)
            
            inputs["hostname"].changed=True
            inputs["hostname"].value=b"beocreate.lan"
            module.on_calc(inputs)
            self.assertEqual(self.fw.get_output("connected"), 1)
        
    def DISABLED_test_manual(self):
        inputs=Hsl3Slots(self.input)
        with self.create_module(inputs) as module:
            module.on_calc(inputs)
            self.assertEqual(self.fw.get_output("connected"), 1)
            time.sleep(60)
    
    def test_playlist(self):
        inputs=Hsl3Slots(self.input)
        module = self.create_module(inputs)
        
        inputs.change("playlist_nextprev", 0)
        module.on_calc(inputs)
        playlist0 = self.fw.get_output("playlist_name")

        inputs.change("playlist_nextprev", 1)
        module.on_calc(inputs)
        playlist1 = self.fw.get_output("playlist_name")
        self.assertNotEqual(playlist0, playlist1)
            
        inputs.change("playlist_nextprev", 1)
        module.on_calc(inputs)
        playlist2 = self.fw.get_output("playlist_name")
        self.assertNotEqual(playlist1, playlist2)
            
        inputs.change("playlist_nextprev", 0)
        module.on_calc(inputs)
        self.assertEqual(self.fw.get_output("playlist_name"), playlist1)

        inputs.change("playlist", playlist2)
        module.on_calc(inputs)
        self.assertEqual(self.fw.get_output("playlist_name"), playlist2)

        inputs.change("playlist", playlist1)
        module.on_calc(inputs)
        self.assertEqual(self.fw.get_output("playlist_name"), playlist1)
        
if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    unittest.main()
