# Density metrics: Status M, printing density, APD, and measurement geometry

Collected 2026-08-16. This project targets three different density metrics –
Status M for C-41, Academy Printing Density for ECN-2 (encoded as ADX16 under
ST 2065-3, with SMPTE RP 180 retained as a comparison), and Status A for the
RA-4 paper inversion – and treats each as a fixed reference. This note records
what those standards say and what they claim about their own accuracy, from
the standards themselves.

**Headline finding: SMPTE RP 180 states in its own introduction that Status M
"can only approximate printing densities for most materials".** The two metrics
this project uses for its two negative paths are not interchangeable, and the
standard that defines one of them says so explicitly.

A second result is a clean verification: the repository's
transcription of the RP 180 responsivity table, whose provenance note recorded
that it had never been checked against the standard, **matches the published
table exactly** at every wavelength.

---

## 0. Provenance and confidence

| Tier | Source | Status |
|---|---|---|
| **A, verified primary** | SMPTE RP 180-1999, *Spectral Conditions Defining Printing Density in Motion-Picture Negative and Intermediate Films*; SMPTE ST 2065-2:2012, *Academy Printing Density* | Both fetched in full from `pub.smpte.org`, including their numeric responsivity tables. Quotations below are verbatim |
| **A, verified primary** | Kodak publication Z-131, on which status C-41 process control is read in | Fetched; see `process-chemistry-c41-ecn2-e6.md` |
| **A, primary, tables compared** | ANSI/ISO 5-3-1995 (ANSI/NAPM IT2.18-1996), the public US adoption identifying itself as identical to ISO 5-3:1995 | Tables 3 (Status A) and 4 (Status M) compared numerically against `data/standards/`; the text was not otherwise read, and the 2009 edition was not obtained |
| **B, secondary technical** | Phil Green, *Bringing one of the oldest international standards into the 21st century: ISO 5 densitometry*, London College of Communication, 2008 | A conference presentation. Reliable on the direction of ISO 5's revision; no substitute for ISO 5-3 itself |
| **B, reference literature** | General statements on the Callier effect in dye versus silver images | Consistent across sources and corroborated by a peer-reviewed statement that chromogenic film is non-scattering |

**ISO 5-3:2009 itself was not obtained.** It is a paid ISO standard. Its 1995
edition is public through the US adoption ANSI/ISO 5-3-1995 (ANSI/NAPM
IT2.18-1996, law.resource.org), and that document's Tables 3 and 4 were
compared numerically with the repository's `StatusA_ISO5-3.json` and
`StatusM_ISO5-3.json`: every explicitly tabulated log-product entry matches,
35 for Status A and 42 for Status M, and the stored linear values agree with
those entries within their six-decimal rounding (largest error below 5e-7).

What that comparison does NOT cover is stated once here and relied on below:
whether the 2009 edition changed any value; the tails beyond the explicit rows,
which the tables define by a slope and the JSONs carry by extrapolation or by
zero; and interpolation between rows. Every statement below attributed to the
TEXT of ISO 5-3 is reported at second hand.

---

## 1. What a density metric is

A density is not a property of a sample alone. It is the sample's spectral
transmittance weighted by a defined spectral response and integrated:

```
D = −log₁₀ ( Σ_λ Π_λ · T_λ  /  Σ_λ Π_λ )
```

where `Π_λ` is the **spectral product**, being the product of the instrument's
influx spectrum and its receiver sensitivity. Changing `Π` changes the number
even though the film has not changed. The named "statuses" are simply
standardised choices of `Π`, each shaped to maximise sensitivity to a particular
class of colorant.

This is the reason the metrics below cannot be converted into one another
exactly, and the reason every density figure in this project must travel with
the name of its metric.

---

## 2. Status M and Status A (tables verified against the 1995 edition; 2009 text not obtained)

Both are defined in ISO 5-3, *Photography and graphic technology – Density
measurements – Part 3: Spectral conditions*, currently ISO 5-3:2009.

- **Status M** is the metric for colour materials **intended for printing**,
  which is to say camera negatives. The C-41 datasheets publish in it, and
  Z-131 specifies process control in it. It is this project's C-41 target.
