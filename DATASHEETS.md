# Source datasheets

Every curve used by this project derives from a manufacturer datasheet. Those
datasheets are copyright Kodak, Kodak Alaris and Fujifilm, and are **not
distributed with this repository**; this file identifies each one precisely
enough for it to be located and verified. All are published product
literature, freely available from the manufacturers and widely mirrored, and
the publication code is the reliable search key: a code such as `E-4050` or
`AF3-0262E` identifies one sheet and one revision.

The repository contains the digitised result instead. Everything under `data/`
is this project's own tracing of those published curves, licensed CC BY 4.0
under LICENSE-DATA, and the pipeline builds from `data/` alone, so a fresh
clone produces byte-identical cubes without the PDF files. The PDF files are
read only by the digitisation tooling, which is not distributed; their role
here is provenance, so that any figure in `data/` can be checked against its
source. Anyone downloading a sheet should keep it out of version control; the
datasheet paths in this repository are gitignored for that reason. The entry
`not recorded` indicates that this repository does not record that field;
the sheet may still carry one.

---

## Film, in `film_datasheet/`

| Filename | Publisher | Product | Pub. code | Revision | Digitised into |
|---|---|---|---|---|---|
| `Portra 400.pdf` | Kodak | Portra 400 | E-4050 | Jan 2025 | `Portra400_datasheet_curves`, `_spectral_sensitivity`, `_dye_density`, `_mtf` |
| `Portra 160.pdf` | Kodak | Portra 160 | E-4051 | Jan 2025 | `Portra160_datasheet_curves`, `_spectral_sensitivity`, `_dye_density`, `_mtf` |
| `Ektar 100.pdf` | Kodak | Ektar 100 | E-4046 | Jan 2025 | `Ektar100_datasheet_curves`, `_spectral_sensitivity`, `_dye_density`, `_mtf` |
| `Gold 200.pdf` | Kodak | Gold 200 | E-7022 | not recorded | `Gold200_datasheet_curves`, `_spectral_sensitivity`, `_dye_density` |
| `Ultramax 400.pdf` | Kodak | Ultra Max 400 | E-7023 | Feb 2016 | `Ultramax400_datasheet_curves`, `_spectral_sensitivity`, `_dye_density` |
| `Pro Image 100.pdf` | Kodak | Pro Image 100 | E-4L | July 1997 | `ProImage100_datasheet_curves`, `_spectral_sensitivity`, `_dye_density` |
| `Portra 800.pdf` | Kodak | Portra 800 | E-4040 | Jan 2025 | `Portra800_datasheet_curves`, `_spectral_sensitivity`, `_dye_density`, `_mtf` |
| `Ektachrome E100.pdf` | Kodak Alaris | Ektachrome E100 | E-4000 | rev. 8-18 | `EktachromeE100_dye_density`, `_datasheet_curves`, `_mtf` |
| `V3 50D.pdf` | Kodak | Vision3 50D (5203) | H-1-5203 | not recorded | `Vision3_50D_dye_density`, `_datasheet_curves`, `_spectral_sensitivity`, `V350D_mtf` |
| `V3 200T.pdf` | Kodak | Vision3 200T (5213) | H-1-5213 | not recorded | `Vision3_200T_dye_density`, `_datasheet_curves`, `_spectral_sensitivity`, `V3200T_mtf` |
| `V3 250D.pdf` | Kodak | Vision3 250D (5207) | H-1-5207 | not recorded | `Vision3_250D_dye_density`, `_datasheet_curves`, `_spectral_sensitivity`, `V3250D_mtf` |
| `V3 500T.pdf` | Kodak | Vision3 500T (5219) | H-1-5219 | not recorded | `Vision3_500T_dye_density`, `V3500T_datasheet_curves`, `Vision3_500T_spectral_sensitivity`, `V3500T_mtf` |
| `Fujifilm 200.pdf` | Fujifilm | Fujifilm 200 | AF3-0261E | 2023 | `Fujifilm200_datasheet_curves`, `_spectral_sensitivity`, `_dye_density` |
| `Fujifilm 400.pdf` | Fujifilm | Fujifilm 400 | AF3-0262E | 2023 | `Fujifilm400_datasheet_curves`, `_spectral_sensitivity`, `_dye_density` |
| `Fujifilm Pro 400H.pdf` | Fujifilm | Pro 400H | AF3-176E | not recorded | `Pro400H_datasheet_curves`, `_dye_density`, `_mtf` |
| `Fujicolor 100 [JP].pdf` | Fujifilm | Fujicolor 100 (Japan market) | 013AR0317A | 2007 | `Fujicolor100_datasheet_curves`, `_spectral_sensitivity`, `_dye_density`, `_mtf` |
| `Superia Premium 400 [JP].pdf` | Fujifilm | Superia Premium 400 (Japan market) | 013AR0324A | 2009 | `SuperiaPremium400_datasheet_curves`, `_spectral_sensitivity`, `_dye_density`, `_mtf` |
| `Superia X-Tra 400.pdf` | Fujifilm | Superia X-Tra 400 (CH) | AF3-0217E | not recorded | `SuperiaXTra400_mtf` only; the stock is not admitted to the C-41 fleet |
| `Provia 100F.pdf` | Fujifilm | Provia 100F (RDP III) | AF3-036E | not recorded | `Provia100F_dye_density`, `_datasheet_curves`, `_mtf` |
| `Velvia 100.pdf` | Fujifilm | Velvia 100 (RVP100) | AF3-202E | not recorded | `Velvia100_dye_density`, `_datasheet_curves`, `_mtf` |
| `Velvia 50.pdf` | Fujifilm | Velvia 50 (RVP50) | AF3-0221E2 | not recorded | `Velvia50_dye_density`, `_datasheet_curves`, `_mtf` |
| `Kodak 2383.pdf` | Kodak | 2383 print film | not recorded | not recorded | nothing; see below |

