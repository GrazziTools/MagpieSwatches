"""Tests for engine/booleans.py's failure-detection helpers.

    blender --background --factory-startup --python tests/test_booleans.py

This is the module the rest of the add-on trusts to turn a boolean modifier
that silently gave up into a raised BooleanError. union() has always
verified geometrically (_swallows); difference() used to accept ANY result
whose vertex/polygon count differed from the input, which is not the same
thing as actually having removed material -- see _shrinks()'s own docstring
for the failure mode that gap left open.

WARNING: Blender exits 0 even when a script raises -- a runner must grep for
'Traceback' as well as reading the RESULT line.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bmesh  # noqa: E402
import bpy  # noqa: E402
import _pkg  # noqa: E402

_pkg.load()

from magpie_swatches.engine import booleans, plate as plate_geo  # noqa: E402

_fails = []


def check(tag, ok, detail=""):
    print(f"[{tag}] {'ok' if ok else 'FAIL'} {detail}")
    if not ok:
        _fails.append(tag)


def near(a, b, tol):
    return abs(a - b) <= tol


def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def cube_mesh(size):
    """A closed, manifold cube of the given side length -- the same
    contract plate.py/hook.py/text.py all build to, and the one _volume()
    and _shrinks() are documented to assume."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=size)
    me = bpy.data.meshes.new(f"cube{size}")
    bm.to_mesh(me)
    bm.free()
    return me


def test_volume_matches_a_known_cube():
    fresh()
    me = cube_mesh(10.0)
    got = booleans._volume(me)
    check("volume.matches_cube", near(got, 1000.0, 0.01), f"{got:.3f}")


def test_shrinks_true_on_real_loss():
    fresh()
    before = booleans._volume(cube_mesh(10.0))
    smaller = cube_mesh(9.0)
    check("shrinks.true_on_real_loss",
          booleans._shrinks(smaller, before),
          f"before {before:.1f}, after {booleans._volume(smaller):.1f}")


def test_shrinks_false_on_untouched():
    """The exact case that used to ship as a silent no-op: the candidate's
    volume is IDENTICAL to before, which is what a boolean modifier that
    gave up hands back -- regardless of whether its vertex/polygon count
    happens to differ, which is all the old check looked at."""
    fresh()
    before = booleans._volume(cube_mesh(10.0))
    same = cube_mesh(10.0)
    check("shrinks.false_on_untouched",
          not booleans._shrinks(same, before),
          f"before {before:.1f}, after {booleans._volume(same):.1f}")


def test_shrinks_false_on_noise_floor():
    """A delta smaller than the floor must not read as a real cut -- this
    is what keeps an unrelated re-triangulation's floating point noise from
    looking like a successful boolean."""
    fresh()
    me = cube_mesh(10.0)
    before = booleans._volume(me)
    check("shrinks.false_on_tiny_delta",
          not booleans._shrinks(me, before + 1e-9))


def test_difference_end_to_end_still_cuts_a_real_hole():
    """Integration proof, not just the helpers in isolation: a real
    difference() call against genuinely overlapping geometry must still
    succeed and actually remove volume -- the fix must not make ordinary
    cuts any harder to accept than before."""
    fresh()
    p = plate_geo.create_plate(24.0, 24.0, 2.0, 3.0, 16, "p")
    before = booleans._volume(p.data)
    cx, cy = plate_geo.hole_center(24.0, 24.0, 3.75)
    tool = plate_geo.hole_tool(3.5, cx, cy, -1.0, 3.0, 32, "t")
    result = booleans.difference(p, tool)
    after = booleans._volume(result.data)
    check("difference.actually_cuts", after < before,
          f"{after:.2f} vs {before:.2f}")


def test_difference_actually_consults_shrinks():
    """Proves the WIRING, not just _shrinks() in isolation: difference()
    must genuinely react to what _shrinks() decides, not just have it
    sitting nearby unused. Monkeypatched to always say "nothing was cut" --
    if difference() ignored that and accepted the result anyway (the exact
    bug this fixes), a real, successful cut would still succeed here.
    """
    fresh()
    p = plate_geo.create_plate(24.0, 24.0, 2.0, 3.0, 16, "p")
    cx, cy = plate_geo.hole_center(24.0, 24.0, 3.75)
    tool = plate_geo.hole_tool(3.5, cx, cy, -1.0, 3.0, 32, "t")

    original = booleans._shrinks
    booleans._shrinks = lambda mesh, before, floor=1e-6: False
    try:
        try:
            booleans.difference(p, tool)
            check("difference.consults_shrinks", False,
                  "accepted a cut that _shrinks() said did not happen")
        except booleans.BooleanError:
            check("difference.consults_shrinks", True)
    finally:
        booleans._shrinks = original


try:
    for fn in (test_volume_matches_a_known_cube, test_shrinks_true_on_real_loss,
              test_shrinks_false_on_untouched, test_shrinks_false_on_noise_floor,
              test_difference_end_to_end_still_cuts_a_real_hole,
              test_difference_actually_consults_shrinks):
        fn()
except Exception as exc:
    import traceback
    traceback.print_exc()
    _fails.append(f"EXCEPTION: {exc}")

print(f"RESULT: {'FAIL -> ' + ', '.join(_fails) if _fails else 'PASS'}")
sys.exit(1 if _fails else 0)
