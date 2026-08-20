# The orange mask: mechanism, and its consequences for this pipeline

Collected 2026-07-26. Companion to
`interimage-effects-and-stock-differentiation.md`. The motivation was that this
project subtracts a per-roll D-min triplet as its mask removal, in
`dctl/prep/RollAnchor_ScanPrep.dctl`, and re-adds a spectral D-min inside the
print engine, while nothing in the repository documented what the mask *is* or
whether those two treatments are correct.

**Headline finding: the orange mask is a positive image that varies inversely
with the negative image, and it is not a filter.** Everything downstream
follows from that property, and it is the one property that a constant D-min
subtraction cannot represent.

> **Note on scope.** The mechanism and literature below stand as collected. The
> pipeline analysis in §5 has since been superseded by a more careful treatment
> in PROJECT.md's bounded systematics register, which is authoritative. The
> revisions are marked in place.

---

## 0. Provenance and confidence

The tiering matches that of the interimage note.

| Tier | Source | Status |
|---|---|---|
| **A, verified primary** | W. T. Hanson, "Color Correction with Colored Couplers", *JOSA* **40**(3):166–171 (1950), the foundational paper. The abstract was fetched and read; the full text was not retrieved. Also the masking-coupler patents US4749641, US6132943, US6010839, US4036646 and US5972585 | Quoted claims below come from fetched text |
| **B, manufacturer and practitioner technical** | Scanning references, RA-4 practice | Reliable on practice, and not on mechanism |
| **C, UNVERIFIED expert testimony** | Photrio posts by "Photo Engineer", that is, Ron Mowrey, a retired Kodak emulsion engineer | **photrio.com returns HTTP 403 to automated fetching.** All Photo Engineer material below is search-snippet PARAPHRASE rather than verbatim. Use it for direction only, never for coefficients. |

---

## 1. The nature of the mask (tiers A and C)

The mask is **neither a separate coating nor a dye layer**. It is the *colour of
the couplers themselves*. Per Photo Engineer, at tier C, the mask "is NOT a
coating of its own, but a specific characteristic of coupler layers, more
precisely of couplers themselves", and the orange colour seen on a clear
processed frame is "unexposed, undeveloped dye coupler".

Its purpose is to cancel the **unwanted side absorptions** of the image dyes.
Real cyan and magenta dyes are impure: the cyan dye absorbs some green and blue
light, and the magenta absorbs some blue. Those impurities would otherwise
print as saturation and hue errors that no amount of printing filtration can
correct, because they vary *with the image*.

Hanson's insight, at tier A and taken from the fetched abstract, is that the
coupler's colour is destroyed during development, so that a colour-negative
frame carries **two superimposed images**:

- a **negative** image composed of developed dye, and
- a **positive** image composed of *unused* coupler.

The effect of overlapping dye absorptions "can be eliminated by the use of
colored couplers" possessing the appropriate spectra. Hanson explicitly frames
this as filling the role of "the six masks which are found to be required by a
number of the theoretical treatments of the problem of exact colour
reproduction". The correction is therefore exact in principle rather than
approximate.

## 2. The property that matters: the mask is image-wise (tier A)

From the masking-coupler patent literature, closely paraphrasing the fetched
text:

> "The colour of the masking coupler is destroyed in the areas of the image
> where the dye with unwanted side absorptions is formed."

> masking couplers "provide optical density of a colour which varies in
> proportion to the level of exposure to offset an undesired side absorption of
> an image dye formed during development"

and, concretely, masking-coupler examples show **high blue density at minimum
exposure and low blue density at maximum exposure**, the coated yellow colour
being "destroyed imagewise".

The mask is consequently at its **maximum in unexposed areas, that is at D-min,
and is progressively consumed as dye forms**. The loss of the mask's blue
absorption is designed to balance exactly the gain in blue absorption arising
from the magenta dye's side absorption. Both terms track the image, which is
why the cancellation holds at every density rather than at one point only.

