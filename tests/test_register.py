"""Register/unregister cycle, plus one real end-to-end build through the UI
layer (properties -> operator -> engine -> export), not just the engine
directly like the other tests.

    blender --background --factory-startup --python tests/test_register.py

Unlike the other test_*.py files, this one imports the REAL magpie_swatches
package (with the repo root on sys.path) instead of _pkg.py's synthetic
engine-only stand-in, because the whole point here is to exercise ui/, which
_pkg.py deliberately keeps out of the engine tests' way.

WARNING: Blender exits 0 even when a script raises -- a runner must grep for
'Traceback' as well as reading the RESULT line.
"""

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bpy  # noqa: E402

import magpie_swatches  # noqa: E402

_fails = []


def check(tag, ok, detail=""):
    print(f"[{tag}] {'ok' if ok else 'FAIL'} {detail}")
    if not ok:
        _fails.append(tag)


def near(a, b, tol):
    return abs(a - b) <= tol


def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def test_register_cycle_three_times():
    for i in range(3):
        magpie_swatches.register()
        check(f"register.has_scene_prop[{i}]",
              hasattr(bpy.types.Scene, "magpie_swatches"))
        check(f"register.class_present[{i}]",
              hasattr(bpy.types, "MAGPIESWATCHES_PT_main"))
        # Operators are looked up via bpy.ops.<module>.<name> (the bl_idname),
        # not via bpy.types.<ClassName> the way Panels/PropertyGroups are --
        # that is normal Blender behaviour, not something to test against.
        check(f"register.operator_present[{i}]",
              hasattr(bpy.ops.magpie_swatches, "generate"))

        magpie_swatches.unregister()
        check(f"unregister.scene_prop_gone[{i}]",
              not hasattr(bpy.types.Scene, "magpie_swatches"))
        check(f"unregister.class_gone[{i}]",
              not hasattr(bpy.types, "MAGPIESWATCHES_PT_main"))


def test_end_to_end_through_operators():
    """Generate through bpy.ops (not build_swatch() directly), then export --
    this is the path that would break if properties.py, operators.py and
    engine/swatch.py disagreed about SwatchParams' shape, which none of the
    engine-only tests can catch."""
    fresh()
    magpie_swatches.register()
    try:
        scene = bpy.context.scene
        p = scene.magpie_swatches
        p.brand = "Sunlu"
        p.type = "PLA Matte"
        p.color = "Marrom Cafe"

        result = bpy.ops.magpie_swatches.generate()
        check("e2e.generate_finished", result == {'FINISHED'}, str(result))
        check("e2e.last_swatch_set", p.last_swatch is not None)
        check("e2e.last_report_set", bool(p.last_report), p.last_report)

        first_obj = p.last_swatch
        first_name = first_obj.name  # read while still alive -- regenerate
                                     # frees the underlying data below, and
                                     # touching ANY attribute of a removed
                                     # object raises ReferenceError
        result2 = bpy.ops.magpie_swatches.generate()
        check("e2e.regenerate_finished", result2 == {'FINISHED'}, str(result2))
        check("e2e.regenerate_replaced", p.last_swatch is not first_obj)
        check("e2e.old_object_removed", first_name not in bpy.data.objects,
              "regenerate must not leave an orphan behind")

        tmp = Path(tempfile.mkdtemp(prefix="ms_export_"))
        try:
            result3 = bpy.ops.magpie_swatches.export(
                filepath=str(tmp / "e2e export.stl"))
            check("e2e.export_finished", result3 == {'FINISHED'}, str(result3))
            stls = list(tmp.glob("*.stl"))
            check("e2e.export_wrote_a_file", len(stls) == 1,
                  [f.name for f in stls])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

        result4 = bpy.ops.magpie_swatches.reset()
        check("e2e.reset_finished", result4 == {'FINISHED'}, str(result4))
        check("e2e.reset_kept_text", p.brand == "Sunlu", p.brand)
        check("e2e.reset_kept_last_swatch", p.last_swatch is not None)
    finally:
        magpie_swatches.unregister()


