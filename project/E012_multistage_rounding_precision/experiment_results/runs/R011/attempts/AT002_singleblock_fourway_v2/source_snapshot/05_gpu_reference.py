"""Exact intermediate arithmetic with the existing V5 integer node exits.

Experimental only. The linear kernel retains a quotient and a common binary
remainder; it does not use floating point for ScaleCode products/reductions.
The small integer Group32 dot follows the same integer-exact tensor-core path
as production. Bounds and independent CPU/Fraction checks are required before
model results from this module are evidence.
"""
from contextlib import contextmanager
from functools import partial

import torch
import triton
import triton.language as tl

from .policy import OUTPUT_ONLY

S24_MIN = -(1 << 23)
S24_MAX = (1 << 23) - 1
SCORE_LIMIT = 16 << 14


@triton.jit
def _linear_exact_kernel(
    ap, acp, asp, azp, wp, wcp, wsp, op, satp,
    rows: tl.constexpr, columns: tl.constexpr, groups: tl.constexpr,
    output_min: tl.constexpr, output_max: tl.constexpr,
    common_bits: tl.constexpr, BM: tl.constexpr, BN: tl.constexpr,
):
    ri = tl.program_id(0) * BM + tl.arange(0, BM)
    ci = tl.program_id(1) * BN + tl.arange(0, BN)
    li = tl.arange(0, 32)
    rm = ri < rows
    cm = ci < columns
    quotient = tl.zeros((BM, BN), tl.int64)
    remainder = tl.zeros((BM, BN), tl.int64)
    for g in tl.range(0, groups):
        a = tl.load(ap + (ri[:, None] * groups + g) * 32 + li[None, :],
                    rm[:, None], 0).to(tl.int32)
        z = tl.load(azp + ri * groups + g, rm, 0).to(tl.int32)
        w = tl.load(wp + (ci[None, :] * groups + g) * 32 + li[:, None],
                    cm[None, :], 0).to(tl.int32)
        dot = tl.dot((a - z[:, None]).to(tl.float32), w.to(tl.float32),
                     input_precision="tf32", out_dtype=tl.float32).to(tl.int64)
        ac = tl.load(acp + ri * groups + g, rm, 0).to(tl.int64)
        wc = tl.load(wcp + ci * groups + g, cm, 0).to(tl.int64)
        ash = tl.load(asp + ri * groups + g, rm, 0).to(tl.int32)
        wsh = tl.load(wsp + ci * groups + g, cm, 0).to(tl.int32)
        raw = dot * ac[:, None] * wc[None, :]
        active = (ac[:, None] != 0) & (wc[None, :] != 0)
        k = tl.where(active, ash[:, None] + wsh[None, :] - 16, 0)
        right = tl.maximum(k, 0)
        left = tl.maximum(-k, 0)
        q = (raw >> right) << left
        # For k <= 0 the multiplication is exact and residue is zero.
        residue = tl.where(k > 0, raw - ((raw >> right) << right), 0)
        quotient += q
        remainder += residue << (common_bits - right)
    quotient += remainder >> common_bits
    remainder &= (1 << common_bits) - 1
    twice = remainder << 1
    increment = tl.where(quotient >= 0, twice >= (1 << common_bits),
                          twice > (1 << common_bits))
    rounded = quotient + increment.to(tl.int64)
    saturated = tl.minimum(tl.maximum(rounded, output_min), output_max)
    mask = rm[:, None] & cm[None, :]
    count = tl.sum(tl.sum((mask & (rounded != saturated)).to(tl.int64), 1), 0)
    tl.atomic_add(satp, count)
    tl.store(op + ri[:, None] * columns + ci[None, :], saturated.to(tl.int32), mask)


