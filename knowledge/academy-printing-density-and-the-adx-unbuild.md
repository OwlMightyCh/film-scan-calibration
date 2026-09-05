# Academy Printing Density, the ADX encodings and the universal unbuild

Collected 2026-09-03. This note extends §4–4b of
`densitometry-standards-and-density-metrics.md`, which records what SMPTE
ST 2065-2 and ST 2065-3 specify. It records what those standards leave out: how
Academy Printing Density (APD) is derived and measured, what the ADX10 and
ADX16 encodings place where, what the original Academy specification carried
that the SMPTE editions dropped, and what the Academy's own ADX-to-ACES
transform assumes about the negative it decodes. The ECN-2 route delivers into
ADX16, so every assumption in that decode is an assumption about what happens
to this project's output after it leaves the cube.

**ADX carries a density, and the transform that turns it into ACES assumes one
generic negative: a fixed matrix from channel-dependent to channel-independent
density, one characteristic curve with a slope of 1/0.55 above 0.6 D, and one
matrix from relative exposure to ACES. Nothing in the decode is stock-specific,
so every per-stock difference the ECN-2 engine models rides into ACES as image
content rather than as calibration.** A second finding is that the original
Academy specification S-2008-002 publishes Status M to APD conversion matrices
for 31 negative and intermediate stocks, Vision3 5207 and 5219 among them, with
residual errors. That is a published quantity relating two metrics this
project computes from the same dye model; compared on each stock's neutral
series, the model reproduces it to within the document's own 0.02 D (§4).

## 0. Provenance and confidence

| Tier | Source | Status |
|---|---|---|
| **A, verified primary** | SMPTE ST 2065-2:2020, *Academy Printing Density (APD) – Spectral Responsivities, Reference Measurement Device and Spectral Calculation* | Fetched in full from `pub.smpte.org`. The densitometry note read the 2012 edition; this is the 2020 reissue |
| **A, verified primary** | SMPTE ST 2065-3:2020, *Academy Density Exchange Encoding (ADX) – Encoding Academy Printing Density (APD) Values* | Fetched in full |
| **A, verified primary** | A.M.P.A.S. S-2008-002 v1.1 (18 November 2010), *Academy Density Exchange Encoding (ADX) and the Spectral Responsivities Defining Academy Printing Density (APD)* | Fetched in full, as the appendix of TB-2014-005 in the `aces-dev` repository at tag v1.0.3. The predecessor of both SMPTE standards; carries the derivation text and Annex C |
| **A, verified primary** | A.M.P.A.S. TB-2014-005, *Informative Notes on SMPTE ST 2065-2 and ST 2065-3* | LaTeX source fetched from `aces-dev` v1.0.3. Two pages; its substance is the appended S-2008-002 |
| **A, verified primary** | `ACEScsc.ADX16_to_ACES.ctl` and `ACEScsc.ADX10_to_ACES.ctl`, `aces-dev` v1.0.3; `CSC.Academy.ADX16_to_ACES.ctl`, `aces-input-and-colorspaces` (ACES 2, transform `a2.v1`) | Fetched; every constant read from the code. The ACES 2 file carries the same constants as the 1.0.3 file |
| **A, verified primary** | Eastman Kodak, *Conversion of 10-bit Log Film Data To 8-bit Linear or Video Data for The Cineon Digital Film System*, version 2.1, 26 July 1995 | Fetched from an Internet Archive copy of the copy at dotcsw.com; the original host returns 404 |
| **A, peer-reviewed** | W. Arrighetti, "The Academy Color Encoding System (ACES): A Professional Color-Management Framework for Production, Post-Production and Archival of Still and Motion Pictures", *Journal of Imaging* 3(4):40, 2017, CC BY 4.0 | Fetched in full. A practitioner's survey by an Academy contributor; reliable on the system's structure, secondary on the standards |
| **B, secondary** | C. J. Clark, *Investigation of the Academy's Image Interchange Framework at RIT*, Rochester Institute of Technology, 21 May 2010 | Fetched. A camera-IDT study; one sentence on the film unbuild is used here |
| **B, secondary** | docs.acescentral.com, "Academy Density Exchange Encoding (ADX)" and "ACES System" pages, version dated 10 September 2025 | Fetched. The ADX page states that "Additional background information about ADX will be added here in the future" |
| **Not obtained** | R. Patterson, "Evaluating Density Metrics for Scanning Motion Picture Negatives", *SMPTE Motion Imaging Journal* 117(4):31, May/June 2008; C. Dumont and T. O. Maier, "Printing Density", SMPTE Technical Conference, October 2007; G. Kennel, "Digital film scanning and recording: the technology and practice", *SMPTE Journal* 103(3):174–181, 1994 | Paywalled at SMPTE and IEEE Xplore. The first two are the bibliography of ST 2065-2 and are the likeliest home of the receiver derivation that no fetched document contains (§6) |
| **Not obtained** | ISO 5-2:2009, ISO 5-3:2009; SMPTE ST 268:2014 (DPX) | Paid standards. ST 268:2014 specifies how ADX is written into DPX; TB-2014-007 refers to it and adds nothing |

