#!/usr/bin/env python3
"""Explicit, one-target maintenance helper. Default is inspection only."""
import argparse, contextlib, datetime, fcntl, hashlib, json, os, re, signal, subprocess, sys
import xml.etree.ElementTree as ET
from pathlib import Path

BASE=Path(__file__).resolve().parent
PREP=BASE.parent
PROJECT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
LIBROOT=PREP/'nvml_local_recovery_20261018'
GPU0='GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6'
GPU1='GPU-d87ce710-76bf-872d-9739-f0d7c9b52533'
LOCKROOT=PREP.parent/'resource_locks'
UNIT='lightdm.service'
UNIT_CGROUP='/system.slice/lightdm.service'
EXPECTED={LIBROOT/'nvml_lib/libnvidia-ml.so.1':'a610e3e6a9ebb901372dcd2b912a7a040c35406ced930290dd902b3fbf1c797c', LIBROOT/'extracted/nvidia-smi':'96d8e10333427a58e588151bf18d67241183100cbdda2b5cfff1a0c6f45c25fa'}
DISPLAY_KEYS=('DISPLAY','WAYLAND_DISPLAY','XAUTHORITY')
DEVICE_NODES=('/dev/nvidia1','/dev/nvidia0','/dev/nvidiactl','/dev/nvidia-uvm','/dev/nvidia-modeset')
class Refusal(RuntimeError): pass

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def under(group,parent):return group==parent or group.startswith(parent+'/')
def overlap(a,b):return under(a,b) or under(b,a)
def props(text):return dict(line.split('=',1)for line in text.splitlines()if'='in line)
def public(obj):
 if isinstance(obj,dict):return {k:public(v)for k,v in obj.items()if not(isinstance(k,str)and k.startswith('_'))}
 if isinstance(obj,list):return [public(v)for v in obj]
 return obj

