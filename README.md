# Film Scan Calibration

Colour transforms for camera-scanned film, derived from manufacturer
datasheets. No curve is adjusted by eye.

[Sample results](#sample-results) · [What this does](#what-this-does) · [How it works](#how-it-works) · [What is provided](#what-is-provided) · [Using the tables](#using-the-tables) · [Scanning a roll](#scanning-a-roll) · [Regenerating the tables](#regenerating-the-tables) · [Building for another apparatus](#building-for-another-apparatus) · [Limitations](#limitations) · [Documentation](#documentation) · [Related projects](#related-projects) · [Licence](#licence) · [Credits](#credits)

## What this does

The colour of a camera scan depends on the light source, the sensor and, on
colour negative film, the orange mask. The usual remedy is a set of
per-channel curves, adjusted until a known grey renders grey. This project
models the optical behaviour of the film from published spectral data and
lands the result on a defined colorimetric standard. A script generates every
transform from datasheet measurements, and no stage inspects the photograph.

> [!IMPORTANT]
> **The shipped `.cube` files are built for a monochrome camera.** The
> twenty-one tables that read a scan assume a sensor with no colour filter
> array and a flat spectral response. With a Bayer camera they are an
> approximation that degrades in dense tones; a build named to the camera
> removes it ([A Bayer camera](#a-bayer-camera)). The twenty-four print tables
> take Status M density as input and suit any camera.
>
> This is a research pipeline, developed on one apparatus: a Sony a7R III
> over a CuteNew RGB Pro Light Source, a narrowband RGB LED panel. The maker
> is named only so that the setup can be reproduced, and has no affiliation
> with or sponsorship of this project. No output has been checked against a
> physical reference measurement. Read [Limitations](#limitations) before
> relying on any figure here.

### Common questions

<details>
<summary><b>What is being published?</b></summary>

A method, an implementation of it, and one worked
instantiation. The method derives a transform from the film's published
spectral behaviour and the measured spectrum of the apparatus reading it; the
engines in `engine/` do that and emit lookup tables; the forty-five `.cube`
files are what one particular light source produces. Anyone holding the two
apparatus measurements can build the equivalent for their own rig from the
same engines and the same film data.

</details>

<details>
<summary><b>How does this differ from adjusting curves until a grey renders grey?</b></summary>

Neutral alignment solves for whatever transform makes one reference patch
neutral, and that solution is not unique: many transforms neutralise the same
patch while disagreeing everywhere else. Here the transform is fixed by
published spectral data before any frame is examined, and lands on Status M
density, CIE XYZ under D50 or, for motion picture negative, the scene exposure
that the stock's own characteristic curves record. The cost is rigidity: a
neutral alignment adapts to any apparatus, where these tables are built for
one.

</details>

<details>
<summary><b>Why does no stage inspect the photograph?</b></summary>

A stage that reads image content
cannot distinguish a colour cast from a coloured scene. Nothing here samples a
patch or estimates an illuminant, so the light a frame was shot in survives
into the output and every frame on a roll receives an identical transform.

</details>

<details>
<summary><b>Why take the film's behaviour from published data?</b></summary>

This project measures the apparatus and takes the film from published
spectra. Reading a known target through the whole chain is more adaptive and
needs no literature, but yields one fused number with no way to attribute an
error. Separating the two allows a systematic to be named and bounded.

</details>

<details>
<summary><b>Is narrowband illumination a requirement?</b></summary>

Yes, and it is the only
constraint the method places on an apparatus. Each exposure must interrogate
the film at close to a single wavelength, which keeps channel crosstalk small
at the point of measurement.
The wavelengths themselves are not prescribed, since the engines integrate
whatever spectrum is supplied. A broadband source is outside the design and no
part of this pipeline models one.

</details>

<details>
<summary><b>What does it take to build these for a different apparatus?</b></summary>

Two
measurements, of which one is usually free: the illuminant spectrum and, for a
Bayer camera, its sensitivity. A monochrome sensor of constant response cancels out of a density
measurement, and `data/cameras/` holds measured sensitivities for forty-four
Bayer bodies. Of the forty-five tables only the twenty-one that convert a scan
into a standard or into the scene are rebuilt; the twenty-four print tables
take Status M density as their input and are valid on any apparatus.
[Building for another apparatus](#building-for-another-apparatus) gives the
formats and the metrics to read afterwards.

</details>

<details>
<summary><b>Does a different camera change the result?</b></summary>

By a bounded amount, mostly in
dense tones: under 0.007 D in a light tone, rising to 0.17 D at a dense
saturated colour across the forty-four measured sensitivities, read through a
colour negative's orange mask as the tables are. Below roughly a third of
maximum density the sensor is a second-order term. Naming a camera at build
time removes the approximation.

</details>

<details>
<summary><b>Has any of this been checked against a physical measurement?</b></summary>

No. The
single external comparison available is qualitative, and every quantitative
figure in this repository is otherwise the model reporting on itself. The
missing test is a grey-ramp exposure series, a ColorChecker frame and
colour-separation wedges, exposed on film and read on a spectrophotometer.

</details>

<details>
<summary><b>Can these tables tell one colour negative stock from another?</b></summary>

Partly. The
modelled dyes cannot, three curves being inferred from one aggregate published
curve, which cannot determine three components. The orange masks do differ,
read directly from the datasheets with no inference, but that difference
reaches the print tables away from the neutral axis only.
[Limitations](#limitations) gives both figures.

</details>

<details>
<summary><b>May these tables be used commercially?</b></summary>

Yes, with attribution on the data.
[Licence](#licence) gives the terms, which differ between the code, the tables
and the imported camera sensitivities.

</details>

## Sample results

Frames from the author's own rolls, published unmodified at their exported
resolution. Each image embeds a Display P3 profile for colour-managed
browsers.

### Reversal, through `E100_XYZ_D50.cube`

<img src="docs/samples/e100_perth-22.jpg" alt="A shaded urban plaza with picnic tables and planted beds" width="100%">

<img src="docs/samples/5294_tas-14.jpg" alt="Autumn trees lining a suburban road, seen past an open car door" width="49%"> <img src="docs/samples/5294_tas-29.jpg" alt="A person seated in a café booth, seen through the window from the street" width="49%">

*Ektachrome E100 at the top, Ektachrome 100D (5294) in the pair beneath. One
table, `EktachromeE100_dye_density.json`, serves E100 and 100D/5294–7294: the
two share an emulsion, and their dye curves agree to 0.006–0.011 D.*

> [!NOTE]
> These three frames are **high dynamic range**: Lightroom JPEG exports with
> an ISO 21496-1 gain map. A display and browser that support gain maps show
> highlights above diffuse white. Elsewhere the frames show their standard
> dynamic range base. A resize discards the gain map, so these three stay at
> full size.

### Colour negative, through RA-4 print emulation

<img src="docs/samples/portra400_endura_premier-17.jpg" alt="An ice cream van in a car park, with people at its window" width="46%" align="left"> <img src="docs/samples/portra400_endura_premier-10.jpg" alt="A carnival game stall beside a fairground ride" width="51%"> <img src="docs/samples/portra400_endura_premier-13.jpg" alt="A road intersection in low sun, with people waiting to cross and a fairground ride rising above the treeline" width="51%"><br clear="all">

<img src="docs/samples/portra400_endura_premier-2.jpg" alt="A person bending to search the seabed by hand in shallow surf" width="49%"> <img src="docs/samples/portra400_endura_premier-19.jpg" alt="A horse sculpture beside a coastal path" width="49%">

<img src="docs/samples/fujicolor100_ca-17.jpg" alt="Tall-masted vessels moored along a harbour boardwalk" width="49%"> <img src="docs/samples/fujicolor100_ca-19.jpg" alt="A moored fishing boat with waterfront buildings behind" width="49%">

*The first five frames are Portra 400 printed onto Endura Premier, the final
pair Fujicolor 100 onto Fujicolor Pro Laser. Each stock pairs with the paper
of its own manufacturer.*

The print stage has no verified reference ([Limitations](#limitations)).
These frames carry the author's own `Print Adjustment` trim, which lowers the
gamma about the pivot to soften contrast. The node is optional, and its
defaults leave the image unchanged.

## How it works

A scan enters as linear data. It leaves on a defined density standard or, for
Vision3, decoded to the scene through the stock's own characteristic curves.
The only measurement taken from the roll is the density of its clear film
base.

<img src="docs/figures/c41-node-plate.jpg" alt="Six panels of one frame at successive stages: two orange negatives, a dark positive, a second similar positive, a saturated print, and the delivered frame." width="100%">

*The same frame after each node of the colour negative chain.*

Panels 1 and 2 are still negative. The logarithm in panel 3 produces the
positive, and no stage performs a tone flip.
[docs/resolve.md](docs/resolve.md#what-each-node-does) reads the chain node by
node, and [docs/method.md](docs/method.md) explains why each stage exists.

## What is provided

Forty-five DaVinci Resolve `.cube` tables on a 65³ grid, covering three
processes, all generated by the engines in `engine/`.

- **Colour negative (C-41)**, twelve stocks: Portra 400, Portra 160, Ektar 100,
  Gold 200, Ultra Max 400, Pro Image 100, Portra 800, Fujifilm 400, Fujifilm
  200, Fujicolor 100, Superia Premium 400 and Pro 400H. Each lands on Status M
  density, and on an RA-4 print emulation in standard and high dynamic range.
- **Reversal (E-6)**: Velvia 100, Velvia 50, Provia 100F and Ektachrome
  E100/100D, landing on colorimetric D50 XYZ.
- **Motion picture (ECN-2)**: Kodak Vision3 50D, 250D, 200T and 500T. One
  shared table lands the family on ADX16 code values (SMPTE ST 2065-3) over
  Academy Printing Density, as the entry to an ACES timeline. After
  printer-light trims on a known neutral, the ACES rendering delivers a
  faithful image with no further grading. A secondary route lands each stock
  on scene-linear DaVinci Wide Gamut through its own characteristic curves and
  spectral sensitivities. It is a per-stock model estimate of scene exposure,
  for graded work.

**Which camera each table suits.** The twenty-four print tables take
normalised Status M density, a published standard, so they are valid on any
apparatus. The twenty-one tables that convert a scan into a standard or into
the scene are built for a **monochrome camera** and this one light source.
[Building for another apparatus](#building-for-another-apparatus) covers a
Bayer camera and other LEDs.

The tables come with a per-roll anchoring tool with a graphical interface, two
raw-to-EXR converters (one for Bayer and pixel-shift raw files, one for
sensors with no colour filter array), and the DCTL nodes of the Resolve chain.

> [!NOTE]
> A script in `engine/` regenerates every table from the data in `data/`. No
> table has been adjusted by hand.

## Using the tables

Grading material that is already scanned and measured needs only DaVinci
Resolve.

1. Download the `.cube` files for the stock from the
   [latest release](../../releases/latest).
2. Copy them, and the contents of `dctl/`, into Resolve's LUT folder. Set
   **3D Lookup Table Interpolation** to **Tetrahedral**.
3. Build the node chain for the film process, following
   [docs/resolve.md](docs/resolve.md).

## Scanning a roll

Each frame is three exposures. The light source fires its red, green and blue
channels one at a time, which gives three raw files per frame in that order.
Fix aperture, ISO and LED drive level for the roll. Keep one exposure time per
channel for the whole roll, short enough that the clear film base stays below
sensor clipping. Also capture the roll's clear film reference for the
measurement step. A plain-light set, with no film in the gate, is optional.
[docs/resolve.md](docs/resolve.md#scanning-a-roll) gives the full procedure.

Two programs run before Resolve, and the tables assume both:

```
raw captures  →  raw_to_exr.py       →  linear EXRs      ─┐
                                                          ├→  Resolve
              →  roll_anchor_gui.py  →  Dmin R/G/B       ─┘
```

**`engine/scan/raw_to_exr.py`** merges the three exposures of each frame into
one ZIP-compressed half-float linear EXR, which Resolve imports unmodified.
Run it with no arguments for an interactive session, or directly:

```bash
python3 engine/scan/raw_to_exr.py --in-dir /path/to/roll --mode superpixel --no-flats
```

`--mode superpixel` reads single-shot captures and `--mode pixelshift` a
pixel-shift composite. The reader routes on the file content and ignores the
extension. It refuses a file whose structure does not match the mode.
`--flats R G B` names three captures with no film in the gate, one per
channel, for a vignetting-only correction; `--no-flats` omits it. The flats
are also merged into `plain.exr`, the plain-light set the anchor tool reads.

**`engine/scan/mono_to_exr.py`** serves a sensor with no colour filter array,
native or stripped. This is the camera the shipped tables are built for.
Nothing in the file tells a stripped array from an intact one, so the choice
of program declares the sensor. Frames are read at full resolution with no
binning, and a pixel-shift composite is averaged across its planes. Keep
monochrome files out of `raw_to_exr.py`: it fails on them or, on a converted
body that still reports Bayer metadata, silently halves the resolution and
draws each channel from different sites.

```bash
python3 engine/scan/mono_to_exr.py --in-dir /path/to/roll --no-flats
```

Both converters refuse a triplet of mixed image sizes, a sequence that is not
a whole number of triplets, and a repeated frame counter. Each of these would
merge the wrong channels into a plausible frame. A skipped counter gives only
a warning and prints the triplet assignment, because a capture deleted by
hand leaves the same gap. `engine/scan/decode_selftest.py` tests both
converters and the numeric core of the anchor tool without sample files, and
exits non-zero on any failure.

**`engine/scan/roll_anchor_gui.py`** measures the clear film reference of the
roll (the developed clear leader for reversal, the unexposed rebate for a
negative) and writes `builds/anchors/<roll-id>.json`. A plain-light set adds a
datasheet-comparable density scale and the measured LED crosstalk; Resolve
needs neither. With no arguments, the program collects frames through file
dialogues, opens a picker for the measured region, and copies the three values
Resolve needs to the clipboard.

```bash
python3 engine/scan/roll_anchor_gui.py
```

Neither program is tied to a camera body. Each reads the exposure time from
the file and divides it out, so frames in a set may differ in exposure; a
D-max patch is reached with a longer exposure. ISO is not read: density is a
ratio of two frames, so a sensor gain common to both cancels. For the same
reason, aperture and ISO must stay fixed across a frame set. The anchor
program refuses an aperture that drifts, and warns, naming the frames, on an
ISO that drifts.

> [!WARNING]
> With a plain-light set, the anchor file reports D-min against two zero
> points. Enter **`dmin_exr_scale`** into `RollAnchor_ScanPrep.dctl`, not the
> plain-light `dmin`. On this apparatus the two differ by approximately
> +0.24, +0.58 and +0.93 D in R, G and B. The plain-light values drive green
> and blue past the clamp of the pre-shaper and return a strongly
> yellow-green frame.

[PROJECT.md](PROJECT.md) documents every option of both programs and the
untested parts of the decode path.

## Regenerating the tables

`data/` holds everything the engines require, so a fresh clone rebuilds every
table without the datasheet PDFs:

```bash
python3 engine/c41/c41_statusm_engine.py --stock portra400
```

Each engine reports its own accuracy when it finishes, and every committed
table is one its script reproduces. Building requires `numpy`, `scipy` and
`colour-science`. The scanning programs also require `rawpy`, `OpenEXR`,
`tifffile` and `matplotlib`. The datasheet tracers, needed only to add a
stock, require `pdfminer.six`, `pdfplumber` and `PyMuPDF`.
[BUILDING.md](BUILDING.md) gives the command behind every table.

## Building for another apparatus

Each engine integrates the product of the illuminant spectrum and the spectral
response of the sensor. The other inputs, the dye curves, the target
responsivity and, on the print path, the paper, belong to the film and to
published standards. Only the two apparatus terms change. An apparatus is a
light source whose narrowband red, green and blue channels fire one at a
time, a camera focused on the film, a holder that keeps the film flat, and one
measured spectrum per channel.

### A monochrome camera, the shipped build

A monochrome sensor has no colour filter, so one response curve serves all
three exposures. Its overall level cancels, because density is a ratio of two
integrals: a constant response moves no modelled density by more than
2 × 10⁻¹⁶ D. Its spectral shape does not cancel. The curve stays inside both
integrals, weighted by the emission of each LED, so its variation across each
LED band, tails included, reaches the density. The engines default to
`--sensor none`, a unity response with nothing synthesised in its place. The
shipped tables are this build. A response tilting by 1% per 10 nm, a scenario
measured on no sensor, costs under 0.008 D up to a dye density of 1.8.

### A Bayer camera

A colour filter breaks the cancellation, because the three channels no longer
share one curve. `data/cameras/` holds measured sensitivities for forty-four
interchangeable-lens bodies from Canon, Nikon, Sony, Fujifilm and Panasonic,
imported from the Academy Software Foundation's `rawtoaces-data` library.
`data/cameras/index.json` lists the EXIF model strings and market names of
each body, and [BUILDING.md](BUILDING.md#per-camera-builds) lists every body
as `--sensor` expects it. Naming one is the whole change:

```bash
python3 engine/c41/c41_statusm_engine.py --stock portra400 --sensor Nikon_Z_f
python3 engine/reversal/reversal_transform.py velvia50-narrowband-d50 --sensor Canon_EOS_R6
```

A named build writes to `builds/sensor-<Body>/` and cannot overwrite the
shipped tables. Every cube header records the response that built it.

`--sensor` also accepts a path to a JSON file with four equal-length arrays:
`ssf_bands`, the wavelengths in nanometres, and `red_ssf`, `green_ssf` and
`blue_ssf`, the three responses. Any spacing and range serves, because each
channel is resampled onto the integration grid and normalised to unit sum.
Units therefore do not matter, and the three channels need not share a scale.
The shape of each curve and the shared wavelength axis must be right. For a
**monochrome sensor with a measured quantum efficiency**, repeat that one
curve in all three keys. That build is exact. The `--sensor none` default is
exact only as far as the response is flat across each LED band.

**Choose the reversal corridor with the camera.** A colour filter band-limits
the spectral tails of the light source. That changes the scanner density of a
dense transparency, and the input domain of the cube must cover it. The
engine prints the requirement on every build:

```
velvia50-narrowband-d50: corridor 5.00 D; this stock needs 4.75 D at dye 4.0
```

The shipped monochrome tables use **5.00**. This project's own a7R III build
uses **5.25**, which covers the 5.08 D requirement of Provia 100F. **5.25 is
not a general Bayer constant.** Build once for the body, read the line above,
then rebuild with `--corridor` and pair the cubes with the matching shaper
DCTLs ([BUILDING.md](BUILDING.md#the-reversal-corridor)). The colour-negative
and motion-picture paths keep their 3.30 corridor with any sensor.

### The light source

The engines read the measured spectrum of the light source of this
apparatus, the CuteNew RGB Pro Light Source
([cutenewdesign.com](https://cutenewdesign.com)). The figures quoted here are
properties of the one unit measured.

Other LEDs need their own spectrum, in the format of
`data/equipment/film_scanner_SPD_combined.csv`: a `wavelength_nm` column from
380 to 780 nm at 1 nm, and one column per measured channel. The engines read
`R100_G0_B0`, `R0_G100_B0` and `R0_G0_B100`, the red, green and blue channels
at full drive. Each channel is normalised to unit sum, so absolute calibration
is unnecessary. Any spectrometer covering 380 to 780 nm at nanometre-scale
resolution serves. Measure each channel alone at full drive and interpolate
onto the 1 nm grid.

The centre wavelengths need not match 640, 544 and 450 nm, but each should
fall near the absorption peak of one dye. `portra_decompose.py` reports the
condition number of the crosstalk matrix, which runs 1.40 to 1.67 across the
twelve C-41 stocks on this light source. A value near 1.0 means the channels
separate the dyes cleanly. A markedly larger value means they do not resolve
the dyes, and no later stage recovers that.

No public dataset supplies the illuminant spectrum of another rig. This
measurement is the one irreducible piece of new work.

### Then rebuild and read the metrics

Every engine reports its node-solve residual, its interpolation error and its
serialised round trip when it finishes. **Current state by stock** in
[PROJECT.md](PROJECT.md) lists what this apparatus produces, so a materially
worse residual points at the new inputs. The per-roll anchoring step stays
the same and is still required.

## Limitations

> [!WARNING]
> Please read this section before relying on anything above.

- **No figure has been checked against a reference measurement.** The
  transforms behave as intended qualitatively on real scans, but every figure
  in this repository is the model reporting on itself. The missing test is a
  grey-ramp exposure series, a ColorChecker frame and colour-separation
  wedges, read on a spectrophotometer. For reversal, one scan of a
  transmissive IT8 target would give the same check: the target ships with
  per-batch reference colorimetry in the output space of the tables.
- **The modelled dyes cannot reliably tell the C-41 stocks apart.** No
  manufacturer publishes per-layer dye spectra for still film. Three dye
  curves are inferred from one aggregate published curve, and one spectrum
  cannot determine three components.
- **Their orange masks do differ**, by 0.346 D across the twelve stocks, read
  directly from the datasheets with no dye inference. The difference reaches
  the print tables away from the neutral axis only. Greys render essentially
  identically between stocks by construction, and saturated colours differ by
  up to 5.5 ΔE2000. A grey card cannot tell the print tables apart; their
  per-stock signature lies in saturated colour.
- **Interimage effects are not modelled.** They arise during development, so
  a developed film already carries them in its measured densities. The
  pipeline cannot predict them from datasheet data. Reversal film relies on
  them more, because a transparency has no orange mask to carry the same
  correction.
- **The print branch renders an idealised print, by design.** It reproduces
  the colour treatment, dye set, per-layer characteristic curves and
  gray-axis lock of the paper. It omits enlarger veiling flare, surface glare
  and viewing surround, which have no measured values. A physically viewed
  print looks softer than the render; set final contrast in the adjustment
  node ahead of the print cube. No physical print has been measured against
  the path, and the enlarger and viewing illuminants are nominal.
- **The scan tables embed one light source and a monochrome camera.** They
  assume a monochrome sensor of flat spectral response, which cancels out of
  a density measurement. A response that varies across an LED band does not
  cancel. No monochrome sensor has been measured, so the sensor-free build is
  an approximation with no established bound; the error budget carries a
  labelled scenario in its place. The illuminant is one measured set of LEDs.
- **A Bayer camera departs from the shipped tables by an amount that grows
  with density.** Across forty-four measured camera sensitivities, read
  through the orange mask of a colour negative as the tables do, scan-space
  density moves under 0.007 D in a light tone, 0.12 D at a dense neutral and
  0.17 D at a dense saturated colour. Green moves most, because its LED is
  twice the width of the other two. The mask passes red far better than blue,
  which raises the weight of the long-wavelength tail of every LED. Below
  roughly a third of maximum density the sensor is a second-order term. Above
  it, the shift exceeds the surrogate-basis uncertainty of the project,
  0.027–0.049 D. No second physical camera has scanned film through the
  chain.
- **The reversal tables lose accuracy in the deepest shadows.** Against the
  full chain under tetrahedral lookup, the maximum error is 0.001 D up to a
  dye density of 2.0 and 0.006 D up to 2.5, rising to 0.30 D by 3.4. With no
  colour filter to band-limit the spectral tails of the light source, a
  monochrome sensor cannot resolve the densest, most saturated states of a
  transparency. The table then holds the nearest colour the scanner model
  closes on, which the film cannot always produce (a share of those solutions
  carries a negative dye amount; PROJECT.md gives the counts). Lowering the
  corridor from 6.0 to 5.0 D recovers part of the error, and no corridor
  recovers the rest. A build named to a camera avoids it: 0.0005 D throughout
  on the a7R III, and 0.0006 D on the GFX 100 except Velvia 50 at 0.0021 D.
  The colour-negative and ADX16 tables are unaffected, with round trips
  within 0.004 D across the range those films occupy.
- **The Vision3 scene tables are a model estimate, unvalidated off the
  neutral series, and lose precision in deep shadows and at the top of each
  layer curve.** The neutral series of the datasheet fixes one path through
  the colour response of the film. The tables assume the simplest rule off
  that path. A different rule reproduces the same neutral and decodes colours
  differently, and only separation exposures on a measured roll can choose
  between them. The output is linear exposure on a lattice uniform in density.
  Under tetrahedral lookup, interpolation departs from the exact chain by
  1.6–1.9% on average within the published characteristic span of each stock.
  80–85% of that span lies in cells whose corners all converged inside the
  published curves, at 1.5–1.7% mean and 7–8% at the 99th percentile. Cells
  that straddle a shoulder carry the tail, to 48%, and a ColorChecker four
  stops under nominal exposure reads up to 22–97% off in its worst channel.
  That tail is lattice error, reducible by finer sampling, on a model that is
  itself steep at the shoulder: there a small density change is a large
  exposure change, and every input error grows. Beyond either end of a
  published curve the inverse clamps, so it synthesises no exposure the sheet
  never documented. The build reports an operating region, clean cells below
  a hundred times mid-grey, separately; the table carries no mark of it. The
  colour matrix is fitted on measured reflectances to 2.2–2.6 ΔE2000 mean on
  its own training set, and no frame has been checked against a known scene.

[PROJECT.md](PROJECT.md) gives the evidence for each item under **Known
limitations**, with the bounded systematics register that quantifies every
effect currently known.

## Documentation

- **[docs/resolve.md](docs/resolve.md)**: using the tables; capturing and
  measuring a roll; the node chain for each process.
- **[docs/method.md](docs/method.md)**: how the transforms are derived, and
  where their numbers come from.
- **[BUILDING.md](BUILDING.md)**: the command behind every table, per-camera
  builds, and the reversal corridor for a new body.
- **[PROJECT.md](PROJECT.md)**: the full technical reference; engines, every
  known systematic error, a glossary, invariants and known limitations.
- **[DATASHEETS.md](DATASHEETS.md)**: every source datasheet, with its
  publication code.
- **[knowledge/](knowledge/)**: literature notes behind the modelling
  decisions, each rating its sources for reliability.

## Related projects

This repository names two open-source projects. Neither contributes code or
data. Both are cited because the boundary against them is load-bearing.

**[NamiColor](https://github.com/Wavechaser/NamiColor)** (GPL-3.0) is a
generic film-scan lineariser: a logarithm, then a per-channel gain and offset
aligned by eye on a neutral reference. The nodes here perform the same
channel alignment, spectrally derived and metrically anchored. One
substitution fails: its negatives mode takes the logarithm of a quantity that
is already a density, which is not the inverse `Density to Linear.dctl`
supplies. Nothing is taken, so the obligations of GPL-3.0 do not arise.

**[spektrafilm](https://github.com/andreavolpato/spektrafilm)** (CC BY-SA 4.0)
is a forward film simulator that reaches the same datasheet-spectral
principles independently. This project adopts two architectural ideas from
it, the DIR matrix as an interimage stage and grey-ramp pre-compensation, and
implements both independently. Neither gates a shipped table, and the
interimage stage stays at identity. Its measured quantities are deliberately
left out, for two reasons. On evidence, its per-stock dye densities come from
an unpublished refinement of a generic seed. On licence, its terms treat a
lookup table as a direct encoding of the profiles behind it, so a `.cube`
derived from that data would carry share-alike terms. [PROJECT.md](PROJECT.md)
sets out both boundaries, including the evidence that the spektrafilm
representation conflates crosstalk unmixing with the orange mask.

## Licence

The code in `engine/` and `dctl/`, and the documentation, are
[MIT](LICENSE). The released `.cube` files and the digitised data in `data/`
are [CC BY 4.0](LICENSE-DATA), with attribution required on redistribution.
The exception is `data/cameras/`, the measured camera sensitivities, imported
from the Academy Software Foundation's `rawtoaces-data` library and still
under its Apache-2.0 licence.

The manufacturer datasheets are copyright Kodak, Kodak Alaris and Fujifilm,
and are **not** distributed here. They are freely available product
literature, and [DATASHEETS.md](DATASHEETS.md) gives the publication code for
each. The curves in `data/` are this project's own tracing of those
documents. The pipeline builds from `data/` alone; the PDFs are needed only to
re-run the digitisers.

## Credits

Built by [OwlMightyCh](https://github.com/OwlMightyCh) with
[Claude](https://claude.com/claude-code) (Anthropic), specifically Opus 5.5,
Opus 5, Opus 4.8, Fable 5 and Fable 5.1, which contributed to the engines,
the datasheet digitisers, the dye-fit modelling, the methodology reviews and
the documentation. Gemini 3.8 Flash (Google) contributed front-end design.
The published commit carries a `Co-Authored-By` trailer for each. GPT-6 Astra,
an external methodology reviewer, reproduced the error budget, the artifact
probes and the Academy comparison independently. It found the defects in the
sign symmetry, patch reachability and basis propagation of the budget, the
operating-region test of the scene tables, and the monochrome-cancellation
wording. The shipped tables and documents carry each correction.

Direction, the physical apparatus, every measurement decision and the
judgement of what counts as evidence are the author's. The light source was
bought at retail, and its maker had no part in this work.
