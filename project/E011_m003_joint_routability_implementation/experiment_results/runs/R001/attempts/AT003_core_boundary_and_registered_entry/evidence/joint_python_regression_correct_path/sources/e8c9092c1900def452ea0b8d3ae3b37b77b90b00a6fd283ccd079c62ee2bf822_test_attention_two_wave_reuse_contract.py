#!/usr/bin/env python3

import unittest

from model.attention_two_wave_reuse_contract import (
    GROUPS,
    ProjectionSchedule,
    WaveConsumption,
    audit_projection_schedule,
    build_projection_schedule,
)


class AttentionTwoWaveReuseContractTests(unittest.TestCase):
    def test_full_tile_accepts_each_weight_once(self):
        schedule = build_projection_schedule()
        self.assertEqual(len(schedule.weights), GROUPS)
        self.assertEqual(len(schedule.consumptions), 2 * GROUPS)
        self.assertEqual(schedule.output_waves, (0, 1))
        self.assertEqual(schedule.physical_weight_bytes, 64 * 1024)
        self.assertEqual(schedule.reread_weight_bytes, 128 * 1024)
        audit_projection_schedule(schedule)

    def test_group_order_is_wave0_then_wave1(self):
        schedule = build_projection_schedule()
        for group in range(GROUPS):
            self.assertEqual(
                schedule.consumptions[2 * group:2 * group + 2],
                (WaveConsumption(group, 0, 0),
                 WaveConsumption(group, 1, 1)),
            )

    def test_missing_or_swapped_wave_fails_closed(self):
        schedule = build_projection_schedule(4)
        swapped = ProjectionSchedule(
            weights=schedule.weights,
            consumptions=(schedule.consumptions[1],
                          schedule.consumptions[0]) +
                         schedule.consumptions[2:],
            output_waves=schedule.output_waves,
        )
        with self.assertRaises(ValueError):
            audit_projection_schedule(swapped, groups=4)

    def test_invalid_group_count_is_rejected(self):
        for groups in (0, GROUPS + 1):
            with self.assertRaises(ValueError):
                build_projection_schedule(groups)


if __name__ == "__main__":
    unittest.main()

