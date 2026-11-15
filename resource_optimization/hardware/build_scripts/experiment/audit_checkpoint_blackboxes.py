#!/usr/bin/env python3
"""Record an independent zero-blackbox check for a preserved post-place DCP."""
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
TCL = ROOT / "scripts/audit_checkpoint_blackboxes.tcl"
NAMES = ("dsp_raw_only", "dsp_all")
GIB = 1024 ** 3


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main(name):
    work = ROOT / "runs" / name
    place = work / "place"
    receipt_path = place / "result.json"
    receipt = json.loads(receipt_path.read_text())
    native_pass = (receipt.get("returncode") == 0 and receipt.get("stop_reason") is None and
                   receipt.get("native_pass_marker"))
    if not native_pass:
        original_log = (place / "vivado.log").read_text(errors="replace")
        impl_log = (work / "create/project/scalellm_final_decode16.runs/impl_1/runme.log").read_text(errors="replace")
        probe = (work / "place_status_probe/console.log").read_text(errors="replace")
        known_wrapper_failure = (receipt.get("returncode") == 1 and
                                 receipt.get("stop_reason") is None and
                                 not receipt.get("changed_inputs") and
                                 not receipt.get("native_pass_marker") and
                                 "Placement or physical optimization failed" in original_log and
                                 "place_design completed successfully" in impl_log and
                                 "phys_opt_design completed successfully" in impl_log and
                                 "IMPL_RUN_STATUS=Not started route_design" in probe and
                                 "IMPL_RUN_PROGRESS=80%" in probe)
        if not known_wrapper_failure:
            raise ValueError("Native place stage differs from the known status-check failure")
        if (receipt.get("vivado_log_sha256") != sha(place / "vivado.log") or
                receipt.get("console_sha256") != sha(place / "console.log")):
            raise ValueError("Preserved native place log identity differs")
    dcp = place / "reports/place_design.dcp"
    digest = sha(dcp)
    if receipt.get("reports", {}).get("reports/place_design.dcp") != digest:
        raise ValueError("Post-place DCP hash differs from native place receipt")
    config = json.loads((work / "build.json").read_text())
    if run_board.total_candidate_rss() != 0:
        raise RuntimeError("A candidate implementation is still running")
    if run_board.mem_available() < 64 * GIB or shutil.disk_usage(work).free < 30 * GIB:
        raise RuntimeError("Insufficient RAM or disk for checkpoint inspection")
    out = work / "post_place_blackbox_audit_v2"
    out.mkdir(exist_ok=False)
    reports = out / "reports"
    reports.mkdir()
    env = os.environ.copy()
    env.update(HAP_SOURCE_DCP=str(dcp), HAP_SOURCE_DCP_SHA256=digest,
               HAP_REPORT_DIR=str(reports), OMP_NUM_THREADS="4")
    command = [config["vivado"], "-mode", "batch", "-notrace", "-source", str(TCL),
               "-log", str(out / "vivado.log"), "-journal", str(out / "vivado.jou")]
    inputs = dict(candidate=name, stage="post_place_blackbox_audit",
                  checkpoint=str(dcp), checkpoint_sha256=digest,
                  original_native_status="PASS" if native_pass else "FAIL_RETAINED_STATUS_CHECK",
                  native_place_result=str(receipt_path), native_place_result_sha256=sha(receipt_path),
                  audit_script_sha256=sha(Path(__file__)), audit_tcl_sha256=sha(TCL), command=command)
    (out / "stage_inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
    started = time.monotonic()
    peak_rss = 0
    minimum_mem = run_board.mem_available()
    minimum_disk = shutil.disk_usage(work).free
    stop_reason = None
    with (out / "console.log").open("w") as console:
        proc = subprocess.Popen(command, cwd=out, env=env, stdout=console,
                                stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while proc.poll() is None:
                peak_rss = max(peak_rss, run_board.process_tree(proc.pid))
                minimum_mem = min(minimum_mem, run_board.mem_available())
                minimum_disk = min(minimum_disk, shutil.disk_usage(work).free)
                if time.monotonic() - started > 1800:
                    stop_reason = "wall time limit"
                elif peak_rss > 192 * GIB:
                    stop_reason = "RSS limit"
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
    boxes = reports / "blackboxes.tsv"
    passed = (proc.returncode == 0 and stop_reason is None and
              "CHECKPOINT_BLACKBOX_PASS count=0" in log and
              boxes.is_file() and boxes.read_text().splitlines() == ["name\tref_name"] and
              sha(dcp) == digest)
    result = dict(schema="scalellm_dsp_post_place_blackbox_audit_v2", candidate=name,
                  status="PASS" if passed else "FAIL", returncode=proc.returncode,
                  stop_reason=stop_reason, peak_tree_rss_bytes=peak_rss,
                  minimum_mem_available_bytes=minimum_mem,
                  minimum_disk_free_bytes=minimum_disk,
                  checkpoint=str(dcp), checkpoint_sha256=digest,
                  native_place_result_sha256=inputs["native_place_result_sha256"],
                  stage_inputs_sha256=sha(out / "stage_inputs.json"),
                  console_sha256=sha(out / "console.log"),
                  vivado_log_sha256=sha(out / "vivado.log") if (out / "vivado.log").is_file() else None,
                  blackboxes_sha256=sha(boxes) if boxes.is_file() else None,
                  elapsed_seconds=round(time.monotonic() - started, 3))
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", choices=NAMES)
    main(parser.parse_args().candidate)
