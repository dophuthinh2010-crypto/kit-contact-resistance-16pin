"""Generate KiCad footprints for ITW McMurdo Red Range 16-way PC-tail connectors.

Dimensions from the ITW McMurdo Red Range datasheet (P.C.B. layout, barrier polarised):
  2 rows x 8 contacts, 4.70 mm pitch, rows 9.14 mm apart, contact holes 1.57 mm,
  2 fixing holes 3.30 mm at B = 53.97 mm centres on the row centreline.
  Plate 62.99 x 22.35 mm max, body 45.47 x 19.05 mm max.
Pin numbering as seen from the mating face (PCB top side):
  plug  RP16-T  : top row 1..8 left->right, bottom row 9..16
  socket RS16P-T: top row 9..16 left->right, bottom row 1..8
"""
import os

PITCH = 4.70
ROW = 9.14
DRILL = 1.57
PAD = 2.60
MH_DRILL = 3.30
MH_X = 53.97 / 2
PLATE = (62.99, 22.35)
BODY = (45.47, 19.05)


def rect(layer, w, h, width):
    x, y = w / 2, h / 2
    return (f'  (fp_rect (start {-x:.3f} {-y:.3f}) (end {x:.3f} {y:.3f}) '
            f'(stroke (width {width}) (type solid)) (fill none) (layer "{layer}"))\n')


def footprint(name, descr, top_row, bottom_row, tag):
    s = [f'(footprint "{name}"\n  (version 20240108)\n  (generator "pcbnew")\n  (layer "F.Cu")\n',
         f'  (descr "{descr}")\n  (tags "{tag}")\n  (attr through_hole)\n',
         f'  (fp_text reference "J**" (at 0 {-PLATE[1]/2 - 1.5:.2f}) (layer "F.SilkS")\n'
         '    (effects (font (size 1 1) (thickness 0.15))))\n',
         f'  (fp_text value "{name}" (at 0 {PLATE[1]/2 + 1.5:.2f}) (layer "F.Fab")\n'
         '    (effects (font (size 1 1) (thickness 0.15))))\n',
         rect("F.Fab", *PLATE, 0.1), rect("F.Fab", *BODY, 0.1),
         rect("F.SilkS", PLATE[0] + 0.3, PLATE[1] + 0.3, 0.12),
         rect("F.CrtYd", PLATE[0] + 1.0, PLATE[1] + 1.0, 0.05)]
    x0 = -3.5 * PITCH
    for row_y, pins in ((-ROW / 2, top_row), (ROW / 2, bottom_row)):
        for i, n in enumerate(pins):
            x = x0 + i * PITCH
            shape = "rect" if n == 1 else "circle"
            s.append(f'  (pad "{n}" thru_hole {shape} (at {x:.3f} {row_y:.3f}) (size {PAD} {PAD}) '
                     f'(drill {DRILL}) (layers "*.Cu" "*.Mask"))\n')
    # pin-1 marker on silk next to pin 1
    p1 = [(x0 + i * PITCH, ry) for ry, pins in ((-ROW / 2, top_row), (ROW / 2, bottom_row))
          for i, n in enumerate(pins) if n == 1][0]
    s.append(f'  (fp_circle (center {p1[0] - 2.2:.3f} {p1[1]:.3f}) (end {p1[0] - 1.9:.3f} {p1[1]:.3f}) '
             '(stroke (width 0.3) (type solid)) (fill solid) (layer "F.SilkS"))\n')
    for x in (-MH_X, MH_X):
        s.append(f'  (pad "" np_thru_hole circle (at {x:.3f} 0) (size {MH_DRILL} {MH_DRILL}) '
                 f'(drill {MH_DRILL}) (layers "*.Cu" "*.Mask"))\n')
    s.append(f'  (fp_text user "Plate on {7.1 if "Plug" in name else 7.9} mm M3 standoffs" '
             f'(at 0 0) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))\n')
    s.append(')\n')
    return "".join(s)


os.makedirs("McMurdo_RedRange.pretty", exist_ok=True)
fps = {
    "McMurdo_RedRange_Plug_16way_RP16-T": (
        "ITW McMurdo Red Range plug RP16-T / DRP116-T, 16 way PC tail, 4.70 mm pitch, 2 rows 9.14 mm",
        list(range(1, 9)), list(range(9, 17)), "connector rack panel McMurdo RP16"),
    "McMurdo_RedRange_Socket_16way_RS16P-T": (
        "ITW McMurdo Red Range socket RS16P-T / DRS116P-T, 16 way PC tail, 4.70 mm pitch, 2 rows 9.14 mm",
        list(range(9, 17)), list(range(1, 9)), "connector rack panel McMurdo RS16"),
}
for name, (d, t, b, tag) in fps.items():
    with open(f"McMurdo_RedRange.pretty/{name}.kicad_mod", "w") as f:
        f.write(footprint(name, d, t, b, tag))
    print("wrote", name)
