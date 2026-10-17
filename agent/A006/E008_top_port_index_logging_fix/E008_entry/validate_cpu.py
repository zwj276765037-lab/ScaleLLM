#!/usr/bin/env python3
"""Necessary CPU admission checks using closed native ledgers and real Tcl IO.

No Vivado launch, simulated native success, or physical qualification claim.
"""
import ast
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import tkinter

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'agent/A006/E006_exact_candidates_capture'))
from capture_membership_resources import table, identity, REPORT, ATTEMPT


def main():
    os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
    output=HERE/'bounded_CPU_admission_directed_CT001.json';assert not output.exists()
    checks={};artifacts=[]
    for path in HERE.glob('*.py'):ast.parse(path.read_text(),filename=str(path))
    checks['Python_AST']='PASS'
    for path in HERE.glob('*.tcl'):
        proc=subprocess.run(['tclsh'],input='set h [open {'+str(path)+'} r]\nputs [info complete [read $h]]\nclose $h\n',capture_output=True,text=True,check=True)
        assert proc.stdout.strip()=='1'
    checks['Tcl_info_complete']='PASS'
    tcl=tkinter.Tcl(); source=(HERE/'candidate_hooks.tcl').read_text()
    # Execute the exact new row writer expression against challenging real values.
    expression='[join $row "\\t"]'
    assert source.count(expression)==2
    values=['literal/g_row_branch[1].u_branch_leaf/a[3]','RAMB36E2','','','Pblock one Pblock two','SLR2','']
    with tempfile.TemporaryDirectory(prefix='E008_real_Tcl_writer_') as temp:
        path=Path(temp)/'actual_writer.tsv';tcl.setvar('row',tuple(values));tcl.setvar('channel',tcl.call('open',str(path),'w'))
        tcl.eval('puts $channel '+expression);tcl.eval('close $channel')
        assert path.read_text().rstrip('\n').split('\t')==values
    checks['real_Tcl_write_parse_literal_brackets_empty_fields_multiword_values']='PASS'
    # Execute the actual two exclusive-open source commands, not invented paths.
    # This rejects reuse of the same literal/settled-site filename within phase.
    runtime_source=(HERE/'runtime_hooks.tcl').read_text()
    literal_line=next(line.strip() for line in source.splitlines() if 'set h [open ' in line and 'candidate_literal_site_members_${point}.tsv' in line)
    settled_line=next(line.strip() for line in runtime_source.splitlines() if 'set h [open ' in line and 'candidate_site_members_${point}.tsv' in line)
    with tempfile.TemporaryDirectory(prefix='E008_phase_file_lifecycle_') as temp:
        tcl.setvar('::m002_report_dir',temp)
        for phase in ['place','physopt','route']:
            tcl.setvar('point',phase)
            for statement in [literal_line,settled_line]:
                tcl.eval(statement);tcl.eval('puts $h actual_exclusive_open_closed');tcl.eval('close $h')
        assert len(list(Path(temp).glob('*.tsv')))==6
    checks['actual_Tcl_literal_and_reconciled_site_exclusive_file_lifecycle']='PASS'

    assert '[join $row \t]' not in source
    # Use closed real native ledgers, converting only the separately documented
    # SPACE export defect; no expected native counts hardcoded into the adapter.
    targets=json.loads((HERE/'target_authority.json').read_text())['candidates'];native_replays=[]
    for target in targets:
        point=target['id'];os.environ['SLR2_CANDIDATE_ROOT']=target['root']
        spec=importlib.util.spec_from_file_location('e008_admission_'+point,HERE/'evidence_adapter.py')
        adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
        with tempfile.TemporaryDirectory(prefix='E008_native_ledger_replay_') as temp:
            report=Path(temp)
            for key in ['RAW','S','P','membership','physical_members']:
                rows=list(table(REPORT/f'candidate_{key}_{point}.tsv'))
                with (report/f'candidate_{key}_pre_place.tsv').open('w') as stream:
                    writer=csv.DictWriter(stream,fieldnames=list(rows[0]),delimiter='\t',quoting=csv.QUOTE_NONE,escapechar='\\')
                    writer.writeheader();writer.writerows(rows)
            members=list(table(REPORT/f'candidate_membership_{point}.tsv'))
            with (report/'candidate_physical_mapping_pre_place.tsv').open('w') as stream:
                stream.write('raw_NAME\tphysical_NAME\n')
                for row in members:stream.write(row['NAME']+'\t'+row['physical_parent']+'\n')
            (report/'utilization_candidate_pre_place_SLR.rpt').write_bytes((REPORT/f'utilization_candidate_{point}_SLR.rpt').read_bytes())
            result=adapter.membership('pre_place',report)
            assert adapter.selected(target['root']+'/x') and not adapter.selected(target['root']+'_extra/x')
            if point=='C01':assert not adapter.selected(target['root'].replace('[1]','[0]')+'/x')
            native_replays.append(dict(id=point,RAW=result['raw_selector_count'],S=result['semantic_S_count'],P=result['placeable_P_count'],P_REF_counts=result['P_REF_counts'],
                limits='CPU replay of actual E006 physopt ledgers. Not E008 native pre-place evidence or equality requirement.'))
        artifacts.append(identity(ATTEMPT/f'candidate_{point}_membership_resources_closed_facts.json'))
    checks['actual_closed_native_C01_C02_generic_membership_constants_DSP_BRAM_literal_selector']='PASS'
    # Evaluate only pure Tcl procedures from the actual new source.
    for name in ['prefix','group','selected','bindable','timing_boundary_selection']:
        start=source.index('proc slr2::'+name+' ');end=source.find('\nproc ',start+1)
        body=source[start:len(source) if end<0 else end]
        tcl.eval('namespace eval slr2 {}');tcl.eval(body)
    for target in targets:
        tcl.setvar('::slr2::root',target['root'])
        assert tcl.call('slr2::selected',target['root']+'/x')==1
        assert tcl.call('slr2::selected',target['root']+'_extra/x')==0
    for ref in ['RAMB36E2','RAMB18E2','URAM288','DSP48E2','FDRE']:assert tcl.call('slr2::bindable',ref)==1
    for ref in ['GND','VCC']:assert tcl.call('slr2::bindable',ref)==0
    for direction,insideDriver,expected in [('EGRESS',1,('external_load',)),('INGRESS',0,('internal_load',))]:
        result=tcl.call('slr2::timing_boundary_selection','SINGLE_DRIVER',insideDriver,('internal_load',),('external_load',),('driver','internal_load'))
        assert result[0]==direction and result[1]==expected
    checks['pure_Tcl_literal_membership_generic_P_and_directional_LOAD_selection']='PASS'
    runtime=(HERE/'runtime_hooks.tcl').read_text()
    start=runtime.index('proc slr2::resource_class ');end=runtime.index('\nproc ',start+1);tcl.eval(runtime[start:end])
    for ref,expected in [('RAMB36E2','RAMB36'),('RAMB18E2','RAMB18'),('URAM288','URAM288'),('DSP48E2','DSP48E2'),('LUT6','CLB_LOGIC_OR_DISTRIBUTED_MEMORY'),('BUFGCE','DEDICATED_CLOCK_IO_REQUIRES_SEPARATE_PROOF'),('UNRECOGNIZED_NEW_PRIMITIVE','UNKNOWN_RESOURCE_REQUIRES_EXPLANATION')]:
        assert tcl.call('slr2::resource_class',ref)==expected
    checks['memory_retained_dedicated_clock_IO_and_unknown_resources_not_auto_qualified']='PASS'
    output.write_text(json.dumps(dict(status='CPU_PREPARED_NATIVE_NOT_RUN',checks=checks,closed_native_ledger_replays=native_replays,
        input_artifacts=artifacts,source_identities=[identity(p) for p in sorted(HERE.glob('*.py'))]+[identity(p) for p in sorted(HERE.glob('*.tcl'))],producer=identity(Path(__file__)),EDA_executed=False,actual_pre_place_membership='NOT_RUN',candidate_selected=None,
        implementation_qualified=False),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(identity(output)))


if __name__=='__main__':main()
