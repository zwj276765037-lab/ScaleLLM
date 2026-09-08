#!/usr/bin/env python3

import unittest
from unittest.mock import Mock

from host.scalellm_memory import (
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
)
from host.scalellm_runtime import XdmaSession


class ScaleLLMMemoryTests(unittest.TestCase):
    def test_frozen_capacity_and_layer_boundaries(self):
        self.assertEqual(LAYER_STRIDE_BYTES, 0x03E0_0000)
        self.assertEqual(MATRIX_BYTES_PER_CHANNEL, 0x7C00_0000)
        self.assertEqual(RUNTIME_LOCAL_BASE, 0x7C00_0000)
        self.assertEqual(RUNTIME_BYTES_PER_CHANNEL, 64 << 20)
        first = layer_addresses(0)
        self.assertEqual(first.attention_c0, 0x0000_0000)
        self.assertEqual(first.mlp_gate_c0, 0x0140_0000)
        self.assertEqual(first.mlp_down_c0, 0x0300_0000)
        last = layer_addresses(31)
        self.assertEqual(last.attention_c0, 0x7820_0000)
        self.assertEqual(last.mlp_gate_c0, 0x7960_0000)
        self.assertEqual(last.mlp_down_c0, 0x7B20_0000)

    def test_matrix_regions_exactly_partition_both_channels(self):
        regions = matrix_regions()
        self.assertEqual(len(regions), 32 * 2 * 3)
        for channel in (0, 1):
            channel_regions = sorted(
                (region for region in regions if region.channel == channel),
                key=lambda region: region.local_start,
            )
            self.assertEqual(channel_regions[0].local_start, 0)
            self.assertEqual(channel_regions[-1].local_end,
                             RUNTIME_LOCAL_BASE)
            for left, right in zip(channel_regions, channel_regions[1:]):
                self.assertEqual(left.local_end, right.local_start)

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
        self.assertEqual(activation_base(0, 0), 0x7C00_0000)
        self.assertEqual(activation_base(1, 2), 0x7C50_0000)
        self.assertLessEqual(ACTIVATION_PAYLOAD_BYTES, 1 << 20)
        self.assertEqual(attention_meta_base(0), 0x7C80_0000)
        self.assertEqual(attention_meta_base(1), 0x7CC0_0000)
        self.assertLessEqual(ATTENTION_META_BYTES, 4 << 20)
        self.assertEqual(mlp_meta_bases(0), (0x7D00_0000, 0x7D70_0000))
        self.assertEqual(mlp_meta_bases(1), (0x7DC0_0000, 0x7E30_0000))
        self.assertEqual(MLP_GATE_META_BYTES + MLP_DOWN_META_BYTES,
                         21 * (1 << 19))

    def test_runtime_regions_do_not_overlap(self):
        ordered = sorted(RUNTIME_REGIONS, key=lambda region: region.local_start)
        for left, right in zip(ordered, ordered[1:]):
            self.assertLessEqual(left.local_end, right.local_start)
        self.assertLessEqual(ordered[-1].local_end, DDR_CHANNEL_BYTES)

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
