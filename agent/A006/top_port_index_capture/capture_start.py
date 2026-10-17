#!/usr/bin/env python3
"""One-time actual R006 native-start audit; no launch or process control."""
import argparse
from datetime import datetime,timezone
import fcntl
import json
import os
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'agent/A006/directed_candidate_top_port_index'))
from directed_evidence import identity,save,require


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['attempt','report','source-dir']:parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args();at=args.attempt.resolve();report=args.report.resolve();src=args.source_dir.resolve()
    require(at.parent==ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R006/attempts','Wrong R006 attempt')
    require(report.parent==ROOT/'project/hardware/vivado/reports' and report.name.startswith('m002_E006_R006_'),'Wrong R006 report')
    output=at/'native_start_verified.json';require(not output.exists(),'Never overwrite native-start audit')
    started=json.loads((at/'started.json').read_text());sample=json.loads((at/'resources.jsonl').read_text().splitlines()[-1])
    observed=[];rows=dict(sample['processes']);rows[str(started['supervisor_pid'])]={'start_ticks':started['supervisor_start_ticks']}
    for pid,expected in sorted(rows.items(),key=lambda row:int(row[0])):
        fields=Path('/proc/'+pid+'/stat').read_text().rsplit(')',1)[1].split();require(int(fields[19])==expected['start_ticks'] and fields[0]!='Z','Actual native owner identity changed')
        command=Path('/proc/'+pid+'/cmdline').read_bytes().replace(b'\0',b' ').decode();affinity=sorted(os.sched_getaffinity(int(pid)))
        require(set(affinity)<=set(range(8)) and int(fields[16])==5,'Actual CPU/nice bound differs')
        observed.append(dict(pid=int(pid),start_ticks=int(fields[19]),cmdline=command,affinity=affinity,nice=int(fields[16]),state=fields[0]))
    require(any('/bin/unwrapped/lnx64.o/vivado' in row['cmdline'] for row in observed),'Actual native binary not observed')
    with (ROOT/'project/hardware/vivado/.m002_eda.lock').open('r') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:held=True
        else:held=False;fcntl.flock(lock,fcntl.LOCK_UN)
    require(held,'EDA lane unexpectedly free during native run')
    inputs=json.loads((at/'input_bindings.json').read_text());require(identity(at/'input_bindings.json')==started['inputs'],'Actual started input binding changed')
    manifest=json.loads((src/'prepared_source_manifest.json').read_text());require(identity(src/'prepared_source_manifest.json')==inputs['preparation_manifest'],'Actual source manifest differs')
    lookup={Path(row['path']).name:row for row in manifest['source_files']}
    for row in inputs['sources']:
        require(identity(row['path'])==row,'Native archived source changed')
        require(all(row[key]==lookup[Path(row['path']).name][key] for key in ['bytes','sha256']),'Native source bytes differ from prepared source')
    require(inputs['frozen_inputs']['verified_files']==144 and inputs['frozen_inputs']['unchanged'],'Production input freeze incomplete')
    with (report/'vivado.log').open() as stream:header=stream.read(1800)
    value=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),native_started=True,stage='open_checkpoint_or_initialization',supervisor=dict(pid=started['supervisor_pid'],start_ticks=started['supervisor_start_ticks']),actual_native_process_tree=observed,
        lane_nonblocking_probe='held_as_expected',started=identity(at/'started.json'),input_bindings=identity(at/'input_bindings.json'),prepared_source_manifest=inputs['preparation_manifest'],archived_sources=inputs['sources'],
        initial_vivado_header=header,sample=dict(utc=sample['utc'],tree_RSS_GiB=sample['rss_bytes']/2**30,MemAvailable_GiB=sample['mem_available_bytes']/2**30,disk_free_GiB=sample['disk_free_bytes']/2**30),
        native_class_qualification='PENDING_ACTUAL_STAGE',candidate_selected=False,formal_signoff=False,producer=identity(__file__))
    save(output,value);print(json.dumps(dict(evidence=identity(output),sample=value['sample'],owners=observed)))

if __name__=='__main__':main()
