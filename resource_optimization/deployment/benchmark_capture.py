"""Capture a fresh public KV128 benchmark and compare published references.

The 256 MiB KV image is generated on the user's board. It is not downloaded
from an author-specific directory. No model math or command submission occurs
in these hooks: the checked deployment runner owns both.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
import struct
import time

ROOT = Path(__file__).resolve().parents[1]
BIT_SHA = "5d78519aa10695be564f668d5a41a0e5554e282c31d39f648534a7dc01ab72f7"
SNAPSHOT_SHA = "fa610d68fab6045573a355313f78808c93b7273dbf1edc2e8f61bc3ea1ad81c8"
LAYER_BYTES = 8 << 20
LAYERS = (0, 8, 16, 24, 31)
TARGETS = {64 * (position - 1) + 2 * layer + 1: (position, layer, 1)
           for position in (32, 128) for layer in LAYERS}
TARGETS.update({64 * (position - 1) + 2: (position, 0, 2)
                for position in (32, 128)})


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def save_new(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


class BenchmarkCapture:
    def __init__(self, output):
        self.output = Path(output).resolve()
        self.directory = self.output / "captures"
        self.directory_created = False
        self.before = {}
        self.after = {}
        self.commands = 0
        self.last_descriptor = None
        self.last_receipt = None
        self.pending = None
        self.pre_last_slots = None
        self.post_last_slots = None
        self.snapshot = None
        self.failure = None
        self.token_reference_path = ROOT.parent / "docs/evidence/kv128_chat16/results/tokens.json"
        self.operator_reference_path = ROOT / "results/board/replay/report.json"
        self.reference_files = {
            path.relative_to(ROOT.parent).as_posix(): {"sha256": sha(path), "bytes": path.stat().st_size}
            for path in (self.token_reference_path, self.operator_reference_path)
        }
        tokens = json.loads(self.token_reference_path.read_text())
        operators = json.loads(self.operator_reference_path.read_text())
        require(tokens["actual_generated_tokens"] == 1784, "Published KV128 token reference differs")
        require(operators["status"] == "PASS", "Published operator reference is not accepted")
        self.tokens = tokens["slots"]
        self.expected_outputs = {record["command_id"]: record for record in operators["commands"]}
        require(set(self.expected_outputs) == set(TARGETS), "Published 12-command reference set differs")

    def ensure_directory(self):
        if not self.directory_created:
            require(self.output.is_dir(), "Runner must create the new result directory first")
            self.directory.mkdir(exist_ok=False)
            self.directory_created = True

    def write_bytes(self, name, data):
        self.ensure_directory()
        path = self.directory / name
        with path.open("xb") as stream:
            stream.write(data)
        return {"file": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

    def before_command(self, backend, descriptor, payload):
        cid = descriptor.command_id
        require(self.pending is None and cid == self.commands + 1, "Benchmark command ordering differs")
        position, within = divmod(cid - 1, 64)
        layer, opcode = within // 2, 1 + within % 2
        words = list(descriptor.words())
        require((descriptor.layer, descriptor.opcode, descriptor.active_mask) == (layer, opcode, 0xffff)
                and position < 128
                and all(words[32 + 2 * s:34 + 2 * s] == [position, 1] for s in range(16)),
                "Benchmark must keep all 16 original slots active through position127")
        self.pending = {"command_id": cid, "descriptor_words": words,
                        "input_sha256": hashlib.sha256(payload).hexdigest(),
                        "begin_monotonic_ns": time.monotonic_ns()}
        if cid not in TARGETS:
            return
        from host.scalellm_final_layout import KV_BASE, ROPE_BASE, ROPE_BYTES
        backend.require_quiescent()
        prefix = f"cmd_{cid:04d}"
        files = {"input": self.write_bytes(prefix + "_input.bin", payload),
                 "descriptor": self.write_bytes(prefix + "_descriptor.bin", struct.pack("<64I", *words))}
        if opcode == 1:
            kv = backend.session.c2h_read_local(0, LAYER_BYTES, KV_BASE + layer * LAYER_BYTES, 1 << 20)
            require(len(kv) == LAYER_BYTES, "Short KV capture before Attention")
            files["kv_before"] = self.write_bytes(prefix + "_kv_before.bin", kv)
            rope = backend.session.c2h_read_local(0, ROPE_BYTES, ROPE_BASE, 1 << 20)
            require(len(rope) == ROPE_BYTES, "Short RoPE capture")
            files["rope"] = self.write_bytes(prefix + "_rope.bin", rope)
        self.before[cid] = {"command_id": cid, "round": position + 1,
                            "layer": layer, "opcode": opcode, "files": files}

    def after_command(self, backend, descriptor, payload, output):
        cid = descriptor.command_id
        require(self.pending is not None and self.pending["command_id"] == cid,
                "Command completion without matching start")
        require(backend.pending is None and backend.receipts[-1]["command_id"] == cid,
                "Completion hook must follow successful output validation and ACK")
        backend.require_quiescent()
        receipt = dict(backend.receipts[-1])
        record = dict(self.pending, output_sha256=hashlib.sha256(output).hexdigest(),
                      completed_monotonic_ns=time.monotonic_ns(),
                      completion_receipt=receipt, acknowledged=True)
        with (self.output / "benchmark_commands.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
        self.commands += 1
        self.last_descriptor = self.pending["descriptor_words"]
        self.last_receipt = receipt
        self.pending = None
        if cid in TARGETS:
            expected = self.expected_outputs[cid]
            entry = self.write_bytes(f"cmd_{cid:04d}_output.bin", output)
            self.after[cid] = {"command_id": cid, "output": entry, "reference_match": False}
            require(len(output) == expected["bytes"] and entry["sha256"] == expected["expected_sha256"],
                    f"Output differs from the published operator reference: command {cid}")
            self.after[cid]["reference_match"] = True

    def before_step(self, runtime, step_index):
        self.ensure_directory()
        require(step_index < 128 and self.commands == step_index * 64,
                "Unexpected benchmark step count")
        if step_index == 127:
            self.pre_last_slots = json.loads(json.dumps([dataclasses.asdict(s) for s in runtime.slots]))

    def after_step(self, runtime, step_index, emitted):
        require(self.commands == (step_index + 1) * 64 and self.pending is None,
                "Step committed before all commands completed")
        if step_index != 127:
            return
        require(set(emitted) == set(range(16)), "Final step did not emit all 16 tokens")
        for index, state in enumerate(runtime.slots):
            expected = self.tokens[str(index)]
            require(list(state.prompt) == expected["prompt_token_ids"]
                    and state.generated == expected["generated_token_ids"]
                    and state.position == 128 and state.finished and state.epoch == 1,
                    f"Full KV128 token/state mismatch in slot {index}")
        self.post_last_slots = json.loads(json.dumps([dataclasses.asdict(s) for s in runtime.slots]))
        from host.scalellm_final_layout import KV_BASE
        path = self.directory / "kv_snapshot.bin"
        digest = hashlib.sha256()
        layers = []
        with path.open("xb") as stream:
            for layer in range(32):
                runtime.backend.require_quiescent()
                data = runtime.backend.session.c2h_read_local(0, LAYER_BYTES,
                                                              KV_BASE + layer * LAYER_BYTES, 1 << 20)
                require(len(data) == LAYER_BYTES, f"Short full-snapshot read at layer {layer}")
                stream.write(data)
                digest.update(data)
                layers.append({"layer": layer, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        self.snapshot = {"file": path.name, "bytes": path.stat().st_size,
                         "sha256": digest.hexdigest(), "layers": layers,
                         "generated_from_this_run": True, "reference_match": digest.hexdigest() == SNAPSHOT_SHA}
        require(self.snapshot["bytes"] == 32 * LAYER_BYTES and self.snapshot["reference_match"],
                "Fresh full KV image differs from the published power experiment snapshot identity")

    def finalize(self, report):
        complete = (report.get("execution") == "COMPLETE" and report.get("handles_closed")
                    and report.get("final_quiescent") and self.commands == 8192
                    and len(report.get("steps", [])) == 128 and set(self.after) == set(TARGETS)
                    and self.snapshot is not None and self.snapshot["reference_match"])
        for relative, identity in self.reference_files.items():
            require(sha(ROOT.parent / relative) == identity["sha256"], "Reference changed during benchmark")
        result = {"schema": "scalellm_portable_kv128_capture_v1",
                  "status": "PASS" if complete else "INCOMPLETE",
                  "run_bitstream_sha256": BIT_SHA,
                  "reference_scope": "Regression against published tokens, 12 operator outputs and sealed full-KV digest; not an independent whole-model mathematical oracle",
                  "source_references": self.reference_files, "commands_completed": self.commands,
                  "native_runner_execution": report.get("execution"),
                  "handles_closed": report.get("handles_closed"),
                  "final_quiescent": report.get("final_quiescent"),
                  "targets_before": list(self.before.values()), "targets_after": list(self.after.values()),
                  "host_before_last_step": self.pre_last_slots, "host_after_last_step": self.post_last_slots,
                  "last_descriptor": self.last_descriptor, "last_completion": self.last_receipt,
                  "snapshot": self.snapshot,
                  "command_journal_sha256": sha(self.output / "benchmark_commands.jsonl")
                  if (self.output / "benchmark_commands.jsonl").exists() else None}
        save_new(self.output / "benchmark_capture.json", result)
        if report.get("execution") == "COMPLETE":
            require(complete, "Incomplete benchmark capture despite model completion")


def create_hooks(output):
    from final.run import RunHooks
    capture = BenchmarkCapture(output)
    return RunHooks(before_command=capture.before_command, after_command=capture.after_command,
                    before_step=capture.before_step, after_step=capture.after_step, finalize=capture.finalize)
