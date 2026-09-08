# Read-only P9 geometry diagnosis against the authenticated P8 production DCP.

foreach variable {HAP_DCP HAP_P9_DIAG_DIR HAP_P9_INPUT_SHA
        HAP_P9_INPUT_MANIFEST_SHA256 HAP_EXPECTED_DCP_SHA256
        HAP_SELECTOR_LIB HAP_FINE19_LIB HAP_COMPOSITE20_LIB
        HAP_P8_PLACE_OUTPUT_SHA HAP_P8_PLACE_OUTPUT_SHA256 HAP_P9_LAUNCHER} {
    if {![info exists ::env($variable)] || $::env($variable) eq ""} {
        error "Missing required P9 diagnostic variable: $variable"
    }
}

set dcp [file normalize $::env(HAP_DCP)]
set out [file normalize $::env(HAP_P9_DIAG_DIR)]
set input_sha [file normalize $::env(HAP_P9_INPUT_SHA)]
set expected_input_sha $::env(HAP_P9_INPUT_MANIFEST_SHA256)
set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)
set selector_lib [file normalize $::env(HAP_SELECTOR_LIB)]
set fine_lib [file normalize $::env(HAP_FINE19_LIB)]
set composite_lib [file normalize $::env(HAP_COMPOSITE20_LIB)]
set p8_output_sha [file normalize $::env(HAP_P8_PLACE_OUTPUT_SHA)]
set expected_p8_output_sha $::env(HAP_P8_PLACE_OUTPUT_SHA256)
set launcher [file normalize $::env(HAP_P9_LAUNCHER)]
set diag_script [file normalize [info script]]
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
set anchor_range CLOCKREGION_X2Y5:CLOCKREGION_X4Y9

proc p9_require_file {path label} {
    if {![file exists $path] || ![file isfile $path] || [file size $path] == 0} {
        error "Missing or empty P9 $label: $path"
    }
}

proc p9_read {path label} {
    p9_require_file $path $label
    set fp [open $path r]
    set text [read $fp]
    close $fp
    return $text
}

proc p9_sha256 {path} {
    set digest [lindex [exec sha256sum -- $path] 0]
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "Malformed P9 SHA256: $path"
    }
    return $digest
}

proc p9_verify_manifest {path expected_count expected_sha label} {
    if {[p9_sha256 $path] ne $expected_sha} {
        error "P9 $label manifest identity mismatch"
    }
    set entries [dict create]
    foreach raw [split [p9_read $path $label] "\n"] {
        set line [string trim $raw]
        if {$line eq ""} {continue}
        if {![regexp {^([0-9a-f]{64})[[:space:]]+\*?(.+)$} \
                $line -> expected file_name]} {
            error "Malformed P9 $label row: $line"
        }
        set normalized [file normalize [string trim $file_name]]
        if {[dict exists $entries $normalized]} {
            error "Duplicate P9 $label path: $normalized"
        }
        p9_require_file $normalized "$label input"
        if {[p9_sha256 $normalized] ne $expected} {
            error "P9 $label SHA mismatch: $normalized"
        }
        dict set entries $normalized $expected
    }
    if {$expected_count >= 0 && [dict size $entries] != $expected_count} {
        error "P9 $label count mismatch: [dict size $entries]"
    }
    return $entries
}

proc p9_require_line {path literal} {
    set count 0
    foreach line [split [p9_read $path evidence] "\n"] {
        if {$line eq $literal} {incr count}
    }
    if {$count != 1} {
        error "P9 evidence line mismatch: path=$path literal=$literal count=$count"
    }
}

proc p9_count_ref {cells pattern} {
    if {[llength $cells] == 0} {return 0}
    set refs [get_property REF_NAME $cells]
    if {[llength $refs] != [llength $cells]} {
        error "P9 REF_NAME cardinality mismatch"
    }
    set count 0
    foreach ref_name $refs {
        if {[string match $pattern $ref_name]} {incr count}
    }
    return $count
}

proc p9_record {label cells} {
    set legal [hap_v5_fine19::pblockable $cells]
    return [dict create label $label cells $legal \
        member_count [llength $legal] lut [p9_count_ref $legal LUT*] \
        ff [p9_count_ref $legal FD*] dsp [p9_count_ref $legal DSP48E2] \
        ramb36 [p9_count_ref $legal RAMB36E2] \
        ramb18 [p9_count_ref $legal RAMB18E2] \
        uram [p9_count_ref $legal URAM288]]
}

