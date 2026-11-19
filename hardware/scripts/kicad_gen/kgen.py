"""Small writer for KiCad 8 schematic (.kicad_sch) and board (.kicad_pcb) files.

The design scripts (main_board.py, jack_board.py) describe parts as:
    Part(ref, value, symbol, footprint, {pin_number: net or None}, mpn=..., note=...)
and this module turns them into:
  * a one-sheet schematic: every part is a box symbol; every pin ends in a short wire with a
    net label (or a no-connect flag), so the netlist is exact and easy to review;
  * a board file: footprints with pads on their nets, the outline, mounting holes, zones,
    linked to the schematic symbols (so "Update PCB from Schematic" keeps the placement).
Routing is not done here (see hardware/kicad/README.md).
"""
from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

NS = uuid.UUID("7f1c0a52-3e2b-4d8a-9a51-6c2f0e9b1a00")
G = 1.27  # schematic grid, mm


def uid(*parts) -> str:
    return str(uuid.uuid5(NS, "/".join(str(p) for p in parts)))


def q(s: str) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def snap(v: float) -> float:
    return round(round(v / G) * G, 4)


def f(v: float) -> str:
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# --------------------------------------------------------------------------- symbols
@dataclass
class Sym:
    """Box symbol. left/right: lists of (pin_number, pin_name) top to bottom; None = gap."""
    name: str
    left: List[Optional[Tuple[str, str]]]
    right: List[Optional[Tuple[str, str]]]
    ref: str = "U"
    width: float = 10.16
    show_names: bool = True
    descr: str = ""

    @property
    def rows(self) -> int:
        return max(len(self.left), len(self.right), 1)

    @property
    def height(self) -> float:
        return (self.rows + 1) * 2.54

    def pin_xy(self, side: str, i: int) -> Tuple[float, float]:
        """Connection point of pin i on a side, in symbol coordinates (y up)."""
        top = (self.rows - 1) * 2.54 / 2
        y = top - i * 2.54
        x = -self.width / 2 - 2.54 if side == "L" else self.width / 2 + 2.54
        return snap(x), snap(y)

    def pins(self):
        for side, lst in (("L", self.left), ("R", self.right)):
            for i, p in enumerate(lst):
                if p:
                    yield side, i, p[0], p[1]

    def lib(self, libname: str) -> str:
        w2, h2 = self.width / 2, self.height / 2
        hide = "" if self.show_names else " hide"
        out = [f'    (symbol {q(libname + ":" + self.name)} (pin_names (offset 0.508){hide}) (exclude_from_sim no) (in_bom yes) (on_board yes)',
               f'      (property "Reference" {q(self.ref)} (at 0 {f(h2 + 1.27)} 0) (effects (font (size 1.27 1.27))))',
               f'      (property "Value" {q(self.name)} (at 0 {f(-h2 - 1.27)} 0) (effects (font (size 1.27 1.27))))',
               '      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
               '      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
               f'      (property "Description" {q(self.descr)} (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
               f'      (symbol {q(self.name + "_0_1")}',
               f'        (rectangle (start {f(-w2)} {f(h2)}) (end {f(w2)} {f(-h2)}) (stroke (width 0.254) (type default)) (fill (type background))))',
               f'      (symbol {q(self.name + "_1_1")}']
        for side, i, num, name in self.pins():
            x, y = self.pin_xy(side, i)
            ang = 0 if side == "L" else 180
            out.append(f'        (pin passive line (at {f(x)} {f(y)} {ang}) (length 2.54) '
                       f'(name {q(name)} (effects (font (size 1.016 1.016)))) (number {q(num)} (effects (font (size 1.016 1.016)))))')
        out.append("      )\n    )")
        return "\n".join(out)


# --------------------------------------------------------------------------- footprints
@dataclass
class Pad:
    num: str
    kind: str          # smd | thru_hole | np_thru_hole
    shape: str         # rect | roundrect | circle | oval
    x: float
    y: float
    sx: float
    sy: float
    drill: float = 0.0


