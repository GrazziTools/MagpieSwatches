"""Low-level object plumbing shared by the geometry modules.

Everything a boolean touches has to be evaluable in the depsgraph, which means
linked into the scene -- an unlinked object is invisible to
`obj.evaluated_get(depsgraph)` and the modifier reads an empty mesh. So the
builders here link into the scene's root collection. The operator relinks the
finished swatch into the user's active collection afterwards; the engine stays
free of any opinion about which collection that is.
"""

import bpy


def link(obj):
    """Put `obj` in the scene's root collection if it is not already there."""
    coll = bpy.context.scene.collection
    if obj.name not in coll.objects:
        coll.objects.link(obj)
    return obj


def from_bmesh(name: str, bm) -> bpy.types.Object:
    """Bake a bmesh into a fresh linked object, freeing the bmesh."""
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))


def remove(obj) -> None:
    """Delete an object and its mesh datablock."""
    me = obj.data
    bpy.data.objects.remove(obj)
    if isinstance(me, bpy.types.Mesh) and me.users == 0:
        bpy.data.meshes.remove(me)
