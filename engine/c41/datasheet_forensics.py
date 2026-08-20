#!/usr/bin/env python3
"""Read-only forensic dump of a film datasheet's vector chart page.

    python3 engine/c41/datasheet_forensics.py <pdf-path> [--page N]

MANDATORY before adding a stock to portra_stocks.py. This tool writes nothing;
it only reports what is actually on the page, so that every number the
digitizers infer can be checked against something printed.

Why it exists: three stocks have now produced three DIFFERENT silent failures,
and not one of them raised an error -- each yielded plausible WRONG NUMBERS,
because tick VALUES are inferred from tick COUNT.

  * Portra 400  -- chart frame drawn as four long LTLines. The baseline.
  * Portra 160  -- every frame is ONE stroked LTCurve rectangle closing with a
                   bare ('h',), so only four vertices are coordinate-bearing and
                   an LTLine-only frame detector sees nothing. Its
                   log-sensitivity axis also runs -1.0..3.0 where Portra 400's
                   runs 0.0..4.0: same five gridlines, every value 1.0 out.
  * Ektar 100   -- its CHARACTERISTIC chart x-axis runs -3.0..+2.0 where both
                   Portras run -4.0..+1.0: same six gridlines, every value one
                   decade out. Its charts also sit ~6 pt lower on the page, so
                   absolute device-space search bands miss entirely.

So: read the FRAME section to see how each frame is drawn, read the GRIDLINES
counts, and above all read the LABELS and IMPLIED AXIS sections -- the printed
labels are the only independent statement of what an axis actually reads. Then
put those origins in portra_stocks.py. Do not assume they match another stock.
"""
import argparse
import sys
from pathlib import Path

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTChar, LTCurve, LTLine

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
# NOTE: pdfchart imports numpy at module scope, so this diagnostic is no longer
# numpy-free. Its former hand-rolled affine_fit existed to keep it dependency-
# light; it now shares the digitizers' numpy lstsq fit, which is the point --
# what this tool reports must be what the digitizers will actually compute.
from engine.common.pdfchart import (   # noqa: E402
    affine_fit, label_ticks, walk,
)

try:                                     # run as a script from engine/c41
    from portra_stocks import (_rect_boxes_from_curves, _rect_boxes_from_lines,
                               frame_boxes)
except ImportError:                      # imported as engine.c41.datasheet_forensics
    from engine.c41.portra_stocks import (_rect_boxes_from_curves,
                                          _rect_boxes_from_lines, frame_boxes)

# Legacy hard-coded assumptions the digitizers used to make, kept here purely so
# that a new stock which disagrees with them gets flagged rather than silently
# inheriting them. Keyed by quadrant.
LEGACY_ORIGINS = {
    "top-left":     {"x": (-4.0, 1.0), "y": (0.0, 1.0)},   # characteristic
    "bottom-left":  {"x": (250.0, 50.0), "y": (0.0, 1.0)},  # spectral sensitivity
}

TOL = 0.05          # data units; the labels are exact round numbers
SKEW_PT = 3.5       # label-centroid skew allowance, device points


def median(vals):
    s = sorted(vals)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def quadrant(box, midx, midy):
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return ("top" if cy >= midy else "bottom") + "-" + ("left" if cx < midx
                                                        else "right")


def drawn_as(box, curve_boxes, line_boxes):
    key = tuple(round(v, 1) for v in box)
    inc = key in {tuple(round(v, 1) for v in b) for b in curve_boxes}
    inl = key in {tuple(round(v, 1) for v in b) for b in line_boxes}
    if inc and inl:
        return "BOTH stroked LTCurve rect AND four LTLines"
    if inc:
        return ("ONE stroked LTCurve rect (frame edges are NOT LTLines -- an "
                "LTLine-only gridline detector will come up two short per axis)")
    if inl:
        return "four long LTLines"
    return "unknown"


