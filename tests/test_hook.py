"""Tests for engine/hook.py and the baked outline it scales.

    blender --background --factory-startup --python tests/test_hook.py

WARNING: Blender exits 0 even when a script raises -- a runner must grep for
'Traceback' as well as reading the RESULT line.
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bmesh  # noqa: E402
import bpy  # noqa: E402
import _pkg  # noqa: E402

_pkg.load()

from magpie_swatches.constants import (DEFAULT_HOOK_SIZE,  # noqa: E402
                                       MIN_HOOK_SIZE)
from magpie_swatches.engine import booleans, hook, plate  # noqa: E402
from magpie_swatches.engine.hook_shape import ASPECT, OUTLINE  # noqa: E402

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


def islands(mesh):
    """How many separate connected pieces the mesh is in."""
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


def test_baked_outline_is_a_clean_closed_loop():
    """The shape is traced artwork, so the table itself is what has to be
    trusted -- and two specific things about it decide whether the boolean
    works at all.

    A self-intersecting outline booleans as a SILENT no-op (measured while
    building the earlier parametric version: the solver refuses the face and
    returns the plate untouched, without raising), so a broken table would
    ship a swatch with no hook in it and nothing to say so.
    """
    check("shape.has_points", len(OUTLINE) > 50, str(len(OUTLINE)))

    # No two consecutive points on top of each other -- a zero-length edge
    # is the cheapest way to make a face degenerate.
    closest = min(math.dist(OUTLINE[i], OUTLINE[(i + 1) % len(OUTLINE)])
                  for i in range(len(OUTLINE)))
    check("shape.no_duplicate_points", closest > 1e-9, f"{closest:.2e}")

    xs = [x for x, _ in OUTLINE]
    ys = [y for _, y in OUTLINE]
    height = max(ys) - min(ys)
    check("shape.normalised_height", near(height, 1.0, 1e-6), f"{height:.6f}")
    check("shape.centred", near((min(xs) + max(xs)) / 2, 0.0, 1e-6)
          and near((min(ys) + max(ys)) / 2, 0.0, 1e-6))
    check("shape.matches_reference_aspect",
          near((max(xs) - min(xs)) / height, ASPECT, 1e-3),
          f"{(max(xs) - min(xs)) / height:.4f} vs {ASPECT}")


def test_tool_is_manifold_and_scales():
    fresh()
    for size in (MIN_HOOK_SIZE, DEFAULT_HOOK_SIZE, 12.0):
        fresh()
        obj = hook.hook_tool(size, 0.0, 0.0, -1.0, 3.0, "t")
        check(f"tool.manifold[{size}]", manifold(obj.data))
        check(f"tool.one_piece[{size}]", islands(obj.data) == 1,
              str(islands(obj.data)))
        ys = [v.co.y for v in obj.data.vertices]
        check(f"tool.height[{size}]", near(max(ys) - min(ys), size, 1e-4),
              f"{max(ys) - min(ys):.4f} vs {size}")


def test_bounds_match_the_real_geometry():
    """swatch.py caps the text off hook_bounds() BEFORE any geometry is
    built. If that disagreed with what hook_tool() actually makes, the text
    would silently overlap the hook."""
    fresh()
    size = DEFAULT_HOOK_SIZE
    min_x, min_y, max_x, max_y = hook.hook_bounds(size)
    obj = hook.hook_tool(size, 0.0, 0.0, -1.0, 3.0, "t")
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    check("bounds.match_x", near(min_x, min(xs), 1e-6)
          and near(max_x, max(xs), 1e-6))
    check("bounds.match_y", near(min_y, min(ys), 1e-6)
          and near(max_y, max(ys), 1e-6))
    # Taller than wide -- the whole reason bounds exists rather than a single
    # radius. If this ever stopped being true, swatch.py's per-direction
    # reasoning would be pointless complexity.
    check("bounds.taller_than_wide", (max_y - min_y) > (max_x - min_x),
          f"{max_x - min_x:.2f} wide x {max_y - min_y:.2f} tall")


def test_cutting_a_plate_leaves_one_piece():
    """The tongue has to stay attached. A shape that fully encircled it
    would cut it loose, and it would drop out of the print -- confirmed
    reachable: a plain ring-shaped cutter does exactly that."""
    fresh()
    size = DEFAULT_HOOK_SIZE
    p = plate.create_plate(24.0, 24.0, 2.0, 3.0, 16, "pl")
    cx, cy = plate.hole_center(24.0, 24.0, hook.hook_inset(size))
    tool = hook.hook_tool(size, cx, cy, -1.0, 3.0, "t")
    out = booleans.difference(p, tool)

    pieces = islands(out.data)
    check("cut.manifold", manifold(out.data))
    check("cut.plate_stays_one_piece", pieces == 1,
          f"{pieces} pieces"
          + (" -- the tongue came loose" if pieces != 1 else ""))


def test_inset_keeps_the_hook_inside_the_plate():
    fresh()
    size = DEFAULT_HOOK_SIZE
    inset = hook.hook_inset(size)
    min_x, _, _, max_y = hook.hook_bounds(size)
    cx, cy = plate.hole_center(24.0, 24.0, inset)
    # left edge of the hook vs left edge of the plate
    check("inset.clears_left_edge", cx + min_x > -12.0,
          f"hook reaches x={cx + min_x:.2f}, plate edge at -12.0")
    check("inset.clears_top_edge", cy + max_y < 12.0,
          f"hook reaches y={cy + max_y:.2f}, plate edge at 12.0")


def test_rejects_a_size_below_the_printable_floor():
    from magpie_swatches.constants import HOLE_HOOK
    from magpie_swatches.engine.swatch import SwatchParams
    from magpie_swatches.engine.validate import ValidationError, check as vcheck

    def params(**over):
        base = dict(brand="X", type="", color="", brand_size=3.0,
                   type_size=3.0, color_size=3.0, plate_w=24.0, plate_h=24.0,
                   thickness=2.0, corner_radius=3.0, corner_segments=16,
                   hole=True, hole_diameter=3.5, mode='EMBOSS', relief=0.4,
                   engrave=0.5, hole_style=HOLE_HOOK,
                   hook_size=DEFAULT_HOOK_SIZE)
        base.update(over)
        return SwatchParams(**base)

    try:
        vcheck(params(hook_size=MIN_HOOK_SIZE - 0.5))
        check("validate.rejects_tiny_hook", False, "did not raise")
    except ValidationError as exc:
        check("validate.rejects_tiny_hook", "Hook size" in str(exc), str(exc))

    try:
        vcheck(params())
        check("validate.accepts_default", True)
    except ValidationError as exc:
        check("validate.accepts_default", False, str(exc))

    try:
        vcheck(params(plate_w=6.0, plate_h=6.0, corner_radius=1.0))
        check("validate.rejects_hook_bigger_than_plate", False,
              "did not raise")
    except ValidationError as exc:
        check("validate.rejects_hook_bigger_than_plate",
              "too big" in str(exc), str(exc))


try:
    for fn in (test_baked_outline_is_a_clean_closed_loop,
              test_tool_is_manifold_and_scales,
              test_bounds_match_the_real_geometry,
              test_cutting_a_plate_leaves_one_piece,
              test_inset_keeps_the_hook_inside_the_plate,
              test_rejects_a_size_below_the_printable_floor):
        fn()
except Exception as exc:
    import traceback
    traceback.print_exc()
    _fails.append(f"EXCEPTION: {exc}")

print(f"RESULT: {'FAIL -> ' + ', '.join(_fails) if _fails else 'PASS'}")
sys.exit(1 if _fails else 0)
