"""BMS gateway configuration"""
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
class BMS_Out_Config():
    """Settings for emulated (output) BMS"""
    # Dedicated CAN interface for this BMS
    CAN_IF: str = "vcan0"
    # Text description for the emulated BMS
    DESCRIPTION = "Virtual BMS"
    # Maximum charging current limit in Amperes as communicated to inverter
    I_LIM_CHARGE: float = 300.0
    # Maximum discharging current limit in Amperes as communicated to inverter
    I_LIM_DISCHARGE: float = 300.0
    # Apply this static scaling factor to the reported current
    I_TOT_SCALING: float = 1.0
    # Apply this static offset in Amperes to the reported current
    I_TOT_OFFSET: float = 0.0
    # Send CAN sync-telegram (CAN-ID 0x305, data 8x 0x00) periodically to inverter
    # if this is set to true
    SEND_SYNC: bool = False
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
    INTERVAL: float = 10.0

@dataclass
class AppConfig():
    """All application settings"""
    mqtt: MQTTConfig
    bms_out: BMS_Out_Config
    bmses_in: list[BMS_In_Config]


def init_or_read_from_config_file() -> AppConfig:
    conf_file = Path.home().joinpath(f".{__package__}").joinpath(CONFIG_FILE_NAME)
    default_conf_file = files(__package__).joinpath(DEFAULT_CONFIG_FILE_NAME)
    if not conf_file.is_file():
        conf_file.parent.mkdir(exist_ok=True)
        shutil.copy(default_conf_file, conf_file)
    try:
        conf = Binder(AppConfig).parse_toml(conf_file)
    except Exception as e:
        logger.exception(f"Error reading configuration file {conf_file}")
        sys.exit(1)
    return conf