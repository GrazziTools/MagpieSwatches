"""Thin wrappers: read props -> call engine -> report. No geometry maths here.

Calls into engine.swatch for the geometry itself, and into engine.validate /
engine.text / engine.booleans / engine.hook only to catch the exceptions a
build can raise (ValidationError, TextOverflowError, BooleanError,
HookError). Nothing here builds a bpy mesh by hand.
"""

from pathlib import Path

import bpy

from ..constants import CORNER_SEGMENTS, MIN_STROKE, MODE_DEBOSS, OP
from ..engine import objects as engine_objects
from ..engine.booleans import BooleanError
from ..engine.hook import HookError
from ..engine.scale import SCENE_UNIT_SCALE
from ..engine.swatch import SwatchParams, build_swatch
from ..engine.text import TextOverflowError
from ..engine.validate import ValidationError
from . import preferences


def scene_is_mm(scene) -> bool:
    """True when the scene's unit settings read as 1 unit = 1 mm.

    Every swatch is built at 1 unit = 1 mm regardless of this setting -- the
    geometry is always correct. This only affects whether Blender's own UI and
    unit-aware exporters (FBX; not STL, which carries no unit) LABEL and scale
    those numbers correctly.
    """
    units = scene.unit_settings
    return (units.system == 'METRIC'
            and abs(units.scale_length - SCENE_UNIT_SCALE) < 1e-9)


def _params_from(props, blank: bool = False) -> SwatchParams:
    """Scene properties -> engine parameters.

    `blank` drops the three text fields on the way through, which is the only
    difference between Add Swatch and Generate -- the plate, hole and mode all
    come from the same settings either way, so the blank you add is exactly
    the plate the lettering will land on.
    """
    return SwatchParams(
        brand="" if blank else props.brand,
        type="" if blank else props.type,
        color="" if blank else props.color,
        brand_size=props.brand_size, type_size=props.type_size,
        color_size=props.color_size,
        plate_w=props.plate_w, plate_h=props.plate_h,
        thickness=props.thickness, corner_radius=props.corner_radius,
        corner_segments=CORNER_SEGMENTS,
        hole=props.hole, hole_diameter=props.hole_diameter,
        mode=props.mode, relief=props.relief, engrave=props.engrave,
        hole_style=props.hole_style, hook_size=props.hook_size,
        hole_offset_x=props.hole_offset_x, hole_offset_y=props.hole_offset_y,
        bottom_margin=props.bottom_margin,
    )


def _build_and_place(op, context, params):
    """Build, swap in for the previous swatch, and hand back the BuildResult.

    Shared by Add Swatch and Generate so the two buttons cannot drift apart on
    the housekeeping: both replace the last swatch instead of piling up
    orphans, both land in the user's active collection, both leave the new
    object selected and active. Returns None after reporting, if the build
    failed.
    """
    props = context.scene.magpie_swatches
    try:
        result = build_swatch(params)
    except (ValidationError, TextOverflowError, BooleanError,
           HookError) as exc:
        # HookError is currently unreachable in practice -- validate.check()
        # runs first and rejects an invalid hook_size before build_swatch()
        # ever reaches hook.hook_tool() -- but that is an ordering fact
        # about build_swatch(), not a guarantee HookError's own definition
        # makes. Catching it here means that stays true even if the two
        # ever drift, instead of a user seeing a bare traceback for it.
        op.report({'ERROR'}, str(exc))
        return None

    obj = result.obj

    # Regenerating replaces the previous swatch rather than piling up orphans.
    # An ID pointer property is auto-cleared to None by Blender when the
    # object it points to is removed elsewhere, so a non-None last_swatch is
    # guaranteed still live -- no extra check.
    if props.last_swatch is not None and props.last_swatch is not obj:
        engine_objects.remove(props.last_swatch)

    # build_swatch() links into the scene's root collection so every boolean
    # along the way has something evaluable to work on (see engine/objects.py).
    # Move it into wherever the user is actually working before handing
    # control back.
    root = context.scene.collection
    if obj.name in root.objects:
        root.objects.unlink(obj)
    target = context.collection or root
    if obj.name not in target.objects:
        target.objects.link(obj)

    for other in context.selected_objects:
        other.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj
    props.last_swatch = obj

    dims = obj.dimensions
    props.last_report = f"{dims.x:.0f} x {dims.y:.0f} x {dims.z:.1f} mm"
    return result


