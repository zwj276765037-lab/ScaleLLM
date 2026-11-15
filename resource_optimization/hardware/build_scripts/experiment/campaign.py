#!/usr/bin/env python3
"""Persist and continue the two-candidate board build through guarded bit generation."""
import fcntl
import hashlib
import calendar
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
RUNNER = ROOT / "scripts/run_board.py"
STATE = RUNS / "campaign_state.json"
RAW_CPUS = list(range(24)) + list(range(48, 72))
ALL_CPUS = list(range(24, 48)) + list(range(72, 96))
FULL_CPUS = list(range(96))
CPUS = {"dsp_raw_only": RAW_CPUS, "dsp_all": ALL_CPUS}
LOCK = threading.Lock()
STATUS = {"schema": "scalellm_dsp_board_campaign_v1", "pid": None, "status": "STARTING", "events": []}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_status(event=None):
    with LOCK:
        if event is not None:
            STATUS["events"].append(dict(utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **event))
        temp = STATE.with_suffix(".tmp")
        temp.write_text(json.dumps(STATUS, indent=2) + "\n")
        temp.replace(STATE)


def valid_native_result(name, stage):
    path = RUNS / name / stage / "result.json"
    if not path.is_file():
        return None
    value = json.loads(path.read_text())
    return value if value.get("returncode") == 0 and value.get("stop_reason") is None and value.get("native_pass_marker") else False


def wait_existing(name, stage, seconds=3600):
    deadline = time.monotonic() + seconds
    path = RUNS / name / stage / "result.json"
    while time.monotonic() < deadline:
        state = valid_native_result(name, stage)
        if state is not None:
            if state is False:
                raise RuntimeError("Existing native stage failed: " + str(path))
            save_status(dict(candidate=name, stage=stage, status="PASS", result=str(path)))
            return state
        time.sleep(10)
    raise TimeoutError("Existing native stage produced no result: " + str(path))


