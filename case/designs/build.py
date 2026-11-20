"""Print-ready models of the three shortlisted cases: spacer ring, snap-on lids, hinged clamshell.

Run: uv run python designs/build.py  ->  out/print/*.stl, *.3mf and a check report on stdout.

Frame and stand-in keyboard come from concepts/common.py (newer PandaKB case, left half keys up at the
origin). Measured from the case model: the rim's outer top edge has a 1 mm x 45° chamfer (z 9.6-10.6),
the bottom edge a 0.45 mm x 45° chamfer, and the display column on the inner edge rises to 14.0 mm.
"""

import sys
from pathlib import Path

import numpy as np
import shapely
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "concepts"))
from common import (  # noqa: E402
    KEY, RIM, ROOT, O, Part, difference, ghost_left, mirror_z, off, prism, union,
)

OUT = ROOT / "out" / "print"

# ---------------------------------------------------------------- shared parameters

FIT = 0.5  # clearance to the case wall: MJF holds about ±0.3 %, the FDM case about ±0.3 mm
WALL = 1.6
RIM_IN = -2.9  # bearing faces reach 2.9 mm in from the outer wall, onto the flat rim top
RIM_CHAMFER = (9.6, 10.6)  # z range of the 1 mm x 45° chamfer on the rim's outer edge
BOTTOM_CHAMFER = 0.45
COLUMN_TOP = 14.0
COLUMN_ZONE = shapely.box(118.3, 24.14, 141.07 + 5, 115.18).intersection(off(5))  # column, padded out past O
INNER_EDGE_X = 141.07  # the straight inner (column) edge
PINKY_EDGE_X = 0.0


def edge_frame(p):
    """Point on the outline nearest p, with unit tangent t and outward normal n (2D)."""
    ring = O().exterior
    d = ring.project(shapely.Point(p))
    q = np.array(ring.interpolate(d).coords[0])
    a = np.array(ring.interpolate(d - 2).coords[0])
    b = np.array(ring.interpolate(d + 2).coords[0])
    t = (b - a) / np.linalg.norm(b - a)
    n = np.array([t[1], -t[0]])
    if O().contains(shapely.Point(q + n)):  # make n point outward
        n = -n
    return q, t, n


def local_prism(p, poly_vz, length, du=0.0):
    """Extrude a polygon given in (v = outward distance from the outline, z) along the edge at p."""
    q, t, n = edge_frame(p)
    m = trimesh.creation.extrude_polygon(shapely.Polygon(poly_vz), length)
    m.apply_translation([0, 0, -length / 2 + du])
    M = np.eye(4)
    M[:3, 0] = [n[0], n[1], 0]  # local x -> outward normal
    M[:3, 1] = [0, 0, 1]  # local y -> world z
    M[:3, 2] = [t[0], t[1], 0]  # local z (extrusion) -> along the edge
    M[:3, 3] = [q[0], q[1], 0]
    m.apply_transform(M)
    if m.volume < 0:
        m.invert()
    return m


def local_box(p, v0, v1, z0, z1, u0, u1):
    return local_prism(p, [(v0, z0), (v1, z0), (v1, z1), (v0, z1)], u1 - u0, du=(u0 + u1) / 2)


def snap_tab(p, z_root, z_free, bead, width=16.0, slot=0.8, thin=1.2):
    """Cut a flexible tab into a wall and return (cuts, bead) meshes.

    The tab runs from z_root (attached) to z_free (free end); slots on both sides free it, and its
    outer face is thinned to `thin`. `bead` is a polygon in (v, z) on the tab's inner face.
    """
    lo, hi = sorted((z_root, z_free))
    eps = 0.6 if z_free > z_root else -0.6
    cuts = []
    for s in (-1, 1):
        u0 = s * width / 2
        u1 = s * (width / 2 + slot)
        cuts.append(local_box(p, FIT - 1.0, FIT + WALL + 1.0, lo if z_free > z_root else lo - 1,
                              hi + 1 if z_free > z_root else hi, min(u0, u1), max(u0, u1)))
    cuts.append(local_box(p, FIT + thin, FIT + WALL + 1.0, lo + (eps if z_free < z_root else 0),
                          hi + (0 if z_free < z_root else 1), -width / 2, width / 2))
    del eps
    return cuts, local_prism(p, bead, width - 3.0)


