# The three processes: C-41, ECN-2 and E-6

Collected 2026-08-16. This project builds transforms for four photographic
processes but nothing in the repository recorded what those processes actually
do, what distinguishes them chemically, or how tightly they are held. This note
supplies that for the three film processes, from the manufacturer's own process
specifications. The RA-4 paper process on which the C-41 branch lands is not
covered here, and its chemistry and control tolerances remain uncollected.

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
| **B, manufacturer product literature** | Kodak Vision3 technical data sheets and product copy | The manufacturer describing its own design, and marketing-grade in register |
| **C, practitioner** | Comparative gamma figures for ECN-2 against C-41 circulated by home-development suppliers and photography blogs | **Not verified against any manufacturer document.** Direction is corroborated by this project's own digitised curves; the specific numbers are not |

The `Kodak LAD.pdf` referenced here is the copy already held in `knowledge/`.
The Z-131 and H-24.07 PDFs are not in the repository and are not redistributed;
they are identified in the sources section below.

---

## 1. Process C-41, for still colour negative (tier A)

From Z-131, table 2-1. Times are minutes and seconds.

| Step | Time | Temperature |
|---|---|---|
| Colour developer | 3:15 | 37.8 ± 0.15 °C (100.0 ± 0.25 °F) |
| Bleach | 4:20 to 6:30 | 38 ± 3 °C (100 ± 5 °F) |
| Wash | 1:05 | 24 to 41 °C |
| Fixer | 4:20 | 38 ± 3 °C (100 ± 5 °F) |
| Wash | 3:15 | 24 to 41 °C |
| Stabiliser or final rinse | 1:05 | 24 to 41 °C |
| Dry | as needed | not over 60 °C |

Push processing extends the developer only, to 3:45 for one stop and 4:15 for
two, and Z-131 restricts this to the Portra films.

The developer temperature tolerance of **± 0.15 °C** is the tightest
specification in the process and is an order of magnitude tighter than that of
any other step. Z-131 describes the mechanism in these terms: the colour
developing agent "oxidizes and combines with color couplers at the site of the
silver image in each of the dye-forming emulsion layers to form a color-dye
image". The bleach "stops the developer activity and converts metallic silver
back to silver halide", and the fixer "converts silver halide in the film into
soluble silver complexes that are washed from the film".

Z-131 does not name the developing agent chemically. The designation CD-4, and
its identity as 4-amino-3-methyl-N-ethyl-N-(β-hydroxyethyl)aniline sulfate, come
from chemical suppliers and are tier B rather than tier A here.

## 2. Process ECN-2, for motion-picture colour negative (tier A)

From H-24.07.

| Step | Time | Temperature |
|---|---|---|
| Prebath (PB-2) | 0:10 | 27 ± 1 °C |
| Rem-jet removal and rinse | – | 27 to 38 °C |
| Developer (SD-49) | 3:00 | 41.1 ± 0.1 °C (106.0 ± 0.2 °F) |
| Stop (SB-14) | 0:30 | 27 to 38 °C |
| Wash | 0:30 | 27 to 38 °C |
| Bleach | 1:00 (persulfate) or 3:00 (ferricyanide) | 27 to 38 °C, or 38 ± 1 °C |
| Wash | 1:00 | 27 to 38 °C |
| Fixer (F-34a) | 2:00 | 38 ± 1 °C |
| Wash | 2:00 | 27 to 38 °C |
| Final rinse (FR-1) | 0:10 | 27 to 38 °C |

The developer is **hotter and shorter** than C-41's, at 41.1 °C for three
minutes against 37.8 °C for three and a quarter, and its tolerance is tighter
still at ± 0.1 °C.

H-24.07 specifies the developer composition. The colour developing agent is
**KODAK Color Developing Agent CD-3**, at 3.9 ± 0.1 g/L in the seasoned tank and
5.2 ± 0.1 g/L in the replenisher, alongside sodium sulfite at 1.8 ± 0.2 g/L,
sodium bromide at 1.20 ± 0.05 g/L and sodium carbonate at 25.0 g/L, at
pH 10.25 ± 0.05.

**Rem-jet.** H-24.07 states that "a removable black antihalation layer (rem-jet)
is coated on the back side of the film support". It is softened in the prebath
and then removed mechanically: "the combined action of water jets and buffers
remove all of the backing and residual haze", with the buffers contacting only
the support side. This is the operational reason ECN-2 film cannot simply be run
through a C-41 line, although H-24.07 itself issues no such warning and does not
mention C-41 at all.

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

Two consequences matter to this project.

- **Reversal film carries no orange mask.** The masking-coupler patent
  literature states the reason directly: coloured masking couplers "have no
  applicability to reversal color elements intended for direct viewing" and
  "would be visually objectionable and serve no useful purpose". A negative is
  an intermediate whose colour cast is removed at the printing stage, so it can
  afford a mask; a transparency is the final artefact and cannot. This is why
  `reversal_transform.py` needs no mask handling. On the negative side the mask
  enters only as measured spectral D-min in the print engine. It cancels on the
  scan-to-Status M path, and it is not modelled at all for the Vision3 stocks.
- **Density scale.** Reversal material reaches far higher maximum densities than
  negative material, which is why this project sets a corridor D-max of 5.00 for
  a sensor-free reversal build, or 5.25 when a Bayer camera is named, against
  3.30 for negatives.

