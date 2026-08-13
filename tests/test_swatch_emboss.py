"""The decisive smoke test: does the emboss boolean actually work on this
Blender build?

    blender --background --factory-startup --python tests/test_swatch_emboss.py

This is the test that decides blender_manifest.toml's blender_version_min (see
docs/decisions/IMPLEMENTATION_PLAN.md R1). GingerCutter measured its equivalent union silently
no-op'ing on 4.2 -- reporting success while merging nothing. If that happens
here, engine/booleans.py raises BooleanError instead of shipping a blank plate,
and this test fails LOUDLY, which is exactly the signal needed to decide
whether 4.2.0 can stay as the floor.

Deviation from the original plan: the plan called for driving the post-boolean
check through the bundled 3D Print Toolbox. Measured instead: that add-on is
NOT present in a stock Blender 4.2 install on this machine (absent from
addon_utils.modules() entirely), and on 5.2 it is only there because it was
installed by hand as a user extension (bl_ext.user_default.print3d_toolbox) --
not guaranteed on a clean CI runner either way. Hand-rolling the two checks
that matter -- manifold, and consistent face winding -- avoids a dependency on
an add-on this project cannot guarantee is installed, without losing anything
the toolbox would have told us.

WARNING: Blender exits 0 even when a script raises -- a runner must grep for
'Traceback' as well as reading the RESULT line.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy  # noqa: E402
import _pkg  # noqa: E402

_pkg.load()

from magpie_swatches.constants import (DEFAULT_HOOK_SIZE,  # noqa: E402
                                       HOLE_HOOK, HOLE_ROUND, MIN_STROKE,
                                       MODE_DEBOSS, MODE_EMBOSS,
                                       PLATE_PRESET_24, PLATE_PRESET_35,
                                       PLATE_PRESETS, TEXT_MARGIN, TYPE_KEY,
                                       TYPE_SWATCH)
from magpie_swatches.engine import hook, plate  # noqa: E402
from magpie_swatches.engine.swatch import SwatchParams, build_swatch  # noqa: E402

_fails = []


def check(tag, ok, detail=""):
    print(f"[{tag}] {'ok' if ok else 'FAIL'} {detail}")
    if not ok:
        _fails.append(tag)


def near(a, b, tol):
    return abs(a - b) <= tol


def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def manifold(mesh):
    counts = {}
    for poly in mesh.polygons:
        for k in poly.edge_keys:
            counts[k] = counts.get(k, 0) + 1
    return all(c == 2 for c in counts.values())


def normals_consistent(mesh):
    """True when every shared edge is walked in opposite directions by its two
    faces -- the signature of a consistently outward-facing surface.

    A manifold count alone misses a flipped-normal seam: the edge is still
    shared by exactly two faces, so it reads as fine, but if both faces
    traverse it the SAME way instead of opposite ways, the surface folds back
    on itself there. That is exactly the kind of defect a boolean at a thin
    glyph contour can leave behind. Counting directed edges catches it: a
    clean 2-manifold has each directed (a, b) pair appear at most once.
    """
    seen = {}
    for poly in mesh.polygons:
        verts = list(poly.vertices)
        n = len(verts)
        for i in range(n):
            a, b = verts[i], verts[(i + 1) % n]
            if (a, b) in seen:
                return False
            seen[(a, b)] = poly.index
    return True


def volume(mesh):
    import bmesh
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        return bm.calc_volume()
    finally:
        bm.free()


def islands(mesh):
    """How many separate connected pieces the mesh is in -- see test_hook.py,
    which uses the identical helper for the same reason: a shape that fully
    encircled the tongue would cut it loose, and this is what would notice."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    seen, count = set(), 0
    for v in bm.verts:
        if v.index in seen:
            continue
        count += 1
        stack = [v]
        seen.add(v.index)
        while stack:
            cur = stack.pop()
            for e in cur.link_edges:
                other = e.other_vert(cur)
                if other.index not in seen:
                    seen.add(other.index)
                    stack.append(other)
    bm.free()
    return count


PLATE_W, PLATE_H, THICK, RADIUS, SEG = 24.0, 24.0, 2.0, 2.0, 16


def base_params(**overrides):
    base = dict(
        brand="Sunlu", type="PLA Matte", color="Marrom Cafe",
        brand_size=3.0, type_size=4.5, color_size=3.5,
        plate_w=PLATE_W, plate_h=PLATE_H, thickness=THICK,
        corner_radius=RADIUS, corner_segments=SEG,
        hole=True, hole_diameter=3.5,
        mode=MODE_EMBOSS, relief=0.4, engrave=0.5,
    )
    base.update(overrides)
    return SwatchParams(**base)


