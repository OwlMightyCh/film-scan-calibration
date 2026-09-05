#!/usr/bin/env python3
"""External check of the Vision3 dye model against the Academy's measured
Status M -> APD relation (A.M.P.A.S. S-2008-002 Annex C).

The Academy exposed 97 patches on each of 31 negative stocks, measured them
spectrally, and fitted a 3x3-plus-offset transform from ISO Status M to
Academy Printing Density per stock, publishing the residuals. Two of those
stocks are Vision3 250D (5207) and 500T (5219). This repository computes both
metrics from one dye model, so the matrix is a check against a published
quantity that no engine's inverse or self-report uses (Rule 4).

Per stock: the per-layer dye amounts are solved from the sheet's three
characteristic curves at once (absolute Status M, base and mask included, the
scene engine's neutral solve); the same amounts are integrated against the
Status M and ST 2065-2 tables; the spectral APD is compared with
`M . StatusM + offset` along the traced exposure axis. Run twice, on the
stock's own dyes and mask and on the family basis the ADX16 cube reads through.
Pass criterion is the document's own statistic, per-channel mean absolute error
<= 0.02 D over the traced neutral series; signed mean (bias) and pointwise
maximum are printed beside it, ungated.
Known bounds: green above ~2.1 D, where Annex C's own residual is 0.03-0.05 D;
red carries the traced mask's D-min disagreement with the sheet (~0.03 D).

Usage:
    python3 engine/ecn2/annexc_check.py [--stocks 250D,500T]
"""
import argparse, json, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]; DATA = ROOT / "data"
sys.path.insert(0, str(ROOT))
from engine.common.spectral import resample

LAYERS = ("cyan", "magenta", "yellow")
STOCKS = {"250D": ("Vision3_250D_dye_density.json", "Vision3_250D_datasheet_curves.json", "Eastman Kodak 5207"),
          "500T": ("Vision3_500T_dye_density.json", "V3500T_datasheet_curves.json", "Eastman Kodak 5219")}
TOL = 0.02

ap = argparse.ArgumentParser()
ap.add_argument("--stocks", default="250D,500T")
args = ap.parse_args()

ANNEX = json.load(open(DATA / "standards" / "StatusM_to_APD_S-2008-002_AnnexC.json"))["stocks"]
FAMILY = json.load(open(DATA / "films" / "Vision3_dye_density.json"))


def curves(dj, grid):
    fc = dj["shared_full_curves"]; wl = np.array(fc["wavelength_nm"], float); out = []
    for k in LAYERS:
        v = np.array([np.nan if x is None else x for x in fc[k]], float); ok = ~np.isnan(v)
        out.append(resample(wl[ok], v[ok], grid))
    md = dj["minimum_density"]; mw = np.array(md["wavelength_nm"], float)
    mv = np.array([np.nan if x is None else x for x in md["density"]], float); ok = ~np.isnan(mv)
    return np.stack(out), resample(mw[ok], mv[ok], grid)


def resp(path, key, grid):
    j = json.load(open(path)); w = np.array(j["wavelength_nm"], float)
    R = np.stack([resample(w, np.array(j[key][c] if key else j[c], float), grid) for c in ("red", "green", "blue")])
    return R / R.sum(1, keepdims=True)


def dens(W, amt, DYE, DMIN):
    T = 10.0 ** (-(np.atleast_2d(amt) @ DYE + DMIN)); return -np.log10(np.clip(T @ W.T, 1e-12, None))


def solve(Dabs, SM, DYE, DMIN):
    """Gauss-Newton on the full dye stack: the model's neutral IS the sheet's."""
    mask = dens(SM, np.zeros((1, 3)), DYE, DMIN)
    S = (dens(SM, np.eye(3), DYE, DMIN) - mask).T
    amt = (Dabs - mask) @ np.linalg.inv(S).T
    for _ in range(40):
        T = 10.0 ** (-(amt @ DYE + DMIN)); integ = T @ SM.T
        J = np.einsum('nl,il,jl->nij', T, SM, DYE) / integ[:, :, None]
        r = -np.log10(np.clip(integ, 1e-12, None)) - Dabs
        amt = np.clip(amt - np.linalg.solve(J, r[:, :, None])[:, :, 0], -0.5, 6.0)
    return amt, float(np.max(np.abs(dens(SM, amt, DYE, DMIN) - Dabs)))


