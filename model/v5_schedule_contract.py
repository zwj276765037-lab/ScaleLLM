#!/usr/bin/env python3
"""Pure V5 16-column-record to 12-column-pass schedule contract.

This module deliberately contains no RTL timing assumptions.  It proves the
column mapping, source-record counts, tail masks and analytical transaction
model that the V5 gather/repack RTL must implement bit exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence, TypeVar


SOURCE_COLUMNS = 16
COMPUTE_COLUMNS = 12
SUPERTILE_COLUMNS = math.lcm(SOURCE_COLUMNS, COMPUTE_COLUMNS)
HIDDEN = 4096
INTERMEDIATE = 14336
HIDDEN_GROUPS = HIDDEN // 32
INTERMEDIATE_GROUPS = INTERMEDIATE // 32
COHORT = 16
CORE_HZ = 150_000_000
LAYERS = 32
PRODUCT_FRONTEND_CYCLES_PER_GROUP = 835
BYTES_PER_SOURCE_RECORD = SOURCE_COLUMNS * 32 * 4 // 8

T = TypeVar("T")


def ceil_div(value: int, divisor: int) -> int:
    if value < 0 or divisor <= 0:
        raise ValueError("ceil_div requires value>=0 and divisor>0")
    return (value + divisor - 1) // divisor


@dataclass(frozen=True)
class ColumnLane:
    """One valid destination lane and its dense source-record location."""

    global_column: int
    source_record: int
    source_lane: int


@dataclass(frozen=True)
class ComputePass:
    """One 12-column pass emitted by a local 48-column supertile."""

    supertile: int
    pass_in_supertile: int
    first_column: int
    valid_columns: int
    lanes: tuple[ColumnLane, ...]


@dataclass(frozen=True)
class Supertile:
    """Dense source records and compute passes for at most 48 columns."""

    index: int
    first_column: int
    valid_columns: int
    source_records: tuple[int, ...]
    compute_passes: tuple[ComputePass, ...]


def build_supertile_schedule(width: int) -> tuple[Supertile, ...]:
    """Return the unique dense 16->48->12 schedule for a matrix width."""
    if width <= 0:
        raise ValueError("matrix width must be positive")
    result: list[Supertile] = []
    for supertile_index, base in enumerate(
            range(0, width, SUPERTILE_COLUMNS)):
        valid = min(SUPERTILE_COLUMNS, width - base)
        source_first = base // SOURCE_COLUMNS
        source_count = ceil_div(valid, SOURCE_COLUMNS)
        source_records = tuple(
            range(source_first, source_first + source_count))
        passes: list[ComputePass] = []
        for pass_index, pass_base in enumerate(
                range(base, base + valid, COMPUTE_COLUMNS)):
            pass_valid = min(COMPUTE_COLUMNS, width - pass_base)
            lanes = tuple(
                ColumnLane(
                    global_column=column,
                    source_record=column // SOURCE_COLUMNS,
                    source_lane=column % SOURCE_COLUMNS,
                )
                for column in range(pass_base, pass_base + pass_valid)
            )
            passes.append(ComputePass(
                supertile=supertile_index,
                pass_in_supertile=pass_index,
                first_column=pass_base,
                valid_columns=pass_valid,
                lanes=lanes,
            ))
        result.append(Supertile(
            index=supertile_index,
            first_column=base,
            valid_columns=valid,
            source_records=source_records,
            compute_passes=tuple(passes),
        ))
    return tuple(result)


def gate_up_source_tiles(supertile: Supertile) -> tuple[int, ...]:
    """Existing V4 tile order for one gate/up gather block.

    Matrix-local source record r maps to gate tile 2*r and up tile 2*r+1.
    Therefore every full supertile is exactly six sequential V4 tiles:
    gate0,up0,gate1,up1,gate2,up2.  Every tile remains tile-major over the
    128 hidden groups; the gather buffer must not mix their group indices.
    """
    output: list[int] = []
    for record in supertile.source_records:
        output.extend((2 * record, 2 * record + 1))
    return tuple(output)


def repack_dense_16_to_12(records: Sequence[Sequence[T]],
                          width: int, pad: T) -> tuple[tuple[T, ...], ...]:
    """Reference column repack including explicit padding of invalid lanes."""
    expected_records = ceil_div(width, SOURCE_COLUMNS)
    if len(records) != expected_records:
        raise ValueError(
            f"expected {expected_records} source records, got {len(records)}")
    for record in records:
        if len(record) != SOURCE_COLUMNS:
            raise ValueError("every source record must contain 16 columns")
    dense = [value for record in records for value in record][:width]
    output: list[tuple[T, ...]] = []
    for start in range(0, width, COMPUTE_COLUMNS):
        valid = list(dense[start:start + COMPUTE_COLUMNS])
        output.append(tuple(valid + [pad] * (COMPUTE_COLUMNS - len(valid))))
    return tuple(output)


def repack_dense_12_to_16(passes: Sequence[Sequence[T]],
                          width: int, pad: T) -> tuple[tuple[T, ...], ...]:
    """Reference inverse repack used before legacy 16-column consumers."""
    expected_passes = ceil_div(width, COMPUTE_COLUMNS)
    if len(passes) != expected_passes:
        raise ValueError(
            f"expected {expected_passes} compute passes, got {len(passes)}")
    for item in passes:
        if len(item) != COMPUTE_COLUMNS:
            raise ValueError("every compute pass must contain 12 columns")
    dense = [value for item in passes for value in item][:width]
    output: list[tuple[T, ...]] = []
    for start in range(0, width, SOURCE_COLUMNS):
        valid = list(dense[start:start + SOURCE_COLUMNS])
        output.append(tuple(valid + [pad] * (SOURCE_COLUMNS - len(valid))))
    return tuple(output)


@dataclass(frozen=True)
class V5LayerModel:
    gate_up_source_records: int
    gate_up_source_transactions: int
    gate_up_compute_passes: int
    gate_up_compute_transactions: int
    down_source_records_per_group: int
    down_source_transactions: int
    down_compute_passes_per_group: int
    down_compute_transactions: int
    mlp_weight_bytes: int
    kernel_dsp: int
    kernel_tops: float
    projection_kernel_roof_tokens_per_s: float
    serial_mlp_cycles_per_layer: int
    serial_mlp_aggregate_tokens_per_s: float


def build_v5_layer_model() -> V5LayerModel:
    gate_up_records = 2 * ceil_div(INTERMEDIATE, SOURCE_COLUMNS)
    gate_up_source_transactions = gate_up_records * HIDDEN_GROUPS
    gate_up_passes = 2 * ceil_div(INTERMEDIATE, COMPUTE_COLUMNS)
    gate_up_compute_transactions = gate_up_passes * HIDDEN_GROUPS
    down_records = ceil_div(HIDDEN, SOURCE_COLUMNS)
    down_source_transactions = down_records * INTERMEDIATE_GROUPS
    down_passes = ceil_div(HIDDEN, COMPUTE_COLUMNS)
    down_compute_transactions = down_passes * INTERMEDIATE_GROUPS
    weight_bytes = (gate_up_source_transactions + down_source_transactions) * \
        BYTES_PER_SOURCE_RECORD

    kernel_dsp = 2 * 8 * (COMPUTE_COLUMNS // 2) * 32
    # One packed DSP emits two multiplications/cycle; each MAC is two useful
    # operations under the project's TOPS convention.
    kernel_ops_per_second = kernel_dsp * 2 * 2 * CORE_HZ
    mlp_ops_per_token = 3 * HIDDEN * INTERMEDIATE * 2 * LAYERS
    kernel_roof = kernel_ops_per_second / mlp_ops_per_token

    product_cycles = INTERMEDIATE_GROUPS * \
        PRODUCT_FRONTEND_CYCLES_PER_GROUP
    serial_cycles = max(gate_up_compute_transactions, product_cycles) + \
        down_compute_transactions
    serial_rate = COHORT * CORE_HZ / (serial_cycles * LAYERS)
    return V5LayerModel(
        gate_up_source_records=gate_up_records,
        gate_up_source_transactions=gate_up_source_transactions,
        gate_up_compute_passes=gate_up_passes,
        gate_up_compute_transactions=gate_up_compute_transactions,
        down_source_records_per_group=down_records,
        down_source_transactions=down_source_transactions,
        down_compute_passes_per_group=down_passes,
        down_compute_transactions=down_compute_transactions,
        mlp_weight_bytes=weight_bytes,
        kernel_dsp=kernel_dsp,
        kernel_tops=kernel_ops_per_second / 1e12,
        projection_kernel_roof_tokens_per_s=kernel_roof,
        serial_mlp_cycles_per_layer=serial_cycles,
        serial_mlp_aggregate_tokens_per_s=serial_rate,
    )


if __name__ == "__main__":
    print(build_v5_layer_model())
