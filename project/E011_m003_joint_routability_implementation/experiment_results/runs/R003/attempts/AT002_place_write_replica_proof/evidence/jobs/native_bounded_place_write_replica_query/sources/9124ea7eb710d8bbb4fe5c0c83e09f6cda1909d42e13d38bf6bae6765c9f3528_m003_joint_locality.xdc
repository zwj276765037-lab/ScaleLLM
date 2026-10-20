# M003 G2-selected overlay. This file is registered for implementation only.
# Keep all source/role/site validation active on native reads and restores.
# FILE_TYPE is explicitly TCL. In Vivado's TCL-constraint interpreter,
# info script belongs to the generated run driver, so use the bound root.
if {![info exists ::env(HAP_M003_SCRIPTS_DIR)]} {error "M003 explicit script root missing"}
set m003_script_root [file normalize $::env(HAP_M003_SCRIPTS_DIR)]
if {![string match */project/hardware/vivado/scripts $m003_script_root]} {error "M003 invalid script root"}
source [file join $m003_script_root m003_joint_checks.tcl]
m003::apply