# ---------------------------------------------------------------- 1. spacer ring + straps

RING_GAP = 2 * (KEY - RIM + 1.0)  # rim to rim, 1 mm over each half's keycaps (16.8)
RING_SKIRT = 4.0
STRAPS_X = (34.0, 106.0)
STRAP_W = 12.5  # for 12 mm flat silicone bands


def ring():
    z0, z1 = RIM, RIM + RING_GAP
    outer = FIT + WALL
    body = prism(off(outer).difference(off(RIM_IN)), z0, z1)
    skirts = [prism(off(outer).difference(off(FIT)), z0 - RING_SKIRT, z0),
              prism(off(outer).difference(off(FIT)), z1, z1 + RING_SKIRT)]
    # Step over the display column on the inner edge (top and bottom).
    col = COLUMN_ZONE.buffer(FIT).intersection(off(FIT))
    col_cuts = [prism(col, z0 - 1, COLUMN_TOP + 0.3), prism(col, z1 + RIM - COLUMN_TOP - 0.3, z1 + 1)]
    # Guide ridges for the two straps on the front and back walls.
    ridges = []
    for x in STRAPS_X:
        for side_pt in ((x, -5.0), (x, 130.0)):
            for s in (-1, 1):
                ridges.append(local_box(side_pt, outer - 0.2, outer + 1.0, z0 - RING_SKIRT, z1 + RING_SKIRT,
                                        s * STRAP_W / 2, s * (STRAP_W / 2 + 1.2)))
    return difference(union([body, *skirts, *ridges]), col_cuts)


# ---------------------------------------------------------------- 4. snap-on lids

LID_CLEAR = 2.0  # keycap tops to the lid's underside
LID_TOP = 2.2
LID_SKIRT = 1.4
LID_BOTTOM = -0.9  # skirt reaches a little below the case bottom so the bead can lead in
LID_TABS = [(PINKY_EDGE_X, 72.0), (INNER_EDGE_X, 68.0), (70.0, 125.0), (66.0, 10.0)]


def lid_left():
    z_in = KEY + LID_CLEAR
    z_top = z_in + LID_TOP
    outer = FIT + LID_SKIRT
    skirt = prism(off(outer).difference(off(FIT)), LID_BOTTOM, z_in)
    top = prism(off(outer), z_in, z_top)
    # Bearing ledge on the rim, stepped up over the display column.
    ring_area = off(FIT + 0.01).difference(off(RIM_IN))
    col = COLUMN_ZONE.buffer(FIT)
    ledge = [prism(ring_area.difference(col), RIM, RIM + 1.4),
             prism(ring_area.intersection(col), COLUMN_TOP, COLUMN_TOP + 1.4)]
    cuts, beads = [], []
    # Bead: catches the 0.45 mm bottom chamfer; 45° lead-in below it.
    tip_v, tip_z = -0.35, 0.25
    bead = [(FIT + 0.01, tip_z + (FIT - tip_v)), (tip_v, tip_z), (tip_v, tip_z - 0.15),
            (FIT + 0.01, tip_z - 0.15 - (FIT - tip_v))]
    bead = [(v, max(z, LID_BOTTOM)) for v, z in bead]
    for p in LID_TABS:
        c, b = snap_tab(p, z_root=12.0, z_free=LID_BOTTOM, bead=bead, thin=LID_SKIRT)
        cuts += c
        beads.append(b)
    lid = union([skirt, top, *ledge, *beads])
    return difference(lid, cuts)


# ---------------------------------------------------------------- 5. hinged clamshell

