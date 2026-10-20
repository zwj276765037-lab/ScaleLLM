# M003 G2-selected overlay. This file is registered for implementation only.
# Keep all source/role/site validation active on native reads and restores.
set m003_overlay_dir [file dirname [file normalize [info script]]]
source [file join $m003_overlay_dir ../scripts/m003_joint_checks.tcl]
m003::apply
