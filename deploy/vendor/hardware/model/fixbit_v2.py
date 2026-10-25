#!/usr/bin/env python3
"""Bit-exact integer helpers for HAP_ATTN_FIXBIT_V2."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Sequence


FORMAT_ID = 0x4838_4102
GROUP_SIZE = 32
INV_SQRT32_Q16 = 11_585
DENOM_SCALE_Q16 = 255 << 16
SCALE_EXACT_LIMIT = 4_261_478_400
S24_MIN = -(1 << 23)
S24_MAX = (1 << 23) - 1
S27_MIN = -(1 << 26)
S27_MAX = (1 << 26) - 1
S42_MIN = -(1 << 41)
S42_MAX = (1 << 41) - 1
KV_QMAX = 2047
KV_SCALE_DENOM_Q16 = KV_QMAX << 16
KV_SCALE_HALF_DENOM_Q16 = KV_SCALE_DENOM_Q16 // 2
KV_SCALE_SHIFT_MIN = 8
KV_SCALE_SHIFT_MAX = 32
HEAD_SCALE_Q16 = 5793


def require_signed(value: int, width: int, name: str = "value") -> int:
    minimum = -(1 << (width - 1))
    maximum = (1 << (width - 1)) - 1
    if not minimum <= value <= maximum:
        raise ValueError(f"{name}={value} does not fit S{width}")
    return value


def saturate_signed(value: int, width: int) -> tuple[int, bool]:
    minimum = -(1 << (width - 1))
    maximum = (1 << (width - 1)) - 1
    if value < minimum:
        return minimum, True
    if value > maximum:
        return maximum, True
    return value, False


def round_shift_away_zero(value: int, shift: int) -> int:
    """Round value / 2**shift to nearest, with exact halves away from zero."""
    if shift < 0:
        raise ValueError("shift must be non-negative")
    if shift == 0:
        return value
    half = 1 << (shift - 1)
    if value >= 0:
        return (value + half) >> shift
    return -(((-value) + half) >> shift)


def hadamard32_unscaled(values: Sequence[int]) -> list[int]:
    if len(values) != GROUP_SIZE:
        raise ValueError(f"Hadamard32 requires {GROUP_SIZE} values")
    work = [require_signed(int(value), 24, f"lane[{idx}]")
            for idx, value in enumerate(values)]
    distance = 1
    stage_width = 25
    while distance < GROUP_SIZE:
        next_work = work.copy()
        for base in range(0, GROUP_SIZE, distance * 2):
            for offset in range(distance):
                lhs = work[base + offset]
                rhs = work[base + offset + distance]
                next_work[base + offset] = require_signed(
                    lhs + rhs, stage_width, "hadamard sum")
                next_work[base + offset + distance] = require_signed(
                    lhs - rhs, stage_width, "hadamard difference")
        work = next_work
        distance *= 2
        stage_width += 1
    return work


@dataclass(frozen=True)
class HadamardResult:
    values: tuple[int, ...]
    saturation_count: int


def hadamard32_normalized(values: Sequence[int]) -> HadamardResult:
    unscaled = hadamard32_unscaled(values)
    output: list[int] = []
    saturation_count = 0
    for value in unscaled:
        product = require_signed(value, 29) * INV_SQRT32_Q16
        require_signed(product, 43, "Hadamard normalization product")
        rounded = round_shift_away_zero(product, 16)
        saturated, did_saturate = saturate_signed(rounded, 27)
        output.append(saturated)
        saturation_count += int(did_saturate)
    return HadamardResult(tuple(output), saturation_count)


@dataclass(frozen=True)
class A8QuantResult:
    values: tuple[int, ...]
    scale_code: int
    scale_shift: int
    zero_point: int
    clip_low: int
    clip_high: int

    @property
    def metadata(self) -> int:
        return (self.scale_shift << 16) | (self.scale_code << 8) | self.zero_point


def round_div_even(numerator: int, denominator: int) -> int:
    """Round a non-negative rational to nearest, with exact ties to even."""
    if numerator < 0 or denominator <= 0:
        raise ValueError("round_div_even requires numerator>=0 and denominator>0")
    quotient, remainder = divmod(numerator, denominator)
    doubled = remainder << 1
    if doubled > denominator or (doubled == denominator and quotient & 1):
        quotient += 1
    return quotient


def encode_scale_from_diff(diff_q16: int) -> tuple[int, int]:
    if diff_q16 <= 0:
        return 0, 0
    shifted = int(diff_q16)
    shift = 0
    while shift < 63 and (shifted << 1) <= SCALE_EXACT_LIMIT:
        shifted <<= 1
        shift += 1
    code = round_div_even(shifted, DENOM_SCALE_Q16)
    if code < 1:
        code = 1
    if code > 255:
        code = 255
    return code, shift


def encode_positive_scale(scale: float) -> tuple[int, int]:
    """Encode a positive real scale as ``code * 2**(-shift)``.

    This is the offline-weight counterpart of the native ScaleCode v2
    decoder.  Exact halves are rounded away from zero (positive values are
    therefore ordinary floor(x + 0.5)).
    """
    if not math.isfinite(float(scale)) or float(scale) < 0.0:
        raise ValueError("ScaleCode scale must be finite and non-negative")
    if float(scale) == 0.0:
        return 0, 0
    shift = int(math.floor(math.log2(255.0 / float(scale))))
    shift = max(0, min(63, shift))
    code = int(math.floor(math.ldexp(float(scale), shift) + 0.5))
    while code > 255 and shift > 0:
        shift -= 1
        code = int(math.floor(math.ldexp(float(scale), shift) + 0.5))
    if not 1 <= code <= 255:
        raise ValueError(
            f"scale={scale!r} is not representable by ScaleCode v2")
    return code, shift


def minmax_a8_quantize(values: Sequence[int]) -> A8QuantResult:
    """Raw Group32 asymmetric U8 Min/Max quantization after Hadamard."""
    if len(values) != GROUP_SIZE:
        raise ValueError(f"A8 group requires {GROUP_SIZE} values")
    source = [require_signed(int(value), 27, f"lane[{idx}]")
              for idx, value in enumerate(values)]

    low = min(min(source), 0)
    high = max(max(source), 0)
    diff = high - low
    if diff == 0:
        return A8QuantResult((0,) * GROUP_SIZE, 0, 0, 0,
                             low, high)

    code, shift = encode_scale_from_diff(diff)
    zero_point = min(255, round_div_even((-low) * 255, diff))
    output: list[int] = []
    for value in source:
        affine_numerator = value * 255 + zero_point * diff
        if affine_numerator <= 0:
            quantized = 0
        elif affine_numerator >= 255 * diff:
            quantized = 255
        else:
            quantized = round_div_even(affine_numerator, diff)
        output.append(quantized)
    return A8QuantResult(tuple(output), code, shift, zero_point,
                         low, high)


def robust_a8_quantize(values: Sequence[int]) -> A8QuantResult:
    """Compatibility alias for callers being migrated to Min/Max naming."""
    return minmax_a8_quantize(values)


def a8w8_group32_guard_s42(
        act_u8: Sequence[int],
        weight_s8: Sequence[int],
        zero_point: int,
        act_code: int,
        act_shift: int,
        weight_code: int,
        weight_shift: int,
) -> int:
    """FixBit v2 native group32 contribution in the S42 Q18.24 domain."""
    if len(act_u8) != GROUP_SIZE or len(weight_s8) != GROUP_SIZE:
        raise ValueError("native linear group must contain 32 lanes")
    if not 0 <= zero_point <= 255:
        raise ValueError("zero_point must fit U8")
    if act_code == 0 or weight_code == 0:
        if (act_code == 0 and act_shift != 0) or \
                (weight_code == 0 and weight_shift != 0):
            raise ValueError("zero native scale code requires shift=0")
        return 0
    if not 1 <= act_code <= 255 or not 1 <= weight_code <= 255:
        raise ValueError("nonzero native group requires scale code in [1,255]")
    total_shift = int(act_shift) + int(weight_shift)
    if not 26 <= total_shift <= 47:
        raise ValueError("native linear total shift must be in [26, 47]")

    correlation = 0
    for lane, (act, weight) in enumerate(zip(act_u8, weight_s8)):
        if not 0 <= int(act) <= 255:
            raise ValueError(f"act_u8[{lane}] does not fit U8")
        require_signed(int(weight), 8, f"weight_s8[{lane}]")
        product = (int(act) - zero_point) * int(weight)
        require_signed(product, 16, f"product[{lane}]")
        correlation += product
    require_signed(correlation, 21, "group32 correlation")
    raw = correlation * act_code * weight_code
    require_signed(raw, 37, "group32 ScaleCode raw product")
    guard = raw >> (total_shift - 24)
    return require_signed(guard, 42, "group32 S42 guard")


def round_sat_guard_s42_to_s24(value: int) -> tuple[int, bool]:
    require_signed(value, 42, "linear S42 guard")
    rounded = round_shift_away_zero(value, 8)
    return saturate_signed(rounded, 24)


def rope_pair_s24(
        x0_s24: int,
        x1_s24: int,
        cos_s18_q16: int,
        sin_s18_q16: int,
) -> tuple[int, int, int]:
    """FixBit v2 RoPE pair, returning y0/y1 and saturation count."""
    require_signed(x0_s24, 24, "rope x0")
    require_signed(x1_s24, 24, "rope x1")
    require_signed(cos_s18_q16, 18, "rope cos")
    require_signed(sin_s18_q16, 18, "rope sin")
    if abs(cos_s18_q16) > 65536 or abs(sin_s18_q16) > 65536:
        raise ValueError("RoPE coefficient magnitude exceeds 1.0")

    x0_cos = round_shift_away_zero(x0_s24 * cos_s18_q16, 16)
    x1_sin = round_shift_away_zero(x1_s24 * sin_s18_q16, 16)
    x0_sin = round_shift_away_zero(x0_s24 * sin_s18_q16, 16)
    x1_cos = round_shift_away_zero(x1_s24 * cos_s18_q16, 16)
    require_signed(x0_cos, 25, "rope rounded product")
    require_signed(x1_sin, 25, "rope rounded product")
    require_signed(x0_sin, 25, "rope rounded product")
    require_signed(x1_cos, 25, "rope rounded product")
    y0, sat0 = saturate_signed(x0_cos - x1_sin, 24)
    y1, sat1 = saturate_signed(x0_sin + x1_cos, 24)
    return y0, y1, int(sat0) + int(sat1)


@dataclass(frozen=True)
class KV12QuantResult:
    values: tuple[int, ...]
    scale_code: int
    scale_shift: int
    clip_count: int

    @property
    def metadata(self) -> int:
        return (self.scale_shift << 8) | self.scale_code


def kv12_quantize_s24(values: Sequence[int]) -> KV12QuantResult:
    """Symmetric group32 S24 Q8.16 to S12 plus ScaleCode v2 metadata."""
    if len(values) != GROUP_SIZE:
        raise ValueError(f"KV12 group requires {GROUP_SIZE} values")
    source = [require_signed(int(value), 24, f"lane[{idx}]")
              for idx, value in enumerate(values)]
    max_abs = max(abs(value) for value in source)
    if max_abs == 0:
        return KV12QuantResult((0,) * GROUP_SIZE, 0, 0, 0)

    # Select the largest legal exponent whose rounded code still fits U8.
    threshold = 256 * KV_SCALE_DENOM_Q16 - KV_SCALE_HALF_DENOM_Q16 - 1
    shift = KV_SCALE_SHIFT_MIN
    shifted = max_abs << shift
    while shift < KV_SCALE_SHIFT_MAX and (shifted << 1) <= threshold:
        shifted <<= 1
        shift += 1
    code = (shifted + KV_SCALE_HALF_DENOM_Q16) // KV_SCALE_DENOM_Q16
    if not 1 <= code <= 255:
        raise AssertionError((max_abs, code, shift))

    output: list[int] = []
    clip_count = 0
    for value in source:
        magnitude = (abs(value) * KV_QMAX + (max_abs // 2)) // max_abs
        if magnitude > KV_QMAX:
            magnitude = KV_QMAX
            clip_count += 1
        output.append(-magnitude if value < 0 else magnitude)
    return KV12QuantResult(tuple(output), code, shift, clip_count)


def q24k12_group_dot_s40(
        query_s24: Sequence[int], key_s12: Sequence[int]) -> int:
    """Direct Q24 x K12 group32 dot in the exact mathematical S40 domain."""
    if len(query_s24) != GROUP_SIZE or len(key_s12) != GROUP_SIZE:
        raise ValueError("QK group dot requires 32 query and key lanes")
    total = 0
    for lane, (query, key) in enumerate(zip(query_s24, key_s12)):
        require_signed(int(query), 24, f"query[{lane}]")
        require_signed(int(key), 12, f"key[{lane}]")
        if int(key) == -2048:
            raise ValueError(f"key[{lane}] uses reserved KV12 code")
        product = int(query) * int(key)
        require_signed(product, 35, f"qk product[{lane}]")
        total += product
    return require_signed(total, 40, "QK group32 dot")


def score_group_q14_s35(dot_s40: int, key_code: int, key_shift: int) -> int:
    """Scale one QK group dot into the score Q6.14 integer domain."""
    require_signed(dot_s40, 40, "QK group dot")
    if int(key_code) == 0:
        if int(key_shift) != 0:
            raise ValueError("zero Score group requires shift=0")
        return 0
    if not 1 <= int(key_code) <= 255:
        raise ValueError("nonzero Score group requires key code in [1,255]")
    if not KV_SCALE_SHIFT_MIN <= int(key_shift) <= KV_SCALE_SHIFT_MAX:
        raise ValueError("Score key shift must be in [8,32]")
    raw_s48 = dot_s40 * int(key_code)
    require_signed(raw_s48, 48, "QK dot times K code")
    scaled_s61 = raw_s48 * HEAD_SCALE_Q16
    require_signed(scaled_s61, 61, "QK head-scaled value")
    return require_signed(scaled_s61 >> (int(key_shift) + 18), 35,
                          "QK scaled group Q14")


def score_finalize_s20(group_q14: Sequence[int]) -> tuple[int, bool]:
    """Accumulate four score groups and clip the Q6.14 boundary to +/-16."""
    if len(group_q14) != 4:
        raise ValueError("Score finalizer requires exactly four head groups")
    total = 0
    for index, value in enumerate(group_q14):
        require_signed(int(value), 35, f"score group[{index}]")
        total += int(value)
    require_signed(total, 37, "four-group Score accumulator")
    clip_min = -(16 << 14)
    clip_max = 16 << 14
    clipped = min(clip_max, max(clip_min, total))
    return require_signed(clipped, 20, "Score S20 Q6.14"), clipped != total


def build_softmax_exp_lut_u17() -> tuple[int, ...]:
    """257 Q16 samples of exp(-x) for x=0..16 at a 1/16 interval."""
    return tuple(int(math.floor(math.exp(-index / 16.0) * 65536.0 + 0.5))
                 for index in range(257))


def softmax_exp_delta_q14_u17(
        delta_q14: int,
        lut: Sequence[int] | None = None,
) -> int:
    """Versioned linear-interpolation exp for a Q14 delta in [-16,0]."""
    if not -(16 << 14) <= int(delta_q14) <= 0:
        raise ValueError("softmax delta Q14 must be in [-16,0]")
    table = build_softmax_exp_lut_u17() if lut is None else tuple(lut)
    if len(table) != 257 or table[0] != 65536:
        raise ValueError("invalid softmax exp LUT")
    magnitude = -int(delta_q14)
    index = magnitude >> 10
    fraction = magnitude & 0x3FF
    if index == 256:
        return int(table[256])
    high = int(table[index])
    low = int(table[index + 1])
    interpolation = ((high - low) * fraction + 512) >> 10
    return high - interpolation


def softmax_reciprocal_u17(row_sum_u24: int) -> int:
    # A valid row always contains its unmasked maximum, whose exp is exactly
    # 65536, so sums below 1.0 indicate a control/artifact error.
    if not 65536 <= int(row_sum_u24) <= (1 << 23):
        raise ValueError("softmax row sum must be in [65536,2^23]")
    reciprocal = ((1 << 32) + (int(row_sum_u24) // 2)) // int(row_sum_u24)
    return reciprocal


def softmax_probability_u16(exp_u17: int, reciprocal_u17: int) -> int:
    if not 0 <= int(exp_u17) <= 65536:
        raise ValueError("softmax exp must fit constrained U17")
    if not 0 <= int(reciprocal_u17) <= 65536:
        raise ValueError("softmax reciprocal must fit constrained U17")
    product = int(exp_u17) * int(reciprocal_u17)
    rounded = (product + 32768) >> 16
    return min(65535, rounded)


def softmax_row_u16(
        scores_q14_s20: Sequence[int],
        masks: Sequence[bool | int],
) -> tuple[tuple[int, ...], tuple[int, ...], int, int]:
    """Bit-exact 128-key Softmax row.

    Returns probabilities, exponent values, U24 row sum and U17 reciprocal.
    Masked elements are exactly zero and at least one element must be unmasked.
    """
    if len(scores_q14_s20) != 128 or len(masks) != 128:
        raise ValueError("Softmax row requires exactly 128 scores and masks")
    scores = [require_signed(int(value), 20, f"score[{index}]")
              for index, value in enumerate(scores_q14_s20)]
    mask_bits = [bool(value) for value in masks]
    unmasked = [score for score, mask in zip(scores, mask_bits) if not mask]
    if not unmasked:
        raise ValueError("Softmax row must contain an unmasked element")
    row_max = max(unmasked)
    exponents: list[int] = []
    for score, mask in zip(scores, mask_bits):
        if mask:
            exponents.append(0)
        else:
            delta = min(0, max(-(16 << 14), score - row_max))
            exponents.append(softmax_exp_delta_q14_u17(delta))
    row_sum = sum(exponents)
    if not 65536 <= row_sum <= (1 << 23):
        raise AssertionError(f"invalid Softmax row sum {row_sum}")
    reciprocal = softmax_reciprocal_u17(row_sum)
    probabilities = tuple(
        softmax_probability_u16(exp_value, reciprocal)
        for exp_value in exponents)
    return probabilities, tuple(exponents), row_sum, reciprocal


def pv_row_tile16_s24(
        probabilities_u16: Sequence[int],
        values_s12: Sequence[Sequence[int]],
        scale_codes_u8: Sequence[int],
        scale_shifts_u6: Sequence[int],
) -> tuple[tuple[int, ...], int]:
    """Accumulate one 128-key by 16-dimension PV tile through S43 Q19.24."""
    if not (len(probabilities_u16) == len(values_s12) ==
            len(scale_codes_u8) == len(scale_shifts_u6) == 128):
        raise ValueError("PV row tile requires exactly 128 keys")
    accumulators = [0] * 16
    for key in range(128):
        probability = int(probabilities_u16[key])
        if not 0 <= probability <= 65535:
            raise ValueError(f"probability[{key}] does not fit U16")
        if len(values_s12[key]) != 16:
            raise ValueError(f"values[{key}] does not contain 16 lanes")
        code = int(scale_codes_u8[key])
        shift = int(scale_shifts_u6[key])
        if code == 0:
            if shift != 0 or any(int(value) != 0 for value in values_s12[key]):
                raise ValueError("zero PV ScaleCode requires shift=0 and zero values")
            continue
        if not 1 <= code <= 255 or not 8 <= shift <= 32:
            raise ValueError("nonzero PV ScaleCode requires shift in [8,32]")
        for lane, value_raw in enumerate(values_s12[key]):
            value = require_signed(int(value_raw), 12, f"V[{key},{lane}]")
            if value == -2048:
                raise ValueError("reserved KV12 value -2048 is not permitted")
            value_code_s20 = value * code
            require_signed(value_code_s20, 20, "PV V*code S20")
            term_raw_s36 = value_code_s20 * probability
            require_signed(term_raw_s36, 36, "PV raw S36")
            term_guard_s36 = term_raw_s36 >> (shift - 8)
            accumulators[lane] += term_guard_s36
            require_signed(accumulators[lane], 43, "PV accumulator S43")
    output: list[int] = []
    saturation_count = 0
    for accumulator in accumulators:
        rounded = round_shift_away_zero(accumulator, 8)
        saturated, did_saturate = saturate_signed(rounded, 24)
        output.append(saturated)
        saturation_count += int(did_saturate)
    return tuple(output), saturation_count


def qk_score_row_s20(
        query_groups_s24: Sequence[Sequence[int]],
        key_groups_s12: Sequence[Sequence[Sequence[int]]],
        key_codes_u8: Sequence[Sequence[int]],
        key_shifts_u6: Sequence[Sequence[int]],
        masks: Sequence[bool | int],
) -> tuple[tuple[int, ...], tuple[bool, ...]]:
    """Compute one 128-key QK score row from four group32 records."""
    if len(query_groups_s24) != 4 or any(
            len(group) != 32 for group in query_groups_s24):
        raise ValueError("QK row query must contain four group32 records")
    if not (len(key_groups_s12) == len(key_codes_u8) ==
            len(key_shifts_u6) == len(masks) == 128):
        raise ValueError("QK score row requires exactly 128 keys")
    scores: list[int] = []
    clips: list[bool] = []
    for key_index in range(128):
        if not (len(key_groups_s12[key_index]) ==
                len(key_codes_u8[key_index]) ==
                len(key_shifts_u6[key_index]) == 4):
            raise ValueError("each QK key must contain four groups")
        scaled_groups: list[int] = []
        for group_index in range(4):
            code = int(key_codes_u8[key_index][group_index])
            shift = int(key_shifts_u6[key_index][group_index])
            key_group = key_groups_s12[key_index][group_index]
            if code == 0:
                if shift != 0 or any(int(value) != 0 for value in key_group):
                    raise ValueError("zero QK scale requires shift=0 and zero key group")
                scaled_groups.append(0)
            else:
                dot = q24k12_group_dot_s40(
                    query_groups_s24[group_index], key_group)
                scaled_groups.append(score_group_q14_s35(dot, code, shift))
        score, clipped = score_finalize_s20(scaled_groups)
        scores.append(score)
        clips.append(clipped)
    return tuple(scores), tuple(clips)


def pack_lanes(values: Iterable[int], width: int) -> int:
    packed = 0
    mask = (1 << width) - 1
    for lane, value in enumerate(values):
        require_signed(int(value), width, f"lane[{lane}]")
        packed |= (int(value) & mask) << (lane * width)
    return packed


def unpack_lanes(packed: int, width: int, count: int) -> list[int]:
    mask = (1 << width) - 1
    sign = 1 << (width - 1)
    values = []
    for lane in range(count):
        raw = (packed >> (lane * width)) & mask
        values.append(raw - (1 << width) if raw & sign else raw)
    return values


def self_test() -> None:
    rounding_cases = {
        (0, 4): 0,
        (7, 4): 0,
        (8, 4): 1,
        (23, 4): 1,
        (24, 4): 2,
        (-7, 4): 0,
        (-8, 4): -1,
        (-23, 4): -1,
        (-24, 4): -2,
    }
    for (value, shift), expected in rounding_cases.items():
        actual = round_shift_away_zero(value, shift)
        if actual != expected:
            raise AssertionError((value, shift, expected, actual))

    for scale, expected in ((0.0, (0, 0)), (0.5, (128, 8)),
                            (1.0 / 256.0, (128, 15))):
        actual = encode_positive_scale(scale)
        if actual != expected:
            raise AssertionError((scale, expected, actual))

    impulse = [0] * GROUP_SIZE
    impulse[0] = 1 << 16
    result = hadamard32_normalized(impulse)
    if result.values != (INV_SQRT32_Q16,) * GROUP_SIZE:
        raise AssertionError("Hadamard impulse response mismatch")
    if result.saturation_count != 0:
        raise AssertionError("unexpected impulse saturation")

    alternating = [S24_MAX if lane & 1 else S24_MIN
                   for lane in range(GROUP_SIZE)]
    result = hadamard32_normalized(alternating)
    if result.saturation_count != 0:
        raise AssertionError("valid S24 Hadamard input unexpectedly saturated")

    zero_quant = minmax_a8_quantize([0] * GROUP_SIZE)
    if zero_quant.values != (0,) * GROUP_SIZE or zero_quant.metadata != 0:
        raise AssertionError("degenerate A8 group mismatch")

    ramp = [(lane - 16) << 16 for lane in range(GROUP_SIZE)]
    ramp_quant = minmax_a8_quantize(ramp)
    if not (1 <= ramp_quant.scale_code <= 255 and
            0 <= ramp_quant.scale_shift <= 63 and
            0 <= ramp_quant.zero_point <= 255):
        raise AssertionError("ramp A8 metadata out of range")

    guard = a8w8_group32_guard_s42(
        list(range(32)), [1] * 32, 16, 128, 16, 128, 16)
    if guard != sum(value - 16 for value in range(32)) * 64:
        raise AssertionError("native group32 S42 helper mismatch")

    zero_kv = kv12_quantize_s24([0] * GROUP_SIZE)
    if zero_kv.values != (0,) * GROUP_SIZE or zero_kv.metadata != 0:
        raise AssertionError("zero KV12 group mismatch")
    edge_kv = kv12_quantize_s24([S24_MIN, S24_MAX] + [0] * 30)
    if edge_kv.values[0] != -2047 or edge_kv.values[1] != 2047:
        raise AssertionError("KV12 symmetric extrema mismatch")
    if any(value == -2048 for value in edge_kv.values):
        raise AssertionError("KV12 reserved value was generated")

    qk_dot = q24k12_group_dot_s40(
        [S24_MIN, S24_MAX] + [0] * 30,
        [-2047, 2047] + [0] * 30)
    if qk_dot != S24_MIN * -2047 + S24_MAX * 2047:
        raise AssertionError("Q24xK12 group dot mismatch")


if __name__ == "__main__":
    self_test()
    print("PASS: FixBit v2 integer helper self-test completed.")
