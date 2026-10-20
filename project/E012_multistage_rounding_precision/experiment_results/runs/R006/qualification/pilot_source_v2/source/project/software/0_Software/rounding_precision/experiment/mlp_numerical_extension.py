"""Read-only MLP measurements alongside the frozen ScaleCode numerical paths.

Construct before installing dynamic frontend traces.  Actual paths are only
observed; a same-input whole-MLP reference calls captured original frontends and
the independent exact Linear backend directly, bypassing existing observers.
No CUDA work starts at import.  Full raw tensors are never retained as evidence.
"""
from __future__ import annotations

from contextlib import contextmanager
from functools import wraps
import hashlib
import json
import math

PER_ARM_OPS = {
    'silu_lookup': 'reconstructed_same_lut_lookup_semantics',
    'gating_multiply_total': 'actual_common_exit_vs_exact_same_lut_product',
    'gating_multiply_extra': 'actual_vs_independent_common_exit_product',
    'down_host_total': 'actual_host_vs_exact_down_integer',
}
CURRENT_OPS = {
    'whole_mlp_local': 'same_mlp_input_current_vs_reference_branch',
    'mlp_fixed_residual_local': 'same_residual_base_current_vs_reference_mlp',
}
PAIRED_OPS = {
    'mlp_branch_propagation': 'free_current_vs_reference_mlp_branch',
    'mlp_residual_input_propagation': 'free_current_vs_reference_second_residual_base',
    'mlp_residual_sum_propagation': 'free_current_vs_reference_second_residual_sum',
}


def row_coordinate(row):
    return row['layer'], row['op'], row['arm']


def expected_coordinates(layers=32):
    return {(layer, op, arm) for layer in range(layers)
            for arm, ops in [('current', PER_ARM_OPS), ('reference', PER_ARM_OPS),
                             ('current', CURRENT_OPS), ('paired', PAIRED_OPS)] for op in ops}


def _sample_indices(size, count, seed):
    if not size or not count:
        return []
    chosen = {0, size - 1} if count > 1 else {0}
    counter = 0
    while len(chosen) < min(size, count):
        chosen.add(int.from_bytes(hashlib.sha256((seed + ':' + str(counter)).encode()).digest()[:8], 'big') % size)
        counter += 1
    return sorted(chosen)


def _signed24(value):
    import torch
    return torch.where((value > (1 << 23) - 1) & (value <= (1 << 24) - 1), value - (1 << 24), value)


def _round_product(numerator):
    """Independent integer half-away, returning the S32/F16 output *code*."""
    import torch
    magnitude = (numerator.abs() + (1 << 15)) >> 16
    return torch.where(numerator < 0, -magnitude, magnitude)


