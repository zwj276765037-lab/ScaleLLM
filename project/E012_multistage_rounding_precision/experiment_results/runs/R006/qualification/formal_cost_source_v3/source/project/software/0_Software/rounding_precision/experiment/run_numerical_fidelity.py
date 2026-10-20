"""Document-level array replay and bounded CPU-only execution receipts (v3)."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def identity(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def available_memory():
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    return 0


def cpu_supervise(args, script, prefix, dependencies=()):
    """Only one owned CPU worker; GPU hidden, <=300s, sampled RSS <=8 GiB."""
    directory = args.output_dir.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    if not 1 <= args.wall_seconds <= 300:
        raise ValueError("v3 CPU preparation wall budget must be <=300 seconds")
    start_path = directory / f"{prefix}_manifest.json"
    sources = [identity(path) for path in dict.fromkeys([Path(script).resolve(), Path(__file__).resolve(), *dependencies])]
    command = [sys.executable, "-B", str(Path(script).resolve()), *sys.argv[1:], "--worker"]
    started = timestamp()
    write_json(start_path, {"schema": "m005_v3_cpu_manifest_v1", "started_at": started,
               "command": command, "code": sources, "python": sys.version,
               "threads": 1, "rss_limit_bytes": 8 << 30, "wall_seconds": args.wall_seconds,
               "scope": "CPU numerical preparation; no ACC/PPL/task noninferiority or GPU"})
    if available_memory() < 32 << 30:
        write_json(directory / f"{prefix}_receipt.json", {"execution_state": "blocked", "exit_code": 75,
                   "started_at": started, "ended_at": timestamp(), "reason": "RAM below32GiB"})
        return 75
    env = os.environ.copy()
    for key in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"]:
        env[key] = "1"
    env.update(CUDA_VISIBLE_DEVICES="", TOKENIZERS_PARALLELISM="false", PYTHONDONTWRITEBYTECODE="1")
    begin = time.monotonic()
    peak = 0
    stop = None
    with (directory / f"{prefix}_stdout.log").open("x") as stdout, \
         (directory / f"{prefix}_stderr.log").open("x") as stderr:
        process = subprocess.Popen(command, env=env, stdout=stdout, stderr=stderr, start_new_session=True)
        write_json(directory / f"{prefix}_launch.json", {"worker_pid": process.pid, "started_at": timestamp()})
        try:
            while process.poll() is None:
                try:
                    rss = next(int(line.split()[1]) * 1024 for line in Path(f"/proc/{process.pid}/status").read_text().splitlines() if line.startswith("VmRSS:"))
                except (OSError, StopIteration):
                    rss = 0
                peak = max(peak, rss)
                if rss > 8 << 30:
                    stop = "8GiB RSS budget"
                elif time.monotonic() - begin >= max(1, args.wall_seconds - 5):
                    stop = "CPU wall budget"
                if stop:
                    break
                time.sleep(.1)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
            native = process.wait()
    unchanged = sources == [identity(path) for path in dict.fromkeys([Path(script).resolve(), Path(__file__).resolve(), *dependencies])]
    code = 124 if stop else native
    if code == 0 and not unchanged:
        code, stop = 76, "consumed code changed"
    receipt = {"execution_state": "completed" if code == 0 else "failed", "exit_code": code,
               "native_exit_code": native, "started_at": started, "ended_at": timestamp(),
               "wall_seconds": time.monotonic() - begin, "max_observed_rss_bytes": peak,
               "worker_pid": process.pid, "worker_reaped": True, "source_unchanged": unchanged, "stop_reason": stop}
    write_json(directory / f"{prefix}_receipt.json", receipt)
    print(json.dumps(receipt))
    return code


def error_energy_metrics(error, reference, valid=None):
    """Floating display aggregates; validity and bound decisions come from oracle masks."""
    import numpy as np
    error, reference = np.asarray(error, dtype=np.float64), np.asarray(reference, dtype=np.float64)
    if error.shape != reference.shape:
        raise ValueError("paired tensors must have identical shape")
    mask = np.ones(error.shape, dtype=bool) if valid is None else np.broadcast_to(np.asarray(valid, dtype=bool), error.shape)
    finite = np.isfinite(error) & np.isfinite(reference)
    good = mask & finite
    error, reference = error[good], reference[good]
    count = int(good.sum())
    E, S = float(np.dot(error, error)), float(np.dot(reference, reference))
    signed_sum = float(error.sum())
    defined = count > 0 and S > 0
    return {"total_elements": int(good.size), "valid_elements": count,
            "excluded_elements": int(good.size - count), "nonfinite_elements": int((~finite).sum()),
            "error_energy": E, "signal_energy": S, "signed_error_sum": signed_sum,
            "relative_l2_percent": 100 * math.sqrt(E / S) if defined else None,
            "normalized_signed_bias_percent": 100 * signed_sum / math.sqrt(count * S) if defined else None,
            "signal_rms": math.sqrt(S / count) if count else None,
            "absolute_rmse": math.sqrt(E / count) if count else None,
            "absolute_max": float(np.max(np.abs(error))) if count else None,
            "zero_signal": count > 0 and S == 0, "empty_valid_domain": count == 0,
            "small_signal_threshold": None,
            "small_signal_status": "not_frozen; report signal_rms without pass threshold"}


def energy_metrics(current, reference, valid=None):
    import numpy as np
    current, reference = np.asarray(current, dtype=np.float64), np.asarray(reference, dtype=np.float64)
    if current.shape != reference.shape:
        raise ValueError("paired tensors must have identical shape")
    return error_energy_metrics(current - reference, reference, valid)


def node_metrics(result, strict=False):
    """Compute error before adding a small rational fraction to a large quotient."""
    import numpy as np
    exact = result["exact"]
    F = exact["fractional_bits"]
    if not isinstance(F, (int, np.integer)):
        raise TypeError("exact.fractional_bits must be scalar integer")
    scale = math.ldexp(1., -int(F))
    c = np.asarray(result["current_code"], dtype=np.float64)
    ref = np.asarray(result["reference_code"], dtype=np.float64)
    q, r, d = [np.broadcast_to(np.asarray(exact[key], dtype=np.float64), c.shape)
               for key in ("quotient_floor", "remainder", "denominator")]
    if np.any(d <= 0) or np.any(r < 0) or np.any(r >= d):
        raise ValueError("exact quotient/remainder must have positive denominator and 0<=r<d")
    fraction = r / d
    coordinate = result.get("metric_mask", result["valid_mask"])
    valid = np.asarray(coordinate,dtype=bool) & np.asarray(result.get("accepted_mask",result["valid_mask"]),dtype=bool)
    if strict:
        valid &= np.asarray(result["valid_mask"],dtype=bool)
    return {"current_vs_reference": error_energy_metrics((c-ref)*scale, ref*scale, valid),
            "current_vs_exact": error_energy_metrics(((c-q)-fraction)*scale, (q+fraction)*scale, valid)}


def mask_counts(result):
    import numpy as np
    shape = np.asarray(result["current_code"]).shape
    names = ("valid_mask", "metric_mask", "domain_valid_mask", "accepted_mask", "saturation_mask",
             "overflow_mask", "clip_mask", "software_padding_mask", "bound_applicable_mask",
             "bound_violation_mask", "reference_bound_violation_mask")
    counts = {key: int(np.broadcast_to(result[key], shape).sum()) for key in names if key in result}
    coordinate=np.broadcast_to(result.get("metric_mask",result.get("valid_mask",True)),shape)
    accepted=np.broadcast_to(result.get("accepted_mask",result.get("valid_mask",True)),shape)
    counts.update(accepted_metric_elements=int((coordinate & accepted).sum()),
                  strict_valid_metric_elements=int((coordinate & np.broadcast_to(result.get("valid_mask",True),shape)).sum()),
                  rejected_metric_elements=int((coordinate & ~accepted).sum()),
                  total_elements=int(np.prod(shape)),
                  bound_not_applicable_elements=int(np.prod(shape))-counts.get("bound_applicable_mask", 0))
    return counts


GROUP_FIELDS = ("doc_id", "layer", "node", "op", "trajectory", "domain", "split", "evidence_role")
CELL_FIELDS = GROUP_FIELDS[1:]


def summarize_documents(rows, bootstrap_replicates=2000, seed=2026101903):
    """Merge tensor partitions by document/site, then resample documents (never scalars)."""
    import numpy as np
    grouped = {}
    for row in rows:
        for series, metric in row["metrics"].items():
            key = tuple(row.get(field) for field in GROUP_FIELDS) + (series,)
            target = grouped.setdefault(key, {**{field: row.get(field) for field in GROUP_FIELDS}, "series": series,
                "error_energy": 0., "signal_energy": 0., "signed_error_sum": 0., "valid_elements": 0,
                "total_elements": 0, "absolute_max": None, "tensor_parts": 0})
            for name in ("error_energy", "signal_energy", "signed_error_sum", "valid_elements", "total_elements"):
                target[name] += metric[name]
            if metric["absolute_max"] is not None:
                target["absolute_max"] = max(target["absolute_max"] or 0., metric["absolute_max"])
            target["tensor_parts"] += 1
    result = []
    for value in grouped.values():
        n, E, S = value["valid_elements"], value["error_energy"], value["signal_energy"]
        value.update(relative_l2_percent=100*math.sqrt(E/S) if n and S else None,
                     normalized_signed_bias_percent=100*value["signed_error_sum"]/math.sqrt(n*S) if n and S else None,
                     signal_rms=math.sqrt(S/n) if n else None,
                     absolute_rmse=math.sqrt(E/n) if n else None,
                     zero_signal=n > 0 and S == 0, empty_valid_domain=n == 0)
        result.append(value)
    cells = {}
    for value in result:
        key = json.dumps([value.get(field) for field in CELL_FIELDS]+[value["series"]], separators=(",", ":"))
        cells.setdefault(key, []).append(value)
    summaries = []
    rng = np.random.default_rng(seed)
    for cell in cells.values():
        summary = {**{field: cell[0].get(field) for field in CELL_FIELDS}, "series": cell[0]["series"],
                   "document_count": len(cell), "zero_signal_documents": sum(v["zero_signal"] for v in cell),
                   "empty_valid_documents": sum(v["empty_valid_domain"] for v in cell),
                   "tail_warning": "P99 is descriptive; tail support is about 0.01*N documents"}
        for field in ("relative_l2_percent", "normalized_signed_bias_percent", "signal_rms", "absolute_rmse", "absolute_max"):
            values = np.asarray([v[field] for v in cell if v[field] is not None], dtype=np.float64)
            estimate = dict(zip(("p50", "p95", "p99"), map(float,np.quantile(values,[.5,.95,.99])))) if values.size else None
            summary[field] = {"defined_documents": int(values.size), "quantiles": estimate, "bootstrap95": None}
            # This is a reporting precision guard, not a scientific pass/fail threshold.
            if values.size >= 20 and bootstrap_replicates > 0:
                boot = np.empty((bootstrap_replicates,3), dtype=np.float64)
                for index in range(bootstrap_replicates):
                    boot[index] = np.quantile(values[rng.integers(values.size,size=values.size)],[.5,.95,.99])
                limits = np.quantile(boot,[.025,.975],axis=0)
                summary[field]["bootstrap95"] = {name:[float(limits[0,i]),float(limits[1,i])]
                                                   for i,name in enumerate(("p50","p95","p99"))}
        summaries.append(summary)
    total_masks = {}
    for row in rows:
        for key,value in row.get("counts", {}).items():
            total_masks[key] = total_masks.get(key,0)+value
    docs = sorted({row["doc_id"] for row in rows})
    formal = sorted({row["doc_id"] for row in rows if row.get("evidence_role") == "formal_eval"})
    return {"document_ids": docs, "document_count": len(docs), "formal_eval_document_count": len(formal),
            "tensor_count": len(rows), "document_metrics": result, "cells": summaries, "element_counts": total_masks,
            "confidence_intervals": {"method": "percentile bootstrap of document metrics within each layer/node/op/domain/trajectory/split cell",
                "replicates": bootstrap_replicates, "seed": seed, "minimum_defined_documents":20,
                "limitations":"descriptive conditional on frozen source sample; no population independence certification; no scalar inference"}}



EXACT_DEFINITIONS = {
    "linear":"unrounded ScaleCode sum before output-format saturation",
    "rope":"unrounded pair-product sum/difference before S24 saturation",
    "qk":"exact scaled dot after intentional algorithmic score clip; unclipped value is diagnostic only",
    "softmax":"exact same-LUT interpolation and normalization before U16 common round/cap",
    "pv":"exact weighted sum before S24 saturation",
    "swiglu":"same-LUT and branch product before common output rounding",
    "host":"input fixed-point raw value before host FP32 conversion",
    "host_fp32":"input fixed-point raw value before host FP32 conversion",
}


def json_metadata(value):
    """Small JSON metadata; diagnostic vectors stay in NPZ, not scalar JSON."""
    import numpy as np
    if isinstance(value, np.ndarray):
        return {"array_shape":list(value.shape),"dtype":str(value.dtype),
                "sum":int(value.sum()) if value.dtype.kind in "iub" else float(value.sum()),
                "nonzero_elements":int(np.count_nonzero(value)),
                "maximum":value.max().item() if value.size else None}
    if isinstance(value, np.generic):return value.item()
    if isinstance(value, dict):return {key:json_metadata(item) for key,item in value.items()}
    if isinstance(value, (list,tuple)):return [json_metadata(item) for item in value]
    return value


def replay_worker(args):
    import numpy as np
    from numerical_reference.policy import evaluate_node
    source = json.loads(args.input_manifest.read_text())
    write_json(args.output_dir / "consumed_input_manifest.json", identity(args.input_manifest))
    output = args.output_dir / "arrays"
    output.mkdir()
    rows = []
    with (args.output_dir / "tensor_metrics.jsonl").open("x", encoding="utf-8") as stream:
        for index, case in enumerate(source["cases"]):
            path = Path(case["input_npz"])
            if identity(path)["sha256"] != case["sha256"]:
                raise ValueError("input artifact SHA mismatch")
            with np.load(path, allow_pickle=False) as archive:
                arrays = {key: archive[key] for key in archive.files}
            result = evaluate_node(case["node"], arrays, case["config"])
            current, reference = result["current_code"], result["reference_code"]
            metrics = node_metrics(result)
            strict_metrics = node_metrics(result, strict=True)
            saved = {"current_code": current, "reference_code": reference,
                     **{"exact_" + key: np.asarray(value) for key, value in result["exact"].items()}}
            for key, value in result.items():
                if isinstance(value, np.ndarray) and key not in saved:
                    saved[key] = value
            for key,value in result.get("current_error_counts",{}).items():
                if isinstance(value,np.ndarray):saved["current_error_counts_"+key]=value
            target = output / f"tensor_{index:06d}.npz"
            with target.open("xb") as handle:
                np.savez_compressed(handle, **saved)
            row = {**{key: case.get(key) for key in GROUP_FIELDS},
                   "source_id":case.get("source_id"), "text_sha256":case.get("text_sha256"),
                   "duplicate_cluster":case.get("duplicate_cluster"), "target_format":case.get("target_format"),
                   "production_source_hash":case.get("production_source_hash"),
                   "output_selection":case.get("output_selection"), "input_artifact": identity(path),
                   "output_artifact":identity(target), "output_shape": list(current.shape),
                   "logical_output_shape":case.get("output_shape"), "metrics": metrics,
                   "strict_metrics":strict_metrics, "primary_denominator":"metric_mask intersect accepted_mask; clips/wraps retained when production defines output",
                   "exact_definition":EXACT_DEFINITIONS.get(case["node"],"see node contract"),
                   "counts":mask_counts(result), "node_metadata":json_metadata(result.get("metadata", {})),
                   "current_error_counts":json_metadata(result.get("current_error_counts", {}))}
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            rows.append(row)
    write_json(args.output_dir / "document_summary.json", summarize_documents(rows))
    write_json(args.output_dir / "strict_valid_document_summary.json",
               summarize_documents([{**row,"metrics":row["strict_metrics"]} for row in rows]))
    write_json(args.output_dir / "output_inventory.json", {"files":[identity(path) for path in sorted(output.glob("*.npz"))],
               "tensor_metrics":identity(args.output_dir/"tensor_metrics.jsonl"),
               "document_summary":identity(args.output_dir/"document_summary.json")})
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--wall-seconds", type=int, default=300)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    try:
        if args.worker:
            code = replay_worker(args)
        else:
            here = Path(__file__).parent
            software = here.parents[2]
            deps = [here/"numerical_reference"/name for name in ["policy.py","current_nodes.py","exact_reductions.py"]]
            deps += [here/"production_replay.py",software/"0_Software/FPtoQ/experiment/v5_fullchain.py",
                     software/"model/export_scalellm_llama31_artifacts.py",software/"model/fixbit_v2.py"]
            code = cpu_supervise(args, __file__, "numerical", deps)
    except Exception:
        traceback.print_exc()
        code = 1
    raise SystemExit(code)


if __name__ == "__main__":
    main()
