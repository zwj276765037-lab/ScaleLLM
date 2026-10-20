"""CPU-only orchestration and refusal tests; no subprocess/system/GPU calls."""
import contextlib,copy,importlib.util,json,unittest,datetime,hashlib
from pathlib import Path
p=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('maintenance',p/'gpu1_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def process(pid,exe,cg,roles=(),uid=0,args=()):return {'pid':pid,'start_ticks':pid*10,'exe':exe,'uid':uid,'cgroups':[cg],'roles':list(roles),'_args':list(args),'display_environment':{k:None for k in (*m.DISPLAY_KEYS,'XDG_SESSION_ID')}}
def snapshot(active=True):
 session={'Id':'c1','Name':'lightdm','User':'106','Seat':'seat0','Class':'greeter','Service':'lightdm-greeter','Display':':0','ControlGroup':'/user.slice/user-106.slice/session-c1.scope'}
 remote={'Id':'c2','Name':'zwj','User':'1001','Seat':'','Class':'user','Service':'xrdp-sesman','Display':':10','ControlGroup':'/user.slice/user-1001.slice/session-c2.scope'}
 procs={3708:process(3708,'/opt/codex/codex','/user.slice/user-1001.slice/session-6.scope',['Codex']),307468:process(307468,'/tools/Vivado/vivado','/user.slice/user-1001.slice/session-6.scope',['M003_or_EDA']),9000:process(9000,'/usr/bin/python3','/user.slice/user-1001.slice/session-6.scope',['helper_or_ancestor'])}
 if active:procs.update({2615:process(2615,'/usr/sbin/lightdm',m.UNIT_CGROUP),2653:process(2653,'/usr/lib/xorg/Xorg',m.UNIT_CGROUP,args=['Xorg',':0'])})
 clients=[{'pid':2653,'type':'G','name':'/usr/lib/xorg/Xorg'}]if active else[]
 return {'unit':{'ActiveState':'active'if active else'inactive','SubState':'running'if active else'dead','MainPID':'2615'if active else'0','ControlGroup':m.UNIT_CGROUP if active else'','KillMode':'control-group'},'sessions':[session,remote]if active else[remote],'gpus':{m.GPU0:copy.deepcopy(clients),m.GPU1:copy.deepcopy(clients)},'processes':procs,'protected_pids':[3708,307468,9000]}
class MemoryEvidence:
 def __init__(self):self.docs={}
 def write(self,name,value):self.docs[name]=copy.deepcopy(value)
class FakeSystem:
 def __init__(self):self.evidence=MemoryEvidence();self.calls=[];self.edits={};self.lock_busy=False;self.stop_fail=False;self.reset_rc=0;self.start_fail=False;self.verify_fail=False
 def verify(self):
  self.calls.append('verify')
  if self.verify_fail:raise m.Refusal('mock kernel/file SHA mismatch')
 def snapshot(self,label):
  self.calls.append(label)
  s=snapshot(active=label not in ('after_stop','after_reset'))
  if label in self.edits:
   change=self.edits[label]
   if isinstance(change,Exception):raise change
   change(s)
  return s
 @contextlib.contextmanager
 def locks(self):
  self.calls.append('locks')
  if self.lock_busy:raise m.Refusal('mock GPU0 lock busy')
  try:yield
  finally:self.calls.append('unlock')
 def service(self,verb):
  self.calls.append(verb)
  if verb=='stop'and self.stop_fail:raise m.Refusal('mock partial stop failure')
  if verb=='start'and self.start_fail:raise m.Refusal('mock restore failure')
 def reset_gpu1(self):self.calls.append(('reset',m.GPU1));return {'exit_code':self.reset_rc}
class Cases(unittest.TestCase):
 def run_case(self,backend,execute=True):return m.maintain(backend,execute)
 def no_actions(self,b):self.assertNotIn('stop',b.calls);self.assertFalse(any(isinstance(c,tuple)for c in b.calls))
 def test_default_check_never_mutates(self):
  b=FakeSystem();r=self.run_case(b,False);self.assertEqual(r['execution_state'],'checked_ready_no_actions');self.no_actions(b)
 def test_external_gpu0_compute_refused_even_with_free_locks(self):
  b=FakeSystem();b.edits['before']=lambda s:s['gpus'][m.GPU0].append({'pid':306724,'type':'C','name':'ScaleLUT worker'});r=self.run_case(b);self.assertIn('unexpected GPU client',r['error']);self.no_actions(b)
 def test_unknown_gpu1_client_refused(self):
  b=FakeSystem();b.edits['before']=lambda s:s['gpus'][m.GPU1].append({'pid':123,'type':'G','name':'unknown'});self.assertEqual(self.run_case(b)['reset_attempts'],0);self.no_actions(b)
 def test_busy_gpu0_lock_refused(self):
  b=FakeSystem();b.lock_busy=True;self.run_case(b);self.no_actions(b)
 def test_file_or_kernel_identity_refused(self):
  b=FakeSystem();b.verify_fail=True;self.run_case(b);self.no_actions(b)
 def test_human_seat0_refused(self):
  b=FakeSystem();b.edits['before']=lambda s:s['sessions'][0].update(Name='zwj',Class='user');self.run_case(b);self.no_actions(b)
 def test_unknown_session_scope_refused(self):
  b=FakeSystem();b.edits['before']=lambda s:s['sessions'][1].update(ControlGroup='');self.run_case(b);self.no_actions(b)
 def test_codex_in_lightdm_scope_refused(self):
  b=FakeSystem();b.edits['before']=lambda s:s['processes'][3708].update(cgroups=[m.UNIT_CGROUP]);self.run_case(b);self.no_actions(b)
 def test_helper_ancestor_in_greeter_scope_refused(self):
  b=FakeSystem();b.edits['before']=lambda s:s['processes'][9000].update(cgroups=[s['sessions'][0]['ControlGroup']]);self.run_case(b);self.no_actions(b)
 def test_protected_local_display_refused(self):
  b=FakeSystem();b.edits['before']=lambda s:s['processes'][3708]['display_environment'].update(DISPLAY=':0');self.run_case(b);self.no_actions(b)
 def test_reviewed_xrdp_display_can_remain(self):
  b=FakeSystem()
  def xrdp(s):s['processes'][9000].update(cgroups=[s['sessions'][-1]['ControlGroup']]);s['processes'][9000]['display_environment'].update(DISPLAY=':10.0',XAUTHORITY='/home/zwj/.Xauthority')
  b.edits={k:xrdp for k in ['before','locked_before','after_stop','after_reset','after_restore']};r=self.run_case(b);self.assertEqual(r['execution_state'],'reset_completed_not_qualified')
 def test_xrdp_display_zero_alias_refused(self):
  for display in [':0',':0.0','localhost:0',':00.0']:
   b=FakeSystem()
   def bad(s):s['sessions'][-1]['Display']=display;s['processes'][9000].update(cgroups=[s['sessions'][-1]['ControlGroup']]);s['processes'][9000]['display_environment'].update(DISPLAY=display)
   b.edits['before']=bad;self.run_case(b);self.no_actions(b)
 def test_unknown_process_in_lightdm_refused(self):
  b=FakeSystem();b.edits['before']=lambda s:s['processes'].update({44:process(44,'/usr/bin/python3',m.UNIT_CGROUP)});self.run_case(b);self.no_actions(b)
 def test_protected_change_before_stop_refused(self):
  b=FakeSystem();b.edits['locked_before']=lambda s:s['processes'][3708].update(start_ticks=1);self.run_case(b);self.no_actions(b)
 def test_stop_nonzero_restores_even_if_partial(self):
  b=FakeSystem();b.stop_fail=True;r=self.run_case(b);self.assertTrue(r['restore_attempted']);self.assertIn('start',b.calls);self.assertEqual(r['reset_attempts'],0)
 def test_post_stop_unknown_client_restores_without_reset(self):
  b=FakeSystem();b.edits['after_stop']=lambda s:s['gpus'][m.GPU1].append({'pid':55,'type':'C','name':'new worker'});r=self.run_case(b);self.assertIn('start',b.calls);self.assertEqual(r['reset_attempts'],0)
 def test_post_stop_snapshot_failure_restores(self):
  b=FakeSystem();b.edits['after_stop']=m.Refusal('mock capture failed');self.run_case(b);self.assertIn('start',b.calls)
 def test_single_reset_failure_still_restores(self):
  b=FakeSystem();b.reset_rc=1;r=self.run_case(b);self.assertEqual(r['reset_attempts'],1);self.assertEqual(b.calls.count(('reset',m.GPU1)),1);self.assertTrue(r['lightdm_restored_active'])
 def test_success_one_target_and_restore_before_unlock(self):
  b=FakeSystem();r=self.run_case(b);self.assertEqual(r['execution_state'],'reset_completed_not_qualified');self.assertEqual(b.calls.count(('reset',m.GPU1)),1);self.assertLess(b.calls.index('start'),b.calls.index('unlock'));self.assertTrue(r['lightdm_restored_active'])
 def test_restore_failure_reported_without_retry(self):
  b=FakeSystem();b.start_fail=True;r=self.run_case(b);self.assertIn('restore_error',r);self.assertEqual(b.calls.count('start'),1);self.assertNotEqual(r['execution_state'],'reset_completed_not_qualified')
 def test_real_reset_argv_is_fixed_gpu1_only(self):
  b=m.System(MemoryEvidence());calls=[];b.verify=lambda:None;b.command=lambda argv:calls.append(argv)or{'exit_code':0};b.reset_gpu1();self.assertEqual(calls,[[str(m.LIBROOT/'extracted/nvidia-smi'),'--gpu-reset','--id='+m.GPU1]])
if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(Cases);result=unittest.TextTestRunner(verbosity=2).run(suite);record={'schema':'scalellm_gpu1_maintenance_CPU_mock_v1','captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'CPU_only':True,'real_system_commands':0,'real_GPU_calls':0,'real_service_actions':0,'helper_sha256':hashlib.sha256((p/'gpu1_maintenance.py').read_bytes()).hexdigest(),'test_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'successful':result.wasSuccessful()};(p/'mock_results.json').write_text(json.dumps(record,indent=2)+'\n');raise SystemExit(0 if result.wasSuccessful()else 1)
