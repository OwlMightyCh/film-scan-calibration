#!/usr/bin/env python3
"""Read-only validation battery for the C-41 -> RA-4 (Portra Endura) print engine.

This is a MEASUREMENT INSTRUMENT, not a fixer: it never writes to disk, never
mutates the shipped engine or its data, and never tunes a constant.  It imports
engine/c41/endura_print_engine.py directly (that module has a __main__ guard, so
importing it is side-effect free) and probes it from the outside.

Check groups:
  A  digitisation / data integrity (axis fits, toe, merged curves, terminal slopes)
  B  grid-coverage leaks caused by resample(left=0, right=0)
  C  gray-axis lock: is it correcting, or masking?
  D  solver health over the 33^3 analysis lattice
  E  colorimetric coherence (neutral axis, mid-gray, viewing illuminant, gamut)
  F  shipped .cube artifact fidelity

Run:  python3 engine/c41/endura_validate.py    (from repo root)
"""
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import colour

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
BUILDS = ROOT / "builds"

# ---- import ONLY the print engine, by file location (no package side effects) ----
_spec = importlib.util.spec_from_file_location(
    "endura_print_engine", ROOT / "engine" / "c41" / "endura_print_engine.py")
E = importlib.util.module_from_spec(_spec)
sys.modules["endura_print_engine"] = E
_spec.loader.exec_module(E)          # module has a __main__ guard -> nothing runs

sys.path.insert(0, str(ROOT))
from engine.common.spectral import (          # noqa: E402
    _m1 as _pq_m1, _m2 as _pq_m2, _c1 as _pq_c1, _c2 as _pq_c2, _c3 as _pq_c3)

LAYERS = E.LAYERS

# SZ is the ANALYSIS lattice for groups A-E: a sampling choice for probing the
# engine, independent of whatever size the engine happens to emit.  33 keeps
# these groups' numbers comparable with their historical values.
SZ = 33


def shipped_cube_size(path):
    """Read LUT_3D_SIZE out of a .cube header.

    Group F compares against the SHIPPED artifact, so it must use the shipped
    file's OWN lattice size, not the analysis size.  Deriving it here rather
    than hardcoding is deliberate: this check silently died once already, when
    the engine moved from 33^3 to 65^3 and this constant did not follow, so
    read_cube() raised 'Unexpected cube payload (274625, 3)' and group F never
    ran.  Reading the header means a future size change cannot repeat that.
    """
    with open(path) as fh:
        for line in fh:
            if line.startswith("LUT_3D_SIZE"):
                return int(line.split()[1])
    raise ValueError("no LUT_3D_SIZE in %s" % path)

# ids whose checks are numbers-only (no mechanical pass criterion given)
NO_VERDICT = []
FAILS = []


def note(cid):
    """Record a numbers-only check id (reported in the summary)."""
    NO_VERDICT.append(cid)


def verdict(cid, ok):
    """Return the ' [PASS]'/' [FAIL]' suffix and record failures."""
    if not ok:
        FAILS.append(cid)
    return " [PASS]" if ok else " [FAIL]"


def f(x, n=4):
    return ("%." + str(n) + "f") % float(x)


# =====================================================================
#  shared setup (built ONCE; the lattice evaluation is the expensive step)
# =====================================================================
eng = E.EnduraPrintEngine()
CG = eng.CGRID
paper_json = json.load(open(E.PAPER))
neg_dye_json = json.load(open(E.NEG_DYE))
neg_curves_json = json.load(open(E.NEG_CURVES))

# the 33^3 lattice, built EXACTLY as endura_print_engine.main() does
ax = np.linspace(0.0, 1.0, SZ)
NODE = np.array(np.meshgrid(ax, ax, ax, indexing="ij")).reshape(3, -1).T
LIN, XYZ_L, DP_L, A_L = eng.dnorm_to_linP3(NODE)

# D65 white for Lab conversions (display white)
_XYZ_D65 = colour.sd_to_XYZ(colour.SDS_ILLUMINANTS["D65"]) / 100.0
XY_D65 = colour.XYZ_to_xy(_XYZ_D65)


def to_lab_d65(xyz):
    return colour.XYZ_to_Lab(np.atleast_2d(xyz), XY_D65)


def dE2000(lab1, lab2):
    return colour.delta_E(lab1, lab2, method="CIE 2000")


