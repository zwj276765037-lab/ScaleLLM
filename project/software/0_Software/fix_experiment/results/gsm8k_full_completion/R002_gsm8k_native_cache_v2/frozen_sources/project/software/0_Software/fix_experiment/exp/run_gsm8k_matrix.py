#!/usr/bin/env python3
"""Run the frozen GSM8K matrix on exclusive per-GPU worker queues.

This process is the supervisor: it must remain alive to advance the stages.
There is deliberately no worker wall-clock or no-output timeout.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone

from gsm8k_protocol import atomic_json, canonical_hash, load_plan, prepare_requests, score_response, sha256_file


HERE = Path(__file__).resolve().parent
ORDER = ["Llama-3.2-3B-Instruct", "Llama-3.1-8B-Instruct", "Qwen2.5-7B-Instruct",
         "Qwen3-8B", "GLM-4-9B-0414", "DeepSeek-R1-Distill-Llama-8B"]
LEGACY_VERIFICATION = "cache_on_off_logits_v1"
NATIVE_VERIFICATION = "native_cache_call_parity_v2"
NATIVE_HARD_GATES = ("native_generate_exact", "rebuilt_cache_exact", "cache_structure_valid",
                     "negative_control_qualified", "same_process_repeat_32_equal")


def now():
    return datetime.now(timezone.utc).isoformat()


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--readiness", type=Path, required=True)
    p.add_argument("--run-root", type=Path, required=True)
    p.add_argument("--model-identities", type=Path, required=True)
    p.add_argument("--model-root", type=Path, required=True)
    p.add_argument("--gpu-uuids", nargs="+", required=True)
    p.add_argument("--cpu-sets", nargs="+", default=["16,17", "18,19"])
    p.add_argument("--python", default=sys.executable)
    p.add_argument("--stages", default="smoke,pilot,formal")
    p.add_argument("--driver-library-dir", type=Path)
    p.add_argument("--allow-resume", action="store_true")
    return p.parse_args()


def verify_readiness(args):
    readiness = json.loads(args.readiness.read_text())
    if readiness.get("ready") is not True:
        raise ValueError("Readiness manifest does not authorize a validated launch")
    if readiness["plan_sha256"] != sha256_file(args.plan):
        raise ValueError("Plan changed after readiness review")
    for path, digest in readiness["source_hashes"].items():
        if sha256_file(Path(path)) != digest:
            raise ValueError(f"Source changed after readiness review: {path}")
    for path, digest in readiness["evidence_hashes"].items():
        if sha256_file(Path(path)) != digest:
            raise ValueError(f"Readiness evidence changed: {path}")
    if {canonical_gpu_uuid(gpu) for gpu in args.gpu_uuids} != {
        canonical_gpu_uuid(gpu) for gpu in readiness["gpu_uuids"]
    }:
        raise ValueError("GPU allocation differs from reviewed readiness")
    return readiness


def group_order(plan):
    rank = {name: i for i, name in enumerate(ORDER)}
    cases = {name: i for i, name in enumerate(
        ["bf16", "a8w8_fp32", "a8w4_fp32", "a8w4_fp16", "reference_qdq"])}
    return sorted(plan["matrix"], key=lambda g: (rank[g["model"]], cases[g["case"]]))


def canonical_gpu_uuid(value):
    """Accept only a full physical GPU UUID, with or without CUDA's prefix."""
    if not isinstance(value, str):
        raise ValueError("Actual GPU UUID is missing")
    value = value.strip()
    if value.lower().startswith("gpu-"):
        value = value[4:]
    try:
        return "GPU-" + str(uuid.UUID(value))
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Expected a full actual GPU UUID, got {value!r}") from exc


def group_key(group):
    return f"{group['model']}/{group['case']}"


def fixed_gpu_assignments(groups, gpu_uuids):
    """Pin each model/config to a stable slot for every stage and retry."""
    devices = [canonical_gpu_uuid(gpu) for gpu in gpu_uuids]
    if not devices or len(devices) > 2 or len(set(devices)) != len(devices):
        raise ValueError("Expected one or two unique physical GPU UUIDs")
    ordered = group_order({"matrix": groups})
    if len({group_key(g) for g in ordered}) != len(ordered):
        raise ValueError("Duplicate model/config keys in the matrix")
    return {group_key(g): devices[index % len(devices)] for index, g in enumerate(ordered)}


