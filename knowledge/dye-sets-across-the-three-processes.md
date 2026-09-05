# Image dyes across C-41, ECN-2 and E-6: chemistry, measured peaks, and the surrogate basis

Collected 2026-08-16. This project decomposes every C-41 stock onto a warped
Vision3 basis, which is to say it models the dyes of a **still colour negative**
process using the dyes of a **motion-picture** process as surrogate. Register entry 8
records the consequence – every stock's fitted cyan sits well to the red of the
basis cyan – but names no mechanism for it. This note assembles what the
literature says about how the three processes' dyes are formed and where they
absorb, and reports what the repository's own data says when asked the same
question.

**Headline finding: the red-shift is not a cyan phenomenon.** All thirty-six fitted
displacements across the twelve-stock fleet, three dyes each, are positive without
exception, under either the fitted shift parameter or the derived peak shift.
Cyan carries the largest, but magenta and yellow are displaced in the same
direction on every stock. A per-stock chemical peculiarity would scatter around
zero; a unidirectional offset on every dye of every stock is a property of the
basis relative to its targets.

**Second finding: the reversal dye data has an external check.**
Independently measured absorption maxima for E-6 dyes, obtained by extracting
and chromatographically separating the dyes from real film, agree with this
project's digitised Kodak reversal peaks to within a few nanometres. This is the
first corroboration from an independent **laboratory measurement** that any part
of this pipeline has received. PROJECT.md records a separate external check of a
different kind, qualitative rather than instrumental, in the darkroom
convergence of Portra 160 and Portra 400.

---

## 0. Provenance and confidence

| Tier | Source | Status |
|---|---|---|
| **A, verified primary** | Silva, Parola, Oliveira, Lavédrine and Ramos, "Contributions to the Characterization of Chromogenic Dyes in Color Slides", *Heritage* 5(4):3946–3969 (2022) | Fetched in full. Dyes physically extracted from film and separated; λmax measured by HPLC-DAD |
| **A, verified primary** | Chatterjee, Trumpy and Ruedel, "Digital Unfading of Chromogenic Film Informed by Its Spectral Densities", *Heritage* 6(4):3418–3428 (2023) | Fetched in full |
| **A, verified primary** | US6296994B1, "Photographic elements for colorimetrically accurate recording intended for scanning", Eastman Kodak, filed 1999-03-01, granted 2001-10-02 | Fetched via Google Patents; quotations verbatim |
| **A, verified primary** | Coupler-chemistry patent literature on pyrazolone and pyrazolotriazole magenta couplers | Fetched |
| **B, secondary** | General statements on differential dark fading of chromogenic dyes | Consistent across archival-sector sources; no single primary obtained |
| **In-repository measurement** | The fitted parameters, digitised peaks and support limits reported in §4 | Computed directly from the repository's shipped data on 2026-08-16 |

---

## 1. How the image dyes are formed, and why the developer is part of them

Colour film forms no dye until development. Each emulsion layer holds a
colourless **coupler** alongside the silver halide. During colour development
the developing agent, an aromatic primary amine of the p-phenylenediamine class,
reduces exposed silver halide and is itself oxidised at that site. The oxidised
developer then reacts with the coupler in the same layer, and that coupling
reaction is what creates the dye.

The consequence that matters here is structural. The dye is the **reaction
product of the developer and the coupler**, so the developer's molecule is built
into the chromophore rather than merely catalysing its formation. From the
literature: the yellow and magenta dyes are **azomethine** dyes, formed from
acylacetanilide and pyrazolone-class couplers respectively, while the cyan dyes
are **indoaniline** dyes formed from phenols and naphthols.

This is why the developing agent identified in
`process-chemistry-c41-ecn2-e6.md` is a chemical fact about the dye set and not
merely a processing detail:

| Process | Developing agent | Dye set |
|---|---|---|
| C-41 | CD-4 | still colour negative |
| ECN-2 | CD-3 | motion-picture colour negative |
| E-6 | CD-3 | colour reversal |

**A tempting inference must be resisted.** It is natural to propose that the
C-41 to Vision3 red-shift follows from CD-4 against CD-3. The repository's own
data refutes that as a sufficient explanation: ECN-2 and E-6 share CD-3, yet
their cyan absorption maxima differ by roughly 26 nm (§3). The coupler, not the
developing agent, dominates where a dye absorbs.

Bergthaller (2002) confirms this directly. The review attributes hue throughout
to coupler structure, and its worked figures are for couplers rather than
developers: a CD-4 dye from a diacylaminophenol coupler shows "a main absorption
band at λmax = 690 nm", while "the absorption maximum of the CD-3 dye hardly
exceeds 645 nm" for a pyrazolo[5,1-c](1,2,4)triazole coupler. **Those two
figures are not a controlled comparison**, since the couplers differ as well as
the developers, and they must not be read as a CD-3 against CD-4 offset. The
review also notes that a given coupler's maximum "can be shifted to at least
650 nm" by formulation additives alone, which places an additional floor under
how precisely any developer-attributable shift could be resolved.

The honest position is that the developing agent is part of the chromophore and
must contribute something, that no source obtained here isolates its
contribution, and that the observed cross-process differences are dominated by
coupler selection.

## 2. Coupler classes and unwanted absorption (tier A)

The three dyes are not equally well behaved, and the differences are by design.

- **Yellow**, from acylacetanilide couplers, is spectrally the cleanest of the
  three and is the reason yellow layers are generally left unmasked.
