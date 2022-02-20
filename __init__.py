"""
skill Radio
Copyright (C) 2020  Andreas Lorensen

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import os
import subprocess
import traceback
from urllib.parse import quote
import re
import requests

from mycroft.messagebus.message import Message
from mycroft.skills.common_play_skill import CommonPlaySkill, CPSMatchLevel
from mycroft.util import get_cache_directory

from pyradios import RadioBrowser


class Radio(CommonPlaySkill):
    def __init__(self):
        super().__init__(name="Radio")
        self.curl = None
        self.regexes = {}
        self.STREAM = '{}/stream'.format(get_cache_directory('RadioSkill'))
        self.search_providers = [self.search_default, self.search_presets, self.search_rb]
        self.rb = RadioBrowser()

    def search_rb(self, search_name):
        if search_name is None or len(search_name) < 1:
            return None
        stations = self.rb.search(name=search_name,bitrate_min=128)
        if len(stations) > 0:
            return stations[0]
        return None

    def search_presets(self, search_name):
        presets = [
            {
                "name"                    : "BBC Radio Cymru",
                "pronounciation_patterns" : ["camry", "cumry", "bbc radio camry", "radio camry"],
                "uuid"                    : "84845637-ea22-4d8c-8b2e-dce4b440d9f2"
            },
            {
                "name"                    : "RTÉ Raidió na Gaeltachta",
                "pronounciation_patterns" : ["rte irish", "irish", "rte radio irish", "irish radio" "radio irish"],
                "uuid"                    : "bf63c901-5797-4450-8d55-5b8db5835991"
            },
            {
                "name"                    : "RNE Radio Nacional",
                "pronounciation_patterns" : ["rne radio", "rne radio nacional" "radio rne", "rne"],
                "uuid"                    : "527c89ae-6e6d-11e9-af37-52543be04c81"
            },
            {
                "name"                    : "Cadena SER - Radio Valencia",
                "pronounciation_patterns" : ["cadena ser valencia"],
                "uuid"                    : "bf09733e-0e88-11e9-a80b-52543be04c81"
            },
            {
                "name"                    : "Cadena SER España",
                "pronounciation_patterns" : ["cadena ser", "cadena", "cadena ser espana"],
                "uuid"                    : "692a3b69-0f68-11ea-a87e-52543be04c81"
            }, 
            {
                "name"                    : "À Punt Ràdio",
                "pronounciation_patterns" : ["a punt", "a punt radio"],
                "uuid"                    : "d53ab822-4756-11e9-aa55-52543be04c81"
            } 
        ]
        self.log.info(f'CPS Match (radio): search_presets search_name is {search_name}')
        for preset in presets:
            for pattern in preset["pronounciation_patterns"]:
                if re.match(pattern, search_name):
                    self.log.info(f'CPS Match (radio): search_presets found: {preset["name"]}')
                    station = self.rb.station_by_uuid(preset["uuid"])
                    if len(station) < 1:
                        self.log.info(f'search_presets (radio): preset {preset["uid"]} not found in RadioBrowser')
                        return None
                    self.log.info(f'CPS Match (radio): search_presets returning station: {type(station)}')
                    return station[0]
        self.log.info(f'search_presets (radio): presets returning None')
        return None

    def search_default(self, search_name):
        if not (search_name is None or len(search_name) < 1):
            return None
        default = {
            "name" : "BBC Radio Cymru",
            "pronounciation_matches" : [],
            "uuid" : "84845637-ea22-4d8c-8b2e-dce4b440d9f2"
        }
        station = self.rb.station_by_uuid(default["uuid"])
        if len(station) < 1:
            self.log.debug(f'search_default (radio): default radio station not found')
            return None
        return station[0]
        
    def CPS_match_query_phrase(self, phrase):
        # Look for regex matches
        # Play (radio|station|stream) <data>

        match = re.search(self.translate_regex('radio'), phrase)
        data = re.sub(self.translate_regex('radio'), '', phrase)
        station = None

        for provider in self.search_providers:
            self.log.info(f'CPS Match (radio): trying provider {provider} with search {data}')
            station = provider(data)
            self.log.info(f'CPS Match (radio):VV ==================================================')
            self.log.info(f'CPS Match (radio): provider {provider} found {type(station)}')
            self.log.info(f'CPS Match (radio): nn==================================================')
            if station is not None:
                self.log.info(f'CPS Match (radio): search providers returning type({type(station)})')
                break

        if station is None:
            self.log.info('CPS Match (radio): Station not found')
            return None
        else: 
            self.log.info(f'CPS Match (radio): Station found {station} - is not none')
            self.log.info(f'CPS Match (radio): Station found type {type(station)}')
        
        if match:
            self.log.info('CPS Match (radio): ' + station['name'] +
                        ' | ' + station['url'])

            return (station['name'],
                    CPSMatchLevel.EXACT,
                    {"station": station["name"],
                        "url": station["url"],
                        "image": station['favicon']})
        else:
            return (station['name'],
                    CPSMatchLevel.TITLE,
                    {"station": station["name"],
                        "url": station["url"],
                        "image": station['favicon']})

    def CPS_start(self, phrase, data):
        url = data['url']
        station = data['station']
        image = data['image']
        try:
            self.stop()

            # (Re)create Fifo
            if os.path.exists(self.STREAM):
                os.remove(self.STREAM)
            os.mkfifo(self.STREAM)

            # Speak intro while downloading in background
            self.speak_dialog('play.radio',
                              data={"station": station},
                              wait=True)

            self.log.debug('Running curl {}'.format(url))
            args = ['curl', '-L', '-s', quote(url, safe=":/"),
                    '-o', self.STREAM]
            self.curl = subprocess.Popen(args)

            # Begin the radio stream
            self.log.info('Station url: {}'.format(url))
            self.CPS_play(('file://' + self.STREAM, 'audio/mpeg'))
            self.CPS_send_status(image=image, track=station)

        except Exception as e:
            self.log.error("Error: {0}".format(e))
            self.log.info("Traceback: {}".format(traceback.format_exc()))
            self.speak_dialog('could.not.play')

    def stop(self):
        # Stop download process if it's running.
        if self.curl:
            try:
                self.curl.kill()
                self.curl.communicate()
            except Exception as e:
                self.log.error('Could not stop curl: {}'.format(repr(e)))
            finally:
                self.curl = None
            self.CPS_send_status()
            return True

    # Get the correct localized regex
    def translate_regex(self, regex):
        if regex not in self.regexes:
            path = self.find_resource(regex + '.regex')
            if path:
                with open(path) as f:
                    string = f.read().strip()
                self.regexes[regex] = string
        return self.regexes[regex]

    def exists_url(url):
        r = requests.head(url)
        if r.status_code < 400:
            return True
        else:
            return False


def create_skill():
    return Radio()
