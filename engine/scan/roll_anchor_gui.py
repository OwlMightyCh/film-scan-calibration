#!/usr/bin/env python3
"""ROI picker GUI for the per-roll anchor extractor (ROLL_ANCHOR_GUI.md phase 2).

A single self-contained engine (matplotlib GUI plus its own numeric core):
for each frame
set (plain light, Dmin leader, optional Dmax rebate) it shows a log-scaled
preview of the R-LED capture, lets you drag the measurement ROI, shows the
selection's per-channel pixel histogram live with a bimodality verdict, and
then runs the exact same measurement path as the CLI. The chosen ROI boxes
are recorded in the anchor JSON, so every GUI run is reproducible headlessly
via --roi.

Runs standalone: copy this ONE file anywhere and it works. It reads no
other file in the repo — the save dialog falls back to the cwd. Outside
dependencies are the `exiftool` binary and, per input format,
numpy / matplotlib / rawpy / OpenEXR / tifffile.

Camera-agnostic: no ISO value is validated, so any body's base ISO is
accepted. ISO is recorded per frame for the audit trail and a drift across
the frame set is warned about, never corrected.

Usage — fully graphical (no arguments): native macOS dialogs collect the
files one channel at a time (foolproof against selection-order ambiguity),
the roll ID, and the output location, then the ROI pickers run:
    python3 engine/scan/roll_anchor_gui.py

Or with the CLI's frame arguments (skips all dialogs):
    python3 engine/scan/roll_anchor_gui.py \
        --plain R.arw G.arw B.arw --dmin R.arw G.arw B.arw \
        [--dmax R.arw G.arw B.arw] \
        --roll-id "V100-2026-07-A" --out builds/anchors/V100-2026-07-A.json

Buttons per frame: "Reuse previous" (previous frame's box — the default
gesture, since the three captures usually share framing), "Central 50%"
(the CLI default), "Confirm".
"""
import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

import numpy as np


# ============================================================================
# shared numeric core (formerly roll_anchor_extractor)
# ============================================================================

CHANNELS = ("R", "G", "B")


# ---------------------------------------------------------------- raw access

