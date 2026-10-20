#!/usr/bin/env python3
"""Generate one frozen GSM8K model/case/stage on a single CUDA device.

Every invocation owns a new attempt directory.  Completed rows from previous
attempts can be imported only after exact execution-identity comparison.  The
worker deliberately never retries generation errors or changes the protocol.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import gc
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import time
import traceback
from typing import Any

from gsm8k_protocol import (DEFAULT_PLAN, INTEGRITY_CONTRACT_ID, atomic_json, canonical_hash,
                            integrity_contract_id, load_plan, prepare_requests, score_response,
                            sha256_file, validate_integrity_evidence)
from six_model_matrix import FIVE_CONFIG_CASES, get_model_spec, validate_quantized_summary

THIS_DIR = Path(__file__).resolve().parent
MANIFEST_SCHEMA = "scalellm_gsm8k_worker_manifest_v1"
ROW_SCHEMA = "scalellm_gsm8k_generation_v1"
VERIFICATION_CONTRACT_ID = "native_cache_call_parity_v2"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--stage", choices=("smoke", "pilot", "formal"), required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--case", choices=FIVE_CONFIG_CASES, required=True)
    parser.add_argument("--model-identity", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--context-length", type=int, default=8192)
    parser.add_argument("--max-gen-toks", type=int)
    parser.add_argument("--seed", type=int, default=20260913)
    parser.add_argument("--resume-from", type=Path, action="append", default=[])
    parser.add_argument("--verify-generation", action="store_true",
                        help="Two fixed train prompts: cache/logits and in-process repeat checks.")
    return parser.parse_args(argv)


def validate_args(args: argparse.Namespace, plan: dict[str, Any]) -> None:
    protocol = plan["protocol"]
    expected_tokens = 64 if args.stage == "smoke" else int(protocol["max_gen_toks"])
    if args.max_gen_toks is None:
        args.max_gen_toks = expected_tokens
    if args.max_gen_toks != expected_tokens:
        raise ValueError(f"generation budget differs from frozen stage: {expected_tokens}")
    if args.context_length != int(protocol["max_sequence_length"]):
        raise ValueError("context length differs from plan; use a separately versioned plan")
    if args.seed != int(protocol["seed"]):
        raise ValueError("seed differs from frozen protocol")
    if args.batch_size != 1 or int(protocol["batch_size"]) != 1:
        raise ValueError("this worker implements frozen batch=1 only")
    if not args.device.startswith("cuda:"):
        raise ValueError("worker requires an explicit single CUDA device")
    if args.max_gen_toks <= 0 or args.context_length <= args.max_gen_toks:
        raise ValueError("invalid context/generation token budgets")
    required = {"do_sample": False, "num_beams": 1, "num_return_sequences": 1,
                "repeats": 1, "num_fewshot": 5, "apply_chat_template": False,
                "system_prompt": "", "use_cache": True, "dtype": "bfloat16",
                "attention_implementation": "eager", "tf32": False,
                "repetition_penalty": 1.0, "no_repeat_ngram_size": 0}
    for key, expected in required.items():
        if protocol.get(key) != expected:
            raise ValueError(f"unsupported protocol {key}={protocol.get(key)!r}")
    if protocol.get("verification_contract_id") != VERIFICATION_CONTRACT_ID:
        raise ValueError("v2 worker requires protocol.verification_contract_id=native_cache_call_parity_v2")
    if integrity_contract_id(plan) is not None and args.stage in {"smoke", "pilot"} and not args.verify_generation:
        raise ValueError("weight-integrity smoke/pilot requires the unchanged generation verification")
    if integrity_contract_id(plan) is not None and args.resume_from:
        raise ValueError("weight-integrity attempts must redo a whole group; row resume is not qualified")


def verify_checkpoint(model: Path, identity_path: Path) -> dict[str, Any]:
    """Rehash every identity file, including weight shards, before loading it."""
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    spec = get_model_spec(model)
    if identity.get("schema") != "scalellm_checkpoint_identity_v1":
        raise ValueError("unsupported checkpoint identity schema")
    if Path(identity["resolved_path"]).resolve() != model.resolve():
        raise ValueError("checkpoint identity path mismatch")
    if identity.get("checkpoint_name") != spec.name:
        raise ValueError("checkpoint identity name mismatch")
    entries = identity.get("files", [])
    names = [item["name"] for item in entries]
    if not entries or names != sorted(set(names)):
        raise ValueError("checkpoint identity files must be nonempty, sorted and unique")
    actual_names = sorted(path.name for path in model.iterdir() if path.is_file())
    if names != actual_names:
        raise ValueError("checkpoint file inventory changed")
    if not any(Path(name).suffix in {".safetensors", ".bin"} for name in names):
        raise ValueError("checkpoint identity lacks weights")
    for item in entries:
        if Path(item["name"]).name != item["name"]:
            raise ValueError("checkpoint identity contains nonlocal filename")
        path = model / item["name"]
        if path.stat().st_size != item["bytes"] or sha256_file(path) != item["sha256"]:
            raise ValueError(f"checkpoint content changed: {path.name}")
    # prepare_model_identity uses the stdlib ASCII default for this fingerprint.
    fingerprint = hashlib.sha256(json.dumps(entries, sort_keys=True,
                                          separators=(",", ":")).encode()).hexdigest()
    if fingerprint != identity.get("fingerprint_sha256"):
        raise ValueError("checkpoint identity fingerprint is inconsistent")
    if identity.get("file_count") != len(entries) or identity.get("total_bytes") != sum(
            item["bytes"] for item in entries):
        raise ValueError("checkpoint identity totals are inconsistent")
    return identity


def tokenizer_identity(tokenizer: Any, model_identity: dict[str, Any]) -> dict[str, Any]:
    return {"class": type(tokenizer).__module__ + "." + type(tokenizer).__name__,
            "vocab_sha256": canonical_hash(tokenizer.get_vocab()),
            "special_tokens_map": tokenizer.special_tokens_map,
            "bos_token_id": tokenizer.bos_token_id, "eos_token_id": tokenizer.eos_token_id,
            "pad_token_id": tokenizer.pad_token_id,
            "add_bos_token": getattr(tokenizer, "add_bos_token", None),
            "padding_side": tokenizer.padding_side,
            "checkpoint_files": [entry for entry in model_identity["files"]
                                 if "token" in entry["name"] or entry["name"] == "special_tokens_map.json"]}


def encode_prompt(tokenizer: Any, prompt: str) -> list[int]:
    # HFLM.tok_encode(add_special_tokens=None, add_bos_token=None) uses native
    # tokenizer defaults. Raw GSM8K prompts never begin with a special BOS string.
    return list(tokenizer.encode(prompt, truncation=False))


def audit_prompts(requests: list[dict[str, Any]], tokenizer: Any, context: int,
                  max_new: int, max_prompt: int) -> tuple[dict[str, list[int]], dict[str, Any]]:
    encoded: dict[str, list[int]] = {}
    lengths: list[int] = []
    for request in requests:
        sample = request["sample_id"]
        if sample in encoded:
            raise ValueError(f"duplicate request ID {sample}")
        ids = encode_prompt(tokenizer, request["prompt"])
        if not ids or len(ids) > max_prompt or len(ids) + max_new > context:
            raise ValueError(f"prompt token budget violation for {sample}: {len(ids)}")
        encoded[sample] = ids
        lengths.append(len(ids))
    return encoded, {"n_requests": len(encoded), "input_truncation": False,
                     "min_input_tokens": min(lengths), "max_input_tokens": max(lengths),
                     "mean_input_tokens": statistics.mean(lengths),
                     "input_token_ids_sha256": canonical_hash(encoded)}


def resolve_generation(model: Any, tokenizer: Any, max_new: int) -> tuple[Any, dict[str, Any]]:
    from transformers import GenerationConfig

    checkpoint = model.generation_config.to_dict()
    eos = checkpoint.get("eos_token_id")
    if eos is None:
        eos = tokenizer.eos_token_id
    eos_ids = [int(eos)] if isinstance(eos, int) else [int(x) for x in (eos or [])]
    if not eos_ids or tokenizer.pad_token_id is None:
        raise ValueError("checkpoint must resolve nonempty EOS IDs and PAD ID")
    # Construct fresh defaults so checkpoint sampling/penalty/forced-token settings
    # cannot silently affect the frozen greedy protocol.
    config = GenerationConfig(
        do_sample=False, num_beams=1, num_beam_groups=1, num_return_sequences=1,
        max_new_tokens=max_new, min_length=0,
        repetition_penalty=1.0, encoder_repetition_penalty=1.0,
        no_repeat_ngram_size=0, encoder_no_repeat_ngram_size=0, length_penalty=1.0,
        eos_token_id=eos_ids, pad_token_id=int(tokenizer.pad_token_id),
        bos_token_id=tokenizer.bos_token_id, forced_bos_token_id=None,
        forced_eos_token_id=None, use_cache=True, cache_implementation="dynamic",
        return_dict_in_generate=True, output_scores=False, output_logits=False,
        remove_invalid_values=False, renormalize_logits=False,
    )
    return config, {"checkpoint_generation_config": checkpoint,
                    "effective_generation_config": config.to_dict(), "eos_token_ids": eos_ids,
                    "pad_token_id": tokenizer.pad_token_id,
                    "temperature_argument_passed": False, "use_cache": True,
                    "kv_cache": "native_dynamic_unquantized", "dtype": "bfloat16",
                    "attention_implementation": "eager", "tf32": False}


def trim_scoring_text(text: str, stops: list[str]) -> tuple[str, str | None]:
    matches = [(text.find(stop), stop) for stop in stops if stop and stop in text]
    if not matches:
        return text, None
    position, stop = min(matches, key=lambda item: item[0])
    return text[:position], stop


def append_jsonl(handle: Any, value: dict[str, Any]) -> None:
    handle.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")
    handle.flush()
    os.fsync(handle.fileno())


def read_complete_jsonl(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """An unterminated tail is uncommitted; any earlier corruption is fatal."""
    raw = path.read_bytes()
    lines = raw.splitlines(keepends=True)
    rows: list[dict[str, Any]] = []
    ignored = None
    for index, line in enumerate(lines):
        if not line.endswith(b"\n"):
            ignored = {"path": str(path), "line": index + 1,
                       "bytes": len(line), "reason": "uncommitted_unterminated_tail"}
            continue
        try:
            row = json.loads(line)
        except (ValueError, UnicodeError) as exc:
            raise ValueError(f"corrupt committed JSONL row {path}:{index + 1}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"nonobject JSONL row {path}:{index + 1}")
        rows.append(row)
    return rows, ignored


def validate_completed_row(row: dict[str, Any], request: dict[str, Any],
                           identity_sha256: str, tokenizer: Any | None = None,
                           input_ids: list[int] | None = None) -> None:
    if row.get("schema") != ROW_SCHEMA or row.get("status") != "complete":
        raise ValueError("resume row is not a completed generation")
    if row.get("identity_sha256") != identity_sha256:
        raise ValueError("resume row identity mismatch")
    for key in ("sample_id", "row_index", "split", "prompt_sha256", "gold",
                "fewshot_train_indices"):
        if row.get(key) != request[key]:
            raise ValueError(f"resume row request mismatch: {key}")
    if row.get("question_sha256") != hashlib.sha256(request["question"].encode()).hexdigest():
        raise ValueError("resume question hash mismatch")
    ids = row.get("new_token_ids")
    if not isinstance(ids, list) or any(type(token) is not int or token < 0 for token in ids):
        raise ValueError("resume token IDs are invalid")
    if row.get("output_tokens") != len(ids):
        raise ValueError("resume token count mismatch")
    if not isinstance(row.get("raw_text"), str) or not isinstance(row.get("scoring_text"), str):
        raise ValueError("resume continuation text missing")
    if row.get("stop_reason") not in {"eos", "stop_string", "length", "model_stop"}:
        raise ValueError("resume stop reason missing")
    if type(row.get("length_capped")) is not bool:
        raise ValueError("resume length cap flag missing")
    if row.get("length_capped") and row["stop_reason"] != "length":
        raise ValueError("resume length cap disagrees with stop reason")
    elapsed = row.get("elapsed_seconds")
    if not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError("resume timing missing/invalid")
    if not isinstance(row.get("peak_memory_allocated_bytes"), int):
        raise ValueError("resume memory evidence missing")
    if row.get("use_cache") is not True:
        raise ValueError("resume row does not establish cache-on generation")
    if input_ids is not None and (row.get("input_tokens") != len(input_ids) or
                                 row.get("input_token_ids_sha256") != canonical_hash(input_ids)):
        raise ValueError("resume input token identity mismatch")
    if tokenizer is not None:
        decoded = tokenizer.decode(ids, skip_special_tokens=False,
                                   clean_up_tokenization_spaces=False)
        scoring_decoded = tokenizer.decode(ids, skip_special_tokens=True)
        scoring, _ = trim_scoring_text(scoring_decoded, row["stop_strings"])
        if decoded != row["raw_text"] or scoring != row["scoring_text"]:
            raise ValueError("resume text is inconsistent with saved token IDs")


def import_resumable(attempts: list[Path], identity_sha256: str,
                     requests: list[dict[str, Any]], tokenizer: Any | None = None,
                     encoded: dict[str, list[int]] | None = None
                     ) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    expected = {request["sample_id"]: request for request in requests}
    imported: dict[str, dict[str, Any]] = {}
    provenance = []
    for attempt in attempts:
        attempt = attempt.resolve()
        manifest = json.loads((attempt / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("schema") != MANIFEST_SCHEMA or manifest.get("identity_sha256") != identity_sha256:
            raise ValueError(f"resume execution identity mismatch: {attempt}")
        if canonical_hash(manifest.get("identity")) != identity_sha256:
            raise ValueError(f"resume manifest identity checksum mismatch: {attempt}")
        if manifest["identity"].get("integrity_contract_id") is not None:
            validate_integrity_evidence(attempt, manifest, manifest["identity"]["integrity_contract_id"],
                sample_ids=manifest.get("request_ids", []))
        generation_path = attempt / "generation.jsonl"
        if not generation_path.exists() and manifest.get("n_completed", 0) == 0:
            provenance.append({"attempt": str(attempt), "imported_rows": 0,
                               "reason": "attempt_failed_before_committed_generation",
                               "manifest_sha256": sha256_file(attempt / "manifest.json")})
            continue
        artifact_digest = manifest.get("artifacts", {}).get("generation.jsonl")
        if artifact_digest is not None and sha256_file(generation_path) != artifact_digest:
            raise ValueError(f"resume generation artifact checksum mismatch: {attempt}")
        rows, ignored = read_complete_jsonl(attempt / "generation.jsonl")
        local_ids = set()
        count = 0
        for row in rows:
            sample = row.get("sample_id")
            if sample not in expected:
                raise ValueError(f"unexpected resume sample {sample}")
            if sample in local_ids:
                raise ValueError(f"duplicate sample in one attempt: {sample}")
            local_ids.add(sample)
            if row.get("status") == "error":
                continue
            validate_completed_row(row, expected[sample], identity_sha256, tokenizer,
                                   None if encoded is None else encoded[sample])
            generation = manifest["identity"].get("generation", {})
            if generation:
                if row.get("stop_strings") != generation["stop_strings"] or row.get("eos_token_ids") != generation["eos_token_ids"]:
                    raise ValueError("resume row stop configuration mismatch")
                maximum = generation["effective_generation_config"]["max_new_tokens"]
                if row["output_tokens"] > maximum or (row["length_capped"] and row["output_tokens"] != maximum):
                    raise ValueError("resume row generation length mismatch")
            if sample in imported:
                # Across attempts, identical copied evidence is accepted; any
                # disagreement is fatal, even when both answers would score alike.
                ignore = {"source_attempt", "imported_from_attempt"}
                old = {k: v for k, v in imported[sample].items() if k not in ignore}
                new = {k: v for k, v in row.items() if k not in ignore}
                if old != new:
                    raise ValueError(f"conflicting completed answers for {sample}")
                continue
            imported[sample] = {**row, "imported_from_attempt": str(attempt)}
            count += 1
        provenance.append({"attempt": str(attempt), "manifest_sha256": sha256_file(attempt / "manifest.json"),
                           "generation_sha256": sha256_file(attempt / "generation.jsonl"),
                           "imported_rows": count, "ignored_tail": ignored})
    return imported, provenance


def score_row(row: dict[str, Any]) -> dict[str, Any]:
    return {"sample_id": row["sample_id"], "identity_sha256": row["identity_sha256"],
            "scoring_text": row["scoring_text"], "gold": row["gold"],
            **score_response(row["scoring_text"], row["gold"])}


def make_summary(rows: list[dict[str, Any]], n_expected: int, stage: str,
                 elapsed_seconds: float, state: str) -> dict[str, Any]:
    completed = [row for row in rows if row["status"] == "complete"]
    scores = [score_row(row) for row in completed]
    correct = sum(bool(score["correct_strict"]) for score in scores)
    flexible = sum(bool(score["correct_flexible"]) for score in scores)
    lengths = [row["output_tokens"] for row in completed]
    times = [row["elapsed_seconds"] for row in completed]
    full = (state == "complete" and stage == "formal" and n_expected == 1319 and
            len(completed) == 1319 and {row["sample_id"] for row in completed} ==
            {f"test:{i:04d}" for i in range(1319)})
    return {"schema": "scalellm_gsm8k_worker_summary_v1", "state": state, "stage": stage,
            "n_expected": n_expected, "n_formal_expected": 1319, "n_completed": len(completed),
            "n_errors": sum(row["status"] == "error" for row in rows), "full_split": full,
            "primary_metric": "exact_match,strict-match", "correct_strict": correct,
            "correct_flexible": flexible,
            # Full expected denominator is retained while execution is partial;
            # partial accuracy is explicitly ineligible for the final table.
            "exact_match,strict-match": correct / n_expected,
            "exact_match,flexible-extract": flexible / n_expected,
            "invalid_strict": sum(bool(score["invalid_strict"]) for score in scores),
            "length_capped": sum(row["length_capped"] for row in completed),
            "output_tokens": sum(lengths), "mean_output_tokens": statistics.mean(lengths) if lengths else None,
            "max_output_tokens": max(lengths, default=0),
            "generation_seconds": sum(times), "elapsed_seconds": elapsed_seconds,
            "mean_seconds_per_example": statistics.mean(times) if times else None,
            "p95_seconds_per_example": sorted(times)[max(0, math.ceil(.95 * len(times)) - 1)] if times else None,
            "tokens_per_generation_second": sum(lengths) / sum(times) if sum(times) else None,
            "peak_memory_allocated_bytes": max((row["peak_memory_allocated_bytes"] for row in completed), default=0),
            "peak_memory_reserved_bytes": max((row.get("peak_memory_reserved_bytes", 0) for row in completed), default=0)}


def generate_one(model: Any, tokenizer: Any, request: dict[str, Any], ids: list[int],
                 config: Any, stops: list[str], device: str, identity_sha256: str,
                 source_attempt: Path) -> dict[str, Any]:
    import torch
    from lm_eval.models.utils_hf import stop_sequences_criteria

    if config.use_cache is not True:
        raise ValueError("generation configuration must enable native KV cache")
    inputs = torch.tensor([ids], dtype=torch.long, device=device)
    torch.cuda.synchronize(device)
    torch.cuda.reset_peak_memory_stats(device)
    started = time.perf_counter()
    with torch.inference_mode():
        result = model.generate(input_ids=inputs, attention_mask=torch.ones_like(inputs),
                                generation_config=copy.deepcopy(config),
                                stopping_criteria=stop_sequences_criteria(tokenizer, stops, len(ids), 1))
    torch.cuda.synchronize(device)
    elapsed = time.perf_counter() - started
    sequences = result.sequences
    if sequences.shape[0] != 1 or sequences.shape[1] < len(ids) or not torch.equal(sequences[0, :len(ids)], inputs[0]):
        raise RuntimeError("generation did not preserve the full prompt prefix")
    new_ids = sequences[0, len(ids):].tolist()
    raw_text = tokenizer.decode(new_ids, skip_special_tokens=False, clean_up_tokenization_spaces=False)
    # HFLM.tok_decode defaults skip_special_tokens=True, then removes stop strings.
    decoded = tokenizer.decode(new_ids, skip_special_tokens=True)
    scoring_text, stop = trim_scoring_text(decoded, stops)
    eos = bool(new_ids and new_ids[-1] in config.eos_token_id)
    at_limit = len(new_ids) >= config.max_new_tokens
    reason = "eos" if eos else "stop_string" if stop is not None else "length" if at_limit else "model_stop"
    return {"schema": ROW_SCHEMA, "status": "complete", "identity_sha256": identity_sha256,
            "sample_id": request["sample_id"], "row_index": request["row_index"], "split": request["split"],
            "question_sha256": hashlib.sha256(request["question"].encode()).hexdigest(),
            "prompt_sha256": request["prompt_sha256"], "fewshot_train_indices": request["fewshot_train_indices"],
            "input_tokens": len(ids), "input_token_ids_sha256": canonical_hash(ids),
            "new_token_ids": new_ids, "output_tokens": len(new_ids), "raw_text": raw_text,
            "decoded_text_skip_special_tokens": decoded, "scoring_text": scoring_text,
            "stop_reason": reason, "matched_stop_string": stop,
            "stop_strings": stops, "eos_token_ids": config.eos_token_id,
            "length_capped": reason == "length", "generation_limit_reached": at_limit,
            "gold": request["gold"], "elapsed_seconds": elapsed,
            "peak_memory_allocated_bytes": torch.cuda.max_memory_allocated(device),
            "peak_memory_reserved_bytes": torch.cuda.max_memory_reserved(device),
            "use_cache": True, "source_attempt": str(source_attempt), "completed_at": now(), "error": None}


def cache_tensors(cache: Any) -> list[tuple[Any, Any]]:
    if cache is None:
        return []
    if hasattr(cache, "layers"):
        return [(layer.keys, layer.values) for layer in cache.layers]
    if isinstance(cache, (list, tuple)):
        return [(layer[0], layer[1]) for layer in cache]
    return []


def snapshot_cache(cache: Any) -> list[tuple[Any, Any]]:
    return [(key.detach().clone(), value.detach().clone()) for key, value in cache_tensors(cache)]


def caches_disjoint(left: Any, right: Any) -> bool:
    def pointers(cache: Any) -> set[tuple[str, int]]:
        return {(str(tensor.device), tensor.untyped_storage().data_ptr())
                for pair in cache_tensors(cache) for tensor in pair if tensor is not None and tensor.numel()}
    return left is not right and not (pointers(left) & pointers(right))


def inspect_cache(cache: Any, expected_length: int, layers: int,
                  previous: list[tuple[Any, Any]]) -> dict[str, Any]:
    import torch
    pairs = cache_tensors(cache)
    details = []
    for index, (key, value) in enumerate(pairs):
        tensor_ok = isinstance(key, torch.Tensor) and isinstance(value, torch.Tensor)
        shape_ok = tensor_ok and key.ndim == value.ndim == 4 and key.shape == value.shape and key.shape[0] == 1
        length_ok = bool(shape_ok and key.shape[-2] == expected_length)
        finite = bool(tensor_ok and torch.isfinite(key).all().item() and torch.isfinite(value).all().item())
        prefix_ok = True
        if previous:
            prefix_ok = index < len(previous) and shape_ok
            if prefix_ok:
                old_key, old_value = previous[index]
                old_length = old_key.shape[-2]
                prefix_ok = (old_length < expected_length and
                    torch.equal(key[..., :old_length, :], old_key) and
                    torch.equal(value[..., :old_length, :], old_value))
        declared = None
        if hasattr(cache, "get_seq_length"):
            declared = int(cache.get_seq_length(index))
            length_ok = length_ok and declared == expected_length
        details.append({"layer": index, "key_shape": list(key.shape) if tensor_ok else None,
                        "value_shape": list(value.shape) if tensor_ok else None,
                        "dtype": str(key.dtype) if tensor_ok else None, "length_valid": bool(length_ok),
                        "declared_length": declared, "finite": finite,
                        "old_prefix_unchanged": bool(prefix_ok),
                        "kv_elements_checked": int(key.numel() + value.numel()) if tensor_ok else 0})
    valid = len(pairs) == layers and layers > 0 and (not previous or len(previous) == layers)
    valid = valid and all(row["length_valid"] and row["finite"] and row["old_prefix_unchanged"] for row in details)
    return {"valid": bool(valid), "expected_length": expected_length,
            "expected_layers": layers, "layers": details}


def logits_comparison(left: Any, right: Any) -> dict[str, Any]:
    import torch
    # Native generate exposes float32 raw logits; native model output is BF16.
    # Casting BF16 to FP32 is exact and allows equality over the same values.
    left, right = left.float(), right.float()
    finite = bool(torch.isfinite(left).all().item() and torch.isfinite(right).all().item())
    same_shape = left.shape == right.shape
    exact = bool(same_shape and finite and torch.equal(left, right))
    def digest(value: Any) -> str:
        return hashlib.sha256(value.detach().contiguous().cpu().view(torch.uint8).numpy().tobytes()).hexdigest()
    return {"exact": exact, "finite": finite, "shape": list(left.shape),
            "elements_compared": left.numel(), "left_sha256": digest(left), "right_sha256": digest(right),
            "max_abs_difference": float((left-right).abs().max().item()) if finite and same_shape else None}


def verify_generation(model: Any, tokenizer: Any, requests: list[dict[str, Any]],
                      config: Any, device: str, seed: int,
                      evidence_path: Path | None = None) -> dict[str, Any]:
    """Validate native cached call parity; cache-off differences stay diagnostic."""
    import torch
    from run_eval_worker import configure_reproducibility
    records: list[dict[str, Any]] = []
    counts: dict[str, dict[str, int]] = {}
    hooks = []
    report: dict[str, Any] = {"schema": "scalellm_gsm8k_generation_verification_v2",
        "verification_contract_id": VERIFICATION_CONTRACT_ID, "state": "running", "passed": False,
        "records": records, "qdq_projection_calls": counts,
        "diagnostic_policy": "cache-off greedy16 and allclose(atol=.125,rtol=.01) are recorded without gating native cache parity",
        "independent_process_repeatability": "pending_scheduler_comparison"}
    def persist() -> None:
        if evidence_path is not None:
            atomic_json(evidence_path, report)
    for name, module in model.named_modules():
        if getattr(module, "_scalellm_gsm8k_qdq", False):
            counts[name] = {"prefill": 0, "decode": 0}
            def count_call(_module: Any, arguments: Any, _output: Any, key: str = name) -> None:
                value = arguments[0]
                counts[key]["decode" if value.ndim >= 3 and value.shape[-2] == 1 else "prefill"] += 1
            hooks.append(module.register_forward_hook(count_call))
    try:
        for request in requests[:2]:
            ids = encode_prompt(tokenizer, request["prompt"])
            inputs = torch.tensor([ids], dtype=torch.long, device=device)
            def generate(cache: bool, count: int, output_logits: bool = False) -> Any:
                cfg = copy.deepcopy(config)
                cfg.max_new_tokens, cfg.use_cache, cfg.output_logits = count, cache, output_logits
                if not cache:
                    cfg.cache_implementation = None
                configure_reproducibility(seed)
                with torch.inference_mode():
                    return model.generate(input_ids=inputs, attention_mask=torch.ones_like(inputs), generation_config=cfg)
            native = generate(True, 17, True)
            native_tokens = native.sequences[0, len(ids):].tolist()
            on = generate(True, 32).sequences[0, len(ids):].tolist()
            repeated = generate(True, 32).sequences[0, len(ids):].tolist()
            off = generate(False, 16).sequences[0, len(ids):].tolist()
            row: dict[str, Any] = {"sample_id": request["sample_id"], "prompt_sha256": request["prompt_sha256"],
                "input_tokens": len(ids), "native_generated_token_ids": native_tokens,
                "native_logits_count": len(native.logits), "repeatability_prefix_32_token_ids": on,
                "cache_on_32_token_ids": on, "repeat_32_token_ids": repeated, "cache_off_16_token_ids": off,
                "greedy_16_equal": on[:16] == off, "same_process_repeat_32_equal": on == repeated,
                "native_prefix_matches_32": native_tokens == on[:len(native_tokens)],
                "atol": .125, "rtol": .01, "steps": []}
            records.append(row)
            prefix, past = inputs, None
            expected_layers = int(model.config.num_hidden_layers)
            native_shape = inspect_cache(native.past_key_values, len(ids)+len(native_tokens)-1, expected_layers, [])
            max_diff, all_close, checked = 0., True, 0
            negative: dict[str, Any] = {"detected": None, "qualified": False, "status": "not_executed"}
            with torch.inference_mode():
                for index, native_logits in enumerate(native.logits):
                    before = snapshot_cache(past)
                    corrupted_logits, corrupt_independent = None, False
                    if index == len(native.logits)-1 and past is not None:
                        corrupted = copy.deepcopy(past)
                        corrupt_independent = caches_disjoint(past, corrupted)
                        if corrupt_independent:
                            for key, value in cache_tensors(corrupted):
                                key.zero_(); value.zero_()
                            corrupted_logits = model(input_ids=prefix[:, -1:], attention_mask=torch.ones_like(prefix),
                                past_key_values=corrupted, use_cache=True, logits_to_keep=1).logits[:, -1, :]
                    cached = model(input_ids=prefix if past is None else prefix[:, -1:],
                        past_key_values=past, attention_mask=torch.ones_like(prefix), use_cache=True, logits_to_keep=1)
                    left = cached.logits[:, -1, :]
                    current = inspect_cache(cached.past_key_values, len(ids)+index, expected_layers, before)
                    native_comparison = logits_comparison(left, native_logits)
                    rebuilt, transitions = None, []
                    for segment_index in range(index+1):
                        old = snapshot_cache(rebuilt)
                        segment = inputs if segment_index == 0 else native.sequences[:, len(ids)+segment_index-1:len(ids)+segment_index]
                        rebuilt_output = model(input_ids=segment,
                            attention_mask=torch.ones((1, len(ids)+segment_index), dtype=torch.long, device=device),
                            past_key_values=rebuilt, use_cache=True, logits_to_keep=1)
                        rebuilt = rebuilt_output.past_key_values
                        transition = inspect_cache(rebuilt, len(ids)+segment_index, expected_layers, old)
                        transitions.append({"segment": segment_index, "expected_length": len(ids)+segment_index,
                                            "cache_structure_valid": transition["valid"]})
                    rebuilt_comparison = logits_comparison(left, rebuilt_output.logits[:, -1, :])
                    manual_pairs, rebuilt_pairs = cache_tensors(cached.past_key_values), cache_tensors(rebuilt)
                    kv_layers = []
                    for layer_index, (manual_pair, rebuilt_pair) in enumerate(zip(manual_pairs, rebuilt_pairs)):
                        key_exact = bool(manual_pair[0].dtype == rebuilt_pair[0].dtype and torch.equal(manual_pair[0], rebuilt_pair[0]))
                        value_exact = bool(manual_pair[1].dtype == rebuilt_pair[1].dtype and torch.equal(manual_pair[1], rebuilt_pair[1]))
                        kv_layers.append({"layer": layer_index, "all_elements_compared": True,
                            "key_exact": key_exact, "value_exact": value_exact,
                            "key_shape": list(manual_pair[0].shape), "value_shape": list(manual_pair[1].shape),
                            "key_elements": manual_pair[0].numel(), "value_elements": manual_pair[1].numel()})
                    independent = caches_disjoint(cached.past_key_values, rebuilt)
                    native_independent = caches_disjoint(cached.past_key_values, native.past_key_values)
                    structure_valid = bool(current["valid"] and native_shape["valid"] and independent and native_independent and
                        all(transition["cache_structure_valid"] for transition in transitions))
                    kv_exact = len(kv_layers) == expected_layers and all(layer["key_exact"] and layer["value_exact"] for layer in kv_layers)
                    step = {"step": index, "prefix_tokens": len(ids)+index,
                        "native_generate_exact": native_comparison["exact"],
                        "rebuilt_cache_exact": rebuilt_comparison["exact"] and kv_exact,
                        "cache_structure_valid": structure_valid, "native_logits": native_comparison,
                        "finite": bool(native_comparison["finite"] and rebuilt_comparison["finite"] and
                            all(layer["finite"] for layer in current["layers"]) and
                            all(layer["finite"] for layer in transition["layers"])),
                        "rebuilt_logits": rebuilt_comparison, "kv_layers": kv_layers,
                        "manual_cache": current, "rebuild_transitions": transitions,
                        "manual_rebuilt_storage_disjoint": independent, "manual_native_storage_disjoint": native_independent}
                    row["steps"].append(step)
                    if index in {0, len(native.logits)-1}:
                        plain = model(input_ids=prefix, attention_mask=torch.ones_like(prefix), use_cache=False, logits_to_keep=1)
                        right = plain.logits[:, -1, :].float()
                        diagnostic_finite = bool(torch.isfinite(left).all().item() and torch.isfinite(right).all().item())
                        difference = float((left.float()-right).abs().max().item()) if diagnostic_finite else None
                        step["cache_off_diagnostic"] = {"finite": diagnostic_finite, "max_abs_difference": difference,
                            "allclose": bool(diagnostic_finite and torch.allclose(left.float(), right, atol=.125, rtol=.01))}
                        if difference is not None:
                            max_diff = max(max_diff, difference)
                        all_close &= step["cache_off_diagnostic"]["allclose"]
                        checked += 1
                    if index == len(native.logits)-1:
                        if corrupted_logits is not None:
                            comparison = logits_comparison(left, corrupted_logits)
                            detected = comparison["finite"] and not comparison["exact"]
                            negative = {"detected": bool(detected), "qualified": bool(detected),
                                "status": "detected" if detected else "failed_to_detect_corruption",
                                "independent_storage": corrupt_independent, "comparison": comparison,
                                "corruption": "all previously cached K/V elements zeroed on an independent copy"}
                        elif past is None and len(native.logits) == 1 and len(native_tokens) == 1 and native_tokens[0] in config.eos_token_id:
                            eligible = step["native_generate_exact"] and step["rebuilt_cache_exact"] and step["cache_structure_valid"]
                            negative = {"detected": None, "qualified": bool(eligible),
                                "status": "not_applicable_early_eos_no_prior_cache", "prior_cache_available": False}
                        else:
                            negative = {"detected": False, "qualified": False,
                                "status": "failed_cache_copy_alias_or_missing_prior_cache"}
                    past = cached.past_key_values
                    prefix = torch.cat((prefix, native.sequences[:, len(ids)+index:len(ids)+index+1]), dim=1)
                    persist()
                    del rebuilt, rebuilt_output
            steps_valid = len(row["steps"]) == min(17, len(native_tokens)) == len(native.logits) and bool(native_tokens)
            row.update({"native_generate_exact": bool(steps_valid and row["native_prefix_matches_32"] and all(s["native_generate_exact"] for s in row["steps"])),
                "rebuilt_cache_exact": bool(steps_valid and all(s["rebuilt_cache_exact"] for s in row["steps"])),
                "cache_structure_valid": bool(steps_valid and all(s["cache_structure_valid"] for s in row["steps"])),
                "negative_control_detected": negative["detected"], "negative_control_qualified": negative["qualified"],
                "negative_control_status": negative["status"], "negative_control": negative,
                "logits_max_abs_difference": max_diff, "logits_comparisons": checked, "logits_allclose": bool(all_close)})
            persist()
        coverage = all(count["prefill"] and count["decode"] for count in counts.values())
        gates = ("native_generate_exact", "rebuilt_cache_exact", "cache_structure_valid",
                 "negative_control_qualified", "same_process_repeat_32_equal")
        report.update({key: len(records) == 2 and all(row[key] for row in records) for key in gates})
        report["negative_control_detected"] = (None if any(row["negative_control_detected"] is None for row in records)
                                               else all(row["negative_control_detected"] for row in records))
        report.update(state="complete", all_qdq_projections_prefill_and_decode=bool(coverage),
                      passed=bool(coverage and all(report[key] for key in gates)))
        persist()
        return report
    except BaseException as exc:
        report.update(state="failed", error={"type": type(exc).__name__, "message": str(exc)}, passed=False)
        persist()
        raise
    finally:
        for hook in hooks:
            hook.remove()


def code_identity() -> dict[str, str]:
    from run_eval_worker import REFERENCE_QDQ_DIR
    from lm_eval.models import huggingface, utils, utils_hf
    paths = [THIS_DIR / name for name in ("run_gsm8k_worker.py", "gsm8k_protocol.py",
                                          "run_eval_worker.py", "six_model_matrix.py", "protocol.py",
                                          "gsm8k_weight_integrity.py")]
    paths += [REFERENCE_QDQ_DIR / "mlp4_method_inference.py",
              REFERENCE_QDQ_DIR.parent / "scale_code_linear" / "scalepath4_method_inference.py"]
    paths += [Path(inspect.getfile(module)) for module in (huggingface, utils, utils_hf)]
    return {str(path.resolve()): sha256_file(path) for path in paths}


def run(args: argparse.Namespace) -> None:
    # Never append into, truncate, or overwrite a previous attempt.
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    manifest: dict[str, Any] = {"schema": MANIFEST_SCHEMA, "state": "starting",
                               "started_at": now(), "pid": os.getpid(), "stage": args.stage,
                               "model": args.model.name, "case": args.case,
                               "output": str(args.output), "n_completed": 0}
    rows: list[dict[str, Any]] = []
    requests: list[dict[str, Any]] = []
    integrity = None
    def summarize(state: str) -> dict[str, Any]:
        summary = make_summary(rows, len(requests), args.stage, time.perf_counter() - started, state)
        summary.update({"model": args.model.name, "case": args.case,
                        "identity_sha256": manifest.get("identity_sha256"),
                        "model_load_attach_peak_memory_allocated_bytes": manifest.get("model_load_attach_peak_memory_allocated_bytes"),
                        "model_load_attach_peak_memory_reserved_bytes": manifest.get("model_load_attach_peak_memory_reserved_bytes")})
        if "integrity" in manifest:
            summary["integrity"] = manifest["integrity"]
        summary["peak_memory_allocated_bytes"] = max(summary["peak_memory_allocated_bytes"],
            manifest.get("model_load_attach_peak_memory_allocated_bytes", 0))
        summary["peak_memory_reserved_bytes"] = max(summary["peak_memory_reserved_bytes"],
            manifest.get("model_load_attach_peak_memory_reserved_bytes", 0))
        return summary
    atomic_json(args.output / "command.json", {"argv": sys.argv, "arguments": {
        key: [str(x) for x in value] if isinstance(value, list) else str(value) if isinstance(value, Path) else value
        for key, value in vars(args).items()}})
    atomic_json(args.output / "manifest.json", manifest)
    try:
        plan = load_plan(args.plan)
        validate_args(args, plan)
        requests = prepare_requests(args.plan, args.stage)
        args.model = args.model.resolve()
        model_identity = verify_checkpoint(args.model, args.model_identity)
        manifest["model_identity"] = model_identity
        manifest["checkpoint_content_verified_at"] = now()
        atomic_json(args.output / "manifest.json", manifest)
        import torch
        from run_eval_worker import (configure_reproducibility, ensure_evaluator_version,
                                     load_model, package_versions)
        torch.set_num_threads(2)
        torch.set_num_interop_threads(2)
        configure_reproducibility(args.seed)
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable")
        versions = package_versions()
        ensure_evaluator_version(versions)
        torch.cuda.set_device(args.device)
        torch.cuda.reset_peak_memory_stats(args.device)
        load_started = time.perf_counter()
        contract = integrity_contract_id(plan)
        if contract is not None:
            available_kib = next(int(line.split()[1]) for line in Path("/proc/meminfo").read_text().splitlines()
                                 if line.startswith("MemAvailable:"))
            free_bytes, total_bytes = torch.cuda.mem_get_info(args.device)
            manifest["integrity_start_resource_guard"] = {
                "host_available_bytes": available_kib * 1024,
                "gpu_free_bytes": free_bytes, "gpu_total_bytes": total_bytes}
            if available_kib < 80 * 1024 * 1024 or free_bytes < 24 * (1 << 30):
                raise RuntimeError("weight-integrity loading requires host reserve 80GiB and GPU free 24GiB")
            from gsm8k_weight_integrity import StaticContentIntegrity
            integrity = StaticContentIntegrity(args.model, model_identity, args.output,
                {"plan_sha256": sha256_file(args.plan), "stage": args.stage, "case": args.case,
                 "model_fingerprint_sha256": model_identity["fingerprint_sha256"],
                 "gpu_uuid": str(torch.cuda.get_device_properties(args.device).uuid)}, device=args.device)
        model, tokenizer, method, audit = load_model(args,
            integrity_observer=integrity.observe if integrity is not None else None)
        torch.cuda.synchronize(args.device)
        manifest["model_load_attach_peak_memory_allocated_bytes"] = torch.cuda.max_memory_allocated(args.device)
        manifest["model_load_attach_peak_memory_reserved_bytes"] = torch.cuda.max_memory_reserved(args.device)
        if audit is not None:
            raise RuntimeError("unexpected hardware/V5 audit in GSM8K algorithm worker")
        if args.case != "bf16":
            validate_quantized_summary(method, get_model_spec(args.model), args.case)
            replacements = []
            for name, module in model.named_modules():
                # Attached QDQ classes live in the two frozen implementation modules.
                if type(module).__module__ in {"mlp4_method_inference", "scalepath4_method_inference"}:
                    module._scalellm_gsm8k_qdq = True
                    replacements.append(name)
            if len(replacements) != get_model_spec(args.model).expected_module_count:
                raise RuntimeError(f"live QDQ projection inventory mismatch: {len(replacements)}")
            method["live_qdq_projection_names"] = replacements
        model.config.use_cache = True
        model.eval()
        if integrity is not None:
            integrity.observe("attached", model)
            torch.cuda.synchronize(args.device)
            # Include the independent full-shape QDQ reconstruction qualification
            # in the load/attach peak; later KV verification has its own scope.
            manifest["model_load_attach_peak_memory_allocated_bytes"] = torch.cuda.max_memory_allocated(args.device)
            manifest["model_load_attach_peak_memory_reserved_bytes"] = torch.cuda.max_memory_reserved(args.device)
        if model.config.use_cache is not True:
            raise RuntimeError("native KV cache was not enabled")
        actual_dtype = str(next(model.parameters()).dtype)
        actual_attention = getattr(model.config, "_attn_implementation", None)
        if actual_dtype != "torch.bfloat16" or actual_attention != "eager":
            raise RuntimeError(f"live backend mismatch: dtype={actual_dtype}, attention={actual_attention}")
        method.update({"use_cache": True, "dtype": "bfloat16", "attention_implementation": "eager",
                       "kv_cache": "native_dynamic_unquantized"})
        encoded, token_audit = audit_prompts(requests, tokenizer, args.context_length,
                                             args.max_gen_toks, int(plan["protocol"]["max_prompt_tokens"]))
        config, generation = resolve_generation(model, tokenizer, args.max_gen_toks)
        eos_text = tokenizer.decode([tokenizer.eos_token_id], skip_special_tokens=False)
        stops = list(dict.fromkeys([*plan["protocol"]["until"], eos_text]))
        if not all(isinstance(stop, str) and stop for stop in stops):
            raise ValueError("empty/nonstring stop sequence")
        generation["stop_strings"] = stops
        generation["context_length"] = args.context_length
        identity = {"protocol_id": plan["protocol_id"], "plan_sha256": sha256_file(args.plan),
                    "protocol_sha256": canonical_hash(plan["protocol"]),
                    "data": plan["data"], "requests_sha256": canonical_hash(requests),
                    "stage": args.stage, "case": args.case, "seed": args.seed,
                    "model_fingerprint_sha256": model_identity["fingerprint_sha256"],
                    "tokenizer": tokenizer_identity(tokenizer, model_identity),
                    "token_audit": token_audit, "generation": generation,
                    "method": method, "code_sha256": code_identity(), "package_versions": versions}
        identity_sha256 = canonical_hash(identity)
        if integrity is not None:
            identity["integrity_contract_id"] = INTEGRITY_CONTRACT_ID
            identity_sha256 = canonical_hash(identity)
        imported, provenance = import_resumable(args.resume_from, identity_sha256, requests, tokenizer, encoded)
        props = torch.cuda.get_device_properties(args.device)
        manifest.update({"state": "running", "identity": identity, "identity_sha256": identity_sha256,
                         "n_expected": len(requests), "request_ids": [r["sample_id"] for r in requests],
                         "model_load_attach_seconds": time.perf_counter() - load_started,
                         "method": method, "generation": generation, "token_audit": token_audit,
                         "resume_sources": provenance, "environment": {"hostname": platform.node(),
                             "python_executable": sys.executable, "package_versions": versions,
                             "cuda_runtime": torch.version.cuda, "device": args.device,
                             "gpu_name": props.name, "gpu_uuid": str(getattr(props, "uuid", "unknown")),
                             "total_memory_bytes": props.total_memory,
                             "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
                             "LD_LIBRARY_PATH": os.environ.get("LD_LIBRARY_PATH"),
                             "nvidia_kernel_driver_version": Path("/proc/driver/nvidia/version").read_text()
                                 if Path("/proc/driver/nvidia/version").exists() else None,
                             "cpu_affinity": sorted(os.sched_getaffinity(0)), "torch_threads": torch.get_num_threads()}})
        atomic_json(args.output / "manifest.json", manifest)
        atomic_json(args.output / "requests.json", requests)
        if integrity is not None:
            integrity.check("setup_complete")
        if args.verify_generation:
            if integrity is not None:
                integrity.check("verification_before")
            torch.cuda.reset_peak_memory_stats(args.device)
            try:
                verification = verify_generation(model, tokenizer, prepare_requests(args.plan, "smoke"),
                    config, args.device, args.seed, evidence_path=args.output / "verification.json")
            finally:
                torch.cuda.synchronize(args.device)
                manifest["verification_peak_memory_allocated_bytes"] = torch.cuda.max_memory_allocated(args.device)
                manifest["verification_peak_memory_reserved_bytes"] = torch.cuda.max_memory_reserved(args.device)
                manifest["verification_memory_scope"] = "diagnostic clones/rebuilds; excluded from production generation memory gate"
            atomic_json(args.output / "verification.json", verification)
            manifest["generation_verification"] = verification
            atomic_json(args.output / "manifest.json", manifest)
            if not verification["passed"]:
                raise RuntimeError("generation cache/repeat/finite/QDQ verification failed")
            if integrity is not None:
                integrity.check("verification_after")
            # Diagnostic cache clones are out of scope for production KV memory.
            # The returned verification report contains only JSON values.
            gc.collect()
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats(args.device)
            manifest["verification_allocator_cache_released_before_generation"] = True
            atomic_json(args.output / "manifest.json", manifest)
        with (args.output / "generation.jsonl").open("x", encoding="utf-8") as generations, \
             (args.output / "scores.jsonl").open("x", encoding="utf-8") as scores:
            for request in requests:
                sample_started = time.perf_counter()
                try:
                    if integrity is not None:
                        integrity.check(f"sample:{request['sample_id']}:before")
                    row = imported.get(request["sample_id"])
                    if row is None:
                        row = generate_one(model, tokenizer, request, encoded[request["sample_id"]],
                                           config, stops, args.device, identity_sha256, args.output)
                    if integrity is not None:
                        integrity.check(f"sample:{request['sample_id']}:after")
                    append_jsonl(generations, row)
                    rows.append(row)
                    append_jsonl(scores, score_row(row))
                    manifest["n_completed"] = len(rows)
                    manifest["last_completed_sample_id"] = row["sample_id"]
                    manifest["updated_at"] = now()
                    atomic_json(args.output / "manifest.json", manifest)
                    atomic_json(args.output / "summary.json", summarize("running"))
                    print(json.dumps({"event": "sample_complete", "sample_id": row["sample_id"],
                                      "n_completed": len(rows), "n_expected": len(requests),
                                      "output_tokens": row["output_tokens"]}), flush=True)
                except Exception as exc:
                    # Persistence/scoring errors also fail the attempt. Do not add a
                    # duplicate error row after an already committed complete row.
                    if not rows or rows[-1]["sample_id"] != request["sample_id"]:
                        error_row = {"schema": ROW_SCHEMA, "status": "error", "sample_id": request["sample_id"],
                                     "identity_sha256": identity_sha256, "source_attempt": str(args.output),
                                     "row_index": request["row_index"], "split": request["split"],
                                     "prompt_sha256": request["prompt_sha256"], "gold": request["gold"],
                                     "fewshot_train_indices": request["fewshot_train_indices"],
                                     "input_tokens": len(encoded[request["sample_id"]]),
                                     "elapsed_seconds": time.perf_counter() - sample_started,
                                     "error": {"type": type(exc).__name__, "message": str(exc),
                                               "traceback": traceback.format_exc()}, "failed_at": now()}
                        try:
                            error_row["peak_memory_allocated_bytes"] = torch.cuda.max_memory_allocated(args.device)
                            error_row["peak_memory_reserved_bytes"] = torch.cuda.max_memory_reserved(args.device)
                        except Exception as memory_error:
                            error_row["memory_query_error"] = str(memory_error)
                        append_jsonl(generations, error_row)
                        rows.append(error_row)
                    raise
        if integrity is not None:
            manifest["integrity"] = integrity.finish()
        summary = summarize("complete")
        if summary["n_completed"] != len(requests):
            raise RuntimeError("attempt ended with missing samples")
        manifest.update({"state": "complete", "completed_at": now(), "full_split": summary["full_split"],
                         "artifacts": {name: sha256_file(args.output / name)
                                       for name in ("generation.jsonl", "scores.jsonl", "requests.json")}})
        if integrity is not None:
            manifest["artifacts"]["integrity.json"] = manifest["integrity"]["sha256"]
            validate_integrity_evidence(args.output, manifest, INTEGRITY_CONTRACT_ID,
                sample_ids=[request["sample_id"] for request in requests], summary=summary)
        atomic_json(args.output / "summary.json", summary)
        atomic_json(args.output / "manifest.json", manifest)
    except BaseException as exc:
        if integrity is not None:
            integrity.fail(exc)
        manifest.update({"state": "failed", "failed_at": now(), "error": {
            "type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}})
        atomic_json(args.output / "manifest.json", manifest)
        if requests:
            atomic_json(args.output / "summary.json", summarize("failed"))
        raise


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
