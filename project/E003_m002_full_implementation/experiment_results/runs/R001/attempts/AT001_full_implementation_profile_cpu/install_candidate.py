"""Install only validated frozen E003 delta while the exclusive EDA lane is idle."""
from pathlib import Path
import datetime as dt
import fcntl
import hashlib
import json
import os
import shutil
at=Path(__file__).resolve().parent
workspace=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');hardware=workspace/'project/hardware'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
validation=json.loads((at/'validation_result.json').read_text());assert validation['verdict']=='PASS' and validation['tests_executed']==129
for row in (at/'archived_sources.sha256').read_text().splitlines():
    digest,name=row.split('  ',1);assert sha(Path(name))==digest,name
old=workspace/'project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R002/attempts/AT012_post_debug_pre_place_recovery_cpu/installation.json'
lock=(hardware/'vivado/.m002_eda.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
for row in json.loads(old.read_text())['files']:
    assert sha(Path(row['path']))==row['after_sha256'],'live input changed since tested AT012: '+row['path']
old_physical=hardware/'vivado/reports/m002_E002_R003_AT009_completed_pre_place_recovery_place_physopt/stage_sources'
for name in ('m002_physical_evidence.py','run_managed_eda.py','run_m002_physical_stage.py','m002_resume_physical.tcl','m002_diagnostic_common.tcl'):
    assert sha(hardware/'vivado/scripts'/name)==sha(old_physical/name),'live input changed since AT009: '+name
changes=[]
for name in ('m002_execution_profile.py','m002_physical_evidence.py','run_managed_eda.py','run_m002_physical_stage.py','test_m002_full_implementation.py'):
    target=hardware/('tests' if name.startswith('test_') else 'vivado/scripts')/name
    if name in ('m002_execution_profile.py','test_m002_full_implementation.py'):assert not target.exists(),'new path used: '+str(target)
    changes.append(dict(path=str(target),before_sha256=sha(target) if target.exists() else None,after_sha256=sha(at/'source_archive'/name)))
for row in changes:
    target=Path(row['path']);shutil.copy2(at/'source_archive'/target.name,target);assert sha(target)==row['after_sha256']
mem=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
value=dict(installed_utc=dt.datetime.now(dt.timezone.utc).isoformat(),verified_against='AT012 tested installation and AT009 archived source; exclusive EDA lane lock',files=changes,validation_sha256=sha(at/'validation_result.json'),frozen_manifest_sha256=sha(at/'archived_sources.sha256'),cpu_affinity=sorted(os.sched_getaffinity(0)),mem_available_kib=int(mem['MemAvailable'].split()[0]),disk_free_bytes=shutil.disk_usage(hardware).free)
(at/'installation.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value))
