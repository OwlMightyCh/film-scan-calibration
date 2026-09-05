# The Academy Color Encoding System: what it specifies, and where a film scan enters it

Collected 2026-09-03. The ECN-2 route delivers into ADX16 "as an entry into an
ACES timeline", and the camera sensitivity library is imported from the
Academy's `rawtoaces-data`. This note records what ACES itself specifies, from
the standards and Academy documents: the core encoding and its reference
capture device, the working encodings built on the second primary set, the
container, the transform vocabulary, and the places where the system's own
documents say how film gets in. The companion note
`academy-printing-density-and-the-adx-unbuild.md` covers the film path in
detail. This note is the vocabulary and the numbers.

**ACES2065-1 is a scene-referred, linear, half-float encoding on the AP0
primaries with a D60-like white, scaled so that an 18 % reflector under the
design illuminant records 0.18 in every channel. The system's documents treat
a film scan as one more input: printing density is converted to APD and then
"brought into ACES by an appropriate Input Device Transform", and the IDT
procedure written for cameras is silent on scanners.** Every quantity the
project hands to ACES is therefore judged by the ACES definitions in §2 and by
the decode described in the companion note, not by anything the project
chooses.

## 0. Provenance and confidence

| Tier | Source | Status |
|---|---|---|
| **A, verified primary** | SMPTE ST 2065-1:2021, *Academy Color Encoding Specification (ACES)* | Fetched in full from `pub.smpte.org` |
| **A, verified primary** | A.M.P.A.S. S-2008-001 v1.0, *Academy Color Encoding Specification (ACES)*, 12 August 2008 | Fetched in full, as the appendix of TB-2014-004 in `aces-dev` v1.0.3. The original specification; its §5 "Usage" has no counterpart in the SMPTE text |
| **A, verified primary** | A.M.P.A.S. TB-2014-004 (notes on ST 2065-1), TB-2014-001 (documentation guide), TB-2014-002 (user experience guidelines), TB-2014-012 (component names), TB-2014-010 (LMTs), TB-2014-007 (notes on ST 268); S-2013-001 (ACESproxy), S-2014-002 (versioning), S-2014-003 (ACEScc), S-2014-004 (ACEScg), S-2016-001 (ACEScct); P-2013-001 (IDT procedure, marked DRAFT) | LaTeX sources fetched from `aces-dev` at tag v1.0.3 |
| **A, verified primary** | SMPTE ST 2065-4:2023, *ACES Image Container File Layout* | Fetched in full |
| **A, peer-reviewed** | W. Arrighetti, *Journal of Imaging* 3(4):40, 2017, CC BY 4.0 | Fetched in full; an Academy contributor's survey, secondary on the standards |
| **B, secondary** | C. J. Clark, *Investigation of the Academy's Image Interchange Framework at RIT*, 2010 | Fetched; a camera-IDT study on a Panasonic HVX200 |
| **B, secondary** | docs.acescentral.com, "ACES System" and "About ACES 2" pages, version of 10 September 2025 | Fetched. The ACES 2 rendering internals are described there in summary only; the transform code was not read |
| **Not obtained** | SMPTE ST 2065-5 (ACES in MXF), ST 268:2014 (DPX); ISO 22028-1:2016; CIE 015:2018 | Paid standards, cited normatively by the documents above |

One discrepancy in the secondary literature is worth recording. The Academy
documents expand IIF as the Image Interchange Framework (S-2008-001 §3, Clark's
title); Arrighetti writes "initially called IIF (Interoperable Interchange
Format)". The Academy's own expansion is used here.

## 1. History and vocabulary

Arrighetti dates the project: "ACES was born back in 2004 by an effort of the
Academy"; "The ACES project, initially called IIF … was then renamed 'ACES' in
2012"; "The first official version labeled 1.0 was released in December 2014".
The SMPTE ST 2065 family was first issued in 2012 (parts 1 to 3) and 2013
(part 4); the editions read here are 2021, 2020, 2020 and 2023. The docs site
describes ACES 2 as bringing "New Output Transforms for rendering ACES images
to displays", with "A less aggressive tone scale with reduced mid-tone contrast
and a gentler highlight rolloff" and "Robust gamut mapping for improved
perceptual uniformity and reduced clipping artifacts", and lists no change to
the core encoding or to ADX. The ADX-to-ACES transform shipped with ACES 2
carries the same constants as the 1.0.3 file (companion note §5).

