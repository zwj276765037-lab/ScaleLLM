#!/usr/bin/env python3
"""Verify/download the double-buffer evidence and recompute timing offline."""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import statistics
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs/evidence/kv_overlap_cycle_sim/release_asset.json"
STAGE = "0_Source/kv_overlap_validation"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def relative(path):
    marker = "/Workspace/ScaleLLM/"
    value = path.split(marker, 1)[-1] if marker in path else path
    safe(value)
    return value


def safe(name):
    part = PurePosixPath(name)
    if part.is_absolute() or ".." in part.parts or "\\" in name or ":" in name:
        raise ValueError(f"Unsafe member name: {name}")


def verify(path, expected):
    if path.stat().st_size != expected["bytes"] or digest(path) != expected["sha256"]:
        raise ValueError("Archive identity differs from published SHA-256/size")
    with zipfile.ZipFile(path) as bundle:
        names = bundle.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP members")
        for name in names:
            safe(name)
        catalog = json.loads(bundle.read("BUNDLE_MANIFEST.json"))
        assert catalog["schema"] == "scalellm_kv_overlap_bundle_v1"
        index = {entry["path"]: entry for entry in catalog["files"]}
        assert set(names) == set(index) | {"BUNDLE_MANIFEST.json", "READ_ME.txt"}
        for name, info in index.items():
            with bundle.open(name) as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            assert bundle.getinfo(name).file_size == info["bytes"] and actual == info["sha256"], name

        def data(name):
            return bundle.read(name)

        def rows(name):
            return list(csv.DictReader(io.StringIO(data(name).decode())))

        comparison = json.loads(data(catalog["comparison"]))
        assert comparison["status"] == "FRAGMENT_PASS"
        images, appends, metrics, builds, manifests = {}, {}, {}, {}, {}
        for mode in ("candidate", "baseline"):
            entry = catalog["selected_runs"][mode]
            assert hashlib.sha256(data(entry["path"])).hexdigest() == entry["sha256"]
            parent = str(PurePosixPath(entry["path"]).parent)
            run = json.loads(data(entry["path"]))
            manifests[mode] = run
            assert run["status"] == "FRAGMENT_EXECUTED"
            assert run["tool_runs"][0]["exit_code"] == 0 and run["tool_runs"][0]["stop_reason"] is None
            for name, info in run["artifacts"].items():
                assert hashlib.sha256(data(parent + "/" + name)).hexdigest() == info["sha256"]
            build_key = relative(run["build_manifest"]["path"])
            assert hashlib.sha256(data(build_key)).hexdigest() == run["build_manifest"]["sha256"]
            build = json.loads(data(build_key)); builds[mode] = build
            for source in build["source_manifest"]["compile_files"]:
                assert hashlib.sha256(data(relative(source["snapshot"]))).hexdigest() == source["sha256"]
            fragment = rows(parent + "/fragment.csv")
            events = rows(parent + "/group_events.csv")
            coverage = rows(parent + "/coverage.csv")
            append = [r for r in fragment if r["event"] == "append"]
            aw = [r for r in fragment if r["event"] == "kv_aw"]
            assert len(append) == len(aw) == 640
            assert sum(r["event"] == "kv_b" for r in fragment) == 640
            assert sum(r["event"] == "weight_fire" for r in fragment) == 10240
            assert sum(r["event"] == "projection_wave" for r in coverage) == 160
            assert sum(r["event"] == "rope_pair" for r in coverage) == 8192
            image = data(parent + "/kv_after_8m.bin"); images[mode] = image; appends[mode] = append
            reconstructed = bytearray(data(relative(run["input_manifest"]["captured_paths"]["kv_before"])))
            for i, r in enumerate(append):
                op = 0 if i < 512 else 1
                group = i // 16 if op == 0 else (i - 512) // 16
                assert int(r["is_v"]) == op and int(r["position"]) == 127 and int(r["layer"]) == 0
                assert int(r["head"]) == group // 4 and int(r["group"]) == group % 4
                assert int(r["command"]) == 8129 and int(r["epoch"]) == 1
                address = 0x60000000 + int(r["slot"]) * 0x80000 + 127 * 0x1000 + op * 0x800 + group * 0x40
                assert int(aw[i]["address"], 16) == address
                record = int(r["s12"], 16).to_bytes(48, "little") + int(r["meta"], 16).to_bytes(2, "little") + bytes(14)
                reconstructed[address - 0x60000000:address - 0x60000000 + 64] = record
            assert bytes(reconstructed) == image and len(image) == 8388608
            group_rows = rows(relative(comparison["group_csv"]["path"]))
            metrics[mode] = {}
            for op, count in ((0, 32), (1, 8)):
                starts = {int(r["group"]): int(r["sim_time_ps"]) for r in events if r["event"] == "dispatch" and int(r["op"]) == op}
                ends = {int(r["group"]): int(r["sim_time_ps"]) for r in events if r["event"] == "append_last_group" and int(r["op"]) == op}
                assert set(starts) == set(ends) == set(range(count))
                cycles = (ends[count - 1] - starts[0]) // 12500
                intervals = [(ends[g] - ends[g - 1]) // 12500 for g in range(2, 7)]
                t8 = (ends[7] - starts[0]) // 12500
                predicted = t8 + 24 * statistics.median(intervals)
                key = "K" if op == 0 else "V"
                declared = comparison["summary"]["candidate" if mode == "candidate" else "sealed_baseline"][key]
                assert declared["actual_cycles"] == cycles
                assert declared["estimate_32_from_first_8"]["predicted_32_ps"] == predicted * 12500
                assert math.isclose(declared["efficiency"], count * 131072 / (160 * cycles), rel_tol=1e-12)
                for row in group_rows:
                    if row["mode"] == ("candidate" if mode == "candidate" else "sealed_baseline") and row["op"] == key:
                        group = int(row["group"])
                        assert int(row["dispatch_ps"]) == starts[group] and int(row["append_last_ps"]) == ends[group]
                metrics[mode][key] = {"groups": count, "cycles": cycles, "efficiency_percent": count * 131072 / (160 * cycles) * 100,
                                      "predicted32_cycles": predicted, "predicted32_efficiency_percent": 4194304 / (160 * predicted) * 100}
        assert images["candidate"] == images["baseline"]
        fields = ("command", "layer", "slot", "epoch", "position", "is_v", "head", "group", "meta", "s12")
        assert all(tuple(a[k] for k in fields) == tuple(b[k] for k in fields)
                   for a, b in zip(appends["candidate"], appends["baseline"]))
        for start in range(0, 640, 16):
            assert {int(r["slot"]) for r in appends["candidate"][start:start + 16]} == set(range(16))
        ca = builds["candidate"]["source_manifest"]["compile_files"]
        cb = builds["baseline"]["source_manifest"]["compile_files"]
        assert len(ca) == len(cb) == 83
        assert [i for i, (a, b) in enumerate(zip(ca, cb)) if a["sha256"] != b["sha256"]] == [9]
        assert manifests["candidate"]["input_manifest"] == manifests["baseline"]["input_manifest"]
        historical = comparison["historical_sealed_full_v32"]
        phase_name = relative(historical["phase_events_path"])
        assert index[phase_name]["sha256"] == historical["phase_events_sha256"]
        dispatch, end = [], []
        with bundle.open(phase_name) as binary:
            for row in csv.DictReader(io.TextIOWrapper(binary)):
                if row["event"] == "linear_tile_dispatch" and row["tile"] == "320":
                    dispatch.append(int(row["sim_time_ps"]))
                if row["event"] == "kv_append_last":
                    end.append(int(row["sim_time_ps"]))
        assert dispatch == [4707131250] and end == [5559706250]
        assert (end[0] - dispatch[0]) // 12500 == historical["actual_cycles"] == 68206
    return {"status": "PASS", "archive_name": path.name, "archive_bytes": expected["bytes"],
            "archive_sha256": expected["sha256"], "verified_files": len(index),
            "all_member_sha256_and_crc": "PASS", "kv_image_byte_exact": True,
            "append_records_compared": 640, "source_closure_same_except_top": True,
            "recomputed": metrics, "historical_baseline_v32_cycles": 68206,
            "v32_candidate_is_estimate": True, "does_not_run_rtl_or_board": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--download", type=Path, help="Download the public asset without authentication")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    expected = json.loads(args.manifest.read_text())
    path = args.archive
    if args.download:
        if path or args.download.exists():
            raise ValueError("Use a new download destination, without --archive")
        path = args.download
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".partial")
        try:
            with urlopen(Request(expected["asset_url"], headers={"User-Agent": "ScaleLLM-evidence-verifier"}), timeout=60) as source, temporary.open("xb") as target:
                while chunk := source.read(1 << 20):
                    target.write(chunk)
            if digest(temporary) != expected["sha256"]:
                raise ValueError("Downloaded archive SHA differs")
            temporary.replace(path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    if path is None:
        parser.error("Provide --archive or --download")
    result = verify(path, expected)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
