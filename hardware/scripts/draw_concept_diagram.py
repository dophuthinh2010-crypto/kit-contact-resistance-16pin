"""Redraws the hand concept sketch as a clean system block diagram (docs/concept_sketch.jpg)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.lines import Line2D

INK, MUTED, EDGE, FILL = "#1d2733", "#5b6776", "#2f4a6b", "#f3f6fa"
FORCE, SENSE, CTRL, DUT = "#b83227", "#1f6fb2", "#7a8694", "#d9822b"
plt.rcParams["font.family"] = "DejaVu Sans"

fig = plt.figure(figsize=(16, 10), dpi=150)
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 160); ax.set_ylim(0, 100); ax.axis("off")

def box(x, y, w, h, title, sub="", fill=FILL, edge=EDGE, tsize=12.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=1.2",
                                fc=fill, ec=edge, lw=1.6))
    cy = y + h / 2 + (1.6 if sub else 0)
    ax.text(x + w / 2, cy, title, ha="center", va="center", fontsize=tsize, fontweight="bold", color=INK)
    if sub:
        ax.text(x + w / 2, y + h / 2 - 2.4, sub, ha="center", va="center", fontsize=9.5, color=MUTED, linespacing=1.3)
    return dict(l=x, r=x + w, b=y, t=y + h, cx=x + w / 2, cy=y + h / 2)

def wire(pts, color, lw, dashed=False, arrow=True):
    xs, ys = zip(*pts)
    ax.add_line(Line2D(xs, ys, color=color, lw=lw, ls=(0, (5, 3)) if dashed else "-", solid_capstyle="round", zorder=1))
    if arrow:
        (x0, y0), (x1, y1) = pts[-2], pts[-1]
        ax.annotate("", xy=(x1, y1), xytext=(x0 + (x1 - x0) * 0.6, y0 + (y1 - y0) * 0.6),
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, mutation_scale=16), zorder=2)

def label(x, y, s, color=MUTED, size=9.5, ha="center", **kw):
    ax.text(x, y, s, ha=ha, va="center", fontsize=size, color=color, **kw)

# ---- title
ax.text(4, 96, "CR-TEST  ·  16-pin contact resistance test kit", fontsize=20, fontweight="bold", color=INK, va="center")
ax.text(4, 92.2, "System concept: 4-wire (Kelvin) resistance of every mated contact of an ITW McMurdo RP16-T / RS16P-T, "
                 "scanned once per plug/unplug cycle  (main board rev C)", fontsize=11, color=MUTED, va="center")

# ---- band 1: control and data
lap = box(6, 70, 26, 14, "Laptop", "CR-TEST desktop app\nCSV log · live charts · issues")
esp = box(54, 70, 30, 14, "ESP32-DevKitC", "scan sequencer\nserial protocol · calibration")
adc = box(108, 70, 24, 14, "ADS1115", "16-bit, differential ±0.256 V\nAIN0−1 contact · AIN2−3 shunt")
wire([(lap["r"], 77), (esp["l"], 77)], INK, 1.6, arrow=False)
label(43, 79.2, "USB serial  115200 Bd", INK, 9.5)
label(43, 74.8, "USB powers the ESP32 only", MUTED, 8.5)
wire([(adc["l"], 77), (esp["r"], 77)], SENSE, 1.6)
label(96, 79.2, "I²C", SENSE, 9.5)

# ---- band 2: test-current (force) path
y2, h2, w2 = 44, 13, 16
xs = [4, 25, 46, None, None, 118, 139]
psu = box(4, y2, w2, h2, "5 V / 2 A", "adapter → J1\nfuse · TVS")
rhi = box(25, y2, w2, h2, "Q_EN", "P-MOSFET\ncurrent on / off")
acs = box(46, y2, w2, h2, "LM317T", "+ R_SET 2.0 Ω\nconstant 0.625 A")
fem = box(68, y2 - 3, 17, h2 + 6, "Female jack", "RS16P-T\n16 contacts", fill="#fff4ea", edge=DUT)
mal = box(95, y2 - 3, 17, h2 + 6, "Male jack", "RP16-T\n16 contacts", fill="#fff4ea", edge=DUT)
fet = box(118, y2, w2, h2, "Q1 … Q16", "pin select\nAO3400A ×16")
rlo = box(139, y2, 17, h2, "R_SH → GND", "0.1 Ω shunt\ncurrent I")
for a, b in [(psu, rhi), (rhi, acs), (acs, fem)]:
    wire([(a["r"], a["cy"]), (b["l"], b["cy"])], FORCE, 3.2)
wire([(mal["r"], mal["cy"]), (fet["l"], fet["cy"])], FORCE, 3.2)
wire([(fet["r"], fet["cy"]), (rlo["l"], rlo["cy"])], FORCE, 3.2)
# mated contacts between the jacks
for i, yy in enumerate([47.5, 50.5, 53.5]):
    ax.add_line(Line2D([fem["r"], mal["l"]], [yy, yy], color=DUT, lw=2.4, zorder=1))
label((fem["r"] + mal["l"]) / 2, 61.6, "mated contact n", DUT, 9.5, fontweight="bold")
label((fem["r"] + mal["l"]) / 2, 42.6, "× 16", DUT, 9.5)
label(41.5, 59.6, "TEST CURRENT  0.625 A  (pulsed ≈40 ms per pin)", FORCE, 9.5, fontweight="bold")

# ---- band 3: Kelvin sense path
mux = box(68, 16, 44, 12, "Sense muxes  10 × CD4053BE", "two 16-to-1 trees: Kelvin taps of pin n on both jacks")
wire([(fem["cx"], fem["b"]), (fem["cx"], mux["t"])], SENSE, 1.6)
wire([(mal["cx"], mal["b"]), (mal["cx"], mux["t"])], SENSE, 1.6)
label(fem["cx"] - 1.5, 34.5, "sense F", SENSE, 9, ha="right")
label(mal["cx"] + 1.5, 34.5, "sense M", SENSE, 9, ha="left")
wire([(mux["r"], mux["cy"]), (115, mux["cy"]), (115, adc["b"])], SENSE, 1.6)
label(116.3, 33, "AIN0−AIN1\ncontact V", SENSE, 9, ha="left")
wire([(rlo["cx"], rlo["t"]), (rlo["cx"], 66), (128, 66), (128, adc["b"])], SENSE, 1.6)
label(129.3, 67.6, "AIN2−AIN3", SENSE, 9, ha="left")
ax.text(118, 20, "No amplifier:\nthe ADS1115 resolves\n7.8 µV = 0.0125 mΩ\nat 0.625 A", fontsize=9.5, color=MUTED, va="center", linespacing=1.35)

# ---- control lines from the ESP32 (dashed)
wire([(62, esp["b"]), (62, 64.8), (rhi["cx"], 64.8), (rhi["cx"], rhi["t"])], CTRL, 1.3, dashed=True)
label(34.5, 62.8, "I_EN", CTRL, 9, ha="left")
wire([(76, esp["b"]), (76, 63.6), (126, 63.6), (126, fet["t"])], CTRL, 1.3, dashed=True)
label(128.5, 59.6, "74HC595 ×2", CTRL, 9, ha="left")
wire([(66, esp["b"]), (66, 9), (90, 9), (90, mux["b"])], CTRL, 1.3, dashed=True)
label(67.5, 11, "mux select S0–S3", CTRL, 9, ha="left")
sw = box(4, 18, 22, 10, "Mate-detect switch", "counts one cycle per mating", tsize=11)
wire([(22.5, sw["t"]), (22.5, 68.8), (52, 68.8)], CTRL, 1.3, dashed=True, arrow=False)
wire([(52, 68.8), (52, 72.5), (esp["l"], 72.5)], CTRL, 1.3, dashed=True)
label(21.5, 36, "GPIO33", CTRL, 9, ha="right")

# ---- result formula and legend
ax.text(4, 5.5, "R(pin n) = (V_on − V_off) / I,   I = V_SH / 0.1 Ω    ·    up to ~400 mΩ    ·    fail limit 10 mΩ    ·    "
                "isolation test finds shorted pins", fontsize=10.5, color=INK)
lx, ly = 104, 6.2
for i, (c, lw, ds, txt) in enumerate([(FORCE, 3.2, False, "test current"), (SENSE, 1.6, False, "sense / analog"),
                                      (CTRL, 1.3, True, "control / digital"), (DUT, 2.4, False, "device under test")]):
    x = lx + i * 14 if i < 2 else lx + i * 14
    ax.add_line(Line2D([lx + (i % 2) * 28, lx + (i % 2) * 28 + 6], [ly - (i // 2) * 3.4] * 2,
                       color=c, lw=lw, ls=(0, (5, 3)) if ds else "-"))
    ax.text(lx + (i % 2) * 28 + 7.5, ly - (i // 2) * 3.4, txt, fontsize=9.5, color=MUTED, va="center")

fig.savefig("concept_sketch.png", facecolor="white")
fig.savefig("concept_sketch.jpg", facecolor="white", pil_kwargs={"quality": 92})
print("ok")
