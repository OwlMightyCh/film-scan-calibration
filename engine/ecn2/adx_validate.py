#!/usr/bin/env python3
"""Acceptance test for the ADX route: the Academy's stock-blind unbuild against
the per-stock scene route, both fed the same synthetic negatives.

For each Vision3 stock the scene engine's forward model turns the reference
reflectance sets (ColorChecker 24 and the broad sets) into D-min-excluded
scanner density for the chosen sensor. That density goes two ways:

  A  per-stock scene route: scan_norm_to_L -> fitted 3x3 -> XYZ(D65)
     (what 'Vision3 <stock> to Scene DWG.cube' encodes, before the DWG matrix);
  B  ADX route: 'Vision3 to ADX16.cube' (trilinear) -> CSC.Academy.ADX16_to_ACES
     (numpy port below, constants verbatim from the Academy CTL, a2.v1) ->
     ACES2065-1 -> XYZ(D65), Bradford.

Both are scored as dE2000 against the colorimetric XYZ(D65) of the same
reflectances under the stock's scene illuminant. Route B is scored three ways:
raw; after one scalar exposure trim placing the 18% grey at Y = 0.18 (the
Academy unbuild anchors a REFERENCE negative's grey at 0.70 D, not this
stock's); after per-channel APD TRIMS added to the encoded code values
before the decode, exactly the operation 'Printer Lights ADX16.dctl'
performs (CV + trim * k * 8000/65535, k = 1.00/0.92/0.95), solved so the
decoded 18% grey lands at AP0 0.18 each; and, as a separately named
comparison only, after per-channel GAINS on the decoded AP0. The two are
different operations through the decode's matrices and curve, so only the
trim column speaks for the delivered printer-light chain. The grey ramp lines
report where the unbuild's reference-film tone curve puts our stocks' neutral
exposures.
"""
import argparse, sys
from pathlib import Path
import numpy as np
import colour
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[2]; BUILDS = ROOT / "builds"
sys.path.insert(0, str(ROOT))
from engine.ecn2 import v3_scene_engine as v3

# ---- CSC.Academy.ADX16_to_ACES, ported (CTL mult_f3_f33 is row-vector @ matrix) ----
CDD_TO_CID = np.array([[0.75573, 0.05901, 0.16134],
                       [0.22197, 0.96928, 0.07406],
                       [0.02230, -0.02829, 0.76460]])
EXP_TO_ACES = np.array([[0.72286, 0.11923, 0.01427],
                        [0.12630, 0.76418, 0.08213],
                        [0.15084, 0.11659, 0.90359]])
LUT_1D = np.array([[-0.190, -6.000000000000000], [0.010, -2.721718645], [0.028, -2.521718645],
                   [0.054, -2.321718645], [0.095, -2.121718645], [0.145, -1.921718645],
                   [0.220, -1.721718645], [0.300, -1.521718645], [0.400, -1.321718645],
                   [0.500, -1.121718645], [0.600, -0.926545676714876]])
REF_PT = (7120.0 - 1520.0) / 8000.0 * (100.0 / 55.0) - np.log10(0.18)
def adx16_to_aces(cv):
    cdd = (np.asarray(cv, float) * 65535.0 - 1520.0) / 8000.0
    cid = cdd @ CDD_TO_CID
    logE = np.where(cid <= 0.6, np.interp(cid, LUT_1D[:, 0], LUT_1D[:, 1]), (100.0 / 55.0) * cid - REF_PT)
    return (10.0 ** logE) @ EXP_TO_ACES
# 'Printer Lights ADX16.dctl': APD trims land on the normalised code values as
# trim * k * 8000/65535 per channel, BEFORE the Academy decode.
K_ST2065_3 = np.array([1.00, 0.92, 0.95]); D_TO_CV = 8000.0 / 65535.0
def apply_apd_trims(cv, trims):
    return np.asarray(cv, float) + trims * K_ST2065_3 * D_TO_CV
def solve_apd_trims(cv_grey):
    """Per-channel APD trims placing the decoded grey at AP0 0.18 each."""
    r = least_squares(lambda t: adx16_to_aces(apply_apd_trims(cv_grey, t))[0] - 0.18, np.zeros(3), xtol=1e-14, ftol=1e-14)
    assert r.success and np.max(np.abs(r.fun)) < 1e-9, (r.status, r.fun)
    return r.x
D65 = colour.CCS_ILLUMINANTS["CIE 1931 2 Degree Standard Observer"]["D65"]
def aces_to_xyz_d65(ap0):
    return colour.RGB_to_XYZ(ap0, "ACES2065-1", illuminant=D65, chromatic_adaptation_transform="Bradford")

def read_cube(path):
    rows = [l.split() for l in Path(path).read_text().splitlines()]
    vals = np.array([[float(x) for x in r] for r in rows if len(r) == 3 and r[0][0] not in "#DL"])
    sz = round(len(vals) ** (1 / 3))
    assert sz ** 3 == len(vals), len(vals)
    return vals.reshape(sz, sz, sz, 3).transpose(2, 1, 0, 3), sz
def trilerp(Lut, sz, u):
    x = np.clip(u, 0, 1) * (sz - 1); i = np.minimum(np.floor(x).astype(int), sz - 2); f = x - i  # clamp the cell BEFORE the fraction: at u = 1 the last cell's fraction is 1, not 0
    out = np.zeros((len(u), 3))
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2])
                out += w[:, None] * Lut[i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz]
    return out

