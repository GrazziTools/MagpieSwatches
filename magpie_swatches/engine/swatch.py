"""Orchestrates plate, hole, text and boolean into one finished swatch.

The only entry point is build_swatch(). Everything else here is a private
helper for the two places raw numbers turn into placement math: how much
width the hole leaves for text (_text_box), and how the label sits in Z for
each mode (_place_label). Both are documented in detail because getting a
sign wrong there is the one mistake in this add-on that ships a broken part
while still looking like it worked.
"""

from dataclasses import dataclass, field as _field

from mathutils import Matrix

from ..constants import (COPLANAR_GUARD, DEFAULT_BOTTOM_MARGIN,
                         DEFAULT_HOLE_OFFSET, DEFAULT_HOOK_SIZE, HOLE_INSET,
                         HOLE_ROUND, HOLE_SEGMENTS, LINE_GAP,
                         MIN_GLYPH_SPACING, MODE_DEBOSS, MODE_EMBOSS, OBJ,
                         TEXT_MARGIN, TYPE_KEY, TYPE_SWATCH)
from . import booleans, hook, text
from . import plate as plate_geo
from .validate import ValidationError, _active_fields, check


@dataclass
class SwatchParams:
    """Everything build_swatch() needs, in millimetres. ui/operators.py builds
    one of these from the scene properties; nothing else in engine/ reads
    bpy.context, so this dataclass is the entire boundary between UI and
    geometry.
    """
    brand: str
    type: str
    color: str
    brand_size: float
    type_size: float
    color_size: float
    plate_w: float
    plate_h: float
    thickness: float
    corner_radius: float
    corner_segments: int
    hole: bool
    hole_diameter: float
    mode: str
    relief: float
    engrave: float
    # Defaults to ROUND here (not constants.DEFAULT_HOLE_STYLE, which is
    # HOOK) so any existing caller that builds a SwatchParams without
    # mentioning hole style at all -- including every test written before
    # the hook existed -- keeps getting exactly the plain round hole it
    # always did. ui/operators.py always passes hole_style explicitly, so
    # this default never actually reaches a real Generate click; the
    # panel's own default (HOOK) lives in ui/properties.py.
    hole_style: str = HOLE_ROUND
    # Tied to the SAME constant ui/properties.py's default comes from, rather
    # than a duplicated literal -- a stale copy here is exactly how a caller
    # that builds a HOOK-style SwatchParams without naming the size would
    # silently get a different hook than Generate ships. (Measured: the
    # parametric version's defaults drifted this way once already.)
    hook_size: float = DEFAULT_HOOK_SIZE
    # (0, 0) reproduces exactly the derived top-left position -- see
    # _hole_position() below. Same stale-default trap as hook_size: tied to
    # constants.py's own constant rather than a duplicated literal.
    hole_offset_x: float = DEFAULT_HOLE_OFFSET
    hole_offset_y: float = DEFAULT_HOLE_OFFSET
    # Only the BOTTOM margin is adjustable -- left/right feed _text_box()
    # and widening them costs lettering width, while this one is free.
    # Defaults to the same TEXT_MARGIN every other side uses, so a caller
    # that never mentions it (including every test written before this
    # existed) gets exactly the old layout.
    bottom_margin: float = DEFAULT_BOTTOM_MARGIN


@dataclass
class BuildResult:
    """The finished object plus the label's layout report, so the operator can
    tell the user about an auto-shrink without re-deriving it.

    `label` is None for a blank plate (no text fields filled in), so callers
    must check it before reading its lines.
    """
    obj: object
    label: object = None
    fields: list = _field(default_factory=list)


def _text_box(p: SwatchParams) -> float:
    """How wide a line may be: the full plate minus a margin each side.

    No sideways allowance for the hole. The hole sits in the TOP-LEFT corner
    and the text block is anchored to the BOTTOM, so they are separated
    vertically -- _anchor_label() enforces that -- and the text gets the whole
    width instead of every line being squeezed by a hole it never reaches.
    """
    return max(0.0, p.plate_w - 2.0 * TEXT_MARGIN)