proc p9_add_record {left right} {
    set result [dict create]
    foreach key {lut ff dsp ramb36 ramb18 uram} {
        dict set result $key [expr {[dict get $left $key] + [dict get $right $key]}]
    }
    return $result
}

proc p9_regions_for_range {range} {
    if {[regexp {^SLR([0-2])$} $range -> index]} {
        set slr [get_slrs -quiet $range]
        if {[llength $slr] != 1} {error "P9 SLR lookup failed: $range"}
        return [get_clock_regions -quiet -of_objects $slr]
    }
    if {![regexp \
            {^CLOCKREGION_X([0-9]+)Y([0-9]+):CLOCKREGION_X([0-9]+)Y([0-9]+)$} \
            $range -> x0 y0 x1 y1] || $x0 > $x1 || $y0 > $y1} {
        error "P9 malformed clock-region range: $range"
    }
    set regions {}
    for {set x $x0} {$x <= $x1} {incr x} {
        for {set y $y0} {$y <= $y1} {incr y} {
            set region [get_clock_regions -quiet X${x}Y${y}]
            if {[llength $region] != 1} {
                error "P9 clock-region lookup failed: X${x}Y${y}"
            }
            lappend regions [lindex $region 0]
        }
    }
    return $regions
}

proc p9_site_capacity {range} {
    array set counts {}
    foreach site [get_sites -quiet -of_objects [p9_regions_for_range $range]] {
        set type [get_property SITE_TYPE $site]
        if {![info exists counts($type)]} {set counts($type) 0}
        incr counts($type)
    }
    set slices 0
    set dsp 0
    set ramb36 0
    set ramb18 0
    set uram 0
    foreach type [array names counts] {
        if {[string match SLICE* $type]} {incr slices $counts($type)}
        if {[string match DSP* $type]} {incr dsp $counts($type)}
        if {[string match RAMB36* $type] ||
            [string match RAMBFIFO36* $type]} {incr ramb36 $counts($type)}
        if {[string match RAMB18* $type] ||
            [string match RAMBFIFO18* $type]} {incr ramb18 $counts($type)}
        if {[string match URAM* $type]} {incr uram $counts($type)}
    }
    return [dict create lut [expr {$slices * 8}] ff [expr {$slices * 16}] \
        dsp $dsp ramb36 $ramb36 ramb18 $ramb18 uram $uram]
}

proc p9_fits {demand capacity} {
    set bram36_equiv [expr {[dict get $demand ramb36] +
        ([dict get $demand ramb18] + 1) / 2}]
    return [expr {[dict get $demand lut] <= [dict get $capacity lut] &&
        [dict get $demand ff] <= [dict get $capacity ff] &&
        [dict get $demand dsp] <= [dict get $capacity dsp] &&
        $bram36_equiv <= [dict get $capacity ramb36] &&
        [dict get $demand ramb18] <= [dict get $capacity ramb18] &&
        [dict get $demand uram] <= [dict get $capacity uram]}]
}

proc p9_write_record {fp record} {
    puts $fp "collection=[dict get $record label]"
    foreach key {member_count lut ff dsp ramb36 ramb18 uram} {
        puts $fp "$key=[dict get $record $key]"
    }
    puts $fp ""
}

proc p9_interface_record {cell} {
    set pins [get_pins -quiet -of_objects $cell]
    set input_pins 0
    set output_pins 0
    foreach direction [get_property DIRECTION $pins] {
        if {$direction eq "IN"} {incr input_pins}
        if {$direction eq "OUT"} {incr output_pins}
    }
    set nets [hap_v5_floorplan::object_names [get_nets -quiet -of_objects $pins]]
    return [dict create input_pins $input_pins output_pins $output_pins \
        nets [llength $nets]]
}

if {![string match "2025.2*" [version -short]]} {
    error "P9 diagnosis requires Vivado 2025.2"
}
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "P9 diagnosis requires HAP_JOBS=32: $jobs"
}
if {[llength [get_designs -quiet]] != 0} {
    error "P9 diagnosis requires a fresh Vivado process"
}
set_param general.maxThreads $jobs

