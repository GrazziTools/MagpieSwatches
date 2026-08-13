"""Scene parameters.

Every field that feeds the geometry carries `update=_stale`, so changing it
invalidates the last report -- a stale "24 x 24 x 2.4 mm" readout describing a
part that no longer matches the current settings is worse than no readout at
all. Two exceptions: `last_swatch` tracks WHICH object Generate should
replace next time, not a fact about the part's shape, so it is never touched
by _stale and only ever written by the generate operator itself; `plate_size`
carries `update=_apply_plate_preset` instead, which writes a whole set of
OTHER fields -- each of those still carries its own `_stale`, so nothing is
missed, it just isn't `plate_size`'s own job to clear the readout.

Never imported by engine/ -- MagpieSwatchesProps crossing that boundary is
exactly what engine.swatch.SwatchParams exists to prevent. Read throughout ui/
via context.scene.magpie_swatches: panel.py draws these fields, operators.py
reads them to build a SwatchParams and act.
"""

import bpy
from bpy.props import (BoolProperty, EnumProperty, FloatProperty,
                       PointerProperty, StringProperty)

from ..constants import (DEFAULT_BOTTOM_MARGIN, DEFAULT_BRAND_SIZE,
                         DEFAULT_COLOR_SIZE,
                         DEFAULT_CORNER_RADIUS, DEFAULT_ENGRAVE,
                         DEFAULT_HOLE, DEFAULT_HOLE_DIAMETER,
                         DEFAULT_HOLE_OFFSET, DEFAULT_HOLE_STYLE,
                         DEFAULT_HOOK_SIZE, DEFAULT_PLATE_H,
                         DEFAULT_PLATE_THICK, DEFAULT_PLATE_W, DEFAULT_RELIEF,
                         DEFAULT_TYPE_SIZE, HOLE_HOOK, HOLE_ROUND,
                         MIN_FONT_SIZE, MIN_HOOK_SIZE, MODE_DEBOSS,
                         MODE_EMBOSS, PLATE_PRESET_24, PLATE_PRESET_35,
                         PLATE_PRESETS, RELIEF_MAX, RELIEF_MIN)


def _stale(self, context):
    """A parameter changed -> the readout describes a part that no longer
    exists."""
    self.last_report = ""
    self.last_warning = ""
    self.last_stroke = ""
    self.last_shrunk = ""


def _apply_plate_preset(self, context):
    """Write the whole calibrated set for the chosen size.

    Blender calls this on every change to plate_size, including the one
    Reset triggers when it unsets the property -- harmless, since it just
    rewrites the same shipped defaults.

    Writing plate_w/plate_h from here is safe and does NOT recurse: their
    own update callback is _stale(), which only clears the readout strings
    and never writes back to plate_size. Each field written here also
    carries its own _stale, so this needs none of its own.
    """
    for field, value in PLATE_PRESETS[self.plate_size].items():
        setattr(self, field, value)


