"""CPU observer qualification; real V5 frontend/SwiGLU/Host, CPU Linear adapter."""
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import torch
from torch import nn

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiment'))
from mlp_numerical_extension import MLPNumericalObserver, expected_coordinates, row_coordinate, _round_product, _sample_indices
from numerical_reference.current_nodes import _v5
from numerical_reference import gpu_reference
from numerical_reference.local_observer import local_observer_context


def cpu_linear(activation, weight_s8, weight_codes_u8, weight_shifts_u8,
               shift_min, shift_max, hardware_accumulator_width, compute_accumulator_width,
               compute_group_guard_width, zero_invalid_guard, audit_hardware_group_guard,
               saturation_count, group_guard_overflow_count, software_group_guard_overflow_count,
               accumulator_overflow_count, software_accumulator_overflow_count,
               output_min=-(1 << 23), output_max=(1 << 23) - 1, *, exact=False):
    """Bounded test-only integer/Fraction adapter; no Triton/GPU claim."""
    output = torch.empty((activation.rows, weight_s8.shape[0]), dtype=torch.int32)
    for row in range(activation.rows):
        for col in range(weight_s8.shape[0]):
            total = Fraction(0) if exact else 0
            for group in range(activation.groups):
                qa = activation.values_u8[row, group].to(torch.int64) - activation.zero_points_u8[row, group]
                dot = int((qa * weight_s8[col, group].to(torch.int64)).sum())
                code = int(activation.codes_u8[row, group]) * int(weight_codes_u8[col, group])
                raw = dot * code
                shift = int(activation.shifts_u8[row, group]) + int(weight_shifts_u8[col, group])
                if code and not shift_min <= shift <= shift_max:
                    raise ValueError('test active shift invalid')
                if exact:
                    total += Fraction(raw, 1 << (shift - 16)) if shift >= 16 else raw * (1 << (16 - shift))
                else:
                    delta = shift - 24
                    total += raw >> delta if delta >= 0 else raw << -delta
                    minimum = -(1 << (compute_accumulator_width - 1))
                    total = ((total - minimum) & ((1 << compute_accumulator_width) - 1)) + minimum
            if exact:
                magnitude = abs(total)
                rounded = (2 * magnitude.numerator + magnitude.denominator) // (2 * magnitude.denominator)
                rounded = -rounded if total < 0 else rounded
            else:
                rounded = (abs(total) + 128) >> 8
                rounded = -rounded if total < 0 else rounded
            clipped = min(max(rounded, output_min), output_max)
            saturation_count.add_(rounded != clipped)
            output[row, col] = clipped
    return output.reshape(*activation.leading_shape, weight_s8.shape[0])


def cpu_exact(*args, **kwargs):
    kwargs.pop('exact', None)
    return cpu_linear(*args, **kwargs, exact=True)


def backend():
    return SimpleNamespace(grouped_linear_exact=cpu_exact, rope_exact=gpu_reference.rope_exact,
                           qk_exact=gpu_reference.qk_exact, softmax_exact=gpu_reference.softmax_exact,
                           pv_exact=gpu_reference.pv_exact)


def make_model(v5, count=2):
    audit = v5.V5Audit(torch.device('cpu'))
    class Layer(nn.Module):
        def __init__(self, layer):
            super().__init__()
            projections = []
            for ordinal, op in enumerate(('gate_proj', 'up_proj', 'down_proj')):
                weight = ((np.arange(32 * 32).reshape(32, 1, 32) + ordinal + layer) % 13 - 6).astype(np.int8)
                projections.append(v5.V5ProductionLinear(
                    module_name=f'model.layers.{layer}.mlp.{op}', op_name=op,
                    weight_s8=weight, weight_codes_u8=np.full((32, 1), 100, np.uint8),
                    weight_shifts_u8=np.full((32, 1), 16, np.uint8),
                    input_width=32 if op == 'down_proj' else 24,
                    hadamard_width=35 if op == 'down_proj' else 27,
                    output_width=32 if op == 'down_proj' else 24, device=torch.device('cpu'), audit=audit,
                    down_shift12_candidate=True))
            self.mlp = v5.V5MLP(*projections, torch.device('cpu'), audit, layer_idx=layer)
            original = SimpleNamespace(variance_epsilon=1e-5, weight=torch.linspace(.8, 1.2, 32))
            self.post_attention_layernorm = v5.HostFP32RMSNorm(original, torch.device('cpu'))
        def forward(self, value):
            residual = value + .001 * torch.sin(value)
            return residual + self.mlp(self.post_attention_layernorm(residual))
    class Model(nn.Module):
        def __init__(self):
            super().__init__()
            self.layers = nn.ModuleList([Layer(i) for i in range(count)])
        def forward(self, value):
            for layer in self.layers:
                value = layer(value)
            return value
    return Model(), audit


