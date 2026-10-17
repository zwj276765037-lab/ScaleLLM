#!/usr/bin/env python3
"""
Unit tests for ScaleLLM DDR 双通道分离地址映射 (M002)

测试目标:
  1. 验证 DDR0/DDR1 地址完全分离
  2. 验证 Attention 仅使用 DDR0
  3. 验证 MLP 仅使用 DDR1
  4. 验证地址转换正确性
"""

import unittest
from host.scalellm_memory import (
    DDR0_HOST_BASE,
    DDR1_HOST_BASE,
    DDR_CHANNEL_BYTES,
    local_to_host,
    host_to_local,
    layer_addresses,
    attention_input_base,
    attention_output_base,
    mlp_input_base,
    mlp_output_base,
    kv_cache_base,
    attention_meta_base,
    mlp_meta_base,
    validate_address_separation,
)


class TestDDRAddressSeparation(unittest.TestCase):
    """测试 DDR0/DDR1 地址分离"""

    def test_validate_separation(self):
        """测试地址分离验证函数"""
        # 应该不抛出异常
        self.assertTrue(validate_address_separation())

    def test_ddr0_all_below_boundary(self):
        """测试所有 DDR0 地址 < DDR1_HOST_BASE"""
        # Attention 所有地址应该 < 0x80000000
        for layer_id in range(32):
            addrs = layer_addresses(layer_id)
            self.assertLess(addrs.attention_weights, DDR1_HOST_BASE,
                          f"Layer {layer_id} Attention weights should be in DDR0")

        # Attention I/O buffers
        for cohort in [0, 1]:
            for slot in [0, 1, 2]:
                attn_in = attention_input_base(cohort, slot)
                attn_out = attention_output_base(cohort, slot)

                self.assertLess(attn_in, DDR1_HOST_BASE,
                              f"Attention input cohort={cohort} slot={slot} should be in DDR0")
                self.assertLess(attn_out, DDR1_HOST_BASE,
                              f"Attention output cohort={cohort} slot={slot} should be in DDR0")

        # KV cache
        kv_addr = kv_cache_base()
        self.assertLess(kv_addr, DDR1_HOST_BASE, "KV cache should be in DDR0")

        # Attention metadata
        for bank in [0, 1]:
            meta_addr = attention_meta_base(bank)
            self.assertLess(meta_addr, DDR1_HOST_BASE,
                          f"Attention metadata bank {bank} should be in DDR0")

    def test_ddr1_all_above_boundary(self):
        """测试所有 DDR1 地址 >= DDR1_HOST_BASE"""
        # MLP 所有地址应该 >= 0x80000000
        for layer_id in range(32):
            addrs = layer_addresses(layer_id)
            self.assertGreaterEqual(addrs.mlp_weights, DDR1_HOST_BASE,
                                   f"Layer {layer_id} MLP weights should be in DDR1")

        # MLP I/O buffers
        for cohort in [0, 1]:
            for slot in [0, 1, 2]:
                mlp_in = mlp_input_base(cohort, slot)
                mlp_out = mlp_output_base(cohort, slot)

                self.assertGreaterEqual(mlp_in, DDR1_HOST_BASE,
                                      f"MLP input cohort={cohort} slot={slot} should be in DDR1")
                self.assertGreaterEqual(mlp_out, DDR1_HOST_BASE,
                                      f"MLP output cohort={cohort} slot={slot} should be in DDR1")

        # MLP metadata
        for bank in [0, 1]:
            meta_addr = mlp_meta_base(bank)
            self.assertGreaterEqual(meta_addr, DDR1_HOST_BASE,
                                  f"MLP metadata bank {bank} should be in DDR1")


