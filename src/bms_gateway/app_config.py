"""BMS gateway configuration.

Do not edit the configuration values herein, they will be
overwritten from config file, see file names below!

2025-04-24 Ulrich Lukas
"""

import logging
import shutil
import sys
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from dataclass_binder import Binder

logger = logging.getLogger(__name__)

CONFIG_FILE_NAME: str = "bms_config.toml"
DEFAULT_CONFIG_FILE_NAME: str = "bms_config_default.toml"


@dataclass
class MQTTConfig:
    """Settings for MQTT broadcaster.

    System state (state of all parallel connected battery BMS) is encoded
    in JSON format and pushed periodically on the specified topic.
    """

    # Setting this to false disables transmitting of MQTT telegrams
    ACTIVATED: bool = True
    TOPIC: str = "tele/bms/state"
    BROKER: str = "localhost"
    PORT: int = 1883
    # MQTT minimum broadcast (transmit) time interval in seconds.
    # If one or more input BMSes stop submitting state updates,
    # MQTT broadcast is also stopped.
    INTERVAL: float = 10.0


@dataclass
class BatteryConfig:
    """Settings for total values of all parallel connected batteries."""

    # Maximum charging current limit in Amperes for total battery stack
    I_LIM_CHARGE: float = 700.0
    # Maximum discharging current limit in Amperes for total battery stack
    I_LIM_DISCHARGE: float = 700.0
    # Apply this scaling factor to the reported total battery stack current.
    # This can be used for total influx or outgoing power control.
    I_TOT_SCALING: float = 1.0
    # Apply this static offset in Amperes to the total battery stack current
    I_TOT_OFFSET: float = 0.0


@dataclass
class BMSOutConfig:
    """Settings for emulated (output) BMS."""

    # Dedicated CAN interface for this BMS (connected to a single battery inverter)
    CAN_IF: str = "vcan0"
    # Text description for the emulated BMS
    DESCRIPTION: str = "Virtual BMS 1"
    # Maximum charging current limit in Amperes as communicated to inverter
    I_LIM_CHARGE: float = 300.0
    # Maximum discharging current limit in Amperes as communicated to inverter
    I_LIM_DISCHARGE: float = 300.0
    # Apply this scaling factor to the reported current.
    # This should be the individual inverter design current limit divided by the
    # sum of all design current limits of all paralell connected inverters.
    I_SCALING: float = 1.0
    # Apply this static offset in Amperes to the reported current
    I_OFFSET: float = 0.0
    # Normal mode of operation is we push BMS state update to the connected
    # inverters as soon as it is available (from all connected BMSes),
    # optionally introducing a delay if PUSH_MIN_DELAY is set > 0.0
    #
    # Limit rate of outgoing messages to inverter using this cycle time in seconds
    PUSH_MIN_DELAY: float = 0.0
    # If SEND_SYNC_ACTIVATED is set, instead of push mode, we wait for
    # an inverter sync/acqknowledge-telegram (CAN-ID 0x305, data 8x 0x00)
    # before sending the state update.
    #
    # This will also enable a periodic task sending an outgoing sync telegram
    # periodically to initially and repeatedly trigger the cycle.
    SEND_SYNC_ACTIVATED: bool = False
    # Cycle time in seconds for transmitting the CAN inverter sync-telegram
    SYNC_INTERVAL: float = 5.0


@dataclass
class BMSInConfig:
    """Settings for input BMS."""

    # Dedicated CAN interface for this BMS (connected to one battery module)
    CAN_IF: str = "vcan1"
    # Text description for battery module BMS
    DESCRIPTION: str = "Battery Rack 1 Left"
    # Battery pack capacity in ampere-hours (Ah) for this module.
    # This is used as a weighting-factor for calculation of SOC, SOH etc.
    CAPACITY_AH: float = 1400
    # If set, using this time interval in seconds, poll the BMS by
    # periodically sending an inverter sync/ackknowledge telegram.
    POLL_INTERVAL: float = None


@dataclass
class AppConfig:
    """All application settings."""

    GATEWAY_ACTIVATED: bool
    mqtt: MQTTConfig
    battery: BatteryConfig
    bmses_in: list[BMSInConfig]
    bmses_out: list[BMSOutConfig]


def init_or_read_from_config_file(*, init: bool = False) -> AppConfig:
    """Read or initialize configuration file and return config data object."""
    conf_file = Path.home().joinpath(f".{__package__}").joinpath(CONFIG_FILE_NAME)
    default_conf_file = files(__package__).joinpath(DEFAULT_CONFIG_FILE_NAME)
    if init or not conf_file.is_file():
        conf_file.parent.mkdir(exist_ok=True)
        shutil.copy(default_conf_file, conf_file)
        msg = "Configuration initialized using file: %s\n==> Please check or edit this file NOW!"
        logger.log(logging.INFO if init else logging.ERROR, msg, conf_file)
        sys.exit(0 if init else 1)
    try:
        conf = Binder(AppConfig).parse_toml(conf_file)
        if not conf.GATEWAY_ACTIVATED:
            msg = "BMS Gateway not configured!  Edit config file first: %s"
            logger.error(msg, conf_file)
            sys.exit(1)
    except Exception:
        msg = "Error reading configuration file %s"
        logger.exception(msg, conf_file)
        sys.exit(1)
    return conf
