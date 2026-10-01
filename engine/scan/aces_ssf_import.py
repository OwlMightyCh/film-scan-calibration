#!/usr/bin/env python3
"""aces_ssf_import — ACES camera spectral sensitivities -> engine CFA format.

Fetches camera spectral sensitivity files from the Academy Software
Foundation's rawtoaces-data repository and rewrites them with the key names
the engines' CFA reader expects (`ssf_bands`, `red_ssf`, `green_ssf`,
`blue_ssf`), so any one of them can supply the camera term the engines
integrate.

Nothing is resampled, smoothed or rescaled. The source grid (380-780 nm at
5 nm) and the published relative values are carried across verbatim; the only
change is the arrangement of the numbers. Channel order is taken from each
source file's own `spectral_data.index.main` rather than assumed.

Every file written records the source URL and the SHA-256 of the bytes it was
built from, and is read back through a copy of the engines' regex reader
before the script reports success.

GROUP_A is the 44 consumer interchangeable-lens bodies of the 52 that ACES
publishes. Six are omitted as implausible film scanners, all of which also sit
at the extremes of the measured spread: two fixed-lens compacts (Canon
PowerShot S90, Sony DSC-RX100M4), two drone camera modules (Hasselblad L1D-20c,
L2D-20c), a 360 camera (Insta360 X5) and a cinema camera (ARRI D21). Two more
are omitted for their sensor filter geometry: the Fujifilm X-T3 and X-T4 carry
an X-Trans mosaic rather than a Bayer one, which does not suit this project's
scanning workflow. The Fujifilm GFX 100 is retained, its sensor being Bayer.
The list is explicit rather than derived by exclusion so that cameras added
upstream do not enter the repository unreviewed.

Usage:
    python3 engine/scan/aces_ssf_import.py --all
    python3 engine/scan/aces_ssf_import.py --camera Sony_ILCE-7RM3
    python3 engine/scan/aces_ssf_import.py --camera Nikon_D850 --input local.json

rawtoaces-data is licensed Apache-2.0, which differs from this repository's
CC BY 4.0 data licence; the notice is reproduced in every file written here.
"""

import argparse
import hashlib
import json
import re
import ssl
import urllib.error
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data"
BASE = ("https://raw.githubusercontent.com/AcademySoftwareFoundation/"
        "rawtoaces-data/main/data/")
STEM = "_380_780_5.json"

GROUP_A = (
    "Canon_Digital_Rebel_XTi", "Canon_EOS-1D_X_Mark_II",
    "Canon_EOS-1Ds_Mark_II", "Canon_EOS-1Ds_Mark_III", "Canon_EOS_100D",
    "Canon_EOS_200D", "Canon_EOS_200D_II", "Canon_EOS_5D",
    "Canon_EOS_5D_Mark_II", "Canon_EOS_5D_Mark_III", "Canon_EOS_5D_Mark_IV",
    "Canon_EOS_5DS", "Canon_EOS_600D", "Canon_EOS_M", "Canon_EOS_R",
    "Canon_EOS_R10", "Canon_EOS_R5", "Canon_EOS_R5m2", "Canon_EOS_R6",
    "Canon_EOS_R6m2", "Canon_EOS_RP",
    "Fujifilm_GFX_100",
    "Nikon_D70", "Nikon_D200", "Nikon_D700", "Nikon_D3300", "Nikon_D5100",
    "Nikon_D5300", "Nikon_D7000", "Nikon_D800E", "Nikon_D810", "Nikon_D850",
    "Nikon_Z_f",
    "Panasonic_DC-GX9",
    "Sony_ILCE-6400", "Sony_ILCE-7CM2", "Sony_ILCE-7M3", "Sony_ILCE-7M4",
    "Sony_ILCE-7RM2", "Sony_ILCE-7RM3", "Sony_ILCE-7RM4", "Sony_ILCE-7SM2",
    "Sony_ILCE-7SM3", "Sony_ILCE-9",
)

NOTICE = (
    "Camera spectral sensitivities from AcademySoftwareFoundation/"
    "rawtoaces-data, licensed Apache-2.0. Values are reproduced verbatim; "
    "only the arrangement of the numbers has changed. This file is therefore "
    "Apache-2.0, not the CC BY 4.0 that covers the rest of data/."
)


