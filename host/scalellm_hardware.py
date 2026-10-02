#!/usr/bin/env python3
"""Register-level VCU118 backend for the ScaleLLM dual-cohort runtime."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Mapping, Protocol

from .scalellm_memory import (
    ATTENTION_META_BYTES,
    MLP_DOWN_META_BYTES,
    MLP_GATE_META_BYTES,
    ROPE_BYTES,
    activation_base_for_buffer,
    attention_meta_base,
    layer_addresses,
    mlp_meta_bases,
)
from .scalellm_runtime import (
    ATTENTION_COMPLETION,
    MLP_COMPLETION,
    CommandIdentity,
    Completion,
    CompletionStatus,
    Engine,
    RuntimeContractError,
    decode_completion,
)


ATTENTION_FORMAT_ID = 0x4838_4103
ATTENTION_ABI = 0x0002_0000
MLP_FORMAT_ID = 0x4838_4605
MLP_ABI = 0x0005_0000

ATTENTION_CONTROL = 0x008
ATTENTION_STATUS = 0x00C
MLP_OWNER_REQUEST = 0x108
MLP_OWNER_STATUS = 0x10C
MLP_CONTROL = 0x110
MLP_STATUS = 0x114
MLP_META_STATUS = 0x14C
MLP_META_ACTION = 0x154
MLP_DMA_ACTION = 0x174
MLP_DMA_STATUS = 0x178
MLP_PAIRED_STATUS = 0x260
MLP_COMPLETION_FLAGS = 0x29C
MLP_COMPLETION_ACK = 0x2A0
MLP_ABORT_STATUS = 0x2A8
MLP_DOWN_SATURATION_COUNT = 0x2AC
MLP_TOTAL_SHIFT_FORMAT_ERROR_COUNT = 0x2B0
MLP_NUMERIC_STATUS = 0x2B4

OWNER_SHARED = 3
MLP_GATE_META_RECORDS = 229_376
MLP_DOWN_META_RECORDS = 114_688
MLP_TENSOR_INPUT_BEATS = 6_144
MLP_TENSOR_INPUT_GROUPS = 128

ATTENTION_TELEMETRY_REGISTERS = {
    "cycle_count": 0x038,
    "weight_group_count": 0x03C,
    "projection_tile_count": 0x040,
    "attention_row_count": 0x044,
    "wo_tile_count": 0x048,
    "error_code": 0x04C,
    "input_frontend_cycles": 0x050,
    "qkv_projection_cycles": 0x054,
    "rope_cycles": 0x058,
    "kv12_cycles": 0x05C,
    "attention_cycles": 0x060,
    "context_frontend_cycles": 0x064,
    "wo_projection_cycles": 0x068,
    "control_overhead_cycles": 0x06C,
}

MLP_TELEMETRY_NAMES = (
    "input_group_count", "input_cache_read_count",
    "input_cache_release_count", "input_hadamard_saturation_count",
    "gate_ddr0_raw_beats", "gate_ddr1_raw_beats",
    "gate_ddr0_elapsed_cycles", "gate_ddr1_elapsed_cycles",
    "gate_ddr0_bursts", "gate_ddr1_bursts",
    "gate_ddr0_ar_stalls", "gate_ddr1_ar_stalls",
    "gate_ddr0_r_backpressure", "gate_ddr1_r_backpressure",
    "gate_ddr0_response_idle", "gate_ddr1_response_idle",
    "gate_ddr0_max_outstanding", "gate_ddr1_max_outstanding",
    "gate_physical_bytes_low", "gate_physical_bytes_high",
    "gate_useful_bytes_low", "gate_useful_bytes_high",
    "down_ddr0_raw_beats", "down_ddr1_raw_beats",
    "down_ddr0_elapsed_cycles", "down_ddr1_elapsed_cycles",
    "down_ddr0_bursts", "down_ddr1_bursts",
    "down_ddr0_ar_stalls", "down_ddr1_ar_stalls",
    "down_ddr0_r_backpressure", "down_ddr1_r_backpressure",
    "down_ddr0_response_idle", "down_ddr1_response_idle",
    "down_ddr0_max_outstanding", "down_ddr1_max_outstanding",
    "down_physical_bytes_low", "down_physical_bytes_high",
    "down_useful_bytes_low", "down_useful_bytes_high",
    "gate_cache_request_count", "gate_weight_group_count",
    "gate_projection_tile_count", "product_group_count",
    "down_activation_write_count", "down_activation_read_count",
    "down_weight_tile_count", "output_tile_count", "saturation_count",
)

PAIRED_TELEMETRY_REGISTERS = {
    "paired_attention_bursts": 0x264,
    "paired_mlp_bursts": 0x268,
    "paired_both_busy_cycles": 0x26C,
    "paired_head_of_line_cycles_ddr0": 0x270,
    "paired_head_of_line_cycles_ddr1": 0x274,
    "paired_outstanding_hwm_ddr0": 0x278,
    "paired_outstanding_hwm_ddr1": 0x27C,
}

MLP_NUMERIC_TELEMETRY_REGISTERS = {
    "down_output_saturation_count": MLP_DOWN_SATURATION_COUNT,
    "total_shift_format_error_count": MLP_TOTAL_SHIFT_FORMAT_ERROR_COUNT,
    "numeric_status": MLP_NUMERIC_STATUS,
}


class HardwareTimeout(RuntimeContractError):
    """Raised when a bounded board operation does not reach its contract."""


class RegisterTransport(Protocol):
    def write32(self, offset: int, value: int) -> None:
        """Write one AXI-Lite register."""

    def read32(self, offset: int) -> int:
        """Read one AXI-Lite register."""


class LayerStager(Protocol):
    def stage_attention(
        self, layer_id: int, local_base: int, expected_bytes: int
    ) -> None:
        """Place one layer of Attention metadata in DDR0 staging."""

    def stage_mlp(
        self, layer_id: int, bank: int, gate_local_base: int,
        gate_bytes: int, down_local_base: int, down_bytes: int
    ) -> None:
        """Place one layer of MLP metadata in the selected DDR0 staging bank."""

    def stage_rope(self, local_base: int, expected_bytes: int) -> None:
        """Place the frozen RoPE image in DDR0 staging."""


@dataclass(frozen=True)
class AttentionInvocation:
    query_start: int = 0
    valid_key_count: int = 16
    query_count: int = 16
    preserve_historical_kv: bool = False

    def __post_init__(self) -> None:
        if self.query_count != 16:
            raise ValueError("cohort16 Attention requires query_count=16")
        if not 1 <= self.valid_key_count <= 128:
            raise ValueError("valid_key_count must be in 1..128")
        if not 0 <= self.query_start <= 127:
            raise ValueError("query_start must be in 0..127")
        if self.query_start + self.query_count > self.valid_key_count:
            raise ValueError("Attention query window exceeds valid keys")


@dataclass(frozen=True)
class HardwareCommandTelemetry:
    engine: str
    identity: CommandIdentity
    completion_status: str
    captured_ns: int
    counters: Mapping[str, int]


class ScaleLLMHardwareBackend:
    """Synchronous per-engine commands over one persistent XDMA session."""

    def __init__(
        self,
        transport: RegisterTransport,
        stager: LayerStager,
        attention_config: Callable[[CommandIdentity], AttentionInvocation]
        | None = None,
        timeout_s: float = 1.0,
        poll_interval_s: float = 0.0005,
    ) -> None:
        if timeout_s <= 0 or poll_interval_s < 0:
            raise ValueError("invalid hardware timeout/poll interval")
        self.transport = transport
        self.stager = stager
        self.attention_config = attention_config or (
            lambda _identity: AttentionInvocation()
        )
        self.timeout_s = timeout_s
        self.poll_interval_s = poll_interval_s
        self._attention_lock = threading.Lock()
        self._mlp_lock = threading.Lock()
        self._mode_lock = threading.Lock()
        self._telemetry_lock = threading.Lock()
        self._initialized = False
        self._attention_layer = None
        self._rope_staged = False
        self._telemetry: list[HardwareCommandTelemetry] = []

    @staticmethod
    def _join_u64(low: int, high: int) -> int:
        return (int(high) << 32) | int(low)

    def _attention_telemetry(self) -> dict[str, int]:
        return {
            name: self.transport.read32(offset)
            for name, offset in ATTENTION_TELEMETRY_REGISTERS.items()
        }

    def _mlp_telemetry(self) -> dict[str, int]:
        words = {
            name: self.transport.read32(0x180 + index * 4)
            for index, name in enumerate(MLP_TELEMETRY_NAMES)
        }
        for prefix in ("gate", "down"):
            for kind in ("physical", "useful"):
                low_name = f"{prefix}_{kind}_bytes_low"
                high_name = f"{prefix}_{kind}_bytes_high"
                words[f"{prefix}_{kind}_bytes"] = self._join_u64(
                    words.pop(low_name), words.pop(high_name)
                )
        words.update({
            name: self.transport.read32(offset)
            for name, offset in PAIRED_TELEMETRY_REGISTERS.items()
        })
        words.update({
            name: self.transport.read32(offset)
            for name, offset in MLP_NUMERIC_TELEMETRY_REGISTERS.items()
        })
        words["tensor_input_beats"] = self.transport.read32(0x17C)
        words["tensor_input_groups"] = self.transport.read32(0x244)
        words["tensor_output_beats"] = self.transport.read32(0x248)
        words["tensor_output_tiles"] = self.transport.read32(0x24C)
        words["metadata_gate_records"] = self.transport.read32(0x250)
        words["metadata_down_records"] = self.transport.read32(0x254)
        words["metadata_physical_bytes"] = self._join_u64(
            self.transport.read32(0x258), self.transport.read32(0x25C)
        )
        words["error_code"] = self.transport.read32(0x148)
        return words

    def _record_telemetry(
        self, engine: Engine, identity: CommandIdentity,
        completion: Completion, counters: Mapping[str, int],
    ) -> None:
        item = HardwareCommandTelemetry(
            engine=engine.value,
            identity=identity,
            completion_status=completion.status.name,
            captured_ns=time.monotonic_ns(),
            counters=dict(counters),
        )
        with self._telemetry_lock:
            self._telemetry.append(item)

    @property
    def telemetry(self) -> tuple[HardwareCommandTelemetry, ...]:
        with self._telemetry_lock:
            return tuple(self._telemetry)

    def _wait(self, description: str, predicate: Callable[[], bool]) -> None:
        deadline = time.monotonic() + self.timeout_s
        while not predicate():
            if time.monotonic() >= deadline:
                raise HardwareTimeout(f"timeout waiting for {description}")
            if self.poll_interval_s:
                time.sleep(self.poll_interval_s)

    def initialize_shared_mode(self) -> None:
        with self._mode_lock:
            expected = (
                (0x000, ATTENTION_FORMAT_ID),
                (0x004, ATTENTION_ABI),
                (0x100, MLP_FORMAT_ID),
                (0x104, MLP_ABI),
            )
            for offset, value in expected:
                actual = self.transport.read32(offset)
                if actual != value:
                    raise RuntimeContractError(
                        f"register 0x{offset:03x} identity mismatch: "
                        f"expected=0x{value:08x} actual=0x{actual:08x}"
                    )
            if self.transport.read32(MLP_COMPLETION_FLAGS) & 0x3:
                raise RuntimeContractError(
                    "cannot initialize with an active/stale MLP command"
                )
            if self.transport.read32(MLP_COMPLETION_ACK) & 0x1:
                raise RuntimeContractError(
                    "cannot initialize with an idle MLP diagnostic"
                )

            def shared_ready() -> bool:
                status = self.transport.read32(MLP_OWNER_STATUS)
                return (status & 0x1F) == 0x1B

            if not shared_ready():
                self._wait(
                    "DDR owner request readiness",
                    lambda: bool(self.transport.read32(MLP_OWNER_STATUS)
                                 & (1 << 5)),
                )
                self.transport.write32(MLP_OWNER_REQUEST, OWNER_SHARED)
                self._wait("shared DDR owner mode", shared_ready)
            self._initialized = True

    def execute(
        self, engine: Engine, identity: CommandIdentity
    ) -> Completion:
        if not self._initialized:
            raise RuntimeContractError("hardware backend is not initialized")
        if engine is Engine.ATTENTION:
            with self._attention_lock:
                return self._execute_attention(identity)
        if engine is Engine.MLP:
            with self._mlp_lock:
                return self._execute_mlp(identity)
        raise RuntimeContractError(f"unsupported engine {engine}")

    def _execute_attention(self, identity: CommandIdentity) -> Completion:
        if identity.op_id != 0:
            raise RuntimeContractError("Attention command requires op_id=0")
        status = self.transport.read32(ATTENTION_STATUS)
        if status & 0x7:
            raise RuntimeContractError(
                f"Attention is not idle/acknowledged: status=0x{status:08x}"
            )
        config = self.attention_config(identity)
        addresses = layer_addresses(identity.layer_id)
        tensor_base = activation_base_for_buffer(identity.buffer_id)

        reload_metadata = self._attention_layer != identity.layer_id or not (
            status & (1 << 3)
        )
        if reload_metadata:
            metadata_base = attention_meta_base(identity.layer_id & 1)
            self.stager.stage_attention(
                identity.layer_id, metadata_base, ATTENTION_META_BYTES
            )
        else:
            metadata_base = attention_meta_base(identity.layer_id & 1)

        rope_base = 0x7E80_0000
        reload_rope = not self._rope_staged or not (status & (1 << 4))
        if reload_rope:
            self.stager.stage_rope(rope_base, ROPE_BYTES)

        query_word = (
            (config.query_count << 16)
            | (config.valid_key_count << 8)
            | config.query_start
        )
        writes = (
            (0x010, identity.command_id),
            (0x014, identity.layer_id),
            (0x018, query_word),
            (0x01C, ATTENTION_FORMAT_ID),
            (0x020, tensor_base),
            (0x024, tensor_base),
            (0x028, addresses.attention_c0),
            (0x02C, addresses.attention_c1),
            (0x030, metadata_base),
            (0x034, rope_base),
            (0x070, identity.request_id),
            (0x074, (identity.buffer_id << 16) | identity.cohort_id),
        )
        for offset, value in writes:
            self.transport.write32(offset, value)
        control = 1
        if reload_metadata:
            control |= 1 << 2
        if reload_rope:
            control |= 1 << 3
        if config.preserve_historical_kv:
            control |= 1 << 4
        self.transport.write32(ATTENTION_CONTROL, control)
        self._wait(
            "Attention completion",
            lambda: bool(self.transport.read32(ATTENTION_STATUS) & 0x6),
        )
        completion = decode_completion(
            self.transport.read32, ATTENTION_COMPLETION
        )
        if completion.identity != identity:
            raise RuntimeContractError(
                f"Attention hardware identity mismatch: "
                f"expected={identity} actual={completion.identity}"
            )
        self._record_telemetry(
            Engine.ATTENTION, identity, completion,
            self._attention_telemetry(),
        )
        self.transport.write32(ATTENTION_CONTROL, 1 << 1)
        self._wait(
            "Attention completion acknowledge",
            lambda: not (self.transport.read32(ATTENTION_STATUS) & 0x6),
        )
        if completion.status is CompletionStatus.SUCCESS:
            self._attention_layer = identity.layer_id
            self._rope_staged = True
        else:
            self._attention_layer = None
            self._rope_staged = False
        return completion

    def _ensure_mlp_metadata(self, layer_id: int) -> int:
        generation = layer_id + 1
        status = self.transport.read32(MLP_STATUS)
        active_bank = (status >> 8) & 0x1
        bank_valid = (status >> 9) & 0x3
        active_generation = self.transport.read32(0x144)
        if bank_valid & (1 << active_bank) and active_generation == generation:
            return active_bank
        if status & ((1 << 11) | (1 << 12)):
            raise RuntimeContractError(
                f"MLP metadata/owner diagnostic: status=0x{status:08x}"
            )

        bank = 1 - active_bank
        meta_status = self.transport.read32(MLP_META_STATUS)
        if meta_status & (1 << (3 + bank)):
            raise RuntimeContractError(f"MLP metadata bank {bank} is loading")
        gate_base, down_base = mlp_meta_bases(bank)
        self.stager.stage_mlp(
            layer_id, bank, gate_base, MLP_GATE_META_BYTES,
            down_base, MLP_DOWN_META_BYTES,
        )
        self.transport.write32(0x150, bank)
        self.transport.write32(0x16C, gate_base)
        self.transport.write32(0x170, down_base)
        self.transport.write32(MLP_META_ACTION, 1)
        self._wait(
            f"MLP metadata bank {bank} load start",
            lambda: bool(self.transport.read32(MLP_META_STATUS)
                         & (1 << (3 + bank))),
        )

        gate_count_offset = 0x160 if bank else 0x15C
        down_count_offset = 0x168 if bank else 0x164

        def metadata_loaded() -> bool:
            dma = self.transport.read32(MLP_DMA_STATUS)
            if dma & (1 << 4):
                raise RuntimeContractError("MLP metadata DMA error")
            return (
                not (dma & (1 << 2))
                and self.transport.read32(gate_count_offset)
                == MLP_GATE_META_RECORDS
                and self.transport.read32(down_count_offset)
                == MLP_DOWN_META_RECORDS
            )

        self._wait(f"MLP metadata bank {bank} load", metadata_loaded)
        self.transport.write32(0x158, generation)
        self.transport.write32(MLP_META_ACTION, 2)

        def metadata_committed() -> bool:
            live = self.transport.read32(MLP_STATUS)
            return (
                ((live >> 8) & 0x1) == bank
                and ((live >> (9 + bank)) & 0x1) == 1
                and self.transport.read32(0x144) == generation
            )

        self._wait(f"MLP metadata generation {generation} commit",
                   metadata_committed)
        return bank

    def _execute_mlp(self, identity: CommandIdentity) -> Completion:
        if identity.op_id != 1:
            raise RuntimeContractError("MLP command requires op_id=1")
        flags = self.transport.read32(MLP_COMPLETION_FLAGS)
        if flags & 0x3:
            raise RuntimeContractError(
                f"MLP is not idle/acknowledged: flags=0x{flags:08x}"
            )
        if self.transport.read32(MLP_COMPLETION_ACK) & 0x1:
            raise RuntimeContractError("MLP has an idle diagnostic")

        self._ensure_mlp_metadata(identity.layer_id)
        addresses = layer_addresses(identity.layer_id)
        tensor_base = activation_base_for_buffer(identity.buffer_id)
        command_bank = identity.buffer_id & 1
        generation = identity.layer_id + 1
        writes = (
            (0x118, identity.command_id),
            (0x11C, identity.layer_id),
            (0x120, MLP_FORMAT_ID),
            (0x124, tensor_base),
            (0x128, tensor_base),
            (0x12C, addresses.mlp_gate_c0),
            (0x130, addresses.mlp_gate_c1),
            (0x134, addresses.mlp_down_c0),
            (0x138, addresses.mlp_down_c1),
            (0x13C, command_bank),
            (0x140, generation),
            (0x280, identity.request_id),
            (0x284, (identity.buffer_id << 16) | identity.cohort_id),
        )
        for offset, value in writes:
            self.transport.write32(offset, value)

        self.transport.write32(MLP_DMA_ACTION, 1)

        def tensor_loaded() -> bool:
            dma = self.transport.read32(MLP_DMA_STATUS)
            if dma & (1 << 3):
                raise RuntimeContractError("MLP tensor load DMA error")
            return (
                not (dma & 0x1)
                and self.transport.read32(0x17C) == MLP_TENSOR_INPUT_BEATS
                and self.transport.read32(0x244) == MLP_TENSOR_INPUT_GROUPS
            )

        self._wait("MLP tensor load", tensor_loaded)
        self.transport.write32(MLP_DMA_ACTION, 2)
        self._wait(
            "MLP tensor store arm",
            lambda: bool(self.transport.read32(MLP_DMA_STATUS) & (1 << 1)),
        )
        self.transport.write32(MLP_CONTROL, 1)
        self._wait(
            "MLP completion",
            lambda: bool(self.transport.read32(MLP_COMPLETION_FLAGS) & 0x1),
        )
        completion = decode_completion(self.transport.read32, MLP_COMPLETION)
        if completion.identity != identity:
            raise RuntimeContractError(
                f"MLP hardware identity mismatch: "
                f"expected={identity} actual={completion.identity}"
            )
        telemetry = self._mlp_telemetry()
        self._record_telemetry(Engine.MLP, identity, completion, telemetry)
        if completion.status in (
            CompletionStatus.TIMEOUT,
            CompletionStatus.MAINTENANCE_ABORT,
        ):
            def maintenance_complete() -> bool:
                abort_status = self.transport.read32(MLP_ABORT_STATUS)
                paired_status = self.transport.read32(MLP_PAIRED_STATUS)
                return (
                    (abort_status & 0x3) == 0
                    and (paired_status & ((1 << 5) | (1 << 4))) == (1 << 5)
                )

            self._wait("MLP abort maintenance completion", maintenance_complete)
        self.transport.write32(MLP_COMPLETION_ACK, identity.command_id)
        self._wait(
            "MLP completion acknowledge",
            lambda: not (self.transport.read32(MLP_COMPLETION_FLAGS) & 0x1),
        )
        numeric_status = telemetry["numeric_status"]
        numeric_faults = []
        if telemetry["down_output_saturation_count"]:
            numeric_faults.append(
                "down_output_saturation_count="
                f"{telemetry['down_output_saturation_count']}"
            )
        if telemetry["total_shift_format_error_count"]:
            numeric_faults.append(
                "total_shift_format_error_count="
                f"{telemetry['total_shift_format_error_count']}"
            )
        if numeric_status & 0x1:
            numeric_faults.append("guard_overflow=1")
        if numeric_status & 0x2:
            numeric_faults.append("accumulator_overflow=1")
        if numeric_status & 0x4:
            numeric_faults.append("format_error_status=1")
        if numeric_status & ~0x7:
            numeric_faults.append(
                f"unknown_numeric_status=0x{numeric_status & ~0x7:08x}"
            )
        if numeric_faults:
            raise RuntimeContractError(
                "MLP numeric telemetry fail-closed: "
                + ", ".join(numeric_faults)
            )
        return completion
