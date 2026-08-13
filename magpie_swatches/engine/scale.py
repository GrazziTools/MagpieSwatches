"""The working scale, and why there is no final rescale.

The brief worried, rightly, that booleans go degenerate in the sub-millimetre
range: at Blender's factory 1 unit = 1 m, a 24 mm plate is 0.024 units and a
0.45 mm stroke is 0.00045 units, which is exactly where the exact solver starts
returning slivers and empty meshes.

The family's answer is a convention, not a rescale: **1 scene unit = 1 mm**, and
the geometry is authored directly in millimetres. The plate is then 24 units,
the stroke 0.45 units, and every boolean runs in a range the solver is happy in.
Nothing is built at metre scale and shrunk afterwards, so there is no "apply the
final scale factor at the end" step -- there is nothing to undo.

This also means the mini-scaling helper the other add-ons carry (PufferWalls'
scaletools.py, which grows a sculpt to a 32 mm or 75 mm figure) does NOT apply
here: a swatch has no reference object to scale to, its dimensions come straight
from the user in millimetres. This module is the swatch's entire scale layer.

STL carries no unit, so a slicer reads the exported numbers as millimetres --
which is what they are. The one place the metre default bites is inside Blender's
own UI and unit-aware exporters (FBX), which the add-on handles by offering to
set the scene to millimetres; it never changes the geometry to do so.
"""

# What context.scene.unit_settings.scale_length must be for "1 unit = 1 mm" to
# read correctly in Blender's metric UI. 0.001 m per unit == 1 mm per unit.
SCENE_UNIT_SCALE = 0.001
