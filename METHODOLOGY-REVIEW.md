# Methodology review: open items

A three-reviewer methodology review of the eleven-stock C-41 chain, split by
identifiability, error accounting and validation logic. Every claim below was
verified against the shipped code by running it, not by reading it. Three of the
six findings have been fixed. **All six now are.** This file records what each
one was and how it was closed, so the reasoning is not lost, together with two
modelling decisions that are the owner's to take and one figure that could not
be reproduced.

Scoping rule that made the review productive, and worth reusing: this repository
documents its own weaknesses at length, so the reviewers were given the
Invariants, Known limitations and systematics-register sections first and told
to treat anything already there as out of scope. The value lay entirely in what
was absent from them.

## The six findings

1. **Optimiser start-dependence.** `portra_decompose.py` solved from one fixed
   start, so each stock reported whichever basin that start sat in. A seeded
   64-point multistart finds strictly better optima on seven of eleven stocks,
   by up to 29.5% on Ektar 100.
2. **Five checks that could not fail.** Four are now behavioural and verified to
   go red on an injected regression; the fifth, the ColorChecker harness, cannot
   be repaired and its claims were withdrawn.
3. **The print branch's accuracy figure.** It measured six-decimal write
   rounding, not lattice error. Both engines now interpolate the artifact read
   back from disk and report the two figures separately.

4. **No end-to-end error budget.** Fifteen terms bounded individually in four
   different spaces and never combined. `engine/c41/error_budget.py` now
   propagates each into dE2000 on the print output.
5. **An evidential standard applied only outward.** External sources were tiered
   A/B/C while the project's own claims carried no class, and no written
   admissibility standard existed for a datasheet.
6. **One wording trap.** A claim of byte-identity that `md5` contradicts.

The three that needed more than a sentence follow.

### 4. There is no end-to-end error budget – FIXED

Fifteen register entries bound their terms individually and none are ever
combined; the documents contain no phrase for a total. The consequence is that
the number the per-stock tables lead with, the aggregate fit RMSE at 0.008 to
0.021 D, is among the smallest terms in the chain, while basis sensitivity at
0.034 to 0.063 D and camera dependence up to 0.114 D are larger and are quoted
only as standalone diagnostics.

Two further problems sit inside this one. The sensitivity bounds are stated in
scan density, the cube's input, and the cube has a non-unit Jacobian, so the
delivered error is up to twice the quoted bound. And the several quantities all
reported as an RMSE in D are not commensurable: the aggregate fit residual is
over wavelength, the node-solve residual over the lattice, the serialisation
error an interpolation. The per-stock rankings they produce disagree with one
another.

`engine/c41/error_budget.py` now propagates every term into dE2000 on the print
output and combines them, reporting neutral and off-neutral separately because
the gray-axis lock forces the neutral axis by construction. The result is in
PROJECT.md under "End-to-end error budget". The headline: basis sensitivity
contributes 2.83 dE2000 off-neutral against the dye fit residual's 0.10, so the
figure the per-stock tables lead with is 29 times smaller than the term that
actually dominates, and every term except the basis is below 0.15.

### 5. The project holds outside sources to a standard it does not apply to itself – FIXED

`knowledge/` rated every external source A, B or C while the project's own
claims carried no equivalent class, so nothing distinguished a measured value
from a modelled or an assumed one at a glance. PROJECT.md now defines four
classes – measured, derived, assumed, unverified – and classifies its
load-bearing quantities, naming the surrogate basis, the ±25 nm bound, the 3.30
corridor and the identity DIR matrix as assumptions rather than results. It also
records where finer provenance lives, which is not where I first wrote it: the
`digitization_audit` blocks sit in the twelve `*_datasheet_curves.json` and ten
`*_spectral_sensitivity.json` files, the eleven C-41 `*_dye_density.json` carry
`fit_audit` instead, and the reversal and Vision3 dye files carry neither
because their per-layer curves are traced rather than fitted.

There was also no written admissibility standard for a datasheet: the four-step
routine is a tracing quality floor that presumes the sheet is already admitted,
and the one rejection on record existed as precedent rather than criteria.
PROJECT.md now carries five criteria ahead of the routine – vector chart
geometry, a two-curve spectral dye-density chart, three separable characteristic
curves, an axis pinnable by something other than gridline count, and a
publication code – with spectral sensitivity explicitly NOT required, since
Pro 400H ships without it. Failing the first two is fatal and is why Harman
Phoenix II was rejected.

Finally, the project's single external corroboration, that two Portra stocks
print almost identically in a darkroom and the model reproduces it, is cited in
the passage that qualifies every number in PROJECT.md without stating that both
stocks fit against an identical basis. Their convergence is therefore largely
forced by construction: the check can test the mask and the characteristic
curves, but not the dye model, which is the part in doubt.

