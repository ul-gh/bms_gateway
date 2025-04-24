import time
import asyncio
import logging
import can
from typing import Self

from .app_config import BMS_In_Config, BMS_Out_Config
from .bms_state import BMSState

logger = logging.getLogger(__name__)

# CAN bitrate for battery-side BMSs
BMS_IN_BITRATE: int = 500000
# Number of CAN frames belonging to one reply data telegram from the BMS
N_BMS_REPLY_FRAMES: int = 6
# CAN ID which marks the start of the data telegram sent from the BMS
ID_BMS_TELEGRAM_START: int = 0x359
# CAN ID which is sent by the inverter to poll the BMS (using 8x 0x00 data)
ID_INVERTER_REQUEST: int = 0x305


class BMS_In():
    def __init__(self, config: BMS_In_Config):
        self.config = config
        self.bus: can.Bus = None
        self._reader: can.AsyncBufferedReader = None
        self._state = BMSState(capacity_ah=config.CAPACITY_AH)
        self._raw_frames: dict = {}
        self._framecounter: int = 0
        self._data_ready = asyncio.Condition()
        self._can_notifier: can.Notifier = None
        self._poll_task: can.CyclicSendTaskABC = None
        self._task_main: asyncio.Task = None

    async def __aenter__(self) -> Self:
        conf = self.config
        loop = asyncio.get_event_loop()
        self.bus = can.Bus(conf.CAN_IF, "socketcan", bitrate=BMS_IN_BITRATE)
        self._reader = can.AsyncBufferedReader()
        self._can_notifier = can.Notifier(self.bus, [self._reader], loop=loop)
        if conf.POLL_INTERVAL is not None:
            sync_msg = can.Message(arbitration_id=ID_INVERTER_REQUEST, data=[0] * 8)
            self._poll_task = self.bus.send_periodic(sync_msg, conf.POLL_INTERVAL)
        self._task_main = loop.create_task(self._fn_task_main())
        return self

    async def __aexit__(self, _exc_type, _exc_value, _traceback) -> None:
        logger.debug("__aexit__ called")
        if self._poll_task is not None:
            self._poll_task.stop()
        self._task_main.cancel()
        self._can_notifier.stop()
        self.bus.shutdown()

    async def get_state(self) -> BMSState:
        logger.debug("BMS_In:get_state() called")
        async with self._data_ready:
            await self._data_ready.wait()
            return self._state

    async def _fn_task_main(self) -> None:
        while True:
            msg = await self._reader.get_message()
            # Fill in BMS reply frames into dictionary
            self._raw_frames[msg.arbitration_id] = msg.data
            # Inverter request or acknowledge is inverleaved with BMS reply.
            # The inverter frame contains no data and only timestamp is logged
            if msg.arbitration_id == ID_INVERTER_REQUEST:
                self._state.timestamp_last_inverter_request = time.time()
            elif msg.arbitration_id == ID_BMS_TELEGRAM_START:
                if self._framecounter >= N_BMS_REPLY_FRAMES:
                    try:
                        self._decode_frames_update_state(self._raw_frames)
                        async with self._data_ready:
                            self._data_ready.notify_all()
                    except ValueError as e:
                        logger.warning(e.args[0])
                self._framecounter = 1
            else:
                self._framecounter += 1

    def _decode_frames_update_state(self, frames: dict[int, can.Message]) -> None:
        state = self._state
        try:
            # CAN ID 0x351
            msg = frames[0x351]
            state.v_charge_cmd = 0.1 * int.from_bytes(msg[0:2], "little")
            state.i_lim_charge = 0.1 * int.from_bytes(msg[2:4], "little", signed=True)
            state.i_lim_discharge = 0.1 * int.from_bytes(msg[4:6], "little", signed=True)
            # CAN ID 0x355
            msg = frames[0x355]
            state.soc = int.from_bytes(msg[0:2], "little")
            state.soh = int.from_bytes(msg[2:4], "little")
            # CAN ID 0x356
            msg = frames[0x356]
            state.v_avg = 0.01 * int.from_bytes(msg[0:2], "little", signed=True)
            state.i_total = 0.1 * int.from_bytes(msg[2:4], "little", signed=True)
            state.t_avg = 0.1 * int.from_bytes(msg[4:6], "little", signed=True)
            # CAN ID 0x359
            msg = frames[0x359]
            state.error_flags_1 = msg[0]
            state.error_flags_2 = msg[1]
            state.warning_flags_1 = msg[2]
            state.warning_flags_2 = msg[3]
            state.n_modules = msg[4]
            # CAN ID 0x35C
            msg = frames[0x35C]
            state.charge_enable = bool(msg[0] & 1<<7)
            state.discharge_enable = bool(msg[0] & 1<<6)
            state.force_charge_request = bool(msg[0] & 1<<5)
            state.force_charge_request_2 = bool(msg[0] & 1<<4)
            state.balancing_charge_request = bool(msg[0] & 1<<3)
            # CAN ID 0x35E
            msg = frames[0x35E]
            state.manufacturer = msg.decode().rstrip("\x00")
        # Operator "<=" tests if left set is a subset of the set on the right side
        #if not {0x351, 0x355, 0x356, 0x359, 0x35C, 0x35E} <= frames.keys():
        except KeyError as e:
            txt = f"Incomplete set of data frames received. ID: {hex(e.args[0])}"
            state.n_invalid_data_telegrams += 1
            raise ValueError(txt)
        except (IndexError, ValueError, UnicodeDecodeError) as e:
            txt = f"Invalid data received. Details: {e.args[0]}"
            state.n_invalid_data_telegrams += 1
            raise ValueError(txt)
        state.timestamp_last_bms_update = time.time()


