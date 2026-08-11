#!/usr/bin/env python3
"""Compare digitized C-41 datasheets directly, stock against stock.

This compares the DIGITIZED DATASHEET DATA, not the fitted dye decomposition or
the built cubes, and that is deliberate. The surrogate-basis fit has a measured
basis sensitivity of 0.030-0.105 D (PROJECT.md, ensemble re-run 2026-07-28) which is
LARGER than the distance between several stocks, so two stocks agreeing after
decomposition is weak evidence -- the pipeline cannot separate Portra 400 from
Ektar 100 either. The datasheet curves carry no such ambiguity: they are what the
manufacturer measured.

Three comparisons, in decreasing order of how much they prove:

  1. SPECTRAL DYE DENSITY. Both Kodak and Fuji sheets plot the same two curves
     under the same convention -- "typical densities for a mid-scale neutral
     subject and for D-min", Status M -- so midscale, D-min and the aggregate
     (midscale - D-min) are directly comparable in absolute density units.
  2. CHARACTERISTIC CURVES. Both are Status M against an ABSOLUTE log-exposure
     axis in lux-seconds under daylight, so density-vs-logH overlays directly.
     Compared on the overlap of the two supports.
  3. SPECTRAL SENSITIVITY. SHAPE ONLY. Fuji prints a relative log axis with an
     arbitrary origin, at a different reference density (1.0 vs 0.2 above D-min)
     over a different range (400-700 vs 250-750 nm). Peak positions and curve
     shape are comparable; absolute magnitudes are NOT.

Run:  python3 engine/c41/c41_stock_compare.py --stocks ultramax400 fujifilm400
      python3 engine/c41/c41_stock_compare.py --all-pairs
"""
import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "films"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from portra_stocks import STOCKS                      # noqa: E402

# Measured sensitivity of the surrogate-basis dye decomposition to the choice of
# basis: how far the Status M cube moves when the basis is swapped for a
# plausible alternative. Any new distance is meaningless without this scale.
#
# Re-measured 2026-07-28 against the CORRECTED Vision3 basis and the
# measured-support fit. It WIDENED, 0.045-0.055 -> 0.030-0.105, which is the
# right direction: the band is the distance to a WRONG basis, and the corrected
# canonical now fits 2-5x better than any alternative (0.012-0.016 D against
# 0.029-0.072), so it sits further from them. Read it as basis SENSITIVITY, not
# as an error bar on the truth -- the alternatives are no longer equally credible.
BASIS_UNCERTAINTY_D = (0.030, 0.105)


def load(stock):
    s = STOCKS[stock]
    c = json.load(open(DATA / s["curves_json"]))
    # Stocks flagged 'sensitivity_absent' carry no 'sensitivity_json' key at all
    # (Pro 400H: four-curve sensitivity chart, see portra_stocks.py).
    try:
        v = json.load(open(DATA / s["sensitivity_json"]))
    except (FileNotFoundError, KeyError):
        v = None
    return s, c, v


def spectral(c):
    """Digitized spectra, plus the stock's MEASURED support.

    The top-level arrays are flat-held past each trace's ends -- every Kodak
    trace stops short of the 400 nm frame edge (402.5-403.7) and Ektar 100 also
    stops at 687.9 rather than 700. Those held values are indistinguishable in
    the array from measured ones, so a comparison run over a fixed 400-700 grid
    silently compares fabricated data. Only Ektar is materially affected (its
    gap is 13 nm wide against 3-4 nm elsewhere): restricting to measured support
    moves Ektar-Portra160 by -0.0067 D and every non-Ektar pair by <= 0.0005.
    The true support is recorded by the digitizer, so use it.
    """
    wl = np.array(c["spectral"]["wavelength_nm"], float)
    mid = np.array(c["spectral"]["midscale_neutral"], float)
    dmn = np.array(c["spectral"]["dmin"], float)
    lo, hi = float(wl[0]), float(wl[-1])
    try:
        ep = c["digitization_audit"]["spectral_dye_density"]["endpoints"]
        lo = max(lo, max(v["wavelength_range_nm"][0] for v in ep.values()))
        hi = min(hi, min(v["wavelength_range_nm"][1] for v in ep.values()))
    except (KeyError, TypeError):
        pass
    keep = (wl >= lo) & (wl <= hi)
    return wl[keep], mid[keep], dmn[keep]


def char(c):
    x = np.array(c["char_curves"]["log_exposure"], float)
    d = {k: np.array(v, float) for k, v in c["char_curves"]["statusM_density"].items()}
    return x, d


