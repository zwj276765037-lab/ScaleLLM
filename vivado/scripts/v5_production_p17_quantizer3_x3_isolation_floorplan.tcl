# Mission 0195 keeps the P16 no-clip quantizer identity but removes its
# clock-region overlap with Attention Region2. Quantizer3 has no DSP/BRAM/URAM
# in the authenticated format-v3 DCP, so the X3-only SLR1 column is legal.

set p17_quantizer3_script_dir [file dirname [file normalize [info script]]]
source [file join $p17_quantizer3_script_dir \
    v5_production_p16_noclip_quantizer3_locality_floorplan.tcl]

namespace eval hap_v5_p9_quantizer3_locality {
    variable contract P17_SWIGLU_QUANTIZER3_X3Y5_X3Y9
    variable pblock_name pb_v5_p17_swiglu_quantizer3_cr_x3y5_x3y9
    variable grid_range CLOCKREGION_X3Y5:CLOCKREGION_X3Y9
    variable allowed_regions {X3Y5 X3Y6 X3Y7 X3Y8 X3Y9}
}

namespace eval hap_v5_p17_quantizer3_isolation {
    variable region2_regions {
        X0Y5 X0Y6 X0Y7 X0Y8 X0Y9
        X1Y5 X1Y6 X1Y7 X1Y8 X1Y9
        X2Y5 X2Y6 X2Y7 X2Y8 X2Y9
    }
}

proc hap_v5_p17_quantizer3_isolation::audit_contract {} {
    variable region2_regions
    set contract [namespace eval ::hap_v5_p9_quantizer3_locality {
        set contract
    }]
    set pblock_name [namespace eval ::hap_v5_p9_quantizer3_locality {
        set pblock_name
    }]
    set grid_range [namespace eval ::hap_v5_p9_quantizer3_locality {
        set grid_range
    }]
    set quantizer_regions [namespace eval ::hap_v5_p9_quantizer3_locality {
        set allowed_regions
    }]
    if {$contract ne "P17_SWIGLU_QUANTIZER3_X3Y5_X3Y9" ||
        $pblock_name ne "pb_v5_p17_swiglu_quantizer3_cr_x3y5_x3y9" ||
        $grid_range ne "CLOCKREGION_X3Y5:CLOCKREGION_X3Y9" ||
        $quantizer_regions ne {X3Y5 X3Y6 X3Y7 X3Y8 X3Y9}} {
        error "P17 quantizer3 isolation constants changed"
    }
    set overlap {}
    foreach region $quantizer_regions {
        if {[lsearch -exact $region2_regions $region] >= 0} {
            lappend overlap $region
        }
    }
    if {[llength $overlap] != 0} {
        error "P17 quantizer3 overlaps Attention Region2: $overlap"
    }
    return [dict create ok 1 contract $contract pblock_name $pblock_name \
        grid_range $grid_range quantizer_regions $quantizer_regions \
        attention_region2_regions $region2_regions overlap_count 0]
}
