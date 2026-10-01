#!/usr/bin/env python3
"""Write and verify dctl/output/Print Adjustment.dctl, with its locus-following Gain (C-41, every fleet stock).

The print cube's gray-axis lock renders the input DIAGONAL neutral. The Status M
cube places a stock's published neutral series on that diagonal at K_MID only,
by one constant offset; away from K_MID the series departs from the diagonal,
and the print renders that departure as the sheet's own baseline casts
(reported by the print engines, never fitted). An equal Gain offset moves every
tone parallel to the diagonal. After overexposure, a print-down by Gain brings
each tone to the density of a darker tone but keeps the departure of its own
density, so the print takes a cast the correctly exposed frame does not have.

TARGET = APPROXIMATE, MODEL-BASED EXPOSURE COMPENSATION: an optional grading
control, above the metric transform, whose print-down moves
a frame along the stock's fixed sheet series and so approximately returns an
overexposed frame of a sheet-matching negative to its correct-exposure
rendering, baseline casts included. It is not a model of enlarger exposure, it
does not restore each coloured pixel's original exposure, and it is not shown to
remove a real roll's colour shift: validation covers the sheet's neutral series.
Its tables are fixed sheet constants, never fitted to scene statistics. It does
not make the series neutral; that is a change to the print convention.

CURVE. s(g) is the stock's balanced locus (R, G = g, B) in k = balanced Status M
/ 3.30, taken from neutral_locus.sheet_neutral_locus in EXPOSURE order; the knots
used as a function of g are the strictly increasing branch (running maximum),
dropped knots reported, never re-sorted. The branch is the SUPPORT [g_min, g_max].
A knot at K_MID is inserted (interpolated) and always kept. Outside support the
locus's departure from the diagonal is held constant (continuous slope-one tails):
    h(g) = clamp(g, g_min, g_max),   s_ext(g) = g (1,1,1) + s(h) - h (1,1,1).

RULE (Darkroom mode, stock selected):
    g_new = Pivot + Gamma (g - Pivot) + Gain
    k_new = s_ext(g_new) + Gamma (k - s_ext(g))
then Gain R/G/B and the [0, 1] clamp. With Locus Stock Off, and in Literal mode,
the transform is the plain Print Adjustment (REFERENCE_DCTL below, the checked
baseline); the identity fast path is shared. A pixel is UNSUPPORTED when g or
g_new leaves support (reported, never counted as compensation).

SIMPLIFICATION (adaptive). Greedy knot removal against the FULL branch (every
original knot between the kept neighbours is checked), endpoints and K_MID kept,
starting at SIMPLIFY_START k; the simplified transform is then compared with the
full-branch transform over the validation set (coloured inputs, the delivered
control limits, real frames when their caches exist), supported and unclipped
points only, through the stock's print cube; the tolerance halves until the
maximum added dE2000 is <= ADDED_DE_MAX.

ACCEPTANCE (the run FAILS on any of these), on the emitted DCTL compiled as C:
  5a  emitted vs simplified double reference: max coordinate error <= NUM_TOL k
      (supported); emitted vs full-branch reference: max added dE2000 <=
      ADDED_DE_MAX (supported, unclipped);
  5b  defaults bit-identical to the input; Off and Literal bit-identical to
      REFERENCE_DCTL; menu build bit-identical to the --slider build; outputs finite;
      continuity at every knot and support end, as the input and the destination
      cross it, by shrinking separation; +Gain then -Gain returns the input at
      Gamma 1 (unclipped); the inverse (same Pivot, 1/Gamma, -Gain/Gamma) returns
      the input at general Gamma (unclipped, trims zero).
REPORTED (not enforced): 5c coverage and 5d the quality goal (mean <= 1, max <= 2
dE2000) on true exposure brackets n = +-1, +-2, +-3 (sheet log-exposure axis
advanced by n log10 2; Gain returns mid-grey), with excluded / unsupported /
clipped counts, plain Print Adjustment, a straight-line fit of the series, the curve,
and the exact-locus reference at the same green-density Gain (the full branch;
a reference for this target, not a bound); Gamma x Pivot x Gain over the control
limits, distance from the sheet's own render at the same green.

Usage:
    python3 engine/c41/locus_follow_dctl.py [--slider]
Report: builds/_forensics/locus_follow/report.json. Needs a C compiler (cc).
"""
import argparse, json, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
import colour

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine.common.spectral import resample   # noqa: E402
from engine.common.lut import read_cube, tetralerp_unit   # noqa: E402
from portra_stocks import STOCKS               # noqa: E402
from neutral_locus import sheet_neutral_locus, header_offset, K_MID, MID_BAND   # noqa: E402

DATA = ROOT / "data"
OUT = ROOT / "dctl" / "output" / "Print Adjustment.dctl"
REPORT = ROOT / "builds" / "_forensics" / "locus_follow" / "report.json"
TILT = ROOT / "builds" / "_forensics" / "tilt_study"
GRID = np.arange(400, 701, 1.0)
DMAX = 3.30
OFFSET_TOL = 5e-4
GAIN_RANGE = 0.2           # slider range, the same as Print Adjustment's
LOG2 = np.log10(2.0)
SIMPLIFY_START = 5e-4      # first knot-removal tolerance, k
SIMPLIFY_FLOOR = 1e-6
ADDED_DE_MAX = 0.1         # simplified vs full-branch transform, dE2000
NUM_TOL = 1e-5             # emitted C vs double reference, k
GOAL = (1.0, 2.0)          # reported exposure-compensation goal: mean, max dE2000
N_RANDOM, N_LIMIT, N_FRAME = 15000, 200, 3000
P3 = colour.RGB_COLOURSPACES["Display P3"]


# ---------------- sheet ----------------
def cube_stem(stock):
    return STOCKS[stock]["curves_json"].split("_datasheet_curves")[0]


def prt_n():
    smj = json.load(open(DATA / "standards" / "StatusM_ISO5-3.json"))
    smw = np.array(smj["wavelength_nm"], float)
    P = np.stack([resample(smw, smj["responsivity_linear_peak1"][c], GRID) for c in ("red", "green", "blue")])
    return P / P.sum(1, keepdims=True)


def series(stock, PRT_n):
    st = STOCKS[stock]
    fc = json.load(open(DATA / "films" / st["dye_density_json"]))["shared_full_curves"]
    wl = np.array(fc["wavelength_nm"], float)
    dye = np.stack([resample(wl, fc[c], GRID) for c in ("cyan", "magenta", "yellow")])
    sp = json.load(open(DATA / "films" / st["curves_json"]))["spectral"]
    dmin = resample(np.array(sp["wavelength_nm"], float), sp["dmin"], GRID)
    return sheet_neutral_locus(DATA / "films" / st["curves_json"], dmin, dye, PRT_n, DMAX)


