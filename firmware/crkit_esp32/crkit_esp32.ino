/*
  CR-TEST kit firmware  (ESP32-DevKitC V4)
  Measures the mated contact resistance of all 16 contacts of an
  ITW McMurdo RP16-T / RS16P-T connector and streams the results over USB serial.

  Protocol: docs/serial-protocol.md   (115200 baud, one line per message)
  Hardware: docs/design.md            (pin map, measurement chain)

  Libraries (Arduino IDE > Library Manager):
    - Adafruit ADS1X15  (by Adafruit, installs Adafruit BusIO too)
  Board package: "esp32" by Espressif Systems (2.x or 3.x)
*/

#include <Wire.h>
#include <Adafruit_ADS1X15.h>
#include <Preferences.h>

#define FW_VERSION "0.4.0"

// ---------------- pin map (docs/design.md) ----------------
const int PIN_SR_DATA  = 23;   // 74HC595 SER
const int PIN_SR_CLK   = 18;   // 74HC595 SRCLK
const int PIN_SR_LATCH = 5;    // 74HC595 RCLK
const int PIN_SR_OE    = 19;   // 74HC595 /OE  (pull-up on board, LOW = outputs on)
const int PIN_MUX_S[4] = {25, 26, 27, 14};
const int PIN_MUX_EN   = 13;   // CD74HC4067 /E (pull-up on board, LOW = enabled)
const int PIN_I_EN     = 32;   // HIGH = test current on
const int PIN_ADC_RDY  = 4;    // ADS1115 ALERT/RDY (not used, polled over I2C)
const int PIN_MATE     = 33;   // mate-detect switch to GND, LOW = mated
const int PIN_LED      = 17;

// ---------------- measurement constants ----------------
const int   NPINS          = 16;
const float ACS_SENS_5V    = 0.185f;   // V/A at a 5.000 V supply (ACS712-05B)
const float INA_RAIL_HI    = 3.20f;    // V, above this the INA333 output is clipped
const float INA_RAIL_LO    = 0.06f;    // V, below this the INA333 output is clipped
const float I_OPEN_LIMIT   = 0.20f;    // A, below this the contact is treated as open
const float I_OVER_LIMIT   = 0.75f;    // A, above this the force path bypasses R_LO (short to GND): switch off
const float ISO_LIMIT_UV   = 50.0f;    // uV on an undriven pin's contact (above its own current-off baseline) = shorted to the driven pin.
                                       // 16 pins all shorted give only ~85-110 uV, so 150 uV (fw 0.3) missed that case.
const float R_LOW_LIMIT    = 0.8f;     // mOhm, a reading below this is not a real contact: flag LOW (possible short)
const float V5_MIN = 4.6f, V5_MAX = 5.4f;
// Board rev B: INA333 REF sits at ~0.25 V (buffered divider), read on ADS1115 AIN3, so the
// amplifier can show contact voltages down to zero. On a rev A board (REF = GND) AIN3 reads ~0.
const int   SAMPLES_ZERO   = 16;
const int   SAMPLES_PIN    = 8;
const int   SETTLE_MS      = 5;        // after switching the current on
const unsigned long MATE_SETTLE_MS = 200;
const unsigned long DEBOUNCE_MS    = 50;

Adafruit_ADS1115 ads;
Preferences prefs;

int   inaGain = 101;
bool  autoMode = true;
long  cycleCount = 0;
float zeroOffset[NPINS];   // mOhm, subtracted from each reading
float gainCorr = 1.0f;     // multiplies each reading
float vRef = 0.0f;         // INA333 REF voltage, read at the start of each scan
bool  isoEnabled = true;   // run the isolation (short) test after every scan
bool  alarmed = false;     // an ALARM stopped this scan

