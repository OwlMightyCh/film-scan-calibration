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
# Camera SSF: the default 'none' presumes no particular camera -- a unity
# (monochrome) response. Naming a body (a bare name from data/cameras/, or a
# path) is the opt-in. It reaches only the decoupling diagnostic, never the fit.
DEFAULT_SENSOR = "none"
_bp.add_argument("--sensor", default=DEFAULT_SENSOR,
                 help="camera SSF: 'none' for a unity (monochrome) response, or "
                      "a bare name from data/cameras/ or a path to presume a "
                      "particular camera (default: %s)" % DEFAULT_SENSOR)
_ba, _rest = _bp.parse_known_args()
BASIS_NAME, OUT_SUFFIX = _ba.basis, _ba.out_suffix
sys.argv = [sys.argv[0]] + _rest


def resolve_sensor(value):
    """(path, label) for --sensor; path is None for the unity/monochrome case."""
    if value == "none":
        return None, "none (unity response; monochrome sensor)"
    cams = DATA / "cameras"
    if "/" in value or "\\" in value:
        path = Path(value)
    elif value.endswith(".json"):
        path = cams / value
        if not path.exists():
            path = Path(value)
    else:
        path = cams / ("%s_ssf.json" % value)
    if not path.exists():
        raise SystemExit("sensor file not found: %s\n(look in %s)" % (path, cams))
    return path, path.name


SENSOR_PATH, SENSOR_LABEL = resolve_sensor(_ba.sensor)
MONO = SENSOR_PATH is None
# data/films/<Stock>_dye_density.json is shipped data. The fitted dye curves are
# sensor-independent -- only the decoupling diagnostic moves with --sensor -- so
# a run that names a camera must never rewrite the canonical file.
if _ba.sensor != DEFAULT_SENSOR and not OUT_SUFFIX:
    raise SystemExit(
        "--sensor %s names a camera, so it requires --out-suffix: the fitted "
        "dye curves are sensor-independent (only the decoupling diagnostic "
        "would change), so "
        "this run must not overwrite the canonical data/films/ JSON." % _ba.sensor)

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

# How this basis identifies itself in the written metadata.  These were three
# hardcoded mentions of Vision3, so an ensemble fit against any other basis
# still described itself as Vision3 and the recorded provenance could not be
# used to tell one fit from another.  The vision3 wording is reproduced exactly
# so the canonical files stay byte-identical.
if BASIS_NAME == "parametric":
    BASIS_SHORT = "parametric"
    BASIS_DESC = "parametric asymmetric-Gaussian dyes, derived from no film"
    BASIS_LABEL = "parametric asymmetric-Gaussian dye set"
else:
    BASIS_SHORT = BASES[BASIS_NAME].replace("_dye_density.json", "")
    BASIS_DESC = "%s shared_full_curves" % BASIS_SHORT
    BASIS_LABEL = ("Vision3 ECN-2 image-dye set" if BASIS_NAME == "vision3"
                   else "%s dye set" % BASIS_SHORT)


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
# 687.9). The digitizer FLAT-HOLDS its last traced value across that gap, so the
# curve arrives here already carrying invented samples -- 51 of them across the
# five Kodak stocks, up to 12 nm wide on Ektar 100 and held at a density of 1.33,
# not at some negligible tail. They are indistinguishable in the array from
# measured ones. (A flat hold is no safer than the zero fill it replaced; both
# state a density nobody read off the chart.)
#
# Fitting to those points was harmless while the Vision3 basis was itself flat
# at the blue end. The corrected basis has a real, steep cyan descender across
# 400-420 nm, so the synthesized edge now fights it: the
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
except (KeyError, TypeError) as _exc:
    # A missing audit block used to fall through in silence, which is the worst
    # available outcome: the fit would quietly run against the fabricated edges
    # and report a residual that looks no different from a clean one. Say so
    # loudly instead. The run continues, because the fallback is still the
    # historical behaviour, but it can no longer pass unnoticed.
    print("WARNING: %s carries no digitization_audit.spectral_dye_density."
          "endpoints block, so the measured support is unknown and the fit "
          "runs over the WHOLE 400-700 nm grid, fabricated edges included (%s: %s)."
          % (STOCK["curves_json"], type(_exc).__name__, _exc))


# ---------- bounded least-squares fit ----------
# params: a,b,c, sC,sM,sY, wC,wM,wY
def model(p):
    a, b, c, sC, sM, sY, wC, wM, wY = p
    return (a * warp("cyan", sC, wC) +
            b * warp("magenta", sM, wM) +
            c * warp("yellow", sY, wY))


def resid(p):
    return (model(p) - aggregate)[_fit_mask]


# The peak-shift bound is UNIFORM at +/-25 nm on every stock -- see the note
# above STOCKS in portra_stocks.py for why. A per-stock bound is inadmissible:
# it would fit different stocks under different priors and thereby render
# cross-stock comparison meaningless. The default below must stay 25.0; +/-15 is
# the retired historical value and, per that note, was never justified.
SHIFT_BOUND = float(STOCK.get("shift_bound_nm", 25.0))
WIDTH_BOUND = (0.85, 1.15)                # same on every stock