def context():
    """A python.org Python carries no root certificates; use certifi's."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return None


def get(url, local=None):
    if local:
        return Path(local).read_bytes()
    try:
        with urllib.request.urlopen(url, timeout=30,
                                    context=context()) as response:
            return response.read()
    except urllib.error.URLError as error:
        raise SystemExit(f"Could not fetch {url}: {error}\n"
                         "Download it by hand and pass it with --input.")


def convert(raw):
    source = json.loads(raw)
    header = source["header"]
    spectral = source["spectral_data"]
    order = spectral["index"]["main"]
    if sorted(order) != ["B", "G", "R"]:
        raise ValueError(f"Unexpected channel index: {order}")

    table = spectral["data"]["main"]
    bands = sorted(int(k) for k in table)
    channels = {name: [float(table[str(b)][i]) for b in bands]
                for i, name in enumerate(order)}

    for name, values in channels.items():
        if min(values) < 0.0:
            raise ValueError(f"Negative sensitivity in {name}; clipping would "
                             "fabricate data, so this must be resolved at the "
                             "source")
    return header, spectral["units"], bands, channels


def build(url, digest, header, units, bands, channels):
    return {
        "camera_name": f"{header['manufacturer']} {header['model']}",
        "manufacturer": header["manufacturer"],
        "model": header["model"],
        "notice": NOTICE,
        "source": {
            "repository": "AcademySoftwareFoundation/rawtoaces-data",
            "url": url,
            "sha256": digest,
            "license": header.get("license"),
            "laboratory": header.get("laboratory"),
            "document_creator": header.get("document_creator"),
            "document_creation_date": header.get("document_creation_date"),
            "measurement_equipment": header.get("measurement_equipment"),
            "bandwidth_FWHM_nm": None,
            "schema_version": header.get("schema_version"),
        },
        "units": units,
        "units_note": (
            "Relative, as published. Every engine row-normalises the "
            "LED SPD x SSF product to unit sum per channel, so a per-channel "
            "scale factor cancels and only the shape of each curve is used."),
        "ssf_bands": bands,
        "red_ssf": channels["R"],
        "green_ssf": channels["G"],
        "blue_ssf": channels["B"],
    }


def verify(path, bands, channels):
    """Re-read the written file with a copy of the engines' regex reader."""
    text = path.read_text()

    def array(key):
        match = re.search(key + r'"?\s*:\s*\[([0-9eE.,\s\\-]*?)\]', text)
        if match is None:
            raise ValueError(f"Engine reader cannot find {key} in {path.name}")
        return [float(x) for x in re.findall(
            r'-?\d+\.?\d*(?:[eE][-+]?\d+)?', match.group(1))]

    if array("ssf_bands") != [float(b) for b in bands]:
        raise ValueError(f"Round trip changed ssf_bands in {path.name}")
    for key, name in (("red_ssf", "R"), ("green_ssf", "G"), ("blue_ssf", "B")):
        if array(key) != channels[name]:
            raise ValueError(f"Round trip changed {key} in {path.name}")


def aliases(local=None):
    """EXIF model strings that resolve onto a published camera."""
    raw = get(BASE + "aliases.json", local)
    table = json.loads(raw)["data"]["camera"]["model"]
    out = {}
    for make, entries in table.items():
        for name, target in entries.items():
            out.setdefault(f"{target['make']} {target['model']}", []).append(
                f"{make} {name}")
    return out


def one(camera, out_dir, local=None):
    url = f"{BASE}camera/{camera}{STEM}"
    raw = get(url, local)
    digest = hashlib.sha256(raw).hexdigest()
    header, units, bands, channels = convert(raw)
    document = build(url, digest, header, units, bands, channels)
    path = out_dir / f"{camera}_ssf.json"
    path.write_text(json.dumps(document, indent=2) + "\n")
    verify(path, bands, channels)
    return path, document, bands


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true",
                       help=f"import all {len(GROUP_A)} group A cameras")
    group.add_argument("--camera", help="one ACES file stem, e.g. Nikon_D850")
    parser.add_argument("--input", help="read a local copy instead of fetching")
    parser.add_argument("--out-dir", default=str(DATA / "cameras"))
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cameras = GROUP_A if args.all else (args.camera,)

    alias_map = aliases() if args.all else {}
    index = []
    for camera in cameras:
        path, document, bands = one(camera, out_dir, args.input)
        index.append({
            "camera_name": document["camera_name"],
            "manufacturer": document["manufacturer"],
            "model": document["model"],
            "file": path.name,
            "exif_aliases": alias_map.get(document["camera_name"], []),
            "sha256": document["source"]["sha256"],
        })
        if not args.all:
            print(f"{path.name}: {len(bands)} bands {bands[0]}-{bands[-1]} nm, "
                  f"sha256 {document['source']['sha256'][:12]}, "
                  "engine round trip exact")

    if args.all:
        index.sort(key=lambda row: (row["manufacturer"], row["model"]))
        (out_dir / "index.json").write_text(json.dumps({
            "description": ("Camera spectral sensitivities in the key layout "
                            "the engines' CFA reader expects. Group A of the "
                            "ACES set: consumer interchangeable-lens bodies."),
            "notice": NOTICE,
            "generated_by": "engine/scan/aces_ssf_import.py --all",
            "count": len(index),
            "cameras": index,
        }, indent=2) + "\n")
        extra = sum(len(row["exif_aliases"]) for row in index)
        print(f"wrote {len(index)} camera files and index.json to {out_dir}, "
              f"{extra} EXIF aliases resolved, engine round trip exact on all")


if __name__ == "__main__":
    main()
