#!/usr/bin/env python3
"""C-41 scanner-density -> Status M density transform (65^3 .cube).

Stock-generic: parameterized by film stock via --stock (registry:
engine/c41/portra_stocks.py), one engine for every C-41 stock in the registry.
The default, portra400, reproduces that build exactly as it always has.

Renamed from portra400_statusm_engine.py (2026-07-27).  The old name predated
--stock and described the only stock it could then build; it had no importers,
only prose references.

Mirrors engine/ecn2/adx_engine.py: same SPD/CFA loading idioms, the same
per-node Gauss-Newton inversion over a scan-density lattice, and the same
cube shaper/domain conventions. The only substantive differences are:

  * dyes come from <Stock>_dye_density.json (C-41, surrogate-basis fit);
  * the print/target space is ISO Status M (StatusM_ISO5-3.json) instead of
    Academy Printing Density;
  * Status M red support runs to 770 nm but the dye data ends at 700 nm, so
    the red responsivity is truncated at 700 and renormalized (density is a
    Pi-weighted average, so renormalization is exact; the note is printed).

Like adx_engine, D-min is NOT baked into the LUT: the forward model uses
only the three image-dye amounts (dc,dm,dy); D-min is a per-roll anchor applied
upstream, exactly as that engine leaves it out (it never adds a base term
to the dye stack). This is stated on stdout.

The anchor is applied in INTEGRATED scan density (RollAnchor_ScanPrep.dctl
divides the linear frame by the base's own reading), so what the cube receives
is the density of the image dyes as seen through the base and orange mask:
    D_anch = -log10( INT PHI 10^-(Dmin+dye.DYE) / INT PHI 10^-Dmin ),
i.e. density under the illuminant PHI 10^-Dmin(l), renormalised. The scan-side
responsivity is therefore that mask-filtered illuminant, built from the stock's
traced D-min spectrum; the target side stays the Status M of the dye stack
alone. The mask is far from flat across an LED band (Portra 400 falls 0.11 D
over the green LED's 528-560 nm FWHM), and with the bare illuminant the cube
would read a neutral midscale negative 0.06 D low in green.
"""
import argparse, json, re, sys
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"; BUILDS = ROOT / "builds"
GRID = np.arange(400, 701, 1.0)   # dye data ends at 700 nm

sys.path.insert(0, str(ROOT))
from engine.common.spectral import density, resample   # noqa: E402
from engine.common.lut import trilerp_unit, tetralerp_unit   # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))   # sibling module import
from portra_stocks import STOCKS as PORTRA_STOCKS, DEFAULT_STOCK   # noqa: E402
from neutral_locus import sheet_neutral_locus, K_MID   # noqa: E402

# ---------- stock selection ----------
_ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
_ap.add_argument("--stock", choices=sorted(PORTRA_STOCKS), default=DEFAULT_STOCK,
                 help="film stock to build (default: %s)" % DEFAULT_STOCK)
# Basis-sensitivity ensemble overrides. Both must be given together; they exist
# so an ensemble run can build a cube from an alternative-basis dye set without
# touching either the canonical dye JSON or the canonical cube.
_ap.add_argument("--dye-json", default=None,
                 help="override dye-density JSON path (ensemble use)")
_ap.add_argument("--out-cube", default=None,
                 help="override output .cube path (ensemble use)")
# Camera spectral sensitivity. The default, 'none', presumes no particular
# camera: unity response at every wavelength, so PHI is the scanner illuminant
# alone. Naming a body is the opt-in, and its cube is written under
# builds/sensor-<Body>/ so it cannot displace the canonical build.
DEFAULT_SENSOR = "none"
_ap.add_argument("--sensor", default=DEFAULT_SENSOR,
                 help="camera SSF: 'none' for a unity (monochrome) response, "
                      "or a bare name from data/cameras/ or a path to presume "
                      "a particular camera (default: %s)" % DEFAULT_SENSOR)
_args = _ap.parse_args()
STOCK = PORTRA_STOCKS[_args.stock]
if bool(_args.dye_json) != bool(_args.out_cube):
    raise SystemExit("--dye-json and --out-cube must be given together, so an "
                     "ensemble build can never overwrite a canonical cube.")


# ---------- sensor selection ----------
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


def sensor_stem(value):
    """Directory stem for a named sensor, e.g. 'Sony_ILCE-7RM3'."""
    name = Path(value).name
    if name.endswith(".json"):
        name = name[:-len(".json")]
    if name.endswith("_ssf"):
        name = name[:-len("_ssf")]
    return name


