# BMS CAN Gateway
Multiplexing n x m CAN-to-CAN and simultaneous CAN-to-MQTT Gateway
for LV (48V) Battery Management Systems using Pylontech Protocol.

Pylontech protocol, while imitating the SMA Sunny Island CAN-Bus BMS protocol,
has found widespread adoption for Low-Voltage (LV) Li-Ion
battery energy storage systems (BESS).

This is intended for (massive) parallel operation of one or more Low-Voltage
Lithium-Ion-Batteries which do not supply a paralleling option
by default, and/or for parallel operation of multiple LV battery inverters
connected to one or more batteries.

Battery data is also published via MQTT telemetry for
keeping track of system state and for system control.

This also allows for remote control of instantaneous influx and outgoing power
at any given time by setting current limit setpoint.

FIXME: remote control/throttling TBD

The Python code uses asyncio, async-enabled python-can and aiomqtt packages
for cooperative multitasking.

Battery-management CAN bus interface is facilitated using the Linux kernel
socket-can API. Hardware interfaces are e.g. using the Raspberry Pi and a
multiple-CAN-bus-interface, or, alternatively, using
multiple USB-to-CAN adapters based on CANable-compatible firmware.

The gateway application is configured via text file in user home folder:
    ~/.bms_gateway/bms_config.toml

This file must be edited to suit application details.

Hardware interfaces are e.g. using the Raspberry Pi and a multiple-CAN-bus-interface:

![RPi Multiple Isolated CAN-Bus HAT image](doc/multiple_can_hat.jpg "RPi Multiple Isolated CAN-Bus HAT")

Or, alternatively, using multiple USB-to-CAN adapters based on CANable-compatible firmware:

![UCAN Board Based on STM32F072 USB to CAN Adapter image](doc/ucan_canable_compatible_usb_can_adapter.jpg "UCAN Board Based on STM32F072 USB to CAN Adapter")

2025-04-24 Ulrich Lukas
## Incomplete and for testing purposes only!

## Installation
```
cd ~/src
git clone https://github.com/ul-gh/bms_gateway
cd bms_gateway
pip install .
```

## Configuration
See config file.
A template is stored at [src/bms_gateway/bms_config_default.toml](src/bms_gateway/bms_config_default.toml),
this will be copied to user home folder at initialization.

Structure of configuration file at ~/.bms_gateway/bms_config.toml:
```
#### BMS gateway configuration ####

# Set this to true to enable the gateway application!
GATEWAY-ACTIVATED = false


#### Settings for MQTT broadcaster.
#### System state (state of all parallel connected battery BMS) is encoded
#### in JSON format and pushed periodically on the specified topic.

[mqtt]
(...)


#### Settings for total values of all parallel connected batteries

[battery]
(...)


#### List here all configured output BMSes.
#### Each output BMS interface is supposed to be connected to an
#### inverter BMS CAN input using an individual CAN interface.

# First virtual (emulated) output BMS, connected to one physical inverter
[[bmses-out]]
(...)

# Second inverter and so on...
[[bmses-out]]
(...)


#### List here all configured input BMSes (connected to battery modules).
#### Each input BMS must be connected to an individual CAN interface.

# First input BMS (connected to one battery module BMS)
[[bmses-in]]
(...)

# Second input BMS and so on...
[[bmses-in]]
(...)
```

## Usage
Run application once to initialize the configuration file, then
edit configuration and run or install application as a system service.

```
user@machine:~$ bms_gateway --init
```
Edit ~/.bms_gateway/bms_config.toml and run app:

```
user@machine:~$ bms_gateway
```

Example output:
```

```
