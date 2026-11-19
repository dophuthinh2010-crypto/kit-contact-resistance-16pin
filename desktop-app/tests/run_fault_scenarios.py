"""Runs the six fault scenarios (incl. all 16 pins shorted) through the app code on the simulated kit. Writes CSVs to ./fault_runs/."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from crkit_app.protocol import parse_line, Data, Short, IsoDone, CycleEnd  # noqa: E402
from crkit_app.analysis import Tracker  # noqa: E402
from crkit_app.issues import IssueLog  # noqa: E402
from crkit_app.recorder import SessionRecorder, write_summary  # noqa: E402
from crkit_app.simulator import SimulatedKit  # noqa: E402

OUT = "fault_runs"
os.makedirs(OUT, exist_ok=True)
SCEN = [
    ("0_no_fault", []),
    ("1_one_pin_open", ["FAULT OPEN 5"]),
    ("2_three_pins_open", ["FAULT OPEN 2,9,14"]),
    ("3_two_pins_shorted", ["FAULT SHORT 4-5"]),
    ("4_three_pins_shorted", ["FAULT SHORT 10-11-12"]),
    ("5_all_16_pins_shorted", ["FAULT SHORT 1-2-3-4-5-6-7-8-9-10-11-12-13-14-15-16"]),
]
CYCLES, FAULT_FROM, FAULT_TO = 30, 11, 20      # healthy 1-10, fault 11-20, fault removed 21-30

for name, faults in SCEN:
    kit = SimulatedKit(); kit.auto = False; kit.read_timeout = 0.005
    for _ in range(20):
        kit.readline()
    tr, log, rec = Tracker(10.0, 3), IssueLog(), SessionRecorder()
    rec.start(f"{OUT}/{name}.csv", {"sample": name, "scenario": "; ".join(faults) or "none"})
    log.start_csv(f"{OUT}/{name}_issues.csv")
    first_detect = None
    for n in range(1, CYCLES + 1):
        if n == FAULT_FROM:
            for f in faults:
                kit.write((f + "\n").encode())
        if n == FAULT_TO + 1:
            kit.write(b"FAULT CLEAR\n")
        kit.write(b"SCAN\n")
        pairs = {}
        while True:
            m = parse_line(kit.readline().decode())
            if isinstance(m, Data):
                tr.add(m); log.on_data(m); rec.write(m, "MATE")
            elif isinstance(m, Short):
                pairs[(m.pin_a, m.pin_b)] = m.microvolts
            elif isinstance(m, IsoDone):
                tr.end_isolation(m.cycle, pairs.keys()); log.on_isolation(m.cycle, pairs)
            elif isinstance(m, CycleEnd):
                break
        for p, st in tr.pins.items():
            if st.fail_cycle == n:
                log.on_fail(p, n, st.fail_reason)
        if faults and first_detect is None and log.events:
            first_detect = n
        rec.flush()
    rec.stop(); log.stop_csv()
    write_summary(f"{OUT}/{name}_summary.csv", tr, {"scenario": name})
    failed = {p: (st.fail_cycle, st.fail_reason) for p, st in tr.pins.items() if st.fail_cycle}
    print(f"\n== {name}  faults: {faults or 'none'}  (fault active cycles {FAULT_FROM}-{FAULT_TO})")
    print(f"   detected at cycle: {first_detect}   failed pins: {sorted(failed) or 'none'} at cycle {sorted(set(v[0] for v in failed.values())) or '-'}   events: {len(log.events)}")
    for e in log.events[:8]:
        print(f"   [{e.severity:8}] cycle {e.cycle:2}  {e.kind:14} pins {e.pins:10} {e.detail[:95]}")
    if "short" in name:
        g = [int(x) for x in faults[0].split()[-1].split("-")]
        b4 = {p: [v for c, v in zip(tr.pins[p].cycles, tr.pins[p].values) if c < FAULT_FROM] for p in g}
        du = {p: [v for c, v in zip(tr.pins[p].cycles, tr.pins[p].values) if FAULT_FROM <= c <= FAULT_TO] for p in g}
        print("   R before vs during short (first 4): " + ", ".join(
            f"pin {p} {sum(b4[p]) / len(b4[p]):.2f} -> {sum(du[p]) / len(du[p]):.2f} mOhm" for p in g[:4]))
