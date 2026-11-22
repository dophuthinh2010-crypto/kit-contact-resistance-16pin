# Kit: 16-pin connector contact resistance tester

Test kit that measures the mated contact resistance of all 16 contacts of an
ITW McMurdo Red Range 16-way connector (RP16-T plug / RS16P-T socket) after
every plug/unplug cycle. The data is used to estimate connector life
(datasheet: 5 mΩ max initially, 10 mΩ max after conditioning, 500 mechanical operations).

**Status:** design stage, for review. Firmware and desktop app written (app core tested; firmware and GUI not yet run on hardware). Schematic and PCB layout not yet drawn in KiCad.

## How it works

- ESP32 selects one contact at a time (16 low-side MOSFETs driven by 2 × 74HC595).
- An LM317T constant-current source drives 0.625 A through the selected contact; a 0.1 Ω shunt read by
  the ADS1115 gives the current I. (Main board rev C.)
- Kelvin sense taps at the connector pads go through two 16-to-1 trees of CD4053BE switches straight to
  the ADS1115, read differentially at ±0.256 V (7.8 µV per step): contact voltage V.
- R = V / I. Range is about 0–51 mΩ (G = 101) or 0–470 mΩ (G = 11, jumper).
- One CSV line per pin per cycle over USB serial: `cycle, pin, I_A, V_mV, R_mOhm`.

Boards: main board (100 × 80 mm, 2-layer) plus two jack breakouts (about 80 × 40 mm),
linked by 34-way IDC ribbons (16 force + 16 sense + 2 GND).

## Repository layout

| Path | Contents |
| --- | --- |
| `docs/INSTALL.md` | **Start here:** installing the USB driver, the desktop app and the firmware, then running a test |
| `docs/design.md` | Design summary: schematic blocks, pin map, connector pinouts, layout rules, open items |
| `docs/concept_sketch.jpg` | System concept diagram (redrawn from the original sketch, `docs/concept_sketch_original.jpg`; source: `hardware/scripts/draw_concept_diagram.py`) |
| `docs/footprint_preview.png` | Preview of the connector footprints |
| `docs/CR-TEST_presentation.pptx` | 13-slide PowerPoint presentation of the kit (source: `docs/presentation/build_deck.js`, pptxgenjs) |
| `docs/3d-model/index.html` | Interactive 3D model of the kit (open in a browser; loads three.js from a CDN) |
| `docs/fault-protection.md` | Open/short fault review, isolation test, rev C protection, scenario results |
| `docs/serial-protocol.md` | Serial protocol between the ESP32 and the laptop |
| `firmware/crkit_esp32/` | ESP32 firmware (Arduino): scan, mate detect, calibration |
| `desktop-app/` | Desktop app (Python, PySide6): connect, record to CSV, live table and plot |
| `docs/simulation/index.html` | 3D simulation: plug/unplug cycles, 16-pin scan through the rev C LM317T / CD4053B / ADS1115 chain with noise, assumed wear model and life estimate |
| `hardware/BOM.xlsx`, `hardware/BOM.csv` | Bill of materials for one kit (rev C, $156.22): model, supplier, price, alternative part (shared sheet: https://claude.ai/artifact/EmcHuasxRLR5GvdHxSPXVu) |
| `hardware/kicad/` | **Rev C KiCad 8 projects**: main board (schematic + placed PCB), female and male jack boards, shared libraries, previews. Not routed yet: see `hardware/kicad/README.md` |
| `hardware/scripts/kicad_gen/` | Python generator for those projects (`python build_all.py`) |
| `hardware/footprints/McMurdo_RedRange.pretty/` | KiCad footprints for RP16-T and RS16P-T |
| `hardware/scripts/gen_mcmurdo_fp.py` | Script that generates those footprints |

The full, living design document (with the BOM and block diagram) is the Claude doc
"PCB Design – 16-Pin Blindmate Contact Resistance Test Kit":
https://claude.ai/artifact/T8kFqe1HFXj3PjpiL8ypHh

## Connector reference

ITW McMurdo "Red range" industrial rack and panel connectors datasheet (not included in
this repo; get it from ITW McMurdo or a distributor).

## Using the footprints

KiCad → Preferences → Manage Footprint Libraries → add
`hardware/footprints/McMurdo_RedRange.pretty`.

## Next steps

- [ ] Review the design summary and open items
- [x] Schematic rev C in KiCad (LM317T, CD4053BE, ADS1115; main board + jack boards, generated)
- [x] PCB placement, nets, net classes, outlines, GND pours
- [ ] Open in KiCad 8, run ERC/DRC, route (hand-route power, Freerouting for the rest)
- [ ] Check footprints against real parts, then order PCBs
- [x] Firmware: scan loop, calibration, serial protocol
- [x] Desktop app: recording, live view, resume, summary
- [ ] Test firmware and app on the real kit
