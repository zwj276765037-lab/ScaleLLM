#!/usr/bin/env python3
"""Bounded post-synthesis leaf verification of one actual board candidate."""

from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

import psutil


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
PROBE = ROOT.parent / "mlp_scalecode_dsp_probe"
REFERENCE = ROOT.parents[2] / "artifacts/verified_80mhz/hardware_agent/evidence/physical/final_decode16_011/source_snapshot/project/hardware/rtl/mlp/hap_a8w4_scalecode_recover2_lut.sv"
VIVADO = Path("/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado")
PART = "xcvu9p-flga2104-2L-e"
TOP = "hap_a8w4_scalecode_recover2_lut"
REFERENCE_SHA = "18a2bad1a3b7df345abfaf3428a8a5bec245d9580dc3b336e6153736a23a9f6a"
GIB = 1024**3
CPU_SET = (0, 1, 2, 3)
RSS_LIMIT = 16 * GIB
WALL_LIMIT = 1800
MEM_FLOOR = 64 * GIB
TASK_RSS_LIMIT = 384 * GIB
DISK_FLOOR = 30 * GIB
SIGNALS = (
    "s0_code_product0_u16_r",
    "s0_code_product1_u16_r",
    "s1_raw0_s33_r",
    "s1_raw1_s33_r",
)
YES = {"dsp_raw_only": set(SIGNALS[2:]), "dsp_all": set(SIGNALS)}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def verify_prior_run() -> dict:
    run = PROBE / "runs/mlp_sc_sim_20261113T081037Z_5219957a"
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["exit_code"] == 0 and manifest["stop_reason"] is None
    assert manifest["success_marker_found"]
    pinned = manifest["inputs_sha256"]
    for suffix in (
        "tb/mlp_sc_recover2_tb.sv",
        "rtl/mlp_sc_recover2_lut.sv",
        "rtl/mlp_sc_recover2_raw_dsp.sv",
        "rtl/mlp_sc_recover2_all_dsp.sv",
    ):
        path = PROBE / suffix
        assert pinned[str(path)] == sha(path), f"Prior input changed: {path}"
    assert pinned[str(REFERENCE)] == REFERENCE_SHA == sha(REFERENCE)
    text = (run / "vivado.log").read_text(errors="replace")
    expected = "SIM_STATS cycles=137353 directed=567 sweep=131072 random=4096 accepted_each=135747 emitted_each=135741 canceled_each=6 max_ii1=131072 latency_checks=394917 input_stall_cycles=1351 output_hold_cycles=1499 reset_edges=5 clear_edges=3 seed=6d2b79f5"
    assert expected in text
    assert "HARDWARE_AGENT_SIM_PASS mlp_sc_recover2_three_variants" in text
    assert not re.search(r"^(ERROR:|FATAL:)", text, re.M)
    return {
        "status": "REUSED_PRIOR_RTL_ONLY",
        "run": str(run),
        "manifest_sha256": sha(run / "manifest.json"),
        "testbench_sha256": sha(PROBE / "tb/mlp_sc_recover2_tb.sv"),
        "stats": expected,
    }


def verify_tb_adapter() -> dict:
    source = PROBE / "tb/mlp_sc_recover2_tb.sv"
    original = source.read_text()
    expected = original
    for name in ("mlp_sc_recover2_lut", "mlp_sc_recover2_raw_dsp", "mlp_sc_recover2_all_dsp"):
        expected = expected.replace(name + " u_", TOP + " u_")
    needle = "    initial begin : stimulus\n"
    assert expected.count(needle) == 1
    expected = expected.replace(needle, needle + "        // Allow the UNISIM glbl startup GSR to deassert before valid traffic.\n        #200;\n", 1)
    expected = expected.replace(
        "HARDWARE_AGENT_SIM_PASS mlp_sc_recover2_three_variants",
        "HARDWARE_AGENT_SIM_PASS mlp_sc_post_synth_candidate",
    )
    tb = HERE / "mlp_sc_post_synth_tb.sv"
    assert tb.read_text() == expected, "Testbench differs beyond permitted netlist adaptation"
    return {"path": str(tb), "sha256": sha(tb), "prior_sha256": sha(source),
            "changes": ["three instance module names", "200 ns GSR settling before stimulus", "success marker"]}


