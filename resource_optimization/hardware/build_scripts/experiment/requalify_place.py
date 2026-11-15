#!/usr/bin/env python3
"""Re-report preserved post-physopt DCPs after the native run-status mismatch."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

import run_board

ROOT = Path(__file__).resolve().parents[1]
TCL = ROOT / "scripts/recovery_physical_report.tcl"
CPUS = {"dsp_raw_only": list(range(24)) + list(range(48, 72)),
        "dsp_all": list(range(24, 48)) + list(range(72, 96))}
GIB = 1024 ** 3


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def preserved_place(work):
    path = work / "place/result.json"
    original = json.loads(path.read_text())
    if (original.get("returncode") != 1 or original.get("stop_reason") is not None or
            original.get("changed_inputs") or original.get("native_pass_marker") or
            original.get("stage_inputs_sha256") != sha(work / "place/stage_inputs.json") or
            original.get("vivado_log_sha256") != sha(work / "place/vivado.log") or
            original.get("console_sha256") != sha(work / "place/console.log")):
        raise ValueError("Original place receipt differs from preserved status-check failure")
    native_log = (work / "create/project/scalellm_final_decode16.runs/impl_1/runme.log").read_text(errors="replace")
    wrapper_log = (work / "place/vivado.log").read_text(errors="replace")
    probe = (work / "place_status_probe/console.log").read_text(errors="replace")
    if ("place_design completed successfully" not in native_log or
            "phys_opt_design completed successfully" not in native_log or
            "Placement or physical optimization failed" not in wrapper_log or
            "IMPL_RUN_STATUS=Not started route_design" not in probe or
            "IMPL_RUN_PROGRESS=80%" not in probe or
            "ERROR:" in probe or "CRITICAL WARNING:" in probe):
        raise ValueError("Native implementation or independent run-status evidence differs")
    expected = {"reports/opt_design.dcp", "reports/place_design.dcp",
                "reports/phys_opt_design.dcp", "reports/blackboxes_post_opt.tsv"}
    if set(original.get("reports", {})) != expected:
        raise ValueError("Original place checkpoint set differs")
    for rel in expected:
        if original["reports"][rel] != sha(work / "place" / rel):
            raise ValueError("Original place checkpoint/report hash differs: " + rel)
    if (work / "place/reports/blackboxes_post_opt.tsv").read_text().splitlines() != ["name\tref_name"]:
        raise ValueError("Original post-opt design contains blackboxes")
    return original


def main(name, audit_path):
    work = ROOT / "runs" / name
    cfg = json.loads((work / "build.json").read_text())
    run_board.verify_candidate(work, cfg)  # Original candidate scripts and source manifest remain unchanged.
    original = preserved_place(work)
    audit_path = audit_path.resolve()
    if audit_path.parent.parent != work or audit_path.name != "result.json":
        raise ValueError("Audit receipt is not inside this candidate")
    audit = json.loads(audit_path.read_text())
    if (audit.get("status") != "PASS" or audit.get("candidate") != name or
            audit.get("native_place_result_sha256") != sha(work / "place/result.json") or
            audit.get("checkpoint_sha256") != original["reports"]["reports/place_design.dcp"]):
        raise ValueError("Independent post-place blackbox audit differs")
    if run_board.total_candidate_rss() > 384 * GIB or run_board.mem_available() < 64 * GIB:
        raise RuntimeError("Insufficient available memory for DCP re-reporting")
    if shutil.disk_usage(work).free < 30 * GIB:
        raise RuntimeError("Insufficient disk for DCP re-reporting")
    out = work / "place_qualified"
    out.mkdir(exist_ok=False)
    reports = out / "reports"
    reports.mkdir()
    dcp = work / "place/reports/phys_opt_design.dcp"
    digest = sha(dcp)
    inputs = dict(candidate=name, stage="place_qualified", original_place_result=str(work / "place/result.json"),
                  original_place_result_sha256=sha(work / "place/result.json"),
                  status_probe_console_sha256=sha(work / "place_status_probe/console.log"),
                  post_place_audit_result=str(audit_path), post_place_audit_result_sha256=sha(audit_path),
                  source_checkpoint=str(dcp), source_checkpoint_sha256=digest,
                  candidate_build_json_sha256=sha(work / "build.json"),
                  candidate_manifest_sha256=sha(work / "candidate_manifest.json"),
                  original_candidate_driver_sha256=sha(ROOT / "scripts/run_board.py"),
                  original_candidate_tcl_sha256=sha(ROOT / "scripts/build_board.tcl"),
                  report_driver_sha256=sha(Path(__file__)), report_tcl_sha256=sha(TCL),
                  release_reports_tcl_sha256=sha(work / "source/project/hardware/vivado/scripts/release_reports.tcl"))
    (out / "stage_inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
    env = os.environ.copy()
    env.update(HAP_HW_ROOT=str(work / "source/project/hardware"), HAP_SOURCE_DCP=str(dcp),
               HAP_SOURCE_DCP_SHA256=digest, HAP_REPORT_DIR=str(reports),
               HAP_JOBS="32", OMP_NUM_THREADS="32")
    command = [cfg["vivado"], "-mode", "batch", "-notrace", "-source", str(TCL),
               "-log", str(out / "vivado.log"), "-journal", str(out / "vivado.jou")]
    cpus = CPUS[name]
    def setup():
        os.sched_setaffinity(0, cpus)
        os.nice(10)
    started = time.monotonic()
    peak = 0
    minimum_mem = run_board.mem_available()
    minimum_disk = shutil.disk_usage(work).free
    stop_reason = None
    with (out / "console.log").open("w") as console:
        proc = subprocess.Popen(command, cwd=out, env=env, stdout=console,
                                stderr=subprocess.STDOUT, start_new_session=True, preexec_fn=setup)
        (out / "progress.json").write_text(json.dumps(dict(stage="place_qualified", candidate=name,
            pid=proc.pid, status="RUNNING", command=command, cpus=cpus, threads=32,
            started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            timeout_seconds=3600, rss_limit_gib=192), indent=2) + "\n")
        try:
            while proc.poll() is None:
                peak = max(peak, run_board.process_tree(proc.pid))
                minimum_mem = min(minimum_mem, run_board.mem_available())
                minimum_disk = min(minimum_disk, shutil.disk_usage(work).free)
                if time.monotonic() - started > 3600:
                    stop_reason = "wall time limit"
                elif peak > 192 * GIB:
                    stop_reason = "RSS limit"
                elif run_board.total_candidate_rss() > 384 * GIB:
                    stop_reason = "combined candidate RSS limit"
                elif minimum_mem < 64 * GIB:
                    stop_reason = "available memory floor"
                elif minimum_disk < 30 * GIB:
                    stop_reason = "free disk floor"
                if stop_reason:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait()
                    break
                time.sleep(1)
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=15)
    log = (out / "console.log").read_text(errors="replace")
    if proc.returncode == 0 and stop_reason is None:
        if "PLACE_DCP_REQUALIFIED_PASS blackboxes=0" not in log:
            stop_reason = "missing native pass marker"
        elif (reports / "blackboxes.txt").read_text().strip():
            stop_reason = "post-physopt DCP has blackboxes"
        elif sha(dcp) != digest:
            stop_reason = "source checkpoint changed"
    result = dict(stage="place_qualified", candidate=name, returncode=proc.returncode,
                  stop_reason=stop_reason, native_pass_marker="PLACE_DCP_REQUALIFIED_PASS blackboxes=0" in log,
                  source_checkpoint={"path":str(dcp), "sha256":digest},
                  original_place_result_sha256=inputs["original_place_result_sha256"],
                  post_place_audit_result_sha256=inputs["post_place_audit_result_sha256"],
                  elapsed_seconds=round(time.monotonic() - started, 3), peak_tree_rss_bytes=peak,
                  minimum_mem_available_bytes=minimum_mem, minimum_disk_free_bytes=minimum_disk,
                  stage_inputs_sha256=sha(out / "stage_inputs.json"),
                  console_sha256=sha(out / "console.log"),
                  vivado_log_sha256=sha(out / "vivado.log") if (out / "vivado.log").is_file() else None,
                  reports={str(p.relative_to(out)):sha(p) for p in reports.rglob("*") if p.is_file()})
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    progress = json.loads((out / "progress.json").read_text())
    progress.update(status="PASS" if proc.returncode == 0 and stop_reason is None else "FAIL",
                    result=str(out / "result.json"))
    (out / "progress.json").write_text(json.dumps(progress, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if proc.returncode or stop_reason:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", choices=tuple(CPUS))
    parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args()
    main(args.candidate, args.audit)
