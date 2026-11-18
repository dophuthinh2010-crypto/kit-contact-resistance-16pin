# CR-TEST desktop app

Reads the ESP32 test kit over USB, records every contact resistance reading to CSV and shows them live.

Installation and use: **[../docs/INSTALL.md](../docs/INSTALL.md)**. Protocol: [../docs/serial-protocol.md](../docs/serial-protocol.md).

Quick start (Windows, Python 3.10+):

```bat
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m crkit_app
```

Pick **Simulator (no hardware)** as the port to try it without the kit.

| File | Purpose |
| --- | --- |
| `crkit_app/protocol.py` | Parses the kit's serial lines |
| `crkit_app/analysis.py` | Per-pin history, statistics, fail rule |
| `crkit_app/recorder.py` | CSV session files, resume, summary export |
| `crkit_app/serial_link.py` | Background serial reader/writer |
| `crkit_app/simulator.py` | Stand-in kit for testing without hardware |
| `crkit_app/main_window.py` | The window |
| `tests/test_core.py` | Tests for everything except the window: `python -m unittest discover tests` |
