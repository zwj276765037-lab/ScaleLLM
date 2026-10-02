# P16 adapter for the shared projection OOC floorplan.  The adapter refuses
# to configure region2 from unversioned or unauthenticated structure data.
set p16_floorplan_script_dir [file dirname [file normalize [info script]]]
source [file join $p16_floorplan_script_dir \
    projection_core16x16_w8_reuse_ooc_floorplan.tcl]

namespace eval hap_projection_ooc_p16_floorplan {
    variable summary_sha256 ""
    variable production_region2_summary_sha256 ""
}

proc hap_projection_ooc_p16_floorplan::read_summary {path} {
    set fp [open $path r]
    set text [read $fp]
    close $fp
    set values [dict create]
    foreach raw [split $text "\n"] {
        set line [string trim $raw]
        if {$line eq ""} {continue}
        if {![regexp {^([^=]+)=(.*)$} $line -> key value]} {
            error "invalid P16 post-opt summary line: $line"
        }
        if {[dict exists $values $key]} {
            error "duplicate P16 post-opt summary key: $key"
        }
        dict set values $key $value
    }
    return $values
}

proc hap_projection_ooc_p16_floorplan::require_value {
        values key expected} {
    if {![dict exists $values $key] || [dict get $values $key] ne $expected} {
        set actual MISSING
        if {[dict exists $values $key]} {set actual [dict get $values $key]}
        error "P16 post-opt summary mismatch: key=$key expected=$expected actual=$actual"
    }
}

proc hap_projection_ooc_p16_floorplan::require_nonzero_integer {
        values key} {
    if {![dict exists $values $key]} {
        error "P16 post-opt summary is missing '$key'"
    }
    set value [dict get $values $key]
    if {![string is integer -strict $value] || $value <= 0} {
        error "P16 post-opt summary '$key' is not a positive integer: $value"
    }
    return $value
}

proc hap_projection_ooc_p16_floorplan::configure_from_post_opt_summary {
        path expected_sha256} {
    variable summary_sha256
    set normalized [file normalize $path]
    if {![file exists $normalized] || [file size $normalized] == 0} {
        error "missing P16 post-opt summary: $normalized"
    }
    set actual_sha256 [lindex [exec sha256sum -- $normalized] 0]
    if {![regexp {^[0-9a-f]{64}$} $expected_sha256] ||
        $actual_sha256 ne $expected_sha256} {
        error "P16 post-opt summary SHA256 mismatch"
    }
    set values [read_summary $normalized]
    foreach {key expected} {
        stage P16_100MHZ_POST_OPT_STRUCTURE_PROBE
        part xcvu9p-flga2104-2L-e
        jobs 32
        clock_mhz 100
        attention_lane_instances 128
        local_dual_accumulator_instances 6
        local_accumulator_contexts 12
        dut_dsp48e2 2240
        array_dsp48e2 2176
        frontend_dsp48e2 64
        frontend_hadamard_dsp48e2 64
        frontend_quantizer_dsp48e2 0
        region2_lane_instances 32
        region2_lower_bank_instances 1
        region2_upper_bank_instances 1
        old_floorplan_discover_called 0
        place_authorized 0
        route_authorized 0
        drc_errors 0
        status PASS
    } {
        require_value $values $key $expected
    }
    hap_projection_ooc_floorplan::configure_dsp_signature \
        [dict get $values frontend_dsp48e2] {272 1696 272} \
        "P16_POST_OPT_SHA256:$actual_sha256"
    foreach key {synthesized_buffer_primitives synthesized_buffer_ff
            synthesized_buffer_payload_ff synthesized_buffer_occupancy_ff} {
        require_nonzero_integer $values $key
    }
    set lane_min [require_nonzero_integer $values \
        region2_lane_min_primitives]
    set lane_max [require_nonzero_integer $values \
        region2_lane_max_primitives]
    if {$lane_min != $lane_max} {
        error "P16 region2 lane primitive signatures are not uniform"
    }
    set signature [dict create \
        total_primitives [require_nonzero_integer $values region2_primitives] \
        total_lut [require_nonzero_integer $values region2_lut_primitives] \
        total_ff [require_nonzero_integer $values region2_ff_primitives] \
        total_dsp [require_nonzero_integer $values region2_dsp48e2] \
        lane_primitives $lane_min lane_dsp 17 \
        rows0_3_primitives [require_nonzero_integer $values \
            region2_rows0_3_primitives] \
        rows0_3_lut [require_nonzero_integer $values region2_rows0_3_lut] \
        rows0_3_ff [require_nonzero_integer $values region2_rows0_3_ff] \
        rows0_3_dsp [require_nonzero_integer $values \
            region2_rows0_3_dsp48e2] \
        rows4_7_primitives [require_nonzero_integer $values \
            region2_rows4_7_primitives] \
        rows4_7_lut [require_nonzero_integer $values region2_rows4_7_lut] \
        rows4_7_ff [require_nonzero_integer $values region2_rows4_7_ff] \
        rows4_7_dsp [require_nonzero_integer $values \
            region2_rows4_7_dsp48e2] \
        residual_primitives [require_nonzero_integer $values \
            region2_residual_primitives] \
        residual_lut [require_nonzero_integer $values region2_residual_lut] \
        residual_ff [require_nonzero_integer $values region2_residual_ff] \
        residual_dsp [dict get $values region2_residual_dsp48e2]]
    hap_projection_ooc_floorplan::configure_region2_signature $signature \
        "P16_POST_OPT_SHA256:$actual_sha256"
    set summary_sha256 $actual_sha256
    return $values
}

