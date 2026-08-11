#!/usr/bin/env python3
"""Trace the Spectral Dye-Density charts of all four Kodak Vision3 negatives.

`data/films/Vision3_dye_density_corrected.json` WAS the surrogate dye basis behind
EVERY Kodak C-41 stock in this repo, and it is the thinnest-sourced file we hold:
its `source` is the bare phrase "digitized from plot", and its own
`important_note` concedes that full curves were traced for **250D (5207) only** --
50D/200T/500T were read at three LED wavelengths (450/544/640 nm) and ASSUMED to
agree to ~0.03 D. This module traces all four stocks at full spectral resolution
so that assumption becomes testable. It writes NEW per-stock files and does not
touch the existing Vision3 JSON.

Sources: `film_datasheet/V3 {50D,200T,250D,500T}.pdf`, page index 3. The dye chart
is a RASTER image, so it is read from the EMBEDDED image at native resolution
(`fitz.Pixmap(doc, xref)`) -- never `page.get_pixmap(dpi=...)`, which resamples and
discards the native detail the sub-pixel centroiding depends on. The chart is
picked by placement rect (`x0 > 300` and `width > 150`): the left-hand image on
each page is the spectral-sensitivity chart and there is also a small logo.

Axis calibration: the frame edges ARE the axis extremes, x = 400..800 nm and
y = -0.2..1.8 D. Confirmed on 250D by replotting the existing JSON, which lands on
the printed ink across all three lobes.

NO AUTOMATED LABEL CROSS-CHECK IS POSSIBLE HERE. The tick labels are baked into
the raster, so there is no text to extract -- this is the first chart family in the
repo without that safety net. The three acceptance tests below stand in for it:

  1. Peak normalization -- the caption says the dyes are peak-normalized, so each
     traced peak must be 1.000 +/- 0.01. A miss means the y calibration is wrong.
  2. Ink-hit -- each traced curve is replotted on the native image and must land
     within 2 px of printed ink for >= 97% of its samples (`ink_hit` is imported
     from engine/c41/datasheet_overlay.py, not copied).
  3. Closure -- with D-mins subtracted and dyes peak-normalized, some NON-NEGATIVE
     a*C + b*M + c*Y must reproduce the printed Midscale Neutral curve. Solved by
     non-negative least squares; the RMS residual is the only independent check on
     the SEPARATION (aggregate agreement validates the sum, not the split).

Counting ticks would be a trap here even if it looked safe: 200T and 500T label x
every 50 nm while 250D and 50D label every 100 nm (same range, different tick
count), 250D labels y every 0.2 while 50D labels every 0.4, and 50D's printed
curves terminate near 760 nm where the others reach 800.

Where a track finds no continuation the trace TERMINATES and the JSON carries
`null` beyond it. Nothing is flat-held or zero-filled -- that is the defect
registered against Ektar 100, and 50D hits it near 760 nm. The true support is
recorded per dye in `digitization_audit`.

Run:
  python3 engine/ecn2/v3_dye_digitize.py            # all four stocks
  python3 engine/ecn2/v3_dye_digitize.py --stock 50D
"""
import argparse
import datetime
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.optimize import nnls

try:
    import fitz                                  # PyMuPDF
except ImportError:                              # pragma: no cover
    raise SystemExit("v3_dye_digitize.py needs PyMuPDF: pip install pymupdf")

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "films"
FORENSICS = ROOT / "builds" / "_forensics"

STOCKS = {
    "50D":  {"pdf": "V3 50D.pdf",  "code": "5203"},
    "200T": {"pdf": "V3 200T.pdf", "code": "5213"},
    "250D": {"pdf": "V3 250D.pdf", "code": "5207"},
    "500T": {"pdf": "V3 500T.pdf", "code": "5219"},
}
PAGE = 3

# self-check only -- the xref is resolved by placement rect, never hard-coded
EXPECTED = {                                     # stock -> (xref, W, H, plotW, plotH)
    "250D": (16, 693, 754, 542, 541),
    "50D":  (17, 693, 765, 542, 542),
    "200T": (16, 716, 712, 567, 568),
    "500T": (16, 686, 722, 568, 568),
}

WL_LEFT, WL_RIGHT = 400.0, 800.0
D_TOP, D_BOTTOM = 1.8, -0.2
GRID = np.arange(400, 801, 1)

# approximate peak wavelengths from the caption geometry; the seed is refined by
# searching a window around each for the run whose centroid sits nearest D = 1.0
PEAKS = {"yellow": 445.0, "magenta": 540.0, "cyan": 685.0}
PEAK_WINDOW_NM = 30.0

INK_THR = 25.0          # ink = 255 - grey; >25 means grey < 230 (anti-aliased edge)
GLYPH_FILL = 0.15       # bbox fill ratio above which a component reads as a glyph
TRACK_TOL_PX = 5.0      # max |centroid - prediction| before a track terminates
FIT_N = 5               # points used for the linear extrapolation
MAX_BRIDGE_PX = 90      # longest crossing a track may bridge on prediction alone
MAX_COAST_PX = 12       # longest stretch with NO acceptable ink before terminating


