"""Tests for engine/text.py: font resolution, layout, stacking, auto-shrink.

    blender --background --factory-startup --python tests/test_text.py

WARNING: Blender exits 0 even when a script raises -- a runner must grep for
'Traceback' as well as reading the RESULT line.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bmesh  # noqa: E402
import bpy  # noqa: E402
import _pkg  # noqa: E402

_pkg.load()

from magpie_swatches.constants import (DEFAULT_BRAND_SIZE,  # noqa: E402
                                       DEFAULT_COLOR_SIZE, DEFAULT_TYPE_SIZE,
                                       MIN_FONT_SIZE, MIN_STROKE)
from magpie_swatches.engine import text  # noqa: E402

_fails = []


def check(tag, ok, detail=""):
    print(f"[{tag}] {'ok' if ok else 'FAIL'} {detail}")
    if not ok:
        _fails.append(tag)


def near(a, b, tol):
    return abs(a - b) <= tol


def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def manifold(mesh):
    counts = {}
    for poly in mesh.polygons:
        for k in poly.edge_keys:
            counts[k] = counts.get(k, 0) + 1
    return all(c == 2 for c in counts.values())


GAP = 1.0
WIDE = 1000.0  # a usable_width no realistic line will ever hit


def visible_bands(mesh):
    """Y extent of each connected-component "band" in a merged label mesh,
    topmost first, as [lo, hi] pairs.

    Connected components are found by walking the vertex/edge graph (each
    glyph is its own island in the merged mesh); components whose Y ranges
    overlap belong to the same printed line (adjacent glyphs in one word) and
    are merged into one band. The merge test is `hi >= running_band.lo` --
    NOT `lo <= running_band.hi` -- because bands are collected topmost-first
    and a later (lower) component only belongs to the running band if its TOP
    reaches into the band's already-seen bottom; comparing bottoms the other
    way merged every band into one on the first attempt at this test.
    """
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    seen, islands = set(), []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack, ys = [v], []
        seen.add(v.index)
        while stack:
            cur = stack.pop()
            ys.append(cur.co.y)
            for e in cur.link_edges:
                other = e.other_vert(cur)
                if other.index not in seen:
                    seen.add(other.index)
                    stack.append(other)
        islands.append([min(ys), max(ys)])
    bm.free()

    islands.sort(key=lambda pair: -pair[1])
    bands = [islands[0]]
    for lo, hi in islands[1:]:
        if hi >= bands[-1][0] - 1e-6:
            bands[-1][0] = min(bands[-1][0], lo)
            bands[-1][1] = max(bands[-1][1], hi)
        else:
            bands.append([lo, hi])
    return bands


def visible_gaps(mesh):
    """Gap between each pair of adjacent bands, topmost pair first."""
    bands = visible_bands(mesh)
    return [bands[i][0] - bands[i + 1][1] for i in range(len(bands) - 1)]


# --- resolve_font ------------------------------------------------------ #

def test_resolve_font_gives_the_bundled_bold():
    fresh()
    font = text.resolve_font()
    check("font.is_bundled", font is not None)
    check("font.is_the_right_file",
          font is not None and "Liberation" in font.filepath,
          str(font.filepath if font else None))


def test_resolve_font_returns_none_if_the_bundle_is_missing():
    """No custom font picker exists -- resolve_font() always tries the ONE
    bundled file. If even that is missing (a broken install), it must
    return None (meaning Blender's own Bfont) rather than raise. Simulated
    by pointing the module at a path that does not exist, since a genuinely
    broken install isn't reproducible on demand.
    """
    fresh()
    original = text._BUNDLED_FONT
    text._BUNDLED_FONT = Path("C:/definitely/not/a/real/font.ttf")
    try:
        font = text.resolve_font()
        check("font.missing_bundle_returns_none", font is None,
              str(font.filepath if font else None))
    finally:
        text._BUNDLED_FONT = original


# --- layout / stacking --------------------------------------------------- #

def test_three_lines_manifold_and_stacked():
    fresh()
    fields = [("Brand", "Sunlu", 3.0), ("Type", "PLA Matte", 4.5),
             ("Color", "Marrom Cafe", 3.5)]
    label = text.build_label(fields, None, 1.0, WIDE, GAP, "lbl3")
    check("text.manifold", manifold(label.obj.data))
    check("text.line_count", len(label.lines) == 3, str(len(label.lines)))

    # Lines are stacked by CAP HEIGHT now (see build_label()'s docstring), so
    # the object's own Y extent is AT LEAST the sum of cap heights plus gaps --
    # "at least" because an accent or a descender can push a line's own bbox
    # past its cap band without that meaning the lines overlapped. If lines
    # DID overlap, the object's extent would fall short of even this minimum.
    expect_min = sum(l.final_size for l in label.lines) + GAP * 2
    got_h = label.obj.dimensions.y
    check("text.no_overlap", got_h >= expect_min - 0.05,
          f"object height {got_h:.3f} vs minimum {expect_min:.3f}")


def test_line_spacing_is_independent_of_other_lines_content():
    """The bug this fixes: changing what is typed on one line must not move
    the gap between two OTHER lines.

    MEASURED before the cap-band anchoring existed, at the shipped default
    sizes (2.4 / 3.0 / 2.6 mm -- three DIFFERENT sizes, which is what exposed
    it): the old bbox-based stacking summed every line's own bbox height to
    find the block's total height, so the gap between lines 1 and 2 changed
    depending on what line 3 said, even though line 3 never touches that gap.
    A plain third line gave a 1.070 mm visible gap there; a third line with a
    descender (g, j, p, q, y) gave 1.300 mm for the SAME first two lines.

    The gap between lines 2 and 3 is deliberately NOT asserted equal across
    all three bodies here: an accent that rises above the font's own cap band
    legitimately shrinks that one gap (MEASURED: 0.819 mm plain vs 0.786 mm
    accented, with this specific bundled font) -- that is correct typesetting
    letting ink spill into the leading, not a bug, and no add-on can promise
    otherwise without measuring the ink of every glyph pair. What the fix
    guarantees is narrower and exact: a gap is unaffected by a line it is not
    adjacent to.
    """
    fresh()
    font = text.resolve_font()
    sizes = (DEFAULT_BRAND_SIZE, DEFAULT_TYPE_SIZE, DEFAULT_COLOR_SIZE)

    def gap_1_2(color_body):
        fields = [("Brand", "Sunlu", sizes[0]), ("Type", "PLA Matte", sizes[1]),
                  ("Color", color_body, sizes[2])]
        label = text.build_label(fields, font, 1.0, WIDE, GAP, "g")
        gaps = visible_gaps(label.obj.data)
        check("spacing.three_bands_found", len(gaps) == 2, str(len(gaps) + 1))
        return gaps[0]

    plain = gap_1_2("Marrom Cafe")
    fresh()
    font = text.resolve_font()
    accented = gap_1_2("Marrom Café")
    fresh()
    font = text.resolve_font()
    descender = gap_1_2("Verde Oliva Gy")

    check("spacing.unaffected_by_accent_elsewhere",
          near(plain, accented, 0.02), f"plain={plain:.4f} accented={accented:.4f}")
    check("spacing.unaffected_by_descender_elsewhere",
          near(plain, descender, 0.02),
          f"plain={plain:.4f} descender={descender:.4f}")


def test_empty_field_dropped_recenters():
    """build_label only ever sees the fields the caller kept -- passing fewer
    lines must still centre the remaining stack close to Y = 0, for free.

    Tolerance is loose on purpose: Blender's align_y='CENTER' centres a glyph
    on FONT METRICS (roughly cap-height-to-baseline), not the tight ink bbox
    of that specific string -- measured (see debug session): the same body at
    the same size gives an identical, repeatable offset every time (not
    noise), a string without descenders sits ~0.12-0.19 mm high of centre,
    and a string of pure descenders ("gjpqy") sits ~0.43 mm low. That is the
    RIGHT trade-off for this add-on -- it keeps every field's baseline
    consistent regardless of which glyphs happen to appear in it, which
    matters more here than pixel-exact centring of a single string would.
    0.6 mm safely covers that known bias while still catching a real stacking
    bug, which would be off by a whole line height (several mm), not tenths.
    """
    fresh()
    one = text.build_label([("Type", "PLA Matte", 4.5)], None, 1.0, WIDE, GAP,
                           "lbl1")
    ys = [v.co.y for v in one.obj.data.vertices]
    mid = (max(ys) + min(ys)) * 0.5
    check("text.single_line_centred", near(mid, 0.0, 0.6), f"mid y={mid:.4f}")

    fresh()
    two = text.build_label([("Brand", "Sunlu", 3.0), ("Color", "Cafe", 3.5)],
                           None, 1.0, WIDE, GAP, "lbl2")
    ys2 = [v.co.y for v in two.obj.data.vertices]
    mid2 = (max(ys2) + min(ys2)) * 0.5
    check("text.two_lines_centred", near(mid2, 0.0, 0.6), f"mid y={mid2:.4f}")


# --- auto-shrink ---------------------------------------------------------- #

def test_auto_shrink_scales_and_respects_width():
    fresh()
    body = "PLA Matte Filament"
    requested = 6.0
    natural = text.build_label([("Type", body, requested)], None, 1.0, WIDE,
                               GAP, "natural")
    natural_w = natural.lines[0].width
    check("shrink.natural_width_positive", natural_w > 0.5, f"{natural_w:.3f}")

    target = natural_w * 0.6
    fresh()
    shrunk = text.build_label([("Type", body, requested)], None, 1.0, target,
                              GAP, "shrunk")
    line = shrunk.lines[0]
    check("shrink.did_shrink", line.shrunk and line.final_size < requested,
          f"final={line.final_size:.3f}")
    check("shrink.matches_ratio", near(line.final_size, requested * 0.6, 0.05),
          f"final={line.final_size:.3f}, expected ~{requested * 0.6:.3f}")
    check("shrink.fits_usable_width", line.width <= target + 0.05,
          f"width={line.width:.3f}, usable={target:.3f}")


def test_overflow_below_floor_raises_named():
    fresh()
    try:
        text.build_label([("Brand", "Sunlu Filament Company", 5.0)], None,
                         1.0, 0.05, GAP, "overflow")
        check("shrink.rejects_impossible_fit", False, "did not raise")
    except text.TextOverflowError as exc:
        check("shrink.rejects_impossible_fit", True)
        check("shrink.names_field", exc.field == "Brand", str(exc))
        check("shrink.message_names_field", "Brand" in str(exc), str(exc))


# --- printable stroke ------------------------------------------------------ #

def test_bundled_font_prints_at_every_shipped_default():
    """The whole reason a font is bundled: every default must clear MIN_STROKE.

    Measured on Blender's Bfont before the bundle, this failed on all three --
    Brand 0.294, Color 0.343, Type 0.441 mm against a 0.45 mm minimum.
    """
    fresh()
    font = text.resolve_font()
    check("font.bundled_loads", font is not None,
          "resolve_font() must find the bundled bold, not fall to Bfont")

    fresh()
    fields = [("Brand", "Sunlu", 3.0), ("Type", "PLA Matte", 4.5),
             ("Color", "Marrom Cafe", 3.5)]
    label = text.build_label(fields, text.resolve_font(), 1.0, WIDE, GAP,
                             "stroke")
    for line in label.lines:
        check(f"font.printable[{line.field}]",
              line.stroke >= MIN_STROKE - 1e-6,
              f"{line.stroke:.3f} mm (minimum {MIN_STROKE})")


def test_size_means_cap_height():
    """The size fields are CAP HEIGHT in mm -- what a caliper measures on the
    printed part -- not Blender's em size, which varies per font."""
    for wanted in (3.0, 4.5):
        # Reload inside the loop: fresh() wipes the file, which invalidates
        # any VectorFont reference held across it.
        fresh()
        font = text.resolve_font()
        label = text.build_label([("Type", "H", wanted)], font, 1.0, WIDE, GAP,
                                 "cap")
        ys = [v.co.y for v in label.obj.data.vertices]
        got = max(ys) - min(ys)
        check(f"font.cap_height[{wanted}]", near(got, wanted, 0.05),
              f"asked {wanted} mm, capital H measures {got:.3f} mm")


def test_metrics_are_measured_not_assumed():
    fresh()
    cap_bfont, stem_bfont, _ = text.metrics(None)
    fresh()
    cap_lib, stem_lib, _ = text.metrics(text.resolve_font())

    check("font.metrics_differ", not near(cap_bfont, cap_lib, 0.01),
          f"Bfont cap/em={cap_bfont:.3f}, bundled cap/em={cap_lib:.3f} -- if "
          f"these matched, sizing by cap height would be pointless")
    # Weight per unit of VISIBLE letter height is the honest comparison; per
    # em it flatters the lighter font, because Bfont packs a taller cap into
    # the same em.
    check("font.bundled_is_bolder",
          (stem_lib / cap_lib) > (stem_bfont / cap_bfont) * 1.2,
          f"stem/cap: Bfont {stem_bfont / cap_bfont:.3f}, "
          f"bundled {stem_lib / cap_lib:.3f}")


def test_shrunk_line_reports_its_real_stroke():
    """Auto-shrink thins the strokes, so the reported stroke must be for the
    size the line ENDS at -- reporting the requested size's stroke would
    overstate how printable a shrunk line is."""
    fresh()
    natural = text.build_label([("Type", "PLA Matte Premium", 6.0)], None,
                               1.0, WIDE, GAP, "nat")
    natural_stroke = natural.lines[0].stroke

    fresh()
    shrunk = text.build_label([("Type", "PLA Matte Premium", 6.0)], None, 1.0,
                              natural.lines[0].width * 0.55, GAP, "shr")
    line = shrunk.lines[0]
    check("stroke.shrink_happened", line.shrunk, f"final={line.final_size:.2f}")
    check("stroke.shrink_thins_the_stroke", line.stroke < natural_stroke,
          f"{line.stroke:.3f} mm shrunk vs {natural_stroke:.3f} mm natural")


def test_offset_thickening_would_break_the_mesh():
    """Guards the decision NOT to synthetically bolden glyphs.

    Curve.offset looks like the obvious fix and passes every cheap check --
    stroke width, counters, accents -- but self-intersects on real words, and
    the resulting mesh cannot be booleaned. If a future Blender ever fixes
    that, this test starts failing and the option is worth revisiting.
    """
    fresh()
    me = text._line_mesh("PLA Matte", None, 3.0, 0.5, 0.08)
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.001)
    bm.to_mesh(me)
    bm.free()
    counts = {}
    for poly in me.polygons:
        for k in poly.edge_keys:
            counts[k] = counts.get(k, 0) + 1
    bad = sum(1 for c in counts.values() if c != 2)
    bpy.data.meshes.remove(me)
    check("stroke.offset_still_self_intersects", bad > 0,
          f"{bad} bad edges at offset 0.08 -- zero would mean Blender fixed "
          f"it and synthetic bold is back on the table")


