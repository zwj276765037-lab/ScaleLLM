"""Small synthetic tensors only; CUDA requires explicit exclusive GPU0 slot."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import sys
import time

import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[4] / "exp"))
import gsm8k_weight_integrity as legacy
from gsm8k_integrity_bytewise import ImmutableTensorSnapshot, METHOD_ID


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="cpu", choices=("cpu", "cuda:0"))
    parser.add_argument("--mib", type=int, default=64)
    parser.add_argument("--chunk-mib", type=int, default=16)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--exclusive-gpu0-slot", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.mib < 1 or args.mib > 512 or args.chunk_mib < 1 or args.chunk_mib > 64 or args.repeats < 1:
        parser.error("bounded benchmark requires 1..512 MiB tensor, 1..64 MiB chunk and positive repeats")
    if args.output.exists():
        parser.error("output exists; use a new attempt path")
    if args.device == "cuda:0" and (not args.exclusive_gpu0_slot or os.environ.get("CUDA_VISIBLE_DEVICES") != "0"):
        parser.error("CUDA requires an actually exclusive GPU0 slot, CUDA_VISIBLE_DEVICES=0, and --exclusive-gpu0-slot")
    if args.device == "cpu" and os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        parser.error("CPU benchmark requires CUDA_VISIBLE_DEVICES='' ")
    torch.set_num_threads(2)
    size, chunk = args.mib * 2**20 + 37, args.chunk_mib * 2**20
    started = time.time()
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    tensor = torch.arange(size, dtype=torch.uint8, device=args.device)
    if args.device == "cuda:0":
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
    tensors, roles = {"synthetic.weight": tensor}, {"synthetic.weight": "parameter"}
    trusted = {"synthetic.weight": legacy.tensor_descriptor(tensor, "parameter")}
    begin = time.perf_counter()
    snap = ImmutableTensorSnapshot(tensors, trusted, roles=roles, chunk_bytes=chunk)
    capture_seconds = time.perf_counter() - begin
    timings = {"legacy_tensor_descriptor_seconds": [], "candidate_compare_seconds": []}
    # Untimed warmups avoid counting Python/allocator cold paths as steady state.
    assert legacy.tensor_descriptor(tensor, "parameter") == trusted["synthetic.weight"]
    assert snap.compare(tensors, roles=roles)[2]["full_coverage_exact"]
    for _ in range(args.repeats):
        begin = time.perf_counter()
        assert legacy.tensor_descriptor(tensor, "parameter") == trusted["synthetic.weight"]
        timings["legacy_tensor_descriptor_seconds"].append(time.perf_counter() - begin)
        begin = time.perf_counter()
        observed, errors, evidence = snap.compare(tensors, roles=roles)
        timings["candidate_compare_seconds"].append(time.perf_counter() - begin)
        assert not errors and observed == trusted and evidence["full_coverage_exact"]
        assert evidence["compared_bytes"] == size == evidence["equal_bytes"]
    corruptions = []
    for offset in sorted({0, chunk-1, chunk, size-1}):
        tensor[offset].bitwise_xor_(1)
        observed, errors, evidence = snap.compare(tensors, roles=roles)
        old_rejects = legacy.tensor_descriptor(tensor, "parameter") != trusted["synthetic.weight"]
        assert old_rejects and not evidence["full_coverage_exact"] and observed != trusted
        corruptions.append({"offset": offset, "bit": 0, "legacy_rejects": old_rejects,
                            "candidate_rejects": True, "compared_bytes": evidence["compared_bytes"]})
        tensor[offset].bitwise_xor_(1)
    assert snap.compare(tensors, roles=roles)[2]["full_coverage_exact"]
    medians = {key: statistics.median(value) for key, value in timings.items()}
    result = {"schema": "integrity_bytewise_synthetic_benchmark_v1", "state": "complete", "method_id": METHOD_ID,
        "device": args.device, "tensor_bytes": size, "tensor_count": 1, "repeats": args.repeats,
        "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__), HERE / "gsm8k_integrity_bytewise.py", Path(legacy.__file__))},
        "environment": {"python": sys.version, "torch": torch.__version__, "platform": platform.platform(),
                        "cpu_affinity": sorted(os.sched_getaffinity(0)), "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
                        "cuda_initialized": torch.cuda.is_initialized(), "torch_threads": torch.get_num_threads()},
        "capture_seconds": capture_seconds, "timings": timings, "median_seconds": medians,
        "measured_median_speedup_this_synthetic_case": medians["legacy_tensor_descriptor_seconds"] / medians["candidate_compare_seconds"],
        "capture": snap.capture_evidence, "positive_last_phase": evidence, "corruption_controls": corruptions,
        "memory": {"ru_maxrss_bytes_before": rss_before, "ru_maxrss_bytes_after": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                   "logical_baseline_bytes": snap.expected_bytes, "unique_immutable_baseline_bytes": snap.unique_baseline_bytes,
                   "staging_buffer_bytes": chunk, "gpu_weight_replica_bytes": 0},
        "started_epoch": started, "finished_epoch": time.time(),
        "applicability": "synthetic tensor only; no model inference or full-model throughput measurement"}
    # Report the final positive phase, not the last intentional corruption.
    result["positive_last_phase"] = snap.compare(tensors, roles=roles)[2]
    if args.device == "cuda:0":
        result["environment"]["gpu_name"] = torch.cuda.get_device_name(0)
        result["memory"].update(cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated(0),
                                 cuda_peak_reserved_bytes=torch.cuda.max_memory_reserved(0))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({"output": str(args.output), "device": args.device, "bytes": size,
                      "median_seconds": medians, "speedup_measured_synthetic_only": result["measured_median_speedup_this_synthetic_case"],
                      "cuda_initialized": torch.cuda.is_initialized()}))


if __name__ == "__main__":
    main()
