"""The hanging hook: an open channel you thread a closed keyring into,
turning the swatch to walk the ring down to its seat.

Pure geometry -- millimetres in, a linked object out, same contract as
plate.py. The shape itself follows the community-standard keyring channel
(see hook_shape.py) and is baked there as a normalised outline; all this
module does is scale it, place it, and hand back a solid to subtract.

WHY THIS IS A BAKED OUTLINE AND NOT A FORMULA. The first version built the
hook as an Archimedean spiral from parameters (seat diameter, channel width,
coil thickness, turns). It produced a clean, printable spiral -- and the
wrong shape. The giveaway, MEASURED off the reference part's raster map: its
tongue TAPERS from about 1.6 mm at the base down to a point at the tip, and
a constant-width channel cannot do that, because a spiral's two walls stay
parallel by construction. No amount of parameter tuning closes that gap; it
needed a different curve entirely. Drawing the shape and tracing the drawing
is both exact and simpler than any formula that would have fitted it.
"""

import bmesh

from . import objects
from .hook_shape import OUTLINE


class HookError(Exception):
    """The hook's parameters cannot be built into valid geometry."""


def _scaled_outline(height: float) -> list[tuple[float, float]]:
    """The baked outline scaled to `height` millimetres tall, still centred
    on its own origin."""
    if height <= 0.0:
        raise HookError("Hook size must be greater than zero.")
    return [(x * height, y * height) for x, y in OUTLINE]


def hook_bounds(height: float) -> tuple[float, float, float, float]:
    """(min_x, min_y, max_x, max_y) of the hook around its own centre.

    The hook is markedly taller than it is wide (0.767 : 1), so a caller that
    needs to know how far it reaches in ONE direction has to ask for that
    direction rather than assume a circle. swatch.py depends on this:
    treating the hook as a circle of its own longest reach previously cost
    the lettering 5.5 mm of vertical room it did not owe, and shipped as a
    "text is too tall for the plate" error on ordinary settings.
    """
    pts = _scaled_outline(height)
    xs = [x for x, _ in pts]
    ys = [y for _, y in pts]
    return min(xs), min(ys), max(xs), max(ys)


# Clear plate material to keep between the hook's outer edge and the plate
# boundary. 1.5 mm, MEASURED off the reference part (which clears its own
# plate edges by 1.3-1.5 mm). On a 24 mm plate every half millimetre here
# comes straight out of the room the lettering has to work in.
WALL_MARGIN = 1.5


def hook_inset(height: float) -> float:
    """Distance from each of the two nearest plate edges to the hook's centre.

    Sized off the real BOUNDS, not the longest reach: the hook sits in the
    top-left corner, so what decides how far its centre must sit from those
    two edges is how far it reaches LEFT and UP, nothing else. swatch.py uses
    this same function both to place the cut and to cap the text, so the two
    can never disagree about where the hook sits.
    """
    min_x, _, _, max_y = hook_bounds(height)
    return max(-min_x, max_y) + WALL_MARGIN


def hook_tool(height: float, cx: float, cy: float, z0: float, z1: float,
              name: str) -> object:
    """The solid to subtract for the hook, running z0 to z1.

    The caller sets those to overshoot both plate faces, so the cut never
    leaves a face coplanar with a plate face -- the case that makes an exact
    boolean solver return degenerate geometry, or nothing at all.

    One closed outline extruded once: no unions, no second tool. The baked
    shape already includes the ring's seat and the channel leading to it as
    a single loop, which is why this needs none of the two-solid dance the
    parametric version did.
    """
    pts = _scaled_outline(height)

    bm = bmesh.new()
    verts = [bm.verts.new((x + cx, y + cy, z0)) for x, y in pts]
    face = bm.faces.new(verts)
    up = bmesh.ops.extrude_face_region(bm, geom=[face])
    moved = [g for g in up['geom'] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=moved, vec=(0.0, 0.0, z1 - z0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return objects.from_bmesh(name, bm)