worst = {"own": 0.0, "family": 0.0}       # worst |signed channel mean|, the document's statistic
worst_mae = {"own": 0.0, "family": 0.0}   # worst per-channel mean |error|
worst_max = {"own": 0.0, "family": 0.0}   # worst pointwise |error|
for stock in args.stocks.split(","):
    dye_file, cc_file, key = STOCKS[stock]
    dj = json.load(open(DATA / "films" / dye_file))
    fc = dj["shared_full_curves"]; wl = np.array(fc["wavelength_nm"], float)
    meas = [wl[np.array([x is not None for x in fc[k]])] for k in LAYERS]
    lo = max(400.0, min(m.min() for m in meas)); hi = min(730.0, max(m.max() for m in meas))
    grid = np.arange(np.ceil(lo), np.floor(hi) + 1, 1.0)
    SM = resp(DATA / "standards" / "StatusM_ISO5-3.json", "responsivity_linear_peak1", grid)
    APD = resp(DATA / "standards" / "APD_ST2065-2.json", None, grid)
    cd = json.load(open(DATA / "films" / cc_file))["char_curves"]
    logH = np.array(cd["log_exposure"], float)
    D = np.stack([np.array([np.nan if v is None else v for v in cd["density"][ch]], float) for ch in "RGB"], 1)
    ok = np.isfinite(D).all(1); logH, D = logH[ok], D[ok]
    M = np.array(ANNEX[key]["matrix"]); off = np.array(ANNEX[key]["offset"]); res = ANNEX[key]["residuals"]
    print("\n%s (%s): grid %.0f-%.0f nm, %d neutral points, logH %+.2f..%+.2f; Annex C mean abs error %s, max (gray) %s"
          % (stock, key, grid[0], grid[-1], logH.size, logH[0], logH[-1],
             res["mean abs error (all)"], res["max abs error (gray)"]))
    for label, src in (("own dyes + own mask", dj), ("family basis (ADX16 cube)", FAMILY)):
        DYE, DMIN = curves(src, grid)
        amt, rs = solve(D, SM, DYE, DMIN)
        stm = dens(SM, amt, DYE, DMIN); apd = dens(APD, amt, DYE, DMIN)
        d = apd - (stm @ M.T + off)
        mask_stm = dens(SM, np.zeros((1, 3)), DYE, DMIN)[0]
        sheet_dmin = np.array([cd["dmin"][c] for c in "RGB"], float)
        straight = logH <= logH[np.argmax(D[:, 1] >= 2.1)] if (D[:, 1] >= 2.1).any() else np.ones_like(logH, bool)
        _k = "own" if label.startswith("own") else "family"
        worst[_k] = max(worst[_k], float(np.abs(d.mean(0)).max()))
        worst_mae[_k] = max(worst_mae[_k], float(np.abs(d).mean(0).max()))
        worst_max[_k] = max(worst_max[_k], float(np.abs(d).max()))
        print("  [%s] neutral solve resid %.4f D; mask Status M minus sheet D-min (R,G,B) = %s"
              % (label, rs, np.round(mask_stm - sheet_dmin, 3).tolist()))
        print("     APD(spectral) - APD(Annex C): mean %s  max|.| %s  | below 2.1 D green: mean|.| %s max|.| %s"
              % (np.round(d.mean(0), 4).tolist(), np.round(np.abs(d).max(0), 4).tolist(),
                 np.round(np.abs(d[straight]).mean(0), 4).tolist(), np.round(np.abs(d[straight]).max(0), 4).tolist()))
# Three statistics, kept apart. The GATE is the worst per-channel MEAN
# ABSOLUTE error over the series, which is the statistic the document itself
# publishes per stock ("mean abs error (all)") and the one its 0.02 D expected
# error refers to; a signed mean would let alternating errors cancel into a
# pass. The signed channel mean is printed beside it as the bias figure, and
# the pointwise maximum as the tail; neither is gated (the document's own
# maximum is over 97 patches, not a traced neutral series).
gate_own = worst_mae["own"] <= TOL
print("\nAnnex C check on the stock's own basis: worst per-channel MEAN ABSOLUTE disagreement %.4f D against the "
      "document's %.2f D expected error: %s" % (worst_mae["own"], TOL, "PASS" if gate_own else "FAIL"))
print("  own basis, ungated: worst per-channel signed mean (bias) %.4f D, worst pointwise |error| %.4f D"
      % (worst["own"], worst_max["own"]))
print("family basis (the ADX16 cube's averaging, bounded separately by adx_engine): worst mean |error| %.4f D "
      "(%s the %.2f D figure), signed mean %.4f D, pointwise max %.4f D"
      % (worst_mae["family"], "within" if worst_mae["family"] <= TOL else "EXCEEDS", TOL, worst["family"], worst_max["family"]))
sys.exit(0 if gate_own else 1)
