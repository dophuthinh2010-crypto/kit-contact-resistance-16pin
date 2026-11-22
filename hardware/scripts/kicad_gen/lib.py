"""Symbols and footprints used by the CR-TEST boards (all embedded in the generated files)."""
from kgen import Fp, Pad, Sym

# ----------------------------------------------------------------------------- symbols
def two(name, ref, a="1", b="2", width=5.08, descr=""):
    return Sym(name, [("1", a)], [("2", b)], ref=ref, width=width, show_names=False, descr=descr)


S_R = two("R", "R")
S_C = two("C", "C")
S_CP = Sym("C_Polarized", [("1", "+")], [("2", "-")], ref="C", width=5.08)
S_D = Sym("D", [("1", "K")], [("2", "A")], ref="D", width=5.08)
S_LED = Sym("LED", [("2", "A")], [("1", "K")], ref="D", width=5.08)
S_FUSE = two("Polyfuse", "F")
S_TP = Sym("TestPoint", [("1", "TP")], [], ref="TP", width=5.08, show_names=False)
S_NMOS = Sym("NMOS_GSD", [("1", "G")], [("3", "D"), ("2", "S")], ref="Q", width=7.62)
S_PMOS = Sym("PMOS_GSD", [("1", "G")], [("3", "D"), ("2", "S")], ref="Q", width=7.62)
S_BAT54S = Sym("BAT54S", [("3", "SIG")], [("2", "K2 (to +3V3A)"), ("1", "A1 (to GND)")], ref="D", width=17.78)
S_ACS712 = Sym("ACS712", [("1", "IP+"), ("2", "IP+"), ("3", "IP-"), ("4", "IP-")],
               [("8", "VCC"), ("7", "VIOUT"), ("6", "FILTER"), ("5", "GND")], ref="U", width=12.7)
S_595 = Sym("74HC595", [("14", "SER"), ("11", "SRCLK"), ("12", "RCLK"), ("13", "~{OE}"), ("10", "~{SRCLR}"), None, ("16", "VCC"), ("8", "GND")],
            [("15", "QA"), ("1", "QB"), ("2", "QC"), ("3", "QD"), ("4", "QE"), ("5", "QF"), ("6", "QG"), ("7", "QH"), ("9", "QH'")],
            ref="U", width=12.7)
S_4067 = Sym("CD74HC4067", [("9", "I0"), ("8", "I1"), ("7", "I2"), ("6", "I3"), ("5", "I4"), ("4", "I5"), ("3", "I6"), ("2", "I7"),
                            ("23", "I8"), ("22", "I9"), ("21", "I10"), ("20", "I11"), ("19", "I12"), ("18", "I13"), ("17", "I14"), ("16", "I15")],
             [("1", "COM"), None, ("10", "S0"), ("11", "S1"), ("14", "S2"), ("13", "S3"), ("15", "~{E}"), None, ("24", "VCC"), ("12", "GND")],
             ref="U", width=12.7)
S_INA333 = Sym("INA333", [("3", "VIN+"), ("2", "VIN-"), ("1", "RG"), ("8", "RG")], [("7", "V+"), ("6", "VOUT"), ("5", "REF"), ("4", "V-")],
               ref="U", width=12.7)
S_OPA333 = Sym("OPA333", [("3", "+IN"), ("4", "-IN")], [("5", "V+"), ("1", "OUT"), ("2", "V-")], ref="U", width=10.16)
S_ADS1115 = Sym("ADS1115", [("4", "AIN0"), ("5", "AIN1"), ("6", "AIN2"), ("7", "AIN3"), ("1", "ADDR")],
                [("8", "VDD"), ("9", "SDA"), ("10", "SCL"), ("2", "ALERT/RDY"), ("3", "GND")], ref="U", width=15.24)
S_LDO = Sym("AP2112K-3.3", [("1", "VIN"), ("3", "EN")], [("5", "VOUT"), ("4", "NC"), ("2", "GND")], ref="U", width=12.7)
S_BARREL = Sym("Barrel_Jack_Switch", [], [("1", "TIP (+)"), ("2", "SLEEVE"), ("3", "SWITCH")], ref="J", width=12.7)


