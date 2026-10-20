#!/usr/bin/env python3
"""Independently validate frozen full-test GSM8K evidence and merge five old tasks.

No model weights are loaded.  The scoring oracle is the installed harness,
not gsm8k_protocol.score_response or the worker's saved correctness flags.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import inspect
import json
import math
from pathlib import Path
import re
import statistics
from typing import Any

from gsm8k_protocol import (DEFAULT_PLAN, atomic_json, canonical_hash, load_plan,
                            prepare_requests, resolve_input_path, sha256_file)
from six_model_matrix import FIVE_CONFIG_CASES, MODEL_BY_DIRECTORY, MODEL_SPECS, validate_quantized_summary

TASKS = ("piqa", "arc_easy", "gsm8k", "boolq", "hellaswag", "winogrande")
HISTORICAL_TASKS = tuple(task for task in TASKS if task != "gsm8k")
METRICS = {"piqa": ("acc_norm", 1838), "arc_easy": ("acc_norm", 2376),
           "boolq": ("acc", 3270), "hellaswag": ("acc_norm", 10042), "winogrande": ("acc", 1267)}
NUMERICAL_FILES = ("six_model_matrix.py", "mlp4_method_inference.py", "scalepath4_method_inference.py")
SCORE_FIELDS = ("strict_prediction", "flexible_prediction", "normalized_gold",
                "correct_strict", "correct_flexible", "invalid_strict")
NATIVE_VERIFICATION = "native_cache_call_parity_v2"
NATIVE_GATES = ("native_generate_exact", "rebuilt_cache_exact", "cache_structure_valid",
                "negative_control_qualified", "same_process_repeat_32_equal")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise ValueError(f"unterminated JSONL in completed attempt: {path}")
    rows = []
    for number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            raise ValueError(f"empty JSONL record {path}:{number}")
        try:
            row = json.loads(line)
        except (ValueError, UnicodeError) as exc:
            raise ValueError(f"invalid JSONL {path}:{number}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"nonobject JSONL {path}:{number}")
        rows.append(row)
    return rows


def unique_rows(rows: list[dict[str, Any]], expected: list[str], label: str) -> dict[str, dict[str, Any]]:
    ids = [row.get("sample_id") for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{label}: duplicate sample IDs")
    if ids != expected:
        raise ValueError(f"{label}: missing, extra or out-of-order sample IDs")
    return dict(zip(ids, rows, strict=True))


class HarnessOracle:
    def __init__(self, protocol: dict[str, Any]):
        from lm_eval.api.metrics import exact_match_hf_evaluate
        from lm_eval.filters.extraction import RegexFilter
        if importlib.metadata.version("lm_eval") != "0.4.11":
            raise ValueError("independent scoring requires lm_eval==0.4.11")
        self.strict = RegexFilter(regex_pattern=protocol["strict_regex"], group_select=0,
                                  fallback=protocol["invalid_value"])
        self.flexible = RegexFilter(regex_pattern=protocol["flexible_regex"], group_select=-1,
                                    fallback=protocol["invalid_value"])
        self.exact_match = exact_match_hf_evaluate
        self.protocol = protocol
        self.evidence = {"lm_eval": "0.4.11", "oracle": "RegexFilter + exact_match_hf_evaluate",
                         "source_sha256": {str(Path(inspect.getfile(obj)).resolve()):
                             sha256_file(Path(inspect.getfile(obj))) for obj in
                             (RegexFilter, exact_match_hf_evaluate)}}

    def score(self, response: str, gold: str) -> dict[str, Any]:
        strict = self.strict.apply([[response]], [{}])[0][0]
        flexible = self.flexible.apply([[response]], [{}])[0][0]
        def matches(prediction: str) -> bool:
            return bool(self.exact_match(predictions=[prediction], references=[gold],
                        regexes_to_ignore=self.protocol["normalization_regexes"],
                        ignore_case=True, ignore_punctuation=False)["exact_match"])
        normalized = gold
        for pattern in self.protocol["normalization_regexes"]:
            normalized = re.sub(pattern, "", normalized)
        normalized = normalized.lower()
        return {"strict_prediction": strict, "flexible_prediction": flexible,
                "normalized_gold": normalized, "correct_strict": matches(strict),
                "correct_flexible": matches(flexible),
                "invalid_strict": strict == self.protocol["invalid_value"]}


def validate_model_identity(identity: dict[str, Any], model: str) -> None:
    if identity.get("schema") != "scalellm_checkpoint_identity_v1" or identity.get("checkpoint_name") != model:
        raise ValueError("checkpoint identity schema/name mismatch")
    entries = identity.get("files", [])
    names = [entry["name"] for entry in entries]
    if not entries or names != sorted(set(names)) or any(Path(name).name != name for name in names):
        raise ValueError("invalid checkpoint file inventory")
    fingerprint = hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if fingerprint != identity.get("fingerprint_sha256"):
        raise ValueError("checkpoint identity fingerprint mismatch")
    if identity.get("file_count") != len(entries) or identity.get("total_bytes") != sum(e["bytes"] for e in entries):
        raise ValueError("checkpoint identity inventory totals mismatch")
    if not any(Path(name).suffix in {".safetensors", ".bin"} for name in names):
        raise ValueError("checkpoint identity lacks weight files")


def hash_by_name(items: dict[str, str] | list[dict[str, str]]) -> dict[str, str]:
    entries = items.items() if isinstance(items, dict) else ((i["path"], i["sha256"]) for i in items)
    result = {}
    for path, digest in entries:
        name = Path(path).name
        if name in result and result[name] != digest:
            raise ValueError(f"ambiguous code identity for {name}")
        result[name] = digest
    return result


def validate_method(current: dict[str, Any], historical: dict[str, Any], model: str, case: str) -> None:
    if current.get("use_cache") is not True or current.get("dtype") != "bfloat16" or current.get("attention_implementation") != "eager":
        raise ValueError("GSM8K live method/cache/backend mismatch")
    if case != "bf16":
        validate_quantized_summary(current, MODEL_BY_DIRECTORY[model], case)
        validate_quantized_summary(historical, MODEL_BY_DIRECTORY[model], case)
    for key, expected in historical.items():
        # Cache is intentionally enabled for generation. The historical five
        # tasks used likelihood and therefore disabled it.
        if key == "use_cache":
            continue
        if current.get(key) != expected:
            raise ValueError(f"historical numerical method mismatch: {key}")


def load_checked_tokenizer(manifest: dict[str, Any]) -> Any:
    from transformers import AutoTokenizer
    model_identity = manifest["model_identity"]
    model = Path(model_identity["resolved_path"])
    # Check all nonweight checkpoint files before loading tokenizer/config code.
    # Full weight hashes were checked at worker launch and are matched to history.
    for entry in model_identity["files"]:
        if Path(entry["name"]).suffix not in {".safetensors", ".bin"}:
            if sha256_file(model / entry["name"]) != entry["sha256"]:
                raise ValueError(f"tokenizer/config checkpoint contents changed: {entry['name']}")
    tokenizer = AutoTokenizer.from_pretrained(model, local_files_only=True, trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer


def check_tokenizer_identity(tokenizer: Any, identity: dict[str, Any]) -> None:
    expected = identity["tokenizer"]
    observed = {"class": type(tokenizer).__module__ + "." + type(tokenizer).__name__,
                "vocab_sha256": canonical_hash(tokenizer.get_vocab()),
                "special_tokens_map": tokenizer.special_tokens_map,
                "bos_token_id": tokenizer.bos_token_id, "eos_token_id": tokenizer.eos_token_id,
                "pad_token_id": tokenizer.pad_token_id,
                "add_bos_token": getattr(tokenizer, "add_bos_token", None),
                "padding_side": tokenizer.padding_side}
    for key, value in observed.items():
        if expected.get(key) != value:
            raise ValueError(f"tokenizer runtime identity mismatch: {key}")


def independently_rescore(row: dict[str, Any], saved: dict[str, Any], request: dict[str, Any],
                          identity: dict[str, Any], identity_hash: str, tokenizer: Any,
                          oracle: HarnessOracle, input_ids: list[int]) -> dict[str, Any]:
    if row.get("schema") != "scalellm_gsm8k_generation_v1" or row.get("status") != "complete":
        raise ValueError("formal row is not a completed generation")
    if row.get("identity_sha256") != identity_hash or saved.get("identity_sha256") != identity_hash:
        raise ValueError("per-sample execution identity mismatch")
    for key in ("sample_id", "row_index", "split", "prompt_sha256", "fewshot_train_indices", "gold"):
        if row.get(key) != request[key]:
            raise ValueError(f"per-sample frozen request mismatch: {key}")
    if row.get("question_sha256") != hashlib.sha256(request["question"].encode()).hexdigest():
        raise ValueError("per-sample question hash mismatch")
    if saved.get("sample_id") != row["sample_id"] or saved.get("gold") != request["gold"]:
        raise ValueError("score sample/gold mismatch")
    generation = identity["generation"]
    config = generation["effective_generation_config"]
    if row.get("input_tokens") != len(input_ids) or row.get("input_token_ids_sha256") != canonical_hash(input_ids):
        raise ValueError("per-sample input token identity mismatch")
    if not input_ids or len(input_ids) > identity["max_prompt_tokens"] or len(input_ids) + config["max_new_tokens"] > generation["context_length"]:
        raise ValueError("prompt exceeds frozen context or prompt budget")
    tokens = row.get("new_token_ids")
    if not isinstance(tokens, list) or any(type(token) is not int or token < 0 for token in tokens):
        raise ValueError("invalid new token IDs")
    if row.get("output_tokens") != len(tokens) or len(tokens) > config["max_new_tokens"]:
        raise ValueError("invalid generation token count")
    stops = generation["stop_strings"]
    if row.get("stop_strings") != stops or row.get("eos_token_ids") != generation["eos_token_ids"]:
        raise ValueError("per-sample stop configuration mismatch")
    raw = tokenizer.decode(tokens, skip_special_tokens=False, clean_up_tokenization_spaces=False)
    decoded = tokenizer.decode(tokens, skip_special_tokens=True)
    matches = [(decoded.index(stop), stop) for stop in stops if stop in decoded]
    position, stop = min(matches, key=lambda item: item[0]) if matches else (len(decoded), None)
    scoring = decoded[:position]
    if row.get("raw_text") != raw or row.get("decoded_text_skip_special_tokens") != decoded or row.get("scoring_text") != scoring:
        raise ValueError("raw/token/scoring continuation mismatch")
    if saved.get("scoring_text") != scoring:
        raise ValueError("saved score text differs from reconstructed continuation")
    eos = bool(tokens and tokens[-1] in generation["eos_token_ids"])
    capped = len(tokens) >= config["max_new_tokens"]
    reason = "eos" if eos else "stop_string" if stop is not None else "length" if capped else "model_stop"
    if row.get("stop_reason") != reason or row.get("matched_stop_string") != stop:
        raise ValueError("stop reason disagrees with raw generation")
    if type(row.get("length_capped")) is not bool or row["length_capped"] != (reason == "length"):
        raise ValueError("length-cap flag disagrees with raw generation")
    if row.get("generation_limit_reached") is not capped or row.get("use_cache") is not True:
        raise ValueError("generation limit/cache evidence mismatch")
    for key in ("elapsed_seconds", "peak_memory_allocated_bytes", "peak_memory_reserved_bytes"):
        value = row.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"missing/invalid per-sample measurement: {key}")
    result = oracle.score(scoring, request["gold"])
    for field in SCORE_FIELDS:
        if saved.get(field) != result[field] or type(saved.get(field)) != type(result[field]):
            raise ValueError(f"independent harness score mismatch: {field}")
    return {"sample_id": row["sample_id"], "identity_sha256": identity_hash,
            "scoring_text_sha256": hashlib.sha256(scoring.encode()).hexdigest(), **result,
            "output_tokens": len(tokens), "length_capped": reason == "length",
            "elapsed_seconds": row["elapsed_seconds"], "peak_memory_allocated_bytes": row["peak_memory_allocated_bytes"]}


def validate_group(attempt: Path, model: str, case: str, plan: dict[str, Any], plan_hash: str,
                   requests: list[dict[str, Any]], historical: dict[str, Any],
                   historical_codes: dict[str, str], contract: dict[str, Any],
                   oracle: HarnessOracle, tokenizer: Any | None = None) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    manifest = read_json(attempt / "manifest.json")
    identity = manifest.get("identity", {})
    identity_hash = canonical_hash(identity)
    if (manifest.get("schema") != "scalellm_gsm8k_worker_manifest_v1" or manifest.get("state") != "complete" or
            manifest.get("stage") != "formal" or manifest.get("model") != model or manifest.get("case") != case or
            manifest.get("identity_sha256") != identity_hash):
        raise ValueError("formal manifest state/model/case/identity mismatch")
    checks = {"protocol_id": plan["protocol_id"], "plan_sha256": plan_hash,
              "protocol_sha256": canonical_hash(plan["protocol"]), "data": plan["data"],
              "requests_sha256": canonical_hash(requests), "stage": "formal", "case": case,
              "seed": plan["protocol"]["seed"]}
    for key, expected in checks.items():
        if identity.get(key) != expected:
            raise ValueError(f"formal execution identity mismatch: {key}")
    for key in ("plan_sha256", "protocol_sha256", "package_versions"):
        if contract.get(key) != identity.get(key):
            raise ValueError(f"frozen run contract mismatch: {key}")
    if contract["stage_requests_sha256"]["formal"] != identity["requests_sha256"] or contract["model_fingerprints"][model] != identity["model_fingerprint_sha256"]:
        raise ValueError("frozen run request/model fingerprint mismatch")
    if identity["package_versions"].get("lm_eval") != "0.4.11":
        raise ValueError("worker harness version differs from oracle")
    codes = identity.get("code_sha256", {})
    if not codes:
        raise ValueError("worker code identity missing")
    for path, digest in codes.items():
        if sha256_file(Path(path)) != digest:
            raise ValueError(f"worker source changed: {path}")
        if path in contract["source_hashes"] and digest != contract["source_hashes"][path]:
            raise ValueError("worker source differs from frozen contract")
    current_codes = hash_by_name(codes)
    for name in NUMERICAL_FILES:
        if current_codes.get(name) != historical_codes.get(name) or name not in current_codes:
            raise ValueError(f"historical numerical code identity mismatch: {name}")
    model_identity = manifest["model_identity"]
    validate_model_identity(model_identity, model)
    if model_identity["fingerprint_sha256"] != identity["model_fingerprint_sha256"] or model_identity["files"] != historical["model_identity"]["files"]:
        raise ValueError("historical checkpoint identity mismatch")
    if historical["model_identity"]["fingerprint_sha256"] != identity["model_fingerprint_sha256"]:
        raise ValueError("historical checkpoint fingerprint mismatch")
    validate_method(identity["method"], historical["method"], model, case)
    if manifest.get("method") != identity["method"] or manifest.get("generation") != identity["generation"]:
        raise ValueError("manifest method/generation disagrees with hashed identity")
    gen = identity["generation"]
    cfg = gen["effective_generation_config"]
    for key, expected in {"do_sample": False, "num_beams": 1, "num_return_sequences": 1,
                          "use_cache": True, "max_new_tokens": plan["protocol"]["max_gen_toks"],
                          "repetition_penalty": 1.0, "no_repeat_ngram_size": 0,
                          "cache_implementation": "dynamic"}.items():
        if cfg.get(key) != expected:
            raise ValueError(f"effective generation config mismatch: {key}")
    if gen.get("context_length") != plan["protocol"]["max_sequence_length"] or gen.get("temperature_argument_passed") is not False:
        raise ValueError("generation context/greedy argument mismatch")
    artifacts = {}
    for name in ("generation.jsonl", "scores.jsonl", "requests.json"):
        digest = sha256_file(attempt / name)
        if manifest.get("artifacts", {}).get(name) != digest:
            raise ValueError(f"artifact hash mismatch: {name}")
        artifacts[name] = digest
    frozen_requests = read_json(attempt / "requests.json")
    if frozen_requests != requests or canonical_hash(frozen_requests) != identity["requests_sha256"]:
        raise ValueError("saved requests differ from frozen requests")
    expected_ids = [f"test:{index:04d}" for index in range(1319)]
    if [request["sample_id"] for request in requests] != expected_ids:
        raise ValueError("formal request list is not full test 0-1318")
    generation_rows = unique_rows(read_jsonl(attempt / "generation.jsonl"), expected_ids, "generation")
    saved_scores = unique_rows(read_jsonl(attempt / "scores.jsonl"), expected_ids, "scores")
    tokenizer = load_checked_tokenizer(manifest) if tokenizer is None else tokenizer
    check_tokenizer_identity(tokenizer, identity)
    encoded = {request["sample_id"]: list(tokenizer.encode(request["prompt"], truncation=False)) for request in requests}
    if canonical_hash(encoded) != identity["token_audit"]["input_token_ids_sha256"] or identity["token_audit"].get("input_truncation") is not False:
        raise ValueError("full request tokenizer audit mismatch")
    # Local-only budget value is passed to the row validator without mutating
    # the identity whose canonical checksum was verified above.
    row_identity = {**identity, "max_prompt_tokens": plan["protocol"]["max_prompt_tokens"]}
    rescored = [independently_rescore(generation_rows[request["sample_id"]], saved_scores[request["sample_id"]],
                request, row_identity, identity_hash, tokenizer, oracle, encoded[request["sample_id"]]) for request in requests]
    correct = sum(row["correct_strict"] for row in rescored)
    flexible = sum(row["correct_flexible"] for row in rescored)
    invalid = sum(row["invalid_strict"] for row in rescored)
    capped = sum(row["length_capped"] for row in rescored)
    summary = read_json(attempt / "summary.json")
    expected_summary = {"state": "complete", "stage": "formal", "n_expected": 1319,
                        "n_completed": 1319, "n_errors": 0, "full_split": True,
                        "correct_strict": correct, "correct_flexible": flexible,
                        "invalid_strict": invalid, "length_capped": capped,
                        "exact_match,strict-match": correct / 1319,
                        "exact_match,flexible-extract": flexible / 1319}
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            raise ValueError(f"worker summary differs from independent full-test recount: {key}")
    p = correct / 1319
    z = 1.959963984540054
    center = (p + z*z/(2*1319)) / (1 + z*z/1319)
    radius = z * math.sqrt(p*(1-p)/1319 + z*z/(4*1319**2)) / (1 + z*z/1319)
    result = {"model": model, "case": case, "model_fingerprint_sha256": identity["model_fingerprint_sha256"],
              "protocol_id": plan["protocol_id"], "n_expected": 1319, "n_completed": 1319,
              "correct_strict": correct, "correct_flexible": flexible, "strict_em": p,
              "flexible_em": flexible / 1319, "strict_wilson95_low": center-radius,
              "strict_wilson95_high": center+radius, "invalid_strict": invalid, "length_capped": capped,
              "output_tokens": sum(row["output_tokens"] for row in rescored),
              "mean_seconds_per_example": statistics.mean(row["elapsed_seconds"] for row in rescored),
              "peak_memory_allocated_bytes": max(max(row["peak_memory_allocated_bytes"] for row in rescored),
                  manifest.get("model_load_attach_peak_memory_allocated_bytes", 0)),
              "model_load_attach_peak_memory_allocated_bytes": manifest.get("model_load_attach_peak_memory_allocated_bytes"),
              "full_split": True, "independent_harness_validated": True, "attempt": str(attempt)}
    source = {"model": model, "case": case, "attempt": str(attempt), "identity_sha256": identity_hash,
              "manifest_sha256": sha256_file(attempt / "manifest.json"),
              "summary_sha256": sha256_file(attempt / "summary.json"), "artifacts": artifacts,
              "accepted": True, "validation": "1319 raw-token continuations independently rescored by installed harness"}
    common = {key: identity[key] for key in ("protocol_id", "plan_sha256", "protocol_sha256", "data",
                                           "requests_sha256", "stage", "seed", "code_sha256", "package_versions")}
    source["comparison_identity_sha256"] = canonical_hash(common)
    return result, rescored, source


def load_history(plan: dict[str, Any], plan_path: Path) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, Any]]:
    csv_path = resolve_input_path(plan_path, plan["paths"]["historical_summary_csv"])
    if sha256_file(csv_path) != plan["paths"]["historical_summary_csv_sha256"]:
        raise ValueError("historical summary CSV hash mismatch")
    parent = csv_path.parent
    manifest_path = parent / "experiment_manifest.json"
    manifest = read_json(manifest_path)
    if manifest.get("status") != "complete" or manifest.get("protocol") != "literature_2048":
        raise ValueError("historical matrix manifest is not complete literature_2048")
    codes = hash_by_name(manifest["code_identity"]["files"])
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    expected = {(spec.name, case) for spec in MODEL_SPECS for case in FIVE_CONFIG_CASES}
    history = {}
    evidence = {"csv": str(csv_path), "csv_sha256": sha256_file(csv_path),
                "experiment_manifest": str(manifest_path), "experiment_manifest_sha256": sha256_file(manifest_path),
                "numerical_code_hashes": {name: codes[name] for name in NUMERICAL_FILES}, "groups": []}
    for row in rows:
        key = (row["model"], row["case"])
        if key in history or key not in expected:
            raise ValueError("historical duplicate/unexpected model/case")
        path = parent / key[0] / f"{key[1]}_literature_2048" / "merged/manifest.json"
        run = read_json(path)
        if run.get("status") != "complete" or run.get("case") != key[1]:
            raise ValueError("historical merged state/case mismatch")
        for field, expected_value in {"protocol": "literature_2048", "context_length": 2048,
                                      "zero_shot": True, "full_split": True, "literature_comparable": True,
                                      "hardware_constrained": False}.items():
            if run["protocol"].get(field) != expected_value:
                raise ValueError(f"historical merged protocol mismatch: {field}")
        validate_model_identity(run["model_identity"], key[0])
        if row["model_fingerprint_sha256"] != run["model_identity"]["fingerprint_sha256"] or row.get("status") != "complete" or row.get("full_split") != "True":
            raise ValueError("historical CSV checkpoint/state mismatch")
        by_task = {entry["task"]: entry for entry in run["results"]}
        values = {}
        for task, (metric, count) in METRICS.items():
            original = by_task[task]
            value = float(row[task])
            if not math.isfinite(value) or not 0 <= value <= 1 or value != float(original["value"]):
                raise ValueError(f"historical CSV/merged score mismatch: {task}")
            if original["primary_metric"] != metric or original["samples"] != count:
                raise ValueError(f"historical metric/count mismatch: {task}")
            values[task] = value
        history[key] = {"values": values, "run": run, "path": str(path)}
        evidence["groups"].append({"model": key[0], "case": key[1], "manifest": str(path),
                                    "manifest_sha256": sha256_file(path)})
    if set(history) != expected:
        raise ValueError("historical matrix does not contain exactly 30 groups")
    return history, evidence


def merge_rows(history: dict[tuple[str, str], dict[str, Any]], results: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for spec in MODEL_SPECS:
        for case in FIVE_CONFIG_CASES:
            key = spec.name, case
            old = history[key]
            result = results.get(key)
            row = {"model": spec.name, "case": case,
                   "model_fingerprint_sha256": old["run"]["model_identity"]["fingerprint_sha256"],
                   **old["values"], "gsm8k": "", "macro_accuracy": "", "status": "pending",
                   "gsm8k_full_split": False, "gsm8k_independent_harness_validated": False,
                   "gsm8k_protocol_id": "", "gsm8k_attempt": ""}
            if result is not None:
                row.update(gsm8k=result["strict_em"], status="validated", gsm8k_full_split=True,
                           gsm8k_independent_harness_validated=True, gsm8k_protocol_id=result["protocol_id"],
                           gsm8k_attempt=result["attempt"])
                row["macro_accuracy"] = sum(float(row[task]) for task in TASKS) / len(TASKS)
            rows.append(row)
    return rows


def validate_native_record(record: dict[str, Any], eos_ids: list[int], layers: int) -> None:
    if not all(record.get(key) is True for key in NATIVE_GATES):
        raise ValueError("native cache record hard gates did not pass")
    count, tokens, steps = record.get("native_logits_count"), record.get("native_generated_token_ids"), record.get("steps")
    if (type(count) is not int or not 1 <= count <= 17 or not isinstance(tokens, list) or
            len(tokens) != count or any(type(token) is not int or token < 0 for token in tokens) or
            not isinstance(steps, list) or len(steps) != count):
        raise ValueError("native cache record lacks complete step/token/logit evidence")
    prefix = record["repeatability_prefix_32_token_ids"]
    if (record.get("native_prefix_matches_32") is not True or tokens != prefix[:count] or
            record.get("repeat_32_token_ids") != prefix or (count < 17 and tokens[-1] not in eos_ids)):
        raise ValueError("native/repeated greedy prefix mismatch or unexplained early termination")
    input_length = record.get("input_tokens")
    if type(input_length) is not int or input_length <= 0:
        raise ValueError("native cache evidence lacks input length")
    for index, step in enumerate(steps):
        if step.get("step") != index or not all(step.get(key) is True for key in
                ("native_generate_exact", "rebuilt_cache_exact", "cache_structure_valid", "finite",
                 "manual_rebuilt_storage_disjoint", "manual_native_storage_disjoint")):
            raise ValueError("native cache per-step hard evidence failed")
        for field in ("native_logits", "rebuilt_logits"):
            comparison = step.get(field, {})
            if (comparison.get("exact") is not True or comparison.get("finite") is not True or
                    not comparison.get("left_sha256") or comparison.get("left_sha256") != comparison.get("right_sha256")):
                raise ValueError("native cache full-logit comparison evidence is inconsistent")
        kv = step.get("kv_layers", [])
        if len(kv) != layers or [layer.get("layer") for layer in kv] != list(range(layers)):
            raise ValueError("native cache full K/V layer coverage mismatch")
        for layer in kv:
            if not all(layer.get(key) is True for key in ("all_elements_compared", "key_exact", "value_exact")):
                raise ValueError("native cache full K/V comparison failed")
            for kind in ("key", "value"):
                shape = layer.get(f"{kind}_shape")
                if (not isinstance(shape, list) or len(shape) != 4 or shape[0] != 1 or
                        shape[-2] != input_length+index or any(type(size) is not int or size <= 0 for size in shape) or
                        layer.get(f"{kind}_elements") != math.prod(shape)):
                    raise ValueError("native cache K/V shape/length evidence mismatch")
        cache = step.get("manual_cache", {})
        cached_layers = cache.get("layers", [])
        if (cache.get("valid") is not True or cache.get("expected_length") != input_length+index or
                cache.get("expected_layers") != layers or len(cached_layers) != layers or
                not all(layer.get("finite") is True and layer.get("length_valid") is True and
                        layer.get("old_prefix_unchanged") is True for layer in cached_layers)):
            raise ValueError("native cache old K/V prefix/length evidence failed")
        transitions = step.get("rebuild_transitions", [])
        if len(transitions) != index+1 or any(transition.get("segment") != offset or
                transition.get("expected_length") != input_length+offset or
                transition.get("cache_structure_valid") is not True for offset, transition in enumerate(transitions)):
            raise ValueError("fresh cache rebuild transitions are incomplete")
    status = record.get("negative_control_status")
    detail = record.get("negative_control", {})
    if status == "not_applicable_early_eos_no_prior_cache":
        if (record.get("negative_control_detected") is not None or "negative_control_detected" not in record or
                count != 1 or tokens[0] not in eos_ids or detail.get("prior_cache_available") is not False):
            raise ValueError("negative-control N/A requires a single native EOS and no prior cache")
    elif status != "detected" or record.get("negative_control_detected") is not True:
        raise ValueError("native cache corruption negative control did not detect the defect")


def validate_generation_qualification(run_root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    """Verify saved train-budget and independent-process cache/repeat evidence."""
    path = run_root / "pilot_gate.json"
    gate = read_json(path)
    expected = {(spec.name, case) for spec in MODEL_SPECS for case in FIVE_CONFIG_CASES}
    groups = gate.get("groups", [])
    keys = [(group["model"], group["case"]) for group in groups]
    if gate.get("passed") is not True or len(keys) != 30 or set(keys) != expected:
        raise ValueError("formal evidence lacks the passed 30-group train pilot gate")
    sources = []
    for group in groups:
        if group.get("passed") is not True or group.get("n") != 32 or group["length_capped_count"] / 32 > plan["pilot_budget_gate"]["threshold_length_capped_fraction"]:
            raise ValueError("train pilot compatibility/length budget gate failed")
        repeat = group["repeatability"]
        if repeat.get("passed") is not True or Path(repeat["smoke"]).resolve() == Path(repeat["pilot"]).resolve():
            raise ValueError("repeatability evidence does not use two independent attempts")
        prefixes = []
        gpu_uuids = []
        for stage in ("smoke", "pilot"):
            folder = Path(repeat[stage])
            file = folder / "verification.json"
            if sha256_file(file) != repeat[f"{stage}_verification_sha256"]:
                raise ValueError("train verification artifact hash mismatch")
            verification = read_json(file)
            manifest = read_json(folder / "manifest.json")
            if manifest.get("state") != "complete" or manifest.get("stage") != stage or manifest.get("model") != group["model"] or manifest.get("case") != group["case"]:
                raise ValueError("train verification model/case/stage mismatch")
            gpu_uuid = manifest.get("environment", {}).get("gpu_uuid")
            if not isinstance(gpu_uuid, str) or gpu_uuid in {"", "unknown"}:
                raise ValueError("train repeatability evidence lacks actual GPU UUID")
            gpu_uuids.append(gpu_uuid.lower().removeprefix("gpu-"))
            if verification.get("passed") is not True or verification.get("all_qdq_projections_prefill_and_decode") is not True:
                raise ValueError("generation verification did not pass")
            records = verification.get("records", [])
            if len(records) != 2 or {record["sample_id"] for record in records} != {"train:0000", "train:0001"}:
                raise ValueError("verification requires the two fixed train prompts")
            values = {}
            eos_ids = manifest["generation"]["eos_token_ids"]
            expected_contract = plan["protocol"].get("verification_contract_id")
            if expected_contract == NATIVE_VERIFICATION:
                if verification.get("verification_contract_id") != expected_contract or not all(
                        verification.get(key) is True for key in NATIVE_GATES):
                    raise ValueError("native generation verification contract/aggregate mismatch")
            elif expected_contract is not None or verification.get("verification_contract_id") is not None:
                raise ValueError("unknown or mixed generation verification contract")
            for record in records:
                ids = record["repeatability_prefix_32_token_ids"]
                if (not 1 <= len(ids) <= 32 or any(type(token) is not int for token in ids) or
                        (len(ids) < 32 and ids[-1] not in eos_ids)):
                    raise ValueError("repeatability prefix is incomplete without early EOS")
                if expected_contract == NATIVE_VERIFICATION:
                    validate_native_record(record, eos_ids, MODEL_BY_DIRECTORY[group["model"]].layers)
                    if any(type(record.get(key)) is not bool for key in ("greedy_16_equal", "logits_allclose")):
                        raise ValueError("cache on/off diagnostics must retain their actual boolean values")
                elif not all(record.get(key) is True for key in ("greedy_16_equal", "same_process_repeat_32_equal", "logits_allclose")):
                    raise ValueError("cache/repeat/logit validation failed")
                if record.get("atol") != .125 or record.get("rtol") != .01:
                    raise ValueError("cache verification tolerance changed")
                values[record["sample_id"]] = (record["prompt_sha256"], ids)
            prefixes.append(values)
        if prefixes[0] != prefixes[1]:
            raise ValueError("greedy prefixes differ across independent smoke/pilot processes")
        if gpu_uuids[0] != gpu_uuids[1]:
            raise ValueError("independent smoke/pilot repeatability used different GPU devices")
        sources.append({"model": group["model"], "case": group["case"], "gpu_uuid": gpu_uuids[0], **repeat})
    return {"passed": True, "pilot_gate": str(path), "pilot_gate_sha256": sha256_file(path), "groups": sources}


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def summarize(run_root: Path, plan_path: Path, output: Path, allow_partial: bool = False) -> dict[str, Any]:
    run_root, plan_path, output = run_root.resolve(), plan_path.resolve(), output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    plan = load_plan(plan_path)
    history, historical_evidence = load_history(plan, plan_path)
    requests = prepare_requests(plan_path, "formal")
    expected = {(spec.name, case) for spec in MODEL_SPECS for case in FIVE_CONFIG_CASES}
    if {(item["model"], item["case"]) for item in plan["matrix"]} != expected or len(plan["matrix"]) != 30:
        raise ValueError("plan matrix must have exactly six models x five cases")
    contract_path = run_root / "frozen_contract.json"
    contract = read_json(contract_path)
    sources_path = run_root / "formal_sources.json"
    selected = read_json(sources_path)["groups"] if sources_path.exists() else []
    keys = [(source["model"], source["case"]) for source in selected]
    if len(keys) != len(set(keys)) or not set(keys) <= expected:
        raise ValueError("formal source list has duplicate/unexpected model/case keys")
    qualification = validate_generation_qualification(run_root, plan) if selected else {
        "passed": False, "reason": "no formal groups selected; generation qualification pending"}
    oracle = HarnessOracle(plan["protocol"])
    results, source_records, errors = {}, [], []
    comparison_identity = None
    for source in selected:
        model, case = source["model"], source["case"]
        attempt = Path(source["attempt"])
        attempt = (attempt if attempt.is_absolute() else run_root / attempt).resolve()
        try:
            result, rescored, evidence = validate_group(attempt, model, case, plan, sha256_file(plan_path), requests,
                history[(model, case)]["run"], historical_evidence["numerical_code_hashes"], contract, oracle)
            if comparison_identity is not None and evidence["comparison_identity_sha256"] != comparison_identity:
                raise ValueError("formal groups do not share the same protocol/code/environment identity")
            comparison_identity = evidence["comparison_identity_sha256"]
            audit_path = output / "independent_scores" / model / f"{case}.jsonl"
            audit_path.parent.mkdir(parents=True, exist_ok=True)
            with audit_path.open("x", encoding="utf-8") as handle:
                for row in rescored:
                    handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            evidence.update(independent_scores=str(audit_path), independent_scores_sha256=sha256_file(audit_path))
            results[(model, case)] = result
            source_records.append(evidence)
        except Exception as exc:
            error = {"model": model, "case": case, "attempt": str(attempt), "accepted": False,
                     "error": f"{type(exc).__name__}: {exc}"}
            errors.append(error)
            source_records.append(error)
    missing = [{"model": model, "case": case} for model, case in sorted(expected - set(keys))]
    complete = len(results) == 30 and not errors and not missing
    summary_rows = [results[(spec.name, case)] for spec in MODEL_SPECS for case in FIVE_CONFIG_CASES if (spec.name, case) in results]
    write_csv(output / "gsm8k_summary.csv", summary_rows, ["model", "case", "model_fingerprint_sha256", "protocol_id",
        "n_expected", "n_completed", "correct_strict", "correct_flexible", "strict_em", "flexible_em",
        "strict_wilson95_low", "strict_wilson95_high", "invalid_strict", "length_capped", "output_tokens",
        "mean_seconds_per_example", "peak_memory_allocated_bytes", "model_load_attach_peak_memory_allocated_bytes",
        "full_split", "independent_harness_validated", "attempt"])
    deltas = []
    for row in summary_rows:
        baseline = results.get((row["model"], "bf16"))
        deltas.append({"model": row["model"], "case": row["case"], "strict_delta_pp":
            100 * (row["strict_em"] - baseline["strict_em"]) if baseline else "",
            "flexible_delta_pp": 100 * (row["flexible_em"] - baseline["flexible_em"]) if baseline else "",
            "paired_test_ids": 1319 if baseline else ""})
    write_csv(output / "gsm8k_delta.csv", deltas, ["model", "case", "strict_delta_pp", "flexible_delta_pp", "paired_test_ids"])
    write_csv(output / "six_task_with_gsm8k.csv", merge_rows(history, results), ["model", "case", "model_fingerprint_sha256",
        *TASKS, "macro_accuracy", "status", "gsm8k_full_split", "gsm8k_independent_harness_validated",
        "gsm8k_protocol_id", "gsm8k_attempt"])
    source_manifest = {"schema": "scalellm_gsm8k_merge_sources_v1", "plan": str(plan_path),
        "plan_sha256": sha256_file(plan_path), "formal_sources": str(sources_path),
        "formal_sources_sha256": sha256_file(sources_path) if sources_path.exists() else None,
        "frozen_contract": str(contract_path), "frozen_contract_sha256": sha256_file(contract_path),
        "historical": historical_evidence, "groups": source_records, "generation_qualification": qualification,
        "scoring_oracle": oracle.evidence,
        "summarizer_sha256": sha256_file(Path(__file__).resolve())}
    atomic_json(output / "source_manifest.json", source_manifest)
    validation = {"schema": "scalellm_gsm8k_independent_validation_v1", "created_at": datetime.now(timezone.utc).isoformat(),
        "full_validated": complete, "groups_expected": 30, "groups_validated": len(results),
        "formal_rows_expected": 39570, "formal_rows_validated": len(results) * 1319,
        "missing": missing, "errors": errors, "primary_metric": "exact_match,strict-match",
        "independent_oracle": oracle.evidence, "partial_display_requested": allow_partial,
        "source_manifest_sha256": sha256_file(output / "source_manifest.json"),
        "artifacts": {name: sha256_file(output / name) for name in
            ("gsm8k_summary.csv", "gsm8k_delta.csv", "six_task_with_gsm8k.csv")},
        "limitations": ["GSM8K source is the frozen local main export; no remote revision attestation",
                        "Wilson interval describes item-sampling uncertainty, not training-seed variance",
                        "Other five tasks use 0-shot likelihood context=2048; GSM8K uses the separate frozen 5-shot generation protocol",
                        "native_cache_call_parity_v2 validates the native cached call path; cache-on/off logits are not assumed equivalent. Original allclose(atol=.125,rtol=.01) and greedy16 results remain diagnostics, not passed gates"]}
    atomic_json(output / "validation.json", validation)
    if not complete and not allow_partial:
        raise ValueError(f"GSM8K matrix not fully validated: {len(results)}/30; see {output / 'validation.json'}")
    return validation


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--output", type=Path, help="New output directory, default run-root/merged")
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    result = summarize(args.run_root, args.plan, args.output or args.run_root / "merged", args.allow_partial)
    print(json.dumps({key: result[key] for key in ("full_validated", "groups_validated", "formal_rows_validated")}))


if __name__ == "__main__":
    main()
