#!/usr/bin/env python3
"""Run synthetic or captured-activation FP-to-Q precision comparisons."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import numpy as np

from fptoq_core import GROUP_SIZE, compare_groups


def _is_down_proj_label(label: str) -> bool:
    """Accept capture labels as either op names or fully qualified paths."""
    return label == "down_proj" or label.endswith(".down_proj")


def _format_widths(labels: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    down = np.fromiter(
        (_is_down_proj_label(str(label)) for label in labels),
        dtype=bool,
        count=labels.size,
    )
    return np.where(down, 32, 24), np.where(down, 35, 27)


def synthetic_groups(count_per_case: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    cases: list[tuple[str, np.ndarray]] = []

    cases.append(("gaussian_rms1", rng.normal(0.0, 1.0, (count_per_case, GROUP_SIZE))))
    cases.append(("gaussian_rms4", rng.normal(0.0, 4.0, (count_per_case, GROUP_SIZE))))
    cases.append(("laplace_rms1", rng.laplace(
        0.0, 1.0 / np.sqrt(2.0), (count_per_case, GROUP_SIZE))))
    student = rng.standard_t(3.0, (count_per_case, GROUP_SIZE)) / np.sqrt(3.0)
    cases.append(("student_t3_rms1", student))

    outlier = rng.normal(0.0, 1.0, (count_per_case, GROUP_SIZE))
    lanes = rng.integers(0, GROUP_SIZE, count_per_case)
    outlier[np.arange(count_per_case), lanes] += rng.choice([-16.0, 16.0], count_per_case)
    cases.append(("single_outlier_16", outlier))

    cases.append(("uniform_near_s24_limit", rng.uniform(
        -127.9, 127.9, (count_per_case, GROUP_SIZE))))
    cases.append(("tiny_rms_2^-14", rng.normal(
        0.0, 2.0**-14, (count_per_case, GROUP_SIZE))))

    overflow = rng.normal(0.0, 1.0, (count_per_case, GROUP_SIZE))
    overflow[:, 0] = rng.choice([-160.0, 160.0], count_per_case)
    cases.append(("overflow_probe", overflow))

    groups = np.concatenate([values for _, values in cases], axis=0).astype(np.float64)
    labels = np.concatenate([
        np.full(values.shape[0], name, dtype="U32") for name, values in cases
    ])
    return groups, labels


def load_groups(path: Path) -> tuple[np.ndarray, np.ndarray]:
    if path.suffix == ".npy":
        values = np.load(path, allow_pickle=False)
        labels = None
    elif path.suffix == ".npz":
        archive = np.load(path, allow_pickle=False)
        key = "groups" if "groups" in archive else "activations"
        if key not in archive:
            raise ValueError(f"{path} needs a 'groups' or 'activations' array")
        values = archive[key]
        labels = archive["labels"] if "labels" in archive else None
    else:
        raise ValueError("input must be .npy or .npz")

    values = np.asarray(values, dtype=np.float64)
    if values.shape[-1] % GROUP_SIZE:
        raise ValueError(f"last dimension {values.shape[-1]} is not divisible by 32")
    groups = values.reshape(-1, GROUP_SIZE)
    if labels is None:
        group_labels = np.full(groups.shape[0], path.stem, dtype="U64")
    else:
        group_labels = np.asarray(labels).reshape(-1).astype("U64")
        if group_labels.size != groups.shape[0]:
            raise ValueError(
                f"labels has {group_labels.size} rows but groups has {groups.shape[0]}")
    return groups, group_labels


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def run_analysis(
    groups: np.ndarray,
    labels: np.ndarray,
    *,
    output_dir: Path,
    source: str,
    seed: int | None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for label in sorted(np.unique(labels).tolist()):
        selected = groups[labels == label]
        input_width = 32 if _is_down_proj_label(str(label)) else 24
        output_width = 35 if input_width == 32 else 27
        rows.append({
            "slice": label,
            **compare_groups(
                selected, input_width=input_width, output_width=output_width),
        })
    input_widths, output_widths = _format_widths(labels)
    rows.append({
        "slice": "__all__",
        **compare_groups(
            groups, input_width=input_widths, output_width=output_widths),
    })

    fieldnames = list(rows[0].keys())
    with (output_dir / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    manifest = _json_safe({
        "schema": "scalellm_fp_to_q_hadamard_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "seed": seed,
        "group_size": GROUP_SIZE,
        "groups": int(groups.shape[0]),
        "labels": {label: int(np.sum(labels == label)) for label in np.unique(labels)},
        "comparison": (
            "archived software FP64 H32 + float A8/ScaleCode QDQ versus "
            "production FP->S24 Q8.16->S27 Q11.16 (regular ops) or "
            "FP->S32 Q16.16->S35 Q19.16 (down_proj) + integer H32 "
            "coefficient/rounding + integer A8/ScaleCode QDQ"
        ),
        "rows": rows,
    })
    (output_dir / "summary.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, help="optional .npy/.npz activation trace")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--count-per-case", type=int, default=4096)
    parser.add_argument("--seed", type=int, default=20260911)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.input is None:
        groups, labels = synthetic_groups(args.count_per_case, args.seed)
        source = "deterministic synthetic distributions and explicit boundary probes"
    else:
        groups, labels = load_groups(args.input)
        source = str(args.input.resolve())
    manifest = run_analysis(
        groups, labels, output_dir=args.output_dir, source=source, seed=args.seed)
    overall = manifest["rows"][-1]
    print(json.dumps({
        "output_dir": str(args.output_dir.resolve()),
        "groups": manifest["groups"],
        "overall": overall,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
