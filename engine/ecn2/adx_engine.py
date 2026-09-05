#!/usr/bin/env python3
"""Vision3 scanner density -> ADX16 (SMPTE ST 2065-3) on Academy Printing Density.

The ECN-2 branch's primary route: one stock-blind ADX16 cube into ACES.
The scan-side model is the negative family's: the shared family dye basis,
the film digitiser's LED SPD, an optional camera SSF, a Gauss-Newton unmix
per lattice node. Two things distinguish the output side:

  * the printing-density responsivities are ST 2065-2 Table A.1 (APD), read
    from data/standards/APD_ST2065-2.json, with RP 180 read only for the
    comparison line;
  * the output is encoded per ST 2065-3 equation 1,
        ADX16 = clip(k * (APD - APD_Dmin) * 8000 + 1520, 0, 65535),
        k = (1.00, 0.92, 0.95) for (R, G, B),
    written as code value / 65535 so the Academy transform
    CSC.Academy.ADX16_to_ACES (DaVinci Resolve: input colour space
    "ADX (16-bit)") consumes it directly. The float cube is not rounded to an
    integer code; the standard's ROUND is a storage matter for integer files.

Dmin. The cube's input axis excludes D-min: the roll anchor divides the base
and orange mask out of the linear frame, which is a subtraction of INTEGRATED
densities, so the cube receives the image dyes as the LEDs see them THROUGH the
mask, and the scan-side responsivity is LED x sensor x 10^-Dmin(l) built from
the family-average Minimum Density curve in Vision3_dye_density.json (the
dashed curve of each stock's own chart, traced). The output is the standard's
own quantity: ST 2065-3 subtracts APD_Dmin, the measured D-min of the sample,
in integrated printing density, so (APD - APD_Dmin) is computed as
APD(mask + dye) - APD(mask), never as the APD of the dye stack alone. One
mask serves the family, as one dye set does; the per-stock curves' spread
about it is reported as the bound on that averaging.

Usage:
    python3 engine/ecn2/adx_engine.py [--sensor none|<camera>] [--out-cube P]
The default sensor writes builds/ecn2/; a named sensor writes
builds/sensor-<Body>/ecn2/ (unrecorded in the cube manifest by design).
"""
import argparse, json, re, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]; DATA = ROOT / "data"; BUILDS = ROOT / "builds"
sys.path.insert(0, str(ROOT))
from engine.common.spectral import density, resample

DMAX = 3.30; SZ = 65                     # corridor and lattice, as every ECN-2 cube
K_ADX = np.array([1.00, 0.92, 0.95])     # ST 2065-3 eq. 1 per-channel factors
ADX16_GAIN, ADX16_OFFSET, ADX16_MAX = 8000.0, 1520.0, 65535.0
ADX10_GAIN, ADX10_OFFSET, ADX10_MAX = 500.0, 95.0, 1023.0
CUBE_NAME = "Vision3 to ADX16.cube"

ap = argparse.ArgumentParser()
ap.add_argument("--sensor", default="none",
                help="camera SSF: 'none' for a unity (monochrome) response, or a bare name "
                     "from data/cameras/ or a path (default: none)")
ap.add_argument("--out-cube", default=None)
args = ap.parse_args()

def resolve_sensor(value):
    if value == "none": return None, "none (unity response; monochrome sensor)"
    cams = DATA / "cameras"
    if "/" in value or "\\" in value: p = Path(value)
    elif value.endswith(".json"):
        p = cams / value
        if not p.exists(): p = Path(value)
    else: p = cams / ("%s_ssf.json" % value)
    if not p.exists(): raise SystemExit("sensor file not found: %s" % p)
    return p, p.name
def sensor_stem(value):
    n = Path(value).name
    if n.endswith(".json"): n = n[:-5]
    if n.endswith("_ssf"): n = n[:-4]
    return n
SENSOR_PATH, SENSOR_LABEL = resolve_sensor(args.sensor); MONO = SENSOR_PATH is None

