#!/usr/bin/env python3
"""M002 engine-local DDR layout, preserving every format05 artifact byte.

c0/c1 name logical weight half-groups, not physical DDR channels. Attention
matrices reside in DDR0; DDR1 holds one leased MLP layer, staged per command.
All CSR addresses are local offsets. Only DMA helpers use host apertures.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

KIB = 1 << 10
MIB = 1 << 20
GIB = 1 << 30
DDR_CHANNELS = 2
DDR_CHANNEL_BYTES = 2 * GIB
DDR0_HOST_BASE = 0
DDR1_HOST_BASE = 0x8000_0000
HOST_APERTURE_BYTES = 4 * GIB
LAYER_COUNT = 32
# Historical export names describe logical half-group artifact sizes.
ATTENTION_BYTES_PER_CHANNEL = 20 * MIB
MLP_GATE_UP_BYTES_PER_CHANNEL = 28 * MIB
MLP_DOWN_BYTES_PER_CHANNEL = 14 * MIB
ATTENTION_BYTES_PER_LAYER = 2 * ATTENTION_BYTES_PER_CHANNEL
MLP_GATE_UP_BYTES_PER_LAYER = 2 * MLP_GATE_UP_BYTES_PER_CHANNEL
MLP_DOWN_BYTES_PER_LAYER = 2 * MLP_DOWN_BYTES_PER_CHANNEL
MLP_BYTES_PER_LAYER = MLP_GATE_UP_BYTES_PER_LAYER + MLP_DOWN_BYTES_PER_LAYER
LAYER_STRIDE_BYTES = ATTENTION_BYTES_PER_LAYER
DDR0_ATTENTION_WEIGHTS_BASE = 0
DDR0_ATTENTION_WEIGHTS_SIZE = LAYER_COUNT * ATTENTION_BYTES_PER_LAYER
DDR1_MLP_WEIGHTS_BASE = 0
DDR1_MLP_WEIGHTS_SIZE = MLP_BYTES_PER_LAYER
# Compatibility exports now refer to DDR0 resident matrices, not both channels.
MATRIX_BYTES_PER_CHANNEL = DDR0_ATTENTION_WEIGHTS_SIZE
RUNTIME_LOCAL_BASE = DDR0_ATTENTION_WEIGHTS_SIZE
RUNTIME_BYTES_PER_CHANNEL = DDR_CHANNEL_BYTES - RUNTIME_LOCAL_BASE

ACTIVATION_ROWS = 16
ACTIVATION_COLUMNS = 4096
ACTIVATION_INPUT_ELEMENT_BYTES = 3
ACTIVATION_OUTPUT_ELEMENT_BYTES = 4
ACTIVATION_INPUT_PAYLOAD_BYTES = ACTIVATION_ROWS * ACTIVATION_COLUMNS * 3
ACTIVATION_OUTPUT_PAYLOAD_BYTES = ACTIVATION_ROWS * ACTIVATION_COLUMNS * 4
ACTIVATION_PAYLOAD_BYTES = ACTIVATION_INPUT_PAYLOAD_BYTES
ACTIVATION_SLOT_BYTES = MIB
ACTIVATION_OUTPUT_OFFSET = MIB // 2
ATTENTION_META_BYTES = 2_621_440
ATTENTION_META_SLOT_BYTES = 4 * MIB
MLP_GATE_META_BYTES = 7 * MIB
MLP_DOWN_META_BYTES = 3_670_016
MLP_META_SLOT_BYTES = 12 * MIB
ROPE_BYTES = 8 * KIB
ROPE_LOCAL_BASE = 0x5700_0000
DDR0_KV_CACHE_BASE = 0x5000_0000
DDR0_KV_CACHE_SIZE = 96 * MIB
DDR0_ATTENTION_INPUT_BASE = 0x5600_0000
DDR0_ATTENTION_OUTPUT_BASE = DDR0_ATTENTION_INPUT_BASE + ACTIVATION_OUTPUT_OFFSET
DDR0_ATTENTION_INPUT_SLOT_BYTES = ACTIVATION_SLOT_BYTES
DDR0_ATTENTION_OUTPUT_SLOT_BYTES = ACTIVATION_SLOT_BYTES
DDR0_ATTENTION_INPUT_SIZE = 6 * ACTIVATION_SLOT_BYTES
DDR0_ATTENTION_OUTPUT_SIZE = 6 * ACTIVATION_SLOT_BYTES
DDR0_ATTENTION_META_BASE = 0x5680_0000
DDR0_ATTENTION_META_SIZE = 2 * ATTENTION_META_SLOT_BYTES
DDR1_MLP_INPUT_BASE = 0x0600_0000
DDR1_MLP_OUTPUT_BASE = DDR1_MLP_INPUT_BASE + ACTIVATION_OUTPUT_OFFSET
DDR1_MLP_INPUT_SLOT_BYTES = ACTIVATION_SLOT_BYTES
DDR1_MLP_OUTPUT_SLOT_BYTES = ACTIVATION_SLOT_BYTES
DDR1_MLP_INPUT_SIZE = 6 * ACTIVATION_SLOT_BYTES
DDR1_MLP_OUTPUT_SIZE = 6 * ACTIVATION_SLOT_BYTES
DDR1_MLP_META_BASE = 0x0680_0000
DDR1_MLP_META_SIZE = 2 * MLP_META_SLOT_BYTES


def local_to_host(channel: int, local_offset: int, size: int = 0) -> int:
    if channel not in range(DDR_CHANNELS):
        raise ValueError(f"invalid DDR channel {channel}")
    if local_offset < 0 or size < 0 or local_offset >= DDR_CHANNEL_BYTES:
        raise ValueError("invalid local DDR range")
    if local_offset + size > DDR_CHANNEL_BYTES:
        raise ValueError(f"DDR{channel} range exceeds 2 GiB")
    return (DDR0_HOST_BASE if channel == 0 else DDR1_HOST_BASE) + local_offset


def host_to_local(host_offset: int, size: int = 0) -> Tuple[int, int]:
    if host_offset < 0 or host_offset >= HOST_APERTURE_BYTES or size < 0:
        raise ValueError("invalid Host DDR aperture range")
    channel = 0 if host_offset < DDR1_HOST_BASE else 1
    local_offset = host_offset - (DDR0_HOST_BASE if channel == 0 else DDR1_HOST_BASE)
    local_to_host(channel, local_offset, size)
    return channel, local_offset


@dataclass(frozen=True)
class MemoryRegion:
    name: str
    channel: int
    local_start: int
    size: int

    def __post_init__(self) -> None:
        if self.size <= 0:
            raise ValueError(f"invalid region {self.name}")
        local_to_host(self.channel, self.local_start, self.size)

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

    @property
    def attention_weights(self) -> int:
        return local_to_host(0, self.attention_c0, ATTENTION_BYTES_PER_LAYER)

    @property
    def mlp_weights(self) -> int:
        return local_to_host(1, self.mlp_gate_c0, MLP_BYTES_PER_LAYER)


def layer_addresses(layer_id: int) -> LayerAddresses:
    if layer_id not in range(LAYER_COUNT):
        raise ValueError("layer_id must be in 0..31")
    attention = layer_id * ATTENTION_BYTES_PER_LAYER
    return LayerAddresses(layer_id, attention,
                          attention + ATTENTION_BYTES_PER_CHANNEL,
                          0, 28 * MIB, 56 * MIB, 70 * MIB)


def attention_matrix_regions() -> Tuple[MemoryRegion, ...]:
    return tuple(MemoryRegion(f"attention_layer{layer:02d}_c{half}", 0,
                              layer * 40 * MIB + half * 20 * MIB, 20 * MIB)
                 for layer in range(LAYER_COUNT) for half in (0, 1))


def mlp_matrix_regions(layer_id: int) -> Tuple[MemoryRegion, ...]:
    addresses = layer_addresses(layer_id)
    return tuple(MemoryRegion(f"{name}_layer{layer_id:02d}_c{half}", 1,
                              getattr(addresses, f"mlp_{stem}_c{half}"), size)
                 for name, stem, size in (
                     ("mlp_gate_up", "gate", MLP_GATE_UP_BYTES_PER_CHANNEL),
                     ("mlp_down", "down", MLP_DOWN_BYTES_PER_CHANNEL))
                 for half in (0, 1))


def matrix_regions() -> Tuple[MemoryRegion, ...]:
    """Physical allocations: all Attention and one reusable MLP layer slot."""
    return attention_matrix_regions() + mlp_matrix_regions(0)


def activation_channel(engine: str = "attention") -> int:
    if engine not in ("attention", "mlp"):
        raise ValueError("activation engine must be attention or mlp")
    return 0 if engine == "attention" else 1


def activation_base(cohort_id: int, slot: int, engine: str = "attention",
                    *, output: bool = False) -> int:
    if cohort_id not in (0, 1) or slot not in range(3):
        raise ValueError("activation location requires cohort 0/1 and slot 0..2")
    channel = activation_channel(engine)
    base = DDR0_ATTENTION_INPUT_BASE if channel == 0 else DDR1_MLP_INPUT_BASE
    return base + (cohort_id * 3 + slot) * ACTIVATION_SLOT_BYTES + (
        ACTIVATION_OUTPUT_OFFSET if output else 0)


def activation_base_for_buffer(buffer_id: int, engine: str = "attention",
                               *, output: bool = False) -> int:
    if buffer_id not in range(6):
        raise ValueError("hardware buffer_id must be in 0..5")
    return activation_base(buffer_id // 3, buffer_id % 3, engine, output=output)


def attention_meta_base(bank: int) -> int:
    if bank not in (0, 1):
        raise ValueError("Attention metadata bank must be 0 or 1")
    return DDR0_ATTENTION_META_BASE + bank * ATTENTION_META_SLOT_BYTES


def mlp_meta_bases(bank: int) -> Tuple[int, int]:
    if bank not in (0, 1):
        raise ValueError("MLP metadata bank must be 0 or 1")
    base = DDR1_MLP_META_BASE + bank * MLP_META_SLOT_BYTES
    return base, base + MLP_GATE_META_BYTES


def mlp_meta_base(bank: int) -> int:
    return local_to_host(1, mlp_meta_bases(bank)[0], MLP_META_SLOT_BYTES)


def attention_input_base(cohort_id: int, slot: int) -> int:
    return local_to_host(0, activation_base(cohort_id, slot), ACTIVATION_INPUT_PAYLOAD_BYTES)


def attention_output_base(cohort_id: int, slot: int) -> int:
    return local_to_host(0, activation_base(cohort_id, slot, output=True), ACTIVATION_INPUT_PAYLOAD_BYTES)


def mlp_input_base(cohort_id: int, slot: int) -> int:
    return local_to_host(1, activation_base(cohort_id, slot, "mlp"), ACTIVATION_INPUT_PAYLOAD_BYTES)


def mlp_output_base(cohort_id: int, slot: int) -> int:
    return local_to_host(1, activation_base(cohort_id, slot, "mlp", output=True), ACTIVATION_OUTPUT_PAYLOAD_BYTES)


def kv_cache_base() -> int:
    return local_to_host(0, DDR0_KV_CACHE_BASE, DDR0_KV_CACHE_SIZE)


RUNTIME_REGIONS = (
    MemoryRegion("kv_cache_reserved", 0, DDR0_KV_CACHE_BASE, DDR0_KV_CACHE_SIZE),
) + tuple(MemoryRegion(f"{engine}_activation_cohort{cohort}_slot{slot}", channel,
                      activation_base(cohort, slot, engine), ACTIVATION_SLOT_BYTES)
          for engine, channel in (("attention", 0), ("mlp", 1))
          for cohort in (0, 1) for slot in range(3)) + tuple(
    MemoryRegion(f"attention_meta_bank{bank}", 0, attention_meta_base(bank), ATTENTION_META_SLOT_BYTES)
    for bank in (0, 1)) + tuple(
    MemoryRegion(f"mlp_meta_bank{bank}", 1, mlp_meta_bases(bank)[0], MLP_META_SLOT_BYTES)
    for bank in (0, 1)) + (MemoryRegion("rope", 0, ROPE_LOCAL_BASE, 64 * KIB),)


def validate_regions(regions: Iterable[MemoryRegion]) -> None:
    """Check complete half-open extents, including same-channel intersections."""
    regions = tuple(regions)
    for channel in range(DDR_CHANNELS):
        occupied = sorted((r for r in regions if r.channel == channel),
                          key=lambda r: r.local_start)
        for left, right in zip(occupied, occupied[1:]):
            if left.local_end > right.local_start:
                raise ValueError(f"DDR{channel} regions overlap: {left.name}, {right.name}")


def validate_frozen_layout() -> None:
    validate_regions(matrix_regions() + RUNTIME_REGIONS)
    if DDR0_ATTENTION_WEIGHTS_SIZE != 1280 * MIB or MLP_BYTES_PER_LAYER != 84 * MIB:
        raise RuntimeError("artifact geometry drifted")
    if ATTENTION_META_BYTES > ATTENTION_META_SLOT_BYTES or MLP_GATE_META_BYTES + MLP_DOWN_META_BYTES > MLP_META_SLOT_BYTES:
        raise RuntimeError("metadata does not fit staging slot")
    if ACTIVATION_INPUT_PAYLOAD_BYTES > ACTIVATION_OUTPUT_OFFSET or ACTIVATION_OUTPUT_OFFSET + ACTIVATION_OUTPUT_PAYLOAD_BYTES > ACTIVATION_SLOT_BYTES:
        raise RuntimeError("activation input/output overlap or exceed slot")


def validate_address_separation() -> bool:
    validate_frozen_layout()
    return True


def get_ddr_layout_summary() -> str:
    return "\n".join(f"DDR{r.channel} {r.name}: [0x{r.local_start:08x},0x{r.local_end:08x})" for r in matrix_regions() + RUNTIME_REGIONS)


validate_frozen_layout()
if __name__ == "__main__":
    print(get_ddr_layout_summary())
