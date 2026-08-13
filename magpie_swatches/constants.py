"""Single source of truth for branding + tuning constants.

Rebranding the whole add-on = change the strings below and the folder / manifest
id. Everything user-visible (N-panel tab, operator namespace, generated object
names) derives from here.

Numbers are grouped by the decision they encode, and every non-obvious one
carries the reason it holds the value it does -- these are print-physics facts,
not free parameters to nudge.
"""

# --- Branding -------------------------------------------------------------- #
ADDON_ID = "magpie_swatches"   # internal id / folder / manifest id
BRAND = "Magpie Swatches"      # N-panel tab + panel title (user-facing name)
AUTHOR = "Gustavo Grazziano"   # shown in the About section
OP = "magpie_swatches"         # operator namespace, e.g. magpie_swatches.generate
OBJ = "MS_"                    # internal prefix (temp names before rename)
TYPE_KEY = "ms_type"           # invisible tag on generated objects, used to find
                               # them regardless of their user-facing name
TYPE_SWATCH = "swatch"         # the one part this add-on makes

# --- Working scale --------------------------------------------------------- #
# 1 scene unit = 1 mm, family-wide -- see engine/scale.py for why the swatch
# is built directly in millimetres and never rescaled: the short version is
# that it keeps every boolean running on 24 mm plates and 0.45 mm strokes
# instead of the sub-millimetre range where the exact solver starts
# shedding faces.

# --- Plate ----------------------------------------------------------------- #
# Measured off a reference part. All four are user-adjustable; these are the
# defaults, not hard-coded dimensions.
DEFAULT_PLATE_W = 24.0         # mm, across
DEFAULT_PLATE_H = 24.0         # mm, tall
DEFAULT_PLATE_THICK = 2.0      # mm
# 3.0, not 2.0 -- measured on the reference (two independent methods agreed
# to within 0.04 mm). No edge chamfer either: the reference is a plain prism,
# same top and bottom outline, which is what create_plate() already builds.
DEFAULT_CORNER_RADIUS = 3.0    # mm, all four corners
CORNER_SEGMENTS = 16           # arc segments per rounded corner

# --- Mounting hole --------------------------------------------------------- #
# A keyring / hangtag opening in one corner, in one of two styles -- see
# HOLE_ROUND / HOLE_HOOK below. Centred HOLE_INSET from each of the two
# nearest edges, so it clears the corner radius and leaves a wall around it.
DEFAULT_HOLE = True
DEFAULT_HOLE_DIAMETER = 3.5    # mm
HOLE_INSET = 3.75             # mm, centre distance from each of the two edges
HOLE_SEGMENTS = 32            # cylinder facets

# A plain round through-hole (ROUND) needs a ring already open to thread
# through it. A spiral hook (HOOK) is a channel you feed a CLOSED keyring
# into from its open outer end, then turn the swatch to walk the ring down to
# a seat at the centre -- no need to open the ring at all.
#
# EnumProperty, not a second boolean alongside `hole`: it leaves room for a
# third style later without breaking any .blend saved against this version --
# same reasoning as `mode`. Both styles stay fully supported; HOOK is only
# the default, not a replacement.
HOLE_ROUND = 'ROUND'
HOLE_HOOK = 'HOOK'
DEFAULT_HOLE_STYLE = HOLE_HOOK

# --- Hook style -------------------------------------------------------------#
# The hook's SHAPE is fixed data, baked into engine/hook_shape.py as a
# normalised outline -- so the only thing left to choose here is how big it
# is. Everything else the earlier parametric version exposed (seat diameter,
# channel width, coil thickness, turns) is gone with it: those knobs existed
# only because the shape was being GUESSED at, and with the real outline in
# hand they have nothing left to control.
#
# 6.56 mm is the height measured on the reference part, which the outline
# reproduces exactly in proportion (0.7673 wide-to-tall, so 5.03 mm across).
# PRINT-VALIDATED (11/08/2026): both shipped presets -- this size on the
# 24 mm plate, and again on the 35 mm one -- came off the printer with a
# clean, working channel. Not a theoretical margin; a physical part.
DEFAULT_HOOK_SIZE = 6.56       # mm, hook height

