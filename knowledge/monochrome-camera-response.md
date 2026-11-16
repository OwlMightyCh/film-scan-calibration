# Monochrome camera response: what a published quantum-efficiency curve supplies, and what a calibration still needs

Collected 2026-11-16. The question this note answers is what the spectral
response of a monochrome camera does to a narrowband density scan, which
published data can stand in for a measurement of that response, in which unit
the data must enter the scan model, and what a calibration of one particular
camera still has to supply.

The scan engines integrate each LED's spectrum against a sensor response. The
shipped monochrome tables set that response to a constant, and the project has
measured no monochrome sensor (PROJECT.md register #9). This note reviews the
one published measurement found as numbers and carries it through the scan
model as a conditional case.

**Headline finding: one traceable measurement of a monochrome
detector-and-window assembly is published as a table, the Sony IMX455 behind
the QHY600M-PH camera window. Converted to the unit the scan model integrates,
it changes the modelled Status M output by at most 0.024 D on the sheet
neutral series of the twelve negative stocks and by 0.10 to 0.13 D at the
worst state of a uniform dye box. It is a model input for that assembly; it
sets no bound for monochrome cameras in general, and no film has been scanned
through such a camera here.**

Two subsidiary findings shape everything below.

- First, the unit decides the size of the effect. Quantum efficiency counts
  electrons per photon, and the LED spectrum is documented as a power
  distribution, so the response the model needs is wavelength times quantum
  efficiency. Entering the published curve unconverted about doubles the
  modelled differences on the C-41 neutral populations, multiplies the worst
  dye-box states several times and reverses the sign of the blue-band slope
  (§2, §5).
- Second, a camera response is a property of the whole optical stack. The held
  curve of a colour body with the same sensor designation falls across the red
  LED band about nine times faster than the response of the measured assembly.
  The held data do not say which component causes the difference, so a sensor
  designation alone does not transfer a curve from one camera to another (§6).

---

## 0. Provenance and confidence

| Tier | Source | Status |
|---|---|---|
| **A, peer-reviewed paper** | E. O. Ofek et al., "The Large Array Survey Telescope – System Overview and Performances", *Publications of the Astronomical Society of the Pacific* 135(1048):065001, 2023, doi:10.1088/1538-3873/acd8f0; preprint arXiv:2304.04796 | Preprint source read at the quantum-efficiency subsection; its Table 3 (wavelength, efficiency, uncertainty) read in full as the machine-readable file in the preprint bundle. Journal copy of the table not obtained (the publisher's page did not serve it to a script), so the two copies are not compared. SHA-256 of the file read: `e0d206dcaa90ea6020f36792104cd821e327aa5667523e6c74103c8d3a0a540e`. The DOI registry lists the version of record under CC BY 3.0; the preprint carries arXiv's non-exclusive licence |
| **A, peer-reviewed paper** | M. R. Alarcon et al., "Scientific CMOS Sensors in Astronomy: IMX455 and IMX411", *PASP* 135:055001, 2023, doi:10.1088/1538-3873/acd04a; preprint arXiv:2302.03700 | Preprint source read at the optical-bench and quantum-efficiency sections. The curve is a figure; the values used here are the ones its text states. The DOI registry lists publisher copyright |
| **A, conference paper** | A. S. Gill et al., "A low-cost ultraviolet-to-infrared absolute quantum efficiency characterization system of detectors", Proc. SPIE, *X-Ray, Optical, and Infrared Detectors for Astronomy X*, 2022, doi:10.1117/12.2627564; preprint arXiv:2207.13052 | Preprint source read at the theory, window-transmission and results sections. Its IMX455 curve is a figure; the values quoted for it are as reported by Alarcon et al. |
| **B, manufacturer article** | QHYCCD, "Measuring the absolute QE of the QHY268M", dated 2021-05-24 | Page text read in full; its curves are images and were not traced |
| **B, software and data of a standards body** | Academy Software Foundation, the ACES raw converter and its camera data library | Converter core source read at the routines that integrate a camera curve with an illuminant; library schema, one illuminant file and two camera files read. The 44 camera files held in this repository reproduce that library's values verbatim in a different file layout (Apache-2.0). The converter's use of a curve shows the intended convention; it does not verify how each contributor prepared a measurement |
| **model calculation** | Every figure marked *computed here* | A calculation on the repository's measured LED spectra, traced dye and mask data and held camera files, at the model state of 2026-11-16, by the expression, support, population and statistic stated beside it. The outside input is fixed by the table hash in the first row. The constant-response tables are the shipped ones, recorded in the shipped cube manifest (SHA-256 of the manifest file `7bb2e8c2601d9d90053bf03f7feb59f7a7cad2f4c16ff556d2b0e93aef45eb55`). The measured-response tables are scratch builds of 21 tables each, made by the shipped engines from that data state, and are not shipped. Their identity is a digest: the SHA-256 of the lines "file SHA-256, two spaces, relative path", sorted by path. Power reading `338cb5a4d4f768d230a9ab1cf7f330c22084202a4ac56edad79acd68b9deba04`; photon reading `c12f20cffc76a51c117611ba90fd3ece015495978d1ea2eac0209cf7f61d754f`. No film was scanned and no camera was measured |

The tier-A papers on the IMX455 describe measurements of astronomical cameras.
No source in the table concerns film scanning, and every statement about scan
density below is a calculation of this note.

---

## 1. What the response does in a density measurement

A scan channel reads

    D = -log10( ∫ L(λ) R(λ) T(λ) dλ / ∫ L(λ) R(λ) dλ )

with `L` the LED spectrum, `R` the sensor response and `T` the transmittance of
the film. For a negative, the roll anchor divides the base out in integrated
density, so the weighting also carries the mask, `L · R · 10^(-Dmin)`
(PROJECT.md register #17).

- **A constant response cancels in the ratio.** PROJECT.md register #9 records
  the check, 2e-16 D. Absolute sensitivity, gain and exposure therefore carry no
  information the tables use.
- **A response that varies across a band re-weights the band.** Write the
  response as a constant times `1 + ε f(λ)`. To first order in `ε` the reading
  changes by

      δD = -(ε / ln 10) · ( ⟨f⟩_wT - ⟨f⟩_w )

  where `⟨f⟩_w` is the mean of `f` under the weight `w` (the LED spectrum, times
  the mask term for a negative) and `⟨f⟩_wT` is its mean under `w · T`. This
  form holds for any band shape and any film spectrum.
- **Two further approximations give a rule of thumb.** If `f` is linear in
  wavelength, the response has a fractional slope `s = ε f′` per nanometre and
  moves the centroid of the band by `s · σ²`, with `σ` the standard deviation
  of `w`. If the spectral density of the film is also close to linear across
  the band, with slope `D′`, and varies little across it, `ln(10) · |D′| · σ ≪ 1`,
  the reading changes by that shift times `D′`. A broad band, a steep or
  curved film spectrum, or a reading that comes from a weak tail of the LED
  breaks the second condition, and the integral form applies.
- **The three bands differ in width.** *Computed here* on 400 to 700 nm at
  1 nm from the measured LED spectra, each normalised to unit sum: centroids
  637.2, 550.2 and 453.3 nm; standard deviations 11.1, 21.8 and 20.1 nm in
  R, G and B. The half-height widths are 15, 32 and 15 nm (PROJECT.md register
  #9); the blue standard deviation exceeds its half-height width because that
  LED carries a weak plateau from 540 to 660 nm.
- **The plateau governs the dense-yellow case.** Once yellow dye absorbs the
  blue peak, the blue reading comes from the plateau, where the response of a
  silicon sensor differs most from its value at 450 nm. The rule of thumb
  fails here.

---

## 2. Quantum efficiency, responsivity and the unit the model needs

**Quantum efficiency is a per-photon quantity.** Gill et al. write the
relation out: the electrons collected per second equal the quantum efficiency
times the incident power divided by the photon energy `hν`. Per unit of radiant
power the response is therefore proportional to wavelength times quantum
efficiency. A normalised density reading cancels the constants `h` and `c` and
keeps the wavelength factor.

**The scan model multiplies the LED spectrum by the response directly**, so the
response must be expressed per unit of whatever the LED file records.

- The LED file is documented as a spectral power distribution (PROJECT.md,
  Source data). The export convention of the instrument that produced it is
  unrecorded, which leaves the photon-flux reading open (§8).
- The held colour-camera files label their values "relative". The converter
  they were prepared for integrates them against an illuminant channel named
  `power`, computed from Planck's law in radiant terms, so their convention by
  use is response per unit power. Under the documented power interpretation of
  the LED file they need no conversion. If the LED file is a photon-flux
  spectrum, each held curve must be divided by wavelength before use.
- This note therefore carries two alternative unit hypotheses. The **power
  reading** takes the response as wavelength times quantum efficiency and is
  the one the documentation supports. The **photon reading** takes the quantum
  efficiency as it stands and is correct only if the LED file is a photon-flux
  spectrum. One of the two is true of the file. Together they span no
  uncertainty of the sensor, the optical stack or an unmeasured wavelength.
- Every comparison with a held colour-camera file in this note uses the power
  reading on both sides.

*Computed here*, on 400 to 700 nm at 1 nm: the slope of the logarithm of the
response across each LED band, by least squares weighted with the normalised
LED spectrum, expressed as the fractional change over 10 nm in per cent, and
the resulting centroid shift against a constant response.

| case | slope R | slope G | slope B | centroid shift R / G / B (nm) |
|---|---|---|---|---|
| photon reading, quantum efficiency | −3.96 | −2.80 | −0.61 | −0.51 / −1.27 / −0.16 |
| power reading, wavelength × quantum efficiency | −2.41 | −1.05 | +1.39 | −0.30 / −0.48 / +0.56 |
| the wavelength factor alone | +1.61 | +1.80 | +2.02 | |

The wavelength factor is larger than the 1 % per 10 nm tilt that PROJECT.md
register #9 uses as its illustration, and in the blue band it outweighs the
sensor's own slope. A response entered in the wrong unit is an error of the
same order as omitting the response altogether.

**Relative and absolute curves serve equally.** The QHYCCD article states that
Sony publishes its curves normalised to a peak of 1, and it derives an absolute
curve for the IMX571 by comparing one camera with a reference sensor of known
efficiency through a single narrowband filter near 500 nm, then scaling the
whole relative curve. Its result is a peak of at least 90 %, between 90.2 and
95.9 % according to which of two literature values is taken for the reference.
The two kinds of curve differ by one constant, which cancels in a density
reading; the shape is the manufacturer's in both. Such a scaled curve adds no
independent evidence of shape.

---

## 3. What a camera response curve already contains

A camera spectral sensitivity is measured from the raw output of the complete
camera while the wavelength of the light is stepped. It is the product of
everything between the light and the raw value: the silicon, the microlenses,
the colour filter array, the infrared and ultraviolet cut stack and any lens in
the path. The 44 held files are such curves, and the scan engines use each as
the whole response of that body. No separate quantum-efficiency factor applies
to them.

*Computed here*, as an illustration on the one sensor designation held in both
forms: each channel of the held Sony a7R IV file divided by the power-reading
response of the IMX455 assembly, on 400 to 700 nm at 5 nm. All three quotients
are scaled by one factor, the largest value over the three channels.

- The three quotients peak at 590 nm (R), 530 nm (G) and 450 nm (B), the
  ordinary positions of dye filters.
- At 400 nm they read 0.02, 0.02 and 0.10, and at 700 nm at most 0.002. The
  quantum efficiency of the monochrome assembly is 0.73 of its peak at 400 nm
  and 0.47 at 700 nm (the latter interpolated, §4). The two effective
  responses therefore differ most at the two ends of the range.

The quotient compares two effective responses and identifies no component. The
held file records neither the lens nor the filter stack of its measurement, the
divisor includes the QHY window, and the two measurements come from different
laboratories and different units of the sensor.

---

## 4. The published measurement

**Method.** Ofek et al. measured the IMX455 "including the QHY600M-PH window"
on a double monochromator. A beam splitter fed a reference diode in parallel
with the detector under test. The reference diode was first calibrated against
a NIST-traceable detector placed in the measurement beam, and the camera then
took its place. A holmium-didymium absorption filter, itself calibrated against
gas-lamp emission lines, fixed the wavelength scale in every run. The authors
give the limit of the method as the variation of the light source, of the
order of 1 % in flux, because the camera exposure could not be synchronised
exactly with the reference.

**The table.** Read from the preprint bundle: wavelength, efficiency and
uncertainty from 300 to 1098 nm, 1,213 points between 400 and 700 nm, median
stated uncertainty 0.58 % of the value in that range. The efficiency peaks at
0.868 near 485 nm and reads 0.633 at 400 nm, 0.838 at 450 nm, 0.785 at 550 nm,
0.559 at 640 nm and 0.437 at 690 nm (5 nm bin means). The table has no point
between 691.55 and 722.04 nm, and the paper gives no reason.

**Reduction used in this note.** The mean of the points in each 5 nm bin from
380 to 780 nm, at least three points per bin, empty bins omitted; the same
curve in all three channels; linear interpolation between bins, which bridges
the missing interval between measured bins on both sides. The binned curve is
not monotonic in the red: it rises slightly from 625 to 630, 640 to 645 and
670 to 675 nm.

*Computed here*, power reading, Portra 400 dye set through its mask, 400 to
700 nm at 1 nm, scan density in D, over six dye states: equal amounts of 0.3,
1.2 and 2.5 of all three dyes, and each single dye at 2.5.

- **Binning.** Against a piecewise-linear curve through every original point,
  the binned curve moves the reading by at most 0.0004 D. The maximum is the
  blue channel under yellow 2.5.
- **The missing interval.** Holding the 690 nm bin up to 720 nm, or applying
  the 720 nm bin from 690 nm, moves the reading by at most 0.0019 D against the
  linear bridge, again in the blue channel under yellow 2.5.
- **The Vision3 support.** The Vision3 dye set is integrated on 402 to 798 nm
  at 1 nm. On that grid each LED carries 0.1 % of its energy above 700 nm and
  none above 780 nm, where the reduced response ends, so the treatment of the
  response beyond 780 nm changes no figure. The two bridge alternatives move
  the Vision3 reading by at most 0.0001 D at equal 2.0 and cyan 2.0.

These results cover scan density at the states named. The alternatives were
not carried through the table comparisons of §5, where an inverse can enlarge
a small change of input. The two bridge alternatives are scenarios and bound
nothing: the shape of the response inside the missing interval is unmeasured.

**Other reports on the same sensor.** They give coarse descriptors of the
shape of the curve from other laboratories and units.

- Alarcon et al. measured a QHY600M Pro on a monochromator bench at 25 nm steps
  with ±1 nm bandwidth against a photodiode reference, with a stated
  systematic uncertainty of about 2 %: a peak of 80 % at 475 nm and 40 % at
  700 nm. They report the manufacturer's curve as 92 % at 450 nm and 46 % at
  700 nm, and that of Gill et al. as 93 % at 480 nm and 42 % at 700 nm.
- The ratio of the 700 nm value to the peak is 0.50, 0.50 and 0.45 in those
  three reports and 0.47 in the Ofek table, whose 700 nm value is itself
  interpolated across the missing interval. Spread evenly over the roughly
  225 nm between peak and 700 nm, a range of 0.45 to 0.50 equals about 0.5 %
  per 10 nm. That figure is an illustrative equivalent over a broad interval.
  It says nothing about the slope inside one LED band, the peaks sit at
  different wavelengths, and two stated points per report cannot separate a
  laboratory bias from a difference between units.
- Alarcon et al. also observed optical etaloning as a spatial variation across
  the frame: with ±1 nm light the frame varies by about 1 % around its mean at
  650 nm and by 10 % at 850 nm and beyond. Fringing is one possible cause of
  the small rises in the binned curve, which the Ofek paper does not discuss.
  No source gives the spectral period of the fringes, so whether an LED band
  averages over them is unknown.
- Gill et al. note that a commercial camera normally has a window over the
  sensor and that the window's transmission must be measured separately to
  isolate the sensor. The Ofek table makes no such separation and describes the
  assembly.

---

## 5. Modelled effect on this apparatus

Every figure in this section is *computed here* and is a model sensitivity: the
change in modelled output when the constant response is replaced by the
measured one. The film model is the same on both sides, and the project holds
no measured check of any part of the C-41 chain (PROJECT.md, Known
limitations), so none of these figures is an observed scanning error.

**Scan density, response minus constant**, Portra 400 dye set through its
mask, 400 to 700 nm at 1 nm (D, R / G / B). "Equal" states carry the same
amount of each dye and are test states, distinct from the sheet's neutral
series.

| dye state | power reading | photon reading |
|---|---|---|
| equal 0.3 | −0.0006 / +0.0018 / +0.0001 | −0.0009 / +0.0041 / +0.0007 |
| equal 1.2 | −0.0022 / +0.0082 / +0.0003 | −0.0036 / +0.0190 / +0.0040 |
| equal 2.5 | −0.0048 / +0.0165 / +0.0008 | −0.0078 / +0.0387 / +0.0145 |
| cyan 2.5 | −0.0074 / −0.0048 / −0.0017 | −0.0124 / −0.0113 / −0.0037 |
| magenta 2.5 | +0.0010 / +0.0341 / +0.0016 | +0.0016 / +0.0673 / −0.0011 |
| yellow 2.5 | +0.0001 / +0.0031 / +0.0048 | +0.0002 / +0.0080 / +0.1107 |

Green carries most of the effect on neutral states, the green band being the
widest. The dense-yellow blue reading depends most strongly on the unit: the
wavelength factor nearly offsets the fall of quantum efficiency between 450 nm
and the 540 to 660 nm plateau.

**Table against table.** Twenty-one scan tables were built with the measured
response in each reading. Seventeen are compared with the shipped
constant-response tables: twelve C-41, four reversal and the ADX16 table. The
four scene-linear Vision3 tables are built and left out (last bullet below).

- **Procedure.** For a dye state, the scan density is computed as the measured
  response would read it. Both tables are then read at that density by
  tetrahedral lookup.
- **Metric.** For C-41 and ADX16 it is the absolute difference of the two
  outputs, taken as the largest of the three channels. For reversal it is the
  CIE 1976 ΔE\*ab between the two outputs, each a D50-relative XYZ for the CIE
  1931 2° observer converted to L\*a\*b\*.
- **Support.** C-41 on 400 to 700 nm at 1 nm, through each stock's mask;
  reversal on each stock's own dye grid, with no mask; ADX16 on 402 to 798 nm
  through the Vision3 minimum density.
- **Populations.** The sheet's neutral series; equal-amount states (0.3, 1.2
  and 2.2 for C-41; 0.3, 1.0, 2.0 and 3.0 for reversal; 0.3, 1.0 and 2.0 for
  ADX16); and a uniform 7 × 7 × 7 dye box used as a stress test.
- **The sheet's neutral series** is every exposure at which the sheet gives
  all three Status M characteristic curves, 186 to 212 per stock, with the
  three curves solved together into dye amounts. The solve is unconstrained,
  and at the toe it returns amounts as low as −0.24.
- **Boundary states.** No state exceeded the upper end of its table. On seven
  of the twelve C-41 stocks the modelled scan of the sheet series falls below
  zero density at the toe, on 11 to 63 exposures per stock and down to
  −0.20 D, and the lookup clamps those states at the table boundary. The
  sheet-series rows below include them. Over the subset that stays inside the
  table the maxima are unchanged in both readings, 0.007–0.024 and
  0.015–0.058 D.

| route and population | power reading | photon reading |
|---|---|---|
| C-41, sheet neutral series, maximum, range over 12 stocks (D) | 0.007–0.024 | 0.015–0.058 |
| C-41, sheet neutral series, mean, range over 12 stocks (D) | 0.002–0.007 | 0.005–0.018 |
| C-41, equal 0.3 / 1.2 / 2.2, Portra 400 (D) | 0.002 / 0.012 / 0.029 | 0.005 / 0.028 / 0.068 |
| C-41, equal 2.2, range over 12 stocks (D) | 0.016–0.041 | 0.032–0.114 |
| C-41, dye box 0–2.2, 95th percentile, range over 12 stocks (D) | 0.055–0.077 | 0.148–0.440 |
| C-41, dye box 0–2.2, maximum, range over 12 stocks (D) | 0.097–0.134 | 0.41–1.43 |
| reversal, equal 0.3 to 3.0, maximum over 4 stocks (ΔE\*ab, D50) | 0.19 | 0.23 |
| reversal, dye box 0–2.5, mean, range over 4 stocks (ΔE\*ab) | 0.26–0.36 | 0.55–0.67 |
| reversal, dye box 0–2.5, maximum, range over 4 stocks (ΔE\*ab) | 1.14–1.44 | 2.46–4.08 |
| ADX16, equal 0.3 / 1.0 / 2.0 (code values) | 11 / 48 / 133 | 26 / 110 / 300 |
| ADX16, dye box 0–2.0, maximum (D of printing density, code / 8000) | 0.108 | 0.433 |

- **The control is an implementation check.** Reading the constant-response
  table at the constant-response scan and the measured-response table at the
  measured-response scan gives the same output to a mean of 0.0002 D over the
  Portra 400 dye box in both readings, with a maximum of 0.0035 D under the
  power reading and 0.0031 D under the photon reading. Both tables invert one
  film model, so this agreement tests the lookup and the serialisation and
  nothing about the film.
- **The reversal corridor.** The four reversal stocks need 3.87 to 4.76 D at a
  dye amount of 4.0 under the power reading, inside the 5.00 D corridor of the
  monochrome tables; the reversal tables were built at 5.00.
- **Scale against the held colour bodies.** Each of the 44 held colour
  responses was compared with the same constant response on the same states:
  Portra 400 through its mask, 400 to 700 nm at 1 nm, absolute difference of
  scan density, power reading. In green the 44 bodies sit 0.086 to 0.129 D
  from the constant response at equal 1.2 (median 0.108) and 0.194 to 0.312 D
  at equal 2.5 (median 0.254). The monochrome assembly sits 0.008 and 0.017 D
  from it. In red the ranges are 0.014 to 0.026 D and 0.029 to 0.057 D against
  0.002 and 0.005 D; in blue 0.018 to 0.023 D and 0.067 to 0.082 D against
  0.0003 and 0.0008 D. On these states every held colour body lies further
  from the constant model than the measured assembly does.
- **The scene-linear Vision3 route** was built and is not reported: its
  comparison needs each stock's own dye and mask set, which this calculation
  did not use.

---

## 6. Filter stacks and converted colour bodies

The IMX455 is widely reported as the sensor of the Sony a7R IV; this note has
no primary source for that identity. The held a7R IV file is a
power-convention curve of that complete camera.

*Computed here*, on 400 to 700 nm at 1 nm, power reading:

- **Two effective responses.** The slope of the a7R IV's own channel across
  each LED band is −22.05, −16.51 and −15.22 % per 10 nm in R, G and B,
  against −2.41, −1.05 and +1.39 for the monochrome assembly.
- **Their ratio in the red.** The a7R IV red channel divided by the response
  of the assembly, normalised at 600 nm, reads 0.66 at 620 nm, 0.43 at 640 nm,
  0.20 at 660 nm and 0.08 at 680 nm. The ratio contains the red dye filter,
  the cut stack, the lens of the measurement and any difference between the
  two units and laboratories. The held data cannot separate them.
- **A conditional experiment.** Suppose a monochrome camera carried that whole
  ratio above 600 nm on top of the response of the assembly. Through the
  Portra 400 mask the red centroid then moves from 637.05 to 634.12 nm, and
  the red scan density differs from the constant-response reading by −0.006 D
  at equal 0.3, −0.025 at 1.2, −0.054 at 2.5 and −0.084 at cyan 2.5, against
  −0.0006, −0.0022, −0.0048 and −0.0074 for the assembly alone.

The experiment shows the size of the effect when a roll-off of that steepness
lies inside the red band: about ten times the effect of the assembly. It
attributes the roll-off to no component and predicts nothing about a colour
body whose filter array has been removed. Such a body may keep its stock cut
stack, receive replacement glass or lose its microlenses, and the effective
response is unmeasured in every one of those states. The general point is
independent of the cause: these LEDs carry 0.1 % of their energy above 700 nm
(§4), so a filter matters here through any slope it has inside a band.

The transferable statement is narrow. The published table describes the
QHY600M-PH assembly. Another camera with the same sensor designation needs its
own effective response, measured or shown equivalent, before the table is used
for it.

---

## 7. What a calibration has to supply

**The quantity.** The relative response of the complete capture path: sensor,
window, any retained filter stack and the scanning lens. The coverage is every
wavelength at which transmitted LED light contributes materially to a reading.
The bands are 15 to 32 nm wide at half height, and selective absorption raises
the weight of the weak tails: the blue band's plateau extends the requirement
to 660 nm. Absolute scale is unnecessary.

**The unit.** Response per unit of the quantity the LED spectrum records. A
quantum-efficiency curve is multiplied by wavelength for a power spectrum and
used as it stands for a photon-flux spectrum. A power-convention camera curve
is used as it stands for a power spectrum and divided by wavelength for a
photon-flux spectrum.

**The form.** The scan engines accept one response curve per channel, and
PROJECT.md register #9 notes that a monochrome user writes the same measured
curve into all three.

**The uncertainties, kept apart.**

- Stated measurement uncertainty: a common scale error cancels, and only its
  wavelength-dependent part reaches a density.
- Unmeasured intervals: interpolation between measured points is a scenario
  with alternatives (§4).
- Unit-to-unit variation, the window and the lens: no measured distribution
  exists for any of them. The reports in §4 give two coarse points each and no
  local slope.
- A window already included in a measurement is applied once only.

**A check outside the film model.** Coloured transmission patches whose
spectral transmittance has been measured can be scanned with the actual
camera, lens and LEDs.

- **The observable.** For each LED channel, the ratio of the patch reading to
  the reading of a clear reference of known transmittance, captured in the
  same geometry. Both readings are dark-subtracted, linear and unsaturated.
  The ratio cancels the scale of the channel; a ratio between channels keeps
  it and is unsuitable.
- **The prediction.** The same ratio computed from the measured transmittance,
  the LED spectrum and the candidate response, with no dye decomposition
  between them.
- **The patches.** Spectrally selective inside each LED band, and independent
  of any data used to derive the candidate response.
- **The criterion.** A stated uncertainty for each measured and predicted
  ratio, and a check in advance that the patches separate the candidates: the
  constant response, the power reading and the photon reading must predict
  ratios that differ by more than that uncertainty.
- **What agreement establishes.** It constrains the product of LED spectrum
  and response over the spectra of the patches tested. An error in the LED
  spectrum and a compensating error in the response remain indistinguishable,
  and the film decomposition and the output conversion remain untested.

A spectrally flat neutral wedge tests linearity and stray light. It is
insensitive to the shape of the response, so it supplements the coloured
patches and cannot replace them.

---

## 8. Open questions

- **The export convention of the LED spectrum.** Whether the file records
  radiant power or photon flux per wavelength interval decides between the two
  columns of §5, and decides whether the held colour-camera curves need a
  division by wavelength. The documentation names it a power distribution; the
  instrument setting is unrecorded and its confirmation is pending. Until it
  is confirmed, the power reading is the working assumption and both columns
  stay in this note.
- **The reduction and the bridge** were tested in scan density at six states
  (§4) and were not carried through the table comparisons of §5.
- **The sensor identity of the Sony a7R IV** rests on general report.
- **The journal copy of the Ofek table** was not obtained and is not compared
  with the preprint copy. Redistribution terms attach to the version of record.
- **The missing interval from 691.55 to 722.04 nm** has no stated cause in the
  paper. Whether the points were never taken or were removed is unknown.
- **No tabulated response was found** for any other monochrome sensor or
  camera body, for a manufacturer's relative curve as numbers, or for a colour
  body after removal of its filter array. The Alarcon curves for the IMX455
  and IMX411 exist as a figure only.
- **Variation between units, windows and lenses** has no measured
  distribution. The comparison in §4 rests on two stated points per report.
- **The scene-linear Vision3 route** has not been compared with each stock's
  own dye and mask set.
- **No film has been scanned through a monochrome camera in this project**, and
  no coloured patch has been measured as §7 describes. Every density figure in
  this note is a model calculation.
