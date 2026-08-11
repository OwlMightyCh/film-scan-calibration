#!/usr/bin/env python3
"""Build reversal scanner-density -> D50-XYZ colorimetric-density LUTs (.cube only).

The colorimetric target (`target="d50-xyz"` on each BuildConfig) is the only
reversal route: CIE 1931 2-deg x D50 colorimetry, encoded as white-relative
density. The dye model, scanner model, corridor, and per-node inversion feed a
D50 observer integration. (The abandoned ISO 5-3 Status A route was removed
2026-07-23; the engine is D50-XYZ-only.)

Usage:
    python3 engine/reversal_transform.py velvia100-narrowband-d50
    python3 engine/reversal_transform.py provia100f-narrowband-d50

The DMAX corridor is an explicit build parameter (6.0 D for all narrowband
builds, raised from 4.5 on 2026-07-26).  It is not inferred from the stock's
physical dye Dmax.  Pair the cubes with the `Preshaper 6.0` / `Postshaper 6.0`
DCTLs — the retired 4.5 pair rescales density SILENTLY (register #5).
At 65^3 the node spacing is 6.0/64 = 0.094 D, FINER than the old 4.5/32 =
0.141 D, so the wider corridor costs no resolution: it buys headroom and
accuracy at once (Velvia 50 / Provia 100F overran 4.5 past dye ~3.7).
Broadband was retired 2026-07-16; narrowband is the only illumination mode.

The integration grid is DERIVED from each stock's measured dye support, not
hand-set per build (2026-07-26).  See `dye_support_grid`.
"""
import argparse
import hashlib
import json
import re
from dataclasses import dataclass
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
BUILDS = ROOT / "builds"

sys.path.insert(0, str(ROOT))
from engine.common.spectral import density, resample   # noqa: E402


@dataclass(frozen=True)
class BuildConfig:
    name: str
    stock: str
    dye_file: str
    illumination: str
    dmax_corridor: float
    cube_file: str
    lut_size: int = 65
    # "d50-xyz": CIE 1931 2-deg x D50 colorimetry, encoded as white-relative
    #            colorimetric density -log10(X/Xw, Y/Yw, Z/Zw) — Option A.
    #            Same corridor/shapers; after the 10^-D linearization node the
    #            image is linear D50-relative XYZ (one matrix node to working space).
    #            The only supported target (Status A was retired 2026-07-23).
    target: str = "d50-xyz"


# The grid is no longer a per-build constant — it is read off each stock's
# measured dye support by dye_support_grid(). Every stock therefore gets the
# same treatment of the unpublished long-wavelength tail (register #2).
BUILDS_BY_NAME = {
    "velvia100-narrowband-d50": BuildConfig(
        "velvia100-narrowband-d50", "Velvia 100", "Velvia100_dye_density.json",
        "narrowband", 6.0, "V100_XYZ_D50.cube", target="d50-xyz",
    ),
    "velvia50-narrowband-d50": BuildConfig(
        "velvia50-narrowband-d50", "Velvia 50", "Velvia50_dye_density.json",
        "narrowband", 6.0, "V50_XYZ_D50.cube", target="d50-xyz",
    ),
    "provia100f-narrowband-d50": BuildConfig(
        "provia100f-narrowband-d50", "Provia 100F", "Provia100F_dye_density.json",
        "narrowband", 6.0, "Provia100F_XYZ_D50.cube", target="d50-xyz",
    ),
    "ektachrome-narrowband-d50": BuildConfig(
        "ektachrome-narrowband-d50", "Ektachrome E100/100D",
        "EktachromeE100_dye_density.json",
        "narrowband", 6.0, "E100_XYZ_D50.cube", target="d50-xyz",
    ),
}


# Lower bound on the integration grid. The observer is deliberately truncated
# below this (documented systematic); the grid never extends further down even
# when a stock's dye chart does.
GRID_FLOOR_NM = 400.0


def load_cfa(grid):
    text = (DATA / "equipment" / "a7r2_cfa.md").read_text()

    def array(key):
        match = re.search(key + r'"?\s*:\s*\[([0-9eE.,\s\\-]*?)\]', text)
        if match is None:
            raise ValueError(f"Could not read {key} from CFA data")
        return np.array(re.findall(r'-?\d+\.?\d*(?:[eE][-+]?\d+)?', match.group(1)), float)

    wavelengths = array("ssf_bands")
    return np.stack([resample(wavelengths, array(k), grid)
                     for k in ("red_ssf", "green_ssf", "blue_ssf")])


