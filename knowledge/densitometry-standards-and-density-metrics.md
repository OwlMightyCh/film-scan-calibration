# Density metrics: Status M, printing density, APD, and measurement geometry

Collected 2026-08-16. This project targets three different density metrics –
Status M for C-41, SMPTE printing density for ECN-2, and Status A for the RA-4
paper inversion – and treats each as a fixed reference. The repository records
which metric each path targets, but not what those standards themselves say or
what they claim about their own accuracy. This note supplies that from the
standards themselves.

**Headline finding: SMPTE RP 180 states in its own introduction that Status M
"can only approximate printing densities for most materials".** The two metrics
this project uses for its two negative paths are not interchangeable, and the
standard that defines one of them says so explicitly.

A second result is a clean verification rather than a caveat: the repository's
transcription of the RP 180 responsivity table, whose provenance note recorded
that it had never been checked against the standard, **matches the published
table exactly** at every wavelength.

---

## 0. Provenance and confidence

| Tier | Source | Status |
|---|---|---|
| **A, verified primary** | SMPTE RP 180-1999, *Spectral Conditions Defining Printing Density in Motion-Picture Negative and Intermediate Films*; SMPTE ST 2065-2:2012, *Academy Printing Density* | Both fetched in full from `pub.smpte.org`, including their numeric responsivity tables. Quotations below are verbatim |
| **A, verified primary** | Kodak publication Z-131, on which status C-41 process control is read in | Fetched; see `process-chemistry-c41-ecn2-e6.md` |
| **B, secondary technical** | Phil Green, *Bringing one of the oldest international standards into the 21st century: ISO 5 densitometry*, London College of Communication, 2008 | A conference presentation rather than the standard. Reliable on the direction of ISO 5's revision, not a substitute for ISO 5-3 itself |
| **B, reference literature** | General statements on the Callier effect in dye versus silver images | Consistent across sources and corroborated by a peer-reviewed statement that chromogenic film is non-scattering |

**ISO 5-3 itself was not obtained.** It is a paid ISO standard. Every statement
below attributed to ISO 5-3 is reported at second hand, and the repository's own
`StatusM_ISO5-3.json` and `StatusA_ISO5-3.json` therefore remain unverified
against the primary document, in contrast to the RP 180 file.

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

## 2. Status M and Status A (tier B, primary not obtained)

Both are defined in ISO 5-3, *Photography and graphic technology – Density
measurements – Part 3: Spectral conditions*, currently ISO 5-3:2009.

- **Status M** is the metric for colour materials **intended for printing**,
  which is to say camera negatives. The C-41 datasheets publish in it, and
  Z-131 specifies process control in it. It is this project's C-41 target.
- **Status A** is the metric for material **intended for direct viewing**,
  which is to say reversal film and prints. This project uses it in exactly one
  place, the inversion of the RA-4 paper characteristic curves, and Kodak's LAD
  aim for print film is quoted in it.

The distinction is one of intended use rather than of chemistry, and it is the
same distinction that decides whether a film carries an orange mask.

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
transcribed from RP 180 in an earlier session, extracted later from an inline
table in `cineon_pd_engine.py`, with the note that "RP_180.pdf itself has not
been migrated into this repo", so the file carries no check against the
standard.

That check is recorded here. Every one of the 37 wavelengths the file carries
matches the published table **exactly**, with zero mismatches across all three
channels. The standard additionally tabulates 370 nm and 740 nm, which the
repository file omits; both rows are zero in all three channels, so the omission
has no effect. The recorded peak wavelengths of 670, 530 and 430 nm are correct.

## 4. SMPTE ST 2065-2: Academy Printing Density (tier A, fetched)

APD is the live standard in this family. It is a **different metric from
RP 180**, not a reissue of it, and the two must not be conflated.

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

This project targets RP 180 alone. `RP180_responsivities.json` carries its
values, and the systematics register distinguishes RP 180 from APD by their
sub-400 nm blue content. No APD responsivity table is held in the repository,
and no engine reads one.

## 4a. Cineon printing density and ADX (tier A)

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
PROJECT.md's glossary draws the distinction, recording that this project's
values are RP 180's throughout notwithstanding the `cineon_pd_engine.py`
filename. **One label remains untightened**, the engine reference table
describing the ECN-2 output as "Cineon/RP 180 printing density". That matters
because Plutino's criticism attaches to the Cineon definition and not to the
RP 180 table.

**The Cineon encoding constants**, which the repository uses at one point
without a source:

- 10-bit log encoding over [0, 1023], one code value being **0.002 OD**.
- Reference black at code **95** and diffuse white at code **685**.
- An offset of 2.048 corresponding to roughly **3.72 log exposure**, about
  12.4 stops, for a film of gamma 0.55.

