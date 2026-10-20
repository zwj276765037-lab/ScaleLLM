#!/usr/bin/env python3

import unittest
from dataclasses import replace

from model.attention_cohort16_integration_contract import (
    ATTENTION_ROW_HEADS,
    K_TILES,
    PROJECTION_WAVE_OUTPUTS,
    Q_TILES,
    QKV_TILES,
    ROPE_AXI256_BEATS,
    TENSOR_AXI256_BEATS,
    TOTAL_TILES,
    V_TILES,
    WAVE_GROUP_CONSUMPTIONS,
    WEIGHT_GROUPS,
    CommandDescriptor,
    ProjectionOp,
    audit_command_schedule,
    build_command_schedule,
)


class AttentionCohort16IntegrationContractTests(unittest.TestCase):
    def setUp(self):
        self.command = CommandDescriptor(
            request_id=0x10203040,
            cohort_id=7,
            layer_id=31,
            query_start=16,
            query_count=16,
            valid_key_count=32,
        )

    def test_full_command_reads_w8_once_for_both_waves(self):
        schedule = build_command_schedule(self.command)
        audit_command_schedule(schedule)
        self.assertEqual(len(schedule.tiles), TOTAL_TILES)
        self.assertEqual(schedule.weight_groups, WEIGHT_GROUPS)
        self.assertEqual(
            schedule.wave_group_consumptions,
            WAVE_GROUP_CONSUMPTIONS,
        )
        self.assertEqual(len(schedule.output_waves), PROJECTION_WAVE_OUTPUTS)
        self.assertEqual(schedule.physical_weight_bytes, 40 * 1024 * 1024)
        self.assertEqual(
            schedule.forbidden_two_command_weight_bytes,
            80 * 1024 * 1024,
        )

    def test_tensor_rope_and_attention_shapes_are_cohort16(self):
        schedule = build_command_schedule(self.command)
        self.assertEqual(schedule.input_beats, TENSOR_AXI256_BEATS)
        self.assertEqual(schedule.output_beats, TENSOR_AXI256_BEATS)
        self.assertEqual(TENSOR_AXI256_BEATS, 6144)
        self.assertEqual(schedule.rope_beats, ROPE_AXI256_BEATS)
        self.assertEqual(ROPE_AXI256_BEATS, 256)
        self.assertEqual(ATTENTION_ROW_HEADS, 512)

    def test_projection_op_boundaries_are_frozen(self):
        schedule = build_command_schedule(self.command)
        ops = tuple(tile.op_id for tile in schedule.tiles)
        self.assertEqual(ops[:Q_TILES], (ProjectionOp.Q,) * Q_TILES)
        self.assertEqual(
            ops[Q_TILES:Q_TILES + K_TILES],
            (ProjectionOp.K,) * K_TILES,
        )
        self.assertEqual(
            ops[Q_TILES + K_TILES:QKV_TILES],
            (ProjectionOp.V,) * V_TILES,
        )
        self.assertEqual(ops[QKV_TILES:], (ProjectionOp.WO,) * 256)

    def test_every_tile_preserves_command_descriptor(self):
        schedule = build_command_schedule(self.command)
        for tile_id, tile in enumerate(schedule.tiles):
            self.assertEqual(tile.request_id, self.command.request_id)
            self.assertEqual(tile.cohort_id, self.command.cohort_id)
            self.assertEqual(tile.layer_id, self.command.layer_id)
            self.assertEqual(tile.tile_id, tile_id)
            self.assertEqual(tile.query_start, self.command.query_start)
            self.assertEqual(
                tile.valid_key_count,
                self.command.valid_key_count,
            )

    def test_non_cohort16_or_corrupt_schedule_fails_closed(self):
        with self.assertRaises(ValueError):
            build_command_schedule(replace(self.command, query_count=8))
        schedule = build_command_schedule(self.command)
        with self.assertRaises(ValueError):
            audit_command_schedule(replace(schedule, weight_groups=2 * WEIGHT_GROUPS))


if __name__ == "__main__":
    unittest.main()
