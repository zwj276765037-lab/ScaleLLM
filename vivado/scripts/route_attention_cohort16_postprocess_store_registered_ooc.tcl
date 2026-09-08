set root [file normalize [file join [file dirname [info script]] ../..]]
set out [file normalize $::env(HAP_REPORT_DIR)]
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
set input_manifest_sha $::env(HAP_INPUT_MANIFEST_SHA256)
set part xcvu9p-flga2104-2L-e
set top hap_attention_cohort16_postprocess_store_registered_ooc_harness
if {![string is integer -strict $jobs] || $jobs < 1 || $jobs > 32} {
    error "HAP_JOBS must be an integer in 1..32: $jobs"
}
if {![regexp {^[0-9a-f]{64}$} $input_manifest_sha]} {
    error "Invalid postprocess OOC input manifest SHA256"
}
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
set_param general.maxThreads $jobs
file mkdir $out

proc write_text {path value} {
    set fp [open $path w]
    puts -nonewline $fp $value
    close $fp
}

proc timing_check_count {text label} {
    set pattern [format \
        {checking[[:space:]]+%s[[:space:]]+\(([0-9]+)\)} $label]
    if {![regexp -nocase -- $pattern $text -> count]} {
        error "Missing check_timing category: $label"
    }
    return $count
}

proc route_status_row {text label {required 0}} {
    foreach line [split $text "\n"] {
        if {[string first $label $line] >= 0 &&
            [regexp {:[[:space:]]*([0-9]+)[[:space:]]*:} \
                $line -> count]} {
            return $count
        }
    }
    if {$required} {error "Missing route-status row: $label"}
    return 0
}

proc congestion_count {text minimum_level} {
    set count 0
    foreach line [split $text "\n"] {
        if {[regexp {^\|[[:space:]]*(North|South|East|West)[[:space:]]+\|[[:space:]]*(Global|Long|Short)[[:space:]]+\|[[:space:]]*([0-9]+)[[:space:]]+\|} \
                $line -> direction type level] && $level >= $minimum_level} {
            incr count
        }
    }
    return $count
}

create_project -in_memory -part $part
read_verilog -sv [file join $root rtl attention \
    hap_attention_cohort16_local_stores.sv]
read_verilog -sv [file join $root rtl attention \
    hap_attention_cohort16_postprocess_store_registered_ooc_harness.sv]
read_xdc [file join $root vivado constraints \
    attention_cohort16_postprocess_store_registered_ooc_150mhz.xdc]
synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive AreaOptimized_high

set source_proxy [get_cells -quiet -hierarchical -filter \
    {NAME =~ src_r_reg* && REF_NAME =~ FD*}]
set sink_proxy [get_cells -quiet -hierarchical -filter \
    {NAME =~ sink_r_reg* && REF_NAME =~ FD*}]
set dut [get_cells -quiet u_dut]
set bank_instances [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_attention_cohort16_postprocess_row_bank ||
    REF_NAME == hap_attention_cohort16_postprocess_row_bank
}]
if {[llength $source_proxy] != 3151 || [llength $sink_proxy] != 3120 ||
    [llength $dut] != 1 || [llength $bank_instances] != 16 ||
    [llength [get_ports -quiet]] != 1} {
    error "Postprocess OOC identity mismatch source=[llength $source_proxy] sink=[llength $sink_proxy] dut=[llength $dut] banks=[llength $bank_instances] ports=[llength [get_ports -quiet]]"
}

