#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["keymap-drawer==0.23.0", "pyyaml>=6"]
# ///
"""Draw one picture per layer of config/eyelash_sofle.keymap.

Writes "Sofle layer 0.svg", "Sofle layer 1.svg", ... to the output folder,
skipping layers where every key is transparent. Files are named by layer index,
so renaming a layer doesn't break pages that embed them. Labels and colours come
from keymap_drawer.config.yaml (the same file the GitHub draw action uses); the
pictures follow the viewer's light or dark theme.

Usage:
    keymap-drawer/draw.py                 write into keymap-drawer/
    keymap-drawer/draw.py "<folder>"      write into another folder, e.g. a notes app's images
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
KEYMAP = REPO / "config" / "eyelash_sofle.keymap"
LAYOUT = REPO / "config" / "eyelash_sofle.json"
CONFIG = REPO / "keymap_drawer.config.yaml"
NAME = "Sofle layer {index}.svg"


def keymap(*args: str) -> str:
    """Runs the keymap-drawer CLI and returns its stdout."""
    cmd = [sys.executable, "-m", "keymap_drawer", "-c", str(CONFIG), *args]
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def is_empty(keys: list) -> bool:
    return all(isinstance(key, dict) and key.get("type") == "trans" for key in keys)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out_dir", nargs="?", type=Path, default=HERE, help="folder for the SVG files")
    args = parser.parse_args()
    out_dir: Path = args.out_dir.expanduser()
    if not out_dir.is_dir():
        sys.exit(f"No such folder: {out_dir}")

    parsed = keymap("parse", "-z", str(KEYMAP))
    layers = yaml.safe_load(parsed)["layers"]
    with tempfile.NamedTemporaryFile("w", suffix=".yaml") as tmp:
        tmp.write(parsed)
        tmp.flush()
        for index, (name, keys) in enumerate(layers.items()):
            if is_empty(keys):
                print(f"skip  layer {index} ({name}): all keys transparent")
                continue
            target = out_dir / NAME.format(index=index)
            keymap("draw", "-j", str(LAYOUT), tmp.name, "-o", str(target), "-s", name)
            print(f"wrote {target}  ({name})")


if __name__ == "__main__":
    main()
