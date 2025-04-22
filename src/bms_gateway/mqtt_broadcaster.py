import logging
import asyncio
import aiomqtt
import json
import dataclasses
from typing import Self

from .bms_state import BmsState

logger = logging.getLogger(__name__)


class MQTTBroadcaster():
    def __init__(self,
                 broker: str = "localhost",
                 port: int = 1883,
                 topic: str = "tele/bms/state",
                 tx_interval: float = 10.0,
                 ):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.tx_interval = tx_interval
        self._state = BmsState()
        self._task_publish_mqtt: asyncio.Task = None
        self._data_valid = asyncio.Condition()

    async def __aenter__(self) -> Self:
        self._task_publish_mqtt = asyncio.create_task(
            self._fn_task_publish_mqtt()
        )
        return self

    async def __aexit__(self, _exc_type, _exc_value, _traceback) -> None:
        self._task_publish_mqtt.cancel()

    async def set_state(self, state: BmsState) -> None:
        async with self._data_valid:
            self._state = state
            self._data_valid.notify_all()

    # Periodically sends BMS data broadcast on the specified bus
    async def _fn_task_publish_mqtt(self) -> None:
        loop = asyncio.get_event_loop()
        async with aiomqtt.Client(self.broker, self.port) as client:
            next_call = loop.time()
            while True:
                async with self._data_valid:
                    await self._data_valid.wait()
                    msg_json = json.dumps(dataclasses.asdict(self._state))
                await client.publish(self.topic, msg_json)
                next_call += self.tx_interval
                await asyncio.sleep(next_call - loop.time())
