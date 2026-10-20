#!/usr/bin/env python3
"""Independent CPU-only reconstruction of saved AT008 hashes and comparisons."""
import datetime
import hashlib
import json
import os
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "native_input_diagnosis" / "AT008"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def digest(t):
    return hashlib.sha256(t.detach().contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()


def compare(a, b):
    a, b = a.reshape(1, -1).float(), b.reshape(1, -1).float()
    finite = bool(torch.isfinite(a).all() and torch.isfinite(b).all())
    same = a.shape == b.shape
    return {"exact": bool(same and finite and torch.equal(a, b)), "finite": finite,
            "shape": list(a.shape), "elements_compared": a.numel(),
            "left_sha256": digest(a), "right_sha256": digest(b),
            "max_abs_difference": float((a-b).abs().max()) if finite and same else None}


def main():
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == ""
    assert set(os.sched_getaffinity(0)) == {8, 9}
    torch.set_num_threads(2)
    d = json.loads((BASE / "diagnosis.json").read_text())
    report = {"schema": "scalellm_gsm8k_isolated_operator_review_v1",
              "reviewed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "reviewer": "A010 /root/gsm8k_protocol", "execution_state": "review_completed_AT008",
              "applicability": "Llama-3.1-8B-Instruct BF16 eager, train:0000, GPU1, one layer25 up_proj",
              "CPU_only": True, "cpu_affinity": sorted(os.sched_getaffinity(0)),
              "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
              "source_review": {"path": str(Path(__file__).resolve()), "sha256": sha(__file__)},
              "diagnosis": {"path": str(BASE / "diagnosis.json"), "sha256": sha(BASE / "diagnosis.json")},
              "diagnostic_snapshot": {"path": str(BASE / "source_snapshot.py"), "sha256": sha(BASE / "source_snapshot.py")},
              "comparisons_recomputed": 0, "mismatches": []}
    def require(test, detail):
        if not test:
            report["mismatches"].append(detail)
    require(report["diagnostic_snapshot"]["sha256"] == d["source_sha256"], "source snapshot identity")
    require(d["state"] == "complete", "completed state")
    rawpath = BASE / "raw_operands_and_outputs.pt"
    report["raw_tensors"] = {"path": str(rawpath), "sha256": sha(rawpath)}
    require(report["raw_tensors"]["sha256"] == d["raw_tensors"]["sha256"], "raw artifact hash")
    raw = torch.load(rawpath, map_location="cpu", weights_only=True)
    require(sorted(raw) == d["raw_tensors"]["keys"], "raw key identities")
    require(all(t.device.type == "cpu" for t in raw.values()), "CPU load")
    require(len({t.untyped_storage().data_ptr() for t in raw.values()}) == len(raw), "saved tensors have distinct CPU storages")
    descriptors = {"fixed_input": d["fixed_input"], "fixed_weight": d["weight_after"]}
    for row in d["native_calls"]:
        for field in ["input", "output"]:
            descriptors[row["key"]+"_"+field] = row[field]
    for row in d["isolated_calls"]:
        descriptors[row["key"]] = row["output"]
    report["raw_descriptors_verified"] = []
    for key, meta in descriptors.items():
        t = raw[key]
        require(digest(t) == meta["sha256"], key+": byte hash")
        require(list(t.shape) == meta["shape"] and str(t.dtype) == meta["dtype"], key+": shape/dtype")
        require(t.numel()*t.element_size() == meta["storage_nbytes"], key+": logical byte count")
        report["raw_descriptors_verified"].append(key)
    for row in d["native_calls"]:
        require(digest(raw[row["key"]+"_logits"]) == row["logits_sha256"], row["key"]+": logit hash")
    require(digest(raw["fixed_weight"].t()) == d["transposed_weight"]["sha256"], "transposed weight hash")
    require(digest(raw["fixed_input"].reshape(-1,4096)) == d["flat_input"]["sha256"], "flat input hash")
    def check(a, b, expected, label):
        got = compare(raw[a], raw[b])
        require(got == {k: v for k, v in expected.items() if k not in ["key", "series"]}, label)
        report["comparisons_recomputed"] += 1
        return {"exact": got["exact"], "finite": got["finite"], "max_abs_difference": got["max_abs_difference"]}
    comparisons = d["comparisons"]
    report["native_comparisons"] = {"input": [], "output": [], "logits": []}
    for field, recorded in [("input", "native_input_repeats"), ("output", "native_output_repeats"), ("logits", "native_logits_repeats")]:
        for i in range(4):
            value = check("native_0_"+field, f"native_{i}_"+field, comparisons[recorded][i], recorded+str(i))
            report["native_comparisons"][field].append(value)
    for row in comparisons["isolated_vs_native0"]:
        check("native_0_output", row["key"], row, "isolated_vs_native0:"+row["key"])
    report["within_series"] = {}
    for name, expected in comparisons["within_series"].items():
        report["within_series"][name] = [check(name+"_0", name+f"_{i}", value, name+str(i)) for i, value in enumerate(expected)]
    report["cross_series"] = [check("functional_linear_0", row["series"]+"_0", row, "cross_series:"+row["series"]) for row in comparisons["cross_series"]]
    wrows = [d["weight_before"]]+[r["weight"] for r in d["native_calls"]]+[d["weight_after"]]
    fields = ["shape", "stride", "dtype", "device", "storage_offset", "contiguous", "data_ptr", "storage_base_ptr", "storage_nbytes"]
    report["weight_observations"] = {
        "shape": d["weight_before"]["shape"], "dtype": d["weight_before"]["dtype"],
        "bytes": d["weight_before"]["storage_nbytes"],
        "all_logged_storage_and_layout_descriptors_equal": all(all(row[k] == wrows[0][k] for k in fields) for row in wrows),
        "before_sha256": d["weight_before"]["sha256"],
        "native_pre_sha256": [r["weight"]["sha256"] for r in d["native_calls"]],
        "after_sha256": d["weight_after"]["sha256"],
        "raw_final_weight_hash_verified": digest(raw["fixed_weight"]) == d["weight_after"]["sha256"],
        "initial_and_intermediate_weight_copies_saved": False,
        "before_vs_after_bytes_equal": d["weight_before"]["sha256"] == d["weight_after"]["sha256"]}
    report["isolated_operand_review"] = {
        "all_18_calls_input_hash_matches_saved_fixed_input": all(r["input_sha256"] == digest(raw["fixed_input"]) for r in d["isolated_calls"]),
        "all_18_calls_weight_hash_matches_saved_final_weight": all(r["weight_sha256"] == digest(raw["fixed_weight"]) for r in d["isolated_calls"]),
        "all_18_complete_outputs_equal_final_native3_output": all(torch.equal(raw[r["key"]].reshape(-1), raw["native_3_output"].reshape(-1)) for r in d["isolated_calls"]),
        "fixed_input_before_after_equal": d["fixed_input"]["sha256"] == d["fixed_input_after"]["sha256"],
        "reused_output_pointer_count": len({r["output"]["data_ptr"] for r in d["isolated_calls"] if r["series"] == "mm_reused_output"}),
        "fresh_output_pointer_count": len({r["output"]["data_ptr"] for r in d["isolated_calls"] if r["series"] == "mm_fresh_output"}),
        "fresh_output_allocations_retained_until_end_of_series": True,
        "reported_all_isolated_operands_identical_false_explanation": "diagnostic compares each isolated weight hash with initial weight_before rather than the final fixed_weight; all 18 isolated calls in fact have the same final-weight hash"}
    # Compare additional identical pre-hash native calls, absent from original native0 comparisons.
    report["native1_vs_native2_additional_control"] = {
        "input_byte_hash_equal": d["native_calls"][1]["input"]["sha256"] == d["native_calls"][2]["input"]["sha256"],
        "pre_weight_byte_hash_equal": d["native_calls"][1]["weight"]["sha256"] == d["native_calls"][2]["weight"]["sha256"],
        "output": {k: v for k, v in compare(raw["native_1_output"],raw["native_2_output"]).items() if k in ["exact", "finite", "max_abs_difference"]}}
    report["hash_capture_implementation_review"] = [
        "digest uses detach().contiguous().cpu(), no non_blocking=True or custom stream; CPU bytes are consumed immediately before return, so recorded hashes are completed CPU reads under PyTorch default copy semantics.",
        "raw cpu(t) uses detach().cpu().contiguous().clone(), creating an independent CPU tensor for each saved output/input, and loaded raw tensors have distinct CPU storages.",
        "The weight is contiguous with storage_offset=0, stable same GPU data/storage pointers, exact full logical/storage size 117440512 bytes. No strided gap or shape/pointer substitution appears in the recorded descriptors.",
        "All saved operand/output byte hashes reproduce on CPU, including final weight and its transposed logical byte ordering; this validates the implemented byte-hash convention for retained tensors.",
        "The script contains no explicit in-place weight mutation; it records unexpected byte-hash changes. Hash-only earlier weights cannot now be independently rehashed or compared elementwise."]
    report["verdict"] = "unexpected weight byte identity instability confirmed in completed log; saved final fixed operands yield 18 exact complete outputs; no backend, allocator, hardware or software root cause established and no repair qualified"
    report["minimum_next_evidence"] = [
        "Read-only CPU comparison of saved final weight against the exact checkpoint tensor to identify differing elements/bytes and rule out checkpoint identity substitution.",
        "For any authorized future probe, retain immediate independent CPU copies of weight before/after loading and immediately before/after each target linear call, record raw/float bit patterns, parameter versions and storage aliasing; preserve effective backend/device identities.",
        "Compare identical-byte input/weight across full call with synchronization on both boundaries; native1/native2 currently have equal pre-hashes but different outputs, so prehash-only changes do not fully explain output variation.",
        "Repair must preserve checkpoint/QDQ semantics and exact gates, close byte-mutation guards and uninstrumented native parity on affected/control prompts, then pass a fresh versioned 30-case v2 qualification and independent-process/pilot gates."]
    output = HERE / "determinism_review_AT003.json"
    with output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"execution_state": report["execution_state"], "comparisons_recomputed": report["comparisons_recomputed"],
                      "raw_descriptors_verified": len(report["raw_descriptors_verified"]), "mismatches": report["mismatches"],
                      "native1_vs_native2": report["native1_vs_native2_additional_control"]}))
    if report["mismatches"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
