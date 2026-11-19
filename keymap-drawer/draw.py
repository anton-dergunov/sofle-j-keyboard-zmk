#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["keymap-drawer==0.23.0", "pyyaml>=6"]
# ///
"""Draw one picture per layer of config/eyelash_sofle.keymap.

Writes "Sofle layer 0.svg", "Sofle layer 1.svg", ... to the output folder,
skipping layers where every key is transparent. Files are named by layer index,
so renaming a layer doesn't break pages that embed them.

keymap-drawer parses the keymap and applies the labels from
keymap_drawer.config.yaml; this script draws the SVG itself, so it can leave out
keys that aren't fitted, pull the halves together and style the keycaps. The
pictures follow the viewer's light or dark theme.

Usage:
    keymap-drawer/draw.py                 write into keymap-drawer/
    keymap-drawer/draw.py "<folder>"      write into another folder, e.g. a notes app's images
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, replace
from html import escape
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
KEYMAP = REPO / "config" / "eyelash_sofle.keymap"
LAYOUT = REPO / "config" / "eyelash_sofle.json"
CONFIG = REPO / "keymap_drawer.config.yaml"
ICONS = HERE / "icons"
NAME = "Sofle layer {index}.svg"

# --- Drawing layout: config/eyelash_sofle.json, adjusted to look like the board on the desk ---

HIDDEN = {6, 19, 32, 45, 58, 52}  # 5-way switch (cap removed, unused) and the knob position (no knob)
THUMB_SLIDE = {57: -0.18, 59: 0.18}  # the Space keys sit a little closer to M1 than the file says
THUMB_GAP = 0.3  # key units between the closest keys of the two halves once pulled together

U = 64  # px per key unit
INSET = 3  # px between neighbouring keycaps, per side
RADIUS = 10
PAD = 6

STYLE = """
svg {
  --key-top: #ffffff; --key-bottom: #f0f2f5; --key-border: #c8cdd5; --legend: #1f2328; --sub: #6e7681;
  --trans-top: #f7f8fa; --trans-bottom: #f3f4f6; --trans-border: #e4e7eb;
  --held-top: #fff3c4; --held-bottom: #ffe28a; --held-border: #d9b13f; --held-legend: #6b4f00;
  --desk-top: #eef5ff; --desk-bottom: #d8e9ff; --desk-border: #79a8e6; --desk-legend: #1858a8;
  --danger-top: #fff2f2; --danger-bottom: #fddcdc; --danger-border: #e59a9a; --danger-legend: #b42318;
  --shadow: rgba(16, 24, 40, 0.18);
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Roboto, "Segoe UI", sans-serif;
}
@media (prefers-color-scheme: dark) {
  svg {
    --key-top: #3a3d43; --key-bottom: #2e3035; --key-border: #4b4f57; --legend: #eceef1; --sub: #9aa2ad;
    --trans-top: #26282c; --trans-bottom: #232529; --trans-border: #303338;
    --held-top: #6a5720; --held-bottom: #574716; --held-border: #9a8133; --held-legend: #ffe7a3;
    --desk-top: #22446b; --desk-bottom: #1b3757; --desk-border: #4a86cc; --desk-legend: #b5d6ff;
    --danger-top: #682a2a; --danger-bottom: #552222; --danger-border: #a65151; --danger-legend: #ffc2c2;
    --shadow: rgba(0, 0, 0, 0.55);
  }
}
.key { color: var(--legend); }
.cap { fill: url(#g-key); stroke: var(--key-border); stroke-width: 1; filter: url(#shadow); }
.trans .cap { fill: url(#g-trans); stroke: var(--trans-border); filter: none; }
.held .cap { fill: url(#g-held); stroke: var(--held-border); }
.held { color: var(--held-legend); }
.desk .cap { fill: url(#g-desk); stroke: var(--desk-border); }
.desk { color: var(--desk-legend); }
.danger .cap { fill: url(#g-danger); stroke: var(--danger-border); }
.danger { color: var(--danger-legend); }
.muted { color: var(--sub); }
text { fill: currentColor; text-anchor: middle; dominant-baseline: central; }
.main { font-weight: 500; }
.sub { color: var(--sub); }
.muted .sub, .held .sub, .desk .sub, .danger .sub { color: inherit; opacity: 0.8; }
.caption { font-weight: 500; letter-spacing: 0.01em; }
"""

GRADIENTS = ("key", "trans", "held", "desk", "danger")


@dataclass(frozen=True)
class Key:
    index: int
    x: float  # top-left corner in key units, before rotation
    y: float
    r: float = 0.0  # rotation in degrees (clockwise) around (rx, ry)
    rx: float = 0.0
    ry: float = 0.0

    def corners(self) -> list[tuple[float, float]]:
        cos, sin = math.cos(math.radians(self.r)), math.sin(math.radians(self.r))
        points = [(self.x, self.y), (self.x + 1, self.y), (self.x, self.y + 1), (self.x + 1, self.y + 1)]
        return [(self.rx + (px - self.rx) * cos - (py - self.ry) * sin,
                 self.ry + (px - self.rx) * sin + (py - self.ry) * cos) for px, py in points]

    def moved(self, dx: float) -> Key:
        return replace(self, x=self.x + dx, rx=self.rx + dx)


def load_layout() -> list[Key]:
    data = json.loads(LAYOUT.read_text())
    entries = next(iter(data["layouts"].values()))["layout"]
    keys = [Key(i, e["x"], e["y"], e.get("r", 0.0), e.get("rx", 0.0), e.get("ry", 0.0))
            for i, e in enumerate(entries) if i not in HIDDEN]
    keys = [replace(k, x=k.x + THUMB_SLIDE.get(k.index, 0.0)) for k in keys]
    middle = (min(k.x for k in keys) + max(k.x for k in keys) + 1) / 2
    left = [k for k in keys if k.x + 0.5 < middle]
    right = [k for k in keys if k.x + 0.5 >= middle]
    # slide the right half left until its closest key is THUMB_GAP from the left half (bisection)
    lo, hi = -(max(k.x for k in right) - min(k.x for k in right)), 0.0
    for _ in range(40):
        dx = (lo + hi) / 2
        if gap(left, [k.moved(dx) for k in right]) < THUMB_GAP:
            lo = dx
        else:
            hi = dx
    return sorted(left + [k.moved(hi) for k in right], key=lambda k: k.index)


def gap(left: list[Key], right: list[Key]) -> float:
    """Shortest distance between any key of one half and any key of the other (keys as squares)."""
    def point_to_segment(p, a, b) -> float:
        (px, py), (ax, ay), (bx, by) = p, a, b
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        return math.hypot(px - ax - t * dx, py - ay - t * dy)

    def edges(key: Key):
        tl, tr, bl, br = key.corners()
        return [(tl, tr), (tr, br), (br, bl), (bl, tl)]

    def overlap(a: Key, b: Key) -> bool:  # coarse: a centre inside b's bounding box
        cx = sum(x for x, _ in a.corners()) / 4
        cy = sum(y for _, y in a.corners()) / 4
        xs, ys = [x for x, _ in b.corners()], [y for _, y in b.corners()]
        return min(xs) <= cx <= max(xs) and min(ys) <= cy <= max(ys)

    best = math.inf
    for a in left:
        for b in right:
            if overlap(a, b) or overlap(b, a):
                return 0.0
            best = min(best,
                       min(point_to_segment(p, *e) for p in a.corners() for e in edges(b)),
                       min(point_to_segment(p, *e) for p in b.corners() for e in edges(a)))
    return best


# --- Icons: $$tabler:name$$ from keymap-drawer/icons/, other $$name$$ from the config's glyphs ---

GLYPH = re.compile(r"^\$\$(.+)\$\$$")


class Icons:
    def __init__(self, glyphs: dict[str, str]):
        self.glyphs = glyphs
        self.used: dict[str, str] = {}

    def symbol_id(self, name: str) -> str:
        if name not in self.used:
            self.used[name] = "i-" + re.sub(r"[^a-z0-9-]", "-", name.lower())
        return self.used[name]

    def source(self, name: str) -> str:
        if name.startswith("tabler:"):
            path = ICONS / f"{name.removeprefix('tabler:')}.svg"
            if not path.exists():
                sys.exit(f"Icon {name} is not vendored: add {path.name} from @tabler/icons to {ICONS}")
            return path.read_text()
        if name in self.glyphs:
            return self.glyphs[name]
        sys.exit(f"Unknown icon $${name}$$: not a tabler: icon and not in draw_config.glyphs")

    def defs(self) -> str:
        out = []
        for name, symbol_id in self.used.items():
            svg = self.source(name)
            m = re.search(r"<svg([^>]*)>(.*)</svg>", svg, re.S)
            attrs, body = m.group(1), m.group(2)
            view_box = re.search(r'viewBox="([^"]+)"', attrs).group(1)
            body = re.sub(r'<path stroke="none" d="M0 0h24v24H0z" fill="none"\s*/>', "", body)
            body = re.sub(r"\s+", " ", body).strip()
            out.append(f'<symbol id="{symbol_id}" viewBox="{view_box}"><g fill="none" stroke="currentColor" '
                       f'stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">{body}</g></symbol>')
        return "\n".join(out)


# --- Legends ---

def normalize(key) -> dict:
    """keymap-drawer gives a key as a plain legend or a dict with t/s/h/type."""
    if key is None:
        return {}
    if isinstance(key, str):
        return {"t": key}
    return {k: str(v) for k, v in key.items() if v not in (None, "")}


def main_size(text: str) -> float:
    if "\n" in text:
        return 11.5
    return {1: 22.0, 2: 17.0, 3: 15.0, 4: 13.0, 5: 12.0}.get(len(text), 11.0)


def legend(icons: Icons, value: str, y: float, size: float, cls: str) -> str:
    if m := GLYPH.match(value):
        symbol = icons.symbol_id(m.group(1))
        return (f'<use href="#{symbol}" x="{U / 2 - size / 2:g}" y="{y - size / 2:g}" '
                f'width="{size:g}" height="{size:g}" class="{cls}"/>')
    lines = value.split("\n")
    if len(lines) == 1:
        return f'<text x="{U / 2:g}" y="{y:g}" class="{cls}" font-size="{size:g}">{escape(value)}</text>'
    step = size * 1.15
    spans = "".join(f'<tspan x="{U / 2:g}" dy="{(-step * (len(lines) - 1) / 2) if i == 0 else step:g}">'
                    f"{escape(line)}</tspan>" for i, line in enumerate(lines))
    return f'<text x="{U / 2:g}" y="{y:g}" class="{cls}" font-size="{size:g}">{spans}</text>'


def draw_key(icons: Icons, key: Key, spec: dict) -> str:
    types = spec.get("type", "").split()
    classes = " ".join(["key", *types])
    transform = f"translate({key.x * U:g} {key.y * U:g})"
    if key.r:
        transform = f"rotate({key.r:g} {key.rx * U:g} {key.ry * U:g}) " + transform
    side = U - 2 * INSET
    parts = [f'<rect class="cap" x="{INSET}" y="{INSET}" width="{side}" height="{side}" rx="{RADIUS}"/>']

    if "trans" not in types:
        t, s, h = spec.get("t", ""), spec.get("s", ""), spec.get("h", "")
        t_is_icon = bool(GLYPH.match(t))
        t_size = (22.0 if h else 25.0) if t_is_icon else main_size(t)
        if s and h:
            s_y, t_y, h_y = 16.5, 33.0, 50.0
        elif s:
            s_y, t_y, h_y = 20.0, 39.0, 0.0
        elif h:
            s_y, t_y, h_y = 0.0, 27.0, 49.0
        else:
            s_y, t_y, h_y = 0.0, 32.0, 0.0
        if s:
            s_size = 14.0
            parts.append(legend(icons, s, s_y, s_size, "sub"))
        if t:
            parts.append(legend(icons, t, t_y, t_size, "main"))
        if h:
            parts.append(legend(icons, h, h_y, 10.5, "sub caption"))
    return f'<g class="{classes}" transform="{transform}">{"".join(parts)}</g>'


def resolve(layers: list[list], layer: int, index: int) -> dict:
    """A held layer key is transparent here: show the label of the key that activates it."""
    spec = normalize(layers[layer][index])
    if "held" in spec.get("type", "").split() and not spec.get("t"):
        for lower in range(layer - 1, -1, -1):
            below = normalize(layers[lower][index])
            if below.get("t") and "trans" not in below.get("type", "").split():
                return {**{k: v for k, v in below.items() if k != "type"}, "type": spec["type"]}
    return spec


def draw_layer(layers: list[list], layer: int, name: str, layout: list[Key], glyphs: dict[str, str]) -> str:
    icons = Icons(glyphs)
    body = "\n".join(draw_key(icons, key, resolve(layers, layer, key.index)) for key in layout)
    xs = [x for key in layout for x, _ in key.corners()]
    ys = [y for key in layout for _, y in key.corners()]
    x0, y0 = min(xs) * U - PAD, min(ys) * U - PAD
    width, height = (max(xs) - min(xs)) * U + 2 * PAD, (max(ys) - min(ys)) * U + 2 * PAD + 2
    gradients = "".join(
        f'<linearGradient id="g-{g}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" style="stop-color: var(--{g}-top)"/><stop offset="1" style="stop-color: var(--{g}-bottom)"/>'
        f"</linearGradient>" for g in GRADIENTS)
    shadow = ('<filter id="shadow" x="-10%" y="-10%" width="120%" height="130%">'
              '<feDropShadow dx="0" dy="1.2" stdDeviation="1.1" style="flood-color: var(--shadow)"/></filter>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0:g} {y0:g} {width:g} {height:g}" '
            f'width="{width:g}" height="{height:g}">\n'
            f"<title>Sofle keymap: {escape(name)}</title>\n"
            f"<style>{STYLE}</style>\n<defs>{gradients}{shadow}\n{icons.defs()}</defs>\n{body}\n</svg>\n")


def keymap(*args: str) -> str:
    """Runs the keymap-drawer CLI and returns its stdout."""
    cmd = [sys.executable, "-m", "keymap_drawer", "-c", str(CONFIG), *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode:
        sys.exit(f"keymap-drawer {args[0]} failed:\n{result.stderr}")
    return result.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out_dir", nargs="?", type=Path, default=HERE, help="folder for the SVG files")
    args = parser.parse_args()
    out_dir: Path = args.out_dir.expanduser()
    if not out_dir.is_dir():
        sys.exit(f"No such folder: {out_dir}")

    parsed = yaml.safe_load(keymap("parse", "-z", str(KEYMAP)))
    glyphs = (yaml.safe_load(CONFIG.read_text()).get("draw_config") or {}).get("glyphs") or {}
    names = list(parsed["layers"])
    layers = [parsed["layers"][n] for n in names]
    layout = load_layout()
    for index, name in enumerate(names):
        if all(normalize(k).get("type") == "trans" for k in layers[index]):
            print(f"skip  layer {index} ({name}): all keys transparent")
            continue
        target = out_dir / NAME.format(index=index)
        target.write_text(draw_layer(layers, index, name, layout, glyphs))
        print(f"wrote {target}  ({name})")


if __name__ == "__main__":
    main()