// ---------------- low-level helpers ----------------
void shiftPins(uint16_t bits) {             // bit n-1 = MOSFET Qn
  digitalWrite(PIN_SR_LATCH, LOW);
  shiftOut(PIN_SR_DATA, PIN_SR_CLK, MSBFIRST, (bits >> 8) & 0xFF);   // goes to U3 (Q9-Q16)
  shiftOut(PIN_SR_DATA, PIN_SR_CLK, MSBFIRST, bits & 0xFF);          // stays in U2 (Q1-Q8)
  digitalWrite(PIN_SR_LATCH, HIGH);
}

void allOff() {
  digitalWrite(PIN_I_EN, LOW);
  shiftPins(0);
}

void selectMux(int ch) {                     // ch 0..15 = pin 1..16
  for (int b = 0; b < 4; b++) digitalWrite(PIN_MUX_S[b], (ch >> b) & 1);
}

float readVolts(int ch, int samples) {
  float sum = 0;
  for (int i = 0; i < samples; i++) sum += ads.computeVolts(ads.readADC_SingleEnded(ch));
  return sum / samples;
}

void loadSettings() {
  prefs.begin("crkit", true);
  inaGain    = prefs.getInt("gain", 101);
  autoMode   = prefs.getBool("auto", true);
  cycleCount = prefs.getLong("cycle", 0);
  gainCorr   = prefs.getFloat("gcorr", 1.0f);
  for (int p = 0; p < NPINS; p++) {
    char key[8]; snprintf(key, sizeof key, "z%d", p);
    zeroOffset[p] = prefs.getFloat(key, 0.0f);
  }
  prefs.end();
}

void saveInt(const char* k, int v)     { prefs.begin("crkit", false); prefs.putInt(k, v);   prefs.end(); }
void saveBool(const char* k, bool v)   { prefs.begin("crkit", false); prefs.putBool(k, v);  prefs.end(); }
void saveLong(const char* k, long v)   { prefs.begin("crkit", false); prefs.putLong(k, v);  prefs.end(); }
void saveFloat(const char* k, float v) { prefs.begin("crkit", false); prefs.putFloat(k, v); prefs.end(); }

void sayHello() {
  Serial.printf("HELLO,CRKIT,%s,%d,%ld\n", FW_VERSION, inaGain, cycleCount);
}

// ---------------- one pin ----------------
struct Reading { float i, vmv, rraw, r, rmin; const char* flag; };

Reading measurePin(int p, float v0, float v5) {
  Reading rd;
  selectMux(p);
  shiftPins(1u << p);
  delay(1);
  digitalWrite(PIN_I_EN, HIGH);                // current pulse starts (about 25 ms)
  delay(SETTLE_MS);
  float sens = ACS_SENS_5V * (v5 / 5.0f);      // ACS712 is ratiometric to its supply
  float iNow = (ads.computeVolts(ads.readADC_SingleEnded(0)) - v0) / sens;
  if (iNow > I_OVER_LIMIT) {                   // force path shorted past R_LO: stop at once
    digitalWrite(PIN_I_EN, LOW);
    shiftPins(0);
    rd.i = iNow; rd.vmv = NAN; rd.rraw = NAN; rd.r = NAN; rd.rmin = NAN; rd.flag = "OPEN";
    Serial.printf("ALARM,%ld,OVERCURRENT,%.3f A on pin %d: test current switched off, scan stopped. Check for a pin shorted to GND or chassis.\n", cycleCount, iNow, p + 1);
    alarmed = true;
    return rd;
  }
  float va = 0, vi = 0, rminRaw = INFINITY;
  for (int s = 0; s < SAMPLES_PIN; s++) {      // interleave so both see the same moment
    float vas = ads.computeVolts(ads.readADC_SingleEnded(0));
    float vis = ads.computeVolts(ads.readADC_SingleEnded(1));
    va += vas; vi += vis;
    float is = (vas - v0) / sens;              // this sample's own R, to find the lowest of the 8
    if (is > I_OPEN_LIMIT) { float rs = ((vis - vRef) / inaGain) / is * 1000.0f; if (rs < rminRaw) rminRaw = rs; }
  }
  digitalWrite(PIN_I_EN, LOW);                 // current pulse ends
  shiftPins(0);
  va /= SAMPLES_PIN; vi /= SAMPLES_PIN;

  rd.i   = (va - v0) / sens;
  float vc = (vi - vRef) / inaGain;            // contact voltage, V
  rd.vmv = vc * 1000.0f;
  rd.rraw = (rd.i >= I_OPEN_LIMIT) ? vc / rd.i * 1000.0f : NAN;   // mOhm, none when open
  rd.r   = (rd.rraw - zeroOffset[p]) * gainCorr;
  rd.rmin = isinf(rminRaw) ? NAN : (rminRaw - zeroOffset[p]) * gainCorr;

  if (rd.i < I_OPEN_LIMIT)      rd.flag = "OPEN";
  else if (vi >= INA_RAIL_HI)   rd.flag = "OVER";
  else if (vi <= INA_RAIL_LO)   rd.flag = "UNDER";
  else if (rd.r < R_LOW_LIMIT)  rd.flag = "LOW";    // below any real contact: two or more pins shorted
  else                          rd.flag = "OK";
  return rd;
}