# ---- dye basis on its measured support (family policy: no synthesized tail) ----
fc = json.load(open(DATA / "films" / "Vision3_dye_density.json"))["shared_full_curves"]
wl_d = np.array(fc["wavelength_nm"], float)
CH = ("cyan", "magenta", "yellow")
vals = {k: np.array([np.nan if v is None else v for v in fc[k]], float) for k in CH}
meas = [wl_d[~np.isnan(vals[k])] for k in CH]
lo = max(400.0, min(m.min() for m in meas)); hi = min(730.0 + 70.0, max(m.max() for m in meas))
GRID = np.arange(np.ceil(lo), np.floor(hi) + 1, 1.0)
print("integration grid narrowed to measured dye support: %.0f-%.0f nm" % (GRID[0], GRID[-1]))
def dye_curve(k):
    ok = ~np.isnan(vals[k]); return resample(wl_d[ok], vals[k][ok], GRID)
DYE = np.stack([dye_curve(k) for k in CH])

# ---- the mask: family-average Minimum Density, absolute, on the same grid ----
_md = json.load(open(DATA / "films" / "Vision3_dye_density.json"))["minimum_density"]
_mw = np.array(_md["wavelength_nm"], float); _mv = np.array([np.nan if v is None else v for v in _md["density"]], float)
_mok = ~np.isnan(_mv)
if GRID[0] < _mw[_mok].min() or GRID[-1] > _mw[_mok].max():
    raise SystemExit("minimum density support %.0f-%.0f nm does not cover the dye grid %.0f-%.0f"
                     % (_mw[_mok].min(), _mw[_mok].max(), GRID[0], GRID[-1]))
DMIN = resample(_mw[_mok], _mv[_mok], GRID)
DMIN_SPREAD = _md["inter_stock_spread"]

# ---- scanner PHI: LED SPD x sensor SSF x 10^-Dmin (the LEDs behind the mask) ----
raw = open(DATA / "equipment" / "film_scanner_SPD_combined.csv").read().strip().splitlines()
hdr = raw[0].split(","); dat = np.array([[float(x) for x in r.split(",")] for r in raw[1:]])
col = lambda n: dat[:, hdr.index(n)]; wl_s = dat[:, 0]
L = [resample(wl_s, col(n), GRID) for n in ("R100_G0_B0", "R0_G100_B0", "R0_G0_B100")]
if MONO: S = [1.0, 1.0, 1.0]
else:
    ct = open(SENSOR_PATH).read()
    def arr(k):
        m = re.search(k + r'"?\s*:\s*\[([0-9eE.,\s\\-]*?)\]', ct)
        return np.array([float(x) for x in re.findall(r'-?\d+\.?\d*(?:[eE][-+]?\d+)?', m.group(1))], float)
    wl_c = arr("ssf_bands"); S = [resample(wl_c, arr(k), GRID) for k in ("red_ssf", "green_ssf", "blue_ssf")]
PHI_bare = np.stack([L[i] * S[i] for i in range(3)]); PHI_bare_n = PHI_bare / PHI_bare.sum(1, keepdims=True)
PHI = PHI_bare * 10.0 ** (-DMIN); PHI_n = PHI / PHI.sum(1, keepdims=True)
_cent = lambda P: (P * GRID).sum(1) / P.sum(1)
print("scan-side responsivity: LED x sensor x 10^-Dmin(l), family-average mask; D-min at 450/544/640 nm = %s, "
      "LED centroid shift vs bare R/G/B = %s nm; inter-stock mask spread median %.3f D, at the LED peaks %s"
      % (np.round(np.interp([450, 544, 640], GRID, DMIN), 3).tolist(),
         np.round(_cent(PHI_n) - _cent(PHI_bare_n), 2).tolist(), DMIN_SPREAD["median_D"], DMIN_SPREAD["at_led_peaks_D"]))