## 1. Lineage: Cineon, RP 180, APD

Printing density predates the Academy. The 1995 Kodak document defines the
Cineon Digital Negative as "represented in printing density, which is to say,
the density that is 'seen' by the print film when the negative is printed with
a standard illuminant", and says of the instrument that "the illumination and
color filters in the Cineon scanner were designed so that the effective
spectral response of the scanner matches that of print film". Three
conventions from that document survive, transformed, in ADX.

- **Range and step.** "The Cineon scanner is calibrated for a 2.048 density
  range: this allows it to capture the full latitude (density range) of the
  negative film with some margin at top and bottom." Ten bits over that range
  give "0.002 D per code value".
- **Anchor points.** "For a normally exposed negative film, the 90% white card
  has a code value of 685, the 18% gray card has a code value of 470, and the
  2% black card has a code value of 180. Dmin (~1% black) has a code value of
  95." Reference black defaults to 95 "which is the code value for Dmin in the
  calibration of the Cineon scanner".
- **A negative gamma of 0.6 in the decode.** Every log-to-linear equation in
  the document has the form `10 ^ ((IN − Refwhite) × 0.002/0.6)`, so the
  conversion to linear light divides printing density by 0.6 before
  antilogging. The Academy decode uses 0.55 (§5).

Plutino's criticism of Cineon printing density, that its defining stocks are
discontinued and its responsivities were never published, is recorded in the
densitometry note §4a and is not repeated here. RP 180 answered the second
objection with a published table; APD answered the first by re-basing the
receiver on current print stocks. ADX10 keeps Cineon's code 95 for D-min and
its 500 code values per density unit; ADX16 scales both by sixteen.

## 2. How APD is defined, and what is not published about it

S-2008-002 §5.1 states the definition as a spectral product, and this is the
form every standard in the family keeps:

> "The spectral responsivities defined in this specification are specified as
> spectral products rather than discrete spectral components. The spectral
> product for any densitometric specification, film scanner, or densitometer
> may be denoted using Equation (5). Π = S(λ)s(λ) … where: S(λ) is the relative
> spectral power distribution of the influx. s(λ) is the relative spectral
> sensitivity of the receiver, which includes the photodetector and all
> intervening components between it and the plane of the sample to be
> measured."

The two halves are of different provenance.

- **The influx is fully specified.** "The spectral responsivities defining APD
  incorporate the influx spectrum S_APD, which models the lamphouse of a Bell &
  Howell Model C motion picture printer, filtered by an Eastman Kodak Wratten
  Filter No. 2B." It is tabulated in Annex B of S-2008-002 and Annex A of
  ST 2065-2, normalised to 1.0 at 560 nm. A note explains the relation to ISO
  densitometry: the Model C "uses a tungsten light source that is separated
  into red, blue, and green components with a set of dichroic mirrors; those
  components are then modulated by a series of light valves … and after
  modulation are filtered with a Eastman Kodak Wratten Filter No. 2B. Use of
  S_APD in the calculation of the spectral responsivity associated with APD
  therefore meets the light source requirement of ISO 5-3:1995(E)", whose
  basic source is CIE Illuminant A.
- **The receiver is described, not derived.** The responsivities "are based on
  the spectral sensitivities of contemporary motion picture print films such as
  those of the Kodak Vision family, of the Fujifilm Eterna family, and of
  Fujifilm F-CP". No fetched document says which print stocks were measured,
  how they were weighted, or how the three products were normalised before
  tabulation. S-2008-002 §5.1, headed "Derivation of Π_APD", contains only the
  spectral-product definition and the influx note quoted above. ST 2065-2's
  bibliography cites Dumont and Maier (2007) and Patterson (2008), both
  unobtained (§6).

