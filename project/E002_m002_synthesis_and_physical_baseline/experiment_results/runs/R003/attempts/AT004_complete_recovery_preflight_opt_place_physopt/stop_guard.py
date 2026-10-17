import datetime,hashlib,json,os,signal,time
from pathlib import Path
attempt=Path(__file__).resolve().parent
started=json.loads((attempt/'started.json').read_text())
report=Path(started['report']);supervisor=started['supervisor_pid'];leader=started['leader_pid']
def stat(pid):
 raw=Path(f'/proc/{pid}/stat').read_text();fields=raw[raw.rfind(')')+2:].split();return {'ppid':int(fields[1]),'start_ticks':int(fields[19])}
def ident(path):
 return {'path':str(path),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
expected_supervisor=stat(supervisor);expected_leader=stat(leader)
assert expected_leader['ppid']==supervisor
assert 'run_managed_eda.py' in Path(f'/proc/{supervisor}/cmdline').read_text()
print(json.dumps({'guard_started':True,'supervisor':supervisor,'leader':leader}),flush=True)
while True:
 try:
  assert stat(supervisor)==expected_supervisor and stat(leader)==expected_leader
 except (FileNotFoundError,AssertionError):
  print('guard ended: original owned task no longer active',flush=True);break
 required=['opt_command_result.txt','opt.dcp','opt_result.txt','check_timing_opt.rpt','clocks_opt.rpt']
 if all((report/name).is_file() and (report/name).stat().st_size for name in required):
  receipt=(report/'opt_command_result.txt').read_text();result=(report/'opt_result.txt').read_text();timing=(report/'check_timing_opt.rpt').read_text();log=(report/'vivado.log').read_text()
  if 'native_tcl_code=0' in receipt and 'blackboxes=0' in result and all('checking '+name+' (' in timing for name in ['no_clock','unconstrained_internal_endpoints','multiple_clock','generated_clocks','loops','pulse_width_clock']) and f"The checkpoint '{report/'opt.dcp'}' has been generated" in log:
   assert 'Command: place_design' not in log
   value={'reason':'missing_explicit_pre_place_debug_implementation','requested_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'supervisor_pid':supervisor,'leader_pid':leader,'supervisor_identity':expected_supervisor,'leader_identity':expected_leader,'report':str(report),'opt_proof':{name:ident(report/name) for name in required},'scope':'preserve actual OPT and clocks; stop this owned task before place; original exit/stop state retained'}
   (attempt/'controlled_stop_request.json').write_text(json.dumps(value,indent=2)+'\n')
   assert stat(supervisor)==expected_supervisor and stat(leader)==expected_leader
   os.kill(supervisor,signal.SIGTERM);print('owned supervisor signaled after completed OPT DCP and clock evidence; before place',flush=True);break
 time.sleep(2)