def check_offsets(stem, offset_d):
    cubes = sorted(ROOT.glob("builds/**/%s_StatusM.cube" % stem))
    if not cubes:
        raise SystemExit("%s: no Status M cube under builds/ to check the offset against" % stem)
    for p in cubes:
        h = header_offset(p)
        if h is None or np.abs(h - offset_d).max() > OFFSET_TOL:
            raise SystemExit("%s: offset %s disagrees with header of %s (%s)"
                             % (stem, np.round(offset_d, 4), p.relative_to(ROOT), h))
    return len(cubes)


def exposure_series(L):
    """Window rows in exposure order: log exposure and balanced k (R, G, B)."""
    w = L.window; o = np.argsort(L.log_h[w])
    return L.log_h[w][o], (L.locus - L.offset)[w][o]


def branch(L):
    lh, bal = exposure_series(L)
    G = bal[:, 1]
    keep = np.r_[True, G[1:] > np.maximum.accumulate(G)[:-1]]
    g, R, B = G[keep], bal[keep, 0], bal[keep, 2]
    if not (np.all(np.isfinite(g)) and np.all(np.isfinite(R)) and np.all(np.isfinite(B))):
        raise SystemExit("non-finite sheet series")
    if not np.all(np.diff(g) > 0):
        raise SystemExit("kept branch is not strictly increasing")
    if not g[0] < K_MID < g[-1]:
        raise SystemExit("K_MID lies outside the supported branch")
    if not np.any(g == K_MID):
        i = np.searchsorted(g, K_MID)
        R = np.insert(R, i, np.interp(K_MID, g, R)); B = np.insert(B, i, np.interp(K_MID, g, B))
        g = np.insert(g, i, K_MID)
    dropped = [round(float(x), 6) for x in G[~keep]]
    return dict(g=g, R=R, B=B, dropped=dropped, mid=int(np.where(g == K_MID)[0][0]))


def fit_line(L):
    """Straight line through (K_MID, K_MID) over the reporting band (comparison column only)."""
    bal = L.locus - L.offset; G = bal[:, 1]; b = L.band; f = {}
    for i, c in ((0, "R"), (2, "B")):
        x, y = G[b] - K_MID, bal[b, i] - K_MID
        f[c] = float((x * y).sum() / (x * x).sum())
    return f


# ---------------- transforms (double-precision references) ----------------
class Curve:
    def __init__(self, g, R, B):
        self.g, self.R, self.B = np.asarray(g, float), np.asarray(R, float), np.asarray(B, float)

    def s_ext(self, x):
        h = np.clip(x, self.g[0], self.g[-1])
        return np.stack([x + np.interp(h, self.g, self.R) - h, x, x + np.interp(h, self.g, self.B) - h], -1)

    def supported(self, x):
        return (x >= self.g[0]) & (x <= self.g[-1])


class Line:
    def __init__(self, f):
        self.f = np.array([f["R"], 1.0, f["B"]])

    def s_ext(self, x):
        return K_MID + (np.asarray(x)[..., None] - K_MID) * self.f


def transform(k, curve, gamma, gain, pivot, trims=None, clip=True):
    """Darkroom mode, per-row controls; curve None = plain Print Adjustment."""
    k = np.atleast_2d(np.asarray(k, float)); n = len(k)
    col = lambda v: np.broadcast_to(np.asarray(v, float), (n,))[:, None]
    gm, gn_, pv = col(gamma), col(gain), col(pivot)
    tr = np.zeros((n, 3)) if trims is None else np.broadcast_to(np.asarray(trims, float), (n, 3))
    if curve is None:
        out = pv + (k - pv) * gm + gn_
    else:
        g = k[:, 1:2]; gout = pv + gm * (g - pv) + gn_
        out = curve.s_ext(gout[:, 0]) + gm * (k - curve.s_ext(g[:, 0]))
    out = out + tr
    fast = (gm[:, 0] == 1.0) & (gn_[:, 0] == 0.0) & np.all(tr == 0.0, 1)
    out[fast] = k[fast]
    if clip:
        out = np.where(fast[:, None], out, np.clip(out, 0.0, 1.0))
    return out


def destination(k, gamma, gain, pivot):
    return pivot + gamma * (np.atleast_2d(k)[:, 1] - pivot) + gain


# ---------------- print rendering ----------------
def print_cube(stem):
    hits = sorted(ROOT.glob("builds/c41/print_*/%s_to_*_DisplayP3.cube" % stem))
    if len(hits) != 1:
        raise SystemExit("%s: expected one DisplayP3 print cube, found %d" % (stem, len(hits)))
    size = int([l for l in open(hits[0]) if l.startswith("LUT_3D_SIZE")][0].split()[1])
    return hits[0], read_cube(hits[0], size)


def lab(cube, k):
    rgb = np.clip(tetralerp_unit(cube, np.clip(np.atleast_2d(k), 0.0, 1.0)), 0.0, 1.0)
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    return colour.XYZ_to_Lab(lin @ P3.matrix_RGB_to_XYZ.T, P3.whitepoint)


def de(cube, a, b):
    return colour.delta_E(lab(cube, a), lab(cube, b), method="CIE 2000")


# ---------------- simplification ----------------
def simplify(br, tol):
    g, R, B = br["g"], br["R"], br["B"]
    keep = list(range(len(g))); protect = {0, len(g) - 1, br["mid"]}
    while True:
        best = None
        for pos in range(1, len(keep) - 1):
            i = keep[pos]
            if i in protect:
                continue
            a, b = keep[pos - 1], keep[pos + 1]
            t = (g[a:b + 1] - g[a]) / (g[b] - g[a])
            e = max(np.abs(R[a] + t * (R[b] - R[a]) - R[a:b + 1]).max(),
                    np.abs(B[a] + t * (B[b] - B[a]) - B[a:b + 1]).max())
            if e <= tol and (best is None or e < best[0]):
                best = (e, pos)
        if best is None:
            break
        del keep[best[1]]
    idx = np.array(keep)
    simp = Curve(g[idx], R[idx], B[idx])
    err = max(np.abs(simp.s_ext(g)[:, 0] - R).max(), np.abs(simp.s_ext(g)[:, 2] - B).max())
    return idx, simp, float(err)


