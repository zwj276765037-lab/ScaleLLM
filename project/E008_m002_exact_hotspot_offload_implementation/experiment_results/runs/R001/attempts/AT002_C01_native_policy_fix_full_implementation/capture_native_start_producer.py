#!/usr/bin/env python3
"""Capture an actually running E008 owner and consumed sources; no EDA control."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[3]


def identity(path):
    path=Path(path).resolve();before=path.stat();h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):h.update(block)
    after=path.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    return dict(path=str(path),bytes=after.st_size,sha256=h.hexdigest())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt',required=True,type=Path);parser.add_argument('--report',required=True,type=Path)
    args=parser.parse_args();at=args.attempt.resolve();report=args.report.resolve()
    assert at.parent==ROOT/'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts'
    assert report.parent==ROOT/'project/hardware/vivado/reports' and report.name.startswith('m002_E008_R001_')
    os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
    target=at/'native_start_verified.json';producer=at/'capture_native_start_producer.py'
    assert not target.exists() and not producer.exists()
    started=json.loads((at/'started.json').read_text());inputs=json.loads((at/'input_bindings.json').read_text())
    assert identity(at/'input_bindings.json')==started['inputs']
    sample=json.loads((at/'resources.jsonl').read_text().splitlines()[-1])
    expected=dict(sample['processes']);expected[str(started['supervisor_pid'])]={'start_ticks':started['supervisor_start_ticks']}
    owners=[]
    for pid,row in sorted(expected.items(),key=lambda item:int(item[0])):
        fields=Path('/proc/'+pid+'/stat').read_text().rsplit(')',1)[1].split()
        assert int(fields[19])==row['start_ticks'] and fields[0]!='Z'
        cmd=Path('/proc/'+pid+'/cmdline').read_bytes().replace(b'\0',b' ').decode()
        affinity=sorted(os.sched_getaffinity(int(pid)))
        assert set(affinity)<=set(range(8)) and int(fields[16])==5
        owners.append(dict(pid=int(pid),start_ticks=int(fields[19]),state=fields[0],nice=int(fields[16]),affinity=affinity,cmdline=cmd))
    assert any('/bin/unwrapped/lnx64.o/vivado' in row['cmdline'] for row in owners)
    project_native=[];other_native_count=0
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():continue
        try:
            command=(entry/'cmdline').read_bytes();parts=command.split(b'\0')
            if not parts[0].decode().endswith('/bin/unwrapped/lnx64.o/vivado'):continue
            if str(ROOT).encode() in command:project_native.append(int(entry.name))
            else:other_native_count+=1
        except (FileNotFoundError,ProcessLookupError,PermissionError):pass
    assert len(project_native)==1 and project_native[0] in {row['pid'] for row in owners}
    with (ROOT/'project/hardware/vivado/.m002_eda.lock').open('r') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:held=True
        else:held=False;fcntl.flock(lock,fcntl.LOCK_UN)
    assert held
    manifest=json.loads(Path(inputs['preparation_manifest']['path']).read_text())
    assert identity(inputs['preparation_manifest']['path'])==inputs['preparation_manifest']
    source_rows=manifest['own_sources']+manifest['reused_sources']
    assert inputs['source_bindings']==source_rows
    all_rows=source_rows+manifest.get('runtime_dependencies',[])+manifest.get('CPU_checks',[])+manifest.get('documentation',[])
    assert all(identity(row['path'])==row for row in all_rows)
    archives=[]
    for row in source_rows:
        archived=identity(report/'stage_sources'/Path(row['path']).name)
        assert all(archived[key]==row[key] for key in ['bytes','sha256']);archives.append(archived)
    assert len(list((report/'stage_sources').iterdir()))==len(source_rows)
    freeze=inputs['frozen_inputs']['freeze'];assert identity(freeze['path'])==freeze
    production=json.loads(Path(freeze['path']).read_text())['files']
    assert len(production)==144 and all(identity(row['path'])==row for row in production)
    assert inputs['frozen_inputs']['verified_files']==144 and inputs['frozen_inputs']['unchanged'] is True
    assert identity(report/'stage_inputs.sha256')==inputs['stage_inputs']
    shutil.copy2(Path(__file__),producer)
    value=dict(observed_utc=datetime.now(timezone.utc).isoformat(),actual_native_started=True,
        stage='actual initialization_or_checkpoint_restore',selected_candidate=inputs['attribution']['selected_candidate'],
        started=identity(at/'started.json'),input_bindings=identity(at/'input_bindings.json'),
        preparation_manifest=inputs['preparation_manifest'],actual_native_process_tree=owners,
        unique_project_native=project_native,unique_project_scope='ScaleLLM workspace command identity; unrelated shared-host native sessions are not controlled',
        excluded_external_native_sessions=other_native_count,lane_nonblocking_probe='held_as_expected',
        all_bound_source_CPU_document_runtime_identities_verified=len(all_rows),archived_runtime_sources=archives,
        production_files_checked=144,production_inputs_unchanged=True,stage_inputs=inputs['stage_inputs'],
        sample=dict(utc=sample['utc'],tree_RSS_GiB=sample['rss_bytes']/2**30,MemAvailable_GiB=sample['mem_available_bytes']/2**30,disk_free_GiB=sample['disk_free_bytes']/2**30),
        implementation_phases='PENDING_ACTUAL_NATIVE_QUALIFICATION_AND_COMPLETION',formal_signoff=False,producer=identity(producer))
    with target.open('x') as stream:stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(facts=identity(target),selected=value['selected_candidate'],owners=owners,sample=value['sample'])))


if __name__=='__main__':main()