The vocabulary, in the pipeline's order, from TB-2014-002's engineering block
diagram and P-2013-001:

- **IDT, Input Device Transform**: "converts non-color-rendered RGB image
  values from a given camera system or other image capture device to ACES RGB
  relative exposure values" (P-2013-001 §1). ACES 2 calls these Input
  Transforms.
- **ACES2065-1**: the "Base encoding, used for exchange of full fidelity
  images, archiving" (TB-2014-012). The docs site: "Linear encoding in a
  wide-gamut RGB color space (AP0); the core interchange encoding in ACES."
- **LMT, Look Modification Transform**: "imparts an image-wide creative 'look'
  to the appearance of ACES images … The inputs to an LMT are ACES RGB relative
  exposure values. The outputs of an LMT are ACES RGB relative exposure
  values" (TB-2014-010). "The internal working space of an LMT is
  unrestricted."
- **RRT, Reference Rendering Transform**: "Converts the scene-referred
  ACES2065-1 colors into colorimetry for an idealized cinema projector with no
  dynamic range or gamut limitations" (TB-2014-002). Its output space is
  **OCES**, the Output Color Encoding Space.
- **ODT, Output Device Transform**: "Takes the output of the RRT and applies
  additional dynamic range compression and gamut adjustment followed by
  encoding of the desired colorimetry for a specific display device
  calibration aim" (TB-2014-002).
- **Output Transform**: "The transform that converts ACES2065-1 colors to code
  values for a particular output device. This is the combination of the RRT
  and an ODT" (TB-2014-002). ACES 2 keeps the umbrella term and splits it into
  a Rendering Transform and a Display Encoding Transform (docs site).

Transform identifiers follow S-2014-002: `Type.a<major>.<minor>.<patch>`, as
in `RRT.a1.0.0` or `IDT.Sony.F65.a1.v1`; ACES 2 identifiers take the form
`urn:ampas:aces:transformId:v2.0:CSC.Academy.ADX16_to_ACES.a2.v1`.

## 2. ST 2065-1: the core encoding

**Chromaticities** (ST 2065-1:2021 §4.2.3–4.2.4, Tables 1 and 2), the AP0
set:

| | x | y |
|---|---|---|
| red | 0.7347 | 0.2653 |
| green | 0.0 | 1.0 |
| blue | 0.0001 | −0.077 |
| white | 0.32168 | 0.33767 |

The white is the chromaticity of "CIE Standard Illuminant D60" in S-2008-001's
usage; "A color encoded in ACES is considered neutral if its RGB values are
equal." The green and blue primaries lie outside the spectrum locus, so the
triangle holds every real colour, and Annex B notes that valid ACES values
"include those with one or more negative ACES color component values".

**The conversion to XYZ** (§4.2.5) is the RP 177 normalised primary matrix of
those chromaticities, given to ten places:

```
NPM = [ 0.9525523959  0.0000000000  0.0000936786 ]
      [ 0.3439664498  0.7281660966 −0.0721325464 ]
      [ 0.0000000000  0.0000000000  1.0088251844 ]
```

**Transfer function and scale.** "The color component transfer function to
encode relative exposure values that would be captured from the scene by the
RICD as ACES color component values shall be linear", R = E_r and so on
(§4.2.7). The image state "shall be scene-referred as defined by ISO 22028-1"
(§4.4.2). The RICD, the Reference Image Capture Device, is a virtual camera
whose spectral sensitivities the 2021 edition moved into a normative Annex A
and "changed from a list of tabulated values to a mathematical formula". Its
scale is fixed by flare and a grey card (Annex A):

> "Calculations using the RICD should introduce camera flare equal to 0.5 % of
> the captured values of a perfect reflecting diffuser. Flare-augmented values
> should then be scaled by the factor S … S = 0.18 / (0.18 + 0.005)."

