#!/usr/bin/env python3
"""C-41 scanner-density -> Status M density transform (65^3 .cube).

Stock-generic: parameterized by film stock via --stock (registry:
engine/c41/portra_stocks.py), one engine for every C-41 stock in the registry.
The default, portra400, reproduces that build exactly as it always has.

Renamed from portra400_statusm_engine.py (2026-07-27).  The old name predated
--stock and described the only stock it could then build; it had no importers,
only prose references.

Mirrors engine/cineon_pd_engine.py: same SPD/CFA loading idioms, the same
per-node Gauss-Newton inversion over a scan-density lattice, and the same
cube shaper/domain conventions. The only substantive differences are:

  * dyes come from <Stock>_dye_density.json (C-41, surrogate-basis fit);
  * the print/target space is ISO Status M (StatusM_ISO5-3.json) instead of
    RP180 printing density;
  * Status M red support runs to 770 nm but the dye data ends at 700 nm, so
    the red responsivity is truncated at 700 and renormalized (density is a
    Pi-weighted average, so renormalization is exact; the note is printed).

Like cineon_pd_engine, D-min is NOT baked into the LUT: the forward model uses
only the three image-dye amounts (dc,dm,dy); D-min is a per-roll anchor applied
upstream, exactly as the Cineon engine leaves it out (it never adds a base term
to the dye stack). This is stated on stdout.
"""
import argparse, json, re, sys
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"; BUILDS = ROOT / "builds"
GRID = np.arange(400, 701, 1.0)   # dye data ends at 700 nm

sys.path.insert(0, str(ROOT))
from engine.common.spectral import density, resample   # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))   # sibling module import
from portra_stocks import STOCKS as PORTRA_STOCKS, DEFAULT_STOCK   # noqa: E402

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
_args = _ap.parse_args()
STOCK = PORTRA_STOCKS[_args.stock]
if bool(_args.dye_json) != bool(_args.out_cube):
    raise SystemExit("--dye-json and --out-cube must be given together, so an "
                     "ensemble build can never overwrite a canonical cube.")


# ---------- Portra dyes ----------
_dye_path = Path(_args.dye_json) if _args.dye_json else DATA / "films" / STOCK["dye_density_json"]
dj = json.load(open(_dye_path)); fc = dj["shared_full_curves"]
wl_d = np.array(fc["wavelength_nm"], float)
C = resample(wl_d, fc["cyan"], GRID); M = resample(wl_d, fc["magenta"], GRID); Y = resample(wl_d, fc["yellow"], GRID)
DYE = np.stack([C, M, Y])

# ---------- scanner LED SPDs x camera CFA (as in cineon_pd_engine) ----------
raw = open(DATA / "equipment" / "film_scanner_SPD_combined.csv").read().strip().splitlines()
hdr = raw[0].split(","); data = np.array([[float(x) for x in r.split(",")] for r in raw[1:]])
def col(n): return data[:, hdr.index(n)]
wl_s = data[:, 0]
L_R = resample(wl_s, col("R100_G0_B0"), GRID); L_G = resample(wl_s, col("R0_G100_B0"), GRID); L_B = resample(wl_s, col("R0_G0_B100"), GRID)
ct = open(DATA / "equipment" / "a7r2_cfa.md").read()
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
red_full = np.array(smj["responsivity_linear_peak1"]["red"], float)
tail_pct = 100.0 * (1.0 - red_full[smw <= 700].sum() / red_full.sum())

PHI = np.stack([L_R * S_R, L_G * S_G, L_B * S_B]); PRT = np.stack([P_R, P_G, P_B])
PHI_n = PHI / PHI.sum(1, keepdims=True); PRT_n = PRT / PRT.sum(1, keepdims=True)


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
print("D-min handling: EXCLUDED from the LUT (forward model uses only dc,dm,dy; "
      "D-min is a per-roll anchor upstream), mirroring cineon_pd_engine.")
print("Status M red truncation: red support to 770 nm truncated at 700 nm "
      "(dye data limit) and renormalized; excluded 700-770 tail = %.2f%% of red area." % tail_pct)
print(f"node solve: residual mean {res.mean():.4f} max {res.max():.4f} D  (>{0.02:.2f} on {100*np.mean(res>0.02):.1f}% nodes, mostly out-of-gamut corners)")
lut = statusm_fwd(dye).reshape(SZ, SZ, SZ, 3)

