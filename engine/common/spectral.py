#!/usr/bin/env python3
"""Shared spectral numerics for every engine in this repo.

Four helpers that were previously copy-pasted across the C-41, ECN-2, print and
reversal engines.  Each one's EDGE BEHAVIOUR is the part that matters -- the
copies agreed on it, and a silent disagreement is exactly the class of bug the
byte-identity regression guard exists to catch (see the 400/700 nm light-leak
note in engine/c41/endura_print_engine.py).

  * resample   -- spectral regrid, ZERO outside the measured support.
  * interp_lin -- tone/curve regrid, TERMINAL-SLOPE LINEAR extension outside.
  * density    -- Beer-Lambert dye stack -> integrated density, general form.
  * pq_encode  -- ST 2084 inverse EOTF.

`resample` deliberately has NO default grid.  Three of the former copies
defaulted `g` to a module-global GRID and three did not; making the grid
explicit at every call site removes a whole class of "which grid was that?"
error and is why the parameter is required here.
"""
import numpy as np


def resample(w, v, g):
    """Interpolate spectrum (w, v) onto grid g, ZERO outside w's support.

    Beyond the measured wavelength support the value is 0, not the end value:
    no dye absorption, sensitivity or emission tail is ever synthesized.  The
    trailing clip at 0 also removes any negative excursion in the source data.

    Callers must pass g explicitly -- there is no default grid.
    """
    return np.clip(np.interp(g, w, v, left=0, right=0), 0, None)


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
