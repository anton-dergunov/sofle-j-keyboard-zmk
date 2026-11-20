"""The five carrying-case concepts as rough, parametric models.

Each function returns the case parts in the closed position (around ghost_pair()), plus optional
extra poses for the renders. Rough concept geometry: fit, hinge and magnet details get designed
properly only for the shortlisted ones.
"""

import shapely
import trimesh

from common import (
    FIT, GAP, KEY, KEY_CLEAR, RIM, STACK, WALL, Z_MID, O, Part, band, difference, ghost_left, mirror_part,
    mirror_z, off, prism, silicone_band, union,
)

SKIRT = 4.0  # how far a skirt reaches down over the case wall
RIM_IN = -2.0  # inner edge of a part bearing on the 3.2 mm wide rim

# Clip / guard positions on the outline (left half frame), named for the renders.
CORNERS = {
    "top-outer": (1.0, 113.0),
    "bottom-outer": (1.2, 30.5),
    "top-inner": (139.8, 113.3),
    "thumb tip": (140.0, 10.0),
    "bottom flat": (52.0, 15.0),
    "top flat": (69.0, 121.1),
}


def _zone(names, r):
    return shapely.union_all([shapely.Point(CORNERS[n]).buffer(r) for n in names])


# ---------------------------------------------------------------- 1. rigid spacer ring + straps


def ring_parts(fit=FIT, wall=WALL, skirt=SKIRT):
    outer = fit + wall
    body = prism(band(outer, RIM_IN), RIM, RIM + GAP)
    lower = prism(band(outer, fit), RIM - skirt, RIM)
    upper = prism(band(outer, fit), RIM + GAP, RIM + GAP + skirt)
    return union([body, lower, upper])


def concept_ring():
    ring = ring_parts()
    # Two shallow strap grooves across the front and back walls.
    straps = [silicone_band(x, pad=FIT + WALL) for x in (32.0, 104.0)]
    return {
        "parts": [
            Part("spacer ring", ring, "PA12"),
            *[Part(f"silicone strap {i + 1}", s, "silicone") for i, s in enumerate(straps)],
        ],
    }


# ---------------------------------------------------------------- 2. TPU bumper


def concept_bumper():
    fit = -0.25  # slight stretch onto the case wall
    wall = 2.2
    outer = fit + wall
    body = prism(band(outer, RIM_IN), RIM, RIM + GAP)
    side = band(outer, fit)
    sides = [prism(side, 0.0, RIM), prism(side, RIM + GAP, STACK)]
    # Corner guards: thicker, wrapping 2 mm under each case bottom.
    corners = _zone(["top-outer", "bottom-outer", "top-inner", "thumb tip"], 13.0)
    guard = off(outer + 1.6).difference(off(fit)).intersection(corners)
    lip = off(outer).difference(off(-2.5)).intersection(corners)
    guards = [prism(guard, -1.2, STACK + 1.2), prism(lip, -1.2, 0.0), prism(lip, STACK, STACK + 1.2)]
    # Weight-saving windows along the long straight edges of the spacer band.
    windows = []
    for (x0, x1, y0, y1) in ((-5, 5, 42, 100), (135, 150, 38, 105), (20, 110, 112, 130)):
        windows.append(trimesh.creation.box(bounds=[[x0, y0, RIM + 3.5], [x1, y1, RIM + GAP - 3.5]]))
    bumper = difference(union([body, *sides, *guards]), windows)
    return {"parts": [Part("TPU bumper", bumper, "TPU")]}


# ---------------------------------------------------------------- 3. corner clips + band


def concept_clips():
    ring = ring_parts(skirt=5.0)
    names = ["top-outer", "bottom-outer", "top-inner", "thumb tip", "bottom flat"]
    parts = []
    for n in names:
        zone = prism(shapely.Point(CORNERS[n]).buffer(11.0), -10, STACK + 10)
        clip = trimesh.boolean.intersection([ring, zone], engine="manifold")
        parts.append(Part(f"clip ({n})", clip, "PA12"))
    parts.append(Part("silicone band", silicone_band(70.0, width=15.0, pad=FIT + WALL), "silicone"))
    return {"parts": parts}


# ---------------------------------------------------------------- 4. snap-on lids, one per half


def lid_left():
    top0 = KEY + KEY_CLEAR
    top1 = top0 + 1.4
    outer = FIT + WALL
    walls = prism(band(outer, FIT), RIM - SKIRT, top0)
    ledge = prism(band(FIT + 0.05, RIM_IN), RIM, RIM + 1.2)  # bears on the rim, not the keys
    top = prism(off(outer), top0, top1)
    # Stiffening ribs under the top, between key rows, kept above the keycaps.
    lid = union([walls, ledge, top])
    # Finger notch in the front edge to lift the lid off.
    notch = trimesh.creation.cylinder(radius=7.0, height=30, sections=48)
    notch.apply_transform(trimesh.transformations.rotation_matrix(1.5708, [1, 0, 0]))
    notch.apply_translation([70.0, 15.0, RIM - SKIRT])
    return difference(lid, notch)