def test_emboss_with_hole():
    fresh()
    result = build_swatch(base_params())
    obj = result.obj
    check("emboss.manifold", manifold(obj.data))
    check("emboss.normals_consistent", normals_consistent(obj.data))
    check("emboss.tagged", obj.get(TYPE_KEY) == TYPE_SWATCH,
          str(obj.get(TYPE_KEY)))
    check("emboss.named", obj.name == "Sunlu - SWATCH", obj.name)

    zs = [v.co.z for v in obj.data.vertices]
    check("emboss.floor_untouched", near(min(zs), 0.0, 0.05),
          f"min z {min(zs):.3f}")
    check("emboss.relief_rises_above_face",
          near(max(zs), THICK + 0.4, 0.05), f"max z {max(zs):.3f}")


def test_emboss_adds_material():
    """The whole point of the boolean: the plate+text volume must be BIGGER
    than a plain plate of the same footprint. If the union silently no-op'd
    (the GingerCutter 4.2 failure mode), the text would be gone and this
    would be false even though nothing raised."""
    fresh()
    plain = plate.create_plate(PLATE_W, PLATE_H, THICK, RADIUS, SEG, "plain")
    plain_vol = volume(plain.data)

    fresh()
    result = build_swatch(base_params(hole=False))
    swatch_vol = volume(result.obj.data)

    check("emboss.volume_grew", swatch_vol > plain_vol,
          f"swatch {swatch_vol:.2f} vs plain {plain_vol:.2f} mm3")


def test_emboss_no_hole():
    fresh()
    result = build_swatch(base_params(hole=False))
    check("emboss.no_hole.manifold", manifold(result.obj.data))
    check("emboss.no_hole.normals_consistent",
          normals_consistent(result.obj.data))


def test_text_is_left_aligned_and_bottom_anchored():
    """Layout contract: every line starts at the same left margin, the block
    sits on the bottom margin, and it never reaches the hole's row.

    The lines are welded into one mesh, so per-line positions cannot be read
    back off the object. What CAN be checked is the block as a whole plus the
    thing left-alignment is actually for: a long line and a short one must
    start at the same x, so a swatch's text reads as a column rather than as
    three separately-centred strips.
    """
    fresh()
    short = build_swatch(base_params(brand="A", type="", color=""))
    left_short = min(v.co.x for v in short.obj.data.vertices
                     if v.co.z > THICK + 0.01)

    fresh()
    # Long enough to prove the two are not both merely centred, short enough
    # to fit without the auto-shrink kicking in and changing the comparison.
    long_ = build_swatch(base_params(brand="ABCDEFGH", type="", color=""))
    left_long = min(v.co.x for v in long_.obj.data.vertices
                    if v.co.z > THICK + 0.01)

    check("layout.left_aligned", near(left_short, left_long, 0.05),
          f"short starts at x={left_short:.3f}, long at x={left_long:.3f}")
    check("layout.at_left_margin",
          near(left_short, -PLATE_W / 2 + TEXT_MARGIN, 0.15),
          f"x={left_short:.3f}, expected ~{-PLATE_W / 2 + TEXT_MARGIN:.3f}")

    fresh()
    full = build_swatch(base_params())
    glyphs = [v.co for v in full.obj.data.vertices if v.co.z > THICK + 0.01]
    bottom = min(c.y for c in glyphs)
    top = max(c.y for c in glyphs)
    check("layout.bottom_anchored",
          near(bottom, -PLATE_H / 2 + TEXT_MARGIN, 0.15),
          f"lowest glyph at y={bottom:.3f}, margin at "
          f"{-PLATE_H / 2 + TEXT_MARGIN:.3f}")

    # the hole is top-left; the text must stop below it
    hole_cx, hole_cy = plate.hole_center(PLATE_W, PLATE_H, 3.75)
    check("layout.hole_is_on_the_left", hole_cx < 0, f"hole cx={hole_cx:.3f}")
    check("layout.clears_the_hole", top < hole_cy - 3.5 / 2,
          f"text tops out at y={top:.3f}, hole starts at "
          f"{hole_cy - 3.5 / 2:.3f}")


