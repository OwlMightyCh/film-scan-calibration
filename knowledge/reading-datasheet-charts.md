# Reading a film or paper datasheet: what each chart measures, and what it does not

Collected 2026-09-02. The transforms in this repository are built from three
kinds of chart – characteristic curves, spectral dye density, spectral
sensitivity – and from one measurement the scanner makes for itself, the
unexposed base; which charts a given route consumes differs (the scene and
print routes read all three, the ADX16 route reads the Vision3 dye, Minimum
Density and Midscale curves and no characteristic curve, the reversal route
its sheet's dyes and characteristic curves).

Each of those is a specific physical quantity with a specific
measurement geometry, and three of the pipeline's structural errors came from
reading one of them as something adjacent to what it is. This note states what
each chart is, in the manufacturer's own terms, and the reading the engines are
held to.

**Headline finding: a characteristic curve is an integral density of one
exposure series, never a per-layer quantity.** For the datasheet series
considered here, each channel reports the Status M or Status A density of a
patch through the whole processed material, all three dyes present at the
amounts that exposure formed, so the red curve carries the magenta and yellow
dyes' red absorption at those amounts. Given an assumed effective dye basis
and baseline, the three channel readings can be solved jointly for model dye
amounts, at each exposure, where the inverse is feasible and sufficiently
conditioned. Using those amount tables at independent layer exposures is a
further separability approximation that the curves alone do not validate.

---

## 0. Provenance and confidence

| Tier | Source | Status |
|---|---|---|
| **A, verified primary** | Kodak still-film datasheets for Portra, Ektar (E-4046), Gold, Ultra Max and Pro Image, each under its own publication code; Kodak H-1-5203/5207/5213/5219 (Vision3); Kodak E-4070 (Endura Premier); Fujifilm datasheets for the Fujicolor, Superia and Pro 400H negatives and the Pro Laser TYPE II paper | Held locally (not redistributed; DATASHEETS.md carries the per-stock codes and editions), traced by the digitisers, every trace replotted onto the ink |
| **A, verified primary** | SMPTE ST 2065-3:2020, *Academy Density Exchange Encoding* | Fetched from `pub.smpte.org`; Equation 1 and the D-min definition quoted below |
| **A, explicit 1995 entries verified** | ISO 5-3 Status M and Status A responsivities, as transcribed in `data/standards/` | All 35 Status A and 42 Status M explicit log entries match the public ANSI adoption of ISO 5-3:1995. The 2009 edition and runtime tail/interpolation conventions are separate questions. See `densitometry-standards-and-density-metrics.md` §2 and §6 |
| **model calculation** | Every figure marked *measured here* | A calculation from `data/` by the engines or by review scripts, on the model state of the date each figure gives (2026-09-02 unless stated); no film was measured. Where a figure's exact expression, input identity and population are not stated beside it, they are not recorded, and the figure should be recomputed on each use (§6) |

---

## 1. The characteristic curves

**What the sheet shows.** Three curves of density against log exposure,
labelled R, G, B (negatives, Status M) or by the paper's three records (Status
A). On the sheets used here the series is a single exposure series captioned
in outline only ("Exposure: Daylight" on the Portra 400 and Ektar 100 charts,
"Exposure: Daylight 1/100 second" on E100; §6 records what the captions omit),
read step by step on a three-channel densitometer; that it is a grey step
wedge behind balancing filtration is the usual sensitometric practice and not
a statement on the sheet.

Each curve is that densitometer's channel reading of the whole three-dye stack,
base and mask included. The three curves share one exposure axis because they
are one series of patches. Other characteristic curve measurements, the
separation exposures of the interimage note for one, are different series and
are not covered by this reading.

**What it is not.** It is not "the cyan layer's density against the cyan
layer's exposure". The Status M red responsivity sits on the cyan dye's peak
but also reads the magenta and yellow dyes' red absorption: on the Vision3
unit-peak dye set the magenta dye contributes 0.09 of the cyan reading and the
yellow dye under 0.01, and across the whole Status M matrix of the traced dyes
the off-diagonal terms run 0.01–0.12 of the diagonal (*measured here*); on the
Endura paper dyes the Status A off-diagonals run 0.02–0.12.

**The reading the engines hold to.** At every exposure on the shared axis the
three densities, base and mask removed, are the Status M (or A) of one dye
stack; the dye amounts are the triple that reproduces all three at once, given
the assumed dye basis and baseline (a three-channel solve, closing to machine
precision on every stock and paper traced, the four reversal sheets included;
closure states that the inverse is feasible on that basis; it says nothing
about whether the basis is right).

