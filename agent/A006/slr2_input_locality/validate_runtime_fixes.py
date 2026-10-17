#!/usr/bin/env python3
"""Directly affected CPU counterexamples; no primitive re-scan or EDA."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import evidence_adapter as a


def tcl_source(path,tail):
    stub='proc m002_live_pre_place_restore {} {exec python3 [file join $::m002_script_dir m002_physical_evidence.py]}\n'
    stub+='proc m002_post {point} {exec python3 [file join $::m002_script_dir m002_physical_evidence.py]}\n'
    return subprocess.run(['tclsh'],input=stub+'source {'+str(path)+'}\n'+tail,
                          text=True,capture_output=True,check=True).stdout.splitlines()


def main():
    for path in HERE.glob('*.py'):ast.parse(path.read_text(),filename=str(path))
    for path in HERE.glob('*.tcl'):
        result=subprocess.run(['tclsh'],input='set h [open {'+str(path)+'} r]\nputs [info complete [read $h]]\nclose $h\n',text=True,capture_output=True,check=True)
        assert result.stdout.strip()=='1'
    old=HERE/'review_before_runtime_fixes'
    def selector_ast(path):
        node=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='selected')
        return hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
    assert selector_ast(HERE/'evidence_adapter.py')==selector_ast(old/'evidence_adapter.py')
    tail=''
    for name in ('prefix','group','selected'):tail+='puts [list '+name+' [info body slr2::'+name+']]\n'
    assert tcl_source(HERE/'candidate_hooks.tcl',tail)==tcl_source(old/'candidate_hooks.tcl',tail)
    prior=json.loads((HERE/'bounded_CPU_validation.json').read_text())
    accepted=[]
    for ref,count in prior['semantic_REF_counts'].items():
        physical_ref='DSP48E2' if ref.startswith('DSP') else ref
        a.accepted_raw_resource(ref,a.FRONT+'u_hadamard/actual_parent',physical_ref)
        result=a.bindable(physical_ref)
        assert result==(ref not in {'GND','VCC'})
        accepted.append(dict(raw_REF=ref,physical_REF=physical_ref,raw_count=count,bindable=result))
    denied=['RAMB36E2','URAM288','UNKNOWN','BUFGCE','IBUF','DSP_ALU']
    for ref in denied:
        try:a.bindable(ref)
        except ValueError:pass
        else:raise AssertionError('Unexpected resource accepted: '+ref)
    for ref,parent,pref in [('DSP_UNKNOWN',a.FRONT+'u_hadamard/p','DSP48E2'),
                            ('DSP_ALU','elsewhere/p','DSP48E2')]:
        try:a.accepted_raw_resource(ref,parent,pref)
        except ValueError:pass
        else:raise AssertionError('Unexpected raw DSP/ancestor accepted')
    cases=[('FDRE','C','0','CLOCK_REF_PIN'),('FDRE','C','1','CLOCK_NATIVE_PIN'),
        ('DSP48E2','C','0','DATA_ARITHMETIC'),('DSP_C_DATA','C[3]','0','DATA_ARITHMETIC'),
        ('BUFGCE','O','0','CLOCK_BUFFER_OUTPUT_REF'),('MUXF7','S','0','SELECT_CONTROL'),
        ('LUT6','I0','0','LOGIC_PIN_FUNCTION_UNCLASSIFIED'),('CARRY8','S[2]','0','DATA_LOGIC_PRIMITIVE'),
        ('FDCE','CLR','0','RESET_SET'),('DSP48E2','CEP','0','ENABLE_WRITE_CONTROL'),
        ('UNKNOWN','weird','0','UNKNOWN_REF_PIN')]
    tail=''.join('puts [slr2::pin_class {'+ref+'} {'+pin+'} {'+clk+'}]\n' for ref,pin,clk,_ in cases)
    assert tcl_source(HERE/'candidate_hooks.tcl',tail)==[expected for *_,expected in cases]
    tail=''
    for ref in denied:tail+='puts [catch {slr2::bindable {'+ref+'}}]\n'
    assert tcl_source(HERE/'candidate_hooks.tcl',tail)==['1']*len(denied)
    assert tcl_source(HERE/'candidate_hooks.tcl','puts [slr2::region_token X0Y1]\nputs [slr2::region_token CLOCKREGION_X0Y1]\nputs [catch {slr2::region_token fabricated}]\n')==['CLOCKREGION_X0Y1','CLOCKREGION_X0Y1','1']
    original_name=a.FRONT+'register_r_reg[0]'
    def obj(name,origin='',ref='FDRE'):
        return dict(NAME=name,REF_NAME=ref,ORIG_CELL_NAME=origin,ORIG_REF_NAME=ref if origin else '',LOC='SLICE_X1Y1',SLR='SLR2')
    original={original_name:'FDRE'}
    checks={}
    checks['surviving_original']=a.reconcile_objects(original,original,[obj(original_name)],[])['qualified']
    checks['missing_rejected']=not a.reconcile_objects(original,{},[],[])['qualified']
    checks['unknown_new_rejected']=not a.reconcile_objects(original,original,[obj(original_name),obj('elsewhere/new')],[])['qualified']
    clone=obj('elsewhere/actual_native_copy',original_name)
    replacement=a.reconcile_objects(original,{},[clone],[])
    checks['native_origin_replacement_accepted']=replacement['qualified'] and replacement['explained_replacements']=={original_name:[clone['NAME']]}
    checks['off_prefix_clone_in_actual_P']=clone['NAME'] in replacement['resolved']
    checks['known_clone_outside_Pblock_rejected']=not a.reconcile_objects(original,original,[obj(original_name)],[clone])['qualified']
    checks['literal_missing_from_Pblock_rejected']=not a.reconcile_objects(original,original,[],[])['qualified']
    checks['unrelated_DSP_rejected']=not a.reconcile_objects({'unrelated/dsp':'DSP48E2'}, {'unrelated/dsp':'DSP48E2'},[obj('unrelated/dsp',ref='DSP48E2')],[])['qualified']
    checks['missing_and_unknown_together_rejected']=not a.reconcile_objects(original,{},[obj('elsewhere/unknown')],[])['qualified']
    assert all(checks.values()),checks
    print(json.dumps(dict(status='PASS_CPU_ONLY',EDA_executed=False,
        literal_selector_unchanged=True,reused_prior_59_cases=True,full_primitive_export_rescanned=False,
        bindable_changed=True,original_REF_distribution_checks=accepted,
        raw_DSP_REF_or_Hadamard_ancestor_rejection_cases=2,
        unsupported_REF_rejection_cases=denied,REF_aware_pin_cases=len(cases),reconciliation_checks=checks,
        native_clock_region_token_forms_checked=2,
        native_API_geometry_policy_timing='NOT_RUN; unsupported required checks reject rather than claim native qualification')))


if __name__=='__main__':main()