@dataclass
class Fp:
    name: str
    pads: List[Pad]
    body: Tuple[float, float, float, float]          # x1 y1 x2 y2 (fab outline)
    descr: str = ""
    through_hole: bool = False
    pin1_mark: bool = True

    def courtyard(self) -> Tuple[float, float, float, float]:
        xs = [self.body[0], self.body[2]] + [p.x - p.sx / 2 for p in self.pads] + [p.x + p.sx / 2 for p in self.pads]
        ys = [self.body[1], self.body[3]] + [p.y - p.sy / 2 for p in self.pads] + [p.y + p.sy / 2 for p in self.pads]
        m = 0.25
        return min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m


# --------------------------------------------------------------------------- parts
@dataclass
class Part:
    ref: str
    value: str
    sym: Sym
    fp: Fp
    nets: Dict[str, Optional[str]]
    mpn: str = ""
    note: str = ""
    block: str = ""
    pcb: Optional[Tuple[float, float, float]] = None   # x, y, rotation (board coordinates)
    sch: Optional[Tuple[float, float]] = None

    def __post_init__(self):
        sym_pins = {p[2] for p in self.sym.pins()}
        fp_pins = {p.num for p in self.fp.pads if p.num}
        missing = sym_pins ^ fp_pins
        if missing:
            raise ValueError(f"{self.ref}: symbol/footprint pins differ: {sorted(missing)}")
        unknown = set(self.nets) - sym_pins
        if unknown:
            raise ValueError(f"{self.ref}: nets given for unknown pins {sorted(unknown)}")
        for p in sym_pins:
            self.nets.setdefault(p, None)


# --------------------------------------------------------------------------- schematic
def write_schematic(path: str, project: str, parts: List[Part], blocks: List[dict], title: str,
                    rev: str, date: str, comments: List[str], paper: str = "A1", libname: str = "crkit",
                    notes: List[Tuple[float, float, str, float]] = ()) -> None:
    root = uid(project, "root")
    syms = {}
    for p in parts:
        syms[p.sym.name] = p.sym
    o = [f'(kicad_sch (version 20231120) (generator "eeschema") (generator_version "8.0")',
         f'  (uuid {q(root)})', f'  (paper {q(paper)})',
         f'  (title_block (title {q(title)}) (date {q(date)}) (rev {q(rev)}) (company "CR-TEST")']
    for i, c in enumerate(comments[:9], 1):
        o.append(f'    (comment {i} {q(c)})')
    o.append("  )")
    o.append("  (lib_symbols")
    for s in syms.values():
        o.append(s.lib(libname))
    o.append("  )")

    for b in blocks:
        x1, y1, x2, y2 = (snap(v) for v in b["rect"])
        o.append(f'  (rectangle (start {f(x1)} {f(y1)}) (end {f(x2)} {f(y2)}) (stroke (width 0.3) (type dash) (color 120 120 120 1)) (fill (type none)) (uuid {q(uid(project, "blk", b["name"]))}))')
        o.append(f'  (text {q(b["name"])} (exclude_from_sim no) (at {f(x1 + 2.54)} {f(y1 + 5.08)} 0) (effects (font (size 3 3) (thickness 0.6) bold) (justify left bottom)) (uuid {q(uid(project, "blkt", b["name"]))}))')
        if b.get("text"):
            o.append(f'  (text {q(b["text"])} (exclude_from_sim no) (at {f(x1 + 2.54)} {f(y1 + 9.4)} 0) (effects (font (size 1.6 1.6)) (justify left bottom)) (uuid {q(uid(project, "blkn", b["name"]))}))')
    for i, (x, y, t, size) in enumerate(notes):
        o.append(f'  (text {q(t)} (exclude_from_sim no) (at {f(snap(x))} {f(snap(y))} 0) (effects (font (size {size} {size})) (justify left top)) (uuid {q(uid(project, "note", i))}))')

    for p in parts:
        X, Y = (snap(v) for v in p.sch)
        su = uid(project, "sym", p.ref)
        h2 = p.sym.height / 2
        props = [("Reference", p.ref, (X, snap(Y - h2 - 1.27)), False),
                 ("Value", p.value, (X, snap(Y + h2 + 1.27)), False),
                 ("Footprint", f"{libname}:{p.fp.name}", (X, Y), True),
                 ("Datasheet", "", (X, Y), True),
                 ("Description", p.note, (X, Y), True),
                 ("MPN", p.mpn, (X, Y), True)]
        o.append(f'  (symbol (lib_id {q(libname + ":" + p.sym.name)}) (at {f(X)} {f(Y)} 0) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)')
        o.append(f'    (uuid {q(su)})')
        for k, v, (px, py), hid in props:
            h = " hide" if hid else ""
            o.append(f'    (property {q(k)} {q(v)} (at {f(px)} {f(py)} 0) (effects (font (size 1.27 1.27)){h}))')
        for side, i, num, name in p.sym.pins():
            o.append(f'    (pin {q(num)} (uuid {q(uid(project, "pin", p.ref, num))}))')
        o.append(f'    (instances (project {q(project)} (path {q("/" + root)} (reference {q(p.ref)}) (unit 1))))')
        o.append("  )")
        # stubs + labels
        for side, i, num, name in p.sym.pins():
            sx, sy = p.sym.pin_xy(side, i)
            px, py = snap(X + sx), snap(Y - sy)
            net = p.nets.get(num)
            if net is None:
                o.append(f'  (no_connect (at {f(px)} {f(py)}) (uuid {q(uid(project, "nc", p.ref, num))}))')
                continue
            ex = snap(px - 2.54) if side == "L" else snap(px + 2.54)
            o.append(f'  (wire (pts (xy {f(px)} {f(py)}) (xy {f(ex)} {f(py)})) (stroke (width 0) (type default)) (uuid {q(uid(project, "w", p.ref, num))}))')
            ang, just = (180, "right bottom") if side == "L" else (0, "left bottom")
            o.append(f'  (label {q(net)} (at {f(ex)} {f(py)} {ang}) (fields_autoplaced yes) (effects (font (size 1.27 1.27)) (justify {just})) (uuid {q(uid(project, "lbl", p.ref, num))}))')
    o.append('  (sheet_instances (path "/" (page "1")))')
    o.append(")")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(o) + "\n")


