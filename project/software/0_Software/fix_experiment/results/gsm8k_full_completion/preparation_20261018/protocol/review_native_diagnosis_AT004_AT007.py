#!/usr/bin/env python3
"""CPU-only independent review of immutable AT004--AT007 evidence."""
import datetime
import hashlib
import json
import os
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "native_input_diagnosis"
FIX = HERE.parents[3]
RUN = FIX / "results/gsm8k_full_completion/R002_gsm8k_native_cache_v2"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(tensor):
    return hashlib.sha256(tensor.contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()


def compare(left, right):
    left, right = left.float(), right.float()
    finite = bool(torch.isfinite(left).all() and torch.isfinite(right).all())
    same = left.shape == right.shape
    return {"exact": bool(same and finite and torch.equal(left, right)), "finite": finite,
            "shape": list(left.shape), "elements_compared": left.numel(),
            "left_sha256": digest(left), "right_sha256": digest(right),
            "max_abs_difference": float((left-right).abs().max()) if finite and same else None}


def main():
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == ""
    assert set(os.sched_getaffinity(0)) == {8, 9}
    torch.set_num_threads(2)
    analysis = json.loads((BASE / "analysis_AT001.json").read_text())
    analyzed = {v["attempt"]: v for v in analysis["attempts"]}
    result = {"schema": "scalellm_gsm8k_determinism_review_v2",
              "reviewed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "reviewer": "A010 /root/gsm8k_protocol", "execution_state": "review_completed_AT004_AT007",
              "verdict": "same-prefix native logits repeat failure confirmed; layer25 up_proj is the first observed differing output, isolated cause and repair unvalidated",
              "applicability": "Llama-3.1-8B-Instruct BF16 eager; two training prompts; diagnostic GPU1 only",
              "CPU_only": True, "cpu_affinity": sorted(os.sched_getaffinity(0)),
              "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
              "review_source": {"path": str(Path(__file__).resolve()), "sha256": sha(__file__)},
              "analysis": {"path": str(BASE / "analysis_AT001.json"), "sha256": sha(BASE / "analysis_AT001.json")},
              "attempts": [], "mismatches": [], "native_pairs_recomputed": 0,
              "manual_pairs_recomputed": 0, "raw_files_sha256_verified": 0}
    def require(condition, detail):
        if not condition:
            result["mismatches"].append(detail)
    identities = {}
    for attempt in ["AT004", "AT005", "AT006", "AT007"]:
        path = BASE / attempt / "diagnosis.json"
        d = json.loads(path.read_text())
        ar = analyzed[attempt]
        source = BASE / attempt / "source_snapshot.py"
        a = {"attempt": attempt, "diagnosis_path": str(path), "diagnosis_sha256": sha(path),
             "source_sha256": sha(source), "state": d["state"], "command": d["command"],
             "plan_sha256": d["plan_sha256"], "runtime_flags": d["runtime_flags"],
             "gpu_uuid_actual": d["gpu_uuid_actual"], "cpu_affinity": d["cpu_affinity"], "records": []}
        require(a["source_sha256"] == d["source_sha256"] == ar["source_sha256"], attempt+": source identity")
        require(a["diagnosis_sha256"] == ar["diagnosis_sha256"], attempt+": analysis diagnosis identity")
        require(d["state"] == "complete", attempt+": completed state")
        require(d["plan_sha256"] == sha(RUN / "frozen_inputs/plan.json"), attempt+": frozen plan identity")
        require(set(d["cpu_affinity"]) == {18, 19}, attempt+": allocated CPUs")
        require(d["gpu_uuid_actual"].removeprefix("GPU-") == "d87ce710-76bf-872d-9739-f0d7c9b52533", attempt+": GPU identity")
        for row, summary in zip(d["records"], ar["rows"]):
            sample = row["sample_id"]
            ident = (row["prompt_sha256"], row["input_tokens"])
            require(identities.setdefault(sample, ident) == ident, attempt+": prompt identity "+sample)
            rawpath = BASE / attempt / (sample.replace(":", "_")+"_raw_logits.pt")
            rawsha = sha(rawpath)
            require(rawsha == row["raw_logits"]["sha256"], attempt+": raw hash "+sample)
            result["raw_files_sha256_verified"] += 1
            raw = torch.load(rawpath, map_location="cpu", weights_only=True)
            rec = {"sample_id": sample, "prompt_sha256": ident[0], "input_tokens": ident[1],
                   "raw_path": str(rawpath), "raw_sha256": rawsha,
                   "model_snapshots_equal": row["before"] == row["after_native_repeats"] == row["after_all"],
                   "all_modules_eval": not any(row["before"]["all_module_training"].values()),
                   "native_repeats": {}}
            require(rec["model_snapshots_equal"] and rec["all_modules_eval"], attempt+": model snapshots "+sample)
            for count in [17, 32]:
                prefix = "native" if count == 17 else "native32"
                left, right = raw[prefix+"_first_logits"], raw[prefix+"_second_logits"]
                idsleft = row["native_generated_ids_first" if count == 17 else "native32_first_generated_ids"]
                idsright = row["native_generated_ids_second" if count == 17 else "native32_second_generated_ids"]
                scope = row[f"native{count}_same_prefix_scope"]
                recorded = row["comparisons"]["first_native_vs_second_native"] if count == 17 else scope["steps"]
                fork = next((i for i, (x, y) in enumerate(zip(idsleft, idsright)) if x != y), None)
                valid = min(len(left), len(right), (fork+1) if fork is not None else count)
                require(len(left) == len(right) == len(idsleft) == len(idsright) == count,
                        f"{attempt}:{sample}:{count} lengths")
                require(scope["first_token_fork"] == fork and scope["same_input_prefix_steps"] == valid,
                        f"{attempt}:{sample}:{count} prefix scope")
                metrics = [compare(left[i], right[i]) for i in range(valid)]
                require(metrics == recorded, f"{attempt}:{sample}:{count} recorded metrics")
                argmax_match = ([int(v.argmax(-1).item()) for v in left] == idsleft and
                                [int(v.argmax(-1).item()) for v in right] == idsright)
                require(argmax_match, f"{attempt}:{sample}:{count} logits vs generated tokens")
                result["native_pairs_recomputed"] += valid
                rec["native_repeats"][str(count)] = {"token_lengths": [len(idsleft), len(idsright)],
                    "tokens_equal": idsleft == idsright, "argmax_matches_recorded_tokens": argmax_match,
                    "first_token_fork": fork, "same_input_prefix_steps": valid,
                    "exact_steps": sum(v["exact"] for v in metrics), "finite_steps": sum(v["finite"] for v in metrics),
                    "prefill_max_abs_difference": metrics[0]["max_abs_difference"],
                    "steps": [{"step": i, "exact": v["exact"], "max_abs_difference": v["max_abs_difference"]}
                              for i, v in enumerate(metrics)]}
            prefill = rec["native_repeats"]["17"]["steps"][0]
            require(prefill["exact"] == summary["prefill_repeat_exact"] and
                    prefill["max_abs_difference"] == summary["prefill_repeat_max_abs"], attempt+": analysis prefill "+sample)
            for key, lhs, rhs in [
                ("first_native_vs_warm_manual_prefill", raw["native_first_logits"][0], raw["warm_manual_logits"]),
                ("second_native_vs_warm_manual_prefill", raw["native_second_logits"][0], raw["warm_manual_logits"]),
                ("first_native_vs_exact_kwargs_replay", raw["native_first_logits"][0], raw["exact_kwargs_replay_logits"]),
                ("second_native_vs_exact_kwargs_replay", raw["native_second_logits"][0], raw["exact_kwargs_replay_logits"]),
                ("warm_manual_vs_exact_kwargs_replay", raw["warm_manual_logits"], raw["exact_kwargs_replay_logits"]),
                ("warm_manual_vs_explicit_position", raw["warm_manual_logits"], raw["explicit_position_logits"])]:
                require(compare(lhs, rhs) == row["comparisons"][key], attempt+": "+sample+":"+key)
                result["manual_pairs_recomputed"] += 1
            probes = row.get("symmetric_native_probes", [])
            if probes:
                require(len(probes) == 5, attempt+": probe call count "+sample)
                first, second = probes[:2]
                different = [name for name, value in first["modules"].items() if value != second["modules"][name]]
                rec["symmetric_probe_review"] = {"probe_calls": len(probes),
                    "first_two_are_measured_native17_calls": "--warmup-native-count" not in d["command"],
                    "prefill_inputs_equal": first["inputs"] == second["inputs"],
                    "all_five_prefill_inputs_equal": all(p["inputs"] == first["inputs"] for p in probes),
                    "observed_modules": len(first["modules"]), "different_outputs_in_execution_order": different,
                    "all_forward_vs_api_prefills_exact_finite": all(p["forward_vs_api_prefill"]["exact"] and p["forward_vs_api_prefill"]["finite"] for p in probes),
                    "measured_forward_vs_api_hashes_match_raw": all(probes[i]["forward_vs_api_prefill"]["right_sha256"] == digest(raw[name][0].float()) for i, name in enumerate(["native_first_logits", "native_second_logits"])),
                    "layers_0_24_output_metadata_equal": all(first["modules"][f"model.layers.{i}"] == second["modules"][f"model.layers.{i}"] for i in range(25))}
                if attempt == "AT007":
                    rec["symmetric_probe_review"]["layer25_matching_detail_outputs"] = [name for name in first["modules"] if name.startswith("model.layers.25.") and name not in different]
                require(rec["symmetric_probe_review"]["prefill_inputs_equal"] and rec["symmetric_probe_review"]["all_forward_vs_api_prefills_exact_finite"] and rec["symmetric_probe_review"]["measured_forward_vs_api_hashes_match_raw"], attempt+": symmetric probes "+sample)
            a["records"].append(rec)
            del raw
        result["attempts"].append(a)
    manifest_path = RUN / "frozen_source_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    result["frozen_source_manifest"] = {"path": str(manifest_path), "sha256": sha(manifest_path)}
    result["frozen_source_hash_matches"] = {path: sha(path) == expected for path, expected in manifest.items()}
    require(all(result["frozen_source_hash_matches"].values()), "production frozen source identity")
    result["analysis_findings_review"] = [
        "AT004 source explicitly performs controlled native17/native32 repeats before input capture and releases GPU output/cache after immediate CPU snapshots.",
        "All 392 native repeat pairs have identical input prefixes; token lengths and argmax identities were independently checked against saved raw logits.",
        "AT005 three warmups did not pass the first-prompt prefill exact gate.",
        "AT006 first observed full-layer difference is layer25; AT007 detailed hooks narrow the first observed output difference to layer25.mlp.up_proj.",
        "AT007 first-prompt layers0-24 and layer25 input norm/Q/K/V/O/post-attention norm/gate outputs match; second prompt observed path matches.",
        "The analysis finding is accepted as an observed-boundary localization, not yet an isolated GEMM cause or implementation repair."]
    result["limitations"] = [
        "Intermediate module tensors were not retained; reviewer verifies recorded output metadata/hash relations, not recomputed intermediate hashes.",
        "AT007 does not directly capture up_proj input/weight bytes; model mutation guards cover parameter versions and registered buffers, not complete parameter byte hashes.",
        "AT006/007 probes synchronize and copy outputs symmetrically; their instrumented execution is distinct from uninstrumented AT004, which independently also fails.",
        "Capture-probe-vs-replay cannot be recomputed because capture-probe raw logits were not saved.",
        "Local 32-token equality is not the required full new-matrix hard-gate qualification, and no formal result is accepted."]
    result["AT008_status"] = "actually launched by A011; independent review pending completed raw evidence"
    result["minimum_repair_evidence"] = [
        "Isolated controls retain original x/weight byte hashes, shapes, dtype, strides, device and mutation guards; compare complete outputs with fixed vs distinct fresh retained out buffers and explicit synchronization.",
        "Any candidate change must exhibit exact/finite repeated isolated outputs and exact/finite uninstrumented native prefills/steps on both previously failing and passing prompts; report unsuccessful variants.",
        "Record effective backend flags, packages, device UUID, source identities, semantics and resource impact; neither token-only equality nor a tolerance relaxation closes the exact gate.",
        "Controller decides compatibility and new R/version boundary before frozen production edits or restart; preserve R001/R002 failures and do not import prior smoke passes across a changed backend.",
        "A repaired evaluation still needs all 30 cases through v2 manual/native and rebuilt-cache gates, corruption control, independent-process32 repeat and fresh pilot memory/runtime qualification before formal test."]
    output = HERE / "determinism_review_AT002.json"
    with output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({k: result[k] for k in ["execution_state", "native_pairs_recomputed", "manual_pairs_recomputed", "raw_files_sha256_verified", "mismatches"]}))
    if result["mismatches"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
