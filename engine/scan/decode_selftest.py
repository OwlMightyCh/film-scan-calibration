#!/usr/bin/env python3
"""decode_selftest — guards on how the two scan converters route a raw file.

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
    if _failures:
        print(f"{len(_failures)} FAILED: " + "; ".join(_failures))
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
