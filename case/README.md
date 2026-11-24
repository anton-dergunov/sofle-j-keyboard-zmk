# Sofle-J Choc carrying cases

Three cases for carrying both halves of the PandaKB Sofle-J Choc keyboard without anything pressing the keys. All three are modelled around the newer PandaKB bottom case (August 2025, 146.3 × 121.2 mm per half), with keycap tops measured at 18 mm.

| Design | Printed parts | Weight | Closed size (mm) | Also needed |
|---|---|---|---|---|
| Spacer ring | `1-spacer-ring` | 45 g | 151 × 125 × 38 | 2 flat silicone bands, 12 mm wide |
| Snap-on lids | `4-lid-left`, `4-lid-right` | 2 × 51 g | 150 × 125 × 23 each half | — |
| Hinged clamshell, nylon | `5-tray-left`, `5-tray-right` | 79 g | 164 × 125 × 41 | 4 magnets, a 2 mm steel rod, epoxy |
| Hinged clamshell, FDM | `5-tray-left-fdm`, `5-tray-right-fdm` | under 125 g in PETG | 165 × 126 × 42 | the same |

The print files are in `out/print/`, as STL and 3MF. The comparison page with renders and cross-sections is `out/concepts.html`.

## Ordering the clamshell as an FDM print

This is the cheapest way to get the clamshell made, and UK services print it in a few days. Upload `5-tray-left-fdm.stl` and `5-tray-right-fdm.stl`.

The FDM files differ from the nylon ones:

- **Thicker:** walls are 2.0 mm instead of 1.6 mm and floors 1.8 mm instead of 1.4 mm, for a stiffer, harder-wearing case.
- **No supports needed:** every downward-facing surface slopes at 45° or less. This covers the undersides of the hinge knuckles, the magnet bosses and the thumb lips, and the bottom edge, which is chamfered instead of rounded. Each tray prints as the file lies: floor on the bed, open side up.
- **More clearance:** FDM prints holes and gaps slightly small, so they are opened up. The keyboard gets 0.6 mm of clearance per side instead of 0.5 mm, the magnet pockets are 8.4 mm across, and the tab slots are 1.0 mm wide. The pin holes are 2.15 mm in the left tray and 2.6 mm in the right.

**Settings, at either service:**

- **Infill: the lowest offered (20%).** The walls and floor print solid at any infill setting. Infill only fills the inside of the hinge knuckles and the magnet bosses, so a higher setting adds cost without adding strength.
- **Layer height:** the standard 0.2 mm. A finer setting costs more and gains nothing here.
- **Colour:** black hides scuffs.
- Don't choose PLA, carbon-fibre PETG or TPU. PLA and carbon-fibre PETG are brittle where the click tabs bend, and PLA also softens in a hot car. TPU is too soft.

### Surface Scan (surfacescan.co.uk)

- Technology **FDM**, material **PETG**, infill **Light (20%)**, colour **black**.
- Their staff prepare each file by hand. Add this note under "Leave us a message": *"Please print each tray as oriented in the file, flat floor on the bed and open side up. The parts are designed to print without supports. Standard 0.2 mm layers and 20% infill are fine."*
- Shipping is £5.99. Check whether the quoted prices include VAT, since their minimum order of £10 is quoted "plus VAT".
- They state FDM accuracy of about ±0.3 mm, which fits inside the 0.6 mm clearance.

### MakeitQuick (makeitquick.co.uk)

- Technology **FDM**, material **ABS+** (they don't offer PETG), **Standard infill 20%**, **0.20 mm** layers.
- ABS+ suits this case too: it is tough, takes the click tabs well, and stands more heat than PETG. They state accuracy of ±0.2%, about ±0.3 mm across a tray.
- Shipping is free (2–3 day tracked). If you are not in a hurry, the Economy tier is 20% cheaper and takes 10–12 working days. Their minimum order is £20 plus VAT.
- Their 2+ copies discount does not apply here: the left and right trays are different parts.

## Ordering the nylon prints

- **Process and material:** MJF (HP Multi Jet Fusion) or SLS in PA12 nylon. Grey is the default; dyed black looks better and hides scuffs. Avoid resin, which is brittle for the click tabs. The spacer ring and the lids exist only in this version: their overhangs need nylon's powder bed.
- **Services:** JLC3DP, PCBWay or Craftcloud (instant quote from the STL files, shipped from abroad). In the UK, Surface Scan prints SLS PA12, at about £28 per clamshell tray. No supports or orientation settings are needed.
- **Tolerances:** walls clear the keyboard case by 0.5 mm, and the click beads overlap the case's chamfers by 0.35–0.5 mm. Standard accuracy is fine; no tight-tolerance option is needed.

## Assembling the clamshell

1. **Test the fit first.** Drop each half into its tray, keys up, and press the rim down until the three tabs click over it. A slightly loose fit is fine. If a tab is too stiff to click, sand the inner face of its bead a little.
2. **Fit the hinge pin** before gluing anything. Use a 2 mm stainless steel rod cut to 84 mm (bought as 100 mm); a 2 mm carbon-fibre rod also works and cuts with a knife. Push it through the knuckles from either end:
   - the left tray's knuckles hold it tight;
   - the right tray's knuckles turn freely on it.

   If a tight hole is too small, open it with a 2 mm drill bit turned by hand. This is likely on an FDM print. If the rod later works loose, put a drop of superglue on it at the left tray's outer knuckles only, keeping glue off the right tray's knuckles.
3. **Glue in the magnets:** four neodymium discs, 8 × 2 mm, N52, axially magnetised.
   - Use two-part epoxy, such as J-B Weld. It fills the small gap around each magnet and doesn't crack from knocks. Superglue holds poorly in a loose pocket and goes brittle.
   - Roughen the magnet and the pocket with sandpaper and wipe both with isopropyl alcohol. Put a small dab of epoxy in the pocket and press the magnet to the bottom. It sits about 0.3 mm below the surface, so it can't scrape the other tray.
   - Get the polarity right: stick the magnets together in two pairs and mark the outward faces. Glue one magnet of each pair into the left tray and its partner into the matching pocket of the right tray, so that each pair attracts when the case closes.
   - Let the epoxy cure with the case open, so that squeezed-out epoxy can't glue the trays together.

## Straps for the spacer ring

Two flat silicone bands about 12 mm wide, with a relaxed circumference of about 230–260 mm. Each sits between a pair of ridges on the ring and runs across both case bottoms.

## Regenerating

```
uv run python designs/build.py    # print files + fit checks
uv run python designs/render.py   # renders for the page
uv run python concepts/render.py  # the five original concepts
```

`build.py` also checks that the trays don't touch at any hinge angle from closed to open flat, and that nothing on the FDM trays overhangs past 45°.

Model sources: the bottom case and plate come from [PandaKBLab/sofle-j-keyboard-case](https://github.com/PandaKBLab/sofle-j-keyboard-case) (CC BY-NC-SA 4.0), cloned to `~/projects/external/`.
