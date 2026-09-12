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
exception, under either the fitted shift parameter or the derived peak shift
(§4a, recomputed from the current `fit_audit` records). Cyan carries the
largest, but magenta and yellow are displaced in the same direction on every
stock. The shared positive shifts describe a systematic relationship between
this surrogate basis and these fitted targets. They do not identify its
chemical cause: no null model establishes that stock-specific chemistry would
scatter around zero, since the stocks share design constraints, the fits share
one basis and one set of bounds, and Fujifilm 200 and 400 share a chart. Nor
do the fitted maxima independently identify the physical dye spectra (§4c).

**Second finding: the reversal dye data has an external check.**
Independently measured absorption maxima for E-6 dyes, obtained by extracting
and chromatographically separating the dyes from real film, agree with this
project's digitised Kodak reversal peaks to within a few nanometres. This is the
first corroboration from an independent **laboratory measurement** that any part
of this pipeline has received. PROJECT.md records a separate external check of a
different kind, qualitative and uninstrumented, in the darkroom
convergence of Portra 160 and Portra 400.

---

## 0. Provenance and confidence

| Tier | Source | Status |
|---|---|---|
| **A, verified primary** | Silva, Parola, Oliveira, Lavédrine and Ramos, "Contributions to the Characterization of Chromogenic Dyes in Color Slides", *Heritage* 5(4):3946–3969 (2022) | Fetched in full. Dyes physically extracted from film and separated; λmax measured by HPLC-DAD |
| **A, verified primary** | Chatterjee, Trumpy and Ruedel, "Digital Unfading of Chromogenic Film Informed by Its Spectral Densities", *Heritage* 6(4):3418–3428 (2023) | Fetched in full |
| **A, verified primary** | US6296994B1, "Photographic elements for colorimetrically accurate recording intended for scanning", Eastman Kodak, filed 1999-03-01, granted 2001-10-02 | Fetched via Google Patents; quotations verbatim |
| **A, verified primary** | Coupler-chemistry patent literature on pyrazolone and pyrazolotriazole magenta couplers | Fetched |
| **A, peer-reviewed review, secondary on the chemistry it surveys** | P. Bergthaller, "Couplers in colour photography – chemistry and function, Part 2", *The Imaging Science Journal* 50(3):187–230 (2002) | Obtained and read in full; quoted figures checked against the page image (Sources) |
| **A, peer-reviewed review** | A. Plutino, "Color systems for motion picture film digitization: a critical review", *Color Research and Application* 49(6):609–617 (2024) | Obtained and read in full |
| **B, secondary** | General statements on differential dark fading of chromogenic dyes | Consistent across archival-sector sources; no single primary obtained |
| **Model calculation from repository data** | The fitted parameters, digitised peaks and support limits reported in §4 | Read from the shipped `data/films/` records; the fleet summaries on 2026-09-12 (§4 states the fields and expression), retained experiments on the dates each section gives |

---

## 1. How the image dyes are formed, and why the developer is part of them

Colour film forms no dye until development. Each emulsion layer holds a
**coupler** alongside the silver halide; in a masked negative the cyan and
magenta layers' couplers are themselves coloured (the masking couplers of
`orange-mask-and-the-scanning-workflow.md`), so "colourless" describes the
image-forming reaction alone. During colour development
the developing agent, an aromatic primary amine of the p-phenylenediamine class,
reduces exposed silver halide and is itself oxidised at that site. The oxidised
developer then reacts with the coupler in the same layer, and that coupling
reaction is what creates the dye.

The consequence that matters here is structural. The dye is the **reaction
product of the developer and the coupler**, so the developer's molecule is built
into the chromophore. From the
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
data shows that the developer alone does not determine the spectrum: ECN-2 and
E-6 share CD-3, yet their cyan absorption maxima differ by roughly 26 nm (§3).
That observation does not isolate the contribution of CD-3 against CD-4 in the
C-41 to ECN-2 comparison, and it does not rank developer against coupler; no
controlled comparison obtained here does.

Bergthaller (2002) confirms this directly. The review attributes hue throughout
to coupler structure, and its worked figures are for couplers: a CD-4 dye from a diacylaminophenol coupler shows "a main absorption
band at λmax = 690 nm", while "the absorption maximum of the CD-3 dye hardly
exceeds 645 nm" for a pyrazolo[5,1-c](1,2,4)triazole coupler. **Those two
figures are not a controlled comparison**, since the couplers differ as well as
the developers, and they must not be read as a CD-3 against CD-4 offset. The
review also notes that a given coupler's maximum "can be shifted to at least
650 nm" by formulation additives alone, which places an additional floor under
how precisely any developer-attributable shift could be resolved.

The honest position is that the developing agent is part of the chromophore and
must contribute something, that no source obtained here isolates its
contribution, and that coupler selection is a sufficient mechanism for
cross-process differences of the size observed, without the data to say it is
the dominant one.

