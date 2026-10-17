#!/usr/bin/env python3
"""Execute affected native Tcl entry/callbacks under actual bundled-Python pollution."""
from datetime import datetime,timezone
import json
import argparse
import os
from pathlib import Path
import subprocess
import sys
from directed_evidence import identity,save,rows,qualify_membership
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
VENDOR=Path('/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/tps/lnx64/python-3.13.0')
BOOT='''
set ::env(PATH) [lindex $argv 1]/bin:/usr/bin:/bin
set ::env(PYTHONHOME) [lindex $argv 1]
set ::env(PYTHONPATH) [lindex $argv 1]/lib/python3.13
foreach name {PYTHONPLATLIBDIR PYTHONUSERBASE TCL_LIBRARY TK_LIBRARY LD_LIBRARY_PATH __PYVENV_LAUNCHER__} {set ::env($name) /nonexistent/vendor_pollution}
'''


def run_script(name,text,args,out):
    path=out/(name+'.tcl');path.write_text(text)
    result=subprocess.run(['tclsh',str(path),*map(str,args)],capture_output=True,text=True)
    save(out/(name+'_result.json'),dict(argv=['tclsh',str(path),*map(str,args)],returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,source=identity(path)))
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--label',default='CT011');args=parser.parse_args();assert args.label.isalnum()
    out=HERE/('CPU_checks/'+args.label+'_system_python_entry');assert not out.exists();out.mkdir(parents=True)
    checks={}
    # Real negative control: the exact installed vendor Python cannot import _tkinter.
    negative=subprocess.run([str(VENDOR/'bin/python3'),'-c','import tkinter; tkinter.Tcl()'],capture_output=True,text=True,env=dict(os.environ,LD_LIBRARY_PATH=str(VENDOR/'lib'),PYTHONHOME=str(VENDOR)))
    save(out/'vendor_negative.json',dict(returncode=negative.returncode,stdout=negative.stdout,stderr=negative.stderr,vendor_binary=identity(VENDOR/'bin/python3')))
    assert negative.returncode!=0 and '_tkinter' in negative.stderr
    checks['actual_installed_vendor_Python_missing_tkinter_reproduced']=True
    text=BOOT+'''
source [file join [lindex $argv 0] system_python.tcl]
set before [array get ::env]
set result [m002_system_python [file join [lindex $argv 0] directed_evidence.py] runtime-preflight]
set h [open [lindex $argv 2] {WRONLY CREAT EXCL}];puts $h $result;close $h
if {[array get ::env] ne $before} {error "Vivado parent environment changed"}
'''
    result=run_script('R005_actual_helper_polluted_environment',text,[HERE,VENDOR,out/'R005_runtime.json'],out)
    assert result.returncode==0,(result.stdout,result.stderr)
    value=json.loads((out/'R005_runtime.json').read_text());assert value['runtime_preflight'] and value['sanitized_python_library_environment']
    checks['actual_R005_helper_system_interpreter_Tcl_import_and_parent_env_unchanged']=True
    # Run the full actual attribution Tcl entry until intentional native-only boundary.
    work=out/'R005_full_entry';work.mkdir()
    entry=BOOT+'''
set ::env(E006_OUT) [lindex $argv 2]
set ::env(E006_DCP) CPU_TEST_NO_DCP_OPENED
set ::env(E006_TARGETS) [file join [lindex $argv 0] targets.tcl]
set ::env(E006_CANDIDATE_ADAPTER) [file join [lindex $argv 0] directed_evidence.py]
proc set_param args {}
proc open_checkpoint args {error "INTENTIONAL_NATIVE_BOUNDARY_STOP\\nsecond line\\tfield"}
source [file join [lindex $argv 0] attribution_directed.tcl]
'''
    result=run_script('R005_full_actual_entry',entry,[HERE,VENDOR,work],out)
    assert result.returncode==1 and (work/'native_system_python_preflight.json').is_file(),(result.stdout,result.stderr)
    receipts=list(rows(work/'query_receipts.tsv'));assert [row['query'] for row in receipts]==['system_python_runtime_preflight','open_checkpoint']
    assert receipts[0]['native_tcl_code']=='0' and receipts[1]['native_tcl_code']=='1'
    assert '\\n' in receipts[1]['result'] and '\\t' in receipts[1]['result'] and len((work/'query_receipts.tsv').read_text().splitlines())==3
    checks['full_R005_actual_entry_preflight_precedes_any_native_DCP_open']=True
    checks['multiline_tab_error_result_receipt_one_row_without_losing_full_error_artifact']=True
    # Source original diagnostic helpers plus complete accepted E008 hooks and its
    # actual implementation entry, executing the same Python preflight before project.
    work=out/'E008_full_entry';work.mkdir()
    script=BOOT+'''
set ::env(SLR2_REUSED_SCRIPT_DIR) [lindex $argv 3]
set ::env(SLR2_HOOKS) [file join [lindex $argv 0] E008_entry candidate_hooks.tcl]
set ::env(SLR2_ADAPTER) [file join [lindex $argv 0] E008_entry evidence_adapter.py]
set ::env(SLR2_CANDIDATE_ROOT) CPU_TEST_LITERAL_ROOT
set ::env(SLR2_CANDIDATE_ID) C01
set ::env(HAP_REPORT_DIR) [lindex $argv 2]
set ::env(HAP_PROJECT_DIR) CPU_TEST_NO_PROJECT_OPENED
set ::env(HAP_STAGE) place
set ::env(HAP_EXECUTION_MODE) checkpoint_restored_commands
proc version args {return 2025.2}
proc set_param args {}
proc open_project args {error INTENTIONAL_NATIVE_PROJECT_BOUNDARY_STOP}
set code [catch {source [file join [lindex $argv 0] E008_entry implementation.tcl]} result options]
if {$code!=1 || $result ne "INTENTIONAL_NATIVE_PROJECT_BOUNDARY_STOP"} {error "Unexpected actual E008 entry result: $code/$result"}
foreach name {m002_live_pre_place_restore m002_post} {
    set body [info body $name]
    if {[string first {exec python3} $body]>=0 || [string first {m002_system_python $::env(SLR2_ADAPTER)} $body]<0} {error "Unsanitized rewritten native helper: $name"}
}
puts E008_FULL_ACTUAL_ENTRY_PREFLIGHT_PASS
'''
    result=run_script('E008_full_actual_entry',script,[HERE,VENDOR,work,ROOT/'project/hardware/vivado/scripts'],out)
    assert result.returncode==0,(result.stdout,result.stderr)
    value=json.loads((work/'native_system_python_preflight.json').read_text());assert value['runtime_preflight'] and value['E008_full_adapter_imported']
    checks['full_E008_actual_entry_preflight_imports_complete_adapter_before_project']=True
    checks['actual_production_hooks_rewritten_all_adapter_calls_use_system_helper']=True
    # Reuse the actually closed native membership ledgers; CPU replay writes an
    # explicitly separate directory and never changes the failed native stage code.
    actual=ROOT/'project/hardware/vivado/reports/m002_E006_R005_AT002_owner_helper_repaired_directed_cut'
    replay=out/'AT002_actual_membership_system_CPU_replay';replay.mkdir();counts={}
    for point in ['C01','C02']:
        for tag in ['RAW','S','P','membership','physical_members','site_members']:
            path=actual/f'candidate_{tag}_{point}.tsv';(replay/path.name).symlink_to(path)
        path=actual/f'candidate_membership_{point}_closed.txt';(replay/path.name).symlink_to(path)
        value=qualify_membership(point,replay);counts[point]={tag:value['current'][tag]['count'] for tag in ['RAW','S','P']}
    checks['actual_AT002_native_membership_replay_with_system_Python_both_candidates_matches_R004']=True
    save(HERE/('CPU_checks/'+args.label+'_system_python_entry.json'),dict(recorded_utc=datetime.now(timezone.utc).isoformat(),EDA_executed=False,native_APIs_mocked_at_open_boundaries=True,
        checks=checks,actual_AT002_native_membership_CPU_replay=counts,original_AT002_stage_codes='FAILED_PRESERVED_NOT_CHANGED',
        source_files=[identity(HERE/name) for name in ['system_python.tcl','attribution_directed.tcl','directed_evidence.py','directed_exporter.tcl']],
        E008_source_files=[identity(HERE/'E008_entry'/name) for name in ['system_python.tcl','implementation.tcl','candidate_hooks.tcl','runtime_hooks.tcl','evidence_adapter.py','directed_evidence.py','directed_exporter.tcl']],
        system_interpreter=identity('/usr/bin/python3'),runtime_preflights=[identity(out/'R005_runtime.json'),identity(work/'native_system_python_preflight.json')],
        producer=identity(__file__),test_artifacts=[identity(path) for path in sorted(out.glob('*_result.json'))],
        limitation='Real CPU interpreter/callbacks and complete actual Tcl entries up to intentional native boundary; no actual Vivado native class/role/cut/physical qualification'))
    print(json.dumps(identity(HERE/('CPU_checks/'+args.label+'_system_python_entry.json'))))

if __name__=='__main__':main()
