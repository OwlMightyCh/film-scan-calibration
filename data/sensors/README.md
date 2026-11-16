# Measured monochrome assemblies

Response curves of monochrome camera assemblies, in the key layout the scan
engines read: `ssf_bands`, `red_ssf`, `green_ssf`, `blue_ssf`. A monochrome
sensor has one response, so the three channel arrays are equal.

## The file held

`QHYCCD_QHY600M-PH_ssf.json` is reduced from Table 3 of Ofek et al. 2023,
"The Large Array Survey Telescope: System Overview and Performances", PASP
135, 065001, doi:10.1088/1538-3873/acd8f0. The table gives the quantum
efficiency of one IMX455 detector with the window of a QHY600M-PH camera,
measured against a calibrated reference detector, with no lens.

The article is published under CC BY 3.0. The reduction is licensed CC BY 4.0
with the rest of `data/`.

## Reduction

    python3 engine/scan/qe_sensor_import.py <table.txt>
    python3 engine/scan/qe_sensor_import.py <table.txt> --check

The table itself is not redistributed here. The script accepts only a file
with the recorded SHA-256, which is that of the machine-readable table in the
arXiv source of the article (2304.04796). The journal's own copy of the table
has not been compared with it.

1. The mean of the table's points in each 5 nm bin from 380 to 780 nm. A bin
   with fewer than three points is omitted.
2. The table has no point between 691.55 and 722.04 nm. The bins from 695 to
   715 nm are therefore absent, and the engines interpolate linearly across
   them.
3. Each bin mean is multiplied by wavelength over 550 nm. A quantum
   efficiency is a response per photon, and the engines weight the LED
   spectrum as radiant power.

The file also carries the binned quantum efficiency, in the
`quantum_efficiency` array.

## Limits

- The curve describes one unit of one assembly. Another camera with the same
  sensor designation has its own window and filter stack and needs its own
  measured response.
- The conversion assumes that the LED spectrum records radiant power. The
  export unit of the LED file is unconfirmed (PROJECT.md register #9). If it
  records photon flux, the `quantum_efficiency` array is the response to use.
- `knowledge/monochrome-camera-response.md` gives the modelled effect of the
  curve, the alternatives across the missing interval and the limits of the
  source.
