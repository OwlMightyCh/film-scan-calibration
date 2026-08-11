#!/usr/bin/env python3
"""raw_to_exr — trichrome scan frames -> half-float linear EXRs (single engine).

Merges exr_maker.py and exr_maker_fast.py (2026-07-18): one self-contained
file with the parallel scheduler built in. No sibling imports — a lone copy
of this file runs anywhere the dependencies (numpy, tifffile, rawpy,
OpenEXR; exiftool optional) are installed.

Modes (asked interactively, or --mode):
  pixelshift  full-resolution per-site RGB. Accepts Sony .ARQ pixel-shift
              composites (native decode, no demosaic) or RGB TIFFs
              (RawTherapee-compatibility path).
  superpixel  half-resolution 2x2 CFA binning. Accepts .DNG / .ARW.

Pipeline per R,G,B triplet (sorted by first number in filename; hidden
files ignored): decode -> linear float32 0-1 (black/white level normalized
where decoding raw) -> trichrome merge -> optional flat-field
(vignetting-only polynomial, fitted from a film-less triplet processed
through the same mode) -> horizontal flip (always on, silent) ->
ZIP-compressed half-float EXR with capture metadata (per-channel
exposure/ISO/f-number, source files, mode, flags) in the "capture_metadata"
header attribute. Half floats give ~constant 0.0002 D precision across the
4.5 corridor. No color space attribute, no ICC — data is linear sensor RGB.

Performance: triplets run in a process pool (--workers, default 4 — a
full-res pixel-shift frame costs ~2.5 GB of working set); all source EXIF
is read in one batched exiftool call. Compression stays ZIP (decision
2026-07-18; revisit with an uncompressed-vs-ZIP Resolve scrub test if
grading ever feels decode-bound).

Resolve import of this EXR flavor verified 2026-07-18 (linear values read
verbatim, no hidden transform).
"""
import argparse
import json
import re
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import tifffile as tiff
import OpenEXR

RAW_EXTS = (".dng", ".arw")
ARQ_EXTS = (".arq",)
TIFF_EXTS = (".tif", ".tiff")
MAX_WORKERS = {"pixelshift": 4, "superpixel": 4}


def sort_key(p: Path):
    nums = re.findall(r"\d+", p.stem)
    return (int(nums[0]) if nums else 10**18, p.name)


# ---------------------------------------------------------------- decoding

def read_tiff_rgb01(path: Path) -> np.ndarray:
    img = tiff.imread(str(path))
    if img.ndim != 3 or img.shape[2] < 3:
        raise RuntimeError(f"{path.name}: expected RGB TIFF, got shape {img.shape}")
    img = img[..., :3]
    if np.issubdtype(img.dtype, np.floating):
        return np.clip(img.astype(np.float32), 0.0, None)
    info = np.iinfo(img.dtype)
    return (img.astype(np.float32) / float(info.max))


def even_crop(m: np.ndarray) -> np.ndarray:
    h, w = m.shape[:2]
    return m[: h - (h % 2), : w - (w % 2)]


def cropped_visible_mosaic(raw):
    s = raw.sizes
    vis = raw.raw_image_visible.astype(np.int32)
    y0 = int(getattr(s, "top_margin", 0) or 0)
    x0 = int(getattr(s, "left_margin", 0) or 0)
    cl = int(getattr(s, "crop_left_margin", 0) or 0)
    ct = int(getattr(s, "crop_top_margin", 0) or 0)
    cw = int(getattr(s, "crop_width", 0) or 0)
    ch = int(getattr(s, "crop_height", 0) or 0)
    if cw > 0 and ch > 0:
        vis = vis[ct:ct + ch, cl:cl + cw]
        y0, x0 = y0 + ct, x0 + cl
    return even_crop(vis), y0, x0


def channel_coords(pattern2x2: np.ndarray):
    coords = {}
    for y in range(2):
        for x in range(2):
            coords.setdefault(int(pattern2x2[y, x]), []).append((y, x))
    if 0 not in coords or 2 not in coords:
        raise RuntimeError(f"Unexpected CFA pattern:\n{pattern2x2}")
    greens = coords.get(1, []) + coords.get(3, [])
    if len(greens) != 2:
        raise RuntimeError(f"Unexpected green sites in CFA pattern:\n{pattern2x2}")
    return coords[0][0], greens[0], greens[1], coords[2][0]


