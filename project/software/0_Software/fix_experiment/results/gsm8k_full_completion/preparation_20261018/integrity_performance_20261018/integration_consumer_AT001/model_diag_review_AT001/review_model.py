"""CPU-only independent audit of existing immutable GPU diagnostic artifacts."""
from datetime import datetime, timezone
import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[10]
# Resolve the explicitly authorized project from this fixed evidence location.
assert ROOT.name == "ScaleLLM", ROOT
EXP = ROOT / "project/software/0_Software/fix_experiment/exp"
E010 = ROOT / "project/E010_gsm8k_six_model_completion"
DIAG = E010 / "experiment_results/performance_repair/production_integration_20261018/shared_model_diag_AT001"
OLD = EXP.parent / "results/gsm8k_full_completion/R003_gsm8k_gpu0_weight_integrity"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--case", required=True, choices=("bf16", "a8w4_fp32"))
parser.add_argument("--parent-comparison", required=True, type=Path)
args = parser.parse_args()
CASE = args.case
WORKER = DIAG / CASE / "execution/worker"
PREVIOUS = OLD / "smoke/Llama-3.1-8B-Instruct" / CASE / "AT001"
METHOD = "immutable_cpu_chunks_memcmp_full_content_v1"
GPU = "GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6"
IDS = [f"train:{index:04d}" for index in range(4)]
sys.path[:0] = [str(EXP), str(E010)]
from gsm8k_protocol import canonical_hash, score_response, validate_integrity_evidence
from run_gsm8k_matrix import validate_actual_gpu, validate_generation_verification
import summarize_gpu0_speed_probe as parent_comparison


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


consumed = {}


def load(path):
    consumed[str(path)] = digest(path)
    return json.loads(path.read_text())


