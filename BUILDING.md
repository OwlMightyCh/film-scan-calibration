# Building the cubes

Every LUT under `builds/` is produced by a script in `engine/`. This file
records the command behind each one, the flags that change what is produced,
and the check that confirms a build is correct; `PROJECT.md` holds the method
and the reasoning. Run every command from the repository root. Each engine
self-reports its accuracy metrics on stdout, and those lines are the
deliverable of a build: a build is not finished until they have been read.

## The engines

| Engine | Produces | Cubes |
|---|---|---|
| `engine/c41/c41_statusm_engine.py` | C-41 scanner density to Status M density | 12 |
| `engine/c41/endura_print_engine.py` | Kodak negative printed on Portra Endura | 14 |
| `engine/c41/fuji_print_engine.py` | Fujifilm negative printed on Fuji Pro Laser | 10 |
| `engine/reversal/reversal_transform.py` | reversal scanner density to D50 XYZ colorimetric density | 4 |
| `engine/ecn2/adx_engine.py` | Vision3 scanner density to ADX16 over Academy Printing Density, the primary route | 1 |
| `engine/ecn2/v3_scene_engine.py` | Vision3 scanner density to scene-linear DaVinci Wide Gamut, per stock | 4 |
| *(an unpublished scene-referred engine)* | the C-41 scene-referred DWG artifact | 1 |

Those forty-six are the cubes recorded in `builds/cube_manifest.json`.

## C-41 negative: scanner density to Status M

One engine, parameterised by `--stock`. Twelve stocks, one cube each, written
to `builds/c41/<Prefix>_StatusM.cube`.

```
for s in portra400 portra160 ektar100 gold200 ultramax400 proimage100 \
         portra800 fujifilm400 fujifilm200 fujicolor100 superiapremium400 pro400h; do
  python3 engine/c41/c41_statusm_engine.py --stock "$s"
done
```

`--dye-json` and `--out-cube` override the dye data and the destination for a
basis-sensitivity ensemble run; the engine refuses either one alone, so an
ensemble build can never land on top of a canonical cube.

The engine reads the stock's traced D-min spectrum as well as its dye set: the
roll anchor divides the base and orange mask out of the frame in integrated
density, so the cube inverts the LEDs as seen through the mask, and the
self-report prints the centroid shift the mask imposes on each LED together
with a neutral-axis closure that reads the full traced midscale with the bare
LEDs and anchors it the way the DCTL does. That closure is the fit's own
Status M residual when everything is consistent.

Fujifilm 200 and Fujifilm 400 share a dye set, so their two cubes have
identical numeric payloads and differ only in the display name on the header
comment. The manifest hashes the payload alone and records one hash for both;
that is the expected result, not a collision.

## C-41 print emulation: negative to RA-4 paper

Each print run emits **two** cubes, a Display P3 SDR cube and a P3-D65 PQ cube
referenced to 203 nits. Both chain **after** the matching
`<Prefix>_StatusM.cube`, whose output domain is their input domain. The
pairing rule is fixed, Kodak negatives on Kodak paper and Fujifilm negatives
on Fuji paper, and `argparse` rejects any other combination.

```
for s in portra400 portra160 ektar100 gold200 ultramax400 proimage100 \
         portra800; do
  python3 engine/c41/endura_print_engine.py --stock "$s"
done
for s in fujifilm400 fujifilm200 fujicolor100 superiapremium400 pro400h; do
  python3 engine/c41/fuji_print_engine.py --stock "$s"
done
```

Outputs land in `builds/c41/print_endura/` and `builds/c41/print_fuji/`. Two
lines of the self-report carry the print model's health. `paper tables`
reports the neutral-scale Status A solve that turns the paper's three
characteristic curves into per-layer amount tables (it closes to machine
precision) and how much of the lattice runs off those tables. `gray-axis lock
over the printable window` reports, per layer, the mean of the lock's
correction, which is enlarger filtration, and its range, which is tone
remapping no filter pack could apply and therefore the shape error the lock
absorbs on the neutral axis; a range that grows after an edit is the signal
to look for.

