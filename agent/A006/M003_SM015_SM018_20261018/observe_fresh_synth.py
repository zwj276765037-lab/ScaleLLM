#!/usr/bin/env python3
"""One synchronous, bounded observation; never launches or controls tools."""
from pathlib import Path
import datetime, json, os, re
from collections import deque

ROOT = Path(__file__).resolve().parents[3]
STATE = Path(__file__).with_name('continuation_state.json')
s = json.loads(STATE.read_text())
a = s['active']
job = Path(a['job'])
with (job / 'resources.jsonl').open() as f:
    recent = [json.loads(line) for line in deque(f, maxlen=61)]
sample, prior = recent[-1], recent[0]
common = sample['processes'].keys() & prior['processes'].keys()
cpu_delta = sum(max(0, sample['processes'][pid]['cpu_ticks']-
                    prior['processes'][pid]['cpu_ticks'])
                for pid in common
                if sample['processes'][pid]['start_ticks'] ==
                prior['processes'][pid]['start_ticks']) / os.sysconf('SC_CLK_TCK')
runs = sorted((Path(a['project']) / 'scalellm_vcu118_f05.runs').glob('*synth_1'))
done, errors, active = [], [], []
for d in runs:
    if (d / '.vivado.end.rst').exists():
        done.append(d.name)
    if (d / '.vivado.error.rst').exists():
        errors.append(d.name)
    log = d / 'runme.log'
    if log.exists() and not (d / '.vivado.end.rst').exists():
        active.append(dict(run=d.name, log_bytes=log.stat().st_size,
                           tail=log.read_text(errors='replace').splitlines()[-3:]))
native_log=(Path(a['report'])/'vivado.log').read_text(errors='replace') if (Path(a['report'])/'vivado.log').exists() else ''
native_dependencies=set(re.findall(r"Reading design checkpoint '([^']+)' for cell '([^']+)'",native_log))
result = dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              attempt=Path(a['attempt']).name, stage=a.get('stage','synth'),
              resource_sample_utc=sample['utc'],
              owned_processes=len(sample['processes']),
              common_owned_CPU_seconds_in_recent_60_samples=round(cpu_delta, 2),
              rss_GiB=round(sample['rss_bytes']/2**30, 2),
              available_GiB=round(sample['mem_available_bytes']/2**30, 2),
              disk_GiB=round(sample['disk_free_bytes']/2**30, 2),
              synthesis_run_count=len(runs), ended_count=len(done),
              synthesis_counts_scope='preserved original AT003 producers, not current recovery progress',
              current_native_unique_dependency_reads=len(native_dependencies),
              error_runs=errors, active=active,
              actual_apply_success_receipts=len(list(Path(a['report']).glob('m003_apply_success_*.json'))),
              selected_qualification_exists=(Path(a['report'])/'m003_qualification_synth.json').exists(),
              native_log_tail=(job/'launcher.log').read_text(errors='replace').splitlines()[-5:],
              supervisor_status=json.loads((job/'status.json').read_text())
              if (job/'status.json').exists() else None)
with Path(__file__).with_name(Path(a['attempt']).name[:5]+'_synchronous_observations.jsonl').open('a') as f:
    f.write(json.dumps(result, ensure_ascii=False)+'\n')
print(json.dumps(result, ensure_ascii=False))