// ---------------- isolation (short) test ----------------
// Drive pin a, then read the contact voltage of every other pin b. With no short, no current
// flows through contact b and its voltage is ~0. If b is shorted to a (on the plug side or on a
// board), part of the test current returns through contact b and its voltage rises.
void isolationTest(float v0, float v5) {
  int found = 0;
  bool seen[NPINS][NPINS] = {};
  float sens = ACS_SENS_5V * (v5 / 5.0f);
  // Baseline: every channel's reading with the current off. Subtracting it removes the INA333
  // offset (up to 25 uV) and thermal EMFs, which matter now that the limit is 50 uV.
  float base[NPINS];
  shiftPins(0);
  digitalWrite(PIN_I_EN, LOW);
  for (int b = 0; b < NPINS; b++) {
    selectMux(b);
    delayMicroseconds(200);
    float acc = 0;
    for (int k = 0; k < 4; k++) acc += ads.computeVolts(ads.readADC_SingleEnded(1));
    base[b] = (acc / 4 - vRef) / inaGain * 1e6f;
  }
  for (int a = 0; a < NPINS && !alarmed; a++) {
    shiftPins(1u << a);
    delay(1);
    digitalWrite(PIN_I_EN, HIGH);
    delay(SETTLE_MS);
    float ia = (ads.computeVolts(ads.readADC_SingleEnded(0)) - v0) / sens;
    if (ia > I_OVER_LIMIT) {
      digitalWrite(PIN_I_EN, LOW); shiftPins(0);
      Serial.printf("ALARM,%ld,OVERCURRENT,%.3f A driving pin %d in the isolation test: current switched off.\n", cycleCount, ia, a + 1);
      alarmed = true; break;
    }
    if (ia >= I_OPEN_LIMIT) {                       // an open pin can't drive current: skip it
      for (int b = 0; b < NPINS; b++) {
        if (b == a) continue;
        selectMux(b);
        delayMicroseconds(200);
        float vs = 0;
        for (int k = 0; k < 2; k++) vs += ads.computeVolts(ads.readADC_SingleEnded(1));
        float uv = (vs / 2 - vRef) / inaGain * 1e6f - base[b];
        if (uv > ISO_LIMIT_UV) {
          int lo = min(a, b), hi = max(a, b);
          if (!seen[lo][hi]) {
            seen[lo][hi] = true; found++;
            Serial.printf("SHORT,%ld,%d,%d,%.0f\n", cycleCount, lo + 1, hi + 1, uv);
          }
        }
      }
    }
    digitalWrite(PIN_I_EN, LOW);
    shiftPins(0);
  }
  Serial.printf("ISO,%ld,%d\n", cycleCount, found);
}

