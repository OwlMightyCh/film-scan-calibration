"""Projection of unreachable LUT nodes onto the reachable gamut.

Every engine inverts scan density to dye amounts on a regular lattice spanning
a corridor of densities. Three dyes reach only part of that corridor, so some
nodes have no dye triple whose scan density equals the node, and the
fixed-iteration Gauss-Newton solve leaves those pinned against a clip bound.
Writing such a solution into the cube places an unphysical value one lattice
step from a reachable colour, and tetrahedral interpolation carries it inward.

`project_to_reachable` gives each unreachable node the dye solution of the
nearest node the solve did reach. Nodes the solve reached are never altered.
"""

import numpy as np

REACH_TOLERANCE_D = 1e-3


def nearest_reached(reached):
    """Flat index of the nearest reached node, by Euclidean lattice distance.

    Exact separable distance transform: one pass per axis, each taking the
    minimum along that axis of the previous pass's cost plus the squared
    offset, and carrying the source index of whichever position won. The
    lattice is uniform and equally spaced on all three axes, so Euclidean
    distance in node indices is proportional to distance in scan density.
    """
    shape = reached.shape
    size = shape[0]
    offsets = ((np.arange(size)[:, None]
                - np.arange(size)[None, :]) ** 2).astype(np.float32)
    cost = np.where(reached, np.float32(0.0), np.float32(np.inf))
    source = np.arange(reached.size).reshape(shape)
    for axis in range(3):
        moved = np.moveaxis(cost, axis, -1)
        rows = moved.reshape(-1, size)
        keys = np.moveaxis(source, axis, -1).reshape(-1, size)
        total = rows[:, None, :] + offsets[None, :, :]
        best = np.argmin(total, axis=2)
        cost = np.moveaxis(
            np.take_along_axis(total, best[:, :, None], axis=2)[:, :, 0]
            .reshape(moved.shape), -1, axis)
        source = np.moveaxis(
            np.take_along_axis(keys, best, axis=1).reshape(moved.shape),
            -1, axis)
    return source


def project_to_reachable(dye_nodes, residual, size,
                         tolerance=REACH_TOLERANCE_D):
    """Give each unreachable node the dye solution of the nearest reachable one.

    A node counts as reached when the forward model applied to its solved dye
    amounts reproduces the node to within `tolerance`. The substitution is made
    in dye space, before the target integration, so every value written to the
    cube is the colorimetric density of a colour the film can produce, and is
    the closest such colour to the node. Reached nodes are returned unchanged,
    which keeps every colour the film can produce bit-identical to the
    unprojected build.

    Returns the dye amounts and the number of nodes projected.
    """
    reached = (residual <= tolerance).reshape(size, size, size)
    unreachable = int((~reached).sum())
    if not unreachable or not reached.any():
        return dye_nodes, unreachable
    source = nearest_reached(reached).reshape(-1)
    outside = ~reached.reshape(-1)
    if not reached.reshape(-1)[source[outside]].all():
        raise ValueError("projection selected a node the solve did not reach")
    projected = dye_nodes.copy()
    projected[outside] = dye_nodes[source[outside]]
    return projected, unreachable