## ECN-2 negative

Two routes from the same input point (normalised scanner density, D-min
excluded, OD/3.30). The ADX16 route is the route for Vision3: a single
stock-blind cube on the shared family-average dye basis, landing the scan on
ADX16 (SMPTE ST 2065-3) code values over Academy Printing Density as the entry
into the Academy decode `ADX16_to_ACES`; PROJECT.md carries the route's
accuracy bound.

```
python3 engine/ecn2/adx_engine.py [--sensor <camera>] [--out-cube P]
python3 engine/ecn2/adx_validate.py [--sensor <camera>]
```

The validator scores the decoded result against the scene engine's truth;
read its dE2000 lines. In Resolve the ADX16 cube is followed by "Printer
Lights ADX16.dctl", then decoded with input colour space ADX (16-bit); the
DCTL header carries the chain and the trim semantics. The ADX16 engine prints
a neutral-axis check per stock, read with the bare LEDs and anchored as the
DCTL does, and a family-mask bound per stock; read both after any change to
the mask or the dyes.

The scene-linear route is the secondary, scene-referred path, per stock
(characteristic curves and spectral sensitivities differ where the ADX16
synthesis is stock-blind), each cube ending in scene-linear DaVinci Wide
Gamut (D65):

```
for s in 50D 250D 200T 500T; do
  python3 engine/ecn2/v3_scene_engine.py --stock "$s"
done
```

The engine prints the Status M of the stock's traced Minimum Density curve
against the characteristic sheet's own D-min triplet (two charts, one
quantity), its matrix-fit residuals, the neutral amount tables' closure on all
three characteristic curves, the neutral-axis exposure ramp, the corridor
requirement and a trilinear LUT-versus-exact-chain probe, the latter split
by lattice cell (clean cells, whose eight corners all solved within the
published curves, against cells touching a table's end clamp or an unsolved
node), binned by exact-chain luminance, closed with a declared operating
region, and followed by an endpoint assertion that the inverse lookup clamps
at both ends of every table. The ColorChecker "full chain" line is a plumbing
check only, forward and inverse sharing machinery; the D-min comparison is the
check against the sheet, and the table closure is a consistency check on the
solve, since it closes on the curves it was solved from. The tungsten stocks are fitted under a 3200 K blackbody scene
illuminant, the daylight stocks under D55, both Bradford-adapted to D65.
Outputs of both routes land in `builds/ecn2/`.

## Reversal: scanner density to D50 XYZ

Four builds, selected by a positional name rather than a flag.

```
for b in velvia100-narrowband-d50 velvia50-narrowband-d50 \
         provia100f-narrowband-d50 ektachrome-narrowband-d50; do
  python3 engine/reversal/reversal_transform.py "$b"
done
```