---

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
measurement is §4f: a stock-dependent input that owes nothing to the surrogate
fit and varies substantially across the fleet.

**Vintage caveat.** Bergthaller's review covers coupler development to about
2000, and the stocks in this fleet are modelled from their current datasheet
editions (Pro 400H is discontinued, modelled from its final datasheet). Where the review
describes which coupler class a film "uses", that is a statement about the state
of the art two decades ago and must not be attributed to any stock shipping
today. It is used here to name mechanisms and to predict what would be
measurable, never as a fact about a current emulsion.

---

## 3. Where the dyes actually absorb

### 3a. Independently measured E-6 maxima (tier A)

Silva et al. (2022) extracted dyes from the borders of two slide films, separated
them by preparative thin-layer chromatography, and measured absorption maxima by
HPLC with diode-array detection.

| Film | Process | Cyan | Magenta | Yellow |
|---|---|---|---|---|
| Kodak Ektachrome 160T (EPT) | E-6 | 663 nm | 551 nm | 442 nm |
| Fujichrome Provia 400X (RXP) | E-6 | 651 nm | 546 and 551 nm | 451 nm |

Provia 400X was found to contain **two distinct magenta dyes**, a detail no
datasheet discloses. A three-component decomposition can still represent that
layer if the two species keep a fixed concentration ratio over the modelled
conditions, one magenta basis spectrum standing for their weighted sum; a
fourth independent component is needed only where the ratio varies. Silva's
maxima are for extracted dyes measured in solution by diode-array detection at
a stated 4 nm resolution.

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
in yellow**.

These are different Kodak emulsions, so exact agreement is not expected, and
the comparison carries a further caveat: Silva's values are measured on dye **in
solution** after extraction, whereas datasheet curves are measured on dye **in
gelatin**, and solvatochromic shifts of a few nanometres between the two are
ordinary, and Silva's detector resolution is 4 nm. No uncertainty budget
combining those terms has been formed, so the agreement is reported as an
observation and not as a residual within a stated tolerance.

It is a plausibility check on the reversal tracing from an independent
laboratory measurement of other emulsions and other measurement media; it is
not a calibration of this project's wavelength axis and not a validation of the
E100 reconstruction.

### 3c. The cross-process picture

Adding the Vision3 basis peaks recorded in every C-41 fit audit:

| Dye set | Process | Cyan | Magenta | Yellow |
|---|---|---|---|---|
| Vision3 basis | ECN-2 (CD-3) | **685.0 nm** | 539.0 nm | 448.0 nm |
| Kodak E-6, digitised | E-6 (CD-3) | 658.8 nm | 549.9 nm | 444.0 nm |
| Kodak E-6, measured by Silva | E-6 (CD-3) | 663 nm | 551 nm | 442 nm |

The ECN-2 cyan sits roughly **26 nm to the red** of the E-6 cyan despite the
shared developing agent, while its magenta sits about 11 nm to the **blue**. The
directions differ per dye. That shows developer identity alone is insufficient
to determine the spectrum; it does not quantify the CD-3 against CD-4
contribution, and it does not rank developer against coupler (§1).

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

Two comparisons follow, with different outcomes:

- **Reversal.** Literature ≤660 nm; Silva's measured values 651 and 663 nm; this
  project's digitised peaks 657.4–661.7 nm. All three agree.
- **Colour negative.** Literature "about 690 nm"; this project's shipped C-41
  cyan model peaks 699.3–713.3 nm (§4c). **These do not agree on eleven stocks,
  and the disagreement is a property of the better optimum.** In the 2026-08-16
  single-start population a fixed start of the same fit landed 8 to 13 nm less
  red (691.8–708.2 nm) and would have read as agreement with Bergthaller's
  design target; the seeded multistart, which reaches strictly lower residuals,
  places the fitted peak past the wavelength the chemistry says the coupler was
  designed for on every stock but Pro 400H, whose tail-constrained fit lands at
  699.3 nm. On eleven stocks the shipped cyan is still rising at the 700 nm edge
  of the output grid, so the fitted peak is an extrapolation there and the
  discrepancy is as likely to be an artefact of extrapolating the surrogate's
  flank as a statement about the dye. Read §4c before using either figure.

What the negative comparison supports is the DIRECTION of §4a's red-shift: a
nine-parameter warp of an ECN-2 basis, with no knowledge of coupler chemistry,
moves every C-41 cyan toward the 690 nm the chemistry names, and past it. It
is not corroboration of the fitted peak values, which sit beyond the output
grid on eleven stocks and are extrapolations there (§4c), and it does not
validate the per-layer split, which remains model-dependent. Chemistry here is
a plausible mechanism for the shift; it measures nothing.

---

## 4. What the repository's own data says

