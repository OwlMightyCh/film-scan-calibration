#!/usr/bin/env python3
"""First end-to-end C-41 error budget, in dE2000 on the PRINT output.

This project bounds its error terms one at a time, in whatever space each was
measured in -- spectral density, scan density, Status M density, Display-P3 code
value -- and never combines them.  The consequence is that the number the
per-stock tables lead with (the dye fit residual, ~0.013 D) is among the
SMALLEST terms in the chain, while basis sensitivity is several times larger, and
no reader can see that from the tables because the terms are not commensurable.

This tool makes them commensurable.  Each term is perturbed at ITS OWN measured
bound, in ITS OWN space, and the perturbation is pushed through the actual print
engine to the actual deliverable -- print emulation is the sole C-41 delivery
route, so the deliverable is the print cube and the output space is dE2000 on
the print output.

MEASUREMENT INSTRUMENT ONLY: it imports the shipped engines, mutates nothing,
writes no .cube and no data file (the two perturbations that must reach the
engine through a file path go to a scratch directory that is deleted on exit).

Two colour groups are reported SEPARATELY and are never merged.  The engine's
gray-axis lock forces the neutral axis by construction and is re-solved under
every perturbation, exactly as a rebuilt cube would be, so every dye-side term
reads near zero on neutrals.  A budget that averaged the two groups would
therefore understate the real uncertainty by an order of magnitude.

Run:  python3 engine/c41/error_budget.py [--stock portra400]
"""
import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import colour

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

sys.path.insert(0, str(Path(__file__).resolve().parent))    # sibling module import
from endura_print_engine import (  # noqa: E402
    PrintEmulationEngine, PrintConfig, LAYERS, DMAX,
    STATUSM, STATUSA, CMFS, PAPER, NEG_STOCKS, NEG_STOCK, neg_paths,
    read_cube, trilinear, BUILDS,
)
from fuji_print_engine import FUJI_PAPER  # noqa: E402

ENSEMBLE = DATA / "films" / "_ensemble"

# ----- copied from engine/c41/endura_validate.py -------------------------------
# endura_validate defines to_lab_d65/dE2000, but importing that module is NOT
# side-effect free: it builds an engine and evaluates the whole 33^3 lattice at
# module scope (its validation battery runs on import).  These two functions are
# three lines each, so they are copied rather than paying for the battery.
_XYZ_D65 = colour.sd_to_XYZ(colour.SDS_ILLUMINANTS["D65"]) / 100.0
XY_D65 = colour.XYZ_to_xy(_XYZ_D65)


def to_lab_d65(xyz):
    return colour.XYZ_to_Lab(np.atleast_2d(xyz), XY_D65)


def dE2000(lab1, lab2):
    return colour.delta_E(lab1, lab2, method="CIE 2000")
# ----- end copied block --------------------------------------------------------

# ----- measured bounds that are NOT re-derived here ----------------------------
# Term 4: Status M cube serialisation error, reported by c41_statusm_engine as
# 0.0002 D over the working range.  It enters the print cube as an error on its
# INPUT, which is normalized density, hence the /DMAX.
SERIALISATION_D = 2.0e-4

# Term 3: register #13 -- the negative's D-min spectrum is flat-held outside the
# stock's measured support; continuing it linearly instead moves D-min by 0.009 D.
DMIN_EDGE_D = 0.009

# Term 5: print-cube trilinear interpolation, ALREADY measured in the output
# space by endura_print_engine's own self-report for the shipped Portra 400
# Display-P3 cube.  Taken as given (per spec) rather than re-derived, because
# re-deriving it means evaluating the engine over the full 65^3 lattice.
INTERP_RMSE_CV, INTERP_MAX_CV = 2.2e-3, 5.9e-2

# Term 6: camera spectral sensitivity.  Zero for the SHIPPED sensor-free cubes
# (a monochrome response cancels in the density ratio).  Register #9's Bayer
# bound is a channel-dependent density error, worst in green at a dense magenta.
BAYER_D = 0.114

# printable window on Endura (PROJECT.md); used to place the off-neutral patches
WINDOW = (0.109, 0.391)


CUBE_SIZE = 65


