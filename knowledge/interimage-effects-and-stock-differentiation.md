# Interimage effects (IIE) and the origin of differences between C-41 stocks

Collected 2026-07-26 in response to the **C-41 fleet discrimination gap**
documented in PROJECT.md. The C-41 stock models do not distinguish the stocks
in the fleet from one another, and no file under `engine/c41/` contains a DIR
stage at all, so interimage coupling is absent from the live C-41 branch. Where
the structure does exist, in `engine/ecn2/cineon_pd_engine.py` and the retired
`engine/retired/c41_scene_engine.py`, `DIR_MATRIX = np.eye(3)` disables it. The
question this file addresses is whether interimage is
in fact where the inter-stock difference resides, and whether it can be
quantified accurately enough to model.

It can be quantified accurately enough to model, subject to one reservation
concerning the quality of the available sources.

> **Note on scope.** The literature findings below stand as collected. The
> project implications in §5 have since been revised: `DIR_MATRIX` gates no
> shipped cube, for the reason set out in that section. PROJECT.md is
> authoritative on the current position.

---

## 0. Provenance and confidence

This project distinguishes measured data from inferred data throughout, and the
same discipline applies here. Sources fall into three tiers.

| Tier | Source | Status |
|---|---|---|
| **A, verified primary** | Patent US4830954A (Agfa-Gevaert, Matejec, filed 1987-02-21, granted 1989-05-16), fetched and read via Google Patents | The definition and numbers below are quoted from the fetched text |
| **B, manufacturer literature** | Kodak Alaris Ektar 100 datasheet E-4046 and Kodak product copy | Marketing-grade, although it is the manufacturer describing its own design |
| **C, UNVERIFIED expert testimony** | Photrio (formerly APUG) posts by "Photo Engineer", that is, Ron Mowrey, a retired Kodak emulsion engineer with approximately 15 years on Eastman Kodak colour negative film design beginning with Ektar 25 | **photrio.com returns HTTP 403 to automated fetching.** Everything attributed to Photo Engineer below reached the collector only as *search-engine snippet paraphrase*. It is NOT verbatim-verified. Treat the wording as approximate, and do not quote it as his exact words without opening the thread by hand. |

**A tier-C claim must never be promoted into the model as though it were
measured data.** Tier C is useful for direction and plausibility, and not for
coefficients.

---

## 1. The definition of the interimage effect and its measurement (tier A)

DIR couplers, that is, development-inhibitor-releasing couplers, release an
inhibitor during colour development. The inhibitor diffuses out of the layer
that produced it and retards development in the *other* layers. The net effect,
as the patent literature expresses it, is a reduction of dye density in one
colour record as a function of exposure and development in another colour
record, which cancels the unwanted spectral absorption of the image dyes.

That constitutes a **cross-channel coupling**, which is to say an off-diagonal
matrix, and it is exactly the shape that `DIR_MATRIX` holds.

US4830954A supplies a measurement definition, quoted from the fetched patent
text:

> "IIE is measured...as percentage increase in the colour gradation when colour
> separation exposure is carried out with light of the corresponding spectral
> region, compared with the colour gradation obtained on exposure to white
> light."

The protocol is therefore as follows.

1. Expose the film to a **colour-separation** step wedge, confined to a single
   region of R, G or B.
2. Expose the same film to a **neutral or white-light** step wedge.
3. Compute gamma, that is, gradation, for each, per channel.
4. Evaluate `IIE% = 100 × (gamma_separation − gamma_neutral) / gamma_neutral`.

Single-colour exposure invariably yields the **higher** contrast, the neutral
exposure being suppressed by inhibitor arriving from the other two layers.

## 2. Magnitudes (tier A)

US4830954A specifies the following as the requirement of its invention:

| region | required IIE |
|---|---|
| yellow | ≥ 10% |
| magenta | ≥ 25% |
| cyan | ≥ 15% |