def exif_exposure_seconds(path):
    out = subprocess.run(
        ["exiftool", "-s3", "-n", "-ExposureTime", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    if not out:
        raise ValueError(f"No ExposureTime in EXIF of {path}; "
                         f"override with '{path}@1/125' syntax")
    return float(out)


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


def repo_root():
    """The Film Scan Calibration checkout this file sits in, or None.

    Returns None whenever the script has been copied out of the repo, so no
    caller may assume the layout exists. `parents[2]` alone would raise
    IndexError on a shallow path, which is why this is not written inline.
    """
    here = Path(__file__).resolve()
    if len(here.parents) < 3:
        return None
    root = here.parents[2]
    return root if (root / "PROJECT.md").exists() else None


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

    (ISO is handled after measurement by iso_drift_warnings, which works on
    raw and merged frames alike. TIFF/EXR inputs are skipped here — their
    aperture is recorded in the merged-frame metadata for the audit trail
    but not enforced.)
    """
    tags = {}
    for p in paths:
        if Path(p).suffix.lower() in (".tif", ".tiff", ".exr"):
            continue
        out = subprocess.run(
            ["exiftool", "-s3", "-n", "-FNumber", str(p)],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        tags[str(p)] = out
    if len(set(tags.values())) > 1:
        detail = "; ".join(f"{Path(k).name}: f/{v}" for k, v in tags.items())
        raise SystemExit(f"Aperture differs across frames — normalization "
                         f"is invalid. {detail}")


def parse_frame_arg(arg):
    """'file.arw' or 'file.arw@1/30' -> (path, exposure_seconds or None)."""
    if "@" in arg:
        path, _, spec = arg.rpartition("@")
        value = (float(spec.split("/")[0]) / float(spec.split("/")[1])
                 if "/" in spec else float(spec))
        return Path(path), value
    return Path(arg), None


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
    x0, x1 = sorted((max(0, x0), min(w, x1)))
    y0, y1 = sorted((max(0, y0), min(h, y1)))
    if x1 - x0 < 16 or y1 - y0 < 16:
        raise ValueError(f"ROI box too small after clamping: {(x0, y0, x1, y1)}")
    return (x0, y0, x1, y1)


def load_linear_planes(path, roi=None):
    """Raw sensor data minus vendor black level, split into CFA colour planes.

    Returns ({channel: 1-D float array of ROI pixel values}, roi_box,
    {channel: white-level span}). The span (white_level - black) is the
    denominator raw_to_exr uses, so mean/span reproduces that EXR's pixel
    value for the same patch. No demosaic, no white balance, no tone curve.
    Default ROI is the central 50% of each axis; see resolve_roi for other
    specs.
    """
    import rawpy
    with rawpy.imread(str(path)) as raw:
        image = raw.raw_image_visible.astype(np.float64)
        colors = raw.raw_colors_visible
        black = np.array(raw.black_level_per_channel, dtype=np.float64)
        white = float(raw.white_level)
        desc = raw.color_desc.decode()  # e.g. "RGBG"
        h, w = image.shape
        x0, y0, x1, y1 = resolve_roi(h, w, roi)
        image, colors = image[y0:y1, x0:x1], colors[y0:y1, x0:x1]
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
    cluster is negligible (>5%).
    """
    v = np.asarray(values, float)
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
    return frac > 0.05 and within > 0 and abs(c2 - c1) > 3.5 * within


# ------------------------------------------------------------- measurements

def robust_stats(values):
    """Trimmed mean/std over a patch: rejects dust, hot pixels, PDAF rows."""
    lo, hi = np.percentile(values, (1, 99))
    core = values[(values >= lo) & (values <= hi)]
    return float(core.mean()), float(core.std(ddof=1)), int(core.size)


MERGED_EXTS = (".tif", ".tiff", ".exr")


def load_merged_frame(path, roi=None):
    """A raw_to_exr/tiff_maker merged trichrome frame -> per-channel ROI
    values + metadata.

    EXR (raw_to_exr, primary): half-float, metadata in the
    "capture_metadata" header attribute. TIFF (legacy): float32, metadata in
    ImageDescription. Both carry per-channel exposure, ISO, and the
    flat-field flag. ROI is resolved against the frame's own dimensions
    (half-res for superpixel merges) — recorded roi_px is in those pixels.
    """
    path = Path(path)
    if path.suffix.lower() == ".exr":
        import OpenEXR
        with OpenEXR.File(str(path)) as f:
            raw_meta = f.header().get("capture_metadata")
            img = f.channels()["RGB"].pixels
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
        raise SystemExit(
            f"{path.name}: not a raw_to_exr/tiff_maker merged frame (no capture "
            f"metadata) — foreign files are not supported; anchor from the "
            f"raw captures instead.")
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
    """
    result = {}
    if len(args_list) == 1:
        path, override = parse_frame_arg(args_list[0])
        if path.suffix.lower() not in MERGED_EXTS:
            raise SystemExit(f"{path.name}: single-file frame must be a merged EXR "
                             f"or TIFF (raw frames come as 3 files in R,G,B order)")
        planes, box, meta = load_merged_frame(path, roi)
        for channel in CHANNELS:
            exposure = override or (meta.get("exposure_s") or {}).get(channel)
            if exposure is None:
                raise SystemExit(f"{path.name}: no exposure for channel {channel} in "
                                 f"metadata — override with '{path}@1/125'")
            iso = (meta.get("iso") or {}).get(channel)
            values = planes[channel]
            mean, std, n = robust_stats(values)
            result[channel] = dict(rate=mean / exposure, mean_adu=mean,
                                   std_adu=std, n_pixels=n, exposure_s=exposure,
                                   iso=iso,
                                   white_frac=mean,  # merged frames are already white-normalized
                                   file=path.name, source="merged_frame",
                                   flat_field_applied=bool(meta.get("flat_field_applied")),
                                   roi_px=list(box), bimodal=bool(bimodality(values)))
        return result

    for channel, arg in zip(CHANNELS, args_list):
        path, override = parse_frame_arg(arg)
        exposure = override or exif_exposure_seconds(path)
        iso = exif_iso(path)
        planes, box, spans = load_linear_planes(path, roi)
        values = planes[channel]
        mean, std, n = robust_stats(values)

        # The OTHER two CFA planes under this LED are the crosstalk. They are
        # already loaded and were previously discarded; recording them costs
        # nothing at capture time and cannot be recovered later from the anchor
        # JSON alone. See crosstalk_matrix().
        response = {}
        for cam in CHANNELS:
            if cam not in planes:
                continue
            cam_mean, _, _ = robust_stats(planes[cam])
            response[cam] = cam_mean / exposure

        result[channel] = dict(rate=mean / exposure, mean_adu=mean,
                               std_adu=std, n_pixels=n,
                               exposure_s=exposure, iso=iso,
                               white_frac=mean / spans[channel],
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


def density(frame, plain):
    # The numerator can legitimately floor at an unmeasurably dark patch, but a
    # plain-light reference of zero is not a small number — it is a missing
    # measurement, and every density on that channel would be meaningless. Fail
    # rather than write nan into the anchor JSON.
    for ch in CHANNELS:
        if not plain[ch]["rate"] > 0:
            raise SystemExit(
                f"plain-light rate for channel {ch} is {plain[ch]['rate']!r}, "
                f"not positive: the reference frame carries no signal on that "
                f"channel. Reshoot the plain-light set.")
    return {ch: float(-np.log10(max(frame[ch]["rate"], 1e-30)
                                / plain[ch]["rate"])) for ch in CHANNELS}


def density_exr_scale(frame):
    """Density against the sensor white level — the zero point of raw_to_exr
    EXRs ("normalized to white level", no plain-light reference). These are
    the values to paste into RollAnchor_ScanPrep.dctl when the graded media
    is raw_to_exr output. Only comparable to the roll's scans if this frame
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


def run_extraction(plain, dmin, dmax, roll_id, out, rois=None,
                   film_family="reversal"):
    """Shared measurement flow (CLI and GUI both land here).

    plain/dmin/dmax: frame-arg lists (3 raws or 1 merged TIFF; dmax optional).
    rois: optional {"plain": roi, "dmin": roi, "dmax": roi} — each a spec
    accepted by resolve_roi. The effective pixel boxes are recorded in the
    output JSON, so any GUI-assisted run is reproducible headlessly.
    Returns the record dict (also written to `out`).
    """
    rois = rois or {}
    all_paths = [parse_frame_arg(a)[0] for a in plain + dmin + (dmax or [])]
    exif_consistency(all_paths)

    plain_frame = measure_frame(plain, rois.get("plain"))
    dmin_frame = measure_frame(dmin, rois.get("dmin"))
    dmin_d = density(dmin_frame, plain_frame)

    record = {
        "roll_id": roll_id,
        "measured": datetime.date.today().isoformat(),
        "mode": "narrowband",
        "film_family": film_family,
        "density_convention": "scanner-space density relative to plain light (clear gate = 0.0)",
        "dmin": {ch: round(v, 4) for ch, v in dmin_d.items()},
        "dmin_exr_scale": {ch: round(v, 4)
                           for ch, v in density_exr_scale(dmin_frame).items()},
        "dmin_exr_scale_note": "density vs sensor white level, matching raw_to_exr "
                               "normalization — paste THESE into RollAnchor_ScanPrep.dctl "
                               "when grading raw_to_exr EXRs; valid only if the dmin frame "
                               "was shot at the roll's per-channel exposure and "
                               "at the same ISO",
        "frames": {"plain": plain_frame, "dmin": dmin_frame},
        "flat_field_note": "plain-frame per-pixel std includes shot noise AND "
                           "field nonuniformity; see std_adu/mean_adu per channel",
    }

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
        record["dmax"] = {ch: round(v, 4)
                          for ch, v in density(dmax_frame, plain_frame).items()}
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
    print("  Dmin (plain-light scale, datasheet comparison):",
          {ch: record['dmin'][ch] for ch in CHANNELS})
    print("  Dmin (EXR scale -> RollAnchor_ScanPrep.dctl):",
          {ch: record['dmin_exr_scale'][ch] for ch in CHANNELS})
    if dmax:
        print("  Dmax:", {ch: record['dmax'][ch] for ch in CHANNELS},
              " SNR(mean):", {ch: record['dmax_snr'][ch]['patch_mean'] for ch in CHANNELS})
    for w in record.get("warnings", []):
        print("  WARNING:", w)
    print(f"wrote {out}")
    return record


# ============================================================================
# matplotlib GUI
# ============================================================================

def load_preview(path, downsample=8):
    """Log-scaled full-frame preview + frame size (raw mosaic or merged TIFF).

    For raws, the CFA mosaic (all sites) is fine for framing purposes; for
    tiff_maker merged TIFFs, the channel mean is shown. Display is
    log-scaled so even a ~4 D rebate patch is visible. Selection
    coordinates map back to source pixels via `downsample`.
    """
    if Path(path).suffix.lower() == ".exr":
        import OpenEXR
        with OpenEXR.File(str(path)) as f:
            img = f.channels()["RGB"].pixels.astype(np.float64).mean(-1)
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
        planes = self.hist_values_fn(self.box)
        colors = {"R": "#DD3B3B", "G": "#3BAA47", "B": "#378ADD"}
        stacked = np.concatenate([planes[ch] for ch in ("R", "G", "B")])
        lo, hi = np.percentile(stacked, (0.5, 99.5))
        bins = np.linspace(lo, hi, 96)
        flagged = []
        for ch in ("R", "G", "B"):
            self.ax_hist.hist(planes[ch], bins=bins, color=colors[ch],
                              alpha=0.5, label=ch)
            if bimodality(planes[ch]):
                flagged.append(ch)
        self.ax_hist.legend(fontsize=8)
        x0, y0, x1, y1 = self.box
        self.ax_hist.set_title(
            f"ROI x {x0}-{x1} · y {y0}-{y1}\n"
            + (f"BIMODAL ({', '.join(flagged)}) — second population in ROI, reselect"
               if flagged else "unimodal — clean patch"),
            color="crimson" if flagged else "green", fontsize=10)
        self.fig.canvas.draw_idle()

    def run(self):
        import matplotlib.pyplot as plt
        plt.show()
        if not self.confirmed:
            raise SystemExit("ROI selection window closed without Confirm — aborting.")
        return self.box


def pick_roi_for_frame(name, frame_args, prev_box):
    """Open the picker for one frame set; returns the confirmed pixel box."""
    r_path, _ = parse_frame_arg(frame_args[0])   # R-LED raw, or the merged TIFF
    preview, raw_hw = load_preview(r_path)
    downsample = 8
    is_merged = r_path.suffix.lower() in MERGED_EXTS

    def hist_values(box):
        if is_merged:
            planes, _, _ = load_merged_frame(r_path, box)
        else:
            planes, _, _ = load_linear_planes(r_path, box)
        return planes

    initial = prev_box or resolve_roi(*raw_hw, 0.5)
    picker = RoiPicker(f"{name} frame — {r_path.name}", preview, raw_hw,
                       downsample, initial, prev_box, hist_values)
    return picker.run()


def parse_shutter_input(text):
    """User shutter entry -> seconds.

    "125" -> 1/125 s (integer denominator, the usual-scan convention);
    "1/30" -> 1/30 s; "2s" or "0.5s" -> seconds (long Dmax exposures).
    """
    text = text.strip().lower()
    if text.endswith("s"):
        return float(text[:-1])
    if "/" in text:
        num, den = text.split("/")
        return float(num) / float(den)
    return 1.0 / float(text)


def frame_exposures_known(frame_args):
    """True when every file in the frame set has a readable exposure."""
    for arg in frame_args:
        path, override = parse_frame_arg(arg)
        if override is not None:
            continue
        if path.suffix.lower() in MERGED_EXTS:
            try:
                if path.suffix.lower() == ".exr":
                    import OpenEXR, json
                    with OpenEXR.File(str(path)) as f:
                        meta = json.loads(f.header().get("capture_metadata"))
                else:
                    import tifffile, json
                    with tifffile.TiffFile(str(path)) as t:
                        meta = json.loads(t.pages[0].description)
                if any((meta.get("exposure_s") or {}).get(ch) is None
                       for ch in ("R", "G", "B")):
                    return False
            except Exception:
                return False
        else:
            try:
                exif_exposure_seconds(path)
            except Exception:
                return False
    return True


def ensure_exposures(name, frame_args):
    """Fallback route: prompt for shutter speed ONLY when a frame set has no
    readable exposure (e.g. a legacy TIFF merged from RawTherapee sources).
    The answer applies to the whole frame set via the @override mechanism,
    so the shared measurement core needs no changes."""
    if frame_args is None or frame_exposures_known(frame_args):
        return frame_args
    import tkinter as tk
    from tkinter import simpledialog
    root = tk.Tk()
    root.withdraw()
    answer = simpledialog.askstring(
        "Shutter speed needed",
        f"The {name} frame set has no readable exposure metadata.\n\n"
        f"Enter its shutter speed:\n"
        f"  a denominator, e.g. 125  (= 1/125 s)\n"
        f"  or seconds with an s suffix, e.g. 2s or 0.5s")
    root.destroy()
    if not answer:
        raise SystemExit(f"{name}: no shutter speed given — aborting.")
    seconds = parse_shutter_input(answer)
    return [f"{parse_frame_arg(a)[0]}@{seconds}" for a in frame_args]


RAW_TYPES = [("Raw captures", "*.arw *.ARW *.dng *.DNG"), ("All files", "*")]
MERGED_TYPES = [("Merged frames (raw_to_exr/tiff_maker)", "*.exr *.EXR *.tif *.tiff *.TIF *.TIFF"), ("All files", "*")]


def dialog_flow():
    """No-argument launch: collect everything via native dialogs.

    Files are requested ONE CHANNEL AT A TIME (R, then G, then B) per frame
    set, so LED order can never be scrambled by multi-select pick order.
    Returns an argparse-like namespace, or exits if the user cancels a
    required step.
    """
    import datetime
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog

    root = tk.Tk()
    root.withdraw()

    reversal = messagebox.askyesno(
        "Film family",
        "Is this roll colour REVERSAL (slide) film?\n\n"
        "Yes — reversal: Dmin = light-struck clear leader,\n"
        "         Dmax = unexposed rebate / frame gap\n"
        "No — negative (Vision3): Dmin = unexposed rebate / frame gap\n"
        "         (orange mask), Dmax = light-struck leader tip")
    family = "reversal" if reversal else "negative"
    patch_names = {
        "reversal": ("Dmin (light-struck clear leader)",
                     "Dmax (unexposed rebate / frame gap)"),
        "negative": ("Dmin (unexposed rebate / frame gap — orange mask)",
                     "Dmax (light-struck leader tip)"),
    }[family]

    use_tiff = messagebox.askyesno(
        "Input type",
        "Are the calibration frames merged files from raw_to_exr/tiff_maker?\n\n"
        "Yes — one merged EXR/TIFF per frame set (exposure/ISO read from its "
        "embedded metadata; measures the exact flat-fielded data entering "
        "Resolve)\nNo — raw captures, three files per frame set in R, G, B "
        "LED order")

    def ask_frame(frame_name, required):
        if use_tiff:
            path = filedialog.askopenfilename(
                title=f"{frame_name} — merged EXR/TIFF", filetypes=MERGED_TYPES)
            if not path:
                if required:
                    raise SystemExit(f"{frame_name}: selection cancelled — aborting.")
                return None
            return [path]
        files, last_dir = [], None
        for ch in ("R", "G", "B"):
            path = filedialog.askopenfilename(
                title=f"{frame_name} — {ch}-LED capture",
                filetypes=RAW_TYPES,
                initialdir=last_dir)
            if not path:
                if required:
                    raise SystemExit(f"{frame_name}: selection cancelled — aborting.")
                return None
            files.append(path)
            last_dir = str(Path(path).parent)
        return files

    messagebox.showinfo(
        "Roll anchor extractor",
        "You will be asked for the calibration frames in this order:\n\n"
        f"1. Plain light (no film in gate)\n"
        f"2. {patch_names[0]}\n"
        f"3. {patch_names[1]} — optional\n\n"
        "Then a roll ID and where to save the anchor JSON.")

    plain = ask_frame("Plain light (no film)", required=True)
    dmin = ask_frame(patch_names[0], required=True)

    dmax = None
    if messagebox.askyesno("Dmax", "Also measure Dmax (unexposed rebate / frame gap)?\n"
                                    "Diagnostic only — needs a long exposure, at the "
                                    "same ISO and aperture as the other frames."):
        dmax = ask_frame(patch_names[1], required=False)

    roll_id = simpledialog.askstring(
        "Roll ID", "Roll identifier for this anchor record:",
        initialvalue=f"ROLL-{datetime.date.today().isoformat()}")
    if not roll_id:
        raise SystemExit("No roll ID — aborting.")

    # NOT `root` — that name is the Tk root, destroyed at the end of this function.
    checkout = repo_root()
    default_dir = (checkout / "builds" / "anchors") if checkout else Path.cwd()
    default_dir.mkdir(parents=True, exist_ok=True)
    out = filedialog.asksaveasfilename(
        title="Save anchor JSON as", defaultextension=".json",
        initialdir=str(default_dir), initialfile=f"{roll_id}.json",
        filetypes=[("JSON", "*.json")])
    if not out:
        raise SystemExit("No output path — aborting.")

    root.destroy()
    return argparse.Namespace(plain=plain, dmin=dmin, dmax=dmax,
                              roll_id=roll_id, out=out, film_family=family)


def main():
    if len(sys.argv) == 1:
        args = dialog_flow()
    else:
        parser = argparse.ArgumentParser(
            description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument("--plain", nargs="+", required=True)
        parser.add_argument("--dmin", nargs="+", required=True)
        parser.add_argument("--dmax", nargs="+")
        parser.add_argument("--roll-id", required=True)
        parser.add_argument("--out", required=True)
        parser.add_argument("--film-family", choices=("reversal", "negative"),
                            default="reversal")
        args = parser.parse_args()

    args.plain = ensure_exposures("plain", args.plain)
    args.dmin = ensure_exposures("dmin", args.dmin)
    args.dmax = ensure_exposures("dmax", args.dmax)

    rois, prev = {}, None
    for name, frame_args in (("plain", args.plain), ("dmin", args.dmin),
                             ("dmax", args.dmax)):
        if frame_args is None:
            continue
        rois[name] = pick_roi_for_frame(name, frame_args, prev)
        prev = rois[name]
        print(f"  {name} ROI confirmed: x {rois[name][0]}-{rois[name][2]} "
              f"y {rois[name][1]}-{rois[name][3]}")

    record = run_extraction(args.plain, args.dmin, args.dmax,
                            args.roll_id, args.out, rois=rois,
                            film_family=args.film_family)
    show_result(record, args.out)


def show_result(record, out_path):
    """Final screen: the three slider values, which are the tool's actual
    deliverable — they go verbatim into RollAnchor_ScanPrep.dctl (the node
    before the preshaper). Values are also placed on the clipboard.

    Rendered with matplotlib, NOT tkinter: on macOS, creating a fresh tk.Tk()
    root after matplotlib's event loop has run (the ROI pickers) segfaults
    ("Python quit unexpectedly"). matplotlib is already the active toolkit
    here and is safe to reuse; the clipboard goes through macOS `pbcopy`
    rather than Tk. The values are also printed to the terminal by
    run_extraction, so they are recoverable even if no display is available.
    """
    import subprocess
    import matplotlib.pyplot as plt

    dmin = record["dmin_exr_scale"]
    lines = [f"Dmin {ch} = {dmin[ch]:.3f}" for ch in ("R", "G", "B")]
    clip = "  ".join(lines)
    clip_note = ""
    try:
        subprocess.run(["pbcopy"], input=clip, text=True, check=True)
        clip_note = "(also copied to the clipboard)"
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    header = ("Enter these into RollAnchor_ScanPrep.dctl\n"
              "(EXR-scale, for grading raw_to_exr EXRs; scan-prep node "
              "BEFORE the preshaper):")
    footer = ("Plain-light scale (datasheet comparison only): "
              + "  ".join(f"{ch} {record['dmin'][ch]:.3f}" for ch in ("R", "G", "B"))
              + "\n")
    if "dmax" in record:
        footer += ("Dmax (diagnostic only — do not enter anywhere): "
                   + "  ".join(f"{ch} {record['dmax'][ch]:.2f}" for ch in ("R", "G", "B")) + "\n")
    if "led_crosstalk" in record:
        worst = max(v for led, row in record["led_crosstalk"].items()
                    for cam, v in row.items() if cam != led)
        footer += (f"LED crosstalk measured (worst off-diagonal {worst:.4f}) — "
                   f"recorded in the JSON, nothing consumes it yet\n")
    for w in record.get("warnings", []):
        footer += f"⚠ {w}\n"
    footer += f"\nAudit record: {out_path}\nClose this window to finish."

    fig = plt.figure(figsize=(8, 5))
    try:
        fig.canvas.manager.set_window_title(f"Anchors — roll {record['roll_id']}")
    except Exception:
        pass
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.text(0.05, 0.95, header, va="top", ha="left", fontsize=12)
    ax.text(0.05, 0.72, "\n".join(lines), va="top", ha="left", fontsize=26,
            family="monospace", fontweight="bold")
    ax.text(0.05, 0.42, clip_note, va="top", ha="left", fontsize=10, color="#666")
    ax.text(0.05, 0.34, footer, va="top", ha="left", fontsize=10, color="#333")
    plt.show()


if __name__ == "__main__":
    main()