**Consequence: the instruction to "subtract the orange mask" is a category
error if taken literally.** There is no constant orange to remove. Subtracting
D-min removes the mask *at its maximum*, which is correct only in the clear
base.

## 3. Consequences for scanning (tier B)

- The mask absorbs strongly in blue and weakly in red. Scanners compensate with
  a much longer blue exposure, one reference giving blue at approximately 3.5
  times and green at approximately 2.5 times the red exposure time. This is why
  blue is the noisiest channel in negative scans: it is the most attenuated
  before it reaches the sensor.
- Anchoring operates on camera-linear scanner data, ahead of the pre-shaper's
  logarithm. Subtracting a D-min triplet in density is exactly a per-channel
  multiplication in linear space, and `RollAnchor_ScanPrep.dctl` implements it
  as such, multiplying each channel by `10^Dmin`. **This is the correct
  operation.** The two forms are one operation and not a choice between them:
  the failure mode the literature warns of is not the linear form but its
  application as a single flat adjustment, treated in the following bullet.
- A known practitioner failure mode is the application of mask correction as a
  *single flat adjustment* rather than per channel, which produces colour
  crossover because mask density is not uniform across the tonal range. This is
  the practical shadow of §2.
- D-min varies from roll to roll with processing, which is why anchoring per
  roll, as this project does, is correct rather than fastidious.

## 4. Consequences for RA-4 paper (tiers B and C)

RA-4 paper is *designed around* the mask, its layer sensitivities assuming a
masked negative. Practitioners note that when printing from **unmasked** film
it can be preferable to add an orange filter rather than to dial the colour
head, precisely because the paper expects that spectral pedestal. This matters
here: the print engine must present the paper with a masked negative rather
than a bare dye stack.

## 4a. How much the mask varies between stocks (measured 2026-08-16)

The sections above treat the mask as a mechanism common to colour negative film.
Its strength is not common. Measured from the ten stocks' published D-min
spectra as blue density minus red density, that is D-min at 440 nm less D-min at
650 nm, the fleet spans **0.6005 D on Fujicolor 100 to 0.9467 D on Fujifilm 200
and 400**, a spread of **0.346 D**, and the ratio (B−R)/(G−R) varies from 1.414
to 2.049, so the mask differs in spectral shape as well as in magnitude.

For scale, the fitted dye sets of the same eleven stocks differ by
0.024–0.220 D
and the basis prior contributes 0.034–0.063 D. **The mask is the largest
basis-independent difference between these stocks that this project has
measured.** Bergthaller (2002) supplies a mechanism to expect it, since
pyrazolotriazole magenta couplers have negligible unwanted blue absorption and
correspondingly need less yellow masking coupler than pyrazolone couplers.

That variation has been traced through the print engine and it does reach the
cubes, but only away from the grey axis. The gray-axis lock holds neutrals to
within 0.114 ΔE2000 for every stock pair tested, while 10–16% of cube nodes
differ by more than 1 ΔE2000 and saturated colours by as much as 4.5. The driver
is the mask's spectral SHAPE rather than its strength: a pair differing by
0.009 D in strength but substantially in shape moves the cube further than a
pair differing by 0.173 D in strength with no shape change. Full method, the
per-stock table and the null control are in
`dye-sets-across-the-three-processes.md` §4f and §4f-bis; the consequences for
the discrimination gap are recorded in PROJECT.md.

Note the scope of that experiment against §5b below: it swaps a **D-min**, which
is the mask at its maximum. It says nothing about how the mask is consumed as
dye forms, which remains the open off-axis systematic.

## 5. Where this affects the pipeline: the original analysis

Three places, with different verdicts.

### 5a. Scan to Status M cube: the error CANCELS

The chain subtracts a per-roll D-min from the scan, and the datasheet
decomposition subtracts the datasheet D-min from midscale-neutral. Writing the
mask as `m(x)`, with maximum `m₀` at D-min:

