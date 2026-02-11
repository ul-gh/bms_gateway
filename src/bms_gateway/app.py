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
import sys
import threading
from contextlib import AsyncExitStack

from bms_gateway import app_config
from bms_gateway.bms_state import BMSState
from bms_gateway.bms_state_combiner import BMSStateCombiner
from bms_gateway.lv_bms import BMSIn, BMSOut
from bms_gateway.mqtt_broadcaster import MQTTBroadcaster

parser = argparse.ArgumentParser(prog=__package__, description=__doc__)
_ = parser.add_argument("-v", "--verbose", action="store_true", help="Set loglevel to DEBUG")
_ = parser.add_argument("-q", "--quiet", action="store_true", help="Set loglevel to WARNING")
_ = parser.add_argument("-d", "--daemon", action="store_true", help="Run in background thread.")
cmdline = parser.parse_args()


if cmdline.verbose:  # pyright: ignore[reportAny]
    logging.basicConfig(level=logging.DEBUG)
elif cmdline.quiet:  # pyright: ignore[reportAny]
    logging.basicConfig(level=logging.WARNING)
else:
    logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("bms_gateway.app")


# App configuration read from file: "~/bms_gateway/bms_config.toml"
# Default configuration: See source tree file "bms_config_default.toml"
conf = app_config.init_or_read_from_config_file(init=cmdline.init)  # pyright: ignore[reportAny]


t_main: threading.Thread | None = None
app_running = threading.Event()

combiner = BMSStateCombiner(conf.battery)


async def main_task() -> None:
    """Receives BMS input data, combines and broadcasts to all inverters."""
    mqtt_out: MQTTBroadcaster | None = None
    async with AsyncExitStack() as stack:
        bmses_in: list[BMSIn] = [BMSIn(conf) for conf in conf.bmses_in]
        bmses_out: list[BMSOut] = [BMSOut(conf) for conf in conf.bmses_out]
        for bms in bmses_in + bmses_out:
            _ = await stack.enter_async_context(bms)
        if conf.mqtt.ACTIVATED:
            mqtt_client: MQTTBroadcaster = MQTTBroadcaster(conf.mqtt)
            _ = await stack.enter_async_context(mqtt_client)
        while app_running.is_set():
            # Read all input BMSes
            states_in: list[BMSState] = await asyncio.gather(*(bms.get_state() for bms in bmses_in))
            # Calculate total and average values, error flags and corrections
            state_out: BMSState = combiner.combine_bms_states(states_in)
            logger.debug(state_out)
            # Set calculated state on all virtual output BMSes.
            # Individual current scaling values are applied from config file.
            _ = await asyncio.gather(*(bms.set_state(state_out) for bms in bmses_out))
            if conf.mqtt.ACTIVATED:
                await mqtt_client.set_state(state_out)  # pyright: ignore[reportPossiblyUnboundVariable]


def run_app() -> None:
    """Run app in foreground (also as a system service)."""
    asyncio.run(main_task())


def start() -> None:
    """Run app in new background thread."""
    global main_thread
    app_running.set()
    main_thread = threading.Thread(target=run_app, name="bms_gateway", daemon=False)
    main_thread.start()
    logger.info("App running in thread: %s", main_thread)

def stop() -> None:
    """Stop energy_modulator app."""
    logger.info("stop() called..")
    app_running.clear()
    main_thread.join()


def main() -> None:
    """Run Energy Modulator Server."""
    try:
        if cmdline.daemon:  # pyright: ignore[reportAny]
            logger.info("Starting Energy Modulator Server in background thread.")
            start()
        else:
            logger.info("Starting Energy Modulator Server")
            run_app()
    except KeyboardInterrupt:
        # Suppress sys.exit() when running interactively.
        stop()
        if "get_ipython" not in locals():
            sys.exit(0)
    except Exception:
        # Main task should never terminate.
        logger.exception("Exception in main()!")
        stop()
        sys.exit(1)


if __name__ == "__main__":
    main()