#!/usr/bin/env python3
"""Inspect and repeat a fresh public active16 position-127 KV128 benchmark.

``verify-source`` verifies the public benchmark offline. ``inspect-live`` only reads XDMA/CSR and compares the complete
fresh 256 MiB KV snapshot. ``run`` requires an accepted inspection, an exclusive
external board lease, and an already running seven-rail sampler. It never
changes the released RTL, numerical path, request tokens, or bitstream.
"""

from __future__ import annotations

import argparse
import ctypes
import dataclasses
import hashlib
import json
import os
from pathlib import Path
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

BIT_SHA = "5d78519aa10695be564f668d5a41a0e5554e282c31d39f648534a7dc01ab72f7"
REFERENCE_BIT_SHA = BIT_SHA
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


def verify_source(main: Path) -> dict:
    from portable_source import verify_portable_source
    return verify_portable_source(main)


def bind_runtime(root: Path):
    root = root.resolve(strict=True)
    from portable_source import ROOT
    manifest = load(ROOT / "deploy/vendor_manifest.json")
    require(sha_file(root / "deploy/vendor_manifest.json") == sha_file(ROOT / "deploy/vendor_manifest.json"),
            "StageRoot public source manifest differs")
    for relative, identity in manifest["files"].items():
        path = (root / relative).resolve(strict=True)
        require(path.is_relative_to(root) and path.stat().st_size == identity["bytes"]
                and sha_file(path) == identity["sha256"], "StageRoot runtime changed: " + relative)
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
    from deploy.final.common import cpu_budget as apply_cpu_budget
    require(sys.platform == "win32", "CPU affinity here requires Windows")
    return apply_cpu_budget(max_cpus)


def qpc_clock():
    require(sys.platform == "win32", "board operations require Windows")
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


def assert_benchmark_csr(state: dict, source: dict) -> None:
    require(state["STATUS"] == state["ADMISSION_ERROR"] == state["DONE_ERROR"] == 0,
            "board not quiescent and error-free")
    require(state["ACK_ID"] == 8192
            and state["completion_descriptor"] == list(source["last_descriptor"])
            and state["DONE_CYCLES"] == source["run"]["receipts"][-1]["cycles"]
            and state["DONE_INPUT_BYTES"] == 196608
            and state["DONE_OUTPUT_BYTES"] == 917504,
            "live CSR last command differs from fresh benchmark; no DDR acceptance")