def gridlines(lines, box):
    """Interior gridlines/ticks per axis, plus the frame's own edges.

    The bands are DERIVED from the frame box, exactly as the digitizers now
    derive theirs -- that is the whole point, since absolute bands read off one
    stock miss on the next."""
    fx0, fy0, fx1, fy1 = box
    vx = {round(l.x0, 1) for l in lines
          if abs(l.x1 - l.x0) < 0.5 and fy0 - 2 < l.y0 < fy0 + 8
          and fx0 - 1.5 <= l.x0 <= fx1 + 1.5}
    hy = {round(l.y0, 1) for l in lines
          if abs(l.y1 - l.y0) < 0.5 and fx0 - 1.5 <= l.x0 <= fx0 + 1.5
          and fy0 - 5 < l.y0 < fy1 + 3}
    interior_x = sorted(v for v in vx
                        if abs(v - fx0) > 0.6 and abs(v - fx1) > 0.6)
    interior_y = sorted(v for v in hy
                        if abs(v - fy0) > 0.6 and abs(v - fy1) > 0.6)
    all_x = sorted(vx | {round(fx0, 1), round(fx1, 1)})
    all_y = sorted(hy | {round(fy0, 1), round(fy1, 1)})
    return interior_x, all_x, interior_y, all_y


def label_bands(box):
    """(x-label band, y-label band) as label_ticks() argument tuples.

    Derived from the frame box: x labels sit in a strip just below the bottom
    edge (above it is the frame, below it is the axis title); y labels sit in a
    strip just left of the left edge (further left is the rotated axis title)."""
    fx0, fy0, fx1, fy1 = box
    return ((fx0 - 45, fx1 + 40, fy0 - 14, fy0 - 3),
            (fy0 - 6, fy1 + 6, fx0 - 26, fx0 - 0.5))


def describe_axis(name, ticks, labels, warnings, legacy):
    """Print the implied origin/step/range for one axis and collect warnings."""
    print("      %s-axis" % name)
    print("        gridlines (%d): %s"
          % (len(ticks), ", ".join("%.2f" % t for t in ticks)))
    if labels:
        print("        labels    (%d): %s"
              % (len(labels), ", ".join("(%.2f, %s)" % (p, txt)
                                        for p, _, txt in labels)))
    else:
        print("        labels    (0): NONE FOUND in the derived search band")
        warnings.append("%s-axis: no numeric labels found -- nothing can "
                        "cross-check the count-inferred tick values" % name)
        return
    if len(labels) < 2:
        warnings.append("%s-axis: only one numeric label; cannot imply a step"
                        % name)
        return

    slope, intercept, _fit_rms = affine_fit([(p, v) for p, v, _ in labels])
    steps = [labels[i + 1][1] - labels[i][1] for i in range(len(labels) - 1)]
    step = median(steps)
    origin = slope * ticks[0] + intercept if ticks else labels[0][1]
    top = slope * ticks[-1] + intercept if ticks else labels[-1][1]
    print("        label fit     : %s = %.6f*pos %+.6f" % (name, slope, intercept))
    print("        IMPLIED origin: %.4f  (value at the lowest gridline)" % origin)
    print("        IMPLIED step  : %.4f   IMPLIED range: %.4f .. %.4f"
          % (step, origin, top))
    print("        label count %d %s gridline count %d"
          % (len(labels), "==" if len(labels) == len(ticks) else "!=", len(ticks)))
    if len(labels) != len(ticks):
        warnings.append(
            "%s-axis: %d labels but %d gridlines -- a count-based assignment "
            "walks off the end or stops short" % (name, len(labels), len(ticks)))

    # What a count-based assignment would give, and whether the labels agree.
    if not ticks:
        return
    cnt_origin, cnt_step = legacy if legacy else (round(origin, 4), round(step, 4))
    allow = TOL + abs(slope) * SKEW_PT
    if legacy:
        print("        count-based assumption (as previously hard-coded): "
              "origin %.4f step %.4f -> range %.4f .. %.4f"
              % (cnt_origin, cnt_step, cnt_origin,
                 cnt_origin + cnt_step * (len(ticks) - 1)))
        if abs(cnt_origin - origin) > allow or abs(cnt_step - step) > allow:
            warnings.append(
                "%s-axis: LABELS SAY origin %.4f step %.4f, a count-based "
                "assignment would give origin %.4f step %.4f -- every value "
                "would be off by %+.4f. Put the label-derived origin in "
                "portra_stocks.py."
                % (name, origin, step, cnt_origin, cnt_step,
                   cnt_origin - origin))

    # Per-label residual against the gridline-count fit rebuilt from the labels'
    # own origin/step, which is the calibration the digitizers will actually use.
    if len(ticks) >= 2:
        g_slope = (step * (len(ticks) - 1)) / (ticks[-1] - ticks[0])
        g_int = origin - g_slope * ticks[0]
        offs = [(p, v, p * g_slope + g_int) for p, v, _ in labels]
        med = median([pred - v for _, v, pred in offs])
        print("        gridline-fit vs labels: median offset %+.4f, worst %+.4f "
              "(allowance %.4f incl. %.1f pt label-centroid skew)"
              % (med, max((pred - v for _, v, pred in offs),
                          key=abs, default=0.0), allow, SKEW_PT))
        for p, v, pred in offs:
            if abs((pred - v) - med) > allow:
                warnings.append(
                    "%s-axis: label at device %.2f reads %.4f but the gridline "
                    "fit predicts %.4f (offset %+.4f, %+.4f away from the "
                    "median). Either a gridline is missing or this label "
                    "mis-extracted -- check by eye."
                    % (name, p, v, pred, pred - v, (pred - v) - med))


