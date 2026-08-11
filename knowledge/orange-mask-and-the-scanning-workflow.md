# The orange mask: mechanism, and where it bites in this pipeline

Collected 2026-07-26. Companion to
`interimage-effects-and-stock-differentiation.md`. Motivation: this project
subtracts a per-roll D-min triplet as its mask removal
(`dctl/prep/RollAnchor_ScanPrep.dctl`) and re-adds a spectral D-min inside the
print engine, but nothing in the repo actually documents what the mask *is* or
whether those two treatments are correct.

**Headline finding: the orange mask is not a filter. It is a positive image that
varies inversely with the negative image.** Everything downstream follows from
that, and it is the one property a constant D-min subtraction cannot represent.

---

## 0. Provenance and confidence

Same tiering as the interimage doc.

| Tier | Source | Status |
|---|---|---|
| **A — verified primary** | W. T. Hanson, "Color Correction with Colored Couplers", *JOSA* **40**(3):166–171 (1950) — the foundational paper. Abstract fetched and read; full text not retrieved. Plus masking-coupler patents (US4749641, US6132943, US6010839, US4036646, US5972585) | Quoted claims below are from fetched text |
| **B — manufacturer / practitioner technical** | Scanning references, RA-4 practice | Reliable on practice, not on mechanism |
| **C — UNVERIFIED expert testimony** | Photrio posts by "Photo Engineer" (Ron Mowrey, retired Kodak emulsion engineer) | **photrio.com returns HTTP 403 to automated fetching.** All PE material below is search-snippet PARAPHRASE, not verbatim. Direction only, never coefficients. |

---

## 1. What the mask is (tier A + C)

It is **not a separate coating and not a dye layer**. It is the *colour of the
couplers themselves*. Per PE (tier C): the mask "is NOT a coating of its own, but
a specific characteristic of coupler layers, more precisely of couplers
themselves"; the orange colour seen on a clear processed frame is "unexposed,
undeveloped dye coupler".

Its purpose is to cancel the **unwanted side absorptions** of the image dyes. Real
cyan and magenta dyes are impure — the cyan dye absorbs some green and blue, the
magenta absorbs some blue. Those impurities would otherwise print as a
saturation- and hue-error that no amount of printing filtration can fix, because
they vary *with the image*.

Hanson's insight (tier A, from the fetched abstract): during development the
coupler's colour is destroyed, so a colour-negative frame carries **two
superimposed images** —

- a **negative** image made of developed dye, and
- a **positive** image made of *unused* coupler.

and the effect of overlapping dye absorptions "can be eliminated by the use of
colored couplers" with the right spectra. Hanson explicitly frames this as
filling the role of "the six masks which are found to be required by a number of
the theoretical treatments of the problem of exact colour reproduction". So the
correction is, in principle, **exact** — not a fudge.

## 2. The property that matters: it is image-wise (tier A)

From the masking-coupler patent literature, verbatim-adjacent:

> "The colour of the masking coupler is destroyed in the areas of the image where
> the dye with unwanted side absorptions is formed."

> masking couplers "provide optical density of a colour which varies in
> proportion to the level of exposure to offset an undesired side absorption of
> an image dye formed during development"

and, concretely, masking-coupler examples show **high blue density at minimum
exposure and low blue density at maximum exposure** — the coated yellow colour is
"destroyed imagewise".

So the mask is at its **maximum in unexposed areas (D-min) and progressively
consumed as dye forms**. The loss of the mask's blue absorption is designed to
exactly balance the gain in blue absorption from the magenta dye's side
absorption. Both terms track the image, which is why the cancellation works at
every density rather than only at one point.

**Consequence: "subtract the orange mask" is a category error if taken
literally.** There is no constant orange to remove. Subtracting D-min removes the
mask *at its maximum*, which is correct only in the clear base.

## 3. Consequences for scanning (tier B)

