#!/usr/bin/env python3
"""Stock-dependent printer-light offsets for Kodak Vision3 500T.

Given the datasheet's normal-exposure gray card (mid-gray at camera stop 0), find
the per-channel density trims that equalize its RP-180 printing-density triplet.

Pipeline (mirrors engine/ecn2/cineon_pd_engine.py idioms: GRID=400..730,
resample(), the Vision3 dye basis, the -log10(10^-(dye@DYE) @ R.T) forward model,
and a Gauss-Newton inversion). Status M responsivities are loaded exactly as in
engine/c41/c41_statusm_engine.py: responsivity_linear_peak1 with the red
channel truncated at 700 nm and renormalized (the dye basis grid ends at 700/730,
and density is a Pi-weighted average so renormalization is exact).

  1. Read the datasheet char curves; at logH_mid = camera_stops_zero_logH take the
     per-channel density minus dmin -> base-relative Status M triplet of mid-gray.
  2. Invert Status M densitometry to dye amounts (Gauss-Newton, FD Jacobian).
  3. Forward those dyes through RP-180 printing density -> PD triplet.
  4. Printer-light preset = offsets that equalize the PD triplet, reported as
     zero-mean (exposure-preserving) and R-referenced (R=0). Positive = that
     channel needs more density.
  5. Sensitivity audit: repeat at logH_mid +/- one camera stop; print the spread.
"""
import json
import sys
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
BUILDS = ROOT / "builds"
GRID = np.arange(400, 731, 1.0)   # provisional; narrowed to the dye set's measured support below
STOP_LOG = np.log10(2.0)

sys.path.insert(0, str(ROOT))
from engine.common.spectral import density, resample   # noqa: E402


# ---------- Vision3 dye basis ----------
dj = json.load(open(DATA / "films" / "Vision3_dye_density.json"))
fc = dj["shared_full_curves"]

# The integration grid is narrowed to the dye set's MEASURED support, following
# engine/reversal/reversal_transform.py's dye_support_grid(). The traced Vision3
# basis carries null at 400-401 and 799-800 (the tracer cannot centre a line in
# the frame-edge columns). Resampling those to 0 would model the film as
# PERFECTLY CLEAR there -- an unbounded, sign-known error; synthesizing a value
# instead is the C-41 blue-edge defect. Truncating and letting the responsivities
# renormalize on the shorter grid asserts only that the unmeasured 2 nm resembles
# the in-band mean: a bounded bias. Costs 0.89%% of the RP180 blue channel.
_wl_all = np.array(fc["wavelength_nm"], float)
_meas = [ _wl_all[~np.isnan(np.array([np.nan if v is None else v for v in fc[k]], float))]
          for k in ("cyan", "magenta", "yellow") ]
_lo = max(GRID[0], min(m.min() for m in _meas))
_hi = min(GRID[-1], max(m.max() for m in _meas))
GRID = np.arange(np.ceil(_lo), np.floor(_hi) + 1, 1.0)
print("integration grid narrowed to measured dye support: %.0f-%.0f nm" % (GRID[0], GRID[-1]))

wl_d = np.array(fc["wavelength_nm"], float)
def _dye(channel):
    """Resample one dye curve, honouring null entries beyond measured support.

    Mirrors load_dye_channel() in engine/reversal/reversal_transform.py: nulls
    are dropped from the interpolation support rather than cast to 0, so no
    synthesized tail enters the integral. GRID is already narrowed to the
    measured support above, so nothing falls outside it.
    """
    v = np.array([np.nan if x is None else x for x in fc[channel]], float)
    ok = ~np.isnan(v)
    return resample(wl_d[ok], v[ok], GRID)

C = _dye("cyan"); M = _dye("magenta"); Y = _dye("yellow")
DYE = np.stack([C, M, Y])

# ---------- Status M responsivities (red truncated at 700, renormalized) ----------
smj = json.load(open(DATA / "standards" / "StatusM_ISO5-3.json"))
smw = np.array(smj["wavelength_nm"], float)
red_full = np.array(smj["responsivity_linear_peak1"]["red"], float)
red_trunc = np.where(smw <= 700, red_full, 0.0)
tail_pct = 100.0 * (1.0 - red_trunc.sum() / red_full.sum())
SM_R = resample(smw, red_trunc, GRID)
SM_G = resample(smw, smj["responsivity_linear_peak1"]["green"], GRID)
SM_B = resample(smw, smj["responsivity_linear_peak1"]["blue"], GRID)
SM = np.stack([SM_R, SM_G, SM_B]); SM_n = SM / SM.sum(1, keepdims=True)

# ---------- RP-180 printing-density responsivities ----------
rpj = json.load(open(DATA / "standards" / "RP180_responsivities.json"))
rpw = np.array(rpj["wavelength_nm"], float)
RP = np.stack([resample(rpw, np.array(rpj["red"], float), GRID),
               resample(rpw, np.array(rpj["green"], float), GRID),
               resample(rpw, np.array(rpj["blue"], float), GRID)])
RP_n = RP / RP.sum(1, keepdims=True)


def statusm_fwd(dye):
    return density(SM_n, dye, DYE)


def print_fwd(dye):
    return density(RP_n, dye, DYE)


