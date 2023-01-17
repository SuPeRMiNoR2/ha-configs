# AppDaemon Scripts

These are the scripts that I use that I think are good enough / portable enough to share.

## motion_lights.py
This script handles turning lights on and off based on motion or other activity in a variety of ways.

Here are some example uses:

### Outdoor Light with different brightness levels
This is an outdoor light that I want to be off during the day, and dim during the night, unless the door or outside motion sensor gets triggered, then it goes to full power.

input_boolean.front_light_automation is a helper that I created in home assistant and turn on and off with the sunset/sunrise.  
When the boolean is on the light will turn on to the "brightness_off" value and stay there unless one of the sensors gets triggered. 

```
lights_front:
  module: motion_lights
  class: MotionLights
  sensor: 
    - binary_sensor.front_door_contact
    - binary_sensor.front_door_motion
  entity_on: light.outside_front_door_light
  brightness_on: 100
  brightness_off: 25
  condition: input_boolean.front_light_automation
  delay: 600
```

## security.py
This is my replacement to using the HSM module on my old Hubitat. It isn't a real alarm system and it doesn't integrate with a real alarm system. 
It is just a handy way of watching doors and motion sensors while I am gone or sleeping. 

It features autodiscovery of supported sensor types (with manual exclusion).

### Setup
You need to create a input_select helper with three states (disarmed, armed_home, armed_away). You also specify the name you want it to use.

It will create two sensors that indicate the system status. You will probably want to create an entity card in home assistant that includes all three entities.

### Configuration Example

```
security:
  module: security
  class: ASM
  arm_target: input_select.alarm_target
  notify_target: mobile_app
  ignored_sensors:
    - binary_sensor.sensor1
    - binary_sensor.sensor2
```
