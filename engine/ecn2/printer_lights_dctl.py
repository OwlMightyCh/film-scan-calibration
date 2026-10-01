#!/usr/bin/env python3
"""Write and verify dctl/output/Printer Lights ADX16.dctl, with its Locus Stock Master (ECN-2, Vision3).

The ADX16 cube emits the negative's untrimmed image-dye Academy Printing Density
(APD) as ST 2065-3 code values. An equal Master offset moves all three channels
by the same APD. Vision3's APD green is steeper than its red and blue, so an
equal print-down of an overexposed frame leaves it green-cyan and an equal
print-up leaves it magenta. Locus Stock moves each pixel along the stock's
neutral series instead.

GREY PLACEMENT. The Academy decode anchors a reference negative's grey at
0.70 D; a Vision3 grey sits elsewhere, so the decoded grey of a correctly
exposed frame misses AP0 0.18 by a per-stock offset and spread. Each stock
carries its grey trims b_c: the per-channel APD trims that place the cube
output of the stock's mid-grey (L = 1) at AP0 0.18 on each channel through
the Academy decode (adx_validate.solve_apd_trims), held at float32. Setting
Locus Stock applies them; the user trims are offsets from them. Locus Stock
Off applies none.

TARGET = APPROXIMATE, MODEL-BASED EXPOSURE COMPENSATION: an optional grading
control with fixed tables, never fitted to scene statistics. The bracket check
uses the scene engine's forward model, which shares the characteristic curves
with the tables and has no interimage (DIR_MATRIX identity), so it tests the
neutral-locus approximation against that model and nothing more. No measured
Vision3 exposure bracket exists. Printing up an underexposed frame keeps larger
colour errors: no neutral control inverts each layer's exposure response.

TABLE. Per stock, sensor-free: the scene engine's neutral series (logH over the
engine's neutral axis, N_DENSE points) scanned through the sensor-free
'Vision3 to ADX16.cube' (tetrahedral), in untrimmed APD. Rows outside the cube
domain are dropped; the knots used as a function of green APD g are the strictly
increasing branch (running maximum), dropped knots counted, never re-sorted. The
exact cube output of the mid-grey (L = 1) is a protected knot. The branch is the
SUPPORT [g_min, g_max].

RULE (Locus Stock set), with q_c(x) = s_c(h) - h, h = clamp(x, g_min, g_max):
    g_new = g + Master
    d_c   = q_c(g_new) - q_c(g)        c in {R, B}; d_G = 0
    CV_c += (trim_c + Master + d_c + b_c) * k_c * 8000/65535
Locus Stock Off is the plain printer-lights transform (REFERENCE_DCTL below),
with the identity fast path at Master 0 and trims 0. No clamp anywhere.

SIMPLIFICATION (adaptive). Top-down split of the full branch at its worst knot
until every original knot lies within tol of the chord between its kept
neighbours (R and B), endpoints and mid-grey kept; tol starts at SIMPLIFY_START D
and halves until the simplified transform stays within ADDED_DE_MAX dE2000 of
the full-branch transform over the validation set (random coloured inputs,
control limits, exposure brackets), decoded by the Academy ADX16 decode,
supported points only.

ACCEPTANCE (the run FAILS on any of these), on the emitted DCTL compiled as C:
  5a  emitted vs simplified double reference: max APD error <= NUM_TOL D
      (supported); emitted vs full branch: max added dE2000 <= ADDED_DE_MAX
      (supported); outputs finite;
  5b  menu build bit-identical to the --slider build; Off bit-identical to
      REFERENCE_DCTL; Off at defaults bit-identical to the input; each stock
      at defaults bit-identical to REFERENCE_DCTL with trims = b_c, and its
      mid-grey decoded within GREY_TOL of AP0 0.18 on each channel;
      continuity at every knot and support end, as the input and the destination
      cross it, by shrinking separation; +Master then -Master (trims zero)
      returns the input within NUM_TOL D (supported), user trims -b_c;
  5e  cross-sensor: for every builds/sensor-*/ apparatus, the exact maximum over
      the common support and |Master| <= MASTER_RANGE of the correction error
      E_c(g, M) = e_c(g + M) - e_c(g), e_c = universal q_c - apparatus q_c,
      is <= SENSOR_E_TOL D.
REPORTED (not enforced): grey placement per stock (b_c, the decoded grey at
Off defaults); per apparatus, its own grey trims against the universal b_c and
its mid-grey decoded under b_c; 5c coverage and 5d the goal (mean <= 1, max <= 2
dE2000) on exposure brackets n = +-1, +-2, +-3, sensor-free: printer lights,
ACES gain, a straight line, the emitted curve, the exact dense locus; the
cross-sensor tails and rendered correction; the table source comparisons
(own-dye APD of the sheet series, Annex C).

CROSS-SENSOR. One table per stock serves every scanner build; 5e checks it
against each per-camera cube.

Usage:
    python3 engine/ecn2/printer_lights_dctl.py [--slider]
Report: builds/_forensics/printer_lights_adx16/report.json. Needs a C compiler (cc).
"""
import argparse, json, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
import colour
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from engine.common.lut import read_cube, tetralerp_unit   # noqa: E402
from engine.common.spectral import interp_lin              # noqa: E402
from engine.ecn2 import v3_scene_engine as v3              # noqa: E402
from engine.ecn2 import adx_validate as av                 # noqa: E402
from engine.ecn2 import annexc_check as ax                 # noqa: E402
from engine.c41.locus_follow_dctl import Curve, emit_stock, run_c, as_arr   # noqa: E402

DATA = ROOT / "data"
OUT = ROOT / "dctl" / "output" / "Printer Lights ADX16.dctl"
REPORT = ROOT / "builds" / "_forensics" / "printer_lights_adx16" / "report.json"
CUBE_NAME = Path("ecn2") / "Vision3 to ADX16.cube"
SZ = 65

K = np.array(av.K_ST2065_3, float)          # ST 2065-3: (1.00, 0.92, 0.95)
CV0 = 1520.0 / 65535.0
SCALE = K * 8000.0 / 65535.0                # CV = APD * SCALE + CV0
MASTER_RANGE = 0.6                          # slider +/-, D
TRIM_RANGE = 0.5
SIMPLIFY_START = 5e-4                       # D
SIMPLIFY_FLOOR = 1e-6
ADDED_DE_MAX = 0.1                          # dE2000 through the Academy decode
NUM_TOL = 1e-5                              # D
SENSOR_E_TOL = 0.0025                       # D, cross-sensor correction gate
GREY_TOL = 1e-4                             # AP0, stock defaults place mid-grey at 0.18
GOAL = (1.0, 2.0)
LOG2 = np.log10(2.0)
N_DENSE = 4001
N_RANDOM, N_LIMIT = 15000, 200
NS = (-3, -2, -1, 1, 2, 3)
ANNEX_KEYS = {"250D": "Eastman Kodak 5207", "500T": "Eastman Kodak 5219"}