def shape_residual(a, b):
    """Residual after allowing ONE overall amplitude scale: min_alpha ||a - alpha*b||.

    The aggregate is dye_amount x dye_spectrum, and "midscale neutral" means
    whatever exposure the manufacturer chose to call midscale. A different choice
    scales all three dye amounts together, moving the aggregate's AMPLITUDE while
    leaving its SHAPE alone. Kodak and Fuji had no reason to pick the same point,
    so a raw aggregate distance across manufacturers confounds dye chemistry with
    a densitometric bookkeeping choice. This removes exactly that one degree of
    freedom and no more.

    The residual is made SYMMETRIC: a least-squares alpha is not, so a raw
    directional residual would rank a pair differently depending on which stock
    was named first (Ultra Max vs Fujifilm gave 0.081 one way and 0.101 the
    other). Using the angle between the two spectra instead,

        shape_rms = mean_magnitude * sqrt(2 * (1 - cos))

    is order-free and still in density units; it coincides with the directional
    residual whenever the two amplitudes already agree (alpha ~ 1).

    Returns (alpha, rms_residual, cosine_similarity).
    """
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    alpha = float(a @ b / (b @ b))
    cos = float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))
    mag = 0.5 * (np.sqrt(np.mean(a ** 2)) + np.sqrt(np.mean(b ** 2)))
    rms = float(mag * np.sqrt(max(2.0 * (1.0 - cos), 0.0)))
    return alpha, rms, cos


def stats(a, b, label, unit="D"):
    r = a - b
    return ("  %-26s RMS %.4f %s   max %.4f %s   mean %+.4f %s"
            % (label, np.sqrt(np.mean(r ** 2)), unit, np.max(np.abs(r)), unit,
               np.mean(r), unit))


def gamma(x, y, lo=-2.5, hi=-0.5):
    m = (x >= lo) & (x <= hi)
    if m.sum() < 5:
        m = np.ones_like(x, bool)
    return float(np.polyfit(x[m], y[m], 1)[0])


def speed_offset(xa, ya, xb, yb, dens=1.0):
    """logH shift between two curves at a common density -- i.e. relative speed."""
    def logh_at(x, y, d):
        if d < y.min() or d > y.max():
            return None
        return float(np.interp(d, y, x))
    a, b = logh_at(xa, ya, dens), logh_at(xb, yb, dens)
    return None if (a is None or b is None) else b - a