class TestAddressConversion(unittest.TestCase):
    """测试地址转换函数"""

    def test_local_to_host_ddr0(self):
        """测试 DDR0 本地地址到 Host 地址转换"""
        # DDR0: channel=0, local=0x1000 → host=0x00001000
        host_addr = local_to_host(0, 0x1000, 0x100)
        self.assertEqual(host_addr, 0x00001000)

        # DDR0: channel=0, local=0x20000000 → host=0x20000000
        host_addr = local_to_host(0, 0x20000000, 0x100)
        self.assertEqual(host_addr, 0x20000000)

    def test_local_to_host_ddr1(self):
        """测试 DDR1 本地地址到 Host 地址转换"""
        # DDR1: channel=1, local=0x1000 → host=0x80001000
        host_addr = local_to_host(1, 0x1000, 0x100)
        self.assertEqual(host_addr, 0x80001000)

        # DDR1: channel=1, local=0x20000000 → host=0xA0000000
        host_addr = local_to_host(1, 0x20000000, 0x100)
        self.assertEqual(host_addr, 0xA0000000)

    def test_host_to_local_ddr0(self):
        """测试 Host 地址到 DDR0 本地地址转换"""
        # host=0x00001000 → channel=0, local=0x1000
        channel, local = host_to_local(0x00001000, 0x100)
        self.assertEqual(channel, 0)
        self.assertEqual(local, 0x1000)

        # host=0x20000000 → channel=0, local=0x20000000
        channel, local = host_to_local(0x20000000, 0x100)
        self.assertEqual(channel, 0)
        self.assertEqual(local, 0x20000000)

    def test_host_to_local_ddr1(self):
        """测试 Host 地址到 DDR1 本地地址转换"""
        # host=0x80001000 → channel=1, local=0x1000
        channel, local = host_to_local(0x80001000, 0x100)
        self.assertEqual(channel, 1)
        self.assertEqual(local, 0x1000)

        # host=0xA0000000 → channel=1, local=0x20000000
        channel, local = host_to_local(0xA0000000, 0x100)
        self.assertEqual(channel, 1)
        self.assertEqual(local, 0x20000000)

    def test_round_trip_conversion(self):
        """测试地址转换往返一致性"""
        test_cases = [
            (0, 0x00000000),
            (0, 0x10000000),
            (0, 0x7FF00000),
            (1, 0x00000000),
            (1, 0x10000000),
            (1, 0x7FF00000),
        ]

        for channel, local_offset in test_cases:
            # local → host → local
            host_addr = local_to_host(channel, local_offset, 0x1000)
            recovered_channel, recovered_local = host_to_local(host_addr, 0x1000)

            self.assertEqual(recovered_channel, channel,
                           f"Channel mismatch for channel={channel}, local=0x{local_offset:x}")
            self.assertEqual(recovered_local, local_offset,
                           f"Local offset mismatch for channel={channel}, local=0x{local_offset:x}")


class TestLayerAddresses(unittest.TestCase):
    """测试每层地址分配"""

    def test_layer_0(self):
        """测试 Layer 0 地址"""
        addrs = layer_addresses(0)
        self.assertEqual(addrs.layer_id, 0)
        self.assertEqual(addrs.attention_weights, 0x00000000)  # DDR0 base
        self.assertEqual(addrs.mlp_weights, 0x80000000)  # DDR1 base

    def test_layer_31(self):
        """测试 Layer 31 地址"""
        addrs = layer_addresses(31)
        self.assertEqual(addrs.layer_id, 31)
        # Attention: 31 * 40 MiB = 1240 MiB = 0x4D800000
        self.assertEqual(addrs.attention_weights, 0x4D800000)
        # MLP: 固定在 DDR1 base（单层加载策略）
        self.assertEqual(addrs.mlp_weights, 0x80000000)

    def test_all_layers_valid(self):
        """测试所有 32 层地址有效"""
        for layer_id in range(32):
            addrs = layer_addresses(layer_id)
            self.assertEqual(addrs.layer_id, layer_id)

            # Attention 在 DDR0
            self.assertLess(addrs.attention_weights, DDR1_HOST_BASE)

            # MLP 在 DDR1
            self.assertGreaterEqual(addrs.mlp_weights, DDR1_HOST_BASE)

    def test_invalid_layer_id(self):
        """测试无效 layer_id 抛出异常"""
        with self.assertRaises(ValueError):
            layer_addresses(-1)

        with self.assertRaises(ValueError):
            layer_addresses(32)


