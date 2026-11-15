#!/usr/bin/env python3
"""Inspect and repeat the sealed active16 position-127 KV128 workload.

``verify-source`` is offline. ``inspect-live`` only reads XDMA/CSR and saves a
256 MiB KV snapshot. ``run`` requires an accepted inspection, an exclusive
external board lease, and an already running seven-rail sampler. It never
changes the released RTL, numerical path, request tokens, or bitstream.
"""

from __future__ import annotations

import argparse
import ctypes
import dataclasses
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import time

# The proven command_active_inference.py QPC wrapper imports the transport
# after loading this module but before invoking main(). Resolve only import
# paths at module load; the board still remains unopened until inspect/run.
if "--runtime-root" in sys.argv:
    _runtime_arg = sys.argv.index("--runtime-root") + 1
    if _runtime_arg >= len(sys.argv):
        raise ValueError("--runtime-root value missing")
    _runtime_root = Path(sys.argv[_runtime_arg]).resolve()
    sys.path.insert(0, str(_runtime_root / "project/hardware"))
    sys.path.append(str(_runtime_root / "deploy/vendor/runtime"))

BIT_SHA = "96df1a5c1bf4174921bc02ccd88df4066dece3d62b491acb3106bb90ac0ffc85"
REQUESTS_SHA = "7f70c6229bff557383ee9e9b619839bc379dff2dec088d583490a911130c6680"
LAYERS = (0, 8, 16, 24, 31)
ATTENTION_IDS = {layer: 8129 + 2 * layer for layer in LAYERS}
MLP_ID = 8130
LAYER_BYTES = 8 << 20
KV_BYTES = 32 * LAYER_BYTES
SLOT_BYTES = 512 << 10
POSITION_BYTES = 4096
HISTORY_BYTES = 127 * POSITION_BYTES
RECORDS = LAYER_BYTES // 64
RAILS = ("VCCINT_FPGA", "VCC1V8_FPGA", "VADJ_1V8_FPGA", "VCCINTIO_BRAM_FPGA",
         "VCC1V2_FPGA", "MGTAVCC_FPGA", "MGTAVTT_FPGA")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_new(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def journal(path: Path, value: dict) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, sort_keys=True) + "\n")
        stream.flush()


def write_phase(path: Path | None, phase: str, block_id=None, repeat_id=None) -> None:
    if path is None:
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps({"phase": phase, "block_id": block_id,
                                     "repeat_id": repeat_id}, sort_keys=True) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def last_jsonl(path: Path) -> dict:
    with path.open("rb") as stream:
        stream.seek(0, os.SEEK_END)
        end = stream.tell()
        require(end > 0, f"empty log: {path}")
        start = max(0, end - 65536)
        stream.seek(start)
        lines = stream.read().splitlines()
    return json.loads(lines[-1])


def checked_capture_file(root: Path, entry: dict) -> Path:
    require(set(entry) == {"file", "bytes", "sha256"}, "capture file metadata differs")
    file = root / entry["file"]
    require(file.parent == root and file.is_file() and file.stat().st_size == entry["bytes"]
            and sha_file(file) == entry["sha256"], f"sealed capture changed: {file}")
    return file


def verify_source(main: Path) -> dict:
    """Recheck old run, checkpoint, six target payloads, and last ACK trace."""
    main = main.resolve(strict=True)
    receipt = load(main / "receipt.json")
    run = load(main / "device/run.json")
    capture = load(main / "payloads/capture_source.json")
    summary = load(main / "payloads/benchmark_summary.json")
    requests_file = next((candidate for candidate in
                          (main.parent / "requests16_fixed128.json",
                           main.parent.parent / "requests16_fixed128.json",
                           main / "requests16_fixed128.json") if candidate.is_file()),
                         main.parent / "requests16_fixed128.json")
    require(requests_file.is_file() and sha_file(requests_file) == REQUESTS_SHA,
            "fixed 16-request source unavailable or changed")
    requests = load(requests_file)
    require(len(requests) == 16 and [r["slot"] for r in requests] == list(range(16)),
            "fixed requests do not have all 16 ordered slots")
    require(receipt.get("state") == "CAPTURE_COMPLETE" and receipt.get("lease_released")
            and not receipt.get("survivors") and receipt.get("bit_sha256") == BIT_SHA,
            "old board capture lifecycle/bitstream differs")
    require(run.get("execution") == "COMPLETE" and run.get("handles_closed")
            and run.get("final_quiescent") and len(run.get("steps", [])) == 128
            and len(run.get("receipts", [])) == 8192,
            "old 128-step model completion differs")
    require(summary.get("execution") == "COMPLETE" and summary.get("commands") == 8192
            and summary.get("full_output_round_committed")
            and summary.get("last_position_committed") == 127,
            "old position-127 host commit is not sealed")
    require(capture.get("release_bit_sha256") == BIT_SHA
            and capture.get("benchmark_requests_sha256") == REQUESTS_SHA
            and run.get("checkpoint_sha256") == capture.get("checkpoint_sha256"),
            "old release/request/checkpoint identity differs")
    prior = run["steps"][126]["slots"]
    final = run["steps"][127]["slots"]
    checkpoint = load(main / "device/decode_checkpoint_127.json")
    require(len(prior) == len(final) == len(checkpoint) == 16, "checkpoint slots differ")
    for index, (before, after, request) in enumerate(zip(prior, final, requests)):
        check = checkpoint[str(index)]
        require(before["epoch"] == after["epoch"] == 1 and before["position"] == check["position"] == 127
                and after["position"] == 128 and not before["finished"] and after["finished"]
                and before["prompt"] == after["prompt"] == request["prompt_token_ids"]
                and before["max_new_tokens"] == after["max_new_tokens"] == request["max_new_tokens"]
                and before["generated"] == check["generated_ids"]
                and after["generated"] == before["generated"] + [run["steps"][127]["emitted"][str(index)]],
                f"slot {index} checkpoint/last commit differs")
    trace = last_jsonl(main / "commands.jsonl")
    words = trace.get("descriptor_words", [])
    require(trace.get("record") == "command" and trace.get("trace_state") == "ACK_WRITTEN"
            and len(words) == 64 and words[2:8] == [8192, 127, 2, 31, 65535, 8192]
            and all(words[32 + 2 * s:34 + 2 * s] == [127, 1] for s in range(16))
            and trace.get("done_cycles_read", {}).get("value") == run["receipts"][-1]["cycles"],
            "old final command/ACK trace differs")
    entries = [json.loads(line) for line in (main / "payloads/capture.jsonl").read_text(
        encoding="utf-8-sig").splitlines() if line]
    before = {e["command_id"]: e for e in entries if e.get("record") == "before_command"}
    after = {e["command_id"]: e for e in entries if e.get("record") == "after_command"}
    targets = {}
    for layer in LAYERS:
        cid = ATTENTION_IDS[layer]
        require(cid in before and cid in after and before[cid]["layer"] == layer
                and before[cid]["opcode"] == 1 and before[cid]["round"] == 128,
                f"old L{layer} Attention capture missing")
        files = {name: checked_capture_file(main / "payloads", entry)
                 for name, entry in dict(before[cid]["files"], output=after[cid]["output"]).items()}
        require(files["kv_before"].stat().st_size == LAYER_BYTES,
                f"old L{layer} KV capture length differs")
        desc = struct.unpack("<64I", files["descriptor"].read_bytes())
        require(desc[2:8] == (cid, 127, 1, layer, 65535, cid)
                and all(desc[32 + 2 * s:34 + 2 * s] == (127, 1) for s in range(16)),
                f"old L{layer} descriptor differs")
        targets[cid] = files
    require(MLP_ID in before and MLP_ID in after, "old L0 MLP capture missing")
    files = {name: checked_capture_file(main / "payloads", entry)
             for name, entry in dict(before[MLP_ID]["files"], output=after[MLP_ID]["output"]).items()}
    require((before[MLP_ID]["layer"], before[MLP_ID]["opcode"], before[MLP_ID]["round"]) == (0, 2, 128),
            "old L0 MLP identity differs")
    targets[MLP_ID] = files
    return {"main": main, "receipt": receipt, "run": run, "capture": capture,
            "requests": requests, "checkpoint": checkpoint, "targets": targets,
            "last_descriptor": tuple(words), "main_run_sha256": sha_file(main / "device/run.json"),
            "source_receipt_sha256": sha_file(main / "receipt.json")}


