"""Detach only the existing owned supervisor; never bypass its exclusive lock."""
import argparse,datetime,json,os,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--attempt',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--print-command',action='store_true');a=p.parse_args()
here=Path(__file__).resolve().parent;root=here.parents[4];package=json.loads((here/'diagnostic_package.json').read_text())
cmd=[sys.executable,str(root/'project/hardware/vivado/scripts/run_m003_owned.py'),'--attempt',str(a.attempt.resolve()),'--job','native_grouped_clock','--report',str(a.report.resolve()),'--',sys.executable,str(here/'launch.py'),'--package',str(here/'diagnostic_package.json')]
for row in package['sources']:cmd+=['--archive-source',row['path']]
if a.print_command:print(json.dumps(cmd));sys.exit(0)
assert a.attempt.is_dir(),'Registered attempt directory required'
logpath=a.attempt/'evidence/detached_owned_supervisor.log';logpath.parent.mkdir(exist_ok=True)
with logpath.open('xb') as log:proc=subprocess.Popen(cmd,cwd=root/'project/hardware',stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,close_fds=True)
start=Path(f'/proc/{proc.pid}/stat').read_text().rsplit(')',1)[1].split()[19]
receipt=dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),supervisor_pid=proc.pid,start_ticks=int(start),detached=True,command=cmd,log=str(logpath),note='Launch requested; actual EDA activation is established only by started.json/native PID, not this receipt')
(a.attempt/'evidence/detached_owned_supervisor_launch.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