set frozen [p9_verify_manifest $input_sha 7 $expected_input_sha input]
foreach required [list $dcp $selector_lib $fine_lib $composite_lib \
        $p8_output_sha $diag_script $launcher] {
    if {![dict exists $frozen $required]} {
        error "Required P9 input absent from manifest: $required"
    }
}
if {[p9_sha256 $dcp] ne $expected_dcp_sha} {
    error "P9 DCP identity mismatch"
}

set p8_entries [p9_verify_manifest $p8_output_sha -1 \
    $expected_p8_output_sha p8_output]
set p8_dir [file dirname $p8_output_sha]
set p8_summary [file join $p8_dir summary.txt]
set p8_status [file join $p8_dir launcher_status.txt]
set p8_congestion [file join $p8_dir congestion_post_place.rpt]
foreach required [list $p8_summary $p8_status $p8_congestion] {
    if {![dict exists $p8_entries $required]} {
        error "Required P8 failure artifact absent from manifest: $required"
    }
}
foreach literal {status=FAIL acceptance_evidence=0 route_eligible=0
        checkpoint_written=0 congestion_level5_or_higher_windows=24
        congestion_level6_or_higher_windows=12} {
    p9_require_line $p8_summary $literal
}
foreach literal {status=FAIL final_exit_code=1 vivado_exit_code=1
        checkpoint_written=0 bitstream_generated=0} {
    p9_require_line $p8_status $literal
}

set flow_start_ms [clock milliseconds]
source $selector_lib
source $fine_lib
source $composite_lib
set phase_start_ms [clock milliseconds]
open_checkpoint $dcp
set open_checkpoint_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]
if {[llength [get_pblocks -quiet]] != 0} {
    error "P9 input DCP unexpectedly contains pblocks"
}

set phase_start_ms [clock milliseconds]
set base_plan [hap_v5_floorplan::discover P2_COHORT16_COL2_12_2]
set fine_plan [hap_v5_fine19::discover $base_plan]
set composite_plan [hap_v5_composite21::discover $base_plan $fine_plan]
set discovery_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]

set swiglu_roots [hap_v5_floorplan::module_cells \
    hap_mlp_swiglu_product_frontend16_q4]
set input_roots [hap_v5_floorplan::module_cells \
    hap_mlp_input_frontend16_compact_cache]
hap_v5_fine19::require_count p9_swiglu_roots $swiglu_roots 1
hap_v5_fine19::require_count p9_input_frontend_roots $input_roots 1
set swiglu_root [lindex $swiglu_roots 0]
set input_root [lindex $input_roots 0]

set swiglu_all [hap_v5_fine19::pblockable_descendants $swiglu_root]
set leaf_union [hap_v5_floorplan::list_union \
    [dict get $base_plan leaf0_primitives] [dict get $base_plan leaf1_primitives]]
set swiglu_central [hap_v5_floorplan::list_subtract $swiglu_all $leaf_union]
set input_frontend [hap_v5_fine19::pblockable_descendants $input_root]
set central_island [hap_v5_floorplan::list_union \
    $swiglu_central $input_frontend]

set mlp_residual [dict get $composite_plan mlp_residual_primitives]
set center_dsp [dict get $fine_plan nonprojection_center_dsp]
set movable_source [hap_v5_floorplan::list_union $mlp_residual $center_dsp]
set island_outside_source [hap_v5_floorplan::list_subtract \
    $central_island $movable_source]
set remaining_mlp [hap_v5_floorplan::list_subtract \
    $mlp_residual $central_island]
set remaining_center_dsp [hap_v5_floorplan::list_subtract \
    $center_dsp $central_island]
set candidate_partition [hap_v5_floorplan::list_union \
    $central_island $remaining_mlp $remaining_center_dsp]
set candidate_partition_ok [expr {
    [llength $island_outside_source] == 0 &&
    [hap_v5_floorplan::object_names $candidate_partition] eq
        [hap_v5_floorplan::object_names $movable_source]}]