class MAGPIESWATCHES_OT_add_swatch(bpy.types.Operator):
    """Add the swatch plate with no lettering on it yet.

    The first step of the two-button flow: put the plate in the scene, look at
    the size and where the hole falls, then type the text and hit Generate.
    Uses the SAME plate settings Generate will, so what you are looking at is
    the plate the lettering lands on -- not a stand-in. Named "Add Swatch",
    not "Add Plate": what it inserts is a swatch (the add-on's one product,
    just not lettered yet), and calling it a "plate" would read as a second,
    unrelated kind of object.
    """

    bl_idname = f"{OP}.add_swatch"
    bl_label = "Add Swatch"
    bl_description = ("Add the swatch with no lettering yet, to check its "
                      "size and the hole before writing anything")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.magpie_swatches
        result = _build_and_place(self, context, _params_from(props,
                                                             blank=True))
        if result is None:
            return {'CANCELLED'}
        props.last_warning = ""
        props.last_stroke = ""
        props.last_shrunk = ""
        self.report({'INFO'}, f"Blank plate: {props.last_report}")
        return {'FINISHED'}


class MAGPIESWATCHES_OT_generate(bpy.types.Operator):
    bl_idname = f"{OP}.generate"
    bl_label = "Generate"
    bl_description = ("Build the swatch with its lettering, sized in "
                      "millimetres and ready to export as STL")
    bl_options = {'REGISTER', 'UNDO'}

    # Deliberately no poll(). Generate is the button that puts the finished
    # piece in the scene, so it must never be greyed out -- on a fresh install
    # every text field is empty, and a disabled button there makes the add-on
    # look like it has no way to insert anything. With no text it falls back
    # to the blank plate; anything genuinely wrong comes back as a named error
    # from engine.validate instead of a dead button with no explanation.

    def execute(self, context):
        props = context.scene.magpie_swatches
        result = _build_and_place(self, context, _params_from(props))
        if result is None:
            return {'CANCELLED'}

        notes = []
        # label is None for a blank plate -- nothing was laid out to shrink.
        lines = result.label.lines if result.label is not None else []

        # The thinnest line is what a nozzle has to cope with, so that is the
        # number worth showing -- an average would hide the one that fails.
        thinnest = min((l.stroke for l in lines), default=0.0)
        props.last_stroke = (f"(thinnest stroke: {thinnest:.2f} mm)"
                             if lines else "")

        # A READOUT, not a warning -- auto-shrink is designed behaviour (see
        # engine/text.py's _fit_size) and fires on ordinary filament names
        # at the shipped defaults, so it belongs next to the stroke figure,
        # not in the panel's error block. It used to sit in `notes` as
        # actionable, which OUTRANKED the printable-stroke warning below:
        # only actionable[0] reaches the panel, and this was appended
        # first, so a colour name long enough to shrink under the
        # printable floor reported the cosmetic note and hid the one that
        # mattered.
        shrunk = [line.field for line in lines if line.shrunk]
        # Named while they fit the panel's ~28 characters; past two fields
        # the names stop earning their room and a count reads better than a
        # truncated list.
        who = ", ".join(shrunk) if len(shrunk) < 3 else f"{len(shrunk)} lines"
        props.last_shrunk = f"({who} auto-shrunk)" if shrunk else ""
        # Actionable, not fatal: a stroke under the nozzle's width still
        # builds and still exports. In emboss the slicer widens it to one
        # bead, so it prints fatter than modelled; in deboss the nozzle
        # cannot enter the cavity and the lettering can disappear. Either
        # way the fix is the user's -- bigger text, or a heavier font.
        if lines and thinnest < MIN_STROKE:
            notes.append((f"thinnest stroke {thinnest:.2f} mm is under the "
                          f"{MIN_STROKE} mm a 0.4 mm nozzle can print -- "
                          f"raise the text size", True))
        if props.mode == MODE_DEBOSS:
            notes.append(("deboss: disable ironing on the top surface or it "
                          "will smear the cavity edges", False))

        actionable = [text for text, act in notes if act]
        props.last_warning = actionable[0] if actionable else ""
        if notes:
            self.report({'WARNING' if actionable else 'INFO'},
                        "; ".join(text for text, _ in notes))
        else:
            self.report({'INFO'}, f"Built: {props.last_report}")
        return {'FINISHED'}


