"""BMS gateway configuration

Do not edit the configuration values herein, they will be
overwritten from config file, see file names below!

2025-04-24 Ulrich Lukas
"""
import sys
import logging
import shutil
from importlib.resources import files
from pathlib import Path
from dataclasses import dataclass
from dataclass_binder import Binder

logger = logging.getLogger(__name__)

CONFIG_FILE_NAME: str = "bms_config.toml"
DEFAULT_CONFIG_FILE_NAME: str = "bms_config_default.toml"

@dataclass
class Battery_Config():
    """Settings for total values of all parallel connected batteries"""
    I_LIM_CHARGE: float = 300.0
    # Maximum discharging current limit in Amperes as communicated to inverter
    I_LIM_DISCHARGE: float = 300.0
    # Apply this scaling factor to the reported current.
    # This can be used for total influx or outgoing power control.
    I_TOT_SCALING: float = 1.0
    # Apply this static offset in Amperes to the reported current
    I_TOT_OFFSET: float = 0.0

@dataclass
class BMS_Out_Config():
    """Settings for emulated (output) BMS"""
    # Dedicated CAN interface for this BMS (connected to a single battery inverter)
    CAN_IF: str = "vcan0"
    # Text description for the emulated BMS
    DESCRIPTION: str = "Virtual BMS"
    # Maximum charging current limit in Amperes as communicated to inverter
    I_LIM_CHARGE: float = 300.0
    # Maximum discharging current limit in Amperes as communicated to inverter
    I_LIM_DISCHARGE: float = 300.0
    # Apply this static scaling factor to the reported current.
    # This should be the individual inverter power divided by the total
    # power of all paralell connected inverters
    I_SCALING: float = 1.0
    # Apply this static offset in Amperes to the reported current
    I_OFFSET: float = 0.0
    # Send CAN sync-telegram (CAN-ID 0x305, data 8x 0x00) periodically to inverter
    # if this is set to true
    SEND_SYNC_ACTIVATED: bool = False
    # Cycle time in seconds for CAN sync-telegram
    SYNC_INTERVAL: float = 5.0

@dataclass
class BMS_In_Config():
    """Settings for input BMS"""
    # Dedicated CAN interface for this BMS
    CAN_IF: str = "vcan1"
    # Text description for each of the BMS channels
    DESCRIPTION: str = "Battery Rack 1 Left", "Battery Rack 2 Right"
    # Battery pack capacity in ampere-hours (ah) for individual input BMSes.
    # This is used as a weighting-factor for calculation of SOC, SOH etc.
    CAPACITY_AH: float = 1400
    # If set to a value in seconds, poll the BMS by
    # periodically sending an inverter sync telegram
    POLL_INTERVAL: float = None

@dataclass
class MQTTConfig():
    """Settings for MQTT broadcaster"""
    ACTIVATED: bool = True
    TOPIC: str = "tele/bms/state"
    BROKER: str = "localhost"
    PORT: int = 1883
    # MQTT broadcast (transmit) interval in seconds
    INTERVAL: float = 10.0

@dataclass
class AppConfig():
    """All application settings"""
    GATEWAY_ACTIVATED: bool
    mqtt: MQTTConfig
    battery: Battery_Config
    bmses_in: list[BMS_In_Config]
    bmses_out: list[BMS_Out_Config]


def init_or_read_from_config_file(init=False) -> AppConfig:
    conf_file = Path.home().joinpath(f".{__package__}").joinpath(CONFIG_FILE_NAME)
    default_conf_file = files(__package__).joinpath(DEFAULT_CONFIG_FILE_NAME)
    if init or not conf_file.is_file():
        conf_file.parent.mkdir(exist_ok=True)
        shutil.copy(default_conf_file, conf_file)
        logger.log(
            level=logging.INFO if init else logging.ERROR,
            msg=f"Configuration initialized using file: {conf_file}\n"
            "==> Please edit this file NOW to configure CAN hardware "
            "etc. and run the application again!",
        )
        sys.exit(0 if init else 1)
    try:
        conf = Binder(AppConfig).parse_toml(conf_file)
        if not conf.GATEWAY_ACTIVATED:
            logger.error(f"BMS Gateway not configured! "
                         f"Edit config file first: {conf_file}")
            sys.exit(1)
    except Exception as e:
        logger.exception(f"Error reading configuration file {conf_file}")
        sys.exit(1)
    return conf