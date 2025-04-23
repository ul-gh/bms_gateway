"""State, Errors and Warnings definition for LV-BMS.

For BMS using Pylontech Protocol
"""
from typing import Self
from dataclasses import dataclass, replace


@dataclass
class BMSState:
    """BMS state as received on the CAN bus."""
    manufacturer: str = ""
    soc: int = 0
    soh: int = 0
    v_charge_cmd: float = 0.0
    i_lim_charge: float = 0.0
    i_lim_discharge: float = 0.0
    v_avg: float = 0.00
    i_total: float = 0.0
    t_avg: float = 0.0
    error_flags_1: int = 0xFF
    error_flags_2: int = 0xFF
    warning_flags_1: int = 0xFF
    warning_flags_2: int = 0xFF
    n_modules: int = 0
    charge_enable: bool = False
    discharge_enable: bool = False
    force_charge_request: bool = False
    force_charge_request_2: bool = False
    balancing_charge_request: bool = False
    timestamp_last_bms_update: float = 0.0
    timestamp_last_inverter_request: float = 0.0
    n_invalid_data_telegrams: int = 0
    capacity_ah: float = 1.0

    def copy(self) -> Self:
        return replace(self)


@dataclass
class Errors:
    """BMS Error flags."""

    oc_discharge: bool = True
    oc_charge: bool = True
    overvoltage: bool = True
    undervoltage: bool = True
    temp_low: bool = True
    temp_high: bool = True
    system_error: bool = True

    def from_flags(self, flags_low: int, flags_high: int):
        self.oc_discharge = bool(flags_low & 1<<7)
        self.temp_low = bool(flags_low & 1<<4)
        self.temp_high = bool(flags_low & 1<<3)
        self.undervoltage = bool(flags_low & 1<<2)
        self.overvoltage = bool(flags_low & 1<<1)
        self.system_error = bool(flags_high & 1<<3)
        self.oc_charge = bool(flags_high & 1<<0)

    def to_flags(self) -> tuple[int]:
        flags_low = int(self.oc_discharge) * 1<<7
        flags_low |= int(self.temp_low) * 1<<4
        flags_low |= int(self.temp_high) * 1<<3
        flags_low |= int(self.undervoltage) * 1<<2
        flags_low |= int(self.overvoltage) * 1<<1
        flags_high = int(self.system_error) * 1<<3
        flags_high |= int(self.oc_charge) * 1<<0
        return flags_low, flags_high
    
    def copy(self) -> Self:
        return replace(self)


@dataclass
class Warnings:
    """BMS Warning flags."""

    oc_discharge: bool = True
    oc_charge: bool = True
    overvoltage: bool = True
    undervoltage: bool = True
    temp_low: bool = True
    temp_high: bool = True
    comm_fail: bool = True

    def from_flags(self, flags_low: int, flags_high: int):
        self.oc_discharge = bool(flags_low & 1<<7)
        self.temp_low = bool(flags_low & 1<<4)
        self.temp_high = bool(flags_low & 1<<3)
        self.undervoltage = bool(flags_low & 1<<2)
        self.overvoltage = bool(flags_low & 1<<1)
        self.comm_fail = bool(flags_high & 1<<3)
        self.oc_charge = bool(flags_high & 1<<0)

    def to_flags(self) -> tuple[int]:
        flags_low = int(self.oc_discharge) * 1<<7
        flags_low |= int(self.temp_low) * 1<<4
        flags_low |= int(self.temp_high) * 1<<3
        flags_low |= int(self.undervoltage) * 1<<2
        flags_low |= int(self.overvoltage) * 1<<1
        flags_high = int(self.comm_fail) * 1<<3
        flags_high |= int(self.oc_charge) * 1<<0
        return flags_low, flags_high
    
    def copy(self) -> Self:
        return replace(self)