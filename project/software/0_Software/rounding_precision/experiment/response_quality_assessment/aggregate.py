"""Unblind two orders, retain unresolved cases, bootstrap question clusters.

The two benchmarks are never pooled. Two judge orders are an order audit, not
two samples. A whole MT-Bench conversation is one question cluster.
"""
import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path

try:
    from .common import identity, index_unique, json_sha, read_jsonl, write_json, write_jsonl
    from .pack import validate_score
except ImportError:
    from common import identity, index_unique, json_sha, read_jsonl, write_json, write_jsonl
    from pack import validate_score

LABELS = ("Better", "Comparable", "Worse")


def wilson95(count, total):
    """Pointwise Wilson score interval for one binary indicator per question."""
    if type(count) is not int or type(total) is not int or count < 0 or count > total or total < 0:
        raise ValueError("invalid Wilson count/denominator")
    if total == 0:
        return None
    z = 1.959963984540054
    p = count / total
    z2 = z * z
    denom = 1 + z2 / total
    center = (p + z2 / (2 * total)) / denom
    radius = z * math.sqrt(p * (1 - p) / total + z2 / (4 * total * total)) / denom
    return {"low": 0.0 if count == 0 else max(0.0, 100 * (center - radius)),
            "high": 100.0 if count == total else min(100.0, 100 * (center + radius))}


def verify_pack(pack_dir):
    manifest_path = Path(pack_dir) / "pack_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schema") != "scalellm_blind_pack_manifest_v1" or manifest.get("execution_state") != "completed":
        raise ValueError("requires completed blind pack")
    paths = set()
    for declared in manifest["inputs"] + manifest["outputs"]:
        actual = identity(declared["path"])
        if any(actual[key] != declared[key] for key in ("path", "sha256", "bytes")):
            raise ValueError("blind pack or source changed: " + declared["path"])
        paths.add(actual["path"])
    for name in ("private/private_map.json", "public/blind_records.jsonl", "public/rubric.txt", "public/score_schema.json"):
        if str((Path(pack_dir) / name).resolve()) not in paths:
            raise ValueError("required pack artifact not bound by manifest: " + name)
    return manifest_path


def mapped_decision(decision, a_arm):
    if decision == "COMPARABLE":
        return "Comparable"
    if decision == "UNJUDGEABLE":
        return None
    winner = a_arm if decision == "A_BETTER" else ("output_only" if a_arm == "current" else "current")
    return "Better" if winner == "current" else "Worse"


def resolve_clusters(mapping, cases, scores, rubric_sha, judge_run_id):
    public = index_unique(cases, lambda x: x["case_id"])
    scored = index_unique(scores, lambda x: x.get("case_id"))
    if set(scored) - set(public):
        raise ValueError("unknown case in score input")
    clusters = index_unique(mapping, lambda x: x["cluster_id"])
    if len({r["prompt_id"] for r in mapping}) != len(mapping):
        raise ValueError("duplicate prompt in private map")
    referenced = [c["case_id"] for r in mapping for c in r["cases"]]
    if len(referenced) != len(set(referenced)) or set(referenced) != set(public):
        raise ValueError("case roster does not match private map")
    out = []
    for record in mapping:
        row = {k: record[k] for k in ("prompt_id", "cluster_id", "dataset", "category", "category_kind", "planned_turns", "observed_generation_turns")}
        row.update({"label": None, "status": "unresolved", "reasons": list(record["reasons"]), "orders": []})
        if record["eligibility"] != "eligible":
            out.append(row)
            continue
        if len(record["cases"]) != 2 or {c["a_arm"] for c in record["cases"]} != {"current", "output_only"}:
            raise ValueError("expected exactly two reversed arm orders")
        for case_map in record["cases"]:
            cid = case_map["case_id"]
            case = public[cid]
            if json_sha(case) != case_map["case_sha256"]:
                raise ValueError("public case changed after packing")
            if cid not in scored:
                row["reasons"].append("missing_order_score")
                continue
            score = scored[cid]
            try:
                validate_score(score, case, rubric_sha)
                if score["judge_run_id"] != judge_run_id:
                    raise ValueError("score judge identity differs from declared run")
            except (ValueError, TypeError, KeyError) as exc:
                row["reasons"].append("invalid_score:" + str(exc))
                continue
            decision = mapped_decision(score["decision"], case_map["a_arm"])
            row["orders"].append({"case_id": cid, "raw_decision": score["decision"], "mapped_label": decision,
                "confidence": score["confidence"], "reason": score["reason"], "evidence_a": score["evidence_a"],
                "evidence_b": score["evidence_b"], "flags": score["flags"]})
        if not row["reasons"] and len(row["orders"]) == 2:
            labels = [x["mapped_label"] for x in row["orders"]]
            if None in labels:
                row["reasons"].append("judge_unjudgeable")
            elif labels[0] != labels[1]:
                row["reasons"].append("order_conflict")
            elif all(t["response_a"] == t["response_b"] for t in public[record["cases"][0]["case_id"]]["turns"]) and labels[0] != "Comparable":
                row["reasons"].append("identical_answers_noncomparable_judgement")
            else:
                row["status"], row["label"] = "resolved", labels[0]
        out.append(row)
    return out