def paper_for(stock):
    return FUJI_PAPER if NEG_STOCKS[stock]["print_paper"] == "fujiprolaser" else PAPER


def cube_path_for(stock):
    """The SHIPPED Display-P3 print cube for this stock, by the pairing rule."""
    fuji = NEG_STOCKS[stock]["print_paper"] == "fujiprolaser"
    pre = NEG_STOCKS[stock]["file_prefix"]
    sub = "print_fuji" if fuji else "print_endura"
    name = ("%s_to_FujiProLaser_DisplayP3.cube" if fuji
            else "%s_to_PortraEndura_DisplayP3.cube") % pre
    return BUILDS / "c41" / sub / name


def make_engine(stock, **over):
    """Shipped print engine for `stock` (correct paper by the pairing rule),
    with PrintConfig fields optionally overridden for a perturbation."""
    neg_dye, neg_curves = neg_paths(stock)
    cfg = dict(medium_mode="reflective", neg_dye_path=neg_dye,
               neg_curves_path=neg_curves, statusm_path=STATUSM,
               statusa_path=STATUSA, cmfs_path=CMFS,
               print_medium_path=paper_for(stock))
    cfg.update(over)
    return PrintEmulationEngine(PrintConfig(**cfg))


# =====================================================================
#  test colours
# =====================================================================
def neutral_patches():
    """The grey ramp, k = 0.05 to 0.60 (the gray-axis lock's own span)."""
    k = np.arange(0.05, 0.6001, 0.025)
    return np.repeat(k[:, None], 3, axis=1)


def offneutral_patches(eng, n_axis=9, chroma_min=5.0, cap=400):
    """Saturated and mid-chroma patches spanning the printable window.

    A lattice over the neutral span, kept where the canonical render is inside
    Display-P3 [0,1] (i.e. actually printable and actually representable) and
    carries real chroma.  Selecting on the render rather than on the input keeps
    the set free of nodes no negative could produce a print from.
    """
    ax = np.linspace(0.05, 0.60, n_axis)
    P = np.array(np.meshgrid(ax, ax, ax, indexing="ij")).reshape(3, -1).T
    lin, XYZ, _, _ = eng.dnorm_to_linP3(P)
    lab = to_lab_d65(XYZ)
    C = np.hypot(lab[:, 1], lab[:, 2])
    keep = (lin.min(1) >= -1e-3) & (lin.max(1) <= 1.0 + 1e-3) & (C >= chroma_min)
    P = P[keep]
    if len(P) > cap:                      # deterministic thinning, never random
        P = P[np.linspace(0, len(P) - 1, cap).round().astype(int)]
    return P


# =====================================================================
#  evaluation helpers
# =====================================================================
def render(eng, P):
    """Print render of input Dnorm P -> (linear P3, Lab D65)."""
    lin, XYZ, _, _ = eng.dnorm_to_linP3(P)
    return lin, to_lab_d65(XYZ)


def de_stats(lab_ref, lab):
    de = dE2000(lab_ref, lab)
    return float(np.mean(de)), float(np.max(de))


def worst_over(deltas):
    """Combine a list of (mean, max) results into one term: the LARGEST mean and
    the LARGEST max over the perturbation directions tried."""
    return (max(d[0] for d in deltas), max(d[1] for d in deltas))


SIGNS = np.array([[a, b, c] for a in (1, -1) for b in (1, -1) for c in (1, -1)], float)


# =====================================================================
#  terms
# =====================================================================
def term_basis(stock, groups, ref):
    """1. BASIS SENSITIVITY -- the real perturbations, not a synthetic one.

    data/films/_ensemble holds the SAME stock refitted under each surrogate dye
    basis.  Pointing PrintConfig.neg_dye_path at each in turn is the whole
    perturbation: no code change, no fabricated curve.
    """
    stem = NEG_STOCKS[stock]["dye_density_json"].replace("_dye_density.json", "")
    bases = ["vision3", "e100", "provia100f", "velvia50", "velvia100", "parametric"]
    per_basis, out = [], {g: [] for g in groups}
    for b in bases:
        p = ENSEMBLE / ("%s_dye_density__%s.json" % (stem, b))
        if not p.exists():
            per_basis.append((b, None))
            continue
        eng = make_engine(stock, neg_dye_path=p)
        row = {}
        for g, P in groups.items():
            row[g] = de_stats(ref[g], render(eng, P)[1])
            out[g].append(row[g])
        per_basis.append((b, row))
    return {g: worst_over(v) for g, v in out.items()}, per_basis