def test_add_swatch_button():
    """Add Swatch inserts the bare plate even with all three fields filled in
    -- that is the whole point of it being a separate button from Generate."""
    fresh()
    magpie_swatches.register()
    try:
        p = bpy.context.scene.magpie_swatches
        p.brand = "Sunlu"
        p.type = "PLA Matte"
        p.color = "Marrom Cafe"

        check("add_swatch.button_is_live",
              bpy.ops.magpie_swatches.add_swatch.poll())
        result = bpy.ops.magpie_swatches.add_swatch()
        check("add_swatch.finished", result == {'FINISHED'}, str(result))
        check("add_swatch.is_blank", p.last_swatch.name == "Blank - SWATCH",
              str(p.last_swatch.name if p.last_swatch else None))

        # ...and Generate then replaces that blank with the lettered swatch,
        # using the text that was sitting in the fields all along.
        blank_name = p.last_swatch.name
        result2 = bpy.ops.magpie_swatches.generate()
        check("add_swatch.generate_replaces_it", result2 == {'FINISHED'},
              str(result2))
        check("add_swatch.now_lettered",
              p.last_swatch.name == "Sunlu - SWATCH",
              str(p.last_swatch.name if p.last_swatch else None))
        check("add_swatch.no_orphan", blank_name not in bpy.data.objects)
    finally:
        magpie_swatches.unregister()


def test_generate_works_with_all_empty():
    """The fresh-install case: nothing typed yet, and Generate must still be
    clickable AND actually insert geometry (the blank plate). A greyed-out
    Generate here is what made the add-on look like it had no way to insert
    anything at all."""
    fresh()
    magpie_swatches.register()
    try:
        p = bpy.context.scene.magpie_swatches
        p.brand = p.type = p.color = ""
        check("blank.button_is_live", bpy.ops.magpie_swatches.generate.poll())

        result = bpy.ops.magpie_swatches.generate()
        check("blank.generate_finished", result == {'FINISHED'}, str(result))
        check("blank.object_created", p.last_swatch is not None)
        check("blank.named", p.last_swatch.name == "Blank - SWATCH",
              str(p.last_swatch.name if p.last_swatch else None))
    finally:
        magpie_swatches.unregister()