# --------------------------------------------------------------------------- board
LAYERS = '''  (layers
    (0 "F.Cu" signal) (31 "B.Cu" signal)
    (32 "B.Adhes" user "B.Adhesive") (33 "F.Adhes" user "F.Adhesive")
    (34 "B.Paste" user) (35 "F.Paste" user)
    (36 "B.SilkS" user "B.Silkscreen") (37 "F.SilkS" user "F.Silkscreen")
    (38 "B.Mask" user) (39 "F.Mask" user)
    (40 "Dwgs.User" user "User.Drawings") (41 "Cmts.User" user "User.Comments")
    (42 "Eco1.User" user "User.Eco1") (43 "Eco2.User" user "User.Eco2")
    (44 "Edge.Cuts" user) (45 "Margin" user)
    (46 "B.CrtYd" user "B.Courtyard") (47 "F.CrtYd" user "F.Courtyard")
    (48 "B.Fab" user) (49 "F.Fab" user)
  )'''


def rot(x: float, y: float, a: float) -> Tuple[float, float]:
    """KiCad board rotation: positive angle is counter-clockwise on screen (y down)."""
    r = math.radians(a)
    return x * math.cos(r) + y * math.sin(r), -x * math.sin(r) + y * math.cos(r)


def placed_courtyard(p: Part, ox: float, oy: float) -> Tuple[float, float, float, float]:
    x1, y1, x2, y2 = p.fp.courtyard()
    pts = [rot(x, y, p.pcb[2]) for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2))]
    xs = [ox + p.pcb[0] + x for x, _ in pts]
    ys = [oy + p.pcb[1] + y for _, y in pts]
    return min(xs), min(ys), max(xs), max(ys)