set all_ff [get_cells -quiet -hierarchical -filter {REF_NAME =~ FD*}]
set dut_ff [filter $all_ff {NAME =~ u_dut/*}]
set shell_ff [filter $all_ff {NAME !~ u_dut/*}]
if {[llength $dut_ff] != 24580 || [llength $shell_ff] != 6271} {
    error "Postprocess OOC FF mismatch dut=[llength $dut_ff] shell=[llength $shell_ff]"
}

opt_design -directive ExploreWithRemap
set dut_nonclock_nets {}
foreach net [get_nets -quiet -hierarchical -filter {NAME =~ u_dut/*}] {
    if {[llength [get_clocks -quiet -of_objects $net]] == 0} {
        lappend dut_nonclock_nets $net
    }
}
if {[llength $dut_nonclock_nets] != 0} {
    set_property CLOCK_BUFFER_TYPE NONE $dut_nonclock_nets
}

create_pblock pb_postprocess_ooc_slr1
resize_pblock [get_pblocks pb_postprocess_ooc_slr1] -add {SLR1}
add_cells_to_pblock [get_pblocks pb_postprocess_ooc_slr1] $dut
add_cells_to_pblock [get_pblocks pb_postprocess_ooc_slr1] \
    [concat $source_proxy $sink_proxy]

place_design -directive AltSpreadLogic_high
set place_congestion [report_design_analysis -congestion -return_string]
write_text [file join $out congestion_post_place.rpt] $place_congestion
set place_level5 [congestion_count $place_congestion 5]
set place_level6 [congestion_count $place_congestion 6]

phys_opt_design -directive AggressiveExplore
route_design -directive AggressiveExplore

set timing_text [report_timing_summary -delay_type min_max -max_paths 100 \
    -report_unconstrained -warn_on_violation -return_string]
write_text [file join $out timing_summary.rpt] $timing_text
report_utilization -hierarchical -hierarchical_depth 5 \
    -file [file join $out utilization.rpt]
set route_text [report_route_status -return_string]
write_text [file join $out route_status.rpt] $route_text
report_drc -file [file join $out drc.rpt]
set route_congestion [report_design_analysis -congestion -return_string]
write_text [file join $out congestion_post_route.rpt] $route_congestion

set setup_path [lindex [get_timing_paths -delay_type max -max_paths 1] 0]
set hold_path [lindex [get_timing_paths -delay_type min -max_paths 1] 0]
if {[llength $setup_path] != 1 || [llength $hold_path] != 1} {
    error "Postprocess OOC timing paths are missing"
}
set wns [get_property SLACK $setup_path]
set whs [get_property SLACK $hold_path]
set no_clock [timing_check_count $timing_text no_clock]
set unconstrained [timing_check_count $timing_text \
    unconstrained_internal_endpoints]
set no_input_delay [timing_check_count $timing_text no_input_delay]
set no_output_delay [timing_check_count $timing_text no_output_delay]
set partial_input_delay [timing_check_count $timing_text partial_input_delay]
set partial_output_delay [timing_check_count $timing_text partial_output_delay]
set timing_coverage_ok [expr {$no_clock == 0 && $unconstrained == 0 &&
    $no_input_delay == 0 && $no_output_delay == 0 &&
    $partial_input_delay == 0 && $partial_output_delay == 0}]

set route_errors [route_status_row $route_text \
    "# of nets with routing errors" 1]
set unrouted_rows [route_status_row $route_text "# of unrouted nets"]
set partial_rows [route_status_row $route_text \
    "# of nets with some unrouted pins"]
set resource_conflicts [route_status_row $route_text \
    "# of nets with resource conflicts"]
set antennas [route_status_row $route_text \
    "# of nets with antennas/islands"]
set unrouted [llength [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == UNROUTED || ROUTE_STATUS == PARTIALLY_ROUTED}]]
set drc [llength [get_drc_violations -quiet -filter {SEVERITY == Error}]]
set dsp [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == DSP48E2}]]
set uram [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == URAM288}]]
set lut [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ LUT*}]]
set data_bufg 0
foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}] {
    set outputs [get_pins -quiet -of_objects $cell -filter \
        {DIRECTION == OUT}]
    if {[llength [get_clocks -quiet -of_objects $outputs]] == 0} {
        incr data_bufg
    }
}
set route_level5 [congestion_count $route_congestion 5]
set route_level6 [congestion_count $route_congestion 6]
set route_clean [expr {$route_errors == 0 && $unrouted_rows == 0 &&
    $partial_rows == 0 && $resource_conflicts == 0 && $antennas == 0 &&
    $unrouted == 0}]
set status [expr {$wns >= 0.0 && $whs >= 0.0 && $timing_coverage_ok &&
    $route_clean && $drc == 0 && $dsp == 0 && $uram == 0 &&
    $data_bufg == 0 && $place_level6 == 0 && $route_level6 == 0 ?
    "PASS" : "FAIL"}]

set fp [open [file join $out summary.txt] w]
foreach {key value} [list \
        tool [version -short] part $part top $top core_clock_mhz 150 jobs $jobs \
        input_manifest_sha256 $input_manifest_sha \
        source_proxy_ff [llength $source_proxy] \
        sink_proxy_ff [llength $sink_proxy] \
        row_bank_instances [llength $bank_instances] \
        dut_lut_primitives $lut dut_ff_primitives [llength $dut_ff] \
        wns_ns $wns whs_ns $whs dsp48e2 $dsp uram288 $uram \
        data_bufg $data_bufg no_clock $no_clock \
        unconstrained_internal_endpoints $unconstrained \
        no_input_delay $no_input_delay no_output_delay $no_output_delay \
        partial_input_delay $partial_input_delay \
        partial_output_delay $partial_output_delay \
        timing_coverage_ok $timing_coverage_ok \
        placer_level5_or_higher $place_level5 \
        placer_level6_or_higher $place_level6 \
        router_level5_or_higher $route_level5 \
        router_level6_or_higher $route_level6 \
        route_error_nets $route_errors \
        route_status_unrouted_nets $unrouted_rows \
        route_status_partial_nets $partial_rows \
        route_status_resource_conflicts $resource_conflicts \
        route_status_antenna_island_nets $antennas \
        unrouted_nets $unrouted route_clean $route_clean \
        drc_errors $drc status $status] {
    puts $fp "$key=$value"
}
close $fp
if {$status ne "PASS"} {
    error "Attention cohort16 postprocess-store OOC physical gate failed"
}
write_checkpoint -force [file join $out post_route.dcp]
puts "POSTPROCESS_REGISTERED_OOC WNS=$wns WHS=$whs LUT=$lut FF=[llength $dut_ff] PLACE_L6=$place_level6 ROUTE_L6=$route_level6 STATUS=$status"
