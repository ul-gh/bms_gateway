import time
import threading
import logging
import paho.mqtt.client as mqtt
from bms_state import BmsState

logger = logging.getLogger(__name__)


class MQTTBroadcast():
    def __init__(self,
                 broker: str = "localhost",
                 port: int = 1883,
                 topic: str = "tele/bms/state",
                 tx_interval: float = 10,
                 ):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.tx_interval = tx_interval
        self.mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self._thread_stop = threading.Event()
        self._thread_obj: threading.Thread = None

    def start(self):
        """Start operation."""
        self.mqttc.connect(self.broker, self.port, 60)
        # This starts a background thread
        self.mqttc.loop_start()
        if self._thread_obj is not None:
            logger.warning("Thread is alrady running!")
            return
        self._thread_stop.clear()
        self._thread_obj = threading.Thread(
            name=f"MQTT_{self.topic}",
            target=self._fn_thread_send_bms_broadcast,
            args=(self.tx_interval, ),
        )
        self._thread_obj.start()

    def stop(self):
        """Stop the background thread and block until done."""
        self._thread_stop.set()
        self._thread_obj.join()
        self._thread_obj = None
        self.mqttc.loop_stop()

    # Periodically sends BMS data broadcast on the specified bus
    def _fn_thread_send_bms_broadcast(self, interval: float):
        next_call = time.time()
        while not self._thread_stop.is_set():
            self.mqttc.publish(self.topic, "FOO")
            next_call += interval
            time.sleep(next_call - time.time())
