#!/usr/bin/env python3
"""Execute the real source-time Tcl dependencies, including actual owner helper."""
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
from directed_evidence import identity,save
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]

def main():
    target=HERE/'CPU_checks/CT001_owner_dependency.json';target.parent.mkdir(exist_ok=True);assert not target.exists()
    original=ROOT/'agent/A006/E006_exact_candidates/candidate_inspector.tcl'
    def owner(source):
        start=source.index('proc slr2::owner name {');end=source.index('proc slr2::spatial loc {',start);return source[start:end]
    assert owner(original.read_text())==owner((HERE/'candidate_inspector.tcl').read_text())
    script='''
source [lindex $argv 0]
source [lindex $argv 1]
# No native commands or owner stub exist in this CPU interpreter.
set required {prefix slr physical ensure_cells property_values value pin_columns objects pin_class timing_boundary_selection owner spatial clock_domains domains scoped_timing readonly_resolve directed_trace directed_role directed_schema_gate directed_pin_columns directed_alias directed_local_scope directed_choose_scope retained_reason cut}
foreach name $required {if {[llength [info procs slr2::$name]]!=1} {error "Missing actual source dependency: $name"}}
set base scalellm_vcu118_f05_bd_i/core/inst/u_core/
foreach suffix {u_compute/u_mlp/x u_compute/u_attention/x u_tensor/x} expected {u_compute/u_mlp u_compute/u_attention u_tensor} {
    if {[slr2::owner ${base}${suffix}] ne "${base}${expected}"} {error "Actual owner selection differs: $suffix"}
}
foreach root {scalellm_vcu118_f05_bd_i/ddr4_0 scalellm_vcu118_f05_bd_i/ddr4_1} {
    if {[slr2::owner $root/x] ne $root} {error "Actual DDR owner selection differs"}
}
if {[slr2::owner unrelated/path/cell] ne "unrelated/path"} {error "Actual owner fallback differs"}
puts [list actual_helper_dependencies [llength $required] actual_owner_cases 6 no_native_commands_executed true]
'''
    result=subprocess.run(['tclsh','/dev/stdin',str(HERE/'candidate_inspector.tcl'),str(HERE/'directed_exporter.tcl')],input=script,text=True,capture_output=True)
    assert result.returncode==0,(result.stdout,result.stderr)
    checks=dict(exact_original_R004_pure_owner_procedure_restored=True,all_real_source_time_procedures_present_without_stubs=True,
        actual_owner_6_cases=True,no_native_or_process_control_executed=True,
        shared_exporter_unchanged=(HERE/'directed_exporter.tcl').read_bytes()==(HERE.parent/'directed_candidate_cut/directed_exporter.tcl').read_bytes(),
        shared_validator_unchanged=(HERE/'directed_evidence.py').read_bytes()==(HERE.parent/'directed_candidate_cut/directed_evidence.py').read_bytes())
    assert all(checks.values())
    save(target,dict(recorded_utc=datetime.now(timezone.utc).isoformat(),EDA_executed=False,checks=checks,stdout=result.stdout,stderr=result.stderr,
        original_owner_source=identity(original),inspector=identity(HERE/'candidate_inspector.tcl'),exporter=identity(HERE/'directed_exporter.tcl'),
        validator=identity(HERE/'directed_evidence.py'),producer=identity(__file__),
        limitation='Actual Tcl pure helper dependency check; not native readonly_resolve/get_cells/property qualification'))
    print(json.dumps(identity(target)))

if __name__=='__main__':main()
