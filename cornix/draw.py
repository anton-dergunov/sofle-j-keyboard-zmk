#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6"]
# ///
"""Draw one picture per layer of a Cornix layout file (cornix/layout.yaml by default).

Writes "Cornix layer 0.svg", "Cornix layer 1.svg", ... in the style of the Sofle pictures:
the keycaps, colours and icons come from keymap-drawer/draw.py, the legends from
keymap_drawer.config.yaml. The knobs are left out, as the Sofle pictures leave out its knob.

Usage:
    cornix/draw.py                                   write into cornix/
    cornix/draw.py "<folder>"                        write into another folder, e.g. a notes app's images
    cornix/draw.py --layout cornix/options/option-b.yaml --name "Cornix option B layer {index}.svg" cornix/options
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
CONFIG = REPO / "keymap_drawer.config.yaml"

spec = importlib.util.spec_from_file_location("sofle_draw", REPO / "keymap-drawer" / "draw.py")
draw = importlib.util.module_from_spec(spec)
sys.modules["sofle_draw"] = draw
spec.loader.exec_module(draw)

# --- Geometry, in key units, measured from the Cornix picture in Vial (1 unit = 19.05 mm key pitch) ---
# Slots: side L/R + row (q, a, z letter rows; b keys under the outer columns; t thumbs) + column.
# Columns count from the outer edge (0) to the index finger (5); thumbs t1 (outer, flat) to t3 (inner, most turned).

COLUMN_DROP = [0.5, 0.5, 0.25, 0.0, 0.25, 0.5]  # column stagger: the middle-finger column is highest
THUMBS = {"t1": (3.99, 4.09, 0), "t2": (5.12, 4.20, 12), "t3": (6.17, 4.55, 26)}  # centre x, centre y, turn (degrees)
MIRROR = 14.45  # right-half centre x = MIRROR - left-half centre x

BOTTOM = {"L": ["b0", "b1", "b2", "t1", "t2", "t3"], "R": ["t3", "t2", "t1", "b2", "b1", "b0"]}


def left_centres() -> dict[str, tuple[float, float, float]]:
    keys = {}
    for r, row in enumerate("qaz"):
        for c in range(6):
            keys[f"{row}{c}"] = (c + 0.47, COLUMN_DROP[c] + r + 0.5, 0)
    for c in range(3):
        keys[f"b{c}"] = (c + 0.47, COLUMN_DROP[c] + 3.5, 0)
    keys.update(THUMBS)
    return keys


def slots() -> list[str]:
    """Every key, in a fixed order: the index of a slot here is its index in a layer's list."""
    names = list(left_centres())
    return [f"L{n}" for n in names] + [f"R{n}" for n in names]


def layout() -> list[draw.Key]:
    left = left_centres()
    keys = []
    for i, slot in enumerate(slots()):
        cx, cy, r = left[slot[1:]]
        if slot[0] == "R":
            cx, r = MIRROR - cx, -r
        keys.append(draw.Key(i, cx - 0.5, cy - 0.5, r, cx, cy))
    return keys


def row_slots(row: int) -> list[str]:
    """Slots of one row of the layout file, as listed: left to right across both halves."""
    if row < 3:
        name = "qaz"[row]
        return [f"L{name}{c}" for c in range(6)] + [f"R{name}{c}" for c in reversed(range(6))]
    return [f"L{s}" for s in BOTTOM["L"]] + [f"R{s}" for s in BOTTOM["R"]]


# --- Legends: QMK/Vial keycodes to the names keymap_drawer.config.yaml labels ---

QMK_TO_ZMK = {
    "KC_BSPC": "BSPC", "KC_ENT": "ENTER", "KC_TAB": "TAB", "KC_ESC": "ESC", "KC_SPC": "SPACE", "KC_CAPS": "CAPS",
    "KC_LSFT": "LSHFT", "KC_RSFT": "RSHFT", "KC_LCTL": "LCTRL", "KC_RCTL": "RCTRL",
    "KC_LALT": "LALT", "KC_RALT": "RALT", "KC_LGUI": "LGUI", "KC_RGUI": "RGUI",
    "KC_GRV": "GRAVE", "KC_MINS": "MINUS", "KC_EQL": "EQUAL", "KC_LBRC": "LBKT", "KC_RBRC": "RBKT", "KC_BSLS": "BSLH",
    "KC_SCLN": "SEMI", "KC_QUOT": "APOS", "KC_COMM": "COMMA", "KC_DOT": "DOT", "KC_SLSH": "FSLH",
    "KC_PGUP": "PG_UP", "KC_PGDN": "PG_DN", "KC_HOME": "HOME", "KC_END": "END", "KC_DEL": "DEL",
    "KC_UP": "UP", "KC_DOWN": "DOWN", "KC_LEFT": "LEFT", "KC_RGHT": "RIGHT",
    "KC_BRID": "C_BRI_DN", "KC_BRIU": "C_BRI_UP", "KC_MCTL": "C_AC_DESKTOP_SHOW_ALL_WINDOWS",
    "KC_LPAD": "C_AC_DESKTOP_SHOW_ALL_APPLICATIONS", "KC_WSCH": "C_AC_SEARCH",
    "KC_MPRV": "C_PREV", "KC_MPLY": "C_PP", "KC_MNXT": "C_NEXT", "KC_MUTE": "C_MUTE", "KC_VOLD": "C_VOL_DN", "KC_VOLU": "C_VOL_UP",
}
# Placeholders for keys whose RMK Vial keycodes are still to be looked up, drawn like the Sofle's ZMK behaviours
PLACEHOLDER_TO_ZMK = {
    **{f"BT{i}": f"&bt BT_SEL {i - 1}" for i in range(1, 6)},
    "BT_CLEAR": "&bt BT_CLR", "BT_CLEAR_ALL": "&bt BT_CLR_ALL", "OUT_USB": "&out OUT_USB", "OUT_BT": "&out OUT_BLE",
    "SOFT_OFF": "&soft_off", "REBOOT": "&sys_reset", "BOOTLOADER": "&bootloader",
    "DESK_PERSONAL": "&to_personal", "DESK_WORK": "&to_work",
}
LAYER_KEY = {1: "M1", 2: "M2", 3: "Num"}


