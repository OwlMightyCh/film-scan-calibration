#!/usr/bin/env python3
"""raw_to_exr — trichrome scan frames -> half-float linear EXRs (single engine).

Merges exr_maker.py and exr_maker_fast.py (2026-07-18): one self-contained
file with the parallel scheduler built in. No sibling imports — a lone copy
of this file runs anywhere the dependencies (numpy, tifffile, rawpy,
OpenEXR, matplotlib for the anchor's ROI picker; exiftool optional) are
installed.

Modes (asked interactively, or --mode):
  pixelshift  full-resolution per-site RGB. Accepts any raw LibRaw reports as
              a stack of planes, which covers Sony .ARQ pixel-shift composites
              and the linear .DNG that Adobe's converter produces from a Nikon
              pixel-shift merge, or RGB TIFFs (RawTherapee-compatibility path).
  superpixel  half-resolution 2x2 CFA binning. Accepts any single-shot Bayer
              raw: .DNG, .ARW, .CR2, .CR3, .NEF, .NRW, .RAF.

A file is routed by what LibRaw reports it to be rather than by its extension,
because one extension can be either: a .dng may hold a Bayer mosaic or a
per-site composite. The same is true of .RAF between camera lines: the GFX
bodies are 2x2 Bayer and decode on the superpixel path (verified against a
real GFX 100 16-bit lossless-compressed RAF: pattern RGBG with the two greens
on separate indices, black 256, white 65535), while the X-series bodies are
X-Trans. Two formats are outside the design. X-Trans sensors have no 2x2 CFA,
so binning has no meaning on them and they are refused. Canon sRAW and mRAW
are stacked like a composite but carry subsampled chroma, so no per-site RGB
exists in them; they are refused with that explanation.

Fujifilm's Pixel Shift Multi-Shot does not write a composite raw either: the
sixteen RAFs merge in Fujifilm Pixel Shift Combiner to a DNG, which this
engine accepts on the stack path the same way it accepts Adobe's linear DNG of
a Nikon merge — accepted by structure, untested against a real file.

Canon writes no pixel-shift raw at all: the EOS R5's IBIS High Resolution Shot
emits a 400 MP JPEG only, and the R5 Mark II dropped the mode. Nikon's pixel
shift merges in NX Studio to .NEFX, which LibRaw does not read; converting it
with Adobe DNG Converter yields a linear DNG this engine accepts.

Pipeline per R,G,B triplet (sorted by the LAST number in the filename, the
frame counter; named flat frames excluded by content; hidden
files ignored): decode -> linear float32 0-1 (black/white level normalized
where decoding raw) -> trichrome merge -> optional flat-field
(vignetting-only polynomial, fitted from three film-less frames, one per
channel, given as explicit R, G, B paths) -> roll anchor (each channel x
10^dmin_exr_scale) -> horizontal flip (always on, silent) -> ZIP-compressed half-float EXR with capture metadata
(per-channel exposure/ISO/f-number, source files, mode, flags, the anchor's
gains) in the "capture_metadata" header attribute. Half floats give
~constant 0.0002 D precision across the 4.5 corridor. No color space
attribute, no ICC — data is linear sensor RGB.

Roll folder: the program asks for a roll name (--roll answers without
prompting). The frames go to <scan folder>/<roll>/, the roll ID is the roll
name, and the anchor record is <roll>/<roll>.json. --out-dir names the folder
outright; the roll ID is then its name unless --roll gives one. A folder that
already holds a run (EXRs, anchor records) is replaced only after a y. The
new roll and its JSON are written into a hidden staging folder and replace
the earlier run's EXRs and anchor records as one set once every frame is
written; a failure before that leaves the folder as it was. Other files in
the folder stay.

Roll anchor: every roll has a Dmin frame: the light-struck clear leader of a
reversal roll, the unexposed rebate or a frame gap of a negative. After the
frame listing the program asks the film family, the Dmin frame (Enter = 0001)
and an optional Dmax frame (Enter = none); --film-family, --dmin-frame N and
--dmax-frame N (0 = none) answer without prompting. While a frame number is
asked, a contact sheet window shows every frame numbered and oriented as
written, from each frame's G capture (the raw's embedded preview, or a
log-scaled sample of its pixels). The Dmin frame, the Dmax
frame and plain.exr merge first, unanchored, into a hidden scratch folder in the roll folder. One
ROI picker per frame set (log-scaled preview, live per-channel histogram,
bimodality verdict) sets the measured box, and the measurement gives
dmin_exr_scale, the D-min against the sensor white level. The
plain-light-scale `dmin` is never used. The whole roll, plain.exr included,
then merges with each channel multiplied by 10^dmin_exr_scale before the
half-float write, so the film base reads 1.0 and every pixel is rounded once.
The header records the gains under roll_anchor; the anchor JSON holds the
measurement, the ROI boxes and a baked_into_exrs block. A Dmin channel
without a finite positive mean is refused (the measurement floors a zero mean
to Dmin 30, a gain of 1e30); a measurement carrying warnings is baked only
after a y; a frame with any pixel that half float cannot hold is refused
before it is written.

mono_to_exr.py imports the roll folder, the anchor and the scheduler from
this file, so both converters behave alike.

Performance: triplets run in a process pool (--workers, default 4 — a
full-res pixel-shift frame costs ~2.5 GB of working set); all source EXIF
is read in one batched exiftool call. Compression stays ZIP (decision
2026-07-18; revisit with an uncompressed-vs-ZIP Resolve scrub test if
grading ever feels decode-bound).

Resolve import of this EXR flavor verified 2026-07-18 (linear values read
verbatim, no hidden transform).
"""
import argparse
import datetime
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import tifffile as tiff
import OpenEXR

RAW_EXTS = (".dng", ".arw", ".arq", ".cr2", ".cr3", ".nef", ".nrw", ".raf")
TIFF_EXTS = (".tif", ".tiff")
MAX_WORKERS = {"pixelshift": 4, "superpixel": 4}


def sort_key(p: Path):
    """Order by the LAST number in the stem, the position a camera's frame
    counter occupies. The first number is the wrong one: a Capture One
    export named C1翻拍文件2115 leads with the 1 of "C1", so every frame ties
    and the order falls to a string sort, and a stray 1.ARW lands in front
    of the roll. Files with no number sort last."""
    nums = re.findall(r"\d+", p.stem)
    return (int(nums[-1]) if nums else 10**18, p.name)


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


def channel_coords(pattern2x2):
    pattern2x2 = np.asarray(pattern2x2) if pattern2x2 is not None else None
    if pattern2x2 is None or pattern2x2.shape != (2, 2):
        raise RuntimeError(
            "No 2x2 CFA pattern: this file is not a Bayer mosaic. X-Trans "
            "sensors report a 6x6 pattern and are not supported, because 2x2 "
            "binning has no meaning on them.")
    coords = {}
    for y in range(2):
        for x in range(2):
            coords.setdefault(int(pattern2x2[y, x]), []).append((y, x))
    if 0 not in coords or 2 not in coords:
        raise RuntimeError(f"Unexpected CFA pattern:\n{pattern2x2}")
    greens = [(1, c) for c in coords.get(1, [])] + [(3, c) for c in coords.get(3, [])]
    if len(greens) != 2:
        raise RuntimeError(f"Unexpected green sites in CFA pattern:\n{pattern2x2}")
    # The colour INDEX travels with each site, because the two green sites are
    # usually indices 1 and 3 and carry separate black levels — but a camera
    # reporting both greens as index 1 must then use bl[1] for both. Reading
    # the index off the pattern is the only way to get that right for either.
    return ((0, coords[0][0]), greens[0], greens[1], (2, coords[2][0]))


def superpixel_rgb01(raw) -> np.ndarray:
    """Bayer mosaic -> half-res linear RGB via 2x2 binning (no demosaic).

    Mosaic, CFA pattern and levels all come from LibRaw, so this is
    independent of manufacturer. Verified against real Canon CR3, Nikon NEF,
    Pentax DNG and Sony ARW files.
    """
    mosaic, y0, x0 = cropped_visible_mosaic(raw)
    (ri, (ry, rx)), (g1i, (g1y, g1x)), (g2i, (g2y, g2x)), (bi, (by, bx)) = \
        channel_coords(raw.raw_pattern)
    yoff, xoff = y0 & 1, x0 & 1

    def plane(cy, cx):
        return mosaic[(cy - yoff) & 1::2, (cx - xoff) & 1::2]

    bl = list(raw.black_level_per_channel) + [0] * 4
    white = int(raw.white_level)
    R = plane(ry, rx).astype(np.float32) - np.float32(bl[ri])
    G = (plane(g1y, g1x).astype(np.float32) - np.float32(bl[g1i])) / np.float32(2) \
        + (plane(g2y, g2x).astype(np.float32) - np.float32(bl[g2i])) / np.float32(2)
    B = plane(by, bx).astype(np.float32) - np.float32(bl[bi])
    # The green plane is the mean of two sites, so its normalisation must use
    # the mean of their black levels; the two agree on most cameras and differ
    # by a count or two on some.
    bl_g = (float(bl[g1i]) + float(bl[g2i])) / 2.0
    out = np.stack([
        R / max(1, white - int(bl[ri])),
        G / max(1.0, white - bl_g),
        B / max(1, white - int(bl[bi])),
    ], axis=-1).astype(np.float32)
    return np.clip(out, 0.0, None)


def stack_kind(raw):
    """'quad', 'linear', or None if the stack is not a per-site composite."""
    image = raw.raw_image_visible
    if image.ndim != 3:
        return None
    planes, colours = image.shape[2], int(raw.num_colors)
    if planes == 4 and colours == 4:
        return "quad"
    if planes == 3:
        return "linear"
    return None


def stack_rgb01(path: Path, raw) -> np.ndarray:
    """Pixel-shift composite -> full-res per-site linear RGB (no demosaic).

    LibRaw reports these as a stacked raw image with one plane per colour.
    Sony's ARQ carries four planes, R, G1, B and G2 per site; that layout and
    this plane order are verified against a real a7R III ARQ, whose channels
    correlate 1.0000, 0.9998 and 1.0000 with LibRaw's own decode of the same
    file, at unit scale. A three-plane stack is a linear DNG, one RGB triple
    per site, which is what Adobe's converter produces from a Nikon pixel-shift
    merge.
    """
    kind = stack_kind(raw)
    if kind is None:
        planes, colours = raw.raw_image_visible.shape[2], int(raw.num_colors)
        raise RuntimeError(
            f"{path.name}: a {planes}-plane raw declaring {colours} colours is "
            f"not a pixel-shift composite. Canon sRAW and mRAW present this "
            f"way and carry subsampled chroma, so no per-site RGB exists in "
            f"them; reshoot in full-size RAW.")
    img = raw.raw_image_visible
    bl = list(raw.black_level_per_channel) + [0] * 4
    white = int(raw.white_level)
    img = img.astype(np.float32)
    if kind == "quad":
        R = img[..., 0] - np.float32(bl[0])
        G = (img[..., 1] - np.float32(bl[1])) / np.float32(2) \
            + (img[..., 3] - np.float32(bl[3])) / np.float32(2)
        B = img[..., 2] - np.float32(bl[2])
    else:
        R = img[..., 0] - np.float32(bl[0])
        G = img[..., 1] - np.float32(bl[1])
        B = img[..., 2] - np.float32(bl[2])
    # A quad stack's green is the mean of two planes, so its normalisation
    # uses the mean of their black levels, as the superpixel path does; with
    # bl[1] alone a white-level input decoded to G < 1 whenever the two
    # greens' black levels differed.
    bl_g = (float(bl[1]) + float(bl[3])) / 2.0 if kind == "quad" else float(bl[1])
    out = np.stack([
        R / max(1, white - int(bl[0])),
        G / max(1.0, white - bl_g),
        B / max(1, white - int(bl[2])),
    ], axis=-1).astype(np.float32)
    return np.clip(out, 0.0, None)


