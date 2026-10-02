# Preserve the P14 same-SLR X2 relief geometry while deriving the exact
# region2 primitive identity from the authenticated P16 post-opt signature.

set p16_relief_script_dir [file dirname [file normalize [info script]]]
source [file join $p16_relief_script_dir \
    v5_production_p14_region2_x2_relief_floorplan.tcl]

proc hap_v5_p14_region2_relief::discover {geometry_plan} {
    variable contract
    variable pblock_name
    variable base_range
    variable relief_range
    variable expected_range
    set signature_source \
        [hap_projection_ooc_floorplan::get_region2_signature_source]
    if {![regexp {^P16_(PRODUCTION_)?POST_OPT_SHA256:[0-9a-f]{64}$} \
            $signature_source]} {
        error "P16 no-clip region2 relief requires fresh P16 provenance"
    }
    set cells [dict get $geometry_plan center_region2_primitives]
    set lut [hap_projection_ooc_floorplan::count_ref_glob $cells LUT*]
    set ff [hap_projection_ooc_floorplan::count_ref_glob $cells FD*]
    set dsp [hap_projection_ooc_floorplan::count_ref $cells DSP48E2]
    if {[llength $cells] == 0 || $lut == 0 || $ff == 0 || $dsp != 544 ||
        [hap_projection_ooc_floorplan::count_ref $cells URAM288] != 0} {
        error "P16 no-clip region2 signature mismatch: primitives=[llength $cells] LUT=$lut FF=$ff DSP=$dsp"
    }
    return [dict create contract $contract pblock_name $pblock_name \
        base_range $base_range relief_range $relief_range \
        expected_range $expected_range primitives $cells \
        primitive_count [llength $cells] lut $lut ff $ff dsp $dsp \
        signature_source $signature_source]
}
