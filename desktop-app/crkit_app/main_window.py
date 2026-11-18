"""Main window of the CR-TEST desktop app."""
from __future__ import annotations

import math
import os
import re
from datetime import datetime

os.environ.setdefault("PYQTGRAPH_QT_LIB", "PySide6")

from PySide6.QtCore import Qt, QSettings, QTimer, QStandardPaths            # noqa: E402
from PySide6.QtGui import QColor, QFont, QAction                             # noqa: E402
from PySide6.QtWidgets import (                                              # noqa: E402
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)
import pyqtgraph as pg                                                       # noqa: E402

from . import __version__                                                    # noqa: E402
from .analysis import Tracker                                                # noqa: E402
from .protocol import NPINS, Ack, Alarm, CycleEnd, CycleStart, Data, Error, Hello, Info, IsoDone, Short, Zero, parse_line  # noqa: E402
from .issues import IssueLog  # noqa: E402
from .recorder import SessionRecorder, load_session, write_summary          # noqa: E402
from .serial_link import SIMULATOR, SerialLink, list_ports                  # noqa: E402

ACCENT = "#2a9bb3"
BAR = "#d9a441"
CONTEXT = "#4a5666"
LIMIT = "#e2574c"
STATUS_STYLE = {
    "ok":   ("OK", "#4fb286"),
    "wear": ("WEAR", "#e0a03a"),
    "open": ("OPEN", "#e0a03a"),
    "fail": ("FAIL", "#e2574c"),
    "short": ("SHORT", "#e2574c"),
    "none": ("–", "#8d9aa8"),
}
SEVERITY_COLOR = {"critical": "#e2574c", "warning": "#e0a03a", "info": "#8d9aa8"}
SCENARIOS = [
    ("No fault", ["FAULT CLEAR"]),
    ("1 pin open (pin 5)", ["FAULT CLEAR", "FAULT OPEN 5"]),
    ("3 pins open (2, 9, 14)", ["FAULT CLEAR", "FAULT OPEN 2,9,14"]),
    ("2 pins shorted (4-5)", ["FAULT CLEAR", "FAULT SHORT 4-5"]),
    ("3 pins shorted (10-11-12)", ["FAULT CLEAR", "FAULT SHORT 10-11-12"]),
    ("Custom (type below)", None),
]
COLS = ["Pin", "Latest (mΩ)", "First (mΩ)", "Change (mΩ)", "Max (mΩ)", "Status", "Failed at cycle / note"]


def fmt(v: float, d: int = 3) -> str:
    return "–" if v is None or math.isnan(v) or math.isinf(v) else f"{v:.{d}f}"


