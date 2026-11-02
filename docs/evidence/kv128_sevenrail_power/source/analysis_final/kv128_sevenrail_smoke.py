#!/usr/bin/env python3
"""Verify the immediate-read seven-rail JSONL schema and smoke cadence offline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from kv128_sevenrail_analyze import RAILS, analyze_pilot, read_word, require, stats, verify_point


def analyze_smoke(metadata: dict, records: list[dict]) -> dict:
    require(metadata.get("schema") == "scalellm_kv128_sevenrail_pmbus_v1"
            and metadata.get("status") == "COMPLETE" and metadata.get("pass") is True
            and metadata.get("read_only") is True and metadata.get("writes") is False
            and metadata.get("read_errors") == 0, "Smoke sampler status/identity differs")
    frequency = metadata["qpc_frequency"]
    require(type(frequency) is int and frequency > 0, "Smoke QPC frequency invalid")
    modes = {}
    calibration = []
    for rail in metadata["configuration"]:
        address = rail["address"]
        require(address not in modes, "Duplicate rail mode")
        modes[address] = read_word(rail["read"], "VOUT_MODE")
        for read in rail.get("calibration", []):
            require(read["command"] in ("IOUT_CAL_GAIN", "IOUT_CAL_OFFSET")
                    and read["command_code"] in (0x38, 0x39)
                    and read["expected_bytes"] == 2,
                    "Unknown or malformed calibration command")
            calibration.append({"address": address, "command": read["command"],
                                "api_status": read["api_status"], "raw_hex": read["raw_hex"],
                                "error": read["error"], "read_id": read["read_id"]})
    require(set(modes) == {address for address, _, _ in RAILS}, "Seven rail modes missing")
    pending = {}
    read_count = 0
    config_count = 0
    points = []
    sweeps = []
    legacy = []
    previous_end = None
    for row in records:
        kind = row.get("record")
        if kind == "bus_read":
            read_count += 1
            require(row.get("read_id") == read_count and row.get("run_id") == metadata["run_id"]
                    and row.get("qpc_frequency") == frequency
                    and row.get("native_ack_status") == "NOT_EXPOSED_BY_OFFICIAL_API"
                    and row.get("fresh_hardware_read") is True
                    and type(row.get("before_ticks")) is int
                    and type(row.get("after_ticks")) is int
                    and row["before_ticks"] < row["after_ticks"],
                    "Immediate bus read identity/QPC sequence differs")
            if previous_end is not None:
                require(previous_end <= row["before_ticks"], "PMBus reads overlap/out of order")
            previous_end = row["after_ticks"]
            if row["api_status"] == "returned":
                raw = bytes.fromhex(row["raw_hex"])
                require(len(raw) == row["expected_bytes"] == row["byte_count"]
                        and row["word_le"] == int.from_bytes(raw, "little")
                        and row["error"] is None, "Returned bus code/length differs")
            else:
                require(row["api_status"] == "error" and row["error"],
                        "Undocumented bus API status")
            pending[read_count] = row
        elif kind == "configuration":
            config_count += 1
            require(config_count <= 7 and row["address"] == RAILS[config_count - 1][0]
                    and row["read"]["read_id"] in pending
                    and pending.pop(row["read"]["read_id"]) == row["read"]
                    and read_word(row["read"], "VOUT_MODE") == modes[row["address"]],
                    "Configuration read linkage/order differs")
            legacy.append(row)
        elif kind == "rail_point":
            index = len(points)
            require(config_count == 7 and row["sweep"] == index // 7
                    and row["position"] == index % 7
                    and row["address"] == RAILS[(row["sweep"] + row["position"]) % 7][0],
                    "Rotating sweep rail order differs")
            for field, command in (("read_vout", "READ_VOUT"),
                                   ("read_iout", "READ_IOUT"),
                                   ("read_pout", "READ_POUT")):
                nested = row[field]
                if nested is None:
                    require(command == "READ_POUT" and row["regulator"] == "MAX15301",
                            "Missing required rail read")
                    continue
                rid = nested["read_id"]
                require(rid in pending and pending.pop(rid) == nested,
                        "Rail read differs from immediate bus record")
            verify_point(row, modes[row["address"]])
            points.append(row)
            legacy.append(row)
        elif kind == "sweep":
            index = len(sweeps)
            require(row["sweep"] == index and len(points) == 7 * (index + 1)
                    and row["complete_rail_points"] == 7
                    and row["rail_order"] == [RAILS[(index + j) % 7][0] for j in range(7)]
                    and row["start_ticks"] < row["end_ticks"],
                    "Sweep completion/order/QPC differs")
            p = points[7 * index:7 * (index + 1)]
            require(row["start_ticks"] <= p[0]["vi_before_ticks"]
                    and p[-1]["point_after_ticks"] <= row["end_ticks"],
                    "Sweep bounds do not contain rail reads")
            sweeps.append(row)
        else:
            raise ValueError(f"Unexpected smoke record {kind!r}")
    for rail in metadata["configuration"]:
        for read in rail.get("calibration", []):
            rid = read["read_id"]
            require(rid in pending and pending.pop(rid) == read,
                    "Calibration code differs from immediate bus record")
    require(not pending and config_count == 7 and len(sweeps) == metadata["complete_sweeps"]
            and len(points) == metadata["complete_rail_points"] == 7 * len(sweeps)
            and read_count == 7 + len(calibration) + 17 * len(sweeps),
            "Smoke bus read/point/sweep totals differ")
    pilot = analyze_pilot(metadata, legacy)
    period_ms = [(right["start_ticks"] - left["start_ticks"]) * 1000 / frequency
                 for left, right in zip(sweeps, sweeps[1:])]
    duration_ms = [(row["end_ticks"] - row["start_ticks"]) * 1000 / frequency
                   for row in sweeps]
    late_ms = [row["late_ticks"] * 1000 / frequency for row in sweeps]
    target = metadata["target_period_ms"]
    require(target > 0 and metadata["missed_deadlines"]
            == sum(value > 2 for value in late_ms), "Target cadence or deadline count differs")
    return {"schema": "scalellm_kv128_sevenrail_smoke_analysis_v1", "status": "PASS",
            "run_id": metadata["run_id"], "boot_utc": metadata["boot_utc"],
            "qpc_frequency": frequency, "complete_sweeps": len(sweeps),
            "complete_rail_points": len(points), "immediate_bus_reads": read_count,
            "calibration": calibration, "target_period_ms": target,
            "actual_sweep_period_ms": stats(period_ms),
            "sweep_duration_ms": stats(duration_ms),
            "deadline_lateness_ms": stats(late_ms),
            "missed_deadlines_gt_2ms": metadata["missed_deadlines"],
            "max20751_vi_minus_pout_w": pilot["max20751_vi_minus_pout_w"],
            "rail_raw_word_counts": pilot["rail_raw_word_counts"],
            "sensor_aperture_and_lag": None,
            "strict_physical_active_mean_w": None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--jsonl", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    metadata = json.loads(args.metadata.read_text(encoding="utf-8-sig"))
    records = [json.loads(line) for line in args.jsonl.read_text(encoding="utf-8-sig").splitlines()
               if line.strip()]
    result = analyze_smoke(metadata, records)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
