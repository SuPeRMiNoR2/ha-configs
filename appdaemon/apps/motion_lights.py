import hassapi as hass
import helpers

# App to Automatically control lights based on motion or other activity
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
# entity_on : entity to turn on when detecting motion, can be a light, script, scene or anything else that can be turned on
# 
#
# Optional:
#
# delay: amount of time in seconds after turning on to turn off again. If not specified defaults to 300 seconds (5 Minutes)
# entity_off : If you need to use a seperate entity or scene for the off mode, specify it here. If not specified, it will use entity_on
# brightness_on: Brightness (0 - 100) to set the entity to when turning it on
# brightness_off: Brightness (0 - 100) to set the entity too instead of turning it off
# condition: Entity that needs to be on for automations to run.
# off_modifier: When this entity is on, brightness_off is the off mode, when this entity is off 
#   brightness_off will be ignored and the light will actually turn off. This allows you to have different behaviors during certain conditions

class MotionLights(hass.Hass):
    def initialize(self):
        self.log("Beginning initialization")

        # Create a variable to store the timer handle
        self.handle = None 

        # Check for delay, and set default if needed
        if "delay" in self.args:
            self.delay = self.args["delay"]
        else:
            self.delay = 300 # 5 Minutes

        if "brightness_on" in self.args:
            self.brightness_on = helpers.brightness_up(self.args["brightness_on"])
        else:
            self.brightness_on = False
        
        if "brightness_off" in self.args:
            self.brightness_off = helpers.brightness_up(self.args["brightness_off"])
        else:
            self.brightness_off = False

        if "entity_on" in self.args:
            self.entity_on = self.args["entity_on"]
        else:
            self.log("Error, no entity on specfied")

        if "entity_off" in self.args:
            self.entity_off = self.args["entity_off"]
        else:
            self.log("No entity off specfied, using entity_on ({0})".format(self.entity_on))
            self.entity_off = self.entity_on

        # Check if sensor entity or sensor entity list is defined
        if "sensor" in self.args:
            sensor = self.args["sensor"]
            if type(sensor) == str:
                # Single entity
                self.listen_state(self.motion_callback, self.args["sensor"])
                self.log("Subscribing to sensor {0}".format(sensor))
            elif type(sensor) == list:
                self.log("Subscribing to sensors {0}".format(sensor))
                for entity in sensor:
                    self.listen_state(self.motion_callback, entity)
        else:
            self.log("Error, No sensor specified. Please edit your app configuration")

        # Check for condition entity, subscribe and set variable
        if "condition" in self.args:
            self.condition_entity = self.args["condition"]
            self.listen_state(self.condition_callback, self.condition_entity)
            self.log("Subscribed to condition {0}".format(self.condition_entity))
        else:
            self.condition_entity = False
        
        if self.get_state(self.entity_on) == "on":
            if self.condition_entity:
                if self.get_state(self.condition_entity) == "off":
                    self.log("The light is currently on, but the condition doesn't allow it to be on. Turning off")
                    self.light_off()

        self.restart_timer()
        self.log("Initialization Complete")

    def motion_callback(self, entity, attribute, old, new, kwargs):
        if self.condition_entity:
            automation_allowed = self.get_state(self.condition_entity)
        else:
            automation_allowed = "on"

        if new == "on" and automation_allowed == "on":
            self.light_on()

    def condition_callback(self, entity, attribute, old, new, kwargs):
        # If the condition entity just switched on, and there is a brightness_off defined, turn on the light to the "off" brightness
        if new == "on" and self.brightness_off:
            if self.get_state(self.entity_on) == "off":
                self.turn_on(self.entity_on, brightness=self.brightness_off)
                self.log("Turned on {0} to brightness_off because condition just turned on".format(self.entity_on)) 

        # If the off modifier entity just switched off, and the light is on *at the brightness_off* level turn off the light
        # *add me
        if new == "off":
            current_state = self.get_state(self.entity_on)
            current_brightness = self.get_state(self.entity_on, attribute="brightness")
            if (current_state == "on") and (current_brightness == self.brightness_off):
                self.log("Turned off {0} because condition just turned off and the light was at the brightness_off value".format(self.entity_on))
                self.turn_off(self.entity_off) 

    def light_off_callback(self, kwargs):
        # Receives timer events
        self.log("Timer Finished")
        self.light_off()            
            
    def light_on(self):
        # Turns on light, if brightness_on is defined turns on light to brightness
        # This section won't run unless the condition allows for it
       
        if self.brightness_on:
            self.log("Event Triggered: turning {0} on to brightness {1} and restarting timer".format(self.entity_on, self.brightness_on))
            self.turn_on(self.entity_on, brightness=self.brightness_on)
        else:
            self.log("Event Triggered: turning {0} on and restarting timer".format(self.entity_on))
            self.turn_on(self.entity_on)
       
        # Restart off timers
        self.restart_timer()

    def light_off(self):
        # Turns off light, following brightness_off if specified
        if self.brightness_off:
            if self.condition_entity:
                # If a brightness_off and condition is defined
                current_state = self.get_state(self.condition_entity)
                if current_state == "on":
                    # If condition is currently on, set light to the brightness_off level instead of turning it off
                    self.log("Setting {0} to brightness {1}".format(self.entity_off, self.brightness_off))
                    self.turn_on(self.entity_on, brightness=self.brightness_off)
                if current_state == "off":
                    # If the condition is off, turn off the light
                    self.log("Turning {} off".format(self.entity_off))
                    self.turn_off(self.entity_off)
            else:
                # No condition, but brightness_off - set light to brightness_off
                self.log("Setting {0} to brightness {1}".format(self.entity_off, self.brightness_off))
                self.turn_on(self.entity_on, brightness=self.brightness_off)
        else:
            # No brightness off, turn light off
            self.log("Turning {} off".format(self.entity_off))
            self.turn_off(self.entity_off)

    def restart_timer(self):
        if self.handle != None:
            if self.info_timer(self.handle) != None:
                self.log("Cancelling Timer")
                self.cancel_timer(self.handle)
        self.log("Starting Timer")
        self.handle = self.run_in(self.light_off_callback, self.delay)
