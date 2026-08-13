"""Pre-flight checks on a swatch's parameters, run before any geometry exists.

Pure: no bpy, no side effects. Every failure names the field or number at fault
so the panel's error is something the user can act on without opening the code.
This module cannot see glyph spacing -- that would need rasterising the actual
font -- so MIN_GLYPH_SPACING stays a README caveat, not a check here.
"""

from ..constants import (ENGRAVE_FLOOR, HOLE_INSET, HOLE_ROUND,
                         MIN_FONT_SIZE, MIN_HOOK_SIZE, MODE_DEBOSS,
                         MODE_EMBOSS, RELIEF_MAX, RELIEF_MIN)
from . import hook as hook_geo
from . import plate as plate_geo


class ValidationError(Exception):
    """A swatch's parameters cannot be built. The message is ready to report."""


def _active_fields(p):
    """(label, body, size) for every field the user actually typed something
    into. Shared with swatch.py so validation and layout agree on what counts
    as empty -- whitespace-only counts as empty, same as a blank field.
    """
    return [(label, body, size) for label, body, size in
            (("Brand", p.brand, p.brand_size),
             ("Type", p.type, p.type_size),
             ("Color", p.color, p.color_size))
            if body and body.strip()]


def check(p) -> None:
    """Raise ValidationError on the first problem found. Returns None if `p`
    is safe to build.

    No text at all is NOT an error: it builds a blank plate. Generate is the
    button that puts geometry in the scene, so it has to work on the very
    first click of a fresh install, when every field is still empty -- a
    disabled button there means the add-on appears to have no way to insert
    anything at all. The blank plate is also useful in its own right, as a
    blank to letter by hand or to check the size against a real filament box.

    Field-level problems (stroke width) are reported before plate-level ones,
    so the smallest and most-likely-to-fail field is what the user sees first.
    """
    fields = _active_fields(p)

    for label, body, size in fields:
        if size < MIN_FONT_SIZE - 1e-9:
            raise ValidationError(
                f"{label} text at {size:.1f} mm is below the "
                f"{MIN_FONT_SIZE:.1f} mm minimum -- its strokes would be "
                f"thinner than the nozzle can print. Raise its size.")

    if p.plate_w <= 0.0 or p.plate_h <= 0.0:
        raise ValidationError("Plate width and height must both be greater "
                              "than zero.")
    if p.thickness <= 0.0:
        raise ValidationError("Plate thickness must be greater than zero.")

    max_radius = min(p.plate_w, p.plate_h) * 0.5
    if not (0.0 <= p.corner_radius <= max_radius + 1e-9):
        raise ValidationError(
            f"Corner radius {p.corner_radius:.1f} mm does not fit a "
            f"{p.plate_w:.0f} x {p.plate_h:.0f} mm plate -- it must be "
            f"between 0 and {max_radius:.1f} mm.")

    if p.hole:
        if p.hole_style == HOLE_ROUND:
            if p.hole_diameter <= 0.0:
                raise ValidationError("Hole diameter must be greater than "
                                      "zero.")
            if p.hole_diameter >= 2.0 * HOLE_INSET:
                raise ValidationError(
                    f"A {p.hole_diameter:.1f} mm hole does not fit its "
                    f"corner -- it must be smaller than "
                    f"{2.0 * HOLE_INSET:.1f} mm.")
            inset = HOLE_INSET
            r = p.hole_diameter * 0.5
            bounds = (-r, -r, r, r)
        else:  # HOLE_HOOK
            # The hook's shape is fixed artwork, so the one thing that can
            # go wrong is scaling it past what its own material can form:
            # shrink the whole drawing and its tongue (the bead a nozzle has
            # to lay down) thins with it, past MIN_STROKE, before the whole
            # thing turns into an unresolvable sliver. See constants.py's
            # MIN_HOOK_SIZE for the measurement.
            if p.hook_size < MIN_HOOK_SIZE - 1e-9:
                raise ValidationError(
                    f"Hook size {p.hook_size:.1f} mm is below the "
                    f"{MIN_HOOK_SIZE:.1f} mm minimum -- its tongue would be "
                    f"too thin for a nozzle to print reliably. Make it "
                    f"bigger.")
            # Checked after the size itself, so a nonsense size gets its own
            # named error first rather than a confusing footprint number
            # derived from it.
            inset = hook_geo.hook_inset(p.hook_size)
            if inset * 2.0 > min(p.plate_w, p.plate_h) + 1e-6:
                raise ValidationError(
                    f"The hook is too big for a {p.plate_w:.0f} x "
                    f"{p.plate_h:.0f} mm plate -- reduce the hook size, use "
                    f"a round hole instead, or use a bigger plate.")
            bounds = hook_geo.hook_bounds(p.hook_size)

        # Everything above assumes the hole/hook sits exactly where
        # hole_center() puts it. Offset X/Y (Adjust panel) can move it
        # anywhere from there, so what actually has to stay valid is the
        # OFFSET position -- checked here, against the real outline, rather
        # than trusting the property's own generous min/max (which cannot
        # see the plate size or the hook's footprint at all). Goes through
        # plate.hole_position(), the same call engine/swatch.py makes for
        # both the cut and the text ceiling, so this check can never drift
        # from where the opening actually ends up.
        cx, cy = plate_geo.hole_position(p.plate_w, p.plate_h, inset,
                                         p.hole_offset_x, p.hole_offset_y)
        min_x, min_y, max_x, max_y = bounds
        half_w, half_h = p.plate_w * 0.5, p.plate_h * 0.5
        if (cx + min_x < -half_w - 1e-6 or cx + max_x > half_w + 1e-6 or
                cy + min_y < -half_h - 1e-6 or cy + max_y > half_h + 1e-6):
            raise ValidationError(
                "The hole's offset pushes it outside the plate -- bring "
                "Offset X/Y back in, or use a smaller hole/hook.")
        # Named separately from the "text is too tall" error in
        # engine/swatch.py: this fires because the HOLE moved into the
        # text's own territory, not because the text grew. Limited outright
        # rather than allowed with its own risk of ambiguous overlap: the
        # hole simply cannot cross into the lower half at all.
        if cy < -1e-6:
            raise ValidationError(
                "The hole's Y offset drops it into the lower half of the "
                "plate, where the text lives -- reduce Offset Y so the "
                "hole stays in the upper half.")

    if p.mode == MODE_EMBOSS:
        if not (RELIEF_MIN - 1e-9 <= p.relief <= RELIEF_MAX + 1e-9):
            raise ValidationError(
                f"Emboss relief {p.relief:.2f} mm is outside the printable "
                f"range ({RELIEF_MIN:.1f}-{RELIEF_MAX:.1f} mm). Taller relief "
                f"risks the nozzle knocking letters loose mid-print.")
    elif p.mode == MODE_DEBOSS:
        if p.engrave <= 0.0:
            raise ValidationError("Engrave depth must be greater than zero.")
        max_engrave = p.thickness - ENGRAVE_FLOOR
        if p.engrave > max_engrave + 1e-9:
            raise ValidationError(
                f"Engrave depth {p.engrave:.1f} mm leaves less than "
                f"{ENGRAVE_FLOOR:.1f} mm of material under a "
                f"{p.thickness:.1f} mm plate. Reduce it or thicken the plate.")