def frozen_group_gpu(contract, group):
    if contract.get("scheduling_schema") != "fixed_gpu_slots_v1":
        raise ValueError("Run lacks a fixed GPU contract; start a new R instead of migrating it")
    try:
        expected = canonical_gpu_uuid(contract["group_gpu_uuids"][group_key(group)])
        devices = [canonical_gpu_uuid(gpu) for gpu in contract["gpu_uuids"]]
    except (KeyError, TypeError) as exc:
        raise ValueError("Frozen group GPU allocation is missing") from exc
    if expected not in devices:
        raise ValueError("Frozen group GPU is outside the allocated devices")
    return expected


def validate_actual_gpu(manifest, expected):
    environment = manifest.get("environment", {})
    actual = canonical_gpu_uuid(environment.get("gpu_uuid"))
    visible = canonical_gpu_uuid(environment.get("CUDA_VISIBLE_DEVICES"))
    if actual != canonical_gpu_uuid(expected) or visible != actual:
        raise ValueError("Actual GPU UUID or worker CUDA visibility differs from its fixed slot")
    if environment.get("device") != "cuda:0":
        raise ValueError("Worker must use cuda:0 within its one-GPU visibility")
    return actual


def verification_contract_id(plan):
    value = plan["protocol"].get("verification_contract_id", LEGACY_VERIFICATION)
    if value not in {LEGACY_VERIFICATION, NATIVE_VERIFICATION}:
        raise ValueError("Unsupported generation verification contract")
    return value


def validate_generation_verification(data, expected_contract=None, manifest=None):
    contract = data.get("verification_contract_id", LEGACY_VERIFICATION)
    if contract not in {LEGACY_VERIFICATION, NATIVE_VERIFICATION} or (
        expected_contract is not None and contract != expected_contract
    ):
        raise ValueError("Generation verification contract differs from the frozen run")
    if data.get("passed") is not True or data.get("all_qdq_projections_prefill_and_decode") is not True:
        raise ValueError("Worker generation checks or QDQ coverage did not pass")
    records = data.get("records", [])
    if (len(records) != 2 or {r.get("sample_id") for r in records} != {"train:0000", "train:0001"}):
        raise ValueError("Expected exactly two unique fixed verification prompts")
    hard = NATIVE_HARD_GATES if contract == NATIVE_VERIFICATION else (
        "greedy_16_equal", "same_process_repeat_32_equal", "logits_allclose")
    if contract == NATIVE_VERIFICATION and not all(data.get(key) is True for key in hard):
        raise ValueError("Native generation verification aggregate hard gate did not pass")
    for row in records:
        if not all(row.get(key) is True for key in hard):
            raise ValueError("Individual generation verification hard gate did not pass")
        if row.get("atol") != .125 or row.get("rtol") != .01:
            raise ValueError("Cache verification diagnostic tolerance changed")
        if any(type(row.get(key)) is not bool for key in ("greedy_16_equal", "logits_allclose")):
            raise ValueError("Original cache on/off diagnostics must retain their actual boolean results")
        if contract == NATIVE_VERIFICATION:
            count, tokens, steps = (row.get("native_logits_count"), row.get("native_generated_token_ids"),
                                    row.get("steps"))
            if (type(count) is not int or not 1 <= count <= 17 or not isinstance(tokens, list) or
                len(tokens) != count or any(type(token) is not int or token < 0 for token in tokens) or
                not isinstance(steps, list) or len(steps) != count):
                raise ValueError("Native verification has incomplete step/logit/token evidence")
            prefix = row.get("repeatability_prefix_32_token_ids")
            if (row.get("native_prefix_matches_32") is not True or not isinstance(prefix, list) or
                tokens != prefix[:count] or row.get("repeat_32_token_ids") != prefix):
                raise ValueError("Native and repeated generation prefixes disagree")
            for index, step in enumerate(steps):
                if (type(step.get("step")) is not int or step["step"] != index or
                    not all(step.get(key) is True for key in
                            ("native_generate_exact", "rebuilt_cache_exact", "cache_structure_valid", "finite"))):
                    raise ValueError("Native per-step cache/logit/finite hard evidence did not pass")
            status = row.get("negative_control_status")
            detected = row.get("negative_control_detected")
            if status == "not_applicable_early_eos_no_prior_cache":
                eos_ids = (manifest or {}).get("generation", {}).get("eos_token_ids", [])
                if ("negative_control_detected" not in row or detected is not None or count != 1 or
                    tokens[0] not in eos_ids):
                    raise ValueError("Negative-control N/A is valid only for a single native EOS step")
            elif status != "detected" or detected is not True:
                raise ValueError("Native cache corruption negative control did not detect the defect")
    return contract


