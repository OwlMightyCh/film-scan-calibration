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

The DMAX corridor is an explicit build parameter and depends on the SENSOR.
It is not inferred from the stock's physical dye Dmax.  The sensor-free
(monochrome) fleet fits in 5.0 D — the shipped corridor, carried on each
BuildConfig — while a named camera SSF demands more: the a7R III fleet needs
5.25 D (see BAYER_CORRIDOR_DEFAULT).  `--corridor` overrides both.  Pair each
cube with the matching `Preshaper X` / `Postshaper X` DCTLs — crossing
corridors rescales density SILENTLY (register #5).
At 65^3 the node spacing is 5.0/64 = 0.078 D, so the headroom costs no
resolution.  Every build prints what the stock actually needs at dye 4.0 and
warns when that exceeds the corridor in force.
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
from engine.common.gamut import (   # noqa: E402
    REACH_TOLERANCE_D, project_to_reachable)


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
    # the stock's traced characteristic curves (Status A against log exposure),
    # the one sheet quantity the inverse never consumes; see sheet_neutral_closure
    curves_file: str = None


# The grid is no longer a per-build constant — it is read off each stock's
# measured dye support by dye_support_grid(). Every stock therefore gets the
# same treatment of the unpublished long-wavelength tail (register #2).
BUILDS_BY_NAME = {
    "velvia100-narrowband-d50": BuildConfig(
        "velvia100-narrowband-d50", "Velvia 100", "Velvia100_dye_density.json",
        "narrowband", 5.0, "V100_XYZ_D50.cube", target="d50-xyz",
        curves_file="Velvia100_datasheet_curves.json",
    ),
    "velvia50-narrowband-d50": BuildConfig(
        "velvia50-narrowband-d50", "Velvia 50", "Velvia50_dye_density.json",
        "narrowband", 5.0, "V50_XYZ_D50.cube", target="d50-xyz",
        curves_file="Velvia50_datasheet_curves.json",
    ),
    "provia100f-narrowband-d50": BuildConfig(
        "provia100f-narrowband-d50", "Provia 100F", "Provia100F_dye_density.json",
        "narrowband", 5.0, "Provia100F_XYZ_D50.cube", target="d50-xyz",
        curves_file="Provia100F_datasheet_curves.json",
    ),
    "ektachrome-narrowband-d50": BuildConfig(
        "ektachrome-narrowband-d50", "Ektachrome E100/100D",
        "EktachromeE100_dye_density.json",
        "narrowband", 5.0, "E100_XYZ_D50.cube", target="d50-xyz",
        curves_file="EktachromeE100_datasheet_curves.json",
    ),
}


# Lower bound on the integration grid. The observer is deliberately truncated
# below this (documented systematic); the grid never extends further down even
# when a stock's dye chart does.
GRID_FLOOR_NM = 400.0


# 'none' presumes no particular camera, and is the canonical build.
DEFAULT_SENSOR = "none"


# Corridor used when a camera SSF is named instead of the sensor-free default.
# A Bayer CFA concentrates each channel's weight where its own dye is dense, so
# the same stack reads deeper than it does under a unity response: 5.25 D covers
# the a7R III fleet, whose worst case is Provia 100F at 5.08 D. It is NOT a
# general Bayer constant — another body's corridor must be determined the same
# way (build it and read the printed requirement), never assumed from this one.
BAYER_CORRIDOR_DEFAULT = 5.25


def resolve_corridor(config, sensor, corridor=None):
    """The corridor actually in force for this build.

    An explicit --corridor wins outright. Otherwise the sensor-free build takes
    the config's shipped corridor, and any named sensor takes
    BAYER_CORRIDOR_DEFAULT.
    """
    if corridor is not None:
        return float(corridor)
    if sensor == "none":
        return config.dmax_corridor
    return BAYER_CORRIDOR_DEFAULT


def resolve_sensor(value):
    """(path, label) for --sensor.

    The default 'none' returns (None, ...) — a monochrome sensor, unity response
    at every wavelength, so the scanner weights are the illuminant alone. To
    presume a particular camera, a bare name resolves to
    data/cameras/<name>_ssf.json; a value ending in .json or containing a path
    separator is taken as given.
    """
    if value == "none":
        return None, "none (unity response; monochrome sensor)"
    cameras = DATA / "cameras"
    if "/" in value or "\\" in value:
        path = Path(value)
    elif value.endswith(".json"):
        path = cameras / value
        if not path.exists():
            path = Path(value)
    else:
        path = cameras / f"{value}_ssf.json"
    if not path.exists():
        raise SystemExit(f"sensor file not found: {path}\n(look in {cameras})")
    return path, path.name


def sensor_stem(value):
    """Directory stem for a named sensor, e.g. 'Sony_ILCE-7RM3'."""
    name = Path(value).name
    if name.endswith(".json"):
        name = name[:-len(".json")]
    if name.endswith("_ssf"):
        name = name[:-len("_ssf")]
    return name


def load_cfa(grid, sensor_path):
    text = sensor_path.read_text()

    def array(key):
        match = re.search(key + r'"?\s*:\s*\[([0-9eE.,\s\\-]*?)\]', text)
        if match is None:
            raise ValueError(f"Could not read {key} from CFA data")
        return np.array(re.findall(r'-?\d+\.?\d*(?:[eE][-+]?\d+)?', match.group(1)), float)

    wavelengths = array("ssf_bands")
    return np.stack([resample(wavelengths, array(k), grid)
                     for k in ("red_ssf", "green_ssf", "blue_ssf")])


def load_scanner_weights(config, grid, sensor_path):
    raw = (DATA / "equipment" / "film_scanner_SPD_combined.csv").read_text().strip().splitlines()
    header = raw[0].split(",")
    data = np.array([[float(v) for v in row.split(",")] for row in raw[1:]])
    wavelengths = data[:, 0]
    cfa = 1.0 if sensor_path is None else load_cfa(grid, sensor_path)

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


def write_cube(path, config, lut, sensor_label, corridor):
    with path.open("w") as output:
        output.write(f"# {config.stock}, {config.illumination} scanner density -> D50 colorimetric density -log10(XYZ/white), CIE 1931 2-deg\n")
        output.write(f"# INPUT = scanner density / {corridor:.2f}; OUTPUT = colorimetric density / {corridor:.2f}\n")
        output.write(f"# sensor: {sensor_label}\n")
        output.write(f"LUT_3D_SIZE {config.lut_size}\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n")
        flat = np.clip(lut / corridor, 0, 1).transpose(2, 1, 0, 3).reshape(-1, 3)
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


CORRIDOR_PROBE_DYE = 4.0


def load_status_a(grid):
    """ISO 5-3 Status A responsivities, row-normalized to unit sum on `grid`.

    The reversal sheets publish their characteristic curves in Status A, so
    this is the densitometer the sheet-quantity closure has to emulate. It is
    used for that check only; the cube's target stays D50 XYZ.
    """
    s = json.loads((DATA / "standards" / "StatusA_ISO5-3.json").read_text())
    products = s["log10_spectral_products_as_published"]
    rows = []
    for channel in ("red", "green", "blue"):
        wl = np.array(sorted(int(k) for k in products[channel]), float)
        v = np.array([products[channel][str(int(w))] for w in wl], float)
        rows.append(resample(wl, 10.0 ** (v - 5.0), grid))
    weights = np.stack(rows)
    return weights / weights.sum(1, keepdims=True)


def density_jacobian(weights, values, dye):
    """(density, d density / d amount) of dye stacks under `weights`."""
    values = np.atleast_2d(values)
    transmission = 10.0 ** (-(values @ dye))
    integral = transmission @ weights.T
    numerator = np.einsum("nl,il,jl->nij", transmission, weights, dye)
    return -np.log10(np.clip(integral, 1e-12, None)), numerator / integral[:, :, None]


def solve_amounts(weights, targets, dye, iterations=40):
    """Dye amounts whose density under `weights` reproduces `targets` (n, 3)."""
    seed_axis = np.linspace(0, 3, 7)
    seed = np.array(np.meshgrid(seed_axis, seed_axis, seed_axis, indexing="ij")).reshape(3, -1).T
    linear_fit, *_ = np.linalg.lstsq(seed, density(weights, seed, dye), rcond=None)
    amounts = targets @ np.linalg.inv(linear_fit)
    for _ in range(iterations):
        current, jacobian = density_jacobian(weights, amounts, dye)
        step = np.linalg.solve(jacobian, (current - targets)[:, :, None])[:, :, 0]
        amounts = amounts - step
    return amounts, np.max(np.abs(density(weights, amounts, dye) - targets), axis=1)


def lab_from_relative_xyz(xyz):
    """CIE L*a*b* of XYZ already expressed relative to the adopted white."""
    def f(t):
        return np.where(t > (6 / 29) ** 3, np.cbrt(t), t / (3 * (6 / 29) ** 2) + 4 / 29)
    fx, fy, fz = f(xyz[:, 0]), f(xyz[:, 1]), f(xyz[:, 2])
    return np.stack([116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)], 1)


