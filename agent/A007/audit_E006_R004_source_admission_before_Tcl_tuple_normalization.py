#!/usr/bin/env python3
"""Bounded independent CPU source identity/selection checks; never launch EDA."""
from pathlib import Path
import ast,hashlib,json,re,subprocess,datetime,tkinter
ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'agent/A006/E006_exact_candidates'
OUT=ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R004'
def ident(p):
 p=Path(p);b=p.read_bytes();return {'path':str(p.resolve()),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def check(row):
 actual=ident(row['path']);assert actual['bytes']==row['bytes'] and actual['sha256']==row['sha256'],row['path'];return actual
m_path=SRC/'prepared_source_manifest.json';start=ident(m_path)
assert start['sha256']=='29b84a338ec696ab2ed68e4b246d12fc3e0313459c75e1fc8102b3527bb677b7' and start['bytes']==6641
m=json.loads(m_path.read_text());verified=[];stat_only=[]
for row in m['source_files']:verified.append(check(row))
for k in ['scope_contract','candidate_targets','execution_authorization','inspector_derivation','upstream_repair_source_manifest']:verified.append(check(m[k]))
for row in m['CPU_checks']:verified.append(check(row))
auth=json.loads(Path(m['execution_authorization']['path']).read_text())
for row in auth.values():
 if isinstance(row,dict) and {'path','bytes','sha256'}.issubset(row):verified.append(check(row))
target_manifest=json.loads((SRC/'targets_manifest.json').read_text())
for row in target_manifest['external_inputs'].values():verified.append(check(row))
reuse=json.loads((SRC/'reuse_manifest.json').read_text())
for key,row in reuse['artifacts'].items():
 if row['bytes']<=8*1024*1024:verified.append(check(row))
 else:
  p=Path(row['path']);assert p.stat().st_size==row['bytes'];stat_only.append(dict(label=key,**row,independent_current_SHA256=False,reason='closed producer identity reused; independent stat only to avoid repeated large export scans'))
assert Path(reuse['checkpoint']['path']).stat().st_size==reuse['checkpoint']['bytes']
stat_only.append(dict(label='unchanged physopt DCP',**reuse['checkpoint'],independent_current_SHA256=False,reason='engineering hash binding and independent stat; no large DCP read'))
parsed=[]
for row in m['source_files']:
 if row['path'].endswith('.py'):ast.parse(Path(row['path']).read_text());parsed.append(row['path'])
old=ROOT/'agent/A006/E006_lean_candidate/run_attribution_lean.py';new=SRC/'run_attribution_lean.py'
def funcs(p):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)}
of,nf=funcs(old),funcs(new);unchanged=[name for name in of if name!='main' and of[name]==nf.get(name)]
assert set(unchanged)==set(of)-{'main'}
anchor='    proc=None;tracked={};stop=None;peak=0;low_since=None'
assert old.read_text().split(anchor,1)[1]==new.read_text().split(anchor,1)[1]
for name in ['candidate_inspector.tcl','attribution_lean.tcl']:
 txt=(SRC/name).read_text();assert not re.search(r'\b(create_pblock|resize_pblock|add_cells_to_pblock|set_property|place_design|phys_opt_design|route_design|synth_design|write_checkpoint|write_bitstream)\b',txt)
t= tkinter.Tcl();t.eval('source {'+str(SRC/'targets.tcl')+'}');old_t=tkinter.Tcl();old_t.eval('source {'+str(ROOT/'agent/A006/E006_lean_candidate/targets.tcl')+'}')
for key in ['owner_roots','regions','failure_nets','failure_nodes']:
 try: newvalue=t.getvar(key);oldvalue=old_t.getvar(key)
 except tkinter.TclError:
  if key=='failure_nets': key='failure_targets';newvalue=t.getvar(key);oldvalue=old_t.getvar(key)
  else:raise
 assert newvalue==oldvalue,key
