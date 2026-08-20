# Camera spectral sensitivities

Forty-four camera spectral sensitivity functions, arranged in the key layout the
engines' CFA reader expects: `ssf_bands`, `red_ssf`, `green_ssf`, `blue_ssf`.
Any one of them can supply the camera term the engines integrate. `index.json`
lists every camera with its file name, source hash, and the EXIF model strings
that resolve onto it.

## Licence

These files are **Apache-2.0**, not the CC BY 4.0 that covers the rest of
`data/`. They originate in
[AcademySoftwareFoundation/rawtoaces-data](https://github.com/AcademySoftwareFoundation/rawtoaces-data),
and each file repeats the notice and records the URL and SHA-256 of the bytes
it was built from. Values are reproduced verbatim: nothing is resampled,
smoothed or rescaled, and only the arrangement of the numbers differs from the
source. Channel order is read from each source file's own
`spectral_data.index.main` rather than assumed.

## Scope

The set is the consumer interchangeable-lens subset of the 52 cameras ACES
publishes, restricted to Bayer sensors. Six are omitted as implausible film
scanners, all of which also sit at the extremes of the measured spread: two
fixed-lens compacts (Canon PowerShot S90, Sony DSC-RX100M4), two drone camera
modules (Hasselblad L1D-20c and L2D-20c), a 360 camera (Insta360 X5) and a
cinema camera (ARRI D21). Two more are omitted for their sensor filter
geometry: the Fujifilm X-T3 and X-T4 carry an X-Trans mosaic rather than a
Bayer one, which does not suit this project's scanning workflow. The Fujifilm
GFX 100 is retained, its sensor being Bayer. The list is explicit in
`engine/scan/aces_ssf_import.py` rather than derived by exclusion, so cameras
added upstream do not enter the repository unreviewed.

## Provenance and its limits

Thirty-eight of the 44 come from one creator, Weta Digital, on an instrument
named only as `lightsaber`, and carry no `laboratory` field. Five come from
scitech and one from the National Physical Laboratory on a double
monochromator; those six, dated 2017, are the better documented of the set.

Three gaps apply to all 44. No file records the lens or filter stack the
measurement was taken through, so none is exactly the sensitivity of a
particular scanning apparatus. No file declares a monochromator bandwidth: the
schema provides `bandwidth_FWHM` and `bandwidth_corrected`, and every file
either omits them or sets them to null, so any residual instrument broadening
is undocumented. Values are relative, with an arbitrary per-channel scale;
this last point is immaterial here, because every engine row-normalises the
LED SPD times SSF product to unit sum per channel, which cancels a per-channel
scale exactly.

## Regenerating

    python3 engine/scan/aces_ssf_import.py --all

The importer reads each written file back through a copy of the engines' regex
reader and fails if any array differs from the source.