- **Magenta**, historically from **5-pyrazolone** couplers, carries a
  well-documented secondary absorption. The patent literature states that
  "pyrazolones have shortcomings with respect to color reproduction in that
  unwanted absorption around 430 nm causes color turbidity". That unwanted blue
  absorption is precisely what the yellow-coloured masking coupler in the green
  layer exists to cancel.
- **Pyrazolotriazole** magenta couplers were introduced to remove it. They "have
  significantly lower unwanted absorption of blue and red light and… a narrower
  dye absorption bandwidth" than pyrazolone alternatives.
- **Cyan**, from phenols and naphthols, absorbs furthest into the red and its
  peak placement varies most between product families (§3).

Bergthaller (2002) puts the magenta figures at 545 nm for anilinopyrazolones
against 555 nm for acylaminopyrazolones, and describes the pyrazolotriazole side
absorption at about 440 nm as "although present… neglible". He goes further:
"the exclusive introduction of pyrazolotriazole type magenta couplers into
colour negative film could make yellow masking couplers dispensable."

**A consequence for this project, and it is measurable.** A stock built on
pyrazolotriazole magenta needs less yellow masking coupler than one built on
pyrazolone magenta, so two stocks may differ in mask strength as well as in dye
shape. The datasheets do not disclose which coupler class any stock uses, but
they do publish D-min, and mask strength can be read from it directly. That
measurement is §4f, and it turns out to be the largest inter-stock signal in the
entire dataset.

**Vintage caveat.** Bergthaller's review covers coupler development to about
2000 and every stock in this fleet is current product. Where the review
describes which coupler class a film "uses", that is a statement about the state
of the art two decades ago and must not be attributed to any stock shipping
today. It is used here to name mechanisms and to predict what would be
measurable, never as a fact about a current emulsion.

## 3. Where the dyes actually absorb

### 3a. Independently measured E-6 maxima (tier A)

Silva et al. (2022) extracted dyes from the borders of two slide films, separated
them by preparative thin-layer chromatography, and measured absorption maxima by
HPLC with diode-array detection.

| Film | Process | Cyan | Magenta | Yellow |
|---|---|---|---|---|
| Kodak Ektachrome 160T (EPT) | E-6 | 663 nm | 551 nm | 442 nm |
| Fujichrome Provia 400X (RXP) | E-6 | 651 nm | 546 and 551 nm | 451 nm |

Provia 400X was found to contain **two distinct magenta dyes**, which is a
detail no datasheet discloses and which a three-component decomposition cannot
represent.

### 3b. Comparison with this project's digitised peaks

The repository's reversal peak wavelengths, traced from manufacturer charts:

| Stock | Cyan | Magenta | Yellow |
|---|---|---|---|
| Ektachrome E100 | 658.8 nm | 549.9 nm | 444.0 nm |
| Provia 100F | 657.4 nm | 542.6 nm | 442.8 nm |
| Velvia 100 | 661.7 nm | 553.0 nm | 445.6 nm |
| Velvia 50 | 659.6 nm | 544.4 nm | 447.4 nm |

Against Silva's measured Kodak E-6 values of 663 / 551 / 442, the project's
Ektachrome E100 tracing agrees to **4.2 nm in cyan, 1.1 nm in magenta and 2.0 nm
in yellow**. These are different Kodak emulsions rather than the same one, so
exact agreement is not expected, and the comparison carries a further caveat:
Silva's values are measured on dye **in solution** after extraction, whereas
datasheet curves are measured on dye **in gelatin**, and solvatochromic shifts
of a few nanometres between the two are ordinary. Agreement at this level is
therefore about as close as the comparison can support, and it is genuine
external corroboration of the reversal tracing.

### 3c. The cross-process picture

Adding the Vision3 basis peaks recorded in every C-41 fit audit:

| Dye set | Process | Cyan | Magenta | Yellow |
|---|---|---|---|---|
| Vision3 basis | ECN-2 (CD-3) | **685.0 nm** | 539.0 nm | 448.0 nm |
| Kodak E-6, digitised | E-6 (CD-3) | 658.8 nm | 549.9 nm | 444.0 nm |
| Kodak E-6, measured by Silva | E-6 (CD-3) | 663 nm | 551 nm | 442 nm |

The ECN-2 cyan sits roughly **26 nm to the red** of the E-6 cyan despite the
shared developing agent, while its magenta sits about 11 nm to the **blue**. The
directions differ per dye, which is the observation that rules out the
developing agent as the dominant cause and points to coupler selection.

There is a design reason to expect exactly this. A reversal film is viewed
directly, so its dyes must look correct to the eye. A negative is an
intermediate whose dyes need only modulate the exposure of a print material, so
its cyan can be placed wherever the print material's red sensitivity lies. That
freedom is what US6296994B1 states in its limiting case for scanned film: "the
color negative elements are intended exclusively for scanning… Thus the actual
hue of the image dye produced is of no importance."

**Bergthaller (2002) states the mechanism outright**, and it is more specific
than the general argument above. Writing of cyan couplers, at journal page 208:

> "Dyes from 2,5-diacylaminophenol type couplers such as (32) (Fig. 17) exhibit
> a very high level of stability to reduction, but their main absorption band
> hardly exceeds λmax = 660 nm. Since the spectral sensitization of colour paper
> had been fitted to that of naphthol couplers (peak sensitivity at 690 nm) and
> changes in the photographic design of colour paper were out of question, cyan
> couplers designed for new colour negative films had to be adapted in their
> structures, to exhibit absorption maxima, λmax, of about 690 nm."

