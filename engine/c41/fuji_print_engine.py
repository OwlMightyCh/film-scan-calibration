#!/usr/bin/env python3
"""C-41 -> RA-4 print-paper (Fujicolor Professional Paper Pro Laser TYPE II) emulation.

A THIN PRESET over the config-driven PrintEmulationEngine in
engine/c41/endura_print_engine.py.  Nothing about the physics changes: this file
supplies a PrintConfig whose only non-default field is print_medium_path (the
Fuji paper JSON) plus its own output cube paths.  The engine, the gray-axis
lock, the Status A inversion and the colorimetry are imported, not copied.

Paper data: data/papers/FujiProLaserTypeII_paper.json, vector-digitized from the
FUJIFILM Product Information Bulletin (Frontier QL type, Japan market) by
engine/c41/fuji_prolaser_digitize.py -- characteristic curves, spectral
sensitivity and spectral dye (reflection) density, key-for-key structurally
identical to data/papers/EnduraPremier_paper.json.  Like the Endura JSON it has
NO top-level "base" block, so PrintConfig.medium_base_spd stays at its default
(zeros) and the medium spectrum is dye-only.

Input domain, pipeline and outputs are identical to the Endura path; see
endura_print_engine's module docstring for the per-node pipeline.

================= FOUR WAYS THIS PAPER DIFFERS FROM ENDURA =================

1. RELATIVE EXPOSURE AXES, ARBITRARY ORIGIN.
   The bulletin prints no absolute logH origin: the H&D x-axis is a 0.5-decade
   gridline lattice and the spectral-sensitivity y-axis a 1.0-decade lattice,
   both with an arbitrary zero (Endura's were absolute).  FINDING (from reading
   the engine): NOTHING in the pipeline depends on an absolute logE or
   log-sensitivity zero, so no origin constant has to be invented.  Two
   independent reasons, both structural:
     (a) A global shift s on the paper's logE axis is exactly cancelled by the
         gray-axis lock.  solve_gray_axis_lock computes the balancing offset
         o_l = inv_hd(l, d_anchor) - LEmid_l and then stores the calibration as
         a MAP LEraw_l -> LEreq_l whose codomain is the paper's own logE axis.
         Shift the axis by s and every inv_hd output shifts by s, so LEreq
         shifts by s, and the forward H&D lookup shifts back by s.  The lock
         solves exposure PLACEMENT, so the placement absorbs the origin.
     (b) A global scale on the log-sensitivity axis multiplies E identically in
         all three layers (SENS_P = 10^log_sens enters E linearly), which is a
         constant additive shift in logE_raw -- again absorbed by o.
   What is NOT absorbed, and what actually matters, is preserved: the
   INTER-LAYER speed RATIOS and the per-layer curve SHAPES, because all three
   curves were read off one chart against one shared axis, so the unknown
   offset is common to the three.  Consequently there is no origin constant
   anywhere in this file.

2. LASER EXPOSURE vs TUNGSTEN ENLARGER (CAVEAT).
   These H&D curves were measured under narrow-band LASER exposure in a Frontier
   minilab (process CP-48S), and the emulsion's spectral sensitisation is
   laser-tuned.  PrintConfig.enlarger_K models a 3200 K broadband tungsten
   enlarger.  We deliberately KEEP the default enlarger_K so the Fuji and Endura
   renders stay directly comparable; integrating the tungsten SPD against the
   measured spectral-sensitivity curve is legitimate physics.  THE CAVEAT is the
   speed point: the H&D's exposure axis was established under a different
   exposure spectrum than the one we integrate, so the per-layer speeds carry a
   spectral-mismatch error.  Its neutral-axis component is soaked up by the
   gray-axis lock (see 1a); its residual is a non-neutral, density-dependent
   colour error that this model does not correct.

3. STATUS A EQUIVALENT, NOT CERTIFIED STATUS A.
   The bulletin says "ステータスA相当" -- Status A EQUIVALENT.  We invert it with
   the same ISO 5-3 Status A responsivities as the Endura path, i.e. we treat
   "equivalent" as "Status A".  Any deviation of Fuji's house densitometer from
   the ISO responsivities shows up as a small error in the recovered dye
   amounts.

4. DEEP MATTE SURFACE IS EXCLUDED.
   The bulletin states explicitly that the characteristic curves do NOT apply to
   the Deep Matte surface (※ディープマットは上記特性曲線とは異なります).  These
   cubes are therefore valid for the glossy/lustre surfaces only.

Run:  python3 engine/c41/fuji_print_engine.py   (from repo root; self-reports metrics)
"""
import argparse
import sys
import numpy as np
from pathlib import Path
import colour

sys.path.insert(0, str(Path(__file__).resolve().parent))    # sibling module import