def bind_runtime(root: Path):
    root = root.resolve(strict=True)
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[key] = "1"
    sys.path.insert(0, str(root / "project/hardware"))
    sys.path.append(str(root / "deploy/vendor/runtime"))
    from resource_guard import ResourceGuard
    from host.scalellm_final_abi import CSR, FinalDescriptor, ATTENTION, MLP
    from host.scalellm_final_layout import KV_BASE, ROPE_BASE
    from host.scalellm_decode16 import DecodeRow
    from host.scalellm_final_runtime import FinalBoardBackend, FinalDecodeRuntime, HostModelAdapter, RequestSlot
    from host.scalellm_final_assets import FinalAssetStore, FinalHostAssetsModel
    from scalellm_windows_xdma import WindowsXdmaSession
    return locals()


def cpu_budget(max_cpus=8) -> dict:
    """Restrict this Windows process to the contracted logical CPUs 0..7."""
    require(sys.platform == "win32", "CPU affinity here requires Windows")
    require(max_cpus == 8, "this workload contracts exactly CPUs 0..7")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.GetProcessAffinityMask.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t),
                                               ctypes.POINTER(ctypes.c_size_t))
    kernel.SetProcessAffinityMask.argtypes = (ctypes.c_void_p, ctypes.c_size_t)
    process = kernel.GetCurrentProcess()
    allowed, system = ctypes.c_size_t(), ctypes.c_size_t()
    require(kernel.GetProcessAffinityMask(process, ctypes.byref(allowed), ctypes.byref(system)),
            "cannot read process CPU affinity")
    mask = 0xff
    require(allowed.value & mask == mask, "parent does not allow all CPUs 0..7")
    require(kernel.SetProcessAffinityMask(process, mask), "cannot restrict CPU affinity")
    return {"logical_cpus": list(range(8)), "affinity_mask": mask, "blas_threads": 1}


def qpc_clock():
    require(sys.platform == "win32", "board operations require the Dell Windows host")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    value = ctypes.c_longlong()
    require(kernel.QueryPerformanceFrequency(ctypes.byref(value)) and value.value > 0,
            "Windows QPC frequency unavailable")
    frequency = value.value

    def now():
        counter = ctypes.c_longlong()
        require(kernel.QueryPerformanceCounter(ctypes.byref(counter)), "Windows QPC unavailable")
        return counter.value

    return now, frequency


def validate_kv_layer(data: bytes) -> dict:
    """Check every 64-byte record's numeric encoding; DDR has no owner tags."""
    import numpy as np
    require(len(data) == LAYER_BYTES, "KV layer byte length differs")
    records = np.frombuffer(data, dtype=np.uint8).reshape(RECORDS, 64)
    require(not np.any(records[:, 50:]), "KV record reserved padding is nonzero")
    meta = records[:, 48].astype(np.uint16) | (records[:, 49].astype(np.uint16) << 8)
    code = meta & 255
    shift = meta >> 8
    require(bool(np.all(((code == 0) & (shift == 0)) | ((code != 0) & (shift >= 8) & (shift <= 32)))),
            "KV scale metadata encoding differs")
    triples = records[:, :48].reshape(RECORDS, 16, 3).astype(np.uint16)
    even = triples[:, :, 0] | ((triples[:, :, 1] & 15) << 8)
    odd = (triples[:, :, 1] >> 4) | (triples[:, :, 2] << 4)
    require(not np.any(even == 2048) and not np.any(odd == 2048),
            "KV contains forbidden signed -2048 lane")
    zeros = code == 0
    require(not np.any(even[zeros]) and not np.any(odd[zeros]),
            "KV zero scale has nonzero quantized lanes")
    per_slot = np.count_nonzero(code.reshape(16, 128, 64)[:, :127, :], axis=(1, 2)).tolist()
    require(all(value > 0 for value in per_slot),
            "at least one layer/slot history is entirely zero-scale")
    return {"records_checked": RECORDS, "nonzero_scale_by_slot_history": per_slot,
            "sha256": sha_bytes(data)}


