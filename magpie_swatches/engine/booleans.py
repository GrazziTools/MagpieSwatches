"""Union, difference, and the cleanup after them.

The whole swatch turns on one boolean. EMBOSS unions the raised glyph solid onto
the plate; DEBOSS subtracts it to sink the cavity. Both go through here, and
nothing in this module knows what a swatch or a glyph is -- it takes two objects
and gives back one.

The trap this module exists to close: a boolean modifier does NOT raise when it
gives up. It hands back the untouched mesh, and the part silently ships missing
whatever was meant to be added or removed. On 4.2 -- FAST and EXACT only, no
MANIFOLD solver -- that is the normal outcome for the thin, near-coplanar glyph
contours a swatch is made of: the modifier reports success and merges nothing,
so a blank plate comes out with the label gone. Both entry points here check the
RESULT (geometry, not a polygon tally) and raise BooleanError instead.
"""

import bmesh
import bpy
from mathutils import Vector

# Weld threshold when healing a boolean seam. 1 micron: large enough to fuse the
# coincident vertices an exact solver leaves along a cut, far too small to touch
# any real feature on a millimetre-scale part.
MERGE_DIST = 0.001


class BooleanError(Exception):
    """A boolean operation could not be completed on this Blender build."""


def has_manifold_solver() -> bool:
    """True when this Blender ships the MANIFOLD boolean solver (4.5+).

    Worth naming so the UI can say "update Blender" instead of blaming the input:
    on 4.2 the emboss union of thin glyph contours is the operation that gives up.
    """
    try:
        items = bpy.types.BooleanModifier.bl_rna.properties['solver'].enum_items
        return 'MANIFOLD' in {i.identifier for i in items}
    except Exception:
        return True


def heal(obj):
    """Clean up the degenerate scraps an exact solver leaves at a cut seam.

    Weld only. Merging coincident vertices is the conservative repair: it removes
    zero-length edges and zero-area faces without collapsing anything carrying
    real area. Dissolving degenerates was tried in the sibling add-on and made
    things worse -- it tears holes around short-but-real edges. Then patch the
    pinholes the solver leaves, bounded to 4-sided loops so this can only close a
    sliver, never roof over a gap that was meant to be there.
    """
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=MERGE_DIST)
        boundary = [e for e in bm.edges if len(e.link_faces) == 1]
        if boundary:
            bmesh.ops.holes_fill(bm, edges=boundary, sides=4)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(obj.data)
    finally:
        bm.free()
    obj.data.update()
    return obj


def _bounds(bound_box, matrix):
    """World-space (min, max) corners of an object's bounding box."""
    pts = [matrix @ Vector(c) for c in bound_box]
    return (Vector((min(p.x for p in pts), min(p.y for p in pts),
                    min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts),
                    max(p.z for p in pts))))


def _swallows(mesh, want, matrix, slack=0.05):
    """True when `mesh` reaches out to cover the box `want`.

    The tell for a union that worked: the result's bounding box grows to include
    the tool. For emboss the glyph stands proud of the plate's top face, so a
    union that no-op'd leaves the result capped at the plate top and misses the
    relief height by millimetres -- caught here. Slack is a re-triangulation
    tolerance, not a fudge: a real union can trim a hair off a corner, a union
    that never happened misses by the whole relief.
    """
    if not mesh.vertices:
        return False
    pts = [matrix @ v.co for v in mesh.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts),
                 min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts),
                 max(p.z for p in pts)))
    return all(lo[i] <= want[0][i] + slack and hi[i] >= want[1][i] - slack
               for i in range(3))


def _volume(mesh):
    """Absolute volume of a mesh in its own local space.

    Assumes manifold, consistently-wound input -- exactly what plate.py,
    hook.py and text.py all build, and what heal() restores after a solver
    leaves a seam, so every mesh this module hands to _volume() qualifies.
    """
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        return abs(bm.calc_volume())
    finally:
        bm.free()


def _shrinks(mesh, before_volume, floor=1e-6):
    """True when `mesh` actually lost volume relative to `before_volume`.

    The mirror of _swallows() for a subtraction: a difference that gave up
    hands back the target UNCHANGED, so its volume equals before_volume to
    float precision -- exactly the silent no-op this module's own docstring
    warns a boolean modifier can produce. A self-intersecting tool outline
    (see engine/hook_shape.py's own docstring on the failure mode) is
    exactly the kind of input that triggers it. Volume, not a polygon
    tally: a no-op can still come back re-triangulated, with a different
    polygon count and nothing actually removed.
    """
    if not mesh.vertices:
        return False
    return (before_volume - _volume(mesh)) > floor


def _consume(tool):
    """Delete the tool object and its mesh once a boolean has eaten it."""
    tool_mesh = tool.data
    bpy.data.objects.remove(tool)
    if getattr(tool_mesh, "users", 1) == 0:
        bpy.data.meshes.remove(tool_mesh)


def _apply(target, tool, operation, verify):
    """Run a boolean modifier, trying MANIFOLD then EXACT, and bake the first
    result that VERIFY accepts. Raise BooleanError if none does.

    MANIFOLD first because it is the one that copes with the near-coplanar glyph
    seams; EXACT is the fallback, and the one that historically comes back empty
    on exactly this input. Counting "did the polygon total change?" is not
    enough -- on 4.2 EXACT returned a differently-sized mesh that had not merged
    the glyph at all, so `verify` looks at the geometry, not the tally.
    """
    before = (len(target.data.vertices), len(target.data.polygons))
    mod = target.modifiers.new(name="Magpie Boolean", type='BOOLEAN')
    mod.operation = operation
    mod.object = tool

    baked = None
    for solver in ('MANIFOLD', 'EXACT'):
        try:
            mod.solver = solver
        except TypeError:
            continue        # solver not present in this Blender build
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        candidate = bpy.data.meshes.new_from_object(
            target.evaluated_get(depsgraph))
        untouched = (len(candidate.vertices), len(candidate.polygons)) == before
        if candidate.polygons and not untouched and verify(candidate):
            baked = candidate
            break
        bpy.data.meshes.remove(candidate)

    if baked is None:
        target.modifiers.remove(mod)
        return None

    target.modifiers.clear()
    old = target.data
    target.data = baked
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return target


def union(target, tool):
    """Boolean-union `tool` into `target`, consuming the tool. One watertight
    object comes back.

    Callers must give the two parts a real overlapping volume -- a glyph that
    merely rests coplanar on the plate face is the case that returns garbage.
    engine/swatch.py sinks the glyph base below the face on purpose.
    """
    want = _bounds(tool.bound_box, tool.matrix_world)
    result = _apply(target, tool, 'UNION',
                    lambda mesh: _swallows(mesh, want, target.matrix_world))
    if result is None:
        raise BooleanError(
            "could not emboss the text -- no boolean solver merged the "
            "letters onto the plate (Blender 4.2 cannot; update to 4.5 or newer)")
    _consume(tool)
    return heal(result)


def difference(target, tool):
    """Boolean-subtract `tool` from `target`, consuming the tool.

    Same trap as union: the modifier does not raise when it gives up, it returns
    the plate untouched -- here that ships a blank plate with no engraving in it.
    """
    before_volume = _volume(target.data)
    result = _apply(target, tool, 'DIFFERENCE',
                    lambda mesh: _shrinks(mesh, before_volume))
    if result is None:
        raise BooleanError(
            "could not deboss the text -- no boolean solver cut the letters "
            "into the plate (Blender 4.2 cannot; update to 4.5 or newer)")
    _consume(tool)
    return heal(result)