def legend_for(code: str, legends: dict, raw: dict) -> dict:
    if code == "_":
        return {"t": "", "type": "trans"}
    if m := re.fullmatch(r"MO\((\d)\)", code):
        return {"t": LAYER_KEY[int(m.group(1))]}
    if code in PLACEHOLDER_TO_ZMK:
        return dict(raw[PLACEHOLDER_TO_ZMK[code]])
    if m := re.fullmatch(r"KC_([A-Z])", code):
        return {"t": m.group(1)}
    if m := re.fullmatch(r"KC_(\d)", code):
        return draw.normalize(legends[f"N{m.group(1)}"])
    if m := re.fullmatch(r"KC_(F\d+)", code):
        return {"t": m.group(1)}
    if code in QMK_TO_ZMK:
        return draw.normalize(legends[QMK_TO_ZMK[code]])
    sys.exit(f"No legend for keycode {code}: add it to QMK_TO_ZMK in {Path(__file__).name}")


def read_layers(path: Path, legends: dict, raw: dict) -> tuple[list[str], list[list[dict]]]:
    data = yaml.safe_load(path.read_text())["layers"]
    order = {s: i for i, s in enumerate(slots())}
    codes = []
    for layer in data:
        keys = ["_"] * len(order)
        if len(layer["rows"]) != 4:
            sys.exit(f"{layer['name']}: expected 4 rows, found {len(layer['rows'])}")
        for r, text in enumerate(layer["rows"]):
            found = text.replace("|", " ").split()
            want = row_slots(r)
            if len(found) != len(want):
                sys.exit(f"{layer['name']}, row {r + 1}: expected {len(want)} keys, found {len(found)}")
            for slot, code in zip(want, found):
                keys[order[slot]] = code
        codes.append(keys)

    pictures = []
    for n, (layer, keys) in enumerate(zip(data, codes)):
        reach = set(layer.get("reach", []))
        specs = []
        for i, code in enumerate(keys):
            # a transparent key that is held to reach this layer: show the layer key below it, amber
            below = next((codes[m][i] for m in range(n - 1, -1, -1) if codes[m][i] != "_"), "_")
            held = code == "_" and (m := re.fullmatch(r"MO\((\d)\)", below)) and int(m.group(1)) in reach
            specs.append({"t": LAYER_KEY[int(m.group(1))], "type": "held"} if held else legend_for(code, legends, raw))
        pictures.append(specs)
    return [layer["name"] for layer in data], pictures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out_dir", nargs="?", type=Path, default=HERE, help="folder for the SVG files")
    parser.add_argument("--layout", type=Path, default=HERE / "layout.yaml", help="layout file to draw")
    parser.add_argument("--name", default="Cornix layer {index}.svg", help="file name pattern")
    args = parser.parse_args()
    out_dir: Path = args.out_dir.expanduser()
    if not out_dir.is_dir():
        sys.exit(f"No such folder: {out_dir}")

    config = yaml.safe_load(CONFIG.read_text())
    legends = config["parse_config"]["zmk_keycode_map"]
    raw = config["parse_config"]["raw_binding_map"]
    glyphs = (config.get("draw_config") or {}).get("glyphs") or {}
    names, pictures = read_layers(args.layout, legends, raw)
    keys = layout()
    for index, (name, specs) in enumerate(zip(names, pictures)):
        target = out_dir / args.name.format(index=index)
        svg = draw.draw_layer([specs], 0, name, keys, glyphs).replace("<title>Sofle keymap:", "<title>Cornix keymap:")
        target.write_text(svg)
        print(f"wrote {target}  ({name})")


if __name__ == "__main__":
    main()