So the cyan peak of a colour negative film is **set by the red sensitisation of
the paper it must print onto**, which was fixed at 690 nm and could not be
changed. Reversal film, having no print stage to satisfy, kept the
2,5-diacylaminophenol couplers at ≤660 nm; Bergthaller notes those have "been in
constant use as cyan couplers in colour reversal film for more than 20 years",
and elsewhere that for a reversal coupler "an absorption maximum of the cyan dye
not exceeding 660 nm might be acceptable".

Two independent checks follow, and both pass:

- **Reversal.** Literature ≤660 nm; Silva's measured values 651 and 663 nm; this
  project's digitised peaks 657.4–661.7 nm. All three agree.
- **Colour negative.** Literature "about 690 nm"; this project's fitted C-41
  cyan peaks 702.4–713.8 nm. **These do not agree, and the disagreement is a
  property of the better optimum.** A single fixed start of the same fit lands
  8 to 13 nm less red (691.8–708.2 nm) and would read as agreement with
  Bergthaller's design target; the seeded multistart, which reaches strictly
  lower residuals, places the fitted peak 12 to 24 nm past the wavelength the
  chemistry says the coupler was designed for. Since every stock's cyan is still
  rising at the 700 nm edge of the measured data, the fitted peak is an
  extrapolation in all twelve cases and the discrepancy is as likely to be an
  artefact of extrapolating the surrogate's flank as a statement about the dye.
  Read §4c before using either figure.

That second agreement is meaningful, because the fitted C-41 cyan peak was
reached by a nine-parameter warp of an ECN-2 basis with no knowledge of coupler
chemistry whatsoever. It is independent corroboration that the red-shift of §4a
is real rather than an artefact of the surrogate. It does not validate the
per-layer split, which remains model-dependent, and §4c's caveat stands: for
all twelve stocks that peak sits beyond the grid edge and is an extrapolation.

## 4. What the repository's own data says

Figures in this section were computed from shipped data on 2026-08-16, except
the derived peak displacements in §4a, which were computed on 2026-08-18 from
the `peak_shift_nm` field added subsequently. All are reproducible from
`data/films/`.

### 4a. Every fitted shift is positive

Fitted shift **parameters**, in nanometres, from each stock's
`fit_audit.params`. The warp is `basis(p + (λ − p)/w − s)`, whose peak lands at
`p + s·w`, so these are not peak displacements:

| Statistic | Cyan | Magenta | Yellow |
|---|---|---|---|
| Mean | +23.58 | +6.55 | +7.05 |
| Minimum | +15.13 | +3.39 | +4.11 |
| Maximum | +25.00 (bound) | +9.22 | +11.12 |
| Negative values | none | none | none |

The derived peak displacements, from `fit_audit.peak_shift_nm`, are the
quantity to use for any cross-stock comparison:

| Statistic | Cyan | Magenta | Yellow |
|---|---|---|---|
| Mean | +25.42 | +5.99 | +7.38 |
| Minimum | +17.40 | +3.74 | +3.69 |
| Maximum | +28.75 | +8.17 | +10.82 |
| Negative values | none | none | none |

**Most stocks move their cyan peak FURTHER than the 25 nm the bound
nominally permits**, because the peak lands at `p + s·w` and `wC` rests on the
1.15 ceiling for several stocks: seven of the twelve pin `sC` at +25.00 and four
of those reach a peak displacement of 28.7 nm. Fujifilm 200 and 400 are the
exception in the other direction, pinning `sC` while `wC` rests on 0.85, so
their peaks move only 21.25 nm. The smallest displacement in the fleet is
Fujicolor 100's at 17.40 nm. See PROJECT.md register entry 12.

**Thirty-six shifts out of thirty-six are positive.** Register entry 8 describes this for
cyan alone. Magenta and yellow are smaller but equally unanimous, and the
register should be read as understating the effect: the whole C-41 dye set sits
to the red of the Vision3 basis, not merely its cyan.

### 4b. Tracing error cannot explain it

The obvious competing explanation is a wavelength-axis calibration difference
between the raster-traced Vision3 sheets and the vector-traced Kodak C-41
sheets. The repository already contains the control that bounds this. Ektachrome
E100's `cross_validation` block compares the **vector** E100 chart against the
**independently traced raster** 100D chart for the same emulsion, and reports a
best-fit lateral shift of **0.5 nm in cyan, 1.0 nm in magenta and 1.5 nm in
yellow**, at RMSE 0.0063–0.0113 D.

That is the same vector-against-raster comparison, on the same digitising
machinery, and it lands within 1.5 nm. A mean cyan displacement of 18 nm is an
order of magnitude larger. **Wavelength-axis calibration is excluded as the
cause.**

A second digitisation-side term is not bounded by this control. PROJECT.md
register entry 14 records that interior columns of the Vision3 trace take a
tracker prediction rather than a measurement, at 0.4–5.2% of columns for most
curves and up to 22.9% on one, and the ink-hit overlay cannot see it because a
crossing supplies the neighbouring curve's ink. That term sits on the basis side
of exactly this fit.

### 4c. The fitted cyan peak is not resolved by the data

