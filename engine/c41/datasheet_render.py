#!/usr/bin/env python3
"""Rasterize a datasheet page so a chart can be LOOKED AT. Read-only.

Step 0b of the digitization routine, alongside datasheet_forensics.py. Vector
path data alone is not enough to digitize a chart safely, and two real failures
on the Fujifilm 400 sheet made that concrete:

  * A cubic Bezier CONTROL point is not on the curve. Read as data it puts a
    phantom peak in the spectrum. pdfminer's flattened point list cannot tell the
    two apart; a picture can, instantly.
  * The Fuji dye-density chart turned out to use the SAME convention as Kodak's
    ("typical densities for a mid-scale neutral subject and for D-min", Status M)
    rather than the per-dye normalization Fuji uses elsewhere. That is written on
    the chart in words. No amount of geometry inspection would have recovered it.

So: render the page, read the axis titles and the fine print, THEN digitize.

Pair this with the overlay check at the other end (see fuji_digitize.py
--overlay): plot the digitized JSON back onto this raster through the axis
calibration. If the curves land on the printed ink, the whole chain -- frame
detection, axis origin, axis STEP, curve assignment, Bezier evaluation -- is
correct at once. That single picture is worth more than any residual.

Run:
  python3 engine/c41/datasheet_render.py "film_datasheet/Fujifilm 400.pdf"
  python3 engine/c41/datasheet_render.py "film_datasheet/Ultramax 400.pdf" --page 3 --dpi 200
  python3 engine/c41/datasheet_render.py <pdf> --page 5 --clip 55,240,293,419
"""
import argparse
from pathlib import Path

try:
    import fitz                                  # PyMuPDF
except ImportError:                              # pragma: no cover
    raise SystemExit("datasheet_render.py needs PyMuPDF: pip install pymupdf")

ROOT = Path(__file__).resolve().parents[2]
OUTDIR = ROOT / "builds" / "_forensics"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pdf", help="path to the datasheet PDF")
    ap.add_argument("--page", type=int, default=None,
                    help="zero-based page index (default: render every page)")
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--clip", default=None,
                    help="x0,y0,x1,y1 in PDF BOTTOM-UP device space -- the same "
                         "convention datasheet_forensics.py prints. PyMuPDF is "
                         "top-down internally; the flip is done here.")
    ap.add_argument("--out", default=None, help="output path (single page only)")
    a = ap.parse_args()

    pdf = Path(a.pdf)
    if not pdf.exists():
        raise SystemExit("no such file: %s" % pdf)
    doc = fitz.open(pdf)
    OUTDIR.mkdir(parents=True, exist_ok=True)

    pages = [a.page] if a.page is not None else range(doc.page_count)
    if a.out and a.page is None:
        raise SystemExit("--out needs a single --page")

    for i in pages:
        page = doc[i]
        clip = None
        if a.clip:
            x0, y0, x1, y1 = (float(v) for v in a.clip.split(","))
            h = page.rect.height
            clip = fitz.Rect(x0, h - y1, x1, h - y0)   # bottom-up -> top-down
        pix = page.get_pixmap(dpi=a.dpi, clip=clip)
        out = Path(a.out) if a.out else OUTDIR / ("%s_p%d.png" % (pdf.stem, i))
        pix.save(out)
        print("wrote %s  (%d x %d px, page %d of %d, %d dpi%s)"
              % (out, pix.width, pix.height, i, doc.page_count, a.dpi,
                 ", clipped" if clip else ""))
    print("Read the axis titles and the fine print before digitizing anything.")


if __name__ == "__main__":
    main()
