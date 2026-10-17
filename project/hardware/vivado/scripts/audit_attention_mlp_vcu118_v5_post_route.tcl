set script_dir [file dirname [file normalize [info script]]]
set root [file normalize [file join $script_dir ../..]]
foreach name {
    HAP_JOBS HAP_PROJECT_DIR HAP_REPORT_DIR HAP_ROUTE_REPORT_DIR
    HAP_BOARD_CORE_CLK_MHZ HAP_BOARD_DDR_UI_CLK_HZ
} {
    if {![info exists ::env($name)] || $::env($name) eq ""} {
        error "Missing audit input $name"
    }
}
set jobs $::env(HAP_JOBS)
set project_dir [file normalize $::env(HAP_PROJECT_DIR)]
set audit_dir [file normalize $::env(HAP_REPORT_DIR)]
set route_dir [file normalize $::env(HAP_ROUTE_REPORT_DIR)]
set project_base [file normalize [file join $root vivado project]]
set report_base [file normalize [file join $root vivado reports]]
if {![string is integer -strict $jobs] || $jobs < 1 || $jobs > 32} {
    error "HAP_JOBS must be in 1..32"
}
if {![string match "2025.2*" [version -short]]} {
    error "Expected Vivado 2025.2, got [version -short]"
}
if {$::env(HAP_BOARD_CORE_CLK_MHZ) ne "100.0" ||
    $::env(HAP_BOARD_DDR_UI_CLK_HZ) ne "200000000"} {
    error "Audit requires the current core100/DDR200 profile"
}
if {![string match [file join $project_base *] $project_dir] ||
    ![string match [file join $report_base *] $route_dir] ||
    ![string match [file join $report_base *] $audit_dir] ||
    $route_dir eq $audit_dir || ![file isdirectory $audit_dir] ||
    [file exists [file join $audit_dir audit_inputs.sha256]]} {
    error "Audit paths must be distinct, new-root project/report directories"
}
set_param general.maxThreads $jobs

proc audit_file {path} {
    if {![file isfile $path] || [file size $path] == 0} {
        error "Missing or empty audit input: $path"
    }
    return $path
}
proc audit_sha {path} {
    return [lindex [exec sha256sum -- [audit_file $path]] 0]
}
proc audit_key_values {path} {
    set handle [open [audit_file $path] r]
    set rows [split [read $handle] "\n"]
    close $handle
    set values [dict create]
    foreach row $rows {
        if {$row eq ""} {continue}
        set pivot [string first = $row]
        if {$pivot < 1} {error "Malformed evidence row in $path: $row"}
        set key [string range $row 0 [expr {$pivot - 1}]]
        if {[dict exists $values $key]} {error "Duplicate evidence key $key"}
        dict set values $key [string range $row [expr {$pivot + 1}] end]
    }
    return $values
}
proc audit_clock_family {port_name reference_ns generated_ns} {
    set port [get_ports -quiet $port_name]
    if {[llength $port] != 1} {error "Missing routed reference port $port_name"}
    set primary [get_clocks -quiet -of_objects $port]
    if {[llength $primary] != 1} {error "$port_name has no unique primary clock"}
    set period [get_property PERIOD $primary]
    if {![string is double -strict $period] ||
        abs(double($period) - double($reference_ns)) > 0.001} {
        error "$port_name primary clock is not $reference_ns ns: $period"
    }
    set family [get_clocks -quiet -include_generated_clocks -of_objects $port]
    set found 0
    foreach clock $family {
        set period [get_property PERIOD $clock]
        if {$clock ne $primary && [string is double -strict $period] &&
            abs(double($period) - double($generated_ns)) <= 0.001} {
            set found 1
        }
    }
    if {!$found} {error "$port_name lacks generated $generated_ns ns clock"}
    return $family
}