class Evidence:
 def __init__(self,path):
  self.path=Path(path);self.path.mkdir(parents=True,exist_ok=False);self.seq=0
 def write(self,name,value):
  (self.path/name).write_text(json.dumps(public(value),indent=2)+'\n')
 def command(self,argv,env):
  self.seq+=1;tag=f'command_{self.seq:03d}';started=now()
  # Let each finite management command return naturally before handling interruption.
  signals={signal.SIGINT,signal.SIGTERM,signal.SIGHUP};old=signal.pthread_sigmask(signal.SIG_BLOCK,signals)
  try:
   p=subprocess.run(argv,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
   record={'argv':argv,'started_at':started,'ended_at':now(),'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
   self.write(tag+'.json',record)
  finally:signal.pthread_sigmask(signal.SIG_SETMASK,old)
  return record

class System:
 def __init__(self,evidence):self.evidence=evidence;self.verify_calls=0;self.env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C','LC_ALL':'C','LD_LIBRARY_PATH':str(LIBROOT/'nvml_lib')}
 def verify(self):
  kernel=Path('/proc/driver/nvidia/version').read_text()
  if 'Kernel Module  580.159.03'not in kernel:raise Refusal('running kernel driver is not580.159.03')
  files=[]
  for path,expected in EXPECTED.items():
   actual=sha(path);files.append({'path':str(path),'sha256':actual,'expected_sha256':expected})
   if actual!=expected:raise Refusal('matched NVIDIA file SHA mismatch: '+str(path))
  self.verify_calls+=1;self.evidence.write(f'library_identity_{self.verify_calls:02d}.json',{'captured_at':now(),'kernel':kernel,'files':files,'helper_sha256':sha(__file__)})
 def command(self,argv):return self.evidence.command(argv,self.env)
 def checked(self,argv):
  r=self.command(argv)
  if r['exit_code']!=0:raise Refusal('read-only inventory command failed: '+repr(argv))
  return r['stdout']
 def gpu_inventory(self):
  raw=self.checked([str(LIBROOT/'extracted/nvidia-smi'),'-q','-x']);root=ET.fromstring(raw);result={}
  for g in root.findall('gpu'):
   uuid=g.findtext('uuid');processes=g.find('processes')
   if processes is None:raise Refusal('missing GPU process inventory')
   result[uuid]=[{'pid':int(p.findtext('pid')),'type':p.findtext('type'),'name':p.findtext('process_name')}for p in processes.findall('process_info')]
  if set(result)!={GPU0,GPU1}:raise Refusal('GPU UUID inventory is not the expected pair')
  return result
 def device_inventory(self):
  if os.geteuid()!=0:raise Refusal('root is required to inspect all GPU device holders')
  result={}
  for node in DEVICE_NODES:
   r=self.command(['/usr/bin/fuser',node]);words=r['stdout'].split()
   if r['exit_code']not in (0,1)or any(not x.isdecimal()for x in words):raise Refusal('GPU device-holder inventory failed: '+node)
   if r['exit_code']==1 and (words or r['stderr'].strip()):raise Refusal('GPU device-holder inventory incomplete: '+node)
   if r['exit_code']==0 and not words:raise Refusal('GPU device-holder inventory returned no PIDs: '+node)
   # fuser writes PIDs to stdout and its node label/access codes to stderr.
   if r['exit_code']==0 and not re.fullmatch(re.escape(node)+r':\s*(?:[cefrFm]\s*)*',r['stderr'].strip()):raise Refusal('GPU device-holder inventory reported unexpected diagnostics: '+node)
   result[node]=sorted({int(x)for x in words})
  return result
 def process(self,pid):
  p=Path('/proc')/str(pid)
  try:
   stat=p.joinpath('stat').read_text().rsplit(')',1)[1].split();raw=p.joinpath('cmdline').read_bytes();args=[x.decode(errors='replace')for x in raw.split(b'\0')if x];exe=os.readlink(p/'exe');uid=p.stat().st_uid
   cg=[line.split(':',2)[2]for line in p.joinpath('cgroup').read_text().splitlines()]
   return {'pid':pid,'ppid':int(stat[1]),'start_ticks':int(stat[19]),'comm':p.joinpath('comm').read_text().strip(),'exe':exe,'uid':uid,'cgroups':cg,'argv0':args[0]if args else None,'cmdline_sha256':hashlib.sha256(raw).hexdigest(),'_args':args}
  except FileNotFoundError:return None
  except PermissionError as exc:raise Refusal('cannot inspect process identity '+str(pid))from exc
 def session_properties(self,sid):
  fields=('Id','Name','User','Seat','Display','Service','Class','Type','Leader','Scope','State')
  argv=['/usr/bin/loginctl','show-session',sid]
  for field in fields:argv.extend(['--property',field])
  return props(self.checked(argv))
 def snapshot(self,label):
  unit=props(self.checked(['/usr/bin/systemctl','show',UNIT,'--property=ActiveState,SubState,MainPID,ControlGroup,KillMode']))
  ids=[r.split()[0]for r in self.checked(['/usr/bin/loginctl','list-sessions','--no-legend','--no-pager']).splitlines()if r.strip()]
  sessions=[]
  for sid in ids:
   s=self.session_properties(sid)
   if not s.get('Scope'):raise Refusal('session scope is unknown: '+sid)
   s['ControlGroup']=props(self.checked(['/usr/bin/systemctl','show',s['Scope'],'--property=ControlGroup'])).get('ControlGroup','');sessions.append(s)
  gpu=self.gpu_inventory();device_clients=self.device_inventory();allproc={}
  for item in Path('/proc').iterdir():
   if item.name.isdecimal():
    r=self.process(int(item.name))
    if r:allproc[r['pid']]=r
  ancestors=set();pid=os.getpid()
  while pid and pid not in ancestors:
   ancestors.add(pid);pid=allproc.get(pid,{}).get('ppid',0)
  greeter_groups=[s['ControlGroup']for s in sessions if s.get('Class')=='greeter']
  leaders={int(s['Leader'])for s in sessions if s.get('Leader','').isdigit()};clients={p['pid']for ps in gpu.values()for p in ps}|{pid for pids in device_clients.values()for pid in pids}
  selected={};protected=[]
  for pid,r in allproc.items():
   command=' '.join(r['_args']);roles=[];ex=r['exe'].lower()
   if 'codex'in Path(ex).name or '/codex/'in ex:roles.append('Codex')
   if re.search(r'vivado|m003|e011',command,re.I):roles.append('M003_or_EDA')
   if pid in ancestors:roles.append('helper_or_ancestor')
   if any(under(g,UNIT_CGROUP)or any(gg and under(g,gg)for gg in greeter_groups)for g in r['cgroups'])or roles or pid in leaders or pid in clients:
    try:
     environment={x.split(b'=',1)[0].decode():x.split(b'=',1)[1].decode(errors='replace')for x in (Path('/proc')/str(pid)/'environ').read_bytes().split(b'\0')if b'='in x}
    except FileNotFoundError:raise Refusal('selected process changed during snapshot')
    except PermissionError as exc:raise Refusal('cannot prove selected process display independence')from exc
    r['display_environment']={k:environment.get(k)for k in (*DISPLAY_KEYS,'XDG_SESSION_ID')};r['roles']=roles;selected[pid]=r
    if roles:protected.append(pid)
  snap={'captured_at':now(),'unit':unit,'sessions':sessions,'gpus':gpu,'device_clients':device_clients,'processes':selected,'protected_pids':protected,'helper_pid':os.getpid()};self.evidence.write(label+'.json',snap);return snap
 @contextlib.contextmanager
 def locks(self):
  held=[]
  try:
   for uuid in (GPU0,GPU1):
    f=(LOCKROOT/(uuid+'.lock')).open('r+');held.append(f)
    try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError as exc:raise Refusal('GPU resource lock busy: '+uuid)from exc
   yield
  finally:
   for f in reversed(held):fcntl.flock(f,fcntl.LOCK_UN);f.close()
 def service(self,verb):
  if verb not in ('stop','start'):raise Refusal('unexpected service action')
  r=self.command(['/usr/bin/systemctl',verb,UNIT])
  if r['exit_code']!=0:raise Refusal('LightDM '+verb+' returned '+str(r['exit_code']))
 def reset_gpu1(self):
  # No configurable target and no retry, fallback, peer reset or driver action.
  self.verify();return self.command([str(LIBROOT/'extracted/nvidia-smi'),'--gpu-reset','--id='+GPU1])

def display_independent(process,sessions):
 env=process['display_environment']
 if env.get('WAYLAND_DISPLAY'):return False
 display=env.get('DISPLAY')
 if not display and not env.get('XAUTHORITY'):return True
 # Reviewed XRDP sessions may retain their own display; local LightDM :0 may not.
 if '/lightdm/'in (env.get('XAUTHORITY')or''):return False
 for session in sessions:
  sd=session.get('Display','')
  remote=re.fullmatch(r':([1-9][0-9]*)(?:\.[0-9]+)?',sd);actual=re.fullmatch(r':([1-9][0-9]*)(?:\.[0-9]+)?',display or'')
  if session.get('Service')=='xrdp-sesman'and not session.get('Seat')and remote and actual and remote.group(1)==actual.group(1)and any(under(cg,session['ControlGroup'])for cg in process['cgroups']):return True
 return False

def validate_device_clients(s,allow_xorg):
 clients=s.get('device_clients')
 if not isinstance(clients,dict)or set(clients)!=set(DEVICE_NODES):raise Refusal('GPU device-holder inventory is missing or incomplete')
 for node,pids in clients.items():
  for pid in pids:
   r=s['processes'].get(pid)
   expected=allow_xorg and r and r['uid']==0 and r['exe']=='/usr/lib/xorg/Xorg'and':0'in r.get('_args',[])and any(under(g,UNIT_CGROUP)for g in r['cgroups'])
   if not expected:raise Refusal('unexpected GPU device holder: '+node+' PID'+str(pid)+' '+(r.get('comm',r.get('exe','unknown'))if r else'identity unavailable'))

def validate_before(s):
 u=s['unit']
 if u.get('ActiveState')!='active'or u.get('SubState')!='running'or u.get('ControlGroup')!=UNIT_CGROUP or u.get('KillMode')!='control-group':raise Refusal('LightDM state/kill scope is not the reviewed active unit')
 main=int(u.get('MainPID','0'));proc=s['processes'];m=proc.get(main)
 if not m or m['uid']!=0 or m['exe']!='/usr/sbin/lightdm'or not any(under(cg,UNIT_CGROUP)for cg in m['cgroups']):raise Refusal('LightDM MainPID identity is unverified')
 greeters=[]
 for session in s['sessions']:
  if not session.get('ControlGroup'):raise Refusal('unknown session control group')
  if session.get('Seat'):
   if not(session['Seat']=='seat0'and session.get('Name')=='lightdm'and session.get('Class')=='greeter'and session.get('Service')=='lightdm-greeter'and session.get('Display')==':0'):raise Refusal('seat0/other seat has a non-reviewed human or unknown session')
   greeters.append(session)
 if len(greeters)!=1:raise Refusal('exactly one reviewed seat0 greeter is required')
 groups=[UNIT_CGROUP,greeters[0]['ControlGroup']];greeter_uid=int(greeters[0]['User'])
 for session in s['sessions']:
  if session not in greeters and any(overlap(session['ControlGroup'],g)for g in groups):raise Refusal('another user session overlaps the stop scope')
 for pid,r in proc.items():
  if any(under(cg,UNIT_CGROUP)for cg in r['cgroups']):
   expected_main=r['uid']==0 and r['exe']=='/usr/sbin/lightdm'
   expected_xorg=r['uid']==0 and r['exe']=='/usr/lib/xorg/Xorg'and':0'in r.get('_args',[])
   if not(expected_main or expected_xorg):raise Refusal('unexpected process inside LightDM kill scope')
  if any(under(cg,greeters[0]['ControlGroup'])for cg in r['cgroups'])and r['uid']not in (0,greeter_uid):raise Refusal('another user process is in the greeter stop scope')
 for pid in s['protected_pids']:
  r=proc[pid]
  if any(under(cg,g)for cg in r['cgroups']for g in groups)or not display_independent(r,s['sessions']):raise Refusal('protected M003/Codex/helper process may be affected by LightDM')
 for uuid,clients in s['gpus'].items():
  for client in clients:
   r=proc.get(client['pid'])
   if client['type']!='G'or not r or r['uid']!=0 or r['exe']!='/usr/lib/xorg/Xorg'or':0'not in r.get('_args',[])or not any(under(cg,UNIT_CGROUP)for cg in r['cgroups']):raise Refusal('unexpected GPU client (including external compute): '+uuid+' PID'+str(client['pid']))
 validate_device_clients(s,True)
 return {(pid,proc[pid]['start_ticks'])for pid in s['protected_pids']}

def validate_after_stop(s,protected):
 if s['unit'].get('ActiveState')!='inactive'or s['unit'].get('MainPID')not in ('0',''):raise Refusal('LightDM has not cleanly stopped')
 if any(s['gpus'].values()):raise Refusal('a GPU still has clients after LightDM stop')
 validate_device_clients(s,False)
 for pid,start in protected:
  r=s['processes'].get(pid)
  if not r or r['start_ticks']!=start:raise Refusal('protected process identity changed during maintenance')
  if any(under(g,UNIT_CGROUP)for g in r['cgroups'])or not display_independent(r,s['sessions']):raise Refusal('protected process gained a display/stop dependency')

def maintain(system,execute=False):
 result={'started_at':now(),'execute_requested':execute,'reset_attempts':0,'target_gpu_uuid':GPU1,'stop_attempted':False,'restore_attempted':False,'execution_state':'running'};before=None
 try:
  system.verify();before=system.snapshot('before');protected=validate_before(before)
  with system.locks():
   locked=system.snapshot('locked_before');locked_protected=validate_before(locked)
   for pid,start in protected:
    r=locked['processes'].get(pid)
    if not r or r['start_ticks']!=start:raise Refusal('protected identity changed before stop')
   protected|=locked_protected
   if not execute:result['execution_state']='checked_ready_no_actions';return result
   try:
    result['stop_attempted']=True;system.service('stop')
    stopped=system.snapshot('after_stop');validate_after_stop(stopped,protected)
    result['reset_attempts']=1;r=system.reset_gpu1();result['reset_exit_code']=r['exit_code']
    after=system.snapshot('after_reset');validate_after_stop(after,protected)
    if r['exit_code']!=0:raise Refusal('single GPU1 reset failed; no retries permitted')
    result['execution_state']='reset_completed_not_qualified'
   finally:
    if result['stop_attempted']and before['unit']['ActiveState']=='active':
     result['restore_attempted']=True
     try:
      system.service('start');restored=system.snapshot('after_restore')
      if restored['unit'].get('ActiveState')!='active'or restored['unit'].get('SubState')!='running'or restored['unit'].get('ControlGroup')!=UNIT_CGROUP:raise Refusal('LightDM running service state was not restored')
      main=restored['processes'].get(int(restored['unit'].get('MainPID','0')))
      if not main or main['uid']!=0 or main['exe']!='/usr/sbin/lightdm':raise Refusal('restored LightDM MainPID identity is unverified')
      for pid,start in protected:
       r=restored['processes'].get(pid)
       if not r or r['start_ticks']!=start:raise Refusal('protected process changed at restoration')
      result['lightdm_restored_active']=True;result['lightdm_restored_service_running']=True
      result['seat0_greeter_observed_after_restore']=any(x.get('Class')=='greeter'and x.get('Name')=='lightdm'and x.get('Seat')=='seat0'and x.get('Display')==':0'for x in restored['sessions'])
     except BaseException as exc:result['restore_error']=repr(exc);result['execution_state']='failed';raise
 except BaseException as exc:
  result['execution_state']='refused_or_failed';result['error']=repr(exc)
 finally:
  result['ended_at']=now();system.evidence.write('result.json',result)
 return result

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true',help='permit reviewed LightDM stop, one GPU1 reset, and LightDM restoration');args=parser.parse_args()
 evidence=Evidence(BASE/'runs'/(("execute_"if args.execute else"check_")+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'_'+str(os.getpid())))
 if args.execute and os.geteuid()!=0:
  evidence.write('result.json',{'execution_state':'refused','error':'--execute requires administrator root; no privilege escalation attempted','target_gpu_uuid':GPU1,'captured_at':now()});print('Refused: root required; evidence '+str(evidence.path));return 2
 def interrupted(sig,frame):raise Refusal('maintenance interrupted by signal '+str(sig))
 for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,interrupted)
 result=maintain(System(evidence),args.execute);print(json.dumps({'result':result,'evidence':str(evidence.path)}));return 0 if result['execution_state']in ('checked_ready_no_actions','reset_completed_not_qualified')else 2
if __name__=='__main__':sys.exit(main())