def concept_lids():
    lid = lid_left()
    left = Part("lid (left)", lid, "PA12")
    # Right half shown face-down on the left in the closed stack is not how lids are used, so the
    # main pose is: two capped halves side by side, as in the felt sleeve.
    gx = 146.3 + 2 * (FIT + WALL) + 6.0
    ghost = ghost_left()
    side_by_side = []
    for p in ghost:
        side_by_side.append(Part(p.name, p.mesh, p.material, tags={"ghost"}))
        m = p.mesh.copy()
        m.apply_transform(_mirror_x_about(146.27 / 2))
        m.apply_translation([gx, 0, 0])
        side_by_side.append(Part(p.name + " (right)", m, p.material, tags={"ghost"}))
    lid_r = lid.copy()
    lid_r.apply_transform(_mirror_x_about(146.27 / 2))
    lid_r.apply_translation([gx, 0, 0])
    side_by_side += [left, Part("lid (right)", lid_r, "PA12")]
    # Back-to-back stack: right half flipped under the left, lids outward.
    stacked = []
    for p in [*ghost, left]:
        m = p.mesh.copy()
        stacked.append(Part(p.name, m, p.material, tags={"ghost"} if p.material.startswith("ghost") else set()))
        m2 = mirror_z(p.mesh, 0.0)
        stacked.append(Part(p.name + " (right)", m2, p.material,
                            tags={"ghost"} if p.material.startswith("ghost") else set()))
    return {
        "parts": [left, Part("lid (right)", mirror_z(lid), "PA12")],
        "count_override": {"lid (left)": 1, "lid (right)": 1},
        "poses": {"side by side": side_by_side, "back to back": stacked},
        "no_default_pose": True,
    }


def _mirror_x_about(x):
    import numpy as np

    T = np.eye(4)
    T[0, 0] = -1
    T[0, 3] = 2 * x
    return T


# ---------------------------------------------------------------- 5. hinged clamshell ("book")


HINGE_R = 3.2
MAGNET_D, MAGNET_H = 8.0, 2.0


def tray_left(parity: int = 0):
    outer = FIT + WALL
    floor = prism(off(outer), -1.4, 0.0)
    walls = prism(band(outer, FIT), 0.0, Z_MID)
    # Small retention bumps at the rim on the two straight sides keep the half in its tray when open.
    bumps = []
    for x, y in ((0.0 - FIT, 70.0), (138.3 + FIT, 70.0)):
        b = trimesh.creation.box(extents=[1.0, 10.0, 1.2])
        b.apply_translation([x + (0.25 if x < 1 else -0.25), y, RIM + 0.8])
        bumps.append(b)
    # Magnet bosses on the outer (pinky) straight edge.
    bosses, pockets = [], []
    for y in (48.0, 92.0):
        boss = trimesh.creation.cylinder(radius=6.0, height=9.0, sections=48)
        boss.apply_translation([-outer - 2.5, y, Z_MID - 4.5])
        bosses.append(boss)
        pocket = trimesh.creation.cylinder(radius=MAGNET_D / 2 + 0.15, height=MAGNET_H + 0.2, sections=48)
        pocket.apply_translation([-outer - 2.5, y, Z_MID - (MAGNET_H + 0.2) / 2 + 0.01])
        pockets.append(pocket)
    # Hinge knuckles along the inner straight edge (x = 138.3), axis along y at z = Z_MID.
    x_axis = 138.3 + outer + HINGE_R
    knuckles = []
    y0, y1, n = 30.0, 108.0, 7
    seg = (y1 - y0) / n
    for i in range(parity, n, 2):  # left tray owns the even knuckles, right tray the odd ones
        k = trimesh.creation.cylinder(radius=HINGE_R, height=seg - 0.5, sections=48)
        k.apply_transform(trimesh.transformations.rotation_matrix(1.5708, [1, 0, 0]))
        k.apply_translation([x_axis, y0 + seg * (i + 0.5), Z_MID])
        web = trimesh.creation.box(bounds=[[138.3 + FIT, y0 + seg * i + 0.25, Z_MID - HINGE_R],
                                           [x_axis, y0 + seg * (i + 1) - 0.25, Z_MID]])
        knuckles += [k, web]
    tray = union([floor, walls, *bumps, *bosses, *knuckles])
    return difference(tray, pockets)


def concept_clamshell():
    left = tray_left(0)
    right = mirror_z(tray_left(1))
    parts = [Part("tray (left)", left, "PA12"), Part("tray (right)", right, "PA12")]
    magnets = []
    for y in (48.0, 92.0):
        for z in (Z_MID - MAGNET_H / 2 - 0.1, Z_MID + MAGNET_H / 2 + 0.1):
            m = trimesh.creation.cylinder(radius=MAGNET_D / 2, height=MAGNET_H, sections=32)
            m.apply_translation([-(FIT + WALL) - 2.5, y, z])
            magnets.append(m)
    parts.append(Part("magnets 8×2 mm", trimesh.util.concatenate(magnets), "magnet"))
    # Open pose: right tray swung 180° about the hinge axis, so both halves lie keys up side by side.
    x_axis = 138.3 + FIT + WALL + HINGE_R
    import numpy as np

    rot = trimesh.transformations.rotation_matrix(np.pi, [0, 1, 0], point=[x_axis, 0, Z_MID])
    open_pose = []
    for p in [*ghost_left()]:
        open_pose.append(Part(p.name, p.mesh, p.material, tags={"ghost"}))
        m = mirror_z(p.mesh)
        m.apply_transform(rot)
        open_pose.append(Part(p.name + " (right)", m, p.material, tags={"ghost"}))
    open_pose.append(parts[0])
    r = right.copy()
    r.apply_transform(rot)
    open_pose.append(Part("tray (right)", r, "PA12"))
    return {"parts": parts, "poses": {"open": open_pose}}


CONCEPTS = {
    "1-ring": ("Spacer ring + straps", concept_ring),
    "2-bumper": ("TPU bumper", concept_bumper),
    "3-clips": ("Corner clips + band", concept_clips),
    "4-lids": ("Snap-on lids", concept_lids),
    "5-clamshell": ("Hinged clamshell", concept_clamshell),
}

__all__ = ["CONCEPTS", "mirror_part", "O"]