def require_same_size(named_images):
    """Refuse a triplet whose captures differ in size, naming each file.

    Cropping to the smallest frame would produce a plausible EXR whose
    channels are misregistered by the size difference, with nothing to show
    it; a differing size means a capture from another body, mode or crop got
    into the sequence. Returns (h, w) when all agree."""
    sizes = {name: tuple(img.shape[:2]) for name, img in named_images}
    if len(set(sizes.values())) != 1:
        detail = ", ".join(f"{name} {w}x{h}" for name, (h, w) in sizes.items())
        raise SystemExit(
            f"Captures in one triplet differ in size ({detail}): a mixed "
            f"capture, mode or crop. Not merged; every frame of a roll must "
            f"come from one body in one mode.")
    return next(iter(sizes.values()))


def read_raw_rgb01(path: Path, mode: str) -> np.ndarray:
    """Decode by what the file IS, rather than by its extension.

    LibRaw reports a single-shot mosaic as a two-dimensional image and a
    pixel-shift composite as a stack of planes, so the mode a file belongs to
    is a property of its contents. One extension can be either: a .dng may hold
    a Bayer mosaic or a per-site composite.
    """
    import rawpy
    with rawpy.imread(str(path)) as raw:
        stacked = raw.raw_image_visible.ndim == 3
        if mode == "pixelshift" and not stacked:
            raise RuntimeError(
                f"{path.name}: single-shot mosaic, not a pixel-shift "
                f"composite. Use --mode superpixel.")
        if mode == "superpixel" and stacked:
            if stack_kind(raw) is None:
                return stack_rgb01(path, raw)      # raises, naming the cause
            raise RuntimeError(
                f"{path.name}: per-site composite, not a single-shot mosaic. "
                f"Use --mode pixelshift.")
        return stack_rgb01(path, raw) if stacked else superpixel_rgb01(raw)


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
        if ext in TIFF_EXTS:
            if mode != "pixelshift":
                raise RuntimeError(
                    f"{path.name}: TIFF input belongs to pixelshift mode.")
            return read_tiff_rgb01(path)
        if ext in RAW_EXTS:
            return read_raw_rgb01(path, mode)
        raise RuntimeError(
            f"{path.name}: unsupported extension {ext}. Accepted: "
            f"{'/'.join(RAW_EXTS + TIFF_EXTS)}.")
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


def build_flat_models(flats, read):
    """flats: the R, G, B flat frames as three explicit paths, in that order.
    Each is a capture with no film in the gate under the matching light, and
    channel idx of frame idx is what the model is fitted to."""
    flats = [Path(p).expanduser() for p in flats]
    if len(flats) != 3:
        raise SystemExit(f"Need exactly 3 flat frames (R, G, B); got {len(flats)}.")
    for ch, fp in zip("RGB", flats):
        if not fp.is_file():
            raise SystemExit(f"{ch} flat frame is not a file: {fp}")
    print(f"  Flat assignment:  R={flats[0].name}  G={flats[1].name}  B={flats[2].name}")
    models = []
    for idx, fp in enumerate(flats):
        chan = read(fp)[..., idx]
        coeffs, deg = fit_flat_model(chan)
        report_gain(fp.name, coeffs, deg, chan.shape)
        models.append((coeffs, deg))
    print()
    return models


def clean_path_input(raw: str) -> str:
    """Strip the quoting and escaped spaces a drag-and-drop path arrives with."""
    return raw.strip().strip("'\"").replace("\\ ", " ").strip()


def prompt_mode():
    while True:
        answer = input("Scan type — [p]ixel shift or [s]uperpixel? ").strip().lower()
        if answer in ("p", "pixelshift", "pixel shift"):
            return "pixelshift"
        if answer in ("s", "superpixel"):
            return "superpixel"
        print("  Please answer p or s.")


def prompt_flats():
    """Ask for the R, G, B flat frames one at a time.

    Enter at the first prompt skips flat-field correction. Once a red frame
    is given the other two are required, since a partial set cannot be
    fitted; an empty answer there re-asks. Returns None or three Paths.
    """
    raw = clean_path_input(
        input("Red flat frame (Enter to skip flat-field correction): "))
    if not raw:
        print("  -> No flat-field correction.\n")
        return None
    flats = [Path(raw).expanduser()]
    for name in ("Green", "Blue"):
        while True:
            raw = clean_path_input(input(f"{name} flat frame: "))
            if raw:
                break
            print(f"  A {name.lower()} flat frame is required once a red one is given.")
        flats.append(Path(raw).expanduser())
    for ch, fp in zip("RGB", flats):
        if not fp.is_file():
            raise SystemExit(f"{ch} flat frame is not a file: {fp}")
    return flats


def resolve_flats_args(args):
    """--no-flats skips; --flats R G B names the frames; neither prompts.
    Returns None or a list of three paths."""
    if args.no_flats and args.flats:
        raise SystemExit("--flats and --no-flats are mutually exclusive.")
    if args.no_flats:
        return None
    if args.flats is None:
        return prompt_flats()
    return [Path(p).expanduser() for p in args.flats]


