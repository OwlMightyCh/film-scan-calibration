# Scanning resolution for film: what the datasheets support, and what remains to be measured

Collected 2026-09-12. The question this note answers is how densely a film
frame must be sampled for the scan to hold what the film recorded, and how far
that figure can be derived from the manufacturer's published image-structure
data. It is answered for the sixteen stocks whose modulation transfer function
(MTF) charts have been traced into `data/films/<Stock>_mtf.json`, across the
three processes this repository models.

The answer has two parts. The traced MTF yields comparison frequencies per stock
and, under a stated optical framing, a set of sampling scenarios to test; the
datasheets support those only up to the frequency at which the manufacturer stops
plotting. A required density in the strict sense, one that guarantees a stated
loss under stated conditions, needs acceptance criteria and same-frame
measurements of film and scanner that the sheets do not carry; the protocol for
them is stated in §7 and the work is on hold.

**Headline finding: the datasheet MTF supports comparison between stocks and
the choice of scan test settings; it does not, on its own, establish a
required scanning resolution for any stock.**

Two subsidiary findings shape everything below.

- First, the question splits into two that the sheets measure with different
  instruments and that rank stocks differently: the density needed to capture the
  *scene-detail response* the MTF characterises, and the density at which the
  scan stops aliasing the *grain structure*, for which the sheets publish
  amplitude figures and no bandwidth.
- Second, the Kodak charts in hand end between 75 and 82 cycles/mm, and on the
  Portra, Ektar and the three faster Vision3 sheets the sharpest records are
  still at 34 to 47 % response there, so the film curve is unknown beyond a
  frequency that a 22 megapixel full-RGB capture of a 135 frame already places
  at Nyquist.

---

## 0. Provenance and confidence

| Tier | Source | Status |
|---|---|---|
| **A, verified primary** | Kodak Alaris datasheets E-4051, E-4050, E-4040, E-4046 (January 2025 revisions: Portra 160, 400, 800, Ektar 100); E-4000 rev. 8-18 (Ektachrome E100); Kodak H-1-5203, -5213, -5207, -5219 (Vision3 50D, 200T, 250D, 500T); Fujifilm AF3-176E (Pro 400H), 013AR0317A (Fujicolor 100), 013AR0324A (Superia Premium 400), AF3-0217E (Superia X-Tra 400), AF3-202E (Velvia 100), AF3-0221E2 (Velvia 50), AF3-036E (Provia 100F) | Held locally (DATASHEETS.md carries codes and editions); MTF charts traced in full by the film MTF digitiser (unpublished), every trace replotted onto the ink and scored; Print Grain Index, RMS granularity and resolving-power figures read from the sheet text |
| **A, primary standard, preview pages only** | ISO 6328:2000, *Photography – Photographic materials – Determination of ISO resolving power* | Public preview pages fetched and read: definitions, contrast-ratio rule, tribar criterion, exposure and focus maxima. Procedure clauses and tables not in the preview |
| **A, primary standard, catalogue only** | ANSI PH2.39-1977 (R1986), *Photographic Modulation Transfer Function* | Not fetched; the sinusoidal target, the nominal 60 % aerial modulation and the adjacency caveat are taken from a catalogue summary and from Kodak H-845, which cites the standard |
| **A, peer-reviewed, abstract only** | R. C. Jones, "Information Capacity of Photographic Films", *JOSA* 51(11):1159–1171, 1961 | Abstract read: capacity from the sine-wave response and the Wiener spectrum of granularity, 0.45 to 2.85 Mbit per cm² for four black-and-white films |
| **A, peer-reviewed, abstract only** | G. C. Farnell, "Colour Negative Granularity: A Simple Theoretical Approach", *J. Photogr. Sci.* 40(3):79–82, 1992; "Estimating the Size and Profile of Diffuse Dye Clouds in Colour Negative Film", *J. Photogr. Sci.* 44(4), 1996 | Abstracts read: granularity against density and coupler starvation; dye-cloud size derived jointly from MTF and noise power spectrum |
| **A, conference paper, full text read** | S. Triantaphillidou, R. E. Jacobson, R. Fagard-Jenkin, "An Evaluation of MTF Determination Methods for 35mm Film Scanners", IS&T PICS 1999 | Open-access PDF read in full: sine-chart, film-grain-noise and slanted-edge methods on one scanner; Kodak T-Max P3200 (black-and-white) grain treated as flat noise power to 40 to 50 cycles/mm |
| **A, conference paper, full text read** | J. C. Trinder, "Aerial Film Granularity and Its Influence on Visual Performance", ISPRS Congress, Hamburg, 1980 | Open-access PDF read in full: measured Wiener spectra of black-and-white aerial films, flat below about 100 lines/mm; Selwyn law verified; information capacity computed |
| **A, conference paper, full text read** | D. Williams and P. D. Burns, "Diagnostics for Digital Capture using MTF", IS&T PICS 2001 | Open-access PDF read: slanted-edge MTF signatures of aperture, defocus, sampling and processing in scanners |
| **B, federal guideline on ISO metrics** | FADGI, *Technical Guidelines* for cultural-heritage digitisation, 3rd edition, 2023 (full title in DATASHEETS.md) | Fetched; film tables and section 2.4 read: transmissive film sampling levels and their stated rationale; SFR50 and SFR10 acceptance criteria per ISO 12233 and ISO 16067-2; response at Nyquist listed in section 2.4.8 as informative and not a compliance metric |
| **B, manufacturer literature** | Kodak, *Print Grain Index*, E-58, 2000; Kodak, *The Essential Reference Guide for Filmmakers*, H-845 | E-58 read in full; H-845 image-structure pages 54 to 57 read: MTF method, adjacency effect, RMS granularity definition, resolving-power method |
| **B, peer-reviewed conservation study** | G. Weaver and Z. Long, "Chromogenic Characterization: A Study of Kodak Color Prints, 1942–2008", *Topics in Photographic Preservation* 13, 2009 | Dye-cloud section read: cloud formation and 1.25 to 4 µm diameters in Kodak papers; carries no negative-film sizes |
| **B, practitioner measurement** | E. M. Granger and K. N. Cupery, subjective quality factor, as documented by Imatest ("Acutance and SQF") and Bob Atkins; Imatest, "Information capacity, NPS, NEQ and SNRi" (measurement guidance only); Strolls with my Dog, "System MTF from Bayer Sensors" and "The Nikon Z7's Insane Sharpness" (2020); N. Koren, "Grain and sharpness in scans and enlarger prints" (2003); R. N. Clark, "Scanner Detail" (2000 to 2006) | Web pages read; the Z7 article also read in full from a supplied PDF |
| **C, practitioner test** | P. L. Andrews, "Grain aliasing", Photoscientia, 2000 | Read: microscope estimate of dye speckle and cluster size, aliasing tests at a 9.4 µm scanner pitch |
| **C, criticised testimony** | T. Vitale, *Film Grain, Resolution and Fundamental Film Particles*, v24, 2010 | Skimmed; criticised by manufacturers as containing many errors; used only as the contrast case for the practitioner figure of about 2800 ppi |
| **model calculation** | Every figure marked *computed here* | A calculation from `data/films/*_mtf.json` on the model state of 2026-09-12 by the expression stated beside it; no film was scanned or measured |