### 6. One wording trap – FIXED

PROJECT.md stated that Fujifilm 200 and 400 are byte-identical in every shipped
artifact and that this was verified. All three cube pairs differ, in the single
header comment naming the stock, while all 274,625 values match. The claim was
true in substance and false as written, and it sent anyone checking with `md5`
after a defect that is not there – as it did me. Both places now say identical
VALUES, state that the files differ in that one comment, and say plainly that
`md5` reporting a difference is not a defect.

## Decisions deliberately not taken

These are modelling choices rather than defects, each surfaced by a fix and each
left for the owner.

- **The ±25 nm cyan shift bound – EVALUATED AND KEPT.** Refitting at ±15, ±20,
  ±25, ±35 and ±50 gives mean RMSE 0.0181, 0.0158, 0.0137, 0.0130, 0.0130 D, so
  the solve converges by ±35: releasing it buys 5% of residual and puts the
  modelled cyan peak at 721 nm. The dye arrays end at 700 nm and every stock's
  cyan is still rising there, so the bound is functioning as an extrapolation
  guard under hard constraint 1 rather than as the chemistry prior it was
  introduced as, and nothing else in the fit enforces that constraint.
  Tightening to ±20 or ±15 costs 15% and 32% and leaves the peak extrapolated
  anyway. What would actually resolve it is recovering the 717–719 nm trace the
  Fujifilm sheets publish and `GRID` discards at 700 – a digitiser change with
  an explicit invariant warning against doing it naively.
- **The `DMAX = 3.30` corridor – EVALUATED AND REJECTED.** Rebuilding at 3.30
  down to 2.40 and probing each over the same physical density range shows the
  squared-spacing law holding on the Status M cube, maximum error 0.0028 D to
  0.0012 D, and not holding at all on the print cubes, which stay flat because
  their error is dominated by the Display-P3 gamut clip. Print emulation being
  the sole delivery route, the change improves only an intermediate artifact
  already an order or two below basis sensitivity, while costing headroom
  (2.40 leaves 0.9 stop beyond the published curve on Ektar 100 and Fujicolor
  100) and breaking every node graph whose shaper was not updated in step. See
  PROJECT.md under "Corridor and LUT size are not independent parameters".

## The ensembles, and one figure that could not be reproduced

The basis-sensitivity ensembles have been regenerated across all eleven stocks
and all six surrogate bases, where previously only four stocks carried full
coverage and the stocks that pin a fit bound carried none.

**The concern that they were stale was unfounded.** Regenerating them under the
old single-start solve and under the current multistart gives the same answer to
three decimal places, so the fit change does not move basis sensitivity at all.

**The published band of 0.030 to 0.105 D could not be reproduced and has been
replaced.** It is now 0.034 to 0.063 D, re-derived by
`c41_stock_compare.py --basis-sensitivity` over all eleven stocks and the five
alternative bases, as the worst displacement of a stock's reconstructed
aggregate spectral density when the assumed basis is swapped. The metric is the
symmetric shape residual the inter-stock distances already use, which is what
makes the two directly comparable; measuring the band with a different metric
from the distances it bounds was the original defect.

The hypothesis offered for the discrepancy was that the published figure
spanned a wider set of basis variants, since `b25`, `hyb` and `shift25` survive
in the ensemble directory and are not among the current `--basis` choices.
**That is refuted**: including all three leaves the band unchanged at 0.034 to
0.063 D, and `b25` is byte-identical to the canonical fit. Roughly two dozen
further candidate definitions were tried, in dye space and in cube space under
four domain masks, and none reproduces the published band.

The correction changes a headline conclusion. Against inter-stock distances of
0.024 to 0.220 D, the old figure put 43 of the 55 pairs inside the ambiguity
band, which supported the claim that the ranges overlapped for most of the
fleet. The re-derived figure puts 17 of 55 inside it, so most pairs are in fact
separable and the documents have been corrected to say so. The output-space
figure in the error budget does not depend on the band, being propagated from
the refits directly.

Two defects surfaced while re-deriving it, both since addressed. The fitter
hardcoded Vision3 in three metadata fields, so an ensemble fit against any other
basis still described itself as Vision3 and the recorded provenance could not
tell one fit from another. Each field now names the basis actually used, and the
sixty-six fits that the current `--basis` choices can produce were regenerated
with no numeric change; the canonical files are byte-identical, the wording for
Vision3 being unchanged by construction. The eighteen fits under the retired
`b25`, `hyb` and `shift25` variants are not `--basis` choices and cannot be
regenerated, so their recorded basis remains unreliable. `b25` in any case
duplicates the canonical fit exactly and contributes nothing as an
alternative.
