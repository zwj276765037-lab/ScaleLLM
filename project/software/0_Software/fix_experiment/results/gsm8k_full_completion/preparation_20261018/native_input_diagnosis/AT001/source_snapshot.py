#!/usr/bin/env python3
"""Isolated train-only inspection of cold/warm native generation call inputs.

This diagnostic never modifies frozen worker/model code or generation settings.
It owns one GPU resource lock and a new output directory for each process.
"""
from __future__ import annotations
import argparse
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback

from gsm8k_protocol import atomic_json, prepare_requests, sha256_file
from run_gsm8k_worker import cache_tensors, encode_prompt, logits_comparison, now, resolve_generation


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--first", choices=("native", "manual"), default="native")
    p.add_argument("--prompt-index", choices=(0, 1), type=int, default=0)
    args = p.parse_args()
    args.device, args.case = "cuda:0", "bf16"
    args.output.mkdir(parents=True, exist_ok=False)
    state = {"schema": "scalellm_native_input_diagnosis_v1", "state": "starting", "started_at": now(),
        "pid": os.getpid(), "command": sys.argv, "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "gpu_uuid_requested": os.environ.get("CUDA_VISIBLE_DEVICES"), "first": args.first,
        "plan_sha256": sha256_file(args.plan), "source_sha256": sha256_file(Path(__file__).resolve()),
        "model": str(args.model), "records": [], "scope": "train diagnostic only; no formal accuracy qualification"}
    def save():
        atomic_json(args.output / "diagnosis.json", state)
    save()
    lock = None
    try:
        if set(os.sched_getaffinity(0)) != {18, 19}:
            raise ValueError("diagnostic allocation requires exactly CPU 18,19")
        gpu = os.environ.get("CUDA_VISIBLE_DEVICES")
        if gpu != "GPU-d87ce710-76bf-872d-9739-f0d7c9b52533":
            raise ValueError("diagnostic allocation is exclusively the assigned GPU1 UUID")
        available = next(int(line.split()[1]) for line in Path("/proc/meminfo").read_text().splitlines()
                         if line.startswith("MemAvailable:"))
        if available < 80*1024*1024:
            raise RuntimeError("host MemAvailable is below the preserved 80 GiB reserve")
        lock_path = Path(__file__).resolve().parent.parent / "results/gsm8k_full_completion/resource_locks" / (gpu+".lock")
        lock = lock_path.open("a+")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state.update(state="loading_model", lock=str(lock_path), lock_acquired_at=now())
        save()
        import torch
        from run_eval_worker import configure_reproducibility, load_model, package_versions
        torch.set_num_threads(2)
        torch.set_num_interop_threads(2)
        configure_reproducibility(20260913)
        torch.cuda.set_device(args.device)
        free, total = torch.cuda.mem_get_info(args.device)
        if free < 24*(1 << 30):
            raise RuntimeError("assigned GPU has less than 24 GiB free before model load")
        state.update(gpu_uuid_actual=str(torch.cuda.get_device_properties(args.device).uuid),
            gpu_memory_before={"free": free, "total": total}, package_versions=package_versions(),
            runtime_flags={"tf32": torch.backends.cuda.matmul.allow_tf32,
                           "bf16_reduced_precision": torch.backends.cuda.matmul.allow_bf16_reduced_precision_reduction})
        loaded_at = time.perf_counter()
        model, tokenizer, method, audit = load_model(args)
        model.config.use_cache = True
        model.eval()
        state.update(state="diagnosing", load_seconds=time.perf_counter()-loaded_at, method=method,
                     numeric_backend="BF16 native eager; frozen configure_reproducibility defaults")
        config, generation = resolve_generation(model, tokenizer, 17)
        config.output_logits = True
        state["generation"] = generation

        def digest(tensor):
            return hashlib.sha256(tensor.detach().contiguous().cpu().view(torch.uint8).numpy().tobytes()).hexdigest()
        def tensor_info(tensor):
            return {"shape": list(tensor.shape), "dtype": str(tensor.dtype), "stride": list(tensor.stride()),
                    "contiguous": tensor.is_contiguous(), "device": str(tensor.device), "sha256": digest(tensor)}
        def metadata(kwargs):
            result = {}
            for key, value in kwargs.items():
                if isinstance(value, torch.Tensor):
                    result[key] = tensor_info(value)
                elif key == "past_key_values":
                    result[key] = {"class": type(value).__module__+"."+type(value).__name__,
                        "sequence_length": int(value.get_seq_length()) if value is not None else None,
                        "layer_shapes": [[list(k.shape) if k is not None else None,
                                          list(v.shape) if v is not None else None] for k,v in cache_tensors(value)]}
                else:
                    result[key] = value if isinstance(value, (str, int, bool, float, type(None))) else repr(value)
            return result
        def model_state():
            return {"buffers": {name: tensor_info(value) for name, value in model.named_buffers()},
                    "parameter_versions": {name: value._version for name, value in model.named_parameters()},
                    "training": model.training, "use_cache": model.config.use_cache,
                    "attention_implementation": getattr(model.config,"_attn_implementation",None)}
        requests = prepare_requests(args.plan,"smoke")
        order = [args.prompt_index, 1-args.prompt_index]
        for prompt_index in order:
            request = requests[prompt_index]
            inputs = torch.tensor([encode_prompt(tokenizer, request["prompt"])],device=args.device)
            attention = torch.ones_like(inputs)
            row = {"sample_id": request["sample_id"], "prompt_sha256": request["prompt_sha256"],
                   "input_tokens": inputs.shape[1], "before": model_state(), "native_inputs": [], "comparisons": {}}
            state["records"].append(row)
            captured = []
            active = [False]
            def capture(_module, positional, kwargs):
                if active[0] and len(captured) == 0:
                    # Capture only the first prefill. It has an empty cache, so
                    # this does not retain or clone any populated K/V tensors.
                    captured.append(copy.deepcopy(kwargs))
                    row["native_inputs"].append(metadata(kwargs))
            hook = model.register_forward_pre_hook(capture, with_kwargs=True)
            def native():
                configure_reproducibility(20260913)
                active[0] = not captured
                out = model.generate(input_ids=inputs,attention_mask=attention,generation_config=copy.deepcopy(config))
                active[0] = False
                return out
            def manual():
                return model(input_ids=inputs,attention_mask=attention,past_key_values=None,use_cache=True,logits_to_keep=1)
            with torch.inference_mode():
                cold_manual = manual() if args.first == "manual" and prompt_index == order[0] else None
                first = native()
                row["after_native_first"] = model_state()
                second = native()
                row["after_native_second"] = model_state()
                warm_manual = manual()
                replay = model(**copy.deepcopy(captured[0]))
                explicit_position = model(input_ids=inputs,attention_mask=attention,past_key_values=None,
                    position_ids=attention.cumsum(-1)-1,use_cache=True,logits_to_keep=1)
                last_first, last_second = first.logits[0],second.logits[0]
                comparisons = row["comparisons"]
                comparisons["first_native_vs_second_native"] = [logits_comparison(a,b) for a,b in zip(first.logits,second.logits)]
                comparisons["first_native_vs_warm_manual_prefill"] = logits_comparison(last_first,warm_manual.logits[:,-1])
                comparisons["second_native_vs_warm_manual_prefill"] = logits_comparison(last_second,warm_manual.logits[:,-1])
                comparisons["first_native_vs_exact_kwargs_replay"] = logits_comparison(last_first,replay.logits[:,-1])
                comparisons["second_native_vs_exact_kwargs_replay"] = logits_comparison(last_second,replay.logits[:,-1])
                comparisons["warm_manual_vs_exact_kwargs_replay"] = logits_comparison(warm_manual.logits[:,-1],replay.logits[:,-1])
                comparisons["warm_manual_vs_explicit_position"] = logits_comparison(warm_manual.logits[:,-1],explicit_position.logits[:,-1])
                if cold_manual is not None:
                    comparisons["cold_manual_vs_warm_manual"] = logits_comparison(cold_manual.logits[:,-1],warm_manual.logits[:,-1])
                row["native_generated_ids_first"] = first.sequences[0,inputs.shape[1]:].tolist()
                row["native_generated_ids_second"] = second.sequences[0,inputs.shape[1]:].tolist()
                row["after_all"] = model_state()
                raw = {"native_first_logits": tuple(value.cpu() for value in first.logits),
                       "native_second_logits": tuple(value.cpu() for value in second.logits),
                       "warm_manual_logits": warm_manual.logits[:,-1].cpu(), "exact_kwargs_replay_logits": replay.logits[:,-1].cpu(),
                       "explicit_position_logits": explicit_position.logits[:,-1].cpu(),
                       "cold_manual_logits": cold_manual.logits[:,-1].cpu() if cold_manual is not None else None}
                artifact = args.output / f"{request['sample_id'].replace(':','_')}_raw_logits.pt"
                torch.save(raw,artifact)
                row["raw_logits"] = {"path": str(artifact), "sha256": sha256_file(artifact)}
            hook.remove()
            save()
            print(json.dumps({"event":"prompt_complete","sample_id":row["sample_id"],
                "first_vs_second_prefill":row["comparisons"]["first_native_vs_second_native"][0],
                "second_vs_manual":row["comparisons"]["second_native_vs_warm_manual_prefill"]}),flush=True)
        state.update(state="complete",finished_at=now(),peak_memory_allocated_bytes=torch.cuda.max_memory_allocated(args.device))
        save()
    except BaseException as exc:
        state.update(state="failed",finished_at=now(),error={"type":type(exc).__name__,"message":str(exc),"traceback":traceback.format_exc()})
        save()
        raise
    finally:
        if lock is not None:
            lock.close()


if __name__ == "__main__":
    main()
