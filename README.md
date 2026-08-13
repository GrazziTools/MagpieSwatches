# Magpie Swatches

A Blender add-on that generates a printable filament sample swatch: a small
plate carrying the filament's **brand**, **type**, and **color name** as
raised (emboss) or recessed (deboss) lettering. Fill in up to three fields,
click Generate, export the STL, print it.

Swatches come out in the **community-standard format** -- a 24 x 24 mm plate
with the usual keyring channel -- so they hang on the same ring and sit in
the same box as the ones you already have.

Free, distributed under GPL-3.0-or-later.

## Install

1. Download the latest `magpie_swatches-X.Y.Z.zip` from
   [Releases](../../releases).
2. In Blender: **Edit ▸ Preferences ▸ Get Extensions ▸** the `⌄` menu top
   right **▸ Install from Disk**, and pick the zip.
3. The **Magpie Swatches** tab appears in the 3D Viewport's N-panel.

Requires **Blender 4.2 LTS** or newer. No other add-ons or Python packages
needed.

## Use

1. Open the **Magpie Swatches** tab in the N-panel (`N` in the 3D Viewport).
2. Click **Generate**. With nothing typed you get the blank plate -- the
   quickest way to see the size in your scene before committing to anything.
3. Type into any of **Brand**, **Type**, **Color**. Any of them can stay
   empty; the remaining lines re-centre on the plate.
4. Pick **Emboss** (raised) or **Deboss** (recessed).
5. Click **Generate** again -- it replaces the previous swatch rather than
   stacking up copies.
6. Click **Export STL** (for slicing) or **Export FBX** (for everything
   else) and pick a folder.

Everything under **Adjust** (plate size, corner radius, the hanging hole,
per-field text size) has a sensible default and only needs opening if you
want a different size swatch.

Regenerating replaces the previous swatch rather than piling up extra objects
in the scene, so it's safe to tweak a field and hit Generate again.

### Plate size

**24 x 24 mm / 35 x 35 mm** at the top of the panel picks between the two
calibrated sizes -- it applies a whole set at once (dimensions, bottom
margin, and all three text sizes), not just the plate itself, since text
sized for 24 mm looks stranded on a 35 mm plate. Every field it sets stays
free to edit afterwards under Adjust; it's a starting point, not a mode.

**24 x 24 mm is the community standard** -- the size everyone else's
swatches are, so a new one drops straight into an existing collection.

**35 x 35 mm is this add-on's own proposal**, for anyone who finds the
standard one cramped: it is easier to hold and to read across a drawer, and
it is not only a matter of taste -- the extra width is what lets a long
colour name print at all. MEASURED with "Cinza Chumbo" (12 characters, about
the longest realistic name): the thinnest stroke lands at 0.437 mm on the
24 mm plate, under the 0.45 mm a 0.4 mm nozzle can lay down, and at
0.666 mm on the 35 mm one.

The toggle stays lit on whichever size was applied last -- it does NOT
track the actual Width/Height fields, so editing those by hand under
Adjust afterwards leaves it pointing at a size that no longer matches.
Width and height are always free fields regardless of the toggle -- any
size builds.

Corner radius, and the hanging hole/hook, stay the SAME size on both
presets rather than scaling up. They're hardware, not decoration -- a
keyring doesn't get bigger just because the plate around it did.

The 35 mm preset also sits its lettering 3.0 mm off the bottom edge rather
than 1.5 mm, since a bigger plate with the small one's margin looks
bottom-heavy. **Bottom margin** under Adjust ▸ Text size adjusts that on any
plate. Only the bottom is adjustable: the side margins decide how much width
the lettering has, so widening them would shrink the text rather than frame
it.

35 mm is more than a bigger label: it fits colour names that don't fit on
24 mm at all. The longest realistic name ("Cinza Chumbo") comes out with a
0.437 mm stroke on the 24 mm preset -- under what a 0.4 mm nozzle can print
-- and 0.666 mm on the 35 mm one. If a name keeps triggering the thin-stroke
warning, the fix is the bigger plate, not a smaller font.

### A note on units

The swatch is built at **1 Blender unit = 1 millimetre**. Both exports come
out at the correct physical size no matter what your scene's unit settings
say:

- **Export STL** carries no unit at all -- a slicer reads a 24 mm plate as
  24 mm, always. Nothing needs converting.
- **Export FBX** *does* record units, and its exporter applies the scene's
  own unit scale by default -- so Export FBX compensates for that on its
  own, and the file comes out at the right physical size whichever way the
  scene happens to be set.

Blender's own default is 1 unit = 1 metre, so until you change it the N-panel
will *label* the swatch "24 m" -- a display label only, and by this point a
purely cosmetic one, since neither export is affected by it. If it bothers
you, the "Adjust" panel offers a one-click **Set Scene to Millimetres** down
at the bottom. That button changes only the scene's unit settings -- nothing
moves and nothing is resized.

### If a line is too long

Text that doesn't fit the plate shrinks automatically. If it still doesn't
fit once it's as small as the nozzle can reliably print, Generate refuses and
names the field and the character count, rather than silently clipping text
off the plate.

## The hanging hole

Under **Adjust**, the hanging opening comes in two styles:

- **Hook** (default) -- an open spiral channel with a small seat at its
  centre. Thread a *closed* keyring in through the channel's open outer end,
  then turn the swatch; the ring walks down the spiral to the seat and stays
  put. No need to open the ring at all.
