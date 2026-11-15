#!/usr/bin/env python3
"""Qualify a preserved complete synth_1 result with its known debug placeholder."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

import run_board
from select_candidate import count_recovery_primitives, number, parse_recovery_hierarchy, row

ROOT = Path(__file__).resolve().parents[1]
TCL = ROOT / "scripts/qualify_synth.tcl"
GIB = 1024 ** 3
CPUS = {"dsp_raw_only": list(range(24)) + list(range(48, 72)),
        "dsp_all": list(range(24, 48)) + list(range(72, 96))}
EXPECTED = {"dsp_raw_only": 192, "dsp_all": 384}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main(name):
    work = ROOT / "runs" / name
    with (work / ".native.lock").open("a") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        cfg = json.loads((work / "build.json").read_text())
        run_board.verify_candidate(work, cfg)
        original = work / "synth"
        receipt = original / "result.json"
        old = json.loads(receipt.read_text())
        if (old.get("returncode") != 1 or old.get("stop_reason") is not None or
                old.get("changed_inputs") or old.get("native_pass_marker") or
                (original / "reports/blackboxes.txt").read_text() != "dbg_hub\n"):
            raise ValueError("Original failure is not the expected single debug placeholder")
        log = (original / "vivado.log").read_text(errors="replace")
        if ("Unresolved blackboxes: 1" not in log or
                "RECOVERY_LEAF_QUERY_COUNT stage=synth count=96" not in log or
                "synth_1 finished" not in log or "write_checkpoint:" not in log):
            raise ValueError("Original native synthesis evidence is incomplete")
        if old["vivado_log_sha256"] != sha(original / "vivado.log") or old["console_sha256"] != sha(original / "console.log"):
            raise ValueError("Original synthesis log hash changed")
        reports = original / "reports"
        dcp = reports / "synthesized.dcp"
        for rel, digest in old["reports"].items():
            if sha(original / rel) != digest:
                raise ValueError("Original synthesis report changed: " + rel)
        hierarchy = parse_recovery_hierarchy((reports / "utilization_hierarchical.rpt").read_text(errors="replace"))
        whole_board_dsp = number(row((reports / "utilization.rpt").read_text(errors="replace"), "DSPs")[0])
        counts, inventory_total, legacy_total = count_recovery_primitives(
            (reports / "recovery_mapping.tsv").read_text(errors="replace"),
            (reports / "dsp_inventory.tsv").read_text(errors="replace"))
        if (len(hierarchy) != 96 or any(row["dsp"] != EXPECTED[name] // 96 for row in hierarchy) or
                len(counts) != 96 or any(count != EXPECTED[name] // 96 for count in counts.values()) or
                sum(counts.values()) != EXPECTED[name] or inventory_total != whole_board_dsp or
                legacy_total != 0):
            raise ValueError("Original recovery hierarchy or primitive mapping differs")
        if run_board.mem_available() < 64 * GIB or shutil.disk_usage(work).free < 30 * GIB:
            raise RuntimeError("Insufficient RAM or disk for checkpoint revalidation")

        out = work / "synth_qualified"
        if out.exists():
            raise FileExistsError("Qualification attempt already exists: " + str(out))
        out.mkdir()
        subreports = out / "reports"
        subreports.mkdir()
        inputs = dict(candidate=name, original_result=str(receipt), original_result_sha256=sha(receipt),
                      source_checkpoint=str(dcp), source_checkpoint_sha256=sha(dcp),
                      candidate_manifest_sha256=sha(work / "candidate_manifest.json"),
                      build_json_sha256=sha(work / "build.json"),
                      qualification_driver_sha256=sha(Path(__file__)), qualification_tcl_sha256=sha(TCL),
                      recovery_leaves=96, recovery_dsp=EXPECTED[name],
                      whole_board_dsp=inventory_total, original_mapping_export_dsp=legacy_total)
        (out / "stage_inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
        env = os.environ.copy()
        env.update(HAP_SOURCE_DCP=str(dcp), HAP_SOURCE_DCP_SHA256=inputs["source_checkpoint_sha256"],
                   HAP_REPORT_DIR=str(subreports), OMP_NUM_THREADS="4")
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
        reason = None
        with (out / "console.log").open("w") as console:
            proc = subprocess.Popen(command, cwd=out, env=env, stdout=console, stderr=subprocess.STDOUT,
                                    start_new_session=True, preexec_fn=setup)
            (out / "progress.json").write_text(json.dumps(dict(candidate=name, stage="synth_qualified",
                pid=proc.pid, status="RUNNING", started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                command=command, cpus=cpus, threads=4, timeout_seconds=1800, rss_limit_gib=192), indent=2) + "\n")
            try:
                while proc.poll() is None:
                    peak = max(peak, run_board.process_tree(proc.pid))
                    minimum_mem = min(minimum_mem, run_board.mem_available())
                    minimum_disk = min(minimum_disk, shutil.disk_usage(work).free)
                    if time.monotonic() - started > 1800:
                        reason = "wall time limit"
                    elif peak > 192 * GIB:
                        reason = "RSS limit"
                    elif run_board.total_candidate_rss() > 384 * GIB:
                        reason = "combined candidate RSS limit"
                    elif minimum_mem < 64 * GIB:
                        reason = "available memory floor"
                    elif minimum_disk < 30 * GIB:
                        reason = "free disk floor"
                    if reason:
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
        probe_log = (out / "console.log").read_text(errors="replace")
        boxes = subreports / "blackboxes.tsv"
        cores = subreports / "debug_cores.tsv"
        if proc.returncode == 0 and reason is None:
            if "SYNTH_DCP_PROBE_COMPLETE" not in probe_log:
                reason = "missing native probe marker"
            elif not boxes.is_file() or boxes.read_text().splitlines() != ["name\tref_name", "dbg_hub\tdbg_hub_CV"]:
                reason = "current DCP blackbox identity differs"
            elif not cores.is_file() or not any(line.split("\t")[0] == "dbg_hub" for line in cores.read_text().splitlines()[1:]):
                reason = "current DCP debug core query did not identify dbg_hub"
            elif sha(dcp) != inputs["source_checkpoint_sha256"]:
                reason = "synthesized checkpoint changed during qualification"
        result = dict(stage="synth_qualified", candidate=name, returncode=proc.returncode,
            stop_reason=reason, native_pass_marker="SYNTH_DCP_PROBE_COMPLETE" in probe_log,
            original_synth_result=str(receipt), original_synth_result_sha256=inputs["original_result_sha256"],
            source_checkpoint=str(dcp), source_checkpoint_sha256=inputs["source_checkpoint_sha256"],
            classification="OPEN_DEBUG_PLACEHOLDER" if reason is None and proc.returncode == 0 else None,
            physical_blackbox_requirement="ZERO", recovery_leaves=96, recovery_dsp=EXPECTED[name],
            whole_board_dsp=inventory_total, original_mapping_export_dsp=legacy_total,
            elapsed_seconds=round(time.monotonic() - started, 3), peak_tree_rss_bytes=peak,
            minimum_mem_available_bytes=minimum_mem, minimum_disk_free_bytes=minimum_disk,
            stage_inputs_sha256=sha(out / "stage_inputs.json"), console_sha256=sha(out / "console.log"),
            vivado_log_sha256=sha(out / "vivado.log") if (out / "vivado.log").is_file() else None,
            reports={str(path.relative_to(out)): sha(path) for path in subreports.rglob("*") if path.is_file()})
        (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        progress = json.loads((out / "progress.json").read_text())
        progress.update(status="PASS" if proc.returncode == 0 and reason is None else "FAIL", result=str(out / "result.json"))
        (out / "progress.json").write_text(json.dumps(progress, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        if proc.returncode or reason:
            raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", choices=tuple(CPUS))
    main(parser.parse_args().candidate)
