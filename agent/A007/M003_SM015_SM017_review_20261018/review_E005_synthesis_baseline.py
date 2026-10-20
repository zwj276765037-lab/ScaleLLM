from pathlib import Path
import json,hashlib,datetime,re
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM'); OUT=ROOT/'agent/A007/M003_SM015_SM017_review_20261018'; REPORT=ROOT/'project/hardware/vivado/reports/m002_E005_R003_AT001_fresh_synth'
def read(p):return json.loads(Path(p).read_text())
def identity(p):
 p=Path(p);assert p.suffix.lower()!='.dcp';assert p.stat().st_size<2_000_000,(p,p.stat().st_size)
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def check(i):
 a=identity(i['path']);assert a['bytes']==i['bytes'] and a['sha256']==i['sha256'],(a,i);return a
p8=ROOT/'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation/recovery_parent.json'
p5=ROOT/'project/hardware/vivado/reports/m002_E005_R004_AT003_current_CDC_bound_OPT_place_physopt/recovery_parent.json'
s=read(p8)['synthesis'];assert s==read(p5)['synthesis']
checked={k:check(s[k]) for k in ['manifest','identity','completion','checkpoint_manifest','checkpoint_bindings','execution_closure','frozen_synthesis_anchor']}
a=read(s['frozen_synthesis_anchor']['path']);assert a['source_rows']==s['source_rows']==342
for i in checked.values():
 if Path(i['path']).name in a['anchors']:assert i['sha256']==a['anchors'][Path(i['path']).name]
freeze=ROOT/'project/E005_m002_optimized_implementation/experiment_source/frozen_inputs_before_current_CDC_recovery.json'
old=ROOT/'project/E005_m002_optimized_implementation/experiment_source/frozen_inputs_before_create.json'
design=ROOT/'agent/A006/M003_SM014_design_20261018/design_input_identities.json'
b8=ROOT/'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/input_bindings.json'
b9=ROOT/'project/E009_m003_failed_net_attribution/experiment_source/AT003_scalar_property_fix/baseline.json'
f={x['path']:x for x in read(freeze)['files']}; d={x['path']:x for x in read(design)['production_inputs']};o={x['path']:x for x in read(old)['files']}
assert f==d and len(f)==144
binding8=read(b8);check(binding8['frozen_inputs']['freeze']);check(binding8['parent']);assert binding8['frozen_inputs']['verified_files']==144 and binding8['frozen_inputs']['unchanged']
assert next(x for x in read(b9)['identities'] if x['path']==str(freeze))==identity(freeze)
manifest={line.split(None,1)[1].strip():line.split(None,1)[0] for line in (REPORT/'inputs.sha256').read_text().splitlines() if line.strip()}
common=sorted(set(manifest)&set(d));assert len(manifest)==342 and len(common)==111
assert all(manifest[p]==d[p]['sha256'] for p in common)
changed=[p for p in sorted(set(o)&set(d)) if o[p]!=d[p]];added=sorted(set(d)-set(o));assert len(changed)==6 and all('/scripts/' in p for p in changed);assert len(added)==3
cats={k:[p for p in common if x in p] for k,x in [('RTL','/rtl/'),('active_XDC','/constraints/'),('data','/data/')]}
assert [len(cats[k]) for k in ['RTL','active_XDC','data']]==[88,4,2]
lines=(REPORT/'utilization_hierarchical_post_synth.rpt').read_text().splitlines();rows={}
cols=['total_LUTs','logic_LUTs','LUTRAMs','SRLs','FFs_report_including_AND_OR','RAMB36','RAMB18','URAM','DSP']
for label,n in [('top',25),('u_meta',510),('u_shared_compute',641),('u_shared_compute_self',642)]:
 parts=[x.strip() for x in lines[n-1].split('|')[1:-1]];rows[label]={'line':n,'instance':parts[0],'module':parts[1],**dict(zip(cols,map(int,parts[2:])))}
assert rows['u_meta']['total_LUTs']==347 and rows['u_meta']['URAM']==80 and rows['u_shared_compute']['total_LUTs']==389067
flat=(REPORT/'utilization_post_synth.rpt').read_text().splitlines()
prims={}
for n,line in enumerate(flat,1):
 m=re.match(r'\|\s*(LUT[1-6]|CARRY8|FD\w+)\s*\|\s*(\d+)\s*\|',line)
 if m:prims[m[1]]={'count':int(m[2]),'line':n}
assert prims['CARRY8']['count']==54364
ff=sum(v['count'] for k,v in prims.items() if k.startswith('FD'));assert ff==1029314
status=(REPORT/'launcher_status.txt').read_text();assert 'exit_code=0' in status and 'native_exit_code=0' in status
log=(REPORT/'vivado.log').read_text().splitlines();native=[{'line':n,'text':l} for n,l in enumerate(log,1) if any(x in l for x in ['synth_design completed successfully','COMPLETED: synth reports'])];assert len(native)>=2
out={'observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'execution':'completed_readonly_bounded_metadata_and_reports','verdict':'existing_same_stage_baseline_supported_for_G4_resource_comparison','applicability':'E005 R003 AT001 post-synth; unchanged 144-source record lineage to frozen SM014 baseline; not new E011 synthesis or route result','review':'independent A007; native source/run facts inherited with independent small-file identity checks','small_metadata_checks':checked,'record_identities':[identity(p) for p in [p8,p5,freeze,old,design,b8,b9]],'reports':[identity(REPORT/p) for p in ['utilization_hierarchical_post_synth.rpt','utilization_post_synth.rpt','launcher_status.txt']],'lineage':{'E005_to_E008_synthesis_objects_equal':True,'freeze_vs_SM014_all144_records_equal':True,'actual_synthesis_manifest_entries':342,'shared_SM014_entries':111,'all_shared_sha_equal':True,'shared_categories':{k:len(v) for k,v in cats.items()},'active_XDC_paths':cats['active_XDC'],'old141_to_current144_changed_script_paths':changed,'added_engineering_paths':added,'SM014_not_in_synthesis_inputs':sorted(set(d)-set(manifest)),'production_files_not_reread':True,'E009_DCP_identity_record_only':next(x for x in read(b9)['identities'] if x['path'].endswith('.dcp'))},'hierarchical_resources':rows,'global_primitives':prims,'global_FF_primitive_total':ff,'native_completion_lines':native,'supervision_limit':s['supervision'],'limitations':['DCP contents not read or rehashed; no EDA','144 comparison is identity-record equality, not all144 actual synth inputs; 111 are shared synth inputs','E005 native success supported; original supervisor gap explicitly preserved, not continuous supervision claim','Hierarchy Total LUTs are utilization-adjusted and not equal raw LUT1..6 primitive sum','Hierarchy FFs includes2 global AND/OR vs raw FF primitives; compare like metrics','Global CARRY8=54364; no per-u_meta CARRY column available','Use same-stage same-metric new reports plus explicit added-cone counts; old route counts do not prove synth deltas','Same-stage comparison is possible; hierarchy can change/flatten, actual new scope and inputs must still be verified']}
p=OUT/'E005_same_stage_synthesis_baseline_review.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'file':str(p),'bytes':p.stat().st_size,'sha256':identity(p)['sha256'],'checks':len(checked),'resources':rows},ensure_ascii=False))
