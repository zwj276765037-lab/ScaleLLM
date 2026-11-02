#!/usr/bin/env python3
"""Offline raw-code verification and cadence report for the seven-rail pilot.

This module never accesses PMBus or the FPGA. A point is a pair of sequential
fresh VOUT/IOUT transactions; MAX20751 also has a subsequent fresh POUT read.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import statistics


RAILS = (
    ("0x70", "VCCINT_FPGA", "MAX20751"),
    ("0x11", "VCC1V8_FPGA", "MAX15301"),
    ("0x12", "VADJ_1V8_FPGA", "MAX15301"),
    ("0x15", "VCCINTIO_BRAM_FPGA", "MAX15301"),
    ("0x14", "VCC1V2_FPGA", "MAX15301"),
    ("0x72", "MGTAVCC_FPGA", "MAX20751"),
    ("0x73", "MGTAVTT_FPGA", "MAX20751"),
)
COMMANDS = {"VOUT_MODE": (0x20, 1), "READ_VOUT": (0x8B, 2),
            "READ_IOUT": (0x8C, 2), "READ_POUT": (0x96, 2)}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def signed_bits(value: int, width: int) -> int:
    return value - (1 << width) if value & (1 << (width - 1)) else value


def linear11(word: int) -> tuple[int, int, float]:
    exponent = signed_bits(word >> 11, 5)
    mantissa = signed_bits(word & 0x7FF, 11)
    return exponent, mantissa, math.ldexp(float(mantissa), exponent)


def vid_vr12(word: int) -> float | None:
    return 0.25 + (word - 1) / 200.0 if 1 <= word <= 255 else None


def linear16_vout(word: int, mode: int) -> float | None:
    if mode & 0xE0:
        return None
    return math.ldexp(float(word), signed_bits(mode & 31, 5))


def read_word(read: dict, command: str) -> int:
    code, size = COMMANDS[command]
    require(read is not None and read.get("command") == command, f"Missing {command}")
    require(read.get("command_code") == code and read.get("expected_bytes") == size,
            f"{command} command/length identity differs")
    require(read.get("api_status") == "returned" and read.get("error") is None
            and read.get("fresh_hardware_read") is True, f"{command} API did not return a fresh read")
    raw = bytes.fromhex(read["raw_hex"])
    require(len(raw) == size and read["word_le"] == int.from_bytes(raw, "little"),
            f"{command} raw bytes/word differ")
    require(type(read["before_ticks"]) is int and type(read["after_ticks"]) is int
            and read["before_ticks"] < read["after_ticks"], f"{command} QPC bounds invalid")
    return int.from_bytes(raw, "little")


def near(actual: float | None, expected: float | None, label: str) -> None:
    if expected is None:
        require(actual is None, f"{label} should be null")
    else:
        require(actual is not None and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12),
                f"{label} differs from raw bytes")


def verify_point(point: dict, mode: int) -> dict:
    address, name, regulator = next(
        (rail for rail in RAILS if rail[0] == point.get("address")), (None, None, None))
    require(address is not None and point.get("name") == name
            and point.get("regulator") == regulator and point.get("mode_word") == mode,
            "Rail identity or cached mode differs")
    vr, ir, pr = (point.get("read_vout"), point.get("read_iout"), point.get("read_pout"))
    vw, iw = read_word(vr, "READ_VOUT"), read_word(ir, "READ_IOUT")
    require(vr["after_ticks"] <= ir["before_ticks"], "VOUT/IOUT read order differs")
    require(point["vi_before_ticks"] == vr["before_ticks"]
            and point["vi_after_ticks"] == ir["after_ticks"], "VI pair bounds differ")
    iexp, _, current = linear11(iw)
    if regulator == "MAX20751":
        require(mode == 0x20, "MAX20751 must use VID mode 0x20")
        voltage = vid_vr12(vw)
        require(iexp == -1, "MAX20751 IOUT exponent differs from documented format")
        pw = read_word(pr, "READ_POUT")
        require(ir["after_ticks"] <= pr["before_ticks"], "POUT read order differs")
        pexp, _, pout = linear11(pw)
        require(pexp == 1, "MAX20751 POUT exponent differs from documented format")
        require(point["pout_status"] == "PMBUS_LINEAR11", "POUT status differs")
        near(point.get("pout_w"), pout, "POUT")
        end = pr["after_ticks"]
    else:
        voltage = linear16_vout(vw, mode)
        require(voltage is not None, "MAX15301 VOUT mode is not Linear16")
        require(pr is None and point["pout_status"] == "NOT_SUPPORTED_BY_DOCUMENTED_COMMAND_SET",
                "MAX15301 POUT must be absent")
        near(point.get("pout_w"), None, "unsupported POUT")
        pout = None
        end = ir["after_ticks"]
    near(point.get("voltage_v"), voltage, "VOUT")
    near(point.get("current_a"), current, "IOUT")
    near(point.get("vi_w"), None if voltage is None else voltage * current, "VxI")
    require(point.get("point_after_ticks") == end
            and point.get("physical_aperture_contained_busy") is None
            and point.get("sensor_aperture_and_lag") == "UNKNOWN",
            "Point end or sensor-aperture declaration differs")
    return {"address": address, "name": name, "regulator": regulator,
            "voltage_v": voltage, "current_a": current, "vi_w": point.get("vi_w"),
            "pout_w": pout, "vi_midpoint_ticks": (vr["before_ticks"] + ir["after_ticks"]) / 2,
            "pout_midpoint_ticks": None if pr is None else (pr["before_ticks"] + pr["after_ticks"]) / 2,
            "vi_bounds": (vr["before_ticks"], ir["after_ticks"]),
            "pout_bounds": None if pr is None else (pr["before_ticks"], pr["after_ticks"]),
            "read_bounds": (vr["before_ticks"], end),
            "latency_ticks": {"READ_VOUT": vr["after_ticks"] - vr["before_ticks"],
                              "READ_IOUT": ir["after_ticks"] - ir["before_ticks"],
                              **({"READ_POUT": pr["after_ticks"] - pr["before_ticks"]} if pr else {})},
            "raw_words": {"READ_VOUT": vw, "READ_IOUT": iw,
                          **({"READ_POUT": pw} if pr else {})}}


def stats(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "min": None, "median": None, "mean": None, "p95": None, "max": None}
    ordered = sorted(values)
    return {"count": len(values), "min": ordered[0], "median": statistics.median(ordered),
            "mean": statistics.fmean(ordered), "p95": ordered[math.ceil(.95 * len(ordered)) - 1],
            "max": ordered[-1]}


def analyze_pilot(metadata: dict, records: list[dict]) -> dict:
    require(metadata.get("schema") == "scalellm_kv128_sevenrail_pmbus_v1"
            and metadata.get("status") == "COMPLETE" and metadata.get("pass") is True
            and metadata.get("read_only") is True and metadata.get("writes") is False
            and metadata.get("address_scan") is False, "Pilot identity/status failed")
    freq = metadata.get("qpc_frequency")
    require(type(freq) is int and freq > 0 and metadata.get("sensor_aperture_and_lag") == "UNKNOWN",
            "QPC or sensor uncertainty metadata missing")
    q = metadata["qpc_validation"]
    require(q["native_before_ticks"] - 2 <= q["stopwatch_ticks"] <= q["native_after_ticks"] + 2,
            "Native/Stopwatch QPC differs")
    config = {}
    for item in metadata["configuration"]:
        addr = item["address"]
        require(addr not in config, "Duplicate rail configuration")
        config[addr] = read_word(item["read"], "VOUT_MODE")
    require(set(config) == {address for address, _, _ in RAILS}, "Seven rail modes incomplete")
    config_records = [r for r in records if r.get("record") == "configuration"]
    require(len(config_records) == 7, "Seven raw configuration records required")
    for item in config_records:
        require(item["address"] in config and read_word(item["read"], "VOUT_MODE") == config[item["address"]],
                "Configuration JSONL/summary mismatch")
    require(not [r for r in records if r.get("record") not in ("configuration", "rail_point")],
            "Pilot has unknown/error record")
    raw_points = [r for r in records if r.get("record") == "rail_point"]
    count = metadata["complete_sweeps"]
    require(count >= 1 and len(raw_points) == 7 * count == metadata["complete_rail_points"]
            and metadata["read_errors"] == 0, "Sweep/point counts differ")
    latency: dict[str, list[float]] = defaultdict(list)
    rail_codes: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    rail_vi: dict[str, list[float]] = defaultdict(list)
    rail_pout: dict[str, list[float]] = defaultdict(list)
    delta: dict[str, list[float]] = defaultdict(list)
    sweep_bounds = []
    sweep_duration_ms = []
    for sweep in range(count):
        points = raw_points[7 * sweep:7 * (sweep + 1)]
        require(all(p.get("sweep") == sweep and p.get("position") == j
                    for j, p in enumerate(points)), "Sweep position/order differs")
        expected = [RAILS[(sweep + j) % 7][0] for j in range(7)]
        require([p["address"] for p in points] == expected, "Rotating rail schedule differs")
        starts = []
        ends = []
        for p in points:
            decoded = verify_point(p, config[p["address"]])
            address = decoded["address"]
            starts.append(decoded["read_bounds"][0]);ends.append(decoded["read_bounds"][1])
            for command, ticks in decoded["latency_ticks"].items():
                latency[command].append(ticks * 1000 / freq)
                latency[f"{address}:{command}"].append(ticks * 1000 / freq)
            for command, word in decoded["raw_words"].items():
                rail_codes[address][command][word] += 1
            if decoded["vi_w"] is not None:
                rail_vi[address].append(decoded["vi_w"])
            if decoded["pout_w"] is not None:
                rail_pout[address].append(decoded["pout_w"])
                if decoded["vi_w"] is not None:
                    delta[address].append(decoded["vi_w"] - decoded["pout_w"])
        require(all(ends[j] <= starts[j + 1] for j in range(6)), "Sweep read bounds overlap")
        sweep_bounds.append((starts[0], ends[-1]))
        sweep_duration_ms.append((ends[-1] - starts[0]) * 1000 / freq)
    periods_ms = [(sweep_bounds[j + 1][0] - sweep_bounds[j][0]) * 1000 / freq
                  for j in range(len(sweep_bounds) - 1)]
    require(all(x > 0 for x in periods_ms), "Sweep start times are not strictly increasing")
    period_p95 = stats(periods_ms)["p95"]
    target_ms = None if period_p95 is None else math.ceil(max(100.0, 1.25 * period_p95) / 10) * 10
    return {"schema": "scalellm_kv128_sevenrail_pilot_analysis_v1",
            "run_id": metadata.get("run_id"), "boot_utc": metadata.get("boot_utc"),
            "qpc_frequency": freq, "complete_sweeps": count, "complete_rail_points": len(raw_points),
            "read_latency_ms": {key: stats(values) for key, values in sorted(latency.items())},
            "sweep_duration_ms": stats(sweep_duration_ms),
            "sweep_period_ms": stats(periods_ms),
            "target_sweep_period_ms": target_ms,
            "target_period_rule": "ceil_10ms(max(100ms,1.25*p95_observed_sweep_period))",
            "rail_raw_word_counts": {rail: {cmd: dict(sorted(counts.items()))
                                           for cmd, counts in sorted(commands.items())}
                                     for rail, commands in sorted(rail_codes.items())},
            "rail_vi_w": {rail: stats(values) for rail, values in sorted(rail_vi.items())},
            "max20751_pout_w": {rail: stats(values) for rail, values in sorted(rail_pout.items())},
            "max20751_vi_minus_pout_w": {rail: stats(values) for rail, values in sorted(delta.items())},
            "max20751_documented_resolution": {"vout_v": .005, "iout_a": .5, "pout_w": 2},
            "sensor_update_is_not_sampling_period": True,
            "sensor_aperture_and_lag": None,
            "strict_physical_active_mean_w": None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--jsonl", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    metadata = json.loads(args.metadata.read_text(encoding="utf-8-sig"))
    records = [json.loads(line) for line in args.jsonl.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    result = analyze_pilot(metadata, records)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": "PASS", "result": str(args.output),
                      "target_sweep_period_ms": result["target_sweep_period_ms"]}))


if __name__ == "__main__":
    main()