SENSOR_PATH, SENSOR_LABEL = resolve_sensor(_args.sensor)
MONO = SENSOR_PATH is None


# ---------- Portra dyes ----------
_dye_path = Path(_args.dye_json) if _args.dye_json else DATA / "films" / STOCK["dye_density_json"]
dj = json.load(open(_dye_path)); fc = dj["shared_full_curves"]
wl_d = np.array(fc["wavelength_nm"], float)
C = resample(wl_d, fc["cyan"], GRID); M = resample(wl_d, fc["magenta"], GRID); Y = resample(wl_d, fc["yellow"], GRID)
DYE = np.stack([C, M, Y])

# ---------- scanner LED SPDs x camera CFA (as in adx_engine) ----------
raw = open(DATA / "equipment" / "film_scanner_SPD_combined.csv").read().strip().splitlines()
hdr = raw[0].split(","); data = np.array([[float(x) for x in r.split(",")] for r in raw[1:]])
def col(n): return data[:, hdr.index(n)]
wl_s = data[:, 0]
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

# ---------- Status M responsivities (truncated at 700, renormalized) ----------
smj = json.load(open(DATA / "standards" / "StatusM_ISO5-3.json"))
smw = np.array(smj["wavelength_nm"], float)
P_R = resample(smw, smj["responsivity_linear_peak1"]["red"], GRID)
P_G = resample(smw, smj["responsivity_linear_peak1"]["green"], GRID)
P_B = resample(smw, smj["responsivity_linear_peak1"]["blue"], GRID)
# The omitted tail is measured on the grid the transform integrates on (1 nm,
# resampled), not on the 10 nm source table: the two differ (0.28% against
# 0.49% of red area) and it is the resampled weighting the cube omits.
_full_grid = np.arange(smw.min(), smw.max() + 1.0, 1.0)
_red_full = resample(smw, smj["responsivity_linear_peak1"]["red"], _full_grid)
tail_pct = 100.0 * _red_full[_full_grid > 700].sum() / _red_full.sum()

PHI_bare = np.stack([L_R * S_R, L_G * S_G, L_B * S_B]); PRT = np.stack([P_R, P_G, P_B])
PHI_bare_n = PHI_bare / PHI_bare.sum(1, keepdims=True); PRT_n = PRT / PRT.sum(1, keepdims=True)

# ---------- the roll anchor divides out the base+mask in integrated density ----------
# so the scan side sees the dyes through the mask: PHI x 10^-Dmin(l), renormalised.
cd = json.load(open(DATA / "films" / STOCK["curves_json"]))
sp = cd["spectral"]; swl = np.array(sp["wavelength_nm"], float)
DMIN = resample(swl, sp["dmin"], GRID)
PHI = PHI_bare * 10.0 ** (-DMIN)
PHI_n = PHI / PHI.sum(1, keepdims=True)
_centroid = lambda P: (P * GRID).sum(1) / P.sum(1)
_shift_nm = _centroid(PHI_n) - _centroid(PHI_bare_n)


def scan_fwd(d): return density(PHI_n, d, DYE)
def statusm_fwd(d): return density(PRT_n, d, DYE)
def scan_jac(dye):
    dye = np.atleast_2d(dye); T = 10.0 ** (-(dye @ DYE)); integ = T @ PHI_n.T
    num = np.einsum('nl,il,jl->nij', T, PHI_n, DYE); return -np.log10(np.clip(integ, 1e-12, None)), num / integ[:, :, None]


# ---------- linear seed: scanD = dye @ W ----------
n = 9; ax = np.linspace(0, 2, n)
g = np.array(np.meshgrid(ax, ax, ax, indexing="ij")).reshape(3, -1).T
W, *_ = np.linalg.lstsq(g, scan_fwd(g), rcond=None); Winv = np.linalg.inv(W)

# ---------- per-node inversion over 65^3 lattice in [0,DMAX] ----------
DMAX = 3.30; SZ = 65
axn = np.linspace(0, DMAX, SZ)
node = np.array(np.meshgrid(axn, axn, axn, indexing="ij")).reshape(3, -1).T
dye = node @ Winv
for it in range(12):
    Dv, J = scan_jac(dye); r = Dv - node
    step = np.linalg.solve(J, r[:, :, None])[:, :, 0]
    dye = np.clip(dye - step, -0.5, 6.0)
