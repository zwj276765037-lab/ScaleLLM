# Full selected board RTL elaboration only; never normal synthesis.
# run_m002_elaborate.sh owns timeout, source hashes and log validation.
set script_dir [file dirname [file normalize [info script]]]
set root [file normalize [file join $script_dir ../..]]
foreach name {HAP_ELAB_REPORT_DIR HAP_JOBS} {
    if {![info exists ::env($name)] || $::env($name) eq ""} {
        error "Missing required input $name; use run_m002_elaborate.sh"
    }
}
set out_dir [file normalize $::env(HAP_ELAB_REPORT_DIR)]
if {![string match [file join $root vivado reports *] $out_dir] ||
    ![file isdirectory $out_dir]} {
    error "Elaboration reports must be below the new hardware root"
}
set jobs $::env(HAP_JOBS)
if {![string is integer -strict $jobs] || $jobs < 1 || $jobs > 8} {
    error "HAP_JOBS must be in 1..8"
}
if {![string match "2025.2*" [version -short]]} {
    error "Expected Vivado 2025.2, got [version -short]"
}
set_param general.maxThreads $jobs
proc m002_collect {root path state} {
    set path [file normalize $path]
    if {![string match [file join $root *] $path] || ![file isfile $path]} {
        error "Manifest input missing or outside hardware root: $path"
    }
    if {[dict exists $state manifests $path]} {return $state}
    dict set state manifests $path 1
    set handle [open $path r]
    set lines [split [read $handle] "\n"]
    close $handle
    foreach raw $lines {
        set entry [string trim [lindex [split $raw #] 0]]
        if {$entry eq ""} {continue}
        set leaf [file normalize [file join $root $entry]]
        if {[file extension $leaf] eq ".list"} {
            set state [m002_collect $root $leaf $state]
        } else {
            if {![string match [file join $root *] $leaf] || ![file isfile $leaf]} {
                error "Source missing or outside hardware root: $leaf"
            }
            dict set state sources $leaf 1
        }
    }
    return $state
}
set manifest [file join $root vivado manifests attention_mlp_board_core_v5_sources.list]
set closure [m002_collect $root $manifest [dict create]]
set defines [list HAP_BOARD_BUILD HAP_BOARD_V5 \
    HAP_MLP_FULL_COMMAND_V5_MODULE=hap_mlp_full_command16_s54 \
    HAP_ATTENTION_BOARD_MODULE=hap_attention_board_cohort16_core]
create_project -in_memory -part xcvu9p-flga2104-2L-e
set_property verilog_define $defines [current_fileset]
set inputs [concat [dict keys [dict get $closure manifests]] \
    [dict keys [dict get $closure sources]] [list [info script]]]
set handle [open [file join $out_dir elab_inputs.sha256] w]
foreach path [lsort -unique $inputs] {
    puts $handle "[lindex [exec sha256sum -- $path] 0]  $path"
}
close $handle
set rtl [list]
dict for {path unused} [dict get $closure sources] {
    if {[file extension $path] in {.sv .v}} {lappend rtl $path}
}
read_verilog -sv $rtl
cd $out_dir
synth_design -rtl -top hap_attention_mlp_board_core \
    -part xcvu9p-flga2104-2L-e -mode out_of_context -no_iobuf
set blackboxes [get_cells -hier -quiet -filter {IS_BLACKBOX == 1}]
if {[llength $blackboxes]} {error "Unresolved black boxes: $blackboxes"}
set handle [open [file join $out_dir elaboration_scope.txt] w]
puts $handle "top=hap_attention_mlp_board_core"
puts $handle "mode=RTL elaboration (-rtl), no synthesis/implementation"
puts $handle "selected_rtl_files=[llength $rtl]"
puts $handle "hierarchical_cells=[llength [get_cells -hier -quiet]]"
puts $handle "blackboxes=[llength $blackboxes]"
close $handle
exec sha256sum --status -c [file join $out_dir elab_inputs.sha256]
puts {M002_FULL_ELABORATION_PASS}
close_design
close_project
exit 0
