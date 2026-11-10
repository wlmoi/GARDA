# Chip art: SENO in Metal4

## Current state: the SENO pose

The art in the published GDS is the SENO mascot pose from `Calvin.png`
(a cut-out on a transparent background), in the bare-oxide box of the
`CALVIN_UP` variant described below: x 1634.9 to 1670.9, y 464.0 to 511.4
(36 x 47.4 um), 1192 Metal4 pixels of 0.6 um as 212 rectangles, 429 um2.
It was made with the `figure` mode of `tools/chip_art.py`:

```
python tools/chip_art.py --image Calvin.png --mode figure --edge 3 \
    --box 1634.9 464.0 1670.9 511.4 --nofill all --out macros/CALVIN_UP
```

- **`--mode figure`** reads the PNG's alpha channel: the opaque silhouette
  becomes metal, the figure is cropped to its opaque extent and fitted to
  the box with its aspect ratio kept (`--margin` empty pixels inside every
  edge), and the image is posterised into `--edge` flat colour regions whose
  boundaries become one-pixel slots (face, glasses, jacket, sarong).  A 2x2
  opening removes specks and spurs; the same Metal4 self-checks run.
  `plate` / `ink` (a round avatar on a dark background) are unchanged.
- **Into the GDS.** The new cell replaced the contents of
  `tt_um_pettit_calvin` in both GDS views, which is what `Project.ChipArt`
  does after stream-out, so placement, routing, DEF and netlist are
  untouched.  Checked: a flattened per-layer XOR outside the art cell is
  empty on every layer, the full-chip XOR differs only on Metal4 inside the
  box, and the art keeps >= 0.6 um from every other Metal4 shape.  The
  next `make harden-tt` with `config_merged_art_up.json` regenerates the
  same art from `macros/CALVIN_UP/art.json`.

## A larger SENO (not done yet)

At 36 x 47 um the picture is visible only when zoomed in.  Seeing it on a
whole-tile render needs roughly 160 um of height.  The current layout has
no such free area: only 19.7 % of Metal4 is free (0.6 um clearance), in
thin slivers between the PDN stripes and signal routes, 2 to 6 % in the
PRISM channel.  So a large picture needs a new hardening run with the area
reserved up front, the `CALVIN_UP` way:

1. Pick a box in a standard-cell channel away from the tile pins and the
   CFGMEM route-through pins, e.g. part of the 166 um gap between the
   bank-B CFGMEMs (y 90.72 to 257.04), and snap its x edges to the
   44.96 um stripe grid so the stripes frame the figure.
2. `python tools/chip_art.py --image Calvin.png --mode figure --edge 4
   --box <x0 y0 x1 y1> --nofill all --cell tt_um_seno_art --out macros/SENO_BIG`
3. A copy of `src/config_merged_art_up.json` with `CHIP_ART_JSON` pointing
   at `macros/SENO_BIG/art.json`, the three `ROUTING_OBSTRUCTIONS`
   (Metal2 to Metal4) moved to the new box, and `CHIP_ART_CUT_ROWS` on.
4. `make harden-tt` (Linux or WSL with LibreLane), then accept the run only
   if DRC, LVS and antenna stay at zero and timing does not get worse; a
   larger keep-out costs placement area in a design at 70 % utilization.

# Chip art: Calvin in Metal4 (history)

