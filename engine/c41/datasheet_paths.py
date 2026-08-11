#!/usr/bin/env python3
"""Operator-level dump of a datasheet page's vector paths. Read-only.

Step 0c of the digitization routine, next to datasheet_forensics.py (which
reads the AXES) and datasheet_render.py (which lets you LOOK at the chart).
This one reads the CURVES, and it exists for one reason:

  pdfminer flattens a path. LTCurve.pts is a bare list of points with the
  operators thrown away, so a cubic Bezier CONTROL point -- which is NOT on
  the curve, and can sit far outside the ink -- is indistinguishable from a
  sampled vertex. Read as data it puts a phantom peak in the digitized
  spectrum. That is not hypothetical; it happened on the Fujifilm 400 sheet.

PyMuPDF's Page.get_drawings() keeps the operator sequence -- 'l' (line to),
'c' (cubic Bezier), 're' (rectangle), 'qu' (quad) -- so the ambiguity simply
does not arise. A path reported as {'c': 10} is ten cubic segments, i.e. ten
on-curve endpoints and twenty control points, and the digitizer must EVALUATE
the Beziers rather than plot their points.

What to look for:
  * a chart curve is typically a 'c'-only path with a handful of segments;
  * a frame is 're', or 'l'-only with 4-5 items, or a closed 'c' rectangle;
  * gridlines are one-item 'l' paths, below --min-size and hidden by default.

Bboxes are printed in BOTH conventions. PyMuPDF is top-down (y grows
downward from the top edge); pdfminer and datasheet_forensics.py are
bottom-up. --region is given BOTTOM-UP so it can be pasted straight from a
forensics dump.

Run:
  python3 engine/c41/datasheet_paths.py "film_datasheet/Fujifilm 400.pdf" --page 5
  python3 engine/c41/datasheet_paths.py "film_datasheet/Ultramax 400.pdf" --page 3
  python3 engine/c41/datasheet_paths.py <pdf> --page 5 --min-size 10 \
      --region 55,240,293,419
"""
import argparse
from collections import Counter
from pathlib import Path

try:
    import fitz                                  # PyMuPDF
except ImportError:                              # pragma: no cover
    raise SystemExit("datasheet_paths.py needs PyMuPDF: pip install pymupdf")

FULL_DUMP_MAX_ITEMS = 12     # above this, control points are noise not evidence


def fmt_colour(c):
    if c is None:
        return "none"
    return "(" + ", ".join("%.3f" % v for v in c) + ")"


def fmt_point(p):
    return "(%.2f, %.2f)" % (p.x, p.y)


def fmt_item(it):
    """One path item as 'op  pt pt ...', with rects/quads spelled out."""
    op = it[0]
    if op == "re":
        r = it[1]
        return ("re  x0 %.2f y0 %.2f x1 %.2f y1 %.2f  (%.2f x %.2f)"
                % (r.x0, r.y0, r.x1, r.y1, r.width, r.height))
    if op == "qu":
        q = it[1]
        return "qu  " + " ".join(fmt_point(p) for p in
                                 (q.ul, q.ur, q.lr, q.ll))
    return "%-3s " % op + " ".join(fmt_point(p) for p in it[1:])


def contained(rect, region):
    x0, y0, x1, y1 = region
    return (rect[0] >= x0 - 1e-6 and rect[1] >= y0 - 1e-6
            and rect[2] <= x1 + 1e-6 and rect[3] <= y1 + 1e-6)


def dump_page(page, idx, npages, args):
    h = page.rect.height
    drawings = page.get_drawings()
    shown = 0

    print("=" * 78)
    print("PAGE index %d (printed page %d of %d)   page height %.2f pt"
          % (idx, idx + 1, npages, h))
    print("  %d drawings on the page; showing those whose bbox exceeds "
          "%.1f pt in BOTH dimensions%s"
          % (len(drawings), args.min_size,
             ", inside the --region" if args.region else ""))
    print("=" * 78)

    for n, d in enumerate(drawings):
        r = d["rect"]
        if r.width <= args.min_size or r.height <= args.min_size:
            continue
        bu = (r.x0, h - r.y1, r.x1, h - r.y0)      # top-down -> bottom-up
        if args.region and not contained(bu, args.region):
            continue
        shown += 1
        items = d["items"]
        ops = Counter(it[0] for it in items)

        print()
        print("  [%d] %d items  ops %s   type %r  closed %r"
              % (n, len(items), dict(sorted(ops.items())),
                 d.get("type"), d.get("closePath")))
        print("      bbox top-down  (PyMuPDF) : x0 %.2f y0 %.2f x1 %.2f y1 %.2f"
              "  (%.2f x %.2f pt)"
              % (r.x0, r.y0, r.x1, r.y1, r.width, r.height))
        print("      bbox bottom-up (pdfminer): x0 %.2f y0 %.2f x1 %.2f y1 %.2f"
              "  (y_bottomup = %.2f - y_topdown)"
              % (bu[0], bu[1], bu[2], bu[3], h))
        print("      stroke %s   fill %s   width %s"
              % (fmt_colour(d.get("color")), fmt_colour(d.get("fill")),
                 d.get("width")))
        if len(items) <= FULL_DUMP_MAX_ITEMS:
            for j, it in enumerate(items):
                print("        %2d. %s" % (j, fmt_item(it)))
        else:
            print("        (%d items -- control points suppressed above %d; "
                   "re-read the ops counts above)"
                  % (len(items), FULL_DUMP_MAX_ITEMS))

    print()
    print("  %d of %d drawings shown." % (shown, len(drawings)))
    print("  A 'c' is a CUBIC BEZIER: 3 points per item, only the LAST is on "
          "the curve.")
    print("  Evaluate them. Do not plot the control points as data.")


def main():
    ap = argparse.ArgumentParser(
        description="Read-only operator-level vector path dump of a datasheet "
                    "page. Distinguishes Bezier control points from on-curve "
                    "vertices, which pdfminer's flattened LTCurve.pts cannot.")
    ap.add_argument("pdf", help="path to the datasheet PDF")
    ap.add_argument("--page", type=int, default=None,
                    help="zero-based page index (default: dump every page)")
    ap.add_argument("--min-size", type=float, default=40.0,
                    help="skip drawings whose bbox is at or below this many "
                         "points in EITHER dimension (default 40). Lower it to "
                         "see gridlines and tick marks.")
    ap.add_argument("--region", default=None,
                    help="x0,y0,x1,y1 -- keep only drawings whose bbox lies "
                         "inside this rect, given in PDF BOTTOM-UP device "
                         "space, the same convention datasheet_forensics.py "
                         "prints.")
    a = ap.parse_args()

    pdf = Path(a.pdf)
    if not pdf.exists():
        raise SystemExit("no such file: %s" % pdf)
    if a.region:
        a.region = tuple(float(v) for v in a.region.split(","))
        if len(a.region) != 4:
            raise SystemExit("--region needs exactly x0,y0,x1,y1")

    doc = fitz.open(pdf)
    pages = [a.page] if a.page is not None else range(doc.page_count)
    for i in pages:
        if not 0 <= i < doc.page_count:
            raise SystemExit("page index %d out of range (%d pages)"
                             % (i, doc.page_count))
        dump_page(doc[i], i, doc.page_count, a)

    print()
    print("This tool WRITES NOTHING. It is a read-only diagnostic.")


if __name__ == "__main__":
    main()