def sheet_neutral_closure(config, grid, dye, scan_forward, target_forward,
                          written_lut, corridor):
    """The one check against a sheet quantity the inverse never consumes.

    The datasheet's characteristic curves are Status A integral densities of
    ONE neutral (daylight) exposure series, base and fog included. The cube
    is built from the spectral dye curves alone and never sees them. Read the
    three curves together: subtract the sheet's own D-min per channel in
    INTEGRATED density (what the roll anchor does to a scan), solve at every
    exposure for the three dye amounts whose Status A density reproduces all
    three curves at once, and then ask two things the dye model must get
    right if it describes this film:

      * the solve must close with non-negative amounts that fall with
        exposure (a negative amount means the traced dyes cannot form the
        sheet's own neutral in Status A);
      * the D50 colorimetry of that series must be neutral, since a reversal
        film's daylight neutral series is what it is designed to render
        neutral on the light table. a*/b* here are the traced dyes, the
        Status A responsivities and the CIE observer disagreeing about one
        set of amounts; the forward model alone cannot make them zero.

    A trilinear lookup of the written cube on the same series is printed too,
    but that line is plumbing: the LUT and the reference share the machinery.
    """
    if not config.curves_file:
        print(f"{config.name}: no traced characteristic curves; sheet closure skipped")
        return
    sheet = json.loads((DATA / "films" / config.curves_file).read_text())
    cc = sheet["char_curves"]
    log_h = np.array(cc["log_exposure"], float)
    status_a_density = np.stack([np.array(cc["statusA_density"][k], float) for k in ("R", "G", "B")], 1)
    d_min = status_a_density.min(0)
    above_base = status_a_density - d_min
    status_a = load_status_a(grid)
    amounts, residual = solve_amounts(status_a, above_base, dye)
    negative = float(amounts.min())
    # amounts must fall with exposure: count rises beyond a tracing-noise allowance
    rises = int(np.sum(np.diff(amounts, axis=0) > 0.02))
    colorimetric = target_forward(amounts)
    xyz = 10.0 ** (-colorimetric)
    lab = lab_from_relative_xyz(xyz)
    y_rel = xyz[:, 1]
    inside = (y_rel > 10.0 ** -2.0) & (y_rel < 10.0 ** -0.3)      # D50 visual density 0.3-2.0
    i_mid = int(np.argmin(np.abs(y_rel - 0.18)))
    chain = trilerp(written_lut, scan_forward(amounts), corridor) - colorimetric
    print(f"{config.name}: sheet closure ({config.curves_file}, Status A neutral series, "
          f"D-min {d_min[0]:.3f}/{d_min[1]:.3f}/{d_min[2]:.3f} subtracted in integrated density): "
          f"3x3 solve residual max {residual.max():.4f} D; amounts min {negative:+.3f} "
          f"({'NEGATIVE amount: the traced dyes cannot form the sheet neutral' if negative < -0.02 else 'non-negative'}); "
          f"rises with exposure {rises}")
    print(f"{config.name}: sheet neutral on the D50 table: at Y=0.18 a* {lab[i_mid, 1]:+.2f} b* {lab[i_mid, 2]:+.2f}; "
          f"over visual density 0.3-2.0 |a*| max {np.abs(lab[inside, 1]).max():.2f}, |b*| max {np.abs(lab[inside, 2]).max():.2f}, "
          f"mean a* {lab[inside, 1].mean():+.2f} b* {lab[inside, 2].mean():+.2f}")
    print(f"{config.name}: written cube on the sheet neutral (plumbing, not evidence): max |error| {np.abs(chain).max():.4f} D")
    return d_min