p0 = [1.0, 1.0, 1.0, 0, 0, 0, 1.0, 1.0, 1.0]
lo = [0, 0, 0] + [-SHIFT_BOUND] * 3 + [WIDTH_BOUND[0]] * 3
hi = [10, 10, 10] + [SHIFT_BOUND] * 3 + [WIDTH_BOUND[1]] * 3

# ---------- multistart: one start point is not a fit ----------
# `least_squares` is a LOCAL method. It walks downhill from wherever it is put
# and stops in that basin, so a single fixed p0 reports the basin p0 happens to
# sit in rather than the best fit available under these bounds. This objective
# is genuinely multi-modal: three warped bands overlap, and a stock can trade
# cyan shift against cyan width against amplitude to reach several distinct
# local optima that reconstruct the aggregate almost equally well.
#
# Measured on this fleet, the single start was landing short on most stocks --
# Ektar 100 by 29.5%, Ultra Max 400 by 23.8%, Portra 400 by 15.0% in RMSE. The
# resulting displacement of the fitted DYE SETS, 0.023-0.073 D mean |dD|, was
# several times the 0.004-0.012 D spread between stocks that the fleet's
# chemistry conclusions rest on. The start point was contributing more to a
# stock's fitted dyes than the stock's own datasheet did, which is the whole
# defect: an arbitrary numerical choice was being read as emulsion design.
#
# Determinism matters more here than in most sampling. A rebuild must reproduce
# the shipped JSON exactly, so the starts come from a SEEDED generator and both
# the seed and the count are recorded in fit_audit. p0 is always evaluated
# first and kept unless something strictly beats it, so this can never do worse
# than the single-start result it replaces.
#
# Sampling: shape parameters over their full bounds, since those carry the
# multi-modality; amplitudes over a generous 0.2-3.0 rather than their formal
# 0-10, because every fitted amplitude on the fleet lies in 0.72-1.21 and
# sampling the far tail only wastes starts. Sampling amplitudes at p0 instead
# reaches the identical optimum on every stock tested, but needs up to 49
# starts where this needs 8 -- the wider draw is faster, not more permissive.
N_STARTS = 64
MULTISTART_SEED = 20260819
_AMP_START_RANGE = (0.2, 3.0)


def _fit_from(start):
    return least_squares(resid, start, bounds=(lo, hi), method="trf", max_nfev=20000)


def _rms(solution):
    r = np.asarray(resid(solution.x))
    return float(np.sqrt(np.mean(r ** 2)))


sol = _fit_from(p0)
_single_start_rmse = _rms(sol)
_best_rms = _single_start_rmse
_winning_start = 0

_rng = np.random.default_rng(MULTISTART_SEED)
_lo_arr, _hi_arr = np.asarray(lo, float), np.asarray(hi, float)
_amp_hi = np.minimum(_hi_arr[:3], _AMP_START_RANGE[1])
for _k in range(1, N_STARTS + 1):
    _s0 = np.asarray(p0, float).copy()
    _s0[:3] = _rng.uniform(_AMP_START_RANGE[0], _amp_hi)
    _s0[3:] = _lo_arr[3:] + _rng.random(6) * (_hi_arr[3:] - _lo_arr[3:])
    try:
        _cand = _fit_from(_s0)
    except Exception as _exc:                     # a diverged start is not an error
        print("  start %d failed (%s), skipped" % (_k, type(_exc).__name__))
        continue
    _v = _rms(_cand)
    if _v < _best_rms - 1e-12:                    # strict: ties keep the earlier start
        sol, _best_rms, _winning_start = _cand, _v, _k

_improvement_pct = (100.0 * (_single_start_rmse - _best_rms) / _single_start_rmse
                    if _single_start_rmse > 0 else 0.0)
if _winning_start:
    print("multistart: %d starts, best is #%d -- RMSE %.5f -> %.5f (%.1f%% better "
          "than the single fixed start)"
          % (N_STARTS, _winning_start, _single_start_rmse, _best_rms, _improvement_pct))
else:
    print("multistart: %d starts, none beat the fixed start (RMSE %.5f) -- p0 is "
          "already in the best basin found" % (N_STARTS, _single_start_rmse))

a, b, c, sC, sM, sY, wC, wM, wY = sol.x
recon = model(sol.x)
err = (recon - aggregate)[_fit_mask]          # quality is judged on measured data only
rmse = float(np.sqrt(np.mean(err ** 2)))
maxerr = float(np.max(np.abs(err)))

# ---------- did the solution land ON a bound? ----------
# A parameter resting exactly on its bound is not a fitted value: it is the
# constraint speaking, and the residual it reports is the best the model could
# do while held there. Half the fleet does this and nothing said so, the fact
# surviving only in hand-written commentary that named the shift pins and never
# the width ones. Report every pin, on both parameter families, from the numbers
# themselves.
_PIN_EPS = 1e-6
_pins = {}
for _k, _v in (("sC", sC), ("sM", sM), ("sY", sY)):
    if abs(abs(float(_v)) - SHIFT_BOUND) < _PIN_EPS:
        _pins[_k] = "shift at %+.2f nm (bound +/-%g)" % (float(_v), SHIFT_BOUND)
