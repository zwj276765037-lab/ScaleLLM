#!/usr/bin/env python3
"""Prepare the small, reviewable public index for the frozen cycle evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile


ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "0_Source/operator_timing_kv32/kv128_compare"
FROZEN = STAGE / "results/publication_final_001"
PUBLIC = ROOT / "docs/evidence/kv32_kv128_cycle_sim"
BOARD = ROOT / "docs/evidence/kv128_chat16/results"
ORIGINAL_BOARD = STAGE / "board/results"
ZIP = ROOT / "0_Source/ScaleLLM_KV128_KV32_Decode16_80MHz_20261101.zip"
ASSET_SHA = "bdd7c7281dace4d26604918da4801bb02e0d8eaf0a0781ab75d7896361b9b38b"
ASSET_BYTES = 781288611
TAG = "evidence-kv32-kv128-20261102"
RELEASE = f"https://github.com/zwj276765037-lab/ScaleLLM/releases/tag/{TAG}"
ASSET_URL = RELEASE.replace("/tag/", "/download/") + "/" + ZIP.name
FROZEN_SUMMARY_SHA = "751c8d3cd47e18a11cc82de5876639dc9ff6dea313c98a5b273f801cdb5e1086"
CLOSURE_SHA = "28f4272d1e8b59be010a584d0f7506aa96abc0dc043318325731c73cf4e97890"
CSV = (
    "stages_by_layer.csv", "group_aggregate.csv", "kv32_kv128_paired.csv",
    "kv32_kv128_matched_aggregate.csv", "service_windows_by_layer.csv",
    "preparation_and_dependency.csv", "command_disjoint_partition.csv",
    "command_crosscheck.csv",
)
FIGURES = ("matched_duration_comparison.png", "matched_duration_comparison.svg")
BOARD_FILES = (
    "summary.json", "tokens.json", "power_summary.json", "aux_summary.json",
    "transfer_verification.json", "commands.csv", "power_kv32.csv", "power_kv128.csv",
)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def meta(path: Path) -> dict:
    return {"sha256": digest(path), "bytes": path.stat().st_size}


def member(path: Path) -> str:
    return path.resolve(strict=True).relative_to(ROOT).as_posix()


def prepare(out: Path) -> None:
    assert not out.exists(), "public output already exists; keep previous evidence"
    assert digest(ZIP) == ASSET_SHA and ZIP.stat().st_size == ASSET_BYTES
    publication_path = FROZEN / "summary.json"
    closure_path = FROZEN / "coverage_closure.json"
    assert digest(publication_path) == FROZEN_SUMMARY_SHA
    assert digest(closure_path) == CLOSURE_SHA
    publication = json.loads(publication_path.read_text())
    closure = json.loads(closure_path.read_text())
    assert publication["state"] == "FINAL" and publication["selected_command_count"] == 12
    assert publication["validated_stage_rows"] == 52 and closure["status"] == "PASS"
    for name in BOARD_FILES:
        assert digest(BOARD / name) == digest(ORIGINAL_BOARD / name), name

    with zipfile.ZipFile(ZIP) as archive:
        catalog = json.loads(archive.read("BUNDLE_MANIFEST.json"))
    assert catalog["mode"] == "FINAL" and len(catalog["selected_analyses"]) == 12
    catalog_by_name = {entry["archive_path"]: entry for entry in catalog["files"]}

    out.mkdir(parents=True)
    for name in CSV + FIGURES:
        source = FROZEN / name
        entry = publication["files"].get(name)
        if entry is None:
            entry = next(x for x in publication["matched_duration_figure"]["files"].values()
                         if Path(x["path"]).name == name)
        assert digest(source) == entry["sha256"] and source.stat().st_size == entry["bytes"]
        shutil.copyfile(source, out / name)

    board_public = json.loads((BOARD / "summary.json").read_text())
    source_manifest = json.loads((STAGE / "sim/cycle_compare_l0_a_kv128_001/manifest.json").read_text())
    build_manifest_path = STAGE / "sim/cycle_compare_compile_001/manifest.json"
    build = json.loads(build_manifest_path.read_text())
    assert build["status"] == "COMPILED"
    assert source_manifest["source_manifest"]["release_manifest_sha256"] == digest(
        ROOT / "deploy/final/hardware_source_manifest.json")
    assert source_manifest["simulator_build_manifest_sha256"] == digest(build_manifest_path)
    assert source_manifest["release_bit_sha256"] == publication["release_bit_sha256"]

    source_identity = {
        "schema": "scalellm_cycle_public_source_identity_v1",
        "evidence_kind": "CYCLE_SIMULATION_ESTIMATE",
        "release_bit_sha256": publication["release_bit_sha256"],
        "release_source_manifest_sha256": source_manifest["source_manifest"]["release_manifest_sha256"],
        "immutable_release_files": len(source_manifest["source_manifest"]["immutable_files"]),
        "compiled_release_files": len(source_manifest["source_manifest"]["compile_files"]),
        "sealed_top": source_manifest["source_manifest"]["top"],
        "testbench_top": source_manifest["source_manifest"]["testbench_top"],
        "build_id": build["build_id"],
        "build_manifest_sha256": digest(build_manifest_path),
        "testbench_snapshots": {name: item["sha256"] for name, item in
                                build["tb_source_snapshot"].items()},
        "core_hz": source_manifest["clocks"]["core_hz"],
        "ddr_hz": source_manifest["clocks"]["ddr_hz"],
        "frozen_publication_sha256": FROZEN_SUMMARY_SHA,
        "frozen_coverage_closure_sha256": CLOSURE_SHA,
        "public_board_summary_sha256": digest(BOARD / "summary.json"),
        "board_public_evidence": "../kv128_chat16/README.md",
        "full_archive_sha256": ASSET_SHA,
    }
    write_json(out / "source_identity.json", source_identity)

    method = {
        "schema": "scalellm_cycle_public_method_v1",
        "status": "COMPLETE_WITH_LIMITATIONS",
        "source_experiment_sha256": digest(STAGE / "EXPERIMENT.md"),
        "independent_method_review_sha256": digest(STAGE / "provenance/final_method_review.json"),
        "evidence_kind": "CYCLE_SIMULATION_ESTIMATE",
        "workload": {"active_requests": 16, "kv_lengths": [32, 128],
                     "positions": {"32": 31, "128": 127}},
        "clocks_hz": {"core": 80000000, "ddr_ui": 200000000},
        "shared_effective_weight_bytes": {"Q": 16777216, "K": 4194304,
                                          "V": 4194304, "O": 16777216,
                                          "GateUp": 58720256},
        "peak_bytes_per_second_per_physical_channel": 12800000000,
        "effective_bandwidth": "shared_effective_weight_bytes / duration_seconds",
        "efficiency": "sum(shared_effective_weight_bytes)/(12.8e9*sum(duration_seconds))",
        "group_boundaries": {
            "Q": "first actual Q dispatch to last Q RoPE accepted",
            "K": "first actual K dispatch to last K quantized KV accepted",
            "V": "first actual V dispatch to last V quantized KV accepted",
            "O": "first actual O dispatch to last O scaled linear output accepted",
            "GateUp": "GateUp command launch to last SiLU-times-Up product accepted",
            "AttentionCore": "first valid KV read-address offer on 256-bit core-domain data AXI0 to last PV context accepted",
        },
        "service_window": "first external weight address offer to same group's postprocessed end",
        "ddr_service_model": source_manifest["ddr_model"],
        "key_count_source": publication["rules"]["attention_key_count_source"],
        "limitations": ["The DDR service model omits actual MIG, SmartConnect, DRAM bank/refresh and host XDMA timing.",
                        "Independent complete-model numerical oracle is not established.",
                        "Strict active-power mean, energy and J/token are not established.",
                        "Unmeasured layers stay null; no 32-layer extrapolation or board-ratio correction."],
    }
    write_json(out / "method.json", method)

    selected = []
    raw_index = []
    for item in closure["selection"]:
        run_id, cid = item["run_id"], item["command_id"]
        raw = Path(item["raw_manifest"]["path"])
        assert raw.is_file() and digest(raw) == item["raw_manifest"]["sha256"]
        paths = {
            "raw_manifest": raw,
            "validated_manifest": Path(item["validation_manifest"]["path"]),
            "analysis_summary": Path(item["analysis"]["path"]),
            "events_csv": raw.parent / f"cmd_{cid}_events.csv",
            "phase_events_csv": raw.parent / f"cmd_{cid}_phase_events.csv",
            "sim_output_bin": raw.parent / f"cmd_{cid}_sim_output.bin",
            "native_log": raw.parent / f"cmd_{cid}_native.log",
            "xsim_log": raw.parent / f"cmd_{cid}_xsim.log",
        }
        if item["terminal_receipt"]:
            paths["terminal_receipt"] = Path(item["terminal_receipt"]["path"])
        files = {}
        for label, path in paths.items():
            archive_name = member(path)
            entry = catalog_by_name[archive_name]
            assert path.stat().st_size == entry["bytes"]
            if label in ("raw_manifest", "validated_manifest", "analysis_summary", "terminal_receipt"):
                assert digest(path) == entry["sha256"]
            files[label] = {"zip_member": archive_name, "sha256": entry["sha256"],
                            "bytes": entry["bytes"]}
        selected.append({"kv_length": item["kv_length"], "layer": item["layer"],
                         "opcode": item["opcode"], "command_id": cid, "run_id": run_id,
                         "output_byte_exact": True,
                         "execution_evidence_kind": item["execution_evidence_kind"]})
        raw_index.append({"kv_length": item["kv_length"], "layer": item["layer"],
                          "opcode": item["opcode"], "command_id": cid,
                          "run_id": run_id, "files": files})
    assert len(selected) == len(raw_index) == 12
    write_json(out / "raw_logs_index.json", {
        "schema": "scalellm_cycle_public_raw_logs_index_v1", "status": "PASS",
        "archive_name": ZIP.name, "archive_sha256": ASSET_SHA,
        "entries": raw_index,
        "note": "zip_member paths are inside the GitHub Release asset, not Git repository files.",
    })
    write_json(out / "coverage.json", {
        "schema": "scalellm_cycle_public_coverage_v1", "status": "PASS",
        "active_requests": 16, "selected_command_count": 12,
        "stage_rows": 384, "valid_stage_rows": 52, "unmeasured_stage_rows": 332,
        "attention_layers_per_kv": [0, 8, 16, 24, 31],
        "gateup_layers_per_kv": [0], "selected_commands": selected,
        "matched_stage_pairs": publication["matched_duration_figure"]["matched_stage_pairs"],
        "matched_attention_core_pairs": publication["matched_duration_figure"]["matched_attention_core_pairs"],
        "active1": {"board_commands": 0, "board_status": "FAIL",
                    "simulation_status": "NOT_RUN"},
        "failed_or_incomplete_attempts_preserved_in_archive": len(closure["failed_attempt_index"]),
        "source_closure_sha256": CLOSURE_SHA,
    })
    write_json(out / "summary.json", {
        "schema": "scalellm_cycle_public_summary_v1", "status": "PASS_WITH_LIMITATIONS",
        "evidence_kind": "CYCLE_SIMULATION_ESTIMATE",
        "active_requests": 16, "kv_lengths": [32, 128],
        "selected_command_count": 12, "valid_stage_rows": 52,
        "matched_aggregate": publication["matched_aggregate"],
        "group_aggregate": publication["aggregate"],
        "board_observation": {
            "status": board_public["status"], "steps": board_public["execution"]["rounds"],
            "commands": board_public["execution"]["commands"],
            "generated_tokens": board_public["execution"]["generated_tokens"],
            "model_wall_s": board_public["speed"]["model_wall_s"],
            "model_generated_tokens_per_s": board_public["speed"]["end_to_end_generated_tokens_per_s"],
            "kv32_position31": board_public["round_comparison"]["kv32_position31"],
            "kv128_position127": board_public["round_comparison"]["kv128_position127"],
            "public_board_summary": "../kv128_chat16/results/summary.json",
            "public_board_summary_sha256": digest(BOARD / "summary.json"),
        },
        "tables": {name: meta(out / name) for name in CSV},
        "figures": {name: meta(out / name) for name in FIGURES},
        "source_publication_sha256": FROZEN_SUMMARY_SHA,
        "full_archive_sha256": ASSET_SHA,
    })
    write_json(out / "release_asset.json", {
        "schema": "scalellm_cycle_public_release_asset_v1",
        "tag": TAG, "release_page": RELEASE, "asset_name": ZIP.name,
        "asset_url": ASSET_URL, "sha256": ASSET_SHA, "bytes": ASSET_BYTES,
        "sha256_sidecar_url": ASSET_URL + ".sha256",
        "validation_sidecar_url": ASSET_URL.removesuffix(".zip") + ".validation.json",
        "original_validation_status": "PASS", "original_validation_file_sha256":
            digest(ROOT / "0_Source/ScaleLLM_KV128_KV32_Decode16_80MHz_20261101.validation.json"),
    })
    print(json.dumps({"status": "PREPARED", "directory": str(out),
                      "csv": len(CSV), "figures": len(FIGURES), "selected": len(selected)}))


def seal(out: Path) -> None:
    assert out.is_dir() and not (out / "MANIFEST.json").exists()
    required = {"README.md", "REPORT.md", "DOWNLOADS.md", "summary.json",
                "source_identity.json", "method.json", "coverage.json",
                "raw_logs_index.json", "release_asset.json", *CSV, *FIGURES}
    files = {p.name for p in out.iterdir() if p.is_file()}
    assert files == required, (sorted(required - files), sorted(files - required))
    for name in ("README.md", "REPORT.md", "DOWNLOADS.md"):
        assert "/home/user/" not in (out / name).read_text()
    records = {name: meta(out / name) for name in sorted(files)}
    write_json(out / "MANIFEST.json", {
        "schema": "scalellm_cycle_public_repository_manifest_v1",
        "status": "PASS", "files": records,
        "frozen_publication_sha256": FROZEN_SUMMARY_SHA,
        "frozen_coverage_closure_sha256": CLOSURE_SHA,
        "release_archive_sha256": ASSET_SHA,
        "board_public_summary_sha256": digest(BOARD / "summary.json"),
    })
    print(json.dumps({"status": "SEALED", "files": len(files),
                      "manifest_sha256": digest(out / "MANIFEST.json")}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "seal"))
    parser.add_argument("--output", type=Path, default=PUBLIC)
    args = parser.parse_args()
    (prepare if args.command == "prepare" else seal)(args.output.resolve())


if __name__ == "__main__":
    main()
