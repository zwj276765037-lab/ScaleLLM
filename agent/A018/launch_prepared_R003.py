"""Launch only the prepared frozen R003 command under the existing owned lane."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess

root = Path.cwd()
at = root / 'project/E011_m003_joint_routability_implementation/experiment_results/runs/R003/attempts/AT001_fixed_complete_physical'
ev = at / 'evidence'
prepared = json.loads((ev / 'prepared_owned_command.json').read_text())

def identity(path):
    path = Path(path)
    return dict(path=str(path), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())

for row in [prepared['prelaunch_receipt'], prepared['actual_G4_gate']]:
    assert identity(row['path']) == row
receipt = json.loads(Path(prepared['prelaunch_receipt']['path']).read_text())
assert receipt['actual_G4_checked_by_unmodified_launcher'] is True
assert receipt['no_native_process_invoked'] is True
for key in ['frozen_physical_v2_package', 'actual_source_review', 'preplace', 'checkpoint']:
    assert identity(receipt[key]['path']) == receipt[key]
assert not Path(prepared['report']).exists()
assert not (ev / 'jobs' / prepared['job']).exists()
assert not (ev / 'detached_owned_supervisor_launch.json').exists()
run = json.loads((at / 'run.json').read_text())
assert run['execution_state'] == 'planned' and run['command'] == prepared['command']
with (ev / 'detached_owned_supervisor.log').open('x') as stream:
    proc = subprocess.Popen(prepared['command'], cwd=root, stdin=subprocess.DEVNULL,
                            stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
start = int(Path(f'/proc/{proc.pid}/stat').read_text().rsplit(')', 1)[1].split()[19])
value = dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
             supervisor_pid=proc.pid, start_ticks=start, detached=True,
             command=prepared['command'], log=str(ev / 'detached_owned_supervisor.log'),
             request_only=True, prepared_receipt=prepared['prelaunch_receipt'])
with (ev / 'detached_owned_supervisor_launch.json').open('x') as stream:
    json.dump(value, stream, indent=2)
    stream.write('\n')
print(json.dumps(dict(requested=True, supervisor_pid=proc.pid,
                      supervisor_start_ticks=start, actual_native_not_yet_claimed=True)))
