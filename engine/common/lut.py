"""3D LUT sampling on the unit cube, the two schemes a LUT box offers.

One implementation for every engine: the reversal, C-41 and ECN-2 builds and
the error budget all validate a serialised cube through these. `pts` lies in
[0,1]^3 (normalised input density), `lut` is (S,S,S,3) indexed in input-channel
order (read_cube ends in .transpose(2,1,0,3) to get there).

The cell index is clamped BEFORE the fraction is taken, so at the top of the
domain the last cell's fraction is 1, not 0, and an identity LUT returns 1 at 1.

Trilinear error does not bound tetrahedral error or the reverse: the two
schemes agree only at nodes, on cell edges and on affine data (f = xy at a cell
centre gives 0.25 trilinear, 0.5 tetrahedral), so a deployment set to
tetrahedral (docs/resolve.md) is validated with tetrahedral.
"""
import numpy as np


def lattice_cell(lut, pts):
    size = lut.shape[0]
    x = np.clip(np.asarray(pts, float), 0.0, 1.0) * (size - 1)
    index = np.minimum(np.floor(x).astype(int), size - 2)
    return index, x - index


def trilerp_unit(lut, pts):
    index, fraction = lattice_cell(lut, pts)
    out = np.zeros((len(index), 3))
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                weight = np.prod(np.where((dx, dy, dz), fraction, 1 - fraction), axis=1)
                out += weight[:, None] * lut[index[:, 0] + dx, index[:, 1] + dy, index[:, 2] + dz]
    return out


def tetralerp_unit(lut, pts):
    """Six-tetrahedron split by the ordering of the fractional coordinates:
    (1-f1) c000 + (f1-f2) c1 + (f2-f3) c2 + f3 c111 with f1 >= f2 >= f3, c1 and
    c2 the corners reached by stepping the largest fraction first."""
    index, fraction = lattice_cell(lut, pts)
    order = np.argsort(-fraction, axis=1)
    sorted_fraction = np.take_along_axis(fraction, order, 1)
    rows = np.arange(len(index))
    step = np.zeros_like(index)
    out = (1 - sorted_fraction[:, 0])[:, None] * lut[index[:, 0], index[:, 1], index[:, 2]]
    for k in range(3):
        step[rows, order[:, k]] = 1
        corner = lut[index[:, 0] + step[:, 0], index[:, 1] + step[:, 1], index[:, 2] + step[:, 2]]
        weight = sorted_fraction[:, k] - (sorted_fraction[:, k + 1] if k < 2 else 0.0)
        out += weight[:, None] * corner
    return out


def read_cube(path, size):
    """Numeric payload of a .cube as (S,S,S,3) in input-channel order."""
    vals = []
    for line in open(path).read().splitlines():
        parts = line.split()
        if len(parts) == 3:
            try:
                vals.append([float(x) for x in parts])
            except ValueError:
                pass
    a = np.array(vals)
    if a.shape != (size ** 3, 3):
        raise ValueError("Unexpected cube payload in %s: %s" % (path, a.shape))
    return a.reshape(size, size, size, 3).transpose(2, 1, 0, 3)