Every chart figure in this note is read from the traced file. Readings of the
same charts by eye, made before the tracing, were wrong by 15 % and more at the
50 % response point and reversed two rankings.

---

## 1. Two questions, and two rulings

**Scene information and grain structure are separate questions.** The MTF
chart and the granularity figure are measured by different instruments on
different targets, and they rank the stocks differently. Ektar 100 ranks finer
than Portra 160 on grain (Print Grain Index 38 against 50 at 8 x 10 in from
135) and softer on the green-record MTF50 (53.0 against 65.9 cycles/mm).
Portra 800 ranks coarsest on grain among the Portras and sharpest on the
blue-record MTF50. One figure cannot carry both properties, so the sampling
scenarios for scene information (§4, §5) and the treatment of grain (§6) are
derived separately and stated separately.

**The 1000:1 resolving power is excluded from the argument, as a declared
scope choice.** ISO 6328 defines contrast ratio as the ratio of bar to
surround luminance, "or the antilog of the density difference", so a 1000:1
target is 3.0 D of contrast, ten stops, and resolving it needs only a few
percent of modulation. Excluding that target limits every claim below to
detail of moderate contrast; nothing here claims to preserve everything the
film recorded at the highest contrasts. The 1.6:1 figure (0.2 D) is retained
as contextual evidence in §2.4 and is not promoted to a threshold.

---

## 2. What the sheets publish, and what each quantity means

### 2.1 Inventory

| Sheet | MTF chart | Grain figure | Resolving power, 1.6:1 / 1000:1 (lines/mm) |
|---|---|---|---|
| Portra 160, 400, 800, Ektar 100 (Kodak, 2025) | three labelled records, vector | Print Grain Index only | none |
| Gold 200, Ultramax 400, Pro Image 100 (Kodak) | none | Print Grain Index only | none |
| Fujifilm 200, 400 (2023) | none | none | none |
| Pro 400H, Fujicolor 100, Superia Premium 400, Superia X-Tra 400 (Fujifilm) | one unlabelled curve, vector | RMS granularity 4 (Fuji scale, stated non-comparable with reversal) | 50 / 125 (Fujicolor 100: 63 / 125) |
| Vision3 50D, 200T, 250D, 500T (Kodak) | three labelled records, bitmap | RMS granularity curves against density | none |
| Ektachrome E100 (Kodak Alaris) | three labelled records, vector | RMS 8 | none |
| Velvia 100 (Fujifilm) | one curve, vector | RMS 8 | 80 / 160 |
| Velvia 50 (Fujifilm) | one curve, bitmap | RMS 9 | 80 / 160 |
| Provia 100F (Fujifilm) | one curve, bitmap | RMS 8 | 60 / 140 |

Kodak's current still-film sheets carry no resolving-power figure, so the
practitioner claim that one C-41 stock "resolves the most" is not sourceable
from the sheets, and §3 shows that the MTF charts do not support a single
winner either.

### 2.2 The MTF chart (tier A, method from H-845 and the ANSI catalogue)

Kodak states that its MTF values are "determined using a method similar to
that of ANSI Standard PH2.39-1977": a sinusoidal target of nominally 60 %
aerial-image modulation, read by microdensitometer. The standard's own caveat,
repeated by Kodak, is that photographic MTF values "are influenced by
development-adjacency effects and are not equivalent to the true optical
modulation-transfer curve of the emulsion layer". Response above 100 % on the
charts is that adjacency effect.

The Vision3 charts state Status M densitometry and the exposure illuminant; the
still-film charts state exposure and process only; no sheet in hand states the
density at which its MTF was measured. The Fujifilm sheets plot one curve and
do not say which record or weighting it represents.

### 2.3 The grain figures (tier A and B)

**Diffuse RMS granularity** is the standard deviation of density read through a
48 µm aperture at a net diffuse density of 1.0 above base, times 1000 (H-845).
Kodak E-58 adds that the 48 µm aperture "corresponds to about a 12X
magnification". It is an amplitude through one aperture and carries no
bandwidth.

**Print Grain Index** (Kodak E-58) is derived in three steps: red, green and
blue negative granularity are carried through a standard paper, printer MTF and
magnification into print granularity; the three are combined into one visual
granularity "based on the spectral characteristics of the print material image
dyes and the spectral luminous efficiency curve for the human visual system";
and the result is mapped to a perceptual scale where two units are a 50 % JND,
four units a 90 % JND, and 25 the visual threshold. It is a luminance-weighted,
magnification-keyed noise figure, and the sheet is right that it cannot be
converted back to RMS granularity: the mathematics are not published.