set route_status_path [audit_file [file join $route_dir launcher_status.txt]]
set route_status [audit_key_values $route_status_path]
foreach {key expected} [list stage route exit_code 0 \
    project $project_dir reports $route_dir] {
    if {![dict exists $route_status $key] ||
        [dict get $route_status $key] ne $expected} {
        error "Original route launcher does not match $key=$expected"
    }
}
set synth_dir [file normalize [dict get $route_status synth_reports]]
if {![string match [file join $report_base *] $synth_dir] ||
    $synth_dir eq $route_dir || $synth_dir eq $audit_dir} {
    error "Route launcher does not identify a distinct same-root synthesis"
}
set project_file [audit_file [file join $project_dir scalellm_vcu118_f05.xpr]]
set dcp [audit_file [file join $route_dir routed.dcp]]
set dcp_manifest [audit_file [file join $route_dir routed_checkpoint.sha256]]
set route_inputs [audit_file [file join $route_dir inputs.sha256]]
set route_identity [audit_file [file join $route_dir build_identity.txt]]
set synth_inputs [audit_file [file join $synth_dir inputs.sha256]]
set synth_identity [audit_file [file join $synth_dir build_identity.txt]]
set synth_marker [audit_file [file join $synth_dir fresh_synth_complete.txt]]
if {[audit_sha $route_inputs] ne [audit_sha $synth_inputs] ||
    [audit_sha $route_identity] ne [audit_sha $synth_identity]} {
    error "Routed build inputs differ from its fresh synthesis"
}
set handle [open $synth_marker r]
set marker [string trim [read $handle]]
close $handle
if {[dict get $marker project] ne $project_dir ||
    [dict get $marker inputs_sha256] ne [audit_sha $route_inputs] ||
    [dict get $marker identity_sha256] ne [audit_sha $route_identity]} {
    error "Fresh synthesis marker does not bind this routed project"
}
set identity [audit_key_values $route_identity]
foreach {key expected} {
    vivado 2025.2
    part xcvu9p-flga2104-2L-e
    board xilinx.com:vcu118:part0:2.0
    top scalellm_vcu118_f05_bd_wrapper
} {
    if {![dict exists $identity $key] ||
        [dict get $identity $key] ne $expected} {
        error "Routed project identity mismatch: $key"
    }
}
set required_defines [list HAP_BOARD_BUILD HAP_BOARD_V5 \
    HAP_MLP_FULL_COMMAND_V5_MODULE=hap_mlp_full_command16_s54 \
    HAP_ATTENTION_BOARD_MODULE=hap_attention_board_cohort16_core]
if {[lsort [dict get $identity defines]] ne [lsort $required_defines]} {
    error "Routed project is not the current format05/cohort16 source"
}
exec sha256sum --check --status $route_inputs
exec sha256sum --check --status $dcp_manifest

set route_reports [list]
foreach name {
    timing_post_route.rpt clocks_post_route.rpt
    clock_interaction_post_route.rpt cdc_post_route.rpt
    drc_post_route.rpt route_status_post_route.rpt
    exceptions_post_route.rpt
} {
    lappend route_reports [audit_file [file join $route_dir $name]]
}
set pin_xdc [audit_file [file join $root vivado constraints \
    vcu118_ddr4_explicit_pins.xdc]]
set clock_xdc [audit_file [file join $root vivado constraints \
    board_clock_domains.xdc]]
set inputs [concat [list [file normalize [info script]] \
    [file join $script_dir run_vcu118_board.sh] \
    [file join $script_dir emit_current_board_evidence.py] \
    $project_file $dcp \
    $dcp_manifest $route_status_path $route_inputs $route_identity $synth_inputs \
    $synth_identity $synth_marker $pin_xdc $clock_xdc] $route_reports]
set input_manifest [file join $audit_dir audit_inputs.sha256]
set handle [open $input_manifest w]
foreach path [lsort -unique $inputs] {
    puts $handle "[audit_sha $path]  $path"
}
close $handle
set dcp_sha [audit_sha $dcp]

# This is a separate Vivado process: the routed design is read from disk, not
# inherited from the implementation run's in-memory design.
open_checkpoint $dcp
if {[get_property PART [current_design]] ne "xcvu9p-flga2104-2L-e"} {
    error "Reopened DCP has the wrong FPGA part"
}
set pcie_family [audit_clock_family pcie_refclk_p 10.000 10.000]
set ddr0_family [audit_clock_family default_250mhz_clk1_clk_p 4.000 5.000]
set ddr1_family [audit_clock_family default_250mhz_clk2_clk_p 4.000 5.000]
set combined [concat $pcie_family $ddr0_family $ddr1_family]
if {[llength [lsort -unique $combined]] != [llength $combined]} {
    error "Reopened PCIe and DDR clock families overlap"
}

