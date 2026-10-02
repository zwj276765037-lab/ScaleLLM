# Bind production floorplan discovery to an authenticated P16 post-opt
# signature. The underlying adapter validates all region2 partitions.

set p16_bound_script_dir [file dirname [file normalize [info script]]]
foreach variable {HAP_P16_POST_OPT_SUMMARY HAP_P16_POST_OPT_SUMMARY_SHA256} {
    if {![info exists ::env($variable)] || $::env($variable) eq ""} {
        error "P16 bound floorplan requires $variable"
    }
}

source [file join $p16_bound_script_dir \
    projection_core16x16_w8_reuse_ooc_p16_floorplan.tcl]

set p16_bound_summary [file normalize $::env(HAP_P16_POST_OPT_SUMMARY)]
set p16_bound_sha256 $::env(HAP_P16_POST_OPT_SUMMARY_SHA256)
hap_projection_ooc_p16_floorplan::configure_from_post_opt_summary \
    $p16_bound_summary $p16_bound_sha256

set production_region2_variables {
    HAP_P16_PRODUCTION_REGION2_SUMMARY
    HAP_P16_PRODUCTION_REGION2_SUMMARY_SHA256
    HAP_P16_PRODUCTION_DCP_SHA256
}
set production_region2_present 0
foreach variable $production_region2_variables {
    if {[info exists ::env($variable)] && $::env($variable) ne ""} {
        incr production_region2_present
    }
}
if {$production_region2_present != 0 &&
    $production_region2_present != [llength $production_region2_variables]} {
    error "P16 production region2 binding is incomplete"
}
if {$production_region2_present != 0} {
    hap_projection_ooc_p16_floorplan::configure_region2_from_production_summary \
        $::env(HAP_P16_PRODUCTION_REGION2_SUMMARY) \
        $::env(HAP_P16_PRODUCTION_REGION2_SUMMARY_SHA256) \
        $::env(HAP_P16_PRODUCTION_DCP_SHA256)
}

set p16_bound_source \
    [hap_projection_ooc_floorplan::get_region2_signature_source]
if {$p16_bound_source ne "P16_POST_OPT_SHA256:$p16_bound_sha256"} {
    if {$production_region2_present == 0} {
        error "P16 bound floorplan did not retain signature provenance"
    }
    set expected_production_source \
        "P16_PRODUCTION_POST_OPT_SHA256:$::env(HAP_P16_PRODUCTION_REGION2_SUMMARY_SHA256)"
    if {$p16_bound_source ne $expected_production_source} {
        error "P16 bound floorplan did not retain production signature provenance"
    }
}
