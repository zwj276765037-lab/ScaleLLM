"""External read-only lifecycle evidence; not the worker's parent/waitpid owner."""
import json,os,select,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent
launch=json.loads((HERE/'actual_launch.json').read_text());pid=launch['pid']
def now():return datetime.now(timezone.utc).isoformat()
def write(name,d):
 p=HERE/name;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(d,indent=2)+'\n');os.replace(t,p)
started=now();pidfd=None;status=None
try:
 stat=Path(f'/proc/{pid}/stat').read_text().split()
 if stat[21]!=launch['startticks']:raise RuntimeError('PID reused before observation')
 pidfd=os.pidfd_open(pid);poll=select.poll();poll.register(pidfd,select.POLLIN)
 write('lifecycle_observer_started.json',dict(pid=os.getpid(),observed_pid=pid,observed_startticks=stat[21],observed_ppid=int(stat[3]),started_at=started,pidfd_opened=True,waitpid_parent=False))
 while not poll.poll(1000):pass
 exit_at=now();proc=Path(f'/proc/{pid}/stat')
 if proc.exists():
  stat=proc.read_text().split();status=dict(state=stat[2],linux_proc_exit_code=int(stat[51]) if len(stat)>51 else None)
 for _ in range(60):
  if not proc.exists():break
  time.sleep(1)
 apps=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_gpu_memory','--format=csv,noheader,nounits'],text=True).strip().splitlines()
 own=[row for row in apps if len(row.split(','))>=2 and row.split(',')[1].strip()==str(pid)]
 write('external_lifecycle_receipt.json',dict(observed_pid=pid,observed_startticks=launch['startticks'],observer_pid=os.getpid(),observer_started_at=started,pidfd_exit_observed_at=exit_at,observed_at=now(),pidfd_signaled_exit=True,proc_stat_at_exit=status,proc_entry_absent=not proc.exists(),os_reaped_observed_by_proc_absence=not proc.exists(),gpu_owned_process_present=bool(own),gpu_owned_process_rows=own,waitpid_parent=False,native_exit_code_source='Linux proc exit_code if captured; otherwise unavailable to nonparent, see worker receipt separately'))
except BaseException as e:write('external_lifecycle_error.json',dict(at=now(),error=str(e),observed_pid=pid))
finally:
 if pidfd is not None:os.close(pidfd)