def latest_attempts(root, stage, model, case):
    return sorted((root / stage / model / case).glob("AT[0-9][0-9][0-9]"))


def read_manifest(directory):
    p = directory / "manifest.json"
    return json.loads(p.read_text()) if p.exists() else {}


def completed(directory):
    m = read_manifest(directory)
    return m.get("state", m.get("status")) == "complete"


def validate_completed_attempt(root, directory, stage, group):
    contract = json.loads((root / "frozen_contract.json").read_text())
    m = read_manifest(directory)
    identity = m.get("identity", {})
    if not completed(directory) or canonical_hash(identity) != m.get("identity_sha256"):
        raise ValueError("Missing/invalid completed worker identity")
    for key, expected in {"stage": stage, "case": group["case"],
                          "plan_sha256": contract["plan_sha256"],
                          "protocol_sha256": contract["protocol_sha256"],
                          "requests_sha256": contract["stage_requests_sha256"][stage],
                          "model_fingerprint_sha256": contract["model_fingerprints"][group["model"]]}.items():
        if identity.get(key) != expected:
            raise ValueError(f"Completed attempt identity mismatch: {key}")
    if m.get("model") != group["model"] or m.get("case") != group["case"]:
        raise ValueError("Completed model/config key mismatch")
    validate_actual_gpu(m, frozen_group_gpu(contract, group))
    codes = identity.get("code_sha256", {})
    if not codes:
        raise ValueError("Missing worker source identity")
    for path, digest in codes.items():
        if sha256_file(Path(path)) != digest:
            raise ValueError(f"Completed worker source changed: {path}")
        if path in contract["source_hashes"] and contract["source_hashes"][path] != digest:
            raise ValueError(f"Completed worker differs from frozen source: {path}")
    if identity.get("package_versions") != contract["package_versions"]:
        raise ValueError("Completed worker package versions mismatch")
    for name in ("generation.jsonl", "scores.jsonl", "requests.json"):
        if sha256_file(directory / name) != m.get("artifacts", {}).get(name):
            raise ValueError(f"Completed artifact hash mismatch: {name}")
    requests = json.loads((directory / "requests.json").read_text())
    if canonical_hash(requests) != identity["requests_sha256"]:
        raise ValueError("Completed request contents mismatch")
    rows = [json.loads(line) for line in (directory / "generation.jsonl").open() if line.strip()]
    expected_ids = [r["sample_id"] for r in requests]
    if [r["sample_id"] for r in rows] != expected_ids or len(set(expected_ids)) != len(rows):
        raise ValueError("Completed attempt has duplicate/missing/out-of-order rows")
    if any(r.get("status") != "complete" or r.get("identity_sha256") != m["identity_sha256"] for r in rows):
        raise ValueError("Completed rows have error/mismatched identities")
    scores = [json.loads(line) for line in (directory / "scores.jsonl").open() if line.strip()]
    if [s.get("sample_id") for s in scores] != expected_ids:
        raise ValueError("Completed scores have missing/duplicate sample IDs")
    for request, row, score in zip(requests, rows, scores, strict=True):
        if row.get("prompt_sha256") != request["prompt_sha256"] or row.get("gold") != request["gold"]:
            raise ValueError("Completed output differs from the frozen request")
        if score.get("identity_sha256") != m["identity_sha256"]:
            raise ValueError("Completed score identity mismatch")
        expected_score = score_response(row["scoring_text"], row["gold"])
        if any(score.get(k) != v for k, v in expected_score.items()):
            raise ValueError("Completed scores do not reproduce output scoring")
    if stage in {"smoke", "pilot"}:
        verification = json.loads((directory / "verification.json").read_text())
        if verification != m.get("generation_verification") or verification.get("passed") is not True:
            raise ValueError("Generation verification not bound to completed manifest")
        validate_generation_verification(verification, contract.get("verification_contract_id", LEGACY_VERIFICATION), m)
    summary = json.loads((directory / "summary.json").read_text())
    if summary["n_completed"] != len(requests) or summary["n_expected"] != len(requests):
        raise ValueError("Completed summary denominator mismatch")
    if summary["length_capped"] != sum(bool(r["length_capped"]) for r in rows):
        raise ValueError("Completed summary length-cap count mismatch")
    if stage == "formal" and (len(rows) != 1319 or summary.get("full_split") is not True):
        raise ValueError("Incomplete formal split")
    return m