def read_superpixel_rgb01(path: Path) -> np.ndarray:
    """DNG/ARW mosaic -> half-res linear RGB via 2x2 binning (no demosaic)."""
    import rawpy
    with rawpy.imread(str(path)) as raw:
        mosaic, y0, x0 = cropped_visible_mosaic(raw)
        (ry, rx), (g1y, g1x), (g2y, g2x), (by, bx) = channel_coords(raw.raw_pattern)
        yoff, xoff = y0 & 1, x0 & 1

        def plane(cy, cx):
            return mosaic[(cy - yoff) & 1::2, (cx - xoff) & 1::2]

        bl = list(raw.black_level_per_channel) + [0] * 4
        white = int(raw.white_level)
        R = plane(ry, rx).astype(np.float32) - np.float32(bl[0])
        G = (plane(g1y, g1x).astype(np.float32) - np.float32(bl[1])) / np.float32(2) \
            + (plane(g2y, g2x).astype(np.float32) - np.float32(bl[1])) / np.float32(2)
        B = plane(by, bx).astype(np.float32) - np.float32(bl[2])
        out = np.stack([
            R / max(1, white - int(bl[0])),
            G / max(1, white - int(bl[1])),
            B / max(1, white - int(bl[2])),
        ], axis=-1).astype(np.float32)
        return np.clip(out, 0.0, None)


def read_arq_rgb01(path: Path) -> np.ndarray:
    """Sony pixel-shift composite -> full-res per-site linear RGB (no demosaic).

    LibRaw exposes ARQ as a 4-plane raw image (R, G1, B, G2 per site).
    UNTESTED against a real ARQ from this rig — verify plane order via
    raw_pattern on first use.
    """
    import rawpy
    with rawpy.imread(str(path)) as raw:
        img = raw.raw_image_visible
        if img.ndim != 3 or img.shape[2] != 4:
            raise RuntimeError(
                f"{path.name}: expected 4-plane pixel-shift raw, got shape "
                f"{img.shape}. If this is a single-shot file, use superpixel mode.")
        img = img.astype(np.float32)
        bl = list(raw.black_level_per_channel) + [0] * 4
        white = int(raw.white_level)
        R = img[..., 0] - np.float32(bl[0])
        G = (img[..., 1] - np.float32(bl[1])) / np.float32(2) \
            + (img[..., 3] - np.float32(bl[3])) / np.float32(2)
        B = img[..., 2] - np.float32(bl[2])
        out = np.stack([
            R / max(1, white - bl[0]),
            G / max(1, white - bl[1]),
            B / max(1, white - bl[2]),
        ], axis=-1).astype(np.float32)
        return np.clip(out, 0.0, None)


def make_reader(mode):
    def read(path: Path) -> np.ndarray:
        try:
            return _read_dispatch(path)
        except Exception as e:
            raise SystemExit(
                f"Failed to read {path.name}: {e}\n"
                f"(Common causes: a macOS '._' sidecar from an SD card, an "
                f"iCloud-offloaded placeholder, or a truncated copy.)")

    def _read_dispatch(path: Path) -> np.ndarray:
        ext = path.suffix.lower()
        if mode == "pixelshift":
            if ext in ARQ_EXTS:
                return read_arq_rgb01(path)
            if ext in TIFF_EXTS:
                return read_tiff_rgb01(path)
            raise RuntimeError(f"{path.name}: pixelshift mode accepts .arq/.tif")
        if ext in RAW_EXTS:
            return read_superpixel_rgb01(path)
        raise RuntimeError(f"{path.name}: superpixel mode accepts .dng/.arw")
    return read


# ------------------------------------------------- flat field (vignetting)

def _poly_design(xn, yn, degree):
    return np.stack([(xn ** i) * (yn ** j)
                     for i in range(degree + 1) for j in range(degree + 1 - i)],
                    axis=-1)


def fit_flat_model(flat2d, degree=4, subsample=4, robust_iters=1, clip_sigma=3.0):
    h, w = flat2d.shape
    Y, X = np.meshgrid(np.arange(0, h, subsample), np.arange(0, w, subsample),
                       indexing="ij")
    z = flat2d[Y, X].astype(np.float64).ravel()
    xn = X.ravel() / max(w - 1, 1) * 2 - 1
    yn = Y.ravel() / max(h - 1, 1) * 2 - 1
    A = _poly_design(xn, yn, degree)
    mask = np.isfinite(z) & (z > 0)
    coeffs = np.zeros(A.shape[1])
    for _ in range(robust_iters + 1):
        coeffs, *_ = np.linalg.lstsq(A[mask], z[mask], rcond=None)
        resid = z - A @ coeffs
        s = np.std(resid[mask])
        if s <= 0:
            break
        newmask = mask & (np.abs(resid) < clip_sigma * s)
        if newmask.sum() == mask.sum() or newmask.sum() < A.shape[1] * 4:
            break
        mask = newmask
    return coeffs, degree