- The mask absorbs strongly in blue, weakly in red. Scanners compensate with much
  longer blue exposure — one reference gives blue ≈3.5× and green ≈2.5× the red
  exposure time. That is why blue is the noisiest channel in negative scans: it
  is the most attenuated before it ever reaches the sensor.
- Because we work in **density (log) space**, subtracting a D-min triplet is
  equivalent to a per-channel linear gain — the noise-cheap operation. Doing the
  same correction as a division in linear space amplifies noise where signal is
  lowest. Our `RollAnchor_ScanPrep.dctl` multiplies linear by `10^Dmin`, i.e. it
  is the density-domain subtraction. **This is the right operation.**
- A known practitioner failure mode: applying mask correction as a *single flat
  adjustment* rather than per channel produces colour crossover, because mask
  density is not uniform across the tonal range. This is the practical shadow of
  §2.
- D-min varies roll to roll with processing, which is why anchoring per roll (as
  this project does) is correct rather than fussy.

## 4. Consequences for RA-4 paper (tier B/C)

RA-4 paper is *designed around* the mask — its layer sensitivities assume a
masked negative. Practitioners note that when printing from **unmasked** film it
can be better to add an orange filter than to dial the colour head, precisely
because the paper expects that spectral pedestal. This matters for us: the print
engine must present the paper with a masked negative, not a bare dye stack.

## 5. WHERE THIS BITES IN OUR PIPELINE — original analysis

Three places, with different verdicts.

### 5a. Scan → Status M cube — the error CANCELS

Our chain subtracts a per-roll D-min from the scan. The datasheet decomposition
subtracts the datasheet D-min from midscale-neutral. Writing the mask as `m(x)`
with maximum `m₀` at D-min:

```
scanned, D-min-subtracted   = dye(x) + m(x) − m₀  = dye(x) − consumed(x)
datasheet mid-minus-D-min   = dye     + m_mid − m₀ = dye − consumed
```

Both sides are the **same effective quantity**: image dye minus consumed mask.
The fitted "dyes" are therefore *effective* dyes, and they are applied to data
carrying the identical convention. **The approximation cancels between
calibration and application.** This is a real and reassuring result — it means
the Status M cube is not silently wrong, and it explains why the neutral axis
comes out exact.

Caveat: it cancels *exactly* only at the density where the datasheet's midscale
sits, and *approximately* elsewhere, since `consumed(x)` is a function of
density while the fit had one sample of it.

### 5b. Print emulation — the error does NOT cancel

`endura_print_engine.py` builds the negative as

```
N(λ) = dmin_spec(λ) + Σ_layer dye_neg · DYE_neg(λ)
```

i.e. it re-adds the datasheet's **D-min spectrum — the mask at its MAXIMUM —
uniformly at every node**, then prints through it. But a real negative has less
mask exactly where it has more dye. So the engine over-applies mask in dense
(highlight-of-scene) areas, and the error grows with density.

Partially mitigating: the auto-solved printer-light offsets and the gray-axis
lock absorb the *average* mask as a per-channel constant — which is precisely
what printer lights correct in a real enlarger. What they cannot absorb is the
*variation*. So the expected residual is a density-dependent colour drift, small
near the calibration anchor (k≈0.22) and growing toward the ends of the printable
window.

**This is a systematic in the print branch.** It is not in the register. It
should be.

### 5c. The dye decomposition — status UNRESOLVED, but LESS alarming than it looks

If `mid − D-min` is `dye − consumed`, the decomposition would be fitting
effective dyes whose shapes are distorted by the mask-consumption spectrum
(orange, i.e. blue-absorbing) — and a natural hypothesis is that this is part of
why **all three stocks pin the +15 nm cyan shift bound**.

**Important mitigating fact: the Vision3 basis is itself D-min subtracted.**
`data/films/Vision3_dye_density.json` states it outright —
`units: "relative diffuse spectral density (Status M, D-min subtracted)"`. So
basis and target are in the *same* convention, rather than pure-dye shapes being
fitted to a mask-contaminated target. Whatever mask term survives D-min
subtraction is present on both sides of the fit, and to first order it cancels
the same way §5a cancels.

