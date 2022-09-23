import hassapi as hass
import datetime

__version__ = "2022-09-23"

# Source: 
#
#
# Security system to replace HSM on Hubitat
#
# Will locate all motion and door sensors, add entity ID's to ignored_sensors to ignore
# Only watches doors in armed_home, watches doors and motion sensors in armed_away
#
# Required:
# arm_target - Entity id of helper to select arming state from HA (input_select helper)
# notify_target - Entity ID to send security notifications to
#
# Optional:
# name: Security system name (Used in notifications, defaults to ASM)
# ignored_sensors: Sensors to ignore 
#  -
#  -
# debug: #Enable debug logging

class ASM(hass.Hass):
    def initialize(self):
        required = ["arm_target", "notify_target"]
        for a in required:
            if not a in self.args:
                self.log("Error loading, required argument '{0}' not defined".format(a))
                return

        if "debug" in self.args:
            self.debug = True
            self.debuglog("Debug logging enabled")
        else:
            self.debug = False

        self.debuglog("Version: "+__version__)

        # Init state variables and entities
        self.arm_target_entity = self.args["arm_target"]
        self.notify_target = self.args["notify_target"]

        if "name" in self.args:
            self.system_name = self.args["name"]
        else:
            self.system_name = "ASM" # Pick default name

        # Initialize water shutoff if configured
        if "water_shutoff" in self.args:
            self.water_shutoff_entity = self.args["water_shutoff"]
            self.listen_state(self.valve_state_callback, entity_id=self.water_shutoff_entity)
        else:
            self.water_shutoff_entity = False

        self.alarm_state_entity = "binary_sensor.{0}_alarm_state".format(self.system_name.lower())
        self.arm_state_entity = "sensor.{0}_arming_state".format(self.system_name.lower())
        
        # Parse ignored sensor list
        if "ignored_sensors" in self.args:
            self.ignored_sensors = self.args["ignored_sensors"]
        else:
            self.ignored_sensors = []

        devices = self.get_state() #Get Device List from HA

        self.motion_sensors = {}
        self.door_sensors = {}
        self.leak_sensors = {}
        self.tamper_sensors = {}
        
        self.monitored_devices = [] #List for display to user

        for device in devices:
            if ("attributes" in devices[device]) and (device not in self.ignored_sensors):
                if "device_class" in devices[device]["attributes"]:
                    if devices[device]["attributes"]["device_class"] == "motion" and not device in self.ignored_sensors:
                        details = {"entity_id": device, "friendly_name": devices[device]["attributes"]["friendly_name"]}
                        self.motion_sensors[device] = details
                        self.debuglog("Added Motion {1}".format(details["friendly_name"], device))
                        self.monitored_devices.insert(0, details["friendly_name"])
                    if devices[device]["attributes"]["device_class"] == "door" and not device in self.ignored_sensors:
                        details = {"entity_id": device, "friendly_name": devices[device]["attributes"]["friendly_name"]}
                        self.door_sensors[device] = details
                        self.debuglog("Added Door {1}".format(details["friendly_name"], device))
                        self.monitored_devices.insert(0, details["friendly_name"])
                    if devices[device]["attributes"]["device_class"] == "tamper" and not device in self.ignored_sensors:
                        details = {"entity_id": device, "friendly_name": devices[device]["attributes"]["friendly_name"]}
                        self.tamper_sensors[device] = details
                        self.debuglog("Added Tamper Sensor {1}".format(details["friendly_name"], device))
                        self.monitored_devices.insert(0, details["friendly_name"])
                    if devices[device]["attributes"]["device_class"] == "moisture" and not device in self.ignored_sensors:
                        details = {"entity_id": device, "friendly_name": devices[device]["attributes"]["friendly_name"]}
                        self.leak_sensors[device] = details
                        self.debuglog("Added Leak Sensor {1}".format(details["friendly_name"], device))
                        self.monitored_devices.insert(0, details["friendly_name"])

        for door in self.door_sensors:
            self.listen_state(self.door_callback, entity_id=door, new="on")
        for motion in self.motion_sensors:
            self.listen_state(self.motion_callback, entity_id=motion, new="on")
        for leak in self.leak_sensors:
            self.listen_state(self.leak_callback, entity_id=leak)
        for tamper in self.tamper_sensors:
            self.listen_state(self.tamper_callback, entity_id=tamper)

        self.listen_state(self.arm_target_callback, entity_id=self.arm_target_entity)

        # Init Arm and Alarm States
        self.update_alarm_state("off")
        self.update_arm_state(self.get_state(self.arm_target_entity)) # Set arm state to what the arm target state currently is

    def leak_callback(self, entity, attribute, old, new, kwargs):
        friendly_name = self.leak_sensors[entity]["friendly_name"]
        if new == "on":
            msg = "Triggered: {0}".format(friendly_name)
            self.send_notification(msg, type="Water Alarm")
            if self.water_shutoff_entity:
                self.handle_water_valve_start(entity)
        if old == "on" and new == "off":
            msg = "Cleared: {0}".format(friendly_name)
            self.send_notification(msg, type="Water Alert")
    
    def valve_state_callback(self, entity, attribute, old, new, kwargs):
        wentity = self.water_shutoff_entity

        # Send a warning if the water valve looses connection
        if new == "unavailable":
            msg = "Water Valve {0} is now unavailable".format(self.water_shutoff_entity)
            self.send_notification(msg, type="System Monitoring")
        
        if old == "unavailable" and (new == "on" or new == "off"):
            msg = "Water Valve {0} no longer unavailable, now {1}".format(self.water_shutoff_entity, new)
            self.send_notification(msg, type="System Monitoring")
    
    def handle_water_valve_start(self, triggerentity):
        self.send_notification("Scheduling water shutoff in 1 minute in response to water alarm", type="Automatic Shutoff")
        self.shutoff_timer = self.run_in(self.handle_water_valve_finish, 60, triggerentity=triggerentity)

    def handle_water_valve_finish(self, kwargs):
        # Check if leak alarm is still active
        leakstate = self.get_state(kwargs['triggerentity'])
        if leakstate == "on":
            self.send_notification("Shutting off water now", type="Automatic Shutoff")
            self.turn_off(self.water_shutoff_entity)
        else:
            self.send_notification("Leak Sensor is no longer active, leaving water on", type="Automatic Shutoff")


    def tamper_callback(self, entity, attribute, old, new, kwargs):
        friendly_name = self.tamper_sensors[entity]["friendly_name"]
        if new == "on" and old == "off":
            msg = "Tampering detected on: {0}".format(friendly_name)
            self.send_notification(msg, type="Tamper Alarm")
        if old == "on" and new == "off":
            msg = "Tampering cleared on: {0}".format(friendly_name)
            self.send_notification(msg, type="Tamper Alert")
    
    def arm_target_callback(self, entity, attribute, old, new, kwargs):
        self.update_arm_state(new)

    def motion_callback(self, entity, attribute, old, new, kwargs):
        details = self.motion_sensors[entity]
        if self.arm_state == "armed_away":
            self.trigger_alarm("motion", entity, details)
    
    def door_callback(self, entity, attribute, old, new, kwargs):
        details = self.door_sensors[entity]
        if self.arm_state == "armed_away":
            self.trigger_alarm("door", entity, details)
        if self.arm_state == "armed_home":
            self.trigger_alarm("door", entity, details)

    def trigger_alarm(self, stype, entity, entity_details):
        if self.alarm_state == "off": # New alarm since being armed
            self.update_alarm_state("on") # Set system alarm state to on
            message = "Triggered: {sensor} \nAlarm State: {arm_state}".format(sensor=entity_details["friendly_name"], arm_state=self.arm_state)
            self.send_notification(message, "Alarm")
        else: # Alarm already triggered
            message = "Triggered: " + entity_details["friendly_name"]
            self.send_notification(message, "Alert")

    def update_alarm_state(self, new):
        if new == "off":
            icon = "mdi:check-underline-circle-outline"
        elif new == "on":
            icon = "mdi:home-alert-outline"
        else:
            self.warning("update_alarm_state called with invalid state")
            return

        attributes = {"source": "AppDaemon: security.py", "icon": icon, "friendly_name": self.system_name + " Alarm State", "device_class": "safety"} 
        self.alarm_state = new
        self.set_state(self.alarm_state_entity, state=new, attributes=attributes)
    
    def update_arm_state(self, new):
        if new == "disarmed":
            icon = "mdi:home-lock-open"

        elif new == "armed_home":
            icon = "mdi:home-lock"
            self.find_open_doors()

        elif new == "armed_away":
            icon = "mdi:lock"
            self.find_open_doors()

        attributes = {"source": "AppDaemon: security.py", "version": __version__, "icon": icon, "friendly_name": self.system_name + " Arm State", "Monitored Devices": self.monitored_devices } 
        self.arm_state = new
        self.set_state(self.arm_state_entity, state=new, attributes=attributes)

        # Clear alarm when disarmed
        if new == "disarmed" and self.alarm_state == "on": 
            self.send_notification("Disarmed during active alarm, clearing alarm", "Alert")
            self.update_alarm_state("off")
    
    def find_open_doors(self):
        #Check for any doors that are already opening when arming
        for door in self.door_sensors:
            state = self.get_state(door)
            if state == "on":
                self.send_notification("Found door {} open while arming".format(self.door_sensors[door]["friendly_name"]), "Warning")


    def send_notification(self, message, type):
        title = "[{0} {1}]".format(self.system_name, type)
        self.log(title + " " + message)
        self.notify(message + "\n", title=title, name=self.notify_target)

    def debuglog(self, message):
        if self.debug:
            self.log(message)

    