`Fujifilm 200.pdf` and `Fujifilm 400.pdf` publish one shared
spectral-dye-density chart, the same artwork with identical Bézier control
points. Every shipped artifact for the two stocks consequently carries an
identical numeric payload, differing only in the stock name its header
records, and the pair cannot be compared spectrally ("Current state by stock"
in PROJECT.md). `Kodak 2383.pdf` is reference reading only: no curve was
digitised from it, and where the 2383 look is wanted on the ADX16 route it
comes from Resolve's built-in "LMT Kodak 2383 Print Film Emulation", which
forms no part of this repository.

## Paper, in `paper_datasheet/`

| Filename | Publisher | Product | Pub. code | Revision | Digitised into |
|---|---|---|---|---|---|
| `Kodak Endura Premier.pdf` | Kodak | Professional Endura Premier Paper | E-4070 | March 2013 | `EnduraPremier_paper` |
| `Fujicolor Professional Paper Pro Laser Type II.pdf` | Fujifilm | Pro Laser TYPE II (Frontier QL, Japan market) | not recorded | not recorded | `FujiProLaserTypeII_paper` |
| `Fujicolor Crystal Archive Type CA.pdf` | Fujifilm | Crystal Archive Paper Type CA | AF3-0250U2 | Nov 2018 | `CrystalArchiveTypeCA_paper` |

The Pro Laser TYPE II sheet is a Product Information Bulletin for which this
repository records no publication code; its densities are labelled
ステータスA相当, Status A equivalent, exposed on a CP-48S laser printer.
Crystal Archive Type CA publishes no characteristic curves, so it cannot drive
the print engine; its JSON holds dye and sensitivity data only and is retained
as reference data only.

## Reference, in `knowledge/`

| Filename | Publisher | Subject | Pub. code | Digitised into |
|---|---|---|---|---|
| `Kodak LAD.pdf` | Kodak | Laboratory Aim Density | not recorded | nothing |

Background reading for the LAD calibration discussed in PROJECT.md; no data
was traced from it.

## Third-party literature, in `literature/`

Journal articles and conference papers consulted for the notes in
`knowledge/`. These are publisher copyright, are **not redistributed**, and
the whole directory is gitignored so that neither the files nor any text
extract can reach a published tree. No curve or numeric table has been traced
from any of them into `data/`. The rows from Triantaphillidou onward are the
sources of `knowledge/scanning-resolution-for-film.md`; web articles are held
as extracted text.