res = np.max(np.abs(scan_fwd(dye) - node), 1)
print("sensor: %s" % SENSOR_LABEL)
print("D-min handling: EXCLUDED from the LUT (forward model uses only dc,dm,dy; "
      "D-min is a per-roll anchor upstream), mirroring adx_engine.")
print("scan-side responsivity: LED x sensor x 10^-Dmin(l) (the anchor divides the base+mask "
      "out in integrated density); D-min at 450/544/640 nm = %s, LED centroid shift vs bare "
      "R/G/B = %s nm" % (np.round(np.interp([450, 544, 640], GRID, DMIN), 3).tolist(),
                         np.round(_shift_nm, 2).tolist()))
print("Status M red truncation: red support to 770 nm truncated at 700 nm (dye data limit) and "
      "renormalized; excluded 700-770 tail = %.2f%% of red area on the 1 nm integration grid. The "
      "renormalised weighting is exact for ITSELF, not for full Status M: it asserts the unmeasured "
      "tail transmits like the in-band mean, a bounded bias worst in dense cyan (register #13)." % tail_pct)
print(f"node solve: residual mean {res.mean():.4f} max {res.max():.4f} D  (>{0.02:.2f} on {100*np.mean(res>0.02):.1f}% nodes, mostly out-of-gamut corners)")

# ---------- measured corridor requirement (REPORTING ONLY; DMAX is unchanged) ----------
# DMAX is hardcoded at 3.30 for the whole fleet and is never derived from this
# number. Ported from reversal_transform.corridor_requirement(): a neutral stack
# is not the worst case, because each scanner channel's weight sits where its own
# dye is dense, so an off-neutral stack can read deeper in a single channel.
# Probe the neutral AND a coarse sweep of the same dye box, and take the maximum
# over all three channels: that is the smallest corridor which clips nothing.
# The probe box must be bounded by what the FILM reaches, not by an arbitrary
# dye ceiling. The reversal engine probes a dye-4.0 box because a transparency
# genuinely reaches those densities; a C-41 negative does not, and probing 4.0
# here reports a requirement of 3.91 D on Portra 400 and so brands the 3.30
# corridor undersized when the film tops out near 2.2 D. Bound it instead by the
# stock's own published characteristic curve, which is the deepest image density
# the datasheet actually documents.
def corridor_requirement(dye_ceiling):
    """Peak scan density produced over the dye box [0, dye_ceiling]^3.

    A neutral stack is not the worst case: each scanner channel's weight sits
    where its own dye is dense, so an off-neutral stack can read deeper in a
    single channel. Probe the neutral AND a coarse sweep of the same box, and
    take the maximum over all three channels — the smallest corridor that
    clips nothing.
    """
    axis = np.linspace(0.0, dye_ceiling, 5)
    sweep = np.array(np.meshgrid(axis, axis, axis, indexing="ij")).reshape(3, -1).T
    probes = np.vstack([np.full((1, 3), dye_ceiling), sweep])
    return float(np.max(scan_fwd(probes)))


def _bisect_dye(fwd, target_D, hi=32.0, iters=60):
    """Smallest neutral dye amount whose `fwd` response reaches target_D."""
    f = lambda d: float(np.max(fwd(np.full((1, 3), d))))
    if f(hi) < target_D:
        return hi
    lo = 0.0
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if f(mid) < target_D:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def dye_ceiling_for_density(target_D, hi=32.0, iters=60):
    """Dye ceiling whose corridor requirement reaches target_D (scan density)."""
    return _bisect_dye(scan_fwd, target_D, hi, iters)


def datasheet_dye_ceiling():
    """Equal-dye amount whose largest Status M channel reaches the largest
    characteristic-curve span: a SCALAR HEURISTIC for the off-neutral probe box,
    not a reading of the sheet series. It subtracts each curve's own minimum
    (integrated D-min) and reads that as bare image-dye Status M, which the
    sheet series below shows is off by up to 0.01 D (register #13)."""
    _cc = json.load(open(DATA / "films" / STOCK["curves_json"]))["char_curves"]
    _sm = _cc.get("statusM_density", _cc)
    _peak = max(float(np.nanmax(np.array(_sm[k], float))
                      - np.nanmin(np.array(_sm[k], float))) for k in ("R", "G", "B"))
    return _bisect_dye(statusm_fwd, _peak)