class Tile(QFrame):
    def __init__(self, caption: str) -> None:
        super().__init__()
        self.setObjectName("tile")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        self.value = QLabel("–")
        self.value.setObjectName("tileValue")
        cap = QLabel(caption)
        cap.setObjectName("tileCaption")
        lay.addWidget(self.value)
        lay.addWidget(cap)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"CR-TEST  Contact Resistance Recorder  v{__version__}")
        self.resize(1360, 860)
        self.settings = QSettings("CR-TEST", "ContactResistanceRecorder")
        self.link = SerialLink()
        self.tracker = Tracker(self.settings.value("limit", 10.0, float), self.settings.value("consecutive", 3, int))
        self.recorder = SessionRecorder()
        self.trigger = ""
        self.selected_pin = 1
        self.dirty = False
        self.announced_fail: set = set()
        self.device_cycle = None
        self.issues = IssueLog(on_new=self._on_issue)
        self._iso_pairs = {}

        self._build_ui()
        self._connect_signals()
        self.refresh_ports()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_if_dirty)
        self.timer.start(400)
        self._refresh_all()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # connection bar
        bar = QHBoxLayout()
        self.port_box = QComboBox(); self.port_box.setMinimumWidth(360)
        self.refresh_btn = QPushButton("Refresh ports")
        self.connect_btn = QPushButton("Connect"); self.connect_btn.setObjectName("primary")
        self.device_lbl = QLabel("Not connected")
        bar.addWidget(QLabel("Port:")); bar.addWidget(self.port_box); bar.addWidget(self.refresh_btn)
        bar.addWidget(self.connect_btn); bar.addSpacing(16); bar.addWidget(self.device_lbl, 1)
        root.addLayout(bar)

        split = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(split, 1)

        # ---- left column: session + device
        left = QWidget(); ll = QVBoxLayout(left); ll.setContentsMargins(0, 0, 0, 0)
        sess = QGroupBox("Test session")
        f = QFormLayout(sess)
        self.sample_ed = QLineEdit(self.settings.value("sample", "RP16-T #1"))
        self.operator_ed = QLineEdit(self.settings.value("operator", ""))
        self.notes_ed = QLineEdit()
        self.limit_sb = QDoubleSpinBox(); self.limit_sb.setRange(1, 500); self.limit_sb.setDecimals(1)
        self.limit_sb.setSuffix(" mΩ"); self.limit_sb.setValue(self.tracker.limit)
        self.consec_sb = QSpinBox(); self.consec_sb.setRange(1, 20); self.consec_sb.setValue(self.tracker.consecutive)
        self.consec_sb.setSuffix(" scans in a row")
        default_dir = os.path.join(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation), "CR-TEST")
        self.folder_ed = QLineEdit(self.settings.value("folder", default_dir))
        self.folder_btn = QPushButton("…"); self.folder_btn.setFixedWidth(32)
        fr = QHBoxLayout(); fr.addWidget(self.folder_ed); fr.addWidget(self.folder_btn)
        f.addRow("Sample ID", self.sample_ed)
        f.addRow("Operator", self.operator_ed)
        f.addRow("Notes", self.notes_ed)
        f.addRow("Fail limit", self.limit_sb)
        f.addRow("Fail after", self.consec_sb)
        f.addRow("Save to", fr)
        self.rec_btn = QPushButton("Start recording"); self.rec_btn.setObjectName("primary")
        self.resume_btn = QPushButton("Resume from file…")
        self.summary_btn = QPushButton("Export summary…")
        self.rec_lbl = QLabel("Not recording"); self.rec_lbl.setWordWrap(True)
        f.addRow(self.rec_btn)
        f.addRow(self.resume_btn)
        f.addRow(self.summary_btn)
        f.addRow(self.rec_lbl)
        ll.addWidget(sess)

        dev = QGroupBox("Kit control")
        g = QGridLayout(dev)
        self.scan_btn = QPushButton("Scan now (counts a cycle)")
        self.measure_btn = QPushButton("Measure only")
        self.auto_cb = QCheckBox("Scan when the mate switch closes"); self.auto_cb.setChecked(True)
        self.gain_box = QComboBox(); self.gain_box.addItems(["11", "101", "1001"]); self.gain_box.setCurrentText("101")
        self.gain_btn = QPushButton("Set gain")
        self.setcycle_btn = QPushButton("Set cycle counter…")
        self.calzero_btn = QPushButton("Calibrate zero…")
        self.calref_btn = QPushButton("Calibrate with shunt…")
        self.calclear_btn = QPushButton("Clear calibration")
        g.addWidget(self.scan_btn, 0, 0); g.addWidget(self.measure_btn, 0, 1)
        g.addWidget(self.auto_cb, 1, 0, 1, 2)
        g.addWidget(QLabel("INA333 gain (match JP1)"), 2, 0); gl = QHBoxLayout(); gl.addWidget(self.gain_box); gl.addWidget(self.gain_btn)
        g.addLayout(gl, 2, 1)
        g.addWidget(self.setcycle_btn, 3, 0, 1, 2)
        g.addWidget(self.calzero_btn, 4, 0); g.addWidget(self.calref_btn, 4, 1)
        g.addWidget(self.calclear_btn, 5, 0, 1, 2)
        ll.addWidget(dev)

        sim = QGroupBox("Simulation mode (no hardware)")
        sg = QGridLayout(sim)
        self.sim_switch_btn = QPushButton("Connect to the simulator")
        self.sim_cycles = QSpinBox(); self.sim_cycles.setRange(1, 100000); self.sim_cycles.setValue(100)
        self.sim_cycles.setSuffix(" cycles")
        self.sim_period = QDoubleSpinBox(); self.sim_period.setRange(0.05, 30); self.sim_period.setDecimals(2)
        self.sim_period.setSingleStep(0.25); self.sim_period.setValue(1.0); self.sim_period.setSuffix(" s per cycle")
        self.sim_run_btn = QPushButton("Run simulation"); self.sim_run_btn.setObjectName("primary")
        self.sim_stop_btn = QPushButton("Stop")
        self.sim_lbl = QLabel("Uses the built-in simulated kit: plug/unplug cycles with an assumed wear model.")
        self.sim_lbl.setWordWrap(True)
        sg.addWidget(self.sim_switch_btn, 0, 0, 1, 2)
        sg.addWidget(QLabel("Run"), 1, 0); sg.addWidget(self.sim_cycles, 1, 1)
        sg.addWidget(QLabel("Cycle time"), 2, 0); sg.addWidget(self.sim_period, 2, 1)
        sg.addWidget(self.sim_run_btn, 3, 0); sg.addWidget(self.sim_stop_btn, 3, 1)
        self.fault_box = QComboBox(); self.fault_box.addItems([n for n, _ in SCENARIOS])
        self.fault_custom = QLineEdit(); self.fault_custom.setPlaceholderText("e.g.  open 3, 7; short 6-7-8")
        self.fault_btn = QPushButton("Apply fault")
        sg.addWidget(QLabel("Fault scenario"), 4, 0); sg.addWidget(self.fault_box, 4, 1)
        sg.addWidget(self.fault_custom, 5, 0, 1, 2)
        sg.addWidget(self.fault_btn, 6, 0, 1, 2)
        sg.addWidget(self.sim_lbl, 7, 0, 1, 2)
        ll.addWidget(sim)
        self.sim_target = 0
        ll.addStretch(1)
        self.device_controls = [self.scan_btn, self.measure_btn, self.auto_cb, self.gain_box, self.gain_btn,
                                self.setcycle_btn, self.calzero_btn, self.calref_btn, self.calclear_btn]
        split.addWidget(left)

        # ---- right: tiles, plot, table, console
        right = QSplitter(Qt.Orientation.Vertical)
        top = QWidget(); tl = QVBoxLayout(top); tl.setContentsMargins(0, 0, 0, 0)
        tiles = QHBoxLayout()
        self.t_cycle, self.t_failed, self.t_first, self.t_worst = (Tile("cycles"), Tile("pins failed"),
                                                                   Tile("first failure"), Tile("worst pin now"))
        for t in (self.t_cycle, self.t_failed, self.t_first, self.t_worst):
            tiles.addWidget(t)
        tl.addLayout(tiles)

        pg.setConfigOptions(antialias=True, background="#151c24", foreground="#c4ccd4")
        self.plot = pg.PlotWidget()
        self.plot.setLabel("left", "Contact resistance", units="mΩ")
        self.plot.setLabel("bottom", "Cycle")
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.plot.addLegend(offset=(10, 10))
        self.curves = {}
        for p in range(1, NPINS + 1):
            name = "Other pins" if p == 2 else None
            self.curves[p] = self.plot.plot([], [], pen=pg.mkPen(CONTEXT, width=1), name=name, connect="finite")
        self.sel_curve = self.plot.plot([], [], pen=pg.mkPen(ACCENT, width=2.2), name="Selected pin (click a row)", connect="finite")
        self.limit_line = pg.InfiniteLine(angle=0, pen=pg.mkPen(LIMIT, width=1.5, style=Qt.PenStyle.DashLine),
                                          label="limit {value:.1f} mΩ", labelOpts={"color": LIMIT, "position": 0.95})
        self.plot.addItem(self.limit_line)

        self.avg_plot = pg.PlotWidget()
        self.avg_plot.setLabel("left", "Average of per-cycle minimum", units="mΩ")
        self.avg_plot.setLabel("bottom", "Pin")
        self.avg_plot.showGrid(x=False, y=True, alpha=0.15)
        self.avg_plot.setMouseEnabled(x=False, y=False)
        self.avg_plot.getAxis("bottom").setTicks([[(i, str(i)) for i in range(1, NPINS + 1)]])
        self.avg_plot.setXRange(0.4, NPINS + 0.6, padding=0)
        self.avg_bars = pg.BarGraphItem(x=list(range(1, NPINS + 1)), height=[0] * NPINS, width=0.65,
                                        brush=BAR, pen=pg.mkPen(None))
        self.avg_hi = pg.BarGraphItem(x=[1], height=[0], width=0.65, brush=BAR, pen=pg.mkPen("#e6ebf0", width=2))
        self.avg_plot.addItem(self.avg_bars); self.avg_plot.addItem(self.avg_hi)
        self.avg_hi_txt = pg.TextItem(color="#e6ebf0", anchor=(0.5, 1.2))
        self.avg_lo_txt = pg.TextItem(color="#e6ebf0", anchor=(0.5, 1.2))
        self.avg_plot.addItem(self.avg_hi_txt); self.avg_plot.addItem(self.avg_lo_txt)
        self.avg_note = QLabel("Each cycle keeps the lowest of 8 readings per pin; a bar is the average of those minimums.")
        self.avg_note.setWordWrap(True)
        avg_tab = QWidget(); al = QVBoxLayout(avg_tab); al.setContentsMargins(0, 0, 0, 0)
        al.addWidget(self.avg_plot, 1); al.addWidget(self.avg_note)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.plot, "R vs cycle")
        self.tabs.addTab(avg_tab, "Average minimum R per pin")
        tl.addWidget(self.tabs, 1)
        right.addWidget(top)

        self.table = QTableWidget(NPINS, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        mono = QFont("Consolas"); mono.setStyleHint(QFont.StyleHint.Monospace)
        for r in range(NPINS):
            for c in range(len(COLS)):
                it = QTableWidgetItem("–" if c else str(r + 1))
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if c in (1, 2, 3, 4, 6):
                    it.setFont(mono)
                self.table.setItem(r, c, it)
        self.table.selectRow(0)
        right.addWidget(self.table)

        con = QWidget(); cl = QVBoxLayout(con); cl.setContentsMargins(0, 0, 0, 0)
        self.console = QPlainTextEdit(); self.console.setReadOnly(True); self.console.setMaximumBlockCount(3000)
        self.console.setFont(mono)
        self.show_data_cb = QCheckBox("Show DATA lines"); self.show_data_cb.setChecked(False)
        cmdrow = QHBoxLayout()
        self.cmd_ed = QLineEdit(); self.cmd_ed.setPlaceholderText("Type a command for the kit, e.g. STATUS, then press Enter")
        self.send_btn = QPushButton("Send")
        cmdrow.addWidget(self.cmd_ed, 1); cmdrow.addWidget(self.send_btn); cmdrow.addWidget(self.show_data_cb)
        cl.addWidget(self.console, 1); cl.addLayout(cmdrow)
        self.issue_table = QTableWidget(0, 6)
        self.issue_table.setHorizontalHeaderLabels(["Time", "Cycle", "Severity", "Type", "Pins", "Detail"])
        self.issue_table.verticalHeader().setVisible(False)
        self.issue_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.issue_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        hh = self.issue_table.horizontalHeader()
        for c in range(5):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.issue_table.setWordWrap(True)
        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.addTab(con, "Serial console")
        self.bottom_tabs.addTab(self.issue_table, "Issues (0)")
        right.addWidget(self.bottom_tabs)
        right.setSizes([420, 300, 160])
        split.addWidget(right)
        split.setSizes([360, 1000])

        menu = self.menuBar().addMenu("&Help")
        about = QAction("About", self); about.triggered.connect(self._about); menu.addAction(about)
        self._set_connected(False)

    def _connect_signals(self) -> None:
        self.refresh_btn.clicked.connect(self.refresh_ports)
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.link.line.connect(self.on_line)
        self.link.opened.connect(self.on_opened)
        self.link.closed.connect(self.on_closed)
        self.folder_btn.clicked.connect(self.pick_folder)
        self.rec_btn.clicked.connect(self.toggle_recording)
        self.resume_btn.clicked.connect(self.resume_session)
        self.summary_btn.clicked.connect(self.export_summary)
        self.scan_btn.clicked.connect(lambda: self.send("SCAN"))
        self.measure_btn.clicked.connect(lambda: self.send("MEASURE"))
        self.auto_cb.toggled.connect(lambda on: self.send(f"AUTO {1 if on else 0}"))
        self.gain_btn.clicked.connect(lambda: self.send(f"GAIN {self.gain_box.currentText()}"))
        self.setcycle_btn.clicked.connect(self.set_cycle)
        self.calzero_btn.clicked.connect(self.cal_zero)
        self.calref_btn.clicked.connect(self.cal_ref)
        self.calclear_btn.clicked.connect(lambda: self._confirm("Clear the kit's calibration?") and self.send("CALCLEAR"))
        self.limit_sb.valueChanged.connect(self.rules_changed)
        self.consec_sb.valueChanged.connect(self.rules_changed)
        self.table.itemSelectionChanged.connect(self.pin_selected)
        self.sim_switch_btn.clicked.connect(self.use_simulator)
        self.sim_run_btn.clicked.connect(self.run_simulation)
        self.sim_stop_btn.clicked.connect(lambda: self.send("SIMSTOP"))
        self.fault_btn.clicked.connect(self.apply_fault)
        self.cmd_ed.returnPressed.connect(self.send_typed)
        self.send_btn.clicked.connect(self.send_typed)

    # ------------------------------------------------------------------ connection
    def refresh_ports(self) -> None:
        last = self.settings.value("port", "")
        self.port_box.clear()
        for dev, label in list_ports():
            self.port_box.addItem(label, dev)
        i = self.port_box.findData(last)
        if i >= 0:
            self.port_box.setCurrentIndex(i)

    def toggle_connection(self) -> None:
        if self.link.is_open:
            self.link.close()
            return
        port = self.port_box.currentData()
        if not port:
            return
        self.settings.setValue("port", port)
        self.connect_btn.setEnabled(False)
        self.device_lbl.setText(f"Opening {port}…")
        self.link.open(port)

    def on_opened(self, port: str) -> None:
        self._set_connected(True)
        if port == SIMULATOR:
            self.link.send("AUTO 0")            # simulation mode: cycles only run when you press Run simulation
            self.auto_cb.blockSignals(True); self.auto_cb.setChecked(False); self.auto_cb.blockSignals(False)
            self.sim_lbl.setText("Simulator connected. Set the cycles and cycle time, then press Run simulation.")
        self.device_lbl.setText(f"Connected to {port}, waiting for the kit…")
        self.log(f"--- connected to {port}")

    def on_closed(self, reason: str) -> None:
        self._set_connected(False)
        self.device_lbl.setText(reason or "Not connected")
        self.log(f"--- {reason or 'disconnected'}")
        if reason:
            self.statusBar().showMessage(reason, 10000)
            self.issues.add(self.device_cycle or 0, "critical", "CONNECTION", "", reason)
        if reason and self.recorder.active:
            QMessageBox.warning(self, "Connection lost",
                                f"{reason}\n\nRecording is still open. Reconnect to continue; "
                                "readings taken while disconnected are not recorded.")

    def _set_connected(self, on: bool) -> None:
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText("Disconnect" if on else "Connect")
        self.port_box.setEnabled(not on)
        self.refresh_btn.setEnabled(not on)
        for w in self.device_controls + [self.cmd_ed, self.send_btn]:
            w.setEnabled(on)
        sim_on = on and self.link.port_name == SIMULATOR
        for w in (self.sim_cycles, self.sim_period, self.sim_run_btn, self.sim_stop_btn,
                  self.fault_box, self.fault_custom, self.fault_btn):
            w.setEnabled(sim_on)
        self.sim_switch_btn.setEnabled(not sim_on)

    def send(self, cmd: str) -> None:
        if not self.link.is_open:
            return
        self.link.send(cmd)
        self.log(f"> {cmd}")

    def send_typed(self) -> None:
        cmd = self.cmd_ed.text().strip()
        if cmd:
            self.send(cmd)
            self.cmd_ed.clear()

    # ------------------------------------------------------------------ incoming data
    def on_line(self, text: str) -> None:
        msg = parse_line(text)
        if not isinstance(msg, Data) or self.show_data_cb.isChecked():
            self.log(text)
        if msg is None:
            return
        if isinstance(msg, Hello):
            self.device_cycle = msg.cycle
            self.device_lbl.setText(f"Kit firmware {msg.firmware} · gain {msg.gain} · cycle counter {msg.cycle}"
                                    + ("  (simulator)" if self.link.port_name == SIMULATOR else ""))
            self.gain_box.setCurrentText(str(msg.gain))
        elif isinstance(msg, CycleStart):
            self.trigger = msg.trigger
            self.device_cycle = msg.cycle
            if self.sim_target and self.link.port_name == SIMULATOR and not self.sim_run_btn.isEnabled():
                self.sim_lbl.setText(f"Running: cycle {msg.cycle}  (target {self.sim_start + self.sim_target})")
        elif isinstance(msg, Zero):
            if not 4.5 < msg.v5 < 5.5:
                self.statusBar().showMessage(f"Warning: 5 V rail reads {msg.v5:.2f} V. Check the power supply.", 8000)
        elif isinstance(msg, Data):
            self.tracker.add(msg)
            self.issues.on_data(msg)
            if self.recorder.active:
                self.recorder.write(msg, self.trigger)
            self.dirty = True
        elif isinstance(msg, Short):
            self._iso_pairs[(msg.pin_a, msg.pin_b)] = msg.microvolts
        elif isinstance(msg, IsoDone):
            self.tracker.end_isolation(msg.cycle, self._iso_pairs.keys())
            self.issues.on_isolation(msg.cycle, dict(self._iso_pairs))
            self._iso_pairs = {}
            self.dirty = True
        elif isinstance(msg, Alarm):
            self.issues.on_alarm(msg)
            QApplication.beep()
            self.statusBar().showMessage(f"KIT ALARM {msg.code}: {msg.detail}", 20000)
        elif isinstance(msg, CycleEnd):
            if self.recorder.active:
                self.recorder.flush()
                self.rec_lbl.setText(f"Recording to {os.path.basename(self.recorder.path)}  ·  "
                                     f"{self.recorder.rows_written} rows this run")
            self._check_new_failures()
            self.dirty = True
        elif isinstance(msg, Error):
            self.statusBar().showMessage(f"Kit refused a command: {msg.text}", 8000)
        elif isinstance(msg, Ack):
            if msg.command == "SIMRUN":
                self.sim_lbl.setText(f"Running {self.sim_target} cycles…")
            elif msg.command in ("SIMDONE", "SIMSTOP"):
                self.sim_lbl.setText(f"Simulation {'finished' if msg.command == 'SIMDONE' else 'stopped'} at cycle {self.device_cycle}.")
                self.sim_run_btn.setEnabled(True)
            if msg.command in ("CALZERO", "CALREF", "CALCLEAR"):
                self.statusBar().showMessage(f"{msg.command} done. Calibration is saved in the kit.", 8000)
        elif isinstance(msg, Info):
            pass

    def _check_new_failures(self) -> None:
        for p in self.tracker.failed_pins():
            if p not in self.announced_fail:
                self.announced_fail.add(p)
                st = self.tracker.pins[p]
                self.issues.on_fail(p, st.fail_cycle, st.fail_reason)
                QApplication.beep()
                self.statusBar().showMessage(f"Pin {p} failed at cycle {st.fail_cycle}: {st.fail_reason}", 15000)

    # ------------------------------------------------------------------ session
    def pick_folder(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Folder for log files", self.folder_ed.text())
        if d:
            self.folder_ed.setText(d)

    def _meta(self) -> dict:
        return {
            "sample": self.sample_ed.text().strip(),
            "operator": self.operator_ed.text().strip(),
            "notes": self.notes_ed.text().strip(),
            "started": datetime.now().isoformat(timespec="seconds"),
            "fail_limit_mOhm": f"{self.limit_sb.value():.1f}",
            "fail_consecutive": str(self.consec_sb.value()),
            "ina_gain": self.gain_box.currentText(),
            "port": self.link.port_name or "",
            "app_version": __version__,
        }

    def toggle_recording(self) -> None:
        if self.recorder.active:
            self.recorder.stop()
            self.issues.stop_csv()
            self.rec_btn.setText("Start recording")
            self.rec_lbl.setText(f"Stopped. Saved {self.recorder.path}")
            return
        sample = self.sample_ed.text().strip()
        if not sample:
            QMessageBox.information(self, "Sample ID needed", "Enter a sample ID first, so the log file can be named.")
            return
        if any(st.cycles for st in self.tracker.pins.values()) and not self._confirm(
                "Start a new session? The readings on screen will be cleared (files already saved are kept)."):
            return
        folder = self.folder_ed.text().strip()
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as e:
            QMessageBox.warning(self, "Can't use that folder", str(e))
            return
        if self.link.is_open and self.device_cycle and self._confirm(
                f"The kit's cycle counter is at {self.device_cycle}. Reset it to 0 for this new sample?"):
            self.send("SETCYCLE 0")
            self.device_cycle = 0
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", sample).strip("_") or "sample"
        path = os.path.join(folder, f"{safe}_{datetime.now():%Y%m%d_%H%M%S}.csv")
        self.tracker.reset(); self.announced_fail.clear()
        self._clear_issues()
        self.recorder.start(path, self._meta())
        self.issues.start_csv(path[:-4] + "_issues.csv")
        self._save_settings()
        self.rec_btn.setText("Stop recording")
        self.rec_lbl.setText(f"Recording to {path}")
        self._refresh_all()

    def resume_session(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Resume a session", self.folder_ed.text(), "CSV files (*.csv)")
        if not path:
            return
        try:
            meta, rows = load_session(path)
        except Exception as e:
            QMessageBox.warning(self, "Can't read that file", str(e))
            return
        if self.recorder.active:
            self.recorder.stop()
        self.tracker.reset(); self.announced_fail.clear()
        for r in rows:
            self.tracker.add(r)
        self.announced_fail.update(self.tracker.failed_pins())
        self.sample_ed.setText(meta.get("sample", self.sample_ed.text()))
        self.operator_ed.setText(meta.get("operator", self.operator_ed.text()))
        self.recorder.start(path, {}, append=True)
        self.issues.start_csv(path[:-4] + "_issues.csv", append=True)
        self.rec_btn.setText("Stop recording")
        last = self.tracker.last_cycle
        self.rec_lbl.setText(f"Resumed {os.path.basename(path)} at cycle {last} ({len(rows)} readings)")
        self._refresh_all()
        if self.link.is_open and self.device_cycle != last and self._confirm(
                f"The file ends at cycle {last} but the kit counter is at {self.device_cycle}. "
                f"Set the kit to {last} so the numbering continues?"):
            self.send(f"SETCYCLE {last}")

    def export_summary(self) -> None:
        if not any(st.cycles for st in self.tracker.pins.values()):
            QMessageBox.information(self, "Nothing to export", "No readings yet.")
            return
        default = os.path.join(self.folder_ed.text(), f"summary_{datetime.now():%Y%m%d_%H%M%S}.csv")
        path, _ = QFileDialog.getSaveFileName(self, "Export summary", default, "CSV files (*.csv)")
        if path:
            meta = self._meta(); meta["cycles"] = str(self.tracker.last_cycle)
            write_summary(path, self.tracker, meta)
            self.statusBar().showMessage(f"Summary saved to {path}", 8000)

    def rules_changed(self) -> None:
        self.tracker.limit = self.limit_sb.value()
        self.tracker.consecutive = self.consec_sb.value()
        self.tracker.recompute()
        self.announced_fail = set(self.tracker.failed_pins())
        self.settings.setValue("limit", self.tracker.limit)
        self.settings.setValue("consecutive", self.tracker.consecutive)
        self._refresh_all()

    # ------------------------------------------------------------------ simulation mode
    def use_simulator(self) -> None:
        if self.link.is_open:
            self.link.close()
        i = self.port_box.findData(SIMULATOR)
        if i >= 0:
            self.port_box.setCurrentIndex(i)
        self.toggle_connection()

    def run_simulation(self) -> None:
        n = self.sim_cycles.value()
        ms = int(round(self.sim_period.value() * 1000))
        self.sim_target, self.sim_start = n, self.device_cycle or 0
        self.send("AUTO 0")
        self.send(f"SIMRUN {n} {ms}")
        self.sim_run_btn.setEnabled(False)
        self.sim_lbl.setText(f"Starting {n} cycles at {ms / 1000:.2f} s each…")
        if not self.recorder.active:
            self.statusBar().showMessage("Tip: press Start recording first to save the simulated readings to CSV.", 8000)

    def apply_fault(self) -> None:
        name, cmds = SCENARIOS[self.fault_box.currentIndex()]
        if cmds is None:                                       # custom: "open 3, 7; short 6-7-8"
            cmds = ["FAULT CLEAR"]
            for part in self.fault_custom.text().split(";"):
                kind, _, pins = part.strip().partition(" ")
                if kind.lower() in ("open", "short") and pins.strip():
                    cmds.append(f"FAULT {kind.upper()} {pins.strip()}")
            name = self.fault_custom.text().strip() or "no fault"
        for c in cmds:
            self.send(c)
        self.issues.add(self.device_cycle or 0, "info", "SCENARIO", "", f"simulator fault scenario: {name}")

    # ------------------------------------------------------------------ issues
    def _on_issue(self, ev) -> None:
        t = self.issue_table
        t.insertRow(0)
        for c, v in enumerate([ev.timestamp[11:], str(ev.cycle), ev.severity.upper(), ev.kind, ev.pins, ev.detail]):
            it = QTableWidgetItem(v)
            if c == 2 or c == 3:
                it.setForeground(QColor(SEVERITY_COLOR.get(ev.severity, "#e6ebf0")))
            t.setItem(0, c, it)
        n = self.issues.counts()
        self.bottom_tabs.setTabText(1, f"Issues ({n['critical']} critical, {n['warning']} warning)"
                                    if n["critical"] or n["warning"] else f"Issues ({len(self.issues.events)})")
        if ev.severity == "critical":
            self.bottom_tabs.setCurrentIndex(1)

    def _clear_issues(self) -> None:
        self.issues.events.clear()
        self.issues.reset_state()
        self.issue_table.setRowCount(0)
        self.bottom_tabs.setTabText(1, "Issues (0)")

    # ------------------------------------------------------------------ kit commands with prompts
    def set_cycle(self) -> None:
        n, ok = QInputDialog.getInt(self, "Set cycle counter", "Cycle counter value:", self.device_cycle or 0, 0, 10_000_000)
        if ok:
            self.send(f"SETCYCLE {n}")
            self.send("STATUS")

    def cal_zero(self) -> None:
        if self._confirm("Fit the shorting bar (force and sense shorted at both jack boards) "
                         "in place of the connector, then press Yes.\n\n"
                         "The kit stores each pin's reading as its zero offset."):
            self.send("CALZERO")

    def cal_ref(self) -> None:
        v, ok = QInputDialog.getDouble(self, "Calibrate with a reference shunt",
                                       "Fit the 4-terminal shunt on pin 1 and enter its value (mΩ):", 10.0, 0.1, 1000, 3)
        if ok:
            self.send(f"CALREF {v:.3f}")

    def _confirm(self, text: str) -> bool:
        return QMessageBox.question(self, "CR-TEST", text) == QMessageBox.StandardButton.Yes

    # ------------------------------------------------------------------ display
    def pin_selected(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if rows:
            self.selected_pin = rows[0].row() + 1
            self._refresh_plot()

    def _refresh_if_dirty(self) -> None:
        if self.dirty:
            self.dirty = False
            self._refresh_all()

    def _refresh_all(self) -> None:
        self._refresh_table()
        self._refresh_plot()
        self._refresh_tiles()

    def _refresh_table(self) -> None:
        for p, st in self.tracker.pins.items():
            r = p - 1
            self.table.item(r, 1).setText(fmt(st.latest))
            self.table.item(r, 2).setText(fmt(st.initial))
            self.table.item(r, 3).setText(("+" if st.delta > 0 else "") + fmt(st.delta) if not math.isnan(st.delta) else "–")
            self.table.item(r, 4).setText(fmt(st.maximum))
            label, color = STATUS_STYLE[self.tracker.status(p)]
            it = self.table.item(r, 5)
            it.setText(label); it.setForeground(QColor(color))
            f = it.font(); f.setBold(label in ("FAIL", "WEAR", "OPEN")); it.setFont(f)
            fc = self.table.item(r, 6)
            if st.fail_cycle is not None:
                fc.setText(f"{st.fail_cycle} ({st.fail_reason})")
            elif st.short_with:
                fc.setText("shorted to " + ", ".join(str(x) for x in sorted(st.short_with)))
            else:
                fc.setText("–")

    def _refresh_plot(self) -> None:
        for p, st in self.tracker.pins.items():
            if p == self.selected_pin:
                self.curves[p].setData([], [])        # drawn on top by sel_curve instead
            else:
                self.curves[p].setData(st.cycles, st.values)
        st = self.tracker.pins[self.selected_pin]
        self.sel_curve.setData(st.cycles, st.values)
        self._refresh_avg_chart()
        self.limit_line.setValue(self.tracker.limit)

    def _refresh_avg_chart(self) -> None:
        avg = [self.tracker.pins[p].avg_min for p in range(1, NPINS + 1)]
        valid = [(v, p) for p, v in enumerate(avg, 1) if not math.isnan(v)]
        heights = [0 if math.isnan(v) else v for v in avg]
        self.avg_bars.setOpts(height=heights)
        if not valid:
            self.avg_hi.setOpts(x=[1], height=[0]); self.avg_hi_txt.setText(""); self.avg_lo_txt.setText("")
            self.avg_note.setText("No cycles yet. Each cycle keeps the lowest of 8 readings per pin; "
                                  "a bar is the average of those minimums.")
            return
        (vh, ph), (vl, pl) = max(valid), min(valid)
        self.avg_hi.setOpts(x=[ph], height=[vh])
        self.avg_hi_txt.setText(f"{vh:.2f}"); self.avg_hi_txt.setPos(ph, vh)
        self.avg_lo_txt.setText(f"{vl:.2f}"); self.avg_lo_txt.setPos(pl, vl)
        self.avg_plot.setYRange(0, max(1.0, vh * 1.2), padding=0)
        n = len(self.tracker.pins[ph].mins)
        self.avg_note.setText(f"Over {n} cycles · highest: pin {ph}, {vh:.3f} mΩ (outlined) · lowest: pin {pl}, "
                              f"{vl:.3f} mΩ · spread {vh - vl:.3f} mΩ. Each cycle keeps the lowest of 8 readings per pin.")

    def _refresh_tiles(self) -> None:
        t = self.tracker
        self.t_cycle.value.setText(str(t.last_cycle))
        self.t_failed.value.setText(f"{len(t.failed_pins())} / {NPINS}")
        ff = t.first_failure()
        self.t_first.value.setText(f"cycle {ff[0]} · pin {ff[1]}" if ff else "–")
        latest = [(st.latest, p) for p, st in t.pins.items() if not math.isnan(st.latest)]
        if latest:
            v, p = max(latest)
            self.t_worst.value.setText(f"pin {p} · {v:.2f} mΩ")
        else:
            self.t_worst.value.setText("–")

    def log(self, text: str) -> None:
        self.console.appendPlainText(f"{datetime.now():%H:%M:%S}  {text}")

    # ------------------------------------------------------------------ misc
    def _about(self) -> None:
        QMessageBox.about(self, "About", f"CR-TEST Contact Resistance Recorder v{__version__}\n\n"
                          "Records the mated contact resistance of all 16 contacts of an "
                          "ITW McMurdo RP16-T / RS16P-T connector from the ESP32 test kit.\n\n"
                          "Protocol: docs/serial-protocol.md")

    def _save_settings(self) -> None:
        self.settings.setValue("sample", self.sample_ed.text())
        self.settings.setValue("operator", self.operator_ed.text())
        self.settings.setValue("folder", self.folder_ed.text())

    def closeEvent(self, ev) -> None:
        if self.recorder.active and not self._confirm("Recording is running. Stop recording and quit?"):
            ev.ignore()
            return
        self.recorder.stop()
        self.issues.stop_csv()
        self.link.close()
        self._save_settings()
        ev.accept()


STYLE = """
QWidget { background: #11161d; color: #e6ebf0; font-family: 'Segoe UI', 'IBM Plex Sans', sans-serif; font-size: 10pt; }
QGroupBox { border: 1px solid #2a3542; border-radius: 6px; margin-top: 14px; padding: 10px 8px 8px 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #8d9aa8; font-weight: 600; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTableWidget {
  background: #151c24; border: 1px solid #2a3542; border-radius: 4px; padding: 4px; selection-background-color: #2a9bb3; }
QPushButton { background: #1c2530; border: 1px solid #2a3542; border-radius: 5px; padding: 6px 12px; }
QPushButton:hover { border-color: #2a9bb3; }
QPushButton:disabled, QCheckBox:disabled, QComboBox:disabled { color: #56616d; }
QPushButton#primary { background: #2a9bb3; color: #06161a; border-color: #2a9bb3; font-weight: 600; }
QHeaderView::section { background: #1c2530; color: #8d9aa8; border: 0; border-bottom: 1px solid #2a3542; padding: 5px; }
QTableWidget { gridline-color: #232c37; }
QFrame#tile { background: #1c2530; border-radius: 6px; }
QLabel#tileValue { font-size: 15pt; font-family: Consolas, 'IBM Plex Mono', monospace; background: transparent; }
QLabel#tileCaption { color: #8d9aa8; font-size: 9pt; background: transparent; }
QSplitter::handle { background: #11161d; }
QTabWidget::pane { border: 1px solid #2a3542; border-radius: 4px; top: -1px; }
QTabBar::tab { background: #1c2530; color: #8d9aa8; border: 1px solid #2a3542; border-bottom: 0;
  border-top-left-radius: 5px; border-top-right-radius: 5px; padding: 6px 14px; margin-right: 2px; }
QTabBar::tab:selected { background: #151c24; color: #e6ebf0; border-color: #2a9bb3; }
QTabBar::tab:hover { color: #e6ebf0; }
QStatusBar { color: #e0a03a; }
"""