set fine_specs [hap_v5_fine19::full_specs $base_plan $fine_plan]
set candidate_specs {}
set anchor_projection_cells {}
foreach spec $fine_specs {
    set name [dict get $spec name]
    if {$name eq "pb_v5_center_nonprojection_dsp_slr1"} {continue}
    lappend candidate_specs $spec
    if {$name in {
            pb_v5_attention_projection_center_region1_logic_cr_x2y5_x4y9
            pb_v5_attention_projection_center_region1_cols4_5_dsp_cr_x3y5_x4y9
            pb_v5_attention_projection_center_region1_cols6_7_dsp_cr_x2y5_x3y9
            pb_v5_attention_projection_owner_cr_x2y5_x4y9
            pb_v5_attention_projection_owner_region2_weight_cr_x2y5_x4y6}} {
        set anchor_projection_cells [hap_v5_floorplan::list_union \
            $anchor_projection_cells [dict get $spec cells]]
    }
}
lappend candidate_specs \
    [dict create name pb_v5_mlp_central_frontends_cr_x2y5_x4y9 target 1 \
        range $anchor_range cells $central_island] \
    [dict create name pb_v5_center_nonprojection_dsp_residual_slr1 target 1 \
        range SLR1 cells $remaining_center_dsp] \
    [dict create name pb_v5_mlp_residual_without_central_frontends_slr1 \
        target 1 range SLR1 cells $remaining_mlp]

set all_names {}
set member_sum 0
set covered_dsp {}
set covered_uram {}
set slr_dsp {0 0 0}
set slr_uram {0 0 0}
foreach spec $candidate_specs {
    set cells [hap_v5_fine19::pblockable [dict get $spec cells]]
    set names [hap_v5_floorplan::object_names $cells]
    set all_names [concat $all_names $names]
    incr member_sum [llength $names]
    set target [dict get $spec target]
    set dsps {}
    set urams {}
    foreach cell $cells ref_name [get_property REF_NAME $cells] {
        if {$ref_name eq "DSP48E2"} {lappend dsps $cell}
        if {$ref_name eq "URAM288"} {lappend urams $cell}
    }
    set covered_dsp [concat $covered_dsp $dsps]
    set covered_uram [concat $covered_uram $urams]
    lset slr_dsp $target [expr {[lindex $slr_dsp $target] + [llength $dsps]}]
    lset slr_uram $target [expr {[lindex $slr_uram $target] + [llength $urams]}]
}
set unique_names [lsort -dictionary -unique $all_names]
set member_overlap [expr {$member_sum - [llength $unique_names]}]
set design_dsp [hap_v5_floorplan::object_names \
    [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}]]
set design_uram [hap_v5_floorplan::object_names \
    [get_cells -quiet -hierarchical -filter {REF_NAME == URAM288}]]
set dsp_coverage [hap_v5_floorplan::object_names $covered_dsp]
set uram_coverage [hap_v5_floorplan::object_names $covered_uram]
set resource_ok [expr {$dsp_coverage eq $design_dsp &&
    $uram_coverage eq $design_uram && [llength $design_dsp] == 5453 &&
    [llength $design_uram] == 752 && $slr_dsp eq {1862 1781 1810} &&
    $slr_uram eq {224 224 304}}]

set swiglu_record [p9_record swiglu_central $swiglu_central]
set input_record [p9_record mlp_input_frontend $input_frontend]
set island_record [p9_record p9_central_island $central_island]
set mlp_remaining_record [p9_record mlp_residual_remaining $remaining_mlp]
set dsp_remaining_record [p9_record center_dsp_remaining $remaining_center_dsp]
set projection_record [p9_record anchor_projection_existing \
    $anchor_projection_cells]
set envelope_cells [hap_v5_floorplan::list_union \
    $anchor_projection_cells $central_island]
set envelope_record [p9_record anchor_combined_envelope $envelope_cells]
set anchor_capacity [p9_site_capacity $anchor_range]
set island_capacity_ok [p9_fits $island_record $anchor_capacity]
set envelope_capacity_ok [p9_fits $envelope_record $anchor_capacity]
set swiglu_interface [p9_interface_record $swiglu_root]
set input_interface [p9_interface_record $input_root]

set records_fp [open [file join $out candidate_resources.txt] w]
foreach record [list $swiglu_record $input_record $island_record \
        $mlp_remaining_record $dsp_remaining_record $projection_record \
        $envelope_record] {
    p9_write_record $records_fp $record
}
close $records_fp

