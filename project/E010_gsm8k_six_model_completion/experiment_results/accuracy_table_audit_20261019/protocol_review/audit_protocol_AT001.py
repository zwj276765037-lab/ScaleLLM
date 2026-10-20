"""Read-only historical evidence audit; standard library only, no model imports."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
assert ROOT.name == "ScaleLLM", ROOT
RAW = Path("/home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/fix_experiment/results/six_model_algorithm_literature_2048")
EVIDENCE = ROOT / "project/software/evidence/literature_2048"
OLD_EXP = RAW.parent.parent / "exp"
assert os.environ.get("CUDA_VISIBLE_DEVICES") == ""
assert sorted(os.sched_getaffinity(0)) == [8, 9]
assert "torch" not in sys.modules
started = datetime.now(timezone.utc).isoformat()
inputs = {}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    inputs[str(path)] = sha(path)
    return json.loads(path.read_text())


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def normalize(value):
    if isinstance(value, str):
        return re.sub(r" at 0x[0-9a-f]+>", " at <runtime-address>>", value)
    if isinstance(value, dict):
        return {key: normalize(val) for key, val in value.items()}
    if isinstance(value, list):
        return [normalize(val) for val in value]
    return value


table_manifest = load(EVIDENCE / "experiment_manifest.json")
old_manifest = load(RAW / "experiment_manifest.json")
inputs[str(EVIDENCE / "six_model_summary.csv")] = sha(EVIDENCE / "six_model_summary.csv")
inputs[str(RAW / "six_model_summary.csv")] = sha(RAW / "six_model_summary.csv")
assert inputs[str(EVIDENCE / "six_model_summary.csv")] == inputs[str(RAW / "six_model_summary.csv")]
assert len(table_manifest["source_manifests"]) == 30
inventory = []
for path in sorted(RAW.rglob("*")):
    if path.is_file():
        inventory.append({"relative_path": str(path.relative_to(RAW)), "bytes": path.stat().st_size,
                          "sha256": sha(path)})
with (OUT / "raw_tree_file_inventory.json").open("x") as output:
    json.dump(inventory, output, indent=2); output.write("\n")
named_candidates = [row for row in inventory if any(
    name in row["relative_path"].lower() for name in ("sample", "cache", "predict", "logit", "sqlite", ".db"))]
groups, workers = [], []
models = defaultdict(list)
acc_tasks = {"piqa", "arc_easy", "arc_challenge", "boolq", "hellaswag", "winogrande"}
prediction_keys = {"resps", "filtered_resps", "pred", "prediction", "predictions", "logits",
                   "loglikelihoods", "choice_loglikelihoods", "doc_id", "input_ids", "token_ids"}
for name in table_manifest["source_manifests"]:
    path = Path(name)
    assert path.is_relative_to(RAW) and path.name == "manifest.json"
    merged = load(path)
    model, case = merged["model_spec"]["name"], merged["case"]
    assert merged["status"] == "complete"
    group_dir = path.parent.parent
    candidates = []
    for worker_path in sorted(group_dir.rglob("manifest.json")):
        if worker_path == path:
            continue
        doc = load(worker_path)
        if doc.get("schema") == "scalellm_literature_aligned_worker_v1" and doc.get("status") == "complete":
            candidates.append((worker_path, doc))
    assert len(candidates) == len(merged["worker_manifests"]), (model, case)
    configs, audits, data_by_task = {}, {}, {}
    for worker_path, doc in candidates:
        match = [inline for inline in merged["worker_manifests"] if
                 inline["tasks"] == doc["tasks"] and inline["elapsed_sec"] == doc["elapsed_sec"] and
                 inline["method"] == doc["method"] and inline["data"] == doc["data"]]
        assert len(match) == 1, worker_path
        assert doc["model_identity"] == merged["model_identity"]
        assert doc["model_spec"] == merged["model_spec"]
        assert doc["method"] == merged["method"]
        assert doc["protocol"] == merged["protocol"]
        raw = doc.get("lm_eval_raw") or {}
        raw_configs = raw.get("configs", {})
        for task, config in raw_configs.items():
            assert task not in configs
            assert config["num_fewshot"] == 0 and config["output_type"] == "multiple_choice"
            configs[task] = normalize(config)
        audits.update(doc.get("truncation_audit", {}))
        data_by_task.update({row["task"]: row for row in doc["data"]})
        found = []
        def inspect(value, prefix=""):
            if isinstance(value, dict):
                for key, val in value.items():
                    location = prefix + "/" + key
                    if key in prediction_keys or (key == "samples" and isinstance(val, (list, dict)) and val):
                        found.append(location)
                    inspect(val, location)
            elif isinstance(value, list):
                for index, val in enumerate(value):
                    inspect(val, prefix + "/" + str(index))
        inspect(raw)
        workers.append({"path": str(worker_path), "model": model, "case": case,
            "tasks": doc["tasks"], "raw_keys": list(raw), "has_top_level_samples": "samples" in raw,
            "prediction_like_fields": found, "lm_eval_result_cache": raw.get("config", {}).get("use_cache"),
            "batch_size": doc["runtime_args"]["batch_size"], "seed": doc["seed"],
            "tokenizer_boundary_policy": doc["tokenizer_boundary_policy"],
            "tokenizer_special_tokens": {key: raw.get(key) for key in
                ("tokenizer_pad_token", "tokenizer_eos_token", "tokenizer_bos_token", "eot_token_id", "max_length")}})
    assert set(configs) == acc_tasks and set(audits) == acc_tasks
    method, spec = merged["method"], merged["model_spec"]
    quantized = case != "bf16"
    attach_match = (method.get("module_count") == spec["expected_module_count"] and
                    method.get("per_op") == spec["expected_per_op"]) if quantized else None
    assert attach_match is not False
    group = {"model": model, "case": case, "merged_path": str(path),
        "worker_paths": [str(p) for p, _ in candidates], "checkpoint_identity": merged["model_identity"],
        "model_spec": spec, "protocol_without_case": {k:v for k,v in merged["protocol"].items() if k != "case"},
        "primary_metric_policy": merged["primary_metric_policy"], "data_by_task": data_by_task,
        "task_configs_without_runtime_addresses": configs, "truncation_audit": audits,
        "versions": merged["versions"], "method": method, "quantized_attach_counts_match_model_spec": attach_match}
    groups.append(group); models[model].append(group)
model_checks = {}
for model, records in models.items():
    assert len(records) == 5
    baseline = next(record for record in records if record["case"] == "bf16")
    checks = {key: all(record[key] == baseline[key] for record in records) for key in
        ("checkpoint_identity", "model_spec", "protocol_without_case", "primary_metric_policy", "data_by_task",
         "task_configs_without_runtime_addresses", "truncation_audit", "versions")}
    quantized_records = [record for record in records if record["case"] != "bf16"]
    checks["quantized_attach_per_op_equal_across_four_cases"] = all(
        record["method"]["per_op"] == quantized_records[0]["method"]["per_op"] for record in quantized_records)
    checks["all_quantized_attach_counts_match_expected"] = all(
        record["quantized_attach_counts_match_model_spec"] is True for record in quantized_records)
    checks["recorded_tokenizer_file_hashes_equal"] = all(
        [f for f in record["checkpoint_identity"]["files"] if "token" in f["name"]] ==
        [f for f in baseline["checkpoint_identity"]["files"] if "token" in f["name"]] for record in records)
    model_checks[model] = {"checks": checks, "checkpoint_fingerprint": baseline["checkpoint_identity"]["fingerprint_sha256"],
        "quantized_module_count": quantized_records[0]["method"]["module_count"],
        "case_worker_counts": {record["case"]: len(record["worker_paths"]) for record in records},
        "batch_sizes": sorted({worker["batch_size"] for worker in workers if worker["model"] == model}),
        "seed_values": sorted({worker["seed"] for worker in workers if worker["model"] == model})}
source_snippets = {}
for filename in ("run_eval_worker.py", "protocol.py"):
    path = OLD_EXP / filename
    inputs[str(path)] = sha(path)
    lines = path.read_text().splitlines()
    hits = [{"line": index+1, "text": line.strip()} for index,line in enumerate(lines) if any(
        needle in line for needle in ("log_samples=False", "cache_requests=False", "logits_cache=True", '"output_type": "multiple_choice"', '"num_fewshot": 0', "num_fewshot=0"))]
    recorded = next(item["sha256"] for item in table_manifest["code_identity"]["files"] if Path(item["path"]).name == filename)
    source_snippets[filename] = {"path": str(path), "current_sha256": inputs[str(path)],
        "recorded_summary_code_sha256": recorded, "current_matches_recorded": inputs[str(path)] == recorded,
        "static_snippets": hits}
deepseek = next(group for group in groups if group["model"] == "DeepSeek-R1-Distill-Llama-8B" and group["case"] == "bf16")
report = {"schema": "scalellm_literature_2048_protocol_readonly_review_v1", "owner": "A010 /root/gsm8k_protocol",
    "execution_state": "completed", "start_utc": started, "end_utc": datetime.now(timezone.utc).isoformat(),
    "CPU_affinity": sorted(os.sched_getaffinity(0)), "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
    "torch_imported": "torch" in sys.modules, "raw_root": str(RAW), "read_only_scope": True,
    "table_copy_byte_identical_to_raw_summary": True, "merged_groups": len(groups), "complete_worker_shards": len(workers),
    "within_model_comparability": model_checks, "workers": workers,
    "raw_file_inventory_count": len(inventory), "raw_file_extensions": dict(Counter(Path(row["relative_path"]).suffix for row in inventory)),
    "sample_cache_prediction_filename_candidates": named_candidates,
    "workers_with_saved_samples": [worker["path"] for worker in workers if worker["has_top_level_samples"]],
    "workers_with_prediction_like_fields": [worker["path"] for worker in workers if worker["prediction_like_fields"]],
    "current_source_static_evidence": source_snippets,
    "deepseek_recorded_task_configs": deepseek["task_configs_without_runtime_addresses"],
    "deepseek_boundary_fallback_by_task": {task: {k:v for k,v in row.items() if "fallback" in k} for task,row in deepseek["truncation_audit"].items()},
    "limitations": ["Aggregate equality cannot establish per-question agreement, all-yes predictions, class bias, score margins or paired flip counts.",
        "Recorded model/tokenizer fingerprints and attach counts are historical declarations; this audit does not rehash checkpoint weights, load models or validate live attached tensors.",
        "Current old-root worker/protocol source hashes differ from the summary recorded code identity; their readable log_samples=False/cache switches are supporting source evidence, not an exact historical source freeze.",
        "No per-sample scores, logits, responses or hidden sample/cache artifacts were found in the specified result tree/complete worker JSON. Files outside this bounded root were not searched.",
        "DeepSeek is evaluated by fixed raw zero-shot multiple-choice loglikelihood tasks; no chat/thinking versus raw controlled comparison was performed, so missing chat/thinking causing low accuracy remains an untested explanation.",
        "Non-monotonic aggregate ACC under quantization is possible because changed scores can repair some decisions and damage others; without saved per-question outputs this mechanism cannot be measured for this run."],
    "input_sha256": inputs}
assert report["torch_imported"] is False
assert all(sha(Path(path)) == digest for path,digest in inputs.items())
for row in inventory:
    assert sha(RAW / row["relative_path"]) == row["sha256"]
report["all_consumed_inputs_and_inventory_hashes_stable"] = True
with (OUT / "protocol_review.json").open("x") as output:
    json.dump(report, output, indent=2); output.write("\n")
with (OUT / "case_protocol_evidence.json").open("x") as output:
    json.dump(groups, output, indent=2); output.write("\n")
print(json.dumps({"groups":len(groups), "worker_shards":len(workers), "files":len(inventory),
    "comparability":{key:value["checks"] for key,value in model_checks.items()},
    "sample_cache_files":len(named_candidates), "saved_samples_workers":len(report["workers_with_saved_samples"]),
    "prediction_fields_workers":len(report["workers_with_prediction_like_fields"]), "all_inputs_stable":True},indent=2))
