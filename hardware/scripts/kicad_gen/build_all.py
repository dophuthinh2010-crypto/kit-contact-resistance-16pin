"""Regenerate every CR-TEST KiCad project, the shared libraries and the PNG previews."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import jack_board  # noqa: E402
import kgen  # noqa: E402
import lib  # noqa: E402
import main_board  # noqa: E402
import preview  # noqa: E402

KICAD = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "kicad"))

parts = main_board.main()
jf = jack_board.build("female")
jm = jack_board.build("male")
syms = {s.name: s for s in vars(lib).values() if isinstance(s, kgen.Sym)}
fps = {f.name: f for f in vars(lib).values() if isinstance(f, kgen.Fp)}
kgen.write_libraries(KICAD, syms.values(), fps.values())
for d in ("crkit_main", "crkit_jack_female", "crkit_jack_male"):
    kgen.write_lib_tables(os.path.join(KICAD, d))
os.makedirs(os.path.join(KICAD, "preview"), exist_ok=True)
preview.board_png(os.path.join(KICAD, "preview", "main_board_placement.png"), parts, (main_board.W, main_board.H), main_board.HOLES,
                  "CR-TEST main board rev C, 135 x 101 mm")
preview.schematic_png(os.path.join(KICAD, "preview", "main_board_schematic.png"), parts, main_board.BLOCKS,
                      title="CR-TEST main board rev C schematic (generated)")
for name, ps in (("female", jf), ("male", jm)):
    preview.board_png(os.path.join(KICAD, "preview", f"jack_{name}_placement.png"), ps, (jack_board.W, jack_board.H), jack_board.HOLES,
                      f"CR-TEST jack board ({name}) rev C, 80 x 40 mm")
print("libraries:", len(syms), "symbols,", len(fps), "footprints")
