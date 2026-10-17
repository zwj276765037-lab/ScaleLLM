#!/usr/bin/env python3
"""Pure Tcl property model counterexamples; never a native/API qualification."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent


def main():
    with tempfile.TemporaryDirectory(prefix='property_alignment_CPU_') as directory:
        audit = Path(directory) / 'audit.tsv'
        source = HERE / 'property_alignment.tcl'
        script = r'''
source {SOURCE}
set scalar [dict create A [dict create NAME A LOC {} REF_NAME VCC BEL {}] B [dict create NAME B LOC SITE_B REF_NAME FDRE BEL BEL_B] C [dict create NAME C LOC SITE_C REF_NAME FDCE BEL BEL_C]]
set mode compressed
proc get_property {quiet property objects} {
    global scalar mode
    if {$mode eq "native_error" && $property eq "LOC"} {error SIMULATED_NATIVE_QUERY_ERROR}
    set result [list]
    foreach object $objects {
        set value [dict get $scalar $object $property]
        if {$mode eq "wrong_name" && $property eq "NAME" && $object eq "A"} {set value WRONG_IDENTITY}
        if {$mode eq "empty_required" && $property eq "REF_NAME" && $object eq "A"} {set value ""}
        if {[llength $objects] > 1 && $mode ne "aligned" && $value eq ""} {continue}
        lappend result $value
    }
    if {[llength $objects]==1} {return [lindex $result 0]}
    return $result
}
set audit {AUDIT}
set result [propertyalign::values {A B C} LOC 1 mixed_empty $audit]
if {$result ne [list {} SITE_B SITE_C]} {error MIXED_EMPTY_LOST_ALIGNMENT}
set refs [propertyalign::values {A B C} REF_NAME 0 required_refs $audit]
if {$refs ne {VCC FDRE FDCE}} {error REQUIRED_REFS_CHANGED}
set mode aligned
if {[propertyalign::values {A B C} LOC 1 aligned_fast_path $audit] ne [list {} SITE_B SITE_C]} {error ALIGNED_EMPTY_NOT_PRESERVED}
set mode compressed
dict set scalar B LOC {};dict set scalar C LOC {}
if {[propertyalign::values {A B C} LOC 1 all_empty $audit] ne [list {} {} {}]} {error ALL_EMPTY_NOT_PRESERVED}
foreach mode {empty_required native_error wrong_name} {
    set property [expr {$mode eq "empty_required" ? "REF_NAME" : "LOC"}]
    if {![catch {propertyalign::values {A B C} $property [expr {$property eq "LOC"}] $mode $audit} result]} {error "FAILED_TO_REJECT_$mode"}
}
if {[propertyalign::values {} NAME 0 zero_objects $audit] ne {}} {error EMPTY_OBJECT_SET_CHANGED}
puts PASS_CPU_PROPERTY_MODEL_ONLY
'''.replace('SOURCE', str(source)).replace('AUDIT', str(audit))
        started = datetime.now(timezone.utc).isoformat()
        result = subprocess.run(['tclsh'], input=script, text=True, capture_output=True)
        ended = datetime.now(timezone.utc).isoformat()
        assert result.returncode == 0 and result.stdout.strip() == 'PASS_CPU_PROPERTY_MODEL_ONLY', (result.stdout, result.stderr)
        receipt = dict(started_utc=started, ended_utc=ended, argv=['tclsh'], stdin=script,
                       exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr,
                       audit_fixture=audit.read_text(), EDA_executed=False,
                       native_API_qualification='NOT_RUN; get_property is a deliberately compressed-empty CPU model',
                       source=dict(path=str(source), bytes=source.stat().st_size,
                                   sha256=hashlib.sha256(source.read_bytes()).hexdigest()),
                       cases=['mixed empty/nonempty optional column retains actual object positions',
                              'required REF values unchanged', 'already aligned fast path retains explicit empties',
                              'all-empty optional column retains every object', 'empty required REF rejected',
                              'native scalar query error propagated', 'wrong scalar NAME identity rejected', 'zero objects empty'])
        output = HERE / 'property_alignment_CPU_check.json'
        with output.open('x') as stream:
            stream.write(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(dict(receipt=str(output), exit_code=result.returncode,
                              EDA_executed=False, cases=len(receipt['cases']))))


if __name__ == '__main__':
    main()