What is *not* established is whether Kodak's published per-layer Vision3 curves
were themselves measured on exposures where that layer's masking coupler had been
consumed. If yes, the conventions match closely and this is a non-issue. If the
per-layer curves are effectively pure-dye measurements, a second-order mismatch
remains. The datasheets do not say, so treat this as open rather than resolved —
but do not over-weight it: the first-order term cancels.

**Tested, result INCONCLUSIVE.** I looked for a short-wavelength
signature in the decomposition residual `aggregate − fit`, by band:

| stock | blue (<500 nm) | red (≥600 nm) | blue − red |
|---|---|---|---|
| Portra 400 | +0.0011 | +0.0020 | −0.0009 |
| Portra 160 | +0.0005 | +0.0029 | −0.0024 |
| Ektar 100 | −0.0002 | +0.0016 | −0.0017 |

No meaningful blue bias. **But this does not clear the hypothesis**, because the
fit has 9 free parameters including per-dye peak shift and width: a smooth
spectral bias like mask consumption is exactly the kind of thing it would absorb
*into the fitted shapes* rather than leave in the residual. A small residual is
therefore consistent with both "no mask artifact" and "mask artifact fully
absorbed into the dyes". The test cannot separate them.

## 6. What would actually settle it

- **Kodak does not publish the mask separately.** The datasheet gives D-min and
  midscale-neutral spectral density; neither isolates `consumed(x)`. So this
  cannot be resolved from the datasheets we have.
- The clean measurement is a **spectral density series at several exposure
  levels** on one stock — the mask's contribution is the part that *decreases*
  with exposure while the dyes increase. Two levels (D-min + midscale) is one
  constraint; the shape needs more.
- The already-planned validation roll could supply this cheaply: it will have a
  gray ramp anyway. Reading **spectral** (not just Status M) density at several
  ramp steps would give `consumed(x)` directly. Worth adding to the roll spec
  alongside the R/G/B separation wedges already added for interimage.
- Until then, §5b stands as a known, unquantified print-branch systematic.

## 7. Open / not found

- No verbatim PE text (403). Most relevant threads: "Orange mask" (132030),
  "Orange Mask on RA4 paper" (149017), "How do scanners color correct C-41
  negatives?" (169634).
- Hanson 1950 full text not retrieved — only the abstract. The six-mask
  theoretical framing it references is likely worth reading properly if we ever
  attempt an exact-correction formulation.
- No published per-stock mask-consumption curves for Portra or Ektar were found.
- Whether Kodak's published per-layer Vision3 dye curves were measured with that
  layer's masking coupler consumed is not stated on the datasheet. That is the
  one fact which would close out §5c.

## Sources

- W. T. Hanson, "Color Correction with Colored Couplers", JOSA 40(3):166–171 (1950) — https://opg.optica.org/josa/abstract.cfm?uri=josa-40-3-166 (tier A, abstract fetched)
- US4749641, "Imaging element containing dye masking coupler" — https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/4749641
- US6132943 / US6010839, yellow-coloured magenta dye-forming masking couplers — https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/6132943
- US4036646, "Color correction of unwanted side densities" — https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/4036646
- US5972585, "Color negatives adapted for visual inspection" — https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/5972585
- Photrio "Orange mask", thread 132030 — https://www.photrio.com/forum/threads/orange-mask.132030/ (tier C, NOT fetched, 403)
- Photrio "Orange Mask on RA4 paper", thread 149017 — https://www.photrio.com/forum/threads/orange-mask-on-ra4-paper.149017/ (tier C, NOT fetched, 403)
- Photrio "How do scanners color correct C-41 negatives?", thread 169634 — https://www.photrio.com/forum/threads/how-do-scanners-color-correct-c-41-negatives.169634/ (tier C, NOT fetched, 403)
- scantips.com, processing scanned colour negatives — https://www.scantips.com/colornegs.html (tier B)
