# Serial protocol: ESP32 ⇄ laptop

USB serial (the DevKitC's USB-UART chip), **115200 baud, 8N1**. Plain text, one message per line,
lines end with `\n`. Fields are comma-separated. Lines starting with `#` are free-text info and are ignored by parsers.

## ESP32 → laptop

| Line | When | Fields |
| --- | --- | --- |
| `HELLO,CRKIT,<fw>,<gain>,<cycle>` | at boot and in reply to `STATUS` | firmware version, INA333 gain set in firmware, current cycle counter |
| `CYCLE,<n>,<trigger>` | start of a scan | cycle number, `MATE` (mate-detect switch) or `MANUAL` (`SCAN` command) |
| `ZERO,<n>,<v0_V>,<v5_V>` | after the zero read | ACS712 zero output, measured 5 V rail |
| `DATA,<n>,<pin>,<I_A>,<V_mV>,<R_mOhm>,<flag>,<Rmin_mOhm>` | once per pin (16 per scan) | cycle, pin 1–16, measured current, contact voltage, resistance (average of 8 readings, after calibration), flag, lowest of the 8 readings (firmware 0.2+; parsers treat it as optional) |
| `END,<n>,<ms>` | end of a scan | cycle, scan duration in ms |
| `OK,<command>` | a command was accepted | |
| `ERR,<text>` | a command was refused | reason |
| `# <text>` | any time | info for the console |

`flag` is one of:

- `OK`: valid reading
- `OVER`: INA333 output at the top rail. R is above range: set JP1 to G = 11 and send `GAIN 11`.
- `UNDER`: INA333 output at the bottom rail (below about 1 mΩ at G = 101)
- `OPEN`: test current below 0.2 A: contact open, connector not mated, or ribbon unplugged

## Laptop → ESP32

| Command | Effect |
| --- | --- |
| `STATUS` | replies with `HELLO,...` |
| `SCAN` | runs one scan now and adds 1 to the cycle counter (use without a mate-detect switch) |
| `MEASURE` | runs one scan **without** adding to the cycle counter (cycle field = current count) |
| `SETCYCLE <n>` | sets the cycle counter (to resume a test after a restart) |
| `GAIN <11\|101\|1001>` | tells the firmware which INA333 gain JP1 is set to |
| `AUTO <0\|1>` | 1 = scan on every mate-detect closure (default), 0 = ignore the switch |
| `CALZERO` | with the shorting bar fitted: scans and stores each pin's reading as its zero offset |
| `CALREF <mOhm>` | with a reference shunt on pin 1: scans pin 1 and stores a gain correction |
| `CALCLEAR` | clears both calibrations |
| `SIMRUN <cycles> <ms>` | **simulator only:** runs that many cycles, one every `<ms>`, then sends `OK,SIMDONE` |
| `SIMSTOP` | **simulator only:** stops a `SIMRUN` |

Settings, calibration and the cycle counter are kept in the ESP32's flash, so they survive a power cycle.
