#!/usr/bin/env python3
"""Bit-exact numeric helpers for the HAP Llama SwiGLU MLP experiment."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable


MLP_FORMAT_ID_V1 = 0x4838_4D01
FULL_FORMAT_ID_V1 = 0x4838_4601
MLP_FORMAT_ID = 0x4838_4D05
FULL_FORMAT_ID = 0x4838_4605
MLP_GATE_UP_TOTAL_SHIFT_MIN = 20
MLP_DOWN_TOTAL_SHIFT_MIN = 12
MLP_TOTAL_SHIFT_MAX = 44
MLP_RAW_S33_ABS_MAX = 4_244_832_000
MLP_GATE_UP_GUARD_WIDTH = 37
MLP_DOWN_GUARD_WIDTH = 45
MLP_GATE_UP_ACCUM_WIDTH = 44
MLP_DOWN_ACCUM_WIDTH = 54
MLP_DOWN_OUTPUT_WIDTH = 32
ROWS = 8
HIDDEN = 4096
INTERMEDIATE = 14336
GROUP_SIZE = 32
OUTPUT_COLS = 16
INPUT_GROUPS = HIDDEN // GROUP_SIZE
INTERMEDIATE_GROUPS = INTERMEDIATE // GROUP_SIZE
GATE_UP_TILES = INTERMEDIATE // OUTPUT_COLS
DOWN_TILES = HIDDEN // OUTPUT_COLS
S24_MIN = -(1 << 23)
S24_MAX = (1 << 23) - 1
S32_MIN = -(1 << 31)
S32_MAX = (1 << 31) - 1
S35_MIN = -(1 << 34)
S35_MAX = (1 << 34) - 1
SCALE_EXACT_LIMIT = 4_261_478_400
SCALE_ROUND_LIMIT = 4_269_834_239
SILU_LIMIT_Q16 = 16 << 16
SILU_STEP_Q16 = 1 << 8
SILU_LUT_ENTRIES = 8193


def a8w4_two_column_packed(centered_activation: int,
                           weight0: int, weight1: int) -> tuple[int, int]:
    """Bit-exact model of one-DSP A8W4 two-output-column packing."""
    activation = require_signed(centered_activation, 9,
                                "centered activation")
    if not -255 <= activation <= 255:
        raise ValueError("centered activation must be in [-255,255]")
    w0 = require_signed(weight0, 4, "weight0")
    w1 = require_signed(weight1, 4, "weight1")
    activation_u9 = activation + 256
    w0_u4 = w0 & 0xF
    w1_u4 = w1 & 0xF
    packed_weight = w0_u4 | (w1_u4 << 13)
    dsp_product = activation_u9 * packed_weight
    unsigned0 = dsp_product & ((1 << 13) - 1)
    unsigned1 = (dsp_product >> 13) & ((1 << 13) - 1)

    def correct(unsigned_product: int, raw_weight: int,
                signed_weight: int) -> int:
        result = unsigned_product - (raw_weight << 8)
        if signed_weight < 0:
            result -= activation << 4
        return require_signed(result, 12, "A8W4 product")

    return correct(unsigned0, w0_u4, w0), \
        correct(unsigned1, w1_u4, w1)


def a8w4_group32_two_column(centered_activations: Iterable[int],
                            weights0: Iterable[int],
                            weights1: Iterable[int]) -> tuple[int, int]:
    """Exact S17 group32 dot products for two output columns."""
    activations = list(centered_activations)
    column0 = list(weights0)
    column1 = list(weights1)
    if len(activations) != GROUP_SIZE or len(column0) != GROUP_SIZE or \
            len(column1) != GROUP_SIZE:
        raise ValueError("A8W4 two-column dot requires 32 lanes")
    dot0 = 0
    dot1 = 0
    for activation, weight0, weight1 in zip(
            activations, column0, column1, strict=True):
        product0, product1 = a8w4_two_column_packed(
            activation, weight0, weight1)
        dot0 += product0
        dot1 += product1
    return require_signed(dot0, 17, "group32 dot0"), \
        require_signed(dot1, 17, "group32 dot1")


def round_half_away(value: float) -> int:
    if not math.isfinite(value):
        raise ValueError("value must be finite")
    return math.floor(value + 0.5) if value >= 0 else -math.floor(-value + 0.5)


def round_shift_away_zero(value: int, shift: int) -> int:
    if shift < 0:
        raise ValueError("shift must be non-negative")
    if shift == 0:
        return int(value)
    half = 1 << (shift - 1)
    if value >= 0:
        return (int(value) + half) >> shift
    return -(((-int(value)) + half) >> shift)


def mlp_recover_guard_s37(raw_s33: int, total_shift: int) -> int:
    """Align one legal Gate/Up contribution to signed S37/F24."""
    raw = require_signed(raw_s33, 33, "MLP raw contribution")
    if not MLP_GATE_UP_TOTAL_SHIFT_MIN <= total_shift <= MLP_TOTAL_SHIFT_MAX:
        raise ValueError("Gate/Up total_shift must be in [20,44]")
    guard = raw << (24 - total_shift) if total_shift < 24 else \
        raw >> (total_shift - 24)
    return require_signed(guard, MLP_GATE_UP_GUARD_WIDTH,
                          "Gate/Up Group32 guard")


def mlp_recover_down_guard_s45(raw_s33: int, total_shift: int) -> int:
    """Align one legal Down contribution to signed S45/F24."""
    raw = require_signed(raw_s33, 33, "MLP raw contribution")
    if not MLP_DOWN_TOTAL_SHIFT_MIN <= total_shift <= MLP_TOTAL_SHIFT_MAX:
        raise ValueError("Down total_shift must be in [12,44]")
    guard = raw << (24 - total_shift) if total_shift < 24 else \
        raw >> (total_shift - 24)
    return require_signed(guard, MLP_DOWN_GUARD_WIDTH,
                          "Down Group32 guard")


def require_signed(value: int, width: int, name: str = "value") -> int:
    low = -(1 << (width - 1))
    high = (1 << (width - 1)) - 1
    if not low <= int(value) <= high:
        raise ValueError(f"{name}={value} does not fit S{width}")
    return int(value)


def saturate_signed(value: int, width: int) -> tuple[int, bool]:
    low = -(1 << (width - 1))
    high = (1 << (width - 1)) - 1
    clamped = min(high, max(low, int(value)))
    return clamped, clamped != int(value)


def silu_real(value: float) -> float:
    # Stable definition avoids exp overflow for stress tests.
    if value >= 0:
        return value / (1.0 + math.exp(-value))
    exponential = math.exp(value)
    return value * exponential / (1.0 + exponential)


def build_silu_lut() -> tuple[int, ...]:
    output = []
    for index in range(SILU_LUT_ENTRIES):
        x_q16 = -SILU_LIMIT_Q16 + index * SILU_STEP_Q16
        encoded = round_half_away(silu_real(x_q16 / 65536.0) * 65536.0)
        encoded, saturated = saturate_signed(encoded, 24)
        if saturated:
            raise AssertionError("SiLU LUT unexpectedly saturated")
        output.append(encoded)
    return tuple(output)


def silu_lut_q16(gate_s24: int, table: tuple[int, ...]) -> int:
    gate = require_signed(gate_s24, 24, "gate")
    if len(table) != SILU_LUT_ENTRIES:
        raise ValueError("invalid SiLU table length")
    if gate <= -SILU_LIMIT_Q16:
        return 0
    if gate >= SILU_LIMIT_Q16:
        return gate
    address = (gate + SILU_LIMIT_Q16 + (SILU_STEP_Q16 // 2)) // SILU_STEP_Q16
    if not 0 <= address < SILU_LUT_ENTRIES:
        raise AssertionError("SiLU table address escaped range")
    return require_signed(table[address], 24, "silu")


def swiglu_product_s32(gate_s24: int, up_s24: int,
                       table: tuple[int, ...]) -> int:
    silu = silu_lut_q16(gate_s24, table)
    up = require_signed(up_s24, 24, "up")
    product_s48 = require_signed(silu * up, 48, "silu product")
    output = round_shift_away_zero(product_s48, 16)
    return require_signed(output, 32, "SwiGLU S32")


@dataclass(frozen=True)
class HadamardS32Result:
    values: tuple[int, ...]
    saturation_count: int


def hadamard32_product_normalized(
        values: Iterable[int]) -> HadamardS32Result:
    """S32 Q16.16 -> normalized Hadamard32 -> S35 Q19.16."""
    work = [require_signed(int(value), 32, f"lane[{index}]")
            for index, value in enumerate(values)]
    if len(work) != GROUP_SIZE:
        raise ValueError(f"Hadamard32 requires {GROUP_SIZE} values")

    distance = 1
    stage_width = 33
    while distance < GROUP_SIZE:
        next_work = work.copy()
        for base in range(0, GROUP_SIZE, distance * 2):
            for offset in range(distance):
                lhs = work[base + offset]
                rhs = work[base + offset + distance]
                next_work[base + offset] = require_signed(
                    lhs + rhs, stage_width, "Hadamard S32 sum")
                next_work[base + offset + distance] = require_signed(
                    lhs - rhs, stage_width, "Hadamard S32 difference")
        work = next_work
        distance *= 2
        stage_width += 1

    output: list[int] = []
    saturation_count = 0
    for value in work:
        product = require_signed(value * 11_585, 51,
                                 "Hadamard S32 normalization product")
        rounded = round_shift_away_zero(product, 16)
        saturated, did_saturate = saturate_signed(rounded, 35)
        output.append(saturated)
        saturation_count += int(did_saturate)
    return HadamardS32Result(tuple(output), saturation_count)


@dataclass(frozen=True)
class A8S35Result:
    values: tuple[int, ...]
    scale_code: int
    scale_shift: int
    zero_point: int
    clip_low: int
    clip_high: int

    @property
    def metadata(self) -> int:
        return (self.scale_shift << 16) | (self.scale_code << 8) | \
            self.zero_point


def round_div_even(numerator: int, denominator: int) -> int:
    """Round a non-negative rational to nearest, with exact ties to even."""
    if numerator < 0 or denominator <= 0:
        raise ValueError("round_div_even requires numerator>=0 and denominator>0")
    quotient, remainder = divmod(numerator, denominator)
    doubled = remainder << 1
    if doubled > denominator or (doubled == denominator and quotient & 1):
        quotient += 1
    return quotient


def _encode_scale_from_diff(diff_q16: int) -> tuple[int, int]:
    if diff_q16 <= 0:
        return 0, 0
    shifted = int(diff_q16)
    shift = 0
    while shift < 63 and (shifted << 1) <= SCALE_EXACT_LIMIT:
        shifted <<= 1
        shift += 1
    code = round_div_even(shifted, 255 << 16)
    return min(255, max(1, code)), shift


def minmax_a8_quantize_s35(values: Iterable[int]) -> A8S35Result:
    """Raw Group32 asymmetric U8 Min/Max quantization after Hadamard."""
    source = [require_signed(int(value), 35, f"lane[{index}]")
              for index, value in enumerate(values)]
    if len(source) != GROUP_SIZE:
        raise ValueError(f"A8 group requires {GROUP_SIZE} values")
    low = min(min(source), 0)
    high = max(max(source), 0)
    diff = high - low
    if diff == 0:
        return A8S35Result((0,) * GROUP_SIZE, 0, 0, 0,
                           low, high)
    code, shift = _encode_scale_from_diff(diff)
    zero_point = min(255, round_div_even((-low) * 255, diff))
    output = []
    for value in source:
        affine_numerator = value * 255 + zero_point * diff
        if affine_numerator <= 0:
            quantized = 0
        elif affine_numerator >= 255 * diff:
            quantized = 255
        else:
            quantized = round_div_even(affine_numerator, diff)
        output.append(quantized)
    return A8S35Result(tuple(output), code, shift, zero_point,
                       low, high)


def robust_a8_quantize_s35(values: Iterable[int]) -> A8S35Result:
    """Compatibility alias for callers being migrated to Min/Max naming."""
    return minmax_a8_quantize_s35(values)


def twos_hex(value: int, width: int) -> str:
    require_signed(value, width)
    digits = (width + 3) // 4
    return f"{value & ((1 << width) - 1):0{digits}x}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class CapacityModel:
    attention_bytes_per_layer: int
    mlp_bytes_per_layer: int
    full_bytes: int
    visible_ddr_bytes: int

    @property
    def full_resident_w8(self) -> bool:
        return self.full_bytes <= self.visible_ddr_bytes


def capacity_model() -> CapacityModel:
    mib = 1 << 20
    attention = (40 * mib) + ((5 * mib) // 2)
    mlp = (168 * mib) + ((21 * mib) // 2)
    return CapacityModel(attention, mlp, 32 * (attention + mlp), 4 << 30)


def architecture_summary() -> dict:
    clock_hz = 100_000_000
    cohort_rows = 16
    layers = 32
    mib = 1 << 20
    attention_matrix_bytes = 1_280 * mib
    mlp_matrix_bytes = 2_688 * mib
    matrix_bytes = attention_matrix_bytes + mlp_matrix_bytes
    visible_ddr_bytes = 4 << 30
    attention_32_cycles = 22_668_478
    mlp_32_cycles = 22_292_480
    serial_32_cycles = attention_32_cycles + mlp_32_cycles
    pipeline_slot_cycles = max(attention_32_cycles, mlp_32_cycles)

    def stage(cycles: int, evidence: str) -> dict:
        return {
            "cycles_32layer_cohort16": cycles,
            "seconds_32layer_cohort16": cycles / clock_hz,
            "tokens_per_second": cohort_rows * clock_hz / cycles,
            "evidence": evidence,
        }

    ddr_targets = []
    for tokens_per_second in (60, 65, 70):
        useful_gbps = matrix_bytes * tokens_per_second / cohort_rows / 1e9
        ddr_targets.append({
            "tokens_per_second": tokens_per_second,
            "cohorts_per_second": tokens_per_second / cohort_rows,
            "useful_gbps": useful_gbps,
            "peak_fraction": useful_gbps / 38.4,
        })

    return {
        "schema": "hap_attention_mlp_architecture_model_v3",
        "model": "Llama-3.1-8B",
        "platform": "VCU118 xcvu9p-flga2104-2L-e",
        "hidden": HIDDEN,
        "intermediate": INTERMEDIATE,
        "layers": layers,
        "clock_hz": clock_hz,
        "cohort": {
            "logical_rows": cohort_rows,
            "active_rows": 32,
            "inflight_cohorts": 2,
        },
        "attention": {
            "activation_bits": 8,
            "weight_bits": 8,
            "physical_rows": 8,
            "waves_per_cohort": 2,
            "group": 32,
            "projection_dsp48e2": 2_240,
        },
        "mlp": {
            "full_format_id": FULL_FORMAT_ID,
            "internal_format_id": MLP_FORMAT_ID,
            "activation_bits": 8,
            "weight_bits": 4,
            "branches": 2,
            "rows_per_branch": 8,
            "columns": 12,
            "group": 32,
            "kernel_dsp48e2": 3_072,
            "compact_input_dsp48e2": 8,
            "s35_dividers_per_quantizer": 2,
            "s35_xsim_max_group_cycles": 308,
            "swiglu_xsim_max_group_interval": 1_213,
            "external_columns": 16,
            "local_repack": "3x16-to-4x12",
            "gate_up_legal_total_shift": [MLP_GATE_UP_TOTAL_SHIFT_MIN,
                                            MLP_TOTAL_SHIFT_MAX],
            "down_legal_total_shift": [MLP_DOWN_TOTAL_SHIFT_MIN,
                                         MLP_TOTAL_SHIFT_MAX],
            "raw_s33_abs_max": MLP_RAW_S33_ABS_MAX,
            "gate_up_group_guard_width": MLP_GATE_UP_GUARD_WIDTH,
            "down_group_guard_width": MLP_DOWN_GUARD_WIDTH,
            "gate_up_accumulator_width": MLP_GATE_UP_ACCUM_WIDTH,
            "down_accumulator_width": MLP_DOWN_ACCUM_WIDTH,
            "down_output_width": MLP_DOWN_OUTPUT_WIDTH,
            "down_output_fraction_bits": 16,
        },
        "weights": {
            "attention_matrix_bytes_per_layer":
                attention_matrix_bytes // layers,
            "mlp_matrix_bytes_per_layer": mlp_matrix_bytes // layers,
            "attention_matrix_bytes_32layer": attention_matrix_bytes,
            "mlp_matrix_bytes_32layer": mlp_matrix_bytes,
            "matrix_bytes_32layer": matrix_bytes,
            "visible_ddr_bytes": visible_ddr_bytes,
            "matrix_headroom_bytes": visible_ddr_bytes - matrix_bytes,
            "all_matrix_payload_resident": matrix_bytes <= visible_ddr_bytes,
            "metadata_policy": "current-layer local A/B; prefetch next layer",
            "external_ddr_format_changed": False,
        },
        "throughput": {
            "attention_stage": stage(
                attention_32_cycles,
                "historical Attention-only cycles scaled to cohort16"),
            "mlp_stage": stage(
                mlp_32_cycles,
                "V5 full-shape analytical schedule using divider2 BRAM-row-ring XSIM interval"),
            "serial_diagnostic": stage(
                serial_32_cycles, "analytical; not target dataflow"),
            "dual_cohort_pipeline": stage(
                pipeline_slot_cycles, "ideal model; not board measured"),
        },
        "ddr_roofline": {
            "aggregate_peak_gbps": 38.4,
            "useful_matrix_bytes_per_cohort": matrix_bytes,
            "targets": ddr_targets,
        },
        "host_turnaround_p95_ms": {
            "hard_60_tokens_per_second": 2.0,
            "engineering_65_tokens_per_second": 1.5,
            "stretch_70_tokens_per_second": 1.2,
        },
        "board_measured": False,
    }


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
