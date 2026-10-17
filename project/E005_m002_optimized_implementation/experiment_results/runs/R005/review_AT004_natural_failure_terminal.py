"""Read-only bounded terminal audit; writes independent evidence only to R005."""
from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
import re

ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
OUT=Path(__file__).parent
REPORT=ROOT/'project/hardware/vivado/reports/m002_E005_R004_AT004_default_route'
AT=ROOT/'project/E005_m002_optimized_implementation/experiment_results/runs/R004/attempts/AT004_default_route'
checks=[]

def ident(path,expected=None):
    assert path.suffix!='.dcp', 'No large checkpoint reads in A007 audit'
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024*1024),b''): digest.update(chunk)
    row={'path':str(path.relative_to(ROOT)),'bytes':path.stat().st_size,'sha256':digest.hexdigest()}
    if expected:
        row['matched']=row['bytes']==expected['bytes'] and row['sha256']==expected['sha256']
        assert row['matched'],row
    checks.append(row)
    return row

def small_json(path):
    assert path.stat().st_size<300000
    ident(path)
    return json.loads(path.read_text())

status=small_json(AT/'status.json')
assert status['execution_state']=='completed' and status['native_exit_code']==status['exit_code']==1
assert status['stop_reason'] is None and not status['owned_before_reap'] and not status['owned_survivors']
artifacts=small_json(REPORT/'failed_route_artifacts.json')
assert artifacts['disposition']=='diagnostic_failed_route' and artifacts['eligible_as_successful_parent'] is False
launch=small_json(REPORT/'command.json')
assert artifacts['synthesis']==launch['synthesis']
assert artifacts['parent']['checkpoint']['path']==launch['environment']['HAP_RECOVERY_CHECKPOINT']
assert str(Path(artifacts['parent']['evidence']['path']).parent)==launch['environment']['HAP_RECOVERY_PARENT_REPORT']
launch_review=json.loads((OUT/'AT004_actual_route_launch_parent_review_evidence.json').read_text())
assert artifacts['parent']['checkpoint']==launch_review['parent']['checkpoint']
assert artifacts['parent']['evidence']==launch_review['parent']['diagnostic']
ident(Path(artifacts['stage_inputs']['path']),artifacts['stage_inputs'])
artifact_checks=[]
for item in artifacts['artifacts']:
    path=Path(item['path'])
    if path.suffix=='.dcp':
        st=path.stat()
        row={'path':item['path'],'actual_stat_bytes':st.st_size,'expected_identity':item,
             'stat_size_matches':st.st_size==item['bytes'],'mtime_ns':st.st_mtime_ns,
             'verification':'A007 stat and native receipt plus A006 hash binding; no checkpoint binary read'}
        assert row['stat_size_matches']
    else: row=ident(path,item)
    artifact_checks.append(row)
saved=small_json(AT/'failed_checkpoint_saved_observation.json')

native=REPORT/'vivado.log'
native_id=ident(native)
ident(REPORT/'implementation_run.log',native_id)
raw=native.read_bytes()
snapshot=OUT/'AT004_natural_terminal_native_log.txt'
with snapshot.open('xb') as handle:handle.write(raw)
assert raw.startswith((OUT/'AT004_phase9_failure_native_log_observed_prefix.txt').read_bytes())
lines=raw.decode().splitlines()
def rows_if(condition):
    return [{'native_line':i+1,'raw':line} for i,line in enumerate(lines) if condition(line)]
selected=rows_if(lambda s:any(v in s for v in ('[Route 35-2]', '[Route 35-162]',
    'Total Elapsed time in route_design', 'route_design: Time', 'Running DRC after route_design',
    'DRC finished with', 'route_failed.dcp\' has been generated', 'write_checkpoint: Time',
    'report_route_status: Time','report_timing_summary: Time','report_design_analysis: Time',
    'report_drc: Time', '[Common 17-39]', 'Exiting Vivado')))