# The floor is set by the TONGUE (the material the nozzle has to lay down),
# not the channel (the void the ring travels through) -- they are different
# physics and do not share a threshold. MEASURED on the baked outline
# (engine/hook_shape.py's OUTLINE, narrowest point-to-point span at each
# candidate size): the tongue reaches MIN_STROKE (0.45 mm, the thinnest bead
# a 0.4 mm nozzle can print) at hook_size = 5.73 mm, so 5.75 is the smallest
# size that cannot be structurally unprintable.
#
# The channel is a SEPARATE, still-open question: at this floor it measures
# only ~0.20 mm, well under the 0.40 mm a nozzle can open, and there is no
# hook_size below ~9.1 mm where the channel alone clears that -- yet the
# shipped 6.56 mm default (channel ~0.29 mm) prints and opens fine (see
# above). That gap between the theoretical channel threshold and what
# actually printed is real and unexplained; it is not grounds to warn on
# every default-sized hook, which would be noise on the common case rather
# than a signal on a real one. If a print test ever shows the channel
# failing to open at a specific size, that changes DEFAULT_HOOK_SIZE, not
# this floor -- the floor's job is only to block what the material itself
# cannot form.
MIN_HOOK_SIZE = 5.75           # mm

# Nudges the hole/hook away from its derived top-left position, for anyone
# who wants it somewhere else. No default nudge -- (0, 0) reproduces exactly
# the position hole_center() alone would give. X is free (only ever has to
# clear the plate edges); Y is capped at the plate's own vertical middle in
# engine/validate.py, because the text block owns the lower half.
DEFAULT_HOLE_OFFSET = 0.0      # mm

# --- Text fields ----------------------------------------------------------- #
# Three independent lines, each with its own size. Type is the visual anchor and
# so the largest, Brand the smallest -- the brief's hierarchy.
#
# SIZES ARE CAP HEIGHTS IN MILLIMETRES: the height of a capital letter, which
# is what a caliper measures on the printed part. NOT Blender's Curve.size,
# which is an em and includes room for ascenders and descenders that most
# strings never use -- see engine/text.py's metrics().
#
# CALIBRATED against real filament names on the default 24 mm plate rather
# than chosen for looks. MEASURED width per mm of cap height, bundled font:
#
#   "Sunlu"          3.90      "PLA Matte"     6.96      "Marrom Cafe"   8.74
#   "Bambu Lab"      7.76      "PLA Silk"      5.80      "Verde Oliva"   8.00
#   "Preto"          3.56                                "Cinza Chumbo" 10.06
#
# With 21 mm of usable width these defaults let the common names through at
# full size; only the longest colour names auto-shrink, and only slightly.
# The brief's original 3.0 / 4.5 / 3.5 were measured before the font was
# settled and, read as cap heights, overflow the plate on almost every real
# name -- every generate would have opened with a shrink warning.
DEFAULT_BRAND_SIZE = 2.4       # mm cap height, top line (smallest)
DEFAULT_TYPE_SIZE = 3.0        # mm cap height, middle line (largest)
DEFAULT_COLOR_SIZE = 2.6       # mm cap height, bottom line

# Gap between stacked CAP BANDS (see engine/text.py's build_label(), which
# anchors by cap band rather than by each line's own bbox specifically so this
# number means the same thing regardless of what is typed). Set to the LARGEST
# visible gap measured across realistic content at the old bbox-based
# stacking's nominal 1.0 mm: a plain third line showed 0.926 mm, an accented
# one 0.910 mm, one with a descender (g, j, p, q, y) 1.300 mm -- standardised
# on the roomiest of those rather than the tightest, since a swatch with a
# descender should not read as more cramped than one without.
LINE_GAP = 1.3                # mm of clear space between stacked cap bands
# 1.5 rather than 2.0: on a 24 mm plate every 0.5 mm of margin is 5% of the
# width the lettering has to work in, and that margin is what decides whether
# a 12-character colour name prints at a legible stroke or not.
TEXT_MARGIN = 1.5             # mm kept clear inside the plate edge, each side

