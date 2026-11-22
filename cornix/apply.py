#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6"]
# ///
"""Write cornix/layout.yaml to the Cornix over USB, with vitaly (a command-line Vial client).

Builds a Vial layout file (.vil) from the layout and a base .vil saved from the keyboard, then previews
or loads it with vitaly. The base file supplies everything the layout doesn't set (layers 4-9, macros,
combos, other settings).

Usage:
    cornix/apply.py                     write cornix/cornix.vil and show what changes against the base
    cornix/apply.py --device 1          the same, then vitaly's preview of the file
    cornix/apply.py --device 1 --write  load it into the keyboard and check a read-back (unlock it first:
                                        vitaly -i 1 lock -u, then hold the keys it marks, A and S on the left)

`vitaly devices` lists the device id. Save a fresh base before changing the keyboard by hand:
    vitaly -i 1 save -f cornix/backup-<date>.vil
"""

from __future__ import annotations

import argparse
import copy
import difflib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("cornix_draw", HERE / "draw.py")
cornix_draw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cornix_draw)

# --- Vial matrix: (row, column) of each slot. Rows 0-3 are the left half, 4-7 the right; column 0 is the
# outer edge, 5 the index-finger column. Row 3/7 holds the three bottom keys (columns 0-2) and the thumbs,
# outer to inner (columns 3-5). Column 6 has the knob presses at (2, 6) left and (5, 6) right; its other
# positions have no key.
ROW = {"q": 0, "a": 1, "z": 2}
THUMB_COLUMN = {"t1": 3, "t2": 4, "t3": 5}
KNOB_PRESS = [(2, 6), (5, 6)]
MATRIX_ROWS, MATRIX_COLUMNS = 8, 7


def matrix(slot: str) -> tuple[int, int]:
    side, key = slot[0], slot[1:]
    offset = 4 if side == "R" else 0
    if key in THUMB_COLUMN:
        return 3 + offset, THUMB_COLUMN[key]
    if key[0] == "b":
        return 3 + offset, int(key[1])
    return ROW[key[0]] + offset, int(key[1])


# Placeholders the keyboard has no key for yet: the desk switch is not wired (README.md, "Still open")
UNWIRED = {"DESK_PERSONAL": "KC_NO", "DESK_WORK": "KC_NO"}

# Vial's Tap-Hold settings (QMK settings ids, as `vitaly settings` lists them)
TAP_HOLD_QSID = {"permissive_hold": "22", "hold_on_other_press": "23", "chordal_hold": "26", "flow_tap_ms": "27"}


def vial_code(code: str, layer: int) -> str:
    if code == "_":
        return "KC_TRNS" if layer else "KC_NO"
    return UNWIRED.get(code, code)


def build(layout_path: Path, base: dict) -> dict:
    doc, codes = cornix_draw.read_codes(layout_path)
    vil = copy.deepcopy(base)
    slots = cornix_draw.slots()

    for n, (layer, keys) in enumerate(zip(doc["layers"], codes)):
        grid = [["KC_NO"] * MATRIX_COLUMNS for _ in range(MATRIX_ROWS)]
        for slot, code in zip(slots, keys):
            r, c = matrix(slot)
            grid[r][c] = vial_code(code, n)
        knobs = layer["knobs"]
        for r, c in KNOB_PRESS:
            grid[r][c] = vial_code(knobs["press"], n)
        vil["layout"][n] = grid
        # Knob turns: "_" means the base layer's turn. Written out on every layer, so it doesn't depend on
        # whether the firmware passes transparent encoder actions through.
        base_turn = doc["layers"][0]["knobs"]["turn"]
        turn = [b if t == "_" else t for t, b in zip(knobs["turn"], base_turn)]
        vil["encoder_layout"][n] = [list(turn) for _ in vil["encoder_layout"][n]]

    for n, td in enumerate(doc.get("tapdances") or []):
        vil["tap_dance"][n] = [td["tap"], td["hold"], td["double_tap"], td["tap_hold"], td["term_ms"]]

    for name, value in (doc.get("tap_hold") or {}).items():
        vil["settings"][TAP_HOLD_QSID[name]] = int(value)
    return vil


