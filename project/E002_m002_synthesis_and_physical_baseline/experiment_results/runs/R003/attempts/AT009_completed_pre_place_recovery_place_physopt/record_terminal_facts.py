"""Observe AT009's actual terminal state without rewriting any native artifact."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import shutil
import sys
import zipfile
sys.dont_write_bytecode=True
attempt=Path(__file__).resolve().parent
workspace=attempt.parents[6]
hardware=workspace/'project/hardware'
report=hardware/'vivado/reports/m002_E002_R003_AT009_completed_pre_place_recovery_place_physopt'
identity=lambda p:dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
status_path=attempt/'status.json'
status=json.loads(status_path.read_text())
tracked={}
for line in (attempt/'resources.jsonl').read_text().splitlines():
    for pid,row in json.loads(line)['processes'].items():
        pid=int(pid);ticks=row['start_ticks']
        if pid in tracked and tracked[pid]!=ticks:raise ValueError('ambiguous owned PID identity')
        tracked[pid]=ticks
supervisor_path=attempt/'supervisor_identity_observed.json'
supervisor=json.loads(supervisor_path.read_text())
if supervisor['pid']!=status['supervisor_pid']:raise ValueError('supervisor observation identity mismatch')
tracked[supervisor['pid']]=supervisor['start_ticks']
checks=[]
for pid,ticks in sorted(tracked.items()):
    try:
        raw=Path(f'/proc/{pid}/stat').read_text();fields=raw[raw.rindex(')')+2:].split()
        actual=int(fields[19]);state='reused_pid' if actual!=ticks else 'still_present'
    except (FileNotFoundError,ProcessLookupError):actual=None;state='not_present'
    if state=='still_present':raise ValueError(f'owned PID identity still present: {pid}')
    checks.append(dict(pid=pid,expected_start_ticks=ticks,observed_start_ticks=actual,state=state))
if status.get('owned_survivors') or not checks:raise ValueError('terminal owned process evidence incomplete')
log=(report/'vivado.log').read_text(errors='replace')
snapshot=attempt/'final_vivado_log_snapshot.txt'
if snapshot.exists():raise ValueError('preserve original terminal evidence')
shutil.copy2(report/'vivado.log',snapshot)
points={}
for point,native in (('place','place_design'),('physopt','phys_opt_design')):
    receipt=report/f'{point}_command_result.txt';checkpoint=report/f'{point}.dcp'
    if not receipt.exists() or not checkpoint.exists():continue
    values=dict(x.split('=',1) for x in receipt.read_text().splitlines())
    if values.get('native_tcl_code')!='0' or values.get('command')!=native or values.get('phase')!=point:continue
    if f"The checkpoint '{checkpoint}' has been generated" not in log:continue
    with zipfile.ZipFile(checkpoint) as archive:xml=archive.read('dcp.xml')
    points[point]=dict(checkpoint=identity(checkpoint),native_command=identity(receipt),
                       dcp_xml_sha256=hashlib.sha256(xml).hexdigest())
completed=[x for x in log.splitlines() if x.startswith('Phase ') and '| Checksum:' in x]
times=[x for x in log.splitlines() if x.startswith('Time (s):')]
value=dict(observed_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
    original_status=identity(status_path),original_status_preserved=True,
    original_started=identity(attempt/'started.json'),original_command=identity(attempt/'command.json'),
    execution_state='cost_stop' if status.get('stop_reason')=='stage_wall_timeout' else 'completed' if status['exit_code']==0 else 'failed',
    managed_exit_code=status['exit_code'],native_exit_code=status['native_exit_code'],stop_reason=status['stop_reason'],
    started_utc=status['started_utc'],ended_utc=status['ended_utc'],
    deadline_utc='2026-10-15T11:41:02.527929+00:00',owned_before_reap=status.get('owned_before_reap'),
    supervisor_identity_observation=identity(supervisor_path),
    owned_survivors=status['owned_survivors'],owned_pid_checks=checks,
    original_resource_samples=identity(attempt/'resources.jsonl'),max_tree_rss_bytes=status['max_tree_rss_bytes'],
    max_tree_rss_GiB=status['max_tree_rss_bytes']/2**30,
    last_completed_native_phase=completed[-1] if completed else None,last_native_time_line=times[-1] if times else None,
    final_native_log=identity(report/'vivado.log'),post_termination_log_snapshot=identity(snapshot),
    implementation_run_log_exists=(report/'implementation_run.log').exists(),
    launcher_status_exists=(report/'launcher_status.txt').exists(),
    place_command_receipt_exists=(report/'place_command_result.txt').exists(),
    physopt_command_receipt_exists=(report/'physopt_command_result.txt').exists(),
    placed_checkpoint_exists=(report/'place.dcp').exists(),physopt_checkpoint_exists=(report/'physopt.dcp').exists(),
    closed_physical_points=points,
    completed_pre_place_restore=identity(report/'pre_place_evidence.json'),
    pre_place_cost=identity(attempt/'pre_place_restored_facts.json'),cost_time_anchors=identity(attempt/'cost_time_anchors.json'),
    prior_debug_checkpoint=json.loads((report/'recovery_parent.json').read_text())['checkpoint'],
    original_warning_facts=[identity(attempt/name) for name in ('place_30_1229_warning_facts.json',
        'place_30_1995_warning_facts.json','post_place_bufg_opt_intermediate_facts.json')],
    route_parent_eligible=bool(status['exit_code']==0 and 'physopt' in points and (report/'diagnostic_evidence.json').exists()),
    partial_placement_memory_progress='not a recoverable checkpoint; lost after process termination',
    next_scope='only qualify closed physical point and missing stages' if points else
        'no new physical recovery point; stop placement retries under the single-restart boundary',
    native_artifact_scope='no original implementation_run.log/launcher success or physical receipt is fabricated',
    formal_reset_cdc_safety='OPEN',physical_signoff=False)
(attempt/'terminal_facts.json').write_text(json.dumps(value,indent=2)+'\n')
print(json.dumps(value,indent=2))
