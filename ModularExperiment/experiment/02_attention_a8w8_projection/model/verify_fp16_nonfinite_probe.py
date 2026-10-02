#!/usr/bin/env python3
"""Validate and freeze the M02 AMD FP16 nonfinite probe bit patterns."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any


CORRELATIONS = [
    0, 65503, 65504, 65519, 65520, 65521, 65535, 65536,
    -65503, -65504, -65519, -65520, -65521, -65535, -65536,
    106787, -121705, 269277, -277754, 298909, -269769,
    65520, -65520, 65520, -65520,
]
ZERO_ACT_SCALE_CASES = {len(CORRELATIONS) - 4, len(CORRELATIONS) - 3}
ZERO_WEIGHT_SCALE_CASES = {len(CORRELATIONS) - 2, len(CORRELATIONS) - 1}
RECORD_PREFIX = "M02_FP16_SEMANTIC_RECORD_JSON: "
SUMMARY_PREFIX = "M02_FP16_SEMANTIC_SUMMARY_JSON: "
HEX_FIELDS = {
    "act_scale_fp16": 4,
    "weight_scale_fp16": 4,
    "correlation_fp32": 8,
    "correlation_fp16": 4,
    "mul1_fp16": 4,
    "mul2_fp16": 4,
    "widen_fp32": 8,
    "float_to_s42_raw48": 12,
    "output_s42": 11,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fp32_bits(value: int) -> int:
    return struct.unpack("<I", struct.pack("<f", float(value)))[0]


def parse_hex(record: dict[str, Any], field: str, digits: int) -> int:
    value = record.get(field)
    if (not isinstance(value, str) or len(value) != digits + 2 or
            not value.startswith("0x")):
        raise AssertionError(f"invalid {field}: {value!r}")
    parsed = int(value[2:], 16)
    if parsed >= (1 << (4 * digits)):
        raise AssertionError(f"out-of-range {field}: {value}")
    return parsed


def fp16_class(bits: int) -> str:
    exponent = (bits >> 10) & 0x1f
    fraction = bits & 0x3ff
    if exponent != 0x1f:
        return "finite"
    return "nan" if fraction else "infinity"


def fp32_class(bits: int) -> str:
    exponent = (bits >> 23) & 0xff
    fraction = bits & 0x7fffff
    if exponent != 0xff:
        return "finite"
    return "nan" if fraction else "infinity"


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.resolve(strict=True)
    summary_path = run_dir / "summary.txt"
    if not summary_path.is_file():
        raise AssertionError("missing probe summary.txt")
    lines = summary_path.read_text(encoding="utf-8").splitlines()
    records = [json.loads(line[len(RECORD_PREFIX):]) for line in lines
               if line.startswith(RECORD_PREFIX)]
    summaries = [json.loads(line[len(SUMMARY_PREFIX):]) for line in lines
                 if line.startswith(SUMMARY_PREFIX)]
    if len(records) != len(CORRELATIONS):
        raise AssertionError(
            f"expected {len(CORRELATIONS)} records, got {len(records)}")
    if len(summaries) != 1:
        raise AssertionError(f"expected one summary, got {len(summaries)}")
    summary = summaries[0]
    expected_summary = {
        "cases": len(CORRELATIONS),
        "completed": len(CORRELATIONS),
        "failures": 0,
        "input_groups": len(CORRELATIONS),
        "output_groups": len(CORRELATIONS),
    }
    if summary != expected_summary:
        raise AssertionError(f"probe summary mismatch: {summary}")

    frozen_records: list[dict[str, Any]] = []
    for index, (record, correlation) in enumerate(zip(records, CORRELATIONS)):
        if record.get("case") != index:
            raise AssertionError(f"case ordering mismatch at {index}")
        if record.get("correlation_s21") != correlation:
            raise AssertionError(f"correlation mismatch at case {index}")
        parsed = {
            field: parse_hex(record, field, digits)
            for field, digits in HEX_FIELDS.items()
        }
        expected_act_scale = (
            0 if index in ZERO_ACT_SCALE_CASES else 0x1c00)
        expected_weight_scale = (
            0 if index in ZERO_WEIGHT_SCALE_CASES else 0x1c00)
        if (parsed["act_scale_fp16"] != expected_act_scale or
                parsed["weight_scale_fp16"] != expected_weight_scale):
            raise AssertionError(f"scale mismatch at case {index}")
        if parsed["correlation_fp32"] != fp32_bits(correlation):
            raise AssertionError(f"S21-to-FP32 mismatch at case {index}")
        if parsed["output_s42"] >= (1 << 42):
            raise AssertionError(f"output_s42 padding bits are nonzero at case {index}")

        classifications = {
            "correlation_fp16_class": fp16_class(
                parsed["correlation_fp16"]),
            "mul1_fp16_class": fp16_class(parsed["mul1_fp16"]),
            "mul2_fp16_class": fp16_class(parsed["mul2_fp16"]),
            "widen_fp32_class": fp32_class(parsed["widen_fp32"]),
        }
        flag_checks = {
            "correlation_fp16_nonfinite":
                classifications["correlation_fp16_class"] != "finite",
            "mul1_nonfinite":
                classifications["mul1_fp16_class"] != "finite",
            "mul2_nonfinite":
                classifications["mul2_fp16_class"] != "finite",
            "widen_nonfinite":
                classifications["widen_fp32_class"] != "finite",
        }
        for field, expected in flag_checks.items():
            if record.get(field) != int(expected):
                raise AssertionError(
                    f"classification flag mismatch case={index} field={field}")

        if ((parsed["float_to_s42_raw48"] & ((1 << 42) - 1)) !=
                parsed["output_s42"]):
            raise AssertionError(f"S42 truncation mismatch at case {index}")
        frozen = dict(record)
        frozen.update(classifications)
        frozen_records.append(frozen)

    class_counts: dict[str, dict[str, int]] = {}
    for field in (
            "correlation_fp16_class", "mul1_fp16_class",
            "mul2_fp16_class", "widen_fp32_class"):
        class_counts[field] = {
            name: sum(record[field] == name for record in frozen_records)
            for name in ("finite", "infinity", "nan")
        }

    output = args.output.resolve()
    if output.parent != run_dir:
        raise AssertionError("semantic map must be written inside the run dir")
    payload = {
        "schema": "scalellm_m02_fp16_nonfinite_semantics_v1",
        "purpose": (
            "Observed AMD Floating-Point IP bit patterns for the exact "
            "matched FP16 projection scale-application chain; not a claim "
            "that nonfinite outputs are numerically valid."),
        "source_summary": str(summary_path),
        "source_summary_sha256": sha256_file(summary_path),
        "record_count": len(frozen_records),
        "class_counts": class_counts,
        "records": frozen_records,
    }
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "M02_FP16_SEMANTIC_VERIFY_PASS "
        f"records={len(frozen_records)} "
        f"summary_sha256={payload['source_summary_sha256']} "
        f"semantic_map_sha256={sha256_file(output)}")


if __name__ == "__main__":
    main()