class MLPNumericalObserver:
    def __init__(self, v5, model, *, backend=None, sink=None, audit_doc_ids=(),
                 samples_per_layer=16, expected_layers=32, chunk_elements=1 << 20):
        import torch
        if backend is None:
            from numerical_reference import gpu_reference
            backend = gpu_reference
        if not 0 <= samples_per_layer <= 64 or not 1 <= chunk_elements <= 1 << 20:
            raise ValueError('bounded sample/chunk budget required')
        base = getattr(model, 'model', model)
        self.layers = list(base.layers)
        if len(self.layers) != expected_layers:
            raise ValueError('MLP extension requires the declared complete decoder layer set')
        self.v5, self.backend, self.sink = v5, backend, sink
        self.audit_doc_ids = set(audit_doc_ids)
        self.samples_per_layer, self.chunk_elements = samples_per_layer, chunk_elements
        # Capture before runner installs any dynamic frontend wrapper.
        self._prepare = v5.prepare_fixed_activation
        self._fp_raw = v5.fp_to_fixed_raw
        self._swiglu = v5._swiglu_s32
        self._active = False
        self.doc_id = self.arm = None
        self._stats, self._metadata, self._samples = {}, {}, {}
        self._pair_samples = {}
        self._live, self._current = {}, {}
        self._actual_seen = set()
        self._failures = []
        self._shadow_audits, self._linear_counters = {}, {}
        self._weight_ranges, self._lut = {}, {}
        self._down_layers = {}
        for layer_id, layer in enumerate(self.layers):
            mlp = layer.mlp
            if mlp.layer_idx != layer_id or mlp.output_dtype is not None:
                raise ValueError('expected indexed V5 MLP with FP32 Host output')
            for projection in (mlp.gate_proj, mlp.up_proj, mlp.down_proj):
                expected = (32, 35, 32) if projection.op_name == 'down_proj' else (24, 27, 24)
                if (projection.input_width, projection.hadamard_width, projection.output_width) != expected:
                    raise ValueError('MLP extension requires format05 widths')
                if not projection.strict_total_shift or projection.software_extended:
                    raise ValueError('MLP extension requires strict production format')
                if projection.op_name == 'down_proj' and not projection.down_shift12_candidate:
                    raise ValueError('MLP extension requires Down05 shift12')
                code, shift = projection.weight_codes_u8, projection.weight_shifts_u8.to(torch.int64)
                self._weight_ranges[id(projection)] = (
                    torch.where(code != 0, shift, 127).amin(0),
                    torch.where(code != 0, shift, -127).amax(0))
            self._down_layers[id(mlp.down_proj)] = layer_id
            table = mlp.silu_lut_s24.detach().cpu().numpy().copy()
            self._lut[layer_id] = dict(dtype=str(mlp.silu_lut_s24.dtype), shape=list(table.shape),
                                       sha256=hashlib.sha256(table.tobytes()).hexdigest(), values=table.tolist())

    def expected_coordinates(self):
        return expected_coordinates(len(self.layers))

    def set_context(self, *, doc_id, arm):
        if not isinstance(doc_id, str) or not doc_id or arm not in ('current', 'reference'):
            raise ValueError('nonempty doc_id and current/reference arm required')
        if self._live:
            raise RuntimeError('previous decoder layer has not completed')
        if self.doc_id is not None and doc_id != self.doc_id and (self._stats or self._current):
            raise RuntimeError('flush previous document before switching')
        if arm == 'reference' and not self._current:
            raise RuntimeError('current arm must precede reference')
        self.doc_id, self.arm = doc_id, arm
        return self

    def _key(self, layer, op, arm=None):
        if self.doc_id is None or self.arm is None:
            raise RuntimeError('set_context before forward')
        return self.doc_id, layer, op, arm or self.arm

    def _reduce(self, key, current, reference):
        import torch
        if current.shape != reference.shape or not current.numel():
            raise ValueError('nonempty matched MLP output geometry required')
        lhs, rhs = current.to(torch.float64), reference.to(torch.float64)
        finite = torch.isfinite(lhs) & torch.isfinite(rhs)
        diff = torch.where(finite, lhs - rhs, 0.)
        ref = torch.where(finite, rhs, 0.)
        reduction = torch.stack((ref.square().sum(), diff.square().sum(), diff.sum(), diff.abs().amax(),
                                 (~finite).sum().to(torch.float64)))
        if key not in self._stats:
            self._stats[key] = [current.numel(), reduction]
        else:
            previous = self._stats[key][1]
            combined = previous + reduction
            combined[3] = torch.maximum(previous[3], reduction[3])
            self._stats[key][0] += current.numel()
            self._stats[key][1] = combined

    def _shadow_audit(self, layer):
        audit = self._shadow_audits.get(layer)
        if audit is None:
            original = self.layers[layer].mlp.audit
            audit = self._shadow_audits[layer] = type(original)(original.device)
        for value in audit.values.values():
            value.zero_()
        audit.activation_elements.zero_()
        return audit

    def _capture_pair_samples(self, key, current, reference, **extra):
        if self.doc_id not in self.audit_doc_ids:
            return
        import torch
        indices = _sample_indices(current.numel(), self.samples_per_layer, ':'.join(map(str, key)))
        ix = torch.tensor(indices, dtype=torch.int64, device=current.device)
        self._pair_samples[key] = dict(indices=indices, current=current.reshape(-1)[ix].detach(),
                                       reference=reference.reshape(-1)[ix].detach(),
                                       **{name: value.reshape(-1)[ix].detach() for name, value in extra.items()})

    def _reference_linear(self, module, activation):
        import torch
        lower = 12 if module.op_name == 'down_proj' else 20
        acc, guard = (54, 45) if lower == 12 else (44, 37)
        minimum, maximum = self._weight_ranges[id(module)]
        active = activation.codes_u8 != 0
        shift = activation.shifts_u8.to(torch.int64)
        invalid = active & (minimum[None, :] != 127) & ((shift + minimum[None, :] < lower) | (shift + maximum[None, :] > 44))
        if bool(invalid.any().item()):
            raise ValueError('same-input MLP reference produced production-invalid active total shift')
        counters = self._linear_counters.get(id(module))
        if counters is None:
            counters = self._linear_counters[id(module)] = [torch.zeros((), dtype=torch.int64, device=module.weight_s8.device) for _ in range(5)]
        for counter in counters:
            counter.zero_()
        return self.backend.grouped_linear_exact(
            activation, module.weight_s8, module.weight_codes_u8, module.weight_shifts_u8,
            lower, 44, acc, acc, guard, True, lower == 20, *counters,
            output_min=-(1 << (module.output_width - 1)), output_max=(1 << (module.output_width - 1)) - 1)

    def _reference_branch(self, layer, source):
        """No production module forward/project calls, so no outer trace events."""
        import torch
        mlp = self.layers[layer].mlp
        audit = self._shadow_audit(layer)
        raw = self._fp_raw(source, mlp.gate_proj.input_width, audit)
        prepared = self._prepare(raw, input_width=24, hadamard_width=27, audit=audit)
        gate = self._reference_linear(mlp.gate_proj, prepared)
        up = self._reference_linear(mlp.up_proj, prepared)
        product = self._swiglu(gate, up, mlp.silu_lut_s24, audit, layer)
        down = self._prepare(product.to(torch.int64), input_width=32, hadamard_width=35, audit=audit)
        result = self._reference_linear(mlp.down_proj, down)
        return result.to(torch.float32) / 65536

    def _capture_product(self, gate, up, table, actual, layer):
        import torch
        if type(layer) is not int or not 0 <= layer < len(self.layers):
            raise ValueError('actual SwiGLU call needs a declared layer index')
        if gate.shape != up.shape or actual.shape != gate.shape:
            raise ValueError('SwiGLU capture geometry mismatch')
        flat_gate, flat_up, flat_actual = gate.reshape(-1), up.reshape(-1), actual.reshape(-1)
        key = self._key(layer, 'silu_lookup')
        meta = dict(input_dtype=str(gate.dtype), up_dtype=str(up.dtype), output_dtype=str(actual.dtype),
                    output_shape=list(actual.shape), input_fractional_bits=16, product_fractional_bits=16,
                    exact_product_denominator_bits=32, common_exit='S32/F16 half-away; overflow rejects, no saturation',
                    intermediate_observation='SiLU reconstructed from actual _swiglu_s32 arguments and frozen lookup rules; not an independently captured internal tensor',
                    lookup_function='same quantized LUT and rounded address; x<=-16 ->0; x>=16 ->x',
                    approximation_loss='analytic SiLU approximation is outside this arithmetic comparison; not inferred zero',
                    lut_identity={k: v for k, v in self._lut[layer].items() if k != 'values'},
                    raw_sample_scope='predeclared audit documents only', selection='boundary plus deterministic SHA256; not selected by error')
        self._metadata[key] = meta
        semantics_counts = torch.zeros(6, dtype=torch.int64, device=actual.device)
        max_address_displacement = torch.zeros((), dtype=torch.int64, device=actual.device)
        for start in range(0, flat_gate.numel(), self.chunk_elements):
            end = min(start + self.chunk_elements, flat_gate.numel())
            original_gate, original_up = flat_gate[start:end].to(torch.int64), flat_up[start:end].to(torch.int64)
            g, u = _signed24(original_gate), _signed24(original_up)
            address = ((g + (16 << 16) + 128) >> 8).clamp(0, 8192)
            silu = torch.where(g <= -(16 << 16), 0, torch.where(g >= 16 << 16, g, table[address].to(torch.int64)))
            numerator = silu * u
            independently_rounded = _round_product(numerator)
            real_actual = flat_actual[start:end].to(torch.float64) / 65536
            self._reduce(key, silu.to(torch.float64) / 65536, silu.to(torch.float64) / 65536)
            self._reduce(self._key(layer, 'gating_multiply_total'), real_actual, numerator.to(torch.float64) / (1 << 32))
            self._reduce(self._key(layer, 'gating_multiply_extra'), real_actual, independently_rounded.to(torch.float64) / 65536)
            interior = (g > -(16 << 16)) & (g < 16 << 16)
            grid = address * 256 - (16 << 16)
            max_address_displacement = torch.maximum(max_address_displacement, torch.where(interior, (grid - g).abs(), 0).amax())
            semantics_counts += torch.stack(((g <= -(16 << 16)).sum(), (g >= 16 << 16).sum(), interior.sum(),
                                              (g != original_gate).sum() + (u != original_up).sum(),
                                              ((independently_rounded < -(1 << 31)) | (independently_rounded > (1 << 31) - 1)).sum(),
                                              (flat_actual[start:end].to(torch.int64) != independently_rounded).sum()))
        self._metadata[key]['_semantic_counts'] = semantics_counts
        self._metadata[key]['_max_address_displacement'] = max_address_displacement
        if self.doc_id in self.audit_doc_ids:
            indices = _sample_indices(flat_gate.numel(), self.samples_per_layer, f'{self.doc_id}:{layer}:{self.arm}')
            ix = torch.tensor(indices, dtype=torch.int64, device=actual.device)
            g0, u0 = flat_gate[ix].to(torch.int64), flat_up[ix].to(torch.int64)
            g, u = _signed24(g0), _signed24(u0)
            address = ((g + (16 << 16) + 128) >> 8).clamp(0, 8192)
            silu = torch.where(g <= -(16 << 16), 0, torch.where(g >= 16 << 16, g, table[address].to(torch.int64)))
            self._samples[key] = (indices, torch.stack((g0, g, u0, u, address, silu, flat_actual[ix].to(torch.int64), silu * u), dim=1))

    def _norm_pre(self, layer, arguments):
        key = self.arm, layer
        identity = self.doc_id, layer, self.arm
        if identity in self._actual_seen:
            raise RuntimeError('duplicate actual MLP layer/arm call')
        self._actual_seen.add(identity)
        if key in self._live:
            raise RuntimeError('duplicate second-residual base capture')
        self._live[key] = dict(residual=arguments[0].detach())

    def _mlp_pre(self, layer, arguments):
        self._live[self.arm, layer]['input'] = arguments[0].detach()

    def _mlp_post(self, layer, result):
        import torch
        live = self._live[self.arm, layer]
        if result.dtype != torch.float32 or 'down_raw' not in live:
            raise ValueError('MLP output must have captured Down integer and FP32 Host boundary')
        live['branch'] = result.detach()
        host_key = self._key(layer, 'down_host_total')
        exact_down = live['down_raw'].to(torch.float64) / 65536
        self._reduce(host_key, result, exact_down)
        self._capture_pair_samples(host_key, result, exact_down, down_raw_int32=live['down_raw'])
        reconstructed = live['down_raw'].to(torch.float32) / 65536
        self._failures.append(('Host output reconstruction', (result != reconstructed).sum()))
        if self.arm == 'current':
            live['local_reference'] = self._reference_branch(layer, live['input'])
            whole_key = self._key(layer, 'whole_mlp_local')
            self._reduce(whole_key, result, live['local_reference'])
            self._capture_pair_samples(whole_key, result, live['local_reference'])

    def _layer_post(self, layer, result):
        value = result[0] if isinstance(result, (tuple, list)) else result
        live = self._live.pop((self.arm, layer))
        r, branch = live['residual'], live['branch']
        self._failures.append(('second residual reconstruction', (value != r + branch).sum()))
        if self.arm == 'current':
            same_base_reference = r + live['local_reference']
            fixed_key = self._key(layer, 'mlp_fixed_residual_local')
            self._reduce(fixed_key, value, same_base_reference)
            self._capture_pair_samples(fixed_key, value, same_base_reference, residual_base=r,
                                       current_branch=branch, reference_branch=live['local_reference'])
            self._current[layer] = (r.detach(), branch.detach(), value.detach())
        else:
            old_r, old_branch, old_sum = self._current.pop(layer)
            for op, current, reference in [('mlp_branch_propagation', old_branch, branch),
                                            ('mlp_residual_input_propagation', old_r, r),
                                            ('mlp_residual_sum_propagation', old_sum, value)]:
                self._reduce(self._key(layer, op, 'paired'), current, reference)
                self._capture_pair_samples(self._key(layer, op, 'paired'), current, reference)
            import torch
            residual_error = old_r.to(torch.float64) - r.to(torch.float64)
            branch_error = old_branch.to(torch.float64) - branch.to(torch.float64)
            self._metadata[self._key(layer, 'mlp_residual_sum_propagation', 'paired')] = {
                '_residual_branch_error_inner_product': (residual_error * branch_error).sum(),
                'decomposition_note': 'saved residual and branch errors; FP32 addition rounding means their real sum need not equal actual sum error exactly'}

    @contextmanager
    def context(self):
        """May be re-entered between arms; cross-arm data remains until flush."""
        marker = '_m005_mlp_extension_active'
        if self._active or getattr(self.v5, marker, False):
            raise RuntimeError('MLP extension contexts may not nest')
        original_swiglu = self.v5._swiglu_s32
        cls = self.v5.V5ProductionLinear
        original_project = cls.project_prepared
        observer, handles = self, []
        @wraps(original_swiglu)
        def swiglu(gate_s24, up_s24, table, audit, layer_idx=None):
            result = original_swiglu(gate_s24, up_s24, table, audit, layer_idx)
            observer._capture_product(gate_s24, up_s24, table, result, layer_idx)
            return result
        @wraps(original_project)
        def project(module, *args, **kwargs):
            result = original_project(module, *args, **kwargs)
            layer = observer._down_layers.get(id(module))
            if layer is not None:
                observer._live[observer.arm, layer]['down_raw'] = result.detach()
            return result
        try:
            self._active = True
            setattr(self.v5, marker, True)
            self.v5._swiglu_s32, cls.project_prepared = swiglu, project
            for layer_id, layer in enumerate(self.layers):
                handles.append(layer.post_attention_layernorm.register_forward_pre_hook(
                    lambda module, args, index=layer_id: observer._norm_pre(index, args)))
                handles.append(layer.mlp.register_forward_pre_hook(
                    lambda module, args, index=layer_id: observer._mlp_pre(index, args)))
                handles.append(layer.mlp.register_forward_hook(
                    lambda module, args, result, index=layer_id: observer._mlp_post(index, result)))
                handles.append(layer.register_forward_hook(
                    lambda module, args, result, index=layer_id: observer._layer_post(index, result)))
            yield self
        finally:
            self.v5._swiglu_s32, cls.project_prepared = original_swiglu, original_project
            for handle in handles:
                handle.remove()
            self._active = False
            if hasattr(self.v5, marker):
                delattr(self.v5, marker)

    def flush(self, doc_id):
        if doc_id != self.doc_id or self._live or self._current:
            raise RuntimeError('both complete arms required before flush')
        selected = {row_coordinate(dict(layer=k[1], op=k[2], arm=k[3])) for k in self._stats if k[0] == doc_id}
        if selected != self.expected_coordinates():
            raise ValueError('incomplete or unexpected MLP measurement coverage')
        for message, count in self._failures:
            if int(count.detach().cpu().item()):
                raise ValueError(message + ' mismatch')
        records = []
        for key in sorted(self._stats):
            doc, layer, op, arm = key
            n, reduction = self._stats[key]
            signal, error, signed, maximum, nonfinite = reduction.detach().cpu().tolist()
            nonfinite = int(nonfinite)
            valid = n - nonfinite
            invalid = nonfinite != 0
            metrics = dict(total_elements=n, valid_elements=valid, excluded_elements=nonfinite, nonfinite_elements=nonfinite,
                           signal_energy=None if invalid else signal, error_energy=None if invalid else error,
                           signed_error_sum=None if invalid else signed, absolute_max=None if invalid else maximum,
                           relative_l2_percent=100 * math.sqrt(error / signal) if not invalid and signal > 0 else None,
                           normalized_signed_bias_percent=100 * (signed / n) / math.sqrt(signal / n) if not invalid and signal > 0 else None,
                           signal_rms=math.sqrt(signal / n) if not invalid else None,
                           absolute_rmse=math.sqrt(error / n) if not invalid else None,
                           zero_signal=signal == 0 and not invalid, empty_valid_domain=valid == 0)
            metadata = dict(self._metadata.get(key, {}))
            if key in self._pair_samples:
                sample = self._pair_samples[key]
                indices = sample['indices']
                values = {name: tensor.detach().cpu().tolist() for name, tensor in sample.items() if name != 'indices'}
                metadata['raw_samples'] = [dict(flat_index=index, **{name: field[j] for name, field in values.items()})
                                           for j, index in enumerate(indices)]
                metadata['raw_scope'] = ('integer and Host conversion values sufficient for independent conversion check' if op == 'down_host_total' else
                                         'paired output spots only; not complete whole-branch inputs/weights for independent branch re-execution')
            if op == 'silu_lookup':
                counts = metadata.pop('_semantic_counts').detach().cpu().tolist()
                metadata['counts'] = dict(zip(('negative_outer_branch', 'positive_outer_branch', 'interior_lookup',
                                               'normalized_zero_extended_payloads', 'product_s32_overflow', 'product_common_exit_mismatch'), counts))
                metadata['max_interior_address_displacement_q16_code'] = int(metadata.pop('_max_address_displacement').detach().cpu().item())
                if metadata['counts']['product_common_exit_mismatch'] or metadata['counts']['product_s32_overflow']:
                    raise ValueError('actual SwiGLU common-exit semantics mismatch/overflow')
                metadata['raw_samples'] = []
                if key in self._samples:
                    indices, samples = self._samples[key]
                    names = ('gate_input_raw', 'gate_s24', 'up_input_raw', 'up_s24', 'lut_address', 'silu_s24', 'product_s32_actual', 'exact_product_numerator')
                    for index, sample in zip(indices, samples.detach().cpu().tolist()):
                        point = dict(zip(names, sample))
                        point.update(flat_index=index, exact_product_numerator=str(point['exact_product_numerator']),
                                     exact_product_denominator_bits=32)
                        metadata['raw_samples'].append(point)
                    # Store full small LUT once per actual arm/layer, only on audit documents.
                    if arm == 'current':
                        metadata['lut_values_s24'] = self._lut[layer]['values']
                    else:
                        metadata['lut_values_record'] = dict(doc_id=doc, layer=layer, arm='current', op='silu_lookup')
            if '_residual_branch_error_inner_product' in metadata:
                metadata['residual_branch_error_inner_product'] = float(metadata.pop('_residual_branch_error_inner_product').detach().cpu().item())
            comparison = (PER_ARM_OPS | CURRENT_OPS | PAIRED_OPS)[op]
            row = dict(doc_id=doc, layer=layer, node='mlp_extension', op=op, arm=arm, comparison=comparison,
                       trajectory='same_input_local_shadow' if op in CURRENT_OPS else ('v5_free_paired' if arm == 'paired' else 'actual_arm_input'),
                       metrics=metrics, metadata=metadata,
                       qualifiers=dict(denominator='all_accepted_real_coordinates', strict_per_output_domain=False,
                                       shared_rule_zero_is_not_total_loss_zero=True,
                                       total_loss_reference='exact same-LUT integer product' if op == 'gating_multiply_total' else
                                       ('exact down integer before Host conversion' if op == 'down_host_total' else None),
                                       silu_analytic_approximation_not_evaluated=op == 'silu_lookup',
                                       semantics_only_not_total_function_approximation=op == 'silu_lookup',
                                       absolute_error_bound_real=2 ** -17 if op == 'gating_multiply_total' else (0. if op == 'gating_multiply_extra' else None),
                                       bound_conditions='same LUT result and up code; valid S24 inputs; S32 product exit without overflow' if op.startswith('gating_') else None,
                                       common_exit_saturation='SwiGLU rejects S32 overflow, no clamp' if op.startswith('gating_') else None))
            records.append(row)
        raw_bytes = sum(len(json.dumps(row['metadata'], separators=(',', ':'), ensure_ascii=False).encode())
                        for row in records)
        if doc_id in self.audit_doc_ids and raw_bytes > 8 << 20:
            raise ValueError('MLP audit raw metadata exceeds8MiB/document')
        for row in records:
            row['qualifiers']['mlp_audit_raw_metadata_bytes_per_document'] = raw_bytes
        if self.sink is not None:
            for row in records:
                self.sink(row)
        self._stats.clear()
        self._metadata.clear()
        self._samples.clear()
        self._pair_samples.clear()
        self._failures.clear()
        self._actual_seen.clear()
        return records
