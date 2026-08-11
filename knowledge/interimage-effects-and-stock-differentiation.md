# Interimage effects (IIE) and why C-41 stocks differ

Collected 2026-07-26 in response to the **C-41 fleet discrimination gap** (see
PROJECT.md): our three C-41 stock models do not tell Portra 400, Portra 160 and
Ektar 100 apart, and `DIR_MATRIX = np.eye(3)` — interimage coupling is disabled.
The question this file answers: *is interimage actually where the inter-stock
difference lives, and can it be quantified well enough to model?*

Short answer: **yes to both, with one caveat about source quality.**

---

## 0. PROVENANCE AND CONFIDENCE — read this first

This project distinguishes measured data from inferred data everywhere else, so
the same discipline applies here. Sources fall into three tiers:

| Tier | Source | Status |
|---|---|---|
| **A — verified primary** | Patent US4830954A (Agfa-Gevaert, Matejec, filed 1987-02-21, granted 1989-05-16), fetched and read via Google Patents | Definition and numbers below are quoted from the fetched text |
| **B — manufacturer literature** | Kodak Alaris Ektar 100 datasheet E-4046 and Kodak product copy | Marketing-grade, but it is the manufacturer describing its own design |
| **C — UNVERIFIED expert testimony** | Photrio (formerly APUG) posts by "Photo Engineer" / PE — Ron Mowrey, retired Kodak emulsion engineer, ~15 years on EK colour negative film design starting with Ektar 25 | **photrio.com returns HTTP 403 to automated fetching.** Everything attributed to PE below reached me only as *search-engine snippet paraphrase*. It is NOT verbatim-verified. Treat wording as approximate and do not quote it as his exact words without opening the thread by hand. |

**Do not promote a tier-C claim into the model as if it were measured data.**
Tier C is useful for *direction and plausibility*, not for coefficients.

---

## 1. What interimage effect is, and how it is MEASURED (tier A)

DIR couplers — development-inhibitor-releasing couplers — release an inhibitor
during colour development. The inhibitor diffuses out of the layer that produced
it and retards development in the *other* layers. The net effect, as the patent
literature puts it, is *reducing dye density in one colour record as a function
of exposure and development in another colour record*, which cancels the unwanted
spectral absorption of the image dyes.

That is a **cross-channel coupling**, i.e. exactly an off-diagonal matrix — which
is what our `DIR_MATRIX` is shaped to hold.

US4830954A gives a measurement definition, quoted from the fetched patent text:

> "IIE is measured...as percentage increase in the colour gradation when colour
> separation exposure is carried out with light of the corresponding spectral
> region, compared with the colour gradation obtained on exposure to white light."

So the protocol is:

1. Expose the film to a **colour-separation** (single-region: R, G or B) step wedge.
2. Expose the same film to a **neutral / white-light** step wedge.
3. Per channel, compute gamma (gradation) for each.
4. `IIE% = 100 × (gamma_separation − gamma_neutral) / gamma_neutral`

Single-colour exposure always gives the **higher** contrast; the neutral exposure
is suppressed by inhibitor arriving from the other two layers.

## 2. Magnitudes (tier A)

US4830954A specifies as its invention's requirement:

| region | required IIE |
|---|---|
| yellow | ≥ 10% |
| magenta | ≥ 25% |
| cyan | ≥ 15% |

and its worked Example 1B achieved **yellow 15%, magenta 35%, cyan 30%**.

Also from the patent literature: DIR compounds with a **diffusion factor ≥ 0.4**
give high levels of inter-record colour correction. Magenta DIR couplers with
high interimage correction are singled out as particularly desirable for modern
colour negative films.

**This is the key quantitative result for us.** Interimage is not a small
perturbation — a 25–35% gamma change in the magenta record is very large compared
with the ~5% characteristic-curve contrast difference we measured between Ektar
and Portra 400 (γ 0.563 vs 0.534). It is entirely plausible that interimage, not
dye chemistry, carries most of the visible inter-stock difference.

## 3. Saturation is DESIGNED IN via interimage (tier C — unverified)

The most directly relevant PE statement, as paraphrased by search snippets:

> On the first Kodacolor Gold 400 design team, the job was to *design in higher
> saturation by means of interimage effects* — purer and brighter colours — with
> a contrast target of **about 0.7, against the pro films' 0.6**.

Two things follow if this is accurate:

- **Saturation differences between Kodak stocks are an interimage design
  parameter, not primarily a dye-set difference.** That is precisely the axis our
  model has switched off, and it explains why our three stocks collapse together.
- The γ 0.6 / 0.7 split is a useful sanity anchor. Our digitized central-slope
  gammas are Portra 400 R 0.534 / G 0.552 / B 0.633, Portra 160 R 0.523 / G 0.544
  / B 0.605, Ektar 100 R 0.563 / G 0.571 / B 0.661 — same ballpark as "pro ≈ 0.6",
  with Ektar highest, consistent with a more saturated design.