The fleet summaries in §4a and §4c were recomputed on 2026-09-12 from the
twelve current `fit_audit` records (`params`, `peak_shift_nm`,
`bounds_pinned`) and the shipped `shared_full_curves` cyan arrays in
`data/films/*_dye_density.json`; the model peak is the recorded 685 nm basis
peak plus the stored displacement, and the sampled argmax is read on the stored
1 nm grid. Experiments retained in §4b, §4d, §4d-bis and §4d-ter carry their
own dates and populations, and where a figure belongs to the single-start
population of 2026-08-16 it is labelled so; those figures are not to be mixed
into the current fleet summaries.

### 4a. Every fitted shift is positive

Fitted shift **parameters**, in nanometres, from each stock's
`fit_audit.params`. The warp is `basis(p + (λ − p)/w − s)`, whose peak lands at
`p + s·w`, so these are not peak displacements:

| Statistic | Cyan | Magenta | Yellow |
|---|---|---|---|
| Mean | +21.46 | +4.58 | +5.58 |
| Minimum | +14.93 | +2.29 | +4.23 |
| Maximum | +25.00 (bound) | +9.22 | +7.87 |
| Negative values | none | none | none |

The derived peak displacements, from `fit_audit.peak_shift_nm`, are the
quantity to use for any cross-stock comparison:

| Statistic | Cyan | Magenta | Yellow |
|---|---|---|---|
| Mean | +22.85 | +4.27 | +5.74 |
| Minimum | +14.31 | +2.03 | +3.87 |
| Maximum | +28.28 | +8.17 | +7.61 |
| Negative values | none | none | none |

**Several stocks move their cyan peak FURTHER than the 25 nm the bound
nominally permits**, because the peak lands at `p + s·w` and `wC` rests on the
1.15 ceiling for six stocks (Ektar 100, Fujicolor 100, Gold 200, Portra 400,
Superia Premium 400, Ultra Max 400).

Two of the twelve pin `sC` at +25.00, Fujifilm 200 and 400, which share one
chart; Pro 400H pinned it too on a 400–700 nm fit, reaching a peak displacement
of 28.7 nm, and its shipped fit, with the traced red tail admitted (§4d-ter),
rests free at +14.93 with the magenta width `wM` on its 1.15 bound instead. Pro
Image 100 sits at +24.9965, free of the bound, and reaches 28.28 nm; Ektar 100,
Ultra Max 400 and Portra 400 exceed 25 nm through the width alone. Fujifilm 200
and 400 are the exception in the other direction, pinning `sC` while `wC` rests
on 0.85, so their peaks move only 21.25 nm.

The smallest displacement in the fleet is Pro 400H's at 14.31 nm, then Fujicolor
100's at 17.40 nm. Nine of the twelve records carry at least one pinned
parameter. See PROJECT.md register entry 12.

**Thirty-six shifts out of thirty-six are positive.** Register entry 8 describes this for
cyan alone. Magenta and yellow are smaller but equally unanimous, and the
register should be read as understating the effect: the whole C-41 dye set, cyan
included, sits to the red of the Vision3 basis.

### 4b. Tracing error cannot explain it

The obvious competing explanation is a wavelength-axis calibration difference
between the raster-traced Vision3 sheets and the vector-traced Kodak C-41
sheets. The repository already contains the control that bounds this. Ektachrome
E100's `cross_validation` block compares the **vector** E100 chart against the
**independently traced raster** 100D chart for the same emulsion, and reports a
best-fit lateral shift of **0.5 nm in cyan, 1.0 nm in magenta and 1.5 nm in
yellow**, at RMSE 0.0063–0.0113 D.

That is the same vector-against-raster comparison, on the same digitising
machinery, and it lands within 1.5 nm. A mean cyan displacement of 24 nm is an
order of magnitude larger. **What the control excludes is a common, large
raster-against-vector axis offset.** It calibrates that one pair of charts; it
does not independently calibrate each Vision3 raster or each C-41 sheet, so a
sheet-specific axis or tracing error remains possible and needs its own
control. Fit uncertainty (§4c) and chart-axis uncertainty are separate terms
and are kept separate here.

A second digitisation-side term is not bounded by this control. PROJECT.md
register entry 14 records that interior columns of the Vision3 trace take a
tracker prediction in place of a measurement, at 0.4–5.2% of columns for most
curves and up to 22.9% on one, and the ink-hit overlay cannot see it because a
crossing supplies the neighbouring curve's ink. That term sits on the basis side
of exactly this fit.

### 4c. The fitted cyan peak is not resolved by the data

For eleven of the twelve C-41 stocks the shipped cyan argmax lands exactly on
700 nm, the last point of the output grid; Pro 400H's lands at 699 nm. Adding
`peak_shift_nm` to the basis peak of 685 nm places the modelled peaks at
699.3–713.3 nm, **eleven beyond the grid entirely** and Pro 400H's at
699.3 nm, so on eleven stocks the fitted cyan curve is still rising at 700 nm
and the peak is not represented in the shipped curve. These are properties of
the fitted model; no isolated dye maximum was measured.

