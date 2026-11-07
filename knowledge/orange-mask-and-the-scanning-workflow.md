# The orange mask: mechanism, and its consequences for this pipeline

Collected 2026-07-26. Companion to
`interimage-effects-and-stock-differentiation.md`. This note records what the
mask *is* and whether this project treats it correctly. Two places treat it: the
converters' roll anchor subtracts a per-roll D-min triplet, and the print engine
re-adds a spectral D-min.

**Headline finding: two quantities carry the name "mask". The surviving coupler
is a positive image, maximal at D-min and consumed as dye forms. Surviving
coupler plus unwanted dye absorption is constant under the compensation target
(§2b), and D-min carries that sum.** A per-channel D-min subtraction removes the
sum. It cannot represent the cancellation a real stock leaves incomplete (§2a).

---

## 0. Provenance and confidence

The tiering matches that of the interimage note.

| Tier | Source | Status |
| :--- | :--- | :--- |
| **A, verified primary** | W. T. Hanson, "Color Correction with Colored Couplers", *JOSA* **40**(3):166–171 (1950), the foundational paper. The full text was read. Also the masking-coupler patents US4749641, US6132943, US6010839, US4036646 and US5972585 | Quoted claims below come from fetched text |
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

Hanson's insight, at tier A, is that the
coupler's colour is destroyed during development, so that a colour-negative
frame carries **two superimposed images**:

- a **negative** image composed of developed dye, and
- a **positive** image composed of *unused* coupler.

The effect of overlapping dye absorptions "can be eliminated by the use of
colored couplers" possessing the appropriate spectra. Hanson explicitly frames
this as filling the role of "the six masks which are found to be required by a
number of the theoretical treatments of the problem of exact color
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

Under the compensation target of §2b, the loss of the mask's blue absorption
offsets the gain in blue absorption from the magenta dye's side absorption, both
terms tracking the image. This is the ideal mechanism of §1. §2a measures that
compensation on Vision3. C-41 still-film sheets publish no per-dye curves, so it
is not established for those stocks.

**Consequence: "subtract the orange mask" has one correct reading.** Surviving
coupler density is not constant. The sum of surviving coupler and unwanted dye
absorption is constant under compensation. Subtracting D-min removes that sum,
so in the ideal mechanism the operation holds at every exposure.

### 2a. Measured cancellation on the Vision3 sheets

All four Vision3 charts carry the caption "Process: ECN-2; D-mins subtracted" on
a density axis reaching −0.2. The sheets do not state how the per-dye samples
were prepared. An exposed patch minus D-min equals dye minus consumed mask, and
the measurements below test the traced curves for that quantity (*measured
here*).

- **Magenta carries consumed mask.** Only a difference spectrum can read below
  zero. Magenta reaches −0.039 at 445 nm on 500T and −0.020 at 445 nm on 250D.
  The D-min blue peak on those stocks is at 442–443 nm. 50D reaches −0.008 at
  426 nm and 200T −0.002 at 403 nm. The far yellow tail scatters by 0.001 D, and
  the magenta lobe has no uncertainty estimate of its own.
- **The dye curves close with no mask term.** Midscale minus D-min is fitted over
  405–720 nm to the three dyes, a flat term and `k·(D-min − min D-min)`. The fit
  gives k = −0.09 ± 0.10 on 50D, −0.03 ± 0.06 on 200T, −0.02 ± 0.05 on 250D and
  −0.03 ± 0.04 on 500T, with standard errors corrected for residual
  autocorrelation. Dye curves without consumed mask need k near the consumed
  fraction. k = −0.35 is excluded on all four stocks (2.6–9.3 standard errors),
  and k = −0.20 on all except 50D. Only 6–11% of the mask shape lies outside the
  span of the dyes, which limits this test.

Change in the unwanted channel per 1.5 D of dye at its peak, as the range over
the four stocks; complete cancellation reads 0. The spread is the 1st–99th
percentile range of `read(dye + D-min) − read(dye)` over random dye mixes, for
the largest channel and stock.