def _default_stem(props) -> str:
    """Suggested filename (no extension): the filled-in fields, in swatch
    order.

    "Sunlu - PLA Matte - Marrom Cafe" rather than the object's own name
    ("Sunlu - SWATCH"): anyone using this add-on generates many of these
    files, and "SWATCH" is identical on every single one of them, so it
    cannot tell two files apart in a folder listing. The three fields
    together ARE the filament's identity.
    """
    parts = [t.strip() for t in (props.brand, props.type, props.color)
            if t and t.strip()]
    stem = " - ".join(parts) if parts else "Swatch"
    # Same sanitising the object name got. str.isalnum() is Unicode-aware, so
    # an accented name like "Marrom Cafe" survives -- do not narrow this to
    # [a-zA-Z0-9].
    safe = "".join(c for c in stem if c.isalnum() or c in " -_.").strip()
    return safe or "Swatch"


class MAGPIESWATCHES_OT_export(bpy.types.Operator):
    """Write the last generated swatch to an STL, ready to slice.

    Scene units are deliberately NOT applied. STL carries no unit, so a
    slicer reads the raw numbers as millimetres -- which is exactly what
    these are. Letting Blender convert would divide by a thousand and the
    swatch would arrive the size of a grain of rice.
    """

    bl_idname = f"{OP}.export"
    bl_label = "Export STL"
    bl_description = "Save the swatch as an STL, at the right size to slice"
    bl_options = {'REGISTER'}

    # filepath (a FULL path), not directory: that is what makes Blender's
    # file browser show an editable filename field instead of opening as a
    # bare folder picker -- confirmed against Blender's own STL exporter
    # (bpy.ops.wm.stl_export), which declares filepath/check_existing/
    # filter_glob and has no directory property at all. Declaring both
    # filepath and directory on one operator leaves the browser's mode
    # ambiguous, so this is a replacement, not an addition.
    filepath: bpy.props.StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE'})
    # Asks before silently overwriting a file that is already there.
    check_existing: bpy.props.BoolProperty(default=True, options={'HIDDEN'})
    filter_glob: bpy.props.StringProperty(default="*.stl", options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        return context.scene.magpie_swatches.last_swatch is not None

    def invoke(self, context, event):
        props = context.scene.magpie_swatches
        prefs = preferences.entry(context)
        folder = (prefs.last_export_dir if prefs and prefs.last_export_dir
                  else "//")
        self.filepath = str(Path(bpy.path.abspath(folder)) /
                            f"{_default_stem(props)}.stl")
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        obj = context.scene.magpie_swatches.last_swatch
        if obj is None:
            self.report({'ERROR'}, "Nothing to export -- generate a swatch "
                        "first")
            return {'CANCELLED'}

        if not self.filepath:
            self.report({'ERROR'}, "No filename given")
            return {'CANCELLED'}

        target = Path(bpy.path.abspath(self.filepath))
        # The name field is free text, so the extension can end up missing or
        # mis-cased; a .stl without the extension will not open with a
        # double-click in the slicer. Compare in lowercase so this cannot
        # produce "name.STL.stl".
        if target.suffix.lower() != ".stl":
            target = target.with_name(target.name + ".stl")

        if not target.parent.is_dir():
            self.report({'ERROR'}, f"Not a folder: {target.parent}")
            return {'CANCELLED'}

        previous = list(context.selected_objects)
        active = context.view_layer.objects.active
        try:
            for other in context.selected_objects:
                other.select_set(False)
            obj.select_set(True)
            context.view_layer.objects.active = obj
            bpy.ops.wm.stl_export(filepath=str(target),
                                  export_selected_objects=True,
                                  global_scale=1.0, apply_modifiers=True)
        except Exception as exc:
            self.report({'ERROR'}, f"Export failed: {exc}")
            return {'CANCELLED'}
        finally:
            for other in context.selected_objects:
                other.select_set(False)
            for other in previous:
                try:
                    other.select_set(True)
                except ReferenceError:
                    pass
            context.view_layer.objects.active = active

        self.report({'INFO'}, f"Wrote {target.name}")
        prefs = preferences.entry(context)
        if prefs:
            prefs.last_export_dir = str(target.parent)
        return {'FINISHED'}


class MAGPIESWATCHES_OT_export_fbx(bpy.types.Operator):
    """Write the last generated swatch to an FBX, at the right physical size
    regardless of the scene's own unit settings.

    Unlike STL, FBX records units, and export_scene.fbx's own
    apply_unit_scale=True default multiplies the export by the scene's
    scale_length. MEASURED: a metric-default scene (1 unit = 1 m, Blender's
    own default) produces an FBX 1000x too large; a scene already set to mm
    produces the correct size. Compensated here instead of requiring the
    scene to be fixed first (the button below does that, but it is now
    purely cosmetic for FBX) -- the file comes out right either way.
    """

    bl_idname = f"{OP}.export_fbx"
    bl_label = "Export FBX"
    bl_description = ("Save the swatch as an FBX, at the right size no "
                      "matter what the scene's units are set to")
    bl_options = {'REGISTER'}

    filepath: bpy.props.StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE'})
    check_existing: bpy.props.BoolProperty(default=True, options={'HIDDEN'})
    filter_glob: bpy.props.StringProperty(default="*.fbx", options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        return context.scene.magpie_swatches.last_swatch is not None

    def invoke(self, context, event):
        props = context.scene.magpie_swatches
        prefs = preferences.entry(context)
        folder = (prefs.last_export_dir if prefs and prefs.last_export_dir
                  else "//")
        self.filepath = str(Path(bpy.path.abspath(folder)) /
                            f"{_default_stem(props)}.fbx")
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        # io_scene_fbx ships enabled by default on both 4.2 and 5.2
        # (confirmed via addon_utils.check), but degrade with a clear
        # message rather than a bare traceback if it is ever missing.
        if not hasattr(bpy.ops.export_scene, "fbx"):
            self.report({'ERROR'}, "FBX export is not available -- enable "
                        "the 'Scene: FBX format' add-on in Preferences.")
            return {'CANCELLED'}

        obj = context.scene.magpie_swatches.last_swatch
        if obj is None:
            self.report({'ERROR'}, "Nothing to export -- generate a swatch "
                        "first")
            return {'CANCELLED'}

        if not self.filepath:
            self.report({'ERROR'}, "No filename given")
            return {'CANCELLED'}

        target = Path(bpy.path.abspath(self.filepath))
        if target.suffix.lower() != ".fbx":
            target = target.with_name(target.name + ".fbx")

        if not target.parent.is_dir():
            self.report({'ERROR'}, f"Not a folder: {target.parent}")
            return {'CANCELLED'}

        # The one thing this operator does that Export STL does not: cancel
        # out whatever the scene's unit settings are, so the file is right
        # either way. Never touches the scene itself -- that is what the
        # "Set Scene to Millimetres" button is for, for anyone who wants the
        # on-screen numbers to read correctly too.
        scale = 1.0 if scene_is_mm(context.scene) else 0.001

        previous = list(context.selected_objects)
        active = context.view_layer.objects.active
        try:
            for other in context.selected_objects:
                other.select_set(False)
            obj.select_set(True)
            context.view_layer.objects.active = obj
            bpy.ops.export_scene.fbx(filepath=str(target),
                                     use_selection=True,
                                     global_scale=scale)
        except Exception as exc:
            self.report({'ERROR'}, f"Export failed: {exc}")
            return {'CANCELLED'}
        finally:
            for other in context.selected_objects:
                other.select_set(False)
            for other in previous:
                try:
                    other.select_set(True)
                except ReferenceError:
                    pass
            context.view_layer.objects.active = active

        self.report({'INFO'}, f"Wrote {target.name}")
        prefs = preferences.entry(context)
        if prefs:
            prefs.last_export_dir = str(target.parent)
        return {'FINISHED'}


class MAGPIESWATCHES_OT_reset(bpy.types.Operator):
    """Put every setting back to its shipped value.

    property_unset() rather than assigning the defaults by hand: these live on
    the scene, so they are saved INTO the .blend. A file made with an older
    build keeps whatever it was saved with, and only unsetting restores what
    the add-on currently ships.
    """

    bl_idname = f"{OP}.reset"
    bl_label = "Reset to Defaults"
    bl_description = ("Put every setting back to its shipped value. Brand, "
                      "Type and Color are kept")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.magpie_swatches
        # Keep the swatch's own content, and the state tracking which object
        # to replace next -- Reset changes STYLING, not what has been typed
        # or what is currently on screen. The four last_* readouts describe
        # ONE build together (see _stale(), which clears all four in one
        # go for exactly this reason) -- keeping only two of them used to
        # leave the panel showing a report with no stroke or shrink figure
        # after a Reset, describing a build that no longer fully exists.
        # (Since 0.14.0 the panel itself only draws three of the four --
        # last_report moved into the status bar only -- but the property
        # still exists and self.report() still reads it, so it stays here.)
        keep = {"brand", "type", "color", "last_swatch", "last_report",
               "last_warning", "last_stroke", "last_shrunk", "rna_type",
               "name"}
        restored = 0
        for key in props.bl_rna.properties.keys():
            if key in keep:
                continue
            try:
                props.property_unset(key)
                restored += 1
            except Exception:
                pass
        self.report({'INFO'}, f"Reset {restored} settings")
        return {'FINISHED'}


class MAGPIESWATCHES_OT_fix_units(bpy.types.Operator):
    """Tell Blender the scene is in millimetres.

    Everything this add-on builds is in mm. Blender defaults to one unit
    being one METRE, so a 24 mm plate reads as "24 m" in the UI. Export STL
    is unaffected (that format carries no unit at all), and Export FBX
    above compensates for the scene's units on its own -- see
    MAGPIESWATCHES_OT_export_fbx -- so both exports come out correct
    whether or not this button is ever clicked. What is left is purely
    cosmetic: this only changes what the numbers in Blender's own UI read.

    Only the unit SETTINGS change here. No object moves and nothing is
    rescaled; the swatch was always the right size, Blender was just
    labelling it wrong.
    """

    bl_idname = f"{OP}.fix_units"
    bl_label = "Set Scene to Millimetres"
    bl_description = ("Set the scene's units to millimetres, so Blender's "
                      "own UI reads the sizes correctly. Nothing moves, "
                      "changes size, or affects either export")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        units = context.scene.unit_settings
        units.system = 'METRIC'
        units.scale_length = SCENE_UNIT_SCALE
        units.length_unit = 'MILLIMETERS'
        self.report({'INFO'}, "Scene units set to millimetres")
        return {'FINISHED'}
