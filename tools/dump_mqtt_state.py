#!/usr/bin/env python3
"""Subscribe to MQTT state broadcasting topic and dump on screen"""
import asyncio
from typing import cast
import aiomqtt
import json
from pprint import pformat

from bms_gateway import app_config
from bms_gateway.bms_state import BMSState, Errors, Warnings
from bms_gateway.include.text_screen import TextScreen

# App configuration read from file: "~/bms_gateway/bms_config.toml"
# Default configuration: See source tree file "bms_config_default.toml"
conf = app_config.init_or_read_from_config_file()

# Double-buffered text output
screen = TextScreen()

async def print_msg(msg: aiomqtt.Message) -> None:
    msg_dict = json.loads(cast(bytes, msg.payload))
    state = BMSState(**msg_dict)
    errors = Errors().from_flags(state.error_flags_1, state.error_flags_2)
    warnings = Warnings().from_flags(state.warning_flags_1, state.warning_flags_2)
    state_str = (f"\x1b[34m{pformat(state)}\n"
                 f"\x1b[31m{pformat(errors)}\n"
                 f"\x1b[33m{pformat(warnings)}\n\x1b[0m")
    screen.put(f"{state_str}\n *******  Got state update!  *******\n")
    screen.refresh()
    await asyncio.sleep(2.0)
    screen.put(f"{state_str}\n\n")
    screen.refresh()


async def main_task() -> None:
    async with aiomqtt.Client(conf.mqtt.BROKER, conf.mqtt.PORT) as client:
        await client.subscribe(conf.mqtt.TOPIC)
        print(f"\nSubscribed to {conf.mqtt.TOPIC} on {conf.mqtt.BROKER}..\n"
              "Press CTRL-C to exit!\n")
        async for msg in client.messages:
            await print_msg(msg)


def run_app() -> None:
    try:
        asyncio.run(main_task())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    run_app()