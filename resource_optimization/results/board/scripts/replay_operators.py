import hashlib
import json
import sys
import time
from pathlib import Path

root = Path(r"D:/ScaleLLM_final_model/dsp_all_board_20261115_001")
runtime = root / "runtime"
sys.path.insert(0, str(runtime / "project/hardware"))
sys.path.append(str(runtime / "deploy/vendor/runtime"))
from resource_guard import ResourceGuard
from scalellm_windows_xdma import WindowsXdmaSession
from host.scalellm_decode16 import KV_BASE, LAYER_STRIDE
from host.scalellm_final_abi import ATTENTION, CSR, FinalDescriptor
from host.scalellm_final_assets import FinalAssetStore
from host.scalellm_final_layout import layer_spans
from host.scalellm_final_runtime import FinalBoardBackend
from host.scalellm_mlp_gu_only_artifacts import GuOnlyArtifactManifest


def sha(data):
    return hashlib.sha256(data).hexdigest()


identity = json.loads((runtime / "candidate_source_identity.json").read_text())
for relative, expected in identity["candidate_files"].items():
    data = (runtime / relative).read_bytes()
    if len(data) != expected["bytes"] or sha(data) != expected["sha256"]:
        raise RuntimeError("Candidate runtime changed " + relative)
reference = json.loads((root / "reference/reference_manifest.json").read_text())
if reference["status"] != "PASS" or len(reference["commands"]) != 12:
    raise ValueError("Expected twelve bound operator references")
payload_root = root / "reference/payloads"
payload_root.mkdir(exist_ok=False)
for case in reference["commands"]:
    for record in case["files"].values():
        source = Path(reference["original_remote_payload_root"]) / record["file"]
        data = source.read_bytes()
        if len(data) != record["bytes"] or sha(data) != record["sha256"]:
            raise RuntimeError("Existing Dell reference changed " + record["file"])
        with (payload_root / record["file"]).open("xb") as stream:
            stream.write(data)

manifest_path = Path(r"D:/ScaleLLM_inference/artifacts_8a09c60f3256_20261025T042725/scalecode_manifest.json")
if sha(manifest_path.read_bytes()) != "45ed3c211c4939e83d5f2efc39731970692317dfa540520ca8c16e525a99e8f6":
    raise RuntimeError("Model manifest changed")
artifacts = GuOnlyArtifactManifest.load(manifest_path, verify_hashes=False)
out = root / "replay"
out.mkdir(exist_ok=False)
guard = ResourceGuard(rss_limit=8 << 30, available_floor=2 << 30)
report = {"schema": "scalellm_dsp_operator_replay_v1", "status": "RUNNING", "commands": [],
          "reference_manifest_sha256": sha((root / "reference/reference_manifest.json").read_bytes()),
          "reference": "sealed version operator reference", "command_timeout_seconds": 120,
          "transport_timeout_ms": 5000, "fixed_wall_time_termination": False,
          "asset_receipts": [], "handles_closed": False}
backend = None
session = None
started = time.monotonic()


def save():
    report["resources"] = guard.summary()
    (out / "report.json").write_text(json.dumps(report, indent=2))


def payload(case, name):
    expected = case["files"][name]
    data = (payload_root / expected["file"]).read_bytes()
    if len(data) != expected["bytes"] or sha(data) != expected["sha256"]:
        raise RuntimeError("Copied reference changed " + expected["file"])
    return data