def main():
    ap = argparse.ArgumentParser(
        description="Read-only forensic dump of a datasheet chart page. "
                    "Run this BEFORE registering a stock in portra_stocks.py.")
    ap.add_argument("pdf", help="path to the datasheet PDF")
    ap.add_argument("--page", type=int, default=None,
                    help="zero-based page index. Default: AUTO-DETECT the chart "
                         "page (the one with the most frame boxes). The four "
                         "Kodak sheets put their charts on index 3; Fujifilm 400 "
                         "puts them on index 5, and a fixed default reported "
                         "'NO FRAME BOXES FOUND' on the wrong page -- a false "
                         "alarm that looked like an unknown frame spelling.")
    ap.add_argument("--all-quadrants", action="store_true",
                    help="also warn on the bottom-right MTF quadrant, which no "
                         "digitizer harvests and whose log-scaled axes disagree "
                         "with a linear check by construction")
    args = ap.parse_args()

    path = Path(args.pdf)
    pages = list(extract_pages(str(path)))
    scan = None
    if args.page is None:
        scan = [(i, len(frame_boxes(list(walk(pg))))) for i, pg in enumerate(pages)]
        best = max(scan, key=lambda t: (t[1], -t[0]))
        page_idx, how = best[0], "AUTO-DETECTED"
    else:
        page_idx, how = args.page, "user-specified"
    if not 0 <= page_idx < len(pages):
        raise SystemExit("page index %d out of range (%d pages)"
                         % (page_idx, len(pages)))
    page = pages[page_idx]

    print("=" * 78)
    print("DATASHEET FORENSICS -- %s, page index %d (printed page %d) [%s]"
          % (path.name, page_idx, page_idx + 1, how))
    if scan is not None:
        print("  frame-box count per page: %s"
              % ", ".join("p%d:%d" % (i, n) for i, n in scan))
    print("=" * 78)
    print(__doc__.split("Why it exists:", 1)[1].strip())
    print("-" * 78)
    print("This tool WRITES NOTHING. It is a read-only diagnostic.")
    print()

    els = list(walk(page))
    chars = [e for e in els if isinstance(e, LTChar)]
    lines = [e for e in els if isinstance(e, LTLine)]
    curves = [e for e in els if isinstance(e, LTCurve)]

    x0, y0, x1, y1 = page.bbox
    midx, midy = (x0 + x1) / 2, (y0 + y1) / 2
    print("page bbox %.2f %.2f %.2f %.2f   (quadrant split at x=%.2f, y=%.2f)"
          % (x0, y0, x1, y1, midx, midy))
    print("elements: %d LTChar, %d LTLine, %d LTCurve (%d stroked)"
          % (len(chars), len(lines), len(curves),
             sum(1 for c in curves if c.stroke)))
    print()

    curve_boxes = _rect_boxes_from_curves(els, 80.0, 80.0, 1.0)
    line_boxes = _rect_boxes_from_lines(els, 80.0, 80.0, 1.0)
    boxes = frame_boxes(els)
    if not boxes:
        raise SystemExit(
            "NO FRAME BOXES FOUND. frame_boxes() knows two spellings -- four "
            "long LTLines, and one stroked axis-aligned LTCurve rectangle. This "
            "page apparently uses a third. Nothing downstream can work until "
            "frame_boxes() learns it.")

    boxes.sort(key=lambda b: (-(b[1] + b[3]) / 2, (b[0] + b[2]) / 2))
    all_warnings = []
    ignored_warnings = []

    print("### 1-5. FRAME BOXES (%d found via portra_stocks.frame_boxes())"
          % len(boxes))
    for i, b in enumerate(boxes, 1):
        q = quadrant(b, midx, midy)
        print()
        print("  [%d] %s quadrant" % (i, q.upper()))
        print("      device bbox: x0 %.2f  y0 %.2f  x1 %.2f  y1 %.2f  "
              "(%.2f x %.2f pt)" % (b[0], b[1], b[2], b[3],
                                    b[2] - b[0], b[3] - b[1]))
        print("      drawn as   : %s" % drawn_as(b, curve_boxes, line_boxes))

        ix, ax, iy, ay = gridlines(lines, b)
        print("      interior gridlines: %d vertical %s, %d horizontal %s"
              % (len(ix), ["%.2f" % v for v in ix],
                 len(iy), ["%.2f" % v for v in iy]))
        print("      with frame edges  : %d vertical, %d horizontal"
              % (len(ax), len(ay)))

        (xlo, xhi, xolo, xohi), (ylo, yhi, yolo, yohi) = label_bands(b)
        xl = label_ticks(chars, "x", xlo, xhi, xolo, xohi, with_text=True)
        yl = label_ticks(chars, "y", ylo, yhi, yolo, yohi, with_text=True)
        print("      label search bands (DERIVED from this frame box):")
        print("        x: x0 in (%.2f, %.2f), y-centre in (%.2f, %.2f)"
              % (xlo, xhi, xolo, xohi))
        print("        y: y-centre in (%.2f, %.2f), x0 in (%.2f, %.2f)"
              % (ylo, yhi, yolo, yohi))

        warnings = []
        legacy = LEGACY_ORIGINS.get(q, {})
        describe_axis("x", ax, xl, warnings, legacy.get("x"))
        describe_axis("y", ay, yl, warnings, legacy.get("y"))
        # The bottom-right quadrant is the MTF chart. No digitizer harvests it,
        # and BOTH its axes are logarithmic (1,2,5,10,20,50,200,600...), so a
        # linear label-vs-gridline comparison disagrees on essentially every
        # tick. Left in the main list it contributes ~20 warnings and buries the
        # one that matters -- on Ektar 100 it outnumbered the real characteristic
        # x-axis finding twenty to one. Segregate rather than delete: a frame
        # appearing here that ISN'T the log-scaled MTF chart is worth seeing.
        target = (all_warnings if (args.all_quadrants or q != "bottom-right")
                  else ignored_warnings)
        for w in warnings:
            target.append("[%d] %s quadrant %s" % (i, q, w))

    print()
    print("=" * 78)
    print("### 6. WARNINGS")
    print("=" * 78)
    if not all_warnings:
        print("None. Every axis's label-implied origin and step agree with what "
              "a count-based assignment would give, and the label and gridline")
        print("counts match. That is necessary, not sufficient -- still read the "
              "IMPLIED origin lines above and copy them into portra_stocks.py.")
    else:
        for w in all_warnings:
            print("  !! " + w)
        print()
        print("Each of these is a place where the tick VALUES inferred from the "
              "tick COUNT would be wrong while every residual stayed clean.")
    if ignored_warnings:
        print()
        print("  (%d further finding%s in the bottom-right MTF quadrant, which no "
              "digitizer harvests and whose axes are" % (len(ignored_warnings),
              "" if len(ignored_warnings) == 1 else "s"))
        print("   logarithmic, so a linear check disagrees by construction. "
              "Re-run with --all-quadrants to see them.)")
    print()
    print("Reminder: this must be run and read BEFORE adding a stock to "
          "portra_stocks.py. Nothing was written.")


if __name__ == "__main__":
    main()
