"""Combine n x BMS states into one (virtual BMS) output state object."""

import threading

from .app_config import BatteryConfig
from .bms_state import BMSState


class BMSStateCombiner:
    """Combine n x BMS states into one (virtual BMS) output state object.

    This does the calculation of the appropriate total values for the system
    like error flags, the summing of all battery current values, applying
    offset or correction factors and applying setpoint limits.

    For further (yet unimplemented) control in multithreaded environment,
    the scaling and limiting values can be set using thread-safe setter methods.
    """

    def __init__(self, battery_conf: BatteryConfig) -> None:
        """Initialize BMSStateCombiner with emulated (virtual) battery config."""
        self._i_lim_charge = battery_conf.I_LIM_CHARGE
        self._i_lim_discharge = battery_conf.I_LIM_DISCHARGE
        self._i_tot_scaling = battery_conf.I_TOT_SCALING
        self._i_tot_offset = battery_conf.I_TOT_OFFSET
        self._thread_lock = threading.Lock()

    def set_i_tot_scaling(self, i_tot_scaling: float) -> None:
        """Set total current scaling factor (correction factor).

        Args:
            i_tot_scaling:  total current scaling factor
                            (default value is 1.0)

        """
        with self._thread_lock:
            self._i_tot_scaling = i_tot_scaling

    def set_tot_offset(self, i_tot_offset: float) -> None:
        """Set total current offset (correction value).

        Args:
            i_tot_offset:   total current offset in amperes
                            (default value is 0.0)

        """
        with self._thread_lock:
            self._i_tot_offset = i_tot_offset

    def set_i_lim_charge(self, i_lim_charge: float) -> None:
        """Set total current limit for charging.

        Args:
            i_lim_charge:   charging current limit setpoint in amperes

        """
        with self._thread_lock:
            self._i_lim_charge = i_lim_charge

    def set_i_lim_discharge(self, i_lim_discharge: float) -> None:
        """Set total current limit for discharging.

        Args:
            i_lim_discharge:    discharging current limit setpoint in amperes

        """
        with self._thread_lock:
            self._i_lim_discharge = i_lim_discharge

    def calculate_result_state(self, states_in: list[BMSState]) -> BMSState:
        """Calculate totalized output state.

        This does the calculation of the appropriate total values
        for the system like error flags, the summing of all battery
        current values, applying offset or correction factors and
        applying setpoint limits.

        Args:
            states_in:  input states
        Returns:
            output state

        """
        self._thread_lock.acquire()
        # Copy state of the first BMS to get a working copy for result calculation
        state = states_in[0].copy()
        # Averaged input values are weighted with each module capacity
        # and are divided by total system capacity further below
        soc_avg = state.soc * state.capacity_ah
        soh_avg = state.soh * state.capacity_ah
        t_avg = state.t_avg * state.capacity_ah
        v_avg = state.v_avg * state.capacity_ah
        for additional in states_in[1:]:
            # For end-of-charge maximum voltage setpoint, the minimum of all
            # voltages requested by the input BMSes is calculated
            state.v_charge_cmd = min(state.v_charge_cmd, additional.v_charge_cmd)
            # Averaged input values are weighted with each module capacity
            # and are divided by total system capacity further below.
            soc_avg += additional.soc * additional.capacity_ah
            soh_avg += additional.soh * additional.capacity_ah
            t_avg += additional.t_avg * additional.capacity_ah
            v_avg += additional.v_avg * additional.capacity_ah
            # Total capacity, total current and total current limis are the
            # sum of all limit values reported by the BMSes
            state.capacity_ah += additional.capacity_ah
            state.i_total += additional.i_total
            # Assuming well-tuned current distribution!
            state.i_lim_charge += additional.i_lim_charge
            state.i_lim_discharge += additional.i_lim_discharge
            # Sum for total number of modules and number of errors
            state.n_modules += additional.n_modules
            state.n_invalid_data_telegrams += additional.n_invalid_data_telegrams
            # Error and warning flags are logically OR-ed
            state.error_flags_1 |= additional.error_flags_1
            state.error_flags_2 |= additional.error_flags_2
            state.warning_flags_1 |= additional.warning_flags_1
            state.warning_flags_2 |= additional.warning_flags_2
            # The normal status flags are individually treated
            state.charge_enable = state.charge_enable and additional.charge_enable
            state.discharge_enable = state.discharge_enable and additional.discharge_enable
            state.force_charge_request = state.force_charge_request or additional.force_charge_request
            state.force_charge_request_2 = state.force_charge_request_2 or additional.force_charge_request_2
            state.balancing_charge_request = state.balancing_charge_request or additional.balancing_charge_request
            # Manufacturer string is kept from the first BMS

        # End of for loop
        # Calculate averaged results for total system state
        avg_factor_ah = 1.0 / state.capacity_ah
        state.soc = soc_avg * avg_factor_ah
        state.soh = soh_avg * avg_factor_ah
        state.v_avg = v_avg * avg_factor_ah
        state.t_avg = t_avg * avg_factor_ah
        # Apply scaling factor and offset to result current
        state.i_total *= self._i_tot_scaling
        state.i_total += self._i_tot_offset
        # Apply total current limits, overriding current limits set by BMSes
        state.i_lim_charge = min(state.i_lim_charge, self._i_lim_charge)
        state.i_lim_discharge = min(state.i_lim_discharge, self._i_lim_discharge)
        # Threading lock was set above
        self._thread_lock.release()
        return state
