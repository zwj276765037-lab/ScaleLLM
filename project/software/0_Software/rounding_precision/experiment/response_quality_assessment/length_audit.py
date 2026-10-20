"""CPU-only exact first-turn template counts and bounded multi-turn reserves."""
import argparse
from collections import Counter
import json
from pathlib import Path

try:
    from .common import identity, read_jsonl, text_sha, write_json
except ImportError:
    from common import identity, read_jsonl, text_sha, write_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prompts", type=Path, required=True)
    p.add_argument("--model-dir", type=Path, required=True)
    p.add_argument("--context-length", type=int, default=2048)
    p.add_argument("--max-new-tokens", type=int, default=512)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(str(a.model_dir), local_files_only=True, trust_remote_code=False)
    rows = []
    for row in read_jsonl(a.prompts):
        messages = []
        turns = []
        for i, user in enumerate(row["turns"]):
            messages.append({"role": "user", "content": user})
            rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            empty_history_tokens = len(tokenizer(rendered, add_special_tokens=False)["input_ids"])
            # Actual earlier answers are unknown. Each is capped at max_new_tokens.
            # Retokenization boundaries can add a few tokens; this is a planning
            # envelope, not a proof. The generation runner must check actual IDs.
            budget = empty_history_tokens + (i + 1) * a.max_new_tokens
            turns.append({"turn_index": i, "template_tokens_with_empty_prior_answers": empty_history_tokens,
                          "prior_answers_reserved_tokens": i * a.max_new_tokens,
                          "total_planned_tokens": budget, "exceeds_planned_context": budget > a.context_length})
            messages.append({"role": "assistant", "content": ""})
        rows.append({"prompt_id": row["prompt_id"], "dataset": row["dataset"], "turns": turns})
    grouped = {}
    for dataset in sorted({r["dataset"] for r in rows}):
        selected = [r for r in rows if r["dataset"] == dataset]
        first = sorted(r["turns"][0]["template_tokens_with_empty_prior_answers"] for r in selected)
        budgets = sorted(max(t["total_planned_tokens"] for t in r["turns"]) for r in selected)
        grouped[dataset] = {"questions": len(selected), "first_turn_min": first[0], "first_turn_max": first[-1],
            "first_turn_median": first[len(first)//2], "planned_context_max": budgets[-1],
            "over_context_questions": sum(any(t["exceeds_planned_context"] for t in r["turns"]) for r in selected)}
    out = {"schema": "scalellm_response_length_audit_v1", "execution_state": "completed", "model_forward": False,
        "context_length": a.context_length, "max_new_tokens_per_turn": a.max_new_tokens,
        "template": "apply_chat_template(tokenize=False,add_generation_prompt=True), then tokenize(add_special_tokens=False)",
        "multi_turn_note": "Reserves capped unknown answers; final runner must check actual prompt+history IDs. No truncation or question exclusion authorized.",
        "sources": [identity(a.prompts)] + [identity(a.model_dir / name) for name in ("tokenizer.json", "tokenizer_config.json", "special_tokens_map.json") if (a.model_dir / name).exists()],
        "chat_template_sha256": text_sha(tokenizer.chat_template), "summary": grouped, "questions": rows,
        "code_identity": identity(__file__)}
    write_json(a.output, out)
    print(json.dumps(grouped))


if __name__ == "__main__":
    main()
