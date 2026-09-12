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
| :--- | :--- | :--- |
| **A, verified primary** | W. T. Hanson, "Color Correction with Colored Couplers", *JOSA* **40**(3):166–171 (1950), the foundational paper. The abstract was fetched and read; the full text was not retrieved. Also the masking-coupler patents US4749641, US6132943, US6010839, US4036646 and US5972585 | Quoted claims below come from fetched text |
| **B, manufacturer and practitioner technical** | Scanning references, RA-4 practice | Reliable on practice, and not on mechanism |
| **C, UNVERIFIED expert testimony** | Photrio posts by "Photo Engineer", that is, Ron Mowrey, a retired Kodak emulsion engineer | **photrio.com returns HTTP 403 to automated fetching.** All Photo Engineer material below is search-snippet PARAPHRASE. Use it for direction only, never for coefficients. |

---

## 1. The nature of the mask (tiers A and C)

The mask is **neither a separate coating nor a dye layer**. It is the *colour of
the couplers themselves*. Photo Engineer's account, at tier C and reaching this
note only as search-snippet paraphrase, is that the mask is not a coating of
its own but a characteristic of the coupler layers, of the couplers themselves,
and that the orange colour seen on a clear processed frame is unexposed,
undeveloped dye coupler.

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
reproduction".

This describes an ideal correction mechanism; it is no evidence that a current
stock or this project achieves exact cancellation.

---

## 2. The property that matters: the mask is image-wise (tier A)

The masking-coupler patent literature listed in §0 (US4749641, US6132943,
US6010839, US4036646, US5972585) was fetched, and the statements below are
attributed paraphrase of it: no passage has been
verified word for word against a named patent and page, so none is set in
quotation marks.

- The colour of the masking coupler is destroyed in the areas of the image
  where the dye with unwanted side absorptions is formed.
- A masking coupler provides an optical density of a colour that varies with
  the level of exposure, so as to offset an undesired side absorption of an
  image dye formed during development.
- The worked examples show high blue density at minimum exposure and low blue
  density at maximum exposure, the coated yellow colour being destroyed
  imagewise.

The mask is consequently at its **maximum in unexposed areas, that is at D-min,
and is progressively consumed as dye forms**.

Coloured couplers are designed so that the loss of the mask's blue absorption
offsets the gain in blue absorption from the magenta dye's side absorption, both
terms tracking the image; that is the design intent, an ideal mechanism as §1
states. The extent of that compensation in any current stock is not established
here.

**Consequence: the instruction to "subtract the orange mask" is a category
error if taken literally.** There is no constant orange to remove. Subtracting
D-min removes the mask *at its maximum*, which is correct only in the clear
base.

---

## 3. Consequences for scanning (tier B)

- The mask absorbs strongly in blue and weakly in red. Scanners compensate with
  a much longer blue exposure; the scantips.com reference (tier B) gives blue at
  approximately 3.5 times and green at approximately 2.5 times the red exposure
  time for its own scanner, and the figures belong to that apparatus and light
  source alone. Under otherwise equal conditions the
  attenuation gives blue an exposure and signal-to-noise disadvantage; whether
  blue ends up the noisiest channel of a given scan depends on the exposure
  times, LED powers and sensor response actually used.

- Anchoring operates on camera-linear scanner data, ahead of the pre-shaper's
  logarithm. Subtracting a D-min triplet in density is exactly a per-channel
  multiplication in linear space, and `RollAnchor_ScanPrep.dctl` implements it
  as such, multiplying each channel by `10^Dmin`. **This is the correct
  operation.** The two forms are one operation:
  the failure mode the literature warns of is the linear form's
  application as a single flat adjustment, treated in the following bullet.
  What the operation subtracts is an INTEGRATED density, the base and mask as
  one LED reads them, and the calibration side has to match that: the C-41
  engines integrate each LED behind the stock's D-min spectrum, never
  behind the bare LED (PROJECT.md register #17; `reading-datasheet-charts.md`
  §4).

