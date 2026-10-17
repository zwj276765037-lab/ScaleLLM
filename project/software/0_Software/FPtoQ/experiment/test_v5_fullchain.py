#!/usr/bin/env python3
"""Conformance tests for the V5 production full-chain Torch/Triton twin."""

from __future__ import annotations

import random
import unittest

import torch

from v5_fullchain import (
    PreparedActivation,
    S24_MAX,
    V5Audit,
    V5ProductionLinear,
    _fixed_rope,
    _kv12_quantize,
    _pv_s24,
    _qk_scores_s20,
    _softmax_u16,
    _swiglu_s32,
    _build_silu_lut,
    prepare_fixed_activation,
)

from pathlib import Path
import sys

SCALELLM_ROOT = Path(__file__).resolve().parents[3]
if str(SCALELLM_ROOT) not in sys.path:
    sys.path.insert(0, str(SCALELLM_ROOT))

from model.fixbit_v2 import (  # noqa: E402
    a8w8_group32_guard_s42,
    hadamard32_normalized,
    kv12_quantize_s24,
    minmax_a8_quantize,
    pv_row_tile16_s24,
    qk_score_row_s20,
    round_sat_guard_s42_to_s24,
    rope_pair_s24,
    softmax_row_u16,
)
from model.mlp_fixed import (  # noqa: E402
    build_silu_lut,
    swiglu_product_s32,
)


