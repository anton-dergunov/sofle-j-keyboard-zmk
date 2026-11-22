# Cornix layout

The Cornix LP (PandaKB, 48 keys + 2 knobs, RMK firmware edited through Vial) is set up to feel like the Sofle in this repo: **a Sofle without the number row**. Everything else is the Sofle key for key, and one extra layer, Num, brings the missing row back.

Status: decided in November 2026, **not yet on the keyboard**. `layout.yaml` is the layout; the pictures below are drawn from it.

## The layout

| Layer | How to reach it | What it holds |
|---|---|---|
| 0 Base | — | The Sofle's base layer without its number row. ⌫ takes the top-right corner (where the Sofle has \\). |
| 1 Nav | hold **M1**, the middle thumb key, either half | The Sofle's Nav layer without its top row: arrows, Page Up/Down, Home/End, - = [ ], \`, Caps Lock, F1–F10. |
| 2 System | hold M1, then **M2** (G on the left, ⌥ on the right) | Bluetooth profiles, desk switch, output, off, reset, flash. |
| 3 Num | hold **Num**, the outer thumb key, either half | Q row: the Sofle's number row (Esc 1–0, and \\ where ⌫ would be). A row: the Sofle's Nav top row (brightness, Mission Control, Launchpad, Spotlight, media, volume). |

Bottom row, each half: ⌃ ⌥ ⌘ on the three keys under the outer columns, then the thumbs Num, M1, Space. Space is on both thumbs and ↩ is on the left pinky (the Caps Lock key), as on the Sofle. Both knobs turn the volume and press for mute on every layer. The pictures leave the knobs out, as the Sofle pictures leave out its knob.

![Base](Cornix%20layer%200.svg)
![Nav](Cornix%20layer%201.svg)
![System](Cornix%20layer%202.svg)
![Num](Cornix%20layer%203.svg)

Held keys are amber, pale blank keys do what the base layer does, the desk keys are blue and the keys that forget pairings are red.

## Decisions

The constraint behind every choice: per half, the Cornix lacks the Sofle's six number-row keys (Esc, 1–5 or 6–0, ⌫) and has one key the Sofle doesn't, a third thumb key. Today's Sofle layout stays as it is.