def summarize(rows, bootstrap_replicates=10000, seed=20261020):
    if bootstrap_replicates < 1000:
        raise ValueError("at least 1000 bootstrap replicates required")
    counts = Counter(r["label"] for r in rows if r["status"] == "resolved")
    planned = len(rows)
    submitted = sum(r.get("observed_generation_turns", 1) > 0 for r in rows)
    n = sum(counts.values())
    unresolved = planned - n
    ci = {label: None for label in LABELS}
    if n:
        import numpy as np
        # Each retained observation is one whole question cluster. For one
        # categorical outcome per cluster this multinomial draw is exactly
        # equivalent to resampling those question clusters with replacement.
        probabilities = np.array([counts[label] / n for label in LABELS])
        rng = np.random.default_rng(seed)
        resampled = rng.multinomial(n, probabilities, size=bootstrap_replicates) * (100.0 / n)
        for i, label in enumerate(LABELS):
            low, high = np.quantile(resampled[:, i], [0.025, 0.975], method="linear")
            ci[label] = {"low": float(low), "high": float(high)}
    return {"planned_question_clusters": planned, "resolved_question_clusters": n,
        "submitted_generation_question_clusters": submitted,
        "no_generation_question_clusters": planned - submitted,
        "unresolved_question_clusters": unresolved, "assessment_coverage_percent": 100 * n / planned if planned else None,
        "assessment_coverage_of_submitted_percent": 100 * n / submitted if submitted else None,
        "counts": {label: counts[label] for label in LABELS},
        "percent_of_resolved": {label: 100 * counts[label] / n if n else None for label in LABELS},
        "percent_of_all_planned": {label: 100 * counts[label] / planned if planned else None for label in LABELS},
        "percent_of_all_submitted": {label: 100 * counts[label] / submitted if submitted else None for label in LABELS},
        "unresolved_percent_of_all_planned": 100 * unresolved / planned if planned else None,
        "unresolved_percent_of_all_submitted": 100 * (submitted - n) / submitted if submitted else None,
        "conditional_question_wilson_95_ci_percent": {label: wilson95(counts[label], n) for label in LABELS},
        "conditional_cluster_bootstrap_95_ci_percent": ci,
        "unresolved_reason_counts": dict(Counter(reason for r in rows if r["status"] != "resolved" for reason in set(r["reasons"]))),
        "primary_ci_method": {"method": "Wilson score, pointwise 95%", "unit": "one unique question-cluster outcome",
            "denominator": "resolved questions; conditional on resolved selection, no missingness correction",
            "assumptions": "independent Bernoulli category indicators across question clusters; sampling/exchangeability unverified",
            "scope": "not simultaneous and not a guarantee for untested prompts, free generations, tasks, or all-world quality"},
        "ci_method": {"unit": "question cluster, whole conversation and both orders collapsed",
            "population": "resolved question clusters only; conditional, no missingness correction",
            "method": "percentile nonparametric question-cluster bootstrap, exact categorical multinomial implementation",
            "replicates": bootstrap_replicates, "seed": seed, "confidence_level": 0.95,
            "coverage": "pointwise, not simultaneous across categories or benchmarks",
            "assumptions": "IID question clusters/exchangeability unverified; benchmark-fixed-set proportions are descriptive",
            "boundary_caution": "Auxiliary only. A zero/all category gives a degenerate percentile interval; use the nondegenerate Wilson interval as primary, not a zero-risk proof"}}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pack-dir", type=Path, required=True)
    p.add_argument("--scores", type=Path, action="append", required=True)
    p.add_argument("--judge-manifest", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--bootstrap-replicates", type=int, default=10000)
    p.add_argument("--seed", type=int, default=20261020)
    a = p.parse_args()
    if a.output_dir.exists():
        raise ValueError("output directory must be new")
    mapping_path = a.pack_dir / "private/private_map.json"
    public_path = a.pack_dir / "public/blind_records.jsonl"
    pack_manifest = verify_pack(a.pack_dir)
    mapping = json.loads(mapping_path.read_text())
    judge = json.loads(a.judge_manifest.read_text())
    if judge.get("assessment_kind") != "preliminary_ai_agent_assessment" or not isinstance(judge.get("judge_run_id"), str) or not judge["judge_run_id"]:
        raise ValueError("declare the actual AI-agent judge run; no human/API judgement implied")
    if judge.get("human_reviewed") is not False:
        raise ValueError("this preliminary pipeline requires explicit human_reviewed=false")
    rows = resolve_clusters(mapping["clusters"], list(read_jsonl(public_path)),
        [row for source in a.scores for row in read_jsonl(source)], mapping["rubric_sha256"], judge["judge_run_id"])
    datasets = []
    for dataset in sorted({r["dataset"] for r in rows}):
        selected = [r for r in rows if r["dataset"] == dataset]
        kinds = {r["category_kind"] for r in selected}
        if len(kinds) != 1:
            raise ValueError("inconsistent group semantics")
        groups = [{"group": group, **summarize([r for r in selected if r["category"] == group], a.bootstrap_replicates, a.seed)} for group in sorted({r["category"] for r in selected})]
        target = {"alpaca_eval": 805, "mt_bench": 80}.get(dataset)
        datasets.append({"dataset": dataset, "group_kind": next(iter(kinds)),
            "official_benchmark_target_questions": target,
            "full_benchmark_roster_present": len(selected) == target if target else None,
            "overall": summarize(selected, a.bootstrap_replicates, a.seed), "groups": groups})
    a.output_dir.mkdir(parents=True)
    write_jsonl(a.output_dir / "question_outcomes.jsonl", rows)
    summary = {"schema": "scalellm_response_quality_aggregate_v1", "execution_state": "completed",
        "assessment_kind": "preliminary_ai_agent_assessment", "human_reviewed": False,
        "comparison": "Current vs retained-intermediate-precision reference; same base quantization/LUT/exit rules, independent free generation",
        "overall_quality_verdict": "not_inferred_from_category_counts",
        "benchmark_pooling": "separate benchmark overalls only; no AlpacaEval+MT-Bench combined score",
        "order_policy": "both mapped order judgements must agree; conflicts/missing/truncation remain unresolved",
        "datasets": datasets, "judge": judge,
        "sources": [identity(pack_manifest), identity(mapping_path), identity(public_path), identity(a.judge_manifest)] + [identity(v) for v in a.scores],
        "code_identity": identity(__file__), "question_outcomes": identity(a.output_dir / "question_outcomes.jsonl")}
    write_json(a.output_dir / "summary.json", summary)
    with (a.output_dir / "category_statistics.csv").open("x", newline="", encoding="utf-8") as stream:
        fields = ["dataset", "group_kind", "group", "label", "planned", "submitted_generation", "resolved", "unresolved", "count", "percent_resolved", "percent_all_planned", "percent_all_submitted", "wilson95_low", "wilson95_high", "bootstrap95_low_aux", "bootstrap95_high_aux"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for dataset in datasets:
            for stat in [{"group": "Overall", **dataset["overall"]}] + dataset["groups"]:
                for label in LABELS:
                    interval = stat["conditional_question_wilson_95_ci_percent"][label]
                    auxiliary = stat["conditional_cluster_bootstrap_95_ci_percent"][label]
                    writer.writerow(dict(dataset=dataset["dataset"], group_kind=dataset["group_kind"], group=stat["group"], label=label,
                        planned=stat["planned_question_clusters"], resolved=stat["resolved_question_clusters"], unresolved=stat["unresolved_question_clusters"],
                        submitted_generation=stat["submitted_generation_question_clusters"], count=stat["counts"][label], percent_resolved=stat["percent_of_resolved"][label],
                        percent_all_planned=stat["percent_of_all_planned"][label], percent_all_submitted=stat["percent_of_all_submitted"][label],
                        wilson95_low=interval["low"] if interval else None, wilson95_high=interval["high"] if interval else None,
                        bootstrap95_low_aux=auxiliary["low"] if auxiliary else None, bootstrap95_high_aux=auxiliary["high"] if auxiliary else None))
    print(json.dumps({d["dataset"]: d["overall"] for d in datasets}))


if __name__ == "__main__":
    main()
