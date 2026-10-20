#!/usr/bin/env python3
"""CPU-only independent validation of completed same-script GPU lifecycle probes."""
import datetime
import hashlib
import json
import os
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "native_input_diagnosis"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8*1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def digest(t):
    return hashlib.sha256(t.detach().contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()


def main():
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == ""
    assert set(os.sched_getaffinity(0)) == {8,9}
    torch.set_num_threads(2)
    ds = {a:json.loads((BASE/a/"diagnosis.json").read_text()) for a in ["AT009","AT010"]}
    assert all(d["state"] == "complete" and d.get("lock_released_at") for d in ds.values()), "wait for completed raw evidence"
    report = {"schema":"scalellm_weight_lifecycle_independent_review_v1",
              "reviewed_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "reviewer":"A010 /root/gsm8k_protocol", "execution_state":"review_completed_AT009_AT010",
              "CPU_only":True,"cpu_affinity":sorted(os.sched_getaffinity(0)),
              "CUDA_VISIBLE_DEVICES":os.environ.get("CUDA_VISIBLE_DEVICES"),"cuda_initialized":torch.cuda.is_initialized(),
              "review_source":{"path":str(Path(__file__).resolve()),"sha256":sha(__file__)},
              "attempts":[],"mismatches":[],"snapshot_files_verified":0,"diff_artifacts_verified":0}
    def require(test, detail):
        if not test:
            report["mismatches"].append(detail)
    for attempt,d in ds.items():
        b=BASE/attempt
        a={"attempt":attempt,"diagnosis_path":str(b/"diagnosis.json"),"diagnosis_sha256":sha(b/"diagnosis.json"),
           "source_sha256":sha(b/"source_snapshot.py"),"gpu_uuid_actual":d["gpu_uuid_actual"],
           "cpu_affinity":d["cpu_affinity"],"runtime_flags":d["runtime_flags"],"snapshots":[]}
        require(a["source_sha256"]==d["source_sha256"],attempt+": source snapshot identity")
        expected_gpu="d87ce710-76bf-872d-9739-f0d7c9b52533" if attempt=="AT009" else "78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6"
        require(d["gpu_uuid_actual"].removeprefix("GPU-")==expected_gpu,attempt+": actual GPU")
        require(set(d["cpu_affinity"])==({18,19} if attempt=="AT009" else {16,17}),attempt+": CPU allocation")
        checkpoint_path=b/"checkpoint_weight.pt"
        require(sha(checkpoint_path)==d["checkpoint"]["saved_sha256"],attempt+": saved checkpoint artifact SHA")
        original=torch.load(checkpoint_path,map_location="cpu",weights_only=True,mmap=True)
        original_sha=digest(original)
        require(original_sha==d["checkpoint"]["tensor"]["sha256"]=="abf3fa9992765e359b6318b5cf94cc559184c37a1a5875b3e249e04f949ee38d",attempt+": checkpoint tensor SHA")
        previous=None
        cpu_ptrs=[]
        gpu_ptrs=[]
        labels=[]
        for row in d["snapshots"]:
            label=row["label"]
            labels.append(label)
            path=b/row["file"]["path"]
            require(sha(path)==row["file"]["sha256"],attempt+":"+label+": artifact SHA")
            values=torch.load(path,map_location="cpu",weights_only=True,mmap=True)
            require(digest(values)==row["cpu"]["sha256"],attempt+":"+label+": value SHA")
            require(list(values.shape)==row["cpu"]["shape"]==row["gpu"]["shape"]==[14336,4096],attempt+":"+label+": shape")
            require(str(values.dtype)==row["cpu"]["dtype"]==row["gpu"]["dtype"]=="torch.bfloat16",attempt+":"+label+": dtype")
            require(row["cpu"]["data_ptr"]!=d["checkpoint"]["tensor"]["data_ptr"],attempt+":"+label+": CPU not checkpoint alias")
            different=values.view(torch.int16)!=original.view(torch.int16)
            coords=different.nonzero()
            changed=int(len(coords));changed_bytes=int((values.view(torch.uint8)!=original.view(torch.uint8)).sum())
            require(changed==row["changed_elements"] and changed_bytes==row["changed_bytes"] and row["checkpoint_equal"]==(changed==0),attempt+":"+label+": differences")
            rec={"label":label,"group":row["group"],"raw_sha256":row["file"]["sha256"],"value_sha256":row["cpu"]["sha256"],
                 "changed_elements":changed,"changed_bytes":changed_bytes,"checkpoint_equal":changed==0,
                 "gpu_parameter_version":row["gpu"]["version"],"gpu_data_ptr":row["gpu"]["data_ptr"]}
            if row["group"]=="model_weight":
                if previous is not None:
                    previous_changes=int((values.view(torch.int16)!=previous.view(torch.int16)).sum())
                    require(previous_changes==row["changed_from_previous_elements"],attempt+":"+label+": previous snapshot delta")
                    rec["changed_from_previous_elements"]=previous_changes
                previous=values
                cpu_ptrs.append(row["cpu"]["data_ptr"])
                gpu_ptrs.append(row["gpu"]["data_ptr"])
            if changed:
                diffpath=b/row["diff_file"]["path"]
                require(sha(diffpath)==row["diff_file"]["sha256"],attempt+":"+label+": diff SHA")
                diff=torch.load(diffpath,map_location="cpu",weights_only=True)
                ow=original.view(torch.int16)[different].int().bitwise_and(65535)
                nw=values.view(torch.int16)[different].int().bitwise_and(65535)
                require(torch.equal(coords,diff["coordinates"]) and torch.equal(ow,diff["original_bf16_words"]) and torch.equal(nw,diff["observed_bf16_words"]),attempt+":"+label+": complete diff coordinates/words")
                maxabs=float((values[different].float()-original[different].float()).abs().max())
                require(maxabs==row["max_abs_difference"],attempt+":"+label+": maxabs")
                rec["high_byte_changes"]=int((ow.bitwise_and(65280)!=nw.bitwise_and(65280)).sum())
                rec["max_abs_difference"]=maxabs
                report["diff_artifacts_verified"]+=1
            a["snapshots"].append(rec)
            report["snapshot_files_verified"]+=1
        require(len(d["snapshots"])==17,attempt+": complete snapshot count")
        a["all_model_snapshot_parameter_versions_zero"]=all(r["gpu"]["version"]==0 for r in d["snapshots"] if r["group"]=="model_weight")
        a["model_gpu_pointer_unchanged"]=len(set(gpu_ptrs))==1
        # Snapshot CPU addresses may safely be reused after old independent clones are released.
        a["capture_alias_review"]="Every snapshot explicitly synchronizes the GPU, makes blocking CPU copy plus clone, writes a distinct tensor artifact immediately; CPU allocator address reuse after object release is permitted and does not alias saved values."
        a["inventory_scope"]="model, model.model, layer25, layer25.mlp, layer25.up_proj and global torch forward hooks; not an inventory of all submodules"
        inventory=d["pre_diagnostic_hook_inventory"]
        a["recorded_forward_hooks_empty"]=all(not v["forward_pre_hooks"] and not v["forward_hooks"] for v in inventory.values())
        a["recorded_modules_unparametrized"]=all(not v.get("is_parametrized",False) for v in inventory.values())
        a["native_inputs_outputs"]={}
        native={}
        for row in d["native_calls"]:
            name=row["key"];native[name]={}
            for field in ["input","output"]:
                meta=row[field];file=row[field+"_file"];path=b/file["path"]
                require(sha(path)==file["sha256"],attempt+":"+name+field+": raw artifact SHA")
                tensor=torch.load(path,map_location="cpu",weights_only=True,mmap=True)
                require(digest(tensor)==meta["sha256"],attempt+":"+name+field+": bytes SHA")
                require(list(tensor.shape)==meta["shape"] and str(tensor.dtype)==meta["dtype"],attempt+":"+name+field+": descriptor")
                native[name][field]=tensor
            logits=torch.load(b/(name+"_logits.pt"),map_location="cpu",weights_only=True,mmap=True)
            require(digest(logits)==row["logits_sha256"],attempt+":"+name+": logits SHA")
            require([int(logits.argmax(-1).item())]==row["generated_ids"],attempt+":"+name+": generated token")
            native[name]["logits"]=logits
        for field in ["input","output","logits"]:
            x,y=native["native_0"][field],native["native_1"][field]
            a["native_inputs_outputs"][field]={"exact":torch.equal(x,y),"finite":bool(torch.isfinite(x).all() and torch.isfinite(y).all()),"max_abs_difference":float((x.float()-y.float()).abs().max())}
        report["attempts"].append(a)
    require(ds["AT009"]["source_sha256"]==ds["AT010"]["source_sha256"],"same lifecycle source")
    require(ds["AT009"]["plan_sha256"]==ds["AT010"]["plan_sha256"] and ds["AT009"]["runtime_flags"]==ds["AT010"]["runtime_flags"] and ds["AT009"]["package_versions"]==ds["AT010"]["package_versions"],"same plan/flags/packages")
    report["verdict"]="GPU1 existing loaded parameter differs and changes even before forward; GPU0 same-script target lifecycle passes; supports provisional GPU1 exclusion but not hardware-root-cause or full-model/GSM8K qualification"
    report["limitations"]=["One parameter and one training prefill prompt only; GPU0 passing this target does not verify all model static tensors or all 30 cases.",
                            "Original parameter and separately allocated correct tensor differ in allocation/lifetime/loading context; good independent roundtrip does not identify which component caused original content changes.",
                            "GPU1 content change with parameter version0 proves versions alone are insufficient; it does not establish whether underlying bytes or device-to-host observation path caused the saved differences.",
                            "Only provisional operational quarantine is supported; no hardware repair or unbounded stress test is authorized by this review."]
    out=HERE/"determinism_review_AT005.json"
    with out.open("x") as stream:
        json.dump(report,stream,indent=2);stream.write("\n")
    print(json.dumps({"execution_state":report["execution_state"],"snapshot_files_verified":report["snapshot_files_verified"],"diff_artifacts_verified":report["diff_artifacts_verified"],"mismatches":report["mismatches"],"attempts":[{"attempt":a["attempt"],"loaded_first3":[r["changed_elements"] for r in a["snapshots"][:3]],"native":a["native_inputs_outputs"]} for a in report["attempts"]]}))
    if report["mismatches"]:raise SystemExit(1)


if __name__=="__main__":main()
