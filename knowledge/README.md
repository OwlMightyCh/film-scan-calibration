# Literature notes

These notes record the published evidence behind the modelling decisions taken
elsewhere in this repository. They exist because the pipeline makes physical
claims about film that neither the code nor the datasheets justify on their own,
and because those claims need a source that a reader can check.

## Index

| Note | Question it answers |
|---|---|
| `process-chemistry-c41-ecn2-e6.md` | What the three processes do, how they differ chemically, and how tightly a laboratory holds them |
| `densitometry-standards-and-density-metrics.md` | What Status M, Status A, printing density and Academy Printing Density actually specify, and how far they may be converted into one another |
| `dye-sets-across-the-three-processes.md` | Where the image dyes absorb, why the three processes differ, and what the surrogate-basis decomposition can and cannot establish |
| `interimage-effects-and-stock-differentiation.md` | Whether interimage coupling is where the difference between stocks resides |
| `orange-mask-and-the-scanning-workflow.md` | What the orange mask is, and whether this pipeline handles it correctly |

## Conventions

Every note follows the same structure, and readers should rely on it.

- **A provenance table comes first**, rating each source. **Tier A** is a
  verified primary document that was fetched and read. **Tier B** is
  manufacturer or practitioner literature, reliable on practice but not on
  mechanism. **Tier C** is unverified testimony, useful for direction and never
  for coefficients. A tier-C claim must never be promoted into the model as
  though it were measured.
- **A scope note marks superseded passages.** Literature findings stand as
  collected; where a note's project implications have since been revised, the
  revision is marked in place rather than by rewriting history. PROJECT.md is
  authoritative on the current position in every case.
- **Measurements computed from this repository's own data are labelled as
  such**, with the date, so that they are never confused with published values.
- **An open-questions section closes each note**, recording what was sought and
  not found. This is deliberate: an absent source is itself a finding, and
  repeating a failed search wastes effort.

## Two standing cautions

**Legacy literature does not describe current stock.** Much of the admissible
material dates from 1950 to 2002, whereas every film in this project is current
product. Coupler chemistry in particular has moved on. These sources supply
mechanism and vocabulary; where a claim is checkable against `data/`, the
measured answer takes precedence and is reported alongside.

**Figures in old papers are frequently not digitisable.** Scanned articles carry
OCR text layers whose numbers may be corrupt, and printed figures often fail to
distinguish their own curves. Both failure modes have been met here and are
recorded where they occur. Apply the digitisation routine in PROJECT.md before
trusting any curve traced from this material.

## Source material

`Kodak LAD.pdf` is held here as reference reading and is gitignored, in common
with the manufacturer datasheets; see DATASHEETS.md. Third-party journal
articles are held in `literature/`, which is gitignored in full.