proc hap_projection_ooc_p16_floorplan::configure_region2_from_production_summary {
        path expected_sha256 expected_dcp_sha256} {
    variable production_region2_summary_sha256
    set normalized [file normalize $path]
    if {![file exists $normalized] || [file size $normalized] == 0} {
        error "missing P16 production region2 summary: $normalized"
    }
    set actual_sha256 [lindex [exec sha256sum -- $normalized] 0]
    if {![regexp {^[0-9a-f]{64}$} $expected_sha256] ||
        $actual_sha256 ne $expected_sha256} {
        error "P16 production region2 summary SHA256 mismatch"
    }
    if {![regexp {^[0-9a-f]{64}$} $expected_dcp_sha256]} {
        error "P16 production region2 DCP SHA256 is malformed"
    }
    set values [read_summary $normalized]
    foreach {key expected} [list \
        stage P16_PRODUCTION_POST_OPT_REGION2_SIGNATURE_PROBE \
        part xcvu9p-flga2104-2L-e \
        top hap_attention_mlp_production_core \
        jobs 32 \
        input_dcp_sha256 $expected_dcp_sha256 \
        projection_instances 1 \
        attention_lane_instances 128 \
        local_dual_accumulator_instances 6 \
        local_accumulator_contexts 12 \
        dut_dsp48e2 2240 \
        array_dsp48e2 2176 \
        frontend_dsp48e2 64 \
        frontend_quantizer_dsp48e2 0 \
        region2_lane_instances 32 \
        region2_lower_bank_instances 1 \
        region2_upper_bank_instances 1 \
        region2_dsp48e2 544 \
        region2_rows0_3_dsp48e2 272 \
        region2_rows4_7_dsp48e2 272 \
        region2_residual_dsp48e2 0 \
        region2_lane_min_dsp48e2 17 \
        region2_lane_max_dsp48e2 17 \
        synthesized_buffer_primitives 4086 \
        synthesized_buffer_ff 2696 \
        synthesized_buffer_payload_ff 2688 \
        synthesized_buffer_tag_ff 6 \
        synthesized_buffer_occupancy_ff 2 \
        drc_errors 0 \
        partition_exact_cover 1 \
        implementation_commands_run 0 \
        checkpoint_written 0 \
        place_authorized 0 \
        route_authorized 0 \
        status V5_P16_PRODUCTION_REGION2_POST_OPT_PROBE_PASS] {
        require_value $values $key $expected
    }
    set lane_min [require_nonzero_integer $values \
        region2_lane_min_primitives]
    set lane_max [require_nonzero_integer $values \
        region2_lane_max_primitives]
    if {$lane_min != $lane_max} {
        error "P16 production region2 lane signatures are not uniform"
    }
    set signature [dict create \
        total_primitives [require_nonzero_integer $values region2_primitives] \
        total_lut [require_nonzero_integer $values region2_lut_primitives] \
        total_ff [require_nonzero_integer $values region2_ff_primitives] \
        total_dsp [require_nonzero_integer $values region2_dsp48e2] \
        lane_primitives $lane_min lane_dsp 17 \
        rows0_3_primitives [require_nonzero_integer $values \
            region2_rows0_3_primitives] \
        rows0_3_lut [require_nonzero_integer $values region2_rows0_3_lut] \
        rows0_3_ff [require_nonzero_integer $values region2_rows0_3_ff] \
        rows0_3_dsp 272 \
        rows4_7_primitives [require_nonzero_integer $values \
            region2_rows4_7_primitives] \
        rows4_7_lut [require_nonzero_integer $values region2_rows4_7_lut] \
        rows4_7_ff [require_nonzero_integer $values region2_rows4_7_ff] \
        rows4_7_dsp 272 \
        residual_primitives [require_nonzero_integer $values \
            region2_residual_primitives] \
        residual_lut [require_nonzero_integer $values region2_residual_lut] \
        residual_ff [require_nonzero_integer $values region2_residual_ff] \
        residual_dsp 0]
    hap_projection_ooc_floorplan::configure_region2_signature $signature \
        "P16_PRODUCTION_POST_OPT_SHA256:$actual_sha256"
    set production_region2_summary_sha256 $actual_sha256
    return $values
}
