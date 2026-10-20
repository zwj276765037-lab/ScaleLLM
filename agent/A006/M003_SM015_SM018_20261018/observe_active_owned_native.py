"""Read-only bounded observation of the current owned native attempt; no control."""
from pathlib import Path
import json,re
ROOT=Path(__file__).resolve().parents[3]
state=json.loads(Path(__file__).with_name('continuation_state.json').read_text())
a=state['active'];job=Path(a['job']);report=Path(a['report'])
def tail(p,n=1200):
 if not p.exists():return ''
 with p.open('rb') as f:f.seek(max(0,p.stat().st_size-n));return f.read().decode(errors='replace')
samples=tail(job/'resources.jsonl',20000).splitlines();s=json.loads(samples[-1]);log=job/'launcher.log';prefix=log.read_text(errors='replace') if log.stat().st_size<2*1024**2 else None
result={'utc':s['utc'],'attempt':Path(a['attempt']).name,'RSS_GiB':round(s['rss_bytes']/1024**3,2),'MemAvailable_GiB':round(s['mem_available_bytes']/1024**3,1),'disk_free_GiB':round(s['disk_free_bytes']/1024**3,1),'processes':{pid:{key:v[key] for key in ('start_ticks','cpu_ticks','nice')} for pid,v in s['processes'].items()},'current_native_dependency_read_count':len(re.findall("Reading design checkpoint '",prefix)) if prefix is not None else None,'native_status':json.loads((job/'status.json').read_text()) if (job/'status.json').exists() else None,'apply_outputs':[{'name':p.name,'bytes':p.stat().st_size,'text':p.read_text()[:800]} for p in report.glob('m003_apply*') if p.stat().st_size<8192],'selected_outputs':[{'name':p.name,'bytes':p.stat().st_size} for pattern in ('m003_native*','m003_qualification*','m003_same_stage_budget*','M003_*') for p in report.glob(pattern)],'log_tail':tail(log)}
partial=sorted(report.glob('m003_uram_properties_*.tsv'))
result['snapshot_partial_outputs']={'uram_property_files':len(partial),'nonempty_uram_property_files':sum(p.stat().st_size>0 for p in partial),'snapshot_error_traces':[{'name':p.name,'bytes':p.stat().st_size} for p in report.glob('m003_snapshot_*_error_info.txt')]}
print(json.dumps(result))
