"""Launch the accepted, frozen R004 read-only command once, under owned guard."""
from pathlib import Path
import datetime
import fcntl
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
AT = ROOT / 'project/E011_m003_joint_routability_implementation/experiment_results/runs/R004/attempts/AT001_failed_route_driver_region_localization'
EV = AT / 'evidence'


def identity(path):
    path = Path(path)
    return dict(path=str(path), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


prepared = json.loads((EV / 'prepared_owned_command_v2.json').read_text())
assert identity(prepared['package']['path']) == prepared['package']
assert identity(prepared['prelaunch_receipt']['path']) == prepared['prelaunch_receipt']
package = json.loads(Path(prepared['package']['path']).read_text())
gate = json.loads((ROOT / package['independent_gate']).read_text())
assert gate['no_substantive_blocker'] is True and gate['package'] == prepared['package']
assert identity(gate['review_evidence']['path']) == gate['review_evidence']
assert not Path(prepared['report']).exists()
assert not (EV / 'jobs' / prepared['job']).exists()
assert not (EV / 'detached_owned_supervisor_launch.json').exists()
with (ROOT / 'project/hardware/vivado/.m002_eda.lock').open('a+') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    fcntl.flock(lock, fcntl.LOCK_UN)
with (EV / 'detached_owned_supervisor.log').open('x') as stream:
    child = subprocess.Popen(prepared['command'], cwd=ROOT, stdin=subprocess.DEVNULL,
                             stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
ticks = int(Path(f'/proc/{child.pid}/stat').read_text().rsplit(')', 1)[1].split()[19])
receipt = dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
               supervisor_pid=child.pid, start_ticks=ticks, detached=True,
               command=prepared['command'], log=str(EV / 'detached_owned_supervisor.log'),
               request_only=True, prepared_receipt=prepared['prelaunch_receipt'],
               launcher=identity(Path(__file__)))
with (EV / 'detached_owned_supervisor_launch.json').open('x') as stream:
    json.dump(receipt, stream, indent=2)
    stream.write('\n')
print(json.dumps(dict(requested=True, supervisor_pid=child.pid,
                      supervisor_start_ticks=ticks, actual_native_not_yet_claimed=True)))