# The BOTTOM margin alone, separated out because the text block is anchored
# to it (see engine/swatch.py's _anchor_label) and because it is the only
# one of the four that can be raised for free: left and right feed
# _text_box(), so widening them takes width straight out of the lettering
# and pushes it into the auto-shrink. MEASURED on the 35 mm preset: raising
# ALL margins to 2.5 mm shrinks the Color line, and to 3.0 mm shrinks Type
# as well -- while raising only this one to 3.0 mm changes nothing about
# the width and still leaves 6.5 mm of clear space above the text.
#
# Defaults to TEXT_MARGIN so nothing about the 24 mm plate changes.
DEFAULT_BOTTOM_MARGIN = TEXT_MARGIN   # mm

# --- Relief / engrave ------------------------------------------------------ #
# EMBOSS and DEBOSS are NOT mirror images: see engine/swatch.py. Each has its own
# validation because the failure modes are opposite.
MODE_EMBOSS = 'EMBOSS'
MODE_DEBOSS = 'DEBOSS'

# Emboss relief height, independent of plate thickness. Clamped tight: taller
# relief is more likely to catch the nozzle and get knocked loose mid-print.
DEFAULT_RELIEF = 0.4          # mm
RELIEF_MIN = 0.3             # mm
RELIEF_MAX = 0.5             # mm

# Deboss engrave depth, measured DOWN from the top face. Bounded against the
# plate: enough material must remain under the deepest cut.
DEFAULT_ENGRAVE = 0.5         # mm
ENGRAVE_FLOOR = 0.8          # mm of material that must remain below the cavity

# The glyph solid must never land coplanar with the plate's top face -- a
# zero-thickness contact makes the exact solver return degenerate faces or
# nothing. So it always overshoots the face by this much:
#   emboss  -- the glyph base sinks this far BELOW the top before the union
#   deboss  -- the glyph tool starts this far ABOVE the top before the cut
COPLANAR_GUARD = 0.1          # mm

# --- Print limits (0.4 mm nozzle) ------------------------------------------ #
# Both apply to both modes, for opposite reasons: in relief the nozzle cannot
# lay a bead thinner than this; in recess it cannot enter a cavity narrower than
# this and the slicer drops the feature.
MIN_STROKE = 0.45            # mm, thinnest printable glyph stroke
MIN_GLYPH_SPACING = 0.4      # mm between adjacent glyph perimeters

# Hard floor for the auto-shrink, as a cap height in mm. Below this a line
# stops being lettering and the add-on refuses outright rather than building
# something nobody could read.
#
# Deliberately BELOW the printable-stroke threshold, which for the bundled
# font is a 2.15 mm cap (MIN_STROKE / 0.209 stem-per-cap, both measured). A
# 12-character colour name on a 24 mm plate genuinely needs about a 2.09 mm
# cap to fit -- refusing it would block a legitimate swatch over 0.06 mm.
# Instead the geometry builds and the panel WARNS that the stroke came out
# under what a 0.4 mm nozzle can lay down, leaving the trade to the person
# who knows their printer. Blocking is for what cannot work at all; warning
# is for what merely prints worse.
MIN_FONT_SIZE = 1.5   # mm cap height

