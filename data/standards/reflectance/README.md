# Reflectance datasets (for broad-set matrix fitting/validation)

Fetched 2026-07-22 for the C-41 scene-matrix improvement (fit/validate beyond the
24-patch ColorChecker). All files share one JSON schema:

```
{ "<spectrum name>": { "wl_start", "wl_end", "wl_step", "values": [reflectance 0–1] } }
```

| File | Spectra | Grid | Source |
|---|---|---|---|
| `munsell_glossy_all.json` | 1600 | 380–780 @ 1 nm | UEF Spectral Color Research group (Orava), via colour-science Zenodo record 3269918 |
| `munsell_matt.json` | 1269 | 380–800 @ 1 nm | UEF (Hauta-Kasari), Zenodo record 3269912 |
| `agfa_it872.json` | 289 | 400–700 @ 10 nm | Agfa IT8.7/2 target (Marszalec, UEF), Zenodo record 3269926; rescaled from percent to 0–1 |
| `nist_skin.json` | 100 | 380–780 @ 1 nm | NIST Reference Data Set of Human Skin Reflectance (Cooksey, Allen, Tsai 2017), doi:10.6028/jres.122.026; per-subject average of R1–R3, native 250–2500 @ ~3 nm linearly resampled |

Notes
- Otsu et al. (2018) clusters were not fetched: not in the Zenodo registry, and the
  Munsell + IT8.7/2 pool covers the same natural/photographic-dye gamut.
- `nist_skin.json` uses each subject's *average* spectrum; raw R1/R2/R3 replicates
  remain in the original download if per-replicate variance is ever needed.
- Original raw files cached in `~/.colour-science/colour-datasets/` (Zenodo sets).
