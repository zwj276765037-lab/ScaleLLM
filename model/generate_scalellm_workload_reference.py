#!/usr/bin/env python3
"""Generate the frozen ScaleLLM algorithmic NLL reference on one GPU."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Sequence


os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

SCRIPT_PATH = Path(__file__).resolve()
HAP_ROOT = SCRIPT_PATH.parents[1]
PROJECT_ROOT_CANDIDATES = (
    HAP_ROOT,
    HAP_ROOT.parent / "fpga_llm_project",
    *HAP_ROOT.parents,
)
PROJECT_ROOT = next(
    root
    for root in PROJECT_ROOT_CANDIDATES
    if (root / "scripts" / "accuracy_MLP_4bit").is_dir()
)
FIXEDPOINT_DIR = (
    PROJECT_ROOT / "scripts" / "accuracy_MLP_4bit" / "scala_code_accuracy"
)
SCALE_CODE_DIR = PROJECT_ROOT / "scripts" / "scale_code_linear"
for import_root in (HAP_ROOT, FIXEDPOINT_DIR, SCALE_CODE_DIR):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from fixedpoint_ops import config_from_variant
from mlp4_fixedpoint_inference import attach_fixedpoint_mlp_nonlinear
from model.freeze_scalellm_workload import (
    MODEL_ID,
    build_samples,
    file_record,
    sha256_file,
    write_workload_manifest,
)


SOFTWARE_ID = "scalellm-hadamard-scalecode-a8w8-a8w4-fxp16q5p10-v1"
EXPECTED_LINEAR_COUNTS = {
    "q_proj": 32,
    "k_proj": 32,
    "v_proj": 32,
    "o_proj": 32,
    "gate_proj": 32,
    "up_proj": 32,
    "down_proj": 32,
}


def _write_json_atomic(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + ".partial")
    temporary.write_text(
        json.dumps(
            value, indent=2, sort_keys=True, allow_nan=False,
            ensure_ascii=True,
        ) + "\n",
        encoding="ascii",
    )
    temporary.replace(path)


def _dtype(name: str) -> torch.dtype:
    return {
        "bfloat16": torch.bfloat16,
        "float16": torch.float16,
        "float32": torch.float32,
    }[name]


def _load_artifact_identity(path: Path) -> tuple[str, str, int]:
    resolved = path.resolve(strict=True)
    try:
        raw = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot parse artifact manifest {resolved}: {exc}") \
            from exc
    if (not isinstance(raw, dict) or raw.get("model_id") != MODEL_ID or
            raw.get("layer_count") != 32):
        raise ValueError("artifact manifest is not the 32-layer Llama-3.1-8B set")
    checkpoint_sha = raw.get("checkpoint_sha256")
    if (not isinstance(checkpoint_sha, str) or len(checkpoint_sha) != 64 or
            any(character not in "0123456789abcdef"
                for character in checkpoint_sha)):
        raise ValueError("artifact manifest checkpoint SHA256 is invalid")
    return checkpoint_sha, sha256_file(resolved), resolved.stat().st_size


def _source_records() -> list[dict]:
    files = (
        SCRIPT_PATH,
        HAP_ROOT / "model" / "freeze_scalellm_workload.py",
        FIXEDPOINT_DIR / "fixedpoint_ops.py",
        FIXEDPOINT_DIR / "mlp4_fixedpoint_inference.py",
        PROJECT_ROOT / "scripts" / "accuracy_MLP_4bit"
        / "mlp4_method_inference.py",
        SCALE_CODE_DIR / "scalepath4_method_inference.py",
    )
    return [file_record(path) for path in files]


def _validate_method_contract(method) -> None:
    linear = method.linear_summary
    expected_weight_bits = {
        op: 8 if op in {"q_proj", "k_proj", "v_proj", "o_proj"} else 4
        for op in EXPECTED_LINEAR_COUNTS
    }
    if method.module_count != 32 or len(set(method.nonlinear_modules)) != 32:
        raise RuntimeError(
            "quantized reference did not wrap exactly 32 SwiGLU MLP modules"
        )
    if sum(method.per_arch.values()) != 32:
        raise RuntimeError("quantized reference MLP architecture count drifted")
    if linear.get("module_count") != 224:
        raise RuntimeError("quantized reference did not replace 224 linear modules")
    if linear.get("per_op") != EXPECTED_LINEAR_COUNTS:
        raise RuntimeError(
            f"quantized reference linear coverage drifted: {linear.get('per_op')}"
        )
    if linear.get("per_op_weight_bits") != expected_weight_bits:
        raise RuntimeError("quantized reference A8W8/A8W4 weight contract drifted")
    exact = {
        "hadamard_block": 32,
        "group_size": 32,
        "act_bits": 8,
        "attention_weight_bits": 8,
        "mlp_weight_bits": 4,
        "scale_code_bits": 8,
    }
    for name, expected in exact.items():
        if linear.get(name) != expected:
            raise RuntimeError(
                f"quantized reference {name} drifted: "
                f"expected={expected} actual={linear.get(name)}"
            )


def _evaluate(
    model, samples: list[dict], device: torch.device, batch_size: int,
) -> tuple[list[dict], float]:
    records = []
    nll_sum = 0.0
    row_count = 0
    with torch.inference_mode():
        for start in range(0, len(samples), batch_size):
            batch = samples[start:start + batch_size]
            input_ids = torch.tensor(
                [item["input_token_ids"] for item in batch],
                dtype=torch.long, device=device,
            )
            target_ids = torch.tensor(
                [item["target_token_ids"] for item in batch],
                dtype=torch.long, device=device,
            )
            logits = model(
                input_ids=input_ids,
                attention_mask=torch.ones_like(input_ids),
                use_cache=False,
            ).logits.to(torch.float32)
            if logits.shape[:2] != input_ids.shape or logits.shape[2] != 128_256:
                raise RuntimeError(f"unexpected reference logits shape: {logits.shape}")
            target_logits = torch.gather(
                logits, 2, target_ids.unsqueeze(-1)
            ).squeeze(-1)
            nll = torch.logsumexp(logits, dim=-1) - target_logits
            top_values, top_ids = torch.topk(
                logits, k=5, dim=-1, largest=True, sorted=True
            )
            for index, sample in enumerate(batch):
                sample_nll = nll[index].detach().cpu().to(torch.float64)
                records.append({
                    "sample_id": sample["sample_id"],
                    "input_token_ids": sample["input_token_ids"],
                    "target_token_ids": sample["target_token_ids"],
                    "nll_sum": float(sample_nll.sum().item()),
                    "mean_nll": float(sample_nll.mean().item()),
                    "per_row_nll": sample_nll.tolist(),
                    "target_logits": target_logits[index].detach().cpu()
                    .to(torch.float64).tolist(),
                    "top_token_ids": top_ids[index].detach().cpu().tolist(),
                    "top_logits": top_values[index].detach().cpu()
                    .to(torch.float64).tolist(),
                })
            nll_sum += float(nll.detach().to(torch.float64).sum().item())
            row_count += int(nll.numel())
            print(
                f"reference_progress={min(start + len(batch), len(samples))}"
                f"/{len(samples)} mean_nll={nll_sum / row_count:.9f}",
                flush=True,
            )
    if row_count != len(samples) * 16:
        raise RuntimeError("reference row count drifted")
    mean_nll = nll_sum / row_count
    if not math.isfinite(mean_nll) or mean_nll < 0:
        raise RuntimeError(f"invalid reference mean NLL: {mean_nll}")
    return records, mean_nll


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate the frozen ScaleLLM V5 software reference"
    )
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--text-field", default="text")
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--artifact-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample-count", type=int, default=32)
    parser.add_argument("--seed", type=int, default=20260904)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument(
        "--dtype", choices=("bfloat16", "float16", "float32"),
        default="bfloat16",
    )
    parser.add_argument("--fixedpoint-variant", default="FXP16-Q5.10")
    parser.add_argument("--absolute-tolerance", type=float, default=0.1)
    parser.add_argument("--cpu-threads", type=int, default=4)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.sample_count < 2 or args.sample_count % 2:
        raise SystemExit("--sample-count must be even and at least 2")
    if args.batch_size <= 0 or args.cpu_threads <= 0:
        raise SystemExit("--batch-size and --cpu-threads must be positive")
    if (not math.isfinite(args.absolute_tolerance) or
            args.absolute_tolerance < 0):
        raise SystemExit("--absolute-tolerance must be finite and nonnegative")
    if os.environ["CUBLAS_WORKSPACE_CONFIG"] not in {":4096:8", ":16:8"}:
        raise SystemExit(
            "CUBLAS_WORKSPACE_CONFIG must be :4096:8 or :16:8"
        )

    torch.set_num_threads(args.cpu_threads)
    torch.manual_seed(args.seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    device = torch.device(args.device)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise SystemExit("the frozen reference must run on an explicit CUDA GPU")
    torch.cuda.set_device(device)

    dataset = args.dataset.resolve(strict=True)
    model_dir = args.model_dir.resolve(strict=True)
    artifact_manifest = args.artifact_manifest.resolve(strict=True)
    dataset_record = file_record(dataset)
    source_records = _source_records()
    checkpoint_sha, artifact_sha, artifact_size = _load_artifact_identity(
        artifact_manifest
    )
    tokenizer = AutoTokenizer.from_pretrained(
        model_dir, local_files_only=True, trust_remote_code=False,
    )
    samples = build_samples(
        dataset, tokenizer, args.text_field, args.sample_count, args.seed
    )

    dtype = _dtype(args.dtype)
    start_ns = time.monotonic_ns()
    model = AutoModelForCausalLM.from_pretrained(
        model_dir, dtype=dtype, local_files_only=True,
        trust_remote_code=False, attn_implementation="eager",
    ).to(device)
    model.config.use_cache = False
    model.eval()
    fixedpoint = config_from_variant(
        args.fixedpoint_variant, requant_mid_a8=False
    )
    method = attach_fixedpoint_mlp_nonlinear(
        model, cfg=fixedpoint, hadamard_block=32, group_size=32,
        act_bits=8, attention_weight_bits=8, mlp_weight_bits=4,
        scale_code_bits=8, compute_dtype=dtype, collect_stats=False,
    )
    _validate_method_contract(method)
    model.eval()
    attach_end_ns = time.monotonic_ns()
    print(
        f"reference_model_ready modules={method.module_count} "
        f"gpu={torch.cuda.get_device_name(device)}",
        flush=True,
    )
    records, mean_nll = _evaluate(model, samples, device, args.batch_size)
    end_ns = time.monotonic_ns()
    if file_record(dataset) != dataset_record:
        raise RuntimeError("dataset changed while generating the reference")
    if _source_records() != source_records:
        raise RuntimeError("reference source changed while generating evidence")
    if (sha256_file(artifact_manifest) != artifact_sha or
            artifact_manifest.stat().st_size != artifact_size):
        raise RuntimeError("artifact manifest changed while generating evidence")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = output_dir / "software_reference.json"
    evidence = {
        "schema": "scalellm_v5_algorithmic_reference_v1",
        "software_id": SOFTWARE_ID,
        "model_id": MODEL_ID,
        "checkpoint_sha256": checkpoint_sha,
        "artifact_manifest": {
            "path": str(artifact_manifest),
            "size": artifact_size,
            "sha256": artifact_sha,
        },
        "dataset": dataset_record,
        "seed": args.seed,
        "sample_count": len(samples),
        "valid_token_rows": len(samples) * 16,
        "quantization": {
            "attention": "Hadamard32 ScaleCode A8W8",
            "mlp": "Hadamard32 ScaleCode A8W4 SwiGLU",
            "fixedpoint": fixedpoint.to_dict(),
            "method": asdict(method),
        },
        "runtime": {
            "torch": torch.__version__,
            "cuda": torch.version.cuda,
            "device": str(device),
            "gpu": torch.cuda.get_device_name(device),
            "dtype": args.dtype,
            "batch_size": args.batch_size,
            "cpu_threads": args.cpu_threads,
            "deterministic_algorithms": True,
            "allow_tf32": False,
            "cublas_workspace_config": os.environ["CUBLAS_WORKSPACE_CONFIG"],
            "model_attach_ns": attach_end_ns - start_ns,
            "evaluation_ns": end_ns - attach_end_ns,
        },
        "source_files": source_records,
        "metric": "causal_nll",
        "nll_sum": sum(item["nll_sum"] for item in records),
        "mean_nll": mean_nll,
        "records": records,
    }
    _write_json_atomic(evidence_path, evidence)
    workload_path = write_workload_manifest(
        dataset=dataset, model_dir=model_dir,
        checkpoint_sha256=checkpoint_sha,
        output=output_dir / "workload_manifest.json", samples=samples,
        software_id=SOFTWARE_ID, expected_mean_nll=mean_nll,
        absolute_tolerance=args.absolute_tolerance, seed=args.seed,
        reference_evidence=evidence_path,
    )
    print(f"SCALELLM_REFERENCE_PASS mean_nll={mean_nll:.12f}")
    print(f"reference={evidence_path} sha256={sha256_file(evidence_path)}")
    print(f"workload={workload_path} sha256={sha256_file(workload_path)}")


if __name__ == "__main__":
    main()
