"""Exact local error comparisons and denominator-aware summary statistics."""
from __future__ import annotations

from collections import Counter, defaultdict
from fractions import Fraction
import math

try:
    from .exact_oracle import decode_fraction, encode_fraction
except ImportError:
    from exact_oracle import decode_fraction, encode_fraction


def _finite_float(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (OverflowError, ValueError):
        return None


def compare_linear(exact: dict, output_only: dict, current: dict) -> dict:
    """Use exact rational comparisons; float fields are presentation values only."""
    reference = decode_fraction(exact)
    reasons = [name for name, count in current["error_counts"].items() if count]
    if output_only["saturated"]:
        reasons.append("output_only_saturation")
    applicable = not reasons and current["accepted"]
    g_right = current["g_right"]
    g_nonzero = current["g_nonzero_remainder"]
    bound_exact = Fraction(g_right, 1 << 24) + Fraction(1, 1 << 17)
    bound_once = Fraction(g_right, 1 << 24) + Fraction(1, 1 << 16)
    truncation_loss = sum((Fraction(int(trace["floor_remainder"]),
                                          1 << (trace["right_shift_bits"] + 24))
                           for trace in current["group_trace"] if trace["active"]
                           and trace["right_shift_bits"] > 0), Fraction())
    tight_exact = truncation_loss + Fraction(1, 1 << 17)
    tight_once = truncation_loss + Fraction(1, 1 << 16)
    result = {
        "g_right": g_right, "g_nonzero_remainder": g_nonzero,
        "truncation_loss_D": encode_fraction(truncation_loss),
        "exact_fractions": {},
        "bounds": {
            "applicable": applicable, "excluded_reasons": reasons,
            "vs_exact": encode_fraction(bound_exact),
            "vs_output_only": encode_fraction(bound_once),
            "nonzero_remainder_vs_exact": encode_fraction(Fraction(g_nonzero, 1 << 24) + Fraction(1, 1 << 17)),
            "nonzero_remainder_vs_output_only": encode_fraction(Fraction(g_nonzero, 1 << 24) + Fraction(1, 1 << 16)),
            "tight_vs_exact": encode_fraction(tight_exact),
            "tight_vs_output_only": encode_fraction(tight_once),
            "violation_vs_exact": None, "violation_vs_output_only": None,
            "tight_violation_vs_exact": None, "tight_violation_vs_output_only": None,
        },
    }
    pre_output_error = Fraction(int(current["accumulator_f24_code"]), 1 << 24) - reference
    result["pre_output_signed_error"] = encode_fraction(pre_output_error)
    identity_excluded = [name for name, count in current["error_counts"].items()
                         if count and name != "output_saturation"]
    result["truncation_identity_applicable"] = not identity_excluded
    result["truncation_identity_holds"] = pre_output_error == -truncation_loss if not identity_excluded else None
    if current["output_code"] is None:
        return result
    current_value = Fraction(current["output_code"], 1 << 16)
    once_value = Fraction(output_only["output_code"], 1 << 16)
    for suffix, value in (("current_vs_exact", reference),
                          ("current_vs_output_only", once_value)):
        error = current_value - value
        for prefix, exact_error in (("signed_error_", error), ("absolute_error_", abs(error)),
                                    ("lsb_error_", error * (1 << 16))):
            name = prefix + suffix
            result[name] = _finite_float(exact_error)
            result["exact_fractions"][name] = encode_fraction(exact_error)
    if applicable:
        error_exact = abs(current_value - reference)
        error_once = abs(current_value - once_value)
        result["bounds"].update(
            violation_vs_exact=error_exact > bound_exact,
            violation_vs_output_only=error_once > bound_once,
            tight_violation_vs_exact=error_exact > tight_exact,
            tight_violation_vs_output_only=error_once > tight_once)
    return result


def _statistics(errors: list[Fraction], references: list[Fraction]) -> dict:
    n = len(errors)
    if not n:
        return {"count": 0, "signed_mean": None, "mae": None, "rmse": None,
                "max_absolute": None, "p99_absolute": None,
                "nmse": None, "nmse_defined": False}
    absolute = sorted(abs(error) for error in errors)
    squared = sum((error * error for error in errors), Fraction())
    reference_energy = sum((value * value for value in references), Fraction())
    mean = sum(errors, Fraction()) / n
    return {
        "count": n, "signed_mean": _finite_float(mean),
        "signed_mean_exact": encode_fraction(mean),
        "mae": _finite_float(sum(absolute, Fraction()) / n),
        "rmse": math.sqrt(_finite_float(squared / n)) if _finite_float(squared / n) is not None else None,
        "max_absolute": _finite_float(absolute[-1]),
        "p99_absolute": _finite_float(absolute[max(0, math.ceil(n * .99) - 1)]),
        "p99_method": "nearest_rank",
        "nmse": _finite_float(squared / reference_energy) if reference_energy else None,
        "nmse_defined": bool(reference_energy),
    }


def _summarize(rows: list[dict]) -> dict:
    counts = Counter(row.get("status", "invalid_input") for row in rows)
    errors = Counter()
    exclusions = Counter()
    valid_rows = []
    anomaly_rows = []
    violation_counts = Counter()
    for row in rows:
        errors.update(row.get("current", {}).get("error_counts", {}))
        output_only = row.get("output_only", {})
        errors["output_only_saturation"] += int(output_only.get("saturated", False))
        bounds = row.get("metrics", {}).get("bounds", {})
        exclusions.update(bounds.get("excluded_reasons", []))
        if bounds.get("applicable"):
            valid_rows.append(row)
            for key in ("violation_vs_exact", "violation_vs_output_only",
                        "tight_violation_vs_exact", "tight_violation_vs_output_only"):
                violation_counts[key] += int(bounds.get(key, False))
        elif row.get("current", {}).get("output_code") is not None:
            anomaly_rows.append(row)
    summaries = {}
    for bucket, selected in (("eligible", valid_rows), ("out_of_contract", anomaly_rows)):
        bucket_summary = {}
        for suffix in ("current_vs_exact", "current_vs_output_only"):
            metric_name = "signed_error_" + suffix
            selected_metric = [row for row in selected
                               if metric_name in row.get("metrics", {}).get("exact_fractions", {})]
            differences = [decode_fraction(row["metrics"]["exact_fractions"][metric_name])
                           for row in selected_metric]
            references = [decode_fraction(row["exact"]) if suffix.endswith("vs_exact")
                          else Fraction(row["output_only"]["output_code"], 1 << 16)
                          for row in selected_metric]
            stats = _statistics(differences, references)
            stats["lsb_signed_mean"] = stats["signed_mean"] * (1 << 16) if stats["signed_mean"] is not None else None
            stats["lsb_rmse"] = stats["rmse"] * (1 << 16) if stats["rmse"] is not None else None
            stats["lsb_max_absolute"] = stats["max_absolute"] * (1 << 16) if stats["max_absolute"] is not None else None
            bucket_summary[suffix] = stats
        comparable = [row for row in selected if row.get("current", {}).get("output_code") is not None]
        histogram = Counter(row["current"]["output_code"] - row["output_only"]["output_code"]
                            for row in comparable)
        identical = histogram.get(0, 0)
        bucket_summary["output_code_comparison"] = {
            "count": len(comparable), "identical_count": identical,
            "identical_fraction": identical / len(comparable) if comparable else None,
            "signed_lsb_histogram": {str(key): count for key, count in sorted(histogram.items())},
        }
        summaries[bucket] = bucket_summary
    return {
        "sample_count": len(rows),
        "status_counts": {name: counts[name] for name in ("ok", "out_of_contract", "invalid_input")},
        "bound_eligible_count": len(valid_rows), "bound_excluded_count": len(rows) - len(valid_rows),
        "bound_violation_counts": {name: violation_counts[name] for name in (
            "violation_vs_exact", "violation_vs_output_only",
            "tight_violation_vs_exact", "tight_violation_vs_output_only")},
        "error_counts": dict(errors), "bound_exclusion_counts": dict(exclusions),
        "statistics": summaries,
    }


def summarize_results(rows) -> dict:
    """Summarize evaluated rows, preserving eligible/anomaly denominator boundaries."""
    rows = list(rows)
    by_profile = defaultdict(list)
    by_source = defaultdict(list)
    for row in rows:
        by_profile[row.get("profile") or "unknown"].append(row)
        by_source[row.get("source_qualification") or "unknown"].append(row)
    return {
        "overall": _summarize(rows),
        "by_profile": {name: _summarize(selected) for name, selected in sorted(by_profile.items())},
        "by_source_qualification": {name: _summarize(selected) for name, selected in sorted(by_source.items())},
        "labels": {"output_only": "仅输出舍入", "current": "当前实现"},
        "units": {"errors": "real_value", "lsb_errors": "F16_output_LSB=2^-16"},
    }