so S = 0.97297, "chosen such that the RICD capture of an ideal gray card
(defined here as an isotropic, non-fluorescing, spectrally nonselective
reflector with a spectral reflectance equal to 0.18000 at each wavelength of
interest) would produce ACES R, G and B relative exposure values each equal to
0.18000" (S-2008-001 Annex A). A perfect diffuser "produces ACES values of 1.0
(prior to the flare addition and the scaling operation specified in Annex A)".

**Digital encoding** (§4.3.2): "ACES values shall be encoded as 16-bit
floating-point numbers using binary16"; "The valid color component value range
shall be [–65 504.0, +65 504.0]." Negative values are valid.

**Normative references**: CIE 015:2018, IEEE 754-2019, ISO 22028-1:2016,
ISO/CIE 11664-1:2019, SMPTE RP 177:1993. The bibliography cites P-2013-001,
CIE 159:2004 (CIECAM02) and ISO 17321-1.

## 3. AP1 and the working encodings

The second primary set, AP1, is shared by ACEScg, ACEScc, ACEScct and
ACESproxy (S-2013-001 §2.1, S-2014-003, S-2014-004, S-2016-001):

| | x | y |
|---|---|---|
| red | 0.713 | 0.293 |
| green | 0.165 | 0.830 |
| blue | 0.128 | 0.044 |
| white | 0.32168 | 0.33767 |

The AP0-to-AP1 matrix, which the specifications name TRA_1:

```
TRA_1 = [  1.4514393161 −0.2365107469 −0.2149285693 ]
        [ −0.0765537734  1.1762296998 −0.0996759264 ]
        [  0.0083161484 −0.0060324498  0.9977163014 ]
```

- **ACEScg** (S-2014-004): linear on AP1, range [−65504.0, +65504.0], 16- or
  32-bit float, the "Working space for paint/compositor applications that
  don't support ACES2065 or ACEScc" (TB-2014-012). Identical to ACES2065-1
  apart from the primaries.
- **ACEScc** (S-2014-003 §1.1), the grading log, `lin_AP1 → ACEScc`:
  ```
  (log2(2^−16) + 9.72) / 17.52                       if lin_AP1 ≤ 0
  (log2(2^−16 + lin_AP1 × 0.5) + 9.72) / 17.52       if lin_AP1 < 2^−15
  (log2(lin_AP1) + 9.72) / 17.52                     if lin_AP1 ≥ 2^−15
  ```
- **ACEScct** (S-2016-001 §1.1), the same log with a linear toe:
  ```
  10.5402377416545 × lin_AP1 + 0.0729055341958355    if lin_AP1 ≤ 0.0078125
  (log2(lin_AP1) + 9.72) / 17.52                     if lin_AP1 > 0.0078125
  ```
  the toe "introduced following many colorists' requests to have a 'log'
  working space more alike those used in traditional film color-grading"
  (Arrighetti §3.3). The two "are identical above CV_ACES2065 0.0078125".
- **ACESproxy** (S-2013-001), integer transport over SDI, "Not intended to be
  stored or used in production imagery or for final color grading/mastering"
  (TB-2014-012). Ten-bit: `FLOAT2CV10[(log2(lin_AP1) + 2.5) × 50 + 425]`
  clamped to [64, 940], with 64 for `lin_AP1 ≤ 2^−9.72`; twelve-bit:
  `(log2(lin_AP1) + 2.5) × 200 + 1700` clamped to [256, 3760].

In every one of these the mid-grey of §2 is preserved: the rows of TRA_1 sum
to 1.0000, so 0.18 in ACES2065-1 remains 0.18 on the AP1 neutral axis, and
the log encodings place it at (log2(0.18) + 9.72) / 17.52 = 0.4136.

## 4. Containers

