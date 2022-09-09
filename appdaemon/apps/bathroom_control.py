import hassapi as hass
import collections
from datetime import datetime

__version__ = "2022-09-09"

#
# source: https://github.com/SuPeRMiNoR2/ha-configs/blob/main/appdaemon/apps/bathroom_control.py
#
# App to Automatically control bathroom fans
#
# --------------------------------------------
# Args:
# 
#   Required:
#     light: light switch entity
#     fan: fan switch entity
#
#   Optional:
#     delay: amount of time in seconds to wait to turn off bathroom fan. If not specified defaults to 600 seconds (10 Minutes)
#     humidity: Humidity sensor entity
#     motion: Motion sensor entity
#     presence: Presence sensor (Will not turn on fan unless this is set to "home")
#     halogging: (Enable Logging to HA Entity)

class bathroom_fan_control(hass.Hass):
    def initialize(self):
        required = ["light", "fan"]
        for a in required:
            if not a in self.args:
                self.log("Error loading, required argument '{0}' not defined".format(a))
                return
            
        # Create a variable to store the timer handle
        self.timer_handle = None
        self.backup_timer = None
        self.motion_timer_handle = None
        
        if "halogging" in self.args:
            self.halogging = True
        else:
            self.halogging = False
        
        # Check for delay, and set default if needed
        if "delay" in self.args:
            self.delay = self.args["delay"]
        else:
            self.delay = 600 # Default to 10 Minutes

        self.light = self.args["light"]
        self.fan = self.args["fan"]
        
        if "humidity" in self.args:
            self.humidity_entity = self.args["humidity"]
            self.log("Found humidity sensor, starting built in trend sensor")
            reading = float(self.get_state(self.humidity_entity)) # Get current humidity to populate the deque with
            self.hum_readings = collections.deque(60 * [reading], maxlen=60) #60 = 15 minutes, 4 readings every minute
            self.run_every(self.sensor_loop, "now",  15) #Run loop every 15 seconds
        else:
            self.humidity_entity = False

        if "presence" in self.args:
            self.presence_entity = self.args["presence"]
            self.log("Found presence sensor, will not turn on fan unless presence sensor is on")
        else:
            self.presence_entity = False

        if "motion" in self.args:
            self.motion = self.args["motion"]
            self.log("Found motion sensor, will use for fan shutoff in addition to light switch")
            self.listen_state(self.motion_callback, entity_id=self.motion)
        else:
            self.motion = False
            self.log("No motion sensor found, the fan will trigger shutdown when the light turns off or the backup timer expires") 

        self.listen_state(self.light_callback, entity_id=self.light)
        self.listen_state(self.fan_callback, entity_id=self.fan)

        if self.get_state(self.fan) == "on" and self.get_state(self.light) == "off":
            # Start timer to clean up fan on restart. The timer will not be going since this is initial load
            self.halog("Startup: Fan is on and the light is off. Starting fan shutdown timer")
            self.timer_handle = self.run_in(self.timer_callback, self.delay)
    
    def sensor_loop(self, kwargs):
        try:
            reading = float(self.get_state(self.humidity_entity))
        except ValueError: 
            reading = 0 # The sensor is unavailable, set to zero to avoid errors 

        # # Calculate average of 30 oldest readings
        # s = 0
        # for i in range (0, 30):
        #     s = s + self.hum_readings[i]
        # past_average = s / 30
        # self.log(s)

        # Calculate average from full deque
        average = round(sum(self.hum_readings) / len(self.hum_readings), 2)
        change = round(reading - average, 2)

        if change > 5: #If humidity has risen 5 degrees over the average, trigger the fan
            self.hum_trigger()

        self.hum_readings.append(reading) # Add reading to deque

    def light_callback(self, entity, attribute, old, new, kwargs):
        if self.get_state(self.fan) == "on": # Only do anything if the fan is actually on

            if old == "on" and new == "off":
                # The light shut off, restart normal timer and cancel backup timer if the timer isn't already started (From motion trigger)
                # Since the light may be motion controlled, if we restart the timer now we may be extending the fan longer than needed
                # If the timer isn't started, this was probably someone turning off the light manually. So we can start the timer now
                if not self.timer_handle:
                    self.cancel_backup()
                    self.restart_normal()
                    self.halog("Detected light shutdown, starting fan timer")
    
            if old == "off" and new == "on":
                # The light switch just went on, cancel all timers so that nothing weird happens to the person who just entered
                self.cancel_normal()
                self.restart_backup()
                self.cancel_motion()

    def motion_callback(self, entity, attribute, old, new, kwargs):
        if self.get_state(self.fan) == "on": # Only do anything if the fan is actually on
            if new == "off" and old == "on": # If motion ends, start motion timer
                self.restart_motion() 
                # After motion timer is over, normal fan timer will be started
            
            if new == "on" and old == "off": # If motion starts, cancel motion timer and normal timer and extend fan backup timer
                self.cancel_motion()
                self.cancel_normal()
                self.restart_backup()

    def fan_callback(self, entity, attribute, old, new, kwargs):
        if new == "on" and old == "off" and not self.backup_timer:
            self.halog("Detected manual fan activation")
            self.timer_handle = self.run_in(self.backup_timer_callback, 3600) #One hour safety timer
        
        if new == "off" and old == "on":
            # Cancel all timers if they aren't already cancelled, the fan may have been turned off manually
            self.cancel_backup()
            self.cancel_normal()

    def timer_callback(self, kwargs):
        self.timer_handle = None
        self.halog("Turning off fan from main timer")
        if self.backup_timer: #Cancel the backup timer regardless
            self.cancel_timer(self.backup_timer)
            self.backup_timer = None
        self.turn_off(self.fan)
    
    def backup_timer_callback(self, kwargs):
        self.backup_timer = None
        self.halog("Turning off fan from backup timer")
        if self.timer_handle: #Cancel the main timer
            self.cancel_timer(self.timer_handle)
            self.timer_handle = None
        self.turn_off(self.fan)
    
    def motion_timer_callback(self, kwargs):
        self.motion_timer_handle = None
        self.halog("Motion timer triggered, starting fan shutdown timer")
        self.restart_normal()
        self.cancel_backup()

    def hum_trigger(self):
        fanstate = self.get_state(self.fan)
        anyone_home = self.get_state(self.presence_entity)
        if fanstate == "off" and anyone_home == "home": #If home, and fan isn't running, turn it on
            self.halog("Internal trend sensor triggered, turning on fan")
            self.turn_on(self.fan)
            self.restart_backup()
            self.cancel_normal()
        # The fan will be turned off from the light, motion, or backup timer.

    def restart_backup(self):
        if self.backup_timer: #Restart backup timer
            self.cancel_timer(self.backup_timer)
        self.backup_timer = self.run_in(self.backup_timer_callback, 3600) #One hour safety timer

    def restart_normal(self):
        if self.timer_handle: #Reset normal timer
            self.cancel_timer(self.timer_handle)
        self.timer_handle = self.run_in(self.timer_callback, self.delay)
    
    def cancel_backup(self):
        if self.backup_timer:
            self.cancel_timer(self.backup_timer)
            self.backup_timer = None
    
    def cancel_normal(self):
        if self.timer_handle:
            self.cancel_timer(self.timer_handle)
            self.timer_handle = None
    
    def restart_motion(self):
        if self.motion_timer_handle:
            self.cancel_timer(self.motion_timer_handle)
        self.motion_timer_handle = self.run_in(self.motion_timer_callback, 600) # 10 Minutes no motion, trigger fan timer
    
    def cancel_motion(self):
        if self.motion_timer_handle:
            self.cancel_timer(self.motion_timer_handle)

    def halog(self, msg):
        # Hacky method to get logs from AD into HA
        # Use a logbook viewer on the sensor.adlog entity to see the logs
        if self.halogging: #Only log to HA if enabled, otherwise just log to normal log
            self.log("[HALOG] - "+ msg)
            icon = "mdi:google-cardboard"
            attributes = {"source": "AppDaemon", "icon": icon, "friendly_name": "AppDaemon Log"} 
            now = datetime.now() # current date and time
            time = now.strftime("%H:%M:%S")

            msg = "[{0}] {1}  ({2})".format(self.name, msg, time)
            self.set_state("sensor.adlog", state=msg, attributes=attributes)
        else:
            self.log(msg) #If HA logging is disabled, log to normal AD without the added text



       
        

    

       
        