def lines(path):
    consumed[str(path)] = digest(path)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def fn_ast(path, name):
    consumed[str(path)] = digest(path)
    node = next(n for n in ast.parse(path.read_text()).body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    return ast.dump(node, include_attributes=False)


assert os.environ.get("CUDA_VISIBLE_DEVICES") == ""
assert sorted(os.sched_getaffinity(0)) == [8, 9]
assert "torch" not in sys.modules
started = datetime.now(timezone.utc).isoformat()
execution = load(DIAG / CASE / "execution/result.json")
spec = load(DIAG / CASE / "spec_reviewed.json")
plan = load(DIAG / "plan.json")
saved_parent = load(args.parent_comparison.resolve())["result"]
assert execution["state"] == "shared_training_speed_diagnostic_complete_not_ACC"
assert execution["child_exit_code"] == 0 and execution["execute_requested"] is True
assert execution["scope"] == spec["scope"] == plan["diagnostic_scope"]
assert execution["scope"]["exclusive_verified"] is False
assert execution["scope"]["formal_progression_eligible"] is False
assert execution["scope"]["matrix_resume"] is False
assert execution["scope"]["sample_ids"] == IDS
assert execution["process_control_actions_on_other_tasks"] == []
assert execution["spec_sha256"] == digest(DIAG / CASE / "spec_reviewed.json")
assert execution["guard_sha256"] == digest(E010 / "run_gpu0_model_speed_probe.py")
assert spec["plan_sha256"] == digest(DIAG / "plan.json")
for key, value in spec["source_hashes"].items():
    assert digest(key) == digest(spec["source_snapshots"][key]) == value
    consumed[key] = value
    consumed[spec["source_snapshots"][key]] = value
legacy_sources = load(OLD / "frozen_sources/manifest.json")
legacy_map = {row["path"]: row for row in legacy_sources}
for row in legacy_sources:
    assert digest(OLD / row["snapshot"]) == row["sha256"]
    consumed[str(OLD / row["snapshot"])] = row["sha256"]

bundles = []
for directory, implementation in [(PREVIOUS, None), (WORKER, METHOD)]:
    manifest, summary, verification, integrity, requests = [load(directory / name) for name in
        ("manifest.json", "summary.json", "verification.json", "integrity.json", "requests.json")]
    rows, scores = lines(directory / "generation.jsonl"), lines(directory / "scores.jsonl")
    assert manifest["state"] == summary["state"] == "complete"
    assert manifest["stage"] == summary["stage"] == "smoke"
    assert manifest["model"] == "Llama-3.1-8B-Instruct" and manifest["case"] == CASE
    assert manifest["n_completed"] == manifest["n_expected"] == summary["n_completed"] == summary["n_expected"] == 4
    assert manifest["full_split"] is summary["full_split"] is False
    assert manifest["identity_sha256"] == canonical_hash(manifest["identity"])
    assert manifest["identity"]["requests_sha256"] == canonical_hash(requests)
    for name, sha in manifest["artifacts"].items():
        assert digest(directory / name) == sha, (directory, name)
        consumed[str(directory / name)] = sha
    assert [row["sample_id"] for row in rows] == [r["sample_id"] for r in requests] == IDS
    assert [score["sample_id"] for score in scores] == IDS
    for row, score, request in zip(rows, scores, requests, strict=True):
        assert row["identity_sha256"] == score["identity_sha256"] == manifest["identity_sha256"]
        assert row["status"] == "complete" and row["split"] == request["split"] == "train"
        assert row["gold"] == request["gold"]
        assert row["prompt_sha256"] == request["prompt_sha256"] == hashlib.sha256(request["prompt"].encode()).hexdigest()
        assert row["question_sha256"] == hashlib.sha256(request["question"].encode()).hexdigest()
        assert row["output_tokens"] == len(row["new_token_ids"])
        assert all(score[key] == value for key, value in score_response(row["scoring_text"], row["gold"]).items())
    validate_actual_gpu(manifest, GPU)
    assert verification == manifest["generation_verification"]
    validate_generation_verification(verification, "native_cache_call_parity_v2", manifest)
    validate_integrity_evidence(directory, manifest, "checkpoint_static_content_v1", sample_ids=IDS,
        expected_gpu=GPU, summary=summary, expected_implementation=implementation)
    assert len(integrity["phase_checks"]) == 15
    assert all(p["exact"] is True and p["complete"] is True for p in integrity["phase_checks"])
    for path, sha in manifest["identity"]["code_sha256"].items():
        expected = legacy_map[path]["sha256"] if implementation is None else spec["source_hashes"][path]
        assert sha == expected
    bundles.append((manifest, summary, verification, integrity, requests, rows))
old_m, old_s, old_v, old_i, old_requests, old_rows = bundles[0]
new_m, new_s, new_v, new_i, new_requests, new_rows = bundles[1]
assert digest(PREVIOUS / "requests.json") == digest(WORKER / "requests.json")
assert old_requests == new_requests
assert old_m["model_identity"] == new_m["model_identity"]
for key in ("model_fingerprint_sha256", "tokenizer", "token_audit", "generation", "method", "package_versions"):
    assert old_m["identity"][key] == new_m["identity"][key], key
assert old_i["baseline_manifest"] == new_i["baseline_manifest"]
assert old_i["baseline_root_sha256"] == new_i["baseline_root_sha256"]
assert [p["label"] for p in old_i["phase_checks"]] == [p["label"] for p in new_i["phase_checks"]]
parity_fields = ["sample_id", "row_index", "split", "prompt_sha256", "question_sha256",
    "fewshot_train_indices", "input_token_ids_sha256", "input_tokens", "new_token_ids", "output_tokens",
    "raw_text", "decoded_text_skip_special_tokens", "scoring_text", "stop_reason", "matched_stop_string",
    "stop_strings", "eos_token_ids", "length_capped", "generation_limit_reached", "gold", "use_cache"]
for old_row, row in zip(old_rows, new_rows, strict=True):
    assert all(old_row[key] == row[key] for key in parity_fields)
    assert row["performance_timing"]["generation_reused_from_completed_evidence"] is False
assert new_m["resume_sources"] == []
assert [(r["sample_id"], r["repeatability_prefix_32_token_ids"]) for r in old_v["records"]] == [
    (r["sample_id"], r["repeatability_prefix_32_token_ids"]) for r in new_v["records"]]
runtime_phases = [p for p in new_i["phase_checks"] if "content_comparison" in p]
assert len(runtime_phases) == 12
logical = new_i["immutable_runtime_baseline"]["logical_baseline_bytes"]
assert all(p["content_comparison"]["expected_bytes"] ==
           p["content_comparison"]["compared_bytes"] ==
           p["content_comparison"]["equal_bytes"] == logical for p in runtime_phases)
ast_equal = {}
for source_name, names in {"run_gsm8k_worker.py": ["generate_one", "verify_generation", "resolve_generation", "audit_prompts"],
                           "gsm8k_protocol.py": ["prepare_requests", "build_prompt", "score_response", "normalize_answer", "_extract"]}.items():
    path = str(EXP / source_name)
    for name in names:
        ast_equal[source_name + ":" + name] = fn_ast(EXP / source_name, name) == fn_ast(OLD / legacy_map[path]["snapshot"], name)
assert all(ast_equal.values())
def gaps(rows):
    timestamps = [datetime.fromisoformat(row["completed_at"]) for row in rows]
    values = [(b-a).total_seconds() for a,b in zip(timestamps,timestamps[1:])]
    assert len(values) == 3 and all(math.isfinite(v) and v > 0 for v in values)
    return values
old_gaps, new_gaps = gaps(old_rows), gaps(new_rows)
cycle_ratio = statistics.median(old_gaps) / statistics.median(new_gaps)
wall_ratio = old_s["elapsed_seconds"] / new_s["elapsed_seconds"]
assert saved_parent["observed_steady_cycle_speedup"] == cycle_ratio
assert saved_parent["observed_short_worker_wall_speedup"] == wall_ratio
parent_fresh = parent_comparison.analyze(CASE, WORKER)
assert parent_fresh == saved_parent
consumed[str(E010 / "summarize_gpu0_speed_probe.py")] = digest(E010 / "summarize_gpu0_speed_probe.py")
consumed[str(E010 / "run_gpu0_model_speed_probe.py")] = digest(E010 / "run_gpu0_model_speed_probe.py")
commands = execution["commands"]
client_records = [record for record in commands if any("query-compute-apps" in arg for arg in record["argv"])]
assert len(client_records) == 2
assert all(record["exit_code"] == 0 and record["stdout"].split(",")[0] == "23186" for record in client_records)
assert execution["manifest_sha256"] == digest(WORKER / "manifest.json")
assert execution["summary_sha256"] == digest(WORKER / "summary.json")
assert spec["baseline_manifest_sha256"] == digest(PREVIOUS / "manifest.json")
assert spec["baseline_summary_sha256"] == digest(PREVIOUS / "summary.json")
assert all(digest(path) == sha for path, sha in consumed.items())
assert "torch" not in sys.modules
report = {"schema": "scalellm_independent_shared_model_diagnostic_review_v1", "case": CASE,
    "reviewer": "A010 /root/gsm8k_protocol", "execution_state": "completed", "verdict": "PASS_bounded_observed_shared_diagnostic",
    "start_utc": started, "end_utc": datetime.now(timezone.utc).isoformat(), "cpu_affinity": sorted(os.sched_getaffinity(0)),
    "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"), "torch_imported": False,
    "parent_summarizer_recomputed_identically": True, "sources_and_evidence_stable": True,
    "requests_byte_identical": True, "sample_ids": IDS, "token_and_text_fields_equal": parity_fields,
    "checkpoint_tokenizer_generation_method_packages_equal": True, "native_v2_passed_old_and_new": True,
    "two_verification_prefixes_equal": True, "all_phase_count": 15, "runtime_full_byte_phase_count": 12,
    "full_static_bytes_per_runtime_phase": logical, "immutable_capture": new_i["immutable_runtime_baseline"],
    "capture_resource_guard": new_i["immutable_capture_resource_guard"], "critical_function_AST_equal": ast_equal,
    "old_completion_gaps_seconds": old_gaps, "new_completion_gaps_seconds": new_gaps,
    "old_median_completion_gap_seconds": statistics.median(old_gaps), "new_median_completion_gap_seconds": statistics.median(new_gaps),
    "observed_steady_cycle_speedup": cycle_ratio, "old_worker_wall_seconds": old_s["elapsed_seconds"],
    "new_worker_wall_seconds": new_s["elapsed_seconds"], "observed_short_worker_wall_speedup": wall_ratio,
    "old_native_generation_seconds": sum(row["elapsed_seconds"] for row in old_rows),
    "new_native_generation_seconds": sum(row["elapsed_seconds"] for row in new_rows),
    "native_generation_speedup_claim": False, "new_timing_breakdown": new_s["performance_timing"],
    "new_peak_memory_reserved_bytes": new_s["peak_memory_reserved_bytes"],
    "external_client_23186_observed_before_and_after": True, "no_external_process_control_recorded": True,
    "exclusive_verified": False, "formal_progression_eligible": False, "ACC_resumed": False,
    "limitations": ["Four fixed training questions; only three completion gaps per version.",
        "Current GPU0 is shared with yqh, old same-device baseline is from an earlier time; no controlled exclusive throughput qualification.",
        "Completion gap includes previous postcheck, next precheck, generation and persistence; it is not guard-only or generation-only speed.",
        "The short worker wall includes setup, native verification, immutable capture and terminal checkpoint reverify.",
        "Parent summarizer is a bounded comparison script; this independent review additionally binds raw artifacts and identities.",
        "GPU/client facts come from existing parent execution receipts; reviewer never initializes or queries a GPU."],
    "consumed_sha256": consumed}
report_path = Path(__file__).with_name(CASE + "_review.json")
with report_path.open("x") as output:
    json.dump(report, output, indent=2); output.write("\n")
print(json.dumps({key: report[key] for key in ("verdict", "observed_steady_cycle_speedup", "observed_short_worker_wall_speedup", "all_phase_count", "runtime_full_byte_phase_count", "full_static_bytes_per_runtime_phase")}, indent=2))
