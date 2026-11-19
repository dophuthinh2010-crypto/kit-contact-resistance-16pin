"""Tests for the parts of the app that don't need a screen or hardware.

Run from the desktop-app folder:   python -m unittest discover tests
"""
import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from crkit_app.protocol import parse_line, Hello, CycleStart, Zero, Data, CycleEnd, Ack, Error, Info  # noqa: E402
from crkit_app.analysis import Tracker  # noqa: E402
from crkit_app.recorder import SessionRecorder, load_session, write_summary  # noqa: E402
from crkit_app.simulator import SimulatedKit  # noqa: E402


class ProtocolTests(unittest.TestCase):
    def test_messages(self):
        self.assertEqual(parse_line("HELLO,CRKIT,0.1.0,101,42"), Hello("0.1.0", 101, 42))
        self.assertEqual(parse_line("CYCLE,43,MATE"), CycleStart(43, "MATE"))
        self.assertEqual(parse_line("ZERO,43,2.5012,4.987"), Zero(43, 2.5012, 4.987))
        self.assertEqual(parse_line("DATA,43,7,0.6201,1.8340,2.9577,OK"), Data(43, 7, 0.6201, 1.834, 2.9577, "OK"))
        self.assertEqual(parse_line("END,43,431"), CycleEnd(43, 431))
        self.assertEqual(parse_line("OK,scan"), Ack("SCAN"))
        self.assertEqual(parse_line("ERR,gain must be 11, 101 or 1001"), Error("gain must be 11, 101 or 1001"))
        self.assertEqual(parse_line("# hello"), Info("hello"))

    def test_min_field(self):
        d = parse_line("DATA,3,5,0.62,1.8,2.95,OK,2.871")
        self.assertEqual(d.r_min_mohm, 2.871)
        self.assertIsNone(parse_line("DATA,3,5,0.62,1.8,2.95,OK").r_min_mohm)

    def test_bad_lines(self):
        for bad in ["", "   ", "DATA,1,17,0.6,1,1,OK", "DATA,1,3,0.6,1,1,MAYBE", "DATA,x,3,0.6,1,1,OK", "garbage", "\x00\xff"]:
            self.assertIsNone(parse_line(bad), bad)

    def test_nan_reading(self):
        d = parse_line("DATA,5,2,0.0001,0.0000,nan,OPEN")
        self.assertTrue(math.isnan(d.r_mohm))
        self.assertEqual(d.flag, "OPEN")


class TrackerTests(unittest.TestCase):
    def test_fail_needs_three_in_a_row(self):
        t = Tracker(limit_mohm=10, consecutive=3)
        seq = [3, 11, 4, 11, 12, 13, 5]          # one spike, then three in a row from cycle 4
        for n, r in enumerate(seq, 1):
            t.add(Data(n, 1, 0.62, r * 0.62, r, "OK"))
        self.assertEqual(t.pins[1].fail_cycle, 6)
        self.assertEqual(t.status(1), "fail")
        self.assertEqual(t.pins[1].initial, 3)
        self.assertEqual(t.pins[1].maximum, 13)

    def test_open_and_over_count_as_above(self):
        t = Tracker(limit_mohm=10, consecutive=2)
        t.add(Data(1, 2, 0.0, 0.0, math.nan, "OPEN"))
        t.add(Data(2, 2, 0.62, 33.0, math.nan, "OVER"))
        self.assertEqual(t.pins[2].fail_cycle, 2)

    def test_recompute_after_limit_change(self):
        t = Tracker(limit_mohm=10, consecutive=3)
        for n in range(1, 6):
            t.add(Data(n, 3, 0.62, 5.0, 8.0, "OK"))
        self.assertIsNone(t.pins[3].fail_cycle)
        t.limit = 7.5
        t.recompute()
        self.assertEqual(t.pins[3].fail_cycle, 3)
        self.assertEqual(t.first_failure(), (3, 3))

    def test_average_minimum(self):
        t = Tracker()
        t.add(Data(1, 6, 0.62, 1.8, 3.0, "OK", 2.8))
        t.add(Data(2, 6, 0.62, 1.8, 3.2, "OK", 3.0))
        t.add(Data(3, 6, 0.0, 0.0, math.nan, "OPEN", None))     # not a valid scan: no minimum
        t.add(Data(4, 6, 0.62, 1.8, 3.1, "OK"))                 # older firmware: falls back to R
        self.assertAlmostEqual(t.pins[6].avg_min, (2.8 + 3.0 + 3.1) / 3)

    def test_wear_status(self):
        t = Tracker(limit_mohm=10)
        t.add(Data(1, 4, 0.62, 5, 8.0, "OK"))
        self.assertEqual(t.status(4), "wear")
        self.assertEqual(t.status(5), "none")