The calculation itself is Equation 6 of S-2008-002, reproduced as the spectral
calculation of ST 2065-2 §4.1.3:

```
APD_c = −log10 ( ∫[360,730] T(λ) Π_APD_c(λ) dλ ),   c ∈ {R, G, B}
```

with each Π_APD_c "normalized such that" its integral over 360–730 nm equals 1,
and T(λ) the spectral transmittance of the negative, "or 10^−density(λ)". The
tables run 360–730 nm at 2 nm; ST 2065-2 §4.1.3 requires the transmittance to
be measured "at intervals no larger than 5 nm". The geometry is ISO 5-2 diffuse
transmission; sample conditioning is 23 ± 2 °C and 50 ± 5 % relative humidity.
Two notes matter to a scanning project. First: "A densitometer with spectral
responsivities equal to the spectral responsivities of Π_APD could measure APD
values directly; no such densitometer, however, exists at the time of this
writing." Second, from ST 2065-2 §4.1.3 note 3, already quoted in the
densitometry note: conversions from other metrics "are product specific: a
separate transformation needs to be determined for each sample".

**Project position.** The ADX16 engine takes the spectral route of Equation 6,
integrating the modelled dye-plus-mask transmittance against the tables held as
`data/standards/APD_ST2065-2.json`. That is the route the standard describes
for a spectral measurement device; the engine substitutes a modelled spectrum
for a measured one, which is the substitution the whole ECN-2 chain rests on
and the reason PROJECT.md lists it under Known limitations. Nothing in APD's
definition is affected by the unpublished receiver derivation, because the
tables are normative; the derivation matters only for judging how far APD
represents any one real print stock.

## 3. The two encodings

ST 2065-3:2020 §4.3 gives both encodings as clipped, rounded affine maps of
D-min-subtracted APD, with the same per-channel factors k = (1.00, 0.92, 0.95)
for (R, G, B):

```
ADX16_c = MAX[0, MIN[65535, ROUND[ k_c × (APD_c − APD_c_Dmin) × 8000 + 1520 ]]]
ADX10_c = MAX[0, MIN[1023,  ROUND[ k_c × (APD_c − APD_c_Dmin) × 500  + 95   ]]]
```

where ROUND(x) is "the largest integer value less than or equal to x + 0.5"
(S-2008-002 used INT). D-min is "optical density of an area of a chemically
processed photographic medium that has received zero exposure. Dmin corresponds
to the optical density of film base and non-image density due to factors other
than exposure to light". The arithmetic these constants imply, computed here:

| | ADX10 | ADX16 |
|---|---|---|
| density per code value (k = 1) | 0.002 | 0.000125 |
| headroom below D-min | 0.19 D | 0.19 D |
| ceiling above D-min (k = 1) | 1.856 D | 8.002 D |
| code at D-min | 95 | 1520 |
| code the Academy decode treats as 18 % grey (§5) | 445 | 7120 |

The ADX10 ceiling is the reason PROJECT.md reports that ADX10 "would clip
16.2 % of working-range probes" and that ADX16 is the only supported target:
the negative corridor runs to DMAX 3.30 over a mask, and a 1.856 D window above
D-min does not hold it.

**Why the factors are 0.92 and 0.95.** S-2008-002 §4.2.2 gives the rationale
the SMPTE text omits: "The exposure of a spectrally nonselective (i.e. neutral
color) object by a source for which the film has been balanced, followed by
nominal laboratory processing, would ideally produce a negative having equal
Red, Green, and Blue printing densities … These gain factors were computed as a
weighted average of gain factors for commonly used motion picture films, and
will produce ADX values whose corresponding Status M densities are compatible
with the capabilities of modern film recorders recording onto intermediate
stocks." The factors are therefore a fleet average that makes a neutral
exposure land on equal code values, and the v1.1 revision history records a
"Modification to ADX encoding gain factors" between September 2009 and October
2010, so the printed values are the second set. The ADX16 engine applies them
verbatim (densitometry note §4b); they are not a project trim.

## 4. Converting from Status M, and Annex C

S-2008-002 §5.2.2 is the fullest statement in the family of what a scanner
must be for a matrix conversion to hold, and it reads on this project's
apparatus directly:

> "Film scanners typically are not manufactured with spectral responsivities
> that either match, or are a linear combination of ISO Status M. However, if a
> film scanner exhibits spectral responsivities that match ISO Status M, the
> transforms in Annex C may be used to transform the scanner density values
> into APD. If a film scanner exhibits spectral responsivities that are a
> linear combination of ISO Status M responsivities, a 3x3 transform may be
> used to convert the scanner density values into ISO Status M before using the
> transforms in Annex C. If a film scanner does not exhibit spectral
> responsivities that either match, or are a linear combination of ISO Status M
> responsivities, either a more complex transform to convert scanner density
> values to ISO Status M density values must be used before the transforms in
> Annex C, or the transforms in Annex C are not appropriate for conversion of
> those scanner density values into APD and a different set of stock-specific
> scanner density to APD IDTs must be calculated."

A narrowband LED scanner is the third case. Its responsivities are not a
linear combination of Status M, so the Academy's own text says a stock-specific
scanner-density-to-APD transform is required; the ECN-2 route builds exactly
that, per stock, from the dye model, and computes APD spectrally rather than
through Status M. The same section says the residual of a 3×3 can be reduced
by a polynomial or "nearly eliminate[d]" by a stock-specific 3D LUT with
shaper, which is the form the route ships.

**Annex C** is the material the SMPTE editions dropped. "The matrix
coefficients were computed based on spectral measurements of 31 contemporary
camera negative and intermediate film stocks. A set of test patches, consisting
of 33 'grays' (a ramp of approximately equal Status M densities in all three
dyes) and 64 'colors' (a cube of 4³ approximately equidistant density
combinations), was exposed on each film stock. An ARRILASER film recorder was
used to create the test negatives. The resulting 97 patches on each negative
were measured with a spectrophotometer in 10 nm increments. The spectral
transmission of each measured patch was converted to Status M density and APD,
respectively. A least-squares regression was used to calculate the Status M
density to APD transforms." The stated use is process control: "With the
exception of the intermediate stocks, the expected errors are all smaller than
or equal to 0.02." The 31 stocks are Kodak 5201, 5205, 5207, 5212, 5217, 5218,
5219, 5229, 5242, 5245, 5246, 5248, 5260, 5274, 5277, 5279 and 5299, and
Fujifilm 8502, 8511, 8522, 8532, 8543, 8552, 8553, 8562, 8563, 8572, 8573,
8582, 8583 and 8592. Vision3 50D (5203) and 200T (5213) post-date the
document and are absent; 5201, 5205, 5212, 5217 and 5218 are their Vision2
predecessors.

The two Vision3 entries, transcribed from the document and checked against its
text, each of the form `APD = M · StatusM + offset`:

| Stock | M (rows R, G, B) | offset | mean abs error (all), R G B | max abs error (all) | max (gray) |
|---|---|---|---|---|---|
| Kodak 5207 (Vision3 250D) | 1.087370 −0.008372 0.001454 / −0.010327 1.022765 0.017075 / −0.007220 0.028536 0.955400 | −0.015931 −0.032591 0.012734 | 0.004 0.010 0.002 | 0.016 0.053 0.010 | 0.006 0.005 0.003 |
| Kodak 5219 (Vision3 500T) | 1.100481 −0.017433 −0.000160 / −0.005245 1.021893 0.009767 / −0.008288 0.028113 0.957600 | −0.046520 −0.025677 0.010549 | 0.003 0.006 0.002 | 0.013 0.032 0.009 | 0.006 0.004 0.003 |

Two features are worth reading before any use. The diagonal is not unity: APD
red runs about 9–10 % steeper than Status M red and APD blue about 4–5 %
flatter, with a green-into-blue term of 0.028 in both stocks. And the offsets
are not zero, so the two metrics do not agree at D-min; the largest, 5219's
−0.047 in red, is the size of a whole grade step in printer lights.

**What this offers the project.** The ECN-2 engines compute Status M and APD
from the same modelled dye amounts. A neutral ramp pushed through both, for
5207 and 5219, and compared against the Annex C matrix, is a check against a
published quantity that neither the ADX16 engine's inverse nor its self-report
uses, which is the kind of check Rule 4 asks for. The pass criterion is the
document's own residual, 0.02 D over a grey ramp.

