"""Register only observed owned-job facts; it never launches or controls EDA."""
from pathlib import Path
import argparse, datetime, hashlib, json, subprocess
p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--job',required=True);p.add_argument('--session',type=int);p.add_argument('--stage',required=True);p.add_argument('--scope',required=True);p.add_argument('--active',action='store_true');a=p.parse_args()
r=Path.cwd();e=r/'project/E011_m003_joint_routability_implementation';at=e/'experiment_results/runs/R002/attempts'/a.attempt;j=at/'evidence/jobs'/a.job;s=json.loads((j/'started.json').read_text());t=json.loads((j/'status.json').read_text()) if (j/'status.json').exists() else None
state=t['execution_state'] if t else 'running'
def ident(f):return dict(path=str(f),bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest())
binding=at/'evidence/runtime_binding.json';binding.write_text(json.dumps(dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),stage=a.stage,report=s['report'],native_started=ident(j/'started.json'),native_status=ident(j/'status.json') if t else None,scope=a.scope),indent=2)+'\n')
x=dict(execution_state=state,command=' '.join(s['command'])+'; cwd='+s['cwd'],code_identity='G2 '+s['G2']['sha256']+'; current frozen entry '+ident(r/'project/hardware/vivado/constraints/m003_entry_manifest.json')['sha256'],input_identity='Actual command/source_archive preserved by owned supervisor; current native lineage remains distinct from original AT003 failed outer result',started_at=s['started_utc'],scope=a.scope,evidence=[str(f.relative_to(r)) for f in [j/'started.json',binding]])
if t:x.update(finished_at=t['ended_utc'],exit_status=t['native_exit_code']);x['evidence'].append(str((j/'status.json').relative_to(r)))
f=e/'experiment_source'/(a.attempt[:5]+'_actual_owned_registration.json');f.write_text(json.dumps(x,indent=2)+'\n');aid,title=a.attempt.split('_',1)
subprocess.run(['python3','/home/zwj/.codex/skills/research-agent/scripts/organize.py','attempt','--root',str(r),'--experiment','E011','--run','R002','--id',aid,'--title',title,'--input',str(f.relative_to(r))],check=True)
if a.active:
 sp=r/'agent/A006/M003_SM015_SM018_20261018/continuation_state.json';v=json.loads(sp.read_text());v['last_observed_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();v['active']=dict(run='R002',attempt=str(at),job=str(j),project=next((s['command'][i+1] for i,x in enumerate(s['command'][:-1]) if x=='--project'),s['report']+'/native_project'),report=s['report'],exec_session_id=a.session,started_utc=s['started_utc'],supervisor_pid=s['supervisor_pid'],leader_pid=s['leader_pid'],leader_start_ticks=s['leader_start_ticks'],state=state,stage=a.stage)
 sp.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(dict(attempt=aid,observed_state=state,status=t)))
