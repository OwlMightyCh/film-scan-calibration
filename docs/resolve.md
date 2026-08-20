# Using the tables in DaVinci Resolve

This document covers everything between a developed roll and a graded image:
capturing the scan, measuring the roll, and the node chain for each of the
three film processes. The reasoning behind the transforms is in
[method.md](method.md), and every parameter is documented in full in
[PROJECT.md](../PROJECT.md).

> [!NOTE]
> **If Resolve is unfamiliar.** Grading in Resolve happens on the Color page,
> where processing is arranged as a chain of **nodes**, each applying one
> operation, connected left to right. Add a node to the end of the chain by
> pressing **Alt+S** (Option+S on macOS), or by right-clicking the node graph
> and choosing **Add Node → Serial**. A `.cube` table is applied to the
> selected node by right-clicking it and choosing the file from the **LUT**
> submenu. A `.dctl` file is applied by adding the **DaVinci CTL** effect to
> the node from the Effects library, then selecting the file from that
> effect's dropdown. The numbered lists below give one node each, in order.

---

## Installing the tables

Download the `.cube` files for the stock being graded from the
[latest release](../../../releases/latest). They are attached to the release
rather than committed to the repository because they total roughly 280 MB.

Open **Project Settings → Color Management** and use the **Open LUT Folder**
button, then copy the `.cube` files into the folder that opens. Copy the
contents of this repository's `dctl/` directory into the same folder, so that
Resolve can find the DCTL nodes. Return to Resolve and click **Update Lists**.

In the same settings page, set **3D Lookup Table Interpolation** to
**Tetrahedral**. Trilinear interpolation, the default in some versions,
introduces visible error on tables of this kind.

---

## Scanning a roll

Two programs run before Resolve, in this order.

```
raw captures  →  raw_to_exr.py  →  linear EXRs      ─┐
                                                     ├→  Resolve
              →  roll_anchor_gui.py  →  Dmin R/G/B  ─┘
```

`engine/scan/raw_to_exr.py` converts the three narrowband exposures of each
frame into ZIP-compressed half-float linear EXR files, a precision of
approximately 0.0002 D. EXR is preferred to 32-bit float TIFF because Resolve
imports it unmodified, applying no implicit transform on the way in.

```bash
python3 engine/scan/raw_to_exr.py                    # interactive
python3 engine/scan/raw_to_exr.py --in-dir /path/to/roll --mode superpixel --flats skip
```

A sensor with no colour filter array, native or stripped, uses
`engine/scan/mono_to_exr.py` instead, which takes no mode and reads at full
resolution. Everything downstream of the converter is identical.

It accepts `.dng`, `.arw`, `.arq`, `.cr2`, `.cr3`, `.nef` and `.nrw`. Choose
`--mode superpixel` for ordinary single-shot captures, which are binned 2×2 to
half resolution, and `--mode pixelshift` for a per-site composite such as a
Sony `.ARQ`, which retains full resolution. Files are routed by what they
actually contain rather than by extension, and a file whose structure does not
match the requested mode is refused with an explanation rather than decoded
into a plausible-looking error.

`engine/scan/roll_anchor_gui.py` then measures the roll against two frame sets,
plain light and the clear developed leader, and writes
`builds/anchors/<roll-id>.json`. It copies the values required by Resolve to
the clipboard.

```bash
python3 engine/scan/roll_anchor_gui.py               # fully graphical
```

Its raw-capture input reads each LED's frame through the matching colour plane
of the filter array and is therefore a colour-sensor path. A monochrome sensor
has no such planes, so a monochrome roll is anchored from the merged EXRs that
`mono_to_exr.py` writes, which is the primary input in either case.

Run with no arguments, it asks whether the frames are merged EXRs or raw
captures, collects them one LED channel at a time so that the order cannot be
scrambled, asks whether a D-max patch is to be measured, and then opens one
region-of-interest picker per frame set. Each picker shows a log-scaled
preview, a live histogram of the selected region, and a warning when that
region contains a second population of pixels, which is what a film box or
gate edge inside the box looks like. The measured boxes are written into the
anchor file as an audit record.

[PROJECT.md](../PROJECT.md) documents both programs in full, under **Per-roll
anchoring** and **Roll-anchor GUI**: the command-line options, the
region-of-interest procedure and its contamination test, the normalisation of
differing exposure times, and the portions of the decode path that remain
untested. No ISO value is tested against a list, so any camera's base ISO is
accepted; ISO simply has to stay the same across a frame set, and a difference
is warned about.

One point is restated here, because the error it prevents is the most
consequential available at this stage.

> [!WARNING]
> The anchor file reports D-min against two zero points. Enter
> **`dmin_exr_scale`** into `RollAnchor_ScanPrep.dctl` when grading EXR files
> from `raw_to_exr.py`. The plain-light `dmin` values over-anchor the image:
> green and blue are driven past the pre-shaper's density-zero clamp, and the
> frame returns strongly yellow-green after decoding. On this apparatus the two
> scales differ by approximately +0.24, +0.58 and +0.93 D in R, G and B, so the
> error is a large one. The EXR-scale values are valid only if the anchor frames
> were exposed at the roll's own per-channel exposure and at the same ISO.

