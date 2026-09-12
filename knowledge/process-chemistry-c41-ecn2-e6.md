# The three processes: C-41, ECN-2 and E-6

Collected 2026-08-16. This note records what the three film processes do, what
distinguishes them chemically, and how tightly a laboratory holds them, from
the manufacturer's own process specifications. The RA-4 paper process on which
the C-41 branch lands is not covered, and its chemistry and control tolerances
remain uncollected.

**Headline finding: the two negative processes use different colour developing
agents.** C-41 develops in CD-4 and ECN-2 in CD-3. Because the developing agent
becomes part of the image-dye molecule, this is a chemical difference between
the two dye sets and not merely a difference of timing. Its consequences are
developed in `dye-sets-across-the-three-processes.md`.

---

## 0. Provenance and confidence

| Tier | Source | Status |
|---|---|---|
| **A, verified primary** | Kodak publication Z-131, *Using KODAK FLEXICOLOR Chemicals* (Process C-41); Kodak publication H-24.07, *Process ECN-2 Specifications*; Kodak publication H-61B, *LAD – Laboratory Aim Density* | PDFs fetched and text-extracted in full. Figures below are quoted from those documents |
| **A, verified primary, patent example** | US5212098A, "Bromide ion determination", Eastman Kodak, granted 1993 | Web text inspected at its "Typical Process C-41 Developer" table and the replenisher table that follows it; identifies CD-4 in a typical C-41 formulation. A patent example of its date, and no current process specification |
| **B, manufacturer product literature** | Kodak Vision3 technical data sheets and product copy | The manufacturer describing its own design, and marketing-grade in register |
| **B, not fetched in full** | Kodak publication Z-119, *Using KODAK Chemicals, Process E-6* | The E-6 sequence and the identity of its colour developing agent in §3 rest on this and on the masking-coupler patent, and Z-119 has not been read; that is a source-verification gap, recorded in §7 |
| **C, practitioner** | Comparative gamma figures for ECN-2 against C-41 circulated by home-development suppliers and photography blogs | **Not verified against any manufacturer document.** Direction is corroborated by this project's own digitised curves; the specific numbers are not |

The `Kodak LAD.pdf` referenced here is the copy already held in `knowledge/`.
The Z-131 and H-24.07 PDFs are not in the repository and are not redistributed;
they are identified in the sources section below.

---

## 1. Process C-41, for still colour negative (tier A)

From Z-131, table 2-1. Times are minutes and seconds.

| Step                      | Time         | Temperature                      |
|---------------------------|--------------|----------------------------------|
| Colour developer          | 3:15         | 37.8 ± 0.15 °C (100.0 ± 0.25 °F) |
| Bleach                    | 4:20 to 6:30 | 38 ± 3 °C (100 ± 5 °F)           |
| Wash                      | 1:05         | 24 to 41 °C                      |
| Fixer                     | 4:20         | 38 ± 3 °C (100 ± 5 °F)           |
| Wash                      | 3:15         | 24 to 41 °C                      |
| Stabiliser or final rinse | 1:05         | 24 to 41 °C                      |
| Dry                       | as needed    | not over 60 °C                   |

Push processing extends the developer only. Z-131's Table 2-7 names two films,
**Portra 400UC** (EI 800, 3:45) and **Portra 800** (EI 1600, 3:45; EI 3200,
4:15), and is an instruction for those two products of its edition only.

The developer temperature tolerance of **± 0.15 °C** is the tightest
specification in the process and is an order of magnitude tighter than that of
any other step.

Z-131 describes the mechanism in these terms: the colour developing agent
"oxidizes and combines with color couplers at the site of the silver image in
each of the dye-forming emulsion layers to form a color-dye image". The bleach
"stops the developer activity and converts metallic silver back to silver
halide", and the fixer "converts silver halide in the film into soluble silver
complexes that are washed from the film".

Z-131 does not identify the agent chemically in the passages used here. Kodak
patent US5212098A independently identifies CD-4 in a typical C-41 developer
formulation, its table headed "Typical Process C-41 Developer" listing "Kodak
Color Developing Agent, CD-4" at 4.50 ± 0.25 g/L, with the agent again in the
replenisher table that follows (tier A, patent example). That supports the
agent's role in C-41; it does not make the patent's formulation a current
process specification. The full chemical name,
4-amino-3-methyl-N-ethyl-N-(β-hydroxyethyl)aniline sulfate, comes from
chemical suppliers and remains tier B.

## 2. Process ECN-2, for motion-picture colour negative (tier A)

From H-24.07.

