#!/usr/bin/env python3
"""Freeze an existing JSONL dataset into the short-context board profile."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Sequence


MODEL_ID = "meta-llama/Llama-3.1-8B"
VOCAB_SIZE = 128_256
QUANTIZATION_ID = (
    "hadamard32-scalecode-group32-attention-a8w8-mlp-a8w4-swiglu"
)


def sha256_file(path: Path, chunk_bytes: int = 8 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(chunk_bytes):
            digest.update(block)
    return digest.hexdigest()


def file_record(path: Path) -> dict:
    resolved = path.resolve(strict=True)
    if not resolved.is_file() or resolved.is_symlink():
        raise ValueError(f"frozen input must be a regular file: {resolved}")
    return {
        "path": str(resolved),
        "size": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
    }


def stable_window_start(seed: int, line_number: int, choices: int) -> int:
    if choices <= 0:
        raise ValueError("window choice count must be positive")
    encoded = f"{seed}:{line_number}".encode("ascii")
    return int.from_bytes(hashlib.sha256(encoded).digest()[:8], "little") % choices


def build_samples(
    dataset: Path, tokenizer, text_field: str, sample_count: int, seed: int,
) -> list[dict]:
    samples = []
    with dataset.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid JSONL at {dataset}:{line_number}: {exc}"
                ) from exc
            if not isinstance(record, dict) or not isinstance(
                record.get(text_field), str
            ):
                raise ValueError(
                    f"missing string field {text_field!r} at "
                    f"{dataset}:{line_number}"
                )
            token_ids = tokenizer.encode(
                record[text_field], add_special_tokens=True
            )
            if len(token_ids) < 17:
                continue
            start = stable_window_start(seed, line_number, len(token_ids) - 16)
            window = token_ids[start:start + 17]
            if len(window) != 17 or any(
                type(token) is not int or not 0 <= token < VOCAB_SIZE
                for token in window
            ):
                raise ValueError(
                    f"invalid tokenizer output at {dataset}:{line_number}"
                )
            samples.append({
                "sample_id": f"line-{line_number:08d}-token-{start:06d}",
                "input_token_ids": window[:16],
                "target_token_ids": window[1:],
                "valid_tokens": 16,
            })
            if len(samples) == sample_count:
                break
    if len(samples) != sample_count:
        raise ValueError(
            f"dataset produced only {len(samples)} valid 17-token windows; "
            f"requested {sample_count}"
        )
    return samples


def write_workload_manifest(
    *, dataset: Path, model_dir: Path, checkpoint_sha256: str,
    output: Path, samples: list[dict], software_id: str,
    expected_mean_nll: float, absolute_tolerance: float, seed: int,
    reference_evidence: Path,
) -> Path:
    if len(samples) < 2 or len(samples) % 2:
        raise ValueError("workload sample count must be even and at least 2")
    tokenizer_paths = [
        model_dir / name for name in (
            "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json"
        )
    ]
    manifest = {
        "schema_version": 1,
        "model_id": MODEL_ID,
        "checkpoint_sha256": checkpoint_sha256,
        "dataset": file_record(dataset),
        "tokenizer_files": [file_record(path) for path in tokenizer_paths],
        "sample_count": len(samples),
        "profile": {
            "max_tokens": 128,
            "cohort_rows": 16,
            "attention_query_count": 16,
            "padding": "none",
            "truncation": "contiguous-17-token-window-to-16-causal-pairs",
            "valid_tokens_per_sample": 16,
        },
        "reference": {
            "software_id": software_id,
            "quantization": QUANTIZATION_ID,
            "metric": "causal_nll",
            "expected_mean_nll": expected_mean_nll,
            "absolute_tolerance": absolute_tolerance,
            "seed": seed,
            "evidence": file_record(reference_evidence),
        },
        "samples": samples,
    }
    resolved = output.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    temporary = resolved.with_name(resolved.name + ".partial")
    temporary.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    temporary.replace(resolved)
    return resolved


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Freeze a deterministic ScaleLLM V5 board workload"
    )
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--text-field", default="text")
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--checkpoint-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample-count", type=int, default=32)
    parser.add_argument("--seed", type=int, default=20260904)
    parser.add_argument("--software-id", required=True)
    parser.add_argument("--reference-evidence", type=Path, required=True)
    parser.add_argument("--expected-mean-nll", type=float, required=True)
    parser.add_argument("--absolute-tolerance", type=float, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.sample_count < 2 or args.sample_count % 2:
        raise SystemExit("--sample-count must be even and at least 2")
    if (len(args.checkpoint_sha256) != 64 or any(
        character not in "0123456789abcdef"
        for character in args.checkpoint_sha256
    )):
        raise SystemExit("--checkpoint-sha256 must be lowercase SHA256")
    for name in ("expected_mean_nll", "absolute_tolerance"):
        value = getattr(args, name)
        if not math.isfinite(value) or value < 0:
            raise SystemExit(f"--{name.replace('_', '-')} must be nonnegative")

    try:
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise SystemExit(
            "transformers is required; use the project zhouwenjun conda env"
        ) from exc

    model_dir = args.model_dir.resolve(strict=True)
    dataset = args.dataset.resolve(strict=True)
    tokenizer = AutoTokenizer.from_pretrained(
        model_dir, local_files_only=True, trust_remote_code=False,
    )
    samples = build_samples(
        dataset, tokenizer, args.text_field, args.sample_count, args.seed
    )
    output = write_workload_manifest(
        dataset=dataset, model_dir=model_dir,
        checkpoint_sha256=args.checkpoint_sha256, output=args.output,
        samples=samples, software_id=args.software_id,
        expected_mean_nll=args.expected_mean_nll,
        absolute_tolerance=args.absolute_tolerance, seed=args.seed,
        reference_evidence=args.reference_evidence.resolve(strict=True),
    )
    print(f"SCALELLM_WORKLOAD_FREEZE_PASS manifest={output}")
    print(f"manifest_sha256={sha256_file(output)}")
    print(f"samples={len(samples)} valid_tokens={16 * len(samples)}")


if __name__ == "__main__":
    main()
