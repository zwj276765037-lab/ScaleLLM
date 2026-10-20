"""CPU-only orchestration and refusal tests; no subprocess/system/GPU calls."""
import contextlib,copy,importlib.util,json,unittest,datetime,hashlib,tempfile
from unittest.mock import patch
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
 return {'unit':{'ActiveState':'active'if active else'inactive','SubState':'running'if active else'dead','MainPID':'2615'if active else'0','ControlGroup':m.UNIT_CGROUP if active else'','KillMode':'control-group'},'sessions':[session,remote]if active else[remote],'gpus':{m.GPU0:copy.deepcopy(clients),m.GPU1:copy.deepcopy(clients)},'device_clients':{node:([2653]if active else[])for node in m.DEVICE_NODES},'processes':procs,'protected_pids':[3708,307468,9000]}

def hidden_holder(s):
 s['device_clients']['/dev/nvidia1'].append(11758)
 s['processes'][11758]=process(11758,'/usr/lib/WebKitWebProcess','/user.slice/user-1001.slice/session-c2.scope',uid=1001)
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
class PersistedFakeSystem(FakeSystem):
 def __init__(self,path):
  super().__init__();self.evidence=m.Evidence(path)
 def snapshot(self,label):
  s=super().snapshot(label);self.evidence.write(label+'.json',s);return s
