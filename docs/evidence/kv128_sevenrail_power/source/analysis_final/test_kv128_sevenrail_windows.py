#!/usr/bin/env python3
"""Synthetic common-coverage integration and raw read linkage checks."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

from test_kv128_sevenrail_analyze import make_pilot
import kv128_sevenrail_windows as subject


def formal_data():
    metadata, legacy = make_pilot()
    metadata["host"] = "TEST_HOST"
    metadata["missed_deadlines"] = 0
    read_id = 0
    records = []
    def formalize(read, source):
        read.update(record="bus_read", read_id=read_id,
                    run_id="test", qpc_frequency=10_000_000,
                    native_ack_status="NOT_EXPOSED_BY_OFFICIAL_API",
                    byte_count=read["expected_bytes"],
                    address=source["address"], name=source["name"],
                    regulator=source["regulator"])
    for item in legacy:
        if item["record"] == "configuration":
            read_id += 1
            formalize(item["read"], item)
            records.append(copy.deepcopy(item["read"]))
            records.append(item)
            continue
        for command in ("read_vout", "read_iout", "read_pout"):
            read = item[command]
            if read is not None:
                read_id += 1
                formalize(read, item)
                records.append(copy.deepcopy(read))
        records.append(item)
        if item["position"] == 6:
            points = [row for row in records if row.get("record") == "rail_point"
                      and row["sweep"] == item["sweep"]]
            records.append({"record": "sweep", "sweep": item["sweep"],
                            "complete_rail_points": 7,
                            "rail_order": [point["address"] for point in points],
                            "start_ticks": points[0]["vi_before_ticks"],
                            "end_ticks": points[-1]["point_after_ticks"],
                            "late_ticks": 0})
    window = {"record": "window", "kind": "full_kv128_step", "repeat_id": 1,
              "start_ticks": 1_000_000, "end_ticks": 3_700_000,
              "status": "COMPLETE", "host": "TEST_HOST", "boot_utc": "test",
              "run_id": "test", "qpc_frequency": 10_000_000}
    return metadata, records, [window]


class WindowTests(unittest.TestCase):
    def test_sealed_qpc_command_busy_and_host_gap_contract(self) -> None:
        relative = Path("0_Source/command_active_power/native/pilot_001/commands.jsonl")
        capture = next((parent / relative for parent in Path(__file__).resolve().parents
                        if (parent / relative).is_file()), None)
        self.assertIsNotNone(capture, "sealed QPC pilot fixture missing")
        with capture.open(encoding="utf-8") as stream:
            clock, _, old = [json.loads(next(stream)) for _ in range(3)]
        command = copy.deepcopy(old)
        command["descriptor_words"][2] = 8194
        command["descriptor_words"][3] = 127
        command["descriptor_words"][7] = 8194
        for slot in range(16):
            command["descriptor_words"][32 + 2 * slot] = 127
        command["descriptor"]["command_id"] = 8194
        command["descriptor_sha256"] = hashlib.sha256(
            struct.pack("<64I", *command["descriptor_words"])).hexdigest()
        command["positions"] = [127] * 16
        metadata = {key: clock[key] for key in ("host", "boot_utc", "run_id", "qpc_frequency")}
        window = {"kind": "mlp_repeat", "repeat_id": 1, "completed_commands": 1,
                  "start_ticks": command["start_write"]["before_ticks"] - 1,
                  "end_ticks": command["ack_write"]["after_ticks"] + 1}
        result = subject.analyze_command_trace(metadata, [clock, command], [window], [],
                                               .42 * clock["qpc_frequency"])
        row = result["windows"][0]
        self.assertEqual(row["command_count"], 1)
        self.assertGreater(row["busy_inner_seconds"], 0)
        self.assertEqual(row["busy_inner_common_telemetry_coverage_seconds"], 0)
        self.assertIsNone(row["busy_inner_strict_physical_mean_w"])
        self.assertAlmostEqual(row["host_gap_total_seconds"], 2 / clock["qpc_frequency"])
        inside = command["first_busy"]["after_ticks"] + 100
        points = [{"address": address, "name": name,
                   "vi_before_ticks": inside, "vi_after_ticks": inside + 100,
                   "vi_w": float(index + 1), "voltage_v": 1.0,
                   "current_a": float(index + 1),
                   "read_vout": {"read_id": index * 2 + 1, "raw_hex": "01 00"},
                   "read_iout": {"read_id": index * 2 + 2, "raw_hex": "02 00"}}
                  for index, (address, name, _) in enumerate(subject.RAILS)]
        conditioned = subject.analyze_command_trace(metadata, [clock, command], [window],
                                                    points, .42 * clock["qpc_frequency"])
        conditional_row = conditioned["windows"][0]
        self.assertEqual(conditional_row["busy_inner_conditional_vi_w_by_rail"]["0x70"]["count"], 1)
        self.assertIsNone(conditional_row["busy_inner_covered_telemetry_mean_w"])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "busy.csv"
            subject.export_busy_points_csv({"command_trace": conditioned}, output)
            self.assertEqual(len(output.read_text().splitlines()), 8)
            command_csv = Path(directory) / "commands.csv"
            subject.export_command_csv({"command_trace": conditioned}, command_csv)
            self.assertEqual(len(command_csv.read_text().splitlines()), 2)
            by_layer_csv = Path(directory) / "busy_by_layer.csv"
            subject.export_busy_by_opcode_layer_csv({"command_trace": conditioned},
                                                    by_layer_csv)
            self.assertEqual(len(by_layer_csv.read_text().splitlines()), 8)
        unobserved = copy.deepcopy(command)
        unobserved["status_observations"] = [row for row in unobserved["status_observations"]
                                             if row["value"] & 2]
        unobserved["status_reads"] = len(unobserved["status_observations"])
        unobserved["busy_reads"] = 0
        unobserved["first_busy"] = unobserved["last_busy"] = None
        no_busy = subject.analyze_command_trace(metadata, [clock, unobserved], [window], [],
                                                .42 * clock["qpc_frequency"])
        self.assertEqual(no_busy["windows"][0]["busy_inner_unavailable_command_ids"], [8194])
        self.assertIsNone(no_busy["windows"][0]["commands"][0]["busy_inner_seconds"])
        broken = copy.deepcopy(command)
        broken["status_observations"][0]["value"] = 4
        with self.assertRaisesRegex(ValueError, "START/STATUS/BUSY/DONE/ACK"):
            subject.analyze_command_trace(metadata, [clock, broken], [window], [],
                                          .42 * clock["qpc_frequency"])

    def test_common_coverage_and_quantization(self) -> None:
        metadata, records, windows = formal_data()
        result = subject.analyze_windows(metadata, records, windows, 100)
        row = result["windows"][0]
        expected = 3 * 5.525 + 4 * (7372 / 4096 * 664 / 512)
        self.assertAlmostEqual(row["total_covered_mean_w"], expected)
        self.assertIsNone(row["total_full_window_mean_w"])
        self.assertGreater(row["common_coverage_fraction"], 0)
        self.assertLess(row["common_coverage_fraction"], 1)
        self.assertAlmostEqual(row["max20751_vi_pout_comparison"]["0x70"]
                               ["matched_vi_minus_pout_mean_w"], -.475)
        self.assertAlmostEqual(row["max20751_vi_pout_comparison"]["0x70"]
                               ["vi_current_step_w"]["mean"], .425)
        self.assertIsNone(result["strict_physical_active_mean_w"])

    def test_window_boundaries_use_bracketing_points(self) -> None:
        metadata, records, windows = formal_data()
        # Every rail has valid observations on both sides of these bounds,
        # although their complete read envelopes need not fit in the window.
        windows[0]["start_ticks"] = 1_800_000
        windows[0]["end_ticks"] = 3_000_000
        row = subject.analyze_windows(metadata, records, windows, 100)["windows"][0]
        self.assertEqual(row["common_coverage_fraction"], 1)
        self.assertIsNotNone(row["total_full_window_mean_w"])
        self.assertEqual(row["common_missing_seconds"], 0)
        self.assertTrue(all(value < 3 for value in row["rail_vi_point_count"].values()))
        self.assertGreater(row["max20751_vi_pout_comparison"]["0x70"]
                           ["matched_coverage_seconds"], 0)

    def test_no_interpolation_across_gap_or_failed_point(self) -> None:
        metadata, records, windows = formal_data()
        continuous = subject.analyze_windows(metadata, records, windows, 100)
        # An invalid point remains as a barrier, so nearby valid points cannot
        # be joined across the failed measurement.
        series = {address: [(0.0, 1.0), (1.0, 1.0), (2.0, 1.0)]
                  for address, _, _ in subject.RAILS}
        original = subject.coverage_and_energy(series, 0, 2, 1, 3)
        series["0x70"][1] = (1.0, None)
        blocked = subject.coverage_and_energy(series, 0, 2, 1, 3)
        self.assertEqual(original["common_coverage_fraction"], 1)
        self.assertEqual(blocked["common_coverage_fraction"], 0)
        self.assertGreater(continuous["windows"][0]["common_coverage_fraction"], 0)

    def test_nested_sample_must_match_standalone_bus_read(self) -> None:
        metadata, records, windows = formal_data()
        broken = copy.deepcopy(records)
        point = next(r for r in broken if r.get("record") == "rail_point")
        point["read_vout"]["raw_hex"] = "00 00"
        with self.assertRaisesRegex(ValueError, "immediately logged bus read"):
            subject.analyze_windows(metadata, broken, windows, 100)


if __name__ == "__main__":
    unittest.main()