SHELL_GAP = 2 * (KEY - RIM + 1.0)
Z_SPLIT = RIM + SHELL_GAP / 2  # parting plane (19.0)
FLOOR = 1.4
HINGE_R = 3.5
HINGE_AXIS_X = INNER_EDGE_X + FIT + WALL + HINGE_R + 0.3
HINGE_Y = (27.0, 111.0)
HINGE_N = 7  # knuckles; the ends belong to the left tray
KNUCKLE_GAP = 0.6
PIN_PRESS, PIN_FREE = 2.05, 2.45  # hole diameters for a 2 mm rod: press fit in the left tray, free in the right
MAGNETS_Y = (46.0, 96.0)
MAGNET_D, MAGNET_H = 8.0, 2.0
MAGNET_X = PINKY_EDGE_X - (FIT + WALL) - 3.6
TRAY_TABS = [(PINKY_EDGE_X, 71.0), (70.0, 125.0), (66.0, 10.0)]


def _knuckle_cyl(y0, y1, r, x=HINGE_AXIS_X, z=Z_SPLIT):
    c = trimesh.creation.cylinder(radius=r, height=y1 - y0, sections=64)
    c.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    c.apply_translation([x, (y0 + y1) / 2, z])
    return c


def tray_left(parity=0):
    """Tray for the left half (keys up), walls to the parting plane. parity 1 makes the right tray's
    knuckle set (before mirroring)."""
    outer = FIT + WALL
    floor = prism(off(outer), -FLOOR, 0.0)
    walls = prism(off(outer).difference(off(FIT)), 0.0, Z_SPLIT)
    parts = [floor, walls]
    cuts = []

    # Click tabs: bead over the rim's 1 mm chamfer holds the half in its tray.
    tip_v, tip_z = -0.5, 9.95
    bead = [(FIT + 0.01, tip_z - (FIT - tip_v)), (tip_v, tip_z), (tip_v, tip_z + 0.2),
            (FIT + 0.01, tip_z + 0.2 + (FIT - tip_v))]
    for p in TRAY_TABS:
        c, b = snap_tab(p, z_root=1.0, z_free=Z_SPLIT, bead=bead)
        cuts += c
        parts.append(b)

    # Magnet bosses on the pinky edge, pockets open at the parting plane.
    for y in MAGNETS_Y:
        boss = trimesh.creation.cylinder(radius=MAGNET_D / 2 + 1.6, height=9.0, sections=64)
        boss.apply_translation([MAGNET_X, y, Z_SPLIT - 4.5])
        cone = trimesh.creation.cone(radius=MAGNET_D / 2 + 1.6, height=5.0, sections=64)
        cone.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0]))
        cone.apply_translation([MAGNET_X, y, Z_SPLIT - 9.0])
        web = trimesh.creation.box(bounds=[[MAGNET_X, y - 3.0, Z_SPLIT - 9.0], [-FIT - 0.2, y + 3.0, Z_SPLIT]])
        parts += [boss, cone, web]
        pocket = trimesh.creation.cylinder(radius=MAGNET_D / 2 + 0.1, height=MAGNET_H + 0.3, sections=64)
        pocket.apply_translation([MAGNET_X, y, Z_SPLIT - (MAGNET_H + 0.3) / 2 + 0.01])
        cuts.append(pocket)

    # Hinge knuckles along the inner edge.
    seg = (HINGE_Y[1] - HINGE_Y[0]) / HINGE_N
    for i in range(HINGE_N):
        y0 = HINGE_Y[0] + seg * i + (KNUCKLE_GAP / 2 if i > 0 else 0)
        y1 = HINGE_Y[0] + seg * (i + 1) - (KNUCKLE_GAP / 2 if i < HINGE_N - 1 else 0)
        mine = (i % 2 == 0) if parity == 0 else (i % 2 == 1)
        if mine:
            parts.append(_knuckle_cyl(y0, y1, HINGE_R))
            parts.append(trimesh.creation.box(bounds=[[INNER_EDGE_X + FIT + WALL - 0.5, y0, Z_SPLIT - HINGE_R],
                                                      [HINGE_AXIS_X, y1, Z_SPLIT]]))
        else:
            # Clearance for the other tray's knuckle as it swings past.
            cuts.append(_knuckle_cyl(y0 - KNUCKLE_GAP / 2, y1 + KNUCKLE_GAP / 2, HINGE_R + 0.5))
    cuts.append(_knuckle_cyl(HINGE_Y[0] - 1, HINGE_Y[1] + 1, (PIN_PRESS if parity == 0 else PIN_FREE) / 2))

    # Thumb lips at the front edge to pull the book open (offset left/right per tray).
    lip_x = 58.0 if parity == 0 else 82.0
    parts.append(local_box((lip_x, 10.0), FIT + WALL - 0.3, FIT + WALL + 2.5, Z_SPLIT - 3.0, Z_SPLIT, -6, 6))
    return difference(union(parts), cuts)