def stage_sources(root, stage, groups):
    selected = []
    for g in groups:
        attempts = latest_attempts(root, stage, g["model"], g["case"])
        if not attempts or not completed(attempts[-1]):
            raise ValueError(f"Incomplete {stage}: {g}")
        validate_completed_attempt(root, attempts[-1], stage, g)
        selected.append({**g, "attempt": str(attempts[-1].resolve())})
    return selected


def paired_verification(smoke_dir, pilot_dir):
    """Require byte-identical greedy prefixes across two fresh model processes."""
    a = json.loads((smoke_dir / "verification.json").read_text())
    b = json.loads((pilot_dir / "verification.json").read_text())
    smoke_manifest, pilot_manifest = read_manifest(smoke_dir), read_manifest(pilot_dir)
    contract_id = validate_generation_verification(a, manifest=smoke_manifest)
    validate_generation_verification(b, contract_id, pilot_manifest)
    if smoke_dir.resolve() == pilot_dir.resolve():
        raise ValueError("Independent process verification requires separate attempts")
    device = canonical_gpu_uuid(smoke_manifest.get("environment", {}).get("gpu_uuid"))
    validate_actual_gpu(smoke_manifest, device)
    validate_actual_gpu(pilot_manifest, device)
    def prefixes(data, directory):
        records = data["records"]
        if len(records) != 2 or {r["sample_id"] for r in records} != {"train:0000", "train:0001"}:
            raise ValueError("Expected exactly two unique fixed verification prompts")
        eos_ids = read_manifest(directory)["generation"]["eos_token_ids"]
        out = {}
        for row in records:
            tokens = row["repeatability_prefix_32_token_ids"]
            if (not isinstance(tokens, list) or not 1 <= len(tokens) <= 32 or
                any(type(token) is not int or token < 0 for token in tokens) or
                (len(tokens) < 32 and tokens[-1] not in eos_ids)):
                raise ValueError("Verification prefix missing tokens without early EOS")
            out[row["sample_id"]] = (row["prompt_sha256"], tokens)
        return out
    av = prefixes(a, smoke_dir)
    bv = prefixes(b, pilot_dir)
    if av != bv:
        raise ValueError("Greedy prefixes differ across fresh smoke/pilot processes")
    return {"passed": True, "smoke": str(smoke_dir), "pilot": str(pilot_dir), "gpu_uuid": device,
            "verification_contract_id": contract_id,
            "smoke_verification_sha256": sha256_file(smoke_dir / "verification.json"),
            "pilot_verification_sha256": sha256_file(pilot_dir / "verification.json")}