The tile carries a Metal4-only picture in its upper-right corner: Calvin
(the author's avatar, `Calvin.png`), 36 x 57 um, in the channel between
two PDN stripe pairs over the right end of the top-right CFGMEM macro.
Nothing electrical: floating metal that the routers were kept off.

## How it is made

`tools/chip_art.py` turns a bitmap into a GDS cell on a pixel grid, with
the Metal4 rules met by construction (run inside the LibreLane nix shell):

```
python tools/chip_art.py --image Calvin.png \
    --box 1634.9 648.8 1670.9 705.5 --extent 1619.3 648.8 1686.9 705.5 \
    --clearance 0.6 --exclude 1662.61 634.47 1662.81 657.87 --out macros/CALVIN
```

- **Rendering.** The avatar's light disc becomes a metal plate and its ink
  strokes become slots in the plate, so under a microscope it reads as the
  avatar does: a bright disc with dark line art.  `--mode ink` draws the
  strokes as metal instead.
- **Pixels.** 0.6 um squares.  On that grid every width and every gap is a
  multiple of 0.6 um, which satisfies the sg13cmos5l Metal4 rules M4.a
  (width 0.20), M4.b (space / notch 0.21), M4.e (0.24 between lines wider
  than 0.39 um over a 1 um run) and M4.f (0.6 between lines wider than
  10 um over a 10 um run).  A clean-up pass fills every 2 x 2 checkerboard
  so no two metal pixels touch only at a corner (zero spacing to a
  checker).  The tool re-checks width, space, area and the wide-metal
  spacing on the merged shapes and refuses to write a cell that fails.
- **Extent and box.** `--extent` is where the whole image goes, `--box`
  the window actually drawn.  The disc is 57 um across but the channel
  between PDN pairs 9 and 10 is 36 um wide, so the disc is drawn larger
  than the window and clipped to it: the stripes frame the face instead
  of crossing it.  A two-pitch box put a stripe pair straight through the
  face; a disc that fits one channel was too coarse to read.
- **Keep-outs.** `--exclude` rectangles (die coordinates), grown by
  `--clearance`, are left empty: here the CFGMEM's route-through pin
  WROW[9] where it reaches into the window.  The box edges keep 0.6 um
  from the two stripe pairs.
- **Output.** `tt_um_pettit_calvin.gds` (Metal4 50/0 and Metal4.nofill
  50/23 over the box, so the chip-level fill leaves the dark areas
  alone; precheck lists both layers as valid), a LEF for the record,
  `art.json` for the flow step, `preview.png`.
- **Rectangles, not merged polygons.** The metal is written as one
  rectangle per horizontal run of pixels (392 of them).  A merged plate
  has holes (the eyes inside the face), and GDS can only write a polygon
  with holes as a boundary with cut lines, which visits the same vertices
  twice.  Tiny Tapeout's 3D viewer triangulates with CDT, which throws on
  such a polygon (an uncaught wasm exception, the viewer shows nothing),
  as the first version of this art demonstrated.  Rectangles have no
  holes; the DRC merges touching shapes before it checks, so it sees the
  same geometry.

## How it gets into the tile

The art is not a LibreLane macro.  A macro over the CFGMEM would overlap
a fixed macro, and its Metal4 obstruction would make pdngen cut the
stripes that cross it.  Instead:

1. `ROUTING_OBSTRUCTIONS` gets a Metal4 entry for the box (the
   `routing_obstruction` of art.json), so the tile's router never uses
   Metal4 there.  The CFGMEM pins under the box are reachable elsewhere
   (WROW[9] has a hundred other shapes) or from Metal3.
2. `Project.ChipArt` (librelane_plugin_prism_pdn.py), inserted with
   `"+Magic.WriteLEF": "Project.ChipArt"`, merges the cell into every GDS
   view after stream-out (GDS, KLAYOUT_GDS, MAG_GDS) at the die origin
   from art.json, and adds the box to the tile LEF as a Metal4 OBS so the
   Tiny Tapeout top-level router stays off it as well.  It runs before the
   KLayout DRC, which therefore checks the art in place.
3. Nothing changes in the ODB, DEF or netlist: LVS does not see the art.

`src/config_merged_art.json` is the vga3_anchor recipe with those three
additions and the registers anchored to vga3_anchor's own placement
(`tools/placements/vga3_anchor_placed_seq.json`).

## The bare-oxide variant: cut the rows under the picture

`macros/CALVIN_UP` and `src/config_merged_art_up.json` (runs/art_up) put
the same picture in the standard-cell channel between the second-row and
top-row CFGMEMs, x 1634.9 to 1670.9, y 464.0 to 511.4 (10 um above the
lower macro's top-face pins), and empty the box on every layer so the
Metal4 lies on bare oxide instead of on logic:

- `Project.ArtKeepout` (`"+OpenROAD.CutRows"`, `CHIP_ART_CUT_ROWS`) cuts
  the standard-cell rows under the box before the PDN is made
  (odb_art_keepout.py: 14 rows split into left and right segments on the
  site grid).  No cell, filler or decap can ever be placed there, and no
  Metal1 rails are drawn there, since the rails follow the rows; the row
  segments on each side still meet a stripe pair.
- `ROUTING_OBSTRUCTIONS` on Metal2, Metal3 and Metal4 over the box keep
  the router out; `--nofill all` puts the fill-exclusion marker of every
  layer (Activ, GatPoly, Metal1 to Metal4) over the box for the chip-level
  fill.
- One anchored register sat in the box and was snapped to the nearest row
  segment by the anchor step.

Cost, measured on the same anchored skeleton: global placement inflated
19.7 % instead of 15.4 %, global routing overflow 20716 instead of 19571
(the detours, all on Metal3), 0.9 % more wire, 259 Metal2 and 159 Metal3
segments displaced.  Sign-off: DRT 0 at pass 57 plus two antenna rounds,
KLayout 0 on the full deck, LVS 0, antenna 0, typ setup +0.360 (the art
run: +0.322), hold +0.223, IR drop unchanged.  Note that the post-GRT
timing repair's table ended at -2.1 ns with 503 endpoints for this run:
that table tracks the slow corner, not the typ sign-off, and is not a
reason to kill a run.

## The corner, for the record

Die 1724.16 x 710.64 um.  The top-right CFGMEM_IHP16 sits at x 1346.39
to 1686.71, y 619.92 to 706.86.  Metal4 PDN pairs (VPWR 2.1 um, 3.52 um
gap, VGND 2.1 um) repeat every 44.96 um: pair 9 at 1626.54 to 1634.26,
pair 10 at 1671.50 to 1679.22, then the irregular last pair at 1703.91
(VGND) and 1716.46 (VPWR).  The CFGMEM's own Metal4 is its data-pin
stubs along the bottom edge (y below 629.3) and the route-through pin
WROW[9], 133 shapes spread over the macro, four of them near the window.
