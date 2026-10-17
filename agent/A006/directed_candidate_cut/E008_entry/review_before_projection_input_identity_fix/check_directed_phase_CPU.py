#!/usr/bin/env python3
"""CPU replay of actual collector mock ledgers through E008 phase view/validator."""
import ast
import argparse
from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(HERE))
import evidence_adapter as a
from directed_evidence import identity,save


def main():
    os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='bounded_CPU_admission_directed_CT003.json');args=parser.parse_args()
    assert Path(args.output).name==args.output
    output=HERE/args.output;assert not output.exists()
    checks={};replays=[]
    fixtures=ROOT/'agent/A007/directed_source_review_20261017/mock_round3'
    assert (HERE/'directed_exporter.tcl').read_bytes()==(HERE.parent/'directed_exporter.tcl').read_bytes()
    assert (HERE/'directed_evidence.py').read_bytes()==(HERE.parent/'directed_evidence.py').read_bytes()
    checks['same_exact_R005_shared_collector_and_validator_bytes']=True
    for src in sorted(fixtures.iterdir()):
        if not (src/'candidate_cut_test_closed.txt').is_file():continue
        with tempfile.TemporaryDirectory(prefix='E008_directed_phase_') as temporary:
            report=Path(temporary)
            for path in src.iterdir():
                if path.is_file() and not any(key in path.name for key in ['summary','validation']):shutil.copy2(path,report/path.name)
            physical=report/'candidate_P_test.tsv';old_bytes=physical.read_bytes()
            actual=report/'candidate_reconciled_P_test.tsv';actual.write_bytes(old_bytes)
            resolved={row['NAME']:row['REF_NAME'] for row in a.rows(actual)}
            (report/'candidate_reconciliation_test.json').write_text(json.dumps(dict(qualified=True,resolved=resolved)))
            # Literal P can be narrower than actual native-origin scope.
            if src.name=='dsp_copy':physical.write_text('NAME\tREF_NAME\ncandidate\tFDRE\n')
            literal_before=identity(physical)
            value=a.cut_summary('test',report);timing=a.directed_timing('test',report)
            assert value['directed_boundary_complete'] and timing['complete_directional_query_sets']
            assert identity(physical)==literal_before
            assert value['artifacts']['P']==identity(actual)
            if src.name=='dsp_copy':assert value['actual_candidate_native_leaf_pins']==4 and len(resolved)==3
            # A second invocation fails at immutable generated output, preserving prior result.
            produced=report/'candidate_cut_summary_test.json';before=identity(produced)
            try:a.cut_summary('test',report)
            except ValueError:pass
            else:raise AssertionError('Duplicate cut accepted')
            assert identity(produced)==before
            replays.append(dict(case=src.name,cut=True,timing=True,literal_P_preserved=True,actualP_rows=len(resolved),candidate_native_leaf_pins=value['actual_candidate_native_leaf_pins']))
    assert len(replays)==14
    checks['fourteen_actual_collector_mock_closed_phase_and_timing_views']=True
    checks['root_external_copy_DSP_reconciled_actual_P_view']=True
    checks['literal_P_never_overwritten_and_actual_P_identity_recorded']=True
    checks['duplicate_validator_output_rejected']=True
    # Before physical placement the actual P is the native literal set and UNPLACED is valid.
    with tempfile.TemporaryDirectory(prefix='E008_preplace_directed_') as temporary:
        report=Path(temporary);src=fixtures/'ingress'
        for path in src.iterdir():
            if path.is_file() and not any(key in path.name for key in ['summary','validation']):
                shutil.copy2(path,report/path.name.replace('_test','_pre_place'))
        # The native payload POINT is not a field in these raw graph ledgers.
        value=a.cut_summary('pre_place',report);timing=a.directed_timing('pre_place',report)
        assert value['directed_boundary_complete'] and timing['complete_directional_query_sets']
        assert value['artifacts']['P']==identity(report/'candidate_P_pre_place.tsv')
    checks['pre_place_literal_actual_P_without_reconciliation_supported']=True
    # Misbound actual phase P must fail before producing any cut conclusion.
    with tempfile.TemporaryDirectory(prefix='E008_wrong_actual_P_') as temporary:
        report=Path(temporary)
        (report/'candidate_reconciled_P_place.tsv').write_text('NAME\tREF_NAME\nwrong\tFDRE\n')
        (report/'candidate_reconciliation_place.json').write_text(json.dumps(dict(qualified=True,resolved={'other':'FDRE'})))
        try:a.directed_validation_projection('place',report)
        except ValueError:pass
        else:raise AssertionError('Actual P mismatch accepted')
    checks['mismatched_native_reconciled_P_identity_rejected']=True
    for path in sorted(HERE.glob('*.py')):ast.parse(path.read_text(),filename=str(path))
    checks['Python_AST']=True
    for path in HERE.glob('*.tcl'):
        result=subprocess.run(['tclsh'],input='set h [open {'+str(path)+'}];puts [info complete [read $h]];close $h\n',capture_output=True,text=True)
        assert result.returncode==0 and result.stdout.strip()=='1'
    checks['Tcl_info_complete']=True
    baseline=ROOT/'agent/A006/exact_hotspot_offload'
    def function(path,name):return ast.dump(next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False)
    for name in ['successful_pre_place_parent','constraint_chain','membership','reconcile_objects','require_origin_query','reconcile']:
        assert function(HERE/'evidence_adapter.py',name)==function(baseline/'evidence_adapter.py',name),name
    checks['successful_parent_constraints_membership_origin_qualification_AST_unchanged_from_b59']=True
    save(output,dict(recorded_utc=datetime.now(timezone.utc).isoformat(),execution='CPU_PREPARED_NATIVE_NOT_RUN',EDA_executed=False,
        candidate_selected=None,implementation_qualified=False,checks=checks,actual_mock_phase_replays=replays,
        shared_R005_manifest=identity(HERE.parent/'prepared_source_manifest.json'),b59_manifest=identity(baseline/'prepared_manifest.json'),
        fixture_snapshot=identity(ROOT/'agent/A007/directed_source_review_20261017/round3_source_identities.json'),
        source_identities=[identity(p) for p in sorted(HERE.glob('*.py'))]+[identity(p) for p in sorted(HERE.glob('*.tcl'))],
        producer=identity(__file__),limitations=['Explicit CPU/native mocks, not Vivado or actual E008 qualification',
            'No selected candidate, physical stage, timing signoff or route success','Same-phase P projection does not alter raw evidence']))
    print(json.dumps(identity(output)))

if __name__=='__main__':main()