def header(name, n, ref="J", width=7.62):
    return Sym(name, [(str(i), str(i)) for i in range(1, n + 1)], [], ref=ref, width=width)


def header2(name, n, ref="J"):
    """2-row header: odd pins left, even right."""
    return Sym(name, [(str(2 * i - 1), str(2 * i - 1)) for i in range(1, n + 1)],
               [(str(2 * i), str(2 * i)) for i in range(1, n + 1)], ref=ref, width=7.62)


S_IDC34 = header2("Conn_02x17_IDC", 17)
S_JST2 = header("Conn_01x02_XH", 2)
S_H3 = header("Conn_01x03_Jumper", 3, ref="JP")
S_H4 = header("Conn_01x04", 4)
DEVKIT_L = ["3V3", "EN", "IO36/VP", "IO39/VN", "IO34", "IO35", "IO32", "IO33", "IO25", "IO26", "IO27", "IO14", "IO12", "GND", "IO13",
            "SD2/IO9", "SD3/IO10", "CMD/IO11", "5V"]
DEVKIT_R = ["GND", "IO23", "IO22", "TX/IO1", "RX/IO3", "IO21", "GND", "IO19", "IO18", "IO5", "IO17", "IO16", "IO4", "IO0", "IO2",
            "IO15", "SD1/IO8", "SD0/IO7", "CLK/IO6"]
S_DEVKIT = Sym("ESP32-DevKitC_V4", [(f"L{i + 1}", n) for i, n in enumerate(DEVKIT_L)], [(f"R{i + 1}", n) for i, n in enumerate(DEVKIT_R)],
               ref="U", width=20.32, descr="Espressif ESP32-DevKitC V4 on two 1x19 sockets, 25.4 mm apart")


def contacts(name, ref="J"):
    return Sym(name, [(str(i), f"C{i}") for i in range(1, 9)], [(str(i), f"C{i}") for i in range(9, 17)], ref=ref, width=10.16)


S_PLUG = contacts("McMurdo_RP16-T")
S_SOCKET = contacts("McMurdo_RS16P-T")


# ----------------------------------------------------------------------------- footprints
def smd2(name, px, sx, sy, body, descr=""):
    return Fp(name, [Pad("1", "smd", "roundrect", -px, 0, sx, sy), Pad("2", "smd", "roundrect", px, 0, sx, sy)],
              (-body[0] / 2, -body[1] / 2, body[0] / 2, body[1] / 2), descr=descr, pin1_mark=False)


F_0603 = smd2("R_0603_1608Metric", 0.825, 0.8, 0.95, (1.6, 0.8), "0603 resistor")
F_C0603 = smd2("C_0603_1608Metric", 0.775, 0.9, 0.95, (1.6, 0.8), "0603 capacitor")
F_0805 = smd2("C_0805_2012Metric", 0.95, 1.0, 1.45, (2.0, 1.25), "0805 capacitor")
F_LED0805 = Fp("LED_0805_2012Metric", [Pad("1", "smd", "roundrect", -0.9375, 0, 0.975, 1.4), Pad("2", "smd", "roundrect", 0.9375, 0, 0.975, 1.4)],
               (-1, -0.625, 1, 0.625), "0805 LED, pad 1 = cathode")
F_1812 = Fp("Fuse_1812_4532Metric", [Pad("1", "smd", "roundrect", -2.1, 0, 1.4, 3.4), Pad("2", "smd", "roundrect", 2.1, 0, 1.4, 3.4)],
            (-2.25, -1.6, 2.25, 1.6), "1812 polyfuse", pin1_mark=False)
F_SMB = Fp("D_SMB", [Pad("1", "smd", "roundrect", -2.15, 0, 2.5, 2.3), Pad("2", "smd", "roundrect", 2.15, 0, 2.5, 2.3)],
           (-2.25, -1.8, 2.25, 1.8), "DO-214AA (SMB), pad 1 = cathode")
