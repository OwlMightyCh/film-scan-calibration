#!/usr/bin/env python3
"""Re-encode the Kodak 2383 print-film-emulation cube from its native
P3-D65 / Gamma 2.6 (DCI, 48-nit-referenced) OUTPUT to P3-D65 / PQ (ST2084),
for HDR delivery of the Vision3 negative path.

The primaries are unchanged (P3-D65 -> P3-D65), so this is purely a per-channel
transfer-function remap baked into every LUT entry:
    gamma 2.6 decode  ->  linear exposure scale S  ->  PQ (ST2084) encode.
Baking it in lets the single LUT be the whole display transform: no separate
"Gamma 2.6 -> ST2084" CST, whose uncontrolled luminance anchor (mapping the
film's reference white toward PQ's 10000-nit ceiling) was the cause of the
over-bright, over-contrasty result.

Brightness is set by anchoring a DIFFUSE-WHITE input code to an absolute nit
level (NOT the container peak), so the print's highlight roll-off sits above
reference white where HDR headroom belongs. Default: diffuse white (Cineon
~90% white, code 0.67) -> 203 nits, ITU-R BT.2408 HDR reference white — the
project's chosen Vision3 HDR-delivery target.

Input LUT expected: "DCI-P3 Kodak 2383 D65.cube" at the repo root (Cineon Log
in, 33^3). Output: builds/pfe/DCI-P3 Kodak 2383 D65 PQ dw<nits>nit.cube.

Usage: python3 engine/ecn2/pfe_to_pq.py [diffuse_white_nits] [diffuse_white_cineon_code]
"""
import sys
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "DCI-P3 Kodak 2383 D65.cube"
OUTDIR = ROOT / "builds" / "pfe"

DW_NITS = float(sys.argv[1]) if len(sys.argv) > 1 else 203.0
DW_CODE = float(sys.argv[2]) if len(sys.argv) > 2 else 0.67      # Cineon ~90% white (685/1023)

# ---- ST 2084 (PQ) inverse EOTF: absolute cd/m^2 -> normalized code 0..1 ----
sys.path.insert(0, str(ROOT))
from engine.common.spectral import pq_encode   # noqa: E402

# ---- parse source cube ----
vals, size = [], None
for line in SRC.read_text().splitlines():
    s = line.strip()
    if s.startswith("#") or not s:
        continue
    if s.startswith("LUT_3D_SIZE"):
        size = int(s.split()[-1]); continue
    if s[0].isalpha():
        continue
    p = s.split()
    if len(p) == 3:
        vals.append([float(x) for x in p])
lut = np.array(vals)
N = size
lut3 = lut.reshape(N, N, N, 3)
# P3-D65 luminance weights. Load-bearing: neutral_relY() uses them to read the
# diffuse-white luminance off the neutral axis, which sets the exposure scale S
# applied to every LUT entry.
YCOEF = np.array([0.2290, 0.6917, 0.0793])

def neutral_relY(code):
    """Relative (gamma-2.6-decoded) luminance of the neutral axis at a Cineon code."""
    x = code * (N - 1)
    j = int(np.floor(x)); f = x - j
    j2 = min(j + 1, N - 1)
    o = lut3[j, j, j] * (1 - f) + lut3[j2, j2, j2] * f
    return float((np.clip(o, 0.0, None) ** 2.6) @ YCOEF)

# ---- linear exposure scale from the diffuse-white anchor ----
S = DW_NITS / neutral_relY(DW_CODE)

# ---- remap every entry: gamma2.6 decode -> scale -> PQ encode (primaries fixed) ----
pq = pq_encode((np.clip(lut, 0.0, None) ** 2.6) * S)

OUTDIR.mkdir(parents=True, exist_ok=True)
OUT = OUTDIR / f"DCI-P3 Kodak 2383 D65 PQ dw{DW_NITS:g}nit.cube"
with open(OUT, "w") as f:
    f.write("# Kodak 2383 film look, re-encoded to P3-D65 PQ (ST2084) for HDR delivery\n")
    f.write("# Input : Cineon Log (float 0.0-1.0) -- unchanged from source\n")
    f.write("# Output: P3-D65 primaries, ST2084/PQ transfer\n")
    f.write(f"# Anchor: diffuse white (Cineon {DW_CODE:g}) = {DW_NITS:g} cd/m2; "
            f"source Gamma 2.6 decoded, linear scale {S:.1f}, PQ encoded\n")
    f.write("# Use as the sole display transform: no CST after this LUT; interpret output as P3-D65 PQ.\n")
    f.write(f"LUT_3D_SIZE {N}\nLUT_3D_INPUT_RANGE 0.0 1.0\n")
    for v in pq:
        f.write(f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")

# ---- self-reported audit metrics ----
def nits_at(code):
    return neutral_relY(code) * S
print(f"wrote {OUT.relative_to(ROOT)}   (linear scale S={S:.1f}; diffuse white Cineon {DW_CODE:g} -> {DW_NITS:g} nits)")
print(f"  black (in 0.00)        : {nits_at(0.0):8.3f} nits")
print(f"  18% gray (Cineon 0.435): {nits_at(0.435):8.2f} nits")
print(f"  diffuse white ({DW_CODE:g})   : {nits_at(DW_CODE):8.2f} nits")
print(f"  print peak white (1.00): {nits_at(1.0):8.2f} nits   (PQ code {float(pq_encode(nits_at(1.0))):.4f})")
print(f"  serialized entries: {len(pq)}  range [{pq.min():.4f}, {pq.max():.4f}]")
