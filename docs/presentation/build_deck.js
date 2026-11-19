const pptxgen = require("pptxgenjs");
const React = require("react");
const RDS = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");
const fs = require("fs");
const { applyTheme } = require("/root/.claude/skills/synced/30416aeb-646b-4891-82d4-792de9d0a6cc_0056ff56-53fe-4310-98a3-a4cf17b3062c/pptx/scripts/apply_theme.js");

const data = JSON.parse(fs.readFileSync("deckdata.json"));
const HEX = { ink: "1B1F24", slate: "2B3440", paper: "FFFFFF", mist: "F1F3F5", red: "C8102E", grid: "DDE1E6", muted: "6B7785" };
const THEME = {
  name: "CR-TEST Red Range",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: HEX.ink, lt1: HEX.paper, dk2: HEX.slate, lt2: HEX.mist,
    accent1: HEX.red, accent2: "3A4A5C", accent3: "E8A33D", accent4: "2E8B57",
    accent5: HEX.muted, accent6: "9AA5B1", hlink: HEX.red, folHlink: "7A0A1C",
  },
};

async function icon(Comp, color, size = 256) {
  const svg = RDS.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size: String(size) }));
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  pres.title = "CR-TEST 16-pin blindmate contact resistance test kit";
  pres.author = "Thinh";
  const C = pres.SchemeColor;

  pres.defineSlideMaster({
    title: "Title dark",
    background: { color: C.text1 },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.7, y: 2.0, w: 8.2, h: 1.9, fontSize: 40, bold: true, color: C.background1, valign: "bottom", align: "left", margin: 0 }, text: "" } },
      { placeholder: { options: { name: "body", type: "body", x: 0.7, y: 4.1, w: 8.2, h: 1.0, fontSize: 18, color: "9AA5B1", valign: "top", margin: 0 }, text: "" } },
    ],
  });
  pres.defineSlideMaster({
    title: "Content",
    background: { color: C.background1 },
    margin: [0.5, 0.6, 0.6, 0.6],
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.4, w: 12.1, h: 0.85, fontSize: 32, bold: true, color: C.text1, valign: "middle", align: "left", margin: 0 }, text: "" } },
      { text: { text: "CR-TEST · RP16 contact resistance kit", options: { x: 0.6, y: 7.0, w: 6, h: 0.3, fontSize: 10, color: C.accent5, margin: 0 } } },
    ],
    slideNumber: { x: 12.2, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: C.accent5, align: "right" },
  });

  const shadow = () => ({ type: "outer", color: "000000", opacity: 0.12, blur: 6, offset: 2, angle: 90 });
  const card = (s, x, y, w, h, name, fill = C.background2) =>
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.12, fill: { color: fill }, line: { type: "none" }, objectName: name });
  async function badge(s, Comp, x, y, d = 0.62, fill = C.accent1) {
    s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { type: "none" }, objectName: "Icon circle" });
    s.addImage({ data: await icon(Comp, "FFFFFF"), x: x + d * 0.24, y: y + d * 0.24, w: d * 0.52, h: d * 0.52, altText: "icon" });
  }
  const txt = (s, t, o) => s.addText(t, { isTextBox: true, margin: 0, color: C.text1, valign: "top", ...o });

  // 1 ── Title
  pres.addSection({ title: "Overview" });
  let s = pres.addSlide({ masterName: "Title dark", sectionTitle: "Overview" });
  s.addText("Contact Resistance Test Kit for the 16-Pin Blindmate Connector", { placeholder: "title" });
  s.addText("ESP32 + 4-wire Kelvin measurement of all 16 contacts over repeated plug/unplug cycles", { placeholder: "body" });
  s.addShape(pres.shapes.OVAL, { x: 9.6, y: 1.55, w: 3.0, h: 3.0, fill: { color: C.accent1 }, line: { type: "none" }, objectName: "Motif circle" });
  s.addImage({ data: await icon(fa.FaPlug, "FFFFFF"), x: 10.35, y: 2.3, w: 1.5, h: 1.5, altText: "Connector icon" });
  txt(s, "ITW McMurdo Red Range RP16-T / RS16P-T", { x: 0.7, y: 6.3, w: 8, h: 0.4, fontSize: 14, color: "9AA5B1" });
  s.addNotes("Introduce CR-TEST: a bench kit that measures the contact resistance of all 16 contacts of the RP16 blindmate connector, cycle by cycle, to judge connector life.");

  // 2 ── Purpose & test object
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Overview" });
  s.addText("We need to know when the RP16 contacts wear out", { placeholder: "title" });
  txt(s, [
    { text: "Device under test", options: { bold: true, fontSize: 18, breakLine: true } },
    { text: "Plug RP16-T and socket RS16P-T, PC-tail version (no solder tags)", options: { fontSize: 15, bullet: true, breakLine: true, paraSpaceAfter: 6 } },
    { text: "2 rows × 8 contacts, 4.70 mm pitch, rows 9.14 mm apart", options: { fontSize: 15, bullet: true, breakLine: true, paraSpaceAfter: 6 } },
    { text: "Goal: record R of every contact on every mating cycle and flag the first failure", options: { fontSize: 15, bullet: true, breakLine: true, paraSpaceAfter: 6 } },
    { text: "Fail rule: R > 10 mΩ, or open, for 3 scans in a row", options: { fontSize: 15, bullet: true } },
  ], { x: 0.6, y: 1.6, w: 5.6, h: 4.5 });
  const stats = [["5 mΩ", "max R, new"], ["10 mΩ", "max R after conditioning"], ["500", "rated mating cycles"], ["5 A", "rated current per contact"]];
  stats.forEach(([v, l], i) => {
    const x = 6.7 + (i % 2) * 3.05, y = 1.6 + Math.floor(i / 2) * 2.35;
    card(s, x, y, 2.8, 2.05, "Stat card " + (i + 1));
    txt(s, v, { x: x + 0.25, y: y + 0.3, w: 2.3, h: 0.95, fontSize: 44, bold: true, color: C.accent1, fontFace: "Cambria" });
    txt(s, l, { x: x + 0.25, y: y + 1.3, w: 2.3, h: 0.5, fontSize: 14, color: C.text2 });
  });
  txt(s, "Data: ITW McMurdo Red Range datasheet", { x: 6.7, y: 6.4, w: 5.9, h: 0.3, fontSize: 10, color: C.accent5 });
  s.addNotes("The datasheet limits are the reference: 5 mOhm new, 10 mOhm after conditioning, 500 mechanical operations.");

  // 3 ── System concept
  pres.addSection({ title: "Design" });
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Design" });
  s.addText("One laptop, one ESP32, one fixture: the whole system", { placeholder: "title" });
  s.addImage({ path: "concept.jpg", x: 2.07, y: 1.4, w: 9.2, h: 5.75 * 0.96, altText: "System concept diagram" });
  s.addNotes("Laptop runs the CR-TEST app over USB. ESP32 controls the main board; ribbons carry force and sense lines to the two jack boards on the slide rail.");

  // 4 ── Measurement principle
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Design" });
  s.addText("Kelvin 4-wire sensing resolves milliohms", { placeholder: "title" });
  const steps = [
    [fa.FaBolt, "Force current", "5 V through R_HI 5.6 Ω + R_LO 2.2 Ω ≈ 0.627 A, switched per pin by AO3400A + 74HC595"],
    [fa.FaRandom, "Select taps", "Two CD74HC4067 muxes pick the sense taps on both sides of the contact"],
    [fa.FaSlidersH, "Amplify", "INA333, gain 101 (or 11) lifts the µV contact voltage"],
    [fa.FaMicrochip, "Digitise", "ADS1115 reads I (ACS712, AIN0) and V (AIN1), 16-bit"],
    [fa.FaCalculator, "Compute", "R = V / I. Range 0–51 mΩ at gain 101"],
  ];
  for (let i = 0; i < steps.length; i++) {
    const x = 0.6 + i * 2.48;
    card(s, x, 1.7, 2.28, 3.9, "Step card " + (i + 1));
    await badge(s, steps[i][0], x + 0.2, 1.95);
    txt(s, `${i + 1}  ${steps[i][1]}`, { x: x + 0.2, y: 2.8, w: 1.95, h: 0.5, fontSize: 17, bold: true });
    txt(s, steps[i][2], { x: x + 0.2, y: 3.35, w: 1.95, h: 2.1, fontSize: 14, color: C.text2 });
  }
  txt(s, "Sense wires carry no current, so lead and trace resistance drop out of the reading.", { x: 0.6, y: 5.95, w: 12, h: 0.5, fontSize: 16, italic: true, color: C.accent1 });
  s.addNotes("ACS712 alone cannot resolve milliohms, which is why the INA333 voltage path was added. Both ADC channels are read so R is ratiometric to the measured current.");

  // 5 ── Hardware
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Design" });
  s.addText("Three boards and a slide fixture", { placeholder: "title" });
  const boards = [
    [fa.FaServer, "Main board 100 × 80 mm", "Current source, pin switches, muxes, INA333, ADS1115, ESP32-DevKitC socket"],
    [fa.FaPlug, "Jack boards 80 × 40 mm", "Plug and socket on PC-tail footprints, 34-way IDC: odd = force, even = sense"],
    [fa.FaArrowsAltH, "Slide fixture", "Rail pushes the plug into the socket, mate switch on GPIO33 detects full insertion"],
  ];
  for (let i = 0; i < boards.length; i++) {
    const y = 1.55 + i * 1.3;
    await badge(s, boards[i][0], 0.6, y + 0.1);
    txt(s, boards[i][1], { x: 1.45, y, w: 4.9, h: 0.4, fontSize: 18, bold: true });
    txt(s, boards[i][2], { x: 1.45, y: y + 0.42, w: 4.9, h: 0.75, fontSize: 14, color: C.text2 });
  }
  card(s, 6.8, 1.55, 5.9, 3.6, "Footprint frame");
  s.addImage({ path: "fp.png", x: 7.0, y: 2.55, w: 5.5, h: 5.5 * 440 / 1540, altText: "RP16 footprints preview" });
  txt(s, "KiCad footprints from the datasheet: Ø1.57 holes, fixing holes 53.97 mm apart", { x: 7.0, y: 4.35, w: 5.5, h: 0.6, fontSize: 12, color: C.accent5 });
  card(s, 0.6, 5.5, 12.1, 1.15, "Power note", "FBE7EA");
  txt(s, [
    { text: "Power rule: ", options: { bold: true, color: C.accent1 } },
    { text: "the ESP32 is powered from the laptop USB only. Main-board +5 V never reaches the DevKitC 5 V pin; GND is shared." },
  ], { x: 0.85, y: 5.72, w: 11.6, h: 0.75, fontSize: 15, valign: "middle" });
  s.addNotes("Powering the DevKitC from two sources at once is unsafe, so the design keeps USB as its only supply.");

  // 6 ── Firmware & protocol
  pres.addSection({ title: "Software" });
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Software" });
  s.addText("Firmware scans, checks and reports every cycle", { placeholder: "title" });
  card(s, 0.6, 1.55, 5.9, 4.3, "Firmware card");
  await badge(s, fa.FaMicrochip, 0.85, 1.8);
  txt(s, "ESP32 firmware 0.3.0", { x: 1.65, y: 1.9, w: 4.6, h: 0.45, fontSize: 18, bold: true });
  txt(s, [
    { text: "Scans 16 pins, 8 samples each, keeps the minimum R", options: { bullet: true, breakLine: true, paraSpaceAfter: 8 } },
    { text: "Isolation test finds shorts: drive pin a, read others (150 µV limit)", options: { bullet: true, breakLine: true, paraSpaceAfter: 8 } },
    { text: "Cuts current above 0.75 A, alarms if 5 V leaves 4.6–5.4 V", options: { bullet: true, breakLine: true, paraSpaceAfter: 8 } },
    { text: "Calibration and settings kept in NVS", options: { bullet: true } },
  ], { x: 0.85, y: 2.65, w: 5.4, h: 3.7, fontSize: 15 });
  card(s, 6.8, 1.55, 5.9, 4.3, "Protocol card");
  await badge(s, fa.FaExchangeAlt, 7.05, 1.8);
  txt(s, "Serial protocol, 115200 baud", { x: 7.85, y: 1.9, w: 4.6, h: 0.45, fontSize: 18, bold: true });
  txt(s, [
    { text: "Kit → app", options: { bold: true, breakLine: true } },
    { text: "HELLO · CYCLE · DATA · SHORT · ISO · ALARM · END", options: { fontFace: "Courier New", fontSize: 13, breakLine: true, paraSpaceAfter: 12 } },
    { text: "App → kit", options: { bold: true, breakLine: true } },
    { text: "SCAN · MEASURE · SETCYCLE · GAIN · AUTO · ISO · CALZERO · CALREF", options: { fontFace: "Courier New", fontSize: 13, breakLine: true, paraSpaceAfter: 12 } },
    { text: "Plain-text lines, so any terminal can drive the kit too.", options: { color: C.text2 } },
  ], { x: 7.05, y: 2.65, w: 5.4, h: 3.7, fontSize: 15 });
  s.addNotes("Full protocol is in docs/serial-protocol.md.");

  // 7 ── Desktop app
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Software" });
  s.addText("The desktop app records, charts and logs issues", { placeholder: "title" });
  const aw = 8.2, ah = aw * 819 / 1456;
  s.addImage({ path: "app.jpg", x: 0.6, y: 1.55, w: aw, h: ah, altText: "CR-TEST desktop app screenshot", shadow: shadow() });
  const feats = [
    ["Live R vs cycle", "per pin, with the 10 mΩ limit line"],
    ["Average minimum R", "pin-to-pin comparison chart"],
    ["Issues log", "OPEN, SHORT, FAIL and ALARM events, saved as CSV"],
    ["Simulation mode", "full runs and fault scenarios with no hardware"],
  ];
  feats.forEach(([h, d], i) => {
    const y = 1.55 + i * 1.18;
    txt(s, h, { x: 9.15, y, w: 3.6, h: 0.4, fontSize: 17, bold: true, color: C.accent1 });
    txt(s, d, { x: 9.15, y: y + 0.4, w: 3.6, h: 0.65, fontSize: 14, color: C.text2 });
  });
  txt(s, "Python + PySide6 · one-click install.bat · 23 unit tests", { x: 0.6, y: 1.65 + ah, w: aw, h: 0.4, fontSize: 13, color: C.accent5 });
  s.addNotes("Screenshot is the app on the bench PC after the fault-scenario run.");

  // 8 ── Test sequence
  pres.addSection({ title: "Results" });
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Results" });
  s.addText("One test run in six steps", { placeholder: "title" });
  const seq = [
    [fa.FaPlug, "Install jacks", "Plug and socket on the jack boards"],
    [fa.FaPowerOff, "Power on", "5 V DC to the main board, USB to laptop"],
    [fa.FaDesktop, "Open app", "Connect, set cycle counter, calibrate zero"],
    [fa.FaPlay, "Start logging", "New session CSV per sample ID"],
    [fa.FaSyncAlt, "Cycle × N", "Push to mate, scan, slide back, repeat"],
    [fa.FaStop, "Stop & export", "Summary with average minimum R"],
  ];
  for (let i = 0; i < seq.length; i++) {
    const x = 0.6 + i * 2.07;
    await badge(s, seq[i][0], x + 0.55, 2.0, 0.85);
    if (i < seq.length - 1) s.addShape(pres.shapes.LINE, { x: x + 1.5, y: 2.425, w: 1.0, h: 0, line: { color: C.accent6, width: 2, endArrowType: "triangle" }, objectName: "Flow arrow" });
    txt(s, `${i + 1}. ${seq[i][1]}`, { x, y: 3.15, w: 1.95, h: 0.45, fontSize: 16, bold: true, align: "center" });
    txt(s, seq[i][2], { x: x + 0.05, y: 3.65, w: 1.85, h: 1.2, fontSize: 14, color: C.text2, align: "center" });
  }
  card(s, 0.6, 4.75, 12.1, 1.25, "Run note");
  txt(s, "A full 100-cycle run has been rehearsed end to end in simulation mode on the bench PC, with the app installed by install.bat.", { x: 0.85, y: 4.9, w: 11.6, h: 0.95, fontSize: 15, valign: "middle" });

  // 9 ── Simulation results chart
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Results" });
  s.addText("100 simulated cycles: every pin far below the limit", { placeholder: "title" });
  s.addChart(pres.charts.BAR, [{ name: "Average minimum R (mΩ)", labels: Array.from({ length: 16 }, (_, i) => String(i + 1)), values: data.avg }], {
    x: 0.6, y: 1.5, w: 8.6, h: 5.2, barDir: "col",
    chartColors: [HEX.red], showLegend: false, showTitle: true, title: "Average minimum R per pin (mΩ)", titleFontSize: 14, titleColor: HEX.ink, titleFontFace: "+mn-lt",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00", dataLabelFontSize: 10, dataLabelColor: HEX.slate, dataLabelFontFace: "+mn-lt",
    catAxisLabelColor: HEX.muted, valAxisLabelColor: HEX.muted, catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", catAxisLabelFontSize: 11, valAxisLabelFontSize: 11,
    showCatAxisTitle: true, catAxisTitle: "Pin", catAxisTitleColor: HEX.muted, catAxisTitleFontSize: 11,
    valAxisMinVal: 0, valAxisMaxVal: 4, valAxisLabelFormatCode: "0", valGridLine: { color: HEX.grid, size: 0.75 }, catGridLine: { style: "none" }, barGapWidthPct: 60,
  });
  const hi = Math.max(...data.avg), lo = Math.min(...data.avg);
  const hiPin = data.avg.indexOf(hi) + 1, loPin = data.avg.indexOf(lo) + 1;
  [[hi.toFixed(2) + " mΩ", `highest: pin ${hiPin}`], [lo.toFixed(2) + " mΩ", `lowest: pin ${loPin}`], ["0 / 16", "pins failed (limit 10 mΩ)"]].forEach(([v, l], i) => {
    const y = 1.6 + i * 1.65;
    card(s, 9.55, y, 3.15, 1.45, "Result card " + (i + 1));
    txt(s, v, { x: 9.8, y: y + 0.2, w: 2.7, h: 0.65, fontSize: 30, bold: true, color: C.accent1, fontFace: "Cambria" });
    txt(s, l, { x: 9.8, y: y + 0.88, w: 2.7, h: 0.4, fontSize: 14, color: C.text2 });
  });
  txt(s, "Simulated data from the app's simulator, not hardware measurements.", { x: 9.55, y: 6.55, w: 3.15, h: 0.4, fontSize: 10, color: C.accent5 });
  s.addNotes("Simulator model: each pin has its own base resistance plus slow wear and noise. Real results will replace this chart once the hardware run is done.");

  // 10 ── Fault scenarios
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Results" });
  s.addText("All four fault scenarios were detected and logged", { placeholder: "title" });
  const hdr = (t) => ({ text: t, options: { bold: true, color: HEX.paper, fill: { color: HEX.slate }, fontSize: 14 } });
  const ok = { text: "Detected", options: { bold: true, color: "2E8B57" } };
  s.addTable([
    [hdr("Scenario"), hdr("Example in run"), hdr("How it shows"), hdr("Result")],
    ["1 pin open", "Pin 5 from cycle 9", "OPEN event, FAIL after 3 scans (cycle 11)", ok],
    ["2+ pins open", "Pins 2 and 9", "OPEN on each pin, both FAIL at cycle 19", ok],
    ["2 pins shorted", "Pins 4–5", "Isolation test: SHORT 4–5, FAIL at cycle 27", ok],
    ["3+ pins shorted", "Pins 10–11–12", "SHORT group, FAIL at cycle 35, cleared when removed", ok],
  ], { x: 0.6, y: 1.6, w: 12.1, colW: [2.4, 2.6, 5.3, 1.8], fontSize: 14, color: HEX.ink, fontFace: "Calibri", border: { type: "solid", color: HEX.grid, pt: 1 }, rowH: 0.62, valign: "middle", margin: [0, 0.12, 0, 0.12] });
  await badge(s, fa.FaClipboardList, 0.6, 5.2);
  txt(s, "Every event goes to the Issues tab and to <session>_issues.csv, with time, cycle, severity and pins.", { x: 1.45, y: 5.25, w: 11.2, h: 0.6, fontSize: 15, valign: "middle" });
  txt(s, "Shorts make R read low, so they are caught by the isolation test, not the R limit.", { x: 1.45, y: 5.9, w: 11.2, h: 0.5, fontSize: 15, italic: true, color: C.accent1 });

  // 11 ── Protection review
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Results" });
  s.addText("Pin shorts are safe today; rev B closes the remaining gaps", { placeholder: "title" });
  card(s, 0.6, 1.55, 5.9, 4.3, "Gaps card");
  await badge(s, fa.FaExclamationTriangle, 0.85, 1.8, 0.62, C.accent3);
  txt(s, "Rev A findings", { x: 1.65, y: 1.9, w: 4.6, h: 0.45, fontSize: 18, bold: true });
  txt(s, [
    { text: "Pin-to-pin shorts limited to ≤ 0.63 A by design", options: { bullet: true, breakLine: true, paraSpaceAfter: 8 } },
    { text: "Force-to-GND short: 0.89 A, 4.46 W in R_HI (fw cuts off > 0.75 A)", options: { bullet: true, breakLine: true, paraSpaceAfter: 8 } },
    { text: "Open pin back-feeds 22 mA into +3V3A", options: { bullet: true, breakLine: true, paraSpaceAfter: 8 } },
    { text: "No reverse-polarity protection, no ACS712 clamp", options: { bullet: true, breakLine: true, paraSpaceAfter: 8 } },
    { text: "Shorts of 3+ pins hard to see with REF = 0 V", options: { bullet: true } },
  ], { x: 0.85, y: 2.65, w: 5.4, h: 3.7, fontSize: 15 });
  card(s, 6.8, 1.55, 5.9, 4.3, "Fixes card");
  await badge(s, fa.FaShieldAlt, 7.05, 1.8, 0.62, C.accent4);
  txt(s, "Rev B changes", { x: 7.85, y: 1.9, w: 4.6, h: 0.45, fontSize: 18, bold: true });
  txt(s, [
    { text: "INA333 REF ≈ 0.25 V, read on AIN3: sees shorts of 3–8+ pins", options: { bullet: true, breakLine: true, paraSpaceAfter: 8 } },
    { text: "10 kΩ sense resistors + bleeder: back-feed 22 → 2.2 mA", options: { bullet: true, breakLine: true, paraSpaceAfter: 8 } },
    { text: "Reverse-polarity P-MOSFET at the 5 V input", options: { bullet: true, breakLine: true, paraSpaceAfter: 8 } },
    { text: "R_HI 5 W → 10 W, BAT54S clamp on ACS712 output", options: { bullet: true, breakLine: true, paraSpaceAfter: 8 } },
    { text: "Leave IDC pins 33/34 unconnected", options: { bullet: true } },
  ], { x: 7.05, y: 2.65, w: 5.4, h: 3.7, fontSize: 15 });
  s.addNotes("Details and worst-case numbers are in docs/fault-protection.md.");

  // 12 ── BOM
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Results" });
  s.addText("About $150 per kit, with two supply risks", { placeholder: "title" });
  const g = Object.entries(data.groups).sort((a, b) => b[1] - a[1]);
  s.addChart(pres.charts.BAR, [{ name: "Cost (USD)", labels: g.map((x) => x[0]), values: g.map((x) => x[1]) }], {
    x: 0.6, y: 1.5, w: 7.6, h: 5.2, barDir: "bar",
    chartColors: [HEX.red], showLegend: false, showTitle: true, title: "Cost by group (USD)", titleFontSize: 14, titleColor: HEX.ink, titleFontFace: "+mn-lt",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "$0", dataLabelFontSize: 11, dataLabelColor: HEX.slate, dataLabelFontFace: "+mn-lt",
    catAxisLabelColor: HEX.muted, valAxisLabelColor: HEX.muted, catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", catAxisLabelFontSize: 12, valAxisLabelFontSize: 11,
    catAxisOrientation: "maxMin", valAxisMaxVal: 60, valAxisLabelFormatCode: "$0", valGridLine: { color: HEX.grid, size: 0.75 }, catGridLine: { style: "none" }, barGapWidthPct: 50,
  });
  card(s, 8.6, 1.55, 4.1, 1.9, "Total card");
  txt(s, "$" + 148.39, { x: 8.85, y: 1.75, w: 3.6, h: 0.9, fontSize: 44, bold: true, color: C.accent1, fontFace: "Cambria" });
  txt(s, "per kit, 40 BOM lines", { x: 8.85, y: 2.75, w: 3.6, h: 0.4, fontSize: 14, color: C.text2 });
  await badge(s, fa.FaExclamationTriangle, 8.6, 3.85, 0.55, C.accent3);
  txt(s, [{ text: "RP16 / RS16 stock", options: { bold: true, breakLine: true } }, { text: "Listed as no longer stocked at element14: buy test samples early", options: { color: C.text2 } }], { x: 9.35, y: 3.82, w: 3.35, h: 1.2, fontSize: 14 });
  await badge(s, fa.FaExclamationTriangle, 8.6, 5.25, 0.55, C.accent3);
  txt(s, [{ text: "ACS712 is NRND", options: { bold: true, breakLine: true } }, { text: "ACS723 is the drop-in alternative in the BOM", options: { color: C.text2 } }], { x: 9.35, y: 5.22, w: 3.35, h: 1.2, fontSize: 14 });
  s.addNotes("Full BOM with suppliers and alternatives: hardware/BOM.xlsx.");

  // 13 ── Next steps
  pres.addSection({ title: "Next steps" });
  s = pres.addSlide({ masterName: "Title dark", sectionTitle: "Next steps" });
  s.addText("Next steps", { placeholder: "title" });
  s.addText("From simulation to the first real 500-cycle life test", { placeholder: "body" });
  const nx = [
    [fa.FaDraftingCompass, "Finish rev B schematic and layout in KiCad"],
    [fa.FaIndustry, "Order PCBs, connector samples and parts from the BOM"],
    [fa.FaTools, "Assemble, calibrate with a reference shunt"],
    [fa.FaChartLine, "Run 500 cycles on real RP16 pairs and compare to the datasheet"],
  ];
  for (let i = 0; i < nx.length; i++) {
    const y = 1.2 + i * 1.3;
    await badge(s, nx[i][0], 9.3, y, 0.7);
    txt(s, nx[i][1], { x: 10.2, y: y - 0.05, w: 2.9, h: 0.85, fontSize: 16, color: C.background1, valign: "middle" });
  }
  txt(s, "github.com/dophuthinh2010-crypto/kit-contact-resistance-16pin", { x: 0.7, y: 6.3, w: 8, h: 0.4, fontSize: 14, color: "9AA5B1" });

  await pres.writeFile({ fileName: "CR-TEST_presentation.pptx" });
  await applyTheme("CR-TEST_presentation.pptx", THEME);
  console.log("written");
})();
