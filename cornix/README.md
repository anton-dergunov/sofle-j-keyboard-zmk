# Cornix layout

The Cornix LP (PandaKB, 48 keys + 2 knobs, RMK firmware edited through Vial) is set up to feel like the Sofle in this repo: **a Sofle without the number row**. Everything else is the Sofle key for key, and one extra layer, Num, brings the missing row back.

Decided and put on the keyboard in November 2026. `layout.yaml` is the layout: `apply.py` writes it to the keyboard and `draw.py` draws the pictures below from it.

## The layout

| Layer | How to reach it | What it holds |
|---|---|---|
| 0 Base | — | The Sofle's base layer without its number row. ⌫ takes the top-right corner (where the Sofle has \\). |
| 1 Nav | hold **M1**, the middle thumb key, either half; double-tap to lock | The Sofle's Nav layer without its top row: arrows, Page Up/Down, Home/End, - = [ ], \`, Caps Lock, F1–F10. |
| 2 System | hold M1, then **M2** (G on the left, ⌥ on the right) | Bluetooth profiles 1–3 and forget-pairing, desk switch (not wired yet), USB/BT output switch, reset, flash. |
| 3 Num | hold **Num**, the outer thumb key, either half; double-tap to lock | Q row: the Sofle's number row (Esc 1–0, and \\ where ⌫ would be). A row: the Sofle's Nav top row (brightness, Mission Control, Launchpad, Spotlight, media, volume). |

Bottom row, each half: ⌃ ⌥ ⌘ on the three keys under the outer columns, then the thumbs Num, M1, Space. Space is on both thumbs and ↩ is on the left pinky (the Caps Lock key), as on the Sofle. Double-tapping Num or M1 keeps that layer on, for several digits or arrow presses in a row; one tap of the same key turns it off. M2 doesn't lock. Both knobs turn the volume and press for mute on every layer. The pictures leave the knobs out, as the Sofle pictures leave out its knob.

![Base](Cornix%20layer%200.svg)
![Nav](Cornix%20layer%201.svg)
![System](Cornix%20layer%202.svg)
![Num](Cornix%20layer%203.svg)

Held keys are amber (with a lock icon where the key also unlocks), pale blank keys do what the base layer does, the desk keys are blue and the key that forgets a pairing is red.

## Decisions

The constraint behind every choice: per half, the Cornix lacks the Sofle's six number-row keys (Esc, 1–5 or 6–0, ⌫) and has one key the Sofle doesn't, a third thumb key. Today's Sofle layout stays as it is.

