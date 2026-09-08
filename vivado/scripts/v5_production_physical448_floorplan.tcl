# P4 full-production physical-only 4/8/4 projection distribution.
#
# The RTL remains the frozen left2/center12/right2 hierarchy.  This layer moves
# the complete center region0 plus the projection frontend into SLR0 and the
# complete center region3 plus its local input staging into SLR2.  The two
# middle four-column regions and all remaining non-projection DSPs stay in
# SLR1.  It requires the production selector, projection geometry and Fine19
# generic pblock helpers to be sourced first.

namespace eval hap_v5_physical448 {
    variable contract_variant P4_COHORT16_PHYSICAL4_8_4_19
    variable expected_base_variant P2_COHORT16_COL2_12_2
    variable expected_dsp_distribution {2198 1173 2082}
    variable expected_uram_distribution {224 224 304}
    variable region0_range CLOCKREGION_X4Y0:CLOCKREGION_X5Y4
    variable region3_range CLOCKREGION_X0Y10:CLOCKREGION_X1Y14
}

proc hap_v5_physical448::require_count {label values expected} {
    set actual [llength $values]
    if {$actual != $expected} {
        error "V5 physical448 $label count mismatch: expected=$expected actual=$actual"
    }
    return $actual
}

proc hap_v5_physical448::projection_specs {geometry_plan} {
    variable region0_range
    variable region3_range
    set result {}
    foreach spec [hap_projection_ooc_floorplan::specs $geometry_plan p4_] {
        set key [dict get $spec key]
        if {$key eq "center_region0_frontend_primitives"} {
            dict set spec name \
                p4_pb_projection_center_region0_frontend_cr_x4y0_x5y4
            dict set spec target 0
            dict set spec range $region0_range
        } elseif {$key eq "center_region3_floorplan_primitives"} {
            dict set spec name \
                p4_pb_projection_center_region3_shared_cr_x0y10_x1y14
            dict set spec target 2
            dict set spec range $region3_range
        }
        lappend result $spec
    }
    require_count projection_specs $result 10
    return $result
}

proc hap_v5_physical448::discover {base_plan geometry_plan} {
    variable contract_variant
    variable expected_base_variant
    variable expected_dsp_distribution
    variable expected_uram_distribution

    if {[dict get $base_plan contract_variant] ne $expected_base_variant ||
        [dict get $base_plan total_dsp] != 5453 ||
        [dict get $base_plan total_uram] != 752 ||
        [dict get $base_plan kernel_dsp] != 3072} {
        error "V5 physical448 base architecture identity mismatch"
    }
    if {![hap_projection_ooc_floorplan::region0_input_localization_ok \
            $geometry_plan] ||
        ![hap_projection_ooc_floorplan::region3_input_localization_ok \
            $geometry_plan] ||
        ![hap_projection_ooc_floorplan::owner_region2_weight_anchor_ok \
            $geometry_plan]} {
        error "V5 physical448 requires the qualified P3 projection geometry"
    }

    # The base center collection contains all center12 primitives plus the 149
    # DSPs not assigned to the outer MLP/Attention owners.  The P3 projection
    # frontend owns 64 of those DSPs; after it moves to SLR0, exactly 85 DSPs
    # remain as the SLR1 non-projection residue.
    set center_extra_all [hap_v5_floorplan::list_subtract \
        [dict get $base_plan center_primitives] \
        [dict get $geometry_plan center_primitives]]
    set center_extra {}
    foreach cell $center_extra_all {
        if {[get_property REF_NAME $cell] eq "DSP48E2"} {
            lappend center_extra $cell
        }
    }
    set center_extra [lsort -dictionary -unique $center_extra]
    set center_extra_dsp [hap_v5_floorplan::count_ref $center_extra DSP48E2]
    set frontend_overlap [hap_v5_floorplan::list_intersection \
        $center_extra [dict get $geometry_plan frontend_primitives]]
    set frontend_overlap_dsp \
        [hap_v5_floorplan::count_ref $frontend_overlap DSP48E2]
    set center_residual [hap_v5_floorplan::list_subtract \
        $center_extra [dict get $geometry_plan frontend_primitives]]
    set center_residual_dsp \
        [hap_v5_floorplan::count_ref $center_residual DSP48E2]
    if {[llength $center_extra] != 149 || $center_extra_dsp != 149 ||
        [llength $frontend_overlap] != 64 || $frontend_overlap_dsp != 64 ||
        [llength $center_residual] != 85 || $center_residual_dsp != 85} {
        error "V5 physical448 center-DSP partition mismatch: extra=[llength $center_extra]/$center_extra_dsp frontend=[llength $frontend_overlap]/$frontend_overlap_dsp residual=[llength $center_residual]/$center_residual_dsp"
    }

    set specs [list \
        [dict create name pb_v5_mlp_branch_slr0 target 0 range SLR0 \
            cells [dict get $base_plan outer0_primitives]] \
        [dict create name pb_v5_mlp_branch_slr2 target 2 range SLR2 \
            cells [dict get $base_plan outer2_primitives]]]
    set specs [concat $specs [projection_specs $geometry_plan]]
    lappend specs \
        [dict create name pb_v5_center_nonprojection_dsp_slr1 target 1 \
            range SLR1 cells $center_residual] \
        [dict create name pb_v5_meta_gate_slr0 target 0 range SLR0 \
            cells [dict get $base_plan gate0_primitives]] \
        [dict create name pb_v5_meta_gate_slr2 target 2 range SLR2 \
            cells [dict get $base_plan gate2_primitives]] \
        [dict create name pb_v5_meta_down0_slr1 target 1 range SLR1 \
            cells [dict get $base_plan down0_primitives]] \
        [dict create name pb_v5_meta_down1_slr1 target 1 range SLR1 \
            cells [dict get $base_plan down1_primitives]] \
        [dict create name pb_v5_attention_meta_slr2 target 2 range SLR2 \
            cells [dict get $base_plan attention_meta_primitives]] \
        [dict create name pb_v5_attention_row_kv_cache_slr0 target 0 \
            range SLR0 cells [dict get $base_plan attention_island_primitives]]
    require_count full_specs $specs 19

    set dsp_distribution {0 0 0}
    set uram_distribution {0 0 0}
    set member_sum 0
    set member_union {}
    foreach spec $specs {
        set cells [hap_v5_fine19::pblockable [dict get $spec cells]]
        set target [dict get $spec target]
        lset dsp_distribution $target [expr {
            [lindex $dsp_distribution $target] +
            [hap_v5_floorplan::count_ref $cells DSP48E2]}]
        lset uram_distribution $target [expr {
            [lindex $uram_distribution $target] +
            [hap_v5_floorplan::count_ref $cells URAM288]}]
        incr member_sum [llength $cells]
        set member_union [concat $member_union $cells]
    }
    set member_union [lsort -dictionary -unique $member_union]
    set member_overlap [expr {$member_sum - [llength $member_union]}]
    if {$member_overlap != 0 ||
        $dsp_distribution ne $expected_dsp_distribution ||
        $uram_distribution ne $expected_uram_distribution} {
        error "V5 physical448 plan mismatch: overlap=$member_overlap DSP=$dsp_distribution URAM=$uram_distribution"
    }

    return [dict create contract_variant $contract_variant specs $specs \
        pblock_count [llength $specs] member_count $member_sum \
        member_overlap $member_overlap \
        center_extra_dsp $center_extra_dsp \
        moved_frontend_dsp $frontend_overlap_dsp \
        center_residual_dsp $center_residual_dsp \
        projected_slr_dsp $dsp_distribution \
        projected_slr_uram $uram_distribution \
        region0_target 0 region3_target 2]
}

