#!/usr/bin/env python3
"""Numerical core for the fixed-Q activation Hadamard experiment.

The integer path mirrors these production contracts:

* host/scalellm_hostops.py::pack_s24_q16
* rtl/attention/hap_hadamard32_norm_stream.sv
* model/fixbit_v2.py::minmax_a8_quantize
* model/mlp_fixed.py::hadamard32_product_normalized (S32/S35 down_proj)

Only NumPy is required so the proof-oriented experiment can run without a
model or CUDA installation.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np


GROUP_SIZE = 32
FRACTION_BITS = 16
Q_SCALE = 1 << FRACTION_BITS
Q_STEP = 1.0 / Q_SCALE
S24_MIN = -(1 << 23)
S24_MAX = (1 << 23) - 1
S27_MIN = -(1 << 26)
S27_MAX = (1 << 26) - 1
S32_MIN = -(1 << 31)
S32_MAX = (1 << 31) - 1
S35_MIN = -(1 << 34)
S35_MAX = (1 << 34) - 1
INV_SQRT32_Q16 = 11_585
SCALE_EXACT_LIMIT = 4_261_478_400
DENOM_SCALE_Q16 = 255 << 16


@dataclass(frozen=True)
class A8Result:
    q: np.ndarray
    scale_code: np.ndarray
    scale_shift: np.ndarray
    zero_point: np.ndarray
    dq: np.ndarray


def _groups(values: np.ndarray, *, dtype: np.dtype[Any] | None = None) -> np.ndarray:
    array = np.asarray(values, dtype=dtype)
    if array.ndim == 1:
        array = array.reshape(1, -1)
    if array.ndim != 2 or array.shape[1] != GROUP_SIZE:
        raise ValueError(f"expected [groups,{GROUP_SIZE}], got {array.shape}")
    return array


def round_half_away_float(values: np.ndarray) -> np.ndarray:
    """Round finite floats to int64, with exact halves away from zero."""
    array = np.asarray(values, dtype=np.float64)
    if not np.all(np.isfinite(array)):
        raise ValueError("input contains NaN or infinity")
    magnitude = np.floor(np.abs(array) + 0.5)
    return np.copysign(magnitude, array).astype(np.int64)


def round_shift_away_zero(values: np.ndarray, shift: int) -> np.ndarray:
    """Integer round(values / 2**shift), exact halves away from zero."""
    if shift < 0:
        raise ValueError("shift must be non-negative")
    array = np.asarray(values, dtype=np.int64)
    if shift == 0:
        return array.copy()
    half = np.int64(1 << (shift - 1))
    return np.where(array >= 0, (array + half) >> shift,
                    -(((-array) + half) >> shift))


def _signed_limits(width: int) -> tuple[int, int]:
    if width < 2 or width > 62:
        raise ValueError(f"unsupported signed width S{width}")
    return -(1 << (width - 1)), (1 << (width - 1)) - 1


def fp_to_q16(values: np.ndarray, width: int) -> tuple[np.ndarray, np.ndarray]:
    """Return signed Q*.16 raw integers and an element-wise saturation mask."""
    source = _groups(values, dtype=np.float64)
    rounded = round_half_away_float(source * Q_SCALE)
    low, high = _signed_limits(width)
    clipped = np.clip(rounded, low, high)
    return clipped.astype(np.int64), clipped != rounded


def fp_to_s24_q16(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return S24 Q8.16 raw integers and an element-wise saturation mask."""
    return fp_to_q16(values, 24)


