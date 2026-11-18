# Kit: 16-pin connector contact resistance tester

Test kit that measures the mated contact resistance of all 16 contacts of an
ITW McMurdo Red Range 16-way connector (RP16-T plug / RS16P-T socket) after
every plug/unplug cycle. The data is used to estimate connector life
(datasheet: 5 mΩ max initially, 10 mΩ max after conditioning, 500 mechanical operations).

**Status:** design stage, for review. Schematic and PCB layout not yet drawn in KiCad.

## How it works

- ESP32 selects one contact at a time (16 low-side MOSFETs driven by 2 × 74HC595).
- About 0.62 A flows through the selected contact. The ACS712 measures the current I.
- Kelvin sense taps at the connector pads go through 2 × CD74HC4067 muxes to an
  INA333 (gain 101), then to an ADS1115 16-bit ADC: contact voltage V.
- R = V / I. Range is about 0–51 mΩ (G = 101) or 0–470 mΩ (G = 11, jumper).
- One CSV line per pin per cycle over USB serial: `cycle, pin, I_A, V_mV, R_mOhm`.

Boards: main board (100 × 80 mm, 2-layer) plus two jack breakouts (about 80 × 40 mm),
linked by 34-way IDC ribbons (16 force + 16 sense + 2 GND).

## Repository layout

| Path | Contents |
| --- | --- |
| `docs/design.md` | Design summary: schematic blocks, pin map, connector pinouts, layout rules, open items |
| `docs/concept_sketch.jpg` | Original concept sketch |
| `docs/footprint_preview.png` | Preview of the connector footprints |
| `docs/3d-model/index.html` | Interactive 3D model of the kit (open in a browser; loads three.js from a CDN) |
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
- [ ] Draw the schematic in KiCad
- [ ] Lay out the jack breakout boards (connector + IDC + force/sense traces)
- [ ] Lay out the main board
- [ ] Firmware: scan loop, calibration, CSV logging