def base_term_bound(config, grid, scanner, dye, status_a_dmin, scan_forward):
    """How much the roll anchor's INTEGRATED base subtraction can differ from
    the bare-LED reading the cube is built on (register #17 for reversal).

    No reversal sheet publishes a base spectrum, so the base is a SURROGATE:
    the sheet's Status A D-min triplet placed at the three Status A peak
    wavelengths and joined by straight lines, i.e. the mildest tint the
    densitometer readings admit. The scan side then sees the dyes through
    that tint, `Phi x 10^-base(lambda)`, and the difference from the bare-LED
    model is the term. A flat base cancels exactly; a tint that falls across
    an LED's band does not.
    """
    status_a = load_status_a(grid)
    peaks = np.array([grid[np.argmax(row)] for row in status_a])          # red, green, blue
    order = np.argsort(peaks)
    base = np.interp(grid, peaks[order], status_a_dmin[order])
    filtered = scanner * 10.0 ** (-base)
    filtered = filtered / filtered.sum(1, keepdims=True)
    axis = np.linspace(0.0, CORRIDOR_PROBE_DYE, 9)
    box = np.array(np.meshgrid(axis, axis, axis, indexing="ij")).reshape(3, -1).T
    neutral = np.array([[1.0, 1.0, 1.0]])
    delta_box = density(filtered, box, dye) - scan_forward(box)
    delta_neutral = density(filtered, neutral, dye) - scan_forward(neutral)
    fall = [float(base[np.argmax(scanner[i])]) for i in range(3)]
    print(f"{config.name}: base term (SURROGATE tint through Status A D-min "
          f"{status_a_dmin[0]:.3f}/{status_a_dmin[1]:.3f}/{status_a_dmin[2]:.3f}, base at the LED peaks "
          f"{fall[0]:.3f}/{fall[1]:.3f}/{fall[2]:.3f}): neutral dye 1.0 reads "
          f"{delta_neutral[0, 0]:+.4f}/{delta_neutral[0, 1]:+.4f}/{delta_neutral[0, 2]:+.4f} D against the bare LED; "
          f"over the dye 0-{CORRIDOR_PROBE_DYE:.0f} box max |delta| {np.abs(delta_box).max():.4f} D")


