# Resume the candidate's native implementation. Original inputs and guards remain frozen.
set out $::env(NATIVE_OUT)
set control $::env(NATIVE_CONTROL)
set name $::env(NATIVE_CANDIDATE)
set hw $::env(HAP_HW_ROOT)
set_param general.maxThreads 32
source [file join $hw vivado scripts release_reports.tcl]

proc save_text {path value} {
    set stream [open $path w]
    puts $stream $value
    close $stream
}
proc phase {value} {
    save_text [file join $::out phase.txt] $value
    puts "NATIVE_PHASE=$value"
    flush stdout
}
proc require_loaded_identity {folder} {
    # The read-only native probe established that TOP is the loaded netlist top,
    # while NAME can be a checkpoint/session alias. Both properties are recorded.
    set original_failed [catch {require_design_identity} original_message]
    set design [current_design]
    set loaded_top [get_property TOP $design]
    set loaded_name [get_property NAME $design]
    set loaded_part [get_property PART $design]
    save_text [file join $folder loaded_identity.txt] "TOP=$loaded_top\nNAME=$loaded_name\nPART=$loaded_part\nVERSION=[version -short]\nORIGINAL_GUARD_FAILED=$original_failed\nORIGINAL_GUARD_MESSAGE=$original_message"
    if {[version -short] ne {2025.2} || $loaded_part ne {xcvu9p-flga2104-2L-e}} {error {Loaded tool or part mismatch}}
    if {$loaded_top ne {scalellm_final_decode16_bd_wrapper}} {error {Loaded netlist TOP mismatch}}
    foreach {pin expected} {core_clk 12.5 ddr0_clk 5.0 ddr1_clk 5.0} {
        set pins [get_pins -quiet scalellm_final_decode16_bd_i/core/inst/$pin]
        set clocks [get_clocks -quiet -of_objects $pins]
        if {[llength $pins] != 1 || [llength $clocks] != 1} {error "Missing unique clock at $pin"}
        if {abs(double([get_property PERIOD $clocks])-$expected)>0.001} {error "Clock period mismatch at $pin"}
    }
    if {$original_failed && $original_message ne {Top mismatch}} {error $original_message}
    puts "LOADED_IDENTITY_PASS TOP=$loaded_top NAME=$loaded_name PART=$loaded_part"
}
proc require_zero_blackboxes {folder} {
    set cells [get_cells -hierarchical -quiet -filter {IS_BLACKBOX == 1}]
    set stream [open [file join $folder blackboxes.txt] w]
    foreach cell $cells {puts $stream "[get_property NAME $cell]\t[get_property REF_NAME $cell]"}
    close $stream
    if {[llength $cells]} {error "Unresolved blackboxes: [llength $cells]"}
}
proc native_reports {folder} {
    file mkdir $folder
    require_loaded_identity $folder
    require_zero_blackboxes $folder
    report_scene $folder
    report_utilization -hierarchical -file [file join $folder utilization_hierarchical.rpt]
    report_utilization -slr -file [file join $folder utilization_slr.rpt]
    foreach {command filename} {report_design_analysis congestion.rpt report_high_fanout_nets high_fanout_nets.rpt} {
        if {$command eq {report_design_analysis}} {
            set failed [catch {report_design_analysis -congestion -file [file join $folder $filename]} message]
        } else {
            set failed [catch {report_high_fanout_nets -file [file join $folder $filename]} message]
        }
        if {$failed} {save_text [file join $folder ${filename}.error.txt] $message}
    }
    set dsps [lsort [get_cells -hierarchical -quiet -filter {REF_NAME == DSP48E2}]]
    set stream [open [file join $folder dsp_inventory.tsv] w]
    puts $stream "name\tref_name\tloc\tbel\torig_ref_name"
    foreach dsp $dsps {
        set fields [list [get_property NAME $dsp]]
        foreach property {REF_NAME LOC BEL ORIG_REF_NAME} {
            set value {}
            catch {set value [get_property $property $dsp]}
            lappend fields $value
        }
        puts $stream [join $fields "\t"]
    }
    close $stream
    set leaves [lsort -unique [concat \
        [get_cells -hierarchical -quiet -filter {REF_NAME =~ *hap_a8w4_scalecode_recover2_lut*}] \
        [get_cells -hierarchical -quiet -filter {ORIG_REF_NAME =~ *hap_a8w4_scalecode_recover2_lut*}]]]
    set stream [open [file join $folder recovery_mapping.tsv] w]
    puts $stream "name\tref_name\torig_ref_name\tdsp_descendants"
    set count 0
    foreach cell $leaves {
        set path [get_property NAME $cell]
        if {![string match {*u_recover*} $path]} {continue}
        set descendants 0
        foreach dsp $dsps {
            if {[string first "$path/" [get_property NAME $dsp]] == 0} {incr descendants}
        }
        puts $stream "$path\t[get_property REF_NAME $cell]\t[get_property ORIG_REF_NAME $cell]\t$descendants"
        incr count
    }
    close $stream
    if {$count != 96} {error "Expected 96 recovery leaves, found $count"}
}
proc await_file {path} {
    while {![file isfile $path]} {after 1000}
    set stream [open $path r]
    set value [string trim [read $stream]]
    close $stream
    return $value
}
proc final_gate {folder} {
    require_loaded_identity $folder
    require_zero_blackboxes $folder
    require_timing $folder
}