| Reader                        | Cyan into green  | Cyan into blue   | Magenta into blue | Offset spread (D) |
| :---                          | :---             | :---             | :---              | ---:              |
| Status M                      | +0.147 to +0.176 | +0.052 to +0.110 | +0.020 to +0.101  | 0.018             |
| 10 nm band, 690/535/445 nm    | +0.098 to +0.130 | +0.056 to +0.121 | −0.052 to +0.029  | 0.001             |
| 1 nm band, 690/535/445 nm     | +0.097 to +0.128 | +0.055 to +0.121 | −0.058 to +0.025  | 0.000             |

- **The offset's constancy depends on the reader.** Band integration bends the
  density sum, and the spread reaches zero at one wavelength.
- **Magenta into blue is close to cancelled.** Most of its Status M value comes
  from band integration.
- **The cyan terms belong to the film.** They survive at one wavelength, and the
  best wavelength per channel still leaves +0.114 to +0.139 in green. Cyan never
  reads below zero, so these curves do not show that it carries consumed mask.
  Four unmasked reversal stocks read +0.112 to +0.268 for cyan into green at
  535 nm and +0.064 to +0.315 for magenta into blue at 445 nm. Those are different
  dye sets, so they give scale only.

The same cross terms through the model's default Endura Premier exposure kernel,
over 400–700 nm, agree with Status M within 0.010 D on all sixteen masked stocks.
The offset spread through that kernel is 0.041–0.079 D, against 0.009–0.033 D
through Status M. The kernel is modelled, so this comparison does not establish
Status M as a substitute for the film's intended print observer.

Limits: each curve is one sample at an unstated exposure, and scaling it assumes
consumption proportional to dye. The physical print response and the off-neutral
attribution of the mask remain unvalidated.

### 2b. Two masking targets (tier A)

Masking can target a chosen cross-channel density gradient under the intended
printing-light and print-sensitivity weighting. A zero gradient compensates
unwanted absorption, and a negative gradient adds deliberate overcorrection. The
achieved correction depends on coupler chemistry, speed, base density and
interimage behaviour. Neither target is established for a current stock.

Hanson (1950) defines these densities by the print material's sensitivities and
uses 440, 560 and 680 nm for simplicity. His two cases are illustrative, with
assumed dyes.

- **Compensation.** Each dye image controls one printing light, with no gradient
  in the other two. Surviving coupler plus unwanted absorption stays constant. In
  his example the coupler absorption costs no speed, because of the layer order.
- **The six masks of exact reproduction.** At a print gamma of 2, his cyan image
  needs gradients of −0.326 in green and −0.258 in blue. The coupler then absorbs
  more than its dye, 0.552 against 0.226 at 560 nm, so the sum falls with
  exposure. His magenta coupler needs D680 0.467 above the red-sensitive layer,
  and he names speed as a possible limiting factor.

Later sources move in the same direction. Bergthaller (2002, Part 3) describes
overmasking as a tool for saturation and print hue. It also reports DIR couplers
least efficient in the toe, and masking couplers with high-speed emulsions
reducing unwanted absorption selectively there. US4830954 uses masking couplers
above the compensating amount because stronger masking raises interimage.
US2428054 defines perfect correction by equal integrated absorption over the
region, so the two curves need not coincide at each wavelength.

**A fixed effective curve needs proportionality.** Hanson's isosbestic point
exists only if dye formed, and anything else formed or destroyed, stays strictly
proportional to coupler consumed. A mix of coloured and uncoloured couplers with
unequal reactivity loses it, and blue density stops being linear in green
density. No source here establishes either behaviour for a stock this project
models.

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
  logarithm. The converters' roll anchor multiplies each channel by `10^Dmin`,
  which is exactly a per-channel subtraction of a D-min triplet in density.
  **This is the correct operation.** It subtracts an INTEGRATED density, the base
  and mask as one LED reads them, and the calibration side has to match that:
  the C-41 engines integrate each LED behind the stock's D-min spectrum, never
  behind the bare LED (PROJECT.md register #17; `reading-datasheet-charts.md`
  §4).