- A known practitioner failure mode is the application of mask correction as a
  single COMMON gain across the three channels, or as one density offset;
  those are different operations from three per-channel gains, and
  the per-channel anchoring above is the one endorsed here. Practitioners
  report colour crossover from the flat forms. Note that a per-channel gain is
  still a constant, and §2 says the mask is not: what a per-channel anchor
  cannot represent is the mask's consumption with density, which is the
  register's open systematic; the anchor itself causes no crossover.

- D-min varies from roll to roll with processing, which is why anchoring per
  roll, as this project does, is correct.

---

## 4. Consequences for RA-4 paper (tiers B and C)

RA-4 paper is *designed around* the mask, its layer sensitivities assuming a
masked negative. Practitioners note that when printing from **unmasked** film
it can be preferable to add an orange filter in place of dialling the colour
head, precisely because the paper expects that spectral pedestal. This matters
here: the print engine must present the paper with a masked negative, mask
included.

### 4a. How much the mask varies between stocks (measured 2026-08-23)

The sections above treat the mask as a mechanism common to colour negative film.
Its strength is not common. Measured from the twelve stocks' published D-min
spectra as blue density minus red density, that is D-min at 440 nm less D-min at
650 nm, the fleet spans **0.6005 D on Fujicolor 100 to 0.9467 D on Fujifilm 200
and 400**, a spread of **0.346 D**, and the ratio (B−R)/(G−R) varies from 1.450
to 2.117, so the mask differs in spectral shape as well as in magnitude.

For scale, the fitted dye sets of the same twelve stocks differ by
0.021–0.219 D
and the basis prior contributes 0.032–0.063 D. **The traced D-min spectra are a
stock-dependent input independent of the surrogate dye fit, and their proxy
varies substantially across the fleet.** Those figures are different
observables over different populations, so no ranking of the mask against the
dye-set differences follows from them; a ranking would need one output metric
on one patch population (dye note §4f).

Bergthaller (2002) supplies a
mechanism to expect the variation, since
pyrazolotriazole magenta couplers have negligible unwanted blue absorption and
correspondingly need less yellow masking coupler than pyrazolone couplers.

That variation has been traced through the print engine and it does reach the
cubes, but only away from the grey axis.

In the mask-swap experiment of
`dye-sets-across-the-three-processes.md` §4f-bis (four pairs, a 25³ grid of
15 625 nodes per pair, evaluated in linear P3 and ΔE2000), the gray-axis lock,
a per-channel intensity-dependent calibration of the model and not a stand-in
for fixed printer-light balancing (dye note §4f),
holds the grey ramp to within 0.131 ΔE2000 on every pair, while 1.2–20.4% of
nodes differ by more than 1 ΔE2000 (12.7–20.4% on the three pairs with a shape
change) and saturated colours by as much as 5.50 on the extreme Fujicolor 100 →
Fujifilm 400 pair.

The contrast between the two diagnostic pairs points to the mask's spectral
SHAPE: a pair differing by 0.009 D in strength but substantially in the
three-wavelength shape ratio moves the cube further than a pair differing by
0.173 D in strength with no ratio change, though the two pairs sit on different
stock backgrounds and the ratio is three wavelengths, so this is indicative
only. Full method, the per-stock table and the null control are in that note;
the consequences for the discrimination gap are recorded in PROJECT.md.

Note the scope of that experiment against §5b below: it swaps a **D-min**, which
is the mask at its maximum. It says nothing about how the mask is consumed as
dye forms, which remains the open off-axis systematic.

---

## 5. Where this affects the pipeline: the original analysis

Three places, with different verdicts.

### 5a. Scan to Status M cube: matching effective-density conventions

The chain subtracts a per-roll D-min from the scan, and the datasheet
decomposition subtracts the datasheet D-min from midscale-neutral. Writing the
mask as `m(x)`, with maximum `m₀` at D-min:

```text
scanned, D-min-subtracted   = dye(x) + m(x) − m₀  = dye(x) − consumed(x)
datasheet mid-minus-D-min   = dye     + m_mid − m₀ = dye − consumed
```

