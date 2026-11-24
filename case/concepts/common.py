"""Shared geometry for the carrying-case concepts.

Frame: the left half lies keys up with its outer outline's bounding box starting at (0, 0) and its
bottom face at z = 0. The right half, closed onto it like a book (hinge along the inner, display-column
edge), is the left half mirrored in the plane z = Z_MID, so every concept is symmetric about Z_MID.
All lengths in mm. Concept models use the newer (Aug 2025) case.
"""

import math
import sys
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import numpy as np
import shapely
import trimesh

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sofle_geom import NEW_STEP, PANDA, left_wall  # noqa: E402

# Measured on the keyboard (no rubber feet) and read from the case model.
RIM = 10.6  # case rim above the table
COLUMN = 14.0  # controller / nice!view column top
KEY = 18.0  # tallest keycap top
KEY_CLEAR = 1.0  # keycap top to the nearest case surface
GAP = 2 * (KEY - RIM + KEY_CLEAR)  # rim-to-rim distance when face to face (16.8)
Z_MID = RIM + GAP / 2  # symmetry plane of the closed stack (19.0)
STACK = 2 * RIM + GAP  # closed stack, bottom to bottom (38.0)

FIT = 0.35  # sliding fit around the case's outer wall (MJF/SLS)
WALL = 1.6  # PA12 wall

DENSITY = {"PA12": 1.01, "TPU": 1.20, "PETG": 1.27}  # g/cm^3 of solid material (MJF; FDM PETG)


@dataclass
class Part:
    name: str
    mesh: trimesh.Trimesh
    material: str  # PA12, TPU, silicone, magnet, ghost-*
    count: int = 1
    tags: set = field(default_factory=set)

    @property
    def grams(self) -> float:
        d = DENSITY.get(self.material)
        return 0.0 if d is None else self.mesh.volume / 1000 * d * self.count


# ---------------------------------------------------------------- 2D helpers


def _poly_from_wall(wall: shapely.Polygon) -> tuple[shapely.Polygon, shapely.Polygon, tuple[float, float]]:
    outer = shapely.Polygon(wall.exterior)
    cavity = shapely.Polygon(max(wall.interiors, key=lambda r: shapely.Polygon(r).area))
    x0, y0, *_ = outer.bounds
    move = lambda p: shapely.affinity.translate(p, -x0, -y0)  # noqa: E731
    return move(outer).simplify(0.02), move(cavity).simplify(0.02), (x0, y0)


@cache
def outline_data():
    return _poly_from_wall(left_wall("new"))


def O() -> shapely.Polygon:
    """Outer outline of the case wall."""
    return outline_data()[0]


def off(d: float) -> shapely.Polygon:
    """Outline offset outward by d (inward when negative), round joins."""
    return O().buffer(d, join_style="round", quad_segs=12)


def band(d_out: float, d_in: float) -> shapely.Polygon:
    """Ring between two offsets of the outline."""
    return off(d_out).difference(off(d_in))


def prism(poly, z0: float, z1: float) -> trimesh.Trimesh:
    """Extrude a shapely (multi)polygon between two heights."""
    polys = list(getattr(poly, "geoms", [poly]))
    meshes = []
    for p in polys:
        if p.is_empty or p.area < 1e-3:
            continue
        m = trimesh.creation.extrude_polygon(p, z1 - z0)
        m.apply_translation([0, 0, z0])
        meshes.append(m)
    return trimesh.util.concatenate(meshes)


def union(meshes) -> trimesh.Trimesh:
    meshes = [m for m in meshes if m is not None and len(m.faces)]
    if len(meshes) == 1:
        return meshes[0]
    return trimesh.boolean.union(meshes, engine="manifold")


def difference(a, b) -> trimesh.Trimesh:
    return trimesh.boolean.difference([a, b] if not isinstance(b, list) else [a, *b], engine="manifold")


def mirror_z(m: trimesh.Trimesh, z: float = Z_MID) -> trimesh.Trimesh:
    """Mirror in the plane at height z (trimesh fixes the winding)."""
    T = np.eye(4)
    T[2, 2] = -1
    T[2, 3] = 2 * z
    out = m.copy()
    out.apply_transform(T)
    return out


def mirror_part(p: Part, suffix=" (right)") -> Part:
    return Part(p.name + suffix, mirror_z(p.mesh), p.material, p.count, set(p.tags))


# ---------------------------------------------------------------- the stand-in keyboard half


PLATE_TOP = 7.6  # so that the plate's display cover ends flush with the column at 14 mm
SWITCH_TOP = PLATE_TOP + 3.0
CAP_BOTTOM = KEY - 4.0


