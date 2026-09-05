# Reading a film or paper datasheet: what each chart measures, and what it does not

Collected 2026-09-02. Every transform in this repository is built from three
charts per material – characteristic curves, spectral dye density, spectral
sensitivity – and from one measurement the scanner makes for itself, the
unexposed base. Each of those is a specific physical quantity with a specific
measurement geometry, and three of the pipeline's structural errors came from
reading one of them as something adjacent to what it is. This note states what
each chart is, in the manufacturer's own terms, and the reading the engines are
held to.

**Headline finding: a characteristic curve is an integral density of a neutral
exposure series, never a per-layer quantity.** The red curve of a colour
negative or paper is the Status M or Status A red density of a patch in which
all three dyes are present at the amounts a neutral exposure formed. It carries
the magenta and yellow dyes' red absorption at those amounts. Three curves
therefore determine three dye amounts only when solved together, at each
exposure, on the neutral series they were measured on.

---

## 0. Provenance and confidence

| Tier | Source | Status |
|---|---|---|
| **A, verified primary** | Kodak E-4050 family (Portra, Ektar, Gold, Ultra Max, Pro Image); Kodak H-1-5203/5207/5213/5219 (Vision3); Kodak E-4070 (Endura Premier); Fujifilm datasheets for the Fujicolor, Superia and Pro 400H negatives and the Pro Laser TYPE II paper | Held locally (not redistributed; DATASHEETS.md carries the codes), traced by the digitisers, every trace replotted onto the ink |
| **A, verified primary** | SMPTE ST 2065-3:2020, *Academy Density Exchange Encoding* | Fetched from `pub.smpte.org`; Equation 1 and the D-min definition quoted below |
| **A, verified primary** | ISO 5-3 Status M and Status A responsivities, as transcribed in `data/standards/` | See `densitometry-standards-and-density-metrics.md` for the transcription's status |
| **repository measurement** | Every figure marked *measured here* | Computed from `data/` by the engines or by review scripts on 2026-09-02 |

---

## 1. The characteristic curves

**What the sheet shows.** Three curves of density against log exposure,
labelled R, G, B (negatives, Status M) or by the paper's three records (Status
A). The exposure series is a neutral: the manufacturer exposes a grey step
wedge, through the filtration that renders it neutral, and reads each step on
a three-channel densitometer. Each curve is that densitometer's channel reading
of the whole three-dye stack, base and mask included. The three curves share
one exposure axis because they are one series of patches.

**What it is not.** It is not "the cyan layer's density against the cyan
layer's exposure". The Status M red responsivity sits on the cyan dye's peak
but also reads the magenta and yellow dyes' red absorption: on the Vision3
unit-peak dye set the magenta dye contributes 0.09 of the cyan reading and the
yellow dye under 0.01, and across the whole Status M matrix of the traced dyes
the off-diagonal terms run 0.01–0.12 of the diagonal (*measured here*); on the
Endura paper dyes the Status A off-diagonals run 0.02–0.12.

**The reading the engines hold to.** At every exposure on the shared axis the
three densities, base and mask removed, are the Status M (or A) of one dye
stack; the dye amounts are the triple that reproduces all three at once (a
three-channel solve, closing to machine precision on every stock and paper
traced, the four reversal sheets included). That gives, per layer, a table of dye amount against exposure on the
neutral series – the only series on which the three curves are consistent with
one another. An off-neutral colour is rendered by looking each layer up on its
own table at its own exposure.

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

**What the sheet shows.** Reversal and Vision3 sheets plot three curves, one
per image dye, each the spectral density of that dye alone, peak-normalised or
at a stated concentration; the Vision3 chart adds two more, a solid Midscale
Neutral, which is absolute (its Status M integrates to roughly 0.8 / 1.2 / 1.5 D
across the four stocks, *measured here*, close to the 0.80 / 1.20 / 1.60
laboratory aim density), and a
dashed Minimum Density, the base and unreacted coupler, also absolute, so
that its caption "D-mins subtracted" applies to the three dye curves alone.
C-41 still-film sheets plot two curves only: the spectral density of a
midscale neutral patch and of the unexposed film (D-min), both including base
and orange mask. RA-4 papers plot the three dyes.

**What it is not.** The C-41 midscale curve is not a dye set. It is one
spectrum, the sum of three dyes and the surviving mask; three components cannot
be recovered from it without a prior, which is the surrogate-basis fit and its
register #8 uncertainty. The D-min curve is not a filter or a layer: it is the
unreacted coloured coupler (see `orange-mask-and-the-scanning-workflow.md`),
maximal at D-min and consumed as dye forms.

**Conventions that must match.** The per-dye curves used for a negative are
D-min subtracted: midscale minus D-min is the image-dye contribution, and the
Vision3 basis states the same convention in its `units`. A chart's plotted range
is its measured support; outside it nothing is known, and a curve is held to
the range its `digitization_audit.endpoints` publishes (the Kodak charts stop
2–3 nm short of the frame, the Vision3 basis at 402 nm).

---

## 3. The spectral sensitivity chart

**What the sheet shows.** Per layer, the logarithm of the reciprocal exposure
needed to reach a stated density above D-min (0.2 for Kodak), against
wavelength, under a stated exposing illuminant. Fujifilm sheets print the
ordinate as a relative scale bar with no absolute origin.

**What it is not.** It is not a colour-matching function and its absolute level
is not comparable between sheets (different reference densities and
illuminants). It enters the scene route only as a relative weighting, from
which a 3×3 is fitted, and enters the print route as the paper's exposure
kernel, whose absolute scale the gray-axis lock absorbs. A relative axis is
therefore harmless where a per-layer offset is an exposure scale, and harmful
only as a wavelength-dependent shape error, which no chart bounds.

---

## 4. The base the scanner measures, and where subtraction happens

**What the roll anchor does.** The clear base (reversal) or unexposed rebate
(negative, mask included) is read by the same LEDs and the same sensor as the
frames, and each frame is divided by it in linear light. That is a subtraction
of INTEGRATED densities: what reaches the table is

    −log10( ∫Φ·10^−(Dmin+dye·DYE) / ∫Φ·10^−Dmin ),

the image dyes as seen under the illuminant `Φ·10^−Dmin(λ)`, the LED filtered
by the base and mask.

**What it is not.** It is not the spectral subtraction the datasheet performs
when midscale minus D-min is formed. The two agree only if the mask is flat
across each LED's band, and a colour negative's mask is not: Portra 400's falls
0.11 D across the green LED's 528–560 nm FWHM. The scan-side responsivity of a
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

- **No sheet states the filtration or illuminant of its neutral series.** The
  characteristic curves are read as a neutral series because the sheets present
  them so; whether the paper series was balanced for the paper's own printing
  filtration or for a reference negative is not stated on E-4070 or the Fuji
  bulletin, and it bears on the absolute per-layer offsets the gray-axis lock
  solves for.
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
  through the same observer to 0.2 units, so the dyes are not the
  disagreement; the characteristic curves are, and whether a sensitometric
  daylight series is meant to be a visual neutral at D50, or the Status A
  transcription's shape is off, no source obtained settles (PROJECT.md
  register #19).
- **Whether a Status M densitometer's reading of a coloured-coupler mask equals
  the chart's D-min curve integrated against the Status M responsivities** is
  assumed, not checked; the chart's midscale integrates to a red density above
  the sheet's own grey-card corridor (PROJECT.md register #8), and no measured
  roll exists to settle which is right.
