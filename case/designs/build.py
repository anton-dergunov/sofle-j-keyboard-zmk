"""Print-ready models of the three shortlisted cases: spacer ring, snap-on lids, hinged clamshell.

Run: uv run python designs/build.py  ->  out/print/*.stl, *.3mf and a check report on stdout.

Frame and stand-in keyboard come from concepts/common.py (newer PandaKB case, left half keys up at the
origin). Measured from the case model: the rim's outer top edge has a 1 mm x 45° chamfer (z 9.6-10.6),
the bottom edge a 0.45 mm x 45° chamfer, and the display column on the inner edge rises to 14.0 mm.
"""

import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import build123d as bd
import numpy as np
import shapely
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "concepts"))
from common import (  # noqa: E402
    KEY, RIM, ROOT, O, Part, difference, ghost_left, mirror_z, off, outline_data, prism, union,
)
from sofle_geom import NEW_STEP  # noqa: E402

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


# ---------------------------------------------------------------- CAD (OCCT) pieces for rounded edges


def occ_mesh(shape, tol=0.02, angular=0.15):
    """Tessellate a build123d solid into a closed trimesh. The defaults keep facets within 0.01 mm of a
    2.5 mm round, well under what MJF resolves; OCCT keeps the first tessellation on the shape."""
    v, f = shape.tessellate(tol, angular)
    m = trimesh.Trimesh([(p.X, p.Y, p.Z) for p in v], f)
    m.merge_vertices(digits_vertex=5)  # stitches faces that meet at a pole (revolved domes)
    m.update_faces(m.nondegenerate_faces())
    m.remove_unreferenced_vertices()
    if m.volume < 0:
        m.invert()
    assert m.is_watertight, "tessellation is not closed"
    return m


def _merge_collinear(edges):
    out = []
    for e in edges:
        if out and e.geom_type == bd.GeomType.LINE and out[-1].geom_type == bd.GeomType.LINE \
                and abs(out[-1].tangent_at(0).dot(e.tangent_at(0))) > 1 - 1e-5:
            out[-1] = bd.Edge.make_line(out[-1].position_at(0), e.position_at(1))
            continue
        out.append(e)
    return out


def _drop_micro_arcs(face):
    """OCCT's offset puts a near-zero arc on every almost-tangent joint; fillets fail on those."""
    es = list(face.outer_wire().order_edges())
    keep = [True] * len(es)
    for i, e in enumerate(es):
        if e.geom_type == bd.GeomType.CIRCLE and e.length / e.radius < np.radians(0.2):
            j = (i + 1) % len(es)
            assert es[j].geom_type == bd.GeomType.LINE, "micro arc before a non-line"
            es[j] = bd.Edge.make_line(e.position_at(0), es[j].position_at(1))
            keep[i] = False
    return bd.Face(bd.Wire([e for e, k in zip(es, keep) if k]))


@cache
def outline_face():
    """The case's outer outline as the STEP model's own lines and arcs, in the frame of O()."""
    solid = bd.import_step(str(NEW_STEP)).solids()[0]
    z = solid.bounding_box().min.Z + 9.0  # the same height O() is cut at
    cut = max(solid.intersect(bd.Plane.XY.offset(z)).faces(), key=lambda f: f.area)
    x0, y0 = outline_data()[2]
    wire = cut.outer_wire().moved(bd.Location((-x0, -y0, -z)))
    return bd.Face(bd.Wire(_merge_collinear(wire.order_edges())))


def offset_face(d, ease=2.0):
    """Outline grown by d with round corners; inside corners eased to at least `ease` radius, which also
    rounds the one sharp inside corner (thumb cluster meets the inner edge)."""
    f = _drop_micro_arcs(bd.offset(outline_face(), d + ease, kind=bd.Kind.ARC).faces()[0])
    return _drop_micro_arcs(bd.offset(f, -ease, kind=bd.Kind.ARC).faces()[0])


def edge_matrix(p):
    """Local frame at the outline point nearest p: x outward, y up, z along the edge."""
    q, t, n = edge_frame(p)
    M = np.eye(4)
    M[:3, 0] = [n[0], n[1], 0]
    M[:3, 1] = [0, 0, 1]
    M[:3, 2] = [t[0], t[1], 0]
    M[:3, 3] = [q[0], q[1], 0]
    return M


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
    m = trimesh.creation.extrude_polygon(shapely.Polygon(poly_vz), length)
    m.apply_translation([0, 0, -length / 2 + du])
    m.apply_transform(edge_matrix(p))
    if m.volume < 0:
        m.invert()
    return m