class TestBufferAddresses(unittest.TestCase):
    """测试 Buffer 地址分配"""

    def test_attention_buffers_in_ddr0(self):
        """测试 Attention buffers 在 DDR0"""
        for cohort in [0, 1]:
            for slot in [0, 1, 2]:
                attn_in = attention_input_base(cohort, slot)
                attn_out = attention_output_base(cohort, slot)

                # 应该在 DDR0
                self.assertLess(attn_in, DDR1_HOST_BASE)
                self.assertLess(attn_out, DDR1_HOST_BASE)

                # 应该在预期范围
                self.assertGreaterEqual(attn_in, 0x56000000)  # DDR0_ATTENTION_INPUT_BASE
                self.assertGreaterEqual(attn_out, 0x56080000)  # DDR0_ATTENTION_OUTPUT_BASE

    def test_mlp_buffers_in_ddr1(self):
        """测试 MLP buffers 在 DDR1"""
        for cohort in [0, 1]:
            for slot in [0, 1, 2]:
                mlp_in = mlp_input_base(cohort, slot)
                mlp_out = mlp_output_base(cohort, slot)

                # 应该在 DDR1
                self.assertGreaterEqual(mlp_in, DDR1_HOST_BASE)
                self.assertGreaterEqual(mlp_out, DDR1_HOST_BASE)

                # 应该在预期范围
                self.assertGreaterEqual(mlp_in, 0x86000000)  # DDR1_MLP_INPUT_BASE (host)
                self.assertGreaterEqual(mlp_out, 0x86080000)  # DDR1_MLP_OUTPUT_BASE (host)

    def test_buffer_no_overlap(self):
        """测试 buffers 之间无重叠"""
        # 收集所有地址和大小
        buffers = []

        # Attention buffers (192 KiB each)
        for cohort in [0, 1]:
            for slot in [0, 1, 2]:
                attn_in = attention_input_base(cohort, slot)
                attn_out = attention_output_base(cohort, slot)
                buffers.append((attn_in, 192 * 1024, "attn_in"))
                buffers.append((attn_out, 192 * 1024, "attn_out"))

        # MLP buffers (192 KiB input, 256 KiB output)
        for cohort in [0, 1]:
            for slot in [0, 1, 2]:
                mlp_in = mlp_input_base(cohort, slot)
                mlp_out = mlp_output_base(cohort, slot)
                buffers.append((mlp_in, 192 * 1024, "mlp_in"))
                buffers.append((mlp_out, 256 * 1024, "mlp_out"))

        # 检查重叠
        buffers.sort()
        for i in range(len(buffers) - 1):
            addr1, size1, name1 = buffers[i]
            addr2, size2, name2 = buffers[i + 1]

            end1 = addr1 + size1
            self.assertLessEqual(end1, addr2,
                               f"Buffer overlap: {name1} [0x{addr1:x}, 0x{end1:x}) "
                               f"vs {name2} [0x{addr2:x}, ...)")

    def test_invalid_cohort_slot(self):
        """测试无效 cohort/slot 抛出异常"""
        # Invalid cohort
        with self.assertRaises(ValueError):
            attention_input_base(2, 0)

        with self.assertRaises(ValueError):
            mlp_input_base(-1, 0)

        # Invalid slot
        with self.assertRaises(ValueError):
            attention_output_base(0, 3)

        with self.assertRaises(ValueError):
            mlp_output_base(0, -1)


class TestKVCacheAndMetadata(unittest.TestCase):
    """测试 KV Cache 和 Metadata 地址"""

    def test_kv_cache_in_ddr0(self):
        """测试 KV cache 在 DDR0"""
        kv_addr = kv_cache_base()
        self.assertLess(kv_addr, DDR1_HOST_BASE)
        self.assertEqual(kv_addr, 0x50000000)  # DDR0_KV_CACHE_BASE

    def test_attention_meta_in_ddr0(self):
        """测试 Attention metadata 在 DDR0"""
        for bank in [0, 1]:
            meta_addr = attention_meta_base(bank)
            self.assertLess(meta_addr, DDR1_HOST_BASE)
            self.assertGreaterEqual(meta_addr, 0x56800000)  # DDR0_ATTENTION_META_BASE

    def test_mlp_meta_in_ddr1(self):
        """测试 MLP metadata 在 DDR1"""
        for bank in [0, 1]:
            meta_addr = mlp_meta_base(bank)
            self.assertGreaterEqual(meta_addr, DDR1_HOST_BASE)
            self.assertGreaterEqual(meta_addr, 0x86800000)  # DDR1_MLP_META_BASE (host)


class TestBoundaryConditions(unittest.TestCase):
    """测试边界条件"""

    def test_ddr_channel_boundary(self):
        """测试 DDR 通道边界"""
        # DDR0 最大地址应该 < 2 GiB (local)
        # DDR0 最大 host 地址应该 < DDR1_HOST_BASE
        max_ddr0_local = DDR_CHANNEL_BYTES - 1
        max_ddr0_host = local_to_host(0, max_ddr0_local)
        self.assertLess(max_ddr0_host, DDR1_HOST_BASE)

        # DDR1 base 应该正好是 DDR1_HOST_BASE
        ddr1_base = local_to_host(1, 0)
        self.assertEqual(ddr1_base, DDR1_HOST_BASE)

    def test_address_overflow_detection(self):
        """测试地址溢出检测"""
        # 超过 2 GiB 应该抛出异常
        with self.assertRaises(ValueError):
            local_to_host(0, DDR_CHANNEL_BYTES, 1)

        with self.assertRaises(ValueError):
            local_to_host(1, DDR_CHANNEL_BYTES, 1)

        # 负数地址应该抛出异常
        with self.assertRaises(ValueError):
            local_to_host(0, -1)

        # 无效通道应该抛出异常
        with self.assertRaises(ValueError):
            local_to_host(2, 0)


if __name__ == "__main__":
    # 运行所有测试
    unittest.main(verbosity=2)
