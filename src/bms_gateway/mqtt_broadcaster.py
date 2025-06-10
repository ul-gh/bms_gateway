"""MQTT telemetry broadcaster for bms_gateway."""

import asyncio
import dataclasses
import json
import logging
from typing import Self

import aiomqtt

from .app_config import MQTTConfig
from .bms_state import BMSState

logger = logging.getLogger(__name__)

# Does this test the connection?
MQTT_TIMEOUT: float = 5.0


class MQTTBroadcaster:
    """MQTT telemetry broadcaster for bms_gateway."""

    def __init__(self, config: MQTTConfig) -> None:
        """Init MQTTBroadcaster with config."""
        self.config = config
        self._state = BMSState()
        self._task_publish_mqtt: asyncio.Task = None
        self._data_valid = asyncio.Condition()
        self._client = aiomqtt.Client(
            config.BROKER,
            config.PORT,
            clean_session=True,
            timeout=MQTT_TIMEOUT,
        )

    async def __aenter__(self) -> Self:
        """Async context manager entry method."""
        self._task_publish_mqtt = asyncio.create_task(
            self._fn_task_publish_mqtt(),
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        """Async context manager exit method."""
        self._task_publish_mqtt.cancel()

    async def set_state(self, state: BMSState) -> None:
        """Set state to be broadcasted over MQTT."""
        async with self._data_valid:
            self._state = state
            self._data_valid.notify_all()

    # Periodically sends BMS data broadcast on the specified bus
    async def _fn_task_publish_mqtt(self) -> None:
        conf = self.config
        loop = asyncio.get_event_loop()
        async with self._client as client:
            next_call = loop.time()
            while True:
                async with self._data_valid:
                    await self._data_valid.wait()
                    msg_json = json.dumps(dataclasses.asdict(self._state))
                await client.publish(conf.TOPIC, msg_json)
                next_call += conf.INTERVAL
                await asyncio.sleep(next_call - loop.time())
