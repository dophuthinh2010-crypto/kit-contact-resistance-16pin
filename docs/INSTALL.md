# Installation guide: CR-TEST kit + desktop app

This guide sets up a Windows laptop to read and record the kit's measurements over USB.
macOS and Linux notes are at the end. Allow about 30 minutes the first time.

You will:

1. Check the cable and power arrangement
2. Install the USB driver for the ESP32
3. Install Python and the desktop app (and try it with the built-in simulator)
4. Upload the firmware to the ESP32
5. Connect, calibrate and run a test
6. Optional: build a stand-alone `CR-TEST.exe`

---

## 1. Cable and power

| Item | What to use |
| --- | --- |
| USB cable | **USB-C (laptop) to Micro-USB (ESP32-DevKitC V4)**. It must be a *data* cable: many cheap cables only charge, and the laptop then never sees the board. If your DevKitC has a USB-C socket, use a USB-C to USB-C data cable. |
| Kit power | The **5 V 2 A adapter** into the main board's barrel jack J1. This powers the test current, sensors and logic. |
| ESP32 power | **From the laptop USB only.** |

> **Important: power the ESP32 from one source only.** Espressif states that the DevKitC must be powered by
> exactly one of USB, the 5V pin or the 3V3 pin, otherwise the board or the power source can be damaged.
> Because the laptop is always connected, the main board does **not** connect +5V to the DevKitC's 5V pin:
> only GND is shared (see `docs/design.md`, Power). If your board was built with that link, cut it or remove
> that header pin before you plug in USB.

Switch-on order: 5 V adapter first, then the USB cable. Switch-off: USB first, then the adapter.

## 2. USB driver

1. Plug the ESP32 into the laptop.
2. Open **Device Manager** (right-click Start → Device Manager) → **Ports (COM & LPT)**.
3. You should see one of:
   - `Silicon Labs CP210x USB to UART Bridge (COMx)`: most DevKitC V4 boards
   - `USB-SERIAL CH340 (COMx)` or `USB-Enhanced-SERIAL CH9102 (COMx)`: some boards
4. If instead there is an **Unknown device** with a yellow mark, install the driver:
   - CP210x: Silicon Labs "CP210x USB to UART Bridge VCP Drivers" (silabs.com), Windows universal driver
   - CH340/CH9102: WCH driver CH341SER (wch-ic.com)

   Unplug and replug the board afterwards. Note the COM number.
5. Nothing appears at all? Try another cable first (see section 1), then another USB port.

## 3. Python and the desktop app

### 3.1 Install Python

1. Download **Python 3.12** (64-bit) from python.org → Downloads → Windows.
2. Run the installer and tick **"Add python.exe to PATH"** on the first screen. Click **Install Now**.
3. Check it: open **Command Prompt** and type `py --version`. It should print `Python 3.12.x`.

### 3.2 Get the code

Either:

- **With Git** (recommended):
  ```bat
  cd /d D:\
  git clone https://github.com/dophuthinh2010-crypto/kit-contact-resistance-16pin.git
  ```
- **Without Git:** on the repository page click **Code → Download ZIP** (you must be signed in, the repo
  is private), then unzip it to `D:\kit-contact-resistance-16pin`.

### 3.3 Install the app

In Command Prompt:

```bat
cd /d D:\kit-contact-resistance-16pin\desktop-app
py -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

This installs PySide6 (the window toolkit), pyserial (USB serial), pyqtgraph and numpy (live plot) into a
private folder `.venv`, so it doesn't touch the rest of your system.

### 3.4 Start it and try the simulator

- Double-click **`run_app.bat`** in the `desktop-app` folder, or
- in Command Prompt (with `.venv` activated): `python -m crkit_app`, or
- in VS Code: open the `desktop-app` folder, pick the `.venv` interpreter (Ctrl+Shift+P → *Python: Select Interpreter*), open `run.py` and press F5.

To check everything works before the hardware is ready: in **Port**, choose **Simulator (no hardware)** and
click **Connect**. A simulated kit runs a plug/unplug cycle every 3 s and the table, plot and tiles fill in.
Try **Start recording** too: a CSV appears in `Documents\CR-TEST`.

## 4. Upload the firmware to the ESP32

1. Install **Arduino IDE 2** (arduino.cc/en/software).
2. **Board package:** Tools → Board → Boards Manager → search **esp32** → install **"esp32 by Espressif Systems"**.
3. **Library:** Tools → Manage Libraries → search **Adafruit ADS1X15** → Install (accept *Install all* so
   Adafruit BusIO comes too).
4. Open `firmware\crkit_esp32\crkit_esp32.ino`.
5. Tools → Board → esp32 → **ESP32 Dev Module**. Tools → Port → the COM port from section 2.
6. **Close the desktop app** (only one program can use the COM port), then click **Upload** (→ arrow).
   - If it stops at `Connecting....___` with "Wrong boot mode": hold the **BOOT** button on the ESP32
     until the upload starts, then let go.
7. Check it: Tools → Serial Monitor, set **115200 baud** and *Newline*. Press the **EN** button on the
   board. You should see:
   ```
   # CR-TEST kit ready. Send STATUS, SCAN or MEASURE.
   HELLO,CRKIT,0.1.0,101,0
   ```
   If you see `# ERROR: ADS1115 not found`, check the I²C wiring and the 3.3 V analog rail.