F_SOD123 = Fp("D_SOD-123", [Pad("1", "smd", "roundrect", -1.65, 0, 0.9, 1.2), Pad("2", "smd", "roundrect", 1.65, 0, 0.9, 1.2)],
              (-1.4, -0.9, 1.4, 0.9), "SOD-123, pad 1 = cathode")
F_SOT23 = Fp("SOT-23", [Pad("1", "smd", "roundrect", -1.1375, -0.95, 1.325, 0.6), Pad("2", "smd", "roundrect", -1.1375, 0.95, 1.325, 0.6),
                        Pad("3", "smd", "roundrect", 1.1375, 0, 1.325, 0.6)], (-0.65, -1.45, 0.65, 1.45), "SOT-23-3")
F_SOT235 = Fp("SOT-23-5", [Pad("1", "smd", "roundrect", -1.1375, -0.95, 1.325, 0.6), Pad("2", "smd", "roundrect", -1.1375, 0, 1.325, 0.6),
                           Pad("3", "smd", "roundrect", -1.1375, 0.95, 1.325, 0.6), Pad("4", "smd", "roundrect", 1.1375, 0.95, 1.325, 0.6),
                           Pad("5", "smd", "roundrect", 1.1375, -0.95, 1.325, 0.6)], (-0.8, -1.45, 0.8, 1.45), "SOT-23-5")


def dual_row(name, n, pitch, px, sx, sy, body, descr):
    """SOIC-style: pins 1..n/2 down the left side, n/2+1..n up the right side."""
    h = n // 2
    pads = []
    for i in range(h):
        y = (i - (h - 1) / 2) * pitch
        pads.append(Pad(str(i + 1), "smd", "roundrect", -px, y, sx, sy))
        pads.append(Pad(str(n - i), "smd", "roundrect", px, y, sx, sy))
    return Fp(name, pads, (-body[0] / 2, -body[1] / 2, body[0] / 2, body[1] / 2), descr)


F_SOIC8 = dual_row("SOIC-8_3.9x4.9mm_P1.27mm", 8, 1.27, 2.475, 1.95, 0.6, (3.9, 4.9), "SOIC-8")
F_SOIC16 = dual_row("SOIC-16_3.9x9.9mm_P1.27mm", 16, 1.27, 2.475, 1.95, 0.6, (3.9, 9.9), "SOIC-16")
F_SOIC24W = dual_row("SOIC-24W_7.5x15.4mm_P1.27mm", 24, 1.27, 4.65, 2.0, 0.6, (7.5, 15.4), "SOIC-24 wide (CD74HC4067M96)")
F_VSSOP8 = dual_row("VSSOP-8_3.0x3.0mm_P0.65mm", 8, 0.65, 2.15, 1.3, 0.42, (3.0, 3.0), "VSSOP-8 (TI DGK)")
F_VSSOP10 = dual_row("VSSOP-10_3.0x3.0mm_P0.5mm", 10, 0.5, 2.15, 1.3, 0.3, (3.0, 3.0), "VSSOP-10 (TI DGS)")


def tht_row(name, n, pitch=2.54, drill=1.0, pad=1.7, body_w=2.54, descr=""):
    pads = [Pad(str(i + 1), "thru_hole", "rect" if i == 0 else "circle", 0, i * pitch, pad, pad, drill) for i in range(n)]
    return Fp(name, pads, (-body_w / 2, -pitch / 2, body_w / 2, (n - 0.5) * pitch), descr, through_hole=True)


F_H3 = tht_row("PinHeader_1x03_P2.54mm_Vertical", 3, descr="jumper header")
F_H4 = tht_row("PinHeader_1x04_P2.54mm_Vertical", 4, descr="I2C spare header")
F_JST2 = Fp("JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical",
            [Pad("1", "thru_hole", "rect", 0, 0, 1.7, 2.0, 0.95), Pad("2", "thru_hole", "oval", 2.5, 0, 1.7, 2.0, 0.95)],
            (-2.45, -2.35, 4.95, 3.4), "JST XH 2 pin", through_hole=True)
