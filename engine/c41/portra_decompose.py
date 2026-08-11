#!/usr/bin/env python3
"""Fit per-layer C/M/Y dye spectra for a Kodak Portra stock.

Which stock is selected with --stock (default portra400, i.e. the historical
behaviour); the registry lives in portra_stocks.py.

The datasheet publishes only *diffuse* spectral density (midscale neutral and
D-min), not per-layer dye curves. We recover a plausible per-layer set by
projecting the mid-minus-min aggregate onto the Vision3 (ECN-2) image-dye set
used as a surrogate basis, allowing each basis dye a small peak-shift and
width-scale warp:

    aggregate(l) = midscale(l) - dmin(l)
                 ~ a*C(l;sC,wC) + b*M(l;sM,wM) + c*Y(l;sY,wY)

9 free parameters (3 amplitudes + shift/width per dye), bounded least squares.
This is a surrogate-basis approximation, not a measurement of Portra's actual
couplers -- the uncertainty field records that.
"""
import argparse, json, re, sys
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares

try:                                     # run as a script from engine/c41
    from portra_stocks import datasheet_label, parse_stock
except ImportError:                      # imported as engine.c41.portra_decompose
    from engine.c41.portra_stocks import datasheet_label, parse_stock

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
GRID = np.arange(400, 701, 1.0)

sys.path.insert(0, str(ROOT))
from engine.common.spectral import resample   # noqa: E402
LED = [450, 544, 640]

# Ensemble args are consumed BEFORE parse_stock: that parser is shared and
# strict, so it would reject --basis/--out-suffix as unrecognized.
_BASIS_CHOICES = ["vision3", "e100", "provia100f", "velvia50", "velvia100",
                  "parametric"]
_bp = argparse.ArgumentParser(add_help=False)
_bp.add_argument("--basis", choices=_BASIS_CHOICES, default="vision3")
_bp.add_argument("--out-suffix", default="")
_ba, _rest = _bp.parse_known_args()
BASIS_NAME, OUT_SUFFIX = _ba.basis, _ba.out_suffix
sys.argv = [sys.argv[0]] + _rest

STOCK = parse_stock(__doc__.splitlines()[0])


# ---------- surrogate basis (peak-normalized) ----------
# Default is the Vision3 ECN-2 image-dye set (the canonical choice; shared
# KODAK VISION lineage). --basis swaps it for the basis-sensitivity ensemble:
# the aggregate constrains only the SUM of three dyes, never the split, so the
# only way to measure how much of the answer is the prior rather than the data
# is to refit against other plausible bases and see how far the cube moves.
# Ensemble runs must also pass --out-suffix so they cannot clobber canonical data.
BASES = {
    "vision3":    "Vision3_dye_density.json",             # canonical (family-avg, 2026-07-28)
    "e100":       "EktachromeE100_dye_density.json",
    "provia100f": "Provia100F_dye_density.json",
    "velvia50":   "Velvia50_dye_density.json",
    "velvia100":  "Velvia100_dye_density.json",
}
bw = np.arange(380.0, 801.0, 1.0)
if BASIS_NAME == "parametric":
    # Basis-FREE control: smooth asymmetric-Gaussian dyes derived from no film
    # at all, only from the three peak positions any C-41 set must have. If the
    # cube barely moves even against this, the aggregate is doing the work
    # rather than the prior.
    def _asym(peak, wl, wr):
        s = np.where(bw < peak, wl, wr)
        return np.exp(-0.5 * ((bw - peak) / s) ** 2)
    basis = {"cyan": _asym(680.0, 45.0, 30.0),
             "magenta": _asym(540.0, 35.0, 40.0),
             "yellow": _asym(440.0, 30.0, 35.0)}
else:
    vj = json.load(open(DATA / "films" / BASES[BASIS_NAME]))
    fc = vj["shared_full_curves"]
    _w = np.array(fc["wavelength_nm"], float)
    basis = {}
    for _k in ("cyan", "magenta", "yellow"):
        _v = np.array([np.nan if v is None else v for v in fc[_k]], float)
        _m = ~np.isnan(_v)
        basis[_k] = np.interp(bw, _w[_m], _v[_m], left=_v[_m][0], right=_v[_m][-1])
basis = {k: v / v.max() for k, v in basis.items()}   # peak-normalize every basis
peak_wl = {k: float(bw[np.argmax(v)]) for k, v in basis.items()}


