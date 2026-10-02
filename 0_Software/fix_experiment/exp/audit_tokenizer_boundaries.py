#!/usr/bin/env python3
"""Audit lm-eval context/continuation token boundaries for one checkpoint."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from transformers import AutoTokenizer

from protocol import TASK_ORDER, build_task
from run_eval_worker import tokenizer_boundary_safe_hflm_class
from six_model_matrix import get_model_spec


class TokenizerOnlyLM:
    backend = "causal"

    def __init__(self, tokenizer: Any) -> None:
        self.tokenizer = tokenizer

    def tok_encode(
        self, text: str, add_special_tokens: bool | None = None
    ) -> list[int]:
        kwargs = (
            {} if add_special_tokens is None
            else {"add_special_tokens": add_special_tokens}
        )
        return self.tokenizer.encode(text, **kwargs)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--model-identity", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary.replace(path)


def main() -> None:
    args = parse_args()
    model = args.model.resolve()
    spec = get_model_spec(model)
    identity = json.loads(args.model_identity.resolve().read_text(encoding="utf-8"))
    if identity.get("checkpoint_name") != spec.name:
        raise ValueError("model identity does not match tokenizer audit checkpoint")
    tokenizer = AutoTokenizer.from_pretrained(
        model, local_files_only=True, trust_remote_code=True
    )
    lm = tokenizer_boundary_safe_hflm_class(TokenizerOnlyLM)(tokenizer)
    per_task: dict[str, dict[str, int]] = {}
    total_requests = 0
    total_fallback = 0
    for task_name in TASK_ORDER:
        task = build_task(task_name)
        task.build_all_requests(
            limit=None,
            rank=0,
            world_size=1,
            cache_requests=False,
            tokenizer_name=str(tokenizer.name_or_path),
        )
        requests = 0
        fallback_requests = 0
        fallback_documents: set[int] = set()
        for instance in task.instances:
            if instance.request_type != "loglikelihood":
                continue
            context, continuation = instance.args
            if context:
                _context_ids, continuation_ids = lm._encode_pair(
                    context, continuation
                )
            else:
                continuation_ids = lm.tok_encode(
                    continuation, add_special_tokens=False
                )
                lm._last_boundary_fallback = False
            if not continuation_ids:
                raise ValueError(
                    f"empty continuation after boundary fix: {task_name}/{instance.doc_id}"
                )
            requests += 1
            if lm._last_boundary_fallback:
                fallback_requests += 1
                if instance.doc_id is not None:
                    fallback_documents.add(int(instance.doc_id))
        per_task[task_name] = {
            "requests": requests,
            "fallback_requests": fallback_requests,
            "fallback_documents": len(fallback_documents),
            "empty_continuations_after_fix": 0,
        }
        total_requests += requests
        total_fallback += fallback_requests
    value = {
        "schema": "scalellm_tokenizer_boundary_audit_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "checkpoint_name": spec.name,
        "model_fingerprint_sha256": identity["fingerprint_sha256"],
        "policy": "fixed_context_independent_continuation_fallback_v1",
        "total_requests": total_requests,
        "fallback_requests": total_fallback,
        "empty_continuations_after_fix": 0,
        "per_task": per_task,
    }
    atomic_json(args.output.resolve(), value)
    print(json.dumps(value, ensure_ascii=False))


if __name__ == "__main__":
    main()