// ---------------- full scan ----------------
// countIt: add 1 to the cycle counter first. raw[]: optional, receives uncalibrated readings.
void runScan(const char* trigger, bool countIt, float* raw = nullptr, int onlyPin = -1) {
  unsigned long t0 = millis();
  if (countIt) { cycleCount++; saveLong("cycle", cycleCount); }
  digitalWrite(PIN_LED, HIGH);
  digitalWrite(PIN_MUX_EN, LOW);
  allOff();
  delay(2);
  float v0 = readVolts(0, SAMPLES_ZERO);       // ACS712 zero, no current flowing
  float v5 = readVolts(2, 4) * 2.0f;           // 5 V rail through the 10k/10k divider
  vRef = readVolts(3, 4);                       // INA333 REF (rev B: ~0.25 V; rev A: 0 V)
  alarmed = false;
  Serial.printf("CYCLE,%ld,%s\n", cycleCount, trigger);
  Serial.printf("ZERO,%ld,%.4f,%.3f\n", cycleCount, v0, v5);
  if (v5 < V5_MIN || v5 > V5_MAX)
    Serial.printf("ALARM,%ld,SUPPLY,5 V rail reads %.2f V (expected %.1f-%.1f V)\n", cycleCount, v5, V5_MIN, V5_MAX);
  for (int p = 0; p < NPINS && !alarmed; p++) {
    if (onlyPin >= 0 && p != onlyPin) continue;
    Reading rd = measurePin(p, v0, v5);
    if (raw) raw[p] = rd.rraw;
    if (alarmed) break;
    Serial.printf("DATA,%ld,%d,%.4f,%.4f,%.4f,%s,%.4f\n", cycleCount, p + 1, rd.i, rd.vmv, rd.r, rd.flag, rd.rmin);
  }
  if (isoEnabled && onlyPin < 0 && !alarmed) isolationTest(v0, v5);
  allOff();
  digitalWrite(PIN_MUX_EN, HIGH);
  digitalWrite(PIN_LED, LOW);
  Serial.printf("END,%ld,%lu\n", cycleCount, millis() - t0);
}

// ---------------- commands ----------------
void handleCommand(String line) {
  line.trim();
  if (line.length() == 0) return;
  String cmd = line, arg = "";
  int sp = line.indexOf(' ');
  if (sp > 0) { cmd = line.substring(0, sp); arg = line.substring(sp + 1); arg.trim(); }
  cmd.toUpperCase();

  if (cmd == "STATUS") { sayHello(); }
  else if (cmd == "SCAN")    { Serial.println("OK,SCAN");    runScan("MANUAL", true); }
  else if (cmd == "MEASURE") { Serial.println("OK,MEASURE"); runScan("MANUAL", false); }
  else if (cmd == "SETCYCLE") {
    long n = arg.toInt();
    if (n < 0) { Serial.println("ERR,cycle must be 0 or more"); return; }
    cycleCount = n; saveLong("cycle", n); Serial.println("OK,SETCYCLE");
  }
  else if (cmd == "GAIN") {
    int g = arg.toInt();
    if (g != 11 && g != 101 && g != 1001) { Serial.println("ERR,gain must be 11, 101 or 1001"); return; }
    inaGain = g; saveInt("gain", g); Serial.println("OK,GAIN");
  }
  else if (cmd == "AUTO") {
    autoMode = arg.toInt() != 0; saveBool("auto", autoMode); Serial.println("OK,AUTO");
  }
  else if (cmd == "ISO") {
    isoEnabled = arg.toInt() != 0; Serial.println("OK,ISO");
  }
  else if (cmd == "CALZERO") {
    float raw[NPINS];
    for (int p = 0; p < NPINS; p++) zeroOffset[p] = 0;
    runScan("MANUAL", false, raw);
    prefs.begin("crkit", false);
    for (int p = 0; p < NPINS; p++) {
      zeroOffset[p] = isnan(raw[p]) ? 0 : raw[p];
      char key[8]; snprintf(key, sizeof key, "z%d", p);
      prefs.putFloat(key, zeroOffset[p]);
    }
    prefs.end();
    Serial.println("OK,CALZERO");
  }
  else if (cmd == "CALREF") {
    float ref = arg.toFloat();
    if (ref <= 0) { Serial.println("ERR,give the reference value in mOhm, e.g. CALREF 10.0"); return; }
    float raw[NPINS];
    gainCorr = 1.0f;
    runScan("MANUAL", false, raw, 0);
    float meas = raw[0] - zeroOffset[0];
    if (isnan(meas) || meas <= 0.1f) { Serial.println("ERR,reading on pin 1 is not valid"); return; }
    gainCorr = ref / meas; saveFloat("gcorr", gainCorr);
    Serial.printf("# gain correction = %.4f\n", gainCorr);
    Serial.println("OK,CALREF");
  }
  else if (cmd == "CALCLEAR") {
    gainCorr = 1.0f; saveFloat("gcorr", 1.0f);
    prefs.begin("crkit", false);
    for (int p = 0; p < NPINS; p++) { zeroOffset[p] = 0; char key[8]; snprintf(key, sizeof key, "z%d", p); prefs.putFloat(key, 0); }
    prefs.end();
    Serial.println("OK,CALCLEAR");
  }
  else { Serial.printf("ERR,unknown command %s\n", cmd.c_str()); }
}