- A known practitioner failure mode applies mask correction as a single COMMON
  gain across the three channels, or as one density offset. Practitioners report
  colour crossover from those flat forms. Three per-channel gains are a different
  operation, and this note endorses the per-channel anchoring above. A
  per-channel gain removes the D-min sum of §2. It cannot represent the
  cancellation a stock leaves incomplete (§2a), which feeds the register's open
  systematic. The anchor itself causes no crossover.

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

### 4a. How much the mask varies between stocks

The mechanism is common to colour negative film. Its strength varies by stock.
Measured from the twelve stocks' published D-min
spectra as blue density minus red density, that is D-min at 440 nm less D-min at
650 nm, the fleet spans **0.6005 D on Fujicolor 100 to 0.9467 D on Fujifilm 200
and 400**, a spread of **0.346 D**, and the ratio (B−R)/(G−R) varies from 1.450
to 2.117, so the mask differs in spectral shape as well as in magnitude.

For scale, the fitted dye sets of the same twelve stocks differ by
0.021–0.219 D
and the basis prior contributes 0.027–0.049 D. **The traced D-min spectra are a
stock-dependent input independent of the surrogate dye fit, and their proxy
varies substantially across the fleet.** Those figures are different
observables over different populations, so no ranking of the mask against the
dye-set differences follows from them; a ranking would need one output metric
on one patch population (dye note §4f).

Bergthaller (2002) supplies a
mechanism to expect the variation, since
pyrazolotriazole magenta couplers have negligible unwanted blue absorption and
correspondingly need less yellow masking coupler than pyrazolone couplers.

That variation reaches the cubes through the print engine, and only away from
the grey axis.

In the mask-swap experiment of
`dye-sets-across-the-three-processes.md` §4f-bis (four pairs, a 25³ grid of
15 625 nodes per pair, evaluated in linear P3 and ΔE2000), the grey-axis lock,
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

That experiment swaps a **D-min**, which is the mask at its maximum. How the mask
is consumed as dye forms is the open off-axis systematic of §5b.

---

## 5. Where this affects the pipeline

Four places, with different verdicts. PROJECT.md's bounded systematics register
is authoritative for this section.

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
calibration and application.** The Status M cube therefore carries no convention
mismatch, and the neutral axis closes as an algebraic identity of the model. That
closure is no statement that the reconstructed spectrum is physically exact
(§5b).

The midscale spectrum is fitted with nonzero residual, and other exposure
levels are not independently established by that single spectrum. Any numerical
neutral lock is distinct from physical spectral exactness.

