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


DEFAULT_PLAN = (
    Path(__file__).resolve().parents[1]
    / "source/gsm8k_completion_plan_20261018/plan.json"
)
STRICT_REGEX = r"#### (\-?[0-9\.\,]+)"
FLEXIBLE_REGEX = r"(-?[$0-9.,]{2,})|(-?[0-9]+)"
NORMALIZATION_REGEXES = (",", r"\$", r"(?s).*#### ", r"\.$")
INVALID = "[invalid]"
STAGES = {"smoke": ("train", 4), "pilot": ("train", 32), "formal": ("test", 1319)}


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