- **Round** -- a plain circular hole. Needs a ring that is already open (a
  split ring, or one you open yourself) to thread through it.

The hook's shape is fixed artwork; the only setting is how big it is. Shrink
it too far and its own tongue becomes too thin for a nozzle to print
reliably -- the add-on refuses with a named error rather than shipping a
swatch whose opening silently doesn't work. The round hole's diameter is
adjustable in the same way.

Under Adjust, **Offset X / Offset Y** nudge the hole or hook away from its
default top-left corner. X is free, as long as the opening stays inside the
plate; Y is capped at the plate's own vertical middle, since the text below
it needs that half for itself. Pushing past either limit is refused with an
error naming the hole -- not the text.

## Deboss and ironing

If your slicer irons the top surface (common for a smooth finish on the last
layer), it will pass directly over debossed text and smear the cavity edges,
degrading legibility. Either disable ironing for a deboss swatch, or use
Emboss instead -- raised text isn't affected.

## Text size and the font

**Sizes are cap heights in millimetres** -- the height of a capital letter,
which is what you'd measure on the printed part with calipers. They are not
"point sizes"; a 3 mm Type line puts a 3 mm capital T on the plate.

The add-on bundles **Liberation Sans Bold** and letters with it. That is not
a style preference, it's a printing requirement: Blender's built-in font is
too light at these sizes. Measured, its stem is 14.4% of the cap height
against Liberation Bold's 20.9%, so at any given letter height the bundled
font lays down about 45% more material. With Blender's own font, all three
shipped defaults produced strokes under the 0.45 mm a 0.4 mm nozzle can
print; with this one they come out at 0.5 mm and up.

After each Generate the panel reports the **thinnest stroke** on the swatch,
and separately notes which field, if any, auto-shrunk to fit. Only the
stroke figure ever becomes a warning -- auto-shrinking is normal and expected
on longer names, not a problem by itself, so it stays a plain readout instead
of crowding out the one message that actually needs your attention. If the
stroke drops under 0.45 mm -- which a very long colour name on a small plate
can still do -- the panel says so. The swatch still builds and exports; the
warning is there so you can decide, since you know your printer. In emboss a
thin stroke usually prints fatter than modelled; in deboss the nozzle can't
enter the cavity and the lettering may not appear at all.

The defaults (Brand 2.4, Type 3.0, Color 2.6 mm) are calibrated against real
filament names on the default 24 mm plate, so common ones fit at full size.
**The real test is a printed part** -- if detail drops out or fuses on your
printer, raise the sizes or the plate.

There is no custom font picker (see *Security* below for why) -- the bundled
bold is the only font this add-on ever letters with.

## Security & privacy

- **No network calls.** Nothing in this add-on talks to the internet -- no
  telemetry, no update checks, no analytics.
- **No collection of system information.** No usernames, file paths outside
  what you explicitly export to, hardware IDs, or environment variables are
  read, logged, or embedded in the generated mesh.
- **No reading of files you did not choose.** The only font used is the one
  bundled with the add-on; nothing scans your filesystem or reads a font (or
  anything else) from a path you did not explicitly pick in an export dialog.
- **No writing to disk** other than the STL or FBX file you explicitly ask
  Export to write, to the folder you pick.
- **Minimal permissions.** The extension manifest declares none.
- **No `eval`, `exec`, or dynamic code execution.** The three text fields are
  strings used to build a text mesh -- never interpreted as code.
- **Zero third-party dependencies.** Everything is built on Blender's own
  `bpy`/`bmesh`/`mathutils`.

## Non-goals (v1)

Deliberately out of scope, to keep this add-on doing one thing well:

- Temperature/settings test features (thickness steps, bridging tabs,
  overhang fins)
- Batch generation from a CSV or filament library
- Material/color preview assignment
- Any cloud sync or shared swatch database
- Custom font browsing (see *Text size and the font* above)

## Development

```
magpie_swatches/          the add-on package
  blender_manifest.toml
  constants.py             branding + tuning constants, single source of truth
  __init__.py               registration only
  engine/                  pure geometry -- no bpy.context, headless-testable
  ui/                      panels, properties, operators -- no geometry maths
tests/                     headless smoke tests (see below)
build.py                   packages a release zip from a clean tag checkout
```

### Running the tests

Each `tests/test_*.py` is a standalone script that runs inside Blender:

```
blender --background --factory-startup --python tests/test_plate.py
```

`tests/run_all.ps1` runs every test file against both Blender 4.2 and 5.2 and
reports PASS/FAIL per file -- this is the release gate:

```
powershell -File tests/run_all.ps1
```

Blender exits 0 even when a test script raises, so the runner greps stdout
and stderr for `Traceback` rather than trusting the exit code alone.

### License

GPL-3.0-or-later. See [LICENSE](LICENSE).

**Hook shape.** The hanging hook follows the keyring-channel pattern in
common use across the 3D printing community for filament swatches,
popularised by Bambu Lab. It is not claimed as an original design. The
outline is traced into `magpie_swatches/engine/hook_shape.py` as plain
coordinate data.

**Bundled font.** `magpie_swatches/assets/LiberationSans-Bold.ttf` is
Liberation Sans Bold, © 2012 Red Hat, Inc. with Reserved Font Name
"Liberation", and digitized data © 2010 Google Corporation with Reserved Font
Name "Arimo". It is licensed under the SIL Open Font License 1.1, redistributed
here unmodified; the full licence text ships alongside it as
`LiberationSans-Bold.LICENSE.txt`.
