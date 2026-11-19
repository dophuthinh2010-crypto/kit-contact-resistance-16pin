# KiCad projects, board rev B

| Folder | Board | Size | Status |
| --- | --- | --- | --- |
| `crkit_main/` | Main board: current source, 16 pin switches, Kelvin sense muxes, INA333, ADS1115, ESP32-DevKitC socket | 135 × 90 mm, 2 layers, 2 oz | Schematic complete. PCB placed, nets and net classes set, GND pours on both layers. **Not routed** |
| `crkit_jack_female/` | RS16P-T socket + 2×17 IDC | 80 × 40 mm | Schematic complete. PCB placed. **Not routed** |
| `crkit_jack_male/` | RP16-T plug + 2×17 IDC | 80 × 40 mm | Schematic complete. PCB placed. **Not routed** |
| `crkit.kicad_sym`, `crkit.pretty/` | Symbols and footprints used by all three (also embedded in each file) | | |
| `preview/` | PNG previews of the schematic and of each placement with its ratsnest | | |

All files are written by `hardware/scripts/kicad_gen/build_all.py` (KiCad 8 format). The design lives
in the scripts: `main_board.py` (netlist + placement), `jack_board.py`, `lib.py` (symbols and footprints).
To change the design, edit the script and run `python build_all.py`, or open the files in KiCad and keep
editing there (then stop regenerating, or your KiCad edits will be overwritten).

The files were generated without KiCad (no KiCad in the build environment). They follow the KiCad 8 file
format and pass a structural check, but **open them in KiCad 8 or newer and run ERC and DRC before
anything else.** Schematic style: every part is a box symbol, and every pin ends in a short wire with
a net label, so the netlist is exact and easy to check against `docs/design.md`.

## Rev B changes in the schematic

| # | Change | Parts |
| --- | --- | --- |
| 1 | INA333 REF = 0.25 V: 120 k / 10 k divider from +3V3A, buffered by OPA333, REF also on ADS1115 AIN3 | U8, R75, R76, C14, C15 |
| 2 | Sense series resistors 1 k → 10 k (32×), 3.3 k bleeder on +3V3A | R39–R70, R71 |
| 3 | Reverse-polarity P-MOSFET at J1, 10 k gate resistor, 5.1 V Zener gate clamp | Q1, R1, D1 |
| 4 | R_HI 5 W → 10 W | R4 |
| 5 | BAT54S clamp on the ACS712 output after its 1 k | R5, D3 |
| 6 | IDC pins 33/34 not connected (were GND) | J2, J3 |
| | Board 100 × 80 → 135 × 90 mm, to fit the 10 W resistor, the extra parts and two IDC headers side by side | |

## Reference map (old names in the docs → KiCad references)

| Docs | KiCad | Docs | KiCad |
| --- | --- | --- | --- |
| R_HI 5.6 Ω 10 W | R4 | R_LO 2.2 Ω 5 W | R6 |
| Q_REV | Q1 | Q_DRV 2N7002 | Q2 |
| Q_EN AO3401A | Q3 | Q1…Q16 pin switches | Q4…Q19 (contact n = Q(n+3)) |
| ACS712 | U2 | AP2112K LDO | U1 |
| 74HC595 ×2 | U3, U4 | CD74HC4067 female / male | U5, U6 |
| INA333 | U7 | OPA333 (REF buffer) | U8 |
| ADS1115 | U9 | ESP32-DevKitC | U10 |
| RG1 1.00 k / RG2 10.0 k | R73 / R74 | Gain jumper | JP1 |
| Barrel jack | J1 | IDC to female / male board | J2 / J3 |
| Mate switch | J4 | I²C spare | J5 |
| Mux-input clamps | D4–D35 | Test points | TP1–TP6 (GND, I_SENSE, LO_RTN, INA_REF, V_CONTACT, F_BUS) |

## Main board placement

![main board placement](preview/main_board_placement.png)

- Top: R4 (R_HI, mount 3 mm off the board) and R6 (R_LO), current switch Q2/Q3, ACS712 (U2).
- Left: power input (J1 on the board edge, Q1 reverse protection, F1, D2 TVS, C1, LDO U1).
- Centre: two rows of 8 pin switches with their gate resistors and pull-downs, shift registers U3/U4 above.
- Middle: muxes U5 (female) and U6 (male) with the INA333 (U7) between them, so SENSE_F/SENSE_M stay short.
- Bottom: 10 k + BAT54S for every sense line, straight above its IDC column. J2/J3 are turned 180° so the
  sense row faces the resistors. **Pin 1 is at the right-hand end** of both headers (silkscreen says so).
- Right: ESP32-DevKitC on two 1×19 sockets 25.4 mm apart, USB end over the top edge.
  Analog corner below it: REF buffer, 5 V divider, pull-ups, LED, mate switch J4, I²C J5, test points.

## Routing (next step)

Net classes are set in the project: **Power** 1.0 mm / 0.3 mm (F_BUS, LO_RTN, I_HI, ACS_IP, +5V, VIN_*,
MF1–MF16, GND) and **Sense** 0.25 mm (SF/SM, SFC/SMC, SENSE_F/M). Default 0.25 mm / 0.2 mm.

1. Open `crkit_main.kicad_pro` in KiCad 8+. Run **Inspect → Electrical Rules Checker** on the schematic, then
   **Tools → Update PCB from Schematic** (should report no changes) and **DRC** (unrouted only).
2. Route by hand first: F_BUS (ACS712 → J2 odd row) and LO_RTN (16 sources → R6) as wide pours or 1.5 mm
   traces on the top layer; the R6 return goes straight to the J1 ground.
3. Then autoroute the rest: **File → Export → Specctra DSN**, route it in Freerouting, then
   **File → Import → Specctra Session**. Keep SENSE_F and SENSE_M as a tight pair over unbroken ground.
4. Press **B** to refill the GND pours and run DRC again.
5. Jack boards: the force (odd) and sense (even) trace of each contact must leave the pad on opposite sides
   and meet only at the pad. Contacts 9–16 are on the far row, so use both layers.

## Check before ordering PCBs

- Footprints against real parts: RP16-T / RS16P-T sample, CUI PJ-002A barrel jack drawing,
  your ESP32-DevKitC (row spacing 25.4 mm, pinout of V4), Yageo SQP10 / SQP500 lead spacing.
- ERC, DRC, and a 1:1 paper print of each board with the connector and the DevKitC laid on it.