_film_dye = datasheet_dye_ceiling()
_needed = corridor_requirement(_film_dye)
# The sheet's neutral series (neutral_locus.py, shared with the print engines)
# gives the corridor line its sheet-series figure and the cube its neutral
# offset below.
_locus = sheet_neutral_locus(DATA / "films" / STOCK["curves_json"], DMIN, DYE, PRT_n, DMAX)
_sheet_logh, _sheet_amounts, _sheet_resid = _locus.log_h, _locus.amounts, _locus.resid
_sheet_scan = scan_fwd(_sheet_amounts)
NEUTRAL_OFFSET_D = _locus.offset * DMAX          # (3,) Status M density, R/G/B
# Headroom above the published maximum is DELIBERATE, not an error: real film can
# be exposed past the end of the characteristic curve, and the corridor has to
# hold those densities rather than clip them. What this line rules out is the
# opposite failure, a corridor too small for the film's own datasheet.
print("corridor: the sheet's neutral series (three records solved together through the spectral "
      "base, %d exposures, solve max |dD| %.4f D, amounts min %+.3f) reaches %.2f D scan density; "
      "the equal-dye heuristic box (dye %.2f) reaches %.2f D; DMAX is %.2f (%.0f%% headroom above "
      "the sheet series). Neither is the film's whole gamut or the scanner's range."
      % (len(_sheet_logh), _sheet_resid, float(_sheet_amounts.min()), float(_sheet_scan.max()),
         _film_dye, _needed, DMAX, 100.0 * (DMAX - float(_sheet_scan.max())) / float(_sheet_scan.max())))
lut = statusm_fwd(dye).reshape(SZ, SZ, SZ, 3)
# ---------- neutral offset: the sheet's neutral series onto the diagonal ----------
# The cube's OUTPUT is image-dye Status M MINUS this stock's neutral offset, so
# the sheet's own neutral exposure series lies on the diagonal k*(1,1,1): where
# Print Adjustment's per-channel pivot at K_MID and the print engine's gray-axis
# lock expect a neutral (a gamma about the pivot would otherwise tilt a neutral
# by offset x (gamma - 1)).  The print engine adds the same offset back before
# inverting; a densitometry comparison adds it back too (quality-control tap).
# Channels whose image-dye density is below the offset clip at 0 on output:
# those nodes sit at the toe, far below the printable window in that channel.
lut_out = lut - NEUTRAL_OFFSET_D[None, None, None, :]
_clipped = float(100.0 * np.mean((lut_out < 0).any(-1)))
print("neutral offset R/G/B = %.4f/%.4f/%.4f D (image-dye Status M of the sheet's neutral series at "
      "k=%.2f, departure from the diagonal; its range over k=%.2f+/-%.2f is %s Dnorm): SUBTRACTED from "
      "the cube output so that series is the diagonal; %.2f%% of lattice nodes clip at 0 in some "
      "channel (image-dye density below the offset there)"
      % (NEUTRAL_OFFSET_D[0], NEUTRAL_OFFSET_D[1], NEUTRAL_OFFSET_D[2], K_MID, K_MID, 0.12,
         np.round(_locus.spread_band, 4).tolist(), _clipped))

# ---------- validate LUT (trilinear) vs direct solve ----------
# PROBE_DYE_MAX is a DYE-AMOUNT ceiling, not a density, and it is NOT the
# corridor: DMAX = 3.30 is a scan-DENSITY corridor. 2.2 dye is the working range
# a real exposure occupies; it covers only part of the domain the cube declares,
# which is why the full-corridor figure is reported alongside it below.
PROBE_DYE_MAX = 2.2
rng = np.random.default_rng(1); gv = rng.uniform(0, PROBE_DYE_MAX, (5000, 3))
sv = scan_fwd(gv); pv = statusm_fwd(gv)
def trilerp(L, pts): return trilerp_unit(L, pts / DMAX)
def tetralerp(L, pts): return tetralerp_unit(L, pts / DMAX)
pv = pv - NEUTRAL_OFFSET_D[None, :]          # the cube's metric: balanced Status M
pl = tetralerp(lut_out, sv); pl_tri = trilerp(lut_out, sv)
print(f"LUT 65^3   : tetrahedral (deployment, docs/resolve.md) RMSE {np.sqrt(np.mean((pl-pv)**2)):.4f} D  max {np.max(np.abs(pl-pv)):.4f} D; "
      f"trilinear RMSE {np.sqrt(np.mean((pl_tri-pv)**2)):.4f} D  max {np.max(np.abs(pl_tri-pv)):.4f} D (neither bounds the other)")