def reset(audit):
    for value in audit.values.values():
        value.zero_()
    for values in audit.linear_values.values():
        for name, value in values.items():
            value.fill_(127 if name == 'linear_total_shift_min' else -1 if name == 'linear_total_shift_max' else 0)
    audit.activation_elements.zero_()


class MLPObserverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        cls.v5 = _v5()

    def test_exact_integer_product_negative_ties_and_boundaries(self):
        values = [-2**46 + 1, -98304, -65537, -32769, -32768, -32767, -1, 0, 1, 32767, 32768, 32769, 65537, 98304, 2**46 - 1]
        actual = _round_product(torch.tensor(values, dtype=torch.int64)).tolist()
        for raw, code in zip(values, actual):
            exact = Fraction(raw, 65536)
            magnitude = abs(exact)
            gold = (2 * magnitude.numerator + magnitude.denominator) // (2 * magnitude.denominator)
            self.assertEqual(code, -gold if raw < 0 else gold)
            self.assertLessEqual(abs(Fraction(code, 65536) - Fraction(raw, 2**32)), Fraction(1, 2**17))

    def test_native_v5_on_off_full_audit_dynamic_noninterference_and_raw(self):
        v5 = self.v5
        model, audit = make_model(v5)
        source = torch.linspace(-.14, .17, 64).reshape(1, 2, 32)
        input_copy = source.clone()
        original_prepare, original_swiglu = v5.prepare_fixed_activation, v5._swiglu_s32
        original_project = v5.V5ProductionLinear.project_prepared
        original_state = {key: value.clone() for key, value in model.state_dict().items()}
        results, audits, local_records, event_counts = {}, {}, {}, {}
        with patch.object(v5, 'grouped_linear_s24', cpu_linear), patch.object(gpu_reference, 'grouped_linear_exact', cpu_exact):
            observer = MLPNumericalObserver(v5, model, backend=backend(), audit_doc_ids=['audit'], expected_layers=2,
                                            samples_per_layer=16, chunk_elements=17)
            for observed in (False, True):
                counts = []
                def traced(*args, **kwargs):
                    counts.append(1)
                    return original_prepare(*args, **kwargs)
                with patch.object(v5, 'prepare_fixed_activation', traced):
                    for arm in ('current', 'reference'):
                        reset(audit)
                        records = []
                        if observed:
                            observer.set_context(doc_id='audit', arm=arm)
                        if arm == 'current':
                            with local_observer_context(v5, backend=backend(), sink=records.append, doc_id='audit', layer=0) as old:
                                if observed:
                                    with observer.context():
                                        result = model(source)
                                else:
                                    result = model(source)
                                old.flush()
                        else:
                            with gpu_reference.arithmetic_context(v5):
                                if observed:
                                    with observer.context():
                                        result = model(source)
                                else:
                                    result = model(source)
                        results[observed, arm] = result.detach().clone()
                        audits[observed, arm] = dict(counters=audit.collect(), linear=audit.collect_linear())
                        local_records[observed, arm] = records
                event_counts[observed] = len(counts)
            rows = observer.flush('audit')
        self.assertEqual(len(rows), 26)
        self.assertEqual({row_coordinate(row) for row in rows}, expected_coordinates(2))
        self.assertEqual(event_counts[False], event_counts[True])
        self.assertEqual(event_counts[True], 2 * 2 * 2)
        self.assertTrue(torch.equal(source, input_copy))
        self.assertEqual(v5.prepare_fixed_activation, original_prepare)
        self.assertEqual(v5._swiglu_s32, original_swiglu)
        self.assertEqual(v5.V5ProductionLinear.project_prepared, original_project)
        for arm in ('current', 'reference'):
            self.assertTrue(torch.equal(results[False, arm], results[True, arm]))
            self.assertEqual(audits[False, arm], audits[True, arm])
            self.assertEqual(local_records[False, arm], local_records[True, arm])
        for key, value in model.state_dict().items():
            self.assertTrue(torch.equal(value, original_state[key]))
        for row in rows:
            if row['op'] == 'gating_multiply_extra':
                self.assertEqual(row['metrics']['error_energy'], 0)
            if row['op'] == 'gating_multiply_total':
                self.assertLessEqual(row['metrics']['absolute_max'], 2**-17)
            if row['op'] == 'silu_lookup':
                meta = row['metadata']
                self.assertEqual(meta['counts']['product_common_exit_mismatch'], 0)
                self.assertEqual(meta['counts']['product_s32_overflow'], 0)
                self.assertEqual(len(meta['raw_samples']), 16)
                for point in meta['raw_samples']:
                    gate, up = point['gate_s24'], point['up_s24']
                    self.assertEqual(point['lut_address'], min(max((gate + (16 << 16) + 128) >> 8, 0), 8192))
                    self.assertEqual(int(point['exact_product_numerator']), point['silu_s24'] * up)
                self.assertLess(row['qualifiers']['mlp_audit_raw_metadata_bytes_per_document'], 8 << 20)
        json.dumps(rows, allow_nan=False)

    def test_actual_swiglu_extreme_and_packed_payload_semantics(self):
        v5 = self.v5
        model, _ = make_model(v5, 1)
        observer = MLPNumericalObserver(v5, model, backend=backend(), expected_layers=1,
                                        audit_doc_ids=['audit'], chunk_elements=3)
        observer.set_context(doc_id='audit', arm='current')
        raw = torch.tensor([-(16 << 16) - 1, -(16 << 16), -(16 << 16) + 1, -128, 0, 128,
                            (16 << 16) - 1, 16 << 16, (16 << 16) + 1, (1 << 24) - 1], dtype=torch.int32)
        up = torch.tensor([17, -19, 32768, -32768, 5, 32768, -32768, 32768, -32768, (1 << 24) - 1], dtype=torch.int32)
        table = model.layers[0].mlp.silu_lut_s24
        audit = v5.V5Audit(torch.device('cpu'))
        gate_copy, up_copy = raw.clone(), up.clone()
        actual = v5._swiglu_s32(raw, up, table, audit, 0)
        observer._capture_product(raw, up, table, actual, 0)
        self.assertTrue(torch.equal(raw, gate_copy));self.assertTrue(torch.equal(up, up_copy))
        meta = observer._metadata[observer._key(0, 'silu_lookup')]
        counts = meta['_semantic_counts'].tolist()
        self.assertEqual(counts[0], 2);self.assertEqual(counts[1], 2)
        self.assertEqual(counts[3], 2);self.assertEqual(counts[4:], [0, 0])

    def test_context_exception_restores_functions_and_hooks(self):
        v5 = self.v5
        model, _ = make_model(v5, 1)
        observer = MLPNumericalObserver(v5, model, backend=backend(), expected_layers=1)
        functions = v5._swiglu_s32, v5.V5ProductionLinear.project_prepared
        before = [(len(m._forward_hooks), len(m._forward_pre_hooks)) for m in model.modules()]
        with self.assertRaisesRegex(RuntimeError, 'injected'):
            with observer.context():
                raise RuntimeError('injected')
        self.assertEqual(functions, (v5._swiglu_s32, v5.V5ProductionLinear.project_prepared))
        self.assertEqual(before, [(len(m._forward_hooks), len(m._forward_pre_hooks)) for m in model.modules()])
        self.assertFalse(hasattr(v5, '_m005_mlp_extension_active'))

    def test_s32_host_loss_is_measured_despite_shared_exit(self):
        model, _ = make_model(self.v5, 1)
        observer = MLPNumericalObserver(self.v5, model, backend=backend(), expected_layers=1,
                                        audit_doc_ids=['audit'])
        observer.doc_id, observer.arm = 'audit', 'reference'
        raw = torch.tensor([2**24 + 1, 2**24 - 1, -2**24 - 1, 2**31 - 1, -2**31], dtype=torch.int32)
        output = raw.to(torch.float32) / 65536
        observer._live['reference', 0] = dict(down_raw=raw)
        observer._mlp_post(0, output)
        _, reduction = observer._stats[observer._key(0, 'down_host_total')]
        self.assertGreater(float(reduction[1]), 0.)
        self.assertEqual(float(reduction[3]), 1 / 65536)
        expected = [float(Fraction(int(code), 65536)) for code in raw]
        self.assertTrue(any(float(actual) != exact for actual, exact in zip(output, expected)))
        self.assertIn('down_raw_int32', observer._pair_samples[observer._key(0, 'down_host_total')])

    def test_missing_arm_rejected_and_deterministic_sampling(self):
        model, _ = make_model(self.v5, 1)
        observer = MLPNumericalObserver(self.v5, model, backend=backend(), expected_layers=1)
        with self.assertRaises(RuntimeError):observer.set_context(doc_id='x', arm='reference')
        with self.assertRaises(RuntimeError):observer.flush('x')
        chosen = _sample_indices(1000, 16, 'fixed')
        self.assertEqual(chosen, _sample_indices(1000, 16, 'fixed'))
        self.assertEqual(len(set(chosen)), 16)
        self.assertEqual((chosen[0], chosen[-1]), (0, 999))
        self.assertEqual(len(expected_coordinates()), 416)


if __name__ == '__main__':
    unittest.main()
