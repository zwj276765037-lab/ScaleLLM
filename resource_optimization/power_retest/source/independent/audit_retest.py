#!/usr/bin/env python3
"""Independently decode and integrate sealed local seven-rail evidence.

Only the Python standard library is used. This program has no hardware access
and imports no workload, sampler, or engineering analysis implementation.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics
import struct
import sys


RAILS = ("0x70", "0x11", "0x12", "0x15", "0x14", "0x72", "0x73")
VID_RAILS = {"0x70", "0x72", "0x73"}
KINDS = ("idle", "attention_repeat", "mlp_repeat", "full_kv128_step")
SCHEDULE = (
    ("idle", "attention_repeat", "mlp_repeat", "full_kv128_step"),
    ("idle", "mlp_repeat", "full_kv128_step", "attention_repeat"),
    ("idle", "full_kv128_step", "attention_repeat", "mlp_repeat"),
)
COMMANDS = {
    "VOUT_MODE": (0x20, 1), "IOUT_CAL_GAIN": (0x38, 2),
    "IOUT_CAL_OFFSET": (0x39, 2), "READ_VOUT": (0x8B, 2),
    "READ_IOUT": (0x8C, 2), "READ_POUT": (0x96, 2),
}
NEW_BIT = "5d78519aa10695be564f668d5a41a0e5554e282c31d39f648534a7dc01ab72f7"
OLD_BIT = "96df1a5c1bf4174921bc02ccd88df4066dece3d62b491acb3106bb90ac0ffc85"
SNAPSHOT_SHA = "fa610d68fab6045573a355313f78808c93b7273dbf1edc2e8f61bc3ea1ad81c8"
REQUESTS_SHA = "7f70c6229bff557383ee9e9b619839bc379dff2dec088d583490a911130c6680"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def near(actual, expected, message):
    require(actual is not None and math.isclose(actual, expected, abs_tol=1e-12,
                                               rel_tol=1e-12), message)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def records(path):
    with path.open(encoding="utf-8-sig") as stream:
        for number, line in enumerate(stream, 1):
            require(bool(line.strip()), f"Empty raw record {path}:{number}")
            yield json.loads(line)


def digest(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def describe(values):
    if not values:
        return dict(count=0, min=None, mean=None, median=None, p95=None, max=None)
    ordered = sorted(values)
    return dict(count=len(values), min=ordered[0], mean=statistics.fmean(ordered), median=statistics.median(ordered),
                p95=ordered[math.ceil(.95 * len(ordered)) - 1], max=ordered[-1])


def linear11(word):
    exponent = word >> 11
    mantissa = word & 0x7FF
    if exponent & 16:
        exponent -= 32
    if mantissa & 1024:
        mantissa -= 2048
    return math.ldexp(mantissa, exponent), exponent


def check_read(read, frequency, run_id, strict=True):
    code, size = COMMANDS[read["command"]]
    raw = bytes.fromhex(read["raw_hex"])
    require(read["command_code"] == code and read["expected_bytes"] == size
            and len(raw) == size and int.from_bytes(raw, "little") == read["word_le"],
            f"Read raw/command mismatch {read}")
    require(read["api_status"] == "returned" and read["error"] is None
            and read["fresh_hardware_read"] is True, "API/fresh read failure")
    require(read["before_ticks"] < read["after_ticks"], "Nonpositive read envelope")
    if strict:
        require(read["byte_count"] == size and read["qpc_frequency"] == frequency
                and read["run_id"] == run_id
                and read["native_ack_status"] == "NOT_EXPOSED_BY_OFFICIAL_API",
                "Read clock/run/length/native-status mismatch")
    return read["word_le"]


def decode_point(point, modes, frequency, run_id, strict=True):
    address = point["address"]
    require(address in RAILS and point["mode_word"] == modes[address], "Point mode mismatch")
    voltage_read, current_read, power_read = (point[k] for k in
                                            ("read_vout", "read_iout", "read_pout"))
    voltage_word = check_read(voltage_read, frequency, run_id, strict)
    current, current_exp = linear11(check_read(current_read, frequency, run_id, strict))
    require(voltage_read["after_ticks"] <= current_read["before_ticks"], "V/I read overlap")
    power = None
    if address in VID_RAILS:
        require(modes[address] == 0x20 and 1 <= voltage_word <= 255
                and current_exp == -1, "MAX20751 mode/VID/IOUT exponent mismatch")
        voltage = .25 + (voltage_word - 1) / 200
        power, power_exp = linear11(check_read(power_read, frequency, run_id, strict))
        require(power_exp == 1 and current_read["after_ticks"] <= power_read["before_ticks"],
                "MAX20751 POUT exponent/order mismatch")
        near(point["pout_w"], power, "POUT decoded value mismatch")
        end_ticks = power_read["after_ticks"]
    else:
        require(modes[address] == 0x14, "MAX15301 VOUT mode mismatch")
        voltage = voltage_word / 4096
        require(power_read is None and point["pout_w"] is None
                and point["pout_status"] == "NOT_SUPPORTED_BY_DOCUMENTED_COMMAND_SET",
                "Unsupported MAX15301 POUT must remain null")
        end_ticks = current_read["after_ticks"]
    near(point["voltage_v"], voltage, "Decoded VOUT differs")
    near(point["current_a"], current, "Decoded signed IOUT differs")
    near(point["vi_w"], voltage * current, "Decoded VxI differs")
    require(point["vi_before_ticks"] == voltage_read["before_ticks"]
            and point["vi_after_ticks"] == current_read["after_ticks"]
            and point["point_after_ticks"] == end_ticks
            and point["physical_aperture_contained_busy"] is None
            and point["sensor_aperture_and_lag"] == "UNKNOWN", "Point envelope/aperture differs")
    return voltage * current, current, power


def telemetry(run, gap_ms=None, strict=True):
    meta = read_json(run / "telemetry.json")
    frequency, run_id = meta["qpc_frequency"], meta["run_id"]
    require(frequency > 0 and meta["status"] == "COMPLETE" and meta["pass"] is True
            and meta["read_errors"] == 0 and meta["read_only"] is True
            and meta["writes"] is False and meta["address_scan"] is False
            and meta["sensor_aperture_and_lag"] == "UNKNOWN", "Telemetry metadata invalid")
    validation = meta["qpc_validation"]
    require(validation["native_before_ticks"] - 2 <= validation["stopwatch_ticks"]
            <= validation["native_after_ticks"] + 2, "Native/Stopwatch QPC mismatch")
    gap_ticks = math.inf if gap_ms is None else gap_ms * frequency / 1000
    modes, pending, types = {}, {}, Counter()
    series = {rail: [] for rail in RAILS}
    points = {rail: [] for rail in RAILS}
    negative, code_counts = Counter(), defaultdict(Counter)
    starts, durations, latency = [], [], defaultdict(list)
    last_id, last_end, point_count, sweep_count, long_vi, late = 0, 0, 0, 0, 0, 0
    for item in meta["configuration"]:
        modes[item["address"]] = check_read(item["read"], frequency, run_id, strict)
    require(set(modes) == set(RAILS), "Seven rail configurations required")
    for item in records(run / "telemetry.jsonl"):
        kind = item["record"]
        types[kind] += 1
        if kind == "bus_read":
            check_read(item, frequency, run_id)
            require(item["read_id"] == last_id + 1 and item["address"] in RAILS
                    and last_end <= item["before_ticks"], "Read reuse/nonmonotonic bus trace")
            last_id = item["read_id"]
            last_end = item["after_ticks"]
            pending[last_id] = item
            latency[(item["address"], item["command"])].append(
                (item["after_ticks"] - item["before_ticks"]) * 1000 / frequency)
        elif kind in ("configuration", "calibration"):
            continue
        elif kind == "rail_point":
            sweep, position, address = item["sweep"], item["position"], item["address"]
            require(sweep == point_count // 7 and position == point_count % 7
                    and address == RAILS[(sweep + position) % 7], "Rail rotation/order mismatch")
            if strict:
                require(item["run_id"] == run_id, "Point run mismatch")
            value, current, power = decode_point(item, modes, frequency, run_id, strict)
            for field in ("read_vout", "read_iout", "read_pout"):
                read = item[field]
                if read is None:
                    continue
                code_counts[(address, read["command"])][read["word_le"]] += 1
                if strict:
                    require(pending.pop(read["read_id"], None) == read
                            and item[field + "_id"] == read["read_id"], "Point immediate-read reference differs")
            before, after = item["vi_before_ticks"], item["vi_after_ticks"]
            valid_value = value if after - before <= gap_ticks else None
            long_vi += valid_value is None
            series[address].append(((before + after) / 2, valid_value))
            points[address].append((before, after, value, item["name"], item["point_after_ticks"]))
            negative[address] += current < 0
            point_count += 1
            if not strict and position == 0:
                starts.append(before)
            if not strict and position == 6:
                durations.append((item["point_after_ticks"] - starts[-1]) / frequency)
        elif kind == "sweep":
            require(item["sweep"] == sweep_count and point_count == 7 * (sweep_count + 1)
                    and item["complete_rail_points"] == 7
                    and item["rail_order"] == list(RAILS[sweep_count % 7:] + RAILS[:sweep_count % 7]),
                    "Sweep count/order differs")
            sweep_count += 1
            starts.append(item["start_ticks"])
            durations.append((item["end_ticks"] - item["start_ticks"]) / frequency)
            late += meta.get("target_period_ms", 0) > 0 and item["late_ticks"] > .002 * frequency
        else:
            raise ValueError(f"Unrecognized raw record {kind}")
    require(point_count == meta["complete_rail_points"] == 7 * meta["complete_sweeps"],
            "Telemetry count mismatch")
    if strict:
        require(sweep_count == meta["complete_sweeps"] and late == meta["missed_deadlines"],
                "Sweep/deadline metadata mismatch")
        for configuration in meta["configuration"]:
            require({read["command"] for read in configuration["calibration"]}
                    == {"IOUT_CAL_GAIN", "IOUT_CAL_OFFSET"}, "Read-only calibration fields incomplete")
            for read in [configuration["read"], *configuration["calibration"]]:
                require(pending.pop(read["read_id"], None) == read, "Configuration raw mismatch")
        require(not pending, "Unreferenced raw bus reads")
    for values in series.values():
        require(all(a[0] < b[0] for a, b in zip(values, values[1:])), "Rail points not monotonic")
    intervals = [(b - a) / frequency for a, b in zip(starts, starts[1:])]
    report = dict(raw_types=dict(types), invalid_long_vi=long_vi,
                  negative_current_points={r: n for r, n in negative.items() if n},
                  sweep_intervals_seconds=describe(intervals), sweep_durations_seconds=describe(durations),
                  missed_deadlines=late,
                  read_latency_ms={f"{r}/{c}": describe(v) for (r, c), v in latency.items()},
                  raw_code_counts={f"{r}/{c}": dict(sorted(v.items())) for (r, c), v in code_counts.items()})
    return meta, series, points, report


def integrate(series, begin, end, frequency, gap_ticks):
    """Partition the whole-run support at every rail breakpoint, then clip W."""
    times = {rail: [point[0] for point in series[rail]] for rail in RAILS}
    cuts = {begin, end}
    for rail in RAILS:
        cuts.update(times[rail][bisect_right(times[rail], begin):bisect_left(times[rail], end)])
    cuts = sorted(cuts)
    covered = 0
    energy, held = dict.fromkeys(RAILS, 0.0), dict.fromkeys(RAILS, 0.0)
    missing = []
    for left, right in zip(cuts, cuts[1:]):
        midpoint = (left + right) / 2
        support = {}
        for rail in RAILS:
            index = bisect_right(times[rail], midpoint) - 1
            if not 0 <= index < len(series[rail]) - 1:
                break
            earlier, later = series[rail][index:index + 2]
            if later[0] - earlier[0] > gap_ticks or earlier[1] is None or later[1] is None:
                break
            support[rail] = earlier, later
        if len(support) != 7:
            if missing and missing[-1][1] == left:
                missing[-1][1] = right
            else:
                missing.append([left, right])
            continue
        covered += right - left
        seconds = (right - left) / frequency
        for rail, (earlier, later) in support.items():
            gradient = (later[1] - earlier[1]) / (later[0] - earlier[0])
            first = earlier[1] + gradient * (left - earlier[0])
            last = earlier[1] + gradient * (right - earlier[0])
            energy[rail] += seconds * (first + last) / 2
            held[rail] += seconds * earlier[1]
    require(covered > 0, "Window has no common seven-rail support")
    seconds = covered / frequency
    total = sum(energy.values()) / seconds
    return dict(coverage=covered / (end - begin), covered_seconds=seconds,
                missing_seconds=(end - begin - covered) / frequency, missing_intervals=missing,
                common_coverage_interval_count=1 + len(missing) - bool(missing and missing[0][0] == begin)
                - bool(missing and missing[-1][1] == end),
                rail_means={rail: energy[rail] / seconds for rail in RAILS},
                rail_zoh_means={rail: held[rail] / seconds for rail in RAILS},
                rail_telemetry_integrals_j=energy, total_mean=total,
                zoh_mean=sum(held.values()) / seconds,
                full_mean=total if end - begin - covered <= 2 else None)


def verify_commands(run, meta, windows, prefix_limit=None):
    summaries = list(records(run / "workload/commands_summary.jsonl"))
    traces = []
    for item in records(run / "commands.jsonl"):
        if item["record"] == "clock":
            require(all(item[key] == meta[key] for key in ("run_id", "qpc_frequency", "host", "boot_utc")),
                    "Command/sampler clock domain differs")
        else:
            require(item["record"] == "command", "Unexpected command record")
            traces.append(item)
    if prefix_limit is not None:
        require(len(traces) >= prefix_limit and len(summaries) >= prefix_limit,
                "Qualification prefix incomplete in received files")
        traces, summaries = traces[:prefix_limit], summaries[:prefix_limit]
    require(len(traces) == len(summaries) > 0, "Command/summary count mismatch")
    previous_ack, previous_id, previous_generation = 0, None, None
    signature, groups, outside, unseen = {}, [[] for _ in windows], [], []
    for command, summary in zip(traces, summaries):
        descriptor, words = command["descriptor"], command["descriptor_words"]
        command_id = descriptor["command_id"]
        require(previous_id is None or command_id == previous_id + 1, "Command IDs discontinuous")
        require(previous_generation is None or words[7] == previous_generation + 1,
                "Buffer generation discontinuous")
        previous_id, previous_generation = command_id, words[7]
        require(words[2] == command_id == summary["command_id"] and words[3] == 127
                and words[4] == descriptor["opcode"] == summary["opcode"]
                and words[5] == descriptor["layer"] == summary["layer"]
                and words[6] == descriptor["active_mask"] == summary["active_mask"] == 0xFFFF
                and words[32:] == [127, 1] * 16, "Descriptor/request identity differs")
        require(hashlib.sha256(struct.pack("<64I", *words)).hexdigest()
                == command["descriptor_sha256"] == summary["descriptor_sha256"], "Descriptor SHA mismatch")
        require(command["trace_state"] == "ACK_WRITTEN" and command["first_error_status"] is None
                and command["core_hz"] == 80_000_000, "Command completion/core failure")
        cycles = command["done_cycles_read"]["value"]
        output_bytes = 196608 if descriptor["opcode"] == 1 else 917504
        require(0 < cycles < 0xFFFFFFFF and cycles == summary["cycles"], "DONE cycles differ")
        completion = {read["register"]: read["value"] for read in command["completion_reads"]}
        require(completion == dict(ADMISSION_ERROR=0, DONE_ERROR=0, DONE_INPUT_BYTES=196608,
                                   DONE_OUTPUT_BYTES=output_bytes), "DONE errors/byte counts differ")
        require(command["input_transfer"]["bytes"] == 196608
                and command["output_transfer"]["bytes"] == summary["output_bytes"] == output_bytes,
                "DMA byte counts differ")
        observations = command["status_observations"]
        busy = [read for read in observations if read["value"] == 1]
        done = [read for read in observations if read["value"] == 2]
        require(done and command["status_reads"] == len(observations)
                and command["busy_reads"] == len(busy)
                and command["first_busy"] == (busy[0] if busy else None)
                and command["last_busy"] == (busy[-1] if busy else None)
                and command["first_done"] == done[0], "BUSY/DONE summary differs")
        require(all(read["before_ticks"] < read["after_ticks"] for read in observations)
                and all(a["after_ticks"] <= b["before_ticks"] for a, b in zip(observations, observations[1:])),
                "STATUS observations overlap")
        require(previous_ack < command["start_write"]["before_ticks"]
                < command["start_write"]["after_ticks"] <= observations[0]["before_ticks"]
                < done[0]["after_ticks"] <= command["output_transfer"]["before_ticks"]
                < command["output_transfer"]["after_ticks"] <= command["ack_write"]["before_ticks"]
                < command["ack_write"]["after_ticks"], "START/DONE/output/ACK chronology differs")
        previous_ack = command["ack_write"]["after_ticks"]
        if not busy:
            unseen.append(command_id)
        key = descriptor["opcode"], descriptor["layer"]
        pair = summary["input_sha256"], summary["output_sha256"]
        require(key not in signature or signature[key] == pair, "Repeated numerical input/output differs")
        signature[key] = pair
        matches = [index for index, window in enumerate(windows)
                   if window["start_ticks"] <= command["start_write"]["before_ticks"]
                   and command["ack_write"]["after_ticks"] <= window["end_ticks"]]
        require(len(matches) <= 1, "Command belongs to overlapping formal windows")
        if matches:
            groups[matches[0]].append(command)
        else:
            outside.append(command)
    require([(c["descriptor"]["layer"], c["descriptor"]["opcode"]) for c in traces[:64]]
            == [(layer, opcode) for layer in range(32) for opcode in (1, 2)],
            "Initial complete qualification layer order differs")
    return groups, outside, unseen, signature, len(traces)


def audit_pilot(run, expected_bit=None):
    meta = read_json(run / "telemetry.json")
    _, _, _, raw = telemetry(run, strict="target_period_ms" in meta)
    nearest_rank_p95 = raw["sweep_intervals_seconds"]["p95"]
    period = math.ceil(max(.100, 1.25 * nearest_rank_p95) * 100 - 1e-12) * 10
    require(meta["max_seconds"] == 60 and meta["sampling_seconds"] >= 60,
            "Pilot duration differs from 60-second design")
    require(period <= 1000, "Pilot-derived D exceeds one second")
    result = dict(status="PASS", scope="Pilot raw decoding and cadence rule", run_id=meta["run_id"],
                  evidence_root=str(run.resolve()), derived_period_ms=period, gap_ms=3 * period,
                  sampling_seconds=meta["sampling_seconds"], **raw,
                  raw_sha256={name: digest(run / name) for name in ("telemetry.json", "telemetry.jsonl")})
    receipt_path = run / "receipt.json"
    if receipt_path.exists():
        receipt = read_json(receipt_path)
        require(receipt["child_exit_code"] == 0 and receipt["status"] == "COMPLETE"
                and receipt["run_id"] == meta["run_id"] and not receipt["survivors"],
                "Pilot native process receipt differs")
        if expected_bit:
            require(receipt["bit_sha256"] == expected_bit, "Pilot bit file identity differs")
        result.update(bit_sha256=receipt["bit_sha256"], sampler_native_exit=receipt["child_exit_code"],
                      lease_managed_externally=receipt.get("lease_managed_externally", False))
        result["raw_sha256"]["receipt.json"] = digest(receipt_path)
    return result


def audit_restore(run, snapshot, expected_bit):
    if snapshot is not None:
        require(snapshot.stat().st_size == 256 * 1024**2 and digest(snapshot) == SNAPSHOT_SHA,
                "Sealed local full snapshot unavailable/changed")
    inspection = read_json(run / "inspection.json")
    require(inspection["schema"] == "scalellm_dsp_frozen_kv_restore_v1"
            and inspection["status"] == "PASS_WITH_LIMITS" and inspection["read_only"] is False
            and inspection["bit_sha256"] == expected_bit and inspection["reference_bit_sha256"] == OLD_BIT
            and inspection["snapshot_sha256"] == inspection["full_snapshot_readback_sha256"] == SNAPSHOT_SHA
            and inspection["snapshot_bytes"] == 256 * 1024**2 and inspection["restored_layers"] == 32
            and inspection["full_snapshot_byteexact"] and inspection["handles_closed"]
            and inspection["independent_full_model_oracle"] == "NOT_ESTABLISHED",
            "New bit full-restore identity/completion differs")
    csr = inspection["csr"]
    require(csr == inspection["csr_before_restore"] and csr["MAGIC"] == 1397109046
            and csr["ABI"] == 65536 and csr["CORE_HZ"] == 80_000_000
            and all(csr[field] == 0 for field in ("STATUS", "ACK_ID", "ADMISSION_ERROR", "DONE_ERROR")),
            "New programmed quiescent CSR identity differs")
    transfers = list(records(run / "xdma.jsonl"))
    require(transfers[0]["operation"] == "open" and transfers[-1]["operation"] == "close",
            "Restore transfer handles not closed")
    chunks = defaultdict(dict)
    for ordinal, item in enumerate(transfers):
        if item.get("node") == "user":
            require(item["operation"] == "read", "Restore contains unexpected CSR write")
        elif item.get("node") in ("h2c_0", "c2h_0"):
            node = item["node"]
            require(item["operation"] == ("write" if node == "h2c_0" else "read")
                    and item["completed"] == item["size"] == 1024**2,
                    "Restore chunk operation/length differs")
            offset = item["offset"] - 0x60000000
            require(0 <= offset < 256 * 1024**2 and offset % 1024**2 == 0
                    and node not in chunks[offset], "Restore chunk offset/reuse differs")
            chunks[offset][node] = (ordinal, item["sha256"])
    require(sorted(chunks) == list(range(0, 256 * 1024**2, 1024**2)), "Restore address coverage incomplete")
    for pair in chunks.values():
        require(set(pair) == {"h2c_0", "c2h_0"} and pair["h2c_0"][1] == pair["c2h_0"][1]
                and pair["h2c_0"][0] < pair["c2h_0"][0], "Actual restore/write-readback chunk log differs")
    layer_hashes = []
    if snapshot is not None:
        with snapshot.open("rb") as stream:
            for layer in range(32):
                data = stream.read(8 * 1024**2)
                layer_hashes.append(hashlib.sha256(data).hexdigest())
                for chunk_index in range(8):
                    offset = (8 * layer + chunk_index) * 1024**2
                    expected = hashlib.sha256(data[chunk_index * 1024**2:(chunk_index + 1) * 1024**2]).hexdigest()
                    require(chunks[offset]["h2c_0"][1] == expected,
                            "Actual full restore/write-readback chunk differs from sealed snapshot")
    else:
        layer_hashes = [item["sha256"] for item in inspection["layers"]]
    require(len(inspection["layers"]) == 32, "Per-layer restore records incomplete")
    for layer, item in enumerate(inspection["layers"]):
        require(item["layer"] == layer and item["byte_exact"]
                and item["read_bytes"] == item["write_bytes"] == 8 * 1024**2
                and item["sha256"] == layer_hashes[layer], "Per-layer restore digest/length differs")
    process_path = run.parent / "environment/restore_process_receipt.json"
    process = read_json(process_path)
    require(process["exitcode"] == 0 and process["phase"] == "restore", "Restore native process exit differs")
    limitations = ["Historical provenance for 27 layers lacks an independent oracle"]
    if snapshot is None:
        limitations.append("Private snapshot bytes unavailable for rehash; aggregate/layer source digests are inspection claims")
    return dict(status="PARTIAL_WITH_LIMITS", source_and_restore_checks="PASS" if snapshot else "PASS_WITH_LIMITS",
                evidence_root=str(run.resolve()), private_snapshot_bytes_rehashed=snapshot is not None,
                verification_scope="Actual write/readback log pairing, addresses, byte lengths, and frozen identity",
                snapshot_chunk_digests_compared_to_private_bytes=snapshot is not None,
                aggregate_snapshot_digest_independently_established=snapshot is not None,
                bit_sha256=expected_bit, reference_bit_sha256=OLD_BIT, snapshot_sha256=SNAPSHOT_SHA,
                native_exit=process["exitcode"], layers_restored_and_readback=32,
                total_write_bytes=256 * 1024**2, total_read_bytes=256 * 1024**2,
                actual_write_readback_chunk_pairs=len(chunks), layer_sha256=layer_hashes,
                independent_full_model_oracle="NOT_ESTABLISHED",
                limitations=limitations,
                raw_sha256={"inspection.json": digest(run / "inspection.json"), "xdma.jsonl": digest(run / "xdma.jsonl"),
                            "restore_process_receipt.json": digest(process_path)})


def check_original_references(reference, signatures, work, snapshot):
    source = read_json(reference / "payloads/capture_source.json")
    receipt = read_json(reference / "receipt.json")
    original = read_json(reference / "device/run.json")
    require(receipt["bit_sha256"] == source["release_bit_sha256"] == OLD_BIT
            and receipt["state"] == "CAPTURE_COMPLETE" and receipt["lease_released"] and not receipt["survivors"],
            "Original numerical reference lifecycle/bit identity differs")
    require(original["execution"] == "COMPLETE" and len(original["steps"]) == 128
            and len(original["receipts"]) == 8192 and original["handles_closed"] and original["final_quiescent"]
            and original["checkpoint_sha256"] == source["checkpoint_sha256"], "Original complete run differs")
    requests = reference.parent.parent / "requests16_fixed128.json"
    require(digest(requests) == source["benchmark_requests_sha256"] == REQUESTS_SHA,
            "Original fixed 16-request hash differs")
    require(digest(reference / "device/run.json") == work["source_main_run_sha256"]
            and original["steps"][127]["emitted"] == work["qualification"]["emitted"],
            "New run source/16-token reference differs")
    host_hashes = {
        "host_state_before_sha256": hashlib.sha256(json.dumps(original["steps"][126]["slots"], sort_keys=True,
                                                               separators=(",", ":")).encode()).hexdigest(),
        "host_state_after_sha256": hashlib.sha256(json.dumps(original["steps"][127]["slots"], sort_keys=True,
                                                              separators=(",", ":")).encode()).hexdigest(),
    }
    if "host_state_before_sha256" in work["qualification"]:
        require(all(work["qualification"][key] == value for key, value in host_hashes.items()),
                "Qualification host checkpoint/commit differs from original state")
    entries = list(records(reference / "payloads/capture.jsonl"))
    before = {item["command_id"]: item for item in entries if item["record"] == "before_command"}
    after = {item["command_id"]: item for item in entries if item["record"] == "after_command"}
    checks = []
    for layer, opcode in [(layer, 1) for layer in (0, 8, 16, 24, 31)] + [(0, 2)]:
        command_id = 8129 + 2 * layer if opcode == 1 else 8130
        captured = before[command_id]
        require((captured["layer"], captured["opcode"], captured["round"]) == (layer, opcode, 128),
                "Captured workload identity differs")
        hashes, files = {}, {}
        for name, entry in dict(captured["files"], output=after[command_id]["output"]).items():
            path = reference / "payloads" / entry["file"]
            require(path.parent == reference / "payloads" and path.stat().st_size == entry["bytes"]
                    and digest(path) == entry["sha256"], "Original full captured bytes/SHA differ")
            hashes[name], files[name] = entry["sha256"], path
        require(signatures[opcode, layer] == (hashes["input"], hashes["output"]),
                "New full numerical input/output differs from sealed original capture")
        words = struct.unpack("<64I", files["descriptor"].read_bytes())
        require(words[2:8] == (command_id, 127, opcode, layer, 65535, command_id)
                and words[32:] == tuple([127, 1] * 16), "Original capture descriptor differs")
        history = None
        if opcode == 1 and snapshot:
            kv = files["kv_before"].read_bytes()
            with snapshot.open("rb") as stream:
                stream.seek(layer * 8 * 1024**2)
                restored = stream.read(8 * 1024**2)
            history = all(kv[slot * 512 * 1024:slot * 512 * 1024 + 127 * 4096]
                          == restored[slot * 512 * 1024:slot * 512 * 1024 + 127 * 4096] for slot in range(16))
            require(history, "Sealed snapshot five-layer history differs from original captured bytes")
        checks.append(dict(layer=layer, opcode=opcode, command_id=command_id,
                           captured_files_sha256=hashes, history_byteexact=history))
    return dict(status="PASS", evidence_root=str(reference.resolve()), six_original_captures=checks,
                fixed_requests_sha256=REQUESTS_SHA, source_run_sha256=work["source_main_run_sha256"],
                original_host_state_sha256=host_hashes)


def compare_engineering(path, independent):
    engineering = read_json(path)
    require(engineering["strict_physical_active_mean_w"] is None, "Engineering strict physical mean must be null")
    require(engineering["target_sweep_period_ms"] == independent["frozen_period_ms"]
            and engineering["maximum_interpolated_gap_ms"] == independent["gap_ms"],
            "Engineering frozen period/gap differs from independent contract")
    differences = []
    maximum = 0.0
    field_map = {"duration": "window_seconds", "coverage": "common_coverage_fraction",
                 "covered_seconds": "common_coverage_seconds", "missing_seconds": "common_missing_seconds",
                 "common_coverage_interval_count": "common_coverage_interval_count",
                 "total_mean": "total_covered_mean_w", "full_mean": "total_full_window_mean_w",
                 "zoh_mean": "total_zoh_covered_mean_w"}

    def compare(actual, expected, location):
        nonlocal maximum
        if actual is None or expected is None:
            matches = actual is expected
        else:
            maximum = max(maximum, abs(actual - expected))
            matches = math.isclose(actual, expected, abs_tol=1e-10, rel_tol=0)
        if not matches:
            differences.append(dict(field=location, independent=actual, engineering=expected))

    require(len(engineering["windows"]) == len(independent["windows"]) == 12, "Engineering window count differs")
    for actual, expected in zip(independent["windows"], engineering["windows"]):
        require((actual["kind"], actual["repeat"]) == (expected["kind"], expected["repeat_id"]),
                "Engineering window identity differs")
        require(expected["strict_physical_active_mean_w"] is None, "Engineering window physical mean must be null")
        label = f"{actual['kind']}/{actual['repeat']}"
        for independent_key, engineering_key in field_map.items():
            compare(actual[independent_key], expected[engineering_key], f"{label}/{independent_key}")
        for rail in RAILS:
            compare(actual["rail_means"][rail], expected["rail_covered_mean_w"][rail], f"{label}/{rail}/mean")
            compare(actual["rail_zoh_means"][rail], expected["rail_zoh_covered_mean_w"][rail], f"{label}/{rail}/zoh")
            compare(actual["vi_envelope_counts"][rail], expected["rail_vi_point_count"][rail], f"{label}/{rail}/point_count")
        if actual["trimmed_10_seconds"] is not None:
            for independent_key, engineering_key in field_map.items():
                if independent_key == "duration":
                    continue
                compare(actual["trimmed_10_seconds"][independent_key], expected["trimmed_10s"][engineering_key],
                        f"{label}/trimmed/{independent_key}")
            for rail in RAILS:
                compare(actual["trimmed_10_seconds"]["rail_means"][rail],
                        expected["trimmed_10s"]["rail_covered_mean_w"][rail], f"{label}/trimmed/{rail}/mean")
                compare(actual["trimmed_10_seconds"]["rail_zoh_means"][rail],
                        expected["trimmed_10s"]["rail_zoh_covered_mean_w"][rail], f"{label}/trimmed/{rail}/zoh")
    compare(independent["command_count"], engineering["command_trace"]["trace_command_count"], "All command count")
    compare(independent["outside_formal_commands"], engineering["command_trace"]["outside_measured_windows"], "Outside command count")
    compare(independent["missed_deadlines"], engineering["missed_deadlines_gt_2ms"], "Missed deadlines")
    for actual, expected in zip(independent["windows"], engineering["command_trace"]["windows"]):
        compare(actual["commands"], expected["command_count"], "Window command count")
        compare(actual["cycles"] / 80_000_000, expected["fpga_cycle_seconds_80mhz"], "FPGA cycle seconds")
        compare(actual["busy_inner_seconds"], expected["busy_inner_seconds"], "BUSY inner seconds")
        compare(actual["busy_inner_commands_with_two_vi_points_each_rail"],
                expected["busy_inner_commands_with_two_vi_points_each_rail"], "Commands with two BUSY points on each rail")
        if actual["busy_inner_commands_with_two_vi_points_each_rail"] == 0:
            require(expected["busy_inner_covered_telemetry_mean_w"] is None,
                    "Engineering BUSY mean lacks required per-command support")
        require(actual["busy_inner_unavailable"] == expected["busy_inner_unavailable_command_ids"],
                "Engineering unavailable BUSY IDs differ")
        for rail in RAILS:
            compare(actual["conditional_vi_counts"][rail],
                    expected["busy_inner_conditional_vi_w_by_rail"][rail]["count"], "BUSY point count")
            for statistic, value in actual["conditional_vi_statistics"][rail].items():
                compare(value, expected["busy_inner_conditional_vi_w_by_rail"][rail][statistic], f"BUSY/{rail}/{statistic}")
    for kind in KINDS:
        members = [w for w in independent["windows"] if w["kind"] == kind]
        expected = engineering["repeat_differences"][kind]
        actual = independent["repeat_summary"][kind]
        for left, right in {"mean": "equal_repeat_covered_mean_w", "sd": "sample_sd_w", "range": "range_w",
                            "cv": "coefficient_of_variation", "pooled_mean": "pooled_by_common_coverage_mean_w"}.items():
            compare(actual[left], expected[right], f"Repeats/{kind}/{left}")
        for rail in RAILS:
            values = [member["rail_means"][rail] for member in members]
            expected_rail = expected["by_rail"][rail]
            for statistic, value in describe(values).items():
                compare(value, expected_rail["covered_mean_w"][statistic], f"Repeats/{kind}/{rail}/{statistic}")
            compare(statistics.stdev(values), expected_rail["sample_sd_w"], f"Repeats/{kind}/{rail}/sd")
            compare(max(values) - min(values), expected_rail["range_w"], f"Repeats/{kind}/{rail}/range")
            pooled = sum(w["rail_means"][rail] * w["covered_seconds"] for w in members) / sum(w["covered_seconds"] for w in members)
            compare(pooled, expected_rail["pooled_by_common_coverage_mean_w"], f"Repeats/{kind}/{rail}/pooled")
    return dict(status="PASS" if not differences else "FAIL", absolute_tolerance=1e-10,
                maximum_absolute_difference=maximum, differences=differences, sha256=digest(path),
                evidence_path=str(path.resolve()))


def compare_published_reference(path, signatures, work):
    document = read_json(path)
    reference = document.get("original_reference_comparison", document)
    require(reference["status"] == "PASS" and len(reference["six_original_captures"]) == 6
            and reference["source_run_sha256"] == work["source_main_run_sha256"]
            and reference["fixed_requests_sha256"] == REQUESTS_SHA, "Published reference identity differs")
    for capture in reference["six_original_captures"]:
        key = capture["opcode"], capture["layer"]
        hashes = capture["captured_files_sha256"]
        require(signatures[key] == (hashes["input"], hashes["output"]),
                "New input/full output hash differs from published sealed reference identity")
    require(all(work["qualification"][key] == value for key, value in
                reference["original_host_state_sha256"].items()), "Host state differs from published reference identity")
    return dict(status="PASS", private_reference_bytes_reopened=False,
                verification_scope="New raw hashes versus published sealed reference identity record",
                evidence_path=str(path.resolve()), sha256=digest(path))


def audit_run(args):
    run = args.run.resolve()
    receipt, work = read_json(run / "receipt.json"), read_json(run / "workload/workload.json")
    windows = list(records(run / "workload/windows.jsonl"))
    period = receipt["target_sweep_period_ms"]
    require(0 < period <= 1000, "Frozen sampler period outside contract")
    meta, series, points, raw = telemetry(run, 3 * period)
    frequency, run_id = meta["qpc_frequency"], meta["run_id"]
    require(meta["target_period_ms"] == period, "Launcher/sampler frozen period differs")
    require(receipt["bit_sha256"] == args.expected_bit, "Runtime bit file identity differs")
    require(work["snapshot_sha256"] == SNAPSHOT_SHA and work["initial_full_kv_snapshot_byteexact"] is True,
            "Snapshot identity or initial full restore/readback differs")
    require(work["independent_full_model_oracle"] == "NOT_ESTABLISHED", "Historical oracle limit missing")
    require(work["status"] in ("COMPLETE", "COMPLETE_WITH_LIMITS") and work["completed_windows"] == 12
            and len(windows) == 12 and Counter(w["kind"] for w in windows) == dict.fromkeys(KINDS, 3),
            "Twelve formal windows incomplete")
    require([(w["kind"], w["repeat_id"]) for w in windows]
            == [(kind, block) for block, order in enumerate(SCHEDULE, 1) for kind in order],
            "Preregistered window order differs")
    require(all(a["end_ticks"] < b["start_ticks"] for a, b in zip(windows, windows[1:])),
            "Formal windows overlap")
    for item in [receipt, work, *windows]:
        require(all(item[key] == meta[key] for key in ("run_id", "qpc_frequency", "host", "boot_utc")),
                "Workload/sampler/launcher QPC identity differs")
    require(all(w["status"] == "COMPLETE" for w in windows), "Incomplete formal window")
    qualification = work["qualification"]
    require(qualification["completed_commands"] == 64 and qualification["all_32_layer_receipts"]
            and qualification["token_match"] and qualification["six_target_inputs_outputs_byteexact"]
            and qualification["kv_snapshot_restored_and_preserved"] and len(qualification["emitted"]) == 16,
            "Complete 32-layer/16-token/six-reference qualification differs")
    if args.expected_bit == NEW_BIT:
        require(all(key in qualification for key in ("host_state_before_sha256", "host_state_after_sha256")),
                "New qualification host-state evidence missing")
    local = work["local_position127_restore_qualification"]
    require([item["layer"] for item in local] == [0, 8, 16, 24, 31]
            and all(item["history_unchanged"] and item["local_equivalent_to_full_8mib"]
                    and item["output_byteexact"] for item in local), "Local KV restore qualification differs")
    groups, outside, unseen, signatures, command_count = verify_commands(run, meta, windows)
    point_starts = {rail: [point[0] for point in points[rail]] for rail in RAILS}
    results = []
    busy_unavailable = []
    for window, commands in zip(windows, groups):
        begin, end, kind = window["start_ticks"], window["end_ticks"], window["kind"]
        duration = (end - begin) / frequency
        shape = [(c["descriptor"]["layer"], c["descriptor"]["opcode"]) for c in commands]
        require(len(commands) == window["completed_commands"], "Window command count differs")
        if kind == "idle":
            require(not commands and duration >= 120, "Idle window shape/duration differs")
        elif kind == "attention_repeat":
            require(duration >= 120 and len(commands) > 0 and len(commands) % 5 == 0
                    and shape == [(layer, 1) for _ in range(len(commands) // 5) for layer in (0, 8, 16, 24, 31)],
                    "Attention window layer order/duration differs")
        elif kind == "mlp_repeat":
            require(duration >= 120 and len(commands) > 0 and shape == [(0, 2)] * len(commands),
                    "MLP window layer/duration differs")
        else:
            require(shape == [(layer, opcode) for layer in range(32) for opcode in (1, 2)]
                    and window["emitted"] == qualification["emitted"] and window["token_match"]
                    and window["six_target_inputs_outputs_byteexact"]
                    and window["kv_snapshot_restored_and_preserved"], "Full-step state/output differs")
            if args.expected_bit == NEW_BIT:
                require(all(window[key] == qualification[key] for key in
                            ("host_state_before_sha256", "host_state_after_sha256")),
                        "Repeated host checkpoint/commit differs from qualification")
        vi_counts = {rail: sum(begin <= point[0] and point[1] <= end for point in points[rail]) for rail in RAILS}
        vip_counts = {rail: sum(begin <= point[0] and point[4] <= end for point in points[rail]) for rail in RAILS}
        require(min(vip_counts.values()) >= 200 and all(vip_counts[r] == window["rail_vi_points"][points[r][0][3]]
                                                       for r in RAILS), "Complete rail point threshold/count differs")
        result = dict(kind=kind, repeat=window["repeat_id"], duration=duration, commands=len(commands),
                      min_rail_points=min(vi_counts.values()), vi_envelope_counts=vi_counts,
                      vip_envelope_counts=vip_counts, cycles=sum(c["done_cycles_read"]["value"] for c in commands),
                      busy_unobserved=[c["descriptor"]["command_id"] for c in commands if c["first_busy"] is None])
        result.update(integrate(series, begin, end, frequency, 3 * period * frequency / 1000))
        result["trimmed_10_seconds"] = integrate(series, begin + 10 * frequency, end - 10 * frequency,
                                                 frequency, 3 * period * frequency / 1000) if duration > 20 else None
        conditional = dict.fromkeys(RAILS, 0)
        conditional_values = {rail: [] for rail in RAILS}
        busy_seconds, unavailable, qualifying_busy = 0, [], 0
        for command in commands:
            busy = [o for o in command["status_observations"] if o["value"] == 1]
            if len(busy) < 2:
                unavailable.append(command["descriptor"]["command_id"])
                continue
            busy_begin, busy_end = busy[0]["after_ticks"] + 2, busy[-1]["before_ticks"] - 2
            if busy_end <= busy_begin:
                unavailable.append(command["descriptor"]["command_id"])
                continue
            busy_seconds += (busy_end - busy_begin) / frequency
            command_counts = dict.fromkeys(RAILS, 0)
            for rail in RAILS:
                bounds = point_starts[rail]
                index = bisect_left(bounds, busy_begin)
                while index < len(bounds) and bounds[index] <= busy_end:
                    if points[rail][index][1] <= busy_end:
                        command_counts[rail] += 1
                        conditional_values[rail].append(points[rail][index][2])
                    index += 1
                conditional[rail] += command_counts[rail]
            qualifying_busy += min(command_counts.values()) >= 2
        result.update(busy_inner_seconds=busy_seconds, busy_inner_unavailable=unavailable,
                      conditional_vi_counts=conditional,
                      conditional_vi_statistics={rail: describe(values) for rail, values in conditional_values.items()},
                      busy_inner_commands_with_two_vi_points_each_rail=qualifying_busy)
        busy_unavailable.extend(unavailable)
        results.append(result)
    repeats = {}
    for kind in KINDS:
        members = [result for result in results if result["kind"] == kind]
        values = [member["total_mean"] for member in members]
        mean = statistics.mean(values)
        repeats[kind] = dict(n=3, mean=mean, sd=statistics.stdev(values), min=min(values), max=max(values),
                             range=max(values) - min(values), cv=statistics.stdev(values) / abs(mean) if mean else None,
                             pooled_mean=sum(m["total_mean"] * m["covered_seconds"] for m in members)
                             / sum(m["covered_seconds"] for m in members))
    paired_deltas = [{"kind": r["kind"], "repeat": r["repeat"], "covered_mean_minus_block_idle_w":
                      r["total_mean"] - next(w["total_mean"] for w in results
                                             if w["kind"] == "idle" and w["repeat"] == r["repeat"])}
                     for r in results if r["kind"] != "idle"]
    limitations = ["Seven selected regulator outputs only", "Sensor aperture/lag and absolute accuracy unestablished",
                   "Historical KV for 27 layers has no independent full-model oracle"]
    if any(r["full_mean"] is None for r in results):
        limitations.append("At least one full-window mean unavailable because common coverage is incomplete")
    if busy_unavailable:
        limitations.append("At least one conservative BUSY inner interval unavailable")
    if receipt["sampler_exit_code"] is None:
        limitations.append("Sampler native exit code unknown")
    elif receipt["sampler_exit_code"] != 0:
        limitations.append("Sampler native exit code is nonzero and retained")
    if receipt["state"] not in ("COMPLETE", "PASS"):
        limitations.append("Original launcher state retained as " + receipt["state"])
    require(receipt["workload_exit_code"] == 0 and receipt["survivors"] == [],
            "Process cleanup/workload native exit failed")
    cleanup_state = "PASS"
    external_owner = receipt.get("lease_managed_externally", False)
    if external_owner:
        require(type(receipt["external_board_owner_pid"]) is int, "External lease owner identity missing")
        cleanup_state = "PENDING_EXTERNAL_OWNER_RELEASE"
        if args.owner_receipt:
            owner = read_json(args.owner_receipt)
            require(owner["owner_pid"] == receipt["external_board_owner_pid"] and owner["state"] == "CLOSED"
                    and owner["lease_released"] is True and owner["stop_reason"] is None
                    and owner["peak_owned_rss_bytes"] <= 8 * 1024**3
                    and owner["minimum_available_bytes"] >= 2 * 1024**3,
                    "External board owner final identity/cleanup/resources differ")
            cleanup_state = "PASS"
        else:
            limitations.append("External board owner final lease-release receipt pending")
    else:
        require(receipt["lease_released"] is True, "Board lease release not established")
    require(receipt["peak_tree_rss_bytes"] <= receipt["rss_limit_bytes"] <= 8 * 1024**3
            and receipt["minimum_available_bytes"] >= receipt["available_floor_bytes"] >= 2 * 1024**3
            and receipt["cpu_mask"] == 255, "Resource contract exceeded")
    launcher_process_path = run.parent / "environment/main_process_receipt.json"
    launcher_native_exit = None
    if launcher_process_path.exists():
        launcher_process = read_json(launcher_process_path)
        require(launcher_process["phase"] == "main", "Launcher phase process identity differs")
        launcher_native_exit = launcher_process["exitcode"]
        if launcher_native_exit != 0:
            limitations.append("Launcher native process exit is nonzero and retained")
    else:
        limitations.append("Launcher native process exit receipt unavailable in this evidence set")
    paths = [run / name for name in ("telemetry.json", "telemetry.jsonl", "commands.jsonl", "receipt.json",
                                     "workload/workload.json", "workload/windows.jsonl", "workload/commands_summary.jsonl")]
    result = dict(schema="scalellm_power_retest_independent_v1", status="PARTIAL_WITH_LIMITS",
                  numerical_and_command_checks="PASS", run_id=run_id, evidence_root=str(run),
                  bit_sha256=receipt["bit_sha256"], snapshot_sha256=work["snapshot_sha256"],
                  qpc_frequency=frequency, frozen_period_ms=period, gap_ms=3 * period,
                  resource_and_cleanup_checks=cleanup_state,
                  raw_wrapper_state=receipt["state"], workload_native_exit=receipt["workload_exit_code"],
                  sampler_native_exit=receipt["sampler_exit_code"], launcher_native_exit=launcher_native_exit,
                  native_process_checks="PASS" if receipt["sampler_exit_code"] == launcher_native_exit == 0 else "PARTIAL_WITH_LIMITS",
                  limitations=limitations,
                  command_count=command_count, outside_formal_commands=len(outside), busy_unobserved=unseen,
                  private_snapshot_bytes_rehashed=args.snapshot is not None,
                  original_private_capture_bytes_rehashed=args.reference_run is not None,
                  busy_inner_unavailable=busy_unavailable, windows=results, repeat_summary=repeats,
                  paired_idle_deltas=paired_deltas, strict_active_mean_w=None, physical_active_energy_j=None,
                  whole_board_input_mean_w=None, input_output_sha256={f"{op}/{layer}": pair for (op, layer), pair in signatures.items()},
                  raw_sha256={str(path.relative_to(run)): digest(path) for path in paths}, **raw)
    if args.snapshot is None:
        limitations.append("Private snapshot bytes were not reopened for this recomputation")
    if args.reference_run is None:
        limitations.append("Original private capture bytes were not reopened; numerical reference identity uses retained run evidence")
    if args.pilot:
        result["pilot"] = audit_pilot(args.pilot, args.expected_bit)
        require(result["pilot"]["derived_period_ms"] == period,
                "Frozen D differs from independently recomputed pilot rule")
    if args.owner_receipt:
        result["external_board_owner_receipt"] = dict(path=str(args.owner_receipt.resolve()),
                                                      sha256=digest(args.owner_receipt))
    if launcher_process_path.exists():
        result["launcher_native_process_receipt"] = dict(path=str(launcher_process_path.resolve()),
                                                         sha256=digest(launcher_process_path))
    normalization_path = run.parent / "environment/birth_normalization.json"
    if normalization_path.exists():
        result["process_creation_time_normalization"] = dict(
            evidence_path=str(normalization_path.resolve()), sha256=digest(normalization_path),
            records=read_json(normalization_path),
            initial_external_guardian_full_tree_coverage="NOT_ESTABLISHED_BEFORE_NORMALIZATION")
        limitations.append("External guardian process-tree recognition required recorded creation-time normalization")
    if args.source_dir:
        source_hashes = {
            "sampler_script_sha256": "kv128_sevenrail_sampler.ps1",
            "workload_script_sha256": "kv128_sevenrail_workload.py",
            "command_trace_script_sha256": "command_active_inference.py",
        }
        require(all(digest(args.source_dir / name) == receipt[field] for field, name in source_hashes.items()),
                "Local source differs from as-run receipt identity")
        result["as_run_source_sha256"] = {name: receipt[field] for field, name in source_hashes.items()}
    if args.restore:
        result["full_snapshot_restore"] = audit_restore(args.restore, args.snapshot, args.expected_bit)
        require(work["inspection_sha256"] == digest(args.restore / "inspection.json"),
                "Workload inspection identity differs from independently verified restore")
    if args.sensitivity_gap_ms is not None:
        require(args.sensitivity_gap_ms > 0, "Sensitivity gap must be positive")
        sensitivity_ticks = args.sensitivity_gap_ms * frequency / 1000
        sensitivity_series = {
            rail: [((point[0] + point[1]) / 2, point[2] if point[1] - point[0] <= sensitivity_ticks else None)
                   for point in points[rail]] for rail in RAILS
        }
        sensitivity = []
        for window, primary in zip(windows, results):
            alternative = integrate(sensitivity_series, window["start_ticks"], window["end_ticks"], frequency,
                                    sensitivity_ticks)
            sensitivity.append(dict(kind=window["kind"], repeat=window["repeat_id"], **alternative,
                                    covered_mean_minus_primary_w=alternative["total_mean"] - primary["total_mean"],
                                    coverage_minus_primary=alternative["coverage"] - primary["coverage"]))
        result["gap_sensitivity"] = dict(actual_frozen_period_ms=period, primary_gap_ms=3 * period,
                                          sensitivity_gap_ms=args.sensitivity_gap_ms,
                                          purpose="Separate gap-threshold sensitivity on the same actual-cadence raw evidence",
                                          windows=sensitivity)
    if args.snapshot:
        require(args.snapshot.stat().st_size == 256 * 1024**2 and digest(args.snapshot) == SNAPSHOT_SHA,
                "Local sealed snapshot size/SHA mismatch")
        result["snapshot_file"] = str(args.snapshot.resolve())
    if args.reference_run:
        result["original_reference_comparison"] = check_original_references(args.reference_run.resolve(), signatures,
                                                                            work, args.snapshot)
    if args.reference_manifest:
        result["published_reference_identity_comparison"] = compare_published_reference(args.reference_manifest,
                                                                                        signatures, work)
    if args.engineering_analysis:
        result["engineering_comparison"] = compare_engineering(args.engineering_analysis, result)
        if result["engineering_comparison"]["status"] == "FAIL":
            result["status"] = "FAIL"
    if args.baseline_audit:
        baseline = read_json(args.baseline_audit)
        differences = []
        fields = ("duration", "commands", "cycles", "coverage", "covered_seconds", "missing_seconds", "total_mean",
                  "zoh_mean", "full_mean", "busy_inner_seconds", "min_rail_points")
        for expected, actual in zip(baseline["windows"], results):
            require((expected["kind"], expected["repeat"]) == (actual["kind"], actual["repeat"]),
                    "Selfcheck baseline window identity differs")
            for field in fields:
                a, b = actual[field], expected[field]
                if (a is None or b is None) and a is not b:
                    differences.append(dict(kind=actual["kind"], repeat=actual["repeat"], field=field, actual=a, expected=b))
                elif a is not None and b is not None and not math.isclose(a, b, abs_tol=1e-10, rel_tol=0):
                    differences.append(dict(kind=actual["kind"], repeat=actual["repeat"], field=field, actual=a, expected=b))
            for field in ("rail_means", "conditional_vi_counts", "vi_envelope_counts", "vip_envelope_counts"):
                for rail in RAILS:
                    if not math.isclose(actual[field][rail], expected[field][rail], abs_tol=1e-10, rel_tol=0):
                        differences.append(dict(kind=actual["kind"], repeat=actual["repeat"], field=field, rail=rail))
        require(not differences, f"Independent historical selfcheck differences {differences}")
        result["historical_selfcheck"] = dict(status="PASS", absolute_tolerance=1e-10,
                                               baseline_sha256=digest(args.baseline_audit), differences=differences)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", "--run-dir", required=True, type=Path, help="Local native run directory")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--pilot-only", action="store_true", help="Audit --run as the 60-second pilot")
    mode.add_argument("--restore-only", action="store_true", help="Audit --run as the complete snapshot restore")
    parser.add_argument("--pilot", type=Path, help="Local 60-second pilot directory")
    parser.add_argument("--restore", type=Path, help="Local actual full-snapshot restore directory")
    parser.add_argument("--snapshot", type=Path, help="Local sealed snapshot to independently hash")
    parser.add_argument("--expected-bit", default=NEW_BIT)
    parser.add_argument("--baseline-audit", type=Path, help="Historical independent result for offline selfcheck")
    parser.add_argument("--reference-run", type=Path, help="Original sealed 128-step run with six binary captures")
    parser.add_argument("--reference-manifest", type=Path, help="Published six-capture/host-state identity audit record")
    parser.add_argument("--engineering-analysis", type=Path, help="Engineering JSON to compare after independent calculations")
    parser.add_argument("--owner-receipt", type=Path, help="Final external board owner receipt")
    parser.add_argument("--source-dir", type=Path, help="Frozen as-run workload/sampler/command-wrapper sources")
    parser.add_argument("--sensitivity-gap-ms", type=float, help="Separate common-coverage gap sensitivity on unchanged raw")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.pilot_only:
            result = audit_pilot(args.run, args.expected_bit)
        elif args.restore_only:
            result = audit_restore(args.run, args.snapshot, args.expected_bit)
        else:
            result = audit_run(args)
    except (ValueError, KeyError, OSError, TypeError) as error:
        result = dict(status="FAIL", evidence_root=str(args.run.resolve()), reason=str(error))
    result["independent_audit_script_sha256"] = digest(Path(__file__))
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: result[key] for key in ("status", "reason", "numerical_and_command_checks", "run_id", "command_count",
                                                 "frozen_period_ms", "derived_period_ms", "gap_ms", "repeat_summary")
                      if key in result}, indent=2))
    if result["status"] == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()