def hd(i, le):
    return E.interp_lin(le, eng.hd_logE[i], eng.hd_dens[i])


def inv_hd(i, d):
    return E.interp_lin(d, eng.hd_dens[i], eng.hd_logE[i])


def chroma_metric(lin):
    """max|rgb - mean| / mean on linear P3, per row."""
    lin = np.atleast_2d(lin)
    m = np.maximum(np.abs(lin.mean(1)), 1e-9)
    return np.max(np.abs(lin - lin.mean(1)[:, None]), axis=1) / m


def neutral_lin(ks):
    ks = np.atleast_1d(np.asarray(ks, float))
    lin, _, _, _ = eng.dnorm_to_linP3(np.repeat(ks[:, None], 3, axis=1))
    return lin


def T_neg_of(ks):
    """Negative transmittance on CGRID for neutral inputs k*(1,1,1)."""
    ks = np.atleast_1d(np.asarray(ks, float))
    D_od = np.repeat(ks[:, None], 3, axis=1) * eng.cfg.dmax_input
    dye = eng.invert_statusm(D_od)
    N = eng.dmin_spec_C + dye @ eng.DYE_neg_C
    return 10.0 ** (-N), dye


print("=== Endura print-emulation validation battery (read-only) ===")

# =====================================================================
#  GROUP A: digitisation / data integrity
# =====================================================================
aud = paper_json["digitization_audit"]
bits = []
for chart in ("characteristic_curves", "spectral_sensitivity", "spectral_dye_density"):
    c = aud[chart]
    bits.append("%s x=%.5f y=%.5f" % (chart[:12], c["x_axis"]["fit_rms_data"],
                                      c["y_axis"]["fit_rms_data"]))
note("A1")
print("A1: paper axis-fit residuals (fit_rms_data): " + " | ".join(bits))

note("A2")
for i, l in enumerate(LAYERS):
    le, de = eng.hd_logE[i], eng.hd_dens[i]
    j = int(np.argmin(de))
    dmin = float(de[j])
    l0 = float(le[j])
    grad = (float(hd(i, l0 + 0.25)) - dmin) / 0.25
    print("A2: %-7s Dbase=%s @logE=%s first_sample=%s dD/dlogE(+0.25)=%s"
          % (l, f(dmin), f(l0, 3), j == 0, f(grad, 4)))

# A3: merged-curve test on the H&D characteristic curves
lo = max(eng.hd_logE[i][0] for i in range(3))
hi = min(eng.hd_logE[i][-1] for i in range(3))
gcom = np.linspace(lo, hi, 601)
Dc, Dm, Dy = (hd(0, gcom), hd(1, gcom), hd(2, gcom))
low = gcom <= lo + 0.5
note("A3")
print("A3: max|Dc-Dm| low0.5logE=%s full=%s ; control max|Dc-Dy| low0.5logE=%s full=%s"
      % (f(np.max(np.abs(Dc - Dm)[low]), 5), f(np.max(np.abs(Dc - Dm)), 5),
         f(np.max(np.abs(Dc - Dy)[low]), 5), f(np.max(np.abs(Dc - Dy)), 5)))

note("A4")
for i, l in enumerate(LAYERS):
    le, de = eng.hd_logE[i], eng.hd_dens[i]
    s_first = (de[2] - de[0]) / (le[2] - le[0])
    s_last = (de[-1] - de[-3]) / (le[-1] - le[-3])
    print("A4: %-7s first3 dD/dlogE=%s last3=%s logE domain=[%s, %s]"
          % (l, f(s_first, 4), f(s_last, 4), f(le[0], 3), f(le[-1], 3)))

# =====================================================================
#  GROUP B: grid-coverage leaks (resample uses left=0, right=0)
# =====================================================================
def gaps(wmin, wmax):
    """CGRID sub-intervals where the source provides no data (zero-filled)."""
    out = []
    if CG[0] < wmin:
        out.append("%g-%g" % (CG[0], wmin))
    if CG[-1] > wmax:
        out.append("%g-%g" % (wmax, CG[-1]))
    return ", ".join(out) if out else "none"


