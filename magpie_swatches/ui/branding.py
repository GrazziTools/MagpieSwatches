"""Loads the logo image into a preview collection so the panel can show it big.
Gracefully no-ops if assets/logo.png is missing (panel falls back to text).

load() and unload() are called once each, from ui/__init__.py's
register_props()/unregister_props(); logo_icon_id() is read on every panel
redraw by panel.py's _banner(). Nothing here reaches into engine/ or touches
scene data -- it is UI chrome only."""

from pathlib import Path

import bpy
import bpy.utils.previews

_previews = {}


def load():
    if "main" in _previews:
        return
    pcoll = bpy.utils.previews.new()
    logo = Path(__file__).resolve().parent.parent / "assets" / "logo.png"
    if logo.is_file():
        try:
            pcoll.load("logo", str(logo), 'IMAGE')
        except Exception:
            pass
    _previews["main"] = pcoll


def unload():
    for pcoll in _previews.values():
        try:
            bpy.utils.previews.remove(pcoll)
        except Exception:
            pass
    _previews.clear()


def logo_icon_id():
    pcoll = _previews.get("main")
    if pcoll is not None and "logo" in pcoll:
        return pcoll["logo"].icon_id
    return 0