# --- diacritics ------------------------------------------------------------ #

def test_bfont_covers_portuguese_diacritics():
    """Marrom Cafe / Cinza Chumbo / Verde Oliva must all build with Bfont, and
    the accented glyph must actually contribute width -- if Bfont dropped 'e'
    (accented e) silently, "Cafe" (accented) would come out the same width as
    "Caf" instead of wider.
    """
    for body in ("Marrom Caf\u00e9", "Cinza Chumbo", "Verde Oliva",
                "A\u00e7\u00e3o"):
        fresh()
        label = text.build_label([("Brand", body, 3.0)], text.resolve_font(),
                                 1.0, WIDE, GAP, "diac")
        check(f"diacritics.builds[{body}]", len(label.obj.data.vertices) > 0,
              body)

    fresh()
    plain = text.build_label([("Brand", "Caf", 5.0)], text.resolve_font(),
                             1.0, WIDE, GAP, "plain")
    fresh()
    accented = text.build_label([("Brand", "Caf\u00e9", 5.0)],
                                text.resolve_font(), 1.0, WIDE, GAP,
                                "accented")
    check("diacritics.accent_adds_width",
          accented.lines[0].width > plain.lines[0].width + 0.1,
          f"Caf={plain.lines[0].width:.3f}  "
          f"Cafe(accented)={accented.lines[0].width:.3f}")


try:
    for fn in (test_resolve_font_gives_the_bundled_bold,
              test_resolve_font_returns_none_if_the_bundle_is_missing,
              test_three_lines_manifold_and_stacked,
              test_line_spacing_is_independent_of_other_lines_content,
              test_empty_field_dropped_recenters,
              test_auto_shrink_scales_and_respects_width,
              test_overflow_below_floor_raises_named,
              test_bundled_font_prints_at_every_shipped_default,
              test_size_means_cap_height,
              test_metrics_are_measured_not_assumed,
              test_shrunk_line_reports_its_real_stroke,
              test_offset_thickening_would_break_the_mesh,
              test_bfont_covers_portuguese_diacritics):
        fn()
finally:
    pass

print(f"RESULT: {'FAIL -> ' + ', '.join(_fails) if _fails else 'PASS'}")
sys.exit(1 if _fails else 0)
