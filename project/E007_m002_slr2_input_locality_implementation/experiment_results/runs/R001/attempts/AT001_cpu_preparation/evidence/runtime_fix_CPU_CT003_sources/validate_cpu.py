#!/usr/bin/env python3
"""One bounded selector audit of the already-closed physopt export; no EDA."""
import ast
import collections
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE))
import evidence_adapter as a


def identity(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda:stream.read(4*1024*1024),b''):digest.update(data)
    return dict(path=str(path),bytes=path.stat().st_size,sha256=digest.hexdigest())


def main():
    os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
    if '--terminology-bridge' in sys.argv:
        before=json.loads((HERE/'selector_before_S_terminology_revision.json').read_text())
        tree=ast.parse((HERE/'evidence_adapter.py').read_text())
        functions={n.name:hashlib.sha256(ast.dump(n,include_attributes=False).encode()).hexdigest()
            for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'selected','bindable'}}
        stub='proc m002_live_pre_place_restore {} {exec python3 [file join $::m002_script_dir m002_physical_evidence.py]}\n'
        stub+='proc m002_post {point} {exec python3 [file join $::m002_script_dir m002_physical_evidence.py]}\n'
        script=stub+'source {'+str(HERE/'candidate_hooks.tcl')+'}\n'
        for name in ['prefix','group','selected','bindable']:script+='puts [list '+name+' [info body slr2::'+name+']]\n'
        result=subprocess.run(['tclsh'],input=script,text=True,capture_output=True,check=True)
        assert functions==before['Python_selector_function_AST_sha256']
        assert hashlib.sha256(result.stdout.encode()).hexdigest()==before['Tcl_selector_proc_bodies_sha256']
        prior=json.loads((HERE/'bounded_CPU_validation.json').read_text())
        assert identity(HERE/'bounded_CPU_validation.json')['sha256']==before['prior_CPU_receipt']['sha256']
        assert prior['accepted_selector_count']==77360 and prior['excluded_constants']==114
        value=dict(status='PASS_CPU_TERMINOLOGY_BRIDGE',EDA_executed=False,
            prior_actual_export_and_59_case_check=identity(HERE/'bounded_CPU_validation.json'),
            selector_unchanged=functions,Tcl_selector_unchanged=True,
            raw_selector_count=77360,semantic_S_count=77360-114,placeable_P_count=77182,
            definitions=dict(RAW='literal primitive scope including constants',S='RAW excluding GND/VCC',
                P='S after excluding non-placeable clock/IO objects and normalizing DSP internals to DSP48E2 parents'),
            reran_full_export=False,reran_59_cases=False,
            current_sources=[identity(p) for p in sorted(HERE.glob('*.py'))]+[identity(HERE/'candidate_hooks.tcl')],
            native_membership='NOT_RUN; actual pre-place RAW/S/P ledgers remain mandatory')
        target=HERE/'bounded_CPU_validation_current.json'
        target.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(dict(output=identity(target),RAW=77360,S=77246,P=77182,EDA_executed=False)))
        return
    source=ROOT/'project/hardware/vivado/reports/m002_E006_R001_AT001_physopt_attribution/all_primitive_locations.tsv'
    expected=json.loads((ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R002/input_frontend_locality_candidate_facts.json').read_text())
    actual_source=identity(source)
    assert actual_source['sha256']=='d291d95dbcb335511de5949a26b53e26a8cd168c0c3aa8972a24eb160db967f2'
    assert actual_source['bytes']==676367399
    semantic={};examples=[];excluded=[]
    with source.open() as stream:
        for row in csv.DictReader(stream,delimiter='\t'):
            name=row['cell']
            if a.selected(name):
                assert name not in semantic
                semantic[name]=row['REF_NAME']
                if len(examples)<32:examples.append(name)
            elif name.startswith((a.FRONT,a.TENSOR)) and len(excluded)<16:excluded.append(name)
    fingerprint=hashlib.sha256(('\n'.join(sorted(semantic))+'\n').encode()).hexdigest()
    assert len(semantic)==expected['selector']['matched_primitive_count']==77360
    assert fingerprint==expected['selector']['exact_sorted_cell_names_sha256']
    physical={};internal=0;constants=0
    for name,ref in semantic.items():
        if ref.startswith('DSP') and ref!='DSP48E2':
            parent=name.rsplit('/',1)[0]
            assert semantic.get(parent)=='DSP48E2'
            physical[parent]='DSP48E2';internal+=1
        elif a.bindable(ref):physical[name]=ref
        else:
            assert ref in {'GND','VCC'}
            constants+=1
    assert internal==64 and constants==114 and len(physical)==77182
    assert sum(r=='DSP48E2' for r in physical.values())==8
    tensor=set();front=set()
    for name in semantic:
        m=re.fullmatch(re.escape(a.TENSOR)+r'g_input_beat_bank\[(\d+)\]\.input_group_beat_r_reg\[(\d+)\]\[(\d+)\]',name)
        if m:
            bank,row,bit=map(int,m.groups());assert bank==row;tensor.add((row,bit))
        m=re.fullmatch(re.escape(a.FRONT)+r'input_buffer_row_r_reg\[(\d+)\]\[(\d+)\]',name)
        if m:front.add(tuple(map(int,m.groups())))
    assert tensor=={(r,b) for r in range(48) for b in range(256)}
    assert front=={(r,b) for r in range(16) for b in range(768)}
    examples += [a.FRONT+x for x in ('u_cache0/x','u_cache1/x','bundle_u8_bank_r_reg[0]',
        'bundle_meta_bank_r_reg[1]','g_bundle_row[0]/x','g_bundle_rowX/x','input_buffer_row_r_reg[0][1]')]
    examples += [a.TENSOR+x for x in ('g_input_beat_bank[0].x','g_input_beat_bankX.x',
        'input_group_r_reg[0]','output_group_r_reg[0]')]
    cases=examples+excluded
    # Source definitions only; fake original procs are never invoked. There are
    # no Vivado commands in this Tcl interpreter and no mocked native success.
    stub='proc m002_live_pre_place_restore {} {exec python3 [file join $::m002_script_dir m002_physical_evidence.py]}\n'
    stub+='proc m002_post {point} {exec python3 [file join $::m002_script_dir m002_physical_evidence.py]}\n'
    script=stub+'source {'+str(HERE/'candidate_hooks.tcl')+'}\n'
    for name in cases:
        assert not any(c in name for c in '{}\n\r')
        script+='puts [slr2::selected {'+name+'}]\n'
    native=subprocess.run(['tclsh'],input=script,text=True,capture_output=True,check=True)
    assert native.stdout.splitlines()==[str(int(a.selected(n))) for n in cases],native.stderr
    for path in HERE.glob('*.py'):ast.parse(path.read_text(),filename=str(path))
    value=dict(status='PASS_CPU_ONLY',EDA_executed=False,
        source=actual_source,accepted_selector_count=len(semantic),selector_sorted_NAME_sha256=fingerprint,
        raw_selector_count=len(semantic),semantic_S_count=len(semantic)-constants,
        normalized_placeable_physopt_reference_count=len(physical),excluded_constants=constants,
        DSP_internal_objects_normalized=internal,physical_DSP=8,
        input_indices=dict(tensor_48x256=len(tensor),capture_16x768=len(front)),
        Python_Tcl_literal_selector_cases=len(cases),all_cases_match=True,
        semantic_REF_counts=dict(collections.Counter(semantic.values())),
        limits=['Physopt reference only; actual pre-place membership/counts not measured.',
          'No Vivado APIs, Pblock geometry, actual DCP graph, connectivity cut or physical phase executed.',
          'Tcl definition parsing/selector checks do not prove API validity or actual assignment.'],
        sources=[identity(p) for p in sorted(HERE.glob('*.py'))]+[identity(HERE/'candidate_hooks.tcl')])
    out=HERE/'bounded_CPU_validation.json'
    out.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(output=identity(out),S=len(semantic),P=len(physical),Tcl_cases=len(cases),EDA_executed=False)))


if __name__=='__main__':main()