**The two sides subtract in different spaces.** The datasheet subtracts D-min
spectrally, wavelength by wavelength. The roll anchor subtracts it in integrated
density, one number per LED, which is the LED's reading of the dyes through the
mask, `Φ·10^−Dmin(λ)`. The two agree only where the mask is flat across an LED's
band, and it is not: Portra 400's D-min falls 0.11 D across the green LED's FWHM.
A scan model with the bare LED reads a midscale Portra 400 neutral 0.056 D low in
green (*measured here*). The Status M engines therefore integrate the
mask-filtered illuminant, and the cancellation above holds for the convention
alone (PROJECT.md register #17).

### 5b. Print emulation: off-axis mis-attribution

The engine builds the negative as
`N(λ) = Dmin(λ) + Σ_layer dye_neg · DYE_neg(λ)`. The fitted dye curves carry mask
consumption, so the negative holds the full mask at `dye = 0` and loses it
linearly with the dye formed. Three different kinds of statement about that
construction need keeping apart.

- **Algebraic identity:** `dye = 0` returns D-min exactly, the full mask.
- **Numerical calibration within the model:** the midscale dye amounts return
  the fitted midscale, whose disagreement with the measured midscale is the
  aggregate fit residual, RMSE 0.0108 D for Portra 400 (fit record).
- **Physical approximation:** the interpolation between those two points assumes
  fixed effective dye spectra and mask consumption linear in the dye formed,
  and one midscale spectrum measures neither how each layer's effective
  spectrum nor how the amount ratios evolve over an exposure series; the
  grey-axis lock forces the engine's output neutral curve onto its target,
  which is a different thing from the reconstructed film spectrum being exact at
  every neutral exposure.

Those assumptions hold subject to the register's bounds.

The systematic here is **off-axis mis-attribution**: each fitted per-layer
curve carries a share of mask consumption apportioned as it was at the neutral
ratio, that being the only ratio the datasheet publishes.

Fitting one neutral aggregate leaves the off-neutral allocation of image dye and
mask consumption underdetermined: at saturated colours the dye ratios depart
from neutral, and the aggregate fit establishes neither whether any particular
per-layer split is correct, nor the direction of its error, nor that the error
grows monotonically with saturation. The resulting spectral and colour errors
may depend on dye ratios and exposure.

This is distinct from the point in §3 that a per-channel anchor cannot describe
incomplete cancellation; correctly implemented per-channel anchoring is not
itself the error. A grey-axis output lock does not establish
zero physical spectral error.

**PROJECT.md's bounded systematics register records this systematic.**

### 5c. The dye decomposition: Vision3 magenta closes, cyan and C-41 stay open

§5a gives `mid − D-min` as `dye − consumed`, so the decomposition fits effective
dyes whose shapes the mask-consumption spectrum can distort. That spectrum is
orange and therefore blue-absorbing. Such distortion is a candidate contributor
to stocks pinning the cyan shift bound.

**The Vision3 basis is itself described relative to D-min.**
The basis record states this outright, its units field
reading "relative diffuse spectral density (Status M, D-min subtracted)".
Basis and target therefore share a reference convention, which avoids an
obvious baseline mismatch.

§2a shows that the Vision3 magenta curves carry consumed mask, and that the dye
curves close on midscale minus D-min with no mask term. Basis and target
therefore share the quantity for magenta as well as the label. Cyan's share, the
layer attribution and each C-41 stock's contribution remain open.

**The residual test is inconclusive.** It looks for a short-wavelength signature
in the decomposition residual `aggregate − fit`, by band:

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
shipped fit rests free at +15.53 with no parameter on a bound; dye note
§4d-ter), and eight of the twelve rest on a bound of one kind or another, so a pinned cyan shift is the constraint
speaking, and is no evidence about the mask. See the fit records' pinned bounds
and register entry 12 in PROJECT.md.

### 5d. Signed dye curves across the routes

The dye fit and every engine keep the negative density of the dye curves, so the
fitted reconstruction and the engine's reconstruction agree. Neutral checks
cannot confirm this, because the amounts, the neutral offset and the grey lock
are all re-solved on the loaded curves. The parity tests therefore compare the
loaded curves directly.

A comparison scenario clips those samples at zero. The table compares it with the
signed chain: one physical negative runs through each matched chain,
20 000 random dye triples at amounts 0–2.2, read by the scanner model and looked
up tetrahedrally. Values are CIEDE2000 after conversion to Lab (*measured here*).
The triples are a uniform box, which is no scene population.

| Route                              | Mean  | p99   | Max   | Above 1 |
| :---                               | ---:  | ---:  | ---:  | ---:    |
| Portra 400, Endura Premier         | 0.010 | 0.073 | 0.109 | 0%      |
| Ektar 100, Portra Endura           | 0.010 | 0.040 | 0.050 | 0%      |
| Portra 400, Endura Transparency    | 0.011 | 0.060 | 0.083 | 0%      |
| Fujifilm 400, Pro Laser            | 0.067 | 0.482 | 0.647 | 0%      |
| Pro 400H, Pro Laser                | 0.016 | 0.081 | 0.108 | 0%      |
| Vision3 500T scene, −4 to +3 stops | 0.565 | 3.495 | 5.210 | 14.6%   |
| Vision3 250D scene, −4 to +3 stops | 0.228 | 1.168 | 1.796 | 1.7%    |

