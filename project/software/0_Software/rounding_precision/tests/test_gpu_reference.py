"""GPU reference qualification against independent CPU integer references.

Use NUMERICAL_TEST_DEVICE=cuda:0 for the actual Triton tests; default CPU tests
the native-tensor node layout and arithmetic without initializing CUDA.
"""
import os
from pathlib import Path
import sys
import unittest
from fractions import Fraction

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiment'))
from numerical_reference import gpu_reference as gpu
from numerical_reference.current_nodes import _v5
from numerical_reference.exact_reductions import evaluate_reference, selected_softmax_code
from numerical_reference.policy import ArithmeticPolicy, canonicalize, PROFILES

DEVICE = os.environ.get('NUMERICAL_TEST_DEVICE', 'cpu')


class Audit:
    def __init__(self): self.values = {}
    def add(self, key, value):
        self.values[key] = self.values.get(key, 0) + int(torch.as_tensor(value).item())


def tensor(a, dtype=torch.int64):
    return torch.as_tensor(a, dtype=dtype, device=DEVICE)


def arr(t): return t.detach().cpu().numpy()


def ref(node, a, config=None):
    config = config or {}
    a, domain = canonicalize(node, a, config)
    assert domain.all(), 'fixture must be within the declared input domain'
    return evaluate_reference(node, a, config)['code']