- **Status A** is the metric for material **intended for direct viewing**,
  which is to say reversal film and prints. This project uses it in two
  places, the inversion of the RA-4 paper characteristic curves and the
  reversal builds' closure against their sheets' characteristic curves
  (PROJECT.md register #19); Kodak's LAD aim for print film is quoted in it.
  The reversal closure is the first place the transcription's SHAPE bears on
  a result; the explicit table entries are verified against the 1995 edition,
  the tails and the 2009 edition are not (§6).

The distinction is one of intended use, and it is the
same distinction that decides whether a film carries an orange mask.

---

## 3. SMPTE RP 180: printing density (tier A, fetched in full)

RP 180-1999 was approved on 23 April 1999 as a revision of RP 180-1994. The
copy on `pub.smpte.org` is stamped **ARCHIVED DECEMBER 12, 2006**.

**What it defines.** Printing density is "the density of the negative as 'seen'
by the printer and print material". The scope clause reads: "This practice
defines the spectral conditions defining the printing density gammas of
motion-picture color negative and intermediate materials."

**What it says about Status M.** The introduction is unusually direct:

> "The ISO has defined status M density for the evaluation of color photographic
> materials intended for printing. Status M density measurements are widely and
> satisfactorily used in process control in motion-picture, amateur color
> negative, and reversal printing originals. However, given the large number of
> films in use, status M densities can only approximate printing densities for
> most materials."

and the scope adds that RP 180 "is not intended as a replacement for the status M
density spectral conditions given in ANSI/ISO 5-3".

**What it does not claim.** RP 180 is explicit that an exact printing-density
measure is unattainable: "Ideally, a measure of printing density would exactly
duplicate these properties. This is not possible in practice owing to the large
variety of printers and materials that exist. The practical goal in specifying a
printing density measure is to require that the printing density measurement
correctly specifies the printing **gammas** of typical motion-picture color
negative and intermediate materials." The metric is therefore designed to get
**contrast** right, and is not a claim about absolute colour.

**Structure of the table.** Responsivities are tabulated from 360 to 740 nm at
10 nm intervals, "arbitrarily normalized to have unit response at the peak
sensitivity", with peaks at **R 670 nm, G 530 nm and B 430 nm**. In use the
densitometer is zeroed either to a 100 % transmitting reference or to the film's
own D-min, which renormalises the table.

**Stated applications**, all three relevant here: calibrating film samples which
in turn calibrate film scanners; deriving "a transformation matrix to transform
status M density measurements to printing density"; and serving "as an aim point
for designing the spectral responses of film scanners".

### Verification of the repository's copy

`data/standards/RP180_responsivities.json` records its provenance as having been
transcribed from RP 180 in an earlier session and extracted later from an inline
table in an unpublished printing-density engine; its provenance field now also
records the check made here, and this section is the fuller statement of it.

Every one of the 37 wavelengths the file carries
matches the published table **exactly**, with zero mismatches across all three
channels. The standard additionally tabulates 370 nm and 740 nm, which the
repository file omits; both rows are zero in all three channels. The 740 nm
omission has no effect, since 730 nm is already zero in every channel.

The 370 nm omission is not quite free: the ADX16 build resamples the table linearly
onto a 1 nm grid to account for the share of each channel's integral lying
outside the engine grid, and without the zero row that resampling reads 0.0026
at 370 nm (between 0 at 360 nm and 0.0052 at 380 nm) where 0 is expected. On that
1 nm sample-sum convention the blue integral is inflated by 0.061 %, and the
blue share below 400 nm reads 3.461 % against 3.401 % from the complete table;
below the engine's 402 nm grid floor, 4.316 % against 4.258 % (*measured
here*, 2026-09-09). The ADX16 build prints that share to three decimals in
percent, so the omission IS visible at the build's own reporting precision,
by about 0.06 percentage points; it does not change the normalised in-grid
RP 180 observer, since 370 nm lies below the grid, and it does not touch APD.

Quote the integration convention with any sub-400 nm percentage. The recorded
peak wavelengths of 670, 530 and 430 nm are correct.

