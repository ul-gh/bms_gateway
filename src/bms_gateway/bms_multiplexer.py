import threading

from .bms_state import BMSState
from .app_config import Battery_Config

class BMSMultiplexer():
    """Multiplex n x BMS states into one (virtual BMS) output state object.

    This does the calculation of the appropriate total values for the system
    like error flags, the summing of all battery current values, applying
    offset or correction factors and applying setpoint limits.

    For further (yet unimplemented) control in multithreaded environment,
    the scaling and limiting values can be set using thread-safe setter methods.
    """
    def __init__(self, battery_conf: Battery_Config):
        self._i_lim_charge = battery_conf.I_LIM_CHARGE
        self._i_lim_discharge = battery_conf.I_LIM_DISCHARGE
        self._i_tot_scaling = battery_conf.I_TOT_SCALING
        self._i_tot_offset = battery_conf.I_TOT_OFFSET
        self._thread_lock = threading.Lock()

    def set_i_tot_scaling(self, i_tot_scaling: float) -> None:
        """Set total current scaling factor (correction factor)
        
        Args:        
            i_tot_scaling:  total current scaling factor
                            (default value is 1.0)
        """
        with self._thread_lock:
            self._i_tot_scaling = i_tot_scaling

    def set_tot_offset(self, i_tot_offset: float) -> None:
        """Set total current offset (correction value)
        
        Args:        
            i_tot_offset:   total current offset in amperes
                            (default value is 0.0)
        """
        with self._thread_lock:
            self._i_tot_offset = i_tot_offset

    def set_i_lim_charge(self, i_lim_charge: float) -> None:
        """Set total current limit for charging
        
        Args:        
            i_lim_charge:   charging current limit setpoint in amperes
        """
        with self._thread_lock:
            self._i_lim_charge = i_lim_charge

    def set_i_lim_discharge(self, i_lim_discharge: float) -> None:
        """Set total current limit for discharging
        
        Args:        
            i_lim_discharge:    discharging current limit setpoint in amperes
        """
        with self._thread_lock:
            self._i_lim_discharge = i_lim_discharge

    def calculate_result_state(self, states_in: tuple[BMSState]) -> BMSState:
        """This does the calculation of the appropriate total values
        for the system like error flags, the summing of all battery
        current values, applying offset or correction factors and
        applying setpoint limits.

        Args:
            states_in:  input states
        Returns:
            output state
        """
        self._thread_lock.acquire()
        state = states_in[0].copy()
        #state.i_total = sum((state.i_total for state in states_in))
        state.soc *= state.capacity_ah
        state.soh *= state.capacity_ah
        for additional in states_in[1:]:
            # Average values need to be divided by total number of BMSes later
            state.soc += additional.soc * additional.capacity_ah
            state.soh += additional.soh * additional.capacity_ah
            state.v_charge_cmd = min(state.v_charge_cmd, additional.v_charge_cmd)
            state.i_lim_charge += additional.i_lim_charge
            state.i_lim_discharge += additional.i_lim_discharge
            # v_avg needs to be divided by total number of BMSes later
            state.v_avg += additional.v_avg
            state.i_total += additional.i_total
            # t_avg needs to be divided by total number of BMSes later
            state.t_avg += additional.t_avg
            state.error_flags_1 |= additional.error_flags_1
            state.error_flags_2 |= additional.error_flags_2
            state.warning_flags_1 |= additional.warning_flags_1
            state.warning_flags_2 |= additional.warning_flags_2
            state.n_modules += additional.n_modules
            state.charge_enable = state.charge_enable and additional.charge_enable
            state.discharge_enable = state.discharge_enable and additional.discharge_enable
            state.force_charge_request = state.force_charge_request or additional.force_charge_request
            state.force_charge_request_2 = state.force_charge_request_2 or additional.force_charge_request_2
            state.balancing_charge_request = state.balancing_charge_request or additional.balancing_charge_request
            state.n_invalid_data_telegrams += additional.n_invalid_data_telegrams
            state.capacity_ah += additional.capacity_ah
        # End of for loop
        # Divide sum of average values by number of averaged values to get total average
        avg_factor_ah = 1.0 / state.capacity_ah
        state.soc *= avg_factor_ah
        state.soh *= avg_factor_ah
        avg_factor_n = 1.0 / len(states_in)
        state.v_avg *= avg_factor_n
        state.t_avg *= avg_factor_n
        # Apply scaling factor and offset to result current
        state.i_total *= self._i_tot_scaling
        state.i_total += self._i_tot_offset
        # Apply total current limits, overriding current limits set by BMSes
        state.i_lim_charge = min(state.i_lim_charge, self._i_lim_charge)
        state.i_lim_discharge = min(state.i_lim_discharge, self._i_lim_discharge)
        # Threading lock was set above
        self._thread_lock.release()
        return state