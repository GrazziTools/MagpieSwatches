# Changelog

Development versions. The first public release will be 1.0.0.

## 0.14.0

- **The plate size picker moved to the top of the main panel, and now
  stays visibly lit on whichever size was last applied** -- the same
  segmented-toggle mechanism as the Hook/Round switch (an `EnumProperty`
  drawn with `expand=True`), not the stateless operator buttons introduced
  in 0.11.0.
- **This reverses the 0.11.0 decision on purpose.** The reasoning then was
  that an enum would silently claim a size no longer true after Width was
  edited by hand -- still correct, but using it in practice showed the
  opposite problem was worse: a plain button never shows which size is
  active at all, so there was no way to glance at the panel and tell. The
  toggle shows the LAST size applied, not a live match against the actual
  plate dimensions -- editing Width or Height afterwards does not change
  it back, and the field's own tooltip says so.
- **`MAGPIESWATCHES_OT_plate_preset` is gone.** The `plate_size` property's
  own update callback does the same write (dimensions, bottom margin, all
  three text sizes together) that the operator used to.
- **The "24 x 24 x 2.4 mm" readout under Add Swatch is gone from the
  panel.** It duplicated what the new size toggle already shows for two of
  its three numbers; the third (finished thickness, including relief)
  still appears in the status bar after every Generate, just not pinned to
  the panel.

## 0.13.1

Second of two refactor passes toward 1.0.0 (see
`docs/decisions/PLANO-v1.0.0.md`). Pure cleanup, no behaviour change --
`tests\run_all.ps1` gives the identical 16/16 result before and after.

