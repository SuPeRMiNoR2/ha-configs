import hassapi as hass
import datetime

__version__ = "2022-09-09"

# Original Source: https://raw.githubusercontent.com/AppDaemon/appdaemon/dev/conf/example_apps/battery.py
# App to send warnings for devices running low on battery
#
# Args:
#
# notifier = notifier entity to send reports to
# 
# Optional:
#
# onrestart = if this arg is present battery levels will be checked on reload
# threshold = value below which battery levels are reported and notification. Defaults to 25
# excluded:
#   - excluded_entity_id
#   - excluded_entity_id
#

class Battery(hass.Hass):
    def initialize(self):
        required = ["notifier"]
        for a in required:
            if not a in self.args:
                self.log("Error loading, required argument '{0}' not defined".format(a))
                return

        self.notifier = self.args["notifier"]

        if "threshold" in self.args:
            self.threshold = int(self.args["threshold"])
        else:
            self.threshold = 25

        time = "18:00:00" # 6 PM
        self.run_daily(self.check_batteries, time)

        self.excluded = []
        if "excluded" in self.args:
            ex = self.args["excluded"]
            if type(ex) == str:
                # Single entity
                self.excluded.insert(0, ex)
            elif type(ex) == list:
                self.excluded = ex
        
        devices = self.find_devices()
        for d in devices:
            self.listen_state(self.battery_callback, d)

        if "onrestart" in self.args:
            self.check_batteries(self)
    
    def battery_callback(self, entity, attribute, old, new, kwargs):
        old = self.normalize_levels(old)
        new = self.normalize_levels(new)

        if old and new: # Verify that neither is None
            if new > old and (old <= self.threshold) and (new > self.threshold): # If the battery went up and it started below the threshold
                message = "Battery {0} went up from {1} to {2}".format(entity, old, new)
                self.log(message)
                self.notify(message, title="Battery Report", name=self.notifier)
    
    def find_devices(self):
        # Find devices with battery class and return list
        hastate = self.get_state()
        devices = []
        for device in hastate:
            try:
                if hastate[device]["attributes"]["device_class"] == "battery" and not device in self.excluded:
                    devices.insert(0, device)
            except KeyError:
                pass
        return devices

    def normalize_levels(self, level):
        # Takes in battery level state and converts it to number only
        try: 
            # Try to convert level to number, catch ValueError
            cleanlevel = int(float(level)) #Float first to handle decimal, but I don't want the decimal
        except ValueError:
            # The level isn't a number, handle known states and set any unknown states to None
            if level == "off":
                cleanlevel = 99
            if level == "on":
                cleanlevel = 1
            else:
                cleanlevel = None
        except TypeError: 
            # The level may be None
            cleanlevel = None

        return cleanlevel

    def check_batteries(self, kwargs):
        self.log("Checking Battery States")

        values = {} # Dict of all battery levels
        low = [] # List of devices that are low
        invalid = [] # List of devices with invalid battery states

        devices = self.find_devices()
        for device in devices:
            cleanlevel = self.normalize_levels(self.get_state(device))
                
            if cleanlevel is not None:
                if cleanlevel < int(self.threshold):
                    low.append(device)
                values[device] = cleanlevel
            else:
                invalid.append(device)

        state = self.datetime().strftime("Updated %I:%M:%S %p") # current date and time
        attributes = {"battery_levels": values, "low_batteries": low, "invalid_devices": invalid} 
        self.set_state("sensor.battery_tracker", state=state, attributes=attributes)

        message = "Battery Level Report \n"
        if low:
            message += "The following devices are low: (< {}) \n\n".format(self.threshold)
            for device in low:
                message = message + device + " " + str(values[device]) + "\n"

            self.log("Low Battery Report: "+message)
            self.log("Sending battery report to: notify."+self.notifier)
            self.notify(message, title="Low Battery Report", name=self.notifier)
            if invalid:
                self.log("Invalid/Ignored devices: {0}".format(invalid))