nd_wl = np.array(neg_dye_json["shared_full_curves"]["wavelength_nm"], float)
dmin_wl = np.array(neg_curves_json["spectral"]["wavelength_nm"], float)
note("B1")
print("B1: dmin_spec_C zero-fill %s ; DYE_neg_C zero-fill %s"
      % (gaps(dmin_wl.min(), dmin_wl.max()), gaps(nd_wl.min(), nd_wl.max())))
for i, l in enumerate(LAYERS):
    L = paper_json["layers"][l]
    sw = np.array(L["sensitivity"]["wavelength_nm"], float)
    dw = np.array(L["dye"]["wavelength_nm"], float)
    print("B1: SENS_P[%s] zero-fill %s ; DYE_P_C[%s] zero-fill %s"
          % (l, gaps(sw.min(), sw.max()), l, gaps(dw.min(), dw.max())))

# B2: fraction of the exposure integral coming from the negative-transparent bands
KS_B2 = np.array([0.05, 0.22, 0.55])
Tn, _ = T_neg_of(KS_B2)
W = eng.SENS_P * eng.L_enl                      # (3, Nc) exposure weights
lo_band = CG < 400.0
hi_band = CG > 700.0
note("B2")
for i, l in enumerate(LAYERS):
    contrib = Tn * W[i][None, :]                # (nk, Nc)
    tot = contrib.sum(1)
    flo = contrib[:, lo_band].sum(1) / tot
    fhi = contrib[:, hi_band].sum(1) / tot
    print("B2: %-7s 380-400nm frac %s ; 700-730nm frac %s   (k=0.05/0.22/0.55)"
          % (l, "/".join(f(x, 4) for x in flo), "/".join(f(x, 4) for x in fhi)))

# B3: flat-held (instead of zero-filled) negative outside 400-700
DYE_neg_held = np.stack([np.interp(CG, nd_wl,
                                   np.array(neg_dye_json["shared_full_curves"][l], float))
                         for l in LAYERS])
dmin_held = np.interp(CG, dmin_wl, np.array(neg_curves_json["spectral"]["dmin"], float))


def logE_raw_held(ks):
    ks = np.atleast_1d(np.asarray(ks, float))
    D_od = np.repeat(ks[:, None], 3, axis=1) * eng.cfg.dmax_input
    dye = eng.invert_statusm(D_od)
    N = dmin_held + dye @ DYE_neg_held
    Eh = (10.0 ** (-N)) @ W.T
    return np.log10(np.clip(Eh, 1e-30, None))


KS_B3 = np.array([0.05, 0.55])
raw_ship = eng.paper_logE_raw(np.repeat(KS_B3[:, None], 3, axis=1))
raw_held = logE_raw_held(KS_B3)
d_raw = raw_held - raw_ship
d_slope = ((raw_held[1] - raw_held[0]) - (raw_ship[1] - raw_ship[0])) / (KS_B3[1] - KS_B3[0])
note("B3")
for i, l in enumerate(LAYERS):
    print("B3: %-7s dlogE@k=0.05 %s  @k=0.55 %s  d(dlogE/dk) %s"
          % (l, f(d_raw[0, i], 4), f(d_raw[1, i], 4), f(d_slope[i], 4)))

# B4: rendering leak -- paper dyes zero-filled vs flat-held outside 400-700
DYE_P_held = np.stack([np.interp(CG, np.array(paper_json["layers"][l]["dye"]["wavelength_nm"], float),
                                 np.array(paper_json["layers"][l]["dye"]["density"], float))
                       for l in LAYERS])


def xyz_with_dyes(a, dyes):
    R = 10.0 ** (-(eng.base_spec_C + a @ dyes))
    return eng.adapt_to_display(eng.medium_to_XYZ(R))


mid = np.full((1, 3), 0.22)
_, _, a_mid = eng.dnorm_to_reflectance(mid)
de_mid = float(dE2000(to_lab_d65(xyz_with_dyes(a_mid, eng.DYE_P_C)),
                      to_lab_d65(xyz_with_dyes(a_mid, DYE_P_held)))[0])
de_lat = dE2000(to_lab_d65(XYZ_L), to_lab_d65(xyz_with_dyes(A_L, DYE_P_held)))
jw = int(np.argmax(de_lat))
note("B4")
print("B4: dE2000(zero-fill vs flat-held paper dyes) mid-gray %s ; worst node %s @Dnorm=%s"
      % (f(de_mid, 4), f(np.max(de_lat), 4), np.round(NODE[jw], 4).tolist()))

