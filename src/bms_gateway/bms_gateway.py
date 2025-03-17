#!/usr/bin/env python3
"""Multiplexer Gateway for LV BMS using Pylontech Protocol."""
import time
import asyncio
import logging

from bms_state import BmsState
from lv_bms import BMS_In, BMS_Out

logger = logging.getLogger(__name__)

CAN_CHANNEL = "vcan0"

async def print_state():
    async with BMS_In(CAN_CHANNEL, "bms_test") as bms:
        while True:
            state = await bms.get_state()
            print(state)


def run_app():
    try:
        asyncio.run(print_state())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    run_app()
