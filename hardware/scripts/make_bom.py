"""Writes hardware/BOM.xlsx and hardware/BOM.csv from the CR-TEST Kit BOM sheet (revision 6, board rev C)."""
import csv
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

HEAD = ["Group", "Ref", "Part / function", "Model (manufacturer part no.)", "Qty", "Unit price", "Line total",
        "Supplier", "Alternative part", "Price basis", "Notes"]
R = [
 ["Device under test", "J_JACK (male)", "Rack & panel plug, 16 way, PC tail", "ITW McMurdo RP16-T", 1, 20, "Farnell / element14", "DRP116-T (same plug, DAP body); RPD16 if you need guide dowels", "Quoted", "Price is for the RP16 solder version ($19.73–21.25). element14 shows RP16 as 'No longer stocked': check availability first."],
 ["Device under test", "J_JACK (female)", "Rack & panel socket, 16 way, PC tail", "ITW McMurdo RS16P-T", 1, 20, "Farnell / element14", "DRS116P-T (DAP body); RSD16 for guide dowels", "Estimate", "Assumed similar to the plug. RS16 also shows 'No longer stocked' at element14."],
 ["Main board", "U16", "ESP32 development board", "Espressif ESP32-DevKitC-32E", 1, 10, "DigiKey 1965-ESP32-DEVKITC-32E-ND", "ESP32-DevKitC-VE (WROVER); local ESP32 DevKit with CP2102", "Quoted", "Micro-USB: needs a USB-C to Micro-USB data cable. Power it from USB only."],
 ["Main board", "U2", "Adjustable regulator used as 0.625 A current source, TO-220", "TI LM317T", 1, 0.45, "LCSC / DigiKey", "ST LM317T, onsemi LM317TG", "Estimate", "Rev C: I = 1.25 V / R_SET. Fit the clip-on heatsink."],
 ["Main board", "HS1", "Clip-on TO-220 heatsink, about 20 °C/W", "Aavid 577202B00000G", 1, 0.6, "DigiKey", "Any TO-220 clip heatsink 18-25 °C/W", "Estimate", "About 2.2 W while a pin is on."],
 ["Main board", "U15", "16-bit ADC, 4 ch, I2C", "TI ADS1115IDGSR", 1, 1.33, "LCSC C37593", "ADS1115 breakout module (for a hand-wired prototype)", "Quoted", "LCSC showed 0 stock on one listing; DigiKey ~$3.59."],
 ["Main board", "U5–U14", "Triple SPDT analog switch, DIP-16 (two 16-to-1 sense trees)", "TI CD4053BE", 10, 0.45, "LCSC / DigiKey", "Nexperia HEF4053BP, CD4053BM96 (SOIC)", "Estimate", "Rev C: replaces the two CD74HC4067. Sense lines only, no test current."],
 ["Main board", "U3, U4", "8-bit shift register", "TI SN74HC595DR", 2, 0.2, "LCSC", "Nexperia 74HC595D", "Estimate", ""],
 ["Main board", "U1", "3.3 V LDO, 600 mA", "Diodes AP2112K-3.3TRG1", 1, 0.1, "LCSC", "AMS1117-3.3 (SOT-223)", "Estimate", "Analog 3.3 V rail."],
 ["Main board", "Q4–Q19", "N-MOSFET, logic level, SOT-23", "AOS AO3400A", 16, 0.03, "LCSC", "Vishay Si2302CDS", "Estimate", "One per contact (pin select)."],
 ["Main board", "Q1, Q3", "P-MOSFET, SOT-23", "AOS AO3401A", 2, 0.03, "LCSC", "Vishay Si2301CDS", "Estimate", "Q3 = test current enable (Q_EN). Q1 = reverse-polarity protection (rev B)."],
 ["Main board", "Q2", "N-MOSFET small signal", "2N7002", 1, 0.02, "LCSC", "BSS138", "Estimate", ""],
 ["Main board", "R4 (R_SET)", "Metal-oxide resistor 2.0 Ω 1 %, 3 W, axial", "Vishay PR03000202008JAC00", 1, 0.2, "DigiKey", "Any 2.0 Ω 3 W, 1 %", "Estimate", "Sets the test current; 0.78 W in use. Mount 2 mm off the board."],
 ["Main board", "R5 (R_SH)", "Current shunt 0.1 Ω 1 %, 1 W, 2512", "Yageo PE2512FKF070R1L", 1, 0.12, "LCSC", "Vishay WSL2512R1000FEA", "Estimate", "Read by ADS1115 AIN2-AIN3 with Kelvin taps."],
 ["Main board", "R (misc)", "Thick-film resistors 1 %, 0603: 10 kΩ ×40, 100 kΩ ×17, 100 Ω ×16, 1 kΩ ×5, 4.7 kΩ ×2, 3.3 kΩ", "UNI-ROYAL 0603WAF series", 81, 0.003, "LCSC", "Yageo RC0603FR-07 series", "Estimate", ""],
 ["Main board", "D3, D4", "Dual Schottky clamp, SOT-23", "Nexperia BAT54S", 2, 0.02, "LCSC", "BAT54SW (SOT-323)", "Estimate", "ADS1115 contact inputs."],
 ["Main board", "D2", "TVS diode 5 V", "Littelfuse SMBJ5.0A", 1, 0.05, "LCSC", "SMAJ5.0A", "Estimate", ""],
 ["Main board", "F1", "Polyfuse 2 A hold, 1812", "Bourns MF-MSMF200-2", 1, 0.15, "LCSC", "Littelfuse 1812L200", "Estimate", ""],
 ["Main board", "C1", "Electrolytic 470 µF 10 V", "Panasonic EEU-FR1A471", 1, 0.15, "LCSC", "Any low-ESR 470 µF 16 V", "Estimate", ""],
 ["Main board", "C (misc)", "Ceramic caps: 100 nF ×18 (0603), 10 µF ×2 and 1 µF (0805)", "Samsung CL series", 21, 0.01, "LCSC", "Murata GRM series", "Estimate", ""],
 ["Main board", "D5", "LED green 0805", "Generic", 1, 0.02, "LCSC", "", "Estimate", ""],
 ["Main board", "J1", "DC barrel jack 5.5/2.1 mm", "CUI PJ-002A", 1, 0.6, "LCSC / DigiKey", "Generic DC-005", "Estimate", ""],
 ["Main board", "J2, J3", "Box header 2×17, 2.54 mm", "Amphenol T821134A1S100CEU", 2, 0.3, "LCSC", "Generic 34-pin IDC box header", "Estimate", "Ribbon to the jack boards."],
 ["Main board", "J4", "JST XH 2-pin header", "JST B2B-XH-A", 1, 0.05, "LCSC", "Generic XH 2.54", "Estimate", "Mate-detect switch."],
 ["Main board", "J5", "Pin header 1×4, 2.54 mm", "Generic 2.54 mm", 1, 0.03, "LCSC", "", "Estimate", "I2C spare."],
 ["Main board", "MCU socket", "Female header 1×19, 2.54 mm", "Generic", 2, 0.15, "LCSC", "", "Estimate", "Lets the ESP32 board plug in."],
 ["Main board", "D1", "Zener 5.1 V, SOD-123", "Diodes BZT52C5V1", 1, 0.02, "LCSC", "MMSZ5231B", "Estimate", "Rev B: Q1 gate clamp."],
 ["Jack boards", "J_IDC", "Box header 2×17, 2.54 mm", "Amphenol T821134A1S100CEU", 2, 0.3, "LCSC", "Generic 34-pin IDC box header", "Estimate", "One per jack board."],
 ["Jack boards", "Standoffs", "M3 brass standoff, 7 mm (plug) and 8 mm (socket)", "Generic M3", 4, 0.1, "LCSC / local", "", "Estimate", "Plates sit 7.1 / 7.9 mm above the board: shim with a washer."],
 ["Cables & power", "W1, W2", "34-way IDC ribbon, 30 cm, with 2 IDC sockets", "3M 3365/34 + 3M 89134 sockets", 2, 1.5, "LCSC / DigiKey", "Generic 34P ribbon assembly", "Estimate", ""],
 ["Cables & power", "PSU", "5 V 2 A adapter, 5.5/2.1 mm plug", "Mean Well GST18A05-P1J", 1, 8, "DigiKey / Mouser", "Generic 5 V 2 A adapter (~$3)", "Estimate", ""],
 ["Cables & power", "USB", "USB-C to Micro-USB data cable, 1 m", "Generic", 1, 2, "Local", "", "Estimate", "Must carry data, not charge-only."],
 ["PCBs", "PCB-1", "Main board 135×101 mm, 2-layer, 2 oz (lot of 5)", "JLCPCB", 1, 22, "JLCPCB", "PCBWay", "Estimate", "Shipping not included."],
 ["PCBs", "PCB-2, PCB-3", "Jack boards 80×40 mm, 2-layer, 1 oz (lot of 5 each)", "JLCPCB", 2, 2, "JLCPCB", "PCBWay", "Estimate", "Two designs (plug and socket footprints)."],
 ["Fixture", "RAIL", "Linear rail MGN12H, 150 mm, with carriage", "HIWIN MGN12H", 1, 15, "AliExpress / local", "Genuine HIWIN (~$60)", "Estimate", "Price for a generic rail."],
 ["Fixture", "MECH", "Base plate, female-board bracket, carriage clamp (aluminium)", "Custom machined", 1, 30, "Local machine shop", "3D-printed brackets on an aluminium plate", "Estimate", ""],
 ["Fixture", "SW", "Mate-detect microswitch, lever", "Omron D2F-01L", 1, 1.5, "DigiKey / LCSC", "KW11-3Z generic", "Estimate", ""],
 ["Fixture", "HW", "Handle knob, M3/M4 screws, rubber feet", "Generic", 1, 5, "Local", "", "Estimate", ""],
 ["Calibration", "SHUNT", "Reference shunt 10 mΩ, 4-terminal (Kelvin), 1 %", "Vishay WSK2512R0100FEA", 1, 2, "DigiKey / Mouser", "Bourns CSS2H-2512K-10L0F", "Estimate", "For 'Calibrate with shunt'."],
 ["Calibration", "SHORT", "Shorting bar (copper), force and sense shorted", "Made in-house", 1, 2, "Local", "", "Estimate", "For 'Calibrate zero'."],
]
NOTE = ("Unit price at qty 1, USD, excl. tax and shipping. 'Quoted' = distributor price seen 18 Nov 2026; "
        "'Estimate' = typical price, check before ordering.")
