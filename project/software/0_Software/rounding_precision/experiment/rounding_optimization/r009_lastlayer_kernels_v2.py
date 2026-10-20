"""R009 two-exit experimental format overlay; frozen production sources untouched.
Candidate finite-width floor alignment and independent exact quotient/remainder
reference are separate implementations. Both use genuine expanded outputs.
"""
from __future__ import annotations
from contextlib import contextmanager
import torch
import triton
import triton.language as tl
from numerical_reference.model_compat import production_module
_v5=production_module()
GROUP=_v5.GROUP
S24_MIN=_v5.S24_MIN
S24_MAX=_v5.S24_MAX


@triton.jit
def _r009_grouped_linear_kernel(
    act_ptr,
    act_code_ptr,
    act_shift_ptr,
    act_zp_ptr,
    weight_ptr,
    weight_code_ptr,
    weight_shift_ptr,
    output_ptr,
    saturation_count_ptr,
    group_guard_overflow_count_ptr,
    software_group_guard_overflow_count_ptr,
    accumulator_overflow_count_ptr,
    software_accumulator_overflow_count_ptr,
    rows: tl.constexpr,
    columns: tl.constexpr,
    group_count: tl.constexpr,
    EXTRA_BITS: tl.constexpr,
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
        delta = act_shift[:, None] + weight_shift[None, :] - (24 + EXTRA_BITS)
        active_shift = (act_code[:, None] != 0) & (weight_code[None, :] != 0)
        right = tl.where(active_shift, tl.maximum(delta, 0), 0)
        left = tl.where(active_shift, tl.maximum(-delta, 0), 0)
        aligned = (raw >> right) << left
        pair_active = (act_code[:, None] != 0) & (weight_code[None, :] != 0)
        legal_shift = (delta + 24 + EXTRA_BITS >= SHIFT_MIN) & (delta + 24 + EXTRA_BITS <= SHIFT_MAX)
        valid_output = row_mask[:, None] & column_mask[None, :]
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
        saturated.to(tl.int64),
        mask=row_mask[:, None] & column_mask[None, :],
    )

def grouped_linear_wide(
    activation: PreparedActivation,
    weight_s8: torch.Tensor,
    weight_codes_u8: torch.Tensor,
    weight_shifts_u8: torch.Tensor,
    shift_min: int,
    shift_max: int,
    hardware_accumulator_width: int,
    compute_accumulator_width: int,
    compute_group_guard_width: int,
    zero_invalid_guard: bool,
    audit_hardware_group_guard: bool,
    saturation_count: torch.Tensor,
    group_guard_overflow_count: torch.Tensor,
    software_group_guard_overflow_count: torch.Tensor,
    accumulator_overflow_count: torch.Tensor,
    software_accumulator_overflow_count: torch.Tensor,
    output_min: int = S24_MIN,
    output_max: int = S24_MAX,
    extra_bits: int = 0,
) -> torch.Tensor:
    if not weight_s8.is_cuda:
        raise ValueError("V5 grouped linear requires CUDA")
    rows = activation.rows
    columns, groups, lanes = weight_s8.shape
    if groups != activation.groups or lanes != GROUP:
        raise ValueError("activation/weight Group32 geometry mismatch")
    output = torch.empty(
        (rows, columns), dtype=torch.int64, device=weight_s8.device
    )
    # tl.dot requires an M tile of at least 16 on the CUDA backend.  Rows
    # below 16 are handled by the load/store masks.
    block_m = 16
    block_n = 16
    grid = (triton.cdiv(rows, block_m), triton.cdiv(columns, block_n))
    _r009_grouped_linear_kernel[grid](
        activation.values_u8,
        activation.codes_u8,
        activation.shifts_u8,
        activation.zero_points_u8,
        weight_s8,
        weight_codes_u8,
        weight_shifts_u8,
        output,
        saturation_count,
        group_guard_overflow_count,
        software_group_guard_overflow_count,
        accumulator_overflow_count,
        software_accumulator_overflow_count,
        rows=rows,
        columns=columns,
        group_count=groups,
        EXTRA_BITS=extra_bits,
        GROUP_SIZE=GROUP,
        OUTPUT_MIN=output_min,
        OUTPUT_MAX=output_max,
        SHIFT_MIN=shift_min,
        SHIFT_MAX=shift_max,
        HARDWARE_ACCUM_MIN=-(1 << (hardware_accumulator_width + extra_bits - 1)),
        HARDWARE_ACCUM_MAX=(1 << (hardware_accumulator_width + extra_bits - 1)) - 1,
        COMPUTE_ACCUM_MIN=-(1 << (compute_accumulator_width + extra_bits - 1)),
        COMPUTE_ACCUM_MAX=(1 << (compute_accumulator_width + extra_bits - 1)) - 1,
        COMPUTE_ACCUM_MASK=(1 << (compute_accumulator_width + extra_bits)) - 1,
        COMPUTE_GUARD_MIN=-(1 << (compute_group_guard_width + extra_bits - 1)),
        COMPUTE_GUARD_MAX=(1 << (compute_group_guard_width + extra_bits - 1)) - 1,
        ZERO_INVALID_GUARD=zero_invalid_guard,
        AUDIT_HARDWARE_GROUP_GUARD=audit_hardware_group_guard,
        BLOCK_M=block_m,
        BLOCK_N=block_n,
        num_warps=4,
    )
    return output.reshape(*activation.leading_shape, columns)