@unittest.skipUnless(torch.cuda.is_available(), "CUDA is required")
class V5FullchainConformance(unittest.TestCase):
    def setUp(self) -> None:
        self.device = torch.device("cuda:0")
        self.audit = V5Audit(self.device)

    def test_activation_frontend_matches_scalar(self) -> None:
        rng = random.Random(20260913)
        source = [rng.randint(-(1 << 20), (1 << 20)) for _ in range(64)]
        raw = torch.tensor(source, dtype=torch.int64, device=self.device)[None]
        actual = prepare_fixed_activation(
            raw,
            input_width=24,
            hadamard_width=27,
            audit=self.audit,
        )
        for group in range(2):
            expected_h = hadamard32_normalized(
                source[group * 32 : (group + 1) * 32]
            )
            expected_q = minmax_a8_quantize(expected_h.values)
            self.assertEqual(
                actual.values_u8[0, group].cpu().tolist(),
                list(expected_q.values),
            )
            self.assertEqual(int(actual.codes_u8[0, group]), expected_q.scale_code)
            self.assertEqual(int(actual.shifts_u8[0, group]), expected_q.scale_shift)
            self.assertEqual(
                int(actual.zero_points_u8[0, group]), expected_q.zero_point
            )

    def test_rope_matches_scalar(self) -> None:
        rng = random.Random(7)
        raw = torch.tensor(
            [rng.randint(-500_000, 500_000) for _ in range(128)],
            dtype=torch.int32,
            device=self.device,
        ).reshape(1, 1, 1, 128)
        cos = torch.tensor(
            [[rng.randint(-65536, 65536) for _ in range(64)]],
            dtype=torch.int32,
            device=self.device,
        ).reshape(1, 1, 64)
        sin = torch.tensor(
            [[rng.randint(-65536, 65536) for _ in range(64)]],
            dtype=torch.int32,
            device=self.device,
        ).reshape(1, 1, 64)
        actual = _fixed_rope(raw, cos, sin, self.audit).cpu().reshape(-1).tolist()
        expected0 = []
        expected1 = []
        flat = raw.cpu().reshape(-1).tolist()
        for lane in range(64):
            y0, y1, _ = rope_pair_s24(
                flat[lane], flat[lane + 64], int(cos[0, 0, lane]), int(sin[0, 0, lane])
            )
            expected0.append(y0)
            expected1.append(y1)
        self.assertEqual(actual, expected0 + expected1)

    def test_triton_linear_matches_scalar_attention(self) -> None:
        import numpy as np

        rng = random.Random(11)
        source = [rng.randint(-400_000, 400_000) for _ in range(64)]
        raw = torch.tensor(source, dtype=torch.int64, device=self.device)[None]
        activation = prepare_fixed_activation(
            raw, input_width=24, hadamard_width=27, audit=self.audit
        )
        weights = np.asarray(
            [
                [
                    [rng.randint(-127, 127) for _ in range(32)]
                    for _ in range(2)
                ]
                for _ in range(16)
            ],
            dtype=np.int8,
        )
        weight_codes = np.asarray(
            [[rng.randint(1, 255) for _ in range(2)] for _ in range(16)],
            dtype=np.uint8,
        )
        weight_shifts = np.full((16, 2), 20, dtype=np.uint8)
        module = V5ProductionLinear(
            module_name="synthetic.q_proj",
            op_name="q_proj",
            weight_s8=weights,
            weight_codes_u8=weight_codes,
            weight_shifts_u8=weight_shifts,
            input_width=24,
            hadamard_width=27,
            device=self.device,
            audit=self.audit,
        )
        actual = module.project_prepared(activation).cpu().reshape(-1).tolist()
        expected = []
        for column in range(16):
            accumulator = 0
            for group in range(2):
                accumulator += a8w8_group32_guard_s42(
                    activation.values_u8[0, group].cpu().tolist(),
                    weights[column, group].tolist(),
                    int(activation.zero_points_u8[0, group]),
                    int(activation.codes_u8[0, group]),
                    int(activation.shifts_u8[0, group]),
                    int(weight_codes[column, group]),
                    int(weight_shifts[column, group]),
                )
            value, _ = round_sat_guard_s42_to_s24(accumulator)
            expected.append(value)
        self.assertEqual(actual, expected)

    def test_tf32_group32_correlation_is_integer_exact_at_extrema(self) -> None:
        import numpy as np

        rng = np.random.default_rng(20260913)
        values = rng.integers(0, 256, size=(16, 4, 32), dtype=np.uint8)
        # Force both endpoint magnitudes into every row/group.
        values[..., 0] = 0
        values[..., 1] = 255
        zero_points = rng.integers(0, 256, size=(16, 4), dtype=np.uint8)
        weights = rng.choice(
            np.asarray([-127, -1, 0, 1, 127], dtype=np.int8),
            size=(16, 4, 32),
        ).astype(np.int8)
        weights[..., 0] = -127
        weights[..., 1] = 127
        activation = PreparedActivation(
            torch.from_numpy(values).to(self.device),
            torch.full((16, 4), 32, dtype=torch.uint8, device=self.device),
            torch.full((16, 4), 13, dtype=torch.uint8, device=self.device),
            torch.from_numpy(zero_points).to(self.device),
            (16,),
        )
        module = V5ProductionLinear(
            module_name="synthetic.q_proj.extrema",
            op_name="q_proj",
            weight_s8=weights,
            weight_codes_u8=np.full((16, 4), 32, dtype=np.uint8),
            weight_shifts_u8=np.full((16, 4), 13, dtype=np.uint8),
            input_width=24,
            hadamard_width=27,
            device=self.device,
            audit=self.audit,
        )
        actual = module.project_prepared(activation).cpu().numpy()
        centered = values.astype(np.int64) - zero_points.astype(np.int64)[..., None]
        expected = np.einsum("rgk,cgk->rc", centered, weights.astype(np.int64))
        # codes 32*32 with total_shift 26 produce guard=correlation*256;
        # the final Q24->Q16 shift therefore recovers the correlation exactly.
        np.testing.assert_array_equal(actual, expected)

    def test_below_v3_mlp_shift_uses_rtl_zero_guard(self) -> None:
        import numpy as np

        activation = PreparedActivation(
            torch.ones((1, 2, 32), dtype=torch.uint8, device=self.device),
            torch.full((1, 2), 100, dtype=torch.uint8, device=self.device),
            torch.full((1, 2), 5, dtype=torch.uint8, device=self.device),
            torch.zeros((1, 2), dtype=torch.uint8, device=self.device),
            (1,),
        )
        module = V5ProductionLinear(
            module_name="synthetic.down_proj",
            op_name="down_proj",
            weight_s8=np.ones((16, 2, 32), dtype=np.int8),
            weight_codes_u8=np.full((16, 2), 141, dtype=np.uint8),
            weight_shifts_u8=np.full((16, 2), 14, dtype=np.uint8),
            input_width=32,
            hadamard_width=35,
            device=self.device,
            audit=self.audit,
            strict_total_shift=False,
        )
        output = module.project_prepared(activation)
        self.assertEqual(output.cpu().reshape(-1).tolist(), [0] * 16)
        self.assertEqual(
            self.audit.collect()["linear_total_shift_format_error"], 32
        )

    def test_format_v3_mlp_shift20_preserves_guard(self) -> None:
        import numpy as np

        activation = PreparedActivation(
            torch.ones((1, 2, 32), dtype=torch.uint8, device=self.device),
            torch.full((1, 2), 100, dtype=torch.uint8, device=self.device),
            torch.full((1, 2), 6, dtype=torch.uint8, device=self.device),
            torch.zeros((1, 2), dtype=torch.uint8, device=self.device),
            (1,),
        )
        module = V5ProductionLinear(
            module_name="synthetic.down_proj",
            op_name="down_proj",
            weight_s8=np.ones((16, 2, 32), dtype=np.int8),
            weight_codes_u8=np.full((16, 2), 141, dtype=np.uint8),
            weight_shifts_u8=np.full((16, 2), 14, dtype=np.uint8),
            input_width=32,
            hadamard_width=35,
            device=self.device,
            audit=self.audit,
        )
        output = module.project_prepared(activation)
        # Each Group32 guard is 32*100*141*2^(24-20)=7,219,200.
        # Two groups accumulate to Q*.24=14,438,400 and Q16 rounding gives
        # the exact S24 output 56,400 in current format-v3.
        self.assertEqual(output.cpu().reshape(-1).tolist(), [56_400] * 16)
        audit = self.audit.collect()
        self.assertEqual(audit["linear_total_shift_format_error"], 0)
        self.assertEqual(audit["linear_group_guard_overflow_s37"], 0)
        self.assertEqual(audit["linear_software_group_guard_overflow"], 0)
        self.assertEqual(audit["linear_accumulator_overflow"], 0)
        self.assertEqual(audit["linear_software_accumulator_overflow"], 0)

    def test_diagnostic_s32_down_boundary_removes_only_s24_clamp(self) -> None:
        import numpy as np

        groups = 448
        activation = PreparedActivation(
            torch.ones(
                (1, groups, 32), dtype=torch.uint8, device=self.device
            ),
            torch.full(
                (1, groups), 100, dtype=torch.uint8, device=self.device
            ),
            torch.full(
                (1, groups), 6, dtype=torch.uint8, device=self.device
            ),
            torch.zeros(
                (1, groups), dtype=torch.uint8, device=self.device
            ),
            (1,),
        )
        common = {
            "op_name": "down_proj",
            "weight_s8": np.ones((16, groups, 32), dtype=np.int8),
            "weight_codes_u8": np.full(
                (16, groups), 141, dtype=np.uint8
            ),
            "weight_shifts_u8": np.full(
                (16, groups), 14, dtype=np.uint8
            ),
            "input_width": 32,
            "hadamard_width": 35,
            "device": self.device,
        }
        s24_audit = V5Audit(self.device)
        s24 = V5ProductionLinear(
            module_name="synthetic.s24.down_proj",
            output_width=24,
            audit=s24_audit,
            **common,
        ).project_prepared(activation)
        s32_audit = V5Audit(self.device)
        s32 = V5ProductionLinear(
            module_name="synthetic.s32.down_proj",
            output_width=32,
            audit=s32_audit,
            **common,
        ).project_prepared(activation)

        self.assertEqual(
            s24.cpu().reshape(-1).tolist(), [S24_MAX] * 16
        )
        self.assertEqual(
            s32.cpu().reshape(-1).tolist(), [12_633_600] * 16
        )
        self.assertEqual(
            s24_audit.collect()["linear_output_saturation"], 16
        )
        self.assertEqual(
            s32_audit.collect()["linear_output_saturation"], 0
        )

    def test_format_v3_s37_guard_accepts_value_above_s36(self) -> None:
        import numpy as np

        activation = PreparedActivation(
            torch.full((1, 1, 32), 255, dtype=torch.uint8, device=self.device),
            torch.full((1, 1), 255, dtype=torch.uint8, device=self.device),
            torch.full((1, 1), 10, dtype=torch.uint8, device=self.device),
            torch.zeros((1, 1), dtype=torch.uint8, device=self.device),
            (1,),
        )
        module = V5ProductionLinear(
            module_name="synthetic.s37_boundary.down_proj",
            op_name="down_proj",
            weight_s8=np.full((16, 1, 32), 7, dtype=np.int8),
            weight_codes_u8=np.full((16, 1), 255, dtype=np.uint8),
            weight_shifts_u8=np.full((16, 1), 10, dtype=np.uint8),
            input_width=32,
            hadamard_width=35,
            device=self.device,
            audit=self.audit,
        )
        module.project_prepared(activation)
        # 32*255*7*255*255 << 4 = 59,427,648,000.  This exceeds S36 but is
        # legal in the production S37 guard introduced by format-v3.
        audit = self.audit.collect()
        self.assertEqual(audit["linear_total_shift_format_error"], 0)
        self.assertEqual(audit["linear_group_guard_overflow_s37"], 0)
        self.assertEqual(audit["linear_software_group_guard_overflow"], 0)

    def test_kv12_matches_scalar(self) -> None:
        rng = random.Random(8)
        source = [rng.randint(-700_000, 700_000) for _ in range(128)]
        raw = torch.tensor(source, dtype=torch.int32, device=self.device).reshape(
            1, 1, 1, 128
        )
        actual = _kv12_quantize(raw, self.audit)
        for group in range(4):
            expected = kv12_quantize_s24(source[group * 32 : (group + 1) * 32])
            self.assertEqual(
                actual.values_s12[0, 0, 0, group].cpu().tolist(),
                list(expected.values),
            )
            self.assertEqual(int(actual.codes_u8[0, 0, 0, group]), expected.scale_code)
            self.assertEqual(int(actual.shifts_u8[0, 0, 0, group]), expected.scale_shift)

    def test_softmax_matches_scalar(self) -> None:
        rng = random.Random(9)
        scores = [rng.randint(-(16 << 14), 16 << 14) for _ in range(128)]
        masks = [index > 92 for index in range(128)]
        expected, _, _, _ = softmax_row_u16(scores, masks)
        score_tensor = torch.tensor(
            scores, dtype=torch.int64, device=self.device
        ).reshape(1, 1, 1, 128)
        valid = torch.tensor(
            [not value for value in masks], dtype=torch.bool, device=self.device
        ).reshape(1, 1, 1, 128)
        lut = torch.tensor(
            __import__("model.fixbit_v2", fromlist=["build_softmax_exp_lut_u17"])
            .build_softmax_exp_lut_u17(),
            dtype=torch.int64,
            device=self.device,
        )
        actual = _softmax_u16(score_tensor, valid, lut).cpu().reshape(-1).tolist()
        self.assertEqual(actual, list(expected))

    def test_softmax_empty_padding_row_is_zero(self) -> None:
        scores = torch.zeros(
            (1, 1, 2, 2), dtype=torch.int64, device=self.device
        )
        valid = torch.tensor(
            [[[[False, False], [True, True]]]],
            dtype=torch.bool,
            device=self.device,
        )
        lut = torch.tensor(
            __import__("model.fixbit_v2", fromlist=[
                "build_softmax_exp_lut_u17"
            ]).build_softmax_exp_lut_u17(),
            dtype=torch.int64,
            device=self.device,
        )
        actual = _softmax_u16(scores, valid, lut)
        self.assertEqual(actual[0, 0, 0].cpu().tolist(), [0, 0])
        self.assertGreater(int(actual[0, 0, 1].sum().item()), 0)

    def test_qk_matches_scalar(self) -> None:
        rng = random.Random(12)
        query = [rng.randint(-900_000, 900_000) for _ in range(128)]
        key_source = [
            [rng.randint(-900_000, 900_000) for _ in range(128)]
            for _ in range(128)
        ]
        key_raw = torch.tensor(
            key_source, dtype=torch.int32, device=self.device
        ).reshape(1, 128, 1, 128)
        key_cache = _kv12_quantize(key_raw, self.audit)
        actual = _qk_scores_s20(
            torch.tensor(query, dtype=torch.int32, device=self.device).reshape(
                1, 1, 1, 128
            ),
            key_cache,
            1,
            self.audit,
        ).cpu().reshape(-1).tolist()
        key_groups = key_cache.values_s12.cpu().reshape(128, 4, 32).tolist()
        key_codes = key_cache.codes_u8.cpu().reshape(128, 4).tolist()
        key_shifts = key_cache.shifts_u8.cpu().reshape(128, 4).tolist()
        expected, _ = qk_score_row_s20(
            [query[index : index + 32] for index in range(0, 128, 32)],
            key_groups,
            key_codes,
            key_shifts,
            [False] * 128,
        )
        self.assertEqual(actual, list(expected))

    def test_pv_matches_scalar(self) -> None:
        rng = random.Random(13)
        value_source = [
            [rng.randint(-700_000, 700_000) for _ in range(128)]
            for _ in range(128)
        ]
        value_raw = torch.tensor(
            value_source, dtype=torch.int32, device=self.device
        ).reshape(1, 128, 1, 128)
        value_cache = _kv12_quantize(value_raw, self.audit)
        probabilities = [rng.randint(0, 65535) for _ in range(128)]
        actual = _pv_s24(
            torch.tensor(
                probabilities, dtype=torch.int64, device=self.device
            ).reshape(1, 1, 1, 128),
            value_cache,
            1,
            self.audit,
        ).cpu().reshape(-1).tolist()
        expected = []
        values = value_cache.values_s12.cpu().reshape(128, 4, 32).tolist()
        codes = value_cache.codes_u8.cpu().reshape(128, 4).tolist()
        shifts = value_cache.shifts_u8.cpu().reshape(128, 4).tolist()
        for group in range(4):
            for half in range(2):
                tile, _ = pv_row_tile16_s24(
                    probabilities,
                    [row[group][half * 16 : (half + 1) * 16] for row in values],
                    [row[group] for row in codes],
                    [row[group] for row in shifts],
                )
                expected.extend(tile)
        self.assertEqual(actual, expected)

    def test_swiglu_matches_scalar(self) -> None:
        rng = random.Random(10)
        gate = [rng.randint(-(20 << 16), 20 << 16) for _ in range(1024)]
        up = [rng.randint(-(100 << 16), 100 << 16) for _ in range(1024)]
        actual = _swiglu_s32(
            torch.tensor(gate, dtype=torch.int32, device=self.device),
            torch.tensor(up, dtype=torch.int32, device=self.device),
            _build_silu_lut(self.device),
            self.audit,
        ).cpu().tolist()
        table = build_silu_lut()
        expected = [swiglu_product_s32(g, u, table) for g, u in zip(gate, up)]
        self.assertEqual(actual, expected)

    def test_swiglu_s24_extrema_fit_s32(self) -> None:
        low = -(1 << 23)
        high = (1 << 23) - 1
        gate = torch.tensor(
            [low, low, high, high], dtype=torch.int32, device=self.device
        )
        up = torch.tensor(
            [low, high, low, high], dtype=torch.int32, device=self.device
        )
        actual = _swiglu_s32(
            gate, up, _build_silu_lut(self.device), self.audit
        )
        table = build_silu_lut()
        expected = [
            swiglu_product_s32(int(g), int(u), table)
            for g, u in zip(gate.cpu().tolist(), up.cpu().tolist())
        ]
        self.assertEqual(actual.cpu().tolist(), expected)
        self.assertEqual(self.audit.collect()["swiglu_output_overflow"], 0)


if __name__ == "__main__":
    unittest.main()
