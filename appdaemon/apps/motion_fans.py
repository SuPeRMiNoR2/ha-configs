import hassapi as hass

__version__ = "2022-06-29"

# Motion Fans
# App to Automatically control fans based on motion or other activity
#
# Args:
# 
# Required:
#
# sensor: binary sensor to use as trigger
# Or, 
# sensor:
#   - sensor1
#   - sensor2 
# 
# fan: The fan entity
# temperature: Temperature entity to pick the fan speed
# 
# Optional:
# 
# speedmap: Speedmap, defaults to 1
# delay: amount of time in seconds after turning on to turn off again. If not specified defaults to 2700 seconds 
# condition: Entity that needs to be on for automations to run
#
# If the condition shuts off while the fan is already on, it will wait the normal delay before turning off

class MotionFan(hass.Hass):
    def initialize(self):
        # Create a variable to store the timer handle
        self.timer_handle = None 

        # Check for delay, and set default if needed
        if "delay" in self.args:
            self.delay = self.args["delay"]
        else:
            self.delay = 2700

        if "fan" in self.args:
            self.fan_entity = self.args["fan"]
        else:
            self.error("No fan specfied")

        if "temperature" in self.args:
            self.temperature_entity = self.args["temperature"]
        else:
            self.error("No temperature sensor specfied")

        if "speedmap" in self.args:
            self.speedmode = int(self.args["speedmap"])
        else:
            self.speedmode = 1 #Default to 1

        # Check if sensor entity or sensor entity list is defined
        if "sensor" in self.args:
            sensor = self.args["sensor"]
            if type(sensor) == str:
                # Single entity
                self.listen_state(self.motion_callback, self.args["sensor"])
                #self.log("Subscribing to sensor {0}".format(sensor))
            elif type(sensor) == list:
                #self.log("Subscribing to sensors {0}".format(sensor))
                for entity in sensor:
                    self.listen_state(self.motion_callback, entity)
        else:
            self.error("No sensor specified. Please edit your app configuration")

        # Check for condition entity, subscribe and set variable
        if "condition" in self.args:
            self.condition_entity = self.args["condition"]
            self.listen_state(self.condition_callback, self.condition_entity)
        else:
            self.condition_entity = False
        
        # Clean up current state
        if self.get_allowed() and self.get_state(self.fan_entity) == "on":
            self.log("Restarted timer because the fan is on during controller startup")
            self.restart_timer()

    def terminate(self):
        if self.timer_handle != None:
            self.cancel_timer(self.timer_handle)

    def motion_callback(self, entity, attribute, old, new, kwargs):
        if self.condition_entity:
            automation_allowed = self.get_state(self.condition_entity)
        else:
            automation_allowed = "on"

        if (old == "off" and new == "on") and automation_allowed == "on":
            self.log("Sensor {0} activated".format(entity))
            self.fan_on()

    def condition_callback(self, entity, attribute, old, new, kwargs):
        if old == "off" and new == "on" and self.get_state(self.fan_entity) == "on":
            self.log("Restarted timer because the fan is on and the condition came on")
            self.restart_timer()

    def timer_callback(self, kwargs):
        # Receives timer events

        # Clear timer
        self.timer_handle = None 

        if self.get_allowed():
            # Turn off fan if allowed
            self.fan_off()            
            
    def fan_on(self):
        # Turns on fan, and pick speed
        # This section won't run unless the condition allows for it 

        temp = float(self.get_state(self.temperature_entity))
        speed = self.speed_map(temp)

        if self.timer_handle: # If there is an active timer
            if self.get_state(self.fan_entity) == "off":
                self.log("Potential issue: fan is off even though there is an active timer. Did someone turn it off?")
                self.turn_on(self.fan_entity, percentage=speed)
        else: # If there isn't an active timer
            self.log("Activating {0} to {1}".format(self.fan_entity, speed))
            self.turn_on(self.fan_entity, percentage=speed)
       
        # Restart off timers 
        self.restart_timer()

    def fan_off(self):
        self.log("Turning off {0}".format(self.fan_entity))
        self.turn_off(self.fan_entity)

    def restart_timer(self):
        if self.timer_handle != None:
            self.cancel_timer(self.timer_handle)
        self.timer_handle = self.run_in(self.timer_callback, self.delay)

    def get_allowed(self):
        if self.condition_entity:
            automation_allowed = self.get_state(self.condition_entity)
        else:
            automation_allowed = "on"
        
        if automation_allowed == "on":
            return True
        else: 
            return False

    def speed_map(self, temp):
        pmap = {"high": 100, "medium": 67, "low": 33, "off": 0}
        
        # Aggressive cooling
        if self.speedmode == 1: # 
            if temp > 75:
                return(pmap["high"])
            elif temp > 72:
                return(pmap["medium"])
            elif temp > 64:
                return(pmap["low"])
            elif temp <= 62:
                return(pmap["off"])

        # Slightly less aggressive cooling
        elif self.speedmode == 2:
            if temp > 79:
                return(pmap["high"])
            elif temp > 72:
                return(pmap["medium"])
            elif temp > 64:
                return(pmap["low"])
            elif temp <= 62:
                return(pmap["off"])