**Dye-cloud size** is not published on any sheet. The 1996 *J. Photogr. Sci.*
paper derives it jointly from MTF and noise power spectrum (abstract only).
Weaver and Long measure 1.25 to 4 µm in Kodak papers, yellow largest, and give
no negative-film sizes. Andrews estimates by microscope dye speckle under 3 µm
clustering to 6 to 9 µm at ISO 100 to 200 (tier C). No credible measured
dye-cloud size for a current colour negative was found.

### 2.4 Resolving power against MTF (tier A cross-check, descriptive only)

For each Fujifilm sheet the published 1.6:1 resolving power is placed on its
traced MTF. The input Michelson modulation of a 1.6:1 target is 0.23; the last
column is the arithmetic product 0.23 x MTF and is illustrative, since the
resolving target contains bars while MTF describes sinusoidal response, and no
sensitometric conversion or noise model is applied.

| Sheet | 1.6:1 lines/mm | 1000:1 lines/mm | MTF at the 1.6:1 figure | 0.23 x MTF |
|---|---|---|---|---|
| Pro 400H | 50 | 125 | 53 % | 0.121 |
| Fujicolor 100 | 63 | 125 | 47 % | 0.108 |
| Superia Premium 400 | 50 | 125 | 58 % | 0.133 |
| Superia X-Tra 400 | 50 | 125 | 58 % | 0.133 |
| Velvia 100 | 80 | 160 | 31 % | 0.072 |
| Velvia 50 | 80 | 160 | beyond chart (33 % at 63) | below 0.076 |
| Provia 100F | 60 | 140 | 26 % | 0.060 |

The products span a factor of two and cannot establish a common detection
threshold; an earlier draft of this analysis derived a 30 % comparison level
from them and the derivation was rejected on review. What the table does show
is that the 1000:1 figures of 125 to 160 lines/mm lie well beyond every chart
end, so film response exists past the chart at low modulation.

### 2.5 Subjective quality factor and information capacity (tier B and A)

Granger and Cupery's SQF integrates MTF against the eye's contrast sensitivity
over roughly 3 to 12 cycles per degree, validated against observer ratings of
prints; a difference of 5 is about one JND. At 34 cm viewing that band is 0.5
to 2 cycles/mm on the print, hence 0.5 to 2 times the magnification on the
negative: 4 to 18 cycles/mm for an 8 x 10 in print from 135.

Jones (1961) computes film information capacity from the sine-wave response
and the Wiener spectrum of granularity; it is the principled fusion of
sharpness and grain and needs the noise spectrum, which no sheet in hand
publishes.

---

## 3. The traced MTF data

### 3.1 Method

The chart is log-log. Each axis is modelled as log10(value) = a x device + b,
seeded from the frame edges and the printed end values, then refitted by least
squares over the drawn gridlines with each gridline assigned its nearest
decade value. The worst gridline residual is the recorded test that the scale
is logarithmic: 0.001 decade on the Kodak vector sheets, 0.008 on the Fujifilm
vector sheets, 0.01 on the bitmaps.

Vector curves are cubic Béziers evaluated at 25 points per segment; bitmap
curves are marched column by column from the labelled end with dead reckoning
through crossings. Every traced curve is replotted onto a 300 dpi render and
scored for ink hit (1.000 on all vector sheets, 0.956 to 1.000 on bitmaps).
Each file carries a `digitization_audit` block with the axis fits, gridline
residuals, label checks and record pairing, and its arrays hold the trace on a
grid of 24 points per decade plus the two traced endpoints.

Three facts found by the tracing are recorded in the files: Velvia 50 prints
its 30 % gridline about 0.04 decade low and that gridline is excluded from the
fit; the three Vision3 50D records cross inside one line width around their
50 % point, so the file carries a `crossing_bracket` of 35.3 to 39.3 cycles/mm
for every record; Velvia 100 and Pro 400H carry no axis numerals extractable
as text.

### 3.2 Per-stock figures (cycles/mm, *computed here* from the `summary` block of each file)

MTF50 and MTF30 are the frequencies at which a traced record falls to 50 and
30 % response. "beyond" means the record is still above that level where the
manufacturer stops plotting; nothing is extrapolated. Records are given in the
order blue, green, red; the Fujifilm sheets carry one unlabelled curve. Peak
responses, MTF20 values and the response at every decade frequency are in the
files.

| Stock | Family | MTF50 B | MTF50 G | MTF50 R | MTF30 B | MTF30 G | MTF30 R | Chart end | End response B / G / R |
|---|---|---|---|---|---|---|---|---|---|
| Portra 160 | C-41 | 56.7 | 65.9 | 35.0 | beyond | beyond | 51.2 | 80 | 36 / 40 / 16 % |
| Portra 400 | C-41 | 72.4 | 60.5 | 39.6 | beyond | beyond | 58.9 | 80 | 46 / 39 / 21 % |
| Portra 800 | C-41 | 73.0 | 54.8 | 33.9 | beyond | beyond | 50.4 | 80 | 47 / 34 / 14 % |
| Ektar 100 | C-41 | 55.2 | 53.0 | 35.6 | beyond | 74.8 | 49.3 | 80 | 39 / 27 / 15 % |
| Vision3 50D | ECN-2 | 35.3 to 39.3 (bracket, all records) | | | 60.9 | 60.9 | 50.8 | 80 | 23 / 18 / 11 % |
| Vision3 200T | ECN-2 | 64.3 | 54.4 | 37.5 | beyond | beyond | 54.4 | 80 | 39 / 37 / 19 % |
| Vision3 250D | ECN-2 | 61.4 | 50.9 | 33.5 | beyond | beyond | 50.4 | 75 | 40 / 38 / 18 % |
| Vision3 500T | ECN-2 | 33.8 | 51.5 | 58.9 | 52.9 | beyond | beyond | 77 | 17 / 31 / 40 % |
| Ektachrome E100 | E-6 | 45.5 | 37.7 | 28.6 | 77.5 | 60.4 | 41.5 | 82 | 28 / 18 / 8 % |