// ---------------- setup / loop ----------------
void setup() {
  pinMode(PIN_I_EN, OUTPUT);     digitalWrite(PIN_I_EN, LOW);     // current off first
  pinMode(PIN_SR_OE, OUTPUT);    digitalWrite(PIN_SR_OE, HIGH);   // outputs off while clearing
  pinMode(PIN_SR_DATA, OUTPUT);  pinMode(PIN_SR_CLK, OUTPUT);  pinMode(PIN_SR_LATCH, OUTPUT);
  shiftPins(0);
  digitalWrite(PIN_SR_OE, LOW);                                    // now safe to enable
  for (int b = 0; b < 4; b++) pinMode(PIN_MUX_S[b], OUTPUT);
  pinMode(PIN_MUX_EN, OUTPUT);   digitalWrite(PIN_MUX_EN, HIGH);
  pinMode(PIN_MATE, INPUT_PULLUP);
  pinMode(PIN_ADC_RDY, INPUT);
  pinMode(PIN_LED, OUTPUT);      digitalWrite(PIN_LED, LOW);

  Serial.begin(115200);
  delay(200);
  loadSettings();

  Wire.begin(21, 22);
  if (!ads.begin(0x48)) {
    Serial.println("# ERROR: ADS1115 not found at 0x48. Check I2C wiring and +3V3A.");
  }
  ads.setGain(GAIN_ONE);                     // +/-4.096 V, 125 uV per bit
  ads.setDataRate(RATE_ADS1115_860SPS);
  Serial.println("# CR-TEST kit ready. Send STATUS, SCAN or MEASURE.");
  sayHello();
}

void loop() {
  static String buf;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') { if (buf.length()) handleCommand(buf); buf = ""; }
    else if (buf.length() < 64) buf += c;
  }

  // mate detect: HIGH -> LOW (stable for DEBOUNCE_MS) = connector just mated
  static int lastStable = HIGH, lastRead = HIGH;
  static unsigned long changedAt = 0;
  int now = digitalRead(PIN_MATE);
  if (now != lastRead) { lastRead = now; changedAt = millis(); }
  if (millis() - changedAt > DEBOUNCE_MS && now != lastStable) {
    lastStable = now;
    if (now == LOW && autoMode) {
      delay(MATE_SETTLE_MS);
      runScan("MATE", true);
    }
  }
}
