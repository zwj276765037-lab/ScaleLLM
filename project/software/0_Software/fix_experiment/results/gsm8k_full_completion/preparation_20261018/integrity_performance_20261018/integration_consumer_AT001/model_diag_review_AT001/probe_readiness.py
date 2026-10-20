"""Demonstrate source-list coverage behavior without invoking a launch path."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[10]
EXP = ROOT / "project/software/0_Software/fix_experiment/exp"
DIAG = ROOT / "project/E010_gsm8k_six_model_completion/experiment_results/performance_repair/production_integration_20261018/shared_model_diag_AT001"
sys.path.insert(0, str(EXP))
from run_gsm8k_matrix import verify_readiness


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


assert os.environ.get("CUDA_VISIBLE_DEVICES") == ""
assert sorted(os.sched_getaffinity(0)) == [8, 9]
spec = json.loads((DIAG / "bf16/spec_reviewed.json").read_text())
out = Path(__file__).parent
record = {"schema": "scalellm_independent_readiness_source_coverage_probe_v1",
    "checked_at": datetime.now(timezone.utc).isoformat(), "matrix_source_sha256": sha(EXP / "run_gsm8k_matrix.py"),
    "scope": "direct pure verify_readiness call only; no matrix main, locks, children, GPU queries or GPU initialization",
    "cases": []}
for omitted in (None, "gsm8k_integrity_bytewise.py", "gsm8k_weight_integrity.py"):
    sources = deepcopy(spec["source_hashes"])
    if omitted:
        key = next(key for key in sources if Path(key).name == omitted)
        del sources[key]
    path = out / ("readiness_" + (omitted or "complete") + ".json")
    fixture = {"ready": True, "plan_sha256": spec["plan_sha256"], "source_hashes": sources,
               "evidence_hashes": {}, "gpu_uuids": [spec["gpu_uuid"]]}
    with path.open("x") as handle:
        json.dump(fixture, handle, indent=2); handle.write("\n")
    accepted = verify_readiness(SimpleNamespace(readiness=path, plan=Path(spec["plan"]),
                                               gpu_uuids=[spec["gpu_uuid"]]))
    assert accepted == fixture
    record["cases"].append({"omitted_source": omitted, "source_count": len(sources),
        "observed_accepted": True, "desired_new_mode_accepted": omitted is None,
        "fixture_sha256": sha(path)})
record.update(verdict="confirmed_source_coverage_gap_for_future_launch", current_shared_diag_affected=False,
    actual_diag_bound_source_count=len(spec["source_hashes"]),
    before_formal_resume="Require full reviewed source set including both helpers, with exact source/snapshot/readiness hashes and CPU omission negative controls before launch; keep current running/frozen sources unchanged.",
    formal_late_failure="train summary checks contract.source_hashes.get(source_path)==digest; missing helper would be refused late even if matrix reused completed stages",
    torch_imported="torch" in sys.modules)
assert record["torch_imported"] is False
with (out / "readiness_probe.json").open("x") as handle:
    json.dump(record, handle, indent=2); handle.write("\n")
print(json.dumps(record, indent=2))
