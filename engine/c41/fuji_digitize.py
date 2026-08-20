#!/usr/bin/env python3
"""Fuji-template datasheets -> <Prefix>_datasheet_curves.json + _spectral_sensitivity.json.

Renamed from fuji400_digitize.py when FUJIFILM 200 (AF3-0261E) turned out to use
the same template as FUJIFILM 400 (AF3-0262E) -- consecutive publications, same
three charts, same conventions. Pick the stock with --stock; only the per-sheet
geometry in SHEETS differs, everything below it is shared.

A SEPARATE digitizer from portra_digitize.py because this sheet is a Fuji-template
sheet, not a Kodak one, and every assumption the Kodak scripts make about chart
geometry fails on it:

  1. HALF-DECADE GRIDLINES ON BOTH CHARACTERISTIC AXES. The logH axis runs
     -4.0..+0.5 in steps of 0.5 over TEN gridlines, and the density axis 0.0..4.0
     in steps of 0.5 over NINE. Every Kodak sheet so far steps by 1.0. The
     count-based assignment the Kodak digitizers use (origin + n*1.0) would read
     the logH axis as -4.0..+5.0 and the density axis as 0.0..8.0 -- a 4.5-decade
     and a 2x error, with clean residuals either way, because evenly spaced
     gridlines fit any step with zero error.
  2. THE DYE-DENSITY PLOT BOX IS WIDER THAN ITS LABELLED RANGE. 400 nm sits at
     x=71.10 and 700 nm at x=274.60, but the frame edges are 60.20 and 287.90
     (~384 and ~719 nm). Deriving wavelength from the frame box -- which is what
     every Kodak chart permits -- is wrong by ~16 nm at each end. Only the four
     labelled ticks are used here.
  3. THE LOG-SENSITIVITY AXIS IS PURELY RELATIVE. The chart prints no numeric y
     scale at all, only a 1.0-decade scale bar between two reference marks. There
     is no absolute origin to recover, so this file emits RELATIVE log
     sensitivity with 0.0 at the lower mark and says so, loudly, in the JSON and
     on stdout. Kodak sheets print an absolute axis; the two are NOT comparable
     in magnitude. They also use different reference densities (Fuji 1.0 above
     D-min, Kodak Ultra Max 0.2 above D-min) and different wavelength ranges
     (400-700 vs 250-750 nm).
  4. THE DATA CURVES ARE CUBIC BEZIERS, not dense polylines. pdfminer flattens a
     path to a bare point list, so a Bezier control point -- which is NOT on the
     curve -- is indistinguishable from a sampled vertex. Reading those points as
     data puts phantom peaks in the curve. This script therefore uses PyMuPDF,
     whose get_drawings() preserves the operator sequence, and evaluates each
     cubic parametrically.

Chart page is NOT the index-3 default of the Kodak sheets: FUJIFILM 400
(AF3-0262E) carries them on page index 5 (printed "No 6"), FUJIFILM 200
(AF3-0261E) on page index 4. The two sheets are the same template but NOT the
same geometry -- on the 200 sheet the characteristic frame sits ~4.4 pt lower,
the sensitivity ticks ~0.2 pt left, and the sensitivity scale bar is 65.80
pt/decade against the 400 sheet's 65.90. Only the dye-density chart happens to
be pixel-identical between them. Never reuse one sheet's numbers on the other.

The two Japanese-market sheets, FUJICOLOR 100 (013AR0317A) and FUJICOLOR SUPERIA
PREMIUM 400 (013AR0324A), are the same family of template but drift further
still: A4 pages, the bottom two quadrants MIRRORED (dye density bottom-RIGHT,
MTF bottom-LEFT), a 57.19 pt/decade sensitivity scale bar, and -- on FUJICOLOR
100 only -- a characteristic x axis running -3.5..+1.0 whose printed minus signs
are not extractable. See the notes above the SHEETS table.

FUJICOLOR PRO 400H (AF3-176E, page index 7) is the fifth sheet and the loosest
fit of all. It emits ONLY <Prefix>_datasheet_curves.json, no sensitivity file:
its sensitivity chart has FOUR curves, a dashed "Cyan Sensitive Layer" between
green and red, and the three-layer classifier below has nowhere to put it. It is
also the first sheet with NO extractable numeric axis labels anywhere, and the
first whose characteristic density axis is 0.0..3.5 (8 gridlines) and whose
dye-density axis is 0.0..2.0 (5) -- which is why CHAR_YVALS and SPEC_YVALS are
per sheet rather than shared module constants. Notes (d)-(g) above SHEETS.

Axis calibration constants below were read off datasheet_forensics.py and
cross-checked against the printed labels and a datasheet_render.py raster.

Run:  python3 engine/c41/fuji_digitize.py [--stock fujifilm200]
      (from repo root; self-reports metrics)
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

try:
    import fitz                                  # PyMuPDF
except ImportError:                              # pragma: no cover
    raise SystemExit("fuji_digitize.py needs PyMuPDF: pip install pymupdf")

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from portra_stocks import STOCKS                 # noqa: E402

PAGE_H = 792.0                                   # bottom-up <-> top-down pivot

# ---------------------------------------------------------------- calibration
# All constants in pdfminer/PDF BOTTOM-UP device space (y from the page bottom).
# PyMuPDF is top-down; convert with y_bu = PAGE_H - y_fitz.
#
# Per-sheet geometry ONLY. The axis VALUES (half-decade steps, 400-700 nm) and
# every algorithm below are shared, because the two sheets are the same template.
#
# 15. CHARACTERISTIC CURVES (top-left) -- gridlines at a half-decade step, with
#     printed labels on every 2nd x gridline.
# 16. SPECTRAL DYE DENSITY (bottom-left) -- labelled x ticks ONLY; the frame
#     edges (~60.2, ~287.9) are NOT data ticks on this chart.
# 17. SPECTRAL SENSITIVITY (top-right) -- same story on x; on y the only
#     reference is a 1.0-decade scale bar between two marks.
#
# The two Japanese-market sheets (FUJICOLOR 100, FUJICOLOR SUPERIA PREMIUM 400)
# are the same FAMILY of template but differ in three ways that are fatal if
# copied over from the export sheets:
#
#   a. PAGE SIZE is A4 (595x842), not US Letter (612x792). PAGE_H is the
#      top-down <-> bottom-up pivot, so it is per sheet, not a module constant.
#   b. THE QUADRANTS ARE MIRRORED. On the export sheets the dye-density chart is
#      BOTTOM-LEFT and MTF is bottom-right; on the JP sheets dye density is
#      BOTTOM-RIGHT and MTF is BOTTOM-LEFT. Reusing the export REGION_SPEC here
#      would silently harvest the MTF curve, with no count or ordering guard
#      tripping (MTF also draws smooth Bezier curves).
#   c. THE CHARACTERISTIC X RANGE IS NOT UNIVERSAL. FUJICOLOR 100 runs
#      -3.5..+1.0, a full decade right of the -4.0..+0.5 the other three sheets
#      use. Hence CHAR_XVALS is per sheet.
#
# FUJIFILM PRO 400H (AF3-176E) breaks two MORE axis-value assumptions, which is
# why CHAR_YVALS and SPEC_YVALS are per sheet as well:
#
#   d. ITS CHARACTERISTIC DENSITY AXIS RUNS 0.0..3.5, over EIGHT gridlines, not
#      the 0.0..4.0 over nine that the other four sheets print.
#   e. ITS DYE-DENSITY AXIS RUNS 0.0..2.0, over FIVE gridlines, not 0.0..2.5
#      over six. Its frame top additionally sits ABOVE the 2.0 gridline, with no
#      label -- pure headroom, NOT a sixth tick.
#   Both are the same class of failure as (c): the gridlines are evenly spaced,
#   so the wrong assignment fits with zero residual and produces plausible
#   wrong numbers rather than an error.
#
#   f. PRO 400H ALSO HAS NO EXTRACTABLE NUMERIC AXIS LABELS AT ALL. Not "the
#      minus signs are missing" as on FUJICOLOR 100 -- datasheet_forensics.py
#      finds no numeric labels on any axis of any frame. There is nothing to
#      cross-check against, on either axis of either chart, so the axis values
#      above rest on the gridline positions plus a 300 dpi rendered-page reading
#      of the printed labels, and the datasheet_overlay.py ink-hit test is the
#      ONLY validator this stock has.
#
#   g. PRO 400H'S SPECTRAL SENSITIVITY CHART IS DELIBERATELY NOT DIGITIZED. It
#      carries FOUR curves -- a dashed "Cyan Sensitive Layer" sitting between
#      the green and red layers -- and every classifier here assumes exactly
#      three, sorted by ascending peak. How a fourth sensitivity layer should
#      feed a 3-channel exposure model is an unresolved modelling question, so
#      the sheet carries "sensitivity_absent": True, no SENS_* geometry, and
#      emits no Pro400H_spectral_sensitivity.json. Do not "complete" this by
#      dropping the fourth curve; that is a modelling decision, not a
#      digitization one.
SHEETS = {
    "fujifilm400": {
        "sheet_name": "FUJIFILM 400",
        "PAGE_H": 792.0,
        "PAGE_W": 612.0,
        "CHAR_XVALS": [-4.0 + 0.5 * i for i in range(10)],    # -4.0 .. +0.5
        "CHAR_YVALS": [0.0 + 0.5 * i for i in range(9)],      # 0.0 .. 4.0
        "SPEC_YVALS": [0.0 + 0.5 * i for i in range(6)],      # 0.0 .. 2.5
        # The JSON `source` string still names fuji400_digitize.py: this file's
        # fujifilm400 output is byte-for-byte frozen, and that is the regression
        # guard for the parameterization. Do not "fix" it.
        "emitted_by": "fuji400_digitize.py",
        "CHAR_XGRID": [60.10, 85.40, 110.70, 136.10, 161.40, 186.70,
                       212.00, 237.30, 262.60, 288.00],
        "CHAR_YGRID": [491.80, 517.20, 542.50, 567.80, 593.10,
                       618.40, 643.70, 669.10, 694.40],
        "CHAR_XLABELS": [(60.10, -4.0), (110.70, -3.0), (161.40, -2.0),
                         (212.00, -1.0), (262.60, 0.0)],
        "SPEC_XTICKS": [(71.10, 400.0), (139.50, 500.0),
                        (207.90, 600.0), (274.60, 700.0)],
        "SPEC_YGRID": [246.20, 279.60, 312.90, 346.30, 379.70, 413.00],
        "SENS_XTICKS": [(374.60, 400.0), (440.40, 500.0),
                        (506.30, 600.0), (572.10, 700.0)],
        "SENS_Y_ZERO": 561.70,                            # arbitrary datum
        "SENS_Y_ONE": 627.60,                             # 65.90 pt/decade
        "REGION_CHAR": (55.0, 486.0, 293.0, 700.0),
        "REGION_SPEC": (55.0, 240.0, 293.0, 419.0),
        "REGION_SENS": (356.0, 490.0, 590.0, 699.0),
    },
    "fujifilm200": {
        "sheet_name": "FUJIFILM 200",
        "emitted_by": "fuji_digitize.py",
        "PAGE_H": 792.0,
        "PAGE_W": 612.0,
        "CHAR_XVALS": [-4.0 + 0.5 * i for i in range(10)],    # -4.0 .. +0.5
        "CHAR_YVALS": [0.0 + 0.5 * i for i in range(9)],      # 0.0 .. 4.0
        "SPEC_YVALS": [0.0 + 0.5 * i for i in range(6)],      # 0.0 .. 2.5
        "CHAR_XGRID": [60.20, 85.50, 110.90, 136.30, 161.60,
                       187.00, 212.40, 237.80, 263.10, 288.50],
        "CHAR_YGRID": [487.40, 512.80, 538.20, 563.50, 588.90,
                       614.30, 639.60, 665.00, 690.40],
        "CHAR_XLABELS": [(60.20, -4.0), (110.90, -3.0), (161.60, -2.0),
                         (212.40, -1.0), (263.10, 0.0)],
        "SPEC_XTICKS": [(71.10, 400.0), (139.50, 500.0),
                        (207.90, 600.0), (274.60, 700.0)],
        "SPEC_YGRID": [246.20, 279.60, 312.90, 346.30, 379.70, 413.00],
        "SENS_XTICKS": [(374.80, 400.0), (440.60, 500.0),
                        (506.30, 600.0), (572.10, 700.0)],
        "SENS_Y_ZERO": 562.80,
        "SENS_Y_ONE": 628.60,                             # 65.80 pt/decade
        "REGION_CHAR": (55.0, 482.0, 293.0, 696.0),
        "REGION_SPEC": (55.0, 240.0, 293.0, 419.0),
        "REGION_SENS": (356.0, 492.0, 590.0, 699.0),
    },
    "fujicolor100": {
        "sheet_name": "FUJICOLOR 100",
        "emitted_by": "fuji_digitize.py",
        "PAGE_H": 842.0,                                  # A4, not US Letter
        "PAGE_W": 595.0,
        # -3.5..+1.0, NOT the -4.0..+0.5 of the other three sheets.
        "CHAR_XVALS": [-3.5 + 0.5 * i for i in range(10)],
        "CHAR_YVALS": [0.0 + 0.5 * i for i in range(9)],      # 0.0 .. 4.0
        "SPEC_YVALS": [0.0 + 0.5 * i for i in range(6)],      # 0.0 .. 2.5
        "CHAR_XGRID": [90.00, 111.50, 133.40, 155.50, 176.90,
                       198.70, 220.30, 242.20, 263.80, 285.70],
        "CHAR_YGRID": [454.40, 475.60, 497.00, 519.20, 540.80,
                       562.40, 584.20, 606.30, 627.40],
        # pdfminer/PyMuPDF extract this sheet's x labels WITHOUT their minus
        # signs ('3.0 2.0 1.0 0.0 1.0' for -3.0 -2.0 -1.0 0.0 +1.0), exactly the
        # fault already documented for Gold 200 in portra_digitize.py. The
        # cross-check is therefore SKIPPED here and flagged on stdout rather
        # than silently dropped; the x calibration rests on the gridline
        # positions plus the rendered-page reading of the printed labels.
        "char_x_labels_unreliable": True,
        # BOTTOM-RIGHT on this sheet -- mirrored vs the export sheets, where the
        # dye-density chart is bottom-LEFT and this quadrant holds MTF.
        "SPEC_XTICKS": [(337.50, 400.0), (397.80, 500.0),
                        (458.20, 600.0), (519.80, 700.0)],
        "SPEC_YGRID": [207.70, 237.40, 266.80, 297.10, 326.20, 356.10],
        "SENS_XTICKS": [(348.30, 400.0), (405.60, 500.0),
                        (462.80, 600.0), (519.80, 700.0)],
        # Full-width horizontal reference lines bracketing the 1.0-decade scale
        # bar, the same construct as the export sheets. 57.19 pt/decade rather
        # than ~65.9 because the whole JP chart is drawn smaller: the frame is
        # 171.3 pt tall against the export sheet's 197.5, and
        # 65.85 * 171.3/197.5 = 57.1.
        "SENS_Y_ZERO": 512.49,
        "SENS_Y_ONE": 569.68,                             # 57.19 pt/decade
        "REGION_CHAR": (85.0, 449.0, 291.0, 632.0),
        "REGION_SPEC": (321.0, 202.0, 536.0, 361.0),
        "REGION_SENS": (332.0, 450.0, 536.0, 631.0),
    },
    "superiapremium400": {
        "sheet_name": "FUJICOLOR SUPERIA PREMIUM 400",
        "emitted_by": "fuji_digitize.py",
        "PAGE_H": 842.0,                                  # A4, not US Letter
        "PAGE_W": 595.0,
        "CHAR_XVALS": [-4.0 + 0.5 * i for i in range(10)],    # -4.0 .. +0.5
        "CHAR_YVALS": [0.0 + 0.5 * i for i in range(9)],      # 0.0 .. 4.0
        "SPEC_YVALS": [0.0 + 0.5 * i for i in range(6)],      # 0.0 .. 2.5
        "CHAR_XGRID": [88.30, 109.90, 131.80, 153.90, 175.30,
                       197.10, 218.70, 240.60, 262.20, 284.10],
        "CHAR_YGRID": [443.40, 464.60, 486.10, 508.20, 529.80,
                       551.40, 573.20, 595.30, 616.40],
        # This sheet DOES keep its minus signs, so the cross-check stays on.
        "CHAR_XLABELS": [(88.30, -4.0), (131.80, -3.0), (175.30, -2.0),
                         (218.70, -1.0), (262.20, 0.0)],
        # BOTTOM-RIGHT here too -- see the note above the SHEETS table.
        "SPEC_XTICKS": [(344.50, 400.0), (404.80, 500.0),
                        (465.20, 600.0), (526.80, 700.0)],
        "SPEC_YGRID": [187.80, 217.50, 246.80, 277.10, 306.30, 336.20],
        "SENS_XTICKS": [(350.10, 400.0), (407.60, 500.0),
                        (464.60, 600.0), (521.50, 700.0)],
        "SENS_Y_ZERO": 502.59,
        "SENS_Y_ONE": 559.78,                             # 57.19 pt/decade
        "REGION_CHAR": (83.0, 438.0, 290.0, 621.0),
        "REGION_SPEC": (328.0, 182.0, 543.0, 341.0),
        "REGION_SENS": (334.0, 441.0, 538.0, 621.0),
    },
    "pro400h": {
        "sheet_name": "FUJICOLOR PRO 400H",
        "emitted_by": "fuji_digitize.py",
        # 595x794 -- neither US Letter nor exactly A4 (842 tall). The page-size
        # guard below is +/-0.5 pt, so this had to be read off the PDF.
        "PAGE_H": 794.0,
        "PAGE_W": 595.0,
        "CHAR_XVALS": [-4.0 + 0.5 * i for i in range(11)],    # -4.0 .. +1.0
        # 0.0..3.5 over EIGHT gridlines, not the 0.0..4.0 over nine that the
        # other four sheets print. See note (d) above the table.
        "CHAR_YVALS": [0.0 + 0.5 * i for i in range(8)],      # 0.0 .. 3.5
        # 0.0..2.0 over FIVE gridlines. The frame top (419.60) is ABOVE the 2.0
        # gridline (408.00) and carries no label -- headroom, not a sixth tick.
        "SPEC_YVALS": [0.0 + 0.5 * i for i in range(5)],      # 0.0 .. 2.0
        "CHAR_XGRID": [78.60, 99.00, 120.30, 141.40, 161.90, 182.40,
                       203.20, 223.70, 244.50, 264.80, 285.50],
        "CHAR_YGRID": [544.40, 565.30, 585.80, 606.50, 627.30,
                       647.50, 668.60, 689.00],
        # NO numeric labels are extractable anywhere on this sheet -- not just
        # the minus signs, as on FUJICOLOR 100, but every label on every axis of
        # every frame. There is nothing to cross-check against. See note (f).
        "char_x_labels_unreliable": True,
        "axis_labels_unreliable": True,
        "labels_unreliable_note": (
            "NO numeric axis labels are extractable anywhere on this sheet "
            "(datasheet_forensics.py reports none on either axis of either "
            "chart), so the cross-check cannot run at all; both axes of both "
            "charts rest on the gridline positions plus a 300 dpi "
            "rendered-page reading of the printed labels. The "
            "datasheet_overlay.py ink-hit test is this stock's ONLY validator."),
        "labels_unreliable_basis": (
            "this sheet carries NO extractable numeric labels on either axis of "
            "either chart, so no label cross-check is available anywhere on it; "
            "both axes rest on the gridline positions plus a 300 dpi "
            "rendered-page reading of the printed labels, with the "
            "datasheet_overlay.py ink-hit test as the only validator"),
        "labels_unreliable_label_fit": (
            "SKIPPED: this sheet carries NO extractable numeric axis labels at "
            "all -- datasheet_forensics.py finds none on either axis of either "
            "frame, so unlike Fujicolor 100 (where only the minus signs are "
            "lost) there is nothing whatever to cross-check against"),
        # BOTTOM-RIGHT, like the two JP sheets; MTF is bottom-LEFT here.
        # datasheet_forensics.py's own footnote calls the bottom-right quadrant
        # "the MTF quadrant" -- that note is hardcoded for the Kodak layout and
        # is WRONG for this sheet.
        "SPEC_XTICKS": [(334.90, 400.0), (397.20, 500.0),
                        (459.80, 600.0), (522.70, 700.0)],
        "SPEC_YGRID": [255.30, 291.80, 331.40, 370.00, 408.00],
        # No SENS_* geometry and no sensitivity output: the chart has a FOURTH
        # (dashed "Cyan Sensitive Layer") curve. See note (g) above the table.
        "sensitivity_absent": True,
        "spec_calibration_basis": (
            "four LABELLED wavelength ticks only -- 400 nm sits essentially ON "
            "the left frame edge (334.90 vs 334.67) but the frame runs right to "
            "533.87, about 718 nm, so this box is wider than its labelled range "
            "at the RED end only and a frame-derived wavelength would be ~18 nm "
            "out there"),
        "REGION_CHAR": (73.0, 539.0, 291.0, 694.0),
        "REGION_SPEC": (329.0, 250.0, 539.0, 425.0),
    },
}

SENS_ORIGIN_NOTE = (
    "RELATIVE, arbitrary: the chart prints only a 1.0-decade scale bar, no "
    "numeric y axis. 0.0 is set at the lower reference mark. NOT comparable in "
    "magnitude to Kodak sheets, which print an absolute log-sensitivity axis at "
    "0.2 above D-min; this sheet's reference density is 1.0 above D-min, and its "
    "wavelength range is 400-700 nm against Kodak's 250-750 nm."
)


def affine(ticks):
    """Least-squares device->data map over (device, value) pairs -> (m, c, rms)."""
    d = np.array([t[0] for t in ticks], float)
    v = np.array([t[1] for t in ticks], float)
    m, c = np.polyfit(d, v, 1)
    rms = float(np.sqrt(np.mean((m * d + c - v) ** 2)))
    return float(m), float(c), rms


def bezier(p0, p1, p2, p3, n=240):
    """Sample one cubic Bezier at n points over t in [0,1]."""
    t = np.linspace(0.0, 1.0, n)[:, None]
    p0, p1, p2, p3 = (np.asarray(p, float) for p in (p0, p1, p2, p3))
    return ((1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1
            + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3)


def subpaths(drawing):
    """Evaluate a get_drawings() path into its CONTINUOUS runs.

    One drawing is not one curve. On the Japanese-market sheets all three
    characteristic curves (and both dye-density curves) are emitted as a SINGLE
    path object holding several disconnected subpaths, so get_drawings() returns
    ONE drawing per chart rather than three. Concatenating its segments blindly
    -- which is what a plain path->points flattening does -- welds the R, G and B
    curves into one zig-zagging polyline, and the "expected 3 curve paths, found
    1" guard is the only thing that catches it.

    A new run starts wherever a segment's first point is not the previous
    segment's last point (the flattened form of a `m` moveto). On the export
    sheets every path is a single continuous run, so this is a no-op there --
    which is what keeps the FUJIFILM 400/200 output byte-identical.

    Returns a list of {"pts": (N,2) bottom-up device points, "n_cubic": int}.
    """
    runs, cur, ncub, last = [], [], 0, None

    def flush():
        if not cur:
            return
        a = np.vstack(cur)
        a[:, 1] = PAGE_H - a[:, 1]                # top-down -> bottom-up
        runs.append({"pts": a, "n_cubic": ncub})

    for it in drawing["items"]:
        if it[0] == "c":
            start, end, seg, n = it[1], it[4], bezier(it[1], it[2], it[3], it[4]), 1
        elif it[0] == "l":
            start, end, n = it[1], it[2], 0
            seg = np.array([[it[1].x, it[1].y], [it[2].x, it[2].y]])
        else:
            continue
        if last is not None and (abs(start.x - last.x) > 0.01
                                 or abs(start.y - last.y) > 0.01):
            flush()
            cur, ncub = [], 0
        cur.append(seg)
        ncub += n
        last = end
    flush()
    return runs


def in_region(dr, reg):
    r = dr["rect"]
    x0, y0, x1, y1 = r.x0, PAGE_H - r.y1, r.x1, PAGE_H - r.y0
    return (reg[0] <= x0 and x1 <= reg[2] and reg[1] <= y0 and y1 <= reg[3])


def chart_runs(curves, region):
    """All continuous runs of every Bezier path lying inside `region`."""
    out = []
    for d in curves:
        if in_region(d, region):
            out.extend(subpaths(d))
    return out


def drop_duplicate_subpaths(runs):
    """Drop runs that redraw part of another run in the same chart.

    The FUJIFILM 200 sensitivity chart emits the cyan curve TWICE: once whole
    (6 cubics, 479.8-571.2) and once as a 2-cubic fragment of its own leading
    section, starting at the identical point and lying within ~0.3 pt of it.
    Counted naively that chart has FOUR curve paths, not three, and the extra
    one would be classified as a fourth layer. A path is dropped only when its
    x-span is strictly contained in another's AND it starts at the same point
    -- i.e. it is provably an overprint, not a distinct curve. This is a no-op
    on the FUJIFILM 400 sheet (which is the byte-identity regression guard).

    A second, coarser case appears on the SUPERIA PREMIUM 400 dye-density chart,
    which draws BOTH curves twice, the second copy offset by ~0.04 pt. Those
    copies are the same LENGTH, so the containment test above cannot see them
    and the chart reads as four curves. Any later run whose start AND end land
    within 0.15 pt of an earlier kept run is therefore dropped as a re-stroke;
    0.15 pt is ~0.05 nm here, far below any real separation between two printed
    curves, so this too is a no-op on the export sheets.
    """
    ev = [(r, r["pts"]) for r in runs]
    keep = []
    for i, (d, a) in enumerate(ev):
        dup = False
        for j, (_, b) in enumerate(ev):
            if i == j or a is None or b is None or len(a) >= len(b):
                continue
            if (abs(a[0, 0] - b[0, 0]) < 0.01 and abs(a[0, 1] - b[0, 1]) < 0.01
                    and a[:, 0].min() >= b[:, 0].min() - 0.01
                    and a[:, 0].max() <= b[:, 0].max() + 0.01):
                dup = True
                break
        if dup:
            continue
        for prev in keep:
            b = prev["pts"]
            if (abs(a[0, 0] - b[0, 0]) < 0.15 and abs(a[0, 1] - b[0, 1]) < 0.15
                    and abs(a[-1, 0] - b[-1, 0]) < 0.15
                    and abs(a[-1, 1] - b[-1, 1]) < 0.15):
                dup = True
                break
        if not dup:
            keep.append(d)
    return keep


def monotonic_xy(pts, mx, cx, my, cy):
    """Device points -> (x_data, y_data), sorted by x, duplicate x removed."""
    x = mx * pts[:, 0] + cx
    y = my * pts[:, 1] + cy
    o = np.argsort(x, kind="stable")
    x, y = x[o], y[o]
    keep = np.concatenate([[True], np.diff(x) > 1e-9])
    return x[keep], y[keep]


def sample(x, y, grid, hold=True):
    """Interpolate onto grid; hold terminal values flat outside support (Kodak
    files do the same) unless hold=False, in which case emit None outside."""
    out = np.interp(grid, x, y, left=y[0] if hold else np.nan,
                    right=y[-1] if hold else np.nan)
    return out


def overlay(page, maps, curves_json_path, out, dpi=200):
    """Plot the digitized JSON back onto the printed chart through the axis maps.

    The single strongest validation available: if the curves land on the printed
    ink, then frame detection, axis origin, axis STEP, curve assignment and
    Bezier evaluation are ALL correct simultaneously. A residual can be clean
    while every one of those is wrong together (evenly spaced gridlines fit any
    origin and any step with zero error) -- this cannot.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    s = dpi / 72.0
    pix = page.get_pixmap(dpi=dpi)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    c = json.loads(Path(curves_json_path).read_text())
    fig, ax = plt.subplots(figsize=(11, 13))
    ax.imshow(img)
    ax.axis("off")

    def to_px(xd, yd, mx, cx, my, cy):
        return ((xd - cx) / mx * s, (PAGE_H - (yd - cy) / my) * s)

    cxm, cxc, cym, cyc, sxm, sxc, sym, syc = maps
    lx = np.array(c["char_curves"]["log_exposure"], float)
    for k, col in zip(("B", "G", "R"), ("#0066ff", "#00aa33", "#ff2200")):
        d = np.array(c["char_curves"]["statusM_density"][k], float)
        ax.plot(*to_px(lx, d, cxm, cxc, cym, cyc), col, lw=2.2, alpha=0.75)
    w = np.array(c["spectral"]["wavelength_nm"], float)
    for key, col in (("midscale_neutral", "#cc00cc"), ("dmin", "#ff8800")):
        d = np.array(c["spectral"][key], float)
        ax.plot(*to_px(w, d, sxm, sxc, sym, syc), col, lw=2.2, alpha=0.75)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(out, dpi=90, bbox_inches="tight")
    print("wrote overlay %s -- the digitized curves must sit ON the printed ink" % out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stock", choices=sorted(SHEETS), default="fujifilm400",
                    help="Fuji-template stock to digitize (default: fujifilm400)")
    ap.add_argument("--overlay", action="store_true",
                    help="also write builds/_forensics/<Prefix>_overlay.png, "
                         "the digitized curves replotted on the printed chart")
    args = ap.parse_args()

    global PAGE_H

    STOCK = STOCKS[args.stock]
    SHEET = SHEETS[args.stock]
    PDF = ROOT / "film_datasheet" / STOCK["pdf_filename"]
    PAGE = STOCK["page"]
    # The JP sheets are A4; every device coordinate below is bottom-up, so the
    # pivot has to follow the sheet rather than sit as a module constant.
    PAGE_H = SHEET["PAGE_H"]
    PAGE_W = SHEET["PAGE_W"]
    CHAR_XGRID = SHEET["CHAR_XGRID"]
    CHAR_XVALS = SHEET["CHAR_XVALS"]
    CHAR_YGRID = SHEET["CHAR_YGRID"]
    CHAR_YVALS = SHEET["CHAR_YVALS"]
    CHAR_XLABELS = SHEET.get("CHAR_XLABELS")
    SPEC_XTICKS = SHEET["SPEC_XTICKS"]
    SPEC_YGRID = SHEET["SPEC_YGRID"]
    SPEC_YVALS = SHEET["SPEC_YVALS"]
    REGION_CHAR = SHEET["REGION_CHAR"]
    REGION_SPEC = SHEET["REGION_SPEC"]
    # Pro 400H harvests no sensitivity chart -- four curves, three-layer model.
    SENS_ABSENT = SHEET.get("sensitivity_absent", False)
    if not SENS_ABSENT:
        SENS_XTICKS = SHEET["SENS_XTICKS"]
        SENS_Y_ZERO = SHEET["SENS_Y_ZERO"]
        SENS_Y_ONE = SHEET["SENS_Y_ONE"]
        SENS_PT_PER_DECADE = SENS_Y_ONE - SENS_Y_ZERO
        REGION_SENS = SHEET["REGION_SENS"]

    if not PDF.exists():
        raise SystemExit("missing %s" % PDF)
    doc = fitz.open(PDF)
    page = doc[PAGE]
    if abs(page.rect.width - PAGE_W) > 0.5 or abs(page.rect.height - PAGE_H) > 0.5:
        raise SystemExit("unexpected page size %s; calibration constants are for "
                         "%gx%g" % (page.rect, PAGE_W, PAGE_H))
    drawings = [d for d in page.get_drawings() if d.get("color") is not None]
    curves = [d for d in drawings
              if any(it[0] == "c" for it in d["items"])]

    # ---------------- axis maps ----------------
    cxm, cxc, cx_rms = affine(list(zip(CHAR_XGRID, CHAR_XVALS)))
    cym, cyc, cy_rms = affine(list(zip(CHAR_YGRID, CHAR_YVALS)))
    sxm, sxc, sx_rms = affine(SPEC_XTICKS)
    sym, syc, sy_rms = affine(list(zip(SPEC_YGRID, SPEC_YVALS)))
    if not SENS_ABSENT:
        nxm, nxc, nx_rms = affine(SENS_XTICKS)
        nym = 1.0 / SENS_PT_PER_DECADE
        nyc = -SENS_Y_ZERO / SENS_PT_PER_DECADE

    # label cross-check on the characteristic x axis (labels sit on every 2nd
    # gridline, so this is an independent statement of the 0.5 step)
    if SHEET.get("char_x_labels_unreliable"):
        print("NOTE %s: %s" % (
            SHEET["sheet_name"],
            SHEET.get("labels_unreliable_note",
                      "x-axis label cross-check SKIPPED (minus signs are not "
                      "extractable on this datasheet); x calibration rests on "
                      "the gridline positions plus the rendered-page reading of "
                      "the printed labels alone.")))
        lx_m = lx_c = lx_rms = None
    else:
        lx_m, lx_c, lx_rms = affine(CHAR_XLABELS)
        if abs(lx_m - cxm) > 0.002 or lx_rms > 0.02:
            raise SystemExit("characteristic x-axis label cross-check failed: "
                             "gridline slope %.6f vs label slope %.6f (rms %.4f)"
                             % (cxm, lx_m, lx_rms))

    # ---------------- 15. characteristic ----------------
    char = drop_duplicate_subpaths(chart_runs(curves, REGION_CHAR))
    if len(char) != 3:
        raise SystemExit("characteristic chart: expected 3 curve paths, found %d"
                         % len(char))
    # B > G > R in density: order by mean y (bottom-up device y rises with density)
    char_pts = [r["pts"] for r in char]
    char_pts.sort(key=lambda a: -a[:, 1].mean())
    names = ["B", "G", "R"]
    ch = {}
    for nm, pts in zip(names, char_pts):
        ch[nm] = monotonic_xy(pts, cxm, cxc, cym, cyc)

    lo = max(ch[n][0][0] for n in names)
    hi = min(ch[n][0][-1] for n in names)
    grid_lo = np.ceil(lo / 0.02) * 0.02
    grid_hi = np.floor(hi / 0.02) * 0.02
    logH = np.round(np.arange(grid_lo, grid_hi + 1e-9, 0.02), 2)
    dens = {n: np.round(sample(*ch[n], logH), 4) for n in names}
    for a, b in (("B", "G"), ("G", "R")):
        if not np.all(dens[a] >= dens[b] - 1e-6):
            raise SystemExit("characteristic curve order violated: %s !>= %s "
                             "over the common support" % (a, b))

    # ---------------- 16. spectral dye density ----------------
    spec = drop_duplicate_subpaths(chart_runs(curves, REGION_SPEC))
    if len(spec) != 2:
        raise SystemExit("spectral dye-density chart: expected 2 curve paths, "
                         "found %d" % len(spec))
    spec_pts = [r["pts"] for r in spec]
    # Kodak-style convention, printed in Japanese on the JP sheets as 中間濃度
    # (mid-scale) and 最小濃度 (minimum). Mid-scale is the UPPER curve on every
    # sheet, so the higher mean device y is the mid-scale neutral.
    spec_pts.sort(key=lambda a: -a[:, 1].mean())          # midscale above dmin
    mid_x, mid_y = monotonic_xy(spec_pts[0], sxm, sxc, sym, syc)
    dmn_x, dmn_y = monotonic_xy(spec_pts[1], sxm, sxc, sym, syc)
    wl = np.arange(400, 701, 1)
    midscale = np.round(sample(mid_x, mid_y, wl), 4)
    dmin = np.round(sample(dmn_x, dmn_y, wl), 4)
    if not np.all(midscale >= dmin - 1e-6):
        raise SystemExit("midscale neutral falls below D-min somewhere; curve "
                         "assignment is wrong")

    # ---------------- 17. spectral sensitivity ----------------
    # Skipped entirely on sheets flagged sensitivity_absent (Pro 400H: the chart
    # has a FOURTH, dashed "Cyan Sensitive Layer" curve between green and red,
    # and the classifier below assumes exactly three sorted by ascending peak).
    if SENS_ABSENT:
        layer_names, log_sens, sens_audit, swl = [], {}, {}, None
    else:
        sens = drop_duplicate_subpaths(chart_runs(curves, REGION_SENS))
        if len(sens) != 3:
            raise SystemExit("spectral-sensitivity chart: expected 3 curve paths, "
                             "found %d" % len(sens))
        sens_xy = []
        for d in sens:
            x, y = monotonic_xy(d["pts"], nxm, nxc, nym, nyc)
            sens_xy.append((x, y))
        sens_xy.sort(key=lambda t: t[0][int(np.argmax(t[1]))])   # by peak wavelength
        layer_names = ["yellow", "magenta", "cyan"]
        swl_lo = int(np.floor(min(x[0] for x, _ in sens_xy)))
        swl_hi = int(np.ceil(max(x[-1] for x, _ in sens_xy)))
        swl = np.arange(swl_lo, swl_hi + 1)
        log_sens, sens_audit = {}, {}
        for nm, (x, y) in zip(layer_names, sens_xy):
            v = sample(x, y, swl, hold=False)
            v[(swl < x[0]) | (swl > x[-1])] = np.nan
            log_sens[nm] = [None if np.isnan(t) else round(float(t), 4) for t in v]
            pk = int(np.argmax(y))
            sens_audit[nm] = {
                "support_nm": [round(float(x[0]), 2), round(float(x[-1]), 2)],
                "peak_wavelength_nm": round(float(x[pk]), 2),
                "peak_log_sensitivity_relative": round(float(y[pk]), 4),
                "n_path_points": int(len(x)),
            }

    # ================= write =================
    src = ("%s Color Negative Film datasheet, Ref. No. %s, page %d "
           "vector charts, digitized from the embedded paths by "
           "engine/c41/%s"
           % (SHEET["sheet_name"], STOCK["datasheet_code"], PAGE + 1,
              SHEET["emitted_by"]))

    # The axis EXTENTS are formatted from the per-sheet value lists rather than
    # hardcoded: Pro 400H's density axis is 0.0..3.5 over 8, not 0.0..4.0 over 9.
    char_basis = ("gridlines at a HALF-decade step on both axes "
                  "(%.1f..%+.1f logH over %d; %.1f..%.1f D over %d); "
                  % (CHAR_XVALS[0], CHAR_XVALS[-1], len(CHAR_XVALS),
                     CHAR_YVALS[0], CHAR_YVALS[-1], len(CHAR_YVALS)))
    if SHEET.get("char_x_labels_unreliable"):
        char_basis += SHEET.get(
            "labels_unreliable_basis",
            "the printed x labels lose their minus signs in extraction "
            "on this sheet, so the label cross-check is NOT available "
            "and the x origin rests on the gridline positions plus a "
            "rendered-page reading of the labels")
    else:
        char_basis += ("printed labels appear on every 2nd x gridline "
                       "and are used as an independent cross-check")

    curves_json = {
        "source": src,
        "char_curves": {
            "log_exposure": [round(float(v), 2) for v in logH],
            "log_exposure_units": "log lux-seconds",
            "statusM_density": {n: [float(v) for v in dens[n]] for n in names},
            "curve_order_note": "at any exposure, top->bottom on the plot = B, G, R",
            "measurement_note": ("Exposure: Daylight, 1/125 sec.; Process: CN-16; "
                                 "Densitometry: Status M"),
        },
        "spectral": {
            "wavelength_nm": [int(v) for v in wl],
            "midscale_neutral": [float(v) for v in midscale],
            "dmin": [float(v) for v in dmin],
            "measurement_note": ("Typical densities for a mid-scale neutral subject "
                                 "and for D-min; Densitometry: Status M"),
        },
        "digitization_audit": {
            "characteristic_curves": {
                "calibration_basis": char_basis,
                "x_axis": {
                    "device_to_data": "logH = %.6f*x_px + %.6f" % (cxm, cxc),
                    "gridline_ticks": CHAR_XGRID,
                    "gridline_step_data": 0.5,
                    "gridline_fit_rms_data": round(cx_rms, 6),
                    "label_fit": (
                        SHEET.get(
                            "labels_unreliable_label_fit",
                            "SKIPPED: the printed minus signs are not extractable on "
                            "this sheet ('3.0 2.0 1.0 0.0 1.0' for -3.0 -2.0 -1.0 0.0 "
                            "+1.0), the same fault documented for Gold 200")
                        if lx_m is None else
                        "logH = %.6f*x_px + %.6f (rms %.4f)" % (lx_m, lx_c, lx_rms)),
                },
                "y_axis": {
                    "device_to_data": "densityM = %.6f*y_px + %.6f" % (cym, cyc),
                    "gridline_ticks": CHAR_YGRID,
                    "gridline_step_data": 0.5,
                    "gridline_fit_rms_data": round(cy_rms, 6),
                },
                "curve_representation": "cubic Bezier paths, sampled parametrically",
                "endpoints": {
                    n: {"logH_range": [round(float(ch[n][0][0]), 4),
                                       round(float(ch[n][0][-1]), 4)],
                        "density_range": [round(float(ch[n][1].min()), 4),
                                          round(float(ch[n][1].max()), 4)],
                        "n_bezier_segments": char[i]["n_cubic"]}
                    for i, n in enumerate(names)
                },
            },
            "spectral_dye_density": {
                "calibration_basis": SHEET.get(
                    "spec_calibration_basis",
                    "four LABELLED wavelength ticks only -- the plot "
                    "box is wider than the labelled range (frame edges "
                    "~384 and ~719 nm), so frame-derived wavelengths "
                    "would be ~16 nm out at each end"),
                "x_axis": {
                    "device_to_data": "wavelength_nm = %.6f*x_px + %.6f" % (sxm, sxc),
                    "label_ticks": [t[0] for t in SPEC_XTICKS],
                    "fit_rms_data": round(sx_rms, 6),
                },
                "y_axis": {
                    "device_to_data": "density = %.6f*y_px + %.6f" % (sym, syc),
                    "gridline_ticks": SPEC_YGRID,
                    "gridline_step_data": 0.5,
                    "fit_rms_data": round(sy_rms, 6),
                },
                "endpoints": {
                    "midscale_neutral": {
                        "wavelength_range_nm": [round(float(mid_x[0]), 2),
                                                round(float(mid_x[-1]), 2)],
                        "density_range": [round(float(mid_y.min()), 4),
                                          round(float(mid_y.max()), 4)]},
                    "dmin": {
                        "wavelength_range_nm": [round(float(dmn_x[0]), 2),
                                                round(float(dmn_x[-1]), 2)],
                        "density_range": [round(float(dmn_y.min()), 4),
                                          round(float(dmn_y.max()), 4)]},
                },
            },
        },
    }

    if SHEET.get("axis_labels_unreliable"):
        curves_json["digitization_audit"]["axis_label_cross_check"] = (
            "UNAVAILABLE ON EVERY AXIS OF BOTH CHARTS. This datasheet carries no "
            "extractable numeric labels anywhere -- datasheet_forensics.py "
            "reports 'no numeric labels found' on every axis of every frame -- "
            "so neither the characteristic nor the dye-density calibration has "
            "any independent numeric confirmation. All four axis assignments "
            "rest on the gridline positions plus a 300 dpi rendered-page reading "
            "of the printed labels. The datasheet_overlay.py ink-hit test is the "
            "ONLY validator this stock has; treat a failure there as fatal.")
    if SHEET.get("sensitivity_absent"):
        curves_json["digitization_audit"]["spectral_sensitivity"] = (
            "NOT DIGITIZED, deliberately. This sheet's spectral-sensitivity "
            "chart carries FOUR curves -- a dashed 'Cyan Sensitive Layer' "
            "between the green and red layers -- and every digitizer here "
            "classifies exactly three layers by ascending peak wavelength. How a "
            "fourth sensitivity layer should feed a 3-channel exposure model is "
            "an unresolved modelling question, so no "
            "%s_spectral_sensitivity.json is emitted and this stock is excluded "
            "from c41_scene_engine.py by design." % STOCK["file_prefix"])

    sens_json = None if SENS_ABSENT else {
        "source": src.replace("vector charts", "chart 17, spectral-sensitivity"),
        "measurement_note": ("Process: CN-16; Densitometry: Status M; "
                             "Density: 1.0 Above D-min"),
        "log_sensitivity_origin": SENS_ORIGIN_NOTE,
        "wavelength_nm": [int(v) for v in swl],
        "wavelength_note": ("1 nm grid over the union support of the three layers; "
                            "each layer is null (JSON null) outside its own support"),
        "log_sensitivity": log_sens,
        "digitization_audit": {
            "calibration_basis": ("x from four labelled wavelength ticks (frame edges "
                                  "are NOT ticks); y from the 1.0-decade scale bar "
                                  "only -- there is no absolute origin on this chart"),
            "x_axis": {
                "device_to_data": "wavelength_nm = %.6f*x_px + %.6f" % (nxm, nxc),
                "label_ticks": [t[0] for t in SENS_XTICKS],
                "fit_rms_data": round(nx_rms, 6),
            },
            "y_axis": {
                "device_to_data": "log_sensitivity_relative = %.6f*y_px + %.6f" % (nym, nyc),
                "scale_bar_pt_per_decade": round(SENS_PT_PER_DECADE, 3),
                "reference_marks_device_y": [SENS_Y_ZERO, SENS_Y_ONE],
            },
            "curve_classification": "by peak wavelength ascending (yellow<magenta<cyan)",
            "curve_representation": "cubic Bezier paths, sampled parametrically",
            "layers": sens_audit,
        },
    }

    p1 = DATA / "films" / STOCK["curves_json"]
    p1.write_text(json.dumps(curves_json, indent=2) + "\n")
    p2 = None
    if not SENS_ABSENT:
        p2 = DATA / "films" / STOCK["sensitivity_json"]
        p2.write_text(json.dumps(sens_json, indent=2) + "\n")

    # ================= self-report =================
    print("=== %s (%s), page %d ==="
          % (SHEET["sheet_name"], STOCK["datasheet_code"], PAGE + 1))
    if SENS_ABSENT:
        print("axis fits (RMS in data units): char x %.2e  char y %.2e  "
              "spec x %.2e  spec y %.2e  sens x n/a (chart not digitized)"
              % (cx_rms, cy_rms, sx_rms, sy_rms))
    else:
        print("axis fits (RMS in data units): char x %.2e  char y %.2e  spec x %.2e  "
              "spec y %.2e  sens x %.2e" % (cx_rms, cy_rms, sx_rms, sy_rms, nx_rms))
    if lx_m is None:
        print("char x label cross-check: SKIPPED (%s)"
              % ("no numeric labels are extractable anywhere on this sheet"
                 if SHEET.get("axis_labels_unreliable")
                 else "minus signs not extractable"))
    else:
        print("char x label cross-check: slope %.6f vs gridline %.6f (rms %.4f) OK"
              % (lx_m, cxm, lx_rms))
    print("characteristic: logH %.2f..%.2f, %d samples @0.02" % (logH[0], logH[-1], len(logH)))
    for n in names:
        i0 = int(np.argmin(np.abs(logH + 3.0)))
        i1 = int(np.argmin(np.abs(logH - 0.0)))
        print("  %s: D(logH=-3.0)=%.3f  D(logH=0.0)=%.3f  range %.3f..%.3f  (%d Bezier segs)"
              % (n, dens[n][i0], dens[n][i1], dens[n].min(), dens[n].max(),
                 char[names.index(n)]["n_cubic"]))
    print("spectral dye density (Status M, midscale neutral and D-min):")
    for w in (400, 450, 500, 550, 600, 650, 700):
        j = int(np.where(wl == w)[0][0])
        print("  %d nm: midscale %.4f   dmin %.4f   aggregate %.4f"
              % (w, midscale[j], dmin[j], midscale[j] - dmin[j]))
    if SENS_ABSENT:
        print("spectral sensitivity: NOT DIGITIZED, deliberately -- this chart "
              "has FOUR curves (a dashed 'Cyan Sensitive Layer' between green "
              "and red) and every classifier here assumes exactly three, by "
              "ascending peak. How a fourth layer feeds a 3-channel exposure "
              "model is unresolved, so no %s is written and this stock is not "
              "registered in c41_scene_engine.py."
              % STOCK.get("sensitivity_json",
                          "%s_spectral_sensitivity.json" % STOCK["file_prefix"]))
    else:
        print("spectral sensitivity (RELATIVE log axis), scale bar %.2f pt/decade "
              "between reference marks y=%.2f and y=%.2f:"
              % (SENS_PT_PER_DECADE, SENS_Y_ZERO, SENS_Y_ONE))
        for n in layer_names:
            a = sens_audit[n]
            print("  %-8s support %.1f-%.1f nm   peak %.1f nm" %
                  (n, a["support_nm"][0], a["support_nm"][1], a["peak_wavelength_nm"]))
        print("CAVEAT: %s" % SENS_ORIGIN_NOTE)
    print("wrote %s" % p1.relative_to(ROOT))
    if p2 is not None:
        print("wrote %s" % p2.relative_to(ROOT))
    if args.overlay:
        overlay(page, (cxm, cxc, cym, cyc, sxm, sxc, sym, syc), p1,
                ROOT / "builds" / "_forensics"
                / ("%s_overlay.png" % STOCK["file_prefix"]))


if __name__ == "__main__":
    main()
