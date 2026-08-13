"""Pure geometry layer.

Every module here is headless-testable: it builds meshes from plain numbers and
never reads bpy.context, a PropertyGroup, or anything in ui/. Operators translate
the panel's state into the explicit arguments these functions take, so the same
code path runs in `blender --background` under test and in the live add-on.
"""
