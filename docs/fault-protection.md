# Fault protection review (open and shorted pins)

## Board rev C (current design, 23 Nov 2026)

Rev C replaces the resistive current source with an **LM317T constant-current source** (R_SET 2.0 Ω,
0.625 A), the sense muxes with **CD4053BE trees**, and reads the contact directly with the **ADS1115**
(no INA333, no ACS712). Fault by fault:

| Fault | Rev C behaviour | Protected? |
| --- | --- | --- |
| 1 or more pins open | No current for that pin: `OPEN` (shunt reads < 0.2 A) | Yes, detected |
| 2, 3 or all 16 pins shorted | Current stays 0.625 A (set by the LM317T), shared by the shorted contacts. Isolation test (50 µV against a current-off baseline) and the `LOW` flag find it | Yes, inherently, and detected |
| Force line shorted to GND | The LM317T still delivers only 0.625 A. It drops about 3.6 V, 2.3 W, the same as a normal pulse | **Yes, inherently** (rev B needed a 10 W R_HI and a firmware cut-off) |
| Open pin pulsed | F_BUS rises to about 3.8 V; the 10 kΩ sense resistors keep the back-feed into +3V3A under 0.1 mA in total, and the 3.3 kΩ bleeder absorbs it | Yes |
| Reversed adapter | Q1 P-MOSFET blocks it | Yes |
| LM317T failed short (IN-OUT) | Current set by the path only (several amps possible) | Firmware: above 0.75 A on the shunt → `ALARM OVERCURRENT`, current off within a few ms; F1 polyfuse backs it up |
| ADC inputs | BAT54S clamps on AIN0/AIN1, 1 kΩ on all four inputs; muxes run from +3V3A behind 10 kΩ | Yes |

Simulated on rev C (firmware 0.5 logic, `desktop-app/tests/run_fault_scenarios.py`): 1 pin open,
3 pins open, 2, 3 and all 16 pins shorted are all detected at cycle 11 and fail at cycle 13 after
3 scans in a row; no false alarms in the no-fault run.

The rest of this file is the rev A/B review, kept for history.


**Verdict:** shorts between connector pins, any number of them, cannot damage the board. The test
current comes through R_HI and R_LO, so it stays at about 0.63 A whatever the pins do, and every part
in the path is rated far above that. Three other faults are not fully covered by board rev A, and are
fixed in **rev B** below: a force line shorted to GND, an open pin back-feeding the 3.3 V analog rail,
and a reversed power adapter. Rev A also cannot reliably *detect* shorts of 3 or more pins.

## Worst case for each fault (rev A)

Normal test pulse: I = 5 V / (5.6 + 2.2 + 0.18 Ω) = **0.627 A**; R_HI 2.20 W, R_LO 0.86 W, F_BUS at 1.49 V.

| Fault | What happens | Current / stress | Protected? |
| --- | --- | --- | --- |
| **1 pin open** | No path for that pin's test current | 0 A for that pin. F_BUS rises to 5 V while it is pulsed (see the 3.3 V row) | Yes (detected: `OPEN`) |
| **2+ pins open** | Same, per pin | Same | Yes (detected: `OPEN` per pin) |
| **2 pins shorted** | Current shares the two contacts; both read about half (2.3 → 1.2 mΩ in the run below) | ≤ 0.63 A, limited by R_HI + R_LO | **Yes, inherently.** Not visible as a high reading: found by the isolation test |
| **3+ pins shorted** | Same with more paths in parallel | ≤ 0.63 A | **Yes, inherently.** Rev A can miss it (detection row) |
| Force line or female pin shorted to **GND** (chassis, crushed ribbon at pins 31/33) | Bypasses R_LO | **0.89 A**, R_HI **4.46 W** (rated 5 W) | Partly. Firmware 0.3 switches off above 0.75 A within ~6 ms (`ALARM OVERCURRENT`). A hung firmware would leave R_HI near its rating |
| Open pin pulsed (F_BUS at 5 V) | All 16 female sense lines sit at 5 V; the BAT54S clamps push current into +3V3A | **22 mA** into a rail that only draws ~1 mA; the LDO can't sink it, so +3V3A rises | **No.** No part is overstressed (all ≤ 5.5 V parts), but readings in that pulse are wrong |
| Firmware hangs with current on, normal pin | Steady 0.627 A | R_HI 2.2 W, R_LO 0.86 W | Yes, within ratings. GPIO32 has a pull-down, so a reset turns the current off |
| Adapter reversed | SMBJ5.0A conducts forward; ICs see about −1 V | Polyfuse trips at ~4 A after a delay | **No.** ACS712 and the logic ICs are only rated to −0.3…−0.5 V |
| Adapter overvoltage (e.g. 12 V) | TVS clamps, polyfuse trips | | Yes (blunt) |
| ACS712 output fault (up to 5 V) into ADS1115 AIN0 | ADS1115 inputs rated to VDD + 0.3 V | | **No clamp** |
| ESD on sense lines when handling the jacks | 1 kΩ + BAT54S on every mux input | | Yes |
| 5 V on the jack boards or ribbon | None exists (only force, sense, GND) | | Not credible |

Isolation test duty: the test adds about 0.4 s of current-on time per scan (0.84 s in total), so R_HI
averages about 1.9 W at one cycle per second, and less at the 3 s cycle you use.

## Detecting shorts