set pin_report [open [file join $audit_dir package_pins_reopened.txt] w]
set handle [open $pin_xdc r]
set pin_rows [split [read $handle] "\n"]
close $handle
set pin_count 0
foreach row $pin_rows {
    if {![string match "set_property -dict *" $row]} {continue}
    if {![regexp {^set_property -dict \{PACKAGE_PIN ([^ ]+) (.+)\} \[get_ports \{([^}]+)\}\]$} \
        $row -> site attributes port_name]} {
        error "Unexpected nonliteral DDR pin constraint: $row"
    }
    set port [get_ports -quiet $port_name]
    if {[llength $port] != 1 ||
        [get_property PACKAGE_PIN $port] ne $site} {
        error "Reopened DDR port/site mismatch: $port_name $site"
    }
    foreach {key expected} $attributes {
        if {[get_property -quiet $key $port] ne $expected} {
            error "Reopened DDR property mismatch: $port_name $key"
        }
    }
    puts $pin_report "$port_name $site"
    incr pin_count
}
close $pin_report
if {$pin_count != 234} {error "Reopened DDR/ref pin count is $pin_count"}

report_timing_summary -delay_type min_max -report_unconstrained \
    -file [file join $audit_dir timing_reopened.rpt]
check_timing -verbose -file [file join $audit_dir check_timing_reopened.rpt]
report_pulse_width -file [file join $audit_dir pulse_width_reopened.rpt]
report_pulse_width -all_violators -file [file join $audit_dir pulse_width_violators_reopened.rpt]
report_bus_skew -delay_type min_max -warn_on_violation \
    -file [file join $audit_dir bus_skew_reopened.rpt]
set sticky_pins [get_pins -of_objects [get_cells -hier -filter {REF_NAME == DSP48E2}] \
    -filter {REF_PIN_NAME == OVERFLOW || REF_PIN_NAME == UNDERFLOW}]
if {[llength $sticky_pins] == 0} { error "Missing DSP sticky-status audit selectors" }
report_timing -from $sticky_pins -delay_type min_max -max_paths 256 \
    -file [file join $audit_dir dsp_status_paths_reopened.rpt]
report_clocks -file [file join $audit_dir clocks_reopened.rpt]
report_clock_interaction -delay_type min_max \
    -file [file join $audit_dir clock_interaction_reopened.rpt]
report_route_status -file [file join $audit_dir route_status_reopened.rpt]
report_drc -file [file join $audit_dir drc_reopened.rpt]
report_cdc -details -file [file join $audit_dir cdc_reopened.rpt]
report_exceptions -coverage -file [file join $audit_dir exceptions_reopened.rpt]
report_io -file [file join $audit_dir io_reopened.rpt]
set setup [lindex [get_timing_paths -quiet -delay_type max -max_paths 1] 0]
set hold [lindex [get_timing_paths -quiet -delay_type min -max_paths 1] 0]
if {$setup eq "" || $hold eq ""} {
    error "Reopened DCP has no setup or hold timing paths"
}
set wns [get_property SLACK $setup]
set whs [get_property SLACK $hold]
if {![string is double -strict $wns] ||
    ![string is double -strict $whs] || $wns < 0 || $whs < 0} {
    error "Reopened DCP setup/hold blocker: WNS=$wns WHS=$whs"
}
foreach violation [get_drc_violations -quiet] {
    if {[string tolower [get_property SEVERITY $violation]] in \
        {error {critical warning}}} {
        error "Reopened DCP DRC blocker: $violation"
    }
}
exec sha256sum --check --status $route_inputs
exec sha256sum --check --status $dcp_manifest
exec sha256sum --check --status $input_manifest
set handle [open [file join $audit_dir audit_summary.txt] w]
puts $handle "status=REOPENED_REPORTS_READY_SIGNOFF_HOLD"
puts $handle "checkpoint=$dcp"
puts $handle "checkpoint_sha256=$dcp_sha"
puts $handle "route_input_manifest_sha256=[audit_sha $route_inputs]"
puts $handle "audit_input_manifest_sha256=[audit_sha $input_manifest]"
puts $handle "part=[get_property PART [current_design]]"
puts $handle "ddr_reference_ns=4.000"
puts $handle "core_generated_ns=10.000"
puts $handle "ddr_generated_ns=5.000"
puts $handle "package_pin_count=$pin_count"
puts $handle "worst_setup_slack_ns=$wns"
puts $handle "worst_hold_slack_ns=$whs"
puts $handle "bitstream_generated=0"
puts $handle "remaining=review_unconstrained_paths_route_cdc_reset_and_all_clock_reports"
puts $handle "dsp_status_report_scope=sample_max256_paths_not_complete_primitive_coverage"
puts $handle "pulse_bus_skew_reports=generated_not_automatically_qualified"
close $handle
close_design
puts "REOPENED_REPORTS_READY_SIGNOFF_HOLD checkpoint_sha256=$dcp_sha"