**ST 2065-4:2023** constrains OpenEXR. The required attributes are
`acesImageContainerFlag`, `channels`, `chromaticities`, `compression`,
`dataWindow`, `displayWindow`, `lineOrder`, `pixelAspectRatio`,
`screenWindowCenter` and `screenWindowWidth` (§6.5.3, Table 5).
`acesImageContainerFlag` "shall be of type int and shall contain the value 1";
`chromaticities` "shall contain the chromaticity values of the ACES RGB
primaries and the ACES RGB white point as defined in SMPTE ST 2065-1", written
as 0.73470, 0.26530, 0.00000, 1.00000, 0.00010, −0.0770, 0.32168, 0.33767
(Table 17); `compression` "shall contain the value 0, indicating no
compression" (§8.19); pixel data "shall be a sequence of values of type half"
(§6.7.1). The docs site lists "Recommendations for using compression in ACES
OpenEXRs" among ACES 2 changes, so a later edition of the standard may relax
§8.19; the 2023 text does not.

**DPX carries ADX.** TB-2014-007 in full: "SMPTE ST 268:2014 … is an update to
SMPTE ST 268M:2003. The updated standard specifies how image data and metadata
should be written to the file format when the image data is in the Academy
Density Exchange Encoding (ADX)." ST 268:2014 itself was not obtained.
ST 2065-5 wraps ST 2065-4 frames in MXF (Arrighetti §3.10); not obtained.

## 5. Input transforms, and the film path in the system's own words

P-2013-001 is the Academy's procedure for camera IDTs, still marked DRAFT at
v1.0.3. It requires that the IDT's output "In the case of D60 illumination,
approximate the ACES RGB relative exposure values that would be produced by the
RICD", "Approximate radiometrically linear representations of light reaching
the focal plane", "Contain a nonzero amount of flare as specified in the ACES
document", "Use equal RGB relative exposure values to represent colors that are
neutral under the illumination source for which the IDT is designed", and
"Approximate a colorimetric response to the scene for the illumination source
for which the IDT is designed, though the native camera system response itself
may not be colorimetric" (§1.1). The scale rule is the grey card again: values
"are uniformly scaled such that a spectrally neutral 18% reflector captured
under the scene adopted white would map to ACES RGB relative exposure values of
[0.18, 0.18, 0.18]" (§5.6). Vendors are asked for two IDTs, "one optimized for
CIE Illuminant D55 (daylight) and a second optimized for the ISO 7589 Studio
Tungsten illuminant". The matrix is fitted by non-linear least squares over
training spectra with a colour-appearance cost, and Clark's 2010 study applied
exactly this procedure to a broadcast camera, reaching average ΔE00 of 1.6–1.9
on the training set and 2.3–2.7 on a real chart.

On film the procedure is silent. TB-2014-002 says "The typical IDTs are
transforms for digital cinema cameras and film scanners", and P-2013-001 never
mentions a scanner, ADX or printing density. The film path is stated only in
the original specification, S-2008-001 §5.5:

> "Files containing Cineon and SMPTE RP-180 printing density data first should
> be converted to Academy Printing Density (APD) data, after which the APD data
> are brought into ACES by an appropriate Input Device Transform (IDT)."

and for prints, §5.5.5: "Print film imagery can be converted to ACES data by
scanning the print, computing the projected colorimetry implied by the scanner
output, then determining what ACES values would have produced that colorimetry
when put through the RRT and ODT for film projection." The ST 2065-1 text
dropped §5 entirely; the SMPTE standard defines the encoding and leaves entry
to the Academy's transforms. The "appropriate IDT" for APD is the universal
unbuild, examined in the companion note.

## 6. Where this project's routes stand

This section is the project's reading, and PROJECT.md is authoritative where
they differ.

- **The ECN-2 ADX16 cube is an ST 2065-3 encoder**, not an IDT. It emits
  D-min-subtracted APD as code values; the Academy's ADX16-to-ACES transform is
  the IDT in the S-2008-001 §5.5.3 sense, and everything that transform
  assumes about the negative (companion note §5) applies after the cube.