def fp_to_s32_q16(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return S32 Q16.16 raw integers and an element-wise saturation mask."""
    return fp_to_q16(values, 32)


def fwht(values: np.ndarray) -> np.ndarray:
    """Unnormalised row-wise Sylvester Walsh-Hadamard transform."""
    source = _groups(values)
    work = source.copy()
    distance = 1
    while distance < GROUP_SIZE:
        shaped = work.reshape(-1, GROUP_SIZE // (2 * distance), 2, distance)
        lhs = shaped[:, :, 0, :].copy()
        rhs = shaped[:, :, 1, :].copy()
        shaped[:, :, 0, :] = lhs + rhs
        shaped[:, :, 1, :] = lhs - rhs
        distance *= 2
    return work


def software_hadamard(values: np.ndarray) -> np.ndarray:
    """Float64 reference H32/sqrt(32), matching local_h_right mathematically."""
    return fwht(_groups(values, dtype=np.float64)) / math.sqrt(GROUP_SIZE)


def hardware_hadamard_q16(
    raw_q16: np.ndarray, *, input_width: int, output_width: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Bit-exact signed Q*.16 -> fixed Hadamard -> signed Q*.16."""
    source = _groups(raw_q16, dtype=np.int64)
    input_low, input_high = _signed_limits(input_width)
    if np.any(source < input_low) or np.any(source > input_high):
        raise ValueError(f"raw input is outside S{input_width}")
    unscaled = fwht(source)
    rounded = round_shift_away_zero(unscaled * INV_SQRT32_Q16, FRACTION_BITS)
    output_low, output_high = _signed_limits(output_width)
    clipped = np.clip(rounded, output_low, output_high).astype(np.int64)
    return clipped, clipped != rounded


def hardware_hadamard_s24(raw_s24: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Bit-exact S24 Q8.16 -> fixed Hadamard -> S27 Q11.16."""
    return hardware_hadamard_q16(
        raw_s24, input_width=24, output_width=27)


def hardware_hadamard_s32(raw_s32: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Bit-exact S32 Q16.16 -> fixed Hadamard -> S35 Q19.16."""
    return hardware_hadamard_q16(
        raw_s32, input_width=32, output_width=35)


def _round_div_even(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    """Vectorised round-to-nearest-even for non-negative integer ratios."""
    numer = np.asarray(numerator, dtype=np.int64)
    denom = np.asarray(denominator, dtype=np.int64)
    if np.any(numer < 0) or np.any(denom <= 0):
        raise ValueError("round_div_even needs numerator >= 0 and denominator > 0")
    quotient = numer // denom
    remainder = numer % denom
    doubled = remainder * 2
    increment = (doubled > denom) | ((doubled == denom) & ((quotient & 1) != 0))
    return quotient + increment.astype(np.int64)


def _encode_scale_float(scale: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    safe = np.maximum(np.asarray(scale, dtype=np.float64), 1e-30)
    shift = np.floor(np.log2(255.0 / safe)).clip(0, 255).astype(np.int64)
    code = np.rint(np.ldexp(safe, shift)).clip(0, 255).astype(np.int64)
    return code, shift


def _encode_scale_from_diff(diff_q16: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Bit-exact production ScaleCode encoding from a non-negative Q16 diff."""
    diff = np.asarray(diff_q16, dtype=np.int64)
    code = np.zeros(diff.shape, dtype=np.int64)
    shift = np.zeros(diff.shape, dtype=np.int64)
    active = diff > 0
    shifted = diff.copy()
    while np.any(active & ((shifted << 1) <= SCALE_EXACT_LIMIT)):
        advance = active & ((shifted << 1) <= SCALE_EXACT_LIMIT)
        shifted[advance] <<= 1
        shift[advance] += 1
    if np.any(active):
        denominator = np.full(np.count_nonzero(active), DENOM_SCALE_Q16,
                              dtype=np.int64)
        encoded = _round_div_even(shifted[active], denominator)
        code[active] = np.clip(encoded, 1, 255)
    return code, shift


def software_a8_qdq(values: np.ndarray) -> A8Result:
    """Archived software float A8 + ScaleCode QDQ reference."""
    source = _groups(values, dtype=np.float64)
    low = np.minimum(source.min(axis=1), 0.0)
    high = np.maximum(source.max(axis=1), 0.0)
    scale = np.maximum((high - low) / 255.0, 1e-12)
    zero_point = np.rint(-low / scale).clip(0, 255).astype(np.int64)
    q = np.rint(source / scale[:, None] + zero_point[:, None])
    q = q.clip(0, 255).astype(np.int64)
    code, shift = _encode_scale_float(scale)
    decoded = np.ldexp(code.astype(np.float64), -shift)
    dq = (q - zero_point[:, None]) * decoded[:, None]
    return A8Result(q, code, shift, zero_point, dq)


def hardware_a8_qdq(raw_q16: np.ndarray) -> A8Result:
    """Bit-exact production MinMax A8 and real-valued ScaleCode decode."""
    source = _groups(raw_q16, dtype=np.int64)
    low = np.minimum(source.min(axis=1), 0)
    high = np.maximum(source.max(axis=1), 0)
    diff = high - low
    active = diff > 0

    code, shift = _encode_scale_from_diff(diff)
    zero_point = np.zeros(diff.shape, dtype=np.int64)
    if np.any(active):
        zero_point[active] = np.minimum(
            255,
            _round_div_even((-low[active]) * 255, diff[active]),
        )

    numerator = source * 255 + zero_point[:, None] * diff[:, None]
    q = np.zeros(source.shape, dtype=np.int64)
    if np.any(active):
        numer_active = numerator[active]
        diff_active = diff[active, None]
        interior = (numer_active > 0) & (numer_active < 255 * diff_active)
        q_active = np.where(numer_active >= 255 * diff_active, 255, 0)
        if np.any(interior):
            denom = np.broadcast_to(diff_active, numer_active.shape)
            q_active[interior] = _round_div_even(
                numer_active[interior], denom[interior])
        q[active] = q_active

    decoded = np.ldexp(code.astype(np.float64), -shift)
    dq = (q - zero_point[:, None]) * decoded[:, None]
    return A8Result(q, code, shift, zero_point, dq)


def _rmse(error: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(error, dtype=np.float64))))


def _cosine(lhs: np.ndarray, rhs: np.ndarray) -> float:
    left = np.asarray(lhs, dtype=np.float64).reshape(-1)
    right = np.asarray(rhs, dtype=np.float64).reshape(-1)
    denom = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denom == 0.0:
        return 1.0 if np.array_equal(left, right) else 0.0
    return float(np.dot(left, right) / denom)


def _sqnr_db(signal: np.ndarray, error: np.ndarray) -> float | None:
    signal_power = float(np.mean(np.square(signal, dtype=np.float64)))
    noise_power = float(np.mean(np.square(error, dtype=np.float64)))
    if noise_power == 0.0:
        return None
    if signal_power == 0.0:
        return -math.inf
    return float(10.0 * math.log10(signal_power / noise_power))


def _row_widths(
    widths: int | np.ndarray, groups: int, *, allowed: tuple[int, ...], name: str,
) -> np.ndarray:
    values = np.asarray(widths, dtype=np.int64)
    if values.ndim == 0:
        values = np.full(groups, int(values), dtype=np.int64)
    else:
        values = values.reshape(-1)
        if values.size != groups:
            raise ValueError(
                f"{name} has {values.size} rows but activations has {groups}")
    if not np.all(np.isin(values, allowed)):
        found = sorted(np.unique(values).tolist())
        raise ValueError(f"{name} must use {allowed}, got {found}")
    return values


def _format_name(input_width: int, output_width: int) -> str:
    integer_input = input_width - FRACTION_BITS
    integer_output = output_width - FRACTION_BITS
    return (
        f"S{input_width} Q{integer_input}.{FRACTION_BITS} -> "
        f"S{output_width} Q{integer_output}.{FRACTION_BITS}"
    )


def compare_groups(
    values: np.ndarray, *, input_width: int | np.ndarray = 24,
    output_width: int | np.ndarray | None = None,
) -> dict[str, Any]:
    """Compare software and production activation frontends for Group32 rows.

    ``input_width``/``output_width`` may be scalars or one value per group.  The
    latter supports a captured trace containing both the regular S24/S27 path
    and the wider MLP ``down_proj`` S32/S35 path in one aggregate row.
    """
    source = _groups(values, dtype=np.float64)
    input_widths = _row_widths(
        input_width, source.shape[0], allowed=(24, 32), name="input_width")
    if output_width is None:
        output_widths = input_widths + 3
    else:
        output_widths = _row_widths(
            output_width, source.shape[0], allowed=(27, 35), name="output_width")
    valid_pairs = ((input_widths == 24) & (output_widths == 27)) | (
        (input_widths == 32) & (output_widths == 35))
    if not np.all(valid_pairs):
        pairs = sorted(set(zip(
            input_widths.tolist(), output_widths.tolist(), strict=True)))
        raise ValueError(f"unsupported input/output format pairs: {pairs}")

    raw_input = np.empty(source.shape, dtype=np.int64)
    input_saturation = np.empty(source.shape, dtype=bool)
    raw_hardware_h = np.empty(source.shape, dtype=np.int64)
    h_saturation = np.empty(source.shape, dtype=bool)
    for current_input, current_output in ((24, 27), (32, 35)):
        selected = (input_widths == current_input) & (
            output_widths == current_output)
        if not np.any(selected):
            continue
        raw_input[selected], input_saturation[selected] = fp_to_q16(
            source[selected], current_input)
        raw_hardware_h[selected], h_saturation[selected] = hardware_hadamard_q16(
            raw_input[selected], input_width=current_input,
            output_width=current_output)
    fixed_input = raw_input.astype(np.float64) / Q_SCALE

    reference_h = software_hadamard(source)
    preq_ideal_h = software_hadamard(fixed_input)
    hardware_h = raw_hardware_h.astype(np.float64) / Q_SCALE

    software_a8 = software_a8_qdq(reference_h)
    hardware_a8 = hardware_a8_qdq(raw_hardware_h)

    input_error = fixed_input - source
    preq_h_error = preq_ideal_h - reference_h
    hardware_h_error = hardware_h - reference_h
    software_a8_error = software_a8.dq - reference_h
    hardware_a8_error = hardware_a8.dq - reference_h
    frontend_delta = hardware_a8.dq - software_a8.dq

    input_l2 = np.linalg.norm(input_error, axis=1)
    preq_h_l2 = np.linalg.norm(preq_h_error, axis=1)
    hardware_h_l2 = np.linalg.norm(hardware_h_error, axis=1)
    fixed_l2 = np.linalg.norm(fixed_input, axis=1)
    coefficient_relative_error = abs(
        math.sqrt(GROUP_SIZE) * INV_SQRT32_Q16 / Q_SCALE - 1.0)
    theorem_bound = (
        input_l2
        + coefficient_relative_error * fixed_l2
        + math.sqrt(GROUP_SIZE) * Q_STEP / 2.0
    )
    valid_theorem_group = ~input_saturation.any(axis=1)
    tolerance = 1e-12
    theorem_violation = valid_theorem_group & (
        hardware_h_l2 > theorem_bound + tolerance)
    energy_identity_error = np.abs(preq_h_l2 - input_l2)

    software_mse = float(np.mean(np.square(software_a8_error)))
    hardware_mse = float(np.mean(np.square(hardware_a8_error)))
    software_rmse = math.sqrt(software_mse)
    hardware_rmse = math.sqrt(hardware_mse)
    metadata_match = (
        (software_a8.scale_code == hardware_a8.scale_code)
        & (software_a8.scale_shift == hardware_a8.scale_shift)
        & (software_a8.zero_point == hardware_a8.zero_point)
    )
    per_group_frontend_rmse = np.sqrt(np.mean(np.square(frontend_delta), axis=1))
    per_group_hardware_rmse = np.sqrt(np.mean(np.square(hardware_a8_error), axis=1))

    active_formats = sorted({
        _format_name(current_input, current_output)
        for current_input, current_output in zip(
            input_widths.tolist(), output_widths.tolist(), strict=True)
    })
    format_profile = active_formats[0] if len(active_formats) == 1 else (
        "mixed: " + "; ".join(active_formats))

    return {
        "format_profile": format_profile,
        "s24_to_s27_groups": int(np.sum(input_widths == 24)),
        "s32_to_s35_groups": int(np.sum(input_widths == 32)),
        "groups": int(source.shape[0]),
        "elements": int(source.size),
        "input_min": float(source.min()),
        "input_max": float(source.max()),
        "input_saturation_elements": int(input_saturation.sum()),
        "input_saturation_groups": int(input_saturation.any(axis=1).sum()),
        "hadamard_saturation_elements": int(h_saturation.sum()),
        "input_fp_to_s24_rmse": _rmse(input_error),
        "input_fp_to_s24_max_abs": float(np.max(np.abs(input_error))),
        "input_fp_to_s24_exact_rate": float(np.mean(input_error == 0.0)),
        "input_fp_to_q16_rmse": _rmse(input_error),
        "input_fp_to_q16_max_abs": float(np.max(np.abs(input_error))),
        "input_fp_to_q16_exact_rate": float(np.mean(input_error == 0.0)),
        "post_h_input_q_only_rmse": _rmse(preq_h_error),
        "post_h_input_q_only_max_abs": float(np.max(np.abs(preq_h_error))),
        "post_h_rtl_exact_rmse": _rmse(hardware_h_error),
        "post_h_rtl_exact_max_abs": float(np.max(np.abs(hardware_h_error))),
        "post_h_rtl_exact_cosine": _cosine(hardware_h, reference_h),
        "post_h_rtl_exact_sqnr_db": _sqnr_db(reference_h, hardware_h_error),
        "software_a8_vs_fp_h_rmse": software_rmse,
        "hardware_a8_vs_fp_h_rmse": hardware_rmse,
        "hardware_a8_rmse_relative_change": (
            hardware_rmse / software_rmse - 1.0 if software_rmse else None),
        "hardware_minus_software_a8_mse": hardware_mse - software_mse,
        "hardware_vs_software_a8_rmse": _rmse(frontend_delta),
        "frontend_delta_over_software_a8_rmse": (
            _rmse(frontend_delta) / software_rmse if software_rmse else None),
        "hardware_vs_software_a8_max_abs": float(np.max(np.abs(frontend_delta))),
        "hardware_vs_software_a8_cosine": _cosine(hardware_a8.dq, software_a8.dq),
        "hardware_a8_vs_fp_h_sqnr_db": _sqnr_db(reference_h, hardware_a8_error),
        "a8_quantized_byte_match_rate": float(np.mean(software_a8.q == hardware_a8.q)),
        "a8_metadata_group_match_rate": float(np.mean(metadata_match)),
        "frontend_delta_group_rmse_p50": float(np.percentile(per_group_frontend_rmse, 50)),
        "frontend_delta_group_rmse_p99": float(np.percentile(per_group_frontend_rmse, 99)),
        "frontend_delta_group_rmse_max": float(per_group_frontend_rmse.max()),
        "hardware_error_group_rmse_p99": float(np.percentile(per_group_hardware_rmse, 99)),
        "hadamard_coefficient_relative_error": coefficient_relative_error,
        "theorem_checked_groups": int(valid_theorem_group.sum()),
        "theorem_violation_groups": int(theorem_violation.sum()),
        "theorem_max_l2_error": float(hardware_h_l2[valid_theorem_group].max())
        if np.any(valid_theorem_group) else None,
        "theorem_max_l2_bound": float(theorem_bound[valid_theorem_group].max())
        if np.any(valid_theorem_group) else None,
        "orthogonal_energy_identity_max_abs": float(energy_identity_error.max()),
    }