Other PE material in the same vein (tier C): the gamma of a given curve differs
between single-colour and neutral exposure *because* of interimage, which exists
to correct unwanted dye absorption; with the other two records absent, the
remaining record is much higher in contrast. A colour negative therefore looks
"unbalanced" as a neutral because interimage and masking are corrections that only
resolve when printed or scanned properly. This is consistent with tier A.

## 4. Ektar specifically (tier B)

Kodak's own Ektar 100 literature attributes its character to **advanced cubic
emulsions plus proprietary DIR couplers**, for high sharpness, fine detail and
well-defined edges, alongside "ultra-vivid colour saturation". Portra 160 by
contrast is described as medium saturation, low contrast, accurate neutral skin
tones.

So the manufacturer names DIR couplers — the interimage mechanism — as an explicit
Ektar design element. Combined with §3, the user's darkroom observation that Ektar
is markedly different from the Portras has a concrete mechanism behind it, and it
is a mechanism our model currently has set to identity.

## 5. What this means for the project

1. **The discrimination gap has a named, quantified cause.** Interimage magnitudes
   of 10–35% gamma change dwarf the ~5% characteristic-curve difference that is
   currently the only thing separating our stocks. This raises confidence that
   fitting `DIR_MATRIX` is the right fix, ahead of further stock additions.
2. **The measurement protocol maps exactly onto the planned validation roll.**
   §1 requires a colour-separation exposure series *and* a neutral series on the
   same film. Our current roll plan (gray ramp ±3 stops + ColorChecker) would NOT
   yield IIE — it has no colour-separation exposure. **Add R/G/B-separation step
   wedges to the roll plan**, or the roll cannot fit the off-diagonal terms it is
   supposed to gate. This is the single most actionable finding here.
3. **Do not hard-code the patent's numbers.** They are Agfa's requirement for one
   1987 invention, not Kodak's values for Portra or Ektar. They bound the plausible
   range (order 10–35%, magenta largest, yellow smallest) and give a sane prior and
   sanity range for a fit — nothing more.
4. **Ordering.** IIE magnitudes here are large enough that interimage is likely a
   bigger term than the surrogate-dye-basis uncertainty. That does not retire the
   basis-sensitivity ensemble — the ensemble is cheap, needs no new data, and
   discriminates between the two candidate causes — but it does suggest that if
   the ensemble exonerates the basis, interimage is very probably the whole story.

## 6. Open / not found

- No verbatim PE text could be retrieved (403). If exact wording matters, the
  threads must be opened by hand — the most technical is "Color Bias in
  characteristic curve in negative films" (Photrio thread 155654).
- No published per-stock IIE values for Portra 400 / 160 / Ektar 100 were found.
  Kodak does not publish them; the datasheets contain no interimage data.
  **This means IIE for our stocks must be MEASURED, not looked up.**
- The IS&T paper "Mechanism of the Interimage-Effect in Color Reversal System and
  Its Application" (1997) returned 403; unread. It may contain a formal model.
- Joel Panning, *Interimage Effects and the MTF of a Color Reversal Film*, RIT
  thesis, 1978 — full text is a free 1.4 MB PDF from RIT; abstract indicates
  empirical MTF methodology rather than a matrix formulation. Unread in full.
  Reversal, not negative, so of secondary relevance.

## Sources

- US4830954A, "Color photographic negative film", Agfa-Gevaert AG, Reinhart Matejec — https://patents.google.com/patent/US4830954A/en (tier A, fetched)
- Kodak Alaris, Ektar 100 technical data E-4046 — https://kodakprofessional.com/sites/default/files/2025-07/e4046.pdf (tier B; local copy at `film_datasheet/Ektar 100.pdf`)
- Photrio, "Color Bias in characteristic curve in negative films", thread 155654 — https://www.photrio.com/forum/threads/color-bias-in-characteristic-curve-in-negative-films.155654/ (tier C, NOT fetched, 403)
- Photrio, "Question about Kodak Gold 200", thread 123709 — https://www.photrio.com/forum/threads/question-about-kodak-gold-200.123709/page-2 (tier C, NOT fetched, 403)
- Photrio, "Tips on shooting Ektar", thread 203383 — https://www.photrio.com/forum/threads/tips-on-shooting-ektar.203383/ (tier C, NOT fetched, 403)
- Joel Panning, "Interimage Effects and the MTF of a Color Reversal Film", RIT, 1978 — https://repository.rit.edu/theses/4816/
- IS&T 1997, "Mechanism of the Interimage-Effect in Color Reversal System and Its Application" — https://www.imaging.org/common/uploaded%20files/pdfs/Papers/1997/IST-0-4/62.pdf (403, unread)
- Related DIR-coupler patents (tier A, background): US5273870, US6174662, US5965341, US5958662