For all twelve C-41 stocks the fitted cyan argmax lands exactly on 700 nm,
the last point of the output grid. Adding `peak_shift_nm` to the basis peak of
685 nm places the modelled peaks at 702.4–713.8 nm, **all twelve beyond the grid
entirely**, and for **all twelve** the fitted cyan curve is still rising at
700 nm, so the peak is not represented in the shipped curve at any stock. The
multistart's optima are what make this universal: a single fixed start of the
same fit places the modelled peaks at 691.8–708.2 nm, with three beyond the
grid and seven still rising, and the strictly better-fitting optimum on every
stock is the one that sits further outside the measured data (*measured here*,
from `fit_audit.multistart`). For Ektar 100 the 700 nm grid edge already lies 12.1 nm beyond the
687.9 nm limit of that sheet's measured support.

A fitted peak wavelength that sits at the edge of the grid is an extrapolation
from the curve's flank and must not be quoted as a physical property of the
emulsion. This is the concrete form of the under-determination that register entry 8
warns about when a stock pins more than one bound.

### 4d. The 700 nm grid cap, and why it must not simply be raised

**Tested 2026-08-16. The obvious remedy is wrong, and the cap is currently
load-bearing.**

`portra_decompose.py` defines `GRID = np.arange(400, 701, 1.0)`. The
support-based fit mask can narrow that range but never extend it, so 700 nm is a
hard cap on both the fit and the output.

Neither side of the fit requires that cap:

- The **Vision3 basis** is traced to **798 nm**, with cyan still at 0.149 of
  peak at the far end. The endpoint itself is real ink, trailing predicted
  columns being rolled back, though interior columns may be tracked rather than
  measured; see register entry 14.
- The **Fujifilm sheets** are digitised well past 700 nm: Fujifilm 400 to
  717.7 nm, Fujicolor 100 to 719.1 nm, Superia Premium 400 to 719.2 nm, and
  Pro 400H and Fujifilm 200 similarly.

So the Fujifilm **sheets** were traced 17 to 19 nm past 700 nm, in precisely the
band that would constrain the cyan peak, while the basis has measured values
across the same band.

**That data is not in the repository, however.** Every
`data/films/*_datasheet_curves.json` stores its `spectral` arrays on a 400.0 to
700.0 nm grid at 1 nm, 301 points, without exception. The extra red tail was
discarded when the digitiser resampled onto that standard grid. What survives is
only the record of it, in `digitization_audit.spectral_dye_density.endpoints`.

This produces a genuine mismatch. **Eleven of the twelve stocks record an `endpoints`
upper limit that lies beyond the end of their own stored array:**

| Stock | Array ends | `endpoints` hi | Beyond array by |
|---|---|---|---|
| Superia Premium 400 | 700.0 nm | 719.08 nm | +19.1 nm |
| Fujicolor 100 | 700.0 nm | 718.66 nm | +18.7 nm |
| Fujifilm 200 and 400 | 700.0 nm | 717.51 nm | +17.5 nm |
| Pro 400H | 700.0 nm | 716.88 nm | +16.9 nm |
| Portra 400 / 160 / 800, Ultra Max 400, Gold 200, Pro Image 100 | 700.0 nm | 702.6–703.1 nm | +2.6 to +3.1 nm |
| **Ektar 100** | 700.0 nm | 687.88 nm | none, correctly inside |

`portra_decompose.py` builds its fit mask from `endpoints`, then intersects it
with `GRID`. Ektar is the case the mechanism was designed for, where `endpoints`
falls **inside** the array and correctly excludes the flat-held 688–700 nm tail.
For the other eleven the intersection with a 700 nm `GRID` is the only thing
keeping the mask inside real data.

**Raising the cap therefore fabricates.** `engine/common/spectral.resample()`
**zero-fills** beyond the traced support, interpolating with `left=0, right=0`,
so extending `GRID` to each stock's `endpoints` limit appends up to 19 nm of
zero density, which is to say perfectly clear film, and the mask, trusting
`endpoints`, admits it into the objective. Against a basis whose cyan is near
maximum in that band, the target collapses to zero while the model does not.
The experiment was run, and the result is unambiguous:

| Stock | RMSE at 700 nm | RMSE extended | Change | sC |
|---|---|---|---|---|
| Portra 400 | 0.01282 | 0.09328 | **+628 %** | +17.94 → −3.82 |
| Fujifilm 400 | 0.01793 | 0.13512 | **+654 %** | +25.00 → −11.35 |
| Pro 400H | 0.01091 | 0.13792 | **+1164 %** | +14.53 → −25.00 |
| Superia Premium 400 | 0.01961 | 0.23020 | **+1074 %** | +19.90 → −25.00 |
| Ektar 100 | 0.01226 | 0.01226 | **0.00 %** | +15.52 → +15.52 |

Every cyan shift inverts, the cyan width collapses onto the 0.85 floor, and
maximum absolute error reaches 0.92 D. Ektar 100 is an exact null control, since
its `endpoints` limit of 687.9 nm is already inside the array, and its perfect
invariance confirms the harness rather than the hypothesis.

**This is a latent violation of the project's own first invariant**, that no
value nobody measured may enter a fit. It is currently inert only because
`GRID` happens to stop at 700 nm. Anyone who raises that ceiling without
re-digitising silently fits fabricated data and the fit degrades by roughly an
order of magnitude. The safe form of the change is to
**re-digitise the Fujifilm sheets onto a wider grid first**, and only then raise
`GRID`. A cheaper defensive fix is to clamp the mask with
`_hi = min(_hi, swl.max())` so that `endpoints` can never reach past the stored
array.

### 4d-bis. How much would the missing band actually buy?

