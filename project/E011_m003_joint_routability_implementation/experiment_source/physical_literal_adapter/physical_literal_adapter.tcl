# Evaluate the exact frozen physical entry after two strict textual adapters.
# Every original registration/zeroapply/G4/fixed command/stage guard remains.
set physical_adapter_dir [file dirname [file normalize [info script]]]
set physical_original_dir [file normalize [file join $physical_adapter_dir ../../.. hardware/vivado/scripts]]
proc m003_physical_install_qualifier {} {
    set body [info body m003::snapshot_body]
    set needle {m003_python [file join $scripts m003_joint_evidence.py] --snapshot [file join $out m003_native_${phase}.json] --spec $spec_path --output [file join $out m003_qualification_${phase}.json]}
    if {[llength [regexp -all -inline {m003_joint_evidence.py} $body]] != 1 || [string first $needle $body] < 0} {error "Frozen physical full qualifier call-site changed"}
    set adapter [file normalize [file join $::physical_adapter_dir ../AT028_init_recovery/native_init_recovery.py]]
    set replacement [format {m003_python {%s} qualify --snapshot [file join $out m003_native_${phase}.json] --spec $spec_path --output [file join $out m003_qualification_${phase}.json]} $adapter]
    proc m003::snapshot_body {phase out} [string map [list $needle $replacement] $body]
}
proc m003_physical_install_post {} {
    set body [info body m002_post]
    set needle {source [file join $::m002_script_dir m003_joint_checks.tcl]}
    if {[llength [regexp -all -inline {source \[file join \$::m002_script_dir m003_joint_checks.tcl\]} $body]] != 1} {error "Frozen physical POST snapshot source changed"}
    proc m002_post {point} [string map [list $needle "$needle\n        m003_physical_install_qualifier"] $body]
}
proc m003_physical_adapt {body} {
    set root_line {set script_dir [file dirname [file normalize [info script]]]}
    set source_line {source [file join $script_dir m003_joint_checks.tcl]}
    foreach needle [list $root_line $source_line] {
        set pos [string first $needle $body]
        if {$pos < 0 || [string first $needle $body [expr {$pos+1}]] >= 0} {error "Frozen physical adapter target changed"}
    }
    set replacement "${source_line}\nm003_physical_install_qualifier\nm003_physical_install_post"
    return [string map [list $root_line [list set script_dir $::physical_original_dir] $source_line $replacement] $body]
}
set h [open [file join $physical_original_dir m003_physical.tcl] r];set physical_body [read $h];close $h
set physical_adapted [m003_physical_adapt $physical_body]
if {![info complete $physical_adapted]} {error "Adapted original physical entry is incomplete Tcl"}
uplevel #0 $physical_adapted