and its worked Example 1B achieved **yellow 15%, magenta 35%, cyan 30%**.

Also from the patent literature: DIR compounds with a **diffusion factor of
≥ 0.4** deliver high levels of inter-record colour correction. Magenta DIR
couplers with high interimage correction are singled out as particularly
desirable for modern colour negative films.

**This is the key quantitative result.** Interimage is not a small
perturbation. A gamma change of 25–35% in the magenta record is very large in
comparison with the approximately 5% characteristic-curve contrast difference
measured between Ektar and Portra 400, at γ 0.563 against 0.534. It is entirely
plausible that interimage rather than dye chemistry carries most of the visible
difference between stocks.

## 3. Saturation as a designed interimage parameter (tier C, unverified)

The most directly relevant statement from Photo Engineer, as paraphrased by
search snippets:

> On the first Kodacolor Gold 400 design team, the task was to *design in higher
> saturation by means of interimage effects*, producing purer and brighter
> colours, against a contrast target of **approximately 0.7, compared with 0.6
> for the professional films**.

Two consequences follow if this is accurate.

- **Saturation differences between Kodak stocks are an interimage design
  parameter rather than primarily a dye-set difference.** That is precisely the
  axis this model has switched off, and it accounts for the stocks collapsing
  together.
- The 0.6 against 0.7 gamma split provides a useful sanity anchor. Measured
  2026-08-18 from `data/films/*_datasheet_curves.json`, by least squares over
  the middle third of each curve's exposure span, the central-slope gammas are
  Portra 400 at R 0.535, G 0.554, B 0.634; Portra 160 at R 0.529, G 0.542,
  B 0.595; and Ektar 100 at R 0.586, G 0.584, B 0.662. These fall in the same
  range as the quoted professional figure of approximately 0.6, with Ektar
  highest, which is consistent with a more saturated design. The figures depend
  on the choice of slope window and should be recomputed rather than quoted.

Further Photo Engineer material in the same vein, also tier C: the gamma of a
given curve differs between single-colour and neutral exposure *because* of
interimage, which exists in order to correct unwanted dye absorption, and with
the other two records absent the remaining record is much higher in contrast. A
colour negative consequently appears unbalanced as a neutral, because
interimage and masking are corrections that resolve only when the negative is
printed or scanned correctly. This is consistent with tier A.

## 4. Ektar specifically (tier B)

Kodak's own Ektar 100 literature attributes the stock's character to **advanced
cubic emulsions together with proprietary DIR couplers**, claiming high
sharpness, fine detail and well-defined edges alongside ultra-vivid colour
saturation. Portra 160 is by contrast described as offering medium saturation,
low contrast and accurate neutral skin tones.

The manufacturer therefore names DIR couplers, which is to say the interimage
mechanism, as an explicit Ektar design element. Taken with §3, the difference in
character between Ektar and the Portras has a concrete mechanism behind it, and
it is a mechanism this model sets to identity. No darkroom observation of that
difference is held in this repository. The one external comparison PROJECT.md
records runs the other way, being the convergence of Portra 160 and Portra 400.

## 4a. Reversal film: the same effect, an entirely different mechanism (tier A)

Added 2026-08-16, from the IS&T 1997 paper previously recorded here as unread.

Shuto, Kuwashima, Bando and Takada, of Fuji Photo Film's Ashigara Research
Laboratories, set out the reversal case. **Interimage in a colour reversal film
is not produced by DIR couplers during colour development.** It arises in the
FIRST, black-and-white development:

> "in case of color reversal films, during the first development (black and
> white development) of color reversal processing, iodide ions released by
> development of silver halide grains in a certain emulsion layer play the part
> of an inhibitor, and diffuse to other emulsion layers to inhibit development
> of silver halide grains within those layers, which generates the
> interimage-effect."