```
scanned, D-min-subtracted   = dye(x) + m(x) − m₀  = dye(x) − consumed(x)
datasheet mid-minus-D-min   = dye     + m_mid − m₀ = dye − consumed
```

Both sides are the **same effective quantity**, namely image dye minus consumed
mask. The fitted dyes are therefore *effective* dyes, and they are applied to
data carrying the identical convention. **The approximation cancels between
calibration and application.** This is a real and reassuring result: it means
the Status M cube is not silently wrong, and it explains why the neutral axis
emerges exact.

Caveat: the cancellation is exact only at the density at which the datasheet's
midscale sits, and approximate elsewhere, since `consumed(x)` is a function of
density while the fit had one sample of it.

### 5b. Print emulation: SUPERSEDED by the register

The analysis originally recorded here held that `endura_print_engine.py`
re-adds the datasheet D-min spectrum, that is, the mask at its maximum,
uniformly at every node, and that the engine therefore over-applies mask in
dense areas with an error growing with density.

**That conclusion is withdrawn.** The engine builds the negative as
`N(λ) = dmin_spec(λ) + Σ_layer dye_neg · DYE_neg(λ)`, which is exact along the
neutral axis: `dye = 0` returns exactly D-min, that is, the full mask, and the
midscale dye amounts return exactly the measured midscale. Since mask
consumption is linear in the dye formed, the interpolation between those
endpoints is correct as well. The engine does not re-add the mask at its
maximum uniformly.

The real systematic is **off-axis mis-attribution**: each fitted per-layer
curve carries a share of mask consumption apportioned as it was at the neutral
ratio, that being the only ratio the datasheet publishes. At saturated colours
the dye ratios depart from neutral and the per-layer split of the consumed mask
is wrong. The expected residual is a chroma-dependent colour drift, zero on the
gray axis by construction and growing with saturation.

**This systematic is recorded in PROJECT.md's bounded systematics register**,
which supersedes the note originally made here that it was absent from the
register.

### 5c. The dye decomposition: UNRESOLVED, although narrower in scope than it first appears

If `mid − D-min` equals `dye − consumed`, the decomposition would be fitting
effective dyes whose shapes are distorted by the mask-consumption spectrum,
which is orange and therefore blue-absorbing. A natural hypothesis was that
this contributes to stocks pinning the cyan shift bound.

**An important mitigating fact is that the Vision3 basis is itself D-min
subtracted.** `data/films/Vision3_dye_density.json` states this outright, its
`units` field reading "relative diffuse spectral density (Status M, D-min
subtracted)". Basis and target therefore share one convention, rather than pure
dye shapes being fitted to a mask-contaminated target. Whatever mask term
survives D-min subtraction is present on both sides of the fit and, to first
order, cancels in the same way as in §5a.

What is *not* established is whether Kodak's published per-layer Vision3 curves
were themselves measured on exposures in which that layer's masking coupler had
been consumed. If they were, the conventions match closely and the question
does not arise. If the per-layer curves are effectively pure-dye measurements,
a second-order mismatch remains. The datasheets are silent, so this should be
treated as open rather than resolved, without being over-weighted: the
first-order term cancels.

**Tested, result INCONCLUSIVE.** A short-wavelength signature was sought in the
decomposition residual `aggregate − fit`, by band:

| stock | blue (<500 nm) | red (≥600 nm) | blue − red |
|---|---|---|---|
| Portra 400 | +0.0011 | +0.0020 | −0.0009 |
| Portra 160 | +0.0005 | +0.0029 | −0.0024 |
| Ektar 100 | −0.0002 | +0.0016 | −0.0017 |

No meaningful blue bias appears. **This does not clear the hypothesis**,
because the fit has nine free parameters including per-dye peak shift and
width: a smooth spectral bias such as mask consumption is exactly the kind of
structure it would absorb *into the fitted shapes* rather than leave in the
residual. A small residual is therefore consistent both with the absence of a
mask artefact and with a mask artefact fully absorbed into the dyes. The test
cannot separate the two.