def test_text_too_tall_is_refused():
    """There is no vertical auto-shrink, so text that cannot fit above the
    bottom margin and below the hole must say so rather than run through it.

    Single letters on purpose: the auto-shrink is horizontal, so a long string
    at a huge size just gets shrunk back down to fit the width and never ends
    up tall. One narrow character per line is what actually reaches the
    ceiling.
    """
    fresh()
    try:
        build_swatch(base_params(brand="A", type="B", color="C",
                                 brand_size=9.0, type_size=9.0,
                                 color_size=9.0))
        check("layout.rejects_too_tall", False, "accepted text taller than "
              "the plate")
    except Exception as exc:
        check("layout.rejects_too_tall", "too tall" in str(exc).lower(),
              f"{type(exc).__name__}: {exc}")


def test_blank_plate():
    """No text at all builds the BLANK PLATE rather than raising.

    Generate must work on the very first click of a fresh install, when every
    field is still empty -- a disabled button there makes the add-on look like
    it has no way to insert anything at all. Checked in both modes: with
    nothing to emboss or deboss, each must come back as the plain plate, not
    as a plate with a stray boolean applied to it.
    """
    fresh()
    plain = plate.create_plate(PLATE_W, PLATE_H, THICK, RADIUS, SEG, "plain")
    plain_vol = volume(plain.data)

    for mode in (MODE_EMBOSS, MODE_DEBOSS):
        fresh()
        result = build_swatch(base_params(brand="", type="", color="",
                                          hole=False, mode=mode))
        obj = result.obj
        check(f"blank.manifold[{mode}]", manifold(obj.data))
        check(f"blank.normals_consistent[{mode}]",
              normals_consistent(obj.data))
        check(f"blank.tagged[{mode}]", obj.get(TYPE_KEY) == TYPE_SWATCH)
        check(f"blank.named[{mode}]", obj.name == "Blank - SWATCH", obj.name)
        check(f"blank.no_label[{mode}]", result.label is None)
        got = volume(obj.data)
        check(f"blank.is_the_plain_plate[{mode}]", near(got, plain_vol, 0.01),
              f"{got:.3f} vs plain {plain_vol:.3f} mm3")
        zs = [v.co.z for v in obj.data.vertices]
        check(f"blank.no_relief[{mode}]", near(max(zs), THICK, 0.001),
              f"max z {max(zs):.4f}")


def test_blank_plate_with_hole():
    """The blank plate still gets its hanging hole -- the hole is part of the
    plate, not part of the text stage that gets skipped."""
    fresh()
    solid = build_swatch(base_params(brand="", type="", color="", hole=False))
    solid_vol = volume(solid.obj.data)

    fresh()
    holed = build_swatch(base_params(brand="", type="", color="", hole=True))
    check("blank_hole.manifold", manifold(holed.obj.data))
    check("blank_hole.removes_material", volume(holed.obj.data) < solid_vol,
          f"{volume(holed.obj.data):.2f} vs {solid_vol:.2f} mm3")


def test_emboss_with_hook_style():
    """The hook style, end to end: cuts a real cavity shaped like the
    spiral (not a round hole), and the text correctly clears its full
    reach -- not just a diameter, which is what the round style's own
    ceiling check uses and would be wrong here.

    Single field on purpose: base_params()'s three-line fixture predates the
    hook and uses larger text sizes than the product's own recalibrated
    defaults (see constants.py) -- fine for the round hole's smaller
    footprint, but the hook reaches farther and the two together leave no
    room. That is a fixture/product mismatch, not a defect this test is
    meant to catch; one line sidesteps it while still exercising the real
    hook-cutting and ceiling logic.
    """
    fresh()
    plain = plate.create_plate(PLATE_W, PLATE_H, THICK, RADIUS, SEG, "plain")
    plain_vol = volume(plain.data)

    fresh()
    result = build_swatch(base_params(hole_style=HOLE_HOOK, type="", color=""))
    obj = result.obj
    check("hook_style.manifold", manifold(obj.data))
    check("hook_style.normals_consistent", normals_consistent(obj.data))
    check("hook_style.removes_material", volume(obj.data) < plain_vol,
          f"{volume(obj.data):.2f} vs plain {plain_vol:.2f} mm3")

    glyphs = [v.co for v in obj.data.vertices if v.co.z > THICK + 0.01]
    top = max(c.y for c in glyphs)
    inset = hook.hook_inset(DEFAULT_HOOK_SIZE)
    # How far it reaches DOWN specifically -- the hook is taller than it is
    # wide, and the text only ever meets its lowest point.
    _, min_y, _, _ = hook.hook_bounds(DEFAULT_HOOK_SIZE)
    reach = -min_y
    _, hole_cy = plate.hole_center(PLATE_W, PLATE_H, inset)
    check("hook_style.text_clears_hook", top < hole_cy - reach,
          f"text tops out at y={top:.3f}, hook starts at "
          f"{hole_cy - reach:.3f}")


