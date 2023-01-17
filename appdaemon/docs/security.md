# Security.py

This app is intended to provide an easy way to monitor various sensors, without requiring specific configuration of each sensor. All supported devices will be auto discovered except for water control valves.

It also allows you to create a "security system" of sorts without requiring any external alarm panel. It can work with any typical sensors, as long as they are connected to HomeAssistant. The various arming modes are described [below](#arming-modes)

You will need to create a "input_select" in home assistant and configure this app with the name of the new entity in home assistant. [Configuration Example](#full-configuration-example)

## Supported Device Types

* Motion
* Door
* Leak
* Tamper
* Smoke
* Carbon Monoxide
* Water Valve [(Manual Configuration)](#water-valve)

## Arming Modes

The arming mode is controlled by the "arm_target" entity provided in the configuration.

The modes are described below

### disarmed

In this mode motion sensors and doors are ignored entirely.

Leak, Tamper, Smoke, and CO are still monitored and will send immediate notifications

### armed_home

In this mode motion sensors are ignored but doors are monitored.

The other sensors are the same as disarmed.

### armed_away

In this mode all sensors are actively monitored

## Water Valve

If you configure a water valve, it will automatically shut off if any of your leak detectors sense a leak. It expects the entity state to be "On" when the water is on, and "Off" when the water is off.

The Zooz valve can be configured either way, so make sure it is configured correctly before trying to use it.

```
security:
  module: security
  class: ASM
  water_shutoff: switch.water_valve
```

## Full Configuration Example

This configuration has debug logging on, and has some excluded sensors and a water valve.

```
security:
  module: security
  class: ASM
  debug:
  arm_target: input_select.alarm_target
  notify_target: notifier
  water_shutoff: switch.water_valve
  ignored_sensors:
    - binary_sensor.bad_sensor
    - binary_sensor.unneeded_sensor
```