def _hole_inset(p: SwatchParams) -> float:
    """Distance from each of the two nearest plate edges to the hole/hook
    centre.

    A fixed constant (HOLE_INSET) for the round style, which never changes
    size. The hook does change size with its own parameters, so it needs its
    centre pushed back by however far IT reaches (hook.hook_inset()) rather
    than a number calibrated for the much smaller round hole -- see that
    function's own docstring. Used by both build_swatch() (to cut the hole
    in the right place) and _anchor_label() (to cap the text at the right
    place), so the two can never disagree about where the opening sits.
    """
    if p.hole_style == HOLE_ROUND:
        return HOLE_INSET
    return hook.hook_inset(p.hook_size)


def _hole_position(p: SwatchParams) -> tuple[float, float]:
    """Where the hole/hook actually ends up, for a SwatchParams -- see
    plate.hole_position() for the actual math and why it lives there.

    Used by BOTH build_swatch() (where the cut happens) and _anchor_label()
    (where the text ceiling is computed) -- exactly like _hole_inset(), and
    for the same reason: if the two ever disagreed about where the opening
    really is, the text would silently overlap it. engine/validate.py calls
    plate.hole_position() directly for the same reason, from the other side
    of a boundary this module cannot cross without an import cycle.
    """
    return plate_geo.hole_position(p.plate_w, p.plate_h, _hole_inset(p),
                                   p.hole_offset_x, p.hole_offset_y)


def _anchor_label(label_obj, p: SwatchParams) -> None:
    """Left-align the block against the left margin and sit it on the bottom
    margin.

    Bottom-anchored rather than centred so that a two-line swatch and a
    three-line one share the same bottom baseline -- a row of these hanging
    side by side then reads as a set. It is also what keeps the block clear of
    the hole without any horizontal give.

    The LEFT margin is TEXT_MARGIN and the BOTTOM one is p.bottom_margin --
    they are separate because raising the bottom is free while raising the
    sides is not: _text_box() derives the usable width from TEXT_MARGIN, so
    widening it takes room straight out of the lettering and pushes it into
    the auto-shrink. Only the bottom can be given away without costing
    anything.
    """
    xs = [v.co.x for v in label_obj.data.vertices]
    ys = [v.co.y for v in label_obj.data.vertices]
    dx = (-p.plate_w * 0.5 + TEXT_MARGIN) - min(xs)
    dy = (-p.plate_h * 0.5 + p.bottom_margin) - min(ys)
    label_obj.data.transform(Matrix.Translation((dx, dy, 0.0)))

    # The block grows upward from the bottom margin, so the only way it can
    # collide with anything is by reaching the hole's row (or running off the
    # top). There is no vertical auto-shrink, so say so plainly instead of
    # letting the text run through the hole or the hook.
    top = max(ys) + dy
    ceiling = p.plate_h * 0.5 - TEXT_MARGIN
    if p.hole:
        # The hook needs its OWN inset (see _hole_inset()): it reaches much
        # farther from its centre than a round hole's radius does, and by an
        # amount that depends on its own parameters, so it cannot share the
        # round style's fixed HOLE_INSET without risking the centre landing
        # too close to the plate edge.
        _, hole_cy = _hole_position(p)
        if p.hole_style == HOLE_ROUND:
            reach = p.hole_diameter * 0.5
        else:
            # How far the hook reaches DOWN, specifically -- not its longest
            # reach in any direction. The text grows upward from the bottom
            # margin, so the only part of the hook it can ever run into is
            # the lowest one, and the hook is a good deal taller than it is
            # wide. Charging the text the larger number is what shipped as a
            # "text is too tall for the plate" error on ordinary settings.
            # hook_bounds() measures the SAME outline hook_tool() extrudes,
            # so this cannot fall out of sync with the real geometry.
            _, min_y, _, _ = hook.hook_bounds(p.hook_size)
            reach = -min_y
        ceiling = min(ceiling, hole_cy - reach - MIN_GLYPH_SPACING)
    if top > ceiling + 1e-6:
        raise ValidationError(
            f"The text is {top - ceiling:.1f} mm too tall for the plate. "
            f"Reduce the text sizes, make the plate taller, or turn the "
            f"hanging hole off.")