def away_fraction(value):
    sign = -1 if value < 0 else 1
    magnitude = abs(value)
    return sign * ((2 * magnitude.numerator + magnitude.denominator) // (2 * magnitude.denominator))


class NumericalNativeReference(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        self.rng = np.random.default_rng(20261019)

    def test_rope_signed_products_and_layout(self):
        raw = self.rng.integers(-(1 << 22), 1 << 22, (2, 5, 3, 128), dtype=np.int64)
        cos = self.rng.integers(-65536, 65537, (2, 5, 64), dtype=np.int64)
        sin = self.rng.integers(-65536, 65537, (2, 5, 64), dtype=np.int64)
        raw[0, 0, 0, 0], raw[0, 0, 0, 64] = 1, -1
        cos[0, 0, 0], sin[0, 0, 0] = 32768, 32768
        pairs = np.stack((raw[..., :64], raw[..., 64:]), -1).reshape(-1, 2)
        a = {'raw_pair': pairs,
             'cos_q16': np.broadcast_to(cos[:, :, None, :], raw[..., :64].shape).reshape(-1),
             'sin_q16': np.broadcast_to(sin[:, :, None, :], raw[..., :64].shape).reshape(-1)}
        expected = ref('rope', a).reshape(2, 5, 3, 64, 2)
        expected = np.concatenate((expected[..., 0], expected[..., 1]), -1)
        actual = gpu.rope_exact(tensor(raw), tensor(cos), tensor(sin), Audit())
        np.testing.assert_array_equal(arr(actual), expected)

    def test_qk_exact_reduction_and_head_repeat(self):
        v5 = _v5()
        query = self.rng.integers(-16384, 16385, (2, 5, 4, 128), dtype=np.int64)
        key = self.rng.integers(-2047, 2048, (2, 7, 2, 4, 32), dtype=np.int64)
        code = self.rng.integers(1, 256, (2, 7, 2, 4), dtype=np.int64)
        shift = self.rng.integers(8, 33, code.shape, dtype=np.int64)
        code[:, 0, :, 0] = 0; shift[:, 0, :, 0] = 63
        keys = v5.KV12(tensor(key, torch.int16), tensor(code, torch.uint8), tensor(shift, torch.uint8))
        q = query.reshape(2, 5, 4, 4, 32).transpose(0, 2, 3, 1, 4)
        k = np.repeat(key, 2, axis=2).transpose(0, 2, 3, 1, 4)
        dots = np.einsum('bhgql,bhgkl->bhqkg', q, k, optimize=True)
        codes = np.repeat(code, 2, axis=2).transpose(0, 2, 1, 3)[:, :, None, :, :]
        shifts = np.repeat(shift, 2, axis=2).transpose(0, 2, 1, 3)[:, :, None, :, :]
        a = dict(dot=dots.reshape(-1, 4), kv_code=np.broadcast_to(codes, dots.shape).reshape(-1, 4),
                 kv_shift=np.broadcast_to(shifts, dots.shape).reshape(-1, 4))
        expected = ref('qk', a).reshape(2, 4, 5, 7)
        np.testing.assert_array_equal(arr(gpu.qk_exact(tensor(query), keys, 2, Audit())), expected)

    def test_softmax_all_switches_masks_and_ties(self):
        from numerical_reference.current_nodes import _v5
        lut = np.asarray(_v5().build_softmax_exp_lut_u17(), dtype=np.int64)
        scores = self.rng.integers(-(16 << 14), (16 << 14) + 1, (16, 128), dtype=np.int64)
        mask = self.rng.random(scores.shape) > .2
        mask[0] = False; mask[1] = False; mask[1, 0] = True
        scores[2] = 0; mask[2] = True
        scores[3, :3] = [0, -512, -1536]; mask[3] = False; mask[3, :3] = True
        a = dict(score_q14=scores, valid_mask=mask, lut_u17=lut)
        for interpolation in (False, True):
            for reciprocal in (False, True):
                policy = ArithmeticPolicy(softmax_interpolation_round=interpolation,
                                          softmax_reciprocal_round=reciprocal)
                expected = selected_softmax_code(a, policy)
                actual = gpu.softmax_exact(tensor(scores), tensor(mask, torch.bool), tensor(lut),
                    interpolation_round=interpolation, reciprocal_round=reciprocal)
                np.testing.assert_array_equal(arr(actual), expected)
                if interpolation and reciprocal:
                    prod = _v5()._softmax_u16(tensor(scores), tensor(mask, torch.bool), tensor(lut))
                    np.testing.assert_array_equal(arr(actual), arr(prod))

    def test_pv_exact_reduction_and_layout(self):
        v5 = _v5()
        probability = self.rng.integers(0, 65536, (1, 4, 5, 7), dtype=np.int64)
        value = self.rng.integers(-2047, 2048, (1, 7, 2, 4, 32), dtype=np.int64)
        code = self.rng.integers(1, 256, (1, 7, 2, 4), dtype=np.int64)
        shift = self.rng.integers(8, 33, code.shape, dtype=np.int64)
        code[:, 0, :, 0] = 0; shift[:, 0, :, 0] = 63
        values = v5.KV12(tensor(value, torch.int16), tensor(code, torch.uint8), tensor(shift, torch.uint8))
        # N order B,H,Q,G,L, reduction key K.
        shape = (1, 4, 5, 4, 32, 7)
        p = probability[:, :, :, None, None, :]
        v = np.repeat(value, 2, axis=2).transpose(0, 2, 3, 4, 1)[:, :, None, :, :, :]
        c = np.repeat(code, 2, axis=2).transpose(0, 2, 3, 1)[:, :, None, :, None, :]
        s = np.repeat(shift, 2, axis=2).transpose(0, 2, 3, 1)[:, :, None, :, None, :]
        a = {name: np.broadcast_to(x, shape).reshape(-1, 7) for name, x in
             [('probability_u16', p), ('value_s12', v), ('kv_code', c), ('kv_shift', s)]}
        expected = ref('pv', a).reshape(1, 4, 5, 128)
        np.testing.assert_array_equal(arr(gpu.pv_exact(tensor(probability), values, 2, Audit(), head_chunk=3)), expected)

    @unittest.skipUnless(DEVICE.startswith('cuda'), 'actual Triton check requires GPU qualification')
    def test_triton_linear_partial_tiles_all_profiles(self):
        v5 = _v5()
        for name, spec in PROFILES.items():
            rows, columns = 17, 19
            groups = 448 if name == 'mlp_down' else 128
            qa = self.rng.integers(0, 256, (rows, groups, 32), dtype=np.uint8)
            zp = self.rng.integers(0, 256, (rows, groups), dtype=np.uint8)
            lo, hi = (-127, 128) if name == 'attention' else (-8, 8)
            qw = self.rng.integers(lo, hi, (columns, groups, 32), dtype=np.int8)
            ac = self.rng.integers(1, 256, (rows, groups), dtype=np.uint8)
            wc = self.rng.integers(1, 256, (columns, groups), dtype=np.uint8)
            base = spec['shift_min'] // 2
            ash = self.rng.integers(base, base + spec['shift_max'] - spec['shift_min'] + 1,
                                     (rows, groups), dtype=np.uint8)
            wsh = np.full((columns, groups), spec['shift_min'] - base, dtype=np.uint8)
            ac[:, 0] = 0; wc[:, 0] = 0; ash[:, 0] = 63; wsh[:, 0] = 63
            activation = v5.PreparedActivation(tensor(qa, torch.uint8), tensor(ac, torch.uint8),
                tensor(ash, torch.uint8), tensor(zp, torch.uint8), (1, rows))
            dots = np.einsum('rgl,cgl->rcg', qa.astype(np.int64) - zp.astype(np.int64)[..., None], qw.astype(np.int64))
            a = {'dot': dots.reshape(-1, groups)}
            for key, x in [('act_code', ac), ('act_shift', ash)]:
                a[key] = np.broadcast_to(x[:, None, :], dots.shape).reshape(-1, groups).astype(np.int64)
            for key, x in [('weight_code', wc), ('weight_shift', wsh)]:
                a[key] = np.broadcast_to(x[None, :, :], dots.shape).reshape(-1, groups).astype(np.int64)
            expected = ref('linear', a, {'profile': name}).reshape(1, rows, columns)
            counters = [torch.zeros((), dtype=torch.int64, device=DEVICE) for _ in range(5)]
            actual = gpu.grouped_linear_exact(activation, tensor(qw, torch.int8), tensor(wc, torch.uint8),
                tensor(wsh, torch.uint8), spec['shift_min'], spec['shift_max'], spec['accumulator_width'],
                spec['accumulator_width'], spec['guard_width'], True, True, *counters,
                output_min=-(1 << (spec['output_width'] - 1)), output_max=(1 << (spec['output_width'] - 1)) - 1)
            np.testing.assert_array_equal(arr(actual), expected)
            for row, col in [(0, 0), (8, 9), (16, 18)]:
                exact = Fraction(0)
                for g in range(groups):
                    n = int(dots[row, col, g]) * int(ac[row, g]) * int(wc[col, g])
                    k = int(ash[row, g]) + int(wsh[col, g]) - 16
                    exact += Fraction(n, 1 << k) if k >= 0 else Fraction(n << -k)
                rounded = away_fraction(exact)
                clipped = min(max(rounded, -(1 << (spec['output_width'] - 1))), (1 << (spec['output_width'] - 1)) - 1)
                self.assertEqual(int(arr(actual)[0, row, col]), clipped)

    def test_patch_restoration_and_current_noop(self):
        from numerical_reference.policy import CURRENT
        v5 = _v5()
        original = v5._fixed_rope
        with gpu.arithmetic_context(v5, CURRENT): self.assertIs(v5._fixed_rope, original)
        with gpu.arithmetic_context(v5):
            with self.assertRaisesRegex(RuntimeError, 'sequential'):
                with gpu.arithmetic_context(v5, CURRENT): pass
        with self.assertRaisesRegex(RuntimeError, 'intentional'):
            with gpu.arithmetic_context(v5):
                self.assertIs(v5._fixed_rope, gpu.rope_exact)
                raise RuntimeError('intentional')
        self.assertIs(v5._fixed_rope, original)


if __name__ == '__main__':
    unittest.main(verbosity=2)
