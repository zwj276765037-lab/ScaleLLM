"""Create explicitly synthetic JSONL v1 inputs; never relabel float traces as real."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random

SEED = 20261019
PROFILES = {"attention": (26, 47, 1036320, 128),
            "mlp_gate_up": (20, 44, 65280, 128),
            "mlp_down": (12, 44, 65280, 448)}


def group(dot: int, total_shift: int, act_code: int = 1, weight_code: int = 1) -> dict:
    return {"dot": dot, "act_code": act_code, "act_shift": total_shift // 2,
            "weight_code": weight_code, "weight_shift": total_shift - total_shift // 2}


def sample(sample_id: str, profile: str, groups: list[dict], coverage: str) -> dict:
    return {"schema_version": 1, "sample_id": sample_id, "kernel": "linear_recovery",
            "profile": profile, "groups": groups,
            "provenance": {"kind": "synthetic", "model": None, "layer": None,
                           "op": None, "source_files": [], "source_format_id": None},
            "coverage": coverage}


def with_lane_evidence(item: dict) -> dict:
    if not -255 <= item["dot"] <= 255:
        raise ValueError("tiny-dot witness only")
    return {**item, "lane_evidence": {"q_a": [abs(item["dot"])] + [0] * 31,
              "q_w": [1 if item["dot"] >= 0 else -1] + [0] * 31, "zero_point": 0}}


def synthetic_samples(seed: int = SEED, random_per_profile: int = 48) -> list[dict]:
    rng = random.Random(seed)
    rows = []
    for profile, (lower, upper, max_dot, full_groups) in PROFILES.items():
        prefix = f"synthetic:{profile}:"
        rows.append(sample(prefix + "zero", profile, [group(0, lower)], "zero"))
        for total in sorted({lower, lower + 1, 24, 25, 32, upper} & set(range(lower, upper + 1))):
            for dot in [-513, -256, -1, 1, 256, 513]:
                rows.append(sample(prefix + f"shift{total}:dot{dot}", profile,
                                   [group(dot, total)], "signed_small_and_shift_edges"))
        # Exact half-LSB ties (when the physically reachable dot range permits).
        tie_shift = max(lower, 17)
        tie_dot = 1 << (tie_shift - 17)
        if tie_dot <= max_dot:
            for sign in [-1, 1]:
                for offset in [-1, 0, 1]:
                    rows.append(sample(prefix + f"tie:{sign}:{offset}", profile,
                                       [group(sign * tie_dot + offset, tie_shift)], "output_half_tie_neighbors"))
        for sign in [-1, 1]:
            rows.append(sample(prefix + f"cancel:{sign}", profile,
                               [group(sign, upper), group(-sign, upper)], "cancellation_floor_bias"))
            rows.append(sample(prefix + f"full_floor_bias:{sign}", profile,
                               [group(sign, upper, 128, 128) for _ in range(full_groups)],
                               "valid_full_group_small_remainders"))
            rows.append(sample(prefix + f"full_max:{sign}", profile,
                               [group(sign * max_dot, lower, 255, 255) for _ in range(full_groups)],
                               "physical_dot_max_full_groups_saturation_or_overflow"))
        inactive = group(max_dot, 0, 0, 255)
        rows.append(sample(prefix + "inactive", profile, [inactive], "inactive_zero_code_shift_exemption"))
        for index in range(random_per_profile):
            count = rng.choice([1, 2, 4, 8])
            groups = [group(rng.randint(-max_dot, max_dot), rng.randint(lower, upper),
                            rng.choice([1, 127, 255]), rng.choice([1, 127, 255])) for _ in range(count)]
            rows.append(sample(prefix + f"random:{index}", profile, groups, "seeded_synthetic"))
        rows.append(sample(prefix + "active_shift_below", profile, [group(1, lower - 1)], "out_of_contract_shift"))
        rows.append(sample(prefix + "active_shift_above", profile, [group(-1, upper + 1)], "out_of_contract_shift"))
        rows.append(sample(prefix + "dot_out_of_range", profile, [group(max_dot + 1, upper)], "out_of_contract_dot"))
        invalid = sample(prefix + "invalid_bool_dot", profile, [group(1, lower)], "invalid_type")
        invalid["groups"][0]["dot"] = True
        rows.append(invalid)
        invalid = sample(prefix + "invalid_code", profile, [group(1, lower, 256)], "invalid_code")
        rows.append(invalid)
    # Independent-review witnesses exhibit a difference caused by many truncations.
    for sign in [-1, 1]:
        rows.append(sample(f"synthetic:attention:multigroup_witness:{sign}", "attention",
                           [with_lane_evidence(group(sign * value, 28)) for value in [127] + [15] * 127],
                           "reviewer_multigroup_accumulation_witness"))
        rows.append(sample(f"synthetic:mlp_down:multigroup_witness:{sign}", "mlp_down",
                           [with_lane_evidence(group(sign, 25)) for _ in range(448)],
                           "reviewer_multigroup_accumulation_witness"))
    rows.append(sample("synthetic:attention:multigroup_cancel", "attention",
                       [with_lane_evidence(group(value, 28)) for value in [15, -15] * 64],
                       "reviewer_multigroup_cancellation"))
    rows.append(sample("synthetic:mlp_down:multigroup_cancel", "mlp_down",
                       [with_lane_evidence(group(value, 25)) for value in [1, -1] * 224],
                       "reviewer_multigroup_cancellation"))
    return rows


def write_synthetic(path: Path, seed: int = SEED, random_per_profile: int = 48) -> dict:
    rows = synthetic_samples(seed, random_per_profile)
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with path.open("xb") as stream:
        for row in rows:
            encoded = (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode()
            stream.write(encoded)
            digest.update(encoded)
    return {"schema": "m005_input_preparation_v1", "kind": "synthetic", "seed": seed,
            "rows": len(rows), "path": str(path.resolve()), "sha256": digest.hexdigest(),
            "random_per_profile": random_per_profile, "real_samples": 0,
            "profiles": list(PROFILES), "scope": "Local recovery only; not a captured model workload"}


def real_capture_plan(model: Path) -> dict:
    """Metadata-only feasibility plan. No torch import, weight read, or device use."""
    model = model.resolve()
    config_path = model / "config.json"
    index_path = model / "model.safetensors.index.json"
    config = json.loads(config_path.read_text())
    index = json.loads(index_path.read_text())
    expected = {"hidden_size": 4096, "intermediate_size": 14336,
                "num_hidden_layers": 32, "num_attention_heads": 32, "num_key_value_heads": 8}
    errors = [f"{key}: expected {value}, got {config.get(key)}" for key, value in expected.items()
              if config.get(key) != value]
    ops = {"q_proj": (4096, 4096, 8), "k_proj": (4096, 1024, 8),
           "v_proj": (4096, 1024, 8), "o_proj": (4096, 4096, 8),
           "gate_proj": (4096, 14336, 4), "up_proj": (4096, 14336, 4),
           "down_proj": (14336, 4096, 4)}
    selected = []
    for layer in [0, 15, 31]:
        for op, (in_features, out_features, bits) in ops.items():
            section = "self_attn" if op in ["q_proj", "k_proj", "v_proj", "o_proj"] else "mlp"
            name = f"model.layers.{layer}.{section}.{op}.weight"
            shard = index.get("weight_map", {}).get(name)
            if not shard or not (model / shard).is_file():
                errors.append(f"missing indexed tensor/shard: {name}")
            selected.append({"layer": layer, "op": op, "tensor": name, "shard": shard,
                             "in_features": in_features, "out_features": out_features,
                             "weight_bits": bits, "input_groups": in_features // 32,
                             "token_rows": [0, 127], "output_channels": [0, 1, 63, out_features - 1]})
    shards = sorted(set(index.get("weight_map", {}).values()))
    weights_bytes = sum((model / shard).stat().st_size for shard in shards if (model / shard).is_file())
    return {"schema": "m005_real_capture_plan_v1", "execution_state": "proposal_only",
            "dry_run_kind": "metadata_only; not functional validation or timing measurement",
            "model": str(model), "geometry_matches": not errors, "errors": errors,
            "metadata_identities": [{"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                                    for path in [config_path, index_path]],
            "checkpoint_bytes_from_metadata": weights_bytes, "weight_content_verified": False,
            "input": {"trajectory": "BF16 eager model, use_cache=False; not V5 trajectory",
                      "prompt_count": 1, "max_tokens": 128, "required_tokens": 128,
                      "source": "one calibration text frozen by source-line hash and resulting token IDs before model launch",
                      "short_input_action": "fail before model load; do not silently pad or repeat",
                      "tokens_scored": 0},
            "selected": selected, "sample_outputs": 168, "ordered_group_records": 29184,
            "raw_integer_operand_bytes_upper_estimate": 2 << 20,
            "evidence_directory_budget_bytes": 256 << 20,
            "capture_steps": [
                "Freeze selected BF16 checkpoint metadata and text/token identity; require exactly 128 input tokens.",
                "Register pre-hooks only for selected layer/op, retaining two actual input rows and their positions.",
                "Capture with one BF16 forward; stop after selected layer31; no generation, NLL, PPL or ACC.",
                "On CPU apply production fp_to_fixed_raw and prepare_fixed_activation with S24 inputs or Down S32 adapter inputs.",
                "Quantize selected checkpoint weight rows once using production quantize_folded_rows and the same Hadamard fold.",
                "Retain q_a/zp_a/q_w/code/shift and ordered dot products, hash consumed checkpoint slices and frozen q_w artifacts.",
                "Independently recompute every dot from saved operands; both rounding branches consume identical JSONL.",
                "Mark BF16-local-input adapter provenance; Down BF16 input converted to S32 is not a production SwiGLU trajectory."],
            "gpu0_option": {"requires_root_resource_qualification": True, "gpu_started": False,
                            "device": "cuda:0 only; GPU1 excluded", "threads": 2,
                            "cpu_rss_limit_gib": 8, "gpu_memory_budget_gib": 24,
                            "pilot_wall_limit_seconds": 300, "main_wall_limit_seconds": 1200,
                            "pilot": "metadata/tokenize + model load + <=32-token forward; separate AT, no final128 reuse claim",
                            "cost_status": "estimated memory budget, latency unmeasured; pilot decides qualification",
                            "stops": ["budget exceeded", "new nonfinite/capture geometry mismatch", "model/input identity mismatch",
                                      "Root resource hold/occupancy conflict before launch"]},
            "cpu_option": {"monolithic_model_load_within_8gib": False,
                           "streamed_layer_design_possible": True,
                           "required_work": "independently implement/review exact BF16 trajectory equivalence while streaming layers and embedding/head slices",
                           "largest_selected_bf16_matrix_bytes": 14336 * 4096 * 2,
                           "layer_weight_bytes_estimate": 440000000,
                           "cpu_threads": 2, "cpu_rss_budget_gib": 8,
                           "wall_time_under_20min_proven": False,
                           "recommendation": "Do not run unimplemented streaming substitute; bounded qualified GPU capture has the existing model-forward path."},
            "conclusion_limits": ["local rounding recovery on real BF16 model inputs only", "no whole-V5 propagation",
                                  "no model metric or implementation timing conclusion"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", default=SEED, type=int)
    parser.add_argument("--random-per-profile", default=48, type=int)
    parser.add_argument("--real-capture-plan", type=Path, metavar="MODEL_DIR",
                        help="write a metadata-only proposal instead of generating synthetic data")
    args = parser.parse_args()
    if not 0 <= args.random_per_profile <= 1000:
        parser.error("random-per-profile must be 0..1000")
    if args.real_capture_plan is not None:
        manifest = real_capture_plan(args.real_capture_plan)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(manifest, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        print(json.dumps({"output": str(args.output), "geometry_matches": manifest["geometry_matches"],
                          "sample_outputs": manifest["sample_outputs"], "gpu_started": False}, ensure_ascii=False))
        return
    manifest = write_synthetic(args.output, args.seed, args.random_per_profile)
    with args.output.with_suffix(".manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
