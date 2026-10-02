#!/usr/bin/env python3
"""Canonical local-data tasks for the ScaleLLM ACC/PPL evaluation.

The task prompts and metrics in this module intentionally mirror
lm-evaluation-harness 0.4.11.  Datasets are read from fpga_llm_project/data so
that evaluation does not silently switch dataset revisions at run time.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable, Iterable


WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
DATA_ROOT = WORKSPACE_ROOT / "fpga_llm_project" / "data"

PROTOCOL_CONTEXT = {
    "literature_2048": 2048,
    "hardware_128": 128,
}

PRIMARY_METRIC = {
    "piqa": "acc_norm",
    "arc_easy": "acc_norm",
    "arc_challenge": "acc_norm",
    "boolq": "acc",
    "hellaswag": "acc_norm",
    "winogrande": "acc",
}

TASK_ORDER = tuple(PRIMARY_METRIC)


@dataclass(frozen=True)
class TaskSource:
    task: str
    path: Path
    split: str
    expected_rows: int
    source_id: str
    source_revision: str


TASK_SOURCES = {
    "piqa": TaskSource(
        "piqa",
        DATA_ROOT / "piqa" / "validation_full.jsonl",
        "validation",
        1838,
        "baber/piqa",
        "local validation export",
    ),
    "arc_easy": TaskSource(
        "arc_easy",
        DATA_ROOT / "lm_eval_standard" / "arc_easy_test.jsonl",
        "test",
        2376,
        "allenai/ai2_arc:ARC-Easy",
        "210d026faf9955653af8916fad021475a3f00453",
    ),
    "arc_challenge": TaskSource(
        "arc_challenge",
        DATA_ROOT / "lm_eval_standard" / "arc_challenge_test.jsonl",
        "test",
        1172,
        "allenai/ai2_arc:ARC-Challenge",
        "210d026faf9955653af8916fad021475a3f00453",
    ),
    "boolq": TaskSource(
        "boolq",
        DATA_ROOT / "bape_eval" / "raw" / "boolq" / "validation.parquet",
        "validation",
        3270,
        "aps/super_glue:boolq",
        "local validation export",
    ),
    "hellaswag": TaskSource(
        "hellaswag",
        DATA_ROOT / "hellaswag" / "hellaswag_val.jsonl",
        "validation",
        10042,
        "Rowan/hellaswag",
        "local validation export",
    ),
    "winogrande": TaskSource(
        "winogrande",
        DATA_ROOT
        / "winogrande"
        / "winogrande_1.1"
        / "winogrande_1.1"
        / "dev.jsonl",
        "validation",
        1267,
        "allenai/winogrande:winogrande_xl",
        "winogrande_1.1 dev",
    ),
}

WIKITEXT_SOURCE = DATA_ROOT / "wikitext-2-raw-v1" / "test-00000-of-00001.jsonl"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise TypeError(f"{path}:{line_number} is not a JSON object")
            rows.append(value)
    return rows


def load_rows(source: TaskSource) -> list[dict[str, Any]]:
    if not source.path.exists():
        raise FileNotFoundError(
            f"missing canonical {source.task} {source.split} split: {source.path}. "
            "Run prepare_standard_data.py first."
        )
    if source.path.suffix == ".parquet":
        from datasets import Dataset

        rows = [dict(row) for row in Dataset.from_parquet(str(source.path))]
    else:
        rows = _read_jsonl(source.path)
    if len(rows) != source.expected_rows:
        raise ValueError(
            f"{source.task} row count mismatch: got {len(rows)}, "
            f"expected {source.expected_rows} for official {source.split}"
        )
    return rows


def data_manifest(tasks: Iterable[str], include_wikitext: bool = False) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    for task in tasks:
        source = TASK_SOURCES[task]
        rows = load_rows(source)
        manifest.append(
            {
                "task": task,
                "path": str(source.path.resolve()),
                "split": source.split,
                "rows": len(rows),
                "expected_rows": source.expected_rows,
                "source_id": source.source_id,
                "source_revision": source.source_revision,
                "sha256": sha256_file(source.path),
                "primary_metric": PRIMARY_METRIC[task],
            }
        )
    if include_wikitext:
        if not WIKITEXT_SOURCE.exists():
            raise FileNotFoundError(WIKITEXT_SOURCE)
        manifest.append(
            {
                "task": "wikitext2",
                "path": str(WIKITEXT_SOURCE.resolve()),
                "split": "test",
                "source_id": "Salesforce/wikitext:wikitext-2-raw-v1",
                "sha256": sha256_file(WIKITEXT_SOURCE),
            }
        )
    return manifest


def _arc_target(doc: dict[str, Any]) -> int:
    labels = [str(value) for value in doc["choices"]["label"]]
    answer = str(doc["answerKey"])
    # Mirrors the official Jinja expression choices.label.index(answerKey).
    return labels.index(answer)


def _hellaswag_preprocess(text: str) -> str:
    # Exact cleaning used by lm-evaluation-harness 0.4.11.
    text = text.strip().replace(" [title]", ". ")
    text = re.sub(r"\[.*?\]", "", text)
    return text.replace("  ", " ")


def _hellaswag_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    processed = []
    for doc in rows:
        ctx = str(doc["ctx_a"]) + " " + str(doc["ctx_b"]).capitalize()
        processed.append(
            {
                "query": _hellaswag_preprocess(
                    str(doc["activity_label"]) + ": " + ctx
                ),
                "choices": [
                    _hellaswag_preprocess(str(ending))
                    for ending in doc["endings"]
                ],
                "gold": int(doc["label"]),
            }
        )
    return processed


def _winogrande_text(doc: dict[str, Any]) -> int:
    return {"1": 0, "2": 1}[str(doc["answer"])]


def _winogrande_target(doc: dict[str, Any]) -> str:
    index = str(doc["sentence"]).index("_") + 1
    return str(doc["sentence"])[index:].strip()


def _winogrande_choices(doc: dict[str, Any]) -> list[str]:
    sentence = str(doc["sentence"])
    index = sentence.index("_")
    return [sentence[:index] + str(doc["option1"]), sentence[:index] + str(doc["option2"])]


def _custom_dataset_factory(split: str, rows: list[dict[str, Any]]) -> Callable[..., Any]:
    def factory(**_: Any) -> Any:
        from datasets import Dataset, DatasetDict

        return DatasetDict({split: Dataset.from_list(rows)})

    return factory


def build_task(task: str) -> Any:
    """Build an lm_eval ConfigurableTask backed only by canonical local data."""
    if task not in TASK_SOURCES:
        raise KeyError(f"unsupported ACC task: {task}")
    from lm_eval.api.task import ConfigurableTask

    source = TASK_SOURCES[task]
    rows = load_rows(source)
    split_kwargs = (
        {"test_split": source.split}
        if source.split == "test"
        else {"validation_split": source.split}
    )
    metrics = [{"metric": "acc", "aggregation": "mean", "higher_is_better": True}]
    if task in {"piqa", "arc_easy", "arc_challenge", "hellaswag"}:
        metrics.append(
            {"metric": "acc_norm", "aggregation": "mean", "higher_is_better": True}
        )

    common: dict[str, Any] = {
        "task": task,
        "custom_dataset": _custom_dataset_factory(source.split, rows),
        "output_type": "multiple_choice",
        "metric_list": metrics,
        "num_fewshot": 0,
        "metadata": {
            "version": 2.0 if task == "boolq" else 1.0,
            "local_source": str(source.path.resolve()),
            "lm_eval_compatibility": "0.4.11",
        },
        **split_kwargs,
    }

    if task == "piqa":
        common.update(
            doc_to_text=lambda doc: f"Question: {doc['goal']}\nAnswer:",
            doc_to_target=lambda doc: int(doc["label"]),
            doc_to_choice=lambda doc: [str(doc["sol1"]), str(doc["sol2"])],
            should_decontaminate=True,
            doc_to_decontamination_query="goal",
        )
    elif task in {"arc_easy", "arc_challenge"}:
        common.update(
            doc_to_text=lambda doc: f"Question: {doc['question']}\nAnswer:",
            doc_to_target=_arc_target,
            doc_to_choice=lambda doc: [str(value) for value in doc["choices"]["text"]],
            should_decontaminate=True,
            doc_to_decontamination_query="Question: {{question}}\nAnswer:",
        )
    elif task == "boolq":
        common.update(
            doc_to_text=lambda doc: (
                f"{doc['passage']}\nQuestion: {doc['question']}?\nAnswer:"
            ),
            doc_to_target=lambda doc: int(bool(doc["answer"])),
            doc_to_choice=["no", "yes"],
            should_decontaminate=True,
            doc_to_decontamination_query="passage",
        )
    elif task == "hellaswag":
        processed = _hellaswag_rows(rows)
        common["custom_dataset"] = _custom_dataset_factory(source.split, processed)
        common.update(
            doc_to_text=lambda doc: str(doc["query"]),
            doc_to_target=lambda doc: int(doc["gold"]),
            doc_to_choice=lambda doc: [str(value) for value in doc["choices"]],
        )
    elif task == "winogrande":
        common.update(
            doc_to_text=_winogrande_text,
            doc_to_target=_winogrande_target,
            doc_to_choice=_winogrande_choices,
            should_decontaminate=True,
            doc_to_decontamination_query="sentence",
        )
    return ConfigurableTask(config=common)


def read_wikitext() -> str:
    texts = [str(row.get("text", "")) for row in _read_jsonl(WIKITEXT_SOURCE)]
    return "\n\n".join(text for text in texts if text.strip())


def validate_protocol(protocol: str, case: str, limit: int | None) -> dict[str, Any]:
    if protocol not in PROTOCOL_CONTEXT:
        raise ValueError(f"unknown protocol {protocol!r}")
    valid_cases = {
        "bf16",
        "a8w8_fp32",
        "a8w4_fp32",
        "a8w4_fp16",
        "reference_qdq",
        "v5_attention",
        "v5_mlp",
        "v5_mlp_down_s32_ablation",
        "v5_mlp_down_s32_shift12_ablation",
        "v5",
        "v5_down_s32_ablation",
        "v5_algorithm",
    }
    if case not in valid_cases:
        raise ValueError(f"unknown case {case!r}")
    if case in {
        "v5_attention", "v5_mlp", "v5_mlp_down_s32_ablation",
        "v5_mlp_down_s32_shift12_ablation",
        "v5", "v5_down_s32_ablation", "v5_algorithm"
    } and protocol != "hardware_128":
        raise ValueError(
            "V5 Attention and RoPE are limited to positions 0..127; "
            "a V5 or V5-algorithm literature_2048 result would not be valid."
        )
    return {
        "protocol": protocol,
        "context_length": PROTOCOL_CONTEXT[protocol],
        "case": case,
        "zero_shot": True,
        "full_split": limit is None,
        "literature_comparable": protocol == "literature_2048" and limit is None,
        "hardware_constrained": protocol == "hardware_128",
        "overlength_continuation_policy": (
            "rolling_windows_score_all_choice_tokens"
            if protocol == "hardware_128"
            else "lm_eval_default"
        ),
    }