from endura_print_engine import (  # noqa: E402
    PrintEmulationEngine, PrintConfig, read_cube, write_cube, pq_encode,
    trilinear, report_cube_fidelity, report_paper_tables, report_lock_nonaffinity,
    ROOT, DATA, BUILDS, DMAX, DW_NITS, ENLARGER_K, LAYERS,
    NEG_DYE, NEG_CURVES, STATUSM, STATUSA, CMFS,
    K_LO, K_HI, N_CAL, K_MID, NEG_STOCKS, NEG_STOCK, neg_paths, stocks_for_paper,
)

FUJI_STOCKS = stocks_for_paper("fujiprolaser")

FUJI_PAPER = DATA / "papers" / "FujiProLaserTypeII_paper.json"

# Default negative is now a FUJIFILM stock, not Portra 400. The pairing rule for
# this repo is Kodak negatives -> Kodak (Endura) paper, Fujifilm negatives ->
# Fuji paper: a print emulation is only meaningful for a combination someone
# would actually run, and Portra-on-Fuji-paper was an artifact of this engine
# predating any digitized Fujifilm negative.
DEFAULT_NEG = "fujifilm400"


class FujiProLaserPrintEngine(PrintEmulationEngine):
    """Fujicolor Professional Paper Pro Laser TYPE II RA-4 reflective preset.

    Identical to EnduraPrintEngine except for print_medium_path.  In particular
    enlarger_K keeps its 3200 K default (see caveat 2 in the module docstring)
    and medium_base_spd stays None (the JSON has no "base" block), so the paper
    swap is the only difference between the two renders.
    """
    def __init__(self, stock=DEFAULT_NEG):
        neg_dye, neg_curves = neg_paths(stock)
        super().__init__(PrintConfig(
            medium_mode="reflective",
            neg_dye_path=neg_dye,
            neg_curves_path=neg_curves,
            statusm_path=STATUSM,
            statusa_path=STATUSA,
            cmfs_path=CMFS,
            print_medium_path=FUJI_PAPER,
        ))


# ================= metrics helpers =================
def lut_rmse(lut, exact_fn, n=11):
    """RMSE of the LUT's trilinear interpolation vs the exact engine, sampled on
    an OFF-lattice grid (cell interiors: where interpolation error lives)."""
    ax = (np.arange(n) + 0.5) / n
    P = np.array(np.meshgrid(ax, ax, ax, indexing="ij")).reshape(3, -1).T
    ref = np.asarray(exact_fn(P), float)
    got = trilinear(lut, P)
    return float(np.sqrt(np.mean((got - ref) ** 2))), float(np.max(np.abs(got - ref)))


def gray_lock_residual(eng):
    """Gray-axis-lock solve residual: |achieved per-layer Status A density -
    the master neutral tone curve| over the calibration span."""
    KK = np.linspace(eng.cfg.k_lo, eng.cfg.k_hi, eng.cfg.n_cal)
    D_P = eng.dnorm_to_reflectance(np.repeat(KK[:, None], 3, axis=1))[1]   # (N,3)
    r = np.abs(D_P - D_P.mean(1, keepdims=True))
    return float(np.sqrt(np.mean(r ** 2))), float(r.max())