# ---- printing-density responsivities: APD (target) and RP 180 (for the delta line) ----
def load_resp(path, keys=("red", "green", "blue")):
    j = json.load(open(path)); w = np.array(j["wavelength_nm"], float)
    full = np.stack([np.array(j[k], float) for k in keys])
    on_grid = np.stack([resample(w, full[i], GRID) for i in range(3)])
    # share of each channel's integral lying outside the grid (truncated, then
    # renormalised), evaluated on a 1 nm resampling of the table's own range so
    # a 10 nm table (RP 180) and a 2 nm one (APD) are weighted alike
    w1 = np.arange(w[0], w[-1] + 1, 1.0)
    full1 = np.stack([np.interp(w1, w, full[i]) for i in range(3)])
    inside = (w1 >= GRID[0]) & (w1 <= GRID[-1])
    lost = 1.0 - full1[:, inside].sum(1) / full1.sum(1)
    return on_grid / on_grid.sum(1, keepdims=True), lost
APD_n, apd_lost = load_resp(DATA / "standards" / "APD_ST2065-2.json")
RP_n, rp_lost = load_resp(DATA / "standards" / "RP180_responsivities.json")
print("APD responsivity share outside the grid (truncated, renormalised): R %.3f%% G %.3f%% B %.3f%%"
      % tuple(100 * apd_lost))
print("RP 180 share outside the grid, for comparison:                  R %.3f%% G %.3f%% B %.3f%%"
      % tuple(100 * rp_lost))

scan_fwd = lambda d: density(PHI_n, d, DYE)


def dens_over_mask(W, d, mask=DMIN, dyes=DYE):
    """(APD - APD_Dmin) as ST 2065-3 defines it: the integrated density of the
    mask-plus-dye stack under W, less that of the mask alone."""
    d = np.atleast_2d(d)
    T = 10.0 ** (-(d @ dyes + mask))
    return -np.log10(np.clip(T @ W.T, 1e-12, None)) + np.log10(np.clip(10.0 ** (-mask) @ W.T, 1e-12, None))


apd_fwd = lambda d: dens_over_mask(APD_n, d)
rp_fwd = lambda d: dens_over_mask(RP_n, d)
def scan_jac(dye):
    dye = np.atleast_2d(dye); T = 10.0 ** (-(dye @ DYE)); integ = T @ PHI_n.T
    num = np.einsum('nl,il,jl->nij', T, PHI_n, DYE)
    return -np.log10(np.clip(integ, 1e-12, None)), num / integ[:, :, None]

def adx16_encode(apd): return np.clip(K_ADX * apd * ADX16_GAIN + ADX16_OFFSET, 0, ADX16_MAX) / ADX16_MAX
def adx16_decode(cv): return (cv * ADX16_MAX - ADX16_OFFSET) / ADX16_GAIN / K_ADX
def adx10_code(apd): return K_ADX * apd * ADX10_GAIN + ADX10_OFFSET   # unclipped, for the headroom line

# ---- linear seed, then per-node Gauss-Newton unmix over the lattice ----
n = 9; ax = np.linspace(0, 2, n)
g = np.array(np.meshgrid(ax, ax, ax, indexing="ij")).reshape(3, -1).T
W, *_ = np.linalg.lstsq(g, scan_fwd(g), rcond=None); Winv = np.linalg.inv(W)
axn = np.linspace(0, DMAX, SZ)
node = np.array(np.meshgrid(axn, axn, axn, indexing="ij")).reshape(3, -1).T
dye = node @ Winv
for _ in range(12):
    Dv, J = scan_jac(dye); r = Dv - node
    dye = np.clip(dye - np.linalg.solve(J, r[:, :, None])[:, :, 0], -0.5, 6.0)
res = np.max(np.abs(scan_fwd(dye) - node), 1)
print("node solve: residual mean %.4f max %.4f D  (>0.02 on %.1f%% nodes, mostly out-of-gamut corners)"
      % (res.mean(), res.max(), 100 * np.mean(res > 0.02)))
print("sensor: %s" % SENSOR_LABEL)

apd_lut = apd_fwd(dye)
lut = adx16_encode(apd_lut).reshape(SZ, SZ, SZ, 3)
codes = lut * ADX16_MAX
print("ADX16 code range over the lattice: min %.0f max %.0f of %d (no clipping: %s)"
      % (codes.min(), codes.max(), int(ADX16_MAX), "yes" if codes.max() < ADX16_MAX else "NO"))

