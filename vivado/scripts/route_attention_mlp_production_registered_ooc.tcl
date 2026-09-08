set root [file normalize [file join [file dirname [info script]] ../..]]
set out [file normalize $::env(HAP_REPORT_DIR)]
set build [file normalize $::env(HAP_BUILD_DIR)]
set part xcvu9p-flga2104-2L-e
set top hap_attention_mlp_production_registered_ooc_harness
set harness_file [file join $root rtl integration \
    hap_attention_mlp_production_registered_ooc_harness.sv]
set xdc_file [file join $root vivado constraints \
    attention_mlp_production_registered_ooc_150_300_300.xdc]
set production_manifest [expr {[info exists ::env(HAP_PRODUCTION_MANIFEST)] ?
    [file normalize $::env(HAP_PRODUCTION_MANIFEST)] :
    [file join $root vivado manifests attention_mlp_production_v4_sources.list]}]
set place_directive [expr {[info exists ::env(HAP_PLACE_DIRECTIVE)] ?
    $::env(HAP_PLACE_DIRECTIVE) : "SSI_SpreadLogic_high"}]
set physopt_directive [expr {[info exists ::env(HAP_PHYSOPT_DIRECTIVE)] ?
    $::env(HAP_PHYSOPT_DIRECTIVE) : "AggressiveExplore"}]
set route_directive [expr {[info exists ::env(HAP_ROUTE_DIRECTIVE)] ?
    $::env(HAP_ROUTE_DIRECTIVE) : "AggressiveExplore"}]
file mkdir $out
file mkdir $build

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}

proc add_manifest {root manifest} {
    set fh [open $manifest r]
    set text [read $fh]
    close $fh
    foreach raw [split $text "\n"] {
        set line [string trim $raw]
        if {$line eq "" || [string index $line 0] eq "#"} {continue}
        set path [file normalize [file join $root $line]]
        if {![file exists $path]} {error "Missing production source $path"}
        if {[string match "*.list" $path]} {
            add_manifest $root $path
            continue
        }
        if {[llength [get_files -quiet $path]] == 0} {
            add_files -fileset sources_1 $path
        }
        if {[string match "*.sv" $path]} {
            set_property file_type SystemVerilog [get_files $path]
        }
        if {[string match "*.mem" $path]} {
            set_property file_type {Memory Initialization Files} [get_files $path]
        }
    }
}

proc require_count {label objects expected} {
    set actual [llength $objects]
    if {$actual != $expected} {
        error "$label count mismatch: expected $expected, got $actual"
    }
    return $actual
}

proc require_subset {label subset superset} {
    foreach object $subset {
        if {[lsearch -exact $superset $object] < 0} {
            error "$label contains out-of-domain object $object"
        }
    }
}

proc require_same_set {label lhs rhs} {
    set lhs_sorted [lsort -dictionary $lhs]
    set rhs_sorted [lsort -dictionary $rhs]
    if {[llength $lhs_sorted] != [llength $rhs_sorted] ||
        $lhs_sorted ne $rhs_sorted} {
        error "$label set/multiplicity mismatch"
    }
}

proc add_expected_bus {map_var signal width base stem} {
    upvar 1 $map_var result
    for {set bit 0} {$bit < $width} {incr bit} {
        set pin [expr {$width == 1 ? "u_dut/$signal" :
            [format {u_dut/%s[%d]} $signal $bit]}]
        dict set result $pin [list $stem [expr {$base + $bit}]]
    }
}

proc verify_exact_anchor_map {label expected actual} {
    set expected_keys [dict keys $expected]
    set actual_keys [dict keys $actual]
    require_same_set ${label}_dut_pin_set $actual_keys $expected_keys
    set errors {}
    foreach pin $expected_keys {
        lassign [dict get $expected $pin] stem index
        set anchor_cell [dict get $actual $pin]
        set actual_name [get_property NAME $anchor_cell]
        set expected_name [format {%s_reg[%d]} $stem $index]
        if {[llength $anchor_cell] != 1 || $actual_name ne $expected_name} {
            lappend errors "$pin:$actual_name!=$expected_name"
        }
    }
    if {[llength $errors] != 0} {
        error "$label exact packed-index mapping failed: $errors"
    }
}

proc first_slack {delay from_set to_set label} {
    set args [list -quiet -delay_type $delay -max_paths 1]
    if {[llength $from_set] != 0} {lappend args -from $from_set}
    if {[llength $to_set] != 0} {lappend args -to $to_set}
    set paths [get_timing_paths {*}$args]
    if {[llength $paths] == 0} {error "$label returned no timing path"}
    return [get_property SLACK [lindex $paths 0]]
}

proc report_pair {out stem from_set to_set} {
    set common [list -max_paths 100 -path_type full_clock_expanded]
    if {[llength $from_set] != 0} {lappend common -from $from_set}
    if {[llength $to_set] != 0} {lappend common -to $to_set}
    report_timing -delay_type max {*}$common -file \
        [file join $out ${stem}_setup_worst100.rpt]
    report_timing -delay_type min {*}$common -file \
        [file join $out ${stem}_hold_worst100.rpt]
}

proc route_row {text label {required 0}} {
    foreach line [split $text "\n"] {
        if {[string first $label $line] >= 0 &&
            [regexp {:[[:space:]]*([0-9]+)[[:space:]]*:} $line -> count]} {
            return $count
        }
    }
    if {$required} {error "Required route-status row '$label' is missing"}
    return 0
}

proc check_timing_count {text check_name} {
    set pattern [format \
        {checking[[:space:]]+%s[[:space:]]+\(([0-9]+)\)} $check_name]
    if {![regexp -nocase -- $pattern $text -> count]} {
        error "check_timing category '$check_name' is missing"
    }
    return $count
}