Both sides are the **same effective quantity**, namely image dye minus consumed
mask. The fitted dyes are therefore *effective* dyes, and they are applied to
data carrying the identical convention. **The convention cancels between
calibration and application.** This is a real and reassuring result: it means
the Status M cube carries no convention mismatch, and it is why the neutral
axis closes to machine precision, which is an algebraic identity of the model
and not a statement that the reconstructed spectrum is physically exact
(§5b).

The midscale spectrum is fitted with nonzero residual, and other exposure
levels are not independently established by that single spectrum. Any numerical
neutral lock is distinct from physical spectral exactness.

**Revised 2026-09-02 (PROJECT.md register #17).** The convention argument
above survives: the fitted dyes are effective dyes, dye minus consumed mask, and
the scan carries the same convention. What it glossed over is the SPACE in which
each side subtracts. The datasheet subtracts D-min spectrally, wavelength by
wavelength; the roll anchor subtracts it in integrated density, one number per
LED, which is the LED's reading of the dyes through the mask, `Φ·10^−Dmin(λ)`.
The two agree only where the mask is flat across an LED's band, and it is not:
Portra 400's D-min falls 0.11 D across the green LED's FWHM. Modelling the
scan side with the bare LED read a midscale Portra 400 neutral 0.056 D low in
green (*measured here*). The Status M engines therefore integrate the
mask-filtered illuminant, and the cancellation claimed in this section holds
for the convention alone.

### 5b. Print emulation: SUPERSEDED by the register

The analysis originally recorded here held that `endura_print_engine.py`
re-adds the datasheet D-min spectrum, that is, the mask at its maximum,
uniformly at every node, and that the engine therefore over-applies mask in
dense areas with an error growing with density.

**That conclusion is withdrawn.** The engine builds the negative as
`N(λ) = dmin_spec(λ) + Σ_layer dye_neg · DYE_neg(λ)`. Three different kinds
of statement about that construction need keeping apart.

- **Algebraic identity:** `dye = 0` returns D-min exactly, the full mask.
- **Numerical calibration within the model:** the midscale dye amounts return
  the fitted midscale, whose disagreement with the measured midscale is the
  aggregate fit residual, RMSE 0.0108 D for Portra 400 (`fit_audit`).
- **Physical approximation:** the interpolation between those two points assumes
  fixed effective dye spectra and mask consumption linear in the dye formed,
  and one midscale spectrum measures neither how each layer's effective
  spectrum nor how the amount ratios evolve over an exposure series; the
  gray-axis lock forces the engine's output neutral curve onto its target,
  which is a different thing from the reconstructed film spectrum being exact at
  every neutral exposure.

Those assumptions stand subject to the register's existing bounds. The engine
does not re-add the mask at its maximum uniformly.

The real systematic is **off-axis mis-attribution**: each fitted per-layer
curve carries a share of mask consumption apportioned as it was at the neutral
ratio, that being the only ratio the datasheet publishes.

Fitting one neutral aggregate leaves the off-neutral allocation of image dye and
mask consumption underdetermined: at saturated colours the dye ratios depart
from neutral, and the aggregate fit establishes neither whether any particular
per-layer split is correct, nor the direction of its error, nor that the error
grows monotonically with saturation. The resulting spectral and colour errors
may depend on dye ratios and exposure.

This is distinct from the valid point in §3 that a constant per-channel anchor
cannot describe an image-dependent mask; correctly implemented per-channel
anchoring is not itself the error. A gray-axis output lock does not establish
zero physical spectral error.

**This systematic is recorded in PROJECT.md's bounded systematics register**,
which supersedes the note originally made here that it was absent from the
register.

### 5c. The dye decomposition: UNRESOLVED, although narrower in scope than it first appears

If `mid − D-min` equals `dye − consumed`, the decomposition would be fitting
effective dyes whose shapes are distorted by the mask-consumption spectrum,
which is orange and therefore blue-absorbing. A natural hypothesis was that
this contributes to stocks pinning the cyan shift bound.

**The Vision3 basis is itself described relative to D-min.**
`data/films/Vision3_dye_density.json` states this outright, its `units` field
reading "relative diffuse spectral density (Status M, D-min subtracted)".
Basis and target therefore share a reference convention, which avoids an
obvious baseline mismatch.

That label establishes the convention only; it does not establish the
composition, magnitude or layer attribution of whatever mask-consumption
contribution each side carries, still less that the two sides carry the same
contribution across different stocks. Cancellation has not been demonstrated,
and no expansion exists here in which a "first-order" term could be said to
cancel and a "second-order" one to remain.

What is *not* established is how Kodak's published per-layer Vision3 curves
were measured: whether on exposures in which that layer's masking coupler had
been consumed, or as effectively pure-dye spectra. The datasheets are silent,
so the per-dye measurement protocol and each stock's effective spectra remain
unknown, and this should be treated as open.

**Tested, result INCONCLUSIVE.** A short-wavelength signature was sought in the
decomposition residual `aggregate − fit`, by band:

| stock      | blue (<500 nm) | red (≥600 nm) | blue − red |
|:-----------|---------------:|--------------:|-----------:|
| Portra 400 |        +0.0011 |       +0.0020 |    −0.0009 |
| Portra 160 |        +0.0005 |       +0.0029 |    −0.0024 |
| Ektar 100  |        −0.0002 |       +0.0016 |    −0.0017 |

No meaningful blue bias appears. **This does not clear the hypothesis**,
because the fit has nine free parameters including per-dye peak shift and
width: a smooth spectral bias such as mask consumption is exactly the kind of
structure it would absorb *into the fitted shapes* and keep out of the
residual. A small residual is therefore consistent both with the absence of a
mask artefact and with a mask artefact fully absorbed into the dyes. The test
cannot separate the two.

Note that the cyan shift bound is a uniform ±25 nm across all twelve stocks.
Two of them pin it, Fujifilm 200 and 400, which share one chart (Pro 400H's
shipped fit admits its traced red tail and rests free at +14.93, with the
magenta width pinned instead; dye note §4d-ter), and nine of the twelve rest
on a bound of one kind or another, so a pinned cyan shift is the constraint
speaking, and is no evidence about the mask. See `fit_audit.bounds_pinned` and
register entry 12 in PROJECT.md.

---

## 6. What would settle the question

- **Kodak does not publish the mask separately.** The datasheet gives D-min and
  midscale-neutral spectral density, and neither isolates `consumed(x)`. The
  question therefore cannot be resolved from the available datasheets.

- A **spectral density series at several exposure levels** on one stock
  constrains the combined effective spectra, dye plus surviving mask, over
  exposure. It does not by itself isolate `consumed(x)`: the exposure
  derivative of total density is growing image-dye absorption plus declining
  coupler absorption at the same wavelengths, and a declining term can be
  hidden under a larger growing one, so reading off "the part that decreases"
  is not a general separation. Isolating the consumed mask takes additional
  assumptions (fixed per-dye spectra, for one) or measurements that separate
  the contributions; off-neutral exposures help but are not chemically pure
  single-layer measurements either. Two levels, D-min and midscale, provide one
  constraint, whereas the shape requires more.

- **A neutral series alone cannot close the §5b defect**, which is a per-layer
  attribution off the neutral axis. That is measured: a free
  parameter subtracting a multiple of the stock's own D-min improves the
  aggregate fit by 18–25%, but a flat vector, meaningless as a mask, fits
  better on every Kodak stock, so the diagnostic fails its own control.
  Off-neutral R/G/B separation exposures are required as well.

- The validation roll specification carries both requirements. It calls for the
  patches to be read **spectrally over 380–730 nm at not fewer than three
  exposure levels**, with separation exposures alongside the neutral series.
  What that reading constrains is the combined effective spectra over exposure
  and the off-neutral behaviour of the reconstruction, tested on withheld
  exposures and colours; it does not by itself isolate pure dyes or consumed
  masking couplers, so the decomposition remains conditional on its dye-model
  assumptions after the roll. The held-out result that would count as success
  is a stated bound on the spectral and Status M residual of withheld patches.
  See PROJECT.md, Known limitations.

- Until that roll is exposed and measured, the off-axis mis-attribution
  described in §5b stands as a known and unquantified print-branch systematic.

---

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

---

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
