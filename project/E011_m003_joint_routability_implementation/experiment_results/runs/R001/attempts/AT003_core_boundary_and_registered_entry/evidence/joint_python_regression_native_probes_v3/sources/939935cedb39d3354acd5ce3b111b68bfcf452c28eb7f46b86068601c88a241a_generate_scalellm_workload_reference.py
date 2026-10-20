#!/usr/bin/env python3
"""Generate the frozen ScaleLLM algorithmic NLL reference on one GPU."""

from __future__ import annotations

import argparse
import ast
from dataclasses import asdict
import hashlib
import importlib.util
import inspect
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
SOFTWARE_ROOT = HAP_ROOT.parent / "software" / "0_Software"
GOLDEN_PATH = SOFTWARE_ROOT / "FPtoQ" / "experiment" / "v5_fullchain.py"
APPROVED_GOLDEN_SHA256 = (
    "58a6bb7c769209925bd3bcd9d1a06414b0a25415a46591f70d8efd62db0b9898"
)
APPROVED_EXPORTER_NUMERIC_AST_SHA256 = (
    "a16d2b9f229ef1804e095243c96e62bae6cf0010efb6014609120a507372e196"
)
APPROVED_FIXBIT_SHA256 = (
    "fb4b34397edc9d14ed3ef4f0b46d60a61b545a52a7a47d15c2eec8ba7b6db271"
)
if str(HAP_ROOT) not in sys.path:
    sys.path.insert(0, str(HAP_ROOT))

from model.export_scalellm_llama31_artifacts import (
    ATTENTION_ABI,
    ATTENTION_FORMAT_ID,
    GROUP as EXPORTER_GROUP,
    LlamaCheckpoint,
    MLP_ABI,
    MLP_FORMAT_ID,
    MODEL_ID,
    SCHEMA_VERSION,
)
from model.freeze_scalellm_workload import (
    build_samples,
    file_record,
    sha256_file,
    write_workload_manifest,
)


CURRENT_PROFILE = "core100_ddr200_format05"
CURRENT_SCHEMA = "scalellm_v5_integer_reference_v2"
SOFTWARE_ID = "scalellm-v5-integer-h32-group32-scalecode-down-s32-shift12-v2"
LEGACY_PROFILE = "legacy_p16_fxp16_ddr300"
LEGACY_ID = "scalellm-hadamard-scalecode-a8w8-a8w4-fxp16q5p10-v1"
NUMERIC_CONTRACT = {
    "hadamard_group": 32,
    "hadamard_inverse_sqrt32_q16": 11585,
    "activation_quantizer": "raw_minmax_including_zero_no_source_preclip",
    "activation_scale_rounding": "nearest_even",
    "scalecode_division_rounding": "nearest_even",
    "folded_weight_rounding": "half_away_terminal_w8_w4_saturation",
    "gate_up": {"input_width": 24, "group_guard_width": 37,
                "accumulator_width": 44, "output_width": 24,
                "total_shift_range": [20, 44]},
    "down": {"input_width": 32, "hadamard_width": 35,
             "group_guard_width": 45, "accumulator_width": 54,
             "output_width": 32, "total_shift_range": [12, 44]},
    "swiglu": "signed_packed_s24_internal_s32",
    "attention": "integer_rope_kv12_qk_softmax_pv_legitimate_clamps",
}
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


def _dtype(name: str, torch_module):
    return {
        "bfloat16": torch_module.bfloat16,
        "float16": torch_module.float16,
        "float32": torch_module.float32,
    }[name]


def _load_artifact_identity(path: Path) -> tuple[str, str, int]:
    resolved = path.resolve(strict=True)
    try:
        raw = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot parse artifact manifest {resolved}: {exc}") \
            from exc
    if (not isinstance(raw, dict) or raw.get("model_id") != MODEL_ID or
            type(raw.get("layer_count")) is not int or
            raw["layer_count"] != 32):
        raise ValueError("artifact manifest is not the 32-layer Llama-3.1-8B-Instruct set")
    identity = {
        "schema_version": SCHEMA_VERSION,
        "attention_format_id": ATTENTION_FORMAT_ID,
        "attention_abi": ATTENTION_ABI,
        "mlp_format_id": MLP_FORMAT_ID,
        "mlp_abi": MLP_ABI,
    }
    for key, expected in identity.items():
        if type(raw.get(key)) is not int or raw[key] != expected:
            raise ValueError(
                f"artifact manifest {key} mismatch: expected={expected} "
                f"actual={raw.get(key)!r}"
            )
    checkpoint_sha = raw.get("checkpoint_sha256")
    if (not isinstance(checkpoint_sha, str) or len(checkpoint_sha) != 64 or
            any(character not in "0123456789abcdef"
                for character in checkpoint_sha)):
        raise ValueError("artifact manifest checkpoint SHA256 is invalid")
    if raw.get("checkpoint_id") != checkpoint_sha:
        raise ValueError("artifact manifest checkpoint ID disagrees with SHA256")
    return checkpoint_sha, sha256_file(resolved), resolved.stat().st_size


