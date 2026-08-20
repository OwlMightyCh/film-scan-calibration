#!/usr/bin/env python3
"""Digitize the Sensitometric Curves of Kodak Vision3 500T (film_datasheet/V3 500T.pdf).

Unlike engine/c41/portra_digitize.py (vector LTCurve geometry) this datasheet's
figure is a RASTER image (page index 2, embedded image "Im1", 673x732 8-bit
DeviceRGB), so the three characteristic curves are recovered by darkness-based
column-by-column tracing rather than path flattening.

Axes (frame edges): top x-axis LOG EXPOSURE (lux-seconds) -4.0 (left) .. 1.0
(right); left y-axis Density 3.0 (top) .. 0.0 (bottom). Three solid black curves,
vertically ordered everywhere (no crossings): top->bottom = B, G, R. Densities are
absolute ECN-2/Status M INCLUDING base+mask. The plot area also carries a
legend block (upper-left) and B/G/R labels (right edge); those columns produce
!=3 clusters (or over-tall clusters) and are rejected by the tracer.
"""
import json
import datetime
from pathlib import Path
import numpy as np
import pdfplumber

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
PDF  = ROOT / "film_datasheet" / "V3 500T.pdf"
PAGE = 2
IMNAME = "Im1"
SRCSIZE = (673, 732)            # (width, height)

LOGH_LEFT, LOGH_RIGHT = -4.0, 1.0
DEN_TOP, DEN_BOTTOM = 3.0, 0.0
STOP_LOG = np.log10(2.0)                       # 0.30103 logH per camera stop
STOPS_ZERO_LOGH = LOGH_LEFT + 8 * STOP_LOG     # camera stop 0 (-8 at left edge)
DARK_THR = 110.0                               # luminance threshold for "on a curve"
GRID = np.round(np.arange(-3.9, 0.9 + 1e-9, 0.02), 2)


def longest_run(mask):
    """Length of the longest run of True values in a 1-D boolean array."""
    best = cur = 0
    for v in mask:
        cur = cur + 1 if v else 0
        if cur > best:
            best = cur
    return best


def runs(mask):
    """Return [(start, stop_exclusive)] for each run of True values."""
    out = []
    i = 0
    n = len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j < n and mask[j]:
                j += 1
            out.append((i, j))
            i = j
        else:
            i += 1
    return out


def smooth5(a):
    """5-point moving average that ignores NaN and preserves NaN-only gaps."""
    out = np.full_like(a, np.nan)
    for i in range(len(a)):
        lo, hi = max(0, i - 2), min(len(a), i + 3)
        w = a[lo:hi]
        w = w[~np.isnan(w)]
        if w.size:
            out[i] = w.mean()
    return out


