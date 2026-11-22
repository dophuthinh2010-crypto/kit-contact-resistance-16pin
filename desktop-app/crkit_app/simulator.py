"""A stand-in for the ESP32 that speaks the same serial protocol.

Lets you try the app without hardware: pick "Simulator" as the port. It behaves like
the firmware (commands, replies, scans) and runs a plug/unplug cycle every few seconds.
Contact wear follows an assumed model, the same one as docs/simulation/index.html.
Measurement physics follow main board rev C: LM317T constant-current source (0.625 A),
CD4053B mux trees, ADS1115 differential at +-0.256 V for the contact and for the 0.1 ohm shunt.
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
        self.gain = 16             # ADS1115 PGA gain, fixed on rev C
        self.auto = True
        self.cycle = 0
        self.interval = cycle_interval_s
        self.speedup = speedup
        self._next = time.monotonic() + 1.0
        self.sim_left = 0          # cycles still to run in a SIMRUN
        self.read_timeout = 0.2    # s, like a serial port's timeout
        self.open_pins = set()     # injected faults (0-based pin indexes)
        self.short_groups = []     # list of sets of 0-based pins shorted together
        self.r0 = [2.2 + self._rng.random() * 1.3 for _ in range(16)]
        self.a = [6.2 if i == 10 else 3.0 * math.exp(self._rng.gauss(0, 0.22)) for i in range(16)]
        self.zero = [0.0] * 16
        self.gcorr = 1 / self.ATTEN   # as after CALREF: mux and filter resistance loading calibrated out
        self.i_set = 1.25 * (1 + self._rng.gauss(0, 0.008)) / 2.0   # this kit's LM317T current, about 0.625 A
        self.ch_off = [self._rng.uniform(-12e-6, 12e-6) for _ in range(16)]   # ADS offset + thermal EMF per channel, V
        self.sh_off = self._rng.uniform(-10e-6, 10e-6)
        self._emit("# CR-TEST kit ready (simulator). Send STATUS, SCAN or MEASURE.")
        self._hello()

    # ---- serial-like interface ----
    def readline(self) -> bytes:
        deadline = time.monotonic() + self.read_timeout
        while time.monotonic() < deadline:
            with self._lock:
                if self._out:
                    return (self._out.popleft() + "\n").encode()
            if (self.auto or self.sim_left > 0) and time.monotonic() >= self._next:
                self._next = time.monotonic() + self.interval
                self._scan("MATE", True)
                if self.sim_left > 0:
                    self.sim_left -= 1
                    if self.sim_left == 0:
                        self._emit("# simulation run finished")
                        self._emit("OK,SIMDONE")
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
        self._emit(f"HELLO,CRKIT,0.5.0-sim,{self.gain},{self.cycle}")

    def _true_r(self, p: int, n: int) -> float:
        r = self.r0[p] + self.a[p] * (n / 500) ** 1.6
        if self._rng.random() < 0.003 + 0.03 * (n / 1000) ** 2:
            r += 0.5 + self._rng.random() * 3
        return r

    # ---- measurement physics (board rev C) -----------------------------------
    LSB = 0.256 / 32768   # V, ADS1115 at +-0.256 V
    ATTEN = 0.969         # 2 x (10 k + 4 x CD4053B Ron + 1 k) against the ADS1115 710 k differential input
    R_SH = 0.100          # ohm, shunt
    R_SHORT = 0.0005      # ohm, resistance of an injected pin-to-pin short
    ISO_LIMIT_UV = 50.0   # isolation test: contact voltage above its current-off baseline = short
    R_LOW_LIMIT = 0.8     # mOhm, readings below this are flagged LOW (possible short)

    def _adc(self, v: float) -> float:
        """One ADS1115 differential reading at +-0.256 V: noise, quantisation, clipping."""
        v = v + self._rng.gauss(0, 2.0e-6)
        v = round(v / self.LSB) * self.LSB
        return min(0.256 - self.LSB, max(-0.256, v))

    def _groups(self) -> dict:
        out = {}
        for g in self.short_groups:
            for p in g:
                out[p] = g
        return out

    def _r_eff(self, p: int, r: list, groups: dict) -> float:
        """Resistance seen between female pad p and male pad p, with shorted neighbours in parallel."""
        g = groups.get(p)
        if not g:
            return r[p]
        cond = 1 / r[p] + sum(1 / (r[m] + self.R_SHORT) for m in g if m != p and m not in self.open_pins)
        return 1 / cond

    def _scan(self, trigger: str, count: bool, only_pin: int = -1) -> list:
        if count:
            self.cycle += 1
        n = max(self.cycle, 0)
        self._emit(f"CYCLE,{self.cycle},{trigger}")
        v5 = 5.0 + self._rng.gauss(0, 0.01)
        sh_zero = sum(self._adc(self.sh_off) for _ in range(8)) / 8
        self._emit(f"ZERO,{self.cycle},{sh_zero:.6f},{v5:.3f}")
        r = [self._true_r(p, n) / 1000 for p in range(16)]          # true contact R this cycle, ohm
        groups = self._groups()
        raw = [math.nan] * 16
        for p in range(16):
            if 0 <= only_pin != p:
                continue
            off = self.ch_off[p]
            v_off = sum(self._adc(off) for _ in range(4)) / 4    # current-off reading of this channel
            if p in self.open_pins:
                reff, i_true = math.nan, 0.0
            else:
                reff = self._r_eff(p, r, groups)
                i_true = self.i_set                              # constant current: independent of the contact
            samples, vc_sum, vs_sum = [], 0.0, 0.0
            for _ in range(8):                                   # 8 readings per pin, like the firmware
                vc_s = self._adc(off + (0.0 if math.isnan(reff) else i_true * reff * self.ATTEN)) - v_off
                vs_s = self._adc(self.sh_off + i_true * self.R_SH) - sh_zero
                vc_sum += vc_s; vs_sum += vs_s
                i_s = vs_s / self.R_SH
                if i_s > 0.2:
                    samples.append(vc_s / i_s * 1000)
            vc, i = vc_sum / 8, vs_sum / 8 / self.R_SH
            if i < 0.2:
                flag, rr, rmin = "OPEN", math.nan, math.nan
            else:
                raw[p] = vc / i * 1000
                rr = (raw[p] - self.zero[p]) * self.gcorr
                flag = "OVER" if vc >= 0.25 else ("LOW" if rr < self.R_LOW_LIMIT else "OK")
                rmin = (min(samples) - self.zero[p]) * self.gcorr if samples else math.nan
            self._emit(f"DATA,{self.cycle},{p + 1},{i:.4f},{vc * 1000:.4f},{rr:.4f},{flag},{rmin:.4f}")
        if only_pin < 0:
            self._isolation_test(r, groups)
        self._emit(f"END,{self.cycle},{int(2500 / self.speedup)}")
        return raw

    def _isolation_test(self, r: list, groups: dict) -> None:
        """Drive each pin in turn and read every other pin's contact voltage: it must be ~0."""
        found = {}
        off = self.ch_off
        base = [sum(self._adc(off[b]) for _ in range(4)) / 4 * 1e6 for b in range(16)]
        for a in range(16):
            if a in self.open_pins:
                continue                                       # no current can flow: nothing to test from here
            reff = self._r_eff(a, r, groups)
            i_tot = self.i_set
            g = groups.get(a, ())
            for b in range(16):
                if b == a:
                    continue
                v = 0.0
                if b in g and b not in self.open_pins:
                    v = i_tot * reff / (r[b] + self.R_SHORT) * r[b] * self.ATTEN
                uv = sum(self._adc(off[b] + v) for _ in range(2)) / 2 * 1e6 - base[b]
                if uv > self.ISO_LIMIT_UV:
                    key = (min(a, b), max(a, b))
                    found[key] = max(found.get(key, 0.0), uv)
        for (a, b), uv in sorted(found.items()):
            self._emit(f"SHORT,{self.cycle},{a + 1},{b + 1},{uv:.0f}")
        self._emit(f"ISO,{self.cycle},{len(found)}")

    def describe_faults(self) -> str:
        o = ", ".join(str(p + 1) for p in sorted(self.open_pins)) or "none"
        sh = "; ".join("-".join(str(p + 1) for p in sorted(g)) for g in self.short_groups) or "none"
        return f"open pins: {o} | shorted groups: {sh}"

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
            self._emit("ERR,board rev C has no gain setting: the ADS1115 always runs at +-0.256 V")
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
        elif cmd == "SIMRUN":                                 # simulator only: run N cycles, one every T ms
            try:
                parts = arg.split()
                n = int(parts[0]); ms = int(parts[1]) if len(parts) > 1 else 1000
                if n < 1 or ms < 20:
                    raise ValueError
            except (ValueError, IndexError):
                self._emit("ERR,use SIMRUN <cycles> <ms per cycle>, e.g. SIMRUN 100 1000"); return
            self.auto = False
            self.sim_left, self.interval = n, ms / 1000
            self._next = time.monotonic() + self.interval
            self._emit("OK,SIMRUN")
        elif cmd == "SIMSTOP":
            self.sim_left = 0; self._emit("OK,SIMSTOP")
        elif cmd == "FAULT":                                  # simulator only: inject a wiring fault
            kind, _, pins = arg.strip().partition(" ")
            kind = kind.upper()
            try:
                if kind == "CLEAR":
                    self.open_pins, self.short_groups = set(), []
                elif kind == "OPEN":
                    ps = {int(x) - 1 for x in pins.replace(",", " ").split()}
                    if not ps or not all(0 <= p < 16 for p in ps):
                        raise ValueError
                    self.open_pins |= ps
                elif kind == "SHORT":
                    ps = {int(x) - 1 for x in pins.replace("-", " ").replace(",", " ").split()}
                    if len(ps) < 2 or not all(0 <= p < 16 for p in ps):
                        raise ValueError
                    self.short_groups.append(ps)
                else:
                    raise ValueError
            except ValueError:
                self._emit("ERR,use FAULT OPEN 2,9 | FAULT SHORT 4-5 | FAULT CLEAR"); return
            self._emit(f"# faults now: {self.describe_faults()}")
            self._emit("OK,FAULT")
        elif cmd == "CALCLEAR":
            self.zero, self.gcorr = [0.0] * 16, 1.0; self._emit("OK,CALCLEAR")
        else:
            self._emit(f"ERR,unknown command {cmd}")