Since the red tail cannot be fitted, its influence was measured the other way,
by pulling the top of the fitted band back through real measured data from
700 nm to 670 nm and watching the fitted cyan shift. No fabricated point enters
any of these fits.

| Stock | sC at 700 | at 690 | at 680 | at 670 | Swing |
|---|---|---|---|---|---|
| Fujifilm 400 and 200 | +25.00 | +25.00 | +25.00 | +25.00 | **0.00** |
| Superia Premium 400 | +19.90 | +19.80 | +18.24 | +17.94 | 1.96 |
| Ektar 100 | +15.52 | +15.52 | +14.00 | +12.16 | 3.36 |
| Portra 400 | +17.94 | +16.80 | +14.53 | +9.85 | 8.09 |
| Pro 400H | +14.53 | +14.17 | +13.99 | +25.00 | 11.01 |
| Fujicolor 100 | +7.14 | +5.55 | +0.52 | −8.53 | **15.67** |

The fitted cyan shift is strongly determined by the reddest few nanometres of
the band for some stocks, at 0.27 nm of shift per nm of band for Portra 400 and
0.52 nm/nm for Fujicolor 100, and barely at all for others.

**Fujifilm 200 and 400, which pin the cyan shift bound, are completely
insensitive to the cut.** The table is the measurement of 2026-08-16, made with
the single-start solve; the shipped fits are a seeded multistart over the same
bounds, under which seven of the twelve stocks pin `sC` at +25.00 and ten of
the twelve rest on a bound of one kind or another, as `fit_audit.bounds_pinned`
and PROJECT.md register entry 12 record. The cut experiment's conclusion is
unaffected: Fujifilm 400 and 200 sit at +25.00 at every cut, so the missing 17.5 nm would
not release them. Their pin has a different cause, which `portra_stocks.py`
already identifies: their dye chart is shared byte-for-byte between two
datasheets and cannot describe two films. The hypothesis that recovering the red
tail would release those bounds is therefore **refuted**.

What the sweep does establish is more general and more useful: for several
stocks the fitted cyan shift is partly a property of **where the fitted band
stops** rather than of the emulsion. That is a direct measurement of the
under-determination register entry 8 warns about, and it reinforces the rule there
that a pinned or extreme cyan shift is evidence about the basis and never a
property of the film.

**The script also reports a support it does not use.** Its stdout line reads
"over the MEASURED support 399.8-717.5 nm" for Fujifilm 400 and
"402.5-703.1 nm" for Portra 400, but the fit mask is intersected with `GRID`,
so in both cases the fit actually ends at 700 nm. The reported figure is the
stock's digitised support rather than the range fitted. Eleven of the twelve stocks
have a support limit above 700 nm and therefore report an upper bound the fit
never reaches; only Ektar 100, whose support ends at 687.9 nm, reports honestly.
The overstatement is confined to the script's stdout and to the
`digitization_audit` block of each `data/films/*_datasheet_curves.json`. The
shipped `data/films/*_dye_density.json` files record the phrase "over the
MEASURED support" without a range, so the wrong figure is not carried into the
dye data itself.

This is the same mismatch as §4d seen from the reporting side, and it is the
reason the discrepancy went unnoticed: every audit block asserts a fitted range
that is up to 19 nm wider than the one actually used.

### 4e. The red LED sits on the cyan flank for negatives, and near the peak for reversal

This project scans at 640 / 544 / 450 nm. Measured against the shipped
peak-normalised cyan curves:

| Stock | Cyan at 640 nm | Cyan peak |
|---|---|---|
| Portra 400 | 0.649 | at or beyond 700 nm |
| Ektar 100 | 0.650 | at or beyond 700 nm |
| Ektachrome E100 | 0.908 (of a 0.948 peak) | 658 nm |

(Re-measured 2026-09-02 on the shipped multistart fits; the single-start fits
of 2026-08-16 read 0.645 and 0.671.) For the negative stocks the red probe sits
on the steep rising flank of the cyan absorption, where the local slope is
approximately **+0.008 per nm**. A 10 nm error in the fitted cyan peak position
therefore moves the modelled cyan density at the red LED by about 0.08 in
peak-normalised units, close to a tenth of peak. Across the fleet the fitted
cyan peak displacement spans 11 nm (17.4–28.8 nm).

For reversal the same probe sits near the cyan maximum, on a flat part of the
curve, where peak-position error is far less consequential.

**This connects two facts the register keeps separate**: cyan is both the least
determined parameter of the C-41 fit and the dye the red channel is most
sensitive to. It is not a defect in the LED choice, which is constrained by
available hardware and by channel decoupling, but it does explain why cyan error
propagates more strongly than magenta or yellow error on the negative paths.

Independently, Chatterjee et al. (2023) chose narrowband capture at **672 / 544 /
447 nm** for multispectral film digitisation. The green and blue choices are
within 3 nm of this project's; the red is 32 nm further into the red.

### 4f. The orange mask discriminates the fleet an order of magnitude better than the dyes do

Bergthaller (2002) states that pyrazolotriazole magenta couplers have negligible
side absorption and that "the exclusive introduction of pyrazolotriazole type
magenta couplers into colour negative film could make yellow masking couplers
dispensable". If contemporary stocks differ in which magenta coupler class they
use, they should differ in how much yellow masking coupler they carry, and that
is measurable from the published D-min spectra without any basis assumption.

