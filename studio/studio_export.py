#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyserial>=3.5", "protobuf>=7.35.1,<8"]
# ///
"""Export the keymap that ZMK Studio saved on the keyboard into this repo.

Studio keeps its edits in the keyboard's settings flash, where they override
config/eyelash_sofle.keymap. This script reads them over the Studio RPC protocol
(USB serial, left half plugged in) and writes:

- config/studio-export.json  the raw bindings, as a lossless backup
- config/eyelash_sofle.keymap  only the `bindings` and `display-name` of each
  layer are rewritten; includes, macros, combos and sensor bindings stay as-is

Usage:
    studio/studio_export.py            export and rewrite the files
    studio/studio_export.py --check    exit 1 (and show a diff) if the files differ from the keyboard
    studio/studio_export.py --port /dev/cu.usbmodem1101
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import serial
from serial.tools import list_ports

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
VENDOR = HERE / "vendor" / "zmk-app"
KEYMAP = REPO / "config" / "eyelash_sofle.keymap"
EXPORT = REPO / "config" / "studio-export.json"

sys.path.insert(0, str(HERE / "studio_pb"))
import behaviors_pb2  # noqa: E402
import core_pb2  # noqa: E402
import keymap_pb2  # noqa: E402
import studio_pb2  # noqa: E402

ZMK_USB_VENDOR_ID = 0x1D50
warnings: list[str] = []


def warn(message: str) -> None:
    warnings.append(message)
    print(f"warning: {message}", file=sys.stderr)


# --- Studio RPC transport: protobuf messages framed as SOF, escaped payload, EOF ---

SOF, ESC, EOF = 0xAB, 0xAC, 0xAD


class Studio:
    def __init__(self, port: str):
        self.serial = serial.Serial(port, timeout=0.1)
        self.request_id = 0
        self.serial.reset_input_buffer()

    def call(self, timeout: float = 3.0, **subsystem) -> studio_pb2.RequestResponse:
        self.request_id += 1
        payload = studio_pb2.Request(request_id=self.request_id, **subsystem).SerializeToString()
        frame = bytearray([SOF])
        for byte in payload:
            if byte in (SOF, ESC, EOF):
                frame.append(ESC)
            frame.append(byte)
        frame.append(EOF)
        self.serial.write(frame)

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            message = self._read_frame(deadline)
            if message is None:
                break
            response = studio_pb2.Response.FromString(message)
            if response.WhichOneof("type") != "request_response":
                continue  # notifications, e.g. unsaved-changes status
            reply = response.request_response
            if reply.request_id != self.request_id:
                continue
            if reply.WhichOneof("subsystem") == "meta":
                raise RuntimeError(f"keyboard refused the request: {reply.meta}")
            return reply
        raise TimeoutError(
            "no reply from the keyboard. Is the left half plugged in over USB and using USB output? "
            "(press &out OUT_USB on layer 2, and OUT_BLE afterwards)")

    def _read_frame(self, deadline: float) -> bytes | None:
        buffer = bytearray()
        in_frame = escaped = False
        while time.monotonic() < deadline:
            chunk = self.serial.read(1)
            if not chunk:
                continue
            byte = chunk[0]
            if escaped:
                buffer.append(byte)
                escaped = False
            elif byte == SOF:
                buffer.clear()
                in_frame = True
            elif not in_frame:
                continue
            elif byte == ESC:
                escaped = True
            elif byte == EOF:
                return bytes(buffer)
            else:
                buffer.append(byte)
        return None


def find_port() -> str:
    ports = [p.device for p in list_ports.comports() if p.vid == ZMK_USB_VENDOR_ID and p.device.startswith("/dev/cu.")]
    if not ports:
        sys.exit("No ZMK keyboard on USB. Plug the left half into this Mac (or pass --port).")
    if len(ports) > 1:
        sys.exit(f"Several ZMK serial ports: {', '.join(ports)}. Pick one with --port.")
    return ports[0]


# --- C preprocessor #defines from ZMK's dt-bindings headers, evaluated as Python ---

DEFINE = re.compile(r"^[ \t]*#define[ \t]+(\w+)(\(([^)]*)\))?[ \t]*(.*)$", re.M)


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def split_cells(body: str) -> list[str]:
    """Splits "BT_CLR_CMD 0" into two cells, but keeps "(a << 24 | b)" as one."""
    cells: list[str] = []
    depth, current = 0, ""
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch.isspace() and depth == 0:
            if current:
                cells.append(current)
            current = ""
        else:
            current += ch
    if current:
        cells.append(current)
    merged: list[str] = []
    for cell in cells:
        if merged and (re.search(r"[-+|&<>~*^]$", merged[-1]) or re.match(r"^[-+|&<>*^]", cell)):
            merged[-1] += " " + cell
        else:
            merged.append(cell)
    return merged


class Defines:
    """Object-like and function-like macros, evaluated lazily and only to ints."""

    def __init__(self):
        self.objects: dict[str, str] = {}
        self.functions: dict[str, tuple[list[str], str]] = {}
        self.order: dict[str, list[str]] = {}  # header file -> names in definition order

    def add_text(self, text: str, origin: str) -> None:
        text = strip_comments(text.replace("\\\n", " "))
        for match in DEFINE.finditer(text):
            name, is_function, params, body = match.groups()
            if name in self.objects or name in self.functions:
                continue  # first definition wins (the keymap's own overrides come first)
            body = re.sub(r"\b(0x[0-9a-fA-F]+|\d+)[uUlL]+\b", r"\1", body.strip())
            if is_function:
                self.functions[name] = ([p.strip() for p in params.split(",") if p.strip()], body)
            else:
                self.objects[name] = body
                self.order.setdefault(origin, []).append(name)

    def cells(self, name: str) -> tuple[int, ...] | None:
        return self.values(self.objects[name])

    def values(self, expr: str) -> tuple[int, ...] | None:
        """Evaluates binding parameters such as "BT_SEL 2", "LS(A)" or "RGB_OFF" (two cells)."""
        result: list[int] = []
        try:
            for cell in split_cells(expr):
                if cell in self.objects and len(split_cells(self.objects[cell])) > 1:
                    result.extend(self.values(self.objects[cell]))
                else:
                    result.append(self._eval(cell, set()))
        except Exception:
            return None
        return tuple(result)

    def _eval(self, expr: str, seen: set[str]) -> int:
        defines = self

        class Namespace(dict):
            def __missing__(self, key):
                if key in defines.functions:
                    params, body = defines.functions[key]
                    return lambda *args: defines._eval(body, seen | {key}) if not params else \
                        defines._eval_with(body, dict(zip(params, args)), seen | {key})
                if key in defines.objects and key not in seen:
                    cells = split_cells(defines.objects[key])
                    if len(cells) != 1:
                        raise ValueError(key)
                    return defines._eval(cells[0], seen | {key})
                if key == "BIT":
                    return lambda n: 1 << n
                raise NameError(key)

        return int(eval(expr, {"__builtins__": {}}, Namespace()))

    def _eval_with(self, body: str, args: dict[str, int], seen: set[str]) -> int:
        for name, value in args.items():
            body = re.sub(rf"\b{name}\b", f"({value})", body)
        return self._eval(body, seen)


# --- Behaviors: Studio reports display names; the keymap needs &references ---

@dataclass
class Behavior:
    ref: str
    cells: int


NODE = re.compile(r"(?:/omit-if-no-ref/\s*)?(\w+)\s*:\s*([\w-]+)\s*\{")


def parse_behaviors(text: str) -> dict[str, Behavior]:
    """Maps display-name, node name and label of each behavior node to its &reference."""
    found: dict[str, Behavior] = {}
    text = strip_comments(text)
    matches = list(NODE.finditer(text))
    for i, match in enumerate(matches):
        block = text[match.end():matches[i + 1].start() if i + 1 < len(matches) else len(text)]
        cells = re.search(r"#binding-cells\s*=\s*<(\d+)>", block)
        if not cells or "compatible" not in block:
            continue
        behavior = Behavior(ref=match.group(1), cells=int(cells.group(1)))
        for key in (re.search(r'display-name\s*=\s*"([^"]+)"', block),
                    re.search(r'\blabel\s*=\s*"([^"]+)"', block)):
            if key:
                found.setdefault(key.group(1), behavior)
        found.setdefault(match.group(2), behavior)
        found.setdefault(match.group(1), behavior)
    return found


# Which kind of value each parameter of a built-in behavior holds.
PARAM_KINDS = {
    "kp": ("key",), "kt": ("key",), "sk": ("key",), "mt": ("key", "key"), "lt": ("layer", "key"),
    "mo": ("layer",), "tog": ("layer",), "to": ("layer",), "sl": ("layer",),
}
# Behaviors whose parameters are named constants: (header, names to consider).
FAMILIES = {
    "bt": ("bt.h", r"BT_\w+"), "out": ("outputs.h", r"OUT_\w+"), "rgb_ug": ("rgb.h", r"RGB_\w+"),
    "bl": ("backlight.h", r"BL_\w+"), "ext_power": ("ext_power.h", r"EP_\w+"),
    "mkp": ("pointing.h", r"MB\d|[LRM]CLK"), "mmv": ("pointing.h", r"MOVE_(UP|DOWN|LEFT|RIGHT)"),
    "msc": ("pointing.h", r"SCRL_(UP|DOWN|LEFT|RIGHT)"),
}
MODIFIERS = [(0x01, "LC"), (0x02, "LS"), (0x04, "LA"), (0x08, "LG"),
             (0x10, "RC"), (0x20, "RS"), (0x40, "RA"), (0x80, "RG")]


class Renderer:
    def __init__(self, defines: Defines, preferred: set[str], layer_index: dict[int, int]):
        self.preferred = preferred
        self.layer_index = layer_index
        self.keys = self._reverse(defines, ["keys.h"], None)
        self.families = {ref: self._reverse(defines, [header], pattern) for ref, (header, pattern) in FAMILIES.items()}

    def _reverse(self, defines: Defines, headers: list[str], pattern: str | None) -> dict[tuple[int, ...], str]:
        candidates: dict[tuple[int, ...], list[str]] = {}
        for header in headers:
            for name in defines.order.get(header, []):
                if pattern and not re.fullmatch(pattern, name):
                    continue
                cells = defines.cells(name)
                if cells:
                    candidates.setdefault(cells, []).append(name)
        # Prefer the spelling the keymap already uses, then the shortest alias.
        return {cells: min(names, key=lambda n: (n not in self.preferred, len(n), names.index(n)))
                for cells, names in candidates.items()}

    def key(self, value: int) -> str:
        if (value,) in self.keys:
            return self.keys[(value,)]
        mods, base = value >> 24, value & 0xFFFFFF
        name = self.keys.get((base,))
        if name is None or mods == 0:
            return hex(value)
        for bit, wrapper in reversed(MODIFIERS):
            if mods & bit:
                name = f"{wrapper}({name})"
        return name

    def layer(self, layer_id: int) -> str:
        return str(self.layer_index.get(layer_id, layer_id))

    def binding(self, behavior: Behavior, params: list[int]) -> str:
        params = params[:behavior.cells]
        kinds = PARAM_KINDS.get(behavior.ref)
        if kinds:
            rendered = [self.key(p) if kind == "key" else self.layer(p) for kind, p in zip(kinds, params)]
        elif behavior.ref in FAMILIES:
            table = self.families[behavior.ref]
            if tuple(params) in table:
                rendered = [table[tuple(params)]]
            elif params and (params[0],) in table:
                rendered = [table[(params[0],)]] + [str(p) for p in params[1:]]
            else:
                rendered = [str(p) for p in params]
        else:
            rendered = [str(p) for p in params]
        return " ".join([f"&{behavior.ref}", *rendered])


# --- Keymap file editing ---

def find_block(text: str, start: int) -> int:
    """Index just past the `}` matching the `{` at `start`."""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    raise ValueError("unbalanced braces in keymap")


@dataclass
class LayerNode:
    name: str
    start: int
    end: int
    text: str


def keymap_layers(text: str) -> tuple[int, int, list[LayerNode]]:
    match = re.search(r"\bkeymap\s*\{", text)
    if not match:
        sys.exit(f"{KEYMAP}: no keymap node")
    open_brace = match.end() - 1
    close = find_block(text, open_brace)
    layers: list[LayerNode] = []
    position = open_brace + 1
    for node in re.finditer(r"(\w+)\s*\{", text[position:close]):
        start = position + node.start()
        if layers and start < layers[-1].end:
            continue
        end = find_block(text, position + node.end() - 1)
        layers.append(LayerNode(node.group(1), start, end, text[start:end]))
    return open_brace, close, layers


BINDINGS = re.compile(r"(?<![-\w])bindings\s*=\s*<(.*?)>\s*;", re.S)
TOKEN = re.compile(r"&\w+(?:[ \t]+(?!&)[^\s&]+)*")


def layer_tokens(layer_text: str) -> list[str]:
    match = BINDINGS.search(strip_comments(layer_text))
    return TOKEN.findall(match.group(1)) if match else []


def row_lengths(layer_text: str) -> list[int]:
    match = BINDINGS.search(strip_comments(layer_text))
    if not match:
        return []
    return [len(TOKEN.findall(line)) for line in match.group(1).splitlines() if "&" in line]


def same_binding(token: str, behavior: Behavior, params: list[int], defines: Defines,
                 layer_index: dict[int, int]) -> bool:
    """Whether the file's text for a key already means what the keyboard has."""
    ref, _, rest = token.partition(" ")
    if ref[1:] != behavior.ref:
        return False
    values = defines.values(rest.strip()) if rest.strip() else ()
    if values is None:
        return False
    expected = list(params[:behavior.cells])
    kinds = PARAM_KINDS.get(behavior.ref, ())
    expected = [layer_index.get(p, p) if i < len(kinds) and kinds[i] == "layer" else p for i, p in enumerate(expected)]
    return list(values) + [0] * (behavior.cells - len(values)) == expected


