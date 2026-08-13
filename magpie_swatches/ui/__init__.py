"""UI layer aggregation. The package root imports CLASSES + register_props/
unregister_props from here so there is a single registration list to maintain.
"""

import bpy

from .preferences import MAGPIESWATCHES_AP_prefs
from .properties import MagpieSwatchesProps
from .operators import (MAGPIESWATCHES_OT_add_swatch,
                        MAGPIESWATCHES_OT_export,
                        MAGPIESWATCHES_OT_export_fbx,
                        MAGPIESWATCHES_OT_fix_units,
                        MAGPIESWATCHES_OT_generate,
                        MAGPIESWATCHES_OT_reset)
from .panel import (MAGPIESWATCHES_PT_about, MAGPIESWATCHES_PT_main,
                    MAGPIESWATCHES_PT_settings)

CLASSES = (
    MAGPIESWATCHES_AP_prefs,   # first: the panel reads it while drawing
    MagpieSwatchesProps,
    MAGPIESWATCHES_OT_add_swatch,
    MAGPIESWATCHES_OT_generate,
    MAGPIESWATCHES_OT_export,
    MAGPIESWATCHES_OT_export_fbx,
    MAGPIESWATCHES_OT_reset,
    MAGPIESWATCHES_OT_fix_units,
    MAGPIESWATCHES_PT_main,
    MAGPIESWATCHES_PT_settings,
    MAGPIESWATCHES_PT_about,
)

from . import branding  # noqa: E402


def register_props():
    bpy.types.Scene.magpie_swatches = bpy.props.PointerProperty(
        type=MagpieSwatchesProps)
    branding.load()


def unregister_props():
    branding.unload()
    if hasattr(bpy.types.Scene, "magpie_swatches"):
        del bpy.types.Scene.magpie_swatches