F_TP = Fp("TestPoint_THTPad_D2.0mm_Drill1.0mm", [Pad("1", "thru_hole", "circle", 0, 0, 2.0, 2.0, 1.0)], (-1, -1, 1, 1),
          "test point loop or probe pad", through_hole=True, pin1_mark=False)
F_CP8 = Fp("CP_Radial_D8.0mm_P3.50mm", [Pad("1", "thru_hole", "rect", 0, 0, 1.6, 1.6, 0.8), Pad("2", "thru_hole", "circle", 3.5, 0, 1.6, 1.6, 0.8)],
           (-2.25, -4, 5.75, 4), "8 mm radial electrolytic", through_hole=True)


def axial(name, pitch, drill, pad, body_l, body_w, descr):
    return Fp(name, [Pad("1", "thru_hole", "rect", 0, 0, pad, pad, drill), Pad("2", "thru_hole", "circle", pitch, 0, pad, pad, drill)],
              (pitch / 2 - body_l / 2, -body_w / 2, pitch / 2 + body_l / 2, body_w / 2), descr, through_hole=True, pin1_mark=False)


F_R10W = axial("R_Axial_SQP10_L48mm_P55.88mm", 55.88, 1.2, 2.4, 48.0, 10.0, "10 W cement wirewound (Yageo SQP10), mount 3 mm off the board")
F_R5W = axial("R_Axial_SQP5_L22mm_P27.94mm", 27.94, 1.0, 2.2, 22.0, 10.0, "5 W cement wirewound (Yageo SQP500)")
F_BARREL = Fp("BarrelJack_CUI_PJ-002A_Horizontal",
              [Pad("1", "thru_hole", "rect", 0, 0, 2.6, 2.6, 1.6), Pad("2", "thru_hole", "circle", -6.0, 0, 3.0, 3.0, 1.8),
               Pad("3", "thru_hole", "circle", -3.0, 4.7, 2.8, 2.8, 1.6)],
              (-13.7, -4.5, 0.7, 4.5), "CUI PJ-002A 5.5/2.1 mm. Check pads against the CUI drawing before ordering", through_hole=True)


def idc_2x17(name="IDC-Header_2x17_P2.54mm_Vertical"):
    """Box header, long axis along x: odd pins (force) on y=0, even pins (sense) on y=2.54. Column n = contact n."""
    pads = []
    for c in range(17):
        pads.append(Pad(str(2 * c + 1), "thru_hole", "rect" if c == 0 else "circle", c * 2.54, 0, 1.7, 1.7, 1.0))
        pads.append(Pad(str(2 * c + 2), "thru_hole", "circle", c * 2.54, 2.54, 1.7, 1.7, 1.0))
    L = 16 * 2.54
    return Fp(name, pads, (L / 2 - 50.8 / 2, 1.27 - 4.45, L / 2 + 50.8 / 2, 1.27 + 4.45), "2x17 IDC box header, key on the even row side",
              through_hole=True)


F_IDC34 = idc_2x17()


def devkit():
    pads = []
    for i in range(19):
        pads.append(Pad(f"L{i + 1}", "thru_hole", "rect" if i == 0 else "circle", 0, i * 2.54, 1.7, 1.7, 1.0))
        pads.append(Pad(f"R{i + 1}", "thru_hole", "circle", 25.4, i * 2.54, 1.7, 1.7, 1.0))
    return Fp("ESP32-DevKitC_V4_Socket_2x1x19_25.4mm", pads, (-1.3, -3, 26.7, 48.26 + 7), "two 1x19 female sockets, 25.4 mm apart, "
              "USB end at pin 19 (5V). Check against your DevKitC board", through_hole=True)


F_DEVKIT = devkit()


