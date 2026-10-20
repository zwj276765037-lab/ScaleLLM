"""A007 bounded terminal/source-boundary review. No native tools or mutations."""
from pathlib import Path
import datetime,hashlib,json
ROOT=Path(__file__).resolve().parents[3];OWN=Path(__file__).resolve().parent
ATT=ROOT/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT024_grouped_stream_postreport_recovery';JOB=ATT/'evidence/jobs/native_postreport'
REPORT=ROOT/'project/hardware/vivado/reports/m003_E011_R002_AT024_grouped_stream_postreport_recovery'
def ident(p):
 b=p.read_bytes();return {'path':str(p.relative_to(ROOT)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
statusp=JOB/'status.json';status=json.loads(statusp.read_text());assert status['native_exit_code']==1 and status['stop_reason'] is None and status['owned_survivors']=={}
identities={int(k):v for k,v in status['tracked_PID_start_identities'].items()};identities.update({157933:6185410,158634:6204663});processes=[]
for pid,start in identities.items():
 p=Path('/proc')/str(pid)/'stat'
 if p.exists():
  fs=p.read_text().rsplit(')',1)[1].split();row={'pid':pid,'expected_start':start,'actual_start':int(fs[19]),'state':fs[0]};assert int(fs[19])!=start
 else:row={'pid':pid,'expected_start':start,'absent':True}
 processes.append(row)
locks=[l for l in Path('/proc/locks').read_text().splitlines() if '169247080' in l];assert not locks
archive=json.loads((JOB/'source_archive.json').read_text())['bindings'];byorig={r['original']['path']:r for r in archive}
mp=ROOT/'project/hardware/vivado/constraints/m003_entry_manifest.json';archived_manifest=Path(byorig[str(mp)]['preserved']['path']);assert ident(archived_manifest)['sha256']=='16f9523c2e4968a34abdce8d8e5c126476f206ce8c0f93ceec146799c0d9cf75'
manifest=json.loads(archived_manifest.read_text());source_checks=[]
for row in manifest['sources']:
 expected=byorig[row['path']];preserved=Path(expected['preserved']['path']);assert ident(preserved)['sha256']==row['sha256']
 actual=Path(row['path']);current=ident(actual);source_checks.append({'path':row['path'],'frozen_sha256':row['sha256'],'preserved_verified':True,'current_sha256':current['sha256'],'current_equals_frozen':current['sha256']==row['sha256']})
assert len(source_checks)==48
errorp=REPORT/'m003_snapshot_synth_158026_error_info.txt';error=errorp.read_text();assert 'selected metadata boundary S count/duplicate mismatch: 0, expected 1' in error and '${meta_scope}/$terminal' in error
receipts=[]
for n in (1,2):
 p=REPORT/f'm003_apply_success_158026_{n}.json';r=json.loads(p.read_text())
 # Explicit checks avoid inference from existence alone.
 assert r['attempt']==str(n) and r['success']=='true' and r['pid']=='158026' and r['source_manifest_sha256']==ident(archived_manifest)['sha256']
 receipts.append({'identity':ident(p),'native':r})
helperp=REPORT/'m003_stream_synth_helper_pins.jsonl.partial';assert helperp.stat().st_size<524288
selected=[]
with helperp.open() as f:
 for line in f:
  row=json.loads(line)
  if row.get('cell','').rsplit('/',1)[-1] in ('u_local_ce','u_local_increment'):selected.append(row)
assert len(selected)==10
selectionp=OWN/'AT024_actual_partial_local_control_10_rows.json'
with selectionp.open('x') as f:json.dump({'source':ident(helperp),'rows':selected},f,ensure_ascii=False,indent=2);f.write('\n')
for i in ('0','1'):
 rows=[r for r in selected if r['slice']==i]
 assert len(rows)==5
 for r in rows:
  if (r['cell'].endswith('u_local_ce') and r['pin']=='I0') or (r['cell'].endswith('u_local_increment') and r['pin']=='I1'):
   assert '/u_attention/engine_soft_clear' in r['nets'] and r['drivers'].endswith('/maintenance_soft_clear_pulse_r_reg/Q')
  elif r['cell'].endswith('u_local_ce') and r['pin']=='I1':assert '/u_attention/input_load_start' in r['nets']
  else:assert '/u_meta/rsp_fire' in r['nets']
partial_stats=[{'name':p.name,'bytes':p.stat().st_size,'stat_only':True} for p in sorted(REPORT.glob('*.partial'))]
assert not (REPORT/'m003_native_synth.json').exists() and not (REPORT/'m003_qualification_synth.json').exists() and not (REPORT/'m003_same_stage_budget.json').exists()
events={n:json.loads((OWN/f'AT024_dependency_event_{n:03d}.json').read_text())['utc'] for n in (4,5)}
record={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'execution':'completed_terminal_and_bounded_boundary_evidence_review','verdict':'natural_native_failure_at_selected_metadata_boundary_S_selector; not_design_or_method_refutation','review':'terminal_accepted_repair_pending','applicability':'AT024 frozen manifest16f/checks604f and preserved partial output only','status':status,'evidence':{'status':ident(statusp),'native_error_stack':ident(errorp),'frozen_manifest':ident(archived_manifest),'actual_partial_control_rows':ident(selectionp),'partial_connection_trace':ident(REPORT/'m003_connection_synth_trace.jsonl')},'process_identity_checks':processes,'original_lock_absent':True,'frozen48_preserved_small_sources_verified':source_checks,'two_actual_apply_receipts':receipts,'partial_output_stats_only':partial_stats,'URAM_property_files_stat_count':len(list(REPORT.glob('m003_uram_properties_synth_*.tsv'))),'full_snapshot_qualification_budget_absent':True,'boundary_facts':['Failed selector asks meta_scope/addr_system_clear and returns zero','RTL u_meta input addr_system_clear exists and connects core system_clear=engine_soft_clear; datapath_clear also includes abort and is semantically different','Actual helper S inputs share engine_soft_clear aliases and one maintenance_soft_clear_pulse_r_reg/Q source','Actual helper L inputs share input_load_start aliases; actual R inputs share u_meta/rsp_fire','RTL u_meta write port is wr_valid; meta_wr_valid is a wire in the parent core; later unexecuted selector requires review'],'repair_constraints':['Retain independent source anchors; do not derive reference S/L/R from the same checked sink then self-validate','Review all seven control-source selectors and polarity/direction, not only first S','Retain all80 protected boundaries and exact fullgraph/clock/source validation','Ordinary source repair/retry authorized without extra signoff; no EDA/production ownership by A007'],'monitoring_gap':{'observer_error_event_utc':events[4],'observer_terminal_event_utc':events[5],'active_review_resumed_after_Root_followup':'2026-10-19T05:06Z reported by Root','old_observer_now_exited':True,'own_session98274_exit_code':0,'cause_reported_by_Root':'A007 capacity error; owner turn completed; automatic continuation missed','continuous_active_notification_not_claimed':True},'G4':False}
out=OWN/'AT024_terminal_boundary_selector_independent_review.json'
with out.open('x') as f:json.dump(record,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({'receipt':ident(out),'partial_rows':ident(selectionp),'current_runtime_differences':[r['path'] for r in source_checks if not r['current_equals_frozen']],'status_ended':status['ended_utc'],'verified_closed_identities':len(processes)}))