# ---- validate the in-memory LUT (trilinear) against truth, in APD density ----
PROBE_DYE_MAX = 2.2
rng = np.random.default_rng(1); gv = rng.uniform(0, PROBE_DYE_MAX, (5000, 3))
sv = scan_fwd(gv); pv = apd_fwd(gv)
def trilerp(Lut, pts):
    x = np.clip(pts / DMAX, 0, 1) * (SZ - 1); i = np.floor(x).astype(int); f = x - i; i = np.minimum(i, SZ - 2)
    out = np.zeros((len(pts), 3))
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2])
                out += w[:, None] * Lut[i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz]
    return out
pl = adx16_decode(trilerp(lut, sv))
print("LUT 65^3   : RMSE %.4f D  max %.4f D  [APD, working range]" % (np.sqrt(np.mean((pl - pv) ** 2)), np.max(np.abs(pl - pv))))
c10 = adx10_code(pv)
print("ADX10 headroom: %.1f%% of working-range probes would clip at 1023 (k*APD > 1.856 D); max k*APD %.3f D"
      % (100 * np.mean((c10 > ADX10_MAX).any(1)), float((K_ADX * pv).max())))
d_rp = pv - rp_fwd(gv)
print("APD minus RP 180 on the same dye stacks: mean %s  max|.| %s D"
      % (np.round(d_rp.mean(0), 4).tolist(), np.round(np.abs(d_rp).max(0), 4).tolist()))

# ================= EXPORT =================
if args.out_cube: CUBE = Path(args.out_cube)
elif MONO: CUBE = BUILDS / "ecn2" / CUBE_NAME
else: CUBE = BUILDS / ("sensor-%s" % sensor_stem(args.sensor)) / "ecn2" / CUBE_NAME
CUBE.parent.mkdir(parents=True, exist_ok=True)
with open(CUBE, "w") as f:
    f.write("# Vision3 scanner density -> ADX16 (SMPTE ST 2065-3) on Academy Printing Density (ST 2065-2); basis = shared image-dye set, family average of 50D/200T/250D/500T\n")
    f.write("# INPUT  = scanner density / %.2f, D-MIN EXCLUDED (apply -log10(linear), subtract D-min, /%.2f before this LUT)\n" % (DMAX, DMAX))
    f.write("# OUTPUT = ADX16 code value / 65535, i.e. (k*(APD - APD_Dmin)*8000 + 1520)/65535 with k = (1.00, 0.92, 0.95); feed to CSC.Academy.ADX16_to_ACES (Resolve: input colour space 'ADX (16-bit)')\n")
    f.write("# scan side = LED x sensor x 10^-Dmin(l) (the anchor divides the mask out in integrated density); APD - APD_Dmin = APD(mask+dye) - APD(mask), the family-average traced Minimum Density curve as the mask\n")
    f.write("# sensor: %s\n" % SENSOR_LABEL)
    f.write("LUT_3D_SIZE %d\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n" % SZ)
    for v in np.clip(lut, 0, 1).transpose(2, 1, 0, 3).reshape(-1, 3):
        f.write("%.6f %.6f %.6f\n" % (v[0], v[1], v[2]))

# ---- validate the serialized, six-decimal artifact (not the in-memory LUT) ----
def read_written_cube(path):
    a = np.array([[float(x) for x in l.split()] for l in Path(path).read_text().splitlines()
                  if len(l.split()) == 3 and not l.startswith(("#", "D", "L"))])
    if a.shape != (SZ ** 3, 3): raise ValueError("unexpected cube payload %s" % (a.shape,))
    return a.reshape(SZ, SZ, SZ, 3).transpose(2, 1, 0, 3)
wl = read_written_cube(CUBE)
err = adx16_decode(trilerp(wl, sv)) - pv
print("serialized %s: RMSE %.4f, max %.4f D  [APD, working range]" % (CUBE.name, np.sqrt(np.mean(err ** 2)), np.max(np.abs(err))))
print("probe: dye 0-%.1f -> scan density max %.2f of the %.2f corridor (%.0f%%)  [working range]"
      % (PROBE_DYE_MAX, float(sv.max()), DMAX, 100 * float(sv.max()) / DMAX))