def _file_digest(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_flat_frame(p: Path, flats) -> bool:
    """True if p IS one of the flat frames, by content rather than path: a
    flat copied into the roll folder under the same or another name is the
    same capture. Size is compared first, so only a size match is hashed."""
    p = p.resolve()
    for fp in flats:
        fp = Path(fp).expanduser().resolve()
        if fp == p:
            return True
        if fp.stat().st_size == p.stat().st_size and \
                _file_digest(fp) == _file_digest(p):
            return True
    return False


def list_scan_frames(in_dir: Path, exts, flats=None):
    """Scan frames in R, G, B, R, G, B ... order (see sort_key), hidden files
    ignored. The flat frames are excluded wherever they sit and whatever they
    are called, because a flat is never a scan frame and one lying in the
    roll folder would otherwise shift every triplet after it."""
    files = sorted((p for p in in_dir.iterdir()
                    if p.is_file() and p.suffix.lower() in exts
                    and not p.name.startswith(".")), key=sort_key)
    if not flats:
        return files
    dropped = [p for p in files if is_flat_frame(p, flats)]
    if dropped:
        print(f"  Excluded from the scan sequence (flat frames): "
              f"{', '.join(p.name for p in dropped)}")
    return [p for p in files if p not in dropped]


def counter_stride(counters):
    """The step a camera's frame counter takes between consecutive captures
    of this roll: the most common positive difference, the smallest on a
    tie. It is 1 on a single-shot roll. A pixel-shift composite is built from
    several frames and the counter advances once per frame, so a Sony ARQ
    roll steps by 4 and a sixteen-frame merge by 16. Deletions cannot win
    the vote unless more captures were removed than kept."""
    steps = [b - a for a, b in zip(counters, counters[1:]) if b > a]
    if not steps:
        return 1
    counts = {}
    for st in steps:
        counts[st] = counts.get(st, 0) + 1
    return min(counts, key=lambda st: (-counts[st], st))


def counter_gaps(files, counters):
    """(stride, problems, gaps) for a counter sequence: problems are repeated
    counters and refuse the run; gaps are jumps that break the roll's stride
    and are only warned about."""
    stride = counter_stride(counters)
    problems = []
    gaps = []
    for i in range(1, len(files)):
        prev, cur = files[i - 1], files[i]
        jump = counters[i] - counters[i - 1]
        if jump == stride:
            continue
        if jump == 0:
            problems.append(f"{prev.name} and {cur.name} share frame counter "
                            f"{counters[i]}: two files for one capture")
            continue
        where = (f"at a triplet boundary, before triplet {i // 3 + 1}"
                 if i % 3 == 0 else
                 f"inside triplet {i // 3 + 1}, between its "
                 f"{'RGB'[i % 3 - 1]} and {'RGB'[i % 3]} files")
        if jump > 0 and jump % stride == 0:
            missing = jump // stride - 1
            what = f"{missing} capture(s) skipped"
        else:
            what = f"jump of {jump} is not a multiple of the stride {stride}"
        gaps.append(f"{what} between {prev.name} and {cur.name} "
                    f"({counters[i - 1]} -> {counters[i]}), {where}")
    return stride, problems, gaps


def check_sequence(files):
    """Refuse a file list that cannot be R, G, B triplets throughout, and
    return the triplet count.

    A count that is not a multiple of three means a capture is missing or a
    stray file is present; wherever that sits, every triplet after it takes
    its channels from the wrong captures, so nothing is written. When every
    file carries a frame counter (the last number in its stem, the sort key)
    the counters are checked too. A repeated counter is two files for one
    capture (a raw and its DNG, say) and is refused. The counter is expected
    to advance by the roll's stride (see counter_stride): 1 on a single-shot
    roll, 4 on a Sony ARQ roll whose every composite consumes four frame
    numbers. A jump that breaks the stride is only WARNED about, never
    refused: a gap in the numbering is as often a deliberate deletion (a
    spoiled capture and its reshoot removed by hand) as a genuinely missing
    frame, and the file list alone cannot tell the two apart. The warning
    says whether the gap sits on a triplet boundary, and the triplet listing
    printed after it is where the assignment is confirmed by eye. Counters
    that all tie carry no information and are not checked; a file with no
    number ends the check the same way.
    """
    groups, leftover = divmod(len(files), 3)
    if leftover:
        raise SystemExit(
            f"{len(files)} scan frames is not a whole number of R, G, B "
            f"triplets ({leftover} left over). A capture is missing or a stray "
            f"file is present, and every triplet after it would merge the "
            f"wrong channels; nothing written. Last file(s) in the sequence: "
            f"{', '.join(p.name for p in files[-3:])}")
    nums = [re.findall(r"\d+", p.stem) for p in files]
    if not all(nums) or len(files) < 2:
        return groups
    counters = [int(n[-1]) for n in nums]
    if len(set(counters)) == 1:
        return groups
    stride, problems, gaps = counter_gaps(files, counters)
    if problems:
        raise SystemExit("Frame counters do not form an unbroken R, G, B "
                         "sequence; nothing written.\n  " + "\n  ".join(problems))
    if gaps:
        print(f"Warning: frame counters break the roll's stride of {stride}. "
              "Deleted captures leave the triplets aligned; captures that "
              "never landed would shift them. Confirm the R, G, B assignment "
              "listed below.\n  " + "\n  ".join(gaps))
    return groups


def print_triplets(files, groups, flats=None):
    """Show the R, G, B assignment before any merge runs, so a shifted
    sequence is caught by eye rather than discovered in the output."""
    print(f"  {groups} triplet(s):")
    for i in range(groups):
        r, g, b = files[i * 3: i * 3 + 3]
        print(f"    [{i + 1:04d}]  R={r.name}  G={g.name}  B={b.name}")
    if flats:
        r, g, b = (Path(p) for p in flats)
        print(f"    [{PLAIN_NAME}]  R={r.name}  G={g.name}  B={b.name}  "
              f"(flat frames merged as {PLAIN_NAME}.exr)")
    print()


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


PLAIN_NAME = "plain"


VALUES_LINEAR = "linear, black-subtracted, normalized to white level"
VALUES_ANCHORED = (VALUES_LINEAR + ", then multiplied by 10^dmin_exr_scale per "
                   "channel (film base = 1.0)")
BAKED_DMIN_NOTE = (
    "density vs sensor white level, matching raw_to_exr normalization, measured "
    "on the unanchored Dmin frame. Baked into every EXR of this roll "
    "(x 10^dmin_exr_scale per channel, film base = 1.0), so re-measuring a "
    "baked frame reads about 0. Valid only if the dmin frame was shot at the "
    "roll's per-channel exposure and at the same ISO")
BAKED_BLOCK_NOTE = (
    "dmin_exr_scale is applied to every EXR in this folder (film base = 1.0).")


def roll_name_problem(name: str):
    if not name:
        return "a roll name is required"
    if "/" in name or name.startswith("."):
        return f"{name!r} is not one folder name (no '/', no leading '.')"
    return None


def prompt_roll_name(parent) -> str:
    while True:
        name = input(f"Roll name (folder under {parent}): ").strip()
        problem = roll_name_problem(name)
        if problem is None:
            return name
        print(f"  {problem[0].upper()}{problem[1:]}.")


def anchor_records(folder: Path):
    """The anchor JSONs in folder: every .json holding dmin_exr_scale. A note
    or an unparseable file is not one and stays where it is."""
    found = []
    for p in sorted(folder.glob("*.json")):
        try:
            if "dmin_exr_scale" in json.loads(p.read_text()):
                found.append(p)
        except (ValueError, TypeError, OSError):
            pass
    return found


def resolve_roll(args, parent):
    """(out_dir, roll_id, the earlier run's EXRs and anchor records). A folder
    that already holds a run is replaced only after a y: a roll name typed
    twice would otherwise overwrite a finished roll without a word. An
    earlier anchor record under another name is part of that run: left
    beside baked frames, a tool reading the folder's JSON would anchor them
    twice."""
    if args.roll and roll_name_problem(args.roll):
        raise SystemExit(f"--roll: {roll_name_problem(args.roll)}.")
    if args.out_dir:
        out_dir = Path(args.out_dir).expanduser()
        roll_id = args.roll or out_dir.name
    else:
        roll_id = args.roll or prompt_roll_name(parent)
        out_dir = parent / roll_id
    if out_dir.exists() and not out_dir.is_dir():
        raise SystemExit(f"Not a folder: {out_dir}")
    exrs = sorted(out_dir.glob("*.exr")) if out_dir.is_dir() else []
    records = anchor_records(out_dir) if out_dir.is_dir() else []
    if exrs or records:
        answer = input(
            f"{out_dir} already holds a run: {len(exrs)} EXR file(s), "
            f"{len(records)} anchor record(s) "
            f"({', '.join(p.name for p in records) or 'none'}). Replace that "
            f"run? It is replaced as one set once the new roll is complete. "
            f"[y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            raise SystemExit("Nothing written.")
    return out_dir, roll_id, exrs + records


def prompt_film_family() -> str:
    while True:
        answer = input("Film family — [n]egative or [r]eversal? ").strip().lower()
        if answer in ("n", "negative"):
            return "negative"
        if answer in ("r", "reversal"):
            return "reversal"
        print("  Please answer n or r.")


# The anchor patches per film family: (Dmin patch, Dmax patch).
FAMILY_PATCHES = {
    "reversal": ("light-struck clear leader", "unexposed rebate / frame gap"),
    "negative": ("unexposed rebate / frame gap, orange mask",
                 "light-struck leader tip"),
}


def measure_anchor(frame_dir, json_path, roll_id, family, dmin_idx,
                   dmax_idx, has_plain):
    """The anchor measurement: exposures, then one ROI picker per frame set in
    the order plain, Dmin, Dmax (each box is offered to the next), then
    run_extraction, which writes json_path and returns the record. The frames
    are the unanchored ones in frame_dir."""
    sets = {"plain": [str(frame_dir / f"{PLAIN_NAME}.exr")] if has_plain else None,
            "dmin": [str(frame_dir / f"{dmin_idx + 1:04d}.exr")],
            "dmax": ([str(frame_dir / f"{dmax_idx + 1:04d}.exr")]
                     if dmax_idx is not None else None)}
    for name in sets:
        sets[name] = ensure_exposures(name, sets[name])
    rois, prev = {}, None
    for name, frame_args in sets.items():
        if frame_args is None:
            continue
        rois[name] = pick_roi_for_frame(name, frame_args, prev)
        prev = rois[name]
        print(f"  {name} ROI confirmed: x {rois[name][0]}-{rois[name][2]} "
              f"y {rois[name][1]}-{rois[name][3]}")
    return run_extraction(sets["plain"], sets["dmin"], sets["dmax"],
                              roll_id, json_path, rois=rois, film_family=family)


# The gain is applied in float32; 10^d overflows it at d >= 38.53.
FLOAT32_LOG10_MAX = math.log10(float(np.finfo(np.float32).max))


def _finite_number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def anchor_from_record(record, json_name):
    """The bake: each channel multiplied by 10^dmin_exr_scale, so that the film
    base reads 1.0. dmin_exr_scale is the EXR-scale D-min, measured against the
    white level these files are normalised to; the plain-light `dmin` is a
    different scale and is never read here.

    A measurement that cannot be a film base is refused before anything is
    written: a channel whose Dmin patch mean (white_frac) is not a finite
    positive fraction of white, or whose density or gain is not finite. The
    measurement floors a zero mean to 1e-30, reports Dmin 30 with no warning, and
    that would bake a gain of 1e30 (inf in half float)."""
    frame = record["frames"]["dmin"]
    problems = []
    for ch in "RGB":
        white_frac = frame[ch].get("white_frac")
        dmin = record["dmin_exr_scale"][ch]
        if not (_finite_number(white_frac) and white_frac > 0
                and _finite_number(dmin) and dmin < FLOAT32_LOG10_MAX):
            problems.append(f"{ch} patch mean {white_frac!r} of white, "
                            f"Dmin {dmin!r}")
    if problems:
        raise SystemExit(
            "The Dmin measurement is not a film base: "
            + "; ".join(problems) + f" (ROI {frame['R'].get('roi_px')} in "
            f"{frame['R'].get('file')}). A channel with no signal in the ROI "
            f"(gate edge, holder, a dark area) cannot anchor the roll. Nothing "
            f"written; any earlier run is untouched. Re-run and select the "
            f"clear base.")
    dmin = {ch: float(record["dmin_exr_scale"][ch]) for ch in "RGB"}
    return {"dmin_exr_scale": dmin,
            "gain": {ch: 10.0 ** dmin[ch] for ch in "RGB"},
            "anchor_json": json_name,
            "rule": "x 10^dmin_exr_scale per channel, applied before the "
                    "half-float write"}


def confirm_warnings(record):
    """Undoing a bake means merging the roll again, so a measurement carrying
    warnings (printed above the prompt) is baked only after a y."""
    warnings = record.get("warnings", [])
    if not warnings:
        return
    answer = input(f"\nThe anchor measurement carries {len(warnings)} "
                   f"warning(s), listed above. Bake it into the roll anyway? "
                   f"[y/N] ").strip().lower()
    if answer not in ("y", "yes"):
        raise SystemExit("Nothing written; any earlier run is untouched.")


def apply_anchor(merged, anchor):
    if anchor is None:
        return merged
    return merged * np.array([anchor["gain"][ch] for ch in "RGB"], np.float32)


def to_half(merged, label, anchor):
    """merged as float16, refusing a frame with any pixel float16 cannot hold:
    past 65504 a value becomes inf, and a NaN stays NaN, in a file Resolve
    reads without complaint. The refusal names the channels and the gain."""
    with np.errstate(over="ignore", invalid="ignore"):
        half = merged.astype(np.float16)
    bad = ~np.isfinite(half)
    if bad.any():
        detail = ", ".join(
            f"{ch} {int(bad[..., i].sum())} px (max {float(np.nanmax(merged[..., i])):.4g})"
            for i, ch in enumerate("RGB") if bad[..., i].any())
        gain = ("" if anchor is None else " at anchor gain "
                + " ".join(f"{ch} {anchor['gain'][ch]:.4g}" for ch in "RGB"))
        raise SystemExit(f"[{label}] pixels half float cannot hold{gain}: "
                         f"{detail}. Not written.")
    return half


def promote(staging, out_dir, earlier):
    """Replace the earlier run (its EXRs and anchor records) with the complete
    roll in staging. Every step is a rename inside out_dir, so one file
    system: the earlier files move into a hidden backup folder, the staged
    files move in, and the backup is deleted only after every rename
    succeeded. On a failure the renames done so far are undone; if that
    fails too, both complete sets stay on disk and the message says where."""
    backup = Path(tempfile.mkdtemp(prefix=".previous-", dir=out_dir))
    moved_out, moved_in = [], []
    try:
        for p in earlier:
            os.replace(p, backup / p.name)
            moved_out.append(p)
        for p in sorted(staging.iterdir()):
            os.replace(p, out_dir / p.name)
            moved_in.append(p)
    except (OSError, KeyboardInterrupt) as e:
        try:
            for p in reversed(moved_in):
                os.replace(out_dir / p.name, p)
            for p in reversed(moved_out):
                os.replace(backup / p.name, p)
            backup.rmdir()
            where = f"the earlier run is back in place; the new roll stays in {staging}"
        except OSError:
            where = (f"the earlier run is in {backup}, the new roll in {staging}, "
                     f"and the files already moved are in {out_dir}")
        raise SystemExit(f"Replacing the earlier run failed ({e!r}). Nothing was "
                         f"deleted: {where}.")
    shutil.rmtree(backup)
    staging.rmdir()


def merge_triplet(index, triplet, mode, flat_models, out_dir, exifs, role=None,
                  anchor=None):
    """Worker: one triplet -> one EXR (float32 intermediates; flat gains
    cached per worker process and frame size).

    role=None writes the numbered scan frame index+1. role="plain" writes the
    flat frames themselves, merged and flat-fielded exactly like a scan frame,
    as plain.exr: the plain-light set the anchor measures against, on the
    same data that the roll's frames carry.

    anchor (from anchor_from_record) multiplies each channel by its gain after
    the flat field and is recorded in the header; None writes the linear
    values."""
    r_path, g_path, b_path = (Path(p) for p in triplet)
    read = make_reader(mode)
    # Only one channel of each decode survives: copying it out and dropping
    # the full RGB image before the next decode keeps one full image resident
    # per worker instead of three.
    r_ch = read(r_path)[..., 0].astype(np.float32, copy=True)
    g_ch = read(g_path)[..., 1].astype(np.float32, copy=True)
    b_ch = read(b_path)[..., 2].astype(np.float32, copy=True)

    h, w = require_same_size([(r_path.name, r_ch), (g_path.name, g_ch),
                              (b_path.name, b_ch)])
    merged = np.stack([r_ch, g_ch, b_ch], axis=-1)
    del r_ch, g_ch, b_ch

    if flat_models is not None:
        if (h, w) not in _GAIN_CACHE:
            _GAIN_CACHE[(h, w)] = np.stack(
                [eval_flat_gain(c, d, h, w) for c, d in flat_models], axis=-1)
        merged = merged * _GAIN_CACHE[(h, w)]
    merged = apply_anchor(merged, anchor)

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
        "values": VALUES_ANCHORED if anchor else VALUES_LINEAR,
        **({"roll_anchor": anchor} if anchor else {}),
        **({"role": role} if role else {}),
    })

    label = role if role else f"{index + 1:04d}"
    out_path = Path(out_dir) / f"{label}.exr"
    header = {"compression": OpenEXR.ZIP_COMPRESSION,
              "type": OpenEXR.scanlineimage,
              "capture_metadata": description}
    with OpenEXR.File(header, {"RGB": to_half(merged, label, anchor)}) as f:
        f.write(str(out_path))
    return (index, f"[{label}] {r_path.name}+{g_path.name}+{b_path.name} "
                   f"-> {out_path.parent.name}/{out_path.name}  ({w}x{h}, half-float linear EXR"
                   f"{', anchored' if anchor else ''})")


