#!/usr/bin/env python3
"""Independent Group32 Min/Max A8 reference for ModularExperiment.

This module deliberately does not import the production RTL golden.  The
experiment contract is the final ScaleCode model contract:

* raw post-Hadamard group minimum/maximum, with zero included in the range;
* unsigned asymmetric A8;
* round-to-nearest, ties-to-even for zero-point, lanes, and ScaleCode;
* ideal Min/Max scale for zero-point and lane U8 generation;
* decoded ScaleCode only for downstream reconstruction.

Inputs are signed fixed-point integers with sixteen fractional bits.  S27 and
S35 use identical arithmetic; the width check is the only difference.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


GROUP_SIZE = 32
QMAX = 255
FRACTION_BITS = 16
SCALE_DENOM_Q16 = QMAX << FRACTION_BITS
SCALE_EXACT_LIMIT_Q16 = QMAX * SCALE_DENOM_Q16
# Largest positive diff whose unshifted ideal scale rounds to code <= 255.
SCALE_ROUND_LIMIT_Q16 = (QMAX * SCALE_DENOM_Q16) + \
    (SCALE_DENOM_Q16 // 2) - 1


@dataclass(frozen=True)
class MinMaxA8Result:
    values: tuple[int, ...]
    scale_code: int
    scale_shift: int
    zero_point: int
    low: int
    high: int
    scale_format_overflow: bool = False

    @property
    def metadata(self) -> int:
        return ((self.scale_shift & 0x3F) << 16) | \
            ((self.scale_code & 0xFF) << 8) | (self.zero_point & 0xFF)

    # Transitional aliases keep old trace-analysis code readable while its
    # counters are migrated from clipping to pre-quantization clipping = 0.
    @property
    def clip_low(self) -> int:
        return self.low

    @property
    def clip_high(self) -> int:
        return self.high


def require_signed(value: int, width: int, label: str = "value") -> int:
    minimum = -(1 << (width - 1))
    maximum = (1 << (width - 1)) - 1
    if not minimum <= value <= maximum:
        raise ValueError(
            f"{label}={value} does not fit signed S{width} "
            f"[{minimum}, {maximum}]")
    return value


def round_div_even(numerator: int, denominator: int) -> int:
    """Round a non-negative rational to nearest integer, ties to even."""
    if numerator < 0:
        raise ValueError("round_div_even requires a non-negative numerator")
    if denominator <= 0:
        raise ValueError("round_div_even requires a positive denominator")
    quotient, remainder = divmod(numerator, denominator)
    doubled = remainder << 1
    if doubled > denominator or (doubled == denominator and quotient & 1):
        quotient += 1
    return quotient


def round_signed_ratio_even(numerator: int, denominator: int) -> int:
    if numerator < 0:
        return -round_div_even(-numerator, denominator)
    return round_div_even(numerator, denominator)


def encode_scale_from_diff(diff_q16: int) -> tuple[int, int, bool]:
    """Encode ideal ``diff/255`` scale as U8 code plus unsigned shift6.

    The shift selection mirrors ``floor(log2(255 / scale))`` without floating
    point.  The overflow flag exposes the existing metadata range limitation;
    code saturation is retained only so diagnostics can still carry a record.
    """
    if diff_q16 <= 0:
        return 0, 0, False
    shifted = int(diff_q16)
    shift = 0
    while shift < 63 and (shifted << 1) <= SCALE_EXACT_LIMIT_Q16:
        shifted <<= 1
        shift += 1
    code = round_div_even(shifted, SCALE_DENOM_Q16)
    code = max(1, min(QMAX, code))
    return code, shift, diff_q16 > SCALE_ROUND_LIMIT_Q16


def quantize_group(
        values: Sequence[int] | Iterable[int], *, input_width: int,
) -> MinMaxA8Result:
    source = [
        require_signed(int(value), input_width, f"lane[{index}]")
        for index, value in enumerate(values)
    ]
    if len(source) != GROUP_SIZE:
        raise ValueError(f"A8 group requires {GROUP_SIZE} values")

    low = min(min(source), 0)
    high = max(max(source), 0)
    diff = high - low
    if diff == 0:
        return MinMaxA8Result((0,) * GROUP_SIZE, 0, 0, 0, 0, 0)

    zero_point = max(
        0, min(QMAX, round_div_even((-low) * QMAX, diff)))
    output: list[int] = []
    for value in source:
        # Round the complete affine expression.  With ties-to-even,
        # round(value*QMAX/diff) + zero_point is not equivalent when the
        # zero-point is odd and the quotient is exactly half-integral.
        affine_numerator = value * QMAX + zero_point * diff
        if affine_numerator <= 0:
            quantized = 0
        elif affine_numerator >= QMAX * diff:
            quantized = QMAX
        else:
            quantized = round_div_even(affine_numerator, diff)
        output.append(quantized)

    code, shift, overflow = encode_scale_from_diff(diff)
    return MinMaxA8Result(
        tuple(output), code, shift, zero_point, low, high, overflow)


def quantize_s27(values: Sequence[int] | Iterable[int]) -> MinMaxA8Result:
    return quantize_group(values, input_width=27)


def quantize_s35(values: Sequence[int] | Iterable[int]) -> MinMaxA8Result:
    return quantize_group(values, input_width=35)


def native_fp_a8(
        values: Sequence[int] | Iterable[int], *, input_width: int,
) -> tuple[list[int], int, int, int, int]:
    """Return common ideal-scale U8, zp, scale-Q24, raw low and raw high."""
    result = quantize_group(values, input_width=input_width)
    diff = result.high - result.low
    if diff == 0:
        return list(result.values), 0, 0, result.low, result.high
    # diff is Q16; multiplying by 2**8 before /255 produces Q24.  Because
    # 255 is odd, an exact half tie cannot occur, but use the common helper.
    scale_q24 = round_div_even(diff << 8, QMAX)
    return (list(result.values), result.zero_point, scale_q24,
            result.low, result.high)


def native_fp_a8_s27(
        values: Sequence[int] | Iterable[int],
) -> tuple[list[int], int, int, int, int]:
    return native_fp_a8(values, input_width=27)


def native_fp_a8_s35(
        values: Sequence[int] | Iterable[int],
) -> tuple[list[int], int, int, int, int]:
    return native_fp_a8(values, input_width=35)