---

## Resolve node chains

Each process has its own chain, and the chains are **not interchangeable**: the
shaper pair, the corridor value and the table must all correspond. Mixing
elements between chains produces a plausible-looking but incorrect image.

Every path expects the same two things before node 1, both from
[Scanning a roll](#scanning-a-roll): the **linear EXR files**, and this roll's
**`dmin_exr_scale`** values entered into `RollAnchor_ScanPrep.dctl`. Load every
table on a node of its own, with **tetrahedral** interpolation.

### C-41, colour negative

```
1  RollAnchor_ScanPrep.dctl        enter this roll's EXR-scale Dmin R/G/B
                                   (for C-41 this also removes the orange colouration)
2  CPD Pre-shaper.dctl             VALUE_BOXes remain at 1.0, as anchoring is done upstream
3  <Stock>_StatusM.cube            scanner density to Status M
4  Print Adjustment.dctl           OPTIONAL; the defaults leave the image unchanged
5  <Stock>_to_<Paper>_DisplayP3.cube    Status M to RA-4 print to Display P3
6  grade
```

| | |
|---|---|
| **Corridor** | 3.30. The CPD shaper pair and both tables must agree on this value |
| **Paper pairing** | Kodak stocks use the Endura tables, Fujifilm stocks the Pro Laser tables |
| **One stock, both tables** | Mixing stocks between nodes 3 and 5 mis-tones the image without any visible warning, because each table encodes its own D-min and characteristic curve |
| **HDR** | Replace node 5 with the corresponding `…_P3D65_PQ203.cube` and set the timeline to P3-D65 ST2084. Same position, different table |
| **Node 4 placement** | If used, it must precede the print table, so that it drives the print in the manner of an enlarger rather than correcting the print afterwards |
| **Quality-control tap** | Stopping after node 3 and multiplying by 3.30 yields Status M density, directly comparable with the datasheet curves |

The output of node 5 is **Display P3 (D65), sRGB-encoded and clipped to
[0,1]**, as stated in every cube header. It is therefore a display encoding
rather than linear data, and it replaces the postshaper and linearisation
stages that the other two chains require. Mid-grey arrives encoded: feeding the
table a neutral k = 0.22 returns 0.4613, which is 18% grey carried through the
sRGB transfer function. Do not add a colour space transform after this node in
the belief that its output is scene-linear.

#### What each node does

One frame of Portra 400, written out as it arrives and again after each node in
the chain above. The panels carry their own numbering: panel 1 is the scan
before any node, and panels 2 to 5 follow nodes 1, 2, 3 and 5 respectively.
Node 4, `Print Adjustment`, has no panel of its own, because its defaults leave
the image unchanged and it would reproduce panel 4 exactly. The D-min values
are read from the roll's anchor measurement rather than from anything in the
picture.

<img src="figures/c41-node-plate.jpg" alt="Six panels of the same fairground scene. Panels one and two are orange negatives, the second slightly less orange than the first. Panel three is a dark, low-contrast positive. Panel four is similar to three. Panel five is a bright, saturated print. Panel six is the delivered frame, slightly warmer and darker than five.">

1. **Linear scan.** The EXR as delivered by `raw_to_exr.py`. A negative, orange
   throughout.
2. **Roll anchor**, `RollAnchor_ScanPrep.dctl`. Each channel multiplied by
   10<sup>Dmin</sup>, which for this roll is ×1.799, ×2.006 and ×2.045. The
   film base now reads density 0.
3. **Pre-shaper**, `CPD Pre-shaper.dctl`. Negative base-ten logarithm, divided
   by the 3.30 corridor, clamped to [0,1]. **The positive appears here.**
4. **Status M table**, `Portra400_StatusM.cube`. Scanner density mapped to
   Status M, the standard in which the datasheet curves are measured.
5. **Print table**, `Portra400_to_PortraEndura_DisplayP3.cube`. Status M
   density through RA-4 print emulation to Display P3.
6. **As delivered.** Panel 5 with the photographer's own `Print Adjustment`
   settings and grade applied, the gamma about the pivot lowered to soften
   contrast, as published under
   [Sample results](../README.md#sample-results).

Three things in that sequence are worth naming, because each is easy to
misread from the node list alone.

**The inversion is the logarithm.** Panels 1 and 2 are negatives; panel 3 is a
positive, and nothing between them inverts anything. Density rises with
exposure, so taking −log₁₀ of transmittance produces a positive by definition.
No stage in this project ever performs a tone flip.

**The anchor is a measurement, and it barely looks like anything.** Its three
gains share a common factor of roughly 1.8, which is exposure normalisation.
Only the residual differences carry the orange removal: green and blue exceed
red by 11.6% and 13.7% respectively. That is the entire mask correction for
this roll, and it is visually slight, which is the reason the sliders must be
pasted from the anchor engine rather than adjusted until the image looks
neutral.

**A negative occupies little of the corridor.** This frame runs to a maximum
density of 2.15 against a corridor of 3.30, with a median of 0.53, so panels 3
and 4 are legitimately dark. A further 0.33% of pixels read below the roll's
D-min and are clamped to zero, which is the pre-shaper behaving as designed
rather than a defect.

> [!NOTE]
> Regenerate this plate with `engine/c41/render_stage_figure.py`, which reads
> the DCTL arithmetic and both tables directly; `--write-panels` additionally
> writes each stage as its own file. The roll's anchor measurement is committed
> beside the figure as
> [`figures/portra400-roll-anchor.json`](figures/portra400-roll-anchor.json).
> The 39 MB source EXR is not held in this repository, so the plate cannot be
> rebuilt from a clone alone.

### ECN-2, Kodak Vision3

```
1  RollAnchor_ScanPrep.dctl        enter this roll's EXR-scale Dmin R/G/B
2  CPD Pre-shaper.dctl             VALUE_BOXes remain at 1.0
3  Vision3 to Cineon PD.cube       scanner density to RP 180 printing density
4  CPD Postshaper.dctl             Encode ON, producing normalised Cineon code value
5  Printer Lights Cineon.dctl      begin from the stock preset in the DCTL header
6  display transform               CST (Cineon Film Log to timeline), then grade
```

| | |
|---|---|
| **Corridor** | 3.30, shared with the C-41 path, as are nodes 1 and 2 |
| **One table, four stocks** | 50D, 200T, 250D and 500T all use the same table |
| **Printer lights** | In practice these are required: a raw Cineon decode always needs them. The DCTL header carries a per-stock datasheet preset as a starting point |
| **HDR alternative** | A stock Kodak 2383 print-emulation LUT may replace the CST at node 6, *in place of it and never in addition to it*. That LUT is third-party and is **not** included in this repository or its releases |

### E-6, reversal film

```
1  RollAnchor_ScanPrep.dctl        enter this roll's EXR-scale Dmin R/G/B
2  Preshaper 5.0.dctl              match the pair to the table, see below
3  <Stock>_XYZ_D50.cube            scanner density to white-relative D50 XYZ
4  Postshaper 5.0.dctl             × 5.0, returning to density
5  Density to Linear.dctl          10^-D; leave its trims at their defaults here
6  XYZ D50 to DWG.dctl             an explicit 3×3; do NOT substitute a Resolve CST
7  grade
```

| | |
|---|---|
| **Corridor** | **5.0** for the published tables, which are built for a monochrome sensor, and **5.25** for this project's own a7R III build. The two are not interchangeable, and the pre- and postshaper must match the table: a mismatch rescales density silently. Narrowband scan density exceeds the film's Status A density, so a corridor must never be inferred from physical D-max. A table rebuilt for another camera needs its own value, which `reversal_transform.py` prints on every build |
| **Why not a CST at node 6** | The table's output is *white-relative* XYZ rather than true CIE XYZ, so Resolve's colour space transform cannot convert it correctly whatever its white-adaptation setting reports |
| **Where trims belong** | After node 6, rather than on XYZ channels, which is why the built-in offsets in node 5 remain at their defaults |

> [!NOTE]
> Every node between the pre-shaper and the linearisation node appears inverted
> or negative on the viewer. This is expected: the image is in density space at
> that point and has not yet been rendered.

## The print look is a choice

The pairing rule, Kodak to Endura and Fujifilm to Pro Laser, is what makes the
print *metrically* faithful. It reproduces the paper a laboratory would
actually have used, so the result is a defensible simulation of that specific
print. It carries no obligation.

Print emulation is a look, and looks are a matter of preference. Crossing the
pairing deliberately, substituting a print-emulation LUT of another design, or
omitting the print stage and grading from density are all legitimate choices.
The claim that the output corresponds to a specific paper is forfeited; nothing
else changes, and nothing upstream is affected.

Stopping before the print stage yields the following in each process:

| Process | Without print emulation |
|---|---|
| **C-41** | Node 3 multiplied by 3.30 is Status M density, a defined and published metric, though not a viewable image. Grading from it is a deliberate choice, and the inversion and the look then fall to the colourist to supply |
| **ECN-2** | The CST decode at node 6 *is* the route without a print look: Cineon Log to the timeline, ready to grade. A print-emulation LUT replaces it only if that look is wanted |
| **E-6** | There is no print stage. Reversal film is viewed directly, so the chain is colorimetric throughout |

---

The reasoning behind each stage is set out in [method.md](method.md), and every
parameter of every node, together with the known systematics of the pipeline,
is documented in [PROJECT.md](../PROJECT.md).