# B5: per-layer raw exposure contrast under four edge treatments
def slope_raw(dyes_neg, dmin_vec, weights):
    ks = np.array([0.05, 0.55])
    D_od = np.repeat(ks[:, None], 3, axis=1) * eng.cfg.dmax_input
    dye = eng.invert_statusm(D_od)
    Eh = (10.0 ** (-(dmin_vec + dye @ dyes_neg))) @ weights.T
    lg = np.log10(np.clip(Eh, 1e-30, None))
    return (lg[1] - lg[0]) / (ks[1] - ks[0])


W_trunc = W.copy()
W_trunc[:, lo_band] = 0.0
W_trunc[:, hi_band] = 0.0
treat = [("A zero-fill", eng.DYE_neg_C, eng.dmin_spec_C, W),
         ("B held-neg ", DYE_neg_held, dmin_held, W),
         ("C trunc-int", eng.DYE_neg_C, eng.dmin_spec_C, W_trunc),
         ("D held+trnc", DYE_neg_held, dmin_held, W_trunc)]
note("B5")
for name, dn, dm, wt in treat:
    s = slope_raw(dn, dm, wt)
    print("B5: %s dlogE/dk [C,M,Y] = %s  spread max-min %s"
          % (name, [f(x, 4) for x in s], f(s.max() - s.min(), 4)))

# =====================================================================
#  GROUP C: gray-axis lock
# =====================================================================
KK = np.linspace(eng.cfg.k_lo, eng.cfg.k_hi, eng.cfg.n_cal)
LEraw_cal = eng.paper_logE_raw(np.repeat(KK[:, None], 3, axis=1))
LEreq_cal = np.stack([E.interp_lin(LEraw_cal[:, i], eng.LEraw_s[i], eng.LEreq_s[i])
                      for i in range(3)], axis=1)
work = np.abs(LEreq_cal - LEraw_cal)

KS_C = np.arange(0.05, 0.601, 0.005)
# "before the lock": balancing offsets o applied, LEraw->LEreq map replaced by identity
raw_c = eng.paper_logE_raw(np.repeat(KS_C[:, None], 3, axis=1)) + eng.o[None, :]
DP_before = np.stack([hd(i, raw_c[:, i]) for i in range(3)], axis=1)
a_before = eng.invert_statusA(np.clip(DP_before - eng.Dbase, 0.0, None))
lin_before = xyz_with_dyes(a_before, eng.DYE_P_C) @ eng.XYZ_to_P3.T
lin_after = neutral_lin(KS_C)
note("C1")
for i, l in enumerate(LAYERS):
    print("C1: %-7s |LEreq-LEraw| max %s rms %s"
          % (l, f(work[:, i].max(), 4), f(np.sqrt(np.mean(work[:, i] ** 2)), 4)))
print("C1: neutral chroma (max over k in [0.05,0.60]) before lock %s -> after lock %s"
      % (f(np.max(chroma_metric(lin_before)), 5), f(np.max(chroma_metric(lin_after)), 5)))

# C2: does equal Status A density render achromatic for these dyes?
d_sweep = np.linspace(float(eng.Dbase.max()) + 0.05, 2.4, 24)
Dtri = np.repeat(d_sweep[:, None], 3, axis=1)
a_c2 = eng.invert_statusA(np.clip(Dtri - eng.Dbase, 0.0, None))
R_c2 = 10.0 ** (-(eng.base_spec_C + a_c2 @ eng.DYE_P_C))
XYZ_c2 = eng.medium_to_XYZ(R_c2)
XYZ_w = eng.medium_to_XYZ(np.ones((1, CG.size)))[0]
xy_view = colour.XYZ_to_xy(XYZ_w)
Lab_c2 = colour.XYZ_to_Lab(XYZ_c2, xy_view)
C_c2 = np.hypot(Lab_c2[:, 1], Lab_c2[:, 2])
note("C2")
for dq in (0.30, 0.74, 1.20, 1.80, 2.30):
    dq_c = float(np.clip(dq, d_sweep[0], d_sweep[-1]))
    ai = eng.invert_statusA(np.clip(np.full((1, 3), dq_c) - eng.Dbase, 0.0, None))
    Xi = eng.medium_to_XYZ(10.0 ** (-(eng.base_spec_C + ai @ eng.DYE_P_C)))
    Li = colour.XYZ_to_Lab(Xi, xy_view)[0]
    print("C2: d=%s a*=%s b*=%s chroma=%s"
          % (f(dq, 2), f(Li[1], 3), f(Li[2], 3), f(np.hypot(Li[1], Li[2]), 3)))