def main():
    pdf = pdfplumber.open(str(PDF))
    page = pdf.pages[PAGE]
    im = [i for i in page.images if i.get("name") == IMNAME][0]
    W, H = SRCSIZE
    method = "raster trace"
    try:
        raw = im["stream"].get_data()
        img = np.frombuffer(raw[:H * W * 3], dtype=np.uint8).reshape(H, W, 3).astype(float)
    except Exception as e:                                          # pragma: no cover
        method = "raster trace (rendered crop fallback)"
        crop = page.crop((im["x0"], im["top"], im["x1"], im["bottom"]))
        img = np.asarray(crop.to_image(resolution=600).original).astype(float)[:, :, :3]
        H, W = img.shape[:2]
        print("WARN: stream decode failed (%s); used rendered crop %dx%d" % (e, W, H))

    lum = img.mean(2)
    dark = lum < DARK_THR

    # ---- locate plot frame: longest dark runs pick the axis-box edges ----
    col_run = np.array([longest_run(dark[:, c]) for c in range(W)])
    row_run = np.array([longest_run(dark[r, :]) for r in range(H)])
    vcand = np.where(col_run > 0.5 * H)[0]       # columns spanning most of the height
    hcand = np.where(row_run > 0.5 * W)[0]       # rows spanning most of the width
    xL, xR = int(vcand.min()), int(vcand.max())
    yT, yB = int(hcand.min()), int(hcand.max())
    frame_box = [xL, yT, xR, yB]

    # ---- calibration (frame-edge linear) ----
    def col_to_logH(c):
        return LOGH_LEFT + (c - xL) / (xR - xL) * (LOGH_RIGHT - LOGH_LEFT)

    def row_to_den(r):
        return DEN_TOP + (r - yT) / (yB - yT) * (DEN_BOTTOM - DEN_TOP)

    # ---- optional top-axis tick calibration audit ----
    # ticks are short dark marks hanging just below the top frame edge; count the
    # dark pixels in a thin band and look for evenly spaced maxima.
    cal_note = "frame-edge calibration (top axis -4.0..1.0 logH, left axis 0..3 D)"
    band = dark[yT + 2:yT + 10, xL:xR + 1].sum(0)
    tick_cols = np.array([c for c in range(1, len(band) - 1)
                          if band[c] >= 4 and band[c] >= band[c - 1] and band[c] >= band[c + 1]])
    if tick_cols.size >= 3:
        tc = np.sort(tick_cols) + xL
        logH_ticks = col_to_logH(tc)
        nearest = np.round(logH_ticks)                      # top axis is integer logH
        cal_res = float(np.sqrt(np.mean((logH_ticks - nearest) ** 2)))
        cal_note = "top-axis tick calibration residual RMS %.4f logH (%d ticks); " \
                   "frame-edge scale retained" % (cal_res, len(tc))
    else:
        cal_res = None

    # ---- trace curves column by column inside the frame ----
    interior = slice(yT + 1, yB)          # exclude the frame edges themselves
    ilen = yB - yT - 1
    EDGE_MARGIN = 3                       # frame anti-aliasing / tick remnants hug the edges
    cols = range(xL + 1, xR)
    # pass 1: collect run heights of columns that look like clean 3-curve columns
    heights = []
    per_col = {}
    for c in cols:
        seg = dark[interior, c]
        rr = [(a, b) for a, b in runs(seg)
              if a >= EDGE_MARGIN and b <= ilen - EDGE_MARGIN]
        per_col[c] = rr
        if len(rr) == 3:
            heights.extend([b - a for a, b in rr])
    if not heights:
        raise SystemExit("no clean 3-cluster columns found; check DARK_THR / frame box")
    med_h = float(np.median(heights))
    max_h = 6.0 * med_h

    # pass 2: accept columns with exactly 3 runs, none over-tall; sub-pixel CoM
    def com(c, a, b):
        rows = np.arange(a, b) + (yT + 1)
        wts = np.clip(DARK_THR - lum[rows, c], 1e-6, None)
        return float((rows * wts).sum() / wts.sum())

    traced = {"B": {}, "G": {}, "R": {}}      # logH -> density, by vertical order
    clean_rows = {"B": {}, "G": {}, "R": {}}  # col -> curve row, for pass 3
    n_cols = 0
    for c in cols:
        n_cols += 1
        rr = per_col[c]
        if len(rr) != 3 or any((b - a) > max_h for a, b in rr):
            continue
        h = col_to_logH(c)
        centers = sorted(com(c, a, b) for a, b in rr)  # ascending row => top..bottom
        for name, r in zip(("B", "G", "R"), centers):
            traced[name][round(h, 4)] = row_to_den(r)
            clean_rows[name][c] = r

    # pass 3: recover columns rejected for extra runs (legend text, curve labels).
    # Predict each curve's row by interpolating the clean trace; accept a run only
    # if exactly one plausible-thickness candidate sits within the match window.
    MATCH_PX = 6.0
    recovered = 0
    for name in ("B", "G", "R"):
        cc = np.array(sorted(clean_rows[name]))
        if cc.size < 2:
            continue
        rr_clean = np.array([clean_rows[name][c] for c in cc])
        for c in cols:
            if c in clean_rows[name] or c < cc[0] or c > cc[-1]:
                continue
            pred = float(np.interp(c, cc, rr_clean))
            cands = [(a, b) for a, b in per_col[c]
                     if (b - a) <= 2.5 * med_h
                     and abs(com(c, a, b) - pred) <= MATCH_PX]
            if len(cands) != 1:
                continue
            traced[name][round(col_to_logH(c), 4)] = row_to_den(com(c, *cands[0]))
            recovered += 1
    print("pass-3 recovery: %d channel-columns accepted via continuity match" % recovered)

    # ---- interpolate onto uniform logH grid, coverage-gated ----
    density = {}
    dmin = {}
    coverage = {}
    mono = {}
    at0 = {}
    warnings = []
    for name in ("B", "G", "R"):
        pts = sorted(traced[name].items())
        cov = len(pts) / n_cols
        coverage[name] = round(100.0 * cov, 1)
        if cov < 0.60 or len(pts) < 4:
            warnings.append("%s coverage %.1f%% below 60%% gate; channel not emitted"
                            % (name, 100.0 * cov))
            density[name] = [None] * len(GRID)
            dmin[name] = None
            mono[name] = None
            at0[name] = None
            continue
        hx = np.array([p[0] for p in pts])
        dy = np.array([p[1] for p in pts])
        lo, hi = hx.min(), hx.max()
        vals = np.interp(GRID, hx, dy)
        vals = np.where((GRID < lo - 1e-9) | (GRID > hi + 1e-9), np.nan, vals)
        vals = smooth5(vals)                                   # light 5-pt smoothing
        density[name] = [None if np.isnan(v) else round(float(v), 4) for v in vals]
        toe = vals[GRID <= -3.5]
        toe = toe[~np.isnan(toe)]
        dmin[name] = round(float(np.median(toe)), 4) if toe.size else None
        fin = vals[~np.isnan(vals)]
        mono[name] = round(float(min(0.0, np.min(np.diff(fin)))), 4) if fin.size > 1 else 0.0
        at0[name] = round(float(np.interp(STOPS_ZERO_LOGH, GRID[~np.isnan(vals)],
                                          vals[~np.isnan(vals)])), 4)

    audit = {
        "frame_box_px_x0y0x1y1": frame_box,
        "image_px": [W, H],
        "coverage_pct": coverage,
        "calibration_note": cal_note,
        "calibration_residual_logH_rms": cal_res,
        "max_monotonicity_violation_D": mono,
        "median_line_thickness_px": round(med_h, 2),
        "dark_threshold_luminance": DARK_THR,
        "smoothing": "5-point moving average on the interpolated logH grid",
    }
    provenance = {
        "source_pdf": "film_datasheet/V3 500T.pdf",
        "page_index": PAGE,
        "image_name": IMNAME,
        "extraction_method": method,
        "figure": "Sensitometric Curves, Kodak Vision3 500T",
        "date": "2026-07-24",
    }
    out = {
        "source": "Kodak Vision3 500T datasheet, Sensitometric Curves figure, "
                  "raster-traced from embedded image Im1 (page index 2)",
        "char_curves": {
            "log_exposure": [round(float(x), 2) for x in GRID],
            "log_exposure_units": "log lux-seconds",
            "density": {"R": density["R"], "G": density["G"], "B": density["B"]},
            "dmin": {"R": dmin["R"], "G": dmin["G"], "B": dmin["B"]},
            "camera_stops_zero_logH": round(float(STOPS_ZERO_LOGH), 5),
            "curve_order_note": "at any exposure, top->bottom on the plot = B, G, R; "
                                "densities are absolute ECN-2/Status M incl. base+mask",
        },
        "provenance": provenance,
        "digitization_audit": audit,
    }
    outp = DATA / "films" / "V3500T_datasheet_curves.json"
    json.dump(out, open(outp, "w"), indent=1)

    # ---- one-line summary per channel ----
    print("frame box px (x0,y0,x1,y1) = %s   image %dx%d   line thickness %.2f px"
          % (frame_box, W, H, med_h))
    print("calibration: %s" % cal_note)
    for name in ("B", "G", "R"):
        if dmin[name] is None:
            print("%s : NOT EMITTED (coverage %.1f%%)" % (name, coverage[name]))
        else:
            print("%s : dmin %.3f  D@stops0 %.3f  coverage %.1f%%  maxNegJump %.4f"
                  % (name, dmin[name], at0[name], coverage[name], mono[name]))
    for w in warnings:
        print("WARN: %s" % w)
    print("wrote %s" % outp.relative_to(ROOT))


if __name__ == "__main__":
    main()
