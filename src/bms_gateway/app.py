#!/usr/bin/env python3
"""Multiplexer Gateway for LV BMS using Pylontech Protocol."""
import argparse
import asyncio
import logging
import threading
from contextlib import AsyncExitStack

from .bms_state import BmsState
from .lv_bms import BMS_In, BMS_Out
from .mqtt_broadcaster import MQTTBroadcaster

logger = logging.getLogger(__name__)

CAN_IF_OUT_DEFAULT: str = "vcan0"
CAN_IFS_IN_DEFAULT: list[str] = ["vcan1", "vcan2"]

MQTT_TOPIC_DEFAULT: str = "tele/bms/state"
MQTT_BROKER_DEFAULT: str = "localhost"
MQTT_PORT_DEFAULT: int = 1883
MQTT_INTERVAL_DEFAULT: float = 10.0

parser = argparse.ArgumentParser(prog=__package__, description=__doc__)
parser.add_argument("--sync_interval", type=float, default=None,
                    help="Send SYNC message to inverter cyclically with this period in seconds. Default: Do not send SYNC.")
parser.add_argument("--no_push_mqtt", action="store_true",
                    help="Do not push incoming BMS telegrams to MQTT")
parser.add_argument("--mqtt_interval", type=float, default=MQTT_INTERVAL_DEFAULT,
                    help=f"MQTT transmit interval. Default: MQTT_INTERVAL_DEFAULT")
parser.add_argument("-t", "--topic", type=str, default=MQTT_TOPIC_DEFAULT,
                    help=f"MQTT topic to push to. Default: MQTT_TOPIC_DEFAULT")
parser.add_argument("-b", "--broker", type=str, default=MQTT_BROKER_DEFAULT,
                    help=f"MQTT host (broker) to push to. Default: MQTT_BROKER_DEFAULT")
parser.add_argument("--port", type=str, default=MQTT_PORT_DEFAULT,
                    help=f"MQTT broker port. Default: MQTT_PORT_DEFAULT")
parser.add_argument("-v", "--verbose", action="store_true",
                    help="Enable verbose (debug) output")
parser.add_argument("if_out", type=str, nargs="?", default=CAN_IF_OUT_DEFAULT,
                    help=f"CAN interface to use for output to inverter. Default: CAN_IF_OUT_DEFAULT")
parser.add_argument("ifs_in", type=str, nargs="*", default=CAN_IFS_IN_DEFAULT,
                    help=f"List of CAN interfaces to read from BMSes. Default: CAN_IFS_IN_DEFAULT")

cmdline = parser.parse_args()

if cmdline.verbose:
    logging.basicConfig(level=logging.DEBUG)

t_main: threading.Thread = None
thread_stop = threading.Event()

async def main_task() -> None:
    async with AsyncExitStack() as stack:
        bmses_in = [BMS_In(can_if, "bms_in") for can_if in cmdline.ifs_in]
        for bms in bmses_in:
            await stack.enter_async_context(bms)
        bms_out = BMS_Out(cmdline.if_out, "bms_out", sync_interval=cmdline.sync_interval)
        await stack.enter_async_context(bms_out)
        if not cmdline.no_push_mqtt:
            mqtt_out = MQTTBroadcaster(
                cmdline.broker, cmdline.port, cmdline.topic, cmdline.mqtt_interval,
            )  
            await stack.enter_async_context(mqtt_out)
        while not thread_stop.isSet():
            state_in_1 = await bmses_in[0].get_state()
            logger.debug(state_in_1)
            state_out = state_in_1
            await bms_out.set_state(state_out)
            if not cmdline.no_push_mqtt:
                await mqtt_out.set_state(state_out)


def run_app(*args: str) -> None:
    global cmdline
    if args:
        cmdline = parser.parse_args(args)
    logger.info(f"Running with options: {str(cmdline)[10:-1]}")
    try:
        asyncio.run(main_task())
    except KeyboardInterrupt:
        pass

def run_app_bg() -> None:
    """Run app in background thread (for debugging in ipython etc)"""
    global t_main
    thread_stop.clear()
    t_main = threading.Thread(target=run_app)
    t_main.start()

def stop_app() -> None:
    thread_stop.set()


if __name__ == "__main__":
    run_app()