def load_scanner_weights(config, grid):
    raw = (DATA / "equipment" / "film_scanner_SPD_combined.csv").read_text().strip().splitlines()
    header = raw[0].split(",")
    data = np.array([[float(v) for v in row.split(",")] for row in raw[1:]])
    wavelengths = data[:, 0]
    cfa = load_cfa(grid)

    def spd(column):
        return resample(wavelengths, data[:, header.index(column)], grid)

    if config.illumination != "narrowband":
        raise ValueError(f"Unknown illumination: {config.illumination} (broadband retired 2026-07-16)")
    light = np.stack([spd("R100_G0_B0"), spd("R0_G100_B0"), spd("R0_G0_B100")])
    weights = light * cfa
    return weights / weights.sum(1, keepdims=True)


def load_d50_xyz(grid):
    """CIE 1931 2-deg CMFs x D50, row-normalized to unit sum on `grid`.

    Row normalization makes density() output -log10(X/Xw) etc. — colorimetric
    density relative to the D50 white (clear film = 0.0 exactly).
    """
    cmfs = json.loads((DATA / "standards" / "CIE1931_2deg_CMFs.json").read_text())
    d50 = json.loads((DATA / "standards" / "D50_illuminant.json").read_text())
    cw = np.array(cmfs["wavelength_nm"], float)
    weights = np.stack([resample(cw, np.array(cmfs[k], float), grid)
                        for k in ("x_bar", "y_bar", "z_bar")])
    weights = weights * resample(np.array(d50["wavelength_nm"], float),
                                 np.array(d50["spd"], float), grid)
    return grid, weights / weights.sum(1, keepdims=True)


def trilerp(lut, points, dmax):
    size = lut.shape[0]
    x = np.clip(points / dmax, 0, 1) * (size - 1)
    index = np.floor(x).astype(int)
    fraction = x - index
    index = np.minimum(index, size - 2)
    out = np.zeros((len(points), 3))
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                weight = np.prod(np.where((dx, dy, dz), fraction, 1 - fraction), axis=1)
                out += weight[:, None] * lut[index[:, 0] + dx, index[:, 1] + dy, index[:, 2] + dz]
    return out


def write_cube(path, config, lut):
    with path.open("w") as output:
        output.write(f"# {config.stock}, {config.illumination} scanner density -> D50 colorimetric density -log10(XYZ/white), CIE 1931 2-deg\n")
        output.write(f"# INPUT = scanner density / {config.dmax_corridor:.2f}; OUTPUT = colorimetric density / {config.dmax_corridor:.2f}\n")
        output.write(f"LUT_3D_SIZE {config.lut_size}\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n")
        flat = np.clip(lut / config.dmax_corridor, 0, 1).transpose(2, 1, 0, 3).reshape(-1, 3)
        for value in flat:
            output.write(f"{value[0]:.6f} {value[1]:.6f} {value[2]:.6f}\n")


def read_written_cube(path, size, dmax):
    data = []
    for line in path.read_text().splitlines():
        fields = line.split()
        if len(fields) == 3:
            try:
                data.append([float(v) for v in fields])
            except ValueError:
                pass
    values = np.array(data)
    if values.shape != (size**3, 3):
        raise ValueError(f"Unexpected cube payload in {path}: {values.shape}")
    return values.reshape(size, size, size, 3).transpose(2, 1, 0, 3) * dmax


def load_dye_channel(dye_data, channel, grid):
    """Resample one dye curve, honouring null entries (beyond measured
    support — e.g. Ektachrome yellow past 680.8 nm). Nulls are excluded from
    the interpolation support, so beyond-support wavelengths fall to zero via
    resample()'s boundary rule — the documented bounded systematic, never a
    synthesized tail."""
    wavelengths = np.array(dye_data["wavelength_nm"], float)
    values = np.array([np.nan if v is None else v for v in dye_data[channel]], float)
    ok = ~np.isnan(values)
    return resample(wavelengths[ok], values[ok], grid)


def dye_support_grid(dye_data):
    """The 1 nm grid over which this stock's dye set is actually measured.

    A wavelength lying outside EVERY dye's measured support is modelled as
    perfectly clear film — a physically false claim wherever the chart was
    merely cropped (cyan is still 0.29-0.75 D at the Fuji/Kodak plot edges).
    Such a wavelength puts an unbounded, sign-known error into the target
    integral and imposes a spurious hard density ceiling at -log10 of the
    observer weight sitting there.

    So the grid spans the UNION of the three dyes' support and stops there.
    Observer weight beyond that edge is dropped and the observer renormalized
    (load_d50_xyz normalizes on whatever grid it is handed), which asserts only
    that the unmeasured tail resembles the in-band mean — a bounded bias
    instead of an unbounded one. This is what the Ektachrome build did by hand
    via grid_stop_nm=700; deriving it applies the same rule to every stock
    (2026-07-26). Wavelengths INSIDE the union where a single dye happens to be
    unmeasured are untouched: the other dyes still absorb there, so the
    perfectly-clear failure mode does not arise.

    The floor stays at GRID_FLOOR_NM even for charts that start lower, but is
    raised when a chart starts above it (Ektachrome begins at 401 nm; a grid
    starting at 400 left one perfectly-clear wavelength carrying 0.039% of the
    D50 z-bar weight, capping modelled blue density at 3.41 D).
    """
    wavelengths = np.array(dye_data["wavelength_nm"], float)
    starts, ends = [], []
    for channel in ("cyan", "magenta", "yellow"):
        values = np.array([np.nan if v is None else v for v in dye_data[channel]], float)
        measured = wavelengths[~np.isnan(values)]
        starts.append(measured.min())
        ends.append(measured.max())
    start = max(GRID_FLOOR_NM, min(starts))
    stop = max(ends)
    if stop <= start:
        raise ValueError(f"Degenerate dye support: {start}-{stop} nm")
    return np.arange(np.ceil(start), np.floor(stop) + 1, 1.0)


