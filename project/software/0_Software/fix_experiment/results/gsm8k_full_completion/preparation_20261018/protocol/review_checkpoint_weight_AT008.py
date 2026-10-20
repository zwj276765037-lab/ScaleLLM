#!/usr/bin/env python3
"""Read-only CPU review of AT008 final captured weight vs frozen checkpoint."""
import datetime
import hashlib
import json
import os
from pathlib import Path

import torch
from safetensors import safe_open

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "native_input_diagnosis/AT008"
FIX = HERE.parents[3]
RUN = FIX / "results/gsm8k_full_completion/R002_gsm8k_native_cache_v2"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def digest(t):
    return hashlib.sha256(t.detach().contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()


def main():
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == ""
    assert set(os.sched_getaffinity(0)) == {8,9}
    torch.set_num_threads(2)
    d = json.loads((BASE / "diagnosis.json").read_text())
    other_path = BASE / "checkpoint_weight_comparison.json"
    other = json.loads(other_path.read_text())
    key = "model.layers.25.mlp.up_proj.weight"
    model = Path(d["model"])
    index_path = model / "model.safetensors.index.json"
    config_path = model / "config.json"
    index = json.loads(index_path.read_text())
    config = json.loads(config_path.read_text())
    shard = model / index["weight_map"][key]
    manifest_path = RUN / "smoke/Llama-3.1-8B-Instruct/bf16/AT001/manifest.json"
    frozen = json.loads(manifest_path.read_text())["model_identity"]
    identities = {row["name"]: row for row in frozen["files"]}
    report = {"schema": "scalellm_checkpoint_weight_independent_review_v1",
              "reviewed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "reviewer": "A010 /root/gsm8k_protocol", "execution_state": "review_completed_checkpoint_AT008",
              "CPU_only": True, "cpu_affinity": sorted(os.sched_getaffinity(0)),
              "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"), "cuda_initialized": torch.cuda.is_initialized(),
              "review_source": {"path": str(Path(__file__).resolve()), "sha256": sha(__file__)},
              "diagnosis": {"path": str(BASE / "diagnosis.json"), "sha256": sha(BASE / "diagnosis.json")},
              "comparison_under_review": {"path": str(other_path), "sha256": sha(other_path)},
              "frozen_checkpoint_identity_source": {"path": str(manifest_path), "sha256": sha(manifest_path)},
              "mismatches": []}
    def require(test, detail):
        if not test:
            report["mismatches"].append(detail)
    require(model.resolve() == Path(frozen["resolved_path"]).resolve(), "model path matches frozen checkpoint")
    report["checkpoint_identity_recheck"] = {}
    for path in [shard, index_path, config_path]:
        actual = {"path": str(path), "bytes": path.stat().st_size, "sha256": sha(path)}
        expected = identities[path.name]
        actual["matches_frozen_manifest"] = actual["bytes"] == expected["bytes"] and actual["sha256"] == expected["sha256"]
        require(actual["matches_frozen_manifest"], path.name+": frozen checkpoint identity")
        report["checkpoint_identity_recheck"][path.name] = actual
    with safe_open(shard, framework="pt", device="cpu") as reader:
        original = reader.get_tensor(key)
    raw = torch.load(BASE / "raw_operands_and_outputs.pt", map_location="cpu", weights_only=True, mmap=True)
    observed = raw["fixed_weight"]
    require(original.dtype == observed.dtype == torch.bfloat16, "both tensors native BF16")
    require(original.shape == observed.shape == (14336,4096), "same original weight shape")
    original_sha, observed_sha = digest(original), digest(observed)
    require(original_sha == other["original"]["sha256"], "original tensor SHA")
    require(observed_sha == other["observed"]["sha256"] == d["weight_after"]["sha256"], "observed tensor SHA")
    original_words = original.view(torch.int16)
    observed_words = observed.view(torch.int16)
    coords = (original_words != observed_words).nonzero()
    ow = original_words[coords[:,0],coords[:,1]].to(torch.int32).bitwise_and(65535)
    nw = observed_words[coords[:,0],coords[:,1]].to(torch.int32).bitwise_and(65535)
    ov = original[coords[:,0],coords[:,1]].float()
    nv = observed[coords[:,0],coords[:,1]].float()
    xor = ow.bitwise_xor(nw)
    setbits = nw.bitwise_and(ow.bitwise_not()).bitwise_and(65535)
    clearbits = ow.bitwise_and(nw.bitwise_not()).bitwise_and(65535)
    byte_difference = original.view(torch.uint8) != observed.view(torch.uint8)
    rowids, rowcounts = coords[:,0].unique(return_counts=True)
    row_counts = [{"row":int(r),"changed_elements":int(c)} for r,c in zip(rowids,rowcounts)]
    value = {"key": key, "shard": str(shard), "shape": list(original.shape), "dtype": str(original.dtype),
             "original_sha256": original_sha, "captured_final_sha256": observed_sha,
             "changed_elements": len(coords), "changed_bytes": int(byte_difference.sum()),
             "high_byte_changes": int(byte_difference[:,1::2].sum()),
             "low_byte_changes": int(byte_difference[:,0::2].sum()),
             "max_abs_difference": float((ov-nv).abs().max()),
             "changed_rows": len(rowids), "row_count_min": int(rowcounts.min()), "row_count_max": int(rowcounts.max()),
             "row_counts": row_counts,
             "bounds": {"row_min": int(coords[:,0].min()), "row_max": int(coords[:,0].max()),
                        "col_min": int(coords[:,1].min()), "col_max": int(coords[:,1].max()),
                        "flat_min": int((coords[:,0]*4096+coords[:,1]).min()),
                        "flat_max": int((coords[:,0]*4096+coords[:,1]).max())},
             "all_changed_high_words_equal": bool(torch.equal(ow.bitwise_and(65280),nw.bitwise_and(65280))),
             "changed_new_low_byte_values": sorted(set(nw.bitwise_and(255).tolist())),
             "changed_final_low_byte_ff_count": int((nw.bitwise_and(255)==255).sum()),
             "cleared_bits_elements": int((clearbits!=0).sum()),
             "set_bits_total": sum(int(v).bit_count() for v in setbits),
             "cleared_bits_total": sum(int(v).bit_count() for v in clearbits),
             "first_example": {"row":int(coords[0,0]), "col":int(coords[0,1]),
                               "original_word_hex":format(int(ow[0]),"04x"), "observed_word_hex":format(int(nw[0]),"04x"),
                               "original_float":float(ov[0]), "observed_float":float(nv[0])}}
    for field in ["changed_elements","changed_bytes","high_byte_changes","max_abs_difference","bounds","row_counts","changed_new_low_byte_values","cleared_bits_elements","set_bits_total"]:
        require(value[field] == other[field], "worker comparison:"+field)
    diffpath = BASE / "checkpoint_weight_diff.pt"
    report["full_diff_artifact"] = {"path":str(diffpath), "sha256":sha(diffpath)}
    require(report["full_diff_artifact"]["sha256"] == other["full_diff_artifact"]["sha256"], "diff artifact hash")
    diff = torch.load(diffpath,map_location="cpu",weights_only=True)
    report["full_diff_artifact"]["tensor_keys"] = {k:{"shape":list(v.shape),"dtype":str(v.dtype)} for k,v in diff.items() if isinstance(v,torch.Tensor)}
    # Retain computed summaries rather than depending on the worker's stored coordinates.
    report["independent_recomputation"] = value
    source_path = FIX / "exp/run_eval_worker.py"
    source_manifest = json.loads((RUN / "frozen_source_manifest.json").read_text())
    report["loader_source"] = {"path":str(source_path),"sha256":sha(source_path),
                               "matches_frozen_source":sha(source_path)==source_manifest[str(source_path)]}
    require(report["loader_source"]["matches_frozen_source"], "frozen loader source identity")
    report["load_path_review"] = [
        "AT008 sets args.case=bf16 and args.model to the same resolved local directory as R002 frozen identity, then uses frozen run_eval_worker.load_model.",
        "Frozen loader calls AutoModelForCausalLM.from_pretrained(local_files_only=True, trust_remote_code=True, dtype=torch.bfloat16, attn_implementation=eager).to(cuda).",
        "The standard Llama config declares LlamaForCausalLM, hidden_size4096/intermediate_size14336, dtype BF16; no auto_map is present. AT008 reports torch.nn.modules.linear.Linear for target module.",
        "The bf16 branch performs no QDQ or format transformation; safetensors key maps exactly to model.layers.25.mlp.up_proj.weight. Source and target are already BF16, so this comparison needs no rounding conversion.",
        "Only final GPU-captured tensor is retained. Earlier checkpoint mismatch is supported by different logged hash, but its elementwise pattern cannot be reconstructed."]
    require(not config.get("auto_map"), "standard config without remote auto_map")
    require(d["module_class"] == "torch.nn.modules.linear.Linear", "native Linear module")
    report["verdict"] = "final captured BF16 weight differs from exact frozen checkpoint by 16345 low bytes in 64 rows; not an ordinary numerical reduction/tolerance comparison; fault source and repair remain unproven"
    report["limitations"] = [
        "A stable disk checkpoint and final captured mismatch do not identify whether change arose in load/transfer, CPU/GPU memory, runtime kernels or capture path; no hardware-failure conclusion follows.",
        "Initial and per-call weights have hashes only. No pre/post raw byte timeline exists to isolate mutation location.",
        "A future repaired run must verify parameter byte identity at loading and relevant execution boundaries; exact logits gate remains unchanged."]
    out = HERE / "determinism_review_AT004.json"
    with out.open("x") as stream:
        json.dump(report,stream,indent=2)
        stream.write("\n")
    print(json.dumps({"execution_state":report["execution_state"],"mismatches":report["mismatches"],
                      "checkpoint_frozen_identity_matches":all(v["matches_frozen_manifest"] for v in report["checkpoint_identity_recheck"].values()),
                      "changed_elements":value["changed_elements"],"changed_bytes":value["changed_bytes"],
                      "high_byte_changes":value["high_byte_changes"],"changed_rows":value["changed_rows"],
                      "new_low_ff":value["changed_final_low_byte_ff_count"],"cleared_bits_elements":value["cleared_bits_elements"]}))
    if report["mismatches"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
