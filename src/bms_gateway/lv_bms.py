"""Async implementation of state and API for LV BMS using Pylontech protocol."""

import asyncio
import logging
import time
from types import TracebackType
from typing import Self, final

import can

from bms_gateway.app_config import BMSInConfig, BMSOutConfig
from bms_gateway.bms_state import BMSState
from bms_gateway.utils import SingleItemQueue

logger = logging.getLogger(__name__)

# CAN bitrate for battery-side BMSs
BMS_IN_BITRATE: int = 500000
# Number of CAN frames belonging to the periodic state updates from the BMS.
N_BMS_REPLY_FRAMES: int = 6
# CAN ID marking the last of the state reporting data frames sent from the BMS.
ID_LAST_FRAME: int = 0x35E
# CAN ID which is sent by the inverter to poll the BMS (using 8x 0x00 data).
ID_INVERTER_REQUEST: int = 0x305


@final
class BMSIn:
    """Representation of input-side battery BMS state."""

    def __init__(self, config: BMSInConfig) -> None:
        """Initialize an input (battery-side) BMS representation object."""
        self.config: BMSInConfig = config
        self.bus: can.BusABC | None = None
        # Result of the BMS state is stored in this object.
        # It can be retrieved by calling state.get() or state.get_nopop() methods.
        # The BMS state is updated by the _run_bms_receiver_task() method
        self.state = SingleItemQueue[BMSState]()
        self._reader: can.AsyncBufferedReader | None = None
        self._raw_frames = dict[int, bytearray]()
        self._framecounter: int = 0
        self._timestamp_last_inverter_request: float = float("NaN")
        self._n_invalid_data_telegrams: int = 0
        self._can_notifier: can.Notifier | None = None
        self._poll_task: can.CyclicSendTaskABC | None = None
        self._task_main: asyncio.Task[None] | None = None

    async def __aenter__(self) -> Self:
        """Async context manager entry method."""
        conf = self.config
        loop = asyncio.get_event_loop()
        self.bus = can.Bus(conf.CAN_IF, "socketcan", bitrate=BMS_IN_BITRATE)
        self._reader = can.AsyncBufferedReader()
        self._can_notifier = can.Notifier(self.bus, [self._reader], loop=loop)
        if conf.POLL_INTERVAL is not None:
            sync_msg = can.Message(arbitration_id=ID_INVERTER_REQUEST, data=[0] * 8)
            self._poll_task = self.bus.send_periodic(sync_msg, conf.POLL_INTERVAL)
        self._task_main = loop.create_task(self._run_bms_receiver_task())
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit method."""
        logger.debug("__aexit__ called")
        if self._poll_task is not None:
            self._poll_task.stop()
        if self._task_main is not None:
            _ = self._task_main.cancel()
        if self._can_notifier is not None:
            self._can_notifier.stop()
        if self.bus is not None:
            self.bus.shutdown()

    async def _run_bms_receiver_task(self) -> None:
        while True:
            msg = await self._reader.get_message()  # pyright: ignore[reportOptionalMemberAccess]
            # Fill in BMS reply frames into dictionary
            self._raw_frames[msg.arbitration_id] = msg.data
            # Inverter request or acknowledge is inverleaved with BMS reply.
            # The inverter frame contains no data and only timestamp is logged
            if msg.arbitration_id == ID_INVERTER_REQUEST:
                self._timestamp_last_inverter_request = time.time()
            elif msg.arbitration_id == ID_LAST_FRAME:
                if self._framecounter >= N_BMS_REPLY_FRAMES:
                    try:
                        new_state = self._decode_frames()
                        self.state.put_nowait(new_state)
                        self._raw_frames.clear()
                    except ValueError as e:
                        logger.warning(e.args[0])  # pyright: ignore[reportAny]
                self._framecounter = 1
            else:
                self._framecounter += 1

    def _decode_frames(self) -> BMSState:
        try:
            # Assign each frame to a variable for easier access
            msg_351 = self._raw_frames[0x351]
            msg_355 = self._raw_frames[0x355]
            msg_356 = self._raw_frames[0x356]
            msg_359 = self._raw_frames[0x359]
            msg_35c = self._raw_frames[0x35C]
            msg_35e = self._raw_frames[0x35E]
            # Construct a BMSState object from the received CAN frames
            state = BMSState(
                # CAN ID 0x351
                v_charge_cmd=0.1 * int.from_bytes(msg_351[0:2], "little"),
                i_lim_charge=0.1 * int.from_bytes(msg_351[2:4], "little", signed=True),
                i_lim_discharge=0.1 * int.from_bytes(msg_351[4:6], "little", signed=True),
                # CAN ID 0x355
                soc=float(int.from_bytes(msg_355[0:2], "little")),
                soh=float(int.from_bytes(msg_355[2:4], "little")),
                # CAN ID 0x356
                v_total=0.01 * int.from_bytes(msg_356[0:2], "little", signed=True),
                i_total=0.1 * int.from_bytes(msg_356[2:4], "little", signed=True),
                t_avg=0.1 * int.from_bytes(msg_356[4:6], "little", signed=True),
                # CAN ID 0x359
                error_flags_1=msg_359[0],
                error_flags_2=msg_359[1],
                warning_flags_1=msg_359[2],
                warning_flags_2=msg_359[3],
                n_modules=msg_359[4],
                # CAN ID 0x35C
                charge_enable=bool(msg_35c[0] & 1 << 7),
                discharge_enable=bool(msg_35c[0] & 1 << 6),
                force_charge_request=bool(msg_35c[0] & 1 << 5),
                force_charge_request_2=bool(msg_35c[0] & 1 << 4),
                balancing_charge_request=bool(msg_35c[0] & 1 << 3),
                # CAN ID 0x35E
                manufacturer=msg_35e.decode().rstrip("\x00"),
                # Timestamp in seconds since epoch when the last BMS update was received
                timestamp_last_bms_update=time.time(),
                # Timestamp in seconds since epoch when the last inverter request was received
                timestamp_last_inverter_request=self._timestamp_last_inverter_request,
                # Number of invalid data telegrams received from or by the BMS
                n_invalid_data_telegrams=self._n_invalid_data_telegrams,
            )
        except KeyError as e:
            txt = f"Incomplete set of data frames received. ID: {hex(e.args[0])}"
            self._n_invalid_data_telegrams += 1
            raise ValueError(txt) from e
        except (IndexError, ValueError, UnicodeDecodeError) as e:
            txt = f"Invalid data received. Details: {e.args[0]}"
            self._n_invalid_data_telegrams += 1
            raise ValueError(txt) from e
        return state


@final
class BMSOut:
    """Emulation of one output-side (connected to iverter) BMS."""

    def __init__(self, config: BMSOutConfig) -> None:
        """Initialize an output-side (emulated battery) BMS object."""
        self.config = config
        self.bus: can.BusABC | None = None
        self._reader: can.AsyncBufferedReader | None = None
        self._output_msgs = SingleItemQueue[list[can.Message]]()
        # Option A: Send BMS state data cyclically when sync_interval is given
        self._task_transmit_sync: can.CyclicSendTaskABC | None = None
        # Option B: Send BMS state data when a SYNC message is received
        self._task_transmit_state: asyncio.Task[None]
        self._can_notifier: can.Notifier

    async def __aenter__(self) -> Self:
        """Async context manager entry method."""
        conf = self.config
        loop = asyncio.get_event_loop()
        self.bus = can.Bus(conf.CAN_IF, "socketcan", bitrate=BMS_IN_BITRATE)
        self._reader = can.AsyncBufferedReader()
        self._can_notifier = can.Notifier(self.bus, [self._reader], loop=loop)
        if conf.SEND_SYNC_ACTIVATED:
            sync_msg = can.Message(
                arbitration_id=ID_INVERTER_REQUEST,
                is_extended_id=False,
                data=b"\x00" * 8,
            )
            self._task_transmit_sync = self.bus.send_periodic(sync_msg, conf.SYNC_INTERVAL)
            assert isinstance(self._task_transmit_sync, can.CyclicSendTaskABC)  # noqa: S101
        # Normal mode of operation is we push BMS state update to the connected
        # inverters as soon as it is available (from all connected BMSes),
        # optionally introducing a delay if conf.PUSH_MIN_DELAY is set > 0.0
        #
        # If conf.SEND_SYNC_ACTIVATED is set, instead of push mode, we wait for
        # an inverter sync/acqknowledge-telegram (CAN-ID 0x305, data 8x 0x00)
        # before sending the state update.
        #
        # This will also enable a periodic task sending an outgoing sync
        # telegram periodically to initially and repeatedly trigger the cycle.
        if conf.SEND_SYNC_ACTIVATED:
            self._task_transmit_state = loop.create_task(
                self._run_bms_send_state_after_sync_task(),
                name="send_state_after_sync_task",
            )
        else:
            self._task_transmit_state = loop.create_task(
                self._run_bms_send_state_task(),
                name="send_state_task"
                )
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit method."""
        if self._task_transmit_sync is not None:
            self._task_transmit_sync.stop()
        else:
            _ = self._task_transmit_state.cancel()
        self._can_notifier.stop()
        if self.bus is not None:
            self.bus.shutdown()

    async def set_state(self, state: BMSState) -> None:
        """Set state of emulated output-side (connected to iverter) BMS."""
        logger.debug("BMS_Out:set_state() called")
        self._output_msgs.put_nowait(self._bms_encode(state))

    # Normal mode: Push state updates to the connected inverter as soon as available
    async def _run_bms_send_state_task(self) -> None:
        while True:
            # Limit push data rate if this is > 0.0 seconds
            await asyncio.sleep(self.config.PUSH_MIN_DELAY)
            # Send state to inverter once _data_valid is notified by set_state()
            tx_msgs = await self._output_msgs.get()
            for msg in tx_msgs:
                self.bus.send(msg)  # pyright: ignore[reportOptionalMemberAccess]

    # If config.SEND_SYNC_ACTIVATED is set, instead of push mode, we wait for
    # an inverter sync/acqknowledge-telegram (CAN-ID 0x305, data 8x 0x00)
    # before sending the state update.
    async def _run_bms_send_state_after_sync_task(self) -> None:
        while True:
            # Read incoming CAN msgs until a SYNC message is received
            while True:
                msg = await self._reader.get_message()  # pyright: ignore[reportOptionalMemberAccess]
                if msg.arbitration_id == ID_INVERTER_REQUEST:
                    break
            # SYNC message was received, reply by sending state to inverter
            tx_msgs = await self._output_msgs.get()
            for msg in tx_msgs:
                self.bus.send(msg)  # pyright: ignore[reportOptionalMemberAccess]

    def _bms_encode(self, state: BMSState) -> list[can.Message]:
        conf = self.config
        # Apply inverter current setpoint limits in addition to battery limits
        i_lim_charge = min(state.i_lim_charge, conf.I_LIM_CHARGE)
        i_lim_discharge = min(state.i_lim_discharge, conf.I_LIM_DISCHARGE)
        # Apply inverter current scaling factor and offset for this inverter
        i_total = state.i_total * conf.I_SCALING + conf.I_OFFSET
        # Generate outgoing CAN messages
        msg_351 = (
            int(10 * state.v_charge_cmd).to_bytes(2, "little")
            + int(10 * i_lim_charge).to_bytes(2, "little", signed=True)
            + int(10 * i_lim_discharge).to_bytes(2, "little", signed=True)
        )
        msg_355 = int(state.soc).to_bytes(2, "little") + int(state.soh).to_bytes(2, "little")
        msg_356 = (
            int(100 * state.v_total).to_bytes(2, "little", signed=True)
            + int(10 * i_total).to_bytes(2, "little", signed=True)
            + int(10 * state.t_avg).to_bytes(2, "little", signed=True)
        )
        msg_359 = bytes(
            (
                state.error_flags_1,
                state.error_flags_2,
                state.warning_flags_1,
                state.warning_flags_2,
                state.n_modules,
                # Following two bytes are fixed values according to Pylontech spec
                0x50,
                0x4E,
            ),
        )
        msg_35c = (
            state.charge_enable << 7
            | state.discharge_enable << 6
            | state.force_charge_request << 5
            | state.force_charge_request_2 << 4
            | state.balancing_charge_request << 3
        ).to_bytes()
        msg_35e = state.manufacturer.encode("ascii") + b"\x00"
        return [
            can.Message(arbitration_id=0x351, is_extended_id=False, data=msg_351),
            can.Message(arbitration_id=0x355, is_extended_id=False, data=msg_355),
            can.Message(arbitration_id=0x356, is_extended_id=False, data=msg_356),
            can.Message(arbitration_id=0x359, is_extended_id=False, data=msg_359),
            can.Message(arbitration_id=0x35C, is_extended_id=False, data=msg_35c),
            can.Message(arbitration_id=ID_LAST_FRAME, is_extended_id=False, data=msg_35e),
        ]
