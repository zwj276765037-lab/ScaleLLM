#!/usr/bin/env python3
"""Capture actually qualified restored preplace and observed place invocation; no EDA."""
import argparse,csv,hashlib,json,os,shutil,sys
from pathlib import Path
from datetime import datetime,timezone
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
def ident(p):
 p=Path(p).resolve();a=p.stat();h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 z=p.stat();assert (a.st_size,a.st_mtime_ns)==(z.st_size,z.st_mtime_ns);return {'path':str(p),'bytes':z.st_size,'sha256':h.hexdigest()}
def kv(p):return dict(s.split('=',1) for s in p.read_text().splitlines() if '=' in s)
def main():
 os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
 p=argparse.ArgumentParser();p.add_argument('--attempt',required=True,type=Path);p.add_argument('--report',required=True,type=Path);a=p.parse_args();at=a.attempt.resolve();r=a.report.resolve()
 assert at.parent==ROOT/'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts'
 target=at/'pre_place_closed_stage_facts.json';producer=at/'capture_pre_place_producer.py';snapshot=at/'pre_place_and_place_invocation_log_snapshot.txt'
 assert not any(q.exists() for q in [target,producer,snapshot])
 started=json.loads((at/'started.json').read_text());inputs=json.loads((at/'input_bindings.json').read_text());assert ident(at/'input_bindings.json')==started['inputs'];assert ident(inputs['preparation_manifest']['path'])==inputs['preparation_manifest']
 manifest=json.loads(Path(inputs['preparation_manifest']['path']).read_text());assert all(ident(x['path'])==x for x in manifest['own_sources']+manifest['reused_sources']+manifest['CPU_checks']+manifest.get('documentation',[]))
 freeze=inputs['frozen_inputs']['freeze'];assert ident(freeze['path'])==freeze;production=json.loads(Path(freeze['path']).read_text())['files'];assert len(production)==144 and all(ident(x['path'])==x for x in production)
 pre=json.loads((r/'pre_place_evidence.json').read_text());cut=json.loads((r/'candidate_cut_summary_pre_place.json').read_text());tim=json.loads((r/'candidate_timing_validation_pre_place.json').read_text());member=json.loads((r/'candidate_membership_pre_place.json').read_text())
 assert pre['diagnostic_eligible'] is True and pre['physical_signoff'] is False
 assert cut['directed_boundary_complete'] and cut['candidate_leaf_coverage_complete'] and tim['complete_directional_query_sets']
 assert tim['native_query_count']==4 and tim['max_paths']==16 and tim['full_cut_TNS']=='NOT_MEASURED'
 policy=kv(r/'candidate_policy_preservation.txt');assert policy['verified']=='1' and policy['unknown_policy']==policy['excluded_macro_partners']=='0'
 assert (r/'candidate_policy_before.tcllist').read_bytes()==(r/'candidate_policy_after.tcllist').read_bytes()
 command=kv(r/'pre_place_restore_command_result.txt');guard=kv(r/'pre_place_restore_guard.txt');assert command['native_tcl_code']=='0' and guard==dict(completed='1',blackboxes='0',drc_blockers='0',clock_groups_verified='1')
 groups={}
 with (r/'candidate_scoped_timing_pre_place.tsv').open() as f:
  for row in csv.DictReader(f,delimiter='\t'):
   key=row['direction']+'_'+row['delay_type'];x=groups.setdefault(key,dict(returned_rows=0,query_load_pins=int(row['queried_boundary_pins']),min_slack_ns=None));x['returned_rows']+=1
   slack=float(row['SLACK']);x['min_slack_ns']=slack if x['min_slack_ns'] is None else min(slack,x['min_slack_ns'])
 assert set(groups)=={'INGRESS_max','INGRESS_min','EGRESS_max','EGRESS_min'} and all(x['returned_rows']==16 for x in groups.values())
 log=r/'vivado.log';size=log.stat().st_size
 with log.open('rb') as f:data=f.read(size)
 assert b'Command: place_design -directive SSI_SpreadSLLs' in data and b'Starting Placer Task' in data
 snapshot.write_bytes(data);shutil.copy2(Path(__file__),producer)
 names=['pre_place_evidence.json','candidate_membership_pre_place.json','candidate_policy_preservation.txt','candidate_policy_before.tcllist','candidate_policy_after.tcllist','candidate_existing_pblocks_before.tcllist','candidate_existing_pblocks_after.tcllist','candidate_pblock_readback.txt','candidate_effective_physical.xdc','candidate_cut_summary_pre_place.json','candidate_timing_validation_pre_place.json','candidate_scoped_timing_pre_place.tsv','candidate_timing_queries_pre_place.tcllist','candidate_scoped_timing_pre_place_coverage.txt','pre_place_restore_guard.txt','pre_place_restore_command_result.txt','check_timing_pre_place_restore.rpt','constraints_pre_place_restore.json','drc_pre_place_restore.rpt']
 value=dict(observed_utc=datetime.now(timezone.utc).isoformat(),stage='qualified_restored_pre_place_and_actual_place_invocation',pre_place_qualification_established=True,selected_candidate=inputs['attribution']['selected_candidate'],input_bindings=ident(at/'input_bindings.json'),preparation_manifest=inputs['preparation_manifest'],production_144_unchanged=True,
  members={k:member[k] for k in ['raw_selector_count','semantic_S_count','placeable_P_count']},policy_preservation=policy,policy_before_after_bytes_equal=True,pblock_readback=kv(r/'candidate_pblock_readback.txt'),
  directed_cut={k:cut[k] for k in ['coverage_version','directed_boundary_complete','candidate_leaf_coverage_complete','canonical_nets','actual_candidate_native_leaf_pins','retained_endpoint_rows','candidate_boundary_driver_load_pairs','unknown_top_or_unplaced_pair_positions']},
  actual_bounded_unplaced_timing=groups,full_cut_TNS='NOT_MEASURED',timing_limit='Pre-place unplaced estimates; not comparable to E006 physopt as improvement, not routed timing or signoff.',
  restored_pre_place_live_clock_coverage=pre['live_clock_coverage'],restored_measurements_scope=pre['inherited_measurements'],native_restore_guard=guard,native_restore_command=command,
  actual_place_command_observed=True,place_completion='PENDING_ACTUAL_CLOSED_COMMAND_POST_AND_LOCALITY',physopt_route_completion='NOT_ESTABLISHED',formal_signoff=False,formal_reset_CDC_IO='OPEN',artifacts=[ident(r/n) for n in names]+[ident(snapshot)],producer=ident(producer))
 with target.open('x') as f:f.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(ident(target)))
if __name__=='__main__':main()
