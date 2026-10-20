"""Pin official public text; preserve prompts and supplied answers separately.

No Hugging Face dataset code is executed. The comparison reference is always
our OUTPUT_ONLY arm; downloaded model answers are neither that arm nor gold.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import urllib.request

try:
    from .common import identity, json_sha, text_sha, write_json, write_jsonl
except ImportError:
    from common import identity, json_sha, text_sha, write_json, write_jsonl

ALPACA_REV = "2edc6fad8be6b14ea7230aabfd08188da6b8b814"
MT_REV = "587d5cfa1609a43d192cedb8441cac3c17db105d"
SOURCES = {
    "alpaca_eval/alpaca_eval.json": f"https://huggingface.co/datasets/tatsu-lab/alpaca_eval/resolve/{ALPACA_REV}/alpaca_eval.json",
    "alpaca_eval/README.md": f"https://huggingface.co/datasets/tatsu-lab/alpaca_eval/resolve/{ALPACA_REV}/README.md",
    "mt_bench/question.jsonl": f"https://raw.githubusercontent.com/lm-sys/FastChat/{MT_REV}/fastchat/llm_judge/data/mt_bench/question.jsonl",
    "mt_bench/gpt-4_reference_answer.jsonl": f"https://raw.githubusercontent.com/lm-sys/FastChat/{MT_REV}/fastchat/llm_judge/data/mt_bench/reference_answer/gpt-4.jsonl",
    "mt_bench/LICENSE": f"https://raw.githubusercontent.com/lm-sys/FastChat/{MT_REV}/LICENSE",
}
EXPECTED_SHA256 = {
    "alpaca_eval/alpaca_eval.json": "d92b92c51e8f1962a21193abe74e6f727c2bc8286035f4041505ff38a7c3ae51",
    "alpaca_eval/README.md": "044d607fc7f4b51a82e2466d462f9d61121ee5dacb879815fdea1643896d0cfc",
    "mt_bench/question.jsonl": "119565adbab82227089cefdb44c8d7e2cf04dc0a0ec233634c82e7d4e2a944f7",
    "mt_bench/gpt-4_reference_answer.jsonl": "f957a5bc977badb66885ec970e6cd08527845780313f0995764260e5777b9b3f",
    "mt_bench/LICENSE": "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4",
}


def fetch_originals(root):
    records = []
    for relative, url in SOURCES.items():
        path = root / "raw" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            request = urllib.request.Request(url, headers={"User-Agent": "ScaleLLM-response-quality-research"})
            with urllib.request.urlopen(request, timeout=40) as response:
                data = response.read(4 * 1024 * 1024 + 1)
            if len(data) > 4 * 1024 * 1024:
                raise ValueError("official text exceeds 4 MiB budget")
            with path.open("xb") as stream:
                stream.write(data)
        source = identity(path)
        if source["sha256"] != EXPECTED_SHA256[relative]:
            raise ValueError("official original SHA mismatch: " + relative)
        records.append({**source, "url": url})
    return records


def convert(root):
    alpaca = json.loads((root / "raw/alpaca_eval/alpaca_eval.json").read_text())
    mt = [json.loads(x) for x in (root / "raw/mt_bench/question.jsonl").read_text().splitlines() if x]
    mt_answers = {x["question_id"]: x for x in (json.loads(v) for v in (root / "raw/mt_bench/gpt-4_reference_answer.jsonl").read_text().splitlines() if v)}
    if len(alpaca) != 805 or len(mt) != 80:
        raise ValueError("official benchmark count changed")
    outputs = {}
    for name, data in (("alpaca_eval", alpaca), ("mt_bench", mt)):
        rows = []
        for i, row in enumerate(data):
            source_key = str(i) if name == "alpaca_eval" else str(row["question_id"])
            pid = f"{name}:{source_key}"
            turns = [row["instruction"]] if name == "alpaca_eval" else row["turns"]
            if not turns or any(not isinstance(t, str) or not t.strip() for t in turns):
                raise ValueError("invalid original turns")
            group = row["dataset"] if name == "alpaca_eval" else row["category"]
            guidance = {"kind": "none", "is_gold": False}
            if name == "alpaca_eval":
                guidance = {"kind": "model_generated", "is_gold": False,
                            "generator": row["generator"], "turns": [row["output"]]}
            else:
                guidance = {"kind": "benchmark_hint" if row.get("reference") else "none",
                            "is_gold": False, "turns": row.get("reference", [])}
                if row["question_id"] in mt_answers:
                    supplied = mt_answers[row["question_id"]]
                    guidance["auxiliary_model_answer"] = {"kind": "model_generated", "is_gold": False,
                        "generator": supplied["model_id"], "turns": supplied["choices"][0]["turns"]}
            rows.append({"schema_version": 1, "id": pid, "prompt_id": pid, "cluster_id": pid,
                         "dataset": name, "source_revision": ALPACA_REV if name == "alpaca_eval" else MT_REV,
                         "source_row_index": i, "source_key": source_key, "category": group,
                         "category_kind": "source_group" if name == "alpaca_eval" else "task_category",
                         "turns": turns, "prompt": turns[0], "prompt_sha256": text_sha(turns[0]),
                         "turns_sha256": json_sha(turns), "reference": guidance})
        outputs[name] = rows
    for name, rows in outputs.items():
        write_jsonl(root / f"{name}_prompts.jsonl", rows)
    combined = outputs["alpaca_eval"] + outputs["mt_bench"]
    write_jsonl(root / "prompts.jsonl", combined)
    # Development smoke roster is preselected by input length, before outputs.
    smoke = min(outputs["alpaca_eval"], key=lambda x: (len(x["prompt"]), x["prompt_id"]))
    write_jsonl(root / "pilot_shortest_input_only.jsonl", [smoke])
    return {"questions": len(combined), "clusters": len({r["cluster_id"] for r in combined}),
            "turns": sum(len(r["turns"]) for r in combined),
            "datasets": {name: {"questions": len(rows), "group_kind": rows[0]["category_kind"],
                                 "groups": dict(Counter(r["category"] for r in rows))} for name, rows in outputs.items()},
            "mt_model_auxiliary_answers": len(mt_answers),
            "mt_questions_with_any_hint": sum(bool(r.get("reference")) for r in mt),
            "pilot_prompt_id": smoke["prompt_id"], "pilot_selection": "shortest original instruction, before generation"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()
    a.output_dir.mkdir(parents=True, exist_ok=True)
    originals = fetch_originals(a.output_dir)
    counts = convert(a.output_dir)
    manifest = {"schema": "scalellm_response_quality_datasets_v1", "execution_state": "completed",
                "prepared_utc": datetime.now(timezone.utc).isoformat(), "generation_state": "not_run",
                "selection": "all official questions; no prompt truncation or answer-based selection",
                "sources": originals, "counts": counts,
                "licenses": {"alpaca_eval": {"dataset": "CC-BY-NC-4.0", "source": SOURCES["alpaca_eval/README.md"],
                    "note": "Official HF dataset card; code Apache-2.0 is not substituted for data license. Retain component-source attribution."},
                    "mt_bench": {"repository": "Apache-2.0", "source": SOURCES["mt_bench/LICENSE"],
                        "note": "Model-generated auxiliary answers are not verified gold."}},
                "outputs": [identity(a.output_dir / v) for v in ("alpaca_eval_prompts.jsonl", "mt_bench_prompts.jsonl", "prompts.jsonl", "pilot_shortest_input_only.jsonl")],
                "code_identity": identity(__file__)}
    write_json(a.output_dir / "dataset_manifest.json", manifest)
    print(json.dumps(counts, ensure_ascii=False))


if __name__ == "__main__":
    main()
