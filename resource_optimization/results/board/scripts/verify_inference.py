import argparse
from datetime import datetime
import hashlib
import json
import struct
from pathlib import Path


def digest(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(1 << 20), b""):
            hasher.update(data)
    return hasher.hexdigest()


def word_hash(value):
    return hashlib.sha256(struct.pack("<I", value)).hexdigest()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--board-test-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.board_test_root.resolve()
    inference = root / "inference"
    requests_path = args.repository_root / "examples/requests16.json"
    golden_path = args.repository_root / "docs/evidence/inference_chat16/outputs.json"
    require(digest(requests_path) == "9d0db082e3504b2077971f0a3a1370f70c27474dd746dc7309ebca6c818444ed", "Original requests changed")
    require(digest(golden_path) == "975c342521ebe538da25cf9d52426c7a65c57632fa256375c2930ce26e04a034", "Original output reference changed")
    requests = json.loads(requests_path.read_text())
    golden = {entry["slot"]: entry for entry in json.loads(golden_path.read_text())}
    report = json.loads((inference / "run.json").read_text())
    process = json.loads((root / "environment/inference_process_receipt.json").read_text(encoding="utf-8-sig"))
    launch = json.loads((root / "environment/inference_launch.json").read_text())
    owned_tree = json.loads((root / "environment/inference_owned_tree.json").read_text(encoding="utf-8-sig"))
    process_roots = [entry for entry in owned_tree if entry["pid"] == launch["pid"]]
    require(len(process_roots) == 1 and process["pid"] == launch["pid"]
            and process["birth"] == process_roots[0]["birth"], "Native exit receipt does not belong to the current inference process")
    started_utc = datetime.fromisoformat(process["started_utc"].replace("Z", "+00:00"))
    birth_utc = datetime.fromisoformat(process["birth"].replace("Z", "+00:00"))
    finished_utc = datetime.fromisoformat(process["finished_utc"].replace("Z", "+00:00"))
    require(started_utc <= birth_utc <= finished_utc, "Native process timestamps are inconsistent")
    native_wall_seconds = (finished_utc - started_utc).total_seconds()
    tokenizer = json.loads((root / "runtime/tokenizer_metadata.json").read_text())
    eos_ids = set(tokenizer["eos_token_ids"])
    require(process["exitcode"] == 0, "Native inference process failed")
    require(report["execution"] == "COMPLETE" and report["handles_closed"] is True
            and report["final_quiescent"] is True, "Inference did not finish with closed handles and idle board")
    require(report["final_status"] == {"STATUS": 0, "ADMISSION_ERROR": 0, "DONE_ERROR": 0}, "Final CSR is not clean")
    require(report["requests"] == requests and len(requests) == 16, "Request identity/count differs")
    require(report["checkpoint_sha256"] == "8a09c60f3256779c16925f8209c9399ba4a1ee0406caf65bd2637ffd99287d6d", "Checkpoint differs")
    require(report["cache_integrity"] == "full startup hashes" and report["prepared_config_sha256"] is None, "Full startup verification was bypassed")
    require(report["wall_limit_seconds"] is None and report["fixed_wall_time_termination"] is False, "Whole-run stopping remains enabled")
    require(len(report["steps"]) == 50 and len(report["receipts"]) == 3200, "Expected 50 complete rounds and 3200 commands")
    require(len(report["slots"]) == 16 and set(report["outputs"]) == {str(i) for i in range(16)}, "Final slots are incomplete")
    final_positions = [50, 49, 48, 49, 47, 48, 50, 49, 48, 47, 48, 50, 49, 48, 48, 48]
    outputs = []
    slot_checks = []
    for request in requests:
        slot = request["slot"]
        state = report["slots"][slot]
        expected = golden[slot]
        generated = report["outputs"][str(slot)]
        require(request["max_new_tokens"] == 32 and generated == expected["generated_token_ids"], f"Generated tokens differ in slot {slot}")
        require(state["generated"] == generated and len(generated) == 32, f"Slot {slot} final token commit differs")
        require(state["position"] == final_positions[slot] == expected["position"], f"Slot {slot} final position differs")
        require(state["prompt"] == request["prompt_token_ids"] and state["finished"] is True and state["epoch"] > 0, f"Slot {slot} ownership/state differs")
        require(not any(token in eos_ids for token in generated) and report["decoded"][str(slot)]["eos"] is False, f"Slot {slot} EOS semantics differ")
        decoded = report["decoded"][str(slot)]["generated"]
        require(decoded == expected["generated_text"] and expected["stop_reason"] == "length_limit", f"Slot {slot} decoded output/stop differs")
        outputs.append(dict(slot=slot, prompt=expected["prompt"], generated_token_ids=generated,
                            generated_text=decoded, new_tokens=len(generated), stop_reason="length_limit",
                            position=state["position"], epoch=state["epoch"]))
        slot_checks.append(dict(slot=slot, status="PASS", generated_tokens=32, position=state["position"], stop_reason="length_limit"))

    for round_index, step in enumerate(report["steps"]):
        require(step["index"] == round_index and len(step["slots"]) == 16, "Round index/state count differs")
        expected_emitted = {}
        for request in requests:
            slot = request["slot"]
            state = step["slots"][slot]
            count = max(0, min(32, round_index + 2 - len(request["prompt_token_ids"])))
            require(state["position"] == min(round_index + 1, final_positions[slot]), f"Position commit differs at round {round_index + 1}, slot {slot}")
            require(state["generated"] == golden[slot]["generated_token_ids"][:count], f"Token prefix differs at round {round_index + 1}, slot {slot}")
            require(state["finished"] == (count == 32) and state["epoch"] == report["slots"][slot]["epoch"], "Finished/epoch lifecycle differs")
            if len(request["prompt_token_ids"]) <= round_index + 1 <= final_positions[slot]:
                expected_emitted[str(slot)] = golden[slot]["generated_token_ids"][count - 1]
        require(step["emitted"] == expected_emitted, f"Atomic emitted set differs at round {round_index + 1}")

    begins = []
    completes = []
    commits = []
    pending = None
    with (inference / "progress.jsonl").open() as stream:
        for line in stream:
            event = json.loads(line)
            if event["event"] == "command_begin":
                require(pending is None, "Overlapping software submissions")
                pending = event["command_id"]
                begins.append(event)
            elif event["event"] == "command_complete":
                require(pending == event["command_id"], "Software completion identity differs")
                pending = None
                completes.append(event)
            elif event["event"] == "position_committed":
                require(pending is None and len(completes) == 64 * (len(commits) + 1), "Position committed before all 64 commands completed")
                commits.append(event)
    require(pending is None and len(begins) == len(completes) == 3200 and len(commits) == 50, "Software command/commit coverage differs")
    for index, (begin, complete, receipt) in enumerate(zip(begins, completes, report["receipts"])):
        cid = index + 1
        round_index, within_round = divmod(index, 64)
        layer, operation = divmod(within_round, 2)
        words = begin["descriptor_words"]
        mask = sum(1 << slot for slot in range(16) if round_index < final_positions[slot])
        require(begin["command_id"] == complete["command_id"] == receipt["command_id"] == cid, "Command sequence differs")
        require(words[2:8] == [cid, round_index, operation + 1, layer, mask, cid], f"Descriptor command/layer/generation differs for {cid}")
        require(words[16] == round_index * 32 + layer + 1, f"Weight owner differs for {cid}")
        for slot in range(16):
            expected_row = [round_index, report["slots"][slot]["epoch"]] if mask & (1 << slot) else [0, 0]
            require(words[32 + slot * 2:34 + slot * 2] == expected_row, f"Descriptor row ownership differs for {cid}, slot {slot}")
        require(receipt["layer"] == layer and receipt["opcode"] == operation + 1 and receipt["active_mask"] == mask
                and receipt["cycles"] > 0 and complete["cycles"] == receipt["cycles"], f"Receipt differs for {cid}")
    for index, commit in enumerate(commits):
        state = report["steps"][index]
        require(commit["positions"] == [slot["position"] for slot in state["slots"]]
                and commit["generated_each_slot"] == [len(slot["generated"]) for slot in state["slots"]], "Progress commit differs from saved state")
        require(state["fpga_cycles"] == commit["fpga_cycles"] == sum(item["cycles"] for item in report["receipts"][index * 64:(index + 1) * 64]), "Round FPGA cycle totals differ")

    reference_path = root / "reference/reference_manifest.json"
    reference = json.loads(reference_path.read_text())
    selected_trace = []
    for case in reference["commands"]:
        if case["kv_length"] != 32:
            continue
        index = case["command_id"] - 1
        begin, complete = begins[index], completes[index]
        selected_trace.append(dict(command_id=case["command_id"],
                                   active_mask=begin["descriptor_words"][6],
                                   expected_input_sha256=case["files"]["input"]["sha256"],
                                   actual_input_sha256=begin["input_sha256"],
                                   expected_output_sha256=case["files"]["output"]["sha256"],
                                   actual_output_sha256=complete["output_sha256"],
                                   input_exact=begin["input_sha256"] == case["files"]["input"]["sha256"],
                                   output_exact=complete["output_sha256"] == case["files"]["output"]["sha256"]))
    require(len(selected_trace) == 6, "Expected six selected KV32 trace references")
    for item in selected_trace:
        item["mismatches"] = []
        if not item["input_exact"]:
            item["mismatches"].append("INPUT_HASH_MISMATCH")
        if not item["output_exact"]:
            item["mismatches"].append("OUTPUT_HASH_MISMATCH")
        if item["active_mask"] != 0xffff:
            item["mismatches"].append("ACTIVE_MASK_MISMATCH")
    selected_trace_status = "HASH_MISMATCH" if any(item["mismatches"] for item in selected_trace) else "PASS"

    descriptor_writes = []
    last_dma_writes = {}
    pending = None
    completed_commands = 0
    opens = closes = io_records = 0
    with (inference / "xdma.jsonl").open() as stream:
        for line in stream:
            event = json.loads(line)
            operation = event.get("operation")
            if operation == "open":
                opens += 1
                require(event["share_mode"] == 0 and event["timeout_ms"] == 5000, "Transport ownership/timeout differs")
            elif operation == "close":
                closes += 1
                require(event["quarantined_requests"] == 0, "Transport closed with quarantined requests")
            elif operation in ("read", "write"):
                io_records += 1
                require(event["completed"] == event["size"], "Transport completed a short operation")
                node, offset, size, observed_hash = event["node"], event["offset"], event["size"], event["sha256"]
                if operation == "write" and node == "h2c_0":
                    require(pending is None, "DDR input/asset write occurred while command pending")
                    last_dma_writes[(offset, size)] = observed_hash
                elif operation == "write" and node == "user" and 1024 <= offset < 1280:
                    require(pending is None and size == 4, "Descriptor mutated while command pending")
                    descriptor_writes.append((offset, observed_hash))
                elif operation == "write" and node == "user" and offset == 32:
                    if observed_hash == word_hash(1):
                        require(pending is None and completed_commands < 3200, "Overlapping or extra hardware START")
                        begin = begins[completed_commands]
                        words = begin["descriptor_words"]
                        require(descriptor_writes == [(1024 + 4 * i, word_hash(word)) for i, word in enumerate(words)], "Hardware submitted descriptor differs from software")
                        input_address = (0 if words[4] == 1 else 0x80000000) + words[8]
                        require(last_dma_writes.get((input_address, words[10])) == begin["input_sha256"], "Hardware staged input differs from software")
                        descriptor_writes = []
                        pending = dict(words=words, completions=[], output=False, ack_id=False, done={})
                    elif observed_hash == word_hash(2):
                        require(pending is not None and pending["ack_id"] and pending["output"], "ACK precedes completed output identity")
                        words = pending["words"]
                        require(pending["completions"] == [(1280 + 4 * i, word_hash(word)) for i, word in enumerate(words)] * 2, "Two full completion descriptor snapshots differ")
                        expected_done = {44: 0, 48: 0, 52: words[10], 56: words[11], 60: report["receipts"][completed_commands]["cycles"]}
                        require(pending["done"] == {offset: word_hash(value) for offset, value in expected_done.items()}, "Hardware completion errors/counts/cycles differ")
                        pending = None
                        completed_commands += 1
                    else:
                        raise AssertionError("Unexpected hardware action")
                elif pending is not None and node == "user" and operation == "read" and 1280 <= offset < 1536:
                    pending["completions"].append((offset, observed_hash))
                elif pending is not None and node == "user" and operation == "read" and offset in (44, 48, 52, 56, 60):
                    pending["done"][offset] = observed_hash
                elif pending is not None and node == "user" and operation == "write" and offset == 40:
                    require(observed_hash == word_hash(pending["words"][2]), "Hardware ACK ID differs")
                    pending["ack_id"] = True
                elif pending is not None and node == "c2h_0" and operation == "read":
                    words = pending["words"]
                    expected_address = (0 if words[4] == 1 else 0x80000000) + words[9]
                    require(not pending["output"] and offset == expected_address and size == words[11]
                            and observed_hash == completes[completed_commands]["output_sha256"], "Hardware output transfer differs")
                    pending["output"] = True
                elif operation == "write" and node == "user":
                    raise AssertionError("Unexpected CSR write at " + hex(offset))
            else:
                raise AssertionError("Unexpected transport event " + str(operation))
    require(pending is None and not descriptor_writes and completed_commands == 3200 and opens == closes == 1, "Transport command/handle closure coverage differs")
    result = dict(schema="scalellm_dsp_inference_regression_v1", status="PASS", original_request_count=16,
                  generated_tokens=512, complete_rounds=50, hardware_commands=3200,
                  token_id_regression="PASS", commit_lifecycle="PASS", submit_complete_ack="PASS",
                  whole_model_independent_numerical_oracle="NOT_ESTABLISHED", slots=slot_checks,
                  final_positions=final_positions, eos_token_ids=sorted(eos_ids),
                  native_exitcode=process["exitcode"], handles_closed=True, final_quiescent=True,
                  seconds=report["seconds"], total_fpga_cycles=sum(item["cycles"] for item in report["receipts"]),
                  duration_scope="run.json.seconds begins after full startup asset verification",
                  native_wall_seconds=native_wall_seconds,
                  transport_io_records=io_records, run_json_sha256=digest(inference / "run.json"),
                  inference_launch_sha256=digest(root / "environment/inference_launch.json"),
                  native_process_receipt_sha256=digest(root / "environment/inference_process_receipt.json"),
                  reference_manifest_sha256=digest(reference_path),
                  selected_kv32_trace_crosscheck=dict(status=selected_trace_status, commands=selected_trace),
                  progress_sha256=digest(inference / "progress.jsonl"), xdma_sha256=digest(inference / "xdma.jsonl"),
                  golden_sha256=digest(golden_path), requests_sha256=digest(requests_path))
    (inference / "outputs.json").write_text(json.dumps(outputs, ensure_ascii=False, indent=2) + "\n")
    (inference / "regression.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("status", "generated_tokens", "complete_rounds", "hardware_commands", "seconds", "native_wall_seconds", "total_fpga_cycles", "selected_kv32_trace_crosscheck")}))


if __name__ == "__main__":
    main()
