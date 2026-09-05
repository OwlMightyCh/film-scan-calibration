#!/usr/bin/env python3
"""mono_to_exr — trichrome scan frames from a MONOCHROME sensor -> linear EXRs.

The companion to raw_to_exr.py, which decodes colour sensors and is the engine
to use for any camera whose colour filter array is intact. The two are kept
apart deliberately. A monochrome frame is decoded by a different rule, and a
sensor with a stripped filter array cannot be told from an intact one by
anything recorded in the file, so the choice of engine is the operator's
declaration of which sensor took the frames. Nothing here can alter how a
colour frame decodes, and nothing in raw_to_exr.py has to account for this
case.

Which engine to use:

  raw_to_exr.py    a colour sensor with its filter array intact. Bayer mosaics
                   in --mode superpixel, pixel-shift composites and RGB TIFFs
                   in --mode pixelshift.
  mono_to_exr.py   a sensor with NO colour filter array, whether built that way
                   (Leica M Monochrom, Phase One Achromatic) or converted by
                   having the array stripped after manufacture.

WHY MONOCHROME NEEDS ITS OWN RULE. A sensor with no filter array measures one
quantity per site. There is therefore nothing to bin and nothing to assemble,
and the mode distinction that governs raw_to_exr.py does not apply: the frame
is read at FULL resolution in every case. The single plane is written to all
three channels, which leaves the trichrome merge correct without a special
case, since that merge takes channel 0 from the red exposure, 1 from the green
and 2 from the blue and finds the same measured value in each. A pixel-shift
composite is AVERAGED across its planes rather than indexed, every plane being
a measurement of the same quantity rather than of a different colour.

Decoding such a file through raw_to_exr.py instead gives a wrong result in one
of two ways. A camera that declares one colour is refused outright, its file
carrying no 2x2 pattern to bin. A converted body still declares its original
Bayer pattern, so it decodes silently at half resolution with the three
channels drawn from different sites, which is a channel misregistration with
no physical cause once the array is gone.

WHAT THIS ENGINE DOES NOT DO. It does not detect whether a sensor is
monochrome, and it does not refuse a file that declares a colour filter array,
because a converted body declares one and is exactly the case this engine
exists for. It reports what each file declares so that an engine chosen in
error is visible in the log rather than silent. Deciding the question from the
statistical similarity of the four sites would mean choosing a decode from
image content, which no part of this pipeline does.

Everything downstream of the decode — the flat-field model, the trichrome
merge, the horizontal flip, the EXR container and its capture metadata, the
parallel scheduler — is imported from raw_to_exr.py rather than copied, so the
two engines cannot drift apart on any of it. This file is therefore NOT a lone
copy that runs on its own; raw_to_exr.py must sit beside it.
"""
import argparse
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import OpenEXR

import raw_to_exr as rte


def is_declared_monochrome(raw) -> bool:
    """True when the FILE declares no colour filter array.

    A camera built without one reports a single colour. A converted body
    reports its original Bayer metadata and returns False here, which is not
    an error: it is why this engine takes the operator's word rather than the
    file's. Used for reporting only.

    The pattern is consulted only for a flat image. A stacked composite
    reports no pattern by construction, colour having already been resolved
    per site, so its absence says nothing about the filter array there.
    """
    if int(getattr(raw, "num_colors", 3) or 3) == 1:
        return True
    if raw.raw_image_visible.ndim == 3:
        return False
    return getattr(raw, "raw_pattern", None) is None


def declared(raw) -> str:
    """One line describing what the file claims, for the run log."""
    n = int(getattr(raw, "num_colors", 3) or 3)
    stacked = raw.raw_image_visible.ndim == 3
    if is_declared_monochrome(raw):
        return "declares 1 colour: a native monochrome sensor"
    shape = f"{raw.raw_image_visible.shape[2]}-plane composite" if stacked \
        else "Bayer mosaic"
    return (f"declares {n} colours as a {shape}: treated as a stripped filter "
            f"array on the operator's declaration")