def term_fit_residual(stock, groups, ref, tmpdir):
    """2. DYE FIT RESIDUAL -- fit_audit.aggregate_rmse_density, perturbed in
    density on the three dye curves.

    DIRECTION.  The residual is an aggregate over the three superposed dyes, so
    its per-layer sign is unknown.  A uniform +rmse on all three layers is the
    common mode: it is nearly a density scale, which the gray-axis lock largely
    absorbs, so taking it alone would flatter the term.  The perturbation is
    therefore applied as an additive offset of +/-rmse per layer over ALL FOUR
    independent sign patterns (the other four are their negatives and give the
    same magnitudes), and the term is the WORST of them -- the differential modes
    are what actually move hue, and they are what the lock cannot remove.

    The offset is applied to the peak-normalized curves, so it is an offset of
    rmse density units at unit dye amount, matching the units the audit reports.
    """
    dj = json.load(open(neg_paths(stock)[0]))
    rmse = float(dj["fit_audit"]["aggregate_rmse_density"])
    out = {g: [] for g in groups}
    for si, s in enumerate(SIGNS[:4]):
        pert = json.loads(json.dumps(dj))
        for i, l in enumerate(LAYERS):
            c = np.array(pert["shared_full_curves"][l], float)
            # clip at 0: a negative spectral density is not physical
            pert["shared_full_curves"][l] = np.clip(c + s[i] * rmse, 0.0, None).tolist()
        p = tmpdir / ("fitres_%d.json" % si)
        p.write_text(json.dumps(pert))
        eng = make_engine(stock, neg_dye_path=p)
        for g, P in groups.items():
            out[g].append(de_stats(ref[g], render(eng, P)[1]))
    return {g: worst_over(v) for g, v in out.items()}, rmse


def term_dmin_edge(stock, groups):
    """3. FABRICATED SPECTRAL EDGES (register #13).

    The held region is 380-400 and 700-730 nm: outside the stock's measured
    support.  The SHIPPED configuration is neg_support_mode="truncate", which
    does not integrate the paper exposure there at all, so a perturbation of the
    held D-min is EXACTLY zero on the shipped cube -- not approximately zero.
    That is reported as the shipped number, and the flat_hold configuration
    (where the held values do reach the exposure) is measured alongside it as the
    bound this term would carry if the engine ever stopped truncating.
    """
    res = {}
    for mode in ("truncate", "flat_hold"):
        base = make_engine(stock, neg_support_mode=mode)
        lab_ref = render(base, np.vstack([groups[g] for g in groups]))[1]
        held = ~((base.CGRID >= base.neg_support[0]) & (base.CGRID <= base.neg_support[1]))
        acc = {g: [] for g in groups}
        for s in (+1.0, -1.0):
            d = base.dmin_spec_C.copy()
            d[held] = np.clip(d[held] + s * DMIN_EDGE_D, 0.0, None)
            eng = make_engine(stock, neg_support_mode=mode, neg_dmin=d)
            for g, P in groups.items():
                acc[g].append(de_stats(render(base, P)[1], render(eng, P)[1]))
        res[mode] = {g: worst_over(v) for g, v in acc.items()}
    return res


def term_input_density(eng, groups, ref, delta_D, label):
    """4 / 6. A DENSITY error on the print cube's INPUT.

    Both the Status M serialisation error and the Bayer camera-SSF bound are
    errors in the negative's measured density, so both enter the print cube the
    same way: as an offset on Dnorm = D/DMAX, worst-cased over the eight
    per-channel sign patterns (a density error need not be common-mode).
    """
    dn = delta_D / DMAX
    out = {g: [] for g in groups}
    for s in SIGNS:
        for g, P in groups.items():
            Q = np.clip(P + s[None, :] * dn, 0.0, 1.0)
            out[g].append(de_stats(ref[g], render(eng, Q)[1]))
    return {g: worst_over(v) for g, v in out.items()}


