# studio

## studio_export.py: keep the ZMK Studio layout in this repo

ZMK Studio saves its edits on the keyboard itself. Those edits override
`config/eyelash_sofle.keymap` and survive firmware updates. This script reads
them back so the repo always holds the real layout.

```
studio/studio_export.py           # export: rewrites the layer bindings and config/studio-export.json
studio/studio_export.py --check   # only compare; exit 1 and show a diff if the repo is out of date
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

1. Edit the layout in ZMK Studio and save.
2. Run `studio/studio_export.py`, review `git diff`, and commit.

To get the file's layout back onto the keyboard (after a settings reset, for
example), flash the firmware and press **Restore Stock Settings** in Studio.

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
for [desk-switch](../../desk-switch), wait 150 ms, and then select Bluetooth
profile 1 or 2 (`BT_SEL` counts from 0). Assign them to keys in Studio.