def compare(sa, sb, verbose=True):
    (Sa, Ca, Va), (Sb, Cb, Vb) = load(sa), load(sb)
    na, nb = Sa["display_name"], Sb["display_name"]
    out = {}
    if verbose:
        print("=" * 78)
        print("%s   vs   %s" % (na, nb))
        print("  %s (%s, %s)  |  %s (%s, %s)"
              % (na, Sa["datasheet_code"], Sa["datasheet_date"],
                 nb, Sb["datasheet_code"], Sb["datasheet_date"]))
        print("=" * 78)

    # ---- 1. spectral dye density ----
    wa, ma, da = spectral(Ca)
    wb, mb, db = spectral(Cb)
    lo, hi = max(wa[0], wb[0]), min(wa[-1], wb[-1])
    g = np.arange(lo, hi + 1)
    ma_, da_ = np.interp(g, wa, ma), np.interp(g, wa, da)
    mb_, db_ = np.interp(g, wb, mb), np.interp(g, wb, db)
    agg_a, agg_b = ma_ - da_, mb_ - db_
    out["aggregate_rms"] = float(np.sqrt(np.mean((agg_a - agg_b) ** 2)))
    out["dmin_rms"] = float(np.sqrt(np.mean((da_ - db_) ** 2)))
    out["midscale_rms"] = float(np.sqrt(np.mean((ma_ - mb_) ** 2)))
    # SHARED-ARTWORK GUARD. Fujifilm published the SAME spectral-dye-density
    # chart in the Fujifilm 200 and Fujifilm 400 datasheets -- byte-identical
    # Bezier control points, verified in the PDFs. A distance computed from it is
    # therefore NOT independent evidence about both stocks, and a 0.0000 row is a
    # statement about the artwork, not the emulsions. Say so rather than let a
    # perfect score be read as a perfect match.
    if np.allclose(agg_a, agg_b, atol=1e-9) and np.allclose(da_, db_, atol=1e-9):
        out["shared_artwork"] = True
        if verbose:
            print("!! %s and %s carry IDENTICAL digitized spectra -- the two datasheets"
                  % (na, nb))
            print("!! reuse one chart. This distance measures the ARTWORK, not the films.")
    al, ar, ac = shape_residual(agg_a, agg_b)
    dl, dr, dc = shape_residual(da_, db_)
    out["aggregate_shape_rms"], out["aggregate_alpha"], out["aggregate_cos"] = ar, al, ac
    out["dmin_shape_rms"], out["dmin_cos"] = dr, dc
    if verbose:
        print("1. SPECTRAL DYE DENSITY (Status M, %d-%d nm, same convention on both sheets)"
              % (lo, hi))
        print(stats(ma_, mb_, "midscale neutral"))
        print(stats(da_, db_, "D-min"))
        print(stats(agg_a, agg_b, "aggregate (mid - D-min)"))
        print("   scale-invariant SHAPE test (removes the midscale-exposure choice):")
        print("     aggregate: alpha %.4f  residual RMS %.4f D  cosine %.6f"
              % (al, ar, ac))
        print("     D-min    : alpha %.4f  residual RMS %.4f D  cosine %.6f"
              % (dl, dr, dc))
        print("   per-wavelength aggregate:")
        print("     nm     %-14s %-14s  delta" % (na, nb))
        for w in range(int(lo), int(hi) + 1, 50):
            j = int(np.where(g == w)[0][0])
            print("     %3d    %-14.4f %-14.4f  %+.4f"
                  % (w, agg_a[j], agg_b[j], agg_a[j] - agg_b[j]))

    # ---- 2. characteristic curves ----
    xa, dA = char(Ca)
    xb, dB = char(Cb)
    clo, chi = max(xa[0], xb[0]), min(xa[-1], xb[-1])
    if chi > clo:
        cg = np.arange(clo, chi + 1e-9, 0.02)
        if verbose:
            print("2. CHARACTERISTIC CURVES (Status M vs absolute logH, overlap %.2f..%.2f)"
                  % (clo, chi))
        ch_rms = []
        for k in ("B", "G", "R"):
            ya = np.interp(cg, xa, dA[k])
            yb = np.interp(cg, xb, dB[k])
            ch_rms.append(float(np.sqrt(np.mean((ya - yb) ** 2))))
            if verbose:
                print(stats(ya, yb, "%s channel density" % k))
                print("      gamma %s %.4f   %s %.4f   delta %+.4f"
                      % (na, gamma(cg, ya), nb, gamma(cg, yb),
                         gamma(cg, yb) - gamma(cg, ya)))
                so = speed_offset(xa, dA[k], xb, dB[k], dens=1.0)
                if so is not None:
                    print("      logH offset at D=1.0: %+.3f decade (%+.2f stop)"
                          % (so, so / 0.301))
        out["char_rms"] = float(np.mean(ch_rms))

    # ---- 3. spectral sensitivity (shape only) ----
    if Va and Vb and verbose:
        print("3. SPECTRAL SENSITIVITY -- SHAPE ONLY (Fuji axis is relative; reference "
              "densities and ranges differ)")
        for layer in ("yellow", "magenta", "cyan"):
            pa = Va["digitization_audit"]["layers"][layer]
            pb = Vb["digitization_audit"]["layers"][layer]
            print("  %-8s peak  %s %7.1f nm   %s %7.1f nm   delta %+.1f nm"
                  % (layer, na, pa["peak_wavelength_nm"],
                     nb, pb["peak_wavelength_nm"],
                     pb["peak_wavelength_nm"] - pa["peak_wavelength_nm"]))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stocks", nargs=2, metavar="STOCK")
    ap.add_argument("--all-pairs", action="store_true",
                    help="every pair with a digitized curves JSON, ranked by "
                         "aggregate distance (gives the headline number a scale)")
    a = ap.parse_args()

    if a.stocks:
        compare(*a.stocks)
    if a.all_pairs or not a.stocks:
        have = [k for k in STOCKS
                if (DATA / STOCKS[k]["curves_json"]).exists()]
        rows = []
        for x, y in itertools.combinations(sorted(have), 2):
            r = compare(x, y, verbose=False)
            rows.append((r["aggregate_shape_rms"], r["aggregate_rms"],
                         r["aggregate_alpha"], r["dmin_shape_rms"],
                         r.get("char_rms"), x, y))
        rows.sort()
        print()
        print("=" * 78)
        print("ALL PAIRS, ranked by spectral aggregate distance (Status M density)")
        print("=" * 78)
        print("  ranked by SHAPE residual -- what survives one overall amplitude scale")
        print("  %-11s %-11s  %-9s %-9s %-7s %-9s %s" %
              ("stock A", "stock B", "shape", "raw agg", "alpha", "D-min sh", "char"))
        for sh, agg, al, dsh, ch, x, y in rows:
            print("  %-11s %-11s  %-9.4f %-9.4f %-7.3f %-9.4f %s"
                  % (x, y, sh, agg, al, dsh, ("%.4f" % ch) if ch else "n/a"))
        print()
        print("  SCALE: the surrogate-basis dye decomposition has a measured")
        print("  basis sensitivity of %.3f-%.3f D. A pair below that is indistinguishable"
              % BASIS_UNCERTAINTY_D)
        print("  to the modelling pipeline REGARDLESS of whether the films differ.")
        print("  The datasheet distances above are free of that ambiguity.")


if __name__ == "__main__":
    main()