def _legacy_imports():
    candidates = (HAP_ROOT, HAP_ROOT.parent / "fpga_llm_project",
                  HAP_ROOT.parent.parent / "fpga_llm_project", *HAP_ROOT.parents)
    project_root = next((root for root in candidates if
                         (root / "scripts" / "accuracy_MLP_4bit").is_dir()), None)
    if project_root is None:
        raise RuntimeError("historical FXP16 scripts are unavailable")
    fixedpoint_dir = project_root / "scripts" / "accuracy_MLP_4bit" / "scala_code_accuracy"
    scale_code_dir = project_root / "scripts" / "scale_code_linear"
    for import_root in (fixedpoint_dir, scale_code_dir):
        if str(import_root) not in sys.path:
            sys.path.insert(0, str(import_root))
    from fixedpoint_ops import config_from_variant
    from mlp4_fixedpoint_inference import attach_fixedpoint_mlp_nonlinear
    return project_root, fixedpoint_dir, scale_code_dir, config_from_variant, attach_fixedpoint_mlp_nonlinear


def _source_records(*, attach=None, legacy_roots=None) -> list[dict]:
    if legacy_roots is None:
        if attach is None:
            raise RuntimeError("current source closure requires the resolved V5 callback")
        if EXPORTER_GROUP != 32:
            raise RuntimeError("V5 exporter Hadamard group changed")
        selected = attach.__globals__
        files = (
            SCRIPT_PATH, HAP_ROOT / "model" / "freeze_scalellm_workload.py",
            Path(inspect.getfile(attach)),
            Path(inspect.getfile(selected["quantize_folded_rows"])),
            Path(inspect.getfile(selected["build_softmax_exp_lut_u17"])),
        )
        expected = (SCRIPT_PATH, HAP_ROOT / "model" / "freeze_scalellm_workload.py",
                    GOLDEN_PATH, HAP_ROOT / "model" / "export_scalellm_llama31_artifacts.py",
                    HAP_ROOT / "model" / "fixbit_v2.py")
        if tuple(path.resolve(strict=True) for path in files) != tuple(
            path.resolve(strict=True) for path in expected
        ):
            raise RuntimeError("V5 golden selected an unexpected exporter/FixBit helper")
        exporter_tree = ast.parse(expected[3].read_text(encoding="utf-8"))
        numeric_names = (
            "llama3_inv_freq", "round_away", "fwht32_normalized",
            "encode_scales", "quantize_folded_rows",
        )
        functions = {
            node.name: ast.dump(node, include_attributes=False)
            for node in exporter_tree.body
            if isinstance(node, ast.FunctionDef) and node.name in numeric_names
        }
        if set(functions) != set(numeric_names):
            raise RuntimeError("V5 exporter numeric helpers are incomplete")
        digest = hashlib.sha256(
            "\n".join(functions[name] for name in numeric_names).encode("utf-8")
        ).hexdigest()
        if (digest != APPROVED_EXPORTER_NUMERIC_AST_SHA256 or
                sha256_file(expected[4]) != APPROVED_FIXBIT_SHA256):
            raise RuntimeError("V5 exporter/FixBit numerical helpers changed")
        return [file_record(path) for path in files]
    project_root, fixedpoint_dir, scale_code_dir = legacy_roots
    files = (
        SCRIPT_PATH,
        HAP_ROOT / "model" / "freeze_scalellm_workload.py",
        fixedpoint_dir / "fixedpoint_ops.py",
        fixedpoint_dir / "mlp4_fixedpoint_inference.py",
        project_root / "scripts" / "accuracy_MLP_4bit"
        / "mlp4_method_inference.py",
        scale_code_dir / "scalepath4_method_inference.py",
    )
    return [file_record(path) for path in files]


def _validate_legacy_method_contract(method) -> None:
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


