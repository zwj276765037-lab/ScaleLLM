"""Run the complete selected-pin collector against CPU native-API spies."""
from pathlib import Path
import json
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
delta = ROOT / 'project/E011_m003_joint_routability_implementation/experiment_results/runs/R003/attempts/AT001_fixed_complete_physical/evidence/place_write_address_source_delta.json'
data = json.loads(delta.read_text())
prefix = r'''
set scenario [lindex $argv 0]
set out [lindex $argv 1]
set collector [lindex $argv 2]
set props {};set groups {};set memberships {};set pinmap {};set group_driver {}
proc property {object key value} {dict set ::props $object $key $value}
proc add_group {id count driver ref} {
    set nets {}
    for {set i 0} {$i<$count} {incr i} {
        set net ${id}_$i
        lappend nets $net
        property $net NAME $net;property $net CLASS net
        dict set ::memberships $net $id
    }
    dict set ::groups $id $nets
    dict set ::group_driver $id $driver
    property $driver NAME $driver;property $driver DIRECTION OUT
    set owner [file dirname $driver]
    property $owner NAME $owner;property $owner REF_NAME $ref
}
proc bind_pin {cell pin group index} {
    if {![dict exists $::props $cell NAME]} {property $cell NAME $cell;property $cell REF_NAME URAM288}
    set name $cell/$pin
    property $name NAME $name;property $name REF_PIN_NAME $pin
    property $name DIRECTION IN;property $name IS_INVERTED 0
    set nets [dict get $::groups $group]
    dict set ::pinmap $name [lindex $nets [expr {$index%[llength $nets]}]]
}
source [file join [file dirname $collector] targets.tcl]
add_group C 12560 clock_buffer/O BUFG
add_group R 10183 reset_buffer/O BUFG
add_group E 2 ce_lut/O LUT1
foreach bit {10 11 12} {add_group D$bit 1 d_lut_$bit/O LUT6}
set index 0
foreach cell $proof_cells {
    foreach {key value} {NAME {} REF_NAME FDCE INIT 1'b0 IS_C_INVERTED 1'b0 IS_CLR_INVERTED 1'b0 IS_SEQUENTIAL 1 IS_PRIMITIVE 1 DONT_TOUCH 0} {
        if {$key eq "NAME"} {set value $cell}
        property $cell $key $value
    }
    set parent [file dirname $cell]
    property $parent NAME $parent;property $parent REF_NAME attention_fixture;property $parent DONT_TOUCH 0
    regexp {artifact_index_r_reg\[([0-9]+)\]} $cell -> bit
    bind_pin $cell D D$bit $index
    bind_pin $cell C C $index
    bind_pin $cell CE E $index
    bind_pin $cell CLR R $index
    incr index
}
property design_handle NAME fixture_design;property design_handle PART xcvu9p-flga2104-2L-e
foreach {key value} {NAME core PERIOD 10.000 WAVEFORM {0.000 5.000} IS_GENERATED 0 MASTER_CLOCK {} SOURCE_PINS clock_buffer/O} {property clock_object $key $value}
'''
for index, driver in enumerate(data['unique_drivers']):
    prefix += f'add_group Q{index} 3 {{{driver}}} FDCE\n'
for index, row in enumerate(data['failed_root_pins']):
    group = data['unique_drivers'].index(row['actual']['drivers'])
    prefix += f'bind_pin {{{row["cell"]}}} {{{row["pin"]}}} Q{group} {index}\n'
