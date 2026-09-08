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
    rms_norm,
    unpack_s24_q16,
)
from host.scalellm_memory import ACTIVATION_PAYLOAD_BYTES
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
        self.assertEqual(len(packed), ACTIVATION_PAYLOAD_BYTES)
        result = unpack_s24_q16(packed).reshape(-1)
        expected = np.array((
            -128.0, -128.0, -2.0 / 65536.0, -1.0 / 65536.0,
            1.0 / 65536.0, 2.0 / 65536.0, 127.0,
            ((1 << 23) - 1) / 65536.0,
        ), dtype=np.float32)
        np.testing.assert_array_equal(result[:8], expected)

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
            transfers.write(attention_output, 7, 0, "fixture", 0)
            host.after_attention(7, 0, 0)
            self.assertEqual(host.states[7], (0, "mlp"))

            mlp_output = np.full(ACTIVATION_SHAPE, -0.0625, dtype=np.float32)
            transfers.write(mlp_output, 7, 0, "fixture", 0)
            host.after_mlp(7, 0, 0)
            self.assertEqual(host.states[7], (1, "attention"))
            expected_hidden = np.full(
                ACTIVATION_SHAPE, 0.3125, dtype=np.float32
            )
            np.testing.assert_array_equal(host._residuals[7], expected_hidden)
            self.assertIn((0, 0x7C10_0000), session.memory)

            with self.assertRaises(RuntimeContractError):
                host.after_mlp(7, 0, 0)


if __name__ == "__main__":
    unittest.main()
