#!/usr/bin/env python3
"""One explicit CPU fixture pair to check the new provider/runner integration."""
import argparse
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys

from dense import DenseArtifacts, root_path, write_json
import run_dense_gu


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle")
    parser.add_argument("out")
    args = parser.parse_args()
    root = root_path()
    sys.path.insert(0, str(root / "project/hardware"))
    spec = importlib.util.spec_from_file_location("CPU_dense_fixture", root / "project/hardware/tests/test_scalellm_mlp_gu_only_backend.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    gold = DenseArtifacts(args.bundle).records["gold_gu_s24"].read_verified()
    result = Path(args.out).resolve()
    class Fixture(module.ScriptedTransport):
        def __init__(self):
            super().__init__()
            self.acks = 0

        def write32(self, address, value):
            if address == 0x320:
                self.output = bytearray(gold)  # Explicit fixture injection.
            if address == 0x2A0:
                assert (result / f"cohort{self.acks}_output.bin").read_bytes() == gold
                compare = json.loads((result / f"cohort{self.acks}_comparison.json").read_text())
                assert compare["verdict"] == "PASS" and not compare["acked"]
                assert (result / f"cohort{self.acks}_done_before_ack.json").is_file()
                self.acks += 1
            super().write32(address, value)
    transport = Fixture()
    captured = io.StringIO()
    with redirect_stdout(captured):
        receipt = run_dense_gu.run(transport, args.bundle, result, cohorts=2, epoch=7, command_base=10, request_id=91)
    assert receipt["verdict"] == "PASS" and receipt["layer_released"] and transport.acks == 2
    write_json(result / "CPU_fixture_scope.json", {"verdict": "PASS", "scope": "CPU scripted transport with injected gold/DONE; provider/runner/persist-before-ACK integration only, not DUT or board evidence", "acks": 2, "layer_released": True})
    print("DENSE_PROVIDER_RUNNER_CPU_PAIR_PASS")


if __name__ == "__main__":
    main()