# ---------------- validation set ----------------
def frame_samples(stem, rng):
    """Real-frame pixels (balanced k through the a7R III Status M cube) for this stock, if the
    tilt study's caches exist; (k array, roll list)."""
    js = TILT / "tilt_study.json"
    sm = ROOT / "builds" / "sensor-Sony_ILCE-7RM3" / "c41" / ("%s_StatusM.cube" % stem)
    if not js.exists() or not sm.exists():
        return np.zeros((0, 3)), []
    size = int([l for l in open(sm) if l.startswith("LUT_3D_SIZE")][0].split()[1]); cube = read_cube(sm, size)
    rows, used = [], []
    for r in json.load(open(js))["rolls"]:
        if cube_stem(r["stock"]) != stem or not (ROOT / r["cache"]).exists():
            continue
        z = np.load(ROOT / r["cache"]); m = z["mean"][:, 35:-35, 35:-35].reshape(-1, 3)
        pick = m[rng.choice(len(m), N_FRAME, replace=False)]
        D = -np.log10(np.clip(pick, 1e-6, None)) - np.array(r["dmin_exr_scale"])
        rows.append(tetralerp_unit(cube, np.clip(D / DMAX, 0, 1))); used.append(r["folder"])
    return (np.concatenate(rows) if rows else np.zeros((0, 3))), used


def validation_set(full, stem, rng):
    """Inputs and controls: random coloured, control limits, real frames."""
    def coloured(n):
        g = rng.uniform(-0.05, 0.75, n)
        k = full.s_ext(g) + np.stack([rng.uniform(-0.15, 0.15, n), np.zeros(n), rng.uniform(-0.15, 0.15, n)], -1)
        return np.clip(k, 0.0, 1.0)

    def controls(n):
        gamma = np.exp(rng.uniform(np.log(0.5), np.log(2.0), n))
        trims = rng.uniform(-0.05, 0.05, (n, 3)) * (rng.random((n, 3)) < 0.3)
        return gamma, rng.uniform(-GAIN_RANGE, GAIN_RANGE, n), rng.uniform(0.05, 0.5, n), trims
    parts = []
    k = coloured(N_RANDOM); parts.append(("random", k, *controls(N_RANDOM)))
    lim = []
    for gm in (0.5, 1.0, 2.0):
        for pv in (0.05, K_MID, 0.5):
            for gn in (-GAIN_RANGE, 0.0, GAIN_RANGE):
                kk = coloured(N_LIMIT); n = len(kk)
                lim.append((kk, np.full(n, gm), np.full(n, gn), np.full(n, pv),
                            rng.uniform(-0.05, 0.05, (n, 3)) * (rng.random((n, 3)) < 0.3)))
    parts.append(("limits", *[np.concatenate([p[i] for p in lim]) for i in range(5)]))
    kf, rolls = frame_samples(stem, rng)
    if len(kf):
        parts.append(("frames", kf, *controls(len(kf))))
    return parts, rolls


def masks(curve, k, gamma, gain, pivot, trims):
    sup_in = curve.supported(k[:, 1])
    sup_out = curve.supported(destination(k, gamma, gain, pivot))
    pre = transform(k, curve, gamma, gain, pivot, trims, clip=False)
    unclipped = np.all((pre >= 0.0) & (pre <= 1.0), 1)
    return sup_in, sup_out, unclipped


def added_de(parts, full, cand, cube):
    worst = 0.0
    for _, k, gm, gn, pv, tr in parts:
        si, so, uc = masks(full, k, gm, gn, pv, tr)
        _, _, uc2 = masks(cand, k, gm, gn, pv, tr)
        m = si & so & uc & uc2
        if m.any():
            worst = max(worst, float(de(cube, transform(k[m], cand, gm[m], gn[m], pv[m], tr[m]),
                                         transform(k[m], full, gm[m], gn[m], pv[m], tr[m])).max()))
    return worst


