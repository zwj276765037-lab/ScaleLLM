#!/usr/bin/env python3
"""Read-only, bounded progress view for A006's recorded E006 attempt."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[2]
active = json.loads((root / 'agent/A006/resume_E006.json').read_text())['active']
attempt = root / active['attempt']
report = root / active['report']
now = datetime.now(timezone.utc)
view = {'stage': active['stage'], 'attempt': active['attempt'], 'observed_now_utc':now.isoformat()}
supervisor_pid = active.get('supervisor_pid')
if supervisor_pid:
    try:
        fields = Path(f'/proc/{supervisor_pid}/stat').read_text().rsplit(')',1)[1].split()
        view['supervisor_live_identity'] = dict(pid=supervisor_pid,state=fields[0],
            start_ticks=int(fields[19]),expected_start_ticks=active.get('supervisor_start_ticks'),
            start_matches=int(fields[19])==active.get('supervisor_start_ticks'))
    except FileNotFoundError:
        view['supervisor_live_identity'] = dict(pid=supervisor_pid,present=False)
resources = attempt / 'resources.jsonl'
handovers = sorted(attempt.glob('supervision_handover_*/resources.jsonl'))
if handovers:
    resources = handovers[-1]
view['resource_source'] = str(resources.relative_to(root))
if resources.exists():
    with resources.open('rb') as stream:
        stream.seek(0, 2)
        length = stream.tell()
        stream.seek(max(0, length - 131072))
        samples = stream.read().splitlines()
        row = json.loads(samples[-1])
        previous = json.loads(samples[-2]) if len(samples) > 1 else row
    original = json.loads((attempt/'started.json').read_text())
    elapsed = row.get('elapsed_seconds',
        (datetime.fromisoformat(row['utc'])-datetime.fromisoformat(original['started_utc'])).total_seconds())
    view.update(utc=row['utc'], elapsed_minutes=round(elapsed/60, 2))
    view['resource_sample_age_seconds'] = round((now-datetime.fromisoformat(row['utc'])).total_seconds(),2)
    for field in ['rss_bytes', 'mem_available_bytes', 'disk_free_bytes']:
        view[field.replace('_bytes', '_GiB')] = round(row[field]/2**30, 2)
    view['live_cpu_tick_growth_last_sample'] = sum(
        process['cpu_ticks'] - previous['processes'][pid]['cpu_ticks']
        for pid, process in row['processes'].items()
        if pid in previous['processes'] and
        process['start_ticks'] == previous['processes'][pid]['start_ticks'])
if (attempt/'status.json').exists():
    status = json.loads((attempt/'status.json').read_text())
    view['terminal'] = {field: status.get(field) for field in
                        ['ended_utc', 'exit_code', 'native_exit_code', 'stop_reason', 'owned_survivors']}
else:
    view['terminal'] = None
runs = root / active['project'] / 'scalellm_vcu118_f05.runs'
execution = json.loads((report/'command.json').read_text()) if (report/'command.json').exists() else {}
view['execution_mode'] = execution.get('execution_mode')
if active['stage'] == 'synth':
    directories = sorted(runs.glob('*synth_1'))
    view['completed_synth_runs'] = sum((directory/'.vivado.end.rst').exists() for directory in directories)
    view['total_synth_runs'] = len(directories)
elif active['stage'] in {'place','route'} and execution.get('execution_mode') != 'checkpoint_restored_commands':
    directories = [runs/'impl_1']
else:
    directories = []
view['active_native_logs'] = []
for directory in directories:
    log = directory / 'runme.log'
    if log.exists() and not (directory/'.vivado.end.rst').exists():
        with log.open('rb') as stream:
            stream.seek(0, 2)
            stream.seek(max(0, stream.tell()-16384))
            lines = stream.read().decode(errors='replace').splitlines()[-3:]
        view['active_native_logs'].append(dict(run=directory.name,
            error_receipt=(directory/'.vivado.error.rst').exists(), tail=lines))
if not view['active_native_logs'] and (report/'vivado.log').exists():
    with (report/'vivado.log').open('rb') as stream:
        stream.seek(0, 2)
        stream.seek(max(0,stream.tell()-16384))
        view['controller_tail'] = stream.read().decode(errors='replace').splitlines()[-4:]
elif not view['active_native_logs'] and (attempt/'launcher.log').exists():
    with (attempt/'launcher.log').open('rb') as stream:
        stream.seek(0, 2)
        stream.seek(max(0,stream.tell()-16384))
        view['worker_tail'] = stream.read().decode(errors='replace').splitlines()[-4:]
if handovers:
    view['handover_status'] = json.loads((resources.parent/'status.json').read_text()) if (resources.parent/'status.json').exists() else 'RUNNING'
if '--brief' in sys.argv[1:]:
    print(json.dumps(dict(utc=view.get('utc'),supervisor_identity_matches=view.get('supervisor_live_identity',{}).get('start_matches'),
        sample_age_s=view.get('resource_sample_age_seconds'),rss_GiB=view.get('rss_GiB'),
        mem_GiB=view.get('mem_available_GiB'),disk_GiB=view.get('disk_free_GiB'),
        cpu_tick_growth=view.get('live_cpu_tick_growth_last_sample'),terminal=view.get('terminal'),
        tail=view.get('controller_tail',view.get('worker_tail',[]))[-2:]),ensure_ascii=False))
else:
    print(json.dumps(view, ensure_ascii=False, indent=2))