def write_board(path: str, project: str, parts: List[Part], size: Tuple[float, float], origin=(50.0, 50.0),
                holes: List[Tuple[float, float]] = (), zones: List[dict] = (), texts: List[Tuple[float, float, str, float]] = (),
                libname: str = "crkit", title: str = "", rev: str = "", date: str = "") -> Dict[str, int]:
    ox, oy = origin
    nets = sorted({n for p in parts for n in p.nets.values() if n})
    netno = {n: i + 1 for i, n in enumerate(nets)}
    o = ['(kicad_pcb (version 20240108) (generator "pcbnew") (generator_version "8.0")',
         '  (general (thickness 1.6) (legacy_teardrops no))', '  (paper "A3")',
         f'  (title_block (title {q(title)}) (date {q(date)}) (rev {q(rev)}) (company "CR-TEST"))',
         LAYERS,
         '  (setup (pad_to_mask_clearance 0) (allow_soldermask_bridges_in_footprints no))',
         '  (net 0 "")']
    for n in nets:
        o.append(f'  (net {netno[n]} {q(n)})')
    for p in parts:
        x, y, a = p.pcb
        fu = uid(project, "fp", p.ref)
        o.append(f'  (footprint {q(libname + ":" + p.fp.name)} (layer "F.Cu") (uuid {q(fu)}) (at {f(ox + x)} {f(oy + y)}{" " + f(a) if a else ""})')
        if p.fp.descr:
            o.append(f'    (descr {q(p.fp.descr)})')
        x1, y1, x2, y2 = p.fp.body
        cy = p.fp.courtyard()
        o.append(f'    (property "Reference" {q(p.ref)} (at 0 {f(cy[1] - 0.8)} {f(a)}) (layer "F.SilkS") (uuid {q(uid(fu, "r"))}) (effects (font (size 0.8 0.8) (thickness 0.12))))')
        o.append(f'    (property "Value" {q(p.value)} (at 0 {f(cy[3] + 0.8)} {f(a)}) (layer "F.Fab") (uuid {q(uid(fu, "v"))}) (effects (font (size 0.8 0.8) (thickness 0.12))))')
        o.append(f'    (property "Footprint" {q(libname + ":" + p.fp.name)} (at 0 0 {f(a)}) (layer "F.Fab") (hide yes) (uuid {q(uid(fu, "f"))}) (effects (font (size 1 1) (thickness 0.15))))')
        o.append(f'    (property "Datasheet" "" (at 0 0 {f(a)}) (layer "F.Fab") (hide yes) (uuid {q(uid(fu, "d"))}) (effects (font (size 1 1) (thickness 0.15))))')
        o.append(f'    (property "Description" {q(p.note)} (at 0 0 {f(a)}) (layer "F.Fab") (hide yes) (uuid {q(uid(fu, "s"))}) (effects (font (size 1 1) (thickness 0.15))))')
        o.append(f'    (path {q("/" + uid(project, "sym", p.ref))})')
        o.append("    (attr through_hole)" if p.fp.through_hole else "    (attr smd)")
        o.append(f'    (fp_rect (start {f(x1)} {f(y1)}) (end {f(x2)} {f(y2)}) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab") (uuid {q(uid(fu, "fab"))}))')
        o.append(f'    (fp_rect (start {f(x1 - 0.1)} {f(y1 - 0.1)}) (end {f(x2 + 0.1)} {f(y2 + 0.1)}) (stroke (width 0.12) (type default)) (fill none) (layer "F.SilkS") (uuid {q(uid(fu, "silk"))}))'
                 if p.fp.through_hole or (x2 - x1) > 2.5 else "")
        o.append(f'    (fp_rect (start {f(cy[0])} {f(cy[1])}) (end {f(cy[2])} {f(cy[3])}) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd") (uuid {q(uid(fu, "crt"))}))')
        if p.fp.pin1_mark:
            p1 = next((pd for pd in p.fp.pads if pd.num == "1"), None)
            if p1:
                mx = p1.x - p1.sx / 2 - 0.5
                o.append(f'    (fp_circle (center {f(mx)} {f(p1.y)}) (end {f(mx + 0.15)} {f(p1.y)}) (stroke (width 0.3) (type default)) (fill solid) (layer "F.SilkS") (uuid {q(uid(fu, "p1"))}))')
        for i, pd in enumerate(p.fp.pads):
            net = p.nets.get(pd.num) if pd.num else None
            layers = '"F.Cu" "F.Paste" "F.Mask"' if pd.kind == "smd" else '"*.Cu" "*.Mask"'
            extra = f" (drill {f(pd.drill)})" if pd.kind != "smd" else ""
            rr = " (roundrect_rratio 0.25)" if pd.shape == "roundrect" else ""
            nets_s = f" (net {netno[net]} {q(net)})" if net else ""
            o.append(f'    (pad {q(pd.num)} {pd.kind} {pd.shape} (at {f(pd.x)} {f(pd.y)}{" " + f(a) if a else ""}) (size {f(pd.sx)} {f(pd.sy)}){extra} (layers {layers}){rr}{nets_s} (uuid {q(uid(fu, "pad", i))}))')
        o.append("  )")
    W, H = size
    o.append(f'  (gr_rect (start {f(ox)} {f(oy)}) (end {f(ox + W)} {f(oy + H)}) (stroke (width 0.1) (type default)) (fill none) (layer "Edge.Cuts") (uuid {q(uid(project, "edge"))}))')
    for i, (hx, hy) in enumerate(holes):
        hu = uid(project, "mh", i)
        o.append(f'  (footprint "{libname}:MountingHole_3.2mm_M3" (layer "F.Cu") (uuid {q(hu)}) (at {f(ox + hx)} {f(oy + hy)})')
        o.append(f'    (property "Reference" "H{i + 1}" (at 0 -3.2 0) (layer "F.SilkS") (hide yes) (uuid {q(uid(hu, "r"))}) (effects (font (size 1 1) (thickness 0.15))))')
        o.append(f'    (property "Value" "M3" (at 0 3.2 0) (layer "F.Fab") (hide yes) (uuid {q(uid(hu, "v"))}) (effects (font (size 1 1) (thickness 0.15))))')
        o.append('    (attr exclude_from_pos_files exclude_from_bom)')
        o.append(f'    (fp_circle (center 0 0) (end 3.2 0) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd") (uuid {q(uid(hu, "c"))}))')
        o.append(f'    (pad "" np_thru_hole circle (at 0 0) (size 3.2 3.2) (drill 3.2) (layers "*.Cu" "*.Mask") (uuid {q(uid(hu, "p"))}))')
        o.append("  )")
    for i, z in enumerate(zones):
        n = z["net"]
        pts = " ".join(f"(xy {f(ox + x)} {f(oy + y)})" for x, y in z["pts"])
        o.append(f'  (zone (net {netno[n]}) (net_name {q(n)}) (layer {q(z["layer"])}) (uuid {q(uid(project, "zone", i))}) (hatch edge 0.5)'
                 f' (priority {z.get("priority", 0)}) (connect_pads (clearance {z.get("clearance", 0.3)})) (min_thickness 0.25) (filled_areas_thickness no)'
                 f' (fill (thermal_gap 0.5) (thermal_bridge_width {z.get("bridge", 0.5)})) (polygon (pts {pts})))')
    for i, (tx, ty, t, size_) in enumerate(texts):
        o.append(f'  (gr_text {q(t)} (at {f(ox + tx)} {f(oy + ty)}) (layer "F.SilkS") (uuid {q(uid(project, "txt", i))}) (effects (font (size {size_} {size_}) (thickness {f(size_ * 0.15)})) (justify left)))')
    o.append(")")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(line for line in o if line) + "\n")
    return netno