def local_box(p, v0, v1, z0, z1, u0, u1):
    return local_prism(p, [(v0, z0), (v1, z0), (v1, z1), (v0, z1)], u1 - u0, du=(u0 + u1) / 2)


def snap_tab(p, z_root, z_free, bead, width=16.0, slot=0.8, thin=1.2, fit=FIT, wall=WALL):
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
        cuts.append(local_box(p, fit - 1.0, fit + wall + 1.0, lo if z_free > z_root else lo - 1,
                              hi + 1 if z_free > z_root else hi, min(u0, u1), max(u0, u1)))
    cuts.append(local_box(p, fit + thin, fit + wall + 1.0, lo + (eps if z_free < z_root else 0),
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
HINGE_R = 3.5
HINGE_Y = (27.0, 111.0)
HINGE_N = 7  # knuckles; the ends belong to the left tray
KNUCKLE_GAP = 0.6
HINGE_CLEAR = 0.5  # the outermost tray wall to the pin axis
MAGNETS_Y = (46.0, 96.0)
MAGNET_D, MAGNET_H = 8.0, 2.0
TRAY_TABS = [(PINKY_EDGE_X, 71.0), (70.0, 125.0), (52.0, 10.0)]
TOP_ROUND = 1.0  # outer edge at the parting plane; the two trays' rounds form a shallow groove at the seam
LUMP_ROUND = 1.0  # thumb lips, magnet bosses and hinge ends


@dataclass(frozen=True)
class Tray:
    """Clamshell parameters for one print process."""
    suffix: str  # appended to the file names
    material: str
    fit: float = FIT
    wall: float = WALL
    floor: float = 1.4
    slot: float = 0.8  # the two slots that free each click tab
    pin_press: float = 2.05  # hole diameters for a 2 mm rod: press fit in the left tray,
    pin_free: float = 2.45  # free in the right
    magnet_hole: float = MAGNET_D + 0.2
    bottom_round: float = 0.0  # outer bottom edge: a round (MJF) ...
    bottom_chamfer: float = 0.0  # ... or a 45° chamfer, which prints cleanly on the bed (FDM)
    min_corner: float = 1.0  # least material allowed where the bottom edge is cut back
    self_supporting: bool = False  # 45° undersides on knuckles, magnet bosses and lips (FDM, no supports)

    @property
    def hinge_x(self):
        """The pin axis. Beyond the knuckle's own clearance from the straight inner wall, it must also lie
        outside the thumb cluster's corner (x 146.3 at y 20, past the straight edge): any part of either
        tray beyond the axis would run into the other tray as soon as the hinge turns."""
        return max(INNER_EDGE_X + self.fit + self.wall + HINGE_R + 0.3,
                   O().bounds[2] + self.fit + self.wall + HINGE_CLEAR)

    @property
    def magnet_x(self):
        return PINKY_EDGE_X - (self.fit + self.wall) - 3.6


# MJF/SLS nylon: thin walls and soft rounds; the process needs no supports.
MJF = Tray("", "PA12", bottom_round=2.5)
# FDM (PETG, ABS+): thicker walls and floor, nothing steeper than 45° overhanging, and the holes and
# slots opened up because FDM prints them small. 0.6 mm fit: a loose fit still works, a tight one doesn't.
FDM = Tray("-fdm", "PETG", fit=0.6, wall=2.0, floor=1.8, slot=1.0, pin_press=2.15, pin_free=2.6,
           magnet_hole=MAGNET_D + 0.4, bottom_chamfer=2.0, min_corner=1.2, self_supporting=True)
HINGE_AXIS_X = MJF.hinge_x


def _knuckle_cyl(y0, y1, r, x=HINGE_AXIS_X, z=Z_SPLIT):
    c = trimesh.creation.cylinder(radius=r, height=y1 - y0, sections=64)
    c.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    c.apply_translation([x, (y0 + y1) / 2, z])
    return c


@cache
def tray_body(t: Tray):
    """Floor and wall as one solid, outer bottom and top edges rounded or chamfered (the cavity is cut later)."""
    f = offset_face(t.fit + t.wall).moved(bd.Location((0, 0, -t.floor)))
    slab = bd.extrude(f, amount=Z_SPLIT + t.floor)
    bottom = slab.faces().sort_by(bd.Axis.Z)[0].edges()
    slab = bd.chamfer(bottom, t.bottom_chamfer) if t.bottom_chamfer else bd.fillet(bottom, t.bottom_round)
    slab = bd.fillet(slab.faces().sort_by(bd.Axis.Z)[-1].edges(), TOP_ROUND)
    return occ_mesh(slab)


@cache
def magnet_boss(y, t: Tray):
    """Round boss on the pinky-side wall; magnet pocket cut later. MJF: a domed underside. FDM: the
    underside slopes up at 45° from the wall, so it prints without supports."""
    r = MAGNET_D / 2 + 1.6
    if t.self_supporting:
        x_out = t.magnet_x - r  # outermost point of the boss
        z_out = Z_SPLIT - (MAGNET_H + 0.3) - 1.6  # 1.6 mm under the pocket floor there
        boss = bd.Cylinder(r, 4 * r, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MAX))
        boss = boss.moved(bd.Location((t.magnet_x, y, Z_SPLIT)))
        boss = bd.split(boss, bisect_by=bd.Plane(origin=(x_out, y, z_out), z_dir=(1, 0, 1)), keep=bd.Keep.TOP)
        boss = bd.fillet(boss.edges().filter_by(bd.GeomType.CIRCLE).sort_by(bd.Axis.Z)[-1], LUMP_ROUND)
        return occ_mesh(boss)
    h, dome = 9.0, 5.0
    with bd.BuildSketch(bd.Plane.XZ) as sk:  # profile in (radius, height), revolved about the axis
        with bd.BuildLine():
            bd.Polyline((0, -dome), (0, h), (r, h), (r, 0))
            bd.EllipticalCenterArc((0, 0), r, dome, start_angle=270, arc_size=90)
        bd.make_face()
    boss = bd.revolve(sk.sketch, bd.Axis.Z)
    boss = bd.fillet(boss.edges().filter_by(bd.GeomType.CIRCLE).sort_by(bd.Axis.Z)[-1], LUMP_ROUND)
    return occ_mesh(boss.moved(bd.Location((t.magnet_x, y, Z_SPLIT - h))))


def thumb_lip(x, t: Tray):
    """Pull lip on the front wall, rounded on every edge that shows; FDM gives it a 45° underside."""
    v0, v1 = t.fit + 0.3, t.fit + t.wall + 2.5  # starts inside the wall so the top round leaves no notch
    if t.self_supporting:
        pts = [(v0, Z_SPLIT), (v1, Z_SPLIT), (v1, Z_SPLIT - 3.0), (v0, Z_SPLIT - 3.0 - (v1 - v0))]
        lip = bd.extrude(bd.Face(bd.Wire.make_polygon([bd.Vector(v, z, 0) for v, z in pts], close=True)),
                         amount=6.0, both=True)
    else:
        lip = bd.Box(v1 - v0, 3.0, 12.0, align=(bd.Align.MIN, bd.Align.MIN, bd.Align.CENTER))
        lip = lip.moved(bd.Location((v0, Z_SPLIT - 3.0, 0)))
    inner = lip.faces().sort_by(bd.Axis.X)[0]
    lip = bd.fillet([e for e in lip.edges() if e not in inner.edges()], LUMP_ROUND)
    m = occ_mesh(lip)
    m.apply_transform(edge_matrix((x, 10.0)))
    return m


def knuckle(y0, y1, t: Tray, round_ends=()):
    """One hinge knuckle on its bridge to the wall; `round_ends` lists the free ends ('lo', 'hi') to round.
    MJF: a flat-bottomed bridge. FDM: a teardrop, its 45° underside running down into the wall."""
    a = t.hinge_x
    x_wall = INNER_EDGE_X + t.fit + 0.1  # inside the wall, so the top round leaves no notch
    cyl = bd.Cylinder(HINGE_R, y1 - y0, rotation=(90, 0, 0)).moved(bd.Location((a, (y0 + y1) / 2, Z_SPLIT)))
    if t.self_supporting:
        s = HINGE_R / np.sqrt(2)  # the 45° tangent point on the knuckle's lower outer side
        tx, tz = a + s, Z_SPLIT - s
        pts = [(x_wall, Z_SPLIT), (x_wall, tz - (tx - x_wall)), (tx, tz), (tx, Z_SPLIT)]
        web = bd.extrude(bd.Face(bd.Wire.make_polygon([bd.Vector(x, y0, z) for x, z in pts], close=True)),
                         amount=y1 - y0, dir=(0, 1, 0))
    else:
        web = bd.Box(a - x_wall, y1 - y0, HINGE_R, align=(bd.Align.MIN, bd.Align.MIN, bd.Align.MAX))
        web = web.moved(bd.Location((x_wall, y0, Z_SPLIT)))
    k = cyl + web
    for end in round_ends:
        face = k.faces().filter_by(bd.Axis.Y).sort_by(bd.Axis.Y)[0 if end == "lo" else -1]
        # Round the arc and the underside, not the short ledge at the parting plane or the buried edge.
        edges = [e for e in face.edges() if e.center().X > x_wall + 2.0 and
                 (e.geom_type == bd.GeomType.CIRCLE or e.center().Z < Z_SPLIT - 0.1)]
        k = bd.fillet(edges, LUMP_ROUND)
    return occ_mesh(k)


def tray_left(t: Tray = MJF, parity=0):
    """Tray for the left half (keys up), walls to the parting plane. parity 1 makes the right tray's
    knuckle set (before mirroring)."""
    body = [tray_body(t)]
    beads, cuts = [], []

    # Click tabs: bead over the rim's 1 mm chamfer holds the half in its tray.
    tip_v, tip_z = -0.5, 9.95
    bead = [(t.fit + 0.01, tip_z - (t.fit - tip_v)), (tip_v, tip_z), (tip_v, tip_z + 0.2),
            (t.fit + 0.01, tip_z + 0.2 + (t.fit - tip_v))]
    for p in TRAY_TABS:
        c, b = snap_tab(p, z_root=1.0, z_free=Z_SPLIT, bead=bead, slot=t.slot, fit=t.fit, wall=t.wall)
        cuts += c
        beads.append(b)

    # Magnet bosses on the pinky edge, pockets open at the parting plane.
    for y in MAGNETS_Y:
        body.append(magnet_boss(y, t))
        pocket = trimesh.creation.cylinder(radius=t.magnet_hole / 2, height=MAGNET_H + 0.3, sections=64)
        pocket.apply_translation([t.magnet_x, y, Z_SPLIT - (MAGNET_H + 0.3) / 2 + 0.01])
        cuts.append(pocket)

    # Hinge knuckles along the inner edge.
    seg = (HINGE_Y[1] - HINGE_Y[0]) / HINGE_N
    for i in range(HINGE_N):
        y0 = HINGE_Y[0] + seg * i + (KNUCKLE_GAP / 2 if i > 0 else 0)
        y1 = HINGE_Y[0] + seg * (i + 1) - (KNUCKLE_GAP / 2 if i < HINGE_N - 1 else 0)
        mine = (i % 2 == 0) if parity == 0 else (i % 2 == 1)
        if mine:
            ends = (("lo",) if i == 0 else ()) + (("hi",) if i == HINGE_N - 1 else ())
            body.append(knuckle(y0, y1, t, ends))
        else:
            # Clearance for the other tray's knuckle as it swings past.
            cuts.append(_knuckle_cyl(y0 - KNUCKLE_GAP / 2, y1 + KNUCKLE_GAP / 2, HINGE_R + 0.5, x=t.hinge_x))
    cuts.append(_knuckle_cyl(HINGE_Y[0] - 1, HINGE_Y[1] + 1, (t.pin_press if parity == 0 else t.pin_free) / 2,
                             x=t.hinge_x))

    # Thumb lips at the front edge to pull the book open (offset left/right per tray).
    body.append(thumb_lip(70.0 if parity == 0 else 84.0, t))  # clear of the front click tab (x 43-61)

    shell = difference(union(body), [prism(off(t.fit), 0.0, Z_SPLIT + 5.0)])
    return difference(union([shell, *beads]), cuts)


def clamshell(t: Tray = MJF):
    left = tray_left(t, 0)
    right = mirror_z(tray_left(t, 1), Z_SPLIT)
    return left, right


def open_rotation(t: Tray, angle=np.pi):
    """Turns the right tray about the hinge pin; pi lays it open beside the left tray, keys up."""
    return trimesh.transformations.rotation_matrix(angle, [0, 1, 0], point=[t.hinge_x, 0, Z_SPLIT])


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

    trays = {}
    gpair5 = [*gl, *[Part(p.name + " (right)", mirror_z(p.mesh, Z_SPLIT), p.material) for p in gl]]
    for key, t in (("clamshell", MJF), ("clamshell-fdm", FDM)):
        left, right = trays[key] = clamshell(t)
        out[key] = [Part("tray (left)", left, t.material), Part("tray (right)", right, t.material)]
        report(f"5. clamshell ({t.material})", out[key], gpair5)
        print(f"  trays together: {sum(p.grams for p in out[key]):.1f} g, "
              f"closed size {np.round(trimesh.util.concatenate([left, right]).extents, 1).tolist()}")
        swing = {d: interference(left, right.copy().apply_transform(open_rotation(t, np.radians(d))))
                 for d in (0, 30, 60, 90, 120, 150, 180)}
        print("  tray-to-tray overlap while opening: " + ", ".join(f"{d}° {v:.2f}" for d, v in swing.items()) + " mm³")
        assert max(swing.values()) < 0.05, "the trays collide as the hinge turns"
        rim = off(t.fit).exterior  # inner corner where the floor meets the wall, against the cut-back outer edge
        pts = [[*rim.interpolate(d).coords[0], 0.0] for d in np.linspace(0, rim.length, 800, endpoint=False)]
        _, dist, _ = trimesh.proximity.closest_point(tray_body(t), pts)
        print(f"  thinnest point at the bottom edge: {dist.min():.2f} mm")
        assert dist.min() >= t.min_corner, "bottom edge leaves the corner too thin"

    # Keycap gap check (same in all face-to-face designs).
    caps = next(p.mesh for p in gl if p.name == "keycaps")
    print(f"\nkeycap tops {caps.bounds[1][2]:.1f} mm; facing keycap gap ring {2 * (RIM + RING_GAP / 2 - KEY):.1f} mm, "
          f"clamshell {2 * (Z_SPLIT - KEY):.1f} mm; lid underside {KEY + LID_CLEAR:.1f} mm")

    # Export each part the way it is used, resting on z = 0. Only rotations and moves: a mirror here
    # would turn a left part into a right one.
    files = [("1-spacer-ring", r, None), ("4-lid-left", lid, "left"), ("4-lid-right", lid_r, "right")]
    for key, t in (("clamshell", MJF), ("clamshell-fdm", FDM)):
        left, right = trays[key]
        right_open = right.copy()
        right_open.apply_transform(open_rotation(t))  # the right tray as it lies when the book is open, keys up
        files += [(f"5-tray-left{t.suffix}", left, "left"), (f"5-tray-right{t.suffix}", right_open, "right")]
    print()
    for name, m, want in files:
        got = handedness(m)
        ok = want is None or got == want
        print(f"  {name:20s} shaped for the {got} half" + ("" if want is None else ("  ok" if ok else "  WRONG")))
        assert ok, name
        m = placed(m)
        if name.endswith("-fdm"):
            area = unsupported_area(m, FDM)
            print(f"  {'':20s} overhangs past 45° on the bed-down print: {area:.1f} mm²")
            assert area < 5.0, "the FDM tray needs supports"
        export(name, m)
    return out, gl


def unsupported_area(m, t: Tray, limit_deg=46.0):
    """Area facing down more steeply than `limit_deg` from vertical, for a part resting on z = 0. The tops
    of the pin hole are left out: they are short bridges over a 2 mm bore."""
    n, c, a = m.face_normals, m.triangles_center, m.area_faces
    down = (n[:, 2] < -np.sin(np.radians(limit_deg))) & (c[:, 2] > 0.05)
    # The bore runs along y at the hinge axis height; find it from the knuckle tops.
    axis_z = m.bounds[1][2] - HINGE_R
    knuckle_x = c[:, 0][np.argmax(c[:, 2])]
    bore = np.hypot(c[:, 0] - knuckle_x, c[:, 2] - axis_z) < t.pin_free / 2 + 0.3
    return float(a[down & ~bore].sum())


def placed(m):
    """Centre on the origin and rest on z = 0."""
    m = m.copy()
    b = m.bounds
    m.apply_translation([-(b[0][0] + b[1][0]) / 2, -(b[0][1] + b[1][1]) / 2, -b[0][2]])
    return m


def handedness(m):
    """'left' when the thumb-cluster tip (the outline's lowest point) is on the +x side, as on the left half
    seen keys up."""
    v = m.vertices
    centre = (v[:, 0].min() + v[:, 0].max()) / 2
    tip = v[v[:, 1] < v[:, 1].min() + 3]
    return "left" if tip[:, 0].mean() > centre else "right"


if __name__ == "__main__":
    build()