set capacity_fp [open [file join $out candidate_capacity.txt] w]
puts $capacity_fp "anchor_range=$anchor_range"
foreach key {lut ff dsp ramb36 ramb18 uram} {
    puts $capacity_fp "anchor_${key}_capacity=[dict get $anchor_capacity $key]"
    puts $capacity_fp "island_${key}_demand=[dict get $island_record $key]"
    puts $capacity_fp "envelope_${key}_demand=[dict get $envelope_record $key]"
}
puts $capacity_fp "island_raw_capacity_ok=$island_capacity_ok"
puts $capacity_fp "envelope_raw_capacity_ok=$envelope_capacity_ok"
close $capacity_fp

set total_elapsed_ms [expr {[clock milliseconds] - $flow_start_ms}]
set status_ok [expr {$candidate_partition_ok &&
    [llength $candidate_specs] == 21 && $member_overlap == 0 &&
    $resource_ok && $island_capacity_ok && $envelope_capacity_ok &&
    [llength [get_pblocks -quiet]] == 0}]
set status [expr {$status_ok ? "P9_CENTRAL_GEOMETRY_DIAGNOSIS_PASS" : "FAIL"}]
set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] \
        stage P9_CENTRAL_GEOMETRY_READ_ONLY_DIAGNOSIS \
        evidence_class DIAGNOSTIC_NO_FLOORPLAN_MUTATION jobs $jobs \
        input_dcp $dcp input_dcp_sha256 $expected_dcp_sha \
        input_manifest_sha256 $expected_input_sha input_manifest_entries 7 \
        p8_place_manifest $p8_output_sha \
        p8_place_manifest_sha256 $expected_p8_output_sha \
        p8_place_verified 1 inherited_contract_variant \
            [dict get $composite_plan contract_variant] \
        fine_member_count [dict get $composite_plan fine_member_count] \
        mlp_residual_count [dict get $composite_plan mlp_residual_count] \
        attention_direct_count [dict get $composite_plan attention_direct_count] \
        anchor_range $anchor_range proposed_pblock_count \
            [llength $candidate_specs] proposed_member_count $member_sum \
        proposed_unique_member_count [llength $unique_names] \
        proposed_member_overlap $member_overlap \
        central_island_member_count [dict get $island_record member_count] \
        central_island_lut [dict get $island_record lut] \
        central_island_ff [dict get $island_record ff] \
        central_island_dsp [dict get $island_record dsp] \
        central_island_ramb36 [dict get $island_record ramb36] \
        mlp_remaining_member_count [dict get $mlp_remaining_record member_count] \
        center_dsp_remaining [dict get $dsp_remaining_record dsp] \
        candidate_partition_ok $candidate_partition_ok \
        island_outside_source [llength $island_outside_source] \
        anchor_island_capacity_ok $island_capacity_ok \
        anchor_envelope_capacity_ok $envelope_capacity_ok \
        swiglu_interface_input_pins [dict get $swiglu_interface input_pins] \
        swiglu_interface_output_pins [dict get $swiglu_interface output_pins] \
        swiglu_interface_nets [dict get $swiglu_interface nets] \
        input_interface_input_pins [dict get $input_interface input_pins] \
        input_interface_output_pins [dict get $input_interface output_pins] \
        input_interface_nets [dict get $input_interface nets] \
        dsp48e2 [llength $design_dsp] uram288 [llength $design_uram] \
        slr0_dsp48e2 [lindex $slr_dsp 0] slr1_dsp48e2 [lindex $slr_dsp 1] \
        slr2_dsp48e2 [lindex $slr_dsp 2] slr0_uram288 [lindex $slr_uram 0] \
        slr1_uram288 [lindex $slr_uram 1] slr2_uram288 [lindex $slr_uram 2] \
        resource_ok $resource_ok open_checkpoint_elapsed_ms \
            $open_checkpoint_elapsed_ms discovery_elapsed_ms \
            $discovery_elapsed_ms total_elapsed_ms $total_elapsed_ms \
        canonical_pblock_count_after [llength [get_pblocks -quiet]] \
        floorplan_mutated 0 implementation_commands_run 0 \
        checkpoint_written 0 status $status] {
    puts $fp "$key=$value"
}
close $fp
puts "P9_CENTRAL_GEOMETRY_DIAGNOSIS_COMPLETE STATUS=$status"
if {!$status_ok} {error "P9 central geometry diagnosis failed"}
close_design