def test_shipped_defaults_actually_generate():
    """The exact configuration a fresh install ships MUST build.

    This is the test that was missing when the hook landed: every other test
    in this file uses base_params()'s own fixture values, which predate the
    recalibrated text sizes -- so the whole suite stayed green while the
    SHIPPED defaults left only 0.5 mm of clearance between the text block and
    the hook, and any swatch with slightly larger text than default failed
    outright with "text is too tall for the plate". Reported from the GUI, not
    caught here.

    Pulls every value from constants.py rather than restating them, so it
    tracks the product's real defaults instead of a copy that can drift.
    """
    from magpie_swatches.constants import (DEFAULT_BRAND_SIZE,
                                           DEFAULT_COLOR_SIZE,
                                           DEFAULT_CORNER_RADIUS,
                                           DEFAULT_HOLE, DEFAULT_HOLE_DIAMETER,
                                           DEFAULT_HOLE_STYLE, DEFAULT_PLATE_H,
                                           DEFAULT_PLATE_THICK,
                                           DEFAULT_PLATE_W, DEFAULT_RELIEF,
                                           DEFAULT_TYPE_SIZE)

    for style in (HOLE_HOOK, HOLE_ROUND):
        fresh()
        shipped = SwatchParams(
            brand="Sunlu", type="PLA Matte", color="Marrom Cafe",
            brand_size=DEFAULT_BRAND_SIZE, type_size=DEFAULT_TYPE_SIZE,
            color_size=DEFAULT_COLOR_SIZE,
            plate_w=DEFAULT_PLATE_W, plate_h=DEFAULT_PLATE_H,
            thickness=DEFAULT_PLATE_THICK,
            corner_radius=DEFAULT_CORNER_RADIUS, corner_segments=SEG,
            hole=DEFAULT_HOLE, hole_diameter=DEFAULT_HOLE_DIAMETER,
            mode=MODE_EMBOSS, relief=DEFAULT_RELIEF, engrave=0.5,
            hole_style=style,
        )
        try:
            result = build_swatch(shipped)
            check(f"defaults.generate[{style}]", True)
            check(f"defaults.manifold[{style}]", manifold(result.obj.data))
        except Exception as exc:
            check(f"defaults.generate[{style}]", False,
                  f"{type(exc).__name__}: {exc}")

    # ...and the same thing half a millimetre UP on every line. A default
    # that only just fits is a default that breaks the moment anyone nudges
    # it, which is exactly how this reached the GUI: before the fix, +0.3 mm
    # per line was already enough to fail outright.
    #
    # SHORT strings on purpose. The auto-shrink is HORIZONTAL, so raising the
    # size of a long name ("Marrom Cafe") just makes it too wide, shrinks it
    # straight back, and the block never actually gets taller -- a version of
    # this test written with the long names passed happily against the very
    # bug it was written to catch. Short names never hit the width limit, so
    # the extra size becomes real height.
    #
    # MEASURED discriminator at +0.5: fails on the pre-fix code, passes on
    # this one, which still has room up to about +0.8.
    fresh()
    roomier = SwatchParams(
        brand="Sunlu", type="PETG", color="Preto",
        brand_size=DEFAULT_BRAND_SIZE + 0.5,
        type_size=DEFAULT_TYPE_SIZE + 0.5,
        color_size=DEFAULT_COLOR_SIZE + 0.5,
        plate_w=DEFAULT_PLATE_W, plate_h=DEFAULT_PLATE_H,
        thickness=DEFAULT_PLATE_THICK, corner_radius=DEFAULT_CORNER_RADIUS,
        corner_segments=SEG, hole=DEFAULT_HOLE,
        hole_diameter=DEFAULT_HOLE_DIAMETER, mode=MODE_EMBOSS,
        relief=DEFAULT_RELIEF, engrave=0.5, hole_style=DEFAULT_HOLE_STYLE,
    )
    try:
        build_swatch(roomier)
        check("defaults.headroom_for_bigger_text", True)
    except Exception as exc:
        check("defaults.headroom_for_bigger_text", False,
              f"{type(exc).__name__}: {exc}")