The multistart's optima are what make this near-universal: in the single-start
population of 2026-08-16 a fixed start of the same fit placed the modelled peaks
at 691.8–708.2 nm, with three beyond the grid and seven still rising, and the
strictly better-fitting optimum on every stock was the one that sat further
outside the measured data (from `fit_audit.multistart` of that population).
For Ektar 100 the 700 nm grid edge already lies 15.1 nm beyond the 684.9 nm
limit of that sheet's measured support.

A fitted peak wavelength that sits at the edge of the grid is an extrapolation
from the curve's flank and must not be quoted as a physical property of the
emulsion. This is the concrete form of the under-determination that register entry 8
warns about when a stock pins more than one bound.

### 4d. Stored support and the guarded 700 nm grid

**Current implementation.** The fit intersects chart audit support with
stored-array support, clamps both limits, rejects missing audit metadata for
canonical runs, and prints the fitted interval separately. Raising the grid
therefore cannot silently admit zero-filled samples through the audited fit
mask. The experiment below describes an unguarded extension and motivates the
existing guard; it is not a current defect.

`portra_decompose.py` defines `GRID = np.arange(400, 701, 1.0)`. The
support-based fit mask can narrow that range but never extend it, so 700 nm is a
hard cap on both the fit and the output.

Neither side of the fit requires that cap:

- The **Vision3 basis** is traced to **798 nm**, with cyan still at 0.149 of
  peak at the far end. The endpoint itself is real ink, trailing predicted
  columns being rolled back, though interior columns may be tracked
  predictions; see register entry 14.
- The **Fujifilm sheets** are digitised well past 700 nm: Fujifilm 400 to
  717.7 nm, Fujicolor 100 to 719.1 nm, Superia Premium 400 to 719.2 nm, and
  Pro 400H and Fujifilm 200 similarly.

So the Fujifilm **sheets** were traced 17 to 19 nm past 700 nm, in precisely the
band that would constrain the cyan peak, while the basis has measured values
across the same band.

**The canonical arrays do not carry it.** Every
`data/films/*_datasheet_curves.json` stores its `spectral` arrays on a 400.0 to
700.0 nm grid at 1 nm, 301 points, without exception, and that is the grid
every consumer reads. The five Fujifilm-family files carry the traced tail
beside it in a second block, `spectral_full_support` (400 nm to the traced
end, null outside each curve's own trace); §4d-ter is what it shows. The
`digitization_audit.spectral_dye_density.endpoints` block records the traced
support for every stock.

This produces a genuine mismatch. **The five Fujifilm-family stocks record an `endpoints`
upper limit that lies beyond the end of their own stored array:**

| Stock | Array ends | `endpoints` hi | Beyond array by |
|---|---|---|---|
| Superia Premium 400 | 700.0 nm | 719.08 nm | +19.1 nm |
| Fujicolor 100 | 700.0 nm | 718.66 nm | +18.7 nm |
| Fujifilm 200 and 400 | 700.0 nm | 717.51 nm | +17.5 nm |
| Pro 400H | 700.0 nm | 716.88 nm | +16.9 nm |
| Portra 400 / 160 / 800, Ultra Max 400, Gold 200, Pro Image 100 | 700.0 nm | 699.5–700.0 nm | none, on or inside the array end |
| **Ektar 100** | 700.0 nm | 684.91 nm | none, correctly inside |

`portra_decompose.py` builds its fit mask from `endpoints`, then intersects it
with `GRID`. Ektar is the case the mechanism was designed for, where `endpoints`
falls **inside** the array and correctly excludes the flat-held 685–700 nm tail.
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
its `endpoints` limit of 684.9 nm is already inside the array, and its perfect
invariance confirms the harness only.

**The guard now in place.** `portra_decompose.py` intersects both audit
support limits with the stored array's span (`_lo = max(_lo, swl.min())`,
`_hi = min(_hi, swl.max())`) before building the fit mask, so `endpoints` can
never reach past stored data whatever `GRID` is set to; a stock whose curves
file carries no usable audit block refuses to run a canonical fit
(`--allow-unaudited-support` is exploratory and requires `--out-suffix`).

The experiment above was run against the earlier mask, which took `endpoints`
unclamped, and is kept as the measurement of what the zero fill would cost;
under the current guard raising `GRID` alone changes nothing. The measured
tail enters only through `spectral_full_support`, as extra residual terms
against measured samples: the shipped Pro 400H fit admits it (registry
`fit_traced_tail`, §4d-ter), the other eleven canonical fits do not, and the
unpublished fit-ensemble diagnostic reads it for the whole family. No fit
evaluates the model on zero-filled samples.

### 4d-bis. How much does the band buy, measured from inside 400–700 nm?

One measure of the band's influence pulls the top of the fitted band back
through real measured data from 700 nm to 670 nm and watches the fitted cyan
shift. No fabricated point enters any of these fits.

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
bounds, under which two of the twelve stocks pin `sC` at +25.00 and nine of
the twelve rest on a bound of one kind or another, as `fit_audit.bounds_pinned`
and PROJECT.md register entry 12 record.

