"""Frozen JSONL v1 facade for exact and production fixed-code Linear recovery."""
from __future__ import annotations

import re

try:
    from .exact_oracle import evaluate_exact
    from .metrics import compare_linear
    from .production_replay import PROFILES, replay_linear
except ImportError:
    from exact_oracle import evaluate_exact
    from metrics import compare_linear
    from production_replay import PROFILES, replay_linear


def _validate(sample) -> list[str]:
    if not isinstance(sample, dict):
        return ["sample must be an object"]
    errors = []
    if type(sample.get("schema_version")) is not int or sample["schema_version"] != 1:
        errors.append("schema_version must be integer 1")
    if not isinstance(sample.get("sample_id"), str) or not sample["sample_id"]:
        errors.append("sample_id must be a nonempty string")
    if sample.get("kernel") != "linear_recovery":
        errors.append("kernel must be linear_recovery")
    if not isinstance(sample.get("profile"), str) or sample["profile"] not in PROFILES:
        errors.append("unknown profile")
    groups = sample.get("groups")
    if not isinstance(groups, list) or not groups:
        errors.append("groups must be a nonempty list")
    elif len(groups) > 4096:
        errors.append("groups exceeds pilot resource limit 4096")
    else:
        for index, group in enumerate(groups):
            if not isinstance(group, dict):
                errors.append(f"groups[{index}] must be an object")
                continue
            for name in ("dot", "act_code", "act_shift", "weight_code", "weight_shift"):
                if type(group.get(name)) is not int:
                    errors.append(f"groups[{index}].{name} must be an integer (not bool/float)")
            if "lane_evidence" in group:
                lane = group["lane_evidence"]
                if not isinstance(lane, dict):
                    errors.append(f"groups[{index}].lane_evidence must be an object")
                else:
                    for name in ("q_a", "q_w"):
                        if not isinstance(lane.get(name), list) or len(lane[name]) != 32 \
                                or any(type(value) is not int for value in lane[name]):
                            errors.append(f"groups[{index}].lane_evidence.{name} requires 32 integer lanes")
                    if type(lane.get("zero_point")) is not int:
                        errors.append(f"groups[{index}].lane_evidence.zero_point must be integer")
    provenance = sample.get("provenance")
    if not isinstance(provenance, dict):
        errors.append("provenance must be an object")
    else:
        if provenance.get("kind") not in ("synthetic", "real_trace"):
            errors.append("provenance.kind must be synthetic or real_trace")
        for name in ("model", "op", "source_format_id"):
            if name not in provenance or (provenance[name] is not None and not isinstance(provenance[name], str)):
                errors.append(f"provenance.{name} must be string or null")
        if "layer" not in provenance or (provenance["layer"] is not None and type(provenance["layer"]) is not int):
            errors.append("provenance.layer must be integer or null")
        if "trajectory" in provenance and not isinstance(provenance["trajectory"], str):
            errors.append("provenance.trajectory must be a string when present")
        files = provenance.get("source_files")
        if not isinstance(files, list):
            errors.append("provenance.source_files must be a list")
        else:
            for index, file in enumerate(files):
                if not isinstance(file, dict) or not isinstance(file.get("path"), str) or not file["path"] \
                        or not isinstance(file.get("sha256"), str) \
                        or re.fullmatch(r"[0-9a-fA-F]{64}", file["sha256"]) is None:
                    errors.append(f"provenance.source_files[{index}] requires path and SHA256")
    return errors