@triton.jit
def _r009_linear_exact_kernel(
    ap, acp, asp, azp, wp, wcp, wsp, op, satp,
    rows: tl.constexpr, columns: tl.constexpr, groups: tl.constexpr,
    output_min: tl.constexpr, output_max: tl.constexpr,
    output_fractional_bits: tl.constexpr, common_bits: tl.constexpr, BM: tl.constexpr, BN: tl.constexpr,
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
        k = tl.where(active, ash[:, None] + wsh[None, :] - output_fractional_bits, 0)
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
    tl.store(op + ri[:, None] * columns + ci[None, :], saturated.to(tl.int64), mask)

def grouped_linear_wide_reference(
    activation, weight_s8, weight_codes_u8, weight_shifts_u8,
    shift_min, shift_max, hardware_accumulator_width, compute_accumulator_width,
    compute_group_guard_width, zero_invalid_guard, audit_hardware_group_guard,
    saturation_count, group_guard_overflow_count, software_group_guard_overflow_count,
    accumulator_overflow_count, software_accumulator_overflow_count,
    output_min=S24_MIN, output_max=S24_MAX, extra_bits=0,
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
    output = torch.empty((activation.rows, columns), dtype=torch.int64, device=weight_s8.device)
    _r009_linear_exact_kernel[(triton.cdiv(activation.rows, 16), triton.cdiv(columns, 16))](
        *inputs, output, saturation_count, activation.rows, columns, groups,
        output_min, output_max, 16 + extra_bits, shift_max - (16 + extra_bits), 16, 16, num_warps=4,
    )
    return output.reshape(*activation.leading_shape, columns)


def _binding_key(module,name):
    value=getattr(module,name)
    return (name in module.__dict__,getattr(value,'__func__',value))


def interface_signature(model):
    layer=model.model.layers[31]
    attention=getattr(layer.self_attn,'core',layer.self_attn)
    mlp=layer.mlp
    return dict(o_width=attention.o_proj.output_width,down_width=mlp.down_proj.output_width,
        o_project=_binding_key(attention.o_proj,'project_prepared'),down_project=_binding_key(mlp.down_proj,'project_prepared'),
        attention_forward=_binding_key(attention,'forward'),mlp_forward=_binding_key(mlp,'forward'),
        attention_output_dtype=attention.output_dtype,mlp_output_dtype=mlp.output_dtype)


@contextmanager
def lastlayer_exit_context(v5,model,b,*,reference=False,events=None):
    """Overlay only layer31 o_proj/down_proj; restore actual instance dictionaries.

    Original branch forward divides by2^16 in FP32. The wrapper multiplies only
    that returned branch by2^-b before the HF residual, exactly once; this equals
    dividing its int64 code by2^(16+b). The auxiliary attention probabilities
    retain their original format.
    """
    if b not in (0,2,4):raise ValueError('R009 only supports b0/b2/b4')
    if getattr(v5,'_r009_exit_overlay_active',False):raise RuntimeError('nested R009 exit overlay')
    if b==0:
        yield
        return
    layer=model.model.layers[31];attention=getattr(layer.self_attn,'core',layer.self_attn);mlp=layer.mlp
    if attention.output_dtype not in (None,torch.float32) or mlp.output_dtype not in (None,torch.float32):
        raise ValueError('R009 Host branches must remain FP32, no BF16 output cast')
    before=interface_signature(model);original_grouped=v5.grouped_linear_s24
    state={'selected':None};saved=[]
    def patch(module,name,value):
        saved.append((module,name,name in module.__dict__,module.__dict__.get(name)))
        setattr(module,name,value)
    def dispatch(*args,**kwargs):
        if state['selected'] is not None:
            fn=grouped_linear_wide_reference if reference else grouped_linear_wide
            return fn(*args,**kwargs,extra_bits=b)
        return original_grouped(*args,**kwargs)
    try:
        setattr(v5,'_r009_exit_overlay_active',True);v5.grouped_linear_s24=dispatch
        for module,base_width,name in [(attention.o_proj,24,'o_proj'),(mlp.down_proj,32,'down_proj')]:
            if module.output_width!=base_width:raise ValueError('unexpected original branch output width')
            original_project=module.project_prepared
            patch(module,'output_width',base_width+b)
            def project(activation,original=original_project,name=name):
                if state['selected'] is not None:raise RuntimeError('nested selected projection')
                state['selected']=name
                try:
                    value=original(activation)
                    if value.dtype!=torch.int64:raise RuntimeError('wide projection output must be int64')
                    if events is not None:events.append(dict(kind='wide_projection',op=name,b=b,dtype=str(value.dtype)))
                    return value
                finally:state['selected']=None
            patch(module,'project_prepared',project)
        original_attention=attention.forward;original_mlp=mlp.forward
        def attention_forward(*args,**kwargs):
            result=original_attention(*args,**kwargs)
            if not isinstance(result,tuple) or result[0].dtype!=torch.float32:raise RuntimeError('attention branch not FP32 before overlay scale')
            scaled=result[0]*(2.0**(-b))
            if events is not None:events.append(dict(kind='host_scale',op='o_proj',b=b,input_dtype=str(result[0].dtype),output_dtype=str(scaled.dtype),scale=2.0**(-b)))
            return (scaled,*result[1:])
        def mlp_forward(*args,**kwargs):
            result=original_mlp(*args,**kwargs)
            if result.dtype!=torch.float32:raise RuntimeError('MLP branch not FP32 before overlay scale')
            scaled=result*(2.0**(-b))
            if events is not None:events.append(dict(kind='host_scale',op='down_proj',b=b,input_dtype=str(result.dtype),output_dtype=str(scaled.dtype),scale=2.0**(-b)))
            return scaled
        patch(attention,'forward',attention_forward);patch(mlp,'forward',mlp_forward)
        yield
    finally:
        for module,name,existed,value in reversed(saved):
            if existed:setattr(module,name,value)
            else:delattr(module,name)
        v5.grouped_linear_s24=original_grouped
        if hasattr(v5,'_r009_exit_overlay_active'):delattr(v5,'_r009_exit_overlay_active')
        if interface_signature(model)!=before:raise RuntimeError('R009 interface attributes/bindings not restored')