def column_gaps(layer_text: str) -> list[int]:
    """The narrowest run of spaces between each pair of columns in the file, so a
    wider gap (like the one between the two halves) survives reformatting."""
    match = BINDINGS.search(strip_comments(layer_text))
    gaps: list[int] = []
    for line in match.group(1).splitlines() if match else []:
        spans = [m.span() for m in TOKEN.finditer(line)]
        for c, (a, b) in enumerate(zip(spans, spans[1:])):
            gap = b[0] - a[1]
            if c < len(gaps):
                gaps[c] = min(gaps[c], gap)
            else:
                gaps.append(gap)
    return gaps


def format_bindings(bindings: list[str], rows: list[int], gaps: list[int]) -> str:
    if sum(rows) != len(bindings):
        rows = [13] * (len(bindings) // 13) + ([len(bindings) % 13] if len(bindings) % 13 else [])
    lines, i = [], 0
    for length in rows:
        lines.append(bindings[i:i + length])
        i += length
    widths = [max(len(line[c]) for line in lines if c < len(line)) for c in range(max(rows))]
    # Each column is padded to its widest cell; the file's measured gap is the spacing
    # left after the widest cell, so subtract the padding the original already had.
    out = []
    for line in lines:
        text = ""
        for c, cell in enumerate(line):
            text += cell
            if c + 1 < len(line):
                text += " " * (widths[c] - len(cell) + max(2, gaps[c] if c < len(gaps) else 2))
        out.append(text)
    return "\n".join(out)


def set_layer(layer_text: str, bindings: str, display_name: str) -> str:
    layer_text = re.sub(r"((?<![-\w])bindings\s*=\s*<).*?(>\s*;)",
                        lambda m: f"{m.group(1)}\n{bindings}\n            {m.group(2)}", layer_text, count=1, flags=re.S)
    if re.search(r'display-name\s*=\s*"[^"]*"', layer_text):
        layer_text = re.sub(r'(display-name\s*=\s*")[^"]*(")', lambda m: f"{m.group(1)}{display_name}{m.group(2)}",
                            layer_text, count=1)
    elif display_name:
        layer_text = layer_text.rstrip("}").rstrip() + f'\n            display-name = "{display_name}";\n        }}'
    return layer_text


# --- Main ---

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", help="serial port of the left half (default: auto-detect)")
    parser.add_argument("--check", action="store_true", help="only compare; exit 1 if the files are out of date")
    args = parser.parse_args()

    studio = Studio(args.port or find_port())
    device = studio.call(core=core_pb2.Request(get_device_info=True)).core.get_device_info
    print(f"Connected to {device.name}")
    unsaved = studio.call(keymap=keymap_pb2.Request(check_unsaved_changes=True)).keymap.check_unsaved_changes
    if unsaved:
        warn("Studio has unsaved changes; exporting the live keymap, which is lost on power-off unless saved")

    behavior_ids = studio.call(behaviors=behaviors_pb2.Request(list_all_behaviors=True)).behaviors.list_all_behaviors.behaviors
    names = {}
    for behavior_id in behavior_ids:
        details = studio.call(behaviors=behaviors_pb2.Request(
            get_behavior_details=behaviors_pb2.GetBehaviorDetailsRequest(behavior_id=behavior_id)))
        names[behavior_id] = details.behaviors.get_behavior_details.display_name
    keymap = studio.call(keymap=keymap_pb2.Request(get_keymap=True)).keymap.get_keymap

    original = KEYMAP.read_text()
    defines = Defines()
    defines.add_text(original, "keymap")
    for header in sorted((VENDOR / "dt-bindings").glob("*.h")):
        defines.add_text(header.read_text(), header.name)
    known = parse_behaviors(original)
    for dtsi in sorted((VENDOR / "behaviors").glob("*.dtsi")):
        for key, behavior in parse_behaviors(dtsi.read_text()).items():
            known.setdefault(key, behavior)

    preferred = set(re.findall(r"\b[A-Z_][A-Z0-9_]*\b", original))
    layer_index = {layer.id: index for index, layer in enumerate(keymap.layers)}
    renderer = Renderer(defines, preferred, layer_index)

    open_brace, close, nodes = keymap_layers(original)
    exported_layers = []
    new_nodes = []
    for index, layer in enumerate(keymap.layers):
        rendered, raw = [], []
        current = layer_tokens(nodes[layer.id].text) if layer.id < len(nodes) else []
        for position, binding in enumerate(layer.bindings):
            display = names.get(binding.behavior_id, f"<behavior {binding.behavior_id}>")
            behavior = known.get(display)
            params = [binding.param1, binding.param2]
            if behavior is None:
                warn(f"layer {index} key {position}: unknown behavior {display!r} "
                     f"({binding.param1}, {binding.param2}); written as &none")
                text = f"&none /* unknown: {display} {binding.param1} {binding.param2} */"
            elif position < len(current) and same_binding(current[position], behavior, params, defines,
                                                           layer_index):
                text = current[position]  # unchanged: keep the spelling already in the file
            else:
                text = renderer.binding(behavior, params)
            rendered.append(text)
            raw.append({"behavior": display, "param1": binding.param1, "param2": binding.param2, "keymap": text})
        exported_layers.append({"id": layer.id, "name": layer.name, "bindings": raw})

        # Layer ids are the devicetree order the firmware was built from; reuse that node
        # as the template so sensor-bindings and other properties survive.
        template = nodes[layer.id].text if layer.id < len(nodes) else \
            f"layer_{layer.id} {{\n            bindings = <\n            >;\n        }}"
        if rendered == current:
            bindings_text = BINDINGS.search(template).group(1).strip("\n").rstrip()  # untouched: keep as written
        else:
            layout = template if row_lengths(template) else (nodes[0].text if nodes else template)
            bindings_text = format_bindings(rendered, row_lengths(layout), column_gaps(layout))
        new_nodes.append(set_layer(template, bindings_text, layer.name))

    if [layer.id for layer in keymap.layers] != list(range(len(nodes))):
        warn(f"Studio has layers {[l.id for l in keymap.layers]} but the file has {len(nodes)}; "
             "layers were added, removed or reordered, so the file's layer list is rebuilt")

    if nodes:
        head = original[:nodes[0].start]
        tail = original[nodes[-1].end:]
        separators = [original[a.end:b.start] for a, b in zip(nodes, nodes[1:])]
        sep = separators[0] if separators else "\n\n        "
        updated = head + sep.join(new_nodes) + tail
    else:
        updated = original[:open_brace + 1] + "\n        " + "\n\n        ".join(new_nodes) + original[close - 1:]

    exported = json.dumps({"device": device.name, "layers": exported_layers,
                           "behaviors": {str(k): v for k, v in sorted(names.items())}}, indent=2) + "\n"

    changes = []
    for path, new in ((KEYMAP, updated), (EXPORT, exported)):
        old = path.read_text() if path.exists() else ""
        if old != new:
            changes.append(path)
            if args.check:
                sys.stdout.writelines(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                                           str(path.relative_to(REPO)), "keyboard"))
            else:
                path.write_text(new)

    if args.check:
        print("Up to date." if not changes else f"Out of date: {', '.join(str(p.relative_to(REPO)) for p in changes)}")
        sys.exit(1 if changes else 0)
    print("Updated: " + ", ".join(str(p.relative_to(REPO)) for p in changes) if changes else "No changes.")
    if warnings:
        print(f"{len(warnings)} warning(s); see above.")


if __name__ == "__main__":
    main()