PROJECT.md refers to an "upstream Cineon diffuse-white placement at 685/1023".
That value is the standard Cineon convention, sourced to Plutino (2024).

**APD's applicability**, from the same review: "APD are based on the spectral
sensitivities of contemporary motion picture film prints, so when working with
films from the early cinema or non-modern films, the tone reproduction may
present artifacts and errors… because the ADX system has been developed for film
production, not archiving." Scanner light sources "have been selected to have an
emission matching perfectly the APD curves, thus not being suitable for the
digitization of all the historical cinematographic materials."

**This caveat does not bite here, and it is worth saying why.** Every stock in
this project is current product, which is precisely the case APD was designed
for. The criticism applies to archival digitisation of early or discontinued
material, which is outside this project's scope. Plutino's recommendation for
those cases, 16-bit linear digitisation followed by post-processing rather than
an encoded density metric, is therefore not a recommendation against this
project's approach.

## 5. Measurement geometry, and why the Callier effect does not bite here (tier B)

Transmission density depends on how collimated the illumination is. In a
scattering sample, collimated light yields a higher density than diffuse light,
the ratio being the Callier coefficient. This matters to this project because
the datasheets publish **diffuse** spectral density while a camera scan
illuminates the film with a comparatively directional source.

The reassuring result is that the effect is a **silver-image phenomenon**. In
processed colour film the silver is bleached and fixed away and the image is
composed of dye clouds, which scatter very little; diffuse and specular
densities are consequently close to equal and the Callier coefficient is near
unity. A peer-reviewed statement of the same fact appears in Chatterjee et al.
(2023): chromogenic film "is a non-scattering material; hence, the
Beer–Lambert law is deemed to be valid".

Two limits on that reassurance are worth recording.

- It is specific to **chromogenic** material. A chromatic Callier effect is
  documented for early film colours, which are tinted, toned or dye-transfer
  rather than chromogenic, and none of those are in this project's scope.
- It concerns the **dye image**. Retained silver from an incomplete bleach or
  fix would reintroduce scattering, which is one of the faults Z-131's D-min
  monitoring exists to catch.

This project's assumption that datasheet diffuse density applies to its own
scan geometry is therefore sound. It is not documented anywhere in PROJECT.md.

## 6. Open questions and material not found

- **ISO 5-3 was not obtained**, being a paid standard. The repository's Status M
  and Status A responsivity JSONs remain unverified against the primary
  document, unlike the RP 180 file. Verifying them is the obvious next
  equivalent check and would need a purchased copy.
- The X-Rite Status M white paper cited in search results resolves to a
  navigation page carrying no technical content.
- The copy of ST 2065-2 fetched here is the 2012 edition. Its responsivity
  values were not compared against the 2020 edition, and no APD table from
  either edition is held in the repository.
- RP 180's own bibliography cites Evans, Hanson and Brewer, *Principles of Color
  Photography* (1953), pp. 191 and 423, and Hunt, *The Reproduction of Colour*
  (1975), p. 237, as the sources of its approach. Neither was consulted.

## Sources

- SMPTE RP 180-1999, *Spectral Conditions Defining Printing Density in Motion-Picture Negative and Intermediate Films* – https://pub.smpte.org/pub/rp180/rp0180-1999_stable2006.pdf (tier A, fetched in full including table 1)
- SMPTE ST 2065-2:2012, *Academy Printing Density (APD) – Spectral Responsivities, Reference Measurement Device and Spectral Calculation* – https://pub.smpte.org/doc/st2065-2/20120312-pub/st2065-2-2012.pdf (tier A, fetched in full)
- ISO 5-3:2009, *Photography and graphic technology – Density measurements – Part 3: Spectral conditions* – https://www.iso.org/standard/52915.html (NOT obtained, paid standard)
- ISO 5-2:2001, diffuse transmission density, cited by ST 2065-2 (NOT obtained)
- Phil Green, *ISO 5 densitometry*, London College of Communication, 2008 – http://www.rps-isg.org/DF2008/ISO5Densitometry.pdf (tier B, fetched)
- Chatterjee, Trumpy and Ruedel, "Digital Unfading of Chromogenic Film Informed by Its Spectral Densities", *Heritage* 6(4):3418–3428, 2023 – https://doi.org/10.3390/heritage6040181 (tier A, fetched; see `dye-sets-across-the-three-processes.md`)
- A. Plutino, "Color systems for motion picture film digitization: a critical review", *Color Research and Application* 49(6):609–617, 2024 – https://doi.org/10.1002/col.22946 (tier A, obtained and read in full)
- Kodak publication Z-131, for the Status M process-control specification – see `process-chemistry-c41-ecn2-e6.md`
