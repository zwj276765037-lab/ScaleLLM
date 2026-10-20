"""Bounded read-only view of current URAM diagnostic; never process control."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[3]
state = json.loads(Path(__file__).with_name('continuation_state.json').read_text())
active = state['active']
job, report = Path(active['job']), Path(active['report'])


def tail(path, size=3000):
    if not path.exists():
        return ''
    with path.open('rb') as stream:
        stream.seek(max(0, path.stat().st_size - size))
        return stream.read().decode(errors='replace')


def available_json(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {'present_but_not_parseable_yet': True, 'bytes': path.stat().st_size}


sample = json.loads(tail(job / 'resources.jsonl', 20000).splitlines()[-1])
print(json.dumps({
    'utc': sample['utc'],
    'attempt': Path(active['attempt']).name,
    'RSS_GiB': round(sample['rss_bytes'] / 1024**3, 3),
    'available_GiB': round(sample['mem_available_bytes'] / 1024**3, 2),
    'disk_GiB': round(sample['disk_free_bytes'] / 1024**3, 2),
    'processes': {pid: {key: row[key] for key in ('start_ticks', 'cpu_ticks')} for pid, row in sample['processes'].items()},
    'native_status': available_json(job / 'status.json'),
    'diagnostic_complete': available_json(report / 'diagnostic_complete.json'),
    'diagnostic_progress_tail': tail(report / 'diagnostic_progress.jsonl'),
    'diagnostic_error': tail(report / 'diagnostic_error_info.txt'),
    'outputs': [{'name': path.name, 'bytes': path.stat().st_size} for path in sorted(report.glob('uram_*.json*'))],
    'launcher_log_tail': tail(job / 'launcher.log', 1600),
    'scope': 'Live observation only; presence or parseability does not prove closed file/native completion.',
}))
