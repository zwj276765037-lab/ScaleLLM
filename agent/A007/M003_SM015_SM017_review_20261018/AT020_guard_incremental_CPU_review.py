"""Previously uncovered threshold boundaries and initial group identity only."""
from pathlib import Path
import copy
import datetime
import hashlib
import importlib.util
import json

ROOT = Path(__file__).resolve().parents[3]
path = ROOT / 'agent/A006/M003_SM015_SM018_20261018/adopt_AT020_resource_guard.py'
assert hashlib.sha256(path.read_bytes()).hexdigest() == '68afb4b5eaf14b5cad1ad7c80d251efea3044f11378a72878a6ed6a5d5c3c5e2'
spec = importlib.util.spec_from_file_location('reviewed_guard', path)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
G = guard.GIB
cases = []
for name, values in [
    ('RSS_at_192GiB_not_above', (192*G, 480*G, 440*G, None, 0)),
    ('available_at_48GiB_not_below', (12*G, 48*G, 440*G, 0, 40)),
    ('recovered_available_ignores_prior_low_since', (12*G, 49*G, 440*G, 0, 40)),
    ('disk_at_30GiB_not_below', (12*G, 480*G, 30*G, None, 0)),
]:
    result = guard.resource_reason(*values)
    assert result is None, (name, result)
    cases.append(dict(name=name, passed=True))
table = {pid: dict(start_ticks=start, pgrp=guard.LEADER) for pid, start in guard.EXPECTED.items()}
for name in ['missing_initial_identity', 'wrong_initial_process_group']:
    value = copy.deepcopy(table)
    if name == 'missing_initial_identity':
        del value[86095]
    else:
        value[86095]['pgrp'] = 1
    try:
        guard.verify_initial(value)
    except RuntimeError as exc:
        cases.append(dict(name=name, passed=True, rejection=str(exc)))
    else:
        raise AssertionError(name)
record = dict(schema='A007_AT020_guard_incremental_CPU_review_v1', utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), cases=cases, guard_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), test_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), guard_main_not_called=True, native_controls_not_called=True, prior_seven_owner_cases_not_rerun=True)
out = Path(__file__).with_name('AT020_guard_incremental_CPU_review.json')
with out.open('x') as f:
    json.dump(record, f, indent=2)
    f.write('\n')
print(json.dumps(dict(cases=len(cases), all_pass=True, receipt=str(out.relative_to(ROOT)), sha256=hashlib.sha256(out.read_bytes()).hexdigest())))
