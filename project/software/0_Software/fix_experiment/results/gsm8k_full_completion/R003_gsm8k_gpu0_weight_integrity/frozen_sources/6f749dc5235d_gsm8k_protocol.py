#!/usr/bin/env python3
"""Frozen local GSM8K requests and lm-evaluation-harness 0.4.11 scoring.

This module uses only the Python standard library. It never downloads data,
loads model weights, applies a chat template, or reads the evaluated answer
while building a prompt. Dataset and few-shot bytes are checked on every
preparation call so a resumed worker cannot silently switch its inputs.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any
import uuid


DEFAULT_PLAN = (
    Path(__file__).resolve().parents[1]
    / "source/gsm8k_completion_plan_20261018/plan.json"
)
STRICT_REGEX = r"#### (\-?[0-9\.\,]+)"
FLEXIBLE_REGEX = r"(-?[$0-9.,]{2,})|(-?[0-9]+)"
NORMALIZATION_REGEXES = (",", r"\$", r"(?s).*#### ", r"\.$")
INVALID = "[invalid]"
STAGES = {"smoke": ("train", 4), "pilot": ("train", 32), "formal": ("test", 1319)}
INTEGRITY_CONTRACT_ID = "checkpoint_static_content_v1"


def integrity_contract_id(plan: dict[str, Any]) -> str | None:
    value = plan["protocol"].get("integrity_contract_id")
    if value not in (None, INTEGRITY_CONTRACT_ID):
        raise ValueError("unsupported weight integrity contract")
    return value


def validate_integrity_evidence(directory: str | Path, manifest: dict[str, Any],
                                expected_contract: str | None, *, sample_ids: list[str],
                                expected_gpu: str | None = None,
                                summary: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Validate complete static-content evidence, never merely its success flag.

    Legacy runs remain readable without gaining the new qualification. R003
    partial/failed attempts cannot supply rows or stage-completion evidence.
    """
    identity = manifest.get("identity", {})
    if expected_contract is None:
        if identity.get("integrity_contract_id") is not None or manifest.get("integrity") is not None:
            raise ValueError("mixed legacy and weight-integrity evidence")
        return None
    if expected_contract != INTEGRITY_CONTRACT_ID or identity.get("integrity_contract_id") != expected_contract:
        raise ValueError("weight integrity contract differs from frozen identity")
    if manifest.get("state") != "complete":
        raise ValueError("weight-integrity reuse requires a complete attempt")
    reference = manifest.get("integrity", {})
    directory = Path(directory)
    if (reference.get("path") != "integrity.json" or reference.get("contract_id") != expected_contract or
            reference.get("qualified") is not True):
        raise ValueError("missing completed integrity reference")
    file = directory / "integrity.json"
    digest = sha256_file(file)
    if reference.get("sha256") != digest or manifest.get("artifacts", {}).get("integrity.json") != digest:
        raise ValueError("integrity artifact hash mismatch")
    if summary is not None and summary.get("integrity") != reference:
        raise ValueError("summary integrity reference differs from manifest")
    data = json.loads(file.read_text())
    if (data.get("schema") != "scalellm_gsm8k_weight_integrity_v1" or data.get("state") != "complete" or
            data.get("qualified") is not True or data.get("contract_id") != expected_contract):
        raise ValueError("weight integrity evidence is incomplete or failed")
    for key in ("plan_sha256", "stage", "case", "model_fingerprint_sha256"):
        if data.get("identity", {}).get(key) != identity.get(key) or identity.get(key) is None:
            raise ValueError(f"integrity execution identity mismatch: {key}")
    def gpu(value):
        try:
            return str(uuid.UUID(value.lower().removeprefix("gpu-")))
        except (ValueError, AttributeError) as exc:
            raise ValueError("integrity lacks an actual full GPU UUID") from exc
    device = gpu(manifest.get("environment", {}).get("gpu_uuid"))
    if (gpu(data["identity"].get("gpu_uuid")) != device or
            gpu(manifest.get("environment", {}).get("CUDA_VISIBLE_DEVICES")) != device or
            manifest.get("environment", {}).get("device") != "cuda:0" or
            (expected_gpu is not None and gpu(expected_gpu) != device)):
        raise ValueError("integrity device identity differs from frozen allocation")
    codes = identity.get("code_sha256", {})
    if not {"gsm8k_weight_integrity.py", "run_eval_worker.py", "run_gsm8k_worker.py", "gsm8k_protocol.py"} <= {Path(p).name for p in codes}:
        raise ValueError("integrity implementation source coverage is incomplete")
    helper_hashes = {digest for path, digest in codes.items() if Path(path).name == "gsm8k_weight_integrity.py"}
    if len(helper_hashes) != 1 or data.get("source_sha256") not in helper_hashes:
        raise ValueError("integrity helper source identity mismatch")
    coverage = data.get("coverage", {})
    def names(value, label):
        if (not isinstance(value, list) or any(not isinstance(v, str) or not v for v in value) or
                len(set(value)) != len(value)):
            raise ValueError(f"invalid or duplicate integrity names: {label}")
        return set(value)
    sets = {key: names(coverage.get(key), key) for key in (
        "checkpoint_names", "checkpoint_tensor_names", "cpu_checked_names", "gpu_checked_names",
        "effective_static_names", "qdq_expected_names", "qdq_rebuilt_names", "external_cache_names")}
    if (not sets["checkpoint_names"] or not sets["checkpoint_tensor_names"] or not sets["effective_static_names"] or
            sets["checkpoint_names"] != sets["cpu_checked_names"] or
            sets["checkpoint_names"] != sets["gpu_checked_names"] or
            not sets["checkpoint_names"] <= sets["effective_static_names"] or
            sets["qdq_expected_names"] != sets["qdq_rebuilt_names"] or
            not (sets["qdq_expected_names"] | sets["external_cache_names"]) <= sets["effective_static_names"]):
        raise ValueError("integrity input/effective-static coverage is incomplete")
    key_map = data.get("checkpoint_key_map", {})
    if (not isinstance(key_map, dict) or any(v is not None and (not isinstance(v, str) or not v) for v in key_map.values()) or
            set(key_map) != sets["checkpoint_names"] or
            {v for v in key_map.values() if v is not None} != sets["checkpoint_tensor_names"]):
        raise ValueError("integrity checkpoint tensor key coverage is incomplete")
    def inventory(value, expected, label):
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError(f"integrity manifest coverage differs: {label}")
        for desc in value.values():
            if (not isinstance(desc, dict) or not re.fullmatch(r"[0-9a-f]{64}", str(desc.get("sha256"))) or
                    not isinstance(desc.get("shape"), list) or any(type(x) is not int or x < 0 for x in desc["shape"]) or
                    not isinstance(desc.get("dtype"), str) or not desc["dtype"] or
                    not isinstance(desc.get("role"), str) or not desc["role"]):
                raise ValueError(f"invalid integrity tensor descriptor: {label}")
        return canonical_hash(value)
    checkpoint_root = inventory(data.get("checkpoint_manifest"), sets["checkpoint_names"], "checkpoint")
    baseline = data.get("baseline_manifest")
    baseline_root = inventory(baseline, sets["effective_static_names"], "effective static")
    if data.get("baseline_root_sha256") != baseline_root or reference.get("baseline_root_sha256") != baseline_root:
        raise ValueError("integrity baseline content/hash mismatch")
    if identity.get("case") == "bf16":
        if sets["qdq_expected_names"]:
            raise ValueError("BF16 evidence unexpectedly contains QDQ rebuilds")
    elif not sets["qdq_expected_names"] or not sets["external_cache_names"]:
        raise ValueError("QDQ evidence lacks rebuilt weights or Hadamard cache coverage")
    for name in sets["checkpoint_names"] - sets["qdq_expected_names"]:
        if any(baseline[name][key] != data["checkpoint_manifest"][name][key]
               for key in ("sha256", "shape", "dtype")):
            raise ValueError("unchanged native static tensor differs from trusted checkpoint")
    if {name for name, desc in baseline.items() if desc["role"] == "external_cache"} != sets["external_cache_names"]:
        raise ValueError("external static cache inventory is incomplete")
    reconstructions = data.get("qdq_reconstruction")
    if not isinstance(reconstructions, list):
        raise ValueError("QDQ reconstruction evidence is missing")
    rebuilt_names = set()
    modules = []
    for record in reconstructions:
        module = record.get("module")
        if not isinstance(module, str) or not module or module in modules:
            raise ValueError("duplicate/invalid QDQ reconstruction module")
        modules.append(module)
        weight = module + ".weight"
        if (weight not in data["checkpoint_manifest"] or record.get("source_key") != key_map[weight] or
                record.get("source_shape") != data["checkpoint_manifest"][weight]["shape"] or
                record.get("fullshape") is not True or record.get("device") != "cuda:0" or
                record.get("class") not in {"ScalePathIAHScaleCodeLinear", "ScalePathIAHFP16ScaleLinear", "ScalePathIAHFP32ScaleLinear"}):
            raise ValueError("QDQ reconstruction differs from trusted source/full shape")
        tensors = record.get("tensors")
        if (not isinstance(tensors, dict) or weight not in tensors or
                any(name not in {weight, module + ".bias"} or baseline.get(name) != desc for name, desc in tensors.items()) or
                rebuilt_names & set(tensors)):
            raise ValueError("QDQ reconstruction tensor coverage/content mismatch")
        rebuilt_names.update(tensors)
    if rebuilt_names != sets["qdq_expected_names"] - sets["external_cache_names"]:
        raise ValueError("QDQ reconstruction does not cover every effective weight/bias")
    if identity.get("case") != "bf16":
        method = identity.get("method", {})
        expected_modules = names(method.get("live_qdq_projection_names"), "live QDQ modules")
        if set(modules) != expected_modules or len(modules) != method.get("module_count"):
            raise ValueError("QDQ reconstruction lacks complete live projection coverage")
    phases = data.get("phase_checks")
    if not isinstance(phases, list) or not phases:
        raise ValueError("integrity phase checks are missing")
    checks = directory / "integrity_checks.jsonl"
    if sha256_file(checks) != data.get("checks_jsonl_sha256"):
        raise ValueError("integrity phase log hash mismatch")
    raw = checks.read_bytes()
    if not raw.endswith(b"\n") or any(not line.strip() for line in raw.splitlines()):
        raise ValueError("integrity phase log is incomplete")
    if [json.loads(line) for line in raw.splitlines()] != phases:
        raise ValueError("integrity phase contents differ from hashed log")
    expected_labels = ["cpu_loaded", "gpu_loaded", "qdq_rebuild", "setup_complete"]
    if identity.get("stage") in {"smoke", "pilot"}:
        expected_labels += ["verification_before", "verification_after"]
    if len(set(sample_ids)) != len(sample_ids):
        raise ValueError("duplicate expected integrity sample IDs")
    expected_labels += [f"sample:{sid}:{side}" for sid in sample_ids for side in ("before", "after")]
    expected_labels += ["stage_complete"]
    if [p.get("label") for p in phases] != expected_labels:
        raise ValueError("integrity phases do not cover all calls and stage completion in order")
    qdq_root = canonical_hash({name: baseline[name] for name in sorted(sets["qdq_expected_names"])})
    for phase in phases:
        label = phase["label"]
        expected_names, expected_root = sets["effective_static_names"], baseline_root
        if label in {"cpu_loaded", "gpu_loaded"}:
            expected_names, expected_root = sets["checkpoint_names"], checkpoint_root
        elif label == "qdq_rebuild":
            expected_names, expected_root = sets["qdq_expected_names"], qdq_root
        if (phase.get("complete") is not True or phase.get("exact") is not True or
                any(phase.get(key) for key in ("missing_names", "unexpected_names", "changed_names", "identity_errors")) or
                names(phase.get("checked_names"), label) != expected_names or
                phase.get("observed_root_sha256") != expected_root or
                (label in {"cpu_loaded", "gpu_loaded", "qdq_rebuild"} and phase.get("trusted_root_sha256") != expected_root)):
            raise ValueError(f"integrity phase content/coverage failed: {label}")
    return reference


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(obj: Any) -> str:
    """Hash UTF-8 compact sorted JSON (including Unicode without ASCII escapes)."""
    payload = json.dumps(
        obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def atomic_json(path: str | Path, obj: Any) -> None:
    """Durably replace one JSON file without leaving partial records."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(obj, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def resolve_input_path(plan_path: str | Path, value: str) -> Path:
    """Resolve both live absolute inputs and portable snapshot-relative inputs."""
    path = Path(value).expanduser()
    return (path if path.is_absolute() else Path(plan_path).resolve().parent / path).resolve()


def load_plan(path: str | Path = DEFAULT_PLAN) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        plan = json.load(handle)
    if plan.get("schema") != "scalellm_gsm8k_completion_plan_v1":
        raise ValueError("unsupported GSM8K plan schema")
    protocol = plan["protocol"]
    integrity_contract_id(plan)
    required = {
        "num_fewshot": 5,
        "doc_to_text": "Question: {{question}}\nAnswer:",
        "doc_to_target": "{{answer}}",
        "target_delimiter": " ",
        "fewshot_delimiter": "\n\n",
        "apply_chat_template": False,
        "system_prompt": "",
        "strict_regex": STRICT_REGEX,
        "strict_group_select": 0,
        "flexible_regex": FLEXIBLE_REGEX,
        "flexible_group_select": -1,
        "normalization_regexes": list(NORMALIZATION_REGEXES),
        "invalid_value": INVALID,
        "ignore_case": True,
        "ignore_punctuation": False,
    }
    for key, expected in required.items():
        if protocol.get(key) != expected:
            raise ValueError(f"unsupported GSM8K protocol {key}: {protocol.get(key)!r}")
    if plan["data"]["formal_split"] != "test" or plan["data"]["formal_examples_per_group"] != 1319:
        raise ValueError("formal GSM8K evaluation must contain all 1319 test rows")
    if plan["data"]["field_mapping"] != {
        "question": "instruction", "answer": "output", "system": "assert empty", "input": "assert empty"
    }:
        raise ValueError("unsupported dataset field mapping")
    return plan


def load_verified_inputs(plan_path: str | Path = DEFAULT_PLAN) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Load exact local bytes, reject changed metadata, rows, or schedules."""
    plan = load_plan(plan_path)
    root = resolve_input_path(plan_path, plan["data"]["root"])
    datasets = {}
    for split, expected_rows in (("train", 7473), ("test", 1319)):
        path = root / f"{split}.jsonl"
        observed = sha256_file(path)
        expected = plan["data"]["dataset_hashes"][split]
        if observed != expected:
            raise ValueError(f"{split} dataset SHA-256 mismatch: {observed} != {expected}")
        with path.open(encoding="utf-8") as handle:
            raw_rows = [json.loads(line) for line in handle if line.strip()]
        if len(raw_rows) != expected_rows:
            raise ValueError(f"{split} row count mismatch: {len(raw_rows)} != {expected_rows}")
        rows = []
        for index, row in enumerate(raw_rows):
            if row.get("system") != "" or row.get("input") != "":
                raise ValueError(f"nonempty system/input at {split}:{index}")
            if (row.get("source"), row.get("config"), row.get("split")) != ("openai/gsm8k", "main", split):
                raise ValueError(f"dataset metadata mismatch at {split}:{index}")
            if not isinstance(row.get("instruction"), str) or not isinstance(row.get("output"), str):
                raise TypeError(f"question/answer must be strings at {split}:{index}")
            rows.append({"question": row["instruction"], "answer": row["output"]})
        datasets[split] = rows
    protocol = plan["protocol"]
    schedule_path = resolve_input_path(plan_path, protocol["fewshot_schedule_file"])
    if sha256_file(schedule_path) != protocol["fewshot_schedule_sha256"]:
        raise ValueError("few-shot schedule SHA-256 mismatch")
    with schedule_path.open(encoding="utf-8") as handle:
        schedule = json.load(handle)
    if schedule["seed"] != protocol["seed"] or schedule["index_base"] != 0:
        raise ValueError("few-shot schedule seed/index mismatch")
    for split in ("train", "test"):
        if schedule[f"{split}_sha256"] != plan["data"]["dataset_hashes"][split]:
            raise ValueError(f"few-shot schedule {split} identity mismatch")
    for stage, (split, count) in STAGES.items():
        entries = schedule["formal" if stage == "formal" else "pilot"][:count]
        if len(entries) != count:
            raise ValueError(f"incomplete few-shot schedule for {stage}")
        index_key = "test_row_index" if split == "test" else "train_row_index"
        for index, entry in enumerate(entries):
            indices = entry["train_row_indices"]
            if entry["sample_id"] != f"{split}:{index:04d}" or entry[index_key] != index:
                raise ValueError(f"few-shot schedule row order mismatch at {stage}:{index}")
            if len(indices) != 5 or len(set(indices)) != 5 or any(type(i) is not int or not 0 <= i < 7473 for i in indices):
                raise ValueError(f"invalid few-shot indices at {stage}:{index}")
            if split == "train" and index in indices:
                raise ValueError(f"train evaluated row leaks into few-shot context at {stage}:{index}")
    return plan, datasets, schedule


def build_prompt(question: str, train_rows: list[dict[str, Any]], fewshot_indices: list[int]) -> str:
    """Build a raw prompt from a question and train demonstrations only."""
    demonstrations = [
        f"Question: {train_rows[index]['question']}\nAnswer: {train_rows[index]['answer']}"
        for index in fewshot_indices
    ]
    return "\n\n".join([*demonstrations, f"Question: {question}\nAnswer:"])


def prepare_requests(plan_path: str | Path = DEFAULT_PLAN, stage: str = "formal") -> list[dict[str, Any]]:
    if stage not in STAGES:
        raise ValueError(f"unknown stage {stage!r}; expected smoke, pilot, or formal")
    _, datasets, schedule = load_verified_inputs(plan_path)
    split, count = STAGES[stage]
    entries = schedule["formal" if stage == "formal" else "pilot"][:count]
    requests = []
    for index, entry in enumerate(entries):
        row = datasets[split][index]
        indices = list(entry["train_row_indices"])
        prompt = build_prompt(row["question"], datasets["train"], indices)
        requests.append({
            "sample_id": entry["sample_id"],
            "row_index": index,
            "split": split,
            "question": row["question"],
            "question_sha256": hashlib.sha256(row["question"].encode("utf-8")).hexdigest(),
            "gold": row["answer"],
            "prompt": prompt,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "fewshot_train_indices": indices,
        })
    return requests


def normalize_answer(text: str) -> str:
    for pattern in NORMALIZATION_REGEXES:
        text = re.sub(pattern, "", text)
    return text.lower()


def _extract(response: Any, pattern: str, group_select: int) -> str:
    # RegexFilter.apply treats nonstrings as empty responses.
    matches = re.findall(pattern, response if isinstance(response, str) else "")
    if not matches:
        return INVALID
    match = matches[group_select]
    if isinstance(match, tuple):
        nonempty = [value for value in match if value]
        match = nonempty[0] if nonempty else INVALID
    return match.strip()


def score_response(response: str, gold: str) -> dict[str, Any]:
    strict = _extract(response, STRICT_REGEX, 0)
    flexible = _extract(response, FLEXIBLE_REGEX, -1)
    normalized_gold = normalize_answer(gold)
    return {
        "strict_prediction": strict,
        "flexible_prediction": flexible,
        "normalized_gold": normalized_gold,
        "correct_strict": normalize_answer(strict) == normalized_gold,
        "correct_flexible": normalize_answer(flexible) == normalized_gold,
        "invalid_strict": strict == INVALID,
    }
