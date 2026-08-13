"""Magpie Swatches -- generate printable filament sample swatches.

Clean-room add-on. Hard rule: engine/ is pure geometry (headless-testable, no
UI); ui/ is the only place that touches panels/props/operators. Importing this
package has NO side effects -- registration happens only in register().
"""

import bpy

from . import ui

_CLASSES = ui.CLASSES


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    ui.register_props()


def unregister():
    ui.unregister_props()
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
