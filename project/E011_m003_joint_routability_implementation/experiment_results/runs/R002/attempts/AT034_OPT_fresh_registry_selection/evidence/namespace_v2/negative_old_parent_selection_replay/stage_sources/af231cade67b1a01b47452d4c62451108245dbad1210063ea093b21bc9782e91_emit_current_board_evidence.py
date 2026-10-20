#!/usr/bin/env python3
"""Inventory current board outputs after the original Vivado process exits.

This records identities and HOLD state. It does not qualify physical signoff.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys


PROFILE = "core100_ddr200_format05"
SCHEMAS = {
    "synth": "scalellm_board_build_evidence_v2",
    "place": "scalellm_board_build_evidence_v2",
    "route": "scalellm_board_build_evidence_v2",
    "audit": "scalellm_board_audit_evidence_v2",
}
REPORTS = {
    "synth": (
        "utilization_post_synth.rpt", "timing_post_synth.rpt",
        "utilization_hierarchical_post_synth.rpt", "check_timing_post_synth.rpt",
        "clocks_post_synth.rpt", "clock_interaction_post_synth.rpt",
        "cdc_post_synth.rpt", "drc_pre_impl.rpt",
        "fresh_synth_complete.txt",
    ),
    "place": (
        "utilization_post_synth.rpt", "timing_post_synth.rpt",
        "utilization_hierarchical_post_synth.rpt", "check_timing_post_synth.rpt",
        "clocks_post_synth.rpt", "clock_interaction_post_synth.rpt",
        "cdc_post_synth.rpt", "drc_pre_impl.rpt",
        "timing_pre_place.rpt", "check_timing_pre_place.rpt", "clocks_pre_place.rpt",
        "clock_interaction_pre_place.rpt", "cdc_pre_place.rpt",
        "drc_pre_place.rpt", "utilization_physopt.rpt", "control_sets_physopt.rpt",
        "congestion_physopt.rpt", "slr_crossing_physopt.rpt", "timing_physopt.rpt",
        "check_timing_physopt.rpt", "cdc_physopt.rpt", "drc_physopt.rpt",
        "metadata_address_locality.tsv", "metadata_physical_cells.tsv",
        "per_cr_resources.tsv", "dsp_clock_regions.tsv", "fresh_place_complete.txt",
    ),
    "route": (
        "utilization_post_synth.rpt", "timing_post_synth.rpt",
        "utilization_hierarchical_post_synth.rpt", "check_timing_post_synth.rpt",
        "clocks_post_synth.rpt", "clock_interaction_post_synth.rpt",
        "cdc_post_synth.rpt", "drc_pre_impl.rpt", "timing_post_route.rpt",
        "clocks_post_route.rpt", "clock_interaction_post_route.rpt",
        "cdc_post_route.rpt", "drc_post_route.rpt",
        "route_status_post_route.rpt", "exceptions_post_route.rpt",
        "check_timing_post_route.rpt", "routed.dcp", "routed_checkpoint.sha256",
    ),
    "audit": (
        "audit_summary.txt", "package_pins_reopened.txt",
        "timing_reopened.rpt", "clocks_reopened.rpt",
        "clock_interaction_reopened.rpt", "route_status_reopened.rpt",
        "drc_reopened.rpt", "cdc_reopened.rpt",
        "exceptions_reopened.rpt", "io_reopened.rpt",
        "check_timing_reopened.rpt", "pulse_width_reopened.rpt",
        "pulse_width_violators_reopened.rpt", "bus_skew_reopened.rpt",
        "dsp_status_paths_reopened.rpt",
    ),
}
SHA_ROW = re.compile(r"([0-9a-f]{64})  (.+)")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_id(path: Path) -> dict[str, object]:
    path = path.resolve(strict=True)
    require(path.is_file() and path.stat().st_size > 0, f"missing/empty file: {path}")
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def inside(base: Path, candidate: str | Path) -> Path:
    path = Path(candidate).resolve(strict=True)
    require(path.is_relative_to(base), f"path outside new hardware root: {path}")
    return path


def key_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for row in path.read_text(encoding="utf-8").splitlines():
        if not row:
            continue
        require("=" in row, f"malformed status row in {path}: {row}")
        key, value = row.split("=", 1)
        require(key and key not in values, f"duplicate/empty status key: {key}")
        values[key] = value
    return values


def input_manifest(path: Path) -> dict[Path, str]:
    rows: dict[Path, str] = {}
    for row in path.read_text(encoding="utf-8").splitlines():
        match = SHA_ROW.fullmatch(row)
        require(match is not None, f"malformed SHA256 row in {path}: {row}")
        expected, name = match.groups()
        source = Path(name).resolve(strict=True)
        require(source not in rows, f"duplicate input path: {source}")
        require(sha256(source) == expected, f"changed input: {source}")
        rows[source] = expected
    require(bool(rows), f"empty input manifest: {path}")
    return rows


def status_id(path: Path, stage: str, project: Path) -> dict[str, object]:
    values = key_values(path)
    require(values.get("stage") == stage, f"wrong stage status: {path}")
    require(values.get("project") == str(project), f"wrong project status: {path}")
    require(values.get("exit_code") == "0", f"stage did not exit zero: {path}")
    require(values.get("native_exit_code", "0") == "0",
            f"native stage did not exit zero: {path}")
    return {**file_id(path), "exit_code": 0}


def create_receipt(root: Path, project: Path, current_inputs: dict[Path, str]) -> dict[str, object]:
    candidates = []
    for path in (root / "vivado/reports").glob("*/launcher_status.txt"):
        values = key_values(path)
        if values.get("stage") == "create" and values.get("project") == str(project):
            candidates.append(path)
    require(len(candidates) == 1, f"expected one original create receipt for {project}")
    path = candidates[0]
    receipt = status_id(path, "create", project)
    report_dir = inside(root, key_values(path)["reports"])
    original = report_dir / "constructor_inputs.sha256"
    source_rows = input_manifest(original)
    for source, digest in source_rows.items():
        require(current_inputs.get(source) == digest,
                f"build input differs from original constructor: {source}")
    return {"launcher": receipt,
            "input_manifest": file_id(original),
            "input_count": len(source_rows),
            "summary": file_id(report_dir / "constructor_summary.txt")}


def identity(path: Path) -> dict[str, str]:
    values = key_values(path)
    expected = {
        "vivado": "2025.2",
        "part": "xcvu9p-flga2104-2L-e",
        "board": "xilinx.com:vcu118:part0:2.0",
        "top": "scalellm_vcu118_f05_bd_wrapper",
    }
    for key, value in expected.items():
        require(values.get(key) == value, f"wrong build identity {key}: {values.get(key)}")
    defines = values.get("defines", "").split()
    require(sorted(defines) == sorted((
        "HAP_BOARD_BUILD", "HAP_BOARD_V5",
        "HAP_MLP_FULL_COMMAND_V5_MODULE=hap_mlp_full_command16_s54",
        "HAP_ATTENTION_BOARD_MODULE=hap_attention_board_cohort16_core",
    )), "wrong format05/cohort16 compile flags")
    return {key: values[key] for key in (*expected, "defines")}


def emit(stage: str, root: Path, project: Path, report_dir: Path) -> Path:
    require(stage in SCHEMAS, f"unsupported evidence stage: {stage}")
    project = inside(root, project)
    report_dir = inside(root, report_dir)
    require(project.is_dir() and report_dir.is_dir(), "project/report directory missing")
    current_status = status_id(report_dir / "launcher_status.txt", stage, project)
    manifest_name = "audit_inputs.sha256" if stage == "audit" else "inputs.sha256"
    manifest_path = report_dir / manifest_name
    rows = input_manifest(manifest_path)
    route_dir: Path | None = None
    synth_dir: Path | None = None
    if stage == "audit":
        route_dir = inside(root, os.environ["HAP_ROUTE_REPORT_DIR"])
        route_status = key_values(route_dir / "launcher_status.txt")
        synth_dir = inside(root, route_status["synth_reports"])
        build_identity = route_dir / "build_identity.txt"
    else:
        build_identity = report_dir / "build_identity.txt"
        if stage in {"place", "route"}:
            synth_dir = inside(root, os.environ["HAP_SYNTH_REPORT_DIR"])
    build = identity(build_identity)
    expected_report = report_dir / "audit_evidence.json" if stage == "audit" else report_dir / "board_evidence.json"
    require(not expected_report.exists(), f"evidence output already exists: {expected_report}")
    exits = {stage: current_status}
    if route_dir is not None:
        exits["route"] = status_id(route_dir / "launcher_status.txt", "route", project)
    if synth_dir is not None:
        exits["synth"] = status_id(synth_dir / "launcher_status.txt", "synth", project)
    if stage != "audit":
        exits["create"] = create_receipt(root, project, rows)
    else:
        route_rows = input_manifest(route_dir / "inputs.sha256")
        exits["create"] = create_receipt(root, project, route_rows)
        require(rows.get((route_dir / "inputs.sha256").resolve()) ==
                sha256(route_dir / "inputs.sha256"), "audit lacks routed input identity")
        require(rows.get((route_dir / "routed.dcp").resolve()) ==
                sha256(route_dir / "routed.dcp"), "audit lacks routed checkpoint identity")
    if synth_dir is not None:
        synth_manifest = synth_dir / "inputs.sha256"
        require(sha256(synth_manifest) == sha256(
            route_dir / "inputs.sha256" if stage == "audit" else manifest_path),
            "fresh synth/route input manifests differ")
    reports = {name: file_id(report_dir / name) for name in REPORTS[stage]}
    output: dict[str, object] = {
        "schema": SCHEMAS[stage], "profile": PROFILE, "stage": stage,
        "qualification": "HOLD", "original_stage_exits": exits,
        "project": str(project), "build": build,
        "input_manifest": file_id(manifest_path), "input_count": len(rows),
        "reports": reports, "bitstream": None, "physical_signoff": False,
    }
    if synth_dir is not None:
        output["source_synthesis"] = {
            "input_manifest": file_id(synth_dir / "inputs.sha256"),
            "build_identity": file_id(synth_dir / "build_identity.txt"),
            "completion_marker": file_id(synth_dir / "fresh_synth_complete.txt"),
            "board_evidence": file_id(synth_dir / "board_evidence.json"),
        }
    if stage == "route":
        place_dir = inside(root, os.environ["HAP_PLACE_REPORT_DIR"])
        exits["place"] = status_id(place_dir / "launcher_status.txt", "place", project)
        require(sha256(place_dir / "inputs.sha256") == sha256(manifest_path),
                "fresh place/route input manifests differ")
        output["source_place"] = {
            "completion_marker": file_id(place_dir / "fresh_place_complete.txt"),
            "screen": file_id(place_dir / "s3_screen.txt"),
            "board_evidence": file_id(place_dir / "board_evidence.json"),
        }
    if route_dir is not None:
        output["source_route"] = {
            "input_manifest": file_id(route_dir / "inputs.sha256"),
            "build_identity": file_id(route_dir / "build_identity.txt"),
            "board_evidence": file_id(route_dir / "board_evidence.json"),
        }
    if stage in {"route", "audit"}:
        dcp = (route_dir if stage == "audit" else report_dir) / "routed.dcp"
        output["routed_checkpoint"] = file_id(dcp)
    else:
        output["routed_checkpoint"] = None
    temporary = expected_report.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
    temporary.replace(expected_report)
    return expected_report


def main() -> int:
    try:
        require(len(sys.argv) == 5, "usage: emit_current_board_evidence.py STAGE ROOT PROJECT REPORT")
        output = emit(sys.argv[1], Path(sys.argv[2]).resolve(strict=True),
                      Path(sys.argv[3]), Path(sys.argv[4]))
    except (KeyError, OSError, ValueError) as exc:
        print(f"CURRENT_BOARD_EVIDENCE_HOLD: {exc}", file=sys.stderr)
        return 1
    print(f"CURRENT_BOARD_EVIDENCE_HOLD: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