# ================= build + metrics =================
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # The pairing rule is enforced here, not merely documented: a Kodak
    # negative on Fuji paper is a combination nobody ever ran, so argparse
    # rejects it rather than the engine silently building it.
    ap.add_argument("--stock", choices=FUJI_STOCKS, default=DEFAULT_NEG,
                    help="Fujifilm NEGATIVE to print on this paper (default: %s)" % DEFAULT_NEG)
    args = ap.parse_args(argv)
    neg = NEG_STOCKS[args.stock]
    neg_name, neg_prefix = neg["display_name"], neg["file_prefix"]
    CUBE_P3 = BUILDS / "c41" / "print_fuji" / ("%s_to_FujiProLaser_DisplayP3.cube" % neg_prefix)
    CUBE_PQ = BUILDS / "c41" / "print_fuji" / ("%s_to_FujiProLaser_P3D65_PQ203.cube" % neg_prefix)
    eng = FujiProLaserPrintEngine(args.stock)
    print("=== C-41 -> RA-4 Fujicolor Pro Paper Pro Laser TYPE II print-emulation engine ===")
    print("paper data: %s" % eng.paper_prov["source"])
    print("  status: %s | densitometry: %s | process: %s | exposure: %s"
          % (eng.paper_prov.get("status"), eng.paper_prov.get("densitometry_note"),
             eng.paper_prov.get("process"), eng.paper_prov.get("exposure")))
    print("  CAVEATS: H&D measured under LASER exposure but rendered through a %.0f K tungsten "
          "enlarger; Status A EQUIVALENT (not certified); curves EXCLUDE the Deep Matte surface; "
          "logE / log-sensitivity axes are RELATIVE (arbitrary origin -- absorbed by the "
          "gray-axis lock, no origin constant assumed)." % ENLARGER_K)
    print("input domain: normalized ISO Status M density [0,1]^3 = OD/%.2f, D-MIN EXCLUDED" % DMAX)
    for i, l in enumerate(LAYERS):
        print("  %-8s channel: sens peak %.1f nm, dye peak %.1f nm, H&D logE [%.2f, %.2f] "
              "D [%.3f, %.3f]"
              % (l, eng.peak_sens[i], eng.peak_dye[i],
                 eng.hd_logE[i][0], eng.hd_logE[i][-1],
                 eng.hd_dens[i].min(), eng.hd_dens[i].max()))
    print("enlarger K = %.0f (default kept deliberately; see caveat 2)" % ENLARGER_K)
    print("negative spectral support: %.0f-%.0f nm, mode=%s ; paper exposure weight kept "
          "[C,M,Y] = %s" % (eng.neg_support[0], eng.neg_support[1], eng.cfg.neg_support_mode,
                            np.round(eng.exp_weight_kept, 3).tolist()))

    # ---- gray-axis lock ----
    print("=== gray-axis lock ===")
    print("  basis=%s (chromaticity-neutral on %.1f%% of the calibration ramp, equal-density "
          "elsewhere)" % (eng.cfg.neutral_basis, 100.0 * eng.visual_frac))
    print("  o [C,M,Y] (balancing offsets; the relative-axis origin is folded in here) = %s"
          % np.round(eng.o, 4).tolist())
    print("  mid-gray anchor: %s, K_MID=%.2f -> Status A density %.4f (target Y=%.2f)"
          % (eng.cfg.mid_anchor, K_MID, eng.d_anchor, eng.cfg.y_mid))
    print("  master neutral clamped to the band all 3 layers realise: D in [%.3f, %.3f]"
          % (eng.d_lo, eng.d_hi))
    print("  calibrated span k in [%.2f, %.2f], N=%d" % (K_LO, K_HI, N_CAL))
    r_rms, r_max = gray_lock_residual(eng)
    print("  solve residual |D_layer - master| over the calibration ramp: RMS %.3e  max %.3e"
          % (r_rms, r_max))
    D_mid_ach = eng.dnorm_to_reflectance(np.full((1, 3), K_MID))[1][0]
    print("  achieved print density @K_MID [C,M,Y] = %s (anchor %.4f)"
          % (np.round(D_mid_ach, 4).tolist(), eng.d_anchor))

    # ---- neutral-axis ramp ----
    print("=== neutral-axis ramp: Dnorm = k*(1,1,1) ===")
    print("   k      DisplayP3(R,G,B)          chroma_err     Y")
    for k in np.arange(0.05, 0.601, 0.05):
        lin, XYZ, D_P, a = eng.dnorm_to_linP3(np.full((1, 3), k))
        rgb = np.clip(lin[0], 0.0, 1.0)
        m = max(abs(rgb.mean()), 1e-9)
        chroma = float(np.max(np.abs(rgb - rgb.mean())) / m)
        print("  %.2f   %-24s  %.4f       %.5f"
              % (k, np.round(rgb, 4).tolist(), chroma, float(XYZ[0, 1])))
    kfine = np.linspace(0.02, 0.60, 400)
    linf = eng.dnorm_to_linP3(np.repeat(kfine[:, None], 3, axis=1))[0]
    j = int(np.argmin(np.abs(np.clip(linf, 0.0, 1.0).mean(1) - 0.18)))
    print("neutral input k reproducing mid-gray (linear P3 mean ~= 0.18): k=%.3f" % kfine[j])

    # ---- printable neutral window (PAPER-SPECIFIC: NOT Endura's) ----
    kf = np.linspace(0.0, 1.0, 501)
    Dn = eng.dnorm_to_reflectance(np.repeat(kf[:, None], 3, axis=1))[1].mean(1)
    inside = (Dn > eng.d_lo + 0.02) & (Dn < eng.d_hi - 0.02)
    if inside.any():
        print("printable neutral window (Fuji, COMPUTED; Endura's differs): "
              "Dnorm k in [%.3f, %.3f]; outside it the print clips to paper white / max black"
              % (float(kf[inside][0]), float(kf[inside][-1])))
        report_lock_nonaffinity(eng, float(kf[inside][0]), float(kf[inside][-1]))
        # System gamma over that window: d(print reflection density)/d(negative OD).
        # The negative-density axis is k*DMAX; multiply by the negative's own gamma
        # for a scene-referred figure.
        x = kf[inside] * DMAX
        y = Dn[inside]
        print("system gamma over the window: dD_print/dD_neg = %.3f (LS fit) / %.3f (endpoint), "
              "negative-referred"
              % (float(np.polyfit(x, y, 1)[0]), float((y[-1] - y[0]) / (x[-1] - x[0]))))
    else:
        print("printable neutral window: EMPTY (the neutral ramp never clears both clips)")

    # ================= build 65^3 cubes =================
    SZ = 65
    ax = np.linspace(0.0, 1.0, SZ)
    node = np.array(np.meshgrid(ax, ax, ax, indexing="ij")).reshape(3, -1).T
    lin, XYZ, D_P, a = eng.dnorm_to_linP3(node)

    # ---- paper-side table use over the emitted lattice ----
    report_paper_tables(eng, node, a, SZ)
    D_od = node * DMAX
    dye_in = eng.invert_statusm(D_od)
    mres = np.abs(eng.statusm_fwd(dye_in) - D_od)
    mclip = ((dye_in <= 1e-12) | (dye_in >= 8.0 - 1e-9)).any(1)
    print("Status M inversion residual |D| over the lattice: median %.3e  95th %.3e  max %.3e"
          "  (%.2f%% of nodes need an unrealizable negative-dye amount)"
          % (float(np.median(mres)), float(np.percentile(mres, 95)), float(mres.max()),
             100.0 * mclip.mean()))

    # ---- gamut diagnostics (pre-clip) ----
    outside = 100.0 * np.mean(np.any((lin < 0.0) | (lin > 1.0), axis=1))
    print("=== gamut: %.2f%% of the %d^3 lattice outside Display-P3 [0,1] (pre-clip) ==="
          % (outside, SZ))

    hdr = [
        "%s (Status M density, D-min excluded) -> Fujicolor Pro Paper Pro Laser TYPE II print" % neg_name,
        "Paper = FUJIFILM Product Information Bulletin, Pro Laser TYPE II (Status A EQUIVALENT,"
        " CP-48S, laser exposure; Deep Matte surface EXCLUDED)",
        "Paper H&D / spectral-sensitivity axes are RELATIVE (arbitrary origin), absorbed by the"
        " gray-axis lock; no absolute origin assumed",
        "Rendered through the default 3200 K tungsten enlarger model (caveat: the H&D speed point"
        " was established under narrow-band laser exposure)",
        "INPUT  = normalized Status M density [0,1]^3 = OD/%.2f, D-MIN EXCLUDED" % DMAX,
        "         (chain AFTER %s_StatusM.cube; sole C-41 delivery route)" % neg_prefix,
    ]

    # ---- 9a: Display P3 cube ----
    lut_p3 = colour.cctf_encoding(np.clip(lin, 0.0, 1.0), function="sRGB").reshape(SZ, SZ, SZ, 3)
    write_cube(CUBE_P3, lut_p3, SZ, hdr + [
        "OUTPUT = Display P3 (D65), sRGB-encoded, clipped [0,1]",
        "GRAY BALANCE = full per-channel gray-axis lock",
    ])

    def f_p3(P):
        return colour.cctf_encoding(np.clip(eng.dnorm_to_linP3(P)[0], 0.0, 1.0), function="sRGB")

    l_rmse, l_max = lut_rmse(lut_p3, f_p3)
    print("LUT %s: interpolation RMSE %.3e  max %.3e (65^3 trilinear vs exact, off-lattice)"
          % (CUBE_P3.name, l_rmse, l_max))
    report_cube_fidelity(CUBE_P3, lut_p3, SZ, f_p3)

    # ---- 9b: P3-D65 PQ cube ----
    lut_pq = pq_encode(np.clip(lin, 0.0, None) * DW_NITS).reshape(SZ, SZ, SZ, 3)
    write_cube(CUBE_PQ, lut_pq, SZ, hdr + [
        "OUTPUT = P3-D65 primaries, ST2084/PQ transfer; paper white = %.0f nits (BT.2408)" % DW_NITS,
        "GRAY BALANCE = full per-channel gray-axis lock",
    ])

    def f_pq(P):
        return pq_encode(np.clip(eng.dnorm_to_linP3(P)[0], 0.0, None) * DW_NITS)

    l_rmse, l_max = lut_rmse(lut_pq, f_pq)
    print("LUT %s: interpolation RMSE %.3e  max %.3e (65^3 trilinear vs exact, off-lattice)"
          % (CUBE_PQ.name, l_rmse, l_max))
    report_cube_fidelity(CUBE_PQ, lut_pq, SZ, f_pq)

    print("wrote %s" % CUBE_P3.relative_to(ROOT))
    print("wrote %s" % CUBE_PQ.relative_to(ROOT))


if __name__ == "__main__":
    main()
