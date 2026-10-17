#!/usr/bin/env python3
"""Finite API-option/error-propagation cases on actual constrain_region; no EDA."""
from datetime import datetime,timezone
import json,os
from pathlib import Path
import sys,tkinter
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
BASE=ROOT/'agent/A006/E008_native_property_policy_fix/E008_entry'
sys.path.insert(0,str(HERE))
from directed_evidence import identity

FIXTURE=r'''
set ::exports [list];set ::ranges [list];set ::assigned [dict create];set ::members [list];set ::created 0
namespace eval slr2 {
 variable P [dict create top/a/p0 LUT1 top/a/p1 DSP48E2]
 variable originalP [dict create]
 variable pblock CPU_C01_SLR2
 variable cellPblocks [dict create]
 variable siteSLR [dict create SLICE_X0Y0 SLR2 DSP48E2_X0Y0 SLR2 RAMB36_X0Y0 SLR2 SLICE_X9Y9 SLR1]
}
proc get_slrs args {return SLR2}
proc get_clock_regions args {return [list X0Y4 X1Y4]}
proc get_pblocks args {if {$::caseName eq "existing_pblock"} {return CPU_C01_SLR2};return [list]}
proc get_property {property objects} {if {$property ne "NAME"} {error BAD_PROPERTY};return $objects}
proc slr2::objects names {return $names}
proc slr2::value {name property} {
 if {$::caseName eq "conflicting_LOC" && $property eq "LOC" && $name eq "top/a/p0"} {return SLICE_X9Y9}
 if {$property in {IS_LOC_FIXED IS_BEL_FIXED DONT_TOUCH}} {return 0};return ""
}
proc slr2::slr site {return [dict get $::slr2::siteSLR $site]}
proc m002_prop {object property} {
 if {$property eq "NAME"} {return $object}
 if {$property eq "GRID_RANGES"} {return $::ranges}
 if {$::caseName eq "soft_readback" && $property eq "IS_SOFT"} {return true}
 return [dict get $::assigned $property]
}
proc create_pblock name {set ::created 1;return $name}
proc resize_pblock {pb option token} {if {$option ne "-add"} {error BAD_RESIZE};lappend ::ranges $token}
proc set_property {property value object} {dict set ::assigned $property $value}
proc add_cells_to_pblock {pb objects} {set ::members $objects}
proc get_cells args {
 if {$::caseName eq "member_readback"} {return [list top/a/p0]};return $::members
}
proc get_sites args {
 if {$::caseName eq "outside_site"} {return [list SLICE_X0Y0 DSP48E2_X0Y0 RAMB36_X0Y0 SLICE_X9Y9]}
 if {$::caseName eq "missing_site"} {return [list SLICE_X0Y0 DSP48E2_X0Y0]}
 return [list SLICE_X0Y0 DSP48E2_X0Y0 RAMB36_X0Y0]
}
proc write_xdc args {
 lappend ::exports $args
 if {[lindex $args 0] eq "-constraints"} {return -code error -errorcode CPU_INVALID_CONSTRAINTS INVALID_CONSTRAINTS_PHYSICAL}
 if {[llength $args] != 3 || [lrange $args 0 1] ne [list -type physical]} {error UNEXPECTED_EXPORT_OPTIONS}
 if {$::caseName eq "native_export_error"} {return -code error -errorcode CPU_XDC_NATIVE_ERROR ACTUAL_EXPORT_ERROR}
 set h [open [lindex $args 2] {WRONLY CREAT EXCL}];puts $h FIXTURE_EXPORT_ONLY;close $h
}
set ::actualCode [catch {slr2::constrain_region} ::actualResult ::actualOptions]
'''

def load(directory,report):
 t=tkinter.Tcl()
 for k,v in [('SLR2_CANDIDATE_ROOT','top/a'),('SLR2_CANDIDATE_ID','C01'),('HAP_REPORT_DIR',str(report))]:t.setvar('env('+k+')',v)
 t.call('source',str(ROOT/'project/hardware/vivado/scripts/m002_diagnostic_common.tcl'))
 t.call('source',str(directory/'candidate_hooks.tcl'))
 return t

def main():
 os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
 out=HERE/'CPU_checks/CT002_physical_export';out.mkdir(parents=True,exist_ok=False)
 old,new=load(BASE,out),load(HERE,out)
 procs=lambda t:{str(n):str(t.call('info','body',n)) for n in t.splitlist(t.call('info','procs','slr2::*'))}
 a,b=procs(old),procs(new)
 assert a.keys()==b.keys();assert [n for n in a if a[n]!=b[n]]==['::slr2::constrain_region']
 assert b['::slr2::constrain_region']==a['::slr2::constrain_region'].replace('write_xdc -constraints physical ','write_xdc -type physical ')
 fixture=out/'actual_region_fixture.tcl';fixture.write_text(FIXTURE)
 cases=[('original_invalid_option',BASE),('corrected_export',HERE),('native_export_error',HERE),('member_readback',HERE),('outside_site',HERE),('missing_site',HERE),('soft_readback',HERE),('existing_pblock',HERE),('conflicting_LOC',HERE)]
 rows=[]
 for name,directory in cases:
  report=out/name;report.mkdir();t=load(directory,report);t.setvar('caseName',name);t.eval(FIXTURE)
  code=int(t.getvar('actualCode'));result=str(t.getvar('actualResult'));exports=t.splitlist(t.getvar('exports'))
  assert (code==0)==(name=='corrected_export'),(name,code,result)
  if name in {'original_invalid_option','corrected_export','native_export_error'}:assert len(exports)==1
  else:assert not exports,(name,exports)
  if name=='native_export_error':assert t.splitlist(t.call('dict','get',t.getvar('actualOptions'),'-errorcode'))==('CPU_XDC_NATIVE_ERROR',)
  xdc=report/'candidate_effective_physical.xdc';assert xdc.exists()==(name=='corrected_export')
  if name=='corrected_export':
   assert t.splitlist(t.getvar('ranges'))==('CLOCKREGION_X0Y4:CLOCKREGION_X0Y4','CLOCKREGION_X1Y4:CLOCKREGION_X1Y4')
   for prop in ['IS_SOFT','EXCLUDE_PLACEMENT','CONTAIN_ROUTING']:assert str(t.call('dict','get',t.getvar('assigned'),prop))=='false'
   assert t.splitlist(t.getvar('members'))==('top/a/p0','top/a/p1')
  rows.append(dict(case=name,result_code=code,result=result,export_calls=[str(x) for x in exports],passed=True,artifacts=[identity(p) for p in sorted(report.iterdir()) if p.is_file()]))
 value=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),EDA_executed=False,checks=dict(one_actual_procedure_one_option_changed=True,physical_region_and_membership_readbacks_preserved=True,native_export_errors_propagated=True,failures_before_export_not_swallowed=True,all_9_cases=True),cases=rows,source=identity(HERE/'candidate_hooks.tcl'),baseline=identity(BASE/'candidate_hooks.tcl'),fixture=identity(fixture),producer=identity(__file__),applicability='Actual constrain_region in finite Tcl native API mocks; native help separately confirms supported syntax. No full design export/place/route claimed.')
 p=out/'results.json';p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(result=identity(p),cases=len(rows),all_passed=True)))
if __name__=='__main__':main()
