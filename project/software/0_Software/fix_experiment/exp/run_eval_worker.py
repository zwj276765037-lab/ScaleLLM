#!/usr/bin/env python3
"""Run one task shard on one GPU with canonical lm_eval semantics."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import gc
import json
import math
import os
from pathlib import Path
import platform
import random
import sys
import time
import traceback
import types
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer

from protocol import (
    MODEL_ROOT,
    PRIMARY_METRIC,
    PROTOCOL_CONTEXT,
    TASK_ORDER,
    SOFTWARE_ROOT,
    build_task,
    data_manifest,
    read_wikitext,
    validate_protocol,
)
from six_model_matrix import (
    FIVE_CONFIG_CASES,
    QUANTIZED_CASE_SPECS,
    get_model_spec,
    validate_quantized_summary,
)


THIS_DIR = Path(__file__).resolve().parent
V5_DIR = SOFTWARE_ROOT / "0_Software" / "FPtoQ" / "experiment"
REFERENCE_QDQ_DIR = (
    SOFTWARE_ROOT
    / "0_Software"
    / "experiment"
    / "scripts"
    / "accuracy_MLP_4bit"
)
DEFAULT_MODEL = MODEL_ROOT / "Llama-3.1-8B-Instruct"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--case",
        choices=FIVE_CONFIG_CASES
        + (
            "v5_attention",
            "v5_mlp",
            "v5_mlp_down_s32_ablation",
            "v5_mlp_down_s32_shift12_ablation",
            "v5",
            "v5_down_s32_ablation",
            "v5_algorithm",
        ),
        required=True,
    )
    parser.add_argument(
        "--protocol",
        choices=tuple(PROTOCOL_CONTEXT),
        required=True,
    )
    parser.add_argument("--tasks", required=True, help="Comma-separated task shard")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument(
        "--model-identity",
        type=Path,
        help="Content-addressed checkpoint identity generated once by the plan runner.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--ppl-batch-size", type=int, default=1)
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Smoke-test limit per ACC task and PPL blocks; 0 means full data.",
    )
    parser.add_argument("--seed", type=int, default=20260913)
    parser.add_argument(
        "--allow-format-errors",
        action="store_true",
        help="Run the V5 RTL zero-guard diagnostic and mark the result invalid.",
    )
    parser.add_argument(
        "--node-trace-layers",
        default="",
        help="Comma-separated V5 layer ids for bounded real-activation traces.",
    )
    parser.add_argument("--node-trace-max-calls", type=int, default=1)
    return parser.parse_args()


def atomic_json(path: Path, value: Any) -> None:
    from lm_eval.utils import handle_non_serializable

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(
            value,
            handle,
            ensure_ascii=False,
            indent=2,
            default=handle_non_serializable,
        )
        handle.write("\n")
    temporary.replace(path)


def configure_reproducibility(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False


def load_model_identity(path: Path | None, model: Path) -> dict[str, Any] | None:
    if path is None:
        return None
    with path.resolve().open(encoding="utf-8") as handle:
        identity = json.load(handle)
    if identity.get("schema") != "scalellm_checkpoint_identity_v1":
        raise ValueError(f"unsupported model identity schema: {identity.get('schema')}")
    if Path(identity["resolved_path"]).resolve() != model.resolve():
        raise ValueError(
            f"model identity path mismatch: {identity['resolved_path']} != {model}"
        )
    spec = get_model_spec(model)
    if identity.get("checkpoint_name") != spec.name:
        raise ValueError(
            f"model identity name mismatch: {identity.get('checkpoint_name')} != {spec.name}"
        )
    if not identity.get("fingerprint_sha256"):
        raise ValueError("model identity has no fingerprint_sha256")
    return identity


def package_versions() -> dict[str, str]:
    import accelerate
    import datasets
    import lm_eval
    import transformers
    import triton

    return {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "datasets": datasets.__version__,
        "lm_eval": getattr(lm_eval, "__version__", "unknown"),
        "accelerate": accelerate.__version__,
        "triton": triton.__version__,
    }


def ensure_evaluator_version(versions: dict[str, str]) -> None:
    if versions["lm_eval"] != "0.4.11":
        raise RuntimeError(
            "This protocol is frozen against lm_eval==0.4.11; observed "
            f"{versions['lm_eval']}. Use exp/requirements.txt."
        )


def load_model(args: argparse.Namespace, integrity_observer: Any = None) -> tuple[Any, Any, dict[str, Any], Any]:
    device = torch.device(args.device)
    if device.type != "cuda":
        raise ValueError("The Llama-3.1-8B evaluation requires a CUDA device")
    torch.cuda.set_device(device)
    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        local_files_only=True,
        trust_remote_code=True,
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        local_files_only=True,
        trust_remote_code=True,
        dtype=torch.bfloat16,
        attn_implementation="eager",
    )
    if integrity_observer is not None:
        integrity_observer("cpu_loaded", model)
    model = model.to(device)
    if integrity_observer is not None:
        integrity_observer("gpu_loaded", model)
    model.config.use_cache = False
    model.eval()
    if args.case in QUANTIZED_CASE_SPECS:
        if str(REFERENCE_QDQ_DIR) not in sys.path:
            sys.path.insert(0, str(REFERENCE_QDQ_DIR))
        from mlp4_method_inference import (
            attach_scalepath_iah_fp16_scale_mlp_w4,
            attach_scalepath_iah_fp32_scale_mlp_w4,
            attach_scalepath_iah_scale_code_mlp_w4,
        )

        common = {
            "hadamard_block": 32,
            "group_size": 32,
            "act_bits": 8,
            "attention_weight_bits": 8,
            "mlp_weight_bits": int(
                QUANTIZED_CASE_SPECS[args.case]["mlp_weight_bits"]
            ),
            "compute_dtype": torch.bfloat16,
        }
        if args.case == "reference_qdq":
            summary = attach_scalepath_iah_scale_code_mlp_w4(
                model,
                scale_code_bits=8,
                **common,
            )
        elif args.case == "a8w4_fp16":
            summary = attach_scalepath_iah_fp16_scale_mlp_w4(model, **common)
        else:
            summary = attach_scalepath_iah_fp32_scale_mlp_w4(model, **common)
        method = {
            **asdict(summary),
            "evaluation_role": "algorithm_quality_reference",
            "evaluation_case": args.case,
            "native_attention_rope_kv": True,
            "hardware_fixed_point_frontend": False,
            "hardware_numeric_contract": "not_applicable",
        }
        audit = None
    elif args.case in {
        "v5_attention",
        "v5_mlp",
        "v5_mlp_down_s32_ablation",
        "v5_mlp_down_s32_shift12_ablation",
        "v5",
        "v5_down_s32_ablation",
        "v5_algorithm",
    }:
        # Transformers 5.x normalizes the legacy Llama keys rope_theta and
        # rope_scaling into rope_parameters.  The frozen V5 artifact builder
        # consumes the original checkpoint schema, so restore those aliases
        # from config.json without changing their values.
        checkpoint_config = json.loads((args.model / "config.json").read_text())
        model.config.rope_theta = checkpoint_config["rope_theta"]
        # LlamaConfig.rope_scaling is a 5.x compatibility property whose
        # setter writes rope_parameters; V5 calls config.to_dict() and needs
        # the legacy key itself present in __dict__.
        model.config.__dict__["rope_scaling"] = checkpoint_config["rope_scaling"]
        # V5 was written against the Transformers 4.x LlamaAttention public
        # attributes. Restore their immutable geometry aliases under 5.x.
        for layer in model.model.layers:
            attention = layer.self_attn
            attention.num_heads = int(model.config.num_attention_heads)
            attention.num_key_value_heads = int(model.config.num_key_value_heads)
            attention.num_key_value_groups = (
                attention.num_heads // attention.num_key_value_heads
            )
            attention.head_dim = int(model.config.head_dim)
            attention.hidden_size = int(model.config.hidden_size)
        if str(V5_DIR) not in sys.path:
            sys.path.insert(0, str(V5_DIR))
        from v5_fullchain import (
            attach_v5_attention_only,
            attach_v5_fullchain,
            attach_v5_mlp_only,
        )

        trace_layers = {
            int(part)
            for part in args.node_trace_layers.split(",")
            if part.strip()
        }
        if any(layer < 0 or layer >= 32 for layer in trace_layers):
            raise ValueError("--node-trace-layers must be in [0,31]")
        if args.node_trace_max_calls <= 0:
            raise ValueError("--node-trace-max-calls must be positive")
        trace_args = {
            "trace_layers": trace_layers,
            "trace_max_calls_per_layer": args.node_trace_max_calls,
        }
        if args.case == "v5_attention":
            method, audit = attach_v5_attention_only(
                model,
                checkpoint_dir=args.model,
                device=device,
                strict_total_shift=not args.allow_format_errors,
                **trace_args,
            )
        elif args.case in {
            "v5_mlp",
            "v5_mlp_down_s32_ablation",
            "v5_mlp_down_s32_shift12_ablation",
        }:
            method, audit = attach_v5_mlp_only(
                model,
                checkpoint_dir=args.model,
                device=device,
                strict_total_shift=not args.allow_format_errors,
                down_output_width=(
                    32
                    if args.case in {
                        "v5_mlp_down_s32_ablation",
                        "v5_mlp_down_s32_shift12_ablation",
                    }
                    else 24
                ),
                down_shift12_candidate=(
                    args.case == "v5_mlp_down_s32_shift12_ablation"
                ),
                **trace_args,
            )
            if args.case in {
                "v5_mlp_down_s32_ablation",
                "v5_mlp_down_s32_shift12_ablation",
            }:
                shift12 = args.case == "v5_mlp_down_s32_shift12_ablation"
                method["case"] = (
                    "v5_mlp_down_s32_shift12_candidate_ablation"
                    if shift12
                    else "v5_mlp_down_s32_diagnostic_ablation"
                )
                method["evaluation_role"] = "diagnostic_not_hardware"
                method["source_hardware_mlp_full_format_id"] = (
                    "0x48384604" if shift12 else "0x48384603"
                )
                method["mlp_full_format_id"] = (
                    "0x48384605" if shift12 else "0x48384604"
                )
        else:
            method, audit = attach_v5_fullchain(
                model,
                checkpoint_dir=args.model,
                device=device,
                strict_total_shift=(
                    args.case in {"v5", "v5_down_s32_ablation"}
                    and not args.allow_format_errors
                ),
                software_extended=args.case == "v5_algorithm",
                down_output_width=(
                    32 if args.case == "v5_down_s32_ablation" else 24
                ),
                **trace_args,
            )
            if args.case == "v5_down_s32_ablation":
                method["case"] = "v5_down_s32_candidate_fullchain"
                method["evaluation_role"] = "diagnostic_not_current_hardware"
                method["source_hardware_mlp_full_format_id"] = "0x48384603"
                method["mlp_full_format_id"] = "0x48384604"
        # Transformers 5.x decoder layers expect attention to return
        # (hidden_states, weights), whereas the frozen V5 Attention twin follows
        # the Transformers 4.x three-item contract.  MLP-only deliberately keeps
        # native Transformers 5 Attention and must not receive this adapter.
        if args.case not in {
            "v5_mlp",
            "v5_mlp_down_s32_ablation",
            "v5_mlp_down_s32_shift12_ablation",
        }:
            for layer in model.model.layers:
                attention = layer.self_attn
                v5_forward = attention.forward

                def transformers5_forward(
                    self: Any,
                    *forward_args: Any,
                    _v5_forward: Any = v5_forward,
                    **forward_kwargs: Any,
                ) -> tuple[Any, Any]:
                    if "past_key_values" in forward_kwargs:
                        forward_kwargs["past_key_value"] = forward_kwargs.pop(
                            "past_key_values"
                        )
                    output, weights, _cache = _v5_forward(
                        *forward_args, **forward_kwargs
                    )
                    return output, weights

                attention.forward = types.MethodType(
                    transformers5_forward, attention
                )
            attention_return_arity = "3_to_2"
        else:
            attention_return_arity = "native_transformers_5"
        method["transformers_5_api_adapter"] = {
            "geometry_aliases_only": True,
            "attention_return_arity": attention_return_arity,
            "numeric_path_changed": False,
        }
    else:
        method = {
            "case": "bf16",
            "dtype": "bfloat16",
            "attention_implementation": "eager",
            "use_cache": False,
        }
        audit = None
    model.eval()
    return model, tokenizer, method, audit


def audit_requests(task: Any, lm: Any, context_length: int, limit: int | None) -> dict[str, Any]:
    """Measure exactly which lm_eval requests require left truncation."""
    task.build_all_requests(
        limit=limit,
        rank=0,
        world_size=1,
        cache_requests=False,
        tokenizer_name=str(lm.tokenizer.name_or_path),
    )
    request_count = 0
    truncated_requests = 0
    truncated_documents: set[int] = set()
    left_truncated_prompt_requests = 0
    left_truncated_prompt_documents: set[int] = set()
    windowed_continuation_requests = 0
    windowed_continuation_documents: set[int] = set()
    boundary_fallback_requests = 0
    boundary_fallback_documents: set[int] = set()
    maximum_total = 0
    maximum_continuation = 0
    for instance in task.instances:
        if instance.request_type != "loglikelihood":
            continue
        context, continuation = instance.args
        if context:
            context_ids, continuation_ids = lm._encode_pair(context, continuation)
            if bool(getattr(lm, "_last_boundary_fallback", False)):
                boundary_fallback_requests += 1
                if instance.doc_id is not None:
                    boundary_fallback_documents.add(int(instance.doc_id))
        else:
            continuation_ids = lm.tok_encode(
                continuation, add_special_tokens=False
            )
            context_ids = [lm.prefix_token_id]
        total = len(context_ids) + len(continuation_ids)
        maximum_total = max(maximum_total, total)
        maximum_continuation = max(maximum_continuation, len(continuation_ids))
        request_count += 1
        # HFLM consumes at most max_length+1 tokens to score max_length inputs.
        if total > context_length + 1:
            truncated_requests += 1
            if instance.doc_id is not None:
                truncated_documents.add(int(instance.doc_id))
            if len(continuation_ids) > context_length:
                windowed_continuation_requests += 1
                if instance.doc_id is not None:
                    windowed_continuation_documents.add(int(instance.doc_id))
            else:
                left_truncated_prompt_requests += 1
                if instance.doc_id is not None:
                    left_truncated_prompt_documents.add(int(instance.doc_id))
    evaluated_documents = len({
        int(instance.doc_id)
        for instance in task.instances
        if instance.doc_id is not None
    })
    return {
        "documents": evaluated_documents,
        "requests": request_count,
        "truncated_documents": len(truncated_documents),
        "truncated_document_fraction": (
            len(truncated_documents) / evaluated_documents
            if evaluated_documents
            else 0.0
        ),
        "truncated_requests": truncated_requests,
        "truncated_request_fraction": (
            truncated_requests / request_count if request_count else 0.0
        ),
        "maximum_context_plus_continuation_tokens": maximum_total,
        "maximum_continuation_tokens": maximum_continuation,
        "left_truncated_prompt_documents": len(left_truncated_prompt_documents),
        "left_truncated_prompt_requests": left_truncated_prompt_requests,
        "windowed_continuation_documents": len(windowed_continuation_documents),
        "windowed_continuation_requests": windowed_continuation_requests,
        "tokenizer_boundary_fallback_documents": len(boundary_fallback_documents),
        "tokenizer_boundary_fallback_requests": boundary_fallback_requests,
        "lm_eval_max_length": context_length,
    }


def tokenizer_boundary_safe_hflm_class(base: Any) -> Any:
    """Keep the prompt fixed when a tokenizer is not prefix-stable.

    lm-eval 0.4.11 normally tokenizes ``context + continuation`` and slices it
    at ``len(tokenize(context))``. Some Llama-derived tokenizers can merge the
    final prompt punctuation with the first choice token (for example,
    ``Answer:`` + `` no``). The combined encoding then does not begin with the
    context encoding and the stock slicer may produce an empty continuation.

    For prefix-stable pairs this is byte-for-byte the stock lm-eval path. For
    non-prefix-stable pairs, tokenize the continuation independently without
    special tokens while retaining the exact context tokens for every choice.
    This prevents a candidate-specific prompt change and is applied identically
    to BF16 and Reference-QDQ.
    """

    class TokenizerBoundarySafeHFLM(base):
        _last_boundary_fallback = False

        def _encode_pair(
            self, context: str, continuation: str
        ) -> tuple[list[int], list[int]]:
            if not context:
                raise AssertionError("Context cannot be empty!")
            n_spaces = len(context) - len(context.rstrip())
            if n_spaces > 0:
                continuation = context[-n_spaces:] + continuation
                context = context[:-n_spaces]
            if self.backend != "causal":
                self._last_boundary_fallback = False
                return super()._encode_pair(context, continuation)
            whole_enc = self.tok_encode(context + continuation)
            context_enc = self.tok_encode(context)
            prefix_stable = (
                len(whole_enc) > len(context_enc)
                and whole_enc[: len(context_enc)] == context_enc
            )
            if prefix_stable:
                self._last_boundary_fallback = False
                return context_enc, whole_enc[len(context_enc) :]
            continuation_enc = self.tok_encode(
                continuation, add_special_tokens=False
            )
            if not continuation_enc:
                raise ValueError(
                    "tokenizer produced an empty continuation even with the "
                    "boundary-safe independent encoding"
                )
            self._last_boundary_fallback = True
            return context_enc, continuation_enc

    return TokenizerBoundarySafeHFLM


def hardware_windowed_hflm_class(base: Any) -> Any:
    """Extend HFLM to score choices longer than the 128-token V5 window.

    Standard HFLM intentionally asserts that a continuation fits in max_length.
    PIQA contains 20 choice requests longer than 128 tokens.  The hardware
    protocol scores every choice token over rolling, non-cached model calls;
    silently dropping those samples or scoring only the suffix would bias ACC.
    """

    class HardwareWindowedHFLM(base):
        @torch.no_grad()
        def _score_windowed_request(self, request: Any) -> tuple[float, bool]:
            context, continuation = request.args
            if context:
                context_ids, continuation_ids = self._encode_pair(
                    context, continuation
                )
            else:
                continuation_ids = self.tok_encode(
                    continuation, add_special_tokens=False
                )
                context_ids = [self.prefix_token_id]
            if not continuation_ids:
                raise ValueError("empty continuation in hardware window scorer")
            history = list(context_ids)
            total_loglikelihood = 0.0
            all_greedy = True
            offset = 0
            target_capacity = self.max_length - 1
            if target_capacity <= 0:
                raise ValueError("hardware context must be at least two tokens")
            while offset < len(continuation_ids):
                target = continuation_ids[offset : offset + target_capacity]
                prefix_budget = self.max_length - len(target)
                prefix = history[-prefix_budget:]
                if not prefix:
                    prefix = [self.prefix_token_id]
                input_ids = torch.tensor(
                    prefix + target,
                    dtype=torch.long,
                    device=self.device,
                ).unsqueeze(0)
                logits = F.log_softmax(
                    self._model_call(input_ids),
                    dim=-1,
                    dtype=self.softmax_dtype,
                )
                first_logit = len(prefix) - 1
                selected = logits[
                    :, first_logit : first_logit + len(target), :
                ]
                target_tensor = torch.tensor(
                    target, dtype=torch.long, device=self.device
                ).view(1, -1, 1)
                total_loglikelihood += float(
                    torch.gather(selected, 2, target_tensor).sum().cpu()
                )
                all_greedy = all_greedy and bool(
                    (selected.argmax(dim=-1) == target_tensor.squeeze(-1))
                    .all()
                    .item()
                )
                history.extend(target)
                offset += len(target)
            return total_loglikelihood, all_greedy

        def loglikelihood(
            self, requests: list[Any], disable_tqdm: bool = False
        ) -> list[tuple[float, bool]]:
            outputs: list[tuple[float, bool] | None] = [None] * len(requests)
            regular_indices: list[int] = []
            regular_requests: list[Any] = []
            for index, request in enumerate(requests):
                context, continuation = request.args
                if context:
                    _context_ids, continuation_ids = self._encode_pair(
                        context, continuation
                    )
                else:
                    continuation_ids = self.tok_encode(
                        continuation, add_special_tokens=False
                    )
                if len(continuation_ids) > self.max_length:
                    outputs[index] = self._score_windowed_request(request)
                else:
                    regular_indices.append(index)
                    regular_requests.append(request)
            if regular_requests:
                regular_outputs = super().loglikelihood(
                    regular_requests, disable_tqdm=disable_tqdm
                )
                for index, value in zip(
                    regular_indices, regular_outputs, strict=True
                ):
                    outputs[index] = value
            if any(value is None for value in outputs):
                raise AssertionError("missing hardware-window loglikelihood")
            return [value for value in outputs if value is not None]

    return HardwareWindowedHFLM


def _metric_value(metrics: dict[str, Any], metric: str) -> tuple[float, float | None]:
    candidates = (f"{metric},none", metric)
    for key in candidates:
        if key in metrics:
            stderr = metrics.get(key.replace(metric, metric + "_stderr", 1))
            parsed_stderr = (
                None
                if stderr is None or str(stderr).strip().upper() == "N/A"
                else float(stderr)
            )
            return float(metrics[key]), parsed_stderr
    raise KeyError(f"metric {metric!r} absent from {sorted(metrics)}")


def run_acc(
    *,
    model: Any,
    tokenizer: Any,
    tasks: list[str],
    context_length: int,
    batch_size: int,
    limit: int | None,
    seed: int,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    from lm_eval import evaluator
    from lm_eval.models.huggingface import HFLM

    task_objects = [build_task(task) for task in tasks]
    boundary_safe_class = tokenizer_boundary_safe_hflm_class(HFLM)
    model_class = (
        hardware_windowed_hflm_class(boundary_safe_class)
        if context_length == 128
        else boundary_safe_class
    )
    lm = model_class(
        pretrained=model,
        tokenizer=tokenizer,
        backend="causal",
        max_length=context_length,
        truncation=True,
        batch_size=batch_size,
        logits_cache=True,
    )
    truncation = {
        task_name: audit_requests(task, lm, context_length, limit)
        for task_name, task in zip(tasks, task_objects, strict=True)
    }
    raw = evaluator.simple_evaluate(
        model=lm,
        tasks=task_objects,
        num_fewshot=0,
        batch_size=batch_size,
        limit=limit,
        # A positive value enables lm_eval's closed-form mean stderr for ACC.
        # No bootstrap loop is used for these mean-aggregated metrics.
        bootstrap_iters=1,
        log_samples=False,
        random_seed=seed,
        numpy_random_seed=seed,
        torch_random_seed=seed,
        fewshot_random_seed=seed,
        verbosity="INFO",
    )
    if raw is None:
        raise RuntimeError("lm_eval returned no result")
    rows: list[dict[str, Any]] = []
    for task in tasks:
        metrics = raw["results"][task]
        primary = PRIMARY_METRIC[task]
        value, stderr = _metric_value(metrics, primary)
        rows.append(
            {
                "task": task,
                "kind": "acc",
                "primary_metric": primary,
                "value": value,
                "stderr": stderr,
                "samples": truncation[task]["documents"],
                "truncated_documents": truncation[task]["truncated_documents"],
                "truncated_document_fraction": truncation[task][
                    "truncated_document_fraction"
                ],
                "left_truncated_prompt_documents": truncation[task][
                    "left_truncated_prompt_documents"
                ],
                "windowed_continuation_documents": truncation[task][
                    "windowed_continuation_documents"
                ],
                "all_metrics": metrics,
            }
        )
    return raw, truncation, rows


@torch.no_grad()
def run_ppl(
    *,
    model: Any,
    tokenizer: Any,
    device: torch.device,
    block_size: int,
    batch_size: int,
    limit: int | None,
) -> dict[str, Any]:
    """GPTQ/QuaRot-style full-stream, non-overlapping WikiText-2 PPL."""
    started = time.time()
    token_ids = tokenizer(
        read_wikitext(),
        add_special_tokens=False,
        return_tensors="pt",
    )["input_ids"][0]
    raw_tokens = int(token_ids.numel())
    available_blocks = raw_tokens // block_size
    block_count = available_blocks if limit is None else min(limit, available_blocks)
    if block_count <= 0:
        raise ValueError("WikiText-2 has no complete evaluation block")
    used = token_ids[: block_count * block_size].reshape(block_count, block_size)
    total_nll = 0.0
    scoring_tokens = 0
    for start in range(0, block_count, max(1, batch_size)):
        batch = used[start : start + max(1, batch_size)].to(device)
        logits = model(input_ids=batch, use_cache=False, return_dict=True).logits
        shifted_logits = logits[:, :-1, :].to(torch.float32)
        labels = batch[:, 1:]
        loss = F.cross_entropy(
            shifted_logits.reshape(-1, shifted_logits.shape[-1]),
            labels.reshape(-1),
            reduction="sum",
        )
        if not torch.isfinite(loss):
            raise FloatingPointError("non-finite WikiText-2 NLL")
        total_nll += float(loss.detach().cpu())
        scoring_tokens += int(labels.numel())
        del batch, logits, shifted_logits, labels, loss
        print(
            f"[ppl] blocks {min(start + batch_size, block_count)}/{block_count}",
            flush=True,
        )
    avg_nll = total_nll / scoring_tokens
    return {
        "task": "wikitext2",
        "kind": "ppl",
        "primary_metric": "token_perplexity",
        "value": math.exp(avg_nll),
        "avg_nll": avg_nll,
        "raw_token_count": raw_tokens,
        "block_size": block_size,
        "available_complete_blocks": available_blocks,
        "evaluated_blocks": block_count,
        "tokens_in_evaluated_blocks": block_count * block_size,
        "scoring_tokens": scoring_tokens,
        "discarded_tail_tokens": raw_tokens - available_blocks * block_size,
        "unscored_block_initial_tokens": block_count,
        "elapsed_sec": time.time() - started,
        "full_stream": limit is None,
        "non_overlapping": True,
        "tail_policy": "drop_incomplete_block",
    }


def main() -> None:
    args = parse_args()
    if args.allow_format_errors and args.case not in {
        "v5_attention",
        "v5_mlp",
        "v5_mlp_down_s32_ablation",
        "v5",
        "v5_down_s32_ablation",
    }:
        raise ValueError(
            "--allow-format-errors is only valid with a hardware V5 case"
        )
    args.output = args.output.resolve()
    args.model = args.model.resolve()
    model_spec = get_model_spec(args.model)
    model_identity = load_model_identity(args.model_identity, args.model)
    task_names = [part.strip() for part in args.tasks.split(",") if part.strip()]
    invalid = set(task_names) - (set(TASK_ORDER) | {"wikitext2"})
    if invalid:
        raise ValueError(f"unsupported tasks: {sorted(invalid)}")
    if len(task_names) != len(set(task_names)):
        raise ValueError("duplicate task in --tasks")
    limit = None if args.limit <= 0 else args.limit
    protocol = validate_protocol(args.protocol, args.case, limit)
    context_length = int(protocol["context_length"])
    configure_reproducibility(args.seed)
    versions = package_versions()
    ensure_evaluator_version(versions)
    started = time.time()
    state_base = {
        "schema": "scalellm_literature_aligned_worker_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "device": args.device,
        "gpu_name": torch.cuda.get_device_name(torch.device(args.device)),
        "model": str(args.model),
        "model_spec": model_spec.to_dict(),
        "model_identity": model_identity,
        "case": args.case,
        "protocol": protocol,
        "tasks": task_names,
        "limit": limit,
        "versions": versions,
        "seed": args.seed,
        "runtime_args": {
            "batch_size": args.batch_size,
            "ppl_batch_size": args.ppl_batch_size,
            "allow_format_errors": args.allow_format_errors,
            "node_trace_layers": args.node_trace_layers,
            "node_trace_max_calls": args.node_trace_max_calls,
        },
        "tokenizer_boundary_policy": {
            "name": "fixed_context_independent_continuation_fallback_v1",
            "stock_lm_eval_path_when_prefix_stable": True,
            "fallback_add_special_tokens": False,
            "applied_to_cases": list(FIVE_CONFIG_CASES)
            + [
                "v5_attention",
                "v5_mlp",
                "v5_mlp_down_s32_ablation",
                "v5_mlp_down_s32_shift12_ablation",
                "v5",
                "v5_down_s32_ablation",
                "v5_algorithm",
            ],
        },
    }
    atomic_json(args.output / "run_state.json", {**state_base, "status": "loading_model"})
    try:
        acc_tasks = [task for task in task_names if task != "wikitext2"]
        sources = data_manifest(
            acc_tasks,
            include_wikitext="wikitext2" in task_names,
        )
        model, tokenizer, method, audit = load_model(args)
        if args.case in QUANTIZED_CASE_SPECS:
            validate_quantized_summary(method, model_spec, args.case)
        atomic_json(
            args.output / "run_state.json",
            {**state_base, "status": "evaluating", "method": method, "data": sources},
        )
        rows: list[dict[str, Any]] = []
        raw_lm_eval: dict[str, Any] | None = None
        truncation: dict[str, Any] = {}
        if acc_tasks:
            raw_lm_eval, truncation, acc_rows = run_acc(
                model=model,
                tokenizer=tokenizer,
                tasks=acc_tasks,
                context_length=context_length,
                batch_size=args.batch_size,
                limit=limit,
                seed=args.seed,
            )
            rows.extend(acc_rows)
        if "wikitext2" in task_names:
            rows.append(
                run_ppl(
                    model=model,
                    tokenizer=tokenizer,
                    device=torch.device(args.device),
                    block_size=context_length,
                    batch_size=args.ppl_batch_size,
                    limit=limit,
                )
            )
        audit_result = audit.collect() if audit is not None else None
        linear_audit_result = (
            audit.collect_linear() if audit is not None else None
        )
        node_trace_result = (
            audit.node_trace.collect()
            if audit is not None and audit.node_trace is not None
            else None
        )
        format_errors = (
            int(audit_result.get("linear_total_shift_format_error", 0))
            if audit_result is not None
            else 0
        )
        if args.case in QUANTIZED_CASE_SPECS:
            hardware_status = "not_applicable_algorithm_reference"
            status = "complete"
        elif args.case == "v5_algorithm":
            hardware_status = "software_reference_not_hardware"
            status = "complete"
        elif args.case in {
            "v5_mlp_down_s32_ablation",
            "v5_mlp_down_s32_shift12_ablation",
            "v5_down_s32_ablation",
        }:
            hardware_status = "diagnostic_ablation_not_hardware"
            status = "complete"
        else:
            hardware_status = "invalid_format_error" if format_errors else "valid"
            status = (
                "complete_invalid_format_error"
                if hardware_status != "valid"
                else "complete"
            )
        manifest = {
            **state_base,
            "status": status,
            "hardware_contract_status": hardware_status,
            "elapsed_sec": time.time() - started,
            "method": method,
            "data": sources,
            "truncation_audit": truncation,
            "hardware_audit": audit_result,
            "hardware_audit_by_module": linear_audit_result,
            "node_trace": node_trace_result,
            "results": rows,
            "lm_eval_raw": raw_lm_eval,
        }
        atomic_json(args.output / "manifest.json", manifest)
        atomic_json(
            args.output / "run_state.json",
            {
                **state_base,
                "status": status,
                "hardware_contract_status": hardware_status,
                "elapsed_sec": time.time() - started,
                "completed_tasks": task_names,
            },
        )
        print(json.dumps({"status": status, "results": rows}, default=str), flush=True)
    except Exception as exc:
        failure = {
            **state_base,
            "status": "failed",
            "elapsed_sec": time.time() - started,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        atomic_json(args.output / "run_state.json", failure)
        atomic_json(args.output / "failure.json", failure)
        raise
    finally:
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
