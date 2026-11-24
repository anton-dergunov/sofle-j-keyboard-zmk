"""Renders and close-up sections of the three print-ready designs.

Run: uv run python designs/render.py  ->  out/renders/d*.png, out/designs.json
"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("agg")
import matplotlib.pyplot as plt
import numpy as np
import pyvista as pv
import shapely
import shapely.geometry.polygon
import trimesh
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "concepts"))
import build as B  # noqa: E402
from common import RIM, Part, mirror_z  # noqa: E402
from render import COLORS, _pv  # noqa: E402

OUT = B.ROOT / "out" / "renders"


def shot(parts, path, direction, focus=None, span=None, size=(1500, 1050), parallel=False):
    pl = pv.Plotter(off_screen=True, window_size=size)
    pl.set_background("white")
    for p in parts:
        mesh = _pv(p.mesh).compute_normals(feature_angle=35, split_vertices=True)
        pl.add_mesh(mesh, color=COLORS[p.material], smooth_shading=True, specular=0.25, specular_power=20,
                    ambient=0.18, diffuse=0.85)
    pl.enable_anti_aliasing("ssaa")
    b = np.vstack([p.mesh.bounds for p in parts])
    lo, hi = b.min(0), b.max(0)
    c = np.array(focus) if focus is not None else (lo + hi) / 2
    s = span if span is not None else np.linalg.norm(hi - lo)
    d = np.array(direction, float)
    d /= np.linalg.norm(d)
    pl.camera.position = tuple(c + d * s * 1.55)
    pl.camera.focal_point = tuple(c)
    pl.camera.up = (0, 0, 1) if abs(d[2]) < 0.99 else (0, 1, 0)
    pl.camera.view_angle = 30
    if parallel:
        pl.enable_parallel_projection()
    pl.reset_camera_clipping_range()
    pl.screenshot(str(path))
    pl.close()


def section(parts, path, title, axis="x", at=66.7, lim=None, notes=(), size=(12, 5.2)):
    normal = {"x": [1, 0, 0], "y": [0, 1, 0]}[axis]
    keep = [1, 2] if axis == "x" else [0, 2]
    fig, ax = plt.subplots(figsize=size)
    order = ["ghost-case", "ghost-plate", "ghost-dark", "ghost-keys", "PA12", "PETG", "TPU", "silicone", "magnet"]
    for mat in order:
        for p in parts:
            if p.material != mat:
                continue
            origin = [at, 0, 0] if axis == "x" else [0, at, 0]
            s = p.mesh.section(plane_origin=origin, plane_normal=normal)
            if s is None:
                continue
            acc = None
            for ent in s.discrete:
                if len(ent) < 3:
                    continue
                loop = shapely.Polygon(ent[:, keep]).buffer(0)
                acc = loop if acc is None else acc.symmetric_difference(loop)
            for g in getattr(acc, "geoms", [acc]) if acc is not None else []:
                if g.geom_type != "Polygon" or g.area < 1e-4:
                    continue
                g = shapely.geometry.polygon.orient(g, 1.0)
                mp = MplPath.make_compound_path(MplPath(np.asarray(g.exterior.coords)),
                                                *[MplPath(np.asarray(r.coords)) for r in g.interiors])
                ax.add_patch(PathPatch(mp, fc=COLORS[mat], ec="#333333", lw=0.4))
    ax.autoscale_view()
    if lim:
        ax.set_xlim(*lim[0])
        ax.set_ylim(*lim[1])
    ax.set_aspect("equal")
    ax.set_xlabel(f"{'y' if axis == 'x' else 'x'} (mm)")
    ax.set_ylabel("z (mm)")
    ax.set_title(title, fontsize=11)
    ax.grid(True, lw=0.25, alpha=0.6)
    for i, n in enumerate(notes):
        ax.text(0.01, 0.97 - 0.075 * i, n, transform=ax.transAxes, fontsize=8.5, va="top",
                bbox=dict(fc="white", ec="none", alpha=0.85))
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def ghosts(z_mirror=None):
    gl = [Part(p.name, p.mesh, p.material) for p in B.ghost_left()]
    if z_mirror is None:
        return gl
    return gl + [Part(p.name + " (right)", mirror_z(p.mesh, z_mirror), p.material) for p in gl]


def lifted(parts, dz):
    out = []
    for p in parts:
        m = p.mesh.copy()
        m.apply_translation([0, 0, dz])
        out.append(Part(p.name, m, p.material))
    return out


def rotated_open(parts, t=B.MJF):
    rot = B.open_rotation(t)
    out = []
    for p in parts:
        m = p.mesh.copy()
        m.apply_transform(rot)
        out.append(Part(p.name, m, p.material))
    return out


ISO = (-0.55, -1.0, 0.75)
ISO_LOW = (-0.55, -1.0, 0.32)
BACK = (0.6, 1.0, 0.7)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    out, _ = B.build()
    imgs = {}

    # ---- 1. ring
    zc = RIM + B.RING_GAP / 2
    g2 = ghosts(zc)
    ring = out["ring"]
    imgs["ring"] = []
    f = OUT / "d1-closed.png"
    shot(g2 + ring, f, ISO)
    imgs["ring"].append((f.name, "Closed (straps not shown: 12 mm silicone bands sit between the ridges)"))
    f = OUT / "d1-exploded.png"
    ex = [Part(p.name, p.mesh.copy(), p.material) for p in g2]
    for p in ex:
        p.mesh.apply_translation([0, 0, 40 if "(right)" in p.name else -40])
    shot(ex + ring, f, ISO_LOW)
    imgs["ring"].append((f.name, "Exploded"))
    f = OUT / "d1-ring-alone.png"
    shot(ring, f, (-0.3, -1.0, 1.1))
    imgs["ring"].append((f.name, "The ring alone: the notch on the right steps over the display column"))
    f = OUT / "d1-section-keys.png"
    section(g2 + ring, f, "Spacer ring: cut through the middle key column (x = 66.7)",
            notes=["keycap tops 2.0 mm apart; ring bears on both rims", "skirts 4 mm over each case wall, 0.5 mm clearance"])
    imgs["ring"].append((f.name, "Cross-section through the keys"))
    f = OUT / "d1-section-column.png"
    section(g2 + ring, f, "Spacer ring: cut along y = 70 at the inner edge, through the display columns",
            axis="y", at=70.0, lim=((105, 150), (0, 38)), size=(8, 6.4),
            notes=["the ring steps over the 14 mm column", "and still bears on the rim beside it"])
    imgs["ring"].append((f.name, "Close-up: stepping over the display column"))

    # ---- 4. lids
    gl = ghosts()
    lidL = out["lids"][0]
    imgs["lids"] = []
    f = OUT / "d4-on.png"
    shot(gl + [lidL], f, ISO)
    imgs["lids"].append((f.name, "Lid on the left half"))
    f = OUT / "d4-off.png"
    shot(gl + lifted([lidL], 30), f, ISO_LOW)
    imgs["lids"].append((f.name, "Lid lifted off"))
    f = OUT / "d4-underside.png"
    shot([lidL], f, (-0.4, -0.9, -0.9))
    imgs["lids"].append((f.name, "Underside: the rim ledge and the four click tabs"))
    f = OUT / "d4-section.png"
    section(gl + [lidL], f, "Lid: cut along y = 72 through the pinky-side and inner tabs", axis="y", at=72.0,
            notes=["lid underside 2 mm above the keycaps, top 2.2 mm", "ledge rests on the rim (and on the column)"])
    imgs["lids"].append((f.name, "Cross-section through two tabs"))
    f = OUT / "d4-bead.png"
    section(gl + [lidL], f, "Lid tab close-up (pinky edge, y = 72)", axis="y", at=72.0,
            lim=((-4, 6), (-2, 6)), size=(6.4, 5.6),
            notes=["bead clicks under the 0.45 mm", "bottom chamfer of the case"])
    imgs["lids"].append((f.name, "Close-up: the bead under the case's bottom chamfer"))

    # ---- 5. clamshell
    left, right = out["clamshell"]
    g5 = ghosts(B.Z_SPLIT)
    imgs["clamshell"] = []
    f = OUT / "d5-closed.png"
    shot(g5 + [left, right], f, ISO)
    imgs["clamshell"].append((f.name, "Closed: magnets on the pinky side, thumb lips at the front"))
    f = OUT / "d5-hinge.png"
    shot(g5 + [left, right], f, BACK)
    imgs["clamshell"].append((f.name, "Closed, from the back: the hinge on the inner edge"))
    right_side = [p for p in g5 if "(right)" in p.name] + [right]
    left_side = [p for p in g5 if "(right)" not in p.name] + [left]
    f = OUT / "d5-open.png"
    shot(left_side + rotated_open(right_side), f, ISO)
    imgs["clamshell"].append((f.name, "Opened flat: both halves keys up, ready to type"))
    f = OUT / "d5-empty.png"
    shot([left] + rotated_open([right]), f, (-0.35, -1.0, 1.1))
    imgs["clamshell"].append((f.name, "Empty trays: click tabs, magnet pockets and hinge"))
    f = OUT / "d5-tab-3d.png"
    shot([left], f, (0.25, 1.0, 0.45), focus=(52.0, 16.0, 9.0), span=30)
    imgs["clamshell"].append((f.name, "A click tab from inside the tray: two slots free a strip of wall, the bead clicks over the rim"))
    f = OUT / "d5-front.png"
    shot([left, right], f, (-0.7, -1.0, 0.55), focus=(68.0, 12.0, 19.0), span=55)
    imgs["clamshell"].append((f.name, "Front edge, closed: the click tab and the two thumb lips"))
    f = OUT / "d5-section.png"
    section(g5 + [left, right], f, "Clamshell: cut through the middle key column (x = 66.7)",
            notes=["keycap tops 2.0 mm apart", "floors 1.4 mm, walls 1.6 mm"])
    imgs["clamshell"].append((f.name, "Cross-section through the keys"))
    f = OUT / "d5-edges.png"
    section(g5 + [left, right], f, "Rounded edges (pinky edge, y = 60)", axis="y", at=60.0,
            lim=((-16, 5), (-3, 41)), size=(6.2, 9.0),
            notes=["bottom edges R 2.5 mm,", "1.07 mm at the thinnest", "seam edges R 1 mm"])
    imgs["clamshell"].append((f.name, "Close-up: the rounded bottom edges and the groove at the seam"))
    f = OUT / "d5-corner.png"
    shot([left, right], f, (-0.9, -0.6, -0.35), focus=(2.0, 30.0, 12.0), span=60)
    imgs["clamshell"].append((f.name, "Closed, from below the pinky-side front corner: rounded bottom, lip and magnet boss"))
    f = OUT / "d5-tab.png"
    section(g5 + [left, right], f, "Tray tab close-up (pinky edge, y = 71)", axis="y", at=71.0,
            lim=((-5, 6), (4, 30)), size=(5.2, 7.6),
            notes=["beads click over the rim's", "1 mm chamfer"])
    imgs["clamshell"].append((f.name, "Close-up: tray tab beads over the rims"))
    f = OUT / "d5-hinge-section.png"
    section(g5 + [left, right], f, "Hinge close-up (y = 33, through a knuckle)", axis="y", at=33.0,
            lim=((134, 156), (8, 30)), size=(6.4, 6.4), notes=["2 mm steel pin", "knuckles Ø7 mm"])
    imgs["clamshell"].append((f.name, "Close-up: hinge knuckle and pin hole"))

    # ---- 5. clamshell, FDM version
    t = B.FDM
    left, right = out["clamshell-fdm"]
    imgs["clamshell-fdm"] = []
    f = OUT / "d5f-closed.png"
    shot(g5 + [left, right], f, ISO)
    imgs["clamshell-fdm"].append((f.name, "Closed"))
    f = OUT / "d5f-below.png"
    shot([left, right], f, (0.9, 0.35, -0.55), focus=(150.0, 60.0, 12.0), span=95)
    imgs["clamshell-fdm"].append((f.name, "From below the hinge: each knuckle runs into the wall at 45°, so nothing needs supports"))
    f = OUT / "d5f-corner.png"
    shot([left, right], f, (-0.9, -0.6, -0.35), focus=(2.0, 30.0, 12.0), span=60)
    imgs["clamshell-fdm"].append((f.name, "From below the pinky-side corner: chamfered bottom, magnet boss and lip with 45° undersides"))
    f = OUT / "d5f-open.png"
    shot([left] + rotated_open([right], t), f, (-0.35, -1.0, 1.1))
    imgs["clamshell-fdm"].append((f.name, "Opened flat, empty"))
    f = OUT / "d5f-hinge-section.png"
    section(g5 + [left, right], f, "FDM hinge close-up (y = 33, through a knuckle)", axis="y", at=33.0,
            lim=((134, 158), (4, 34)), size=(6.4, 7.6), notes=["teardrop knuckle: 45° underside", "2 mm pin"])
    imgs["clamshell-fdm"].append((f.name, "Close-up: a teardrop knuckle"))
    f = OUT / "d5f-edges.png"
    section(g5 + [left, right], f, "FDM edges (pinky edge, y = 60)", axis="y", at=60.0,
            lim=((-16, 5), (-3, 42)), size=(6.2, 9.0),
            notes=["walls 2.0 mm, floors 1.8 mm", "bottom chamfer 2 mm × 45°,", "1.26 mm at the thinnest"])
    imgs["clamshell-fdm"].append((f.name, "Close-up: chamfered bottom edges"))

    summary = {k: {"grams": round(sum(p.grams for p in v), 1),
                   "parts": [{"name": p.name, "grams": round(p.grams, 1),
                              "size_mm": np.round(p.mesh.extents, 1).tolist()} for p in v],
                   "images": imgs[k]} for k, v in out.items()}
    (B.ROOT / "out" / "designs.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    for k, v in summary.items():
        print(k, v["grams"], [i[0] for i in v["images"]])


if __name__ == "__main__":
    main()
