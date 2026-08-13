"""Add-on preferences: does the N panel draw the logo, and where Export STL
last saved.

Lives in preferences, not in the scene, on purpose -- both are screen-space /
machine-local facts about using the add-on, not part of the .blend's own
content. Each add-on in the family carries its own copy; there is no shared
store between extensions, and inventing one would be worse than the
duplication.

show_logo() and entry() never raise, by design -- see their own docstrings --
so a caller can use them unconditionally. show_logo() is read by panel.py, both
for the main panel's toggle logic and the mirrored checkbox in About.
last_export_dir is read/written by MAGPIESWATCHES_OT_export in operators.py.
Nothing in engine/ knows either of these exist.
"""

import bpy

from ..constants import BRAND


class MAGPIESWATCHES_AP_prefs(bpy.types.AddonPreferences):
    # Installed as an extension the package is dotted (bl_ext.user_default.
    # magpie_swatches.ui), so the id has to be derived, never hardcoded: drop
    # the trailing ".ui" and what is left is the add-on module Blender knows.
    bl_idname = __package__.rpartition(".")[0] or __package__

    show_logo: bpy.props.BoolProperty(
        name="Show Logo",
        description="Draw the %s logo at the top of the N panel" % BRAND,
        default=True,
    )

    # Written by MAGPIESWATCHES_OT_export after a successful export, read back
    # to seed the file browser's starting folder next time. A scene property
    # would travel inside the .blend and open in someone else's folder on
    # their machine; this is a fact about THIS install, so it belongs here
    # instead.
    last_export_dir: bpy.props.StringProperty(
        name="Last export folder", subtype='DIR_PATH', default="",
    )

    def draw(self, context):
        self.layout.prop(self, "show_logo")


def entry(context):
    """The preferences block itself, or None when it cannot be reached.

    Lets any panel draw the switch inline. Preferences is where Blender users
    expect an add-on switch to LIVE, but it is not where a first-timer will ever
    look for it -- so About mirrors it, and both drive the same property.
    """
    try:
        return context.preferences.addons[
            MAGPIESWATCHES_AP_prefs.bl_idname].preferences
    except (KeyError, AttributeError):
        return None


def show_logo(context):
    """True unless the user turned the logo off.

    Never raises. Headless tests and a half-registered add-on both hit a missing
    preferences entry, and a missing entry must not take the whole panel down --
    so the fallback is the default: draw it.
    """
    try:
        prefs = context.preferences.addons[
            MAGPIESWATCHES_AP_prefs.bl_idname].preferences
        return bool(prefs.show_logo)
    except (KeyError, AttributeError):
        return True