**Two sheet types, kept apart.** The Fujifilm sheets publish one unlabelled
curve and do not state which record it is, whether it is a weighted
combination, or the measurement density (§2.2). A figure read from it is
therefore a different quantity from a figure read from three labelled records,
and every table below places the Fujifilm sheets in their own group. Within
the Fujifilm group the figures are comparable with one another under the
assumption that Fujifilm plots the same quantity on every sheet, which no
sheet confirms. Across the two groups a figure is a comparison of two
different published quantities, and no ranking in this note crosses that
boundary.

| Stock (one curve) | Family | MTF50 | MTF30 | Chart end | End response |
|---|---|---|---|---|---|
| Pro 400H | C-41 | 53.0 | 84.9 | 105 | 22 % |
| Fujicolor 100 | C-41 | 59.4 | 87.3 | 105 | 22 % |
| Superia Premium 400 | C-41 | 59.0 | 87.8 | 104 | 23 % |
| Superia X-Tra 400 | C-41 | 58.9 | 87.8 | 104 | 23 % |
| Velvia 100 | E-6 | 44.9 | 83.4 | 100 | 26 % |
| Velvia 50 | E-6 | 46.4 | beyond | 63 | 33 % |
| Provia 100F | E-6 | 40.0 | 54.6 | 62 | 26 % |

Three observations follow.

- On every three-record sheet with a resolved order, Vision3 500T excepted,
  the red record is the softest, by 15 to 39 cycles/mm at MTF50 against the
  sharpest record; on 500T the blue record is softest, and on Vision3 50D the
  order is unresolved within the bracket.
- Portra 400 and Portra 800 lead the C-41 group on blue MTF50 and Portra 160
  leads on green; §4 gives the weighted figure.
- The Kodak charts stop between 75 and 82 cycles/mm; on the Portra, Ektar and
  the three faster Vision3 sheets the sharpest records are still at 34 to 47 %
  there, so their MTF30 lies beyond the measured support, while on Vision3 50D
  and Ektachrome E100 every record has fallen below 30 % inside the chart.

---

## 4. Reading one figure from three records

A three-record chart yields three MTF50 values and a choice of which to quote.
The choice that matches print practice combines the *curves* with luminance
weights and reads the figure from the combined curve; Kodak E-58 combines the
three granularities the same way through the luminous-efficiency curve, and
digital practice derives a system luminance MTF as a weighted sum of per-plane
curves (Strolls with my Dog). Averaging the three MTF50 values is a different
quantity and is not used.

The weights used here are the Rec. 709 luma coefficients, green 0.7152, red
0.2126, blue 0.0722, applied to the traced response curves on a common
log-frequency grid. They are an illustrative metric: film records are dye
densities and not display RGB, and a print-engine model would carry record
gains, a defined stimulus and the operating tone scale. A weight set derived
through the print engine remains an open item (§9).

*Computed here*, by the expression in §5.4, with the Vision3 50D bracket
carried through. Print Grain Index at 8 x 10 in from 135 is placed beside the
weighted figure to show the two properties side by side; the Fujifilm sheets
give an RMS scalar only.

Kodak sheets, three records combined:

| Stock | Family | Luminance MTF50 | Luminance MTF30 | Softest record MTF50 | Print Grain Index, 8 x 10 in |
|---|---|---|---|---|---|
| Portra 160 | C-41 | 58.6 | beyond | 35.0 | 50 |
| Portra 400 | C-41 | 56.1 | beyond | 39.6 | 59 |
| Portra 800 | C-41 | 51.7 | beyond | 33.9 | 70 |
| Ektar 100 | C-41 | 48.4 | 71.3 | 35.6 | 38 |
| Vision3 200T | ECN-2 | 51.5 | beyond | 37.5 | RMS curves |
| Vision3 250D | ECN-2 | 47.5 | beyond | 33.5 | RMS curves |
| Vision3 500T | ECN-2 | 52.0 | beyond | 33.8 | RMS curves |
| Vision3 50D | ECN-2 | 35.3 to 39.3 (bracket) | 58.8 | unresolved within bracket | RMS curves |
| Ektachrome E100 | E-6 | 35.8 | 56.9 | 28.6 | RMS 8 |

Fujifilm sheets, the single published curve read as is (§3.2 precaution; the
"luminance" label does not apply, since no weighting was performed):

| Stock | Family | MTF50 of the published curve | MTF30 | RMS granularity |
|---|---|---|---|---|
| Fujicolor 100 | C-41 | 59.4 | 87.3 | 4 |
| Superia Premium 400, X-Tra 400 | C-41 | 58.9 | 87.8 | 4 |
| Pro 400H | C-41 | 53.0 | 84.9 | 4 |
| Velvia 100 | E-6 | 44.9 | 83.4 | 8 |
| Velvia 50 | E-6 | 46.0 | beyond | 9 |
| Provia 100F | E-6 | 40.0 | 55.3 | 8 |

On the luminance curve Portra 160 leads the Kodak C-41 group, Portra 400 is
within 3 cycles/mm of it, and Portra 800 trails by 7; the Fujifilm C-41
figures of 53 to 59 are not placed in that ranking, since the quantity behind
them is unstated; the blue-record lead of Portra 400 and 800 enters the
weighted figure at 7 % and the weighted order is what the metric reports. The
ranking is of this metric, and no sheet can turn it into a ranking of
scene-information capacity without a noise spectrum.

**Why a stock that leads on MTF50 can look softer in use.** Two published
quantities bear on perceived print sharpness and both are carried here. The
SQF band for an 8 x 10 in print from 135 is 4 to 18 cycles/mm on the negative
(§2.5); across the sixteen sheets the stored record responses in that band
run from 70 % (Ektachrome E100 red) to 121 % (Portra 800 green, Velvia 50),
*computed here* as the minimum and maximum of each stored curve between 4 and
18 cycles/mm, and a spread of responses above and below 100 % is a statement
about the curves and demonstrates nothing about perceptual equivalence.