That gives, per layer, a table of dye amount against exposure on
the sheet's series – the only series on which the three curves are consistent
with one another. An off-neutral colour is rendered by looking each layer up
on its own table at its own exposure, which is a further separability
approximation the characteristic curves do not validate.

**What the wrong reading costs.** Reading one channel's curve at its layer's
exposure attributes the other layers' cross absorption to that layer. On
Vision3 it places the three layers' exposures 0.09–0.22 logH apart at midscale
and up to 0.44 logH apart at +1.5 stops on a neutral that satisfies the sheet;
on Endura it costs up to 15 ΔE2000 at saturated colours (*measured here*). Both
readings agree exactly on a neutral, which is why a neutral-axis check cannot
distinguish them. Register entries and Invariants in PROJECT.md carry the
figures.

**Terminal behaviour.** Past the plotted span the curve is unknown. The
engines extend a tone curve by its terminal slope (a curve that collapsed to
zero off its end would be a worse invention), but an INVERSE lookup, amount to
exposure, is clamped at the table's ends: past the shoulder the inverse slope is
enormous and a small overshoot in amount reads as many stops of exposure.

---

## 2. The spectral dye density chart

**What the sheet shows.**

- **Reversal and Vision3 sheets** plot three curves, one per image dye, each
  labelled as the spectral density of that dye alone, peak-normalised or at a
  stated concentration, the preparation and measurement protocol behind that
  label being unstated (orange-mask note §5c); the Vision3 chart adds two more,
  a solid Midscale Neutral, which is absolute (its Status M integrates to
  roughly 0.8 / 1.2 / 1.5 D across the four stocks, *measured here*, close to
  the 0.80 / 1.20 / 1.60 laboratory aim density), and a dashed Minimum Density,
  the base and unreacted coupler, also absolute, so that its caption "D-mins
  subtracted" applies to the three dye curves alone.
- **C-41 still-film sheets** plot two curves only: the spectral density of a
  midscale neutral patch and of the unexposed film (D-min), both including base
  and orange mask.
- **RA-4 papers** plot the three dyes.

**What it is not.** The C-41 midscale curve is not a dye set. It is one
spectrum, the sum of three dyes and the surviving mask; three components cannot
be recovered from it without a prior, which is the surrogate-basis fit and its
register #8 uncertainty.

The D-min curve is not a filter or a layer: it is the
whole minimum-density spectrum, support tint plus the unreacted coloured
couplers (see `orange-mask-and-the-scanning-workflow.md`, and the dye note's
caveat that B − R does not isolate one coupler), the coupler part maximal at
D-min and consumed as dye forms.

**Conventions that must match.** The per-dye curves used for a negative are
D-min subtracted: midscale minus D-min is the image-dye contribution, and the
Vision3 basis states the same convention in its `units`.

A chart's plotted range is its measured support; outside it nothing is known,
and a curve is held to the range its `digitization_audit.endpoints` publishes,
which varies by sheet (Ektar 100's dye chart ends at 684.9 nm, the other Kodak
still-film charts on or just inside the 700 nm frame, the Fujifilm charts to
717–719 nm, the Vision3 basis from 402 nm); cite each stock's own audit block.

---

## 3. The spectral sensitivity chart

**What the sheet shows.** Per layer, the logarithm of the reciprocal exposure
needed to reach a stated density above D-min (0.2 for Kodak), against
wavelength, under a stated exposing illuminant. Fujifilm sheets print the
ordinate as a relative scale bar with no absolute origin.

**What it is not.** It is not a colour-matching function and its absolute level
is not comparable between sheets (different reference densities and
illuminants).

It enters the scene route only as a relative weighting, from which a 3×3 is
fitted, and enters the print route as the paper's exposure kernel, whose
absolute scale the gray-axis lock absorbs. A relative axis is therefore
harmless where a per-layer offset is an exposure scale, and harmful only as a
wavelength-dependent shape error, which no chart bounds.

---

## 4. The base the scanner measures, and where subtraction happens

**What the roll anchor does.** The clear base (reversal) or unexposed rebate
(negative, mask included) is read by the same LEDs and the same sensor as the
frames, and each frame is divided by it in linear light. That is a subtraction
of INTEGRATED densities: what reaches the table is

```
−log10( ∫Φ·10^−(Dmin+dye·DYE) / ∫Φ·10^−Dmin ),
```

the image dyes as seen under the illuminant `Φ·10^−Dmin(λ)`, the LED filtered
by the base and mask.

