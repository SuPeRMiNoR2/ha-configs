import hassapi as hass
import datetime

__version__ = "2023-01-19"

# Source: 
#
#
# ZWave JS "Fixer"
#
# autoping
# autorefresh
# time
#
# debug

class monitor(hass.Hass):
    def initialize(self):
        if "debug" in self.args:
            self.debug = True
            self.debuglog("Debug logging enabled")
        else:
            self.debug = False

        self.debuglog("Version: "+__version__)

        if "time" in self.args:
            self.time = self.args["time"]
        else:
            self.time = "20:00:00" # Default to 10 PM

        self.debuglog("Scheduled daily battery refresh for: "+self.time)
        self.run_daily(self.daily_callback, self.time)

        if "autoping" in self.args:
            self.autoping = True
        else:
            self.autoping = False

        if "autorefresh" in self.args:
            self.autorefresh = True
        else:
            self.autorefresh = False

        self.battery_entities = []

        self.discover_devices()

    def daily_callback(self, kwargs):
        self.debuglog("Refresh running")
        self.discover_devices()
        self.refresh_batteries()

    def discover_devices(self):
        # Get full entity list from HA
        entities = self.get_state() 
        
        # Find entites that have the "battery" class
        for entity in entities:
            try:
                if entities[entity]["attributes"]["device_class"] == "battery":
                    self.battery_entities.insert(0, entity)
            except KeyError:
                pass

    def refresh_batteries(self):
        for e in self.battery_entities:
            self.debuglog("Scheduling Refresh for: "+e)
            self.call_service("zwave_js/refresh_value", entity_id=e)

    def debuglog(self, message):
        if self.debug:
            self.log(message)