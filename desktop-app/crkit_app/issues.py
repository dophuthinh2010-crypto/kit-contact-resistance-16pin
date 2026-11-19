"""Issue log: turns kit messages into a short list of events (open pins, shorts, alarms, failures, connection).

An event is logged when a problem starts and when it clears, not on every scan, so a pin that stays
open for 500 cycles is two lines, not 500. Events are kept in memory and, while a session is
recording, written to `<session>_issues.csv` next to the readings.
"""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, FrozenSet, Iterable, List, Optional, TextIO, Tuple

from .analysis import short_groups
from .protocol import Alarm, Data

ISSUE_COLUMNS = ["timestamp", "cycle", "severity", "type", "pins", "detail"]


@dataclass(frozen=True)
class Issue:
    timestamp: str
    cycle: int
    severity: str     # "critical", "warning" or "info"
    kind: str         # OPEN, OPEN cleared, SHORT, SHORT cleared, OVER RANGE, FAIL, ALARM, CONNECTION, ...
    pins: str         # "5", "4, 5", "" ...
    detail: str


def _pins(ps: Iterable[int]) -> str:
    return ", ".join(str(p) for p in sorted(ps))


class IssueLog:
    def __init__(self, on_new: Optional[Callable[[Issue], None]] = None) -> None:
        self.events: List[Issue] = []
        self.on_new = on_new
        self._fh: Optional[TextIO] = None
        self._writer = None
        self.path: Optional[str] = None
        self.reset_state()

    def reset_state(self) -> None:
        self._open: Dict[int, int] = {}            # pin -> cycle it went open
        self._over: Dict[int, int] = {}
        self._low: Dict[int, int] = {}
        self._shorts: Dict[FrozenSet[int], int] = {}   # group -> cycle first seen

    # ---- file -------------------------------------------------------------
    def start_csv(self, path: str, append: bool = False) -> None:
        self.stop_csv()
        exists = os.path.exists(path) and os.path.getsize(path) > 0
        self._fh = open(path, "a" if (append and exists) else "w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._fh)
        if not (append and exists):
            self._writer.writerow(ISSUE_COLUMNS)
            self._fh.flush()
        self.path = path

    def stop_csv(self) -> None:
        if self._fh:
            self._fh.close()
        self._fh, self._writer, self.path = None, None, None

    # ---- adding events ----------------------------------------------------
    def add(self, cycle: int, severity: str, kind: str, pins: str, detail: str) -> Issue:
        ev = Issue(datetime.now().isoformat(timespec="seconds"), cycle, severity, kind, pins, detail)
        self.events.append(ev)
        if self._writer:
            self._writer.writerow([ev.timestamp, ev.cycle, ev.severity, ev.kind, ev.pins, ev.detail])
            self._fh.flush()
        if self.on_new:
            self.on_new(ev)
        return ev

    def on_data(self, d: Data) -> None:
        p = d.pin
        if d.flag == "OPEN" and p not in self._open:
            self._open[p] = d.cycle
            self.add(d.cycle, "warning", "OPEN", str(p),
                     f"no test current through pin {p} ({max(0.0, d.current_a) * 1000:.0f} mA): contact open, not mated, or ribbon unplugged")
        elif d.flag != "OPEN" and p in self._open:
            since = self._open.pop(p)
            self.add(d.cycle, "info", "OPEN cleared", str(p), f"pin {p} conducts again (open since cycle {since})")
        if d.flag == "OVER" and p not in self._over:
            self._over[p] = d.cycle
            self.add(d.cycle, "warning", "OVER RANGE", str(p),
                     f"pin {p} resistance above the amplifier range: set JP1 to G11 and send GAIN 11")
        elif d.flag != "OVER" and p in self._over:
            since = self._over.pop(p)
            self.add(d.cycle, "info", "OVER RANGE cleared", str(p), f"pin {p} back in range (since cycle {since})")

        if d.flag == "LOW" and p not in self._low:
            self._low[p] = d.cycle
            self.add(d.cycle, "warning", "LOW", str(p),
                     f"pin {p} reads {d.r_mohm:.2f} mOhm, below any real contact: pins shorted together")
        elif d.flag != "LOW" and p in self._low:
            since = self._low.pop(p)
            self.add(d.cycle, "info", "LOW cleared", str(p), f"pin {p} reads normally again (low since cycle {since})")

    def on_isolation(self, cycle: int, pairs: Dict[Tuple[int, int], float]) -> None:
        groups = set(short_groups(pairs.keys()))
        for g in groups - set(self._shorts):
            self._shorts[g] = cycle
            uv = max(v for (a, b), v in pairs.items() if a in g and b in g)
            ps = sorted(g)
            names = ", ".join(str(x) for x in ps[:-1]) + f" and {ps[-1]}"
            self.add(cycle, "critical", "SHORT", _pins(g),
                     f"pins {names} are shorted together (isolation test: up to {uv:.0f} µV on an undriven pin). "
                     "Their resistance readings show the contacts in parallel and read low.")
        for g in set(self._shorts) - groups:
            since = self._shorts.pop(g)
            self.add(cycle, "info", "SHORT cleared", _pins(g), f"pins {_pins(g)} isolated again (short since cycle {since})")

    def on_alarm(self, a: Alarm) -> None:
        self.add(a.cycle, "critical", f"ALARM {a.code}", "", a.detail)

    def on_fail(self, pin: int, cycle: int, reason: str) -> None:
        self.add(cycle, "critical", "FAIL", str(pin), f"pin {pin} failed at cycle {cycle}: {reason}")

    def counts(self) -> Dict[str, int]:
        out = {"critical": 0, "warning": 0, "info": 0}
        for e in self.events:
            out[e.severity] = out.get(e.severity, 0) + 1
        return out