What the cut establishes is bounded by its design: it REMOVES measured data
from 700 nm downward and finds those two fits unmoved, so they are insensitive
to those particular deletions. It does not test what independently measured
samples ABOVE 700 nm would do; that test is §4d-ter, which admits the traced
tail and finds the Fujifilm 200/400 pin unchanged. Two further facts sit beside
it without settling it: the two stocks' dye chart is shared byte-for-byte
between two datasheets, so the pair contributes one measurement, which is a
limit on the DATA and no demonstrated cause of the optimiser's bound hit; and
two product names sharing one chart is not proof that they share dye chemistry,
only that the sheets do not distinguish them.

What the sweep does establish is more general and more useful: for several
stocks the fitted cyan shift is partly a property of **where the fitted band
stops**. That is a direct measurement of the
under-determination register entry 8 warns about, and it reinforces the rule there
that a pinned or extreme cyan shift is evidence about the basis and never a
property of the film.

**What the script reports.** Its stdout names the range actually fitted, the
audit span intersected with the stored array ("over the MEASURED support
399.8-700.0 nm (audit span intersected with the stored 400-700 nm array)" for
a Fujifilm-family stock), so the fitted range and the digitised range are
distinguished in the report. The `digitization_audit` block of each
`data/films/*_datasheet_curves.json` still records the wider digitised support
(to 719 nm on Superia Premium 400); that is the record of the traced chart, and the shipped `*_dye_density.json` files carry the
phrase "over the MEASURED support" without a range.

### 4d-ter. The recovered tail as a withheld band

The five Fujifilm-family `spectral_full_support` blocks hold 16 to 19 traced
samples above 700 nm (four independent charts, Fujifilm 200 and 400 sharing
one). The canonical fit, solved on 400–700 nm only, is evaluated on them, and
then re-solved with them admitted under the same basis, bounds and seeded
starts. The measured aggregate reaches its red-region maximum at or just before
the band on every sheet, 694 nm Fujicolor 100 (a local maximum; the global
one is the 454 nm yellow lobe), 696 Pro 400H, 701 Fujifilm 200/400, 705
Superia Premium 400, so the withheld samples lie on the turnover and the
descent.

| Stock | Withheld RMSE | In-band RMSE | Cyan peak, canonical → with tail | sC | In-band cost | Tail RMSE after |
|---|---|---|---|---|---|---|
| Fujifilm 200 / 400 | 0.0041 | 0.0179 | 706.3 → 706.3 nm | +25.00 pinned, stays | none | 0.0033 |
| Superia Premium 400 | 0.0070 | 0.0196 | 707.9 → 707.6 nm | +19.90 → +19.67 | none | 0.0038 |
| Fujicolor 100 | 0.0491 | 0.0207 | 702.4 → 699.0 nm | +15.13 → +12.33 | 0.0207 → 0.0216 | 0.0216 |
| Pro 400H | 0.0525 | 0.0107 | 713.7 → 699.3 nm | +25.00 pinned → +14.93 free; wM → 1.15 pinned | 0.0107 → 0.0109 | 0.0021 (training) |

Two readings.

- Where the withheld error is below the in-band error, the aggregate
  extrapolation is corroborated, and a pinned +25.00 (Fujifilm 200/400) is
  consistent with samples it never saw; no independent cyan component is
  identified by that.
- Where it was not, the model overshoots the band by 0.045 to 0.050 D mean, the
  cyan placed too far red.

Pro 400H's pin is an artefact of a bimodal objective: holding the cyan shift
fixed and refitting the rest gives a second basin at sC +14 to +15 (peak
698–699 nm) only 2.4% worse in residual than the pinned one, and the tail
selects it at a 2% in-band cost, moving the cyan curve by 0.038 D mean; the
refit's magenta width lands on its 1.15 bound, and its tail residual is training
error. Fujicolor 100's tail residual after refit (0.022) stays at the in-band
level, which suggests a mismatch of the warped form at the turnover; whether the
form can describe the true spectrum waits on the source-uncertainty analysis.

Fixed-shift profiles across the fleet (1 nm steps, tolerance crossings bisected
to 0.05 nm, excess against the unrestricted optimum; sampled estimates) put the
cyan peak within 0.6 nm on Fujifilm 200/400, 3–7 nm on six further stocks and
12–17 nm on four (Portra 160, Portra 800, Pro Image 100, Pro 400H) at 5%
residual tolerance; the same four move 11–16 nm across the four individual
Vision3 stock bases and the family average, the other eight under 3 nm:
ambiguity across every chart–basis combination tested. Status M density of the
reconstructed midscale spreads at most 0.014 D (red) across any of those sets,
which is closure of the sum, a range across reconstructed midscales.