original=(REPORT/'route_failed_original_error.tcllist').read_text()
expected_error="ERROR: [Common 17-39] 'route_design' failed due to earlier errors."
assert original.startswith('code 1 result {'+expected_error+'\n}')
assert 'options {-code 1 -level 0 -errorstack ' in original
assert '-errorcode NONE -errorinfo {'+expected_error in original
assert 'command {route_design -directive Default}' in original
original_epoch=int(re.search(r' epoch (\d+) disposition diagnostic_failed_route',original)[1])
error_line=next(i for i,line in enumerate(lines) if line==expected_error)
last_report_line=next(i for i,line in enumerate(lines) if line.startswith('report_drc: Time'))
assert error_line>last_report_line
assert any('m002_route_with_failure_capture $command' in line for line in lines[error_line:])
assert any('m002_command route {route_design -directive Default}' in line for line in lines[error_line:])
assert 'Exiting Vivado at Fri Oct 16 21:56:20 2026' in lines[-1]

receipt_path=REPORT/'route_command_result.txt'
ident(receipt_path)
receipt=dict(line.split('=',1) for line in receipt_path.read_text().splitlines())
assert receipt['phase']=='route' and receipt['command']=='route_design -directive Default' and receipt['native_tcl_code']=='1'
start,end=int(receipt['started_epoch']),int(receipt['ended_epoch'])
captures=list(csv.DictReader(io.StringIO((REPORT/'route_failed_capture_receipts.tsv').read_text()),delimiter='\t'))
assert [r['label'] for r in captures]==['checkpoint','route_status','timing','congestion','drc']
for index,row in enumerate(captures):
    assert row['code']=='0'
    row['duration_seconds']=int(row['ended_epoch'])-int(row['started_epoch'])
    if index:assert row['started_epoch']==captures[index-1]['ended_epoch']
assert int(captures[0]['started_epoch'])==original_epoch and int(captures[-1]['ended_epoch'])==end

stage_sources=REPORT/'stage_sources'
static_checks=[]
for name,needles in {
    'm002_route_failure_capture.tcl':['return -options $options $result','WRONLY CREAT EXCL'],
    'm002_resume_physical.tcl':['if {$rc} {return -options $options $result}', 'm002_post route'],
    'run_m002_physical_stage.py':['eligible_as_successful_parent=False','require(native == 0,'],
}.items():
    archive=stage_sources/name
    aid=ident(archive)
    live=ROOT/'project/hardware/vivado/scripts'/name
    lid=ident(live)
    assert aid['sha256']==lid['sha256']
    source=archive.read_text()
    assert all(needle in source for needle in needles)
    static_checks.append({'archive':aid,'live':lid,'required_guards':needles})
launcher=(REPORT/'launcher_status.txt').read_text()
ident(REPORT/'launcher_status.txt');ident(REPORT/'evidence_error.txt')
assert 'exit_code=1\nnative_exit_code=1\n' in launcher
assert (REPORT/'evidence_error.txt').read_text()=='ValueError: native physical controller exited 1\n'
success_artifact_names=['route.dcp','route_result.txt','diagnostic_evidence.json','implementation_checkpoint.sha256',
    'route_status_route.rpt','timing_route.rpt','utilization_route.rpt','drc_route.rpt',
    'fanout_reset_integrity_route.json','reset_structure_route.json','optimized_boundaries_route.tsv']
success_absence={name:not (REPORT/name).exists() for name in success_artifact_names}
assert all(success_absence.values())

route_status=(REPORT/'route_failed_status.rpt').read_text()
counts={}
for line in route_status.splitlines():
    match=re.search(r'# of (.*?)\.+\s*:\s*(\d+)\s*:',line)
    if match: counts[match[1]]=int(match[2])
assert counts['routable nets']==2031772
assert counts['fully routed nets']==1273309
assert counts['nets with routing errors']==counts['nets with resource conflicts']==758463
assert counts['fully routed nets']+counts['nets with routing errors']==counts['routable nets']
counts['unrouted_explicit_in_this_report']=None
counts['partially_routed_explicit_in_this_report']=None
counts['qualification']='Omitted categories are not inferred zero; earlier Phase8 counters retained separately.'

