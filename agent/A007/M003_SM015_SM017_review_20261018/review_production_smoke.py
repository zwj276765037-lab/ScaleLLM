from pathlib import Path
import json,hashlib,re,datetime
R=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');O=R/'agent/A007/M003_SM015_SM017_review_20261018';J=R/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R001/attempts/AT003_core_boundary_and_registered_entry/evidence/jobs/selected_production_smoke';P=R/'project/hardware/vivado/reports/m003_E011_R001_AT003_production_smoke'
def read(p):return json.loads(p.read_text())
def ident(p):
 p=Path(p);b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def verify(x):
 a=ident(x['path']);assert all(a[k]==x[k] for k in ['bytes','sha256']),(a,x);return a
cmd=read(J/'command.json');st=read(J/'status.json');assert st['execution_state']=='completed' and st['native_exit_code']==0 and not st['stop_reason'] and not st['owned_survivors'] and st['core_RTL_unchanged_during_job']
assert cmd['timeout_seconds'] is None and cmd['no_output_timeout_seconds'] is None and cmd['cpu_affinity']==list(range(8)) and cmd['nice']==5
verify(cmd['source_archive']);archive=read(J/'source_archive.json');assert archive['observed_utc']<=cmd['started_utc'];bindings=[]
for row in archive['bindings']:
 a=verify(row['original']);b=verify(row['preserved']);assert a['sha256']==b['sha256'];bindings.append({'original':a,'preserved':b})
by_original={r['original']['path']:r['original'] for r in bindings}
for key in ['G2','supervisor','ownership_helpers']:assert by_original[cmd[key]['path']]==cmd[key]
for item in cmd['core_RTL']:assert by_original[item['path']]==item
inputs=[]
for line in (P/'inputs.sha256').read_text().splitlines():
 h,p=line.split(None,1);a=ident(p.strip());assert a['sha256']==h;assert by_original[a['path']]==a;inputs.append(a)
tbp=R/'project/hardware/tb/hap_m003_selected_production_smoke_tb.sv';tb=tbp.read_text();body=re.sub(r'//[^\n]*','',tb);assert not re.search(r'\b(force|release)\b',body)
reads=re.findall(r'read_csr\(12\'h([0-9a-f]+),32\'h([0-9a-f]+)\)',tb);assert reads==[('000','48384103'),('004','00020000'),('100','48384605'),('104','00050000'),('000','48384103'),('100','48384605')]
assert 'u_meta.LOCAL_ADDR_COPIES!=1' in tb and 'u_shared_compute.TILE_W!=9' in tb
text=(P/'xsim.log').read_text();assert 'M003_PRODUCTION_SMOKE checks=6 A3_mode1 M2_TILE9 asynchronous_DDR_clocks maintenance' in text and '\nHARDWARE_AGENT_SIM_PASS\n' in text and '$finish called at time : 1790 ns' in text and not (P/'fault_lines.txt').read_text().strip()
launcher=dict(line.split('=',1) for line in (P/'launcher_status.txt').read_text().splitlines() if '=' in line);assert launcher['exit_code']=='0' and launcher['phase']=='complete' and launcher['step_timeout_seconds']=='0'
result={'observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'execution':'completed','verdict':'SELECTED_PRODUCTION_TOP_SMOKE_ACCEPTED','applicability':'Real hap_attention_mlp_production_core, production A3 mode1 and M2 TILE_W9 hierarchy; no force; reset/AXIL CSR read/stall/public maintenance only. Complete Attention/MLP command and DDR data transactions not exercised.','review':'A007 native source/archive/assertion scope verified','core_RTL':cmd['core_RTL'],'job_status':st,'input_count':len(inputs),'archive_binding_count':len(bindings),'raw_evidence':[ident(P/n) for n in ['launcher_status.txt','inputs.sha256','argv.txt','xvlog.log','xelab.log','xsim.log','fault_lines.txt']]+[ident(J/n) for n in ['command.json','status.json','started.json','resources.jsonl','source_archive.json']],'verified_inputs':inputs,'preexecution_archive_bindings':bindings,'smoke_scope':{'force_used':False,'clocks_ns':{'core_period':10,'DDR0_period':5,'DDR1_period':5,'DDR1_initial_offset':1.25},'CSR_reads_hex':reads,'response_stall_cycles_each':3,'reset_initial_cycles':5,'public_core_clear_cycles':1,'post_maintenance_wait_cycles':100,'integration_error_expected':0,'finish_ns':1790,'xpm_initial_SIM_ASSERT_CHK_notice_count':text.count('Warning: SIM_ASSERT_CHK (1)'),'notice_interpretation':'XPM announcement of simulation assertion checking at1ps, not detected transaction error'},'G3b_total_passed':False,'no_A007_EDA':True}
p=O/'AT003_selected_production_smoke_review.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'review':ident(p),'input_count':len(inputs),'archive_binding_count':len(bindings)},ensure_ascii=False))