A different statistic, the maximum deviation from the canonical conversion:
inverting each member's dye set on identical scan densities (216 dye-amount
triplets, LEDs behind the stock's D-min, unity sensor, common valid population)
deviates Status M on unequal-amount inputs by up to 0.089 D in green (Portra
160), 0.05–0.07 D on Pro 400H, Portra 800, Superia Premium 400 and Pro Image
100, and 0.003–0.04 D on the rest; equal-amount inputs (not a photographed
neutral, the curves being independently normalised) by 0.003–0.046 D. The two
are reported side by side.

The Pro 400H tail refit is the shipped fit (registry `fit_traced_tail`; the tail
enters as extra residual terms, the curves stay on 400–700 nm). Against the
cubes from the 400–700 fit, the Status M cube's equal-scan-density diagonal (not
thereby a photographed neutral) moves 0.010 D mean, 0.022 max, and its
unsaturated working range a median of 0.013/0.008/0.005 D R/G/B (90th percentile
0.041/0.034/0.011); the Fuji print cube's diagonal moves at most 0.007 in
Display P3 encoding, its working range a median of 0.001–0.003 (90th percentile
0.006/0.014/0.045), and the gray lock is unchanged; on a common working-range
population the two dye sets agree where both solve (residual mean 0.0002 D) and
differ in reach (62.1% against 60.2% of sampled nodes solvable).

The other four Fujifilm-family stocks keep the 400–700 fit: Fujifilm 200/400 and
Superia move under 0.3 nm with the tail admitted, and Fujicolor 100 has no
withheld validation to admit it on.

### 4e. The red LED sits on the cyan flank for negatives, and near the peak for reversal

This project scans at 640 / 544 / 450 nm. Measured against the shipped
peak-normalised cyan curves:

| Stock | Cyan at 640 nm | Cyan peak |
|---|---|---|
| Portra 400 | 0.6616 | at or beyond 700 nm |
| Ektar 100 | 0.6713 | at or beyond 700 nm |
| Ektachrome E100 | 0.908 (of a 0.948 peak) | 658 nm |

(Read 2026-09-09 from the shipped peak-normalised `shared_full_curves` cyan
arrays, which are the multistart fits after the dye-axis recalibration; the
same read on 2026-09-02 gave 0.649 and 0.650, and the single-start fits of
2026-08-16 read 0.645 and 0.671. The figure moves with the model state and
must be re-read on each use.)

For the negative stocks the red probe sits on the steep rising flank of the
cyan absorption, where the local slope is approximately **+0.008 per nm**. As a
first-order illustration, a rigid 10 nm translation of the curve would move the
modelled cyan density at the red LED by about 0.08 in peak-normalised units,
close to a tenth of peak; a 10 nm change in the fitted peak is not in general a
rigid translation, since the fitted shift, width and amplitude are correlated.
Across the fleet the fitted cyan peak displacement spans 14 nm (14.3–28.3 nm,
§4a).

For reversal the same probe sits near the cyan maximum, on a flat part of the
curve, where peak-position error is far less consequential.

**This connects two facts the register keeps separate**: cyan is both the least
determined parameter of the C-41 fit and the dye whose flank the red probe
sits on. It is not a defect in the LED choice, which is constrained by
available hardware and by channel decoupling. The local slope is an
illustrative derivative and no ranking: the real channel integrates a finite
LED band, the sensor response and the mask, so whether cyan error propagates
more strongly than magenta or yellow error through the full inverse requires
matched perturbations of all three dyes through the integrated scanner model
and its inverse, over one valid population, with residuals, conditioning and
failed solves reported. That measurement has not been made.

Independently, Chatterjee et al. (2023) chose narrowband capture at **672 / 544 /
447 nm** for multispectral film digitisation. The green and blue choices are
within 3 nm of this project's; the red is 32 nm further into the red.

### 4f. The orange mask is a directly traced, basis-independent source of variation between the stocks

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
| Portra 400 | 0.8179 | 0.6034 | 0.1952 | 0.6227 | 1.525 |
| Portra 160 | 0.8183 | 0.6188 | 0.1757 | 0.6426 | **1.450** |
| Ektar 100 | 0.8652 | 0.5983 | 0.2170 | 0.6482 | 1.700 |
| Pro Image 100 | 0.9673 | 0.6726 | 0.2769 | 0.6904 | 1.745 |
| Gold 200 | 0.9844 | 0.6361 | 0.2470 | 0.7374 | 1.895 |
| Ultra Max 400 | 0.9777 | 0.5880 | 0.2292 | 0.7485 | 2.086 |
| Portra 800 | 0.9941 | 0.5850 | 0.2188 | 0.7753 | **2.117** |
| Pro 400H | 1.0351 | 0.6996 | 0.2101 | 0.8250 | 1.685 |
| Fujifilm 200 and 400 | 1.0430 | 0.5848 | 0.0963 | **0.9467** | 1.938 |

**The spread is 0.346 D**, from 0.6005 to 0.9467. For orientation, beside the
other density-valued quantities this project reports:

| Quantity | Magnitude |
|---|---|
| Basis sensitivity of the dye decomposition | 0.032–0.063 D |
| Inter-stock distances between fitted dye sets | 0.021–0.219 D |
| C-41 process-control tolerance (Z-131) | ±0.03–0.09 D |
| **Mask-strength spread across the fleet** | **0.346 D** |

These four share a unit and nothing else: a fleet-wide range of a
two-wavelength proxy, a sensitivity to a handful of alternative bases, a
spectral shape-distance statistic between fitted dye sets, and a
densitometer's control-strip limits are different observables over different
populations, so their ratios are not measures of discrimination and no
"order of magnitude" follows from them (even the raw ratio of the proxy range
to the largest inter-stock dye distance is 0.346/0.219, about 1.6).

What the table supports is the statement made in the heading: the traced D-min
spectra provide a stock-dependent input independent of the surrogate dye fit,
and their two-wavelength proxy varies substantially across the fleet. Its
contribution to distinguishability, and any ranking of it against the dye-set
differences, must be assessed in a common output metric on a common patch
population; no such ranking is made here. §4f-bis is the first step, in the
print cube's own ΔE.

The shape differs as well as the scale: the ratio (B−R)/(G−R) runs from 1.450 on
Portra 160 to 2.117 on Portra 800, so the mask's spectral profile is itself a
per-stock property, within what a three-wavelength ratio can say about shape
(§4f-bis).

The ordering is broadly coherent with Bergthaller's account. The slower
professional Kodak stocks carry the weakest masks, Portra 400 at 0.623, Portra
160 at 0.643 and Ektar 100 at 0.648, while the consumer and older formulations
carry among the strongest, Gold 200 at 0.737, Ultra Max 400 at 0.749 and
Fujifilm 200/400 at 0.947 – though Portra 800, professional but fast, sits at
0.775, above both Kodak consumer stocks. That is the pattern expected if
premium films have moved to
pyrazolotriazole magenta and need less yellow masking coupler. **It is a
consistency and no proof:** no datasheet names a coupler class, and the
inference from mask strength to coupler chemistry is not something these data
can close.

**How far this reaches into the deliverables is a separate question, measured
in §4f-bis.** The print branch is one engine, `PrintEmulationEngine`, presented
as `endura_print_engine.py` for the seven Kodak stocks on Endura Premier and
`fuji_print_engine.py` for the five Fujifilm stocks on Fujicolor Pro Laser TYPE
II; each engine's `--stock` choices enforce the pairing. It builds the negative
as `N(λ) = dmin_spec(λ) + Σ dye · DYE(λ)` and reads `dmin_spec` from each
stock's own digitised curves, so a strongly stock-dependent term does enter the
print branch, and it owes nothing to the surrogate basis. It does not follow
that the shipped print cubes differ by anything like 0.346 D.

The engine applies a full per-channel **gray-axis lock**
(`solve_gray_axis_lock`), constructing for each channel a monotone,
intensity-dependent mapping from raw to required log exposure so that the
model's neutral response follows one master curve over the calibrated range.
That is more freedom than the fixed per-channel light offsets of a printer's
colour balance, and it is a rendering and calibration choice of the model; it
should not be equated with printer balancing, and it does not validate a real
print's neutral scale. **The lock absorbs the per-channel component of any mask
difference along the neutral axis by construction.**

What can survive it is the part a per-channel scalar cannot represent: the
mask's spectral shape *within* each of the paper's three sensitivity bands, and
its consequences away from the neutral axis. The shape variation measured above,
with (B−R)/(G−R) running 1.450 to 2.117, is real and is exactly that kind of
term, and §4f-bis measures its effect within the stated model experiment.

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
construction of the lock, within this model; whether an optical print balanced
with fixed printer lights achieves the same compensation across the scale is
not tested here, and would take a measured print or a fixed-trim model on the
same negative and paper for comparison. Equal Status A densities are also not
the same criterion as visual neutrality, for which the engine offers a
separate option.

**Off the neutral axis the mask survives.** For realistic stock pairs 13–20% of
nodes exceed 1 ΔE2000, reaching 3.6–5.5 ΔE2000 at saturated colours.

**The contrast points to shape.** The last two rows are diagnostic pairs chosen
to separate the two. Ektar 100 → Pro 400H changes mask strength by 0.173 D with
essentially no change of the three-wavelength shape ratio, and yields 1.2% of
nodes above 1 ΔE and a maximum of 1.55. Fujicolor 100 → Superia Premium 400
changes strength by 0.009 D, **nineteen times less**, while changing the ratio
by as much as the extreme pair, and yields 18.8% and a maximum of 4.02.

Two limits keep this suggestive: the two swaps sit on different stock
backgrounds, so they are not a controlled isolation of shape from strength; and
(B−R)/(G−R) is three wavelengths, which does not establish that two masks are
alike or different WITHIN each of the paper's sensitivity bands, nor does a
scale change of a non-flat spectrum leave the transmitted spectral weighting
unchanged.