8. Close the Serial Monitor before starting the desktop app.

## 5. Connect, calibrate and run a test

### 5.1 Connect

1. Power the kit (adapter), then plug in the USB cable.
2. Start the app. In **Port**, pick the entry marked **← ESP32** and click **Connect**.
3. The top line should show `Kit firmware 0.1.0 · gain 101 · cycle counter …`.
4. Under **Kit control**, set **INA333 gain** to the same value as jumper **JP1** on the main board
   (G101 for normal contacts) and click **Set gain**.

### 5.2 Calibrate (once per kit, and after any hardware change)

1. **Zero:** in place of the connector, fit the shorting bar so that force and sense are shorted together at
   both jack boards. Click **Calibrate zero…** → Yes. Each pin's residual reading is stored as its offset.
2. **Gain:** fit a 4-terminal reference shunt (e.g. 10.0 mΩ) on pin 1. Click **Calibrate with shunt…** and
   enter its value.
3. Check: with the shunt still fitted, click **Measure only**. Pin 1 should read the shunt value within about ±2 %.

Calibration is stored in the ESP32 and survives power-off. **Clear calibration** resets it.

### 5.3 Run a life test

1. Fit the connector pair (RP16-T on the male board, RS16P-T on the female board).
2. Fill in **Sample ID**, **Operator**, **Notes**. Check **Fail limit** (default 10 mΩ, the datasheet value
   after conditioning) and **Fail after** (default 3 scans in a row).
3. Click **Start recording**. If asked, reset the kit's cycle counter to 0 for a new sample.
4. Plug and unplug the connector. With the mate-detect switch fitted and
   *Scan when the mate switch closes* ticked, every mating counts a cycle and scans all 16 pins
   (about 1 s). Without a switch, click **Scan now** after each mating.
5. Watch the table (status **OK / WEAR / OPEN / FAIL**), the plot (click a row to highlight that pin) and
   the tiles. The laptop beeps when a pin fails.
6. Click **Stop recording** when done, and **Export summary…** for a one-row-per-pin table.

### 5.4 Where the data goes

`Documents\CR-TEST\<sample>_<date>_<time>.csv` (change it in **Save to**). It opens directly in Excel:

```
# CR-TEST contact resistance log
# sample: RP16-T #1
# operator: ...
timestamp,cycle,pin,current_A,voltage_mV,r_mOhm,flag,trigger
2026-11-19T09:12:03.512,1,1,0.6203,1.8340,2.9577,OK,MATE
```

The file is saved after every scan, so a crash or power cut loses at most the scan in progress.

**Continuing a test another day:** click **Resume from file…**, pick the CSV, and let the app set the kit's
cycle counter to the last cycle in the file. New readings are added to the same file.

### 5.5 Check the installation (optional)

```bat
cd /d D:\kit-contact-resistance-16pin\desktop-app
.venv\Scripts\activate
python -m unittest discover tests
```

All 10 tests should pass.

## 6. Optional: stand-alone CR-TEST.exe

To run the app on another laptop without installing Python:

```bat
cd /d D:\kit-contact-resistance-16pin\desktop-app
.venv\Scripts\activate
pip install pyinstaller
pyinstaller --noconfirm --windowed --name CR-TEST --collect-all pyqtgraph run.py
```

Copy the whole `dist\CR-TEST` folder to the other laptop and run `CR-TEST.exe`. That laptop still needs
the USB driver from section 2.

---

## Troubleshooting

| What you see | What to do |
| --- | --- |
| No **← ESP32** port in the list | Click **Refresh ports**. Check Device Manager (section 2). Swap to a known data cable. |
| `Could not open COM5: Access is denied` | Another program has the port: close the Arduino Serial Monitor or another app window. |
| Connected, but no `Kit firmware …` line | Press **EN** on the ESP32, or type `STATUS` in the console. If still nothing, re-upload the firmware (section 4). |
| Every pin shows **OPEN** | The 5 V adapter is off, a ribbon cable is unplugged, or the connector is not mated. |
| Pins show **OVER** | Resistance is above the range for this gain. Set JP1 to G11 and click **Set gain** with 11. |
| Pins show **UNDER** | Reading below about 1 mΩ at G101: normal right after a zero calibration with the shorting bar. |
| Status bar: *5 V rail reads …* | The adapter is too weak or the barrel jack is loose. Use a 5 V 2 A adapter. |
| Readings jump around | Check the ribbon cables are fully seated, keep them away from the 5 W resistors, recalibrate. |
| Upload fails: `Wrong boot mode` | Hold **BOOT** while uploading (section 4, step 6). |
| `PySide6 is not installed` | The virtual environment is not active: run `.venv\Scripts\activate`, or use `run_app.bat`. |

## macOS and Linux

- Steps 3–5 are the same with `python3` instead of `py`, and `source .venv/bin/activate` instead of
  `.venv\Scripts\activate`.
- The port is called `/dev/cu.SLAB_USBtoUART` or `/dev/cu.usbserial-…` (macOS), or `/dev/ttyUSB0` (Linux).
- Linux: add yourself to the serial group once, then log out and back in:
  `sudo usermod -aG dialout $USER`.
