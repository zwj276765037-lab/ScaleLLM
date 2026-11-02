#!/usr/bin/env python3
"""Verify and optionally recompute the seven-rail power archive offline."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "docs/evidence/kv128_sevenrail_power/release_asset.json"
PREFIX = "kv128_repeat_sevenrail/"

def digest(stream):
    return hashlib.file_digest(stream, "sha256").hexdigest()

def safe(name):
    p = PurePosixPath(name)
    if p.is_absolute() or ".." in p.parts or "\\" in name or ":" in name:
        raise ValueError("Unsafe ZIP member: " + name)

def verify(path, expected, recompute=False):
    with path.open("rb") as f:
        if path.stat().st_size != expected["bytes"] or digest(f) != expected["sha256"]:
            raise ValueError("ZIP size/SHA-256 differs from the release manifest")
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP members")
        for name in names:
            safe(name)
        manifest = json.loads(z.read(PREFIX + "PACKAGE_MANIFEST.json"))
        assert manifest["schema"] == "scalellm_power_package_v1"
        entries = {PREFIX + item["path"]: item for item in manifest["included"]}
        assert len(entries) == len(manifest["included"])
        assert set(names) == set(entries) | {PREFIX + "PACKAGE_MANIFEST.json"}
        assert len(names) == expected["file_count"]
        for name, item in entries.items():
            assert z.getinfo(name).file_size == item["bytes"], name
            with z.open(name) as f:
                assert digest(f) == item["sha256"], name
        def read(name):
            return json.loads(z.read(PREFIX + name).decode("utf-8-sig"))
        summary = read("results/summary.json")
        analysis = read("results/main_004_analysis_v2.json")
        receipt = read("native/main_004/receipt.json")
        telemetry = read("native/main_004/telemetry.json")
        workload = read("native/main_004/workload/workload.json")
        assert summary["status"] == analysis["status"] == "PARTIAL_WITH_LIMITS"
        assert receipt["state"] == "FAIL" and receipt["workload_exit_code"] == 0
        assert receipt["sampler_exit_code"] is None and receipt["lease_released"] and not receipt["survivors"]
        assert workload["status"] == "COMPLETE_WITH_LIMITS" and workload["completed_windows"] == 12
        assert telemetry["status"] == "COMPLETE" and telemetry["read_errors"] == 0
        assert summary["commands_completed_and_acknowledged"] == 9129
        assert summary["commands_no_busy_observation"] == [14365]
        assert summary["commands_without_two_busy_observations"] == [10084, 14365]
        assert sum(w["command_count"] for w in summary["windows"]) == 9055
        for window in summary["windows"]:
            if window["kind"] in ("idle", "full_kv128_step"):
                assert window["common_coverage_fraction"] == 1
                assert window["seven_rail_full_window_mean_w"] == window["seven_rail_covered_mean_w"]
            else:
                assert 0.97 < window["common_coverage_fraction"] < 1
                assert window["seven_rail_full_window_mean_w"] is None
            assert window["strict_physical_active_mean_w"] is None
        result = dict(status="PASS", meaning="Archive integrity and declared limits verified; measurement remains PARTIAL_WITH_LIMITS",
                      archive_name=path.name, archive_bytes=expected["bytes"], archive_sha256=expected["sha256"],
                      archive_members=len(names), hashed_members=len(entries), all_member_sha256_and_crc="PASS",
                      windows=12, formal_window_commands=9055, qualification_commands=74, raw_read_errors=0,
                      full_window_mean_counts={"idle":3, "full_kv128_step":3, "attention_repeat":0, "mlp_repeat":0},
                      preserved_launcher_state=receipt["state"], preserved_sampler_exit_code=receipt["sampler_exit_code"],
                      numerical_recomputation="NOT_REQUESTED", does_not_access_board=True)
        if recompute:
            with tempfile.TemporaryDirectory(prefix="scalellm-power-verify-") as temp:
                dest = Path(temp)
                selected = [name for name in names if name.startswith(PREFIX+"source/analysis_final/")]
                selected += [PREFIX+"native/main_004/"+n for n in ["telemetry.json", "telemetry.jsonl", "commands.jsonl", "workload/windows.jsonl"]]
                for name in selected:
                    z.extract(name, dest)
                base = dest / "kv128_repeat_sevenrail"
                native = base / "native/main_004"
                out = dest / "recomputed.json"
                cmd = [sys.executable, str(base/"source/analysis_final/kv128_sevenrail_windows.py"),
                       "--metadata", str(native/"telemetry.json"), "--jsonl", str(native/"telemetry.jsonl"),
                       "--windows", str(native/"workload/windows.jsonl"), "--commands", str(native/"commands.jsonl"),
                       "--target-period-ms", "140", "--output", str(out)]
                p = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
                if p.returncode:
                    raise RuntimeError("Frozen offline analyzer failed: " + p.stderr[-2000:])
                with out.open("rb") as f:
                    actual = digest(f)
                assert actual == expected["analysis_sha256"]
                result.update(numerical_recomputation="BYTE_IDENTICAL_JSON", recomputed_analysis_sha256=actual)
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--archive", type=Path)
    group.add_argument("--download", type=Path)
    p.add_argument("--recompute", action="store_true")
    p.add_argument("--receipt", type=Path)
    args = p.parse_args()
    expected = json.loads(args.manifest.read_text())
    target = args.archive or args.download
    if args.download:
        if target.exists():
            raise FileExistsError("Choose a new download destination")
        target.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(Request(expected["asset_url"], headers={"User-Agent":"ScaleLLM-evidence-verifier"}), timeout=60) as src, target.open("xb") as dst:
            for block in iter(lambda: src.read(1024*1024), b""):
                dst.write(block)
    result = verify(target, expected, args.recompute)
    value = json.dumps(result, indent=2) + "\n"
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(value)
    print(value, end="")

if __name__ == "__main__":
    main()