class Cases(unittest.TestCase):
 def run_case(self,backend,execute=True):return m.maintain(backend,execute)
 def no_actions(self,b):self.assertNotIn('stop',b.calls);self.assertFalse(any(isinstance(c,tuple)for c in b.calls))
 def test_default_check_never_mutates(self):
  b=FakeSystem();r=self.run_case(b,False);self.assertEqual(r['execution_state'],'checked_ready_no_actions');self.no_actions(b)
 def test_public_accepts_integer_pid_keys_and_recursively_filters_private_keys(self):
  original={'processes':{331396:{'pid':331396,'_args':['private'],'nested':[{'visible':1,'_private':'hidden'}]}},'_private':'hidden'}
  unchanged=copy.deepcopy(original)
  expected={'processes':{331396:{'pid':331396,'nested':[{'visible':1}]}}}
  self.assertEqual(m.public(original),expected);self.assertEqual(original,unchanged)
 def test_real_evidence_writes_snapshot_with_integer_pid_keys(self):
  s=snapshot();unchanged=copy.deepcopy(s)
  with tempfile.TemporaryDirectory()as tmp:
   evidence=m.Evidence(Path(tmp)/'run');evidence.write('snapshot.json',s)
   recorded=json.loads((evidence.path/'snapshot.json').read_text())
   self.assertEqual(set(recorded['processes']),{str(pid)for pid in s['processes']})
   self.assertEqual(recorded['processes']['2653']['pid'],2653)
   self.assertTrue(all('_args'not in r for r in recorded['processes'].values()))
   self.assertEqual(s,unchanged);self.assertEqual(len(m.validate_before(s)),3)
 def test_full_fake_maintenance_with_real_evidence_persistence(self):
  with tempfile.TemporaryDirectory()as tmp:
   b=PersistedFakeSystem(Path(tmp)/'run');r=self.run_case(b)
   self.assertEqual(r['execution_state'],'reset_completed_not_qualified')
   self.assertEqual(b.calls.count(('reset',m.GPU1)),1)
   for name in ['before','locked_before','after_stop','after_reset','after_restore']:
    recorded=json.loads((b.evidence.path/(name+'.json')).read_text());self.assertIn('3708',recorded['processes'])
   self.assertEqual(json.loads((b.evidence.path/'result.json').read_text())['execution_state'],'reset_completed_not_qualified')
 def test_real_evidence_preserves_external_gpu0_compute_refusal(self):
  with tempfile.TemporaryDirectory()as tmp:
   b=PersistedFakeSystem(Path(tmp)/'run')
   b.edits['before']=lambda s:s['gpus'][m.GPU0].append({'pid':306724,'type':'C','name':'external worker'})
   r=self.run_case(b);self.no_actions(b);self.assertIn('unexpected GPU client',r['error'])
   recorded=json.loads((b.evidence.path/'result.json').read_text())
   self.assertEqual(recorded['reset_attempts'],0);self.assertFalse(recorded['stop_attempted'])
 def test_external_gpu0_compute_refused_even_with_free_locks(self):
  b=FakeSystem();b.edits['before']=lambda s:s['gpus'][m.GPU0].append({'pid':306724,'type':'C','name':'ScaleLUT worker'});r=self.run_case(b);self.assertIn('unexpected GPU client',r['error']);self.no_actions(b)
 def test_unknown_gpu1_client_refused(self):
  b=FakeSystem();b.edits['before']=lambda s:s['gpus'][m.GPU1].append({'pid':123,'type':'G','name':'unknown'});self.assertEqual(self.run_case(b)['reset_attempts'],0);self.no_actions(b)
 def test_hidden_device_holder_refused_before_any_actions(self):
  with tempfile.TemporaryDirectory()as tmp:
   b=PersistedFakeSystem(Path(tmp)/'run');b.edits['before']=hidden_holder;r=self.run_case(b)
   self.no_actions(b);self.assertIn('/dev/nvidia1 PID11758',r['error'])
   recorded=json.loads((b.evidence.path/'before.json').read_text())
   self.assertIn(11758,recorded['device_clients']['/dev/nvidia1'])
   self.assertNotIn(11758,[p['pid']for p in recorded['gpus'][m.GPU1]])
 def test_device_holder_appearing_during_lock_check_prevents_stop(self):
  b=FakeSystem();b.edits['locked_before']=hidden_holder;r=self.run_case(b)
  self.no_actions(b);self.assertIn('unexpected GPU device holder',r['error'])
 def test_device_holder_appearing_after_stop_restores_without_reset(self):
  b=FakeSystem();b.edits['after_stop']=hidden_holder;r=self.run_case(b)
  self.assertIn('stop',b.calls);self.assertIn('start',b.calls);self.assertEqual(r['reset_attempts'],0)
  self.assertIn('unexpected GPU device holder',r['error'])
 def test_xorg_device_holder_remaining_after_stop_refused(self):
  b=FakeSystem()
  def residual(s):
   s['device_clients']['/dev/nvidia1']=[2653]
   s['processes'][2653]=process(2653,'/usr/lib/xorg/Xorg',m.UNIT_CGROUP,args=['Xorg',':0'])
  b.edits['after_stop']=residual;r=self.run_case(b)
  self.assertEqual(r['reset_attempts'],0);self.assertIn('start',b.calls)
 def test_missing_or_incomplete_device_inventory_prevents_actions(self):
  for change in [lambda s:s.pop('device_clients'),lambda s:s['device_clients'].pop('/dev/nvidia1')]:
   b=FakeSystem();b.edits['before']=change;r=self.run_case(b)
   self.no_actions(b);self.assertIn('inventory is missing or incomplete',r['error'])
 def test_device_holder_without_identity_refused(self):
  b=FakeSystem();b.edits['before']=lambda s:s['device_clients']['/dev/nvidia1'].append(12345)
  r=self.run_case(b);self.no_actions(b);self.assertIn('identity unavailable',r['error'])
 def test_device_inventory_requires_root_before_commands(self):
  b=m.System(MemoryEvidence());calls=[];b.command=lambda argv:calls.append(argv)
  with patch.object(m.os,'geteuid',return_value=1001):
   with self.assertRaisesRegex(m.Refusal,'root is required'):b.device_inventory()
  self.assertEqual(calls,[])
 def test_device_inventory_parses_pids_access_codes_and_empty_nodes(self):
  b=m.System(MemoryEvidence());calls=[]
  def command(argv):
   calls.append(argv);node=argv[-1]
   return {'exit_code':0,'stdout':' 11758 2653 11758','stderr':node+':    m F\n'}if node=='/dev/nvidia1'else{'exit_code':1,'stdout':'','stderr':''}
  b.command=command
  with patch.object(m.os,'geteuid',return_value=0):result=b.device_inventory()
  self.assertEqual(result['/dev/nvidia1'],[2653,11758]);self.assertTrue(all(not v for k,v in result.items()if k!='/dev/nvidia1'))
  self.assertEqual(calls,[['/usr/bin/fuser',node]for node in m.DEVICE_NODES])
 def test_device_inventory_rejects_errors_and_incomplete_output(self):
  records=[{'exit_code':2,'stdout':'','stderr':''},
   {'exit_code':1,'stdout':'','stderr':'Permission denied'},
   {'exit_code':1,'stdout':'11758','stderr':''},
   {'exit_code':0,'stdout':'','stderr':'/dev/nvidia1:'},
   {'exit_code':0,'stdout':'PID11758','stderr':'/dev/nvidia1:'},
   {'exit_code':0,'stdout':'11758','stderr':'/dev/nvidia1: Permission denied'},
   {'exit_code':0,'stdout':'11758','stderr':'/dev/nvidia0:'}]
  for record in records:
   with self.subTest(record=record):
    b=m.System(MemoryEvidence());b.command=lambda argv:record
    with patch.object(m.os,'geteuid',return_value=0):
     with self.assertRaises(m.Refusal):b.device_inventory()
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
 def test_loginctl_uses_one_property_argument_per_field(self):
  b=m.System(MemoryEvidence());calls=[]
  b.checked=lambda argv:calls.append(argv)or'Scope=session-115.scope\nId=115\n'
  properties=b.session_properties('115');self.assertEqual(properties['Scope'],'session-115.scope')
  fields=('Id','Name','User','Seat','Display','Service','Class','Type','Leader','Scope','State')
  expected=['/usr/bin/loginctl','show-session','115']
  for field in fields:expected.extend(['--property',field])
  self.assertEqual(calls,[expected]);self.assertFalse(any(','in arg for arg in calls[0]))
 def test_real_reset_argv_is_fixed_gpu1_only(self):
  b=m.System(MemoryEvidence());calls=[];b.verify=lambda:None;b.command=lambda argv:calls.append(argv)or{'exit_code':0};b.reset_gpu1();self.assertEqual(calls,[[str(m.LIBROOT/'extracted/nvidia-smi'),'--gpu-reset','--id='+m.GPU1]])
if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(Cases);result=unittest.TextTestRunner(verbosity=2).run(suite);record={'schema':'scalellm_gpu1_maintenance_CPU_mock_v1','captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'CPU_only':True,'real_system_commands':0,'real_GPU_calls':0,'real_service_actions':0,'helper_sha256':hashlib.sha256((p/'gpu1_maintenance.py').read_bytes()).hexdigest(),'test_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'successful':result.wasSuccessful()};(p/'mock_results.json').write_text(json.dumps(record,indent=2)+'\n');raise SystemExit(0 if result.wasSuccessful()else 1)
