"""MQTT telemetry broadcaster for bms_gateway."""

import asyncio
import dataclasses
import json
import logging
from types import TracebackType
from typing import Self, final

import aiomqtt

from .app_config import MQTTConfig
from .bms_state import BMSState
from .utils import async_fixed_time_intervals

logger = logging.getLogger(__name__)

# Does this test the connection?
MQTT_TIMEOUT: float = 5.0

@final
class MQTTBroadcaster:
    """MQTT telemetry broadcaster for bms_gateway."""

    def __init__(self, config: MQTTConfig) -> None:
        """Init MQTTBroadcaster with config."""
        self.config = config
        self._state = BMSState()
        self._task_publish_mqtt: asyncio.Task[None] | None = None
        self._data_lock = asyncio.Lock()
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

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit method."""
        if self._task_publish_mqtt is not None:
            _ = self._task_publish_mqtt.cancel()

    async def set_state(self, state: BMSState) -> None:
        """Set state to be broadcasted over MQTT."""
        async with self._data_lock:
            self._state = state

    # Periodically sends BMS data broadcast on the specified bus
    async def _fn_task_publish_mqtt(self) -> None:
        async with self._client as client:
            async for _ in async_fixed_time_intervals(self.config.INTERVAL):
                msg_json = json.dumps(dataclasses.asdict(self._state))
                await client.publish(self.config.TOPIC, msg_json)