proc hap_v5_physical448::apply {physical_plan} {
    hap_v5_fine19::apply_specs [dict get $physical_plan specs]
}

proc hap_v5_physical448::audit {physical_plan require_placed} {
    return [hap_v5_fine19::audit_specs [dict get $physical_plan specs] \
        [dict get $physical_plan contract_variant] $require_placed]
}

proc hap_v5_physical448::physical_metrics {physical_plan audit} {
    variable expected_dsp_distribution
    variable expected_uram_distribution
    if {![dict get $audit require_placed] ||
        [dict get $audit contract_variant] ne \
            [dict get $physical_plan contract_variant]} {
        error "V5 physical448 requires its placed audit"
    }
    set global [hap_v5_floorplan::physical_slr_audit_for_cells \
        [get_cells -quiet -hierarchical -filter {IS_PRIMITIVE}]]
    set dsp [hap_v5_floorplan::placed_slr_counts DSP48E2]
    set uram [hap_v5_floorplan::placed_slr_counts URAM288]
    return [dict create slr_dsp $dsp slr_uram $uram \
        expected_slr_dsp $expected_dsp_distribution \
        expected_slr_uram $expected_uram_distribution \
        wrong_total [dict get $audit placed_wrong] \
        unplaced [dict get $global direct_slr_empty] \
        virtual_total [dict get $global virtual_total] \
        physical_count [dict get $global physical_count]]
}

proc hap_v5_physical448::physical_ok {metrics} {
    variable expected_dsp_distribution
    variable expected_uram_distribution
    return [expr {[dict get $metrics wrong_total] == 0 &&
        [dict get $metrics unplaced] == 0 &&
        [dict get $metrics slr_dsp] eq $expected_dsp_distribution &&
        [dict get $metrics slr_uram] eq $expected_uram_distribution}]
}

proc hap_v5_physical448::write_plan {physical_plan path marker} {
    set fp [open $path w]
    puts $fp "status=$marker"
    foreach key {contract_variant pblock_count member_count member_overlap
            center_extra_dsp moved_frontend_dsp center_residual_dsp
            projected_slr_dsp projected_slr_uram region0_target
            region3_target} {
        puts $fp "$key=[dict get $physical_plan $key]"
    }
    foreach spec [dict get $physical_plan specs] {
        set name [dict get $spec name]
        set cells [hap_v5_fine19::pblockable [dict get $spec cells]]
        puts $fp "${name}_target=[dict get $spec target]"
        puts $fp "${name}_range=[dict get $spec range]"
        puts $fp "${name}_members=[llength $cells]"
        puts $fp "${name}_dsp48e2=[hap_v5_floorplan::count_ref $cells DSP48E2]"
        puts $fp "${name}_uram288=[hap_v5_floorplan::count_ref $cells URAM288]"
    }
    close $fp
}