def invert_statusm(target, iters=20):
    """Gauss-Newton with a finite-difference Jacobian for a single triplet."""
    d = np.array([0.5, 0.5, 0.5], float)
    eps = 1e-5
    for _ in range(iters):
        f = statusm_fwd(d)[0]
        J = np.empty((3, 3))
        for k in range(3):
            dp = d.copy(); dp[k] += eps
            J[:, k] = (statusm_fwd(dp)[0] - f) / eps
        d = np.clip(d - np.linalg.solve(J, f - target), -0.5, 6.0)
    res = float(np.max(np.abs(statusm_fwd(d)[0] - target)))
    return d, res


def curve_density(curves, name, logH):
    grid = np.array(curves["log_exposure"], float)
    dens = np.array([np.nan if v is None else v for v in curves["density"][name]], float)
    ok = ~np.isnan(dens)                 # grid-edge NaNs outside the traced span are normal
    if not ok.any():
        raise SystemExit("channel %s not emitted by the digitizer; cannot proceed" % name)
    if not (grid[ok][0] <= logH <= grid[ok][-1]):
        raise SystemExit("channel %s: logH %.3f outside traced span %.2f..%.2f"
                         % (name, logH, grid[ok][0], grid[ok][-1]))
    return float(np.interp(logH, grid[ok], dens[ok]))


def offsets_at(curves, logH):
    """Return (statusM_rel, dye, residual, PD, zero_mean_offsets, R_ref_offsets)."""
    dmin = curves["dmin"]
    sm_rel = np.array([curve_density(curves, n, logH) - float(dmin[n]) for n in ("R", "G", "B")])
    dye, res = invert_statusm(sm_rel)
    pd = print_fwd(dye)[0]
    zero_mean = pd.mean() - pd          # positive => channel needs more density
    r_ref = pd[0] - pd                  # R referenced to 0
    return sm_rel, dye, res, pd, zero_mean, r_ref


def main():
    curves = json.load(open(DATA / "films" / "V3500T_datasheet_curves.json"))["char_curves"]
    logH_mid = float(curves["camera_stops_zero_logH"])

    sm_rel, dye, res, pd, zero_mean, r_ref = offsets_at(curves, logH_mid)

    print("Status M red truncated at 700 nm, renormalized (tail dropped %.3f%%)" % tail_pct)
    print("anchor logH_mid (camera stop 0) = %.5f" % logH_mid)
    print("base-relative Status M triplet [R,G,B] = [%.4f %.4f %.4f]" % tuple(sm_rel))
    print("inverted dye amounts [C,M,Y]           = [%.4f %.4f %.4f]" % tuple(dye))
    print("Status M inversion residual            = %.6f D" % res)
    print("RP-180 printing-density triplet [R,G,B]= [%.4f %.4f %.4f]" % tuple(pd))
    print("printer-light offsets (positive = channel needs more density):")
    print("  zero-mean  [R,G,B] = [%+.4f %+.4f %+.4f]" % tuple(zero_mean))
    print("  R-referenced       = [%+.4f %+.4f %+.4f]" % tuple(r_ref))

    # ---- sensitivity: +/- one camera stop ----
    print("=== sensitivity to mid-gray choice (+/- 1 camera stop) ===")
    zms = [zero_mean]
    rrs = [r_ref]
    for dlog in (-STOP_LOG, STOP_LOG):
        _, _, _, _, zm, rr = offsets_at(curves, logH_mid + dlog)
        zms.append(zm); rrs.append(rr)
        print("  logH %+.4f: zero-mean [%+.4f %+.4f %+.4f]" % (logH_mid + dlog, *zm))
    zms = np.array(zms); rrs = np.array(rrs)
    zm_spread = zms.max(0) - zms.min(0)
    rr_spread = rrs.max(0) - rrs.min(0)
    print("  zero-mean offset spread [R,G,B]   = [%.4f %.4f %.4f]" % tuple(zm_spread))
    print("  R-referenced offset spread [R,G,B]= [%.4f %.4f %.4f]" % tuple(rr_spread))

    out = {
        "title": "Vision3 500T stock-dependent printer-light preset (RP-180 PD equalization)",
        "anchor_logH_mid": round(logH_mid, 5),
        "base_relative_statusM_triplet_RGB": [round(float(v), 4) for v in sm_rel],
        "inverted_dye_CMY": [round(float(v), 4) for v in dye],
        "statusM_inversion_residual_D": round(res, 6),
        "printing_density_triplet_RGB": [round(float(v), 4) for v in pd],
        "printer_light_offsets": {
            "convention": "density trims; positive = channel needs more density",
            "zero_mean_RGB": [round(float(v), 4) for v in zero_mean],
            "R_referenced_RGB": [round(float(v), 4) for v in r_ref],
        },
        "sensitivity_pm1_stop": {
            "zero_mean_spread_RGB": [round(float(v), 4) for v in zm_spread],
            "R_referenced_spread_RGB": [round(float(v), 4) for v in rr_spread],
        },
        "provenance": {
            "curves": "data/films/V3500T_datasheet_curves.json",
            "dye_basis": "data/films/Vision3_dye_density.json",
            "status_m": "data/standards/StatusM_ISO5-3.json (responsivity_linear_peak1, "
                        "red truncated at 700 nm and renormalized)",
            "rp180": "data/standards/RP180_responsivities.json",
            "grid_nm": [int(GRID[0]), int(GRID[-1])],
            "statusM_red_tail_dropped_pct": round(tail_pct, 4),
            "date": "2026-07-24",
        },
    }
    outp = BUILDS / "ecn2" / "V3500T_printer_lights.json"
    outp.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(outp, "w"), indent=1)
    print("wrote %s" % outp.relative_to(ROOT))


if __name__ == "__main__":
    main()