def verify_source(candidate: str) -> dict:
    source = ROOT / "runs" / candidate / "source/project/hardware/rtl/mlp/hap_a8w4_scalecode_recover2_lut.sv"
    actual = source.read_text()
    reference = REFERENCE.read_text()
    assert sha(REFERENCE) == REFERENCE_SHA
    normalized = actual
    attributes = {}
    for name in SIGNALS:
        lines = [line for line in normalized.splitlines(keepends=True)
                 if name in line and '(* use_dsp = ' in line]
        assert len(lines) == 1, f"Missing or duplicate attribute: {name}"
        line = lines[0]
        matches = re.findall(r'\(\* use_dsp = "(yes|no)" \*\)', line)
        assert len(matches) == 1, f"Malformed attribute: {name}"
        value = matches[0]
        assert (value == "yes") == (name in YES[candidate]), f"Wrong attribute: {name}={value}"
        attributes[name] = value
        normalized = normalized.replace(line, line.replace('use_dsp = "yes"', 'use_dsp = "no"'), 1)
    assert normalized == reference, "Candidate source differs from pinned production outside four attributes"
    assert actual.count(f"module {TOP} (") == 1
    return {"path": str(source), "sha256": sha(source),
            "normalized_reference_path": str(REFERENCE),
            "normalized_reference_sha256": REFERENCE_SHA,
            "normalized_equal": True, "attributes": attributes}


def own_tree(pid: int) -> list[psutil.Process]:
    try:
        parent = psutil.Process(pid)
        return [parent, *parent.children(recursive=True)]
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return []


def tree_rss(procs: list[psutil.Process]) -> int:
    total = 0
    for proc in procs:
        try:
            total += proc.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return total