Grain differs a great deal: Print Grain Index at 8 x 10 in runs 38 for Ektar
100, 50 for Portra 160, 59 for Portra 400 and 70 for Portra 800, differences
of many 90 % JNDs. Portra 800's sharp blue record at 73 cycles/mm is real,
carries a small weight in the luminance metric, and lies above the SQF band
of that print.

These two facts are consistent with the practitioner observation that Portra
800 looks softer in use; they do not completely explain perceived sharpness,
which also depends on viewing conditions, colour of the detail and the whole
imaging chain. A screen view at 100 % specifies neither a physical
magnification nor a viewing distance, so no statement is made about which
metric decides there.

---

## 5. Sampling scenarios per stock

### 5.1 The optical framing

The figures below fix the scanning lens as lossless. The capture chain then
holds two known functions besides the film: the pixel aperture, a sinc that
passes 0.637 at the Nyquist frequency for a square pixel of 100 % fill, and
the sampling itself. The framing removes the scanner's own MTF from the
calculation so that the sheets can be read on their own; it does not make the
figures a ceiling on useful sampling, since denser sampling with the same lens
still raises the pixel-aperture response at a given frequency, reduces
aliasing and improves a filtered reduction to a smaller delivered file.

The aperture term is sensor-specific: slanted-edge measurements on a Nikon Z7
put its first null at 1.12 cycles per pixel, an effective aperture of 0.79 of
the pixel area and 0.70 response at Nyquist, with the author's test set ranging
from 65 to 80 % (Strolls with my Dog, 2020). The tables give the 100 % fill
value and, where it matters, the Z7 value beside it.

**Film MTF comparison level.** For a declared level X, the scenario sampling
density is 2 f_X, where f_X is the frequency at which the luminance curve (§4)
falls to X %. This places the chosen film-response frequency at Nyquist. It is
a comparison level on the film curve alone: under the 100 % fill pixel model
the combined presampling response at that frequency is 0.318 for X = 50 and
0.191 for X = 30, and the sampled contrast of a sinusoid at Nyquist itself
depends on its phase. X is declared and carried in the table; it is not
derived from the sheets, and the earlier attempt to derive a 30 % level from
the resolving-power cross-check was rejected on review (§2.4). Where the
luminance curve is still above X at the chart end, the scenario is marked
"beyond"; the chart-end column places the last traced frequency at Nyquist and
bounds knowledge of the film curve and leaves the useful sensor resolution
open.

**Pixel accounting.** All densities are in full-RGB samples: a pixel-shift
sequence that samples every colour at native pitch counts at native pitch; a
Bayer 2 x 2 superpixel yields one full-RGB sample per four sensor pixels; and
ordinary demosaicing has no universal effective-resolution factor and is
assessed per pipeline. Linear density in samples/mm is ppi divided by 25.4;
the count for a 24 x 36 mm frame is 864 times the square of the linear
density. Capture sampling and delivered file resolution are reported
separately, since oversampled capture followed by filtered reduction improves
a smaller delivered file.

### 5.2 Scenario densities (*computed here*, §5.4)

Sampling density in ppi at which the film MTF comparison level X sits at
Nyquist. "beyond" means the luminance curve is still above X at the chart end.

The Fujifilm rows are read from the single published curve and stand in
their own tables (§3.2 precaution); a Fujifilm ppi figure is a scenario for a
curve of unstated meaning and is not compared with a Kodak row.

Kodak sheets, luminance curve:

| Stock | X = 50 % | X = 30 % | X = 20 % | Chart end at Nyquist |
|---|---|---|---|---|
| Portra 160 | 2975 | beyond | beyond | 4065 |
| Portra 400 | 2852 | beyond | beyond | 4069 |
| Portra 800 | 2628 | beyond | beyond | 4062 |
| Ektar 100 | 2460 | 3621 | beyond | 4069 |
| Vision3 50D | 1793 to 1996 (bracket) | 2986 | 3660 | 4068 |
| Vision3 200T | 2617 | beyond | beyond | 4047 |
| Vision3 250D | 2414 | beyond | beyond | 3810 |
| Vision3 500T | 2644 | beyond | beyond | 3925 |
| Ektachrome E100 | 1819 | 2888 | 3736 | 4143 |

Fujifilm sheets, single published curve:

| Stock | X = 50 % | X = 30 % | X = 20 % | Chart end at Nyquist |
|---|---|---|---|---|
| Pro 400H | 2691 | 4312 | beyond | 5356 |
| Fujicolor 100 | 3017 | 4434 | beyond | 5314 |
| Superia Premium 400, X-Tra 400 | 2991 | 4459 | beyond | 5261 |
| Velvia 100 | 2281 | 4238 | beyond | 5058 |
| Velvia 50 | 2337 | beyond | beyond | 3186 |
| Provia 100F | 2031 | 2808 | beyond | 3126 |

The same scenarios as full-RGB megapixels per 135 frame. Kodak sheets:

| Stock | X = 50 % | X = 30 % | X = 20 % | Chart end at Nyquist |
|---|---|---|---|---|
| Portra 160 | 12 | beyond | beyond | 22 |
| Portra 400 | 11 | beyond | beyond | 22 |
| Portra 800 | 9 | beyond | beyond | 22 |
| Ektar 100 | 8 | 18 | beyond | 22 |
| Vision3 50D | 4.3 to 5.3 (bracket) | 12 | 18 | 22 |
| Vision3 200T | 9 | beyond | beyond | 22 |
| Vision3 250D | 8 | beyond | beyond | 19 |
| Vision3 500T | 9 | beyond | beyond | 21 |
| Ektachrome E100 | 4 | 11 | 19 | 23 |

Fujifilm sheets:

| Stock | X = 50 % | X = 30 % | X = 20 % | Chart end at Nyquist |
|---|---|---|---|---|
| Pro 400H | 10 | 25 | beyond | 38 |
| Fujicolor 100 | 12 | 26 | beyond | 38 |
| Superia Premium 400, X-Tra 400 | 12 | 27 | beyond | 37 |
| Velvia 100 | 7 | 24 | beyond | 34 |
| Velvia 50 | 7 | beyond | beyond | 14 |
| Provia 100F | 6 | 11 | beyond | 13 |