print("C2: max chroma over sweep [%s, %s] = %s"
      % (f(d_sweep[0], 3), f(d_sweep[-1], 3), f(C_c2.max(), 3)))

# C3: extrapolation outside the calibrated span
ks_c3 = np.array([0.0, 0.01, 0.70, 0.80, 0.90, 1.00])
ch_c3 = chroma_metric(neutral_lin(ks_c3))
note("C3")
print("C3: neutral chroma @k=" + " ".join("%.2f:%s" % (k, f(c, 4))
                                          for k, c in zip(ks_c3, ch_c3)))

# C4: monotonicity + finiteness of the stored calibration
worst = 0.0
mono_ok = True
finite_ok = True
for i in range(3):
    for arr in (eng.LEraw_s[i], eng.LEreq_s[i], eng.hd_logE[i], eng.hd_dens[i]):
        finite_ok &= bool(np.all(np.isfinite(arr)))
    for arr in (eng.LEraw_s[i], eng.LEreq_s[i]):
        d = np.diff(arr)
        if d.size and d.min() < -1e-12:
            mono_ok = False
            worst = min(worst, float(d.min()))
print("C4: LEraw_s/LEreq_s non-decreasing(no fold)=%s finite(all arrays)=%s worst step %s%s"
      % (mono_ok, finite_ok, f(worst, 3) if worst < 0 else "n/a",
         verdict("C4", mono_ok and finite_ok)))

# =====================================================================
#  GROUP D: solver health over the emitted lattice
# =====================================================================
D_od_L = NODE * eng.cfg.dmax_input
dye_neg_L = eng.invert_statusm(D_od_L)
res_m = np.abs(eng.statusm_fwd(dye_neg_L) - D_od_L)
clip_m = np.any((dye_neg_L <= 0.0) | (dye_neg_L >= 8.0), axis=1)
p95_m = float(np.percentile(res_m, 95))
print("D1: Status M residual median %.3e p95 %.3e max %.3e ; clipped nodes %d (%.2f%%)%s"
      % (np.median(res_m), p95_m, res_m.max(), int(clip_m.sum()),
         100.0 * clip_m.mean(), verdict("D1", float(np.max(res_m[~clip_m])) < 1e-9 if (~clip_m).any() else True)))

res_a = np.abs(eng.statusA_fwd(A_L) + eng.Dbase - DP_L)
clip_a = np.any((A_L <= 0.0) | (A_L >= 8.0), axis=1)
zero_a = np.any(A_L <= 0.0, axis=1)
clamp_a = np.any(DP_L < eng.Dbase, axis=1)
p95_a = float(np.percentile(res_a, 95))
print("D2: Status A residual median %.3e p95 %.3e max %.3e ; a-clipped %d (%.2f%%) ; "
      "Dbase-clamp active %d (%.2f%%)%s"
      % (np.median(res_a), p95_a, res_a.max(), int(clip_a.sum()), 100.0 * clip_a.mean(),
         int(clamp_a.sum()), 100.0 * clamp_a.mean(), verdict("D2", float(np.max(res_a[~clip_a])) < 1e-9 if (~clip_a).any() else True)))
mass = res_a.sum(1)
r0, r1 = res_a[zero_a], res_a[~zero_a]
print("D2: split a==0 nodes (%d) median %.3e p95 %.3e max %.3e | a>0 nodes (%d) median %.3e "
      "p95 %.3e max %.3e | %% residual mass on a==0 nodes %.2f%%"
      % (int(zero_a.sum()),
         np.median(r0) if r0.size else 0.0, np.percentile(r0, 95) if r0.size else 0.0,
         r0.max() if r0.size else 0.0, int((~zero_a).sum()),
         np.median(r1) if r1.size else 0.0, np.percentile(r1, 95) if r1.size else 0.0,
         r1.max() if r1.size else 0.0,
         100.0 * mass[zero_a].sum() / max(mass.sum(), 1e-300)))