ap = argparse.ArgumentParser()
ap.add_argument("--sensor", default=v3.DEFAULT_SENSOR)
ap.add_argument("--cube", default=None, help="ADX16 cube (default: the build for --sensor)")
args = ap.parse_args()
sensor_path, sensor_label = v3.resolve_sensor(args.sensor)
cube_path = Path(args.cube) if args.cube else (
    BUILDS / "ecn2" / "Vision3 to ADX16.cube" if sensor_path is None
    else BUILDS / ("sensor-%s" % v3.sensor_stem(args.sensor)) / "ecn2" / "Vision3 to ADX16.cube")
LUT, SZ = read_cube(cube_path)
print("ADX16 cube: %s (%d^3)   sensor: %s" % (cube_path.relative_to(ROOT), SZ, sensor_label))
print("Academy unbuild anchor: CID 0.70 D -> 18%% grey (REF_PT %.4f)" % REF_PT)
_chk = adx16_to_aces(np.array([[(0.70 * 8000.0 + 1520.0) / 65535.0] * 3]))[0]
print("unbuild port self-check: neutral CDD 0.70 D -> AP0 %s (expected 0.18 each)" % np.round(_chk, 5).tolist())
assert np.allclose(_chk, 0.18, atol=2e-4), _chk

for stock in sorted(v3.STOCKS):
    eng = v3.V3SceneEngine(stock, sensor_path, sensor_label)
    route_B_xyz = lambda Dn: aces_to_xyz_d65(adx16_to_aces(trilerp(LUT, SZ, Dn)))
    # grey placement and trims from a flat 18% grey (L = 1,1,1)
    Dn_g = eng.L_to_scan_norm(np.ones((1, 3)))
    cv_g = trilerp(LUT, SZ, Dn_g)
    ap0_g = adx16_to_aces(cv_g)[0]
    Yg = float(aces_to_xyz_d65(ap0_g)[1])
    s_exp = 0.18 / Yg                              # scalar exposure trim
    trims = solve_apd_trims(cv_g)                  # the DCTL's pre-decode APD trims (the delivered chain)
    s_rgb = 0.18 / ap0_g                           # per-channel gains on decoded AP0 (comparison only)
    print("=== %s (illuminant %s) ===" % (stock, eng.p["scene_illuminant"]))
    print("18%% grey via ADX: AP0 %s  Y %.4f  (%+.2f stops from 0.18; AP0 channel spread %.1f%%)"
          % (np.round(ap0_g, 4).tolist(), Yg, np.log2(Yg / 0.18), 100 * (ap0_g.max() / ap0_g.min() - 1)))
    print("  printer-light APD trims placing the decoded grey at 0.18 (R,G,B, D; diagnostic, not a preset): %s"
          % np.round(trims, 4).tolist())
    sets = [("ColorChecker24", eng.cc_L, eng.cc_X)] + [(nm, La, Xa) for nm, (La, Xa) in eng.broad_sets.items()]
    print("  %-20s %6s | %-13s | %-13s | %-13s | %-13s | %-13s" % ("set", "n", "A scene route", "B ADX raw", "B +exposure", "B +APD trims", "B +AP0 gains"))
    for nm, La, Xa in sets:
        Dn = eng.L_to_scan_norm(La)
        XA = (eng.M @ eng.scan_norm_to_L(Dn).T).T
        cv = trilerp(LUT, SZ, Dn)
        ap0 = adx16_to_aces(cv)
        XB = aces_to_xyz_d65(ap0); XBe = aces_to_xyz_d65(ap0 * s_exp)
        XBt = aces_to_xyz_d65(adx16_to_aces(apply_apd_trims(cv, trims)))   # the DCTL chain
        XBg = aces_to_xyz_d65(ap0 * s_rgb)                                  # AP0 gains, comparison only
        f = lambda X: "%5.2f / %5.2f" % (eng.dE(X, Xa).mean(), eng.dE(X, Xa).max())
        print("  %-20s %6d | %s | %s | %s | %s | %s   (trims vs gains: max dE %.2f)"
              % (nm, len(La), f(XA), f(XB), f(XBe), f(XBt), f(XBg), eng.dE(XBt, XBg).max()))
    print("  grey ramp (dlogH): route A Y/Y0 | route B (+exposure) Y/Y0, AP0 spread | expected 10^d")
    ramp = []
    for d in np.arange(-2.0, 2.001, 0.5):
        Dn = eng.L_to_scan_norm(np.full((1, 3), 10.0 ** d))
        YA = float((eng.M @ eng.scan_norm_to_L(Dn).T).T[0, 1]) / 0.18
        ap0 = adx16_to_aces(trilerp(LUT, SZ, Dn))[0] * s_exp
        YB = float(aces_to_xyz_d65(ap0)[1]) / 0.18
        print("    %+.1f   %7.4f | %7.4f  %5.1f%% | %7.4f" % (d, YA, YB, 100 * (ap0.max() / ap0.min() - 1), 10.0 ** d))
        ramp.append((d, YB))
    r = np.array(ramp); sel = (r[:, 0] >= -1.0)
    slope = np.polyfit(r[sel, 0], np.log10(r[sel, 1]), 1)[0]
    print("  effective contrast of route B over dlogH -1..+2 (straight-line part): %.3f x the scene's (reference-film gamma 0.55 x %.3f = %.3f in CID terms)"
          % (slope, slope, 0.55 * slope))
