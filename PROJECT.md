# Film scanner spectral calibration pipeline

A spectral calibration pipeline for a camera-based film scanner with
narrowband sequential red, green and blue LEDs at 640, 544 and 450 nm.
Narrowband illumination is the only supported mode. The pipeline converts raw
scanner-space density into standardised, externally defined density metrics,
so that grading in DaVinci Resolve begins from a metrically defensible
quantity rather than from the combined idiosyncrasies of the scanner and its
illuminant. The shipped tables assume no camera: they are built for a
monochrome sensor of constant spectral response, which cancels out of a
density measurement, whereas a response that varies across an LED's band
does not and is carried as a labelled scenario (register #9); a Bayer body
is named at build time.

Three film families are covered, each with the target metric its process
implies:

- **Reversal / E-6** (Fujichrome Velvia 100/50, Provia 100F; Kodak Ektachrome
  E100/100D) → D50 white-relative colorimetric density (CIE 1931 2° XYZ). No
  printing step exists in this process, so the target is the transparency as
  an object viewed on a D50 light table.
- **Negative / ECN-2** (Kodak Vision3 50D/200T/250D/500T) → ADX16 (ST 2065-3)
  over Academy Printing Density (ST 2065-2), the quantity a motion picture
  printer sees through the negative, from one stock-blind table into an ACES
  timeline. Once the per-channel printer-light trims are dialled on a known
  neutral, the ACES rendering delivers a faithful, pleasing image with no
  further grading; Resolve's built-in "LMT Kodak 2383 Print Film Emulation"
  may optionally follow. A secondary, scene-referred route lands each stock on
  scene-linear DaVinci Wide Gamut (D65) by inverting the stock's own
  characteristic curves; it is the accuracy reference the ADX16 route is
  measured against (ColorChecker ΔE2000 6–7 mean after the printer-light
  trims) and the path for
  graded work.
- **Negative / C-41** (twelve still stocks, Kodak and Fujifilm) → Status M
  density, followed by RA-4 **print emulation** to Display P3 or P3-PQ. A
  colour negative is designed to be printed, so print emulation is the sole
  delivery route. A "stock" in this document denotes a dye set together with
  a D-min spectrum, the unreacted coloured coupler of the Glossary, and never
  a tone curve.

Status A appears in two places: the inversion of RA-4 paper reflection-density
curves on the C-41 print path, and the reversal builds' closure against their
sheets' characteristic curves (register #19). No cube lands on it; the
reversal target is D50 XYZ.

A collaborator's calibration tool, DiVERE, and their capture setup inform the
apparatus parameters; this pipeline is independently constructed.

## Contents

- [Current status](#current-status) – what is built, and the two facts that qualify every number
- [Glossary](#glossary) – terms used throughout, including the orange mask
- [Repository layout](#repository-layout) – every directory and what belongs in it
- [Hard constraints (do not relax these)](#hard-constraints-do-not-relax-these)
- [Source data (`data/`)](#source-data-data) – every input, with its provenance
- [How a transform works](#how-a-transform-works) – the spectral round trip, the corridor convention and the node chains
- [Per-roll anchoring](#per-roll-anchoring) – the two density scales, and which one Resolve needs
- [Engines and script reference](#engines-and-script-reference) – each engine, what it reads, what it prints
  - [C-41 fleet discrimination gap](#c-41-fleet-discrimination-gap-the-most-important-caveat-in-this-document) – the document's most important caveat
- [Current state by stock](#current-state-by-stock) – residuals, build state and deliverables
- [Bounded systematics register (everything currently known and unpatched)](#bounded-systematics-register-everything-currently-known-and-unpatched)
- [The role of NamiColor in this project](#the-role-of-namicolor-in-this-project)
- [Invariants](#invariants) – properties that must survive any future change
- [Known limitations](#known-limitations) – what is unverified, unmodelled or unmeasured
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
   against a measurement.** The cubes are in regular use on real scans and
   pass qualitative examination. The single external check agrees with the
   model: the user reports Portra 160 and Portra 400 printing extremely close
   in a real darkroom, and the model reproduces that result. The check has
   little power to discriminate, because both stocks are fitted against the
   same surrogate basis (their `fit_audit.basis` entries are identical); it
   tests the mask and the characteristic curves, which differ between the two,
   and not the dye model, which is the part in doubt. One check in the ECN-2
   chain reaches a quantity measured outside this repository: the Vision3
   dye model reproduces the Academy's published Status M to APD matrices for
   5207 and 5219 (`annexc_check.py`), the worst per-channel mean absolute
   error over the traced neutral series, the document's own statistic, being
   0.018 D on each stock's own dye set against its 0.02 D expected error, with
   per-point maxima to 0.035 D and the family basis the ADX16 cube reads
   through at 0.024 D. It
   tests the dye spectra, the mask and the density tables, and no part of the
   scan side. Quantitative validation
   is a grey-ramp exposure series, a ColorChecker frame and spectrally read
   separation wedges, each compared against reference values. Until that roll
   is exposed and measured, every figure here is a model reporting on itself
   (Known limitations).
2. **The fleet cannot distinguish every stock from every other.** Basis
   sensitivity is 0.034–0.063 D while inter-stock distances run 0.021–0.220 D,
   so 20 of the 66 pairs sit inside the ambiguity band and cannot be told apart
   by their modelled dye sets; the remaining 46 are separated by more than the
   basis prior can account for. Datasheet-level comparisons are
   basis-independent and hold; per-stock *rendering* differences largely do
   not. See "C-41 fleet discrimination gap".

### Evidence classes

The `knowledge/` notes rate every outside source A, B or C and record when it
was collected. This document applies the same discipline to its own claims, in
four classes.

| class | meaning |
|---|---|
| **measured** | read from a manufacturer's published chart, or computed by running an engine in this repository over that data |
| **derived** | a model output, correct only to the extent its inputs and its model are |
| **assumed** | a choice made without a measurement behind it, which could have been made otherwise |
| **unverified** | asserted, and never checked against anything |

| quantity | class |
|---|---|
| the digitised characteristic curves, spectral dye densities and D-min spectra | measured, with the tracing bounded by register #13 |
| the LED spectral power distributions in `data/equipment/` | measured, on this apparatus |
| the mask-filtered scan illuminant `LED × 10^−Dmin(λ)` every negative cube inverts | derived, from the traced D-min spectrum; register #17 |
| the four Vision3 Minimum Density curves | measured, the dashed curve of each sheet traced, and cross-checked against the characteristic sheet's D-min triplet to within 0.045 D |
| the samples of each fitted C-41 dye set that rest on the basis's held blue edge | **assumed**; recorded per stock as `fit_audit.basis_held`, register #18 |
| the three-dye decomposition and every per-layer curve | derived, and see register #8 |
| the Status M, print and reversal cubes | derived |
| the aggregate fit residual, node-solve residual and serialisation figures | measured, by running the engines |
| the Vision3 dye model's Status M to APD relation for 5207 and 5219 | measured against the Academy's published S-2008-002 Annex C matrices: worst per-channel mean absolute error 0.018 D on the stock's own basis against their 0.02 D expected error, the document's own statistic and the gate; signed mean (bias) and per-point maxima printed beside it ungated, 0.018 D and 0.035 D; family basis 0.024 D mean absolute with per-point maxima to 0.037 D; a FAIL exits nonzero; the scan side is untouched by it |
| the end-to-end error budget | derived, from measured perturbations |
| the surrogate Vision3 basis standing in for C-41 couplers | **assumed** |
| the uniform ±25 nm shift bound and the 0.85–1.15 width bound | **assumed** |
| `DMAX = 3.30`, the negative corridor | **assumed**, with the requirement measured |
| `DIR_MATRIX = identity`, interimage disabled | **assumed** |
| that integrated density is linear in the dye amounts, every dye's unit spectrum fixed at all concentrations | **assumed**, by every `density()` forward; the one datum that could bear on it, the 0.06–0.08 D Vision3 midscale closure residual, is consistent with a small violation and is undiagnosed |
| the 3200 K blackbody enlarger SPD in the print render | **assumed** (nominal) |
| the gray-axis lock's mid-gray intent, luminance Y = 0.18 at input k = 0.22 | **assumed** |
| D65 viewing for the print render, D50 for the reversal target | **assumed**; D65 against D50+CAT02 measured at ΔE00 median 0.75, 0.017 on the neutral axis |
| that the scene illuminant survives the chain | **unverified** on film |
| that any part of the C-41 chain matches a physical reference | **unverified**, and this is the open gate |

Per-datum provenance lives in the data itself. All seventeen
`*_datasheet_curves.json` and all eleven `*_spectral_sensitivity.json` carry a
`digitization_audit` block naming the source sheet, the device-to-data
transform and the measured support: the measured class. The twelve C-41
`*_dye_density.json` carry a `fit_audit` block recording the basis, the
bounds, which parameters rest on one, and the multistart that found the
solution: the derived class. The reversal and Vision3 `*_dye_density.json`
carry neither, their per-layer curves being traced rather than fitted, which
is why the reversal path does not inherit register #8.

## Glossary

Terms are grouped by category, because the same letter denotes different
quantities in different contexts.

**Photographic image formation**

| | |
|---|---|
| **Emulsion layer** | one of the three light-sensitive coatings on colour film, sensitised to blue, green or red light respectively |
| **Latent image** | the invisible record left in an emulsion layer by exposure, before development makes it visible |
| **Coupler** | the compound that reacts with oxidised developer during processing to form image dye. The blue-, green- and red-sensitive layers form yellow, magenta and cyan dye respectively |
| **Development** | the processing step that reduces exposed silver halide and, through the coupler reaction, forms dye in proportion to exposure |
| **C-41** | the colour-negative process for still film (Portra, Ektar, Gold, Superia and others) |
| **ECN-2** | Eastman Colour Negative 2, the motion-picture negative process (Vision3) |
| **E-6** | the colour-reversal (slide, transparency) process (Velvia, Provia, Ektachrome). It develops twice: a black-and-white first developer forms a negative silver image, the remaining halide is fogged, and a colour developer forms dye where the first developer did not form silver, so the dye image is a POSITIVE. Reversal film carries NO orange mask, because a transparency is viewed directly and a coloured coupler would be visible; interimage is consequently its principal means of correcting unwanted dye absorption (register #11) |
| **RA-4** | the colour process for printing a negative onto photographic PAPER |
| **Orange mask** | a misleading name for a mechanism that involves neither a discrete layer nor a filter. Colour negative film builds its magenta- and cyan-forming chemistry from *coloured couplers*, yellow and pink respectively, which are consumed wherever image dye forms. The orange cast is the coupler that did NOT react, distributed through the emulsion layers. Its absorption completes the unwanted absorptions of the image dyes, so that dye plus surviving coupler sum to a nearly constant unwanted absorption at every exposure. It is a POSITIVE image, maximal at D-min and falling as exposure rises, and it constitutes half of a correction, so removing it and correcting the film are different operations. Sourcing in `knowledge/orange-mask-and-the-scanning-workflow.md` (Hanson, JOSA 40(3):166, 1950) |
| **DIR coupler** | Development-Inhibitor-Releasing coupler, the chemistry underlying interimage effects |
| **Interimage / IIE** | the inhibition of one layer's development by a neighbouring layer, which sharpens colour separation. `IIE%` denotes the gamma difference between a colour-separation exposure and a neutral one |

**Density and sensitometry**

| | |
|---|---|
| **OD** | optical density, −log₁₀(transmittance or reflectance). A density of 1.0 transmits one tenth of the incident light |
| **D-min / D-max** | the least and greatest density a film or paper attains. On a negative, D-min is the unexposed base together with the orange mask |
| **H&D curve** | Hurter–Driffield characteristic curve: density plotted against log exposure. Its slope is gamma |
| **logH / logE** | log exposure, the abscissa of the H&D curve. H and E are used interchangeably in the source literature |
| **Status M** | the ISO 5-3 densitometric standard for measuring colour NEGATIVES. C-41 datasheets publish in it, which is why it serves as the negative-side target here |
| **Status A** | the ISO 5-3 standard for reversal material and PRINTS. Used here in two places, the inversion of RA-4 paper curves and the reversal builds' characteristic-curve closure (register #19); no cube lands on it |
| **APD / RP 180** | printing density, what a motion picture printer sees through the negative. Academy Printing Density (ST 2065-2) is the live standard and the target metric of the ECN-2 ADX16 route; SMPTE RP 180-1999, its predecessor, was ARCHIVED by SMPTE in December 2006 but publishes an explicit responsivity table, retained here for the APD-versus-RP 180 comparison the ADX16 build prints. "Cineon printing density" properly denotes a third metric defined by discontinued stocks (5384 print, 5248 base) whose spectral sensitivities were never fully specified |
| **LAD** | Laboratory Aim Density, a fixed reference density for placing mid-gray |
| **k** | normalised density, `k = OD / DMAX`, the domain in which the cubes and the Print Adjustment DCTL operate. Density runs *backwards* with respect to lightness: higher k means a denser negative and therefore a lighter print |
| **DMAX (corridor)** | the density range onto which a cube's 0–1 input domain is mapped: 3.30 for negatives on every sensor, and on the reversal path 5.00 sensor-free or 5.25 for this apparatus's a7R III build. Load-bearing: cube and shapers must agree on it |

**Colour science**

| | |
|---|---|
| **SPD** | spectral power distribution, a light source's power as a function of wavelength |
| **CMF** | colour matching function. CIE 1931 2° is the standard observer used here |
| **D50 / D55 / D65** | CIE daylight illuminants at approximately 5000, 5500 and 6500 K |
| **XYZ** | CIE tristimulus space, the device-independent colour reference |
| **ΔE2000 / ΔE00** | CIE perceptual colour-difference metric. A value near 1.0 corresponds roughly to one just-noticeable difference |
| **a\* / b\* / L\* / Cab\*** | CIELAB axes: red-green, yellow-blue, lightness and chroma. Cab\* ≈ 0 indicates a neutral colour |
| **CAT02 / Bradford** | chromatic-adaptation transforms, used to convert between illuminants |
| **JND** | just-noticeable difference |

**Delivery and the Resolve chain**

| | |
|---|---|
| **LUT / `.cube`** | three-dimensional lookup table, the pipeline's principal deliverable. 65³ denotes 65 nodes per axis |
| **DCTL** | DaVinci Colour Transform Language, in which the hand-written Resolve nodes are implemented |
| **Shaper (pre/post)** | the DCTL pair that maps linear scanner values into and out of a cube's normalised density corridor |
| **P3 / Display P3 / P3-D65** | the wide-gamut display colour space used for delivery |
| **PQ (ST 2084)** | the HDR transfer function. "PQ203" = paper white placed at 203 nits per ITU-R BT.2408 |
| **SDR / HDR** | standard / high dynamic range |
| **DWG** | DaVinci Wide Gamut, Resolve's working space, and the destination of the Vision3 scene route |
| **Scene-linear** | relative scene exposure, 10^(logH − logH_mid) per layer with the datasheet's midscale neutral at 0.18, delivered as DWG (D65). The Vision3 scene route's output, and the only transform destination here that is not a density |
| **ACES / APD / IDT / LMT** | the Academy colour system: Academy Printing Density, Input Device Transform, Look Modification Transform |
| **CST** | Resolve's Colour Space Transform node |

**Capture and scanning**

| | |
|---|---|
| **Narrowband / trichrome** | three sequential exposures under R/G/B LEDs at 640/544/450 nm, in place of a single white-light exposure. The only supported mode here |
| **CFA** | colour filter array, the Bayer mosaic on the sensor |
| **SSF** | spectral sensitivity function, the sensor's response as a function of wavelength in each of its three channels. It is what the engines integrate; the CFA is the physical arrangement that produces it. Held in `data/cameras/` |
| **PDAF** | phase-detect autofocus pixels, which read differently from image pixels and must be rejected |
| **ARW / ARQ / EXR** | Sony single-shot raw file / Sony pixel-shift composite / OpenEXR half-float linear image. The converter also reads Canon CR2 and CR3, Nikon NEF and NRW, Fujifilm RAF (Bayer GFX bodies; X-Trans is refused), and DNG |
| **Pixel shift** | a capture mode that displaces the sensor by one photosite between exposures so that every site records all three colours, removing the need to demosaic. Written by Sony as `.ARQ`; see `raw_to_exr.py` for what the other manufacturers do |
| **ROI** | region of interest, the measured patch within an anchor frame |
| **Roll anchor** | the per-roll D-min measurement that normalises a scan ahead of any cube |
| **Flat field** | correction for uneven illumination across the frame |
| **SNR** | signal-to-noise ratio |

**Analysis and fitting**

| | |
|---|---|
| **RMSE** | root-mean-square error |
| **FWHM** | full width at half maximum, a measure of a curve's width |
| **Gauss-Newton** | the iterative solver used to invert density to dye amounts |
| **Decoupling condition** | the condition number of the LED crosstalk matrix. A value near 1.0 indicates that the three channels are well separated |
| **Basis sensitivity** | the displacement of a fitted result when the assumed dye basis is changed. It is 0.034–0.063 D here, and it bounds every stock comparison |
| **Serialisation RMSE** | the error introduced by writing a cube's floating-point values at six decimal places |
| **MTF** | modulation transfer function, a sharpness chart present on the datasheets but not harvested here |

**Data sources**

| | |
|---|---|
| **IT8 / ColorChecker** | standard reflective colour targets |
| **Munsell / NIST skin** | measured reflectance sets used to fit and test matrices |
| **UEF** | University of Eastern Finland, publisher of the Munsell and Agfa spectral sets |
| **CGATS / ISO 5-3** | the standards bodies and document defining Status A/M responsivities |

## Repository layout

```
data/
  cameras/        camera spectral sensitivity functions, 44 bodies imported
                  from the ACES rawtoaces-data library, plus index.json and a
                  README recording provenance. Read only when `--sensor`
                  names a body; the default is none
  equipment/      measured LED SPDs
  films/          per-stock dye density, characteristic-curve and
                  spectral-sensitivity JSONs
  papers/         RA-4 print-paper datasheet JSONs (Endura Premier,
                  Fujicolor Pro Laser TYPE II, Crystal Archive Type CA)
  standards/      Status M, Status A, APD, RP 180 and CIE/D50 reference
                  data, and reflectance/ for the measured reflectance sets
engine/
  common/         shared numerics
    spectral.py                 density, resampling, integration primitives
    interimage.py               interimage-effect analysis helpers
    gamut.py                    projection of unreachable LUT nodes onto the
                                reachable gamut (reversal path only)
  scan/           capture side
    raw_to_exr.py               camera raw scans -> half-float linear EXRs
                                (PRIMARY converter, self-contained, parallel).
                                COLOUR sensors only; holds no monochrome path
    mono_to_exr.py              the same for a sensor with NO colour filter
                                array, native or stripped. A separate program
                                rather than a flag: a stripped array is not
                                distinguishable from an intact one in the
                                file, so the engine chosen IS the declaration.
                                Imports its merge, flat-field and scheduler
                                from raw_to_exr.py, so the two cannot drift
    decode_selftest.py          guards on the scan tools: how both converters
                                route and decode a raw file, that a triplet
                                of differing sizes is refused, and the anchor
                                tool's ROI, exposure-override and histogram-
                                source rules. Runs with no arguments and no
                                sample files, LibRaw's report stubbed; exits
                                non-zero on any failure
    roll_anchor_gui.py          self-contained per-roll Dmin/Dmax anchor
                                engine: ROI-picker GUI plus its own numeric
                                core, one independent engine
    aces_ssf_import.py          ACES camera SSFs -> data/cameras/
  c41/            still colour negative
    c41_statusm_engine.py       scanner density -> Status M cubes
    portra_decompose.py         aggregate dye curve -> three-dye decomposition
    portra_stocks.py            the twelve-stock registry
    c41_stock_compare.py        inter-stock distance and basis-sensitivity tool
    endura_print_engine.py      C-41 -> RA-4 Endura print emulation
                                (Display P3 / P3-PQ)
    fuji_print_engine.py        C-41 -> RA-4 Fuji Pro Laser TYPE II print
                                emulation, a thin preset over the same
                                PrintEmulationEngine
  ecn2/           motion-picture negative
    adx_engine.py               the primary ADX16 route into ACES
    adx_validate.py             scores the ADX16 route's Academy decode against
                                the scene engine's truth
    annexc_check.py             the dye model against the Academy's measured
                                Status M to APD matrices (S-2008-002 Annex C)
    v3_scene_engine.py          Vision3 scanner density -> scene-linear DWG,
                                per stock: the secondary, scene-referred path
    v3_basis_build.py           the family-average Vision3 dye basis, which
                                serves the stock-blind ADX16 route
  reversal/       slide film
    reversal_transform.py       parameterised engine, all reversal builds
  (the digitisation and QA tooling that produced data/ from the datasheet
  PDFs, the per-route error-budget instruments, and one standalone
  scene-referred engine are not distributed)
builds/           engine-generated cubes, plus anchors/ per-roll JSONs.
                  _ensemble/ and _forensics/ hold diagnostics and are
                  untracked; sensor-*/ holds per-camera builds, untracked
dctl/             hand-written DCTLs
  prep/           RollAnchor_ScanPrep.dctl
  shapers/        Preshaper 3.3 (negative), and the 5.0 and 5.25
                  reversal pairs (sensor-free and a7R III respectively)
  output/         10^-D linearisation, XYZ D50 to DWG, printer lights,
                  print adjustment
  dctl_shim.c     compiles a Transform DCTL as plain C to catch parse and
                  arithmetic faults before Resolve sees the file
film_datasheet/   manufacturer film datasheets. Publisher copyright, NOT
paper_datasheet/  redistributed, and gitignored. DATASHEETS.md carries the
                  publication code for each. Restore them to these paths in
                  order to re-run the digitisers
knowledge/        literature notes underlying the modelling decisions, each
                  tier-rated for source quality; README.md indexes them
literature/       third-party journal articles held for reference. Publisher
                  copyright, NOT redistributed, and gitignored in full
docs/             reader-facing documentation, split by the question it answers
  resolve.md      using the tables: capturing and measuring a roll, and the
                  node chain for each of the three processes
  method.md       how the transforms are derived and where their numbers come
                  from, including the film-chemistry background
  explainer.html  visual walkthrough, plotted from the repository's own files
  figures/        rendered figures, regenerated by scripts in engine/
  samples/        the frames shown in README.md
README.md         the front page: what the project provides, sample output,
                  a quick start, and the limitations
PROJECT.md        this document, the full technical reference
BUILDING.md       the build runbook: the command behind every cube
DATASHEETS.md     every source datasheet, with its publication code
LICENSE           MIT, covering engine/, dctl/ and the documentation
LICENSE-DATA      CC BY 4.0, covering the released cubes and data/, with a
                  scope exception for data/cameras/
```

### Repository hygiene (standing rules)

- **Run `git gc` periodically.** The auto-snapshot convention commits every
  few minutes and nothing packs the loose objects; 1505 have been observed.
- **Never run `filter-repo` on this repository.** Rewriting commit hashes
  would break the byte-identical-regeneration guard, which depends on history.
- **A stale linked worktree is a full second checkout**, `builds/` included,
  approximately 100 MB. Verify `git -C <wt> status --porcelain` is empty
  before removing one, and retain its `worktree-*` branch, which keeps the
  commits reachable.
- **Diagnostic artifacts are untracked.** `builds/_ensemble/`,
  `builds/_forensics/` and `data/films/_ensemble/` hold basis-sensitivity
  reruns and overlay renders. `.gitignore` does not untrack retroactively:
  nine ensemble cubes totalling 21 MB were once tracked, and removing them
  from the index does not shrink `.git`, the blobs remaining reachable in
  history. `portra_decompose.py --out-suffix` and the overlay tooling
  regenerate them.

One engine per family, parameterised by stock and illuminant, propagates any
methodological correction everywhere by construction and removes the failure
mode in which two stocks' build scripts diverge. Builds emit no per-build
manifest recording engine commit and data hashes.

## Hard constraints (do not relax these)

1. **No unbracketed synthesis of spectral shape.** A dye, sensitivity or
   D-min curve is authoritative only within its measured support, and no
   value outside that support may enter a fit objective or a shipped integral
   as if it had been measured. Every engine nevertheless makes some claim
   about the bands it cannot see (an observer truncated and renormalised
   asserts that the unmeasured tail transmits like the in-band mean; a paper
   exposure integral cut at the negative's support asserts that the band is
   blocked; a basis held flat asserts a plateau), so the rule governs how such
   a claim is made. Four responses are admissible, in order of preference:
   - **Interpolation between measured samples** of one curve, across a dash
     gap or a crossing, with the bridged samples recorded in the file's audit
     block.
   - **A bracket**, the standard treatment of a band outside support: the two
     physically admissible extremes (edge value held against zero; band
     blocked against transmitting; plateau against a continued descender) are
     both carried through the engine and their spread is entered in the
     register as the bound. Truncation with renormalisation is one point
     inside such a bracket and is never the bound itself.
   - **A single chosen prior**, only when its alternatives have been measured
     end to end and recorded (register #18 is the pattern), and never chosen
     for the fit residual it buys: a lower residual over an unmeasured band is
     the signature of an over-fitted invention.
   - **Every synthesised sample is marked in the data file** (`basis_held`,
     the `digitization_audit` endpoints), so that a reader can exclude it.
   Free extrapolation of shape into a band with no bracket remains prohibited;
   the tone-curve extension of register #16 is the only extension by slope.
2. **Numerical grounding takes precedence over qualitative review.** Every
   claim about accuracy, and every assertion that an effect is negligible,
   derives from running the computation over the measured data in this
   repository. The characteristic failure is a qualitative judgement of
   negligibility that proves wrong once computed over the relevant domain:
   a linear-in-cyan framing makes the cyan truncation of register #2 appear
   negligible, whereas it reaches 0.24 D in deep shadow.
3. **Validate the artifact as shipped, rather than the in-memory array.**
   `.cube` files are clipped to [0,1] and quantised to six decimal places on
   write. Re-parse the written file and validate that.
4. **Metric and aesthetic operations remain separated.** Per-channel log-space
   offsets (printer lights, white balance, CC filtration) are aesthetic and
   belong in a node *above* the metric transform. Folding them into the
   metric, for instance by adopting a neutral point set by eye, corrupts it;
   this is the central criticism of NamiColor's reversal-mode workflow.
5. **No scene-dependent decisions occur anywhere in the chain.** Every
   operation is either a fixed physical constant (dye spectra, paper H&D
   curves, Status M responsivities) or a per-roll physical measurement (the
   anchor). Nothing reads picture content. The two normalisations that could
   have introduced such a dependence are keyed to scene-independent
   references by construction: the roll anchor to unexposed film base, light
   that never formed an image, and the gray-axis lock to the stock's own
   published neutral scale, solved once per stock and paper. Consequences:
   the scene illuminant survives into the grade (a tungsten-lit frame remains
   warm, as this emulsion and this paper render it, which is a photographic
   rather than a colorimetric record of the illuminant); frame-to-frame
   relationships across a roll survive; and the property is one-directional,
   since a cast can be removed later in the grade whereas a cast removed by a
   content-dependent estimator cannot be restored. Any future automatic
   neutralisation, automatic exposure or content-driven correction belongs
   above the metric transform, per constraint 4.

## Source data (`data/`)

**Equipment** (`data/equipment/`). `film_scanner_SPD_combined.csv`: measured
LED SPDs, 380–780 nm at 1 nm, narrowband R/G/B at multiple drive levels
together with broadband white W1–W100 columns that are unused.

**Camera spectral sensitivity** (`data/cameras/`). Forty-four measured camera
sensitivity functions, 380–780 nm at 5 nm, imported verbatim from the ACES
`rawtoaces-data` library by `engine/scan/aces_ssf_import.py`. Each file
records the source URL, the SHA-256 of the upstream document, the measuring
laboratory and the creator, and the importer re-reads every file it writes
through a copy of the engines' own reader. `index.json` maps the EXIF model
strings that identify each body. The population is the consumer
interchangeable-lens Bayer subset of the library: fixed-lens compacts, drone
and cinema modules and the X-Trans bodies are excluded, the last because a
6×6 colour filter pattern has no 2×2 reading. `GROUP_A` in the importer is an
explicit list, so an addition upstream cannot enter unreviewed. No engine
reads any of these files by default; `--sensor` selects one, and its default,
`none`, supplies no spectral sensitivity at all. This directory is the one
part of `data/` that is not CC BY 4.0: the upstream library is Apache-2.0,
and `LICENSE-DATA` carries the scope exception.

**Per-stock film data** (`data/films/`). Each JSON documents its own
digitisation method, registration audit and known uncertainties.

- `Vision3_dye_density.json`: the Kodak VISION3 shared image-dye set, the
  family average of the four traced stocks, together with the family-average
  Minimum Density curve. The averaging is load-bearing: a single-stock basis
  is wrong by up to 0.197 D in cyan at 402 nm, across a band carrying 69% of
  Status M blue responsivity. No spektrafilm-sourced data is used anywhere in
  this project, that data being unvalidatable.
- `Vision3_<Stock>_dye_density.json`, `_datasheet_curves.json` and
  `_spectral_sensitivity.json` per Vision3 stock (500T's curves file keeps
  the name `V3500T_datasheet_curves.json`).
- `Velvia100`, `Velvia50`, `Provia100F` and `EktachromeE100` `_dye_density.json`
  and `_datasheet_curves.json`. The Ektachrome file covers both E100 and
  100D/5294–7294: the dye data on the two datasheets is identical, verified
  against the Kodak Alaris E-4000 rev. 8-18 and Eastman Kodak H-1-5294 rev.
  5-24 sheets, whose provenance the JSON records.
- Twelve C-41 stocks, each with `_datasheet_curves.json`,
  `_spectral_sensitivity.json` (absent for Pro 400H) and `_dye_density.json`.

**Target-metric standards** (`data/standards/`).

- `StatusM_ISO5-3.json`: ISO 5-3 and CGATS.5 Status M spectral products,
  obtained via ArgyllCMS `xspect.c`; its Status A table matches
  `StatusA_ISO5-3.json` exactly, indicating a shared lineage. Status M is the
  C-41 densitometric target because the C-41 characteristic curves are
  published in it, which makes the datasheet numbers usable for quality
  control. Unverified against the paid primary standard (register #19).
- `StatusA_ISO5-3.json`: ISO 5-3:1995 Table 3 Status A responsivities, from
  the public ANSI/NAPM IT2.18-1996 copy.
- `CIE1931_2deg_CMFs.json`, the CIE 1931 2° colour-matching functions over
  360–830 nm at 1 nm, and `D50_illuminant.json`, the CIE D50 relative SPD over
  300–780 nm at 5 nm. Both are exported from the official CIE tabulations in
  colour-science 0.4.7 and stored as published; reloading them reproduces the
  D50 white point xy (0.3457, 0.3585) and XYZ (0.9642, 1.0, 0.8250) exactly.
- `APD_ST2065-2.json`: Academy Printing Density responsivities, ST 2065-2:2012
  Tables A.1 and B.1, the ADX16 route's target.
- `StatusM_to_APD_S-2008-002_AnnexC.json`: the Academy's Status M to APD
  conversion transforms for 31 negative and intermediate stocks, matrix,
  offset and published residuals per stock, from S-2008-002 Annex C. Read by
  `annexc_check.py` for the 5207 and 5219 entries.
- `RP180_responsivities.json`: SMPTE RP 180 printing-density responsivities,
  peak-normalised, 360–730 nm at 10 nm, including the sub-400 nm blue tail.
  Verified against the standard; the ADX16 build reads it for its
  APD-versus-RP 180 comparison line.
- `reflectance/`: measured reflectance datasets for broad-set matrix fitting
  and validation: Munsell glossy 1600 and matt 1269 (UEF, via the
  colour-science Zenodo deposit), Agfa IT8.7/2 289, and NIST human skin 100
  (Cooksey, Allen and Tsai 2017, per-subject averages). All share one JSON
  schema with reflectance on 0–1; provenance and resampling notes are in the
  directory's README.md.

**Papers** (`data/papers/`). `EnduraPremier_paper.json` (E-4070, March
2013), `FujiProLaserTypeII_paper.json` and `CrystalArchiveTypeCA_paper.json`,
each with characteristic curves as Status A density against logE for R/G/B,
the spectral sensitivity of the Y/M/C-forming layers and the spectral dye
density of C/M/Y, layers assigned by spectral peak, and a
`digitization_audit` block. Type CA publishes no characteristic curves and is
reference data only.
## How a transform works

Every transform is a **spectral round trip**. The scanner SPD, multiplied by
the camera's spectral sensitivity where one is named, integrated against the
stock's measured dye curves yields scan density; the same dye state integrated
against the target responsivity (CIE D50 XYZ, APD or Status M) yields target
density. On the negative paths the scan-side integral carries one further
factor, the stock's traced D-min spectrum as a filter on the illuminant: the
roll anchor divides the base and orange mask out of the linear frame, which is
a subtraction of integrated densities, so the cube receives the density of the
image dyes as the LEDs see them THROUGH the mask, and the engine integrates
`LED × sensor × 10^−Dmin(λ)`, renormalised (register #17). The mapping between
the two integrals is solved numerically at each node (Newton or
Levenberg-Marquardt) and shipped as a 65³ LUT; no analytic DCTL is exported.
Not every lattice node admits a solution, the domain being a box of densities
of which the dye set reaches only part; the reversal engine substitutes for
the unreachable remainder (its section below), the negative engines do not
(Invariants).

The Vision3 scene route is the one transform whose destination is not a
density: it shares the first half of the round trip, then inverts each layer's
characteristic curve to log exposure and maps relative exposure to XYZ (D65)
through a fitted 3×3, landing in scene-linear DaVinci Wide Gamut.

The round trip is a change-of-observer problem requiring four inputs: dye
curves (traced from the manufacturer's charts), illuminant SPD (a measurement
of this apparatus), camera spectral sensitivity, and target responsivity (a
standard). The sensor term is omitted by default: a monochrome sensor's
response appears in both numerator and denominator of a density measurement,
so a constant response cancels exactly, while a response that varies across
an LED's band does not, and the engines integrate the illuminant alone unless
`--sensor` names a body. No monochrome sensor has been measured, so the
omission is an approximation with no established bound; register #9 quantifies
it as a labelled scenario and bounds the Bayer case.

### Corridor and shaper convention

A preshaper, `d = clamp(-log10(linear), 0, DMAX)/DMAX`, converts into the
cube's normalised [0,1] domain; on the reversal path a postshaper, `× DMAX`,
converts back out. Shapers carry no spectral content and are reusable across
any stock and illuminant sharing the same DMAX.

**The negative path (Status M, ADX16 and Vision3 scene alike) uses DMAX 3.30
on every sensor; the reversal corridor depends on the sensor.** All builds are
65³. `Preshaper 3.3.dctl` feeds every negative cube and no postshaper follows
any of them: the scene cubes leave density behind, the ADX16 cube emits code
values, and the Status M cubes feed the print tables in normalised density.
On the reversal path one pair serves all four stocks at a given corridor:
`Preshaper 5.0.dctl` and `Postshaper 5.0.dctl` for the sensor-free cubes that
ship, and the 5.25 pair for the a7R III build. Crossing corridors rescales
density silently (register #5).

**The reversal corridor is set by the stock's densest state, measured.**
`reversal_transform.py` evaluates scan density over a neutral dye-4.0 stack
and an off-neutral sweep of the same box, prints the requirement on every
build, and warns, naming the value to use, when the corridor would clip it:

| stock | sensor-free | through the a7R III |
|---|---|---|
| Velvia 100 | 3.88 | 3.95 |
| Ektachrome E100 | 4.25 | 4.28 |
| Provia 100F | 4.60 | **5.08** |
| Velvia 50 | **4.75** | 4.91 |

Hence 5.00 sensor-free and 5.25 for this apparatus. 5.25 is a property of one
camera and not a general Bayer constant: a colour filter band-limits the
illuminant's spectral tails by an amount particular to that filter, so another
body's corridor is determined the same way (BUILDING.md).

**Corridor and LUT size are coupled.** Node spacing is `dmax/(size-1)` and
trilinear error scales as the square of spacing (measured: 4.5 to 6.0 at 33³
raises error by 1.78 against 1.78 predicted). At a 6.0 corridor the a7R III
reversal builds measure RMSE 0.0004 D, maximum 0.0012 D, and reach 58–62% of
the lattice; at 5.25, **0.0003 D and 0.0009 D** and 68–73%. A 4.5 corridor is
overrun by two stocks even sensor-free and gave 0.0009–0.0010 D with a
maximum of 0.003 D at 33³.

**Two numbers are both called a serialisation check; only one is an accuracy
figure.** Comparing the written cube against the in-memory lattice NODE FOR
NODE measures the six-decimal write rounding, pinned at 2.9e-07, and nothing
else. The figure that matters interpolates the artifact read back from disk at
off-lattice points (hard constraint 3). Every engine prints both, labelled. On
the print branch the gap is four orders of magnitude: Portra 400 to Endura
serialises at 2.7e-07 by node quantisation and carries an interpolation RMSE
of 2.3e-03 with a worst case of 8.9e-02, 23 code values out of 255, its PQ
pair 4.0e-03 and 1.5e-01. Those are the print branch's real lattice accuracy,
the largest such error in the chain.

**The negative corridor carries deliberate headroom.** `DMAX = 3.30` is
uniform across the twelve stocks, whose published maxima need between 1.69 D
of scan density (Gold 200) and 2.16 D (Pro Image 100), so the corridor holds
53% to 96% more than any datasheet documents. Real film is exposed past the
end of its published curve, and the engine reports the requirement per stock.
Tightening was measured and rejected: Portra 400 rebuilt at 3.30, 3.00, 2.80,
2.60 and 2.40 and probed over the SAME physical range gives, on the Status M
cube, a maximum error falling from 0.0028 D to 0.0012 D (a factor of 2.3
against 1.9 predicted by the squared-spacing law), and on the print cubes no
trend at all (RMSE 2.3 to 3.1e-03, maximum 7.3 to 8.0e-02 over a fixed 0 to
2.16 D input), because the print lattice's error is dominated by the
Display P3 gamut clip, a kink no node spacing resolves, a quarter to a third
of that lattice sitting outside P3 before clipping. Since print emulation is
the sole C-41 delivery route, the change would improve only the intermediate
artifact, already one to two orders below the 0.034 to 0.063 D basis
sensitivity; it would leave 0.9 stop of headroom beyond the published curve on
Ektar 100 and Fujicolor 100 at 2.40 (1.1 on Portra 400; under two stops at
2.60; only 3.00 and above keeps every stock past three stops) where negatives
are routinely overexposed one to two stops by intent; and `DMAX` is
load-bearing in four places that must agree (both C-41 engines and both 3.3
shaper DCTLs). The accuracy probe over the working dye range, reaching 2.18 D,
reports RMSE 0.0002 D and a maximum of 0.0028; over the whole declared
corridor 0.0013 D and 0.0407. Both are printed.

Narrowband scan density exceeds the film's Status A density, because the LEDs
sit on the dye peaks: Velvia 50 scan red reaches 4.08 D at a 3.5 D Status A
neutral and 4.42 D at 3.6 D, and a 4.0 corridor clips Velvia 100's scan red by
0.17 D at a 3.5 D neutral. A corridor is never inferred from the film's
physical Dmax.

### Resolve node chains

docs/resolve.md carries the chains node by node with the operator's
instructions; this section records the parameters behind them.

**Reversal:** `RollAnchor_ScanPrep.dctl` (paste the EXR-scale Dmin R/G/B) →
`Preshaper 5.0.dctl` (5.25 for a camera-named build; the unpublished 4.5 and
6.0 pairs serve older cubes only) → cube, own node, tetrahedral → `Postshaper
5.0.dctl` (or 5.25) → `Density to Linear.dctl` (the 10^-D node; its trims stay
at defaults here) → `XYZ D50 to DWG.dctl` (an explicit 3×3; a Resolve CST
cannot substitute, because the cube emits WHITE-RELATIVE XYZ) → aesthetic
offsets → display transform. Every node between the preshaper and the
linearisation node displays inverted, the image being in density space. The
chain is anchored at the bright end on the film base: after anchoring the
linearisation node cannot emit values above linear 1.0, so peak brightness is
decided by the display transform and no absolute luminance is encoded. For HDR
delivery emulating the ISO 3664 transparency illuminator (1270 cd/m², roughly
800 nits through a typical 0.2 D base), the linearisation node's OutputGain is
the control; the value differs per stock and roll, so set it against the
timeline's scopes.

**ECN-2, ADX16 (the route):** scan prep → `Preshaper 3.3.dctl` (VALUE_BOXes
at 1.0) → `builds/ecn2/Vision3 to ADX16.cube` → `Printer Lights ADX16.dctl`
(per-channel density trims; a raw Academy decode always needs them, dialled
once per stock and rig on a known neutral) → ADX decode (input colour space
ADX (16-bit), `CSC.Academy.ADX16_to_ACES`) → the ACES timeline. No
postshaper: the cube emits normalised code values and the trim DCTL converts
its density sliders to code-value offsets internally, applying the ST 2065-3
factors k = (1.00, 0.92, 0.95). Density-space stages of a negative display
positive tonality. Do not use `Density to Linear.dctl` here. The Academy
decode reads the negative against a reference-film assumption Vision3 does not
meet, which is the source of the route's bound: ColorChecker ΔE2000 6.3–7.3
mean after the printer-light trims, solved as the DCTL applies them (APD
offsets on the code values before the decode), against the scene-linear
route, effective contrast 0.92–0.99 of
the scene's, and a grey-axis channel spread of 6–18% in AP0 at mid-grey rising
to 14–35% at +1.5 stops, which the printer-light trims remove at one density
only; the larger figures belong to 250D and 500T, whose masks depart most from
the family average the one table carries (register #17). No datasheet
printer-light presets exist for this chain, and none carry over from other
routes. A print-through look is optional and lives in the timeline: Resolve's
built-in "LMT Kodak 2383 Print Film Emulation" after the decode.

**ECN-2, scene-linear (secondary, for graded work):** scan prep → `Preshaper
3.3.dctl` → the stock's own `Vision3 <Stock> to Scene DWG.cube` under
`builds/ecn2/` → CST (DaVinci Wide Gamut / Linear → timeline) → grade. No
postshaper, no printer lights and no `Density to Linear.dctl`: the output is
linear, negatives permitted. The stock's balance illuminant (D55 for 50D/250D,
3200 K for 200T/500T) is built in and Bradford-adapted to D65, so a tungsten
stock under tungsten light decodes neutral and the datasheet's midscale
neutral lands at 0.18. Exposure and balance trims belong after the cube, in
linear. There is no separate HDR table.

**C-41:** scan prep (for C-41 this is also the orange-mask removal, per
channel) → `Preshaper 3.3.dctl` → `builds/c41/<Stock>_StatusM.cube` → `Print
Adjustment.dctl` (optional; defaults no-op; must precede the print cube) →
`builds/c41/print_endura/<Stock>_to_PortraEndura_DisplayP3.cube` (Fujifilm
stocks: `print_fuji/<Stock>_to_FujiProLaser_…`) → grade. The two cubes must
be the SAME stock; mixing them mis-tones the image with no visible warning,
each encoding its own D-min. The print cube's output is **Display P3 (D65),
sRGB-encoded and clipped to [0,1]**, written into every cube header: an input
of k = 0.22 returns 0.4613/0.4613/0.4614, which is 18% grey through the sRGB
transfer function (0.4620) and demonstrates the gray-axis lock holding neutral
to four decimal places. Do not place a colour space transform after it on the
assumption that it emits scene-linear data. For quality control, stop after
the Status M cube and multiply by 3.30: the result is Status M density with
D-min excluded, directly comparable with the E-4050 characteristic curves and,
once the roll's D-min is added back (approximately; register #17), with the
gray-card corridor of 0.77–0.87. Printing density was deliberately avoided for
C-41, because it encodes a cine print stock's view of the negative and is
foreign to a stock whose destinations are RA-4 or digital.

### `PrintEmulationEngine`: the shared print-emulation core

A configuration-driven `PrintEmulationEngine`, parameterised by `PrintConfig`
and supporting reflective and transmissive media through `neutral_basis`,
`medium_base_spd` and `adapt_view_white_to_d65`, carries the print model;
`EnduraPrintEngine` and `FujiProLaserPrintEngine` are thin presets over it.
Two properties of the core are load-bearing: the medium's spectral base
appears in the rendered spectrum, the engine subtracting `Dbase` to recover
dye amounts and then forming `10^-(base + a·DYE)` (inert for Endura, whose
paper JSON carries no `base` block), and chromatic adaptation of the viewing
white to D65 precedes the D65-referred XYZ to P3 matrix (a no-op when the
viewing illuminant is already D65).

## Per-roll anchoring

The cubes map scan density onto their target density exactly, although
density is defined only with respect to a reference. Anchoring pins that
reference to the actual roll, per roll rather than per apparatus, because
D-min varies with processing and film condition while remaining within
specification.

**Measurement** is performed by `engine/scan/roll_anchor_gui.py`, one
self-contained engine carrying the graphical interface and the numeric core,
specified under Engines and script reference. It consumes calibration captures
the roll already carries: the clear leader (reversal) or unexposed rebate
(negative) for D-min, the one required set, and optionally plain light with no
film in the gate and the rebate or light-struck leader tip for D-max. The
Resolve deliverable is measured against the sensor white level and needs no
plain-light reference; the plain-light set adds the plain-light-scale densities
and the measured LED crosstalk, which nothing downstream requires. D-max is
reached by lengthening the exposure, which the shutter normalisation divides
out; no dark-frame subtraction is performed. `--film-family` selects which area
of film supplies which anchor; the measurement is identical.

**LED drive level is a free variable.** The cubes are built against the
100%-drive SPDs. The worst case over dye 0–3.5, on Velvia 100 at 20% drive, is
0.013, 0.032 and 0.003 D in R, G and B on saturated colours, where the green
LED's shift interacts with the steep magenta flank; the median is ≤0.006 D and
dye-3 neutrals stay below 0.01 D. The measured spectral shift is approximately
1 nm of centroid between 20% and 100% drive. Because D-min is measured at the
same drive level as the scan, the anchor absorbs the neutral-axis component and
only the colour-dependent residual survives; a drive level of 50% or above
keeps the worst case under approximately 0.02 D. Where either control would
serve, prefer shutter time, which is spectrally free. **RULE: a plain-light
datum frame must be captured at the SAME LED drive level as the roll's scan**,
or the drive-level shift must be measured and recorded in the anchor JSON,
since a datum at a different level silently breaks the cancellation.

**Application** is by `dctl/prep/RollAnchor_ScanPrep.dctl`, hand-written,
slider maximum 2.0 because orange-mask D-min values exceed 1.0. Three sliders
receive the D-min R/G/B values, and the node multiplies linear values by
10^Dmin per channel so that the roll's film base lands at density 0.0, the
base-relative convention every cube expects. A Strength slider provides an
anchored and unanchored A/B comparison. Verified: the leader maps to 0.0 D
exactly and base plus 1.5 D maps to 1.5 D exactly. This is a metric, measured
operation, never a place for neutralisation by eye. `Preshaper 3.3.dctl`
carries its own built-in linear D-min boxes, defaulting to 1.0 to indicate
anchoring upstream; use one mechanism or the other, never both.

**Two density scales.** The extractor reports D-min against two zero points.

- The *plain-light scale*, recorded as `dmin` only when a plain-light set is
  supplied, is density relative to the plain-light frame, true transmission
  density, the scale to compare against datasheets.
- The *EXR scale*, recorded as `dmin_exr_scale` and presented as the headline
  figure on the GUI result screen and clipboard, is density relative to the
  sensor white level, the normalisation `raw_to_exr.py` bakes into its EXR
  files. It needs no reference frame. Each channel carries its own
  plain-light-to-white-level offset, approximately +0.24, +0.58 and +0.93 D in
  R, G and B on this apparatus. A D-max patch is reported against the D-min
  frame as `dmax_above_base` whether or not a plain-light set exists.

**Paste the EXR-scale values into `RollAnchor_ScanPrep.dctl` when grading
`raw_to_exr` EXRs.** The plain-scale values over-anchor: green and blue are
crushed past the preshaper's density-zero clamp, producing a strong
yellow-green cast. EXR-scale values are valid only if the anchor frames were
exposed at the roll's own per-channel exposure and at the same ISO.
## Engines and script reference

`engine/` is organised by family: `scan/` holds the converters and the anchor
tool, `c41/` the still-negative toolchain and both print engines, `ecn2/` the
ADX16 and scene engines, `reversal/` the cube builder. Run everything from the
repository root. BUILDING.md records the command behind every cube.

### C-41 toolchain (`engine/c41/`)

Datasheet-only calibration for C-41 stocks, none of which publish per-layer
dye spectra. The per-layer data is INFERRED by a constrained fit against the
Vision3 dye basis, pinned metrically by the published Status M characteristic
curves; register #8 records the resulting uncertainty. Every script is
parameterised by `--stock`, and the registry `engine/c41/portra_stocks.py`
holds each stock's source sheet, provenance code, output filenames and
per-sheet chart geometry. Metrics quoted here are Portra 400's; the per-stock
tables are under "Current state by stock".

> **Shared KODAK VISION emulsion lineage does not justify the basis.** Gold
> 200, a non-VISION control, fits the Vision3 basis *better* than any
> VISION-lineage stock, at RMSE 0.0142 against Ektar 0.0159, Portra 400 0.0174
> and Portra 160 0.0183 (single-start figures). The basis encodes no
> VISION-specific chemistry and is a generic flexible three-dye model that
> fits any C-41 aggregate. It remains the best available basis and the fits
> stand; lineage is not a reason to trust them.

1. `data/films/<Stock>_datasheet_curves.json`: the traced characteristic
   curves and spectral dye-density chart (midscale neutral and D-min), with a
   `digitization_audit` block.
2. `data/films/<Stock>_spectral_sensitivity.json`: the traced
   spectral-sensitivity chart (Portra 400 layer peaks 406, 550 and 651 nm).
   Both files are the measured class, bounded by register #13.
3. `portra_decompose.py`: a nine-parameter warped-basis fit, over per-dye
   amount, peak shift within ±25 nm and width within ±15%, of midscale minus
   D-min onto the Vision3 dyes. Portra 400: aggregate reconstruction RMSE
   0.0109 D, Status M reproduction deltas 0.009, −0.001 and −0.002 D in R, G
   and B, and an LED crosstalk condition number, for the LEDs as the roll
   anchor leaves them behind the mask, of 1.4163. The solve is a seeded
   64-point multistart (register #12). It writes
   `data/films/<Stock>_dye_density.json` with a `fit_audit` block. The ±25 nm
   shift bound is uniform across all twelve stocks, recorded per stock as
   `shift_bound_nm` in the registry (register #8).
4. `c41_statusm_engine.py`: the scanner-to-Status M cube, D-min excluded,
   Status M red truncated at the 700 nm dye-chart edge and renormalised
   (0.28% of the red area). Its scan-side responsivity is the LED (times the
   sensor, when one is named) filtered by the stock's traced D-min spectrum
   (register #17); the engine prints the D-min at the three LED peaks and the
   centroid shift the mask imposes on each LED (Portra 400: 0.2, 6.1 and
   3.4 nm in R, G and B). Its neutral-axis check reads the full traced
   midscale and the base with the BARE LEDs, anchors one against the other
   exactly as the DCTL does, and unmixes the result through the
   mask-filtered model: the closure is the fit's own Status M reproduction
   error (Portra 400: −0.006, +0.002 and −0.005 D). It writes
   `builds/c41/<Stock>_StatusM.cube`.

The unpublished scene-referred engine forms no part of any shipped build. It
proceeds from Status M to dye amounts by Gauss-Newton, through
characteristic-curve inversion to layer exposures, then through a 3×3 fitted
on the ColorChecker babel_average under D55 and adapted to D65 by Bradford
with 18% gray pinned to DWG 0.18, producing the retained
`Portra400_StatusM_to_DWG.cube`. It is the only home for the broad-set 3×3
fit over 3,258 measured reflectances, whose finding stands: the
ColorChecker-only matrix is already near-optimal on 3,258 unseen spectra (the
broad-set matrix improves the checker mean from 2.50 to 2.46, skin from 2.67
to 2.64, Munsell maximum from 8.51 to 8.10), so the saturated-red ΔE of 6.3 is
a limit of the forward model, attributable to the surrogate cyan and to
missing interimage effects, and no 3×3 remedies it.

**Interimage and DIR structure.** `engine/common/interimage.py` applies a 3×3
`DIR_MATRIX`, identity by default, in dye-amount space with grey-ramp
pre-compensation (the pre-coupler curves are solved so that the neutral ramp
reproduces the datasheet curves exactly; the identity case takes a fast path
verified bit-identical). It is instantiated in `v3_scene_engine.py` and in the
unpublished scene-referred engine only; no file under `engine/c41/` contains a
DIR stage, and `DIR_MATRIX` gates no shipped cube. Its parameters are
unmeasured. The architecture (DIR matrix, grey-ramp pre-compensation) is taken
from spektrafilm; **no data is**: spektrafilm's inhibition numbers are a single
author-tuned default shared across all C-41 negatives, some entries commented
"just eyeballed", with interlayer terms around 0.15–0.35 of the same-layer
terms, and carry no per-stock signal. Everything metric in the chain rests on
measured data (the reflectance sets are genuine spectrophotometry; the film
curves are this project's digitisation of published charts); the sole
non-measured element in the C-41 chain is the inferred per-layer dye split
(register #8).

### C-41 → RA-4 print-paper emulation

**The ONLY C-41 delivery route.** Its input domain is normalised Status M
density with D-min excluded, so it chains after `<Stock>_StatusM.cube`. Each of
the twelve stocks has a print emulation paired by manufacturer: Kodak
negatives to Kodak ENDURA Premier (`print_endura/`), Fujifilm negatives to
Fujicolor Pro Laser TYPE II (`print_fuji/`). The pairing is enforced by the
`print_paper` key in `portra_stocks.py`; each print engine offers only the
stocks matching its paper and the argument parser rejects a cross-paired
build. The key records which paper a user would print that brand on and makes
no claim about which factory coated the film.

`endura_print_engine.py` proceeds at each node from Status M density to
negative dye amounts by Gauss-Newton inversion, to negative spectral
transmittance including the orange mask (`N(λ) = dmin_spec(λ) + Σ dye·DYE(λ)`),
through a tungsten enlarger at 3200 K to paper exposure, per layer to the
amount of dye that exposure forms, and to print reflectance, a D65 viewing
condition and P3. The paper's three characteristic curves are Status A
INTEGRAL densities of one neutral exposure series, each channel carrying the
other two layers' unwanted absorption (the unit paper dyes' Status A matrix
has off-diagonal terms of 0.02–0.11), so the engine converts them once, on
that series, into per-layer amount-against-exposure tables by inverting
Status A with `data/standards/StatusA_ISO5-3.json`, and renders every colour
by looking each layer up on its own exposure; reading each channel's curve at
its layer's exposure would agree on the neutral and mis-attribute the cross
absorption everywhere else, at up to 15 ΔE2000 on saturated colours
(Invariants). Gray balance is a full per-channel GRAY-AXIS LOCK, all channels
pulled onto the mean neutral tone curve at every density and auto-solved so
that a neutral negative prints neutral; the engine reports how far the lock
departs from a per-channel offset, which is the print-model shape error it
absorbs. The self-report also prints the paper-table solve (machine
precision) and the share of the lattice that runs off those tables. Each run
emits a Display P3 SDR cube and a P3-D65 PQ cube with paper white at 203 nits.
No modelling constant differs between stocks.

A read-only validation battery (not distributed) covers digitisation
integrity, grid coverage, gray-axis lock, solver health, colorimetry and
shipped-artifact fidelity (groups A to F). Only some checks carry a pass
criterion; the rest print numbers, and the summary reports how many were
verdicted of the total. All verdicted checks pass, group F included (F1 RMSE
2.6e-07 and 2.8e-07, F2 zero violations, F3 5.9e-06). Read both summary lines
and treat a traceback as a FAIL: a validator that dies part-way still prints
its earlier groups.

#### The printable neutral window

**The single most important property of the print path.** At the true paper
gamma, approximately 2.6 from the datasheet H&D curves, the printable neutral
window is NARROW, and outside it the print clips to paper white or maximum
black exactly as a real RA-4 print does. The window is a property of the
PAPER, measured by each engine on its own neutral ramp as the span over which
the mean print density sits 0.02 D clear of both paper white and the weakest
layer's maximum black:

| paper | window (Dnorm k) | OD | sensitivity at mid-gray |
|---|---|---|---|
| Endura Premier | [0.082, 0.348] | 0.88 | 0.33 stop per 0.01 k |
| Fuji Pro Laser | [0.036, 0.364] | 1.08 | 0.27 stop per 0.01 k |

The sensitivity is the system gamma over the window (3.03 on Endura, 2.41–2.52
on Fuji Pro Laser by stock) times the 0.033 D that 0.01 k represents. The
window varies by at most 0.002 k across the Kodak stocks on Endura and 0.010 k
across the Fujifilm stocks on Fuji Pro Laser. Fuji Pro Laser is the
lower-contrast paper, offering roughly 0.2 OD more room, almost all of it at
the shadow end. Off-neutral corners are correspondingly extreme: 26–30% of the
lattice falls outside P3 before clipping on Endura and 13.5% on Fuji Pro
Laser. On the shipped lattices no layer's exposure runs off its table nor
clips at zero; the only infeasibility is on the negative side, where 22–25%
of nodes ask for a negative image-dye amount, as the box domain must
(Invariants).

CAVEATS. No physical print has been measured against this path. The
appearance of a *viewed* print (enlarger veiling flare, print-surface glare,
viewing surround) is a non-goal: the branch reproduces the paper's colour
treatment as densitometry records it. The enlarger SPD at 3200 K is nominal,
and the negative side uses the surrogate dye model of register #8. D65 viewing
is nominal and measured harmless: the datasheet specifies evaluation at
5000 K ± 1000, and D50 with CAT02 differs from the shipped D65 render by ΔE00
median 0.75 and maximum 3.28, 0.017 on the neutral axis (7.3 and 15.3 without
the adaptation). The paper's spectral base is absent from the datasheet, so
its D-min non-neutrality (Status A 0.0915/0.0915/0.0651, a 0.026 D
blue-versus-red difference) is discarded rather than rendered: `Dbase` is
stripped as a scalar and `base_spec_C` is zeros.

#### Darkroom controls

Three controls, at the three stages where a real darkroom provides them, all
defaulting to no-ops:

| control | where | what it does |
|---|---|---|
| `PrintConfig.flare` | paper, during exposure (pre-lock) | contrast: system gamma 1.83 → 1.61 at 0.010 |
| `PrintConfig.printer_lights` | paper, after the lock | colour balance: b\* ±16 for ∓0.05 logE |
| `dctl/output/Print Adjustment.dctl` | negative, before the cube | tone + balance, live: gamma about a pivot, exposure offset, per-channel printer lights |

The placements are load-bearing. `flare` is a property of the optical path
present while the print is balanced, so it precedes the gray-axis lock;
`printer_lights` follows the lock, because the lock defines the neutral
reference and printer lights are a departure from it (placed before, they
would be re-neutralised). Verified: flare moves gamma while leaving the
neutral axis at Cab\* ≤ 0.001, and printer lights swing b\* by ±16 with gamma
unchanged in 1.79–1.84. The DCTL precedes the cube because on the negative
side it functions as an enlarger.

**Contrast grades do not exist for RA-4.** There is no dual emulsion for
filtration to bias, so the light mix controls colour balance alone; a
per-channel logE offset cannot alter dD/dlogE. What softens a real print is
veiling flare, the paper surface, exposure placement onto the toe and
shoulder, and local work. Exposure placement is measured: an overall shift of
−0.30 logE takes system gamma from 1.83 to 0.81, the curve being sigmoidal
with a local slope of 0.9 in the toe, 4.6 mid-curve and 1–2.5 in the
shoulder. Of those effects only exposure placement is in the chain; flare,
surface and surround carry no measured value, so the shipped cubes render the
flare-free ideal at system gamma 1.83, above any physically viewed print by
construction. A Gamma below 1.0 at the DCTL is ordinary use. A constant
reduction applied identically to every stock and image is an estimate of the
missing flare terms, whose measured home is `PrintConfig.flare`; the DCTL's
Gamma changes slope uniformly about the pivot, whereas enlarger flare rolls
off print highlights asymmetrically.

The Print Adjustment DCTL requires no rebuild. Its domain is normalised
Status M density, `k = OD/3.30`; density runs backwards (higher k, lighter
print) and the printable window is narrow, so a change of 0.01 in k is
visible. Two modes, selected by `Literal Pow`:

```
darkroom (default) :  k' = pivot + (k - pivot) * gamma + gain
literal            :  k' = (1 + gain) * k ^ gamma
```

`gain` is a pure density offset (enlarger exposure); `gamma` is contrast
about `pivot`, whose default 0.22 is the engine's calibrated mid-gray, the k
that renders Y = 0.18. Literal mode's fixed point is k = 1.0 whereas the image
lies below k ≈ 0.41, so it reads predominantly as brightness. `Gain R/G/B` are
additive density offsets after the master in both modes, printer-lights colour
balance operating live. Measured through the engine's calibrated neutral ramp:

| case | gamma | Y(mid) | a\* | b\* |
|---|---|---|---|---|
| baseline | 3.034 | 0.1828 | −0.01 | 0.02 |
| gain +0.010 | 2.935 | 0.2366 | −0.01 | 0.00 |
| gain −0.010 | 3.100 | 0.1377 | −0.02 | 0.02 |
| gamma 1.20 | 3.292 | 0.1834 | −0.01 | 0.02 |
| gamma 0.85 | 2.756 | 0.1824 | −0.01 | 0.01 |
| gamma 0.85, pivot 0.10 | 2.881 | 0.1069 | −0.01 | 0.01 |
| literal gamma 0.90 | 2.689 | **0.4149** | −0.01 | 0.02 |
| trim R +.005 B −.005 | 3.025 | 0.1868 | 1.89 | 4.78 |

The pivot holds (gamma 0.85 to 1.20 swings system gamma 2.76 to 3.29 with
mid-gray at 0.182–0.183); a pivot at 0.10 drags mid-gray to 0.107; gain +0.010
moves mid-gray 0.183 to 0.237, *more* density yielding a brighter print;
literal gamma 0.90 more than doubles mid-gray to 0.415; the per-channel trim
swings b\* by 4.8 at ±0.005 k at constant contrast. `dctl_shim.c` confirms the
defaults are a bit-exact no-op in both modes, that pivoted gain offsets all
three sample points by exactly +0.010000, that literal gain is exactly
`1.1 × k`, that the per-channel trim is identical across modes, and that the
output clamps into [0, 1].

**DCTL authoring constraints.** Resolve rejects some otherwise valid files
with `wrong argument int p_Width in Transform DCTL` or `main DCTL function has
wrong arguments`; the message names the `transform` signature while the fault
lies earlier in the file. Restrict a file to constructs that appear in a
working DCTL here: one function only, everything inside `transform()` (no
`__DEVICE__` helpers); no `__CONSTANT__` at file scope (use `const float`
locals); no `DCTLUI_COMBO_BOX` (only `DCTLUI_SLIDER_FLOAT`, `DCTLUI_CHECK_BOX`
and `DCTLUI_VALUE_BOX` are proven; combo-box display names are expanded as
code, so a hyphen within one is read as an operator); ASCII only, no tabs,
`if/else` in preference to ternaries. `dctl/dctl_shim.c` compiles a Transform
DCTL as plain C and catches signature errors, undefined identifiers and faulty
arithmetic, not Resolve-specific macro faults:

```
sed "s|DCTL_UNDER_TEST|$PWD/dctl/output/Print Adjustment.dctl|" dctl/dctl_shim.c > /tmp/shim.c
cc -std=c99 -o /tmp/shim /tmp/shim.c -lm && /tmp/shim
```

#### Second RA-4 paper: Fujicolor Pro Laser TYPE II

`fuji_print_engine.py` is a preset differing from `EnduraPrintEngine` only in
`print_medium_path`. Two Fujifilm papers are traced; Crystal Archive Type CA
cannot drive the engine because its datasheet publishes no characteristic
curves (its "Calibration data" section is Frontier minilab setup), so
`CrystalArchiveTypeCA_paper.json` is reference data only. Measured on the
metrics used for Endura, a neutral ramp through each engine's calibrated
path, Portra 400 and Fujicolor 100 negatives respectively:

| | Endura Premier | Fuji Pro Laser II |
|---|---|---|
| printable window (Dnorm k) | **[0.082, 0.348]** | **[0.036, 0.364]** |
| system gamma over the window | 3.034 | 2.468 |
| neutral input k landing Y = 0.18 | 0.221 | 0.221 |
| gray-axis lock, mean correction per layer C/M/Y (logE) | +0.44 / +0.06 / −0.13 | +1.45 / +0.85 / +0.56, relative-axis origin folded in |
| gray-axis lock, range of correction over the window C/M/Y (logE) | 0.12 / 0.13 / 0.65 | 0.15 / 0.20 / 0.44 |
| outside P3 pre-clip | 27.0% | 13.5% |
| neutral-scale Status A solve, max residual | 4 × 10⁻¹⁶ D | 1.1 × 10⁻⁴ D |
| gray-lock solve residual | not tabulated | RMS 0.030, max 0.131 D |
| serialised 65³ interpolation RMSE / max (P3) | 2.3e-3 / 8.9e-2 | 1.8e-3 / 6.8e-2 |
| serialised 65³ interpolation RMSE / max (PQ) | 4.0e-3 / 1.5e-1 | 3.3e-3 / 1.1e-1 |
| serialised node quantisation (P3 / PQ) | 2.7e-7 / 2.8e-7 | 3.1e-7 / 3.2e-7 |

CAVEATS, recorded in the engine's docstring and the cube headers:

1. **Laser paper rendered through a tungsten enlarger.** Pro Laser TYPE II is
   a Frontier minilab paper: its H&D curves were measured under narrowband
   laser exposure and its sensitisation is laser-tuned, whereas it is rendered
   through the default 3200 K enlarger, `enlarger_K` left unchanged so that
   the two papers remain comparable. The Frontier scans and applies
   proprietary processing before driving its lasers, so the printer half is
   not modelable; a laser-line kernel through the negative would model an RGB
   narrowband enlarger head. Quantified: 3200 K against laser lines, same
   paper and lock, over the printable band ±0.12 Dnorm off-neutral, mean ΔE00
   2.2–3.1, p95 6–7, worst 11–19, neutral ramp shifts up to 1.8; which laser
   triple matters far less (685 versus 670 nm red, mean 0.3–0.5; 473/532/685
   versus 470/530/650, mean 0.9–1.6). The better route is an optical Fujifilm
   paper sheet with characteristic curves, which Type CA lacks.
2. **Relative exposure axes.** The datasheet prints no absolute logH origin:
   the H&D abscissa is a 0.5-decade lattice and the sensitivity ordinate a
   1.0-decade lattice with arbitrary zeros. Harmless here: a global shift
   passes through `inv_hd` into the lock's exposure offset `o` and cancels,
   and a global sensitivity offset scales all three layers equally into the
   same constant. The lock's solved offsets, `o = [1.4560, 0.8840, 0.8120]` on
   Fujifilm 400, have the arbitrary origin folded in and are not comparable
   with Endura's.
3. The datasheet labels its densities **"Status A equivalent"** (ステータスA相当).
4. **Deep Matte is excluded**, the datasheet stating that its characteristic
   curves do not apply to that surface.
5. **This is not the intended paper.** Both Fujifilm JSONs record that the
   target was the darkroom cut-sheet Pro-G / Pro-L, for which no standalone
   optical datasheet was found; Pro Laser TYPE II is the closest same-family
   relative.
6. No physical print has been measured against the path, and the validation
   battery is Endura-specific.

### C-41 fleet discrimination gap: the most important caveat in this document

**The pipeline cannot reliably distinguish its twelve C-41 stocks from one
another.** The limitation is structural and bounds what every C-41 deliverable
may be claimed to do. Ground truth the datasheets cannot supply shows it: the
user reports Ektar 100 as a very different stock from the Portras, scanned and
printed, whereas the model reads Ektar as one of the *closest* stocks to
Portra 400, and fleet size does not resolve the discrepancy.

**The measurement**, from `engine/c41/c41_stock_compare.py` over all 66
pairs: inter-stock spectral shape distances span **0.021–0.220 D** and the
basis sensitivity of the surrogate decomposition is **0.034–0.063 D**. Below
approximately 0.063 D the model cannot distinguish a genuine film difference
from an artefact of the assumed basis, which is the case for 20 of the 66
pairs. The closest pairs, all inside the ambiguity band:

| pair | shape distance (D) |
|---|---|
| Fujifilm 200 / Fujifilm 400 | 0.0000, identical by construction, one shared dye chart |
| Portra 800 / Ultra Max 400 | 0.0206 |
| Portra 400 / Pro Image 100 | 0.0208 |
| Gold 200 / Portra 400 | 0.0244 |
| Portra 160 / Pro Image 100 | 0.0264 |
| Portra 160 / Portra 400 | 0.0271 |
| Ektar 100 / Portra 160 | 0.0305 |
| Gold 200 / Ultra Max 400 | 0.0313 |

Only the most widely separated pairs, Superia Premium 400 against most Kodak
stocks at 0.15–0.22 D, sit clear of the band.

**The cause.** Every stock's dye set is a warped Vision3 basis (register #8),
so the twelve fitted sets stay within a mean |ΔD| of 0.004–0.073 when
peak-normalised, most pairs in 0.012–0.055. `DIR_MATRIX = np.eye(3)`, so
interimage is disabled, and grain is not modelled. The two mechanisms that
make stocks look different, real dye chemistry and interimage coupling, are
precisely the two absent from this model.

**A third mechanism is present, measured, and larger than either.** The
orange mask, measured from the published D-min spectra as D-min at 440 nm
less D-min at 650 nm, spans **0.6005 D on Fujicolor 100 to 0.9467 D on
Fujifilm 200 and 400, a spread of 0.346 D**, and its spectral shape varies as
well: the ratio (B−R)/(G−R) runs from 1.414 on Portra 160 to 2.089 on
Portra 800. That spread exceeds the dye distances, the basis sensitivity and
Kodak's C-41 process-control tolerance of ±0.03–0.09 D (Z-131). The
measurement is basis-independent. The ordering is broadly coherent with
coupler chemistry: the slower professional Kodak stocks carry the weakest
masks (Portra 400 0.623, Portra 160 0.638, Ektar 100 0.652, Pro Image 100
0.700), the consumer and Fujifilm stocks among the strongest (Gold 200 0.738,
Ultra Max 400 0.753, Fujifilm 200/400 0.947), Portra 800 at 0.781 sitting
above both Kodak consumer stocks; pyrazolotriazole magenta couplers need less
yellow masking coupler than pyrazolone couplers, although no datasheet names a
coupler class. The per-stock table is in
`knowledge/dye-sets-across-the-three-processes.md` §4f.

**This propagates into the print cubes, measured.** Pairs of engines built
differing ONLY in `dmin_spec`, the gray-axis lock re-solved against each mask,
evaluated over a 25³ grid (null control: re-injecting a stock's own mask
reproduces the engine at a maximum linear-P3 difference of 0.000e+00). Four
swaps, two realistic stock pairs and two diagnostic pairs separating mask
strength from shape (per-swap table, with the fraction of the 15 625 nodes
above 1 ΔE2000, in the same note, §4f-bis):

- The gray-axis lock absorbs the mask on the neutral axis, to a maximum of
  0.131 ΔE2000 across every pair; neutral rendering is stock-independent by
  construction.
- Off the neutral axis the mask survives: for realistic pairs 13–20% of grid
  nodes differ by more than 1 ΔE2000, reaching 3.6–5.5 ΔE2000 at saturated
  colours.
- The driver is SHAPE, not strength: a swap changing strength by 0.173 D with
  almost no shape change gives 1.2% of nodes above 1 ΔE and a maximum of
  1.55; a swap changing strength by 0.009 D but shape by as much as the
  extreme pair gives 18.8% and 4.02.

**What this does and does not invalidate.** The print cubes are metrically
sound as prints and are not stock-DISCRIMINATING by their dye sets; their
per-stock MASK term does discriminate, off the neutral axis only, so a claim
that two print cubes render a saturated colour differently is supportable and
basis-independent, whereas any claim resting on neutral rendering is not.
Datasheet-level comparisons are admissible: the `char` and D-min-shape columns
of `c41_stock_compare.py` never pass through the basis. `DIR_MATRIX` is NOT
the remedy: interimage occurs during development, every cube begins after
that point (`<Stock>_StatusM.cube` is densitometry on dyes that already exist;
`endura_print_engine.py` never inverts the negative's characteristic curve nor
calls `apply_dir`), and a scanned negative already carries the effect. The
remedy is MEASURED per-layer dye data, which only colour-separation wedges on
a validation roll can supply. Supporting literature:
`knowledge/interimage-effects-and-stock-differentiation.md` (Kodak names
proprietary DIR couplers as an Ektar design element; published interimage
magnitudes run to a 10–35% gamma change; an UNVERIFIED tier-C source holds
that Kodak saturation differences are designed in by interimage rather than by
dye set, the axis this model has set to identity).

### `reversal_transform.py`: reversal cubes (D50 XYZ only)

The canonical engine for all reversal builds; D50 XYZ is the only target and
legacy build names fail loudly. The integration grid is derived per stock by
`dye_support_grid()` from measured dye support (400–710 nm for Velvia 100 and
Velvia 50, 400–719 nm for Provia, 401–700 nm for Ektachrome), so no wavelength
is modelled as clear film (register #2). The cube outputs white-relative
colorimetric density, −log10(XYZ/white), and requires `dctl/output/XYZ D50 to
DWG.dctl` after the linearisation node, which un-normalises by the D50 white,
applies a Bradford adaptation from D50 to D65 and converts XYZ to DWG in one
explicit 3×3. The engine validates the re-parsed serialised cube. `DMAX` is an
explicit per-build corridor resolved from the sensor, 5.00 sensor-free and
5.25 for the a7R III build, `--corridor` overriding both; every build prints
the corridor the stock requires at dye 4.0, probed over the corners, faces and
a coarse interior lattice of that box as well as the neutral (the maximum sits
on a corner, so the coarse probe is exact: a 33-point axis reproduces every
requirement to four decimals).

**The tracing bound is propagated as shape error.** Each reversal dye file
documents its tracing uncertainty (0.005–0.011 D, `uncertainty` field), and a
trace-budget instrument pushes three perturbation families through the
inversion and the D50 integration under the worst-of-sign-patterns
convention, all eight per-layer sign patterns for each family and the 128
combinations jointly (opposite signs are not mirror images through the
nonlinear chain of spectral integrals and inversion, so no half of them is
deduced from the other): a per-layer flat density offset at the documented
reading bound, a per-layer lateral wavelength shift, and a joint
wavelength-axis stretch. The flat offset factors out of the scanner and
observer integrals alike and contributes only 0.003–0.008 D. The shift term
carries the budget: the E100
cross-validation against the independent 100D raster finds best-fit lateral
shifts of 0.5/1.0/1.5 nm per dye between two digitisations of one emulsion,
and Provia's axis fit leaves residuals up to 1.2 nm; those bound each stock's
shift, the worst, 1.5 nm, standing as surrogate for the two Velvias. All three
families jointly give a worst-case output error of 0.040–0.179 D max and
0.008–0.015 D mean over the dye 0–2.5 box and the neutral series, Provia
100F best at 0.040 D and Velvia 50 worst at 0.179 D as the fleet's only
raster trace: the largest model-side term this branch has a measurement for,
two orders above cube serialisation. Maxima sit at sign-pattern corners;
means are representative. The figures are extrema over the perturbation
shapes tested, not a proof of the worst case over every possible shape.
A per-dye amplitude scale carries no term, the chain being invariant to
per-dye scaling.

**The one check against a sheet quantity the inverse never consumes is the
characteristic-curve closure.** The four reversal sheets' characteristic
curves are traced (Status A density against log exposure, three records, a
`_datasheet_curves.json` per stock with its own digitisation audit and
replot-on-ink figures of 100% on Ektachrome E100, Velvia 100 and Provia 100F
and 96–98% on Velvia 50, whose three dash-coded records share one bitmap; on
Velvia 50 the G and B records are drawn on one another outside the toe, and
on Provia only where they depart from R, the JSONs carrying the union in
those spans and recording where). The build subtracts the sheet's D-min per
channel in integrated density, solves the three curves together into
per-layer amount tables through the traced dyes and the Status A
responsivities, and prints the solve residual, the amount floor and
monotonicity, and the D50 a\*/b\* of the series. Register #19 records what it
found: the series render blue-green on the D50 table by up to 7.5 units of
b\*. The same pass bounds the roll anchor's base term under a surrogate tint
(register #17).

**The lattice extends beyond the reachable gamut, and the excess is projected
onto its boundary.** For a large minority of nodes no dye triple has the
node's scan density and Gauss-Newton terminates against its clip bounds.
Reachability is governed by chroma: nodes with small channel spread converge
almost without exception. The reachable proportion depends on the sensor,
because a colour filter band-limits the illuminant's spectral tails: on the
shipped sensor-free cubes at corridor 5.00 it is 41.3% on Provia 100F, 47.8%
on Velvia 100, 48.4% on Velvia 50 and 50.3% on Ektachrome E100; the a7R III
build at 5.25 reaches 67.8% to 73.5%. `project_to_reachable()` gives each
unreachable node (residual above `REACH_TOLERANCE_D`, 10^-3 D; the residual
distribution is bimodal, 58.40% of Provia's nodes at or below 10^-6 D against
58.43% at or below 10^-3 D) the dye solution of the nearest reached node, by
an exact separable distance transform over the lattice, in dye space before
the target integration, so every value written is the colorimetric density of
a colour the film can produce; reached nodes are bit-identical. The purpose is
continuity: the largest step between adjacent nodes where one is unreachable
was 0.8461 on Provia 100F and 0.7419 on Ektachrome E100 against 0.0498 and
0.0806 between reached nodes, and is 0.0623 and 0.0743 with the projection.
The projection writes values the transform did not compute, a deliberate
exception of bounded scope to hard constraint 1: an unreachable node has no
true value of any kind, so there is nothing to fabricate, and the alternative
is the arbitrary point at which a clipped iteration stopped. No plausible
input reaches the region: sampling 40,000 dye triples per build, 0.00% land in
a trilinear cell containing an unreachable node on either reversal build, on
every C-41 stock and on the Vision3 build, and it stays 0.00% under a
per-channel anchoring offset of up to 0.2 D; at 0.4 D, 0.26% on Provia 100F,
0.18% on Ektachrome E100 and 0.01% on Fujicolor 100. The projection is
confined to the reversal path (Invariants).

**The consequence for a sensor-free build is a loss of accuracy in deep
shadow, and it is not a corridor problem.** Interpolation cells a real
transparency reaches contain projected corners once dye exceeds about 2.5.
Sampled against the full chain the shipped cubes hold to a maximum of 0.0019 D
up to dye 2.0 and 0.0123 D up to 2.5, then 0.2931 D by 3.4. Lowering the
corridor from 6.00 to 5.00 recovers roughly a factor of two at moderate
density; sweeping 4.5, 5.0, 5.5 and 6.0 shows finer node spacing offset by
clipping at the ceiling, nearly cancelling above dye 3. A camera-named build
holds RMSE 0.0003 D and a maximum of 0.0009 D across the whole range.

#### What would recover it: per-exposure filtering

The colour filter's value is that it is CHANNEL-SELECTIVE: its blue channel
suppresses 540–660 nm for the blue exposure while its red channel keeps
640 nm for the red exposure. No filter in the shared light path can do that,
because it must pass 640 nm for every exposure including the blue one. The
blue LED's spectrum carries a plateau from roughly 540 to 660 nm at 0.13% of
peak, and a dense yellow dye is transparent there, so at high yellow the blue
reading is dominated by it. Four remedies were measured and rejected:
treating the plateau as stray light (it tracks the in-band signal at a ratio
of 0.0080–0.0081 across drive levels from 5% to 100% with an additive
intercept of 0.2%, so it is real; removing it would be fabrication); more
solver iterations (14 to 60 leaves the reachable fraction at 41.34% on Provia
100F, failures at a median residual of 2.65 D); a 3×3 decoupling matrix in
the shaper (the gap is curvature, 1.10 D deviation from the best linear model
sensor-free against 0.44 D on the a7R III); and a bandpass filter in the
shared path (a triple bandpass at ±10 nm moves the reachable fraction from
40.0% to 56.6% and leaves the nonlinearity at 1.01 D).

Filtering each exposure separately is effective, since the LEDs fire
sequentially. Simulated as ideal top-hats and built through the engine:

| sensor response | nonlinearity | reachable | serialised RMSE / max |
|---|---|---|---|
| none, as shipped | 1.096 | 40.0% | 0.0203 / 0.6479 D |
| shared bandpass ±10 nm | 1.011 | 56.6% | not built |
| a7R III colour filter | 0.443 | 69.3% | 0.0003 / 0.0009 D |
| **per-exposure ±40 nm** | **0.243** | **77.0%** | **0.0003 / 0.0008 D** |
| per-exposure ±25 nm | 0.083 | 82.6% | not built |

Nonlinearity and reachability are on Provia 100F; serialised figures over dye
0–4.0. A monochrome sensor filtered per exposure outperforms a Bayer camera on
both measures. The least costly realisation filters the LEDs rather than the
sensor (nothing moves), needs no code change (the sensitivity schema carries
three curves), and is most honestly done by re-measuring
`film_scanner_SPD_combined.csv` with the filters fitted. Qualifications: a
physical filter has shoulders and recovers less than ideal top-hats; filtering
lengthens exposure; the corridor rises (Provia 100F required 5.08 D at ±40 nm).

### `raw_to_exr.py`: trichrome scans to half-float linear EXRs (PRIMARY)

A single self-contained file. Interactive by default (export folder, pixel
shift versus superpixel, the R, G, B flat frames one at a time, Enter at the
first skipping them); non-interactive through `--out-dir`, `--mode`,
`--flats R G B` or `--no-flats`, `--in-dir` and `--workers` (default 4). The
flat frames fit the vignetting model and are merged through the same pipeline
as `plain.exr`, marked `role: plain`, for the anchor tool's plain-light set.
Output is 16-bit half-float OpenEXR, ZIP-compressed, approximately 0.0002 D
precision; Resolve imports it verbatim (verified) where float32 TIFF is
unreliable. Metadata goes to the `capture_metadata` EXR header attribute; no
EXIF, colour space attribute or ICC profile is emitted. A process pool across
triplets, four workers at approximately 2.5 GB each on full-resolution
pixel-shift frames, and one batched exiftool call; decode and flat-gain paths
avoid float64. Output is verified pixel- and metadata-identical to the serial
reference on synthetic and real frames.

**Input is routed by what LibRaw reports, not by extension.** A
two-dimensional raw image is a single-shot mosaic (superpixel mode); a stack
of planes is a pixel-shift composite (pixel-shift mode). Accepted extensions:
`.dng`, `.arw`, `.arq`, `.cr2`, `.cr3`, `.nef`, `.nrw` and `.raf`, plus RGB
TIFF on the pixel-shift path. The superpixel decoder takes mosaic, colour
filter pattern and levels from LibRaw and is manufacturer-independent: verified
against real Canon CR3 and CR2, Nikon NEF (Z f, D850), Pentax DNG and Fujifilm
GFX 100 RAF (16-bit lossless-compressed; correlation 1.000000 per channel at
unit scale with LibRaw's own half-size render), with Canon, Nikon and GFX 100
triplets producing correct EXRs end to end. Each green site is black-corrected
with its own level (LibRaw publishes one per colour index; one level for both
would bias any camera whose levels differ). The ARQ decode is verified against
a real a7R III file: channels correlate 1.0000, 0.9998 and 1.0000 with
LibRaw's decode against 0.9603 to 0.9819 off-diagonal, at a per-channel scale
of 1.000, which establishes the plane order R, G1, B, G2. Two kinds of file are refused:
X-Trans (6×6 pattern, on which 2×2 binning has no meaning; verified against a
real X-T2 RAF) and Canon sRAW/mRAW, which LibRaw reports as a stack like a
pixel-shift composite but which carry subsampled chroma, identified by
declaring three colours across four planes. Canon writes no pixel-shift raw
(the EOS R5's High Resolution Shot emits a 400 MP JPEG; the R5 Mark II
withdrew the mode); Nikon merges in NX Studio to `.NEFX`, which LibRaw does not
read, and Adobe DNG Converter renders that as a linear DNG, accepted as a
three-plane stack but untested here.

```
python3 engine/scan/raw_to_exr.py                        # interactive
python3 engine/scan/raw_to_exr.py --mode pixelshift --no-flats --in-dir /path/to/roll
```

`mono_to_exr.py` is the companion for a sensor with no colour filter array
(README, docs/resolve.md); `decode_selftest.py` guards both converters with
17 checks against a stubbed LibRaw report and exits non-zero on failure.

### `roll_anchor_gui.py`: per-roll Dmin and Dmax anchors

One self-contained engine: the ROI-picker GUI and its numeric core, no
separate module, no headless `--roi` path. It reads nothing else in the
repository (its one repository-path read is the `builds/anchors/` save-dialog
default; `repo_root()` returns `None` rather than raising on a shallow path),
so a copy on a scanning machine is indistinguishable from an in-repository
run; its dependencies are the `exiftool` binary and the numpy, matplotlib,
rawpy, OpenEXR and tifffile packages. Nothing in it is specific to one
camera.

```
python3 engine/scan/roll_anchor_gui.py                   # fully graphical
python3 engine/scan/roll_anchor_gui.py \
    --dmin R.arw G.arw B.arw \
    --plain R.arw G.arw B.arw --dmax R.arw G.arw B.arw \
    --roll-id "V100-2026-07-A" --out builds/anchors/V100-2026-07-A.json
```

**Frame input**, per frame set, takes either three raw files in R, G, B LED
order, each read through the matching CFA plane (a colour-sensor path: a
sensor with no filter array reports one plane and its rolls are anchored from
the merged EXRs `mono_to_exr.py` writes), or one merged frame from
`raw_to_exr` as a half-float EXR, the primary route, whose embedded metadata
supplies per-channel exposure and ISO so that the anchor measures exactly the
flat-fielded data entering Resolve. A merged file lacking that metadata is
accepted as a foreign frame: exposure from the `file@1/125` override, per
channel as `file@G=1/60,B=1/30` when only some channels lack it, or the GUI's
shutter-speed prompt, which asks only for the exposures the set cannot supply
and never replaces a known one; ISO and flat-field state recorded as unknown, an
alpha channel ignored, and a warning that its EXR-scale densities are relative
to the file's own unit white. Legacy `tiff_maker` TIFFs are also read. Without
the plain-light set the anchor JSON omits the plain-light-scale densities, the
LED crosstalk matrix and the field-nonuniformity note.

**Rules.** Shutter normalisation in linear space before any logarithm;
exposure read from EXIF, `file.arw@1/30` as an override, applied to that file
alone (skipping this
corrupts a D-max reading by approximately 2.4 D; a D-max patch needs
approximately 250 times the plain-light exposure). Aperture must match across
a frame set or the tool refuses to run. ISO is recorded and never validated
against a list: density is a ratio of two frames' shutter-normalised rates, so
a sensor gain common to both cancels whatever its value, and any base ISO is
accepted; a drift within a set biases the result by the logarithm of the gain
ratio, approximately 0.8 D between ISO 100 and 640, so ISO is compared across
the set after measurement and a difference raises a warning naming the frames
(a warning, not a refusal, because only the operator knows whether a
deliberately different D-max exposure is worth the bias). Verified on
synthetic frames: identical light at ISO 64 and 6400 yields identical
densities, and a set mixing 100 with 640 returns the uncorrected ratio with
the warning. D-max is diagnostic only, never a rescaling reference.

**ROI.** The default is the central 50% of each axis (25% of area,
approximately 10.5 Mpx on the a7R III, 2.6 Mpx per CFA plane). The box is
chosen with the picker (drag, Central 50%, Reuse previous), and the effective
pixel box is recorded per channel in the JSON. Statistics are trimmed to the
1st to 99th percentile, and a bimodality check (dip test plus two-cluster
separation over the trimmed values) warns when the ROI contains a second
population, a film box or gate edge; on synthetic tests a 20% contamination
corrupts D-min from 0.121 to 0.184 D and triggers the warning. Previews are
log- or gamma-scaled for display only, a rebate patch being approximately 4 D
down; the selection maps back to raw pixel coordinates.

**GUI.** With no arguments, native tkinter dialogs ask whether the frames are
merged files or raw captures (collected one channel at a time, R then G then
B, so selection order cannot scramble the assignment), whether a plain-light
set and a D-max set are to be measured, the roll ID (dated default) and where
to save the JSON (default `builds/anchors/<roll-id>.json`); then one
ROI-picker window per frame set (matplotlib `RectangleSelector`, ~40 lines):
log-scaled preview of the R-lit capture, drag, live per-channel histogram
with the bimodality verdict, each channel read from the capture and CFA plane
the extraction measures (R from the R-lit file, G from the G-lit, B from the
B-lit), live raw-pixel coordinate readout, Reuse previous / Central 50% /
Confirm, a reused box being re-validated against the new frame and falling
back to the central 50% if it does not fit. Shutter speed is asked only for
the files, or the merged frame's channels, whose exposure is unreadable
(enter a denominator, "125" = 1/125 s, or seconds with an s suffix); known
exposures are never replaced. The result dialog shows the
three D-min slider values, matching the slider names and 0.001 step of
`RollAnchor_ScanPrep.dctl` verbatim and copied to the clipboard, D-max marked
"diagnostic only", any warnings, and the JSON path. Passing the frame
arguments skips the file dialogs but still opens the pickers. The ROI is per
frame, because the plain-light, leader and rebate exposures will not frame
identically.

**Status.** Numeric core verified on synthetic frames (D-min ±0.0003 D, D-max
±0.0001 D at 4.31 D), including the ISO-independence and ISO-drift cases; the
merged-frame path validated on real a7R III captures, producing anchors
identical to the TIFF path; the GUI verified headlessly (construction and
wiring of selector, buttons and histogram). Real film frames and the rawpy
ARW decode path, including a7R III PDAF rows and black level, have never run
on a real file (register #6).

### `adx_engine.py`

The ECN-2 branch's primary, ADX16 route, and the only route by which the ADX16
cube is regenerated. It reads `data/equipment/film_scanner_SPD_combined.csv`,
`data/films/Vision3_dye_density.json` (the family dye basis and the
family-average Minimum Density curve), `data/standards/APD_ST2065-2.json`,
`RP180_responsivities.json` for the comparison line, and the four per-stock
dye JSONs for the neutral-axis and family-mask checks; it writes and validates
`builds/ecn2/Vision3 to ADX16.cube` at DMAX 3.30, load-bearing across cube and
`Preshaper 3.3.dctl`. Its scan side is the LED, times the sensor when one is
named, filtered by the family-average Minimum Density curve (register #17;
the mask shifts the LED centroids by 0.5, 4.1 and 5.4 nm in R, G and B), and
its output is `APD(mask + dye) − APD(mask)`, the quantity ST 2065-3 encodes.

Self-report: a working-range corridor probe (dye 0–2.2 reaches scan density
2.18 of the 3.30 corridor, 66% occupancy); the serialised-cube probe, RMSE
0.0006 / max 0.0129 D in APD over the working range; an ADX16 code-range
check, no clipping over the lattice, where ADX10 would clip 16.2% of
working-range probes, which is why ADX16 is the only supported target; a
neutral-axis check per stock that reads the stock's traced midscale and its
own traced mask with the BARE LEDs, anchors one against the other as the DCTL
does, unmixes through the family model and compares the encoded value with
the direct `APD(midscale) − APD(mask)`, closing within 0.012 D on every stock;
a family-mask bound per stock, the stock's own mask on the film against the
family mask in the cube over the working box, 0.001–0.012 D mean and up to
0.089 D in APD; and an APD-versus-RP 180 comparison on the same dye stacks,
agreeing in the mean to 0.03 D and at most 0.24 D per channel.
`adx_validate.py` scores the full chain through the Academy decode against
the scene engine's truth and prints the route's accuracy bound per stock. Its
printer-light column adds per-channel APD trims to the encoded code values
before the decode, the operation `Printer Lights ADX16.dctl` performs, solved
so the decoded 18% grey lands at AP0 0.18 on each channel; a per-channel gain
on the decoded AP0 is printed beside it as a separately named comparison
only, being a different operation through the decode's matrices and curve,
and departs from the trim chain by up to 3.1 ΔE2000 on 250D.

`annexc_check.py` is the one comparison in the ECN-2 chain against a quantity
measured outside this repository. The Academy's S-2008-002 Annex C fitted a
Status M to APD matrix per stock on 97 spectrally measured patches, 5207 and
5219 among them, and published the residuals. The script solves each stock's
per-layer dye amounts from all three characteristic curves at once, integrates
the same amounts against the Status M and ST 2065-2 tables, and compares the
spectral APD with the Academy's matrix along the traced neutral series, on the
stock's own basis and on the family basis the cube reads through. The pass
statistic is the worst per-channel mean absolute error over the series, the
statistic the document publishes per stock ("mean abs error") and the one its
0.02 D expected error refers to: 0.018 D on the stocks' own bases (per-channel
0.001–0.018 D), which passes, and 0.024 D on the family basis, which does not
and is reported beside it. A signed mean would let alternating errors cancel
into a pass, so it is printed only as the bias figure, 0.018 D on the own
basis, where every red residual shares one sign and the two coincide, and
0.024 D on the family basis; the pointwise maximum, 0.035 D own and 0.037 D
family, is printed as the tail and not gated, the document's own maximum
being over 97 patches rather than a traced neutral series. A FAIL on the gate
is a nonzero exit status, not a printed word. Blue agrees within 0.005 D
throughout; green within 0.005 D below 2.1 D and up to 0.037 D at the
shoulder, where the Academy's own linear fit misfits green by 0.032–0.053 D;
red carries a constant offset of opposite sign per stock, present at D-min and
equal to the traced mask's disagreement with the sheet's red D-min, so it is
bounded by the mask trace rather than the dye model. The comparison tests the
dye spectra, the mask and the two responsivity tables; it does not reach the
scan side, and the Status M table sits on both sides of it, so a common error
there would cancel. `knowledge/academy-printing-density-and-the-adx-unbuild.md`
§4 carries the method, the matrices and the caveats.

A trace-budget instrument (not distributed) propagates four perturbation
families into RP 180 printing density over the dye 0–2.2 box and the neutral
series, RP 180 being the predecessor metric whose responsivities sit on the
same steep dye flanks; every per-layer family is worst-cased over all eight
sign patterns and the joint term over the 128 combinations, opposite signs
not being mirror images through the nonlinear chain. A wavelength-flat
per-layer offset at the basis's inter-stock spread (median 0.021–0.031 D per
dye, the family traces' measured disagreement) gives 0.012–0.013 mean /
0.050 D max on the neutral series and 0.064 D over the box, the reading-error
floor, structurally unable to alter the metamerism between the scanner's view
and the RP 180 view. The real
perturbation, each stock's own trace as the film against the family-average
knowledge, costs 0.002–0.007 D mean and at most 0.036 D, so the family
averaging is confirmed in output space. What the spread cannot see is a
digitisation bias common to all four traces (one digitiser, one method, one
chart class), and the Vision3 record carries no axis calibration to bound one
with; under surrogate bounds taken from the repository's traced-chart record
(±1.5 nm per-layer lateral shift, 0.4% axis stretch) the shift term reaches
0.048–0.054 D mean / 0.39 D max, and the three synthetic families jointly
0.072–0.080 mean / 0.51 D max, the branch's largest model-side exposure,
bounded by surrogate rather than by measurement, and an extremum over the
shapes tested rather than over every possible shape. A second independent
Vision3 source would convert the surrogate into a measurement.

Two authoring hazards of per-stock scripts: a copied engine can keep the
source stock's output filename and silently overwrite the first stock's cube;
and `DMAX` must be explicit and correct in every build script (a corridor
choice, never the film's physical D-max, since narrowband scan density exceeds
the film's Status A density; if a regenerated cube does not match the shipped
one, check this constant first).

### `v3_scene_engine.py`

The ECN-2 branch's secondary, scene-referred path and its only per-stock
engine: `v3_scene_engine.py --stock {50D,200T,250D,500T}` builds
`Vision3 <Stock> to Scene DWG.cube` under `builds/ecn2/`, scanner density to
scene-linear DaVinci Wide Gamut (D65), unclamped, reading the LED SPD, the
stock's own `Vision3_<Stock>_dye_density.json`, `_datasheet_curves.json` and
`_spectral_sensitivity.json`, `StatusM_ISO5-3.json`, `CIE1931_2deg_CMFs.json`
and the reflectance sets. The cube chains at exactly the ADX16 cube's input
point (normalised scanner density, OD/3.30, D-min excluded, behind the same
3.3 preshaper). Per lattice node:

1. de-normalise to scanner density;
2. Gauss–Newton unmix through Φ (scanner SPD × sensor response, unity under
   `--sensor none`, × 10^−Dmin(λ), the stock's own traced Minimum Density
   curve, register #17) to image-dye amounts, on the stock's OWN traced dye
   set (the family average serves only the stock-blind ADX16 route);
3. per layer, look the amount up on that layer's neutral-scale table, amount
   against logH on the sheet's shared exposure axis. The tables are solved
   from all three characteristic curves at once, the sheet's curves being
   Status M INTEGRAL densities of one neutral exposure series in which each
   channel carries the other two layers' unwanted absorption (the
   off-diagonal terms of the unit-peak dyes' Status M matrix run 0.03–0.13 of
   the diagonal); only the amount triple whose dye stack, over the traced
   mask, reproduces all three curves at a given logH is the sheet's neutral.
   The solve closes to machine precision on every stock; with the traced mask
   under the dyes no point of the 50D, 200T or 500T tables needs a negative
   amount, and on 250D 12.7% of the toe does, because the traced mask's
   Status M red exceeds the sheet's own D-min red by 0.031 D, the small
   negative amounts being kept. Reading one channel's curve as one layer's
   would place the three layers' exposures 0.09–0.22 logH apart at midscale
   and up to 0.44 logH apart at +1.5 stops on a neutral that satisfies the
   sheet, a cast the neutral ramp cannot see. Each table is made strictly
   increasing by a reverse-scan running minimum keeping the last point of
   each tie run (0–5 points dropped per layer). The forward model extends
   each table by its terminal slope; the inverse lookup, amount to logH,
   clamps at both ends of the table (Rule 4: past the shoulder the inverse
   slope is enormous, and a small overshoot in amount would read as many
   stops of invented exposure). Forward and inverse therefore agree only
   within the published span, and the build asserts the clamp at both ends
   of every table;
4. relative layer exposure L = 10^(logH − logH_mid). logH_mid comes from the
   traced midscale-neutral curve: Status M integrated over its measured
   support only, responsivities renormalised on that support, char-inverted
   per channel and averaged (per-channel spread 0.026–0.103 logH). The
   sheet's camera-stops zero is printed as a cross-check and not used; it
   differs by 0.067–0.404 logH, a uniform per-stock exposure trim, never a
   colour error;
5. a 3×3, weighted least squares over 3,282 measured reflectances
   (ColorChecker 24, Munsell glossy and matt, Agfa IT8.7/2, NIST skin)
   illuminated by the stock's balance illuminant (D55 for 50D/250D, a 3200 K
   blackbody for 200T/500T), Bradford-adapted to D65, with an exact grey-row
   normalisation so that the midscale neutral lands on Y = 0.18, maps L to
   XYZ (D65);
6. XYZ (D65) to DWG linear through the standard DaVinci Wide Gamut matrix.

The colorimetric grid runs 380–730 nm, truncating 21 nm of traced 50D
yellow-layer toe below 380 nm rather than synthesising reflectance data to
integrate against it.

Self-report across the four stocks: ColorChecker matrix residual 2.23–2.78
ΔE2000 mean, maxima 6.83–7.34 on the red patch, the metameric floor; the
traced mask's Status M against the sheet's D-min triplet within 0.045 D on
every channel of every stock; the neutral amount tables closing on all three
characteristic curves to 4 × 10⁻¹⁶ D, midscale amounts 0.54–0.75 per layer;
the neutral exposure ramp exact from 1.5 decades below logH_mid to 2 above
on every stock, and at 2 below on 200T and 500T, while on 50D and 250D that
point lies below the published toe (their tables begin 1.59 and 1.95 decades
below logH_mid) and reads the toe clamp, Y/Y₀ 0.026 and 0.011 against 0.010;
corridor
requirement 1.87–2.02 D against DMAX 3.30, 63–76% headroom; node solve on the
65–66% of nodes inside the dye box mean 0.013–0.020 D, above 0.02 D on
1.7–2.9% of them, the remainder being density combinations no dye stack
reaches (a smaller reachable share than the bare LED gave, because the mask
raises the blue LED's long-wavelength tail); no lattice node negative in DWG;
serialised round trip at 2 × 10⁻⁷. The ColorChecker "full chain" line is a
plumbing check: forward model and inverse chain share machinery, so the figure
collapses to the matrix-only residual. The table solve closes on the same
three curves it was solved from, so its closure is a consistency check on the
solve, not independent evidence for the fitted curves or for off-neutral
behaviour; the sheet quantity the inverse never consumes is the D-min triplet
of the characteristic sheet, compared with the traced mask's Status M above,
and the branch's one comparison against a quantity measured outside the
repository is the Annex C check.

The route's characteristic cost is interpolation: the output is exponential in
the input on a lattice uniform in density, so a trilinear probe against the
exact chain gives, within each stock's published characteristic span (per
layer, the top of its neutral table, dye 0–1.68 to 0–2.02), a mean relative
error of 2.2–2.6% with a 99th percentile of 12–15% and a maximum of 23–53%;
over the full dye 0–2.2 working range the mean is 1.8–2.3% and the maximum
23–54%, the clamp bounding what any node beyond a table's end can carry. The
build separates that figure by lattice cell. A cell is clean when all eight corner nodes converged to within
0.001 D and every layer's amount at every corner lies within both ends of
its neutral table; any other cell carries a corner value clamped at a
table's end, at the toe or the shoulder, or from an unconverged node, and
its error is not an interpolation figure. Clean cells
hold 80–85% of the span's samples at 2.1–2.5% mean, 10–12% at the 99th
percentile and 19–23% maximum; the remaining 15–20% run 4.5–5.3% mean, 16–22%
at the 99th percentile and 21–53% maximum. The cells that produce those
maxima straddle the top of a layer's published curve, where the amount table
is nearly flat and the inverse steepens; the clamp caps the exposure a corner
beyond the table can carry, so no cell interpolates between a published
exposure and an invented one. Two distinct quantities meet there. The
lattice's disagreement with its own engine is a numerical approximation error
and is reducible by finer sampling. What is not reducible is the model's
sensitivity itself, since on the
shoulder a small change in density is a large change in exposure, so the
same steepness amplifies every measurement and model error in the input;
a finer lattice would track the engine more closely there without making
the recovered exposure more trustworthy. The build
declares an operating region, clean cells below a hundred times mid-grey,
covering 74–81% of the span's samples at 2.1–2.3% mean, 10–11% at the 99th
percentile and 17–21% maximum; within it, by exact-chain luminance, the
mean is 1.0–1.2% below mid-grey, 1.6–1.8% from mid-grey to ten times it and
2.8–3.2% to a hundred times it. The camera-named builds reach 83–88% clean
cells and hold the declared region at 1.3–1.5% mean, 5–7% at the 99th
percentile and 8–14% maximum. The probe is trilinear, on 5,000 fixed-seed
dye states drawn uniformly over each range, and its coverage figures describe
that synthetic probe, not the usable fraction of real photographs; Resolve's
tetrahedral interpolation is not probed.
## Current state by stock

**Reversal (E-6).** Target D50 XYZ, corridor DMAX 5.00, 65³. All four stocks
are complete, built on integration grids derived from measured dye support
(register #2), with an exact white point. Accuracy falls with transparency
density because a sensor-free build cannot resolve the densest and most
saturated states the film reaches (register #9); the ranges span the four
stocks, Velvia 50 the worst throughout and Ektachrome E100 the best:

| dye up to | RMSE | maximum |
|---|---|---|
| 2.0 | 0.0003 | 0.0019 |
| 2.5 | 0.0003–0.0004 | 0.0123 |
| 3.0 | 0.0005–0.0015 | 0.0818 |
| 3.4 | 0.0016–0.0051 | 0.2931 |

A build named to a specific camera does not degrade in this way, holding RMSE
0.0003 D and a maximum of 0.0009 D across the whole range.

| Stock | Cube |
|---|---|
| Velvia 100 | `V100_XYZ_D50.cube` |
| Velvia 50 | `V50_XYZ_D50.cube` |
| Provia 100F | `Provia100F_XYZ_D50.cube` |
| Ektachrome E100/100D | `E100_XYZ_D50.cube` |

All reversal builds use narrowband illumination.

**Negative, ECN-2 (Vision3).** Corridor DMAX 3.3. Two delivery routes fork at
the same input point (normalised scanner density, D-min excluded). The
primary, ADX16 route is `Vision3 to ADX16.cube` behind the 3.3 pre-shaper: one
table for the family on the shared dye basis, read through the family-average
traced mask. Its node solve leaves a mean residual of 0.3955 D, above 0.02 on
36.8% of nodes, on the same sensor-free basis as the C-41 fleet and with the
same qualification (the mask raises the blue LED's tail, register #17); the
65³ interpolation RMSE over the working range is 0.0006 D with a maximum of
0.0129 D, matched by the serialised round trip. The secondary, scene-referred
route is per stock: `Vision3 <Stock> to Scene DWG.cube` decodes through the
stock's own traced dye set, characteristic curves and spectral sensitivities
to scene-linear DaVinci Wide Gamut (D65), its 3×3 fitted on measured
reflectances under the stock's balance illuminant (D55 daylight, 3200 K
tungsten) and Bradford-adapted. ColorChecker matrix residuals are 2.23–2.78
dE2000 mean with maxima of 6.83–7.34 on the red patch, the same metameric
floor as the C-41 scene machinery; the neutral exposure ramp is exact over
±2 stops with chroma error at the numeric floor; the per-layer amount tables
reproduce all three published characteristic curves at once over the stock's
traced mask; the corridor requirement is 1.87–2.02 D against 3.30; and within
each stock's published characteristic span the serialised table tracks the
exact chain at 3.5–5.0% mean relative error under trilinear interpolation,
2.1–2.5% over the 80–85% of samples whose lattice cell is clean, with the
92–449% maxima confined to cells that straddle the top of a layer's
published curve, where the exact chain itself steepens without limit. The mid-grey
anchor is the traced midscale-neutral curve inverted through the
characteristic curves (per-channel spread 0.026–0.103 logH); the sheets'
camera-stops zero differs from it by 0.067–0.404 logH, a uniform per-stock
exposure trim reported as a cross-check only.

**Negative, C-41: the fleet is complete at twelve stocks**, corridor DMAX 3.3,
all built from datasheets alone. No per-layer dye data is published for any of
them, so the per-layer split is inferred (register #8). Every stock has a
`<Stock>_StatusM.cube` and a print emulation paired by manufacturer. **None of
the twelve has a measured validation**, which is the open gate on the whole
family.

| Stock | Print branch | Node-solve residual (mean D, % nodes >0.02) | 65³ probe over dye 0–2.2 (RMSE / max D) |
|---|---|---|---|
| Superia Premium 400 [JP] | `print_fuji/` | 0.3530 · 31.7%, best of the fleet | 0.0004 / 0.0073 |
| Fujicolor 100 [JP] | `print_fuji/` | 0.3609 · 34.3% | 0.0004 / 0.0075 |
| Portra 160 | `print_endura/` | 0.3835 · 41.8% | 0.0005 / 0.0070 |
| Gold 200 | `print_endura/` | 0.3869 · 38.8% | 0.0006 / 0.0135 |
| Ektar 100 | `print_endura/` | 0.3903 · 35.5% | 0.0005 / 0.0100 |
| Ultra Max 400 | `print_endura/` | 0.3951 · 39.7% | 0.0006 / 0.0137 |
| Portra 400 | `print_endura/` | 0.4017 · 37.0% | 0.0005 / 0.0094 |
| Pro Image 100 | `print_endura/` | 0.4040 · 37.5% | 0.0006 / 0.0103 |
| Pro 400H | `print_fuji/` | 0.4119 · 36.5% | 0.0007 / 0.0142 |
| Portra 800 | `print_endura/` | 0.4240 · 39.0% | 0.0007 / 0.0121 |
| Fujifilm 400 | `print_fuji/` | 0.5654 · 66.9%, least confident | 0.0014 / 0.0302 |
| Fujifilm 200 | `print_fuji/` | 0.5654 · 66.9%, identical to Fujifilm 400 | 0.0014 / 0.0302 |

**The node-solve residual is not the accuracy of the cube.** It is a mean over
the whole lattice, most of which lies outside the gamut any dye triple can
produce; dropping the colour filter widens each channel's effective sampling
band and enlarges that unreachable region, and reading the LEDs through the
orange mask, as the cube must (register #17), enlarges it further, since the
mask passes red so much better than blue that the blue LED's long-wavelength
plateau gains about four times its bare weight and the blue channel saturates
under a dense yellow dye inside the corridor. Over the density range a colour
negative occupies the cubes are little affected: the 65³ probe over dye 0–2.2
tabulated above is RMSE 0.0004–0.0014 D with maxima of 0.007–0.030 D, and the
serialised round trip matches it. Over the whole declared corridor the same
probe reaches 0.006–0.16 D RMSE and up to 3.1 D, the excess sitting where the
sensor-free blue channel has saturated; a colour filter removes that plateau,
so the figure belongs to the unity response rather than to the film. Two
caveats travel with the table. Fujifilm 200 and Fujifilm 400 carry identical
values in every shipped artifact because they share one dye chart, as recorded
under Deliverables, so their agreement at 0.0000 D is a statement about the
artwork rather than about the emulsions. And the fleet as a whole cannot
distinguish its stocks (see [C-41 fleet discrimination
gap](#c-41-fleet-discrimination-gap-the-most-important-caveat-in-this-document)),
so the per-stock ranking reports fit quality rather than a demonstrated
difference between stocks.

### Deliverables currently in the repo

```
builds/reversal/   engine-generated, regenerable via engine/reversal/reversal_transform.py;
                   all narrowband, DMAX 5.0, 65^3
  V100_XYZ_D50.cube, V50_XYZ_D50.cube, Provia100F_XYZ_D50.cube
                                 D50 colorimetric variants on dye-support-derived
                                 grids (register #2)
  E100_XYZ_D50.cube              Ektachrome E100/100D; grid 401-700, the 401 floor
                                 avoiding a 1 nm clear hole that caps modelled blue
                                 density at 3.41 D
                                 All four: white point exact; accuracy by dye range
                                 under "Current state by stock"; 49.7% to 58.7% of
                                 nodes lie outside the dye gamut and hold a
                                 projected value

builds/ecn2/
  Vision3 to ADX16.cube          the primary route into ACES: Vision3 -> ADX16 code
                                 values over Academy Printing Density, DMAX 3.3
  Vision3 <Stock> to Scene DWG.cube
                                 the secondary, scene-referred route, per stock
                                 (50D, 200T, 250D, 500T): scanner density ->
                                 scene-linear DaVinci Wide Gamut (D65), DMAX 3.3,
                                 output unclamped; same input point as the ADX16 cube

builds/c41/   fleet complete at twelve stocks; regenerable via engine/c41/ with --stock
  <Stock>_StatusM.cube           NEGATIVE BRANCH, one per stock at the root:
                                 scanner density -> Status M density (D-min excluded;
                                 corridor 3.30). The FRONT of the chain, not an
                                 output: both print branches and the Print
                                 Adjustment DCTL consume it
  print_endura/                  PRINT BRANCH, split by paper so the pairing rule is
                                 visible on disk. Portra400, Portra160, Ektar100,
                                 Gold200, Ultramax400, ProImage100 (Kodak Endura
                                 Premier RA-4, datasheet E-4070)
  print_fuji/                    Fujifilm400, Fujifilm200, Fujicolor100,
                                 SuperiaPremium400, Pro400H (Fujicolor Professional
                                 Paper Pro Laser TYPE II)
                                 Each stock contributes a DisplayP3 / P3D65_PQ203
                                 pair, 22 print cubes in total

dctl/     hand-written, in prep|shapers|output subfolders; the engine generates no DCTLs
dctl/prep/
  RollAnchor_ScanPrep.dctl       per-roll Dmin anchoring (see Per-roll anchoring)
dctl/shapers/
  Preshaper 5.0.dctl             reversal corridor, sensor-free (shipped):
                                 clamp(-log10(linear),0,5.0)/5.0
  Postshaper 5.0.dctl            x 5.0 back to density
  Preshaper 5.25.dctl            reversal corridor for the a7R III build; an example
  Postshaper 5.25.dctl           of a per-camera corridor, not a general Bayer constant
  Preshaper 3.3.dctl             negative-path preshaper: linear -> per-channel Dmin
                                 anchor (LINEAR value boxes, see note) -> -log10 ->
                                 /3.30 -> clamp [0,1]; Diag mode passes raw scanner
                                 density for scope checks
dctl/output/
  XYZ D50 to DWG.dctl            D50-route matrix node: the cube's white-relative XYZ
                                 is NOT true CIE XYZ (film base = 1,1,1), so Resolve's
                                 CST cannot convert it regardless of its
                                 white-adaptation checkbox. One explicit 3x3:
                                 un-normalise by D50 white -> Bradford D50->D65 ->
                                 XYZ->DWG. Base white lands on DWG neutral exactly
  Density to Linear.dctl         10^-D view/linearisation plus AESTHETIC density trims
                                 (master/RGB offsets, output gain). Generic 10^-D: it
                                 serves the D50 XYZ chain too, with trims at defaults
                                 there, because aesthetic adjustments belong after the
                                 XYZ D50 to DWG matrix node rather than on XYZ channels
  Printer Lights ADX16.dctl      ECN-2 aesthetic per-channel density trims, after the
                                 ADX16 cube and before the Academy decode; sliders read
                                 in APD, the ST 2065-3 k factors applied inside
  Print Adjustment.dctl          BEFORE any print-emulation cube (after StatusM,
                                 before the print cube). Operates on normalised
                                 Status M density: gamma about a pivot plus gain as a
                                 density offset (darkroom mode), or a literal
                                 gain*k^gamma, plus per-channel density offsets acting
                                 as printer lights. Paper-agnostic; only Pivot is
                                 paper-specific (0.22 = Endura's mid-gray). Defaults
                                 no-op; see "Darkroom controls"
```

The 4.5 and 6.0 corridor shaper pairs are unpublished and kept out
of `dctl/shapers/` so that neither can be picked by accident; they serve only
to reprocess cubes built on those corridors.

**Shipped total:** 12 Status M cubes + 24 print cubes + 4 reversal cubes +
1 Vision3 ADX16 cube + 4 Vision3 scene cubes = 45 .cube files from the live
engines. The release carries 46, the extra being the scene-referred
Portra400_StatusM_to_DWG.cube that the unpublished scene-referred engine
produces, alongside cube_manifest.json. Cubes are the only transform
artifacts: no analytic transform DCTL is generated on either path.

**No scene-referred landing on the C-41 path.** A colour negative is designed
to be printed, so the print branch is the sole delivery route; the producer of
a scene-referred `<Stock>_StatusM_to_DWG.cube` is the unpublished
scene-referred engine and forms no part of any shipped build. This is what
allows the fleet to be uniformly complete: Pro 400H publishes no spectral
sensitivity (Known limitations), which would have blocked a scene cube for
that stock alone. A ColorChecker "full-chain" ΔE2000 once quoted for Portra
400 is withdrawn, that harness being blind to the film model for the reason
given under register #8.

**Pairing is enforced in code.** No cross-paired cube such as
Portra400_to_FujiProLaser_* is shipped, since it would print a Kodak negative
onto Fujifilm paper. Each stock carries a `print_paper` key in
`portra_stocks.py`, and each print engine offers only the stocks matching its
own paper, so a cross-paired build is rejected by the argument parser. The key
records which paper a user would print that brand on and makes no claim about
which factory coated the film.

**Fujifilm 200 and Fujifilm 400 carry identical values in every shipped
artifact**, the Status M cube and both print cubes: all 274,625 entries of
each pair match. The files differ only in the header comment naming the
stock, so `md5` reports them as different, which is not a defect. The two
datasheets publish one shared spectral-dye-density chart, the same artwork
with identical Bezier control points, and the chain depends on the negative
only through its dye set and D-min spectrum, both of which derive from that
chart; the pair therefore cannot be compared spectrally at all, and only
their characteristic curves differ, which no shipped artifact reads. The
anomaly tracks the artwork rather than the manufacturer: the two best-fitting
stocks in the fleet are Fujifilm stocks, and the only two anomalous ones are
the two that share a chart. Their figure of 0.5654 is the deliberately
accepted cost of applying the ±25 nm shift bound uniformly rather than
damping those two stocks with a tighter bound (`portra_stocks.py`, register
#8); the densest mask in the fleet compounds it, the blue channel saturating
under yellow earliest on these two (register #17). Both Fujifilm sheets print
a RELATIVE log-sensitivity axis with no absolute origin, so any overall gain
difference derived from them is untrustworthy in absolute terms; only shape
and channel structure may be relied upon.

**The negative's H&D characteristic curves feed no shipped artifact.** The
print branch reads the curves JSON only for the D-min spectrum, at
`endura_print_engine.py:271-275`. This is correct rather than an oversight:
the print route's input is a real scan of real film, so the film's
characteristic curve is already physically present in the measured density,
and modelling it again would double-count; a scene-referred route requires
the H&D precisely because it inverts it to recover scene exposure. Within
this pipeline, choosing a "stock" means choosing a dye set together with a
D-min spectrum, the unreacted coloured coupler that constitutes the orange
cast (Glossary), not a tone curve. The characteristic curves remain digitised
as quality-control and comparison data: they constitute the basis-independent
`char` column in `c41_stock_compare.py`, which is how the Fujifilm 200 and
400 manufacture question was examined.

**DMAX 3.30 is load-bearing** across the negative cubes and the pre-shaper,
which must agree. `Preshaper 3.3.dctl` carries its own built-in Dmin boxes,
which take the LINEAR value that the clear base reads, defaulting to 1.0 to
indicate anchoring upstream; the sliders of `RollAnchor_ScanPrep.dctl`
instead take density values from the extractor. Use one mechanism or the
other and never both: with the roll-anchor node in front, leave the
preshaper's boxes at 1.0.

## Bounded systematics register (everything currently known and unpatched)

**The orange mask is a positive image, neither a filter nor a layer.** It
consists of unreacted coloured coupler distributed through the magenta- and
cyan-forming layers (Glossary); coupler is consumed wherever image dye forms,
so mask density is maximal at D-min and falls as exposure rises. See
`knowledge/orange-mask-and-the-scanning-workflow.md` and Hanson, JOSA
40(3):166, 1950. Two consequences have been traced.

- **Scan to Status M: the approximation cancels.** The per-roll D-min
  subtraction and the datasheet's midscale-minus-D-min leave the same
  effective quantity, dye minus consumed mask, and the Vision3 basis is itself
  D-min subtracted, as its `units` field states. Calibration and application
  share one convention, which is why the neutral axis emerges exact.
- **Print emulation: the approximation does not cancel, although the defect
  is narrow.** `endura_print_engine.py` builds the negative as
  `N(l) = dmin_spec(l) + sum dye*DYE(l)` (`endura_print_engine.py:476`). This
  is exact along the neutral axis: `dye = 0` gives exactly D-min, the full
  mask, and the midscale dye amounts give exactly the measured midscale; mask
  consumption being linear in the dye formed, the interpolation between them
  is correct as well. The real systematic is **off-axis mis-attribution**:
  each fitted per-layer curve carries a share of mask consumption apportioned
  at the neutral ratio, the only ratio the datasheet publishes, so at
  saturated colours the per-layer split of the consumed mask is wrong. The
  expected residual is a chroma-dependent colour drift, zero on the grey axis
  by construction and growing with saturation.

  The neutral ramp provably cannot close this. One free parameter subtracting
  mu times the stock's own measured D-min improves the aggregate fit by
  18–25% on the four clean Kodak stocks at a consistent mu of approximately
  0.14–0.20, but a flat constant vector, meaningless as a mask, fits better
  than the real D-min on every stock (Portra 400 0.00782 against 0.01054,
  Ektar 0.00714 against 0.00955, Gold 0.00669 against 0.00794, Ultra Max
  0.00755 against 0.00899), and on Portra 160 and the Fujifilm stocks the
  reversed D-min beats it outright (0.00836 against 0.01462). The improvement
  is the added degree of freedom alone; no D-min-shaped structure exists in
  the residual. A diagnostic of this kind is run against a shape-matched
  control before it is believed. Closing it requires both spectral density at
  several exposure levels and off-neutral R/G/B separation exposures for the
  per-layer attribution, the same separation wedges `DIR_MATRIX` requires;
  one shoot serves both.

  **Rejected: importing spektrafilm's representation.** Its profiles encode
  mask consumption as negative absorption within the per-layer curves; every
  negative film in that set shows negative excursions while both print papers
  are strictly positive, so the mechanism represented is real, but the
  negative bands sit under other layers' peaks (cyan negative at 440–465 and
  535–565 nm, yellow's and magenta's peaks; magenta negative at 650–750 nm,
  cyan's peak), the yellow layer is classically unmasked in C-41, and no
  red-absorbing mask exists in the magenta layer. That is the signature of
  crosstalk unmixing (its commit `feat: non-linear unmixing of status
  densities`) conflated with the physical mask. The measured aggregate used
  here, midscale minus D-min, never goes negative on any stock (minimum
  0.22–0.53 D), so nothing in this project's data compels negative per-layer
  curves.

The entries below are documented rather than fixed, in accordance with the
no-synthesised-spectra rule.

1. **380-400 nm grid truncation (Vision3/RP 180 only).** Blue printing
   density overestimated by ~0.02-0.05 D at typical yellow concentrations.
   The sub-400 nm truncation is set by the Kodak datasheet's own starting
   wavelength, and RP 180's Dmin-zeroing renormalisation likely suppresses it
   further; unmeasurable with the available rig (phosphor cuts off ~420 nm).
   Does not affect APD, whose blue responsivity carries only 0.2% of its
   integral below 400 nm against RP 180's ~3.5%.
2. **Cyan long-wavelength truncation: handled for the shipped reversal cubes;
   a bounded-observer residual remains.** The engine takes no hand-set
   `grid_stop_nm`: `dye_support_grid()` derives the integration grid from
   each stock's measured dye support (union of the three curves, floored at
   400 nm), so no wavelength inside the grid is modelled as perfectly clear
   film, the same rule the print path applies as
   `PrintConfig.neg_support_mode="truncate"`. Grids: Velvia 100 400-710,
   Velvia 50 400-710, Provia 100F 400-719, Ektachrome 401-700. A fixed
   400-730 grid would fabricate 11-20 nm of clear film on the three Fuji
   stocks, and 400-700 truncates Ektachrome. Measured cost of a fixed grid
   against a support-derived one, both scored against the correct physics
   over reachable dye states (0-3.4, 20k samples):

   | stock | fixed-grid RMSE / max | support-derived RMSE / max |
   |---|---|---|
   | Velvia 100 | 0.0133 / 0.173 D | 0.0009 / 0.003 D |
   | Velvia 50 | 0.0319 / 0.392 D | 0.0009 / 0.003 D |
   | Provia 100F | 0.0161 / 0.223 D | 0.0009 / 0.003 D |
   | Ektachrome | 0.0232 / 0.246 D | 0.0010 / 0.003 D |

   Spurious hard ceilings (X-density 3.30 D Velvia, 3.73 D Provia; Z-density
   3.41 D Ektachrome) do not arise, there being no clear-film weight to
   impose one. Deep-shadow neutral spread at dye 3.5 is 0.05 D (Ektachrome),
   0.28 D (V50), 0.39 D (Provia), 0.07 D (V100), against 0.32 / 0.78 / 0.68 /
   0.17 D on a fixed grid. Ektachrome is the diagnostic case: its dye set is
   normalised to be neutral-forming, so equal amounts should read neutral,
   and they do; the residual V50/Provia spread is real, those sets being
   unit-peak-normalised.

   *Corridor clipping is distinct from LUT resolution.* Beyond dye 4.0 on a
   4.5 corridor, V50 and Provia degrade to RMSE 0.009 / 0.017 D because at
   dye 4.0 their scan densities reach 4.91 / 5.06 D, past the ceiling:
   in-corridor samples converge with LUT size (0.0009 → 0.0002 D, 33→65,
   O(h²)) while the clipped 0.86% flatten toward a nonzero floor (0.0977 →
   0.0693), and Velvia 100, which never exceeds 4.5, shows no degradation.
   A corridor sized to the measured requirement removes it: on the a7R III
   at 5.25 both stocks sit at RMSE 0.0003 / max 0.0009 D over dye 0-4.0 with
   zero clipping. A domain-boundary artifact and an interpolation artifact
   look identical in a headline RMSE; split the samples by whether they clip.

   *The defect the support rule prevents.* Dye plots end at 710 nm (V100) /
   718-719 nm (Provia) while cyan is still substantial (0.29 / 0.59 D). A
   grid running past the edge treats the unmeasured band as clear film.
   Status A red carries ~0.02% of its weight beyond the edge, and the effect
   is nonlinear in cyan amount rather than a fixed per-unit offset (a
   "negligible, ~0.00004 D/unit" characterisation holds only below ~cyan 2.5):
   it imposes a spurious hard ceiling on modelled Status A red at exactly
   `-log10(0.0002) = 3.708 D` and, after partial cancellation with the
   scan-side red LED's own truncated tail, costs up to **0.24 D max** in deep
   shadow (dye 2.5-3.5), negligible below dye ~2, physical red reading
   higher than model. The D50 XYZ cubes would be hit harder: the X channel
   carries 0.066% (V100) / 0.034% (Provia) of its weight beyond the dye edge,
   giving ceilings of X-density 3.18 D (V100) / 3.47 D (Provia) against 3.71,
   and at a dye-3.5 neutral the clear-tail term would be 54% (V100) / 90%
   (Provia) of the modelled X signal, an X-density error reaching +0.34 D
   (V100) / +0.99 D (Provia) if the physical tail were opaque, unbounded
   above without measured tail data. Velvia 50 does not have the
   merged-baseline form of this problem, its chart drawing all three curves
   to a common frame.

   *What survives, for all four stocks:* the observer is truncated at the dye
   edge and renormalised (for Ektachrome, 0.139% of X weight and 0.048% of Y
   omitted, its chart ending at 700 nm with cyan still ~0.75 D), which
   produces no hard ceiling. The residual is a bounded bias, worst in deep
   shadow, ~0.01 D-class if the cyan tail stays edge-dense beyond the edge,
   its sign depending on the unmeasured tail's density against the in-band
   mean. Deep shadows (dye ≳2.5) are treated as qualitative; a mini-LED
   display's own deep-shadow weakness covers the same region.
3. **Not applicable: the Velvia 50 yellow reading floor.** Under broadband
   illumination yellow is indistinguishable from the baseline beyond 592 nm,
   at a plot floor of approximately 0.013 D, bounding the broadband
   red-channel error to ≤0.013 D per unit of yellow. The 640 nm narrowband
   LED renders it irrelevant. Retained so that the numbering remains stable.
4. **Not applicable: quadratic and cubic DCTL extrapolation.** Analytic
   transform DCTLs are fitted over a bounded dye range, typically 0–3,
   whereas the density clamp admits values up to DMAX. No such DCTL is
   exported. Retained so that the numbering remains stable.
5. **Reversal (5.00 or 5.25) and negative (3.3) shaper pairs are not
   interchangeable, and neither are the two reversal pairs.** One pair is
   shared across all four reversal stocks at a given corridor, and the
   corridor depends on the sensor, so a cube and its shapers are taken from
   the same build. Crossing corridors silently rescales density by their
   ratio.
6. **No Dmin/Dmax anchoring from real film frames**, for any stock. Real
   *calibration* captures have been through the merged-frame path on the
   a7R III; real *film* frames have not; the rawpy ARW decode path has never
   touched a real file, so PDAF rows and black level are unexercised there.
7. **Axis-calibration uncertainty varies by datasheet source.** Provia's
   gridlines are unevenly spaced in the source artwork (up to 1.2 nm /
   0.005 D residual after least-squares fit), datasheet drawing imprecision
   rather than a tracing error, since labels corroborate the gridlines.
   Velvia 50's chart is a 600 dpi raster requiring joint multi-track tracing.
   Registration audits for both are in their dye JSONs.
8. **Per-layer C-41 dyes are inferred rather than measured, across the whole
   chain and all twelve stocks.** No C-41 manufacturer publishes per-layer
   dye spectra, so each stock's dye set is a 9-parameter warped-Vision3-basis
   fit to the aggregate datasheet curve (C-41 toolchain). One aggregate
   spectrum cannot determine three components; that under-determination is
   the root cause of the fleet discrimination gap, and only measured
   separation wedges can close it. Stocks share the basis, so **agreement
   between two stocks is not independent validation of either**. Fit state,
   from the shipped `data/films/*_dye_density.json`:

   | stock | aggregate RMSE (D) | max (D) | cyan shift sC (nm) | decoupling cond |
   |---|---|---|---|---|
   | Portra 800 | 0.0076 | 0.0329 | **+25.00 (pinned)** | 1.4119 |
   | Ultra Max 400 | 0.0082 | 0.0456 | **+25.00 (pinned)** | 1.4146 |
   | Gold 200 | 0.0086 | 0.0408 | +24.16 | 1.4088 |
   | Ektar 100 | 0.0086 | 0.0724 | **+25.00 (pinned)** | 1.4052 |
   | Pro 400H | 0.0107 | 0.0258 | **+25.00 (pinned)** | 1.4708 |
   | Portra 400 | 0.0109 | 0.0611 | **+25.00 (pinned)** | 1.4163 |
   | Portra 160 | 0.0139 | 0.0787 | +23.75 | 1.4379 |
   | Pro Image 100 | 0.0139 | 0.1092 | +24.99 | 1.3967 |
   | Fujifilm 400 / 200 | 0.0179 | 0.0451 | **+25.00 (pinned)** | 1.6590 |
   | Superia Premium 400 | 0.0196 | 0.1479 | +19.89 | 1.4706 |
   | Fujicolor 100 | 0.0207 | 0.0846 | +15.13 | 1.4295 |

   The decoupling condition number is that of the LEDs read through each
   stock's own mask, the responsivity the cube inverts (register #17).
   Sub-effects, none closable without a measured validation roll:
   - **Every stock's cyan sits to the red of the Vision3 basis cyan**, sC
     between +15 and +25 nm; seven stocks rest exactly on the +25 nm bound
     and two more within 1 nm of it, so for nine of the twelve the value is
     the constraint rather than a fitted optimum. The fit establishes a
     direction, not a per-stock magnitude; the surviving spread belongs to
     the three stocks the bound does not reach. C-41 cyan genuinely differs
     from Vision3's, and the residual concentrates as a Status M red delta at
     midscale. The claim that it also concentrates as ΔE at saturated reds,
     citing Portra 400's worst ColorChecker patch at 6.3 ΔE2000 against a
     mean of 2.5, is unsupported: those figures come from a harness whose
     forward and inverse film stages cancel exactly, so they measure the 3×3
     fitted on the same 24 patches and nothing about the dye model, and did
     not move when a refit changed every stock's dye set. The neutral axis is
     constrained and unaffected, ramp chroma error 0.0002.
   - **The shift bound is a uniform ±25 nm on every stock** (`portra_stocks.py`),
     and it is an extrapolation guard rather than a chemistry prior. A former
     ±15 nm bound was an artefact: five stocks clipped against it at exactly
     +15.000, and a control releasing the WIDTH bound instead bought nothing;
     ±25 moves which stocks pin and how many, seven of twelve resting on
     +25.00. Refitting the fleet at ±15, ±20, ±25, ±35 and ±50 gives mean
     aggregate RMSE 0.0181, 0.0158, 0.0137, 0.0130 and 0.0130 D, so the solve
     converges by ±35. Releasing the bound that far buys 5% of residual and
     moves the modelled cyan peak to 721 nm, while the dye arrays end at
     700 nm with every stock's fitted cyan still rising there: the peak is
     already an extrapolation at ±25, and a looser bound buys fit quality
     over the measured region by making an unmeasured claim more extreme,
     which hard constraint 1 forbids. Tightening to ±20 or ±15 costs 15% and
     32% of residual and leaves the peak extrapolated regardless. What would
     place the peak is data, not a bound: the Fujifilm-family sheets publish
     spectral dye density out to 717–719 nm and the Kodak sheets to about
     703, but `GRID` stops at 700 and the digitiser discards the wider trace
     on resampling; raising the ceiling without re-digitising degrades
     measured RMSE by 500–1160% and inverts every fitted cyan shift
     (Invariants). A per-stock bound is inadmissible, since fitting stocks
     under different priors would render cross-stock comparison meaningless;
     Fujifilm 400 and 200 pin +25.00 as well, and their node-solve residual
     of 0.5654, the highest in the fleet, is the accepted cost of declining
     to damp them with a bound they alone would receive.
   - **A stock that pins more than one bound simultaneously signals
     under-determination of the basis, not a per-stock peculiarity**, and is
     read as evidence about the basis, never as a property of the emulsion.
     Fujifilm 200 and 400 pin the cyan shift and both the cyan and magenta
     widths. Ten of the twelve stocks fit against a bound, only Portra 160
     and Pro Image 100 being free of one: Ektar 100 and Ultra Max 400 pin the
     cyan shift together with the 1.15 cyan width; Portra 400, Portra 800 and
     Pro 400H pin the cyan shift; Gold 200, Fujicolor 100 and Superia Premium
     400 pin the 1.15 cyan width. That the bound binds this widely under the
     multistart solve of entry 12 is itself the under-determination. The
     engine reports every pin from the solution itself.
   - The twelve fitted dye sets lie within a mean |ΔD| of 0.004–0.073 of one
     another, most pairs in 0.012–0.055, which is why the fleet cannot
     distinguish its own stocks (discrimination gap).
   - C-41 interimage and DIR-coupler effects are unmodelled, the same class as
     the reversal caveat of entry 11, and **their magnitude relative to
     reversal film is unknown**: no source measures both by one method. The
     functional argument runs the other way: a reversal film cannot use
     coloured masking couplers, so interimage is its principal correction for
     unwanted dye absorption, and Fuji attributes the Velvia, Provia and Astia
     characters to interimage deliberately enhanced by DIR hydroquinones. The
     mechanisms differ, DIR couplers during colour development in a negative
     against iodide released during the first, black-and-white development in
     a reversal film (`knowledge/interimage-effects-and-stock-differentiation.md`
     §4a). The effects are largest off-neutral and invisible to
     datasheet-only validation. The structure exists (`DIR_MATRIX` and
     grey-ramp pre-compensation with an identity default) in
     `engine/ecn2/v3_scene_engine.py` and the unpublished scene-referred
     engine only; no file under `engine/c41/` contains a DIR stage, so the
     live C-41 branch has no interimage structure to parameterise, and its
     parameters are unmeasured in any case. The broad-set matrix comparison
     (C-41 toolchain) confirms that the saturated-red ΔE is not matrix-fit
     error, which identifies this effect and the surrogate cyan as the source
     of the residual.
   - `logH_mid` shows a per-channel spread of 0.23 logH: the characteristic
     curves do not cross the digitised midscale-neutral densities at one
     common exposure, partly real film behaviour and partly digitisation
     tolerance. The mean is used wherever a characteristic curve is inverted
     and cancels exactly on neutrals.
   - Status M red responsivity is truncated at the 700 nm dye-chart edge and
     renormalised, affecting 0.28% of the red area, the same handling class
     as the Ektachrome truncation.
   - A datasheet cross-check anomaly persists: the spectral chart's midscale
     neutral integrates to a Status M red of 0.969, against the judging
     table's gray-card corridor of 0.77–0.87. The chart's midscale sits above
     the gray-card exposure; the true gray-card point remains unlocated
     without a measured roll.
   - A Status M to DWG landing is a metameric 3×3, film sensitivities not
     being combinations of the colour matching functions, the same compromise
     any camera input device transform makes, quantified by the ColorChecker
     ΔE figures above.
9. **The shipped cubes embed no camera, and naming one is worth a bounded and
   measured amount.** The engines integrate `PHI = LED_SPD x camera_SSF`, in
   `c41_statusm_engine.py`, `adx_engine.py`, `portra_decompose.py` and
   `reversal_transform.py`, the C-41 pair with the stock's D-min spectrum as
   a further factor (register #17). All four row-normalise `PHI`, so a
   per-channel scale cancels and only the shape of the sensitivity curve can
   matter, and all four default to `--sensor none`, which drops the factor
   rather than substituting a curve.

   *The default assumes a unity response; a shared curve cancels only in its
   scale.* One response curve serves all three exposures and appears in both
   integrals of `D = -log10(INT LED*Q*T / INT LED*Q)`. A constant `Q` factors
   out and moves no modelled density by more than 2e-16 D, verified. A
   wavelength-dependent `Q` does not cancel: it stays inside both integrals,
   weighted by each LED's emission, tails included, and sharing one curve
   across three exposures does not make it flat. The tilts below are
   illustrative shapes against a flat reference, not a measured bound on any
   sensor:

   | response tilt | R | G | B |
   |---|---|---|---|
   | 1% per 10 nm, dye 1.0 | 0.0008 | 0.0033 | 0.0006 |
   | 1% per 10 nm, dye 1.8 | 0.0014 | 0.0072 | 0.0017 |
   | 1% per 10 nm, dye 2.5 | 0.0021 | 0.0109 | 0.0035 |
   | 1% per 10 nm, dense yellow | 0.0001 | 0.0028 | 0.0376 |
   | 3% per 10 nm, dense yellow | 0.0003 | 0.0083 | 0.1201 |

   Blue under a dense yellow dye is the worst case by an order of magnitude,
   the blue reading there being dominated by the LED's spectral tails where
   the dye is weaker. A monochrome user chasing deep shadow can write a
   measured `Q` into all three channels of an SSF file, which the existing
   reader accepts.

   *The bound is a function of density.* Substituting each of the forty-four
   measured cameras in `data/cameras/` in turn, reading scan-space density on
   the Portra 400 dye set through its mask as the cube does, gives this
   peak-to-peak spread across the population:

   | dye state | R | G | B |
   |---|---|---|---|
   | neutral 0.3 | 0.0030 | 0.0071 | 0.0015 |
   | neutral 1.2 | 0.0122 | 0.0408 | 0.0073 |
   | neutral 2.5 | 0.0262 | 0.1210 | 0.0202 |
   | cyan 2.5 | **0.0425** | 0.0155 | 0.0035 |
   | magenta 2.5 | 0.0068 | **0.1743** | 0.0021 |
   | yellow 2.5 | 0.0010 | 0.0171 | **0.1178** |

   Against the a7R III specifically, the displacement a second camera would
   see from the shipped cubes, the figures are 0.006/0.021/0.004 at a 0.3
   neutral, 0.024/0.113/0.020 at a 1.2 neutral and 0.052/0.280/0.072 at a
   2.5 neutral, reaching 0.48 in green at a dense magenta and 0.78 in blue at
   a dense yellow. The mask roughly doubles the green and blue figures
   relative to a bare-LED reading, because it passes red far better than
   blue and so raises the weight of each LED's long-wavelength tail, exactly
   where the colour filter and the unity response differ. Three properties
   follow, the first the one to quote:

   - **Below approximately 1.2 peak dye the camera is a second-order term**,
     under 0.041 D peak-to-peak across the population and under 0.12 D
     between the a7R III and the sensor-free model; above it the dependence
     climbs past the 0.034–0.063 D basis-sensitivity band of entry 8. A
     single figure for the whole cube overstates the low end and understates
     the high end.
   - **Each channel is most camera-sensitive where its own dye is dense**, and
     green is roughly twice as sensitive as red or blue. This tracks the
     illuminant: the LEDs are 15, 32 and 15 nm FWHM in R, G and B, so each
     samples the film at nearly a single wavelength and the SSF enters
     approximately as a per-channel scalar that cancels in the density ratio,
     the green LED being the widest and least monochromatic. A narrower green
     LED would remove most of the residual dependence without altering a line
     of code; a broadband scan would carry the dependence at first order,
     which is a further reason narrowband is a hard constraint.
   - **The camera is not what blocks portability.** The other half of `PHI`
     is `film_scanner_SPD_combined.csv`, a measurement of this apparatus's
     own LEDs, and no public dataset supplies the equivalent for another rig.

   *A colour filter is not purely a cost.* It band-limits the illuminant's
   spectral tails per channel (see per-exposure filtering under
   `reversal_transform.py`). Removing it widens each channel's effective
   sampling band, on the a7R III from a standard deviation of 16.4 to 21.8 nm
   in green and 11.5 to 20.1 nm in blue, enlarging the region of the lattice
   no dye triple can reach. On the 3.3 corridor that is immaterial within the
   working range (C-41 probe RMSE 0.0004–0.0014 D, maximum 0.007–0.030 D over
   dye 0–2.2) but not over the whole declared corridor, where the same probe
   reaches 0.006–0.16 D RMSE and up to 3.1 D: read through the orange mask,
   the blue LED's 540–660 nm plateau carries about four times the weight it
   has in the bare LED, so the sensor-free blue channel saturates under a
   dense yellow dye well inside the corridor, first on the Fujifilm 200/400
   mask, the fleet's densest. A colour filter removes that plateau, so the
   figures are a property of the unity response, not of the film. On the 5.0
   reversal corridor the widening is the reason the sensor-free reversal
   cubes lose accuracy beyond dye 2.5. The forward model is not saturating:
   scan density rises at slope 1.0 to 1.1 out to dye 5.0 on both sensors, so
   the effect is confined to the chroma corners.

   Every figure here comes from published sensitivity curves; no second
   physical camera has scanned film through this chain. The library's
   provenance is thinner than its size suggests (`data/cameras/README.md`):
   thirty-eight of the forty-four come from one creator on one instrument
   and carry no `laboratory` field, and no file declares a monochromator
   bandwidth or the lens and filter stack in front of the sensor.

10. **Scan-side stray light is unmodelled.** `engine/` contains no
   veiling-glare or stray-light term on the capture side; the `flare` control
   in `PrintEmulationEngine` belongs to the print stage. Measured density is
   `-log10(rate_film / rate_plain)`, in which a per-channel sensor gain
   cancels but an additive floor from glare, LED crosstalk or black-level
   residual does not; such a floor compresses the dense end and imposes a
   ceiling:

   | stray-light fraction | max measurable D | error at D 2.0 | at D 3.0 |
   |---|---|---|---|
   | 0.01% | 4.00 | 0.004 | 0.041 |
   | 0.1% | 3.00 | 0.041 | 0.301 |
   | 0.5% | 2.30 | 0.174 | 0.776 |

   The corridor ceilings are DMAX 3.30 on the negative path and dye densities
   near 4.0 on the reversal path, so the sensitivity is not academic. The
   apparatus controls flare effectively, so the term is recorded as known and
   unquantified rather than as a defect. The inexpensive route to closing it
   is a certified step tablet (for example 21 steps spanning 0.05–3.05 D)
   scanned in the gate: many known densities in one capture, no film or
   development, yielding the linearity curve and the stray-light fraction per
   channel. A roll's own D-max cannot serve: it is a second unknown, and the
   noisiest patch on the roll.

11. **Reversal interimage is unmodelled, and no structure exists for it.**
   `engine/reversal/reversal_transform.py` contains no `DIR_MATRIX`, no
   grey-ramp pre-compensation and no interimage stage, so unlike the ECN-2
   path there is not even an identity-default hook. The mechanism differs
   from the negative case: in a colour negative interimage arises from DIR
   couplers releasing inhibitor during colour development; in a reversal film
   it arises during the first, black-and-white development, from iodide ions
   released by developing grains diffusing into neighbouring layers and
   inhibiting solution physical development there, requiring a silver halide
   solvent in the first developer and silver iodide in the causing layer, and
   manufacturers enhance it with DIR hydroquinones, which act in
   black-and-white development where ordinary DIR couplers cannot. Its
   importance is greater in reversal material: a transparency is viewed
   directly and cannot carry coloured masking couplers, so interimage is the
   principal remaining correction for unwanted dye absorption, and Fuji
   attributes the differing characters of Velvia, Provia and Astia to
   deliberately controlled interimage. No published IIE percentage exists for
   any stock in this fleet, and no source measures reversal and negative
   interimage by one method. It is a caveat rather than a defect: the
   reversal cubes perform densitometry on dyes that already exist, so a
   scanned transparency carries its interimage in the measured densities and
   re-simulating it would double-count, as argued for C-41 under the
   discrimination gap. What is lost is the ability to predict how two
   reversal stocks differ off the neutral axis from datasheet data alone.
   Sourcing in `knowledge/interimage-effects-and-stock-differentiation.md`
   §4a.
12. **Most of the C-41 fleet fits against a bound rather than freely.** Ten
   of the twelve stocks rest at least one shape parameter exactly on its
   limit; only Portra 160 and Pro Image 100 are free of one. Seven pin the
   cyan shift at +25 nm (Ektar 100, Ultra Max 400, Portra 400, Portra 800,
   Pro 400H and both Fujifilm stocks) and five pin a width: Ektar 100, Ultra
   Max 400, Gold 200, Fujicolor 100 and Superia Premium 400 at the 1.15 cyan
   ceiling, and the two Fujifilm stocks at the 0.85 cyan and magenta floor. A
   pinned value is the constraint speaking, and the residual beside it is the
   best the model could manage while held there. `portra_decompose.py`
   derives the list from the solution, prints a warning naming each pinned
   parameter, and records it as `fit_audit.bounds_pinned`.

   The count is nine, not five, because the solve does not depend on where
   it starts: `least_squares` is a local method, and on eight of the twelve
   stocks a seeded 64-point multistart over the same bounds finds a strictly
   better optimum than a single fixed start, by up to 29.5% in RMSE on Ektar
   100. The better optima push harder against the cyan shift limit, so a fit
   that looked free was in several cases an early stop short of the
   constraint. `fit_audit.multistart` records the seed, the start count, the
   single-start RMSE and the improvement. The ±25 nm bound is therefore
   load-bearing for nine of the twelve, counting the two stocks within 1 nm
   of it, and the fitted cyan shift is not a per-stock measurement for those
   stocks; whether the uniform bound should be widened is an open modelling
   question, to be justified against dye chemistry rather than the residual
   it would buy.

   **The shift parameter is not the peak displacement in nanometres.** The
   warp is `basis(p + (l - p)/w - s)`, whose peak lands at `p + s·w`. At the
   width limits the two differ by up to 15% of `s`, so the ±25 nm bound
   permits a true displacement of up to ±28.75 nm, and a stock reported at
   +25.0 nm may have moved its peak by 21.25 nm. The parameterisation is
   self-consistent and stands, a change requiring the whole fleet to be
   refitted; the derived quantity is published as
   `fit_audit.peak_shift_nm`, which cross-stock comparisons use.
13. **The digitised spectral curves carry fabricated edges, bounded but real.**
   Every Kodak spectral trace stops short of the 400–700 nm frame, and the
   digitiser flat-holds its last traced value across the gap: 67 samples
   across the seven Kodak stocks, up to 12 samples wide on Ektar 100 and held
   at a D-min of 0.2603 rather than at a negligible tail. Replotted onto the
   printed chart, the traced regions hit the ink on 100.0% of samples for
   every stock and both curves; the held edges hit it on 20.0% (Ektar 100),
   50.0% (Portra 160), 66.7–75.0% (Gold 200, Ultra Max 400), 66.7–80.0% (Pro
   Image 100), 75.0% (Portra 800) and 100.0% (Portra 400, two samples), so
   the held value disagrees with the printed curve in most cases by more than
   the chart's line width. Pro Image 100 shows the same effect at its
   short-wavelength end alone, its midscale trace beginning only at
   405.96 nm where the printed curve is clipped by the top of the plot box,
   so five samples of midscale and three of D-min are held; those edges hit
   the ink on 80.0% and 66.7% of samples.

   *Reach.* The decomposition excludes it: `portra_decompose.py` masks its
   objective to each stock's measured support, and all 67 samples fall
   outside that mask. The Status M cube is untouched, the spectral arrays
   being read only after the cube is written, for a printed neutral-axis
   diagnostic. The print path is the one place it enters: the negative's
   D-min spectral density feeds the paper exposure integral, whose support
   mask stops at the 400–700 nm grid edge rather than at the stock's measured
   range, so 17 of Ektar 100's fabricated samples sit inside it and carry
   31.5% of the cyan record's exposure weight. The consequence is small
   because the curve is nearly flat where it was held: continuing it linearly
   from the last ten measured samples moves the D-min by 0.009 D and the cyan
   record's printing exposure by −0.0014 log₁₀ E, approximately 0.005 stop,
   magenta and yellow unmoved. The Fujicolor Pro Laser paper's magenta dye
   curve is held for 33 samples in the same way but hits the ink on 100.0% of
   them.

   *Recorded rather than corrected* because removing the hold means
   re-tracing and re-emitting the affected `data/` files and revalidating
   every dependent stock, for about 0.005 stop on one record of one stock.
   Anyone reusing `data/films/*_curves.json` should treat each curve as
   authoritative only within the
   `digitization_audit.spectral_dye_density.endpoints` range it publishes.
14. **Part of the Vision3 basis is tracked rather than measured, and the
   proportion is not published.** The Vision3 dye tracer follows each curve
   column by column; where a column yields no centroid within tolerance, or
   the run is shared with a neighbouring curve, it takes its own linear
   prediction. Trailing predicted columns are rolled back so the recorded
   support ends at real ink, but interior ones are kept undistinguished.
   Across the four traced stocks the share of predicted columns is 0.4–5.2%
   for most curves, rising to 19.3% for Vision3 50D's magenta and 22.9% for
   200T's magenta, both running through extended crossings. The ink test
   cannot see this: at a crossing the neighbouring curve's ink occupies the
   same place, so a predicted point scores as a hit, and the audit reports
   100.0% for curves a fifth predicted. This is a second blind spot of the
   overlay alongside labelling, and it bears on every C-41 stock, the Vision3
   set being their surrogate basis. It is interpolation across genuinely
   ambiguous ink rather than invention where no ink exists, hence a caveat
   and not a defect.
15. **Paper channel assignment rests on vertical order alone.** The paper
   digitiser sorts the three characteristic curves by descending bounding-box
   centre and names them R, G and B in that order, with nothing corroborating
   the assignment. The three curves of Endura Premier cross one another two
   or three times over the shared exposure range and touch to within
   0.0000 D, so their vertical order is not constant, and the overlay cannot
   help: a channel swap preserves geometry exactly and scores 100%, measured.
   The film path is guarded by three mechanisms the paper path lacks: both
   sensitivity digitisers classify by peak wavelength and assert the result
   against expected bands; the Fujifilm digitiser asserts that the
   characteristic curves do not cross; the Kodak digitiser asserts the
   documented B > G > R order by at least 0.05 D (the orange mask offsets the
   records, the smallest gap in the fleet being 0.175 D on Fujicolor 100 with
   no sign change on any stock), verified to fail on a permutation at a worst
   gap of −0.48 D. None transfers to paper: RA-4 curves genuinely cross, and
   paper characteristic curves have no peak to classify by.
16. **Paper tone curves are evaluated with a terminal-slope linear extension
   beyond their digitised span, and the shipped cubes barely engage it.** The
   H&D lookups use `interp_lin`, which continues the local slope where a
   characteristic curve's data ends, the one deliberate exception to the
   rule that the model stops where the data does, because a tone curve
   collapsing to zero off its end would be a worse invention than the slope.
   Over the 65^3 print lattices the Endura build engages the extension on
   0.00% of nodes in every layer; the Fuji build on 1.06% of nodes in cyan
   and 0.02% in yellow, moving density by at most 0.027 D relative to holding
   the end value; neither engages it on any patch of the printable window or
   the neutral calibration ramp. The gray-axis lock's stored 1-D calibration
   maps extend the same way outside the calibrated neutral span, on 24–36% of
   lattice nodes, but the H&D evaluation downstream stays inside its
   digitised span at the rates above, which is what bounds the output.
17. **The roll anchor subtracts D-min in integrated density, and the engines
   model what that leaves.** `RollAnchor_ScanPrep.dctl` divides the linear
   frame by the base's own reading, so the cube receives
   `−log10(∫Φ·10^−(Dmin+dye·DYE) / ∫Φ·10^−Dmin)`, the image dyes as the LEDs
   see them through the base and orange mask, density under the illuminant
   `Φ·10^−Dmin(λ)`. That differs from the density under the bare LED unless
   the mask is flat across each LED's band, and it is not: Portra 400's D-min
   falls 0.11 D across the green LED's 528–560 nm FWHM and Fujifilm 400's
   0.05 D across the blue LED's. The bare-LED model against the mask-filtered
   one, over the dye 0–2.2 box: a neutral at dye 1.0 read 0.056 D low in
   green and 0.009 D low in blue on Portra 400, 0.060 and 0.055 D low on
   Fujifilm 400, with maxima of 0.19–0.28 D in green and 0.23–0.47 D in blue
   at the box corners; through the Endura print a physically neutral Portra
   400 negative rendered at a\* +3.8 / b\* −1.7 at k = 0.18 and a\* +6.9 /
   b\* −3.5 at k = 0.24 (ΔE2000 5.4 and 9.2), and the off-neutral mean over
   the printable window was 2.4 ΔE2000 on Portra 400 and 1.5 on Ektar 100,
   the size of the basis term of the error budget. `c41_statusm_engine.py`
   and the decoupling diagnostic in `portra_decompose.py` therefore integrate
   the mask-filtered illuminant, and the Status M engine's neutral-axis check
   reads the full traced midscale and the base with the bare LEDs and anchors
   one against the other, so the closure it prints is the fit's own residual
   again. Adding the roll's D-min back to a cube's Status M output for
   datasheet quality control carries the same non-commutation on the Status M
   side, 0.01–0.08 D in green over the box, and is approximate.

   *ECN-2 applies the same factor from the traced Minimum Density curve.*
   Each Vision3 sheet prints that curve dashed on its spectral dye-density
   chart, and the film digitiser traces it (401–762 nm on 50D, 401–799 nm on
   the other three), with an external check no other curve in the repository
   has: the Status M of the traced spectrum against the characteristic
   sheet's densitometer D-min triplet closes to −0.014 to −0.033 D in red,
   −0.025 to −0.036 D in green and −0.004 to −0.044 D in blue across the four
   stocks, the trace reading slightly lighter throughout. The scene cubes
   read each stock's own curve; the ADX16 cube reads the family average,
   whose inter-stock spread is 0.053 D median, 0.033 / 0.016 / 0.066 D at the
   three LED peaks. ST 2065-3 subtracts `APD_Dmin` in integrated printing
   density, and `adx_engine.py` forms exactly that, `APD(mask + dye) −
   APD(mask)`. The ADX engine's neutral-axis check, which reads each stock's
   traced midscale and its own mask with the bare LEDs, anchors one against
   the other and unmixes through the family model, closes to within 0.012 D
   on every stock; the 0.06–0.08 D it left without the mask was this entry's
   non-commutation. The stock-blind cube's residual mask term is measured: a
   stock's own mask against the family mask costs, over the dye 0–2.2 box,
   0.001–0.012 D mean and 0.005–0.089 D maximum in APD, largest in green on
   50D and 250D; through the Academy decode the mismatch appears as an AP0
   channel spread on a flat grey of 6–18% at mid-grey, largest on 250D and
   500T, which the printer-light trims remove at one density and a per-stock
   mask would remove at every density, at the cost of four ADX16 cubes
   instead of one.

   *The reversal path carries the same term under a surrogate base.* No
   reversal sheet publishes a base spectrum, so each build bounds the term
   with the mildest tint its own sheet admits: the characteristic curves'
   Status A D-min triplet placed at the three Status A peak wavelengths and
   joined by straight lines, the scan side reading the dyes through
   `Φ·10^−base(λ)`. A neutral at dye 1.0 differs from the bare-LED reading by
   at most 0.0002 D, and over the dye 0–4 box by 0.007 D on Ektachrome E100,
   0.002 D on Velvia 100 and 0.000 D on Provia 100F and Velvia 50, whose
   D-min triplets are flat to the third decimal. The bound is only as good as
   the surrogate: a base whose tint varies within an LED's band rather than
   between the channels is invisible to it, and a measured clear base would
   replace it. Every reversal build prints the figure.
18. **Part of every fitted C-41 dye set rests on the basis's held blue edge.**
   `portra_decompose.py` warps the Vision3 basis by `basis(p + (λ−p)/w − s)`,
   and the basis is measured on 402–798 nm and held flat outside it. A red
   shift or a narrowing pulls the blue end of the warped curve onto the held
   value: a cyan at +25 nm reads the basis below 402 nm for every grid
   wavelength under about 427 nm, and at width 0.85 under 465 nm. The shipped
   curves therefore carry plateaus at the blue end that the chart never
   published: magenta held at −0.0057 over 400–413 to 428 nm on ten stocks,
   cyan at 0.2164 over 400–465 nm on Fujifilm 200 and 400 and over 400–428 nm
   on Portra 160, yellow at 0.5103 over 400–404 to 414 nm on all twelve, each
   recorded in the dye JSON as `fit_audit.basis_held` with band, sample count
   and value. The fit objective is not restricted to exclude them, because
   the aggregate is measured there and dropping it would leave the yellow
   peak unconstrained on the Fujifilm stocks; the basis cannot be re-traced
   there, its chart starting at 400 nm. Bounded by refitting under the other
   admissible prior, the descender continued linearly from its last 10 nm:
   the fitted curves move by 0.008–0.029 D mean and up to 0.26 D at the blue
   edge, scan density over the dye 0–2.2 box by 0.001–0.031 D mean, and a
   negative made under one prior read by a cube built under the other
   misreads Status M by 0.002–0.009 D mean and up to 0.064 D (green, Portra
   400), 0.017 D on Fujifilm 400. The linear prior reaches a lower residual
   on the Kodak stocks (Portra 400 0.0077 against 0.0109 D) and a higher one
   on Fujifilm 400, the same signal as entry 8's bound: fit quality bought
   over an unmeasured band is not evidence, so the hold stays and the samples
   are marked assumed.
19. **The reversal sheets' neutral series is not visually neutral through the
   model, and the disagreement is larger than Status A placement can
   explain.** Each reversal build reads its stock's traced characteristic
   curves (Status A against log exposure, base and fog included, the one
   sheet quantity its inverse never consumes), subtracts the sheet's own
   D-min per channel in integrated density as the roll anchor does, and
   solves at every exposure for the three dye amounts whose Status A density
   reproduces all three curves at once. The solve closes at machine precision
   with non-negative amounts falling with exposure on all four stocks (Velvia
   50 shows 13 small rises, tracing noise in its dashed band), so the traced
   dyes can form each sheet's neutral. Rendered on the D50 table those series
   are not neutral: at Y = 0.18, a\*/b\* read −0.4/−7.4 on Ektachrome E100,
   −1.7/−5.5 on Velvia 100, −1.4/−2.7 on Provia 100F and −3.6/−3.2 on Velvia
   50, with |b\*| up to 7.5 over visual density 0.3–2.0. The E100 sheet
   supplies an internal control: its dye chart states that equal amounts form
   a visual neutral at 5000 K, and equal amounts through the same dyes and
   observer give a\*/b\* −0.1/+0.1, so the dyes and the observer agree with
   the sheet and the disagreement lies between the characteristic curves and
   the dye chart, in the Status A path: the sheet's neutral series carries
   20% less yellow than a visual neutral of its own dyes. Shifting any Status
   A responsivity by ±10 nm moves b\* by at most 1.5 (a green shift moves a\*
   by ±4); nulling E100's b\* would take +0.10 D on the sheet's blue record,
   Provia's +0.05 D. Candidates, none settled: the sensitometric daylight
   series may not be a visual neutral at D50 by design; the Status A
   transcription is unverified against ISO 5-3 in shape as well as placement;
   the observer is truncated below 400 nm, worth about one unit of b\* in
   this direction. Until a transparency is measured, the reversal cubes'
   neutral axis is read as carrying a possible blue-green bias of this size
   on a sheet-defined neutral. Every reversal build prints the closure and
   the D50 a\*/b\* of the series; the written cube reproduces the series to
   0.0007 D, which is plumbing, not evidence.

## The role of NamiColor in this project

NamiColor (open source, GPL-3.0, github.com/Wavechaser/NamiColor) is a generic
film-scan lineariser: `log10`, or `-log10` for negatives, followed by a
per-channel affine gain and offset aligned by eye against a neutral reference,
landing in a Cineon Film Log container. It provides no spectral model, no
crosstalk correction and no standardised target, and its author documents it
as approximable with stock Resolve nodes. This pipeline's cubes and DCTLs
perform the work of its channel-alignment step, spectrally derived and
metrically anchored. NamiColor is not placed after the postshaper to
linearise Status A density back to a positive image: its Negatives mode
computes `-log10` of an already logarithmic quantity, not the `10^-D`
inverse. `Density to Linear.dctl` performs that step, and NamiColor-style
per-channel offsets, where wanted, belong as aesthetic trims within that node
or above it, never fused into the linearisation arithmetic.

## Invariants

Each rule prevents a defect that is not apparent from the code alone.

- **Never let a held or zero-filled sample vote in a fit.** Fit only the
  measured region; do not default to 400-730 nm. Flat-holding the unmeasured
  400-403 nm blue edge degrades every Kodak C-41 dye fit by 3-7×. A hold
  inside a model function is the same fabrication one step removed: the
  warp's reading of the basis below 402 nm is a plateau nobody traced, carried
  only because the aggregate is measured there, marked per stock in
  `fit_audit.basis_held` and bounded by its alternative prior (register #18,
  hard constraint 1).
- **Derive a curve's measured support from the data, never from a metadata
  field.** `reversal_transform.dye_support_grid()` reads support from
  `~isnan(values)` on the array itself. `portra_decompose.py` instead reads
  `digitization_audit.spectral_dye_density.endpoints`, and the two disagree:
  eleven of the twelve C-41 stocks record an `endpoints` upper limit above the
  end of their own 400–700 nm array, by 2.6–3.1 nm on the Kodak sheets and
  16.9–19.1 nm on the Fujifilm ones, the wider trace having been discarded on
  resampling. The fit mask is saved only by its intersection with a `GRID`
  that stops at 700 nm; raise that ceiling without re-digitising and
  `resample()` supplies zero density, perfectly clear film, across the
  difference, degrading measured RMSE by 500–1160% and inverting every fitted
  cyan shift. Clamp any metadata-derived support with `min(hi, wl.max())`, or
  read the array as the reversal engine does.
- **Never bridge a gap where the curve left the chart.** Gold 200's cyan has
  a real gap at 470-485 nm where the blue tail dives below the axis floor and
  resurfaces; the datasheet does not print it, so it is kept null. A straight
  line across it would sit above every true value, the floor bounding the
  curve from above: the gap is a bracket [0, floor], not two samples with an
  unknown between them, and only the latter may be interpolated (hard
  constraint 1). The reversal engine's gap handling is the reference
  implementation.
- **Ektar 100's printed spectral curves stop at 687.9 nm; the 688-700 nm red
  tail is not flat-held.** That band carries 1.1% of Status M red; flat-hold
  against zero-fill moves Ektar's red Status M aggregate by 0.028 D,
  comparable to the smallest inter-stock distance in the fleet (0.021 D).
  True support is recorded in each `digitization_audit.endpoints` block.
- **Spectral comparison tools restrict fits to each stock's measured
  support**, not a fixed 400-700 nm grid, on which Ektar silently contributes
  13 fabricated flat-held points.
- **The Vision3 ADX16 route ships one shared-basis cube, not four; the scene
  route ships four; the two are not conflated.** In printing density,
  inter-stock disagreement is 0.008-0.018 D RMS, far below the 0.116 D that
  separates the corrected basis from the uncorrected one; per-stock
  printing-density cubes would bake tracing noise in as chemistry. The scene
  cubes are per stock because their divergence is real: characteristic
  curves, spectral sensitivities and balance illuminant differ where the dye
  synthesis does not, and each decodes through the stock's own traced dye set
  so that its output is that stock's exposure record. The per-stock dye JSONs
  are live inputs on the scene route and reference data only on the ADX16
  route.
- **Do not drop the 9-parameter warp or substitute an unwarped shared basis**
  without reproducing what the warp absorbs. The closure residual has the
  same structure across all four independently traced Vision3 stocks
  (correlations +0.78 to +0.99), peaks at 580 nm in the magenta-cyan valley
  at +0.164 D, and the warp absorbs 60-69% of it (0.059-0.078 D down to
  0.018-0.031 D). It compensates a real shape mismatch between published
  peak-normalised dyes and dye shapes at developed midscale neutral.
- **A dye-amount inversion residual that sits entirely on zero-clipped nodes
  is a constraint violation, not a fit error.** The Status M inversion on the
  print path is exact wherever it does not clip, and 22–25% of the lattice
  asks for a negative image-dye amount, where the inversion is impossible by
  physics and no refitting will improve it.
- **The gamut projection is confined to the reversal path.** Applying
  `project_to_reachable()` in `c41_statusm_engine.py` or the family-basis
  Vision3 negative build was tested and rejected on measurement. Their
  unreachable fractions are small, 4.4% on Fujicolor 100, 4.7% on the
  Vision3 build and 10.8% on Portra 400 against 41.6% on Provia 100F, and
  form scattered pockets rather than one contiguous region; projecting a
  pocket one node deep gives it a neighbour's value and doubles the step to
  the node on its far side. The largest step involving an unreachable node
  rose from 0.2019 D to 0.4019 D on Fujicolor 100 and from 0.3719 D to
  0.5461 D on the Vision3 build, against falls from 0.9713 D to 0.4174 D on
  Fujifilm 400 and from 0.4031 D to 0.3384 D on Portra 400: two builds of
  four made worse for no reachable benefit, since no plausible input reaches
  the region on any path.
- **A published characteristic curve is an integral density of a neutral
  series and is never read as one layer's dye.** The Vision3 scene engine and
  both print engines convert their three curves, on the neutral series where
  the three are consistent, into per-layer amount tables by the full
  three-channel solve, and look each layer up on its own table. Reading a
  channel's curve at its layer's exposure attributes the other two layers'
  unwanted absorption to that layer: on Vision3 it puts the layers' exposures
  0.09–0.44 logH apart on a neutral that satisfies the sheet, and on Endura
  it costs up to 15 ΔE2000 at saturated colours while agreeing exactly on the
  neutral, which is why no neutral-axis check can see it
  (`knowledge/reading-datasheet-charts.md`).
- **The scan-side responsivity of a masked negative is the LED behind the
  mask.** The roll anchor subtracts D-min in integrated density, so the C-41
  engines integrate `LED × sensor × 10^−Dmin(λ)`; the bare LED misreads a
  midscale neutral by 0.06 D in green (register #17).
- **A gamut projection never touches a node the solve reached.**
  `reversal_transform.project_to_reachable()` substitutes only where the
  residual exceeds `REACH_TOLERANCE_D`, leaving every colour the film can
  produce bit-identical to the unprojected build; smoothing across the
  boundary would displace reachable colours to tidy a region no scan
  addresses.

## Known limitations

The single most consequential caveat is set out under
[C-41 fleet discrimination gap](#c-41-fleet-discrimination-gap-the-most-important-caveat-in-this-document)
and summarised in the second entry below.

- **No measured validation.** Every metric the C-41 fleet reports derives
  from datasheets and is verified only against itself; the chain is in real
  use and passes qualitative examination, but no part of it has a measured
  check. Turning "looks right" into "agrees with a reference to within X"
  requires a validation roll on at least two stocks, **Portra 400 and Ektar
  100**, because the discrimination gap is the thing under test and one stock
  cannot show it. Such a roll carries, on each stock, on one development:
  1. a neutral gray-card exposure ramp (±3 stops) and a ColorChecker frame;
  2. **R/G/B colour-separation step wedges**, without which the roll cannot
     fit `DIR_MATRIX`. Interimage is *defined* as the gamma difference between
     a separation exposure and a neutral one (US4830954A;
     `knowledge/interimage-effects-and-stock-differentiation.md`), so a gray
     ramp and a ColorChecker, both exposed under neutral light, contain no
     interimage signal. Per channel
     `IIE% = 100·(γ_separation − γ_neutral)/γ_neutral` gives the six
     off-diagonal terms; published magnitudes run ~10–35% (magenta largest,
     yellow smallest), far larger than the ~5% characteristic-curve contrast
     difference that is currently the only separation between the stocks in
     this fleet;
  3. an unexposed-developed **D-min patch**;
  4. the **process record**: one processing run for every stock under test,
     identified, with its control-strip reading against the manufacturer's
     reference values, the measurement geometry, and a repeatability figure
     from repeated reads. Every stock and basis difference is then reported
     against that process variation, the manufacturer's action and control
     limits kept distinct from the measured statistical uncertainty; a
     difference between two stocks developed in separate runs is evidence of
     nothing (`knowledge/process-chemistry-c41-ecn2-e6.md` §4). The
     separation wedges remain what identifies the dye basis; adding an
     interimage stage to the C-41 scan-to-print chain is not the remedy for
     its discrimination gap.

  The patches are read **spectrally, 380–730 nm, at ≥3 exposure levels**
  spanning the printable window, not as densitometry alone. The marginal cost
  is a spectrophotometer pass over film already shot, and it closes two
  further register items no modelling can: orange-mask off-axis
  mis-attribution (spectral density at ≥3 exposure levels and off-neutral
  colours; the neutral ramp alone is provably insufficient, and the separation
  patches *are* the off-neutral colours), and per-layer dye separation
  (register #8: a separation exposure produces a patch dominated by one
  layer, whose spectrum approaches a direct read of that layer's dye, the
  only route to measured per-layer curves and to a checkable surrogate
  basis). Densitometer or spectrophotometer geometry and illuminant belong in
  the audit block.

- **The C-41 fleet cannot distinguish every stock it holds by their modelled
  dye sets.** Basis sensitivity is 0.034–0.063 D against inter-stock
  distances of 0.021–0.220 D, so 20 of the 66 pairs sit inside the ambiguity
  band; adding stocks does not change this. The stocks differ markedly in
  their published D-min, whose blue-minus-red mask strength spans 0.346 D
  across the fleet, a basis-independent measurement that reaches the print
  cubes at 13–20% of nodes above 1 ΔE2000 and up to 5.5 ΔE2000 on saturated
  colours while leaving neutrals within 0.131 ΔE2000. The print cubes are
  therefore not fully degenerate between stocks, but what separates them is
  the orange mask rather than the modelled dye sets, and only away from the
  grey axis.

- **The Vision3 scene tables are verified only against their own machinery,
  and lose precision in extreme highlights.** The 3×3 is fitted on measured
  reflectances (ColorChecker residual 2.23–2.78 dE2000 mean, maxima 6.83–7.34
  on the red patch, the C-41 scene machinery's metameric floor), the neutral
  ramp is exact by construction, and the ColorChecker full-chain figure
  collapses to the matrix residual because forward and inverse share code.
  What the machinery holds to is the sheet: the per-layer amount tables
  reproduce all three characteristic curves at once with the traced mask
  under the dyes, and the mask's Status M agrees with the sheet's D-min
  triplet to within 0.045 D. The cube stores an exponential output on a
  lattice uniform in density, so trilinear interpolation departs from the
  exact chain by 3.5–5.0% mean within each stock's published characteristic
  span, 2.1–2.5% in the 80–85% of cells that are clean and up to 92–449% in
  the cells that straddle the top of a layer's published curve, where the
  exact chain itself steepens without limit; that tail is a reducible
  lattice error (refining locally brings the worst sample to 6% at 257³)
  sitting on an irreducible model sensitivity, and the build declares the
  operating region (clean cells below a hundred times mid-grey) and reports
  it separately. Mid-grey rests on the
  traced midscale neutral; the sheets' camera-stops zero differs from it by
  0.067–0.404 logH, a uniform per-stock exposure trim. No frame has been
  checked against a known scene.

- **The survival of the scene illuminant through the chain is unverified on
  film.** Hard constraint 5 asserts that it survives, and unlike a
  neutral-axis check that assertion is not guaranteed by construction: the
  gray-axis lock is calibrated on the stock's own neutral and has no
  knowledge of the capture illuminant, and the Vision3 scene route makes the
  same assertion through its built-in balance illuminant. Testing it costs
  one frame: photograph a grey card under a known illuminant, run the chain,
  and compare the print's cast against the prediction from the stock's
  published spectral sensitivity. It is the cheapest real-film evidence
  available to this project.

- **The Print Adjustment trims actually applied are not logged**, per roll
  or per stock. Only 0.005–0.020 k of per-channel trim is ever required,
  0.2–0.8 stop of printer light. Part of that residual has a known cause: a
  cube that integrated the bare LEDs read a midscale Portra 400 neutral
  0.064 D low in green, 0.019 k, the size of the trims observed, and the
  mask-filtered illuminant of register #17 removes it. What the remainder
  correlates with is free diagnostic information nobody records: variation
  by roll within a stock indicates anchor noise or development; consistency
  within a stock but difference between stocks indicates dye-model error, the
  first per-stock signal this pipeline would have produced; correlation with
  neither indicates the scene illuminant, the expected answer. A small trim
  is weak evidence: the gray-axis lock forces the neutral axis by
  construction, `K_MID` being an input it solves against, and has corrected
  as much as 1.23 log-E, four stops, while neutrals still measured clean, so
  a small residual establishes that the normalisation stages are mutually
  consistent along the neutral axis and nothing about the dye model, whose
  errors are off-neutral by nature.

- **Half of every reversal lattice lies outside the dye gamut and holds a
  projected value.** Between 49.7% and 58.7% of nodes, by stock, have no dye
  triple that reproduces their scan density on the shipped sensor-free
  builds, against 26.5% to 32.2% on the a7R III build, and
  `project_to_reachable()` gives them the dye solution of the nearest node
  that does. The sensor-free figure is high enough that the projection
  reaches material a real transparency contains, which is why those cubes
  lose accuracy beyond a dye density of about 2.5 (Current state by stock).
  The cube is continuous at the boundary and every value in it is a colour
  the film can produce, but the region beyond the gamut is a clamp carrying
  no information: the nearest attainable colour, not the colour the node
  asks for. A further 28,361 of Provia's nodes are reached only with a
  negative dye amount, equally unphysical; those are left untouched, the
  mapping through them being continuous, since clamping them would displace
  colours near the boundary that the film does produce. The negative and
  ECN-2 paths hold their unprojected solve output at the corresponding nodes
  (Invariants).

- **The reversal family has no empirical validation either**, and its one
  check against a sheet quantity (register #19) reports a blue-green bias of
  up to 7.5 units of b\* on the sheets' own neutral series that the model
  cannot attribute. It is the branch where the gap is cheapest to close:
  transmissive IT8 targets are manufactured on E-6 stock and ship with
  per-batch reference colorimetry of every patch, the reversal cubes' own
  output space, so a single scan of a target made on one of this fleet's
  stocks would grade that stock's whole chain against independent
  measurement, per-roll anchoring included, with no camera, film lab or
  densitometer involved.

- **The rawpy ARW decode path in `roll_anchor_gui.py` has never run on a
  real file**, leaving PDAF rows and black level unexercised; everything else
  in that tool is verified on synthetic frames, and the interactive windows
  have likewise not run on real captures. The separate decoder in
  `raw_to_exr.py` runs on real Canon CR3 and CR2, Nikon NEF and Pentax DNG
  files and on a real Sony a7R III ARQ, so mosaic, pattern and level handling
  is exercised there, although the ARW container and the a7R III PDAF rows
  are not.

- **Interimage and masking effects are unmodelled**, and for the shipped
  transforms this is a predictive limitation rather than an error: a
  developed, scanned film carries its interimage in the measured densities,
  so the cubes reproduce the effect without modelling it. What is lost is the
  ability to predict off-neutral stock differences from datasheet data alone,
  potentially the largest such gap across the industry, at approximately
  0.1 D in cross-band couplings and amplified roughly twofold through
  inversion in the negative case. The structure exists in
  `engine/common/interimage.py`, and `DIR_MATRIX` sits at identity, its real
  parameters unmeasured.

- **There is no LAD calibration** on the negative path, a fixed
  per-apparatus constant required to place mid-gray correctly in ACES. The
  chain is anchored only on D-min, so the absolute level of mid-gray is
  unconstrained. The anchor tool measures a second point per roll, D-max, and
  marks it diagnostic-only; whether it can serve as the second constraint is
  untested, and its SNR warning indicates that it is frequently no more than
  a lower bound.

- **The computed LED crosstalk has never been compared against a measured
  one.** The engines build `PHI = LED_SPD x camera_SSF` and report a
  decoupling condition number, although that matrix is unmeasured.
  `roll_anchor_gui.py` records `led_crosstalk` in every anchor JSON built
  from three-raw frame sets that include a plain-light set, the off-diagonal
  CFA response under each LED with no film in the gate. It costs nothing at
  capture time and nothing consumes it; comparing it against `PHI` is an
  inexpensive empirical check on a quantity the whole chain assumes,
  requiring no new film.

- **HDR delivery in P3-PQ has not been exercised on a real master.** For
  reversal the proposed default is film-base white, post-anchor density 0.0,
  mapped to 203 nits per ITU-R BT.2408, with a brighter placement of
  approximately 300–400 nits available as a mastering choice; either is one
  scalar in the grade or output stage and is never baked into a cube.

- **Pro 400H's fourth sensitivity layer is not modelled.** Its chart shows a
  dashed "Cyan Sensitive Layer" between green and red, three dyes and four
  sensitivity layers, whereas every digitiser assumes three layers classified
  by ascending peak. How a fourth layer feeds a three-channel exposure model
  is a modelling question, and the weighting is unpublished. The registry
  marks the stock `sensitivity_absent: True`; this blocks no deliverable and
  affects only analysis requiring spectral sensitivity.

- **Builds emit no per-build manifest** recording engine commit and data
  hashes.

## End-to-end error budget

A read-only error-budget instrument (not distributed) propagates every known
error term into the units of the deliverable, ΔE2000 on the print output, and
lists them side by side; it writes nothing. Without it the terms are bounded
individually in the register's entries, in four different spaces, and never
compared. **The patch groups are reported separately and never merged.** The
gray-axis lock forces the neutral axis by construction, so every print-side
term reads near zero on neutrals; a dye-set error on the scan side moves the
neutral axis before the lock sees it, and is the one term that does not. The
off-neutral sampler selects on the render, which does not guarantee that the
input density triple lies on the negative's dye manifold: the patches the
engine's own Status M inverse cannot reproduce to 0.001 D (53 of 400, missing
by up to 0.383 D) measure the solver's clipping on density triples no dye
stack reaches, not film, and are reported as their own group. The reachable
off-neutral column is the budget.

Portra 400, shipped sensor-free configuration, off-neutral, mean and maximum
ΔE2000 over the 347 reachable in-gamut patches spanning the printable window:

| term | mean | max |
|---|---|---|
| basis sensitivity, six refits under different surrogate bases, propagated through the scan inverse and the print | **1.91** | **8.45** |
| the same at fixed Status M, print engine only (comparison, not a term) | 1.26 | 6.89 |
| paper dye digitisation, ±0.00703 D per layer (chart y-axis fit residual) | 0.45 | 1.49 |
| print cube trilinear interpolation, per patch | 0.13 | 1.07 |
| dye fit residual, ±0.0109 D per curve | 0.12 | 0.69 |
| paper H&D digitisation, ±0.00233 D per layer (chart y-axis fit residual) | 0.12 | 0.43 |
| Status M cube serialisation, 0.0005 D on the input | 0.04 | 0.16 |
| paper dye wavelength axis, ±0.036 nm per layer (chart x-axis fit residual) | 0.02 | 0.05 |
| fabricated spectral edges | 0.00 | 0.00 |
| paper sensitivity digitisation | 0.00 | 0.00 |
| **combined, root-sum-square** (under independence; not a bound) | 1.97 | 8.68 |
| combined, plain sum (aligned perturbations) | 2.79 | 12.32 |

Three sensitivities sit beside the table rather than in it, having no
measured bound to enter with. The camera's spectral sensitivity: a constant
monochrome response cancels in the density ratio, a wavelength-dependent one
does not (register #9), and no monochrome sensor has been measured, so the
row is register #9's scenario of a 1% response change per 10 nm across the
band, in both directions, read through the shipped Status M conversion: 0.17
mean / 0.90 max ΔE2000 off-neutral. The enlarger SPD, 3200 K being a nominal
choice: ±100 K gives 0.10 mean / 0.44 max. A Bayer capture, by register #9's
worst case applied at every patch: up to 14.8 ΔE2000 in the mean, a ceiling
rather than a typical value. Four conclusions follow, the first the one to
quote.

- **The figure these documents lead with is among the smallest terms that
  matter.** The dye fit residual contributes 0.12 ΔE2000 where basis
  sensitivity contributes 1.91, a factor of sixteen; a reader who takes the
  per-stock RMSE as the stock's accuracy is reading the wrong number by more
  than an order of magnitude.
- **The budget is one term, and it is consumed twice.** The dye set enters
  the chain at the Status M cube, which converts the scan, and again at the
  print engine, which inverts Status M. Holding the Status M input fixed and
  swapping only the print engine's basis exercises the second consumer alone
  and gives 1.26 mean; holding the scanner observation fixed, so that the
  alternative basis also performs the scan conversion, gives 1.91, and it is
  this figure that the surrogate basis costs. Everything else is at or below
  0.45 ΔE2000 in the mean, the next-largest term, the paper's dye
  digitisation, sitting a factor of four below. The budget carries no
  structural term: it perturbs inputs, and the three model-structure errors
  that once outranked every term but the basis (the bare-LED scan side of
  register #17, the per-channel reading of the paper curves and of the
  Vision3 curves recorded under Invariants) were found by testing the
  engines' assumptions rather than their inputs, and are closed in the
  engines rather than carried as terms.
- **Two terms are exactly zero for the shipped configuration**, by
  construction: the fabricated spectral edges never reach the render because
  `neg_support_mode` truncates that band, and a per-layer offset on the
  paper's log sensitivity is a per-layer exposure scale, which the re-solved
  gray-axis lock absorbs identically at every input, the same mechanism that
  makes the Fuji paper's relative axes harmless. Only a wavelength-dependent
  sensitivity error could reach the render, and the chart's y-axis residual
  carries no shape information to bound one with. The dye chart's wavelength
  error is bounded by its own x-axis residual and carried as a term:
  vector-precise on Endura (±0.036 nm, the 0.02 in the table) and an order
  larger on Fuji Pro Laser (±0.483 nm), where it contributes 0.21 mean / 1.00
  max ΔE2000, that paper's third-largest term and a shape change the
  gray-axis lock cannot absorb. Every perturbed term is worst-cased over all
  eight per-layer sign patterns; a pattern and its negative do not give equal
  magnitudes through the clip at zero, the nonlinear inverse and the
  re-solved lock (the paper H&D term's worst mean rises by half when the
  second four patterns are included).
- **The combined rows are a sensitivity inventory, not an uncertainty
  interval.** Each term is the worst of a set of perturbations at a stated
  bound, not a standard uncertainty with a distribution, and no covariance
  between terms is known. The root-sum-square holds only for independent
  terms and is not a lower bound, since terms of opposite sign cancel and the
  fit residual and the basis sensitivity act on the same three curves; the
  plain sum is the ceiling for perturbations that all push the same way, and
  ΔE2000 is not additive, so even that is approximate. The terms and their
  ranking are the result; no combined figure is the accuracy of a print.