---

## 4. SMPTE ST 2065-2: Academy Printing Density (tier A, fetched)

**Revised 2026-09-03.** The derivation of the APD responsivities, the ADX10
encoding, the original Academy specification S-2008-002 with its Status M to
APD matrices, and the Academy's ADX-to-ACES transform are recorded in
`academy-printing-density-and-the-adx-unbuild.md`; the surrounding ACES
system in `aces-system-and-encodings.md`. This section and §4b stand as
collected.

APD is the live standard in this family. It is a **different metric from
RP 180**, and the two must not be conflated.

- APD's responsivities are "based on the spectral sensitivities of contemporary
  motion picture print films such as those of the Kodak Vision family, of the
  Fujifilm Eterna family, and of Fujifilm F-CP", measured against a reference
  device defined as "the spectral power distribution of a Bell & Howell Model C
  printer lamp house with dichroic filters and the spectral transmittance of an
  Eastman Kodak Wratten Filter No. 2B".
- It is tabulated from 360 to 730 nm at **2 nm** intervals, against RP 180's
  10 nm, and the standard tabulates the influx spectrum separately.
- Density is specified in the **diffuse** transmission geometry of ISO 5-2.
- Its bibliography cites RP 180 as archived.

ST 2065-2 carries its own warning about conversion, in note 3: "Conversions
between other density metric values (i.e. ISO Status M density, scanner density,
etc.) and APD values are possible…. Each type transformation will likely be
imperfect and care should be taken… to appropriately minimize the associated
residual errors."

The ECN-2 route lands on APD. `Vision3 to ADX16.cube` integrates the
responsivities held as `data/standards/APD_ST2065-2.json` (ST 2065-2:2012
Tables A.1 and B.1, numerically identical to the 2020 companion files, §6)
and encodes the result under ST 2065-3 (§4b);
`RP180_responsivities.json` is read by the same build only for the
APD-versus-RP 180 comparison it prints, and by the unpublished ECN-2 trace
budget, whose output space is the cube's own mask-relative APD and which
carries RP 180 beside it as a named comparison. The systematics register
distinguishes the two responsivity sets by their sub-400 nm blue content.

### 4b. SMPTE ST 2065-3: the ADX encoding (tier A, fetched)

ST 2065-3:2020, *Academy Density Exchange Encoding*, is the container the ECN-2
cube delivers into. Its Equation 1 encodes each channel as

```
ADX16 = k × (APD − APD_Dmin) × 8000 + 1520,    k = (1.00, 0.92, 0.95) for R, G, B
```

clipped to 16 bits, where `APD_Dmin` is "the measured Dmin of the sample".

Two points bear on the modelling.

- The subtraction is of INTEGRATED printing densities, the same operation the
  roll anchor performs in linear light (see `reading-datasheet-charts.md` §4), so
  the ADX16 engine forms exactly `APD(mask + dye) − APD(mask)` from the traced
  Vision3 Minimum Density curve, with no spectral subtraction.
- And the per-channel factors `k` are the standard's own, checked verbatim
  against the SMPTE text; they are not a project-fitted trim.

### 4a. Cineon printing density and ADX (tier A)

Plutino (2024) reviews the Cineon and Academy Density Exchange encodings as used
by contemporary scanners, and supplies several figures this project relies on
without a citation.

**Cineon printing density is not the same thing as RP 180.** Cineon printing
densities were "defined by the spectral sensitivities of the 5384 film print,
the spectral radiance of a printer (Bell & Howell Model C with a Wratten 2B UV
filter), and the 5248 negative film base density". Plutino's criticism is
pointed: "Cineon Printing Densities are based on film stocks that are no longer
manufactured, and the corresponding spectral sensitivities were never fully
specified."

RP 180, by contrast, publishes an explicit responsivity table and is
reproducible from the standard alone, which is what this project uses.
PROJECT.md's glossary draws the distinction, recording that the label "Cineon
printing density" denotes a metric defined by discontinued stocks, distinct
from the RP 180 table this repository holds; the RP 180 values serve as a
comparison reference beside the live Academy Printing Density target:
Plutino's criticism attaches to the Cineon
definition and not to the RP 180 table.

