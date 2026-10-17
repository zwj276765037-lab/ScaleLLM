"""Install this tested candidate only while the owned EDA lane is idle."""
from pathlib import Path
import fcntl, hashlib, json, shutil, datetime as dt
at = Path(__file__).resolve().parent
hw = at.parents[6] / 'project/hardware'
arc = at / 'source_archive'
prior = hw / 'vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/stage_sources'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert json.loads((at / 'actual_replay_status.json').read_text())['verdict'] == 'PASS'
for row in (at / 'archived_sources.sha256').read_text().splitlines():
    digest, name = row.split('  ', 1)
    assert sha(Path(name)) == digest, name
changes = []
lock = (hw / 'vivado/.m002_eda.lock').open('a+')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
for name in ('m002_physical_evidence.py', 'run_managed_eda.py', 'run_m002_physical_stage.py',
             'm002_resume_physical.tcl', 'm002_diagnostic_common.tcl'):
    live = hw / 'vivado/scripts' / name
    assert sha(live) == sha(prior / name), f'live changed since AT008: {name}'
    changes.append(dict(path=str(live), before_sha256=sha(live), after_sha256=sha(arc / name)))
new_test = hw / 'tests/test_m002_pre_place_recovery.py'
assert not new_test.exists(), 'new test path already exists'
changes.append(dict(path=str(new_test), before_sha256=None, after_sha256=sha(arc / new_test.name)))
for row in changes:
    live = Path(row['path'])
    shutil.copy2(arc / live.name, live)
    assert sha(live) == row['after_sha256']
value = dict(installed_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
             verified_against='AT008 frozen five live scripts; new test absent; exclusive EDA lane lock',
             files=changes, source_archive_sha256=sha(at / 'archived_sources.sha256'),
             actual_post_replay_sha256=sha(at / 'actual_replay_status.json'))
(at / 'installation.json').write_text(json.dumps(value, indent=2) + '\n')
print(json.dumps(value, indent=2))