note("D3")
print("D3: cond(S) = %s ; cond(SA) = %s"
      % (f(np.linalg.cond(eng.S), 4), f(np.linalg.cond(eng.SA), 4)))

# =====================================================================
#  GROUP E: colorimetric coherence
# =====================================================================
ks_e1 = np.arange(0.05, 0.601, 0.05)
lin_e1 = neutral_lin(ks_e1)
dev = np.max(np.abs(lin_e1 - lin_e1.mean(1)[:, None]), axis=1)
je = int(np.argmax(dev))
print("E1: max|linP3-mean| over k in [0.05,0.60] = %.3e at k=%s%s"
      % (dev[je], f(ks_e1[je], 2), verdict("E1", dev.max() < 5e-3)))

lin_mid, XYZ_mid, DP_mid, _ = eng.dnorm_to_linP3(np.full((1, 3), eng.cfg.k_mid))
Lmid = colour.XYZ_to_Lab(XYZ_mid, XY_D65)[0, 0]
kfine = np.linspace(0.02, 0.60, 400)
lf, _, _, _ = eng.dnorm_to_linP3(np.repeat(kfine[:, None], 3, axis=1))
k18 = float(kfine[int(np.argmin(np.abs(np.clip(lf, 0.0, 1.0).mean(1) - 0.18)))])
note("E2")
print("E2: @K_MID=%s Status A D_P=%s Y=%s L*=%s ; k with linP3 mean=0.18 -> %s "
      "(D_MID=%s target Y)"
      % (f(eng.cfg.k_mid, 2), [f(x, 4) for x in DP_mid[0]], f(XYZ_mid[0, 1], 5),
         f(Lmid, 3), f(k18, 4), f(eng.cfg.d_mid, 2)))

# E3: viewing-illuminant coherence (D50 render, with and without CAT to D65)
dj = json.load(open(DATA / "standards" / "D50_illuminant.json"))
D50_C = np.interp(CG, np.array(dj["wavelength_nm"], float), np.array(dj["spd"], float))
Lab_ship = to_lab_d65(XYZ_L)
C_ship = np.hypot(Lab_ship[:, 1], Lab_ship[:, 2])
sat_mask = C_ship >= np.percentile(C_ship, 95)
diag = np.zeros(SZ ** 3, bool)
diag[[i * SZ * SZ + i * SZ + i for i in range(SZ)]] = True
note("E3")
for tag, adapt in (("(a) D50+CAT02", True), ("(b) D50 no-CAT", False)):
    e2 = E.PrintEmulationEngine(E.PrintConfig(view_illuminant_spd=D50_C,
                                              adapt_view_white_to_d65=adapt))
    lin2, XYZ2, _, _ = e2.dnorm_to_linP3(NODE)
    de = dE2000(Lab_ship, to_lab_d65(XYZ2))
    print("E3: %s dE2000 vs shipped: median %s p95 %s max %s"
          % (tag, f(np.median(de), 4), f(np.percentile(de, 95), 4), f(de.max(), 4)))
    if adapt:
        print("E3: (a) dE2000 median on neutral diagonal %s ; on top-5%% saturated %s"
              % (f(np.median(de[diag]), 4), f(np.median(de[sat_mask]), 4)))

out_p3 = np.any((LIN < 0.0) | (LIN > 1.0), axis=1)
M_srgb = np.array(colour.RGB_COLOURSPACES["sRGB"].matrix_XYZ_to_RGB)
lin_srgb = XYZ_L @ M_srgb.T
out_srgb = np.any((lin_srgb < 0.0) | (lin_srgb > 1.0), axis=1)
note("E4")
print("E4: outside Display-P3 [0,1] %s%% (worst negative %s) ; outside sRGB [0,1] %s%%"
      % (f(100.0 * out_p3.mean(), 3), f(LIN.min(), 5), f(100.0 * out_srgb.mean(), 3)))

# =====================================================================
#  GROUP F: shipped artifact fidelity
# =====================================================================
CUBE_P3 = BUILDS / "c41" / "print_endura" / "Portra400_to_PortraEndura_DisplayP3.cube"
CUBE_PQ = BUILDS / "c41" / "print_endura" / "Portra400_to_PortraEndura_P3D65_PQ203.cube"
SHIP_SZ = shipped_cube_size(CUBE_P3)
if SHIP_SZ != shipped_cube_size(CUBE_PQ):
    raise ValueError("the two shipped cubes disagree on LUT_3D_SIZE")