**Reading the tables.** The 50 % column is the density at which the film's
MTF50 sits at Nyquist; it corresponds to the practitioner figure of 2500 to
3000 ppi for the C-41 stocks and is numerically consistent with it.
It is also the lowest level in the table, and at it the band between MTF50 and
the chart end, in which the Portra and faster Vision3 stocks still hold 34 to
47 % response, lies above Nyquist. The chart-end column is the highest
frequency the sheets can speak to; it bounds what is known of the film curve
and says nothing about what the film holds beyond it, where the 1000:1
resolving powers show that response continues. The scenarios per group are:

| Group | Sheet type | X = 50 %, ppi | X = 50 %, MP | Chart end, ppi | Chart end, MP |
|---|---|---|---|---|---|
| C-41, Kodak professional | three records | 2460 to 2975 | 8 to 12 | 4060 to 4070 | 22 |
| ECN-2, Kodak Vision3 | three records | 1793 to 2645 | 4.3 to 9 | 3810 to 4070 | 19 to 22 |
| E-6, Kodak Ektachrome E100 | three records | 1819 | 4 | 4143 | 23 |
| C-41, Fujifilm | one curve | 2690 to 3020 | 10 to 12 | 5260 to 5360 | 37 to 38 |
| E-6, Fujifilm | one curve | 2030 to 2340 | 6 to 7 | 3130 to 5060 | 13 to 34 |

The Fujifilm E-6 spread in the chart-end columns is a spread of chart extents,
62 cycles/mm for the Velvia 50 and Provia bitmaps against 100 for Velvia 100,
and says nothing about the films. The two E-6 rows are of different sheet
types and are not compared.

### 5.3 The inverse: film-plus-aperture response at a sensor's Nyquist frequency (*computed here*, §5.4)

For a sensor of N full-RGB samples per frame the Nyquist frequency is
f_N = sqrt(N / 864) / 2 cycles/mm: 59 cycles/mm at 12 megapixels and 83 at 24.
The table gives the film luminance MTF at f_N and its product with the pixel
aperture, for the 100 % fill value and for the Z7 value of 0.70. These are
model outputs describing how much scene modulation the film-plus-sensor chain
passes at that one frequency under a lossless lens.

They do not measure aliasing: the film's scene MTF describes how the scene is
attenuated before grain forms and does not describe how the scanner filters
grain, and the amount of aliasing depends on the response and the signal and
noise spectra above Nyquist, which no sheet gives. FADGI lists response at
Nyquist as an informative scanner metric (section 2.4.8) outside its compliance
criteria, and its values apply to the scanner measured alone. From 24 megapixels
the Nyquist frequency lies beyond every Kodak chart, and from 45 megapixels
beyond every chart in hand, so those cells are empty by the rule that nothing
is extrapolated.

Kodak sheets, luminance curve:

| Stock | Film MTF at f_N, 12 MP | x 0.637 | x 0.70 | Film MTF at f_N, 24 MP | x 0.637 |
|---|---|---|---|---|---|
| Portra 160 | 0.50 | 0.32 | 0.35 | beyond chart | |
| Portra 400 | 0.48 | 0.30 | 0.33 | beyond chart | |
| Portra 800 | 0.42 | 0.27 | 0.29 | beyond chart | |
| Ektar 100 | 0.40 | 0.25 | 0.28 | beyond chart | |
| Vision3 50D | 0.30 | 0.19 | 0.21 | beyond chart | |
| Vision3 200T | 0.44 | 0.28 | 0.31 | beyond chart | |
| Vision3 250D | 0.42 | 0.27 | 0.29 | beyond chart | |
| Vision3 500T | 0.44 | 0.28 | 0.31 | beyond chart | |
| Ektachrome E100 | 0.29 | 0.18 | 0.20 | beyond chart | |

Fujifilm sheets, single published curve (§3.2 precaution):

| Stock | Film MTF at f_N, 12 MP | x 0.637 | x 0.70 | Film MTF at f_N, 24 MP | x 0.637 |
|---|---|---|---|---|---|
| Pro 400H | 0.45 | 0.29 | 0.32 | 0.31 | 0.20 |
| Fujicolor 100 | 0.50 | 0.32 | 0.35 | 0.32 | 0.21 |
| Superia Premium 400, X-Tra 400 | 0.50 | 0.32 | 0.35 | 0.33 | 0.21 |
| Velvia 100 | 0.40 | 0.26 | 0.28 | 0.30 | 0.19 |
| Velvia 50 | 0.36 | 0.23 | 0.25 | beyond chart | |
| Provia 100F | 0.27 | 0.17 | 0.19 | beyond chart | |

At 12 megapixels the Kodak C-41 stocks pass 0.25 to 0.32 of scene modulation
at Nyquist under the 100 % fill model, the faster Vision3 stocks 0.27 to 0.28,
and Ektachrome E100 and Vision3 50D 0.18 to 0.19; the Fujifilm single curves
give 0.29 to 0.32 for the C-41 sheets and 0.17 to 0.26 for the reversal
sheets.

Whether a 45 or 100 megapixel capture passes more or less at its own Nyquist
frequency cannot be read from any sheet. Assessing the scanner's own response,
and any aliasing, is a separate measurement (§7).

### 5.4 Reproduction

Every figure in §4 and §5 is produced by one script over the sixteen files:
the luminance curve is the Rec. 709 weighted sum of the three records
interpolated in log frequency onto the union of their grids inside the common
support, or the single Fuji curve; f_X is found by log-log interpolation
between the bracketing samples; the chart end is the last stored sample, which
is the traced curve end; the inverse table interpolates the luminance curve at
f_N and multiplies by sinc(1/2) = 0.637 or by 0.70. The Vision3 50D MTF50 is
taken from the file's `crossing_bracket` and both ends are carried: 2 f gives
70.6 to 78.6 samples/mm, 1793 to 1996 ppi, 4.31 to 5.34 megapixels.

