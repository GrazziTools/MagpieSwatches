"""The swatch plate: a rounded rectangle, and the cylinder that bores its hole.

Pure geometry -- millimetres in, a linked object out. The plate is built sitting
on the bed: its bottom face is at Z = 0 and its top face at Z = thickness, so the
top face is the one the text is embossed onto or debossed into, and the part is
already the right way up for a slicer.
"""

import math

import bmesh

from . import objects


def _rounded_rect_outline(width: float, height: float, radius: float,
                          segments: int) -> list[tuple[float, float]]:
    """Counter-clockwise (x, y) loop of a rectangle with four rounded corners,
    centred on the origin.

    The straight edges are implicit: consecutive corner arcs leave a gap that
    becomes one edge when the face is built, so only the arc points are emitted.
    """
    # Clamp the radius to what fits -- a radius past half the short side would
    # make the arcs cross and self-intersect the loop.
    radius = max(0.0, min(radius, min(width, height) * 0.5))
    hw, hh = width * 0.5, height * 0.5

    if radius <= 1e-6:
        return [(hw, -hh), (hw, hh), (-hw, hh), (-hw, -hh)]

    cx, cy = hw - radius, hh - radius
    # (corner centre, start angle) for each corner, walked CCW from bottom-right.
    corners = [((cx, -cy), -math.pi / 2),   # bottom-right
               ((cx, cy), 0.0),             # top-right
               ((-cx, cy), math.pi / 2),    # top-left
               ((-cx, -cy), math.pi)]       # bottom-left

    loop = []
    for (ox, oy), start in corners:
        for i in range(segments + 1):
            a = start + (math.pi / 2) * (i / segments)
            loop.append((ox + radius * math.cos(a), oy + radius * math.sin(a)))
    return loop


def create_plate(width: float, height: float, thickness: float,
                 corner_radius: float, segments: int, name: str) -> object:
    """Build the rounded plate as a closed, manifold solid on the bed."""
    outline = _rounded_rect_outline(width, height, corner_radius, segments)

    bm = bmesh.new()
    verts = [bm.verts.new((x, y, 0.0)) for x, y in outline]
    face = bm.faces.new(verts)
    up = bmesh.ops.extrude_face_region(bm, geom=[face])
    moved = [g for g in up['geom'] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=moved, vec=(0.0, 0.0, thickness))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return objects.from_bmesh(name, bm)


def hole_center(width: float, height: float, inset: float) -> tuple[float, float]:
    """Centre of the mounting hole: the TOP-LEFT corner, `inset` from each of
    the two nearest edges.

    Top-left, not top-right, because the text is left-aligned and sits in the
    lower part of the plate: the hole takes the corner the text block has
    already vacated, so neither has to make room for the other sideways.
    """
    return (-width * 0.5 + inset, height * 0.5 - inset)


def hole_position(width: float, height: float, inset: float,
                  offset_x: float = 0.0, offset_y: float = 0.0) -> tuple[float, float]:
    """Where the hole/hook actually ends up: hole_center()'s derived
    position, plus a caller-supplied nudge away from it.

    The one place this math happens -- swatch.py (the cut, and the text
    ceiling above it) and validate.py (the offset bounds check) all call
    this instead of each recomputing hole_center() + offset by hand, so
    none of the three can drift into disagreeing about where the opening
    really is. Lives here rather than on SwatchParams because this module
    has no dependency on either caller, so both can depend on it without
    risking an import cycle between them.
    """
    cx, cy = hole_center(width, height, inset)
    return cx + offset_x, cy + offset_y


def hole_tool(diameter: float, cx: float, cy: float, z0: float, z1: float,
              segments: int, name: str) -> object:
    """A capped cylinder to subtract for the mounting hole.

    Runs from z0 to z1, which the caller sets to overshoot both faces of the
    plate, so the cut never leaves a glyph face coplanar with a plate face.
    """
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments,
                          radius1=diameter * 0.5, radius2=diameter * 0.5,
                          depth=z1 - z0)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(cx, cy, (z0 + z1) * 0.5))
    return objects.from_bmesh(name, bm)
