#!/usr/bin/env python3
"""Multiplexing n x m CAN-to-CAN and simultaneous CAN-to-MQTT Gateway.

BMS gateway for LV (48V) Battery Management Systems using Pylontech Protocol.

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

2025-04-24 Ulrich Lukas
"""

import argparse
import asyncio
import logging
import threading
from contextlib import AsyncExitStack

from . import app_config
from .bms_state_combiner import BMSStateCombiner
from .lv_bms import BMSIn, BMSOut
from .mqtt_broadcaster import MQTTBroadcaster

parser = argparse.ArgumentParser(prog=__package__, description=__doc__)
parser.add_argument("--init", action="store_true", help="Initialize configuration file and exit")
parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose (debug) output")
cmdline = parser.parse_args()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG if cmdline.verbose else logging.INFO)


# App configuration read from file: "~/bms_gateway/bms_config.toml"
# Default configuration: See source tree file "bms_config_default.toml"
conf = app_config.init_or_read_from_config_file(init=cmdline.init)

t_main: threading.Thread = None
thread_stop = threading.Event()

combiner = BMSStateCombiner(conf.battery)


async def main_task() -> None:
    """Receives BMS input data, combines and broadcasts to all inverters."""
    async with AsyncExitStack() as stack:
        bmses_in = [BMSIn(bms_conf) for bms_conf in conf.bmses_in]
        for bms in bmses_in:
            await stack.enter_async_context(bms)
        bmses_out = [BMSOut(bms_conf) for bms_conf in conf.bmses_out]
        for bms in bmses_out:
            await stack.enter_async_context(bms)
        if conf.mqtt.ACTIVATED:
            mqtt_out = MQTTBroadcaster(conf.mqtt)
            await stack.enter_async_context(mqtt_out)
        while not thread_stop.isSet():
            # Read all input BMSes
            getters = (bms.get_state() for bms in bmses_in)
            states_in = await asyncio.gather(*getters)
            # Calculate total and average values, error flags and corrections
            state_out = combiner.calculate_result_state(states_in)
            logger.debug(state_out)
            # Set calculated state on all virtual output BMSes.
            # Individual current scaling values are applied from config file.
            setters = (bms.set_state(state_out) for bms in bmses_out)
            await asyncio.gather(*setters)
            if conf.mqtt.ACTIVATED:
                await mqtt_out.set_state(state_out)


def run_app() -> None:
    """Run app in foreground (also as a system service)."""
    try:  # noqa: SIM105
        asyncio.run(main_task())
    except KeyboardInterrupt:
        pass


def run_app_bg() -> None:
    """Run app in background thread (for debugging in ipython etc)."""
    global t_main  # noqa: PLW0603
    thread_stop.clear()
    t_main = threading.Thread(target=run_app)
    t_main.start()


def stop_app() -> None:
    """Stop app running in background thread."""
    thread_stop.set()


if __name__ == "__main__":
    run_app()