# Fail closed on constraint-policy drift before Vivado reads the XDC.  The
# three-domain asynchronous grouping in that file is the only clock-domain
# isolation; explicit path waivers and datapath-only delays are forbidden.
set xdc_fh [open $xdc_file r]
set xdc_text [read $xdc_fh]
close $xdc_fh
set xdc_code ""
foreach line [split $xdc_text "\n"] {
    if {![regexp {^[[:space:]]*#} $line]} {append xdc_code $line "\n"}
}
set forbidden_false_path [join {set false path} _]
set forbidden_datapath "-[join {datapath only} _]"
set clock_groups_cmd [join {set clock groups} _]
set forbidden_pattern [format {%s|%s} \
    $forbidden_false_path $forbidden_datapath]
if {[regexp -nocase -- $forbidden_pattern $xdc_code]} {
    error "Registered production OOC XDC contains a forbidden timing waiver"
}
require_count xdc_create_clock \
    [regexp -all -inline {create_clock[[:space:]]} $xdc_code] 3
set async_group_pattern [format {%s[[:space:]]+-asynchronous} \
    $clock_groups_cmd]
require_count xdc_async_group_command \
    [regexp -all -inline -- $async_group_pattern $xdc_code] 1
require_count xdc_async_group_members \
    [regexp -all -inline -- \
        {-group[[:space:]]+\[get_clocks} $xdc_code] 3

# The Tcl also owns timing exceptions after synthesis.  Audit its executable
# text so a later edit cannot add a hidden false path/datapath-only waiver or
# a second asynchronous-group policy outside the registered XDC.
set self_fh [open [file normalize [info script]] r]
set self_text [read $self_fh]
close $self_fh
set self_code ""
foreach line [split $self_text "\n"] {
    if {![regexp {^[[:space:]]*#} $line]} {append self_code $line "\n"}
}
if {[regexp -nocase -- $forbidden_pattern $self_code]} {
    error "Registered production OOC Tcl contains a forbidden timing waiver"
}
if {[regexp -nocase -- $clock_groups_cmd $self_code]} {
    error "Registered production OOC Tcl contains an extra clock-group policy"
}

create_project production_registered_ooc $build -part $part -force
set_property target_language Verilog [current_project]
set_property verilog_define {HAP_BOARD_BUILD} [get_filesets sources_1]
add_manifest $root $production_manifest
add_files -fileset sources_1 $harness_file
set_property file_type SystemVerilog [get_files $harness_file]
set_property top $top [current_fileset]
update_compile_order -fileset sources_1
read_xdc $xdc_file

set_msg_config -id {Synth 8-4445} -new_severity ERROR
set_msg_config -id {Synth 8-3848} -new_severity ERROR
set_msg_config -id {Synth 8-6901} -new_severity ERROR
set elaboration_only 0
if {[info exists ::env(HAP_ELAB_ONLY)] && $::env(HAP_ELAB_ONLY) ne "0"} {
    set elaboration_only 1
}
if {$elaboration_only} {
    synth_design -top $top -part $part -mode out_of_context -rtl \
        -flatten_hierarchy none
} else {
    synth_design -top $top -part $part -mode out_of_context \
        -flatten_hierarchy none -directive AreaOptimized_high
}

set expected_ports [lsort {
    core_clk core_rst_n ddr0_clk ddr0_rst_n ddr1_clk ddr1_rst_n
}]
set actual_ports [lsort [get_property NAME [get_ports]]]
require_same_set top_clock_reset_only $actual_ports $expected_ports

# Lightweight, non-implementing check used while a large production build is
# already running elsewhere.  RTL elaboration proves the recursive V4 graph,
# wrapper port map, vector widths, and XDC selectors without starting device
# synthesis, placement, or routing.  Exact primitive gates remain mandatory
# in every non-elaboration run below.
if {$elaboration_only} {
    set dut [get_cells -quiet u_dut]
    require_count production_dut_instance $dut 1
    set fp [open [file join $out summary.txt] w]
    foreach {key value} [list \
        tool [version -short] part $part top $top \
        production_manifest $production_manifest top_ports [llength $actual_ports] \
        functional_boundary_bits 1888 source_boundary_bits 1366 \
        sink_boundary_bits 522 timing_categories 9 \
        status PRODUCTION_REGISTERED_OOC_ELABORATION_PASS] {
        puts $fp "$key=$value"
    }
    close $fp
    puts "PRODUCTION_REGISTERED_OOC ELABORATION_PASS PORTS=[llength $actual_ports] FUNCTIONAL_BITS=1888"
    close_project
    exit 0
}

# Exact resetless boundary register counts.  Any missing bit, extra shell FF,
# wrong-domain anchor, trim, merge, or inferred extra state is a hard failure.
set core_src [get_cells -quiet -hierarchical -filter \
    {NAME =~ core_src_r_reg* && REF_NAME =~ FD*}]
set ddr0_src [get_cells -quiet -hierarchical -filter \
    {NAME =~ ddr0_src_r_reg* && REF_NAME =~ FD*}]
set ddr1_src [get_cells -quiet -hierarchical -filter \
    {NAME =~ ddr1_src_r_reg* && REF_NAME =~ FD*}]
set core_sink [get_cells -quiet -hierarchical -filter \
    {NAME =~ core_sink_r_reg* && REF_NAME =~ FD*}]
set ddr0_sink [get_cells -quiet -hierarchical -filter \
    {NAME =~ ddr0_sink_r_reg* && REF_NAME =~ FD*}]
set ddr1_sink [get_cells -quiet -hierarchical -filter \
    {NAME =~ ddr1_sink_r_reg* && REF_NAME =~ FD*}]
set core_src_count [require_count core_source_boundary $core_src 332]
set ddr0_src_count [require_count ddr0_source_boundary $ddr0_src 517]
set ddr1_src_count [require_count ddr1_source_boundary $ddr1_src 517]
set core_sink_count [require_count core_sink_boundary $core_sink 428]
set ddr0_sink_count [require_count ddr0_sink_boundary $ddr0_sink 47]
set ddr1_sink_count [require_count ddr1_sink_boundary $ddr1_sink 47]
set source_ff_count [expr {$core_src_count + $ddr0_src_count + $ddr1_src_count}]
set sink_ff_count [expr {$core_sink_count + $ddr0_sink_count + $ddr1_sink_count}]
set boundary_ff_count [expr {$source_ff_count + $sink_ff_count}]
if {$source_ff_count != 1366 || $sink_ff_count != 522 ||
    $boundary_ff_count != 1888} {
    error "Production registered OOC total boundary FF count mismatch"
}

set core_regs [all_registers -clock [get_clocks core_clk]]
set ddr0_regs [all_registers -clock [get_clocks ddr0_clk]]
set ddr1_regs [all_registers -clock [get_clocks ddr1_clk]]
require_subset core_source_clock_domain $core_src $core_regs
require_subset core_sink_clock_domain $core_sink $core_regs
require_subset ddr0_source_clock_domain $ddr0_src $ddr0_regs
require_subset ddr0_sink_clock_domain $ddr0_sink $ddr0_regs
require_subset ddr1_source_clock_domain $ddr1_src $ddr1_regs
require_subset ddr1_sink_clock_domain $ddr1_sink $ddr1_regs

set all_ff [get_cells -quiet -hierarchical -filter {REF_NAME =~ FD*}]
set dut_ff [filter $all_ff {NAME =~ u_dut/*}]
set shell_ff [filter $all_ff {NAME !~ u_dut/*}]
set boundary_ff [concat $core_src $ddr0_src $ddr1_src \
    $core_sink $ddr0_sink $ddr1_sink]
require_count shell_ff_total $shell_ff 1888
require_same_set shell_ff_are_exactly_boundary_ff $shell_ff $boundary_ff

# Connectivity gate: exact counts alone would not detect an equal-width swap
# or a duplicate DUT connection.  Every functional u_dut input pin must have
# exactly one source-boundary FF in its transitive startpoint cone, and every
# functional output pin must have exactly one sink-boundary FF in its
# transitive endpoint cone.  Clock/reset pins are separately required to have
# no proxy source/sink FF at all.
set dut_clock_reset_pins [get_pins -quiet [list \
    u_dut/core_clk u_dut/core_rst_n \
    u_dut/ddr0_clk u_dut/ddr0_rst_n \
    u_dut/ddr1_clk u_dut/ddr1_rst_n]]
require_count dut_clock_reset_pins $dut_clock_reset_pins 6
set dut_input_pins [get_pins -quiet -of_objects [get_cells u_dut] \
    -filter {DIRECTION == IN}]
set dut_output_pins [get_pins -quiet -of_objects [get_cells u_dut] \
    -filter {DIRECTION == OUT}]
set dut_functional_input_pins {}
foreach pin $dut_input_pins {
    if {[lsearch -exact $dut_clock_reset_pins $pin] < 0} {
        lappend dut_functional_input_pins $pin
    }
}
require_count dut_input_pins_total $dut_input_pins 1372
require_count dut_functional_input_pins $dut_functional_input_pins 1366
require_count dut_functional_output_pins $dut_output_pins 522

set core_functional_input_pins {}
set ddr0_functional_input_pins {}
set ddr1_functional_input_pins {}
foreach pin $dut_functional_input_pins {
    set name [get_property NAME $pin]
    if {[string match {u_dut/ddr0_axi_*} $name]} {
        lappend ddr0_functional_input_pins $pin
    } elseif {[string match {u_dut/ddr1_axi_*} $name]} {
        lappend ddr1_functional_input_pins $pin
    } else {
        lappend core_functional_input_pins $pin
    }
}
set core_functional_output_pins {}
set ddr0_functional_output_pins {}
set ddr1_functional_output_pins {}
foreach pin $dut_output_pins {
    set name [get_property NAME $pin]
    if {[string match {u_dut/ddr0_axi_*} $name]} {
        lappend ddr0_functional_output_pins $pin
    } elseif {[string match {u_dut/ddr1_axi_*} $name]} {
        lappend ddr1_functional_output_pins $pin
    } else {
        lappend core_functional_output_pins $pin
    }
}
require_count core_functional_input_pins $core_functional_input_pins 332
require_count ddr0_functional_input_pins $ddr0_functional_input_pins 517
require_count ddr1_functional_input_pins $ddr1_functional_input_pins 517
require_count core_functional_output_pins $core_functional_output_pins 428
require_count ddr0_functional_output_pins $ddr0_functional_output_pins 47
require_count ddr1_functional_output_pins $ddr1_functional_output_pins 47

set core_source_q_pins [get_pins -quiet -of_objects $core_src \
    -filter {REF_PIN_NAME == Q}]
set ddr0_source_q_pins [get_pins -quiet -of_objects $ddr0_src \
    -filter {REF_PIN_NAME == Q}]
set ddr1_source_q_pins [get_pins -quiet -of_objects $ddr1_src \
    -filter {REF_PIN_NAME == Q}]
set core_sink_d_pins [get_pins -quiet -of_objects $core_sink \
    -filter {REF_PIN_NAME == D}]
set ddr0_sink_d_pins [get_pins -quiet -of_objects $ddr0_sink \
    -filter {REF_PIN_NAME == D}]
set ddr1_sink_d_pins [get_pins -quiet -of_objects $ddr1_sink \
    -filter {REF_PIN_NAME == D}]
set source_q_pins [concat $core_source_q_pins $ddr0_source_q_pins \
    $ddr1_source_q_pins]
set sink_d_pins [concat $core_sink_d_pins $ddr0_sink_d_pins \
    $ddr1_sink_d_pins]
require_count source_boundary_q_pins $source_q_pins 1366
require_count sink_boundary_d_pins $sink_d_pins 522

# Use flat startpoint/endpoint cones so hierarchy-net segment aliases cannot
# create false mismatches.  Vivado returns a sequential startpoint pin (often
# C) or endpoint D; normalize both to the owning FF cell.  Candidate membership
# is then a dictionary lookup, so this is O(boundary pins), not O(N^2).
set core_source_set {}
set ddr0_source_set {}
set ddr1_source_set {}
foreach {pins set_name} [list \
        $core_src core_source_set \
        $ddr0_src ddr0_source_set \
        $ddr1_src ddr1_source_set] {
    foreach pin $pins {dict set $set_name $pin 1}
}
set core_sink_set {}
set ddr0_sink_set {}
set ddr1_sink_set {}
foreach {pins set_name} [list \
        $core_sink core_sink_set \
        $ddr0_sink ddr0_sink_set \
        $ddr1_sink ddr1_sink_set] {
    foreach pin $pins {dict set $set_name $pin 1}
}

set input_pin_errors {}
set used_source_q_pins {}
set actual_source_anchor_by_dut_pin {}
foreach {domain pins source_set} [list \
        core $core_functional_input_pins $core_source_set \
        ddr0 $ddr0_functional_input_pins $ddr0_source_set \
        ddr1 $ddr1_functional_input_pins $ddr1_source_set] {
    foreach pin $pins {
        set anchors {}
        foreach startpoint [all_fanin -quiet -flat -startpoints_only -to $pin] {
            set start_cell [get_cells -quiet -of_objects $startpoint]
            if {[llength $start_cell] == 1 &&
                [dict exists $source_set [lindex $start_cell 0]]} {
                lappend anchors [lindex $start_cell 0]
            }
        }
        if {[llength $anchors] != 1} {
            lappend input_pin_errors ${domain}:$pin
        } else {
            set anchor [lindex $anchors 0]
            lappend used_source_q_pins $anchor
            dict set actual_source_anchor_by_dut_pin \
                [get_property NAME $pin] $anchor
        }
    }
}
set output_pin_errors {}
set used_sink_d_pins {}
set actual_sink_anchor_by_dut_pin {}
foreach {domain pins sink_set} [list \
        core $core_functional_output_pins $core_sink_set \
        ddr0 $ddr0_functional_output_pins $ddr0_sink_set \
        ddr1 $ddr1_functional_output_pins $ddr1_sink_set] {
    foreach pin $pins {
        set anchors {}
        foreach endpoint [all_fanout -quiet -flat -endpoints_only -from $pin] {
            set end_cell [get_cells -quiet -of_objects $endpoint]
            if {[llength $end_cell] == 1 &&
                [dict exists $sink_set [lindex $end_cell 0]]} {
                lappend anchors [lindex $end_cell 0]
            }
        }
        if {[llength $anchors] != 1} {
            lappend output_pin_errors ${domain}:$pin
        } else {
            set anchor [lindex $anchors 0]
            lappend used_sink_d_pins $anchor
            dict set actual_sink_anchor_by_dut_pin \
                [get_property NAME $pin] $anchor
        }
    }
}
set clock_reset_proxy_errors {}
set all_source_set [dict merge $core_source_set \
    $ddr0_source_set $ddr1_source_set]
foreach pin $dut_clock_reset_pins {
    foreach startpoint [all_fanin -quiet -flat -startpoints_only -to $pin] {
        set start_cell [get_cells -quiet -of_objects $startpoint]
        if {[llength $start_cell] == 1 &&
            [dict exists $all_source_set [lindex $start_cell 0]]} {
            lappend clock_reset_proxy_errors $pin
            break
        }
    }
}
if {[llength $input_pin_errors] != 0 ||
    [llength $output_pin_errors] != 0 ||
    [llength $clock_reset_proxy_errors] != 0} {
    error "Production registered OOC connectivity gate failed: input=$input_pin_errors output=$output_pin_errors clock_reset=$clock_reset_proxy_errors"
}
require_same_set one_to_one_source_anchor_use $used_source_q_pins \
    [concat $core_src $ddr0_src $ddr1_src]
require_same_set one_to_one_sink_anchor_use $used_sink_d_pins \
    [concat $core_sink $ddr0_sink $ddr1_sink]

# Exact packed-vector bit mapping.  This closes the equal-width permutation
# hole left by count/bijection-only gates: every DUT port bit is bound to the
# source/sink FF index prescribed by the RTL layout, including bit order.
set expected_source_anchor_by_dut_pin {}
add_expected_bus expected_source_anchor_by_dut_pin core_clear 1 0 core_src_r
add_expected_bus expected_source_anchor_by_dut_pin ctrl_awaddr 12 1 core_src_r
add_expected_bus expected_source_anchor_by_dut_pin ctrl_awvalid 1 13 core_src_r
add_expected_bus expected_source_anchor_by_dut_pin ctrl_wdata 32 14 core_src_r
add_expected_bus expected_source_anchor_by_dut_pin ctrl_wstrb 4 46 core_src_r
add_expected_bus expected_source_anchor_by_dut_pin ctrl_wvalid 1 50 core_src_r
add_expected_bus expected_source_anchor_by_dut_pin ctrl_bready 1 51 core_src_r
add_expected_bus expected_source_anchor_by_dut_pin ctrl_araddr 12 52 core_src_r
add_expected_bus expected_source_anchor_by_dut_pin ctrl_arvalid 1 64 core_src_r
add_expected_bus expected_source_anchor_by_dut_pin ctrl_rready 1 65 core_src_r
add_expected_bus expected_source_anchor_by_dut_pin data_axi_arready 1 66 core_src_r
add_expected_bus expected_source_anchor_by_dut_pin data_axi_rvalid 1 67 core_src_r
add_expected_bus expected_source_anchor_by_dut_pin data_axi_rdata 256 68 core_src_r
add_expected_bus expected_source_anchor_by_dut_pin data_axi_rresp 2 324 core_src_r
add_expected_bus expected_source_anchor_by_dut_pin data_axi_rlast 1 326 core_src_r
add_expected_bus expected_source_anchor_by_dut_pin data_axi_awready 1 327 core_src_r
add_expected_bus expected_source_anchor_by_dut_pin data_axi_wready 1 328 core_src_r
add_expected_bus expected_source_anchor_by_dut_pin data_axi_bvalid 1 329 core_src_r
add_expected_bus expected_source_anchor_by_dut_pin data_axi_bresp 2 330 core_src_r
foreach {prefix stem} {ddr0 ddr0_src_r ddr1 ddr1_src_r} {
    add_expected_bus expected_source_anchor_by_dut_pin ${prefix}_axi_arready 1 0 $stem
    add_expected_bus expected_source_anchor_by_dut_pin ${prefix}_axi_rvalid 1 1 $stem
    add_expected_bus expected_source_anchor_by_dut_pin ${prefix}_axi_rdata 512 2 $stem
    add_expected_bus expected_source_anchor_by_dut_pin ${prefix}_axi_rresp 2 514 $stem
    add_expected_bus expected_source_anchor_by_dut_pin ${prefix}_axi_rlast 1 516 $stem
}

# Sink vector concatenations place the first-listed RTL signal at the MSB;
# the ascending bases below follow the reverse, LSB-first signal order.
set expected_sink_anchor_by_dut_pin {}
add_expected_bus expected_sink_anchor_by_dut_pin ctrl_awready 1 0 core_sink_r
add_expected_bus expected_sink_anchor_by_dut_pin ctrl_wready 1 1 core_sink_r
add_expected_bus expected_sink_anchor_by_dut_pin ctrl_bresp 2 2 core_sink_r
add_expected_bus expected_sink_anchor_by_dut_pin ctrl_bvalid 1 4 core_sink_r
add_expected_bus expected_sink_anchor_by_dut_pin ctrl_arready 1 5 core_sink_r
add_expected_bus expected_sink_anchor_by_dut_pin ctrl_rdata 32 6 core_sink_r
add_expected_bus expected_sink_anchor_by_dut_pin ctrl_rresp 2 38 core_sink_r
add_expected_bus expected_sink_anchor_by_dut_pin ctrl_rvalid 1 40 core_sink_r
add_expected_bus expected_sink_anchor_by_dut_pin data_axi_arvalid 1 41 core_sink_r
add_expected_bus expected_sink_anchor_by_dut_pin data_axi_araddr 32 42 core_sink_r
add_expected_bus expected_sink_anchor_by_dut_pin data_axi_arlen 8 74 core_sink_r
add_expected_bus expected_sink_anchor_by_dut_pin data_axi_arsize 3 82 core_sink_r
add_expected_bus expected_sink_anchor_by_dut_pin data_axi_arburst 2 85 core_sink_r
add_expected_bus expected_sink_anchor_by_dut_pin data_axi_rready 1 87 core_sink_r
add_expected_bus expected_sink_anchor_by_dut_pin data_axi_awvalid 1 88 core_sink_r
add_expected_bus expected_sink_anchor_by_dut_pin data_axi_awaddr 32 89 core_sink_r
add_expected_bus expected_sink_anchor_by_dut_pin data_axi_awlen 8 121 core_sink_r
add_expected_bus expected_sink_anchor_by_dut_pin data_axi_awsize 3 129 core_sink_r
add_expected_bus expected_sink_anchor_by_dut_pin data_axi_awburst 2 132 core_sink_r
add_expected_bus expected_sink_anchor_by_dut_pin data_axi_wvalid 1 134 core_sink_r
add_expected_bus expected_sink_anchor_by_dut_pin data_axi_wdata 256 135 core_sink_r
add_expected_bus expected_sink_anchor_by_dut_pin data_axi_wstrb 32 391 core_sink_r
add_expected_bus expected_sink_anchor_by_dut_pin data_axi_wlast 1 423 core_sink_r
add_expected_bus expected_sink_anchor_by_dut_pin data_axi_bready 1 424 core_sink_r
add_expected_bus expected_sink_anchor_by_dut_pin attention_irq 1 425 core_sink_r
add_expected_bus expected_sink_anchor_by_dut_pin mlp_irq 1 426 core_sink_r
add_expected_bus expected_sink_anchor_by_dut_pin integration_error 1 427 core_sink_r
foreach {prefix stem} {ddr0 ddr0_sink_r ddr1 ddr1_sink_r} {
    add_expected_bus expected_sink_anchor_by_dut_pin ${prefix}_axi_arvalid 1 0 $stem
    add_expected_bus expected_sink_anchor_by_dut_pin ${prefix}_axi_araddr 32 1 $stem
    add_expected_bus expected_sink_anchor_by_dut_pin ${prefix}_axi_arlen 8 33 $stem
    add_expected_bus expected_sink_anchor_by_dut_pin ${prefix}_axi_arsize 3 41 $stem
    add_expected_bus expected_sink_anchor_by_dut_pin ${prefix}_axi_arburst 2 44 $stem
    add_expected_bus expected_sink_anchor_by_dut_pin ${prefix}_axi_rready 1 46 $stem
}
verify_exact_anchor_map source_boundary $expected_source_anchor_by_dut_pin \
    $actual_source_anchor_by_dut_pin
verify_exact_anchor_map sink_boundary $expected_sink_anchor_by_dut_pin \
    $actual_sink_anchor_by_dut_pin

set core_dut_regs [filter $core_regs {NAME =~ u_dut/*}]
set ddr0_dut_regs [filter $ddr0_regs {NAME =~ u_dut/*}]
set ddr1_dut_regs [filter $ddr1_regs {NAME =~ u_dut/*}]
if {[llength $core_dut_regs] == 0 || [llength $ddr0_dut_regs] == 0 ||
    [llength $ddr1_dut_regs] == 0} {
    error "One or more production DUT clock domains contain no sequential cell"
}

# Hard-resource production contract plus tightly bounded proxy overhead.
set dsp [llength [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}]]
set uram [llength [get_cells -quiet -hierarchical -filter {REF_NAME == URAM288}]]
set kernel_dsp [llength [get_cells -quiet -hierarchical -filter {
    REF_NAME == DSP48E2 &&
    NAME =~ u_dut/u_compute/u_mlp/u_serial_command/u_shared_compute/*
}]]
set kernels [llength [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_a8w4_slice8x16_group_s36 ||
    REF_NAME == hap_a8w4_slice8x16_group_s36
}]]
set shell_lut [get_cells -quiet -hierarchical -filter {
    REF_NAME =~ LUT* && NAME !~ u_dut/*
}]
set shell_lut_count [llength $shell_lut]
if {$dsp != 6492 || $uram != 752 || $kernel_dsp != 4096 || $kernels != 2} {
    error "Production hard-resource gate failed: DSP=$dsp URAM=$uram kernel_DSP=$kernel_dsp kernels=$kernels"
}
if {$shell_lut_count > 16} {
    error "Registered proxy inferred unreasonable shell LUT overhead: $shell_lut_count > 16"
}
set util_text [report_utilization -return_string]
if {![regexp {\| CLB LUTs\*?\s+\|\s*([0-9]+)} $util_text unused clb_lut]} {
    error "CLB LUT utilization parse failed"
}
if {![regexp {\| CLB Registers\s+\|\s*([0-9]+)} $util_text unused clb_ff]} {
    error "CLB FF utilization parse failed"
}
# Existing production ceiling is 1,064,016 CLB LUTs.  The same recirculating
# harness pattern has synthesized to only a few top-level LUTs because the
# invert/shift is absorbed into FF controls; permit 16 proxy LUTs as a narrow
# fail-closed allowance.  The 1,888 shell FFs remain exact above.
if {$clb_lut > 1064032} {
    error "Registered production CLB LUT ceiling exceeded: $clb_lut"
}

# Nine exact timing categories.  Capture/launch sets include the opposite
# boundary anchor so a legal combinational feed-through is still charged the
# shell budget instead of silently receiving a full clock period.
set core_capture [concat $core_dut_regs $core_sink]
set ddr0_capture [concat $ddr0_dut_regs $ddr0_sink]
set ddr1_capture [concat $ddr1_dut_regs $ddr1_sink]
set core_launch [concat $core_dut_regs $core_src]
set ddr0_launch [concat $ddr0_dut_regs $ddr0_src]
set ddr1_launch [concat $ddr1_dut_regs $ddr1_src]

set_max_delay 5.666 -from $core_src -to $core_capture
set_min_delay 0.000 -from $core_src -to $core_capture
set_max_delay 2.533 -from $ddr0_src -to $ddr0_capture
set_min_delay 0.000 -from $ddr0_src -to $ddr0_capture
set_max_delay 2.533 -from $ddr1_src -to $ddr1_capture
set_min_delay 0.000 -from $ddr1_src -to $ddr1_capture
set_max_delay 5.666 -from $core_launch -to $core_sink
set_min_delay 0.000 -from $core_launch -to $core_sink
set_max_delay 2.533 -from $ddr0_launch -to $ddr0_sink
set_min_delay 0.000 -from $ddr0_launch -to $ddr0_sink
set_max_delay 2.533 -from $ddr1_launch -to $ddr1_sink
set_min_delay 0.000 -from $ddr1_launch -to $ddr1_sink

set timing_categories [list \
    core_internal $core_dut_regs $core_dut_regs \
    ddr0_internal $ddr0_dut_regs $ddr0_dut_regs \
    ddr1_internal $ddr1_dut_regs $ddr1_dut_regs \
    core_boundary_in $core_src $core_capture \
    ddr0_boundary_in $ddr0_src $ddr0_capture \
    ddr1_boundary_in $ddr1_src $ddr1_capture \
    core_boundary_out $core_launch $core_sink \
    ddr0_boundary_out $ddr0_launch $ddr0_sink \
    ddr1_boundary_out $ddr1_launch $ddr1_sink]
require_count timing_category_fields $timing_categories 27
foreach {label from_set to_set} $timing_categories {
    first_slack max $from_set $to_set ${label}_setup_nonempty
    first_slack min $from_set $to_set ${label}_hold_nonempty
}

report_utilization -hierarchical -hierarchical_depth 9 -file \
    [file join $out utilization_post_synth.rpt]
report_exceptions -coverage -file [file join $out exceptions_coverage.rpt]
set exceptions_fh [open [file join $out exceptions_coverage.rpt] r]
set exceptions_text [read $exceptions_fh]
close $exceptions_fh
set max_delay_rows [regexp -all -line {^[[:space:]]*[0-9]+[[:space:]]+Max Delay[[:space:]]} \
    $exceptions_text]
set min_delay_rows [regexp -all -line {^[[:space:]]*[0-9]+[[:space:]]+Min Delay[[:space:]]} \
    $exceptions_text]
set false_path_rows [regexp -all -line {^[[:space:]]*[0-9]+[[:space:]]+False Path[[:space:]]} \
    $exceptions_text]
if {$max_delay_rows != 6 || $min_delay_rows != 6 ||
    $false_path_rows != 0} {
    error "Registered production OOC exception coverage mismatch: max=$max_delay_rows min=$min_delay_rows false_path=$false_path_rows"
}
report_clock_interaction -delay_type min_max -file \
    [file join $out clock_interaction_post_synth.rpt]
write_checkpoint -force [file join $out post_synth.dcp]

set synth_timing_text [report_timing_summary -delay_type min_max -max_paths 10 \
    -report_unconstrained -warn_on_violation -return_string]
set synth_no_clock [check_timing_count $synth_timing_text no_clock]
set synth_unconstrained [check_timing_count $synth_timing_text \
    unconstrained_internal_endpoints]
set synth_no_input_delay [check_timing_count $synth_timing_text no_input_delay]
set synth_no_output_delay [check_timing_count $synth_timing_text no_output_delay]
set synth_partial_input_delay [check_timing_count $synth_timing_text \
    partial_input_delay]
set synth_partial_output_delay [check_timing_count $synth_timing_text \
    partial_output_delay]
set synth_timing_coverage_ok [expr {$synth_no_clock == 0 &&
    $synth_unconstrained == 0 && $synth_no_input_delay == 3 &&
    $synth_no_output_delay == 0 && $synth_partial_input_delay == 0 &&
    $synth_partial_output_delay == 0}]
if {!$synth_timing_coverage_ok} {
    error "Registered production OOC post-synth timing coverage gate failed"
}

set synth_only 0
if {[info exists ::env(HAP_SYNTH_ONLY)] && $::env(HAP_SYNTH_ONLY) ne "0"} {
    set synth_only 1
}

set place_only 0
if {[info exists ::env(HAP_PLACE_ONLY)] && $::env(HAP_PLACE_ONLY) ne "0"} {
    set place_only 1
}
if {$synth_only} {
    set fp [open [file join $out summary.txt] w]
    foreach {key value} [list \
        tool [version -short] part $part top $top \
        production_manifest $production_manifest \
        place_directive $place_directive physopt_directive $physopt_directive \
        route_directive $route_directive \
        core_clock_mhz 150 ddr0_clock_mhz 300 ddr1_clock_mhz 300 \
        core_io_budget_ns 1.000 ddr_io_budget_ns 0.800 \
        core_source_boundary_ff $core_src_count \
        ddr0_source_boundary_ff $ddr0_src_count \
        ddr1_source_boundary_ff $ddr1_src_count \
        core_sink_boundary_ff $core_sink_count \
        ddr0_sink_boundary_ff $ddr0_sink_count \
        ddr1_sink_boundary_ff $ddr1_sink_count \
        source_boundary_ff_total $source_ff_count \
        sink_boundary_ff_total $sink_ff_count \
        boundary_ff_total $boundary_ff_count \
        shell_ff_total [llength $shell_ff] shell_lut_primitives $shell_lut_count \
        core_dut_sequential [llength $core_dut_regs] \
        ddr0_dut_sequential [llength $ddr0_dut_regs] \
        ddr1_dut_sequential [llength $ddr1_dut_regs] \
        timing_categories 9 dsp48e2 $dsp uram288 $uram \
        mlp_kernel_instances $kernels mlp_kernel_dsp48e2 $kernel_dsp \
        clb_lut $clb_lut clb_register $clb_ff \
        no_clock_endpoints $synth_no_clock \
        unconstrained_internal_endpoints $synth_unconstrained \
        no_input_delay_ports $synth_no_input_delay \
        no_output_delay_ports $synth_no_output_delay \
        partial_input_delay_ports $synth_partial_input_delay \
        partial_output_delay_ports $synth_partial_output_delay \
        timing_coverage_ok $synth_timing_coverage_ok \
        max_delay_exception_rows $max_delay_rows \
        min_delay_exception_rows $min_delay_rows \
        false_path_exception_rows $false_path_rows \
        status PRODUCTION_REGISTERED_OOC_SYNTH_PASS] {
        puts $fp "$key=$value"
    }
    close $fp
    puts "PRODUCTION_REGISTERED_OOC SYNTH_ONLY_PASS BOUNDARY_FF=$boundary_ff_count DSP=$dsp URAM=$uram KERNEL_DSP=$kernel_dsp"
    close_project
    exit 0
}

# Preserve the signed production physical partition under the wrapper's
# u_dut/ hierarchy.  This is intentionally duplicated in this standalone
# proxy flow so the production placement script and manifest stay untouched.
set slice_roots [lsort -dictionary [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME =~ hap_mlp_shared_slice8x16_s43_s45* ||
    REF_NAME =~ hap_mlp_shared_slice8x16_s43_s45*
}]]
require_count mlp_slice_roots $slice_roots 2
set slice0_root [lindex $slice_roots 0]
set slice1_root [lindex $slice_roots 1]
create_pblock pb_mlp_slice0_slr0
add_cells_to_pblock [get_pblocks pb_mlp_slice0_slr0] \
    [get_cells -quiet -hierarchical -filter "NAME =~ $slice0_root/*"]
resize_pblock [get_pblocks pb_mlp_slice0_slr0] -add {SLR0}
set_property IS_SOFT false [get_pblocks pb_mlp_slice0_slr0]
create_pblock pb_mlp_slice1_slr2
add_cells_to_pblock [get_pblocks pb_mlp_slice1_slr2] \
    [get_cells -quiet -hierarchical -filter "NAME =~ $slice1_root/*"]
resize_pblock [get_pblocks pb_mlp_slice1_slr2] -add {SLR2}
set_property IS_SOFT false [get_pblocks pb_mlp_slice1_slr2]

set gate_bank0 [get_cells -quiet u_dut/u_meta_bank/u_gate_bank0]
set gate_bank1 [get_cells -quiet u_dut/u_meta_bank/u_gate_bank1]
set down_bank0 [get_cells -quiet u_dut/u_meta_bank/u_down_bank0]
set down_bank1 [get_cells -quiet u_dut/u_meta_bank/u_down_bank1]
require_count metadata_gate_bank0_root $gate_bank0 1
require_count metadata_gate_bank1_root $gate_bank1 1
require_count metadata_down_bank0_root $down_bank0 1
require_count metadata_down_bank1_root $down_bank1 1
create_pblock pb_meta_gate_bank0_slr0
add_cells_to_pblock [get_pblocks pb_meta_gate_bank0_slr0] \
    [get_cells -quiet -hierarchical -filter "NAME =~ $gate_bank0/*"]
resize_pblock [get_pblocks pb_meta_gate_bank0_slr0] -add {SLR0}
set_property IS_SOFT false [get_pblocks pb_meta_gate_bank0_slr0]
create_pblock pb_meta_gate_bank1_slr2
add_cells_to_pblock [get_pblocks pb_meta_gate_bank1_slr2] \
    [get_cells -quiet -hierarchical -filter "NAME =~ $gate_bank1/*"]
resize_pblock [get_pblocks pb_meta_gate_bank1_slr2] -add {SLR2}
set_property IS_SOFT false [get_pblocks pb_meta_gate_bank1_slr2]
create_pblock pb_meta_down_banks_slr1
add_cells_to_pblock [get_pblocks pb_meta_down_banks_slr1] [concat \
    [get_cells -quiet -hierarchical -filter "NAME =~ $down_bank0/*"] \
    [get_cells -quiet -hierarchical -filter "NAME =~ $down_bank1/*"]]
resize_pblock [get_pblocks pb_meta_down_banks_slr1] -add {SLR1}
set_property IS_SOFT false [get_pblocks pb_meta_down_banks_slr1]

set projection_array \
    u_dut/u_compute/u_attention/u_compute/u_projection/u_array
set projection_lane_slr0 [get_cells -quiet [list \
    ${projection_array}/g_row\[0\].g_col\[0\].u_lane \
    ${projection_array}/g_row\[0\].g_col\[1\].u_lane \
    ${projection_array}/g_row\[0\].g_col\[2\].u_lane \
    ${projection_array}/g_row\[0\].g_col\[3\].u_lane \
    ${projection_array}/g_row\[0\].g_col\[4\].u_lane \
    ${projection_array}/g_row\[0\].g_col\[5\].u_lane \
    ${projection_array}/g_row\[0\].g_col\[6\].u_lane \
    ${projection_array}/g_row\[0\].g_col\[7\].u_lane]]
set projection_lane_slr2 [get_cells -quiet [list \
    ${projection_array}/g_row\[7\].g_col\[13\].u_lane \
    ${projection_array}/g_row\[7\].g_col\[14\].u_lane \
    ${projection_array}/g_row\[7\].g_col\[15\].u_lane]]
require_count projection_slr0_lane_roots $projection_lane_slr0 8
require_count projection_slr2_lane_roots $projection_lane_slr2 3
set projection_lane_slr0_cells {}
foreach lane $projection_lane_slr0 {
    set projection_lane_slr0_cells [concat $projection_lane_slr0_cells \
        [get_cells -quiet -hierarchical -filter "NAME =~ $lane/*"]]
}
set projection_lane_slr2_cells {}
foreach lane $projection_lane_slr2 {
    set projection_lane_slr2_cells [concat $projection_lane_slr2_cells \
        [get_cells -quiet -hierarchical -filter "NAME =~ $lane/*"]]
}
create_pblock pb_attention_projection_lanes_slr0
add_cells_to_pblock [get_pblocks pb_attention_projection_lanes_slr0] \
    $projection_lane_slr0_cells
resize_pblock [get_pblocks pb_attention_projection_lanes_slr0] -add {SLR0}
set_property IS_SOFT false [get_pblocks pb_attention_projection_lanes_slr0]
create_pblock pb_attention_projection_lanes_slr2
add_cells_to_pblock [get_pblocks pb_attention_projection_lanes_slr2] \
    $projection_lane_slr2_cells
resize_pblock [get_pblocks pb_attention_projection_lanes_slr2] -add {SLR2}
set_property IS_SOFT false [get_pblocks pb_attention_projection_lanes_slr2]

opt_design -directive ExploreWithRemap
report_drc -file [file join $out drc_pre_place.rpt]
set pre_place_drc_errors [llength [get_drc_violations -quiet -filter {
    SEVERITY == Error
}]]
if {$pre_place_drc_errors != 0} {
    error "Registered production OOC pre-place DRC has $pre_place_drc_errors errors"
}

place_design -directive $place_directive
write_checkpoint -force [file join $out post_place.dcp]
report_timing_summary -delay_type min_max -max_paths 100 -file \
    [file join $out timing_post_place.rpt]
report_utilization -slr -file [file join $out utilization_slr_post_place.rpt]
report_design_analysis -congestion -file \
    [file join $out congestion_post_place.rpt]
set place_setup [first_slack max {} {} post_place_global_setup]
set place_hold [first_slack min {} {} post_place_global_hold]
if {$place_only} {
    set fp [open [file join $out summary.txt] w]
    foreach {key value} [list \
        tool [version -short] part $part top $top \
        production_manifest $production_manifest \
        place_directive $place_directive \
        post_place_wns_ns $place_setup post_place_whs_ns $place_hold \
        pre_place_drc_errors $pre_place_drc_errors \
        boundary_ff_total $boundary_ff_count dsp48e2 $dsp uram288 $uram \
        mlp_kernel_dsp48e2 $kernel_dsp \
        status PRODUCTION_REGISTERED_OOC_PLACE_COMPLETE_TIMING_NOT_SIGNED] {
        puts $fp "$key=$value"
    }
    close $fp
    puts "PRODUCTION_REGISTERED_OOC PLACE_ONLY_COMPLETE WNS=$place_setup WHS=$place_hold"
    close_project
    exit 0
}

phys_opt_design -directive $physopt_directive
route_design -directive $route_directive

report_timing_summary -delay_type min_max -max_paths 100 -file \
    [file join $out timing_summary.rpt]
foreach {label from_set to_set} $timing_categories {
    report_pair $out $label $from_set $to_set
}
report_utilization -hierarchical -hierarchical_depth 9 -file \
    [file join $out utilization_hier.rpt]
report_utilization -slr -file [file join $out utilization_slr.rpt]
set route_text [report_route_status -return_string]
report_route_status -file [file join $out route_status.rpt]
report_drc -file [file join $out drc.rpt]
report_cdc -details -file [file join $out cdc.rpt]
report_clock_interaction -delay_type min_max -file \
    [file join $out clock_interaction.rpt]
report_methodology -file [file join $out methodology.rpt]
report_design_analysis -congestion -file [file join $out congestion.rpt]
write_checkpoint -force [file join $out post_route.dcp]

set timing_text [report_timing_summary -delay_type min_max -max_paths 100 \
    -report_unconstrained -warn_on_violation -return_string]
set timing_fh [open [file join $out timing_summary_coverage.rpt] w]
puts -nonewline $timing_fh $timing_text
close $timing_fh

set wns [first_slack max {} {} global_setup]
set whs [first_slack min {} {} global_hold]
set category_slacks {}
set all_category_timing_ok 1
foreach {label from_set to_set} $timing_categories {
    set setup [first_slack max $from_set $to_set ${label}_wns]
    set hold [first_slack min $from_set $to_set ${label}_whs]
    lappend category_slacks ${label}_wns_ns $setup ${label}_whs_ns $hold
    if {$setup < 0.0 || $hold < 0.0} {set all_category_timing_ok 0}
}

set route_errors [route_row $route_text "# of nets with routing errors" 1]
set explicit_gaps [route_row $route_text "# of nets with explicit gaps"]
set unrouted_rows [route_row $route_text "# of unrouted nets"]
set unrouted_pins [route_row $route_text "# of nets with some unrouted pins"]
set resource_conflicts [route_row $route_text "# of nets with resource conflicts"]
set antennas [route_row $route_text "# of nets with antennas/islands"]

# Narrowly recognize the unavoidable OOC aliases: exactly three clock roots
# may be PARTIAL and exactly three reset roots may be zero-node HIERPORT gaps.
set allowed_ooc_clocks [lsort {core_clk ddr0_clk ddr1_clk}]
set allowed_ooc_resets [lsort {core_rst_n ddr0_rst_n ddr1_rst_n}]
set partial_all [get_nets -quiet -hierarchical -filter {
    ROUTE_STATUS == PARTIAL || ROUTE_STATUS == PARTIALLY_ROUTED ||
    ROUTE_STATUS == UNROUTED
}]
set bad_partial {}
set partial_parents {}
foreach net $partial_all {
    set parent [get_property PARENT $net]
    set type [get_property TYPE $net]
    set ports [lsort -unique [get_property NAME \
        [get_ports -quiet -of_objects $net]]]
    if {$type eq "LOCAL_CLOCK" &&
        [lsearch -exact $allowed_ooc_clocks $parent] >= 0 &&
        [llength $ports] == 1 && [lindex $ports 0] eq $parent} {
        lappend partial_parents $parent
    } else {
        lappend bad_partial $net
    }
}
set partial_clock_roots [lsort -unique $partial_parents]
set clock_alias_ok [expr {[llength $partial_all] > 0 &&
    $partial_clock_roots eq $allowed_ooc_clocks &&
    [llength $bad_partial] == 0}]

set hierport_all [get_nets -quiet -hierarchical -filter {ROUTE_STATUS == HIERPORT}]
set bad_hierport {}
set hierport_roots {}
foreach net $hierport_all {
    set parent [get_property PARENT $net]
    if {[lsearch -exact $allowed_ooc_resets $parent] < 0 ||
        [llength [get_nodes -quiet -of_objects $net]] != 0} {
        lappend bad_hierport $net
    } else {
        lappend hierport_roots $parent
    }
}
set reset_roots [lsort -unique $hierport_roots]
set reset_gap_ok [expr {$explicit_gaps == 3 &&
    $reset_roots eq $allowed_ooc_resets && [llength $bad_hierport] == 0}]
foreach reset $allowed_ooc_resets {
    set reset_net [get_nets -quiet $reset]
    set reset_port [get_ports -quiet $reset]
    if {[llength $reset_net] != 1 || [llength $reset_port] != 1 ||
        [get_property ROUTE_STATUS $reset_net] ne "HIERPORT" ||
        [llength [get_nodes -quiet -of_objects $reset_net]] != 0} {
        set reset_gap_ok 0
    }
}

set route35198_ports {}
set log_path [file join $out vivado.log]
if {[file exists $log_path]} {
    set log_fh [open $log_path r]
    set log_text [read $log_fh]
    close $log_fh
    foreach line [split $log_text "\n"] {
        if {[regexp {WARNING: \[Route 35-198\] Port "([^"]+)" does not have an associated HD\.PARTPIN_LOCS} $line -> port]} {
            lappend route35198_ports $port
        }
    }
}
set route35198_ok [expr {[lsort -unique $route35198_ports] eq $allowed_ooc_resets}]
set reset_gap_ok [expr {$reset_gap_ok && $route35198_ok}]

set conflict_status [llength [get_nets -quiet -hierarchical -filter {
    ROUTE_STATUS == CONFLICTS
}]]
set drc_errors [llength [get_drc_violations -quiet -filter {SEVERITY == Error}]]
set cdc_fh [open [file join $out cdc.rpt] r]
set cdc_text [read $cdc_fh]
close $cdc_fh
set cdc_critical 0
foreach {whole count} [regexp -all -inline \
        {Critical[[:space:]]+([1-9][0-9]*)} $cdc_text] {
    incr cdc_critical $count
}
set no_clock [check_timing_count $timing_text no_clock]
set unconstrained [check_timing_count $timing_text \
    unconstrained_internal_endpoints]
set no_input_delay [check_timing_count $timing_text no_input_delay]
set no_output_delay [check_timing_count $timing_text no_output_delay]
set partial_input_delay [check_timing_count $timing_text partial_input_delay]
set partial_output_delay [check_timing_count $timing_text partial_output_delay]
set timing_coverage_ok [expr {$no_clock == 0 && $unconstrained == 0 &&
    $no_input_delay == 3 && $no_output_delay == 0 &&
    $partial_input_delay == 0 && $partial_output_delay == 0}]

# Re-audit all signed resource and shell counts in the final routed design.
set final_dsp [llength [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}]]
set final_uram [llength [get_cells -quiet -hierarchical -filter {REF_NAME == URAM288}]]
set final_kernel_dsp [llength [get_cells -quiet -hierarchical -filter {
    REF_NAME == DSP48E2 &&
    NAME =~ u_dut/u_compute/u_mlp/u_serial_command/u_shared_compute/*
}]]
set final_shell_ff [get_cells -quiet -hierarchical -filter {
    REF_NAME =~ FD* && NAME !~ u_dut/*
}]
set final_shell_lut [get_cells -quiet -hierarchical -filter {
    REF_NAME =~ LUT* && NAME !~ u_dut/*
}]
set resource_ok [expr {$final_dsp == 6492 && $final_uram == 752 &&
    $final_kernel_dsp == 4096 && [llength $final_shell_ff] == 1888 &&
    [llength $final_shell_lut] <= 16}]

# Post-route physical-contract audit.  The exact hard blocks are necessary but
# not sufficient: every primitive in each MLP slice, every metadata cascade,
# and the eleven congestion-relief projection lanes must remain in its signed
# SLR after physical optimization.
set post_unplaced [llength [get_cells -quiet -hierarchical -filter {
    IS_PRIMITIVE && !IS_PLACED
}]]
set slice0_primitive_wrong 0
set post_slice_roots [lsort -dictionary [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME =~ hap_mlp_shared_slice8x16_s43_s45* ||
    REF_NAME =~ hap_mlp_shared_slice8x16_s43_s45*
}]]
set post_slice_root_count [llength $post_slice_roots]
set post_slice0_root [expr {$post_slice_root_count == 2 ?
    [lindex $post_slice_roots 0] : ""}]
set post_slice1_root [expr {$post_slice_root_count == 2 ?
    [lindex $post_slice_roots 1] : ""}]
set slice1_primitive_wrong 0
set slice0_dsp {}
set slice1_dsp {}
if {$post_slice_root_count == 2} {
    set slice0_dsp [get_cells -quiet -hierarchical -filter \
        "REF_NAME == DSP48E2 && NAME =~ $post_slice0_root/*"]
    set slice1_dsp [get_cells -quiet -hierarchical -filter \
        "REF_NAME == DSP48E2 && NAME =~ $post_slice1_root/*"]
    foreach cell [get_cells -quiet -hierarchical -filter \
            "IS_PRIMITIVE && NAME =~ $post_slice0_root/*"] {
        set index [get_property SLR_INDEX $cell]
        if {$index ne "" && $index != 0} {incr slice0_primitive_wrong}
    }
    foreach cell [get_cells -quiet -hierarchical -filter \
            "IS_PRIMITIVE && NAME =~ $post_slice1_root/*"] {
        set index [get_property SLR_INDEX $cell]
        if {$index ne "" && $index != 2} {incr slice1_primitive_wrong}
    }
}

set gate0_uram [get_cells -quiet -hierarchical -filter \
    "REF_NAME == URAM288 && NAME =~ $gate_bank0/*"]
set gate1_uram [get_cells -quiet -hierarchical -filter \
    "REF_NAME == URAM288 && NAME =~ $gate_bank1/*"]
set down0_uram [get_cells -quiet -hierarchical -filter \
    "REF_NAME == URAM288 && NAME =~ $down_bank0/*"]
set down1_uram [get_cells -quiet -hierarchical -filter \
    "REF_NAME == URAM288 && NAME =~ $down_bank1/*"]
set metadata_uram_wrong 0
foreach cell $gate0_uram {
    if {[get_property SLR_INDEX $cell] != 0} {incr metadata_uram_wrong}
}
foreach cell $gate1_uram {
    if {[get_property SLR_INDEX $cell] != 2} {incr metadata_uram_wrong}
}
foreach cell [concat $down0_uram $down1_uram] {
    if {[get_property SLR_INDEX $cell] != 1} {incr metadata_uram_wrong}
}

set projection_slr0_dsp {}
set projection_slr2_dsp {}
set projection_slr0_primitive_wrong 0
set projection_slr2_primitive_wrong 0
foreach lane $projection_lane_slr0 {
    set projection_slr0_dsp [concat $projection_slr0_dsp \
        [get_cells -quiet -hierarchical -filter \
            "REF_NAME == DSP48E2 && NAME =~ $lane/*"]]
    foreach cell [get_cells -quiet -hierarchical -filter \
            "IS_PRIMITIVE && NAME =~ $lane/*"] {
        set index [get_property SLR_INDEX $cell]
        if {$index ne "" && $index != 0} {
            incr projection_slr0_primitive_wrong
        }
    }
}
foreach lane $projection_lane_slr2 {
    set projection_slr2_dsp [concat $projection_slr2_dsp \
        [get_cells -quiet -hierarchical -filter \
            "REF_NAME == DSP48E2 && NAME =~ $lane/*"]]
    foreach cell [get_cells -quiet -hierarchical -filter \
            "IS_PRIMITIVE && NAME =~ $lane/*"] {
        set index [get_property SLR_INDEX $cell]
        if {$index ne "" && $index != 2} {
            incr projection_slr2_primitive_wrong
        }
    }
}
set projection_slr0_dsp_wrong 0
foreach cell $projection_slr0_dsp {
    if {[get_property SLR_INDEX $cell] != 0} {incr projection_slr0_dsp_wrong}
}
set projection_slr2_dsp_wrong 0
foreach cell $projection_slr2_dsp {
    if {[get_property SLR_INDEX $cell] != 2} {incr projection_slr2_dsp_wrong}
}

set slr_dsp {0 0 0}
foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}] {
    set index [get_property SLR_INDEX $cell]
    if {$index < 0 || $index > 2} {error "Illegal DSP SLR index $index"}
    lset slr_dsp $index [expr {[lindex $slr_dsp $index] + 1}]
}
set physical_ok [expr {$post_unplaced == 0 &&
    $post_slice_root_count == 2 &&
    [llength $slice0_dsp] == 2048 && [llength $slice1_dsp] == 2048 &&
    $slice0_primitive_wrong == 0 && $slice1_primitive_wrong == 0 &&
    [llength $gate0_uram] == 224 && [llength $gate1_uram] == 224 &&
    [llength $down0_uram] == 112 && [llength $down1_uram] == 112 &&
    $metadata_uram_wrong == 0 &&
    [llength $projection_slr0_dsp] == 136 &&
    [llength $projection_slr2_dsp] == 51 &&
    $projection_slr0_dsp_wrong == 0 && $projection_slr2_dsp_wrong == 0 &&
    $projection_slr0_primitive_wrong == 0 &&
    $projection_slr2_primitive_wrong == 0 &&
    [lindex $slr_dsp 0] <= 2200 && [lindex $slr_dsp 1] <= 2200 &&
    [lindex $slr_dsp 2] <= 2200}]
set route_clean [expr {$route_errors == 0 && $unrouted_rows == 0 &&
    $unrouted_pins == 0 && $resource_conflicts == 0 && $antennas == 0 &&
    $conflict_status == 0 && $clock_alias_ok && $reset_gap_ok}]
set all_timing_ok [expr {$wns >= 0.0 && $whs >= 0.0 &&
    $all_category_timing_ok}]
set status [expr {$all_timing_ok && $route_clean && $resource_ok &&
    $physical_ok && $timing_coverage_ok && $drc_errors == 0 &&
    $cdc_critical == 0 ?
    "PRODUCTION_REGISTERED_OOC_PROXY_PASS_EXPECTED_RESET_PARTPIN_GAPS" :
    "PRODUCTION_REGISTERED_OOC_POST_ROUTE_FAIL"}]

set fp [open [file join $out summary.txt] w]
foreach {key value} [concat [list \
    tool [version -short] part $part top $top \
    production_manifest $production_manifest \
    place_directive $place_directive physopt_directive $physopt_directive \
    route_directive $route_directive \
    core_clock_mhz 150 ddr0_clock_mhz 300 ddr1_clock_mhz 300 \
    core_io_budget_ns 1.000 ddr_io_budget_ns 0.800 \
    wns_ns $wns whs_ns $whs] $category_slacks [list \
    core_source_boundary_ff $core_src_count \
    ddr0_source_boundary_ff $ddr0_src_count \
    ddr1_source_boundary_ff $ddr1_src_count \
    core_sink_boundary_ff $core_sink_count \
    ddr0_sink_boundary_ff $ddr0_sink_count \
    ddr1_sink_boundary_ff $ddr1_sink_count \
    source_boundary_ff_total $source_ff_count \
    sink_boundary_ff_total $sink_ff_count \
    boundary_ff_total $boundary_ff_count timing_categories 9 \
    shell_ff_total [llength $final_shell_ff] \
    shell_lut_primitives [llength $final_shell_lut] \
    dsp48e2 $final_dsp uram288 $final_uram \
    mlp_kernel_dsp48e2 $final_kernel_dsp \
    route_error_nets $route_errors explicit_gap_nets $explicit_gaps \
    unrouted_nets $unrouted_rows some_unrouted_pin_nets $unrouted_pins \
    resource_conflict_nets $resource_conflicts antenna_island_nets $antennas \
    route_status_partial [llength $partial_all] \
    bad_partial_nets [llength $bad_partial] \
    partial_clock_roots [join $partial_clock_roots ,] \
    reset_hierport_aliases [llength $hierport_all] \
    bad_hierport_nets [llength $bad_hierport] \
    reset_gap_roots [join $reset_roots ,] \
    route35198_reset_port_audit $route35198_ok \
    no_clock_endpoints $no_clock unconstrained_paths $unconstrained \
    no_input_delay_ports $no_input_delay \
    no_output_delay_ports $no_output_delay \
    partial_input_delay_ports $partial_input_delay \
    partial_output_delay_ports $partial_output_delay \
    timing_coverage_ok $timing_coverage_ok \
    drc_errors $drc_errors cdc_critical $cdc_critical \
    pre_place_drc_errors $pre_place_drc_errors \
    post_place_wns_ns $place_setup post_place_whs_ns $place_hold \
    post_unplaced_primitives $post_unplaced \
    post_slice_root_count $post_slice_root_count \
    slice0_dsp [llength $slice0_dsp] slice1_dsp [llength $slice1_dsp] \
    slice0_primitive_wrong_slr $slice0_primitive_wrong \
    slice1_primitive_wrong_slr $slice1_primitive_wrong \
    metadata_gate0_uram [llength $gate0_uram] \
    metadata_gate1_uram [llength $gate1_uram] \
    metadata_down0_uram [llength $down0_uram] \
    metadata_down1_uram [llength $down1_uram] \
    metadata_uram_wrong_slr $metadata_uram_wrong \
    projection_slr0_lane_roots [llength $projection_lane_slr0] \
    projection_slr2_lane_roots [llength $projection_lane_slr2] \
    projection_slr0_dsp [llength $projection_slr0_dsp] \
    projection_slr2_dsp [llength $projection_slr2_dsp] \
    projection_slr0_dsp_wrong $projection_slr0_dsp_wrong \
    projection_slr2_dsp_wrong $projection_slr2_dsp_wrong \
    projection_slr0_primitive_wrong $projection_slr0_primitive_wrong \
    projection_slr2_primitive_wrong $projection_slr2_primitive_wrong \
    slr0_dsp [lindex $slr_dsp 0] slr1_dsp [lindex $slr_dsp 1] \
    slr2_dsp [lindex $slr_dsp 2] \
    exact_resource_contract_ok $resource_ok \
    physical_contract_ok $physical_ok status $status]] {
    puts $fp "$key=$value"
}
close $fp
puts "PRODUCTION_REGISTERED_OOC WNS=$wns WHS=$whs BOUNDARY_FF=$boundary_ff_count DSP=$final_dsp URAM=$final_uram KERNEL_DSP=$final_kernel_dsp STATUS=$status"
if {$status ne \
    "PRODUCTION_REGISTERED_OOC_PROXY_PASS_EXPECTED_RESET_PARTPIN_GAPS"} {
    error "Registered production core OOC acceptance failed"
}
close_project
