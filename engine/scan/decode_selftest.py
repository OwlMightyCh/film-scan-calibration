#!/usr/bin/env python3
"""decode_selftest — guards on the scan tools: how the two converters route
and decode a raw file, that a mismatched triplet is refused, and the anchor
tool's ROI, exposure-override and histogram-source rules.

    python3 engine/scan/decode_selftest.py

Exits 0 when every check passes and 1 otherwise, printing one line each. No
test framework and no sample raw files are required: LibRaw's report is stubbed
so that formats this project cannot hold a specimen of, a monochrome camera
above all, are still covered. The decode arithmetic exercised is the shipped
arithmetic; only what rawpy would have returned is supplied here.

WHY THIS FILE EXISTS. The routing decisions these converters make are taken
from what LibRaw reports rather than from a file extension, which is correct
and is also the part that fails silently. A misrouted file does not raise: it
produces a plausible image that is wrong. The first check below covers a defect
of exactly that kind, found during development and fixed before it shipped, in
which keying monochrome detection on the absence of a Bayer pattern routed
EVERY pixel-shift composite to the monochrome path and turned each one
greyscale. A composite reports no pattern by construction, colour having
already been resolved per site, so its absence says nothing about the filter
array. num_colors is the authoritative signal and the pattern is consulted only
for a flat image.

Splitting the converters has since made that particular failure unreachable
through either shipped path: the colour engine refuses a frame declaring one
colour, through the mosaic and the pixel-shift entry point alike, and
mono_to_exr.py decodes every frame as monochrome by construction, consulting
the declaration for its run log alone. That refusal is asserted below by
calling the colour engine with a monochrome frame and requiring it to raise,
rather than by grepping for a flag name, which would constrain spelling rather
than behaviour. Wiring detection back to a decode in the colour engine is the
change those checks exist to fail.

The stubs encode one assumption that no test here can settle: that a camera
built without a colour filter array reports num_colors == 1. That is rawpy's
documented contract and it should be confirmed against the first real
monochrome file put through mono_to_exr.py, whose log line names what the file
declared.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import raw_to_exr as colour          # noqa: E402
import mono_to_exr as mono           # noqa: E402


class _Sizes:
    top_margin = left_margin = 0
    crop_left_margin = crop_top_margin = crop_width = crop_height = 0


class FakeRaw:
    """Only the attributes the converters read from a rawpy handle."""

    def __init__(self, image, pattern, num_colors, black=(0, 0, 0, 0),
                 white=16383):
        self.raw_image_visible = image
        self.raw_pattern = pattern
        self.num_colors = num_colors
        self.black_level_per_channel = list(black)
        self.white_level = white
        self.sizes = _Sizes()


RGGB = np.array([[0, 1], [3, 2]])
H = W = 8
_rng = np.random.default_rng(1789)
SCENE = _rng.integers(600, 15000, size=(H, W)).astype(np.uint16)
BL = (512, 512, 512, 514)

_failures = []


def check(label, passed, detail=""):
    print(("PASS  " if passed else "FAIL  ") + label + (f"    {detail}" if detail else ""))
    if not passed:
        _failures.append(label)


def main():
    print("Routing guards")
    # The defect this file exists for. A four-plane composite reports no Bayer
    # pattern; if that alone selected the monochrome path, every ARQ would
    # decode greyscale and nothing would raise.
    arq = FakeRaw(np.stack([SCENE, SCENE // 2, SCENE // 3, SCENE // 4], -1),
                  None, 4, BL)
    check("a 4-plane composite is not treated as monochrome",
          not mono.is_declared_monochrome(arq),
          "raw_pattern is None on ANY stack, so it cannot be the signal")
    out = colour.stack_rgb01(Path("x.arq"), arq)
    check("and it decodes as colour, not greyscale",
          not np.array_equal(out[..., 0], out[..., 1]))

    dng = FakeRaw(np.stack([SCENE, SCENE // 2, SCENE // 3], -1), None, 3, BL)
    check("a 3-plane linear DNG is not treated as monochrome",
          not mono.is_declared_monochrome(dng))
    out = colour.stack_rgb01(Path("x.dng"), dng)
    check("and it decodes as colour",
          not np.array_equal(out[..., 0], out[..., 1]))

    print()
    print("Colour sensor, unchanged behaviour")
    bayer = FakeRaw(SCENE, RGGB, 3, BL)
    out = colour.superpixel_rgb01(bayer)
    check("a Bayer mosaic bins to half resolution",
          out.shape == (H // 2, W // 2, 3), str(out.shape))
    check("its channels come from distinct sites",
          not np.allclose(out[..., 0], out[..., 2]))
    # Behavioural, not textual: the colour engine must REFUSE a monochrome
    # frame rather than return a plausible array. A grep for a flag name would
    # stay green if a monochrome branch were added under any other name.
    native_probe = FakeRaw(SCENE, None, 1, (512, 0, 0, 0))
    try:
        colour.superpixel_rgb01(native_probe)
        refused_bayer = False
    except RuntimeError:
        refused_bayer = True
    check("the colour engine refuses a monochrome frame (mosaic path)",
          refused_bayer)
    try:
        colour.stack_rgb01(Path("x.raw"), FakeRaw(SCENE[..., None], None, 1,
                                                  (512, 0, 0, 0)))
        refused_stack = False
    except RuntimeError:
        refused_stack = True
    check("and refuses it through the pixel-shift path too",
          refused_stack)

    print()
    print("Monochrome sensor")
    native = FakeRaw(SCENE, None, 1, (512, 0, 0, 0))
    check("a camera declaring one colour is recognised",
          mono.is_declared_monochrome(native))
    out = mono.mono_rgb01(native)
    check("it is read at FULL resolution, not binned",
          out.shape == (H, W, 3), str(out.shape))
    check("all three channels carry the same measurement",
          np.array_equal(out[..., 0], out[..., 1])
          and np.array_equal(out[..., 0], out[..., 2]))
    expect = np.clip((SCENE.astype(np.float32) - 512) / (16383 - 512), 0, None)
    check("values are black-subtracted and white-normalised",
          np.allclose(out[..., 0], expect, atol=1e-6))

    print()
    print("Stripped filter array, which no metadata reveals")
    stripped = FakeRaw(SCENE, RGGB, 3, BL)
    check("it is NOT claimed to declare monochrome",
          not mono.is_declared_monochrome(stripped),
          "the engine chosen is the declaration, not the file")
    check("the run log says so rather than staying silent",
          "operator" in mono.declared(stripped))
    out = mono.mono_rgb01(stripped)
    check("the monochrome engine reads it at full resolution",
          out.shape == (H, W, 3) and np.array_equal(out[..., 0], out[..., 2]))

    noisy = np.stack([np.clip(SCENE.astype(np.int32)
                              + _rng.integers(-40, 40, (H, W)), 0, 65535)
                      for _ in range(4)], -1).astype(np.uint16)
    shifted = FakeRaw(noisy, None, 4, (512,) * 4)
    truth = np.clip((SCENE.astype(np.float32) - 512) / (16383 - 512), 0, None)
    averaged = mono.mono_rgb01(shifted)[..., 0]
    indexed = colour.stack_rgb01(Path("x.arq"), shifted)[..., 0]
    check("averaging a composite's planes beats indexing one of them",
          np.abs(averaged - truth).std() < np.abs(indexed - truth).std(),
          f"std {np.abs(averaged-truth).std():.5f} against "
          f"{np.abs(indexed-truth).std():.5f}")

    print()
    print("Formats outside the design are still refused")
    try:
        colour.superpixel_rgb01(FakeRaw(SCENE, np.zeros((6, 6), int), 3, BL))
        check("X-Trans is refused", False)
    except RuntimeError as e:
        check("X-Trans is refused", "6x6" in str(e))
    try:
        colour.stack_rgb01(Path("x.cr2"),
                           FakeRaw(np.stack([SCENE, SCENE // 2], -1), None, 3, BL))
        check("Canon sRAW is refused", False)
    except RuntimeError as e:
        check("Canon sRAW is refused", "sRAW" in str(e))

    print()
    print("Decode arithmetic")
    # A white-level input must decode to 1.0 on every channel. With the two
    # green planes carrying different black levels, normalising by bl[1]
    # alone gave G = 0.8889 on this input.
    white = 16383
    flat = np.full((H, W), white, np.uint16)
    quad_white = FakeRaw(np.stack([flat] * 4, -1), None, 4, (512, 100, 512, 900), white)
    out = colour.stack_rgb01(Path("x.arq"), quad_white)
    check("a quad stack at white level decodes to 1.0 on G with unequal green blacks",
          np.allclose(out[..., 1], 1.0, atol=1e-6), f"G = {float(out[0, 0, 1]):.4f}")
    bayer_white = FakeRaw(flat, RGGB, 3, (512, 100, 512, 900), white)
    out = colour.superpixel_rgb01(bayer_white)
    check("the superpixel path agrees (its mean-black rule was already right)",
          np.allclose(out, 1.0, atol=1e-6))

    print()
    print("Mismatched captures are refused, not cropped")
    # A triplet whose captures differ in size would otherwise merge to a
    # plausible, misregistered EXR. The reader is stubbed so no files are read.
    import tempfile
    big = np.ones((H, W, 3), np.float32); small = np.ones((H - 2, W, 3), np.float32)
    def fake_reader(_mode=None):
        return lambda p: small if "g" in Path(p).stem else big
    for engine, label in ((colour, "raw_to_exr"), (mono, "mono_to_exr")):
        saved = engine.make_reader
        engine.make_reader = fake_reader
        exifs = {p: dict(exposure_s=1.0, iso=100, f_number=8) for p in ("r.arw", "g.arw", "b.arw")}
        try:
            with tempfile.TemporaryDirectory() as td:
                if engine is colour:
                    engine.merge_triplet(0, ["r.arw", "g.arw", "b.arw"], "superpixel", None, td, exifs)
                else:
                    engine.merge_triplet(0, ["r.arw", "g.arw", "b.arw"], None, td, exifs)
            check(f"{label} refuses a triplet with differing sizes", False, "merged silently")
        except SystemExit as e:
            check(f"{label} refuses a triplet with differing sizes",
                  "g.arw" in str(e) and f"{W}x{H - 2}" in str(e), "names the file and its size")
        finally:
            engine.make_reader = saved

    print()
    print("Anchor tool numeric core")
    import roll_anchor_gui as anchor    # noqa: E402  (numpy-only at import)
    h, w = 400, 600
    check("a reversed ROI box is sorted before clamping",
          anchor.resolve_roi(h, w, (500, 300, 100, 50)) == (100, 50, 500, 300))
    check("a box from a larger image is clamped at both ends",
          anchor.resolve_roi(h, w, (100, 100, 5000, 5000)) == (100, 100, 600, 400))
    try:
        anchor.resolve_roi(h, w, (1000, 1000, 5000, 5000))
        check("a box entirely outside the frame is rejected, not returned empty", False)
    except ValueError:
        check("a box entirely outside the frame is rejected, not returned empty", True)
    p, ov = anchor.parse_frame_arg("m.exr@G=1/60,B=0.5")
    check("a merged frame accepts a per-channel exposure override",
          ov == {"G": 1 / 60, "B": 0.5} and anchor.override_for(ov, "R") is None)
    # ensure_exposures must fill ONLY the missing exposures. Stub the two
    # sources of known exposures: EXIF on raws, metadata on merged frames.
    saved_exif, saved_meta = anchor.exif_exposure_seconds, anchor.merged_frame_exposures
    anchor.exif_exposure_seconds = lambda path: (1 / 125 if "known" in Path(path).stem
                                                 else (_ for _ in ()).throw(ValueError("no EXIF")))
    anchor.merged_frame_exposures = lambda path: {"R": 1 / 30, "G": None, "B": 1 / 30}
    asked = []
    def ask(label):
        asked.append(label); return "250"
    try:
        out = anchor.ensure_exposures("dmin", ["known_r.arw", "noexif_g.arw", "b.arw@1/8"], ask=ask)
        check("a raw set is prompted only for the file with no exposure",
              out == ["known_r.arw", "noexif_g.arw@0.004", "b.arw@1/8"] and len(asked) == 1, str(out))
        asked.clear()
        out = anchor.ensure_exposures("dmin", ["m.exr"], ask=ask)
        check("a merged frame is prompted only for its missing channel",
              out == ["m.exr@G=0.004"] and asked == ["The dmin frame m.exr, channel G,"], str(out))
        asked.clear()
        out = anchor.ensure_exposures("dmin", ["m.exr@G=1/60"], ask=ask)
        check("an explicit per-channel override is never overwritten",
              out == ["m.exr@G=1/60"] and not asked)
    finally:
        anchor.exif_exposure_seconds, anchor.merged_frame_exposures = saved_exif, saved_meta
    # The picker's histogram must read each channel from its own capture.
    saved_planes = anchor.load_linear_planes
    anchor.load_linear_planes = lambda path, roi=None: (
        {ch: np.full(4, {"r": 1.0, "g": 2.0, "b": 3.0}[Path(path).stem] * 10 + i)
         for i, ch in enumerate(anchor.CHANNELS)}, roi, {})
    try:
        planes = anchor.frame_hist_planes(["r.arw", "g.arw", "b.arw"], (0, 0, 64, 64))
        check("the histogram takes R, G, B from the R-, G-, B-lit captures",
              planes["R"][0] == 10 and planes["G"][0] == 21 and planes["B"][0] == 32,
              str({k: float(v[0]) for k, v in planes.items()}))
    finally:
        anchor.load_linear_planes = saved_planes

    print()
    if _failures:
        print(f"{len(_failures)} FAILED: " + "; ".join(_failures))
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