def warp(name, s, w):
    """Basis dye 'name' interpolated onto lambda_peak + (l-lambda_peak)/w - s,
    flat-extrapolated beyond the basis grid."""
    p = peak_wl[name]
    src = p + (GRID - p) / w - s
    v = basis[name]
    return np.interp(src, bw, v, left=v[0], right=v[-1])


# ---------- digitized datasheet curves ----------
dj = json.load(open(DATA / "films" / STOCK["curves_json"]))
sp = dj["spectral"]
swl = np.array(sp["wavelength_nm"], float)
midscale = resample(swl, sp["midscale_neutral"], GRID)
dmin = resample(swl, sp["dmin"], GRID)
aggregate = midscale - dmin

# ---------- fit ONLY where the datasheet was actually measured ----------
# Every Kodak spectral trace stops short of the 400 nm frame edge (402.5-403.7,
# depending on stock) and some stop short at the red end too (Ektar 100 at
# 687.9). resample() flat-holds the terminal value across those gaps, so the
# aggregate carries FABRICATED values there -- indistinguishable, in the array,
# from measured ones.
#
# Fitting to them was harmless while the Vision3 basis was itself flat at the
# blue end (fabricated met fabricated). The corrected basis has a real, steep
# cyan descender across 400-420 nm, so the flat-held edge now fights it: the
# 400-410 band became the WORST residual band for every stock (0.020-0.069 D
# against 0.007-0.021 D elsewhere), Ektar worst because its gap is widest.
#
# So the fit is restricted to each stock's own measured support, read from the
# digitizer's audit block. Nothing is discarded from the OUTPUT curves -- only
# from the objective, which must never be driven by values no one measured.
_fit_mask = np.ones_like(GRID, bool)
_support = None
try:
    _ep = dj["digitization_audit"]["spectral_dye_density"]["endpoints"]
    _lo = max(v["wavelength_range_nm"][0] for v in _ep.values())
    _hi = min(v["wavelength_range_nm"][1] for v in _ep.values())
    _support = (_lo, _hi)
    _fit_mask = (GRID >= _lo) & (GRID <= _hi)
except (KeyError, TypeError):
    pass                                  # no audit -> fit everything, as before


# ---------- bounded least-squares fit ----------
# params: a,b,c, sC,sM,sY, wC,wM,wY
def model(p):
    a, b, c, sC, sM, sY, wC, wM, wY = p
    return (a * warp("cyan", sC, wC) +
            b * warp("magenta", sM, wM) +
            c * warp("yellow", sY, wY))


def resid(p):
    return (model(p) - aggregate)[_fit_mask]


# The peak-shift bound is PER STOCK -- see the note above STOCKS in
# portra_stocks.py for why Kodak runs at +/-25 and Fujifilm stays at +/-15.
# Default +/-15 (the historical value) if a stock predates the key.
SHIFT_BOUND = float(STOCK.get("shift_bound_nm", 15.0))
WIDTH_BOUND = (0.85, 1.15)                # same on every stock

p0 = [1.0, 1.0, 1.0, 0, 0, 0, 1.0, 1.0, 1.0]
lo = [0, 0, 0] + [-SHIFT_BOUND] * 3 + [WIDTH_BOUND[0]] * 3
hi = [10, 10, 10] + [SHIFT_BOUND] * 3 + [WIDTH_BOUND[1]] * 3
sol = least_squares(resid, p0, bounds=(lo, hi), method="trf", max_nfev=20000)
a, b, c, sC, sM, sY, wC, wM, wY = sol.x
recon = model(sol.x)
err = (recon - aggregate)[_fit_mask]          # quality is judged on measured data only
rmse = float(np.sqrt(np.mean(err ** 2)))
maxerr = float(np.max(np.abs(err)))

# fitted per-layer curves, each peak-normalized to 1.0
raw = {"cyan": a * warp("cyan", sC, wC),
       "magenta": b * warp("magenta", sM, wM),
       "yellow": c * warp("yellow", sY, wY)}
norm = {k: v / v.max() for k, v in raw.items()}
C, M, Y = norm["cyan"], norm["magenta"], norm["yellow"]
DYE = np.stack([C, M, Y])


# ---------- scanner effective responsivities (mirror cineon_pd_engine) ----------
raw_spd = open(DATA / "equipment" / "film_scanner_SPD_combined.csv").read().strip().splitlines()
hdr = raw_spd[0].split(",")
spd = np.array([[float(x) for x in r.split(",")] for r in raw_spd[1:]])
def col(n): return spd[:, hdr.index(n)]
wl_s = spd[:, 0]
L_R = resample(wl_s, col("R100_G0_B0"), GRID); L_G = resample(wl_s, col("R0_G100_B0"), GRID); L_B = resample(wl_s, col("R0_G0_B100"), GRID)
ct = open(DATA / "equipment" / "a7r2_cfa.md").read()
def arr(k):
    m = re.search(k + r'"?\s*:\s*\[([0-9eE.,\s\\-]*?)\]', ct)
    return np.array([float(x) for x in re.findall(r'-?\d+\.?\d*(?:[eE][-+]?\d+)?', m.group(1))], float)
