"""CSV recording of a test session, and reading a session back to resume it."""
from __future__ import annotations

import csv
import math
import os
from datetime import datetime
from typing import Dict, List, Optional, TextIO, Tuple

from .protocol import Data

COLUMNS = ["timestamp", "cycle", "pin", "current_A", "voltage_mV", "r_mOhm", "flag", "trigger"]


class SessionRecorder:
    """Writes one CSV file per test session.

    The file starts with '# key: value' lines (session details), then a header row,
    then one row per pin per scan. Each scan is flushed to disk when it ends, so a
    power cut loses at most the scan in progress.
    """

    def __init__(self) -> None:
        self.path: Optional[str] = None
        self._fh: Optional[TextIO] = None
        self._writer = None
        self.rows_written = 0

    @property
    def active(self) -> bool:
        return self._fh is not None

    def start(self, path: str, meta: Dict[str, str], append: bool = False) -> None:
        self.stop()
        exists = os.path.exists(path) and os.path.getsize(path) > 0
        mode = "a" if (append and exists) else "w"
        self._fh = open(path, mode, newline="", encoding="utf-8")
        self.path = path
        self._writer = csv.writer(self._fh)
        if mode == "w":
            self._fh.write("# CR-TEST contact resistance log\n")
            for k, v in meta.items():
                self._fh.write(f"# {k}: {str(v).replace(chr(10), ' ')}\n")
            self._writer.writerow(COLUMNS)
        else:
            self._fh.write(f"# resumed: {datetime.now().isoformat(timespec='seconds')}\n")
        self._fh.flush()
        self.rows_written = 0

    def write(self, d: Data, trigger: str = "") -> None:
        if not self._writer:
            return
        r = "" if math.isnan(d.r_mohm) else f"{d.r_mohm:.4f}"
        self._writer.writerow([datetime.now().isoformat(timespec="milliseconds"), d.cycle, d.pin,
                               f"{d.current_a:.4f}", f"{d.voltage_mv:.4f}", r, d.flag, trigger])
        self.rows_written += 1

    def flush(self) -> None:
        if self._fh:
            self._fh.flush()
            os.fsync(self._fh.fileno())

    def stop(self) -> None:
        if self._fh:
            self.flush()
            self._fh.close()
        self._fh, self._writer = None, None


def load_session(path: str) -> Tuple[Dict[str, str], List[Data]]:
    """Read a session CSV. Returns (session details, readings)."""
    meta: Dict[str, str] = {}
    rows: List[Data] = []
    with open(path, newline="", encoding="utf-8") as fh:
        body = []
        for line in fh:
            if line.startswith("#"):
                if ":" in line:
                    k, v = line[1:].split(":", 1)
                    meta.setdefault(k.strip(), v.strip())
            else:
                body.append(line)
    for rec in csv.DictReader(body):
        try:
            r = float(rec["r_mOhm"]) if rec["r_mOhm"] else math.nan
            rows.append(Data(int(rec["cycle"]), int(rec["pin"]), float(rec["current_A"]),
                             float(rec["voltage_mV"]), r, rec["flag"]))
        except (KeyError, ValueError):
            continue
    return meta, rows


def write_summary(path: str, tracker, meta: Dict[str, str]) -> None:
    """One row per pin: first, latest, min, max, change and fail cycle."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        for k, v in meta.items():
            fh.write(f"# {k}: {v}\n")
        fh.write(f"# fail rule: {tracker.consecutive} scans in a row above {tracker.limit} mOhm\n")
        w = csv.writer(fh)
        w.writerow(["pin", "first_mOhm", "latest_mOhm", "min_mOhm", "max_mOhm", "change_mOhm", "status", "fail_cycle"])
        f = lambda v: "" if (v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))) else f"{v:.3f}"
        for p, st in tracker.pins.items():
            w.writerow([p, f(st.initial), f(st.latest), f(st.minimum), f(st.maximum), f(st.delta),
                        tracker.status(p), st.fail_cycle if st.fail_cycle is not None else ""])