# ---------------------------------------------------------------- ink_hit reuse
def _load_ink_hit():
    """Import `ink_hit` from engine/c41/datasheet_overlay.py (do not copy it)."""
    p = ROOT / "engine" / "c41" / "datasheet_overlay.py"
    sys.path.insert(0, str(p.parent))            # module does `from portra_stocks import`
    spec = importlib.util.spec_from_file_location("_c41_overlay", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ink_hit


ink_hit = _load_ink_hit()


# ------------------------------------------------------------------ chart input
def load_chart(stock):
    """Native-resolution RGB array of the dye chart, plus its frame box."""
    doc = fitz.open(ROOT / "film_datasheet" / STOCKS[stock]["pdf"])
    page = doc[PAGE]
    picks = []
    for info in page.get_images(full=True):
        xref = info[0]
        rects = page.get_image_rects(xref)
        if not rects:
            continue
        r = rects[0]
        if r.x0 > 300 and r.width > 150:
            picks.append((xref, r))
    if len(picks) != 1:
        raise SystemExit("%s: expected 1 dye chart on page %d, found %d"
                         % (stock, PAGE, len(picks)))
    xref, rect = picks[0]
    pm = fitz.Pixmap(doc, xref)
    img = np.frombuffer(pm.samples, np.uint8).reshape(pm.height, pm.width, pm.n)
    img = img[:, :, :3].astype(float)
    dpi = round(pm.width / rect.width * 72.0)

    grey = img.mean(2)
    H, W = grey.shape
    dark = grey < 128
    rows = np.where(dark.sum(1) > 0.7 * W)[0]
    if rows.size < 2:
        raise SystemExit("%s: frame rows not found" % stock)
    yT, yB = int(rows.min()), int(rows.max())
    sub = dark[yT:yB + 1]
    cols = np.where(sub.sum(0) > 0.7 * sub.shape[0])[0]
    if cols.size < 2:
        raise SystemExit("%s: frame columns not found" % stock)
    xL, xR = int(cols.min()), int(cols.max())

    exp = EXPECTED.get(stock)
    warn = None
    got = (xref, W, H, xR - xL, yB - yT)
    if exp and tuple(exp) != got:
        warn = ("WARNING %s: chart geometry %s != expected %s -- verify the source"
                % (stock, got, tuple(exp)))
        print(warn)
    return {"stock": stock, "img": img, "grey": grey, "xref": xref, "dpi": dpi,
            "frame": (xL, yT, xR, yB), "warn": warn}


def col_to_wl(ch, c):
    xL, _, xR, _ = ch["frame"]
    return WL_LEFT + (np.asarray(c, float) - xL) * (WL_RIGHT - WL_LEFT) / (xR - xL)


def wl_to_col(ch, wl):
    xL, _, xR, _ = ch["frame"]
    return xL + (np.asarray(wl, float) - WL_LEFT) * (xR - xL) / (WL_RIGHT - WL_LEFT)


def row_to_D(ch, r):
    _, yT, _, yB = ch["frame"]
    return D_TOP + (np.asarray(r, float) - yT) * (D_BOTTOM - D_TOP) / (yB - yT)


def D_to_row(ch, d):
    _, yT, _, yB = ch["frame"]
    return yT + (np.asarray(d, float) - D_TOP) * (yB - yT) / (D_BOTTOM - D_TOP)


# -------------------------------------------------------------- in-plot text mask
def mask_text(ch):
    """Strip the in-plot annotation, keeping only the curve network.

    The chart prints "Midscale Neutral", "Yellow", "Magenta", "Cyan", "Minimum
    Density" and "Process: ECN-2; D-mins subtracted" INSIDE the plot area, which
    is why columns average ~7.5 ink runs where only five curves exist. Connected
    -component labelling separates them cleanly: the five solid curves cross each
    other and fuse into ONE sprawling component (bbox fill ~0.04, spanning the
    whole plot), while every glyph is a small, dense island (fill 0.3-0.7, bbox
    <= ~20 px). On all four stocks exactly one component survives the filter, and
    the dashes of the (unused) Minimum Density curve are dropped with the text.

    Returns (ink, summary) where `ink` is 255-grey with everything masked out.
    """
    xL, yT, xR, yB = ch["frame"]
    sl = (slice(yT + 2, yB - 1), slice(xL + 2, xR - 1))
    plot_grey = ch["grey"][sl]
    binary = plot_grey < 170
    lab, n = ndimage.label(binary, np.ones((3, 3)))
    if n == 0:
        raise SystemExit("%s: no ink inside the plot frame" % ch["stock"])
    objs = ndimage.find_objects(lab)
    counts = ndimage.sum(binary, lab, range(1, n + 1))

    keep = np.zeros(n + 1, bool)
    removed = []
    for i, box in enumerate(objs):
        h = box[0].stop - box[0].start
        w = box[1].stop - box[1].start
        fill = counts[i] / float(w * h)
        small = (w < 0.25 * binary.shape[1]) and (h < 0.25 * binary.shape[0])
        if fill > GLYPH_FILL and small:
            removed.append((int(counts[i]), w, h, round(float(fill), 3)))
        else:
            keep[i + 1] = True

    kept_mask = keep[lab]
    # dilate by 2 px so the anti-aliased skirt of each kept curve -- which is
    # lighter than the 170 binarization threshold and therefore outside the
    # component -- still contributes to the sub-pixel centroid.
    kept_mask = ndimage.binary_dilation(kept_mask, np.ones((5, 5)))

    ink = np.zeros_like(ch["grey"])
    ink[sl] = np.where(kept_mask, 255.0 - plot_grey, 0.0)
    ink[ink < INK_THR] = 0.0

    summary = {
        "method": "8-connected components on grey<170 inside the frame; drop any "
                  "component with bbox fill > %.2f whose bbox is < 25%% of the plot "
                  "in both axes (glyphs are dense and compact, curves are thin and "
                  "long); kept components dilated 2 px to recover the anti-aliased "
                  "skirt" % GLYPH_FILL,
        "components_total": int(n),
        "components_kept": int(keep.sum()),
        "components_removed": len(removed),
        "removed_px_total": int(sum(r[0] for r in removed)),
        "removed_bbox_px_max": max((max(r[1], r[2]) for r in removed), default=0),
        "removed_fill_min": min((r[3] for r in removed), default=None),
        "note": "removed components are the in-plot labels (Midscale Neutral, "
                "Yellow, Magenta, Cyan, Minimum Density, Process: ECN-2; D-mins "
                "subtracted) and the dashes of the untraced Minimum Density curve; "
                "the surviving component is the fused solid-curve network",
    }
    return ink, summary


# --------------------------------------------------------------- run extraction
def _split_at_valleys(v):
    """Indices splitting an ink profile where two lines merely touch.

    Two curves 8 px apart with a 4 px line width share ONE contiguous ink run,
    but their profile still dips between them. Splitting at a valley that falls
    below 85% of the neighbouring peaks recovers the pair as two candidates,
    which is what keeps a track from sliding onto its neighbour at a shallow
    crossing. Curves that genuinely overlap saturate into a flat plateau, leave
    no valley, and are handled by the merge branch of the tracker instead.
    """
    cuts = []
    for i in range(1, len(v) - 1):
        if v[i] <= v[i - 1] and v[i] <= v[i + 1]:
            lo = v[:i].max() if i else v[i]
            hi = v[i + 1:].max()
            if v[i] < 0.85 * min(lo, hi):
                cuts.append(i)
    return cuts


def column_candidates(ink, x, r0, r1, linew, split_above=None):
    """Candidate line centres in column x as (centroid, height, top, bottom).

    `r0`/`r1` exclude the frame's own horizontal rules, which would otherwise
    read as a curve spanning every column. `split_above` is the run height beyond
    which a run is suspected of holding two lines; it must be slope-aware, since a
    steep single line is legitimately tall and must NOT be split.
    """
    if split_above is None:
        split_above = 1.3 * single_line_height(linew, 0.0)
    col = ink[r0:r1 + 1, x]
    on = col > 0
    out = []
    i, n = 0, len(col)
    while i < n:
        if not on[i]:
            i += 1
            continue
        j = i
        while j < n and on[j]:
            j += 1
        v = col[i:j]
        cuts = _split_at_valleys(v) if (j - i) > split_above else []
        for a, b in zip([0] + cuts, cuts + [len(v)]):
            w = v[a:b]
            if w.sum() <= 0:
                continue
            rows = np.arange(a, b, dtype=float) + i + r0
            out.append((float((rows * w).sum() / w.sum()), b - a,
                        float(rows[0]), float(rows[-1])))
        i = j
    return out


def median_line_width(ink, ch):
    """Median run height over interior columns -- the printed line width in px."""
    xL, yT, xR, yB = ch["frame"]
    hs = []
    for x in range(xL + 6, xR - 5, 3):
        hs += [r[1] for r in column_candidates(ink, x, yT + 1, yB - 1, 3.0)]
    return float(np.median(hs)) if hs else 3.0


def row_limits(ch, linew):
    """Row band that excludes the frame's top and bottom rules."""
    _, yT, _, yB = ch["frame"]
    m = int(round(linew)) + 2
    return yT + m, yB - m


# ------------------------------------------------------------------- the tracer
def single_line_height(linew, slope):
    """Vertical extent one printed line occupies in one column.

    A line of perpendicular width w drawn at slope s spans w*sqrt(1+s^2) + s rows,
    so a steep curve is legitimately many times taller than the nominal line
    width. Ignoring that is what makes a naive "tall run = crossing" test fire on
    every steep flank -- the magenta rise alone reaches 13 px at a 4 px line width.
    """
    return linew * np.sqrt(1.0 + slope * slope) + slope


def _predict(xs, ys, x):
    """Short linear extrapolation of the last accepted points to column x."""
    if len(ys) == 1:
        return ys[-1]
    k = min(FIT_N, len(ys))
    a, b = np.polyfit(np.asarray(xs[-k:], float), np.asarray(ys[-k:], float), 1)
    return a * x + b


def _walk(ink, ch, x0, y0, step, linew, out, bridged, others=()):
    """Track one curve away from its seed, one column at a time.

    At each column the candidate centre nearest a short linear extrapolation of
    the last few accepted points wins. Where two curves genuinely overlap the
    candidate is a saturated plateau far taller than one line can be; there the
    extrapolated PREDICTION is taken instead of the centroid, which is the
    joint-continuity handling already used for Velvia 50.

    Where no candidate is acceptable the track COASTS on the prediction for a few
    columns -- a dash of the Minimum Density curve fused to a solid one throws the
    centroid briefly -- but every coasted column stays PENDING until real ink is
    re-acquired, and a track that never re-acquires (a genuine curve END, such as
    50D's near 760 nm) has its whole coasted tail rolled back. The recorded support
    therefore stops at the last column where printed ink was actually measured.
    Nothing is flat-held or zero-filled.
    """
    xL, _, xR, _ = ch["frame"]
    r0, r1 = row_limits(ch, linew)
    xs, ys = [x0], [y0]
    run_bridge = coast = 0
    written = []                                 # columns this walk wrote, in order
    coasting = []                                # trailing columns with NO ink match
    x = x0 + step
    while xL + 1 <= x <= xR - 1:
        pred = _predict(xs, ys, x)
        slope = abs(pred - ys[-1])
        expect = single_line_height(linew, slope)
        cands = column_candidates(ink, x, r0, r1, linew,
                                  split_above=1.3 * expect)
        if not cands:
            break
        cen, hgt, top, bot = min(cands, key=lambda r: abs(r[0] - pred))
        # while coasting the tolerance opens up, so the track can re-acquire the
        # line it lost. 50D's magenta is the case: the dashed Minimum Density
        # curve runs tangentially along it near 600 nm and the dashes that touch
        # it survive the text mask, dragging the centroid ~6 px off for a dozen
        # columns before the real line reappears cleanly.
        tol = (TRACK_TOL_PX + 0.5 * slope) * (1.0 + min(coast, 8) * 0.25)
        # a crossing is not "a tall run" -- it is a run this track SHARES with a
        # neighbouring curve. Pass 2 knows where the other tracks are, so the
        # condition can be stated directly instead of inferred from height.
        shared = any(top - 1.0 <= o[x] <= bot + 1.0 for o in others if x in o)
        merged = shared or hgt > 1.45 * expect + 1.0
        if merged and top - 1.0 <= pred <= bot + 1.0:
            # inside a crossing: the ink IS here, it just belongs to two curves
            y, run_bridge, coast, coasting = pred, run_bridge + 1, 0, []
            bridged.add(x)
        elif abs(cen - pred) <= tol:
            y, run_bridge, coast, coasting = cen, 0, 0, []
        else:
            y, coast = pred, coast + 1
            coasting.append(x)
            bridged.add(x)
        if coast > MAX_COAST_PX:
            break
        if run_bridge > MAX_BRIDGE_PX:           # a crossing this long is not one
            coasting = written[-run_bridge:]
            break
        xs.append(x)
        ys.append(y)
        out[x] = y
        written.append(x)
        x += step
    for k in coasting:                           # never invent curve past the ink
        out.pop(k, None)
        bridged.discard(k)
    return len(xs) - 1


def _seed_at_peak(ink, ch, name, linew):
    """Peak seed: the run nearest D = 1.0 in a window around the printed peak.

    The caption states the dyes are peak-normalized, so each dye touches EXACTLY
    1.0 at its own peak -- that is a far stronger seed than "topmost run".
    """
    xL, _, xR, _ = ch["frame"]
    r0, r1 = row_limits(ch, linew)
    c0 = int(round(wl_to_col(ch, PEAKS[name] - PEAK_WINDOW_NM)))
    c1 = int(round(wl_to_col(ch, PEAKS[name] + PEAK_WINDOW_NM)))
    best = None
    for x in range(max(xL + 1, c0), min(xR - 1, c1) + 1):
        for cen, hgt, top, bot in column_candidates(ink, x, r0, r1, linew):
            if hgt > 2.0 * linew:                # a crossing blob is not a peak
                continue
            err = abs(float(row_to_D(ch, cen)) - 1.0)
            if best is None or err < best[0]:
                best = (err, x, cen)
    if best is None:
        raise SystemExit("%s/%s: no seed run found near the expected peak"
                         % (ch["stock"], name))
    return best[1], best[2]


def trace_dye(ink, ch, name, linew, others=()):
    """Seed a dye at its peak and track outward in both directions."""
    x0, y0 = _seed_at_peak(ink, ch, name, linew)
    out, bridged = {x0: y0}, set()
    _walk(ink, ch, x0, y0, -1, linew, out, bridged, others)
    _walk(ink, ch, x0, y0, +1, linew, out, bridged, others)
    return out, bridged


def _duplicate(a, b, tol=2.0, frac=0.4):
    """True if track `b` shadows track `a` -- the same ink under another name.

    Pass 1 is fallible: a track that jumped at a crossing comes back sitting ON
    its neighbour. Feeding that back into pass 2 as "another curve is here" would
    make the victim treat its OWN ink as a permanent crossing and bridge until it
    died. Any pass-1 track that coincides with this one over a large fraction of
    their common columns is therefore discarded as evidence.
    """
    common = [x for x in a if x in b]
    if not common:
        return False
    same = sum(1 for x in common if abs(a[x] - b[x]) <= tol)
    return same > frac * len(common)


def trace_all_dyes(ink, ch, linew):
    """Two-pass joint trace of the three dyes.

    Pass 1 traces them in order of separability -- cyan alone, then magenta knowing
    cyan, then yellow knowing both -- so each track starts from the best evidence
    available. Pass 2 re-traces every dye knowing where the other two ran, which
    lets a run SHARED with a neighbour be recognised as a crossing and handed to
    the extrapolated prediction. Height alone cannot make that call: a steep single
    line is legitimately three times the nominal line width, and magenta's descent
    through the rising cyan at ~590 nm is exactly the case where a height test
    terminates the track on the wrong branch.
    """
    names = ("cyan", "magenta", "yellow")
    first = {}
    for n in names:
        first[n] = trace_dye(ink, ch, n, linew, others=list(first.values()))[0]
    out = {}
    for n in names:
        others = [first[m] for m in names
                  if m != n and not _duplicate(first[n], first[m])]
        out[n] = trace_dye(ink, ch, n, linew, others=others)
    return out


def _truncate_where_duplicated(track, seed_x, others, window=20, need=15, tol=2.0):
    """Cut a track where it stops being its own curve and becomes a neighbour's.

    A track that loses its identity at a crossing does not fail loudly -- it comes
    out sitting exactly ON the curve it swapped to, ink-hit 100%, looking perfect.
    500T's Midscale Neutral does this: it merges with the rising cyan at ~641 nm
    and never comes back. The only honest signal is the coincidence itself.

    The test is a sliding window rather than a consecutive run: a track that has
    swapped wobbles a pixel or two off its captor, which resets a consecutive
    counter but not a "`need` of the last `window` columns coincide" test. A
    genuine crossing -- 250D's Midscale Neutral passing through cyan near 620 nm --
    coincides for only a handful of columns and survives.
    """
    cut = set()
    for direction in (-1, +1):
        xs = sorted((x for x in track if direction * (x - seed_x) > 0),
                    reverse=direction < 0)
        flags = []
        for i, x in enumerate(xs):
            flags.append(any(x in o and abs(track[x] - o[x]) <= tol for o in others))
            lo = max(0, i - window + 1)
            if sum(flags[lo:]) >= need:
                start = lo + flags[lo:].index(True)
                cut.update(xs[start:])
                break
    for x in cut:
        track.pop(x, None)
    return len(cut)


def trace_midscale(ink, ch, linew, others=()):
    """The topmost solid curve. Optional -- returns None if it cannot be seeded."""
    r0, r1 = row_limits(ch, linew)
    seed = None
    for x in range(int(round(wl_to_col(ch, 520))), int(round(wl_to_col(ch, 560)))):
        cands = [c for c in column_candidates(ink, x, r0, r1, linew)
                 if c[1] <= 2.0 * linew]
        if not cands:
            continue
        cen = min(cands, key=lambda r: r[0])[0]
        if seed is None or cen < seed[1]:
            seed = (x, cen)
    if seed is None:
        return None, set()
    out, bridged = {seed[0]: seed[1]}, set()
    _walk(ink, ch, seed[0], seed[1], -1, linew, out, bridged, others)
    _walk(ink, ch, seed[0], seed[1], +1, linew, out, bridged, others)
    _truncate_where_duplicated(out, seed[0], others)
    bridged &= set(out)
    return out, bridged


# ------------------------------------------------------------------ resampling
def to_grid(ch, track):
    """Column->row track -> 1 nm grid of densities, None outside traced support."""
    xs = np.array(sorted(track), float)
    ys = np.array([track[int(x)] for x in xs], float)
    wl = col_to_wl(ch, xs)
    order = np.argsort(wl)
    wl, ys = wl[order], ys[order]
    d = row_to_D(ch, np.interp(GRID, wl, ys))
    inside = (GRID >= wl.min()) & (GRID <= wl.max())
    d = np.where(inside, d, np.nan)
    return d, (float(wl.min()), float(wl.max()))


def jsonify(a):
    return [None if not np.isfinite(v) else round(float(v), 4) for v in a]


# ------------------------------------------------------------- acceptance tests
def test_peak(curves):
    """1. Each dye's traced peak must be 1.000 +/- 0.01 (caption guarantees it)."""
    res = {}
    for k in ("cyan", "magenta", "yellow"):
        d = curves[k]
        i = int(np.nanargmax(d))
        near = abs(GRID[i] - PEAKS[k]) <= PEAK_WINDOW_NM
        res[k] = {"peak_nm": int(GRID[i]), "peak_value": round(float(d[i]), 4),
                  "abs_error": round(abs(float(d[i]) - 1.0), 4),
                  "expected_peak_nm": PEAKS[k],
                  "peak_in_expected_window": bool(near),
                  "pass": bool(abs(float(d[i]) - 1.0) <= 0.01 and near)}
    res["pass"] = all(res[k]["pass"] for k in ("cyan", "magenta", "yellow"))
    return res


def test_ink(ch, curves):
    """2. Replot each curve on the native image; >= 97% within 2 px of ink."""
    res = {"threshold_pct": 97.0, "per_curve": {}}
    worst = 100.0
    for k, d in curves.items():
        ok = np.isfinite(d)
        px = wl_to_col(ch, GRID[ok])
        py = D_to_row(ch, d[ok])
        hit, tot = ink_hit(ch["img"], px, py, radius=2)
        pct = 100.0 * hit / tot if tot else float("nan")
        res["per_curve"][k] = {"samples": int(tot), "on_ink_pct": round(pct, 2),
                               "pass": bool(pct >= 97.0)}
        if k in ("cyan", "magenta", "yellow"):
            worst = min(worst, pct)
    res["worst_dye_pct"] = round(worst, 2)
    res["pass"] = bool(worst >= 97.0)
    return res


def test_closure(curves):
    """3. Non-negative a*C + b*M + c*Y vs the printed Midscale Neutral curve.

    D-mins are subtracted and the dyes peak-normalized, so the neutral must be a
    non-negative mixture of the three. This is the only check on the SEPARATION --
    aggregate agreement validates the SUM, not the split -- so it is reported
    always and flagged, never hard-failed, above 0.05 D RMS.
    """
    if "midscale_neutral" not in curves:
        return {"status": "skipped", "reason": "Midscale Neutral was not traced"}
    M = np.column_stack([curves[k] for k in ("cyan", "magenta", "yellow")])
    y = curves["midscale_neutral"]
    ok = np.isfinite(y) & np.isfinite(M).all(1)
    if ok.sum() < 20:
        return {"status": "skipped", "reason": "insufficient common support"}
    coef, _ = nnls(M[ok], y[ok])
    resid = M[ok] @ coef - y[ok]
    rms = float(np.sqrt((resid ** 2).mean()))
    return {"status": "run",
            "overlap_nm": [int(GRID[ok][0]), int(GRID[ok][-1])],
            "n_samples": int(ok.sum()),
            "coefficients": {"cyan": round(float(coef[0]), 4),
                             "magenta": round(float(coef[1]), 4),
                             "yellow": round(float(coef[2]), 4)},
            "rms_residual_D": round(rms, 4),
            "max_abs_residual_D": round(float(np.abs(resid).max()), 4),
            "flag": bool(rms > 0.05),
            "note": "non-negative least squares; flagged above 0.05 D RMS but not "
                    "a hard failure"}


# ---------------------------------------------------------------- diagnostics
def write_pngs(ch, ink, curves, mask_summary):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FORENSICS.mkdir(parents=True, exist_ok=True)
    xL, yT, xR, yB = ch["frame"]
    st = ch["stock"]

    fig, ax = plt.subplots(1, 2, figsize=(13, 6.5))
    ax[0].imshow(ch["img"].astype(np.uint8))
    ax[0].set_title("%s native chart" % st, fontsize=9)
    ax[1].imshow(255.0 - ink, cmap="gray", vmin=0, vmax=255)
    ax[1].set_title("after text mask: %d of %d components removed (%d px)"
                    % (mask_summary["components_removed"],
                       mask_summary["components_total"],
                       mask_summary["removed_px_total"]), fontsize=9)
    for a in ax:
        a.axis("off")
    plt.tight_layout()
    masked_png = FORENSICS / ("V3_%s_textmask.png" % st)
    plt.savefig(masked_png, dpi=110, bbox_inches="tight")
    plt.close(fig)

    fig, a = plt.subplots(figsize=(9, 9))
    a.imshow(ch["img"].astype(np.uint8))
    for k, col in (("cyan", "#00b7c8"), ("magenta", "#d0169b"),
                   ("yellow", "#d8a400"), ("midscale_neutral", "#2233cc")):
        if k not in curves:
            continue
        d = curves[k]
        ok = np.isfinite(d)
        a.plot(wl_to_col(ch, GRID[ok]), D_to_row(ch, d[ok]), color=col, lw=1.6,
               alpha=0.75, label=k)
    a.plot([xL, xR, xR, xL, xL], [yT, yT, yB, yB, yT], "r-", lw=0.6, alpha=0.5)
    a.legend(fontsize=8, loc="upper right")
    a.set_title("Vision3 %s (%s) traced dyes on the printed chart"
                % (st, STOCKS[st]["code"]), fontsize=10)
    a.axis("off")
    plt.tight_layout()
    over_png = FORENSICS / ("V3_%s_overlay.png" % st)
    plt.savefig(over_png, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return masked_png, over_png


# --------------------------------------------------------------------- driver
def digitize(stock):
    ch = load_chart(stock)
    ink, mask_summary = mask_text(ch)
    linew = median_line_width(ink, ch)
    xL, yT, xR, yB = ch["frame"]

    curves, support, bridge = {}, {}, {}
    tracks = trace_all_dyes(ink, ch, linew)
    for name in ("cyan", "magenta", "yellow"):
        track, br = tracks[name]
        curves[name], support[name] = to_grid(ch, track)
        bridge[name] = len(br)
    mid, br = trace_midscale(ink, ch, linew,
                             others=[tracks[n][0] for n in tracks])

    if mid is not None:
        curves["midscale_neutral"], support["midscale_neutral"] = to_grid(ch, mid)
        bridge["midscale_neutral"] = len(br)

    t1 = test_peak(curves)
    t2 = test_ink(ch, curves)
    t3 = test_closure(curves)
    masked_png, over_png = write_pngs(ch, ink, curves, mask_summary)

    audit = {
        "digitizer": "engine/ecn2/v3_dye_digitize.py",
        # Deliberately NO timestamp. Every artifact in this repo must regenerate
        # BYTE-IDENTICALLY -- that is the regression guard the whole pipeline
        # leans on (see PROJECT.md). A wall-clock stamp defeats it: the trace is
        # otherwise fully deterministic, so a timestamp would turn every rerun
        # into a spurious diff and hide a real one.
        "pdf": "film_datasheet/" + STOCKS[stock]["pdf"],
        "page_index": PAGE,
        "image_xref": ch["xref"],
        "image_px": [int(ch["grey"].shape[1]), int(ch["grey"].shape[0])],
        "effective_dpi": ch["dpi"],
        "geometry_selfcheck": ch["warn"] or "matches the verified table",
        "frame_box_xL_yT_xR_yB": [xL, yT, xR, yB],
        "frame_detection": "rows with dark(grey<128) sum > 0.7*W give top/bottom; "
                           "columns within those rows with sum > 0.7*subheight give "
                           "left/right",
        "x_axis": {"quantity": "wavelength_nm", "frame_edges": [WL_LEFT, WL_RIGHT],
                   "device_to_data": "wavelength_nm = %.9f * x_px + %.6f"
                                     % ((WL_RIGHT - WL_LEFT) / (xR - xL),
                                        WL_LEFT - xL * (WL_RIGHT - WL_LEFT) / (xR - xL))},
        "y_axis": {"quantity": "density", "frame_edges_top_bottom": [D_TOP, D_BOTTOM],
                   "y_px_origin": "image row 0, measured top-down",
                   "device_to_data": "density = %.9f * y_px + %.6f"
                                     % ((D_BOTTOM - D_TOP) / (yB - yT),
                                        D_TOP - yT * (D_BOTTOM - D_TOP) / (yB - yT))},
        "label_cross_check": "NOT POSSIBLE -- the tick labels are baked into the "
                             "raster, so no text extraction exists for this chart "
                             "family. The three acceptance tests below replace it.",
        "tick_count_traps_avoided": [
            "200T/500T label x every 50 nm, 250D/50D every 100 nm (same range)",
            "250D labels y every 0.2, 50D every 0.4 (same range)",
            "50D's printed curves stop near 760 nm where the others reach 800",
        ],
        "median_line_width_px": round(linew, 2),
        "text_mask": mask_summary,
        "tracing": "sub-pixel ink centroid per column (ink = 255-grey, no binary "
                   "thresholding); seeded at each dye's peak (nearest D=1.0) and "
                   "tracked outward by linear-extrapolation continuity; merged runs "
                   "at curve crossings take the prediction; tracks TERMINATE where "
                   "no run lies within %.0f px -- values beyond the traced support "
                   "are null, never flat-held or zero-filled" % TRACK_TOL_PX,
        "traced_support_nm": {k: [round(v[0], 1), round(v[1], 1)]
                              for k, v in support.items()},
        "traced_samples": {k: int(np.isfinite(v).sum()) for k, v in curves.items()},
        "bridged_columns": dict(bridge),
        "bridged_columns_note": "columns where the curve was inside a saturated "
                                "crossing blob and the extrapolated prediction was "
                                "used instead of an ink centroid",
        "minimum_density_curve": "not traced -- printed dashed; skipped rather than "
                                 "fabricated (the basis needs only C/M/Y)",
        "midscale_neutral_curve": "traced as the topmost solid curve, then truncated "
                                  "wherever it coincides with a dye track (a swap at "
                                  "a crossing produces a curve that is perfectly on "
                                  "ink but is the neighbour's). Used only for "
                                  "acceptance test 3.",
        "acceptance_tests": {
            "1_peak_normalization": t1,
            "2_ink_hit": t2,
            "3_closure": t3,
        },
        "diagnostics": ["builds/_forensics/" + masked_png.name,
                        "builds/_forensics/" + over_png.name],
    }

    doc = {
        "title": "Kodak Vision3 %s (%s) — per-layer spectral dye density"
                 % (stock, STOCKS[stock]["code"]),
        "family": "Vision3 colour negative (ECN-2 dye set)",
        "stock": stock,
        "kodak_code": STOCKS[stock]["code"],
        "units": "relative diffuse spectral density (Status M, D-min subtracted)",
        "normalization": "peak = 1.0 per dye",
        "source": "Kodak Vision3 %s datasheet, Spectral Dye-Density Curves "
                  "(film_datasheet/%s page %d), raster curve trace at native "
                  "image resolution by engine/ecn2/v3_dye_digitize.py"
                  % (stock, STOCKS[stock]["pdf"], PAGE),
        "shared_full_curves": {
            "wavelength_nm": [int(v) for v in GRID],
            "cyan": jsonify(curves["cyan"]),
            "magenta": jsonify(curves["magenta"]),
            "yellow": jsonify(curves["yellow"]),
        },
        "support_note": "null means OUTSIDE the traced support of that dye -- the "
                        "printed curve does not exist there. Not zero, not held.",
        "digitization_audit": audit,
    }
    if "midscale_neutral" in curves:
        doc["midscale_neutral"] = {
            "wavelength_nm": [int(v) for v in GRID],
            "density": jsonify(curves["midscale_neutral"]),
            "note": "topmost solid curve on the chart; traced for acceptance "
                    "test 3 (closure), not part of the dye basis",
        }

    out = DATA / ("Vision3_%s_dye_density.json" % stock)
    out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    return out, audit


def report(stock, audit):
    t1 = audit["acceptance_tests"]["1_peak_normalization"]
    t2 = audit["acceptance_tests"]["2_ink_hit"]
    t3 = audit["acceptance_tests"]["3_closure"]
    print("\n=== Vision3 %s (%s)  xref %d  frame %s  line %.1f px"
          % (stock, STOCKS[stock]["code"], audit["image_xref"],
             audit["frame_box_xL_yT_xR_yB"], audit["median_line_width_px"]))
    tm = audit["text_mask"]
    print("  text mask : removed %d of %d components (%d px, max bbox %d px, "
          "min fill %.2f); %d kept"
          % (tm["components_removed"], tm["components_total"],
             tm["removed_px_total"], tm["removed_bbox_px_max"],
             tm["removed_fill_min"] or 0.0, tm["components_kept"]))
    for k in ("cyan", "magenta", "yellow", "midscale_neutral"):
        if k not in audit["traced_support_nm"]:
            continue
        s = audit["traced_support_nm"][k]
        pk = t1.get(k)
        ih = t2["per_curve"].get(k, {})
        print("  %-16s support %6.1f-%6.1f nm  %s  ink-hit %5.1f%% %s"
              % (k, s[0], s[1],
                 ("peak %3d nm = %.4f %s" % (pk["peak_nm"], pk["peak_value"],
                                             "OK " if pk["pass"] else "FAIL"))
                 if pk else " " * 24,
                 ih.get("on_ink_pct", float("nan")),
                 "OK" if ih.get("pass") else "FAIL"))
    print("  test 1 peak normalization : %s" % ("PASS" if t1["pass"] else "FAIL"))
    print("  test 2 ink-hit (>=97%%)    : %s (worst dye %.1f%%)"
          % ("PASS" if t2["pass"] else "FAIL", t2["worst_dye_pct"]))
    if t3["status"] == "run":
        print("  test 3 closure            : RMS %.4f D  max %.4f D  a,b,c = "
              "%.3f/%.3f/%.3f  %s"
              % (t3["rms_residual_D"], t3["max_abs_residual_D"],
                 t3["coefficients"]["cyan"], t3["coefficients"]["magenta"],
                 t3["coefficients"]["yellow"],
                 "FLAG >0.05 D" if t3["flag"] else "ok"))
    else:
        print("  test 3 closure            : SKIPPED (%s)" % t3["reason"])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stock", choices=sorted(STOCKS))
    a = ap.parse_args()
    todo = [a.stock] if a.stock else ["50D", "200T", "250D", "500T"]
    for st in todo:
        out, audit = digitize(st)
        report(st, audit)
        print("  wrote %s" % out.relative_to(ROOT))


if __name__ == "__main__":
    main()
