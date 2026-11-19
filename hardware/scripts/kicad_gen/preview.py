"""PNG previews of a generated board (placement + ratsnest) and schematic, for review without KiCad."""
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, Rectangle  # noqa: E402

import kgen  # noqa: E402


def pad_positions(p):
    x0, y0, a = p.pcb
    for pd in p.fp.pads:
        dx, dy = kgen.rot(pd.x, pd.y, a)
        yield pd, x0 + dx, y0 + dy


def board_png(path, parts, size, holes=(), title=""):
    W, H = size
    fig, ax = plt.subplots(figsize=(W / 7, H / 7 + 0.6), dpi=150)
    ax.add_patch(Rectangle((0, 0), W, H, fc="#1f4d2b", ec="#e6e600", lw=1.2))
    for hx, hy in holes:
        ax.add_patch(Circle((hx, hy), 1.6, fc="white", ec="#999"))
    netpts = {}
    for p in parts:
        x1, y1, x2, y2 = kgen.placed_courtyard(p, 0, 0)
        ax.add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, fc="none", ec="#d0d0d0", lw=0.3))
        for pd, x, y in pad_positions(p):
            sx, sy = (pd.sx, pd.sy) if p.pcb[2] % 180 == 0 else (pd.sy, pd.sx)
            col = "#c8a040" if pd.kind == "smd" else "#e0c060"
            if pd.kind == "np_thru_hole":
                ax.add_patch(Circle((x, y), pd.drill / 2, fc="white", ec="#999", lw=0.3))
                continue
            if pd.shape == "circle":
                ax.add_patch(Circle((x, y), sx / 2, fc=col, ec="none"))
            else:
                ax.add_patch(Rectangle((x - sx / 2, y - sy / 2), sx, sy, fc=col, ec="none"))
            if pd.drill:
                ax.add_patch(Circle((x, y), pd.drill / 2, fc="#1f4d2b", ec="none"))
            n = p.nets.get(pd.num)
            if n:
                netpts.setdefault(n, []).append((x, y))
        fs = 3.2 if (x2 - x1) < 4 else 4.5
        ax.text((x1 + x2) / 2, y1 - 0.15, p.ref, ha="center", va="bottom", fontsize=fs, color="white")
    for n, pts in netpts.items():
        if n == "GND" or len(pts) < 2:
            continue
        col = "#ff6060" if n in ("F_BUS", "LO_RTN", "+5V", "I_HI", "ACS_IP") or n.startswith("MF") else "#7fd0ff"
        done, rest = [pts[0]], pts[1:]
        while rest:                      # Prim MST
            best = min(((a, b) for a in done for b in rest), key=lambda ab: math.dist(*ab))
            ax.plot([best[0][0], best[1][0]], [best[0][1], best[1][1]], color=col, lw=0.25, alpha=0.7)
            done.append(best[1]); rest.remove(best[1])
    ax.set_xlim(-2, W + 2); ax.set_ylim(H + 2, -4); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(title + "   (placement and ratsnest, not routed; red = 1 mm power nets, blue = signals, GND = pours)", fontsize=7)
    fig.savefig(path, bbox_inches="tight", facecolor="white"); plt.close(fig)


def schematic_png(path, parts, blocks, size=(841, 594), title=""):
    W, H = size
    fig, ax = plt.subplots(figsize=(W / 25, H / 25), dpi=110)
    ax.add_patch(Rectangle((0, 0), W, H, fc="white", ec="#888"))
    for b in blocks:
        x1, y1, x2, y2 = b["rect"]
        ax.add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, fc="none", ec="#999", ls="--", lw=0.8))
        ax.text(x1 + 2.5, y1 + 5, b["name"], fontsize=11, weight="bold", va="bottom", color="#333")
        if b.get("text"):
            ax.text(x1 + 2.5, y1 + 9.5, b["text"], fontsize=6.5, va="bottom", color="#555")
    for p in parts:
        X, Y = p.sch
        s = p.sym
        ax.add_patch(Rectangle((X - s.width / 2, Y - s.height / 2), s.width, s.height, fc="#ffffcc", ec="#880000", lw=0.6))
        ax.text(X, Y - s.height / 2 - 0.6, p.ref, ha="center", va="bottom", fontsize=4.5, color="#006", weight="bold")
        ax.text(X, Y + s.height / 2 + 0.6, p.value, ha="center", va="top", fontsize=4, color="#333")
        for side, i, num, name in s.pins():
            px, py = s.pin_xy(side, i)
            x, y = X + px, Y - py
            ex = x - 2.54 if side == "L" else x + 2.54
            bx = X - s.width / 2 if side == "L" else X + s.width / 2
            ax.plot([bx, ex], [y, y], color="#880000", lw=0.4)
            if s.show_names and len(s.left) + len(s.right) > 2:
                ax.text(bx + (0.6 if side == "L" else -0.6), y, name, fontsize=2.8, va="center", ha="left" if side == "L" else "right")
            net = p.nets.get(num)
            if net is None:
                ax.plot([x - 0.6, x + 0.6], [y - 0.6, y + 0.6], color="blue", lw=0.4)
                ax.plot([x - 0.6, x + 0.6], [y + 0.6, y - 0.6], color="blue", lw=0.4)
            else:
                ax.text(ex + (-0.4 if side == "L" else 0.4), y - 0.3, net, fontsize=3, color="#006400",
                        ha="right" if side == "L" else "left", va="bottom")
    ax.set_xlim(0, W); ax.set_ylim(H, 0); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(title, fontsize=12)
    fig.savefig(path, bbox_inches="tight", facecolor="white"); plt.close(fig)