The paper reports the conditions under which it appears: a silver halide solvent
in the first developer, such as potassium thiocyanate or sodium sulfite; silver
iodide in the causing layer's emulsion; smaller silver halide grains in the
receiving layer; and enhancement by DIR hydroquinones, which release inhibitor
during black-and-white development where ordinary DIR couplers cannot act.
Bergthaller (2002) confirms the last point independently: "normal DIR couplers
are of no use in black-and-white development where most of the final
photographic quality of a colour reversal film is established", and DIR
hydroquinones "have proved useful in colour reversal film".

**Interimage matters MORE in reversal film, not less.** The reason is the one
recorded in `orange-mask-and-the-scanning-workflow.md`, stated here from the
other side:

> "In case of color reversal films, an original photographic image is directly
> used for appreciation, and the masking technique by colored couplers which is
> generally used to compensate for the unwanted absorption in case of color
> negative films, may not be utilized. Thus, the use of interimage-effect is a
> particularly important means to improve the color reproduction of color
> reversal films."

A reversal film cannot mask, so interimage is its principal means of correcting
unwanted dye absorption. Fuji attributes the Velvia, Provia and Astia
characters to deliberately controlled interimage, all three using DIR-HQ.

**This settles a comparison PROJECT.md leaves open.** Register entry 8 records the
magnitude of C-41 interimage relative to that of reversal film as **unknown**,
and this material is why. Neither this paper nor US4830954A gives IIE
percentages for both classes measured the same way, so no source obtained
supports a comparison in either direction. The functional argument in fact runs
toward reversal: masking and interimage are alternative corrections, and the
film that cannot mask leans harder on interimage.

**The measurement protocol has an older primary source.** This paper attributes
the separation-against-neutral method to W. T. Hanson Jr and C. A. Horton,
*JOSA* 42:663–669 (1952), which predates US4830954A by thirty-five years and is
the original reference for the technique the validation roll needs. Hanson is
the same author as the 1950 coloured-coupler paper underpinning the orange-mask
note.

**Vintage caveat.** This is a 1997 account of 1990s Fujichrome products. The
mechanism is likely still correct, since it follows from process chemistry
rather than from any one emulsion, but the named stocks and their characters
must not be transferred to current product.

## 5. Implications for the project

1. **The discrimination gap has a named and quantified cause.** Interimage
   magnitudes of 10–35% gamma change dwarf the approximately 5%
   characteristic-curve difference that currently constitutes the only
   separation between the stocks in this fleet.
2. **The measurement protocol maps exactly onto the planned validation roll.**
   §1 requires a colour-separation exposure series *and* a neutral series on
   the same film. A roll plan consisting of a gray ramp of ±3 stops together
   with a ColorChecker would NOT yield IIE, because it contains no
   colour-separation exposure. The roll plan accordingly carries **R/G/B
   separation step wedges** alongside the gray ramp and the ColorChecker. This
   is the finding here that reaches the plan, and it survives the revision in
   item 4 below.
3. **The patent's numbers must not be hard-coded.** They state Agfa's
   requirement for one 1987 invention and are not Kodak's values for Portra or
   Ektar. They bound the plausible range, of order 10–35% with magenta largest
   and yellow smallest, and supply a sane prior and sanity range for a fit.
   They serve no further purpose.
4. **Fitting `DIR_MATRIX` is NOT the remedy for the discrimination gap.** This
   supersedes the recommendation originally recorded here. Interimage occurs
   during DEVELOPMENT, whereas every cube in this pipeline begins after
   development: `<Stock>_StatusM.cube` performs densitometry on dyes that
   already exist, and `endura_print_engine.py` neither inverts a characteristic
   curve nor calls `apply_dir`. When a real negative is scanned, the interimage
   effect is already physically present in the measured densities, so
   re-simulating it would double-count. `DIR_MATRIX` accordingly gates no
   shipped cube. See "C-41 fleet discrimination gap" in PROJECT.md.