# ================= EXPORT =================
BUILDS.mkdir(exist_ok=True)
if _args.out_cube:
    CUBE = Path(_args.out_cube)
elif MONO:
    CUBE = BUILDS / "c41" / ("%s_StatusM.cube" % STOCK["file_prefix"])
else:
    # A per-apparatus build lands beside, never on top of, the canonical cube.
    CUBE = (BUILDS / ("sensor-%s" % sensor_stem(_args.sensor)) / "c41"
            / ("%s_StatusM.cube" % STOCK["file_prefix"]))
CUBE.parent.mkdir(parents=True, exist_ok=True)
with open(CUBE, "w") as f:
    f.write("# %s scanner-density -> Status M density (per-point)\n" % STOCK["display_name"])
    f.write("# INPUT  = scanner density / %.2f  (apply -log10(linear) then /%.2f before this LUT)\n" % (DMAX, DMAX))
    f.write("# OUTPUT = balanced Status M density / %.2f  (multiply by %.2f, then ADD the neutral offset "
            "below to recover image-dye Status M OD)\n" % (DMAX, DMAX))
    f.write("# neutral offset R/G/B = %.4f/%.4f/%.4f D (subtracted: the sheet's neutral series lies on "
            "the diagonal; the print engine adds it back)\n"
            % (NEUTRAL_OFFSET_D[0], NEUTRAL_OFFSET_D[1], NEUTRAL_OFFSET_D[2]))
    f.write("# sensor: %s\n" % SENSOR_LABEL)
    f.write("LUT_3D_SIZE %d\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n" % SZ)
    flat = np.clip(lut_out / DMAX, 0, 1).transpose(2, 1, 0, 3).reshape(-1, 3)  # cube: R fastest
    for v in flat: f.write("%.6f %.6f %.6f\n" % (v[0], v[1], v[2]))

# ---------- validate the serialized, clipped, six-decimal artifact ----------
def read_written_cube(path, size, dmax):
    vals = []
    for line in Path(path).read_text().splitlines():
        parts = line.split()
        if len(parts) == 3:
            try: vals.append([float(x) for x in parts])
            except ValueError: pass
    a = np.array(vals)
    if a.shape != (size ** 3, 3): raise ValueError(f"Unexpected cube payload in {path}: {a.shape}")
    return a.reshape(size, size, size, 3).transpose(2, 1, 0, 3) * dmax
wl = read_written_cube(CUBE, SZ, DMAX)
err = tetralerp(wl, sv) - pv
_err_tri = trilerp(wl, sv) - pv
# A sample whose balanced Status M is below 0 in some channel (image-dye density
# under the neutral offset there: the toe of that record) cannot be represented
# by a [0,1] cube and reads the floor; report it as its own share, not as
# interpolation error.
_floor = (pv < 0).any(1)
print(f"serialized {CUBE.name}: tetrahedral RMSE {np.sqrt(np.mean(err[~_floor]**2)):.4f}, max {np.max(np.abs(err[~_floor])):.4f} D; "
      f"trilinear RMSE {np.sqrt(np.mean(_err_tri[~_floor]**2)):.4f}, max {np.max(np.abs(_err_tri[~_floor])):.4f} D "
      f"over the {100*(1-_floor.mean()):.1f}% of samples above the output floor; the other {100*_floor.mean():.1f}% "
      f"sit below it in some channel (image-dye density under the neutral offset) and clip by up to {np.max(np.abs(err[_floor])) if _floor.any() else 0:.4f} D")
print("probe: dye 0-%.1f -> scan density max %.2f of the %.2f corridor (%.0f%%)  [working range]"
      % (PROBE_DYE_MAX, float(sv.max()), DMAX, 100.0 * float(sv.max()) / DMAX))

# Same serialization error over the FULL declared corridor: probe dye amounts up
# to whatever it takes to reach DMAX, rather than stopping at the working range.
_dye_full = dye_ceiling_for_density(DMAX)
_gv_full = np.random.default_rng(1).uniform(0, _dye_full, (5000, 3))
_sv_full = scan_fwd(_gv_full); _pv_full = statusm_fwd(_gv_full) - NEUTRAL_OFFSET_D[None, :]
_err_full = tetralerp(wl, _sv_full) - _pv_full
_floor_full = (_pv_full < 0).any(1)
print(f"serialized {CUBE.name}: tetrahedral RMSE {np.sqrt(np.mean(_err_full[~_floor_full]**2)):.4f}, "
      f"max {np.max(np.abs(_err_full[~_floor_full])):.4f} D over the {100*(1-_floor_full.mean()):.1f}% above the floor  [full corridor]")