# ---------------- DCTL emission ----------------
HEAD = r"""// Print Adjustment.dctl -- gamma / gain on the negative, before a print cube
//
// GENERATED by engine/c41/locus_follow_dctl.py (stock tables and this text); do
// not edit by hand: regenerate, and read the generator's acceptance report.
//
// PLACE IMMEDIATELY BEFORE a print-emulation cube. Nothing here is bound to a
// particular paper: it needs only that the incoming signal is NORMALIZED STATUS
// M DENSITY, k = OD / DMAX, D-min excluded, which is the shared input domain of
// the print branch. On the C-41 chain that means between
//   builds/c41/<Stock>_StatusM.cube                        (scanner -> Status M)
//   builds/c41/print_endura/<Stock>_to_PortraEndura_*.cube    (Kodak negatives)
//   builds/c41/print_fuji/<Stock>_to_FujiProLaser_*.cube      (Fujifilm negatives)
// -- the pairing rule is Kodak film -> Endura, Fujifilm film -> Fuji paper --
// and it will sit in front of any future paper built by PrintEmulationEngine
// on the same corridor (DMAX 3.30).
//
// Density is NOT linear light and NOT a display encoding, so do not reach for a
// normal gain/gamma tool at this node -- Resolve's would be operating on the
// wrong quantity. Defaults are a bit-exact no-op, whatever Locus Stock says.
//
// Two things follow from the domain, and both surprise people:
//
//  1. DENSITY RUNS BACKWARDS. Higher k = a denser negative = less light through
//     the enlarger = a LIGHTER print. Raise Gain and the print gets brighter.
//     True of any negative-to-print path, whatever the paper.
//  2. THE PRINTABLE WINDOW IS NARROW. It depends on the paper, negative and
//     calibrated exposure kernel. Each engine measures it on its neutral
//     ramp (the span over which the mean
//     print density sits 0.02 D clear of paper white and max black):
//
//       Portra 400 / Endura   k in [0.084, 0.346] = 0.86 OD   0.35 stop per 0.01 k
//       Fujifilm 400 / Fuji  k in [0.054, 0.344] = 0.96 OD   0.31 stop per 0.01 k
//
//     Endura uses 3200 K; Fuji uses the model's 473/532/685 nm laser kernel.
//     Window endpoints vary by up to 0.002 k across Kodak stocks and 0.012 k
//     across Fuji stocks. These two examples differ by ~0.10 OD, at the
//     shadow end. A move of 0.01 k is about a third of a stop on either --
//     so these really are small numbers. Outside the window it clips to paper
//     white / max black, as a real RA-4 print does.
//
// EXPECT TO LOWER GAMMA. The print cubes render an idealised print: no
// enlarger veiling flare, no print-surface glare, no viewing surround. None
// of those has a measured value, so none is baked in, and each one softens a
// real print -- the render sits at system gamma 3.07 per negative OD
// (measured on Portra 400 / Endura by the trim check's metric),
// above the effective contrast of any print viewed in a room. Gamma below 1.0
// here is the intended way to set final contrast, not the correction of an
// error. This slider changes slope uniformly about the pivot; real enlarger
// flare instead rolls off PRINT HIGHLIGHTS asymmetrically. If that shape
// specifically is wanted, PrintConfig.flare in the engine is the knob (gamma
// 3.07 -> 2.74 at flare 0.010), at the cost of a cube rebuild.
//
// Mode 1 -- DARKROOM (Literal Pow OFF, the default). The one to reach for.
//
//   Locus Stock Off:   k = pivot + (k - pivot) * gamma + gain
//
//   Gain  is a pure density offset: the grading analogue of enlarger exposure
//         (not a model of it; Status M is not printing density). The slider
//         runs to +/-%(gainrange).1f, enough to print down a negative about three stops
//         over on the modelled sheets (e.g. Gain -0.177 for Fujifilm 200 at +3
//         stops). With Locus Stock Off it moves all three channels equally,
//         along the diagonal; a stock's neutral series leaves the diagonal away
//         from mid-grey (below), so a large print-down also shifts colour.
//         Select the stock (LOCUS STOCK, below) and Gain follows the series.
//   Gamma is contrast about Pivot, which holds still while the ends fan out.
//         Pivot defaults to 0.22 = mid-gray, the k that renders Y = 0.18, and
//         that is true on EVERY cube in the fleet -- measured k = 0.2199 on all
//         ten, both papers, spread 0.0000 (2026-08-10). It cannot drift,
//         because K_MID is an INPUT to the gray-axis lock, not an output: with
//         mid_anchor="luminance" the lock solves the balancing offsets so that
//         K_MID lands on Y = 0.18 whatever the negative and whatever the paper,
//         and fuji_print_engine.py imports K_MID rather than defining its own.
//         The print renders the DIAGONAL neutral. A C-41 neutral does not read
//         equal in Status M, so each stock's Status M cube subtracts its
//         published neutral offset (engine/c41/neutral_locus.py) before this
//         node; the stock's neutral series then meets the diagonal at mid-grey
//         and departs from it elsewhere, printing a few units of a*/b* off
//         neutral (the stock's baseline casts). A per-channel gamma about a
//         pivot on the diagonal leaves a diagonal input on the diagonal instead
//         of tilting it by offset x (gamma - 1).
//         *** If K_MID in endura_print_engine.py ever changes, this default
//         must change with it. *** To pivot elsewhere, stay inside the window
//         above: on Endura ~0.15 is a shadow pivot and ~0.32 a highlight one;
//         Fuji's wider window allows ~0.10 and ~0.35.
//
// LOCUS STOCK (Darkroom mode only; Off by default). Set it to the negative's
// stock, the one whose Status M cube precedes this node. Gain and Gamma then
// move each pixel along that stock's published neutral series instead of along
// the diagonal (g = green, s = the stock's series):
//
//   g_new = Pivot + Gamma * (g - Pivot) + Gain
//   k_new = s_ext(g_new) + Gamma * (k - s_ext(g))
//   s_ext(x) = x + [s(h) - h],  h = x clamped to the series' support
//
// This is approximate, model-based EXPOSURE COMPENSATION: printing down an
// overexposed frame of a negative that matches its sheet returns it to the
// rendering of the correctly exposed frame, baseline casts included, instead of
// carrying the casts of denser tones down to mid-grey. It is a grading control
// with fixed sheet tables, never fitted to a scene; it is not a model of
// enlarger exposure, it is validated on the sheet's neutral series only, and it
// does not make the series neutral. It works best printing DOWN: printing up an
// underexposed frame drags shadows out of the toe, where a density offset is
// not an exposure change, and no Gain-type control can return them. s is
// piecewise linear on knots of the sheet series (exposure order, strictly
// increasing green); outside its support the series' departure from the
// diagonal is held constant (a declared fallback, not film data). A real
// negative's departure from its sheet varies with tone; constant per-channel
// offsets cannot remove it across tones, and this control does not address it.
//
// Locus Stock (%(uikind)s):
//   0  Off (plain Print Adjustment)
%(legend)s
//
// Mode 2 -- LITERAL (Literal Pow ON). Locus Stock has no effect here.
//
//   k = (1 + gain) * k ^ gamma
//
//   The plain power law, for when you want exactly that. Be aware of what it
//   does here: the fixed point of a power law is k = 1.0, and the whole image
//   sits below k = 0.41 (see the windows above), so Gamma reads mostly as a
//   large BRIGHTNESS shift
//   rather than as contrast -- at gamma 0.9, k 0.22 -> 0.257 and k 0.10 ->
//   0.126, i.e. both ends move the same way. It cannot open or close the tonal
//   range the way the pivoted slope can. Gain becomes a multiplier, written as
//   1 + gain so that 0.0 stays a no-op in both modes.
//
// PER-CHANNEL TRIM, both modes: Gain R/G/B are density offsets added after the
// master. A per-channel density offset at this node acts as printer-lights
// colour balance -- the same kind of adjustment as PrintConfig.printer_lights in
// PrintEmulationEngine, but live, with no cube rebuild. Sign follows the
// master: +R = more red density in the negative = a print with MORE red.
//
// *** TRAP: Gain R/G/B can hide an anchor error. ***
//
// RollAnchor_ScanPrep.dctl removes the roll's D-min as a per-channel offset in
// SCANNER density, upstream of the Status M cube. The cube is nonlinear, so an
// anchor error arrives at this node as a colour error that varies with density
// and colour, not as a constant offset. A trim here cancels it at one density
// and hides it there.
//
// Do not correct it here. The two belong to different stages and the split is
// load-bearing:
//
//   ANCHOR   physical, ONE setting for the whole roll, measured not judged
//            (roll_anchor_gui.py reads the actual clear base). Get it right
//            once and every frame on the roll is right.
//   THIS DCTL  interpretive, per shot or per timeline, judged by eye.
//
// Fix a colour cast here and you have made a per-frame correction to a per-roll
// physical error: it now travels with the grade, has to be redone on every
// clip, and drifts between them, while the anchor stays wrong. A cast has
// several possible sources: the stock's baseline casts away from mid-grey
// (above), the scene's illuminant, the negative's departure from its sheet, and
// the anchor. If a grey card at normal exposure in daylight will not sit near
// neutral at mid-grey with the trims at zero, re-measure the anchor first; do
// not dial it out. (Same reasoning as the flare /
// printer-lights placement in PrintEmulationEngine: a control belongs at the
// stage whose physics it describes.)
//
// Output is clamped to [0, 1], the cube's input domain. Clipping to 0 is a real
// consequence (no such thing as negative density), not a guard. The clamp acts
// per channel: a strongly coloured pixel can reach a face of the domain in one
// channel while it is still a mid-tone, and it loses colour information there
// (a large Gain makes this reachable). On the diagonal the faces print as
// paper black and paper white.
//
// Written in a deliberately plain style (single transform(), no helper
// functions, no __CONSTANT__, ASCII only) because Resolve rejected richer
// DCTLs here with "main DCTL function has wrong arguments". The named menu
// loads in Resolve with display names free of hyphens.%(uinote)s

DEFINE_UI_PARAMS(gamma, Gamma, DCTLUI_SLIDER_FLOAT, 1.0, 0.5, 2.0, 0.01)
DEFINE_UI_PARAMS(gain, Gain, DCTLUI_SLIDER_FLOAT, 0.0, -%(gainrange).1f, %(gainrange).1f, 0.001)
DEFINE_UI_PARAMS(pivot, Pivot, DCTLUI_SLIDER_FLOAT, 0.22, 0.05, 0.5, 0.01)
DEFINE_UI_PARAMS(gainR, Gain R, DCTLUI_SLIDER_FLOAT, 0.0, -0.05, 0.05, 0.001)
DEFINE_UI_PARAMS(gainG, Gain G, DCTLUI_SLIDER_FLOAT, 0.0, -0.05, 0.05, 0.001)
DEFINE_UI_PARAMS(gainB, Gain B, DCTLUI_SLIDER_FLOAT, 0.0, -0.05, 0.05, 0.001)
DEFINE_UI_PARAMS(literal, Literal Pow, DCTLUI_CHECK_BOX, 0)
%(stockparam)s

__DEVICE__ float3 transform(int p_Width, int p_Height, int p_X, int p_Y, float p_R, float p_G, float p_B)
{
    if (gamma == 1.0f && gain == 0.0f && gainR == 0.0f && gainG == 0.0f && gainB == 0.0f)
    {
        return make_float3(p_R, p_G, p_B);
    }

    float r = p_R;
    float g = p_G;
    float b = p_B;

    if (literal)
    {
        float m = 1.0f + gain;
        r = m * _powf(_fmaxf(r, 0.0f), gamma);
        g = m * _powf(_fmaxf(g, 0.0f), gamma);
        b = m * _powf(_fmaxf(b, 0.0f), gamma);
    }
    else if (stock == %(offkey)s)
    {
        r = pivot + (r - pivot) * gamma + gain;
        g = pivot + (g - pivot) * gamma + gain;
        b = pivot + (b - pivot) * gamma + gain;
    }
    else
    {
        float gout = pivot + (g - pivot) * gamma + gain;
        float dr0 = 0.0f;
        float db0 = 0.0f;
        float dr1 = 0.0f;
        float db1 = 0.0f;
        for (int e = 0; e < 2; e++)
        {
            float x = g;
            if (e == 1) x = gout;
            float h = x;
            float hr = x;
            float hb = x;
%(chain)s
            if (e == 0) { dr0 = hr - h; db0 = hb - h; }
            else { dr1 = hr - h; db1 = hb - h; }
        }
        r = (gout + dr1) + (r - (g + dr0)) * gamma;
        b = (gout + db1) + (b - (g + db0)) * gamma;
        g = gout;
    }

    r = r + gainR;
    g = g + gainG;
    b = b + gainB;

    r = _fminf(_fmaxf(r, 0.0f), 1.0f);
    g = _fminf(_fmaxf(g, 0.0f), 1.0f);
    b = _fminf(_fmaxf(b, 0.0f), 1.0f);

    return make_float3(r, g, b);
}
"""