def pilot_gate(root, groups, plan):
    pilots = stage_sources(root, "pilot", groups)
    smokes = stage_sources(root, "smoke", groups)
    records, errors = [], []
    for s, p in zip(smokes, pilots, strict=True):
        directory = Path(p["attempt"])
        summary = json.loads((directory / "summary.json").read_text())
        n = summary["n_completed"]
        caps = summary["length_capped"]
        record = {"model": p["model"], "case": p["case"], "n": n,
                  "length_capped_count": caps, "attempt": str(directory)}
        try:
            if n != 32 or caps / n > plan["pilot_budget_gate"]["threshold_length_capped_fraction"]:
                raise ValueError(f"Length budget gate failed: {caps}/{n}")
            record["repeatability"] = paired_verification(Path(s["attempt"]), directory)
            record["passed"] = True
        except Exception as exc:
            record.update(passed=False, error=str(exc))
            errors.append(record)
        records.append(record)
    result = {"created_at": now(), "passed": not errors, "groups": records,
              "next_action": "formal" if not errors else "review_train_pilot_budget_or_compatibility"}
    atomic_json(root / "pilot_gate.json", result)
    if errors:
        raise ValueError("Train pilot gate failed; formal generation has not been started")
    return result


def query_cuda_memory(python, gpu):
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=gpu, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    command = [python, "-B", "-c", "import torch,json; f,t=torch.cuda.mem_get_info(0); "
               "print(json.dumps({'free_bytes':f,'total_bytes':t}))"]
    result = subprocess.run(command, env=env, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def verify_formal_memory(root, groups, args):
    pilots = stage_sources(root, "pilot", groups)
    maximum = 0
    by_group = []
    for group in pilots:
        summary = json.loads((Path(group["attempt"]) / "summary.json").read_text())
        peak = max(summary["peak_memory_allocated_bytes"], summary["peak_memory_reserved_bytes"])
        maximum = max(maximum, peak)
        by_group.append({"model": group["model"], "case": group["case"], "peak_bytes": peak})
    observations = [{"gpu_uuid": gpu, **query_cuda_memory(args.python, gpu)} for gpu in args.gpu_uuids]
    required = int(maximum * 1.2)
    passed = maximum > 0 and all(x["free_bytes"] >= required for x in observations)
    atomic_json(root / "formal_memory_gate.json", {"created_at": now(), "passed": passed,
                "pilot_peaks": by_group, "required_free_bytes": required, "devices": observations})
    if not passed:
        raise ValueError("Formal GPU memory gate failed: pilot peak + 20% margin unavailable")


def host_memory_ok():
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) >= 80 * 1024 * 1024
    return False


