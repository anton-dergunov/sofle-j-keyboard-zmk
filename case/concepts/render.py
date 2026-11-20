"""Render every concept: closed view, exploded or alternative pose, and a dimensioned cross-section.

Run: uv run python concepts/render.py [concept-key ...]  ->  out/renders/*.png, out/concepts.json
"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("agg")
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath
import numpy as np
import pyvista as pv
import shapely
import shapely.geometry.polygon
import trimesh

sys.path.insert(0, str(Path(__file__).parent))
from common import GAP, KEY, RIM, ROOT, STACK, Z_MID, Part, ghost_pair  # noqa: E402
from designs import CONCEPTS  # noqa: E402

OUT = ROOT / "out" / "renders"
COLORS = {
    "ghost-case": "#cfcac2",
    "ghost-plate": "#8d949c",
    "ghost-dark": "#2f3236",
    "ghost-keys": "#f4f4f2",
    "PA12": "#2a8c82",
    "TPU": "#e07a4f",
    "silicone": "#2b3a47",
    "magnet": "#a9adb3",
}
SECTION_X = 66.7  # through the middle key column


def _pv(m: trimesh.Trimesh) -> pv.PolyData:
    faces = np.hstack([np.full((len(m.faces), 1), 3), m.faces]).ravel()
    return pv.PolyData(np.asarray(m.vertices), faces)


def shot(parts: list[Part], path: Path, view: str = "iso", size=(1500, 1050)):
    pl = pv.Plotter(off_screen=True, window_size=size)
    pl.set_background("white")
    for p in parts:
        mesh = _pv(p.mesh)
        mesh = mesh.compute_normals(feature_angle=35, split_vertices=True)
        pl.add_mesh(mesh, color=COLORS[p.material], smooth_shading=True, specular=0.25, specular_power=20,
                    ambient=0.18, diffuse=0.85)
    pl.enable_anti_aliasing("ssaa")
    b = np.vstack([p.mesh.bounds for p in parts])
    lo, hi = b.min(0), b.max(0)
    c = (lo + hi) / 2
    span = np.linalg.norm(hi - lo)
    dirs = {
        "iso": np.array([-0.55, -1.0, 0.75]),
        "iso-back": np.array([0.6, 1.0, 0.7]),
        "iso-low": np.array([-0.55, -1.0, 0.32]),
        "front": np.array([0.0, -1.0, 0.18]),
        "top": np.array([0.0, -0.0001, 1.0]),
    }
    d = dirs[view] / np.linalg.norm(dirs[view])
    pl.camera.position = tuple(c + d * span * 1.55)
    pl.camera.focal_point = tuple(c)
    pl.camera.up = (0, 0, 1) if view != "top" else (0, 1, 0)
    pl.camera.view_angle = 30
    pl.reset_camera_clipping_range()
    path.parent.mkdir(parents=True, exist_ok=True)
    pl.screenshot(str(path))
    pl.close()


def exploded(parts: list[Part], e: float = 42.0) -> list[Part]:
    out = []
    for p in parts:
        if p.material == "silicone":
            continue
        m = p.mesh.copy()
        if p.material.startswith("ghost"):
            m.apply_translation([0, 0, e if "(right)" in p.name else -e])
        out.append(Part(p.name, m, p.material))
    return out


def section(parts: list[Part], path: Path, title: str, x: float = SECTION_X, notes=()):
    fig, ax = plt.subplots(figsize=(12, 5.2))
    order = ["ghost-case", "ghost-plate", "ghost-dark", "ghost-keys", "PA12", "TPU", "silicone", "magnet"]
    for mat in order:
        for p in parts:
            if p.material != mat:
                continue
            s = p.mesh.section(plane_origin=[x, 0, 0], plane_normal=[1, 0, 0])
            if s is None:
                continue
            # Even-odd combine the cut loops so that holes (a band around the stack) stay open.
            acc = None
            for ent in s.discrete:
                if len(ent) < 3:
                    continue
                loop = shapely.Polygon(ent[:, [1, 2]]).buffer(0)
                acc = loop if acc is None else acc.symmetric_difference(loop)
            for g in getattr(acc, "geoms", [acc]) if acc is not None else []:
                if g.geom_type != "Polygon" or g.area < 1e-3:
                    continue
                g = shapely.geometry.polygon.orient(g, 1.0)
                mpath = MplPath.make_compound_path(
                    MplPath(np.asarray(g.exterior.coords)), *[MplPath(np.asarray(r.coords)) for r in g.interiors])
                ax.add_patch(PathPatch(mpath, fc=COLORS[mat], ec="#333333", lw=0.3))
    ax.autoscale_view()
    ax.set_aspect("equal")
    ax.set_xlabel("y (mm)")
    ax.set_ylabel("z (mm)")
    ax.set_title(title, fontsize=11)
    ax.grid(True, lw=0.25, alpha=0.6)
    for i, n in enumerate(notes):
        ax.text(0.01, 0.97 - 0.07 * i, n, transform=ax.transAxes, fontsize=8.5, va="top",
                bbox=dict(fc="white", ec="none", alpha=0.85))
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def bbox_size(parts):
    b = np.vstack([p.mesh.bounds for p in parts if p.material != "silicone"])
    return (b.max(0) - b.min(0)).round(1).tolist()


def main(keys):
    ghosts = [Part(p.name, p.mesh, p.material) for p in ghost_pair()]
    summary = {}
    for key, (title, fn) in CONCEPTS.items():
        if keys and key not in keys:
            continue
        d = fn()
        parts = d["parts"]
        grams = round(sum(p.grams for p in parts), 1)
        images = []
        if d.get("no_default_pose"):
            for i, (pose, pp) in enumerate(d["poses"].items()):
                f = OUT / f"{key}-{i + 1}-{pose.replace(' ', '-')}.png"
                shot(pp, f)
                images.append((f.name, pose))
            closed = d["poses"]["back to back"]
            size = bbox_size(d["poses"]["side by side"])
            size_alt = bbox_size(closed)
        else:
            closed = ghosts + parts
            f = OUT / f"{key}-1-closed.png"
            shot(closed, f)
            images.append((f.name, "closed"))
            f = OUT / f"{key}-2-closed-back.png"
            shot(closed, f, "iso-back")
            images.append((f.name, "closed, from the back (inner edge)"))
            if "poses" in d:
                for pose, pp in d["poses"].items():
                    f = OUT / f"{key}-3-{pose}.png"
                    shot(pp, f, "iso")
                    images.append((f.name, pose))
            else:
                f = OUT / f"{key}-3-exploded.png"
                shot(exploded(ghosts + parts), f, "iso-low")
                images.append((f.name, "exploded"))
            size = bbox_size(closed)
            size_alt = None
        f = OUT / f"{key}-4-section.png"
        notes = [f"case parts: {grams:.0f} g (MJF {'TPU' if any(p.material == 'TPU' for p in parts) else 'PA12'})",
                 f"keycap tops {KEY:.0f} mm, rim {RIM:.1f} mm; keycap-to-keycap gap {2 * (RIM + GAP / 2 - KEY):.1f} mm"]
        section(closed, f, f"{title} — cut through the middle key column (x = {SECTION_X} mm)", notes=notes)
        images.append((f.name, "cross-section"))
        summary[key] = {"title": title, "grams": grams, "size_mm": size, "size_alt_mm": size_alt,
                        "parts": [{"name": p.name, "material": p.material, "grams": round(p.grams, 1)}
                                  for p in parts],
                        "images": images}
        print(key, grams, "g", size, [i[0] for i in images])
    js = ROOT / "out" / "concepts.json"
    old = json.loads(js.read_text()) if js.exists() else {}
    old.update(summary)
    js.write_text(json.dumps(old, indent=1, ensure_ascii=False))
    print("stack", STACK, "Z_MID", Z_MID)


if __name__ == "__main__":
    main(sys.argv[1:])