def emit_stock(key, curve, first):
    g, R, B = [np.round(a, 7) for a in (curve.g, curve.R, curve.B)]
    if not np.all(np.diff(g) > 0):
        raise SystemExit("%s: knots collide after rounding to 7 decimals" % key)
    lines = ["            %sif (stock == %s)" % ("" if first else "else ", key), "            {",
             "                h = _fminf(_fmaxf(x, %.7ff), %.7ff);" % (g[0], g[-1])]
    n = len(g)
    for i in range(n - 1):
        sr = (R[i + 1] - R[i]) / (g[i + 1] - g[i]); sb = (B[i + 1] - B[i]) / (g[i + 1] - g[i])
        d = ("(h - %.7ff)" % g[i]) if g[i] >= 0 else ("(h + %.7ff)" % -g[i])
        body = "{ hr = %.7ff + %s * %.9ef; hb = %.7ff + %s * %.9ef; }" % (R[i], d, sr, B[i], d, sb)
        if i == 0 and n > 2:
            lines.append("                if (h <= %.7ff) %s" % (g[i + 1], body))
        elif i < n - 2:
            lines.append("                else if (h <= %.7ff) %s" % (g[i + 1], body))
        else:
            lines.append("                %s%s" % ("else " if n > 2 else "", body))
    lines.append("            }")
    return "\n".join(lines)


def write_dctl(path, rows, slider):
    legend = "\n".join("//  %2d  %-18s %3d knots, support k %.4f-%.4f" % (i + 1, r["stem"], len(r["curve"].g),
                                                                        r["curve"].g[0], r["curve"].g[-1])
                       for i, r in enumerate(rows))
    if slider:
        key = lambda i, stem: "%d" % (i + 1); off = "0"
        param = "DEFINE_UI_PARAMS(stock, Locus Stock, DCTLUI_SLIDER_INT, 0, 0, %d, 1)" % len(rows)
        uikind, uinote = "numbered int slider", ""
    else:
        key = lambda i, stem: "LS_" + stem.upper(); off = "LS_OFF"
        ids = ", ".join(["LS_OFF"] + [key(i, r["stem"]) for i, r in enumerate(rows)])
        labels = ", ".join(["Off"] + [r["name"] for r in rows])
        param = "DEFINE_UI_PARAMS(stock, Locus Stock, DCTLUI_COMBO_BOX, 0, { %s }, { %s })" % (ids, labels)
        uikind, uinote = "named menu", (" If Resolve refuses the menu, regenerate with --slider for\n"
                                        "// a numbered slider (same numbers as the list above).")
    chain = "\n".join(emit_stock(key(i, r["stem"]), r["curve"], i == 0) for i, r in enumerate(rows))
    Path(path).write_text(HEAD % {"legend": legend, "chain": chain, "stockparam": param, "offkey": off,
                                  "uikind": uikind, "uinote": uinote, "gainrange": GAIN_RANGE})
    return ["LS_OFF"] + ["LS_" + r["stem"].upper() for r in rows]


