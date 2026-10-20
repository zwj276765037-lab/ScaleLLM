# Unmodified original project/G4/restore and fixed physopt/route, with an
# explicitly inherited successful place and all original unfinished POST checks.
set continue_here [file dirname [file normalize [info script]]]
set continue_scripts [file normalize [file join $continue_here ../../../hardware/vivado/scripts]]
source [file join $continue_here runtime_state_collector.tcl]
proc m003_continue_install_qualifier {} {
    set body [info body m003::snapshot_body]
    set needle {m003_python [file join $scripts m003_joint_evidence.py] --snapshot [file join $out m003_native_${phase}.json] --spec $spec_path --output [file join $out m003_qualification_${phase}.json]}
    if {[llength [regexp -all -inline {m003_joint_evidence.py} $body]] != 1 || [string first $needle $body] < 0} {error "Original full qualifier call-site changed"}
    set helper [file join $::continue_here runtime_qualify.py]
    set replacement [format {m003_python {%s} --snapshot [file join $out m003_native_${phase}.json] --spec $spec_path --output [file join $out m003_qualification_${phase}.json] --phase $phase --report $out} $helper]
    proc m003::snapshot_body {phase out} "m003_collect_actual_write_states \$phase \$out\n[string map [list $needle $replacement] $body]"
}
proc m003_continue_install_post {} {
    set body [info body m002_post]
    set needle {source [file join $::m002_script_dir m003_joint_checks.tcl]}
    if {[llength [regexp -all -inline {source \[file join \$::m002_script_dir m003_joint_checks.tcl\]} $body]] != 1} {error "Original POST source changed"}
    proc m002_post {point} [string map [list $needle "$needle\n        m003_continue_install_qualifier"] $body]
}
proc m003_complete_inherited_place_POST {point} {
    if {$point ne "place"} {error "Only successful place reports may be inherited"}
    set bb [get_cells -quiet -hier -filter {IS_BLACKBOX == 1}]
    if {[llength $bb]} {error "Restored successful place has new blackboxes"}
    m003_collect_actual_write_states place $::m002_report_dir
    m003_python [file join $::continue_here runtime_qualify.py] --snapshot [file join $::m002_report_dir m003_native_place.json] --spec [file join $::continue_scripts ../constraints/m003_joint_locality_spec.json] --output [file join $::m002_report_dir m003_qualification_place.json] --phase place --report $::m002_report_dir
    set full [info body m002_post]
    set marker [format {    if {$point in {place physopt route}} %c} 123]
    set index [string first $marker $full]
    if {$index < 0 || [string first $marker $full [expr {$index+1}]] >= 0} {error "Original full unfinished place POST boundary changed"}
    set suffix [string range $full $index end]
    if {![info complete $suffix]} {error "Inherited place POST suffix incomplete"}
    eval $suffix
}
set h [open [file join $continue_scripts m003_physical.tcl] r]
set body [read $h]
close $h
set substitutions [list \
    {set script_dir [file dirname [file normalize [info script]]]} [list set script_dir $continue_scripts] \
    {source [file join $script_dir m003_joint_checks.tcl]} {source [file join $script_dir m003_joint_checks.tcl]
m003_continue_install_qualifier
m003_continue_install_post} \
    {    m003_command place {place_design -directive SSI_SpreadSLLs}} {    puts "M003_PLACE_COMMAND_INHERITED actual_parent_AT001_native_tcl_code=0 no_place_reexecuted=true"} \
    {    m002_post place} {    m003_complete_inherited_place_POST place}]
foreach {old new} $substitutions {
    set index [string first $old $body]
    if {$index < 0 || [string first $old $body [expr {$index+1}]] >= 0} {error "Original physical continuation substitution changed"}
    set body [string map [list $old $new] $body]
}
if {![info complete $body]} {error "Original physical continuation body incomplete"}
uplevel #0 $body
