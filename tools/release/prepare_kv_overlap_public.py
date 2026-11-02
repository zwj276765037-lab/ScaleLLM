#!/usr/bin/env python3
"""Package existing KV double-buffer evidence without running RTL or hardware."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "0_Source/kv_overlap_validation"
PUBLIC = ROOT / "docs/evidence/kv_overlap_cycle_sim"
OUTPUT = STAGE / "publication_github_20261102"
NAME = "continuous_k32_v8_c001_b001"
ASSET = "ScaleLLM_KV128_DoubleBuffer_RTL_20261102.zip"
TAG = "evidence-kv-overlap-20261102"
BASE = "https://github.com/zwj276765037-lab/ScaleLLM/releases"
SKIP = {"xsim.dir", ".Xil", "__pycache__"}
SECRET = re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bgh[pousr]_[A-Za-z0-9]{30,}\b|\bhf_[A-Za-z0-9]{30,}\b")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def main():
    result_path = STAGE / "results" / f"{NAME}_comparison.json"
    result = json.loads(result_path.read_text())
    assert result["status"] == "FRAGMENT_PASS"
    for key in ("group_csv", "summary_csv", "prefix_csv", "analyzer_source"):
        assert digest(Path(result[key]["path"])) == result[key]["sha256"]
    assert result["append_tags_s12_meta_and_full_kv_image_byte_exact"]
    assert result["summary"]["candidate"]["K"]["actual_cycles"] == 43791
    assert result["summary"]["candidate"]["V"]["estimate_32_from_first_8"]["predicted_32_ps"] == 450875000
    PUBLIC.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    selected = {}

    def add(path):
        path = Path(path)
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Not a regular evidence file: {path}")
        relative = path.relative_to(ROOT).as_posix()
        if path.suffix.lower() not in {".bin", ".png"} and SECRET.search(path.read_bytes()):
            raise ValueError(f"Unexpected credential content: {relative}")
        selected[relative] = path

    for sub in ("results", "provenance", "runs"):
        for path in sorted((STAGE / sub).rglob("*")):
            if path.is_file() and not path.is_symlink() and not SKIP.intersection(path.relative_to(STAGE).parts):
                if path.suffix not in {".wdb", ".pb", ".jou"}:
                    add(path)
    add(STAGE / "README.md")
    experiment = ROOT / "project/hardware/experiments/kv_overlap_validation"
    for path in sorted(experiment.rglob("*")):
        if path.is_file() and not SKIP.intersection(path.relative_to(experiment).parts):
            add(path)
    manifests = {}
    for mode in ("candidate", "baseline"):
        path = STAGE / f"runs/fragment_{mode}_continuous_001/manifest.json"
        manifest = json.loads(path.read_text())
        assert manifest["status"] == "FRAGMENT_EXECUTED"
        assert manifest["tool_runs"][0]["exit_code"] == 0 and manifest["tool_runs"][0]["stop_reason"] is None
        for name, info in manifest["artifacts"].items():
            assert digest(path.parent / name) == info["sha256"]
        for captured in manifest["input_manifest"]["captured_paths"].values():
            add(Path(captured))
        manifests[mode] = {"path": str(path.relative_to(ROOT)), "sha256": digest(path)}
    historical = result["historical_sealed_full_v32"]
    for prefix in ("manifest", "phase_events"):
        path = Path(historical[f"{prefix}_path"])
        assert digest(path) == historical[f"{prefix}_sha256"]
        add(path)
    add(ROOT / "deploy/final/hardware_source_manifest.json")
    add(Path(__file__).resolve())
    add(ROOT / "tools/release/verify_kv_overlap_asset.py")
    inventory = [{"path": key, "bytes": path.stat().st_size, "sha256": digest(path)}
                 for key, path in sorted(selected.items())]
    catalog = {"schema": "scalellm_kv_overlap_bundle_v1", "status": "FROZEN_VALIDATED_EVIDENCE",
               "files": inventory, "selected_runs": manifests,
               "comparison": str(result_path.relative_to(ROOT)),
               "release_bit_sha256": "96df1a5c1bf4174921bc02ccd88df4066dece3d62b491acb3106bb90ac0ffc85",
               "scope": "Layer 0, active16, KV128, K32 observed RTL; V8 observed RTL and V32 estimated",
               "exclusions": ["Compiled XSim caches/executables, wave databases and journals",
                              "Model weight assets and Vivado installation; RTL rerun is not self-contained"],
               "original_paths": "Original absolute paths inside frozen provenance are identifiers, not download URLs."}
    archive = OUTPUT / ASSET
    if archive.exists():
        raise ValueError(f"Archive already exists: {archive}")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for name, path in sorted(selected.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 2, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with path.open("rb") as source, bundle.open(info, "w", force_zip64=True) as target:
                shutil.copyfileobj(source, target, length=1 << 20)
        bundle.writestr("BUNDLE_MANIFEST.json", json.dumps(catalog, indent=2, sort_keys=True) + "\n")
        bundle.writestr("READ_ME.txt", "ScaleLLM independent double-buffer RTL evidence.\n"
                         "K32 is observed simulation; V32 is an extrapolation from V8, not a board measurement.\n"
                         "Original run/build/source snapshots are preserved. Model weights and tool binaries are excluded.\n"
                         "Use tools/release/verify_kv_overlap_asset.py for offline byte/timing checks.\n")
    asset_sha = digest(archive)
    (OUTPUT / (ASSET + ".sha256")).write_text(f"{asset_sha}  {ASSET}\n")
    copies = {f"{NAME}_groups.csv": "groups.csv", f"{NAME}_summary.csv": "summary.csv",
              f"{NAME}_prefixes.csv": "prefixes.csv", "continuous_prefix_efficiency.svg": "prefix_efficiency.svg",
              "continuous_prefix_efficiency.png": "prefix_efficiency.png"}
    for source, dest in copies.items():
        shutil.copyfile(STAGE / "results" / source, PUBLIC / dest)
    identity = {"schema": "scalellm_kv_overlap_public_v1", "status": "FRAGMENT_PASS",
                "workload": {"model": "Llama-3.1-8B-Instruct", "layer": 0, "command_id": 8129,
                             "active_requests": 16, "kv_length": 128, "position": 127},
                "core_hz": 80000000, "ddr_interface_hz": 200000000, "channel_peak_bytes_per_s": 12800000000,
                "release_bit_sha256": catalog["release_bit_sha256"], "comparison_sha256": digest(result_path),
                "observed_candidate_groups": {"K": 32, "V": 8}, "candidate_v32": "ESTIMATED_FROM_V8",
                "full_attention": "NOT_RUN", "candidate_board_performance": "NOT_RUN",
                "append_records_per_run": 640, "kv_image_bytes": 8388608,
                "kv_image_sha256": result["kv_after_sha256"], "summary": result["summary"],
                "historical_baseline_v32_cycles": historical["actual_cycles"],
                "quantizer_and_ddr_model_unchanged": True,
                "limitations": result["limitations"], "selected_runs": manifests}
    write(PUBLIC / "results.json", identity)
    write(PUBLIC / "archive_members.json", {"archive_name": ASSET, "files": inventory,
                                            "selected_runs": manifests, "comparison": catalog["comparison"]})
    write(PUBLIC / "release_asset.json", {"schema": "scalellm_kv_overlap_release_asset_v1",
          "tag": TAG, "asset_name": ASSET, "bytes": archive.stat().st_size, "sha256": asset_sha,
          "file_count": len(inventory), "release_page": f"{BASE}/tag/{TAG}",
          "asset_url": f"{BASE}/download/{TAG}/{ASSET}",
          "sha256_sidecar_url": f"{BASE}/download/{TAG}/{ASSET}.sha256",
          "validation_sidecar_url": f"{BASE}/download/{TAG}/ScaleLLM_KV128_DoubleBuffer_RTL_20261102.validation.json"})
    print(json.dumps({"archive": str(archive), "files": len(inventory), "bytes": archive.stat().st_size,
                      "sha256": asset_sha, "public": str(PUBLIC)}))


if __name__ == "__main__":
    main()
