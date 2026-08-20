#!/usr/bin/env python3
"""render_stage_figure — one scan, rendered at every stage of the C-41 chain.

Produces the panels of the "What each node does" figure in README.md. The point
is didactic: the same frame is written out after each node so a reader can see
what that node did, rather than being told.

The chain reproduced here is the one documented in README's "C-41, colour
negative" node chain, and the arithmetic is copied from the DCTL sources rather
than reimplemented:

  1  scan          the linear EXR as delivered by engine/scan/raw_to_exr.py
  2  anchored      dctl/prep/RollAnchor_ScanPrep.dctl   x 10^Dmin per channel
  3  density       dctl/shapers/CPD Pre-shaper.dctl     -log10, / DMAX, clamp
  4  status M      builds/c41/<stock>_StatusM.cube
  5  print         builds/c41/print_<paper>/<stock>_to_<Paper>_DisplayP3.cube

`dctl/output/Print Adjustment.dctl` sits between 4 and 5 and is a no-op at its
defaults, so it is omitted: it would produce a panel identical to stage 4.

The D-min values are READ FROM THE ROLL'S ANCHOR JSON, from the
`dmin_exr_scale` block, which is the scale that matches raw_to_exr output. They
are not estimated from image content, and nothing here inspects the picture.

Usage:

    python3 engine/c41/render_stage_figure.py \
        --exr    sample_images/portra400_endura_premier-10.exr \
        --anchor sample_images/portra400.json \
        --stock  Portra400 --paper PortraEndura

The EXR is a 39 MB scan and is not held in this repository; see the figure
caption in README.md. Everything else the script needs is committed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import OpenEXR
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]

# Load-bearing, and must match the pre-shaper and both cubes exactly.
DMAX = 3.30
EPS = 1e-6


def read_exr(path: Path) -> np.ndarray:
    """A raw_to_exr merged trichrome frame -> float64 RGB in [0, 1]."""
    with OpenEXR.File(str(path)) as fh:
        channels = fh.channels()
        if "RGB" in channels:
            arr = channels["RGB"].pixels
        else:
            try:
                arr = np.stack([channels[c].pixels for c in ("R", "G", "B")], axis=-1)
            except KeyError:
                raise SystemExit(f"{path}: expected an RGB or R/G/B channel layout, "
                                 f"found {sorted(channels)}")
    return np.asarray(arr, dtype=np.float64)[..., :3]


def read_cube(path: Path) -> tuple[np.ndarray, int]:
    """A .cube 3D LUT -> array indexed [b][g][r], plus its edge length."""
    size, rows = None, []
    for line in path.read_text().splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("LUT_3D_SIZE"):
            size = int(s.split()[1])
            continue
        if s.startswith(("TITLE", "DOMAIN_", "LUT_1D_SIZE")):
            continue
        parts = s.split()
        if len(parts) == 3:
            rows.append([float(v) for v in parts])
    if size is None:
        raise SystemExit(f"{path}: no LUT_3D_SIZE")
    table = np.asarray(rows, dtype=np.float64)
    if table.shape[0] != size ** 3:
        raise SystemExit(f"{path}: {table.shape[0]} entries, expected {size ** 3}")
    # .cube varies red fastest, so a plain reshape indexes as [b][g][r].
    return table.reshape(size, size, size, 3), size


def apply_cube(img: np.ndarray, lut: np.ndarray, n: int) -> np.ndarray:
    """Trilinear interpolation, matching Resolve's LUT domain of [0, 1]."""
    x = np.clip(img, 0.0, 1.0) * (n - 1)
    lo = np.floor(x).astype(np.int32)
    hi = np.minimum(lo + 1, n - 1)
    f = x - lo
    r0, g0, b0 = lo[..., 0], lo[..., 1], lo[..., 2]
    r1, g1, b1 = hi[..., 0], hi[..., 1], hi[..., 2]
    fr, fg, fb = f[..., 0:1], f[..., 1:2], f[..., 2:3]
    c00 = lut[b0, g0, r0] * (1 - fr) + lut[b0, g0, r1] * fr
    c01 = lut[b0, g1, r0] * (1 - fr) + lut[b0, g1, r1] * fr
    c10 = lut[b1, g0, r0] * (1 - fr) + lut[b1, g0, r1] * fr
    c11 = lut[b1, g1, r0] * (1 - fr) + lut[b1, g1, r1] * fr
    return ((c00 * (1 - fg) + c01 * fg) * (1 - fb)
            + (c10 * (1 - fg) + c11 * fg) * fb)


