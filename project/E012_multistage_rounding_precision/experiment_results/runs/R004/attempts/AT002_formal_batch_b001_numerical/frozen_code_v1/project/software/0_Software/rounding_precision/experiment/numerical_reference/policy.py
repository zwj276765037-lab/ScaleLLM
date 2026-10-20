"""NumPy-only public contract for matched ScaleCode arithmetic comparisons."""
from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib
import numpy as np

PROFILES = {
    'attention': dict(shift_min=26, shift_max=47, guard_width=42, accumulator_width=42, output_width=24, dot_max=1036320),
    'mlp_gate_up': dict(shift_min=20, shift_max=44, guard_width=37, accumulator_width=44, output_width=24, dot_max=65280),
    'mlp_down': dict(shift_min=12, shift_max=44, guard_width=45, accumulator_width=54, output_width=32, dot_max=65280),
}

@dataclass(frozen=True)
class ArithmeticPolicy:
    linear_group_floor: bool = False
    rope_product_round: bool = False
    qk_group_floor: bool = False
    softmax_interpolation_round: bool = False
    softmax_reciprocal_round: bool = False
    pv_term_floor: bool = False

    def __post_init__(self):
        if any(type(value) is not bool for value in asdict(self).values()):
            raise TypeError('arithmetic switches must be bool')

CURRENT = ArithmeticPolicy(True, True, True, True, True, True)
OUTPUT_ONLY = ArithmeticPolicy()


def integer_array(arrays, name):
    if name not in arrays:
        raise ValueError('missing array: ' + name)
    value = np.asarray(arrays[name])
    if value.dtype.kind not in 'iu':
        raise TypeError(name + ' must have an integer dtype, not bool/float/object')
    if value.dtype.kind == 'u' and value.size and np.max(value) > np.iinfo(np.int64).max:
        raise ValueError(name + ' exceeds signed int64')
    return value.astype(np.int64, copy=False)


def _broadcast(arrays, name, shape):
    try:
        return np.broadcast_to(integer_array(arrays, name), shape)
    except ValueError as error:
        raise ValueError(name + ' cannot broadcast to ' + str(shape)) from error


def _range(value, low, high):
    return (value >= low) & (value <= high)


