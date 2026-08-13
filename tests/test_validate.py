"""Tests for engine/validate.py -- pure, no bpy needed, but run inside Blender
like the rest of the suite so the whole gate uses one runner.

    blender --background --factory-startup --python tests/test_validate.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _pkg  # noqa: E402

_pkg.load()

from magpie_swatches.constants import (ENGRAVE_FLOOR, HOLE_INSET,  # noqa: E402
                                       MIN_FONT_SIZE, MODE_DEBOSS,
                                       MODE_EMBOSS, RELIEF_MAX, RELIEF_MIN)
from magpie_swatches.engine.swatch import SwatchParams  # noqa: E402
from magpie_swatches.engine.validate import ValidationError, check  # noqa: E402

_fails = []


def check_result(tag, ok, detail=""):
    print(f"[{tag}] {'ok' if ok else 'FAIL'} {detail}")
    if not ok:
        _fails.append(tag)


def valid_params(**overrides) -> SwatchParams:
    base = dict(
        brand="Sunlu", type="PLA Matte", color="Marrom Cafe",
        brand_size=3.0, type_size=4.5, color_size=3.5,
        plate_w=24.0, plate_h=24.0, thickness=2.0, corner_radius=2.0,
        corner_segments=16, hole=True, hole_diameter=3.5,
        mode=MODE_EMBOSS, relief=0.4, engrave=0.5,
    )
    base.update(overrides)
    return SwatchParams(**base)


def expect_ok(tag, **overrides):
    try:
        check(valid_params(**overrides))
        check_result(tag, True)
    except ValidationError as exc:
        check_result(tag, False, f"raised unexpectedly: {exc}")


def expect_error(tag, needle, **overrides):
    try:
        check(valid_params(**overrides))
        check_result(tag, False, "did not raise")
    except ValidationError as exc:
        check_result(tag, needle.lower() in str(exc).lower(), str(exc))


def test_baseline_is_valid():
    expect_ok("valid.baseline")
    expect_ok("valid.deboss", mode=MODE_DEBOSS)
    expect_ok("valid.no_hole", hole=False)


def test_all_fields_empty_is_allowed():
    """No text at all is the BLANK PLATE, not an error -- Generate has to work
    on the first click of a fresh install, when every field is still empty."""
    expect_ok("empty.all_blank", brand="", type="", color="")
    expect_ok("empty.all_whitespace", brand="   ", type="\t", color="")


def test_stroke_width_names_the_field():
    expect_error("stroke.brand_too_small", "Brand",
                 brand_size=MIN_FONT_SIZE - 0.5)
    expect_error("stroke.type_too_small", "Type",
                 type_size=MIN_FONT_SIZE - 0.5)
    expect_error("stroke.color_too_small", "Color",
                 color_size=MIN_FONT_SIZE - 0.5)
    # empty fields are never checked, however small their size
    expect_ok("stroke.ignores_empty_field", type="", color="",
             type_size=0.1, color_size=0.1)


def test_plate_dimensions():
    expect_error("plate.zero_width", "greater than zero", plate_w=0.0)
    expect_error("plate.zero_height", "greater than zero", plate_h=0.0)
    expect_error("plate.zero_thickness", "greater than zero", thickness=0.0)
    expect_error("plate.radius_too_big", "Corner radius",
                 corner_radius=100.0)
    expect_ok("plate.radius_at_max", corner_radius=12.0)  # exactly min(w,h)/2


def test_hole_dimensions():
    expect_error("hole.zero_diameter", "greater than zero", hole_diameter=0.0)
    expect_error("hole.too_big_for_corner", "fit its corner",
                 hole_diameter=2.0 * HOLE_INSET + 1.0)
    expect_ok("hole.ignored_when_off", hole=False,
             hole_diameter=2.0 * HOLE_INSET + 1.0)


def test_hole_offset_position():
    """X is free (as long as the opening stays inside the plate); Y is
    capped at the plate's own vertical middle -- the hole may not cross
    into the text's own territory. See swatch.py's _hole_position() for the
    geometry this checks against."""
    expect_ok("offset.zero_is_additive", hole_offset_x=0.0, hole_offset_y=0.0)
    expect_ok("offset.modest_lateral", hole_offset_x=2.0, hole_offset_y=-1.0)
    expect_error("offset.outside_plate", "outside the plate",
                 hole_offset_x=50.0)

    # ROUND is valid_params()'s default style: HOLE_INSET (3.75) from each of
    # the two nearest edges of a 24 mm plate puts the hole's centre at
    # y = 12 - 3.75 = 8.25. Half a millimetre past that pushes the CENTRE
    # (not the whole hole) below y = 0, without yet pushing the hole's own
    # footprint outside the plate -- so this isolates the upper-half rule
    # from the outside-the-plate rule above.
    base_cy = 24.0 * 0.5 - HOLE_INSET
    expect_error("offset.lower_half", "lower half",
                 hole_offset_y=-(base_cy + 0.5))


def test_emboss_relief_range():
    expect_error("emboss.too_shallow", "printable range",
                 mode=MODE_EMBOSS, relief=RELIEF_MIN - 0.1)
    expect_error("emboss.too_tall", "printable range",
                 mode=MODE_EMBOSS, relief=RELIEF_MAX + 0.1)
    expect_ok("emboss.at_bounds", mode=MODE_EMBOSS, relief=RELIEF_MIN)
    expect_ok("emboss.at_bounds_max", mode=MODE_EMBOSS, relief=RELIEF_MAX)


def test_deboss_engrave_range():
    expect_error("deboss.zero_engrave", "greater than zero",
                 mode=MODE_DEBOSS, engrave=0.0)
    thickness = 2.0
    too_deep = thickness - ENGRAVE_FLOOR + 0.1
    expect_error("deboss.too_deep", "leaves less than",
                 mode=MODE_DEBOSS, thickness=thickness, engrave=too_deep)
    at_floor = thickness - ENGRAVE_FLOOR
    expect_ok("deboss.exactly_at_floor", mode=MODE_DEBOSS,
             thickness=thickness, engrave=at_floor)


try:
    for fn in (test_baseline_is_valid, test_all_fields_empty_is_allowed,
              test_stroke_width_names_the_field, test_plate_dimensions,
              test_hole_dimensions, test_hole_offset_position,
              test_emboss_relief_range, test_deboss_engrave_range):
        fn()
finally:
    pass

print(f"RESULT: {'FAIL -> ' + ', '.join(_fails) if _fails else 'PASS'}")
sys.exit(1 if _fails else 0)
