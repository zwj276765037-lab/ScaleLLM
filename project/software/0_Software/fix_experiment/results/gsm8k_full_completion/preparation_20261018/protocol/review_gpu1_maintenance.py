#!/usr/bin/env python3
"""CPU-only source and bounded mock review; never invoke maintenance main."""
import contextlib
import datetime
import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
DIRECTORY = HERE.parent / "gpu1_maintenance_20261018"
EXPECTED = "2249afac1537e04a993e55f6cf75a30d3df0030a0ea7c7bc663d0b94527ca15a"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def main():
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == ""
    assert set(os.sched_getaffinity(0)) == {8, 9}
    helper = DIRECTORY / "gpu1_maintenance.py"
    testfile = DIRECTORY / "test_helper_mock.py"
    assert sha(helper) == EXPECTED
    m = module(helper, "maintenance_independent_review")
    t = module(testfile, "maintenance_author_tests_review")
    author_receipt = json.loads((DIRECTORY / "mock_results.json").read_text())
    assert author_receipt["helper_sha256"] == EXPECTED
    assert author_receipt["test_source_sha256"] == sha(testfile)
    log = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(t.Cases)
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    assert result.wasSuccessful() and result.testsRun == 21
    checks = []

    def check(name, condition, detail=None):
        checks.append({"name": name, "passed": bool(condition), "detail": detail})
        assert condition, name

    for display in (":0", ":0.0", ":0.9", ":00.0", "localhost:0", "unix:0", "0", ":01.0"):
        session = {"Service": "xrdp-sesman", "Seat": "", "Display": display, "ControlGroup": "/review/xrdp"}
        process = {"display_environment": {"DISPLAY": display, "XAUTHORITY": "/review/.Xauthority", "WAYLAND_DISPLAY": None}, "cgroups": ["/review/xrdp"]}
        check("reject_ambiguous_or_zero_display_" + display, m.display_independent(process, [session]) is False)
    for display in (":10", ":10.0", ":10.1"):
        session = {"Service": "xrdp-sesman", "Seat": "", "Display": ":10", "ControlGroup": "/review/xrdp"}
        process = {"display_environment": {"DISPLAY": display, "XAUTHORITY": "/review/.Xauthority", "WAYLAND_DISPLAY": None}, "cgroups": ["/review/xrdp"]}
        check("allow_reviewed_xrdp_" + display, m.display_independent(process, [session]) is True)
    process["cgroups"] = ["/review/unrelated"]
    check("reject_xrdp_display_with_wrong_cgroup", m.display_independent(process, [session]) is False)
    process["cgroups"] = ["/review/xrdp"]
    process["display_environment"]["WAYLAND_DISPLAY"] = "wayland-0"
    check("reject_wayland_dependency", m.display_independent(process, [session]) is False)
    process["display_environment"]["WAYLAND_DISPLAY"] = None
    process["display_environment"]["XAUTHORITY"] = "/run/lightdm/root/:0"
    check("reject_lightdm_authority_under_xrdp_label", m.display_independent(process, [session]) is False)

    def no_mutation(backend):
        return "stop" not in backend.calls and "start" not in backend.calls and not any(isinstance(c, tuple) for c in backend.calls)

    backend = t.FakeSystem()
    backend.edits["locked_before"] = lambda s: s["processes"].pop(3708)
    state = m.maintain(backend, True)
    check("protected_pid_disappearance_before_stop_refuses_without_mutation", no_mutation(backend) and state["reset_attempts"] == 0)

    def add_protected(s):
        s["processes"][9999] = t.process(9999, "/opt/codex/codex", "/review/protected", ["Codex"])
        s["protected_pids"].append(9999)

    backend = t.FakeSystem()
    backend.edits["locked_before"] = add_protected
    state = m.maintain(backend, True)
    check("new_locked_protected_pid_is_required_after_stop", state["reset_attempts"] == 0 and "start" in backend.calls and not any(isinstance(c, tuple) for c in backend.calls) and state["execution_state"] == "refused_or_failed")

    class InterruptedStop(t.FakeSystem):
        def service(self, verb):
            self.calls.append(verb)
            if verb == "stop":
                raise KeyboardInterrupt("CPU injected interruption during stop")

    backend = InterruptedStop()
    state = m.maintain(backend, True)
    check("KeyboardInterrupt_during_stop_restores_before_unlock", state["restore_attempted"] and backend.calls.index("start") < backend.calls.index("unlock") and state["reset_attempts"] == 0)

    class InterruptedReset(t.FakeSystem):
        def reset_gpu1(self):
            self.calls.append(("reset", m.GPU1))
            raise SystemExit("CPU injected interruption during reset")

    backend = InterruptedReset()
    state = m.maintain(backend, True)
    check("SystemExit_during_single_reset_still_restores", state["reset_attempts"] == 1 and backend.calls.count(("reset", m.GPU1)) == 1 and state["restore_attempted"] and "start" in backend.calls)

    backend = t.FakeSystem()
    backend.edits["after_restore"] = lambda s: s["unit"].update(SubState="exited")
    state = m.maintain(backend, True)
    check("active_but_not_running_restore_cannot_report_success", "restore_error" in state and not state.get("lightdm_restored_service_running", False) and state["execution_state"] != "reset_completed_not_qualified")

    backend = t.FakeSystem()
    state = m.maintain(backend, False)
    check("default_check_has_zero_actions", no_mutation(backend) and state["execution_state"] == "checked_ready_no_actions")

    # Exercise the actual flock implementation against two scratch files only.
    # No production GPU lock is opened or changed.
    original_lockroot = m.LOCKROOT
    with tempfile.TemporaryDirectory(prefix="maintenance_lock_review_", dir=HERE) as scratch:
        m.LOCKROOT = Path(scratch)
        for uuid in (m.GPU0, m.GPU1):
            (m.LOCKROOT / (uuid + ".lock")).touch()
        actual = m.System(t.MemoryEvidence())
        try:
            for busy_gpu in (m.GPU0, m.GPU1):
                with (m.LOCKROOT / (busy_gpu + ".lock")).open("r+") as busy:
                    fcntl.flock(busy, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    refused = False
                    try:
                        with actual.locks():
                            pass
                    except m.Refusal:
                        refused = True
                    check("actual_flock_refuses_scratch_busy_" + busy_gpu, refused)
                    fcntl.flock(busy, fcntl.LOCK_UN)
                with actual.locks():
                    pass
                check("all_scratch_locks_released_after_" + busy_gpu, True)
        finally:
            m.LOCKROOT = original_lockroot
    check("source_stable_during_independent_CPU_review", sha(helper) == EXPECTED)
    evidence = {
        "schema": "scalellm_gpu1_maintenance_independent_source_mock_review_v1",
        "reviewed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "reviewer": "A010 /root/gsm8k_protocol", "CPU_only": True,
        "cpu_affinity": sorted(os.sched_getaffinity(0)), "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "helper": str(helper), "helper_sha256": EXPECTED, "review_source_sha256": sha(__file__),
        "author_test_source_sha256": sha(testfile), "author_mock_receipt_sha256": sha(DIRECTORY / "mock_results.json"),
        "author_tests_independently_rerun": result.testsRun, "author_tests_failures": len(result.failures), "author_tests_errors": len(result.errors),
        "additional_independent_checks": checks, "additional_independent_checks_passed": len(checks),
        "real_system_commands": 0, "real_GPU_calls": 0, "real_service_actions": 0, "production_GPU_locks_opened": 0,
        "execution_state": "source_and_CPU_mock_review_complete",
        "verdict": "bounded source and CPU mock qualification accepted for this exact helper version; actual maintenance unexecuted",
        "blocking_source_findings": [],
        "resolved_findings": ["Initial and locked protected PID/start identities are bound before stop; newly observed protected identities are retained for postchecks.", "Physical display0 aliases cannot pass the XRDP exemption; only explicit matching nonzero local XRDP display numbers are accepted.", "Restoration checks active/running unit and root LightDM MainPID; greeter observation is reported separately.", "Repeated NVIDIA library identity checks preserve separate raw records."],
        "source_reviewed_controls": ["Default check cannot call stop/reset/start; nonroot execute refuses without escalation.", "Both original GPU locks are held throughout stop/reset/restoration, and unexpected NVML-enumerated GPU0/GPU1 clients refuse even with free locks.", "Only the fixed lightdm.service and GPU1 UUID can be mutated; there is no fallback target, retry or driver installation/restart.", "Human/unknown seat sessions, affected Codex/EDA/helper cgroups/display dependencies and unknown NVML clients refuse before stop.", "The stop-attempt marker is set before calling stop; BaseException paths attempt restoration before releasing locks.", "A reset exit0 is labelled reset_completed_not_qualified and cannot establish postreset model/byte qualification."],
        "limitations": ["No real system inventory command, service action, GPU reset, postreset validation or restoration was executed by reviewer.", "CPU mock success proves orchestration behavior within the covered cases; it does not prove real reset support or device repair.", "Actual helper may legitimately refuse due to existing external GPU0 compute, unknown session ownership, permission or other preconditions.", "NVML process inventory may omit clients holding only monitor/device descriptors; reset may naturally refuse in-use despite the inventory gate. No descriptor scan or client control was added under the final bounded scope.", "Finally restoration cannot guarantee recovery after process/host failure such as SIGKILL or power loss; actual result and service evidence must be reviewed.", "Only the controller can release the existing R003 maintenance hold after resolving the real maintenance state."],
    }
    (HERE / "gpu1_maintenance_independent_CPU_review_AT001.log").write_text(log.getvalue())
    out = HERE / "gpu1_maintenance_independent_review_AT001.json"
    with out.open("x") as stream:
        json.dump(evidence, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"output": str(out), "helper_sha256": EXPECTED, "author_tests_rerun": result.testsRun, "additional_independent_checks": len(checks), "blocking_source_findings": []}))


if __name__ == "__main__":
    main()
