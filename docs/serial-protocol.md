# Serial protocol: ESP32 ⇄ laptop

USB serial (the DevKitC's USB-UART chip), **115200 baud, 8N1**. Plain text, one message per line,
lines end with `\n`. Fields are comma-separated. Lines starting with `#` are free-text info and are ignored by parsers.

## ESP32 → laptop

| Line | When | Fields |
| --- | --- | --- |
| `HELLO,CRKIT,<fw>,<gain>,<cycle>` | at boot and in reply to `STATUS` | firmware version, gain (fw 0.5+ / board rev C: always 16 = ADS1115 at ±0.256 V; rev A/B: INA333 gain), current cycle counter |
| `CYCLE,<n>,<trigger>` | start of a scan | cycle number, `MATE` (mate-detect switch) or `MANUAL` (`SCAN` command) |
| `ZERO,<n>,<v0_V>,<v5_V>` | after the zero read | fw 0.5+: shunt channel offset (V) with the current off; rev A/B: ACS712 zero output. Then the measured 5 V rail |
| `DATA,<n>,<pin>,<I_A>,<V_mV>,<R_mOhm>,<flag>,<Rmin_mOhm>` | once per pin (16 per scan) | cycle, pin 1–16, measured current, contact voltage, resistance (average of 8 readings, after calibration), flag, lowest of the 8 readings (firmware 0.2+; parsers treat it as optional) |
| `SHORT,<n>,<pinA>,<pinB>,<uV>` | isolation test (after the 16 DATA lines), once per shorted pair | pins A and B are connected; the voltage seen on the undriven pin's contact (firmware 0.3+) |
| `ISO,<n>,<pairs>` | end of the isolation test | number of shorted pairs found (0 = all pins isolated) |
| `ALARM,<n>,<code>,<text>` | when a kit-level fault is found | `OVERCURRENT`: test current above 0.75 A (force path shorted to GND/chassis); current switched off and the scan stopped. `SUPPLY`: 5 V rail outside 4.6–5.4 V |
| `END,<n>,<ms>` | end of a scan | cycle, scan duration in ms |
| `OK,<command>` | a command was accepted | |
| `ERR,<text>` | a command was refused | reason |
| `# <text>` | any time | info for the console |

`flag` is one of:

- `OK`: valid reading
- `OVER`: R is above range. Rev C: contact voltage above 0.25 V (R > about 400 mΩ). Rev A/B: INA333 output at the top rail, set JP1 to G = 11 and send `GAIN 11`.
- `UNDER` (rev A/B only): INA333 output at the bottom rail (below about 1 mΩ at G = 101). Rev C never sends it.
- `LOW` (fw 0.4+): calibrated R below 0.8 mΩ, lower than any real contact: two or more pins are shorted. The app logs it and counts it toward the fail rule.
- `OPEN`: test current below 0.2 A: contact open, connector not mated, or ribbon unplugged. R and Rmin are sent as `nan`.

**Shorted pins** read *lower* than normal in the DATA lines (the shorted contacts carry current in parallel), so they are found by the isolation test, not by the resistance limit: the kit drives each pin in turn and checks that no other pin's contact carries current (fw 0.4: more than 50 µV above that channel's current-off baseline = SHORT; this also catches all 16 pins shorted together).

## Laptop → ESP32

| Command | Effect |
| --- | --- |
| `STATUS` | replies with `HELLO,...` |
| `SCAN` | runs one scan now and adds 1 to the cycle counter (use without a mate-detect switch) |
| `MEASURE` | runs one scan **without** adding to the cycle counter (cycle field = current count) |
| `SETCYCLE <n>` | sets the cycle counter (to resume a test after a restart) |
| `GAIN <11\|101\|1001>` | rev A/B only: tells the firmware which INA333 gain JP1 is set to. Fw 0.5 (rev C) replies `ERR` |
| `ISO <0\|1>` | 1 = run the isolation (short) test after every scan (default), 0 = skip it |
| `AUTO <0\|1>` | 1 = scan on every mate-detect closure (default), 0 = ignore the switch |
| `CALZERO` | with the shorting bar fitted: scans and stores each pin's reading as its zero offset |
| `CALREF <mOhm>` | with a reference shunt on pin 1: scans pin 1 and stores a gain correction |
| `CALCLEAR` | clears both calibrations |
| `SIMRUN <cycles> <ms>` | **simulator only:** runs that many cycles, one every `<ms>`, then sends `OK,SIMDONE` |
| `SIMSTOP` | **simulator only:** stops a `SIMRUN` |
| `FAULT OPEN <pins>` / `FAULT SHORT <a-b-c>` / `FAULT CLEAR` | **simulator only:** inject open pins (e.g. `FAULT OPEN 2,9,14`) or a group of shorted pins (`FAULT SHORT 10-11-12`); faults add up until `FAULT CLEAR` |

Settings, calibration and the cycle counter are kept in the ESP32's flash, so they survive a power cycle.
