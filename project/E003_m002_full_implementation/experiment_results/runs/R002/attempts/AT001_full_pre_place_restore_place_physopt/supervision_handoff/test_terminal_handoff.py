"""CPU-only zombie status and stopped-supervisor release test."""
import importlib.util,json,os,signal,subprocess,tempfile,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('adoption',HERE/'adopt_no_wall.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
with tempfile.TemporaryDirectory() as tmp:
    data=Path(tmp);child=data/'child.py';supervisor=data/'supervisor.py'
    child.write_text('import os,time,sys\nfrom pathlib import Path\nPath('+repr(str(data/'pid'))+').write_text(str(os.getpid()))\ntime.sleep(.5)\nsys.exit(7)\n')
    supervisor.write_text('import subprocess\np=subprocess.Popen(["python3",'+repr(str(child))+'],start_new_session=True)\np.wait()\n')
    owner=subprocess.Popen(['python3',str(supervisor)],start_new_session=True)
    try:
        for _ in range(300):
            if (data/'pid').exists():break
            time.sleep(.01)
        leader=int((data/'pid').read_text());s=m.procstat(owner.pid);l=m.procstat(leader)
        proof=m.stop_supervisor(owner.pid,s['start_ticks'],leader,l['start_ticks'])
        for _ in range(300):
            terminal=m.procstat(leader)
            if terminal['state']=='Z':break
            time.sleep(.01)
        assert terminal['state']=='Z' and m.decode_wait(terminal['exit_wait_status'])==7
        assert not m.active_owned(leader,{leader:l['start_ticks']})
        m.single_signal(owner.pid,s['start_ticks'],signal.SIGKILL);assert owner.wait(timeout=3)==-9
        for _ in range(300):
            if m.procstat(leader) is None:break
            time.sleep(.01)
        gone=m.procstat(leader) is None
        assert gone,'orphan worker zombie not reaped'
        result=dict(verdict='PASS',scope='isolated CPU-only dummy; actual terminal wait7, no active child at single supervisor kill, orphan reaped',terminal=terminal,orphan_reaped=gone,old_supervisor_native_exit=-9)
    finally:
        if owner.poll() is None:os.kill(owner.pid,signal.SIGKILL);owner.wait()
    (HERE/'terminal_handoff_test_result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
