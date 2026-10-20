from pathlib import Path
import json,hashlib,re,datetime
R=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');O=R/'agent/A007/M003_SM015_SM017_review_20261018';J=R/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R001/attempts/AT002_native_functional_absolute_entry/evidence/jobs/M2_legacy_dispatch';P=R/'project/hardware/vivado/reports/m003_E011_R001_AT002_M2_legacy_dispatch'
def read(p):return json.loads(p.read_text())
def ident(p):
 p=Path(p);b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def verify(x):
 actual=ident(x['path']);assert all(actual[k]==x[k] for k in ['bytes','sha256']),(actual,x);return actual
command=read(J/'command.json');status=read(J/'status.json');assert status['execution_state']=='completed' and status['native_exit_code']==0 and not status['stop_reason'] and not status['owned_survivors'] and status['core_RTL_unchanged_during_job']
assert command['timeout_seconds'] is None and command['no_output_timeout_seconds'] is None and command['cpu_affinity']==list(range(8)) and command['nice']==5
verify(command['source_archive']);archive=read(J/'source_archive.json');assert archive['observed_utc']<=command['started_utc'];bindings=[]
for row in archive['bindings']:
 a=verify(row['original']);b=verify(row['preserved']);assert a['sha256']==b['sha256'];bindings.append({'original':a,'preserved':b})
by_original={r['original']['path']:r['original'] for r in bindings}
for key in ['G2','supervisor','ownership_helpers']:assert by_original[command[key]['path']]==command[key]
for item in command['core_RTL']:assert by_original[item['path']]==item
inputs=[]
for line in (P/'inputs.sha256').read_text().splitlines():
 sha,p=line.split(None,1);a=ident(p.strip());assert a['sha256']==sha;assert by_original[a['path']]==a;inputs.append(a)
assert len(inputs)==131
old=read(O/'AT002_M2_production_dispatch_review.json')['original_reference'];bench=R/old['path'];assert ident(bench)['sha256']==old['sha256']=='bf897659a9f7cf96849891d2ba0b94def4eb5ef9937903e7e20d08fd28334405'
tb=bench.read_text();assert 'GG=128,DG=448,DT=4,TOTAL=GG*2+DG*DT' in tb and '.DOWN_TILES(DT),.DOWN_GROUPS(DG)' in tb and '.TILE_W' not in tb
rtl=(R/'project/hardware/rtl/mlp/hap_mlp_shared_dual_slice16x12_s44_s54.sv').read_text();assert '(DOWN_TILES <= 2) ? 1 : $clog2(DOWN_TILES)' in rtl and 'if (TILE_W == 9 && PARENT_PAYLOAD_W == 6560)' in rtl and 'g_original_parent_ce' in rtl
text=(P/'xsim.log').read_text();phases=[list(map(int,m)) for m in re.findall(r'DISPATCH phase=(\d+) inputs=(\d+) branches=(\d+)/(\d+) issue_cycles=(\d+) first_output=(\d+) ii=(\d+)/(\d+)/(\d+)',text)];assert phases==[[0,2048,2048,2048,2048,148,1,1,1],[1,2048,2048,2048,2048,157,1,1,1]]
assert 'DISPATCH checks=2304 stable=42' in text and 'HARDWARE_AGENT_SIM_PASS' in text and '$finish called at time : 42110 ns' in text and not (P/'fault_lines.txt').read_text().strip()
launcher=dict(line.split('=',1) for line in (P/'launcher_status.txt').read_text().splitlines() if '=' in line);assert launcher['exit_code']=='0' and launcher['phase']=='complete' and launcher['step_timeout_seconds']=='0'
result={'observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'execution':'completed','verdict':'M2_REDUCED_PARAMETER_LEGACY_DISPATCH_ACCEPTED','applicability':'Actual unchanged integer-reference dispatch bench, DOWN_TILES4/DOWN_GROUPS448/default TILE_W2 exercises original CE compatibility branch; real full parent/branches/kernels. Does not claim full342tile workload or post-synth/physical qualification.','review':'A007 independent native/raw/source-archive verification; same selected3RTL and G2','core_RTL':command['core_RTL'],'job_status':status,'command_identity':ident(J/'command.json'),'raw_evidence':[ident(P/n) for n in ['launcher_status.txt','inputs.sha256','argv.txt','xvlog.log','xelab.log','xsim.log','fault_lines.txt']]+[ident(J/n) for n in ['status.json','started.json','resources.jsonl','source_archive.json']],'verified_inputs':inputs,'preexecution_archive_bindings':bindings,'input_count':len(inputs),'archive_binding_count':len(bindings),'results':{'phases':phases,'phase_fields':['phase','inputs','branch0','branch1','issue_cycles','first_output','maxII_input','maxII_branch0','maxII_branch1'],'integer_lane_checks':2304,'stall_stability_checks':42,'inflight_clear':True,'default_TILE_W':2,'simulation_finish_ns':42110},'remaining':['actual cohort core A3 integration/labels/sidebands and joint regression','G3b formal overlay/checker/restore positive-negative evidence','new synthesis/G4 and full physical qualification'],'G3a_total_passed':False,'no_A007_EDA':True}
p=O/'AT002_M2_legacy_dispatch_review.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'review':ident(p),'input_count':len(inputs),'archive_binding_count':len(bindings),'phases':phases},ensure_ascii=False))
