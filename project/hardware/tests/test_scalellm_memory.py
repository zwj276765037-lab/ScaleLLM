#!/usr/bin/env python3

import unittest
from unittest.mock import Mock

from host.scalellm_memory import (
    ACTIVATION_INPUT_PAYLOAD_BYTES,
    ACTIVATION_OUTPUT_PAYLOAD_BYTES,
    ACTIVATION_PAYLOAD_BYTES,
    ATTENTION_META_BYTES,
    DDR_CHANNEL_BYTES,
    HOST_APERTURE_BYTES,
    LAYER_STRIDE_BYTES,
    MATRIX_BYTES_PER_CHANNEL,
    MLP_DOWN_META_BYTES,
    MLP_GATE_META_BYTES,
    RUNTIME_BYTES_PER_CHANNEL,
    RUNTIME_LOCAL_BASE,
    RUNTIME_REGIONS,
    activation_base,
    attention_meta_base,
    host_to_local,
    layer_addresses,
    local_to_host,
    matrix_regions,
    mlp_meta_bases,
    validate_frozen_layout,
    MemoryRegion,
    validate_regions,
    mlp_matrix_regions,
    activation_base_for_buffer,
)
from host.scalellm_runtime import XdmaSession


class ScaleLLMMemoryTests(unittest.TestCase):
    def test_frozen_capacity_and_layer_boundaries(self):
        # Original export sizes: two Attention half-groups, 20 MiB each.
        self.assertEqual(LAYER_STRIDE_BYTES, 40 << 20)
        self.assertEqual(MATRIX_BYTES_PER_CHANNEL, 1280 << 20)
        first = layer_addresses(0)
        last = layer_addresses(31)
        self.assertEqual((first.attention_c0, first.attention_c1), (0, 20 << 20))
        self.assertEqual((last.attention_c0, last.attention_c1),
                         (1240 << 20, 1260 << 20))
        for layer in (first, last):
            self.assertEqual((layer.mlp_gate_c0, layer.mlp_gate_c1,
                              layer.mlp_down_c0, layer.mlp_down_c1),
                             (0, 28 << 20, 56 << 20, 70 << 20))
            self.assertTrue(all(value < DDR_CHANNEL_BYTES for value in (
                layer.attention_c0, layer.attention_c1, layer.mlp_gate_c0,
                layer.mlp_gate_c1, layer.mlp_down_c0, layer.mlp_down_c1)))

    def test_matrix_regions_partition_resident_attention_and_single_mlp_layer(self):
        regions = matrix_regions()
        self.assertEqual(len(regions), 64 + 4)
        for channel, count, end in ((0, 64, 1280 << 20), (1, 4, 84 << 20)):
            selected = sorted((r for r in regions if r.channel == channel),
                              key=lambda r: r.local_start)
            self.assertEqual(len(selected), count)
            self.assertEqual(selected[0].local_start, 0)
            self.assertEqual(selected[-1].local_end, end)
            for left, right in zip(selected, selected[1:]):
                self.assertEqual(left.local_end, right.local_start)
        self.assertEqual([r.local_start for r in mlp_matrix_regions(0)],
                         [r.local_start for r in mlp_matrix_regions(31)])
        self.assertGreater(32 * 84 << 20, DDR_CHANNEL_BYTES)

    def test_host_and_engine_address_domains_are_distinct(self):
        local = 0x1234_0000
        self.assertEqual(local_to_host(0, local), local)
        self.assertEqual(local_to_host(1, local), 0x9234_0000)
        self.assertEqual(host_to_local(0x9234_0000), (1, local))
        self.assertEqual(host_to_local(0x1234_0000), (0, local))

    def test_address_translation_rejects_cross_channel_ranges(self):
        with self.assertRaises(ValueError):
            local_to_host(0, DDR_CHANNEL_BYTES - 31, 32)
        with self.assertRaises(ValueError):
            local_to_host(2, 0)
        with self.assertRaises(ValueError):
            host_to_local(HOST_APERTURE_BYTES)
        with self.assertRaises(ValueError):
            layer_addresses(32)

    def test_runtime_slots_fit_exact_payloads(self):
        validate_frozen_layout()
        self.assertEqual(activation_base(0, 0), 0x5600_0000)
        self.assertEqual(activation_base(1, 2), 0x5650_0000)
        self.assertEqual(activation_base_for_buffer(5, "mlp"), 0x0650_0000)
        self.assertEqual(activation_base_for_buffer(5, "mlp", output=True), 0x0658_0000)
        self.assertEqual(ACTIVATION_INPUT_PAYLOAD_BYTES, 192 << 10)
        self.assertEqual(ACTIVATION_OUTPUT_PAYLOAD_BYTES, 256 << 10)
        self.assertEqual(attention_meta_base(0), 0x5680_0000)
        self.assertEqual(attention_meta_base(1), 0x56C0_0000)
        self.assertEqual(mlp_meta_bases(0), (0x0680_0000, 0x06F0_0000))
        self.assertEqual(mlp_meta_bases(1), (0x0740_0000, 0x07B0_0000))
        self.assertEqual(MLP_GATE_META_BYTES + MLP_DOWN_META_BYTES, 21 * (1 << 19))

    def test_all_physical_allocations_do_not_overlap(self):
        for channel in (0, 1):
            ordered = sorted((r for r in matrix_regions() + RUNTIME_REGIONS
                              if r.channel == channel), key=lambda r: r.local_start)
            for left, right in zip(ordered, ordered[1:]):
                self.assertLessEqual(left.local_end, right.local_start)
            self.assertLessEqual(ordered[-1].local_end, DDR_CHANNEL_BYTES)

    def test_intersections_and_crossings_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "overlap"):
            validate_regions((MemoryRegion("outer", 0, 0, 100),
                              MemoryRegion("inner", 0, 40, 5)))
        with self.assertRaisesRegex(ValueError, "overlap"):
            validate_regions((MemoryRegion("left", 1, 10, 20),
                              MemoryRegion("right", 1, 29, 10)))
        validate_regions((MemoryRegion("left", 0, 0, 20),
                          MemoryRegion("touching", 0, 20, 10),
                          MemoryRegion("other_ddr", 1, 0, 20)))
        for args in (("overflow", 0, (2 << 30)-1, 2),
                     ("negative", 1, -1, 1), ("empty", 0, 0, 0),
                     ("bad_channel", 2, 0, 1)):
            with self.assertRaises(ValueError):
                MemoryRegion(*args)
        with self.assertRaises(ValueError):
            local_to_host(0, DDR_CHANNEL_BYTES, 0)

    def test_xdma_local_helpers_apply_host_channel_translation(self):
        session = XdmaSession(event=None)
        session.h2c_write = Mock(return_value=3)
        session.c2h_read = Mock(return_value=b"abc")
        session.c2h_read_into = Mock(return_value=3)
        self.assertEqual(
            session.h2c_write_local(1, b"abc", 0x1000, 4096), 3)
        session.h2c_write.assert_called_once_with(
            b"abc", 0x8000_1000, 4096)
        self.assertEqual(
            session.c2h_read_local(1, 3, 0x2000, 4096), b"abc")
        session.c2h_read.assert_called_once_with(3, 0x8000_2000, 4096)
        destination = bytearray(3)
        self.assertEqual(
            session.c2h_read_into_local(1, destination, 0x3000, 4096), 3
        )
        session.c2h_read_into.assert_called_once_with(
            destination, 0x8000_3000, 4096
        )


if __name__ == "__main__":
    unittest.main()