def write_project(path: str, name: str, classes: List[dict], patterns: List[Tuple[str, str]]) -> None:
    base = {"name": "Default", "clearance": 0.2, "track_width": 0.25, "via_diameter": 0.6, "via_drill": 0.3,
            "diff_pair_gap": 0.25, "diff_pair_width": 0.2, "diff_pair_via_gap": 0.25, "microvia_diameter": 0.3,
            "microvia_drill": 0.1, "wire_width": 6, "bus_width": 12, "line_style": 0, "pcb_color": "rgba(0, 0, 0, 0.000)",
            "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 2147483647}
    cls = [base] + [dict(base, priority=i, **c) for i, c in enumerate(classes)]
    proj = {
        "board": {"design_settings": {"rules": {"min_clearance": 0.2, "min_track_width": 0.2, "min_via_diameter": 0.5,
                                                "min_through_hole_diameter": 0.3, "min_copper_edge_clearance": 0.4,
                                                "min_hole_to_hole": 0.25}}},
        "meta": {"filename": name + ".kicad_pro", "version": 1},
        "net_settings": {"classes": cls, "meta": {"version": 3},
                         "netclass_patterns": [{"netclass": c, "pattern": p} for p, c in patterns]},
        "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
        "sheets": [[uid(name, "root"), "Root"]],
        "text_variables": {},
    }
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(proj, fh, indent=2)
        fh.write("\n")


def check_sexpr(path: str) -> None:
    """Balanced parentheses outside strings, and no stray characters: a basic parse check."""
    depth, ins, esc, line = 0, False, False, 1
    with open(path, encoding="utf-8") as fh:
        for ch in fh.read():
            if ch == "\n":
                line += 1
            if ins:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    ins = False
                continue
            if ch == '"':
                ins = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth < 0:
                    raise ValueError(f"{path}: extra ')' at line {line}")
    if depth or ins:
        raise ValueError(f"{path}: unbalanced (depth {depth}, open string {ins})")


def overlaps(parts: List[Part], allow=()) -> List[Tuple[str, str]]:
    boxes = [(p.ref, placed_courtyard(p, 0, 0)) for p in parts]
    bad = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, A = boxes[i]
            b, B = boxes[j]
            if (a, b) in allow or (b, a) in allow:
                continue
            if A[0] < B[2] and B[0] < A[2] and A[1] < B[3] and B[1] < A[3]:
                bad.append((a, b))
    return bad


# --------------------------------------------------------------------------- libraries
def write_libraries(libdir: str, syms, fps, libname: str = "crkit") -> None:
    """crkit.kicad_sym + crkit.pretty/, so 'Update PCB from Schematic' and edits work in KiCad."""
    import os
    os.makedirs(os.path.join(libdir, libname + ".pretty"), exist_ok=True)
    lines = ['(kicad_symbol_lib (version 20231120) (generator "kicad_symbol_editor") (generator_version "8.0")']
    for s in syms:
        lines.append(s.lib(libname).replace(q(libname + ":" + s.name), q(s.name), 1))
    lines.append(")")
    with open(os.path.join(libdir, libname + ".kicad_sym"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    for fp in fps:
        o = [f'(footprint {q(fp.name)} (version 20240108) (generator "pcbnew") (generator_version "8.0") (layer "F.Cu")',
             f'  (descr {q(fp.descr)})', '  (property "Reference" "REF**" (at 0 -1 0) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))',
             f'  (property "Value" {q(fp.name)} (at 0 1 0) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))',
             "  (attr through_hole)" if fp.through_hole else "  (attr smd)"]
        x1, y1, x2, y2 = fp.body
        c = fp.courtyard()
        o.append(f'  (fp_rect (start {f(x1)} {f(y1)}) (end {f(x2)} {f(y2)}) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))')
        o.append(f'  (fp_rect (start {f(c[0])} {f(c[1])}) (end {f(c[2])} {f(c[3])}) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))')
        for pd in fp.pads:
            layers = '"F.Cu" "F.Paste" "F.Mask"' if pd.kind == "smd" else '"*.Cu" "*.Mask"'
            extra = f" (drill {f(pd.drill)})" if pd.kind != "smd" else ""
            rr = " (roundrect_rratio 0.25)" if pd.shape == "roundrect" else ""
            o.append(f'  (pad {q(pd.num)} {pd.kind} {pd.shape} (at {f(pd.x)} {f(pd.y)}) (size {f(pd.sx)} {f(pd.sy)}){extra} (layers {layers}){rr})')
        o.append(")")
        p = os.path.join(libdir, libname + ".pretty", fp.name + ".kicad_mod")
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(o) + "\n")
        check_sexpr(p)


def write_lib_tables(projdir: str, libname: str = "crkit") -> None:
    import os
    with open(os.path.join(projdir, "sym-lib-table"), "w", newline="\n") as fh:
        fh.write(f'(sym_lib_table\n  (version 7)\n  (lib (name "{libname}")(type "KiCad")(uri "${{KIPRJMOD}}/../{libname}.kicad_sym")(options "")(descr "CR-TEST symbols"))\n)\n')
    with open(os.path.join(projdir, "fp-lib-table"), "w", newline="\n") as fh:
        fh.write(f'(fp_lib_table\n  (version 7)\n  (lib (name "{libname}")(type "KiCad")(uri "${{KIPRJMOD}}/../{libname}.pretty")(options "")(descr "CR-TEST footprints"))\n)\n')
