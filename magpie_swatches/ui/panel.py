"""The N-panel.

Design brief: three text fields, a mode switch, and one button. The two
calibrated plate sizes are a segmented toggle at the very top of the main
panel, since forgetting which one is active is exactly the mistake it exists
to prevent; everything else that shapes the plate (raw dimensions, hole,
per-field sizes) lives under Adjust, closed by default, because a filament
swatch is made a dozen times a session with the same plate and different
words on it -- the plate settings should not be back in the way every time.

Never calls engine/ directly and never builds a bpy object -- every action is
an operator invoked by its bl_idname string. Reads branding.py and
preferences.py for the logo, constants.py for the brand strings, and
operators.py for scene_is_mm().
"""

from pathlib import Path

import bpy

from ..constants import (AUTHOR, BRAND, HOLE_ROUND, MODE_DEBOSS, MODE_EMBOSS,
                         OP)
from ..engine.booleans import has_manifold_solver
from . import branding, preferences
from .operators import scene_is_mm

try:
    import tomllib
except Exception:
    tomllib = None

# House button hierarchy, same across the add-on family:
#   2.5 = the one headline action (there is exactly one per add-on)
#   2.0 = primary action of a section
#   1.5 = secondary "add a part" action
#   1.0 = fields and modifiers (Blender default, never scaled)
HERO = 2.5
ADD_PART = 1.5


def _banner(layout, scale):
    """Draw the logo. Copied verbatim from the sibling add-ons, on purpose:
    this is the known-good version, and siblings must render identically."""
    icon = branding.logo_icon_id()
    if not icon:
        return False
    row = layout.row()
    row.alignment = 'CENTER'
    row.template_icon(icon_value=icon, scale=scale)
    return True


# Cached after the first read -- draw() is called on every redraw of every
# panel, and re-opening + re-parsing blender_manifest.toml that often is
# disk I/O this add-on has no business doing in a callback the size of a
# label. The manifest cannot change under a running session (a version bump
# only takes effect after a reinstall, which reloads this whole module), so
# one read for the module's lifetime is exactly as fresh as it needs to be.
_VERSION_CACHE = None


def _version():
    global _VERSION_CACHE
    if _VERSION_CACHE is not None:
        return _VERSION_CACHE
    if tomllib is None:
        _VERSION_CACHE = ""
        return _VERSION_CACHE
    try:
        manifest = Path(__file__).resolve().parent.parent / "blender_manifest.toml"
        with manifest.open("rb") as f:
            _VERSION_CACHE = str(tomllib.load(f).get("version", ""))
    except Exception:
        _VERSION_CACHE = ""
    return _VERSION_CACHE


def _wrap(layout, text, icon):
    """A narrow panel truncates past ~28 characters, so wrap by hand rather
    than letting Blender cut the message in half."""
    col = layout.column(align=True)
    words = text.split()
    line = ""
    first = True
    for word in words:
        if len(line) + len(word) + 1 > 28:
            col.label(text=line, icon=icon if first else 'BLANK1')
            first = False
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        col.label(text=line, icon=icon if first else 'BLANK1')


class MAGPIESWATCHES_PT_main(bpy.types.Panel):
    bl_label = BRAND
    bl_idname = "MAGPIESWATCHES_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = BRAND

    def draw(self, context):
        layout = self.layout
        p = context.scene.magpie_swatches

        # Logo at scale 12 == full width of a default N panel; the number is
        # the family's, so the sibling add-ons read as one set. Drawn straight
        # on the layout -- nesting it in a column shrinks it. Switched off in
        # add-on preferences for narrow sidebars, and then the text fallback
        # and the gap go with it -- turning the artwork off has to actually
        # buy back the vertical space, not leave a hole and a title where it
        # used to be.
        if preferences.show_logo(context):
            if not _banner(layout, 12.0):
                title = layout.row()
                title.alignment = 'CENTER'
                title.scale_y = 1.6
                title.label(text=BRAND, icon='MESH_CIRCLE')
            layout.separator(factor=1.5)

        # CARD 1 -- pick a size, then insert. Segmented toggle at 1.0, same
        # tier as the Hook/Round switch under Adjust -- both are
        # EnumProperty(expand=True), the mechanism that gives Blender's own
        # pressed-in highlight, not a scale choice. See properties.py's
        # plate_size for why this replaced a stateless operator button.
        box = layout.box()
        box.row(align=True).prop(p, "plate_size", expand=True)

        add = box.row(align=True)
        add.scale_y = ADD_PART
        add.operator(f"{OP}.add_swatch", icon='MESH_PLANE')

        # CARD 2 -- write on it, then finish it. House hierarchy: 1.5 is the
        # "add a part" tier used above, below HERO's 2.5 -- Card 1 drops the
        # bare plate in so you can look at it, it is not the finished,
        # ready-to-slice piece that scale_y = HERO below is.
        box = layout.box()
        col = box.column()
        col.label(text="Text", icon='OUTLINER_OB_FONT')
        col.separator()
        col.prop(p, "brand")
        col.prop(p, "type")
        col.prop(p, "color")

        # Derived, never asked for: the stroke the bundled font's own stem
        # width came out to at this size, not something the add-on
        # thickened -- see engine/text.py's "WHY THERE IS NO SYNTHETIC BOLD
        # HERE" for why post-processing the outline was rejected instead.
        # Right after Color -- it is that field's own line that most often
        # needs it.
        # Parenthesised, no icon: a readout, not a warning -- see
        # last_shrunk just below, which used to BE a warning and hid the
        # one that actually mattered.
        if p.last_stroke:
            stroke = box.row()
            stroke.alignment = 'CENTER'
            stroke.label(text=p.last_stroke)
        if p.last_shrunk:
            shrunk = box.row()
            shrunk.alignment = 'CENTER'
            shrunk.label(text=p.last_shrunk)

        box.separator(factor=0.5)
        box.label(text="Mode")
        box.row(align=True).prop(p, "mode", expand=True)
        if p.mode == MODE_EMBOSS:
            box.prop(p, "relief")
        else:
            box.prop(p, "engrave")

        box.separator(factor=0.75)
        row = box.row(align=True)
        row.scale_y = HERO
        row.operator(f"{OP}.generate",
                    icon='MOD_SOLIDIFY' if p.mode == MODE_EMBOSS else 'MOD_MASK')
        # Card 2 ends here -- everything below is about what to know AFTER
        # a build, not about building one.

        # CARD 3 -- what to know about what just got built. Guarded: in the
        # common case (emboss, Blender 4.5+, a clean build) none of the
        # three fire, and an empty box() here would be a grey rectangle
        # sitting between Generate and Export for no reason.
        if p.last_warning or p.mode == MODE_DEBOSS or not has_manifold_solver():
            box = layout.box()
            # last_warning first: it is specific to the build that just
            # happened and the only one of the three that is actionable.
            # The other two are standing notices -- true regardless of what
            # was just generated -- so whoever had a problem reads about
            # THEIR problem before the general notices.
            if p.last_warning:
                _wrap(box, p.last_warning, 'ERROR')
            if p.mode == MODE_DEBOSS:
                _wrap(box, "disable ironing on top, or it will smear the "
                           "cavity edges", 'INFO')
            if not has_manifold_solver():
                _wrap(box, "Blender 4.2: validated and working here on the "
                           "EXACT solver -- 4.5+ adds MANIFOLD, with more "
                           "margin for unusual geometry", 'INFO')

        # CARD 4 -- export.
        if p.last_swatch is not None:
            box = layout.box()
            col = box.column(align=True)
            col.scale_y = 1.4
            col.operator(f"{OP}.export", icon='EXPORT')
            col.operator(f"{OP}.export_fbx", icon='EXPORT')


