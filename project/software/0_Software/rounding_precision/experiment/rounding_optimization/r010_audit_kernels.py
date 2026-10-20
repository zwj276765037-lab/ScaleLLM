"""R010 observer-only copy of original production Linear and independent exact parts.
No production source is modified. Original kernel arithmetic retained byte-for-byte
apart from name/signature and observer-only counters/pre-exit accumulator export.
The second kernel copies the independent quotient/remainder reference and only
exports its normalized exact unrounded parts before original common-exit round.
"""
import torch
import triton
import triton.language as tl
from triton.language.extra.cuda import libdevice

@triton.jit
def _r010_observed_kernel(
    act_ptr,
    act_code_ptr,
    act_shift_ptr,
    act_zp_ptr,
    weight_ptr,
    weight_code_ptr,
    weight_shift_ptr,
    output_ptr,
    pre_exit_accumulator_ptr,
    active_shift_hist_ptr,
    nonzero_remainder_hist_ptr,
    discarded_one_bits_ptr,
    saturation_count_ptr,
    group_guard_overflow_count_ptr,
    software_group_guard_overflow_count_ptr,
    accumulator_overflow_count_ptr,
    software_accumulator_overflow_count_ptr,
    rows: tl.constexpr,
    columns: tl.constexpr,
    group_count: tl.constexpr,
    GROUP_SIZE: tl.constexpr,
    OUTPUT_MIN: tl.constexpr,
    OUTPUT_MAX: tl.constexpr,
    SHIFT_MIN: tl.constexpr,
    SHIFT_MAX: tl.constexpr,
    HARDWARE_ACCUM_MIN: tl.constexpr,
    HARDWARE_ACCUM_MAX: tl.constexpr,
    COMPUTE_ACCUM_MIN: tl.constexpr,
    COMPUTE_ACCUM_MAX: tl.constexpr,
    COMPUTE_ACCUM_MASK: tl.constexpr,
    COMPUTE_GUARD_MIN: tl.constexpr,
    COMPUTE_GUARD_MAX: tl.constexpr,
    ZERO_INVALID_GUARD: tl.constexpr,
    AUDIT_HARDWARE_GROUP_GUARD: tl.constexpr,
    BLOCK_M: tl.constexpr,
    BLOCK_N: tl.constexpr,
):
    row_ids = tl.program_id(0) * BLOCK_M + tl.arange(0, BLOCK_M)
    column_ids = tl.program_id(1) * BLOCK_N + tl.arange(0, BLOCK_N)
    lane_ids = tl.arange(0, GROUP_SIZE)
    row_mask = row_ids < rows
    column_mask = column_ids < columns
    accumulator = tl.zeros((BLOCK_M, BLOCK_N), dtype=tl.int64)
    group_guard_overflow_total = tl.zeros((), dtype=tl.int64)
    software_group_guard_overflow_total = tl.zeros((), dtype=tl.int64)
    accumulator_overflow_total = tl.zeros((), dtype=tl.int64)
    software_accumulator_overflow_total = tl.zeros((), dtype=tl.int64)

    active_shift_hist = tl.zeros((32,), tl.int64)
    nonzero_remainder_hist = tl.zeros((32,), tl.int64)
    discarded_one_bits = tl.zeros((), tl.int64)
    for group in tl.range(0, group_count):
        act_offsets = (
            (row_ids[:, None] * group_count + group) * GROUP_SIZE
            + lane_ids[None, :]
        )
        weight_offsets = (
            (column_ids[None, :] * group_count + group) * GROUP_SIZE
            + lane_ids[:, None]
        )
        act = tl.load(
            act_ptr + act_offsets,
            mask=row_mask[:, None],
            other=0,
        ).to(tl.int32)
        zp = tl.load(
            act_zp_ptr + row_ids * group_count + group,
            mask=row_mask,
            other=0,
        ).to(tl.int32)
        weight = tl.load(
            weight_ptr + weight_offsets,
            mask=column_mask[None, :],
            other=0,
        ).to(tl.int32)
        centered = act - zp[:, None]
        correlation = tl.dot(
            centered.to(tl.float32),
            weight.to(tl.float32),
            # centered A8 and W8/W4 are small exact integers.  Their Group32
            # dot is bounded by 32*255*127=1,036,320 < 2^20, so TF32 inputs,
            # products and FP32 accumulation remain integer-exact while using
            # Ampere Tensor Cores.  Scalar conformance tests cover this path.
            input_precision="tf32",
            out_dtype=tl.float32,
        ).to(tl.int64)
        act_code = tl.load(
            act_code_ptr + row_ids * group_count + group,
            mask=row_mask,
            other=0,
        ).to(tl.int64)
        act_shift = tl.load(
            act_shift_ptr + row_ids * group_count + group,
            mask=row_mask,
            other=0,
        ).to(tl.int32)
        weight_code = tl.load(
            weight_code_ptr + column_ids * group_count + group,
            mask=column_mask,
            other=0,
        ).to(tl.int64)
        weight_shift = tl.load(
            weight_shift_ptr + column_ids * group_count + group,
            mask=column_mask,
            other=0,
        ).to(tl.int32)
        raw = correlation * act_code[:, None] * weight_code[None, :]
        delta = act_shift[:, None] + weight_shift[None, :] - 24
        right = tl.maximum(delta, 0)
        left = tl.maximum(-delta, 0)
        aligned = (raw >> right) << left
        pair_active = (act_code[:, None] != 0) & (weight_code[None, :] != 0)
        legal_shift = (delta + 24 >= SHIFT_MIN) & (delta + 24 <= SHIFT_MAX)
        valid_output = row_mask[:, None] & column_mask[None, :]
        # Observer-only summaries: inactive pairs use sentinel31 and contribute no bits.
        observed_pair = valid_output & pair_active
        safe_right = tl.where(observed_pair, right, 0)
        lost = raw - ((raw >> safe_right) << safe_right)
        active_bins = tl.reshape(tl.where(observed_pair, right, 31), (BLOCK_M * BLOCK_N,))
        lost_bins = tl.reshape(tl.where(observed_pair & (lost != 0), right, 31), (BLOCK_M * BLOCK_N,))
        active_shift_hist += tl.histogram(active_bins, 32).to(tl.int64)
        nonzero_remainder_hist += tl.histogram(lost_bins, 32).to(tl.int64)
        ones = libdevice.popc(lost.to(tl.int64)).to(tl.int64)
        discarded_one_bits += tl.sum(tl.sum(tl.where(observed_pair, ones, 0), 1), 0)

        if AUDIT_HARDWARE_GROUP_GUARD:
            guard_overflow = valid_output & pair_active & (
                (aligned < COMPUTE_GUARD_MIN)
                | (aligned > COMPUTE_GUARD_MAX)
            )
            group_guard_overflow_total += tl.sum(tl.sum(
                guard_overflow.to(tl.int64), axis=1
            ), axis=0)
        software_guard_overflow = valid_output & pair_active & (
            (aligned < COMPUTE_GUARD_MIN) | (aligned > COMPUTE_GUARD_MAX)
        )
        software_group_guard_overflow_total += tl.sum(tl.sum(
            software_guard_overflow.to(tl.int64), axis=1
        ), axis=0)
        # strict_rtl and rtl_zero_guard reproduce the production error path.
        # software_extended retains the mathematically aligned contribution
        # while still auditing it against the production RTL widths.
        if ZERO_INVALID_GUARD:
            guard = tl.where(pair_active & ~legal_shift, 0, aligned)
        else:
            guard = aligned
        next_accumulator = accumulator + guard
        accumulator_overflow = valid_output & (
            (next_accumulator < HARDWARE_ACCUM_MIN)
            | (next_accumulator > HARDWARE_ACCUM_MAX)
        )
        overflow_count = tl.sum(tl.sum(
            accumulator_overflow.to(tl.int64), axis=1
        ), axis=0)
        accumulator_overflow_total += overflow_count
        software_accumulator_overflow = valid_output & (
            (next_accumulator < COMPUTE_ACCUM_MIN)
            | (next_accumulator > COMPUTE_ACCUM_MAX)
        )
        software_accumulator_overflow_total += tl.sum(tl.sum(
            software_accumulator_overflow.to(tl.int64), axis=1
        ), axis=0)
        accumulator = (
            (next_accumulator - COMPUTE_ACCUM_MIN) & COMPUTE_ACCUM_MASK
        ) + COMPUTE_ACCUM_MIN

    hi = tl.arange(0, 32)
    tl.atomic_add(active_shift_hist_ptr + hi, active_shift_hist, hi < 31)
    tl.atomic_add(nonzero_remainder_hist_ptr + hi, nonzero_remainder_hist, hi < 31)
    tl.atomic_add(discarded_one_bits_ptr, discarded_one_bits)
    tl.store(pre_exit_accumulator_ptr + row_ids[:, None] * columns + column_ids[None, :],
             accumulator, row_mask[:, None] & column_mask[None, :])
    rounded = tl.where(
        accumulator >= 0,
        (accumulator + 128) >> 8,
        -(((-accumulator) + 128) >> 8),
    )
    saturated = tl.minimum(tl.maximum(rounded, OUTPUT_MIN), OUTPUT_MAX)
    saturation_mask = row_mask[:, None] & column_mask[None, :] & (
        rounded != saturated
    )
    saturation_count = tl.sum(
        tl.sum(saturation_mask.to(tl.int64), axis=1), axis=0
    )
    tl.atomic_add(saturation_count_ptr, saturation_count)
    tl.atomic_add(group_guard_overflow_count_ptr, group_guard_overflow_total)
    tl.atomic_add(
        software_group_guard_overflow_count_ptr,
        software_group_guard_overflow_total,
    )
    tl.atomic_add(accumulator_overflow_count_ptr, accumulator_overflow_total)
    tl.atomic_add(
        software_accumulator_overflow_count_ptr,
        software_accumulator_overflow_total,
    )
    output_offsets = row_ids[:, None] * columns + column_ids[None, :]
    tl.store(
        output_ptr + output_offsets,
        saturated.to(tl.int32),
        mask=row_mask[:, None] & column_mask[None, :],
    )