phase placement_report
open_project $::env(NATIVE_PROJECT)
set run [get_runs impl_1]
save_text [file join $out native_run_status.txt] "STATUS=[get_property STATUS $run]\nPROGRESS=[get_property PROGRESS $run]\nDIRECTORY=[get_property DIRECTORY $run]"
if {[get_property PART [current_project]] ne {xcvu9p-flga2104-2L-e}} {error {Project part mismatch}}
if {[get_property INCREMENTAL_CHECKPOINT $run] ne {}} {error {Unexpected incremental checkpoint}}
open_run impl_1
set placed [file join $out post_physopt]
native_reports $placed
save_text [file join $out reports_ready.txt] {POST_PHYSOPT_REPORTS_PASS}
phase selection_wait
set selected [await_file [file join $control selected.txt]]
if {$selected ne $name} {
    phase not_selected
    close_project
    puts {NATIVE_PLACEMENT_REPORT_PASS NOT_SELECTED}
    exit 0
}
await_file [file join $control route_go.txt]
phase route
set routed [file join $out route]
file mkdir $routed
require_loaded_identity $routed
require_zero_blackboxes $routed
set failed [catch {route_design -directive Default} message options]
set current_dcp [file join $routed routed.dcp]
write_checkpoint $current_dcp
if {$failed} {return -options $options $message}
native_reports $routed
set gate_failed [catch {final_gate $routed} gate_message]
save_text [file join $routed gate.txt] [expr {$gate_failed ? "FAIL $gate_message" : {PASS}}]
phase route_review
set command_index 1
set used_hold {}
while {1} {
    set action [await_file [file join $out command_${command_index}.txt]]
    incr command_index
    if {$action eq {bitstream}} {
        if {$gate_failed} {error {Bitstream requires a passing physical gate}}
        phase bitstream
        set bitout [file join $out bitstream]
        file mkdir $bitout
        set source_sha [lindex [exec sha256sum -- $current_dcp] 0]
        save_text [file join $bitout selected_checkpoint.txt] "PATH=$current_dcp\nSHA256=$source_sha"
        final_gate $bitout
        if {[lindex [exec sha256sum -- $current_dcp] 0] ne $source_sha} {error {Selected checkpoint changed before bit generation}}
        write_bitstream [file join $bitout ScaleLLM_Final_Decode16_80MHz.bit]
        phase complete
        close_project
        puts {NATIVE_RESUME_BITSTREAM_PASS}
        exit 0
    }
    if {$action ni {hold-sll hold}} {error "Unsupported recovery action $action"}
    if {$action in $used_hold} {error "Hold repair already attempted: $action"}
    lappend used_hold $action
    phase $action
    set holdout [file join $out $action]
    file mkdir $holdout
    require_loaded_identity $holdout
    require_zero_blackboxes $holdout
    if {![report_route_status -boolean_check ROUTED_FULLY] || [report_route_status -boolean_check ERRORS_IN_ROUTES]} {error {Hold repair requires full routing}}
    set method [expr {$action eq {hold-sll} ? {sll_reg_hold_fix} : {hold_fix}}]
    save_text [file join $holdout repair_selection.txt] "METHOD=phys_opt_design -$method\nSOURCE=$current_dcp\nSHA256=[lindex [exec sha256sum -- $current_dcp] 0]"
    set failed [catch {phys_opt_design -$method} message options]
    write_checkpoint [file join $holdout post_physopt.dcp]
    if {$failed} {return -options $options $message}
    set fully [report_route_status -boolean_check ROUTED_FULLY]
    set errors [report_route_status -boolean_check ERRORS_IN_ROUTES]
    if {$fully ni {0 1} || $errors ni {0 1}} {error {Unknown route-status boolean}}
    if {!$fully || $errors} {
        set failed [catch {route_design -preserve} message options]
    }
    set current_dcp [file join $holdout routed.dcp]
    write_checkpoint $current_dcp
    if {$failed} {return -options $options $message}
    native_reports $holdout
    set gate_failed [catch {final_gate $holdout} gate_message]
    save_text [file join $holdout gate.txt] [expr {$gate_failed ? "FAIL $gate_message" : {PASS}}]
    phase hold_review
}
