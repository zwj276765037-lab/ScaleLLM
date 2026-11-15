# SPDX-License-Identifier: Apache-2.0
# One explicit global hold-repair invocation, adapted from the successful reader011 flow.
# No old DCP hash, endpoint, LOC/BEL, net selector or iteration loop is baked in.
set scripts [file dirname [file normalize [info script]]]
source [file join $scripts release_reports.tcl]
foreach name {HAP_STAGE HAP_JOBS HAP_REPORT_DIR HAP_SOURCE_DCP HAP_SOURCE_DCP_SHA256 HAP_HOLD_METHOD} {
    if {![info exists ::env($name)] || $::env($name) eq {}} {error "Missing $name"}
}
set out $::env(HAP_REPORT_DIR)
set method $::env(HAP_HOLD_METHOD)
if {$method ni {sll_reg_hold_fix hold_fix}} {error {Only an explicitly selected hold method is supported}}
set_param general.maxThreads $::env(HAP_JOBS)
if {[lindex [exec sha256sum -- $::env(HAP_SOURCE_DCP)] 0] ne $::env(HAP_SOURCE_DCP_SHA256)} {error {Source checkpoint hash mismatch}}
open_checkpoint $::env(HAP_SOURCE_DCP)
require_design_identity
set f [open [file join $out repair_selection.txt] {WRONLY CREAT EXCL}]
puts $f "method=phys_opt_design -$method"
puts $f "source_sha256=$::env(HAP_SOURCE_DCP_SHA256)"
puts $f {scope=global native optimization; no source/XDC/clock/LOC/severity mutation}
close $f
if {![report_route_status -boolean_check ROUTED_FULLY] || [report_route_status -boolean_check ERRORS_IN_ROUTES]} {
    error {Hold repair requires a fully routed input with zero routing errors}
}
set failed [catch {phys_opt_design -$method} problem options]
# The first operation after a physical command is preservation, even on failure.
set post [file join $out post_physopt.dcp]
write_checkpoint $post
if {$failed} {catch {close_design};return -options $options $problem}
set fully [report_route_status -boolean_check ROUTED_FULLY]
set errors [report_route_status -boolean_check ERRORS_IN_ROUTES]
if {$fully ni {0 1} || $errors ni {0 1}} {error {Unknown route-status boolean}}
set skip [expr {$fully && !$errors}]
set f [open [file join $out route_decision.txt] {WRONLY CREAT EXCL}]
puts $f "ROUTED_FULLY=$fully ERRORS_IN_ROUTES=$errors"
puts $f "action=[expr {$skip ? {SKIPPED_ALREADY_FULLY_ROUTED} : {route_design -preserve}}]"
close $f
set failed 0
if {!$skip} {set failed [catch {route_design -preserve} problem options]}
set routed [file join $out [expr {$failed ? {failed_route.dcp} : {routed.dcp}}]]
if {$skip} {file copy $post $routed} else {write_checkpoint $routed}
if {$failed} {catch {close_design};return -options $options $problem}
# Reports and all publication checks happen only after the new scene is saved.
report_scene $out
set accepted [catch {require_timing $out} problem options]
close_design
if {$accepted} {
    puts {HOLD_REPAIR_REVIEW_REQUIRED: preserved checkpoint; no bitstream produced}
    return -options $options $problem
}
puts "SCALELLM_RELEASE_STAGE_PASS stage=$::env(HAP_STAGE)"