actual=[list(t.splitlist(x)) for x in t.splitlist(t.getvar('exact_candidate_targets'))]
targets=json.loads(Path(m['candidate_targets']['path']).read_text());assert actual==[[x['id'],x['root']] for x in targets['candidates']]
assert len(t.splitlist(t.getvar('failed_alignment_objects')))==9
ct=json.loads((SRC/'bounded_CPU_validation_CT003.json').read_text());assert ct['exit_code']==0 and ct['EDA_executed'] is False
for row in ct['source_files']:verified.append(check(row))
# Replay only the recorded pure-Tcl expressions; no native query commands exist here.
r=subprocess.run(['tclsh'],input=ct['Tcl_semantics_and_literal_selector']['stdin'],text=True,capture_output=True,check=False)
assert r.returncode==0 and r.stderr=='' and r.stdout==ct['Tcl_semantics_and_literal_selector']['stdout']
# Independent compressed-vector scalar-empty case and mandatory-empty rejection.
t2=tkinter.Tcl();t2.eval('source {'+str(SRC/'property_alignment.tcl')+'}')
audit=OUT/'independent_property_fallback_CPU.tsv';assert not audit.exists()
t2.eval('''proc get_property {quiet property objects} {
 if {$property eq "NAME"} {return $objects}
 if {$property eq "LOC"} {if {[llength $objects]>1} {return SLICE_X0Y0}; if {$objects eq "a"} {return ""};return SLICE_X0Y0}
 if {$property eq "REF_NAME"} {if {[llength $objects]>1} {return FDRE};if {$objects eq "a"} {return ""};return FDRE}
 error unexpected_property
}''')
vals=t2.call('propertyalign::values',('a','b'),'LOC',1,'independent_mixed_empty',str(audit));assert list(t2.splitlist(vals))==['','SLICE_X0Y0']
rejected=False
try:t2.call('propertyalign::values',('a','b'),'REF_NAME',0,'independent_required_empty',str(audit))
except tkinter.TclError as e:rejected='Required native scalar property empty' in str(e)
assert rejected
assert ident(m_path)==start,'Prepared manifest changed during audit'
for row in m['source_files']:check(row)
assert not (ROOT/'project/hardware/vivado/reports/m002_E006_R004_AT001_exact_candidate_comparison').exists()
attempt=OUT/'attempts/AT001_exact_candidate_comparison';assert not attempt.exists(),'Fresh R004 path required by unchanged exact planned-scaffold helper'
result={'recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'execution':'bounded source admission audit complete; native NOT_RUN','verdict':'source_preparation_accepted_for_bound_R004_readonly_execution','applicability':'exact manifest 29b84a33 / contracts + evidence correction + execution e7ed / original physopt DCP, fresh R004/AT001 only','review':'A007 independent; real lane/PID/input/resource admission still enforced by engineering runner; no new user gate','manifest':start,'verified_small_identity_rows':len(verified),'verified_small_identities':verified,'large_inputs_stat_and_bound_identity_only':stat_only,'python_AST_parsed':parsed,'unchanged_runner_helper_AST_names':unchanged,'supervision_and_post_integrity_tail_identical':True,'exact_C01_C02_targets':actual,'original_owner_regions_failure_targets_preserved':True,'pure_Tcl_replay':{'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'scope':'semantic/literal/mixed-load directional selector only; no native API'},'independent_property_fallback':{'mixed_optional_empty_preserved':True,'required_scalar_empty_rejected':True,'audit':ident(audit),'scope':'compressed-vector mock, not proof of native failing column'},'repairs_closed':['R004-F01: EGRESS external LOAD leaf/top scope; INGRESS internal LOAD; unknown/inout remain UNRESOLVED','R004-F02: P parent nine policy fields and actual Pblocks exported','R004-F03: actual vector body plus scalar rows exported','R004-N01: all primitive members on P-touched sites exported for shared/exclusive analysis'],'limits':['actual native full-cut completeness and property column failure not yet measured','full-cut TNS and formal signoff not measured; cap16 samples only','S/P contains actual nonconstant references and normalized DSP parents, not migration compatibility certification','No candidate_supported or combined candidate acceptance','E007 helper review is not a dependency'],'initial_review':ident(OUT/'independent_initial_source_review.json'),'producer':ident(__file__)}
with (OUT/'independent_source_admission_review.json').open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps(ident(OUT/'independent_source_admission_review.json')))
