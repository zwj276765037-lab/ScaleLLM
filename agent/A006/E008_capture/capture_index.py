#!/usr/bin/env python3
"""Read a qualified actual E008 native index and its closed buffered alias log."""
import argparse
from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('point',choices=['pre_place','place','physopt','route','route_failed'])
    parser.add_argument('--attempt',type=Path,required=True);parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();at=args.attempt.resolve();report=args.report.resolve();point=args.point
    assert at.parent==ROOT/'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts'
    assert report.parent==ROOT/'project/hardware/vivado/reports' and report.name.startswith('m002_E008_R001_')
    os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
    module_path=report/'stage_sources/top_port_evidence.py'
    spec=importlib.util.spec_from_file_location('actual_archived_E008_top_port_evidence',module_path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);identity=module.identity
    target=at/f'candidate_{point}_native_port_index_closed_facts.json';producer=at/f'capture_{point}_native_port_index_producer.py'
    assert not target.exists() and not producer.exists()
    inputs=json.loads((at/'input_bindings.json').read_text());started=json.loads((at/'started.json').read_text())
    assert identity(at/'input_bindings.json')==started['inputs']
    assert identity(inputs['preparation_manifest']['path'])==inputs['preparation_manifest']
    source=next(row for row in inputs['source_bindings'] if Path(row['path']).name==module_path.name)
    assert all(identity(module_path)[key]==source[key] for key in ['bytes','sha256'])
    value=module.validate(point,report)
    closed_path=report/f'candidate_top_port_index_closed_{point}.json';closed=json.loads(closed_path.read_text())
    trace=report/f'candidate_alias_api_trace_{point}.tcllist';marker=report/f'candidate_alias_api_trace_{point}_closed.txt'
    logging=dict(line.split('=',1) for line in marker.read_text().splitlines())
    with trace.open() as stream:count=sum(1 for _ in stream)
    assert logging['point']==point and logging['mapping_tcl_code']=='0' and logging['normal_final_flush']=='1' and count==int(logging['recorded_events'])
    shutil.copy2(Path(__file__),producer)
    facts=dict(observed_utc=datetime.now(timezone.utc).isoformat(),point=point,
        native_index_qualification_closed=True,native_port_count=value['native_port_count'],native_group_count=len(value['groups']),native_call_count=value['native_calls'],
        native_closed_receipt=closed,archived_validator=identity(module_path),
        native_index_artifacts=[identity(value['path']),identity(value['calls_path']),identity(closed_path)],
        buffered_alias_trace=dict(receipt=logging,actual_event_lines=count,artifacts=[identity(trace),identity(marker)]),
        actual_selected_candidate=inputs['attribution']['selected_candidate'],input_bindings=identity(at/'input_bindings.json'),preparation_manifest=inputs['preparation_manifest'],
        full_physical_phase_qualification='NOT_CLAIMED_BY_INDEX_SUBSTEP',formal_signoff=False,producer=identity(producer))
    with target.open('x') as stream:stream.write(json.dumps(facts,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(identity(target)))


if __name__=='__main__':main()