The calculation is the scenario-report mode of the film MTF digitiser
(unpublished), which prints the rows of these tables from the sixteen files;
the expressions above suffice to recompute any entry without it. The report
prints the Kodak three-record sheets first and the Fujifilm single-curve
sheets after a divider, in the order of the tables.

---

## 6. Grain structure: what the sheets allow, and what they do not

**No anti-aliasing rule is prescribed from the sheets.** Print Grain Index and
aperture-filtered RMS granularity describe grain amplitude or visibility; they
carry no spatial bandwidth and cannot set a sampling density. Dye-cloud size
alone cannot either, since cluster size and cloud profile, and not particle
size, set the spectrum (Andrews; the 1996 dye-cloud paper). An earlier draft
placed the lens diffraction cutoff near Nyquist as an anti-aliasing rule and
it was withdrawn on review: an ideal lens with its cutoff at Nyquist passes
only 0.219 at two thirds of Nyquist, 0.181 with the pixel aperture, so the
rule buys aliasing suppression with most of the film's high-frequency
contrast.

**What the literature establishes, with its film types and ranges.**

- Trinder measured Wiener spectra of black-and-white aerial films and found
  them flat below about 100 lines/mm. Triantaphillidou used Kodak T-Max P3200,
  a black-and-white stock, as a white-noise source on the assumption of a flat
  noise power spectrum to 40 to 50 cycles/mm. Both are silver-image films; the
  colour stocks here form their image from dye clouds, and no measured noise
  spectrum for any of them was found. Nothing in these two measurements
  establishes where the grain power of a colour negative lies relative to the
  Nyquist frequencies of §5.2, several of which are above 50 cycles/mm.
- Grain aliasing occurs where the scanner still responds between the Nyquist
  frequency and two to three times it (Koren; Andrews), and Andrews found it
  most visible in low-contrast areas at a 9.4 µm pitch, 2700 ppi. Drum scans
  of Velvia keep gaining detail to at least 6000 ppi, with 4000 ppi "close but
  not all" (Clark, measured on 35 mm).
- FADGI's SFR50 and SFR10 criteria, and its informative response-at-Nyquist
  metric, are the acceptance vocabulary for the scanner measured alone; the
  film-side tolerance remains to be stated.

**Grain ranking.** Within C-41 the Print Grain Index orders the stocks in hand
at 8 x 10 in from 135: Ektar 100 at 38, Portra 160 at 50, Portra 400 at 59,
Gold 200 at 64, Pro Image 100 at 65, Portra 800 at 70 (Gold 200's sheet prints
4.4x for both its columns; Ultramax 400 is given at 4 x 6 in only, 46). Within
E-6 the RMS scalars are 8 for E100, Velvia 100 and Provia 100F and 9 for
Velvia 50. The Vision3 RMS curves have not been traced; readings by eye near
D 1.0 are 0.004 to 0.005 for 50D and up to 0.02 for 500T blue and are quoted
as such.

The finest-grained candidate per group is therefore Ektar 100 (C-41),
Vision3 50D (ECN-2, by eye) and the three RMS-8 reversal stocks tied (E-6).
Stock-specific noise spectra remain necessary before any sampling density can
be tied to grain.

---

## 7. Toward a required resolution: the measurement protocol

A required density, one that guarantees a stated loss under stated
conditions, is an experimental result. The datasheet tables of §5 supply the
starting settings for that experiment; they do not supply its answer. The
experiment establishes a result for one stock, process, exposure range,
scanner configuration and acceptance tolerance, and its statement takes the
form given at the end of this section. The calculation is on hold until the
experiment is run.

### 7.1 Two comparisons, kept distinct

Photographing a known target and measuring its scan tests the whole chain:
target, photographing lens, film and processing, scanner, conversion. A weak
result can originate anywhere in that chain, so the target alone cannot
attribute a loss to the scanner. Two comparisons are therefore made and kept
apart.

- **Target against scene.** The known target identifies real scene detail and
  shows what the film and its exposure recorded.
- **Candidate against reference, same frame.** Each candidate scan is compared
  with a demonstrably better capture of the same developed frame. This
  comparison measures the loss the scan adds to what the film already lost,
  which is the quantity a required density is about.

### 7.2 Reference adequacy

The highest-density scan is a reference only once it is shown to be adequate.
It can itself be limited by focus, optics, sampling or noise. Adequacy is
tested by raising the actual optical sampling and checking whether the target
response and the grain rendition change by more than the measurement
uncertainty. The scanner's own response is verified over the frequencies
being assessed, by the slanted-edge method of ISO 12233 as applied to film
scanners in ISO 16067-2 (Williams and Burns; FADGI metrics), per channel and
field position, at each candidate density. Where the reference remains
unresolved, the candidate result is reported as inconclusive.

The same developed frame serves every candidate-against-reference comparison,
since its grain is fixed and repeated scans of it isolate the scanner.
Independently exposed frames estimate film variability and show whether a
result generalises beyond one frame.

### 7.3 Fixed film frequencies

The inverse table of §5.3 evaluates each sensor at its own Nyquist frequency,
so its columns assess different detail sizes. The experiment compares
captures at the same frequencies in cycles/mm on the film. For a target
pattern at frequency f,

```text
R(f) = recovered target amplitude in the candidate scan
       / recovered target amplitude in the reference scan
```

computed after consistent tonal calibration, in the same signal domain, and
only where the reference amplitude is reliably measurable. Several
frequencies, contrasts and orientations are assessed. A value near one is
desirable; sharpening and aliases can inflate amplitude, so artifacts are
assessed alongside it.

### 7.4 Joint acceptance criteria

A single criterion is insufficient: retained modulation alone admits an
aliased scan, and absence of visible aliasing alone admits an excessively
blurred one. Every applicable criterion passes together.