class MAGPIESWATCHES_PT_settings(bpy.types.Panel):
    """The plate itself: dimensions, hole, and how big each line of text is.

    Named with a verb -- it invites you to touch it, and closed by default
    because most sessions reuse the same plate and only change the words.
    """

    bl_label = "Adjust"
    bl_idname = "MAGPIESWATCHES_PT_settings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = BRAND
    bl_parent_id = "MAGPIESWATCHES_PT_main"
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 5

    def draw(self, context):
        layout = self.layout
        p = context.scene.magpie_swatches

        box = layout.box()
        box.label(text="Plate", icon='MESH_PLANE')
        col = box.column(align=True)
        col.prop(p, "plate_w")
        col.prop(p, "plate_h")
        col.prop(p, "thickness")
        col.prop(p, "corner_radius")

        box.separator()
        box.prop(p, "hole", toggle=True)
        if p.hole:
            box.row(align=True).prop(p, "hole_style", expand=True)
            if p.hole_style == HOLE_ROUND:
                box.prop(p, "hole_diameter")
            else:
                box.prop(p, "hook_size")
            sub = box.column(align=True)
            sub.prop(p, "hole_offset_x")
            sub.prop(p, "hole_offset_y")

        box = layout.box()
        box.label(text="Text size", icon='SMALL_CAPS')
        col = box.column(align=True)
        col.prop(p, "brand_size")
        col.prop(p, "type_size")
        col.prop(p, "color_size")
        # Separate group: the three above answer "how big are the letters",
        # this answers "where does the block sit".
        box.separator()
        box.prop(p, "bottom_margin")

        # Purely cosmetic now that Export FBX self-compensates (see
        # ui/operators.py's MAGPIESWATCHES_OT_export_fbx): the only thing
        # this button changes is whether Blender's own UI labels the swatch
        # "24 mm" or "24 m". No ERROR icon and its own card, not loose on
        # the main panel, because it stopped being a warning the moment the
        # FBX export learned to compensate on its own. Only drawn when
        # there is something to say -- an empty box here would be a grey
        # rectangle with no reason to exist.
        if not scene_is_mm(context.scene):
            box = layout.box()
            for line in ("Scene is not in mm.", "Only changes what Blender",
                        "shows -- exports are", "correct either way."):
                r = box.row()
                r.alignment = 'CENTER'
                r.label(text=line, icon='INFO' if line.startswith("Scene")
                        else 'BLANK1')
            fix = box.row(align=True)
            fix.scale_y = 1.3
            fix.operator(f"{OP}.fix_units", icon='DRIVER_DISTANCE')

        layout.separator()
        row = layout.row(align=True)
        row.operator(f"{OP}.reset", icon='LOOP_BACK')


class MAGPIESWATCHES_PT_about(bpy.types.Panel):
    bl_label = "About"
    bl_idname = "MAGPIESWATCHES_PT_about"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = BRAND
    bl_parent_id = "MAGPIESWATCHES_PT_main"
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 20

    def draw(self, context):
        col = self.layout.column(align=True)
        col.label(text=f"{BRAND}  v{_version()}")
        col.label(text=f"(c) {AUTHOR}", icon='COPY_ID')

        prefs = preferences.entry(context)
        if prefs:
            col.separator()
            col.prop(prefs, "show_logo")
