"""Save a new immutable CPU-only test attempt and its exact source identities."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"AT[0-9]{3}", args.attempt):
        parser.error("attempt must be AT followed by three digits")
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "" or not set(os.sched_getaffinity(0)) <= {18, 19}:
        parser.error("requires CUDA_VISIBLE_DEVICES='' and CPU affinity within 18,19")
    root = Path(__file__).resolve().parent
    out = root / "cpu_validation" / args.attempt
    out.mkdir(parents=True, exist_ok=False)
    tmp = out / "tmp"
    tmp.mkdir()
    environment = dict(os.environ, TMPDIR=str(tmp), PYTHONDONTWRITEBYTECODE="1",
                       OMP_NUM_THREADS="2", MKL_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2")
    command = [sys.executable, "-B", str(root / "test_bytewise_integrity.py")]
    started = time.time()
    result = subprocess.run(command, env=environment, capture_output=True, text=True)
    (out / "stdout.log").write_text(result.stdout)
    (out / "stderr.log").write_text(result.stderr)
    sources = [root / "gsm8k_integrity_bytewise.py", root / "test_bytewise_integrity.py", Path(__file__),
               root.parents[4] / "exp/gsm8k_weight_integrity.py",
               root.parents[4] / "exp/test_gsm8k_weight_integrity.py"]
    count = re.search(r"Ran (\d+) tests", result.stderr)
    receipt = {"execution_state": "completed" if result.returncode == 0 else "failed", "exit_code": result.returncode,
               "test_count": int(count[1]) if count else None, "command": command, "started_epoch": started,
               "finished_epoch": time.time(), "cpu_affinity": sorted(os.sched_getaffinity(0)),
               "CUDA_VISIBLE_DEVICES": environment["CUDA_VISIBLE_DEVICES"],
               "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"receipt": str(out / "receipt.json"), "exit_code": result.returncode,
                      "test_count": receipt["test_count"], "stderr_tail": result.stderr[-350:]}))
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
