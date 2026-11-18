"""Background serial link: reads lines from the kit and sends commands, off the GUI thread."""
from __future__ import annotations

import queue
import threading
from typing import List, Tuple

from PySide6.QtCore import QObject, Signal

from .simulator import SimulatedKit

SIMULATOR = "Simulator (no hardware)"
BAUD = 115200


def list_ports() -> List[Tuple[str, str]]:
    """[(device, description)], real ports first, the simulator last."""
    out: List[Tuple[str, str]] = []
    try:
        from serial.tools import list_ports as lp
        for p in sorted(lp.comports(), key=lambda p: p.device):
            desc = p.description or ""
            hint = ""
            if p.vid in (0x10C4,):          # Silicon Labs CP210x (most ESP32-DevKitC)
                hint = "  ← ESP32 (CP210x)"
            elif p.vid in (0x1A86,):        # WCH CH340/CH9102
                hint = "  ← ESP32 (CH340/CH9102)"
            elif p.vid in (0x303A,):        # Espressif native USB
                hint = "  ← ESP32 (native USB)"
            out.append((p.device, f"{p.device}  {desc}{hint}"))
    except ImportError:
        pass
    out.append((SIMULATOR, SIMULATOR))
    return out


class SerialLink(QObject):
    line = Signal(str)
    opened = Signal(str)
    closed = Signal(str)       # reason ("" when closed by the user)

    def __init__(self) -> None:
        super().__init__()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._tx: "queue.Queue[str]" = queue.Queue()
        self.port_name = ""

    @property
    def is_open(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def open(self, port: str) -> None:
        if self.is_open:
            self.close()
        self._stop.clear()
        self._tx = queue.Queue()
        self.port_name = port
        self._thread = threading.Thread(target=self._run, args=(port,), daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        self._thread = None

    def send(self, command: str) -> None:
        self._tx.put(command.strip())

    def _run(self, port: str) -> None:
        try:
            if port == SIMULATOR:
                dev = SimulatedKit()
            else:
                import serial
                dev = serial.Serial()
                dev.port, dev.baudrate, dev.timeout = port, BAUD, 0.2
                dev.dtr = False            # keep the ESP32 out of reset / boot mode on open
                dev.rts = False
                dev.open()
                dev.reset_input_buffer()
        except Exception as e:           # port busy, unplugged, no permission, pyserial missing
            self.closed.emit(f"Could not open {port}: {e}")
            return
        self.opened.emit(port)
        self._tx.put("STATUS")
        reason = ""
        buf = b""
        try:
            while not self._stop.is_set():
                while not self._tx.empty():
                    dev.write((self._tx.get_nowait() + "\n").encode())
                chunk = dev.readline()
                if not chunk:
                    continue
                buf += chunk
                while b"\n" in buf:
                    raw, buf = buf.split(b"\n", 1)
                    text = raw.decode("utf-8", errors="replace").strip("\r")
                    if text:
                        self.line.emit(text)
        except Exception as e:           # USB cable pulled, board reset, driver error
            reason = f"Connection lost: {e}"
        finally:
            try:
                dev.close()
            except Exception:
                pass
        self.closed.emit(reason)