# ---- neutral-axis check and family-mask bound over the four traced stocks ----
# Each stock's own traced midscale (absolute, mask included) and its own
# traced Minimum Density are read with the BARE LEDs and anchored one against
# the other, exactly as the roll anchor does on a scan; that input is unmixed
# through the family model and encoded, and compared with the direct
# ST 2065-3 quantity APD(midscale) - APD(own mask). The family-mask bound is
# the same comparison over the working dye box with the stock's own mask on
# both sides of the film and the family mask inside the cube.
_dens = lambda rn, sp: -np.log10(np.clip((10.0 ** (-sp)) @ rn.T, 1e-12, None))
_rng = np.random.default_rng(2); _gb = _rng.uniform(0, PROBE_DYE_MAX, (3000, 3))
for s in ("50D", "200T", "250D", "500T"):
    sj = json.load(open(DATA / "films" / ("Vision3_%s_dye_density.json" % s)))
    m = sj["midscale_neutral"]; mwl = np.round(np.array(m["wavelength_nm"], float)); md = m["density"]
    ok = np.array([v is not None for v in md], bool)
    val = dict(zip(mwl[ok], [v for v in md if v is not None]))
    om = sj["minimum_density"]; ow = np.array(om["wavelength_nm"], float)
    ov = np.array([np.nan if v is None else v for v in om["density"]], float); ook = ~np.isnan(ov)
    mask = np.isin(GRID, mwl[ok]) & (GRID >= ow[ook].min()) & (GRID <= ow[ook].max())
    spec = np.array([val[w] for w in GRID[mask]], float)
    own = resample(ow[ook], ov[ook], GRID)
    phi_b = PHI_bare[:, mask] / PHI_bare[:, mask].sum(1, keepdims=True)
    phi_m = PHI[:, mask] / PHI[:, mask].sum(1, keepdims=True)
    apd_m = APD_n[:, mask] / APD_n[:, mask].sum(1, keepdims=True); dye_m = DYE[:, mask]
    direct = _dens(apd_m, spec[None, :])[0] - _dens(apd_m, own[mask][None, :])[0]
    sd = _dens(phi_b, spec[None, :])[0] - _dens(phi_b, own[mask][None, :])[0]
    d = sd @ Winv
    for _ in range(12):
        T = 10.0 ** (-(d[None, :] @ dye_m)); integ = T @ phi_m.T
        Jm = np.einsum('nl,il,jl->nij', T, phi_m, dye_m)[0] / integ[0][:, None]
        d = np.clip(d - np.linalg.solve(Jm, -np.log10(np.clip(integ[0], 1e-12, None)) - sd), -0.5, 6.0)
    chain = dens_over_mask(apd_m, d[None, :], mask=DMIN[mask], dyes=dye_m)[0]
    print("neutral-axis check (%s midscale, own mask, %d of %d grid wavelengths): chain APD %s direct APD %s delta %s"
          % (s, int(mask.sum()), len(GRID), np.round(chain, 4).tolist(), np.round(direct, 4).tolist(), np.round(chain - direct, 4).tolist()))
    # family-mask bound: a stock's own mask on the film, the family mask in the cube
    phi_own = PHI_bare * 10.0 ** (-own); phi_own_n = phi_own / phi_own.sum(1, keepdims=True)
    sv_own = density(phi_own_n, _gb, DYE)
    dh = _gb.copy()
    for _ in range(14):
        Dv, J = scan_jac(dh); dh = np.clip(dh - np.linalg.solve(J, (Dv - sv_own)[:, :, None])[:, :, 0], -0.5, 6.0)
    e = apd_fwd(dh) - dens_over_mask(APD_n, _gb, mask=own)
    print("family-mask bound (%s own mask vs family mask, dye 0-%.1f): APD error mean %s max %s D"
          % (s, PROBE_DYE_MAX, np.round(np.abs(e).mean(0), 4).tolist(), np.round(np.abs(e).max(0), 4).tolist()))
try: shown = CUBE.relative_to(ROOT)
except ValueError: shown = CUBE
print("wrote %s" % shown)