class RecorderTests(unittest.TestCase):
    def test_write_resume_and_summary(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "session.csv")
            rec = SessionRecorder()
            rec.start(path, {"sample": "RP16 #1", "operator": "T"})
            rec.write(Data(1, 1, 0.62, 1.8, 2.9, "OK"), "MATE")
            rec.write(Data(1, 2, 0.0, 0.0, math.nan, "OPEN"), "MATE")
            rec.stop()
            rec.start(path, {}, append=True)
            rec.write(Data(2, 1, 0.62, 1.9, 3.1, "OK"), "MATE")
            rec.stop()
            meta, rows = load_session(path)
            self.assertEqual(meta["sample"], "RP16 #1")
            self.assertEqual([r.cycle for r in rows], [1, 1, 2])
            self.assertTrue(math.isnan(rows[1].r_mohm))
            t = Tracker()
            for r in rows:
                t.add(r)
            out = os.path.join(d, "summary.csv")
            write_summary(out, t, meta)
            with open(out, encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("pin,first_mOhm", text)
            self.assertIn("1,2.900,3.100", text)


class SimulationRunTests(unittest.TestCase):
    def test_simrun(self):
        kit = SimulatedKit(); kit.auto = False
        kit.write(b"SIMRUN 5 20\n")
        data, done = [], False
        for _ in range(3000):
            m = parse_line(kit.readline().decode())
            if isinstance(m, Data):
                data.append(m)
            if m == Ack("SIMDONE"):
                done = True
                break
        self.assertTrue(done)
        self.assertEqual(len(data), 5 * 16)
        self.assertEqual(max(d.cycle for d in data), 5)
        self.assertTrue(all(d.r_min_mohm <= d.r_mohm + 1e-9 for d in data))


class SimulatorTests(unittest.TestCase):
    def read_until(self, kit, kind, limit=400):
        msgs = []
        for _ in range(limit):
            m = parse_line(kit.readline().decode())
            if m is not None:
                msgs.append(m)
                if isinstance(m, kind):
                    break
        return msgs

    def test_scan_produces_16_readings(self):
        kit = SimulatedKit()
        kit.auto = False
        self.assertIsInstance(self.read_until(kit, Hello)[-1], Hello)
        kit.write(b"SCAN\n")
        msgs = self.read_until(kit, CycleEnd)
        data = [m for m in msgs if isinstance(m, Data)]
        self.assertEqual(len(data), 16)
        self.assertEqual({d.pin for d in data}, set(range(1, 17)))
        self.assertTrue(all(1.5 < d.r_mohm < 6 for d in data), [d.r_mohm for d in data])
        self.assertTrue(all(abs(d.current_a - 0.625) < 0.05 for d in data))

    def test_commands(self):
        kit = SimulatedKit(); kit.auto = False
        self.read_until(kit, Hello)
        kit.write(b"SETCYCLE 499\n"); self.assertEqual(self.read_until(kit, Ack)[-1], Ack("SETCYCLE"))
        kit.write(b"SCAN\n")
        msgs = self.read_until(kit, CycleEnd)
        self.assertEqual(msgs[-1].cycle, 500)
        kit.write(b"GAIN 7\n"); self.assertIsInstance(self.read_until(kit, Error)[-1], Error)
        kit.write(b"CALZERO\n")
        msgs = self.read_until(kit, Ack)
        self.assertEqual(msgs[-1], Ack("CALZERO"))
        kit.write(b"MEASURE\n")
        data = [m for m in self.read_until(kit, CycleEnd) if isinstance(m, Data)]
        self.assertTrue(all(abs(d.r_mohm) < 3.5 for d in data))   # roughly zero after CALZERO
        self.assertEqual(data[0].cycle, 500)                     # MEASURE does not count


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------- fault scenarios
from crkit_app.protocol import Short, IsoDone, Alarm  # noqa: E402
from crkit_app.analysis import short_groups  # noqa: E402
from crkit_app.issues import IssueLog  # noqa: E402


def run_scan(kit):
    """One SCAN on the simulated kit: returns (data by pin, shorted pairs, iso count)."""
    kit.write(b"SCAN\n")
    data, pairs, iso = {}, {}, None
    for _ in range(4000):
        m = parse_line(kit.readline().decode())
        if isinstance(m, Data):
            data[m.pin] = m
        elif isinstance(m, Short):
            pairs[(m.pin_a, m.pin_b)] = m.microvolts
        elif isinstance(m, IsoDone):
            iso = m.pairs
        elif isinstance(m, CycleEnd):
            break
    return data, pairs, iso


def fresh_kit(*faults):
    kit = SimulatedKit(); kit.auto = False; kit.read_timeout = 0.005
    for f in faults:
        kit.write((f + "\n").encode())
    for _ in range(50):
        kit.readline()
    return kit


class FaultParsingTests(unittest.TestCase):
    def test_lines(self):
        self.assertEqual(parse_line("SHORT,7,5,4,880"), Short(7, 4, 5, 880.0))
        self.assertEqual(parse_line("ISO,7,0"), IsoDone(7, 0))
        a = parse_line("ALARM,7,OVERCURRENT,0.871 A on pin 3: test current switched off")
        self.assertEqual((a.code, a.detail), ("OVERCURRENT", "0.871 A on pin 3: test current switched off"))
        self.assertIsNone(parse_line("SHORT,7,4,4,10"))

    def test_groups(self):
        self.assertEqual(short_groups([(10, 11), (11, 12), (4, 5)]), [frozenset({4, 5}), frozenset({10, 11, 12})])


class ScenarioTests(unittest.TestCase):
    def test_no_fault_no_false_alarms(self):
        kit = fresh_kit()
        for _ in range(20):
            data, pairs, iso = run_scan(kit)
            self.assertEqual(iso, 0)
            self.assertTrue(all(d.flag == "OK" for d in data.values()))

    def test_one_pin_open(self):
        data, pairs, iso = run_scan(fresh_kit("FAULT OPEN 5"))
        self.assertEqual([p for p, d in data.items() if d.flag == "OPEN"], [5])
        self.assertTrue(math.isnan(data[5].r_mohm))
        self.assertEqual(iso, 0)

    def test_three_pins_open(self):
        data, pairs, iso = run_scan(fresh_kit("FAULT OPEN 2,9,14"))
        self.assertEqual(sorted(p for p, d in data.items() if d.flag == "OPEN"), [2, 9, 14])
        self.assertEqual(iso, 0)

    def test_two_pins_shorted(self):
        base, _, _ = run_scan(fresh_kit())
        data, pairs, iso = run_scan(fresh_kit("FAULT SHORT 4-5"))
        self.assertEqual(iso, 1)
        self.assertEqual(set(pairs), {(4, 5)})
        for p in (4, 5):                      # parallel contacts: roughly half the normal reading
            self.assertLess(data[p].r_mohm, 0.7 * base[p].r_mohm)
        self.assertTrue(all(d.flag == "OK" for d in data.values()))   # a short is NOT visible as a flag

    def test_three_pins_shorted(self):
        data, pairs, iso = run_scan(fresh_kit("FAULT SHORT 10-11-12"))
        self.assertEqual(iso, 3)
        self.assertEqual(short_groups(pairs), [frozenset({10, 11, 12})])

    def test_open_and_short_together(self):
        data, pairs, iso = run_scan(fresh_kit("FAULT OPEN 1", "FAULT SHORT 7-8"))
        self.assertEqual(data[1].flag, "OPEN")
        self.assertEqual(set(pairs), {(7, 8)})

    def test_tracker_fails_shorted_pins(self):
        kit = fresh_kit("FAULT SHORT 4-5")
        t = Tracker(consecutive=3)
        for _ in range(3):
            data, pairs, iso = run_scan(kit)
            for d in data.values():
                t.add(d)
            t.end_isolation(max(d.cycle for d in data.values()), pairs)
        self.assertEqual(t.status(4), "fail")
        self.assertIn("short with pin 5", t.pins[4].fail_reason)
        self.assertEqual(t.status(6), "ok")

    def test_all_sixteen_pins_shorted(self):
        kit = fresh_kit("FAULT SHORT " + "-".join(str(p) for p in range(1, 17)))
        data, pairs, iso = run_scan(kit)
        groups = short_groups(pairs)
        self.assertEqual(groups, [frozenset(range(1, 17))])          # one group with every pin
        self.assertTrue(all(d.flag == "LOW" for d in data.values()))  # and every reading is LOW
        t = Tracker(consecutive=3)
        for _ in range(3):
            data, pairs, iso = run_scan(kit)
            for d in data.values():
                t.add(d)
            t.end_isolation(max(d.cycle for d in data.values()), pairs)
        self.assertEqual(sorted(t.failed_pins()), list(range(1, 17)))

    def test_no_false_shorts_with_offsets(self):
        kit = fresh_kit()
        for _ in range(20):
            data, pairs, iso = run_scan(kit)
            self.assertEqual(pairs, {})
            self.assertTrue(all(d.flag == "OK" for d in data.values()))


class IssueLogTests(unittest.TestCase):
    def test_transitions_and_csv(self):
        with tempfile.TemporaryDirectory() as d:
            log = IssueLog()
            log.start_csv(os.path.join(d, "s_issues.csv"))
            log.on_data(Data(1, 5, 0.0, 0.0, math.nan, "OPEN"))
            log.on_data(Data(2, 5, 0.0, 0.0, math.nan, "OPEN"))      # still open: no new event
            log.on_data(Data(3, 5, 0.62, 1.8, 2.9, "OK"))             # cleared
            log.on_data(Data(3, 6, 0.62, 0.1, 0.18, "LOW"))           # below any real contact
            log.on_data(Data(4, 6, 0.62, 1.8, 2.9, "OK"))
            log.on_isolation(3, {(10, 11): 600.0, (11, 12): 580.0, (10, 12): 590.0})
            log.on_isolation(4, {(10, 11): 600.0, (11, 12): 580.0, (10, 12): 590.0})   # same group: no new event
            log.on_isolation(5, {})
            log.on_alarm(Alarm(6, "OVERCURRENT", "0.87 A"))
            log.stop_csv()
            kinds = [e.kind for e in log.events]
            self.assertEqual(kinds, ["OPEN", "OPEN cleared", "LOW", "LOW cleared", "SHORT", "SHORT cleared", "ALARM OVERCURRENT"])
            self.assertEqual(log.events[4].pins, "10, 11, 12")
            with open(os.path.join(d, "s_issues.csv"), encoding="utf-8") as fh:
                self.assertEqual(len(fh.read().strip().splitlines()), 8)