for _k, _v in (("wC", wC), ("wM", wM), ("wY", wY)):
    for _b in WIDTH_BOUND:
        if abs(float(_v) - _b) < _PIN_EPS:
            _pins[_k] = "width at %.2f (bound %g-%g)" % (float(_v), *WIDTH_BOUND)
if _pins:
    print("WARNING: %d of 6 shape parameters are PINNED to a bound -- the fit "
          "was constrained, not free, and this stock's residual must be read "
          "in that light:" % len(_pins))
    for _k in sorted(_pins):
        print("           %s: %s" % (_k, _pins[_k]))

# The warp is basis(p + (l-p)/w - s), whose peak therefore lands at p + s*w and
# NOT at p + s. The two differ by up to 15% of s at the width bounds, so `s` on
# its own is not the physical displacement it is often read as; the derived
# value below is. Reported alongside rather than in place of the parameters,
# which are what the optimiser actually solved for.
_peak_shift = {"cyan": float(sC * wC), "magenta": float(sM * wM),
               "yellow": float(sY * wY)}

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
if MONO:
    S_R = S_G = S_B = 1.0   # unity response: PHI is the LED SPD alone
else:
    ct = open(SENSOR_PATH).read()
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
              "projected onto the %s as surrogate basis"
              % (datasheet_label(STOCK), STOCK["curves_json"], BASIS_LABEL),
    "uncertainty": ("Surrogate-basis method: Portra's actual couplers are not published, "
                    "so the mid-minus-min aggregate was decomposed onto warped %s "
                    "dyes (shift parameter +/-%g nm, width-scale %g-%g; the peak "
                    "moves by shift x width, see peak_shift_nm). Aggregate "
                    "reconstruction RMSE %.4f D, max abs %.4f D over the MEASURED support. "
                    "Per-layer separation is model-dependent; treat off-peak/crosstalk "
                    "values as ~+/-0.05 and the whole set as provisional."
                    % (BASIS_SHORT, SHIFT_BOUND, WIDTH_BOUND[0], WIDTH_BOUND[1],
                       rmse, maxerr)),
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
        "basis": "%s (peak-normalized), peak wavelengths %s" % (BASIS_DESC, peak_wl),
        "params": {"a": round(float(a), 5), "b": round(float(b), 5), "c": round(float(c), 5),
                   "sC": round(float(sC), 4), "sM": round(float(sM), 4), "sY": round(float(sY), 4),
                   "wC": round(float(wC), 5), "wM": round(float(wM), 5), "wY": round(float(wY), 5)},
        "bounds": {"shift_nm": SHIFT_BOUND, "width_scale": list(WIDTH_BOUND)},
        "bounds_pinned": _pins or None,
        "bounds_pinned_note": "parameters resting exactly on a bound; their value is "
                              "the constraint, not a fitted optimum, and any comparison "
                              "against another stock is confounded by it",
        "peak_shift_nm": {k: round(v, 4) for k, v in _peak_shift.items()},
        "peak_shift_note": "actual displacement of each dye's peak, s*w -- the warp is "
                           "basis(p + (l-p)/w - s), so the peak lands at p + s*w and the "
                           "shift parameter s alone is NOT the physical shift in nm",
        "aggregate_rmse_density": round(rmse, 5),
        "aggregate_maxabs_density": round(maxerr, 5),
        "multistart": {
            "n_starts": N_STARTS,
            "seed": MULTISTART_SEED,
            "winning_start": _winning_start,
            "single_start_rmse": round(_single_start_rmse, 5),
            "improvement_pct": round(_improvement_pct, 2),
            "note": "least_squares is a local method, so a lone start reports its own "
                    "basin rather than the best fit under these bounds. Starts are drawn "
                    "from the seeded generator above and the fixed p0 is always tried "
                    "first, so the result is reproducible and never worse than "
                    "single-start. winning_start 0 means p0 was not beaten",
        },
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
    print("  excluded %d of %d grid points as synthesized datasheet edge (never measured)"
          % (_n, len(GRID)))
print("=== Status M constraint (dmin+fit vs digitized midscale) ===")
print("reconstructed RGB %s" % np.round(sm_recon, 4).tolist())
print("digitized     RGB %s" % np.round(sm_direct, 4).tolist())
print("delta         RGB %s" % np.round(sm_delta, 4).tolist())
print("Status M of digitized midscale RGB %s   dmin RGB %s"
      % (np.round(sm_mid, 4).tolist(), np.round(sm_dmin, 4).tolist()))
print("=== decoupling matrix ===")
print("sensor: %s" % SENSOR_LABEL)
print("condition number %.4f" % cond)
print(red_trunc_note)
print("wrote %s" % outp.relative_to(ROOT))
