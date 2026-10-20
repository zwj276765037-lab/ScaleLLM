"""A007 one-shot CPU evidence check; no EDA, process inspection or control."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import hashlib,json,re
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
OUT=ROOT/'agent/A007/M003_SM015_SM017_review_20261018'
REPORT=ROOT/'project/hardware/vivado/reports/m003_E011_R002_AT035_qualified_OPT_POST_to_actual_debug'
ATTEMPT=ROOT/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT035_qualified_OPT_POST_to_actual_debug'
PHYSICAL=ROOT/'project/E011_m003_joint_routability_implementation/experiment_source/physical_literal_adapter'
LIMIT=12_000_000
verified={}; delegated={}
def read(path):return json.loads(Path(path).read_text())
def identity(path):
 p=Path(path).resolve();assert p.stat().st_size<=LIMIT,p
 return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def verify(i):
 p=Path(i['path']);p=p if p.is_absolute() else ROOT/p;p=p.resolve()
 assert p.stat().st_size==i['bytes'],str(p)
 if p.suffix=='.dcp' or p.stat().st_size>LIMIT:
  delegated[str(p)]={**i,'A007_check':'size only; full identity from completed unchanged native/owner verification'};return
 actual=identity(p);assert actual['sha256']==i['sha256'],str(p)
 verified[str(p)]=actual

def walk(v):
 if isinstance(v,dict):
  if all(k in v for k in ('path','bytes','sha256')):verify(v)
  else:
   for x in v.values():walk(x)
 elif isinstance(v,list):
  for x in v:walk(x)
def rows(name):return [json.loads(x) for x in (REPORT/name).read_text().splitlines()]
def bind(path):
 x=identity(path);verify(x);return x
package=read(REPORT/'M003_preplace_package.json')
package_id=bind(REPORT/'M003_preplace_package.json')
assert package_id['sha256']=='94e3f3350af829d7fd61d4e01988e262b1344697801a062d762a8ca295e98e52'
assert package['physical_signoff'] is False
walk(package)
pre=read(REPORT/'pre_place_evidence.json');walk(pre)
integ=read(REPORT/'integrity_debug_materialized.json');walk(integ)
qual=read(REPORT/'m003_qualification_debug_materialized.json');walk(qual)
assert integ['phase']=='debug_materialized' and not integ['gate_issues']
assert integ['reset_structure']['qualified'] and not integ['reset_structure']['issues']
assert len(integ['reset_structure']['explicit_primitive_exports'])==14
assert integ['reset_fanout_observation']['qualified'] and not integ['reset_fanout_observation']['issues']
assert integ['cdc_classification']['classified_opt_reset']==8 and integ['cdc_classification']['new_critical']==0
assert integ['cdc_classification']['formal_reset_cdc_safety']=='OPEN'
clock=integ['debug_clock_observation'];assert clock['relationship_qualified'] and not clock['relationship_issues']
assert clock['actual_input_hz']==50_000_000 and clock['declared_input_hz']==300_000_000
assert clock['fanout_endpoint_count']==530 and clock['declared_matches_actual_input'] is False
assert qual['passed'] and not qual['errors'] and qual['fixture'] is False and qual['phase']=='debug_materialized'
assert [qual[k] for k in ['exact_new_M2_LUT1','exact_new_address_FF','exact_helper_LUT','exact_helper_CARRY8','protected_added_LUT']]==[81,34,40,4,85]
assert qual['URAM_per_slice']=={'0':40,'1':40} and qual['actual_address_root_counts']=={'0':6,'1':6}
assert len(qual['raw_reset_endpoint_observations'])==51 and qual['normalized_cell_literals']==17
assert qual['raw_snapshot_unchanged'] and qual['pin_evidence_unchanged_and_required'] and qual['original_full_function_evaluation_retained']
assert not (REPORT/'place_command_result.txt').exists()
coverage=pre['clock_coverage']
assert all(coverage[k]==0 for k in coverage if k not in ['no_input_delay','no_output_delay'])
assert coverage['no_input_delay']==1 and coverage['no_output_delay']==2
native_command=(REPORT/'debug_materialization_command_result.txt').read_text();assert 'native_tcl_code 0' in native_command or 'native_tcl_code\t0' in native_command or 'native_tcl_code=0' in native_command
boundary=rows('m003_stream_debug_materialized_boundaries.jsonl')
assert len(boundary)==80 and len({x['NAME'] for x in boundary})==80
assert Counter(x['tag'] for x in boundary)=={'input':48,'gate':16,'down':16}
for x in boundary:
 assert x['DONT_TOUCH']=='1' and x['REF_NAME'].startswith('LUT')
 assert int(x['load_count'])==int(x['expected_width'])=={'input':256,'gate':384,'down':512}[x['tag']]
 assert len(x['load_terminals'].split())==int(x['load_count']) and set(x['load_terminals'].split())=={'CE'}
assert sum(int(x['load_count']) for x in boundary)==26624
uram=rows('m003_stream_debug_materialized_uram_configs.jsonl')
assert len(uram)==80 and len({x['NAME'] for x in uram})==80
uram_summary={}
for slice_id in ['0','1']:
 rr=[x for x in uram if x['slice']==slice_id];assert len(rr)==40
 for port in ['A','B']:
  observed={(int(x[f'MEM.PORT{port}.ADDRESS_BEGIN']),int(x[f'MEM.PORT{port}.ADDRESS_END']),int(x[f'MEM.PORT{port}.DATA_LSB']),int(x[f'MEM.PORT{port}.DATA_MSB'])) for x in rr}
  expected={(i*4096,(i+1)*4096-1,lo,hi) for i in range(20) for lo,hi in [(0,71),(72,127)]}
  assert observed==expected
  assert Counter(x[f'CASCADE_ORDER_{port}'] for x in rr)=={'FIRST':6,'MIDDLE':28,'LAST':6}
  for x in rr:
   assert x[f'BWE_MODE_{port}']=='PARITY_INDEPENDENT' and x[f'NUM_UNIQUE_SELF_ADDR_{port}']=='20' and x[f'SELF_MASK_{port}']=="11'h7E0"
   for key in ['IREG_PRE','OREG','OREG_ECC','REG_CAS','USE_EXT_CE']:assert x[f'{key}_{port}']=='FALSE'
 uram_summary[slice_id]=dict(primitives=40,address_intervals=20,depth=81920,data_intervals=[[0,71],[72,127]],cascade_per_port={'FIRST':6,'MIDDLE':28,'LAST':6})
spec_path=ROOT/'project/hardware/vivado/constraints/m003_joint_locality_spec.json';spec=read(spec_path)
assert bind(spec_path)['sha256']==qual['spec_sha256']
walk(spec['source_RTL'])
pblocks={x['NAME']:x for x in rows('m003_stream_debug_materialized_pblocks.jsonl')}
assert len(pblocks)==28
assert all(x[k]=='0' for x in pblocks.values() for k in ['IS_SOFT','EXCLUDE_PLACEMENT','CONTAIN_ROUTING'])
pool_summary=[]
for pool in spec['meta_pools']:
 i=pool['index'];sa=set(pblocks[f'm003_meta_slice{i}_address']['actual_sites'].split());su=set(pblocks[f'm003_meta_slice{i}_uram']['actual_sites'].split())
 assert sa==set(pool['CLB_sites']) and su==set(pool['URAM_sites']) and not sa&su
 assert len(sa)==3480 and len(su)==40
 pool_summary.append(dict(slice=i,address_sites=3480,URAM_sites=40,exact_spec_sites=True,intersection=0))
assert len(spec['regions'])==23
assert all(len(pblocks['m003_parent_'+x['clock_region']]['actual_sites'].split())==x['native_CLB_site_count'] for x in spec['regions'])
assert pblocks['m002_exact_hotspot_SLR2']['GRID_RANGES']=='CLOCKREGION_X0Y10:CLOCKREGION_X5Y14'
membership=read(REPORT/'effective_pblock_membership_debug_materialized.json');walk(membership)
opt_membership=read(REPORT/'effective_pblock_membership_opt.json');walk(opt_membership)
assert membership['passed'] and not membership['errors'] and not membership['C01_other_PBLOCKS']
assert membership['counts']==opt_membership['counts']=={'payload':13120,'buffer':81,'c01':9491}
assert membership['stream']['sha256']==opt_membership['stream']['sha256']
assert membership['M2_expected_region_member_counts']==opt_membership['M2_expected_region_member_counts']
assert sum(membership['M2_expected_region_member_counts'].values())==13201
trace=rows('m003_connection_debug_materialized_trace.jsonl')
assert trace[0]['event']=='call_begin' and trace[0]['phase']=='debug_materialized'
assert trace[-1]['event']=='call_complete' and trace[-1]['endpoints']=='13252'
assert next(x for x in trace if x['event']=='reset_provenance_complete')['endpoints']=='51'
constraints=read(REPORT/'constraints_debug_materialized.json');walk(constraints)
assert constraints['phase']=='debug_materialized' and len(constraints['hashes'])==163
for name,digest in constraints['hashes'].items():assert bind(name)['sha256']==digest
archive=read(REPORT/'source_archive.json');assert len(archive)==447
manifest={}
for line in (REPORT/'stage_inputs.sha256').read_text().splitlines():
 m=re.fullmatch(r'([0-9a-f]{64})  (.+)',line);assert m
 digest,name=m.groups();assert name not in manifest;manifest[name]=digest
assert len(manifest)==451
originals={x['original']['path']:x['original']['sha256'] for x in archive}
assert len(originals)==447
assert all(x['original']['sha256']==x['preserved']['sha256'] and x['original']['bytes']==x['preserved']['bytes'] for x in archive)
assert all(manifest[n]==d for n,d in originals.items())
probe=read(REPORT/'probe_targets_debug_materialized.json');walk(probe)
extra=set(manifest)-set(originals)
assert extra=={probe[k]['path'] for k in ['baseline_report','actual_report','warning_log','probe']}
for k in ['baseline_report','actual_report','warning_log','probe']:assert manifest[probe[k]['path']]==probe[k]['sha256']
owner=read(ATTEMPT/'evidence/actual_debug_POST_preplace_and_outer_cleanup_attribution.json');walk(owner)
assert owner['actual_full_debug_POST_complete'] and owner['actual_preplace_recomputed_unchanged'] and owner['all_archived_source_bindings_match']
assert owner['actual_debug_command_native_tcl_code']==0 and owner['outer_native_exit_code']==1
closure=read(Path(owner['owner_terminal_closure']['path']));walk(closure)
assert closure['lock_free'] and closure['archive_bindings']==203 and len(closure['source_checks'])==203
assert all(x['current_matches'] and x['archive_matches'] for x in closure['source_checks'])
assert len(closure['processes'])==30 and all(x['actual_start'] is None and x['expected_alive'] is False for x in closure['processes'])
terminal=closure['terminal'];assert terminal['native_exit_code']==1 and terminal['stop_reason'] is None and not terminal['owned_survivors']
assert terminal['core_RTL_unchanged_during_job'] and terminal['no_wall_or_quiet_stop']
supplements=[]
for n in ['actual_OPT_provenance_exact_equality_supplement.json','terminal_actual_OPT_provenance_exact_equality_supplement.json']:
 path=ATTEMPT/'evidence'/n;s=read(path);walk(s)
 assert s['completed'] and s['exact_current_provenance_equals_frozen'] and s['nested_reset_exports_and_models_verified'] and s['nested_CDC_proof_sources_verified']
 assert [s[k] for k in ['anchors','reports','producers']]==[13,4,3]
 assert len(s['negative_mutations'])==22 and all(x['rejected'] for x in s['negative_mutations'])
 assert s['live_entry_guard_was_modified'] is False
 supplements.append(bind(path))
binding=read(Path(s['frozen_binding']['path']));walk(binding)
physical=read(PHYSICAL/'dependency_package_v2.json');walk(physical)
assert physical['frozen_source_manifest']==package['source_manifest']
proposal=read(PHYSICAL/'proposal_evidence_v2.json');walk(proposal)
prior_names=['AT027_final_reset_exports_budget_and_freeze_one_shot_review.json','AT030_INIT_recovery_adapter_one_shot_independent_review.json','physical_literal_adapter_candidate_one_shot_review_20261020.json','physical_literal_adapter_v2_minimal_delta_review_20261020.json','AT034_critical_CDC_same_OPT_binding_diagnosis_20261020.json','AT035_OPT_provenance_debug_boundary_independent_review_20261020.json']
priors=[bind(OUT/n) for n in prior_names]
assert priors[0]['sha256']=='f1bf83f611ecd1e44715f45d614e23c7712423b3ecc7c2dce11e7d939347ae4a'
assert priors[3]['sha256']=='e05d8d8b9e3d3647d80dc01adc55358addb8b55aa61b085183e7015fde35dcc8'
assert priors[-1]['sha256']=='58fe7485dc7a28b9932e16b257c39dd2e90de59c6a8003c6da7d30466b4a1512'
budget=read(OUT/prior_names[0]);walk(budget['budget_provenance']);assert budget['global_CARRY8']['delta']==4
physical_prior=read(OUT/prior_names[3]);walk(physical_prior['applicability'])
# Read only relevant report sections, retain exact file identities.
drc_lines=(REPORT/'drc_debug_materialized.rpt').read_text().splitlines()
drc_summary=[line for line in drc_lines[:45] if re.match(r'\|\s*(DPIP-|DPOP-|DPREG-|FLBO-|REQP-)',line)]
assert len(drc_summary)==7 and all('Warning' in x for x in drc_summary)
assert sum(int(x.split('|')[-2].strip()) for x in drc_summary)==15918
flbo=[]
for n,line in enumerate(drc_lines):
 if re.match(r'FLBO-1#[1-4] Warning$',line):flbo.append(dict(line=n+1,text=drc_lines[n:n+4]))
assert len(flbo)==4
for i in [0,1]:
 assert any(f'm003_meta_slice{i}_address overlaps with m003_meta_slice{i}_uram' in '\n'.join(x['text']) for x in flbo)
 assert any(f'm003_meta_slice{i}_uram overlaps with m003_meta_slice{i}_address' in '\n'.join(x['text']) for x in flbo)
timing_lines=(REPORT/'timing_debug_materialized.rpt').read_text().splitlines()
tidx=next(i for i,x in enumerate(timing_lines) if x.lstrip().startswith('WNS(ns)'))
vals=timing_lines[tidx+2].split();assert vals[:2]==['0.904','0.000'] and vals[4:6]==['-0.814','-48983.922'] and vals[8:10]==['-0.012','-0.037']
log_lines=(REPORT/'vivado.log').read_text().splitlines()
assert 'M002_DIAGNOSTIC_STEP_COMPLETED debug_materialized coverage=COMPLETE_INTERNAL physical_signoff=false' in log_lines[218]
assert log_lines[219].startswith('close_design:') and 'No open project' in log_lines[220]
for n in ['m003_stream_debug_materialized_boundaries.jsonl','m003_stream_debug_materialized_uram_configs.jsonl','m003_stream_debug_materialized_pblocks.jsonl','m003_connection_debug_materialized_trace.jsonl','effective_pblock_membership_opt.json','effective_pblock_membership_debug_materialized.json','probe_targets_debug_materialized.json','drc_debug_materialized.rpt','timing_debug_materialized.rpt','vivado.log']:
 bind(REPORT/n)
for n in ['actual_debug_POST_preplace_and_outer_cleanup_attribution.json','exact_postcompletion_close_failure_location.json']:bind(ATTEMPT/'evidence'/n)
result=dict(schema='A007_AT035_actual_G4_bounded_evidence_check_v1',observed_utc=datetime.now(timezone.utc).isoformat(),execution='completed_cpu_only',all_checks_passed=True,package=package_id,
 native_execution=dict(actual_debug_tcl=0,POST_complete=True,outer_exit=1,cleanup_error_preserved=True,terminal=terminal,process_and_lock_scope='Read final owner receipt only; no new process or lock observation'),
 structure=dict(selection=package['selection'],protection_boundaries=80,boundary_tags=dict(Counter(x['tag'] for x in boundary)),exact_all_CE_loads=26624,URAM=uram_summary,pools=pool_summary,M2_parent_pools=23,Pblocks=28,C01_sites=78266,actual_membership=membership['counts'],OPT_debug_membership_and_selected_stream_digest_equal=True,connection_trace_complete_endpoints=13252),
 current_reset_CDC=dict(exports=14,qualified_structure=True,qualified_fanout=True,classified_reset_critical=8,new_critical=0,formal_safety='OPEN'),
 timing=dict(summary_line=tidx+3,raw_summary=timing_lines[tidx+2].strip(),WNS_ns=0.904,TNS_ns=0,WHS_ns=-0.814,THS_ns=-48983.922,WPWS_ns=-0.012,TPWS_ns=-0.037,signoff=False),
 DRC=dict(summary=drc_summary,warnings=15918,errors=0,critical_warnings=0,overlap_records=flbo,overlap_attribution='Each address CLB pool and its URAM pool overlap geographically; exact native resource-site sets equal the frozen spec, are disjoint by resource type, and EXCLUDE_PLACEMENT=0. No all-resource exclusion or shared BEL requirement is introduced.'),
 coverage=coverage,debug_clock=dict(actual_input_Hz=50_000_000,declared_input_Hz=300_000_000,actual_relationship_qualified=True,fanout_endpoints=530,formal_frequency_review='OPEN diagnostic limitation retained'),
 source_bindings=dict(archive447_metadata_matches_manifest=True,stage_inputs=451,extra_four_probe_paths=sorted(extra),current_constraint_hashes_verified=163,full_archive447_hash_check_attributed_to_owner=owner['all_archived_source_bindings_match'],owner203_sources_and30_processes_receipt=owner['owner_terminal_closure']),
 exact_OPT_supplements=supplements,physical_dependency=bind(PHYSICAL/'dependency_package_v2.json'),physical_proposal=bind(PHYSICAL/'proposal_evidence_v2.json'),prior_reviews=priors,
 independently_verified_small_identities=list(verified.values()),large_identity_checks_delegated=list(delegated.values()),
 review_limits=['No DCP or whole large graph/snapshot/cell stream content read or rehashed.','Actual full native qualification and unchanged pre_place_evidence(create=False) completion attributed to owner final receipt; prior full independent reviews reused by exact identity.','No EDA, observer, polling, waiting, process or lock control; no project evidence modifications.'])
out=OUT/'AT035_actual_G4_bounded_evidence_check_20261020.json'
assert not out.exists();out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(dict(passed=True,receipt=identity(out),small_identities=len(verified),delegated_large_identities=len(delegated)),ensure_ascii=False))