- **Comments that no longer matched the code, fixed:** two functions this
  add-on's own docstrings referenced (`thicken_for()`, `stroke_ratio()`)
  were removed in earlier versions and never updated out of the comments
  pointing at them; `engine/booleans.py` named the wrong pair of Blender
  4.2's boolean solvers (FAST/EXACT, not FLOAT/EXACT); the panel's stroke
  readout called the lettering "auto-thickened", which hasn't been true
  since synthetic bolding was rejected (see `engine/text.py`'s own "WHY
  THERE IS NO SYNTHETIC BOLD HERE").
- **Dead code removed:** `hook.hook_extent()` (no callers since 0.7.1),
  `scale.mm()` and `scale.MM` (no callers), the duplicate `MM` constant in
  `constants.py` (the same dead pair). `SwatchParams.font_path` -- the only
  place in the add-on that ever read a user-chosen file path, and the UI
  never set it -- is gone; `resolve_font()` now always resolves the bundled
  font.
- **`HookError` is now actually catchable.** It could be raised by the hook
  geometry but was not in the operator's exception list -- unreachable
  today only because validation happens to run first, which is an ordering
  fact, not a guarantee. Added to the same `except` as the other three
  build errors.
- **One duplicated calculation removed.** `engine/validate.py` was
  recomputing the hole/hook's offset position by hand, alongside
  `engine/swatch.py`'s own version of the same math. Both now call a single
  `plate.hole_position()`.
- **`_version()` no longer re-reads and re-parses `blender_manifest.toml`
  on every panel redraw** -- cached after the first read.
- **Planning documents moved** to `docs/decisions/` (`AJUSTES-*.md`,
  `IMPLEMENTATION_PLAN.md`, `PLANO-v1.0.0.md`), out of the repository root.

## 0.13.0

First of two refactor passes toward 1.0.0 (see `docs/decisions/PLANO-v1.0.0.md`), following
an external code review. This one changes behaviour on purpose; the next is
pure cleanup with an identical test gate before and after.

- **Fixed: `MIN_HOOK_SIZE` allowed a structurally unprintable hook.** The
  old floor (3.0 mm) let through a hook whose tongue -- the bead a nozzle
  has to lay down -- measured only 0.24 mm, roughly half the 0.45 mm
  minimum stroke this add-on enforces everywhere else. Raised to 5.75 mm,
  the smallest size whose tongue cannot fall under that floor. The shipped
  default (6.56 mm) does not change: it is now print-validated (both the
  24 mm and 35 mm plates came off the printer with a clean, working hook),
  which is stronger evidence than any theoretical measurement.
- **Fixed: the 35 mm preset's hook and hole are hardware sized for a
  keyring, not decoration that scales with the plate.** They now match the
  24 mm preset's sizes exactly, referencing the same constants. Confirmed
  by print test: the scaled hardware was the one part of the 35 mm swatch
  that looked wrong once built.
- **Fixed: `difference()` accepted a boolean result that changed shape but
  not volume.** Only `union()` used to verify its result geometrically;
  `difference()` accepted anything whose vertex/polygon count merely
  differed from the input, which is not the same thing as material
  actually having been removed. Now checks volume loss directly, covering
  every use of `difference()` (the round hole, the hook, and deboss) at
  the one place they all go through.
- **Fixed: Reset to Defaults could leave the panel showing an inconsistent
  readout.** `last_report`, `last_warning`, `last_stroke` and `last_shrunk`
  describe one build together and are cleared together everywhere else;
  Reset used to keep only two of the four, so a Reset after a Generate
  could leave a report on screen with no stroke or shrink figure next to
  it. All four are now kept together.

## 0.12.0

- **New: an adjustable bottom margin**, and the 35 x 35 preset now uses
  3.0 mm of it against the 24 x 24's 1.5 mm. At 1.5 mm the lettering sat
  1.5 mm off the bottom edge with 8.37 mm of clear space above it -- badly
  bottom-heavy on a plate that size. MEASURED, 3.0 mm puts the ratio of
  bottom border to space-above at 1:2.3, against the small plate's own
  1:2.6.
- Only the BOTTOM margin is adjustable, and that is deliberate. The left
  and right margins feed the usable text width, so widening them takes room
  straight out of the lettering: MEASURED on the 35 mm preset, raising all
  four margins to 2.5 mm auto-shrinks the Color line and 3.0 mm shrinks
  Type as well. Raising only the bottom moves the block and changes nothing
  about its width -- confirmed identical to four decimal places.
- The 24 x 24 plate is unchanged: its bottom margin is still the same 1.5 mm
  every other side uses, referenced from the one constant.

## 0.11.1

- **The 35 x 35 preset now uses the same 3.0 mm corner radius as the 24 x 24
  one**, instead of a proportionally scaled 4.4 mm. A corner is a corner:
  the scaled version read as a different product rather than a bigger
  version of the same one. Both presets reference the one constant, so they
  cannot drift apart on it again.

## 0.11.0

- **New: a 35 x 35 mm plate preset**, alongside the shipped 24 x 24. Two
  buttons at the top of Adjust's Plate section apply width, height, corner
  radius, hole/hook size and all three text sizes together. Width and
  height were already free fields -- a 35 mm plate always built -- but the
  24 mm-calibrated numbers on it left the lettering looking stranded:
  MEASURED, text filling 65.3% of the width instead of 24's 88.1%, and
  40.8% of unused vertical headroom instead of 14.5%.
- The 35 mm text sizes (3.4 / 4.2 / 3.6 mm) are NOT the 24 mm set scaled by
  35/24 -- that multiplication (3.5 / 4.4 / 3.8) overflows the usable width
  and auto-shrinks an ordinary colour name. 3.4/4.2/3.6 is the largest set
  that does not.
- The bigger plate is not just proportionally nicer -- it prints names the
  24 mm one cannot. MEASURED with "Cinza Chumbo" (12 characters, the
  longest realistic colour name): the thinnest stroke comes out at 0.437 mm
  on the 24 mm preset, under the 0.45 mm a 0.4 mm nozzle can lay down, and
  0.666 mm on the 35 mm preset, comfortably above it.
- A button, not a size dropdown: an enum would have to silently flip to
  some "Custom" state the moment Width was edited by hand afterwards.
  Every field this preset touches stays a free, ordinary field -- the
  preset only sets a starting point.
- Plate thickness is not part of either preset (see docs/decisions/AJUSTES-0.11.0.md);
  it's a printing decision, not a size proportion.

## 0.10.0

- **Fixed: the auto-shrink notice could hide the printable-stroke warning.**
  Only the first actionable note reached the panel's warning slot, and
  "Color auto-shrunk to fit the plate" was appended before "thinnest stroke
  ... is under 0.45 mm" -- so a colour name long enough to trigger both (a
  case the shipped defaults hit on ordinary names, e.g. "Cinza Chumbo" on a
  24 mm plate, measured at a 0.44 mm stroke) reported the cosmetic note and
  hid the one that actually mattered. Auto-shrink is designed behaviour, not
  a problem, so it is no longer actionable at all: it now shows as its own
  parenthesised readout next to the thinnest-stroke figure, and the stroke
  warning gets the panel's warning slot to itself.
- **Panel reorganised again**, following from the 0.9.0 cards: the text card
  now ends at Generate, and a new card below it holds whatever there is to
  know about the build that just happened -- the printable-stroke warning
  (if any), the deboss/ironing note, and the Blender-4.2-solver note. It
  only appears when it has something to say.
- **The "scene is not in mm" notice is now its own card** in Adjust, instead
  of sitting loose under Text size, and **Reset to Defaults moved below it**.
