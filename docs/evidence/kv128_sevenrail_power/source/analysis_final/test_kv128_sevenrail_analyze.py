#!/usr/bin/env python3
"""Independent known-code and synthetic seven-rail pilot checks (CPU only)."""
from __future__ import annotations

import copy
import unittest

import kv128_sevenrail_analyze as subject


def raw_read(command: str, word: int, before: int, after: int) -> dict:
    code, size = subject.COMMANDS[command]
    return {"command": command, "command_code": code, "before_ticks": before,
            "after_ticks": after, "raw_hex": word.to_bytes(size, "little").hex(" ").upper(),
            "word_le": word, "expected_bytes": size, "api_status": "returned",
            "error": None, "fresh_hardware_read": True}


def make_pilot(sweeps: int = 3) -> tuple[dict, list[dict]]:
    modes = {address: 0x20 if regulator == "MAX20751" else 0x14
             for address, _, regulator in subject.RAILS}
    config = []
    records = []
    for address, name, regulator in subject.RAILS:
        row = {"address": address, "name": name, "regulator": regulator,
               "read": raw_read("VOUT_MODE", modes[address], 100, 110)}
        config.append(row)
        records.append({"record": "configuration", **row})
    for sweep in range(sweeps):
        tick = 1_000_000 + 1_000_000 * sweep
        for position in range(7):
            address, name, regulator = subject.RAILS[(sweep + position) % 7]
            vword = 121 if regulator == "MAX20751" else 0x1CCC
            iword = 0xF80D if regulator == "MAX20751" else 0xBA98
            v = raw_read("READ_VOUT", vword, tick, tick + 10000)
            i = raw_read("READ_IOUT", iword, tick + 15000, tick + 25000)
            p = raw_read("READ_POUT", 0x0803, tick + 30000, tick + 40000) if regulator == "MAX20751" else None
            voltage = .85 if regulator == "MAX20751" else 7372 / 4096
            current = 6.5 if regulator == "MAX20751" else 664 / 512
            records.append({"record": "rail_point", "sweep": sweep, "position": position,
                            "address": address, "name": name, "regulator": regulator,
                            "mode_word": modes[address], "read_vout": v, "read_iout": i,
                            "read_pout": p,
                            "pout_status": "PMBUS_LINEAR11" if p else "NOT_SUPPORTED_BY_DOCUMENTED_COMMAND_SET",
                            "voltage_v": voltage,
                            "voltage_status": "MAX20751_VID_VR12_EQUATION28" if p else "PMBUS_LINEAR16",
                            "current_a": current, "current_status": "PMBUS_LINEAR11",
                            "pout_w": 6.0 if p else None, "vi_w": voltage * current,
                            "vi_before_ticks": v["before_ticks"], "vi_after_ticks": i["after_ticks"],
                            "point_after_ticks": p["after_ticks"] if p else i["after_ticks"],
                            "physical_aperture_contained_busy": None,
                            "sensor_aperture_and_lag": "UNKNOWN"})
            tick += 100000
    metadata = {"schema": "scalellm_kv128_sevenrail_pmbus_v1", "status": "COMPLETE",
                "pass": True, "read_only": True, "writes": False, "address_scan": False,
                "qpc_frequency": 10_000_000,
                "qpc_validation": {"native_before_ticks": 10, "stopwatch_ticks": 11,
                                   "native_after_ticks": 12},
                "sensor_aperture_and_lag": "UNKNOWN", "run_id": "test", "boot_utc": "test",
                "configuration": config, "complete_sweeps": sweeps,
                "complete_rail_points": sweeps * 7, "read_errors": 0}
    return metadata, records


class DecodeTests(unittest.TestCase):
    def test_known_board_bytes_and_vid_range(self) -> None:
        self.assertEqual(subject.vid_vr12(0x0079), 0.85)
        self.assertEqual(subject.vid_vr12(0x0083), 0.90)
        self.assertEqual(subject.vid_vr12(0x00BF), 1.20)
        self.assertIsNone(subject.vid_vr12(0))
        self.assertIsNone(subject.vid_vr12(256))
        self.assertEqual(subject.linear11(0xF80D), (-1, 13, 6.5))
        self.assertEqual(subject.linear11(0x0803), (1, 3, 6.0))
        self.assertEqual(subject.linear11(0xBA98), (-9, 664, 1.296875))
        self.assertEqual(subject.linear16_vout(0x1CCC, 0x14), 1.7998046875)

    def test_full_raw_pilot_and_cadence(self) -> None:
        metadata, records = make_pilot()
        result = subject.analyze_pilot(metadata, records)
        self.assertEqual(result["complete_rail_points"], 21)
        self.assertEqual(result["target_sweep_period_ms"], 130)
        self.assertEqual(result["rail_raw_word_counts"]["0x70"]["READ_VOUT"], {121: 3})
        self.assertAlmostEqual(result["max20751_vi_minus_pout_w"]["0x70"]["mean"], -0.475)
        self.assertIsNone(result["strict_physical_active_mean_w"])

    def test_wrong_endian_or_unsupported_pout_fails(self) -> None:
        metadata, records = make_pilot()
        wrong = copy.deepcopy(records)
        point = next(r for r in wrong if r.get("record") == "rail_point")
        point["read_vout"]["word_le"] = 0x7900
        with self.assertRaisesRegex(ValueError, "raw bytes/word"):
            subject.analyze_pilot(metadata, wrong)
        wrong = copy.deepcopy(records)
        point = next(r for r in wrong if r.get("record") == "rail_point" and r["regulator"] == "MAX15301")
        point["read_pout"] = raw_read("READ_POUT", 0x0803, 3, 4)
        with self.assertRaisesRegex(ValueError, "MAX15301 POUT must be absent"):
            subject.analyze_pilot(metadata, wrong)


if __name__ == "__main__":
    unittest.main()