**The Cineon encoding constants**, which no shipped route now uses (the
Cineon-container route is unpublished; the live ECN-2 delivery is ADX16, §4b),
recorded here because the project's discussion of third-party linearisers still
refers to the Cineon Film Log container:

- 10-bit log encoding over [0, 1023], one code value being **0.002 OD**.
- Reference black at code **95** and diffuse white at code **685**.
- An offset of 2.048 corresponding to roughly **3.72 log exposure**, about
  12.4 stops, for a film of gamma 0.55.

The 685/1023 diffuse-white placement is the standard Cineon convention, sourced
to Plutino (2024); it is the reference point any Cineon-container comparison
(PROJECT.md's NamiColor discussion) implies.

**APD's applicability**, from the same review: "APD are based on the spectral
sensitivities of contemporary motion picture film prints, so when working with
films from the early cinema or non-modern films, the tone reproduction may
present artifacts and errors… because the ADX system has been developed for film
production, not archiving." Scanner light sources "have been selected to have an
emission matching perfectly the APD curves, thus not being suitable for the
digitization of all the historical cinematographic materials."

**Scope of that caveat here.** Every stock on this project's APD route is a
Vision3 camera negative modelled from its current H-1 datasheet edition, the
class of material APD was designed around (Kodak's remjet-free AHU
construction of the same four types is stated by Kodak not to alter
sensitometric performance). The historical-material concern is therefore less
directly applicable to the modelled fleet than to archival digitisation of
early or discontinued material.

What remains is the stock-specific conversion error that ST 2065-2's Note 3
states for every product (§4), which this scope statement does not remove.
Plutino's recommendation for archival cases, 16-bit linear digitisation
followed by post-processing, is not a recommendation against this project's
approach.

---

## 5. Measurement geometry and the negligible-scattering assumption (tier B)

Transmission density depends on how collimated the illumination is. In a
scattering sample, collimated light yields a higher density than diffuse light,
the ratio being the Callier coefficient. This matters to this project because
the datasheets publish **diffuse** spectral density while a camera scan
illuminates the film with a comparatively directional source.

For correctly processed chromogenic film the model assumes scattering effects
are small enough for its transmission calculation. The reference literature
(tier B) gives the reason to expect so: the Callier effect is documented
chiefly for silver images, and in processed colour film the silver is bleached
and fixed away, leaving dye clouds that scatter little, so diffuse and
specular densities are expected to be close and the Callier coefficient near
unity. Chatterjee et al. (2023) adopt the same position: chromogenic film "is
a non-scattering material; hence, the Beer–Lambert law is deemed to be valid".

That assumption has not been checked for the apparatus and density range used
here; a bound would take matched reference-densitometer and apparatus readings
of the same patches across the actual corridor.

Three limits on that expectation are worth recording.

- It is specific to **chromogenic** material. A chromatic Callier effect is
  documented for early film colours, which are tinted, toned or dye-transfer
  images, and none of those are in this project's scope.
- It concerns the **dye image**. Retained silver from an incomplete bleach or
  fix would reintroduce scattering. Z-131 detects retained silver on its
  control strip by plotting D-max blue minus the yellow patch's blue (Table
  5-1, control limit +0.12); its D-min plot monitors base and fog only.
- Chatterjee et al. state non-scattering as a modelling ASSUMPTION they adopt
  (their §2.2), and their paper is support for Beer–Lambert spectral addition
  in chromogenic film. It is not a measurement that this scanner's geometry
  and every datasheet's geometry read the same density.

The position this project takes is therefore an assumption, stated as one: the
model assumes that scattering and geometry differences are negligible for
correctly processed chromogenic film, and no apparatus-specific measurement
closes that assumption. PROJECT.md does not record it.

---

## 6. Open questions and material not found