@cache
def _plate_layout():
    """Switch-hole centres/angles and the display-cover outline, in plate-bbox coordinates."""
    m = trimesh.load(PANDA / "Switch Plate Left 1.stl")

    def sec(z):
        s = m.section(plane_origin=[0, 0, m.bounds[0][2] + z], plane_normal=[0, 0, 1])
        p2, _ = s.to_2D(to_2D=np.eye(4))
        return max(p2.polygons_full, key=lambda g: g.area)

    plate = sec(1.0)
    x0, y0, x1, y1 = plate.bounds
    keys = []
    for ring in plate.interiors:
        h = shapely.Polygon(ring)
        if 150 < h.area < 230:
            c = list(h.minimum_rotated_rectangle.exterior.coords)
            ang = math.degrees(math.atan2(c[1][1] - c[0][1], c[1][0] - c[0][0])) % 90
            if ang > 45:
                ang -= 90
            keys.append((h.centroid.x - x0, h.centroid.y - y0, ang))
    cover = shapely.affinity.translate(sec(5.0), -x0, -y0)
    return keys, cover, (x1 - x0, y1 - y0)


def _rect(cx, cy, w, h, ang, r=1.0):
    b = shapely.box(-w / 2 + r, -h / 2 + r, w / 2 - r, h / 2 - r).buffer(r, quad_segs=6)
    b = shapely.affinity.rotate(b, ang, origin=(0, 0))
    return shapely.affinity.translate(b, cx, cy)


@cache
def ghost_left() -> list[Part]:
    """The left half: real case model plus simplified plate, switches and keycaps."""
    import build123d as bd

    solid = bd.import_step(str(NEW_STEP)).solids()[0]
    v, f = solid.tessellate(0.05)
    case = trimesh.Trimesh([(p.X, p.Y, p.Z) for p in v], f)
    x0, y0 = outline_data()[2]
    case.apply_translation([-x0, -y0, -case.bounds[0][2]])

    keys, cover, (pw, ph) = _plate_layout()
    cav = outline_data()[1]
    cb = cav.bounds
    px = (cb[0] + cb[2]) / 2 - pw / 2
    py = (cb[1] + cb[3]) / 2 - ph / 2
    plate = prism(cav.buffer(-0.4), PLATE_TOP - 2.0, PLATE_TOP)
    cover_m = prism(shapely.affinity.translate(cover, px, py), PLATE_TOP, COLUMN - 0.05)
    switches = trimesh.util.concatenate(
        [prism(_rect(px + x, py + y, 15.0, 15.0, a, 0.5), PLATE_TOP, SWITCH_TOP) for x, y, a in keys]
    )
    caps = trimesh.util.concatenate(
        [prism(_rect(px + x, py + y, 17.5, 16.5, a, 1.2), CAP_BOTTOM, KEY) for x, y, a in keys]
    )
    return [
        Part("case", case, "ghost-case"),
        Part("plate", plate, "ghost-plate"),
        Part("display cover", cover_m, "ghost-dark"),
        Part("switches", switches, "ghost-dark"),
        Part("keycaps", caps, "ghost-keys"),
    ]


def ghost_pair() -> list[Part]:
    left = ghost_left()
    return [*left, *[mirror_part(p) for p in left]]


def keycap_envelope() -> trimesh.Trimesh:
    return next(p.mesh for p in ghost_left() if p.name == "keycaps")


# ---------------------------------------------------------------- shared pieces


def silicone_band(x_centre: float, width: float = 12.0, thick: float = 1.5, z0: float = 0.0, z1: float = STACK,
                  pad: float = 0.0) -> trimesh.Trimesh:
    """A flat band looped around the stack in the y–z plane at x_centre."""
    strip = shapely.box(x_centre - width / 2, -100, x_centre + width / 2, 300)
    sect = off(pad).intersection(strip)
    ylo, yhi = sect.bounds[1], sect.bounds[3]
    outer = trimesh.creation.box(bounds=[[x_centre - width / 2, ylo - thick, z0 - thick],
                                         [x_centre + width / 2, yhi + thick, z1 + thick]])
    inner = trimesh.creation.box(bounds=[[x_centre - width / 2 - 1, ylo, z0], [x_centre + width / 2 + 1, yhi, z1]])
    return difference(outer, inner)


def convex_corners(min_turn_deg: float = 25.0) -> list[tuple[float, float]]:
    """Outline vertices where the outline turns sharply (the case corners)."""
    pts = np.array(O().exterior.coords)[:-1]
    # Collapse the fillet arcs: simplify hard first.
    simp = np.array(O().simplify(2.0).exterior.coords)[:-1]
    out = []
    n = len(simp)
    for i in range(n):
        a, b, c = simp[i - 1], simp[i], simp[(i + 1) % n]
        v1, v2 = b - a, c - b
        turn = math.degrees(math.atan2(v1[0] * v2[1] - v1[1] * v2[0], v1 @ v2))
        if abs(turn) >= min_turn_deg:
            out.append(tuple(b))
    del pts
    return out
