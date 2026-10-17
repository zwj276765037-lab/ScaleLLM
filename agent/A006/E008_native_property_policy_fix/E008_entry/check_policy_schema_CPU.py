#!/usr/bin/env python3
"""Finite native-policy compatibility cases on actual runtime procedures; no EDA."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sys
import tkinter
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
BASE=ROOT/'agent/A006/E008_top_port_index_logging_fix/E008_entry'
sys.path.insert(0,str(HERE))
from directed_evidence import identity


def load(directory,report):
    t=tkinter.Tcl()
    for key,value in [('SLR2_CANDIDATE_ROOT','top/a'),('SLR2_CANDIDATE_ID','C01'),('HAP_REPORT_DIR',str(report))]:t.setvar('env('+key+')',value)
    t.call('source',str(ROOT/'project/hardware/vivado/scripts/m002_diagnostic_common.tcl'))
    t.call('source',str(directory/'candidate_hooks.tcl'))
    return t


FIXTURE=r'''
set ::caseName $caseName
set ::point before
set ::overlayCreated 0
set ::regionCalls 0
set ::schemaCalls [dict create]
set ::required {NAME REF_NAME IS_PRIMITIVE LOC BEL IS_LOC_FIXED IS_BEL_FIXED USER_SLR_ASSIGNMENT RLOC MACRO_NAME DONT_TOUCH}
set ::data [dict create]
foreach name {top top/a top/a/p0 top/a/p1 outside} {
    set primitive [expr {[string match */p? $name] || $name eq "outside"}]
    set ref [expr {$primitive ? "LUT1" : "hierarchy_ref"}]
    set values [dict create NAME $name REF_NAME $ref IS_PRIMITIVE $primitive LOC "" BEL "" IS_LOC_FIXED 0 IS_BEL_FIXED 0 USER_SLR_ASSIGNMENT "" RLOC "" RLOC_ORIGIN "" MACRO_NAME "" DONT_TOUCH 0]
    dict set ::data $name $values
}
namespace eval slr2 {
    variable root top/a
    variable P [dict create top/a/p0 LUT1 top/a/p1 LUT1]
    variable RAW $P
    variable siteSLR [dict create SLICE_X0Y0 SLR2]
    variable pblock CPU_NEW_PBLOCK
}
proc native_value {object property} {
    if {$::caseName eq "supported_nonempty" && $object eq "top/a/p0" && $property eq "RLOC_ORIGIN"} {return X0Y0}
    if {$::caseName eq "unsupported_nonempty" && $object eq "top/a/p0" && $property eq "RLOC_ORIGIN"} {return X0Y0}
    if {$::caseName eq "unsupported_error" && $object eq "top/a/p0" && $property eq "RLOC_ORIGIN"} {return -code error -errorcode CPU_NATIVE_ORIGIN_ERROR NATIVE_READ_FAILED}
    if {$::caseName eq "RLOC_nonempty" && $object eq "top/a" && $property eq "RLOC"} {return X1Y1}
    if {$::caseName eq "MACRO_NAME_nonempty" && $object eq "top/a/p0" && $property eq "MACRO_NAME"} {return ACTUAL_MACRO}
    if {$::caseName eq "conflicting_SLR" && $object eq "top" && $property eq "USER_SLR_ASSIGNMENT"} {return SLR1}
    if {$::caseName eq "after_value_change" && $::point eq "after" && $object eq "top/a/p0" && $property eq "LOC"} {return SLICE_X0Y0}
    return [dict get $::data $object $property]
}
proc list_property object {
    dict incr ::schemaCalls $object
    set props $::required
    if {$::caseName in {supported_empty supported_nonempty} || ($::caseName eq "same_REF_mixed_support" && $object eq "top/a/p1") || ($::caseName eq "after_support_change" && $::point eq "after" && $object eq "top/a/p0")} {lappend props RLOC_ORIGIN}
    if {[string match missing_* $::caseName] && $object eq "top/a/p1"} {
        set missing [string range $::caseName 8 end]
        set i [lsearch -exact $props $missing];if {$i>=0} {set props [lreplace $props $i $i]}
    }
    return $props
}
proc get_property {property objects} {
    if {[llength $objects]==1} {return [native_value [lindex $objects 0] $property]}
    set out [list];foreach object $objects {lappend out [native_value $object $property]};return $out
}
proc m002_prop {object property} {return [native_value $object $property]}
proc m002_exact {command name} {if {[dict exists $::data $name]} {return $name};return [list]}
proc slr2::property_values {objects property allow_empty context} {
    set values [list];foreach object $objects {lappend values [native_value $object $property]};return $values
}
proc slr2::objects names {return $names}
proc slr2::pblock_snapshot {} {
    set old [dict create OLD_PBLOCK [list [dict create IS_SOFT false] [list outside]]]
    if {$::overlayCreated} {dict set old $::slr2::pblock [list [dict create IS_SOFT false] [list top/a/p0 top/a/p1]]}
    return $old
}
proc slr2::constrain_region {} {incr ::regionCalls;set ::overlayCreated 1;set ::point after}
proc get_cells args {
    if {"-hier" in $args} {return [list top/a top/a/p0 top/a/p1]}
    if {"-of_objects" in $args} {
        if {$::caseName eq "macro_partners_error"} {error NATIVE_MACRO_PARTNERS_FAILED}
        return [list top/a/p0 outside]
    }
    return [list]
}
proc get_macros args {
    if {$::caseName eq "macro_enumeration_error"} {error NATIVE_MACROS_FAILED}
    if {$::caseName in {excluded_macro_partner macro_partners_error}} {return [list MACRO1]}
    return [list]
}
if {$::caseName eq "macro_api_missing"} {rename get_macros {}}
set ::actualCode [catch {slr2::constrain} ::actualResult ::actualOptions]
'''


def main():
    os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
    out=HERE/'CPU_checks/CT001_native_policy_schema';out.mkdir(parents=True,exist_ok=False)
    before=load(BASE,out);after=load(HERE,out)
    procs=lambda t:{str(name):str(t.call('info','body',name)) for name in t.splitlist(t.call('info','procs','slr2::*'))}
    old,new=procs(before),procs(after)
    changed=[name for name in old if old[name]!=new.get(name)]
    assert set(old)==set(new) and set(changed)=={'::slr2::placement_policy','::slr2::resource_admissibility'},changed
    assert new['::slr2::constrain']==old['::slr2::constrain']
    assert (HERE/'directed_exporter.tcl').read_bytes()==(BASE/'directed_exporter.tcl').read_bytes()
    cases=['observed_unsupported_empty','supported_empty','same_REF_mixed_support','supported_nonempty','unsupported_nonempty','unsupported_error','RLOC_nonempty','MACRO_NAME_nonempty','conflicting_SLR','excluded_macro_partner','macro_enumeration_error','macro_partners_error','macro_api_missing','after_support_change','after_value_change']
    cases+=['missing_'+name for name in ['NAME','REF_NAME','IS_PRIMITIVE','LOC','BEL','IS_LOC_FIXED','IS_BEL_FIXED','USER_SLR_ASSIGNMENT','RLOC','MACRO_NAME','DONT_TOUCH']]
    passes={'observed_unsupported_empty','supported_empty','same_REF_mixed_support'};results=[]
    fixture=out/'actual_policy_fixture.tcl';fixture.write_text(FIXTURE)
    for case in cases:
        report=out/case;report.mkdir();t=load(HERE,report);t.setvar('caseName',case);t.eval(FIXTURE)
        code=int(t.getvar('actualCode'));result=str(t.getvar('actualResult'));region=int(t.getvar('regionCalls'))
        assert (code==0)==(case in passes),(case,code,result)
        if case in passes:assert region==1 and (report/'candidate_policy_preservation.txt').is_file(),case
        elif case.startswith('after_'):assert region==1 and not (report/'candidate_policy_preservation.txt').exists(),case
        else:assert region==0 and not (report/'candidate_policy_preservation.txt').exists(),case
        if case in passes:
            b=t.call('slr2::placement_policy','audit',t.call('list','top','top/a','top/a/p0','top/a/p1'))
            states={name:str(t.call('dict','get',b,name,'NATIVE_RLOC_ORIGIN_SUPPORT')) for name in ['top/a/p0','top/a/p1']}
            if case=='same_REF_mixed_support':assert states['top/a/p0']!=states['top/a/p1']
        else:states={}
        row=dict(case=case,native_mock_result_code=code,result=result,region_calls=region,passed=True,support_states=states,artifacts=[identity(p) for p in sorted(report.iterdir()) if p.is_file()])
        results.append(row)
    value=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),EDA_executed=False,
        checks=dict(only_two_runtime_procedures_changed=True,constrain_macro_and_preservation_gates_identical=True,acquisition_logging_and_physical_pipeline_unchanged=True,all_26_actual_policy_cases=True,only_RLOC_ORIGIN_schema_exception=True,unsupported_native_nonempty_or_error_rejects=True,all_11_other_required_fields_fail_when_missing=True,same_REF_independent_object_support=True,before_after_support_and_value_changes_reject=True,macros_ancestors_and_partner_failures_reject=True),
        cases=results,source=identity(HERE/'runtime_hooks.tcl'),baseline=identity(BASE/'runtime_hooks.tcl'),fixture=identity(fixture),producer=identity(__file__),
        applicability='Finite native-command mocks execute actual resource_admissibility, placement_policy and constrain wrapper; no native design or implementation success claimed')
    path=out/'results.json';path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(result=identity(path),cases=len(results),all_passed=True)))


if __name__=='__main__':main()
