#!/usr/bin/env python3
"""Independent CPU review of an actual completed GPU0 preparation smoke."""
import argparse
import datetime
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[3]
sys.path.insert(0, str(BASE / "exp"))

from gsm8k_protocol import (INTEGRITY_CONTRACT_ID, canonical_hash, load_plan,
                            prepare_requests, sha256_file, validate_integrity_evidence)
from run_gsm8k_matrix import validate_generation_verification, NATIVE_VERIFICATION
from summarize_gsm8k import (HarnessOracle, check_tokenizer_identity, independently_rescore,
                             load_checked_tokenizer, validate_model_identity, validate_native_record)
from six_model_matrix import get_model_spec, validate_quantized_summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == ""
    assert set(os.sched_getaffinity(0)) == {8,9}
    planpath = BASE / "source/gsm8k_gpu_integrity_v3_20261018/plan.json"
    plan = load_plan(planpath)
    requests = prepare_requests(planpath, "smoke")
    directory = args.attempt.resolve()
    m = json.loads((directory / "manifest.json").read_text())
    s = json.loads((directory / "summary.json").read_text())
    identity = m["identity"]
    assert m["state"] == s["state"] == "complete"
    assert m["stage"] == s["stage"] == identity["stage"] == "smoke"
    assert identity["plan_sha256"] == sha256_file(planpath)
    assert identity["protocol_sha256"] == canonical_hash(plan["protocol"])
    assert identity["protocol_id"] == plan["protocol_id"] and identity["data"] == plan["data"]
    assert identity["requests_sha256"] == canonical_hash(requests)
    assert identity["seed"] == plan["protocol"]["seed"]
    assert m["identity_sha256"] == canonical_hash(identity)
    assert m["method"] == identity["method"] and m["generation"] == identity["generation"]
    assert all(m["method"].get(k) == v for k,v in {"dtype":"bfloat16","attention_implementation":"eager","use_cache":True}.items())
    assert identity["generation"]["effective_generation_config"]["max_new_tokens"] == 64
    assert s["n_completed"] == s["n_expected"] == 4 and s["n_errors"] == 0 and s["full_split"] is False
    spec = get_model_spec(Path(m["model_identity"]["resolved_path"]))
    validate_model_identity(m["model_identity"], spec.name)
    assert identity["model_fingerprint_sha256"] == m["model_identity"]["fingerprint_sha256"]
    if m["case"] != "bf16":
        validate_quantized_summary(m["method"], spec, m["case"])
    freeze = json.loads((HERE / "integrity_v3_consumer_freeze_AT001.json").read_text())
    for path, expected in identity["code_sha256"].items():
        assert sha256_file(path) == expected, path
        if path in freeze["source_sha256"]:
            assert freeze["source_sha256"][path] == expected, path
    for name in ("generation.jsonl","scores.jsonl","requests.json"):
        assert sha256_file(directory/name) == m["artifacts"][name], name
    assert json.loads((directory/"requests.json").read_text()) == requests
    ref = validate_integrity_evidence(directory, m, INTEGRITY_CONTRACT_ID,
        sample_ids=[r["sample_id"] for r in requests], expected_gpu=plan["resources"]["allowed_gpu_uuids"][0], summary=s)
    data = json.loads((directory/"integrity.json").read_text())
    inputs = json.loads((HERE / "integrity_v3_gpu_bf16_input_review_AT001.json").read_text())
    assert canonical_hash(data["checkpoint_manifest"]) == inputs["checkpoint_manifest_root"]
    verification = json.loads((directory/"verification.json").read_text())
    assert verification == m["generation_verification"]
    validate_generation_verification(verification, NATIVE_VERIFICATION, m)
    for row in verification["records"]:
        validate_native_record(row, m["generation"]["eos_token_ids"], spec.layers)
        assert row["prompt_sha256"] == next(r["prompt_sha256"] for r in requests if r["sample_id"] == row["sample_id"])
    rows = [json.loads(line) for line in (directory/"generation.jsonl").read_text().splitlines()]
    scores = [json.loads(line) for line in (directory/"scores.jsonl").read_text().splitlines()]
    assert [r["sample_id"] for r in rows] == [r["sample_id"] for r in scores] == [r["sample_id"] for r in requests]
    tokenizer = load_checked_tokenizer(m)
    check_tokenizer_identity(tokenizer, identity)
    oracle = HarnessOracle(plan["protocol"])
    rescored = []
    for row, score, request in zip(rows,scores,requests,strict=True):
        ids = list(tokenizer.encode(request["prompt"],truncation=False))
        rescored.append(independently_rescore(row,score,request,
            {**identity,"max_prompt_tokens":plan["protocol"]["max_prompt_tokens"]},m["identity_sha256"],tokenizer,oracle,ids))
    assert sum(r["correct_strict"] for r in rescored) == s["correct_strict"]
    evidence = {"schema":"scalellm_gsm8k_gpu0_integrity_smoke_independent_review_v1",
        "reviewed_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"reviewer":"A010 /root/gsm8k_protocol",
        "CPU_only":True,"cpu_affinity":sorted(os.sched_getaffinity(0)),"CUDA_VISIBLE_DEVICES":os.environ.get("CUDA_VISIBLE_DEVICES"),
        "review_source_sha256":sha256_file(__file__),"attempt":str(directory),"model":m["model"],"case":m["case"],
        "execution_state":"completed_training_smoke_independently_accepted","verdict":"original v2 and full static identity/content/storage gates passed for this controlled training attempt",
        "plan_sha256":sha256_file(planpath),"source_sha256":identity["code_sha256"],
        "artifacts":{name:sha256_file(directory/name) for name in ("manifest.json","summary.json","verification.json","integrity.json","integrity_checks.jsonl","generation.jsonl","scores.jsonl","requests.json")},
        "integrity_reference":ref,"checkpoint_names":len(data["coverage"]["checkpoint_names"]),
        "effective_static_names":len(data["coverage"]["effective_static_names"]),
        "QDQ_modules_independently_rebuilt":len(data["qdq_reconstruction"]),"external_caches":len(data["coverage"]["external_cache_names"]),
        "phase_count":len(data["phase_checks"]),"all_phase_coverage_and_roots_verified":True,
        "all_original_v2_detailed_gates_verified":True,"raw_token_rows_independently_redecoded_rescored":len(rescored),
        "runtime_evidence":{k:s.get(k) for k in ("elapsed_seconds","generation_seconds","output_tokens","mean_seconds_per_example","tokens_per_generation_second")},
        "load_attach_seconds":m.get("model_load_attach_seconds"),"started_at":m.get("started_at"),"completed_at":m.get("completed_at"),
        "formal_results_accepted":0,"applicability":"Preparation only; new R003 still needs all 30 fresh smoke/pilot processes and independent-process repeat before formal; no GPU1 hardware verdict"}
    with args.output.open("x") as stream:
        json.dump(evidence,stream,indent=2);stream.write("\n")
    print(json.dumps({k:evidence[k] for k in ("execution_state","model","case","checkpoint_names","effective_static_names","QDQ_modules_independently_rebuilt","external_caches","phase_count","raw_token_rows_independently_redecoded_rescored")}))


if __name__=="__main__":main()