- **Removed: "Use 3D cursor".** The swatch now always lands at the world
  origin. Nothing else in the add-on depended on it; a .blend saved with the
  old setting still opens fine, Blender just ignores the unused value.

## 0.9.0

- **New: Export FBX**, alongside Export STL. Unlike STL, FBX records units,
  and its exporter applies the scene's own unit scale by default -- MEASURED:
  a metric-default scene (1 unit = 1 m, Blender's own default) produces an
  FBX 1000x too large unless something compensates. The new operator
  compensates on its own, so the file is the right physical size whichever
  way the scene's units happen to be set, with no requirement to fix them
  first. "Set Scene to Millimetres" is unaffected by this and still there,
  now purely cosmetic for FBX -- it only changes what Blender's own UI reads.
- **New: hole/hook position offset.** Two new fields under Adjust, Offset X
  and Offset Y, nudge the hole or hook away from its default top-left
  corner. X is free, as long as the opening stays inside the plate; Y is
  capped at the plate's own vertical middle -- the text block owns the lower
  half, so the hole cannot cross into it. A push past either limit is
  refused with an error naming the HOLE, not the "text is too tall" message
  that would otherwise misattribute the problem.
- **Panel reorganised into three cards**, matching the actual workflow: Add
  Swatch on its own, then the text fields through Generate, then export.
  Each build's size and thinnest-stroke readouts moved to sit next to the
  action that produced them, instead of trailing behind Export at the
  bottom.
- The "disable ironing" and Blender-4.2-solver hints now wrap onto multiple
  lines instead of truncating in the narrow N-panel.
- The "scene is not in mm" notice moved out of the main panel and into the
  bottom of Adjust, and its wording changed: with Export FBX now
  self-compensating, the old claim that a non-mm scene made FBX exports
  oversized stopped being true. It is now correctly described as cosmetic.

## 0.8.0

- **The hook is now a traced outline** baked into `engine/hook_shape.py`,
  following the community-standard keyring channel (see that module). It
  replaces the parametric Archimedean spiral of 0.7.0, which was never
  going to match: the intended shape's tongue TAPERS to a point, and a
  constant-width spiral channel cannot do that, because its two walls stay
  parallel by construction. Measured against the reference part, the traced
  outline reproduces its proportion exactly (0.7673 wide-to-tall,
  5.03 x 6.56 mm).
- The outline is traced once, at development time -- no vector file is
  imported at runtime. The add-on still declares **zero permissions** and
  does not depend on Blender's SVG importer being enabled on the user's
  machine.
- **Hook settings collapse to a single "Hook size"** control. Seat diameter,
  channel width, coil thickness and turns are gone: those knobs only existed
  because the shape was being guessed at, and with the real drawing there is
  nothing left for them to control.
- Cutting the hook is now one boolean against one solid, rather than a
  cylinder and a channel subtracted separately.

## 0.7.1

- **Fixed: "The text is N mm too tall for the plate" when generating with the
  Hook style.** A regression in 0.7.0. The hook was measured as if it were a
  circle of its own circumscribed radius, in every direction -- but a spiral
  is not radially symmetric (7.8 mm wide against 6.7 mm tall at the shipped
  defaults, descending 3.92 mm while its circumscribed radius is 4.50). That
  cost the layout twice: it pushed the hook further from the plate corner
  than it needed to be, then capped the text lower than the hook actually
  reached. Text room dropped from 6.10 mm under the old round hole to
  0.60 mm -- so tight that text only 0.3 mm larger than default failed
  outright. Now measured per direction, restoring it to 2.28 mm, and the
  hook's wall margin is 1.5 mm (measured off the reference part) rather than
  the 2.0 mm previously assumed by analogy with the round hole.
- Added a test covering the SHIPPED defaults specifically, plus headroom
  above them. The 0.7.0 suite stayed green through this because every swatch
  test used fixture values that predate the recalibrated text sizes.

## 0.7.0

- **Corner radius default raised to 3.0 mm** (was 2.0), measured off a
  reference part.
- **New hanging-hole style: Hook.** An open Archimedean-spiral channel with a
  seat at its centre, alongside the existing plain Round hole (`Style`
  switch under Adjust). Thread a closed keyring in through the spiral's open
  end and turn the swatch; the ring walks down the channel to the seat --
  no need to open the ring at all. This is an ORIGINAL construction from the
  functional principle, not a copy of any reference part's contour. Hook is
  now the default; Round remains fully supported and unchanged.
- Hook geometry is parametric: seat diameter, channel width, coil thickness
  and turns are all adjustable, each validated against the 0.4 mm nozzle's
  printable stroke before anything is built.
- The text ceiling (how tall the lettering may be before it would run into
  the opening) now accounts for the hook's real reach, which is
  considerably larger than a round hole's radius.

## 0.6.0

- **Export STL now lets you choose the filename.** The operator used to
  declare only a `directory` property, which makes Blender's file browser
  open as a bare folder picker with no name field -- the exported file was
  always named after the object ("Sunlu - SWATCH.stl") with no way to
  change it. Confirmed against Blender's own STL exporter, which declares
  `filepath` (not `directory`) for exactly this reason. Switched to
  `filepath`, so the browser now shows an editable name field, pre-filled
  with a suggested name built from the swatch's own fields (e.g.
  "Sunlu - PLA Matte - Marrom Cafe.stl") rather than the generic object
  name. A missing `.stl` extension is added automatically if the name field
  is edited down to nothing recognisable, and the browser now asks before
  overwriting an existing file.

