"""CPU-only native-API fixtures for legal empty/unsupported property paths."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
query = (HERE / 'query.tcl').read_text()
procedures = query[query.index('proc proof_fields '):query.index('foreach cell $proof_cells')]
helper = (ROOT / 'project/hardware/vivado/scripts/m003_joint_checks.tcl').read_text()
empty_helper = helper[helper.index('proc m003::collection_property '):helper.index('proc m003::memory_startpoint_names ')]
property_helper = helper[helper.index('proc m003::prop '):helper.index('proc m003::prefix ')]
script = r'''
namespace eval m003 {}
set fixture_mode internal
proc m003::one {command name} {return $name}
proc m003::exact_count {objects n label} {if {[llength $objects] != $n} {error "$label count mismatch"}}
proc m003::jobject {row} {return $row}
proc list_property {object} {return {NAME REF_PIN_NAME DIRECTION IS_INVERTED PERIOD WAVEFORM}}
proc get_property {args} {
    if {[lindex $args 0] eq "-quiet"} {set args [lrange $args 1 end]}
    if {[llength $args] != 2} {error "unexpected property API signature"}
    lassign $args property objects
    if {![llength $objects]} {error "unexpected get_property on empty collection"}
    set values {}
    foreach object $objects {
        switch -- $property {
            NAME {lappend values $object}
            DIRECTION {lappend values [expr {$object eq "driver/Q" ? "OUT" : "IN"}]}
            REF_PIN_NAME {lappend values [file tail $object]}
            REF_NAME {lappend values FDCE}
            IS_INVERTED {lappend values 0}
            PERIOD {lappend values 10.000}
            WAVEFORM {lappend values {0.000 5.000}}
            default {error "unsupported property was not guarded"}
        }
    }
    if {[llength $values] == 1} {return [lindex $values 0]}
    return $values
}
proc get_cells {args} {return driver}
proc get_nets {args} {if {$::fixture_mode eq "no_net"} {return {}};return {net0 net0_alias}}
proc get_pins {args} {
    set filter [lindex $args end]
    if {$filter eq "DIRECTION == OUT"} {
        if {$::fixture_mode eq "primary"} {return {}}
        return driver/Q
    }
    regexp {REF_PIN_NAME == "([^"]+)"} $filter -> terminal
    return cell/$terminal
}
proc get_ports {args} {if {$::fixture_mode eq "primary"} {return top_input};return {}}
proc get_clocks {args} {
    if {$::fixture_mode eq "no_clock"} {return {}}
    if {$::fixture_mode eq "two_clocks"} {return {clock0 clock1}}
    return clock0
}
'''
with tempfile.TemporaryDirectory() as directory:
    output = Path(directory) / 'cpu_fixtures_only.txt'
    script += empty_helper + property_helper + procedures
    script += '\nset h [open {' + str(output) + '} w]\n'
    script += r'''
set fixture_mode internal
proof_pin cell D state_pin
proof_pin cell C state_pin
set fixture_mode primary
proof_pin cell D state_pin
set unsupported [proof_fields cell {NAME FOREIGN_PROPERTY}]
if {[dict get $unsupported FOREIGN_PROPERTY] ne "NOT_SUPPORTED"} {error "unsupported property lost"}
set fixture_mode no_net
if {![catch {proof_pin cell D state_pin}]} {error "required disconnected net accepted"}
set fixture_mode no_clock
if {![catch {proof_pin cell C state_pin}]} {error "required absent clock accepted"}
set fixture_mode two_clocks
if {![catch {proof_pin cell C state_pin}]} {error "nonunique clock accepted"}
close $h
puts "CPU_COLLECTOR_PROPERTY_FIXTURES_PASS cases=7 native_executed=false"
'''
    result = subprocess.run(['tclsh'], input=script, text=True, capture_output=True)
    assert result.returncode == 0 and not result.stderr and 'CPU_COLLECTOR_PROPERTY_FIXTURES_PASS' in result.stdout, result
    print(result.stdout.strip())

sys.path.insert(0, str(HERE))
from state_equivalence import actual_signal, flag
row = dict(nets='net0', drivers='driver/Q', driver_cells='driver', driver_refs='FDCE',
           primary_ports='', primary_port_directions='')
actual_signal(row)
for mutation in [dict(drivers='', driver_cells='', driver_refs=''),
                 dict(primary_ports='top_input', primary_port_directions='IN')]:
    try:
        actual_signal({**row, **mutation})
    except AssertionError:
        pass
    else:
        raise AssertionError('required exclusive actual source was accepted')
try:
    flag('NOT_SUPPORTED')
except AssertionError:
    pass
else:
    raise AssertionError('required unknown polarity was accepted')
print('CPU_REQUIRED_SOURCE_NEGATIVES_PASS cases=3 native_executed=false')