- **Digits:** the spare thumb key on each half is Num, a held layer that shows the Sofle's number row one row lower. One per half keeps the rule that either half alone reaches every layer. The alternative (option B below) put the digits on the Nav layer of both boards, which would have meant rebuilding the Sofle's Nav.
- **Nav:** identical to the Sofle's, row for row.
- **⌫ in the top-right corner:** the same right-pinky reach as on the Sofle, one row lower. \\ moves to Num + that key.
- **Esc:** only on Num + Tab key, the spot under where Esc sits on the Sofle. Esc on M1 + Tab on both boards was considered and left out.
- **Bottom row ⌃ ⌥ ⌘ outside:** they group together like on a MacBook, and the six bottom keys split three modifiers and three thumbs. The alternative put ⌘ on the first thumb key (where the Sofle's ⌘ sits physically) and Num on an outer key, but holding Num with a finger is poor for typing long numbers.
- **System:** the Cornix version keeps the Sofle's rows below the Bluetooth row: desk keys on D F / K L, reset to flash on the bottom letter row. The Bluetooth profiles move down from the Sofle's number row to the Q row, and the disconnect keys are left out. The Cornix firmware has three profiles, one key that forgets the current profile's pairing (no forget-all), one USB/BT toggle instead of separate USB and BT keys, and no soft-off key, so those spots are blank. The Sofle's own System layer stays as it is.
- **Layer lock (Cornix only):** double-tap Num or M1 to keep its layer on, one tap to turn it off; for typing several digits or moving the cursor without holding a thumb down. Each is a Vial tap dance (hold: the layer, double tap: toggle it), and on the layer itself the same key is a plain toggle, so one tap unlocks. Tap-hold is set to resolve as soon as another key is pressed, so holding Num and typing feels like a plain hold key. M2 stays a plain hold key. The Sofle doesn't have this.

## Options considered

`options/layout-options.html` is the interactive comparison used to decide: every layer of both boards side by side, rings on changed keys, and toggles for each choice above. Open it in a browser (it loads its fonts from Google Fonts).

**Option B, digits on Nav**, is kept to try if A doesn't work out: `options/option-b.yaml`, drawn as `options/Cornix option B layer N.svg`. On both boards the Nav layer slides down one row and the digits take its Q row; on the Cornix the spare thumb keys become Esc (left) and ⌫ (right), and there are no F-keys. The Sofle's Nav changes with it (media to the left hand, F1–F10 to its number row); the HTML page shows that side.

Still open:
- **A second ↩ on the right.** No free key in A. Live with the left pinky ↩ on both boards for a few weeks first; if it still bothers you, B's right spare thumb is the cleanest spot, at the cost of putting ↩ back on a thumb.
- **⌦ Delete** has no key on either board (macOS uses fn + ⌫).
- **Desk switch (Personal/Work)** is drawn but not wired: the keys send nothing. To try: a Vial macro on RMK that presses F18/F19 and then switches the Bluetooth profile, as the Sofle's macros do.

## Redrawing the pictures

```sh
cornix/draw.py                                    # writes cornix/Cornix layer N.svg
cornix/draw.py "<obsidian vault>/90 Meta/Images"  # the copies the Obsidian note embeds
cornix/draw.py --layout cornix/options/option-b.yaml --name "Cornix option B layer {index}.svg" cornix/options
```

The script reuses `keymap-drawer/draw.py` (keycaps, colours, icons) and the legends in `keymap_drawer.config.yaml`. A keycode without a legend stops it with a message naming the keycode; add it to `QMK_TO_ZMK` in `draw.py`.

## Writing it to the keyboard

```sh
vitaly devices                       # the device id (1 on this Cornix)
vitaly -i 1 lock -u                  # unlock Vial: hold A and S on the left half until it says so
cornix/apply.py --device 1           # write cornix/cornix.vil, list the changes, show vitaly's preview
cornix/apply.py --device 1 --write   # load it into the keyboard and check a read-back
vitaly -i 1 lock -l                  # lock Vial again
```

Connect the Cornix over USB (Vial editing over Bluetooth is unreliable, says the PandaKB manual). [vitaly](https://github.com/bskaplou/vitaly) is a command-line Vial client (MIT; `brew install bskaplou/tap/vitaly`).

- `apply.py` fills a copy of `backup-2026-11-22.vil` (the keyboard as it came, saved with `vitaly save`) with `layout.yaml`: keys of layers 0–3, knobs, tap dances, the tap-hold settings. Everything else (layers 4–9, macros, combos) stays as in the backup. `cornix.vil` is the result, kept so the keyboard's state is on record. Save a fresh backup before changing the keyboard in Vial by hand.
- The Vial matrix, which only the keyboard knows (PandaKB publishes CAD files and compiled firmware, no keymap): rows 0–3 are the left half, 4–7 the right, column 0 the outer edge; the thumbs are row 3/7, columns 3–5, outer to inner; the knob presses are (2, 6) and (5, 6). `matrix()` in `apply.py` holds this.
- RMK firmware V1.12 quirks: writing a setting works but answers with what vitaly calls an "Unexpected protocol response", which stops `vitaly load` before the keys. `apply.py` writes the settings one by one, then loads the rest. vitaly exits with 0 even after an error, so the read-back is the real check.
- RMK's "User" keys: `QK_KB_0`–`2` Bluetooth profiles 1–3 (hold 5 s to forget the pairing), `QK_KB_3`/`4` next/previous profile, `QK_KB_5` forget the current profile's pairing, `QK_KB_6` USB/BT output, `QK_KB_7` forget the pairing between the halves. The firmware has 10 layers, 32 tap dances, 32 macros and 32 combos.
