#!/usr/bin/env python3
"""CPU scripted fixtures for driver ordering; never numerical DUT/board proof."""
import argparse
from contextlib import redirect_stdout, redirect_stderr
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

from diagnostic import DiagnosticRecord, DiagnosticArtifacts, digest, json_write
import run_gu


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    root = next(parent for parent in Path(__file__).resolve().parents if (parent / "project/hardware/host").is_dir())
    sys.path.insert(0, str(root / "project/hardware"))
    spec = importlib.util.spec_from_file_location("cpu_transport_fixture", root / "project/hardware/tests/test_scalellm_mlp_gu_only_backend.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    bundle = Path(args.bundle).resolve()
    artifacts = DiagnosticArtifacts(bundle)
    gold = artifacts.records["gold_gu_s24"].read_verified()
    verified = json.loads((bundle / "verification.json").read_text())
    checks = []
    class OrderedFixture(module.ScriptedTransport):
        def __init__(self, result, corrupt=False):
            super().__init__()
            self.result, self.corrupt, self.starts, self.acks = result, corrupt, 0, 0

        def write32(self, address, value):
            if address == 0x320:
                self.starts += 1
                self.output = bytearray(gold)
                if self.corrupt:
                    self.output[0] ^= 1
            if address == 0x2A0:
                cohort = self.acks
                assert (self.result / f"cohort{cohort}_output.bin").read_bytes() == gold
                assert (self.result / f"cohort{cohort}_done_before_ack.json").is_file()
                persisted = json.loads((self.result / f"cohort{cohort}_comparison.json").read_text())
                assert persisted["verdict"] == "PASS" and persisted["acked"] is False
                self.acks += 1
            return super().write32(address, value)

    log = io.StringIO()
    for cohorts in (1, 2):
        result = out / f"CPU_fixture_success_cohorts{cohorts}"
        transport = OrderedFixture(result)
        with patch.object(run_gu, "verify_bundle", return_value=verified), redirect_stdout(log), redirect_stderr(log):
            receipt = run_gu.run(transport, bundle, result, cohorts=cohorts, epoch=7, command_base=10, request_id=91)
        assert receipt["verdict"] == "PASS" and transport.starts == cohorts and transport.acks == cohorts
        assert receipt["layer_released"] == (cohorts == 2)
        checks.append({"check": f"scripted_{cohorts}_cohort_ordering", "verdict": "PASS", "starts": transport.starts, "acks": transport.acks})
    result = out / "CPU_fixture_numerical_mismatch"
    transport = OrderedFixture(result, corrupt=True)
    with patch.object(run_gu, "verify_bundle", return_value=verified), redirect_stdout(log), redirect_stderr(log):
        try:
            run_gu.run(transport, bundle, result, cohorts=2, epoch=7, command_base=10, request_id=91)
            raise AssertionError("mismatch accepted")
        except AssertionError as error:
            assert "numerical mismatch" in str(error)
    receipt = json.loads((result / "receipt.json").read_text())
    assert receipt["verdict"] == "FAIL" and transport.starts == 1 and transport.acks == 0
    diff = receipt["cohorts"][0]
    assert diff["mismatched_values"] == 1 and diff["mismatched_bytes"] == 1
    assert diff["coordinates"][0] == {"matrix": "gate", "row": 0, "column": 0, "byte_offset": 0, "expected_s24": 1, "actual_s24": 0}
    assert receipt["retained_pending"]["command_id"] == 10 and receipt["retained_layer_lease"] == [0, 7, 1]
    checks.append({"check": "scripted_mismatch_no_ACK_no_second_START", "verdict": "PASS", "first_difference": diff["coordinates"][0]})
    for layer, name in ((1, "mlp_gate_meta"), (0, "mlp_down_c0")):
        try:
            artifacts.layer_artifact(layer, name)
            raise AssertionError("unsupported diagnostic artifact accepted")
        except ValueError:
            pass
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "record.bin"
        path.write_bytes(b"abc")
        for size, sha in ((4, digest(b"abc")), (3, "0" * 64)):
            try:
                DiagnosticRecord(path, size, sha).read_verified()
                raise AssertionError("invalid identity accepted")
            except ValueError:
                pass
    checks.append({"check": "diagnostic_only_layer_and_size_hash_rejection", "verdict": "PASS"})
    (out / "CPU_fixture_driver.log").write_text(log.getvalue())
    json_write(out / "result.json", {"verdict": "PASS", "scope": "CPU scripted transport fixtures; output and DONE injected; no RTL/DUT/board evidence", "checks": checks})
    print(f"CPU_DRIVER_FIXTURES_PASS checks={len(checks)}")


if __name__ == "__main__":
    main()
