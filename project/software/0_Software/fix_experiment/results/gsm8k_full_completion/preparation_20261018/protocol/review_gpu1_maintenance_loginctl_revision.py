#!/usr/bin/env python3
"""CPU-only bounded review of the loginctl argv environment adaptation."""
import ast
import copy
import datetime
import difflib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
DIRECTORY = HERE.parent / "gpu1_maintenance_20261018"
OLD_SHA = "2249afac1537e04a993e55f6cf75a30d3df0030a0ea7c7bc663d0b94527ca15a"
NEW_SHA = "3d12ec648dd587bc1dc160c04f102abe49b1a679e3fcbcb81c456a48b21f23fa"
FIELDS = ("Id", "Name", "User", "Seat", "Display", "Service", "Class", "Type", "Leader", "Scope", "State")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def dump(node):
    return ast.dump(node, include_attributes=False)


def system(tree):
    return next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "System")


def session_assignment(tree):
    method = next(n for n in system(tree).body if isinstance(n, ast.FunctionDef) and n.name == "snapshot")
    return next(n for n in ast.walk(method) if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "s")


def main():
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == "" and set(os.sched_getaffinity(0)) == {8, 9}
    old_path = HERE / "gpu1_maintenance_2249afac_source_snapshot.py"
    new_path = DIRECTORY / "gpu1_maintenance.py"
    assert sha(old_path) == OLD_SHA and sha(new_path) == NEW_SHA
    old_source, new_source = old_path.read_text(), new_path.read_text()
    old_tree, new_tree = ast.parse(old_source), ast.parse(new_source)
    method = next(n for n in system(new_tree).body if isinstance(n, ast.FunctionDef) and n.name == "session_properties")
    expected_method = ast.parse("def session_properties(self,sid):\n fields=('Id','Name','User','Seat','Display','Service','Class','Type','Leader','Scope','State')\n argv=['/usr/bin/loginctl','show-session',sid]\n for field in fields:argv.extend(['--property',field])\n return props(self.checked(argv))\n").body[0]
    assert dump(method) == dump(expected_method)
    assert dump(session_assignment(new_tree).value) == dump(ast.parse("self.session_properties(sid)", mode="eval").body)
    normalized = copy.deepcopy(new_tree)
    system(normalized).body = [n for n in system(normalized).body if not (isinstance(n, ast.FunctionDef) and n.name == "session_properties")]
    session_assignment(normalized).value = copy.deepcopy(session_assignment(old_tree).value)
    assert dump(normalized) == dump(old_tree), "Changes extend beyond the reviewed CLI adapter"
    old_review = read(HERE / "gpu1_maintenance_independent_review_AT001.json")
    assert old_review["helper_sha256"] == OLD_SHA and old_review["blocking_source_findings"] == []

    testfile = DIRECTORY / "test_helper_mock.py"
    spec = importlib.util.spec_from_file_location("maintenance_loginctl_revision_tests", testfile)
    tests = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tests)
    log = io.StringIO()
    suite = unittest.TestSuite([tests.Cases("test_loginctl_uses_one_property_argument_per_field")])
    test_result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    assert test_result.wasSuccessful() and test_result.testsRun == 1
    author_mock = read(DIRECTORY / "mock_results.json")
    assert author_mock["helper_sha256"] == NEW_SHA and author_mock["test_source_sha256"] == sha(testfile)
    assert author_mock["tests_run"] == 22 and author_mock["successful"] is True

    validation = DIRECTORY / "validation/loginctl_fields_AT001"
    receipt, command = read(validation / "receipt.json"), read(validation / "command_001.json")
    expected_argv = ["/usr/bin/loginctl", "show-session", "115"]
    for field in FIELDS:
        expected_argv.extend(["--property", field])
    assert receipt["helper_sha256"] == NEW_SHA and receipt["euid"] == 1001
    assert command["argv"] == expected_argv and command["exit_code"] == 0 and not command["stderr"]
    assert receipt["real_readonly_loginctl_commands"] == 1 and receipt["real_GPU_calls"] == receipt["real_service_actions"] == 0
    parsed = tests.m.props(command["stdout"])
    assert set(parsed) == set(FIELDS) and parsed == receipt["properties"]
    assert parsed["Id"] == "115" and parsed["Scope"] == "session-115.scope"
    calls = []
    backend = tests.m.System(tests.MemoryEvidence())
    backend.checked = lambda argv: calls.append(argv) or command["stdout"]
    assert backend.session_properties("115") == parsed and calls == [expected_argv]

    old_run = DIRECTORY / "runs/check_20261018T050240.255069Z_320577"
    old_result, old_command = read(old_run / "result.json"), read(old_run / "command_003.json")
    assert old_command["exit_code"] == 0 and old_command["stdout"] == ""
    assert old_result["error"] == "Refusal('session scope is unknown: 115')"
    new_run = DIRECTORY / "runs/check_20261018T050450.227605Z_320888"
    new_result = read(new_run / "result.json")
    assert read(new_run / "library_identity_01.json")["helper_sha256"] == NEW_SHA
    assert new_result["execution_state"] == "refused_or_failed" and new_result["error"] == "Refusal('cannot inspect process identity 1')"
    for state in (old_result, new_result):
        assert state["execute_requested"] is False and state["reset_attempts"] == 0
        assert state["stop_attempted"] is False and state["restore_attempted"] is False
    command_hashes, sequence = {}, []
    session115_seen = False
    for path in sorted(new_run.glob("command_*.json")):
        record = read(path)
        argv = record["argv"]
        assert record["exit_code"] == 0
        assert (argv[:2] == ["/usr/bin/systemctl", "show"] or argv[:2] in (["/usr/bin/loginctl", "list-sessions"], ["/usr/bin/loginctl", "show-session"]) or (argv[0].endswith("/extracted/nvidia-smi") and argv[1:] == ["-q", "-x"]))
        if argv == expected_argv:
            session115_seen = True
            assert tests.m.props(record["stdout"])["Scope"] == "session-115.scope"
        sequence.append({"file": path.name, "argv": argv, "exit_code": record["exit_code"]})
        command_hashes[str(path)] = sha(path)
    assert session115_seen and len(sequence) == 27
    assert sha(new_path) == NEW_SHA and sha(old_path) == OLD_SHA
    snapshot = HERE / "gpu1_maintenance_3d12ec64_source_snapshot.py"
    with snapshot.open("x") as stream:
        stream.write(new_source)
    patch = HERE / "gpu1_maintenance_loginctl_revision_AT001.patch"
    with patch.open("x") as stream:
        stream.write("".join(difflib.unified_diff(old_source.splitlines(keepends=True), new_source.splitlines(keepends=True), fromfile=str(old_path), tofile=str(new_path))))
    logfile = HERE / "gpu1_maintenance_loginctl_revision_CPU_AT001.log"
    with logfile.open("x") as stream:
        stream.write(log.getvalue())
    artifacts = [old_path, new_path, snapshot, patch, testfile, DIRECTORY / "mock_results.json", validation / "receipt.json", validation / "command_001.json", old_run / "result.json", old_run / "command_003.json", new_run / "result.json", new_run / "library_identity_01.json", HERE / "gpu1_maintenance_independent_review_AT001.json"]
    evidence = {
        "schema": "scalellm_gpu1_maintenance_loginctl_adapter_independent_review_v1",
        "reviewed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "reviewer": "A010 /root/gsm8k_protocol",
        "CPU_only": True, "cpu_affinity": sorted(os.sched_getaffinity(0)), "old_helper_sha256": OLD_SHA, "new_helper_sha256": NEW_SHA,
        "review_source_sha256": sha(__file__), "only_adapter_AST_delta_verified": True, "all_prior_safety_control_AST_unchanged": True,
        "new_argv_test_independently_run": 1, "new_argv_test_passed": True, "author_22_test_receipt_bound_not_all_repeated": True,
        "real_readonly_session_115_receipt_verified": True, "all_11_fields_and_empty_values_preserved": True,
        "old_default_check_error": old_result["error"], "new_default_check_error": new_result["error"],
        "new_default_check_scope": "CLI parsing progressed; real nonroot /proc process-identity permission refusal remains, before any stop/reset attempt",
        "actual_readonly_command_sequence": sequence, "actual_readonly_command_sha256": command_hashes,
        "reviewer_real_system_commands": 0, "reviewer_real_GPU_calls": 0, "reviewer_real_service_actions": 0,
        "blocking_source_findings": [], "execution_state": "bounded_adapter_revision_review_complete",
        "verdict": "loginctl CLI adaptation accepted for exact new SHA; previous safety review applies through verified unchanged AST; actual maintenance unexecuted",
        "artifact_sha256": {str(path): sha(path) for path in artifacts},
        "limitations": ["This is an environment adapter review only; no models, memory qualification, reset or restoration checks were repeated.", "The actual default check still refuses under the real nonroot /proc permission boundary; this is not a maintenance-ready or reset-success result.", "Old raw failed check and original independent review remain historical and unchanged.", "R003 maintenance hold and any administrator action remain controlled by the parent."]}
    output = HERE / "gpu1_maintenance_loginctl_revision_review_AT001.json"
    with output.open("x") as stream:
        json.dump(evidence, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"output": str(output), "new_helper_sha256": NEW_SHA, "only_adapter_AST_delta_verified": True, "targeted_test_passed": True, "actual_check_error": new_result["error"], "blocking_source_findings": []}))


if __name__ == "__main__":
    main()