def task_rss() -> int:
    matched = set()
    for proc in psutil.process_iter(["pid", "cmdline", "cwd"]):
        try:
            command = " ".join(proc.info["cmdline"] or [])
            cwd = proc.info["cwd"] or ""
            if str(ROOT) in command or cwd.startswith(str(ROOT / "runs")) or cwd.startswith(str(HERE)):
                matched.add(proc.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    total = 0
    for pid in matched:
        try:
            total += psutil.Process(pid).memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return total


def terminate_tree(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    time.sleep(3)
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def stage(stage_dir: Path, tcl: Path, args: list[Path], inputs: list[Path], marker: str) -> dict:
    stage_dir.mkdir(parents=True, exist_ok=False)
    assert psutil.virtual_memory().available >= MEM_FLOOR + RSS_LIMIT, "Insufficient memory headroom"
    assert psutil.disk_usage(str(HERE)).free >= DISK_FLOOR + GIB, "Insufficient disk headroom"
    assert task_rss() + RSS_LIMIT <= TASK_RSS_LIMIT, "Task RSS reservation exceeded"
    command = [str(VIVADO), "-mode", "batch", "-source", str(tcl),
               "-log", str(stage_dir / "vivado.log"),
               "-journal", str(stage_dir / "vivado.jou"),
               "-tclargs", str(stage_dir), *map(str, args)]
    manifest = {
        "start_utc": utc(), "command": command, "cwd": str(stage_dir),
        "inputs_sha256": {str(p): sha(p) for p in [Path(__file__), tcl, *inputs]},
        "tool": str(VIVADO), "tool_sha256": sha(VIVADO),
        "limits": {"cpu_affinity": CPU_SET, "nice_increment": 10, "max_threads": 4,
                   "tree_rss_bytes": RSS_LIMIT, "wall_seconds": WALL_LIMIT,
                   "min_mem_available_bytes": MEM_FLOOR, "min_disk_free_bytes": DISK_FLOOR,
                   "max_task_rss_bytes": TASK_RSS_LIMIT},
        "process_samples": str(stage_dir / "process_samples.jsonl"),
        "console_log": str(stage_dir / "console.log"),
        "vivado_log": str(stage_dir / "vivado.log"),
    }
    write_json(stage_dir / "manifest.json", manifest)

    def set_limits() -> None:
        os.sched_setaffinity(0, CPU_SET)
        os.nice(10)

    env = os.environ.copy()
    env.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    started = time.monotonic()
    reason = None
    peak = 0
    min_mem = 1 << 63
    min_disk = 1 << 63
    peak_task = 0
    with (stage_dir / "console.log").open("wb") as output, (stage_dir / "process_samples.jsonl").open("w") as samples:
        proc = subprocess.Popen(command, cwd=stage_dir, env=env, stdout=output,
                                stderr=subprocess.STDOUT, start_new_session=True,
                                preexec_fn=set_limits)
        manifest["pid"] = proc.pid
        write_json(stage_dir / "manifest.json", manifest)
        while proc.poll() is None:
            processes = own_tree(proc.pid)
            rss = tree_rss(processes)
            available = psutil.virtual_memory().available
            disk = psutil.disk_usage(str(HERE)).free
            task = task_rss()
            elapsed = time.monotonic() - started
            peak = max(peak, rss)
            peak_task = max(peak_task, task)
            min_mem = min(min_mem, available)
            min_disk = min(min_disk, disk)
            sample = {"elapsed_seconds": round(elapsed, 3), "pids": [p.pid for p in processes],
                      "tree_rss_bytes": rss, "task_rss_bytes": task,
                      "mem_available_bytes": available, "disk_free_bytes": disk}
            samples.write(json.dumps(sample) + "\n")
            samples.flush()
            if rss > RSS_LIMIT:
                reason = "tree_rss_limit"
            elif task > TASK_RSS_LIMIT:
                reason = "task_rss_limit"
            elif available < MEM_FLOOR:
                reason = "mem_available_floor"
            elif disk < DISK_FLOOR:
                reason = "disk_free_floor"
            elif elapsed > WALL_LIMIT:
                reason = "wall_time_limit"
            if reason:
                terminate_tree(proc.pid)
                break
            time.sleep(2)
        code = proc.wait()
    log = (stage_dir / "console.log").read_text(errors="replace")
    log_errors = re.findall(r"^(?:ERROR:|FATAL:).*?$", log, re.M | re.I)
    found = marker in log
    if reason is None and code != 0:
        reason = "nonzero_exit"
    if reason is None and log_errors:
        reason = "log_error"
    if reason is None and not found:
        reason = "success_marker_missing"
    manifest.update(end_utc=utc(), elapsed_seconds=round(time.monotonic() - started, 3),
                    exit_code=code, stop_reason=reason, peak_tree_rss_bytes=peak,
                    peak_task_rss_bytes=peak_task, min_mem_available_bytes=min_mem,
                    min_disk_free_bytes=min_disk, log_errors=log_errors[:20],
                    success_marker=marker, success_marker_found=found)
    write_json(stage_dir / "manifest.json", manifest)
    return manifest


def extract_stats(log_path: Path) -> dict:
    text = log_path.read_text(errors="replace")
    line = re.search(r"^SIM_STATS (.+)$", text, re.M)
    assert line, "Missing SIM_STATS"
    fields = dict(re.findall(r"(\w+)=([^ ]+)", line.group(1)))
    expected = {"directed": 567, "sweep": 131072, "random": 4096,
                "accepted_each": 135747, "emitted_each": 135741,
                "canceled_each": 6, "max_ii1": 131072,
                "latency_checks": 394917}
    for key, value in expected.items():
        assert int(fields[key]) == value, f"Coverage mismatch: {key}={fields[key]}"
    for key in ("input_stall_cycles", "output_hold_cycles", "reset_edges", "clear_edges"):
        assert int(fields[key]) > 0, f"Missing coverage: {key}"
    assert int(fields["accepted_each"]) == int(fields["emitted_each"]) + int(fields["canceled_each"])
    assert fields["seed"] == "6d2b79f5"
    return fields


def verify_tool_and_primitive(synth_log: Path, sim_log: Path) -> dict:
    synth = synth_log.read_text(errors="replace")
    sim = sim_log.read_text(errors="replace")
    synth_version = re.search(r"^LEAF_SYNTH_IDENTITY .* tool=(\S+)$", synth, re.M)
    sim_version = re.search(r"^LEAF_NETLIST_SIM_IDENTITY .* tool=(\S+)$", sim, re.M)
    assert synth_version and sim_version
    assert synth_version.group(1) == sim_version.group(1) == "2025.2"
    assert "-L unisims_ver" in sim
    assert "Compiling module unisims_ver.DSP48E2" in sim
    return {"name": "Vivado/XSim", "version": synth_version.group(1),
            "executable": str(VIVADO), "executable_sha256": sha(VIVADO),
            "primitive_model": "unisims_ver.DSP48E2",
            "model_compile_evidence_log": str(sim_log)}


def main(candidate: str) -> int:
    global CPU_SET
    if candidate not in YES:
        raise SystemExit("usage: run_leaf.py dsp_raw_only|dsp_all")
    CPU_SET = (24, 25, 26, 27) if candidate == "dsp_all" else (0, 1, 2, 3)
    output = HERE / candidate
    output.mkdir(exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    attempt = output / "attempts" / stamp
    attempt.mkdir(parents=True, exist_ok=False)
    result: dict = {"candidate": candidate, "status": "FAIL", "started_utc": utc(),
                    "attempt": str(attempt), "kind": "leaf_post_synthesis_functional"}
    lock = ROOT / "runs" / candidate / ".native.lock"
    try:
        with lock.open("a+") as lock_fd:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result["lease"] = {"path": str(lock), "pid": os.getpid(), "exclusive": True}
            result["source"] = verify_source(candidate)
            result["prior_rtl_evidence"] = verify_prior_run()
            result["testbench_adapter"] = verify_tb_adapter()
            assert VIVADO.is_file()
            assert set(CPU_SET).issubset(os.sched_getaffinity(0))
            synth_dir = attempt / "synth"
            result["synthesis"] = stage(synth_dir, HERE / "synth_leaf.tcl",
                                        [Path(result["source"]["path"])],
                                        [Path(result["source"]["path"]), REFERENCE],
                                        "LEAF_POST_SYNTH_EXPORT_PASS")
            assert result["synthesis"]["stop_reason"] is None, "Leaf synthesis failed"
            netlist = synth_dir / "post_synth_funcsim.v"
            dcp = synth_dir / "post_synth.dcp"
            assert netlist.is_file() and dcp.is_file()
            result["netlist"] = {"path": str(netlist), "sha256": sha(netlist),
                                 "dcp_path": str(dcp), "dcp_sha256": sha(dcp)}
            inventory = synth_dir / "dsp_inventory.tsv"
            result["dsp48e2_count"] = len(inventory.read_text().splitlines()) - 1
            assert result["dsp48e2_count"] > 0, "Synthesis did not map a DSP48E2"
            sim_dir = attempt / "sim"
            result["simulation"] = stage(sim_dir, HERE / "sim_netlist.tcl",
                                         [netlist, HERE / "mlp_sc_post_synth_tb.sv"],
                                         [netlist, HERE / "mlp_sc_post_synth_tb.sv"],
                                         "HARDWARE_AGENT_SIM_PASS mlp_sc_post_synth_candidate")
            assert result["simulation"]["stop_reason"] is None, "Netlist simulation failed"
            result["tool"] = verify_tool_and_primitive(synth_dir / "console.log", sim_dir / "console.log")
            result["coverage"] = extract_stats(sim_dir / "console.log")
            result["status"] = "PASS"
    except Exception as exc:
        result["failure"] = f"{type(exc).__name__}: {exc}"
    result["finished_utc"] = utc()
    write_json(output / "result.json", result)
    print(json.dumps({"candidate": candidate, "status": result["status"],
                      "result": str(output / "result.json"), "failure": result.get("failure")}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) == 2 else ""))
