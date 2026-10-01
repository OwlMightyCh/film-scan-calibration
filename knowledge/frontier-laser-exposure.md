# Laser exposure in the Fujifilm Frontier: which lines are documented, and what the print model takes from them

Collected 2026-09-28. Fujicolor Pro Laser TYPE II is a Frontier minilab
paper. Its datasheet records laser exposure (レーザー露光) for the
characteristic curves, and the print branch exposes it at laser lines
(PROJECT.md, second RA-4 paper, caveat 1). This note records what the
published evidence says about the Frontier's exposing light, and which of
the modelled lines rest on it.

**Headline finding: the Frontier 350 exposes the paper from a digital scan,
with a built-in 473 nm blue and a built-in 532 nm green frequency-doubled
solid-state laser and a red laser diode whose wavelength no source found
here states.** The model selects 685 nm from a patent example as a rendering
choice. Its red-wavelength scenario spans 650–688 nm, drawn from Fujifilm's
patent examples and component lists; this is not a measured uncertainty bound.
The 462 nm and 525 nm figures in circulation come from
aftermarket replacement modules and carry no Fujifilm attribution.

---

## 0. Provenance and confidence

| Tier | Source | Status |
|---|---|---|
| **A, manufacturer conference paper** | H. Nakamura (Fuji Photo Film), "Digital Image Processing for the Frontier350 Digital Minilab", IS&T PICS Conference 1999, p. 96 | Full text read from the PDF text layer; copy in `literature/frontier-laser-exposure/` |
| **A, patent example tables** | US 7,598,026 B2 and its family member US 6,916,601 B2, Fuji Photo Film, priority 2001-12-28, Tables 3 and 10 and the Frontier 350 exposure example | Google Patents OCR text read in full; table rows read as OCR text, page images not compared; copies in `literature/frontier-laser-exposure/` |
| **A, patent examples** | Fuji Photo Film paper patents US 5,705,326 A (priority 1993-05-10), US 6,387,609 B1 (1999-09-29), US 6,632,596 B2 (2000-07-19), US 6,703,194 B2 (2000-12-27), US 6,818,388 B2 (2001-05-23) | Example passages read in the Google Patents OCR text; none names its test apparatus as a Frontier |
| **A, patent source lists** | Fuji Photo Film patents US 7,279,272 B2 (priority 2001-05-23), US 6,780,579 B2 (2002-03-26), US 6,830,880 B2 (2002-06-28) | Lists of usable light sources read in the OCR text; these name components, never a machine |
| **B, manufacturer product pages** | Fujifilm, Frontier LP5700R/5500R specifications and Frontier LP9700 product page (fujifilm.com) | Fetched 2026-09-28; exposure method quoted below; no wavelength published |
| **C, vendor listings** | minilablaser.com, "Laser Module For Fujifilm Frontier" and "Laser Module For Frontier 7XXX Series" | Fetched 2026-09-28; aftermarket replacement parts |
| **traced chart** | `data/papers/FujiProLaserTypeII_paper.json`, spectral-sensitivity peaks | Read from the stored peak fields of the traced Pro Laser TYPE II chart |

---

## 1. What exposes the paper in a Frontier

**The exposure follows a scan.** Nakamura (1999) describes the Frontier 350
as an input scanner, an image processor and a laser printer. A line-type CCD
reads the film in red, green and blue, custom hardware processes the signal
in real time, and "images are output to silver-halide color paper using a
trio of RGB lasers". The same paper states that Fuji Photo Film developed
"solid-state lasers (for blue and green) using its own technologies". The
negative never sits in the paper's light path.

**The built-in blue and green lines are 473 nm and 532 nm.** US 7,598,026 B2
lists its test oscillators in Tables 3 and 10. Two rows carry the entry
"FUJI FILM Frontier Built-in": "Blue SHG 473" and "Green SHG 532". SHG is
second-harmonic generation, the frequency doubling of an infrared solid-state
laser. The same patent states that the Frontier series "uses a semiconductor
laser", and one example remodels the exposure section of a Frontier 350 to
change its wavelengths.

**The red source is a laser diode of unstated wavelength.** No red row in
those tables carries the Frontier entry. The red sources listed there are
third-party diodes: 685 nm (Mitsubishi ML101J10), 658 nm and 650 nm (Hitachi
HL6501-series), 635 nm (Hitachi HL6314MG) and 780 nm (Hitachi HL7859MG).