## 0.5.0

- **Fixed uneven line spacing.** Lines used to stack by their own bounding
  box, so the visible gap between two lines shifted depending on what was
  typed on a THIRD, unrelated line -- an accent or a descender (g, j, p, q, y)
  anywhere in the swatch could pull the whole stack out of rhythm. Measured
  before the fix, default sizes: the gap between lines 1 and 2 read 1.070 mm
  with a plain third line and 1.300 mm with a descender in it, for the exact
  same first two lines. Lines now stack by CAP HEIGHT, so a gap is fixed by
  its own two neighbours and nothing else -- measured after the fix, that same
  gap holds at 0.9659 mm regardless of what the third line says.
- `LINE_GAP` default raised from 1.0 to **1.3 mm**, the largest gap measured
  across realistic content under the old stacking -- standardised on the
  roomiest spacing rather than the tightest, so a swatch with a descender
  does not read as more cramped than one without.
- **Add Plate renamed to Add Swatch** and moved to the top of the panel,
  above the text fields -- the button order now matches the workflow (add,
  write, generate).
- **Adjust panel:** the hanging hole moved into the Plate box, right after
  Corner Radius, instead of its own separate box.
- Removed the gap between the Emboss/Deboss switch and the Relief/Engrave
  field below it; tightened the gap between the Color field and the Mode
  section above it.

## 0.4.0

- **Bundled Liberation Sans Bold** (SIL OFL 1.1) and letter with it. Blender's
  built-in font is too light to print at swatch sizes: measured, its stem is
  14.4% of the cap height against Liberation Bold's 20.9%, and with it all
  three shipped defaults produced strokes under the 0.45 mm a 0.4 mm nozzle
  can lay down.
- **Text sizes are now cap heights in millimetres** -- the height of a capital
  letter, which is what calipers measure on the printed part -- rather than
  Blender's em size, whose relationship to visible letter height varies by
  font (Bfont 0.682 per em, Liberation Bold 0.488).
- Recalibrated defaults against real filament names on the 24 mm plate:
  Brand 2.4, Type 3.0, Color 2.6 mm; text margin 2.0 → 1.5 mm. Common names
  now fit at full size instead of auto-shrinking on almost every generate.
- The panel reports the **thinnest stroke** on the finished swatch and warns
  when it falls under 0.45 mm, instead of silently producing lettering too
  fine to print.

## 0.3.0

- Mounting hole moved to the **top-left** corner.
- Text is **left-aligned** and **anchored to the bottom margin**, so swatches
  with two and three lines share a baseline. With the hole above the text
  rather than beside it, lettering now gets the full plate width.
- Added a separate **Add Plate** button (the "add a part" tier) alongside
  Generate (the finished-piece tier), so the plate can be dropped in and
  looked at before committing to any lettering.
- Text that cannot fit above the bottom margin and below the hole is now
  refused with a clear message rather than running through the hole.

## 0.2.0

- **Generate is never disabled.** With no text at all it builds the blank
  plate, so the button works on the first click of a fresh install. Drops the
  earlier rule that all three fields empty was an error.

## 0.1.0

Initial build.

- Rounded plate (24 x 24 x 2 mm default, all dimensions adjustable) with an
  optional hanging hole in one corner.
- Three independent text fields (Brand / Type / Color), each with its own
  size, stacked and centred, empty fields skipped and the rest re-centred.
- Emboss (raised) or Deboss (recessed) lettering, selected per swatch.
- Auto-shrink for a line that overflows the plate width, down to a printable
  floor; a clear, field-named error if it still doesn't fit.
- Per-mode validation: emboss relief clamped to 0.3-0.5 mm, deboss engrave
  depth checked against the plate's remaining material.
- Regenerating replaces the previous swatch instead of leaving orphans.
- STL export, one file per swatch.
- No network calls, no telemetry, zero third-party Python dependencies.
- Validated on Blender 4.2 LTS and 5.2 LTS.