def test_round_style_still_works_when_named_explicitly():
    """Every other test in this file relies on ROUND being the dataclass
    default -- this confirms asking for it BY NAME produces the identical
    result, so the hook feature is proven additive, not a change to the
    path every other test already exercises."""
    fresh()
    explicit = build_swatch(base_params(hole_style=HOLE_ROUND))
    # Read the volume NOW: fresh() below wipes bpy.data entirely
    # (read_factory_settings), which turns `explicit.obj` into a dangling
    # reference -- touching it afterwards raises ReferenceError, the same
    # trap the family's own test_register.py hit before this session.
    explicit_vol = volume(explicit.obj.data)

    fresh()
    implicit = build_swatch(base_params())
    implicit_vol = volume(implicit.obj.data)

    check("round_style.matches_default",
          near(explicit_vol, implicit_vol, 1e-6),
          f"{explicit_vol:.4f} vs {implicit_vol:.4f}")


def test_hole_offset_zero_is_additive():
    """(0, 0) must build EXACTLY what omitting the offset entirely already
    builds -- proves the offset is additive on top of the derived position,
    not a replacement for it, which is what makes it safe to ship on top of
    every swatch already out there with no offset set at all."""
    fresh()
    baseline = build_swatch(base_params(hole_style=HOLE_HOOK, type="",
                                        color=""))
    baseline_vol = volume(baseline.obj.data)

    fresh()
    explicit = build_swatch(base_params(hole_style=HOLE_HOOK, type="",
                                        color="", hole_offset_x=0.0,
                                        hole_offset_y=0.0))
    check("offset.zero_is_additive",
          near(volume(explicit.obj.data), baseline_vol, 1e-6),
          f"{volume(explicit.obj.data):.4f} vs {baseline_vol:.4f}")


def test_lateral_hole_offset_keeps_one_piece():
    """A sideways-and-down nudge must still cut a clean, single-piece
    swatch -- proving the offset reaches the REAL cut in build_swatch(), not
    just a number reported back to the panel."""
    fresh()
    result = build_swatch(base_params(hole_style=HOLE_HOOK, type="",
                                      color="", hole_offset_x=2.0,
                                      hole_offset_y=-1.0))
    check("offset.lateral_manifold", manifold(result.obj.data))
    check("offset.lateral_one_piece", islands(result.obj.data) == 1,
          str(islands(result.obj.data)))


def test_hole_offset_into_lower_half_is_rejected_by_the_hole_not_the_text():
    """A Y offset that pushes the hole below the plate's own middle must be
    refused by validate.check() -- BEFORE any text layout runs -- with an
    error naming the HOLE. If this fell through to _anchor_label() instead,
    the user would see "text is too tall for the plate" for a problem they
    caused by moving the hole, not the text.
    """
    fresh()
    size = DEFAULT_HOOK_SIZE
    inset = hook.hook_inset(size)
    _, base_cy = plate.hole_center(PLATE_W, PLATE_H, inset)
    try:
        build_swatch(base_params(hole_style=HOLE_HOOK, type="", color="",
                                 hole_offset_y=-(base_cy + 0.5)))
        check("offset.lower_half_rejected", False,
              "accepted an offset into the lower half")
    except Exception as exc:
        msg = str(exc).lower()
        check("offset.lower_half_rejected", "lower half" in msg, str(exc))
        check("offset.not_blamed_on_text", "too tall" not in msg, str(exc))


def _params_from_preset(preset_key, style=HOLE_HOOK, **overrides):
    """A SwatchParams built the same way the panel's preset button does:
    apply the preset dict on top of the product's own shipped constants,
    never a second copy of the same numbers. If PLATE_PRESETS ever drifted
    to a hand-typed literal instead of referencing DEFAULT_PLATE_W and
    friends, this is the seam where a test can catch it.
    """
    from magpie_swatches.constants import (DEFAULT_ENGRAVE, DEFAULT_HOLE,
                                           DEFAULT_PLATE_THICK,
                                           DEFAULT_RELIEF)
    base = dict(
        brand="Sunlu", type="PLA Matte", color="Marrom Cafe",
        thickness=DEFAULT_PLATE_THICK, corner_segments=SEG,
        hole=DEFAULT_HOLE, mode=MODE_EMBOSS, relief=DEFAULT_RELIEF,
        engrave=DEFAULT_ENGRAVE, hole_style=style,
    )
    base.update(PLATE_PRESETS[preset_key])
    base.update(overrides)
    return SwatchParams(**base)


