#!/usr/bin/env python3
"""Capture closed native class-schema substep; never promotes unfinished cut."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import shutil
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'agent/A006/directed_candidate_top_port_index'))
from directed_evidence import identity,save,require,tdict,split


def main():
    parser=argparse.ArgumentParser();parser.add_argument('point',choices=['C01','C02']);parser.add_argument('--attempt',required=True,type=Path);parser.add_argument('--report',required=True,type=Path)
    args=parser.parse_args();at=args.attempt.resolve();report=args.report.resolve();point=args.point
    require(at.parent==ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R006/attempts','Wrong attempt')
    out=at/f'candidate_{point}_native_class_schema_closed_facts.json';producer=at/f'capture_{point}_native_schema_producer.py';require(not out.exists() and not producer.exists(),'Never overwrite schema evidence')
    path=report/f'candidate_directed_class_schema_{point}.tcllist';before=identity(path);schema=tdict(path.read_text());require(identity(path)==before,'Schema producer not closed')
    responses=[tdict(value) for value in split(schema['responses'])]
    require(len(responses)==2,'Wrong native class command count')
    require(split(responses[0]['command'])==['list_property','-class','pin'] and split(responses[1]['command'])==['list_property_value','DIRECTION','-class','pin'],'Unexpected native class proof')
    actual=all(row['native_tcl_code']=='0' for row in responses) and {'NAME','DIRECTION','IS_LEAF'}<=set(split(responses[0]['result'])) and {'IN','OUT','INOUT'}<=set(split(responses[1]['result'])) and schema['native_tool']=='2025.2'
    require(schema['qualified']==str(int(actual)),'Native schema qualification declaration differs')
    inputs=json.loads((at/'input_bindings.json').read_text());start=json.loads((at/'started.json').read_text());require(identity(at/'input_bindings.json')==start['inputs'],'Started native binding changed')
    shutil.copy2(Path(__file__),producer)
    value=dict(observed_utc=datetime.now(timezone.utc).isoformat(),point=point,coverage_version=schema['coverage_version'],native_class_schema_qualified=actual,
        execution='closed_native_substep_only',scope='Actual global pin class schema/enum proof on current native tool; candidate leaf/alias/role/cut/timing remain independently required',
        native_tool=schema['native_tool'],native_commands_and_full_responses=responses,schema=before,
        input_bindings=identity(at/'input_bindings.json'),source_DCP=inputs['checkpoint'],prepared_source_manifest=inputs['preparation_manifest'],
        local_candidate_leaf_coverage='NOT_ASSESSED_BY_THIS_SUBSTEP',directed_cut_complete=False,candidate_supported='NOT_ASSESSED',formal_signoff=False,producer=identity(producer))
    save(out,value);print(json.dumps(identity(out)))

if __name__=='__main__':main()
