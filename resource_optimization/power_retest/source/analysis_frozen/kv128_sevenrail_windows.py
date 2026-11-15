#!/usr/bin/env python3
"""Time-weighted seven-rail PMBus telemetry for explicit repeated windows.

All numbers here are sensor telemetry. An unknown sensor averaging aperture and
lag keep physical command-active power and energy unverified.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left, bisect_right
from collections import defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import struct

from kv128_sevenrail_analyze import RAILS, read_word, require, stats, verify_point


KINDS = ("idle", "attention_repeat", "mlp_repeat", "full_kv128_step")


def analyze_command_trace(metadata: dict, trace: list[dict], windows: list[dict],
                          point_records: list[dict], gap_ticks: float) -> dict:
    """Validate every START/STATUS/DONE/ACK and report measured BUSY/gaps.

    Telemetry wholly inside conservative BUSY is reported separately from the
    complete host window. An unknown sensor aperture keeps physical active
    power null even if a short BUSY interval happens to contain rail samples.
    """
    require(trace and trace[0].get("record") == "clock"
            and all(row.get("record") == "command" for row in trace[1:]),
            "QPC command trace clock/records missing")
    clock = trace[0]
    for key in ("host", "boot_utc", "run_id", "qpc_frequency"):
        require(clock.get(key) == metadata.get(key), f"QPC command clock {key} differs")
    require(clock.get("schema") == "scalellm_command_qpc_v1", "QPC command schema differs")
    freq = metadata["qpc_frequency"]
    starts = [row["start_ticks"] for row in windows]
    groups = [[] for _ in windows]
    unwindowed = 0
    previous_id = None
    previous_ack = None
    by_rail = {address: [] for address, _, _ in RAILS}
    for point in point_records:
        by_rail[point["address"]].append(point)
    for points in by_rail.values():
        points.sort(key=lambda row: row["vi_before_ticks"])
    rail_before = {rail: [row["vi_before_ticks"] for row in points]
                   for rail, points in by_rail.items()}
    for command in trace[1:]:
        descriptor = command["descriptor"]
        words = command["descriptor_words"]
        command_id = descriptor["command_id"]
        require(type(command_id) is int and command_id > 8192
                and (previous_id is None or command_id == previous_id + 1)
                and len(words) == 64 and all(type(word) is int and 0 <= word < 2**32 for word in words)
                and descriptor == {"command_id": words[2], "layer": words[5],
                                   "opcode": words[4], "active_mask": words[6]}
                and hashlib.sha256(struct.pack("<64I", *words)).hexdigest()
                == command["descriptor_sha256"]
                and descriptor["active_mask"] == 65535
                and words[3] == 127 and words[7] == command_id
                and descriptor["opcode"] in (1, 2)
                and 0 <= descriptor["layer"] < 32
                and command["positions"] == [127] * 16
                and command["epochs"] == [1] * 16
                and command["core_hz"] == 80_000_000,
                "QPC command descriptor identity/sequence differs")
        previous_id = command_id
        observations = command["status_observations"]
        busy = [row for row in observations if row["value"] & 1 and not row["value"] & 2]
        done = [row for row in observations if row["value"] & 2]
        start, ack = command["start_write"], command["ack_write"]
        require(command["trace_state"] == "ACK_WRITTEN" and start and ack
                and done
                and command["first_busy"] == (busy[0] if busy else None)
                and command["last_busy"] == (busy[-1] if busy else None)
                and command["first_done"] == done[0]
                and command["status_reads"] == len(observations)
                and command["busy_reads"] == len(busy)
                and command["first_error_status"] is None
                and start["before_ticks"] < start["after_ticks"]
                <= done[0]["before_ticks"]
                and (not busy or start["after_ticks"] <= busy[0]["before_ticks"])
                and (not busy or busy[-1]["after_ticks"] <= done[0]["before_ticks"])
                and done[0]["after_ticks"] <= ack["before_ticks"] < ack["after_ticks"]
                and all(row["before_ticks"] < row["after_ticks"] for row in observations)
                and all(left["after_ticks"] <= right["before_ticks"]
                        for left, right in zip(observations, observations[1:]))
                and (previous_ack is None or previous_ack <= start["before_ticks"]),
                "QPC START/STATUS/BUSY/DONE/ACK bounds or error status differ")
        previous_ack = ack["after_ticks"]
        completions = {row["register"]: row["value"] for row in command["completion_reads"]}
        expected_output = 196608 if descriptor["opcode"] == 1 else 917504
        require(len(completions) == len(command["completion_reads"])
                and completions.get("ADMISSION_ERROR") == 0
                and completions.get("DONE_ERROR") == 0
                and completions.get("DONE_INPUT_BYTES") == 196608
                and completions.get("DONE_OUTPUT_BYTES") == expected_output
                and command["input_transfer"]["bytes"] == 196608
                and command["output_transfer"]["bytes"] == expected_output
                and type(command["done_cycles_read"]["value"]) is int
                and command["done_cycles_read"]["value"] > 0,
                "QPC command completion, transfer, or cycle receipt differs")
        inner_a = busy[0]["after_ticks"] + 2 if len(busy) >= 2 else None
        inner_b = busy[-1]["before_ticks"] - 2 if len(busy) >= 2 else None
        busy_interval_status = ("VALID" if inner_a is not None and inner_a < inner_b
                                else "NO_BUSY_OBSERVATION" if not busy
                                else "FEWER_THAN_TWO_BUSY_OBSERVATIONS" if len(busy) == 1
                                else "EMPTY_CONSERVATIVE_BUSY_INTERVAL")
        if busy_interval_status != "VALID":
            inner_a = inner_b = None
        index = bisect_right(starts, start["before_ticks"]) - 1
        if index < 0 or start["before_ticks"] < windows[index]["start_ticks"]:
            unwindowed += 1
            continue
        window = windows[index]
        if ack["after_ticks"] > window["end_ticks"]:
            require(start["before_ticks"] >= window["end_ticks"],
                    "QPC command crosses a measured window boundary")
            unwindowed += 1
            continue
        inner_series = {}
        inner_counts = {}
        inner_points = []
        for rail, points in by_rail.items():
            i = bisect_left(rail_before[rail], inner_a) if inner_a is not None else len(points)
            valid = []
            while i < len(points) and inner_b is not None and points[i]["vi_before_ticks"] <= inner_b:
                point = points[i]
                if point["vi_after_ticks"] <= inner_b and point["vi_w"] is not None:
                    valid.append(((point["vi_before_ticks"] + point["vi_after_ticks"]) / 2,
                                  point["vi_w"]))
                    inner_points.append({"address": rail, "name": point["name"],
                                         "command_id": command_id,
                                         "vi_before_ticks": point["vi_before_ticks"],
                                         "vi_after_ticks": point["vi_after_ticks"],
                                         "vout_read_id": point["read_vout"]["read_id"],
                                         "iout_read_id": point["read_iout"]["read_id"],
                                         "vout_raw_hex": point["read_vout"]["raw_hex"],
                                         "iout_raw_hex": point["read_iout"]["raw_hex"],
                                         "voltage_v": point["voltage_v"],
                                         "current_a": point["current_a"],
                                         "vi_w": point["vi_w"]})
                i += 1
            inner_series[rail] = valid
            inner_counts[rail] = len(valid)
        inner_telemetry = (coverage_and_energy(inner_series, inner_a, inner_b, freq, gap_ticks)
                           if inner_a is not None
                           and all(count >= 2 for count in inner_counts.values()) else None)
        groups[index].append({"command_id": command_id, "layer": descriptor["layer"],
                              "opcode": descriptor["opcode"],
                              "start_ticks": start["before_ticks"],
                              "ack_ticks": ack["after_ticks"],
                              "busy_inner_status": busy_interval_status,
                              "busy_inner_start_ticks": inner_a,
                              "busy_inner_end_ticks": inner_b,
                              "first_busy_read_after_ticks": busy[0]["after_ticks"] if busy else None,
                              "last_busy_read_before_ticks": busy[-1]["before_ticks"] if busy else None,
                              "wall_ms": (ack["after_ticks"] - start["before_ticks"]) * 1000 / freq,
                              "busy_reads": len(busy),
                              "busy_inner_seconds": (inner_b - inner_a) / freq
                              if inner_a is not None else None,
                              "cycle_seconds": command["done_cycles_read"]["value"] / 80_000_000,
                              "busy_inner_rail_vi_points": inner_counts,
                              "busy_inner_points": inner_points,
                              "busy_inner_telemetry": inner_telemetry})
    rows = []
    for window, commands in zip(windows, groups):
        kind = window["kind"]
        require(len(commands) == window.get("completed_commands"),
                "QPC command count differs from workload window journal")
        shape = [(row["layer"], row["opcode"]) for row in commands]
        if kind == "idle":
            require(not shape, "Idle window contains FPGA command")
        elif kind == "attention_repeat":
            require(shape and len(shape) % 5 == 0
                    and shape == [(layer, 1) for _ in range(len(shape) // 5)
                                  for layer in (0, 8, 16, 24, 31)],
                    "Attention repeat is not complete five-layer cycles")
        elif kind == "mlp_repeat":
            require(shape and all(pair == (0, 2) for pair in shape),
                    "MLP repeat includes a different command")
        else:
            require(shape == [(layer, opcode) for layer in range(32)
                              for opcode in (1, 2)],
                    "Full KV128 step lacks ordered 32-layer A/MLP command pairs")
        edges = [window["start_ticks"]]
        gaps = []
        for row in commands:
            gaps.append((row["start_ticks"] - edges[-1]) * 1000 / freq)
            edges.append(row["ack_ticks"])
        gaps.append((window["end_ticks"] - edges[-1]) * 1000 / freq)
        require(all(gap >= 0 for gap in gaps), "Negative host gap")
        gap_detail = ([{"kind": "window_before_first_start", "milliseconds": gaps[0]}]
                      + [{"kind": "between_ack_and_next_start", "milliseconds": gap}
                         for gap in gaps[1:-1]]
                      + [{"kind": "after_last_ack_to_window_end", "milliseconds": gaps[-1]}]
                      if commands else [{"kind": "entire_idle_window", "milliseconds": gaps[0]}])
        busy_seconds = sum(row["busy_inner_seconds"] or 0 for row in commands)
        cycle_seconds = sum(row["cycle_seconds"] for row in commands)
        telemetry_covered = sum(row["busy_inner_telemetry"]["common_coverage_seconds"]
                                for row in commands if row["busy_inner_telemetry"] is not None)
        telemetry_energy = sum(row["busy_inner_telemetry"]["total_covered_mean_w"]
                               * row["busy_inner_telemetry"]["common_coverage_seconds"]
                               for row in commands if row["busy_inner_telemetry"] is not None
                               and row["busy_inner_telemetry"]["total_covered_mean_w"] is not None)
        conditional = {address: [] for address, _, _ in RAILS}
        for command in commands:
            for point in command["busy_inner_points"]:
                conditional[point["address"]].append(point["vi_w"])
        rows.append({"kind": kind, "repeat_id": window["repeat_id"],
                     "command_count": len(commands),
                     "first_command_id": commands[0]["command_id"] if commands else None,
                     "last_command_id": commands[-1]["command_id"] if commands else None,
                     "busy_status_reads": sum(row["busy_reads"] for row in commands),
                     "busy_inner_valid_command_count": sum(
                         row["busy_inner_status"] == "VALID" for row in commands),
                     "busy_inner_unavailable_command_ids": [
                         row["command_id"] for row in commands
                         if row["busy_inner_status"] != "VALID"],
                     "busy_inner_seconds": busy_seconds,
                     "busy_inner_fraction_of_window": busy_seconds * freq
                     / (window["end_ticks"] - window["start_ticks"]),
                     "fpga_cycle_seconds_80mhz": cycle_seconds,
                     "command_wall_ms": stats([row["wall_ms"] for row in commands]),
                     "host_gap_ms": stats(gaps),
                     "host_gaps": gap_detail,
                     "host_gap_total_seconds": sum(gaps) / 1000,
                     "busy_inner_commands_with_two_vi_points_each_rail": sum(
                         all(count >= 2 for count in row["busy_inner_rail_vi_points"].values())
                         for row in commands),
                     "busy_inner_common_telemetry_coverage_seconds": telemetry_covered,
                     "busy_inner_covered_telemetry_mean_w":
                     telemetry_energy / telemetry_covered if telemetry_covered else None,
                     "busy_inner_conditional_vi_w_by_rail": {
                         rail: stats(values) for rail, values in conditional.items()},
                     "busy_inner_conditional_statistic":
                     "arithmetic point distribution for VI envelopes wholly within conservative BUSY, not a time-weighted active mean",
                     "busy_inner_strict_physical_mean_w": None,
                     "commands": commands})
    return {"schema": "scalellm_kv128_sevenrail_command_analysis_v1",
            "trace_command_count": len(trace) - 1,
            "outside_measured_windows": unwindowed,
            "busy_inner_unavailable_command_count": sum(
                len(row["busy_inner_unavailable_command_ids"]) for row in rows),
            "windows": rows,
            "busy_power_note": "Telemetry requires two wholly contained VI points per rail and common coverage; physical sensor aperture and lag remain unknown"}


def interval_at(points: list[tuple[float, float | None]], midpoint: float,
                gap_ticks: float, times: list[float] | None = None):
    if times is None:
        times = [point[0] for point in points]
    index = bisect_right(times, midpoint) - 1
    if index < 0 or index + 1 >= len(points):
        return None
    left, right = points[index], points[index + 1]
    if (right[0] <= left[0] or right[0] - left[0] > gap_ticks
            or left[1] is None or right[1] is None):
        return None
    return left, right


def at(left: tuple[float, float], right: tuple[float, float], tick: float) -> float:
    return left[1] + (right[1] - left[1]) * (tick - left[0]) / (right[0] - left[0])


def coverage_and_energy(series: dict[str, list[tuple[float, float | None]]],
                        start: int, end: int, freq: int, gap_ticks: float) -> dict:
    breaks = {float(start), float(end)}
    for points in series.values():
        breaks.update(t for t, _ in points if start < t < end)
    bounds = sorted(breaks)
    rails = list(series)
    times = {rail: [t for t, _ in series[rail]] for rail in rails}
    energy = dict.fromkeys(rails, 0.0)
    zoh_energy = dict.fromkeys(rails, 0.0)
    covered_ticks = 0.0
    covered_intervals = []
    for a, b in zip(bounds, bounds[1:]):
        if b <= a:
            continue
        segments = {rail: interval_at(series[rail], (a + b) / 2, gap_ticks, times[rail])
                    for rail in rails}
        if any(segment is None for segment in segments.values()):
            continue
        duration = (b - a) / freq
        for rail, (left, right) in segments.items():
            energy[rail] += (at(left, right, a) + at(left, right, b)) / 2 * duration
            zoh_energy[rail] += left[1] * duration
        covered_ticks += b - a
        if covered_intervals and covered_intervals[-1][1] == a:
            covered_intervals[-1][1] = b
        else:
            covered_intervals.append([a, b])
    covered_seconds = covered_ticks / freq
    window_seconds = (end - start) / freq
    fraction = covered_ticks / (end - start)
    complete = math.isclose(covered_ticks, end - start, rel_tol=0, abs_tol=2)
    covered_mean = {rail: (energy[rail] / covered_seconds if covered_seconds else None) for rail in rails}
    zoh_mean = {rail: (zoh_energy[rail] / covered_seconds if covered_seconds else None) for rail in rails}
    total = sum(energy.values()) / covered_seconds if covered_seconds else None
    zoh_total = sum(zoh_energy.values()) / covered_seconds if covered_seconds else None
    return {"window_seconds": window_seconds, "common_coverage_seconds": covered_seconds,
            "common_coverage_fraction": fraction,
            "common_missing_seconds": window_seconds - covered_seconds,
            "common_coverage_interval_count": len(covered_intervals),
            "rail_covered_mean_w": covered_mean,
            "total_covered_mean_w": total,
            "rail_full_window_mean_w": covered_mean if complete else dict.fromkeys(rails),
            "total_full_window_mean_w": total if complete else None,
            "rail_zoh_covered_mean_w": zoh_mean,
            "total_zoh_covered_mean_w": zoh_total,
            "zero_order_hold_minus_linear_total_w": None if total is None else zoh_total - total,
            "strict_physical_active_mean_w": None,
            "sensor_aperture_and_lag": None}


def one_rail_coverage(points: list[tuple[float, float | None]], start: int, end: int,
                      freq: int, gap_ticks: float) -> dict:
    covered_ticks = 0.0
    energy = 0.0
    for left, right in zip(points, points[1:]):
        if (left[1] is None or right[1] is None or right[0] - left[0] > gap_ticks):
            continue
        a, b = max(start, left[0]), min(end, right[0])
        if b <= a:
            continue
        covered_ticks += b - a
        energy += (at(left, right, a) + at(left, right, b)) / 2 * (b - a) / freq
    window_ticks = end - start
    complete = math.isclose(covered_ticks, window_ticks, rel_tol=0, abs_tol=2)
    return {"valid_point_count": sum(start <= tick <= end and value is not None
                                     for tick, value in points),
            "covered_seconds": covered_ticks / freq,
            "coverage_fraction": covered_ticks / window_ticks,
            "covered_mean_w": energy * freq / covered_ticks if covered_ticks else None,
            "full_window_mean_w": energy * freq / covered_ticks if complete and covered_ticks else None}


def validate_windows(windows: list[dict], metadata: dict) -> list[dict]:
    require(windows, "No repeat window records")
    validated = []
    seen = set()
    for item in windows:
        kind, repeat = item.get("kind"), item.get("repeat_id")
        require(item.get("record") == "window" and kind in KINDS
                and type(repeat) is int and repeat > 0, "Invalid window identity")
        require((kind, repeat) not in seen, "Duplicate kind/repeat window")
        seen.add((kind, repeat))
        start, end = item.get("start_ticks"), item.get("end_ticks")
        require(type(start) is int and type(end) is int and 0 < start < end,
                "Invalid window QPC bounds")
        for key in ("host", "boot_utc", "run_id", "qpc_frequency"):
            require(item.get(key) == metadata.get(key), f"Window/telemetry {key} differs")
        validated.append(item)
    validated.sort(key=lambda x: x["start_ticks"])
    require(all(validated[j]["end_ticks"] <= validated[j + 1]["start_ticks"]
                for j in range(len(validated) - 1)), "Repeated windows overlap")
    return validated


def analyze_windows(metadata: dict, records: list[dict], windows: list[dict],
                    target_period_ms: int, commands: list[dict] | None = None) -> dict:
    require(metadata.get("schema") == "scalellm_kv128_sevenrail_pmbus_v1"
            and metadata.get("pass") is True and metadata.get("status") == "COMPLETE"
            and metadata.get("read_only") is True and metadata.get("writes") is False
            and metadata.get("read_errors") == 0,
            "Sampler identity/status invalid")
    freq = metadata["qpc_frequency"]
    require(type(freq) is int and freq > 0 and type(target_period_ms) is int
            and target_period_ms >= 100 and target_period_ms % 10 == 0,
            "QPC or pilot target period invalid")
    gap_ticks = 3 * target_period_ms / 1000 * freq
    windows = validate_windows(windows, metadata)
    modes = {}
    for item in metadata["configuration"]:
        require(item["address"] not in modes, "Duplicate VOUT_MODE rail")
        modes[item["address"]] = read_word(item["read"], "VOUT_MODE")
    require(set(modes) == {address for address, _, _ in RAILS}, "Seven VOUT_MODE rails missing")
    starts = [w["start_ticks"] for w in windows]
    # Integrate the continuous per-rail record, including samples immediately
    # before and after a window. Restricting this series to wholly contained
    # reads loses the bracketing samples needed to interpolate at its bounds.
    all_vi = {address: [] for address, _, _ in RAILS}
    all_pout = {address: [] for address, _, regulator in RAILS
                if regulator == "MAX20751"}
    contained_vi_counts = [{address: 0 for address, _, _ in RAILS} for _ in windows]
    contained_pout_counts = [{address: 0 for address in all_pout} for _ in windows]
    quantization = [{address: {"iout_step_w": [], "vout_step_w": []}
                     for address, _, regulator in RAILS if regulator == "MAX20751"}
                    for _ in windows]
    point_counts = 0
    point_records = []
    bus_reads = {}
    expected_read_id = 1
    sweep_count = 0
    sweep_records = []
    read_latency_ms = defaultdict(list)
    for raw in records:
        if raw.get("record") in ("configuration", "calibration"):
            continue
        if raw.get("record") == "bus_read":
            rid = raw.get("read_id")
            require(type(rid) is int and rid == expected_read_id,
                    "Bus read ID is missing, duplicated, or out of order")
            expected_read_id += 1
            require(raw.get("run_id") == metadata["run_id"]
                    and raw.get("qpc_frequency") == freq
                    and raw.get("native_ack_status") == "NOT_EXPOSED_BY_OFFICIAL_API"
                    and (raw.get("api_status") == "error"
                         or raw.get("byte_count") == raw.get("expected_bytes")),
                    "Bus read provenance or byte count differs")
            read_latency_ms[raw["command"]].append(
                (raw["after_ticks"] - raw["before_ticks"]) * 1000 / freq)
            bus_reads[rid] = raw
            continue
        if raw.get("record") == "sweep":
            require(raw.get("sweep") == sweep_count
                    and point_counts == 7 * (sweep_count + 1)
                    and raw.get("complete_rail_points") == 7
                    and raw.get("rail_order") == [RAILS[(sweep_count + j) % 7][0]
                                                  for j in range(7)]
                    and raw["start_ticks"] <= point_records[-7]["vi_before_ticks"]
                    and point_records[-1]["point_after_ticks"] <= raw["end_ticks"],
                    "Sweep rotation/count/QPC bounds differ")
            sweep_records.append(raw)
            sweep_count += 1
            continue
        require(raw.get("record") == "rail_point", "Sampler error/unknown record")
        require(raw.get("sweep") == point_counts // 7
                and raw.get("position") == point_counts % 7
                and raw.get("address") == RAILS[(raw["sweep"] + raw["position"]) % 7][0],
                "Rail point sweep identity/rotation differs")
        for key, command in (("read_vout", "READ_VOUT"), ("read_iout", "READ_IOUT"),
                             ("read_pout", "READ_POUT")):
            nested = raw.get(key)
            if nested is None:
                require(command == "READ_POUT" and raw.get("regulator") == "MAX15301",
                        "Missing required bus read")
                continue
            rid = nested.get("read_id")
            require(rid in bus_reads and bus_reads.pop(rid) == nested,
                    "Rail sample does not match immediately logged bus read")
        point = verify_point(raw, modes[raw["address"]])
        point_counts += 1
        point_records.append(raw)
        vi_value = (point["vi_w"] if point["vi_bounds"][1] - point["vi_bounds"][0]
                    <= gap_ticks else None)
        all_vi[point["address"]].append((point["vi_midpoint_ticks"], vi_value))
        if point["regulator"] == "MAX20751":
            pout_value = (point["pout_w"] if point["pout_w"] is not None
                          and point["pout_bounds"][1] - point["pout_bounds"][0]
                          <= gap_ticks else None)
            all_pout[point["address"]].append((point["pout_midpoint_ticks"], pout_value))
        index = bisect_right(starts, point["vi_midpoint_ticks"]) - 1
        if index < 0 or index >= len(windows):
            continue
        window = windows[index]
        a, b = window["start_ticks"], window["end_ticks"]
        if a <= point["vi_bounds"][0] and point["vi_bounds"][1] <= b and vi_value is not None:
            contained_vi_counts[index][point["address"]] += 1
            if point["regulator"] == "MAX20751":
                quantization[index][point["address"]]["iout_step_w"].append(abs(point["voltage_v"]) * .5)
                quantization[index][point["address"]]["vout_step_w"].append(abs(point["current_a"]) * .005)
        if point["pout_w"] is not None:
            pout_index = bisect_right(starts, point["pout_midpoint_ticks"]) - 1
            if pout_index >= 0 and pout_index < len(windows):
                pout_window = windows[pout_index]
                if (pout_window["start_ticks"] <= point["pout_bounds"][0]
                        and point["pout_bounds"][1] <= pout_window["end_ticks"]):
                    contained_pout_counts[pout_index][point["address"]] += 1
    require(point_counts == metadata["complete_rail_points"], "Raw point count/metadata differs")
    require(sweep_count == metadata["complete_sweeps"], "Sweep records/metadata differ")
    sweep_period_ms = [(right["start_ticks"] - left["start_ticks"]) * 1000 / freq
                       for left, right in zip(sweep_records, sweep_records[1:])]
    sweep_duration_ms = [(row["end_ticks"] - row["start_ticks"]) * 1000 / freq
                         for row in sweep_records]
    sweep_lateness_ms = [row["late_ticks"] * 1000 / freq for row in sweep_records]
    require(metadata.get("missed_deadlines") == sum(x > 2 for x in sweep_lateness_ms),
            "Sampler deadline count differs")
    for item in metadata["configuration"]:
        for raw in [item["read"], *item.get("calibration", [])]:
            rid = raw["read_id"]
            require(rid in bus_reads and bus_reads.pop(rid) == raw,
                    "Configuration read differs from immediate raw bus record")
    require(not bus_reads, "Unreferenced bus reads remain")
    for series in (*all_vi.values(), *all_pout.values()):
        require(all(series[j][0] < series[j + 1][0]
                    for j in range(len(series) - 1)),
                "Rail midpoint order/duplication invalid")
    rows = []
    for index, window in enumerate(windows):
        measured = coverage_and_energy(all_vi, window["start_ticks"], window["end_ticks"],
                                       freq, gap_ticks)
        rail_coverage = {rail: one_rail_coverage(points, window["start_ticks"],
                                                window["end_ticks"], freq, gap_ticks)
                         for rail, points in all_vi.items()}
        if measured["window_seconds"] > 20:
            trimmed = coverage_and_energy(all_vi, window["start_ticks"] + 10 * freq,
                                          window["end_ticks"] - 10 * freq, freq, gap_ticks)
        else:
            trimmed = None
        comparisons = {}
        for rail, pout_points in all_pout.items():
            deltas = []
            for tick, pout_w in pout_points:
                if not (window["start_ticks"] <= tick <= window["end_ticks"]) or pout_w is None:
                    continue
                segment = interval_at(all_vi[rail], tick, gap_ticks)
                if segment is not None:
                    deltas.append(at(*segment, tick) - pout_w)
            matched = coverage_and_energy({"vi": all_vi[rail], "pout": pout_points},
                                          window["start_ticks"], window["end_ticks"],
                                          freq, gap_ticks)
            vi_mean = matched["rail_covered_mean_w"]["vi"]
            pout_mean = matched["rail_covered_mean_w"]["pout"]
            comparisons[rail] = {"pout_point_count": contained_pout_counts[index][rail],
                                 "vi_minus_pout_w": stats(deltas),
                                 "matched_coverage_seconds": matched["common_coverage_seconds"],
                                 "matched_vi_covered_mean_w": vi_mean,
                                 "matched_pout_covered_mean_w": pout_mean,
                                 "matched_vi_minus_pout_mean_w": None if vi_mean is None else vi_mean - pout_mean,
                                 "pout_resolution_w": 2.0,
                                 "vi_current_step_w": stats(quantization[index][rail]["iout_step_w"]),
                                 "vi_voltage_step_w": stats(quantization[index][rail]["vout_step_w"]),
                                 "comparison_is_asynchronous": True}
        rows.append({"kind": window["kind"], "repeat_id": window["repeat_id"],
                     "window_status": window.get("status"),
                     "start_ticks": window["start_ticks"], "end_ticks": window["end_ticks"],
                     "rail_vi_point_count": contained_vi_counts[index],
                     "rail_coverage": rail_coverage,
                     "trimmed_10s": trimmed,
                     "max20751_vi_pout_comparison": comparisons,
                     **measured})
    def accepted(row: dict) -> bool:
        if row["window_status"] not in ("COMPLETE", "PASS") or row["total_covered_mean_w"] is None:
            return False
        if row["kind"] in ("idle", "attention_repeat", "mlp_repeat") and row["window_seconds"] < 120:
            return False
        if row["kind"] in ("idle", "attention_repeat", "mlp_repeat") and min(row["rail_vi_point_count"].values()) < 200:
            return False
        return True

    kind_counts = {kind: sum(r["kind"] == kind and accepted(r) for r in rows) for kind in KINDS}
    repeat_differences = {}
    for kind in KINDS:
        data = sorted((r for r in rows if r["kind"] == kind and accepted(r)),
                      key=lambda r: r["repeat_id"])
        values = [r["total_covered_mean_w"] for r in data]
        sd = statistics.stdev(values) if len(values) >= 2 else None
        mean = statistics.fmean(values) if values else None
        covered_seconds = sum(r["common_coverage_seconds"] for r in data)
        repeat_differences[kind] = {
            "accepted_repeat_count": len(data),
            "equal_repeat_covered_mean_w": mean,
            "sample_sd_w": sd,
            "coefficient_of_variation": sd / abs(mean) if sd is not None and mean else None,
            "range_w": max(values) - min(values) if values else None,
            "pooled_by_common_coverage_mean_w": (sum(r["total_covered_mean_w"] * r["common_coverage_seconds"]
                                                       for r in data) / covered_seconds if covered_seconds else None),
            "covered_total_mean_w": stats(values),
            "pairwise_delta_w": [{"left_repeat": left["repeat_id"], "right_repeat": right["repeat_id"],
                                   "right_minus_left_w": right["total_covered_mean_w"] - left["total_covered_mean_w"]}
                                  for i, left in enumerate(data) for right in data[i + 1:]],
            "by_rail": {}}
        for address, _, _ in RAILS:
            rail_rows = [(row["repeat_id"], row["rail_covered_mean_w"][address],
                          row["common_coverage_seconds"]) for row in data]
            rail_values = [value for _, value, _ in rail_rows if value is not None]
            rail_sd = statistics.stdev(rail_values) if len(rail_values) >= 2 else None
            rail_mean = statistics.fmean(rail_values) if rail_values else None
            rail_coverage = sum(seconds for _, value, seconds in rail_rows if value is not None)
            repeat_differences[kind]["by_rail"][address] = {
                "covered_mean_w": stats(rail_values),
                "sample_sd_w": rail_sd,
                "coefficient_of_variation": rail_sd / abs(rail_mean)
                if rail_sd is not None and rail_mean else None,
                "range_w": max(rail_values) - min(rail_values) if rail_values else None,
                "pooled_by_common_coverage_mean_w":
                (sum(value * seconds for _, value, seconds in rail_rows if value is not None)
                 / rail_coverage if rail_coverage else None),
                "pairwise_delta_w": [{"left_repeat": left[0], "right_repeat": right[0],
                                       "right_minus_left_w": right[1] - left[1]}
                                      for i, left in enumerate(rail_rows)
                                      for right in rail_rows[i + 1:]
                                      if left[1] is not None and right[1] is not None]}
    idle_by_repeat = {r["repeat_id"]: r for r in rows if r["kind"] == "idle" and accepted(r)}
    idle_paired = [{"kind": r["kind"], "repeat_id": r["repeat_id"],
                    "load_minus_idle_covered_mean_w": r["total_covered_mean_w"]
                    - idle_by_repeat[r["repeat_id"]]["total_covered_mean_w"],
                    "rail_load_minus_idle_covered_mean_w": {
                        address: r["rail_covered_mean_w"][address]
                        - idle_by_repeat[r["repeat_id"]]["rail_covered_mean_w"][address]
                        for address, _, _ in RAILS}}
                   for r in rows if r["kind"] != "idle" and accepted(r)
                   and r["repeat_id"] in idle_by_repeat]
    command_analysis = (analyze_command_trace(metadata, commands, windows,
                                              point_records, gap_ticks)
                        if commands is not None else None)
    if command_analysis is not None:
        for row, trace_row in zip(rows, command_analysis["windows"]):
            row["command_count"] = trace_row["command_count"]
            row["busy_inner_covered_telemetry_mean_w"] = trace_row[
                "busy_inner_covered_telemetry_mean_w"]
            row["busy_inner_common_telemetry_coverage_seconds"] = trace_row[
                "busy_inner_common_telemetry_coverage_seconds"]
    complete_windows = sum(row["total_full_window_mean_w"] is not None for row in rows)
    covered_only_windows = sum(row["total_full_window_mean_w"] is None
                               and row["total_covered_mean_w"] is not None for row in rows)
    status = ("INCOMPLETE_REPEATS" if not all(count >= 3 for count in kind_counts.values())
              else "PARTIAL_WITH_LIMITS" if covered_only_windows else "PASS_WITH_LIMITS")
    return {"schema": "scalellm_kv128_sevenrail_repeat_analysis_v1",
            "status": status,
            "raw_record_validation_status": "PASS",
            "complete_common_coverage_window_count": complete_windows,
            "covered_only_window_count": covered_only_windows,
            "target_sweep_period_ms": target_period_ms,
            "maximum_interpolated_gap_ms": 3 * target_period_ms,
            "actual_sweep_period_ms": stats(sweep_period_ms),
            "sweep_duration_ms": stats(sweep_duration_ms),
            "sweep_deadline_lateness_ms": stats(sweep_lateness_ms),
            "missed_deadlines_gt_2ms": metadata["missed_deadlines"],
            "read_latency_ms": {name: stats(values)
                                for name, values in sorted(read_latency_ms.items())},
            "calibration_readback": [{"address": rail["address"],
                                      "command": read["command"],
                                      "api_status": read["api_status"],
                                      "raw_hex": read["raw_hex"],
                                      "error": read["error"]}
                                     for rail in metadata["configuration"]
                                     for read in rail.get("calibration", [])],
            "window_counts": kind_counts,
            "windows": rows, "repeat_differences": repeat_differences,
            "idle_paired_differences": idle_paired,
            "command_trace": command_analysis,
            "time_method": "per-rail VI envelope midpoint; linear between adjacent valid points; common seven-rail intersection only",
            "zero_order_hold_sensitivity_included": True,
            "pout_is_asynchronous_coarse_comparison": True,
            "strict_physical_active_mean_w": None,
            "sensor_aperture_and_lag": None}


def plot(result: dict, path: Path) -> None:
    import matplotlib.pyplot as plt
    figure, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    kinds = list(KINDS)
    palette = {"idle": "#737373", "attention_repeat": "#277da1",
               "mlp_repeat": "#f9844a", "full_kv128_step": "#43aa8b"}
    for x, kind in enumerate(kinds):
        rows = [r for r in result["windows"] if r["kind"] == kind]
        for row in rows:
            shift = (row["repeat_id"] - 2) * .13
            color = palette[kind]
            if row["total_covered_mean_w"] is not None:
                axes[0].scatter(x + shift, row["total_covered_mean_w"], color=color, s=52)
                axes[0].plot([x + shift, x + shift],
                             [row["total_covered_mean_w"], row["total_zoh_covered_mean_w"]],
                             color=color, alpha=.45)
            axes[1].bar(x + shift, row["common_coverage_fraction"] * 100,
                        color=color, width=.10, alpha=.72)
        dispersion = result["repeat_differences"][kind]
        if dispersion["accepted_repeat_count"] == 3:
            axes[0].errorbar(x + .26, dispersion["equal_repeat_covered_mean_w"],
                             yerr=dispersion["sample_sd_w"], color="#111111",
                             marker="D", ms=4, capsize=4, lw=1,
                             label="three-repeat mean ± sample SD" if x == 0 else None)
    axes[0].set_ylabel("Seven-rail telemetry on common coverage (W)")
    axes[1].set_ylabel("Common window coverage (%)")
    axes[1].set_ylim(0, 105)
    axes[1].set_xticks(range(len(kinds)), ["Idle", "Attention repeat", "MLP repeat", "Full KV128 step"])
    axes[0].set_title("Seven-rail PMBus repeats: each dot is one window")
    axes[0].legend(loc="upper right", frameon=False, fontsize=8)
    axes[0].grid(axis="y", alpha=.25);axes[1].grid(axis="y", alpha=.25)
    figure.text(.5, .005, "Black mean ± sample SD shows repeat dispersion, not measurement accuracy. "
                "Sensor aperture/lag and strict physical active mean remain unknown.",
                ha="center", fontsize=8)
    figure.tight_layout(rect=(0,.03,1,1))
    figure.savefig(path, dpi=180)
    plt.close(figure)


def export_raw_csv(records: list[dict], windows: list[dict], path: Path) -> None:
    """One lossless-code row per observed rail point; JSONL remains primary."""
    fieldnames = ("run_id", "sweep", "position", "phase", "block_id", "repeat_id", "window_kind",
                  "window_repeat_id", "address", "name", "regulator", "mode_word",
                  "vout_read_id", "vout_before_ticks", "vout_after_ticks", "vout_raw_hex",
                  "vout_word_le", "vout_api_status", "iout_read_id", "iout_before_ticks",
                  "iout_after_ticks", "iout_raw_hex", "iout_word_le", "iout_api_status",
                  "pout_read_id", "pout_before_ticks", "pout_after_ticks", "pout_raw_hex",
                  "pout_word_le", "pout_api_status", "pout_status", "voltage_v",
                  "current_a", "vi_w", "pout_w", "sensor_aperture_and_lag")
    starts = [window["start_ticks"] for window in windows]
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for point in records:
            if point.get("record") != "rail_point":
                continue
            v, i, p = (point["read_vout"], point["read_iout"], point["read_pout"])
            index = bisect_right(starts, point["vi_before_ticks"]) - 1
            window = (windows[index] if index >= 0
                      and point["point_after_ticks"] <= windows[index]["end_ticks"] else None)
            row = {"run_id": point["run_id"],
                   "sweep": point["sweep"], "position": point["position"],
                   "phase": point.get("phase"), "block_id": point.get("block_id"),
                   "repeat_id": point.get("repeat_id"),
                   "window_kind": window["kind"] if window else None,
                   "window_repeat_id": window["repeat_id"] if window else None,
                   "address": point["address"], "name": point["name"],
                   "regulator": point["regulator"], "mode_word": point["mode_word"],
                   "pout_status": point["pout_status"], "voltage_v": point["voltage_v"],
                   "current_a": point["current_a"], "vi_w": point["vi_w"],
                   "pout_w": point["pout_w"],
                   "sensor_aperture_and_lag": point["sensor_aperture_and_lag"]}
            for prefix, read in (("vout", v), ("iout", i), ("pout", p)):
                for field, key in (("read_id", "read_id"), ("before_ticks", "before_ticks"),
                                   ("after_ticks", "after_ticks"), ("raw_hex", "raw_hex"),
                                   ("word_le", "word_le"), ("api_status", "api_status")):
                    row[f"{prefix}_{field}"] = read[key] if read is not None else None
            writer.writerow(row)


def export_window_csv(result: dict, path: Path) -> None:
    fields = ("kind", "repeat_id", "address", "name", "regulator", "window_seconds",
              "valid_vi_points", "rail_coverage_seconds", "rail_coverage_fraction",
              "rail_covered_mean_w", "rail_full_window_mean_w", "rail_zoh_covered_mean_w",
              "common_coverage_seconds", "common_coverage_fraction", "common_rail_mean_w",
              "common_total_mean_w", "common_total_full_window_mean_w",
              "pout_point_count", "pout_resolution_w", "matched_coverage_seconds",
              "matched_vi_mean_w", "matched_pout_mean_w", "matched_vi_minus_pout_w",
              "command_count", "busy_inner_seconds", "busy_inner_common_coverage_seconds",
              "busy_inner_covered_telemetry_mean_w", "fpga_cycle_seconds_80mhz",
              "host_gap_total_seconds", "strict_physical_active_mean_w")
    fields = fields + ("busy_conditional_point_count", "busy_conditional_arithmetic_mean_w",
                       "busy_conditional_median_w", "busy_conditional_min_w",
                       "busy_conditional_max_w")
    command_lookup = {}
    if result["command_trace"] is not None:
        command_lookup = {(row["kind"], row["repeat_id"]): row
                          for row in result["command_trace"]["windows"]}
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for window in result["windows"]:
            command = command_lookup.get((window["kind"], window["repeat_id"]), {})
            for address, name, regulator in RAILS:
                rail = window["rail_coverage"][address]
                pout = window["max20751_vi_pout_comparison"].get(address, {})
                conditional = command.get("busy_inner_conditional_vi_w_by_rail", {}).get(
                    address, {})
                writer.writerow({
                    "kind": window["kind"], "repeat_id": window["repeat_id"],
                    "address": address, "name": name, "regulator": regulator,
                    "window_seconds": window["window_seconds"],
                    "valid_vi_points": window["rail_vi_point_count"][address],
                    "rail_coverage_seconds": rail["covered_seconds"],
                    "rail_coverage_fraction": rail["coverage_fraction"],
                    "rail_covered_mean_w": rail["covered_mean_w"],
                    "rail_full_window_mean_w": rail["full_window_mean_w"],
                    "rail_zoh_covered_mean_w": window["rail_zoh_covered_mean_w"][address],
                    "common_coverage_seconds": window["common_coverage_seconds"],
                    "common_coverage_fraction": window["common_coverage_fraction"],
                    "common_rail_mean_w": window["rail_covered_mean_w"][address],
                    "common_total_mean_w": window["total_covered_mean_w"],
                    "common_total_full_window_mean_w": window["total_full_window_mean_w"],
                    "pout_point_count": pout.get("pout_point_count"),
                    "pout_resolution_w": pout.get("pout_resolution_w"),
                    "matched_coverage_seconds": pout.get("matched_coverage_seconds"),
                    "matched_vi_mean_w": pout.get("matched_vi_covered_mean_w"),
                    "matched_pout_mean_w": pout.get("matched_pout_covered_mean_w"),
                    "matched_vi_minus_pout_w": pout.get("matched_vi_minus_pout_mean_w"),
                    "command_count": command.get("command_count"),
                    "busy_inner_seconds": command.get("busy_inner_seconds"),
                    "busy_inner_common_coverage_seconds": command.get(
                        "busy_inner_common_telemetry_coverage_seconds"),
                    "busy_inner_covered_telemetry_mean_w": command.get(
                        "busy_inner_covered_telemetry_mean_w"),
                    "fpga_cycle_seconds_80mhz": command.get("fpga_cycle_seconds_80mhz"),
                    "host_gap_total_seconds": command.get("host_gap_total_seconds"),
                    "strict_physical_active_mean_w": None,
                    "busy_conditional_point_count": conditional.get("count"),
                    "busy_conditional_arithmetic_mean_w": conditional.get("mean"),
                    "busy_conditional_median_w": conditional.get("median"),
                    "busy_conditional_min_w": conditional.get("min"),
                    "busy_conditional_max_w": conditional.get("max")})


def export_busy_points_csv(result: dict, path: Path) -> None:
    fields = ("kind", "repeat_id", "command_id", "address", "name",
              "vi_before_ticks", "vi_after_ticks", "vout_read_id", "iout_read_id",
              "vout_raw_hex", "iout_raw_hex", "voltage_v", "current_a", "vi_w")
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for window in result["command_trace"]["windows"]:
            for command in window["commands"]:
                for point in command["busy_inner_points"]:
                    writer.writerow({"kind": window["kind"],
                                     "repeat_id": window["repeat_id"], **point})


def export_busy_by_opcode_layer_csv(result: dict, path: Path) -> None:
    """Conditional observed VI points; never an active time-weighted mean."""
    fields = ("kind", "repeat_id", "opcode", "layer", "address", "name",
              "sampled_command_count", "total_command_count", "point_count",
              "arithmetic_mean_w", "median_w", "min_w", "max_w",
              "statistic_type")
    groups = {}
    for window in result["command_trace"]["windows"]:
        for command in window["commands"]:
            key = (window["kind"], window["repeat_id"], command["opcode"], command["layer"])
            entry = groups.setdefault(key, {"total": 0, "rails": {address: []
                                      for address, _, _ in RAILS},
                                      "sampled": {address: set() for address, _, _ in RAILS}})
            entry["total"] += 1
            for point in command["busy_inner_points"]:
                entry["rails"][point["address"]].append(point["vi_w"])
                entry["sampled"][point["address"]].add(command["command_id"])
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for (kind, repeat, opcode, layer), entry in sorted(groups.items()):
            for address, name, _ in RAILS:
                observed = stats(entry["rails"][address])
                writer.writerow({"kind": kind, "repeat_id": repeat,
                                 "opcode": opcode, "layer": layer,
                                 "address": address, "name": name,
                                 "sampled_command_count": len(entry["sampled"][address]),
                                 "total_command_count": entry["total"],
                                 "point_count": observed["count"],
                                 "arithmetic_mean_w": observed["mean"],
                                 "median_w": observed["median"],
                                 "min_w": observed["min"], "max_w": observed["max"],
                                 "statistic_type": "observed VI points wholly inside conservative BUSY; not time weighted"})


def export_command_csv(result: dict, path: Path) -> None:
    fields = ("kind", "repeat_id", "command_id", "layer", "opcode", "start_ticks",
              "ack_ticks", "first_busy_read_after_ticks", "last_busy_read_before_ticks",
              "busy_inner_start_ticks", "busy_inner_end_ticks", "busy_inner_seconds",
              "busy_inner_status", "busy_reads", "wall_ms", "cycle_seconds_80mhz", "host_gap_before_ms",
              "busy_inner_conditional_vi_point_count", "busy_inner_common_coverage_seconds",
              "busy_inner_covered_telemetry_mean_w")
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for window in result["command_trace"]["windows"]:
            gaps = window["host_gaps"]
            for index, command in enumerate(window["commands"]):
                telemetry = command["busy_inner_telemetry"]
                writer.writerow({
                    "kind": window["kind"], "repeat_id": window["repeat_id"],
                    "command_id": command["command_id"], "layer": command["layer"],
                    "opcode": command["opcode"], "start_ticks": command["start_ticks"],
                    "ack_ticks": command["ack_ticks"],
                    "first_busy_read_after_ticks": command["first_busy_read_after_ticks"],
                    "last_busy_read_before_ticks": command["last_busy_read_before_ticks"],
                    "busy_inner_start_ticks": command["busy_inner_start_ticks"],
                    "busy_inner_end_ticks": command["busy_inner_end_ticks"],
                    "busy_inner_seconds": command["busy_inner_seconds"],
                    "busy_inner_status": command["busy_inner_status"],
                    "busy_reads": command["busy_reads"], "wall_ms": command["wall_ms"],
                    "cycle_seconds_80mhz": command["cycle_seconds"],
                    "host_gap_before_ms": gaps[index]["milliseconds"],
                    "busy_inner_conditional_vi_point_count": len(command["busy_inner_points"]),
                    "busy_inner_common_coverage_seconds":
                    telemetry["common_coverage_seconds"] if telemetry else None,
                    "busy_inner_covered_telemetry_mean_w":
                    telemetry["total_covered_mean_w"] if telemetry else None})


def plot_rail_points(metadata: dict, records: list[dict], windows: list[dict], path: Path) -> None:
    """Show every discrete V×I/POUT point on the full measured QPC time axis."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    origin = metadata["sampling_started_ticks"]
    frequency = metadata["qpc_frequency"]
    grouped = {address: {"vi": ([], []), "pout": ([], [])}
               for address, _, _ in RAILS}
    for point in records:
        if point.get("record") != "rail_point":
            continue
        row = grouped[point["address"]]
        midpoint = (point["vi_before_ticks"] + point["vi_after_ticks"]) / 2
        row["vi"][0].append((midpoint - origin) / frequency / 60)
        row["vi"][1].append(point["vi_w"])
        if point["read_pout"] is not None:
            p = point["read_pout"]
            row["pout"][0].append(((p["before_ticks"] + p["after_ticks"]) / 2
                                   - origin) / frequency / 60)
            row["pout"][1].append(point["pout_w"])
    figure, axes = plt.subplots(7, 1, figsize=(13, 15), sharex=True)
    shades = {"idle": "#bdbdbd", "attention_repeat": "#8ecae6",
              "mlp_repeat": "#ffb084", "full_kv128_step": "#a8ddb5"}
    for axis, (address, name, regulator) in zip(axes, RAILS):
        for window in windows:
            axis.axvspan((window["start_ticks"] - origin) / frequency / 60,
                         (window["end_ticks"] - origin) / frequency / 60,
                         color=shades[window["kind"]], alpha=.2, lw=0)
        xs, ys = grouped[address]["vi"]
        axis.scatter(xs, ys, s=2.5, marker=".", color="#13293d", linewidths=0,
                     label="raw V×I points")
        if regulator == "MAX20751":
            px, py = grouped[address]["pout"]
            axis.scatter(px, py, s=4, marker="x", color="#bd271e", linewidths=.4,
                         label="raw READ_POUT")
        axis.set_ylabel(f"{name}\nW", fontsize=8)
        axis.grid(axis="y", alpha=.15)
        axis.legend(loc="upper right", fontsize=7, frameon=False)
    axes[-1].set_xlabel("Minutes since seven-rail sampling start (QPC)")
    title = (f"All seven rails: discrete PMBus readings across {len(windows)} repeat windows"
             if windows else "All seven rails: discrete PMBus readings during the read-only smoke")
    figure.suptitle(title)
    if windows:
        figure.legend(handles=[Patch(facecolor=shades[kind], label={
            "idle": "Idle", "attention_repeat": "Attention repeat",
            "mlp_repeat": "MLP repeat", "full_kv128_step": "Full KV128 step"}[kind])
            for kind in KINDS], loc="lower center", ncol=4,
            bbox_to_anchor=(.5, .015), fontsize=8, frameon=False)
    figure.text(.5, .006, "Discrete readings; no smoothing; sensor aperture/lag unknown.",
                ha="center", fontsize=8)
    figure.tight_layout(rect=(0, .04 if windows else .015, 1, .98))
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--jsonl", type=Path, required=True)
    parser.add_argument("--windows", type=Path, required=True)
    parser.add_argument("--commands", type=Path, required=True)
    parser.add_argument("--target-period-ms", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--figure", type=Path)
    parser.add_argument("--rail-figure", type=Path)
    parser.add_argument("--raw-csv", type=Path)
    parser.add_argument("--window-csv", type=Path)
    parser.add_argument("--busy-points-csv", type=Path)
    parser.add_argument("--busy-by-opcode-layer-csv", type=Path)
    parser.add_argument("--command-csv", type=Path)
    args = parser.parse_args()
    outputs = [path for path in (args.output, args.figure, args.rail_figure,
                                 args.raw_csv, args.window_csv, args.busy_points_csv,
                                 args.busy_by_opcode_layer_csv,
                                 args.command_csv) if path is not None]
    require(len({path.resolve() for path in outputs}) == len(outputs)
            and all(path.parent.is_dir() and not path.exists() for path in outputs),
            "Output paths must be distinct new files in existing directories")
    metadata = json.loads(args.metadata.read_text(encoding="utf-8-sig"))
    with args.jsonl.open(encoding="utf-8-sig") as stream:
        records = [json.loads(line) for line in stream if line.strip()]
    with args.windows.open(encoding="utf-8-sig") as stream:
        windows = [json.loads(line) for line in stream if line.strip()]
    with args.commands.open(encoding="utf-8-sig") as stream:
        commands = [json.loads(line) for line in stream if line.strip()]
    result = analyze_windows(metadata, records, windows, args.target_period_ms, commands)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    if args.figure:
        plot(result, args.figure)
    if args.rail_figure:
        plot_rail_points(metadata, records, windows, args.rail_figure)
    if args.raw_csv:
        export_raw_csv(records, windows, args.raw_csv)
    if args.window_csv:
        export_window_csv(result, args.window_csv)
    if args.busy_points_csv:
        export_busy_points_csv(result, args.busy_points_csv)
    if args.busy_by_opcode_layer_csv:
        export_busy_by_opcode_layer_csv(result, args.busy_by_opcode_layer_csv)
    if args.command_csv:
        export_command_csv(result, args.command_csv)
    print(json.dumps({"status": result["status"], "output": str(args.output),
                      "figure": str(args.figure) if args.figure else None,
                      "rail_figure": str(args.rail_figure) if args.rail_figure else None}))


if __name__ == "__main__":
    main()