def main():
    args = parse_args()
    root = args.run_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    args.gpu_uuids = [canonical_gpu_uuid(gpu) for gpu in args.gpu_uuids]
    stages = args.stages.split(",")
    if (not stages or len(set(stages)) != len(stages) or
        any(s not in {"smoke", "pilot", "formal"} for s in stages) or
        stages != sorted(stages, key=["smoke", "pilot", "formal"].index)):
        raise ValueError("Stages must be an ordered unique subset of smoke,pilot,formal")
    if (len(args.gpu_uuids) != len(args.cpu_sets) or len(args.gpu_uuids) > 2 or
        len(set(args.gpu_uuids)) != len(args.gpu_uuids)):
        raise ValueError("One CPU set per unique GPU and at most two GPUs are allowed")
    allocated = []
    for cpu_set in args.cpu_sets:
        cpus = {int(x) for x in cpu_set.split(",")}
        if cpus & set(range(8)) or any(cpus & old for old in allocated):
            raise ValueError("Software CPU sets must be disjoint and exclude EDA CPU 0-7")
        allocated.append(cpus)
    locks = []
    for gpu in args.gpu_uuids:
        lock_dir = HERE.parent / "results/gsm8k_full_completion/resource_locks"
        lock_dir.mkdir(parents=True, exist_ok=True)
        handle = (lock_dir / (gpu + ".lock")).open("a+")
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        locks.append(handle)
    plan = load_plan(args.plan)
    readiness = verify_readiness(args)
    groups = group_order(plan)
    assignments = fixed_gpu_assignments(groups, args.gpu_uuids)
    contract = {"plan_sha256": sha256_file(args.plan),
                "protocol_sha256": canonical_hash(plan["protocol"]),
                "stage_requests_sha256": {s: canonical_hash(prepare_requests(args.plan, s))
                                         for s in ("smoke", "pilot", "formal")},
                "model_fingerprints": {g["model"]: json.loads((args.model_identities /
                    (g["model"] + ".json")).read_text())["fingerprint_sha256"] for g in groups},
                "source_hashes": readiness["source_hashes"],
                "package_versions": readiness["package_versions"],
                "verification_contract_id": verification_contract_id(plan),
                "scheduling_schema": "fixed_gpu_slots_v1", "gpu_uuids": args.gpu_uuids,
                "group_gpu_uuids": assignments}
    contract_path = root / "frozen_contract.json"
    if contract_path.exists() and json.loads(contract_path.read_text()) != contract:
        raise ValueError("Run directory belongs to another frozen plan/source; start a new R")
    if not contract_path.exists():
        atomic_json(contract_path, contract)
    supervisor_no = len(list(root.glob("supervisor_AT*.json"))) + 1
    state_path = root / f"supervisor_AT{supervisor_no:03d}.json"
    state = {"schema": "scalellm_gsm8k_supervisor_v1", "state": "running", "pid": os.getpid(),
             "started_at": now(), "stages": stages, "gpu_uuids": args.gpu_uuids,
             "cpu_sets": args.cpu_sets, "plan_sha256": sha256_file(args.plan),
             "group_gpu_uuids": assignments,
             "command": sys.argv, "active": [], "completed": [], "failures": [],
             "worker_wallclock_timeout": None, "worker_silence_timeout": None}

    def save():
        state["updated_at"] = now()
        atomic_json(state_path, state)
        atomic_json(root / "current_state.json", state)

    save()
    active = {}
    try:
        for stage in stages:
            verify_readiness(args)
            if stage == "pilot":
                stage_sources(root, "smoke", groups)
            if stage == "formal":
                pilot_gate(root, groups, plan)
                verify_formal_memory(root, groups, args)
            state["current_stage"] = stage
            pending = {slot: [g for g in groups if assignments[group_key(g)] == gpu]
                       for slot, gpu in enumerate(args.gpu_uuids)}
            active = {}
            failure = False
            while any(pending.values()) or active:
                for slot, gpu in enumerate(args.gpu_uuids):
                    if failure or slot in active or not pending[slot]:
                        continue
                    if not host_memory_ok():
                        state["launch_blocker"] = "Host MemAvailable below 80 GiB; existing workers continue"
                        continue
                    state.pop("launch_blocker", None)
                    g = pending[slot].pop(0)
                    prior = latest_attempts(root, stage, g["model"], g["case"])
                    if prior and not args.allow_resume:
                        raise ValueError("Prior attempts exist; explicit --allow-resume required")
                    if prior and completed(prior[-1]):
                        validate_completed_attempt(root, prior[-1], stage, g)
                        state["completed"].append({"stage": stage, **g, "attempt": str(prior[-1]), "reused": True})
                        continue
                    directory = root / stage / g["model"] / g["case"] / f"AT{len(prior) + 1:03d}"
                    # The worker creates the new attempt directory; logs live next to it.
                    directory.parent.mkdir(parents=True, exist_ok=True)
                    out_log = directory.with_suffix(".stdout.log").open("x")
                    err_log = directory.with_suffix(".stderr.log").open("x")
                    command = ["taskset", "-c", args.cpu_sets[slot], args.python, "-B",
                               str(HERE / "run_gsm8k_worker.py"), "--plan", str(args.plan.resolve()),
                               "--stage", stage, "--model", str(args.model_root / g["model"]),
                               "--case", g["case"], "--model-identity",
                               str(args.model_identities / (g["model"] + ".json")),
                               "--output", str(directory), "--device", "cuda:0", "--batch-size", "1",
                               "--context-length", str(plan["protocol"]["max_sequence_length"]),
                               "--max-gen-toks", str(64 if stage == "smoke" else plan["protocol"]["max_gen_toks"])]
                    if stage in {"smoke", "pilot"}:
                        command.append("--verify-generation")
                    for old in prior:
                        if (old / "generation.jsonl").exists():
                            validate_actual_gpu(read_manifest(old), frozen_group_gpu(contract, g))
                            command += ["--resume-from", str(old)]
                    env = dict(os.environ)
                    env.update(CUDA_VISIBLE_DEVICES=gpu, OMP_NUM_THREADS="2", MKL_NUM_THREADS="2",
                               OPENBLAS_NUM_THREADS="2", TOKENIZERS_PARALLELISM="false",
                               HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_DATASETS_OFFLINE="1")
                    if args.driver_library_dir:
                        env["LD_LIBRARY_PATH"] = str(args.driver_library_dir.resolve()) + (
                            ":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
                    process = subprocess.Popen(command, env=env, stdout=out_log, stderr=err_log,
                                               cwd=HERE, start_new_session=True,
                                               pass_fds=(locks[slot].fileno(),))
                    record = {"stage": stage, "model": g["model"], "case": g["case"],
                              "gpu_uuid": gpu, "pid": process.pid, "attempt": str(directory),
                              "started_at": now(), "command": command,
                              "stdout": str(directory.with_suffix('.stdout.log')),
                              "stderr": str(directory.with_suffix('.stderr.log'))}
                    active[slot] = (process, record, out_log, err_log)
                    state["active"] = [x[1] for x in active.values()]
                    save()
                    print(json.dumps({"event": "worker_started", **record}), flush=True)
                for slot, (process, record, out_log, err_log) in list(active.items()):
                    code = process.poll()
                    if code is None:
                        continue
                    out_log.close()
                    err_log.close()
                    record.update(exit_code=code, finished_at=now())
                    del active[slot]
                    if code == 0 and completed(Path(record["attempt"])):
                        validate_completed_attempt(root, Path(record["attempt"]), stage, record)
                        state["completed"].append(record)
                    else:
                        state["failures"].append(record)
                        failure = True
                    print(json.dumps({"event": "worker_finished", **record}), flush=True)
                state["active"] = [x[1] for x in active.values()]
                state["pending_count"] = sum(len(queue) for queue in pending.values())
                save()
                if failure and not active:
                    raise RuntimeError("A worker failed; drained active workers and stopped new launches")
                if any(pending.values()) or active:
                    time.sleep(3)
            atomic_json(root / (stage + "_sources.json"), {"created_at": now(), "groups": stage_sources(root, stage, groups)})
        state["state"] = "completed"
        if "formal" in stages:
            review_path = root / "finalizer_readiness.json"
            if not review_path.exists():
                state["state"] = "generated_pending_review"
            else:
                review = json.loads(review_path.read_text())
                if review.get("ready") is not True:
                    raise ValueError("Final result validation is not ready")
                for path, digest in review["source_hashes"].items():
                    if sha256_file(Path(path)) != digest:
                        raise ValueError(f"Finalizer source changed: {path}")
                state["current_stage"] = "independent_scoring_and_table_update"
                save()
                for number, command in enumerate(review["commands"], 1):
                    if command[0] != args.python or Path(command[2]).parent.resolve() != HERE:
                        raise ValueError("Finalizer command is outside the reviewed evaluation entrypoint")
                    env = dict(os.environ, CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="2", MKL_NUM_THREADS="2")
                    log_path = root / f"finalizer_supervisor_AT{supervisor_no:03d}_{number}.log"
                    state.setdefault("finalizer_logs", []).append(str(log_path))
                    save()
                    with log_path.open("x") as log:
                        subprocess.run(command, cwd=HERE, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
                state["result_validation_completed"] = True
    except BaseException as exc:
        # Keep resource locks until active workers finish naturally. Children also
        # inherit their lock FD so abrupt supervisor death cannot unlock a busy GPU.
        state.update(state="failed", error=str(exc), traceback=traceback.format_exc())
        state["active"] = [x[1] for x in active.values()]
        save()
        while active:
            for slot, (process, record, out_log, err_log) in list(active.items()):
                code = process.poll()
                if code is None:
                    continue
                out_log.close()
                err_log.close()
                record.update(exit_code=code, finished_at=now(), drained_after_supervisor_error=True)
                state["failures"].append(record)
                del active[slot]
            state["active"] = [x[1] for x in active.values()]
            save()
            if active:
                time.sleep(3)
        raise
    finally:
        state["finished_at"] = now()
        save()
        for handle in locks:
            handle.close()


if __name__ == "__main__":
    main()
