#!/usr/bin/env python3
"""Build the canonical Vision3 image-dye basis from the four traced stocks.

Replaces `data/films/Vision3_dye_density_corrected.json`, RETIRED 2026-07-28.

Why the old file was retired
----------------------------
It disagreed with a proper trace of its OWN stated source (250D / 5207) by
RMSE 0.042 D on cyan and up to **0.197 D at 402 nm**. It gave cyan a flat 0.02
across 400-450 nm; the printed chart shows a real descender from ~0.21 D at
400 nm through ~0.14 at 420 to ~0.03 by 500. Verified against the raster with
all five printed curves at 400 nm accounted for and magenta correctly flat there
(see builds/_forensics/V3_250D_overlay.png).

That band is not cosmetic: **69.2% of the ISO Status M BLUE channel's weight
lies in 400-460 nm**, so the old basis understated cyan-to-blue crosstalk by
~0.1 D exactly where blue is most sensitive. Every C-41 dye decomposition and
Status M cube built on it inherited that error.

Why a FAMILY AVERAGE
--------------------
The old file asserted the four Vision3 stocks share one image-dye set, but had
only checked it at three LED wavelengths (450/544/640 nm). Tracing all four
(engine/ecn2/v3_dye_digitize.py) confirms it at full spectral resolution: worst
pairwise RMSE over any dye and any pair is 0.0332 D, and peak wavelengths agree
to 1-2 nm (Y 447-448, M 538-539, C 683-685). Averaging the four therefore
reduces per-trace noise without smearing genuinely different chemistry -- and it
is now an evidenced choice rather than an assumption.

50D's printed curves end near 760 nm. Beyond that the average is taken over the
three stocks that reach 800; `n_stocks` records the contributing count at every
wavelength, so no value is ever synthesized from nothing. Nothing is flat-held
or zero-filled (the defect registered against Ektar 100).

Known limitation carried forward
--------------------------------
A non-negative C+M+Y fit to the printed Midscale Neutral leaves RMS 0.06-0.08 D
on all four stocks. This is a property of the CHART, not of the separation: the
retired basis closes no better (0.060-0.072) and with a worse maximum
(0.21-0.30 vs 0.16-0.19). The printed neutral is simply not an exact
non-negative mixture of the three peak-normalized dyes -- plausibly residual
stain surviving D-min subtraction, or dye shape shifting with concentration.
Undiagnosed; recorded so it is not rediscovered as a defect of this file.

Run:  python3 engine/ecn2/v3_basis_build.py
"""
import json
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "films"
STOCKS = ["50D", "200T", "250D", "500T"]
DYES = ["cyan", "magenta", "yellow"]
GRID = np.arange(400, 801, 1.0)
OUT = DATA / "Vision3_dye_density.json"


def load(stock):
    d = json.loads((DATA / ("Vision3_%s_dye_density.json" % stock)).read_text())
    fc = d["shared_full_curves"]
    w = np.array(fc["wavelength_nm"], float)
    out = {}
    for k in DYES:
        v = np.array([np.nan if t is None else t for t in fc[k]], float)
        m = ~np.isnan(v)
        # resample onto GRID, leaving NaN outside the traced support -- never
        # flat-held, never zero-filled
        r = np.full(GRID.shape, np.nan)
        inside = (GRID >= w[m][0]) & (GRID <= w[m][-1])
        r[inside] = np.interp(GRID[inside], w[m], v[m])
        out[k] = r
    return d, out