| Step                      | Time                                     | Temperature                    |
|---------------------------|------------------------------------------|--------------------------------|
| Prebath (PB-2)            | 0:10                                     | 27 ± 1 °C                      |
| Rem-jet removal and rinse | –                                        | 27 to 38 °C                    |
| Developer (SD-49)         | 3:00                                     | 41.1 ± 0.1 °C (106.0 ± 0.2 °F) |
| Stop (SB-14)              | 0:30                                     | 27 to 38 °C                    |
| Wash                      | 0:30                                     | 27 to 38 °C                    |
| Bleach                    | 1:00 (persulfate) or 3:00 (ferricyanide) | 27 to 38 °C, or 38 ± 1 °C      |
| Wash                      | 1:00                                     | 27 to 38 °C                    |
| Fixer (F-34a)             | 2:00                                     | 38 ± 1 °C                      |
| Wash                      | 2:00                                     | 27 to 38 °C                    |
| Final rinse (FR-1)        | 0:10                                     | 27 to 38 °C                    |

The developer is **hotter and shorter** than C-41's, at 41.1 °C for three
minutes against 37.8 °C for three and a quarter, and its tolerance is tighter
still at ± 0.1 °C.

H-24.07 specifies the developer composition. The colour developing agent is
**KODAK Color Developing Agent CD-3**, at 3.9 ± 0.1 g/L in the seasoned tank and
5.2 ± 0.1 g/L in the replenisher, alongside sodium sulfite at 1.8 ± 0.2 g/L,
sodium bromide at 1.20 ± 0.05 g/L and sodium carbonate at 25.0 g/L, at
pH 10.25 ± 0.05.

**Rem-jet construction.** The legacy H-24.07 description states that "a
removable black antihalation layer (rem-jet) is coated on the back side of the
film support". It is softened in the prebath and then removed mechanically:
"the combined action of water jets and buffers remove all of the backing and
residual haze", with the buffers contacting only the support side.

