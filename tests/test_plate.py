"""Tests for engine/plate.py: the rounded plate and its mounting hole.

    blender --background --factory-startup --python tests/test_plate.py

WARNING: Blender exits 0 even when a script raises -- a runner must grep for
'Traceback' as well as reading the RESULT line.
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy  # noqa: E402
import _pkg  # noqa: E402

_pkg.load()

from magpie_swatches.engine import booleans, plate  # noqa: E402

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


def volume(mesh):
    import bmesh
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        return bm.calc_volume()
    finally:
        bm.free()


W, H, T, R, SEG = 24.0, 24.0, 2.0, 2.0, 16


def test_plain_plate():
    fresh()
    obj = plate.create_plate(W, H, T, R, SEG, "p")
    check("plate.manifold", manifold(obj.data))
    check("plate.dims", near(obj.dimensions.x, W, 0.05)
          and near(obj.dimensions.y, H, 0.05)
          and near(obj.dimensions.z, T, 1e-4),
          f"{tuple(round(v, 3) for v in obj.dimensions)}")
    zs = [v.co.z for v in obj.data.vertices]
    check("plate.bed", near(min(zs), 0.0, 1e-4), f"min z {min(zs):.4f}")
    check("plate.top", near(max(zs), T, 1e-4), f"max z {max(zs):.4f}")

    xs = [abs(v.co.x) for v in obj.data.vertices]
    ys = [abs(v.co.y) for v in obj.data.vertices]
    check("plate.within_footprint",
          max(xs) <= W * 0.5 + 1e-6 and max(ys) <= H * 0.5 + 1e-6,
          f"max |x|={max(xs):.4f} max |y|={max(ys):.4f}")


def test_zero_radius_is_a_sharp_rect():
    fresh()
    obj = plate.create_plate(W, H, T, 0.0, SEG, "p0")
    check("plate.zero_radius.manifold", manifold(obj.data))
    check("plate.zero_radius.dims", near(obj.dimensions.x, W, 1e-4)
          and near(obj.dimensions.y, H, 1e-4))


def test_radius_clamps_to_short_side():
    """A radius requested past half the short side must not self-intersect --
    plate.py clamps it instead of building garbage."""
    fresh()
    obj = plate.create_plate(10.0, 6.0, T, 100.0, SEG, "pclamp")
    check("plate.radius_clamped.manifold", manifold(obj.data))
    check("plate.radius_clamped.dims", near(obj.dimensions.x, 10.0, 0.05)
          and near(obj.dimensions.y, 6.0, 0.05))


def test_hole_cuts_through():
    fresh()
    obj = plate.create_plate(W, H, T, R, SEG, "ph")
    solid_vol = volume(obj.data)

    cx, cy = plate.hole_center(W, H, 3.75)
    diameter = 3.5
    tool = plate.hole_tool(diameter, cx, cy, -1.0, T + 1.0, 32, "hole")
    holed = booleans.difference(obj, tool)

    check("hole.manifold", manifold(holed.data))
    holed_vol = volume(holed.data)
    check("hole.removes_material", holed_vol < solid_vol,
          f"{holed_vol:.2f} vs {solid_vol:.2f} mm3")

    expect = math.pi * (diameter * 0.5) ** 2 * T
    removed = solid_vol - holed_vol
    check("hole.roughly_bore_sized", near(removed, expect, expect * 0.1),
          f"removed {removed:.2f} mm3, bore alone is {expect:.2f}")

    nearest = min(math.hypot(v.co.x - cx, v.co.y - cy)
                  for v in holed.data.vertices)
    check("hole.opens_a_real_cavity", near(nearest, diameter * 0.5, 0.1),
          f"closest vertex to hole centre is {nearest:.3f} mm away, "
          f"expected ~{diameter * 0.5:.3f}")


try:
    for fn in (test_plain_plate, test_zero_radius_is_a_sharp_rect,
              test_radius_clamps_to_short_side, test_hole_cuts_through):
        fn()
finally:
    pass

print(f"RESULT: {'FAIL -> ' + ', '.join(_fails) if _fails else 'PASS'}")
sys.exit(1 if _fails else 0)