- **ADX16 moves by at most 36 of 65 535 codes,** in blue, which is 0.005 D.
- **The scene route responds most.** It inverts to exposure on each stock's own
  traced curves, and 500T carries the deepest lobe. The change sits in the blue
  layer's exposure on 500T: +0.115 stops magenta-heavy, +0.032 near neutral and
  −0.071 yellow-heavy. Two effects oppose. The inverse assigns more yellow where
  magenta is present, and the neutral tables assign more yellow at every exposure.
  They balance on the neutral. The scene matrix then spreads the blue change into
  red and green output.
- **The C-41 rows measure consistency only.** Every C-41 magenta curve carries
  the Vision3 family mean's −0.012, warped. Neither treatment measures that film.
- **Unreachable lattice corners move far more,** up to 3.30 D of Status M output.
  The node solve already leaves up to 3.9 D of residual there.
- **Absolute density stays positive.** D-min plus any stack up to amount 2.2 reads
  at least +0.089 D over 400–700 nm on all seventeen dye sets, neutral, corner and
  random mixes included. The minimum sits at D-min itself.

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

- **Testing fixed effective spectra.** One processing batch carries an unexposed
  patch, repeated controls, red-, green- and blue-selective wedges over toe,
  middle and shoulder, and mixed exposures, with levels and mixtures withheld
  before fitting. A calibrated transmission spectrophotometer records them. A
  repeatable withheld spectral component outside the fitted basis, above
  measurement uncertainty, rejects fixed spectra. A common crossing is supporting
  evidence only: cross-exposure and interimage can remove one, and its presence
  cannot prove proportional chemistry. A neutral series holds three coupler–dye
  pairs and shows no isolated crossing. A change inside the same basis span stays
  indistinguishable from a change of amount.

- Until that roll is exposed and measured, the off-axis mis-attribution
  described in §5b stands as a known and unquantified print-branch systematic.

---

## 7. Open questions and material not found

- No verbatim Photo Engineer text, the server returning 403. The most relevant
  threads are "Orange mask" (132030), "Orange Mask on RA4 paper" (149017) and
  "How do scanners color correct C-41 negatives?" (169634).

- No published per-stock mask-consumption curves for Portra or Ektar were
  found.

- The datasheets do not state how the per-dye Vision3 samples were prepared.
  §2a settles the question by measurement for magenta; cyan remains open.

---

## Sources

- W. T. Hanson, "Color Correction with Colored Couplers", JOSA 40(3):166–171 (1950) – https://opg.optica.org/josa/abstract.cfm?uri=josa-40-3-166 (tier A, full text read)
- P. Bergthaller, "Couplers in colour photography – chemistry and function, Part 3", *The Imaging Science Journal* 50(4):233–276, 2002 – doi:10.1080/13682199.2002.11784405 (tier A, review)
- US2428054, "Photographic color correction using colored couplers" – https://patents.google.com/patent/US2428054A/en
- US4830954, "Color photographic negative film" – https://patents.google.com/patent/US4830954A/en
- US4749641, "Imaging element containing dye masking coupler" – https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/4749641
- US6132943 / US6010839, yellow-coloured magenta dye-forming masking couplers – https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/6132943
- US4036646, "Color correction of unwanted side densities" – https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/4036646
- US5972585, "Color negatives adapted for visual inspection" – https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/5972585
- Photrio "Orange mask", thread 132030 – https://www.photrio.com/forum/threads/orange-mask.132030/ (tier C, NOT fetched, 403)
- Photrio "Orange Mask on RA4 paper", thread 149017 – https://www.photrio.com/forum/threads/orange-mask-on-ra4-paper.149017/ (tier C, NOT fetched, 403)
- Photrio "How do scanners color correct C-41 negatives?", thread 169634 – https://www.photrio.com/forum/threads/how-do-scanners-color-correct-c-41-negatives.169634/ (tier C, NOT fetched, 403)
- scantips.com, processing scanned colour negatives – https://www.scantips.com/colornegs.html (tier B)
- P. Bergthaller, "Couplers in colour photography – chemistry and function, Part 2", *The Imaging Science Journal* 50(3):187–230, 2002, on masking couplers and on pyrazolotriazole magenta making them dispensable (tier A, obtained; see `dye-sets-across-the-three-processes.md`)