# ============================================================================
# roll anchor: measurement core and ROI picker
# ============================================================================

CHANNELS = ("R", "G", "B")


# ---------------------------------------------------------------- raw access

def valid_seconds(value, label):
    """An exposure that can divide a rate: finite and positive. Anything else
    (0, a negative, nan, inf, a non-number) would pass through the arithmetic
    and land in the anchor JSON as inf or nan, so it is refused at the source
    whatever that source is: EXIF, merged-frame metadata or an override."""
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        raise SystemExit(f"{label}: exposure {value!r} is not a number")
    if not np.isfinite(seconds) or seconds <= 0:
        raise SystemExit(f"{label}: exposure {value!r} s is not a finite "
                         f"positive time")
    return seconds


def exif_exposure_seconds(path):
    out = subprocess.run(
        ["exiftool", "-s3", "-n", "-ExposureTime", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    if not out:
        raise ValueError(f"No ExposureTime in EXIF of {path}; "
                         f"override with '{path}@1/125' syntax")
    return valid_seconds(out, f"{Path(path).name} EXIF")


def exif_iso(path):
    """The frame's ISO, recorded for the audit trail and never acted on.

    No value is validated: base ISO differs from body to body, so a whitelist
    here would reject perfectly good cameras. Sensor gain cancels in the
    density ratio as long as it does not drift across the frame set, which
    iso_drift_warnings checks after measurement.
    """
    out = subprocess.run(
        ["exiftool", "-s3", "-n", "-ISO", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out) if out else None


def iso_drift_warnings(frames):
    """Warn when ISO is not the same in every frame of the set.

    Density here is a ratio of two frames' rates, so sensor gain cancels
    exactly when it is uniform and biases the result by log10 of the ratio
    when it is not. The value itself is irrelevant — ISO 64, 100 or 200 all
    work — so this compares frames against each other and never against a
    fixed list. A warning rather than a refusal: only the operator knows
    whether a deliberately different Dmax exposure is worth the bias.
    """
    seen = {}
    for name, frame in frames.items():
        for ch in CHANNELS:
            iso = frame[ch].get("iso")
            if iso is not None:
                seen.setdefault(float(iso), []).append(f"{name}/{ch}")
    if len(seen) < 2:
        return []
    detail = "; ".join(f"ISO {int(v)}: {', '.join(w)}"
                       for v, w in sorted(seen.items()))
    return [f"ISO differs across the frame set — sensor gain no longer "
            f"cancels in the density ratio and these densities are biased "
            f"by log10 of the gain ratio. Reshoot at one ISO. {detail}"]


def exif_consistency(paths):
    """Aperture drift across frames breaks shutter-only normalization.

    A raw capture's aperture comes from EXIF; a merged frame's from the
    per-channel f_number the converter embedded, one entry per source capture
    (a foreign frame carries none and contributes nothing). Every value found
    across the whole frame set must agree. ISO is handled after measurement
    by iso_drift_warnings, which works on raw and merged frames alike.
    """
    tags = {}
    for p in paths:
        p = Path(p)
        if p.suffix.lower() in MERGED_EXTS:
            f_numbers = merged_frame_meta(p).get("f_number") or {}
            for ch in CHANNELS:
                if f_numbers.get(ch) is not None:
                    tags[(str(p.resolve()), ch)] = float(f_numbers[ch])
            continue
        out = subprocess.run(
            ["exiftool", "-s3", "-n", "-FNumber", str(p)],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        if out:
            tags[(str(p.resolve()), None)] = float(out)
    # Keyed by full path (plus channel), never by basename: plain/0001.exr and
    # dmin/0001.exr are different frames and must both be compared.
    if len({round(v, 2) for v in tags.values()}) > 1:
        detail = "; ".join(
            f"{Path(path).parent.name}/{Path(path).name}"
            + (f" ({ch} capture)" if ch else "") + f": f/{v:g}"
            for (path, ch), v in tags.items())
        raise SystemExit(f"Aperture differs across frames — normalization "
                         f"is invalid. {detail}")


def _parse_seconds(spec):
    spec = spec.strip()
    try:
        if "/" in spec:
            num, den = spec.split("/")
            seconds = float(num) / float(den)
        else:
            seconds = float(spec)
    except (ValueError, ZeroDivisionError):
        raise SystemExit(f"exposure override {spec!r} is not a time: use "
                         f"seconds (0.5) or a fraction (1/125)")
    return valid_seconds(seconds, f"exposure override {spec!r}")


def parse_frame_arg(arg):
    """'file.arw' or 'file.arw@1/30' -> (path, exposure_seconds or None).

    A merged frame may carry a per-channel override, 'file.exr@G=1/60,B=1/30',
    which returns a {channel: seconds} dict and applies only to the channels
    named, so that a channel whose exposure IS in the metadata keeps it.
    """
    if "@" not in arg:
        return Path(arg), None
    path, _, spec = arg.rpartition("@")
    if "=" in spec:
        per = {}
        for part in spec.split(","):
            ch, _, val = part.partition("=")
            ch = ch.strip().upper()
            if ch not in CHANNELS:
                raise ValueError(f"{arg}: per-channel override names {ch!r}, not one of R, G, B")
            per[ch] = _parse_seconds(val)
        return Path(path), per
    return Path(path), _parse_seconds(spec)


def override_for(override, channel):
    """The override that applies to one channel: a scalar applies to all,
    a dict only to the channels it names."""
    if isinstance(override, dict):
        return override.get(channel)
    return override


def resolve_roi(h, w, roi):
    """ROI spec -> pixel box (x0, y0, x1, y1) in raw visible-frame coords.

    roi may be None (central 50% per axis — the historical default), a
    fraction 0<f<=1 (centered box covering f of each axis), or an explicit
    (x0, y0, x1, y1) box, clamped to the frame.
    """
    if roi is None:
        roi = 0.5
    if isinstance(roi, (int, float)):
        f = float(roi)
        if not 0 < f <= 1:
            raise ValueError(f"ROI fraction must be in (0, 1], got {f}")
        mx, my = int(w * (1 - f) / 2), int(h * (1 - f) / 2)
        return (mx, my, w - mx, h - my)
    x0, y0, x1, y1 = (int(v) for v in roi)
    # Sort FIRST, then clamp both ends of each axis: clamping before sorting
    # let a reversed or out-of-frame endpoint back into the result, and a box
    # from a larger image could return an empty crop.
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    x0, x1 = (min(max(0, v), w) for v in (x0, x1))
    y0, y1 = (min(max(0, v), h) for v in (y0, y1))
    if x1 - x0 < 16 or y1 - y0 < 16:
        raise ValueError(f"ROI box too small after clamping to {w}x{h}: {(x0, y0, x1, y1)}")
    return (x0, y0, x1, y1)


def read_raw_arrays(path):
    """The decoded raw, held in its native integer dtype so a picker can keep
    all three captures of a frame set resident (a 61 MP mosaic is ~120 MB as
    uint16 and ~490 MB as float64) and re-measure any ROI without decoding
    again. Copies are taken because rawpy's arrays are views into the raw
    object, which closes here."""
    import rawpy
    with rawpy.imread(str(path)) as raw:
        return dict(image=raw.raw_image_visible.copy(),
                    colors=raw.raw_colors_visible.copy(),
                    black=np.array(raw.black_level_per_channel, dtype=np.float64),
                    white=float(raw.white_level),
                    desc=raw.color_desc.decode())  # e.g. "RGBG"


def load_linear_planes(path, roi=None, arrays=None):
    """Raw sensor data minus vendor black level, split into CFA colour planes.

    Returns ({channel: 1-D float array of ROI pixel values}, roi_box,
    {channel: white-level span}). The span (white_level - black) is the
    denominator raw_to_exr uses, so mean/span reproduces that EXR's pixel
    value for the same patch. No demosaic, no white balance, no tone curve.
    Default ROI is the central 50% of each axis; see resolve_roi for other
    specs. `arrays` is an already-decoded read_raw_arrays(path), so a caller
    measuring many ROIs of one capture decodes it once.
    """
    if arrays is None:
        arrays = read_raw_arrays(path)
    black, white, desc = arrays["black"], arrays["white"], arrays["desc"]
    h, w = arrays["image"].shape
    x0, y0, x1, y1 = resolve_roi(h, w, roi)
    # Crop first, then convert: only the ROI becomes float64.
    image = arrays["image"][y0:y1, x0:x1].astype(np.float64)
    colors = arrays["colors"][y0:y1, x0:x1]
    planes = {}
    span_parts = {}
    for ci, letter in enumerate(desc):
        if letter not in CHANNELS:
            continue
        values = image[colors == ci] - black[ci]
        planes.setdefault(letter, []).append(values)
        # 'RGBG' visits G twice, at CFA indices 1 and 3, and those two
        # sites can carry different black levels. The pixels are already
        # per-plane subtracted, so only the span has to be combined —
        # weighted by how many pixels each index actually contributed,
        # which is what the pooled plane's mean is an average over.
        span_parts.setdefault(letter, []).append(
            (max(1.0, white - black[ci]), values.size))
    spans = {}
    for ch, parts in span_parts.items():
        n = sum(size for _, size in parts)
        spans[ch] = (sum(s * size for s, size in parts) / n if n
                     else max(s for s, _ in parts))
    return ({ch: np.concatenate(v) for ch, v in planes.items()},
            (x0, y0, x1, y1), spans)


def bimodality(values, max_sample=50000):
    """Two-population heuristic: True when the ROI looks contaminated.

    1-D two-means on a subsample; flags when the clusters are well separated
    (> 3.5x pooled within-cluster std — a pure Gaussian split at its mean
    scores ~2.65, so the threshold must sit clearly above that) and neither
    cluster is negligible (>5%). Two distinct clusters with NO within-cluster
    spread are the limiting case of separation, not its absence, and flag.
    """
    v = np.asarray(values, float)
    v = v[np.isfinite(v)]
    if v.size < 100:
        return False           # too few to split; also guards the percentiles
    if v.size > max_sample:
        v = v[:: v.size // max_sample]
    lo, hi = np.percentile(v, (1, 99))
    v = v[(v >= lo) & (v <= hi)]
    if v.size < 100 or v.std() == 0:
        return False
    c1, c2 = np.percentile(v, (25, 75))
    for _ in range(30):
        mid = (c1 + c2) / 2
        a, b = v[v <= mid], v[v > mid]
        if not len(a) or not len(b):
            return False
        n1, n2 = a.mean(), b.mean()
        if n1 == c1 and n2 == c2:
            break
        c1, c2 = n1, n2
    a, b = v[v <= (c1 + c2) / 2], v[v > (c1 + c2) / 2]
    frac = min(len(a), len(b)) / v.size
    within = np.sqrt((a.var() * len(a) + b.var() * len(b)) / v.size)
    return frac > 0.05 and abs(c2 - c1) > 3.5 * within


# ------------------------------------------------------------- measurements

MIN_PATCH_PIXELS = 32


def robust_stats(values, label="patch"):
    """Trimmed mean/std over a patch: rejects dust, hot pixels, PDAF rows.

    Non-finite pixels (an EXR can carry nan or inf) are dropped before the
    trim, and a population too small to average is refused: with them a
    single nan turned the whole result into (nan, nan, 0), which np.percentile
    propagates rather than reports."""
    values = np.asarray(values, dtype=np.float64)
    finite = values[np.isfinite(values)]
    if finite.size < values.size:
        print(f"  {label}: {values.size - finite.size} non-finite pixel(s) "
              f"dropped before measurement")
    if finite.size < MIN_PATCH_PIXELS:
        raise SystemExit(f"{label}: only {finite.size} usable pixel(s) in the ROI "
                         f"(need at least {MIN_PATCH_PIXELS}); enlarge the ROI")
    lo, hi = np.percentile(finite, (1, 99))
    core = finite[(finite >= lo) & (finite <= hi)]
    if core.size < 2:
        raise SystemExit(f"{label}: ROI collapses to {core.size} pixel(s) after "
                         f"trimming; enlarge the ROI")
    return float(core.mean()), float(core.std(ddof=1)), int(core.size)


MERGED_EXTS = (".tif", ".tiff", ".exr")


def read_exr(path):
    """An EXR -> (H x W x 3 float32 array in R,G,B order, header dict).

    Channels are resolved BY NAME rather than through OpenEXR's grouped view
    (`channels()["RGB"]`), which exists only when the file holds exactly R, G
    and B: an alpha channel regroups them as "RGBA", a layer prefix
    ("rgb.R") or a single luminance plane ("Y") gives other keys, and a
    Resolve or Nuke re-save can introduce any of these. Accepted: R, G, B
    with or without one layer prefix (alpha ignored); or a lone Y, replicated
    into three planes. Anything else fails naming the channels present.
    """
    import OpenEXR
    with OpenEXR.File(str(path), separate_channels=True) as f:
        header = dict(f.header())
        chans = {name: c.pixels for name, c in f.channels().items()}
    def find(letter):
        if letter in chans:
            return chans[letter]
        hits = [v for k, v in chans.items() if k.endswith("." + letter)]
        return hits[0] if len(hits) == 1 else None
    rgb = [find(ch) for ch in CHANNELS]
    if all(v is not None for v in rgb):
        planes = rgb
    elif find("Y") is not None:
        planes = [find("Y")] * 3
    else:
        raise SystemExit(
            f"{Path(path).name}: no R, G, B (or Y) channels — channels present: "
            f"{sorted(chans)}. Anchor from the raw captures or from an EXR "
            f"written by raw_to_exr / mono_to_exr.")
    return np.stack([np.asarray(v, dtype=np.float32) for v in planes], -1), header


def read_merged_arrays(path):
    """(H x W x 3 float32 image, metadata dict) of a merged frame, decoded
    once; load_merged_frame takes it through `arrays` so a picker can
    re-measure any ROI without re-reading the file."""
    path = Path(path)
    if path.suffix.lower() == ".exr":
        img, header = read_exr(path)
        raw_meta = header.get("capture_metadata")
    else:
        import tifffile
        with tifffile.TiffFile(str(path)) as t:
            raw_meta = t.pages[0].description
            img = t.asarray()
    try:
        meta = json.loads(raw_meta)
    except (json.JSONDecodeError, TypeError):
        meta = {}
    if meta.get("kind") != "trichrome_merge":
        meta = {"foreign": True}
    return img, meta


def load_merged_frame(path, roi=None, arrays=None):
    """A raw_to_exr/tiff_maker merged trichrome frame -> per-channel ROI
    values + metadata.

    EXR (raw_to_exr, primary): half-float, metadata in the
    "capture_metadata" header attribute. TIFF (legacy): float32, metadata in
    ImageDescription. Both carry per-channel exposure, ISO, and the
    flat-field flag. A file carrying neither (an EXR re-saved by another
    program, or written by something other than raw_to_exr / mono_to_exr) is
    a FOREIGN merged frame: it is accepted with empty metadata, so the
    exposure must come from the '@' override (ensure_exposures prompts for it), and
    the record flags it. Its EXR-scale densities are relative to the file's
    own unit white, which is what matters when this file is the media being
    graded. ROI is resolved against the frame's own dimensions (half-res for
    superpixel merges) — recorded roi_px is in those pixels.
    """
    img, meta = arrays if arrays is not None else read_merged_arrays(path)
    h, w = img.shape[:2]
    x0, y0, x1, y1 = resolve_roi(h, w, roi)
    crop = img[y0:y1, x0:x1]
    planes = {ch: crop[..., i].astype(np.float64).ravel()
              for i, ch in enumerate(CHANNELS)}
    return planes, (x0, y0, x1, y1), meta


def measure_frame(args_list, roi=None):
    """One calibration frame -> per-channel shutter-normalized rate + stats.

    Input is either THREE raw files in R,G,B LED order (each read through
    the matching CFA plane) or ONE merged EXR (raw_to_exr, primary) or
    legacy tiff_maker TIFF (per-channel exposure/ISO read from its embedded
    metadata). Rates are normalized by exposure time only; sensor gain
    cancels in the density ratio and ISO is recorded, not corrected. `roi`
    (see resolve_roi) applies to the whole frame set; the effective pixel
    box and a bimodality (contamination) flag are recorded per channel.

    `rate` is in ONE unit for both inputs: fraction of the sensor white level
    per second (white_frac / exposure). A raw capture's mean is in ADU and is
    divided by its CFA plane's white span, the same denominator raw_to_exr
    used to write the EXR, so a raw set and the merged frame of the same
    captures give the same rate. mean_adu / std_adu stay in the input's own
    units (ADU for raw, white fraction for merged) and are labelled as such.
    """
    result = {}
    if len(args_list) == 1:
        path, override = parse_frame_arg(args_list[0])
        if path.suffix.lower() not in MERGED_EXTS:
            raise SystemExit(f"{path.name}: single-file frame must be a merged EXR "
                             f"or TIFF (raw frames come as 3 files in R,G,B order)")
        planes, box, meta = load_merged_frame(path, roi)
        for channel in CHANNELS:
            exposure = override_for(override, channel)
            if exposure is None:
                exposure = (meta.get("exposure_s") or {}).get(channel)
                if exposure is None:
                    raise SystemExit(f"{path.name}: no exposure for channel {channel} in "
                                     f"metadata — override with '{path}@1/125' or, per "
                                     f"channel, '{path}@{channel}=1/125'")
                exposure = valid_seconds(exposure, f"{path.name} metadata, channel {channel}")
            iso = (meta.get("iso") or {}).get(channel)
            values = planes[channel]
            mean, std, n = robust_stats(values, f"{path.name} channel {channel}")
            foreign = bool(meta.get("foreign"))
            result[channel] = dict(rate=mean / exposure, mean_adu=mean,
                                   std_adu=std, n_pixels=n, exposure_s=exposure,
                                   iso=iso,
                                   white_frac=mean,  # merged frames are already white-normalized
                                   adu_unit="fraction of white level",
                                   file=path.name,
                                   source="foreign_merged_frame" if foreign else "merged_frame",
                                   flat_field_applied=(None if foreign
                                                       else bool(meta.get("flat_field_applied"))),
                                   roi_px=list(box), bimodal=bool(bimodality(values)))
        return result

    for channel, arg in zip(CHANNELS, args_list):
        path, override = parse_frame_arg(arg)
        exposure = override_for(override, channel)
        if exposure is None:
            exposure = exif_exposure_seconds(path)
        iso = exif_iso(path)
        planes, box, spans = load_linear_planes(path, roi)
        values = planes[channel]
        mean, std, n = robust_stats(values, f"{path.name} plane {channel}")

        # The OTHER two CFA planes under this LED are the crosstalk. They are
        # already loaded and were previously discarded; recording them costs
        # nothing at capture time and cannot be recovered later from the anchor
        # JSON alone. See crosstalk_matrix().
        response = {}
        for cam in CHANNELS:
            if cam not in planes:
                continue
            cam_mean, _, _ = robust_stats(planes[cam], f"{path.name} plane {cam}")
            response[cam] = cam_mean / spans[cam] / exposure

        white_frac = mean / spans[channel]
        result[channel] = dict(rate=white_frac / exposure, mean_adu=mean,
                               std_adu=std, n_pixels=n,
                               exposure_s=exposure, iso=iso,
                               white_frac=white_frac, adu_unit="ADU",
                               file=path.name, source="raw",
                               roi_px=list(box), bimodal=bool(bimodality(values)),
                               cfa_response={k: round(v, 6) for k, v in response.items()})
    return result


def crosstalk_matrix(frame):
    """Measured LED -> camera-channel leak, from a 3-raw frame set. None if
    the frame came from a merged file (the planes are already combined).

    Row = illuminating LED, column = camera CFA channel, each row scaled so its
    diagonal is 1.0. Off-diagonals are the fraction of that LED's signal landing
    in the wrong channel.

    This is the EMPIRICAL counterpart to the crosstalk the engines COMPUTE as
    `LED_SPD x camera_SSF` (see c41_statusm_engine.py's PHI). Nothing consumes
    it yet — it is recorded so the computed matrix can be checked against a
    measurement rather than trusted. Measure it on the PLAIN-LIGHT frame set:
    no film in the gate means the only mixing is the rig's own.
    """
    if not all(isinstance(frame.get(ch), dict) and frame[ch].get("cfa_response")
               for ch in CHANNELS):
        return None
    rows = {}
    for led in CHANNELS:
        resp = frame[led]["cfa_response"]
        diag = resp.get(led)
        if not diag or diag <= 0:
            return None
        rows[led] = {cam: round(resp.get(cam, 0.0) / diag, 6) for cam in CHANNELS}
    return rows


def density(frame, reference, reference_name="plain-light"):
    """Shutter-normalized density of `frame` relative to `reference`.

    The reference is the plain-light set (transmission density, clear gate =
    0.0) or, when no plain-light set was captured, the Dmin set (density above
    the film base). Exposure is already divided out of both rates.
    """
    # The numerator can legitimately floor at an unmeasurably dark patch, but a
    # reference of zero is not a small number — it is a missing measurement,
    # and every density on that channel would be meaningless. Fail rather than
    # write nan into the anchor JSON.
    for ch in CHANNELS:
        if not reference[ch]["rate"] > 0:
            raise SystemExit(
                f"{reference_name} rate for channel {ch} is "
                f"{reference[ch]['rate']!r}, not positive: the reference frame "
                f"carries no signal on that channel. Reshoot the "
                f"{reference_name} set.")
    return {ch: float(-np.log10(max(frame[ch]["rate"], 1e-30)
                                / reference[ch]["rate"])) for ch in CHANNELS}


def density_exr_scale(frame):
    """Density against the sensor white level — the zero point of raw_to_exr
    EXRs ("normalized to white level", no plain-light reference). These are
    the values the converters bake into their EXRs. Only comparable to the roll's scans if this frame
    was shot at the same per-channel exposure/ISO."""
    return {ch: float(-np.log10(max(frame[ch]["white_frac"], 1e-30)))
            for ch in CHANNELS}


def patch_snr(frame):
    """SNR of the patch MEAN (spatial averaging included) and per-pixel SNR."""
    out = {}
    for ch in CHANNELS:
        f = frame[ch]
        per_pixel = f["mean_adu"] / f["std_adu"] if f["std_adu"] > 0 else float("inf")
        out[ch] = dict(per_pixel=round(per_pixel, 3),
                       patch_mean=round(per_pixel * np.sqrt(f["n_pixels"]), 1))
    return out


def require_one_input_kind(frame_sets):
    """Every frame set of one run is raw captures, or every one is a merged
    frame. A density is a ratio between two frame sets, and a raw set and a
    merged frame differ in more than units: the merged frame may be
    flat-fielded, is half-float, and was written from its own captures'
    exposures. Mixing them puts two differently processed measurements on the
    two sides of one ratio, so the run is refused rather than reconciled.
    Values are frame-arg lists (3 raws or 1 merged file) or None."""
    kinds = {}
    for name, args in frame_sets.items():
        if args is None:
            continue
        kinds[name] = "merged" if len(args) == 1 else "raw"
    if len(set(kinds.values())) > 1:
        detail = ", ".join(f"{name}: {kind}" for name, kind in kinds.items())
        raise SystemExit(f"Frame sets mix raw captures and merged frames "
                         f"({detail}). Measure the whole set from raws, or "
                         f"the whole set from the converter's EXRs.")


def run_extraction(plain, dmin, dmax, roll_id, out, rois=None,
                   film_family="reversal"):
    """The anchor measurement on frames whose ROIs are chosen.

    plain/dmin/dmax: frame-arg lists (3 raws or 1 merged EXR/TIFF); dmin is
    required, plain and dmax optional (None to omit).
    rois: optional {"plain": roi, "dmin": roi, "dmax": roi} — each a spec
    accepted by resolve_roi. The effective pixel boxes are recorded in the
    output JSON; passing them back as `rois` reproduces a run.
    Returns the record dict (also written to `out`).

    Without a plain-light set the record carries no plain-light-scale
    densities ("dmin", "dmax"), no "led_crosstalk" and no "flat_field_note";
    "dmin_exr_scale" (the Resolve deliverable) and "dmax_above_base" are
    measured against the sensor white level and the Dmin frame respectively
    and do not depend on it.
    """
    rois = rois or {}
    require_one_input_kind({"plain": plain, "dmin": dmin, "dmax": dmax})
    all_paths = [parse_frame_arg(a)[0]
                 for a in (plain or []) + dmin + (dmax or [])]
    exif_consistency(all_paths)

    plain_frame = measure_frame(plain, rois.get("plain")) if plain else None
    dmin_frame = measure_frame(dmin, rois.get("dmin"))

    record = {
        "roll_id": roll_id,
        "measured": datetime.date.today().isoformat(),
        "mode": "narrowband",
        "film_family": film_family,
        "density_convention": (
            "scanner-space density relative to plain light (clear gate = 0.0)"
            if plain_frame else
            "no plain-light set: densities relative to the sensor white level "
            "(dmin_exr_scale) and to the Dmin frame (dmax_above_base) only"),
        "dmin_exr_scale": {ch: round(v, 4)
                           for ch, v in density_exr_scale(dmin_frame).items()},
        "dmin_exr_scale_note": BAKED_DMIN_NOTE,
        "frames": {"dmin": dmin_frame},
    }

    if plain_frame:
        record["dmin"] = {ch: round(v, 4)
                          for ch, v in density(dmin_frame, plain_frame).items()}
        record["frames"]["plain"] = plain_frame
        record["flat_field_note"] = ("plain-frame per-pixel std includes shot noise "
                                     "AND field nonuniformity; see std_adu/mean_adu "
                                     "per channel")
        xtalk = crosstalk_matrix(plain_frame)
        if xtalk:
            record["led_crosstalk"] = xtalk
            record["led_crosstalk_note"] = (
                "MEASURED on the plain-light frames (no film in the gate), so this is "
                "the rig's own LED->CFA leak. Row = LED, column = camera channel, rows "
                "scaled to a 1.0 diagonal. Nothing consumes this yet; it exists so the "
                "engines' COMPUTED crosstalk (LED_SPD x camera_SSF) can be checked "
                "against a measurement. Only available from 3-raw frame sets.")

    if dmax:
        dmax_frame = measure_frame(dmax, rois.get("dmax"))
        if plain_frame:
            record["dmax"] = {ch: round(v, 4)
                              for ch, v in density(dmax_frame, plain_frame).items()}
        # Density above the film base: the convention every cube expects, and
        # independent of any plain-light reference.
        record["dmax_above_base"] = {
            ch: round(v, 4)
            for ch, v in density(dmax_frame, dmin_frame, "Dmin").items()}
        record["dmax_snr"] = patch_snr(dmax_frame)
        record["frames"]["dmax"] = dmax_frame
        record["dmax_black_handling"] = "vendor black level (dark-frame subtraction removed 2026-07-18)"
        for ch in CHANNELS:
            if dmax_frame[ch]["mean_adu"] < 3 * dmax_frame[ch]["std_adu"] / np.sqrt(dmax_frame[ch]["n_pixels"]):
                record.setdefault("warnings", []).append(
                    f"Dmax channel {ch}: patch mean is not significant vs noise "
                    f"(< 3 sigma of the mean) — treat this Dmax as a lower bound only")

    for w in iso_drift_warnings(record["frames"]):
        record.setdefault("warnings", []).append(w)

    for frame_name, frame in record["frames"].items():
        if frame["R"].get("source") == "foreign_merged_frame":
            record.setdefault("warnings", []).append(
                f"{frame_name} frame {frame['R']['file']} carries no capture "
                f"metadata (not written by raw_to_exr / mono_to_exr): exposure "
                f"was supplied by the operator, ISO and flat-field state are "
                f"unknown, and its EXR-scale densities are relative to the "
                f"file's own unit white — valid for grading files of the same "
                f"normalisation, not for datasheet comparison")

    for frame_name, frame in record["frames"].items():
        for ch in CHANNELS:
            if frame[ch].get("bimodal"):
                record.setdefault("warnings", []).append(
                    f"{frame_name} channel {ch}: ROI pixel distribution is bimodal — "
                    f"a second population (film box / gate edge / holder?) is inside "
                    f"the ROI; reselect a cleaner region")

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=1))
    print(f"roll {roll_id} (narrowband, {film_family}):")
    if "dmin" in record:
        print("  Dmin (plain-light scale, datasheet comparison):",
              {ch: record['dmin'][ch] for ch in CHANNELS})
    else:
        print("  no plain-light set: plain-light-scale densities and LED "
              "crosstalk not recorded")
    print("  Dmin (EXR scale, baked into the roll):",
          {ch: record['dmin_exr_scale'][ch] for ch in CHANNELS})
    if dmax:
        if "dmax" in record:
            print("  Dmax:", {ch: record['dmax'][ch] for ch in CHANNELS})
        print("  Dmax above base:", {ch: record['dmax_above_base'][ch] for ch in CHANNELS},
              " SNR(mean):", {ch: record['dmax_snr'][ch]['patch_mean'] for ch in CHANNELS})
    for w in record.get("warnings", []):
        print("  WARNING:", w)
    print(f"wrote {out}")
    return record


# ============================================================================
# ROI picker (matplotlib)
# ============================================================================

def load_preview(path, downsample=8):
    """Log-scaled full-frame preview + frame size (raw mosaic or merged TIFF).

    For raws, the CFA mosaic (all sites) is fine for framing purposes; for
    tiff_maker merged TIFFs, the channel mean is shown. Display is
    log-scaled so even a ~4 D rebate patch is visible. Selection
    coordinates map back to source pixels via `downsample`.
    """
    if Path(path).suffix.lower() == ".exr":
        img = read_exr(path)[0].astype(np.float64).mean(-1)
    elif Path(path).suffix.lower() in (".tif", ".tiff"):
        import tifffile
        img = tifffile.imread(str(path)).astype(np.float64).mean(-1)
    else:
        import rawpy
        with rawpy.imread(str(path)) as raw:
            img = raw.raw_image_visible.astype(np.float64)
            img = img - float(np.mean(raw.black_level_per_channel))
    h, w = img.shape
    small = img[::downsample, ::downsample]
    floor = max(1e-9, np.percentile(small[small > 0], 0.1) if (small > 0).any() else 1e-9)
    display = np.log10(np.clip(small, floor, None))
    return display, (h, w)


def hist_verdict(planes):
    """The picker's per-channel histogram data and its verdict line.

    Returns (finite planes or None, verdict text, colour). Non-finite pixels
    are dropped first, because one NaN made every bin edge NaN and an entirely
    non-finite channel emptied bimodality's input; a channel left with fewer
    than MIN_PATCH_PIXELS usable pixels makes the ROI invalid (the same
    threshold robust_stats enforces at measurement), and is reported instead
    of histogrammed. Pure numpy, so the picker's verdict is testable headless."""
    finite = {ch: np.asarray(planes[ch], dtype=np.float64) for ch in CHANNELS}
    finite = {ch: v[np.isfinite(v)] for ch, v in finite.items()}
    short = [f"{ch} {finite[ch].size}" for ch in CHANNELS
             if finite[ch].size < MIN_PATCH_PIXELS]
    if short:
        return (None, f"INVALID ROI — too few usable (finite) pixels: "
                      f"{', '.join(short)}; need {MIN_PATCH_PIXELS} per channel",
                "crimson")
    dropped = sum(int(np.asarray(planes[ch]).size - finite[ch].size) for ch in CHANNELS)
    flagged = [ch for ch in CHANNELS if bimodality(finite[ch])]
    if flagged:
        verdict = f"BIMODAL ({', '.join(flagged)}) — second population in ROI, reselect"
    else:
        verdict = "unimodal — clean patch"
    if dropped:
        verdict += f" ({dropped} non-finite pixel(s) ignored)"
    return finite, verdict, "crimson" if flagged else "green"


class RoiPicker:
    def __init__(self, title, preview, raw_hw, downsample, initial_box, prev_box,
                 hist_values_fn):
        import matplotlib.pyplot as plt
        from matplotlib.widgets import RectangleSelector, Button

        self.downsample = downsample
        self.raw_h, self.raw_w = raw_hw
        self.box = initial_box            # raw-coordinate (x0, y0, x1, y1)
        self.prev_box = prev_box
        self.confirmed = False
        self.hist_values_fn = hist_values_fn

        self.fig, (self.ax_img, self.ax_hist) = plt.subplots(
            1, 2, figsize=(12, 6), width_ratios=[2, 1])
        self.fig.suptitle(title)
        self.ax_img.imshow(preview, cmap="gray", aspect="equal")
        self.ax_img.set_title("drag to select ROI (log-scaled preview)")

        self.selector = RectangleSelector(
            self.ax_img, self.on_select, useblit=True, interactive=True,
            button=[1], minspanx=4, minspany=4)
        self._apply_box(self.box)

        axes = [self.fig.add_axes(rect) for rect in
                ((0.55, 0.02, 0.13, 0.05), (0.69, 0.02, 0.13, 0.05),
                 (0.83, 0.02, 0.13, 0.05))]
        self.btn_prev = Button(axes[0], "Reuse previous")
        self.btn_prev.on_clicked(self.on_reuse)
        if prev_box is None:
            self.btn_prev.label.set_color("0.6")
        self.btn_reset = Button(axes[1], "Central 50%")
        self.btn_reset.on_clicked(self.on_reset)
        self.btn_ok = Button(axes[2], "Confirm")
        self.btn_ok.on_clicked(self.on_confirm)
        self.update_hist()

    def _apply_box(self, box):
        d = self.downsample
        x0, y0, x1, y1 = box
        self.selector.extents = (x0 / d, x1 / d, y0 / d, y1 / d)

    def on_select(self, eclick, erelease):
        d = self.downsample
        x0, x1 = sorted((eclick.xdata, erelease.xdata))
        y0, y1 = sorted((eclick.ydata, erelease.ydata))
        self.box = resolve_roi(self.raw_h, self.raw_w,
                               (x0 * d, y0 * d, x1 * d, y1 * d))
        self.update_hist()

    def on_reuse(self, _event):
        if self.prev_box is not None:
            self.box = self.prev_box
            self._apply_box(self.box)
            self.update_hist()

    def on_reset(self, _event):
        self.box = resolve_roi(self.raw_h, self.raw_w, 0.5)
        self._apply_box(self.box)
        self.update_hist()

    def on_confirm(self, _event):
        import matplotlib.pyplot as plt
        self.confirmed = True
        plt.close(self.fig)

    def update_hist(self):
        self.ax_hist.clear()
        planes, verdict, colour = hist_verdict(self.hist_values_fn(self.box))
        colors = {"R": "#DD3B3B", "G": "#3BAA47", "B": "#378ADD"}
        if planes is not None:
            stacked = np.concatenate([planes[ch] for ch in CHANNELS])
            lo, hi = np.percentile(stacked, (0.5, 99.5))
            bins = np.linspace(lo, hi, 96) if hi > lo else 96
            for ch in CHANNELS:
                self.ax_hist.hist(planes[ch], bins=bins, color=colors[ch],
                                  alpha=0.5, label=ch)
            self.ax_hist.legend(fontsize=8)
        x0, y0, x1, y1 = self.box
        self.ax_hist.set_title(f"ROI x {x0}-{x1} · y {y0}-{y1}\n{verdict}",
                               color=colour, fontsize=10)
        self.fig.canvas.draw_idle()

    def run(self):
        import matplotlib.pyplot as plt
        plt.show()
        if not self.confirmed:
            raise SystemExit("ROI selection window closed without Confirm — aborting.")
        return self.box


def frame_hist_planes(frame_args, box, cache=None):
    """The histogram's per-channel values, from the SAME capture and CFA
    plane the extraction measures: R from the R-lit capture, G from the G-lit,
    B from the B-lit. A merged frame holds all three. Reading every channel
    off the R-lit capture, as before, let the picker call an ROI clean on
    planes the extraction never looks at.

    `cache` ({path: decoded arrays}) keeps each capture decoded across the
    ROI updates of one picker: without it every drag re-read all three raws
    and the picker stalled for the decode each time. None decodes per call."""
    paths = [parse_frame_arg(a)[0] for a in frame_args]
    if len(paths) == 1:
        if cache is None:
            planes, _, _ = load_merged_frame(paths[0], box)
        else:
            key = str(paths[0])
            if key not in cache:
                cache[key] = read_merged_arrays(paths[0])
            planes, _, _ = load_merged_frame(paths[0], box, arrays=cache[key])
        return {ch: planes[ch] for ch in CHANNELS}
    out = {}
    for ch, path in zip(CHANNELS, paths):
        if cache is None:
            planes, _, _ = load_linear_planes(path, box)
        else:
            key = str(path)
            if key not in cache:
                cache[key] = read_raw_arrays(path)
            planes, _, _ = load_linear_planes(path, box, arrays=cache[key])
        out[ch] = planes[ch]
    return out


def pick_roi_for_frame(name, frame_args, prev_box):
    """Open the picker for one frame set; returns the confirmed pixel box.
    The frame set's captures are decoded once into a cache that lives as long
    as this picker, then released."""
    r_path, _ = parse_frame_arg(frame_args[0])   # R-LED raw, or the merged frame
    preview, raw_hw = load_preview(r_path)
    downsample = 8
    cache = {}

    def hist_values(box):
        return frame_hist_planes(frame_args, box, cache)

    # A previous frame's box is reused only if it is a valid box on THIS
    # frame; a box from a larger image falls back to the central 50%.
    if prev_box is not None:
        try:
            prev_box = resolve_roi(*raw_hw, prev_box)
        except ValueError as e:
            print(f"  {name}: previous ROI does not fit this frame ({e}); "
                  f"starting from the central 50%")
            prev_box = None
    initial = prev_box or resolve_roi(*raw_hw, 0.5)
    picker = RoiPicker(f"{name} frame — {r_path.name}", preview, raw_hw,
                       downsample, initial, prev_box, hist_values)
    return picker.run()


def parse_shutter_input(text):
    """User shutter entry -> seconds.

    "125" -> 1/125 s (integer denominator, the usual-scan convention);
    "1/30" -> 1/30 s; "2s" or "0.5s" -> seconds (long Dmax exposures).
    Anything that is not a finite positive time is refused (valid_seconds).
    """
    text = text.strip().lower()
    try:
        if text.endswith("s"):
            seconds = float(text[:-1])
        elif "/" in text:
            num, den = text.split("/")
            seconds = float(num) / float(den)
        else:
            seconds = 1.0 / float(text)
    except (ValueError, ZeroDivisionError):
        raise SystemExit(f"shutter entry {text!r} is not a time: use a "
                         f"denominator (125), a fraction (1/30) or seconds (2s)")
    return valid_seconds(seconds, f"shutter entry {text!r}")


def merged_frame_meta(path):
    """A merged frame's capture_metadata dict, read from the header alone
    (no pixel decode); {} when the file carries none (a foreign frame)."""
    path = Path(path)
    try:
        if path.suffix.lower() == ".exr":
            import OpenEXR
            with OpenEXR.File(str(path)) as f:
                meta = json.loads(f.header().get("capture_metadata"))
        else:
            import tifffile
            with tifffile.TiffFile(str(path)) as t:
                meta = json.loads(t.pages[0].description)
        return meta if isinstance(meta, dict) else {}
    except Exception:
        return {}


def merged_frame_exposures(path):
    """{channel: seconds or None} from a merged frame's metadata; all None
    when the file carries none (a foreign frame)."""
    exp = merged_frame_meta(path).get("exposure_s") or {}
    return {ch: exp.get(ch) for ch in CHANNELS}


def missing_exposures(frame_args):
    """[(index, channel or None, path)] for every exposure the frame set
    cannot supply: a raw file with no EXIF exposure and no override (channel
    None), or a merged frame's channel that neither the metadata nor a
    per-channel override covers."""
    missing = []
    for i, arg in enumerate(frame_args):
        path, override = parse_frame_arg(arg)
        if path.suffix.lower() in MERGED_EXTS:
            known = merged_frame_exposures(path)
            for ch in CHANNELS:
                if override_for(override, ch) is None and known[ch] is None:
                    missing.append((i, ch, path))
        elif override is None:
            try:
                exif_exposure_seconds(path)
            except Exception:
                missing.append((i, None, path))
    return missing


def _ask_shutter_dialog(label):
    import tkinter as tk
    from tkinter import simpledialog
    root = tk.Tk()
    root.withdraw()
    answer = simpledialog.askstring(
        "Shutter speed needed",
        f"{label} has no readable exposure.\n\n"
        f"Enter its shutter speed:\n"
        f"  a denominator, e.g. 125  (= 1/125 s)\n"
        f"  or seconds with an s suffix, e.g. 2s or 0.5s")
    root.destroy()
    return answer


def ensure_exposures(name, frame_args, ask=_ask_shutter_dialog):
    """Prompt for a shutter speed ONLY for the exposures the frame set cannot
    supply, one prompt per missing file or per missing channel of a merged
    frame, and write each answer as an @override on that file (per channel
    for a merged frame). Every exposure already known, from EXIF, metadata or
    an explicit override, is preserved: one answer applied to the whole set
    would replace known, possibly different, channel exposures and bias the
    density ratios."""
    if frame_args is None:
        return frame_args
    missing = missing_exposures(frame_args)
    if not missing:
        return frame_args
    answers = {}
    for i, ch, path in missing:
        label = f"The {name} frame {path.name}" + (f", channel {ch}," if ch else "")
        answer = ask(label)
        if not answer:
            raise SystemExit(f"{name}: no shutter speed given for {path.name}"
                             f"{' channel ' + ch if ch else ''} — aborting.")
        answers.setdefault(i, {})[ch] = parse_shutter_input(answer)
    out = list(frame_args)
    for i, given in answers.items():
        path, override = parse_frame_arg(frame_args[i])
        if None in given:                       # a raw file: one exposure
            out[i] = f"{path}@{given[None]}"
            continue
        per = dict(override) if isinstance(override, dict) else {}
        per.update(given)
        out[i] = f"{path}@" + ",".join(f"{ch}={per[ch]}" for ch in CHANNELS if ch in per)
    return out


THUMB_PX = 320
NON_INTERACTIVE_BACKENDS = ("agg", "cairo", "pdf", "pgf", "ps", "svg", "template")


def frame_thumbnail(path, rotate=False):
    """A greyscale picture of one capture, 0-1, at most THUMB_PX on its long
    side, oriented as the converter writes the frame (horizontal flip, then
    the 180-degree rotation if asked). A raw gives its embedded preview,
    decoded at reduced size in milliseconds. A TIFF, or a raw without a JPEG
    preview, gives a strided sample of its pixels on a log scale fixed to the
    white level (3 D range), so a clear frame and a dense frame keep their
    difference. For identifying frames only: nothing here is measured."""
    path = Path(path)
    img = None
    if path.suffix.lower() in TIFF_EXTS:
        import tifffile
        data = tifffile.imread(str(path))
        white = (float(np.iinfo(data.dtype).max)
                 if np.issubdtype(data.dtype, np.integer) else 1.0)
        data = data.astype(np.float32)
        lin = (data.mean(-1) if data.ndim == 3 else data) / white
        step = max(1, -(-max(lin.shape) // THUMB_PX))
        lin = lin[::step, ::step]
    else:
        import io
        import rawpy
        from PIL import Image
        with rawpy.RawPy() as raw:
            raw.open_file(str(path))
            try:
                thumb = raw.extract_thumb()
            except (rawpy.LibRawNoThumbnailError,
                    rawpy.LibRawUnsupportedThumbnailError):
                thumb = None
            if thumb is not None and thumb.format == rawpy.ThumbFormat.JPEG:
                pic = Image.open(io.BytesIO(thumb.data))
                pic.draft("L", (THUMB_PX, THUMB_PX))
                pic = pic.convert("L")
                pic.thumbnail((THUMB_PX, THUMB_PX))
                img = np.asarray(pic, np.float32) / 255.0
            else:
                raw.unpack()
                mosaic = raw.raw_image_visible
                black = float(np.mean(raw.black_level_per_channel))
                white = float(raw.white_level)
                if mosaic.ndim == 3:            # a stacked composite
                    mosaic = mosaic.mean(-1)
                # An even stride stays on one CFA site.
                step = max(2, 2 * -(-max(mosaic.shape) // (2 * THUMB_PX)))
                lin = ((mosaic[::step, ::step].astype(np.float32) - black)
                       / max(1.0, white - black))
    if img is None:
        img = np.clip(1.0 + np.log10(np.clip(lin, 1e-3, None)) / 3.0, 0.0, 1.0)
    img = img[:, ::-1]
    if rotate:
        img = img[::-1, ::-1]
    return img


def show_contact_sheet(files, groups, per=3, rotate=False):
    """Open a window of numbered thumbnails, one per frame of the listing, so
    the Dmin and Dmax frames are found by eye before their numbers are asked.
    Each tile is the frame's second capture (the G exposure of a triplet).
    The window stays open while the terminal prompts run. Returns a function
    that closes it; with no display the listing alone serves, and an
    unreadable capture leaves its tile blank."""
    import matplotlib.pyplot as plt
    if plt.get_backend().lower() in NON_INTERACTIVE_BACKENDS:
        print("  (no display for the contact sheet; the frame listing above "
              "names the frames)")
        return lambda: None

    def tile(i):
        try:
            return frame_thumbnail(files[i * per + 1], rotate)
        except Exception as e:
            print(f"  [{i + 1:04d}] no thumbnail: {e}")
            return None

    print(f"Contact sheet: reading {groups} preview(s)...", flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        thumbs = list(pool.map(tile, range(groups)))
    shapes = [t.shape for t in thumbs if t is not None] or [(2, 3)]
    aspect = max(h / w for h, w in shapes)
    cols = min(groups, 8)
    rows = -(-groups // cols)
    width = min(16.0, max(7.0, 2.2 * cols))
    fig, axes = plt.subplots(rows, cols, squeeze=False, figsize=(
        width, rows * (width / cols * aspect + 0.3) + 0.5))
    for i, ax in enumerate(axes.flat):
        ax.axis("off")
        if i < groups:
            if thumbs[i] is not None:
                ax.imshow(thumbs[i], cmap="gray", vmin=0.0, vmax=1.0)
            ax.set_title(f"{i + 1:04d}", fontsize=9)
    fig.suptitle("Frames as the roll is written; answer the frame prompts "
                 "in the terminal")
    fig.tight_layout()
    plt.ion()
    plt.show(block=False)
    plt.pause(0.1)

    def close():
        plt.close(fig)
        plt.ioff()
    return close


def prompt_frame(label, groups, default):
    """A frame number from the listing above; Enter takes default (None = no
    frame)."""
    hint = f"Enter = {default:04d}" if default else "Enter = none"
    while True:
        raw = input(f"{label} — frame number ({hint}): ").strip()
        if not raw:
            return default
        if raw.isdigit() and 1 <= int(raw) <= groups:
            return int(raw)
        print(f"  Please give a frame number from 1 to {groups}.")


def resolve_dmin(args, groups, files=None):
    """(film family, Dmin frame index, Dmax frame index or None), 0-based.
    Every roll has a Dmin frame; it defaults to frame 0001. When a frame
    number is to be asked and files (the listed captures) are given, the
    contact sheet stays open while the prompts run."""
    for flag, number, lowest in (("--dmin-frame", args.dmin_frame, 1),
                                 ("--dmax-frame", args.dmax_frame, 0)):
        if number is not None and not lowest <= number <= groups:
            raise SystemExit(f"{flag} {number}: the roll's frames are 1 to "
                             f"{groups}{' (0 = none)' if lowest == 0 else ''}.")
    print("The Dmin frame holds clear film base: the light-struck clear leader "
          "of a reversal roll, the unexposed rebate or frame gap of a negative. "
          "The ROI picker opens on it.")
    asks = args.dmin_frame is None or args.dmax_frame is None
    close = (show_contact_sheet(files, groups) if files and asks
             else (lambda: None))
    try:
        family = args.film_family or prompt_film_family()
        dmin_patch, dmax_patch = FAMILY_PATCHES[family]
        dmin = args.dmin_frame or prompt_frame(f"Dmin ({dmin_patch})", groups, 1)
        dmax = (args.dmax_frame if args.dmax_frame is not None else
                prompt_frame(f"Dmax ({dmax_patch}, optional)", groups, None))
    finally:
        close()
    print()
    return family, dmin - 1, (dmax - 1 if dmax else None)


def convert_roll(tasks, submit, workers, out_dir, roll_id, earlier, plan,
                 has_plain):
    """Merge a roll into out_dir, shared by both converters. tasks is a list
    of (index, group, role); submit(pool, index, group, role, dest, anchor)
    returns a Future for one frame. plan is resolve_dmin's result. The Dmin
    (and Dmax) frames are merged unanchored and measured, then every frame is
    merged again with the anchor baked in. The earlier run (earlier) is
    replaced only once the new roll is complete."""
    def run(batch, dest, anchor):
        done = 0
        with ProcessPoolExecutor(max_workers=max(1, min(workers, len(batch)))) as pool:
            futures = [submit(pool, i, group, role, dest, anchor)
                       for i, group, role in batch]
            try:
                for future in as_completed(futures):
                    index, line = future.result()
                    done += 1
                    print(f"({done}/{len(batch)}) {line}", flush=True)
            except BaseException:
                # The roll cannot complete: frames not yet started are cancelled
                # instead of merged into a set that is about to be discarded.
                for future in futures:
                    future.cancel()
                raise

    out_dir.mkdir(parents=True, exist_ok=True)
    family, dmin_idx, dmax_idx = plan
    # Stage 1: the anchor's frames, unanchored, into a scratch folder that is
    # removed whatever happens; the roll folder is untouched until the anchor
    # is measured. Stage 2 merges them again with the gain, so every written
    # pixel is rounded to half float once.
    json_name = f"{roll_id}.json"
    wanted = {dmin_idx, dmax_idx} - {None}
    with tempfile.TemporaryDirectory(prefix=".anchor-", dir=out_dir) as scratch:
        scratch = Path(scratch)
        print("Anchor frames (unanchored, for measurement only):")
        run([t for t in tasks if t[2] == PLAIN_NAME or (t[2] is None and t[0] in wanted)],
            scratch, None)
        print()
        record = measure_anchor(scratch, scratch / json_name, roll_id, family,
                                dmin_idx, dmax_idx, has_plain)
    anchor = anchor_from_record(record, json_name)
    confirm_warnings(record)
    record["baked_into_exrs"] = dict(anchor, note=BAKED_BLOCK_NOTE)

    # Stage 2: the whole roll and its JSON into a staging
    # folder. The earlier run is replaced only once every file of the new one
    # exists; a failure here discards the staging folder and leaves the roll
    # folder as it was.
    expected = {f"{t[2] or f'{t[0] + 1:04d}'}.exr" for t in tasks} | {json_name}
    staging = Path(tempfile.mkdtemp(prefix=".export-", dir=out_dir))
    try:
        print("\nBaking the anchor into every frame: x10^dmin_exr_scale = "
              + "  ".join(f"{ch} {anchor['gain'][ch]:.4f}" for ch in "RGB") + "\n")
        run(tasks, staging, anchor)
        (staging / json_name).write_text(json.dumps(record, indent=1))
        staged = {p.name for p in staging.iterdir()}
        if staged != expected:
            raise SystemExit(f"Staged roll is incomplete: missing "
                             f"{sorted(expected - staged)}, unexpected "
                             f"{sorted(staged - expected)}.")
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        print(f"\nThe roll did not complete; {out_dir} is unchanged.", flush=True)
        raise
    dropped = sorted(p.name for p in earlier if p.name not in expected)
    promote(staging, out_dir, earlier)
    if dropped:
        print(f"\nRemoved {len(dropped)} file(s) of the earlier run that this "
              f"run did not write: {', '.join(dropped)}")
    print(f"\nwrote {out_dir / json_name}")
    print("Every EXR in this roll is anchored: the film base reads 1.0.")


def add_roll_args(parser):
    """The roll-naming and anchor flags both converters take."""
    parser.add_argument("--in-dir", default=".")
    parser.add_argument("--out-dir",
                        help="the roll folder outright (default <in-dir>/<roll>)")
    parser.add_argument("--roll",
                        help="roll name: the folder under the scan folder, and "
                             "the roll ID")
    parser.add_argument("--film-family", choices=("negative", "reversal"))
    parser.add_argument("--dmin-frame", type=int, metavar="N",
                        help="frame number holding the Dmin patch (default 1)")
    parser.add_argument("--dmax-frame", type=int, metavar="N",
                        help="frame number holding the Dmax patch, 0 = none")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=("pixelshift", "superpixel"))
    parser.add_argument("--flats", nargs=3, metavar=("R", "G", "B"),
                        help="the three flat frames (no film in the gate), one "
                             "per channel in R, G, B order")
    parser.add_argument("--no-flats", action="store_true",
                        help="skip flat-field correction without prompting")
    add_roll_args(parser)
    parser.add_argument("--workers", type=int,
                        help="parallel workers (default 4; ~2.5 GB per worker on "
                             "full-res pixel-shift — drop to 2 or 1 if memory-tight)")
    args = parser.parse_args()

    in_dir = Path(args.in_dir).resolve()
    out_dir, roll_id, earlier = resolve_roll(args, in_dir)
    mode = args.mode or prompt_mode()
    read = make_reader(mode)
    flats = resolve_flats_args(args)
    exts = (RAW_EXTS + TIFF_EXTS) if mode == "pixelshift" else RAW_EXTS
    files = list_scan_frames(in_dir, exts, flats)
    if len(files) < 3:
        from collections import Counter
        found = Counter(p.suffix.lower() for p in in_dir.iterdir()
                        if p.is_file() and not p.name.startswith("."))
        hint = ""
        if mode == "superpixel" and sum(found.get(e, 0) for e in TIFF_EXTS) >= 3:
            hint = ("\nThe folder holds TIFFs, which only pixelshift mode reads "
                    "— did you mean --mode pixelshift?")
        raise SystemExit(
            f"Need at least 3 scan frames ({'/'.join(exts)}) in {in_dir}.\n"
            f"Folder contents by extension: "
            f"{dict(found) if found else 'empty'}{hint}")

    flat_models = build_flat_models(flats, read) if flats else None

    exifs = batch_exif(files + list(flats or []))
    check_exposures_batch(files, exifs)

    groups = check_sequence(files)
    print_triplets(files, groups, flats)
    plan = resolve_dmin(args, groups, files)

    workers = args.workers or MAX_WORKERS[mode]
    tasks = [(i, [str(p) for p in files[i * 3: i * 3 + 3]], None) for i in range(groups)]
    if flats:
        tasks.append((groups, [str(p) for p in flats], PLAIN_NAME))

    def submit(pool, i, group, role, dest, anchor):
        return pool.submit(merge_triplet, i, group, mode, flat_models,
                           str(dest), exifs, role, anchor)

    convert_roll(tasks, submit, workers, out_dir, roll_id, earlier, plan,
                 bool(flats))


if __name__ == "__main__":
    main()
