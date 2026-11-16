# Film scanner spectral calibration pipeline

A spectral calibration pipeline for a camera-based film scanner with narrowband
sequential red, green and blue LEDs at 640, 544 and 450 nm, the only supported
mode. It converts raw scanner density into externally defined density metrics,
so that grading in DaVinci Resolve begins from a defined quantity.

The release carries nine builds of the scan tables: one general monochrome
build (no colour filter array, constant spectral response, which cancels out
of a density measurement), one sensor-specific monochrome build on the
published response of one measured assembly, and one for each of seven Bayer
cameras, built on the body's measured spectral sensitivity. The general
monochrome build is the weaker set for a camera that has a sensor-specific
one. A response that varies across an LED's band does
not cancel and is carried as a labelled scenario (register #9). Any other body
is named at build time.

| Family | Stocks | Target |
|---|---|---|
| Reversal / E-6 | Velvia 100/50, Provia 100F, Ektachrome E100/100D | D50 white-relative colorimetric density (CIE 1931 2° XYZ): the transparency on a D50 light table |
| Negative / ECN-2 | Vision3 50D/200T/250D/500T | ADX16 (ST 2065-3) over Academy Printing Density (ST 2065-2), one stock-blind table into an ACES timeline; secondary per-stock scene-linear DaVinci Wide Gamut (D65) |
| Negative / C-41 | twelve still stocks, Kodak and Fujifilm | Status M density, then RA-4 **print emulation** to Display P3, the sole delivery route |

- **ECN-2, ADX16.** Locus Stock applies the stock's grey trims, so a
  datasheet-exposed 18% grey decodes to 0.18 in ACES. The per-channel
  printer-light trims, dialled on a known neutral, absorb the rig and the roll.
  The ACES output transform sets the display brightness. Resolve's built-in
  "LMT Kodak 2383 Print Film Emulation" may follow.
- **ECN-2, scene route.** A per-stock, model-based estimate of relative scene
  exposure from the stock's own characteristic curves, and the path for graded
  work. It is the model reference the ADX16 route is scored against
  (ColorChecker ΔE2000 6–7 mean after the printer-light trims). No frame has
  been checked against a known scene.
- **C-41.** A "stock" denotes a dye set together with a D-min spectrum (the
  unreacted coloured coupler of the Glossary), never a tone curve.
- **Status A** appears in two places: the inversion of RA-4 paper
  reflection-density curves, and the reversal builds' closure against their
  sheets' characteristic curves (register #19). No cube lands on it.

A collaborator's calibration tool, DiVERE, and their capture setup inform the
apparatus parameters. This pipeline is independently constructed.

## Contents

- [Current status](#current-status)
- [Glossary](#glossary)
- [Repository layout](#repository-layout)
- [Hard constraints (do not relax these)](#hard-constraints-do-not-relax-these)
- [Source data (`data/`)](#source-data-data)
- [How a transform works](#how-a-transform-works)
- [Per-roll anchoring](#per-roll-anchoring)
- [Engines and script reference](#engines-and-script-reference)
  - [C-41 fleet discrimination gap](#c-41-fleet-discrimination-gap-the-most-important-caveat-in-this-document)
- [Current state by stock](#current-state-by-stock)
- [Bounded systematics register (everything currently known and unpatched)](#bounded-systematics-register-everything-currently-known-and-unpatched)
- [The role of NamiColor in this project](#the-role-of-namicolor-in-this-project)
- [Invariants](#invariants)
- [Known limitations](#known-limitations)
- [End-to-end error budget](#end-to-end-error-budget)

## Current status

| | State |
|---|---|
| Reversal | 4 stocks, complete |
| ECN-2 / Vision3 | ADX16 cube as the route into ACES; 4 per-stock scene-linear cubes as the secondary, scene-referred path |
| C-41 | fleet complete at 12 stocks, each with a print emulation |
| Qualitative use on real film | **passing**: in use, behaving as intended |
| **Quantitative validation** | **none. This is the open gate** |

Two facts qualify every number in this document.

1. **The chain functions, although no number within it has been checked
   against a measurement.** Every figure here is a model reporting on itself
   (Known limitations). Quantitative validation is a grey-ramp exposure series,
   a ColorChecker frame and spectrally read separation wedges, each compared
   against reference values.
   - One external check agrees with the model: Portra 160 and Portra 400 print
     extremely close in a real darkroom (user report). It has little power,
     because both stocks are fitted against the same surrogate basis. It tests
     the mask and the characteristic curves, and leaves the dye model untested.
   - One ECN-2 check reaches a quantity measured outside this repository
     (`annexc_check.py`): the Vision3 dye model against the Academy's Status M
     to APD matrices for 5207 and 5219. Worst per-channel mean absolute
     disagreement over the traced neutral series is 0.018 D on each stock's own
     dye set, against a project threshold of 0.02 D (the expected error the
     document states over its 97 measured patches, a different population).
     Per-point maxima reach 0.035 D. The family basis gives 0.024 D, reported
     and ungated. The scan side is untouched by it.
2. **The fleet cannot distinguish every stock from every other.** Basis
   sensitivity is 0.027–0.049 D; inter-stock distances run 0.021–0.219 D. 16 of
   the 66 pairs sit inside the ambiguity band; the remaining 50 are separated
   by more than the basis prior can account for. Datasheet-level comparisons
   are basis-independent and hold; per-stock *rendering* differences largely do
   not. See "C-41 fleet discrimination gap".

### Evidence classes

| class | meaning |
|---|---|
| **measured** | read from a manufacturer's published chart, or measured on this apparatus |
| **computed** | a numerical property of this repository's software, obtained by running an engine over the measured data; it establishes implementation consistency and model sensitivity, never physical accuracy |
| **derived** | a model output, correct only to the extent its inputs and its model are |
| **assumed** | a choice made without a measurement behind it |
| **unverified** | asserted, and never checked against anything |

| quantity | class |
|---|---|
| digitised characteristic curves, spectral dye densities, D-min spectra | measured; tracing bounded by register #13 |
| LED spectral power distributions | measured, on this apparatus |
| camera-filter transmission | measured, traced from the manufacturer's raster chart; no engine reads it |
| WRATTEN 2 filter densities | measured, traced from Kodak's vector charts, censored above 3.0 D; only the tricolor kernel reads them |
| the 47B filter of that kernel (No. 98 less No. 2B in density) | **assumed**, a proxy from a catalogue equivalence |
| mask-filtered scan illuminant `LED × 10^−Dmin(λ)` | derived from the traced D-min spectrum; register #17 |
| the four Vision3 Minimum Density curves | measured; cross-checked against the characteristic sheet's D-min triplet to within 0.045 D |
| C-41 dye-set samples on the basis's held blue edge | **assumed**; `fit_audit.basis_held`, register #18 |
| three-dye decomposition and every per-layer curve | derived; register #8 |
| Status M, print and reversal cubes | derived |
| aggregate fit residual, node-solve residual, serialisation figures | computed |
| Vision3 Status M to APD relation for 5207 and 5219 | computed against S-2008-002 Annex C: worst per-channel mean absolute disagreement 0.017 D on the stock's own basis, gated at 0.02 D; signed mean and per-point maxima ungated, 0.018 D and 0.035 D; family basis 0.024 D mean absolute, maxima to 0.037 D, ungated; a FAIL exits nonzero |
| end-to-end error budget | derived, from computed perturbations |
| surrogate Vision3 basis standing in for C-41 couplers | **assumed** |
| uniform ±25 nm shift bound; per-dye width bounds, cyan 0.85–1.15, magenta and yellow 0.5–2.0 | **assumed** |
| `DMAX = 3.30`, the negative corridor | **assumed**, with the requirement computed |
| `DIR_MATRIX = identity`, interimage disabled | **assumed**; harmless where a transform ends in a density; a modelling assumption on the Vision3 scene route, which the neutral series cannot choose (Known limitations) |
| each Vision3 layer responds off the neutral series as its neutral-series amount table; the sheet's spectral sensitivity is an exposure-invariant additive kernel | **assumed** |
| integrated density is linear in the dye amounts, each unit spectrum fixed at all concentrations | **assumed** by every `density()` forward; the Vision3 midscale closure samples one density level (RMS 0.006–0.012 D with D-min subtracted) and cannot test it |
| 3200 K blackbody lamp of the Endura tricolor kernel | **assumed** (nominal); band weights are calibrated model parameters |
| Pro Laser kernel, 473/532/685 nm | 473 and 532 nm **documented** Frontier lines; 685 nm **assumed**, tested at 650 and 688 nm as scenarios outside the budget totals; line powers calibrated |
| grey-axis lock's mid-grey intent, Y = 0.18 at input k = 0.22 | **assumed** |
| D50 viewing with CAT02 to D65 for the print render; D50 for the reversal target | print viewing **documented** as about 5000 K by every paper sheet; a D65 view differs by ΔE00 median 0.77, 0.016 on the neutral axis |
| a negative's effective dye curves, negative samples included, scale with dye amount | **assumed**; traced on Vision3, inherited on the C-41 surrogates |
| print colorimetry over the dyes' measured 400–700 nm only, normalised to that band's white | **assumed** (rendering convention); unmeasured bands are sensitivity scenarios (Known limitations) |
| the rendered cast of a frame matches its physical illuminant | **unverified** on film; hard constraint 5 guarantees only that no stage neutralises it |
| any part of the C-41 chain matches a physical reference | **unverified**, the open gate |

Per-datum provenance lives in the data:

- all twenty `*_datasheet_curves.json`, fifteen `*_spectral_sensitivity.json`
  and sixteen `*_mtf.json` carry a `digitization_audit` block (source sheet,
  device-to-data transform, measured support);
- the twelve C-41 `*_dye_density.json` carry a `fit_audit` block (basis, bounds,
  parameters resting on a bound, multistart);
- the four per-stock Vision3 `*_dye_density.json` carry a `digitization_audit`
  block;
- the reversal `*_dye_density.json` carry neither block, since their per-layer
  curves are traced directly. The reversal path therefore does not inherit
  register #8.

## Glossary

**Photographic image formation**

| | |
|---|---|
| **Emulsion layer** | one of the three light-sensitive coatings, sensitised to blue, green or red |
| **Coupler** | reacts with oxidised developer to form image dye: yellow, magenta and cyan from the blue-, green- and red-sensitive layers |
| **C-41 / ECN-2 / E-6 / RA-4** | still colour negative / motion-picture negative (Vision3) / colour reversal / colour paper process |
| **E-6 detail** | a first developer forms a negative silver image, the remaining halide is fogged, and a colour developer forms dye where no silver formed: a POSITIVE. No orange mask; interimage is its principal correction of unwanted dye absorption (register #11) |
| **Orange mask** | neither a layer nor a filter. The magenta- and cyan-forming couplers are *coloured* (yellow and pink) and are consumed where image dye forms. The cast is the coupler that did NOT react: a POSITIVE image, maximal at D-min, whose absorption completes the image dyes' unwanted absorptions to a nearly constant sum at every exposure. Removing it and correcting the film are different operations. Source: `knowledge/orange-mask-and-the-scanning-workflow.md` (Hanson, JOSA 40(3):166, 1950) |
| **DIR coupler** | Development-Inhibitor-Releasing coupler, the chemistry underlying interimage effects |
| **Interimage / IIE** | inhibition of one layer's development by a neighbour. `IIE%` is the gamma difference between a colour-separation exposure and a neutral one |

**Density and sensitometry**

| | |
|---|---|
| **OD** | optical density, −log₁₀(transmittance or reflectance) |
| **D-min / D-max** | least and greatest density. On a negative, D-min is the unexposed base with the orange mask |
| **H&D curve** | characteristic curve: density against log exposure; its slope is gamma |
| **logH / logE** | log exposure, used interchangeably |
| **Status M** | ISO 5-3 densitometry for colour NEGATIVES; the negative-side target here |
| **Status A** | ISO 5-3 densitometry for reversal material and PRINTS; used for RA-4 paper curves and the reversal closure (register #19) |
| **APD / RP 180** | printing density. Academy Printing Density (ST 2065-2) is the target of the ADX16 route. SMPTE RP 180-1999, ARCHIVED December 2006, publishes an explicit responsivity table and serves the comparison line. "Cineon printing density" is a third metric defined by discontinued stocks (5384 print, 5248 base) |
| **LAD** | Laboratory Aim Density, a fixed reference density for mid-grey |
| **CC** | colour-compensating filter value: CC 10 is 0.10 peak density, so 40M is a CC 40 magenta |
| **k** | normalised density, `k = OD / DMAX`. Higher k is a denser negative and a lighter print |
| **DMAX (corridor)** | density range of a cube's 0–1 input: 3.30 for negatives on every sensor; reversal 5.00 monochrome, 5.25 for each camera build. Cube and shapers must agree on it |

**Colour science**

| | |
|---|---|
| **SPD** | spectral power distribution |
| **CMF** | colour-matching function; CIE 1931 2° here |
| **D50 / D55 / D65** | CIE daylight illuminants near 5000, 5500 and 6500 K |
| **XYZ** | CIE tristimulus space |
| **ΔE2000 / ΔE00** | CIE colour difference; about 1.0 is one just-noticeable difference |
| **a\* / b\* / L\*** | CIELAB axes; chroma is zero for a neutral |
| **CAT02 / Bradford** | chromatic-adaptation transforms |

**Delivery and the Resolve chain**

| | |
|---|---|
| **LUT / `.cube`** | 3D lookup table, the principal deliverable; 65³ is 65 nodes per axis |
| **DCTL** | DaVinci Colour Transform Language |
| **Shaper (pre/post)** | the DCTL pair mapping linear scanner values into and out of a cube's corridor |
| **P3 / Display P3 / P3-D65** | the wide-gamut delivery space |
| **PQ (ST 2084)** | the HDR transfer function, absolute luminance |
| **DWG** | DaVinci Wide Gamut, the Vision3 scene route's destination |
| **Scene-linear** | relative scene exposure, 10^(logH − logH_mid) per layer, scaled by the datasheet's midscale neutral so that a flat 18% grey lands at 0.18; delivered as DWG (D65). The only destination here that is not a density |
| **ACES / LMT** | Academy Color Encoding System and its Look Modification Transform |
| **AP0** | the primaries of ACES2065-1 (ST 2065-1) |
| **CST** | Resolve's Colour Space Transform node |

**Capture and scanning**

| | |
|---|---|
| **Narrowband / trichrome** | three sequential exposures under R/G/B LEDs at 640/544/450 nm (here a CuteNew RGB Pro Light Source, no affiliation) |
| **CFA / SSF** | colour filter array / spectral sensitivity function. The engines integrate the SSF, held in `data/cameras/` |
| **PDAF** | phase-detect autofocus pixels, rejected |
| **ARW / ARQ / EXR** | Sony raw / Sony pixel-shift composite / OpenEXR half-float linear. The converter also reads Canon CR2 and CR3, Nikon NEF and NRW, Fujifilm RAF (Bayer GFX; X-Trans refused) and DNG |
| **Pixel shift** | one-photosite sensor displacement so every site records all three colours |
| **ROI** | region of interest, the measured patch of an anchor frame |
| **Roll anchor** | the per-roll D-min measurement that normalises a scan ahead of any cube |
| **Flat field** | correction for uneven illumination |

**Analysis and fitting**

| | |
|---|---|
| **Gauss-Newton** | the iterative solver that inverts density to dye amounts |
| **Decoupling condition** | condition number of the dye-mixing matrix read through the three LEDs, scaled to a unit diagonal; near 1.0 the channels separate the dyes well |
| **Basis sensitivity** | displacement of a fitted result when the assumed dye basis changes: 0.027–0.049 D here; it bounds every stock comparison |
| **Serialisation check** | the written cube against the in-memory lattice, node for node: six-decimal write rounding only (hard constraint 3) |
| **MTF** | modulation transfer function, traced into `data/films/<Stock>_mtf.json` for sixteen sheets |
| **RMSE / FWHM / SNR** | root-mean-square error / full width at half maximum / signal-to-noise ratio |

**Data sources**

| | |
|---|---|
| **IT8 / ColorChecker** | standard reflective colour targets |
| **Munsell / NIST skin** | measured reflectance sets for fitting and testing matrices |
| **UEF** | University of Eastern Finland, publisher of the Munsell spectral sets |
| **CGATS / ISO 5-3** | the bodies and document defining Status A/M |

## Repository layout

```
data/
  cameras/        44 camera SSFs from the ACES rawtoaces-data library, with
                  index.json and a provenance README; read only when
                  --sensor names a body
  equipment/      measured LED SPDs, a traced camera-filter transmission,
                  traced WRATTEN 2 enlarger-filter densities
  films/          per-stock dye density, characteristic-curve and
                  spectral-sensitivity JSONs
  papers/         RA-4 datasheet JSONs (Endura Premier, Portra Endura,
                  Fujicolor Pro Laser TYPE II, Crystal Archive Type CA)
  standards/      Status M, Status A, APD, RP 180, CIE/D50 data;
                  reflectance/ holds the measured reflectance sets
engine/
  common/
    spectral.py                 density, resampling, integration
    interimage.py               DIR matrix stage in dye-amount space, identity
                                by default; only the Vision3 scene engine
                                calls it
    lut.py                      trilinear and tetrahedral LUT sampling; every
                                engine validates its serialised cube with it
    gamut.py                    projection of unreachable nodes onto the
                                reachable gamut (reversal only)
  scan/
    raw_to_exr.py               camera raw scans -> anchored half-float linear
                                EXRs (PRIMARY; measures and bakes the roll
                                anchor). COLOUR sensors only
    mono_to_exr.py              the same for a sensor with NO colour filter
                                array; shares merge, flat field, anchor and
                                scheduler with raw_to_exr.py
    decode_selftest.py          guards on the scan tools; no arguments, no
                                sample files; non-zero exit on any failure
    aces_ssf_import.py          ACES camera SSFs -> data/cameras/
  c41/
    c41_statusm_engine.py       scanner density -> Status M cubes
    portra_decompose.py         aggregate dye curve -> three-dye decomposition
    portra_stocks.py            the twelve-stock registry
    neutral_locus.py            each stock's published neutral in Status M
    c41_stock_compare.py        inter-stock distance and basis sensitivity
    endura_print_engine.py      C-41 -> RA-4 Endura print emulation (Display P3)
    fuji_print_engine.py        C-41 -> RA-4 Fuji Pro Laser TYPE II, a preset
                                over the same PrintEmulationEngine
    locus_follow_dctl.py        writes Print Adjustment.dctl; checks it
                                compiles as C
    crosstalk_dctl.py           writes Density Crosstalk.dctl; checks it
                                compiles as C
  ecn2/
    adx_engine.py               the primary ADX16 route into ACES
    adx_validate.py             scores the ADX16 decode against the scene
                                engine's model
    annexc_check.py             the dye model against S-2008-002 Annex C
    printer_lights_dctl.py      writes Printer Lights ADX16.dctl; checks it
                                compiles as C
    v3_scene_engine.py          scanner density -> scene-linear DWG, per stock
    v3_basis_build.py           the family-average Vision3 dye basis
  reversal/
    reversal_transform.py       parameterised engine, all reversal builds
  (digitisation, QA tooling and the error-budget instruments are not
  distributed)
builds/           engine-generated cubes: monochrome/, print/ and one
                  untracked folder per camera build named by its --sensor
                  name; _ensemble/ and _forensics/ are untracked diagnostics
scripts/
  cube_audit.py   validates, samples and compares .cube files; checks tables
                  against the release's cube_manifest.json
DCTLs             release assets, hand-written except Print Adjustment.dctl
                  (engine/c41/locus_follow_dctl.py), Density Crosstalk.dctl
                  (engine/c41/crosstalk_dctl.py) and Printer Lights ADX16.dctl
                  (engine/ecn2/printer_lights_dctl.py)
  shapers         Preshaper 3.3 (negative); the 5.0 and 5.25 reversal pairs
  output nodes    10^-D linearisation, XYZ D50 to DWG, printer lights,
                  print adjustment, density crosstalk
film_datasheet/   manufacturer datasheets: publisher copyright, NOT
paper_datasheet/  redistributed, gitignored. DATASHEETS.md carries each
                  publication code
knowledge/        tier-rated literature notes; README.md indexes them
literature/       third-party articles, NOT redistributed, gitignored
docs/
  resolve.md      capturing and measuring a roll; the node chains
  method.md       how the transforms are derived; film-chemistry background
  figures/        rendered figures and the node plate's roll anchor
  samples/        the frames shown in README.md
README.md         front page
PROJECT.md        this document, the technical reference
BUILDING.md       the build runbook
DATASHEETS.md     every source datasheet, with its publication code
LICENSE           MIT: engine/, the DCTLs, the documentation
LICENSE-DATA      CC BY 4.0: released cubes and data/, with a scope exception
                  for data/cameras/
```

### Repository hygiene (standing rules)

- **Run `git gc` periodically.** Nothing packs the loose objects; 1505 have
  been observed.
- **Never run `filter-repo`.** A rewrite of commit hashes breaks the
  byte-identical-regeneration guard.
- **A stale linked worktree is a second checkout**, about 48 MB. Remove one
  only when `git -C <wt> status --porcelain` is empty; retain its `worktree-*`
  branch.
- **Diagnostic artefacts are untracked**: `builds/_forensics/`,
  `data/films/_ensemble/` and a gitignored `_ensemble/` under `builds/`.
  `portra_decompose.py --out-suffix` and the overlay tooling regenerate them.
  Three ensemble cubes in six versions, 44 MB, remain reachable in history.

Each family has one engine, parameterised by stock and illuminant, so a
correction propagates everywhere. Builds emit no per-build manifest of engine
commit and data hashes.

## Hard constraints (do not relax these)

1. **No unbracketed synthesis of spectral shape.** A dye, sensitivity or
   D-min curve is authoritative only within its measured support. No value
   outside that support may enter a fit objective or a shipped integral as if
   it had been measured. Every engine still makes some claim about the bands
   it cannot see (a truncated observer, a cut exposure integral, a basis held
   flat), so the rule governs how the claim is made. Admissible, in order of
   preference:
   - **Interpolation between measured samples** of one curve, across a dash
     gap or a crossing, with the bridged samples recorded in the audit block.
   - **A bracket**, the standard treatment of a band outside support. The
     engine carries both physically admissible extremes through (edge value
     held against zero, band blocked against transmitting, plateau against a
     continued descender) and the register records their spread. The extremes
     bracket the input; that is no proof that every admissible prior lands
     between them after a nonlinear inverse. Truncation with renormalisation
     is one point inside a bracket, never the bound.
   - **A single chosen prior**, only when its alternatives have been measured
     end to end and recorded (register #18 is the pattern). Never choose a
     prior for the fit residual it buys.
   - **Every synthesised sample is marked in the data file** (`basis_held`,
     the `digitization_audit` endpoints).

   Free extrapolation of shape into a band with no bracket is prohibited. The
   tone-curve extension of register #16 is the only extension by slope.
2. **Numerical grounding takes precedence over qualitative review.** Every
   accuracy claim, and every assertion that an effect is negligible, derives
   from running the computation over the measured data in this repository. A
   linear-in-cyan framing makes the cyan truncation of register #2 appear
   negligible; it reaches 0.24 D in deep shadow.
   - The precedence runs over judgement alone. A computation establishes what
     the model does and how sensitive it is, never that the model is right
     (invariant 10).
   - A reproducible observation on real film outranks every synthetic check
     that passes, and opens an investigation. A pleasing image justifies no
     change to spectral data until a reference measurement has scored it.
   - A computed figure bounds implementation consistency and sensitivity. An
     independent reference measurement bounds accuracy over its stated domain.
     Visual review establishes usability, and no numerical bound.
3. **Validate the artefact as shipped.** Every `.cube` is quantised to six
   decimal places on write. The density and print cubes are also clipped to
   [0,1]; the scene cubes alone are written unclamped. Re-parse the written
   file, and validate it through the interpolation the host applies.
4. **Metric and aesthetic operations remain separated.**
   - A per-channel subtraction that estimates a measured physical quantity
     belongs inside the metric, recorded with its measurement: the roll
     anchor's D-min, and the mask-filtered illuminant of register #17.
   - A per-channel log-space offset chosen for the look (printer lights, white
     balance, CC filtration) is aesthetic and belongs in a node *above* the
     metric transform. A neutral point set by eye inside the metric corrupts
     it; this is the central criticism of NamiColor's reversal-mode workflow.
   - A rendering convention inside the metric is recorded as one. There are
     two.
   - **The grey-axis lock** renders the input diagonal neutral by per-channel
     maps that vary with density. The Status M cube's constant offset places
     the sheet's neutral series on that diagonal at k = 0.22 only. Its
     mid-grey intent is assumed. It is no evidence that an enlarger behaves
     that way.
   - **The reversal base-white mapping.** The roll anchor places the measured
     D-min at density 0.0 and the reversal cubes integrate only the dyes above
     it, so the film base renders as D50 white: a base-free dye model. Exact
     film-relative colorimetry would also weight the target by the base
     spectrum. The register #17 surrogate (each sheet's Status A D-min triplet)
     gives 0.085–0.159 D visual density on the D50 table and, at the base's own
     L\*: a\* +0.65 / b\* −0.81 on Ektachrome E100; a\* −0.28 / b\* +0.14 on
     Velvia 100; within 0.01 of zero on Provia 100F and Velvia 50. Three
     channel readings do not fix the base colour: a smooth base matching the
     E100 surrogate's scanner readings exactly can sit 1.23 ΔE\*ab from it.
     Rendering the base's own colour needs a measured base spectrum and a
     declared output white.
5. **No scene-dependent decisions occur anywhere in the chain.** Every
   operation is a fixed physical constant (dye spectra, paper H&D curves,
   Status M responsivities) or a per-roll physical measurement (the anchor).
   Picture content never determines the transform. Diagnostics may read content
   to flag clipping, an unreachable node or an inversion failure; they alter no
   value.
   - Grading controls above the metric are the photographer's decisions. Their
     shapes are fixed constants: Print Adjustment's stock tables come from the
     sheet's neutral series, its Contrast layer basis from the stock's dye set.
   - The two normalisations are keyed to scene-independent references: the
     roll anchor to unexposed film base, and the grey-axis lock to the stock's
     published neutral series, solved once per stock and paper.
   - **A reference frame counts as a measurement.** A target photographed on
     the roll under a declared illuminant may calibrate a per-roll parameter,
     provided that the fitted parameters, their reference and the frames they
     govern are recorded; the parameters are held fixed across those frames;
     and the correction stays as low-dimensional as the reference supports.
     One grey patch supports a constant balance and exposure, never a matrix. A
     neutral scale across the printable window also supports a slope per layer
     (the diagonal of Density Crosstalk). A grey card under an undeclared
     illuminant supports nothing.
   - **No stage neutralises a frame's illuminant.** A tungsten-lit frame stays
     warm as this emulsion and this paper render it, and frame-to-frame
     relationships across a roll survive. Whether the rendered cast matches the
     physical illuminant is unverified on film (Known limitations). Any
     automatic neutralisation, exposure or content-driven correction belongs
     above the metric transform, per constraint 4.

## Source data (`data/`)

Each JSON documents its own digitisation method, registration audit and known
uncertainties.

**Measured monochrome assemblies, `data/sensors/`**

- `QHYCCD_QHY600M-PH_ssf.json`: the response of one IMX455 detector with the
  window of a QHY600M-PH camera, reduced by `engine/scan/qe_sensor_import.py`
  from Table 3 of Ofek et al. 2023 (CC BY 3.0): 5 nm bin means from 380 to
  780 nm, the bins from 695 to 715 nm absent, multiplied by wavelength as a
  response per unit radiant power. The sensor-specific monochrome build reads
  it (register #9).

**Equipment, `data/equipment/`**

- `film_scanner_SPD_combined.csv`: measured LED SPDs, 380–780 nm at 1 nm:
  narrowband R/G/B at multiple drive levels, plus unused broadband white
  W1–W100 columns. The unit is a CuteNew RGB Pro Light Source
  (https://cutenewdesign.com), named for reproducibility only; no affiliation
  or sponsorship. The engines read the values as radiant power per wavelength
  interval. The export unit of the instrument is unrecorded and its
  confirmation is pending. The unit changes no shipped table. It decides how
  a sensor curve must be converted before use (register #9).
- `Kenko_ZXII_L41_transmission.json`: transmission of the UV filter on the
  owner's film cameras, traced from the manufacturer's chart, 396–700 nm at
  1 nm. No engine reads it; it supports capture-side estimates only. No
  affiliation or sponsorship.
- `Wratten2_No25_density.json`, `_No99_`, `_No98_`, `_No2B_`: diffuse density
  of four KODAK WRATTEN 2 filters, traced from Kodak's vector sheets,
  300–897 nm at 1 nm (No. 25 301–897, No. 99 300–898). A `censored` flag marks
  each point above the chart's 3.0 D ceiling, where the stored 3.0 is a lower
  bound. Only the Endura tricolor kernel reads them.

**Camera spectral sensitivity, `data/cameras/`**

- Forty-four measured SSFs, 380–780 nm at 5 nm, imported verbatim from the ACES
  `rawtoaces-data` library by `engine/scan/aces_ssf_import.py`. Each file
  records the source URL, the upstream SHA-256, the measuring laboratory and
  the creator. `index.json` maps the EXIF model strings.
- The population is the consumer interchangeable-lens Bayer subset. Fixed-lens
  compacts, drone and cinema modules and X-Trans bodies (a 6×6 pattern has no
  2×2 reading) are excluded. `GROUP_A` in the importer is an explicit list.
- No engine reads these files by default: `--sensor` defaults to `none`. The
  directory is Apache-2.0 upstream, and `LICENSE-DATA` carries the exception.

**Per-stock film data, `data/films/`**

- `Vision3_dye_density.json`: the VISION3 shared image-dye set, the family
  average of the four traced stocks, with the family-average Minimum Density
  curve. The four stocks agree to a worst pairwise RMSE of 0.0332 D. The cyan
  band is load-bearing: a trace that flattens cyan to 0.02 across 400–450 nm is
  wrong by up to 0.197 D at 402 nm, across a band carrying 69% of Status M blue
  responsivity. No spektrafilm-sourced data is used anywhere in this project.
- `Vision3_<Stock>_dye_density.json`, `_datasheet_curves.json`,
  `_spectral_sensitivity.json` per Vision3 stock (500T's curves file is
  `V3500T_datasheet_curves.json`).
- `Velvia100`, `Velvia50`, `Provia100F`, `EktachromeE100` `_dye_density.json`
  and `_datasheet_curves.json`. The Ektachrome file covers E100 and
  100D/5294–7294: the dye data on the two sheets is identical (Kodak Alaris
  E-4000 rev. 8-18, Eastman Kodak H-1-5294 rev. 5-24).
- Twelve C-41 stocks, each with `_datasheet_curves.json`,
  `_spectral_sensitivity.json` (absent for Pro 400H) and `_dye_density.json`.
- `<Stock>_mtf.json` for the sixteen sheets with an MTF chart: the four Kodak
  professional C-41 stocks and Ektachrome E100 (three labelled records each),
  the four Vision3 stocks (three records, one order per sheet), the seven
  Fujifilm sheets (one unlabelled curve). Each carries the traced curve on a
  fixed log grid, a summary (MTF50, MTF30, MTF20, response at fixed
  frequencies, chart end) and a `digitization_audit` block. Where bitmap
  curves cross inside one line width, the sheet carries a `crossing_bracket`
  in place of a per-record MTF50 (Vision3 50D). Gold 200, Ultramax 400, Pro
  Image 100 and the 2023 Fujifilm 200 and 400 sheets print no MTF chart. No
  engine consumes these files.

**Target-metric standards, `data/standards/`**

- `StatusM_ISO5-3.json`: ISO 5-3 / CGATS.5 Status M, via ArgyllCMS `xspect.c`.
  Its Status A table matches `StatusA_ISO5-3.json` exactly. Unverified against
  the paid primary standard (register #19).
- `StatusA_ISO5-3.json`: ISO 5-3:1995 Table 3, from the public ANSI/NAPM
  IT2.18-1996 copy.
- `CIE1931_2deg_CMFs.json` (360–830 nm at 1 nm) and `D50_illuminant.json`
  (300–780 nm at 5 nm), from the CIE tabulations in colour-science 0.4.7.
  Reloading reproduces the D50 white point xy (0.3457, 0.3585) exactly, and
  XYZ (0.9642, 1.0, 0.8252) on the shared 5 nm grid.
- `APD_ST2065-2.json`: ST 2065-2:2012 Tables A.1 and B.1.
- `StatusM_to_APD_S-2008-002_AnnexC.json`: the Academy's Status M to APD
  transforms for 31 stocks (matrix, offset, published residuals).
  `annexc_check.py` reads the 5207 and 5219 entries.
- `RP180_responsivities.json`: SMPTE RP 180, peak-normalised, 360–730 nm at
  10 nm, including the sub-400 nm blue tail; verified against the standard.
- `reflectance/`: Munsell glossy 1600 and matt 1269 (UEF, via the
  colour-science Zenodo deposit); NIST human skin 100 (Cooksey, Allen and Tsai
  2017, per-subject averages). One JSON schema, reflectance on 0–1; provenance
  in the directory's README.md.

**Papers, `data/papers/`**

- `EnduraPremier_paper.json` (E-4070, March 2013), `PortraEndura_paper.json`
  (E-4021, September 2008), `FujiProLaserTypeII_paper.json` and
  `CrystalArchiveTypeCA_paper.json` each carry Status A characteristic curves
  against logE, the spectral sensitivity of the Y/M/C-forming layers, the
  spectral dye density of C/M/Y (layers assigned by spectral peak) and a
  `digitization_audit` block. Type CA publishes no characteristic curves and
  is reference data only.
- An independent tracing reproduces the paper dye charts: spektrafilm's
  Endura Premier and Portra Endura traces (commit `3bb2c2d`) agree with this
  project's at 0.002–0.004 RMS after peak normalisation, with the same peak
  wavelengths, and the Status A crosstalk matrices agree within 0.006. Both
  read the same printed chart. No spektrafilm data enters this project.

## How a transform works

Every transform is a **spectral round trip** between two integrals of one dye
state:

- **Scan density.** The scanner SPD, times the camera's spectral sensitivity
  where one is named, integrated against the stock's measured dye curves.
- **Target density.** The same dye state integrated against the target
  responsivity (CIE D50 XYZ, APD or Status M).

The engine solves the mapping numerically at each node (Newton or Gauss-Newton)
and ships it as a 65³ LUT. No analytic DCTL is exported. The inputs are the
traced dye curves, the measured illuminant SPD, the camera spectral sensitivity
and the target responsivity.

- **Negative paths: the traced D-min filters the illuminant.** The roll anchor
  divides the base and orange mask out of the linear frame, a subtraction of
  integrated densities. The cube therefore receives the image dyes as the LEDs
  see them THROUGH the mask, and the engine integrates
  `LED × sensor × 10^−Dmin(λ)`, renormalised (register #17).
- **Unreachable nodes.** The dye set reaches only part of the density box. The
  reversal engine substitutes for the remainder (its section); the negative
  engines do not (Invariants).
- **The Vision3 scene route** shares the first half, then inverts each layer's
  characteristic curve to log exposure and maps relative exposure to XYZ (D65)
  through a fitted 3×3, landing in scene-linear DaVinci Wide Gamut.
- **The sensor term is omitted by default.** A constant response cancels
  exactly in a density measurement; a response that varies across an LED's
  band does not. The engines integrate the illuminant alone unless `--sensor`
  names a body. The project has measured no monochrome sensor. One published
  measurement of a single camera assembly exists and sets no bound for
  monochrome cameras in general, so the omission has no established bound
  (register #9).

### Corridor and shaper convention

- **Preshaper:** `d = clamp(-log10(linear), 0, DMAX)/DMAX`. **Postshaper**
  (reversal only): `× DMAX`. Shapers carry no spectral content.
- **The negative path (Status M, ADX16 and Vision3 scene alike) uses DMAX 3.30
  on every sensor; the reversal corridor depends on the sensor.** All builds
  are 65³.
- `Preshaper 3.3.dctl` feeds every negative cube; no postshaper follows any of
  them.
- Reversal: `Preshaper 5.0.dctl` and `Postshaper 5.0.dctl` for the monochrome
  cubes, the 5.25 pair for the camera builds on the release.
- Crossing corridors rescales density silently (register #5).
- A change to the corridor, the lattice or the print pivot moves the shapers,
  the paired cubes, the DCTLs, the identity checks and the instructions
  together. Never adopt one silently.

**The reversal corridor is set by the stock's densest state, measured.**
`reversal_transform.py` evaluates scan density over a neutral dye-4.0 stack and
an off-neutral sweep, prints the requirement on every build, and warns when the
corridor would clip it:

| stock | monochrome | through the a7R III | the seven camera builds on the release |
|---|---|---|---|
| Velvia 100 | 3.88 | 3.95 | 3.93–3.95 |
| Ektachrome E100 | 4.25 | 4.28 | 4.28–4.29 |
| Provia 100F | 4.60 | **5.08** | **5.06–5.08** |
| Velvia 50 | **4.75** | 4.91 | 4.88–4.92 |

Hence 5.00 monochrome and 5.25 for every camera build on the release. The seven
bodies sit within 0.04 D of one another on every stock. 5.25 is measured per
body, since a colour filter band-limits the illuminant's tails by its own
amount; another body's corridor is determined the same way (BUILDING.md).

**Corridor and LUT size are coupled.** Node spacing is `dmax/(size-1)` and
interpolation error scales as its square: 4.5 to 6.0 at 33³ raises error by
1.78 against 1.78 predicted (trilinear probe). The a7R III reversal builds
under that probe:

| corridor | RMSE | maximum | lattice reached |
|---|---|---|---|
| 6.0 | 0.0004 D | 0.0012 D | 58–62% |
| 5.25 | 0.0003 D | 0.0009–0.0010 D | 68–73% |

The tetrahedral lookup that the Resolve setup requires brings the second row to
**0.0002 D and 0.0005 D**. A 4.5 corridor is overrun by two stocks even
monochrome; at 33³ it gave 0.0009–0.0010 D, maximum 0.003 D.

**Two numbers are called a serialisation check.** The node-for-node comparison
measures the six-decimal write rounding, pinned at 2.9e-07, and nothing else.
The accuracy figure interpolates the artefact read back from disk at
off-lattice points (hard constraint 3). Every engine prints both. On the print
branch the gap is four orders: Portra 400 to Endura Premier serialises at
2.6e-07 and interpolates at RMSE 2.0e-03, worst case 1.0e-01, 26 code values
of 255, the largest lattice error in the chain.

**The negative corridor carries deliberate headroom.** `DMAX = 3.30` is uniform
across the twelve stocks. Their published neutral series reach 1.63 D of scan
density (Pro 400H) to 2.26 D (Portra 400), so the corridor holds 46% to 101%
more than any datasheet documents. A tighter corridor was measured and
rejected: Portra 400 rebuilt at 3.30, 3.00, 2.80, 2.60 and 2.40, probed over
the same physical range.

- Status M cube: maximum error falls from 0.0028 D to 0.0012 D, a factor of 2.3
  against 1.9 predicted.
- Print cubes: no trend, RMSE 2.3 to 3.1e-03, maximum 7.3 to 8.0e-02 over a
  fixed 0 to 2.16 D input. The Display P3 gamut clip dominates; a quarter to a
  third of that lattice sits outside P3 before clipping.
- The change would improve only the intermediate artefact, already one to two
  orders below the 0.027 to 0.049 D basis sensitivity.
- Negatives are overexposed one to two stops by intent. 2.40 leaves 0.9 stop of
  headroom beyond the published curve on Ektar 100 and Fujicolor 100 (1.1 on
  Portra 400); 2.60 leaves under two stops; only 3.00 and above keeps every
  stock past three stops.
- `DMAX` must agree in four places: both C-41 engines and both 3.3 shaper
  DCTLs.

Over the working dye range (to 2.15 D on Portra 400) the tetrahedral RMSE is
0.0003 D, maximum 0.0045. Over the whole declared corridor the serialised cube
gives 0.0124 D and 0.7227, over the 98% of samples above the output floor.

**A corridor is never inferred from the film's physical Dmax.** The LEDs sit on
the dye peaks: Velvia 50 scan red reaches 4.08 D at a 3.5 D Status A neutral
and 4.42 D at 3.6 D. A 4.0 corridor clips Velvia 100's scan red by 0.17 D at a
3.5 D neutral.

### Resolve node chains

docs/resolve.md carries the chains node by node with the operator's
instructions. This section records the parameters behind them.

**Reversal:** anchored EXR → `Preshaper 5.0.dctl` (5.25 for a camera-named
build) → the cube, on its own node, tetrahedral → `Postshaper 5.0.dctl` (or
5.25) → `Density to Linear.dctl` (10^-D; trims at defaults) →
`XYZ D50 to DWG.dctl`, an explicit 3×3 → aesthetic offsets → display transform.

- A Resolve CST cannot substitute for the explicit matrix node: the cube emits
  WHITE-RELATIVE XYZ.
- After anchoring, the linearisation node cannot emit values above linear 1.0,
  so no absolute luminance is encoded. For HDR delivery emulating the ISO 3664
  transparency illuminator (1270 cd/m², roughly 800 nits through a typical
  0.2 D base), the node's OutputGain is the control, set per stock and roll.

**ECN-2, ADX16 (the route):** anchored EXR → `Preshaper 3.3.dctl` →
`builds/monochrome/ecn2/Vision3 to ADX16.cube` → `Printer Lights ADX16.dctl` →
ADX decode (input colour space ADX (16-bit), `CSC.Academy.ADX16_to_ACES`) →
the ACES timeline.

- The cube emits normalised code values, so no postshaper follows. The trim
  DCTL converts density sliders to code-value offsets with the ST 2065-3
  factors k = (1.00, 0.92, 0.95). Do not use `Density to Linear.dctl` here.
- Locus Stock applies the stock's grey trims, which place a datasheet-exposed
  grey at AP0 0.18 on each channel. The sliders are offsets from them, dialled
  once per stock and rig on a known neutral.
- **The Academy decode is the source of the route's bound.** It reads the
  negative against a reference-film assumption that Vision3 does not meet.
  Against the scene-linear route:
  - ColorChecker ΔE2000 6.3–7.3 mean after the printer-light trims, solved as
    the DCTL applies them;
  - effective contrast 0.92–0.99 of the scene's;
  - a grey-axis channel spread of 6–18% in AP0 at mid-grey, rising to 14–36%
    at 1.5 log exposure units above it (about 5 stops). The trims remove it at
    one density only. The larger spreads belong to 250D and 500T. The spread is
    the decode's: a table built on a stock's own dyes and mask leaves it at
    5–18% (register #17).
- **Master is the exposure control.** With Locus Stock Off, Master adds equal
  APD to all channels. Vision3's APD green is steeper than its red and blue:
  two stops over, a return of green to mid-grey needs 0.039–0.045 D more red
  and 0.030–0.033 D more blue than green (the generator's tables; Annex C's
  matrix on the sheet curves gives the same sign and 79–90% of the size on 250D
  and 500T). An equal print-down of an overexposed frame turns green-cyan, an
  equal print-up magenta. With the stock selected, Master moves each pixel
  along that stock's neutral series: green by Master, red and blue by the
  series' departure from green, held constant outside its support.
  `engine/ecn2/printer_lights_dctl.py` generates the file (BUILDING.md).
- **Master on the scene engine's forward model** (ColorChecker brackets;
  shared characteristic curves, no interimage):

  | case | mean ΔE2000 | maximum |
  |---|---|---|
  | three stops over, printed down with Master | 0.27–0.57 | 0.66–1.02 |
  | three stops over, equal printer lights | 7.59–7.82 | 12.02–13.04 |
  | two stops under, printed up with Master | 0.60–1.71 | 3.61–6.49 |

  One table per stock serves every scanner build: against tables built through
  each of the seven camera builds the correction differs by at most 0.00217 D
  (the generator fails above 0.0025 D) and 0.47 ΔE2000 on the ColorChecker and
  the broad reflectance sets. Master runs to ±0.6 D, enough for three stops
  either way (0.489–0.524 D on the four stocks).
- A print-through look is optional: Resolve's "LMT Kodak 2383 Print Film
  Emulation" after the decode.

**ECN-2, scene-linear (secondary, for graded work):** anchored EXR →
`Preshaper 3.3.dctl` → the stock's own `Vision3 <Stock> to Scene DWG.cube`
under `builds/monochrome/ecn2/` → CST (DaVinci Wide Gamut / Linear → timeline)
→ the grade.

- No postshaper, printer lights or `Density to Linear.dctl`: the output is
  linear, negatives permitted. There is no separate HDR table.
- The stock's balance illuminant (D55 for 50D/250D, 3200 K for 200T/500T) is
  built in and Bradford-adapted to D65. The datasheet's midscale neutral lands
  at 0.18. Exposure and balance trims belong after the cube, in linear.

**C-41:** anchored EXR (the anchor is also the orange-mask removal, per
channel) → `Preshaper 3.3.dctl` → `builds/monochrome/c41/<Stock>_StatusM.cube`
→ `Print Adjustment.dctl` (optional; defaults no-op; must precede the print
cube) → `builds/print/DisplayP3/<Stock>_EnduraPremier_DisplayP3.cube` (Kodak
stocks on the lower-contrast paper: `<Stock>_PortraEndura_…`; Fujifilm stocks:
`<Stock>_ProLaser_…`) → the grade.

- The two cubes must be the SAME stock: each encodes its own D-min, and a mix
  mis-tones the image with no warning.
- The print cube's output is **Display P3 (D65), sRGB-encoded and clipped to
  [0,1]**, written into every cube header. On Portra 400 / Endura Premier an
  input of k = 0.22 returns 0.4613/0.4613/0.4613, which is 18% grey through the
  sRGB transfer function (0.4614). Place no colour space transform after it.
- **The diagonal input is the stock's own published neutral.** A C-41 neutral
  does not read equal in Status M: Portra 400's sits 0.10/0.06 D below and
  0.16 D above equal channels in R/G/B at mid-grey. The Status M cube subtracts
  each stock's neutral offset, solved from the characteristic-curve series
  through the spectral base (`engine/c41/neutral_locus.py`), and writes it into
  its header. The print engines add it back before they invert. The print
  cube's diagonal meets the sheet neutral at k = 0.22.
- **The encoding is not reversible at its floor.** A channel whose image-dye
  density is below a positive offset goes negative in balanced density and the
  cube clips it. Every print build measures the loss on a uniform dye 0–2.2
  probe, exact render before the clip against after:

  | stock | samples below the floor | mean ΔE2000 on that share | worst |
  |---|---|---|---|
  | Portra 400 (Endura Premier) | 4.7% | 0.09 | 0.81 |
  | Ektar 100 (Endura Premier) | 4.0% | 0.08 | 0.73 |
  | Portra 400 (Portra Endura) | 4.7% | 0.30 | 1.35 |
  | Ektar 100 (Portra Endura) | 4.0% | 0.26 | 1.19 |
  | Fujifilm 400 | 0.9% | 0.03 | 0.11 |
  | Pro 400H | none | | |

  The loss sits at the toe of one record on a strongly off-neutral negative.
  Portra Endura shows about three times Endura Premier's loss. A fleet-wide
  shift of the encoding would remove it by moving the mid-grey pivot on every
  cube; it is not taken on these figures.
- **For quality control, stop after the Status M cube.** Multiply by 3.30 and
  add the header's neutral offset: the Status M density of the image dyes
  alone. A densitometer and the E-4050 curves include base and fog; the engine
  prints the full reading beside it. The sheet's integrated D-min, added in its
  place, is off by 0.009 D in green on Portra 400.
- Printing density is avoided for C-41: it encodes a cine print stock's view of
  the negative.

### `PrintEmulationEngine`: the shared print-emulation core

`PrintEmulationEngine`, parameterised by `PrintConfig`, supports reflective
and transmissive media through `neutral_basis`, `medium_base_spd` and
`adapt_view_white_to_d65`. `EnduraPrintEngine` and `FujiProLaserPrintEngine`
are thin presets. Two properties are load-bearing:

1. The medium's spectral base appears in the rendered spectrum: the engine
   subtracts `Dbase` to recover dye amounts, then forms `10^-(base + a·DYE)`.
   Inert for Endura, whose paper JSON carries no `base` block.
2. Chromatic adaptation of the viewing white to D65 precedes the D65-referred
   XYZ to P3 matrix. Every shipped paper is viewed under D50, so the CAT02
   adaptation is always active.

## Per-roll anchoring

Density is defined against a reference. Anchoring pins it to the actual roll,
because D-min varies with processing and film condition.

- **Measurement** is performed by the converters (`raw_to_exr.py`,
  `mono_to_exr.py`). Every roll has a D-min frame, frame 0001 by default: clear
  leader (reversal) or unexposed rebate (negative). A plain-light set (the
  flats, merged as `plain.exr`) and a D-max frame set are optional. The anchor
  is measured against the sensor white level. No dark-frame subtraction is
  performed. `--film-family` selects which area of film supplies which anchor.
- **RULE: a plain-light datum frame must be captured at the SAME LED drive
  level as the roll's scan**, or the drive-level shift must be measured and
  recorded in the anchor JSON.
- **LED drive level is a free variable.** The cubes are built against the
  100%-drive SPDs. Worst case over dye 0–3.5: Velvia 100 at 20% drive, 0.013,
  0.032 and 0.003 D in R, G and B on saturated colours; median ≤0.006 D;
  dye-3 neutrals below 0.01 D. The centroid shifts about 1 nm between 20% and
  100% drive. The anchor absorbs the neutral-axis component. 50% drive or
  above keeps the worst case under about 0.02 D. Prefer shutter time, which is
  spectrally free.
- **Application is baked into every EXR.** Each channel is multiplied by
  10^dmin_exr_scale before the half-float write, so the film base reads 1.0,
  density 0.0. Each EXR header records the gains under `roll_anchor`; the
  anchor JSON holds the measurement, the ROI boxes and a `baked_into_exrs`
  block. On real a7R III ARW captures the baked D-min frame re-measures at 0
  within 2 × 10^-5 D, and every baked pixel equals the unanchored merge times
  the gain within the two-rounding bound of 9.8 × 10^-4.
- **Two density scales.** The *plain-light scale* (`dmin`, only with a
  plain-light set) is true transmission density, comparable with datasheets.
  The *EXR scale* (`dmin_exr_scale`) is density relative to the sensor white
  level, and is the value applied. The offset between them is about +0.24,
  +0.58 and +0.93 D in R, G and B on this apparatus. A D-max patch is reported
  against the D-min frame as `dmax_above_base`.
- **The converter applies the EXR-scale values.** The plain-scale values would
  crush green and blue past the preshaper's density-zero clamp, with a strong
  yellow-green cast. EXR-scale values are valid only if the anchor frames were
  exposed at the roll's own per-channel exposure and ISO.

## Engines and script reference

`engine/` is organised by family: `scan/` (converters and the anchor tool),
`c41/` (the still-negative toolchain and both print engines), `ecn2/` (the
ADX16 and scene engines), `reversal/` (the cube builder). Run everything from
the repository root. BUILDING.md records the command behind every cube.

### C-41 toolchain (`engine/c41/`)

A datasheet-only calibration. No C-41 stock publishes per-layer dye spectra, so
a constrained fit against the Vision3 dye basis INFERS them, pinned metrically
by the published Status M characteristic curves (register #8). Every script
takes `--stock`; the registry `engine/c41/portra_stocks.py` holds each stock's
source sheet, provenance code, output filenames and chart geometry. Metrics
quoted here are Portra 400's; per-stock tables are under "Current state by
stock".

> **Shared KODAK VISION emulsion lineage does not justify the basis.** Gold
> 200, a non-VISION control, fits the Vision3 basis *better* than Ektar 100,
> Portra 400 and Portra 160: single-start RMSE 0.0105 against 0.0122, 0.0131
> and 0.0138. The basis is a generic flexible three-dye model that fits any
> C-41 aggregate. It remains the best available basis and the fits stand.

1. `data/films/<Stock>_datasheet_curves.json`: traced characteristic curves and
   spectral dye-density chart (midscale neutral and D-min), with a
   `digitization_audit` block.
2. `data/films/<Stock>_spectral_sensitivity.json`: the traced sensitivity chart
   (Portra 400 layer peaks 406, 550 and 651 nm). Both files are measured,
   bounded by register #13.
3. `portra_decompose.py`: a nine-parameter warped-basis fit of midscale minus
   D-min onto the Vision3 dyes: per-dye amount, peak shift within ±25 nm, width
   scale within 0.85–1.15 for cyan and 0.5–2.0 for magenta and yellow. A seeded
   64-point multistart (register #12) writes
   `data/films/<Stock>_dye_density.json` with a `fit_audit` block. The ±25 nm
   bound is uniform across the twelve stocks (`shift_bound_nm`, register #8).
   Portra 400: aggregate reconstruction RMSE 0.0108 D; Status M reproduction
   deltas 0.004, −0.001 and −0.002 D in R, G and B; LED crosstalk condition
   number 1.4175 behind the mask.
4. `c41_statusm_engine.py`: the scanner-to-Status M cube, D-min excluded,
   written to `builds/monochrome/c41/<Stock>_StatusM.cube`.
   - Status M red is truncated at the 700 nm dye-chart edge and renormalised:
     0.49% of the red area on the 1 nm grid (the 10 nm source table sums to
     0.28%).
   - The scan-side responsivity is the LED (times the sensor, when named)
     filtered by the traced D-min (register #17). The mask shifts the LED
     centroids on Portra 400 by 0.1, 6.2 and 3.6 nm in R, G and B.
   - The neutral-axis check reads the traced midscale and the base with the
     BARE LEDs, anchors one against the other as the DCTL does, and unmixes
     through the mask-filtered model. The closure is the fit's own Status M
     reproduction error (Portra 400: −0.005, +0.001 and −0.005 D).

**Interimage and DIR structure.** `engine/common/interimage.py` applies a 3×3
`DIR_MATRIX`, identity by default, in dye-amount space with grey-ramp
pre-compensation; the identity case takes a fast path, verified bit-identical.
It is instantiated in `v3_scene_engine.py` only: no file under `engine/c41/`
contains a DIR stage, and `DIR_MATRIX` gates no shipped cube. Its parameters
are unmeasured. The architecture is taken from spektrafilm; **no data is**.
spektrafilm's inhibition numbers are one author-tuned default shared across all
C-41 negatives (some commented "just eyeballed", interlayer terms around
0.15–0.35 of the same-layer terms). The sole non-measured element in the C-41
chain is the inferred per-layer dye split (register #8).

### C-41 → RA-4 print-paper emulation

**The ONLY C-41 delivery route.** Its input is normalised Status M density with
D-min excluded, so it chains after `<Stock>_StatusM.cube`. Pairing is by
manufacturer, enforced by the `print_paper` key in `portra_stocks.py` (a
shipped default against an accidental cross-pair; the paper is a rendering
choice):

- Kodak negatives to Kodak ENDURA Premier (`*_EnduraPremier_*`) or Kodak PORTRA
  ENDURA, the lower-contrast paper (`*_PortraEndura_*`);
- Fujifilm negatives to Fujicolor Pro Laser TYPE II (`*_ProLaser_*`).

`endura_print_engine.py`, per node:

1. Status M density to negative dye amounts, by Gauss-Newton inversion;
2. dye amounts to negative spectral transmittance, orange mask included
   (`N(λ) = dmin_spec(λ) + Σ dye·DYE(λ)`);
3. through the paper's exposure kernel: a 3200 K tungsten lamp through WRATTEN
   No. 25, 99 and 47B for the two Kodak papers; laser lines at 473, 532 and
   685 nm for Pro Laser TYPE II;
4. per layer, to the dye amount that exposure forms;
5. to print reflectance, viewed under D50 with CAT02 adaptation to the D65
   display white, and to P3.

Every paper sheet names a viewing light of about 5000 K (5000 K ± 1000 and ANSI
PH2.30-1989 on the Kodak sheets; ISO 3664-2000 at 5000 ± 300 K on Pro Laser).
All three papers emit a Display P3 SDR cube. No modelling constant differs
between stocks.

**The paper's characteristic curves become per-layer amount tables.** The three
curves are Status A INTEGRAL densities of one neutral series; the unit paper
dyes' Status A matrix has off-diagonal terms of 0.01–0.13 on the three
reflective papers. The engine converts the curves once into per-layer
amount-against-exposure tables (`data/standards/StatusA_ISO5-3.json`) and
renders every colour by looking each layer up on its own exposure. Reading each
channel's curve at its layer's exposure agrees on the neutral and costs up to
15 ΔE2000 on saturated colours (Invariants).

**Grey balance is a full per-channel GREY-AXIS LOCK.** It pulls all channels
onto the mean neutral tone curve at every density, auto-solved so that the
input diagonal prints neutral. The Status M cube places the published neutral
series on that diagonal at k = 0.22 (`neutral_locus.py`); the engine adds the
offset back and refuses a Status M cube whose header carries a different one.

- The lock is calibrated on a constant offset. The series' curvature about it
  is reported, never fitted: within 4.0 units of a\* and 4.2 of b\* on Portra
  400 over k = 0.22 ± 0.12 on Endura Premier, 1.3 and 4.0 on Portra Endura.
- The paper-table solve closes to machine precision on Portra Endura and
  1.2e-5 D on Endura Premier.
- The sheet's midscale spectrum names a different neutral (Known limitations).

**Sheet series under a constant per-layer balance, beside the lock.** A
constant balance approximates fixed filtration; the offset sets equal Status A
density at K_MID. C\*ab over the samples both renders support within L\* 10–92:

| material | constant balance, maximum | mean | lock, maximum | mean |
|---|---|---|---|---|
| Endura Premier, seven stocks | 1.8–4.5 | 1.1–3.3 | 3.6–6.2 | 1.8–4.0 |
| Portra Endura, seven stocks | 1.7–3.7 | 1.1–2.4 | 3.5–5.4 | 1.8–3.7 |
| Fuji Pro Laser, five stocks | 7.1–13.4 | 5.1–9.0 | 1.5–3.9 | 0.8–2.8 |

On the Kodak papers the lock gives the higher mean chroma on 13 of the 14
pairings (Gold 200 on Endura Premier is the exception); on Fuji Pro Laser the
lower on every pairing. A conditional model diagnostic: both renders share the
surrogate dye set, paper tables and calibrated kernel, and no measured print
supports either.

**Exchanging stock, paper and kernel.** Cells include pairings no build ships;
each re-solves its weights and offset, so the contrasts do not add. Mean C\*ab
of the sheet series under the constant balance, tricolor kernel, over the
samples all nine paper and kernel cells of a stock support (39–50 samples, mean
k 0.13–0.31):

| stock | Endura Premier | Portra Endura | Fuji Pro Laser |
|---|---|---|---|
| Portra 400 | 1.4 | 1.6 | 3.5 |
| Gold 200 | 3.3 | 2.2 | 4.6 |
| Fujicolor 100 | 2.4 | 1.8 | 5.6 |
| Fujifilm 400 | 3.8 | 3.8 | 7.1 |
| Pro 400H | 4.2 | 3.3 | 6.6 |

- **Paper.** Pro Laser is higher on every stock, by 1.3–3.8. Its sheet's own
  series carries blue Status A 0.05, 0.11 and 0.17 D under green at green
  densities of 1.0, 1.5 and 2.0.
- **Kernel.** The laser lines are higher than tricolor in every cell, by
  0.1–2.9. The red-sensitive layer's modelled log-exposure slope against mean
  image-dye Status M density is 0.94–1.21 under tricolor, 1.20–1.52 under the
  lines.
- **Stock.** On Endura Premier under tricolor the three layers' slopes span
  1.04–1.07 on Portra 400 and 1.03–1.07 on Gold 200, against 0.97–1.12 on
  Fujicolor 100, 1.00–1.22 on Fujifilm 400 and 0.91–1.21 on Pro 400H.
- The lock's mean on the same samples is 0.6–3.0, the lower of the two in every
  cell of the three Fujifilm stocks and every Pro Laser cell.

The contrasts measure sensitivity to the neutral-rendering convention. They
assign no fault to a paper, kernel or stock.

**Validation battery, groups A to F** (not distributed; one Kodak material and
stock at a time, default Endura Premier and Portra 400): digitisation
integrity, grid and print-viewing support, grey-axis lock and black-end state,
solver health, colorimetry, shipped-artefact fidelity. Only some checks carry a
pass criterion. Two results are recorded known exceptions, and the battery
fails if either grows:

- **Neutral-scale data–model compatibility.** The solve closes to 4.4e-16 D on
  every target that non-negative dye amounts can reach. On Endura Premier 8 toe
  samples at −2.56 to −2.52 cannot be reached, residual 1.2e-5 D; none on
  Portra Endura.
- **Neutral ramp against the declared du′v′ 0.01.** Where the requested neutral
  is unreachable, the equal-density master supplies the target and keeps a
  cast. Portra Endura exceeds the limit on Gold 200, Portra 160, Portra 800,
  Pro Image 100 and Ultramax 400, over k 0 to 0.012–0.018, at du′v′
  0.0104–0.0119. Fuji Pro Laser exceeds it on all five stocks, over k 0 to
  0.068–0.082, at 0.0241–0.0242. Endura Premier (0.005) passes.

The unit tests check the neutral-ramp record on all 19 pairings. Read both
summary lines of the validator, and treat a traceback as a FAIL.

**Group G: two E-4070 quantities that no inverse reads**, the tricolor exposure
times and the white-light starting filter pack. The sheet does not give the
negative's patch spectrum, the print aim, the sensitivity chart's density
criterion, or reciprocity from the charts' 0.5 s exposures to 2.4–4.9 s, so
group G reports scenarios and carries no pass criterion: Portra 160, 400 and
800; two negative-support treatments; lamps at 2850 to 3400 K; two density
criteria; both ends of the filter censoring (a censored point has transmission
between 0 and 10^−3); the locus neutral or the midscale spectrum; two mappings
of the sensitivity chart onto the layer tables.

- In every scenario the model's green time is 0.78–1.86 stop longer than the
  sheet's, and green-minus-blue 0.33–1.39 stop larger. The censoring end moves
  a time by at most 0.04 stop.
- The ideal white-light filtration needs no cyan, like the sheet's pack. Its
  M−Y difference spans the sheet's −10. The closest scenario is within 2.8 CC
  of both 40M and 50Y on the locus neutral, 3.5 CC on the midscale spectrum.
- The green residual is assigned to no input, and no input is adjusted to
  close it.

**Exposure kernel: tricolor.** E-4070 names white light (one exposure from a
3200 K lamp through a filter pack) and tricolor (three exposures through
WRATTEN No. 25, 99 and 47B); E-4021 names the same three filters, so the two
Kodak papers share one kernel.

- `PrintConfig.tricolor` builds the kernel: the lamp times the weighted sum of
  the three filter transmissions. The weights are balanced so that the lock
  needs equal per-layer offsets at K_MID: B 0.392, G 0.445, R 0.162 on Portra
  400 / Endura Premier. They are model parameters solved per stock; through the
  filters' overlap they also change off-neutral colour. No measured printer
  calibration establishes them.
- Kodak's typical times (B 4.9 s, G 3.3 s, R 2.4 s) belong to a real enlarger
  and are not used. The 47B is a proxy: No. 98 less No. 2B, with No. 98 alone
  selectable through `tricolor_blue`.
- `EnduraPrintEngine(tricolor=False)` keeps the white-light blackbody as an A/B
  reference. On Portra 400 / Endura Premier the shipped render differs from it
  by ΔE2000 mean 1.26, p95 3.35, max 8.79; colours are 4.4% more chromatic in
  the median; neutrals move by at most 0.37 ΔE2000 (0.42 with No. 98 alone).
- On the floor-loss probe on Endura Premier, the mean ΔE2000 on the clipped
  share is 3.6 to 6.8 times lower under tricolor on Ektar 100, Gold 200, Portra
  160, Portra 400 and Pro Image 100. Portra 800 and Ultra Max 400 lose almost
  nothing under either kernel.

#### The printable neutral window

**The single most important property of the print path.** At the true paper
gamma, about 2.6 from the datasheet H&D curves, the printable neutral window is
NARROW. Outside it the print clips to paper white or maximum black, as a real
RA-4 print does. The window is the span over which the mean print density sits
0.02 D clear of both paper white and the weakest layer's maximum black:

| stock / paper | window (Dnorm k) | OD | sensitivity over the window |
|---|---|---|---|
| Portra 400 / Endura Premier | [0.088, 0.344] | 0.84 | 0.35 stop per 0.01 k |
| Portra 400 / Portra Endura | [0.008, 0.410] | 1.33 | 0.24 stop per 0.01 k |
| Fujifilm 400 / Fuji Pro Laser | [0.054, 0.346] | 0.96 | 0.31 stop per 0.01 k |

- The sensitivity is the system gamma over the window (3.181 on Endura Premier
  and 2.155 on Portra Endura with Portra 400; 2.816 on Fuji Pro Laser with
  Fujifilm 400) times the 0.033 D that 0.01 k represents.
- Endura Premier: [0.088, 0.344] on Portra 160, Portra 400 and Pro Image 100;
  [0.086, 0.344] on Ektar 100, Gold 200, Portra 800 and Ultra Max 400, at the
  0.002 k sampling step. Portra Endura opens at k 0.004–0.024 and closes at
  0.410–0.412. Fuji Pro Laser varies by at most 0.010 k across its stocks.
- Fujifilm 400 / Pro Laser offers roughly 0.1 OD more room than Endura Premier,
  at the shadow end; Portra Endura about 0.5 OD more, at both ends.
- Lattice outside P3 before clipping: 31.8–34.6% on Endura Premier, 26.3–26.7%
  on Portra Endura, 15.7–17.7% on Fuji Pro Laser.
- On the shipped lattices no layer's exposure runs off its table or clips at
  zero. On the negative side 22–26% of nodes (34% on Fujifilm 200 and 400) ask
  for a negative image-dye amount, as the box domain must (Invariants).

**CAVEATS. The branch gives a print look; it is not a physical emulation of a
print.** Darkroom variables and the operator change a physical print greatly,
so no single measured print is a reference. The appearance of a *viewed* print
(veiling flare, surface glare, surround) is a non-goal. Nominal inputs:

- the Endura lamp at 3200 K and its 47B proxy;
- the Pro Laser red line at 685 nm, standing for an unpublished wavelength;
- the surrogate dye model of register #8 on the negative side;
- D50 viewing for the sheets' 5000 K light, adapted by CAT02. A D65 view
  differs from the shipped render by ΔE00 median 0.83, p95 2.19, maximum 2.73
  on Portra 400 / Endura Premier, median 0.36 on the neutral axis. D50 without
  the adaptation differs by 7.4 median and 15.3 maximum.

No Kodak sheet gives the material's spectral base, so its D-min non-neutrality
is discarded: Status A R/G/B 0.104/0.104/0.078 on Endura Premier (blue 0.026 D
below red) and 0.094/0.098/0.104 on Portra Endura (blue 0.010 D above red).
`Dbase` is stripped as a scalar and `base_spec_C` is zeros, so each render is
relative to its own base white.

#### Darkroom controls

All four default to no-ops. The placements are load-bearing.

| control | where | what it does |
|---|---|---|
| `PrintConfig.flare` | paper, during exposure (pre-lock) | contrast: system gamma 3.05 → 2.71 at 0.010 |
| `PrintConfig.printer_lights` | paper, after the lock (before it they would be re-neutralised) | colour balance: mid-grey b\* ±10.3 for ±0.05 logE on yellow |
| `Print Adjustment.dctl` | negative, before the cube | per shot: gamma about a pivot, exposure offset, per-channel printer lights, optional stock-locus exposure compensation |
| `Density Crosstalk.dctl` | negative, before Print Adjustment | per roll, optional: a 3×3 density matrix about mid-grey, optionally in the stock's dye-layer basis; the diagonal sets a slope per layer; the off-diagonal sliders are an experimental correction for a suspected processing error that couples the layers |

**The trim check** measures system gamma per negative OD on Portra 400: a
least-squares line of log10 display-clipped Y against input k, slope magnitude
divided by 3.30, over the samples within k = 0.082–0.348 of a 241-point ramp
over 0.02–0.60. The printable-window gamma above is a different quantity (a
Status A print-density slope).

- Flare 0.005, 0.010 and 0.020 lower system gamma from 3.05 to 2.88, 2.71 and
  2.44, with mid-grey held at a\* −0.01 / b\* +0.01.
- ±0.05 logE on one layer moves mid-grey by up to 10.3 in b\* and 9.3 in a\*,
  with system gamma at 2.96–3.10.

**Contrast grades do not exist for RA-4.** A per-channel logE offset cannot
alter dD/dlogE. Four effects soften a real print: veiling flare, the paper
surface, exposure placement and local work. Only exposure placement is in the
chain: an overall shift of −0.30 logE takes system gamma from 3.05 to 1.61 (the
curve's local slope is 0.9 in the toe, 4.6 mid-curve, 1–2.5 in the shoulder).
The shipped cubes render the flare-free ideal at system gamma 3.05, above any
physically viewed print. A Gamma below 1.0 at the DCTL is ordinary use.

**Print Adjustment** requires no rebuild. Its domain is normalised Status M
density, `k = OD/3.30`; a change of 0.01 in k is visible. `Literal Pow` selects
the mode:

```
darkroom (default) :  k' = pivot + (k - pivot) * gamma + gain
literal            :  k' = (1 + gain) * k ^ gamma
```

- `gain`: a pure density offset, slider range ±0.2.
- `gamma`: contrast about `pivot`; the default 0.22 is the k that renders
  Y = 0.18.
- `Gain R/G/B`: additive density offsets after the master in both modes.
- Literal mode's fixed point is k = 1.0, while the image lies below k ≈ 0.41,
  so it reads mostly as brightness.

Measured through the engine's calibrated neutral ramp (mid-grey rendered at
exactly k = 0.22, gamma on the fixed probe above):

| case | gamma | Y(mid) | a\* | b\* |
|---|---|---|---|---|
| baseline | 3.050 | 0.1800 | −0.01 | 0.01 |
| gain +0.010 | 2.950 | 0.2344 | −0.01 | 0.02 |
| gain −0.010 | 3.115 | 0.1345 | −0.01 | 0.01 |
| gamma 1.20 | 3.304 | 0.1800 | −0.01 | 0.01 |
| gamma 0.85 | 2.772 | 0.1800 | −0.01 | 0.01 |
| gamma 0.85, pivot 0.10 | 2.896 | 0.1039 | 0.00 | 0.01 |
| literal gamma 0.90 | 2.703 | **0.4159** | −0.05 | 0.05 |
| trim R +.005 B −.005 | 3.037 | 0.1861 | 1.88 | 5.11 |

The C shim confirms: defaults are a bit-exact no-op in both modes; pivoted gain
offsets all three sample points by exactly +0.010000; literal gain is exactly
`1.1 × k`; the per-channel trim is identical across modes; the output clamps
into [0, 1].

**Locus Stock** (Darkroom mode; Off by default). The Status M cube places the
sheet's neutral series on the diagonal at k = 0.22 only, so an equal `gain`
carries the casts of denser tones down to mid-grey. With the stock selected,
`gain` and `gamma` move each pixel along that stock's series s (g is green),
holding the series' departure from the diagonal constant outside its support:

```
g' = pivot + (g - pivot) * gamma + gain
k' = s(g') + (k - s(g)) * gamma
```

It is approximate, model-based exposure compensation with fixed sheet tables:
it does not model enlarger exposure, it is validated on the sheet's neutral
series only, and it keeps the series' baseline casts.

- **Generator.** `engine/c41/locus_follow_dctl.py` takes each stock's series
  from `neutral_locus.py` and keeps the green branch, each kept sample more
  than 1e-5 k above the last (Portra 800 drops 16 toe samples, Ultramax 400
  drops 8; the two such samples in Portra 800's toe would form a slope of 125).
  Each branch is simplified to 20–63 knots.
- **The run fails unless the emitted file** matches its double-precision
  reference to 1e-5 k; stays within 0.1 ΔE2000 of the full series through every
  Display P3 cube the stock prints on; reproduces the plain transform bit for
  bit with the stock Off and in Literal mode; keeps the defaults bit-exact; is
  continuous at every knot; and inverts (1/gamma, −gain/gamma) to within
  3e-7 k. Worst added ΔE2000 is 0.029–0.069 on Portra Endura against
  0.034–0.088 on Premier, and 0.060 against 0.077 after a layer slope.
- **Exposure brackets of the sheet series**, mean/max ΔE2000 against the
  correctly exposed render: two stops over printed down gives 0.26/0.35 on
  Fujifilm 200 (7.86/12.05 with the stock Off) and 0.05/0.12 on Portra 400
  (5.49/9.43). At three stops over the mean stays within 1.15 and the maximum
  within 3.08 (Gold 200) on every stock. Two stops under reaches 7.47 at most
  on Fujicolor 100 (12.21 with the stock Off): in the toe a density offset is
  not an exposure change.

**Per-layer slopes** (`Density Crosstalk.dctl`, three diagonal sliders, 1.0 by
default, range 0.8–1.2) serve a negative whose layers developed to different
contrasts. The node precedes Print Adjustment, so a Locus Stock print-down
reads the corrected green:

```
k' = P + M (k - P),   P = (0.22, 0.22, 0.22), independent of pivot
Layer Basis Off      :  M = diag(cR, cG, cB)
Layer Basis selected :  M = Sn diag(cR, cG, cB) Sn^-1
```

- Column l of `Sn` is the Status M density of a unit amount of the stock's dye
  l, scaled to 1 in its own channel, checked against the print engine's matrix.
  Its 2-norm condition number is 1.27–1.51 over the twelve stocks. Status M is
  not linear in dye, so a fixed `Sn` separates the layers approximately.
- Set Layer Basis to the stock in Locus Stock; the menus are independent.
  `Gain R/G/B` stays after the master, so a correction pairing a slope with a
  trim holds for the master grade it was set under.
- The Density Crosstalk run fails unless a diagonal matrix matches an
  independent layer-slope implementation to 1e-6 k (worst 3.6e-7 k).
- The Print Adjustment run feeds its file inputs already moved by a slope: the
  tables stay within 0.1 ΔE2000 of the full series under random and box-corner
  slopes; the file matches its reference to 1e-5 k on every stock (worst
  3.9e-7 k, Portra 800); at master identity it passes the input bit for bit.

**DCTL authoring constraints.** Resolve rejects some valid files with
`wrong argument int p_Width in Transform DCTL` or `main DCTL function has wrong
arguments`; the fault lies earlier in the file. Use only constructs proven
here:

- one function only, everything inside `transform()` (no `__DEVICE__` helpers);
- no `__CONSTANT__` at file scope (use `const float` locals);
- `DCTLUI_SLIDER_FLOAT`, `DCTLUI_CHECK_BOX`, `DCTLUI_VALUE_BOX`,
  `DCTLUI_COMBO_BOX`; combo display names free of hyphens;
- slider labels of letters, digits and spaces only (parentheses give "unknown
  type of DCTLUIParams definition" and no sliders at all);
- a `for` loop and a long `if/else` chain load; `if/else` in preference to
  ternaries; ASCII only, no tabs.

An unpublished C shim compiles a Transform DCTL as plain C; Resolve-specific
macro faults escape it.

#### Second RA-4 paper: Fujicolor Pro Laser TYPE II

`fuji_print_engine.py` is a preset that differs from `EnduraPrintEngine` in
`print_medium_path` and, through the paper's laser provenance, its exposure
kernel. Crystal Archive Type CA publishes no characteristic curves (its
"Calibration data" section is Frontier minilab setup), so
`CrystalArchiveTypeCA_paper.json` is reference data only.

Neutral ramp through each engine's calibrated path, D50 view, Portra 400 on the
Kodak materials and Fujifilm 400 on Pro Laser:

| | Endura Premier | Portra Endura | Fuji Pro Laser II |
|---|---|---|---|
| neutral offset subtracted by the Status M cube, R/G/B (D) | −0.105 / −0.049 / +0.154 | −0.105 / −0.049 / +0.154 | +0.068 / −0.045 / −0.023 |
| sheet series' curvature about that offset, k = 0.22 ± 0.12, max \|a\*\| / \|b\*\| | 1.2 / 4.2 | 1.3 / 4.0 | 2.8 / 1.0 |
| printable window (Dnorm k) | **[0.088, 0.344]** | **[0.008, 0.410]** | **[0.054, 0.346]** |
| system gamma over the window | 3.181 | 2.155 | 2.816 |
| neutral input k landing Y = 0.18 | 0.221 | 0.221 | 0.221 |
| grey-axis lock, mean correction per layer C/M/Y (logE) | +0.21 / +0.24 / +0.25, per-layer balance carried by the band weights | +0.24 / +0.25 / +0.35, per-layer balance carried by the band weights | +1.35 / +1.38 / +1.44, relative-axis origin folded in, per-layer balance carried by the line powers |
| grey-axis lock, range of correction over the window C/M/Y (logE) | 0.11 / 0.10 / 0.58 | 0.15 / 0.04 / 0.84 | 0.48 / 0.17 / 0.48 |
| outside P3 pre-clip | 31.8% | 26.3% | 17.6% |
| neutral-scale Status A solve, max residual | 1.2 × 10⁻⁵ D | 4 × 10⁻¹⁶ D | 1.1 × 10⁻⁴ D |
| grey-lock solve residual | not tabulated | not tabulated | RMS 0.029, max 0.116 D |
| serialised 65³ interpolation RMSE / max (P3), tetrahedral | 2.0e-3 / 1.0e-1 | 1.8e-3 / 7.5e-2 | 1.7e-3 / 6.2e-2 |
| serialised node quantisation (P3) | 2.6e-7 | 2.7e-7 | 2.6e-7 |

The Endura Premier solve residual is a non-negativity clip on eight far-toe
samples (logE −2.56 to −2.52), where the traced red and green records sit one
stored density step (1e-4 D) above their base.

CAVEATS, recorded in the engine's docstring and the cube headers:

1. **Laser paper exposed at laser lines.** Pro Laser TYPE II is a Frontier
   minilab paper with H&D curves measured under laser exposure. The engine
   reads "laser" in the paper's provenance and exposes at 473, 532 and 685 nm.
   - The line powers are calibrated model parameters, balanced so that a
     neutral negative at K_MID needs no per-layer trim. On the error budget's
     250 reachable off-neutral Fujifilm 400 patches, lock re-solved: equal
     powers move the print by 1.31 mean / 9.29 max ΔE2000; a 10% change of the
     blue power by 0.02 / 0.18.
   - Fujifilm documents the Frontier 350's 473 nm blue and 532 nm green lasers.
     The red diode's wavelength is unpublished; 685 nm is the diode Fujifilm's
     patent pairs with them, a rendering choice within the 650–688 nm span of
     its test diodes (`knowledge/frontier-laser-exposure.md`).
   - The Frontier scans the negative and drives its lasers from image data, so
     the kernel models an RGB laser enlarger, a machine no source documents.
     Against cubes built with a 3200 K tungsten enlarger on the same paper and
     lock (printable band, ±0.12 Dnorm per channel), the shipped cubes differ
     by 1.55–2.99 mean, 3.1–5.2 p95 and 4.7–8.1 max ΔE00, up to 4.2 along the
     diagonal, most on Fujifilm 200 and 400. A 650 nm red moves them by
     0.84–1.58 mean and 2.1–3.6 max. No measured print checks either kernel.
   - The exposure time behind the datasheet's curves is unpublished (a patent's
     scanning test exposed each pixel for 1.7×10⁻⁷ s), as is the paper's
     reciprocity at enlarger times.
2. **Relative exposure axes.** The sheet prints no absolute logH origin (H&D
   abscissa a 0.5-decade lattice, sensitivity ordinate a 1.0-decade lattice).
   A global shift passes through `inv_hd` into the lock's offset `o` and
   cancels. The solved offsets, `o = 1.384` on all three layers of Fujifilm
   400, have the arbitrary origin folded in and are not comparable with
   Endura's.
3. The datasheet labels its densities **"Status A equivalent"** (ステータスA相当).
4. **Deep Matte is excluded**: its characteristic curves do not apply to that
   surface.
5. **This is not the intended paper.** The target was the darkroom cut-sheet
   Pro-G / Pro-L, for which no standalone optical datasheet was found.
6. No physical print is a reference for the path (see the Endura CAVEATS), and
   the validation battery covers the Kodak materials only.

### C-41 fleet discrimination gap: the most important caveat in this document

**The pipeline cannot reliably distinguish its twelve C-41 stocks from one
another.** The limitation is structural and bounds every C-41 claim. The user
reports Ektar 100 as a very different stock from the Portras, scanned and
printed; the model reads Ektar as one of the *closest* stocks to Portra 400.

`engine/c41/c41_stock_compare.py` measures all 66 pairs:

- inter-stock spectral shape distances span **0.021–0.219 D**;
- the basis sensitivity of the surrogate decomposition is **0.027–0.049 D**.

16 of the 66 pairs sit inside the band; the last is Portra 400 / Pro 400H, at
0.0491 D against a band edge of 0.0494 D. The closest pairs:

| pair | shape distance (D) |
|---|---|
| Fujifilm 200 / Fujifilm 400 | 0.0000, identical by construction, one shared dye chart |
| Portra 800 / Ultra Max 400 | 0.0207 |
| Portra 400 / Pro Image 100 | 0.0211 |
| Gold 200 / Portra 400 | 0.0243 |
| Portra 160 / Pro Image 100 | 0.0265 |
| Portra 160 / Portra 400 | 0.0277 |
| Ektar 100 / Portra 160 | 0.0307 |
| Gold 200 / Ultra Max 400 | 0.0311 |

The other 50 pairs sit clear; the widest is Superia Premium 400 against most
Kodak stocks, at 0.15–0.22 D.

**The cause.** Every stock's dye set is a warped Vision3 basis (register #8):
the twelve fitted sets stay within a mean |ΔD| of 0.005–0.098 peak-normalised,
most pairs in 0.009–0.066. `DIR_MATRIX = np.eye(3)`, and grain is not modelled.
Real dye chemistry and interimage coupling, the two mechanisms that make stocks
look different, are the two absent from this model.

**The orange mask is present, measured, and larger than either.** D-min at
440 nm less D-min at 650 nm spans **0.6005 D on Fujicolor 100 to 0.9467 D on
Fujifilm 200 and 400, a spread of 0.346 D**. Its shape ratio (B−R)/(G−R) runs
from 1.450 on Portra 160 to 2.117 on Portra 800. The spread exceeds the dye
distances, the basis sensitivity and Kodak's C-41 process-control tolerance of
±0.03–0.09 D (Z-131), and is basis-independent.

| stock | mask (D) | stock | mask (D) |
|---|---|---|---|
| Fujicolor 100 | 0.600 | Gold 200 | 0.737 |
| Superia Premium 400 | 0.609 | Ultra Max 400 | 0.749 |
| Portra 400 | 0.623 | Portra 800 | 0.775 |
| Portra 160 | 0.643 | Pro 400H | 0.825 |
| Ektar 100 | 0.648 | Fujifilm 200/400 | 0.947 |
| Pro Image 100 | 0.690 | | |

Pyrazolotriazole magenta couplers need less yellow masking coupler than
pyrazolone couplers; no datasheet names a coupler class. The per-stock table is
in `knowledge/dye-sets-across-the-three-processes.md` §4f.

**Propagation into the print cubes, measured.** Pairs of engines differing ONLY
in `dmin_spec`, lock re-solved against each mask, over a 25³ grid (15 625
nodes; the null control reproduces the engine at 0.000e+00; per-swap table in
§4f-bis of the same note):

- the lock absorbs the mask on the neutral axis, to a maximum of 0.131 ΔE2000
  across every pair;
- off the neutral axis, for realistic pairs, 13–20% of nodes differ by more
  than 1 ΔE2000, reaching 3.6–5.5 at saturated colours;
- the driver is SHAPE: a swap of 0.173 D strength with almost no shape change
  gives 1.2% of nodes above 1 ΔE and a maximum of 1.55; a swap of 0.009 D
  strength with the extreme pair's shape change gives 18.8% and 4.02.

**What this does and does not invalidate.** The print cubes are metrically
sound as prints. They are not stock-DISCRIMINATING by their dye sets; their
per-stock MASK term discriminates off the neutral axis only. A claim that two
print cubes render a saturated colour differently is supportable; a claim that
rests on neutral rendering is not. Datasheet-level comparisons (the `char` and
D-min-shape columns of `c41_stock_compare.py`) never pass through the basis.

`DIR_MATRIX` is NOT the remedy: interimage occurs during development, and every
cube begins after it. `<Stock>_StatusM.cube` is densitometry on dyes that
already exist; `endura_print_engine.py` never inverts the negative's
characteristic curve nor calls `apply_dir`. The remedy is MEASURED per-layer
dye data from colour-separation wedges on a validation roll.

Supporting literature (`knowledge/interimage-effects-and-stock-differentiation.md`):
Kodak names proprietary DIR couplers as an Ektar design element; published
interimage magnitudes run to a 10–35% gamma change; an UNVERIFIED tier-C source
holds that Kodak saturation differences are designed in by interimage.

### `reversal_transform.py`: reversal cubes (D50 XYZ only)

The canonical engine for all reversal builds. D50 XYZ is the only target, and
legacy build names fail loudly.

- **Integration grid.** `dye_support_grid()` derives it per stock from measured
  dye support: 400–710 nm for Velvia 100 and Velvia 50, 400–719 nm for Provia,
  401–700 nm for Ektachrome. No wavelength is modelled as clear film
  (register #2).
- **Output.** White-relative colorimetric density, −log10(XYZ/white).
  `XYZ D50 to DWG.dctl` after the linearisation node un-normalises by the D50
  white, applies Bradford from D50 to D65 and converts XYZ to DWG in one 3×3.
- **Validation.** The engine validates the re-parsed serialised cube.
- **Corridor.** `DMAX` is resolved from the sensor: 5.00 monochrome, 5.25 for a
  named camera, `--corridor` overriding both. Every build prints the corridor
  the stock requires at dye 4.0. The maximum sits on a corner of the probed
  box: a 33-point axis reproduces every requirement to four decimals.

**The tracing bound is propagated as shape error.** Each reversal dye file
documents its tracing uncertainty (0.005–0.011 D, `uncertainty` field). A
trace-budget instrument pushes three families through the inversion and the
D50 integration: a per-layer flat density offset at the reading bound, a
per-layer lateral wavelength shift, and a joint wavelength-axis stretch. It
takes the worst of all eight per-layer sign patterns per family and of the 128
combinations jointly.

- The flat offset contributes only 0.003–0.008 D.
- The shift term carries the budget. The E100 cross-validation against the
  independent 100D raster finds best-fit lateral shifts of 0.5/1.0/1.5 nm per
  dye; Provia's axis fit leaves residuals up to 1.2 nm. The worst, 1.5 nm,
  stands as surrogate for the two Velvias.
- All three families jointly: 0.029–0.045 D max and 0.008–0.014 D mean over
  the dye 0–2.5 box and the neutral series (Ektachrome E100 best at 0.029 D,
  Velvia 100 worst at 0.045 D). This is the branch's largest measured
  model-side term, two orders above cube serialisation.
- A moved curve holds its measured end value across the uncovered part of the
  original support, so the term measures shape alone. Under the zero-boundary
  policy printed beside it (`SHIFT/zero-boundary`), Velvia 50's shift term is
  0.119 D (0.097 D over the box) against 0.030 D with the edge held;
  Ektachrome's is 0.041 D against 0.021 D; Velvia 100 and Provia are unchanged.
- The figures are extrema over the shapes tested. A per-dye amplitude scale
  carries no term: the chain is invariant to per-dye scaling.

**The characteristic-curve closure** is the one check against a sheet quantity
the inverse never consumes. The four sheets' Status A curves are traced
(replot-on-ink 100% on Ektachrome E100, Velvia 100 and Provia 100F; 96–98% on
Velvia 50, whose dash-coded records share one bitmap; the JSONs carry the union
where records overlap). The build subtracts the sheet's D-min per channel in
integrated density, solves the three curves together into per-layer amount
tables, and prints the solve residual, the amount floor, monotonicity and the
D50 a\*/b\* of the series. The series render blue-green on the D50 table by up
to 7.5 units of b\* (register #19). The same pass bounds the roll anchor's base
term under a surrogate tint (register #17).

**The lattice extends beyond the reachable gamut, and the excess is projected
onto its boundary.** For a large minority of nodes no dye triple has the node's
scan density. The reachable share depends on the sensor:

| build | reachable |
|---|---|
| monochrome, corridor 5.00 | 41.3% Provia 100F, 47.8% Velvia 100, 48.3% Velvia 50, 50.3% Ektachrome E100 |
| a7R III, corridor 5.25 | 67.8% to 73.5% |

- `project_to_reachable()` gives each unreachable node the dye solution of the
  nearest reached node (exact separable distance transform, in dye space,
  before the target integration). Unreachable means a residual above
  `REACH_TOLERANCE_D`, 10^-3 D. The distribution is bimodal: 41.34% of Provia's
  nodes close within 10^-3 D and the rest miss by about 2.5 D on average (mean
  residual 1.4492 D over all nodes). Reached nodes are bit-identical.
- Reached means numerical convergence only. Of the reached nodes, 10.0% on
  Velvia 100, 17.4% on Velvia 50, 21.0% on Provia 100F and 14.4% on Ektachrome
  E100 close only with a negative dye amount (Known limitations).
- The purpose is continuity. Without the projection the largest step between
  adjacent nodes with one unreachable is 0.8461 on Provia 100F and 0.7419 on
  Ektachrome E100, against 0.0498 and 0.0806 between reached nodes; with it,
  0.0623 and 0.0743.
- The projection is a deliberate, bounded exception to hard constraint 1: an
  unreachable node has no true value. It is confined to the reversal path
  (Invariants).
- No plausible input reaches the region. Of 40,000 dye triples per build,
  0.00% land in a trilinear cell containing an unreachable node on either
  reversal build, every C-41 stock and the Vision3 build, and still 0.00% under
  a per-channel anchoring offset of up to 0.2 D. At 0.4 D: 0.26% on Provia
  100F, 0.18% on Ektachrome E100, 0.01% on Fujicolor 100.

**A monochrome build loses accuracy in deep shadow.** Cells that a real
transparency reaches contain projected corners where dye exceeds about 2.5.
Against the full chain, tetrahedral:

| range | shipped monochrome cubes, maximum |
|---|---|
| up to dye 2.0 | 0.0012 D |
| up to 2.5 | 0.0059 D |
| by 3.4 | 0.2993 D |

Lowering the corridor from 6.00 to 5.00 recovers roughly a factor of two at
moderate density; in a sweep of 4.5, 5.0, 5.5 and 6.0, finer spacing and
ceiling clipping nearly cancel above dye 3. A camera-named build holds RMSE
0.0002 D and maximum 0.0005 D across the whole range on the a7R III; the GFX
100 builds hold 0.0006 D, except Velvia 50 at 0.0021 D.

#### What would recover it: per-exposure filtering

The colour filter is CHANNEL-SELECTIVE: its blue channel suppresses 540–660 nm
for the blue exposure while its red channel keeps 640 nm. No filter in the
shared light path can do that. The blue LED carries a plateau from roughly 540
to 660 nm at 0.13% of peak; a dense yellow dye is transparent there, so at high
yellow the plateau dominates the blue reading.

Five remedies were measured and rejected:

1. *Plateau as stray light.* It tracks the in-band signal at a ratio of
   0.0080–0.0081 across drive levels from 5% to 100%, with an additive
   intercept of 0.2%. It is real.
2. *More solver iterations.* 14 to 60 iterations leave Provia 100F at 41.34%
   reachable, failures at a median residual of 2.65 D.
3. *A robust solver.* Bounded least squares, five starts, yellow ceiling 12 on
   the worst Velvia 50 cell (dye 0.04/3.55/3.91): blue scan density plateaus at
   2.603 D when yellow passes 4. Two of the cell's eight corners close; six
   stop at the ceiling with residuals of 0.004–0.050 D. The nodes are
   saturation.
4. *A 3×3 decoupling matrix in the shaper.* The gap is curvature: 1.10 D
   deviation from the best linear model monochrome, 0.44 D on the a7R III.
5. *A bandpass filter in the shared path.* A triple bandpass at ±10 nm moves
   reachability from 40.0% to 56.6% and leaves the nonlinearity at 1.01 D.

Filtering each exposure separately works, since the LEDs fire sequentially.
Ideal top-hats built through the engine (nonlinearity and reachability on
Provia 100F; serialised figures over dye 0–4.0, trilinear):

| sensor response | nonlinearity | reachable | serialised RMSE / max |
|---|---|---|---|
| none, the monochrome build | 1.096 | 40.0% | 0.0203 / 0.6479 D |
| shared bandpass ±10 nm | 1.011 | 56.6% | not built |
| a7R III colour filter | 0.443 | 69.3% | 0.0003 / 0.0009 D |
| **per-exposure ±40 nm** | **0.243** | **77.0%** | **0.0003 / 0.0008 D** |
| per-exposure ±25 nm | 0.083 | 82.6% | not built |

The least costly realisation filters the LEDs and re-measures
`film_scanner_SPD_combined.csv` with the filters fitted; no code changes. A
physical filter has shoulders and recovers less; filtering lengthens exposure;
the corridor rises (Provia 100F required 5.08 D at ±40 nm).

### `raw_to_exr.py`: trichrome scans to anchored half-float linear EXRs (PRIMARY)

A single self-contained file; docs/resolve.md carries the operator's steps.

```
python3 engine/scan/raw_to_exr.py                        # interactive
python3 engine/scan/raw_to_exr.py --mode pixelshift --no-flats --in-dir /path/to/roll \
    --roll V100-A --film-family reversal
```

- **Modes.** Interactive by default. Non-interactive through `--roll`,
  `--out-dir`, `--mode`, `--flats R G B` or `--no-flats`, `--film-family`,
  `--dmin-frame`, `--dmax-frame`, `--in-dir` and `--workers` (default 4).
- **Output.** `<scan folder>/<roll>/` or `--out-dir`, with the anchor record
  `<roll>.json` beside the frames: 16-bit half-float OpenEXR, ZIP-compressed,
  about 0.0002 D precision. Metadata goes to the `capture_metadata` header
  attribute; no EXIF, colour space attribute or ICC profile. An earlier run is
  replaced only after confirmation, as one set, through a hidden staging
  folder.
- **Flats** merge through the same pipeline as `plain.exr` (`role: plain`), the
  anchor's plain-light set.
- **Parallelism.** A process pool across triplets, four workers at about
  2.5 GB each on full-resolution pixel-shift frames; output verified pixel- and
  metadata-identical to the serial reference.
- **Routing is by what LibRaw reports, whatever the extension**: a 2D raw
  image is a single-shot mosaic (superpixel mode); a stack of planes is a
  pixel-shift composite. Accepted: `.dng`, `.arw`, `.arq`, `.cr2`, `.cr3`,
  `.nef`, `.nrw`, `.raf`, plus RGB TIFF on the pixel-shift path.
- **Superpixel decoder.** Verified against real Canon CR3 and CR2, Nikon NEF
  (Z f, D850), Pentax DNG and Fujifilm GFX 100 RAF (16-bit
  lossless-compressed; correlates 1.000000 per channel with LibRaw's half-size
  render). Each green site is black-corrected with its own level.
- **ARQ decode.** Against a real a7R III file, channels correlate 1.0000,
  0.9998 and 1.0000 with LibRaw's decode, against 0.9603 to 0.9819
  off-diagonal, at a per-channel scale of 1.000: plane order R, G1, B, G2.
- **Refused.** X-Trans (verified against a real X-T2 RAF) and Canon sRAW/mRAW
  (three colours across four planes, subsampled chroma). Canon writes no
  pixel-shift raw (the EOS R5 emits a 400 MP JPEG; the R5 Mark II withdrew the
  mode). Nikon merges to `.NEFX`, which LibRaw does not read; a linear DNG from
  Adobe DNG Converter is accepted as a three-plane stack, untested.

`mono_to_exr.py` is the companion for a sensor with no colour filter array and
imports the roll folder, anchor and scheduler from this file.
`decode_selftest.py` guards both converters and the anchor with 79 checks,
LibRaw's report stubbed.

#### The roll anchor

Two merges. The D-min frame, the D-max frame and `plain.exr` merge first,
unanchored, into a hidden scratch folder, and the anchor is measured on them
(their metadata supplies per-channel exposure and ISO). The whole roll then
merges again, each channel multiplied by 10^dmin_exr_scale before the
half-float write. A contact sheet identifies frames and is never measured.

**Rules.**

- Normalise shutter in linear space before any logarithm.
- Read exposure from the merged frame's metadata. Skipping this corrupts a
  D-max reading by about 2.4 D; a D-max patch needs about 250 times the
  plain-light exposure.
- Aperture must match across a frame set, or the measurement refuses to run.
- ISO is recorded and never validated against a list. Any base ISO is
  accepted, since a common gain cancels. A drift within a set biases the result
  by the log of the gain ratio (about 0.8 D between ISO 100 and 640) and raises
  a warning naming the frames. Verified on synthetic frames: identical light at
  ISO 64 and 6400 yields identical densities.
- D-max is diagnostic only, never a rescaling reference.
- Refused: a D-min channel whose patch mean is not a finite positive fraction
  of white (a zero mean floors to D-min 30, a gain of 10^30); a frame with any
  pixel above 65504. A measurement that carries warnings is baked only after
  confirmation.
- Without the plain-light set the anchor JSON omits the plain-light-scale
  densities and the field-nonuniformity note. No converter record carries the
  LED crosstalk matrix.

**ROI.** Default: the central 50% of each axis (25% of area, about 10.5 Mpx on
the a7R III, 2.6 Mpx per CFA plane), chosen per frame set with the picker
(matplotlib `RectangleSelector`; drag, Central 50%, Reuse previous). The JSON
records the effective pixel box per channel. Statistics are trimmed to the 1st
to 99th percentile. A bimodality check (dip test plus two-cluster separation)
warns of a second population: on synthetic tests a 20% contamination corrupts
D-min from 0.121 to 0.184 D and triggers it. Previews are log- or gamma-scaled
for display only (a rebate patch is about 4 D down). Shutter speed is asked
only where a channel's exposure is unreadable.

**Status.** The bake is verified on real a7R III ARW captures (Per-roll
anchoring). The numeric core is verified on synthetic frames (D-min ±0.0003 D,
D-max ±0.0001 D at 4.31 D). The merged-frame path gives anchors identical to
the TIFF path. The picker is verified headlessly. The absolute D-min of a real
roll has no independent check (register #6).

### `adx_engine.py`

The ECN-2 branch's primary route, and the only route by which the ADX16 cube is
regenerated. It writes and validates
`builds/monochrome/ecn2/Vision3 to ADX16.cube` at DMAX 3.30, shared with
`Preshaper 3.3.dctl`. Its scan side is the LED, times the sensor when named,
filtered by the family-average Minimum Density curve (register #17); the mask
shifts the LED centroids by 0.5, 4.1 and 5.4 nm in R, G and B. Its output is
`APD(mask + dye) − APD(mask)`, the quantity ST 2065-3 encodes.

Inputs: `data/equipment/film_scanner_SPD_combined.csv`;
`data/films/Vision3_dye_density.json`; `data/standards/APD_ST2065-2.json`;
`RP180_responsivities.json` for the comparison line; the four per-stock dye
JSONs for the neutral-axis and family-mask checks.

| self-report | figure |
|---|---|
| working-range corridor probe | dye 0–2.2 reaches scan density 2.18 of the 3.30 corridor, 66% occupancy |
| serialised cube, APD, working range | tetrahedral RMSE 0.0003 / max 0.0074 D (trilinear 0.0006 / 0.0128 D) |
| ADX16 code range | no clipping over the lattice; ADX10 would clip 16.1% of working-range probes, so ADX16 is the only supported target |
| neutral-axis check per stock (traced midscale and own mask, BARE LEDs, anchored as the DCTL does, unmixed through the family model, against the direct `APD(midscale) − APD(mask)`) | within 0.012 D on every stock |
| family-mask bound per stock (own mask on the film, family mask in the cube, working box) | 0.001–0.012 D mean, up to 0.089 D in APD |
| APD against RP 180, same dye stacks | 0.03 D in the mean, at most 0.24 D per channel |

**`adx_validate.py`** scores the full chain through the Academy decode against
the scene route. Both delivered cubes are sampled tetrahedrally, after a header
check and a corner check.

- The exact scene engine without its cube is printed as a diagnostic: the scene
  cube sits 0.2–0.3 ΔE2000 mean and at most 1.3 from it over the reflectance
  sets, 0.46–0.79 maximum on the ColorChecker. The route's accuracy bound per
  stock is the cube's figure, on this synthetic population.
- The printer-light column adds per-channel APD trims to the code values before
  the decode, as `Printer Lights ADX16.dctl` does, solved so the decoded 18%
  grey lands at AP0 0.18 per channel. A per-channel gain on the decoded AP0 is
  a different operation, printed as a comparison only: it departs from the trim
  chain by up to 3.7 ΔE2000 on 250D (3.1 on the ColorChecker).

**`annexc_check.py`** is the one ECN-2 comparison against a quantity measured
outside this repository (`knowledge/academy-printing-density-and-the-adx-unbuild.md`
§4). The Academy's S-2008-002 Annex C fitted a Status M to APD matrix per stock
on 97 spectrally measured patches (64 of them colours), 5207 and 5219 among
them. The script solves each stock's per-layer amounts from all three
characteristic curves at once, integrates them against the Status M and
ST 2065-2 tables, and compares the spectral APD with the Academy's matrix along
the traced neutral series.

- **Gate:** worst per-channel mean absolute disagreement ≤ 0.02 D, a project
  criterion borrowed from the document's expected error over a different
  population. A consistency check; a FAIL is a nonzero exit status.
- **Own bases:** 0.018 D (per-channel 0.002–0.018 D), which passes. **Family
  basis:** 0.024 D, reported without gating.
- Signed mean (bias): 0.018 D own, 0.024 D family. Pointwise maximum: 0.035 D
  own, 0.037 D family. Neither is gated.
- **Blue** agrees within 0.0085 D on each stock's own basis (250D; 0.0052 D on
  500T) and within 0.0045 D on the family basis, 0.002–0.004 D mean absolute.
- **Green** below 2.1 D runs 0.003–0.006 D mean absolute, maxima 0.015–0.019 D
  (the first point at or above 2.1 D is a shoulder point). It climbs to
  0.037 D at the shoulder, where the Academy's own linear fit misfits green by
  0.032–0.053 D.
- **Red** carries a near-constant offset of opposite sign per stock, present at
  D-min, which correlates with the traced mask's disagreement with the sheet's
  red D-min. The comparison does not separate mask, matrix-fit and dye-model
  error.
- The comparison tests the dye spectra, the mask and the two responsivity
  tables, and no part of the scan side. A +1 nm shift of the Status M red
  responsivity moves 250D's red mean by 0.003 D and single points by up to
  0.009 D. The table's explicit entries match the 1995 edition of ISO 5-3.

**Trace budget** (instrument not distributed). The quantity perturbed is
APD(mask + dye) − APD(mask) on the engine's 402–798 nm grid, with RP 180
carried as a separately named comparison. Each per-layer family is worst-cased
over all eight sign patterns, the joint term over the 128 combinations. Three
sample groups are never merged: the dye 0–2.2 box; an equal-amount diagonal
(k, k, k), which is not a neutral exposure (decoded through each stock's scene
engine it spreads the layers' exposures by 1.2–2.3 stops); and each stock's own
characteristic-curve neutral series.

| term | mean | max |
|---|---|---|
| flat per-layer offset at the inter-stock spread (median 0.021–0.031 D per dye), neutral series | 0.007–0.009 D | 0.033–0.036 D; 0.060 D over the box |
| own dyes and mask as the film, family as knowledge, neutral series | 0.002–0.005 D | 0.015 D |
| the same, over the box | 0.004–0.010 D | 0.050 D |
| shift, ±1.5 nm per layer (surrogate) | 0.010–0.014 D | 0.026–0.039 D |
| stretch, 0.4% (surrogate) | 0.002–0.003 | 0.007–0.015 D |
| three synthetic families jointly | 0.017–0.024 | 0.069–0.113 D |

- The joint maximum is 0.069–0.077 D on the neutral series and 0.113 D over the
  box: the branch's largest model-side exposure, bounded by surrogate, an
  extremum over the shapes tested. A digitisation bias common to all four
  traces is invisible to the spread; a second independent Vision3 source would
  convert the surrogate bound into a measurement.
- In RP 180 the same perturbations run about four times larger in the mean
  under the shift, four to five times jointly and about ten times under the
  stretch, reaching 0.47 D under the shift and 0.75 D jointly. Those figures
  describe the archived metric only.

**Authoring hazards of per-stock scripts.** A copied engine can keep the source
stock's output filename and overwrite its cube. `DMAX` is a corridor choice,
never the film's physical D-max; if a regenerated cube does not match the
shipped one, check this constant first.

### `v3_scene_engine.py`

The ECN-2 branch's secondary, scene-referred path and its only per-stock
engine. `v3_scene_engine.py --stock {50D,200T,250D,500T}` builds
`Vision3 <Stock> to Scene DWG.cube` under `builds/monochrome/ecn2/`: scanner
density to scene-linear DaVinci Wide Gamut (D65), unclamped, at the ADX16
cube's input point (OD/3.30, D-min excluded, behind the 3.3 preshaper).

Inputs: the LED SPD; the stock's own `Vision3_<Stock>_dye_density.json`,
`_datasheet_curves.json` and `_spectral_sensitivity.json`;
`StatusM_ISO5-3.json` and `CIE1931_2deg_CMFs.json`; the reflectance sets.

Per lattice node:

1. de-normalise to scanner density;
2. Gauss–Newton unmix through Φ to image-dye amounts on the stock's OWN traced
   dye set. Φ is the scanner SPD × sensor response (unity under
   `--sensor none`) × 10^−Dmin(λ), the stock's own traced Minimum Density curve
   (register #17);
3. per layer, look the amount up on that layer's neutral-scale table (amount
   against logH), clamped at both ends on the inverse;
4. relative layer exposure L = 10^(logH − logH_mid);
5. a 3×3, weighted least squares over 2,993 measured reflectances, maps L to
   XYZ (D65);
6. XYZ (D65) to DWG linear through the standard DaVinci Wide Gamut matrix.

**Neutral amount tables (step 3).** The sheet's curves are Status M INTEGRAL
densities of one neutral series; the largest off-diagonal term of the unit-peak
dyes' Status M matrix is 0.11–0.15 of the diagonal. The tables are solved from
all three curves at once, over the traced mask.

- The solve closes to 4 × 10⁻¹⁶ D on every stock. The final monotone tables
  close to 4 × 10⁻¹⁶ D on 50D, 200T and 500T, and 4 × 10⁻⁴ D on 250D, where
  five yellow points are dropped. Midscale amounts are 0.55–0.77 per layer.
- No point of the 50D, 200T or 500T tables needs a negative amount. On 250D
  12.7% of the toe does, because the traced mask's Status M red exceeds the
  sheet's D-min red by 0.031 D; the small negative amounts are kept.
- Reading one channel's curve as one layer's would place the layers' exposures
  0.09–0.22 logH apart at midscale and up to 0.44 logH apart at +1.5 stops, a
  cast the neutral ramp cannot see.
- Each table is made strictly increasing by a reverse-scan running minimum
  (0–5 points dropped per layer). The forward model extends each table by its
  terminal slope; the inverse clamps at both ends (Rule 4: past the
  shoulder a small overshoot in amount would read as many stops of invented
  exposure). The build asserts the clamp at both ends of every table.

**logH_mid (step 4)** comes from the traced midscale-neutral curve: Status M
integrated over the curve's measured support, responsivities renormalised,
char-inverted per channel and averaged.

- The three per-channel values disagree by 0.026–0.103 logH, a colour residual
  the scalar average does not remove (Known limitations).
- 500T's midscale trace ends at 640 nm, below 69% of the red Status M weight,
  so its red value is a partial-band density inverted against a full-band
  curve. The build prints each channel's excluded share and warns above 5%.
- The sheet's camera-stops zero is printed as a cross-check and not used. It
  differs by 0.067–0.404 logH, a uniform per-stock exposure trim.

**Matrix (step 5).** The reflectances are ColorChecker 24, Munsell glossy and
matt, and NIST skin, under the stock's balance illuminant (D55 for 50D/250D, a
3200 K blackbody for 200T/500T), Bradford-adapted to D65.

- The grey constraint M·1 = XYZ(18% grey) is imposed inside the solve, so a
  flat 18% grey on the characteristic series lands on Y = 0.18. The build
  prints the constrained and the row-rescaled unconstrained residuals and
  asserts the order.
- Set totals (ColorChecker 24, Munsell glossy 24, matt 12, skin 24, each
  spectrum weighted set total over set size) are a stated preference. They give
  the 100 skin spectra 28.6% of the objective.

**Grids.** The colorimetric grid runs 380–730 nm and truncates 21 nm of traced
50D yellow-layer toe below 380 nm. Synthesising reflectance data to integrate
against it is forbidden: the loader refuses a reflectance set if any spectrum
fails to cover 380–730 nm. The densitometry grid runs from 402 nm to the end of
the dyes' measured support (760 nm on 50D, 798 nm on the other three, capped at
800 nm); the LED SPD is measured to 780 nm and zero beyond.

- A 730 nm cap would discard the red LED's tail behind the cyan dye. Under the
  unity sensor that tail moves scanner density by up to 0.013–0.020 D, and the
  decoded layer exposure by 10–16% at the 99th percentile and 29–51% at most,
  over 2,000 uniform dye states per stock (an observer-area fraction of
  0.04–0.19%). Under the a7R III response the same band moves density by less
  than 5 × 10⁻⁶ D.

**Self-report across the four stocks.**

| item | figure |
|---|---|
| ColorChecker matrix residual (training set) | 2.18–2.64 ΔE2000 mean, maxima 4.73–5.90; worst patch cyan on 50D and 250D, green on 200T, white on 500T |
| constrained fit against the row-rescaled unconstrained fit | weighted XYZ residual 6.0–10.2% lower |
| NIST skin, withheld from the fit against in the fit | 2.54–3.33 against 1.51–2.02 |
| halving or doubling any one set's weight | pool mean moves by up to 0.31–0.39 ΔE2000 from the shipped matrix |
| traced mask Status M against the sheet's D-min triplet | within 0.045 D on every channel of every stock |
| neutral exposure ramp | exact from 1.5 decades below logH_mid to 2 above on every stock, and at 2 below on 200T and 500T; on 50D and 250D that point lies below the published toe (tables begin 1.59 and 1.95 decades below logH_mid) and reads the toe clamp: Y/Y₀ 0.026 and 0.011 against 0.010 |
| traced midscale spectrum through the delivered inverse and matrix | Y 0.159–0.184 against 0.18; ΔE2000 off neutral at matched luminance: 200T 1.4, 500T 3.0 (red LED 41% outside the trace's support), 50D 6.2, 250D 11.3 |
| corridor requirement | 1.86–2.02 D against DMAX 3.30, 64–77% headroom |
| node solve, on the 63–65% of nodes inside the dye box | mean 0.006–0.023 D, above 0.02 D on 1.0–3.3% of them |
| DWG range | no lattice node negative |
| serialised round trip | 3 × 10⁻⁷ |

**Which checks are independent evidence.**

- The ColorChecker "full chain" line is a plumbing check: forward and inverse
  share machinery, so it collapses to the matrix-only residual.
- The table solve closes on the curves it was solved from: a consistency check.
- The sheet quantity the inverse never consumes is the characteristic sheet's
  D-min triplet, against the traced mask's Status M.
- The one comparison against a quantity measured outside the repository is the
  Annex C check.

**None of these checks bears on the off-neutral inverse.** The neutral series
fixes one path through a three-dimensional exposure response, and the identity
coupling is one of many rules that reproduce it. A diagnostic coupling of 1.10
on the diagonal and −0.05 off it, back-solved onto the same series, reproduces
the neutral scan within 4 × 10⁻⁴ D on 250D and 10⁻¹⁵ D on the others. It
decodes the training reflectances 1.6 ΔE2000 mean and 4.9–5.2 maximum apart
from the shipped chain, with single layers up to 0.42–0.73 stops apart. No such
coefficient is installed.

**Interpolation.** The output is exponential in the input on a lattice uniform
in density. Probe: 5,000 fixed-seed dye states drawn uniformly over each range,
serialised cube against the exact chain, relative error. The published span is,
per layer, the top of its neutral table: dye 0–1.69 to 0–2.02.

| range, tetrahedral | share of samples | mean | 99th percentile | maximum |
|---|---|---|---|---|
| each stock's published characteristic span | | 1.6–1.9% | 9–11% | 22–48% |
| the full dye 0–2.2 working range | | 1.3–1.7% | | 20–46% |
| span, trilinear | | 2.2–2.6% | 12–15% | 24–49% |
| clean cells of the span | 80–84% | 1.5–1.7% | 7–8% | 16–18% |
| remaining cells of the span | 16–20% | 3.6–4.1% | 14–17% | 22–48% |
| declared operating region: clean cells below 100× mid-grey | 74–81% | 1.5–1.6% | 6–7% | 16–18% |
| the same, camera-named builds (83–88% clean cells) | | 1.1–1.2% | 4–6% | 7–14% |

- A cell is clean when all eight corners converged to within 0.001 D and every
  layer's amount at every corner lies within both ends of its neutral table.
  The cells that produce the maxima straddle the top of a layer's published
  curve, where the clamp caps what a corner beyond the table can carry.
- Within the operating region, by exact-chain luminance, the mean is 0.8–0.9%
  below mid-grey, 1.1–1.3% from mid-grey to ten times it, and 2.0–2.3% to a
  hundred times it.
- A finer lattice would track the engine more closely at the shoulder without
  making the recovered exposure more trustworthy: there the model's own
  sensitivity amplifies every input error.

**ColorChecker exposure sweep** through the delivered lookup at −4 to +2 stops,
retaining a patch only where the exact inverse returns it unclamped and its
scan lies inside the cube (15, 19, 24 and 24 of the 24 patches on 50D, 250D,
200T and 500T). Worst-channel error:

| exposure | worst-channel error |
|---|---|
| nominal | at most 1.1–1.7% |
| two stops under | 1.7–6.9% |
| four stops under | 22–97%; a doubling of exposure fails to double the output by up to 17–39% |

These are lattice errors (denominator floor 0.001 DWG) and are reducible: the
same lattice storing log exposure, exponentiated and matrixed after the lookup,
probed at exact corner values, holds the declared region at 0.4% mean and
2.2–2.9% at the 99th percentile, maxima 7–17%. That needs a decode stage the
Resolve chain does not have; the linear cube ships.

The region does not certify two things:

- **A density residual bounds no exposure error.** ±0.01 D on one scanner
  channel about a neutral moves a layer's decoded exposure by up to 0.09–0.10
  stops at nominal exposure and 0.15–0.25 stops four stops under; Y moves by
  4.4–4.9% and 7–12%. The perturbation is a diagnostic size.
- **The cube carries no per-pixel flag.** Unconverged and clamped nodes carry
  values like any other.

## Current state by stock

**Reversal (E-6).** Target D50 XYZ, corridor DMAX 5.00, 65³, narrowband. All
four stocks are complete, on integration grids derived from measured dye
support (register #2), with an exact white point.

| Stock | Cube |
|---|---|
| Velvia 100 | `V100_XYZ_D50.cube` |
| Velvia 50 | `V50_XYZ_D50.cube` |
| Provia 100F | `Provia100F_XYZ_D50.cube` |
| Ektachrome E100/100D | `E100_XYZ_D50.cube` |

Accuracy falls with transparency density on a monochrome build (register #9).
Ranges span the four stocks, Velvia 50 worst and Ektachrome E100 best,
tetrahedral:

| dye up to | RMSE | maximum |
|---|---|---|
| 2.0 | 0.0001–0.0002 | 0.0012 |
| 2.5 | 0.0002 | 0.0059 |
| 3.0 | 0.0002–0.0007 | 0.0329 |
| 3.4 | 0.0006–0.0043 | 0.2993 |

- The trilinear figures run 1.1–4.5× larger at dye 3.0; neither scheme bounds
  the other.
- On the cube's faces and corners, where the projection boundary runs, the
  reached samples hold to 0.005 D on Provia 100F and 0.025 D on Velvia 100, and
  reach 0.39 D on Velvia 50 and 0.61 D on Ektachrome E100.
- A camera-named build holds RMSE 0.0002 D and maximum 0.0005 D across the
  whole range on the a7R III, and 0.0006 D on the GFX 100 (Velvia 50 0.0021 D).

**Negative, ECN-2 (Vision3).** Corridor DMAX 3.3. Two routes fork at one input
point (normalised scanner density, D-min excluded).

- **Primary, ADX16.** `Vision3 to ADX16.cube`: one table for the family on the
  shared dye basis, read through the family-average traced mask. Node-solve
  mean residual 0.3986 D, above 0.02 on 36.8% of nodes (the mask raises the
  blue LED's tail, register #17). 65³ interpolation over the working range:
  RMSE 0.0003 D, maximum 0.0074 D tetrahedral (trilinear 0.0006 D and
  0.0128 D); the serialised round trip matches.
- **Secondary, scene-referred.** `Vision3 <Stock> to Scene DWG.cube`, per
  stock. Figures are under `v3_scene_engine.py`: ColorChecker matrix residuals
  2.18–2.64 dE2000 mean, maxima 4.73–5.90 (training set); neutral ramp exact
  over ±2 stops; corridor requirement 1.86–2.02 D against 3.30; 1.6–1.9% mean
  relative error within the published span (1.5–1.7% over the 80–84% of
  samples in clean cells; maxima 22–48%); shadow errors up to 22–97% four
  stops under nominal. The mid-grey anchor's per-channel spread is
  0.026–0.103 logH, the midscale spectrum decodes 1.4–11.3 ΔE2000 off the
  series' neutral, and the camera-stops zero differs by 0.067–0.404 logH. No
  frame has been checked against a known scene.

**Negative, C-41: the fleet is complete at twelve stocks**, corridor DMAX 3.3,
built from datasheets alone, the per-layer split inferred (register #8). Every
stock has a `<Stock>_StatusM.cube` and a print emulation paired by
manufacturer. **None of the twelve has a measured validation.**

| Stock | Print paper | Node-solve residual (mean D, % nodes >0.02) | 65³ trilinear probe over dye 0–2.2 (RMSE / max D) |
|---|---|---|---|
| Superia Premium 400 [JP] | Pro Laser | 0.3562 · 31.7%, best of the fleet | 0.0004 / 0.0073 |
| Ektar 100 | Endura Premier, Portra Endura | 0.3569 · 36.5% | 0.0005 / 0.0093 |
| Fujicolor 100 [JP] | Pro Laser | 0.3610 · 34.3% | 0.0004 / 0.0074 |
| Pro Image 100 | Endura Premier, Portra Endura | 0.3708 · 38.1% | 0.0006 / 0.0103 |
| Gold 200 | Endura Premier, Portra Endura | 0.3848 · 40.2% | 0.0006 / 0.0139 |
| Portra 160 | Endura Premier, Portra Endura | 0.3869 · 40.5% | 0.0005 / 0.0083 |
| Portra 800 | Endura Premier, Portra Endura | 0.3896 · 40.1% | 0.0007 / 0.0125 |
| Portra 400 | Endura Premier, Portra Endura | 0.3896 · 37.7% | 0.0005 / 0.0101 |
| Ultra Max 400 | Endura Premier, Portra Endura | 0.3930 · 41.1% | 0.0006 / 0.0143 |
| Pro 400H | Pro Laser | 0.4345 · 37.8% | 0.0007 / 0.0152 |
| Fujifilm 400 | Pro Laser | 0.5808 · 69.6%, least confident | 0.0016 / 0.0340 |
| Fujifilm 200 | Pro Laser | 0.5808 · 69.6%, identical to Fujifilm 400 | 0.0016 / 0.0340 |

- **The node-solve residual is not the accuracy of the cube.** It is a mean
  over the whole lattice, most of which no dye triple reaches. Read through the
  orange mask (register #17), the blue LED's long-wavelength plateau gains
  about four times its bare weight, and the blue channel saturates under a
  dense yellow dye.
- Over the range a negative occupies (dye 0–2.2) the probe is RMSE
  0.0004–0.0016 D, maxima 0.007–0.034 D, and the serialised round trip matches.
  Over the whole declared corridor it reaches 0.005–0.20 D RMSE and up to
  2.9 D, where the monochrome blue channel has saturated.
- The per-stock ranking reports fit quality alone ([C-41 fleet discrimination
  gap](#c-41-fleet-discrimination-gap-the-most-important-caveat-in-this-document)).

### Deliverables currently in the repo

```
builds/monochrome/  the monochrome scan tables, one folder per route;
                    a camera build builds/<Body>/ holds the same 21 names

builds/monochrome/reversal/      engine/reversal/reversal_transform.py;
                                 narrowband, DMAX 5.0, 65^3
  V100_XYZ_D50.cube, V50_XYZ_D50.cube, Provia100F_XYZ_D50.cube
  E100_XYZ_D50.cube              Ektachrome E100/100D; grid 401-700, the 401 floor
                                 avoiding a 1 nm clear hole that caps modelled blue
                                 density at 3.41 D
                                 All four: white point exact; 49.7% to 58.7% of
                                 nodes lie outside the dye gamut and hold a
                                 projected value

builds/monochrome/ecn2/
  Vision3 to ADX16.cube          Vision3 -> ADX16 code values over Academy
                                 Printing Density, DMAX 3.3
  Vision3 <Stock> to Scene DWG.cube
                                 per stock (50D, 200T, 250D, 500T): scanner density
                                 -> scene-linear DaVinci Wide Gamut (D65), DMAX 3.3,
                                 output unclamped

builds/monochrome/c41/           engine/c41/ with --stock
  <Stock>_StatusM.cube           scanner density -> Status M density (D-min
                                 excluded; corridor 3.30); every print paper and
                                 the Print Adjustment DCTL consume it

builds/print/                    camera-independent
  DisplayP3/                     Display P3 (D65), SDR, 19 cubes, named by paper;
                                 every material viewed under D50 adapted to D65
  <Stock>_EnduraPremier_*        Portra400, Portra160, Portra800, Ektar100, Gold200,
                                 Ultramax400, ProImage100 (E-4070, tricolor)
  <Stock>_PortraEndura_*         the same seven Kodak stocks (E-4021, tricolor;
                                 the lower-contrast paper)
  <Stock>_ProLaser_*             Fujifilm400, Fujifilm200, Fujicolor100,
                                 Premium400, Pro400H (Pro Laser TYPE II)

DCTLs (release assets)
  Preshaper 5.0.dctl             reversal, monochrome: clamp(-log10(linear),0,5.0)/5.0
  Postshaper 5.0.dctl            x 5.0 back to density
  Preshaper 5.25.dctl            reversal corridor of every camera build on the
  Postshaper 5.25.dctl           release
  Preshaper 3.3.dctl             negative path: anchored linear -> -log10 -> /3.30
                                 -> clamp [0,1]; Diag mode passes raw scanner
                                 density for scope checks
  XYZ D50 to DWG.dctl            one explicit 3x3: un-normalise by D50 white ->
                                 Bradford D50->D65 -> XYZ->DWG. The cube's
                                 white-relative XYZ is NOT true CIE XYZ (film base
                                 = 1,1,1), so a CST cannot convert it
  Density to Linear.dctl         10^-D linearisation plus AESTHETIC density trims
                                 (master/RGB offsets, output gain); trims at
                                 defaults on the D50 XYZ chain
  Printer Lights ADX16.dctl      per-channel density trims in APD after the ADX16
                                 cube, before the Academy decode; Locus Stock
                                 applies the stock's grey trims and makes Master
                                 follow its neutral series. Generated by
                                 engine/ecn2/printer_lights_dctl.py
  Print Adjustment.dctl          after StatusM, before the print cube: gamma about
                                 a pivot plus gain (darkroom mode) or a literal
                                 gain*k^gamma, plus per-channel offsets; Locus
                                 Stock follows the stock's neutral series.
                                 Pivot's default 0.22 is mid-grey on every print
                                 cube. Defaults no-op
  Density Crosstalk.dctl         OPTIONAL, after the Status M cube, before Print
                                 Adjustment: k <- P + M (k - P), P = 0.22. The
                                 diagonal sets a slope per dye layer; the
                                 off-diagonals are EXPERIMENTAL. Layer Basis
                                 selects M = Sn C Sn^-1; Hold Neutral keeps the
                                 input Status M diagonal fixed. No clamp. Defaults
                                 no-op. Generated by engine/c41/crosstalk_dctl.py
```

**Shipped total:** 12 Status M cubes + 19 print cubes + 4 reversal cubes +
1 Vision3 ADX16 cube + 4 Vision3 scene cubes = 40 .cube files from the live
engines, the set the manifest records. The seven Bayer camera builds and the
sensor-specific monochrome build add 21 scan
cubes each, 168 in all, for 208 on the release. No analytic transform DCTL is
generated on either path.

- **Release layout.** cube_manifest.json and the DCTLs are files of their own.
  `print.7z` holds the 19 print cubes, `monochrome.7z` the 21 monochrome scan
  cubes, and one archive per named build its 21. The 5.0 shaper pair serves
  `monochrome.7z` and `QHYCCD_QHY600M-PH.7z`, the 5.25 pair every Bayer
  camera archive.
- **No scene-referred landing on the C-41 path.** The print branch needs no
  spectral sensitivity, which lets the fleet be uniformly complete: Pro 400H
  publishes none.
- **Pairing is enforced in code** (`print_paper` in `portra_stocks.py`): no
  cross-paired cube such as Portra400_ProLaser_* is shipped.
- **Fujifilm 200 and Fujifilm 400 carry identical values in every shipped
  artefact**: all 274,625 entries of each pair match; the files differ only in
  the header comment. The two datasheets publish one shared spectral-dye-density
  chart (identical Bezier control points), and the chain depends on the
  negative only through its dye set and D-min spectrum. Their 0.5808 residual
  is the accepted cost of the uniform ±25 nm shift bound (register #8),
  compounded by the densest mask in the fleet (register #17). Both sheets print
  a RELATIVE log-sensitivity axis; only shape and channel structure may be
  relied upon.
- **The negative's H&D characteristic curves feed no shipped C-41 artefact.**
  The print branch reads the curves JSON only for the D-min spectrum
  (`endura_print_engine.py:405-409`). The scan already carries the film's
  characteristic curve; modelling it again would double-count. The curves
  remain as quality-control data: the basis-independent `char` column of
  `c41_stock_compare.py`.
- **DMAX 3.30 is load-bearing** across the negative cubes and the pre-shaper.

## Bounded systematics register (everything currently known and unpatched)

**The orange mask is a positive image, neither a filter nor a layer.** It is
unreacted coloured coupler in the magenta- and cyan-forming layers (Glossary),
maximal at D-min and falling as exposure rises. Surviving coupler plus unwanted
dye absorption is constant under the compensation target, and a per-channel
D-min subtraction removes that sum. Films can also target a negative gradient;
neither target is established for a current stock
(`knowledge/orange-mask-and-the-scanning-workflow.md`; Hanson, JOSA 40(3):166,
1950).

- **Scan to Status M: the approximation cancels.** The per-roll D-min
  subtraction and the datasheet's midscale-minus-D-min leave the same quantity,
  dye minus consumed mask; the Vision3 basis is itself relative to D-min. The
  Vision3 magenta curves carry consumed mask (below zero at the D-min blue peak
  on 250D and 500T). Cyan's share and each C-41 stock's contribution remain
  open (§2a, §5c of the note).
- **The dye curves keep their negative density, untested on film.** On Vision3
  those samples are traced; on the C-41 surrogates they are the warped Vision3
  family mean. Absolute density stays positive: D-min plus any stack up to
  amount 2.2 reads at least +0.089 D over 400–700 nm on all seventeen dye sets.
  `FILM_CLIPPED_DYE=1` clips the samples at zero, one other shape assumption
  that bounds nothing. On matched chains and 20 000 random dye triples the
  clipped chain differs from the signed one by:

  | route | mean ΔE2000 | maximum | above 1 |
  |---|---|---|---|
  | five C-41 print pairs | 0.010–0.067 | 0.647 | none |
  | Vision3 scene, 500T, −4 to +3 stops | 0.565 | 5.210 | 14.6% |
  | Vision3 scene, 250D | 0.228 | 1.796 | |

  ADX16 moves by at most 36 codes (§5d of the note).
- **Print emulation: the approximation does not cancel.**
  `endura_print_engine.py` builds the negative as
  `N(l) = dmin_spec(l) + sum dye*DYE(l)` (`endura_print_engine.py:890`): D-min
  at zero dye, the aggregate at the fitted midscale within the `fit_audit` RMSE
  (0.0108 D for Portra 400). Fixed effective spectra and mask consumption
  linear in the dye formed are modelling assumptions. The real systematic is
  **off-axis mis-attribution**: each fitted per-layer curve carries a share of
  mask consumption apportioned at the neutral ratio, so at saturated colours
  the split is underdetermined. The lock holds the drift to zero on the grey
  axis only.
- **The neutral ramp cannot close this.** One free parameter subtracting mu
  times the stock's own D-min improves the aggregate fit by 18–25% on the four
  clean Kodak stocks (mu about 0.14–0.20), but a flat constant vector fits
  better than the real D-min on every stock (Portra 400 0.00782 against
  0.01054, Ektar 0.00714 against 0.00955, Gold 0.00669 against 0.00794, Ultra
  Max 0.00755 against 0.00899), and on Portra 160 and the Fujifilm stocks the
  reversed D-min beats it outright (0.00836 against 0.01462). The gain is the
  added degree of freedom. Test such a diagnostic against a shape-matched
  control. Closing the defect needs spectral density at several exposure levels
  and off-neutral R/G/B separation exposures, the wedges `DIR_MATRIX` also
  needs.
- **Rejected: spektrafilm's representation**, which encodes mask consumption
  as negative absorption within the per-layer curves. Its negative bands sit
  under other layers' peaks (cyan negative at 440–465 and 535–565 nm; magenta
  negative at 650–750 nm): the signature of crosstalk unmixing (its commit
  `feat: non-linear unmixing of status densities`). The measured aggregate
  here, midscale minus D-min, never goes negative on any stock (minimum
  0.22–0.53 D).

The entries below are documented and left in place.

1. **380-400 nm grid truncation (Vision3/RP 180 only).** Blue printing
   density is overestimated by ~0.02-0.05 D at typical yellow concentrations.
   The Kodak datasheet's starting wavelength sets the truncation, and the rig
   cannot measure it (phosphor cuts off ~420 nm). APD is unaffected: 0.2% of
   its blue integral lies below 400 nm against RP 180's ~3.5%.
2. **Cyan long-wavelength truncation: handled for the shipped reversal cubes;
   a bounded-observer residual remains.** `dye_support_grid()` derives the
   grid from each stock's measured dye support (union of the three curves,
   floored at 400 nm); the print path applies the same rule as
   `PrintConfig.neg_support_mode="truncate"`. Grids: Velvia 100 400-710,
   Velvia 50 400-710, Provia 100F 400-719, Ektachrome 401-700. A fixed 400-730
   grid would fabricate 11-20 nm of clear film on the three Fuji stocks.

   Fixed against support-derived grid, scored against the correct physics over
   reachable dye states (0-3.4, 20k samples):

   | stock | fixed-grid RMSE / max | support-derived RMSE / max | neutral spread at dye 3.5, fixed / derived |
   |---|---|---|---|
   | Velvia 100 | 0.0133 / 0.173 D | 0.0009 / 0.003 D | 0.17 / 0.07 D |
   | Velvia 50 | 0.0319 / 0.392 D | 0.0009 / 0.003 D | 0.78 / 0.28 D |
   | Provia 100F | 0.0161 / 0.223 D | 0.0009 / 0.003 D | 0.68 / 0.39 D |
   | Ektachrome | 0.0232 / 0.246 D | 0.0010 / 0.003 D | 0.32 / 0.05 D |

   - Spurious hard ceilings (X-density 3.30 D Velvia, 3.73 D Provia; Z-density
     3.41 D Ektachrome) do not arise. Ektachrome's set is neutral-forming, so
     equal amounts read neutral; the V50/Provia spread is real
     (unit-peak-normalised sets).
   - **The defect prevented.** Dye plots end at 710 nm (V100) / 718-719 nm
     (Provia) with cyan still 0.29 / 0.59 D. A grid past the edge treats the
     band as clear film. Status A red carries ~0.02% of its weight there, a
     hard ceiling at `-log10(0.0002) = 3.708 D`; a "negligible,
     ~0.00004 D/unit" framing holds only below ~cyan 2.5. The cost is up to
     **0.24 D max** in deep shadow (dye 2.5-3.5), negligible below dye ~2. On
     the D50 cubes the X channel carries 0.066% (V100) / 0.034% (Provia)
     beyond the edge: ceilings of X-density 3.18 D / 3.47 D against 3.71; at a
     dye-3.5 neutral the clear-tail term would be 54% / 90% of the X signal,
     and an opaque tail would mean +0.34 D / +0.99 D.
   - **Corridor clipping is distinct from LUT resolution.** Beyond dye 4.0 on a
     4.5 corridor, V50 and Provia degrade to RMSE 0.009 / 0.017 D (scan
     densities 4.91 / 5.06 D). In-corridor samples converge with LUT size
     (0.0009 → 0.0002 D, 33→65); the clipped 0.86% flatten toward a nonzero
     floor (0.0977 → 0.0693). On the a7R III at 5.25 both sit at RMSE 0.0003 /
     max 0.0009 D over dye 0-4.0 (trilinear; 0.0002 / 0.0005 D tetrahedral),
     with zero clipping. Split samples by whether they clip.
   - **What survives.** The observer is truncated at the dye edge and
     renormalised. For Ektachrome 0.138% of X weight and 0.049% of Y are
     omitted above 700 nm, where cyan is still ~0.75 D; 0.22–0.26% of Z is
     omitted below 400 nm on every stock. Every reversal build prints the
     bracket on a neutral stack (`tail bracket` lines). Below the grid the
     extremes differ from the truncation by no more than 0.006 D in Z at dye
     2.5. Above it, a clear cyan tail lowers X against the truncation by:

     | stock | neutral dye 2.0 | dye 2.5 |
     |---|---|---|
     | Velvia 100 | 0.019 D | 0.051 |
     | Velvia 50 | 0.036 D | 0.106 |
     | Provia 100F | 0.022 D | 0.070 |
     | Ektachrome E100 | 0.060 D | 0.166 D |

     The held end sits within 0.010 D of the truncation on the three stocks
     whose cyan is still dense at the edge. Provia's cyan trace ends at
     718.3 nm, within 0.7 nm of its grid end, so held and clear all but
     coincide (−0.066 against −0.070 D at dye 2.5): its shipped truncation sits
     0.021 D (dye 2.0) and 0.066 D (dye 2.5) outside its own bracket in X, a
     known bias. The cube stays on the truncation for all four stocks (uniform
     treatment). Deep shadows (dye ≳2.5) are qualitative.
3. **Not applicable: the Velvia 50 yellow reading floor.** Under broadband
   illumination yellow is indistinguishable from the baseline beyond 592 nm,
   at a plot floor of about 0.013 D per unit of yellow. The 640 nm LED renders
   it irrelevant. Retained so that the numbering remains stable.
4. **Not applicable: quadratic and cubic DCTL extrapolation.** Analytic
   transform DCTLs are fitted over dye 0–3 while the clamp admits values up to
   DMAX. No such DCTL is exported. Retained so that the numbering remains
   stable.
5. **Reversal (5.00 or 5.25) and negative (3.3) shaper pairs are not
   interchangeable, and neither are the two reversal pairs.** Take a cube and
   its shapers from the same build. Crossing corridors silently rescales
   density by their ratio.
6. **The roll anchor has no independent check on real film.** Anchors are
   measured from real frames on the a7R III and the bake's arithmetic is
   verified. No densitometer or second instrument has read the same base.
7. **Axis-calibration uncertainty varies by datasheet source.** Provia's
   gridlines are unevenly spaced in the source artwork (up to 1.2 nm /
   0.005 D residual after least-squares fit). Velvia 50's chart is a 600 dpi
   raster requiring joint multi-track tracing. Registration audits are in
   their dye JSONs.
8. **Per-layer C-41 dyes are inferred, across the whole chain and all twelve
   stocks.** Each stock's dye set is a 9-parameter warped-Vision3-basis fit to
   the aggregate datasheet curve. One aggregate spectrum cannot determine
   three components: the root cause of the fleet discrimination gap, closable
   only by measured separation wedges. **Agreement between two stocks is not
   independent validation of either.**

   | stock | aggregate RMSE (D) | max (D) | cyan shift sC (nm) | decoupling cond |
   |---|---|---|---|---|
   | Portra 800 | 0.0078 | 0.0331 | +21.99 | 1.4144 |
   | Ultra Max 400 | 0.0083 | 0.0435 | +22.18 | 1.4195 |
   | Ektar 100 | 0.0086 | 0.0729 | +22.50 | 1.4079 |
   | Gold 200 | 0.0088 | 0.0396 | +21.28 | 1.4140 |
   | Pro 400H | 0.0103 (in-band 0.0105, traced tail 701–716 nm 0.0009) | 0.0302 | +15.53 | 1.4739 |
   | Portra 400 | 0.0108 | 0.0685 | +23.71 | 1.4175 |
   | Fujifilm 400 / 200 | 0.0119 | 0.0413 | **+25.00 (pinned)** | 1.6676 |
   | Pro Image 100 | 0.0135 | 0.1243 | +25.00 (free, 0.0004 nm inside the bound) | 1.4032 |
   | Portra 160 | 0.0138 | 0.0785 | +20.85 | 1.4185 |
   | Superia Premium 400 | 0.0196 | 0.1479 | +19.90 | 1.4706 |
   | Fujicolor 100 | 0.0207 | 0.0846 | +15.13 | 1.4295 |

   The decoupling condition is that of the LEDs read through each stock's own
   mask (register #17).

   - **Every stock's cyan sits to the red of the Vision3 basis cyan**, sC
     between +15 and +25 nm. Three of the twelve rest on or within 0.001 nm of
     the bound; the other nine fit freely between +15.1 and +23.7 nm. The fit
     establishes a direction only. The neutral axis is unaffected: ramp chroma
     error 0.0002.
   - **The shift bound is a uniform ±25 nm** (`portra_stocks.py`), an
     extrapolation guard with no chemistry behind it. A per-stock bound is
     inadmissible: different priors would make cross-stock comparison
     meaningless. A refit of the fleet at each bound:

     | shift bound | mean aggregate RMSE (D) | pinned |
     |---|---|---|
     | ±15 | 0.0160 | five at exactly +15.000 |
     | ±20 | 0.0137 | seven of twelve at +20.00 |
     | ±25 | 0.0122 | two of twelve at +25.00 |
     | ±35 | 0.0118 | none; largest shift +28.58 nm |
     | ±50 | 0.0118 | |

     Releasing to ±35 buys 3% of residual and moves the modelled cyan peak to
     718 nm; the dye arrays end at 700 nm with every fitted cyan still rising,
     so the peak is already an extrapolation at ±25. Tightening to ±20 or ±15
     costs 13% and 32%. Raising the 700 nm ceiling without traced samples
     degrades measured RMSE by 500–1160% and inverts every fitted cyan shift
     (Invariants).
   - **Withheld-tail test.** The Fujifilm-family sheets publish dye density to
     716–719 nm (Kodak to about 703); the five curves files carry the traced
     tail as `spectral_full_support`. The aggregate's red-region maximum is at
     694 nm on Fujicolor 100, 696 on Pro 400H, 701 on Fujifilm 200/400 and 705
     on Superia Premium 400. Fujifilm 200/400 and Superia Premium 400 predict
     the withheld tail at 0.004 and 0.007 D RMSE; Pro 400H, fitted over
     400–700 nm alone, at 0.0017 D with the cyan peak at 700.0 nm; Fujicolor
     100 overshoots by 0.045 D mean.
   - **Width bounds** are per dye and uniform: magenta and yellow 0.5–2.0, a
     range no stock reaches; cyan 0.85–1.15, an extrapolation guard. Held to
     0.85–1.15, the magenta width pins Pro 400H at 1.15 and sends its fit into
     the other cyan basin (pinned at +25.00, peak 713.7 nm, missing the tail by
     0.0525 D). Released, the cyan width makes the tail predict worse: Superia
     Premium 400 0.0070 → 0.0518 D, Fujicolor 100 0.0491 → 0.0700 D.
   - **The shipped Pro 400H fit admits its tail** (registry
     `fit_traced_tail`): 16 samples as extra residual terms, output curves on
     400–700 nm; 0.0105 D in-band and 0.0009 D on the tail, no parameter on a
     bound, cyan peak 699.9 nm. Against the 400–700 fit no dye curve moves by
     more than 0.0009 D, and the Status M reconstruction by 0.0001 D. The
     other four keep the 400–700 fit: Fujifilm 200/400 and Superia Premium 400
     move under 0.3 nm with the tail admitted; Fujicolor 100 moves from 702.4
     to 699.0 nm at 0.0207 → 0.0216 D in-band and still misses the tail at
     0.022 D.
   - **Cyan-peak ambiguity** (cyan shift held, the rest refitted; 1 nm steps,
     crossings bisected to 0.05 nm). Within 5% of each stock's best residual
     the peak moves 0.5 nm on Fujifilm 200/400, 3–7 nm on seven further stocks
     and 12–16 nm on Portra 160, Portra 800 and Pro Image 100. The same three
     move 10–16 nm across the four Vision3 stock bases and the family average,
     where the other nine move under 3 nm.
   - **Reach into the conversion.** The reconstructed midscale's Status M
     spreads no more than 0.014 D in red and 0.005 D in green or blue across
     any such set. Inverting each member on identical scan densities (216
     dye-amount triplets, unity sensor), a member deviates from the shipped
     conversion on unequal-amount inputs by up to 0.100 D in green for Portra
     160, 0.062 Portra 800, 0.056 Superia Premium 400, 0.051 Pro Image 100,
     0.040 Fujicolor 100 and 0.004–0.025 D on the other seven; equal-amount
     inputs deviate 0.002–0.051 D. The shipped cubes were not rebuilt per
     member, and the print path is not propagated.
   - **Pins signal under-determination of the basis**, never an emulsion
     property. Fujifilm 200 and 400 pin the cyan shift and the 0.85 cyan width
     and take a magenta width of 0.728, where every other stock lies in
     0.84–1.19. Their node-solve residual of 0.5808 is the accepted cost of
     the uniform bound.
   - The twelve fitted dye sets lie within a mean |ΔD| of 0.005–0.098 of one
     another, most pairs in 0.009–0.066.
   - **C-41 interimage and DIR-coupler effects are unmodelled.** The structure
     (`DIR_MATRIX`, grey-ramp pre-compensation, identity default) exists in
     `engine/ecn2/v3_scene_engine.py` only. No source measures negative and
     reversal interimage by one method
     (`knowledge/interimage-effects-and-stock-differentiation.md` §4a).
   - `logH_mid` shows a per-channel spread of 0.23 logH. The mean is used
     wherever a characteristic curve is inverted, and cancels on neutrals.
   - Status M red responsivity is truncated at the 700 nm dye-chart edge and
     renormalised: 0.49% of the red area on the 1 nm grid.
   - A datasheet anomaly persists: the spectral chart's midscale neutral
     integrates to a Status M red of 0.983, against the judging table's
     gray-card corridor of 0.77–0.87. The gray-card point is unlocated without
     a measured roll.
9. **The monochrome cubes embed a flat sensor response, and naming a camera is
   worth a bounded and measured amount.** The engines integrate
   `PHI = LED_SPD x camera_SSF` in five places: `c41_statusm_engine.py`,
   `adx_engine.py`, `v3_scene_engine.py`, `portra_decompose.py` and
   `reversal_transform.py`. Every negative engine adds a D-min spectrum
   (register #17). All five row-normalise `PHI` and default to `--sensor none`.

   A constant response factors out of `D = -log10(INT LED*Q*T / INT LED*Q)`
   and moves no modelled density by more than 2e-16 D, verified. A
   wavelength-dependent one does not cancel. Illustrative tilts against a flat
   reference, measured on no sensor (D):

   | response tilt | R | G | B |
   |---|---|---|---|
   | 1% per 10 nm, dye 1.0 | 0.0008 | 0.0033 | 0.0006 |
   | 1% per 10 nm, dye 1.8 | 0.0014 | 0.0072 | 0.0017 |
   | 1% per 10 nm, dye 2.5 | 0.0021 | 0.0109 | 0.0035 |
   | 1% per 10 nm, dense yellow | 0.0001 | 0.0028 | 0.0376 |
   | 3% per 10 nm, dense yellow | 0.0003 | 0.0083 | 0.1201 |

   One published measurement of a monochrome assembly exists as a table: the
   Sony IMX455 behind the QHY600M-PH window (Ofek et al., 2023). It is a
   quantum efficiency, a per-photon quantity, and enters `PHI` as wavelength
   times quantum efficiency when the LED file records power. On that reading
   the modelled scan density, Portra 400 dye set through its mask, sits at
   most 0.017 D from the flat model at the tested equal-dye states (0.3, 1.2
   and 2.5 of each dye) and 0.034 D at magenta 2.5. If the LED file records
   photon flux the figures are 0.039 D and 0.111 D, the latter in blue at
   yellow 2.5. The export unit of the LED file is unrecorded and its
   confirmation is pending; the power reading is the working assumption. The
   case describes one unit of one assembly and bounds no population; the tilt
   rows above stay the illustrative scenario. The release carries the
   power-reading case as a sensor-specific monochrome build,
   `QHYCCD_QHY600M-PH`, built from `data/sensors/` at the 5.00 corridor. For
   that assembly the general monochrome build is the weaker set: it assumes
   the flat response that the measurement replaces. The ranking holds on the
   power reading and is unestablished on the photon reading.
   `knowledge/monochrome-camera-response.md` holds the authoritative figures,
   the unit argument and the limits of the source.

   A monochrome user can write a measured `Q` into all three channels of an
   SSF file, in the unit the LED file records. Peak-to-peak spread of scan
   density across the forty-four measured cameras, Portra 400 dye set through
   its mask (D). The "equal" states carry the same amount of each dye and are
   test states, distinct from a sheet's neutral series:

   | dye state | R | G | B |
   |---|---|---|---|
   | equal 0.3 | 0.0030 | 0.0071 | 0.0015 |
   | equal 1.2 | 0.0122 | 0.0408 | 0.0073 |
   | equal 2.5 | 0.0262 | 0.1210 | 0.0202 |
   | cyan 2.5 | **0.0425** | 0.0155 | 0.0035 |
   | magenta 2.5 | 0.0068 | **0.1743** | 0.0021 |
   | yellow 2.5 | 0.0010 | 0.0171 | **0.1178** |

   Against the a7R III specifically, a second camera would sit 0.006/0.021/0.004
   from the shipped cubes at equal 0.3, 0.024/0.113/0.020 at 1.2,
   0.052/0.280/0.072 at 2.5, and up to 0.48 in green at a dense magenta and
   0.78 in blue at a dense yellow. The mask roughly doubles the green and blue
   figures relative to a bare-LED reading.

   - **Below about 1.2 peak dye the camera is a second-order term**: under
     0.041 D peak-to-peak across the population, and under 0.12 D between the
     a7R III and the monochrome model. Above it the dependence climbs past the
     0.027–0.049 D basis-sensitivity band of entry 8.
   - **Each channel is most camera-sensitive where its own dye is dense**, and
     green roughly twice as much as red or blue. The LEDs are 15, 32 and 15 nm
     FWHM in R, G and B; a narrower green LED would remove most of the
     dependence. A broadband scan would carry it at first order.
   - **The camera is not what blocks portability.** The other half of `PHI` is
     `film_scanner_SPD_combined.csv`, this apparatus's own LEDs.
   - **A colour filter is not purely a cost.** Replacing the held a7R III
     response with the constant model widens each channel's sampling band: the
     standard deviation widens from 16.4 to 21.8 nm in green and from 11.5 to
     20.1 nm in blue, enlarging the unreachable lattice. This is a model
     comparison; no filter has been physically removed. On the 3.3 corridor this is immaterial within the
     working range (C-41 trilinear RMSE 0.0004–0.0016 D, maximum 0.007–0.034 D
     over dye 0–2.2; tetrahedral 0.0002–0.0008 D and 0.003–0.018 D) and
     material over the whole corridor (tetrahedral 0.005–0.20 D RMSE, up to
     2.9 D): read through the mask, the blue LED's 540–660 nm plateau carries
     about four times its bare weight, first on the Fujifilm 200/400 mask. On
     the 5.0 reversal corridor it is why the monochrome cubes lose accuracy
     beyond dye 2.5; scan density still rises at slope 1.0 to 1.1 out to dye
     5.0 on both sensors.
   - Every camera figure comes from published sensitivity curves, and the
     tilt rows are invented illustrations; no second physical camera has
     scanned film through this chain. Thirty-eight of the forty-four
     come from one creator on one instrument and carry no `laboratory` field
     (`data/cameras/README.md`). No file declares a monochromator bandwidth or
     the lens and filter stack.

10. **Scan-side stray light is unmodelled.** `engine/` has no veiling-glare
    term on the capture side (`flare` in `PrintEmulationEngine` belongs to the
    print stage). An additive floor from glare, LED crosstalk or black-level
    residual does not cancel in `-log10(rate_film / rate_plain)`:

    | stray-light fraction | max measurable D | error at D 2.0 | at D 3.0 |
    |---|---|---|---|
    | 0.01% | 4.00 | 0.004 | 0.041 |
    | 0.1% | 3.00 | 0.041 | 0.301 |
    | 0.5% | 2.30 | 0.174 | 0.776 |

    The corridor ceilings are DMAX 3.30 (negative) and dye densities near 4.0
    (reversal). The term is known and unquantified. A certified step tablet
    (for example 21 steps spanning 0.05–3.05 D) scanned in the gate would give
    the linearity curve and the stray-light fraction per channel; a roll's own
    D-max cannot.
11. **Reversal interimage is unmodelled, and no structure exists for it.**
    `engine/reversal/reversal_transform.py` contains no `DIR_MATRIX`, no
    grey-ramp pre-compensation and no interimage stage. The cubes perform
    densitometry on dyes that already exist, so re-simulating interimage would
    double-count. What is lost is the ability to predict how two reversal
    stocks differ off the neutral axis from datasheet data alone. In reversal
    film interimage arises in the first, black-and-white development (iodide
    diffusion, enhanced with DIR hydroquinones) and is the principal
    correction for unwanted dye absorption; Fuji attributes the Velvia, Provia
    and Astia characters to it. No published IIE percentage exists for any
    stock in this fleet
    (`knowledge/interimage-effects-and-stock-differentiation.md` §4a).
12. **Most of the C-41 fleet fits against a bound.** Eight of the twelve
    stocks rest at least one shape parameter exactly on its limit; only
    Portra 160, Portra 800, Pro Image 100 and Pro 400H are free of one.
    `portra_decompose.py` derives the list from the solution, warns, and
    records it as `fit_audit.bounds_pinned`.
    - All eight pin the cyan width: Ektar 100, Ultra Max 400, Gold 200, Portra
      400, Fujicolor 100 and Superia Premium 400 at the 1.15 ceiling, the two
      Fujifilm stocks at the 0.85 floor. The two Fujifilm stocks also pin the
      cyan shift at +25 nm. No magenta or yellow width reaches its 0.5–2.0
      bound.
    - **The solve does not depend on where it starts.** On seven of the twelve
      stocks a seeded 64-point multistart finds a better optimum than a single
      fixed start, by 2.0–29.5% in RMSE (Ektar 100 the largest); on the other
      five the gain is under 0.03%. `fit_audit.multistart` records it.
    - **The ±25 nm bound is load-bearing for three of the twelve** (Pro Image
      100 at 0.0004 nm inside it). Any widening is justified against dye
      chemistry, never against the residual it would buy.
    - **The shift parameter is not the peak displacement.** The warp is
      `basis(p + (l - p)/w - s)`, whose peak lands at `p + s·w`: up to 15% of
      `s` apart at the width limits, so ±25 nm permits a true displacement of
      up to ±28.75 nm, and a stock at +25.0 nm may have moved by 21.25 nm.
      `fit_audit.peak_shift_nm` publishes the derived quantity.
13. **The digitised spectral curves carry fabricated edges, bounded but real.**
    Where a Kodak spectral trace stops short of the 400–700 nm frame, the
    digitiser flat-holds its last traced value: 53 samples across the seven
    Kodak stocks.
    - 34 are on Ektar 100, whose printed curves end at 684.9 nm: 16 samples
      per curve at the red end, D-min at 0.2582. Five stocks hold 0 to 2
      samples per curve. Pro Image 100's midscale trace begins at 402.97 nm
      (four midscale and two D-min samples held).
    - Replotted onto the chart, traced regions hit the ink on 100.0% of
      samples everywhere; the held edges hit it on 35.3% on Ektar 100 and
      100.0% elsewhere.
    - **Reach.** The decomposition masks its objective to measured support, so
      all 53 fall outside it, and the Status M cube is untouched. On the print
      path the D-min spectral density feeds the paper exposure integral to the
      400–700 nm grid edge: 17 of Ektar 100's held samples sit inside it and
      carry 31.5% of the cyan record's exposure weight. A linear continuation
      from the last ten measured samples moves the D-min by 0.009 D and the
      cyan record's printing exposure by −0.0014 log₁₀ E, about 0.005 stop.
      The Pro Laser paper's magenta dye curve is held for 33 samples the same
      way and hits the ink on 100.0% of them.
    - Recorded, uncorrected. Treat each curve as authoritative only within the
      `digitization_audit.spectral_dye_density.endpoints` range it publishes.

14. **Part of the Vision3 basis is tracker prediction, and the proportion is
    not published.** Where a column yields no centroid within tolerance, or
    the run is shared with a neighbouring curve, the tracer takes its own
    linear prediction. Trailing predicted columns are rolled back; interior
    ones are kept, undistinguished. The share is 0.4–5.2% for most curves,
    rising to 19.3% for Vision3 50D's magenta and 22.9% for 200T's magenta,
    which run through extended crossings. The ink test cannot see it (a
    predicted point at a crossing scores as a hit; the audit reports 100.0%).
    It bears on every C-41 stock through the surrogate basis. It is
    interpolation across ambiguous ink, hence a caveat.
15. **Paper channel assignment rests on vertical order or label placement,
    never on a measurement.**
    - Endura Premier: the digitiser sorts the three curves by descending
      bounding-box centre and names them R, G, B. The curves cross two or
      three times and touch to within 0.0000 D, so their order is not constant.
    - Pro Laser: each curve is named by its stroke hue, keyed by the sheet's
      coloured legend.
    - Portra Endura: the printed labels are read. R is the topmost curve at the
      R label's log exposure, B the lowest at the common right end, G the
      remainder. The digitiser refuses to write when either rule clears the
      next curve by less than 0.02 D; the margins are 0.076 D and 0.235 D.
    - The overlay cannot help: a channel swap preserves geometry and scores
      100%, measured.
    - The film path has three guards that do not transfer. Both sensitivity
      digitisers classify by peak wavelength against expected bands. The
      Fujifilm digitiser asserts that the characteristic curves do not cross.
      The Kodak digitiser asserts B > G > R by at least 0.05 D (smallest gap in
      the fleet 0.175 D on Fujicolor 100; verified to fail on a permutation at
      a worst gap of −0.48 D).
16. **Paper tone curves are evaluated with a terminal-slope linear extension
    beyond their digitised span, and the shipped cubes barely engage it.**
    `interp_lin` continues the local slope where a characteristic curve's data
    ends, the one deliberate exception to the rule that the model stops where
    the data does. Over the 65^3 print lattices:
    - the Endura Premier and Portra Endura builds engage it on 0.00% of nodes
      in every layer;
    - the Fuji build engages it on 1.06% of nodes in cyan and 0.02% in yellow,
      moving density by at most 0.027 D relative to holding the end value;
    - neither engages it on the printable window or the neutral calibration
      ramp;
    - the grey-axis lock's stored 1-D maps extend the same way outside the
      calibrated neutral span, on 24–36% of lattice nodes.
17. **The roll anchor subtracts D-min in integrated density, and the engines
    model what that leaves.** The cube receives
    `−log10(∫Φ·10^−(Dmin+dye·DYE) / ∫Φ·10^−Dmin)`: density under the
    illuminant `Φ·10^−Dmin(λ)`. That differs from density under the bare LED
    unless the mask is flat across each LED's band.
    - **Bare-LED against mask-filtered model.** Portra 400's D-min falls
      0.11 D across the green LED's 528–560 nm FWHM, Fujifilm 400's 0.05 D
      across the blue LED's. A neutral at dye 1.0 reads 0.056 D low in green
      and 0.009 D low in blue on Portra 400, and 0.060 and 0.055 D low on
      Fujifilm 400; box-corner maxima are 0.19–0.28 D in green and
      0.23–0.47 D in blue. Through the Endura Premier print (white-light
      kernel) a neutral Portra 400 negative rendered at a\* +3.8 / b\* −1.7 at
      k = 0.18 and a\* +6.9 / b\* −3.5 at k = 0.24 (ΔE2000 5.4 and 9.2); the
      off-neutral mean over the printable window was 2.4 ΔE2000 on Portra 400
      and 1.5 on Ektar 100.
    - `c41_statusm_engine.py` and the decoupling diagnostic in
      `portra_decompose.py` integrate the mask-filtered illuminant. Adding the
      roll's D-min back to a cube's Status M output for quality control
      carries the same non-commutation, 0.01–0.08 D in green over the box.
    - **ECN-2.** The film digitiser traces each sheet's dashed Minimum Density
      curve: 401–762 nm on 50D, 401–799 nm on the other three. Its Status M
      against the characteristic sheet's D-min triplet closes at −0.033 to
      +0.031 D in red, −0.025 to −0.036 D in green and −0.004 to −0.044 D in
      blue. The trace reads slightly lighter on every channel of every stock
      except 250D red, where it reads denser by 0.031 D. The scene cubes read
      each stock's own curve; the ADX16 cube reads the family average
      (inter-stock spread 0.053 D median, 0.033 / 0.016 / 0.066 D at the LED
      peaks). The ADX engine's neutral-axis check closes within 0.012 D on
      every stock; without the mask it leaves 0.06–0.08 D.
    - **ADX16 family mask.** A stock's own mask against the family mask costs,
      over the dye 0–2.2 box, 0.0004–0.012 D mean and 0.001–0.089 D maximum in
      APD, largest in green on 50D and 250D. Through the Academy decode a flat
      grey shows an AP0 channel spread of 6–18% at mid-grey, largest on 250D
      and 500T. A table built on the stock's own mask moves that spread by at
      most one percentage point: the spread belongs to the decode's
      reference-film assumption, and the trims correct it at one density.
    - **Reversal, surrogate base.** No reversal sheet publishes a base
      spectrum. Each build uses the characteristic curves' Status A D-min
      triplet, placed at the three Status A peak wavelengths and joined by
      straight lines. A neutral at dye 1.0 differs from the bare-LED reading
      by at most 0.0002 D; over the dye 0–4 box by 0.007 D on Ektachrome E100,
      0.002 D on Velvia 100 and 0.000 D on Provia 100F and Velvia 50 (sampled
      9×9×9 grid). The figures bound no other base spectrum.
    - **The missing band as a term.** Truncation at the support edge asserts
      that the uncovered bands transmit like the covered ones. The error
      budget carries the support policy itself: the negative's edge density
      held outward against the shipped truncation, each with its own re-solved
      lock, differs by 0.26 mean / 0.94 max ΔE2000 off-neutral on Portra 400,
      the fourth-largest term. Clear film in those bands, a permissive
      diagnostic, gives 7.0 / 11.2. On Pro Laser TYPE II the term is exactly
      zero. On the scan side the Status M red responsivity omits 0.49% of its
      area beyond 700 nm on the 1 nm grid (the 10 nm source table sums to
      0.28%): at equal dye 2.2 a clear red tail would read 0.091 D lower than
      the truncation on Portra 400 and 0.047 D lower on Fujifilm 400; the held
      edge reads 0.002 D higher. The two stages share the convention and do
      not add.
18. **Part of every fitted C-41 dye set rests on the basis's held blue edge.**
    `portra_decompose.py` warps the Vision3 basis by
    `basis(p + (λ−p)/w − s)`. The basis is measured on 402–798 nm and held
    flat outside it. A cyan at +25 nm reads the basis below 402 nm for every
    grid wavelength under about 427 nm, and at width 0.85 under 465 nm. The
    shipped curves carry blue-end plateaus, recorded as
    `fit_audit.basis_held`:
    - magenta held at −0.0057 over 400–409 to 426 nm on ten stocks;
    - cyan at 0.2164 over 400–465 nm on Fujifilm 200 and 400, and over
      400–425 nm on Portra 160;
    - yellow at 0.5103 over 400–403 to 411 nm on all twelve.

    The objective keeps those samples: the aggregate is measured there, and
    dropping it would leave the yellow peak unconstrained on the Fujifilm
    stocks. Under the other admissible prior (the descender continued linearly
    from its last 10 nm):
    - the fitted curves move by 0.008–0.029 D mean and up to 0.26 D at the
      blue edge;
    - scan density over the dye 0–2.2 box moves by 0.001–0.031 D mean;
    - a negative made under one prior, read by a cube built under the other,
      misreads Status M by 0.002–0.009 D mean and up to 0.064 D (green, Portra
      400), 0.017 D on Fujifilm 400.

    The linear prior reaches a lower residual on the Kodak stocks (Portra 400
    0.0077 against 0.0108 D) and a higher one on Fujifilm 400. Fit quality over
    an unmeasured band is not evidence, so the hold stays.
19. **The reversal sheets' neutral series is not visually neutral through the
    model, and the disagreement is larger than Status A placement can
    explain.** Each build reads the traced characteristic curves (Status A,
    base and fog included), subtracts the sheet's D-min per channel in
    integrated density, and solves for the dye amounts that reproduce all three
    curves at once. The solve closes at machine precision with non-negative
    amounts that fall with exposure on all four stocks (Velvia 50 shows 13
    small rises, tracing noise in its dashed band).

    | stock | a\*/b\* at Y = 0.18 on the D50 table |
    |---|---|
    | Ektachrome E100 | −0.4/−7.4 |
    | Velvia 100 | −1.7/−5.5 |
    | Provia 100F | −1.4/−2.7 |
    | Velvia 50 | −3.6/−3.2 |

    - Over visual density 0.3–2.0, |b\*| reaches up to 7.5.
    - **E100 internal control.** Its dye chart states that equal amounts form
      a visual neutral at 5000 K, and equal amounts through the same dyes and
      observer give a\*/b\* −0.1/+0.1. The disagreement therefore lies between
      the characteristic curves and the dye chart: the sheet's neutral series
      carries 20% less yellow than a visual neutral of its own dyes.
    - Shifting any Status A responsivity by ±10 nm moves b\* by at most 1.5 (a
      green shift moves a\* by ±4). Nulling E100's b\* would take +0.10 D on
      the sheet's blue record, Provia's +0.05 D.
    - Candidates, none settled: the sensitometric daylight series may not be a
      visual neutral at D50 by design; the Status A table's tails and the 2009
      edition are unverified (its explicit entries match the public 1995
      edition of ISO 5-3); the observer is truncated below 400 nm, worth about
      one unit of b\* in this direction.
    - Until a transparency is measured, the reversal cubes' neutral axis is
      read as carrying a possible blue-green bias of this size. The written
      cube reproduces the series to 0.0007 D, which is plumbing.

## The role of NamiColor in this project

NamiColor (open source, GPL-3.0, github.com/Wavechaser/NamiColor) is a generic
film-scan lineariser: `log10`, or `-log10` for negatives, then a per-channel
affine gain and offset aligned by eye against a neutral reference, landing in a
Cineon Film Log container. It has no spectral model, crosstalk correction or
standardised target.

This pipeline's cubes and DCTLs perform its channel-alignment step, spectrally
derived and metrically anchored. NamiColor is not placed after the postshaper:
its Negatives mode computes `-log10` of an already logarithmic quantity, where
the `10^-D` inverse is required (`Density to Linear.dctl`). NamiColor-style
per-channel offsets belong as aesthetic trims within that node or above it.

## Invariants

Each rule prevents a defect that is not apparent from the code alone.

- **Never let a held or zero-filled sample vote in a fit.** Fit only the
  measured region; do not default to 400-730 nm. Flat-holding the unmeasured
  400-403 nm blue edge degrades every Kodak C-41 dye fit by 3-7×. The warp's
  reading of the basis below 402 nm is a plateau nobody traced, carried only
  because the aggregate is measured there, marked in `fit_audit.basis_held`
  and bounded by its alternative prior (register #18, hard constraint 1).
- **Derive a curve's measured support from the data, never from a metadata
  field.** `reversal_transform.dye_support_grid()` reads support from
  `~isnan(values)`. Clamp any metadata-derived support with
  `min(hi, wl.max())`. `portra_decompose.py` reads
  `digitization_audit.spectral_dye_density.endpoints`, and the five
  Fujifilm-family C-41 stocks record an upper limit 16.9–19.1 nm above the end
  of their 400–700 nm array (the wider trace sits in `spectral_full_support`).
  The fit mask is saved only by a `GRID` that stops at 700 nm. Raise that
  ceiling without re-digitising and `resample()` supplies clear film across
  the difference: measured RMSE degrades by 500–1160% and every fitted cyan
  shift inverts.
- **Never bridge a gap where the curve left the chart.** Gold 200's cyan has
  a real gap at 470-485 nm, where the blue tail dives below the axis floor. It
  is kept null. The gap is a bracket [0, floor], and a straight line across it
  would sit above every true value; only an unknown between two samples may be
  interpolated (hard constraint 1). The reversal engine's gap handling is the
  reference implementation.
- **Ektar 100's printed spectral curves stop at 684.9 nm; the 685-700 nm red
  tail is not flat-held.** True support is in each
  `digitization_audit.endpoints` block. The band carries 1.7% of Status M red:
  flat-hold against zero-fill moves Ektar's red Status M aggregate by 0.042 D,
  comparable to the smallest inter-stock distance in the fleet (0.021 D).
- **Spectral comparison tools restrict fits to each stock's measured
  support**; on a fixed 400-700 nm grid Ektar silently contributes
  13 fabricated flat-held points.
- **The Vision3 ADX16 route ships one shared-basis cube; the scene
  route ships four; the two are not conflated.** The per-stock dye JSONs are
  live inputs on the scene route and reference data only on the ADX16 route.
  In printing density, inter-stock disagreement is 0.008-0.018 D RMS, far
  below the 0.116 D that separates the corrected basis from the uncorrected
  one; per-stock printing-density cubes would bake tracing noise in as
  chemistry. The scene cubes are per stock because characteristic curves,
  spectral sensitivities and balance illuminant differ; each decodes to that
  stock's modelled exposure record. A per-stock printing-density cube earns
  its place by independent reference performance, never by a lower closure
  residual on the synthetic box.
- **Do not drop the 9-parameter warp or substitute an unwarped shared basis**
  without reproducing what the warp absorbs. The closure residual has the same
  structure across all four independently traced Vision3 stocks (correlations
  +0.78 to +0.99), peaking at 580 nm in the magenta-cyan valley at +0.164 D.
  The warp absorbs 60-69% of it (0.059-0.078 D down to 0.018-0.031 D). A
  simpler or better-supported model that reproduces it on independent output
  performance may replace the warp. A stock-specific prior supported by
  independent information is admissible; a bound chosen per stock for the
  residual it buys is not.
- **A dye-amount inversion residual that sits entirely on zero-clipped nodes
  is a constraint violation and no fit error.** The Status M inversion on the
  print path is exact wherever it does not clip. 22–26% of the lattice (34% on
  Fujifilm 200 and 400) asks for a negative image-dye amount, where no
  refitting will improve it.
- **The gamut projection is confined to the reversal path.** Applying
  `project_to_reachable()` in `c41_statusm_engine.py` or the family-basis
  Vision3 negative build was tested and rejected on measurement. Their
  unreachable fractions are small scattered pockets (4.4% on Fujicolor 100,
  4.7% on the Vision3 build, 10.8% on Portra 400, against 41.6% on Provia
  100F), and projecting a pocket one node deep doubles the step to its far
  side. Largest step involving an unreachable node:

  | build | before | after |
  |---|---|---|
  | Fujicolor 100 | 0.2019 D | 0.4019 D |
  | Vision3 build | 0.3719 D | 0.5461 D |
  | Fujifilm 400 | 0.9713 D | 0.4174 D |
  | Portra 400 | 0.4031 D | 0.3384 D |

  A successor is scored on the same figures and on off-lattice reachable
  samples whose interpolation uses an altered corner (invariant 12).
- **A published characteristic curve is an integral density of a neutral
  series and is never read as one layer's dye.** The Vision3 scene engine and
  both print engines convert their three curves into per-layer amount tables
  by the full three-channel solve and look each layer up on its own table. A
  single-channel reading attributes the other layers' unwanted absorption to
  that layer: 0.09–0.44 logH apart on a Vision3 neutral that satisfies the
  sheet, and up to 15 ΔE2000 at saturated colours on Endura, while it agrees
  exactly on the neutral (`knowledge/reading-datasheet-charts.md`).
- **The scan-side responsivity of a masked negative is the LED behind the
  mask.** The roll anchor subtracts D-min in integrated density, so the C-41
  engines integrate `LED × sensor × 10^−Dmin(λ)`. The bare LED misreads a
  midscale neutral by 0.06 D in green (register #17).
- **A gamut projection never touches a node the solve reached.**
  `reversal_transform.project_to_reachable()` substitutes only where the
  residual exceeds `REACH_TOLERANCE_D`. Every reached node stays bit-identical
  to the unprojected build.

## Known limitations

The most consequential caveat is the
[C-41 fleet discrimination gap](#c-41-fleet-discrimination-gap-the-most-important-caveat-in-this-document).

**No measured validation.** Every metric the C-41 fleet reports derives from
datasheets and is verified only against itself. A validation roll needs at
least two stocks, **Portra 400 and Ektar 100**, on one development, each
carrying:

1. a neutral gray-card exposure ramp (±3 stops) and a ColorChecker frame;
2. **R/G/B colour-separation step wedges**. Interimage is *defined* as the
   gamma difference between a separation exposure and a neutral one
   (US4830954A; `knowledge/interimage-effects-and-stock-differentiation.md`):
   `IIE% = 100·(γ_separation − γ_neutral)/γ_neutral` per channel gives the six
   off-diagonal terms. Published magnitudes run ~10–35% (magenta largest,
   yellow smallest), far above the ~5% characteristic-curve contrast difference
   that currently separates the stocks. A grey ramp and a ColorChecker carry no
   interimage signal;
3. an unexposed-developed **D-min patch**;
4. the **process record**: one processing run for every stock, with its
   control-strip reading against the manufacturer's reference values, the
   measurement geometry and a repeatability figure. A difference between two
   stocks developed in separate runs is evidence of nothing
   (`knowledge/process-chemistry-c41-ecn2-e6.md` §4).

The patches are read **spectrally, 380–730 nm, at ≥3 exposure levels** across
the printable window. That pass also closes the orange-mask off-axis
mis-attribution and the per-layer dye separation of register #8, which no
modelling can close. Instrument geometry and illuminant belong in the audit
block. An interimage stage in the C-41 chain does not remedy the gap.

**The C-41 fleet cannot distinguish every stock by its modelled dye set.**
Basis sensitivity is 0.027–0.049 D against inter-stock distances of
0.021–0.219 D: 16 of the 66 pairs sit inside the band. The mask strength spans
0.346 D, basis-independent, and reaches the print cubes at 13–20% of nodes
above 1 ΔE2000 and up to 5.5 on saturated colours, leaving neutrals within
0.131. What separates the print cubes is the orange mask alone, away from the
grey axis.

**The Vision3 scene tables are a per-stock model estimate, verified only
against their own machinery, unvalidated off the neutral series, and imprecise
in deep shadows and extreme highlights.**

- The ColorChecker residual, 2.18–2.64 dE2000 mean with maxima 4.73–5.90, is a
  training-set figure: skin withheld from the fit scores 2.54–3.33 against
  1.51–2.02 in it. The neutral ramp is exact by construction. The full-chain
  ColorChecker figure collapses to the matrix residual.
- What the machinery holds to is the sheet: the amount tables reproduce all
  three characteristic curves, and the mask's Status M agrees with the D-min
  triplet to within 0.045 D. None of that reaches the off-neutral inverse. A
  diagnostic coupling of ±0.05 decodes the same neutral within 4 × 10⁻⁴ D and
  the training reflectances 1.6 ΔE2000 mean and 4.9–5.2 maximum apart, single
  layers up to 0.42–0.73 stops apart. Only separation exposures on a measured
  roll can choose the rule. The exposure-invariant additive sensitivity kernel
  is a further assumption of the same kind.
- Lattice error against the exact chain, tetrahedral: 1.6–1.9% mean within the
  published span; 1.5–1.7% in the 80–84% of clean cells; up to 22–48% in cells
  straddling the top of a layer's curve; up to 22–97% four stops under nominal
  in the ColorChecker sweep, where a doubling of exposure fails to double the
  output by up to 17–39%. ±0.01 D on one scanner channel moves a layer's
  decoded exposure by up to 0.25 stops four stops under. The cube carries no
  per-pixel mark of the declared operating region.
- The ADX validator finds the delivered scene cube within 0.2–0.3 ΔE2000 mean
  and 1.3 maximum of the exact engine on the reflectance sets.
- Mid-grey rests on the traced midscale neutral, which decodes 1.4–11.3
  ΔE2000 off the series' neutral at matched luminance (largest on 250D). On
  500T the trace ends at 640 nm. The camera-stops zero differs from the anchor
  by 0.067–0.404 logH.
- The output is an adapted, scene-referred estimate under the stock's nominal
  balance illuminant, fitted on reflective surfaces. It recovers neither an
  illuminant-independent reflectance nor unadapted scene radiance. No frame
  has been checked against a known scene.

**The sheet's two charts disagree about what a neutral negative reads, and the
chain can follow only one.** Portra 400's mid-grey in R/G/B:

- the characteristic-curve series, through the spectral base: 0.10/0.06 D
  below and 0.16 D above equal channels;
- the midscale-neutral spectrum under the same Status M: 0.13 D below and
  0.12 D above, a different green.

| stock | spectrum under the shipped curve-series balance, a\*/b\* | spectrum under an equal-channel balance, b\* |
|---|---|---|
| Portra 400 | −20/+14 | −31 |
| Ektar 100 | −9/−16 | −48 |
| Fujifilm 400 | −20/−23 | −21 |
| Pro 400H | −7/−15 | −14 |

- The series ships, being a series; the spectrum is one exposure of unstated
  placement. The error budget carries the distance as the "neutral reference"
  bracket: the same negatives balanced on the spectrum render 4.9 mean / 15.2
  max ΔE2000 apart on Portra 400 and 9.3 / 26.6 on Fujifilm 400. The series'
  curvature about the lock's constant offset adds a further 4 to 5 units of
  a\*/b\* over the printable band.
- **Fujifilm 200 and 400 also disagree at D-min.** The shared spectral chart's
  Minimum Density reads Status M 0.102/0.591/0.977 in R/G/B; the
  characteristic curves bottom out at 0.163/0.403/0.886 on Fujifilm 400 and
  0.133/0.373/0.823 on Fujifilm 200. Green differs by 0.19 and 0.22 D. On the
  other ten stocks the comparison stays within 0.12 D on every channel.
- **Scanned roll bases favour the spectral chart in green.** A roll's base
  density under the three LEDs exceeds its sheet's Minimum Density prediction
  on every roll measured: by 0.09 to 0.24 D in green on seven rolls of five
  other stocks (Portra 160, 400 and 800, Ektar 100, Fujicolor 100), and by 0.15
  to 0.16 D on three Fujifilm 200 and 400 rolls against the spectral chart.
  Lowering the green prediction by the characteristic curves' 0.19 and 0.22 D
  raises their excess to 0.34 to 0.38 D, above every other roll. The dye fit
  stays on the spectral chart. The cause of the common excess is undetermined.

**That a frame's rendered cast matches its physical illuminant is unverified
on film.** Hard constraint 5 guarantees only that no stage neutralises the
cast. A test costs one frame: a grey card under a known illuminant, the print's
cast compared against the prediction from the stock's published spectral
sensitivity.

**Every published curve is a manufacturer prior.** Kodak states that the
Vision3 curves represent production coatings under the stated exposure and
processing, and do not apply directly to a particular roll. The per-roll anchor
and a declared reference frame are the only roll-specific inputs.

**Print Adjustment's Locus Stock is validated on each sheet's neutral series
only.** Its extension to coloured pixels is an aesthetic choice. Printing up an
underexposed frame is limited by the toe.

**Density Crosstalk is checked in the engine's own model only.** A study
injects faults into the sheet's own dye amounts, with no interimage.

- A slope about mid-grey corrects a contrast change that crosses at mid-grey.
  A crossing elsewhere or an added speed change needs `Gain R/G/B` as well. No
  slope corrects a change of curve shape in the toe or shoulder, a cross-layer
  change or a change of dye hue.
- Off-diagonal sliders (experimental), matrix fitted on a 24-patch chart with
  known target densities:

  | cross-layer fault | mean ΔE2000 |
  |---|---|
  | uncorrected | 1.07–3.58 |
  | per-layer slopes and Gain R/G/B | 0.74–2.43 |
  | matrix fit, linear fault | 0.01–0.12 |
  | matrix fit, fault growing with density | 0.26–0.37 (maximum 1.43) |
  | affine least-squares benchmark on the evaluation colours | 0.24–0.32 (maximum 1.98) |
  | exported to the 0.001-step sliders, compiled chain, three linear faults | 0.01–0.11 |
  | the same, density-dependent fault | 0.32–0.45 |

- The linear case is close to exact by construction (fault and correction
  share the dye basis). Figures are similar under a per-shot master of Gamma
  0.8, Gain −0.05 with Locus Stock. With Hold Neutral on, the 2E fault needs a
  slider outside its range on all twelve stocks (magenta slope 1.231 and 1.215
  on Portra 400 and Fujifilm 400).
- The manual procedure is unvalidated: freezing the slopes at their grey fit
  left about 1 ΔE2000 mean on Portra 400 and Fujifilm 400. A neutral scale
  fixes three of the nine numbers, so the off-diagonal sliders are set by eye
  or against a known-good reference roll. No processed roll with a known fault
  has tested the node.

**Printer Lights ADX16's Locus Stock is checked against the scene engine's
model only.** No measured Vision3 exposure bracket exists. Printing up keeps
the larger residuals: mean up to 1.71, maximum up to 6.49 ΔE2000 at two stops
under. Its grey trims come from the same model.

**The Print Adjustment trims actually applied are not logged, per roll or per
stock.** Only 0.005–0.020 k of per-channel trim is ever required, 0.2–0.8 stop
of printer light. A cube that integrated the bare LEDs read a midscale Portra
400 neutral 0.064 D low in green, 0.019 k, the size of the trims observed; the
mask-filtered illuminant of register #17 removes it. What the remainder
correlates with is unrecorded: variation by roll within a stock indicates
anchor noise or development; consistency within a stock with a difference
between stocks indicates dye-model error; correlation with neither indicates
the scene illuminant. A small trim is weak evidence: the grey-axis lock has
corrected as much as 1.23 log-E, four stops, while neutrals still measured
clean.

**Half of every reversal lattice lies outside the dye gamut and holds a
projected value.** 49.7% to 58.7% of nodes, by stock, on the shipped monochrome
builds; 26.5% to 32.2% on the a7R III build. The monochrome figure is high
enough that the projection reaches material a real transparency contains,
which is why those cubes lose accuracy beyond a dye density of about 2.5. The
region beyond the gamut is a clamp that carries no information. Reached nodes
that close only with a negative dye amount:

| stock | nodes | share of reached |
|---|---|---|
| Velvia 100 | 13,096 | 10.0% |
| Velvia 50 | 23,073 | 17.4% |
| Provia 100F | 23,830 | 21.0% |
| Ektachrome E100 | 19,819 | 14.4% |

A few dozen sit at the solver's −0.5 floor. Every build prints the count. The
nodes are left untouched, the mapping through them being continuous. A
constrained inverse is an untested alternative.

**The reversal family has no empirical validation either.** Its one check
against a sheet quantity (register #19) reports a blue-green bias of up to 7.5
units of b\* that the model cannot attribute. It is the cheapest gap to close:
transmissive IT8 targets are made on E-6 stock and ship with per-batch
reference colorimetry of every patch, in the reversal cubes' own output space.
One scan of a target on one of this fleet's stocks would grade that stock's
whole chain, anchoring included.

**The a7R III PDAF rows are unexamined.** The decoder runs on real Canon CR3
and CR2, Nikon NEF and Pentax DNG files, a real a7R III ARQ and real ARW
captures. Whether the phase-detection rows bias a measured patch is untested.

**Interimage and masking effects are unmodelled.** For transforms that end in a
density this is a predictive limitation: a scanned film carries its interimage
in the measured densities, while the developed spectra stay within the span of
the fixed dye curves. A spectrum outside that span reads differently through
scanner and target, and that error is unmeasured. On the Vision3 scene route
the identity and the fixed curves are both modelling assumptions. The gap is
about 0.1 D in cross-band couplings, amplified roughly twofold through
inversion in the negative case. `DIR_MATRIX` in `engine/common/interimage.py`
sits at identity; a constant matrix in amount space carries neither an
exposure-dependent interimage nor a change of spectral shape.

Synthetic scenarios (an invented exposure-dependent mask term, D-min held, the
neutral Status M records re-solved) illustrate what the fixed-curve assumption
can cost, at the larger tested amplitude:

| quantity | figure |
|---|---|
| Vision3 bare-image Status M, 99th-percentile miss on scan-valid patches | about 0.013 D |
| Vision3 integrated-base-subtracted APD, the same | 0.024 D |
| pooled 99th-percentile exposure error, reflectance patches | 0.433 stops |
| C-41 print miss | 0.99 ΔE2000 on Endura, 4.53 on Pro Laser |

Six stocks run on both print configurations give larger maxima on Pro Laser,
which implicates the combined print configuration. The scenarios stay inside
the model, establish no physical bound and rank no route.

**There is no LAD calibration on the negative path.** The chain is anchored
only on D-min, so the absolute level of mid-grey is unconstrained. The anchor
records D-max when a frame is named, diagnostic-only; whether it can serve as a
second constraint is untested.

**The print path's mid-grey is a fixed density, and its exposure differs by
stock.** K_MID = 0.22 lies 2.74–4.12 stops above each sheet's speed point, a
spread of 1.38 stops (speed point estimated from the green and slowest records
at 0.15 D above the trace minimum, combined as ISO 5800 does). A grey exposed
at H = 8/S lux-seconds renders through the shipped default at (print white at
1; mid-grey intent Y = 0.18):

| stocks | Y at H = 8/S | Y at H = 10/S |
|---|---|---|
| nine stocks | 0.051–0.131 | 0.089–0.217 |
| Pro Image 100 | 0.385 | 0.526 |
| Fujicolor 100 | 0.324 | 0.469 |
| Pro 400H | 0.014 | 0.018 |

A frame exposed at box speed prints at a brightness particular to its stock
until Print Adjustment's gain places it. No axis audit explains the three
outliers, and no axis is adjusted to a box speed.

**HDR delivery in P3-PQ has not been exercised on a real master.** For reversal
the proposed default is film-base white, post-anchor density 0.0, at 203 nits
per ITU-R BT.2408, with about 300–400 nits available as a mastering choice. It
is one scalar in the grade, never baked into a cube.

**Print colorimetry integrates the dyes' measured band only.** The sheets' dye
spectra stop at 400 and 700 nm and the viewing integral runs from 380 to
730 nm; the render normalises to the measured band's white. With zero dye
density in the unmeasured bands, on Portra 400 / Endura Premier the black sits
at 2.24 D at du′v′ 0.039 against 2.27 D at 0.005. Each scenario re-solves the
grey lock: a sensitivity envelope.

**Pro 400H's fourth sensitivity layer is not modelled.** Its chart shows a
dashed "Cyan Sensitive Layer" between green and red. Every digitiser assumes
three layers. The registry marks the stock `sensitivity_absent: True`; no
deliverable is blocked.

**Builds emit no per-build manifest** of engine commit and data hashes.

## End-to-end error budget

A read-only error-budget instrument (not distributed) propagates every known
error term into ΔE2000 on the print output. It perturbs inputs and writes
nothing.

- The patch groups are never merged. The lock forces the neutral axis, so
  print-side terms read near zero on neutrals; a scan-side dye-set error moves
  the neutral axis before the lock sees it.
- The off-neutral sampler selects on the render. Patches the engine's own
  Status M inverse cannot reproduce to 0.001 D (75 of 379 on Portra 400,
  missing by up to 0.417 D) are their own group. The reachable off-neutral
  column is the budget.

Portra 400 on Endura Premier, shipped monochrome configuration, off-neutral,
mean and maximum ΔE2000 over the 304 reachable patches of a 9-per-axis lattice
over k = 0.05–0.60, kept where the render lies inside Display P3 with C\*ab ≥ 5
and thinned to at most 400 (379 kept):

| term | mean | max |
|---|---|---|
| basis sensitivity, the canonical reference plus five alternative surrogate bases, propagated through the scan inverse and the print: the largest mean and maximum over each alternative's accepted patches | **2.02** | **5.24** |
| the same at fixed Status M, print engine only (comparison only) | 0.83 | 2.70 |
| dye fit residual, ±0.0107 D per curve, a flat-offset scenario propagated through the scan inverse and the print | 0.31 | 1.02 |
| the same at fixed Status M, print engine only (comparison only) | 0.09 | 0.42 |
| missing-band policy of the paper exposure, edge held against truncated (register #13) | 0.26 | 0.94 |
| both shipped cubes composed, Status M then print, tetrahedral, per patch | 0.07 | 0.21 |
| the print cube alone, tetrahedral (comparison, inside the row above) | 0.07 | 0.21 |
| paper H&D digitisation, ±0.00035 D per layer (chart y-axis fit residual) | 0.02 | 0.06 |
| paper dye digitisation, ±0.00021 D per layer (chart y-axis fit residual) | 0.01 | 0.04 |
| paper dye wavelength axis, ±0.030 nm per layer (chart x-axis fit residual) | 0.01 | 0.03 |
| fabricated spectral edges | 0.00 | 0.00 |
| paper sensitivity digitisation, ±0.00035 log10 sensitivity per layer | 0.00 | 0.01 |
| **combined, root-sum-square** (under independence; no bound) | 2.06 | 5.43 |
| combined, plain sum (aligned perturbations) | 2.70 | 7.56 |

Fujifilm 400 on Fuji Pro Laser, 253 reachable patches, conditional on the
shipped laser kernel and its calibrated line powers:

| term | mean | max |
|---|---|---|
| basis | 3.65 | 16.50 |
| fit residual through the scan (0.31 / 1.19 at fixed Status M) | 0.60 | 1.83 |
| missing-band policy (every line inside the measured band) | 0 | 0 |
| composed cubes | 0.06 | 0.19 |
| paper dye wavelength axis | 0.19 | 1.12 |
| combined, root-sum-square | 3.71 | 16.64 |
| combined, plain sum | 4.62 | 20.01 |

**The basis row, by the provenance of each alternative** (mean / max ΔE2000
off-neutral at a fixed scan; the common column uses the patches every basis
accepts, 255 of 304 on Portra 400 and 198 of 253 on Fujifilm 400). The classes
rank no basis as more correct.

| class | bases | Portra 400, accepted | Portra 400, common | Fujifilm 400, accepted | Fujifilm 400, common |
|---|---|---|---|---|---|
| masked-negative-derived | the canonical reference | 0 | 0 | 0 | 0 |
| reversal-derived | E100, Provia 100F, Velvia 50, Velvia 100 | 0.89 / 3.31 | 0.91 / 3.12 | 3.65 / 16.50 | 3.23 / 14.12 |
| parametric | one basis derived from no film | 2.02 / 5.24 | 2.06 / 5.24 | 2.59 / 9.36 | 2.52 / 7.81 |

Each class entry is the largest member-specific mean and maximum. The
parametric basis sets the row on the seven Endura stocks, a reversal-derived
basis on the five Pro Laser stocks. Accepted means a scan inverse within
0.001 D and no negative dye amount:

| basis | Portra 400, kept of 304 | Fujifilm 400, kept of 253 |
|---|---|---|
| E100 | 295 | 243 |
| Provia 100F | 261 | 198 |
| Velvia 50 | 284 | 229 |
| Velvia 100 | 304 | 253 |
| parametric | 303 | 249 |

Nearly every rejected patch has a good residual and a negative amount. Through
the print inverse, which clips amounts at zero, the rejected patches reach 7.39
on Portra 400 and 29.23 on Fujifilm 400. Rendered directly past the clip with
every patch included, the maximum stays at the row's value on all twelve stocks
and the mean moves by at most 0.24, on Pro 400H.

**Sensitivities beside the table, with no measured bound to enter with.**

| scenario | mean | max |
|---|---|---|
| camera spectral sensitivity: register #9's 1% response change per 10 nm, both directions, through the monochrome Status M conversion | 0.19 | 0.86 |
| tricolor lamp, 3200 K ± 100 K, band weights re-balanced | 0.02 | 0.13 |
| Pro Laser red line moved to 650 and 688 nm, Fujifilm 400 | 1.56 | 4.04 |
| a Bayer capture, register #9's worst case at every patch | up to 17.2 (a ceiling) | |
| neutral reference bracket, midscale spectrum against curve series, Portra 400 | 3.69 | 12.93 |
| the same, Fujifilm 400 | 10.21 | 29.46 |
| the same balanced coordinates under both references (diagnostic) | 0.08 | 0.28 |
| print-viewing support, edge density held outward, Portra 400 | 0.04 | 0.19 |
| the same, Fujifilm 400 | 0.04 | 0.38 |
| print-viewing support, zero density in 380–400 and 700–730 nm, Portra 400 | 0.29 | 2.54 |
| the same, Fujifilm 400 | 0.27 | 5.88 |

The neutral-reference bracket is the largest figure on the page: the sheet's
own disagreement about which negative is grey (Known limitations). A grey card
on a measured roll closes it. The Pro Laser scenario covers neither the
Frontier generation, the blue and green wavelengths, the linewidth nor the
exposure path. The balanced encoding's floor loss is printed beside the table
too.

Four conclusions follow, the first the one to quote.

1. **The figure these documents lead with is among the smallest terms that
   matter.** The dye fit residual contributes 0.31 ΔE2000 where basis
   sensitivity contributes 2.02, a factor of 6.5. The per-stock RMSE is not
   the stock's accuracy. The residual is applied as a wavelength-flat offset;
   the basis ensemble is what probes shape.
2. **The budget is one term, and it is consumed twice.** The dye set enters at
   the Status M cube and at the print engine. Swapping only the print engine's
   basis at fixed Status M gives 0.83 mean; letting the alternative basis also
   perform the scan conversion gives 2.02, the cost of the surrogate basis.
   The fit residual likewise: 0.31 through the scan against 0.09. Everything
   else is at or below 0.31 in the mean. The budget carries no structural
   term. Four model-structure errors larger than every term but the basis were
   found by testing assumptions, and all four are closed in the engines: the
   bare-LED scan side of register #17; the per-channel reading of the paper
   curves; the per-channel reading of the Vision3 curves; an equal-channel
   neutral as the lock's target.
3. **One term is exactly zero for the shipped configuration, by construction,
   and that zero is no bound.** The fabricated spectral edges never reach the
   render, because `neg_support_mode` truncates that band; the support policy
   is carried as the missing-band term instead. A per-layer offset on the
   paper's log sensitivity is absorbed by the re-solved lock and re-weighted by
   the tricolor balancing: 0.00 mean / 0.01 max at the probed ±0.00035 log10.
   The dye chart's wavelength error is vector-precise on Endura Premier
   (±0.030 nm, the 0.01 in the table) and an order larger on Fuji Pro Laser
   (±0.483 nm), where it contributes 0.19 mean / 0.94 max, a shape change the
   lock cannot absorb. Every perturbed term is worst-cased over all eight
   per-layer sign patterns. A scalar density of 0.0005 D applied to every
   patch gave 0.05 / 0.19, printed for comparison.
4. **The combined rows are a sensitivity inventory and no uncertainty
   interval.** Each term is the worst of a set of perturbations at a stated
   bound, with no distribution and no known covariance. The root-sum-square
   holds only for independent terms, and the fit residual and the basis
   sensitivity act on the same three curves. The plain sum is a ceiling for
   aligned perturbations; ΔE2000 is not additive. No combined figure is the
   accuracy of a print.
