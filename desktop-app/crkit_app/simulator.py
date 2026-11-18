"""A stand-in for the ESP32 that speaks the same serial protocol.

Lets you try the app without hardware: pick "Simulator" as the port. It behaves like
the firmware (commands, replies, scans) and runs a plug/unplug cycle every few seconds.
Contact wear follows an assumed model, the same one as docs/simulation/index.html.
"""
from __future__ import annotations

import math
import random
import threading
import time
from collections import deque


class SimulatedKit:
    """Has the parts of the pyserial Serial interface the app uses: readline, write, close, is_open."""

    port = "SIMULATOR"

    def __init__(self, cycle_interval_s: float = 3.0, seed: int = 20261118, speedup: float = 1.0):
        self._rng = random.Random(seed)
        self._out: deque = deque()
        self._lock = threading.Lock()
        self.is_open = True
        self.gain = 101
        self.auto = True
        self.cycle = 0
        self.interval = cycle_interval_s
        self.speedup = speedup
        self._next = time.monotonic() + 1.0
        self.r0 = [2.2 + self._rng.random() * 1.3 for _ in range(16)]
        self.a = [6.2 if i == 10 else 3.0 * math.exp(self._rng.gauss(0, 0.22)) for i in range(16)]
        self.zero = [0.0] * 16
        self.gcorr = 1.0
        self._emit("# CR-TEST kit ready (simulator). Send STATUS, SCAN or MEASURE.")
        self._hello()

    # ---- serial-like interface ----
    def readline(self) -> bytes:
        deadline = time.monotonic() + 0.2
        while time.monotonic() < deadline:
            with self._lock:
                if self._out:
                    return (self._out.popleft() + "\n").encode()
            if self.auto and time.monotonic() >= self._next:
                self._next = time.monotonic() + self.interval
                self._scan("MATE", True)
                continue
            time.sleep(0.01)
        return b""

    def write(self, data: bytes) -> int:
        for line in data.decode(errors="replace").splitlines():
            self._command(line.strip())
        return len(data)

    def reset_input_buffer(self) -> None:
        pass

    def close(self) -> None:
        self.is_open = False

    # ---- device behaviour ----
    def _emit(self, s: str) -> None:
        with self._lock:
            self._out.append(s)

    def _hello(self) -> None:
        self._emit(f"HELLO,CRKIT,0.1.0-sim,{self.gain},{self.cycle}")

    def _true_r(self, p: int, n: int) -> float:
        r = self.r0[p] + self.a[p] * (n / 500) ** 1.6
        if self._rng.random() < 0.003 + 0.03 * (n / 1000) ** 2:
            r += 0.5 + self._rng.random() * 3
        return r

    def _scan(self, trigger: str, count: bool, only_pin: int = -1) -> list:
        if count:
            self.cycle += 1
        n = max(self.cycle, 0)
        self._emit(f"CYCLE,{self.cycle},{trigger}")
        v5 = 5.0 + self._rng.gauss(0, 0.01)
        self._emit(f"ZERO,{self.cycle},{2.5 + self._rng.gauss(0, 0.001):.4f},{v5:.3f}")
        raw = [math.nan] * 16
        for p in range(16):
            if 0 <= only_pin != p:
                continue
            rt = self._true_r(p, n) / 1000
            i_true = 5 / (5.6 + 2.2 + 0.18 + rt)
            i = i_true + self._rng.gauss(0, 0.004 / math.sqrt(8) / 0.185)
            vi = self.gain * (i_true * rt + self._rng.gauss(0, 1.5e-6)) + self._rng.gauss(0, 0.0003)
            flag = "OK"
            if vi >= 3.2:
                flag, vi = "OVER", 3.25
            elif vi <= 0.06:
                flag, vi = "UNDER", 0.05
            vc = vi / self.gain
            raw[p] = vc / i * 1000
            r = (raw[p] - self.zero[p]) * self.gcorr
            self._emit(f"DATA,{self.cycle},{p + 1},{i:.4f},{vc * 1000:.4f},{r:.4f},{flag}")
        self._emit(f"END,{self.cycle},{int(420 / self.speedup)}")
        return raw

    def _command(self, line: str) -> None:
        if not line:
            return
        cmd, _, arg = line.partition(" ")
        cmd = cmd.upper()
        if cmd == "STATUS":
            self._hello()
        elif cmd == "SCAN":
            self._emit("OK,SCAN"); self._scan("MANUAL", True)
        elif cmd == "MEASURE":
            self._emit("OK,MEASURE"); self._scan("MANUAL", False)
        elif cmd == "SETCYCLE":
            try:
                self.cycle = max(0, int(arg)); self._emit("OK,SETCYCLE")
            except ValueError:
                self._emit("ERR,cycle must be a number")
        elif cmd == "GAIN":
            if arg.strip() in ("11", "101", "1001"):
                self.gain = int(arg); self._emit("OK,GAIN")
            else:
                self._emit("ERR,gain must be 11, 101 or 1001")
        elif cmd == "AUTO":
            self.auto = arg.strip() != "0"; self._emit("OK,AUTO")
        elif cmd == "CALZERO":
            self.zero = [0.0] * 16
            raw = self._scan("MANUAL", False)
            self.zero = [0.0 if math.isnan(v) else v for v in raw]
            self._emit("OK,CALZERO")
        elif cmd == "CALREF":
            try:
                ref = float(arg)
            except ValueError:
                ref = 0
            if ref <= 0:
                self._emit("ERR,give the reference value in mOhm, e.g. CALREF 10.0"); return
            self.gcorr = 1.0
            raw = self._scan("MANUAL", False, only_pin=0)
            self.gcorr = ref / (raw[0] - self.zero[0])
            self._emit(f"# gain correction = {self.gcorr:.4f}")
            self._emit("OK,CALREF")
        elif cmd == "CALCLEAR":
            self.zero, self.gcorr = [0.0] * 16, 1.0; self._emit("OK,CALCLEAR")
        else:
            self._emit(f"ERR,unknown command {cmd}")
