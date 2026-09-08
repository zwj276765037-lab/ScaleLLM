#!/usr/bin/env python3

import random
import unittest

from model.v5_schedule_contract import (
    BYTES_PER_SOURCE_RECORD,
    COMPUTE_COLUMNS,
    HIDDEN,
    INTERMEDIATE,
    SOURCE_COLUMNS,
    build_supertile_schedule,
    build_v5_layer_model,
    ceil_div,
    gate_up_source_tiles,
    repack_dense_12_to_16,
    repack_dense_16_to_12,
)


class V5ScheduleContractTests(unittest.TestCase):
    def check_width(self, width: int, expected_tail_records: int,
                    expected_tail_pass_valid: tuple[int, ...]) -> None:
        schedule = build_supertile_schedule(width)
        self.assertEqual(sum(len(item.source_records) for item in schedule),
                         ceil_div(width, SOURCE_COLUMNS))
        self.assertEqual(sum(len(item.compute_passes) for item in schedule),
                         ceil_div(width, COMPUTE_COLUMNS))
        self.assertEqual(len(schedule[-1].source_records),
                         expected_tail_records)
        self.assertEqual(tuple(item.valid_columns
                               for item in schedule[-1].compute_passes),
                         expected_tail_pass_valid)

        columns = [lane.global_column for item in schedule
                   for output_pass in item.compute_passes
                   for lane in output_pass.lanes]
        self.assertEqual(columns, list(range(width)))
        for item in schedule:
            for output_pass in item.compute_passes:
                for lane in output_pass.lanes:
                    self.assertIn(lane.source_record, item.source_records)
                    self.assertEqual(
                        lane.global_column,
                        lane.source_record * SOURCE_COLUMNS + lane.source_lane)

    def test_intermediate_shape_and_tail(self):
        self.check_width(INTERMEDIATE, 2, (12, 12, 8))
        schedule = build_supertile_schedule(INTERMEDIATE)
        self.assertEqual(len(schedule), 299)
        self.assertEqual(sum(len(x.source_records) for x in schedule), 896)
        self.assertEqual(sum(len(x.compute_passes) for x in schedule), 1195)

    def test_hidden_shape_and_tail(self):
        self.check_width(HIDDEN, 1, (12, 4))
        schedule = build_supertile_schedule(HIDDEN)
        self.assertEqual(len(schedule), 86)
        self.assertEqual(sum(len(x.source_records) for x in schedule), 256)
        self.assertEqual(sum(len(x.compute_passes) for x in schedule), 342)

    def test_gate_up_v4_tile_gather_is_contiguous(self):
        schedule = build_supertile_schedule(INTERMEDIATE)
        flattened = [tile for item in schedule
                     for tile in gate_up_source_tiles(item)]
        self.assertEqual(flattened, list(range(1792)))
        self.assertEqual(gate_up_source_tiles(schedule[0]),
                         (0, 1, 2, 3, 4, 5))
        self.assertEqual(gate_up_source_tiles(schedule[-1]),
                         (1788, 1789, 1790, 1791))

    def test_roundtrip_repack_is_dense_and_bit_exact(self):
        rng = random.Random(0x4838_5605)
        for width in (1, 4, 12, 16, 17, 32, 47, 48, 49,
                      HIDDEN, INTERMEDIATE):
            dense = [rng.getrandbits(32) for _ in range(width)]
            records = []
            for start in range(0, width, SOURCE_COLUMNS):
                payload = dense[start:start + SOURCE_COLUMNS]
                records.append(tuple(payload + [0] *
                                     (SOURCE_COLUMNS - len(payload))))
            passes = repack_dense_16_to_12(records, width, 0)
            rebuilt = repack_dense_12_to_16(passes, width, 0)
            self.assertEqual(tuple(records), rebuilt)
            self.assertEqual([value for item in passes for value in item]
                             [:width], dense)

    def test_layer_transaction_and_performance_model(self):
        model = build_v5_layer_model()
        self.assertEqual(model.gate_up_source_records, 1792)
        self.assertEqual(model.gate_up_source_transactions, 229_376)
        self.assertEqual(model.gate_up_compute_passes, 2390)
        self.assertEqual(model.gate_up_compute_transactions, 305_920)
        self.assertEqual(model.down_source_records_per_group, 256)
        self.assertEqual(model.down_source_transactions, 114_688)
        self.assertEqual(model.down_compute_passes_per_group, 342)
        self.assertEqual(model.down_compute_transactions, 153_216)
        self.assertEqual(model.mlp_weight_bytes,
                         (229_376 + 114_688) * BYTES_PER_SOURCE_RECORD)
        self.assertEqual(model.mlp_weight_bytes, 84 * (1 << 20))
        self.assertEqual(model.kernel_dsp, 3072)
        self.assertAlmostEqual(model.kernel_tops, 1.8432, places=4)
        self.assertAlmostEqual(
            model.projection_kernel_roof_tokens_per_s, 163.49, places=1)
        self.assertEqual(model.serial_mlp_cycles_per_layer, 527_296)
        self.assertAlmostEqual(
            model.serial_mlp_aggregate_tokens_per_s, 142.24, places=1)

    def test_invalid_shapes_fail_closed(self):
        with self.assertRaises(ValueError):
            build_supertile_schedule(0)
        with self.assertRaises(ValueError):
            repack_dense_16_to_12([], 16, 0)
        with self.assertRaises(ValueError):
            repack_dense_12_to_16([], 12, 0)


if __name__ == "__main__":
    unittest.main()
