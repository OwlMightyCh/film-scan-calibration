# Source datasheets

Every curve this project uses comes from a manufacturer datasheet. Those
datasheets are copyright Kodak, Kodak Alaris and Fujifilm, so they are **not
distributed with this repository**. This file identifies each one precisely
enough to find and verify it.

All of them are published product literature, freely available from the
manufacturers and widely mirrored. The publication codes below are the reliable
search key — a code such as `E-4050` or `AF3-0262E` identifies one sheet and
one revision.

**What is in the repo instead:** the digitized result. Everything under `data/`
is this project's tracing of those published curves, licensed CC BY 4.0
(LICENSE-DATA). The pipeline builds from `data/`, so a fresh clone produces
byte-identical cubes without the PDFs.

**What you need the PDFs for:** re-running the digitizers. Eleven scripts read
the PDFs directly — `engine/c41/portra_digitize.py`,
`engine/c41/portra_digitize_sens.py`, `engine/c41/fuji_digitize.py`,
`engine/c41/fuji_prolaser_digitize.py`, `engine/c41/endura_digitize.py`,
`engine/c41/datasheet_paths.py`, `engine/c41/datasheet_render.py`,
`engine/c41/datasheet_overlay.py`, `engine/c41/paper_overlay.py`,
`engine/ecn2/v3_datasheet_digitize.py` and `engine/ecn2/v3_dye_digitize.py`.
To re-digitize or re-run an overlay check, download the sheets and restore them
to the filenames in the tables below. Those paths are gitignored, so local
copies stay untracked.

`not recorded` below means this repository does not record that field. It is not
a claim that the sheet lacks one.

---

## Film — `film_datasheet/`

| Filename | Publisher | Product | Pub. code | Revision | Digitized into |
|---|---|---|---|---|---|
| `Portra 400.pdf` | Kodak | Portra 400 | E-4050 | Jan 2025 | `Portra400_datasheet_curves`, `_spectral_sensitivity`, `_dye_density` |
| `Portra 160.pdf` | Kodak | Portra 160 | E-4051 | Jan 2025 | `Portra160_datasheet_curves`, `_spectral_sensitivity`, `_dye_density` |
| `Ektar 100.pdf` | Kodak | Ektar 100 | E-4046 | Jan 2025 | `Ektar100_datasheet_curves`, `_spectral_sensitivity`, `_dye_density` |
| `Gold 200.pdf` | Kodak | Gold 200 | E-7022 | not recorded | `Gold200_datasheet_curves`, `_spectral_sensitivity`, `_dye_density` |
| `Ultramax 400.pdf` | Kodak | Ultra Max 400 | E-7023 | Feb 2016 | `Ultramax400_datasheet_curves`, `_spectral_sensitivity`, `_dye_density` |
| `Ektachrome E100.pdf` | Kodak Alaris | Ektachrome E100 | E-4000 | rev. 8-18 | `EktachromeE100_dye_density` |
| `V3 50D.pdf` | Kodak | Vision3 50D (5203) | H-1-5203 | not recorded | `Vision3_50D_dye_density` |
| `V3 200T.pdf` | Kodak | Vision3 200T (5213) | H-1-5213 | not recorded | `Vision3_200T_dye_density` |
| `V3 250D.pdf` | Kodak | Vision3 250D (5207) | H-1-5207 | not recorded | `Vision3_250D_dye_density` |
| `V3 500T.pdf` | Kodak | Vision3 500T (5219) | H-1-5219 | not recorded | `Vision3_500T_dye_density`, `V3500T_datasheet_curves` |
| `Fujifilm 200.pdf` | Fujifilm | Fujifilm 200 | AF3-0261E | 2023 | `Fujifilm200_datasheet_curves`, `_spectral_sensitivity`, `_dye_density` |
| `Fujifilm 400.pdf` | Fujifilm | Fujifilm 400 | AF3-0262E | 2023 | `Fujifilm400_datasheet_curves`, `_spectral_sensitivity`, `_dye_density` |
| `Fujifilm Pro 400H.pdf` | Fujifilm | Pro 400H | AF3-176E | not recorded | `Pro400H_datasheet_curves`, `_dye_density` |
| `Fujicolor 100 [JP].pdf` | Fujifilm | Fujicolor 100 (Japan market) | 013AR0317A | 2007 | `Fujicolor100_datasheet_curves`, `_spectral_sensitivity`, `_dye_density` |
| `Superia Premium 400 [JP].pdf` | Fujifilm | Superia Premium 400 (Japan market) | 013AR0324A | 2009 | `SuperiaPremium400_datasheet_curves`, `_spectral_sensitivity`, `_dye_density` |
| `Provia 100F.pdf` | Fujifilm | Provia 100F (RDP III) | AF3-036E | not recorded | `Provia100F_dye_density` |
| `Velvia 100.pdf` | Fujifilm | Velvia 100 (RVP100) | AF3-202E | not recorded | `Velvia100_dye_density` |
| `Velvia 50.pdf` | Fujifilm | Velvia 50 (RVP50) | not recorded | not recorded | `Velvia50_dye_density` |
| `Kodak 2383.pdf` | Kodak | 2383 print film | not recorded | not recorded | nothing — see note below |

`Kodak 2383.pdf` is reference reading only. No curve was digitized from it; the
2383 look was only ever exercised through a stock third-party LUT, which is not
part of this repository and carries its own licence.

## Paper — `paper_datasheet/`

| Filename | Publisher | Product | Pub. code | Revision | Digitized into |
|---|---|---|---|---|---|
| `Kodak Endura Premier.pdf` | Kodak | Professional Endura Premier Paper | E-4070 | March 2013 | `EnduraPremier_paper` |
| `Fujicolor Professional Paper Pro Laser Type II.pdf` | Fujifilm | Pro Laser TYPE II (Frontier QL, Japan market) | not recorded | not recorded | `FujiProLaserTypeII_paper` |
| `Fujicolor Crystal Archive Type CA.pdf` | Fujifilm | Crystal Archive Paper Type CA | AF3-0250U2 | Nov 2018 | `CrystalArchiveTypeCA_paper` |

The Pro Laser TYPE II sheet is a Product Information Bulletin; this repository
records no publication code for it. Its densities are labelled ステータスA相当
(Status A equivalent), exposed on a CP-48S laser printer.

## Reference — `knowledge/`

| Filename | Publisher | Subject | Pub. code | Digitized into |
|---|---|---|---|---|
| `Kodak LAD.pdf` | Kodak | Laboratory Aim Density | not recorded | nothing |

Background reading for the LAD calibration discussed in PROJECT.md. No data was
traced from it.

---

## Digitization provenance

Per-sheet tracing parameters are recorded in the `digitization_audit` block of
each JSON under `data/` — chart page, vector-versus-raster method, effective
dpi, axis calibration, fit residuals and true measured support. That block, not
this file, is the authority on how a given curve was produced. Representative
residuals are 0.0012 logH and 0.0005 D RMS on the vector Kodak sheets; the
raster-traced Vision3 sheets record effective dpi of 246–261.

Read the "Invariants" section of PROJECT.md before re-digitizing anything. It
records the traps these sheets set — non-zero axis origins, differing axis
ranges, curves that stop before the chart edge, and shared artwork between
sheets — each of which has produced a real error in this project.
