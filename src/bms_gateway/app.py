#!/usr/bin/env python3
"""Multiplexer Gateway for LV BMS using Pylontech Protocol."""
import argparse
import asyncio
import logging
from contextlib import AsyncExitStack

from .bms_state import BmsState
from .lv_bms import BMS_In, BMS_Out
from .mqtt_broadcast import MQTTBroadcaster

logger = logging.getLogger(__name__)

CAN_INTERFACE_DEFAULT: str = "vcan0"

MQTT_TOPIC_DEFAULT: str = "tele/bms"
MQTT_BROKER_DEFAULT: str = "localhost"
MQTT_PORT: int = 1883
MQTT_TX_INTERVAL: float = 10.0

CAN_IF_OUT: str = "vcan0"
CAN_IF_IN_1: str = "vcan1"
CAN_IF_IN_2: str = "vcan2"

parser = argparse.ArgumentParser(prog=__package__, description=__doc__)
parser.add_argument("ifname", type=str, nargs="?", default=CAN_INTERFACE_DEFAULT,
                    help="CAN interface to use. Default: vcan0")
parser.add_argument("--push", action="store_true",
                    help="Push incoming BMS telegrams to MQTT")
parser.add_argument("-t", "--topic", type=str, default=MQTT_TOPIC_DEFAULT,
                    help="MQTT topic to push to. Default: tele/bms")
parser.add_argument("-b", "--broker", type=str, default=MQTT_BROKER_DEFAULT,
                    help="MQTT host (broker) to push to. Default: localhost")
parser.add_argument("-s", "--silent", action="store_true",
                    help="Suppress screen text output")
parser.add_argument("-ss", "--super-silent", action="store_true",
                    help="Suppress text output. Also suppress warnings")

cmdline = parser.parse_args()

async def main_task():
    async with AsyncExitStack() as stack:
        bms_in_1 = await stack.enter_async_context(BMS_In(
            CAN_IF_IN_1, "bms_in"
        ))
        bms_out = await stack.enter_async_context(BMS_Out(
            CAN_IF_OUT, "bms_out"
        ))
        mqtt_out = await stack.enter_async_context(MQTTBroadcaster(
            cmdline.broker, MQTT_PORT, cmdline.topic, MQTT_TX_INTERVAL
        ))
        while True:
            state_in_1 = await bms_in_1.get_state()
            print(state_in_1)
            state_out = state_in_1
            await bms_out.set_state(state_out)
            await mqtt_out.set_state(state_out)


def run_app(*args: list[str]):
    global cmdline
    if args:
        cmdline = parser.parse_args(args)
    logger.info(f"Running with options: {str(cmdline)[10:-1]}")
    try:
        asyncio.run(main_task())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run_app()