5. **The basis-sensitivity measurement does not exonerate the basis.** Measured
   from the shipped dye data, basis sensitivity is 0.034–0.063 D against
   inter-stock distances of 0.024–0.220 D, so 17 of the 55 pairs sit inside the
   ambiguity band. The
   remedy identified is MEASURED per-layer dye data, which only
   colour-separation wedges on a measured validation roll can supply. This
   reinforces item 2 while removing the conditional framing originally recorded
   in this section.

## 6. Open questions and material not found

- No verbatim Photo Engineer text could be retrieved, the server returning 403.
  Where exact wording matters, the threads must be opened by hand; the most
  technical is "Color Bias in characteristic curve in negative films", Photrio
  thread 155654.
- No published per-stock IIE values for Portra 400, Portra 160 or Ektar 100
  were found. Kodak does not publish them and the datasheets contain no
  interimage data. **IIE for these stocks must therefore be MEASURED rather
  than looked up.**
- The IS&T 1997 paper has since been obtained and read; see §4a. It contains a
  mechanism and a qualitative demonstration but **no formal model and no IIE
  percentages**. Its Figure 2 plots D-logE curves for the red-sensitive layers
  of Astia 100 and Provia 100 under white light and through a red filter, and
  the separation exposure is visibly steeper, as the definition requires.
  **The figure is not digitisable**: within each exposure pair the two films are
  drawn in the same line style and the legend's two swatches are visually
  identical at the published reproduction quality, so no curve can be attributed
  to a film. It is recorded as a qualitative confirmation only.
- Hanson and Horton, *JOSA* 42:663–669 (1952), the original source of the
  separation-against-neutral measurement method, has not been retrieved.
- Joel Panning, *Interimage Effects and the MTF of a Color Reversal Film*, RIT
  thesis, 1978. The full text is a free 1.4 MB PDF from RIT; the abstract
  indicates an empirical MTF methodology rather than a matrix formulation. It
  is unread in full. It concerns reversal rather than negative material and is
  therefore of secondary relevance.

## Sources

- US4830954A, "Color photographic negative film", Agfa-Gevaert AG, Reinhart Matejec – https://patents.google.com/patent/US4830954A/en (tier A, fetched)
- Kodak Alaris, Ektar 100 technical data E-4046 – https://kodakprofessional.com/sites/default/files/2025-07/e4046.pdf (tier B; local copy at `film_datasheet/Ektar 100.pdf`)
- Photrio, "Color Bias in characteristic curve in negative films", thread 155654 – https://www.photrio.com/forum/threads/color-bias-in-characteristic-curve-in-negative-films.155654/ (tier C, NOT fetched, 403)
- Photrio, "Question about Kodak Gold 200", thread 123709 – https://www.photrio.com/forum/threads/question-about-kodak-gold-200.123709/page-2 (tier C, NOT fetched, 403)
- Photrio, "Tips on shooting Ektar", thread 203383 – https://www.photrio.com/forum/threads/tips-on-shooting-ektar.203383/ (tier C, NOT fetched, 403)
- Joel Panning, "Interimage Effects and the MTF of a Color Reversal Film", RIT, 1978 – https://repository.rit.edu/theses/4816/
- S. Shuto, S. Kuwashima, S. Bando and S. Takada (Fuji Photo Film, Ashigara Research Laboratories), "Mechanism of the Interimage-Effect in Color Reversal System and Its Application to Improve Color Reproduction", IS&T's 50th Annual Conference, 1997, pp. 210–212 (tier A, obtained and read in full)
- W. T. Hanson Jr and C. A. Horton, "Subtractive color reproduction: interimage effects", *J. Opt. Soc. Am.* 42:663–669 (1952) – the original separation-against-neutral method (NOT retrieved)
- P. Bergthaller, "Couplers in colour photography – chemistry and function, Part 2", *The Imaging Science Journal* 50(3):187–230, 2002 (tier A, obtained; see `dye-sets-across-the-three-processes.md`)
- Related DIR-coupler patents (tier A, background): US5273870, US6174662, US5965341, US5958662
