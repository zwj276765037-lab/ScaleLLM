# SPDX-License-Identifier: Apache-2.0
# Read the native project run status after an implementation launcher exits.
if {![info exists ::env(HAP_PROJECT_DIR)]} {error {Missing HAP_PROJECT_DIR}}
if {[version -short] ne {2025.2}} {error {Vivado 2025.2 required}}
open_project [file join $::env(HAP_PROJECT_DIR) scalellm_final_decode16.xpr]
set run [get_runs impl_1]
puts "IMPL_RUN_STATUS=[get_property STATUS $run]"
puts "IMPL_RUN_PROGRESS=[get_property PROGRESS $run]"
puts "IMPL_RUN_DIRECTORY=[get_property DIRECTORY $run]"
close_project
