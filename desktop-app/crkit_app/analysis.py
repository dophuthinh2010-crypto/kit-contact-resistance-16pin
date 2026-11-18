"""Per-pin tracking: history, statistics and the pass/fail rule."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .protocol import NPINS, Data


@dataclass
class PinState:
    pin: int
    cycles: List[int] = field(default_factory=list)
    values: List[float] = field(default_factory=list)   # mOhm, NaN where the reading was not valid
    latest: float = math.nan
    latest_flag: str = ""
    initial: float = math.nan
    minimum: float = math.inf
    maximum: float = -math.inf
    over_run: int = 0
    fail_cycle: Optional[int] = None
    mins: List[float] = field(default_factory=list)      # per-cycle minimum R (valid scans only)

    @property
    def avg_min(self) -> float:
        """Average of the per-cycle minimum readings, mOhm."""
        return sum(self.mins) / len(self.mins) if self.mins else math.nan

    @property
    def delta(self) -> float:
        """Change from the first valid reading, mOhm."""
        if math.isnan(self.initial) or math.isnan(self.latest):
            return math.nan
        return self.latest - self.initial


class Tracker:
    """Keeps every pin's readings and applies the fail rule.

    A pin fails after `consecutive` scans in a row that are above `limit_mohm`.
    OVER (above range) and OPEN (no current) readings count as above the limit.
    """

    def __init__(self, limit_mohm: float = 10.0, consecutive: int = 3, warn_fraction: float = 0.75):
        self.limit = limit_mohm
        self.consecutive = consecutive
        self.warn_fraction = warn_fraction
        self.reset()

    def reset(self) -> None:
        self.pins: Dict[int, PinState] = {p: PinState(p) for p in range(1, NPINS + 1)}
        self.last_cycle = 0

    def add(self, d: Data) -> None:
        st = self.pins[d.pin]
        valid = d.flag in ("OK", "UNDER") and not math.isnan(d.r_mohm)
        value = d.r_mohm if valid else math.nan
        st.cycles.append(d.cycle)
        st.values.append(value)
        st.latest = value
        st.latest_flag = d.flag
        if valid:
            m = d.r_min_mohm if d.r_min_mohm is not None and not math.isnan(d.r_min_mohm) else value
            st.mins.append(m)
            if math.isnan(st.initial):
                st.initial = value
            st.minimum = min(st.minimum, value)
            st.maximum = max(st.maximum, value)
        above = d.flag in ("OVER", "OPEN") or (valid and value > self.limit)
        if st.fail_cycle is None:
            st.over_run = st.over_run + 1 if above else 0
            if st.over_run >= self.consecutive:
                st.fail_cycle = d.cycle
        self.last_cycle = max(self.last_cycle, d.cycle)

    def recompute(self) -> None:
        """Re-apply the fail rule to all stored readings (after the limit changes)."""
        for st in self.pins.values():
            st.over_run, st.fail_cycle = 0, None
            for c, v in zip(st.cycles, st.values):
                above = math.isnan(v) or v > self.limit
                if st.fail_cycle is None:
                    st.over_run = st.over_run + 1 if above else 0
                    if st.over_run >= self.consecutive:
                        st.fail_cycle = c

    def status(self, pin: int) -> str:
        """'fail', 'open', 'wear', 'ok' or 'none' (no reading yet)."""
        st = self.pins[pin]
        if st.fail_cycle is not None:
            return "fail"
        if not st.cycles:
            return "none"
        if st.latest_flag == "OPEN":
            return "open"
        if not math.isnan(st.latest) and st.latest > self.limit * self.warn_fraction:
            return "wear"
        return "ok"

    def failed_pins(self) -> List[int]:
        return [p for p, st in self.pins.items() if st.fail_cycle is not None]

    def first_failure(self) -> Optional[tuple]:
        fails = [(st.fail_cycle, p) for p, st in self.pins.items() if st.fail_cycle is not None]
        return min(fails) if fails else None