def enc(apd):
    return np.asarray(apd, float) * SCALE + CV0


def unenc(cv):
    return (np.asarray(cv, float) - CV0) / SCALE


def lab(cv):
    return colour.XYZ_to_Lab(av.aces_to_xyz_d65(av.adx16_to_aces(np.atleast_2d(cv))), av.D65)


def de(la, lb):
    return colour.delta_E(la, lb, method="CIE 2000")


def cube_lookup(lut, scan):
    return tetralerp_unit(lut, np.clip(np.atleast_2d(scan), 0.0, 1.0))


def grey_Y(cv):
    return float(av.aces_to_xyz_d65(av.adx16_to_aces(np.atleast_2d(cv)))[0, 1])


# ---------------- table (b) ----------------
def dense_table(e, lut):
    """Neutral series of engine e through cube lut, in untrimmed APD. Returns the strictly
    increasing green branch (g, R, B, h), the mid knot index, and the unfiltered valid rows
    (hv, apdv) for logH-parametrised lookups."""
    hh = np.linspace(e.neutral_logH[0], e.neutral_logH[-1], N_DENSE)
    scan = e.L_to_scan_norm(np.repeat((10.0 ** (hh - e.logH_mid))[:, None], 3, axis=1))
    valid = np.all((scan >= 0.0) & (scan <= 1.0), 1)
    hv = hh[valid]; apdv = unenc(tetralerp_unit(lut, scan[valid]))
    G = apdv[:, 1]
    keep = np.r_[True, G[1:] > np.maximum.accumulate(G)[:-1]]
    g, R, B, h = G[keep], apdv[keep, 0], apdv[keep, 2], hv[keep]
    if not (np.all(np.isfinite(g)) and np.all(np.isfinite(R)) and np.all(np.isfinite(B))):
        raise SystemExit("%s: non-finite dense table" % e.p["display_name"])
    cv_mid = tetralerp_unit(lut, e.L_to_scan_norm(np.ones((1, 3))))[0]
    apd_mid = unenc(cv_mid)
    if not g[0] < apd_mid[1] < g[-1]:
        raise SystemExit("%s: mid-grey green %.4f D outside support %.4f-%.4f" % (e.p["display_name"], apd_mid[1], g[0], g[-1]))
    if not np.any(g == apd_mid[1]):
        i = int(np.searchsorted(g, apd_mid[1]))
        g = np.insert(g, i, apd_mid[1]); R = np.insert(R, i, apd_mid[0]); B = np.insert(B, i, apd_mid[2])
        h = np.insert(h, i, e.logH_mid)
    if not np.all(np.diff(g) > 0):
        raise SystemExit("%s: kept branch is not strictly increasing" % e.p["display_name"])
    if not np.any(hv == e.logH_mid):
        j = int(np.searchsorted(hv, e.logH_mid))
        hv = np.insert(hv, j, e.logH_mid); apdv = np.insert(apdv, j, apd_mid, axis=0)
    return dict(g=g, R=R, B=B, h=h, mid=int(np.where(g == apd_mid[1])[0][0]), dropped=int((~keep).sum()),
                cv_mid=cv_mid, apd_mid=apd_mid, hv=hv, apdv=apdv)


def at_logH(tab, hq):
    return np.stack([np.interp(hq, tab["hv"], tab["apdv"][:, c]) for c in range(3)], -1)


def grey_move(e, lut, tab, n):
    """Master returning the grey bracketed by n stops to mid green."""
    cv = cube_lookup(lut, e.L_to_scan_norm(np.full((1, 3), 2.0 ** n)))[0]
    return float(tab["apd_mid"][1] - unenc(cv)[1]), cv


# ---------------- transform (double reference) ----------------
def transform(cv, curve, master, trims):
    """Per-row controls; curve None = Locus Stock Off."""
    cv = np.atleast_2d(np.asarray(cv, float)); n = len(cv)
    m = np.broadcast_to(np.asarray(master, float), (n,))
    tr = np.broadcast_to(np.asarray(trims, float), (n, 3))
    d = np.zeros((n, 3))
    if curve is not None:
        g = unenc(cv)[:, 1]; gn = g + m
        d = (curve.s_ext(gn) - gn[:, None]) - (curve.s_ext(g) - g[:, None])
        d[:, 1] = 0.0
    out = cv + (tr + m[:, None] + d) * SCALE
    fast = (m == 0.0) & np.all(tr == 0.0, 1)
    out[fast] = cv[fast]
    return out


def support_masks(curve, cv, master):
    g = unenc(cv)[:, 1]
    return curve.supported(g), curve.supported(g + master)