| Publication | Author | Venue | Identifier |
|---|---|---|---|
| Couplers in colour photography: chemistry and function, Part 2 | P. Bergthaller | *The Imaging Science Journal* 50(3):187–230, 2002 | doi:10.1080/13682199.2002.11784404 |
| Color systems for motion picture film digitization: a critical review | A. Plutino | *Color Research and Application* 49(6):609–617, 2024 | doi:10.1002/col.22946 |
| Mechanism of the Interimage-Effect in Color Reversal System and Its Application to Improve Color Reproduction | S. Shuto, S. Kuwashima, S. Bando, S. Takada | IS&T's 50th Annual Conference, 1997, pp. 210–212 | no DOI recorded |
| An Evaluation of MTF Determination Methods for 35mm Film Scanners | S. Triantaphillidou, R. E. Jacobson, R. Fagard-Jenkin | IS&T PICS Conference, 1999 | open access at imaging.org |
| Aerial Film Granularity and Its Influence on Visual Performance | J. C. Trinder | ISPRS 14th Congress, Hamburg, 1980, Commission I | open access at isprs.org |
| Diagnostics for Digital Capture using MTF | D. Williams, P. D. Burns | IS&T PICS Conference, 2001 | open access at imaging.org |
| Chromogenic Characterization: A Study of Kodak Color Prints, 1942–2008 | G. Weaver, Z. Long | *Topics in Photographic Preservation* 13, 2009 | prepublication PDF from the author's site |
| Film Grain, Resolution and Fundamental Film Particles, v24 | T. Vitale | self-published, 2010 | culturalheritage.org video preservation library |
| Print Grain Index (E-58); The Essential Reference Guide for Filmmakers (H-845) | Kodak | manufacturer publications, 2000 and undated | Kodak publication codes |
| Technical Guidelines for Digitizing Cultural Heritage Materials, 3rd edition | FADGI | digitizationguidelines.gov, 2023 | public federal guideline |
| ISO 6328:2000, Determination of ISO resolving power | ISO | public preview pages only | iTeh sample pages |
| The Nikon Z7's Insane Sharpness; System MTF from Bayer Sensors; Nikon Z7 pixel aperture | Strolls with my Dog | web articles, 2020 | strollswithmydog.com |
| Information capacity, NPS, NEQ and SNRi; Acutance and SQF | Imatest | web documentation | imatest.com |
| Grain and sharpness in scans and enlarger prints; Scanner Detail; Grain aliasing | N. Koren; R. N. Clark; P. L. Andrews | web articles, 2000 to 2006 | normankoren.com, clarkvision.com, photoscientia.co.uk |

The Bergthaller article is a **scanned document carrying an OCR text layer**:
its numeric values must be checked against the page images before use, and
its PDF page numbers run 185 behind the journal pagination. Two further
sources cited in `knowledge/` are open access and are not held here: Silva et
al., *Heritage* 5(4):3946–3969 (2022), doi:10.3390/heritage5040203, and
Chatterjee, Trumpy and Ruedel, *Heritage* 6(4):3418–3428 (2023),
doi:10.3390/heritage6040181. The standards documents SMPTE RP 180-1999 and
SMPTE ST 2065-2 are published free by SMPTE and are cited in full in
`knowledge/densitometry-standards-and-density-metrics.md`.

---

## Digitisation provenance

Per-sheet tracing parameters are recorded in the `digitization_audit` block of
each JSON under `data/`, covering chart page, vector-versus-raster method,
effective dpi, axis calibration, fit residuals and true measured support; that
block is the authority on how a given curve was
produced. Representative residuals are 0.0012 logH and 0.0005 D RMS on the
vector Kodak sheets, while the raster-traced Vision3 sheets record an
effective dpi of 219–261 depending on the chart. Two Vision3 wording nuances
are recorded unresolved: the 500T sensitometric chart prints
"Densitometry: ECN-2" where the other three print "Status M", and the 50D
spectral-sensitivity chart's printed y labels are adrift from their own
gridlines. The `*_mtf.json` files trace the modulation transfer function chart, a
log-log surface: each axis is fitted as log10(value) against device position
over the drawn gridlines, and the worst gridline residual is the recorded test
that the scale is logarithmic (0.001 decade on the vector Kodak sheets, 0.008
on the vector Fujifilm sheets, 0.01 on the bitmap sheets). The Velvia 50
sheet prints its 30 % gridline about 0.04 decade low while the other seven
fit within 4 px at 600 dpi; that line is excluded from the fit and the
exclusion is recorded in the file. On the Vision3 50D bitmap the three
records cross inside one line width around their 50 % point, so that file
carries a `crossing_bracket` in place of per-record MTF50 values. Read the
"Invariants" section of PROJECT.md before re-digitising
anything: it records the traps these sheets set, comprising non-zero axis
origins, differing axis ranges, curves that stop before the chart edge, and
artwork shared between sheets, each of which has produced a real error in
this project.
