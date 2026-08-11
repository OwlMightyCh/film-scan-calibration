#!/usr/bin/env python3
"""Shared pdfminer vector-chart parsing helpers for the datasheet digitizers.

Previously copy-pasted across engine/c41/portra_digitize.py,
engine/c41/portra_digitize_sens.py and engine/c41/datasheet_forensics.py.
Everything here is device-space geometry: walking the layout tree, flattening
LTCurve paths, clustering tick labels and fitting the device->data affine.

This module imports pdfminer at module scope, so ONLY the digitizers and the
forensics tool import it.  The numeric engines must not: portra_stocks.py
deliberately imports pdfminer lazily, inside its two frame helpers, precisely so
that importing the stock registry from an engine never drags pdfminer in.
"""
import re

import numpy as np
from pdfminer.layout import LTChar


def walk(o):
    """Depth-first yield of every layout element, LTChars treated as leaves."""
    for e in o:
        yield e
        if hasattr(e, "__iter__") and not isinstance(e, LTChar):
            yield from walk(e)


def bezier(p0, p1, p2, p3, n=12):
    """Sample a cubic bezier at n points (endpoints included)."""
    t = np.linspace(0, 1, n)[:, None]
    mt = 1 - t
    return (mt**3) * p0 + 3 * (mt**2) * t * p1 + 3 * mt * (t**2) * p2 + (t**3) * p3


def polyline(curve):
    """Flatten an LTCurve path to a dense device-space polyline, subdividing
    any cubic-bezier ('c'/'v'/'y') segments; 'l'/'m' pass straight through."""
    pts = []
    cur = None
    for seg in curve.original_path:
        op, coords = seg[0], seg[1:]
        if op == "m":
            cur = np.array(coords[0], float)
            pts.append(cur)
        elif op == "l":
            cur = np.array(coords[0], float)
            pts.append(cur)
        elif op in ("c", "v", "y"):
            c = [np.array(p, float) for p in coords]
            if op == "c":
                p1, p2, p3 = c
            elif op == "v":
                p1, p2, p3 = cur, c[0], c[1]
            else:  # 'y'
                p1, p2, p3 = c[0], c[1], c[1]
            for q in bezier(cur, p1, p2, p3)[1:]:
                pts.append(q)
            cur = p3
        elif op == "h":
            pass
    return np.array(pts)


def cluster(vals, gap):
    """Group sorted scalar positions into clusters separated by > gap."""
    vals = sorted(vals)
    groups, cur = [], [vals[0]]
    for v in vals[1:]:
        if v - cur[-1] > gap:
            groups.append(cur); cur = []
        cur.append(v)
    groups.append(cur)
    return groups


def label_ticks(chars, axis, lo, hi, olo, ohi, gap=6, with_text=False):
    """Return [(position, value)] for numeric tick labels.

    axis='x': cluster LTChars by x, position = mean x; other axis window
    (olo,ohi) constrains the cross-axis band. axis='y': cluster by y.

    with_text=True instead returns [(position, value, text)] sorted by
    position -- the forensics dump needs the raw glyph text so a printed label
    can be compared with what was parsed out of it.  The digitizers serialize
    the 2-tuple form into their audit blocks, so that stays the default.
    """
    sel = [c for c in chars
           if (lo < c.x0 < hi if axis == "x" else olo < c.x0 < ohi)
           and (olo < (c.y0 + c.y1) / 2 < ohi if axis == "x" else lo < (c.y0 + c.y1) / 2 < hi)]
    if not sel:
        return []
    key = (lambda c: c.x0) if axis == "x" else (lambda c: (c.y0 + c.y1) / 2)
    sel.sort(key=key)
    groups = cluster([key(c) for c in sel], gap)
    out = []
    for g in groups:
        members = [c for c in sel if g[0] - 1e-6 <= key(c) <= g[-1] + 1e-6]
        members.sort(key=lambda c: c.x0)
        txt = "".join(c.get_text() for c in members)
        m = re.search(r"-?\d+\.?\d*", txt)
        if not m:
            continue
        pos = float(np.mean([key(c) for c in members]))
        out.append((pos, float(m.group()), txt.strip()) if with_text
                   else (pos, float(m.group())))
    if with_text:
        out.sort()
    return out


def affine_fit(ticks):
    """Fit data = slope*pos + intercept; return (slope, intercept, rms_data).

    Accepts (pos, value) or (pos, value, text) tuples -- only the first two
    fields are read.
    """
    p = np.array([t[0] for t in ticks]); v = np.array([t[1] for t in ticks])
    A = np.vstack([p, np.ones_like(p)]).T
    (slope, intercept), *_ = np.linalg.lstsq(A, v, rcond=None)
    rms = float(np.sqrt(np.mean((A @ [slope, intercept] - v) ** 2)))
    return float(slope), float(intercept), rms


def to_data(poly, mx, bx, my, by):
    """Apply the per-axis device->data affines to a device-space polyline."""
    return np.column_stack([poly[:, 0] * mx + bx, poly[:, 1] * my + by])


def resample_curve(dc, grid, extrapolate):
    """Sort a data-space curve by x and interpolate onto grid. When
    extrapolate is False, points outside the curve range are NaN.

    NOT the spectral `resample` in engine/common/spectral.py: different
    signature, different return type (this one also returns the measured
    (lo, hi) support), and the opposite edge rule -- NaN / flat-hold here,
    zero-fill there.
    """
    order = np.argsort(dc[:, 0])
    x, y = dc[order, 0], dc[order, 1]
    # collapse duplicate x
    xr = np.round(x, 6)
    ux = np.unique(xr)
    uy = np.array([y[xr == v].mean() for v in ux])
    lo, hi = ux[0], ux[-1]
    out = np.interp(grid, ux, uy)
    if not extrapolate:
        out = np.where((grid < lo - 1e-9) | (grid > hi + 1e-9), np.nan, out)
    return out, (float(lo), float(hi))
