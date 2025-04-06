import time
import logging
import asyncio
import aiomqtt
import json

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
        self._event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        self._data_valid = asyncio.Condition()

    async def __aenter__(self):
        self._task_publish_mqtt = self._event_loop.create_task(self._fn_task_publish_mqtt())

    async def __aexit__(self, _exc_type, _exc_value, _traceback):
        self._task_publish_mqtt.cancel()

    async def set_state(self, state: BmsState):
        async with self._data_valid:
            self._state = state
            self._data_valid.notify_all()

    # Periodically sends BMS data broadcast on the specified bus
    async def _fn_task_publish_mqtt(self):
        async with aiomqtt.Client(self.broker, self.port) as client:
            next_call = time.time()
            while True:
                async with self._data_valid:
                    await self._data_valid.wait()
                    msg_json = json.dumps(self._state)
                await client.publish(self.topic, msg_json)
                next_call += self.tx_interval
                await asyncio.sleep(next_call - time.time())
