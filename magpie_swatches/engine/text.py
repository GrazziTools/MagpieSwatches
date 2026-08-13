"""Text to solid: turn each field's string into an extruded glyph mesh, size it,
and stack the lines centred on the plate.

The glyphs come from a Blender FONT curve (built-in Bfont by default, or a font
the user picked), extruded to a solid and baked to a mesh through the depsgraph
so the same path runs headless. Nothing here positions the label in Z against the
plate -- swatch.py does that, differently for emboss and deboss. Here the label
is built centred on the origin: X centred, the lines stacked and centred in Y,
and the solid centred on Z = 0.
"""

from dataclasses import dataclass, field as _field
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix

from . import objects
from .booleans import MERGE_DIST
from ..constants import MIN_FONT_SIZE, MIN_STROKE


class TextError(Exception):
    """Base for text-layout failures the operator turns into a panel error."""


class TextOverflowError(TextError):
    """A line will not fit the plate width even shrunk to the font-size floor."""

    def __init__(self, field: str, chars: int, width: float):
        self.field = field
        self.chars = chars
        super().__init__(
            f"{field} is too long to fit ({chars} characters). Shorten it, widen "
            f"the plate, or lower its size -- it cannot shrink below "
            f"{MIN_FONT_SIZE:.2f} mm without the strokes becoming unprintable")


@dataclass
class Line:
    """One field's laid-out line, ready for the operator to report on."""
    field: str
    body: str
    requested_size: float
    final_size: float
    width: float
    height: float
    shrunk: bool = False
    stroke: float = 0.0     # finished stem width in mm, after any auto-shrink


@dataclass
class Label:
    """The built label object plus what happened while laying it out."""
    obj: object
    lines: list = _field(default_factory=list)


# Shipped with the add-on: Liberation Sans Bold (SIL Open Font License 1.1,
# licence text alongside it in assets/). Blender's own Bfont is too light to
# print at swatch sizes -- MEASURED, its stem is 0.144 of the cap height
# against Liberation Bold's 0.209, so at any given letter height this one lays
# down about 45% more material. That difference is the whole reason a font is
# bundled at all rather than relying on what Blender happens to ship.
_BUNDLED_FONT = (Path(__file__).resolve().parent.parent / "assets" /
                 "LiberationSans-Bold.ttf")


def resolve_font():
    """The font to letter with: always the bundled bold.

    Never raises. If even the bundled file is missing (a broken install) it
    returns None, which means Blender's built-in Bfont -- lettering that is
    too light to print is still better than a traceback. There is no custom
    font picker in this version (see README's Security section for why), so
    this never reads a path the user supplied.
    """
    try:
        return bpy.data.fonts.load(str(_BUNDLED_FONT), check_existing=True)
    except (RuntimeError, OSError):
        return None


def _bounds(mesh):
    """(min, max) tuples over x, y, z of a mesh's vertices."""
    xs = [v.co.x for v in mesh.vertices]
    ys = [v.co.y for v in mesh.vertices]
    zs = [v.co.z for v in mesh.vertices]
    return ((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)))


def _line_mesh(body: str, font_data, size: float, extrude: float,
               offset: float = 0.0):
    """Bake one string to an extruded mesh, centred on the origin.

    `offset` would fatten every glyph outline by that much on each side --
    Blender's own Curve.offset, and the obvious synthetic-bold fix for a
    font too thin to print. Always 0.0 in this add-on: it was tried and
    rejected (see the "WHY THERE IS NO SYNTHETIC BOLD HERE" note below
    metrics()) for self-intersecting outlines on real words, not just
    single letters. Left as a parameter rather than removed because
    `metrics()` reuses this same function to measure a plain "I" and
    passing 0.0 explicitly there would be no clearer than the default.

    The returned mesh is owned by the caller and must be removed after use. It
    carries no object -- a temporary object is created only long enough for the
    depsgraph to evaluate the curve into geometry.
    """
    cu = bpy.data.curves.new(name="MS_text", type='FONT')
    cu.body = body
    cu.size = size
    cu.offset = offset
    if font_data is not None:
        cu.font = font_data
    # LEFT, not CENTER: the lines are left-aligned against a common margin, so
    # a short Brand and a long Color start at the same x instead of each being
    # centred on its own width. swatch.py then anchors the whole block once.
    cu.align_x = 'LEFT'
    cu.align_y = 'CENTER'
    cu.fill_mode = 'BOTH'
    # Extrude is per-side, so the solid comes out 2*extrude thick and centred on
    # Z = 0. swatch.py measures the real Z extent rather than trusting this, so
    # the exact factor never has to be assumed here.
    cu.extrude = extrude

    obj = bpy.data.objects.new("MS_text", cu)
    objects.link(obj)
    try:
        # A freshly linked object is not yet reflected in a stale depsgraph --
        # without this update the evaluated mesh can come back with caps
        # missing (measured: the front cap silently absent, every letter left
        # open on one side). booleans.py hits the same requirement before
        # every evaluated_depsgraph_get() and this needs the same discipline.
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph))
    finally:
        bpy.data.objects.remove(obj)
        bpy.data.curves.remove(cu)
    return me


