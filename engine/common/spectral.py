#!/usr/bin/env python3
"""Shared spectral numerics for every engine in this repo.

Helpers that were previously copy-pasted across the C-41, ECN-2, print and
reversal engines.  Each one's EDGE BEHAVIOUR is the part that matters -- the
copies agreed on it, and a silent disagreement is exactly the class of bug the
byte-identity regression guard exists to catch (see the 400/700 nm light-leak
note in engine/c41/endura_print_engine.py).

  * resample   -- spectral regrid, ZERO outside the measured support.
  * resample_dye -- the same regrid for a negative's effective dye curves, which
                    keeps their negative samples.
  * interp_lin -- tone/curve regrid, TERMINAL-SLOPE LINEAR extension outside.
  * density    -- Beer-Lambert dye stack -> integrated density, general form.
  * pq_encode  -- ST 2084 inverse EOTF.

`resample` deliberately has NO default grid.  Three of the former copies
defaulted `g` to a module-global GRID and three did not; making the grid
explicit at every call site removes a whole class of "which grid was that?"
error and is why the parameter is required here.
"""
import hashlib
import os
from pathlib import Path

import numpy as np


def resample(w, v, g):
    """Interpolate spectrum (w, v) onto grid g, ZERO outside w's support.

    Beyond the measured wavelength support the value is 0, not the end value:
    no dye absorption, sensitivity or emission tail is ever synthesized.  The
    trailing clip at 0 also removes any negative excursion in the source data.

    Callers must pass g explicitly -- there is no default grid.
    """
    return np.clip(np.interp(g, w, v, left=0, right=0), 0, None)


def signed_dye():
    """False only under the FILM_CLIPPED_DYE=1 comparison scenario."""
    return os.environ.get("FILM_CLIPPED_DYE") != "1"


def resample_dye(w, v, g):
    """Resample a negative's effective dye curve onto grid g.

    The curve is a difference spectrum, dye minus consumed mask, so it can read
    below zero, and the dye fit keeps those samples. It stays ZERO outside w's
    support. FILM_CLIPPED_DYE=1 clips the samples at zero: a sensitivity scenario
    for a whole chain, never a release setting.
    """
    return np.interp(g, w, v, left=0, right=0) if signed_dye() else resample(w, v, g)


def dye_policy():
    """The header text naming the dye policy of a generated artefact."""
    return "dye policy: %s" % ("signed" if signed_dye() else "clipped")


def dye_stamp(dye_path):
    """Header text naming the dye policy and the dye data a table was built from."""
    p = Path(dye_path)
    return "%s; dye data: %s sha256:%s" % (
        dye_policy(), p.name,
        hashlib.sha256(p.read_bytes()).hexdigest()[:16])


def header_dye_stamp(cube_path):
    """The dye stamp in a cube's comment header, or None."""
    with open(cube_path) as f:
        for line in f:
            if not line.startswith("#"):
                break
            if "dye policy:" in line:
                return line[line.index("dye policy:"):].strip()
    return None


def interp_lin(x, xp, fp):
    """Interpolate with terminal-slope LINEAR extension beyond the ends (xp
    strictly increasing).

    The opposite edge choice to `resample`: this is for characteristic /
    tone curves, where running off the end of the digitized data must continue
    the local slope rather than collapse to zero.
    """
    x = np.asarray(x, float)
    y = np.interp(x, xp, fp)
    s0 = (fp[1] - fp[0]) / (xp[1] - xp[0])
    s1 = (fp[-1] - fp[-2]) / (xp[-1] - xp[-2])
    y = np.where(x < xp[0], fp[0] + s0 * (x - xp[0]), y)
    y = np.where(x > xp[-1], fp[-1] + s1 * (x - xp[-1]), y)
    return y


def density(weights, dye_amounts, dye_spectra):
    """Integrated density of a dye stack under a set of channel responsivities.

    weights      (n_channels, n_lambda) responsivities / weighting spectra,
                 already normalized however the caller wants (Pi-weighted
                 average: any common scale cancels).
    dye_amounts  (..., n_dyes) dye amounts; 1-D input is promoted to (1, n).
    dye_spectra  (n_dyes, n_lambda) unit-amount spectral densities.

    Returns (n_samples, n_channels) density.  Transmission is clipped at 1e-12
    before the log, which is the only guard against -inf at extreme dye loads.

    This is the GENERAL form.  The engines' one-line `statusm_fwd` / `scan_fwd`
    / `print_fwd` wrappers bind their module's own dye basis and responsivity
    set to it; the three former copies that closed over a module-global DYE now
    pass it explicitly.
    """
    dye_amounts = np.atleast_2d(dye_amounts)
    transmission = 10.0 ** (-(dye_amounts @ dye_spectra))
    return -np.log10(np.clip(transmission @ weights.T, 1e-12, None))


# ---- ST 2084 (PQ) inverse EOTF: absolute cd/m^2 -> normalized code 0..1 ----
_m1 = 2610 / 16384
_m2 = 2523 / 4096 * 128
_c1 = 3424 / 4096
_c2 = 2413 / 4096 * 32
_c3 = 2392 / 4096 * 32


def pq_encode(L):
    """Absolute luminance in cd/m^2 -> normalized PQ code 0..1.

    L is clamped to the 0..10000 nit container range before encoding.
    """
    Lp = np.clip(np.asarray(L, float) / 10000.0, 0.0, 1.0)
    return ((_c1 + _c2 * Lp**_m1) / (1.0 + _c3 * Lp**_m1)) ** _m2
