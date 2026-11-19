"""CR-TEST main board, rev B: netlist, schematic layout and board placement.

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
REV, DATE = "B", "2026-11-19"
W, H = 135.0, 90.0
HOLES = [(4, 4), (96, 4), (3.5, 71), (131, 86)]

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
    "Rev B: reverse-polarity protection (ideal-diode P-MOSFET). Body diode conducts first, then the gate pulls it fully on.")
R("10k", "QREV_G", "GND", (24.5, 28.5, 90), B, note="Q_REV gate to GND")
add("D", "BZT52C5V1", S_D, F_SOD123, {"1": "VIN_P", "2": "QREV_G"}, (24.5, 33.5, 90), B, "Diodes BZT52C5V1", "Q_REV gate-source clamp")
add("F", "2A hold", S_FUSE, F_1812, {"1": "VIN_P", "2": "+5V"}, (20, 40, 0), B, "Bourns MF-MSMF200-2")
add("D", "SMBJ5.0A", S_D, F_SMB, {"1": "+5V", "2": "GND"}, (20, 45, 0), B, "Littelfuse SMBJ5.0A", "TVS on +5V")
add("C", "470u 10V", S_CP, F_CP8, {"1": "+5V", "2": "GND"}, (8, 52, 90), B, "Panasonic EEU-FR1A471")
add("U", "AP2112K-3.3", S_LDO, F_SOT235, {"1": "+5V", "3": "+5V", "5": "+3V3A", "2": "GND", "4": None}, (20, 51, 0), B,
    "Diodes AP2112K-3.3TRG1", "Analog 3.3 V rail")
C("1u", "+5V", "GND", (25, 48.6, 90), B, mpn="Samsung CL21 X7R", fp=F_0805)
C("10u", "+3V3A", "GND", (25, 53.8, 90), B, mpn="Samsung CL21 X5R", fp=F_0805)
add("TP", "GND", S_TP, F_TP, {"1": "GND"}, (8, 62, 0), B)

# ----------------------------------------------------------------------------- 2 current source
B = "2 Test current source"
add("Q", "2N7002", S_NMOS, F_SOT23, {"1": "I_EN", "3": "QEN_G", "2": "GND"}, (23, 18, 0), B, "2N7002", "Q_DRV")
R("100k", "I_EN", "GND", (27.5, 18, 90), B, note="current off while the ESP32 resets")
add("Q", "AO3401A", S_PMOS, F_SOT23, {"1": "QEN_G", "2": "+5V", "3": "I_HI"}, (14, 18, 0), B, "AOS AO3401A", "Q_EN, test current switch")
R("10k", "+5V", "QEN_G", (18.5, 18, 90), B, note="Q_EN off by default")
add("R", "5.6R 10W", S_R, F_R10W, {"1": "I_HI", "2": "ACS_IP"}, (10, 8, 0), B, "Yageo SQP10AJB-5R6",
    "R_HI. Rev B: 10 W (was 5 W). A force-to-GND short with hung firmware dissipates 4.46 W.")
add("U", "ACS712-05B", S_ACS712, F_SOIC8, {"1": "ACS_IP", "2": "ACS_IP", "3": "F_BUS", "4": "F_BUS", "8": "+5V", "7": "ACS_OUT",
                                          "6": "ACS_FILT", "5": "GND"}, (75, 9, 0), B, "Allegro ACS712ELCTR-05B-T")
C("100n", "+5V", "GND", (80.5, 7, 90), B)
C("1n", "ACS_FILT", "GND", (80.5, 11, 90), B)
R("1k", "ACS_OUT", "I_SENSE", (75, 14.5, 0), B)
clamp("I_SENSE", (80.5, 16, 0), B, "Rev B: keeps the ACS712 output inside the ADS1115 input range")
add("TP", "I_SENSE", S_TP, F_TP, {"1": "I_SENSE"}, (85, 9, 0), B)
add("R", "2.2R 5W", S_R, F_R5W, {"1": "LO_RTN", "2": "GND"}, (36, 19, 0), B, "Yageo SQP500JB-2R2", "R_LO, return to the J1 ground")

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
add("TP", "LO_RTN", S_TP, F_TP, {"1": "LO_RTN"}, (67, 24, 0), B)

# ----------------------------------------------------------------------------- 4 sense inputs
B = "4 Kelvin sense inputs (10k + clamp)"
for side, base in (("F", 11.5), ("M", 63.5)):
    for n in range(1, 17):
        R("10k", f"S{side}{n}", f"S{side}C{n}", (base + (17 - n) * 2.54, 72, 90), B,
          note="Rev B: 10 k (was 1 k), limits open-pin back-feed to 2.2 mA")
    for n in range(1, 17):
        r_, k = divmod(n - 1, 8)
        clamp(f"S{side}C{n}", (base + (7 - k) * 5.08 + 2.54, 60.5 + r_ * 5, 0), B)
R("3.3k", "+3V3A", "GND", (123, 66, 0), B, note="Rev B bleeder: absorbs clamp back-feed so +3V3A cannot rise")

# ----------------------------------------------------------------------------- 5 muxes + amplifier
B = "5 Sense muxes and amplifier"
ch_pins = ["9", "8", "7", "6", "5", "4", "3", "2", "23", "22", "21", "20", "19", "18", "17", "16"]
mux_common = {"10": "MUX_S0", "11": "MUX_S1", "14": "MUX_S2", "13": "MUX_S3", "15": "MUX_EN", "24": "+3V3A", "12": "GND"}
add("U", "CD74HC4067", S_4067, F_SOIC24W, dict(mux_common, **{"1": "SENSE_F", **{c: f"SFC{i + 1}" for i, c in enumerate(ch_pins)}}),
    (52, 51, 90), B, "TI CD74HC4067M96", "female (F_BUS) side taps")
add("U", "CD74HC4067", S_4067, F_SOIC24W, dict(mux_common, **{"1": "SENSE_M", **{c: f"SMC{i + 1}" for i, c in enumerate(ch_pins)}}),
    (80, 51, 90), B, "TI CD74HC4067M96", "male (switch) side taps")
C("100n", "+3V3A", "GND", (42, 51, 90), B)
C("100n", "+3V3A", "GND", (90.2, 51, 90), B)
R("10k", "+3V3A", "MUX_EN", (127, 66, 0), B, note="muxes off at boot")
add("U", "INA333", S_INA333, F_VSSOP8, {"3": "SENSE_F", "2": "SENSE_M", "1": "RG_A", "8": "RG_B", "7": "+3V3A", "6": "INA_OUT",
                                       "5": "INA_REF", "4": "GND"}, (66, 51, 0), B, "TI INA333AIDGKR")
C("100p C0G", "SENSE_F", "GND", (63.5, 45.5, 0), B, mpn="Samsung CL10 C0G")
C("100p C0G", "SENSE_M", "GND", (68.5, 45.5, 0), B, mpn="Samsung CL10 C0G")
C("10n", "SENSE_F", "SENSE_M", (66, 47.3, 0), B)
C("100n", "+3V3A", "GND", (70.8, 49, 90), B)
R("1.00k 0.1%", "RG_A", "RG1_SEL", (63.5, 54.8, 0), B, "Yageo RT0603BRD071KL", "gain 101")
R("10.0k 0.1%", "RG_A", "RG2_SEL", (68.5, 54.8, 0), B, "Yageo RT0603BRD0710KL", "gain 11")
add("JP", "Gain 101 | 11", S_H3, F_H3, {"1": "RG1_SEL", "2": "RG_B", "3": "RG2_SEL"}, (53.5, 59.5, 90), B, "2.54 mm header + jumper",
    "1-2 = G101 (send GAIN 101), 2-3 = G11 (GAIN 11)")
# REF buffer (rev B)
add("U", "OPA333", S_OPA333, F_SOT235, {"3": "REF_DIV", "4": "INA_REF", "1": "INA_REF", "5": "+3V3A", "2": "GND"}, (111, 61.5, 0), B,
    "TI OPA333AIDBVR", "Rev B: INA333 REF = 0.25 V so the output can show 0 mV and shorts of 3+ pins")
C("100n", "+3V3A", "GND", (115.5, 61.5, 90), B)
R("120k", "+3V3A", "REF_DIV", (119.5, 61.5, 0), B)
R("10k", "REF_DIV", "GND", (123.5, 61.5, 0), B)
C("100n", "REF_DIV", "GND", (127.5, 61.5, 0), B)
add("TP", "INA_REF", S_TP, F_TP, {"1": "INA_REF"}, (116.5, 83, 0), B)

# ----------------------------------------------------------------------------- 6 ADC
B = "6 ADC"
add("U", "ADS1115", S_ADS1115, F_VSSOP10, {"4": "I_SENSE", "5": "V_CONTACT", "6": "V5_HALF", "7": "INA_REF", "1": "GND", "8": "+3V3A",
                                          "9": "SDA", "10": "SCL", "2": "ADC_RDY", "3": "GND"}, (95.5, 49, 0), B, "TI ADS1115IDGSR",
    "I2C 0x48. AIN3 = INA333 REF (rev B)")
C("100n", "+3V3A", "GND", (95.5, 45.5, 0), B)
R("10k", "+3V3A", "ADC_RDY", (95.5, 43.5, 0), B)
R("1k", "INA_OUT", "V_CONTACT", (93, 53.5, 0), B)
C("100n", "V_CONTACT", "GND", (97, 53.5, 0), B)
R("4.7k", "+3V3A", "SDA", (93, 57, 0), B)
R("4.7k", "+3V3A", "SCL", (97, 57, 0), B)
R("10k", "+5V", "V5_HALF", (111, 66, 0), B)
R("10k", "V5_HALF", "GND", (115, 66, 0), B)
C("100n", "V5_HALF", "GND", (119, 66, 0), B)
add("TP", "V_CONTACT", S_TP, F_TP, {"1": "V_CONTACT"}, (119.5, 83, 0), B)

# ----------------------------------------------------------------------------- 7 MCU and I/O
B = "7 ESP32 and I/O"
gpio = {"IO23": "SR_DATA", "IO18": "SR_CLK", "IO5": "SR_LATCH", "IO19": "SR_OE", "IO25": "MUX_S0", "IO26": "MUX_S1", "IO27": "MUX_S2",
        "IO14": "MUX_S3", "IO13": "MUX_EN", "IO32": "I_EN", "IO21": "SDA", "IO22": "SCL", "IO4": "ADC_RDY", "IO33": "MATE_DET",
        "IO17": "LED_IO", "GND": "GND"}
dk = {}
for i, n in enumerate(DEVKIT_L):
    dk[f"L{i + 1}"] = gpio.get(n)
for i, n in enumerate(DEVKIT_R):
    dk[f"R{i + 1}"] = gpio.get(n)
add("U", "ESP32-DevKitC-32E", S_DEVKIT, F_DEVKIT, dk, (129.4, 54.72, 180), B, "Espressif ESP32-DevKitC-32E on 2x 1x19 sockets",
    "Powered from the laptop USB only: its 5V and 3V3 pins are NOT connected. Only GND is shared.")
R("10k", "+3V3A", "SR_OE", (111, 70.5, 0), B, note="all switches off at boot")
R("10k", "+3V3A", "MATE_DET", (115, 70.5, 0), B)
C("100n", "MATE_DET", "GND", (119, 70.5, 0), B, note="switch debounce")
R("1k", "LED_IO", "LED_A", (123, 70.5, 0), B)
add("D", "green", S_LED, F_LED0805, {"2": "LED_A", "1": "GND"}, (127, 70.5, 0), B, "0805 green LED")
add("J", "Mate switch", S_JST2, F_JST2, {"1": "MATE_DET", "2": "GND"}, (118.5, 76.5, 0), B, "JST B2B-XH-A", ref="J4")
add("J", "I2C spare", S_H4, F_H4, {"1": "+3V3A", "2": "GND", "3": "SDA", "4": "SCL"}, (131, 62, 0), B, "2.54 mm header", ref="J5")
add("TP", "F_BUS", S_TP, F_TP, {"1": "F_BUS"}, (122.5, 83, 0), B)

# ----------------------------------------------------------------------------- 8 ribbon connectors
B = "8 Ribbon connectors"
jf = {str(2 * n - 1): "F_BUS" for n in range(1, 17)}
jf.update({str(2 * n): f"SF{n}" for n in range(1, 17)})
jf.update({"33": None, "34": None})
add("J", "Female jack board", S_IDC34, F_IDC34, jf, (11.5 + 16 * 2.54, 82.54, 180), B, "Amphenol T821134A1S100CEU", ref="J2", note=
    "odd = force (all join F_BUS), even = sense n. Rev B: 33/34 not connected")
jm = {str(2 * n - 1): f"MF{n}" for n in range(1, 17)}
jm.update({str(2 * n): f"SM{n}" for n in range(1, 17)})
jm.update({"33": None, "34": None})
add("J", "Male jack board", S_IDC34, F_IDC34, jm, (63.5 + 16 * 2.54, 82.54, 180), B, "Amphenol T821134A1S100CEU", ref="J3", note=
    "odd = force n (to Qn), even = sense n. Rev B: 33/34 not connected")

# ----------------------------------------------------------------------------- schematic placement
BLOCKS = [
    dict(name="1 Power input", rect=(15, 15, 215, 200), cols=2,
         text="Rev B: Q_REV reverse-polarity MOSFET. ESP32 gets power from USB only."),
    dict(name="2 Test current source", rect=(220, 15, 420, 200), cols=2, text="I = 5 V / (5.6 + 2.2 + ~0.18 ohm) = 0.627 A"),
    dict(name="6 ADC", rect=(425, 15, 625, 200), cols=2, text="ADS1115 @ 0x48: AIN0 I, AIN1 V, AIN2 5V/2, AIN3 REF"),
    dict(name="7 ESP32 and I/O", rect=(630, 15, 826, 200), cols=2, text="GPIO map as docs/design.md"),
    dict(name="3 Pin select (16 low-side switches)", rect=(15, 205, 330, 579), cols=4, text="Qn on = contact n carries the test current"),
    dict(name="4 Kelvin sense inputs (10k + clamp)", rect=(335, 205, 615, 579), cols=4, text="Rev B: 10 k series, 3.3 k bleeder"),
    dict(name="5 Sense muxes and amplifier", rect=(620, 205, 826, 470), cols=2, text="Rev B: REF = 0.25 V via OPA333, also on AIN3"),
    dict(name="8 Ribbon connectors", rect=(620, 475, 826, 579), cols=2, text="34-way IDC to the jack boards"),
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
                         ["4-wire Kelvin measurement, 0.627 A, INA333 + ADS1115, ESP32-DevKitC",
                          "Generated by hardware/scripts/kicad_gen/main_board.py (edit the script, then regenerate)",
                          "Rev B changes: see docs/fault-protection.md"])
    holes = HOLES
    zones = [dict(net="GND", layer="B.Cu", pts=[(0.5, 0.5), (W - 0.5, 0.5), (W - 0.5, H - 0.5), (0.5, H - 0.5)]),
             dict(net="GND", layer="F.Cu", pts=[(0.5, 0.5), (W - 0.5, 0.5), (W - 0.5, H - 0.5), (0.5, H - 0.5)])]
    texts = [(84, 3.2, "CR-TEST main board rev B", 1.2), (12, 86.6, "J2: FEMALE jack board (pin 1 right)", 0.9),
             (64, 86.6, "J3: MALE jack board (pin 1 right)", 0.9), (104, 1.8, "ESP32-DevKitC: USB power only", 0.9)]
    pcb = os.path.join(OUT, PROJECT + ".kicad_pcb")
    netno = kgen.write_board(pcb, PROJECT, parts, (W, H), holes=holes, zones=zones, texts=texts,
                             title="CR-TEST main board", rev=REV, date=DATE)
    power = ["F_BUS", "LO_RTN", "I_HI", "ACS_IP", "+5V", "VIN_RAW", "VIN_P", "GND"] + [f"MF{n}" for n in range(1, 17)]
    sense = [f"S{s}{n}" for s in "FM" for n in range(1, 17)] + [f"S{s}C{n}" for s in "FM" for n in range(1, 17)] + ["SENSE_F", "SENSE_M"]
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
