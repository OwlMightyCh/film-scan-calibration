"""Measure what 'Print Adjustment.dctl' does to the Endura print.

The DCTL is paper-agnostic; this check exercises it against the one paper that
exists so far, so the numbers below are Endura Premier's.

It sits BEFORE the print cube, on normalized Status M density k = OD/DMAX, so
this applies the DCTL's exact math to k and then prints the adjusted ramp
through the engine -- the same order the Resolve node chain uses.

READ-ONLY: reuses the engine's OWN neutral-ramp code path (dnorm_to_linP3 on
Dnorm = k*(1,1,1), the call behind the per-k neutral report in
endura_print_engine.main()).  Writes nothing; never calls the engine's main(),
so builds/ is untouched.

Sampling the ramp through the engine matters: neutral_basis is 'visual', so the
neutral axis is NOT equal-density in normalized Status M space and cannot be
re-derived by hand from R=G=B.

Run: python3 engine/c41/endura_trim_check.py
"""

import sys
import numpy as np
import colour
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from endura_print_engine import EnduraPrintEngine, DMAX

# printable neutral window, in normalized Status M density k = OD/DMAX
K_WIN_LO, K_WIN_HI = 0.082, 0.348
K_WIN_MID = 0.22                      # engine's calibrated mid-gray (renders Y=0.18)

P3_to_XYZ = np.array(colour.RGB_COLOURSPACES["Display P3"].matrix_RGB_to_XYZ)
D65 = colour.CCS_ILLUMINANTS["CIE 1931 2 Degree Standard Observer"]["D65"]


def trim(k, gamma=1.0, gain=0.0, pivot=0.22, trims=(0.0, 0.0, 0.0), literal=False):
    """Same math, same order, as the DCTL. k is (n,3) normalized density."""
    if gamma == 1.0 and gain == 0.0 and all(t == 0.0 for t in trims):
        return k
    if literal:
        out = (1.0 + gain) * np.power(np.maximum(k, 0.0), gamma)
    else:
        out = pivot + (k - pivot) * gamma + gain
    return np.clip(out + np.asarray(trims), 0.0, 1.0)


def render(eng, ks, **kw):
    """Trim the neutral ramp, then print it. Returns linear Display P3."""
    k3 = np.repeat(ks[:, None], 3, axis=1)
    lin, _, _, _ = eng.dnorm_to_linP3(trim(k3, **kw))
    return np.clip(lin, 0.0, 1.0)


def metrics(ks, lin):
    XYZ = lin @ P3_to_XYZ.T
    Y = XYZ[:, 1]
    w = (ks >= K_WIN_LO) & (ks <= K_WIN_HI)
    # k is normalized Status M density = OD/DMAX, so dividing the slope by DMAX
    # puts it back in print-density per negative-OD.  Y rises with k (denser
    # negative -> less paper exposure -> lighter print), so take the magnitude.
    slope = np.polyfit(ks[w], np.log10(np.maximum(Y[w], 1e-12)), 1)[0]
    gamma = abs(slope) / DMAX

    i_mid = int(np.argmin(np.abs(ks - K_WIN_MID)))
    Lab = colour.XYZ_to_Lab(XYZ[i_mid], D65)
    return gamma, float(Y[i_mid]), float(Lab[1]), float(Lab[2])


CASES = [
    ("baseline (no-op)",            {}),
    ("gain +0.010",                 dict(gain=+0.010)),
    ("gain -0.010",                 dict(gain=-0.010)),
    ("gamma 1.20",                  dict(gamma=1.20)),
    ("gamma 0.85",                  dict(gamma=0.85)),
    ("gamma 0.85 pivot 0.10",       dict(gamma=0.85, pivot=0.10)),
    ("literal gamma 0.90",          dict(gamma=0.90, literal=True)),
    ("literal gain +0.05",          dict(gain=+0.05, literal=True)),
    ("trim R+.005 B-.005",          dict(trims=(+0.005, 0.0, -0.005))),
    ("trim R-.005 B+.005",          dict(trims=(-0.005, 0.0, +0.005))),
]


def main():
    eng = EnduraPrintEngine()
    ks = np.linspace(0.02, 0.60, 241)
    print("%-24s %7s %9s %8s %8s" % ("case", "gamma", "Y(mid)", "a*(mid)", "b*(mid)"))
    for name, kw in CASES:
        g, ym, a, b = metrics(ks, render(eng, ks, **kw))
        print("%-24s %7.3f %9.4f %8.2f %8.2f" % (name, g, ym, a, b))


if __name__ == "__main__":
    main()