def eval_flat_gain(coeffs, degree, h, w, max_gain=3.0, chunk_rows=256):
    """Evaluate the flat model in row chunks: the full-frame design matrix
    would be (h*w, 15) float64 — ~5 GB at pixel-shift resolution, the cause
    of the 2026-07-18 memory blow-up. Chunked float32 evaluation keeps the
    transient under ~100 MB with identical results at output precision."""
    model = np.empty((h, w), np.float32)
    xn_row = (np.arange(w, dtype=np.float32) / max(w - 1, 1) * 2 - 1)
    coeffs32 = coeffs.astype(np.float32)
    for y0 in range(0, h, chunk_rows):
        y1 = min(h, y0 + chunk_rows)
        yn = (np.arange(y0, y1, dtype=np.float32) / max(h - 1, 1) * 2 - 1)
        Yc, Xc = np.meshgrid(yn, xn_row, indexing="ij")
        design = _poly_design(Xc.ravel(), Yc.ravel(), degree)
        model[y0:y1] = (design @ coeffs32).reshape(y1 - y0, w)
    peak = float(np.nanmax(model))
    if peak <= 0:
        raise RuntimeError("Flat model peak <= 0; bad flat frame?")
    norm = np.clip(model / peak, 1.0 / max_gain, 1.0)
    return (1.0 / norm).astype(np.float32)


def report_gain(name, coeffs, degree, shape, max_gain=3.0):
    g = eval_flat_gain(coeffs, degree, *shape, max_gain=1e9)
    gmax = float(g.max())
    msg = f"   {name}: max corner gain x{gmax:.3f} ({np.log2(gmax):+.2f} stops)"
    capped = float((g > max_gain).mean()) * 100.0
    if capped > 0:
        msg += f"  [WARNING: {capped:.2f}% of pixels exceed x{max_gain:g} cap]"
    print(msg)


def build_flat_models(folder: Path, read):
    exts = ARQ_EXTS + TIFF_EXTS + RAW_EXTS
    flats = sorted((p for p in folder.iterdir()
                    if p.is_file() and p.suffix.lower() in exts
                    and not p.name.startswith(".")), key=sort_key)
    if len(flats) < 3:
        raise SystemExit(f"Need 3 flat frames in {folder} (found {len(flats)}).")
    flats = flats[:3]
    print(f"  Flat assignment:  R={flats[0].name}  G={flats[1].name}  B={flats[2].name}")
    models = []
    for idx, fp in enumerate(flats):
        chan = read(fp)[..., idx]
        coeffs, deg = fit_flat_model(chan)
        report_gain(fp.name, coeffs, deg, chan.shape)
        models.append((coeffs, deg))
    print()
    return models


def prompt_out_dir(in_dir: Path) -> Path:
    default = in_dir / "merged_trichrome_exr"
    raw = input(f"Export folder (Enter for {default}): ").strip()
    raw = raw.strip("'\"").replace("\\ ", " ").strip()
    if not raw:
        return default
    out = Path(raw).expanduser()
    if out.exists() and not out.is_dir():
        raise SystemExit(f"Not a folder: {out}")
    return out


def prompt_mode():
    while True:
        answer = input("Scan type — [p]ixel shift or [s]uperpixel? ").strip().lower()
        if answer in ("p", "pixelshift", "pixel shift"):
            return "pixelshift"
        if answer in ("s", "superpixel"):
            return "superpixel"
        print("  Please answer p or s.")


def prompt_flats():
    raw = input("Flats folder (Enter to skip flat-field correction): ").strip()
    raw = raw.strip("'\"").replace("\\ ", " ").strip()
    if not raw:
        print("  -> No flat-field correction.\n")
        return None
    folder = Path(raw).expanduser()
    if not folder.is_dir():
        raise SystemExit(f"Not a folder: {folder}")
    return folder



def batch_exif(paths):
    """{filename: {exposure_s, iso, f_number}} in one exiftool invocation."""
    if not paths:
        return {}
    try:
        out = subprocess.run(
            ["exiftool", "-j", "-n", "-ExposureTime", "-ISO", "-FNumber",
             *[str(p) for p in paths]],
            capture_output=True, text=True, check=True).stdout
        records = json.loads(out)
    except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError):
        return {str(p): dict(exposure_s=None, iso=None, f_number=None) for p in paths}
    result = {}
    for rec in records:
        result[str(Path(rec.get("SourceFile", "")).resolve())] = dict(
            exposure_s=rec.get("ExposureTime"), iso=rec.get("ISO"),
            f_number=rec.get("FNumber"))
    return {str(p): result.get(str(Path(p).resolve()),
                               dict(exposure_s=None, iso=None, f_number=None))
            for p in paths}


def check_exposures_batch(files, exif):
    by_channel = {0: set(), 1: set(), 2: set()}
    for i, p in enumerate(files):
        exp = exif[str(p)]["exposure_s"]
        if exp is not None:
            by_channel[i % 3].add(exp)
    for ch, name in zip(by_channel, "RGB"):
        if len(by_channel[ch]) > 1:
            print(f"WARNING: {name}-lit frames have inconsistent exposures "
                  f"{sorted(by_channel[ch])} — density scale will drift mid-roll.")