def main():
    warnings.filterwarnings("ignore", category=RuntimeWarning)  # all-NaN edge slices are by design
    per, meta = {}, {}
    for s in STOCKS:
        meta[s], per[s] = load(s)

    basis, counts = {}, {}
    for k in DYES:
        stack = np.vstack([per[s][k] for s in STOCKS])
        n = (~np.isnan(stack)).sum(0)
        with np.errstate(invalid="ignore"):
            avg = np.nanmean(stack, axis=0)
        avg[n == 0] = np.nan
        # NOTHING is synthesized at the edges. An earlier version of this file
        # held the terminal value across the <=3 nm the tracer cannot centre
        # (support runs ~401.5-798.5, the frame edges are 400/800). That is the
        # same class of defect as the C-41 blue-edge flat-hold, and it carried
        # 0.89% of the RP180 blue channel -- small, but synthesized.
        # engine/reversal/reversal_transform.py already established the correct
        # doctrine: emit null, let the CONSUMER derive its integration grid from
        # the measured support and renormalize its observer there. That converts
        # an unbounded "perfectly clear film" claim into a bounded one.
        # restore the file's normalization contract: peak exactly 1.0
        avg = avg / np.nanmax(avg)
        basis[k], counts[k] = avg, n

    # spread across stocks, for the audit
    spread = {}
    for k in DYES:
        stack = np.vstack([per[s][k] for s in STOCKS])
        with np.errstate(invalid="ignore"):
            sp = np.nanmax(stack, 0) - np.nanmin(stack, 0)
        ok = np.isfinite(sp)
        spread[k] = {"max_D": round(float(sp[ok].max()), 4),
                     "max_at_nm": int(GRID[ok][int(np.argmax(sp[ok]))]),
                     "median_D": round(float(np.median(sp[ok])), 4)}

    def ser(a):
        return [None if not np.isfinite(v) else round(float(v), 5) for v in a]

    doc = {
        "title": "KODAK VISION3 shared image-dye set (family average of 50D/200T/250D/500T)",
        "source": ("Traced from the Spectral Dye-Density chart of each stock's own "
                   "datasheet (H-1-5203/5213/5207/5219, page 4, embedded raster ~250-260 dpi) "
                   "by engine/ecn2/v3_dye_digitize.py; averaged by engine/ecn2/v3_basis_build.py"),
        "units": "relative diffuse spectral density (Status M, D-min subtracted)",
        "normalization": "peak = 1.0 per dye (as the datasheet caption states)",
        "stocks_covered": ["50D (5203)", "200T (5213)", "250D (5207)", "500T (5219)"],
        "replaces": {
            "file": "Vision3_dye_density_corrected.json",
            "retired": "2026-07-28",
            "reason": ("disagreed with a proper trace of its own stated source (250D) by "
                       "RMSE 0.042 D cyan / 0.037 magenta / 0.012 yellow, max 0.197 D for "
                       "cyan at 402 nm; it flattened cyan to 0.02 across 400-450 nm where "
                       "the chart shows a real descender from ~0.21 D. That band carries "
                       "69.2% of Status M blue-channel weight."),
        },
        "shared_full_curves": {
            "wavelength_nm": [int(v) for v in GRID],
            **{k: ser(basis[k]) for k in DYES},
        },
        "support_note": ("Edge columns (<=3 nm at each frame edge) hold the terminal value -- a line-centring artifact, not absent data. Wider gaps stay null.  50D's printed curves end near "
                         "760 nm, so beyond that the average is over the three stocks that "
                         "reach 800 nm; n_stocks_contributing records the count at every "
                         "wavelength. Beyond those <=3 nm edge columns nothing is flat-held or "
                         "zero-filled."),
        "audit": {
            "n_stocks_contributing": {k: [int(v) for v in counts[k]] for k in DYES},
            "shared_dye_set_evidence": {
                "worst_pairwise_rmse_D": 0.0332,
                "claim_it_tests": ("the datasheets' ~0.03 D agreement, previously checked "
                                   "only at 450/544/640 nm"),
                "peak_wavelengths_nm": {s: {k: meta[s]["digitization_audit"]["curves"][k]
                                            ["peak_wavelength_nm"]
                                            for k in DYES} for s in STOCKS}
                if all("curves" in meta[s].get("digitization_audit", {}) for s in STOCKS) else None,
            },
            "inter_stock_spread": spread,
            "closure_caveat": ("non-negative C+M+Y vs the printed Midscale Neutral leaves "
                               "RMS 0.06-0.08 D on all four stocks. A chart property, not a "
                               "separation bias: the retired basis closes no better "
                               "(0.060-0.072) with a worse maximum. Undiagnosed."),
        },
    }
    OUT.write_text(json.dumps(doc, indent=2) + "\n")

    print("=== Vision3 canonical basis rebuilt (family average of four traced stocks) ===")
    for k in DYES:
        v = basis[k]
        ok = np.isfinite(v)
        print("  %-8s peak %.4f @ %d nm   support %d-%d nm   spread max %.4f D @ %d nm"
              % (k, np.nanmax(v), int(GRID[int(np.nanargmax(v))]),
                 int(GRID[ok][0]), int(GRID[ok][-1]),
                 spread[k]["max_D"], spread[k]["max_at_nm"]))
    n4 = int((counts["cyan"] == 4).sum())
    print("  wavelengths with all four stocks contributing: %d of %d" % (n4, len(GRID)))
    print("wrote %s" % OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
