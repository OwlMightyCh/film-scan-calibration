# Literature notes

These notes record the published evidence behind the modelling decisions taken
elsewhere in this repository. They exist because the pipeline makes physical
claims about film that neither the code nor the datasheets justify on their own,
and because those claims need a source that a reader can check.

## Index

| Note                                              | Question it answers |
| :------------------------------------------------ | :--- |
| `process-chemistry-c41-ecn2-e6.md`                | What the three processes do, how they differ chemically, and how tightly a laboratory holds them |
| `densitometry-standards-and-density-metrics.md`   | What Status M, Status A, printing density and Academy Printing Density actually specify, and how far they may be converted into one another |
| `dye-sets-across-the-three-processes.md`          | Where the image dyes absorb, why the three processes differ, and what the surrogate-basis decomposition can and cannot establish |
| `interimage-effects-and-stock-differentiation.md` | Whether interimage coupling is where the difference between stocks resides |
| `orange-mask-and-the-scanning-workflow.md`        | What the orange mask is, and whether this pipeline handles it correctly |
| `reading-datasheet-charts.md`                     | What each datasheet chart measures – an integral density of a neutral series, a per-dye spectrum, a reciprocal exposure – and in which space the scanner's own base subtraction happens |
| `aces-system-and-encodings.md`                    | What ACES specifies – the AP0 encoding and its reference capture device, the AP1 working encodings, the container, the transform vocabulary – and where the system's own documents say a film scan enters |
| `academy-printing-density-and-the-adx-unbuild.md`  | How Academy Printing Density is derived and measured, what ADX10 and ADX16 place where, what the original Academy specification carries that the SMPTE editions dropped, and what the Academy's ADX-to-ACES transform assumes about the negative |
| `scanning-resolution-for-film.md`                 | How densely a frame must be sampled to hold what each stock recorded – the traced MTF of sixteen sheets, the luminance-weighted comparison figure, nominal densities per stock under a lossless lens, why grain needs a separate answer, and the measurements a required figure still needs |

## Conventions

Every note follows the same structure, and readers should rely on it.

- **A provenance table comes first**, rating each source. **Tier A** is a
  primary document or peer-reviewed paper; **tier B** is manufacturer or
  practitioner literature, reliable on practice but not on mechanism; **tier
  C** is unverified testimony, useful for direction and never for
  coefficients. The tier is the kind of source. Whether it was fetched in full,
  read at an abstract only, or compared table by table is the verification
  status, stated in the row's status column, and a tier-A row may carry any of
  those states. How the source is used in the argument, as mechanism,
  vocabulary, coefficient or check, is a third thing and is stated where the
  source is used. A tier-C claim must never be promoted into the model as
  though it were measured.
- **The tier names the kind of source; the status column names the work
  done on it.** "Primary standard", "peer-reviewed paper", "manufacturer
  datasheet", "patent example" and "forum recollection" are kinds of evidence;
  "full text read", "abstract only", "numeric table compared", "not obtained"
  are verification states, and a row carries both. A paraphrase from a search
  snippet is written as attributed paraphrase, never inside quotation marks.
- **A computed figure carries its definition.** Script or expression, data
  identity, observer, wavelength support, interpolation rule, statistic and
  population, and the model state it was read from; a date alone is not
  enough, and a figure duplicated across notes names which note holds the
  authoritative value. "Exact", "independent", "verified" and "refuted" each
  state which of a model identity, a within-model calibration, a literature
  comparison and a measurement on film they mean.
- **Current conclusions accompany retained experiments.** A scope warning alone
  does not qualify a later claim: retained calculations must identify their
  tested model/data state, and current implications must agree with the
  implementation. PROJECT.md is authoritative on the current position in
  every case.
- **Computed results are labelled as model calculations**, with their data/model
  identity, reproducible expression or command, metric, support and sample
  population. A date alone is insufficient, and model closure is not validation
  against measured film.
- **An open-questions section closes each note**, recording what was sought and
  not found. This is deliberate: an absent source is itself a finding, and
  repeating a failed search wastes effort.

## Two standing cautions

**Legacy literature does not describe current stock.** Much of the admissible
material dates from 1950 to 2002, whereas the films in this project are
modelled from their current datasheet editions (one, Pro 400H, is
discontinued and modelled from its final sheet; Kodak's remjet-free Vision3
AHU construction post-dates the H-1 sheets traced here). A stock name, a
datasheet edition, remaining inventory and present manufacturing status are
four different facts. Coupler chemistry in particular has moved on.

These sources supply mechanism and vocabulary; where a claim is checkable
against `data/`, the repository's answer is reported alongside, named for what
it is: a traced manufacturer chart, a fitted model result, or a direct
measurement on film. Only the last is a measurement, and this project holds
none for the C-41 chain (PROJECT.md, Known limitations); the first two
constrain the literature claim without outranking it.

**Figures in old papers are frequently not digitisable.** Scanned articles carry
OCR text layers whose numbers may be corrupt, and printed figures often fail to
distinguish their own curves. Both failure modes have been met here and are
recorded where they occur. A curve traced from this material is held to the
same test as a datasheet curve: replotted onto the printed figure, and trusted
only where it lands on the ink.

## Source material

`Kodak LAD.pdf` is held here as reference reading and is gitignored, in common
with the manufacturer datasheets; see DATASHEETS.md. Third-party journal
articles are held in `literature/`, which is gitignored in full.

## Evidence and source verification

- Source type and verification status are separate: a peer-reviewed review is
  secondary on another standard, a fetched abstract is not a fetched full
  paper, and a patent example does not bound an entire stock fleet.
- Record the edition, page/table and precisely what was checked.
- Forum snippets must be attributed as paraphrases.
- Computed neutral closure, controlled model perturbations and measured-film
  validation are distinct forms of evidence.