def clamshell():
    left = tray_left(0)
    right = mirror_z(tray_left(1), Z_SPLIT)
    return left, right


# ---------------------------------------------------------------- checks and export


def interference(a, b):
    try:
        i = trimesh.boolean.intersection([a, b], engine="manifold")
        return 0.0 if i is None or i.is_empty else float(i.volume)
    except Exception:
        return float("nan")


def report(name, parts, ghosts):
    print(f"\n== {name}")
    for p in parts:
        m = p.mesh
        print(f"  {p.name:18s} {p.grams:6.1f} g  watertight={m.is_watertight}  "
              f"size={np.round(m.extents, 1).tolist()}")
        for g in ghosts:
            v = interference(m, g.mesh)
            if v > 0.05:
                print(f"    overlaps {g.name:24s} {v:7.2f} mm³" + ("  (snap beads, by design)" if v < 60 else ""))


def export(name, mesh):
    OUT.mkdir(parents=True, exist_ok=True)
    mesh.export(OUT / f"{name}.stl")
    mesh.export(OUT / f"{name}.3mf")


def build():
    gl = ghost_left()
    ghosts_pair = [*gl, *[Part(p.name + " (right)", mirror_z(p.mesh, RIM + RING_GAP / 2), p.material) for p in gl]]
    out = {}

    r = ring()
    out["ring"] = [Part("spacer ring", r, "PA12")]
    report("1. spacer ring", out["ring"], ghosts_pair)

    lid = lid_left()
    lid_r = lid.copy()
    lid_r.apply_transform(np.diag([-1.0, 1, 1, 1]))  # the right half is the mirror image
    out["lids"] = [Part("lid (left)", lid, "PA12"), Part("lid (right)", lid_r, "PA12")]
    report("4. snap-on lids (left lid on the left half)", out["lids"][:1], gl)
    print(f"  pair: {sum(p.grams for p in out['lids']):.1f} g")

    left, right = clamshell()
    out["clamshell"] = [Part("tray (left)", left, "PA12"), Part("tray (right)", right, "PA12")]
    gpair5 = [*gl, *[Part(p.name + " (right)", mirror_z(p.mesh, Z_SPLIT), p.material) for p in gl]]
    report("5. clamshell", out["clamshell"], gpair5)
    print(f"  trays together: {sum(p.grams for p in out['clamshell']):.1f} g, "
          f"closed size {np.round(trimesh.util.concatenate([left, right]).extents, 1).tolist()}")
    print(f"  tray-to-tray overlap: {interference(left, right):.2f} mm³")

    # Keycap gap check (same in all face-to-face designs).
    caps = next(p.mesh for p in gl if p.name == "keycaps")
    print(f"\nkeycap tops {caps.bounds[1][2]:.1f} mm; facing keycap gap ring {2 * (RIM + RING_GAP / 2 - KEY):.1f} mm, "
          f"clamshell {2 * (Z_SPLIT - KEY):.1f} mm; lid underside {KEY + LID_CLEAR:.1f} mm")

    # Export print orientation: everything flat on its largest face.
    export("1-spacer-ring", r)
    for nm, m in (("4-lid-left", lid), ("4-lid-right", lid_r)):
        m2 = m.copy()
        m2.apply_transform(np.diag([1.0, 1, -1, 1]))  # top face down
        export(nm, m2)
    export("5-tray-left", left)
    rr = right.copy()
    rr.apply_transform(np.diag([1.0, 1, -1, 1]))
    export("5-tray-right", rr)
    return out, gl


if __name__ == "__main__":
    build()