@triton.jit
def _r010_exact_parts_kernel(
    ap, acp, asp, azp, wp, wcp, wsp, op, satp, quotient_ptr, remainder_ptr,
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
    mask = rm[:, None] & cm[None, :]
    tl.store(quotient_ptr + ri[:, None] * columns + ci[None, :], quotient, mask)
    tl.store(remainder_ptr + ri[:, None] * columns + ci[None, :], remainder, mask)
    twice = remainder << 1
    increment = tl.where(quotient >= 0, twice >= (1 << common_bits),
                          twice > (1 << common_bits))
    rounded = quotient + increment.to(tl.int64)
    saturated = tl.minimum(tl.maximum(rounded, output_min), output_max)
    mask = rm[:, None] & cm[None, :]
    count = tl.sum(tl.sum((mask & (rounded != saturated)).to(tl.int64), 1), 0)
    tl.atomic_add(satp, count)
    tl.store(op + ri[:, None] * columns + ci[None, :], saturated.to(tl.int32), mask)



def capture(activation, module):
    attention = module.op_name == 'o_proj'
    shift_min, shift_max = (26, 47) if attention else (12, 44)
    aw, gw = (42, 42) if attention else (54, 45)
    rows=activation.rows;columns,groups,lanes=module.weight_s8.shape
    assert lanes==32 and (attention or module.down_shift12_candidate)
    shape=(rows,columns);device=module.weight_s8.device
    output=torch.empty(shape,dtype=torch.int32,device=device)
    accumulator=torch.empty(shape,dtype=torch.int64,device=device)
    counters=[torch.zeros((),dtype=torch.int64,device=device) for _ in range(5)]
    histogram=torch.zeros((32,),dtype=torch.int64,device=device)
    losthist=torch.zeros_like(histogram);ones=torch.zeros_like(counters[0])
    args=(activation.values_u8,activation.codes_u8,activation.shifts_u8,activation.zero_points_u8,
          module.weight_s8,module.weight_codes_u8,module.weight_shifts_u8)
    grid=(triton.cdiv(rows,16),triton.cdiv(columns,16))
    _r010_observed_kernel[grid](*args,output,accumulator,histogram,losthist,ones,*counters,
        rows=rows,columns=columns,group_count=groups,GROUP_SIZE=32,
        OUTPUT_MIN=-(1<<(module.output_width-1)),OUTPUT_MAX=(1<<(module.output_width-1))-1,
        SHIFT_MIN=shift_min,SHIFT_MAX=shift_max,HARDWARE_ACCUM_MIN=-(1<<(aw-1)),HARDWARE_ACCUM_MAX=(1<<(aw-1))-1,
        COMPUTE_ACCUM_MIN=-(1<<(aw-1)),COMPUTE_ACCUM_MAX=(1<<(aw-1))-1,COMPUTE_ACCUM_MASK=(1<<aw)-1,
        COMPUTE_GUARD_MIN=-(1<<(gw-1)),COMPUTE_GUARD_MAX=(1<<(gw-1))-1,
        ZERO_INVALID_GUARD=True,AUDIT_HARDWARE_GROUP_GUARD=False,BLOCK_M=16,BLOCK_N=16,num_warps=4)
    exact=torch.empty_like(output);q=torch.empty_like(accumulator);r=torch.empty(shape,dtype=torch.int32,device=device)
    sat=torch.zeros((),dtype=torch.int64,device=device)
    _r010_exact_parts_kernel[grid](*args,exact,sat,q,r,rows,columns,groups,
        -(1<<(module.output_width-1)),(1<<(module.output_width-1))-1,shift_max-16,16,16,num_warps=4)
    return dict(accumulator=accumulator,current_code=output,reference_code=exact,exact_quotient=q,exact_remainder=r,
                active_shift_hist=histogram,nonzero_remainder_hist=losthist,discarded_one_bits=ones,
                counters=counters,reference_saturation=sat,common_bits=shift_max-16)