def mono_rgb01(raw) -> np.ndarray:
    """Monochrome sensor -> FULL-resolution linear RGB, one plane replicated.

    A stack is averaged across its planes; a flat image is taken as it stands,
    cropped to the visible area but not rounded to an even size, there being
    no 2x2 phase to preserve.
    """
    img = raw.raw_image_visible
    bl = list(raw.black_level_per_channel) + [0] * 4
    white = int(raw.white_level)
    if img.ndim == 3:
        n = int(img.shape[2])
        m = np.mean([img[..., i].astype(np.float32) - np.float32(bl[i])
                     for i in range(n)], axis=0)
        black = sum(float(bl[i]) for i in range(n)) / n
    else:
        s = raw.sizes
        y0 = int(getattr(s, "top_margin", 0) or 0)
        x0 = int(getattr(s, "left_margin", 0) or 0)
        cl = int(getattr(s, "crop_left_margin", 0) or 0)
        ct = int(getattr(s, "crop_top_margin", 0) or 0)
        cw = int(getattr(s, "crop_width", 0) or 0)
        ch = int(getattr(s, "crop_height", 0) or 0)
        vis = img.astype(np.int32)
        if cw > 0 and ch > 0:
            vis = vis[ct:ct + ch, cl:cl + cw]
        m = vis.astype(np.float32) - np.float32(bl[0])
        black = float(bl[0])
    m = m / max(1.0, float(white) - black)
    return np.clip(np.repeat(m[..., None], 3, axis=2), 0.0, None).astype(np.float32)


def read_mono(path: Path, report=None) -> np.ndarray:
    """Decode one frame. Extension routing matches raw_to_exr's accepted set."""
    ext = path.suffix.lower()
    if ext in rte.TIFF_EXTS:
        raise RuntimeError(
            f"{path.name}: TIFF input is a colour path only; a monochrome "
            f"sensor is read from its raw file.")
    if ext not in rte.RAW_EXTS:
        raise RuntimeError(
            f"{path.name}: unsupported extension {ext}. Accepted: "
            f"{'/'.join(rte.RAW_EXTS)}.")
    import rawpy
    with rawpy.imread(str(path)) as raw:
        if report is not None:
            report(path, declared(raw))
        return mono_rgb01(raw)


def make_reader(verbose=False):
    seen = set()

    def report(path, text):
        if verbose and text not in seen:
            seen.add(text)
            print(f"  {path.name}: {text}", flush=True)

    def read(path: Path) -> np.ndarray:
        try:
            return read_mono(path, report)
        except Exception as e:
            raise SystemExit(
                f"Failed to read {path.name}: {e}\n"
                f"(If this sensor has an intact colour filter array, use "
                f"raw_to_exr.py instead.)")
    return read


_GAIN_CACHE = {}