def test_preset_24_matches_the_shipped_defaults():
    """The 24 preset must reproduce EXACTLY what a fresh install already
    builds with no preset touched at all -- proof that PLATE_PRESETS[P24]
    references the real DEFAULT_* constants rather than a second, driftable
    copy of the same numbers."""
    from magpie_swatches.constants import (DEFAULT_BOTTOM_MARGIN,
                                           DEFAULT_BRAND_SIZE,
                                           DEFAULT_COLOR_SIZE,
                                           DEFAULT_CORNER_RADIUS,
                                           DEFAULT_HOLE_DIAMETER,
                                           DEFAULT_HOOK_SIZE, DEFAULT_PLATE_H,
                                           DEFAULT_PLATE_W, DEFAULT_TYPE_SIZE)

    preset = PLATE_PRESETS[PLATE_PRESET_24]
    check("preset24.plate_w", preset["plate_w"] == DEFAULT_PLATE_W)
    check("preset24.plate_h", preset["plate_h"] == DEFAULT_PLATE_H)
    check("preset24.corner_radius",
          preset["corner_radius"] == DEFAULT_CORNER_RADIUS)
    check("preset24.hook_size", preset["hook_size"] == DEFAULT_HOOK_SIZE)
    check("preset24.hole_diameter",
          preset["hole_diameter"] == DEFAULT_HOLE_DIAMETER)
    check("preset24.brand_size", preset["brand_size"] == DEFAULT_BRAND_SIZE)
    check("preset24.type_size", preset["type_size"] == DEFAULT_TYPE_SIZE)
    check("preset24.color_size", preset["color_size"] == DEFAULT_COLOR_SIZE)
    check("preset24.bottom_margin",
          preset["bottom_margin"] == DEFAULT_BOTTOM_MARGIN)

    for style in (HOLE_HOOK, HOLE_ROUND):
        fresh()
        no_preset = build_swatch(SwatchParams(
            brand="Sunlu", type="PLA Matte", color="Marrom Cafe",
            brand_size=DEFAULT_BRAND_SIZE, type_size=DEFAULT_TYPE_SIZE,
            color_size=DEFAULT_COLOR_SIZE, plate_w=DEFAULT_PLATE_W,
            plate_h=DEFAULT_PLATE_H, thickness=THICK,
            corner_radius=DEFAULT_CORNER_RADIUS, corner_segments=SEG,
            hole=True, hole_diameter=DEFAULT_HOLE_DIAMETER,
            mode=MODE_EMBOSS, relief=0.4, engrave=0.5, hole_style=style,
            hook_size=DEFAULT_HOOK_SIZE))
        no_preset_vol = volume(no_preset.obj.data)

        fresh()
        via_preset = build_swatch(_params_from_preset(
            PLATE_PRESET_24, style=style, thickness=THICK, relief=0.4))
        check(f"preset24.matches_no_preset[{style}]",
              near(volume(via_preset.obj.data), no_preset_vol, 1e-6),
              f"{volume(via_preset.obj.data):.4f} vs {no_preset_vol:.4f}")


