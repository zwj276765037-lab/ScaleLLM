#!/usr/bin/env python3
"""Generate address-sensitive accelerator-schedule QK vectors.

The query memory contains a distinct 128-D vector for every one of the
8 query rows x 32 Q heads.  The key memory follows the production cache
address exactly: {kv_head[2:0], token[6:0], group[1:0]}.  Consequently the
same KV head/token is reused across query rows and across the four Q heads in
one GQA group; it is not flattened in scheduler-consumption order.
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
import sys
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
HAP = HERE.parents[2] / "HAP_new"
SRC = HAP / "data" / "qk_score_row_128"
OUT = HERE / "data_arch"
ROWS = 8
HEADS = 32
KV_HEADS = 8
KEYS = 128
GROUPS = 4
LANES = 32
HEAD_SCALE_Q16 = 5793

sys.path.insert(0, str(HAP / "model"))
from fixbit_v2 import (  # noqa: E402
    q24k12_group_dot_s40,
    score_finalize_s20,
    score_group_q14_s35,
)


def sx(value: int, width: int) -> int:
    return value - (1 << width) if value & (1 << (width - 1)) else value


def unpack_signed(record: int, width: int, count: int) -> list[int]:
    mask = (1 << width) - 1
    return [sx((record >> (lane * width)) & mask, width)
            for lane in range(count)]


def pack_lanes(values: list[int], width: int) -> int:
    mask = (1 << width) - 1
    return sum((int(value) & mask) << (lane * width)
               for lane, value in enumerate(values))


def fp16_bits(value: float) -> int:
    return int(np.float16(value).view(np.uint16))


def fp32_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", float(np.float32(value))))[0]


def bits_fp16(value: int) -> np.float16:
    return np.asarray([value], dtype=np.uint16).view(np.float16)[0]


def bits_fp32(value: int) -> np.float32:
    return np.asarray([value], dtype=np.uint32).view(np.float32)[0]


def ftz16(value: float | np.float16) -> np.float16:
    rounded = np.float16(value)
    bits = int(rounded.view(np.uint16))
    if (bits & 0x7C00) == 0:
        return bits_fp16(bits & 0x8000)
    return rounded


def mul16(a: np.float16, b: np.float16) -> np.float16:
    with np.errstate(over="ignore", invalid="ignore"):
        product = np.float32(ftz16(a)) * np.float32(ftz16(b))
        # Xilinx Floating-Point v7.1 flushes a half result below the midpoint
        # between the largest subnormal and smallest normal. Values at/above
        # that midpoint round to 0x0400; lower values flush to signed zero.
        normal_round_midpoint = 2.0**-14 * (1.0 - 2.0**-12)
        if ((product != 0) and
                (abs(float(product)) < normal_round_midpoint)):
            return bits_fp16(0x8000 if product < 0 else 0x0000)
        return ftz16(product)


def balanced_sum_f32(values: list[np.float32]) -> np.float32:
    work = [np.float32(value) for value in values]
    if not work or (len(work) & (len(work) - 1)):
        raise ValueError("balanced FP32 tree requires a nonzero power of two")
    while len(work) > 1:
        work = [np.float32(work[index] + work[index + 1])
                for index in range(0, len(work), 2)]
    return work[0]


def clip_score(value: int) -> tuple[int, bool]:
    clipped = max(-(16 << 14), min(16 << 14, value))
    return clipped, clipped != value


def write_mem(path: Path, values: list[int], digits: int) -> None:
    mask = (1 << (4 * digits)) - 1
    path.write_text("".join(f"{value & mask:0{digits}x}\n"
                            for value in values), encoding="ascii")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bank_sha256(values: list[int], digits: int) -> str:
    payload = "".join(f"{value:0{digits}x}\n" for value in values)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def main() -> None:
    query_start = int(os.environ.get("M7_QUERY_START", "0"))
    valid_keys = int(os.environ.get("M7_VALID_KEYS", "8"))
    out = Path(os.environ.get("M7_DATA_OUT", str(OUT))).resolve()
    if not 0 <= query_start <= 127:
        raise ValueError("M7_QUERY_START must be in [0, 127]")
    if not 1 <= valid_keys <= 128:
        raise ValueError("M7_VALID_KEYS must be in [1, 128]")

    q_records = [int(line, 16) for line in
                 (SRC / "query_group_s24.mem").read_text().splitlines()]
    k_records = [int(line, 16) for line in
                 (SRC / "key_group_s12.mem").read_text().splitlines()]
    meta_records = [int(line, 16) for line in
                    (SRC / "key_meta16.mem").read_text().splitlines()]
    if len(q_records) != KV_HEADS * GROUPS:
        raise AssertionError("source query template count changed")
    if len(k_records) != KV_HEADS * KEYS * GROUPS:
        raise AssertionError("source key cache size changed")
    if len(meta_records) != len(k_records):
        raise AssertionError("source key/meta lengths differ")

    source_queries = [
        [unpack_signed(q_records[template * GROUPS + group], 24, LANES)
         for group in range(GROUPS)]
        for template in range(KV_HEADS)
    ]
    source_keys = [
        [[unpack_signed(
            k_records[((kv_head * KEYS + key) * GROUPS) + group],
            12, LANES) for group in range(GROUPS)]
         for key in range(KEYS)]
        for kv_head in range(KV_HEADS)
    ]
    source_meta = [
        [[meta_records[((kv_head * KEYS + key) * GROUPS) + group]
          for group in range(GROUPS)] for key in range(KEYS)]
        for kv_head in range(KV_HEADS)
    ]

    # Templates 0 and 1 are the old all-zero and full-scale corner cases.
    # Use the six bounded, nondegenerate templates and encode the complete
    # row/head identity by sign-flipping eight common nonzero lanes.  This is
    # exact in S24, FP16, and FP32 and cannot introduce overflow or NaN.
    bounded_templates = tuple(range(2, 8))
    tag_lanes = [lane for lane in range(GROUPS * LANES)
                 if all(source_queries[template][lane // LANES]
                        [lane % LANES] != 0
                        for template in bounded_templates)][:8]
    if len(tag_lanes) != 8:
        raise AssertionError("not enough common nonzero query tag lanes")

    query_fixed_groups: list[list[list[list[int]]]] = []
    for row in range(ROWS):
        row_queries: list[list[list[int]]] = []
        for head in range(HEADS):
            logical_id = row * HEADS + head
            template = bounded_templates[(row + head) % len(bounded_templates)]
            flat = [value for group in source_queries[template]
                    for value in group]
            for bit, lane in enumerate(tag_lanes):
                if (logical_id >> bit) & 1:
                    flat[lane] = -flat[lane]
            row_queries.append([flat[group * LANES:(group + 1) * LANES]
                                for group in range(GROUPS)])
        query_fixed_groups.append(row_queries)

    query_fixed: list[int] = []
    query16: list[int] = []
    query32: list[int] = []
    query16_values: list[list[list[list[np.float16]]]] = []
    query32_values: list[list[list[list[np.float32]]]] = []
    for row in range(ROWS):
        q16_row: list[list[list[np.float16]]] = []
        q32_row: list[list[list[np.float32]]] = []
        for head in range(HEADS):
            q16_head: list[list[np.float16]] = []
            q32_head: list[list[np.float32]] = []
            for group in range(GROUPS):
                fixed_lanes = query_fixed_groups[row][head][group]
                lanes16 = [np.float16(value / float(1 << 16))
                           for value in fixed_lanes]
                lanes32 = [np.float32(value / float(1 << 16))
                           for value in fixed_lanes]
                if not (all(np.isfinite(value) for value in lanes16) and
                        all(np.isfinite(value) for value in lanes32)):
                    raise AssertionError("nonfinite transformed query")
                query_fixed.append(pack_lanes(fixed_lanes, 24))
                query16.append(pack_lanes([fp16_bits(value)
                                           for value in lanes16], 16))
                query32.append(pack_lanes([fp32_bits(value)
                                           for value in lanes32], 32))
                q16_head.append(lanes16)
                q32_head.append(lanes32)
            q16_row.append(q16_head)
            q32_row.append(q32_head)
        query16_values.append(q16_row)
        query32_values.append(q32_row)

    # K is laid out by the production 12-bit address, never by consumption
    # order: address = (kv_head << 9) | (token << 2) | group.
    key_fixed_group: list[int] = []
    meta_fixed_group: list[int] = []
    key16_group: list[int] = []
    key32_group: list[int] = []
    key16_values: list[list[list[list[np.float16]]]] = []
    key32_values: list[list[list[list[np.float32]]]] = []
    for kv_head in range(KV_HEADS):
        k16_head: list[list[list[np.float16]]] = []
        k32_head: list[list[list[np.float32]]] = []
        for key in range(KEYS):
            k16_key: list[list[np.float16]] = []
            k32_key: list[list[np.float32]] = []
            for group in range(GROUPS):
                fixed_lanes = source_keys[kv_head][key][group]
                meta = source_meta[kv_head][key][group]
                code = meta & 0xFF
                shift = (meta >> 8) & 0x3F
                if code == 0:
                    if shift != 0 or any(fixed_lanes):
                        raise AssertionError("invalid zero-scale source K")
                    scale = 0.0
                else:
                    if not 8 <= shift <= 32:
                        raise AssertionError("invalid nonzero source K shift")
                    scale = code / float(1 << shift)
                lanes16 = [np.float16(value * scale)
                           for value in fixed_lanes]
                lanes32 = [np.float32(value * scale)
                           for value in fixed_lanes]
                if not (all(np.isfinite(value) for value in lanes16) and
                        all(np.isfinite(value) for value in lanes32)):
                    raise AssertionError("nonfinite key conversion")
                key_fixed_group.append(pack_lanes(fixed_lanes, 12))
                meta_fixed_group.append(meta)
                key16_group.append(pack_lanes([fp16_bits(value)
                                                for value in lanes16], 16))
                key32_group.append(pack_lanes([fp32_bits(value)
                                                for value in lanes32], 32))
                k16_key.append(lanes16)
                k32_key.append(lanes32)
            k16_head.append(k16_key)
            k32_head.append(k32_key)
        key16_values.append(k16_head)
        key32_values.append(k32_head)

    row_key_counts = [min(query_start + row + 1, valid_keys)
                      for row in range(ROWS)]
    expected_fixed: list[int] = []
    expected16: list[int] = []
    expected32: list[int] = []
    fixed_clips = 0
    fp16_clips = 0
    fp32_clips = 0
    scale16 = bits_fp16(0x2DA8)
    scale32 = bits_fp32(0x3DB50800)

    # Three independent arithmetic goldens.  The floating paths reproduce
    # the exact balanced 128-input tree used by m7_fp_qk_slot_arch.
    for row in range(ROWS):
        for head in range(HEADS):
            kv_head = head >> 2
            query_groups = query_fixed_groups[row][head]
            q16_flat = [value for group in query16_values[row][head]
                        for value in group]
            q32_flat = [value for group in query32_values[row][head]
                        for value in group]
            q16_scaled = [mul16(value, scale16) for value in q16_flat]
            if not all(np.isfinite(value) for value in q16_scaled):
                raise AssertionError("FP16 query prescale overflow/NaN")
            for key in range(row_key_counts[row]):
                fixed_groups: list[int] = []
                for group in range(GROUPS):
                    meta = source_meta[kv_head][key][group]
                    code = meta & 0xFF
                    shift = (meta >> 8) & 0x3F
                    if code == 0:
                        fixed_groups.append(0)
                    else:
                        dot = q24k12_group_dot_s40(
                            query_groups[group],
                            source_keys[kv_head][key][group])
                        fixed_groups.append(score_group_q14_s35(
                            dot, code, shift))
                score_fixed, clipped_fixed = score_finalize_s20(fixed_groups)
                expected_fixed.append(score_fixed)
                fixed_clips += int(clipped_fixed)

                k16_flat = [value for group in key16_values[kv_head][key]
                            for value in group]
                products16 = [np.float32(mul16(qvalue, kvalue))
                              for qvalue, kvalue in
                              zip(q16_scaled, k16_flat)]
                sum16 = balanced_sum_f32(products16)
                if not np.isfinite(sum16):
                    raise AssertionError("FP16 product/reduction overflow/NaN")
                raw16 = int(np.rint(float(sum16) * (1 << 14)))
                score16, clipped16 = clip_score(raw16)
                expected16.append(score16)
                fp16_clips += int(clipped16)

                k32_flat = [value for group in key32_values[kv_head][key]
                            for value in group]
                products32 = [np.float32(qvalue * kvalue)
                              for qvalue, kvalue in zip(q32_flat, k32_flat)]
                dot32 = balanced_sum_f32(products32)
                scaled32 = np.float32(dot32 * scale32)
                if not np.isfinite(scaled32):
                    raise AssertionError("FP32 product/reduction overflow/NaN")
                raw32 = int(np.rint(float(scaled32) * (1 << 14)))
                score32, clipped32 = clip_score(raw32)
                expected32.append(score32)
                fp32_clips += int(clipped32)

    expected_scores = HEADS * sum(row_key_counts)
    expected_query_records = ROWS * HEADS * GROUPS
    expected_key_records = KV_HEADS * KEYS * GROUPS
    lengths = {
        "query_fixed": len(query_fixed),
        "query_fp16": len(query16),
        "query_fp32": len(query32),
        "key_fixed": len(key_fixed_group),
        "key_meta": len(meta_fixed_group),
        "key_fp16": len(key16_group),
        "key_fp32": len(key32_group),
        "expected_fixed": len(expected_fixed),
        "expected_fp16": len(expected16),
        "expected_fp32": len(expected32),
    }
    if any(lengths[name] != expected_query_records for name in
           ("query_fixed", "query_fp16", "query_fp32")):
        raise AssertionError(f"query length self-check failed: {lengths}")
    if any(lengths[name] != expected_key_records for name in
           ("key_fixed", "key_meta", "key_fp16", "key_fp32")):
        raise AssertionError(f"key length self-check failed: {lengths}")
    if any(lengths[name] != expected_scores for name in
           ("expected_fixed", "expected_fp16", "expected_fp32")):
        raise AssertionError(f"golden length self-check failed: {lengths}")

    query_unique = {
        "fixed": len(set(tuple(query_fixed[index:index + GROUPS])
                         for index in range(0, len(query_fixed), GROUPS))),
        "fp16": len(set(tuple(query16[index:index + GROUPS])
                        for index in range(0, len(query16), GROUPS))),
        "fp32": len(set(tuple(query32[index:index + GROUPS])
                        for index in range(0, len(query32), GROUPS))),
    }
    if any(count != ROWS * HEADS for count in query_unique.values()):
        raise AssertionError(f"query diversity self-check failed: {query_unique}")

    kv_bank_checksums = {
        "fixed": [bank_sha256(key_fixed_group[head * KEYS * GROUPS:
                                               (head + 1) * KEYS * GROUPS], 96)
                  for head in range(KV_HEADS)],
        "fp16": [bank_sha256(key16_group[head * KEYS * GROUPS:
                                          (head + 1) * KEYS * GROUPS], 128)
                 for head in range(KV_HEADS)],
        "fp32": [bank_sha256(key32_group[head * KEYS * GROUPS:
                                          (head + 1) * KEYS * GROUPS], 256)
                 for head in range(KV_HEADS)],
    }
    kv_unique = {name: len(set(checksums))
                 for name, checksums in kv_bank_checksums.items()}
    if any(count != KV_HEADS for count in kv_unique.values()):
        raise AssertionError(f"KV-head diversity self-check failed: {kv_unique}")

    out.mkdir(parents=True, exist_ok=True)
    outputs = {
        "query_group_fixed.mem": (query_fixed, 192),
        "query_group_fp16.mem": (query16, 128),
        "query_group_fp32.mem": (query32, 256),
        "key_group_fixed.mem": (key_fixed_group, 96),
        "key_meta_fixed.mem": (meta_fixed_group, 4),
        "key_group_fp16.mem": (key16_group, 128),
        "key_group_fp32.mem": (key32_group, 256),
        "expected_fixed.mem": (expected_fixed, 5),
        "expected_fp16.mem": (expected16, 5),
        "expected_fp32.mem": (expected32, 5),
    }
    for filename, (values, digits) in outputs.items():
        write_mem(out / filename, values, digits)
    checksums = {filename: sha256_file(out / filename)
                 for filename in outputs}

    manifest = {
        "schema": "m7_accelerator_slot_address_sensitive_v2",
        "query_start": query_start,
        "valid_keys": valid_keys,
        "query_rows": ROWS,
        "query_heads": HEADS,
        "kv_heads": KV_HEADS,
        "gqa_q_heads_per_kv_head": 4,
        "gqa_mapping": "kv_head = q_head >> 2",
        "logical_score_rows": ROWS * HEADS,
        "row_key_counts": row_key_counts,
        "scores": expected_scores,
        "query_groups": expected_query_records,
        "key_cache_groups": expected_key_records,
        "consumed_key_groups": GROUPS * expected_scores,
        "schedule": "one shared QK slot; row-major, then query-head; four groups/key",
        "input_cadence": "one group32 cache record every two cycles",
        "query_address_layout": "{query_row[2:0], q_head[4:0], group[1:0]}",
        "key_address_layout": "{kv_head[2:0], token[6:0], group[1:0]}",
        "cache_response_model": "one-cycle/no-contention",
        "V_zero_control_only": True,
        "diversity": {
            "query_method": "bounded source templates 2..7 plus exact 8-bit row/head sign tag",
            "query_tag_lanes": tag_lanes,
            "unique_query_vectors": query_unique,
            "unique_kv_head_banks": kv_unique,
            "kv_bank_sha256": kv_bank_checksums,
            "key_reuse": "one semantic KV cache shared by all query rows and four Q heads per KV head",
        },
        "numeric_models": {
            "fixed": "independent exact Q24xK12/group scale/accum/clip golden",
            "fp16": "FP16 query prescale and products, FTZ, balanced FP32 reduction, clip",
            "fp32": "FP32 products, balanced FP32 reduction and head scale, clip",
        },
        "clip_counts": {
            "fixed": fixed_clips,
            "fp16": fp16_clips,
            "fp32": fp32_clips,
        },
        "record_counts": lengths,
        "sha256": checksums,
        "self_check": {
            "all_256_queries_unique_each_format": True,
            "all_8_kv_banks_unique_each_format": True,
            "semantic_key_cache_records": expected_key_records,
            "all_fp_inputs_and_intermediates_finite": True,
            "independent_golden_lengths_match_schedule": True,
        },
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print("M7_ARCH_VECTOR_JSON:", json.dumps(manifest, sort_keys=True))
    print("PASS: address-sensitive M7 architecture vectors generated")


if __name__ == "__main__":
    main()