def test_export_honours_a_custom_filename():
    """The name typed into the export window has to be the name on disk --
    before 0.6.0 the operator only accepted a FOLDER and derived the name
    from the object, so there was no way to choose it.

    Tested through execute() (calling the operator with filepath= directly),
    not invoke() -- invoke() opens a modal file browser that does not run
    under --background.
    """
    fresh()
    magpie_swatches.register()
    try:
        p = bpy.context.scene.magpie_swatches
        p.brand, p.type, p.color = "Sunlu", "PLA", "Preto"
        bpy.ops.magpie_swatches.generate()

        tmp = Path(tempfile.mkdtemp(prefix="ms_filename_"))
        try:
            # 1. A custom name is honoured verbatim, not overridden by the
            # object's own name ("Sunlu - SWATCH").
            chosen = tmp / "Sunlu PLA Preto.stl"
            result = bpy.ops.magpie_swatches.export(filepath=str(chosen))
            check("filename.custom_finished", result == {'FINISHED'},
                  str(result))
            check("filename.custom_name_used", chosen.is_file(),
                  [f.name for f in tmp.glob("*.stl")])
            check("filename.no_object_name_fallback",
                  not (tmp / "Sunlu - SWATCH.stl").exists())

            # 2. A name typed without an extension still gets one -- a .stl
            # with no extension will not open with a double-click in a
            # slicer.
            no_ext = tmp / "sem extensao"
            result2 = bpy.ops.magpie_swatches.export(filepath=str(no_ext))
            check("filename.no_ext_finished", result2 == {'FINISHED'},
                  str(result2))
            check("filename.extension_added",
                  (tmp / "sem extensao.stl").is_file(),
                  [f.name for f in tmp.glob("*")])

            # 3. Neither file is an empty stub a slicer would choke on.
            check("filename.custom_not_empty", chosen.stat().st_size > 0)
            check("filename.no_ext_not_empty",
                  (tmp / "sem extensao.stl").stat().st_size > 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    finally:
        magpie_swatches.unregister()


def test_plate_size_selector_applies_and_builds():
    """Setting plate_size (the segmented toggle's own property) writes the
    whole calibrated set, and a Generate right after still builds -- proving
    the applied values are actually valid SwatchParams together, not just
    individually plausible numbers.

    FloatProperty is single precision and PLATE_PRESETS holds
    double-precision Python literals, so a value written and read back does
    NOT compare exactly -- MEASURED on Blender 4.2: type_size 4.2 reads
    back as 4.199999809265137, an error of 1.9e-07. Every comparison here
    uses near() with a tolerance loose enough to clear that (500x, at
    1e-4 mm -- a tenth of a micron, geometrically irrelevant), never `==`.
    """
    fresh()
    magpie_swatches.register()
    try:
        p = bpy.context.scene.magpie_swatches
        p.brand, p.type, p.color = "Sunlu", "PLA Matte", "Marrom Cafe"

        p.plate_size = 'P35'
        check("platesize.applied_plate_w", near(p.plate_w, 35.0, 1e-4),
              p.plate_w)
        check("platesize.applied_plate_h", near(p.plate_h, 35.0, 1e-4),
              p.plate_h)
        check("platesize.applied_type_size", near(p.type_size, 4.2, 1e-4),
              p.type_size)
        check("platesize.applied_bottom_margin",
              near(p.bottom_margin, 3.0, 1e-4), p.bottom_margin)

        result = bpy.ops.magpie_swatches.generate()
        check("platesize.generate_after_finished", result == {'FINISHED'},
              str(result))
        check("platesize.generated_at_the_new_size",
              near(p.last_swatch.dimensions.x, 35.0, 0.5),
              p.last_swatch.dimensions.x)

        # Switching back must not leave any 35 mm field behind -- the whole
        # point of writing every field on every change, not just the ones
        # that differ from the current values.
        p.plate_size = 'P24'
        check("platesize.back_to_24_w", near(p.plate_w, 24.0, 1e-4), p.plate_w)
        check("platesize.back_to_24_type_size",
              near(p.type_size, 3.0, 1e-4), p.type_size)
        check("platesize.back_to_24_bottom_margin",
              near(p.bottom_margin, 1.5, 1e-4), p.bottom_margin)
    finally:
        magpie_swatches.unregister()


def test_plate_size_default_matches_shipped_defaults():
    """A fresh install's plate_size default is P24, and it has to actually
    match what the add-on already builds by default -- a segmented toggle
    that starts lit on a size other than the real default would be lying
    from the very first Generate."""
    fresh()
    magpie_swatches.register()
    try:
        p = bpy.context.scene.magpie_swatches
        check("platesize.default_is_p24", p.plate_size == 'P24', p.plate_size)
        check("platesize.default_matches_plate_w",
              near(p.plate_w, 24.0, 1e-6), p.plate_w)
        check("platesize.default_matches_plate_h",
              near(p.plate_h, 24.0, 1e-6), p.plate_h)
    finally:
        magpie_swatches.unregister()


def test_export_fbx_compensates_for_scene_units():
    """FBX (unlike STL) applies the scene's own unit scale on export by
    default -- MEASURED (see docs/decisions/AJUSTES-0.9.0.md): a metric-default scene
    (1 unit = 1 m, Blender's own default) produces an FBX 1000x too large
    unless something compensates. Export FBX compensates itself (see
    MAGPIESWATCHES_OT_export_fbx), so the file it writes must come out the
    SAME physical size whether the scene was in metres or already in
    millimetres when it was written -- that is the only way to prove the
    compensation actually works, since a broken version would still write a
    file with no error either way.
    """
    tmp = Path(tempfile.mkdtemp(prefix="ms_fbx_"))
    try:
        widths = {}
        for label, to_mm in (("metres", False), ("millimetres", True)):
            fresh()
            magpie_swatches.register()
            try:
                scene = bpy.context.scene
                if to_mm:
                    bpy.ops.magpie_swatches.fix_units()
                p = scene.magpie_swatches
                p.brand, p.type, p.color = "Sunlu", "PLA", "Preto"
                bpy.ops.magpie_swatches.generate()

                target = tmp / f"{label}.fbx"
                result = bpy.ops.magpie_swatches.export_fbx(
                    filepath=str(target))
                check(f"fbx.{label}_finished", result == {'FINISHED'},
                      str(result))
                check(f"fbx.{label}_file_written", target.is_file())
            finally:
                magpie_swatches.unregister()

            # Reimport into a totally clean, DEFAULT-unit scene (read_
            # factory_settings resets scene.unit_settings along with
            # everything else -- factory default is METRIC, scale_length
            # 1.0, i.e. 1 Blender unit = 1 real-world metre) and measure
            # what actually landed. import_scene.fbx has its own
            # apply_unit_scale=True default, so the number that lands here
            # is already real-world metres -- a correctly-sized 24 mm plate
            # reads as 0.024 Blender units in THIS scene, not 24. Converting
            # by *1000 is what makes that comparable to a millimetre figure;
            # asserting a bare 24.0 here would be checking the wrong thing.
            fresh()
            before = set(bpy.data.objects.keys())
            bpy.ops.import_scene.fbx(filepath=str(target))
            imported = [o for o in bpy.data.objects
                       if o.name not in before]
            check(f"fbx.{label}_reimported", len(imported) == 1,
                  [o.name for o in imported])
            if imported:
                bpy.context.view_layer.update()
                width_mm = imported[0].dimensions.x * 1000.0
                widths[label] = width_mm
                check(f"fbx.{label}_is_24mm", near(width_mm, 24.0, 1.0),
                      f"{width_mm:.3f} mm")

        if "metres" in widths and "millimetres" in widths:
            check("fbx.both_scene_states_match",
                  near(widths["metres"], widths["millimetres"], 0.5),
                  f"metres scene -> {widths['metres']:.3f} mm, "
                  f"mm scene -> {widths['millimetres']:.3f} mm")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_auto_shrink_is_a_readout_not_a_warning():
    """Auto-shrink used to be reported as an actionable warning, which
    OUTRANKED the printable-stroke warning in the same slot -- only the
    first actionable note reaches last_warning, and auto-shrink was
    appended first. A colour name long enough to both shrink AND fall
    under the printable floor reported "Color auto-shrunk to fit the
    plate" and hid "thinnest stroke ... is under 0.45 mm" entirely.

    "Cinza Chumbo" at the shipped defaults on a 24 mm plate is exactly that
    case (see constants.py's measured width-per-mm table and
    docs/decisions/AJUSTES-0.10.0.md). This is the regression test for the fix: the
    stroke warning must be the one that reaches the panel, and the
    shrink note must be its own readout instead.
    """
    fresh()
    magpie_swatches.register()
    try:
        p = bpy.context.scene.magpie_swatches
        p.brand, p.type, p.color = "Sunlu", "PLA Matte", "Cinza Chumbo"
        result = bpy.ops.magpie_swatches.generate()
        check("shrink.generate_finished", result == {'FINISHED'}, str(result))

        check("shrink.last_shrunk_set", bool(p.last_shrunk), p.last_shrunk)
        check("shrink.last_shrunk_names_color", "Color" in p.last_shrunk,
              p.last_shrunk)
        check("shrink.last_shrunk_is_parenthesised",
              p.last_shrunk.startswith("(") and p.last_shrunk.endswith(")"),
              p.last_shrunk)

        check("shrink.last_warning_is_about_stroke",
              "stroke" in p.last_warning.lower(), p.last_warning)
        check("shrink.last_warning_not_about_shrink",
              "shrunk" not in p.last_warning.lower(), p.last_warning)
    finally:
        magpie_swatches.unregister()


def test_reset_keeps_all_four_readouts_together():
    """_stale() clears last_report, last_warning, last_stroke and
    last_shrunk as one group, because together they describe ONE build --
    Reset's own `keep` set used to preserve only two of the four, so a
    Reset after a Generate left the panel showing a stale report with no
    stroke or shrink figure next to it, describing a build that only
    half still applied.

    "Cinza Chumbo" is reused from the auto-shrink test above because it is
    the one scenario already known to populate all four at once: a report
    (every build gets one), a stroke readout (every lettered build gets
    one), a shrink readout (the Color line shrinks) and a warning (the
    resulting stroke falls under the printable floor).
    """
    fresh()
    magpie_swatches.register()
    try:
        p = bpy.context.scene.magpie_swatches
        p.brand, p.type, p.color = "Sunlu", "PLA Matte", "Cinza Chumbo"
        bpy.ops.magpie_swatches.generate()
        before = (p.last_report, p.last_warning, p.last_stroke,
                 p.last_shrunk)
        check("reset.all_four_populated_before", all(before), before)

        result = bpy.ops.magpie_swatches.reset()
        check("reset.finished", result == {'FINISHED'}, str(result))

        after = (p.last_report, p.last_warning, p.last_stroke,
                 p.last_shrunk)
        check("reset.all_four_survived_together", after == before,
              f"before {before}\nafter  {after}")
    finally:
        magpie_swatches.unregister()


try:
    for fn in (test_register_cycle_three_times,
              test_end_to_end_through_operators, test_add_swatch_button,
              test_generate_works_with_all_empty,
              test_export_honours_a_custom_filename,
              test_plate_size_selector_applies_and_builds,
              test_plate_size_default_matches_shipped_defaults,
              test_export_fbx_compensates_for_scene_units,
              test_auto_shrink_is_a_readout_not_a_warning,
              test_reset_keeps_all_four_readouts_together):
        fn()
except Exception as exc:
    import traceback
    traceback.print_exc()
    _fails.append(f"EXCEPTION: {exc}")

print(f"RESULT: {'FAIL -> ' + ', '.join(_fails) if _fails else 'PASS'}")
sys.exit(1 if _fails else 0)
