"""Bounded synthetic benchmark; external GPU0 resource owner controls launch."""
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
import uuid

import torch

HERE = Path(__file__).resolve().parent
import gsm8k_weight_integrity as legacy
from gsm8k_integrity_bytewise import ImmutableTensorSnapshot, METHOD_ID, audit_capture_memory


def canonical_gpu_uuid(value):
    if not isinstance(value, str):
        raise ValueError("a full GPU UUID is required")
    return "GPU-" + str(uuid.UUID(value.lower().removeprefix("gpu-")))


def validate_cuda_identity(expected_uuid, visible_uuid, actual_uuid=None):
    expected = canonical_gpu_uuid(expected_uuid)
    if canonical_gpu_uuid(visible_uuid) != expected:
        raise ValueError("CUDA_VISIBLE_DEVICES must be the complete target GPU0 UUID")
    if actual_uuid is not None and canonical_gpu_uuid(str(actual_uuid)) != expected:
        raise ValueError("Torch actual device UUID differs from target GPU0 UUID")
    return expected


def parse_benchmark_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="cpu", choices=("cpu", "cuda:0"))
    parser.add_argument("--mib", type=int, default=64)
    parser.add_argument("--chunk-mib", type=int, default=16)
    parser.add_argument("--repeats", type=int, default=5)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--exclusive-gpu0-slot", action="store_true",
                      help="External runner must actually hold the original lock and pass resource guards; flag alone proves no exclusivity.")
    mode.add_argument("--diagnostic-shared-gpu0", action="store_true",
                      help="Bounded synthetic diagnostic only; no exclusive/model/ACC qualification.")
    parser.add_argument("--gpu-uuid", help="Complete physical GPU0 UUID, required for either CUDA mode.")
    parser.add_argument("--external-guard-evidence", type=Path,
                        help="Optional external runner resource/lock evidence artifact, recorded by path and SHA.")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.mib < 1 or args.mib > 512 or args.chunk_mib < 1 or args.chunk_mib > 64 or args.repeats < 1:
        parser.error("bounded benchmark requires 1..512 MiB tensor, 1..64 MiB chunk and positive repeats")
    if args.output.exists():
        parser.error("output exists; use a new attempt path")
    if args.device == "cuda:0":
        if not args.exclusive_gpu0_slot and not args.diagnostic_shared_gpu0:
            parser.error("CUDA requires an explicitly selected exclusive or shared diagnostic mode")
        try:
            validate_cuda_identity(args.gpu_uuid, os.environ.get("CUDA_VISIBLE_DEVICES"))
        except (ValueError, AttributeError) as error:
            parser.error(str(error))
        if args.diagnostic_shared_gpu0 and (args.mib > 64 or args.chunk_mib != 16 or not 3 <= args.repeats <= 5):
            parser.error("shared diagnostic requires <=64MiB+37 bytes, 16MiB chunk and 3..5 repeats")
    if args.device == "cpu" and os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        parser.error("CPU benchmark requires CUDA_VISIBLE_DEVICES='' ")
    if args.device == "cpu" and (args.exclusive_gpu0_slot or args.diagnostic_shared_gpu0 or args.gpu_uuid):
        parser.error("GPU allocation flags cannot be used with CPU mode")
    if args.external_guard_evidence is not None and not args.external_guard_evidence.is_file():
        parser.error("external guard evidence file does not exist")
    return args


def main():
    args = parse_benchmark_args()
    torch.set_num_threads(2)
    size, chunk = args.mib * 2**20 + 37, args.chunk_mib * 2**20
    started = time.time()
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    actual_gpu_uuid = None
    if args.device == "cuda:0":
        props = torch.cuda.get_device_properties(0)
        actual_gpu_uuid = validate_cuda_identity(args.gpu_uuid, os.environ.get("CUDA_VISIBLE_DEVICES"), props.uuid)
        torch.cuda.reset_peak_memory_stats()
    tensor = torch.arange(size, dtype=torch.uint8, device=args.device)
    if args.device == "cuda:0":
        torch.cuda.synchronize()
    tensors, roles = {"synthetic.weight": tensor}, {"synthetic.weight": "parameter"}
    trusted = {"synthetic.weight": legacy.tensor_descriptor(tensor, "parameter")}
    resource_guard = audit_capture_memory(tensors, chunk)
    if not resource_guard["passed"]:
        raise RuntimeError("immutable capture would violate host reserve 80GiB")
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
        "gpu_uuid": actual_gpu_uuid,
        "actual_gpu_uuid": actual_gpu_uuid,
        "shared_diagnostic_only": bool(args.diagnostic_shared_gpu0),
        "exclusive_verified": False,
        "model_or_ACC_qualified": False,
        "allocation_mode": "shared_gpu0_diagnostic" if args.diagnostic_shared_gpu0 else "exclusive_gpu0_external_guard_required" if args.device == "cuda:0" else "cpu_only",
        "exclusive_qualification_proven_by_cli_flag": False,
        "qualification_scope": "synthetic_shared_diagnostic_not_exclusive_model_or_ACC_qualification" if args.diagnostic_shared_gpu0 else "synthetic_tensor_only_not_model_or_ACC_qualification",
        "external_guard_evidence": ({"path": str(args.external_guard_evidence.resolve()),
                                     "sha256": hashlib.sha256(args.external_guard_evidence.read_bytes()).hexdigest()}
                                    if args.external_guard_evidence is not None else None),
        "immutable_capture_resource_guard": resource_guard,
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
                                 cuda_peak_reserved_bytes=torch.cuda.max_memory_reserved(0),
                                 peak_memory_allocated_bytes=torch.cuda.max_memory_allocated(0))
        if args.diagnostic_shared_gpu0:
            result["memory"]["shared_diagnostic_owned_allocation_limit_bytes"] = 1 << 30
            if result["memory"]["cuda_peak_allocated_bytes"] > (1 << 30):
                raise RuntimeError("shared synthetic diagnostic exceeded 1GiB owned CUDA allocation")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({"output": str(args.output), "device": args.device, "bytes": size,
                      "median_seconds": medians, "speedup_measured_synthetic_only": result["measured_median_speedup_this_synthetic_case"],
                      "cuda_initialized": torch.cuda.is_initialized()}))


if __name__ == "__main__":
    main()
