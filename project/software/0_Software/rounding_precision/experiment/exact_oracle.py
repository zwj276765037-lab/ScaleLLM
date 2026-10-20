"""Independent arbitrary-precision reference for fixed-code Linear recovery.

No production arithmetic or floating-point computation is used here.  The common
binary denominator is retained even when the rational could be reduced.
"""
from __future__ import annotations

from fractions import Fraction
from typing import Iterable, Mapping


def round_rational_away(numerator: int, denominator: int) -> int:
    """Nearest integer, with exact ties away from zero."""
    if type(numerator) is not int or type(denominator) is not int:
        raise TypeError("rational components must be Python integers")
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    quotient, remainder = divmod(abs(numerator), denominator)
    rounded = quotient + int(2 * remainder >= denominator)
    return -rounded if numerator < 0 else rounded


def common_binary_sum(groups: Iterable[Mapping[str, int]]) -> tuple[int, int]:
    """Return numerator and denominator exponent for sum(dot*codes*2**-shift)."""
    terms = [
        (group["dot"] * group["act_code"] * group["weight_code"],
         group["act_shift"] + group["weight_shift"])
        for group in groups
    ]
    exponent = max([0, *(shift for _, shift in terms)])
    numerator = sum(product * (1 << (exponent - shift))
                    for product, shift in terms)
    return numerator, exponent


def encode_fraction(value: Fraction) -> dict[str, str]:
    return {"numerator": str(value.numerator), "denominator": str(value.denominator)}


def decode_fraction(value: Mapping[str, int]) -> Fraction:
    return Fraction(int(value["numerator"]), int(value["denominator"]))


def evaluate_exact(sample: Mapping, output_width: int) -> dict:
    """Evaluate the exact sum and its only final F16 half-away quantization.

    The caller validates input syntax.  Width is explicit so this independent
    reference does not obtain a format specification from the production model.
    """
    numerator, exponent = common_binary_sum(sample["groups"])
    denominator = 1 << exponent
    rounded = round_rational_away(numerator * (1 << 16), denominator)
    low, high = -(1 << (output_width - 1)), (1 << (output_width - 1)) - 1
    output = min(high, max(low, rounded))
    reduced = Fraction(numerator, denominator)
    return {
        "exact": {
            "numerator": str(reduced.numerator),
            "denominator": str(reduced.denominator),
            "denominator_bits": reduced.denominator.bit_length() - 1,
            "common_numerator": str(numerator),
            "common_denominator_bits": exponent,
            "arithmetic": "arbitrary_precision_integer_common_binary_denominator",
        },
        "output_only": {
            "label": "仅输出舍入",
            "output_code": output,
            "pre_saturation_code": rounded,
            "saturated": output != rounded,
            "fractional_bits": 16,
        },
    }