- **Digits:** the spare thumb key on each half is Num, a held layer that shows the Sofle's number row one row lower. One per half keeps the rule that either half alone reaches every layer. The alternative (option B below) put the digits on the Nav layer of both boards, which would have meant rebuilding the Sofle's Nav.
- **Nav:** identical to the Sofle's, row for row.
- **⌫ in the top-right corner:** the same right-pinky reach as on the Sofle, one row lower. \\ moves to Num + that key.
- **Esc:** only on Num + Tab key, the spot under where Esc sits on the Sofle. Esc on M1 + Tab on both boards was considered and left out.
- **Bottom row ⌃ ⌥ ⌘ outside:** they group together like on a MacBook, and the six bottom keys split three modifiers and three thumbs. The alternative put ⌘ on the first thumb key (where the Sofle's ⌘ sits physically) and Num on an outer key, but holding Num with a finger is poor for typing long numbers.
- **System:** the Cornix version keeps the Sofle's rows below the Bluetooth row: desk keys on D F / K L, reset to flash on the bottom letter row. The Bluetooth profiles move down from the Sofle's number row to the Q row, and the disconnect keys are left out. The Sofle's own System layer stays as it is.

## Options considered

`options/layout-options.html` is the interactive comparison used to decide: every layer of both boards side by side, rings on changed keys, and toggles for each choice above. Open it in a browser (it loads its fonts from Google Fonts).

**Option B, digits on Nav**, is kept to try if A doesn't work out: `options/option-b.yaml`, drawn as `options/Cornix option B layer N.svg`. On both boards the Nav layer slides down one row and the digits take its Q row; on the Cornix the spare thumb keys become Esc (left) and ⌫ (right), and there are no F-keys. The Sofle's Nav changes with it (media to the left hand, F1–F10 to its number row); the HTML page shows that side.

Still open:
- **A second ↩ on the right.** No free key in A. Live with the left pinky ↩ on both boards for a few weeks first; if it still bothers you, B's right spare thumb is the cleanest spot, at the cost of putting ↩ back on a thumb.
- **⌦ Delete** has no key on either board (macOS uses fn + ⌫).

## Redrawing the pictures

```sh
cornix/draw.py                                    # writes cornix/Cornix layer N.svg
cornix/draw.py "<obsidian vault>/90 Meta/Images"  # the copies the Obsidian note embeds
cornix/draw.py --layout cornix/options/option-b.yaml --name "Cornix option B layer {index}.svg" cornix/options
```

The script reuses `keymap-drawer/draw.py` (keycaps, colours, icons) and the legends in `keymap_drawer.config.yaml`. A keycode without a legend stops it with a message naming the keycode; add it to `QMK_TO_ZMK` in `draw.py`.

## Next session: put the layout on the keyboard

Goal: write `layout.yaml` to the Cornix from a script, not by clicking through vial.rocks, then redraw the pictures and update the Obsidian note ("Cornix mechanical keyboard").

Tool: [vitaly](https://github.com/bskaplou/vitaly), a command-line client for Vial keyboards (MIT). It can back up and restore the whole layout as a `.vil` file, set single keys by layer/row/column, set knobs and macros, and report how many layers the keyboard has. Install with `brew install bskaplou/tap/vitaly` (or `cargo install vitaly`).

Steps:
1. Connect the Cornix over USB (Vial editing over Bluetooth is unreliable, says the PandaKB manual). Run `vitaly devices -c`, note the device id and check `layer_count` is at least 4 (the manual's default setup already uses `Mo(3)`, so layer 3 should exist).
2. **Back up first:** `vitaly -i <id> save -f cornix/backup-<date>.vil`, and commit it. That file also shows the Vial matrix (row, column) of every key and what Vial calls each keycode. The keyboard is the only source for the matrix: PandaKB's [Cornix repository](https://github.com/PandaKBLab/Cornix-Split-Low-Profile-Wireless-Keyboard) holds CAD files and compiled firmware (`firmwareV1.12.zip` is the newest: one `.uf2` per half), with no keymap or source.
3. Map each slot in `layout.yaml` to its matrix row and column. `draw.py` names the slots (`slots()`, `row_slots()`); add the matrix positions next to them, or in a small table.
4. Look up the RMK firmware's Vial keycodes for the placeholders in the System layer: `BT1`–`BT5`, `BT_CLEAR`, `BT_CLEAR_ALL`, `OUT_USB`, `OUT_BT`, `SOFT_OFF`, `REBOOT`, `BOOTLOADER`. The manual mentions BT0–BT2 under Vial's "User" tab, so the Cornix may have only 3 profiles; adjust the layer if so. Also check that RMK sends `KC_MCTL`, `KC_LPAD` and `KC_WSCH` (Mission Control, Launchpad, Spotlight) the way macOS expects.
5. Write `cornix/apply.py`: read `layout.yaml`, fill a copy of the backup `.vil` with the new keymap and knob settings, preview it with `vitaly -i <id> load -p -f <file>`, then load it. Setting single keys with `vitaly -i <id> keys -l <layer> -p <row>,<col> -v <KEYCODE>` is the fallback if the `.vil` route fails. Vial may need unlocking first (`vitaly -i <id> lock -u`, then hold the keys it marks).
6. Test on the keyboard: every layer reachable from either half alone, Num + Q row types the digits and Shift + Num + 1 types !, the knobs change the volume.
7. Desk switch (Personal/Work): leave unwired for now. Later, check whether a Vial macro on RMK can press F18/F19 and then switch the Bluetooth profile, as the Sofle's macros do.
8. Redraw the pictures into the vault and drop the "planned" wording from the note.