def mcmurdo(name, socket):
    pads = []
    for i in range(8):
        x = -16.45 + i * 4.70
        top, bot = (i + 9, i + 1) if socket else (i + 1, i + 9)
        pads.append(Pad(str(top), "thru_hole", "rect" if top == 1 else "circle", x, -4.57, 2.6, 2.6, 1.57))
        pads.append(Pad(str(bot), "thru_hole", "rect" if bot == 1 else "circle", x, 4.57, 2.6, 2.6, 1.57))
    pads.append(Pad("", "np_thru_hole", "circle", -26.985, 0, 3.3, 3.3, 3.3))
    pads.append(Pad("", "np_thru_hole", "circle", 26.985, 0, 3.3, 3.3, 3.3))
    return Fp(name, pads, (-31.495, -11.175, 31.495, 11.175), "ITW McMurdo Red Range, PC tail, 2x8 at 4.70 mm, rows 9.14 mm", through_hole=True)


F_PLUG = mcmurdo("McMurdo_RedRange_Plug_16way_RP16-T", False)
F_SOCKET = mcmurdo("McMurdo_RedRange_Socket_16way_RS16P-T", True)
F_MH = Fp("MountingHole_3.2mm_M3", [Pad("", "np_thru_hole", "circle", 0, 0, 3.2, 3.2, 3.2)], (-1.6, -1.6, 1.6, 1.6), "M3 mounting hole",
          through_hole=True, pin1_mark=False)

# ----------------------------------------------------------------------------- rev C parts
S_4053 = Sym("CD4053B", [("12", "AX"), ("13", "AY"), ("2", "BX"), ("1", "BY"), ("5", "CX"), ("3", "CY"), None, ("11", "A"), ("10", "B"), ("9", "C"), ("6", "INH")],
             [("14", "A COM"), ("15", "B COM"), ("4", "C COM"), None, ("16", "VDD"), ("7", "VEE"), ("8", "VSS")], ref="U", width=12.7,
             descr="Triple SPDT analog switch: control 0 = X, 1 = Y; INH high = all off")
S_LM317 = Sym("LM317T", [("3", "IN")], [("2", "OUT"), ("1", "ADJ")], ref="U", width=10.16,
              descr="Adjustable regulator, used as a constant-current source: I = 1.25 V / R_SET")


def dip(name, n, row=7.62, descr=""):
    h = n // 2
    pads = []
    for i in range(h):
        pads.append(Pad(str(i + 1), "thru_hole", "rect" if i == 0 else "oval", 0, i * 2.54, 1.6, 1.6, 0.8))
        pads.append(Pad(str(n - i), "thru_hole", "oval", row, i * 2.54, 1.6, 1.6, 0.8))
    L = (h - 1) * 2.54
    return Fp(name, pads, (0.8, -1.27, row - 0.8, L + 1.27), descr, through_hole=True)


F_DIP16 = dip("DIP-16_W7.62mm", 16, descr="DIP-16 300 mil (CD4053BE)")
F_TO220 = Fp("TO-220-3_Vertical_Heatsink", [Pad("1", "thru_hole", "rect", 0, 0, 1.9, 2.2, 1.2), Pad("2", "thru_hole", "oval", 2.54, 0, 1.9, 2.2, 1.2),
                                             Pad("3", "thru_hole", "oval", 5.08, 0, 1.9, 2.2, 1.2)],
             (-2.46, -3.2, 7.54, 12.0), "TO-220 vertical, area includes a clip-on heatsink behind the tab (about 10 x 13 mm)", through_hole=True)
F_2512 = Fp("R_2512_6332Metric_Shunt", [Pad("1", "smd", "roundrect", -3.1, 0, 1.6, 3.4), Pad("2", "smd", "roundrect", 3.1, 0, 1.6, 3.4)],
            (-3.15, -1.6, 3.15, 1.6), "2512 current shunt. Route the ADC taps from the inner edge of each pad (Kelvin)", pin1_mark=False)
F_R3W = axial("R_Axial_3W_L15.5mm_P20.32mm", 20.32, 1.0, 2.0, 15.5, 5.5, "3 W metal-oxide resistor, mount 2 mm off the board")
