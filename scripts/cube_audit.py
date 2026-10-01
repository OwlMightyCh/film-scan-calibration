#!/usr/bin/env python3
"""Regression and sanity audit tool for .cube 3D LUTs.

Provides four subcommands:
  validate  - Verify .cube header, shape, finiteness, and domain.
  sample    - Perform trilinear interpolation at (R, G, B) normalized coordinates.
  compare   - Compare two .cube files (max absolute difference and RMSE).
  manifest  - Record or check content hashes (sha256) of .cube files.

Checking a manifest also sweeps for cubes on disk that it does not record, so a
newly built LUT cannot pass the audit merely by being absent from it.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import NamedTuple

import numpy as np


class Cube(NamedTuple):
    path: str
    size: int
    domain_min: np.ndarray
    domain_max: np.ndarray
    table: np.ndarray  # shape: (size, size, size, 3), indexed [b, g, r, c]
    title: str | None = None


def parse_cube(path_str: str) -> tuple[Cube | None, str | None]:
    """Parse and validate a .cube 3D LUT file.

    Returns:
        (cube, None) on success, or (None, failure_reason) on failure.
    """
    path = Path(path_str)
    if not path.exists():
        return None, f"file not found: {path_str}"
    if not path.is_file():
        return None, f"not a regular file: {path_str}"

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return None, f"cannot read file: {e}"

    size: int | None = None
    domain_min: np.ndarray = np.array([0.0, 0.0, 0.0], dtype=np.float64)
    domain_max: np.ndarray = np.array([1.0, 1.0, 1.0], dtype=np.float64)
    domain_min_set = False
    domain_max_set = False
    title: str | None = None
    data_rows: list[list[float]] = []

    for line_num, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()
        keyword = parts[0].upper()

        if keyword == "TITLE":
            # Optional title, may be quoted
            title_text = line[5:].strip()
            if (title_text.startswith('"') and title_text.endswith('"')) or (
                title_text.startswith("'") and title_text.endswith("'")
            ):
                title_text = title_text[1:-1]
            title = title_text
            continue

        if keyword == "LUT_3D_SIZE":
            if len(parts) < 2:
                return None, f"line {line_num}: malformed LUT_3D_SIZE"
            try:
                size = int(parts[1])
            except ValueError:
                return None, f"line {line_num}: invalid integer for LUT_3D_SIZE '{parts[1]}'"
            continue

        if keyword == "LUT_1D_SIZE":
            return None, "1D LUT is not supported (LUT_3D_SIZE required)"

        if keyword == "DOMAIN_MIN":
            if len(parts) != 4:
                return None, f"line {line_num}: DOMAIN_MIN requires 3 values, got {len(parts)-1}"
            try:
                domain_min = np.array([float(x) for x in parts[1:4]], dtype=np.float64)
                domain_min_set = True
            except ValueError:
                return None, f"line {line_num}: non-numeric DOMAIN_MIN value"
            continue

        if keyword == "DOMAIN_MAX":
            if len(parts) != 4:
                return None, f"line {line_num}: DOMAIN_MAX requires 3 values, got {len(parts)-1}"
            try:
                domain_max = np.array([float(x) for x in parts[1:4]], dtype=np.float64)
                domain_max_set = True
            except ValueError:
                return None, f"line {line_num}: non-numeric DOMAIN_MAX value"
            continue

        if keyword == "LUT_3D_INPUT_RANGE":
            if len(parts) == 3:
                try:
                    vmin = float(parts[1])
                    vmax = float(parts[2])
                    if not domain_min_set:
                        domain_min = np.array([vmin, vmin, vmin], dtype=np.float64)
                    if not domain_max_set:
                        domain_max = np.array([vmax, vmax, vmax], dtype=np.float64)
                except ValueError:
                    pass
            continue

        # Data row
        if len(parts) == 3:
            try:
                r = float(parts[0])
                g = float(parts[1])
                b = float(parts[2])
                data_rows.append([r, g, b])
            except ValueError:
                return None, f"line {line_num}: malformed numeric triplet '{line}'"
        else:
            return None, f"line {line_num}: unexpected line '{line}'"

    # Check a: LUT_3D_SIZE present and 2 <= N <= 256
    if size is None:
        return None, "missing LUT_3D_SIZE"
    if size < 2 or size > 256:
        return None, f"LUT_3D_SIZE N={size} out of range [2, 256]"

    # Check b: exactly N**3 triplets, no more, no fewer
    expected_nodes = size**3
    actual_nodes = len(data_rows)
    if actual_nodes != expected_nodes:
        return None, f"expected {expected_nodes} triplets for N={size}, got {actual_nodes}"

    table_flat = np.array(data_rows, dtype=np.float64)

    # Check c: every value finite (no NaN, no inf)
    if not np.all(np.isfinite(table_flat)):
        return None, "non-finite values (NaN or Inf) encountered"

    # Check d: DOMAIN_MIN strictly less than DOMAIN_MAX componentwise
    if not np.all(domain_min < domain_max):
        return (
            None,
            f"DOMAIN_MIN ({domain_min.tolist()}) must be strictly less than DOMAIN_MAX ({domain_max.tolist()}) componentwise",
        )

    # Red varies fastest in .cube data ordering -> reshape as [b, g, r, c]
    table = table_flat.reshape((size, size, size, 3))

    return (
        Cube(
            path=path_str,
            size=size,
            domain_min=domain_min,
            domain_max=domain_max,
            table=table,
            title=title,
        ),
        None,
    )


def compute_cube_hash(cube: Cube) -> str:
    """Compute sha256 content hash over canonical size, domain, and data values.

    Depends only on numeric data formatted '%.6f' in file order, size, and domain.
    Ignores comments, TITLE, and whitespace.
    """
    h = hashlib.sha256()
    h.update(f"LUT_3D_SIZE {cube.size}\n".encode("ascii"))
    h.update(
        f"DOMAIN_MIN {cube.domain_min[0]:.6f} {cube.domain_min[1]:.6f} {cube.domain_min[2]:.6f}\n".encode(
            "ascii"
        )
    )
    h.update(
        f"DOMAIN_MAX {cube.domain_max[0]:.6f} {cube.domain_max[1]:.6f} {cube.domain_max[2]:.6f}\n".encode(
            "ascii"
        )
    )

    flat = cube.table.reshape((-1, 3))
    for r, g, b in flat:
        h.update(f"{r:.6f} {g:.6f} {b:.6f}\n".encode("ascii"))
    return h.hexdigest()


def sample_cube(cube: Cube, r: float, g: float, b: float) -> np.ndarray:
    """Perform trilinear interpolation at coordinate (r, g, b).

    Clamps inputs to domain. Returns interpolated RGB triplet.
    """
    # Clamp to domain
    rc = min(max(r, float(cube.domain_min[0])), float(cube.domain_max[0]))
    gc = min(max(g, float(cube.domain_min[1])), float(cube.domain_max[1]))
    bc = min(max(b, float(cube.domain_min[2])), float(cube.domain_max[2]))

    # Map to continuous grid coordinates [0, N - 1]
    n = cube.size
    ur = (rc - cube.domain_min[0]) / (cube.domain_max[0] - cube.domain_min[0]) * (n - 1)
    ug = (gc - cube.domain_min[1]) / (cube.domain_max[1] - cube.domain_min[1]) * (n - 1)
    ub = (bc - cube.domain_min[2]) / (cube.domain_max[2] - cube.domain_min[2]) * (n - 1)

    # Snap tiny floating-point inaccuracies to exact node integers
    if abs(ur - round(ur)) < 1e-12:
        ur = float(round(ur))
    if abs(ug - round(ug)) < 1e-12:
        ug = float(round(ug))
    if abs(ub - round(ub)) < 1e-12:
        ub = float(round(ub))

    # Compute bounding grid indices and fractional offsets
    def get_indices_and_frac(u: float, max_idx: int) -> tuple[int, int, float]:
        i0 = int(math.floor(u))
        if i0 >= max_idx:
            return max_idx, max_idx, 0.0
        i1 = min(i0 + 1, max_idx)
        frac = u - i0
        return i0, i1, frac

    r0, r1, fr = get_indices_and_frac(ur, n - 1)
    g0, g1, fg = get_indices_and_frac(ug, n - 1)
    b0, b1, fb = get_indices_and_frac(ub, n - 1)

    # 8 corner samples from lut[b, g, r]
    lut = cube.table
    c000 = lut[b0, g0, r0]
    c001 = lut[b0, g0, r1]
    c010 = lut[b0, g1, r0]
    c011 = lut[b0, g1, r1]
    c100 = lut[b1, g0, r0]
    c101 = lut[b1, g0, r1]
    c110 = lut[b1, g1, r0]
    c111 = lut[b1, g1, r1]

    # Trilinear interpolation: Red (fastest), then Green, then Blue (slowest)
    c00 = c000 * (1.0 - fr) + c001 * fr
    c01 = c010 * (1.0 - fr) + c011 * fr
    c10 = c100 * (1.0 - fr) + c101 * fr
    c11 = c110 * (1.0 - fr) + c111 * fr

    c0 = c00 * (1.0 - fg) + c01 * fg
    c1 = c10 * (1.0 - fg) + c11 * fg

    return c0 * (1.0 - fb) + c1 * fb


def cmd_validate(args: argparse.Namespace) -> int:
    exit_code = 0
    for path in args.cubes:
        cube, err = parse_cube(path)
        if err or cube is None:
            print(f"{path}: FAIL {err}")
            exit_code = 1
            continue

        min_val = float(np.min(cube.table))
        max_val = float(np.max(cube.table))
        num_nodes = cube.size**3

        # Count nodes with any channel outside unit range [0, 1]
        out_of_range_mask = np.any((cube.table < 0.0) | (cube.table > 1.0), axis=-1)
        out_of_range_count = int(np.sum(out_of_range_mask))

        out_str = (
            f"{path}: OK N={cube.size} nodes={num_nodes} range=[{min_val:.6f},{max_val:.6f}]"
        )
        if out_of_range_count > 0:
            out_str += f" out-of-range: {out_of_range_count} nodes"

        print(out_str)

    return exit_code


def cmd_sample(args: argparse.Namespace) -> int:
    cube, err = parse_cube(args.cube)
    if err or cube is None:
        print(f"{args.cube}: FAIL {err}")
        return 1

    sampled = sample_cube(cube, args.r, args.g, args.b)
    print(f"{sampled[0]:.6f} {sampled[1]:.6f} {sampled[2]:.6f}")
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    cube_a, err_a = parse_cube(args.a)
    if err_a or cube_a is None:
        print(f"{args.a}: FAIL {err_a}")
        return 1

    cube_b, err_b = parse_cube(args.b)
    if err_b or cube_b is None:
        print(f"{args.b}: FAIL {err_b}")
        return 1

    if cube_a.size != cube_b.size:
        print(f"compare: FAIL LUT_3D_SIZE mismatch ({cube_a.size} vs {cube_b.size})")
        return 1

    if not (
        np.allclose(cube_a.domain_min, cube_b.domain_min, atol=1e-9)
        and np.allclose(cube_a.domain_max, cube_b.domain_max, atol=1e-9)
    ):
        print("compare: FAIL domain mismatch")
        return 1

    diff = cube_a.table - cube_b.table
    max_abs_diff = float(np.max(np.abs(diff)))
    rmse = float(np.sqrt(np.mean(diff**2)))

    out = f"max={max_abs_diff:.6e} rmse={rmse:.6e}"
    if max_abs_diff == 0.0:
        out += " IDENTICAL"
    print(out)
    return 0


def manifest_scan_root(keys) -> Path | None:
    """Deepest directory containing every recorded path.

    Returns None when the manifest is empty or its paths share no ancestor, so
    that a manifest spanning disjoint trees does not silently turn the sweep
    into a walk of the whole working directory.
    """
    parents = [Path(k).parent for k in keys]
    if not parents:
        return None

    common = parents[0].parts
    for p in parents[1:]:
        parts = p.parts
        n = 0
        while n < min(len(common), len(parts)) and common[n] == parts[n]:
            n += 1
        common = common[:n]

    return Path(*common) if common else None


def find_orphan_cubes(manifest_keys, root: Path) -> list[Path]:
    """Cubes under root that the manifest does not record.

    Both sides are resolved before comparison. Without that, a manifest holding
    resolved paths swept from an unresolved root -- which is what a symlinked
    directory produces -- would report every recorded cube as an orphan, a false
    failure worse than the omission this sweep exists to catch.
    """
    recorded = {Path(k).resolve() for k in manifest_keys}
    return [p for p in sorted(root.rglob("*.cube")) if p.resolve() not in recorded]


def classify_orphans(
    orphans: list[Path], root: Path
) -> tuple[list[Path], list[Path]]:
    """Partition orphan cubes into expected (per-apparatus) and unexpected orphans.

    The sensor-* convention is how every engine isolates per-apparatus builds from
    the canonical tree; the manifest records canonical cubes only, so these are
    unrecorded BY DESIGN, and listing them as ORPHAN on every run desensitises the
    alarm.
    """
    root_path = Path(root)
    expected: list[Path] = []
    unexpected: list[Path] = []
    for p in orphans:
        p_path = Path(p)
        try:
            rel = p_path.relative_to(root_path)
        except ValueError:
            rel = p_path.resolve().relative_to(root_path.resolve())
        if len(rel.parts) > 1 and fnmatch.fnmatch(rel.parts[0], "sensor-*"):
            expected.append(p_path)
        else:
            unexpected.append(p_path)
    return expected, unexpected


def cmd_manifest(args: argparse.Namespace) -> int:
    if args.record:
        if not args.cubes:
            print("manifest: FAIL --record requires at least one cube file")
            return 1

        manifest_data: dict[str, str] = {}
        exit_code = 0

        for path in args.cubes:
            cube, err = parse_cube(path)
            if err or cube is None:
                print(f"{path}: FAIL {err}")
                exit_code = 1
                continue

            h = compute_cube_hash(cube)
            manifest_data[path] = h
            print(f"{path}: RECORDED")

        if exit_code != 0:
            return 1

        try:
            out_path = Path(args.record)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(manifest_data, indent=2) + "\n", encoding="utf-8")
        except Exception as e:
            print(f"{args.record}: FAIL cannot write manifest: {e}")
            return 1

        return 0

    if args.check:
        in_path = Path(args.check)
        if not in_path.exists():
            print(f"{args.check}: FAIL manifest file not found")
            return 1

        try:
            manifest_raw = json.loads(in_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"{args.check}: FAIL invalid JSON: {e}")
            return 1

        if not isinstance(manifest_raw, dict):
            print(f"{args.check}: FAIL manifest JSON must be an object")
            return 1

        exit_code = 0
        for path_str, expected in manifest_raw.items():
            if isinstance(expected, dict):
                expected_hash = expected.get("sha256") or expected.get("hash")
            else:
                expected_hash = str(expected)

            p = Path(path_str)
            if not p.exists():
                print(f"{path_str}: MISSING")
                exit_code = 1
                continue

            cube, err = parse_cube(path_str)
            if err or cube is None:
                print(f"{path_str}: CHANGED")
                exit_code = 1
                continue

            actual_hash = compute_cube_hash(cube)
            if actual_hash == expected_hash:
                print(f"{path_str}: MATCH")
            else:
                print(f"{path_str}: CHANGED")
                exit_code = 1

        # A cube absent from the manifest is invisible to the loop above: the
        # audit would report MATCH on every recorded LUT and say nothing about
        # a new one. Sweep the recorded tree so that cannot happen.
        root = Path(args.root) if getattr(args, "root", None) else manifest_scan_root(manifest_raw)
        if root is None:
            print("orphan sweep: SKIPPED (manifest records no common directory; pass --root)")
        elif not root.is_dir():
            print(f"orphan sweep: SKIPPED ({root} is not a directory)")
        else:
            # State the root. It is derived, so a manifest confined to one
            # directory sweeps only that directory, and the line is what makes
            # that visible instead of a silent narrowing.
            print(f"orphan sweep: {root}")
            orphans = find_orphan_cubes(manifest_raw, root)
            expected_orphans, unexpected_orphans = classify_orphans(orphans, root)
            strict_orphans = getattr(args, "strict_orphans", False)

            if strict_orphans:
                for p in orphans:
                    print(f"{p}: ORPHAN")
                    exit_code = 1
            else:
                for p in unexpected_orphans:
                    print(f"{p}: ORPHAN")
                    exit_code = 1

                counts: dict[str, int] = {}
                for p in expected_orphans:
                    try:
                        rel = p.relative_to(root)
                    except ValueError:
                        rel = p.resolve().relative_to(root.resolve())
                    sensor_dir = rel.parts[0]
                    counts[sensor_dir] = counts.get(sensor_dir, 0) + 1

                for sensor_dir in sorted(counts):
                    print(
                        f"{root / sensor_dir}: {counts[sensor_dir]} per-apparatus cubes "
                        f"(unrecorded by design; --strict-orphans lists them)"
                    )

        return exit_code

    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sanity and regression audit tool for .cube 3D LUTs."
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # validate
    validate_parser = subparsers.add_parser(
        "validate", help="Validate .cube files against sanity checks"
    )
    validate_parser.add_argument("cubes", nargs="+", help="Path(s) to .cube file(s)")

    # sample
    sample_parser = subparsers.add_parser(
        "sample", help="Sample .cube at normalized RGB coordinate using trilinear interpolation"
    )
    sample_parser.add_argument("cube", help="Path to .cube file")
    sample_parser.add_argument("r", type=float, help="Red coordinate")
    sample_parser.add_argument("g", type=float, help="Green coordinate")
    sample_parser.add_argument("b", type=float, help="Blue coordinate")

    # compare
    compare_parser = subparsers.add_parser("compare", help="Compare two .cube files")
    compare_parser.add_argument("a", help="Path to first .cube file")
    compare_parser.add_argument("b", help="Path to second .cube file")

    # manifest
    manifest_parser = subparsers.add_parser(
        "manifest", help="Record or check manifest of content hashes"
    )
    manifest_group = manifest_parser.add_mutually_exclusive_group(required=True)
    manifest_group.add_argument(
        "--record", metavar="OUT_JSON", help="Record content hashes to JSON file"
    )
    manifest_group.add_argument(
        "--check", metavar="IN_JSON", help="Check content hashes against JSON file"
    )
    manifest_parser.add_argument(
        "cubes", nargs="*", help="Cube file(s) to record (used with --record)"
    )
    manifest_parser.add_argument(
        "--root",
        metavar="DIR",
        help="Directory to sweep for unrecorded cubes with --check "
        "(default: the deepest directory containing every recorded path)",
    )
    manifest_parser.add_argument(
        "--strict-orphans",
        action="store_true",
        help="Restore old behaviour of listing per-apparatus builds as ORPHAN and failing",
    )

    args = parser.parse_args()

    if args.subcommand == "validate":
        return cmd_validate(args)
    if args.subcommand == "sample":
        return cmd_sample(args)
    if args.subcommand == "compare":
        return cmd_compare(args)
    if args.subcommand == "manifest":
        return cmd_manifest(args)

    return 1


if __name__ == "__main__":
    sys.exit(main())
