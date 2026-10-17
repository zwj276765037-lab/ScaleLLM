#!/usr/bin/env python3

import unittest

import numpy as np

from host.scalellm_hostops import (
    ACTIVATION_SHAPE,
    LlamaNormWeights,
    PinnedActivationPool,
    PinnedBuffer,
    ScaleLLMHostBoundaryOps,
    pack_s24_q16,
    pack_s32_q16,
    rms_norm,
    unpack_s24_q16,
    unpack_s32_q16,
)
from host.scalellm_memory import (
    ACTIVATION_INPUT_PAYLOAD_BYTES,
    ACTIVATION_OUTPUT_PAYLOAD_BYTES,
    activation_base_for_buffer,
)
from host.scalellm_runtime import RuntimeContractError


class MemorySession:
    def __init__(self):
        self.memory = {}

    def h2c_write_local(self, channel, data, local_offset, chunk_bytes):
        self.memory[(channel, local_offset)] = bytes(data)
        return len(data)

    def c2h_read_into_local(
        self, channel, destination, local_offset, chunk_bytes
    ):
        data = self.memory[(channel, local_offset)]
        destination[:] = data
        return len(data)


class ScaleLLMHostOpsTests(unittest.TestCase):
    def test_s24_q16_roundtrip_and_saturation(self):
        values = np.zeros(ACTIVATION_SHAPE, dtype=np.float32)
        values.reshape(-1)[:8] = (
            -200.0, -128.0, -1.5 / 65536.0, -0.5 / 65536.0,
            0.5 / 65536.0, 1.5 / 65536.0, 127.0, 200.0,
        )
        packed = pack_s24_q16(values)
        self.assertEqual(len(packed), ACTIVATION_INPUT_PAYLOAD_BYTES)
        result = unpack_s24_q16(packed).reshape(-1)
        expected = np.array((
            -128.0, -128.0, -2.0 / 65536.0, -1.0 / 65536.0,
            1.0 / 65536.0, 2.0 / 65536.0, 127.0,
            ((1 << 23) - 1) / 65536.0,
        ), dtype=np.float32)
        np.testing.assert_array_equal(result[:8], expected)

    def test_s32_q16_roundtrip_signed_little_endian_and_exact_size(self):
        values = np.zeros(ACTIVATION_SHAPE, dtype=np.float32)
        values.reshape(-1)[:6] = (
            -32768.0, -1.5 / 65536.0, -0.5 / 65536.0,
            0.5 / 65536.0, 1.5 / 65536.0, 32768.0,
        )
        packed = pack_s32_q16(values)
        self.assertEqual(len(packed), ACTIVATION_OUTPUT_PAYLOAD_BYTES)
        self.assertEqual(packed[:4], b"\x00\x00\x00\x80")
        result = unpack_s32_q16(packed).reshape(-1)
        expected = np.array((
            -32768.0, -2.0 / 65536.0, -1.0 / 65536.0,
            1.0 / 65536.0, 2.0 / 65536.0,
            ((1 << 31) - 1) / 65536.0,
        ), dtype=np.float32)
        np.testing.assert_array_equal(result[:6], expected)
        with self.assertRaisesRegex(ValueError, "exactly 256 KiB"):
            unpack_s32_q16(packed[:-1])

    def test_rms_norm_is_float32_and_row_local(self):
        source = np.zeros(ACTIVATION_SHAPE, dtype=np.float32)
        source[0] = 2.0
        source[1] = np.arange(4096, dtype=np.float32) / 4096.0
        weight = np.linspace(0.5, 1.5, 4096, dtype=np.float32)
        result = rms_norm(source, weight, 1e-5)
        self.assertEqual(result.dtype, np.float32)
        expected0 = 2.0 / np.sqrt(np.float32(4.0 + 1e-5)) * weight
        np.testing.assert_allclose(result[0], expected0, rtol=2e-7, atol=0)
        np.testing.assert_array_equal(result[2], np.zeros(4096, np.float32))

    def test_pinned_buffer_is_writable(self):
        with PinnedBuffer(4096, require_lock=True) as buffer:
            self.assertTrue(buffer.locked)
            self.assertEqual(buffer.address % 4096, 0)
            buffer.view[:4] = b"HAP5"
            self.assertEqual(bytes(buffer.view[:4]), b"HAP5")

    def test_host_boundaries_preserve_residual_and_rotate_buffer(self):
        session = MemorySession()
        weights = LlamaNormWeights(
            np.ones((32, 4096), dtype=np.float32),
            np.ones((32, 4096), dtype=np.float32),
            np.ones(4096, dtype=np.float32),
        )
        with PinnedActivationPool(
            session, require_lock=True
        ) as transfers:
            host = ScaleLLMHostBoundaryOps(transfers, weights)
            initial = np.full(ACTIVATION_SHAPE, 0.25, dtype=np.float32)
            host.prepare_cohort(7, 0, initial)
            self.assertEqual(host.states[7], (0, "attention"))

            attention_output = np.full(
                ACTIVATION_SHAPE, 0.125, dtype=np.float32
            )
            session.memory[(0, 0x56080000)] = pack_s24_q16(attention_output)
            host.after_attention(7, 0, 0)
            self.assertEqual(host.states[7], (0, "mlp"))

            mlp_output = np.full(ACTIVATION_SHAPE, -0.0625, dtype=np.float32)
            session.memory[(1, 0x06080000)] = \
                pack_s32_q16(mlp_output)
            host.after_mlp(7, 0, 0)
            self.assertEqual(host.states[7], (1, "attention"))
            expected_hidden = np.full(
                ACTIVATION_SHAPE, 0.3125, dtype=np.float32
            )
            np.testing.assert_array_equal(host._residuals[7], expected_hidden)
            self.assertIn((0, 0x5610_0000), session.memory)
            self.assertEqual([(t.stage, t.channel, t.local_offset) for t in transfers.transfers],
                             [("before_attention", 0, 0x56000000),
                              ("after_attention", 0, 0x56080000),
                              ("before_mlp", 1, 0x06000000),
                              ("after_mlp", 1, 0x06080000),
                              ("before_attention", 0, 0x56100000)])

            with self.assertRaises(RuntimeContractError):
                host.after_mlp(7, 0, 0)


if __name__ == "__main__":
    unittest.main()
