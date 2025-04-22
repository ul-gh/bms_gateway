# BMS CAN Gateway

Multiplexing n x CAN - to - CAN and simultaneous CAN - to - MQTT Gateway
for LV (48V) Battery Management Systems using Pylontech Protocol.
---

Pylontech Protocol, while imitating the SMA Sunny Island CAN-Bus BMS protocol,
has found widespread adoption for Low-Voltage (LV) Li-Ion
battery energy storage systems (BESS).

This is intended for (massive) parallel operation of multiple Low-Voltage
Lithium-Ion-Batteries which do not supply a paralleling option
by default. Battery data is also published via MQTT telemetry for
keeping track of system state and for system control.

This also allows for easy control of instantaneous influx and outgoing power
at any given time by setting and limiting battery current setpoint.

2025-04-25 Ulrich Lukas
## Incomplete and for testing purposes only!

## Installation
```
cd /home/src
git clone https://github.com/ul-gh/bms_gateway
cd bms_gateway
pip install .
```

```

```

Example output:
```

```
