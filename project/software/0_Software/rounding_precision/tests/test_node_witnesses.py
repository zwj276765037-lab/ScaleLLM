from fractions import Fraction
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiment'))
from numerical_reference.node_witnesses import NodeWitnesses, deterministic_indices, extract_witness, load_witness
from numerical_reference.policy import evaluate_node


def half_away(value):
    sign = -1 if value < 0 else 1
    value = abs(value)
    return sign * ((2 * value.numerator + value.denominator) // (2 * value.denominator))


def linear_fixture(groups=5):
    rng = np.random.default_rng(20261019)
    rows, columns = 2, 3
    qa = torch.from_numpy(rng.integers(0, 256, (rows, groups, 32), dtype=np.uint8))
    qw = torch.from_numpy(rng.integers(-127, 128, (columns, groups, 32), dtype=np.int8))
    zp = torch.full((rows, groups), 123, dtype=torch.uint8)
    ac = torch.full((rows, groups), 71, dtype=torch.uint8)
    ash = torch.full((rows, groups), 20, dtype=torch.uint8)
    wc = torch.full((columns, groups), 93, dtype=torch.uint8)
    wsh = torch.full((columns, groups), 10, dtype=torch.uint8)
    activation = SimpleNamespace(values_u8=qa, zero_points_u8=zp, codes_u8=ac,
                                 shifts_u8=ash, rows=rows, groups=groups, leading_shape=(1, rows))
    args = dict(activation=activation, weight_s8=qw, weight_codes_u8=wc,
                weight_shifts_u8=wsh, shift_min=26, shift_max=47)
    # Construct the fixture through the frozen array API, not witness extraction.
    row = np.repeat(np.arange(rows), columns)
    col = np.tile(np.arange(columns), rows)
    a = dict(q_a=qa.numpy()[row], q_w=qw.numpy()[col], zero_point=zp.numpy()[row],
             act_code=ac.numpy()[row], act_shift=ash.numpy()[row],
             weight_code=wc.numpy()[col], weight_shift=wsh.numpy()[col])
    a['dot'] = np.sum((a['q_a'].astype(np.int64) - a['zero_point'][..., None]) * a['q_w'].astype(np.int64), axis=-1)
    result = evaluate_node('linear', a, {'profile': 'attention'})
    return args, torch.from_numpy(result['current_code']).reshape(1, rows, columns), torch.from_numpy(result['reference_code']).reshape(1, rows, columns)


class NodeWitnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_selection_reproducible_boundaries_and_seed(self):
        key = ('audit_doc', 15, 'linear', 'q_proj')
        a = deterministic_indices(10000, 16, seed=17, coordinate=key)
        self.assertEqual(len(a), 16)
        self.assertEqual((a[0], a[-1]), (0, 9999))
        np.testing.assert_array_equal(a, deterministic_indices(10000, 16, seed=17, coordinate=key))
        self.assertFalse(np.array_equal(a, deterministic_indices(10000, 16, seed=18, coordinate=key)))
        np.testing.assert_array_equal(deterministic_indices(3, 16), [0, 1, 2])
        self.assertEqual(deterministic_indices(0).size, 0)
        with self.assertRaises(ValueError): deterministic_indices(4, 0)

    def test_linear_all_lanes_dot_and_fraction_replay(self):
        args, current, reference = linear_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            collector = NodeWitnesses(temporary, ['audit'], samples_per_coordinate=4, seed=31)
            row = collector.record(('audit', 7, 'linear', 'q_proj'), 16, current, reference, args)
            self.assertEqual(row['status'], 'saved')
            witness = load_witness(temporary, row)
            arrays = witness['arrays']
            self.assertEqual(arrays['q_a'].shape, (4, 5, 32))
            dot = np.sum((arrays['q_a'].astype(np.int64) - arrays['zero_point'][..., None]) * arrays['q_w'].astype(np.int64), axis=-1)
            np.testing.assert_array_equal(dot, arrays['dot'])
            evaluated = evaluate_node(witness['node'], arrays, witness['config'])
            np.testing.assert_array_equal(evaluated['current_code'], witness['current_code'])
            np.testing.assert_array_equal(evaluated['reference_code'], witness['reference_code'])
            for i in range(4):
                exact = sum((Fraction(int(dot[i, g]) * int(arrays['act_code'][i, g]) * int(arrays['weight_code'][i, g]),
                                      1 << (int(arrays['act_shift'][i, g]) + int(arrays['weight_shift'][i, g]) - 16)) for g in range(5)), Fraction())
                self.assertEqual(half_away(exact), int(witness['reference_code'][i]))
            np.testing.assert_array_equal(witness['current_code'], current.numpy().reshape(-1)[witness['output_flat_indices']])
            # The same coordinate's later call does not replace preselected evidence.
            self.assertIsNone(collector.record(('audit', 7, 'linear', 'q_proj'), 16, current + 123, reference, args))
            self.assertEqual(len(collector.manifest['records']), 1)
            self.assertFalse(torch.cuda.is_initialized())

    def test_native_four_nodes_complete_dependencies_and_array_replay(self):
        from numerical_reference.model_compat import production_module
        from numerical_reference.local_observer import local_observer_context
        from numerical_reference import gpu_reference
        source = production_module()
        from model.fixbit_v2 import build_softmax_exp_lut_u17
        torch.manual_seed(619)
        raw = torch.randint(-3000, 3001, (1, 2, 2, 128), dtype=torch.int32)
        cos = torch.randint(-65536, 65537, (1, 2, 64), dtype=torch.int64)
        sin = torch.randint(-65536, 65537, (1, 2, 64), dtype=torch.int64)
        query = torch.randint(-4000, 4001, (1, 2, 2, 128), dtype=torch.int32)
        values = torch.randint(-2047, 2048, (1, 3, 1, 4, 32), dtype=torch.int16)
        code = torch.randint(1, 256, (1, 3, 1, 4), dtype=torch.uint8)
        shift = torch.full((1, 3, 1, 4), 20, dtype=torch.uint8)
        cache = source.KV12(values, code, shift)
        score = torch.tensor([[[[0, -513, -1025], [-11, 0, -512]], [[0, 0, 0], [-513, 0, -1024]]]], dtype=torch.int64)
        mask = torch.tensor([[[[True, True, False], [True, True, True]], [[False, False, False], [True, True, True]]]])
        lut = torch.tensor(build_softmax_exp_lut_u17(), dtype=torch.int64)
        probability = torch.tensor([[[[30000, 20000, 15535], [5000, 6553, 53982]], [[1, 2, 65532], [32768, 32767, 0]]]], dtype=torch.int64)
        inputs = [raw, cos, sin, query, values, code, shift, score, mask, lut, probability]
        before = [value.clone() for value in inputs]
        with tempfile.TemporaryDirectory() as temporary:
            collector = NodeWitnesses(temporary, ['audit'], samples_per_coordinate=5)
            with local_observer_context(source, backend=gpu_reference, doc_id='audit', layer=15, track_linear_modules=False) as observer:
                had_record = '_record' in observer.__dict__
                with collector.context(observer):
                    with observer.operation('query_rope'): source._fixed_rope(raw, cos, sin, source.V5Audit(torch.device('cpu')))
                    source._qk_scores_s20(query, cache, 2, source.V5Audit(torch.device('cpu')))
                    source._softmax_u16(score, mask, lut)
                    source._pv_s24(probability, cache, 2, source.V5Audit(torch.device('cpu')))
                self.assertEqual('_record' in observer.__dict__, had_record)
            records = collector.manifest['records']
            self.assertEqual({row['node'] for row in records}, {'rope', 'qk', 'softmax', 'pv'})
            for row in records:
                self.assertEqual(row['status'], 'saved')
                witness = load_witness(temporary, row)
                result = evaluate_node(witness['node'], witness['arrays'], witness['config'])
                np.testing.assert_array_equal(result['current_code'], witness['current_code'], err_msg=row['node'])
                np.testing.assert_array_equal(result['reference_code'], witness['reference_code'], err_msg=row['node'])
                self._fraction_spot(witness)
                if row['node'] == 'rope':
                    self.assertEqual(row['actual_scalar_count'], 2 * row['planned_unit_count'])
                    self.assertEqual(row['planned_scalar_count'], 5)
                if row['node'] == 'softmax':
                    self.assertEqual(row['actual_scalar_count'], 3 * row['planned_unit_count'])
                    self.assertEqual(row['planned_scalar_count'], 5)
                    self.assertEqual(witness['arrays']['lut_u17'].shape, (257,))
            manifest = json.loads((Path(temporary) / 'manifest.json').read_text())
            self.assertGreaterEqual(len(manifest['source_files']), 3)
            self.assertFalse(manifest['error_based_selection'])
            self.assertEqual(manifest['excluded_nodes'], ['swiglu', 'host'])
            self.assertLess(sum(path.stat().st_size for path in Path(temporary).iterdir()), 64 << 20)
        for value, frozen in zip(inputs, before): self.assertTrue(torch.equal(value, frozen))
        self.assertFalse(torch.cuda.is_initialized())

    def _fraction_spot(self, witness):
        node, a, expected = witness['node'], witness['arrays'], witness['reference_code']
        if node == 'rope':
            x, y = map(int, a['raw_pair'][0]); c, s = int(a['cos_q16'][0]), int(a['sin_q16'][0])
            result = [half_away(Fraction(x*c-y*s, 65536)), half_away(Fraction(x*s+y*c, 65536))]
            np.testing.assert_array_equal(result, expected[0])
        elif node == 'qk':
            exact = sum((Fraction(sum(int(x)*int(y) for x, y in zip(a['query_s24'][0, g], a['key_s12'][0, g])) * int(a['kv_code'][0, g]) * 5793,
                                  1 << (int(a['kv_shift'][0, g]) + 18)) for g in range(4)), Fraction())
            self.assertEqual(max(-(16 << 14), min(16 << 14, exact.numerator // exact.denominator)), int(expected[0]))
        elif node == 'pv':
            exact = sum((Fraction(int(p)*int(v)*int(c), 1 << int(s)) for p, v, c, s in zip(a['probability_u16'][0], a['value_s12'][0], a['kv_code'][0], a['kv_shift'][0])), Fraction())
            self.assertEqual(half_away(exact), int(expected[0]))
        elif node == 'softmax':
            for r in range(a['score_q14'].shape[0]):
                valid = a['valid_mask'][r]
                if not valid.any():
                    np.testing.assert_array_equal(expected[r], 0)
                    continue
                maximum = max(int(v) for v, use in zip(a['score_q14'][r], valid) if use)
                exponents = []
                for value, use in zip(a['score_q14'][r], valid):
                    delta = min(16 << 14, max(0, maximum - int(value)))
                    index, fraction = divmod(delta, 1024)
                    high, low = int(a['lut_u17'][index]), int(a['lut_u17'][min(256, index+1)])
                    exponents.append(Fraction(high*1024 - (high-low)*fraction, 1024) if use else Fraction())
                total = sum(exponents, Fraction())
                codes = []
                for exponent in exponents:
                    value = 65536 * exponent / total
                    codes.append(min(65535, (2*value.numerator + value.denominator) // (2*value.denominator)))
                np.testing.assert_array_equal(codes, expected[r])

    def test_budget_skip_is_visible_at_later_layer_and_doc_allowlist(self):
        args, current, reference = linear_fixture(128)
        with tempfile.TemporaryDirectory() as temporary:
            collector = NodeWitnesses(temporary, ['audit'], max_doc_bytes=16384, max_at_bytes=32768)
            self.assertIsNone(collector.record(('not_audit', 0, 'linear', 'q'), 16, current, reference, args))
            for layer in (0, 31):
                row = collector.record(('audit', layer, 'linear', 'q_proj'), 16, current, reference, args)
                self.assertEqual(row['status'], 'skipped')
                self.assertTrue(row['planned']); self.assertTrue(row['budget_exhausted'])
                self.assertEqual(row['skip_reason'], 'byte_budget')
            self.assertEqual(len(collector.manifest['records']), 2)
            self.assertEqual(len(list(Path(temporary).glob('*.npz'))), 0)
            self.assertLessEqual(sum(path.stat().st_size for path in Path(temporary).iterdir()), 16384)

    def test_context_restores_instance_method_on_exception_and_never_rewrites(self):
        args, current, reference = linear_fixture()
        calls = []
        def original(*arguments): calls.append(arguments); return 'same_result'
        observer = SimpleNamespace(_record=original)
        with tempfile.TemporaryDirectory() as temporary:
            collector = NodeWitnesses(temporary, ['audit'])
            with self.assertRaisesRegex(RuntimeError, 'test_exit'):
                with collector.context(observer):
                    result = observer._record(('audit', 0, 'linear', 'q_proj'), 16, current, reference, args, {}, {})
                    self.assertEqual(result, 'same_result')
                    self.assertIs(calls[0][2], current); self.assertIs(calls[0][4], args)
                    with self.assertRaises(RuntimeError):
                        with collector.context(observer): pass
                    raise RuntimeError('test_exit')
            self.assertIs(observer._record, original)
            self.assertFalse(hasattr(observer, '_m005_node_witnesses_active'))
            with self.assertRaises(FileExistsError): NodeWitnesses(temporary, ['audit'])
            row = collector.manifest['records'][0]
            path = Path(temporary) / row['path']
            with path.open('ab') as handle: handle.write(b'tamper')
            with self.assertRaisesRegex(ValueError, 'identity'): load_witness(temporary, row)


if __name__ == '__main__':
    unittest.main()
