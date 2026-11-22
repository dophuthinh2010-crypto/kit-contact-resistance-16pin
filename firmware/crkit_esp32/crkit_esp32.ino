/*
  CR-TEST kit firmware  (ESP32-DevKitC V4), main board rev C
  Measures the mated contact resistance of all 16 contacts of an
  ITW McMurdo RP16-T / RS16P-T connector and streams the results over USB serial.

  Rev C measurement chain:
    LM317T + 2.0 ohm R_SET  -> constant 0.625 A into F_BUS (female side of every contact)
    Qn (AO3400A) on         -> current returns through contact n and the 0.1 ohm shunt R_SH
    2x CD4053B mux trees    -> select the Kelvin taps either side of contact n
    ADS1115 AIN0-AIN1       -> contact voltage, differential, PGA +-0.256 V (7.8 uV per step)
    ADS1115 AIN2-AIN3       -> shunt voltage, so I = V_SH / 0.1 ohm
    R = (V_contact(on) - V_contact(off)) / I   (the current-off reading removes offsets and thermal EMF)

  Protocol: docs/serial-protocol.md   (115200 baud, one line per message)
  Hardware: docs/design.md, hardware/kicad/README.md

  Libraries (Arduino IDE > Library Manager):
    - Adafruit ADS1X15  (by Adafruit, installs Adafruit BusIO too)
  Board package: "esp32" by Espressif Systems (2.x or 3.x)
*/

#include <Wire.h>
#include <Adafruit_ADS1X15.h>
#include <Preferences.h>

#define FW_VERSION "0.5.0"

// ---------------- pin map (docs/design.md) ----------------
const int PIN_SR_DATA  = 23;   // 74HC595 SER
const int PIN_SR_CLK   = 18;   // 74HC595 SRCLK
const int PIN_SR_LATCH = 5;    // 74HC595 RCLK
const int PIN_SR_OE    = 19;   // 74HC595 /OE  (pull-up on board, LOW = outputs on)
const int PIN_MUX_S[4] = {25, 26, 27, 14};   // CD4053B tree levels 1-4: channel n = binary n-1
const int PIN_MUX_EN   = 13;   // CD4053B INH, all ten chips (pull-up on board, LOW = enabled)
const int PIN_I_EN     = 32;   // HIGH = test current on (Q_EN feeds the LM317T)
const int PIN_ADC_RDY  = 4;    // ADS1115 ALERT/RDY (not used, polled over I2C)
const int PIN_MATE     = 33;   // mate-detect switch to GND, LOW = mated
const int PIN_LED      = 17;
const int PIN_V5_MON   = 34;   // 5 V rail through a 10k/10k divider (input-only ADC1 pin)

// ---------------- measurement constants ----------------
const int   NPINS          = 16;
const float R_SHUNT        = 0.100f;   // ohm, R_SH (1 %, calibrate with CALREF for better)
const float I_NOMINAL      = 0.625f;   // A, 1.25 V / 2.0 ohm
const float I_OPEN_LIMIT   = 0.20f;    // A, below this the contact is treated as open
const float I_LOW_LIMIT    = 0.55f;    // A, below this the LM317T is out of headroom (supply low or path resistance high)
const float I_OVER_LIMIT   = 0.75f;    // A, the LM317T cannot give this: something is wrong, switch off
const float V_FSR          = 0.256f;   // V, ADS1115 PGA range used for both channels
const float V_OVER         = 0.250f;   // V, contact voltage above this = over range (R > ~400 mOhm)
const float ISO_LIMIT_UV   = 50.0f;    // uV on an undriven pin's contact above its current-off baseline = shorted to the driven pin
const float R_LOW_LIMIT    = 0.8f;     // mOhm, a reading below this is not a real contact: flag LOW (pins shorted)
const float V5_MIN = 4.6f, V5_MAX = 5.4f;
const int   SAMPLES_OFF    = 4;        // current-off readings per pin
const int   SAMPLES_PIN    = 8;        // current-on readings per pin
const int   SETTLE_MS      = 3;        // after switching the current on (LM317T settles in < 1 ms)
const int   MUX_SETTLE_US  = 300;      // after changing the mux (10 k + CD4053B Ron + 100 nF filter)
const unsigned long MATE_SETTLE_MS = 200;
const unsigned long DEBOUNCE_MS    = 50;