print("F0: shipped lattice %d^3 (analysis lattice is %d^3)" % (SHIP_SZ, SZ))

# Rebuild the comparison lattice at the SHIPPED size -- LIN above is on the
# 33^3 analysis lattice and cannot be compared against a 65^3 artifact.
_axs = np.linspace(0.0, 1.0, SHIP_SZ)
NODE_SHIP = np.array(np.meshgrid(_axs, _axs, _axs, indexing="ij")).reshape(3, -1).T
LIN_SHIP, _, _, _ = eng.dnorm_to_linP3(NODE_SHIP)

lut_p3 = colour.cctf_encoding(np.clip(LIN_SHIP, 0.0, 1.0),
                              function="sRGB").reshape(SHIP_SZ, SHIP_SZ, SHIP_SZ, 3)
lut_pq = E.pq_encode(np.clip(LIN_SHIP, 0.0, None)
                     * eng.cfg.dw_nits).reshape(SHIP_SZ, SHIP_SZ, SHIP_SZ, 3)
ship_p3 = E.read_cube(CUBE_P3, SHIP_SZ)
ship_pq = E.read_cube(CUBE_PQ, SHIP_SZ)
f1_ok = True
for name, mine, ship in (("DisplayP3", lut_p3, ship_p3), ("P3D65_PQ203", lut_pq, ship_pq)):
    d = np.abs(ship - mine)
    ok = float(d.max()) < 1e-6
    f1_ok &= ok
    print("F1: %-11s RMSE %.3e max %.3e%s"
          % (name, np.sqrt(np.mean((ship - mine) ** 2)), d.max(),
             " [PASS]" if ok else " [FAIL]"))
if not f1_ok:
    FAILS.append("F1")

f2_bad = 0
for name, ship in (("DisplayP3", ship_p3), ("P3D65_PQ203", ship_pq)):
    diagv = np.stack([ship[i, i, i] for i in range(SHIP_SZ)])  # (SHIP_SZ,3)
    dd = np.diff(diagv, axis=0)
    bad = int(np.sum(dd < -1e-12))          # a DECREASE folds the LUT
    flat = int(np.sum(np.abs(dd) <= 1e-12))  # a PLATEAU is legitimate clipping
    f2_bad += bad
    print("F2: %-11s diagonal decreases %d ; flat (clipped) steps %d ; min step %.3e"
          % (name, bad, flat, dd.min()))
print("F2: total violations %d%s" % (f2_bad, verdict("F2", f2_bad == 0)))


def pq_decode(x):
    """ST 2084 EOTF: normalized code 0..1 -> absolute cd/m^2.

    The PQ constants live in engine/common/spectral.py, which is where
    pq_encode() was consolidated; endura_print_engine only re-exports the
    function, not the private constants.  This block used to read E._m2 etc.
    and would have raised AttributeError -- it was simply never reached,
    because group F died earlier on the lattice-size mismatch above.
    """
    x = np.clip(np.asarray(x, float), 0.0, 1.0) ** (1.0 / _pq_m2)
    num = np.clip(x - _pq_c1, 0.0, None)
    return 10000.0 * (num / (_pq_c2 - _pq_c3 * x)) ** (1.0 / _pq_m1)


lin_from_pq = pq_decode(ship_pq) / eng.cfg.dw_nits
lin_from_sdr = colour.cctf_decoding(ship_p3, function="sRGB")
inside = np.all((ship_p3 > 0.0) & (ship_p3 < 1.0), axis=-1)
dmax_f3 = float(np.max(np.abs(lin_from_pq - lin_from_sdr)[inside])) if inside.any() else 0.0
print("F3: max|PQ-decoded - SDR-decoded| over %d unclipped nodes = %.3e%s"
      % (int(inside.sum()), dmax_f3, verdict("F3", dmax_f3 < 1e-5)))

# =====================================================================
print("=== SUMMARY ===")
print("FAILED: %s" % (", ".join(FAILS) if FAILS else "none"))
print("numbers-only (no verdict): %s" % ", ".join(NO_VERDICT))