with (REPORT/'route_failed_timing.rpt').open() as handle:
    timing_prefix=[next(handle).rstrip('\n') for _ in range(148)]
timing_heading=next(i for i,line in enumerate(timing_prefix) if 'WNS(ns)' in line)
timing_values=timing_prefix[timing_heading+2].split()
assert len(timing_values)==12
names=['wns_ns','tns_ns','setup_failing_endpoints','setup_total_endpoints','whs_ns','ths_ns',
       'hold_failing_endpoints','hold_total_endpoints','wpws_ns','tpws_ns','pw_failing_endpoints','pw_total_endpoints']
timing_metrics={name:float(value) if '_ns' in name else int(value) for name,value in zip(names,timing_values)}
timing={'metrics':timing_metrics,'metric_line':timing_heading+3,'raw_metric_line':timing_prefix[timing_heading+2],
    'scope':'failed illegal routing diagnostic only; header Routed does not establish legality or formal signoff',
    'check_timing_rows':[{'line':i+1,'raw':line} for i,line in enumerate(timing_prefix) if re.match(r'\d+\. checking ',line)]}

with (REPORT/'route_failed_drc.rpt').open() as handle:
    drc_prefix=[next(handle).rstrip('\n') for _ in range(46)]
drc_summary=[]
for i,line in enumerate(drc_prefix):
    cols=[v.strip() for v in line.split('|')[1:-1]]
    if len(cols)==4 and re.match(r'[A-Z]+-\d+',cols[0]):
        drc_summary.append({'line':i+1,'rule':cols[0],'severity':cols[1],'description':cols[2],'checks':int(cols[3]),'raw':line})
assert sum(row['checks'] for row in drc_summary)==15918
assert drc_summary[0]['rule']=='RTSTAT-13' and drc_summary[0]['severity']=='Critical Warning'
drc={'summary':drc_summary,'checks_total':15918,'header_state':'Partially Routed',
     'routing_check_limit':drc_prefix[44], 'prefix_records':[{'line':i+1,'raw':line} for i,line in enumerate(drc_prefix)]}

congestion_lines=(REPORT/'route_failed_congestion.rpt').read_text().splitlines()
section=None; congestion_rows=[]
for i,line in enumerate(congestion_lines):
    if line=='1. Placer Final Level Congestion Reporting': section='Placer Final Level Congestion Reporting'
    elif line=='2. Router Initial Congestion': section='Router Initial Congestion'
    cols=[v.strip() for v in line.split('|')[1:-1]]
    if cols and cols[0] in ('North','South','East','West'):
        congestion_rows.append({'line':i+1,'section':section,'direction':cols[0],'type':cols[1],'level':int(cols[2]),'window':cols[3],'columns':cols,'raw':line})
congestion_sections={}
for section in ('Placer Final Level Congestion Reporting','Router Initial Congestion'):
    rows=[r for r in congestion_rows if r['section']==section]
    peaks={}
    for row in rows:
        key=row['direction']+'/'+row['type'];peaks[key]=max(peaks.get(key,-1),row['level'])
    congestion_sections[section]={'row_count':len(rows),'peaks':peaks}
assert congestion_sections['Placer Final Level Congestion Reporting']['row_count']==24
assert congestion_sections['Router Initial Congestion']['row_count']==21

identities=dict(status['tracked_identities'])
identities[str(status['supervisor_pid'])]=next(r['expected_start_ticks'] for r in launch_review['current_process_checks'] if r['pid']==status['supervisor_pid'])
process_checks=[]
for pid,expected in identities.items():
    path=Path('/proc')/pid/'stat'
    row={'pid':int(pid),'expected_start_ticks':expected}
    try:
        fields=path.read_text().split(') ',1)[1].split()
        row.update(actual_start_ticks=int(fields[19]),state=fields[0],same_identity=int(fields[19])==expected)
    except FileNotFoundError:row.update(actual_start_ticks=None,same_identity=False,state='ABSENT')
    process_checks.append(row)
