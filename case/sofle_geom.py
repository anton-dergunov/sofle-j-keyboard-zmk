"""Outline and height data for the PandaKB Sofle-J Choc bottom case.

Two revisions exist and differ only in wall thickness: the newer one (2025-08, the STEP file) is the
older outline (2025-06, the STLs) grown outward by 1.4 mm. The cavity inside is the same.
"""

from functools import cache
from pathlib import Path

import numpy as np
import shapely
import trimesh

PANDA = Path.home() / "projects/external/sofle-j-keyboard-case/Sofle-J Choc ZMK Wireless Keyboard"
OLD_LEFT_STL = PANDA / "Bottom Case Left.stl"
NEW_STEP = PANDA / "Bottom Case.stp"

# Heights above the case's bottom face, mm.
HEIGHTS = {
    "old": {"rim": 9.4, "column": 13.4},
    "new": {"rim": 10.6, "column": 14.0},
}


def _section(mesh: trimesh.Trimesh, z_above_bottom: float) -> shapely.Polygon:
    """Largest closed cross-section of a mesh at a height above its lowest point."""
    s = mesh.section(plane_origin=[0, 0, mesh.bounds[0][2] + z_above_bottom], plane_normal=[0, 0, 1])
    p2, _ = s.to_2D(to_2D=np.eye(4))
    return max(p2.polygons_full, key=lambda g: g.area)


def _normalise(p: shapely.Polygon) -> shapely.Polygon:
    """Move so the bounding box starts at the origin."""
    x0, y0, *_ = p.bounds
    return shapely.affinity.translate(p, -x0, -y0)


@cache
def left_wall(rev: str = "old") -> shapely.Polygon:
    """Wall ring of the left half seen from above (keys up), just below the rim, origin at bbox corner."""
    if rev == "old":
        mesh = trimesh.load(OLD_LEFT_STL)
    else:
        import build123d as bd

        solid = bd.import_step(str(NEW_STEP)).solids()[0]  # solid 0 is the left half
        v, f = solid.tessellate(0.02)
        mesh = trimesh.Trimesh([(p.X, p.Y, p.Z) for p in v], f)
    # 9 mm is above the port openings and below both rims.
    return _section(mesh, 9.0)


def left_outline(rev: str = "old") -> shapely.Polygon:
    """Outer outline of the left half, filled, origin at its bounding-box corner."""
    return _normalise(shapely.Polygon(left_wall(rev).exterior))


def left_outlines_aligned() -> tuple[shapely.Polygon, shapely.Polygon]:
    """(old, new) outer outlines in one frame: new is old grown by 1.4 mm, so they share a centre."""
    old = left_outline("old")
    new = left_outline("new")
    dx = old.centroid.x - new.centroid.x
    dy = old.centroid.y - new.centroid.y
    return old, shapely.affinity.translate(new, dx, dy)
