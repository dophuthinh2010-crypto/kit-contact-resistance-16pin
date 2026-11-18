"""Parser for the CR-TEST kit serial protocol (see docs/serial-protocol.md)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

NPINS = 16
FLAGS = ("OK", "OVER", "UNDER", "OPEN")


@dataclass(frozen=True)
class Hello:
    firmware: str
    gain: int
    cycle: int


@dataclass(frozen=True)
class CycleStart:
    cycle: int
    trigger: str  # "MATE" or "MANUAL"


@dataclass(frozen=True)
class Zero:
    cycle: int
    v0: float
    v5: float


@dataclass(frozen=True)
class Data:
    cycle: int
    pin: int          # 1..16
    current_a: float
    voltage_mv: float
    r_mohm: float
    flag: str
    r_min_mohm: Optional[float] = None   # lowest of the 8 readings in this scan (firmware 0.2+), None if not sent


@dataclass(frozen=True)
class CycleEnd:
    cycle: int
    ms: int


@dataclass(frozen=True)
class Ack:
    command: str


@dataclass(frozen=True)
class Error:
    text: str


@dataclass(frozen=True)
class Info:
    text: str


Message = Union[Hello, CycleStart, Zero, Data, CycleEnd, Ack, Error, Info]


def _num(s: str) -> float:
    v = float(s)            # "nan" parses to NaN, which is what the firmware sends for no reading
    return v


def parse_line(line: str) -> Optional[Message]:
    """Turn one received line into a message. Returns None for blank or unrecognised lines."""
    line = line.strip()
    if not line:
        return None
    if line.startswith("#"):
        return Info(line[1:].strip())
    parts = [p.strip() for p in line.split(",")]
    kind = parts[0].upper()
    try:
        if kind == "HELLO" and len(parts) >= 5 and parts[1] == "CRKIT":
            return Hello(parts[2], int(parts[3]), int(parts[4]))
        if kind == "CYCLE" and len(parts) >= 3:
            return CycleStart(int(parts[1]), parts[2].upper())
        if kind == "ZERO" and len(parts) >= 4:
            return Zero(int(parts[1]), _num(parts[2]), _num(parts[3]))
        if kind == "DATA" and len(parts) >= 7:
            pin = int(parts[2])
            flag = parts[6].upper()
            if not 1 <= pin <= NPINS or flag not in FLAGS:
                return None
            rmin = _num(parts[7]) if len(parts) >= 8 and parts[7] else None
            return Data(int(parts[1]), pin, _num(parts[3]), _num(parts[4]), _num(parts[5]), flag, rmin)
        if kind == "END" and len(parts) >= 3:
            return CycleEnd(int(parts[1]), int(parts[2]))
        if kind == "OK" and len(parts) >= 2:
            return Ack(parts[1].upper())
        if kind == "ERR":
            return Error(line.split(",", 1)[1].strip() if "," in line else "")
    except ValueError:
        return None
    return None