wl_c = arr("ssf_bands")
S_R = resample(wl_c, arr("red_ssf"), GRID); S_G = resample(wl_c, arr("green_ssf"), GRID); S_B = resample(wl_c, arr("blue_ssf"), GRID)
PHI = np.stack([L_R * S_R, L_G * S_G, L_B * S_B])
PHI_n = PHI / PHI.sum(1, keepdims=True)   # per-channel LED*CFA effective responsivity


def scan_density(amounts):
    """Scan density (R,G,B) for dye amounts (dc,dm,dy) at unit peak = 1."""
    amounts = np.atleast_2d(amounts)
    T = 10.0 ** (-(amounts @ DYE))
    return -np.log10(np.clip(T @ PHI_n.T, 1e-12, None))


# decoupling matrix: mixing matrix Amix[i][j] = scan density in channel i from
# unit peak density of dye j; rows R,G,B (LED 640/544/450), columns C,M,Y.
# Channel order R,G,B matches PHI rows (R_LED,G_LED,B_LED).
Amix = np.zeros((3, 3))
for j, amt in enumerate(np.eye(3)):
    Amix[:, j] = scan_density(amt)[0]
Dec = np.linalg.inv(Amix)
Dec = Dec / np.diag(Dec)[:, None]          # diag-normalized to 1
cond = float(np.linalg.cond(Dec))


# ---------- Status M constraint check ----------
smj = json.load(open(DATA / "standards" / "StatusM_ISO5-3.json"))
smw = np.array(smj["wavelength_nm"], float)
PM = np.stack([resample(smw, smj["responsivity_linear_peak1"]["red"], GRID),
               resample(smw, smj["responsivity_linear_peak1"]["green"], GRID),
               resample(smw, smj["responsivity_linear_peak1"]["blue"], GRID)])
# red support extends to 770 nm but dye data ends at 700 -> truncate & renormalize
PM_n = PM / np.clip(PM.sum(1, keepdims=True), 1e-12, None)
# tail fraction measured on the standard's own 400-770 nm grid (10 nm)
red_full = np.array(smj["responsivity_linear_peak1"]["red"], float)
red_area_full = red_full.sum()
red_area_700 = red_full[smw <= 700].sum()
red_trunc_note = ("Status M red responsivity truncated at 700 nm (dye data limit) "
                  "and renormalized; the excluded 700-770 nm tail carries "
                  "%.2f%% of the full red area." %
                  (100.0 * (1.0 - red_area_700 / red_area_full)))


def statusM_density(spectrum):
    T = 10.0 ** (-spectrum)
    return -np.log10(np.clip(PM_n @ T, 1e-12, None))


sm_recon = statusM_density(dmin + recon)          # reconstructed midscale
sm_direct = statusM_density(midscale)             # digitized midscale directly
sm_delta = (sm_recon - sm_direct)                 # per-channel R,G,B
sm_mid = sm_direct                                 # Status M density of digitized midscale
sm_dmin = statusM_density(dmin)                    # Status M density of digitized D-min


# ---------- dye density at LED wavelengths (from peak-normalized curves) ----------
def at_led(v):
    return [round(float(np.interp(w, GRID, v)), 4) for w in LED]


