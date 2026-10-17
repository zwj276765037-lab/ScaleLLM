"""Actual CPU-only isolated process stop test; never targets EDA."""
import importlib.util,json,os,signal,subprocess,tempfile,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('adoption',HERE/'adopt_no_wall.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
with tempfile.TemporaryDirectory() as tmp:
    data=Path(tmp);child=data/'child.py';supervisor=data/'supervisor.py'
    child.write_text('import os,time\nfrom pathlib import Path\np=Path('+repr(str(data))+')\n(p/"pid").write_text(str(os.getpid()))\nfor i in range(80):\n (p/"ticks").write_text(str(i));time.sleep(.05)\n')
    supervisor.write_text('import subprocess\np=subprocess.Popen(["python3",'+repr(str(child))+'],start_new_session=True)\np.wait()\n')
    owner=subprocess.Popen(['python3',str(supervisor)],start_new_session=True)
    stopped=False
    try:
        for _ in range(200):
            if (data/'pid').exists() and (data/'ticks').exists():break
            time.sleep(.01)
        leader=int((data/'pid').read_text());s=m.procstat(owner.pid);l=m.procstat(leader)
        ready=m.sample(leader,{})
        proof=m.stop_supervisor(owner.pid,s['start_ticks'],leader,l['start_ticks']);stopped=True
        before=int((data/'ticks').read_text());time.sleep(.3);after=int((data/'ticks').read_text())
        assert after>before and m.procstat(owner.pid)['state'] in {'T','t'}
        assert m.procstat(leader)['start_ticks']==l['start_ticks'] and m.procstat(leader)['pgrp']==l['pgrp']
        assert m.decode_wait(7<<8)==7 and m.decode_wait(signal.SIGTERM)==-signal.SIGTERM
        try:m.single_signal(owner.pid,s['start_ticks']+1,signal.SIGSTOP)
        except RuntimeError:pass
        else:raise AssertionError('reused identity accepted')
        result=dict(verdict='PASS',scope='isolated CPU-only owned dummy supervisor/child; no EDA signals',ready=ready,proof=proof,child_tick_before=before,child_tick_after=after,reused_pid_rejected=True,terminal_wait_decode=True)
    finally:
        if stopped:os.kill(owner.pid,signal.SIGCONT)
        owner.wait(timeout=10)
    (HERE/'adoption_test_result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(verdict='PASS',child_progressed_while_only_supervisor_stopped=after-before)))
