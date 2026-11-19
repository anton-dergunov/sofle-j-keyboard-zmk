# studio

## studio_export.py: keep the ZMK Studio layout in this repo

ZMK Studio saves its edits on the keyboard itself. Those edits override
`config/eyelash_sofle.keymap` and survive firmware updates. This script reads
them back so the repo always holds the real layout.

```
studio/studio_export.py           # export: rewrites the layer bindings and config/studio-export.json
studio/studio_export.py --check   # only compare; exit 1 and show a diff if the repo is out of date
studio/studio_export.py --reset   # drop Studio's saved edits so the keyboard follows the flashed file
```

- **Connect:** plug the **left** half into the Mac with a USB cable. Studio
  answers on whichever output the keyboard is using. If the keyboard is pinned
  to Bluetooth, press `&out OUT_USB` on layer 2 first and `OUT_BLE` afterwards.
- **What changes in the file:** only each layer's `bindings` and
  `display-name`. Includes, macros, combos and sensor bindings stay as
  written, and so does the spelling of any key that didn't change (`UP_ARROW`
  stays `UP_ARROW`). A layer with no changed keys keeps its exact text.
- **The backup:** `config/studio-export.json` holds every binding as raw
  Studio data plus its devicetree form.
- **Unknown behaviors:** a behavior the script can't name is written as
  `&none /* unknown: … */` and reported as a warning, never dropped silently.
- **Needs:** [uv](https://docs.astral.sh/uv/). The dependencies (`pyserial`,
  `protobuf`) are declared inside the script.

### Workflow

The file `config/eyelash_sofle.keymap` is the source of truth; the pictures
are how you read it.

1. Change the layout: edit the file (by hand, with a coding agent, or in the
   web [Keymap Editor](https://nickcoutsos.github.io/keymap-editor/)), or try
   it in ZMK Studio, save, and run `studio/studio_export.py` to bring it into
   the file.
2. Run `keymap-drawer/draw.py` and look at the pictures (see below).
3. Commit and push. CI builds the firmware; flash `eyelash_sofle_studio_left`
   to the left half (the keymap lives there; the right half needs no flash).
4. If Studio edits were ever saved on the keyboard, they override the file,
   key by key: run `studio/studio_export.py --reset` once after flashing (the
   same as **Restore Stock Settings** in Studio). It drops only the saved
   keymap, not Bluetooth pairings, and then compares the keyboard with the file.
5. `studio/studio_export.py --check` should now say "Up to date."

## keymap-drawer/draw.py: one picture per layer

```
keymap-drawer/draw.py              # writes "Sofle layer N.svg" into keymap-drawer/
keymap-drawer/draw.py "<folder>"   # or into another folder, e.g. your notes' images
```

Labels, colours and icons are set in `keymap_drawer.config.yaml`, which the
GitHub draw action also uses for `keymap-drawer/eyelash_sofle.svg` (the
all-layers picture in the README). Layers whose keys are all transparent are
skipped. The pictures follow the viewer's light or dark theme.

### Vendored files

`vendor/` holds the ZMK v0.3.0 behavior definitions, dt-bindings headers and
Studio `.proto` files that the script reads. `studio_pb/` is the Python code
generated from those `.proto` files. After bumping ZMK in `config/west.yml`,
update `ZMK_REF` and `MSGS_REF` in `vendor/fetch.sh`, then regenerate:

```
studio/vendor/fetch.sh
uv run --no-project --with grpcio-tools python -m grpc_tools.protoc \
    -Istudio/vendor/proto --python_out=studio/studio_pb studio/vendor/proto/*.proto
```

## desk-switch macros

`to_personal` and `to_work` (in `config/eyelash_sofle.keymap`) tap F18 or F19
for [desk-switch](../../desk-switch), wait 150 ms, and then switch output:

- **Personal:** `&out OUT_USB` + Bluetooth profile 1. Over USB when the left
  half is cabled to the personal Mac; with no host on the cable (a charger, or
  unplugged), ZMK falls back to Bluetooth profile 1.
- **Work:** `&out OUT_BLE` + Bluetooth profile 2, even while cabled.

`BT_SEL` counts from 0. The keys sit on layer 2 (M1 + M2), R2 positions 3 and 4
of each half. If the cable ever goes to the work Mac instead, swap the two
`&out` lines.