Adafruit_ADS1115 ads;
Preferences prefs;

bool  autoMode = true;
long  cycleCount = 0;
float zeroOffset[NPINS];   // mOhm, subtracted from each reading (fixture and lead resistance)
float gainCorr = 1.0f;     // multiplies each reading (shunt tolerance, mux and filter resistance)
float vShZero = 0.0f;      // V, shunt channel offset with the current off, read at the start of each scan
bool  isoEnabled = true;   // run the isolation (short) test after every scan
bool  alarmed = false;     // an ALARM stopped this scan

// ---------------- low-level helpers ----------------
void shiftPins(uint16_t bits) {             // bit n-1 = MOSFET Qn
  digitalWrite(PIN_SR_LATCH, LOW);
  shiftOut(PIN_SR_DATA, PIN_SR_CLK, MSBFIRST, (bits >> 8) & 0xFF);   // goes on to U4 (contacts 9-16)
  shiftOut(PIN_SR_DATA, PIN_SR_CLK, MSBFIRST, bits & 0xFF);          // stays in U3 (contacts 1-8)
  digitalWrite(PIN_SR_LATCH, HIGH);
}

void allOff() {
  digitalWrite(PIN_I_EN, LOW);
  shiftPins(0);
}

void selectMux(int ch) {                     // ch 0..15 = pin 1..16
  for (int b = 0; b < 4; b++) digitalWrite(PIN_MUX_S[b], (ch >> b) & 1);
}

float vContact() { return ads.computeVolts(ads.readADC_Differential_0_1()); }   // V, AIN0-AIN1
float vShunt()   { return ads.computeVolts(ads.readADC_Differential_2_3()); }   // V, AIN2-AIN3

float avgContact(int n) { float s = 0; for (int i = 0; i < n; i++) s += vContact(); return s / n; }
float avgShunt(int n)   { float s = 0; for (int i = 0; i < n; i++) s += vShunt();   return s / n; }

float readV5() { return analogReadMilliVolts(PIN_V5_MON) * 2.0f / 1000.0f; }

void loadSettings() {
  prefs.begin("crkit", true);
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
  Serial.printf("HELLO,CRKIT,%s,%d,%ld\n", FW_VERSION, 16, cycleCount);   // 16 = ADS1115 PGA gain (+-0.256 V); rev C has no amplifier jumper
}

// ---------------- one pin ----------------
struct Reading { float i, vmv, rraw, r, rmin; const char* flag; };

Reading measurePin(int p) {
  Reading rd;
  shiftPins(0);
  selectMux(p);
  delayMicroseconds(MUX_SETTLE_US);
  float vOff = avgContact(SAMPLES_OFF);        // no current: ADS offset + thermal EMF of this channel
  shiftPins(1u << p);
  delay(1);
  digitalWrite(PIN_I_EN, HIGH);                // current pulse starts (about 40 ms)
  delay(SETTLE_MS);
  float iNow = (vShunt() - vShZero) / R_SHUNT;
  if (iNow > I_OVER_LIMIT) {                   // the LM317T can't give this: switch off at once
    digitalWrite(PIN_I_EN, LOW);
    shiftPins(0);
    rd.i = iNow; rd.vmv = NAN; rd.rraw = NAN; rd.r = NAN; rd.rmin = NAN; rd.flag = "OPEN";
    Serial.printf("ALARM,%ld,OVERCURRENT,%.3f A on pin %d: test current switched off, scan stopped. Check the LM317T and R_SET.\n", cycleCount, iNow, p + 1);
    alarmed = true;
    return rd;
  }
  float vc = 0, vs = 0, rminRaw = INFINITY;
  for (int s = 0; s < SAMPLES_PIN; s++) {      // interleave so both see the same moment
    float vcs = vContact() - vOff;
    float vss = vShunt() - vShZero;
    vc += vcs; vs += vss;
    float is = vss / R_SHUNT;                  // this sample's own R, to find the lowest of the 8
    if (is > I_OPEN_LIMIT) { float rs = vcs / is * 1000.0f; if (rs < rminRaw) rminRaw = rs; }
  }
  digitalWrite(PIN_I_EN, LOW);                 // current pulse ends
  shiftPins(0);
  vc /= SAMPLES_PIN; vs /= SAMPLES_PIN;

  rd.i    = vs / R_SHUNT;
  rd.vmv  = vc * 1000.0f;
  rd.rraw = (rd.i >= I_OPEN_LIMIT) ? vc / rd.i * 1000.0f : NAN;   // mOhm, none when open
  rd.r    = (rd.rraw - zeroOffset[p]) * gainCorr;
  rd.rmin = isinf(rminRaw) ? NAN : (rminRaw - zeroOffset[p]) * gainCorr;

  if (rd.i < I_OPEN_LIMIT)      rd.flag = "OPEN";
  else if (vc >= V_OVER)        rd.flag = "OVER";
  else if (rd.r < R_LOW_LIMIT)  rd.flag = "LOW";    // below any real contact: two or more pins shorted
  else                          rd.flag = "OK";
  return rd;
}