def corridor_requirement(scan_forward, dye=CORRIDOR_PROBE_DYE):
    """Peak scanner density this stock puts out over the dye-`dye` box.

    A neutral stack is not the worst case — an off-neutral one can read deeper
    in a single channel, because each channel's weight sits where its own dye
    is dense. So probe the neutral AND a sweep of the same box (its corners,
    faces and a coarse interior lattice) and take the maximum over all three
    channels: that is the smallest corridor which clips nothing.
    """
    axis = np.linspace(0.0, dye, 5)
    sweep = np.array(np.meshgrid(axis, axis, axis, indexing="ij")).reshape(3, -1).T
    probes = np.vstack([np.full((1, 3), dye), sweep])
    return float(np.max(scan_forward(probes)))


def build(config, sensor=DEFAULT_SENSOR, corridor=None):
    corridor = resolve_corridor(config, sensor, corridor)
    sensor_path, sensor_label = resolve_sensor(sensor)
    dye_data = json.loads((DATA / "films" / config.dye_file).read_text())["fine_curves_1nm"]
    grid = dye_support_grid(dye_data)
    dye = np.stack([load_dye_channel(dye_data, channel, grid)
                    for channel in ("cyan", "magenta", "yellow")])
    scanner = load_scanner_weights(config, grid, sensor_path)
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

    needed = corridor_requirement(scan_forward)
    print(f"{config.name}: corridor {corridor:.2f} D; this stock needs "
          f"{needed:.2f} D at dye {CORRIDOR_PROBE_DYE:.1f}")
    if needed > corridor:
        # Not an error: a deliberately narrow corridor is a legitimate choice.
        print(f"{config.name}: WARNING corridor {corridor:.2f} D clips this "
              f"stock, which needs {needed:.2f} D; use "
              f"--corridor {np.ceil(needed / 0.25) * 0.25:.2f}")

    seed_axis = np.linspace(0, 3, 9)
    seed_dye = np.array(np.meshgrid(seed_axis, seed_axis, seed_axis, indexing="ij")).reshape(3, -1).T
    seed_scan = scan_forward(seed_dye)
    linear_fit, *_ = np.linalg.lstsq(seed_dye, seed_scan, rcond=None)
    inverse_fit = np.linalg.inv(linear_fit)

    axis = np.linspace(0, corridor, config.lut_size)
    nodes = np.array(np.meshgrid(axis, axis, axis, indexing="ij")).reshape(3, -1).T
    dye_nodes = nodes @ inverse_fit
    iterations = 14
    for iteration in range(iterations):
        current, jacobian = scan_jacobian(dye_nodes)
        step = np.linalg.solve(jacobian, (current - nodes)[:, :, None])[:, :, 0]
        dye_nodes = np.clip(dye_nodes - step, -0.5, 8.0)
    residual = np.max(np.abs(scan_forward(dye_nodes) - nodes), axis=1)
    dye_nodes, unreachable = project_to_reachable(dye_nodes, residual, config.lut_size)
    lut = target_forward(dye_nodes).reshape(config.lut_size, config.lut_size, config.lut_size, 3)

    BUILDS.mkdir(exist_ok=True)
    if sensor_path is None:
        cube_path = BUILDS / "reversal" / config.cube_file
    else:
        # A per-apparatus build lands beside, never on top of, the canonical cube.
        cube_path = BUILDS / f"sensor-{sensor_stem(sensor)}" / "reversal" / config.cube_file
    cube_path.parent.mkdir(parents=True, exist_ok=True)
    write_cube(cube_path, config, lut, sensor_label, corridor)

    # Validate the serialized, clipped, six-decimal artifact—not the in-memory LUT.
    written_lut = read_written_cube(cube_path, config.lut_size, corridor)
    # 0-4.0: the corridor is sized to hold a dye-4.0 stack on every stock in the
    # fleet, so the self-check exercises that headroom rather than stopping short.
    samples = np.random.default_rng(1).uniform(0, CORRIDOR_PROBE_DYE, (5000, 3))
    error = trilerp(written_lut, scan_forward(samples), corridor) - target_forward(samples)
    print(f"{config.name}: grid {grid[0]:.0f}-{grid[-1]:.0f} nm (derived from dye support)")
    print(f"{config.name}: sensor {sensor_label}")
    print(f"{config.name}: node residual mean {residual.mean():.4f}, max {residual.max():.4f} D")
    print(f"{config.name}: {(residual <= REACH_TOLERANCE_D).sum()} reachable nodes, "
          f"{unreachable} unreachable projected onto the nearest reachable node")
    print(f"serialized {cube_path.name}: RMSE {np.sqrt(np.mean(error**2)):.4f}, max {np.max(np.abs(error)):.4f} D")
    d_min = sheet_neutral_closure(config, grid, dye, scan_forward, target_forward, written_lut, corridor)
    if d_min is not None:
        base_term_bound(config, grid, scanner, dye, d_min, scan_forward)
    print(f"data SHA256: {hashlib.sha256((DATA / 'films' / config.dye_file).read_bytes()).hexdigest()}")
    print(f"wrote {cube_path.relative_to(ROOT)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", choices=BUILDS_BY_NAME, help="reversal build to generate")
    parser.add_argument("--sensor", default=DEFAULT_SENSOR,
                        help="camera SSF: 'none' for a unity (monochrome) "
                             "response, or a bare name from data/cameras/ or a "
                             "path to presume a particular camera "
                             f"(default: {DEFAULT_SENSOR})")
    parser.add_argument("--corridor", type=float, default=None,
                        help="DMAX corridor in density, overriding the default "
                             "for this build (the config's corridor when "
                             "--sensor is 'none', otherwise "
                             f"{BAYER_CORRIDOR_DEFAULT:g}). Must match the "
                             "Pre/Postshaper DCTL pair in use.")
    _args = parser.parse_args()
    build(BUILDS_BY_NAME[_args.build], _args.sensor, _args.corridor)