def srgb_encode(linear: np.ndarray) -> np.ndarray:
    """Display gamma, so that linear panels are legible on a page."""
    a = np.clip(linear, 0.0, 1.0)
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * np.power(a, 1 / 2.4) - 0.055)


def resize(img: np.ndarray, long_edge: int) -> np.ndarray:
    """Area-average downscale.

    BOX rather than LANCZOS deliberately. A windowed-sinc kernel overshoots at
    edges, and here an undershoot is not merely cosmetic: a scan value driven
    below the true minimum becomes a density the film never recorded, which
    then propagates through the log and into the cubes. Box averaging cannot
    leave the range of its inputs.
    """
    h, w = img.shape[:2]
    if max(h, w) <= long_edge:
        return img
    scale = long_edge / max(h, w)
    out = (int(round(w * scale)), int(round(h * scale)))
    bands = [np.asarray(
        Image.fromarray(img[..., i].astype(np.float32), mode="F").resize(out, Image.BOX),
        dtype=np.float64) for i in range(img.shape[2])]
    return np.stack(bands, axis=-1)


def write_panel(path: Path, rgb01: np.ndarray, icc: bytes | None, quality: int) -> None:
    arr = (np.clip(rgb01, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    Image.fromarray(arr, mode="RGB").save(
        path, "JPEG", quality=quality, optimize=True, progressive=True,
        **({"icc_profile": icc} if icc else {}))


def rel(path: Path) -> Path:
    """Repo-relative when possible. An --out-dir outside the tree is legal."""
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


def to_image(rgb01: np.ndarray) -> Image.Image:
    return Image.fromarray((np.clip(rgb01, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8), "RGB")


def load_font(size: int):
    """A system sans face, falling back to PIL's bitmap font."""
    for candidate in ("/System/Library/Fonts/Helvetica.ttc",
                      "/System/Library/Fonts/HelveticaNeue.ttc",
                      "/System/Library/Fonts/Supplemental/Arial.ttf",
                      "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
    return ImageFont.load_default()


def compose_plate(panels: list[tuple[str, Image.Image]], path: Path,
                  icc: bytes | None, quality: int,
                  cols: int = 3, panel_w: int = 520, pad: int = 18,
                  label_h: int = 34, bg=(60, 60, 60), fg=(235, 235, 235)) -> None:
    """Lay the stages out as one plate, so the page needs no table to hold them.

    A markdown table draws a bordered, zebra-striped cell around every image and
    an empty header row above them, which reads as a spreadsheet rather than a
    figure. One composed image avoids all of that, and the descriptive text then
    lives in the document as prose rather than inside table cells.

    Downscaling into the cells uses LANCZOS. That is safe here and not upstream:
    this step is terminal and purely presentational, so ringing cannot reach a
    density or a cube.
    """
    font = load_font(21)
    ratio = panels[0][1].height / panels[0][1].width
    panel_h = int(round(panel_w * ratio))
    rows = (len(panels) + cols - 1) // cols
    w = cols * panel_w + (cols - 1) * pad + 2 * pad
    h = rows * (panel_h + label_h) + (rows - 1) * pad + 2 * pad
    plate = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(plate)
    for i, (label, img) in enumerate(panels):
        x = pad + (i % cols) * (panel_w + pad)
        y = pad + (i // cols) * (panel_h + label_h + pad)
        plate.paste(img.convert("RGB").resize((panel_w, panel_h), Image.LANCZOS), (x, y))
        draw.text((x, y + panel_h + 9), label, font=font, fill=fg)
    plate.save(path, "JPEG", quality=quality, optimize=True, progressive=True,
               **({"icc_profile": icc} if icc else {}))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exr", required=True, type=Path)
    ap.add_argument("--anchor", required=True, type=Path,
                    help="roll anchor JSON from engine/scan/roll_anchor_gui.py")
    ap.add_argument("--stock", default="Portra400")
    ap.add_argument("--paper", default="PortraEndura")
    ap.add_argument("--paper-dir", default="print_endura")
    ap.add_argument("--long-edge", type=int, default=1000)
    ap.add_argument("--quality", type=int, default=86)
    ap.add_argument("--out-dir", type=Path, default=ROOT / "docs" / "figures")
    ap.add_argument("--prefix", default="c41-stage")
    ap.add_argument("--plate", type=Path, default=None,
                    help="composed figure (default docs/figures/c41-node-plate.jpg)")
    ap.add_argument("--write-panels", action="store_true",
                    help="also write each stage as its own file; off by default, "
                         "since only the plate is referenced by README")
    ap.add_argument("--delivered", type=Path,
                    default=ROOT / "docs" / "samples" / "portra400_endura_premier-10.jpg",
                    help="the frame as published, shown as the final panel to "
                         "mark where the photographer's own adjustments enter")
    ap.add_argument("--icc-from", type=Path,
                    default=ROOT / "docs" / "samples" / "portra400_endura_premier-10.jpg",
                    help="image whose Display P3 profile is copied onto the print panel")
    args = ap.parse_args()

    import json
    anchor = json.loads(args.anchor.read_text())
    try:
        dmin = anchor["dmin_exr_scale"]
        r, g, b = float(dmin["R"]), float(dmin["G"]), float(dmin["B"])
    except (KeyError, TypeError):
        raise SystemExit(f"{args.anchor}: no dmin_exr_scale block. The "
                         f"plain-light `dmin` block is the WRONG scale for an "
                         f"EXR and must not be substituted.")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    icc = None
    if args.icc_from.exists():
        with Image.open(args.icc_from) as ref:
            icc = ref.info.get("icc_profile")

    scan = resize(read_exr(args.exr), args.long_edge)
    print(f"scan          {scan.shape[1]}x{scan.shape[0]}  "
          f"range [{scan.min():.4f}, {scan.max():.4f}]")

    panels: list[tuple[str, str, np.ndarray, bytes | None]] = []
    panels.append(("1-scan", "1 · linear scan", srgb_encode(scan), None))

    # Stage 2 — RollAnchor_ScanPrep.dctl, at strength 1.
    gain = np.array([10 ** r, 10 ** g, 10 ** b])
    anchored = scan * gain
    print(f"anchor gains  R {gain[0]:.4f}  G {gain[1]:.4f}  B {gain[2]:.4f}   "
          f"(Dmin R {r} G {g} B {b})")
    panels.append(("2-anchored", "2 · roll anchor", srgb_encode(anchored), None))

    # Stage 3 — CPD Pre-shaper.dctl, value boxes left at 1.0.
    density = -np.log10(np.maximum(anchored, EPS))
    k = np.clip(density / DMAX, 0.0, 1.0)
    print(f"density OD    min {density.min():.3f}  median {np.median(density):.3f}  "
          f"max {density.max():.3f}   ({(density < 0).mean() * 100:.2f}% below base, clamped)")
    panels.append(("3-density", "3 · pre-shaper", k, None))

    # Stage 4 — the Status M cube.
    sm_path = ROOT / "builds" / "c41" / f"{args.stock}_StatusM.cube"
    lut, n = read_cube(sm_path)
    status_m = apply_cube(k, lut, n)
    print(f"status M      {sm_path.name}  {n}^3")
    panels.append(("4-statusm", "4 · Status M table", status_m, None))

    # Stage 5 — the print cube. Output is sRGB-encoded Display P3 already.
    pr_path = (ROOT / "builds" / "c41" / args.paper_dir
               / f"{args.stock}_to_{args.paper}_DisplayP3.cube")
    lut2, n2 = read_cube(pr_path)
    printed = apply_cube(status_m, lut2, n2)
    print(f"print         {pr_path.name}  {n2}^3")
    panels.append(("5-print", "5 · print table", printed, icc))

    plate_panels = [(label, to_image(data)) for _, label, data, _ in panels]
    if args.delivered.exists():
        with Image.open(args.delivered) as d:
            plate_panels.append(("6 \u00b7 as delivered", d.convert("RGB").copy()))
    else:
        print(f"  note: {args.delivered} absent, plate shows five panels")

    plate = args.plate or (args.out_dir / "c41-node-plate.jpg")
    compose_plate(plate_panels, plate, icc, args.quality)
    print(f"  wrote {rel(plate)}  {plate.stat().st_size // 1024} KB  "
          f"{len(plate_panels)} panels")

    if args.write_panels:
        for slug, _, data, profile in panels:
            out = args.out_dir / f"{args.prefix}-{slug}.jpg"
            write_panel(out, data, profile, args.quality)
            print(f"  wrote {rel(out)}  {out.stat().st_size // 1024} KB"
                  f"{'  [Display P3]' if profile else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