Measured from each stock's own `_datasheet_curves.json` on 2026-08-23, using
D-min at 440 nm minus D-min at 650 nm as a mask-strength proxy:

| Stock | D-min 440 | D-min 550 | D-min 650 | B − R | (B−R)/(G−R) |
|---|---|---|---|---|---|
| Fujicolor 100 | 0.7554 | 0.5567 | 0.1549 | **0.6005** | 1.495 |
| Superia Premium 400 | 0.8714 | 0.5800 | 0.2624 | 0.6090 | 1.918 |
| Portra 400 | 0.8232 | 0.6176 | 0.2006 | 0.6226 | 1.493 |
| Portra 160 | 0.8187 | 0.6320 | 0.1805 | 0.6382 | **1.414** |
| Ektar 100 | 0.8731 | 0.6111 | 0.2210 | 0.6521 | 1.672 |
| Pro Image 100 | 0.9787 | 0.6828 | 0.2792 | 0.6995 | 1.733 |
| Gold 200 | 0.9896 | 0.6482 | 0.2519 | 0.7377 | 1.861 |
| Ultra Max 400 | 0.9861 | 0.6008 | 0.2334 | 0.7527 | 2.049 |
| Portra 800 | 1.0040 | 0.5969 | 0.2231 | 0.7809 | **2.089** |
| Pro 400H | 1.0351 | 0.6996 | 0.2101 | 0.8250 | 1.685 |
| Fujifilm 200 and 400 | 1.0430 | 0.5848 | 0.0963 | **0.9467** | 1.938 |

**The spread is 0.346 D**, from 0.6005 to 0.9467. Set against the quantities
this project uses to bound its own claims:

| Quantity | Magnitude |
|---|---|
| Basis sensitivity of the dye decomposition | 0.034–0.063 D |
| Inter-stock distances between fitted dye sets | 0.021–0.220 D |
| C-41 process-control tolerance (Z-131) | ±0.03–0.09 D |
| **Mask-strength spread across the fleet** | **0.346 D** |

The mask separates these stocks by more than the dyes do, more than the basis
prior does, and far more than process drift does. The shape differs too, not
merely the scale: the ratio (B−R)/(G−R) runs from 1.414 on Portra 160 to 2.089
on Portra 800, so the mask's spectral profile is itself a per-stock property.

The ordering is broadly coherent with Bergthaller's account. The slower
professional Kodak stocks carry the weakest masks, Portra 400 at 0.623, Portra
160 at 0.638 and Ektar 100 at 0.652, while the consumer and older formulations
carry among the strongest, Gold 200 at 0.738, Ultra Max 400 at 0.753 and
Fujifilm 200/400 at 0.947 – though Portra 800, professional but fast, sits at
0.781, above both Kodak consumer stocks. That is the pattern expected if
premium films have moved to
pyrazolotriazole magenta and need less yellow masking coupler. **It is a
consistency, not a proof:** no datasheet names a coupler class, and the
inference from mask strength to coupler chemistry is not something these data
can close.

**How far this reaches into the deliverables is a separate question, and the
answer is currently unknown.** The print branch is one engine,
`PrintEmulationEngine`, presented as `endura_print_engine.py` for the seven
Kodak stocks on Endura Premier and `fuji_print_engine.py` for the five
Fujifilm stocks
on Fujicolor Pro Laser TYPE II; each engine's `--stock` choices enforce the
pairing. It builds the negative as `N(λ) = dmin_spec(λ) + Σ dye · DYE(λ)` and
reads `dmin_spec` from each stock's own digitised curves, so a strongly
stock-dependent term does enter the print branch, and it owes nothing to the
surrogate basis. It does not follow that the
shipped print cubes differ by anything like 0.346 D. The engine applies a full
per-channel **gray-axis lock**, calibrating every channel to a common master
neutral tone curve at every density, which is precisely what a printer's colour
balance does to a mask in practice. **The lock absorbs the per-channel scalar
component of any mask difference by construction.**

What can survive it is the part a per-channel scalar cannot represent: the
mask's spectral shape *within* each of the paper's three sensitivity bands, and
its consequences away from the neutral axis. The shape variation measured above,
with (B−R)/(G−R) running 1.414 to 2.089, is real and is exactly that kind of
term, but no measurement here establishes how much of it reaches a cube.

### 4f-bis. Measured: how much of the mask reaches a cube

Run 2026-08-16. Pairs of engines were constructed differing **only** in
`dmin_spec`. The swap is performed after construction so that both engines take
the identical sentinel code path, leaving `neg_support` and every other derived
quantity untouched, and `solve_gray_axis_lock()` is then re-run against the new
mask exactly as it would be in a real build. Dyes, paper, illuminant and
support handling are shared throughout, so any difference is mask-attributable
by construction. Evaluation is over a 25³ grid, 15 625 nodes, plus a 128-sample
grey ramp.

**Null control.** Re-injecting a stock's own mask and re-solving the lock
reproduces the engine exactly: maximum linear-P3 difference **0.000e+00**.

| Mask swap (dyes held fixed) | Δ(B−R) | Δ shape ratio | neutral max ΔE | nodes > 1 ΔE | max ΔE |
|---|---|---|---|---|---|
| Fujicolor 100 → Fujifilm 400 mask | +0.346 | +0.443 | 0.036 | 20.4% | 5.50 |
| Portra 400 → Gold 200 mask | +0.115 | +0.368 | 0.101 | 12.7% | 3.62 |
| Ektar 100 → Pro 400H mask | +0.173 | +0.014 | 0.131 | 1.2% | 1.55 |
| Fujicolor 100 → Superia Premium 400 mask | +0.009 | +0.423 | 0.027 | 18.8% | 4.02 |