def canonicalize(node, arrays, config):
    """Validate shape/types and sanitize only invalid records before int64 arithmetic.

    Invalid records retain false domain masks; their code arrays are diagnostics,
    never numerical evidence. Shared validation contains no rounding arithmetic.
    """
    if not isinstance(arrays, dict) or not isinstance(config, dict):
        raise TypeError('arrays and config must be dictionaries')
    out = {}
    if node in ('linear', 'qk'):
        dot = integer_array(arrays, 'dot')
        if dot.ndim != 2 or not dot.shape[0] or not 1 <= dot.shape[1] <= 4096:
            raise ValueError('dot must be nonempty [N,G], G<=4096')
        if node == 'qk' and dot.shape[1] != 4:
            raise ValueError('QK requires four groups')
        shape = dot.shape
        out['dot'] = dot
        names = ('act_code', 'act_shift', 'weight_code', 'weight_shift') if node == 'linear' else ('kv_code', 'kv_shift')
        for name in names:
            out[name] = _broadcast(arrays, name, shape)
        if node == 'linear':
            profile = config.get('profile')
            if not isinstance(profile, str) or profile not in PROFILES:
                raise ValueError('Linear requires a frozen profile')
            spec = PROFILES[profile]
            active = (out['act_code'] != 0) & (out['weight_code'] != 0)
            total = out['act_shift'] + out['weight_shift']
            good = _range(dot, -spec['dot_max'], spec['dot_max'])
            for name in ('act_code', 'weight_code'):
                good &= _range(out[name], 0, 255)
            for name in ('act_shift', 'weight_shift'):
                good &= _range(out[name], 0, 63)
            good &= ~active | _range(total, spec['shift_min'], spec['shift_max'])
            lane_names=('q_a','q_w','zero_point')
            present=[name in arrays for name in lane_names]
            if any(present) and not all(present):
                raise ValueError('Linear optional lanes need q_a/q_w/zero_point together')
            if all(present):
                qa=integer_array(arrays,'q_a');qw=integer_array(arrays,'q_w')
                zp=_broadcast(arrays,'zero_point',shape)
                if qa.shape!=shape+(32,) or qw.shape!=qa.shape:
                    raise ValueError('Linear q_a/q_w must be [N,G,32]')
                low_w,high_w=(-127,127) if profile=='attention' else (-8,7)
                lane_ok=_range(qa,0,255)&_range(qw,low_w,high_w)
                lane_ok &= _range(zp,0,255)[...,None]
                reconstructed=np.sum((np.where(lane_ok,qa,0)-np.where(_range(zp,0,255),zp,0)[...,None])*np.where(lane_ok,qw,0),axis=-1,dtype=np.int64)
                good &= np.all(lane_ok,axis=-1)&(reconstructed==dot)
        else:
            maximum = 32 * (1 << 23) * 2047
            good = _range(dot, -maximum, maximum) & _range(out['kv_code'], 0, 255)
            good &= _range(out['kv_shift'], 0, 63)
            good &= (out['kv_code'] == 0) | _range(out['kv_shift'], 8, 32)
            if ('query_s24' in arrays) != ('key_s12' in arrays):
                raise ValueError('optional QK lanes require query_s24 and key_s12 together')
            if 'query_s24' in arrays:
                query = integer_array(arrays, 'query_s24')
                key = integer_array(arrays, 'key_s12')
                if query.shape != shape + (32,) or key.shape != query.shape:
                    raise ValueError('QK lanes must be [N,4,32]')
                lanes_ok = _range(query, -(1 << 23), (1 << 23)-1) & _range(key, -2047, 2047)
                checked_dot = np.sum(np.where(lanes_ok, query, 0) * np.where(lanes_ok, key, 0), axis=-1, dtype=np.int64)
                good &= np.all(lanes_ok, axis=-1) & (checked_dot == dot)
        domain = np.all(good, axis=-1)
        for name in out:
            out[name] = np.where(domain[:, None], out[name], 0)
        output_shape = (shape[0],)
    elif node == 'rope':
        pair = integer_array(arrays, 'raw_pair')
        if pair.ndim != 2 or pair.shape[1] != 2 or not pair.shape[0]:
            raise ValueError('RoPE raw_pair must be [N,2]')
        out['raw_pair'] = pair
        for name in ('cos_q16', 'sin_q16'):
            out[name] = _broadcast(arrays, name, (pair.shape[0],))
        domain = np.all(_range(pair, -(1 << 23), (1 << 23)-1), axis=-1)
        domain &= _range(out['cos_q16'], -65536, 65536) & _range(out['sin_q16'], -65536, 65536)
        out['raw_pair'] = np.where(domain[:, None], pair, 0)
        for name in ('cos_q16', 'sin_q16'):
            out[name] = np.where(domain, out[name], 0)
        output_shape = pair.shape
        domain = np.broadcast_to(domain[:, None], output_shape)
    elif node == 'pv':
        base = integer_array(arrays, 'probability_u16')
        if base.ndim != 2 or not base.shape[0] or not 1 <= base.shape[1] <= 128:
            raise ValueError('PV probability_u16 must be [N,K], 1<=K<=128')
        for name in ('probability_u16', 'value_s12', 'kv_code', 'kv_shift'):
            out[name] = _broadcast(arrays, name, base.shape)
        good = _range(out['probability_u16'], 0, 65535) & _range(out['value_s12'], -2047, 2047)
        good &= _range(out['kv_code'], 0, 255) & _range(out['kv_shift'], 0, 63)
        good &= (out['kv_code'] == 0) | _range(out['kv_shift'], 8, 32)
        domain = np.all(good, axis=-1)
        for name in out:
            out[name] = np.where(domain[:, None], out[name], 0)
        output_shape = (base.shape[0],)
    elif node == 'softmax':
        score = integer_array(arrays, 'score_q14')
        valid = np.asarray(arrays.get('valid_mask'))
        lut = integer_array(arrays, 'lut_u17')
        if score.ndim != 2 or not score.shape[0] or not 1 <= score.shape[1] <= 128:
            raise ValueError('Softmax score_q14 must be [R,K],1<=K<=128')
        if valid.dtype != np.bool_:
            raise TypeError('Softmax valid_mask must be bool')
        valid = np.broadcast_to(valid, score.shape)
        if lut.shape != (257,) or not np.all(_range(lut, 0, 65536)) or lut[0] != 65536:
            raise ValueError('Softmax LUT must be 257 constrained U17 entries with lut[0]=65536')
        if np.any(lut[:-1] < lut[1:]):
            raise ValueError('Softmax LUT must be non-increasing')
        rows_ok = np.all(_range(score, -(16 << 14), 16 << 14), axis=-1)
        out = dict(score_q14=np.where(rows_ok[:, None], score, 0), valid_mask=valid, lut_u17=lut)
        output_shape = score.shape
        domain = np.broadcast_to(rows_ok[:, None], output_shape)
    elif node == 'swiglu':
        gate = integer_array(arrays, 'gate_s24')
        up = _broadcast(arrays, 'up_s24', gate.shape)
        lut = integer_array(arrays, 'lut_s24')
        if not gate.size or lut.shape != (8193,) or not np.all(_range(lut, -(1 << 23), (1 << 23)-1)):
            raise ValueError('SwiGLU needs nonempty inputs and S24 LUT[8193]')
        gate=np.where((gate>(1<<23)-1)&(gate<=(1<<24)-1),gate-(1<<24),gate)
        up=np.where((up>(1<<23)-1)&(up<=(1<<24)-1),up-(1<<24),up)
        domain = _range(gate, -(1 << 23), (1 << 23)-1) & _range(up, -(1 << 23), (1 << 23)-1)
        out = dict(gate_s24=np.where(domain, gate, 0), up_s24=np.where(domain, up, 0), lut_s24=lut)
        output_shape = gate.shape
    elif node in ('host', 'host_fp32'):
        raw = integer_array(arrays, 'raw_s32')
        if not raw.size:
            raise ValueError('Host input must be nonempty')
        width=config.get('input_width',32)
        if type(width) is not int or width not in (24,32):
            raise ValueError('Host input_width must be 24 or 32')
        domain = _range(raw, -(1 << (width-1)), (1 << (width-1))-1)
        out = dict(raw_s32=np.where(domain, raw, 0))
        output_shape = raw.shape
    else:
        raise ValueError('unknown numerical node: ' + str(node))
    if 'expected_lut_sha256' in config:
        name = 'lut_u17' if node == 'softmax' else 'lut_s24'
        if name not in out or hashlib.sha256(np.ascontiguousarray(out[name]).tobytes()).hexdigest() != config['expected_lut_sha256']:
            raise ValueError('frozen LUT identity mismatch')
    return out, np.broadcast_to(domain, output_shape).copy()


