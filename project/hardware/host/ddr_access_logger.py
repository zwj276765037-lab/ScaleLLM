#!/usr/bin/env python3
"""
DDR 访问验证工具 (M002)

用于验证 Attention 和 MLP 是否正确分离到 DDR0/DDR1
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Dict, Any
from scalellm_memory import DDR1_HOST_BASE


@dataclass
class DDRAccess:
    """DDR 访问记录"""
    timestamp: float
    channel: int  # 0 = DDR0, 1 = DDR1
    operation: str  # "attention_input", "mlp_output", etc.
    address: int  # Host address
    size: int  # Bytes
    cohort: int = -1
    slot: int = -1
    layer: int = -1


class DDRAccessLogger:
    """DDR 访问日志记录器"""

    def __init__(self):
        self._log: List[DDRAccess] = []
        self._enabled = True

    def enable(self):
        """启用日志记录"""
        self._enabled = True

    def disable(self):
        """禁用日志记录"""
        self._enabled = False

    def clear(self):
        """清空日志"""
        self._log.clear()

    def log_access(self,
                   operation: str,
                   address: int,
                   size: int,
                   cohort: int = -1,
                   slot: int = -1,
                   layer: int = -1):
        """记录一次 DDR 访问"""
        if not self._enabled:
            return

        # 判断通道
        channel = 0 if address < DDR1_HOST_BASE else 1

        access = DDRAccess(
            timestamp=time.time(),
            channel=channel,
            operation=operation,
            address=address,
            size=size,
            cohort=cohort,
            slot=slot,
            layer=layer,
        )

        self._log.append(access)

    def get_all_accesses(self) -> List[DDRAccess]:
        """获取所有访问记录"""
        return self._log.copy()

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self._log:
            return {
                "total_accesses": 0,
                "ddr0_accesses": 0,
                "ddr1_accesses": 0,
                "ddr0_bytes": 0,
                "ddr1_bytes": 0,
                "separation_ok": True,
                "violations": [],
            }

        ddr0_accesses = [a for a in self._log if a.channel == 0]
        ddr1_accesses = [a for a in self._log if a.channel == 1]

        ddr0_bytes = sum(a.size for a in ddr0_accesses)
        ddr1_bytes = sum(a.size for a in ddr1_accesses)

        # 检查分离违规
        violations = []

        # Attention 应该只在 DDR0
        attention_ops = ["attention_input", "attention_output", "attention_weights",
                        "kv_cache", "attention_meta"]
        for access in self._log:
            if any(op in access.operation for op in attention_ops):
                if access.channel != 0:
                    violations.append({
                        "operation": access.operation,
                        "expected_channel": 0,
                        "actual_channel": access.channel,
                        "address": f"0x{access.address:08X}",
                    })

        # MLP 应该只在 DDR1
        mlp_ops = ["mlp_input", "mlp_output", "mlp_weights", "mlp_meta"]
        for access in self._log:
            if any(op in access.operation for op in mlp_ops):
                if access.channel != 1:
                    violations.append({
                        "operation": access.operation,
                        "expected_channel": 1,
                        "actual_channel": access.channel,
                        "address": f"0x{access.address:08X}",
                    })

        return {
            "total_accesses": len(self._log),
            "ddr0_accesses": len(ddr0_accesses),
            "ddr1_accesses": len(ddr1_accesses),
            "ddr0_bytes": ddr0_bytes,
            "ddr1_bytes": ddr1_bytes,
            "ddr0_percentage": len(ddr0_accesses) / len(self._log) * 100 if self._log else 0,
            "ddr1_percentage": len(ddr1_accesses) / len(self._log) * 100 if self._log else 0,
            "separation_ok": len(violations) == 0,
            "violations": violations,
        }

    def print_summary(self):
        """打印统计摘要"""
        stats = self.get_statistics()

        print("=" * 80)
        print("DDR 访问统计摘要")
        print("=" * 80)
        print(f"总访问次数: {stats['total_accesses']}")
        print(f"  DDR0 (Attention): {stats['ddr0_accesses']} 次 ({stats['ddr0_percentage']:.1f}%)")
        print(f"  DDR1 (MLP):       {stats['ddr1_accesses']} 次 ({stats['ddr1_percentage']:.1f}%)")
        print(f"总传输字节:")
        print(f"  DDR0: {stats['ddr0_bytes']:,} bytes ({stats['ddr0_bytes'] / (1024**2):.2f} MiB)")
        print(f"  DDR1: {stats['ddr1_bytes']:,} bytes ({stats['ddr1_bytes'] / (1024**2):.2f} MiB)")

        if stats['separation_ok']:
            print("\n✅ DDR 分离验证通过：Attention 仅访问 DDR0，MLP 仅访问 DDR1")
        else:
            print(f"\n❌ DDR 分离验证失败：发现 {len(stats['violations'])} 个违规")
            for v in stats['violations']:
                print(f"  - {v['operation']}: 期望 DDR{v['expected_channel']}, "
                      f"实际 DDR{v['actual_channel']} (地址 {v['address']})")

        print("=" * 80)

    def print_access_log(self, limit: int = 20):
        """打印访问日志（最近 N 条）"""
        print("\n最近的 DDR 访问记录:")
        print("-" * 100)
        print(f"{'时间':>12} | {'通道':>4} | {'操作':<20} | {'地址':>10} | {'大小':>10} | Cohort | Slot | Layer")
        print("-" * 100)

        recent = self._log[-limit:] if len(self._log) > limit else self._log
        for access in recent:
            ts_str = f"{access.timestamp:.3f}"[-12:]
            channel_str = f"DDR{access.channel}"
            addr_str = f"0x{access.address:08X}"
            size_str = f"{access.size:,}"
            cohort_str = str(access.cohort) if access.cohort >= 0 else "-"
            slot_str = str(access.slot) if access.slot >= 0 else "-"
            layer_str = str(access.layer) if access.layer >= 0 else "-"

            print(f"{ts_str:>12} | {channel_str:>4} | {access.operation:<20} | "
                  f"{addr_str:>10} | {size_str:>10} | {cohort_str:>6} | {slot_str:>4} | {layer_str:>5}")


# 全局单例
_global_logger = DDRAccessLogger()


def get_global_logger() -> DDRAccessLogger:
    """获取全局 DDR 访问日志记录器"""
    return _global_logger


def log_ddr_access(operation: str, address: int, size: int, **kwargs):
    """便捷函数：记录 DDR 访问"""
    _global_logger.log_access(operation, address, size, **kwargs)


def validate_ddr_separation() -> bool:
    """便捷函数：验证 DDR 分离"""
    stats = _global_logger.get_statistics()
    return stats['separation_ok']


def print_ddr_summary():
    """便捷函数：打印统计摘要"""
    _global_logger.print_summary()


# 测试代码
if __name__ == "__main__":
    from scalellm_memory import (
        attention_input_base,
        attention_output_base,
        mlp_input_base,
        mlp_output_base,
        layer_addresses,
    )

    logger = get_global_logger()

    # 模拟一些访问
    print("模拟 DDR 访问...")

    # Layer 0 Attention
    addrs = layer_addresses(0)
    log_ddr_access("attention_weights", addrs.attention_weights, 20 * 1024 * 1024, layer=0)

    attn_in = attention_input_base(0, 0)
    log_ddr_access("attention_input", attn_in, 192 * 1024, cohort=0, slot=0, layer=0)

    attn_out = attention_output_base(0, 0)
    log_ddr_access("attention_output", attn_out, 192 * 1024, cohort=0, slot=0, layer=0)

    # Layer 0 MLP
    log_ddr_access("mlp_weights", addrs.mlp_weights, 88 * 1024 * 1024, layer=0)

    mlp_in = mlp_input_base(0, 0)
    log_ddr_access("mlp_input", mlp_in, 192 * 1024, cohort=0, slot=0, layer=0)

    mlp_out = mlp_output_base(0, 0)
    log_ddr_access("mlp_output", mlp_out, 256 * 1024, cohort=0, slot=0, layer=0)

    # 打印结果
    logger.print_access_log()
    print()
    logger.print_summary()

    # 验证
    if validate_ddr_separation():
        print("\n✅ 测试通过")
    else:
        print("\n❌ 测试失败")
