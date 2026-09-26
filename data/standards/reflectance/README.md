# Reflectance datasets, for broad-set matrix fitting and validation

Fetched 2026-07-22. These datasets support fitting and validating a 3×3 matrix
against a population of measured spectra considerably larger than the 24-patch
ColorChecker. The broad-set fit itself resides in the unpublished
scene-referred engine, which produces no shipped cube and is the only home for
that fit, for the ColorChecker full-chain ΔE2000 harness and for the
neutral-axis ramp diagnostic; the Vision3 scene engine fits its per-stock
matrix on the same pool. See PROJECT.md for the surrounding context.

All files share a single JSON schema:

```
{ "<spectrum name>": { "wl_start", "wl_end", "wl_step", "values": [reflectance 0–1] } }
```

| File | Spectra | Grid | Source |
|---|---|---|---|
| `munsell_glossy_all.json` | 1600 | 380–780 @ 1 nm | UEF Spectral Color Research group (Orava), via colour-science Zenodo record 3269918 |
| `munsell_matt.json` | 1269 | 380–800 @ 1 nm | UEF (Hauta-Kasari), Zenodo record 3269912 |
| `agfa_it872.json` | 289 | 400–700 @ 10 nm | Agfa IT8.7/2 target (Marszalec, UEF), Zenodo record 3269926; rescaled from percent to 0–1 |
| `nist_skin.json` | 100 | 380–780 @ 1 nm | NIST Reference Data Set of Human Skin Reflectance (Cooksey, Allen and Tsai 2017), doi:10.6028/jres.122.026; per-subject average of R1–R3, natively 250–2500 nm at approximately 3 nm, linearly resampled |

Notes:

- The Otsu et al. (2018) clusters were not fetched. They are absent from the
  Zenodo registry, and the Munsell together with IT8.7/2 pool covers the same
  natural and photographic-dye gamut.
- `nist_skin.json` holds each subject's *average* spectrum. The raw R1, R2 and
  R3 replicates remain in the original download should per-replicate variance
  ever be required.
- The original raw files are cached in `~/.colour-science/colour-datasets/` for
  the Zenodo sets.