This is coherent with the mechanism: a per-channel scalar lock can compensate
the mask's overall level in each band but cannot compensate how the mask density
varies **within** a band, and it is that within-band profile which reaches the
print.

**Conclusion.** The orange mask is the first demonstrated mechanism by which
this project's C-41 print cubes discriminate between stocks. It is
basis-independent, it is measurable in the input data at 0.346 D, and it reaches
the deliverable at up to 5.50 ΔE2000 on saturated colours (the extreme pair;
1.55–4.02 on the other three), with the grey ramp held to 0.131 ΔE2000 or
better on every pair.

The swaps above are a controlled mask-only experiment run inside a single
engine, and therefore measure the mechanism alone: three of the four cross a
paper brand that the pairing rule forbids, and no equivalent measurement exists
for the Pro Laser lock. The corresponding limitation is equally clear: it
contributes nothing on or near the grey axis, so no claim about neutral
rendering may rest on it.

Three caveats travel with this measurement:

- D-min is the **whole** film base, comprising support tint and both the yellow
  and the pink masking couplers. B − R is a proxy for total mask strength and
  does not isolate the yellow masking coupler. A spectrally neutral support
  cancels exactly in a two-wavelength difference; what survives besides the
  couplers is any support tint, which is not neutral, and the trace's own
  noise at the two wavelengths.
- **Fujifilm 200 and 400 are identical by construction**, sharing one dye chart,
  so they contribute one measurement, and their extreme position
  should not be over-read.
- These are published D-min values for fresh film. Differential dye fading (§8)
  does not affect unexposed D-min in the same way it affects image dye, but the
  masking couplers are themselves dyes and are not immune.

---

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

---

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

One qualification on the "matrix treatment": a linear relation between spectral
response channels holds before the logarithm is taken, and a matrix applied
directly between density triplets is a material- and range-dependent
approximation unless further conditions establish it (the Academy note, §4,
states the counterexample). The decomposition here is spectral, so the
qualification bears on how its results are compared with matrix conversions and
leaves the fit itself untouched.

---

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

1. Interimage and masking are alternatives to signal-domain correction. A negative that has already been developed carries its
   interimage effect in the measured densities, which is the argument recorded in
   `interimage-effects-and-stock-differentiation.md` §5.4.
2. The patent describes films designed **without** a mask for scanning. Every
   stock in this fleet is a conventional masked negative, so that design case
   does not apply here, but it clarifies what the mask is for.

---

## 8. Dye fading (tier B)

Chromogenic dyes fade selectively in dark storage. Chatterjee et al. observe,
in their samples of late-1970s Kodak material, "yellow and cyan dyes
substantially faded, while the magenta dye is always well-preserved"; their
§2.2.2 also describes substantial differences between samples, one of which
retains its yellow. That is a case study of selected historical samples, and
the archival-sector generalisation that cyan and yellow fade before magenta is
tier B here: fading behaviour depends on stock and storage conditions, and no
per-stock rate has been established by this project.

The relevance here is a scope boundary. Every curve in `data/` describes
**fresh** film as published by the manufacturer, while any real scan is of film
that has aged since exposure. None of this project's transforms model aging, and
no figure held here says how small the change is for recently processed
material.

Chatterjee et al. is the reference for what modelling it would involve, namely
per-dye scalar fading factors solved against a known neutral; their §2.2 adopts
scalar fading of fixed spectral shapes as an assumption, and their adopted
density-addition approximation is not independent empirical validation of this
project's spectral model.

No quantitative fading rate per dye was found in either paper.

---

## 9. Open questions and material not found

- **No measured λmax for any C-41 or ECN-2 dye was located.** Silva et al. covers
  E-6 only. The cross-process comparison in §3c therefore rests on datasheet
  tracing for the negative processes and on laboratory measurement only for
  reversal.
- **The magnitude of the CD-3 against CD-4 spectral difference is unquantified.**
  No source obtained gives absorption maxima for the same coupler developed in
  both agents, which is the measurement that would settle §1.
- **Which magenta coupler class each stock uses is not published.** D-min can be
  traced per stock without identifying that class; attributing its variation to
  a particular chemistry requires additional evidence.
- **Whether Fujicolor 100 should also fit its traced tail is undecided.**
  Admitting it moves the cyan peak 702.4 → 699.0 nm at 0.0207 → 0.0216 D
  in-band and leaves a 0.022 D tail residual, with no withheld check left to
  judge it by. Status M red responsivity is itself truncated at 700 nm here,
  so a fitted tail constrains the fit and does not enter the Status M
  integral.
- **Which magenta coupler class each current stock uses remains unpublished**,
  and §4f infers only a consistency. Confirming it would need a
  chemical method of the kind Silva et al. used, applied to current C-41 stock.
- **Whether the measured off-axis mask difference is CORRECT is untested.**
  §4f-bis establishes that the mask reaches the print cubes and by how much;
  whether the resulting colours match a real print is unestablished. The D-min spectra driving it
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

---

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