**The lock behaves as predicted on neutrals.** Across every pair the grey ramp
differs by at most 0.131 ΔE2000. Neutral rendering is stock-independent by
construction, which is what a printer's colour balance does to a mask in
practice.

**Off the neutral axis the mask survives.** For realistic stock pairs 13–20% of
nodes exceed 1 ΔE2000, reaching 3.6–5.5 ΔE2000 at saturated colours.

**The driver is shape, not strength.** The last two rows are diagnostic pairs
chosen to separate the two. Ektar 100 → Pro 400H changes mask strength by
0.173 D with essentially no change of spectral shape, and yields 1.2% of nodes
above 1 ΔE and a maximum of 1.55. Fujicolor 100 → Superia Premium 400 changes
strength by 0.009 D, **nineteen times less**, while changing shape by as much as
the extreme pair, and yields 18.8% and a maximum of 4.02. A mask difference with
no magnitude to speak of therefore moves the cube further than one with
substantial magnitude and no shape change.

This is coherent with the mechanism: a per-channel scalar lock can compensate
the mask's overall level in each band but cannot compensate how the mask density
varies **within** a band, and it is that within-band profile which reaches the
print.

**Conclusion.** The orange mask is the first demonstrated mechanism by which
this project's C-41 print cubes discriminate between stocks. It is
basis-independent, it is measurable in the input data at 0.346 D, and it reaches
the deliverable at up to 4.5 ΔE2000 on saturated colours. The swaps above are a
controlled mask-only experiment run inside a single engine, and therefore
measure the mechanism rather than any shipped pair of cubes: three of the four
cross a paper brand that the pairing rule forbids, and no equivalent measurement
exists for the Pro Laser lock. The corresponding
limitation is equally clear: it contributes nothing on or near the grey axis, so
no claim about neutral rendering may rest on it.

Three caveats travel with this measurement:

- D-min is the **whole** film base, comprising support tint and both the yellow
  and the pink masking couplers. B − R is a proxy for total mask strength and
  does not isolate the yellow masking coupler. A neutral base contributes
  roughly equally to both bands and largely cancels in the difference, but not
  exactly.
- **Fujifilm 200 and 400 are identical by construction**, sharing one dye chart,
  so they contribute one measurement rather than two, and their extreme position
  should not be over-read.
- These are published D-min values for fresh film. Differential dye fading (§8)
  does not affect unexposed D-min in the same way it affects image dye, but the
  masking couplers are themselves dyes and are not immune.

## 5. The modelling assumption, stated in the literature (tier A)

This project decomposes an aggregate spectral density into a weighted sum of
per-dye curves. That step assumes densities add linearly. Chatterjee et al.
(2023) state the assumption and its justification explicitly:

> chromogenic, dye-based film "is a non-scattering material; hence, the
> Beer–Lambert law is deemed to be valid; the overall spectral density of the
> film is the sum of the spectral densities of the individual dyes with weights
> corresponding to their local concentrations"

The paper states no limit or breakdown condition. This is a peer-reviewed
statement of the pipeline's core modelling assumption, which the repository
states without citation, and it also supports the geometry argument in
`densitometry-standards-and-density-metrics.md`.

## 6. Integral against analytical density (tier A)

The vocabulary for what this project does exists in the literature, and
`reading-datasheet-charts.md` and the PROJECT.md Invariants use it.

- **Integral density** is what a densitometer measures through the whole film:
  it blends the absorptions of all three dyes at every wavelength.
- **Analytical density** is the density attributable to each dye separately, and
  is proportional to the amount of that dye.

US6296994B1 describes the standard conversion between them, and confirms that a
matrix treatment is the accepted method: "a second set of speeds was generated
by taking the Status M densitometry and transforming it to analytical densities
using a 3×3 matrix treatment appropriate for the image dye set". It also records
the limitation this project runs into, that "the degree of overlaps of
sensitivity of the red, green and blue recording emulsion units apparently can
lead to problems in accurately portraying the unit responsivity from integral
densitometry", and warns that Status M and Status A "may have no distinct
meaning" when image dyes depart from the hues used in optical printing.

**This project's decomposition is an integral-to-analytical conversion in which
the dye set is unknown and assumed.** Naming it that way makes the surrogate
basis easier to describe and connects the work to an existing literature.

## 7. Interimage and the scanning case (tier A)

US6296994B1 supports, from Kodak's side, the position PROJECT.md reaches for
`DIR_MATRIX`. It describes traditional colour correction as achieved "through
interlayer interimage effects generally produced by colored masking couplers and
development inhibitor releasing couplers", and then states that for elements
intended for scanning "the color correction that was formally performed
chemically can be done with higher effectiveness by mathematical transformations
of the electronic signals". Films of that invention carry "less than 0.02…
millimole/m² of colored masking coupler" and "no colored masking coupler is
required".

Two points follow for this project.

1. Interimage and masking are alternatives to signal-domain correction, not
   additions to it. A negative that has already been developed carries its
   interimage effect in the measured densities, which is the argument recorded in
   `interimage-effects-and-stock-differentiation.md` §5.4.
2. The patent describes films designed **without** a mask for scanning. Every
   stock in this fleet is a conventional masked negative, so that design case
   does not apply here, but it clarifies what the mask is for.