## 4. Process control: how tightly a process is actually held (tier A)

This is the most directly useful material in Z-131 for this project, because it
quantifies how much two rolls of the same emulsion may legitimately differ.

Z-131 specifies control in **Status M** density, which corroborates this
project's choice of Status M as the C-41 target. Its control-strip tolerances,
from table 5-1, are as follows.

| Parameter | Aim adjustment | Action limit | Control limit |
|---|---|---|---|
| D-min | ± 0.03 | + 0.03 | + 0.05 |
| LD (low density) | ± 0.04 | ± 0.06 | ± 0.08 |
| HD − LD (contrast) | ± 0.03 | ± 0.07 | ± 0.09 |
| D-max blue − yellow blue | ± 0.07 | + 0.10 | + 0.12 |

A colour-balance spread limit of 0.09 applies to contrast.

**These numbers sit squarely inside the range this project cannot resolve.** The
measured basis sensitivity of the C-41 decomposition is 0.034–0.063 D and the
inter-stock distances across the fleet are 0.024–0.220 D. A process running
anywhere within Kodak's own control limits can therefore move a density by an
amount comparable to the difference between two different emulsions. Two
implications follow, and both are new constraints on the planned validation
roll:

1. **A validation roll must be developed in one run, on one process, with a
   control strip read.** PROJECT.md already requires "one development" for the
   stocks under test. The tolerance table is the reason that requirement is
   load-bearing rather than tidy: without it, process drift alone could
   manufacture or erase an inter-stock difference.
2. **Any measured inter-stock difference must be reported against process
   tolerance, not only against basis sensitivity.** A difference of 0.05 D
   between two stocks developed in separate runs is not evidence of anything.

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

The printer-light figure is worth recording because `endura_print_engine.py`
already carries the same constant as an unattributed approximation, in a comment
reading "Roughly 0.025 logE per printer-light point on a conventional head".
That value is correct and now has a primary source.

PROJECT.md records that there is no LAD calibration on the negative path.
H-61B's aim triplet is what such a calibration would be anchored to, and it
applies to the print film rather than to the negative.

## 6. Contrast: ECN-2 against C-41 (tier C, with a tier A cross-check)

Practitioner sources circulate the figures that ECN-2 aims at a gamma of roughly
0.45–0.55 while C-41 aims at roughly 0.60–0.65, the stated reason being that
ECN-2 negatives are printed onto a high-contrast print film whereas C-41
negatives are printed onto RA-4 paper. **No manufacturer document was found
stating either range**, and H-24.07 carries no sensitometric aims at all, so
these numbers must not be used as coefficients.

The direction is nonetheless consistent with this project's own digitised data.
The central-slope gammas already recorded in
`interimage-effects-and-stock-differentiation.md` are Portra 400 at R 0.534,
G 0.552, B 0.633; Portra 160 at R 0.523, G 0.544, B 0.605; and Ektar 100 at
R 0.563, G 0.571, B 0.661. Those fall in or just below the quoted C-41 band. The
ECN-2 half of the claim remains unchecked against the repository's Vision3
curves.

## 7. Open questions and material not found

- **Z-131 states no LAD values and no gamma aim**, only control-strip
  tolerances. The aim densities themselves are film-specific and live in the
  per-film publications.
- **Neither process specification warns against cross-processing.** The
  incompatibility is inferred from the rem-jet step and from the different
  developing agents rather than stated.
- **No manufacturer gamma aim for ECN-2 was located.** H-24.07 defers to
  publications H-1-5244 and H-1-5272, which were not retrieved.
- The magnitude of the density error produced by a given developer time or
  temperature deviation is not quantified in Z-131, only its direction.
  Module 8 of *Processing KODAK Motion Picture Films* is named as the ECN-2
  equivalent and was not retrieved.

## Sources

- Kodak publication Z-131, *Using KODAK FLEXICOLOR Chemicals* (Process C-41) – https://business.kodakmoments.com/sites/default/files/wysiwyg/pro/chemistry/z131.pdf (tier A, fetched, 97 pp.)
- Kodak publication H-24.07, *Process ECN-2 Specifications* – http://www.handmadefilm.org/resources/technicalResources/processes/developing/kodakSpecs/h2407ECN.pdf (tier A, fetched, 38 pp.)
- Kodak publication H-61B, *LAD – Laboratory Aim Density* (tier A; local copy at `knowledge/Kodak LAD.pdf`)
- Kodak, *Using KODAK Kit Chemicals in Motion Picture Film Laboratories* – https://www.kodak.com/content/products-brochures/Film/Using-KODAK-Kit-Chemicals-in-Motion-Picture-Film-Laboratories.pdf (tier B, not fetched)
- Kodak publication Z-119, *Using KODAK Chemicals, Process E-6* – https://125px.com/docs/techpubs/kodak/z119-2.pdf (tier B, not fetched in full)
- US5972585, "Color negatives adapted for visual inspection", on why reversal films carry no masking coupler – https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/5972585 (tier A)
- Practitioner comparisons of ECN-2 and C-41 contrast – https://help.cinestillfilm.com/hc/en-us/articles/360028874172-Is-C-41-or-ECN-2-process-better-for-CineStill-color-film and https://www.lomography.com/school/what-is-the-difference-between-ecn-2-and-c-41-film-fa-nred3al5 (tier C, unverified)
