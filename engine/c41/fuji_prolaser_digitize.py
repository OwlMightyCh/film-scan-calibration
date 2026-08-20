#!/usr/bin/env python3
"""Digitize the vector charts of the Fujicolor Pro Laser Type II paper datasheet.

Independent re-trace. Everything below is extracted from the PDF itself
(paper_datasheet/'Fujicolor Professional Paper Pro Laser Type II.pdf'); no
prior digitization of this paper was consulted.

All three charts live on PAGE index 3 (the printed "page 4"), 595.22x842 pt:

  * chart 13  特性曲線  "Characteristic (H&D) curves",  left,
        frame (82.8, 305.5)-(288.0, 487.2). y = reflection density D
        (Status A equivalent), x = log H. The x axis carries NO absolute
        numeral -- only a double-arrow spanning one gridline interval labelled
        "0.5", i.e. a gridline SPACING. The x axis is therefore RELATIVE with
        an ARBITRARY origin (see audit).
  * chart 14  分光感度曲線 "Spectral sensitivity", right,
        frame (333.6, 305.2)-(536.9, 489.7). x = wavelength nm (absolute
        numerals 400/500/600/700), y = relative log sensitivity -- again a
        spacing-labelled double arrow, so RELATIVE with an ARBITRARY origin.
  * chart 15  色素の分光濃度曲線 "Spectral dye density", bottom left,
        frame (89.0, 86.8)-(277.9, 221.1). x = wavelength nm, y = spectral
        REFLECTION density (absolute numerals on both axes).

Structure, pdfminer helpers, axis-calibration approach and output schema mirror
engine/c41/endura_digitize.py, so the emitted JSON is a drop-in sibling of
data/papers/EnduraPremier_paper.json for the print engine.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTChar, LTCurve, LTLine, LTRect

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.c41.portra_digitize import (  # noqa: E402
    walk, affine_fit, to_data, resample_curve, bezier, cluster,
)

DATA = ROOT / "data"
PDF = ROOT / "paper_datasheet" / "Fujicolor Professional Paper Pro Laser Type II.pdf"
PAGE = 3

# device-space plot frames, located from the printed axis numerals
HD_FRAME = (82.8, 305.5, 288.0, 487.2)
SENS_FRAME = (333.6, 305.2, 536.9, 489.7)
DYE_FRAME = (89.0, 86.8, 277.9, 221.1)


# ---------- geometry helpers ----------
def polyline_dense(curve, n=32):
    """Flatten an LTCurve path to a dense device-space polyline.

    Same contract as portra_digitize.polyline but with a caller-controlled
    bezier subdivision count (requirement: sample curve geometry densely).
    """
    pts = []
    cur = None
    for seg in curve.original_path:
        op, coords = seg[0], seg[1:]
        if op in ("m", "l"):
            cur = np.array(coords[0], float)
            pts.append(cur)
        elif op in ("c", "v", "y"):
            c = [np.array(p, float) for p in coords]
            if op == "c":
                p1, p2, p3 = c
            elif op == "v":
                p1, p2, p3 = cur, c[0], c[1]
            else:  # 'y'
                p1, p2, p3 = c[0], c[1], c[1]
            for q in bezier(cur, p1, p2, p3, n=n)[1:]:
                pts.append(q)
            cur = p3
    return np.array(pts)


def rgb(color):
    """Normalize a pdfminer colour (float gray | 3-tuple | None) to an RGB tuple."""
    if color is None:
        return None
    if isinstance(color, (int, float)):
        return (float(color),) * 3
    if len(color) == 1:
        return (float(color[0]),) * 3
    if len(color) == 3:
        return tuple(float(v) for v in color)
    if len(color) == 4:  # CMYK
        c, m, y, k = [float(v) for v in color]
        return (1 - min(1, c + k), 1 - min(1, m + k), 1 - min(1, y + k))
    return None


def is_chromatic(color, thresh=0.15):
    """True for a saturated (data-curve) stroke colour.

    The chart frames, gridlines and tick marks are all drawn in near-neutral
    ink -- pure black (0,0,0) or the datasheet's registration grey
    (0.137,0.121,0.125) / (0.133,0.121,0.125). Every data curve is drawn in a
    saturated hue. max(rgb)-min(rgb) separates the two populations cleanly and
    is the secondary defence against the toe/axis merge trap.
    """
    c = rgb(color)
    if c is None:
        return False
    return (max(c) - min(c)) > thresh


def inside(bbox, frame, pad=1.0):
    x0, y0, x1, y1 = bbox
    fx0, fy0, fx1, fy1 = frame
    return (x0 >= fx0 - pad and x1 <= fx1 + pad
            and y0 >= fy0 - pad and y1 <= fy1 + pad)


def overlaps(bbox, frame, pad=12.0):
    x0, y0, x1, y1 = bbox
    fx0, fy0, fx1, fy1 = frame
    return not (x1 < fx0 - pad or x0 > fx1 + pad
                or y1 < fy0 - pad or y0 > fy1 + pad)


def select_data_curves(els, frame, min_segments=4):
    """Split every path element near `frame` into kept data curves vs discards.

    Rejection order (each reason counted separately for the audit):
      axis_geometry  -- LTLine / LTRect: frame rectangle, gridlines, tick
                        marks, the spacing-arrow rule and the legend swatches.
                        Excluded WHOLESALE, never colour-tested; this is what
                        keeps an axis line from being welded onto a curve toe.
      not_stroked    -- fill-only art: arrowheads, legend glyph outlines,
                        the page-furniture layer diagram and its 25 rasters.
      achromatic     -- stroked path drawn in near-neutral ink (rules emitted
                        as generic curves rather than LTLine).
      outside_frame  -- bbox not contained by the plot frame.
      too_few_segs   -- stroked chromatic path with < min_segments segments
                        (arrowhead strokes, marker ticks).
    """
    kept, reasons = [], {}

    def bump(k):
        reasons[k] = reasons.get(k, 0) + 1

    near = [e for e in els if isinstance(e, LTCurve) and overlaps(e.bbox, frame)]
    for e in near:
        if isinstance(e, (LTLine, LTRect)):
            bump("axis_geometry")
            continue
        if not e.stroke:
            bump("not_stroked")
            continue
        if not is_chromatic(e.stroking_color):
            bump("achromatic")
            continue
        if not inside(e.bbox, frame):
            bump("outside_frame")
            continue
        if len(e.original_path) < min_segments:
            bump("too_few_segs")
            continue
        kept.append(e)
    return kept, len(near), reasons


def numeral_ticks(chars, xlo, xhi, ylo, yhi, axis, gap):
    """[(device_position, value)] from the PRINTED axis numerals.

    Glyphs whose *centre* falls in the window are grouped along the label axis;
    a group's position is the mean of its glyph CENTRES (not x0 -- using x0
    biases a 3-glyph label like "400" ~2.3 pt left of the gridline it marks).
    """
    key = (lambda c: (c.x0 + c.x1) / 2) if axis == "x" else (lambda c: (c.y0 + c.y1) / 2)
    sel = [c for c in chars
           if xlo <= (c.x0 + c.x1) / 2 <= xhi and ylo <= (c.y0 + c.y1) / 2 <= yhi
           and re.match(r"[0-9.\-]", c.get_text())]
    if not sel:
        return []
    groups = cluster([key(c) for c in sel], gap)
    out = []
    for g in groups:
        members = [c for c in sel if g[0] - 1e-6 <= key(c) <= g[-1] + 1e-6]
        members.sort(key=lambda c: c.x0)
        m = re.search(r"-?\d+\.?\d*", "".join(c.get_text() for c in members))
        if not m:
            continue
        out.append((float(np.mean([key(c) for c in members])), float(m.group())))
    out.sort()
    return out


def gridlines(els, frame, orient, pad=1.0):
    """Ruled gridline positions of a plot frame, and its two frame edges.

    orient='v' -> vertical rules, returns x positions; 'h' -> y positions.
    Only near-neutral LTLine/LTRect geometry spanning the full frame qualifies,
    so a data curve can never masquerade as a gridline. Returns
    (rules, edges) SEPARATELY: a frame edge is not necessarily a gridline --
    on chart 14 the top edge sits only 12 pt above the highest rule, and on
    chart 15 the top edge is likewise off-lattice. Callers must therefore
    lattice-test the edges before giving them a value.
    """
    fx0, fy0, fx1, fy1 = frame
    pos = []
    for e in els:
        if not isinstance(e, (LTLine, LTRect)):
            continue
        x0, y0, x1, y1 = e.bbox
        if is_chromatic(e.stroking_color):
            continue          # coloured legend swatches
        if orient == "v":
            if abs(x1 - x0) < 0.6 and y0 <= fy0 + 3 and y1 >= fy1 - 3:
                pos.append((x0 + x1) / 2)
        else:
            if abs(y1 - y0) < 0.6 and x0 <= fx0 + 3 and x1 >= fx1 - 3:
                pos.append((y0 + y1) / 2)
    lo, hi = (fx0, fx1) if orient == "v" else (fy0, fy1)
    pos = [p for p in pos if lo + pad < p < hi - pad]
    rules = [float(np.mean(g)) for g in cluster(pos, 3.0)] if pos else []
    return rules, [float(lo), float(hi)]


def lattice_ticks(rules, edges, ref, step, tol=3.0):
    """Anchor list for a RELATIVE axis calibrated from a gridline spacing.

    `rules` fixes the lattice pitch (median rule-to-rule gap). Value 0 is
    DEFINED at `ref`, and each rule/edge gets round((p-ref)/pitch)*step --
    but only if it actually lands on the lattice to within `tol` device pt,
    which is what keeps an off-lattice frame edge from being handed a bogus
    value. Returns (anchors, pitch, rejected_positions).
    """
    rs = sorted(rules)
    pitch = float(np.median(np.diff(rs)))
    anchors, rejected = [], []
    for p in sorted(set([round(v, 4) for v in rs + edges])):
        k = (p - ref) / pitch
        if abs(k - round(k)) * pitch <= tol:
            anchors.append((round(float(p), 3), round(float(round(k) * step), 4)))
        else:
            rejected.append(round(float(p), 3))
    return anchors, pitch, rejected


def snapped_ticks(positions, m, b, quantum, tol):
    """Gridline anchors for an ABSOLUTE axis already calibrated by numerals.

    Each position is mapped through the numeral fit and snapped to the nearest
    multiple of `quantum`; positions further than `tol` (data units) from a
    multiple are off-lattice and dropped. Used only for the independent
    gridline cross-check, never for the primary fit.
    """
    anchors, rejected = [], []
    for p in sorted(positions):
        v = m * p + b
        q = round(v / quantum) * quantum
        if abs(v - q) <= tol:
            anchors.append((round(float(p), 3), round(float(q), 4)))
        else:
            rejected.append(round(float(p), 3))
    return anchors, rejected


def spacing_arrow_span(els, frame, orient, band):
    """Device span of the double-headed 'gridline spacing' annotation.

    `band` is the cross-axis window the annotation sits in. Both the shaft
    (an LTLine) and the two solid arrowheads (small filled LTCurves) are
    collected; the union of their extents along `orient` is the labelled span.
    """
    lo, hi = band
    ext = []
    for e in els:
        if not isinstance(e, LTCurve):
            continue
        x0, y0, x1, y1 = e.bbox
        if orient == "v":       # vertical arrow: spans in y, lives at x in band
            if lo <= (x0 + x1) / 2 <= hi and (y1 - y0) < 0.6 * (frame[3] - frame[1]):
                ext += [y0, y1]
        else:                   # horizontal arrow: spans in x, lives at y in band
            if lo <= (y0 + y1) / 2 <= hi:
                ext += [x0, x1]
    if not ext:
        return None
    return (float(min(ext)), float(max(ext)))


def peak_wavelength(wl_grid, vals):
    arr = np.array(vals, float)
    return float(wl_grid[int(np.nanargmax(arr))])


def layer_from_peak(peak, i):
    if 380 <= peak < 500:
        return "yellow"     # blue-sensitive -> yellow-forming
    if 500 <= peak < 600:
        return "magenta"    # green-sensitive -> magenta-forming
    if 600 <= peak <= 760:
        return "cyan"       # red-sensitive -> cyan-forming
    return "unknown_%d" % i


def dominant_hue(color):
    """'R'/'G'/'B' from a saturated stroke colour (H&D curve identification)."""
    return "RGB"[int(np.argmax(rgb(color)))]


# =====================================================================
def main():
    page = list(extract_pages(str(PDF)))[PAGE]
    els = list(walk(page))
    chars = [e for e in els if isinstance(e, LTChar)]
    audit = {}

    # =================================================================
    # the 0.1 vs 1.0 question -- chart 14's only y numeral
    # =================================================================
    # The glyphs are set with text matrix (0, 7.1236, -7.1234, 0, ...): a
    # +90 deg rotation, so the text advance vector (1,0) maps to device
    # (0, +7.12) -- reading order runs UP the page. Sorting the three glyphs
    # by ascending device y therefore yields the reading order.
    stack = sorted([c for c in chars
                    if 320 < (c.x0 + c.x1) / 2 < 333
                    and 380 < (c.y0 + c.y1) / 2 < 400],
                   key=lambda c: c.y0)
    stack_text = "".join(c.get_text() for c in stack)
    stack_matrix = [round(v, 4) for v in stack[0].matrix[:4]] if stack else None
    stack_detail = [{"glyph": c.get_text(), "y0": round(c.y0, 3),
                     "y1": round(c.y1, 3)} for c in stack]

    # =================================================================
    # CHART 13 -- characteristic (H&D) curves
    # =================================================================
    hd_ynum = numeral_ticks(chars, 66, 82.5, 300, 492, axis="y", gap=8.0)
    hmy, hby, hyr = affine_fit(hd_ynum)          # D = hmy*y_px + hby

    hd_vrules, hd_vedges = gridlines(els, HD_FRAME, "v")
    hd_hrules, hd_hedges = gridlines(els, HD_FRAME, "h")
    # independent cross-check: the horizontal gridlines carry the same values
    hd_grid_ticks, hd_grid_rej = snapped_ticks(hd_hrules + hd_hedges,
                                               hmy, hby, 0.5, 0.06)
    hd_grid_fit = affine_fit(hd_grid_ticks)
    hd_grid_disagree = max(abs((hmy * y + hby) - (hd_grid_fit[0] * y + hd_grid_fit[1]))
                           for y in (HD_FRAME[1], HD_FRAME[3]))
    # PRIMARY = the gridlines, NOT the glyph centres. The printed numerals still
    # assign the VALUES (snapped_ticks above labels each gridline through the
    # numeral fit), but a numeral's glyph-centre is only an approximation of the
    # tick it names: text boxes carry 1-2 pt of centring error, and the '0.0' is
    # visibly nudged off the axis rule. That is a ~0.02 D SYSTEMATIC offset on
    # this axis, which is what an independent digitisation of this datasheet
    # caught. The gridlines are the geometry the curves were actually drawn
    # against, and they fit an order of magnitude tighter. Numerals for values,
    # gridlines for positions.
    hd_num_fit = (hmy, hby, hyr)
    hmy, hby, hyr = hd_grid_fit

    # x axis: only "0.5" is printed, and it labels the span of the double
    # arrow drawn just under the frame -> a gridline SPACING, not a coordinate.
    hd_arrow = spacing_arrow_span(els, HD_FRAME, "h", (297.5, 304.5))
    hd_xlabel = numeral_ticks(chars, 190, 216, 296, 306, axis="x", gap=20.0)
    hd_vall = sorted(hd_vrules + hd_vedges)
    hd_a0 = min(hd_vall, key=lambda x: abs(x - hd_arrow[0]))
    hd_a1 = min(hd_vall, key=lambda x: abs(x - hd_arrow[1]))
    step = hd_xlabel[0][1] if hd_xlabel else 0.5     # 0.5 decade per interval
    # ORIGIN IS ARBITRARY: logH := 0 at the arrow's left-hand gridline.
    HD_X, hd_pitch, hd_xrej = lattice_ticks(hd_vrules, hd_vedges, hd_a0, step)
    hmx, hbx, hxr = affine_fit(HD_X)             # logH_rel = hmx*x_px + hbx

    hd_curves, hd_near, hd_reasons = select_data_curves(els, HD_FRAME)
    # H&D curves carry no spectrum; identity comes from the stroke hue, which
    # matches the coloured legend rules inside the plot (R/G/B exposures).
    hd_by_hue = {}
    for c in hd_curves:
        hd_by_hue.setdefault(dominant_hue(c.stroking_color), []).append(c)
    hd_names = ["R", "G", "B"]
    # Exactly one path per hue, asserted rather than assumed: taking [0] of a
    # bucket that collected two paths would silently digitize one of them and
    # discard the other, and a missing bucket would raise a bare KeyError with
    # nothing said about what was actually found.
    if sorted(hd_by_hue) != sorted(hd_names) or \
            any(len(v) != 1 for v in hd_by_hue.values()):
        raise SystemExit(
            "H&D chart: expected exactly one curve per hue bucket R/G/B, found "
            + ", ".join("%s=%d" % (k, len(hd_by_hue[k])) for k in sorted(hd_by_hue)))

    hd_dev = {n: to_data(polyline_dense(hd_by_hue[n][0]), hmx, hbx, hmy, hby)
              for n in hd_names}

    ranges = [(np.sort(hd_dev[n][:, 0])[0], np.sort(hd_dev[n][:, 0])[-1])
              for n in hd_names]
    lo = max(r[0] for r in ranges)
    hi = min(r[1] for r in ranges)
    logE = np.round(np.arange(np.ceil(lo / 0.02) * 0.02,
                              np.floor(hi / 0.02) * 0.02 + 1e-9, 0.02), 2)

    hd_curve_data, hd_endpoints = {}, {}
    for n in hd_names:
        vals, rng = resample_curve(hd_dev[n], logE, extrapolate=False)
        gx = [round(float(v), 4) for v in logE]
        gy = [round(float(v), 4) for v in vals]
        hd_curve_data[n] = (gx, gy)
        hd_endpoints[n] = {
            "stroke_rgb": [round(v, 4) for v in rgb(hd_by_hue[n][0].stroking_color)],
            "logH_rel_range": [round(rng[0], 4), round(rng[1], 4)],
            "n_path_points": int(len(hd_dev[n])),
            "n_path_segments": int(len(hd_by_hue[n][0].original_path)),
            "n_samples": len(gx),
            "density_range": [round(float(np.nanmin(vals)), 4),
                              round(float(np.nanmax(vals)), 4)],
            "Dmin": round(float(np.nanmin(vals)), 4),
            "Dmax": round(float(np.nanmax(vals)), 4),
        }

    audit["characteristic_curves"] = {
        "chart": "13  特性曲線 (characteristic curves)",
        "page_index": PAGE,
        "frame_device_bbox": list(HD_FRAME),
        "x_axis": {
            "device_to_data": "logH_relative = %.6f*x_px + %.6f" % (hmx, hbx),
            "anchors": HD_X,
            "fit_rms_data": round(hxr, 5),
            "ORIGIN_IS_ARBITRARY": True,
            "axis_is_relative": True,
            "origin_note": (
                "The datasheet prints NO absolute log-H coordinate. Its only x "
                "numeral, '%s' at device x=%.1f, labels a double-headed arrow "
                "spanning device x %.1f..%.1f, which snaps to the vertical "
                "gridlines at x=%.2f and x=%.2f -- i.e. it states the gridline "
                "SPACING of %.2f decade, not a position. The scale is therefore "
                "calibrated from that spacing propagated across all %d vertical "
                "gridlines, and logH=0 is DEFINED at x=%.2f purely by "
                "convention. Only DIFFERENCES in logH are meaningful; the "
                "absolute offset is unknown."
                % (hd_xlabel[0][1] if hd_xlabel else "0.5",
                   hd_xlabel[0][0] if hd_xlabel else float("nan"),
                   hd_arrow[0], hd_arrow[1], hd_a0, hd_a1, step,
                   len(HD_X), hd_a0)),
            "gridline_pitch_px": round(hd_pitch, 4),
            "off_lattice_positions_rejected": hd_xrej,
        },
        "y_axis": {
            "device_to_data": "density = %.6f*y_px + %.6f" % (hmy, hby),
            "anchors": [(round(p, 3), v) for p, v in hd_grid_ticks],
            "anchor_source": ("horizontal gridlines, each labelled 0.0..4.0 by "
                              "the printed numerals -- numerals for values, "
                              "gridlines for positions"),
            "fit_rms_data": round(hyr, 5),
            "off_lattice_positions_rejected": hd_grid_rej,
            "numeral_crosscheck": {
                "device_to_data": "density = %.6f*y_px + %.6f" % (hd_num_fit[0],
                                                                  hd_num_fit[1]),
                "anchors": [(round(p, 3), v) for p, v in hd_ynum],
                "n_numerals": len(hd_ynum),
                "fit_rms_data": round(hd_num_fit[2], 5),
                "max_disagreement_D_over_frame": round(float(hd_grid_disagree), 4),
                "note": ("glyph centres are the CROSS-CHECK, not the "
                         "calibration. They fit ~8x looser than the gridlines "
                         "and sit systematically off by ~0.02 D -- the '0.0' "
                         "numeral is nudged a couple of points up off the axis "
                         "rule. Anchoring on them biases every density."),
            },
        },
        "curve_identification": (
            "by saturated stroke hue (dominant RGB channel), cross-checked "
            "against the coloured legend rules inside the plot. H&D curves "
            "carry no spectrum, so peak-wavelength assignment is not applicable "
            "here; the R/G/B exposure curves are mapped to dye layers via the "
            "spectral evidence of chart 14 -- see layer_mapping."),
        "paths_near_frame": hd_near,
        "paths_kept": len(hd_curves),
        "paths_discarded": hd_near - len(hd_curves),
        "discard_reasons": hd_reasons,
        "toe_axis_exclusion": (
            "The frame rectangle, every vertical and horizontal gridline, the "
            "tick rules, the spacing-arrow shaft and the legend swatches are all "
            "LTLine/LTRect and are discarded WHOLESALE before any curve is "
            "considered, so no axis or tick segment can be concatenated onto a "
            "curve toe. Surviving candidates must additionally be stroked in a "
            "saturated hue (max(rgb)-min(rgb) > 0.15); every rule on this page "
            "is near-neutral ink -- (0,0,0) or (0.133,0.121,0.125) -- and is "
            "rejected. D-min is therefore read from curve geometry only, never "
            "from the frame floor."),
        "densitometry": "Status A equivalent (ステータスA相当)",
        "exposure": "laser (レーザー露光)",
        "process": "CP-48S",
        "caveat": ("※ディープマットは上記特性曲線とは異なります -- the Deep Matte "
                   "surface does NOT follow these characteristic curves."),
    }

    # =================================================================
    # CHART 14 -- spectral sensitivity
    # =================================================================
    sens_xnum = numeral_ticks(chars, 335, 535, 294, 306, axis="x", gap=20.0)
    smx, sbx, sxr = affine_fit(sens_xnum)        # nm = smx*x_px + sbx

    sens_hrules, sens_hedges = gridlines(els, SENS_FRAME, "h")
    sens_arrow = spacing_arrow_span(els, SENS_FRAME, "v", (323.0, 330.0))
    s_a0 = min(sens_hrules, key=lambda y: abs(y - sens_arrow[0]))
    s_a1 = min(sens_hrules, key=lambda y: abs(y - sens_arrow[1]))
    sens_step = float(stack_text)                # 1.0 -- see verdict below
    # ORIGIN IS ARBITRARY: log sensitivity := 0 at the arrow's lower gridline.
    # NB the frame's top edge is deliberately lattice-tested here: it sits only
    # ~12 pt above the highest rule and is NOT a gridline, so it gets rejected.
    SENS_Y, sens_pitch, sens_yrej = lattice_ticks(sens_hrules, sens_hedges,
                                                  s_a0, sens_step)
    smy, sby, syr = affine_fit(SENS_Y)           # logS_rel = smy*y_px + sby

    sens_interval_px = sens_pitch
    verdict = {
        "question": "does the stacked y numeral of chart 14 read 0.1 or 1.0?",
        "verdict": stack_text,
        "decade_per_gridline_interval": sens_step,
        "evidence": [
            ("Text matrix of the glyph run is %s -- a +90 deg rotation, so the "
             "text advance direction (1,0) maps to device (0,+%.3f). Reading "
             "order therefore runs UP the page, and sorting the glyphs by "
             "ascending device y gives the reading order."
             % (stack_matrix, stack_matrix[1] if stack_matrix else float("nan"))),
            ("Glyphs by ascending y0: %s -> '%s'. Read the other way (down the "
             "page, i.e. against the text matrix) it would spell '%s', which is "
             "the 0.1 misreading."
             % (", ".join("%r@y0=%.2f" % (d["glyph"], d["y0"]) for d in stack_detail),
                stack_text, stack_text[::-1])),
            ("Placement corroborates it: the numeral's centre sits at device "
             "y=%.2f, the midpoint (%.2f) of the double-headed arrow spanning "
             "y %.1f..%.1f, whose ends snap to the horizontal gridlines at "
             "y=%.2f and y=%.2f. The numeral therefore labels exactly ONE "
             "gridline interval, not the whole axis."
             % (float(np.mean([(c.y0 + c.y1) / 2 for c in stack])),
                (s_a0 + s_a1) / 2, sens_arrow[0], sens_arrow[1], s_a0, s_a1)),
            ("Same idiom as chart 13 on the same page, where the single x "
             "numeral '%s' likewise labels a spacing arrow between two adjacent "
             "gridlines. Consistent construction across the two charts."
             % (hd_xlabel[0][1] if hd_xlabel else "0.5")),
            ("Magnitude check: %.1f log unit per %.2f pt interval spans %.2f log "
             "over the %d gridline intervals of the frame, which is the normal "
             "dynamic range of an RA-4 paper spectral-sensitivity plot. The 0.1 "
             "reading would compress the whole family into %.2f log, which no "
             "paper datasheet plots."
             % (sens_step, sens_interval_px, sens_step * (len(SENS_Y) - 1),
                len(SENS_Y) - 1, 0.1 * (len(SENS_Y) - 1))),
        ],
    }

    sens_curves, sens_near, sens_reasons = select_data_curves(els, SENS_FRAME)
    wl_sens = np.arange(376, 727, 1.0)

    sens_layers, sens_audit, sens_detect = {}, {}, []
    for i, c in enumerate(sens_curves):
        dc = to_data(polyline_dense(c), smx, sbx, smy, sby)
        vals, rng = resample_curve(dc, wl_sens, extrapolate=False)
        peak = peak_wavelength(wl_sens, vals)
        layer = layer_from_peak(peak, i)
        # A second curve landing in a layer already filled means the peak
        # assignment collided; overwriting would lose a real curve in silence.
        if layer in sens_layers:
            raise SystemExit(
                "spectral sensitivity: curve %d (peak %.1f nm) assigned to layer "
                "%s, which is already held by a curve peaking at %.1f nm"
                % (i, peak, layer, sens_layers[layer]["_peak_nm"]))
        mask = ~np.isnan(vals)
        w, v = wl_sens[mask], vals[mask]
        order = np.argsort(w)
        sens_layers[layer] = {
            "wavelength_nm": [round(float(x), 2) for x in w[order]],
            "log_sensitivity": [round(float(x), 4) for x in v[order]],
            "_peak_nm": round(peak, 2),
        }
        vmin, vmax = float(np.nanmin(vals)), float(np.nanmax(vals))
        sens_detect.append((round(peak, 2), layer, int(len(dc)), round(vmin, 4),
                            round(vmax, 4), round(rng[0], 2), round(rng[1], 2)))
        sens_audit[layer] = {
            "peak_nm": round(peak, 2),
            "assigned_by": "spectral peak wavelength (not legend order, not draw order)",
            "stroke_rgb": [round(x, 4) for x in rgb(c.stroking_color)],
            "wavelength_range_nm": [round(rng[0], 2), round(rng[1], 2)],
            "n_path_points": int(len(dc)),
            "n_samples": len(sens_layers[layer]["wavelength_nm"]),
            "log_sensitivity_range": [round(vmin, 4), round(vmax, 4)],
        }

    if len(sens_layers) != 3:
        raise SystemExit(
            "spectral sensitivity: expected exactly 3 layers, found %d (%s)"
            % (len(sens_layers), ", ".join(sorted(sens_layers))))

    audit["spectral_sensitivity"] = {
        "chart": "14  分光感度曲線 (spectral sensitivity)",
        "page_index": PAGE,
        "frame_device_bbox": list(SENS_FRAME),
        "x_axis": {
            "device_to_data": "wavelength_nm = %.6f*x_px + %.6f" % (smx, sbx),
            "anchors": [(round(p, 3), v) for p, v in sens_xnum],
            "anchor_source": "printed numerals 400/500/600/700, glyph-group-centre x",
            "fit_rms_data": round(sxr, 5),
        },
        "y_axis": {
            "device_to_data": "log_sensitivity_relative = %.6f*y_px + %.6f" % (smy, sby),
            "anchors": SENS_Y,
            "fit_rms_data": round(syr, 5),
            "ORIGIN_IS_ARBITRARY": True,
            "axis_is_relative": True,
            "origin_note": (
                "比感度（対数） = RELATIVE log sensitivity. The axis carries a "
                "single spacing numeral and no absolute coordinate, so logS=0 is "
                "DEFINED at the gridline y=%.2f purely by convention. Only "
                "differences -- within a layer and between layers -- are "
                "meaningful." % s_a0),
            "gridline_pitch_px": round(sens_pitch, 4),
            "off_lattice_positions_rejected": sens_yrej,
            "stacked_numeral_verdict": verdict,
        },
        "layer_by_peak": sens_audit,
        "paths_near_frame": sens_near,
        "paths_kept": len(sens_curves),
        "paths_discarded": sens_near - len(sens_curves),
        "discard_reasons": sens_reasons,
        "toe_axis_exclusion": (
            "Identical rule to chart 13: all LTLine/LTRect frame, gridline and "
            "spacing-arrow geometry is dropped before curve selection, and "
            "survivors must be stroked in a saturated hue, so near-neutral axis "
            "ink cannot contaminate a curve's low-sensitivity tail."),
    }

    # =================================================================
    # CHART 15 -- spectral dye density
    # =================================================================
    dye_xnum = numeral_ticks(chars, 90, 275, 76, 86, axis="x", gap=20.0)
    dye_ynum = numeral_ticks(chars, 74, 89, 82, 200, axis="y", gap=8.0)
    dmx, dbx, dxr = affine_fit(dye_xnum)         # nm = dmx*x_px + dbx
    dmy, dby, dyr = affine_fit(dye_ynum)         # D  = dmy*y_px + dby

    dye_hrules, dye_hedges = gridlines(els, DYE_FRAME, "h")
    dye_grid_ticks, dye_grid_rej = snapped_ticks(dye_hrules + dye_hedges,
                                                 dmy, dby, 0.5, 0.06)
    dye_grid_fit = affine_fit(dye_grid_ticks)
    dye_num_fit = (dmy, dby, dyr)
    dye_grid_disagree = max(abs((dmy * y + dby) - (dye_grid_fit[0] * y + dye_grid_fit[1]))
                            for y in (DYE_FRAME[1], DYE_FRAME[3]))
    # gridlines are primary here too -- see the chart 13 y-axis note above
    dmy, dby, dyr = dye_grid_fit

    dye_curves, dye_near, dye_reasons = select_data_curves(els, DYE_FRAME)
    wl_dye = np.arange(400, 701, 1.0)

    dye_layers, dye_audit, dye_detect = {}, {}, []
    for i, c in enumerate(dye_curves):
        dc = to_data(polyline_dense(c), dmx, dbx, dmy, dby)
        vals, rng = resample_curve(dc, wl_dye, extrapolate=True)   # flat-hold edges
        peak = peak_wavelength(wl_dye, vals)
        layer = layer_from_peak(peak, i)
        if layer in dye_layers:
            raise SystemExit(
                "spectral dye density: curve %d (peak %.1f nm) assigned to layer "
                "%s, which is already held by a curve peaking at %.1f nm"
                % (i, peak, layer, dye_layers[layer]["_peak_nm"]))
        dye_layers[layer] = {
            "wavelength_nm": [int(x) for x in wl_dye],
            "density": [round(float(x), 4) for x in vals],
            "_peak_nm": round(peak, 2),
        }
        vmin, vmax = float(np.min(vals)), float(np.max(vals))
        dye_detect.append((round(peak, 2), layer, int(len(dc)), round(vmin, 4),
                           round(vmax, 4), round(rng[0], 2), round(rng[1], 2)))
        dye_audit[layer] = {
            "peak_nm": round(peak, 2),
            "assigned_by": "spectral peak wavelength (not legend order, not draw order)",
            "stroke_rgb": [round(x, 4) for x in rgb(c.stroking_color)],
            "wavelength_range_nm": [round(rng[0], 2), round(rng[1], 2)],
            "n_path_points": int(len(dc)),
            "n_samples": len(wl_dye),
            "density_range": [round(vmin, 4), round(vmax, 4)],
        }

    if len(dye_layers) != 3:
        raise SystemExit(
            "spectral dye density: expected exactly 3 layers, found %d (%s)"
            % (len(dye_layers), ", ".join(sorted(dye_layers))))

    audit["spectral_dye_density"] = {
        "chart": "15  色素の分光濃度曲線 (spectral dye density)",
        "page_index": PAGE,
        "frame_device_bbox": list(DYE_FRAME),
        "density_kind": "spectral REFLECTION density (分光反射濃度)",
        "x_axis": {
            "device_to_data": "wavelength_nm = %.6f*x_px + %.6f" % (dmx, dbx),
            "anchors": [(round(p, 3), v) for p, v in dye_xnum],
            "anchor_source": "printed numerals 400/500/600/700, glyph-group-centre x",
            "fit_rms_data": round(dxr, 5),
        },
        "y_axis": {
            "device_to_data": "density = %.6f*y_px + %.6f" % (dmy, dby),
            "anchors": [(round(p, 3), v) for p, v in dye_grid_ticks],
            "anchor_source": ("horizontal gridlines, labelled 0.0/0.5/1.0 by the "
                              "printed numerals -- numerals for values, "
                              "gridlines for positions"),
            "fit_rms_data": round(dyr, 5),
            "off_lattice_positions_rejected": dye_grid_rej,
            "numeral_crosscheck": {
                "device_to_data": "density = %.6f*y_px + %.6f" % (dye_num_fit[0],
                                                                  dye_num_fit[1]),
                "anchors": [(round(p, 3), v) for p, v in dye_ynum],
                "n_numerals": len(dye_ynum),
                "fit_rms_data": round(dye_num_fit[2], 5),
                "max_disagreement_D_over_frame": round(float(dye_grid_disagree), 4),
            },
        },
        "layer_by_peak": dye_audit,
        "paths_near_frame": dye_near,
        "paths_kept": len(dye_curves),
        "paths_discarded": dye_near - len(dye_curves),
        "discard_reasons": dye_reasons,
        "toe_axis_exclusion": (
            "Same wholesale LTLine/LTRect drop plus the saturated-hue gate. This "
            "chart's frame floor sits essentially at D=0.0, so an axis fragment "
            "welded onto a dye tail would read as a spurious zero-density "
            "shoulder; excluding the rules by element type prevents that."),
    }

    # =================================================================
    # layer mapping + assembly
    # =================================================================
    # Chain: an H&D curve is the response to one exposing primary. Chart 14
    # says which emulsion answers that primary (peak wavelength), and the
    # subtractive rule fixes the dye it forms.
    hd_for_layer, layer_mapping = {}, {}
    hue_band = {"R": ("cyan", 600, 760), "G": ("magenta", 500, 600),
                "B": ("yellow", 380, 500)}
    for hue, (layer, wl0, wl1) in hue_band.items():
        hd_for_layer[layer] = hue
        pk = sens_layers[layer]["_peak_nm"]
        layer_mapping[layer] = {
            "hd_curve": hue,
            "sensitivity_peak_nm": pk,
            "dye_peak_nm": dye_layers[layer]["_peak_nm"],
            "reasoning": ("H&D curve '%s' is the %s-light exposure response; the "
                          "emulsion peaking at %.1f nm (in [%d,%d)) is the "
                          "%s-sensitive layer, which forms %s dye (peak %.1f nm)."
                          % (hue, hue, pk, wl0, wl1,
                             {"R": "red", "G": "green", "B": "blue"}[hue],
                             layer, dye_layers[layer]["_peak_nm"])),
        }
    audit["layer_mapping"] = layer_mapping

    layers = {}
    for layer in ("cyan", "magenta", "yellow"):
        s, d = sens_layers[layer], dye_layers[layer]
        gx, gy = hd_curve_data[hd_for_layer[layer]]
        layers[layer] = {
            "sensitivity": {
                "wavelength_nm": s["wavelength_nm"],
                "log_sensitivity": s["log_sensitivity"],
            },
            "dye": {
                "wavelength_nm": d["wavelength_nm"],
                "density": d["density"],
            },
            "hd": {
                "logE": gx,
                "statusA_density": gy,
            },
            "peak_sensitivity_nm": s["_peak_nm"],
            "peak_dye_nm": d["_peak_nm"],
        }

    out = {
        "provenance": {
            "source": ("FUJIFILM Product Information Bulletin -- Fujicolor "
                       "Professional Paper Pro Laser TYPE II (Frontier QL type), "
                       "Japan market; page index 3 (printed page 4) vector charts "
                       "13/14/15, digitized from embedded PDF path geometry"),
            "density_measure": "status_a",
            "densitometry_note": "ステータスA相当 (Status A equivalent)",
            "dye_density_kind": "spectral reflection density (分光反射濃度)",
            "status": "datasheet-digitized (independent re-trace)",
            "process": "CP-48S",
            "exposure": "laser (レーザー露光)",
            "sensitivity_definition": ("reciprocal of the exposure (J/cm2) "
                                       "required to reach density = Dmin + 1.0"),
            "caveat": ("※ディープマットは上記特性曲線とは異なります -- the Deep "
                       "Matte surface does NOT follow these characteristic curves."),
            "relative_axes": ("H&D logE and spectral log-sensitivity both have "
                              "ARBITRARY origins: the datasheet prints only "
                              "gridline spacings on those axes, no absolute "
                              "coordinate. Differences are meaningful, absolute "
                              "values are not."),
            "date": "2026-07-25",
        },
        "layers": layers,
        "digitization_audit": audit,
    }

    outp = DATA / "papers" / "FujiProLaserTypeII_paper.json"
    outp.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(outp, "w"), indent=1, ensure_ascii=False)

    # ============================ self-report ============================
    print("=== axis fits (device px -> data) ===")
    print("chart13 H&D  x: logH_rel = %.6f*x + %.6f  RMS %.5f dec   [RELATIVE, arbitrary origin @x=%.2f]"
          % (hmx, hbx, hxr, hd_a0))
    print("             lattice: pitch %.3f pt = %.2f dec, %d anchors, off-lattice rejected %s"
          % (hd_pitch, step, len(HD_X), hd_xrej))
    print("chart13 H&D  y: D        = %.6f*y + %.6f  RMS %.5f D     (%d gridlines)"
          % (hmy, hby, hyr, len(hd_grid_ticks)))
    print("             numeral cross-check:  D = %.6f*y + %.6f  RMS %.5f  max disagree %.4f D"
          % (hd_num_fit[0], hd_num_fit[1], hd_num_fit[2], hd_grid_disagree))
    print("chart14 SENS x: nm       = %.6f*x + %.6f  RMS %.5f nm    (%d printed numerals)"
          % (smx, sbx, sxr, len(sens_xnum)))
    print("chart14 SENS y: logS_rel = %.6f*y + %.6f  RMS %.5f logS  [RELATIVE, arbitrary origin @y=%.2f]"
          % (smy, sby, syr, s_a0))
    print("             lattice: pitch %.3f pt = %.2f logS, %d anchors, off-lattice rejected %s"
          % (sens_pitch, sens_step, len(SENS_Y), sens_yrej))
    print("chart15 DYE  x: nm       = %.6f*x + %.6f  RMS %.5f nm    (%d printed numerals)"
          % (dmx, dbx, dxr, len(dye_xnum)))
    print("chart15 DYE  y: D        = %.6f*y + %.6f  RMS %.5f D     (%d gridlines)"
          % (dmy, dby, dyr, len(dye_grid_ticks)))
    print("             numeral cross-check:  D = %.6f*y + %.6f  RMS %.5f  max disagree %.4f D"
          % (dye_num_fit[0], dye_num_fit[1], dye_num_fit[2], dye_grid_disagree))

    print("=== path filtering: kept vs discarded, per chart ===")
    for tag, near, kept, why in (("chart13 H&D ", hd_near, len(hd_curves), hd_reasons),
                                 ("chart14 SENS", sens_near, len(sens_curves), sens_reasons),
                                 ("chart15 DYE ", dye_near, len(dye_curves), dye_reasons)):
        print("%s: %3d paths near frame -> KEPT %d, DISCARDED %3d   (%s)"
              % (tag, near, kept, near - kept,
                 ", ".join("%s=%d" % kv for kv in sorted(why.items()))))

    print("=== chart13 H&D per curve (x is RELATIVE logH) ===")
    for n in hd_names:
        e = hd_endpoints[n]
        gx, _ = hd_curve_data[n]
        print("  %s (rgb %s): %d samples  logH_rel %.3f..%.3f  D %.4f..%.4f  Dmin %.4f  Dmax %.4f"
              % (n, e["stroke_rgb"], e["n_samples"], gx[0], gx[-1],
                 e["density_range"][0], e["density_range"][1], e["Dmin"], e["Dmax"]))

    print("=== chart14 spectral sensitivity per layer (ASSIGNED BY PEAK) ===")
    for peak, layer, npts, mn, mx, r0, r1 in sorted(sens_detect):
        s = sens_layers[layer]
        print("  peak %.1f nm -> %-7s : %d samples  nm %.1f..%.1f  logS %.4f..%.4f"
              % (peak, layer, len(s["wavelength_nm"]), r0, r1, mn, mx))

    print("=== chart15 spectral dye density per layer (ASSIGNED BY PEAK) ===")
    for peak, layer, npts, mn, mx, r0, r1 in sorted(dye_detect):
        d = dye_layers[layer]
        print("  peak %.1f nm -> %-7s : %d samples  nm %d..%d (traced %.1f..%.1f)  D %.4f..%.4f"
              % (peak, layer, len(d["wavelength_nm"]), d["wavelength_nm"][0],
                 d["wavelength_nm"][-1], r0, r1, mn, mx))

    print("=== layer assignment chain ===")
    for layer in ("cyan", "magenta", "yellow"):
        print("  %-7s <- %s" % (layer, layer_mapping[layer]["reasoning"]))

    print("=== VERDICT: chart14 stacked y numeral, 0.1 vs 1.0 ===")
    print("  READS '%s'  =>  %.1f log unit per gridline interval (%.2f pt)"
          % (stack_text, sens_step, sens_interval_px))
    for e in verdict["evidence"]:
        print("  - " + e)

    print("wrote %s" % outp.relative_to(ROOT))


if __name__ == "__main__":
    main()
