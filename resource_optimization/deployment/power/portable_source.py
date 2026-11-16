"""Offline validation of fresh public KV128 captures for seven-rail replay."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "project/hardware"))
from host.scalellm_final_abi import FinalDescriptor
from deploy.final.common import CHECKPOINT_SHA, profile_identity
from deploy.final.execution import (BENCHMARK_KV128, ORIGINAL_REQUESTS_SHA,
                                    benchmark_requests, policy_description,
                                    validate_benchmark_report)

BIT_SHA = "5d78519aa10695be564f668d5a41a0e5554e282c31d39f648534a7dc01ab72f7"
SNAPSHOT_SHA = "fa610d68fab6045573a355313f78808c93b7273dbf1edc2e8f61bc3ea1ad81c8"
LAYER_BYTES = 8 << 20
KV_BYTES = 32 * LAYER_BYTES
LAYERS = (0, 8, 16, 24, 31)
TARGET_IDS = {64 * (step - 1) + 2 * layer + 1: (step, layer, 1)
              for step in (32, 128) for layer in LAYERS}
TARGET_IDS.update({64 * (step - 1) + 2: (step, 0, 2) for step in (32, 128)})
REFERENCES = {
    "docs/evidence/kv128_chat16/results/tokens.json": "1def7959d5e8058aa729060770e40efc4e47c9a3e64e70777624b72c78648090",
    "resource_optimization/results/board/replay/report.json": "3061e8b6302720538c7955f8e412b9fa1a15b0014e3ec7ff2163006369d50f7a",
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def checked_file(root, entry):
    require(set(entry) >= {"file", "bytes", "sha256"}, "Capture metadata incomplete")
    relative = Path(entry["file"])
    require(not relative.is_absolute() and len(relative.parts) == 1,
            "Capture filename must remain in the fresh captures directory")
    path = (root / relative).resolve(strict=True)
    require(path.parent == root.resolve() and path.is_file()
            and path.stat().st_size == entry["bytes"] and sha_file(path) == entry["sha256"],
            "Fresh capture bytes/identity differ: " + str(path))
    return path


def descriptor_check(words, cid):
    position, within = divmod(cid - 1, 64)
    layer, opcode = within // 2, 1 + within % 2
    require(isinstance(words, (tuple, list)) and len(words) == 64
            and all(type(word) is int and 0 <= word < 2**32 for word in words)
            and list(words[2:8]) == [cid, position, opcode, layer, 65535, cid]
            and all(list(words[32 + 2 * slot:34 + 2 * slot]) == [position, 1]
                    for slot in range(16)), "Fresh benchmark descriptor differs at command " + str(cid))
    FinalDescriptor.unpack(struct.pack("<64I", *words))


def unique_by_command(entries, label):
    result = {entry["command_id"]: entry for entry in entries}
    require(len(result) == len(entries) and set(result) == set(TARGET_IDS), label + " capture set differs")
    return result


def validate_program_identity(receipt):
    """Validate an evidence record offline, preserving its original host/boot."""
    require(receipt.get("schema") == "scalellm_sram_program_receipt_v1"
            and receipt.get("execution") == "COMPLETE"
            and type(receipt.get("returncode")) is int and receipt["returncode"] == 0
            and receipt.get("deployment_profile") == profile_identity("all-dsp")
            and receipt.get("volatile_sram") is True, "Programming evidence identity/status differs")
    host = receipt.get("host_identity", {})
    require(isinstance(host.get("hostname"), str) and host["hostname"]
            and host["hostname"] == host["hostname"].casefold()
            and host.get("platform") == "win32"
            and host.get("boot_source") == "Win32_OperatingSystem.LastBootUpTime.UTC"
            and isinstance(host.get("boot_id"), str)
            and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{7}Z", host["boot_id"]),
            "Programming evidence host/boot identity missing or invalid")


def verify_portable_source(main):
    """Validate local files and published references without opening a device."""
    main = Path(main).resolve(strict=True)
    run = load(main / "run.json")
    capture = load(main / "benchmark_capture.json")
    source = load(main / "benchmark_source.json")
    requests = load(main / "requests.json")
    profile = profile_identity("all-dsp")
    policy = policy_description(BENCHMARK_KV128)
    require(run.get("execution") == "COMPLETE" and run.get("handles_closed") is True
            and run.get("final_quiescent") is True and run.get("checkpoint_sha256") == CHECKPOINT_SHA,
            "Fresh benchmark did not close and commit successfully")
    require(source.get("schema") == "scalellm_portable_kv128_source_v1"
            and source.get("original_requests_sha256") == ORIGINAL_REQUESTS_SHA
            and source.get("deployment_profile") == run.get("deployment_profile") == profile
            and source.get("execution_policy") == run.get("execution_policy") == policy
            and run.get("bitstream_file", {}).get("sha256") == BIT_SHA
            and run.get("bitstream_file", {}).get("bytes") == profile["bit_bytes"],
            "Fresh benchmark source/profile/policy identity differs")
    require(requests == run.get("requests") == benchmark_requests()
            and source.get("benchmark_requests_sha256") == run.get("requests_sha256")
            == sha_file(main / "requests.json"), "Fresh fixed 16-request identity differs")
    for name in ("source_manifest_sha256", "artifact_manifest_sha256", "host_manifest_sha256"):
        require(source.get(name) == run.get(name) and isinstance(source.get(name), str)
                and len(source[name]) == 64, "Fresh runtime/model manifest identity differs: " + name)
    require(source["source_manifest_sha256"] == sha_file(ROOT / "deploy/vendor_manifest.json"),
            "Fresh benchmark runtime source differs from this public checkout")
    programming = run.get("programming_receipt")
    require(isinstance(programming, dict) and isinstance(programming.get("sha256"), str)
            and re.fullmatch(r"[0-9a-f]{64}", programming["sha256"])
            and isinstance(programming.get("receipt"), dict), "Fresh benchmark programming provenance missing")
    validate_program_identity(programming["receipt"])
    validate_benchmark_report(run)
    require(capture.get("schema") == "scalellm_portable_kv128_capture_v1"
            and capture.get("status") == "PASS" and capture.get("run_bitstream_sha256") == BIT_SHA
            and capture.get("commands_completed") == 8192
            and capture.get("native_runner_execution") == "COMPLETE"
            and capture.get("handles_closed") is True and capture.get("final_quiescent") is True,
            "Fresh public capture was not accepted")
    require(set(capture.get("source_references", {})) == set(REFERENCES), "Published reference set differs")
    for relative, expected in REFERENCES.items():
        path = ROOT / relative
        require(sha_file(path) == expected
                and capture["source_references"][relative] == {"sha256": expected, "bytes": path.stat().st_size},
                "Published reference identity differs: " + relative)
    tokens = load(ROOT / next(iter(REFERENCES)))["slots"]
    require(sum(len(row["generated_token_ids"]) for row in tokens.values()) == 1784,
            "Published token count differs")
    for slot in range(16):
        require(run["outputs"][str(slot)] == tokens[str(slot)]["generated_token_ids"]
                and requests[slot]["prompt_token_ids"] == tokens[str(slot)]["prompt_token_ids"],
                "Fresh generated tokens differ from published reference in slot " + str(slot))
    for index, step in enumerate(run["steps"]):
        expected_emitted = {}
        for slot, (state, request) in enumerate(zip(step["slots"], requests)):
            expected_tokens = tokens[str(slot)]["generated_token_ids"]
            count = max(0, index + 2 - len(request["prompt_token_ids"]))
            require(state.get("prompt") == request["prompt_token_ids"]
                    and state.get("max_new_tokens") == request["max_new_tokens"]
                    and state.get("generated") == expected_tokens[:count]
                    and state.get("finished") is (index == 127),
                    f"Fresh committed host prompt/budget/token prefix differs at step {index}, slot {slot}")
            if count:
                expected_emitted[str(slot)] = expected_tokens[count - 1]
        require(step.get("emitted") == expected_emitted,
                "Fresh atomic host token commit differs at step " + str(index))
    require(capture.get("host_before_last_step") == run["steps"][126]["slots"]
            and capture.get("host_after_last_step") == run["steps"][127]["slots"],
            "Fresh final host-state capture differs from committed steps")
    before = unique_by_command(capture["targets_before"], "Before")
    after = unique_by_command(capture["targets_after"], "After")
    expected_outputs = {row["command_id"]: row for row in load(ROOT / list(REFERENCES)[1])["commands"]}
    targets = {}
    for cid, (step, layer, opcode) in TARGET_IDS.items():
        entry = before[cid]
        require((entry["round"], entry["layer"], entry["opcode"]) == (step, layer, opcode),
                "Fresh target round/layer/opcode differs")
        names = {"input", "descriptor", "kv_before", "rope"} if opcode == 1 else {"input", "descriptor"}
        require(set(entry["files"]) == names and after[cid].get("reference_match") is True,
                "Fresh target file set/comparison differs")
        files = {name: checked_file(main / "captures", identity)
                 for name, identity in dict(entry["files"], output=after[cid]["output"]).items()}
        require(files["descriptor"].stat().st_size == 256
                and files["input"].stat().st_size == 196608,
                "Fresh target input/descriptor byte count differs")
        words = struct.unpack("<64I", files["descriptor"].read_bytes())
        descriptor_check(words, cid)
        expected = expected_outputs[cid]
        require(files["output"].stat().st_size == expected["bytes"]
                and sha_file(files["output"]) == expected["expected_sha256"],
                "Fresh target output differs from published reference")
        if opcode == 1:
            require(files["kv_before"].stat().st_size == LAYER_BYTES
                    and files["rope"].stat().st_size == 8192, "Fresh target KV/RoPE size differs")
        targets[cid] = files
    journal = main / "benchmark_commands.jsonl"
    require(sha_file(journal) == capture["command_journal_sha256"], "Fresh command journal changed")
    count, previous_end = 0, 0
    with journal.open(encoding="utf-8-sig") as stream:
        for line in stream:
            row = json.loads(line)
            count += 1
            cid = row.get("command_id")
            require(type(cid) is int and cid == count and count <= 8192 and row.get("acknowledged") is True,
                    "Fresh command ordering/ACK differs")
            descriptor_check(row.get("descriptor_words"), cid)
            receipt = row.get("completion_receipt")
            require(receipt == run["receipts"][cid - 1]
                    and type(receipt.get("cycles")) is int and 0 < receipt["cycles"] < 2**32
                    and type(row.get("begin_monotonic_ns")) is int
                    and type(row.get("completed_monotonic_ns")) is int
                    and previous_end <= row["begin_monotonic_ns"] < row["completed_monotonic_ns"],
                    "Fresh ACK receipt/cycles/timing differs")
            previous_end = row["completed_monotonic_ns"]
            if cid in targets:
                require(row["input_sha256"] == sha_file(targets[cid]["input"])
                        and row["output_sha256"] == sha_file(targets[cid]["output"])
                        and row["descriptor_words"] == list(struct.unpack("<64I", targets[cid]["descriptor"].read_bytes())),
                        "Fresh journal/target payloads differ")
    require(count == 8192 and capture.get("last_descriptor") == row["descriptor_words"]
            and capture.get("last_completion") == row["completion_receipt"],
            "Fresh benchmark last completion/count differs")
    snapshot = capture["snapshot"]
    require(snapshot.get("bytes") == KV_BYTES and snapshot.get("sha256") == SNAPSHOT_SHA
            and snapshot.get("generated_from_this_run") is True and snapshot.get("reference_match") is True,
            "Fresh snapshot provenance/full digest differs")
    snapshot_file = checked_file(main / "captures", snapshot)
    require(len(snapshot["layers"]) == 32, "Fresh snapshot layer identity incomplete")
    with snapshot_file.open("rb") as stream:
        for layer, identity in enumerate(snapshot["layers"]):
            data = stream.read(LAYER_BYTES)
            require(identity == {"layer": layer, "bytes": LAYER_BYTES, "sha256": hashlib.sha256(data).hexdigest()},
                    "Fresh snapshot layer hash differs at layer " + str(layer))
    return {"main": main, "run": run, "capture": dict(capture, checkpoint_sha256=CHECKPOINT_SHA),
            "source": source, "requests": requests, "targets": targets,
            "snapshot": snapshot_file, "last_descriptor": tuple(capture["last_descriptor"]),
            "main_run_sha256": sha_file(main / "run.json"),
            "source_receipt_sha256": sha_file(main / "benchmark_capture.json")}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main", type=Path, required=True)
    parser.add_argument("--program-receipt", type=Path)
    args = parser.parse_args()
    result = verify_portable_source(args.main)
    if args.program_receipt is not None:
        validate_program_identity(load(args.program_receipt))
    print(json.dumps({"status": "PASS", "source_main_run_sha256": result["main_run_sha256"],
                      "source_capture_sha256": result["source_receipt_sha256"],
                      "source_bit_sha256": BIT_SHA, "commands": 8192, "tokens": 1784,
                      "snapshot_sha256": SNAPSHOT_SHA}))


if __name__ == "__main__":
    main()
