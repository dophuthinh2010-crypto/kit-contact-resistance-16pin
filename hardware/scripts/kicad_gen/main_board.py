"""CR-TEST main board, rev C: netlist, schematic layout and board placement.

Run:  python main_board.py   (writes hardware/kicad/crkit_main/)
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import kgen  # noqa: E402
from kgen import Part  # noqa: E402
from lib import *  # noqa: E402,F401,F403

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "kicad", "crkit_main")
PROJECT = "crkit_main"
REV, DATE = "C", "2026-11-23"
W, H = 135.0, 101.0
HOLES = [(4, 4), (96, 4), (3.5, 84), (131, 97)]

parts = []
counters = defaultdict(int)


def add(prefix, value, sym, fp, nets, pcb, block, mpn="", note="", ref=None):
    if ref is None:
        counters[prefix] += 1
        ref = f"{prefix}{counters[prefix]}"
    p = Part(ref, value, sym, fp, dict(nets), mpn=mpn, note=note, block=block, pcb=pcb)
    parts.append(p)
    return p


def R(value, a, b, pcb, block, mpn="", note="", fp=F_0603):
    return add("R", value, S_R, fp, {"1": a, "2": b}, pcb, block, mpn or "UNI-ROYAL 0603WAF", note)


def C(value, a, b, pcb, block, mpn="Samsung CL10 X7R", note="", fp=F_C0603):
    return add("C", value, S_C, fp, {"1": a, "2": b}, pcb, block, mpn, note)


def clamp(sig, pcb, block, note=""):
    return add("D", "BAT54S", S_BAT54S, F_SOT23, {"3": sig, "2": "+3V3A", "1": "GND"}, pcb, block, "Nexperia BAT54S", note)


# ----------------------------------------------------------------------------- 1 power input
B = "1 Power input"
add("J", "5V 2A barrel", S_BARREL, F_BARREL, {"1": "VIN_RAW", "2": "GND", "3": "GND"}, (14, 32, 0), B, "CUI PJ-002A", ref="J1")
add("Q", "AO3401A", S_PMOS, F_SOT23, {"1": "QREV_G", "3": "VIN_RAW", "2": "VIN_P"}, (19.5, 30, 0), B, "AOS AO3401A",
    "Reverse-polarity protection (ideal-diode P-MOSFET). Body diode conducts first, then the gate pulls it fully on.")
R("10k", "QREV_G", "GND", (24.5, 28.5, 90), B, note="Q_REV gate to GND")
add("D", "BZT52C5V1", S_D, F_SOD123, {"1": "VIN_P", "2": "QREV_G"}, (24.5, 33.5, 90), B, "Diodes BZT52C5V1", "Q_REV gate-source clamp")
add("F", "2A hold", S_FUSE, F_1812, {"1": "VIN_P", "2": "+5V"}, (20, 40, 0), B, "Bourns MF-MSMF200-2")
add("D", "SMBJ5.0A", S_D, F_SMB, {"1": "+5V", "2": "GND"}, (20, 45, 0), B, "Littelfuse SMBJ5.0A", "TVS on +5V")
add("C", "470u 10V", S_CP, F_CP8, {"1": "+5V", "2": "GND"}, (8, 52, 90), B, "Panasonic EEU-FR1A471")
add("U", "AP2112K-3.3", S_LDO, F_SOT235, {"1": "+5V", "3": "+5V", "5": "+3V3A", "2": "GND", "4": None}, (20, 51, 0), B,
    "Diodes AP2112K-3.3TRG1", "Analog 3.3 V rail")
C("1u", "+5V", "GND", (25, 48.6, 90), B, mpn="Samsung CL21 X7R", fp=F_0805)
C("10u", "+3V3A", "GND", (25, 53.8, 90), B, mpn="Samsung CL21 X5R", fp=F_0805)

# ----------------------------------------------------------------------------- 2 current source
B = "2 Test current source (LM317T)"
add("Q", "2N7002", S_NMOS, F_SOT23, {"1": "I_EN", "3": "QEN_G", "2": "GND"}, (23, 18, 0), B, "2N7002", "Q_DRV")
R("100k", "I_EN", "GND", (27.5, 18, 90), B, note="current off while the ESP32 resets")
add("Q", "AO3401A", S_PMOS, F_SOT23, {"1": "QEN_G", "2": "+5V", "3": "LM_IN"}, (14, 18, 0), B, "AOS AO3401A", "Q_EN, test current switch")
R("10k", "+5V", "QEN_G", (18.5, 18, 90), B, note="Q_EN off by default")
C("10u", "LM_IN", "GND", (31.5, 5, 0), B, mpn="Samsung CL21 X5R", fp=F_0805)
C("100n", "LM_IN", "GND", (36, 5, 0), B)
add("U", "LM317T", S_LM317, F_TO220, {"3": "LM_IN", "2": "LM_OUT", "1": "F_BUS"}, (32, 12, 0), B, "TI LM317T (TO-220) + clip-on heatsink",
    "Rev C: constant-current source. I = 1.25 V / 2.0 ohm = 0.625 A into F_BUS, whatever the contact. Needs about 3.5 V of the 5 V.")
add("R", "2.0R 3W 1%", S_R, F_R3W, {"1": "LM_OUT", "2": "F_BUS"}, (44, 12, 0), B, "Vishay PR03000202008JAC00 (or any 2.0 ohm 3 W)",
    "R_SET: sets the test current. 0.78 W in normal use")
add("R", "0.1R 1% 2512", S_R, F_2512, {"1": "LO_RTN", "2": "GND"}, (64, 20, 0), B, "Yageo PE2512FKF070R1L",
    "R_SH: current shunt, read by ADS1115 AIN2-AIN3 (Kelvin taps)")
add("TP", "LO_RTN", S_TP, F_TP, {"1": "LO_RTN"}, (55, 20, 0), B)

# ----------------------------------------------------------------------------- 3 pin select
B = "3 Pin select (16 low-side switches)"
for n in range(1, 17):
    r_, k = divmod(n - 1, 8)
    x, y = 36 + k * 8, 29 + r_ * 9
    add("Q", "AO3400A", S_NMOS, F_SOT23, {"1": f"G{n}", "3": f"MF{n}", "2": "LO_RTN"}, (x, y, 0), B, "AOS AO3400A", f"switch for contact {n}")
    R("100", f"GR{n}", f"G{n}", (x - 3.6, y, 90), B)
    R("100k", f"G{n}", "GND", (x, y + 3.6, 0), B)
sr_common = {"11": "SR_CLK", "12": "SR_LATCH", "13": "SR_OE", "10": "+3V3A", "16": "+3V3A", "8": "GND"}
outs = ["15", "1", "2", "3", "4", "5", "6", "7"]
add("U", "74HC595", S_595, F_SOIC16, dict(sr_common, **{"14": "SR_DATA", "9": "SR_CHAIN", **{o: f"GR{i + 1}" for i, o in enumerate(outs)}}),
    (75, 22, 90), B, "TI SN74HC595DR")
add("U", "74HC595", S_595, F_SOIC16, dict(sr_common, **{"14": "SR_CHAIN", "9": None, **{o: f"GR{i + 9}" for i, o in enumerate(outs)}}),
    (89, 22, 90), B, "TI SN74HC595DR")
C("100n", "+3V3A", "GND", (82, 22, 90), B)
C("100n", "+3V3A", "GND", (96, 22, 90), B)

# ----------------------------------------------------------------------------- 4 sense inputs
B = "4 Kelvin sense inputs (10k)"
for side, base in (("F", 11.5), ("M", 63.5)):
    for n in range(1, 17):
        R("10k", f"S{side}{n}", f"S{side}C{n}", (base + (17 - n) * 2.54, 85, 90), B,
          note="protects the CD4053B inputs; open-pin back-feed under 0.1 mA")
R("3.3k", "+3V3A", "GND", (40, 47, 0), B, note="bleeder: +3V3A cannot be pushed up by back-feed")

# ----------------------------------------------------------------------------- 5 sense muxes (CD4053B trees)
B = "5 Sense muxes (10x CD4053BE, two 16-to-1 trees)"
SECT = [("12", "13", "14", "11"), ("2", "1", "15", "10"), ("5", "3", "4", "9")]   # X, Y, COM, control per section A, B, C


def tree(side, out):
    """15 SPDT switches: 8 at level 1 (S0), 4 at level 2 (S1), 2 at level 3 (S2), 1 at level 4 (S3)."""
    sw = []
    for k in range(8):
        sw.append((f"S{side}C{2 * k + 1}", f"S{side}C{2 * k + 2}", f"{side}_L1_{k}", "MUX_S0"))
    for j in range(4):
        sw.append((f"{side}_L1_{2 * j}", f"{side}_L1_{2 * j + 1}", f"{side}_L2_{j}", "MUX_S1"))
    for i in range(2):
        sw.append((f"{side}_L2_{2 * i}", f"{side}_L2_{2 * i + 1}", f"{side}_L3_{i}", "MUX_S2"))
    sw.append((f"{side}_L3_0", f"{side}_L3_1", out, "MUX_S3"))
    return sw


for t, (side, out) in enumerate((("F", "SENSE_F"), ("M", "SENSE_M"))):
    sw = tree(side, out)
    for c in range(5):
        nets = {"6": "MUX_EN", "7": "GND", "8": "GND", "16": "+3V3A"}
        for s_i, (x_, y_, com, ctl) in enumerate(sw[3 * c:3 * c + 3]):
            px, py, pc, pk = SECT[s_i]
            nets.update({px: x_, py: y_, pc: com, pk: ctl})
        k = t * 5 + c
        x0 = 5.2 + 12.5 * k
        add("U", "CD4053BE", S_4053, F_DIP16, nets, (x0, 61, 0), B, "TI CD4053BE",
            f"{'female' if side == 'F' else 'male'} side tree, chip {c + 1} of 5")
        C("100n", "+3V3A", "GND", (x0 + 10.06, 62.5, 90), B)
R("10k", "+3V3A", "MUX_EN", (32, 47, 0), B, note="INH high: all switches off at boot")

# ----------------------------------------------------------------------------- 6 ADC
B = "6 ADC (ADS1115, differential)"
add("U", "ADS1115", S_ADS1115, F_VSSOP10, {"4": "ADS_F", "5": "ADS_M", "6": "SH_P", "7": "SH_N", "1": "GND", "8": "+3V3A",
                                          "9": "SDA", "10": "SCL", "2": "ADC_RDY", "3": "GND"}, (66, 51, 0), B, "TI ADS1115IDGSR",
    "I2C 0x48. AIN0-AIN1 = contact voltage at PGA +-0.256 V (7.8 uV/step). AIN2-AIN3 = shunt voltage")
R("1k", "SENSE_F", "ADS_F", (58.5, 49.5, 0), B)
R("1k", "SENSE_M", "ADS_M", (58.5, 52.5, 0), B)
C("100n", "ADS_F", "ADS_M", (54.5, 51, 90), B, note="differential filter, 2 k x 100 nF")
clamp("ADS_F", (50, 48.5, 0), B)
clamp("ADS_M", (50, 53.5, 0), B)
R("1k", "LO_RTN", "SH_P", (73.5, 49.5, 0), B, note="Kelvin tap at the R_SH LO_RTN pad")
R("1k", "GND", "SH_N", (73.5, 52.5, 0), B, note="Kelvin tap at the R_SH GND pad: route it as its own trace")
C("100n", "SH_P", "SH_N", (77.5, 51, 90), B)
C("100n", "+3V3A", "GND", (62, 46.5, 0), B)
R("10k", "+3V3A", "ADC_RDY", (70, 46.5, 0), B)
R("4.7k", "+3V3A", "SDA", (62, 55.5, 0), B)
R("4.7k", "+3V3A", "SCL", (66, 55.5, 0), B)
R("10k", "+5V", "V5_MON", (70, 55.5, 0), B, note="5 V supply monitor, read by ESP32 IO34")
R("10k", "V5_MON", "GND", (74, 55.5, 0), B)
C("100n", "V5_MON", "GND", (78, 55.5, 0), B)
for i, (tp, xy) in enumerate((("GND", (44, 47)), ("F_BUS", (44, 51)), ("SENSE_F", (40, 55.5)), ("SENSE_M", (44, 55.5)), ("V5_MON", (82, 51)))):
    add("TP", tp, S_TP, F_TP, {"1": tp}, (xy[0], xy[1], 0), B)

# ----------------------------------------------------------------------------- 7 MCU and I/O
B = "7 ESP32 and I/O"
gpio = {"IO23": "SR_DATA", "IO18": "SR_CLK", "IO5": "SR_LATCH", "IO19": "SR_OE", "IO25": "MUX_S0", "IO26": "MUX_S1", "IO27": "MUX_S2",
        "IO14": "MUX_S3", "IO13": "MUX_EN", "IO32": "I_EN", "IO21": "SDA", "IO22": "SCL", "IO4": "ADC_RDY", "IO33": "MATE_DET",
        "IO17": "LED_IO", "IO34": "V5_MON", "GND": "GND"}
dk = {}
for i, n in enumerate(DEVKIT_L):
    dk[f"L{i + 1}"] = gpio.get(n)
for i, n in enumerate(DEVKIT_R):
    dk[f"R{i + 1}"] = gpio.get(n)
add("U", "ESP32-DevKitC-32E", S_DEVKIT, F_DEVKIT, dk, (129.4, 54.72, 180), B, "Espressif ESP32-DevKitC-32E on 2x 1x19 sockets",
    "Powered from the laptop USB only: its 5V and 3V3 pins are NOT connected. Only GND is shared.")
R("10k", "+3V3A", "SR_OE", (36, 47, 0), B, note="all switches off at boot")
R("10k", "+3V3A", "MATE_DET", (32, 51, 0), B)
C("100n", "MATE_DET", "GND", (36, 51, 0), B, note="switch debounce")
R("1k", "LED_IO", "LED_A", (123, 86, 0), B)
add("D", "green", S_LED, F_LED0805, {"2": "LED_A", "1": "GND"}, (127, 86, 0), B, "0805 green LED")
add("J", "Mate switch", S_JST2, F_JST2, {"1": "MATE_DET", "2": "GND"}, (113.5, 93, 0), B, "JST B2B-XH-A", ref="J4")
add("J", "I2C spare", S_H4, F_H4, {"1": "+3V3A", "2": "GND", "3": "SDA", "4": "SCL"}, (131.5, 80, 0), B, "2.54 mm header", ref="J5")

# ----------------------------------------------------------------------------- 8 ribbon connectors
B = "8 Ribbon connectors"
jf = {str(2 * n - 1): "F_BUS" for n in range(1, 17)}
jf.update({str(2 * n): f"SF{n}" for n in range(1, 17)})
jf.update({"33": None, "34": None})
add("J", "Female jack board", S_IDC34, F_IDC34, jf, (11.5 + 16 * 2.54, 95.54, 180), B, "Amphenol T821134A1S100CEU", ref="J2", note=
    "odd = force (all join F_BUS), even = sense n. 33/34 not connected")
jm = {str(2 * n - 1): f"MF{n}" for n in range(1, 17)}
jm.update({str(2 * n): f"SM{n}" for n in range(1, 17)})
jm.update({"33": None, "34": None})
add("J", "Male jack board", S_IDC34, F_IDC34, jm, (63.5 + 16 * 2.54, 95.54, 180), B, "Amphenol T821134A1S100CEU", ref="J3", note=
    "odd = force n (to Qn), even = sense n. 33/34 not connected")

# ----------------------------------------------------------------------------- schematic placement
BLOCKS = [
    dict(name="1 Power input", rect=(15, 15, 215, 200), cols=2,
         text="Q1 reverse-polarity MOSFET. ESP32 gets power from USB only."),
    dict(name="2 Test current source (LM317T)", rect=(220, 15, 420, 200), cols=2, text="I = 1.25 V / R_SET 2.0 ohm = 0.625 A, measured on R_SH"),
    dict(name="6 ADC (ADS1115, differential)", rect=(425, 15, 625, 200), cols=2, text="AIN0-1 contact (PGA 0.256 V), AIN2-3 shunt. 5 V on IO34"),
    dict(name="7 ESP32 and I/O", rect=(630, 15, 826, 200), cols=2, text="GPIO map as docs/design.md"),
    dict(name="3 Pin select (16 low-side switches)", rect=(15, 205, 270, 579), cols=3, text="Qn on = contact n carries the test current"),
    dict(name="4 Kelvin sense inputs (10k)", rect=(275, 205, 420, 420), cols=2, text="10 k series into the muxes"),
    dict(name="8 Ribbon connectors", rect=(275, 425, 420, 579), cols=2, text="34-way IDC to the jack boards"),
    dict(name="5 Sense muxes (10x CD4053BE, two 16-to-1 trees)", rect=(425, 205, 826, 579), cols=4,
         text="Level 1 S0, level 2 S1, level 3 S2, level 4 S3. Channel n = binary n-1, INH = MUX_EN"),
]


def place_schematic():
    by_block = defaultdict(list)
    for p in parts:
        by_block[p.block].append(p)
    for b in BLOCKS:
        x1, y1, x2, y2 = b["rect"]
        cw = (x2 - x1) / b["cols"]
        ps = by_block[b["name"]]
        col, y = 0, y1 + 16
        for p in ps:
            h = p.sym.height + 5.08
            if y + h > y2 - 3 and y > y1 + 16:
                col, y = col + 1, y1 + 16
            if col >= b["cols"]:
                raise SystemExit(f"block {b['name']} too small")
            p.sch = (x1 + cw * (col + 0.5), y + h / 2)
            y += h


def main():
    os.makedirs(OUT, exist_ok=True)
    place_schematic()
    bad = kgen.overlaps(parts)
    if bad:
        print("COURTYARD OVERLAPS:", bad)
    for p in parts:
        x1, y1, x2, y2 = kgen.placed_courtyard(p, 0, 0)
        if x1 < 0.3 or y1 < -8 or x2 > W - 0.3 or y2 > H - 0.3:
            print("near/over edge:", p.ref, round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2))
    sch = os.path.join(OUT, PROJECT + ".kicad_sch")
    kgen.write_schematic(sch, PROJECT, parts, BLOCKS, "CR-TEST main board (16-pin contact resistance)", REV, DATE,
                         ["4-wire Kelvin: LM317T 0.625 A source, 2x CD4053B mux trees, ADS1115 differential, ESP32-DevKitC",
                          "Generated by hardware/scripts/kicad_gen/main_board.py (edit the script, then regenerate)",
                          "Rev C: LM317T current source, CD4053BE muxes, no INA333/ACS712. See hardware/kicad/README.md"])
    holes = HOLES
    zones = [dict(net="GND", layer="B.Cu", pts=[(0.5, 0.5), (W - 0.5, 0.5), (W - 0.5, H - 0.5), (0.5, H - 0.5)]),
             dict(net="GND", layer="F.Cu", pts=[(0.5, 0.5), (W - 0.5, 0.5), (W - 0.5, H - 0.5), (0.5, H - 0.5)])]
    texts = [(66, 3.2, "CR-TEST main board rev C", 1.2), (12, 99.6, "J2: FEMALE jack board (pin 1 right)", 0.9),
             (64, 99.6, "J3: MALE jack board (pin 1 right)", 0.9), (104, 1.8, "ESP32-DevKitC: USB power only", 0.9)]
    pcb = os.path.join(OUT, PROJECT + ".kicad_pcb")
    netno = kgen.write_board(pcb, PROJECT, parts, (W, H), holes=holes, zones=zones, texts=texts,
                             title="CR-TEST main board", rev=REV, date=DATE)
    power = ["F_BUS", "LO_RTN", "LM_IN", "LM_OUT", "+5V", "VIN_RAW", "VIN_P", "GND"] + [f"MF{n}" for n in range(1, 17)]
    sense = [f"S{s}{n}" for s in "FM" for n in range(1, 17)] + [f"S{s}C{n}" for s in "FM" for n in range(1, 17)] + ["SENSE_F", "SENSE_M", "ADS_F", "ADS_M", "SH_P", "SH_N"] + [f"{s}_L{l}_{i}" for s in "FM" for l, n in ((1, 8), (2, 4), (3, 2)) for i in range(n)]
    kgen.write_project(os.path.join(OUT, PROJECT + ".kicad_pro"), PROJECT,
                       [dict(name="Power", track_width=1.0, clearance=0.3, via_diameter=1.0, via_drill=0.5),
                        dict(name="Sense", track_width=0.25, clearance=0.2)],
                       [(n, "Power") for n in power] + [(n, "Sense") for n in sense])
    for path in (sch, pcb):
        kgen.check_sexpr(path)
    print(f"{len(parts)} parts, {len(netno)} nets -> {OUT}")
    return parts


if __name__ == "__main__":
    main()