- **ISO 5-3:2009 was not obtained**, being a paid standard. The repository's
  Status M and Status A tables are verified entry by entry against the public
  1995 edition (§0); what remains open is whether the 2009 revision changed a
  value, and the treatment of the tails, which the standard defines by slope
  and the JSONs carry by extrapolation (Status A) or as zero beyond the last
  row (Status M). Neither is a blanket verification of the runtime observers,
  and the reversal neutral-colour discrepancy (PROJECT.md register #19) is
  narrowed by the table check and remains open.
- The X-Rite Status M white paper cited in search results resolves to a
  navigation page carrying no technical content.
- The APD table held as `data/standards/APD_ST2065-2.json` was transcribed
  from the 2012 edition. The 2020 edition's companion files
  (`st2065-2a-2020.csv`, responsivities; `st2065-2b-2020.csv`, influx) were
  compared with it: 186 wavelengths each, zero unequal cells, maximum absolute
  difference 0.0. The two editions are numerically the same table; no
  coefficient change follows.
- RP 180's own bibliography cites Evans, Hanson and Brewer, *Principles of Color
  Photography* (1953), pp. 191 and 423, and Hunt, *The Reproduction of Colour*
  (1975), p. 237, as the sources of its approach. Neither was consulted.

---

## Sources

- SMPTE RP 180-1999, *Spectral Conditions Defining Printing Density in Motion-Picture Negative and Intermediate Films* – https://pub.smpte.org/pub/rp180/rp0180-1999_stable2006.pdf (tier A, fetched in full including table 1)
- SMPTE ST 2065-2:2012, *Academy Printing Density (APD) – Spectral Responsivities, Reference Measurement Device and Spectral Calculation* – https://pub.smpte.org/doc/st2065-2/20120312-pub/st2065-2-2012.pdf (tier A, fetched in full)
- SMPTE ST 2065-3:2020, *Academy Density Exchange Encoding (ADX) – Encoding Academy Printing Density (APD) Values* – pub.smpte.org (tier A, fetched; Equation 1 and the D-min definition quoted in §4b and in `reading-datasheet-charts.md`)
- ISO 5-3:2009, *Photography and graphic technology – Density measurements – Part 3: Spectral conditions* – https://www.iso.org/standard/52915.html (NOT obtained, paid standard)
- ANSI/ISO 5-3-1995, ANSI/NAPM IT2.18-1996, *Photography – Density measurements – Part 3: Spectral conditions* – https://law.resource.org/pub/us/cfr/ibr/001/aimm.it2.18.1996.pdf (tier A, public US adoption of the 1995 edition; Tables 3 and 4, printed pp. 7–8, compared numerically with `data/standards/`)
- SMPTE ST 2065-2:2020 companion files `st2065-2a-2020.csv` and `st2065-2b-2020.csv` – https://pub.smpte.org/pub/st2065-2/st2065-2-2020.zip (tier A, fetched; compared cell by cell with the 2012 transcription)
- ISO 5-2:2001, diffuse transmission density, cited by ST 2065-2 (NOT obtained)
- Phil Green, *ISO 5 densitometry*, London College of Communication, 2008 – http://www.rps-isg.org/DF2008/ISO5Densitometry.pdf (tier B, fetched)
- Chatterjee, Trumpy and Ruedel, "Digital Unfading of Chromogenic Film Informed by Its Spectral Densities", *Heritage* 6(4):3418–3428, 2023 – https://doi.org/10.3390/heritage6040181 (tier A, fetched; see `dye-sets-across-the-three-processes.md`)
- A. Plutino, "Color systems for motion picture film digitization: a critical review", *Color Research and Application* 49(6):609–617, 2024 – https://doi.org/10.1002/col.22946 (tier A, obtained and read in full)
- Kodak publication Z-131, for the Status M process-control specification – see `process-chemistry-c41-ecn2-e6.md`

Primary verification references: [ANSI adoption of ISO 5-3:1995, Tables 3-4](https://law.resource.org/pub/us/cfr/ibr/001/aimm.it2.18.1996.pdf); [official ST 2065-2:2020 companion archive](https://pub.smpte.org/pub/st2065-2/st2065-2-2020.zip). The 1995 explicit Status A/M entries and all held APD/influx coefficients were compared on 2026-09-09.