A short makes the affected pins read *lower*, so the 10 mΩ limit never catches it. The **isolation
test** (firmware 0.3.0+, after each scan) drives each pin in turn and reads the contact voltage of
every other pin through the existing muxes. Without a short, no current flows through an undriven
contact, so its voltage is about 0. If the pins are shorted, part of the current returns through
that contact. With healthy 2.8 mΩ contacts, the voltage on an undriven pin is:

| Pins shorted together | Voltage on an undriven pin | INA333 output (G = 101) |
| --- | --- | --- |
| 2 | 878 µV | +89 mV |
| 3 | 585 µV | +59 mV |
| 4 | 439 µV | +44 mV |
| 8 | 219 µV | +22 mV |
| 16 (all pins) | ~110 µV (85–130 µV, depends on the contacts) | +11 mV |

On rev A, INA333 REF is tied to GND, so the output cannot go below about 50 mV. A 3-pin short is then
barely above that floor and a 4-pin short is below it. **Rev B lifts REF to about 0.25 V**, so every
row is well clear of the noise (about 0.8 mV rms). The firmware reads REF on AIN3 and subtracts it.

**All 16 pins shorted (found 19 Nov 2026).** Firmware 0.3 used a 150 µV limit, which a 16-pin short
(about 110 µV) stays under: the simulated run detected nothing and every pin quietly read 0.2 mΩ.
Firmware 0.4.0 fixes this two ways:

1. Isolation limit 150 → **50 µV**, measured against each channel's own current-off baseline (read at the
   start of every isolation test), so the INA333 offset (up to ±25 µV) and thermal EMFs cancel.
   Noise after averaging is a few µV, so 50 µV keeps a wide margin both ways.
2. A plausibility check: any reading below **0.8 mΩ** is flagged `LOW`. No real contact on this kit reads
   that low (new contacts measure about 2–3.5 mΩ), so LOW means pins are shorted. It works even with the
   isolation test turned off (`ISO 0`), and the app counts LOW toward the 3-in-a-row fail rule.

## Rev B changes

| # | Change | Fixes | Parts |
| --- | --- | --- | --- |
| 1 | INA333 REF = 0.25 V: divider 120 kΩ / 10 kΩ from +3V3A, buffered by an OPA333; REF also wired to ADS1115 AIN3 | Detects shorts of 3–8+ pins; readings near 0 mΩ | OPA333AIDBVR, 2 resistors, 100 nF |
| 2 | Sense-line series resistors 1 kΩ → **10 kΩ**, plus a 3.3 kΩ bleeder from +3V3A to GND | Open-pin back-feed falls from 22 mA to 2.2 mA, which the bleeder absorbs | 32 × 10 kΩ, 1 × 3.3 kΩ |
| 3 | Reverse-polarity P-MOSFET at J1 (ideal-diode connection, gate to GND through 10 kΩ, 5.1 V Zener gate–source) | Reversed adapter | AO3401A, BZT52C5V1, 10 kΩ |
| 4 | R_HI 5 W → **10 W** wirewound | Force-to-GND short with stuck firmware: 4.46 W becomes about 45 % of rating | 5.6 Ω 10 W |
| 5 | BAT54S clamp to +3V3A after the ACS712's 1 kΩ output resistor | ACS712 fault voltage into the ADS1115 | BAT54S |
| 6 | Ribbon pins 33/34: leave **unconnected** instead of GND | A crushed IDC next to Force 16 can no longer short it to GND | none |

Firmware (0.3.0, done): overcurrent cut-off above 0.75 A, isolation test, `OPEN` readings sent as
`nan`, supply alarm outside 4.6–5.4 V. Firmware (0.4.0, done): isolation limit 50 µV against a
current-off baseline, `LOW` flag below 0.8 mΩ. Firmware (to do): enable the ESP32 task watchdog, and stop a
scan if the mate-detect switch opens mid-scan.

## Scenario run (simulated kit, app code, 30 cycles each: fault on cycles 11–20)

| Scenario | Detected | Pins failed (3 in a row) | Cleared | Logged as |
| --- | --- | --- | --- | --- |
| No fault | no false alarms | none | | nothing |
| 1 pin open (5) | cycle 11 | pin 5 at cycle 13 (open) | cycle 21 | OPEN, FAIL, OPEN cleared |
| 3 pins open (2, 9, 14) | cycle 11 | 2, 9, 14 at cycle 13 (open) | cycle 21 | 3 × OPEN, 3 × FAIL, 3 × cleared |
| 2 pins shorted (4–5) | cycle 11 | 4, 5 at cycle 13 (short with each other) | cycle 21 | SHORT, 2 × FAIL, SHORT cleared. R 2.26 → 1.24 mΩ |
| 3 pins shorted (10–11–12) | cycle 11 | 10, 11, 12 at cycle 13 | cycle 21 | SHORT (one group event), 3 × FAIL, cleared. R ≈ 3 → 1.05 mΩ |
| **All 16 pins shorted**, firmware 0.3 | **not detected** | none | | nothing. R 2.2–3.5 → 0.2 mΩ on every pin |
| **All 16 pins shorted**, firmware 0.4 | cycle 11 | all 16 at cycle 13 | cycle 21 | SHORT (one group of 16, up to 132 µV), 16 × LOW, 16 × FAIL, all cleared |

Rerun on 19 Nov 2026 with firmware 0.4 logic: the five earlier scenarios give the same results, with no
false alarms. Protection is unchanged for the all-pin short: it only puts the contacts in parallel, the
current stays at 0.627 A (limited by R_HI + R_LO), and the one switched-on AO3400A carries it.

The simulator models rev B (REF = 0.25 V). On real hardware, check the isolation test with a
deliberate solder-bridge sample before trusting a long run.