assert not any(row['same_identity'] for row in process_checks)
lock_rows=[line for line in Path('/proc/locks').read_text().splitlines() if '103:02:169247080' in line]
assert not any(re.search(r'WRITE\s+'+pid+r'\s',line) for pid in identities for line in lock_rows)

times={
    'native_internal_total_elapsed_seconds':15510.3,
    'native_ending_routing_task_cumulative_elapsed_seconds':15525,
    'native_route_command_including_automatic_DRC_elapsed':'04:23:02',
    'native_route_command_including_automatic_DRC_seconds':15782,
    'native_capture_start_epoch':original_epoch,
    'wrapper_start_to_original_error_capture_epoch_seconds':original_epoch-start,
    'failure_capture_sum_seconds':sum(r['duration_seconds'] for r in captures),
    'wrapper_receipt_including_capture_seconds':end-start,
    'attempt_supervisor_elapsed_seconds':(datetime.fromisoformat(status['ended_utc'])-datetime.fromisoformat(status['started_utc'])).total_seconds(),
    'scope':'Different native/wrapper/attempt intervals; epoch rounding and wrapper overhead retained, not equated.'}

evidence={'reviewed_at':datetime.now(timezone.utc).isoformat(),'execution':'AT004 naturally exited failure; bounded terminal audit complete except new engineering freeze/resource closure facts followup',
    'verdict':'native legal routing failed, failed diagnostic capture completed; no successful route POST/parent or timing signoff',
    'applicability':'same AT004 accepted physopt parent and frozen source; E003 same-stage comparisons in section38',
    'review':'A007 independent bounded audit, not global user acceptance',
    'small_and_report_identity_checks':checks,'large_checkpoint_binding_stat_only':artifact_checks[0],
    'closed_native_log_snapshot':str(snapshot.relative_to(ROOT)),'prior_prefix_is_exact_prefix':True,
    'selected_native_records':selected,'original_error_raw':original,'original_error_rethrow_after_all_captures':True,
    'capture_receipts':captures,'wrapper_receipt':receipt,'times':times,
    'artifact_checks':artifact_checks,'parent_and_synthesis_match_launch_and_prior_review':True,
    'failed_checkpoint_saved_observation':saved,'frozen_source_guard_checks':static_checks,
    'success_post_artifacts_absent':success_absence,'parent_rejection':'native code1 and diagnostic_failed_route; eligible_as_successful_parent false; no successful route evidence',
    'route_status_counts':counts,'failed_diagnostic_timing':timing,'failed_diagnostic_DRC':drc,
    'failed_diagnostic_congestion_sections':congestion_sections,'failed_diagnostic_congestion_rows':congestion_rows,
    'failed_congestion_limit':'Contains only retained Placer Final Level and Router Initial tables; not final routed congestion. Use section38 Phase8 log for final router evidence.',
    'supervisor_status':status,'independent_process_identity_checks':process_checks,'actual_lane_lock_rows_at_review':lock_rows,
    'resource_scope':'Supervisor terminal observed extrema read; independent resource JSONL extrema and current144freeze pending engineering sealed facts.',
    'no_DCP_or_reset_graph_read_no_EDA_or_test_or_process_control':True}
target=OUT/'AT004_natural_failure_terminal_review_evidence.json'
with target.open('x') as handle:json.dump(evidence,handle,ensure_ascii=False,indent=2);handle.write('\n')
print(json.dumps({'evidence':str(target.relative_to(ROOT)),'hash_checks':len(checks),'times':times,
    'failed_timing':timing_metrics,'route_status':counts,'congestion_sections':congestion_sections,
    'process_identities_absent':len(process_checks),'lock_rows_at_review':lock_rows},ensure_ascii=False,indent=2))