# ---------------- simplification ----------------
def simplify(tab, tol):
    """Top-down split at the worst knot until every original knot between kept neighbours
    lies within tol of their chord (R and B); endpoints and mid kept."""
    g, R, B = tab["g"], tab["R"], tab["B"]
    n = len(g); keep = {0, n - 1, tab["mid"]}
    stack = [(0, tab["mid"]), (tab["mid"], n - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        t = (g[a:b + 1] - g[a]) / (g[b] - g[a])
        err = np.maximum(np.abs(R[a] + t * (R[b] - R[a]) - R[a:b + 1]), np.abs(B[a] + t * (B[b] - B[a]) - B[a:b + 1]))
        j = int(np.argmax(err))
        if err[j] > tol:
            keep.add(a + j); stack += [(a, a + j), (a + j, b)]
    idx = np.array(sorted(keep))
    simp = Curve(g[idx], R[idx], B[idx])
    s = simp.s_ext(g)
    return idx, simp, float(max(np.abs(s[:, 0] - R).max(), np.abs(s[:, 2] - B).max()))


# ---------------- validation set ----------------
def trims_rule(rng, tb, n):
    return tb[None, :] + rng.uniform(-0.05, 0.05, (n, 3)) * (rng.random((n, 3)) < 0.3)


def bracket_sets(e):
    return [("CC24", e.cc_L)] + [(k, v[0]) for k, v in e.broad_sets.items()]


def validation_set(e, lut, tab, full, tb, rng):
    """Parts (name, cv, master, trims), inputs kept only with CV in [0, 1]."""
    def coloured(n):
        g = rng.uniform(full.g[0] - 0.1, full.g[-1] + 0.1, n)
        apd = full.s_ext(g) + np.stack([rng.uniform(-0.15, 0.15, n), np.zeros(n), rng.uniform(-0.15, 0.15, n)], -1)
        return enc(apd)
    parts = [("random", coloured(N_RANDOM), rng.uniform(-MASTER_RANGE, MASTER_RANGE, N_RANDOM), trims_rule(rng, tb, N_RANDOM))]
    lim = []
    for m in (-MASTER_RANGE, 0.0, MASTER_RANGE):
        lim.append((coloured(N_LIMIT), np.full(N_LIMIT, m), trims_rule(rng, tb, N_LIMIT)))
    parts.append(("limits", *[np.concatenate([p[i] for p in lim]) for i in range(3)]))
    br = []
    for _, L in bracket_sets(e):
        for n in range(-3, 4):
            move, _ = grey_move(e, lut, tab, n)
            cv = cube_lookup(lut, e.L_to_scan_norm(L * 2.0 ** n))
            br.append((cv, np.full(len(cv), move), np.broadcast_to(tb, (len(cv), 3)).copy()))
    parts.append(("brackets", *[np.concatenate([p[i] for p in br]) for i in range(3)]))
    out = []
    for name, cv, m, tr in parts:
        ok = np.all((cv >= 0.0) & (cv <= 1.0), 1)
        out.append((name, cv[ok], m[ok], tr[ok]))
    return out


def added_de(parts, full, cand, ref_labs):
    worst = 0.0
    for (_, cv, m, tr), (sup, lref) in zip(parts, ref_labs):
        if sup.any():
            worst = max(worst, float(de(lab(transform(cv[sup], cand, m[sup], tr[sup])), lref).max()))
    return worst


# ---------------- DCTL emission ----------------
HEAD = r"""// Printer Lights ADX16.dctl -- per-channel density trims on ADX16 code values
//
// GENERATED by engine/ecn2/printer_lights_dctl.py (stock tables and this
// text); do not edit by hand: regenerate, and read the generator's report.
//
// Place AFTER "Vision3 to ADX16.cube" and BEFORE the transform that decodes
// ADX16 to ACES (CSC.Academy.ADX16_to_ACES; in Resolve, input colour space
// "ADX (16-bit)").
//
// This is the AESTHETIC slot of the ADX16 chain (metric/aesthetic
// separation): the cube emits the negative's honest Academy Printing Density,
// and the Academy decode reads it against the decode's own reference-film
// assumption, so the decoded image carries a balance offset and a grey-axis
// channel spread -- removed here, not in the anchor, preshaper, or cube.
// A per-channel trim on grey is expected use of this chain, not a defect.
//
// Trims are entered in DENSITY (OD) of image-dye printing density
// (APD - APD_Dmin): +0.30 D on a channel is about 1 stop more of that colour
// in the decoded positive; negative reduces it. Master is the exposure
// control. The ST 2065-3 per-channel factors k = (1.00, 0.92, 0.95) belong
// to the code-value encoding and are applied below, so sliders read in true
// APD.
//
// GREY PLACEMENT. Setting Locus Stock to the negative's stock applies that
// stock's grey trims (listed below): they place a correctly exposed 18%%
// grey on the stock's published neutral series at AP0 0.18 on each channel
// after the decode. Without them that grey decodes at
// %(darkest)s
// stops from 0.18 in Y. The sliders then read as offsets
// from the grey placement: at zero, a datasheet-exposed grey decodes
// neutral at 0.18. The grey trims are model-derived (the scene engine's
// neutral through the sensor-free cube); the rig, the roll and its
// processing add their own offset, so dial the sliders on a known neutral
// at normal exposure, once per stock/rig, and reuse them across rolls.
// With Locus Stock Off nothing is added: the sliders are the whole trim,
// and the same image needs the grey trims added to them.
//
// LOCUS STOCK (Off by default). With the stock Off, Master adds the same
// APD to all three channels, the plain printer-lights behaviour. Vision3's
// APD green is steeper than its red and blue, so an equal print-down of an
// overexposed frame turns it green-cyan, and an equal print-up turns it
// magenta. Set Locus Stock to the negative's stock and Master moves each
// pixel along that stock's neutral series (g = green APD, c = red or blue,
// q_c(x) = the series' c minus its g at green x):
//
//   g_new = g + Master
//   c_new = c + Master + q_c(h(g_new)) - q_c(h(g)),  h = g clamped to the
//                                                    series' support
//
// then the trims and the stock's grey trims.
//
// This is approximate, model-based EXPOSURE COMPENSATION: a grading control
// with fixed tables, never fitted to a scene. Each table is the scene
// engine's neutral series for the stock, scanned through the sensor-free
// ADX16 cube, in the cube's untrimmed APD. One table per stock serves every
// scanner build; the generator checks it against each per-camera cube. The
// control works best printing DOWN an overexposed frame. Printing up an
// underexposed frame draws shadows out of the toe, where no neutral control
// inverts each layer's exposure response, and colours keep larger errors
// there. The evidence is a model check: the scene engine's forward model
// shares the characteristic curves with the tables and has no interimage,
// and no measured Vision3 exposure bracket exists. Outside the series'
// support the departure is held constant (a declared fallback, not film
// data). The slider runs to +/-%(masterrange).1f D, enough to undo three stops either
// way on all four stocks.
//
// Locus Stock (%(uikind)s):
//   0  Off (equal printer lights, no grey trims)
%(legend)s
//
// Written in a deliberately plain style (single transform(), no helper
// functions, no __CONSTANT__, ASCII only) because Resolve rejected richer
// DCTLs with "main DCTL function has wrong arguments". The named menu loads
// in Resolve with display names free of hyphens.%(uinote)s

DEFINE_UI_PARAMS(trimR, Trim R density, DCTLUI_SLIDER_FLOAT, 0.0, -0.5, 0.5, 0.001)
DEFINE_UI_PARAMS(trimG, Trim G density, DCTLUI_SLIDER_FLOAT, 0.0, -0.5, 0.5, 0.001)
DEFINE_UI_PARAMS(trimB, Trim B density, DCTLUI_SLIDER_FLOAT, 0.0, -0.5, 0.5, 0.001)
DEFINE_UI_PARAMS(master, Master density, DCTLUI_SLIDER_FLOAT, 0.0, -%(masterrange).1f, %(masterrange).1f, 0.001)
%(stockparam)s

__DEVICE__ float3 transform(int p_Width, int p_Height, int p_X, int p_Y, float p_R, float p_G, float p_B)
{
    // APD -> normalized ADX16 CV (ST 2065-3 eq. 1): CV = k*APD*8000 + 1520,
    // written as CV/65535, so an APD offset lands as k*8000/65535 per channel
    const float D_TO_CV = 8000.0f / 65535.0f;

    if (stock == %(offkey)s)
    {
        if (master == 0.0f && trimR == 0.0f && trimG == 0.0f && trimB == 0.0f)
        {
            return make_float3(p_R, p_G, p_B);
        }
        return make_float3(p_R + (trimR + master) * 1.00f * D_TO_CV,
                           p_G + (trimG + master) * 0.92f * D_TO_CV,
                           p_B + (trimB + master) * 0.95f * D_TO_CV);
    }

    // the stock's grey trims (APD, D)
    float br = 0.0f;
    float bg = 0.0f;
    float bb = 0.0f;
%(grey)s

    float g = (p_G * 65535.0f - 1520.0f) / (0.92f * 8000.0f);
    float gout = g + master;
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
    float dr = dr1 - dr0;
    float db = db1 - db0;

    return make_float3(p_R + (trimR + master + dr + br) * 1.00f * D_TO_CV,
                       p_G + (trimG + master + bg) * 0.92f * D_TO_CV,
                       p_B + (trimB + master + db + bb) * 0.95f * D_TO_CV);
}
"""


def menu_id(label):
    return "LS_" + label.upper().replace(" ", "_")


def write_dctl(path, rows, slider):
    legend = "\n".join("//  %2d  %-14s %4d knots, support g %.4f-%.4f D; grey trims R/G/B %+.4f/%+.4f/%+.4f D"
                       % (i + 1, r["label"], len(r["curve"].g), r["curve"].g[0], r["curve"].g[-1], *r["tb"])
                       for i, r in enumerate(rows))
    darkest = ", ".join("%s %+.2f" % (r["stock"], r["grey_stops_off"]) for r in rows)
    if slider:
        key = lambda i, lbl: "%d" % (i + 1); off = "0"
        param = "DEFINE_UI_PARAMS(stock, Locus Stock, DCTLUI_SLIDER_INT, 0, 0, %d, 1)" % len(rows)
        uikind, uinote = "numbered int slider", ""
    else:
        key = lambda i, lbl: menu_id(lbl); off = "LS_OFF"
        ids = ", ".join(["LS_OFF"] + [key(i, r["label"]) for i, r in enumerate(rows)])
        labels = ", ".join(["Off"] + [r["label"] for r in rows])
        param = "DEFINE_UI_PARAMS(stock, Locus Stock, DCTLUI_COMBO_BOX, 0, { %s }, { %s })" % (ids, labels)
        uikind, uinote = "named menu", ("\n// If Resolve refuses the menu, regenerate with --slider for\n"
                                        "// a numbered slider (same numbers as the list above).")
    chain = "\n".join(emit_stock(key(i, r["label"]), r["curve"], i == 0) for i, r in enumerate(rows))
    grey = "\n".join("    %sif (stock == %s) { br = %sf; bg = %sf; bb = %sf; }"
                     % ("" if i == 0 else "else ", key(i, r["label"]), *[f32lit(v) for v in r["tb"]])
                     for i, r in enumerate(rows))
    Path(path).write_text(HEAD % {"legend": legend, "chain": chain, "grey": grey, "stockparam": param, "offkey": off,
                                  "uikind": uikind, "uinote": uinote, "masterrange": MASTER_RANGE, "darkest": darkest})
    return ["LS_OFF"] + [menu_id(r["label"]) for r in rows]


# ---------------- plain reference ----------------
# The hand-written printer-lights transform (Locus Stock Off must equal it bit for bit),
# frozen here as the baseline the emitted file is checked against.
REFERENCE_DCTL = r"""DEFINE_UI_PARAMS(trimR, Trim R density, DCTLUI_SLIDER_FLOAT, 0.0, -0.5, 0.5, 0.001)
DEFINE_UI_PARAMS(trimG, Trim G density, DCTLUI_SLIDER_FLOAT, 0.0, -0.5, 0.5, 0.001)
DEFINE_UI_PARAMS(trimB, Trim B density, DCTLUI_SLIDER_FLOAT, 0.0, -0.5, 0.5, 0.001)
DEFINE_UI_PARAMS(master, Master density, DCTLUI_SLIDER_FLOAT, 0.0, -0.5, 0.5, 0.001)

__DEVICE__ float3 transform(int p_Width, int p_Height, int p_X, int p_Y, float p_R, float p_G, float p_B)
{
    // APD -> normalized ADX16 CV (ST 2065-3 eq. 1): CV = k*APD*8000 + 1520,
    // written as CV/65535, so an APD offset lands as k*8000/65535 per channel
    const float D_TO_CV = 8000.0f / 65535.0f;
    return make_float3(p_R + (trimR + master) * 1.00f * D_TO_CV,
                       p_G + (trimG + master) * 0.92f * D_TO_CV,
                       p_B + (trimB + master) * 0.95f * D_TO_CV);
}
"""


# ---------------- C harness ----------------
HARNESS = r"""#include <math.h>
#include <stdio.h>
typedef struct { float x, y, z; } float3;
static float3 make_float3(float a, float b, float c){ float3 v={a,b,c}; return v; }
#define __DEVICE__ static
static float _fmaxf(float a, float b){ return fmaxf(a,b); }
static float _fminf(float a, float b){ return fminf(a,b); }
#define DEFINE_UI_PARAMS(name, label, type, ...) float name = 0;
#define DCTLUI_SLIDER_FLOAT 0
#define DCTLUI_SLIDER_INT 0
#define DCTLUI_COMBO_BOX 0
%(enum)s
#include "%(dut)s"
%(nostock)s
int main(void){
    float s,m,a,b2,c,r,g,b;
    while (scanf("%%f %%f %%f %%f %%f %%f %%f %%f",&s,&m,&a,&b2,&c,&r,&g,&b)==8){
        stock=s; master=m; trimR=a; trimG=b2; trimB=c;
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


def f32(v):
    """Round to the float32 the emitted literal and the C harness both carry."""
    return np.asarray(v, np.float32).astype(float)


def f32lit(v):
    s = "%.9g" % np.float32(v)
    return s if ("." in s or "e" in s) else s + ".0"


def rows_for(stock_id, cv, master, trims):
    n = len(cv)
    return np.column_stack([np.full(n, stock_id), np.broadcast_to(np.asarray(master, float), (n,)),
                            np.broadcast_to(np.asarray(trims, float), (n, 3)), cv])


# ---------------- 5e: exact maximum of the correction error ----------------
def window_absmax(cand, ev, M):
    """For each candidate x, max |ev(x) - ev(y)| over candidates y with |x - y| <= M
    (range min/max by a sparse table)."""
    n = len(ev)
    j0 = np.searchsorted(cand, cand - M - 1e-12, "left"); j1 = np.searchsorted(cand, cand + M + 1e-12, "right")
    mx, mn = [ev], [ev]; w = 1
    while 2 * w <= n:
        mx.append(np.maximum(mx[-1][:-w], mx[-1][w:])); mn.append(np.minimum(mn[-1][:-w], mn[-1][w:])); w *= 2
    ln = j1 - j0; k = np.floor(np.log2(ln)).astype(int); out = np.empty(n)
    for lv in np.unique(k):
        s = k == lv; p = 1 << int(lv)
        hi = np.maximum(mx[lv][j0[s]], mx[lv][j1[s] - p]); lo = np.minimum(mn[lv][j0[s]], mn[lv][j1[s] - p])
        out[s] = np.maximum(ev[s] - lo, hi - ev[s])
    return out


def q_of(tab, x, c):
    arr = tab["R"] if c == 0 else tab["B"]
    return np.interp(x, tab["g"], arr - tab["g"])


def sensor_error(tu, ta, M=MASTER_RANGE):
    """(gated max over the common support, tail max) per channel R, B."""
    lo = max(tu["g"][0], ta["g"][0]); hi = min(tu["g"][-1], ta["g"][-1])
    k = np.union1d(tu["g"], ta["g"]); k = np.union1d(k[(k >= lo) & (k <= hi)], [lo, hi])
    cand = np.union1d(k, np.clip(np.r_[k - M, k + M], lo, hi))
    lo_e = min(tu["g"][0], ta["g"][0]) - M; hi_e = max(tu["g"][-1], ta["g"][-1]) + M
    ke = np.union1d(np.union1d(tu["g"], ta["g"]), [lo, hi, lo_e, hi_e])
    cand_e = np.union1d(ke, np.clip(np.r_[ke - M, ke + M], lo_e, hi_e))
    outside = (cand_e < lo) | (cand_e > hi)
    gated, tail = [], []
    for c in (0, 2):
        ev = q_of(tu, cand, c) - q_of(ta, cand, c)
        gated.append(float(window_absmax(cand, ev, M).max()))
        ev_e = q_of(tu, cand_e, c) - q_of(ta, cand_e, c)
        tail.append(float(window_absmax(cand_e, ev_e, M)[outside].max()) if outside.any() else 0.0)
    return gated, tail, (float(lo), float(hi)), len(cand)


# ---------------- 5c/5d coverage ----------------
def coverage(e, L, n, lut):
    """Masks for one set at bracket n: locus support (input and destination green), layer
    exposure tables, cube domain, negative dye; plus the bracketed CV."""
    sn0 = e.L_to_scan_norm(L); sn = e.L_to_scan_norm(L * 2.0 ** n)
    cv = cube_lookup(lut, sn); cv0 = cube_lookup(lut, sn0)
    return sn0, sn, cv0, cv


def masks_for(e, L, n, sn0, sn, cv, move, curves):
    g = unenc(cv)[:, 1]
    loc = np.ones(len(L), bool)
    for c in curves:
        loc &= c.supported(g) & c.supported(g + move)
    lay = np.ones(len(L), bool); neg = np.ones(len(L), bool)
    for ll in (L, L * 2.0 ** n):
        hs = np.log10(np.maximum(ll, 1e-12)) + e.logH_mid
        for c in range(3):
            tab_h = e.neutral_tab[c][1]
            lay &= (hs[:, c] >= tab_h[0]) & (hs[:, c] <= tab_h[-1])
            neg &= interp_lin(hs[:, c], tab_h, e.neutral_tab[c][0]) >= 0
    dom = np.all((sn >= 0) & (sn <= 1), 1) & np.all((sn0 >= 0) & (sn0 <= 1), 1)
    return dict(locus=loc, layer=lay, domain=dom, negdye=neg, supported=loc & lay & dom & neg)


def stats(d):
    return [float(d.mean()), float(d.max())] if len(d) else [None, None]


def fmt(s):
    return "  n/a/ n/a " if s[0] is None else "%5.2f/%5.2f" % tuple(s)


# ---------------- 2.10 source (a) ----------------
def own_dye_apd(e):
    """Image-dye APD of the sheet Status M series on the stock's own dyes and mask, and its logH."""
    dj = json.load(open(e.p["dye_density"])); grid = e.DGRID[e.DGRID <= 798]
    dy, mask = ax.curves(dj, grid)
    sm = ax.resp(DATA / "standards" / "StatusM_ISO5-3.json", "responsivity_linear_peak1", grid)
    apr = ax.resp(DATA / "standards" / "APD_ST2065-2.json", None, grid)
    cd = json.load(open(e.p["char_curves"]))["char_curves"]
    h = np.array(cd["log_exposure"], float)
    d = np.array([[np.nan if x is None else x for x in cd["density"][ch]] for ch in "RGB"], float).T
    ok = np.isfinite(d).all(1); h, d = h[ok], d[ok]
    amt, res = ax.solve(d, sm, dy, mask)
    own = ax.dens(apr, amt, dy, mask) - ax.dens(apr, np.zeros((1, 3)), dy, mask)
    return h, own, d, float(res)


def dq(f, h_mid, n):
    """R/B correction returning the n-bracketed grey to mid: q(mid) - q(mid + n LOG2)."""
    a, b = f(np.array([h_mid])), f(np.array([h_mid + n * LOG2]))
    qa = a[0, [0, 2]] - a[0, 1]; qb = b[0, [0, 2]] - b[0, 1]
    return qa - qb


def interp_rows(h, arr):
    return lambda x: np.stack([np.interp(x, h, arr[:, c]) for c in range(3)], -1)


# ---------------- main ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slider", action="store_true", help="numbered int slider in place of the named menu")
    args = ap.parse_args()
    rng = np.random.default_rng(20260930)
    cube_u = ROOT / "builds" / CUBE_NAME
    lut = read_cube(cube_u, SZ)
    rows = []
    print("TABLE SOURCE: %s (sensor-free), %d-point neutral series per stock" % (cube_u.relative_to(ROOT), N_DENSE))
    print("SIMPLIFICATION (adaptive, full transform over the validation set, Academy ADX16 decode)")
    print("stock           knots full/kept  dropped  tol D      curve err D  added dE2000 (double)  validation pts   steepest segment")
    for s in v3.STOCKS:
        label = "Vision3 %s" % s
        if not label.isascii() or any(ch in label for ch in ",{}-"):
            raise SystemExit("%s: label %r cannot be a menu label" % (s, label))
        e = v3.V3SceneEngine(s, *v3.resolve_sensor("none"))
        tab = dense_table(e, lut)
        full = Curve(tab["g"], tab["R"], tab["B"])
        tb = f32(av.solve_apd_trims(tab["cv_mid"][None, :]))
        ap0_off = av.adx16_to_aces(tab["cv_mid"][None, :])[0]
        grey_stops_off = float(np.log2(grey_Y(tab["cv_mid"]) / 0.18))
        parts = validation_set(e, lut, tab, full, tb, rng)
        ref_labs = []
        for _, cv, m, tr in parts:
            si, so = support_masks(full, cv, m); sup = si & so
            ref_labs.append((sup, lab(transform(cv[sup], full, m[sup], tr[sup]))))
        tol = SIMPLIFY_START
        while True:
            idx, simp, err = simplify(tab, tol)
            add = added_de(parts, full, simp, ref_labs)
            if add <= ADDED_DE_MAX:
                break
            tol /= 2.0
            if tol < SIMPLIFY_FLOOR:
                raise SystemExit("%s: no simplification tolerance meets %.2f dE2000" % (label, ADDED_DE_MAX))
        npts = sum(len(p[1]) for p in parts)
        slope = float(max(np.abs(np.diff(simp.R) / np.diff(simp.g)).max(), np.abs(np.diff(simp.B) / np.diff(simp.g)).max()))
        print("%-14s  %4d / %4d      %4d     %.2e   %.6f     %.4f                 %6d           |dR,dB/dg| %.2f"
              % (label, len(tab["g"]), len(idx), tab["dropped"], tol, err, add, npts, slope))
        rows.append(dict(stock=s, label=label, e=e, tab=tab, full=full, curve=simp, tol=tol, curve_err=err,
                         added_double=add, parts=parts, tb=tb, slope=slope, ap0_off=ap0_off,
                         grey_stops_off=grey_stops_off))
    print("\nGREY PLACEMENT (stock's grey trims b_c; mid-grey decoded at Off defaults)")
    print("stock           b R/G/B D                    AP0 at Off defaults        Y vs 0.18")
    for r in rows:
        print("%-14s  %+.4f/%+.4f/%+.4f      %.4f/%.4f/%.4f       %+.2f stops"
              % (r["label"], *r["tb"], *r["ap0_off"], r["grey_stops_off"]))
    ids = write_dctl(OUT, rows, args.slider)
    report = dict(target="approximate model-based exposure compensation on the ADX16 chain",
                  cube=str(cube_u.relative_to(ROOT)), stocks={})
    fails = []

    with tempfile.TemporaryDirectory() as tmp:
        menu_path = Path(tmp) / "menu.dctl"; slider_path = Path(tmp) / "slider.dctl"
        write_dctl(menu_path, rows, False); write_dctl(slider_path, rows, True)
        exe = compile_dut(tmp, "menu", menu_path, ids)
        exe_sl = compile_dut(tmp, "slider", slider_path)
        ref_path = Path(tmp) / "reference.dctl"; ref_path.write_text(REFERENCE_DCTL)
        exe_ref = compile_dut(tmp, "reference", ref_path, has_stock=False)

        # ---- 5a ----
        print("\n5a  EMITTED C vs references (supported points)")
        print("stock           max APD err vs simplified double D   max added dE2000 vs full branch   supported/unsup-in/unsup-dest")
        allrows = []
        for i, r in enumerate(rows):
            cv, m, tr = [np.concatenate([p[j] for p in r["parts"]]) for j in (1, 2, 3)]
            R_ = rows_for(i + 1, cv, m, tr - r["tb"]); allrows.append(R_)
            outc = as_arr(run_c(exe, R_))
            ref_s = transform(cv, r["curve"], m, tr); ref_f = transform(cv, r["full"], m, tr)
            si, so = support_masks(r["full"], cv, m); sup = si & so
            cerr = float((np.abs(outc - ref_s) / SCALE)[sup].max())
            dmax = float(de(lab(outc[sup]), lab(ref_f[sup])).max())
            counts = [int(sup.sum()), int((~si).sum()), int((si & ~so).sum())]
            print("%-14s  %.2e                             %.4f                            %s"
                  % (r["label"], cerr, dmax, "/".join(map(str, counts))))
            if cerr > NUM_TOL: fails.append("%s 5a APD error %.2e D" % (r["label"], cerr))
            if dmax > ADDED_DE_MAX: fails.append("%s 5a added dE %.4f" % (r["label"], dmax))
            if not np.all(np.isfinite(outc)): fails.append("%s non-finite output" % r["label"])
            report["stocks"][r["label"]] = dict(
                knots_full=len(r["tab"]["g"]), knots_kept=len(r["curve"].g), dropped_knots=r["tab"]["dropped"],
                support_g_D=[float(r["curve"].g[0]), float(r["curve"].g[-1])], mid_apd=r["tab"]["apd_mid"].tolist(),
                grey_trims_emitted_D=r["tb"].tolist(), ap0_mid_at_off_defaults=r["ap0_off"].tolist(),
                grey_stops_at_off_defaults=r["grey_stops_off"], simplify_tol_D=r["tol"], curve_err_D=r["curve_err"],
                added_de_double=r["added_double"], steepest_segment=r["slope"], emitted_apd_err_D=cerr,
                emitted_added_de=dmax, validation_counts=dict(supported=counts[0], unsupported_input=counts[1],
                                                              unsupported_destination=counts[2]))

        # ---- 5b ----
        print("\n5b  BEHAVIOUR (emitted C)")
        big = np.concatenate(allrows)
        same = run_c(exe, big) == run_c(exe_sl, big)
        print("  menu build vs --slider build, %d rows: %s" % (len(big), "BIT-IDENTICAL" if same else "DIFFER"))
        if not same: fails.append("menu vs slider differ")
        N = 20000
        rr = np.column_stack([np.zeros(N), rng.uniform(-MASTER_RANGE, MASTER_RANGE, N),
                              rng.uniform(-TRIM_RANGE, TRIM_RANGE, (N, 3)) * (rng.random((N, 3)) < 0.5),
                              rng.uniform(0, 1, (N, 3))])
        rr[::7, 1] = 0.0
        ok = run_c(exe, rr) == run_c(exe_ref, rr)
        print("  Off vs frozen reference transform, %d random rows: %s" % (N, "BIT-IDENTICAL" if ok else "DIFFER"))
        if not ok: fails.append("Off differs from the frozen reference")
        dfl = rr.copy(); dfl[:, 0] = 0; dfl[:, 1:5] = 0
        lines_d = run_c(exe, dfl)
        inp32 = np.array([[np.float32(float("%.9g" % v)) for v in row] for row in dfl[:, 5:8]], np.float32)
        ok = np.array_equal(as_arr(lines_d).astype(np.float32), inp32) and lines_d == run_c(exe_ref, dfl)
        print("  Off at defaults (Master 0, trims 0): %s" % ("BIT-IDENTICAL to input" if ok else "CHANGED"))
        if not ok: fails.append("Off at defaults changes the input")
        okg = True
        for i, r in enumerate(rows):
            d_s = dfl.copy(); d_s[:, 0] = i + 1
            d_r = dfl.copy(); d_r[:, 2:5] = r["tb"]
            okg &= run_c(exe, d_s) == run_c(exe_ref, d_r)
            ap0 = av.adx16_to_aces(as_arr(run_c(exe, rows_for(i + 1, r["tab"]["cv_mid"][None, :], 0.0, np.zeros(3)))))[0]
            gerr = float(np.abs(ap0 - 0.18).max())
            print("  %-14s at defaults: mid-grey AP0 %.5f/%.5f/%.5f (max |err| %.1e)" % (r["label"], *ap0, gerr))
            if gerr > GREY_TOL: fails.append("%s defaults place mid-grey %.1e off AP0 0.18" % (r["label"], gerr))
            report["stocks"][r["label"]]["mid_grey_ap0_at_defaults"] = ap0.tolist()
        print("  each stock at defaults vs frozen reference with trims = its grey trims, %d rows each: %s"
              % (N, "BIT-IDENTICAL" if okg else "DIFFER"))
        if not okg: fails.append("a stock at defaults differs from Off with its grey trims")

        cont = {}; mc = 0.25
        dep = np.array([0.03, 0.0, -0.02])
        for eps in (1e-3, 1e-4, 1e-5):
            worst = 0.0
            for i, r in enumerate(rows):
                gk = r["curve"].g
                for mode in ("input", "destination"):
                    gc = gk if mode == "input" else gk - mc
                    apd = r["full"].s_ext(gc) + dep
                    lo = apd.copy(); hi = apd.copy(); lo[:, 1] = gc - eps; hi[:, 1] = gc + eps
                    a = as_arr(run_c(exe, rows_for(i + 1, enc(lo), mc, np.zeros(3))))
                    b = as_arr(run_c(exe, rows_for(i + 1, enc(hi), mc, np.zeros(3))))
                    worst = max(worst, float((np.abs(a - b) / SCALE).max()))
            cont[eps] = worst
        print("  continuity at every knot and support end, green crossing it as input and as destination"
              " (Master %.2f):\n    " % mc + "   ".join("separation %.0e -> max jump %.2e D" % (2 * e_, w) for e_, w in cont.items()))
        if cont[1e-5] > 10 * 2e-5 + 2e-6: fails.append("discontinuity: jump %.2e D at separation 2e-5" % cont[1e-5])
        report["continuity_max_jump_by_separation_D"] = {("%.0e" % (2 * e_)): w for e_, w in cont.items()}

        rev = 0.0; nrev = 0
        for i, r in enumerate(rows):
            cv = np.concatenate([p[1] for p in r["parts"]])[:4000]; n = len(cv)
            mv = rng.uniform(-MASTER_RANGE, MASTER_RANGE, n); z = np.zeros(3)
            o1 = as_arr(run_c(exe, rows_for(i + 1, cv, mv, z - r["tb"])))
            o2 = as_arr(run_c(exe, rows_for(i + 1, o1, -mv, z - r["tb"])))
            si, so = support_masks(r["full"], cv, mv)
            m = si & so & (mv != 0)
            rev = max(rev, float((np.abs(o2 - cv) / SCALE)[m].max())); nrev += int(m.sum())
        print("  +Master then -Master, trims zero in total (supported, %d pts): max |error| %.2e D" % (nrev, rev))
        if rev > NUM_TOL: fails.append("Master reversal error %.2e D" % rev)
        report["master_reversal_max_err_D"] = rev

    # ---- 5e: cross-sensor ----
    apps = sorted(ROOT.glob("builds/sensor-*/"))
    print("\n5e  CROSS-SENSOR (gate: exact max |E_c(g, M)| <= %.4f D over the common support, |M| <= %.1f)"
          % (SENSOR_E_TOL, MASTER_RANGE))
    print("  apparatus: %s" % ([str(p.relative_to(ROOT)) for p in apps] or "none"))
    report["cross_sensor"] = {}
    grey_rows = []
    if not apps:
        fails.append("no per-camera build to check; build them with --sensor")
    missing = [p for p in apps if not (p / CUBE_NAME).exists()]
    for p in missing:
        fails.append("%s lacks %s" % (p.relative_to(ROOT), CUBE_NAME))
    print("  stock           apparatus                 max|E| R/B (gated)   tails R/B (reported)   common support   "
          "rendered mean/max dE2000 (supported/total)")
    for p in apps:
        if p in missing:
            continue
        name = p.name[len("sensor-"):]
        lut_a = read_cube(p / CUBE_NAME, SZ)
        for r in rows:
            e_a = v3.V3SceneEngine(r["stock"], *v3.resolve_sensor(name))
            ta = dense_table(e_a, lut_a); full_a = Curve(ta["g"], ta["R"], ta["B"])
            tb_a = av.solve_apd_trims(ta["cv_mid"][None, :])
            ap0_a = av.adx16_to_aces((ta["cv_mid"] + r["tb"] * SCALE)[None, :])[0]
            grey_rows.append((r["label"], name, tb_a - r["tb"], ap0_a))
            gated, tail, (lo, hi), ncand = sensor_error(r["tab"], ta)
            ds, nsup, ntot = [], 0, 0
            for _, L in bracket_sets(e_a):
                for n in NS:
                    move, _ = grey_move(e_a, lut_a, ta, n)
                    sn0, sn, cv0, cv = coverage(e_a, L, n, lut_a)
                    mk = masks_for(e_a, L, n, sn0, sn, cv, move, [r["curve"], full_a])["supported"]
                    ntot += len(L); nsup += int(mk.sum())
                    if mk.any():
                        ds.append(de(lab(transform(cv[mk], r["curve"], move, tb_a)),
                                     lab(transform(cv[mk], full_a, move, tb_a))))
            ds = np.concatenate(ds) if ds else np.zeros(0)
            st = stats(ds)
            print("  %-14s  %-24s  %.5f/%.5f        %.5f/%.5f          %.3f-%.3f D    %s (%d/%d)"
                  % (r["label"], name, gated[0], gated[1], tail[0], tail[1], lo, hi, fmt(st), nsup, ntot))
            for c, v in zip("RB", gated):
                if v > SENSOR_E_TOL:
                    fails.append("%s %s 5e max |E_%s| %.5f D" % (r["label"], name, c, v))
            report["cross_sensor"].setdefault(name, {})[r["label"]] = dict(
                max_E_D=dict(R=gated[0], B=gated[1]), tails_max_E_D=dict(R=tail[0], B=tail[1]),
                common_support_D=[lo, hi], candidates=ncand, rendered_de=st, rendered_supported=nsup,
                rendered_total=ntot, grey_balance_trims_D=tb_a.tolist(),
                own_minus_universal_grey_trims_D=(tb_a - r["tb"]).tolist(), mid_grey_ap0_under_universal=ap0_a.tolist())
    if grey_rows:
        print("  grey placement per apparatus (reported): own grey trims minus the stock's, D; its mid-grey decoded under the stock's")
        for lbl, name, dtb, ap0 in grey_rows:
            print("  %-14s  %-24s  %+.4f/%+.4f/%+.4f   AP0 %.4f/%.4f/%.4f (%+.3f stops max)"
                  % (lbl, name, *dtb, *ap0, float(np.abs(np.log2(ap0 / 0.18)).max())))

    # ---- 5c/5d: brackets (reported), sensor-free ----
    print("\n5c/5d  EXPOSURE BRACKETS (reported; goal mean <= %.0f, max <= %.0f dE2000; '!' = curve misses the goal,"
          " '*' = |Master| beyond %.1f); CC24 rows" % (GOAL[0], GOAL[1], MASTER_RANGE))
    print("stock           n   Master     sup/locus/layer/domain/negdye   PL mean/max   gain mean/max  line mean/max  curve mean/max   exact locus")
    for r in rows:
        e, tab, tb = r["e"], r["tab"], r["tb"]
        xs = np.array([n * LOG2 for n in (-2, -1, 0, 1, 2, 3)])
        ys = at_logH(tab, e.logH_mid + xs) - at_logH(tab, np.array([e.logH_mid]))
        slope_c = (xs[:, None] * ys).sum(0) / (xs * xs).sum()
        ratio = slope_c / slope_c[1]
        rep = dict(line_slopes=slope_c.tolist(), line_ratio=ratio.tolist(), rows=[])
        for n in NS:
            move, cvg = grey_move(e, lut, tab, n)
            pl = brentq(lambda t: grey_Y(cvg + (tb + t) * SCALE) - 0.18, -2, 2)
            line = brentq(lambda t: grey_Y(cvg + (tb + t * ratio) * SCALE) - 0.18, -2, 2)
            gain = 0.18 / grey_Y(cvg + tb * SCALE)
            for sname, L in bracket_sets(e):
                sn0, sn, cv0, cv = coverage(e, L, n, lut)
                mk = masks_for(e, L, n, sn0, sn, cv, move, [r["full"]])
                sup = mk["supported"]
                ref = lab(cv0[sup] + tb * SCALE)
                outs = [lab(cv[sup] + (tb + pl) * SCALE),
                        colour.XYZ_to_Lab(av.aces_to_xyz_d65(av.adx16_to_aces(cv[sup] + tb * SCALE)) * gain, av.D65),
                        lab(cv[sup] + (tb + line * ratio) * SCALE),
                        lab(transform(cv[sup], r["curve"], move, tb)),
                        lab(transform(cv[sup], r["full"], move, tb))]
                cells = [stats(de(o, ref)) for o in outs]
                miss = cells[3][0] is not None and (cells[3][0] > GOAL[0] or cells[3][1] > GOAL[1])
                cnt = [int(sup.sum())] + [int((~mk[k]).sum()) for k in ("locus", "layer", "domain", "negdye")]
                if sname == "CC24":
                    print("%-14s %+d  %+.4f%s  %3d/%3d/%3d/%3d/%3d          %s   %s   %s  %s%s   %s"
                          % (r["label"], n, move, "*" if abs(move) > MASTER_RANGE else " ", *cnt,
                             fmt(cells[0]), fmt(cells[1]), fmt(cells[2]), fmt(cells[3]), "!" if miss else " ", fmt(cells[4])))
                rep["rows"].append(dict(set=sname, n=n, master=move, pl_offset=pl, line_t=line, aces_gain=gain,
                                        total=len(L), supported=cnt[0], outside_locus=cnt[1], outside_layer_tables=cnt[2],
                                        outside_cube_domain=cnt[3], negative_dye=cnt[4], pl=cells[0], gain=cells[1],
                                        line=cells[2], curve=cells[3], exact_locus=cells[4], goal_met=not miss,
                                        master_beyond_range=abs(move) > MASTER_RANGE))
        report["stocks"][r["label"]]["brackets"] = rep

    # ---- 2.10: source comparisons (reported) ----
    print("\nTABLE SOURCES: R/B correction dq_c(n) = q_c(mid) - q_c(mid + n log2), D  (b dense cube table, a own-dye APD, c Annex C)")
    print("stock           n    b R/B              a R/B              c R/B")
    for r in rows:
        e, tab = r["e"], r["tab"]
        fb = lambda x: at_logH(tab, x)
        h_a, own, d_sheet, res = own_dye_apd(e)
        fa = interp_rows(h_a, own)
        fc = None
        if r["stock"] in ANNEX_KEYS:
            A = ax.ANNEX[ANNEX_KEYS[r["stock"]]]
            fc = interp_rows(h_a, d_sheet @ np.array(A["matrix"]).T + np.array(A["offset"]))
        src = []; mba = mbc = 0.0
        for n in NS:
            b = dq(fb, e.logH_mid, n); a = dq(fa, e.logH_mid, n)
            c = dq(fc, e.logH_mid, n) if fc else None
            mba = max(mba, float(np.abs(b - a).max()))
            if c is not None:
                mbc = max(mbc, float(np.abs(b - c).max()))
            print("%-14s %+d   %+.4f/%+.4f    %+.4f/%+.4f    %s"
                  % (r["label"], n, b[0], b[1], a[0], a[1], ("%+.4f/%+.4f" % (c[0], c[1])) if c is not None else "not in Annex C"))
            src.append(dict(n=n, b=b.tolist(), a=a.tolist(), c=c.tolist() if c is not None else None))
        print("%-14s max |b-a| %.4f D   max |b-c| %s   (own-dye neutral solve resid %.4f D)"
              % (r["label"], mba, ("%.4f D" % mbc) if fc else "not in Annex C", res))
        report["stocks"][r["label"]]["sources"] = dict(rows=src, max_b_minus_a=mba,
                                                       max_b_minus_c=mbc if fc else None, own_dye_solve_resid=res)

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1, default=float) + "\n")
    print("\nwrote %s (%s)" % (OUT.relative_to(ROOT), "slider" if args.slider else "named menu"))
    print("report %s" % REPORT.relative_to(ROOT))
    if fails:
        raise SystemExit("ACCEPTANCE FAILED:\n  " + "\n  ".join(fails))
    print("ACCEPTANCE: 5a, 5b and 5e pass on every stock")


if __name__ == "__main__":
    main()
