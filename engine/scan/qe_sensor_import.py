#!/usr/bin/env python3
"""Reduce a published quantum-efficiency table of a monochrome camera assembly
to a sensor file the scan engines read.

    python3 engine/scan/qe_sensor_import.py <table.txt>           # write
    python3 engine/scan/qe_sensor_import.py <table.txt> --check   # compare only

The table is Table 3 of Ofek et al. 2023 (PASP 135, 065001,
doi:10.1088/1538-3873/acd8f0): the quantum efficiency of an IMX455 detector
with the window of a QHY600M-PH camera. It is not held in this repository; the
script refuses any file whose SHA-256 differs from TABLE_SHA256.

Reduction, in this order:
  1. the mean of the table's points in each 5 nm bin [c - 2.5, c + 2.5) for
     c = 380, 385, ..., 780 nm; a bin with fewer than MIN_POINTS points is
     omitted (the table has no point between 691.55 and 722.04 nm, so the
     bins 695 to 715 nm are absent and the engines interpolate across them);
  2. rounding to six decimals;
  3. conversion to a response per unit radiant power: QE x wavelength / 550,
     rounded to six decimals. A quantum efficiency is a response per photon,
     and the engines weight the LED spectrum as radiant power.
The same curve is written to all three channels.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "sensors" / "QHYCCD_QHY600M-PH_ssf.json"
TABLE_SHA256 = "e0d206dcaa90ea6020f36792104cd821e327aa5667523e6c74103c8d3a0a540e"
MIN_POINTS = 3
REFERENCE_NM = 550.0


def read_table(path):
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != TABLE_SHA256:
        sys.exit("table sha256 %s differs from the recorded %s" % (digest, TABLE_SHA256))
    rows = []
    for line in raw.decode("utf-8").splitlines():
        if re.match(r"^\s*\d+\.\d+\s+-?\d", line):
            w, q = line.split()[:2]
            rows.append((float(w), float(q)))
    return rows


def reduce_table(rows):
    bands, qe = [], []
    for i in range(81):
        c = 380.0 + 5.0 * i
        pts = [q for w, q in rows if c - 2.5 <= w < c + 2.5]
        if len(pts) >= MIN_POINTS:
            bands.append(c)
            qe.append(round(sum(pts) / len(pts), 6))
    power = [round(q * c / REFERENCE_NM, 6) for c, q in zip(bands, qe)]
    return bands, qe, power


def document(bands, qe, power):
    return {
        "camera_name": "QHYCCD QHY600M-PH (IMX455 detector and camera window)",
        "manufacturer": "QHYCCD",
        "model": "QHY600M-PH",
        "notice": ("Reduced from Table 3 of Ofek et al. 2023, PASP 135, 065001, "
                   "doi:10.1088/1538-3873/acd8f0, published under CC BY 3.0. "
                   "The reduction is licensed CC BY 4.0 with the rest of data/."),
        "source": {
            "doi": "10.1088/1538-3873/acd8f0",
            "table": "Table 3, Quantum Efficiency of the IMX455 detector and window",
            "table_copy": "machine-readable table of the arXiv source, 2304.04796",
            "table_sha256": TABLE_SHA256,
            "measured_object": "one detector with the camera window; no lens",
        },
        "reduction": {
            "bin_nm": 5.0,
            "bin_rule": "mean of the table points in [centre - 2.5, centre + 2.5)",
            "minimum_points_per_bin": MIN_POINTS,
            "omitted_bins_nm": [c for c in (380.0 + 5.0 * i for i in range(81)) if c not in bands],
            "conversion": "quantum efficiency x wavelength / 550, a response per unit radiant power",
            "generated_by": "engine/scan/qe_sensor_import.py",
        },
        "units": "relative response per unit radiant power",
        "units_note": ("The scan engines weight the LED spectrum as radiant power. If the LED "
                       "spectrum records photon flux, the quantum_efficiency array is the "
                       "response to use and this file's ssf arrays are not."),
        "ssf_bands": bands,
        "red_ssf": power,
        "green_ssf": power,
        "blue_ssf": power,
        "quantum_efficiency": qe,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("table")
    ap.add_argument("--check", action="store_true", help="compare with the file on disk and write nothing")
    args = ap.parse_args()
    doc = document(*reduce_table(read_table(args.table)))
    text = json.dumps(doc, indent=1) + "\n"
    if args.check:
        if not OUT.exists() or OUT.read_text() != text:
            sys.exit("MISMATCH: %s differs from the reduction of the table" % OUT)
        print("MATCH: %s (%d bands)" % (OUT.relative_to(ROOT), len(doc["ssf_bands"])))
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    print("wrote %s (%d bands, omitted bins %s)" % (OUT.relative_to(ROOT), len(doc["ssf_bands"]),
                                                    doc["reduction"]["omitted_bins_nm"]))


if __name__ == "__main__":
    main()