**Measured here, 2026-09-03.** For each stock, the per-layer dye amounts were
solved from the sheet's three characteristic curves at once (absolute Status M
including base and mask, the scene engine's neutral solve, residual below
0.0001 D), then the same amounts were integrated against the ISO Status M and
ST 2065-2 tables held in `data/standards/` on the 402–730 nm dye grid (the
share of either responsivity outside that grid is below 0.3 % in every
channel). The spectral APD was compared with the Annex C prediction
`M · StatusM + offset` along the whole traced exposure axis (230 points for
250D, 239 for 500T), twice: with the stock's own dye set and mask, and with
the family-average dye set and mask that the ADX16 cube reads through.

| Stock, basis | mean (APD_spectral − APD_AnnexC), R G B | max abs, R G B | Annex C's own mean abs error (all) |
|---|---|---|---|
| 250D, own dyes and mask | −0.014 +0.010 +0.003 | 0.028 0.035 0.004 | 0.004 0.010 0.002 |
| 250D, family basis | −0.010 +0.009 +0.001 | 0.023 0.031 0.003 | |
| 500T, own dyes and mask | +0.018 +0.008 −0.002 | 0.022 0.032 0.005 | 0.003 0.006 0.002 |
| 500T, family basis | +0.024 +0.012 +0.001 | 0.032 0.037 0.002 | |

Reading the three channels separately:

- **Blue agrees to within 0.005 D everywhere**, on both bases, inside the
  Academy's own residual. The blue relation between the two metrics is the
  one most sensitive to the yellow dye's shape and the mask's blue density,
  so this is the strongest of the three results.
- **Green agrees to within 0.005 D over the toe and straight line** and
  diverges at the shoulder, reaching +0.03 to +0.04 D at the top of the traced
  axis. Annex C's own maximum green residual is 0.032 (5219) and 0.053 (5207)
  over its 97 patches, so the Academy's linear matrix misfits green by the
  same amount somewhere in its range; the comparison cannot discriminate in
  green above about 2.1 D. Below that it passes.
- **Red carries a near-constant offset**, −0.01 to −0.03 D for 250D and +0.01
  to +0.02 D for 500T, of opposite sign for the two stocks. It is present at
  D-min, where the modelled mask reads 0.03 D above the sheet's Status M
  red D-min for 250D and 0.03 D below it for 500T; that is the traced Minimum
  Density curve's known disagreement with the sheet's D-min triplet
  (PROJECT.md records the family cross-check at 0.045 D). The Academy's red
  offsets also differ between the two stocks by 0.03, so a per-stock red
  D-min term is real in both data sets. The red result is therefore bounded
  by the mask trace, not by the dye model.

Overall the dye model reproduces the Academy's measured Status M to APD
relation to 0.001–0.018 D per-channel mean absolute error on the stocks' own bases,
within the 0.02 D the document itself claims for its matrices, and to 0.024 D
on the family basis, which does not meet it; the largest single-point
disagreement is 0.035 D, in green at the shoulder. No channel shows the 0.1 D class of disagreement a
wrong dye reading or a one-curve-per-layer misreading would produce. Two
caveats bound the pass. The ISO Status M table in `data/standards/` is
transcribed and unverified against ISO 5-3, and the same table sits on both
sides of the comparison, so a common error there would cancel. And the Annex C
patches were laser exposures on 2010 emulsions, measured by spectrophotometer,
while the ramp here is the datasheet's traced neutral; the two neutrals need
not lie on the same locus in dye space. The check is `engine/ecn2/annexc_check.py`;
the 31 matrices are held as `data/standards/StatusM_to_APD_S-2008-002_AnnexC.json`.

## 5. The universal unbuild

The Academy does not publish the ADX-to-ACES transform as a document. It is
code: `ACEScsc.ADX16_to_ACES.ctl` in ACES 1.0.3 and, with identical constants,
`CSC.Academy.ADX16_to_ACES.ctl` (transform ID `a2.v1`) in ACES 2. TB-2014-005
says only that "The universal ADX-to-ACES transform and universal ACES-to-ADX
transform are described in other documents detailing the Image Interchange
Framework"; no such document was found (§6). The code is short enough to state
in full. Operating on normalised input, per channel unless stated:

1. `adx = input × 65535` (ADX10: × 1023).
2. `cdd = (adx − 1520) / 8000` (ADX10: `(adx − 95) / 500`). The comment names
   this "Channel Dependent Density". It is APD above D-min with the k factors
   left in.
3. `cid = cdd · CDD_TO_CID`, "Channel Independent Density":
   ```
   CDD_TO_CID = [ 0.75573  0.05901  0.16134 ]
                [ 0.22197  0.96928  0.07406 ]
                [ 0.02230 −0.02829  0.76460 ]
   ```