def changes(old: dict, new: dict) -> list[str]:
    out = []
    for n, (a, b) in enumerate(zip(old["layout"], new["layout"])):
        diff = [f"({r},{c}) {a[r][c]} -> {b[r][c]}" for r in range(len(a)) for c in range(len(a[r])) if a[r][c] != b[r][c]]
        if diff:
            out.append(f"layer {n}: {len(diff)} keys\n    " + "\n    ".join(diff))
    for key in ("encoder_layout", "tap_dance", "combo", "macro", "settings"):
        if old[key] != new[key]:
            if isinstance(old[key], list):
                idx = [i for i, (a, b) in enumerate(zip(old[key], new[key])) if a != b]
                out.append(f"{key}: " + "; ".join(f"[{i}] {old[key][i]} -> {new[key][i]}" for i in idx))
            else:
                out.append(f"{key}: {old[key]} -> {new[key]}")
    return out


def vitaly(device: str, *args: str) -> None:
    result = subprocess.run(["vitaly", "-i", device, *args], text=True)
    if result.returncode:
        sys.exit(f"vitaly {' '.join(args)} failed")


def write(device: str, vil: dict, out: Path) -> None:
    """Load the file into the keyboard. The Cornix firmware (RMK, V1.12) applies a setting but answers with a
    reply vitaly calls an "Unexpected protocol response", which stops `vitaly load` before the keys. So the
    settings go one by one with their errors ignored, the rest loads with an empty settings section, and a
    read-back checks the lot. vitaly exits with 0 even after printing an error (it printed an I/O timeout
    once while the load still went through), so the read-back is the real check."""
    for qsid, value in vil["settings"].items():
        text = str(value).lower() if qsid in ("22", "23", "26") else str(value)  # vitaly wants true/false for flags
        subprocess.run(["vitaly", "-i", device, "settings", "-q", qsid, "-v", text], capture_output=True)
    with tempfile.TemporaryDirectory() as tmp:
        rest = Path(tmp) / "keys.vil"
        rest.write_text(json.dumps({**vil, "settings": {}}))
        vitaly(device, "load", "-f", str(rest))
        back = Path(tmp) / "back.vil"
        subprocess.run(["vitaly", "-i", device, "save", "-f", str(back)], capture_output=True, check=True)
        # The keyboard reports long keycode names (KC_AUDIO_MUTE for KC_MUTE): compare vitaly's previews instead
        previews = [subprocess.run(["vitaly", "-i", device, "load", "-p", "-f", str(f)], capture_output=True,
                                   text=True).stdout.splitlines() for f in (back, out)]
    diff = list(difflib.unified_diff(*previews, "keyboard", out.name, lineterm="", n=0))
    print("read-back matches " + out.name if not diff else "read-back differs:\n" + "\n".join(diff))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--layout", type=Path, default=HERE / "layout.yaml")
    parser.add_argument("--base", type=Path, default=HERE / "backup-2026-11-22.vil", help="a .vil saved from the keyboard")
    parser.add_argument("--out", type=Path, default=HERE / "cornix.vil")
    parser.add_argument("--device", help="vitaly device id: preview the file against the keyboard")
    parser.add_argument("--write", action="store_true", help="load the file into the keyboard")
    args = parser.parse_args()

    base = json.loads(args.base.read_text())
    vil = build(args.layout, base)
    text = json.dumps(vil, indent=2)
    args.out.write_text(re.sub(r"\[\s+([^\[\]]*?)\s+\]", lambda m: "[" + " ".join(m.group(1).split()) + "]", text) + "\n")
    print(f"wrote {args.out}")
    print("\n".join(changes(base, vil)) or "no changes against the base")

    if args.write and not args.device:
        sys.exit("--write needs --device")
    if args.write:
        write(args.device, vil, args.out)
    elif args.device:
        vitaly(args.device, "load", "-p", "-f", str(args.out))


if __name__ == "__main__":
    main()