def _source_qualification(sample: dict) -> tuple[str, list[str]]:
    provenance = sample["provenance"]
    reasons = ["source_identity_not_verified"]
    if provenance["kind"] == "synthetic":
        return "synthetic", ["synthetic_not_model_evidence"]
    format_id = provenance["source_format_id"]
    if isinstance(format_id, str) and format_id.lower().endswith("04"):
        return "legacy_input_replay", reasons + ["legacy_format04"]
    if provenance.get("trajectory") in {"bf16", "bf16_trajectory"}:
        return "bf16_trajectory_local_replay", reasons + ["not_v5_production_trajectory"]
    profile = sample["profile"]
    expected_ops = {"attention": {"q_proj", "k_proj", "v_proj", "o_proj"},
                    "mlp_gate_up": {"gate_proj", "up_proj"}, "mlp_down": {"down_proj"}}
    if provenance["model"] != "Llama-3.1-8B-Instruct":
        reasons.append("model_not_current_scope")
    if type(provenance["layer"]) is not int or not 0 <= provenance["layer"] <= 31:
        reasons.append("layer_not_current_scope")
    if provenance["op"] not in expected_ops[profile]:
        reasons.append("op_profile_mismatch")
    if len(sample["groups"]) != (448 if profile == "mlp_down" else 128):
        reasons.append("group_count_not_current_model")
    if not provenance["source_files"]:
        reasons.append("source_files_missing")
    if provenance.get("trajectory") != "v5_production":
        reasons.append("not_v5_production_trajectory")
    try:
        numeric_format = int(format_id, 0) if isinstance(format_id, str) else None
    except ValueError:
        numeric_format = None
    valid_formats = {0x48384103, 0x48384605} if profile == "attention" else {0x48384605, 0x48384D05}
    if numeric_format not in valid_formats:
        reasons.append("source_format_not_current_profile")
    return ("current_format_real_trace_pending_verification" if len(reasons) == 1
            else "real_input_incomplete"), reasons


def _verify_lanes(sample: dict) -> tuple[dict, dict]:
    audit = {"provided_groups": 0, "verified_groups": 0,
             "domain_error_groups": 0, "mismatch_groups": 0}
    errors = {"lane_domain": 0, "lane_dot_mismatch": 0}
    low_w, high_w = (-127, 127) if sample["profile"] == "attention" else (-8, 7)
    for group in sample["groups"]:
        if "lane_evidence" not in group:
            continue
        audit["provided_groups"] += 1
        lane = group["lane_evidence"]
        domain_valid = (0 <= lane["zero_point"] <= 255
                        and all(0 <= value <= 255 for value in lane["q_a"])
                        and all(low_w <= value <= high_w for value in lane["q_w"]))
        errors["lane_domain"] += int(not domain_valid)
        audit["domain_error_groups"] += int(not domain_valid)
        dot = sum((activation - lane["zero_point"]) * weight
                  for activation, weight in zip(lane["q_a"], lane["q_w"]))
        errors["lane_dot_mismatch"] += int(dot != group["dot"])
        audit["mismatch_groups"] += int(dot != group["dot"])
        audit["verified_groups"] += int(domain_valid and dot == group["dot"])
    return audit, errors


def evaluate_linear_sample(sample: dict) -> dict:
    """Return a JSON-serializable row; syntax rejection never coerces integers."""
    syntax_errors = _validate(sample)
    base = {
        "schema_version": 1,
        "sample_id": sample.get("sample_id") if isinstance(sample, dict) else None,
        "profile": sample.get("profile") if isinstance(sample, dict) else None,
        "kernel": "linear_recovery",
    }
    if syntax_errors:
        return {**base, "status": "invalid_input", "input_errors": syntax_errors}
    source_status, source_reasons = _source_qualification(sample)
    base.update(provenance=sample["provenance"], group_count=len(sample["groups"]),
                source_qualification=source_status, provenance_status=source_status,
                eligible_current_format_evidence=False, provenance_reasons=source_reasons,
                profile_contract=dict(PROFILES[sample["profile"]]))
    domain_errors = []
    for index, group in enumerate(sample["groups"]):
        for name in ("act_code", "weight_code"):
            if not 0 <= group[name] <= 255:
                domain_errors.append(f"groups[{index}].{name} outside U8")
        for name in ("act_shift", "weight_shift"):
            if not 0 <= group[name] <= 63:
                domain_errors.append(f"groups[{index}].{name} outside [0,63]")
    if domain_errors:
        return {**base, "status": "out_of_contract", "domain_errors": domain_errors,
                "current": {"accepted": False, "output_code": None,
                            "error_counts": {"metadata_range": len(domain_errors)}},
                "metrics": {"bounds": {"applicable": False,
                                        "excluded_reasons": ["metadata_range"]}}}
    reference = evaluate_exact(sample, PROFILES[sample["profile"]]["output_width"])
    current = replay_linear(sample)
    lane_verification, lane_errors = _verify_lanes(sample)
    current["error_counts"].update(lane_errors)
    base["lane_verification"] = lane_verification
    metrics = compare_linear(reference["exact"], reference["output_only"], current)
    return {**base, "status": "ok" if metrics["bounds"]["applicable"] else "out_of_contract",
            **reference, "current": current, "metrics": metrics}