4. `logE = interpolate1D(LUT, cid)` for `cid ≤ 0.6`, else
   `logE = (100/55) × cid − REF_PT`, with
   `REF_PT = (7120 − 1520)/8000 × (100/55) − log10(0.18)` and the LUT
   ```
   cid   −0.190  0.010   0.028   0.054   0.095   0.145   0.220   0.300   0.400   0.500   0.600
   logE  −6.000 −2.7217 −2.5217 −2.3217 −2.1217 −1.9217 −1.7217 −1.5217 −1.3217 −1.1217 −0.92655
   ```
5. `exp = 10^logE`.
6. `aces = exp · EXP_TO_ACES`:
   ```
   EXP_TO_ACES = [ 0.72286  0.11923  0.01427 ]
                 [ 0.12630  0.76418  0.08213 ]
                 [ 0.15084  0.11659  0.90359 ]
   ```

The CTL routine `mult_f3_f33` multiplies a row vector by the matrix, so the
matrices act as printed with the vector on the left, and the quantity conserved
along the neutral axis is the column sum. Computed here: every column of both
matrices sums to 1.000 to four places, so equal channel densities decode to
equal ACES values, and the k factors of §3 are what make a neutral exposure
arrive at equal densities in the first place. Other properties, computed from
the constants:

- The curve is continuous at the junction: the LUT's last node is −0.92655 at
  0.6 and the linear branch gives the same value there.
- Its slope is 2.00 in log exposure per density unit between 0.01 and 0.5
  (gamma 0.50), 1.95 between 0.5 and 0.6, and 1/0.55 = 1.818 above 0.6. The
  Cineon document's decode used 1/0.6 throughout (§1).
- `REF_PT` evaluates to 2.01745, and it places 18 % grey at a channel
  independent density of 0.700 above D-min, which for a neutral (where
  `cid = cdd`) is ADX16 code 7120 and ADX10 code 445. The Cineon convention put
  18 % grey at 470, or 0.75 D above D-min; the two systems anchor differently
  and are not meant to agree.
- Below D-min the LUT's first node sends `cid = −0.19` to `logE = −6`, so the
  full headroom of §3 decodes to 10⁻⁶ of the 100 % diffuser.

**What the decode assumes.** The three constants are one negative. The
`CDD_TO_CID` matrix removes one set of print-film cross-sensitivities, the LUT
inverts one characteristic curve, and `EXP_TO_ACES` maps one set of camera-film
spectral sensitivities to the RICD. None of these is named in the code or in
any fetched document, and the transform carries no stock parameter. Clark's
2010 report states the design consequence plainly: "It is important to note
that ACES will preserve the aesthetic characteristics of film and other
cameras. For example, the universal film unbuild will still unbuild a highly
saturated film into highly saturated ACES images." Arrighetti's description of
the encoded quantity is the same point from the other side: "ADX is
output-referred to a reference print film: all in all, it encodes a
'film-referred' color-space."

**Project position.** This is the mechanism behind the sentence in PROJECT.md
that the scene-linear route "is the accuracy reference the ADX16 route is
judged against". The ADX16 cube lands each Vision3 stock on the APD its own
dyes and mask produce, which is the quantity ADX is defined to carry; the
Academy decode then inverts a generic curve and a generic matrix. Every
difference between a stock's real curve and that generic one, and between its
sensitivities and the generic `EXP_TO_ACES`, survives into ACES as image
content, which is what the Academy intends and what "printer-light trims are
dialled on a known neutral" in the README addresses. The trims act in the CDD
domain, before the matrix, so they are density offsets in printing density,
which is the quantity a laboratory's printer lights also move. The scene route
inverts the stock's own characteristic curves and sensitivities, and is the
route to use where the stock's rendering is not wanted. `adx_validate.py`
scores the full chain through this decode (PROJECT.md).

## 6. Open questions and material not found

- **The receiver derivation of Π_APD.** Which print stocks, what weighting,
  and how the three products were normalised is in no fetched document. The
  two references ST 2065-2 cites for it, Dumont and Maier (2007) and Patterson
  (2008), are paywalled at SMPTE. Kennel (1994) is the corresponding source for
  the Cineon scanner and is paywalled at IEEE Xplore.