**Fujifilm's paper patents use these blue and green lines with several reds.** The
blue line is 473 nm, doubled from a 946 nm Nd:YAG laser pumped by an
808.5 nm GaAlAs diode. The green line is 532 nm, doubled from a 1064 nm
YVO<sub>4</sub> laser. The red line is an AlGaInP diode at 680 nm (Matsushita
LN9R20; US 6,387,609 B1, US 6,703,194 B2), 670 nm (US 5,705,326 A,
US 6,632,596 B2) or 688 nm (US 6,818,388 B2). The source lists in the later
patents add a blue diode at 430–460 nm, a 470 nm blue from a doubled 940 nm
diode, a 530 nm green from a doubled 1060 nm diode, and red diodes at 685 nm
(Hitachi HL6738MG) and 650 nm (Hitachi HL6501MG). Those lists name
components a laser printer may use; they do not describe a Frontier.

**The later-machine pages consulted give no wavelengths.** Fujifilm specifies the Frontier
LP5700R/5500R as a "scanning exposure system using RGB lasers" and the
LP9700 as using "direct-modulated semiconductor lasers" for the three
colours.

**The 462 nm and 525 nm figures are aftermarket.** A replacement-parts
vendor lists semiconductor diode modules at 462 nm (blue) and 525 nm (green)
for the Frontier 330/340, 350/370/390, 500 and 550/570/590, and for the
LP7000 to LP7900 series. The listing states no Fujifilm specification.

## 2. Where the documented lines fall on the paper's sensitivity

The traced Pro Laser TYPE II chart peaks at 479 nm (yellow-forming layer),
550 nm (magenta) and 706 nm (cyan). The built-in 473 nm line sits 6 nm below
the yellow peak and the 532 nm line 18 nm below the magenta peak. The red
candidates in the model's 650–688 nm scenario sit 18–56 nm below the cyan peak.
US 7,598,026 B2, Table 4, reports comparable offsets for its own test paper:
its blue sensitivity maximum lies 7 nm above the 473 nm line and its red
maximum 15 nm above the 685 nm line.

The same patent's scanning test used a 600 dpi pitch and an average exposure
time of 1.7×10<sup>-7</sup> s per pixel, on its own test paper. An enlarger
exposes for seconds. No source found here states the exposure time behind the
Pro Laser TYPE II datasheet curves, so the patent figure does not transfer to
them, and the paper's reciprocity between laser and enlarger exposure times
is not measured here.

## 3. Consequences for this repository

PROJECT.md holds the current position (second RA-4 paper, caveat 1).

- The Pro Laser render exposes the paper at 473 nm blue and 532 nm green, the
  two documented built-in lines, and at 685 nm red, the diode US 7,598,026 B2
  pairs with them (Table 10, oscillator I). The 685 nm line is a rendering
  choice selected by visual comparison. The error budget evaluates 650 and
  688 nm red as scenarios with blue and green fixed and zero linewidth. That
  row stays outside the combined totals because it has no measured bound.
- Nakamura (1999) confirms that the Frontier exposes from a scan. A
  laser-line kernel through the negative therefore models an RGB laser
  enlarger, and no documented machine does that. No physical print validates
  either this kernel or the Endura render's tricolor kernel (a nominal 3200 K
  lamp through three filters).
- The relative line powers are calibrated model parameters. They are balanced
  so a neutral negative at k = 0.22 needs no per-layer trim. Paper
  cross-sensitivity makes those powers affect off-neutral colour too; they
  are not measured Frontier powers.
- The shipped comparison is 473/532/685 against the same paper under 3200 K;
  the alternative red rendering uses 473/532/650. PROJECT.md records the cube
  differences. These compare appearances and do not establish printer fidelity.
- All three modelled lines lie inside the negative's measured 400–700 nm
  support. With identical in-band spectra, holding or truncating the unknown
  spectral edges therefore gives the same paper exposure. The missing-band
  term is zero for this kernel.
- The 462/525 pair carries tier C support only and does not enter a
  modelled set.

## 4. Open questions

- **The Frontier's built-in red wavelength.** Not found in any source above.
  A Frontier 350/370 service manual is a possible source; its wavelength
  specifications have not been checked.
- **Which Frontier generation the paper targets.** The Pro Laser TYPE II
  bulletin names the Frontier QL type. Whether that generation keeps the
  473/532 nm SHG lasers or uses direct-modulated diodes is not found.
- **The apparatus of JP-A 11-88619, FIG. 6.** US 6,818,388 B2 exposes its
  examples on it. Whether it is a Frontier is not obtained.
- **Wavelength and linewidth scenarios.** The red endpoints do not cover
  blue/green wavelength uncertainty, finite linewidth, machine generation or
  the difference between a digital printer and the modelled laser enlarger.
- **Reciprocity at laser exposure times.** The exposure time behind the
  datasheet's laser-exposed characteristic curves is not published; the one
  figure found, 1.7×10<sup>-7</sup> s per pixel, belongs to the patent's
  scanning test. How the paper's per-layer speed and contrast change at
  enlarger exposure times is not published for this paper.
