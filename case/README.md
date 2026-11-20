# Sofle-J Choc carrying cases

Three cases for carrying both halves of the PandaKB Sofle-J Choc keyboard without anything pressing the keys. All three are modelled around the newer PandaKB bottom case (August 2025, 146.3 × 121.2 mm per half), with keycap tops measured at 18 mm.

| Design | Printed parts | Weight | Closed size (mm) | Also needed |
|---|---|---|---|---|
| Spacer ring | `1-spacer-ring` | 45 g | 151 × 125 × 38 | 2 flat silicone bands, 12 mm wide |
| Snap-on lids | `4-lid-left`, `4-lid-right` | 2 × 51 g | 150 × 125 × 23 each half | — |
| Hinged clamshell | `5-tray-left`, `5-tray-right` | 80 g | 162 × 125 × 41 | 4 magnets, a 2 mm steel rod, glue |

The print files are in `out/print/`, as STL and 3MF. The comparison page with renders and cross-sections is `out/concepts.html`.

## Ordering the prints

- **Process and material:** MJF (HP Multi Jet Fusion) in PA12 nylon. Grey is the default; dyed black looks better and hides scuffs. SLS PA12 works too. Avoid resin, which is brittle for the click tabs, and FDM, which is too coarse for the 0.5 mm fits.
- **Services:** JLC3DP, PCBWay or Craftcloud. Upload the STL files and the quote is instant. No supports or orientation settings are needed for MJF.
- **Tolerances:** walls clear the keyboard case by 0.5 mm, and the click beads overlap the case's chamfers by 0.35–0.5 mm. Standard MJF accuracy is fine; no tight-tolerance option is needed.

## Hardware for the clamshell

- **Magnets:** 4 neodymium discs, 8 × 2 mm, N52, axially magnetised. Glue them into the pockets with superglue or epoxy.
- **Getting the polarity right:**
  1. Stick the magnets together in two pairs and mark the outward faces.
  2. Glue one magnet of each pair into the left tray and its partner into the matching pocket of the right tray, so that each pair attracts when the case closes.
- **Hinge pin:** a 2 mm stainless steel rod, cut to 84 mm (bought as 100 mm). A 2 mm carbon-fibre rod also works and cuts with a knife. Push it through the knuckles from either end:
  - the left tray's knuckles hold it tight;
  - the right tray's knuckles turn freely on it;
  - if the tight holes come out undersized, open them with a 2 mm drill bit by hand.

## Straps for the spacer ring

Two flat silicone bands about 12 mm wide, with a relaxed circumference of about 230–260 mm. Each sits between a pair of ridges on the ring and runs across both case bottoms.

## Regenerating

```
uv run python designs/build.py    # print files + fit checks
uv run python designs/render.py   # renders for the page
uv run python concepts/render.py  # the five original concepts
```

Model sources: the bottom case and plate come from [PandaKBLab/sofle-j-keyboard-case](https://github.com/PandaKBLab/sofle-j-keyboard-case) (CC BY-NC-SA 4.0), cloned to `~/projects/external/`.
