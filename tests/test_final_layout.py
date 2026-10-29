"""Final runtime CPU/mock regression; no FPGA or licensed model files."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "project/hardware"))

import struct
import unittest

import numpy as np

from host.scalellm_final_layout import (
    ATTENTION_OUTPUT_BYTES, HIDDEN, INTERMEDIATE, KV_BASE, KV_BYTES,
    MLP_OUTPUT_BYTES, Span, pack_input_s24, pack_mlp_s32, pack_normalized_fp32, static_spans,
    tensor_spans, unpack_attention_s24, unpack_mlp_s32,
)


class FinalLayoutTests(unittest.TestCase):
    def test_normalized_fp32_matches_original_host_rounding_boundary(self):
        from host.scalellm_hostops import pack_s24_q16
        values = np.random.default_rng(10627).uniform(-127, 127, (16, HIDDEN)).astype(np.float32)
        values[0, :8] = np.asarray([-128, 128, -0.5 / 65536, 0.5 / 65536,
                                    -1.5 / 65536, 1.5 / 65536, -0.0, 0.0], dtype=np.float32)
        self.assertEqual(pack_normalized_fp32(values), pack_s24_q16(values))

    def test_full_reservation_and_staging_no_overlap(self):
        spans = static_spans()
        kv = next(span for span in spans if span.name == "persistent KV")
        self.assertEqual((kv.channel, kv.address, kv.size), (0, KV_BASE, KV_BYTES))
        self.assertEqual(kv.address + kv.size, 0x70000000)
        self.assertEqual(tensor_spans(5)["mlp_output"].address, 0x12900000)
        self.assertEqual(tensor_spans(0)["mlp_input"].host_address, 0x90000000)
        self.assertEqual(tensor_spans(0)["mlp_output"].size, 917504)

    def test_input_s24_signed_row_order_and_inactive_zero(self):
        values = np.arange(16 * HIDDEN, dtype=np.int64).reshape(16, HIDDEN)
        values[0, :5] = [-(1 << 23), -1, 0, 1, (1 << 23) - 1]
        payload = pack_input_s24(values, 0x8001)
        self.assertEqual(len(payload), ATTENTION_OUTPUT_BYTES)
        self.assertEqual(payload[:15], bytes.fromhex(
            "000080 ffffff 000000 010000 ffff7f"))
        self.assertEqual(int.from_bytes(payload[15 * HIDDEN * 3:][:3], "little"),
                         int(values[15, 0]))
        decoded = unpack_attention_s24(payload)
        np.testing.assert_array_equal(decoded[0], values[0])
        np.testing.assert_array_equal(decoded[15], values[15])
        self.assertFalse(np.any(decoded[1:15]))

    def test_product_wire_order_independently_indexed(self):
        rows, cols = np.indices((16, INTERMEDIATE))
        values = (rows * 100000 + cols).astype(np.int64)
        values[0, 0] = -(1 << 31)
        values[15, -1] = (1 << 31) - 1
        payload = pack_mlp_s32(values)
        self.assertEqual(len(payload), MLP_OUTPUT_BYTES)
        for slot, column in ((0, 0), (15, 15), (0, 16), (9, 7341), (15, 14335)):
            tile, lane = divmod(column, 16)
            byte_offset = ((tile * 16 + slot) * 16 + lane) * 4
            self.assertEqual(struct.unpack_from("<i", payload, byte_offset)[0],
                             int(values[slot, column]))
        np.testing.assert_array_equal(unpack_mlp_s32(payload), values)

    def test_product_inactive_rows_zero(self):
        payload = pack_mlp_s32(np.ones((16, INTERMEDIATE), dtype=np.int32), 0x100)
        data = unpack_mlp_s32(payload)
        self.assertTrue(np.all(data[8] == 1))
        self.assertEqual(np.count_nonzero(data), INTERMEDIATE)

    def test_rejects_bad_tensor_range_lengths_and_slots(self):
        values = np.zeros((16, HIDDEN), dtype=np.int64)
        values[7, 1] = 1 << 23
        with self.assertRaises(ValueError): pack_input_s24(values)
        with self.assertRaises(ValueError): pack_input_s24(values.astype(float))
        with self.assertRaises(ValueError): unpack_mlp_s32(bytes(1376256))
        with self.assertRaises(ValueError): unpack_attention_s24(bytes(32))
        with self.assertRaises(ValueError): tensor_spans(6)
        with self.assertRaises(ValueError): Span("bad", 1, 0x7fffffe0, 64)


if __name__ == "__main__":
    unittest.main()
