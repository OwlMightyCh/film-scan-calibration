#!/usr/bin/env python3
"""Shared DIR / interimage-inhibition helper for the colour-negative engines.

Interimage (DIR-coupler) inhibition is modelled as a single 3x3 matrix acting in
dye-amount space: developed dye = DIR_MATRIX @ pre_coupler dye.  Because the
datasheet neutral characteristic curves already embody the real film's coupler
behaviour, the neutral axis must be preserved exactly: the pre-coupler curves are
back-solved so that after applying DIR_MATRIX along the neutral ramp the
developed amounts reproduce the digitized datasheet amounts.

Callers guard on `is_identity(DIR_MATRIX)` so that the default (identity) path
skips this stage entirely and stays numerically bit-identical to today.

Scope, as of the current tree: the only LIVE caller is
engine/ecn2/v3_scene_engine.py.  engine/retired/cineon_pd_engine.py and
engine/retired/c41_scene_engine.py also use it but ship nothing.  No file under engine/c41/ has a DIR stage, so the live
C-41 print branch has no interimage structure, and neither does
engine/reversal/reversal_transform.py -- reversal interimage arises in the FIRST
developer rather than from DIR couplers, so this matrix would not model it in
any case.  See PROJECT.md register entries 8 and 11.
"""
import numpy as np


def is_identity(M):
    """True when M is (numerically) the 3x3 identity -> interimage disabled."""
    return np.allclose(np.asarray(M, float), np.eye(3))


def apply_dir(pre_amounts, DIR):
    """developed dye amounts = DIR @ pre-coupler amounts (row-wise, (...,3))."""
    return np.asarray(pre_amounts, float) @ np.asarray(DIR, float).T


def precompensate(developed_amounts, DIR):
    """pre-coupler amounts = inv(DIR) @ developed amounts (inverse of apply_dir).

    Used both to back-solve the neutral pre-coupler curves from the datasheet
    developed amounts and, in the inverse (density->exposure) chain, to strip the
    interimage effect back off measured developed dye."""
    return np.asarray(developed_amounts, float) @ np.linalg.inv(np.asarray(DIR, float)).T


def status_line(name, DIR):
    """One-line build-time report of interimage state for an engine."""
    if is_identity(DIR):
        return "%s interimage: off (identity)" % name
    return "%s interimage: ON  DIR_MATRIX=%s" % (name, np.round(np.asarray(DIR, float), 4).tolist())