| Requirement | What it prevents |
|---|---|
| Target-detail retention within tolerance at the fixed frequencies | Losing recorded detail |
| Aliasing and false colour within tolerance | Inventing or misplacing detail |
| Added scanner noise within tolerance | Preserving contrast while obscuring the signal |

Uniform patches measure grain and scanner noise; their appearance alone
cannot establish faithful grain reproduction, so their spatial statistics and
same-frame rendition are compared with the reference. Known fine patterns
expose aliases.

The tolerances are defined before any candidate is judged, and each states
whether it applies to preservation of colour detail or to a specified print or
display result. No source supplies them; they are a decision (§9).

### 7.5 Capture density and delivered resolution

Two experiments answer two questions.

- Actual captures at different optical sampling densities determine what the
  scanner set-up must capture.
- Filtered reductions of the reference determine how small the delivered
  file can be for the intended use.

A digitally reduced reference does not reproduce the aliasing, optical
response or noise of a genuinely lower-density capture, so it cannot stand
in for the first experiment. For camera scanning, a change of magnification
changes the optical conditions too; each configuration is recorded and
characterised, and results are compared at explicitly defined output sizes
with consistent processing.

### 7.6 Colour and processing conditions

The weighted MTF curves of §4 help select test settings; they are not the
sole acceptance metric when the objective includes colour detail. Neutral and
coloured patterns are both tested, and colour errors are assessed alongside
luminance response. Scanner RGB channels are mixtures of the film-dye
responses and are not direct measurements of the manufacturer's individual
records.

Measurement uses a controlled baseline conversion with consistent tonal
handling and no adaptive sharpening or noise reduction. The intended
production conversion is evaluated separately, since processing changes
measured response and apparent information recovery. Imatest's guidance on
information-capacity measurement makes the same separation between minimally
processed measurements and tests that expose processing artifacts; the design
here is this project's proposal and Imatest specifies no film-scanning
protocol.

### 7.7 Stopping rule and reporting

"No further improvement" means no improvement larger than the declared
tolerance plus the measurement uncertainty. Captures are repeated, and
independently exposed frames are included, so that the uncertainty is
estimated. If the uncertainty is large enough to hide the allowed loss, the
result is inconclusive. The report gives the lowest tested density that
passes, the adjacent failing density where available, and the conditions
covered.

A stock-specific noise power spectrum is necessary for Jones's
information-capacity calculation (§2.5). It is not a prerequisite for this
empirical test: practical detail loss and grain artifacts are measured
directly.

### 7.8 Cost and pilot

The scanner response and the reference-adequacy check are one-time work on
the scanner in hand; the target series costs a roll per stock. A roll of
Portra 160 provides a pilot for that stock and tests the protocol; it cannot
establish requirements for other C-41 stocks. The experiment ultimately
supports a statement of this form:

> For this stock, process, exposure range and scanning configuration, this
> capture density meets the stated detail, artifact and noise tolerances at
> the specified delivered resolution.

---

## 8. Summary of the position

- Two concepts, two figures: scene information from the MTF, grain from the
  granularity figures; no single number carries both.
- The 1000:1 resolving power is excluded as a declared scope choice; the 1.6:1
  figure is context.
- Sixteen MTF charts are traced with a recorded log-log audit; every figure
  here is read from the files.
- The comparison figure is the MTF50 of the luminance-weighted curve. On it
  Portra 160 leads the Kodak C-41 group by a small margin; grain differences
  between the Portras are large on the Print Grain Index; neither fact
  completely explains perceived sharpness.
- The tables of §5 guide comparison and testing. Under a lossless lens the
  film's MTF50 sits at Nyquist near 2500 to 3000 ppi (8 to 12 full-RGB MP per
  135 frame) for the C-41 stocks; the sheets' chart ends sit at Nyquist near
  4060 ppi and 22 MP for the Kodak professional C-41 stocks (3810 to 4143 ppi
  and 19 to 23 MP across all Kodak sheets) and 5300 ppi and 38 MP for the
  Fujifilm C-41 sheets (3126 to 5058 ppi and 13 to 34 MP for the Fujifilm
  reversal sheets), beyond which the film curve is unknown.
- Film-plus-aperture response at a 12 MP sensor's Nyquist frequency is 0.25 to
  0.32 for the Kodak C-41 stocks; it is a model output and not a measure of
  aliasing.
- The Fujifilm sheets publish one unlabelled curve, so their figures form a
  separate group in every table and no ranking crosses the Kodak–Fujifilm
  boundary.
- Required scanning resolutions await explicit acceptance criteria and
  same-frame candidate-against-reference measurements of the film and
  scanner under the intended conditions, with joint detail, artifact and
  noise criteria and a stopping rule that includes uncertainty (§7).

---

## 9. Open questions

Sought and not found, or not yet done:

1. **The density at which the sheets' MTF was measured**, and what the single
   Fujifilm curve represents. No sheet states either; manufacturer
   clarification or measurement is needed.
2. **A noise power spectrum for any of these stocks.** Kodak still-film sheets
   carry none; the 1985 *J. Photogr. Sci.* paper on the power spectrum of
   coupler-incorporated colour negative film and the OSTI report on the
   definition and measurement of granularity were not obtained; Dainty and
   Shaw, *Image Science*, chapter 8, is an archive.org borrow. Jones's
   information capacity cannot be computed without it; the empirical test of
   §7 measures grain artifacts directly and does not need it.
3. **A measured dye-cloud size for a current colour negative.** Only paper
   sizes (Weaver and Long) and a tier-C microscope estimate (Andrews) exist.
4. **Record weights derived through the print engine** in place of the
   Rec. 709 coefficients, and MTF across the tone scale.
5. **The Vision3 RMS granularity curves**, untraced; the readings in §6 are by
   eye.
6. **The acceptance tolerances** of §7.4, which no source supplies and
   which are a decision.
7. **ANSI PH2.39 full text**, held at a catalogue summary; **ISO 6328** beyond
   its preview pages; the two *J. Photogr. Sci.* papers beyond their abstracts.