def merge_triplet(index, triplet, flat_models, out_dir, exifs, role=None):
    """Worker: one triplet -> one EXR. The merge, flip and container are the
    colour engine's; only the decode differs. role="plain" writes the flat
    frames as plain.exr, as in the colour engine."""
    r_path, g_path, b_path = (Path(p) for p in triplet)
    read = make_reader()
    r_img = read(r_path).astype(np.float32, copy=False)
    g_img = read(g_path).astype(np.float32, copy=False)
    b_img = read(b_path).astype(np.float32, copy=False)

    h, w = rte.require_same_size([(r_path.name, r_img), (g_path.name, g_img),
                                  (b_path.name, b_img)])
    merged = np.stack([r_img[..., 0], g_img[..., 1], b_img[..., 2]], axis=-1)
    del r_img, g_img, b_img

    if flat_models is not None:
        if (h, w) not in _GAIN_CACHE:
            _GAIN_CACHE[(h, w)] = np.stack(
                [rte.eval_flat_gain(c, d, h, w) for c, d in flat_models], axis=-1)
        merged = merged * _GAIN_CACHE[(h, w)]

    merged = merged[:, ::-1, :]  # horizontal flip (always on, silent)

    description = json.dumps({
        "generator": "mono_to_exr.py",
        "kind": "trichrome_merge",
        "mode": "monochrome",
        "sensor": "no colour filter array (operator declaration)",
        "source_files": {ch: p.name for ch, p in
                         zip("RGB", (r_path, g_path, b_path))},
        "exposure_s": {ch: exifs[str(p)]["exposure_s"] for ch, p in
                       zip("RGB", (r_path, g_path, b_path))},
        "iso": {ch: exifs[str(p)]["iso"] for ch, p in
                zip("RGB", (r_path, g_path, b_path))},
        "f_number": {ch: exifs[str(p)]["f_number"] for ch, p in
                     zip("RGB", (r_path, g_path, b_path))},
        "flat_field_applied": flat_models is not None,
        "horizontal_flip": True,
        "values": "linear, black-subtracted, normalized to white level",
        **({"role": role} if role else {}),
    })

    label = role if role else f"{index + 1:04d}"
    out_path = Path(out_dir) / f"{label}.exr"
    header = {"compression": OpenEXR.ZIP_COMPRESSION,
              "type": OpenEXR.scanlineimage,
              "capture_metadata": description}
    with OpenEXR.File(header, {"RGB": merged.astype(np.float16)}) as f:
        f.write(str(out_path))
    return (index, f"[{label}] {r_path.name}+{g_path.name}+{b_path.name} "
                   f"-> {out_path.parent.name}/{out_path.name}  "
                   f"({w}x{h}, half-float linear EXR)")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--flats", nargs=3, metavar=("R", "G", "B"),
                        help="the three flat frames (no film in the gate), one "
                             "per channel in R, G, B order")
    parser.add_argument("--no-flats", action="store_true",
                        help="skip flat-field correction without prompting")
    parser.add_argument("--in-dir", default=".")
    parser.add_argument("--out-dir")
    parser.add_argument("--workers", type=int,
                        help="parallel workers (default 4)")
    args = parser.parse_args()

    in_dir = Path(args.in_dir).resolve()
    out_dir = Path(args.out_dir) if args.out_dir else rte.prompt_out_dir(in_dir)
    read = make_reader(verbose=True)
    flats = rte.resolve_flats_args(args)
    files = rte.list_scan_frames(in_dir, rte.RAW_EXTS, flats)
    if len(files) < 3:
        from collections import Counter
        found = Counter(p.suffix.lower() for p in in_dir.iterdir()
                        if p.is_file() and not p.name.startswith("."))
        raise SystemExit(
            f"Need at least 3 scan frames ({'/'.join(rte.RAW_EXTS)}) in {in_dir}.\n"
            f"Folder contents by extension: {dict(found) if found else 'empty'}")

    print(f"Reading {len(files)} frames as monochrome:")
    flat_models = rte.build_flat_models(flats, read) if flats else None

    exifs = rte.batch_exif(files + list(flats or []))
    rte.check_exposures_batch(files, exifs)

    out_dir.mkdir(parents=True, exist_ok=True)
    groups, leftover = divmod(len(files), 3)
    if leftover:
        print(f"Warning: {leftover} leftover file(s) ignored (not a full R,G,B triplet): "
              f"{', '.join(p.name for p in files[groups * 3:])}")
    rte.print_triplets(files, groups, flats)

    workers = args.workers or 4
    tasks = [(i, [str(p) for p in files[i * 3: i * 3 + 3]], None) for i in range(groups)]
    if flats:
        tasks.append((groups, [str(p) for p in flats], rte.PLAIN_NAME))
    done = 0
    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(merge_triplet, i, triplet, flat_models,
                               str(out_dir), exifs, role) for i, triplet, role in tasks]
        for future in as_completed(futures):
            index, line = future.result()
            done += 1
            print(f"({done}/{len(tasks)}) {line}", flush=True)


if __name__ == "__main__":
    main()
