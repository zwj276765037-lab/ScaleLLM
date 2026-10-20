#!/usr/bin/env python3

import unittest

from model.v5_gate_up_gather_contract import (
    COMPUTE_COLUMNS,
    HIDDEN_GROUPS,
    INTERMEDIATE,
    SOURCE_COLUMNS,
    GateUpGatherBank,
    SourceTransaction,
    ZERO_LANE,
    audit_full_gather,
    block_shapes,
    expected_legacy_tiles,
    gather_resources,
    low_mask,
    projection_passes,
    simulate_buffer_schedule,
    simulate_inverse_backpressure,
    source_transactions,
)


class V5GateUpGatherContractTests(unittest.TestCase):
    def test_full_shape_tile_major_to_pass_major_is_bit_exact(self):
        source_count, compute_count = audit_full_gather()
        self.assertEqual(source_count, 229_376)
        self.assertEqual(compute_count, 305_920)

    def test_exact_v4_source_order_and_14336_tail_masks(self):
        shapes = block_shapes(INTERMEDIATE)
        self.assertEqual(len(shapes), 299)
        self.assertTrue(all(shape.valid_columns == 48
                            for shape in shapes[:-1]))
        tail = shapes[-1]
        self.assertEqual(tail.first_column, 14_304)
        self.assertEqual(tail.valid_columns, 32)
        self.assertEqual(tail.source_records_per_matrix, 2)
        self.assertEqual(tail.compute_passes_per_matrix, 3)
        self.assertEqual(tail.source_transactions, 512)
        self.assertEqual(tail.compute_transactions, 768)

        transactions = list(source_transactions(tail, INTERMEDIATE))
        # Existing tile-major order: gate record894 all 128 groups, then up
        # record894, gate record895, up record895.
        boundary_tags = [
            (transactions[index].matrix,
             transactions[index].global_record,
             transactions[index].k_group)
            for index in (0, 127, 128, 255, 256, 383, 384, 511)
        ]
        self.assertEqual(boundary_tags, [
            (0, 894, 0), (0, 894, 127),
            (1, 894, 0), (1, 894, 127),
            (0, 895, 0), (0, 895, 127),
            (1, 895, 0), (1, 895, 127),
        ])

        bank = GateUpGatherBank(tail)
        for transaction in transactions:
            bank.accept(transaction)
        bank.seal()
        drained = list(bank.drain())
        masks = []
        for output_pass in range(3):
            # One representative group from gate and up has the same mask.
            masks.append(drained[output_pass * 2 * HIDDEN_GROUPS].valid_mask)
        self.assertEqual(masks, [low_mask(12, 12),
                                 low_mask(12, 12), low_mask(8, 12)])
        for transaction in drained[-HIDDEN_GROUPS:]:
            self.assertEqual(transaction.valid_mask, low_mask(8, 12))
            self.assertEqual(transaction.lanes[8:], (ZERO_LANE,) * 4)

    def test_inverse_repack_restores_legacy_gate_up_order_under_backpressure(self):
        simulation = simulate_inverse_backpressure(INTERMEDIATE)
        self.assertEqual(simulation.input_count,
                         len(projection_passes(INTERMEDIATE)))
        self.assertEqual(simulation.input_count, 2_390)
        self.assertEqual(simulation.output_count, 1_792)
        self.assertEqual(simulation.outputs,
                         expected_legacy_tiles(INTERMEDIATE))
        self.assertGreater(simulation.input_stall_cycles, 0)
        self.assertGreater(simulation.output_stall_cycles, 0)
        self.assertGreater(simulation.stable_input_checks, 0)
        self.assertGreater(simulation.stable_output_checks, 0)
        self.assertEqual(simulation.outputs[-4:], (
            expected_legacy_tiles(INTERMEDIATE)[-4],
            expected_legacy_tiles(INTERMEDIATE)[-3],
            expected_legacy_tiles(INTERMEDIATE)[-2],
            expected_legacy_tiles(INTERMEDIATE)[-1],
        ))

    def test_ping_pong_hides_full_shape_source_fill(self):
        single = simulate_buffer_schedule(INTERMEDIATE, banks=1)
        ping_pong = simulate_buffer_schedule(INTERMEDIATE, banks=2)
        self.assertEqual(single.source_transactions, 229_376)
        self.assertEqual(single.compute_transactions, 305_920)
        self.assertEqual(single.cycles, 535_296)
        self.assertEqual(ping_pong.source_transactions, 229_376)
        self.assertEqual(ping_pong.compute_transactions, 305_920)
        self.assertEqual(ping_pong.cycles, 306_688)
        self.assertEqual(ping_pong.cycles - ping_pong.compute_transactions,
                         768)
        # Full blocks have 256 cycles of source slack: 768 fill versus 1024
        # compute.  This is a model, not measured DDR availability.
        full = block_shapes(INTERMEDIATE)[0]
        self.assertEqual(full.compute_transactions - full.source_transactions,
                         256)

    def test_random_ready_valid_stalls_are_lossless_and_stable(self):
        # Four full 48-column blocks plus a 32-column tail, with non-production
        # group count only to keep the randomized state-space test fast.
        simulation = simulate_buffer_schedule(
            4 * 48 + 32, groups=7, banks=2, seed=0xBACC_4812,
            source_probability=0.79, compute_ready_probability=0.67)
        shapes = block_shapes(4 * 48 + 32, groups=7)
        self.assertEqual(simulation.source_transactions,
                         sum(shape.source_transactions for shape in shapes))
        self.assertEqual(simulation.compute_transactions,
                         sum(shape.compute_transactions for shape in shapes))
        self.assertGreater(simulation.source_stall_cycles, 0)
        self.assertGreater(simulation.compute_stall_cycles, 0)
        self.assertGreater(simulation.stable_source_checks, 0)
        self.assertGreater(simulation.stable_compute_checks, 0)

    def test_capacity_and_bram_mapping(self):
        resources = gather_resources()
        self.assertEqual(resources.weight_bits_per_bank, 1_572_864)
        self.assertEqual(resources.metadata_bits_per_bank, 172_032)
        self.assertEqual(resources.useful_bits_per_bank,
                         768 * (2048 + 224))
        self.assertEqual(resources.useful_bits_per_bank, 1_744_896)
        self.assertEqual(resources.ping_pong_useful_bits, 3_489_792)
        self.assertEqual(resources.naive_source_record_ramb36_per_bank, 64)
        # 12 lane banks x ceil(142/36) RAMB36 in 1024x36 TDP mode.
        self.assertEqual(resources.ramb36_per_bank, 48)
        self.assertEqual(resources.central_ping_pong_ramb36, 96)
        self.assertEqual(resources.duplicated_outer_slr_ramb36, 192)
        self.assertEqual(resources.inverse_tail_bits, 9_216)
        self.assertEqual(resources.optional_inverse_output_skid_bits, 6_144)

    def test_illegal_tile_or_metadata_order_fails_closed(self):
        shape = block_shapes(48)[0]
        first = next(source_transactions(shape, 48))
        bank = GateUpGatherBank(shape)
        wrong_matrix = SourceTransaction(
            block=first.block,
            matrix=1,
            record_in_block=first.record_in_block,
            global_record=first.global_record,
            k_group=first.k_group,
            valid_mask=first.valid_mask,
            lanes=first.lanes,
        )
        with self.assertRaises(ValueError):
            bank.accept(wrong_matrix)

        bad_lanes = list(first.lanes)
        bad_lanes[0] = ZERO_LANE
        bad_payload = SourceTransaction(
            block=first.block,
            matrix=first.matrix,
            record_in_block=first.record_in_block,
            global_record=first.global_record,
            k_group=first.k_group,
            valid_mask=first.valid_mask,
            lanes=tuple(bad_lanes),
        )
        with self.assertRaises(ValueError):
            GateUpGatherBank(shape).accept(bad_payload)

        bad_mask = SourceTransaction(
            block=first.block,
            matrix=first.matrix,
            record_in_block=first.record_in_block,
            global_record=first.global_record,
            k_group=first.k_group,
            valid_mask=low_mask(SOURCE_COLUMNS - 1, SOURCE_COLUMNS),
            lanes=first.lanes,
        )
        with self.assertRaises(ValueError):
            GateUpGatherBank(shape).accept(bad_mask)


if __name__ == "__main__":
    unittest.main()