# Reference em size for measuring a font. Big enough to keep the measurements
# clear of float noise; both results are ratios, so the number itself does not
# matter.
_METRIC_REF_EM = 10.0


def metrics(font_data) -> tuple[float, float, float]:
    """(cap height, stem width, cap band mid-Y) per em of this font, MEASURED
    not assumed.

    Cap height and stem are needed because Blender's Curve.size is an EM size,
    and em is not what anyone means by "3 mm text" -- it includes room for
    ascenders and descenders that most strings never use. MEASURED at the same
    em size: Blender's Bfont puts a cap at 0.682 of the em, Liberation Sans
    Bold at 0.488. Sizing by em would make the same number produce visibly
    different letters per font; sizing by CAP HEIGHT is what a caliper on the
    printed part measures, so that is what the add-on's size fields mean.

    The mid-Y is needed for STACKING: align_y='CENTER' centres a glyph on the
    font's own metrics (roughly cap-height-to-descender), not on the tight ink
    bbox of whatever string happens to be on that line -- an accent or a
    descender shifts a string's own bbox without moving where its cap band
    actually sits. Because that centring is a font-and-em fact, not a
    per-string one, one measurement here lets build_label() place every line's
    CAP BAND at an exact, predictable Y regardless of what the string
    contains, instead of inheriting the small string-dependent bias align_y
    leaves behind.

    A capital I is a plain unserifed bar in both fonts, so its bbox gives the
    cap height, the stem width and the cap band's own Y extent in one
    measurement. That assumption is why this is only trusted for the bundled
    font -- see resolve_font().
    """
    me = _line_mesh("I", font_data, _METRIC_REF_EM, 0.1)
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    cap = ((max(ys) - min(ys)) / _METRIC_REF_EM) if ys else 0.0
    stem = ((max(xs) - min(xs)) / _METRIC_REF_EM) if xs else 0.0
    cap_mid = (((max(ys) + min(ys)) * 0.5) / _METRIC_REF_EM) if ys else 0.0
    bpy.data.meshes.remove(me)
    return cap, stem, cap_mid


# WHY THERE IS NO SYNTHETIC BOLD HERE.
#
# The obvious fix for a font too thin to print is Curve.offset, which fattens
# every glyph outline -- and on the easy fixtures it looks perfect: at 3 mm it
# takes Bfont's 0.294 mm stem to 0.454 mm in a dead-straight line, counters
# stay open ("e" keeps its hole past 0.20 mm of offset) and accents survive.
#
# It is still unusable, and the check that catches it is MANIFOLDNESS, which
# bbox and vertex counts both miss. An outline pushed outwards self-intersects
# wherever the contour turns tightly, and real words turn tightly constantly.
# MEASURED at 3 mm, bad edges after welding:
#
#   string           offset 0.02   0.04   0.06   0.08
#   "I"                       0      0      0      0
#   "Sunlu"                   0      0      0      0
#   "PLA Matte"               0      6      1     98
#   "Marrom Cafe"             0     14      3     99
#
# The glyph solid then fails to boolean at all -- measured: the emboss union
# gives up outright and BooleanError fires. Single letters pass and words do
# not, so any test fixture short enough to be convenient hides this.
#
# Stroke weight therefore has to come from the FONT, not from post-processing
# its outlines. metrics() above is what measures the shipped font's own
# stem-per-cap ratio; the panel reports the resulting stroke and warns when
# it is not enough.