def test_both_presets_share_the_same_hardware():
    """Corner radius, hook size and hole diameter are all HARDWARE, not
    decoration -- none of the three scale with the plate. PRINT-VALIDATED
    (11/08/2026): a scaled hook on the 35 mm preset was the one part of it
    that read as wrong once printed, confirming a keyring-sized opening
    does not get bigger just because the plate around it did. Both presets
    reference the same DEFAULT_* constants for all three, so none of them
    can drift by editing only one preset.
    """
    from magpie_swatches.constants import (DEFAULT_CORNER_RADIUS,
                                           DEFAULT_HOLE_DIAMETER,
                                           DEFAULT_HOOK_SIZE)
    p24 = PLATE_PRESETS[PLATE_PRESET_24]
    p35 = PLATE_PRESETS[PLATE_PRESET_35]

    for field, default in (("corner_radius", DEFAULT_CORNER_RADIUS),
                           ("hook_size", DEFAULT_HOOK_SIZE),
                           ("hole_diameter", DEFAULT_HOLE_DIAMETER)):
        check(f"preset.same_{field}", p24[field] == p35[field],
              f"{p24[field]} vs {p35[field]}")
        check(f"preset.{field}_is_the_default", p35[field] == default,
              f"{p35[field]} vs {default}")

    # ...and the corner radius survives all the way into the built
    # geometry, not just the table: a radius the plate builder clamped or
    # ignored would still pass the dict comparison above.
    r35 = p35["corner_radius"]
    fresh()
    p = _params_from_preset(PLATE_PRESET_35, hole=False, brand="", type="",
                            color="")
    obj = build_swatch(p).obj
    corner_verts = [v.co for v in obj.data.vertices
                   if v.co.x > p.plate_w * 0.5 - r35 - 1e-6
                   and v.co.y > p.plate_h * 0.5 - r35 - 1e-6
                   and v.co.z < 1e-6]
    # The arc's own centre, and every arc vertex sitting r35 away from it.
    ox, oy = p.plate_w * 0.5 - r35, p.plate_h * 0.5 - r35
    import math
    dists = [math.hypot(c.x - ox, c.y - oy) for c in corner_verts]
    check("preset.built_corner_matches_radius",
          dists and all(abs(d - r35) < 0.01 for d in dists),
          f"{len(dists)} arc verts, spread "
          f"{min(dists):.4f}-{max(dists):.4f} vs r={r35}")


def test_bottom_margin_lifts_the_text_without_narrowing_it():
    """The whole reason the bottom margin is separate from TEXT_MARGIN: it
    can be raised for free. MEASURED on the 35 mm preset, raising ALL four
    margins to 2.5 mm auto-shrinks the Color line and to 3.0 mm shrinks Type
    as well, because left/right feed _text_box(); raising only the bottom
    changes the block's position and nothing about its width.
    """
    fresh()
    low = build_swatch(_params_from_preset(PLATE_PRESET_35, bottom_margin=1.5))
    low_glyphs = [v.co for v in low.obj.data.vertices if v.co.z > 2.01]
    low_bottom = min(c.y for c in low_glyphs)
    low_width = max(c.x for c in low_glyphs) - min(c.x for c in low_glyphs)

    fresh()
    high = build_swatch(_params_from_preset(PLATE_PRESET_35,
                                            bottom_margin=3.0))
    high_glyphs = [v.co for v in high.obj.data.vertices if v.co.z > 2.01]
    high_bottom = min(c.y for c in high_glyphs)
    high_width = max(c.x for c in high_glyphs) - min(c.x for c in high_glyphs)

    check("bottom_margin.lifts_the_block",
          near(high_bottom - low_bottom, 1.5, 0.01),
          f"moved up {high_bottom - low_bottom:.3f} mm, expected 1.5")
    check("bottom_margin.does_not_narrow_the_text",
          near(high_width, low_width, 1e-6),
          f"{high_width:.4f} vs {low_width:.4f}")
    check("bottom_margin.no_shrink_at_3mm",
          not [l.field for l in high.label.lines if l.shrunk],
          [l.field for l in high.label.lines if l.shrunk])


def test_preset_bottom_margins_land_in_the_geometry():
    """Each preset's bottom margin must be the real, measured distance from
    the plate's bottom edge to the lowest glyph -- not just a number in a
    dict that something downstream could ignore."""
    for preset_key, expected in ((PLATE_PRESET_24, 1.5),
                                 (PLATE_PRESET_35, 3.0)):
        fresh()
        p = _params_from_preset(preset_key)
        result = build_swatch(p)
        glyphs = [v.co for v in result.obj.data.vertices
                 if v.co.z > p.thickness + 0.01]
        border = min(c.y for c in glyphs) - (-p.plate_h * 0.5)
        check(f"preset.bottom_border[{preset_key}]",
              near(border, expected, 0.02), f"{border:.3f} mm vs {expected}")


def test_both_presets_build_manifold_in_both_hole_styles():
    for preset_key in (PLATE_PRESET_24, PLATE_PRESET_35):
        for style in (HOLE_HOOK, HOLE_ROUND):
            fresh()
            tag = f"preset.builds[{preset_key}][{style}]"
            try:
                result = build_swatch(_params_from_preset(preset_key,
                                                           style=style))
                check(tag, True)
                check(f"{tag}.manifold", manifold(result.obj.data))
            except Exception as exc:
                check(tag, False, f"{type(exc).__name__}: {exc}")