class MagpieSwatchesProps(bpy.types.PropertyGroup):
    # --- the three text fields --- #
    brand: StringProperty(
        name="Brand",
        description="The filament brand, e.g. Sunlu. Leave empty to skip this "
                    "line -- only all three fields empty is an error",
        update=_stale,
    )
    type: StringProperty(
        name="Type",
        description="The filament type, e.g. PLA Matte. Drawn largest -- it is "
                    "the line most people read first",
        update=_stale,
    )
    color: StringProperty(
        name="Color",
        description="The colour name, e.g. Marrom Cafe",
        update=_stale,
    )
    brand_size: FloatProperty(
        name="Brand size (mm)",
        description="Height of a capital letter on the Brand line, in "
                    "millimetres -- what you would measure on the printed "
                    "part. A line too wide for the plate is shrunk to fit",
        default=DEFAULT_BRAND_SIZE, min=MIN_FONT_SIZE, update=_stale,
    )
    type_size: FloatProperty(
        name="Type size (mm)",
        description="Height of a capital letter on the Type line, in "
                    "millimetres",
        default=DEFAULT_TYPE_SIZE, min=MIN_FONT_SIZE, update=_stale,
    )
    color_size: FloatProperty(
        name="Color size (mm)",
        description="Height of a capital letter on the Color line, in "
                    "millimetres",
        default=DEFAULT_COLOR_SIZE, min=MIN_FONT_SIZE, update=_stale,
    )
    bottom_margin: FloatProperty(
        name="Bottom margin (mm)",
        description="Clear space between the plate's bottom edge and the "
                    "lettering. Only the bottom is adjustable -- widening "
                    "the sides would take width away from the text and "
                    "shrink it",
        default=DEFAULT_BOTTOM_MARGIN, min=0.0, update=_stale,
    )

    # --- plate --- #
    # Segmented toggle, same mechanism as hole_style/mode below (EnumProperty
    # drawn with expand=True) -- deliberately reverses the 0.11.0 decision to
    # use a stateless operator button instead, because a button never shows
    # WHICH size is active and that was worse in practice than the risk this
    # brings back: it shows the LAST size applied, not a live match against
    # plate_w/plate_h, so editing Width by hand afterwards leaves it pointing
    # at a size that no longer matches. No attempt to resync it from
    # plate_w/plate_h -- that update loop risks becoming genuinely circular.
    plate_size: EnumProperty(
        name="Plate size",
        description="Apply a calibrated plate size -- sets the dimensions, "
                    "the bottom margin and all three text sizes together. "
                    "Shows the last size applied: editing Width or Height "
                    "by hand afterwards does not change it back",
        items=[
            (PLATE_PRESET_24, "24 x 24 mm",
             "24 x 24 mm -- the community-standard size, so the swatch "
             "matches the ones you already have"),
            (PLATE_PRESET_35, "35 x 35 mm",
             "35 x 35 mm -- this add-on's own roomier proposal: easier to "
             "read, and wide enough to print long colour names that come "
             "out too thin at 24 mm"),
        ],
        default=PLATE_PRESET_24, update=_apply_plate_preset,
    )
    plate_w: FloatProperty(
        name="Width (mm)", description="Plate width, left to right",
        default=DEFAULT_PLATE_W, min=1.0, update=_stale,
    )
    plate_h: FloatProperty(
        name="Height (mm)", description="Plate height, bottom to top",
        default=DEFAULT_PLATE_H, min=1.0, update=_stale,
    )
    thickness: FloatProperty(
        name="Thickness (mm)", description="How thick the plate is",
        default=DEFAULT_PLATE_THICK, min=0.6, update=_stale,
    )
    corner_radius: FloatProperty(
        name="Corner radius (mm)",
        description="How rounded the four corners are. 0 for sharp corners",
        default=DEFAULT_CORNER_RADIUS, min=0.0, update=_stale,
    )

    # --- mounting hole --- #
    hole: BoolProperty(
        name="Hanging hole",
        description="Add a hole in one corner, for a keyring or hangtag",
        default=DEFAULT_HOLE, update=_stale,
    )
    hole_diameter: FloatProperty(
        name="Hole diameter (mm)", description="How wide the hole is",
        default=DEFAULT_HOLE_DIAMETER, min=0.5, update=_stale,
    )
    # Enum, not a second boolean alongside `hole`: leaves room for a third
    # style later without breaking a saved .blend -- same reasoning as `mode`.
    hole_style: EnumProperty(
        name="Style",
        description="How the hanging opening works",
        items=[
            (HOLE_HOOK, "Hook", "An open spiral channel -- thread a closed "
                                "keyring in through its open end and turn "
                                "the swatch to walk the ring down to the "
                                "seat. No need to open the ring"),
            (HOLE_ROUND, "Round", "A plain round hole -- needs a ring "
                                  "that is already open, or split, to "
                                  "thread through it"),
        ],
        default=DEFAULT_HOLE_STYLE, update=_stale,
    )
    hook_size: FloatProperty(
        name="Hook size (mm)",
        description="How tall the hook is. The shape itself is fixed, so "
                    "this scales the whole thing -- channel and ring seat "
                    "included",
        default=DEFAULT_HOOK_SIZE, min=MIN_HOOK_SIZE, update=_stale,
    )
    # Static min/max here are a generous safety rail, not the real limit --
    # how far the hole can actually move depends on the plate size and the
    # hole/hook's own footprint, neither of which a FloatProperty's min/max
    # can see. The real check runs in engine/validate.py against the real
    # geometry, and reports a named error naming the hole, not the text.
    hole_offset_x: FloatProperty(
        name="Offset X (mm)",
        description="Move the hole/hook sideways from its default top-left "
                    "position. Free to move either way, as long as it still "
                    "clears the plate edges",
        default=DEFAULT_HOLE_OFFSET, soft_min=-20.0, soft_max=20.0,
        update=_stale,
    )
    hole_offset_y: FloatProperty(
        name="Offset Y (mm)",
        description="Move the hole/hook up or down from its default "
                    "top-left position. Limited to the plate's upper half "
                    "-- the text block owns the lower half",
        default=DEFAULT_HOLE_OFFSET, soft_min=-20.0, soft_max=20.0,
        update=_stale,
    )

    # --- relief mode --- #
    # An EnumProperty rather than a boolean on purpose: it leaves room for a
    # third mode (CUTOUT, text punched fully through the plate) later without
    # breaking any .blend saved against this version.
    mode: EnumProperty(
        name="Mode",
        description="Whether the text stands up off the plate or sinks into it",
        items=[
            (MODE_EMBOSS, "Emboss", "Raised lettering -- reads well from any "
                                    "angle on a single-colour part"),
            (MODE_DEBOSS, "Deboss", "Recessed lettering -- for a filament or "
                                    "colour change at a set layer height"),
        ],
        default=MODE_EMBOSS, update=_stale,
    )
    relief: FloatProperty(
        name="Relief height (mm)",
        description="How far the emboss stands up off the plate. Taller "
                    "letters catch the nozzle more easily and can be knocked "
                    "loose mid-print",
        default=DEFAULT_RELIEF, min=RELIEF_MIN, max=RELIEF_MAX, update=_stale,
    )
    engrave: FloatProperty(
        name="Engrave depth (mm)",
        description="How deep the deboss cuts into the plate",
        default=DEFAULT_ENGRAVE, min=0.1, update=_stale,
    )

    # --- read-only result of the last build --- #
    last_report: StringProperty(default="")
    last_warning: StringProperty(default="")
    last_stroke: StringProperty(default="")
    last_shrunk: StringProperty(default="")

    # Tracks which object Generate should replace next time, so regenerating
    # does not pile up orphan swatches. A fact about add-on STATE, not about
    # the part's shape -- never touched by _stale.
    last_swatch: PointerProperty(type=bpy.types.Object)
