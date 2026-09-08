#!/usr/bin/env python3
"""Frozen VCU118 dual-DDR address layout for ScaleLLM."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


KIB = 1 << 10
MIB = 1 << 20
GIB = 1 << 30

DDR_CHANNELS = 2
DDR_CHANNEL_BYTES = 2 * GIB
DDR0_HOST_BASE = 0x0000_0000
DDR1_HOST_BASE = 0x8000_0000
HOST_APERTURE_BYTES = 4 * GIB

LAYER_COUNT = 32
LAYER_STRIDE_BYTES = 62 * MIB
ATTENTION_BYTES_PER_CHANNEL = 20 * MIB
MLP_GATE_UP_BYTES_PER_CHANNEL = 28 * MIB
MLP_DOWN_BYTES_PER_CHANNEL = 14 * MIB
MATRIX_BYTES_PER_CHANNEL = LAYER_COUNT * LAYER_STRIDE_BYTES
RUNTIME_LOCAL_BASE = MATRIX_BYTES_PER_CHANNEL
RUNTIME_BYTES_PER_CHANNEL = DDR_CHANNEL_BYTES - RUNTIME_LOCAL_BASE

ACTIVATION_ROWS = 16
ACTIVATION_COLUMNS = 4096
ACTIVATION_ELEMENT_BYTES = 3
ACTIVATION_PAYLOAD_BYTES = (
    ACTIVATION_ROWS * ACTIVATION_COLUMNS * ACTIVATION_ELEMENT_BYTES
)
ACTIVATION_SLOT_BYTES = 1 * MIB
ATTENTION_META_BYTES = 2_621_440
ATTENTION_META_SLOT_BYTES = 4 * MIB
MLP_GATE_META_BYTES = 7 * MIB
MLP_DOWN_META_BYTES = 3_670_016
MLP_META_SLOT_BYTES = 12 * MIB
ROPE_BYTES = 8 * KIB


@dataclass(frozen=True)
class MemoryRegion:
    name: str
    channel: int
    local_start: int
    size: int

    def __post_init__(self) -> None:
        if self.channel not in range(DDR_CHANNELS):
            raise ValueError(f"invalid DDR channel {self.channel}")
        if self.local_start < 0 or self.size <= 0:
            raise ValueError(f"invalid region {self.name}")
        if self.local_end > DDR_CHANNEL_BYTES:
            raise ValueError(f"region {self.name} exceeds DDR channel")

    @property
    def local_end(self) -> int:
        return self.local_start + self.size

    @property
    def host_start(self) -> int:
        return local_to_host(self.channel, self.local_start, self.size)

    @property
    def host_end(self) -> int:
        return self.host_start + self.size


@dataclass(frozen=True)
class LayerAddresses:
    layer_id: int
    attention_c0: int
    attention_c1: int
    mlp_gate_c0: int
    mlp_gate_c1: int
    mlp_down_c0: int
    mlp_down_c1: int


def local_to_host(channel: int, local_offset: int, size: int = 0) -> int:
    if channel not in range(DDR_CHANNELS):
        raise ValueError(f"invalid DDR channel {channel}")
    if local_offset < 0 or size < 0:
        raise ValueError("DDR offset and size must be non-negative")
    if local_offset > DDR_CHANNEL_BYTES - size:
        raise ValueError(
            f"DDR{channel} range exceeds 2 GiB: "
            f"offset=0x{local_offset:x} size=0x{size:x}"
        )
    return (DDR0_HOST_BASE if channel == 0 else DDR1_HOST_BASE) + local_offset


def host_to_local(host_offset: int, size: int = 0) -> Tuple[int, int]:
    if host_offset < 0 or host_offset >= HOST_APERTURE_BYTES or size < 0:
        raise ValueError("invalid Host DDR aperture range")
    channel = 0 if host_offset < DDR1_HOST_BASE else 1
    base = DDR0_HOST_BASE if channel == 0 else DDR1_HOST_BASE
    local_offset = host_offset - base
    local_to_host(channel, local_offset, size)
    return channel, local_offset


def layer_addresses(layer_id: int) -> LayerAddresses:
    if layer_id not in range(LAYER_COUNT):
        raise ValueError(f"layer_id must be in 0..{LAYER_COUNT - 1}")
    layer_base = layer_id * LAYER_STRIDE_BYTES
    gate_base = layer_base + ATTENTION_BYTES_PER_CHANNEL
    down_base = gate_base + MLP_GATE_UP_BYTES_PER_CHANNEL
    return LayerAddresses(
        layer_id=layer_id,
        attention_c0=layer_base,
        attention_c1=layer_base,
        mlp_gate_c0=gate_base,
        mlp_gate_c1=gate_base,
        mlp_down_c0=down_base,
        mlp_down_c1=down_base,
    )


def matrix_regions() -> Tuple[MemoryRegion, ...]:
    regions = []
    for layer_id in range(LAYER_COUNT):
        addresses = layer_addresses(layer_id)
        for channel in range(DDR_CHANNELS):
            suffix = f"layer{layer_id:02d}_c{channel}"
            regions.extend((
                MemoryRegion(
                    f"attention_{suffix}", channel,
                    addresses.attention_c0 if channel == 0
                    else addresses.attention_c1,
                    ATTENTION_BYTES_PER_CHANNEL,
                ),
                MemoryRegion(
                    f"mlp_gate_up_{suffix}", channel,
                    addresses.mlp_gate_c0 if channel == 0
                    else addresses.mlp_gate_c1,
                    MLP_GATE_UP_BYTES_PER_CHANNEL,
                ),
                MemoryRegion(
                    f"mlp_down_{suffix}", channel,
                    addresses.mlp_down_c0 if channel == 0
                    else addresses.mlp_down_c1,
                    MLP_DOWN_BYTES_PER_CHANNEL,
                ),
            ))
    return tuple(regions)


RUNTIME_REGIONS = tuple(
    MemoryRegion(
        f"activation_cohort{cohort}_slot{slot}", 0,
        RUNTIME_LOCAL_BASE + (cohort * 3 + slot) * ACTIVATION_SLOT_BYTES,
        ACTIVATION_SLOT_BYTES,
    )
    for cohort in range(2)
    for slot in range(3)
) + (
    MemoryRegion("attention_meta_bank0", 0, 0x7C80_0000,
                 ATTENTION_META_SLOT_BYTES),
    MemoryRegion("attention_meta_bank1", 0, 0x7CC0_0000,
                 ATTENTION_META_SLOT_BYTES),
    MemoryRegion("mlp_meta_bank0", 0, 0x7D00_0000,
                 MLP_META_SLOT_BYTES),
    MemoryRegion("mlp_meta_bank1", 0, 0x7DC0_0000,
                 MLP_META_SLOT_BYTES),
    MemoryRegion("rope", 0, 0x7E80_0000, 64 * KIB),
    MemoryRegion("trace_and_board_scratch", 0, 0x7F00_0000, 16 * MIB),
)


def mlp_meta_bases(bank: int) -> Tuple[int, int]:
    if bank not in (0, 1):
        raise ValueError("MLP metadata bank must be 0 or 1")
    slot = next(region for region in RUNTIME_REGIONS
                if region.name == f"mlp_meta_bank{bank}")
    return slot.local_start, slot.local_start + MLP_GATE_META_BYTES


def attention_meta_base(bank: int) -> int:
    if bank not in (0, 1):
        raise ValueError("Attention metadata bank must be 0 or 1")
    return next(region.local_start for region in RUNTIME_REGIONS
                if region.name == f"attention_meta_bank{bank}")


def activation_base(cohort_id: int, slot: int) -> int:
    if cohort_id not in (0, 1) or slot not in range(3):
        raise ValueError("activation location requires cohort 0/1 and slot 0..2")
    name = f"activation_cohort{cohort_id}_slot{slot}"
    return next(region.local_start for region in RUNTIME_REGIONS
                if region.name == name)


def activation_base_for_buffer(buffer_id: int) -> int:
    if buffer_id not in range(6):
        raise ValueError("hardware buffer_id must be in 0..5")
    return activation_base(buffer_id // 3, buffer_id % 3)


def validate_frozen_layout() -> None:
    if MATRIX_BYTES_PER_CHANNEL != 0x7C00_0000:
        raise RuntimeError("matrix payload must end at local 0x7c000000")
    if RUNTIME_BYTES_PER_CHANNEL != 64 * MIB:
        raise RuntimeError("each channel must retain exactly 64 MiB runtime space")
    for channel in range(DDR_CHANNELS):
        expected = 0
        regions = sorted(
            (region for region in matrix_regions()
             if region.channel == channel),
            key=lambda region: region.local_start,
        )
        for region in regions:
            if region.local_start != expected:
                raise RuntimeError(
                    f"DDR{channel} matrix gap/overlap before {region.name}: "
                    f"expected=0x{expected:x} actual=0x{region.local_start:x}"
                )
            expected = region.local_end
        if expected != RUNTIME_LOCAL_BASE:
            raise RuntimeError(f"DDR{channel} matrix extent is incomplete")

    occupied = sorted(RUNTIME_REGIONS, key=lambda region: region.local_start)
    previous_end = RUNTIME_LOCAL_BASE
    for region in occupied:
        if region.channel != 0 or region.local_start < RUNTIME_LOCAL_BASE:
            raise RuntimeError(f"runtime region is outside DDR0: {region.name}")
        if region.local_start < previous_end:
            raise RuntimeError(f"runtime regions overlap at {region.name}")
        previous_end = region.local_end
    if previous_end > DDR_CHANNEL_BYTES:
        raise RuntimeError("runtime regions exceed DDR0")

    gate0, down0 = mlp_meta_bases(0)
    gate1, down1 = mlp_meta_bases(1)
    for gate, down in ((gate0, down0), (gate1, down1)):
        if down - gate != MLP_GATE_META_BYTES:
            raise RuntimeError("MLP metadata gate/down boundary drifted")
        if MLP_GATE_META_BYTES + MLP_DOWN_META_BYTES > MLP_META_SLOT_BYTES:
            raise RuntimeError("MLP metadata does not fit its staging slot")
    if ATTENTION_META_BYTES > ATTENTION_META_SLOT_BYTES:
        raise RuntimeError("Attention metadata does not fit its staging slot")
    if ACTIVATION_PAYLOAD_BYTES > ACTIVATION_SLOT_BYTES:
        raise RuntimeError("cohort16 activation does not fit its runtime slot")


validate_frozen_layout()