def grouped_linear_exact(
    activation, weight_s8, weight_codes_u8, weight_shifts_u8,
    shift_min, shift_max, hardware_accumulator_width, compute_accumulator_width,
    compute_group_guard_width, zero_invalid_guard, audit_hardware_group_guard,
    saturation_count, group_guard_overflow_count, software_group_guard_overflow_count,
    accumulator_overflow_count, software_accumulator_overflow_count,
    output_min=S24_MIN, output_max=S24_MAX,
):
    """Production call signature; finite internal guard/acc limits are removed.

    Production project_prepared still checks every active shift before calling
    this function. Saturation is retained; production guard/acc counters are
    not populated for this wider reference and must be labelled in its report.
    """
    del hardware_accumulator_width, compute_accumulator_width, compute_group_guard_width
    del audit_hardware_group_guard, group_guard_overflow_count, software_group_guard_overflow_count
    del accumulator_overflow_count, software_accumulator_overflow_count
    if not zero_invalid_guard or (shift_min, shift_max) not in {(26, 47), (20, 44), (12, 44)}:
        raise ValueError("exact reference requires a strict supported production format")
    columns, groups, lanes = weight_s8.shape
    if not weight_s8.is_cuda or groups != activation.groups or lanes != 32 or groups > 448:
        raise ValueError("exact Linear requires CUDA Group32 with at most 448 groups")
    inputs = (activation.values_u8, activation.codes_u8, activation.shifts_u8,
              activation.zero_points_u8, weight_s8, weight_codes_u8, weight_shifts_u8)
    if any(not x.is_contiguous() for x in inputs):
        raise ValueError("exact Linear expects contiguous production tensors")
    output = torch.empty((activation.rows, columns), dtype=torch.int32, device=weight_s8.device)
    _linear_exact_kernel[(triton.cdiv(activation.rows, 16), triton.cdiv(columns, 16))](
        *inputs, output, saturation_count, activation.rows, columns, groups,
        output_min, output_max, shift_max - 16, 16, 16, num_warps=4,
    )
    return output.reshape(*activation.leading_shape, columns)


def _round_binary(numerator, bits):
    q = numerator >> bits
    r = numerator - (q << bits)
    half = 1 << (bits - 1)
    return q + torch.where(q >= 0, r >= half, r > half).to(torch.int64)


def _sum_binary(numerator, shift, dim, common_bits):
    """Exact sum for nonnegative shifts under the node-specific int64 bounds."""
    quotient = numerator >> shift
    residue = numerator - (quotient << shift)
    q = quotient.sum(dim=dim)
    r = (residue << (common_bits - shift)).sum(dim=dim)
    q = q + (r >> common_bits)
    r = r & ((1 << common_bits) - 1)
    return q, r


def _round_parts(q, r, bits):
    half = 1 << (bits - 1)
    return q + torch.where(q >= 0, r >= half, r > half).to(torch.int64)


def rope_exact(raw, cos_q16, sin_q16, audit):
    low, high = raw[..., :64].to(torch.int64), raw[..., 64:].to(torch.int64)
    cos, sin = cos_q16[:, :, None, :].to(torch.int64), sin_q16[:, :, None, :].to(torch.int64)
    a = _round_binary(low * cos - high * sin, 16)
    b = _round_binary(low * sin + high * cos, 16)
    joined = torch.cat((a, b), dim=-1)
    audit.add("rope_output_saturation", ((joined < S24_MIN) | (joined > S24_MAX)).sum())
    return joined.clamp(S24_MIN, S24_MAX).to(torch.int32)


def qk_exact(query_s24, keys, num_key_value_groups, audit):
    batch, queries, heads, _ = query_s24.shape
    query = query_s24.reshape(batch, queries, heads, 4, 32).permute(0, 2, 3, 1, 4).to(torch.float64)
    key = keys.values_s12.repeat_interleave(num_key_value_groups, dim=2).permute(0, 2, 3, 1, 4).to(torch.float64)
    # Each partial dot is an exact integer below 2^40, before scaling.
    dot = torch.matmul(query, key.transpose(-1, -2)).to(torch.int64)
    codes = keys.codes_u8.repeat_interleave(num_key_value_groups, dim=2).permute(0, 2, 3, 1).to(torch.int64)
    shifts = keys.shifts_u8.repeat_interleave(num_key_value_groups, dim=2).permute(0, 2, 3, 1).to(torch.int64)
    raw = dot * codes[..., None, :] * 5793
    exponent = torch.where(codes != 0, shifts + 18, 0)
    q, _ = _sum_binary(raw, exponent[..., None, :], 2, 50)
    clipped = q.clamp(-SCORE_LIMIT, SCORE_LIMIT)
    audit.add("qk_score_clip", (clipped != q).sum())
    return clipped