// ---------------- isolation (short) test ----------------
// Drive pin a, then read the contact voltage of every other pin b. With no short, no current
// flows through contact b and its voltage is ~0. If b is shorted to a (on the plug side or on a
// board), part of the test current returns through contact b and its voltage rises.
void isolationTest() {
  int found = 0;
  bool seen[NPINS][NPINS] = {};
  // Baseline: every channel's reading with the current off (ADS offset and thermal EMF).
  float base[NPINS];
  shiftPins(0);
  digitalWrite(PIN_I_EN, LOW);
  for (int b = 0; b < NPINS; b++) {
    selectMux(b);
    delayMicroseconds(MUX_SETTLE_US);
    base[b] = avgContact(4) * 1e6f;
  }
  for (int a = 0; a < NPINS && !alarmed; a++) {
    shiftPins(1u << a);
    delay(1);
    digitalWrite(PIN_I_EN, HIGH);
    delay(SETTLE_MS);
    float ia = (vShunt() - vShZero) / R_SHUNT;
    if (ia > I_OVER_LIMIT) {
      digitalWrite(PIN_I_EN, LOW); shiftPins(0);
      Serial.printf("ALARM,%ld,OVERCURRENT,%.3f A driving pin %d in the isolation test: current switched off.\n", cycleCount, ia, a + 1);
      alarmed = true; break;
    }
    if (ia >= I_OPEN_LIMIT) {                       // an open pin can't drive current: skip it
      for (int b = 0; b < NPINS; b++) {
        if (b == a) continue;
        selectMux(b);
        delayMicroseconds(MUX_SETTLE_US);
        float uv = avgContact(2) * 1e6f - base[b];
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
  vShZero = avgShunt(8);                       // shunt offset, no current flowing
  float v5 = readV5();                         // 5 V rail through the 10k/10k divider on IO34
  alarmed = false;
  Serial.printf("CYCLE,%ld,%s\n", cycleCount, trigger);
  Serial.printf("ZERO,%ld,%.6f,%.3f\n", cycleCount, vShZero, v5);   // shunt offset (V), 5 V rail (V)
  if (v5 < V5_MIN || v5 > V5_MAX)
    Serial.printf("ALARM,%ld,SUPPLY,5 V rail reads %.2f V (expected %.1f-%.1f V)\n", cycleCount, v5, V5_MIN, V5_MAX);
  for (int p = 0; p < NPINS && !alarmed; p++) {
    if (onlyPin >= 0 && p != onlyPin) continue;
    Reading rd = measurePin(p);
    if (raw) raw[p] = rd.rraw;
    if (alarmed) break;
    Serial.printf("DATA,%ld,%d,%.4f,%.4f,%.4f,%s,%.4f\n", cycleCount, p + 1, rd.i, rd.vmv, rd.r, rd.flag, rd.rmin);
    if (rd.i >= I_OPEN_LIMIT && rd.i < I_LOW_LIMIT)
      Serial.printf("# pin %d: test current only %.3f A (LM317T out of headroom: check the 5 V supply)\n", p + 1, rd.i);
  }
  if (isoEnabled && onlyPin < 0 && !alarmed) isolationTest();
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
    Serial.println("ERR,board rev C has no gain setting: the ADS1115 always runs at +-0.256 V");
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
  ads.setGain(GAIN_SIXTEEN);                 // +/-0.256 V, 7.8125 uV per bit
  ads.setDataRate(RATE_ADS1115_475SPS);      // ~2 ms per reading, about 2.5 s per scan with the isolation test
  analogSetPinAttenuation(PIN_V5_MON, ADC_11db);
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