def term_interpolation(eng, groups, ref, cube_path):
    """5. PRINT CUBE INTERPOLATION -- measured PER PATCH, not bounded.

    An earlier version applied the cube's single worst-node code-value error to
    every patch and worst-cased over sign patterns. That is a ceiling rather
    than a propagation, and because sRGB decoding amplifies a fixed code-value
    offset enormously in the deep shadows it reported tens of dE2000 where no
    real interpolation error of that size exists.

    What a user actually meets is the difference between the cube's trilinear
    output at their input and the exact transform at the same input, so that is
    what this measures: interpolate the SHIPPED artifact read back from disk at
    each test patch and compare against the engine's own forward. The result is
    a distribution over the patches rather than one number applied everywhere.
    """
    P3_to_XYZ = np.linalg.inv(eng.XYZ_to_P3)
    lut = read_cube(cube_path, CUBE_SIZE)
    out = {}
    for g, P in groups.items():
        lin, _ = render(eng, P)
        exact_enc = colour.cctf_encoding(np.clip(lin, 0.0, 1.0), function="sRGB")
        got_enc = trilinear(lut, np.clip(P, 0.0, 1.0))
        lin2 = colour.cctf_decoding(np.clip(got_enc, 0.0, 1.0), function="sRGB")
        out[g] = de_stats(ref[g], to_lab_d65(lin2 @ P3_to_XYZ.T))
    return out