# ---------------- plain reference ----------------
# The plain Print Adjustment transform (Locus Stock Off and Literal mode must equal it
# bit for bit). Frozen here as the baseline the emitted file is checked against.
REFERENCE_DCTL = r"""DEFINE_UI_PARAMS(gamma, Gamma, DCTLUI_SLIDER_FLOAT, 1.0, 0.5, 2.0, 0.01)
DEFINE_UI_PARAMS(gain, Gain, DCTLUI_SLIDER_FLOAT, 0.0, -0.2, 0.2, 0.001)
DEFINE_UI_PARAMS(pivot, Pivot, DCTLUI_SLIDER_FLOAT, 0.22, 0.05, 0.5, 0.01)
DEFINE_UI_PARAMS(gainR, Gain R, DCTLUI_SLIDER_FLOAT, 0.0, -0.05, 0.05, 0.001)
DEFINE_UI_PARAMS(gainG, Gain G, DCTLUI_SLIDER_FLOAT, 0.0, -0.05, 0.05, 0.001)
DEFINE_UI_PARAMS(gainB, Gain B, DCTLUI_SLIDER_FLOAT, 0.0, -0.05, 0.05, 0.001)
DEFINE_UI_PARAMS(literal, Literal Pow, DCTLUI_CHECK_BOX, 0)

__DEVICE__ float3 transform(int p_Width, int p_Height, int p_X, int p_Y, float p_R, float p_G, float p_B)
{
    if (gamma == 1.0f && gain == 0.0f && gainR == 0.0f && gainG == 0.0f && gainB == 0.0f)
    {
        return make_float3(p_R, p_G, p_B);
    }

    float r = p_R;
    float g = p_G;
    float b = p_B;

    if (literal)
    {
        float m = 1.0f + gain;
        r = m * _powf(_fmaxf(r, 0.0f), gamma);
        g = m * _powf(_fmaxf(g, 0.0f), gamma);
        b = m * _powf(_fmaxf(b, 0.0f), gamma);
    }
    else
    {
        r = pivot + (r - pivot) * gamma + gain;
        g = pivot + (g - pivot) * gamma + gain;
        b = pivot + (b - pivot) * gamma + gain;
    }

    r = r + gainR;
    g = g + gainG;
    b = b + gainB;

    r = _fminf(_fmaxf(r, 0.0f), 1.0f);
    g = _fminf(_fmaxf(g, 0.0f), 1.0f);
    b = _fminf(_fmaxf(b, 0.0f), 1.0f);

    return make_float3(r, g, b);
}
"""


# ---------------- C harness ----------------
HARNESS = r"""#include <math.h>
#include <stdio.h>
typedef struct { float x, y, z; } float3;
static float3 make_float3(float a, float b, float c){ float3 v={a,b,c}; return v; }
#define __DEVICE__ static
static float _powf(float a, float b){ return powf(a,b); }
static float _fmaxf(float a, float b){ return fmaxf(a,b); }
static float _fminf(float a, float b){ return fminf(a,b); }
#define DEFINE_UI_PARAMS(name, label, type, ...) float name = 0;
#define DCTLUI_SLIDER_FLOAT 0
#define DCTLUI_SLIDER_INT 0
#define DCTLUI_CHECK_BOX 0
#define DCTLUI_COMBO_BOX 0
%(enum)s
#include "%(dut)s"
%(nostock)s
int main(void){
    float s,l,ga,gn,pv,a,b2,c,r,g,b;
    while (scanf("%%f %%f %%f %%f %%f %%f %%f %%f %%f %%f %%f",&s,&l,&ga,&gn,&pv,&a,&b2,&c,&r,&g,&b)==11){
        stock=s; literal=l; gamma=ga; gain=gn; pivot=pv; gainR=a; gainG=b2; gainB=c;
        float3 o=transform(0,0,0,0,r,g,b); printf("%%.9g %%.9g %%.9g\n",o.x,o.y,o.z);
    }
    return 0;
}
"""


def compile_dut(tmp, name, dctl, ids=None, has_stock=True):
    src = Path(tmp) / (name + ".c")
    src.write_text(HARNESS % {"enum": ("enum { %s };" % ", ".join(ids)) if ids else "", "dut": dctl,
                              "nostock": "" if has_stock else "float stock = 0;"})
    exe = Path(tmp) / name
    r = subprocess.run(["cc", "-O0", "-Wall", "-Wno-unused-function", str(src), "-o", str(exe), "-lm"],
                       capture_output=True, text=True)
    if r.returncode or r.stderr.strip():
        raise SystemExit("C compile of %s failed or warned:\n%s" % (name, r.stderr))
    return exe


def run_c(exe, rows):
    inp = "\n".join(" ".join("%.9g" % v for v in row) for row in rows)
    out = subprocess.run([str(exe)], input=inp, capture_output=True, text=True).stdout.split("\n")[:len(rows)]
    return out


def as_arr(lines):
    return np.array([l.split() for l in lines], float)


def rows_for(stock_id, k, gm, gn, pv, tr, literal=0):
    n = len(k)
    col = lambda v: np.broadcast_to(np.asarray(v, float), (n,))
    return np.column_stack([np.full(n, stock_id), np.full(n, literal), col(gm), col(gn), col(pv),
                            np.broadcast_to(np.asarray(tr, float), (n, 3)), k])