_GAIN_CACHE = {}


def merge_triplet(index, triplet, mode, flat_models, out_dir, exifs):
    """Worker: one triplet -> one EXR (float32 intermediates; flat gains
    cached per worker process and frame size)."""
    r_path, g_path, b_path = (Path(p) for p in triplet)
    read = make_reader(mode)
    r_img = read(r_path).astype(np.float32, copy=False)
    g_img = read(g_path).astype(np.float32, copy=False)
    b_img = read(b_path).astype(np.float32, copy=False)

    h = min(x.shape[0] for x in (r_img, g_img, b_img))
    w = min(x.shape[1] for x in (r_img, g_img, b_img))
    merged = np.stack([r_img[:h, :w, 0], g_img[:h, :w, 1], b_img[:h, :w, 2]],
                      axis=-1)
    del r_img, g_img, b_img

    if flat_models is not None:
        if (h, w) not in _GAIN_CACHE:
            _GAIN_CACHE[(h, w)] = np.stack(
                [eval_flat_gain(c, d, h, w) for c, d in flat_models], axis=-1)
        merged = merged * _GAIN_CACHE[(h, w)]

    merged = merged[:, ::-1, :]  # horizontal flip (always on, silent)

    description = json.dumps({
        "generator": "raw_to_exr.py",
        "kind": "trichrome_merge",
        "mode": mode,
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
    })

    out_path = Path(out_dir) / f"{index + 1:04d}.exr"
    header = {"compression": OpenEXR.ZIP_COMPRESSION,
              "type": OpenEXR.scanlineimage,
              "capture_metadata": description}
    with OpenEXR.File(header, {"RGB": merged.astype(np.float16)}) as f:
        f.write(str(out_path))
    return (index, f"[{index + 1:04d}] {r_path.name}+{g_path.name}+{b_path.name} "
                   f"-> {out_path.parent.name}/{out_path.name}  ({w}x{h}, half-float linear EXR)")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=("pixelshift", "superpixel"))
    parser.add_argument("--flats", help="flats folder path ('skip' = no correction)")
    parser.add_argument("--in-dir", default=".")
    parser.add_argument("--out-dir")
    parser.add_argument("--workers", type=int,
                        help="parallel workers (default 4; ~2.5 GB per worker on "
                             "full-res pixel-shift — drop to 2 or 1 if memory-tight)")
    args = parser.parse_args()

    in_dir = Path(args.in_dir).resolve()
    out_dir = Path(args.out_dir) if args.out_dir else prompt_out_dir(in_dir)
    mode = args.mode or prompt_mode()
    read = make_reader(mode)
    exts = (ARQ_EXTS + TIFF_EXTS) if mode == "pixelshift" else RAW_EXTS
    files = sorted((p for p in in_dir.iterdir()
                    if p.is_file() and p.suffix.lower() in exts
                    and not p.name.startswith(".")), key=sort_key)
    if len(files) < 3:
        from collections import Counter
        found = Counter(p.suffix.lower() for p in in_dir.iterdir()
                        if p.is_file() and not p.name.startswith("."))
        hint = ""
        other = (RAW_EXTS if mode == "pixelshift" else ARQ_EXTS + TIFF_EXTS)
        wrong_mode = sum(found.get(e, 0) for e in other)
        if wrong_mode >= 3:
            right = "superpixel" if mode == "pixelshift" else "pixelshift"
            hint = (f"\nThe folder holds {wrong_mode} file(s) the OTHER mode accepts "
                    f"— did you mean --mode {right}?")
        raise SystemExit(
            f"Need at least 3 scan frames ({'/'.join(exts)}) in {in_dir}.\n"
            f"Folder contents by extension: "
            f"{dict(found) if found else 'empty'}{hint}")

    if args.flats is None:
        flats_folder = prompt_flats()
    else:
        flats_folder = None if args.flats.lower() == "skip" else Path(args.flats).expanduser()
    flat_models = build_flat_models(flats_folder, read) if flats_folder else None

    exifs = batch_exif(files)
    check_exposures_batch(files, exifs)

    out_dir.mkdir(parents=True, exist_ok=True)
    groups, leftover = divmod(len(files), 3)
    if leftover:
        print(f"Warning: {leftover} leftover file(s) ignored (not a full R,G,B triplet).")

    workers = args.workers or MAX_WORKERS[mode]
    tasks = [(i, [str(p) for p in files[i * 3: i * 3 + 3]]) for i in range(groups)]
    done = 0
    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(merge_triplet, i, triplet, mode, flat_models,
                               str(out_dir), exifs) for i, triplet in tasks]
        for future in as_completed(futures):
            index, line = future.result()
            done += 1
            print(f"({done}/{groups}) {line}", flush=True)


if __name__ == "__main__":
    main()