Reversal is the only route whose density corridor is a build parameter (see
**The reversal corridor**). Each build ends with three lines that are checks
against the sheet rather than against the model. `sheet closure` reads the
stock's traced characteristic curves, subtracts the sheet's D-min per channel
in integrated density and solves the three curves together into dye amounts
through the Status A responsivities: read the residual (machine precision),
the amount floor (a negative amount means the traced dyes cannot form the
sheet's neutral) and the count of rises with exposure. `sheet neutral on the
D50 table` is that series' a\*/b\* through the cube's own observer; it is not
zero on any stock, and PROJECT.md register #19 says what is known about why.
`base term` bounds the roll anchor's integrated D-min subtraction under a
surrogate tint through the sheet's D-min triplet (register #17). The `written
cube on the sheet neutral` line is plumbing only.

## The legacy artifact

`builds/c41/Portra400_StatusM_to_DWG.cube` comes from an unpublished
scene-referred engine. It is the C-41 branch's only scene-referred artifact
and is kept because nothing else occupies that role there; print emulation is
the C-41 delivery route. The ECN-2 branch's per-stock scene-referred cubes
come from a live, published engine and are its route.

## Per-camera builds

`--sensor` presumes a particular camera in front of the film. The default,
`none`, is a unity response at every wavelength, which makes the scanner
weights the illuminant alone; that is the canonical, shipped build, and
naming a body is strictly opt-in. Four engines accept it:
`c41_statusm_engine.py`, `reversal_transform.py`, `adx_engine.py` and
`v3_scene_engine.py`. The RA-4 print engines do **not** and need not: their
input domain is normalised Status M density, which the scan cube has already
delivered, so a print cube is independent of the capture sensor, and a
per-camera fleet is twenty-one cubes, not forty-five.

The value is a bare name resolved against `data/cameras/`, so
`data/cameras/Fujifilm_GFX_100_ssf.json` is named as `Fujifilm_GFX_100`. A
value containing a path separator or ending in `.json` is taken as given.

### Bodies held

Forty-four, named as `--sensor` expects them. Several stand in for a sibling
sold under another name, and `data/cameras/index.json` records those aliases
in full.

**Canon**, twenty-one: `Canon_Digital_Rebel_XTi` (EOS 400D, Kiss Digital X),
`Canon_EOS_5D`, `Canon_EOS_5D_Mark_II`, `Canon_EOS_5D_Mark_III`,
`Canon_EOS_5D_Mark_IV`, `Canon_EOS_5DS` (also 5DS R), `Canon_EOS_100D`
(Rebel SL1, Kiss X7), `Canon_EOS_200D` (Rebel SL2, Kiss X9),
`Canon_EOS_200D_II` (EOS 250D, Rebel SL3, Kiss X10), `Canon_EOS_600D`
(Rebel T3i, Kiss X5), `Canon_EOS-1D_X_Mark_II`, `Canon_EOS-1Ds_Mark_II`,
`Canon_EOS-1Ds_Mark_III`, `Canon_EOS_M`, `Canon_EOS_R`, `Canon_EOS_R5` (also
R5 C), `Canon_EOS_R5m2`, `Canon_EOS_R6`, `Canon_EOS_R6m2` (also EOS R8),
`Canon_EOS_R10` (also EOS R50) and `Canon_EOS_RP` (also EOS 6D Mark II).

**Nikon**, eleven: `Nikon_D70`, `Nikon_D200`, `Nikon_D700`, `Nikon_D3300`,
`Nikon_D5100`, `Nikon_D5300`, `Nikon_D7000`, `Nikon_D800E` (also D800),
`Nikon_D810`, `Nikon_D850` and `Nikon_Z_f` (also Z 6II).

**Sony**, ten: `Sony_ILCE-6400`, `Sony_ILCE-7M3`, `Sony_ILCE-7M4`,
`Sony_ILCE-7CM2`, `Sony_ILCE-7RM2`, `Sony_ILCE-7RM3` (also 7R III A),
`Sony_ILCE-7RM4` (also 7R IV A and 7R V), `Sony_ILCE-7SM2`, `Sony_ILCE-7SM3`
and `Sony_ILCE-9`.

**Fujifilm**, one: `Fujifilm_GFX_100` (also GFX 100S). The X-series bodies are
excluded because X-Trans has no 2×2 colour filter pattern.

**Panasonic**, one: `Panasonic_DC-GX9`.

A named sensor writes to `builds/sensor-<Body>/<route>/`, beside and never on
top of the canonical cube, and stamps `# sensor: <file>` into the header. That
tree is excluded by `.gitignore`, so per-camera builds are local artifacts and
deliberately absent from `builds/cube_manifest.json`; the manifest check
reports cubes under `builds/sensor-*/` as one summary line per sensor
directory rather than as ORPHANs, and does not fail on them
(`--strict-orphans` restores the per-cube listing and the failing exit).

```
S=Fujifilm_GFX_100
for b in velvia100-narrowband-d50 velvia50-narrowband-d50 \
         provia100f-narrowband-d50 ektachrome-narrowband-d50; do
  python3 engine/reversal/reversal_transform.py "$b" --sensor "$S"
done
for s in portra400 portra160 ektar100 gold200 ultramax400 proimage100 \
         fujifilm400 fujifilm200 fujicolor100 superiapremium400 pro400h; do
  python3 engine/c41/c41_statusm_engine.py --stock "$s" --sensor "$S"
done
for s in 50D 250D 200T 500T; do
  python3 engine/ecn2/v3_scene_engine.py --stock "$s" --sensor "$S"
done
python3 engine/ecn2/adx_engine.py --sensor "$S"
```

A named-sensor build is regenerated from the same engines as the shipped set,
so a change to any engine that consumes `PHI` stales it alongside the shipped
cubes: rerun the loops above whenever the manifest check reports CHANGED on
the corresponding shipped cube.

## The reversal corridor

The corridor is the density range the reversal cube spans. It is an explicit
build parameter and is **not** inferred from a stock's physical dye Dmax. Cube
input and output are both scaled by it, so it must match the shaper DCTL pair
in force; crossing corridors rescales density silently and produces no error.
`resolve_corridor` decides which value applies:

| `--sensor` | corridor |
|---|---|
| `none` | the config value carried on each `BuildConfig` |
| any named camera | `BAYER_CORRIDOR_DEFAULT` |
| either, with `--corridor` given | the explicit value, which wins outright |

A Bayer CFA concentrates each channel's weight where its own dye is dense, so
the same dye stack reads deeper than it does under a unity response, which is
why a named camera takes a wider corridor than the sensor-free build. The
default is **not** a general Bayer constant: every body has to be measured the
same way.

### Determining the corridor for a new camera

Every reversal build prints the corridor in force and what the stock requires:

```
<build>: corridor 5.25 D; this stock needs 5.08 D at dye 4.0
```

The requirement is the peak scanner density the stock puts out anywhere in
the dye 0 to 4.0 box, probed over its corners, faces and a coarse interior
lattice, not merely along the neutral axis: an off-neutral stack can read
deeper in a single channel than a neutral one. The procedure:

1. Build all four stocks with the new `--sensor` and record the requirement
   each one prints.
2. Take the maximum over the four. The corridor is that value rounded up to
   the next 0.25 D step, which is what the engine suggests in its own warning
   line when a corridor clips.
3. Confirm a shaper pair exists for that value in `dctl/shapers/`. If not, add
   a matching `Preshaper X` and `Postshaper X`.
4. Rebuild all four at the chosen value, so the whole fleet shares one
   corridor and one shaper pair.

Choose the **smallest** step that clips nothing: a wider corridor clips
nothing either, but at a fixed 65 cubed grid it spends node spacing for
headroom no stock uses. The serialised RMSE printed by the self-check will not
settle this question, since it draws uniform samples over the dye box and the
corner where a slightly narrow corridor clips is a vanishing fraction of such
a draw; judge the corridor by the printed requirement.

## Verifying a build

The check is the cube manifest, which hashes numeric payloads only, so a
changed header comment does not register as drift:

```
python3 scripts/cube_audit.py manifest --check builds/cube_manifest.json
```

A change is correct when it reports CHANGED on exactly the cubes it should
have moved and MATCH on every other. Re-record only once the CHANGED set is
the intended one, and never to make an unexplained difference go away. The
sweep for unrecorded cubes reports each as ORPHAN, except per-apparatus builds
under `builds/sensor-*/`, which appear as one summary line per sensor
directory without failing the check (`--strict-orphans` lists and fails them
too). The swept directory is the deepest one containing every recorded path,
printed as `orphan sweep: <dir>`; `--root DIR` widens it.

Alongside the manifest, read the metric lines each engine prints.
`cube_audit.py` also offers `validate`, `sample` and `compare` subcommands for
inspecting a single cube or diffing two.