OUT = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "..") + "/"
first, last = 6, 5 + len(R)

wb = Workbook(); ws = wb.active; ws.title = "BOM"
ws["A1"] = "Total per kit (USD)"; ws["B1"] = f"=SUM(G{first}:G{last})"
ws["A2"] = "Prices"; ws["B2"] = NOTE
ws["A4"] = "Parts for one CR-TEST kit"
for c in ("A1", "B1", "A4"): ws[c].font = Font(bold=True)
ws.append([]) if False else None
for j, h in enumerate(HEAD, 1):
    cell = ws.cell(row=5, column=j, value=h); cell.font = Font(bold=True)
    cell.fill = PatternFill("solid", fgColor="F3F3F3")
for i, r in enumerate(R):
    n = first + i
    vals = r[:6] + [f"=E{n}*F{n}"] + r[6:]
    for j, v in enumerate(vals, 1):
        c = ws.cell(row=n, column=j, value=(v if v != "" else None))
        if j in (3, 4, 8, 9, 11): c.alignment = Alignment(wrap_text=True, vertical="top")
        else: c.alignment = Alignment(vertical="top")
    ws.cell(row=n, column=6).number_format = '"$"#,##0.000'
    ws.cell(row=n, column=7).number_format = '"$"#,##0.00'
ws["B1"].number_format = '"$"#,##0.00'
for col, w in zip("ABCDEFGHIJK", [18, 15, 34, 28, 6, 11, 11, 24, 32, 11, 46]):
    ws.column_dimensions[col].width = w
ws.freeze_panes = "A6"
ws.auto_filter.ref = f"A5:K{last}"
dv = DataValidation(type="list", formula1='"Quoted,Estimate"', allow_blank=True)
ws.add_data_validation(dv); dv.add(f"J{first}:J{last}")
wb.save(OUT + "BOM.xlsx")

total = 0
with open(OUT + "BOM.csv", "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh); w.writerow(HEAD)
    for r in R:
        lt = round(r[4] * r[5], 3); total += lt
        w.writerow(r[:6] + [lt] + r[6:])
    w.writerow(["TOTAL per kit (USD)", "", "", "", "", "", round(total, 2), "", "", "", NOTE])
print(len(R), "lines, total", round(total, 2))