# --- Plate size presets ----------------------------------------------------#
# WHERE THE TWO SIZES COME FROM, because they are not the same kind of
# number:
#
#   24 x 24 mm is the COMMUNITY STANDARD -- the size filament swatches are
#   shared at, so one built here drops into an existing collection and hangs
#   on the same ring. It is the shipped default for that reason, not because
#   it measures best.
#
#   35 x 35 mm is this ADD-ON'S OWN PROPOSAL, for anyone who finds the
#   standard cramped. Easier to hold and read -- and not only taste: the
#   extra width is what lets a long colour name print at all. MEASURED with
#   "Cinza Chumbo" (12 characters), the thinnest stroke is 0.437 mm at 24 mm
#   -- under the 0.45 mm a 0.4 mm nozzle can lay down -- against 0.666 mm at
#   35 mm.
#
# Offered as a segmented toggle (ui/properties.py's plate_size) at the top of
# the main panel -- the SAME mechanism as the Hook/Round switch, chosen
# (0.14.0, reversing an 0.11.0 decision) so the active size stays visibly lit
# rather than a stateless button nobody can glance at to check. Each is a
# complete set applied together -- a bigger plate with the 24 mm set's
# lettering reads as a small label stranded in a corner. MEASURED at the
# shipped 24 mm defaults on a 35 mm plate: the text block drops from 88.1% of
# the width to 65.3%, and unused headroom triples from 14.5% to 40.8%.
#
# 35's numbers are NOT the 24 set multiplied by 35/24 (1.4583). MEASURED,
# that multiplication (text 3.5/4.4/3.8) overflows the usable width and
# auto-shrinks an ordinary colour name ("Marrom Cafe"); 3.4/4.2/3.6 is the
# largest set that does not. TEXT_MARGIN, HOLE_INSET and LINE_GAP above stay
# module constants, not part of any preset -- no operator reaches them, so
# the 35 mm preset's proportions are close to but not an exact match for
# 24's.
#
# Corner radius, hook size and hole diameter are hardware, and NONE of the
# three scale with the plate -- see the PLATE_PRESET_35 entry below for the
# print-validated reasoning. A scaled round hole would also run into a hard
# limit even if the decision were purely geometric: HOLE_INSET (3.75 mm,
# fixed) is the hole's centre-to-edge distance regardless of plate size, so
# the naive multiplication's 5.1 mm hole would leave only 1.2 mm of wall.
#
# Thickness is deliberately absent from both -- it is a printing decision,
# not a proportion, and both presets would set the same DEFAULT_PLATE_THICK
# anyway, so including it here could only overwrite a deliberate choice with
# no benefit.
PLATE_PRESET_24 = 'P24'
PLATE_PRESET_35 = 'P35'
PLATE_PRESETS = {
    # Built FROM the shipped defaults, never a second copy of the same
    # numbers -- a duplicated literal here is exactly how hook_size drifted
    # out of sync with its own default once already (see engine/swatch.py's
    # SwatchParams).
    PLATE_PRESET_24: {
        "plate_w": DEFAULT_PLATE_W, "plate_h": DEFAULT_PLATE_H,
        "corner_radius": DEFAULT_CORNER_RADIUS,
        "hook_size": DEFAULT_HOOK_SIZE,
        "hole_diameter": DEFAULT_HOLE_DIAMETER,
        "brand_size": DEFAULT_BRAND_SIZE,
        "type_size": DEFAULT_TYPE_SIZE,
        "color_size": DEFAULT_COLOR_SIZE,
        "bottom_margin": DEFAULT_BOTTOM_MARGIN,
    },
    PLATE_PRESET_35: {
        "plate_w": 35.0, "plate_h": 35.0,
        # Corner radius, hook and hole all stay at the SMALL plate's sizes,
        # not scaled up -- all three are hardware, not decoration. A corner
        # is a corner regardless of the plate around it, and the hook/hole
        # exist to fit a real keyring, which does not get bigger on a bigger
        # plate. PRINT-VALIDATED (11/08/2026): both plates came off the
        # printer looking right, and the 35 mm one with a SCALED hook (9.6,
        # hole 4.0) was the one part of it that read as wrong -- confirming
        # the hardware should not have scaled in the first place. Referenced
        # from the constants, never restated as literals, so the two
        # presets cannot drift apart on any of the three again.
        "corner_radius": DEFAULT_CORNER_RADIUS,
        "hook_size": DEFAULT_HOOK_SIZE,
        "hole_diameter": DEFAULT_HOLE_DIAMETER,
        "brand_size": 3.4, "type_size": 4.2, "color_size": 3.6,
        # Double the 24 mm plate's, because at 1.5 mm the block sat 1.5 mm
        # off the bottom edge with 8.37 mm of clear space above it -- badly
        # bottom-heavy on a plate this size. MEASURED, 3.0 puts the ratio of
        # bottom border to space-above at 1:2.3, against the 24 mm plate's
        # own 1:2.6. Free of the auto-shrink because this margin never
        # reaches _text_box() -- see DEFAULT_BOTTOM_MARGIN above.
        "bottom_margin": 3.0,
    },
}