def test_preset_35_does_not_auto_shrink_an_ordinary_name():
    """35's text sizes (3.4/4.2/3.6) were chosen SPECIFICALLY because the
    naive 24-set x 35/24 multiplication (3.5/4.4/3.8) overflows the usable
    width and shrinks "Marrom Cafe" -- see docs/decisions/AJUSTES-0.11.0.md. This is the
    regression test for that choice."""
    fresh()
    result = build_swatch(_params_from_preset(PLATE_PRESET_35))
    shrunk = [l.field for l in result.label.lines if l.shrunk]
    check("preset35.no_shrink_on_ordinary_name", not shrunk, shrunk)


def test_preset_35_prints_where_preset_24_cannot():
    """The proportional argument for the bigger plate, made concrete: the
    longest realistic colour name ("Cinza Chumbo", 12 characters) comes out
    under the printable floor at 24 mm and comfortably above it at 35 mm --
    MEASURED 0.437 mm vs 0.666 mm. The 35 preset does not just look better,
    it prints a swatch the 24 preset cannot."""
    fresh()
    small = build_swatch(_params_from_preset(PLATE_PRESET_24,
                                             color="Cinza Chumbo"))
    small_thinnest = min(l.stroke for l in small.label.lines)
    check("preset24.cinza_chumbo_under_floor", small_thinnest < MIN_STROKE,
          f"{small_thinnest:.3f} mm")

    fresh()
    big = build_swatch(_params_from_preset(PLATE_PRESET_35,
                                           color="Cinza Chumbo"))
    big_thinnest = min(l.stroke for l in big.label.lines)
    check("preset35.cinza_chumbo_above_floor", big_thinnest >= MIN_STROKE,
          f"{big_thinnest:.3f} mm")


def test_both_presets_fill_a_comparable_width_band():
    """Not an exact match -- TEXT_MARGIN/HOLE_INSET/LINE_GAP stay module
    constants outside either preset's reach, so 35 cannot reproduce 24's
    proportions exactly (see docs/decisions/AJUSTES-0.11.0.md). A band, not a fixed number,
    so this does not break on the next font/metric recalibration the way an
    exact-match assertion would.
    """
    for preset_key in (PLATE_PRESET_24, PLATE_PRESET_35):
        fresh()
        p = _params_from_preset(preset_key)
        result = build_swatch(p)
        glyphs = [v.co for v in result.obj.data.vertices
                 if v.co.z > p.thickness + 0.01]
        width_pct = ((max(c.x for c in glyphs) - min(c.x for c in glyphs))
                    / p.plate_w * 100.0)
        check(f"preset.fills_width_band[{preset_key}]",
              80.0 <= width_pct <= 95.0, f"{width_pct:.1f}%")


def test_emboss_single_field():
    """Only one field filled -- the two empty ones must not block the build,
    and validate.check() must accept it (only all-three-empty is an error)."""
    fresh()
    result = build_swatch(base_params(brand="", color=""))
    check("emboss.single_field.manifold", manifold(result.obj.data))
    check("emboss.single_field.named", result.obj.name == "PLA Matte - SWATCH",
          result.obj.name)


try:
    for fn in (test_emboss_with_hole, test_emboss_adds_material,
              test_emboss_no_hole, test_text_is_left_aligned_and_bottom_anchored,
              test_text_too_tall_is_refused, test_blank_plate,
              test_blank_plate_with_hole, test_emboss_with_hook_style,
              test_shipped_defaults_actually_generate,
              test_round_style_still_works_when_named_explicitly,
              test_hole_offset_zero_is_additive,
              test_lateral_hole_offset_keeps_one_piece,
              test_hole_offset_into_lower_half_is_rejected_by_the_hole_not_the_text,
              test_preset_24_matches_the_shipped_defaults,
              test_both_presets_share_the_same_hardware,
              test_bottom_margin_lifts_the_text_without_narrowing_it,
              test_preset_bottom_margins_land_in_the_geometry,
              test_both_presets_build_manifold_in_both_hole_styles,
              test_preset_35_does_not_auto_shrink_an_ordinary_name,
              test_preset_35_prints_where_preset_24_cannot,
              test_both_presets_fill_a_comparable_width_band,
              test_emboss_single_field):
        fn()
except Exception as exc:
    import traceback
    traceback.print_exc()
    _fails.append(f"EXCEPTION: {exc}")

print(f"RESULT: {'FAIL -> ' + ', '.join(_fails) if _fails else 'PASS'}")
sys.exit(1 if _fails else 0)
