"""Timing generators and functions."""

import asyncio
import time
from collections.abc import AsyncGenerator, Callable, Generator
from itertools import count


async def async_fixed_time_intervals(
    period: float,
    n_repeats: int | None = None,
    resume_at: int = 0,
    *,
    break_last_cycle: bool = False,
) -> AsyncGenerator[tuple[int, float]]:
    """Async time generator for fixed interval timing.

    This delays the second and any further iteration by awaiting
    asyncio.sleep until the end of each cycle time is reached.

    Time stamping achieves exact timing over multiple iterations,
    without accumulating small differences of run time of
    individual iterations.

    Parameters
    ----------
        period: Period (cycle) time in seconds.
        n_repeats: Number of repeats. If left out or None, do infinite repeats.
        resume_at: Resume a previous run starting at this cycle number.
            This reduces the number of cycles for the call.
        break_last_cycle: When True, do not wait for end of cycle period after last run.

    Yields
    ------
        - Index number of the current repeat, starting at zero
        - Initial timestamp of the first run.
    """
    time_start = time.time()
    time_end = time_start + period
    time_remaining = 0.0
    # Begin initial test cycle
    counter = count(resume_at) if n_repeats is None else range(resume_at, n_repeats)
    for run_no in counter:
        yield run_no, time_start
        # Calculate remaining time to sleep until next cycle starts
        time_remaining = time_end - time.time()
        # If run took less than a period, set remaining time
        # and set next run end time to one period later.
        # If run took longer, add as many multiples of the period as needed
        # to have a positive remaining time for the next cycle.
        while time_remaining < 0.0:
            time_end += period
            time_remaining = time_end - time.time()
        # New end time for next cycle is plus one period
        time_end += period
        if n_repeats is not None and run_no >= n_repeats - 1:
            if not break_last_cycle:
                await asyncio.sleep(time_remaining)
            break
        await asyncio.sleep(time_remaining)
        # End of for loop
    return


def fixed_time_intervals(
    period: float,
    n_repeats: int | None = None,
    resume_at: int = 0,
    *,
    break_last_cycle: bool = False,
) -> Generator[tuple[int, float]]:
    """Time generator for fixed interval timing.

    This delays the second and any further iteration using a blocking
    call of time.sleep() until the end of each cycle time is reached.

    Time stamping achieves exact timing over multiple iterations,
    without accumulating small differences of run time of
    individual iterations.

    Parameters
    ----------
        period: Period (cycle) time in seconds.
        n_repeats: Number of repeats. If left out or None, do infinite repeats.
        resume_at: Resume a previous run starting at this cycle number.
            This reduces the number of cycles for the call.
        break_last_cycle: When True, do not wait for end of cycle period after last run.

    Yields
    ------
        - Index number of the current repeat, starting at zero
        - Initial timestamp of the first run.
    """
    time_start = time.time()
    time_end = time_start + period
    time_remaining = 0.0
    # Begin initial test cycle
    counter = count(resume_at) if n_repeats is None else range(resume_at, n_repeats)
    for run_no in counter:
        yield run_no, time_start
        # Calculate remaining time to sleep until next cycle starts
        time_remaining = time_end - time.time()
        # If run took less than a period, set remaining time
        # and set next run end time to one period later.
        # If run took longer, add as many multiples of the period as needed
        # to have a positive remaining time for the next cycle.
        while time_remaining < 0.0:
            time_end += period
            time_remaining = time_end - time.time()
        # New end time for next cycle is plus one period
        time_end += period
        if n_repeats is not None and run_no >= n_repeats - 1:
            if not break_last_cycle:
                time.sleep(time_remaining)
            break
        time.sleep(time_remaining)
        # End of for loop
    return


def repeat_periodic(
    fn: Callable[[int], object],
    period: float,
    n_repeats: int | None = None,
    resume_at: int = 0,
    *,
    break_last_cycle: bool = False,
) -> float:
    """Run a function periodically, using time stamping.

    This delays the second and any further call of fn() using a blocking
    call of time.sleep() until the end of each cycle time is reached.

    Time stamping achieves exact timing over multiple iterations,
    without accumulating small differences of run time of
    individual iterations.

    Parameters
    ----------
        fn: The function or method to be repeatedly called.
            Signature: fn(run_no: int) -> Any
        period: Period (cycle) time in seconds.
        n_repeats: Number of repeats. If left out or None, do infinite repeats.
        resume_at: Resume a previous run starting at this cycle number.
            This reduces the number of cycles for the call.
        break_last_cycle: When True, do not wait for end of cycle period after last run.

    Returns
    -------
        Time stamp after completing the last run (float value).
    """
    time_start = time.time()
    time_end = time_start + period
    time_remaining = 0.0
    # Begin initial test cycle
    counter = count(resume_at) if n_repeats is None else range(resume_at, n_repeats)
    for run_no in counter:
        _ = fn(run_no)
        # Calculate remaining time to sleep until next cycle starts
        time_remaining = time_end - time.time()
        # If run took less than a period, set remaining time
        # and set next run end time to one period later.
        # If run took longer, add as many multiples of the period as needed
        # to have a positive remaining time for the next cycle.
        while time_remaining < 0.0:
            time_end += period
            time_remaining = time_end - time.time()
        # New end time for next cycle is plus one period
        time_end += period
        if n_repeats is not None and run_no >= n_repeats - 1:
            if not break_last_cycle:
                time.sleep(time_remaining)
            break
        time.sleep(time_remaining)
        # End of for loop
    # Return total run time in seconds.
    return time_end - time_start - period - (time_remaining if break_last_cycle else 0.0)


def repeat_periodic_while(
    fn: Callable[[int], bool],
    period: float,
    n_repeats: int | None = None,
    resume_at: int = 0,
    *,
    break_last_cycle: bool = False,
) -> float:
    """Run a function periodically, using time stamping.

    This delays the second and any further call of fn() using a blocking
    call of time.sleep() until the end of each cycle time is reached.

    Function is only repeated while it returns a True return value.

    Time stamping achieves exact timing over multiple iterations,
    without accumulating small differences of run time of
    individual iterations.

    Parameters
    ----------
        fn: The function or method to be repeatedly called.
            Signature: fn(run_no: int) -> bool
            When fn returns False, further repeats are aborted.
        period: Period (cycle) time in seconds.
        n_repeats: Number of repeats. If left out or None, do infinite repeats.
        resume_at: Resume a previous run starting at this cycle number.
            This reduces the number of cycles for the call.
        break_last_cycle: When True, do not wait for end of cycle period after last run.

    Returns
    -------
        Time stamp after completing the last run (float value).
    """
    time_start = time.time()
    time_end = time_start + period
    time_remaining = 0.0
    # Begin initial test cycle
    counter = count(resume_at) if n_repeats is None else range(resume_at, n_repeats)
    for run_no in counter:
        fn_do_continue = fn(run_no)
        # Calculate remaining time to sleep until next cycle starts
        time_remaining = time_end - time.time()
        # If run took less than a period, set remaining time
        # and set next run end time to one period later.
        # If run took longer, add as many multiples of the period as needed
        # to have a positive remaining time for the next cycle.
        while time_remaining < 0.0:
            time_end += period
            time_remaining = time_end - time.time()
        # New end time for next cycle is plus one period
        time_end += period
        if not fn_do_continue:
            if not break_last_cycle:
                time.sleep(time_remaining)
            break
        time.sleep(time_remaining)
        # End of for loop
    # Return total run time in seconds.
    return time_end - time_start - period - (time_remaining if break_last_cycle else 0.0)