def adopt_running_stage(name, stage, timeout):
    work = RUNS/name
    progress_path = work/stage/"progress.json"
    inputs_path = work/stage/"stage_inputs.json"
    if not progress_path.is_file() or not inputs_path.is_file():
        raise RuntimeError("Existing stage lacks live progress/input identity")
    progress = json.loads(progress_path.read_text())
    inputs = json.loads(inputs_path.read_text())
    if progress.get("status") != "RUNNING" or progress.get("candidate") != name or progress.get("stage") != stage:
        raise RuntimeError("Existing stage is not the expected running candidate")
    if (inputs.get("candidate") != name or inputs.get("stage") != stage or
            inputs.get("candidate_manifest_sha256") != sha(work/"candidate_manifest.json") or
            inputs.get("build_json_sha256") != sha(work/"build.json")):
        raise RuntimeError("Existing running stage input identity differs")
    pid = int(progress["pid"])
    try:
        cmdline = (Path("/proc")/str(pid)/"cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
    except FileNotFoundError as exc:
        raise RuntimeError("Existing stage PID is no longer alive") from exc
    expected_log = str(work/stage/"vivado.log")
    if "vivado" not in cmdline or expected_log not in cmdline or str(inputs["stage_tcl_sha256"]) != sha(Path(progress["command"][5])):
        raise RuntimeError("Existing stage PID/command/Tcl identity differs")
    started = calendar.timegm(time.strptime(progress["started_utc"], "%Y-%m-%dT%H:%M:%SZ"))
    remaining = max(1, int(timeout - (time.time() - started) + 600))
    save_status(dict(candidate=name, stage=stage, status="ADOPTED_RUNNING", vivado_pid=pid,
                     remaining_wait_seconds=remaining, progress=str(progress_path)))
    return wait_existing(name, stage, seconds=remaining)


def wait_functional(name, seconds=5400):
    path = ROOT / "functional" / name / "result.json"
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if path.is_file():
            result = json.loads(path.read_text())
            good = result.get("status") == "PASS" or result.get("result") == "PASS" or result.get("pass") is True
            expected = json.loads((RUNS/name/"build.json").read_text())["candidate_leaf"]["sha256"]
            identified = result.get("candidate") == name and result.get("source", {}).get("sha256") == expected
            if not good or not identified:
                raise RuntimeError("Candidate functional result failed or identity differs: " + str(path))
            save_status(dict(candidate=name, stage="functional", status="PASS", result=str(path), sha256=sha(path)))
            return result
        time.sleep(10)
    raise TimeoutError("No candidate functional result: " + str(path))


def run_native(name, stage, *, threads, jobs=1, rss=192, timeout=1800, cpus=None, source_dcp=None, timing_failure_ok=False):
    existing = valid_native_result(name, stage)
    if existing is not None:
        if existing is False:
            path = RUNS/name/stage/"result.json"
            if timing_failure_ok and path.is_file():
                result = json.loads(path.read_text())
                if result.get("stop_reason") is None:
                    save_status(dict(candidate=name, stage=stage, status="REUSED_REVIEW_REQUIRED", result=str(path)))
                    return result
            raise RuntimeError("Cannot overwrite failed native stage: " + name + "/" + stage)
        save_status(dict(candidate=name, stage=stage, status="REUSED_PASS", result=str(RUNS/name/stage/"result.json")))
        return existing
    work = RUNS / name
    if (work / stage).exists():
        progress_path = work/stage/"progress.json"
        if progress_path.is_file() and json.loads(progress_path.read_text()).get("status") == "RUNNING":
            return adopt_running_stage(name, stage, timeout)
        raise RuntimeError("Preserved attempt exists without a passing result: " + str(work/stage))
    cpus = cpus if cpus is not None else CPUS[name]
    cmd = [sys.executable, str(RUNNER), "stage", "--work", str(work), "--stage", stage,
           "--threads", str(threads), "--ip-jobs", str(jobs), "--cpus", ",".join(map(str, cpus)),
           "--timeout", str(timeout), "--rss-gib", str(rss)]
    if source_dcp is not None:
        cmd += ["--source-dcp", str(source_dcp)]
    log_path = RUNS / ("campaign_" + name + "_" + stage + ".log")
    with log_path.open("w") as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        save_status(dict(candidate=name, stage=stage, status="RUNNING", runner_pid=proc.pid,
                         log=str(log_path), command=cmd))
        code = proc.wait()
    result_path = work / stage / "result.json"
    if not result_path.is_file():
        raise RuntimeError("Native stage produced no result (runner exit %d): %s" % (code, log_path))
    result = json.loads(result_path.read_text())
    good = code == 0 and result.get("returncode") == 0 and result.get("stop_reason") is None and result.get("native_pass_marker")
    if not good:
        save_status(dict(candidate=name, stage=stage, status="FAIL", result=str(result_path), runner_exit=code))
        if not timing_failure_ok or result.get("stop_reason") is not None:
            raise RuntimeError("Native stage failed: " + str(result_path))
    else:
        save_status(dict(candidate=name, stage=stage, status="PASS", result=str(result_path)))
    return result


def prepare_candidate(name):
    wait_existing(name, "create")
    wait_functional(name)
    run_native(name, "synth", threads=4, jobs=6, timeout=10800)
    run_native(name, "place", threads=32, timeout=28800)


def timing_from(name, stage):
    from select_candidate import parse_timing
    path = RUNS / name / stage / "reports/timing_summary.rpt"
    if not path.is_file():
        raise RuntimeError("Missing physical timing report: " + str(path))
    return parse_timing(path.read_text(errors="replace"))


def closed(timing):
    return (timing["wns"] >= 0 and timing["tns"] == 0 and timing["setup_fail"] == 0
            and timing["whs"] >= 0 and timing["ths"] == 0 and timing["hold_fail"] == 0
            and timing["wpws"] >= 0 and timing["tpws"] == 0 and timing["pulse_fail"] == 0)


def setup_clean(timing):
    return timing["wns"] >= 0 and timing["tns"] == 0 and timing["setup_fail"] == 0


def hold_failure_only(timing):
    return (setup_clean(timing) and timing["wpws"] >= 0 and timing["tpws"] == 0
            and timing["pulse_fail"] == 0 and
            (timing["whs"] < 0 or timing["ths"] < 0 or timing["hold_fail"] > 0))


def remaining_seconds(total, *elapsed):
    remaining = int(total - sum(elapsed) - 1)
    if remaining < 1:
        raise RuntimeError("No remaining shared wall-time budget")
    return remaining


def routed_checkpoint(name, stage):
    path = RUNS/name/stage/"reports/routed.dcp"
    if not path.is_file():
        raise RuntimeError("No preserved routed checkpoint: " + str(path))
    return path


def run_physical(name):
    place = json.loads((RUNS/name/"place/result.json").read_text())
    remaining = remaining_seconds(28800, place["elapsed_seconds"])
    route = run_native(name, "route", threads=32, rss=384, timeout=remaining,
                       cpus=FULL_CPUS, timing_failure_ok=True)
    timing = timing_from(name, "route")
    gate = RUNS/name/"route/reports/timing_gate.txt"
    status = RUNS/name/"route/reports/route_status_pre_gate.rpt"
    if route["returncode"] != 0 and (not gate.is_file() or not status.is_file()):
        raise RuntimeError("Routing failed before the physical timing gate")
    checkpoint = routed_checkpoint(name, "route")
    accepted_stage = "route"
    if route["returncode"] != 0 and closed(timing):
        raise RuntimeError("Route timing numbers closed but native route/DRC gate failed")
    if not closed(timing):
        if not hold_failure_only(timing):
            raise RuntimeError("Route has setup/pulse failures or a non-hold physical gate error")
        detail = (RUNS/name/"route/reports/timing_summary.rpt").read_text(errors="replace")
        cross_slr = any(word in detail.lower() for word in ("laguna", "triple_slr", "/slr_"))
        if cross_slr:
            sll = run_native(name, "hold-sll", threads=32, rss=384, timeout=7199,
                             cpus=FULL_CPUS, source_dcp=checkpoint, timing_failure_ok=True)
            checkpoint = routed_checkpoint(name, "hold-sll")
            timing = timing_from(name, "hold-sll")
            accepted_stage = "hold-sll"
            if sll["returncode"] != 0 and not hold_failure_only(timing):
                raise RuntimeError("SLR hold repair did not leave a hold-only gate failure")
        if not closed(timing):
            used = 0
            prior = RUNS/name/"hold-sll/result.json"
            if prior.is_file():
                used = json.loads(prior.read_text())["elapsed_seconds"]
            remaining_hold = remaining_seconds(7200, used)
            hold = run_native(name, "hold", threads=32, rss=384, timeout=remaining_hold,
                              cpus=FULL_CPUS, source_dcp=checkpoint, timing_failure_ok=True)
            checkpoint = routed_checkpoint(name, "hold")
            timing = timing_from(name, "hold")
            accepted_stage = "hold"
            if hold["returncode"] != 0 or not closed(timing):
                raise RuntimeError("Final hold repair did not pass physical timing gate")
    if not closed(timing):
        raise RuntimeError("Final selected checkpoint lacks global timing closure")
    if not valid_native_result(name, accepted_stage):
        raise RuntimeError("Final selected checkpoint did not pass native route/timing/DRC guards")
    save_status(dict(candidate=name, stage="physical_acceptance", status="PASS", checkpoint=str(checkpoint),
                     checkpoint_sha256=sha(checkpoint), timing=timing))
    result = run_native(name, "bitstream", threads=32, rss=384, timeout=2400,
                        cpus=FULL_CPUS, source_dcp=checkpoint)
    bit = RUNS/name/"bitstream/reports/ScaleLLM_Final_Decode16_80MHz.bit"
    if not bit.is_file() or bit.stat().st_size == 0:
        raise RuntimeError("Bit stage passed without a nonempty candidate bitstream")
    output = dict(schema="scalellm_dsp_board_final_v1", candidate=name, bitstream=str(bit),
                  bitstream_sha256=sha(bit), bitstream_bytes=bit.stat().st_size,
                  input_checkpoint=str(checkpoint), input_checkpoint_sha256=sha(checkpoint),
                  bit_result=str(RUNS/name/"bitstream/result.json"), bit_result_sha256=sha(RUNS/name/"bitstream/result.json"),
                  timing=timing, board_programming="NOT_RUN")
    (RUNS/"final_artifact.json").write_text(json.dumps(output, indent=2) + "\n")
    return output


def main():
    with (RUNS/".campaign.lock").open("a") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX|fcntl.LOCK_NB)
        STATUS.update(pid=__import__("os").getpid(), status="RUNNING", script_sha256=sha(Path(__file__)),
                      runner_sha256=sha(RUNNER), selector_sha256=sha(ROOT/"scripts/select_candidate.py"),
                      started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        save_status(dict(status="CAMPAIGN_STARTED"))
        results = {}
        workers = {}
        def wrapped(name):
            try:
                prepare_candidate(name)
                results[name] = "PASS"
            except BaseException as exc:
                results[name] = "FAIL: " + str(exc)
                save_status(dict(candidate=name, status="CANDIDATE_FAILED", error=str(exc)))
        for name in ("dsp_raw_only", "dsp_all"):
            workers[name] = threading.Thread(target=wrapped, args=(name,), name=name)
            workers[name].start()
        for thread in workers.values():
            thread.join()
        from select_candidate import select
        selection = select()
        save_status(dict(stage="selection", status="PASS", candidate=selection["candidate"],
                         reason=selection["reason"], result=str(RUNS/"selection.json")))
        output = run_physical(selection["candidate"])
        STATUS.update(status="PASS", finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                      final_artifact=str(RUNS/"final_artifact.json"))
        save_status(dict(stage="bitstream", status="PASS", bitstream=output["bitstream"],
                         bitstream_sha256=output["bitstream_sha256"]))


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        STATUS.update(status="FAIL", error=str(exc), traceback=traceback.format_exc(),
                      finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        save_status(dict(status="CAMPAIGN_FAILED", error=str(exc)))
        raise