def _place_label(plate_obj, label_obj, p: SwatchParams):
    """Sink or raise the label so it overlaps the plate's top face by
    COPLANAR_GUARD, then run the matching boolean.

    EMBOSS and DEBOSS are NOT mirror images: emboss adds material above the
    face, deboss removes material below it, so the guard has to push the
    label in opposite directions -- see constants.COPLANAR_GUARD. The label's
    real Z extent is measured off its baked mesh rather than trusted from the
    extrude value passed in, because that value is a per-side thickness and
    the mesh is the ground truth for where its faces actually landed.
    """
    zs = [v.co.z for v in label_obj.data.vertices]
    z0, z1 = min(zs), max(zs)
    top = p.thickness

    if p.mode == MODE_EMBOSS:
        # Top of the relief lands exactly `relief` above the plate face; the
        # base then sinks below the face by whatever remains of the solid's
        # own thickness, which construction guarantees is >= COPLANAR_GUARD.
        dz = (top + p.relief) - z1
        label_obj.data.transform(Matrix.Translation((0.0, 0.0, dz)))
        return booleans.union(plate_obj, label_obj)

    # DEBOSS: the cavity floor lands `engrave` below the face; the solid's
    # top then rises above the face by COPLANAR_GUARD, so the cut actually
    # breaks the surface instead of stopping just short of it.
    dz = (top - p.engrave) - z0
    label_obj.data.transform(Matrix.Translation((0.0, 0.0, dz)))
    return booleans.difference(plate_obj, label_obj)


def _swatch_name(fields) -> str:
    """"{first non-empty field} - SWATCH" -- family convention: the object is
    found later by its TYPE_KEY tag, never by this name, so the name only
    has to be readable, not unique. With no text at all it is "Blank", not
    "Swatch", which would read as "Swatch - SWATCH".
    """
    source = next((body.strip() for _, body, _ in fields if body.strip()),
                  "Blank")
    return f"{source} - SWATCH"


def build_swatch(p: SwatchParams):
    """Build one finished swatch object, linked into the scene root.

    Raises ValidationError, text.TextOverflowError or booleans.BooleanError.
    The operator is the only caller expected to catch them and turn them into
    a self.report({'ERROR'}, ...).
    """
    check(p)
    fields = _active_fields(p)

    plate_obj = plate_geo.create_plate(p.plate_w, p.plate_h, p.thickness,
                                       p.corner_radius, p.corner_segments,
                                       OBJ + "plate")

    if p.hole:
        cx, cy = _hole_position(p)
        z0, z1 = -1.0, p.thickness + 1.0
        if p.hole_style == HOLE_ROUND:
            tool = plate_geo.hole_tool(p.hole_diameter, cx, cy, z0, z1,
                                       HOLE_SEGMENTS, OBJ + "hole")
            plate_obj = booleans.difference(plate_obj, tool)
        else:
            # One solid, one boolean: the baked outline already carries the
            # ring's seat and the channel leading to it as a single closed
            # loop, so there is nothing to combine first.
            tool = hook.hook_tool(p.hook_size, cx, cy, z0, z1,
                                  OBJ + "hook")
            plate_obj = booleans.difference(plate_obj, tool)

    # No text at all is a legitimate swatch: the blank plate. Skip the whole
    # text-and-boolean stage rather than feeding build_label() an empty list,
    # which would produce an empty mesh with no Z extent for _place_label() to
    # measure against.
    label = None
    if fields:
        usable_width = _text_box(p)
        if usable_width <= 0.0:
            raise ValidationError(
                "The plate is too narrow for any text -- widen it, or reduce "
                "the margin.")

        depth = p.relief if p.mode == MODE_EMBOSS else p.engrave
        font_data = text.resolve_font()
        label = text.build_label(fields, font_data, depth + COPLANAR_GUARD,
                                 usable_width, LINE_GAP, OBJ + "label")
        _anchor_label(label.obj, p)

        plate_obj = _place_label(plate_obj, label.obj, p)

    plate_obj[TYPE_KEY] = TYPE_SWATCH
    plate_obj.name = _swatch_name(fields)
    return BuildResult(obj=plate_obj, label=label, fields=fields)