def inspect_live(args, source: dict) -> dict:
    from portable_live import inspect_or_restore
    return inspect_or_restore(args, source, sys.modules[__name__])


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
    from portable_live import require_launcher
    require_launcher()
    from deploy.final.common import read_program_receipt
    programming = read_program_receipt(args.program_receipt, "all-dsp")
    require(sha_file(args.bit_file) == BIT_SHA, "live bitstream file hash differs")
    inspection = load(args.inspection)
    snapshot = Path(inspection["snapshot_file"]).resolve(strict=True)
    require(inspection.get("schema") == "scalellm_portable_kv128_inspection_v1"
            and inspection.get("handles_closed") is True
            and inspection.get("full_snapshot_byteexact") is True
            and inspection.get("programming_receipt", {}).get("sha256") == programming["sha256"]
            and inspection.get("source_bit_sha256") == BIT_SHA
            and inspection["status"] == "PASS_WITH_LIMITS"
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
              "bit_sha256": BIT_SHA, "reference_bit_sha256": REFERENCE_BIT_SHA,
              "source_capture_schema": source["capture"]["schema"],
              "source_capture_sha256": source["source_receipt_sha256"],
              "fixed_wall_time_termination": False,
              "resume": None}

    def check_budget():
        guard()
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
        require(sha_file(args.assets) == source["source"]["host_manifest_sha256"]
                and sha_file(args.artifacts) == source["source"]["artifact_manifest_sha256"],
                "Replay model manifests differ from this fresh benchmark")
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
            require(initial_csr == inspection["csr"], "live CSR differs from this run accepted inspection")
            require(assert_snapshot(session, api, snapshot) == inspection["snapshot_sha256"],
                    "board KV changed after accepted read-only inspection")
            report["initial_full_kv_snapshot_byteexact"] = True
            store = api["FinalAssetStore"](backend, artifacts, assets)
            model = api["HostModelAdapter"](api["FinalHostAssetsModel"](assets), store)
            store.load_resident()
            rows = tuple(api["DecodeRow"](True, 1, 127) for _ in range(16))
            next_command = max(8192, initial_csr["ACK_ID"])
            next_generation = next_command

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
                host_before = [dict(dataclasses.asdict(slot), prompt=list(slot.prompt)) for slot in runtime.slots]
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
                        "full position127 token/slot commit differs from fresh benchmark")
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
                          "host_state_before_sha256": sha_bytes(json.dumps(host_before, sort_keys=True, separators=(",", ":")).encode()),
                          "host_state_after_sha256": sha_bytes(json.dumps(final, sort_keys=True, separators=(",", ":")).encode()),
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
            report["final_csr"] = csr_snapshot(session, api)
            backend.require_quiescent()
            report.update(status="COMPLETE_WITH_LIMITS", completed_windows=12,
                          independent_full_model_oracle="NOT_ESTABLISHED",
                          historical_kv_source_for_27_layers="FRESH_BENCHMARK_AND_PUBLISHED_FULL_SNAPSHOT_DIGEST")
    except BaseException as error:
        report.update(status="FAIL", error=repr(error))
        write_phase(phase_path, "failed")
        raise
    finally:
        if report["status"] == "COMPLETE_WITH_LIMITS":
            write_phase(phase_path, "complete")
        report["handles_closed"] = bool("session" in locals() and not session.handles and not session.quarantine)
        report["resources"] = guard.summary()
        save_new(out / "workload.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    source_only = commands.add_parser("verify-source")
    inspect = commands.add_parser("inspect-live")
    restore = commands.add_parser("restore")
    run = commands.add_parser("run")
    for command in (source_only, inspect, restore, run):
        command.add_argument("--main", type=Path, required=True, help="fresh public benchmark result root")
    for command in (inspect, restore, run):
        command.add_argument("--runtime-root", type=Path, required=True)
        command.add_argument("--bit-file", type=Path, required=True)
        command.add_argument("--out", type=Path, required=True)
    for command in (inspect, restore, run):
        command.add_argument("--program-receipt", type=Path, required=True)
    run.add_argument("--inspection", type=Path, required=True)
    run.add_argument("--artifacts", type=Path, required=True)
    run.add_argument("--assets", type=Path, required=True)
    run.add_argument("--sampler-jsonl", type=Path, required=True)
    run.add_argument("--sampler-ready", type=Path, required=True)
    run.add_argument("--windows-jsonl", type=Path, required=True)
    run.add_argument("--phase-path", type=Path,
                     help="optional atomic phase JSON consumed by the seven-rail sampler")
    run.add_argument("--stop-file", type=Path,
                     help="optional externally requested stop, honored at quiescent boundaries")
    args = parser.parse_args(argv)
    source = verify_source(args.main)
    if args.command == "verify-source":
        result = {"status": "PASS", "source_main_run_sha256": source["main_run_sha256"],
                  "source_capture_schema": source["capture"]["schema"],
                  "source_capture_sha256": source["source_receipt_sha256"],
                  "source_bit_sha256": source["capture"]["run_bitstream_sha256"],
                  "snapshot_sha256": source["capture"]["snapshot"]["sha256"],
                  "last_command_id": 8192, "captured_attention_layers": LAYERS,
                  "captured_mlp_layers": (0,)}
    elif args.command in ("inspect-live", "restore"):
        result = inspect_live(args, source)
    else:
        result = run_windows(args, source)
    print(json.dumps(result if args.command == "verify-source" else {
        "status": result["status"], "out": str(args.out)}, sort_keys=True))


if __name__ == "__main__":
    main()