## 8. Dye fading (tier B)

Chromogenic dyes fade at different rates in dark storage, and the pattern is
consistent across the archival literature: **cyan and yellow fade faster than
magenta**, which survives comparatively well. Chatterjee et al. observe exactly
this in their samples, with "yellow and cyan dyes substantially faded, while the
magenta dye is always well-preserved".

The relevance here is a scope boundary rather than a defect. Every curve in
`data/` describes **fresh** film as published by the manufacturer, while any real
scan is of film that has aged since exposure. For recently shot and promptly
developed material the difference is negligible. For archival material it is not,
and none of this project's transforms model it. Chatterjee et al. is the
reference for what modelling it would involve, namely per-dye scalar fading
factors solved against a known neutral.

No quantitative fading rate per dye was found in either paper.

## 9. Open questions and material not found

- **No measured λmax for any C-41 or ECN-2 dye was located.** Silva et al. covers
  E-6 only. The cross-process comparison in §3c therefore rests on datasheet
  tracing for the negative processes and on laboratory measurement only for
  reversal.
- **The magnitude of the CD-3 against CD-4 spectral difference is unquantified.**
  No source obtained gives absorption maxima for the same coupler developed in
  both agents, which is the measurement that would settle §1.
- **Which magenta coupler class each stock uses is not published.** This is
  needed before mask strength could be modelled per stock.
- **Whether re-digitising the Fujifilm red tail is worth doing is unresolved.**
  §4d-bis shows the two stocks that pin the cyan bound would not be released by
  it, while Fujicolor 100 and Pro 400H are highly band-sensitive and might move
  substantially, though both rest their magenta width on the 1.15 bound and are
  therefore not free fits either. Settling it requires re-tracing the four Fujifilm sheets whose
  charts run past 700 nm and refitting, which is a digitisation task rather than
  a modelling one. Note that Status M red responsivity is itself truncated at
  700 nm here, so the gain would be confined to constraining the fit and would
  not directly change the Status M integral.
- **Which magenta coupler class each current stock uses remains unpublished**,
  and §4f infers only a consistency, not a chemistry. Confirming it would need a
  chemical method of the kind Silva et al. used, applied to current C-41 stock.
- **Whether the measured off-axis mask difference is CORRECT is untested.**
  §4f-bis establishes that the mask reaches the print cubes and by how much, not
  that the resulting colours match a real print. The D-min spectra driving it
  are digitised datasheet values, so the difference is as good as those traces
  and no better. A validation roll remains the only route to confirming it, and
  the saturated colours where the effect concentrates are precisely those the
  R/G/B separation wedges would cover.
- **Mask consumption is still unmodelled off-neutral.** §4f-bis swaps a D-min,
  which is the mask at its maximum. How the mask is consumed as dye forms away
  from the neutral ratio is the open systematic recorded in
  `orange-mask-and-the-scanning-workflow.md` §5b, and it is untouched by this
  experiment.
- Scarpace and Friederichs, "A method of determining spectral analytical dye
  densities", *Photogrammetric Engineering and Remote Sensing* 44:1293 (1978),
  determines unit spectral dye curves for three dyes from integral measurements
  at 16 to 19 wavelengths. This is the closest published analogue to this
  project's decomposition. NASA's record carries **no downloadable full text**,
  and it is the one significant item still missing.

## Sources

- Silva, Parola, Oliveira, Lavédrine and Ramos, "Contributions to the Characterization of Chromogenic Dyes in Color Slides", *Heritage* 5(4):3946–3969, 2022 – https://doi.org/10.3390/heritage5040203 (tier A, fetched in full)
- Chatterjee, Trumpy and Ruedel, "Digital Unfading of Chromogenic Film Informed by Its Spectral Densities", *Heritage* 6(4):3418–3428, 2023 – https://doi.org/10.3390/heritage6040181 (tier A, fetched in full)
- US6296994B1, "Photographic elements for colorimetrically accurate recording intended for scanning", Eastman Kodak (Sowinski, Buitano, Link) – https://patents.google.com/patent/US6296994B1/en (tier A, fetched)
- US6787294B1, bicyclic pyrazolotriazole coupler with improved hue – https://patents.google.com/patent/US6787294B1/en (tier A, fetched)
- US5378587A, photographic material comprising a bicyclic pyrazolo coupler – https://patents.google.com/patent/US5378587A/en (tier A, fetched)
- US5972585, "Color negatives adapted for visual inspection", on masking couplers in reversal elements – https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/5972585 (tier A)
- Scarpace and Friederichs, "A method of determining spectral analytical dye densities", *Photogrammetric Engineering and Remote Sensing* 44:1293, 1978 – https://ntrs.nasa.gov/citations/19790026986 (abstract only, no full text available)
- P. Bergthaller, "Couplers in colour photography – chemistry and function, Part 2", *The Imaging Science Journal* 50(3):187–230, 2002 – doi:10.1080/13682199.2002.11784404 (tier A, obtained and read in full). **Scanned pages with an OCR text layer**: every figure quoted here was checked against the page image, and PDF page numbers run 185 behind journal pages
- A. Plutino, "Color systems for motion picture film digitization: a critical review", *Color Research and Application* 49(6):609–617, 2024 – https://doi.org/10.1002/col.22946 (tier A, obtained and read in full)
- National Film Preservation Foundation, colour dye fading – https://www.filmpreservation.org/preservation-basics/color-dye-fading (tier B)