def softmax_exact(score_s20, valid_mask, lut_u17, *, interpolation_round=False,
                  reciprocal_round=False):
    score_s20, lut_u17 = score_s20.to(torch.int64), lut_u17.to(torch.int64)
    sentinel = torch.full_like(score_s20, -(1 << 19))
    row_max = torch.where(valid_mask, score_s20, sentinel).amax(dim=-1, keepdim=True)
    magnitude = -(score_s20 - row_max).clamp(-SCORE_LIMIT, 0)
    index, fraction = magnitude >> 10, magnitude & 1023
    high, low = lut_u17[index], lut_u17[(index + 1).clamp_max(256)]
    loss = (high - low) * fraction
    if interpolation_round:
        exponent = (high - ((loss + 512) >> 10)) << 10
    else:
        exponent = (high << 10) - loss
    exponent = torch.where(valid_mask, exponent, 0)
    total = exponent.sum(dim=-1, keepdim=True)
    has_key = valid_mask.any(dim=-1, keepdim=True)
    safe = torch.where(has_key, total, 1 << 26)
    if reciprocal_round:
        inverse = ((1 << 42) + safe // 2) // safe
        result = (exponent * inverse + (1 << 25)) >> 26
    else:
        numerator = exponent << 16
        quotient = torch.div(numerator, safe, rounding_mode="floor")
        residue = numerator - quotient * safe
        result = quotient + ((residue << 1) >= safe).to(torch.int64)
    return torch.where(has_key, result.clamp_max(65535), 0).to(torch.int64)


def pv_exact(probability_u16, values, num_key_value_groups, audit, head_chunk=4):
    batch, heads, queries, _ = probability_u16.shape
    vh = values.values_s12.repeat_interleave(num_key_value_groups, dim=2).to(torch.int64)
    ch = values.codes_u8.repeat_interleave(num_key_value_groups, dim=2).to(torch.int64)
    sh = values.shifts_u8.repeat_interleave(num_key_value_groups, dim=2).to(torch.int64)
    output = torch.empty((batch, heads, queries, 4, 32), device=probability_u16.device, dtype=torch.int32)
    for begin in range(0, heads, head_chunk):
        end = min(begin + head_chunk, heads)
        prob = probability_u16[:, begin:end]
        for group in range(4):
            value = vh[:, :, begin:end, group, :]
            code = ch[:, :, begin:end, group]
            shift = torch.where(code != 0, sh[:, :, begin:end, group], 0)
            product = prob[..., None] * (value * code[..., None]).permute(0, 2, 1, 3)[:, :, None, :, :]
            exponent = shift.permute(0, 2, 1)[:, :, None, :, None]
            q, r = _sum_binary(product, exponent, 3, 32)
            rounded = _round_parts(q, r, 32)
            audit.add("pv_output_saturation", ((rounded < S24_MIN) | (rounded > S24_MAX)).sum())
            output[:, begin:end, :, group, :] = rounded.clamp(S24_MIN, S24_MAX).to(torch.int32)
    return output.reshape(batch, heads, queries, 128)


@contextmanager
def arithmetic_context(v5, policy=OUTPUT_ONLY):
    """Select arithmetic for one sequential forward, restoring all symbols.

    This process-local patch is not thread safe; paired forwards run serially.
    It changes no weights, quantizers, LUTs, Host operations or source files.
    """
    marker = '_m005_arithmetic_context_active'
    if getattr(v5, marker, False) or getattr(v5, '_m005_local_observer_active', False):
        raise RuntimeError('arithmetic contexts must be sequential, not nested')
    patches = {}
    if not policy.linear_group_floor:
        patches['grouped_linear_s24'] = grouped_linear_exact
    if not policy.rope_product_round:
        patches['_fixed_rope'] = rope_exact
    if not policy.qk_group_floor:
        patches['_qk_scores_s20'] = qk_exact
    if not (policy.softmax_interpolation_round and policy.softmax_reciprocal_round):
        patches['_softmax_u16'] = partial(softmax_exact,
            interpolation_round=policy.softmax_interpolation_round,
            reciprocal_round=policy.softmax_reciprocal_round)
    if not policy.pv_term_floor:
        patches['_pv_s24'] = pv_exact
    originals = {name: getattr(v5, name) for name in patches}
    try:
        setattr(v5, marker, True)
        for name, value in patches.items():
            setattr(v5, name, value)
        yield
    finally:
        for name, value in originals.items():
            setattr(v5, name, value)
        delattr(v5, marker)
