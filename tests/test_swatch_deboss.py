"""The other half of the decisive smoke test: does the deboss boolean (a
DIFFERENCE, not a UNION) actually cut a cavity on this Blender build?

    blender --background --factory-startup --python tests/test_swatch_deboss.py

Per docs/decisions/IMPLEMENTATION_PLAN.md: "DEBOSS is the one that tends to break -- this
test is the guard." See test_swatch_emboss.py's header for why this hand-rolls
its watertight/normals checks instead of depending on the 3D Print Toolbox.

WARNING: Blender exits 0 even when a script raises -- a runner must grep for
'Traceback' as well as reading the RESULT line.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy  # noqa: E402
import _pkg  # noqa: E402

_pkg.load()

from magpie_swatches.constants import MODE_DEBOSS, TYPE_KEY, TYPE_SWATCH  # noqa: E402
from magpie_swatches.engine import plate  # noqa: E402
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
    """See test_swatch_emboss.py -- catches a flipped-normal seam a manifold
    count alone misses."""
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


PLATE_W, PLATE_H, THICK, RADIUS, SEG = 24.0, 24.0, 2.0, 2.0, 16


def base_params(**overrides):
    base = dict(
        brand="Sunlu", type="PLA Matte", color="Marrom Cafe",
        brand_size=3.0, type_size=4.5, color_size=3.5,
        plate_w=PLATE_W, plate_h=PLATE_H, thickness=THICK,
        corner_radius=RADIUS, corner_segments=SEG,
        hole=True, hole_diameter=3.5,
        mode=MODE_DEBOSS, relief=0.4, engrave=0.5,
    )
    base.update(overrides)
    return SwatchParams(**base)


def test_deboss_with_hole():
    fresh()
    result = build_swatch(base_params())
    obj = result.obj
    check("deboss.manifold", manifold(obj.data))
    check("deboss.normals_consistent", normals_consistent(obj.data))
    check("deboss.tagged", obj.get(TYPE_KEY) == TYPE_SWATCH,
          str(obj.get(TYPE_KEY)))

    zs = [v.co.z for v in obj.data.vertices]
    check("deboss.floor_untouched", near(min(zs), 0.0, 0.05),
          f"min z {min(zs):.3f}")
    # A difference can only ever remove material, so the top of the result
    # can never rise above the plate's own top face -- unlike emboss, there
    # is no relief height to add on here.
    check("deboss.never_exceeds_plate_top", max(zs) <= THICK + 0.05,
          f"max z {max(zs):.3f}, plate top {THICK}")


def test_deboss_removes_material():
    """If the difference silently no-op'd (the boolean giving up and handing
    back the plate untouched), the cavity would be missing and the volume
    would equal a plain plate's, even though nothing raised."""
    fresh()
    plain = plate.create_plate(PLATE_W, PLATE_H, THICK, RADIUS, SEG, "plain")
    plain_vol = volume(plain.data)

    fresh()
    result = build_swatch(base_params(hole=False))
    swatch_vol = volume(result.obj.data)

    check("deboss.volume_shrank", swatch_vol < plain_vol,
          f"swatch {swatch_vol:.2f} vs plain {plain_vol:.2f} mm3")


def test_deboss_no_hole():
    fresh()
    result = build_swatch(base_params(hole=False))
    check("deboss.no_hole.manifold", manifold(result.obj.data))
    check("deboss.no_hole.normals_consistent",
          normals_consistent(result.obj.data))


def test_deboss_deep_engrave_near_floor():
    """The engrave depth closest to ENGRAVE_FLOOR is the case most likely to
    punch a hole clean through a thin plate -- exercise it explicitly rather
    than only ever testing the comfortable default."""
    fresh()
    # thickness=2.0, ENGRAVE_FLOOR=0.8 -> max valid engrave is 1.2
    result = build_swatch(base_params(hole=False, engrave=1.2))
    check("deboss.deep_engrave.manifold", manifold(result.obj.data))
    check("deboss.deep_engrave.normals_consistent",
          normals_consistent(result.obj.data))
    zs = [v.co.z for v in result.obj.data.vertices]
    check("deboss.deep_engrave.floor_intact", near(min(zs), 0.0, 0.05),
          f"min z {min(zs):.3f}")


try:
    for fn in (test_deboss_with_hole, test_deboss_removes_material,
              test_deboss_no_hole, test_deboss_deep_engrave_near_floor):
        fn()
except Exception as exc:
    import traceback
    traceback.print_exc()
    _fails.append(f"EXCEPTION: {exc}")

print(f"RESULT: {'FAIL -> ' + ', '.join(_fails) if _fails else 'PASS'}")
sys.exit(1 if _fails else 0)