def build(config):
    dye_data = json.loads((DATA / "films" / config.dye_file).read_text())["fine_curves_1nm"]
    grid = dye_support_grid(dye_data)
    dye = np.stack([load_dye_channel(dye_data, channel, grid)
                    for channel in ("cyan", "magenta", "yellow")])
    scanner = load_scanner_weights(config, grid)
    if config.target != "d50-xyz":
        raise ValueError(
            f"Unknown target: {config.target!r} (the D50-XYZ route is the only "
            "supported target; Status A was retired 2026-07-23)"
        )
    status_wavelengths, status_weights = load_d50_xyz(grid)
    status_dye = np.stack([load_dye_channel(dye_data, channel, status_wavelengths)
                            for channel in ("cyan", "magenta", "yellow")])

    scan_forward = lambda values: density(scanner, values, dye)
    target_forward = lambda values: density(status_weights, values, status_dye)

    def scan_jacobian(values):
        values = np.atleast_2d(values)
        transmission = 10.0 ** (-(values @ dye))
        integral = transmission @ scanner.T
        numerator = np.einsum("nl,il,jl->nij", transmission, scanner, dye)
        return -np.log10(np.clip(integral, 1e-12, None)), numerator / integral[:, :, None]

    seed_axis = np.linspace(0, 3, 9)
    seed_dye = np.array(np.meshgrid(seed_axis, seed_axis, seed_axis, indexing="ij")).reshape(3, -1).T
    seed_scan = scan_forward(seed_dye)
    linear_fit, *_ = np.linalg.lstsq(seed_dye, seed_scan, rcond=None)
    inverse_fit = np.linalg.inv(linear_fit)

    axis = np.linspace(0, config.dmax_corridor, config.lut_size)
    nodes = np.array(np.meshgrid(axis, axis, axis, indexing="ij")).reshape(3, -1).T
    dye_nodes = nodes @ inverse_fit
    iterations = 14
    for iteration in range(iterations):
        current, jacobian = scan_jacobian(dye_nodes)
        step = np.linalg.solve(jacobian, (current - nodes)[:, :, None])[:, :, 0]
        dye_nodes = np.clip(dye_nodes - step, -0.5, 8.0)
    residual = np.max(np.abs(scan_forward(dye_nodes) - nodes), axis=1)
    lut = target_forward(dye_nodes).reshape(config.lut_size, config.lut_size, config.lut_size, 3)

    BUILDS.mkdir(exist_ok=True)
    cube_path = BUILDS / "reversal" / config.cube_file
    write_cube(cube_path, config, lut)

    # Validate the serialized, clipped, six-decimal artifact—not the in-memory LUT.
    written_lut = read_written_cube(cube_path, config.lut_size, config.dmax_corridor)
    # 0-4.0: the 6.0 corridor is sized to hold a neutral dye-4.0 stack on every
    # stock (Provia 100F needs 5.06 D of scanner density there), so the self-
    # check now exercises that headroom instead of stopping at the old 3.4.
    samples = np.random.default_rng(1).uniform(0, 4.0, (5000, 3))
    error = trilerp(written_lut, scan_forward(samples), config.dmax_corridor) - target_forward(samples)
    print(f"{config.name}: grid {grid[0]:.0f}-{grid[-1]:.0f} nm (derived from dye support)")
    print(f"{config.name}: node residual mean {residual.mean():.4f}, max {residual.max():.4f} D")
    print(f"serialized {cube_path.name}: RMSE {np.sqrt(np.mean(error**2)):.4f}, max {np.max(np.abs(error)):.4f} D")
    print(f"data SHA256: {hashlib.sha256((DATA / 'films' / config.dye_file).read_bytes()).hexdigest()}")
    print(f"wrote {cube_path.relative_to(ROOT)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", choices=BUILDS_BY_NAME, help="reversal build to generate")
    build(BUILDS_BY_NAME[parser.parse_args().build])