def csr_snapshot(session, api: dict) -> dict:
    csr = api["CSR"]
    names = ("MAGIC", "ABI", "CORE_HZ", "STATUS", "ACK_ID", "ADMISSION_ERROR",
             "DONE_ERROR", "DONE_INPUT_BYTES", "DONE_OUTPUT_BYTES", "DONE_CYCLES")
    return {name: session.read32(csr[name]) for name in names} | {
        "completion_descriptor": [session.read32(csr["COMPLETION_DESCRIPTOR"] + 4 * i)
                                  for i in range(64)]}


def assert_old_csr(state: dict, source: dict) -> None:
    require(state["STATUS"] == state["ADMISSION_ERROR"] == state["DONE_ERROR"] == 0,
            "board not quiescent and error-free")
    require(state["ACK_ID"] == 8192
            and state["completion_descriptor"] == list(source["last_descriptor"])
            and state["DONE_CYCLES"] == source["run"]["receipts"][-1]["cycles"]
            and state["DONE_INPUT_BYTES"] == 196608
            and state["DONE_OUTPUT_BYTES"] == 917504,
            "live CSR last command differs from sealed run_002; no DDR acceptance")


def verify_resume_trace(path: Path, source: dict, inspection: dict,
                        inspection_path: Path, frequency: int) -> dict:
    """Accept only the two evidenced, fully ACKed failed qualification prefixes."""
    path = path.resolve(strict=True)
    attempt = path.parent
    receipt = load(attempt / "receipt.json")
    prior = load(attempt / "workload/workload.json")
    script_sha = receipt.get("workload_script_sha256")
    if script_sha == "0f9854577a8c5e20e86f05f6ed83955800dff4ce0db36ae2cf295f9338cd32eb":
        first_id, command_count, last_id = 8193, 43, 8235
        require(prior.get("resume") is None, "main_001 must begin at sealed command8192")
    elif script_sha == "147eef06d63b11d5c80576f240694b58cf0c71803c6642c56bc0ffa6e28d62ba":
        first_id, command_count, last_id = 8236, 50, 8285
        previous = verify_resume_trace(attempt.parent / "main_001/commands.jsonl",
                                       source, inspection, inspection_path, frequency)
        require(prior.get("resume") == {k: v for k, v in previous.items()
                                         if k != "last_trace"},
                "main_003 resume chain does not match sealed main_001 evidence")
        require(prior.get("initial_full_kv_snapshot_byteexact") is True
                and prior.get("resume_live_csr", {}).get("ACK_ID") == 8235,
                "main_003 did not establish the prior live CSR and 256 MiB KV baseline")
    else:
        raise RuntimeError("failed qualification source is not one of two sealed attempts")
    require(receipt.get("state") == "FAIL" and receipt.get("lease_released")
            and not receipt.get("survivors")
            and receipt.get("workload_exit_code") != 0
            and receipt.get("command_trace_script_sha256")
            == "892f551c6cedcbb5b30eb884f0935909684d7d1931d30a6fa8645377323b4ec1",
            "failed qualification launcher lifecycle/source is not sealed")
    require(prior.get("status") == "FAIL" and not prior.get("windows")
            and "qualification" not in prior
            and "seven-rail sampler stopped appending before safe boundary" in prior.get("error", "")
            and prior.get("source_main_run_sha256") == source["main_run_sha256"]
            and prior.get("inspection_sha256") == sha_file(inspection_path)
            and prior.get("snapshot_sha256") == inspection["snapshot_sha256"],
            "failed qualification did not stop on the known heartbeat race before any window")
    require(receipt.get("run_id") == prior.get("run_id")
            and receipt.get("qpc_frequency") == prior.get("qpc_frequency") == frequency,
            "failed qualification run/QPC identity differs")
    old_boot = datetime.fromisoformat(receipt["boot_utc"].replace("Z", "+00:00"))
    current_boot = datetime.fromisoformat(os.environ["SCALELLM_BOOT_UTC"].replace("Z", "+00:00"))
    require(abs((current_boot - old_boot).total_seconds()) <= 10,
            "failed qualification and current OS session differ")
    records = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line]
    require(len(records) == command_count + 1 and records[0].get("record") == "clock"
            and records[0].get("schema") == "scalellm_command_qpc_v1"
            and records[0].get("qpc_frequency") == frequency
            and records[0].get("run_id") == receipt["run_id"]
            and records[0].get("boot_utc") == receipt["boot_utc"],
            "failed qualification command trace clock/count differs")
    summaries = [json.loads(line) for line in
                 (attempt / "workload/commands_summary.jsonl").read_text(
                     encoding="utf-8-sig").splitlines() if line]
    require(len(summaries) == command_count, "failed qualification summary count differs")
    for ordinal, (trace, summary) in enumerate(zip(records[1:], summaries)):
        cid = first_id + ordinal
        layer, opcode = ordinal // 2, (1 if ordinal % 2 == 0 else 2)
        words = trace.get("descriptor_words", [])
        require(trace.get("record") == "command" and trace.get("trace_state") == "ACK_WRITTEN"
                and trace.get("first_busy") is not None and trace.get("first_done") is not None
                and trace.get("ack_write") is not None and trace.get("first_error_status") is None
                and len(words) == 64 and words[2:8] == [cid, 127, opcode, layer, 65535, cid]
                and all(words[32 + 2 * slot:34 + 2 * slot] == [127, 1] for slot in range(16))
                and summary.get("record") == "completed_command"
                and (summary.get("command_id"), summary.get("layer"), summary.get("opcode"))
                == (cid, layer, opcode)
                and summary.get("descriptor_sha256") == trace.get("descriptor_sha256")
                and summary.get("cycles") == trace.get("done_cycles_read", {}).get("value")
                and summary.get("output_bytes") == trace.get("output_transfer", {}).get("bytes"),
                f"failed qualification command {cid} is incomplete or differs")
        target_id = ATTENTION_IDS.get(layer) if opcode == 1 else MLP_ID if layer == 0 else None
        if target_id is not None:
            require(summary["input_sha256"] == sha_file(source["targets"][target_id]["input"])
                    and summary["output_sha256"] == sha_file(source["targets"][target_id]["output"]),
                    f"failed qualification captured command {cid} numerical bytes differ")
    last = records[-1]
    require(last["descriptor_words"][2] == last_id
            and last["descriptor_words"][4:6]
            == [1 if command_count % 2 else 2, (command_count - 1) // 2],
            "failed qualification did not stop at its expected last ACK")
    return {"last_command_id": last_id, "last_generation": last["descriptor_words"][7],
            "last_trace": last, "trace_sha256": sha_file(path),
            "prior_report_sha256": sha_file(attempt / "workload/workload.json"),
            "prior_receipt_sha256": sha_file(attempt / "receipt.json"),
            "prior_summary_sha256": sha_file(attempt / "workload/commands_summary.jsonl"),
            "prior_run_id": receipt["run_id"], "prior_boot_utc": receipt["boot_utc"],
            "completed_commands": len(summaries)}


def assert_resume_csr(state: dict, resume: dict) -> None:
    last = resume["last_trace"]
    require(state["STATUS"] == state["ADMISSION_ERROR"] == state["DONE_ERROR"] == 0
            and state["ACK_ID"] == resume["last_command_id"]
            and state["completion_descriptor"] == last["descriptor_words"]
            and state["DONE_CYCLES"] == last["done_cycles_read"]["value"]
            and state["DONE_INPUT_BYTES"] == last["input_transfer"]["bytes"]
            and state["DONE_OUTPUT_BYTES"] == last["output_transfer"]["bytes"],
            "current live CSR does not equal failed qualification last ACK; no resume writes")


def inspect_live(args, source: dict) -> dict:
    require(sys.platform == "win32", "live inspection requires Windows XDMA")
    require(sha_file(args.bit_file) == BIT_SHA, "live bitstream file hash differs")
    api = bind_runtime(args.runtime_root)
    cpu_budget(8)
    guard = api["ResourceGuard"](rss_limit=8 << 30, available_floor=2 << 30)
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    snapshot = out / "kv_snapshot.bin"
    report = {"schema": "scalellm_kv128_live_inspection_v1", "status": "RUNNING",
              "source_main_run_sha256": source["main_run_sha256"],
              "source_receipt_sha256": source["source_receipt_sha256"],
              "source_boot_utc": source["receipt"]["boot_utc"],
              "observed_boot_utc": os.environ.get("SCALELLM_BOOT_UTC"),
              "boot_continuity": "EXTERNAL_EVENT_CHAIN_REQUIRED",
              "bit_sha256": BIT_SHA, "read_only": True, "layers": []}
    try:
        with api["WindowsXdmaSession"](timeout_ms=5000, log_path=str(out / "xdma.jsonl")) as session:
            backend = api["FinalBoardBackend"](session, timeout_s=120)
            backend.require_quiescent()
            state = csr_snapshot(session, api)
            assert_old_csr(state, source)
            report["csr"] = state
            digest = hashlib.sha256()
            with snapshot.open("xb") as stream:
                for layer in range(32):
                    guard()
                    data = session.c2h_read_local(0, LAYER_BYTES,
                                                  api["KV_BASE"] + layer * LAYER_BYTES, 1 << 20)
                    detail = validate_kv_layer(data)
                    if layer in LAYERS:
                        old = source["targets"][ATTENTION_IDS[layer]]["kv_before"].read_bytes()
                        for slot in range(16):
                            start = slot * SLOT_BYTES
                            require(data[start:start + HISTORY_BYTES] == old[start:start + HISTORY_BYTES],
                                    f"live L{layer} slot{slot} positions0..126 differ from sealed capture")
                        detail["sealed_history_comparison"] = "16_slots_x_127_positions_BYTEEXACT"
                    else:
                        detail["sealed_history_comparison"] = "NO_OLD_PER_LAYER_HASH"
                    stream.write(data)
                    digest.update(data)
                    report["layers"].append({"layer": layer, **detail})
            require(snapshot.stat().st_size == KV_BYTES, "KV snapshot length differs")
            backend.require_quiescent()
            require(csr_snapshot(session, api) == state, "CSR changed during read-only KV inspection")
            report.update(status="PASS_WITH_LIMITS", snapshot_file=str(snapshot),
                          snapshot_bytes=KV_BYTES, snapshot_sha256=digest.hexdigest(),
                          history_provenance="5_layers_byteexact;27_layers_format_and_nonzero_only",
                          independent_full_model_oracle="NOT_ESTABLISHED")
            report["resources"] = guard.summary()
    except BaseException as error:
        report.update(status="FAIL", error=repr(error))
        raise
    finally:
        save_new(out / "inspection.json", report)
    return report


def snapshot_layers(snapshot: Path):
    require(snapshot.stat().st_size == KV_BYTES, "KV snapshot size differs")
    with snapshot.open("rb") as stream:
        for layer in range(32):
            data = stream.read(LAYER_BYTES)
            require(len(data) == LAYER_BYTES, "short KV snapshot")
            yield layer, data


def assert_snapshot(session, api: dict, snapshot: Path) -> str:
    digest = hashlib.sha256()
    for layer, reference in snapshot_layers(snapshot):
        live = session.c2h_read_local(0, LAYER_BYTES,
                                      api["KV_BASE"] + layer * LAYER_BYTES, 1 << 20)
        require(live == reference, f"live KV layer {layer} differs from accepted baseline")
        digest.update(live)
    return digest.hexdigest()


def restore_last_position(session, backend, api: dict, layer: int, data: bytes) -> None:
    """Restore all 16 physical append slots; positions0..126 are untouched."""
    require(len(data) == LAYER_BYTES, "restore layer size differs")
    backend.require_quiescent()
    for slot in range(16):
        offset = slot * SLOT_BYTES + 127 * POSITION_BYTES
        expected = data[offset:offset + POSITION_BYTES]
        address = api["KV_BASE"] + layer * LAYER_BYTES + offset
        require(session.h2c_write_local(0, expected, address, 1 << 20) == POSITION_BYTES,
                f"short KV position127 restore at L{layer} slot{slot}")
        require(session.c2h_read_local(0, POSITION_BYTES, address, 1 << 20) == expected,
                f"KV position127 restore readback differs at L{layer} slot{slot}")


def point_counts(path: Path, start: int, end: int) -> dict[str, int]:
    counts = {rail: 0 for rail in RAILS}
    if not path.is_file():
        return counts
    with path.open("r", encoding="utf-8-sig") as stream:
        for line in stream:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue  # The sampler may still be appending the final line.
            name = row.get("name")
            if (row.get("record") == "rail_point" and name in counts
                    and row.get("voltage_v") is not None and row.get("current_a") is not None
                    and start <= row.get("vi_before_ticks", -1)
                    and row.get("point_after_ticks", end + 1) <= end):
                counts[name] += 1
    return counts


def sampler_qpc_heartbeat(path: Path, now, frequency: int, run_id: str) -> dict:
    """Read one complete recent sampler record using the shared QPC domain."""
    detail = {"source": str(path), "qpc_frequency": frequency,
              "run_id": run_id, "tail_limit_bytes": 32768, "age_limit_seconds": 10}
    if not path.is_file():
        return dict(detail, valid=False, reason="SAMPLER_LOG_MISSING")
    with path.open("rb") as stream:
        stream.seek(0, os.SEEK_END)
        end = stream.tell()
        begin = max(0, end - 32768)
        stream.seek(begin)
        if begin:
            stream.readline()  # Discard a potentially partial first record.
        data = stream.read(end - stream.tell())
    lines = data.split(b"\n")
    if data and not data.endswith(b"\n"):
        lines.pop()  # Concurrent PowerShell append may be a partial last JSON line.
    for raw in reversed(lines):
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        kind = row.get("record")
        if kind == "bus_read" and row.get("api_status") == "returned":
            tick = row.get("after_ticks")
            if row.get("qpc_frequency") != frequency:
                continue
        elif kind == "sweep" and row.get("complete_rail_points") == 7:
            tick = row.get("end_ticks")
        else:
            continue
        if row.get("run_id") != run_id or type(tick) is not int or tick <= 0:
            continue
        observed = now()  # Read after the immutable completed line, never before.
        age = (observed - tick) / frequency
        return dict(detail, valid=0 <= age < 10, reason="QPC_AGE",
                    record=kind, record_ticks=tick, observed_ticks=observed,
                    age_seconds=age, sweep=row.get("sweep"), read_id=row.get("read_id"))
    return dict(detail, valid=False, reason="NO_COMPLETE_SAME_RUN_QPC_RECORD")


def run_windows(args, source: dict) -> dict:
    """Qualification, then three matched idle/A/MLP/full windows."""
    require(sys.platform == "win32", "live workload requires Windows XDMA")
    require(sha_file(args.bit_file) == BIT_SHA, "live bitstream file hash differs")
    inspection = load(args.inspection)
    snapshot = Path(inspection["snapshot_file"]).resolve(strict=True)
    require(inspection["status"] == "PASS_WITH_LIMITS"
            and inspection["source_main_run_sha256"] == source["main_run_sha256"]
            and inspection["snapshot_bytes"] == KV_BYTES
            and sha_file(snapshot) == inspection["snapshot_sha256"],
            "accepted KV inspection/snapshot changed")
    require(args.sampler_jsonl.is_file() and args.sampler_ready.is_file(),
            "seven-rail sampler is not ready")
    api = bind_runtime(args.runtime_root)
    cpu_affinity = cpu_budget(8)
    guard = api["ResourceGuard"](rss_limit=8 << 30, available_floor=2 << 30)
    from host_math import HostAssets
    from host.scalellm_mlp_gu_only_artifacts import GuOnlyArtifactManifest
    now, frequency = qpc_clock()
    resume = (verify_resume_trace(args.resume_command_trace, source, inspection,
                                  args.inspection, frequency)
              if args.resume_command_trace is not None else None)
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    windows = args.windows_jsonl.resolve()
    require(not windows.exists() and windows.parent.is_dir(), "window journal must be a new file")
    phase_path = None if args.phase_path is None else args.phase_path.resolve()
    require(phase_path is None or phase_path.parent.is_dir(), "phase marker parent absent")
    report = {"schema": "scalellm_kv128_sevenrail_workload_v1", "status": "RUNNING",
              "source_main_run_sha256": source["main_run_sha256"],
              "inspection_sha256": sha_file(args.inspection), "snapshot_sha256": inspection["snapshot_sha256"],
              "windows_jsonl": str(windows), "qpc_frequency": frequency,
              "host": os.environ.get("COMPUTERNAME"),
              "boot_utc": os.environ.get("SCALELLM_BOOT_UTC"),
              "run_id": os.environ.get("SCALELLM_RUN_ID"),
              "cpu_affinity": cpu_affinity, "windows": [],
              "resume": None if resume is None else {k: v for k, v in resume.items()
                                                      if k != "last_trace"}}
    started = time.monotonic()

    def check_budget():
        guard()
        require(time.monotonic() - started < args.wall_seconds,
                "workload global wall budget expired at safe boundary")
        require(args.stop_file is None or not args.stop_file.exists(),
                "workload external stop requested at safe boundary")
        heartbeat = sampler_qpc_heartbeat(args.sampler_jsonl, now, frequency,
                                          report["run_id"])
        report["sampler_last_heartbeat"] = heartbeat
        require(heartbeat["valid"],
                f"seven-rail sampler QPC heartbeat failed: {heartbeat}")

    try:
        write_phase(phase_path, "setup")
        check_budget()
        assets = HostAssets(args.assets, verify=True)
        artifacts = GuOnlyArtifactManifest.load(args.artifacts, verify_hashes=True)
        require(artifacts.original.checkpoint_sha256 == assets.manifest["checkpoint_sha256"]
                == source["capture"]["checkpoint_sha256"], "model checkpoint differs")
        with api["WindowsXdmaSession"](timeout_ms=5000, log_path=str(out / "xdma.jsonl")) as session:
            backend_type = api["FinalBoardBackend"]
            target_files = source["targets"]

            class CheckingBackend(backend_type):
                def run(self, descriptor, payload, validate_output=None):
                    check_budget()
                    self.require_quiescent()
                    require(descriptor.active_mask == 65535 and descriptor.rows[0].position == 127
                            and all(r.active and r.epoch == 1 and r.position == 127 for r in descriptor.rows),
                            "replay descriptor does not address 16 epoch1 position127 rows")
                    old_id = (ATTENTION_IDS.get(descriptor.layer) if descriptor.opcode == 1
                              else MLP_ID if descriptor.layer == 0 else None)
                    if old_id is not None:
                        require(payload == target_files[old_id]["input"].read_bytes(),
                                f"replay L{descriptor.layer} opcode{descriptor.opcode} input differs")
                        expected = target_files[old_id]["output"].read_bytes()
                        original_validator = validate_output
                        def check(desc, output):
                            require(output == expected, f"replay L{desc.layer} opcode{desc.opcode} output differs")
                            if original_validator is not None:
                                original_validator(desc, output)
                        validate_output = check
                    output = super().run(descriptor, payload, validate_output)
                    journal(out / "commands_summary.jsonl", {
                        "record": "completed_command", "command_id": descriptor.command_id,
                        "batch_tag": descriptor.batch_tag, "layer": descriptor.layer,
                        "opcode": descriptor.opcode, "active_mask": descriptor.active_mask,
                        "position": 127, "epoch": 1,
                        "descriptor_sha256": sha_bytes(descriptor.pack()),
                        "input_sha256": sha_bytes(payload),
                        "output_sha256": sha_bytes(output),
                        "output_bytes": len(output), "cycles": self.receipts[-1]["cycles"],
                        "utc_unix_ns": time.time_ns()})
                    return output

            backend = CheckingBackend(session, timeout_s=120)
            initial_csr = csr_snapshot(session, api)
            if resume is None:
                assert_old_csr(initial_csr, source)
            else:
                assert_resume_csr(initial_csr, resume)
                report["resume_live_csr"] = initial_csr
            require(assert_snapshot(session, api, snapshot) == inspection["snapshot_sha256"],
                    "board KV changed after accepted read-only inspection")
            report["initial_full_kv_snapshot_byteexact"] = True
            store = api["FinalAssetStore"](backend, artifacts, assets)
            model = api["HostModelAdapter"](api["FinalHostAssetsModel"](assets), store)
            store.load_resident()
            rows = tuple(api["DecodeRow"](True, 1, 127) for _ in range(16))
            next_command = 8192 if resume is None else resume["last_command_id"]
            next_generation = 8192 if resume is None else resume["last_generation"]

            def make_runtime():
                runtime = api["FinalDecodeRuntime"](backend, model, store, ())
                runtime.slots = [api["RequestSlot"](1, tuple(s["prompt"]), s["max_new_tokens"],
                                                    127, list(s["generated"]), False)
                                 for s in source["run"]["steps"][126]["slots"]]
                runtime.command_id = next_command
                runtime.buffer_generation = next_generation
                runtime.batch_tag = 127
                return runtime

            def do_full(label, guarded=False, repeat_id=None):
                nonlocal next_command, next_generation
                backend.require_quiescent()
                for layer, data in snapshot_layers(snapshot):
                    restore_last_position(session, backend, api, layer, data)
                require(assert_snapshot(session, api, snapshot) == inspection["snapshot_sha256"],
                        "full-step physical KV prestate differs")
                runtime = make_runtime()
                before_count = len(backend.receipts)
                if guarded:
                    write_phase(phase_path, "full_pre_guard", "full_kv128_step", repeat_id)
                    time.sleep(10)  # Quiet PMBus samples immediately before step().
                write_phase(phase_path, "full_kv128_step" if guarded else "qualification",
                            "full_kv128_step" if guarded else "qualification", repeat_id)
                start = now()  # Full window begins before embedding in runtime.step().
                emitted = runtime.step()
                end = now()    # Commit and all Host Down/LM-head work have returned.
                if guarded:
                    write_phase(phase_path, "full_post_guard", "full_kv128_step", repeat_id)
                    time.sleep(10)  # Quiet PMBus samples immediately after commit.
                final = [dict(dataclasses.asdict(slot), prompt=list(slot.prompt))
                         for slot in runtime.slots]
                require(emitted == {int(k): v for k, v in source["run"]["steps"][127]["emitted"].items()}
                        and final == source["run"]["steps"][127]["slots"],
                        "full position127 token/slot commit differs from sealed run")
                receipts = backend.receipts[before_count:]
                require(len(receipts) == 64
                        and [(r["layer"], r["opcode"]) for r in receipts]
                        == [(layer, opcode) for layer in range(32) for opcode in (1, 2)],
                        "full position127 step did not execute all 32 A/M layers")
                next_command, next_generation = runtime.command_id, runtime.buffer_generation
                require(assert_snapshot(session, api, snapshot) == inspection["snapshot_sha256"],
                        "full-step KV changed from deterministic accepted baseline")
                result = {"start_ticks": start, "end_ticks": end,
                          "completed_commands": 64, "fpga_cycles": sum(r["cycles"] for r in receipts),
                          "emitted": emitted, "token_match": True,
                          "six_target_inputs_outputs_byteexact": True,
                          "all_32_layer_receipts": True, "kv_snapshot_restored_and_preserved": True,
                          "label": label}
                return result

            # The first complete step qualifies the 27 layers lacking sealed KV bytes.
            qualification = do_full("unmeasured_live_state_qualification")
            report["qualification"] = qualification
            journal(out / "events.jsonl", {"record": "qualification", **qualification})

            # Establish that a local 16x4KiB restore is equivalent to the
            # contract's complete 8 MiB pre-append layer restore. This is a
            # separate unmeasured qualification for every selected A layer.
            write_phase(phase_path, "qualification_attention_restore")
            rope = target_files[ATTENTION_IDS[0]]["rope"].read_bytes()
            require(all(target_files[ATTENTION_IDS[layer]]["rope"].read_bytes() == rope
                        for layer in LAYERS), "five target RoPE rows differ")
            require(session.h2c_write_local(0, rope, api["ROPE_BASE"], 1 << 20) == len(rope)
                    and session.c2h_read_local(0, len(rope), api["ROPE_BASE"], 1 << 20) == rope,
                    "qualification RoPE stage/readback differs")
            restore_proof = []
            with snapshot.open("rb") as snapshot_stream:
                for layer in LAYERS:
                    check_budget()
                    backend.require_quiescent()
                    snapshot_stream.seek(layer * LAYER_BYTES)
                    expected_after = snapshot_stream.read(LAYER_BYTES)
                    before = target_files[ATTENTION_IDS[layer]]["kv_before"].read_bytes()
                    address = api["KV_BASE"] + layer * LAYER_BYTES
                    require(session.h2c_write_local(0, before, address, 1 << 20) == LAYER_BYTES,
                            f"short complete L{layer} pre-append KV restore")
                    require(session.c2h_read_local(0, LAYER_BYTES, address, 1 << 20) == before,
                            f"complete L{layer} pre-append KV restore readback differs")
                    next_command += 1; next_generation += 1
                    descriptor = api["FinalDescriptor"].create(
                        next_command, 127, api["ATTENTION"], layer, rows,
                        next_generation, max(store.generation, 1))
                    backend.run(descriptor, target_files[ATTENTION_IDS[layer]]["input"].read_bytes())
                    actual_after = session.c2h_read_local(0, LAYER_BYTES, address, 1 << 20)
                    for slot in range(16):
                        offset = slot * SLOT_BYTES
                        require(actual_after[offset:offset + HISTORY_BYTES]
                                == before[offset:offset + HISTORY_BYTES],
                                f"L{layer} slot{slot} historical KV changed during Attention")
                    require(actual_after == expected_after,
                            f"complete L{layer} Attention append did not restore accepted baseline")
                    complete_restore_command = next_command
                    restore_last_position(session, backend, api, layer, before)
                    require(session.c2h_read_local(0, LAYER_BYTES, address, 1 << 20) == before,
                            f"L{layer} local position127 restore differs from full 8 MiB prestate")
                    next_command += 1; next_generation += 1
                    descriptor = api["FinalDescriptor"].create(
                        next_command, 127, api["ATTENTION"], layer, rows,
                        next_generation, max(store.generation, 1))
                    backend.run(descriptor, target_files[ATTENTION_IDS[layer]]["input"].read_bytes())
                    require(session.c2h_read_local(0, LAYER_BYTES, address, 1 << 20) == expected_after,
                            f"L{layer} local position127 restore replay differs from full restore")
                    restore_proof.append({"layer": layer,
                                          "full_restore_command_id": complete_restore_command,
                                          "local_restore_command_id": next_command,
                                          "kv_before_sha256": sha_bytes(before),
                                          "kv_after_sha256": sha_bytes(expected_after),
                                          "history_unchanged": True, "output_byteexact": True,
                                          "local_equivalent_to_full_8mib": True})
            report["local_position127_restore_qualification"] = restore_proof
            require(assert_snapshot(session, api, snapshot) == inspection["snapshot_sha256"],
                    "five-layer restore qualification changed accepted KV baseline")
            write_phase(phase_path, "between_windows")

            def append_window(kind, repeat_id, payload):
                published_kind = {"idle": "idle", "attention": "attention_repeat",
                                  "mlp": "mlp_repeat", "full": "full_kv128_step"}[kind]
                record = {"record": "window", "kind": published_kind, "repeat_id": repeat_id,
                          "qpc_frequency": frequency, "host": report["host"],
                          "boot_utc": report["boot_utc"], "run_id": report["run_id"],
                          "status": "COMPLETE", "start_boundary": payload.pop("start_boundary"),
                          "end_boundary": payload.pop("end_boundary"), **payload}
                record["rail_vi_points"] = point_counts(args.sampler_jsonl,
                                                        record["start_ticks"], record["end_ticks"])
                require(min(record["rail_vi_points"].values()) >= 200,
                        f"{kind} window lacks 200 VI points per rail")
                if kind != "full":
                    require((record["end_ticks"] - record["start_ticks"]) / frequency >= 120,
                            f"{kind} window shorter than 120s")
                journal(windows, record)
                report["windows"].append(record)

            # Fixed before observing power: one paired idle in each block,
            # with rotated A/M/full order to reduce time-order confounding.
            schedule = ((1, ("idle", "attention", "mlp", "full")),
                        (2, ("idle", "mlp", "full", "attention")),
                        (3, ("idle", "full", "attention", "mlp")))
            report["fixed_schedule"] = [dict(block_id=block, order=list(order))
                                        for block, order in schedule]
            for repeat_id, order in schedule:
                for kind in order:
                    check_budget()
                    backend.require_quiescent()
                    require(assert_snapshot(session, api, snapshot) == inspection["snapshot_sha256"],
                            f"KV baseline differs before {kind} repeat{repeat_id}")
                    if kind == "idle":
                        write_phase(phase_path, "idle", "idle", repeat_id)
                        start = now()
                        while (now() - start) / frequency < 120:
                            check_budget()
                            time.sleep(0.5)
                        end = now()
                        counts = point_counts(args.sampler_jsonl, start, end)
                        while min(counts.values()) < 200 and (end - start) / frequency < 180:
                            check_budget()
                            time.sleep(1)
                            end = now()
                            counts = point_counts(args.sampler_jsonl, start, end)
                        payload = {"start_ticks": start, "end_ticks": end,
                                   "completed_commands": 0, "start_boundary": "board_quiescent_before_idle",
                                   "end_boundary": "board_quiescent_after_idle"}
                    elif kind == "full":
                        payload = do_full(f"full_repeat_{repeat_id}", guarded=True,
                                          repeat_id=repeat_id)
                        payload.update(start_boundary="before_runtime_step_embedding",
                                       end_boundary="after_runtime_step_commit_return")
                    elif kind == "attention":
                        # Resident Attention weights are already verified and staged.
                        rope = target_files[ATTENTION_IDS[0]]["rope"].read_bytes()
                        require(all(target_files[ATTENTION_IDS[layer]]["rope"].read_bytes() == rope
                                    for layer in LAYERS), "five target RoPE rows differ")
                        require(session.h2c_write_local(0, rope, api["ROPE_BASE"], 1 << 20) == len(rope)
                                and session.c2h_read_local(0, len(rope), api["ROPE_BASE"], 1 << 20) == rope,
                                "Attention RoPE stage/readback differs")
                        write_phase(phase_path, "attention_repeat", "attention_repeat", repeat_id)
                        start = now()
                        counts_by_layer = {layer: 0 for layer in LAYERS}
                        cycles_by_layer = {layer: 0 for layer in LAYERS}
                        while True:
                            check_budget()
                            for layer in LAYERS:
                                old_kv = target_files[ATTENTION_IDS[layer]]["kv_before"].read_bytes()
                                restore_last_position(session, backend, api, layer, old_kv)
                                next_command += 1; next_generation += 1
                                desc = api["FinalDescriptor"].create(next_command, 127, api["ATTENTION"],
                                                                      layer, rows, next_generation,
                                                                      max(store.generation, 1))
                                backend.run(desc, target_files[ATTENTION_IDS[layer]]["input"].read_bytes())
                                counts_by_layer[layer] += 1
                                cycles_by_layer[layer] += backend.receipts[-1]["cycles"]
                            end = now()  # Stop only at a complete five-layer ACK boundary.
                            elapsed = (end - start) / frequency
                            if elapsed >= 120:
                                counts = point_counts(args.sampler_jsonl, start, end)
                                if min(counts.values()) >= 200:
                                    break
                            require(elapsed < 175, "Attention reached safe 180s window limit without VI coverage")
                        payload = {"start_ticks": start, "end_ticks": end,
                                   "completed_commands": sum(counts_by_layer.values()),
                                   "layers": counts_by_layer, "fpga_cycles_by_layer": cycles_by_layer,
                                   "five_layer_complete_cycles": min(counts_by_layer.values()),
                                   "start_boundary": "before_first_position127_restore",
                                   "end_boundary": "after_last_attention_ack"}
                    else:
                        # GU halves and RoPE are staged outside the MLP window.
                        store.prepare_layer(0, rows)
                        write_phase(phase_path, "mlp_repeat", "mlp_repeat", repeat_id)
                        start = now()
                        count = cycles = 0
                        last_point_check = 0.0
                        while True:
                            check_budget()
                            next_command += 1; next_generation += 1
                            desc = api["FinalDescriptor"].create(next_command, 127, api["MLP"],
                                                                  0, rows, next_generation, store.generation)
                            backend.run(desc, target_files[MLP_ID]["input"].read_bytes())
                            count += 1; cycles += backend.receipts[-1]["cycles"]
                            end = now()
                            elapsed = (end - start) / frequency
                            if elapsed >= 120 and time.monotonic() - last_point_check >= 1:
                                last_point_check = time.monotonic()
                                counts = point_counts(args.sampler_jsonl, start, end)
                                if min(counts.values()) >= 200:
                                    break
                            require(elapsed < 179, "MLP reached safe 180s window limit without VI coverage")
                        payload = {"start_ticks": start, "end_ticks": end,
                                   "completed_commands": count, "fpga_cycles": cycles,
                                   "layer": 0, "start_boundary": "before_first_mlp_command",
                                   "end_boundary": "after_last_mlp_ack"}
                    backend.require_quiescent()
                    write_phase(phase_path, "between_windows")
                    require(assert_snapshot(session, api, snapshot) == inspection["snapshot_sha256"],
                            f"KV baseline changed after {kind} repeat{repeat_id}")
                    append_window(kind, repeat_id, payload)
            report.update(status="COMPLETE_WITH_LIMITS", completed_windows=12,
                          independent_full_model_oracle="NOT_ESTABLISHED",
                          historical_kv_source_for_27_layers="LIFECYCLE_AND_LIVE_BEHAVIOR_ONLY")
    except BaseException as error:
        report.update(status="FAIL", error=repr(error))
        write_phase(phase_path, "failed")
        raise
    finally:
        if report["status"] == "COMPLETE_WITH_LIMITS":
            write_phase(phase_path, "complete")
        report["resources"] = guard.summary()
        save_new(out / "workload.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    source_only = commands.add_parser("verify-source")
    inspect = commands.add_parser("inspect-live")
    run = commands.add_parser("run")
    for command in (source_only, inspect, run):
        command.add_argument("--main", type=Path, required=True, help="sealed run_002 root")
    for command in (inspect, run):
        command.add_argument("--runtime-root", type=Path, required=True)
        command.add_argument("--bit-file", type=Path, required=True)
        command.add_argument("--out", type=Path, required=True)
    run.add_argument("--inspection", type=Path, required=True)
    run.add_argument("--resume-command-trace", type=Path,
                     help="failed main_001 commands.jsonl; also checks its receipt, report and summaries")
    run.add_argument("--artifacts", type=Path, required=True)
    run.add_argument("--assets", type=Path, required=True)
    run.add_argument("--sampler-jsonl", type=Path, required=True)
    run.add_argument("--sampler-ready", type=Path, required=True)
    run.add_argument("--windows-jsonl", type=Path, required=True)
    run.add_argument("--phase-path", type=Path,
                     help="optional atomic phase JSON consumed by the seven-rail sampler")
    run.add_argument("--stop-file", type=Path,
                     help="optional externally requested stop, honored at quiescent boundaries")
    run.add_argument("--wall-seconds", type=float, default=2700)
    args = parser.parse_args(argv)
    if args.command == "run":
        require(0 < args.wall_seconds <= 7200, "workload wall limit outside (0,7200]")
    source = verify_source(args.main)
    if args.command == "verify-source":
        result = {"status": "PASS", "source_main_run_sha256": source["main_run_sha256"],
                  "last_command_id": 8192, "captured_attention_layers": LAYERS,
                  "captured_mlp_layers": (0,)}
    elif args.command == "inspect-live":
        result = inspect_live(args, source)
    else:
        result = run_windows(args, source)
    print(json.dumps(result if args.command == "verify-source" else {
        "status": result["status"], "out": str(args.out)}, sort_keys=True))


if __name__ == "__main__":
    main()