# ---------- validate LUT (trilinear) vs direct solve ----------
rng = np.random.default_rng(1); gv = rng.uniform(0, 2.2, (5000, 3))
sv = scan_fwd(gv); pv = statusm_fwd(gv)
def trilerp(L, pts):
    x = np.clip(pts / DMAX, 0, 1) * (SZ - 1); i = np.floor(x).astype(int); f = x - i; i = np.minimum(i, SZ - 2)
    out = np.zeros((len(pts), 3))
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2])
                out += w[:, None] * L[i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz]
    return out
pl = trilerp(lut, sv)
print(f"LUT 65^3   : RMSE {np.sqrt(np.mean((pl-pv)**2)):.4f} D  max {np.max(np.abs(pl-pv)):.4f} D")

# ================= EXPORT =================
BUILDS.mkdir(exist_ok=True)
CUBE = (Path(_args.out_cube) if _args.out_cube
        else BUILDS / "c41" / ("%s_StatusM.cube" % STOCK["file_prefix"]))
CUBE.parent.mkdir(parents=True, exist_ok=True)
with open(CUBE, "w") as f:
    f.write("# %s scanner-density -> Status M density (per-point)\n" % STOCK["display_name"])
    f.write("# INPUT  = scanner density / %.2f  (apply -log10(linear) then /%.2f before this LUT)\n" % (DMAX, DMAX))
    f.write("# OUTPUT = Status M density / %.2f  (multiply by %.2f to recover OD)\n" % (DMAX, DMAX))
    f.write("LUT_3D_SIZE %d\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n" % SZ)
    flat = np.clip(lut / DMAX, 0, 1).transpose(2, 1, 0, 3).reshape(-1, 3)  # cube: R fastest
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
err = trilerp(wl, sv) - pv
print(f"serialized {CUBE.name}: RMSE {np.sqrt(np.mean(err**2)):.4f}, max {np.max(np.abs(err)):.4f} D")

# ---------- neutral-axis check ----------
# For the digitized midscale exposure: predict Status M from the full chain
# (dye amounts that reproduce the midscale scan density) vs datasheet values.
cd = json.load(open(DATA / "films" / STOCK["curves_json"]))
sp = cd["spectral"]; swl = np.array(sp["wavelength_nm"], float)
mid = resample(swl, sp["midscale_neutral"], GRID); dmn = resample(swl, sp["dmin"], GRID)
agg = mid - dmn  # image-dye contribution of the midscale neutral (dmin removed)
# density of an arbitrary spectrum against a normalized responsivity set
def dens_spec(rn, spectrum):
    return -np.log10(np.clip(rn @ 10.0 ** (-spectrum), 1e-12, None))
# Status M of the full digitized midscale (with D-min) -- datasheet truth.
sm_datasheet = dens_spec(PRT_n, mid)
# D-min-excluded reference: Status M of the aggregate image-dye spectrum.
sm_agg = dens_spec(PRT_n, agg)
# Full chain (D-min excluded): scan density of aggregate spectrum -> invert to
# dye amounts -> Status M via the same forward model the LUT uses.
sd_mid = dens_spec(PHI_n, agg)
dye_mid = sd_mid @ Winv
for _ in range(12):
    Dv, J = scan_jac(dye_mid[None, :]); step = np.linalg.solve(J[0], (Dv[0] - sd_mid))
    dye_mid = np.clip(dye_mid - step, -0.5, 6.0)
sm_chain = statusm_fwd(dye_mid[None, :])[0]
print("neutral-axis check @ digitized midscale exposure (D-min excluded, as in LUT):")
print("  predicted Status M (full chain)      RGB %s" % np.round(sm_chain, 4).tolist())
print("  reference Status M (aggregate spec)  RGB %s" % np.round(sm_agg, 4).tolist())
print("  delta                                RGB %s" % np.round(sm_chain - sm_agg, 4).tolist())
print("  datasheet Status M (full midscale, incl. D-min) RGB %s" % np.round(sm_datasheet, 4).tolist())
print("  datasheet gray-card red-density corridor 0.77-0.87 noted for reference "
      "(full-midscale red Status M = %.3f)" % sm_datasheet[0])
print(f"wrote {CUBE.relative_to(ROOT)}")