print("probe: dye 0-%.2f -> scan density max %.2f of the %.2f corridor (%.0f%%)  [full corridor]"
      % (_dye_full, float(_sv_full.max()), DMAX, 100.0 * float(_sv_full.max()) / DMAX))

# ---------- neutral-axis check ----------
# For the digitized midscale exposure: predict Status M from the full chain
# (dye amounts that reproduce the midscale scan density) vs datasheet values.
mid = resample(swl, sp["midscale_neutral"], GRID); dmn = DMIN
agg = mid - dmn  # image-dye contribution of the midscale neutral (dmin removed)
# density of an arbitrary spectrum against a normalized responsivity set
def dens_spec(rn, spectrum):
    return -np.log10(np.clip(rn @ 10.0 ** (-spectrum), 1e-12, None))
# Status M of the full digitized midscale (with D-min) -- datasheet truth.
sm_datasheet = dens_spec(PRT_n, mid)
# D-min-excluded reference: Status M of the aggregate image-dye spectrum.
sm_agg = dens_spec(PRT_n, agg)
# Full chain, as the scanner and the roll anchor deliver it: the BARE LEDs read
# the full midscale spectrum and the base, and the anchor subtracts the two
# integrated densities. That input is then unmixed through the mask-filtered
# model the LUT uses -> Status M.
sd_mid = dens_spec(PHI_bare_n, mid) - dens_spec(PHI_bare_n, dmn)
dye_mid = sd_mid @ Winv
for _ in range(12):
    Dv, J = scan_jac(dye_mid[None, :]); step = np.linalg.solve(J[0], (Dv[0] - sd_mid))
    dye_mid = np.clip(dye_mid - step, -0.5, 6.0)
sm_chain = statusm_fwd(dye_mid[None, :])[0]
print("neutral-axis check @ digitized midscale exposure (bare-LED reading of the full "
      "midscale, base anchored out in integrated density, unmixed as the LUT does):")
print("  predicted Status M (full chain)      RGB %s" % np.round(sm_chain, 4).tolist())
print("  reference Status M (aggregate spec)  RGB %s" % np.round(sm_agg, 4).tolist())
print("  delta                                RGB %s" % np.round(sm_chain - sm_agg, 4).tolist())
print("  datasheet Status M (full midscale, incl. D-min) RGB %s" % np.round(sm_datasheet, 4).tolist())
# The cube's output is the Status M of the IMAGE DYES alone (spectral base
# subtracted); a sheet characteristic curve or a densitometer reads base and fog
# too. Subtracting the sheet's integrated D-min is NOT the same subtraction:
# print both, so the quality-control tap (docs/resolve.md) is compared to the
# right quantity. Full Status M of the chain's dyes on the base is the number a
# densitometer would read; the cube output plus integrated D-min is not.
sm_chain_full = dens_spec(PRT_n, dmn + dye_mid @ DYE)
sm_dmin_int = dens_spec(PRT_n, dmn)
print("  quality-control tap: cube output x %.2f plus the neutral offset is image-dye Status M %s; a "
      "densitometer or the sheet curve reads the full negative %s (chain dyes on the base); integrated "
      "D-min %s added to image-dye Status M gives %s, off by %s D from the full reading"
      % (DMAX, np.round(sm_chain, 4).tolist(), np.round(sm_chain_full, 4).tolist(),
         np.round(sm_dmin_int, 4).tolist(), np.round(sm_chain + sm_dmin_int, 4).tolist(),
         np.round(sm_chain + sm_dmin_int - sm_chain_full, 4).tolist()))
print("  datasheet gray-card red-density corridor 0.77-0.87 noted for reference "
      "(full-midscale red Status M = %.3f)" % sm_datasheet[0])
# --out-cube accepts an arbitrary path, which need not lie under ROOT;
# Path.relative_to raises ValueError in that case, so fall back to the absolute
# path. Output for the default in-repo destination is unchanged.
try:
    _shown = CUBE.relative_to(ROOT)
except ValueError:
    _shown = CUBE
print(f"wrote {_shown}")