save()
try:
    with WindowsXdmaSession(timeout_ms=5000, log_path=str(out / "xdma.jsonl")) as session:
        backend = FinalBoardBackend(session, timeout_s=120)
        store = FinalAssetStore(backend, artifacts, None)
        report["asset_receipts"] = store.receipts
        for case in reference["commands"]:
            guard()
            backend.require_quiescent()
            descriptor_bytes = payload(case, "descriptor")
            descriptor = FinalDescriptor.unpack(descriptor_bytes)
            if (descriptor.pack() != descriptor_bytes or descriptor.command_id != case["command_id"]
                    or descriptor.layer != case["layer"] or descriptor.opcode != case["opcode"]
                    or descriptor.active_mask != 0xffff
                    or any(row.position != case["kv_length"] - 1 for row in descriptor.rows)):
                raise ValueError("Sealed descriptor workload changed")
            record = {"command_id": descriptor.command_id, "layer": descriptor.layer,
                      "opcode": descriptor.opcode, "kv_length": case["kv_length"],
                      "descriptor_sha256": sha(descriptor_bytes), "status": "PREPARING", "acknowledged": False}
            report["commands"].append(record)
            save()
            spans = layer_spans(descriptor.layer)
            addresses = {"attention_c0": (0, descriptor.weight_half0),
                         "attention_c1": (0, descriptor.weight_half1),
                         "attention_meta": (0, descriptor.metadata_base)} if descriptor.opcode == ATTENTION else {
                         "mlp_gate_up_c0": (1, descriptor.weight_half0),
                         "mlp_gate_up_c1": (1, descriptor.weight_half1),
                         "mlp_gate_meta": (1, descriptor.metadata_base)}
            for name, expected in case["scale_assets"].items():
                backend.require_quiescent()
                data = artifacts.original.layer_artifact(descriptor.layer, name).read_verified()
                if sha(data) != expected["sha256"]:
                    raise RuntimeError("Sealed scale asset differs " + name)
                channel, address = addresses[name]
                if name in spans and (spans[name].channel != channel or spans[name].address != address
                                      or spans[name].size != len(data)):
                    raise RuntimeError("Scale asset address differs from existing layout")
                store._write(channel, address, data, f"cmd{descriptor.command_id}/{name}")
                guard()
            if descriptor.opcode == ATTENTION:
                kv = payload(case, "kv_before")
                if len(kv) != LAYER_STRIDE:
                    raise ValueError("Captured KV must cover exactly one existing layer span")
                backend.require_quiescent()
                store._write(0, KV_BASE + descriptor.layer * LAYER_STRIDE, kv,
                             f"cmd{descriptor.command_id}/kv_before")
                store._write(0, descriptor.rope_base, payload(case, "rope"),
                             f"cmd{descriptor.command_id}/rope")
            expected_output = payload(case, "output")

            def validate_output(completed, observed):
                (out / f"cmd_{completed.command_id:04d}_output.bin").write_bytes(observed)
                completion = [session.read32(CSR["COMPLETION_DESCRIPTOR"] + 4 * word) for word in range(64)]
                record.update(status="COMPARED", byte_exact=observed == expected_output,
                              expected_sha256=sha(expected_output), actual_sha256=sha(observed), bytes=len(observed),
                              completion_words=completion, submitted_words=list(completed.words()),
                              done_before_ack={name: session.read32(CSR[name]) for name in
                                               ("STATUS", "ADMISSION_ERROR", "DONE_ERROR", "DONE_INPUT_BYTES", "DONE_OUTPUT_BYTES", "DONE_CYCLES")})
                save()
                if observed != expected_output:
                    record["status"] = "FAIL"
                    save()
                    raise AssertionError("Operator output mismatch, completion retained " + str(completed.command_id))

            record["status"] = "RUNNING"
            save()
            output = backend.run(descriptor, payload(case, "input"), validate_output=validate_output)
            backend.require_quiescent()
            record.update(status="PASS", acknowledged=True, receipt=backend.receipts[-1],
                          final_csr={name: session.read32(CSR[name]) for name in ("STATUS", "ADMISSION_ERROR", "DONE_ERROR")})
            if any(record["final_csr"].values()) or backend.pending is not None:
                raise RuntimeError("Operator ACK did not leave clean idle state")
            save()
            print(json.dumps({key: record[key] for key in ("command_id", "layer", "opcode", "kv_length", "status", "byte_exact", "actual_sha256", "receipt")}), flush=True)
        backend.require_quiescent()
        report.update(status="PASS", final_quiescent=True, seconds=time.monotonic() - started)
except BaseException as error:
    report.update(status="FAIL", error=repr(error), pending_descriptor=None if backend is None or backend.pending is None else list(backend.pending.words()))
    raise
finally:
    report["handles_closed"] = bool(session is not None and not session.handles and not session.quarantine)
    save()
print(json.dumps({"status": report["status"], "commands": len(report["commands"]), "handles_closed": report["handles_closed"]}), flush=True)