- **The provenance of the unbuild constants.** TB-2014-005 defers to "other
  documents detailing the Image Interchange Framework". None was found in
  `aces-dev`, `aces-docs`, on acescentral.com or in the literature searched.
  Which negative, or which average of negatives, the `CDD_TO_CID`, LUT and
  `EXP_TO_ACES` constants represent is unknown.
- **The Annex C check** (§4) passes at the document's own tolerance. It runs
  on demand and is not part of the ADX16 build's self-report, since it reads
  per-stock characteristic curves the stock-blind build does not load.
- **The green shoulder** cannot be discriminated with a linear matrix whose
  own residual is 0.03–0.05 D there. A patch-level comparison would need the
  Academy's 97 spectra, which are not published.
- **ST 268:2014**, which specifies the DPX fields that carry ADX (descriptor,
  transfer characteristic, D-min metadata), was not obtained. Arrighetti
  recommends "that the scanner software fills as many DPX Film-Area metadata as
  possible, including printing-density type (APD), clear-base Dmin". This
  project's route hands the cube output to Resolve's ADX (16-bit) input colour
  space directly and does not write DPX, so the fields are not needed today.
- **ISO 5-2 and ISO 5-3** remain unobtained, as in the densitometry note.

## Sources

- SMPTE ST 2065-2:2020, *Academy Printing Density (APD) – Spectral Responsivities, Reference Measurement Device and Spectral Calculation* – https://pub.smpte.org/latest/st2065-2/st2065-2-2020.pdf (tier A, fetched in full)
- SMPTE ST 2065-3:2020, *Academy Density Exchange Encoding (ADX) – Encoding Academy Printing Density (APD) Values* – https://pub.smpte.org/latest/st2065-3/st2065-3-2020.pdf (tier A, fetched in full)
- A.M.P.A.S. S-2008-002 v1.1, *Academy Density Exchange Encoding (ADX) and the Spectral Responsivities Defining Academy Printing Density (APD)*, 18 November 2010 – https://github.com/ampas/aces-dev/blob/v1.0.3/documents/LaTeX/TB-2014-005/S-2008-002.pdf (tier A, fetched in full)
- A.M.P.A.S. TB-2014-005, *Informative Notes on SMPTE ST 2065-2 and SMPTE ST 2065-3* – https://github.com/ampas/aces-dev/tree/v1.0.3/documents/LaTeX/TB-2014-005 (tier A, LaTeX source)
- `ACEScsc.ADX16_to_ACES.ctl`, `ACEScsc.ADX10_to_ACES.ctl` – https://github.com/ampas/aces-dev/tree/v1.0.3/transforms/ctl/csc/ADX (tier A, code); `CSC.Academy.ADX16_to_ACES.ctl` – https://github.com/aces-aswf/aces-input-and-colorspaces/tree/main/ADX (tier A, code, ACES 2)
- Eastman Kodak, *Conversion of 10-bit Log Film Data To 8-bit Linear or Video Data for The Cineon Digital Film System*, v2.1, 26 July 1995 – https://web.archive.org/web/2019/https://www.dotcsw.com/doc/cineon1.pdf (tier A, fetched)
- W. Arrighetti, "The Academy Color Encoding System (ACES): A Professional Color-Management Framework for Production, Post-Production and Archival of Still and Motion Pictures", *Journal of Imaging* 3(4):40, 2017 – https://doi.org/10.3390/jimaging3040040 (tier A, CC BY 4.0, fetched)
- C. J. Clark, *Investigation of the Academy's Image Interchange Framework at RIT*, 21 May 2010 – https://s3.cad.rit.edu/cadgallery_production/storage/media/uploads/faculty-s-projects/472/documents/25/academy-iif-at-rit.pdf (tier B, fetched)
- docs.acescentral.com, *Academy Density Exchange Encoding (ADX)* – https://docs.acescentral.com/encodings/adx/ (tier B, fetched, version of 10 September 2025)
- R. Patterson, "Evaluating Density Metrics for Scanning Motion Picture Negatives", *SMPTE Motion Imaging Journal* 117(4):31, 2008 (NOT obtained, paywalled)
- C. Dumont and T. O. Maier, "Printing Density", SMPTE Technical Conference Proceedings, 24–27 October 2007 (NOT obtained, paywalled)
- G. Kennel, "Digital film scanning and recording: the technology and practice", *SMPTE Journal* 103(3):174–181, 1994 (NOT obtained, paywalled)
- SMPTE ST 268:2014, *File Format for Digital Moving Picture Exchange (DPX)* (NOT obtained, paid standard)