def _fit_size(body: str, font_data, cap: float, extrude: float,
              usable_width: float, field: str, cap_per_em: float,
              stem_per_em: float):
    """Generate a line at `cap` millimetres of cap height, shrinking it to fit
    `usable_width` if it overflows.

    Returns (mesh, final_cap, width, height, stroke). Text scales linearly, so
    the shrink factor comes from one measurement rather than iterating. Raises
    TextOverflowError if fitting would need to go below the printable floor.

    `stroke` is for the size the line ENDS at, not the one it was asked for:
    auto-shrink thins the strokes, so a shrunk line's printability has to be
    judged after the shrink, never before.
    """
    def build(cap_mm):
        em = cap_mm / cap_per_em if cap_per_em > 0.0 else cap_mm
        return _line_mesh(body, font_data, em, extrude), stem_per_em * em

    me, stroke = build(cap)
    (x0, y0, _), (x1, y1, _) = _bounds(me)
    width = x1 - x0

    if width <= usable_width or width <= 1e-6:
        return me, cap, width, (y1 - y0), stroke

    fitted = cap * (usable_width / width)
    if fitted < MIN_FONT_SIZE - 1e-6:
        bpy.data.meshes.remove(me)
        raise TextOverflowError(field, len(body), usable_width)

    bpy.data.meshes.remove(me)
    me, stroke = build(fitted)
    (x0, y0, _), (x1, y1, _) = _bounds(me)
    return me, fitted, (x1 - x0), (y1 - y0), stroke


def build_label(fields: list[tuple[str, str, float]], font_data, extrude: float,
                usable_width: float, line_gap: float, name: str) -> Label:
    """Build the stacked, centred label solid.

    `fields` is the non-empty lines in top-to-bottom order, each a
    (field_name, body, size) triple. The empty ones are dropped by the caller, so
    the remaining lines re-centre vertically here for free.

    Sizes are CAP HEIGHTS in millimetres, not em sizes -- see metrics().

    Lines are STACKED BY CAP HEIGHT, not by their own bbox: two swatches with
    the same three cap sizes but different words must line-space identically,
    which bbox-based stacking cannot promise -- an accented Color line or one
    with a descender (g, j, p, q, y) inflates that one line's bbox and eats
    into line_gap unevenly. MEASURED before this existed, defaults, gap
    nominally 1.0 mm: a plain third line left a 0.926 mm visible gap next to
    the first line's 1.070 mm, an accented one 0.910 mm, and one with a
    descender 1.300 mm -- the same swatch reading unevenly spaced depending on
    what was typed. Anchoring every line by its CAP BAND (via metrics()'
    cap_mid, a font-and-em fact, not a per-string one) keeps the visible gap
    constant and lets accents/descenders spill into the leading exactly the
    way ordinary typesetting expects them to.
    """
    cap_per_em, stem_per_em, cap_mid_per_em = metrics(font_data)

    laid = []
    meshes = []
    for field, body, size in fields:
        me, final, width, height, stroke = _fit_size(
            body, font_data, size, extrude, usable_width, field,
            cap_per_em, stem_per_em)
        meshes.append(me)
        laid.append(Line(field=field, body=body, requested_size=size,
                         final_size=final, width=width, height=height,
                         shrunk=final < size - 1e-6, stroke=stroke))

    # Stack by CAP HEIGHT (what final_size actually is), not by each line's
    # own bbox height -- the whole point of the cap-band anchoring below.
    total = sum(l.final_size for l in laid) + line_gap * (len(laid) - 1)
    cursor = total * 0.5   # top of the first line's cap band, Y=0 centred

    bm = bmesh.new()
    for line, me in zip(laid, meshes):
        # em varies per line (auto-shrink), so the cap band's LOCAL position
        # in this line's own raw mesh has to be recomputed at its own em --
        # cap_mid_per_em is a ratio, constant across sizes, but the millimetre
        # position it maps to is not.
        em = line.final_size / cap_per_em if cap_per_em > 0.0 else line.final_size
        cap_mid_local = cap_mid_per_em * em
        wanted_mid = cursor - line.final_size * 0.5
        me.transform(Matrix.Translation((0.0, wanted_mid - cap_mid_local, 0.0)))
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
        cursor -= (line.final_size + line_gap)

    # Blender's curve-to-mesh evaluation does NOT weld the fill (cap) topology
    # to the extrude (side-wall) topology -- every vertex comes back doubled,
    # coincident but at a different index, which makes every letter read as
    # non-manifold even though nothing is actually open. Measured on a single
    # "o": 384 vertices before welding, 192 (exactly half) after, 0 bad edges
    # either way. Done once here, after all lines are merged, rather than per
    # line -- one pass instead of N.
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=MERGE_DIST)

    return Label(obj=objects.from_bmesh(name, bm), lines=laid)
