#!/usr/bin/env python3
"""Full-command schedule contract for cohort16 Llama-3.1-8B-Instruct Attention."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


ROWS_PER_WAVE = 8
WAVES = 2
COHORT_ROWS = ROWS_PER_WAVE * WAVES
HIDDEN_SIZE = 4096
KV_SIZE = 1024
COLS_PER_TILE = 16
GROUP_SIZE = 32
GROUPS_PER_TILE = HIDDEN_SIZE // GROUP_SIZE
Q_TILES = HIDDEN_SIZE // COLS_PER_TILE
K_TILES = KV_SIZE // COLS_PER_TILE
V_TILES = KV_SIZE // COLS_PER_TILE
WO_TILES = HIDDEN_SIZE // COLS_PER_TILE
QKV_TILES = Q_TILES + K_TILES + V_TILES
TOTAL_TILES = QKV_TILES + WO_TILES
WEIGHT_GROUPS = TOTAL_TILES * GROUPS_PER_TILE
WAVE_GROUP_CONSUMPTIONS = WEIGHT_GROUPS * WAVES
PROJECTION_WAVE_OUTPUTS = TOTAL_TILES * WAVES
WEIGHT_BYTES_PER_GROUP = COLS_PER_TILE * GROUP_SIZE
WEIGHT_BYTES = WEIGHT_GROUPS * WEIGHT_BYTES_PER_GROUP
TENSOR_BYTES = COHORT_ROWS * HIDDEN_SIZE * 3
AXI256_BYTES = 32
TENSOR_AXI256_BEATS = TENSOR_BYTES // AXI256_BYTES
ROPE_PAIRS_PER_ROW = HIDDEN_SIZE // 32 // 2
ROPE_RECORDS = COHORT_ROWS * ROPE_PAIRS_PER_ROW
ROPE_AXI256_BEATS = ROPE_RECORDS * 8 // AXI256_BYTES
ATTENTION_ROW_HEADS = COHORT_ROWS * 32


class ProjectionOp(IntEnum):
    Q = 0
    K = 1
    V = 2
    WO = 3


@dataclass(frozen=True)
class CommandDescriptor:
    request_id: int
    cohort_id: int
    layer_id: int
    query_start: int
    query_count: int
    valid_key_count: int

    def validate(self) -> None:
        if not 0 <= self.request_id < 2**32:
            raise ValueError("request_id must fit 32 bits")
        if not 0 <= self.cohort_id < 2**16:
            raise ValueError("cohort_id must fit 16 bits")
        if not 0 <= self.layer_id < 32:
            raise ValueError("layer_id must identify one of 32 layers")
        if self.query_count != COHORT_ROWS:
            raise ValueError("cohort16 command requires exactly 16 rows")
        if not 0 <= self.query_start <= 128 - COHORT_ROWS:
            raise ValueError("query_start exceeds fixed 128-token profile")
        if not 1 <= self.valid_key_count <= 128:
            raise ValueError("valid_key_count must be in 1..128")
        if self.query_start + self.query_count > self.valid_key_count:
            raise ValueError("valid rows exceed valid_key_count")


@dataclass(frozen=True)
class TileDescriptor:
    request_id: int
    cohort_id: int
    layer_id: int
    op_id: ProjectionOp
    tile_id: int
    query_start: int
    valid_key_count: int


@dataclass(frozen=True)
class CommandSchedule:
    command: CommandDescriptor
    tiles: tuple[TileDescriptor, ...]
    weight_groups: int
    wave_group_consumptions: int
    output_waves: tuple[int, ...]
    input_beats: int
    output_beats: int
    rope_beats: int

    @property
    def physical_weight_bytes(self) -> int:
        return self.weight_groups * WEIGHT_BYTES_PER_GROUP

    @property
    def forbidden_two_command_weight_bytes(self) -> int:
        return self.physical_weight_bytes * WAVES


def tile_op(tile_id: int) -> ProjectionOp:
    if not 0 <= tile_id < TOTAL_TILES:
        raise ValueError("tile_id outside the 640-tile Attention command")
    if tile_id < Q_TILES:
        return ProjectionOp.Q
    if tile_id < Q_TILES + K_TILES:
        return ProjectionOp.K
    if tile_id < QKV_TILES:
        return ProjectionOp.V
    return ProjectionOp.WO


def build_command_schedule(command: CommandDescriptor) -> CommandSchedule:
    command.validate()
    tiles = tuple(
        TileDescriptor(
            request_id=command.request_id,
            cohort_id=command.cohort_id,
            layer_id=command.layer_id,
            op_id=tile_op(tile_id),
            tile_id=tile_id,
            query_start=command.query_start,
            valid_key_count=command.valid_key_count,
        )
        for tile_id in range(TOTAL_TILES)
    )
    return CommandSchedule(
        command=command,
        tiles=tiles,
        weight_groups=WEIGHT_GROUPS,
        wave_group_consumptions=WAVE_GROUP_CONSUMPTIONS,
        output_waves=(0, 1) * TOTAL_TILES,
        input_beats=TENSOR_AXI256_BEATS,
        output_beats=TENSOR_AXI256_BEATS,
        rope_beats=ROPE_AXI256_BEATS,
    )


def audit_command_schedule(schedule: CommandSchedule) -> None:
    expected = build_command_schedule(schedule.command)
    if schedule != expected:
        raise ValueError("cohort16 Attention command schedule mismatch")
    if schedule.physical_weight_bytes != 40 * 1024 * 1024:
        raise ValueError("Attention W8 command must read exactly 40 MiB")
    if schedule.wave_group_consumptions != schedule.weight_groups * WAVES:
        raise ValueError("each accepted W8 group must serve both waves")
    if len(schedule.output_waves) != PROJECTION_WAVE_OUTPUTS:
        raise ValueError("each logical tile must retire two wave outputs")


if __name__ == "__main__":
    descriptor = CommandDescriptor(1, 0, 0, 0, 16, 16)
    item = build_command_schedule(descriptor)
    audit_command_schedule(item)
    print({
        "logical_projection_tiles": len(item.tiles),
        "weight_group_reads": item.weight_groups,
        "wave_group_consumptions": item.wave_group_consumptions,
        "projection_wave_outputs": len(item.output_waves),
        "physical_weight_bytes": item.physical_weight_bytes,
        "avoided_reread_bytes": (
            item.forbidden_two_command_weight_bytes
            - item.physical_weight_bytes
        ),
        "input_axi256_beats": item.input_beats,
        "output_axi256_beats": item.output_beats,
        "rope_axi256_beats": item.rope_beats,
        "attention_row_heads": ATTENTION_ROW_HEADS,
    })