That describes the remjet-backed construction, and it is construction-specific
within current VISION3: Kodak has introduced a remjet-free structure, VISION3
AHU (an anti-halation undercoat with a process-surviving backside layer), for
all four types 5/7203, 5/7207, 5/7213 and 5/7219, and states that the change
"does not alter sensitometric performance, nor does it require any adjustments
in processing" while both structures are in the market ([Kodak's AHU
reference](https://www.kodak.com/content/pdfs/motion/AHU-talking-points.pdf)).
The datasheets traced here are the H-1 sheets of the remjet construction.
Unchanged sensitometry is a statement about density against exposure; it does
not independently establish that the full spectral transmittance, base
included, is unchanged, and no evidence either way is held.

For remjet-backed film the removal step is the operational reason it cannot
simply be run through a C-41 line, although H-24.07 itself issues no such
warning and does not mention C-41 at all.

H-24.07 carries **no sensitometric aims**. It defers them explicitly to the
per-film publications and to H-61, *LAD – Laboratory Aim Density*.

## 3. Process E-6, for colour reversal (tiers A and B)

E-6 is the odd process of the three and the project's reversal path depends on
its structure. It develops twice. A **first developer** is an ordinary
black-and-white developer that reduces the exposed silver halide to metallic
silver, forming a negative silver image and forming no dye. The remaining,
previously unexposed halide is then fogged, chemically in a reversal bath or by
light, and a **colour developer** develops that fogged halide, forming dye where
the first developer did not form silver. The dye image is therefore a positive.
E-6's colour developing agent is **CD-3**, the same agent as ECN-2.

Neither the sequence nor the agent is supported here by a verified primary
quotation: Z-119 was not fetched in full and no passage from it is quoted (§0,
§7), so unlike the C-41 and ECN-2 sections this one rests on the masking-coupler
patent for the no-mask statement and on unverified process literature for the
rest.

Two consequences matter to this project.

- **Reversal film carries no orange mask.** The masking-coupler patent
  literature states the reason directly: coloured masking couplers "have no
  applicability to reversal color elements intended for direct viewing" and
  "would be visually objectionable and serve no useful purpose". A negative is
  an intermediate whose colour cast is removed at the printing stage, so it can
  afford a mask; a transparency is the final artefact and cannot. This is why
  `reversal_transform.py` needs no mask handling.

  On the negative side the mask enters the calibration as the measured spectral
  D-min in two places: the print engines build the negative on it, and the
  scan-to-Status M engines integrate each LED behind it, because the roll anchor
  subtracts D-min in integrated density and the datasheet subtracts it
  spectrally, two operations that agree only for a mask flat across each LED's
  band (PROJECT.md register #17; `reading-datasheet-charts.md` §4). The Vision3
  sheets' dashed Minimum Density curve is traced, and the ADX16 and scene
  engines apply the same factor from it.
- **Density scale.** Reversal material reaches far higher maximum densities than
  negative material, which is why this project sets a corridor D-max of 5.00 for
  a sensor-free reversal build, or 5.25 when a camera is named, against 3.30
  for negatives. The 5.25 figure is this apparatus's choice for the a7R III and
  the software's named-camera default, with no measured requirement for Bayer
  sensors as a class (PROJECT.md states the distinction). The absence of a
  mask also does not mean the base absorbs nothing: the reversal builds carry a
  base term with its own bounds.

## 4. Process control: how tightly a process is actually held (tier A)

This is the most directly useful material in Z-131 for this project, because it
states the limits within which a laboratory is required to hold the process,
and so motivates monitoring process stability during validation. It does not
quantify the expected difference between two rolls, two patches or two
stocks; that is estimated from control-strip records and repeated
measurements under the actual test conditions.

Z-131 specifies control in **Status M** density, which corroborates this
project's choice of Status M as the C-41 target. Its control-strip tolerances,
from table 5-1, are as follows.

| Parameter                | Aim adjustment | Action limit | Control limit |
|--------------------------|----------------|--------------|---------------|
| D-min                    | ± 0.03         | + 0.03       | + 0.05        |
| LD (low density)         | ± 0.04         | ± 0.06       | ± 0.08        |
| HD − LD (contrast)       | ± 0.03         | ± 0.07       | ± 0.09        |
| D-max blue − yellow blue | ± 0.07         | + 0.10       | + 0.12        |

A colour-balance spread limit of 0.09 applies to contrast.

**These limits are of the same order as the quantities this project cannot
resolve.** The basis sensitivity of the C-41 decomposition is 0.032–0.063 D
and the inter-stock distances across the fleet are 0.021–0.219 D. A process
running at the edge of Kodak's control limits would move a control-strip
density by an amount comparable to those figures, which is why process state
must be recorded alongside any inter-stock comparison; the limits do not say
how far a given run has moved, and the three quantities are different
observables over different populations, so no ratio between them is a
measure of anything.

What the table is, and is not, needs stating: these are action and control
limits on specified control-strip steps read in Status M. They say when a
laboratory must act; they are not a probability distribution for the error
of any image patch, nor of the two-wavelength mask proxy, and they give
neither the direction nor the magnitude of a given run's departure. Two
implications follow, and both are constraints on the validation roll:

1. **A validation roll must be developed in one run, on one process, with a
   control strip read.** PROJECT.md already requires "one development" for the
   stocks under test. The tolerance table is the reason that requirement is
   load-bearing: without it, process drift alone could
   manufacture or erase an inter-stock difference. Developing the comparison
   samples together controls that nuisance variable; it does not measure
   process or emulsion variation, for which replicates and a documented
   process state are still needed.
2. **Any measured inter-stock difference must be reported against measured
   process variation as well as against basis sensitivity.** A difference of
   0.05 D between two stocks developed in separate runs is confounded
   evidence: its reading depends on the control strips and repeat measurements
   of those runs, and the between-run uncertainty to report is the one those
   controls measure; a control-strip action limit is no error bar.

Z-131 gives the direction but not the magnitude of the drift: "An increase in
developer time produces an increase in the amount of dye formed", and "High
temperatures will increase the amount of dye formed; low temperatures will
decrease the amount of dye formed".

## 5. Laboratory Aim Density (tier A)

H-61B, the copy in `knowledge/`, defines LAD for Kodak Vision colour **print**
film. Its concrete figures are these.

- The LAD patch is a neutral grey of **1.0 visual density**. On Kodak Vision
  Color Print Film 2383/3383 and Vision Premier 2393/3393, the corresponding
  **Status A aim is 1.09 red, 1.06 green and 1.03 blue**. H-61B notes that other
  films require different Status A densities to reach the same visual neutral.
- **One printer light of trim is 0.025 log exposure units**, and near aim
  produces approximately 0.07 density change on the print for those stocks.

The printer-light figure is recorded because `endura_print_engine.py` carries
the same constant, in a comment reading "Roughly 0.025 logE per printer-light
point on a conventional head"; H-61B is its primary source.

PROJECT.md records that there is no LAD calibration on the negative path.
H-61B's aim triplet is what such a calibration would be anchored to, and it
applies to the print film.

## 6. Contrast: ECN-2 against C-41 (tier C, with a tier A cross-check)

Practitioner sources circulate the figures that ECN-2 aims at a gamma of roughly
0.45–0.55 while C-41 aims at roughly 0.60–0.65, the stated reason being that
ECN-2 negatives are printed onto a high-contrast print film whereas C-41
negatives are printed onto RA-4 paper. **No manufacturer document was found
stating either range**, and H-24.07 carries no sensitometric aims at all, so
these numbers must not be used as coefficients.

The direction is nonetheless consistent with this project's own digitised data.

- The central-slope gammas already recorded in
  `interimage-effects-and-stock-differentiation.md` are Portra 400 at R 0.535,
  G 0.554, B 0.634; Portra 160 at R 0.529, G 0.542, B 0.595; and Ektar 100 at
  R 0.586, G 0.584, B 0.662. Those fall in or just below the quoted C-41 band.
- The ECN-2 half is checked the same way (*measured here*, 2026-09-02, same
  middle-third least-squares window on the traced Vision3 characteristic curves):
  50D R 0.467, G 0.558, B 0.534; 250D R 0.475, G 0.556, B 0.536; 200T R 0.479,
  G 0.560, B 0.536; 500T R 0.457, G 0.535, B 0.516. The Vision3 stocks sit below
  the C-41 stocks in red and blue by 0.06–0.13 and level with them in green, so
  the direction of the practitioner claim holds while the magnitudes overlap the
  two quoted bands.

The window matters: the Vision3 sheets plot a wider exposure span, so the middle
third takes in more of the toe and shoulder than it does on the Kodak
still-film sheets, and the figures should be recomputed on each use. A process
contrast ranking would need the stocks' gammas compared in matched exposure
regions; the comparison above supports the direction of the practitioner claim
and nothing finer.

## 7. Open questions and material not found

- **Z-131 states no LAD values and no gamma aim**, only control-strip
  tolerances. The aim densities themselves are film-specific and live in the
  per-film publications.
- **Z-119 has not been read.** The E-6 sequence and its CD-3 identification
  in §3 are not verified against a primary Kodak document.
- **Neither process specification warns against cross-processing.** The
  incompatibility is inferred from the rem-jet step and from the different
  developing agents; no source states it.
- **No manufacturer gamma aim for ECN-2 was located.** H-24.07 defers to
  publications H-1-5244 and H-1-5272, which were not retrieved.
- The magnitude of the density error produced by a given developer time or
  temperature deviation is not quantified in Z-131, only its direction.
  Module 8 of *Processing KODAK Motion Picture Films* is available from Kodak
  and has been obtained as reference; its process-variation results have not
  yet been comprehensively analyzed for this model.

## Sources

- Kodak publication Z-131, *Using KODAK FLEXICOLOR Chemicals* (Process C-41) – https://business.kodakmoments.com/sites/default/files/wysiwyg/pro/chemistry/z131.pdf (tier A, fetched, 97 pp.)
- Kodak publication H-24.07, *Process ECN-2 Specifications* – http://www.handmadefilm.org/resources/technicalResources/processes/developing/kodakSpecs/h2407ECN.pdf (tier A, fetched, 38 pp.)
- Kodak publication H-61B, *LAD – Laboratory Aim Density* (tier A; local copy at `knowledge/Kodak LAD.pdf`)
- Kodak, *Using KODAK Kit Chemicals in Motion Picture Film Laboratories* – https://www.kodak.com/content/products-brochures/Film/Using-KODAK-Kit-Chemicals-in-Motion-Picture-Film-Laboratories.pdf (tier B, not fetched)
- Kodak publication Z-119, *Using KODAK Chemicals, Process E-6* – https://125px.com/docs/techpubs/kodak/z119-2.pdf (tier B, not fetched in full)
- US5212098A, "Bromide ion determination", Eastman Kodak, on the typical C-41 developer and replenisher formulations naming CD-4 – https://patents.google.com/patent/US5212098A/en (tier A, web text inspected at the formulation tables, 2026-09-12)
- US5972585, "Color negatives adapted for visual inspection", on why reversal films carry no masking coupler – https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/5972585 (tier A)
- Practitioner comparisons of ECN-2 and C-41 contrast – https://help.cinestillfilm.com/hc/en-us/articles/360028874172-Is-C-41-or-ECN-2-process-better-for-CineStill-color-film and https://www.lomography.com/school/what-is-the-difference-between-ecn-2-and-c-41-film-fa-nred3al5 (tier C, unverified)