Note that the cyan shift bound is a uniform ±25 nm across all ten stocks, under
which only Fujifilm 400 and 200 pin it. The pinning originally cited here as
evidence was an artefact of the retired ±15 nm bound. Three further stocks pin a
width bound instead, so five of the ten fit against a bound of one kind or
another. See register entry 12 in PROJECT.md.

## 6. What would settle the question

- **Kodak does not publish the mask separately.** The datasheet gives D-min and
  midscale-neutral spectral density, and neither isolates `consumed(x)`. The
  question therefore cannot be resolved from the available datasheets.
- A **spectral density series at several exposure levels** on one stock gives
  `consumed(x)` summed over the layers, the mask's contribution being the part
  that *decreases* with exposure while the dyes increase. Two levels, D-min and
  midscale, provide one constraint, whereas the shape requires more.
- **A neutral series alone cannot close the §5b defect**, which is a per-layer
  attribution off the neutral axis. That is measured rather than argued: a free
  parameter subtracting a multiple of the stock's own D-min improves the
  aggregate fit by 18–25%, but a flat vector, meaningless as a mask, fits
  better on every Kodak stock, so the diagnostic fails its own control.
  Off-neutral R/G/B separation exposures are required as well.
- The validation roll specification carries both requirements. It calls for the
  patches to be read **spectrally over 380–730 nm at not fewer than three
  exposure levels**, and it names this systematic as one of the two register
  items that reading closes. One shoot serves both purposes. See PROJECT.md,
  Known limitations.
- Until that roll is exposed and measured, the off-axis mis-attribution
  described in §5b stands as a known and unquantified print-branch systematic.

## 7. Open questions and material not found

- No verbatim Photo Engineer text, the server returning 403. The most relevant
  threads are "Orange mask" (132030), "Orange Mask on RA4 paper" (149017) and
  "How do scanners color correct C-41 negatives?" (169634).
- The full text of Hanson 1950 was not retrieved, only the abstract. The
  six-mask theoretical framing it references is likely worth reading properly
  should an exact-correction formulation ever be attempted.
- No published per-stock mask-consumption curves for Portra or Ektar were
  found.
- Whether Kodak's published per-layer Vision3 dye curves were measured with
  that layer's masking coupler consumed is not stated on the datasheet. That is
  the one fact which would close out §5c.

## Sources

- W. T. Hanson, "Color Correction with Colored Couplers", JOSA 40(3):166–171 (1950) – https://opg.optica.org/josa/abstract.cfm?uri=josa-40-3-166 (tier A, abstract fetched)
- US4749641, "Imaging element containing dye masking coupler" – https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/4749641
- US6132943 / US6010839, yellow-coloured magenta dye-forming masking couplers – https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/6132943
- US4036646, "Color correction of unwanted side densities" – https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/4036646
- US5972585, "Color negatives adapted for visual inspection" – https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/5972585
- Photrio "Orange mask", thread 132030 – https://www.photrio.com/forum/threads/orange-mask.132030/ (tier C, NOT fetched, 403)
- Photrio "Orange Mask on RA4 paper", thread 149017 – https://www.photrio.com/forum/threads/orange-mask-on-ra4-paper.149017/ (tier C, NOT fetched, 403)
- Photrio "How do scanners color correct C-41 negatives?", thread 169634 – https://www.photrio.com/forum/threads/how-do-scanners-color-correct-c-41-negatives.169634/ (tier C, NOT fetched, 403)
- scantips.com, processing scanned colour negatives – https://www.scantips.com/colornegs.html (tier B)
- P. Bergthaller, "Couplers in colour photography – chemistry and function, Part 2", *The Imaging Science Journal* 50(3):187–230, 2002, on masking couplers and on pyrazolotriazole magenta making them dispensable (tier A, obtained; see `dye-sets-across-the-three-processes.md`)