def evaluate_node(node: str, arrays: dict, config: dict | None = None) -> dict:
    """Return fixed current/output-only paths, exact values, masks and selected policy."""
    config = {} if config is None else dict(config)
    safe, domain = canonicalize(node, arrays, config)
    from .exact_reductions import evaluate_reference, selected_softmax_code
    from .current_nodes import evaluate_current
    reference = evaluate_reference(node, safe, config)
    current = evaluate_current(node, safe, config)
    code, reference_code = current['code'], reference['code']
    shape = code.shape
    zeros = np.zeros(shape, dtype=bool)
    saturation = current.get('saturation_mask', zeros) | reference.get('saturation_mask', zeros)
    overflow = current.get('overflow_mask', zeros) | reference.get('overflow_mask', zeros)
    padding = reference.get('software_padding_mask', zeros)
    accepted = domain & (~overflow if node=='swiglu' else np.ones(shape,dtype=bool))
    structural=np.ones(shape,dtype=bool)
    if node=='softmax':
        structural=safe['valid_mask'] & ~padding
    valid = domain & ~overflow & ~saturation & structural
    if node == 'softmax':
        valid &= safe['valid_mask']
    bound_applicable = valid & reference.get('bound_supported_mask', np.ones(shape, dtype=bool))
    bound_n = reference.get('bound_numerator', np.zeros(shape, dtype=np.int64))
    bound_d = reference.get('bound_denominator', np.ones(shape, dtype=np.int64))
    q, r, d = (reference['exact'][name] for name in ('quotient_floor', 'remainder', 'denominator'))
    # d<=2^50; current/exact comparison uses quotient/remainder to avoid a
    # potentially overflowing common numerator. Bounds are in output LSB.
    # Compare with Fraction only at threshold candidates; int64 cross-products
    # can exceed 63 bits in QK. Vector float is never the deciding oracle.
    from fractions import Fraction
    difference = code.astype(np.float64) - q.astype(np.float64) - r.astype(np.float64)/d
    candidates = bound_applicable & (np.abs(difference) >= bound_n/bound_d - 1e-9)
    violation = np.zeros(shape, dtype=bool)
    for flat_index in np.flatnonzero(candidates):
        index=np.unravel_index(flat_index,shape)
        err = abs(Fraction(int(code[index])-int(q[index])) - Fraction(int(r[index]),int(d[index])))
        violation[index] = err > Fraction(int(bound_n[index]),int(bound_d[index]))
    pair_n = reference.get('reference_bound_numerator', bound_n)
    pair_d = reference.get('reference_bound_denominator', bound_d)
    pair_violation = np.zeros(shape, dtype=bool)
    pair_candidates = bound_applicable & (np.abs(code-reference_code).astype(np.float64) >= pair_n/pair_d - 1e-9)
    for flat_index in np.flatnonzero(pair_candidates):
        index=np.unravel_index(flat_index,shape)
        pair_violation[index] = Fraction(abs(int(code[index])-int(reference_code[index]))) > Fraction(int(pair_n[index]),int(pair_d[index]))
    selection = config.get('policy', OUTPUT_ONLY)
    if isinstance(selection, dict):
        selection = ArithmeticPolicy(**selection)
    if not isinstance(selection, ArithmeticPolicy):
        raise TypeError('config.policy must be ArithmeticPolicy or a bool-field dictionary')
    switch = {'linear':'linear_group_floor', 'rope':'rope_product_round', 'qk':'qk_group_floor', 'pv':'pv_term_floor'}.get(node)
    selected = code.copy() if switch and getattr(selection, switch) else reference_code.copy()
    if node == 'softmax':
        selected = selected_softmax_code(safe, selection)
    metadata = dict(config.get('metadata', {}))
    metadata.update(bound_kind=('conservative_row_length' if node=='softmax' else 'deterministic'),output_shape=list(shape), policy=asdict(selection), fractional_bits=reference['exact']['fractional_bits'], bound_units='output_code_LSB', bound_comparisons=['current_vs_exact','current_vs_reference'])
    return dict(current_code=code, reference_code=reference_code, selected_code=selected,
                exact=reference['exact'], exact_unclipped=reference.get('exact_unclipped'),
                current_pre_clip_code=current.get('pre_clip_code',code), reference_pre_clip_code=reference.get('pre_clip_code',reference_code),
                valid_mask=valid, metric_mask=structural.copy(), domain_valid_mask=domain, accepted_mask=accepted,
                saturation_mask=saturation, overflow_mask=overflow,
                clip_mask=current.get('clip_mask',zeros) | reference.get('clip_mask',zeros),
                software_padding_mask=padding, bound_applicable_mask=bound_applicable,
                bound_violation_mask=violation, reference_bound_violation_mask=pair_violation,
                bound_numerator=bound_n, bound_denominator=bound_d,
                reference_bound_numerator=pair_n, reference_bound_denominator=pair_d,
                g_right=reference.get('g_right'), current_error_counts=current.get('error_counts',{}),
                source_identity=current.get('source_identity',{}), metadata=metadata)