out = {
    "title": "Kodak %s — per-layer spectral dye density (surrogate-basis fit)"
             % STOCK["display_name"],
    "family": "C-41 colour negative",
    "stocks_covered": [STOCK["display_name"]],
    "normalization": "peak = 1.0 per dye",
    "units": "relative diffuse spectral density (Status M, D-min subtracted)",
    "source": "Fitted to %s midscale-neutral "
              "minus D-min spectral density (see %s), "
              "projected onto the Vision3 ECN-2 image-dye set as surrogate basis"
              % (datasheet_label(STOCK), STOCK["curves_json"]),
    "uncertainty": ("Surrogate-basis method: Portra's actual couplers are not published, "
                    "so the mid-minus-min aggregate was decomposed onto warped Vision3 "
                    "dyes (peak-shift +/-%g nm, width-scale %g-%g). Aggregate "
                    "reconstruction RMSE %.4f D, max abs %.4f D over the MEASURED support. "
                    "Per-layer separation is model-dependent; treat off-peak/crosstalk "
                    "values as ~+/-0.05 and the whole set as provisional."
                    % (SHIFT_BOUND, WIDTH_BOUND[0], WIDTH_BOUND[1], rmse, maxerr)),
    "shared_full_curves": {
        "wavelength_nm": [int(x) for x in GRID],
        "cyan": [round(float(x), 4) for x in C],
        "magenta": [round(float(x), 4) for x in M],
        "yellow": [round(float(x), 4) for x in Y],
    },
    "led_wavelengths_nm": LED,
    "per_stock": {
        STOCK["speed_key"]: {
            "dye_density_at_led_wavelengths": {
                "wavelength_nm": LED,
                "cyan": at_led(C),
                "magenta": at_led(M),
                "yellow": at_led(Y),
            },
            "decoupling_matrix_rowmajor_RGB_density": [[round(float(x), 4) for x in row] for row in Dec],
            "matrix_note": "rows=R/G/B scan density @640/544/450; columns=cyan/magenta/yellow; "
                           "diag-normalized inverse of the LED-SPD x CFA mixing matrix "
                           "(scan density per unit peak dye density); off-diagonals = crosstalk removed",
        }
    },
    "fit_audit": {
        "basis": "Vision3 shared_full_curves (peak-normalized), peak wavelengths %s" % peak_wl,
        "params": {"a": round(float(a), 5), "b": round(float(b), 5), "c": round(float(c), 5),
                   "sC": round(float(sC), 4), "sM": round(float(sM), 4), "sY": round(float(sY), 4),
                   "wC": round(float(wC), 5), "wM": round(float(wM), 5), "wY": round(float(wY), 5)},
        "bounds": {"shift_nm": SHIFT_BOUND, "width_scale": list(WIDTH_BOUND)},
        "aggregate_rmse_density": round(rmse, 5),
        "aggregate_maxabs_density": round(maxerr, 5),
        "statusM_constraint": {
            "note": "Status M density of reconstructed midscale (dmin+fit) vs digitized midscale",
            "reconstructed_RGB": [round(float(x), 4) for x in sm_recon],
            "digitized_RGB": [round(float(x), 4) for x in sm_direct],
            "delta_RGB": [round(float(x), 4) for x in sm_delta],
        },
        "statusM_of_digitized_curves": {
            "note": "for reference against the characteristic curves",
            "midscale_neutral_RGB": [round(float(x), 4) for x in sm_mid],
            "dmin_RGB": [round(float(x), 4) for x in sm_dmin],
        },
        "decoupling_condition_number": round(cond, 4),
        "statusM_red_truncation": red_trunc_note,
    },
}
outp = DATA / "films" / STOCK["dye_density_json"]
if OUT_SUFFIX:                       # ensemble run: never touch canonical data
    _ens = DATA / "films" / "_ensemble"
    _ens.mkdir(exist_ok=True)
    outp = _ens / STOCK["dye_density_json"].replace(".json", "__%s.json" % OUT_SUFFIX)
json.dump(out, open(outp, "w"), indent=1)


# ---------- mandatory stdout ----------
print("=== fitted params ===")
print("a=%.4f b=%.4f c=%.4f  sC=%.3f sM=%.3f sY=%.3f  wC=%.4f wM=%.4f wY=%.4f"
      % (a, b, c, sC, sM, sY, wC, wM, wY))
print("=== aggregate reconstruction (midscale - dmin) ===")
print("RMSE %.4f D   max abs %.4f D   over the MEASURED support %s"
      % (rmse, maxerr,
         ("%.1f-%.1f nm" % _support) if _support else "400-700 nm (no audit block)"))
if _support:
    _n = int((~_fit_mask).sum())
    print("  excluded %d of %d grid points as flat-held datasheet edge (never measured)"
          % (_n, len(GRID)))
print("=== Status M constraint (dmin+fit vs digitized midscale) ===")
print("reconstructed RGB %s" % np.round(sm_recon, 4).tolist())
print("digitized     RGB %s" % np.round(sm_direct, 4).tolist())
print("delta         RGB %s" % np.round(sm_delta, 4).tolist())
print("Status M of digitized midscale RGB %s   dmin RGB %s"
      % (np.round(sm_mid, 4).tolist(), np.round(sm_dmin, 4).tolist()))
print("=== decoupling matrix ===")
print("condition number %.4f" % cond)
print(red_trunc_note)
print("wrote %s" % outp.relative_to(ROOT))