# =====================================================================
#  report
# =====================================================================
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stock", choices=sorted(NEG_STOCKS), default=NEG_STOCK)
    args = ap.parse_args(argv)
    stock = args.stock
    paper = NEG_STOCKS[stock]["print_paper"]

    tmp = Path(tempfile.mkdtemp(prefix="c41_error_budget_"))
    try:
        base = make_engine(stock)
        groups = {"NEUTRAL": neutral_patches(),
                  "OFF-NEUTRAL": offneutral_patches(base)}
        ref = {g: render(base, P)[1] for g, P in groups.items()}

        print("=" * 78)
        print("C-41 END-TO-END ERROR BUDGET -- %s on %s paper" % (stock, paper))
        print("=" * 78)
        print("output space: dE2000 on the PRINT render (print emulation is the sole")
        print("C-41 delivery route, so the print cube IS the deliverable).")
        print("patches: NEUTRAL n=%d (grey ramp k=0.05..0.60) ; OFF-NEUTRAL n=%d "
              "(printable window k~[%.3f, %.3f], Cab* >= 5)"
              % (len(groups["NEUTRAL"]), len(groups["OFF-NEUTRAL"]), *WINDOW))
        print()
        print("THE TWO GROUPS ARE NEVER MERGED.  The gray-axis lock forces the neutral")
        print("axis by construction and is re-solved under every perturbation here, just")
        print("as it would be in a rebuilt cube, so every dye-side term reads near zero on")
        print("neutrals.  Averaging the groups would understate the real uncertainty by")
        print("about an order of magnitude.  Read the OFF-NEUTRAL column as the budget.")
        print()

        terms = []      # (label, {group: (mean, max)}, note)

        basis, per_basis = term_basis(stock, groups, ref)
        terms.append(("1 basis sensitivity", basis, "6 refits in data/films/_ensemble"))

        fitres, rmse = term_fit_residual(stock, groups, ref, tmp)
        terms.append(("2 dye fit residual", fitres, "+/-%.4f D on each dye curve" % rmse))

        dmin = term_dmin_edge(stock, groups)
        terms.append(("3 fabricated edges", dmin["truncate"],
                      "0 by construction: shipped mode truncates the held band"))

        ser = term_input_density(base, groups, ref, SERIALISATION_D, "serialisation")
        terms.append(("4 StatusM cube serialisation", ser,
                      "%.4f D on the input" % SERIALISATION_D))

        interp = term_interpolation(base, groups, ref, cube_path_for(stock))
        terms.append(("5 print cube interpolation", interp,
                      "measured per patch against the shipped cube"))

        zero = {g: (0.0, 0.0) for g in groups}
        terms.append(("6 camera SSF (SHIPPED, sensor-free)", zero,
                      "provably zero: monochrome response cancels"))

        bayer = term_input_density(base, groups, ref, BAYER_D, "bayer")
        dmin_fh = dmin["flat_hold"]

        w = 36
        for g in groups:
            print("-" * 78)
            print("%s  (n=%d)" % (g, len(groups[g])))
            print("-" * 78)
            print("%-*s %9s %9s   %s" % (w, "term", "mean dE", "max dE", "basis of the bound"))
            for label, val, note in terms:
                print("%-*s %9.4f %9.4f   %s" % (w, label, val[g][0], val[g][1], note))
            vals = [val[g] for _, val, _ in terms]
            rss = (float(np.hypot.reduce([v[0] for v in vals])),
                   float(np.hypot.reduce([v[1] for v in vals])))
            tot = (sum(v[0] for v in vals), sum(v[1] for v in vals))
            # dominance is ranked on the MEAN: the max column applies each term's
            # single worst-node magnitude to every patch at once, so it ranks the
            # terms by how badly they can behave somewhere, not by what they cost.
            dom = max(range(len(vals)), key=lambda i: vals[i][0])
            print()
            print("%-*s %9.4f %9.4f   ASSUMING INDEPENDENCE -- a LOWER BOUND, see below"
                  % (w, "TOTAL, root-sum-square", rss[0], rss[1]))
            print("%-*s %9.4f %9.4f   worst case, terms fully correlated"
                  % (w, "TOTAL, plain sum", tot[0], tot[1]))
            print("%-*s %9.4f %9.4f   %s"
                  % (w, "LARGEST SINGLE TERM", vals[dom][0], vals[dom][1], terms[dom][0]))
            print()
            print("  NOT in the totals above (different configurations):")
            print("  %-*s %9.4f %9.4f   Bayer capture, register #9 (%.3f D)"
                  % (w - 2, "camera SSF, BAYER sensor", bayer[g][0], bayer[g][1], BAYER_D))
            print("  %-*s %9.4f %9.4f   if the engine ever stops truncating"
                  % (w - 2, "fabricated edges, flat_hold mode", dmin_fh[g][0], dmin_fh[g][1]))
            print()
            print("  One reading above is an UPPER BOUND, not a typical value:")
            print("  * the Bayer row applies register #9's WORST-CASE bound (0.114 D, met")
            print("    only at a dense magenta) at every patch and in every sign pattern.")
            print("    Register #9 is explicit that the term is a function of density and")
            print("    is negligible below ~1.2 peak dye, so this is a ceiling.")
            print()

        print("-" * 78)
        print("BASIS SENSITIVITY, per surrogate basis (dE2000 vs the canonical fit)")
        print("-" * 78)
        print("%-14s %19s %19s" % ("basis", "NEUTRAL mean/max", "OFF-NEUTRAL mean/max"))
        for b, row in per_basis:
            if row is None:
                print("%-14s %19s   (no ensemble file -- NOT propagated)" % (b, "--"))
                continue
            print("%-14s %9.4f %9.4f %9.4f %9.4f"
                  % (b, row["NEUTRAL"][0], row["NEUTRAL"][1],
                     row["OFF-NEUTRAL"][0], row["OFF-NEUTRAL"][1]))
        print()
        print("=" * 78)
        print("INDEPENDENCE ASSUMPTION -- READ THIS BEFORE QUOTING THE RSS")
        print("=" * 78)
        print("The root-sum-square total assumes the terms are INDEPENDENT.  They are not")
        print("obviously so: the dye fit residual and the basis sensitivity both act on the")
        print("same three dye curves and are correlated by construction, and both feed the")
        print("same gray-axis lock.  The RSS is therefore a LOWER BOUND on the combined")
        print("uncertainty, and the plain sum is the fully-correlated worst case.  The true")
        print("value lies between them and no measurement in this project locates it.")
        if stock != "portra400":
            print()
            print("NOTE: term 5 uses the Portra 400 Display-P3 cube's interpolation figures")
            print("      (the engine only self-reports them for that build); for %s it is a"
                  % stock)
            print("      stand-in, not a measurement of that stock's own cube.")
        print()
        print("This tool wrote nothing.  It is a measurement instrument.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