**What it is not.** It is not the spectral subtraction the datasheet performs
when midscale minus D-min is formed. The two are not equal in general; a base
that is spectrally flat across each LED's band makes them equal (so does a
spectrally neutral dye absorption, a special case that does not arise here),
and a colour negative's mask is not flat: Portra 400's falls 0.11 D across the
green LED's 528–560 nm FWHM. The scan-side responsivity of a
masked negative is therefore the LED behind the mask, and the engines integrate
it that way (PROJECT.md register #17). The datasheet's spectral subtraction
belongs to the calibration side only.

**Consequences worth knowing.** The mask passes red far better than blue, so
every LED's long-wavelength tail gains weight behind it; for a unity-response
(monochrome) sensor the blue LED's 540–660 nm plateau then dominates the blue
reading under a dense yellow dye, and the channel saturates inside the
corridor. A colour filter removes that tail, which is why the camera-named
C-41 builds solve cleanly where the sensor-free ones do not (*measured here*).

ST 2065-3 subtracts the same way the anchor does: its Equation 1 encodes
`k × (APD − APD_Dmin) × 8000 + 1520` with `APD_Dmin` "the measured Dmin of the
sample", in integrated printing density, and the ADX16 engine forms exactly
that quantity from the traced Minimum Density curve.

---

## 5. A reading checklist

1. Which quantity is plotted: a per-dye spectrum, an integral density of a
   stack, a reciprocal exposure? Name it before using it.
2. On what series was it measured, and is that the series the model will use
   it on? Integral curves are consistent only on their own neutral series.
3. Where is the base: included (characteristic curves, C-41 spectral charts),
   excluded (per-dye spectra), or subtracted by the hardware in a different
   space (the roll anchor)?
4. What is the measured support, and what does the engine do past it? A hold, a
   zero fill, a terminal slope and a clamp are four different claims.
5. Does any check compare the model against a sheet quantity the inverse did
   not consume? If every check inverts the model with itself, nothing has been
   tested.

---

## 6. Open questions

- **The sheets state the exposing illuminant of their characteristic curves
  only in outline.** The Portra 400 and Ektar 100 charts are captioned
  "Exposure: Daylight" and E100's "Exposure: Daylight 1/100 second" (with the
  process and the densitometry status); what none of them states is the
  illuminant's spectral distribution, the balancing filtration, or the paper
  exposure convention. Whether the paper series was balanced for the paper's
  own printing filtration or for a reference negative is not stated on E-4070
  or the Fuji bulletin, and it bears on the absolute per-layer offsets the
  gray-axis lock solves for. A sensitometric daylight series is a neutral
  EXPOSURE series; that does not make every reconstructed patch a visual
  neutral under D50 (next bullets).
- **The Vision3 Minimum Density curve is printed dashed, and a dashed curve
  is traceable.** Its dashes are re-admitted from the text mask by stroke
  weight and island size, walked with the solid curves as crossings, and the
  gaps interpolated between measured dashes; the trace closes against the
  characteristic sheet's densitometer D-min triplet to within 0.045 D on all
  four stocks, reading slightly lighter throughout (*measured here*). What
  remains open is that residual's sign: whether the chart's dashed curve or
  the densitometer triplet is the better statement of the film's D-min, which
  no third source settles.
- **The reversal sheets' neutral series is not a visual neutral through the
  model.** Read as the note prescribes (three Status A curves solved together
  through the traced dyes, D-min subtracted in integrated density), each
  sheet's daylight series closes with non-negative amounts and then renders
  blue-green on the D50 table, by 2.7 to 7.4 units of b\* at mid-grey
  (*measured here*). The E100 dye chart's own equal-amount neutral passes
  through the same observer to 0.2 units. That shows the model can produce a
  near-neutral spectrum under the selected observer at equal amounts; it does
  not show the dyes are correct at the amount ratios the characteristic curves
  reconstruct, nor on the other three sheets, and it does not identify which
  of the characteristic-curve, dye, base, viewing or measurement model causes
  the reconstructed-series cast. Whether a sensitometric daylight series is
  meant to be a visual neutral at D50 is itself unresolved. Two bounds sit on
  the observer candidate: the Status A table's explicit entries match the
  1995 edition of ISO 5-3 exactly (densitometry note §0), and register #19's
  sensitivity test finds that shifting any Status A responsivity by ±10 nm
  moves b\* by at most 1.5, a placement bound and not a complete shape-error
  or tail bound. Separating the candidates would take matched spectral and
  Status A measurements of the same patches under known exposure and viewing
  conditions.
- **Whether a Status M densitometer's reading of a coloured-coupler mask equals
  the chart's D-min curve integrated against the Status M responsivities** is
  assumed without check; the chart's midscale integrates to a red density above
  the sheet's own grey-card corridor (PROJECT.md register #8), and no measured
  roll exists to settle which is right.