- **The scan-side method is not a P-2013-001 IDT.** An IDT maps a camera's
  linear RGB to relative exposure by a matrix fitted over training spectra
  under a scene illuminant. The project's engines map a narrowband scan to a
  density metric through a dye model, with no scene illuminant and no training
  set. The two are answers to different questions: one characterises a camera
  looking at a scene, the other a camera looking at a negative. The P-2013-001
  requirements on neutrality and on the 0.18 scale have no direct counterpart
  on the density side, where the corresponding conventions are ADX's k factors
  and its D-min subtraction.
- **The scene-referred ECN-2 route lands on DaVinci Wide Gamut**, not on
  ACES2065-1. Both are linear, so the step into ACES is a colour space
  transform, a matrix and a white adaptation, which Resolve performs as a
  standard operation. The route's mid-grey convention is its own; the ACES
  0.18 rule of §2 is met only if the roll anchor places grey there.
- **The C-41 print route never enters ACES.** It is display-referred by
  design (Display P3 output), so it is a finished picture in ACES terms, and an
  ACES user would treat it as one more delivered output rather than as
  material for grading.
- **The camera sensitivity library** is the Academy's `rawtoaces-data`, which
  exists to build P-2013-001 IDTs from spectral data. The project uses the
  same sensitivities for a different purpose, predicting a scan through a
  mask, and PROJECT.md records that dependence under the sensor-free default
  and its corridors.

## 7. Open questions and material not found

- **The ACES 2 rendering internals.** The docs site was read at summary level
  only; the tone scale and gamut mapping of the ACES 2 Output Transforms were
  not examined and are not needed by any route here, since the project's ACES
  delivery ends at ADX16.
- **ST 268:2014 DPX fields for ADX**, ST 2065-5 and ISO 22028-1 were not
  obtained. None affects a route that hands code values to Resolve directly.
- **Whether the RICD sensitivities of the 2021 formula differ numerically from
  the 2008 tables** was not checked; TB-2014-004 states the change as
  editorial and the project uses neither.

## Sources

- SMPTE ST 2065-1:2021, *Academy Color Encoding Specification (ACES)* – https://pub.smpte.org/latest/st2065-1/st2065-1-2021.pdf (tier A, fetched in full)
- SMPTE ST 2065-4:2023, *ACES Image Container File Layout* – https://pub.smpte.org/latest/st2065-4/st2065-4-2023.pdf (tier A, fetched in full)
- A.M.P.A.S. S-2008-001 v1.0, *Academy Color Encoding Specification (ACES)*, 12 August 2008 – https://github.com/ampas/aces-dev/blob/v1.0.3/documents/LaTeX/TB-2014-004/S-2008-001.pdf (tier A, fetched in full)
- A.M.P.A.S. TB-2014-001, TB-2014-002, TB-2014-004, TB-2014-007, TB-2014-010, TB-2014-012, S-2013-001, S-2014-002, S-2014-003, S-2014-004, S-2016-001, P-2013-001 – https://github.com/ampas/aces-dev/tree/v1.0.3/documents/LaTeX (tier A, LaTeX sources); PDFs are linked from https://github.com/ampas/aces-dev/blob/v1.0.3/documents/README.md
- W. Arrighetti, "The Academy Color Encoding System (ACES): A Professional Color-Management Framework for Production, Post-Production and Archival of Still and Motion Pictures", *Journal of Imaging* 3(4):40, 2017 – https://doi.org/10.3390/jimaging3040040 (tier A, CC BY 4.0, fetched)
- C. J. Clark, *Investigation of the Academy's Image Interchange Framework at RIT*, 21 May 2010 – https://s3.cad.rit.edu/cadgallery_production/storage/media/uploads/faculty-s-projects/472/documents/25/academy-iif-at-rit.pdf (tier B, fetched)
- docs.acescentral.com, *ACES System* – https://docs.acescentral.com/background/overview/ and *About ACES 2* – https://docs.acescentral.com/background/about-aces-2/ (tier B, fetched, version of 10 September 2025)
- Academy Software Foundation, `aces-input-and-colorspaces` – https://github.com/aces-aswf/aces-input-and-colorspaces (tier A, code, ACES 2 transforms)
- SMPTE ST 2065-5, ST 268:2014, ISO 22028-1:2016, CIE 015:2018 (NOT obtained, paid standards)