# ---------------- main ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slider", action="store_true", help="numbered int slider in place of the named menu")
    args = ap.parse_args()
    if abs(K_MID - 0.22) > 1e-12:
        raise SystemExit("K_MID is %.4f; the DCTL template hard-codes 0.22" % K_MID)
    rng = np.random.default_rng(20260930)
    PRT_n = prt_n(); stocks = sorted(STOCKS, key=cube_stem); rows = []
    print("SIMPLIFICATION (adaptive, full transform over the validation set)")
    print("stock               knots full/kept  dropped  tol k      curve err k  added dE2000 (double)  validation pts [frame rolls]")
    for s in stocks:
        L = series(s, PRT_n); stem = cube_stem(s)
        ncubes = check_offsets(stem, L.offset * DMAX)
        name = STOCKS[s]["display_name"]
        if not name.isascii() or any(ch in name for ch in ",{}-"):
            raise SystemExit("%s: display_name %r cannot be a menu label" % (stem, name))
        br = branch(L); full = Curve(br["g"], br["R"], br["B"])
        _, cube = print_cube(stem)
        parts, rolls = validation_set(full, stem, rng)
        tol = SIMPLIFY_START
        while True:
            idx, simp, err = simplify(br, tol)
            add = added_de(parts, full, simp, cube)
            if add <= ADDED_DE_MAX:
                break
            tol /= 2.0
            if tol < SIMPLIFY_FLOOR:
                raise SystemExit("%s: no simplification tolerance meets %.2f dE2000" % (stem, ADDED_DE_MAX))
        npts = sum(len(p[1]) for p in parts)
        slope = float(max(np.abs(np.diff(simp.R) / np.diff(simp.g)).max(), np.abs(np.diff(simp.B) / np.diff(simp.g)).max()))
        print("%-18s  %3d / %3d        %2d      %.2e   %.6f     %.4f                 %d %s   steepest segment |dR,dB/dg| %.1f"
              % (stem, len(br["g"]), len(idx), len(br["dropped"]), tol, err, add, npts, rolls, slope))
        rows.append(dict(stock=s, stem=stem, name=name, L=L, br=br, full=full, curve=simp, tol=tol,
                         curve_err=err, added_double=add, parts=parts, rolls=rolls, cube=cube, ncubes=ncubes,
                         line=Line(fit_line(L))))
    ids = write_dctl(OUT, rows, args.slider)
    report = dict(target="approximate model-based exposure compensation (option A)", stocks={})

    with tempfile.TemporaryDirectory() as tmp:
        menu_path = Path(tmp) / "menu.dctl"; slider_path = Path(tmp) / "slider.dctl"
        write_dctl(menu_path, rows, False); write_dctl(slider_path, rows, True)
        exe = compile_dut(tmp, "menu", menu_path, ids)
        exe_sl = compile_dut(tmp, "slider", slider_path)
        ref_path = Path(tmp) / "reference.dctl"; ref_path.write_text(REFERENCE_DCTL)
        exe_pa = compile_dut(tmp, "plain", ref_path, has_stock=False)
        fails = []

        # ---- 5a: emitted vs references ----
        print("\n5a  EMITTED C vs references (coordinate error on supported points; dE on supported + unclipped)")
        print("stock               max coord err vs simplified double k   max added dE2000 vs full branch   supported/unsup-in/unsup-dest/clipped")
        allrows = []
        for i, r in enumerate(rows):
            ks, gms, gns, pvs, trs = [np.concatenate([p[j] for p in r["parts"]]) for j in range(1, 6)]
            R_ = rows_for(i + 1, ks, gms, gns, pvs, trs); allrows.append(R_)
            outc = as_arr(run_c(exe, R_))
            ref_s = transform(ks, r["curve"], gms, gns, pvs, trs)
            ref_f = transform(ks, r["full"], gms, gns, pvs, trs)
            si, so, uc = masks(r["full"], ks, gms, gns, pvs, trs)
            sup = si & so
            cerr = float(np.abs(outc - ref_s)[sup].max())
            m = sup & uc
            dmax = float(de(r["cube"], outc[m], ref_f[m]).max())
            counts = [int(sup.sum()), int((~si).sum()), int((si & ~so).sum()), int((sup & ~uc).sum())]
            print("%-18s  %.2e                               %.4f                            %s"
                  % (r["stem"], cerr, dmax, "/".join(map(str, counts))))
            if cerr > NUM_TOL: fails.append("%s 5a coordinate error %.2e" % (r["stem"], cerr))
            if dmax > ADDED_DE_MAX: fails.append("%s 5a added dE %.4f" % (r["stem"], dmax))
            if not np.all(np.isfinite(outc)): fails.append("%s non-finite output" % r["stem"])
            report["stocks"][r["stem"]] = dict(knots_full=len(r["br"]["g"]), knots_kept=len(r["curve"].g),
                dropped_knots=r["br"]["dropped"], support_k=[float(r["curve"].g[0]), float(r["curve"].g[-1])],
                simplify_tol_k=r["tol"], curve_err_k=r["curve_err"], added_de_double=r["added_double"],
                emitted_coord_err_k=cerr, emitted_added_de=dmax, validation_counts=dict(
                    supported=counts[0], unsupported_input=counts[1], unsupported_destination=counts[2],
                    supported_clipped=counts[3]), frame_rolls=r["rolls"], statusm_cubes_checked=r["ncubes"])

        # ---- 5b: behaviour ----
        print("\n5b  BEHAVIOUR (emitted C)")
        big = np.concatenate(allrows)
        same = run_c(exe, big) == run_c(exe_sl, big)
        print("  menu build vs --slider build, %d rows: %s" % (len(big), "BIT-IDENTICAL" if same else "DIFFER"))
        if not same: fails.append("menu vs slider differ")
        N = 20000
        rr = np.column_stack([np.zeros(N), rng.integers(0, 2, N), rng.uniform(0.5, 2, N), rng.uniform(-0.2, 0.2, N),
                              rng.uniform(0.05, 0.5, N), rng.uniform(-0.05, 0.05, (N, 3)) * (rng.random((N, 3)) < 0.5),
                              rng.uniform(0, 1, (N, 3))])
        rr[::5, 2] = 1.0; rr[::7, 3] = 0.0
        ok = run_c(exe, rr) == run_c(exe_pa, rr)
        print("  Off vs plain reference transform, %d random rows (both modes): %s" % (N, "BIT-IDENTICAL" if ok else "DIFFER"))
        if not ok: fails.append("Off differs from the plain reference")
        lit = rr.copy(); lit[:, 0] = rng.integers(1, len(rows) + 1, N); lit[:, 1] = 1
        ok = run_c(exe, lit) == run_c(exe_pa, lit)
        print("  Literal, every stock, vs plain reference transform, %d rows: %s" % (N, "BIT-IDENTICAL" if ok else "DIFFER"))
        if not ok: fails.append("Literal differs")
        dfl = rr.copy(); dfl[:, 0] = rng.integers(0, len(rows) + 1, N); dfl[:, 1] = 0; dfl[:, 2] = 1; dfl[:, 3] = 0; dfl[:, 5:8] = 0
        lines_d = run_c(exe, dfl)
        # compare in float32: the harness parses each "%.9g" input into a float and prints the float
        # with 9 significant digits, which round-trips a float exactly
        inp32 = np.array([[np.float32(float("%.9g" % v)) for v in row] for row in dfl[:, 8:11]], np.float32)
        ok = np.array_equal(as_arr(lines_d).astype(np.float32), inp32) and lines_d == run_c(exe_pa, dfl)
        print("  defaults (Gamma 1, Gain 0, trims 0), every setting: %s" % ("BIT-IDENTICAL to input" if ok else "CHANGED"))
        if not ok: fails.append("defaults change the input")

        cont = {}
        gm, gn, pv = 1.25, 0.05, K_MID
        for eps in (1e-3, 1e-4, 1e-5):
            worst = 0.0
            for i, r in enumerate(rows):
                gk = r["curve"].g; n = len(gk)
                for mode in ("input", "destination"):
                    gc = gk if mode == "input" else pv + (gk - gn - pv) / gm
                    dep = np.array([0.03, 0.0, -0.02])
                    kmid = r["full"].s_ext(gc) + dep
                    klo = kmid.copy(); khi = kmid.copy(); klo[:, 1] = gc - eps; khi[:, 1] = gc + eps
                    a = as_arr(run_c(exe, rows_for(i + 1, klo, gm, gn, pv, np.zeros(3))))
                    b = as_arr(run_c(exe, rows_for(i + 1, khi, gm, gn, pv, np.zeros(3))))
                    inside = np.all((a > 0) & (a < 1) & (b > 0) & (b < 1), 1)
                    if inside.any():
                        worst = max(worst, float(np.abs(a - b)[inside].max()))
            cont[eps] = worst
        print("  continuity at every knot and support end, green crossing it as input and as destination"
              " (Gamma 1.25, Gain 0.05):\n    " + "   ".join("separation %.0e -> max jump %.2e" % (2 * e, w) for e, w in cont.items()))
        if cont[1e-5] > 10 * 2e-5 + 2e-6: fails.append("discontinuity: jump %.2e at separation 2e-5" % cont[1e-5])
        report["continuity_max_jump_by_separation"] = {("%.0e" % (2 * e)): w for e, w in cont.items()}

        rev = inv = 0.0; nrev = ninv = 0
        for i, r in enumerate(rows):
            k = np.concatenate([p[1] for p in r["parts"]])[:4000]; n = len(k)
            gnv = rng.uniform(-0.2, 0.2, n); pvv = rng.uniform(0.05, 0.5, n); z = np.zeros(3)
            o1 = as_arr(run_c(exe, rows_for(i + 1, k, 1.0, gnv, pvv, z)))
            o2 = as_arr(run_c(exe, rows_for(i + 1, o1, 1.0, -gnv, pvv, z)))
            m = np.all((o1 > 0) & (o1 < 1) & (o2 > 0) & (o2 < 1), 1) & (gnv != 0)
            rev = max(rev, float(np.abs(o2 - k)[m].max())); nrev += int(m.sum())
            gmv = np.exp(rng.uniform(np.log(0.5), np.log(2.0), n))
            o1 = as_arr(run_c(exe, rows_for(i + 1, k, gmv, gnv, pvv, z)))
            o2 = as_arr(run_c(exe, rows_for(i + 1, o1, 1.0 / gmv, -gnv / gmv, pvv, z)))
            m = np.all((o1 > 0) & (o1 < 1) & (o2 > 0) & (o2 < 1), 1)
            inv = max(inv, float(np.abs(o2 - k)[m].max())); ninv += int(m.sum())
        print("  +Gain then -Gain at Gamma 1 (unclipped, %d pts): max |error| %.2e k" % (nrev, rev))
        print("  inverse at general Gamma (1/Gamma, -Gain/Gamma, same Pivot; unclipped, %d pts): max |error| %.2e k" % (ninv, inv))
        if rev > NUM_TOL: fails.append("Gain reversal error %.2e" % rev)
        if inv > NUM_TOL: fails.append("inverse round-trip error %.2e" % inv)
        report.update(gain_reversal_max_err=rev, inverse_roundtrip_max_err=inv)

    # ---- 5c/5d: coverage and the reported goal (double references) ----
    print("\n5c/5d  TRUE EXPOSURE BRACKETS (reported; goal mean <= %.0f, max <= %.0f dE2000; '!' = curve misses the goal,"
          " '*' = Gain beyond +/-%.1f)" % (GOAL[0], GOAL[1], GAIN_RANGE))
    print("stock              n   Gain      kept/excl/unsup/clip   plain mean/max   line mean/max   curve mean/max    exact-locus ref")
    for r in rows:
        lh, bal = exposure_series(r["L"])
        at = lambda x: np.stack([np.interp(x, lh, bal[:, c]) for c in range(3)], -1)
        tones = np.arange(lh.min(), lh.max() + 1e-9, 0.05)
        tones = tones[(at(tones)[:, 1] >= K_MID - MID_BAND) & (at(tones)[:, 1] <= K_MID + MID_BAND)]
        ref = at(tones); lh_mid = np.interp(K_MID, bal[:, 1], lh); br_rep = []
        for n in (-3, -2, -1, 1, 2, 3):
            inside = (tones + n * LOG2 <= lh.max()) & (tones + n * LOG2 >= lh.min())
            gain = K_MID - at(lh_mid + n * LOG2)[1]
            ks = at(tones[inside] + n * LOG2); m_ = len(ks)
            si, so, uc = masks(r["curve"], ks, 1.0, gain, K_MID, None)
            ok = si & so & uc
            cells = []
            for cv in (None, r["line"], r["curve"], r["full"]):
                d = de(r["cube"], transform(ks[ok], cv, 1.0, gain, K_MID), ref[inside][ok])
                cells.append((float(d.mean()), float(d.max())))
            flag = "!" if (cells[2][0] > GOAL[0] or cells[2][1] > GOAL[1]) else " "
            print("%-18s %+d  %+.4f%s  %3d/%2d/%2d/%2d          %5.2f/%5.2f      %5.2f/%5.2f     %5.2f/%5.2f%s     %5.2f/%5.2f"
                  % (r["stem"], n, gain, "*" if abs(gain) > GAIN_RANGE else " ", int(ok.sum()), int((~inside).sum()),
                     int((~(si & so)).sum()), int((si & so & ~uc).sum()), *cells[0], *cells[1], *cells[2], flag, *cells[3]))
            br_rep.append(dict(n=n, gain=gain, kept=int(ok.sum()), excluded=int((~inside).sum()),
                               unsupported=int((~(si & so)).sum()), clipped=int((si & so & ~uc).sum()),
                               plain=cells[0], line=cells[1], curve=cells[2], exact_locus_reference=cells[3],
                               goal_met=flag == " "))
        report["stocks"][r["stem"]]["brackets"] = br_rep

    print("\nGAMMA x PIVOT x GAIN over the control limits (Gamma 0.5/0.8/1.25/2, Pivot 0.05/0.15/0.22/0.30/0.5,"
          " Gain -0.1/0/+0.1),\ncorrect-exposure ramp: max dE2000 vs the sheet's own render at the same green"
          " (supported, unclipped); worst setting (Gamma, Pivot, Gain)")
    for r in rows:
        lh, bal = exposure_series(r["L"])
        tones = bal[(bal[:, 1] >= K_MID - MID_BAND) & (bal[:, 1] <= K_MID + MID_BAND)]
        own = lambda out: np.stack([np.interp(out[:, 1], r["full"].g, r["full"].R), out[:, 1],
                                    np.interp(out[:, 1], r["full"].g, r["full"].B)], -1)
        worst = {"plain": (0.0, None), "curve": (0.0, None)}
        for gm in (0.5, 0.8, 1.25, 2.0):
            for pv in (0.05, 0.15, K_MID, 0.30, 0.5):
                for gn in (-0.1, 0.0, 0.1):
                    si, so, uc = masks(r["curve"], tones, gm, gn, pv, None)
                    ok = si & so & uc
                    if not ok.any():
                        continue
                    for key, cv in (("plain", None), ("curve", r["curve"])):
                        out = transform(tones[ok], cv, gm, gn, pv)
                        v = float(de(r["cube"], out, own(out)).max())
                        if v > worst[key][0]:
                            worst[key] = (v, (gm, pv, gn))
        print("  %-18s plain %5.2f at %-18s curve %5.2f at %s" % (r["stem"], worst["plain"][0], worst["plain"][1],
                                                                  worst["curve"][0], worst["curve"][1]))
        report["stocks"][r["stem"]]["gamma_pivot_gain_worst"] = worst

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1, default=float) + "\n")
    print("\nwrote %s (%s)" % (OUT.relative_to(ROOT), "slider" if args.slider else "named menu"))
    print("report %s" % REPORT.relative_to(ROOT))
    if fails:
        raise SystemExit("ACCEPTANCE FAILED:\n  " + "\n  ".join(fails))
    print("ACCEPTANCE: 5a and 5b pass on every stock")


if __name__ == "__main__":
    main()