class BMS_Out():
    def __init__(self, config: BMS_Out_Config):
        self.config = config
        self.bus: can.Bus = None
        self._reader: can.AsyncBufferedReader = None
        self._output_msgs: list[can.Message] = self._bms_encode(BMSState())
        # Option A: Send BMS state data cyclically when sync_interval is given
        self._sync_task: can.CyclicSendTaskABC = None
        # Option B: Send BMS state data when a SYNC message is received
        self._task_reply: asyncio.Task = None
        self._data_valid = asyncio.Condition()
        self._can_notifier: can.Notifier = None

    async def __aenter__(self) -> Self:
        conf = self.config
        loop = asyncio.get_event_loop()
        self.bus = can.Bus(conf.CAN_IF, "socketcan", bitrate=BMS_IN_BITRATE)
        self._reader = can.AsyncBufferedReader()
        self._can_notifier = can.Notifier(self.bus, [self._reader], loop=loop)
        if conf.SEND_SYNC_ACTIVATED:
            sync_msg = can.Message(
                arbitration_id=ID_INVERTER_REQUEST,
                is_extended_id=False,
                data=b"\x00" * 8
            )
            self._sync_task = self.bus.send_periodic(sync_msg, conf.SYNC_INTERVAL)
            assert isinstance(self._sync_task, can.CyclicSendTaskABC)
        self._task_reply = loop.create_task(self._fn_task_reply())
        return self

    async def __aexit__(self, _exc_type, _exc_value, _traceback) -> None:
        if self._sync_task is not None:
            self._sync_task.stop()
        else:
            self._task_reply.cancel()
        self._can_notifier.stop()
        self.bus.shutdown()

    async def set_state(self, state: BMSState) -> None:
        logger.debug("BMS_Out:set_state() called")
        async with self._data_valid:
            self._output_msgs.clear()
            self._output_msgs.extend(self._bms_encode(state))
            self._data_valid.notify_all()

    async def _fn_task_reply(self) -> None:
        while True:
            # Read incoming CAN msgs until a SYNC message is received
            while True:
                msg = await self._reader.get_message()
                if msg.arbitration_id == ID_INVERTER_REQUEST:
                    break
            # SYNC message was received, reply by sending state to inverter
            # once _data_valid is notified by set_state()
            async with self._data_valid:
                await self._data_valid.wait()
                for msg in self._output_msgs:
                    self.bus.send(msg)

    def _bms_encode(self, state: BMSState) -> list[can.Message]:
        msg_351 = (
            int(10 * state.v_charge_cmd).to_bytes(2, "little")
            + int(10 * state.i_lim_charge).to_bytes(2, "little", signed=True)
            + int(10 * state.i_lim_discharge).to_bytes(2, "little", signed=True)
        )
        msg_355 = (
            int(state.soc).to_bytes(2, "little")
            + int(state.soh).to_bytes(2, "little")
        )
        msg_356 = (
            int(100 * state.v_avg).to_bytes(2, "little", signed=True)
            + int(10 * state.i_total).to_bytes(2, "little", signed=True)
            + int(10 * state.t_avg).to_bytes(2, "little", signed=True)
        )
        msg_359 = bytes((
            state.error_flags_1,
            state.error_flags_2,
            state.warning_flags_1,
            state.warning_flags_2,
            state.n_modules,
            # Following two bytes are fixed values according to Pylontech spec
            0x50,
            0x4E,
        ))
        msg_35C = (
            state.charge_enable << 7
            | state.discharge_enable << 6
            | state.force_charge_request << 5
            | state.force_charge_request_2 << 4
            | state.balancing_charge_request << 3
        ).to_bytes()
        msg_35E = state.manufacturer.encode("ascii") + b"\x00"
        return [
            can.Message(arbitration_id=0x351, is_extended_id=False, data=msg_351),
            can.Message(arbitration_id=0x355, is_extended_id=False, data=msg_355),
            can.Message(arbitration_id=0x356, is_extended_id=False, data=msg_356),
            can.Message(arbitration_id=0x359, is_extended_id=False, data=msg_359),
            can.Message(arbitration_id=0x35C, is_extended_id=False, data=msg_35C),
            can.Message(arbitration_id=0x35E, is_extended_id=False, data=msg_35E),
        ]