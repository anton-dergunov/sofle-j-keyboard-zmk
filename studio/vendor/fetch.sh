#!/bin/bash
# Fetches the ZMK files studio_export.py reads: behavior definitions (display
# name -> &reference), dt-bindings headers (numbers -> names) and the Studio
# RPC .proto files. Pin ZMK_REF to the revision in config/west.yml.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

ZMK_REF="v0.3.0"
MSGS_REF="6cb4c283e76209d59c45fbcb218800cd19e9339d"  # pinned by zmk's app/west.yml at $ZMK_REF

raw() { curl -fsSL "https://raw.githubusercontent.com/zmkfirmware/$1"; }

rm -rf zmk-app proto
mkdir -p zmk-app/behaviors zmk-app/dt-bindings proto
for f in $(curl -fsSL "https://api.github.com/repos/zmkfirmware/zmk/contents/app/dts/behaviors?ref=$ZMK_REF" | python3 -c 'import json,sys; print(" ".join(e["name"] for e in json.load(sys.stdin)))'); do
	raw "zmk/$ZMK_REF/app/dts/behaviors/$f" > "zmk-app/behaviors/$f"
done
for f in bt.h ext_power.h hid_usage.h hid_usage_pages.h keys.h modifiers.h mouse.h outputs.h pointing.h reset.h rgb.h backlight.h; do
	raw "zmk/$ZMK_REF/app/include/dt-bindings/zmk/$f" > "zmk-app/dt-bindings/$f"
done
for f in studio meta core behaviors keymap; do
	raw "zmk-studio-messages/$MSGS_REF/proto/zmk/$f.proto" > "proto/$f.proto"
done
echo "$ZMK_REF" > zmk-app/VERSION
echo "Fetched ZMK $ZMK_REF and zmk-studio-messages $MSGS_REF"