prefix += r'''
proc current_design {} {return fixture_design}
proc get_designs {} {return design_handle}
proc set_param {args} {}
proc open_checkpoint {args} {}
proc close_design {} {}
proc list_property {object} {return [dict keys [dict get $::props $object]]}
proc get_property {args} {
    if {[lindex $args 0] eq "-quiet"} {set args [lrange $args 1 end]}
    lassign $args key objects
    if {![llength $objects]} {error {get_property on empty object collection}}
    set values {}
    foreach object $objects {lappend values [dict get $::props $object $key]}
    if {[llength $objects]==1} {return [lindex $values 0]}
    return $values
}
proc get_cells {args} {
    if {[lsearch -exact $args -hier]>=0} {
        regexp {NAME == "([^"]+)"} [lindex $args end] -> name
        if {![dict exists $::props $name]} {return {}}
        return $name
    }
    return [file dirname [lindex $args end]]
}
proc get_pins {args} {
    if {[lsearch -exact $args -leaf]>=0} {
        set nets [lindex $args [expr {[lsearch -exact $args -of_objects]+1}]]
        set group [dict get $::memberships [lindex $nets 0]]
        return [dict get $::group_driver $group]
    }
    set cell [lindex $args [expr {[lsearch -exact $args -of_objects]+1}]]
    regexp {REF_PIN_NAME == "([^"]+)"} [lindex $args end] -> pin
    return $cell/$pin
}
proc get_nets {args} {
    set pin [lindex $args [expr {[lsearch -exact $args -of_objects]+1}]]
    set direct [dict get $::pinmap $pin]
    set group [dict get $::memberships $direct]
    if {[lsearch -exact $args -top_net_of_hierarchical_group]>=0} {
        if {$::scenario eq "canonical_missing"} {return {}}
        if {$::scenario eq "canonical_foreign"} {return foreign}
        return [lindex [dict get $::groups $group] 0]
    }
    if {[lsearch -exact $args -segments]>=0} {
        if {$::scenario eq "direct_omitted"} {return {}}
        return [dict get $::groups $group]
    }
    return $direct
}
proc get_ports {args} {
    if {[llength [lindex $args end]]!=1} {error {primary-port query did not use one actual canonical object}}
    if {$::scenario eq "native_port_error"} {error {native primary-port failure}}
    return {}
}
proc get_clocks {args} {
    if {$::scenario eq "clock_missing"} {return {}}
    return clock_object
}
set ::env(HAP_REPORT_DIR) $out
set ::env(HAP_QUERY_CHECKPOINT) cpu_fixture_only_not_a_native_checkpoint
set code [catch {source $collector} message options]
if {$code} {puts stderr [dict get $options -errorinfo];exit 1}
'''

results = []
for scenario in ['positive', 'canonical_missing', 'canonical_foreign', 'direct_omitted', 'native_port_error', 'clock_missing']:
    with tempfile.TemporaryDirectory() as directory:
        report = Path(directory)
        mock = report / 'mock.tcl'
        mock.write_text(prefix)
        run = subprocess.run(['tclsh', str(mock), scenario, str(report), str(HERE / 'query_cached.tcl')], text=True, capture_output=True)
        assert run.returncode == (0 if scenario == 'positive' else 1), (scenario, run.stderr)
        if scenario != 'positive':
            results.append(dict(case=scenario, rejected=True))
            continue
        rows = [json.loads(line) for line in (report / 'selected_state_and_root_pins.jsonl').read_text().splitlines()]
        kinds = {kind: sum(row['kind'] == kind for row in rows) for kind in ['cell', 'parent', 'state_pin', 'state_clock', 'memory_root_pin']}
        assert kinds == dict(cell=12, parent=12, state_pin=48, state_clock=12, memory_root_pin=24)
        selected = {row['NAME'] for row in rows if row['kind'] == 'cell'}
        assert len(selected) == 12
        state = {(row['cell'], row['terminal']): row for row in rows if row['kind'] == 'state_pin'}
        assert set(state) == {(cell, terminal) for cell in selected for terminal in ['D', 'C', 'CE', 'CLR']}
        root = {(row['cell'], row['terminal']): row for row in rows if row['kind'] == 'memory_root_pin'}
        assert set(root) == {(row['cell'], row['pin']) for row in data['failed_root_pins']}
        for key, row in state.items():
            assert row['IS_INVERTED'] == '0' and row['primary_ports'] == ''
            if key[1] == 'C':
                assert len(row['nets'].split()) == 12560 and row['drivers'] == 'clock_buffer/O'
            elif key[1] == 'CLR':
                assert len(row['nets'].split()) == 10183 and row['drivers'] == 'reset_buffer/O'
        for row in data['failed_root_pins']:
            assert root[(row['cell'], row['pin'])]['drivers'] == row['actual']['drivers']
        trace = [json.loads(line) for line in (report / 'grouped_API_trace.jsonl').read_text().splitlines()]
        begins = [row for row in trace if row['event'] == 'api_begin']
        calls = {api: sum(row['api'] == api for row in begins) for api in ['segments', 'drivers', 'canonical', 'ports']}
        assert calls == dict(segments=15, drivers=15, canonical=15, ports=15), calls
        assert all(row['input_objects'] == '1' for row in begins if row['api'] == 'ports')
        assert next(row for row in trace if row['event'] == 'call_complete')['endpoints'] == '72'
        groups = [json.loads(line) for line in (report / 'grouped_native_sources.jsonl').read_text().splitlines()]
        assert len(groups) == 15 and max(len(row['nets']) for row in groups) == 12560
        results.append(dict(case=scenario, complete_original_schema=kinds,
                            endpoints=72, groups=15, calls=calls,
                            all_primary_port_queries_one_canonical_object=True,
                            complete_12560_clock_and_10183_reset_members=True,
                            native_executed=False))
print(json.dumps(dict(passed=True, cases=results, actual_native_timing_not_measured=True), indent=2))