def _load_current_attach():
    path = GOLDEN_PATH.resolve(strict=True)
    if sha256_file(path) != APPROVED_GOLDEN_SHA256:
        raise RuntimeError("approved V5 golden source SHA256 changed")
    spec = importlib.util.spec_from_file_location("scalellm_v5_fullchain_golden", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load approved V5 golden: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    attach = module.attach_v5_fullchain
    if Path(inspect.getfile(attach)).resolve(strict=True) != path:
        raise RuntimeError("V5 attachment did not resolve to the approved source")
    return attach


def _validate_current_method(method: object, audit: object) -> None:
    if not isinstance(method, dict) or method.get("case") != "v5_production_fullchain":
        raise RuntimeError("V5 attachment did not return its production method")
    exact = {
        "manifest": "vivado/manifests/attention_mlp_production_v5_cohort16_sources.list",
        "mlp_full_format_id": "0x48384605", "layers": 32,
        "max_context": 128, "cohort_rows": 16,
        "attention_weight_bits": 8, "mlp_weight_bits": 4,
        "activation_bits": 8, "kv_bits": 12,
        "host_residual_rmsnorm": "FP32", "lm_head": "FP32 host",
        "strict_total_shift": True, "total_shift_policy": "strict_rtl",
        "software_reference_not_hardware": False,
        "node_trace_layers": [],
        "mlp_total_shift_range": [12, 44],
        "mlp_group_guard_compute_width": 45,
        "mlp_gate_up_accumulator_compute_width": 44,
        "mlp_down_accumulator_compute_width": 54,
        "mlp_down_output_width": 32,
    }
    for key, expected in exact.items():
        if method.get(key) != expected:
            raise RuntimeError(f"V5 attachment method {key} drifted")
    if method.get("attention_format_id") != "0x48384103":
        raise RuntimeError("V5 Attention format drifted")
    if not callable(getattr(audit, "collect", None)) or not callable(
        getattr(audit, "collect_linear", None)
    ):
        raise RuntimeError("V5 attachment did not return an audit collector")
    names = set(getattr(audit, "linear_values", {}))
    expected_names = {
        f"model.layers.{layer}.{scope}.{op}.weight"
        for layer in range(32)
        for scope, ops in (("self_attn", ("q_proj", "k_proj", "v_proj", "o_proj")),
                           ("mlp", ("gate_proj", "up_proj", "down_proj")))
        for op in ops
    }
    if names != expected_names:
        raise RuntimeError("V5 attachment did not bind all 224 linear operations")


def _evaluate(
    model, samples: list[dict], device, batch_size: int, torch_module,
) -> tuple[list[dict], float]:
    records = []
    nll_sum = 0.0
    row_count = 0
    with torch_module.inference_mode():
        for start in range(0, len(samples), batch_size):
            batch = samples[start:start + batch_size]
            input_ids = torch_module.tensor(
                [item["input_token_ids"] for item in batch],
                dtype=torch_module.long, device=device,
            )
            target_ids = torch_module.tensor(
                [item["target_token_ids"] for item in batch],
                dtype=torch_module.long, device=device,
            )
            logits = model(
                input_ids=input_ids,
                attention_mask=torch_module.ones_like(input_ids),
                use_cache=False,
            ).logits.to(torch_module.float32)
            if logits.shape[:2] != input_ids.shape or logits.shape[2] != 128_256:
                raise RuntimeError(f"unexpected reference logits shape: {logits.shape}")
            target_logits = torch_module.gather(
                logits, 2, target_ids.unsqueeze(-1)
            ).squeeze(-1)
            nll = torch_module.logsumexp(logits, dim=-1) - target_logits
            top_values, top_ids = torch_module.topk(
                logits, k=5, dim=-1, largest=True, sorted=True
            )
            for index, sample in enumerate(batch):
                sample_nll = nll[index].detach().cpu().to(torch_module.float64)
                records.append({
                    "sample_id": sample["sample_id"],
                    "input_token_ids": sample["input_token_ids"],
                    "target_token_ids": sample["target_token_ids"],
                    "nll_sum": float(sample_nll.sum().item()),
                    "mean_nll": float(sample_nll.mean().item()),
                    "per_row_nll": sample_nll.tolist(),
                    "target_logits": target_logits[index].detach().cpu()
                    .to(torch_module.float64).tolist(),
                    "top_token_ids": top_ids[index].detach().cpu().tolist(),
                    "top_logits": top_values[index].detach().cpu()
                    .to(torch_module.float64).tolist(),
                })
            nll_sum += float(nll.detach().to(torch_module.float64).sum().item())
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
    parser.add_argument("--reference-profile", choices=(CURRENT_PROFILE, LEGACY_PROFILE),
                        default=CURRENT_PROFILE)
    parser.add_argument("--fixedpoint-variant")
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
    if args.reference_profile == CURRENT_PROFILE and (
        args.dtype != "bfloat16" or args.batch_size != 2 or
        args.cpu_threads > 4
    ):
        raise SystemExit("current V5 reference requires BF16, batch2, 1..4 CPU threads")

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

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
    if args.reference_profile == CURRENT_PROFILE:
        if args.fixedpoint_variant is not None:
            raise SystemExit("--fixedpoint-variant is historical-only")
        attach_current = _load_current_attach()
        source_records = _source_records(attach=attach_current)
        legacy_imports = None
    else:
        legacy_imports = _legacy_imports()
        source_records = _source_records(legacy_roots=legacy_imports[:3])
    checkpoint_sha, artifact_sha, artifact_size = _load_artifact_identity(
        artifact_manifest
    )
    checkpoint = LlamaCheckpoint(model_dir)
    actual_sha, _ = checkpoint.source_identity()
    if actual_sha != checkpoint_sha:
        raise ValueError("artifact manifest does not bind the Instruct checkpoint")
    tokenizer = AutoTokenizer.from_pretrained(
        model_dir, local_files_only=True, trust_remote_code=False,
    )
    samples = build_samples(
        dataset, tokenizer, args.text_field, args.sample_count, args.seed
    )

    dtype = _dtype(args.dtype, torch)
    start_ns = time.monotonic_ns()
    model = AutoModelForCausalLM.from_pretrained(
        model_dir, dtype=dtype, local_files_only=True,
        trust_remote_code=False, attn_implementation="eager",
    ).to(device)
    model.config.use_cache = False
    model.eval()
    if args.reference_profile == CURRENT_PROFILE:
        method, audit = attach_current(
            model, checkpoint_dir=model_dir, device=device,
            strict_total_shift=True, software_extended=False,
            down_output_width=32, down_shift12_candidate=True,
        )
        _validate_current_method(method, audit)
        method_record = method
        fixedpoint_record = NUMERIC_CONTRACT
        software_id = SOFTWARE_ID
    else:
        _, _, _, config_from_variant, attach_legacy = legacy_imports
        fixedpoint = config_from_variant(
            args.fixedpoint_variant or "FXP16-Q5.10", requant_mid_a8=False
        )
        method = attach_legacy(
            model, cfg=fixedpoint, hadamard_block=32, group_size=32,
            act_bits=8, attention_weight_bits=8, mlp_weight_bits=4,
            scale_code_bits=8, compute_dtype=dtype, collect_stats=False,
        )
        _validate_legacy_method_contract(method)
        method_record = asdict(method)
        fixedpoint_record = fixedpoint.to_dict()
        software_id = LEGACY_ID
    model.eval()
    attach_end_ns = time.monotonic_ns()
    print(
        f"reference_model_ready profile={args.reference_profile} "
        f"gpu={torch.cuda.get_device_name(device)}",
        flush=True,
    )
    records, mean_nll = _evaluate(model, samples, device, args.batch_size, torch)
    end_ns = time.monotonic_ns()
    if file_record(dataset) != dataset_record:
        raise RuntimeError("dataset changed while generating the reference")
    if _source_records(attach=attach_current if args.reference_profile == CURRENT_PROFILE
                       else None,
                       legacy_roots=None if args.reference_profile == CURRENT_PROFILE
                       else legacy_imports[:3]) != source_records:
        raise RuntimeError("reference source changed while generating evidence")
    if (sha256_file(artifact_manifest) != artifact_sha or
            artifact_manifest.stat().st_size != artifact_size):
        raise RuntimeError("artifact manifest changed while generating evidence")
    if checkpoint.source_identity()[0] != checkpoint_sha:
        raise RuntimeError("Instruct checkpoint changed while generating evidence")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = output_dir / "software_reference.json"
    evidence = {
        "schema": (CURRENT_SCHEMA if args.reference_profile == CURRENT_PROFILE
                   else "scalellm_v5_algorithmic_reference_v1"),
        "software_id": software_id,
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
            "fixedpoint": fixedpoint_record,
            "method": method_record,
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
    if args.reference_profile == CURRENT_PROFILE:
        collected = audit.collect()
        linear_audit = audit.collect_linear()
        if set(linear_audit) != set(audit.linear_values):
            raise RuntimeError("V5 audit lost linear operation coverage")
        evidence["profile"] = CURRENT_PROFILE
        evidence["audit"] = {"counters": collected, "linear": linear_audit}
    _write_json_atomic(evidence_path, evidence)
    workload_path = write_workload_manifest(
        dataset=dataset, model_dir=model_dir,
        checkpoint_sha256=checkpoint_sha,
        output=output_dir / "workload_manifest.json", samples=samples,
        software_id=software_id, reference_profile=args.reference_profile,
        expected_mean_nll=mean_nll,
        absolute_tolerance=args.absolute_tolerance, seed=args.seed,
        reference_evidence=evidence_path,
    )
    print(f"SCALELLM_REFERENCE_PASS mean_nll={mean_nll:.12f}")
    print(f"reference={evidence_path} sha256={sha256_file(evidence_path)}")
    print(f"workload={workload_path} sha256={sha256_file(workload_path)}")


if __name__ == "__main__":
    main()
