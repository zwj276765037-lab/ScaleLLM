"""Offline pilot validation and pre-run cadence freeze from raw sweep starts."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from kv128_sevenrail_analyze import RAILS, analyze_pilot, stats
from portable_source import BIT_SHA, require, sha_file


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def freeze_pilot(metadata_path, jsonl_path, receipt_path):
    metadata = read_json(metadata_path)
    receipt = read_json(receipt_path)
    require(receipt.get("schema") == "scalellm_portable_power_launcher_v1"
            and receipt.get("action") == "pilot" and receipt.get("state") == "COMPLETE"
            and receipt.get("sampler_exit_code") == 0 and receipt.get("lease_released") is True
            and not receipt.get("survivors") and receipt.get("bit_sha256") == BIT_SHA,
            "Pilot launcher/native exit/lease identity differs")
    for key in ("run_id", "boot_utc", "qpc_frequency"):
        require(receipt.get(key) == metadata.get(key), "Pilot launcher/sampler identity differs: " + key)
    with Path(jsonl_path).open(encoding="utf-8-sig") as stream:
        records = [json.loads(line) for line in stream if line.strip()]
    allowed = {"configuration", "calibration", "bus_read", "rail_point", "sweep"}
    require(all(row.get("record") in allowed for row in records), "Pilot contains error/unknown records")
    # The frozen decoder validates raw words, signed codes, timing bounds,
    # seven rail order and all complete VI/POUT points without changing math.
    decoded = analyze_pilot(metadata, [row for row in records
                                    if row["record"] in ("configuration", "rail_point")])
    require(metadata.get("target_period_ms") == 0 and metadata.get("interval_ms") == 0
            and metadata["complete_sweeps"] >= 200, "Pilot must contain at least 200 unpaced sweeps")
    bus = {}
    sweeps = []
    points = []
    previous_after = 0
    for row in records:
        kind = row["record"]
        if kind == "bus_read":
            rid = row.get("read_id")
            require(rid == len(bus) + 1 and row.get("run_id") == metadata["run_id"]
                    and row.get("qpc_frequency") == metadata["qpc_frequency"]
                    and row.get("native_ack_status") == "NOT_EXPOSED_BY_OFFICIAL_API"
                    and row.get("fresh_hardware_read") is True
                    and type(row.get("before_ticks")) is int and type(row.get("after_ticks")) is int
                    and previous_after <= row["before_ticks"] <= row["after_ticks"],
                    "Pilot bus read sequence/provenance/timing differs")
            if row.get("command") not in ("IOUT_CAL_GAIN", "IOUT_CAL_OFFSET"):
                require(row.get("api_status") == "returned" and row.get("error") is None
                        and row.get("byte_count") == row.get("expected_bytes"),
                        "Pilot measurement read failed")
            previous_after = row["after_ticks"]
            bus[rid] = row
        elif kind == "rail_point":
            for key in ("read_vout", "read_iout", "read_pout"):
                nested = row.get(key)
                if nested is not None:
                    require(bus.get(nested.get("read_id")) == nested,
                            "Pilot point differs from immediately logged raw read")
            points.append(row)
        elif kind == "sweep":
            index = len(sweeps)
            require(row.get("sweep") == index and len(points) == 7 * (index + 1)
                    and row.get("complete_rail_points") == 7
                    and row.get("rail_order") == [RAILS[(index + offset) % 7][0] for offset in range(7)]
                    and row["start_ticks"] <= points[-7]["vi_before_ticks"]
                    and points[-1]["point_after_ticks"] <= row["end_ticks"],
                    "Pilot sweep bounds/count/rotation differ")
            sweeps.append(row)
    calibration = [read for rail in metadata["configuration"] for read in rail.get("calibration", [])]
    configuration = [rail["read"] for rail in metadata["configuration"]]
    for read in configuration + calibration:
        require(bus.get(read.get("read_id")) == read, "Pilot configuration/calibration raw provenance differs")
    require(len(sweeps) == metadata["complete_sweeps"]
            and len(bus) == 17 * len(sweeps) + 7 + len(calibration), "Pilot raw transaction count differs")
    frequency = metadata["qpc_frequency"]
    periods = [(right["start_ticks"] - left["start_ticks"]) * 1000 / frequency
               for left, right in zip(sweeps, sweeps[1:])]
    require(all(value > 0 for value in periods), "Pilot sweep starts are not increasing")
    cadence = stats(periods)
    target = math.ceil(max(100.0, 1.25 * cadence["p95"]) / 10) * 10
    return {"schema": "scalellm_portable_power_pilot_freeze_v1", "status": "PASS",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "pilot_metadata_sha256": sha_file(metadata_path), "pilot_jsonl_sha256": sha_file(jsonl_path),
            "pilot_receipt_sha256": sha_file(receipt_path),
            "pilot_run_id": metadata["run_id"], "boot_utc": metadata["boot_utc"],
            "host": metadata["host"], "qpc_frequency": frequency,
            "adapter_serial_sha256": metadata["adapter_serial_sha256"],
            "sampler_script_sha256": receipt["sampler_script_sha256"],
            "powertool_manifest_sha256": receipt["powertool_manifest_sha256"],
            "bit_sha256": BIT_SHA, "sweep_period_ms": cadence,
            "target_period_ms": target, "gap_threshold_ms": 3 * target,
            "formula": "ceil_10ms(max(100ms,1.25*p95_raw_sweep_start_to_start))",
            "period_source": "raw sweep.start_ticks", "frozen_before_formal_run": True,
            "decoded_pilot": decoded}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--jsonl", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = freeze_pilot(args.metadata, args.jsonl, args.receipt)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"status": "PASS", "target_period_ms": result["target_period_ms"],
                      "gap_threshold_ms": result["gap_threshold_ms"]}))


if __name__ == "__main__":
    main()
