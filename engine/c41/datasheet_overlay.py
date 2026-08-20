#!/usr/bin/env python3
"""Replot a digitized JSON back onto its own datasheet chart. Read-only-ish.

The closing step of the digitization routine, and the only check that validates
frame detection, axis ORIGIN, axis STEP and curve sampling SIMULTANEOUSLY.
Everything else in the pipeline can be clean while all of those are wrong
together:

  * Evenly spaced gridlines fit ANY origin and ANY step with ZERO residual, so a
    good axis fit proves nothing about what the ticks mean. Portra 160's
    sensitivity axis (-1.0..3.0 read as 0.0..4.0) and Fujifilm 400's half-decade
    characteristic axes (read as full decades) are both invisible to residuals.
  * A label cross-check catches most of that -- but Gold 200's x labels lose
    their minus signs in text extraction ('3.02.01.00.01.0'), so its
    characteristic x-axis carries no automated cross-check at all and rests on
    gridline COUNT alone.
  * Curve-to-channel assignment (which path is B, G, R) is a heuristic on
    vertical order; a swap keeps every residual clean.

If the replotted curve lands on the printed ink, the AXIS-side items above are
right at once.

CURVE ASSIGNMENT IS THE ONE THING THIS CHECK CANNOT SEE, and nothing else
guards it. ink_hit() below asks whether a replotted point is near ANY dark
pixel, so permuting the channel labels moves no plotted coordinate and every
curve still lands on ink: measured, a B<->R swap on Portra 400, Ektar 100 and
Gold 200 scores 100% exactly as the truth does, while a 0.10 D offset drops to
0%. The check is live for geometry and blind to identity.

Nor is there a cheap signal to add. Colour would settle it, but only Fujifilm
200/400 and Provia 100F print these charts in colour; the other nine sheets
here are pure black ink (measured chromatic fraction 0.000). Stroke style would
settle it too, but every chart curve on the Kodak sheets is solid with a near
identical width and colour, so PyMuPDF's dash, width and colour fields do not
separate them. Assignment therefore rests on vertical order alone, and the
place to catch an error is step 2 of the routine -- LOOK at the rendered chart
-- not here.

This works off the JSON's own `digitization_audit.*.device_to_data` strings, so
it needs no cooperation from the digitizer that produced them -- which is what
lets it re-check stocks digitized long before this check existed.

Run:
  python3 engine/c41/datasheet_overlay.py --stock portra400
  python3 engine/c41/datasheet_overlay.py --all
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

try:
    import fitz                                  # PyMuPDF
except ImportError:                              # pragma: no cover
    raise SystemExit("datasheet_overlay.py needs PyMuPDF: pip install pymupdf")

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "films"
OUTDIR = ROOT / "builds" / "_forensics"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from portra_stocks import STOCKS                 # noqa: E402

_AFFINE = re.compile(r"=\s*(-?[\d.eE+-]+)\s*\*\s*[xy]_px\s*\+\s*(-?[\d.eE+-]+)")


def affine_of(block):
    """(slope, intercept) parsed from a `device_to_data` string, or None."""
    s = block.get("device_to_data") if isinstance(block, dict) else None
    if not s:
        return None
    m = _AFFINE.search(s)
    return (float(m.group(1)), float(m.group(2))) if m else None


def inv(v, sl_ic):
    """data value -> device pixel (bottom-up), inverting data = slope*px + ic."""
    sl, ic = sl_ic
    return (np.asarray(v, float) - ic) / sl


def ink_hit(img, px, py, radius=2, thresh=170):
    """Fraction of curve samples landing within `radius` px of dark ink.

    The visual overlay made objective. Rasterize the page, walk the replotted
    curve, and ask whether the printed line is actually there. A wrong axis
    origin or a wrong axis step moves the curve OFF the ink while leaving every
    numerical residual untouched, so this is a check no fit statistic can
    substitute for. A SWAPPED CHANNEL does not move it: this function tests
    membership against the union of all dark pixels and never sees which curve
    it landed on. See the module docstring.

    Charts are line art on white, so "ink" is simply a dark pixel. The radius
    absorbs line width and rasterization; it is far smaller than any of the
    errors this is meant to catch (Portra 160's sensitivity origin error was a
    full decade, ~46 px at 170 dpi).

    Returns (on-ink, total finite samples, off-canvas samples). Off-canvas
    samples are counted in the total, so they depress the score.
    """
    g = img[:, :, :3].mean(2) if img.ndim == 3 and img.shape[2] >= 3 else img[:, :, 0]
    H, W = g.shape
    ok = tot = off = 0
    for x, y in zip(px, py):
        if not (np.isfinite(x) and np.isfinite(y)):
            continue
        tot += 1
        xi, yi = int(round(x)), int(round(y))
        # A point off the raster is the worst failure this tool exists to find
        # -- a curve mapped clean off its own chart -- so it counts as a MISS.
        # Skipping it instead let a wholly off-page curve score tot == 0 and
        # drop out of the summary entirely, which read as silence, not alarm.
        if not (0 <= xi < W and 0 <= yi < H):
            off += 1
            continue
        y0, y1 = max(0, yi - radius), min(H, yi + radius + 1)
        x0, x1 = max(0, xi - radius), min(W, xi + radius + 1)
        if g[y0:y1, x0:x1].min() < thresh:
            ok += 1
    return ok, tot, off


def overlay(stock, dpi=170):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    s = STOCKS[stock]
    cpath = DATA / s["curves_json"]
    if not cpath.exists():
        print("  %-12s SKIP (no curves JSON)" % stock)
        return None
    c = json.loads(cpath.read_text())
    aud = c.get("digitization_audit", {})

    pdf = ROOT / "film_datasheet" / s["pdf_filename"]
    doc = fitz.open(pdf)
    page = doc[s["page"]]
    H = page.rect.height
    scale = dpi / 72.0
    pix = page.get_pixmap(dpi=dpi)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)

    fig, ax = plt.subplots(figsize=(12, 14))
    ax.imshow(img)
    ax.axis("off")
    drawn = []

    scores = []

    def plot(xd, yd, xmap, ymap, colour, label=""):
        px = inv(xd, xmap) * scale
        py = (H - inv(yd, ymap)) * scale
        ax.plot(px, py, colour, lw=2.0, alpha=0.72)
        ok, tot, off = ink_hit(img, px, py)
        if tot:
            scores.append((label, 100.0 * ok / tot, tot, off))

    # ---- characteristic ----
    ch = aud.get("characteristic_curves", {})
    xm, ym = affine_of(ch.get("x_axis", {})), affine_of(ch.get("y_axis", {}))
    if xm and ym and "char_curves" in c:
        lx = np.array(c["char_curves"]["log_exposure"], float)
        for k, col in zip(("B", "G", "R"), ("#0066ff", "#00aa33", "#ff2200")):
            d = c["char_curves"]["statusM_density"].get(k)
            if d is None:
                continue
            d = np.array([np.nan if v is None else v for v in d], float)
            plot(lx, d, xm, ym, col, "char:%s" % k)
        drawn.append("characteristic")

    # ---- spectral dye density ----
    sp = aud.get("spectral_dye_density", {})
    xm, ym = affine_of(sp.get("x_axis", {})), affine_of(sp.get("y_axis", {}))
    if xm and ym and "spectral" in c:
        w = np.array(c["spectral"]["wavelength_nm"], float)
        for key, col in (("midscale_neutral", "#cc00cc"), ("dmin", "#ff8800")):
            plot(w, np.array(c["spectral"][key], float), xm, ym, col, "spec:%s" % key)
        drawn.append("spectral")

    # ---- spectral sensitivity (separate JSON, own audit) ----
    # Some stocks have none by design -- Pro 400H's sensitivity chart carries a
    # fourth, dashed "Cyan Sensitive Layer" curve that the three-layer model has
    # no place for, so it is not digitized. Those entries carry no
    # 'sensitivity_json' key at all and simply plot their two charts (5 curves).
    vname = s.get("sensitivity_json")
    vpath = DATA / vname if vname else None
    if vpath is not None and vpath.exists():
        v = json.loads(vpath.read_text())
        va = v.get("digitization_audit", {})
        xm, ym = affine_of(va.get("x_axis", {})), affine_of(va.get("y_axis", {}))
        if xm and ym:
            wl = np.array(v["wavelength_nm"], float)
            for lay, col in (("yellow", "#ccaa00"), ("magenta", "#cc00aa"),
                             ("cyan", "#00aacc")):
                d = v["log_sensitivity"].get(lay)
                if d is None:
                    continue
                d = np.array([np.nan if t is None else t for t in d], float)
                plot(wl, d, xm, ym, col, "sens:%s" % lay)
            drawn.append("sensitivity")

    OUTDIR.mkdir(parents=True, exist_ok=True)
    out = OUTDIR / ("%s_overlay.png" % s["file_prefix"])
    plt.tight_layout()
    plt.savefig(out, dpi=88, bbox_inches="tight")
    plt.close(fig)
    worst = min(scores, key=lambda s: s[1]) if scores else None
    print("  %-12s %-26s ink-hit min %s  mean %5.1f%%  (%d curves)"
          % (stock, out.name,
             ("%5.1f%% [%s]" % (worst[1], worst[0])) if worst else "   n/a",
             float(np.mean([s[1] for s in scores])) if scores else float("nan"),
             len(scores)))
    for lab, pct, n, off in scores:
        if pct < 90.0:
            # Report the off-canvas count alongside the score: it separates a
            # curve sitting slightly beside its ink from one mapped off the page.
            print("       !! %-18s only %.1f%% of %d samples on ink"
                  "%s -- INSPECT"
                  % (lab, pct, n,
                     (" (%d off canvas)" % off) if off else ""))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stock", choices=sorted(STOCKS))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dpi", type=int, default=170)
    a = ap.parse_args()
    todo = sorted(STOCKS) if (a.all or not a.stock) else [a.stock]
    print("replotting digitized JSON onto the printed charts:")
    for k in todo:
        overlay(k, a.dpi)
    print("\nInspect each: every coloured curve must sit ON the printed ink.")
    print("A curve that is parallel-but-offset means a wrong axis ORIGIN;")
    print("one that diverges linearly means a wrong axis STEP; a pair that is")
    print("swapped means a curve-assignment error. None of the three moves a residual.")


if __name__ == "__main__":
    main()
