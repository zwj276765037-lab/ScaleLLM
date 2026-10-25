"""Independent old-reference math and byte-index tests for Host linear MLP."""

import hashlib
from pathlib import Path
import struct
import unittest
from unittest import mock

import numpy as np

from host import scalellm_mlp_linear as linear
from host.scalellm_hostops import pack_s24_q16
from model import fixbit_v2 as fixbit
from model import mlp_fixed as old_mlp


def reference_h32(values, bits):
    oracle = fixbit.hadamard32_normalized if bits == 24 else old_mlp.hadamard32_product_normalized
    result = np.empty(values.shape, dtype=np.int64)
    for source, output in zip(values.reshape(-1, 32), result.reshape(-1, 32), strict=True):
        answer = oracle(source.tolist())
        assert answer.saturation_count == 0
        output[:] = answer.values
    return result


def reference_quantize(values, bits):
    oracle = fixbit.minmax_a8_quantize if bits == 27 else old_mlp.minmax_a8_quantize_s35
    q = np.empty(values.shape, dtype=np.uint8)
    meta = np.empty((*values.shape[:-1], values.shape[-1] // 32), dtype=np.uint32)
    for index, source in enumerate(values.reshape(-1, 32)):
        answer = oracle(source.tolist())
        q.reshape(-1, 32)[index] = answer.values
        meta.reshape(-1)[index] = answer.metadata
    return q, meta


def reference_rec576(q, metadata):
    """Direct scalar byte indexing; independent of DUT reshape/transposes."""
    groups = q.shape[1] // 32
    result = bytearray(groups * 576)
    for group in range(groups):
        for row in range(16):
            for lane in range(32):
                result[group * 576 + row * 32 + lane] = int(q[row, group * 32 + lane])
            offset = group * 576 + 512 + row * 3
            result[offset:offset + 3] = int(metadata[row, group]).to_bytes(3, "little")
    return bytes(result)


def reference_gu_payload(gate, up):
    result = bytearray(linear.GU_PAYLOAD_BYTES)
    for tile in range(896):
        for matrix, values in enumerate((gate, up)):
            for row in range(16):
                for lane in range(16):
                    offset = (2 * tile + matrix) * 768 + (row * 16 + lane) * 3
                    result[offset:offset + 3] = int(values[row, tile * 16 + lane]).to_bytes(3, "little", signed=True)
    return bytes(result)


def marked_gu_values():
    row = np.arange(16, dtype=np.int64)[:, None]
    col = np.arange(14336, dtype=np.int64)[None, :]
    gate = (row * 524309 + col * 7919) % (1 << 24) - (1 << 23)
    up = (row * 1048583 + col * 15401 + 17) % (1 << 24) - (1 << 23)
    gate[0, 0], up[15, -1] = -(1 << 23), (1 << 23) - 1
    return gate, up


class HadamardAndBoundaryTests(unittest.TestCase):
    def test_s24_full_16_rows_and_128_groups_against_old_reference(self):
        values = np.random.default_rng(6001).integers(-(1 << 23), 1 << 23, (16, 4096), dtype=np.int64)
        values[15, :32] = -(1 << 23)
        values[14, :32] = (1 << 23) - 1
        np.testing.assert_array_equal(linear.hadamard32_s24_exact(values), reference_h32(values, 24))

    def test_s32_full_16_rows_and_448_groups_against_old_reference(self):
        values = np.random.default_rng(6002).integers(-(1 << 31), 1 << 31, (16, 14336), dtype=np.int64)
        values[15, :32] = -(1 << 31)
        values[14, :32] = (1 << 31) - 1
        result = linear.hadamard32_s32_exact(values)
        np.testing.assert_array_equal(result, reference_h32(values, 32))
        self.assertGreater(int(np.max(np.abs(result))), (1 << 31) - 1)

    def test_zero_impulse_alternating_and_half_away_ties(self):
        for bits, operation in ((24, linear.hadamard32_s24_exact), (32, linear.hadamard32_s32_exact)):
            high, low = (1 << (bits - 1)) - 1, -(1 << (bits - 1))
            values = np.array([[0] * 32, [high] + [0] * 31,
                               [low, high] * 16, [32768] + [0] * 31,
                               [-32768] + [0] * 31], dtype=np.int64)
            result = operation(values)
            np.testing.assert_array_equal(result, reference_h32(values, bits))
            self.assertEqual(int(result[3, 0]), 5793)
            self.assertEqual(int(result[4, 0]), -5793)

    def test_numeric_apis_reject_float_out_of_range_and_wrong_groups(self):
        for operation, bits in ((linear.hadamard32_s24_exact, 24), (linear.hadamard32_s32_exact, 32)):
            for values in (np.zeros(32, np.float32), np.zeros(32, bool)):
                with self.assertRaises(TypeError):
                    operation(values)
            for values in (np.array([1 << (bits - 1)] * 32), np.zeros(31, np.int64), np.array([], dtype=np.int64)):
                with self.assertRaises(linear.MLPLinearFormatError):
                    operation(values)
        with self.assertRaises(linear.MLPLinearFormatError):
            linear.hadamard32_s24_exact(np.full(32, 2**64 - 1, dtype=np.uint64))

    def test_normalized_fp32_boundary_matches_existing_s24_bytes(self):
        values = np.random.default_rng(6003).uniform(-130, 130, (16, 4096)).astype(np.float32)
        values[0, :8] = [-200, 200, -1.5 / 65536, -.5 / 65536, .5 / 65536, 1.5 / 65536, -128, 128]
        expected = pack_s24_q16(values)
        integers = linear.s24_from_normalized_fp32(values)
        actual = b"".join(int(value).to_bytes(3, "little", signed=True) for value in integers.ravel())
        self.assertEqual(actual, expected)
        self.assertEqual(integers[0, :8].tolist(), [-8388608, 8388607, -2, -1, 1, 2, -8388608, 8388607])

    def test_normalized_boundary_rejects_dtype_nonfinite_and_shape(self):
        with self.assertRaises(TypeError):
            linear.s24_from_normalized_fp32(np.zeros((16, 4096), np.float64))
        for values in (np.full((16, 4096), np.nan, np.float32), np.zeros((8, 4096), np.float32)):
            with self.assertRaises(linear.MLPLinearFormatError):
                linear.s24_from_normalized_fp32(values)

    def test_extreme_finite_fp32_saturates_before_integer_conversion(self):
        values = np.full((16, 4096), np.finfo(np.float32).max, np.float32)
        values[15] *= -1
        result = linear.s24_from_normalized_fp32(values)
        self.assertTrue(np.all(result[:15] == 8388607))
        self.assertTrue(np.all(result[15] == -8388608))


class QuantizationTests(unittest.TestCase):
    def test_s27_full_16_rows_128_groups_independent_oracle(self):
        values = np.random.default_rng(6010).integers(-(1 << 26), 1 << 26, (16, 4096), dtype=np.int64)
        actual = linear.minmax_a8_scalecode_exact(values)
        for got, expected in zip(actual, reference_quantize(values, 27), strict=True):
            np.testing.assert_array_equal(got, expected)

    def test_s35_full_16_rows_448_groups_independent_oracle(self):
        values = np.random.default_rng(6011).integers(-2_000_000_000, 2_000_000_000, (16, 14336), dtype=np.int64)
        actual = linear.minmax_a8_scalecode_exact(values, input_bits=35)
        for got, expected in zip(actual, reference_quantize(values, 35), strict=True):
            np.testing.assert_array_equal(got, expected)

    def test_zero_constant_positive_negative_and_scale_scan_boundaries(self):
        diffs = [0, 1, 2, 3, 255 << 8, 255 << 16, linear.SCALE_EXACT_LIMIT,
                 linear.SCALE_DIFF_Q16_MAX]
        diffs += [linear.SCALE_EXACT_LIMIT >> shift for shift in range(1, 32)]
        for diff in diffs:
            for sign in (-1, 1):
                values = np.full((1, 32), sign * diff, np.int64)
                actual = linear.minmax_a8_scalecode_exact(values, input_bits=35)
                expected = reference_quantize(values, 35)
                for got, want in zip(actual, expected, strict=True):
                    np.testing.assert_array_equal(got, want)
        zero_q, zero_meta = linear.minmax_a8_scalecode_exact(np.zeros((16, 32), np.int64))
        self.assertFalse(np.any(zero_q))
        self.assertFalse(np.any(zero_meta))

    def test_ties_even_zero_point_and_affine_clamp(self):
        values = np.array([[-255, 255, -254, -253, -252, -251, 0, 1] * 4], dtype=np.int64)
        q, metadata = linear.minmax_a8_scalecode_exact(values)
        self.assertEqual(int(metadata[0, 0]) & 255, 128)  # 127.5 -> even 128
        self.assertEqual(q[0, :8].tolist(), [0, 255, 1, 2, 2, 2, 128, 128])
        for got, want in zip((q, metadata), reference_quantize(values, 27), strict=True):
            np.testing.assert_array_equal(got, want)

    def test_scale_code_rounding_ties(self):
        # shift=0; code exact half ties at 128.5 and 129.5, yielding 128/130.
        for code, rounded in ((128, 128), (129, 130), (254, 254), (255, 255)):
            diff = (2 * code + 1) * (255 << 15)
            if diff > linear.SCALE_DIFF_Q16_MAX:
                continue
            values = np.array([[0, diff] + [0] * 30], np.int64)
            _, metadata = linear.minmax_a8_scalecode_exact(values, input_bits=35)
            # Scale scan can shift low ranges; assert the final old integer rule.
            expected = old_mlp.minmax_a8_quantize_s35(values[0].tolist())
            self.assertEqual(int(metadata[0, 0]), expected.metadata)
            if expected.scale_shift == 0:
                self.assertEqual(expected.scale_code, rounded)

    def test_d_limit_accept_and_one_above_reject_even_if_old_helper_clips(self):
        for low, high in ((0, linear.SCALE_DIFF_Q16_MAX), (-2_000_000_000, linear.SCALE_DIFF_Q16_MAX - 2_000_000_000)):
            values = np.array([[low, high] + [0] * 30], np.int64)
            for got, want in zip(linear.minmax_a8_scalecode_exact(values, input_bits=35), reference_quantize(values, 35), strict=True):
                np.testing.assert_array_equal(got, want)
            values[0, 1] += 1
            self.assertEqual(old_mlp.minmax_a8_quantize_s35(values[0].tolist()).scale_code, 255)
            with self.assertRaisesRegex(linear.MLPLinearFormatError, "D=4269834240"):
                linear.minmax_a8_scalecode_exact(values, input_bits=35)

    def test_s35_width_and_input_bits_rejections(self):
        for value in (-(1 << 34) - 1, 1 << 34):
            with self.assertRaises(linear.MLPLinearFormatError):
                linear.minmax_a8_scalecode_exact(np.full(32, value, np.int64), input_bits=35)
        with self.assertRaises(ValueError):
            linear.minmax_a8_scalecode_exact(np.zeros(32, np.int64), input_bits=32)


class REC576Tests(unittest.TestCase):
    @staticmethod
    def fixture(groups):
        rows = np.arange(16)[:, None]
        cols = np.arange(groups * 32)[None, :]
        q = ((rows * 43 + cols * 17 + 5) % 256).astype(np.uint8)
        group = np.arange(groups)[None, :]
        zp = (rows * 7 + group * 13) % 256
        code = (rows * 11 + group * 19) % 255 + 1
        shift = (rows * 5 + group * 3) % 64
        metadata = (zp | (code << 8) | (shift << 16)).astype(np.uint32)
        return q, metadata

    def test_pack_all_16_rows_all_128_and_448_groups_against_byte_index(self):
        for groups in (128, 448):
            q, metadata = self.fixture(groups)
            actual = linear.pack_a8_rec576(q, metadata)
            self.assertEqual(actual, reference_rec576(q, metadata))
            self.assertEqual(len(actual), groups * 576)

    def test_unpack_independent_448_group_image(self):
        q, metadata = self.fixture(448)
        actual_q, actual_meta = linear.unpack_a8_rec576(reference_rec576(q, metadata), groups=448)
        np.testing.assert_array_equal(actual_q, q)
        np.testing.assert_array_equal(actual_meta, metadata)

    def test_row10_metadata_crosses_beat16_17_and_group7_crosses_4k(self):
        q, metadata = self.fixture(8)
        metadata[10, 7] = 0x231234
        payload = linear.pack_a8_rec576(q, metadata)
        offset = 7 * 576 + 512 + 10 * 3
        self.assertEqual(offset % 576, 542)
        self.assertEqual(payload[offset:offset + 3], b"\x34\x12\x23")
        self.assertEqual((offset % 576) // 32, 16)
        self.assertEqual(((offset % 576) + 2) // 32, 17)
        self.assertEqual(7 * 576, 4032)
        self.assertEqual(payload[4096:4096 + 32], bytes(q[2, 7 * 32:8 * 32]))
        got_q, got_meta = linear.unpack_a8_rec576(payload, groups=8)
        np.testing.assert_array_equal(got_q, q)
        self.assertEqual(int(got_meta[10, 7]), 0x231234)

    def test_padding_and_reserved_bits_rejected(self):
        q, metadata = self.fixture(1)
        good = reference_rec576(q, metadata)
        for offset, value, reason in ((560, 1, "padding"), (575, 255, "padding"), (544, 0x40, "reserved"), (559, 0x80, "reserved")):
            broken = bytearray(good)
            broken[offset] = value
            with self.assertRaisesRegex(linear.MLPLinearFormatError, reason):
                linear.unpack_a8_rec576(broken, groups=1)
        metadata[15, 0] |= 1 << 22
        with self.assertRaisesRegex(linear.MLPLinearFormatError, "reserved"):
            linear.pack_a8_rec576(q, metadata)

    def test_canonical_zero_every_row_and_nonzero_code_one_allowed(self):
        q = np.zeros((16, 32), np.uint8)
        metadata = np.zeros((16, 1), np.uint32)
        self.assertEqual(linear.pack_a8_rec576(q, metadata), bytes(576))
        for row in range(16):
            for kind in ("q", "zp", "shift"):
                bad_q, bad_meta = q.copy(), metadata.copy()
                if kind == "q":
                    bad_q[row, 31] = 1
                else:
                    bad_meta[row, 0] = 1 if kind == "zp" else 1 << 16
                with self.assertRaisesRegex(linear.MLPLinearFormatError, "noncanonical"):
                    linear.pack_a8_rec576(bad_q, bad_meta)
                with self.assertRaisesRegex(linear.MLPLinearFormatError, "noncanonical"):
                    linear.unpack_a8_rec576(reference_rec576(bad_q, bad_meta), groups=1)
        metadata[:] = 1 << 8
        self.assertEqual(len(linear.pack_a8_rec576(q, metadata[:, 0])), 576)

    def test_lengths_missing_extra_beats_and_shape_rejections(self):
        for size in (0, 544, 575, 577, 608):
            with self.assertRaises(linear.MLPLinearFormatError):
                linear.unpack_a8_rec576(bytes(size), groups=1)
        for groups in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                linear.unpack_a8_rec576(bytes(576), groups=groups)
        for q, meta in ((np.zeros((8, 32), np.uint8), np.zeros(8, np.uint32)),
                        (np.zeros((16, 32), np.uint8), np.zeros((16, 2), np.uint32)),
                        (np.full((16, 32), 256), np.zeros(16, np.uint32))):
            with self.assertRaises(linear.MLPLinearFormatError):
                linear.pack_a8_rec576(q, meta)


class OutputCodecAndSwiGLUTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate, cls.up = marked_gu_values()
        cls.gu_payload = reference_gu_payload(cls.gate, cls.up)
        cls.table = old_mlp.build_silu_lut()

    def test_gu_all_896_tiles_both_matrices_all_rows_columns_extrema(self):
        gate, up = linear.unpack_gu_interleaved_s24(self.gu_payload)
        np.testing.assert_array_equal(gate, self.gate)
        np.testing.assert_array_equal(up, self.up)
        self.assertEqual(int(gate[0, 0]), -(1 << 23))
        self.assertEqual(int(up[15, -1]), (1 << 23) - 1)

    def test_gu_last_32_column_block_and_last_u895_byte_indices(self):
        gate, up = linear.unpack_gu_interleaved_s24(self.gu_payload)
        # block48=298 has record indices 0 and 1 -> global tile894 and895.
        for tile in (894, 895):
            for matrix, result in enumerate((gate, up)):
                for row in (0, 10, 15):
                    for lane in range(16):
                        offset = (2 * tile + matrix) * 768 + (row * 16 + lane) * 3
                        expected = int.from_bytes(self.gu_payload[offset:offset + 3], "little", signed=True)
                        self.assertEqual(int(result[row, tile * 16 + lane]), expected)
        self.assertEqual(self.gu_payload[-3:], int(self.up[15, -1]).to_bytes(3, "little", signed=True))

    def test_down_all_256_tiles_all_rows_columns_signed_extrema(self):
        row = np.arange(16, dtype=np.int64)[:, None]
        col = np.arange(4096, dtype=np.int64)[None, :]
        values = ((row * 268435459 + col * 7919) % (1 << 32)) - (1 << 31)
        values[15, -1] = (1 << 31) - 1
        payload = bytearray(262144)
        for tile in range(256):
            for r in range(16):
                for lane in range(16):
                    struct.pack_into("<i", payload, tile * 1024 + (r * 16 + lane) * 4, int(values[r, tile * 16 + lane]))
        np.testing.assert_array_equal(linear.unpack_down_s32(payload), values)

    def test_gu_down_lengths_rejected(self):
        for operation, expected in ((linear.unpack_gu_interleaved_s24, 1376256), (linear.unpack_down_s32, 262144)):
            for delta in (-32, -1, 1, 32):
                with self.assertRaises(linear.MLPLinearFormatError):
                    operation(bytes(expected + delta))

    def test_frozen_rom_sha_and_all_words_against_original_generator(self):
        self.assertEqual(hashlib.sha256(linear.SILU_ROM_PATH.read_bytes()).hexdigest(), linear.SILU_ROM_SHA256)
        self.assertEqual(linear.load_silu_rom(), self.table)
        self.assertEqual(len(linear.load_silu_rom()), 8193)

    def test_silu_every_address_tie_and_endpoints(self):
        # Both sides of every 2^-8 address midpoint, including implicit entry8192.
        base = -linear.SILU_LIMIT_Q16 + np.arange(8192, dtype=np.int64) * 256
        gates = np.concatenate((base + 127, base + 128, base + 129,
                                np.array([-8388608, -1048577, -1048576, -1048575,
                                          1048575, 1048576, 1048577, 8388607])))
        up = np.full(gates.shape, 65536, dtype=np.int64)
        expected = [old_mlp.swiglu_product_s32(int(g), int(u), self.table) for g, u in zip(gates, up, strict=True)]
        np.testing.assert_array_equal(linear.silu_table_mul_exact(gates, up), expected)

    def test_silu_multiply_full_16_rows_positive_negative_and_product_ties(self):
        gate = np.random.default_rng(6020).integers(-1048576, 1048577, (16, 14336), dtype=np.int64)
        up = np.random.default_rng(6021).integers(-8388608, 8388608, gate.shape, dtype=np.int64)
        gate[15, :4] = 1048577  # odd SiLU with +/-32768 produces exact product halves
        up[15, :4] = [32768, -32768, 98304, -98304]
        expected = np.array([old_mlp.swiglu_product_s32(int(g), int(u), self.table)
                             for g, u in zip(gate.ravel(), up.ravel(), strict=True)]).reshape(gate.shape)
        actual = linear.silu_table_mul_exact(gate, up)
        np.testing.assert_array_equal(actual, expected)
        self.assertEqual(actual[15, :4].tolist(), [524289, -524289, 1572866, -1572866])

    def test_silu_s32_extrema_and_invalid_inputs(self):
        gate = np.array([8388607, 8388607], np.int64)
        up = np.array([8388607, -8388608], np.int64)
        expected = [old_mlp.swiglu_product_s32(int(g), int(u), self.table) for g, u in zip(gate, up, strict=True)]
        np.testing.assert_array_equal(linear.silu_table_mul_exact(gate, up), expected)
        with self.assertRaises(linear.MLPLinearFormatError):
            linear.silu_table_mul_exact([1 << 23], [0])
        with self.assertRaises(linear.MLPLinearFormatError):
            linear.silu_table_mul_exact([0], [0, 0])
        with self.assertRaises(TypeError):
            linear.silu_table_mul_exact([0.0], [0])


class ProductionPreparationTests(unittest.TestCase):
    def test_prepare_gu_exact_full_shape_no_rmsnorm(self):
        values = np.random.default_rng(6030).integers(-2_000_000, 2_000_001, (16, 4096), dtype=np.int64)
        q, metadata = reference_quantize(reference_h32(values, 24), 27)
        self.assertEqual(linear.prepare_gate_up_input(values), reference_rec576(q, metadata))
        self.assertEqual(len(linear.prepare_gate_up_input(np.zeros((16, 4096), np.int64))), 73728)
        with self.assertRaises(TypeError):
            linear.prepare_gate_up_input(np.zeros((16, 4096), np.float32))
        with self.assertRaises(linear.MLPLinearFormatError):
            linear.prepare_gate_up_input(np.zeros((8, 4096), np.int64))

    def test_prepare_fp32_adapter_uses_existing_normalized_result(self):
        normalized = np.full((16, 4096), 2.0, np.float32)
        expected = linear.prepare_gate_up_input(np.full((16, 4096), 2 << 16, np.int64))
        self.assertEqual(linear.prepare_gate_up_input_from_normalized_fp32(normalized), expected)

    def test_prepare_down_full_16_rows_448_groups_independent_pipeline(self):
        row = np.arange(16, dtype=np.int64)[:, None]
        col = np.arange(14336, dtype=np.int64)[None, :]
        gate = (row * 7919 + col * 43) % 1048576 - 524288
        up = (row * 15401 + col * 97) % 1048576 - 524288
        payload = reference_gu_payload(gate, up)
        table = old_mlp.build_silu_lut()
        products = np.array([old_mlp.swiglu_product_s32(int(g), int(u), table)
                             for g, u in zip(gate.ravel(), up.ravel(), strict=True)], dtype=np.int64).reshape(gate.shape)
        q, metadata = reference_quantize(reference_h32(products, 32), 35)
        actual = linear.prepare_down_input(payload)
        self.assertEqual(actual, reference_rec576(q, metadata))
        self.assertEqual(len(actual), 258048)

    def test_prepare_down_rejects_real_extreme_gu_without_payload(self):
        gate = np.full((16, 14336), 8388607, np.int64)
        up = np.full((16, 14336), 8388607, np.int64)
        payload = reference_gu_payload(gate, up)
        with mock.patch.object(linear, "pack_a8_rec576", wraps=linear.pack_a8_rec576) as pack:
            with self.assertRaisesRegex(linear.MLPLinearFormatError, "exceeds"):
                linear.prepare_down_input(payload)
            pack.assert_not_called()


if __name__ == "__main__":
    unittest.main()
