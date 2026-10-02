set script_dir [file dirname [file normalize [info script]]]
set dcp [file normalize $::env(HAP_DCP)]
set out [file normalize $::env(HAP_FINE19_PROBE_DIR)]
set input_sha [file normalize $::env(HAP_FINE19_INPUT_SHA)]
set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)
set expected_manifest_sha $::env(HAP_FINE19_INPUT_MANIFEST_SHA256)
set selector_lib [file normalize $::env(HAP_FINE19_SELECTOR_LIB)]
set fine_lib [file normalize $::env(HAP_FINE19_LIB)]
set composite21_lib [file normalize $::env(HAP_COMPOSITE21_LIB)]
set post_opt_audit_sha \
    [file normalize $::env(HAP_POST_OPT_AUDIT_OUTPUT_SHA)]
set expected_post_opt_audit_sha \
    $::env(HAP_POST_OPT_AUDIT_OUTPUT_SHA256)
set p9_diag_output_sha [file normalize $::env(HAP_P9_DIAG_OUTPUT_SHA)]
set expected_p9_diag_output_sha $::env(HAP_P9_DIAG_OUTPUT_SHA256)
set probe_script [file normalize [info script]]
set launcher [file normalize $::env(HAP_FINE19_LAUNCHER)]
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]

proc hap_fine19_require_nonempty_file {path label} {
    if {![file exists $path] || ![file isfile $path] ||
        [file size $path] == 0} {
        error "Missing or empty $label: $path"
    }
}

proc hap_fine19_read_nonempty {path label} {
    hap_fine19_require_nonempty_file $path $label
    set fp [open $path r]
    set text [read $fp]
    close $fp
    return $text
}

proc hap_fine19_sha256 {path} {
    set digest [lindex [exec sha256sum -- $path] 0]
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "Malformed SHA256 for $path: $digest"
    }
    return $digest
}

proc hap_fine19_verify_manifest {path expected_count expected_sha} {
    if {[hap_fine19_sha256 $path] ne $expected_sha} {
        error "V5 fine19 input manifest digest mismatch"
    }
    set entries [dict create]
    foreach raw [split [hap_fine19_read_nonempty $path input_manifest] "\n"] {
        set line [string trim $raw]
        if {$line eq ""} {continue}
        if {![regexp {^([0-9a-f]{64})[[:space:]]+\*?(.+)$} \
                $line -> expected file_name]} {
            error "Malformed V5 fine19 manifest row: $line"
        }
        set normalized [file normalize [string trim $file_name]]
        if {[dict exists $entries $normalized]} {
            error "Duplicate V5 fine19 input: $normalized"
        }
        hap_fine19_require_nonempty_file $normalized frozen_input
        if {[hap_fine19_sha256 $normalized] ne $expected} {
            error "V5 fine19 input SHA mismatch: $normalized"
        }
        dict set entries $normalized $expected
    }
    if {$expected_count >= 0 && [dict size $entries] != $expected_count} {
        error "V5 fine19 input count mismatch: [dict size $entries]"
    }
    return $entries
}

proc hap_fine19_require_line {path literal} {
    set count 0
    foreach line [split [hap_fine19_read_nonempty $path evidence] "\n"] {
        if {$line eq $literal} {incr count}
    }
    if {$count != 1} {
        error "V5 evidence line mismatch: $path literal=$literal count=$count"
    }
}

proc hap_fine19_count_ref_pattern {cells pattern} {
    set count 0
    set cell_count [llength $cells]
    if {$cell_count == 0} {return 0}
    set refs [get_property REF_NAME $cells]
    if {[llength $refs] != $cell_count} {
        error "V5 fine19 pattern REF_NAME cardinality mismatch"
    }
    foreach ref_name $refs {
        if {[string match $pattern $ref_name]} {
            incr count
        }
    }
    return $count
}

proc hap_fine19_regions_for_range {range} {
    if {[regexp {^SLR([0-2])$} $range -> index]} {
        set slr [get_slrs -quiet $range]
        if {[llength $slr] != 1} {
            error "V5 fine19 SLR range lookup failed: $range"
        }
        return [get_clock_regions -quiet -of_objects $slr]
    }
    if {![regexp \
            {^CLOCKREGION_X([0-9]+)Y([0-9]+):CLOCKREGION_X([0-9]+)Y([0-9]+)$} \
            $range -> x0 y0 x1 y1] || $x0 > $x1 || $y0 > $y1} {
        error "V5 fine19 malformed clock-region range: $range"
    }
    set regions {}
    for {set x $x0} {$x <= $x1} {incr x} {
        for {set y $y0} {$y <= $y1} {incr y} {
            set region [get_clock_regions -quiet X${x}Y${y}]
            if {[llength $region] != 1} {
                error "V5 fine19 clock-region lookup failed: X${x}Y${y}"
            }
            lappend regions [lindex $region 0]
        }
    }
    return $regions
}

proc hap_fine19_region_slr_index {regions} {
    set names {}
    foreach region $regions {
        set slrs [get_slrs -quiet -of_objects $region]
        if {[llength $slrs] != 1} {
            error "V5 fine19 region has no unique SLR: $region"
        }
        lappend names [get_property NAME [lindex $slrs 0]]
    }
    set names [lsort -dictionary -unique $names]
    if {[llength $names] != 1 ||
        ![regexp {^SLR([0-2])$} [lindex $names 0] -> index]} {
        error "V5 fine19 range crosses SLRs: $names"
    }
    return $index
}

proc hap_fine19_site_capacity {regions} {
    array set counts {}
    foreach site [get_sites -quiet -of_objects $regions] {
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

proc hap_fine19_write_spec {fp spec} {
    set name [dict get $spec name]
    set target [dict get $spec target]
    set range [dict get $spec range]
    set soft [hap_v5_fine19::spec_is_soft $spec]
    set cells [hap_v5_fine19::pblockable [dict get $spec cells]]
    set regions [hap_fine19_regions_for_range $range]
    set range_target [hap_fine19_region_slr_index $regions]
    set capacity [hap_fine19_site_capacity $regions]
    set lut [hap_fine19_count_ref_pattern $cells LUT*]
    set ff [hap_fine19_count_ref_pattern $cells FD*]
    set dsp [hap_fine19_count_ref_pattern $cells DSP48E2]
    set ramb36 [hap_fine19_count_ref_pattern $cells RAMB36E2]
    set ramb18 [hap_fine19_count_ref_pattern $cells RAMB18E2]
    set uram [hap_fine19_count_ref_pattern $cells URAM288]
    set bram36_equiv [expr {$ramb36 + ($ramb18 + 1) / 2}]
    set capacity_ok [expr {$lut <= [dict get $capacity lut] &&
        $ff <= [dict get $capacity ff] &&
        $dsp <= [dict get $capacity dsp] &&
        $bram36_equiv <= [dict get $capacity ramb36] &&
        $ramb18 <= [dict get $capacity ramb18] &&
        $uram <= [dict get $capacity uram]}]
    puts $fp "pblock=$name"
    puts $fp "target_slr=$target"
    puts $fp "soft=$soft"
    puts $fp "range=$range"
    puts $fp "range_slr=$range_target"
    puts $fp "member_count=[llength $cells]"
    puts $fp "lut_demand=$lut"
    puts $fp "ff_demand=$ff"
    puts $fp "dsp_demand=$dsp"
    puts $fp "ramb36_demand=$ramb36"
    puts $fp "ramb18_demand=$ramb18"
    puts $fp "uram_demand=$uram"
    puts $fp "lut_capacity=[dict get $capacity lut]"
    puts $fp "ff_capacity=[dict get $capacity ff]"
    puts $fp "dsp_capacity=[dict get $capacity dsp]"
    puts $fp "ramb36_capacity=[dict get $capacity ramb36]"
    puts $fp "ramb18_capacity=[dict get $capacity ramb18]"
    puts $fp "uram_capacity=[dict get $capacity uram]"
    puts $fp "raw_capacity_ok=$capacity_ok"
    puts $fp ""
    return [dict create name $name target $target soft $soft \
        range_target $range_target \
        cells $cells member_count [llength $cells] lut $lut ff $ff dsp $dsp \
        ramb36 $ramb36 ramb18 $ramb18 uram $uram capacity_ok $capacity_ok]
}

proc hap_fine19_collection_record {label cells} {
    set legal [hap_v5_fine19::pblockable $cells]
    return [dict create label $label cells $legal \
        member_count [llength $legal] \
        lut [hap_fine19_count_ref_pattern $legal LUT*] \
        ff [hap_fine19_count_ref_pattern $legal FD*] \
        dsp [hap_fine19_count_ref_pattern $legal DSP48E2] \
        ramb36 [hap_fine19_count_ref_pattern $legal RAMB36E2] \
        ramb18 [hap_fine19_count_ref_pattern $legal RAMB18E2] \
        uram [hap_fine19_count_ref_pattern $legal URAM288]]
}

proc hap_fine19_write_collection {fp record} {
    puts $fp "collection=[dict get $record label]"
    foreach key {member_count lut ff dsp ramb36 ramb18 uram} {
        puts $fp "${key}=[dict get $record $key]"
    }
    puts $fp ""
}

proc hap_fine19_add_record {left right} {
    set result [dict create]
    foreach key {lut ff dsp ramb36 ramb18 uram} {
        dict set result $key [expr {
            [dict get $left $key] + [dict get $right $key]}]
    }
    return $result
}

proc hap_fine19_capacity_fit {demand capacity} {
    set bram36_equiv [expr {[dict get $demand ramb36] +
        ([dict get $demand ramb18] + 1) / 2}]
    return [expr {[dict get $demand lut] <= [dict get $capacity lut] &&
        [dict get $demand ff] <= [dict get $capacity ff] &&
        [dict get $demand dsp] <= [dict get $capacity dsp] &&
        $bram36_equiv <= [dict get $capacity ramb36] &&
        [dict get $demand ramb18] <= [dict get $capacity ramb18] &&
        [dict get $demand uram] <= [dict get $capacity uram]}]
}

proc hap_fine19_write_candidate {fp name attention_target mlp_target
        slr_records slr_capacity attention_record mlp_record} {
    set candidate_records $slr_records
    lset candidate_records $attention_target [hap_fine19_add_record \
        [lindex $candidate_records $attention_target] $attention_record]
    lset candidate_records $mlp_target [hap_fine19_add_record \
        [lindex $candidate_records $mlp_target] $mlp_record]
    set all_fit 1
    puts $fp "candidate=$name"
    puts $fp "attention_target_slr=$attention_target"
    puts $fp "mlp_target_slr=$mlp_target"
    for {set index 0} {$index < 3} {incr index} {
        set demand [lindex $candidate_records $index]
        set capacity [lindex $slr_capacity $index]
        set fit [hap_fine19_capacity_fit $demand $capacity]
        if {!$fit} {set all_fit 0}
        foreach key {lut ff dsp ramb36 ramb18 uram} {
            puts $fp "slr${index}_${key}_demand=[dict get $demand $key]"
            puts $fp "slr${index}_${key}_capacity=[dict get $capacity $key]"
        }
        puts $fp "slr${index}_raw_capacity_ok=$fit"
    }
    puts $fp "candidate_raw_capacity_ok=$all_fit"
    puts $fp ""
    return $all_fit
}

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "V5 production qualification requires HAP_JOBS=32: $jobs"
}
if {[llength [get_designs -quiet]] != 0} {
    error "V5 fine19 probe requires a fresh Vivado process"
}
set_param general.maxThreads $jobs
set frozen [hap_fine19_verify_manifest $input_sha 8 $expected_manifest_sha]
foreach required [list $dcp $selector_lib $fine_lib $composite21_lib \
        $post_opt_audit_sha $p9_diag_output_sha $probe_script $launcher] {
    if {![dict exists $frozen $required]} {
        error "V5 fine19 required input is absent from manifest: $required"
    }
}
if {[hap_fine19_sha256 $dcp] ne $expected_dcp_sha} {
    error "V5 fine19 DCP identity mismatch"
}
set post_opt_audit_entries [hap_fine19_verify_manifest $post_opt_audit_sha -1 \
    $expected_post_opt_audit_sha]
set post_opt_audit_dir [file dirname $post_opt_audit_sha]
set post_opt_audit_report [file join $post_opt_audit_dir audit.txt]
set post_opt_audit_status [file join $post_opt_audit_dir launcher_status.txt]
foreach required [list $post_opt_audit_report $post_opt_audit_status] {
    if {![dict exists $post_opt_audit_entries $required]} {
        error "Required P7 post-opt audit evidence absent from manifest: $required"
    }
}
foreach literal [list evidence_class=V5_POST_OPT_READ_ONLY_REOPEN \
        "dcp=$dcp" "input_dcp_sha256=$expected_dcp_sha" \
        attention_query_store_instances=1 \
        attention_postprocess_store_instances=1 \
        attention_context_store_instances=1 \
        attention_query_store_ramb36e2=44 \
        attention_postprocess_store_lutram_primitives=0 \
        attention_context_store_ramb36e2=44 \
        attention_context_store_lutram_primitives=0 \
        dsp48e2=5453 uram288=752 ramb36e2=801 ramb18e2=22 \
        post_opt_data_bufg=0 attention_local_store_ok=1 \
        resource_ok=1 checkpoint_written=0 implementation_commands_run=0 \
        status=V5_POST_OPT_DCP_AUDIT_PASS] {
    hap_fine19_require_line $post_opt_audit_report $literal
}
foreach literal {status=PASS final_exit_code=0 vivado_exit_code=0
        input_sha_recheck_exit_code=0 input_manifest_sha_match=1
        upstream_lineage_sha_recheck_exit_code=0
        upstream_lineage_manifest_sha_match=1
        upstream_contract_recheck_exit_code=0 audit_gate_exit_code=0
        checkpoint_written=0 implementation_commands_run=0} {
    hap_fine19_require_line $post_opt_audit_status $literal
}

set p9_diag_entries [hap_fine19_verify_manifest $p9_diag_output_sha -1 \
    $expected_p9_diag_output_sha]
set p9_diag_dir [file dirname $p9_diag_output_sha]
set p9_diag_summary [file join $p9_diag_dir summary.txt]
set p9_diag_status [file join $p9_diag_dir launcher_status.txt]
set p9_diag_capacity [file join $p9_diag_dir candidate_capacity.txt]
foreach required [list $p9_diag_summary $p9_diag_status $p9_diag_capacity] {
    if {![dict exists $p9_diag_entries $required]} {
        error "Required P9 diagnostic evidence absent from output manifest: $required"
    }
}
foreach literal [list status=P9_CENTRAL_GEOMETRY_DIAGNOSIS_PASS \
        input_dcp=$dcp input_dcp_sha256=$expected_dcp_sha \
        proposed_pblock_count=21 proposed_member_overlap=0 \
        central_island_member_count=197091 central_island_dsp=80 \
        mlp_remaining_member_count=88785 center_dsp_remaining=5 \
        candidate_partition_ok=1 island_outside_source=0 \
        anchor_island_capacity_ok=1 anchor_envelope_capacity_ok=1 \
        dsp48e2=5453 uram288=752 resource_ok=1 \
        canonical_pblock_count_after=0 floorplan_mutated=0 \
        implementation_commands_run=0 checkpoint_written=0] {
    hap_fine19_require_line $p9_diag_summary $literal
}
foreach literal {status=PASS final_exit_code=0 vivado_exit_code=0
        input_sha_recheck_exit_code=0 p8_output_sha_recheck_exit_code=0
        diagnosis_gate_exit_code=0 floorplan_mutated=0
        implementation_commands_run=0 checkpoint_written=0} {
    hap_fine19_require_line $p9_diag_status $literal
}

set flow_start_ms [clock milliseconds]
source $selector_lib
source $fine_lib
source $composite21_lib
set phase_start_ms [clock milliseconds]
open_checkpoint $dcp
set open_checkpoint_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]
puts "HAP_FINE19_PHASE open_checkpoint elapsed_ms=$open_checkpoint_elapsed_ms"
if {[llength [get_pblocks -quiet]] != 0} {
    error "V5 fine19 probe input unexpectedly contains pblocks"
}
set phase_start_ms [clock milliseconds]
set base_plan [hap_v5_floorplan::discover P2_COHORT16_COL2_12_2]
set base_discovery_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]
puts "HAP_FINE19_PHASE base_discovery elapsed_ms=$base_discovery_elapsed_ms"
set phase_start_ms [clock milliseconds]
set fine_plan [hap_v5_fine19::discover $base_plan]
set fine_discovery_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]
puts "HAP_FINE19_PHASE fine_discovery elapsed_ms=$fine_discovery_elapsed_ms"
set specs [hap_v5_fine19::full_specs $base_plan $fine_plan]
if {[llength $specs] != 19} {
    error "V5 fine19 spec count mismatch: [llength $specs]"
}
set phase_start_ms [clock milliseconds]
set composite21_plan [hap_v5_composite21::discover $base_plan $fine_plan]
set composite21_discovery_elapsed_ms \
    [expr {[clock milliseconds] - $phase_start_ms}]
puts "HAP_FINE19_PHASE composite21_discovery elapsed_ms=$composite21_discovery_elapsed_ms"
set composite21_specs [hap_v5_composite21::full_specs \
    $base_plan $fine_plan $composite21_plan]
if {[llength $composite21_specs] != 21} {
    error "V5 composite21 spec count mismatch: [llength $composite21_specs]"
}

set phase_start_ms [clock milliseconds]
set records [dict create]
set fp [open [file join $out pblock_capacity.txt] w]
foreach spec $specs {
    set record [hap_fine19_write_spec $fp $spec]
    set name [dict get $record name]
    if {[dict exists $records $name]} {
        error "V5 fine19 duplicate pblock name: $name"
    }
    dict set records $name $record
}
close $fp

set all_members {}
set all_member_cells {}
set member_sum 0
set all_dsp {}
set all_uram {}
set slr_dsp {0 0 0}
set slr_uram {0 0 0}
set slr_records {}
for {set index 0} {$index < 3} {incr index} {
    lappend slr_records [dict create lut 0 ff 0 dsp 0 ramb36 0 ramb18 0 uram 0]
}
set capacity_ok 1
set range_target_ok 1
foreach name [dict keys $records] {
    set record [dict get $records $name]
    set target [dict get $record target]
    set cells [dict get $record cells]
    set all_member_cells [concat $all_member_cells $cells]
    set all_members [concat $all_members \
        [hap_v5_floorplan::object_names $cells]]
    incr member_sum [llength $cells]
    set cell_refs [get_property REF_NAME $cells]
    if {[llength $cell_refs] != [llength $cells]} {
        error "V5 fine19 probe bulk REF_NAME cardinality mismatch: $name"
    }
    foreach cell $cells ref_name $cell_refs {
        switch -- $ref_name {
            DSP48E2 {lappend all_dsp $cell}
            URAM288 {lappend all_uram $cell}
        }
    }
    lset slr_dsp $target [expr {[lindex $slr_dsp $target] + \
        [dict get $record dsp]}]
    lset slr_uram $target [expr {[lindex $slr_uram $target] + \
        [dict get $record uram]}]
    set target_record [lindex $slr_records $target]
    foreach key {lut ff dsp ramb36 ramb18 uram} {
        dict set target_record $key [expr {[dict get $target_record $key] +
            [dict get $record $key]}]
    }
    lset slr_records $target $target_record
    if {![dict get $record capacity_ok]} {set capacity_ok 0}
    if {[dict get $record range_target] != $target} {set range_target_ok 0}
}
set unique_members [lsort -dictionary -unique $all_members]
set member_overlap [expr {$member_sum - [llength $unique_members]}]
set covered_dsp [hap_v5_floorplan::object_names $all_dsp]
set covered_uram [hap_v5_floorplan::object_names $all_uram]
set design_dsp [hap_v5_floorplan::object_names [get_cells -quiet \
    -hierarchical -filter {REF_NAME == DSP48E2}]]
set design_uram [hap_v5_floorplan::object_names [get_cells -quiet \
    -hierarchical -filter {REF_NAME == URAM288}]]
set dsp_coverage_ok [expr {$covered_dsp eq $design_dsp &&
    [llength $covered_dsp] == 5453}]
set uram_coverage_ok [expr {$covered_uram eq $design_uram &&
    [llength $covered_uram] == 752}]
set resource_distribution_ok [expr {$slr_dsp eq {1862 1781 1810} &&
    $slr_uram eq {224 224 304}}]

# The 19 hard pblocks cover every DSP/URAM but intentionally do not cover all
# production logic. Quantify that composite pressure without mutating the
# checkpoint so the next floorplan factor is chosen from capacity evidence.
set all_member_cells [lsort -dictionary -unique $all_member_cells]
set all_design_primitives [hap_v5_fine19::pblockable \
    [get_cells -quiet -hierarchical -filter {IS_PRIMITIVE}]]
set uncovered_primitives [hap_v5_floorplan::list_subtract \
    $all_design_primitives $all_member_cells]

set mlp_roots [hap_v5_floorplan::module_cells hap_mlp_full_command16_s46]
set attention_compute_roots [hap_v5_floorplan::module_cells \
    hap_attention_compute_cohort16_top]
set attention_board_roots [hap_v5_floorplan::module_cells \
    hap_attention_board_cohort16_core]
hap_v5_fine19::require_count composite_mlp_roots $mlp_roots 1
hap_v5_fine19::require_count composite_attention_compute_roots \
    $attention_compute_roots 1
hap_v5_fine19::require_count composite_attention_board_roots \
    $attention_board_roots 1

set mlp_primitives [hap_v5_fine19::pblockable_descendants \
    [lindex $mlp_roots 0]]
set attention_compute_primitives [hap_v5_fine19::pblockable_descendants \
    [lindex $attention_compute_roots 0]]
set attention_board_primitives [hap_v5_fine19::pblockable_descendants \
    [lindex $attention_board_roots 0]]
set attention_shell_primitives [hap_v5_floorplan::list_subtract \
    $attention_board_primitives $attention_compute_primitives]

set mlp_uncovered [hap_v5_floorplan::list_intersection \
    $uncovered_primitives $mlp_primitives]
set attention_compute_uncovered [hap_v5_floorplan::list_intersection \
    $uncovered_primitives $attention_compute_primitives]
set attention_shell_uncovered [hap_v5_floorplan::list_intersection \
    $uncovered_primitives $attention_shell_primitives]
set attention_uncovered [hap_v5_floorplan::list_union \
    $attention_compute_uncovered $attention_shell_uncovered]
set classified_uncovered [hap_v5_floorplan::list_union \
    $mlp_uncovered $attention_uncovered]
set support_uncovered [hap_v5_floorplan::list_subtract \
    $uncovered_primitives $classified_uncovered]
set composite_partition [hap_v5_floorplan::list_union \
    $all_member_cells $mlp_uncovered $attention_compute_uncovered \
    $attention_shell_uncovered $support_uncovered]
set composite_partition_ok [expr {
    [hap_v5_floorplan::object_names $composite_partition] eq
        [hap_v5_floorplan::object_names $all_design_primitives]}]

set mlp_root [lindex $mlp_roots 0]
set mlp_input_root [hap_v5_fine19::child $mlp_root u_input_frontend \
    composite_mlp_input_root]
set mlp_serial_root [hap_v5_fine19::child $mlp_root u_serial_command \
    composite_mlp_serial_root]
set mlp_gate_root [hap_v5_fine19::child $mlp_serial_root u_gate_scheduler \
    composite_mlp_gate_root]
set mlp_down_root [hap_v5_fine19::child $mlp_serial_root u_down_scheduler \
    composite_mlp_down_root]
set mlp_w4_root [hap_v5_fine19::child $mlp_serial_root u_w4_frontend \
    composite_mlp_w4_root]
set mlp_down_cache_root [hap_v5_fine19::child $mlp_serial_root \
    u_down_activation_cache composite_mlp_down_cache_root]
set mlp_shared_root [hap_v5_fine19::child $mlp_serial_root u_shared_compute \
    composite_mlp_shared_root]

set attention_compute_root [lindex $attention_compute_roots 0]
set attention_board_root [lindex $attention_board_roots 0]
set attention_kv_quant_root [hap_v5_fine19::child $attention_compute_root \
    u_kv_quantizer4 composite_attention_kv_quant_root]
set attention_rope_root [hap_v5_fine19::child $attention_compute_root u_rope \
    composite_attention_rope_root]
set attention_input_root [hap_v5_fine19::child $attention_board_root \
    u_input_buffer composite_attention_input_root]
set attention_output_root [hap_v5_fine19::child $attention_board_root \
    u_output_buffer composite_attention_output_root]

foreach {label root} [list \
        mlp_input $mlp_input_root mlp_gate $mlp_gate_root \
        mlp_down $mlp_down_root mlp_w4 $mlp_w4_root \
        mlp_down_cache $mlp_down_cache_root mlp_shared $mlp_shared_root \
        attention_kv_quant $attention_kv_quant_root \
        attention_rope $attention_rope_root \
        attention_input $attention_input_root \
        attention_output $attention_output_root] {
    set ${label}_uncovered [hap_v5_floorplan::list_intersection \
        $uncovered_primitives [hap_v5_fine19::pblockable_descendants $root]]
}
set attention_direct_uncovered [hap_v5_floorplan::list_subtract \
    $attention_compute_uncovered [hap_v5_floorplan::list_union \
        $attention_kv_quant_uncovered $attention_rope_uncovered]]
set attention_shell_other_uncovered [hap_v5_floorplan::list_subtract \
    $attention_shell_uncovered [hap_v5_floorplan::list_union \
        $attention_input_uncovered $attention_output_uncovered]]
set mlp_named_uncovered [hap_v5_floorplan::list_union \
    $mlp_input_uncovered $mlp_gate_uncovered $mlp_down_uncovered \
    $mlp_w4_uncovered $mlp_down_cache_uncovered $mlp_shared_uncovered]
set mlp_other_uncovered [hap_v5_floorplan::list_subtract \
    $mlp_uncovered $mlp_named_uncovered]
set subgroup_partition [hap_v5_floorplan::list_union \
    $attention_direct_uncovered $attention_kv_quant_uncovered \
    $attention_rope_uncovered $attention_input_uncovered \
    $attention_output_uncovered $attention_shell_other_uncovered \
    $mlp_input_uncovered $mlp_gate_uncovered $mlp_down_uncovered \
    $mlp_w4_uncovered $mlp_down_cache_uncovered $mlp_shared_uncovered \
    $mlp_other_uncovered $support_uncovered]
set subgroup_partition_ok [expr {
    [hap_v5_floorplan::object_names $subgroup_partition] eq
        [hap_v5_floorplan::object_names $uncovered_primitives]}]

set collection_records [dict create]
foreach {label cells} [list \
        uncovered_all $uncovered_primitives \
        mlp_uncovered $mlp_uncovered \
        attention_compute_uncovered $attention_compute_uncovered \
        attention_shell_uncovered $attention_shell_uncovered \
        support_uncovered $support_uncovered] {
    dict set collection_records $label \
        [hap_fine19_collection_record $label $cells]
}
set subgroup_records [dict create]
foreach {label cells} [list \
        attention_direct $attention_direct_uncovered \
        attention_kv_quant $attention_kv_quant_uncovered \
        attention_rope $attention_rope_uncovered \
        attention_input $attention_input_uncovered \
        attention_output $attention_output_uncovered \
        attention_shell_other $attention_shell_other_uncovered \
        mlp_input $mlp_input_uncovered mlp_gate $mlp_gate_uncovered \
        mlp_down $mlp_down_uncovered mlp_w4 $mlp_w4_uncovered \
        mlp_down_cache $mlp_down_cache_uncovered \
        mlp_shared $mlp_shared_uncovered \
        mlp_other $mlp_other_uncovered support $support_uncovered] {
    dict set subgroup_records $label \
        [hap_fine19_collection_record $label $cells]
}
set uncovered_record [dict get $collection_records uncovered_all]
set uncovered_hard_resources_zero [expr {
    [dict get $uncovered_record dsp] == 0 &&
    [dict get $uncovered_record uram] == 0}]

set slr_capacity {}
for {set index 0} {$index < 3} {incr index} {
    lappend slr_capacity [hap_fine19_site_capacity \
        [hap_fine19_regions_for_range SLR${index}]]
}

# Qualify the selected P9 factor as an exact, disjoint 21-hard-pblock extension
# of Fine19. Attention-direct remains part of the flexible residual. This is a
# read-only selector/capacity audit: no pblock object is created in the opened
# checkpoint.
set composite21_records [dict create]
set composite21_fp [open [file join $out composite21_pblock_capacity.txt] w]
foreach spec $composite21_specs {
    set record [hap_fine19_write_spec $composite21_fp $spec]
    set name [dict get $record name]
    if {[dict exists $composite21_records $name]} {
        error "V5 composite21 duplicate pblock name: $name"
    }
    dict set composite21_records $name $record
}
set composite21_member_names {}
set composite21_member_cells {}
set composite21_member_sum 0
set composite21_dsp {}
set composite21_uram {}
set composite21_slr_dsp {0 0 0}
set composite21_slr_uram {0 0 0}
set composite21_slr_records {}
set composite21_hard_slr_records {}
for {set index 0} {$index < 3} {incr index} {
    lappend composite21_slr_records \
        [dict create lut 0 ff 0 dsp 0 ramb36 0 ramb18 0 uram 0]
    lappend composite21_hard_slr_records \
        [dict create lut 0 ff 0 dsp 0 ramb36 0 ramb18 0 uram 0]
}
set composite21_soft_pblock_count 0
set composite21_individual_capacity_ok 1
set composite21_range_target_ok 1
foreach name [dict keys $composite21_records] {
    set record [dict get $composite21_records $name]
    set target [dict get $record target]
    set cells [dict get $record cells]
    set soft [dict get $record soft]
    if {$soft} {incr composite21_soft_pblock_count}
    set names [hap_v5_floorplan::object_names $cells]
    set composite21_member_cells [concat $composite21_member_cells $cells]
    set composite21_member_names [concat $composite21_member_names $names]
    incr composite21_member_sum [llength $names]
    set refs [get_property REF_NAME $cells]
    if {[llength $refs] != [llength $cells]} {
        error "V5 composite21 bulk REF_NAME cardinality mismatch: $name"
    }
    foreach cell $cells ref_name $refs {
        switch -- $ref_name {
            DSP48E2 {lappend composite21_dsp $cell}
            URAM288 {lappend composite21_uram $cell}
        }
    }
    lset composite21_slr_dsp $target [expr {
        [lindex $composite21_slr_dsp $target] + [dict get $record dsp]}]
    lset composite21_slr_uram $target [expr {
        [lindex $composite21_slr_uram $target] + [dict get $record uram]}]
    set target_record [lindex $composite21_slr_records $target]
    foreach key {lut ff dsp ramb36 ramb18 uram} {
        dict set target_record $key [expr {[dict get $target_record $key] +
            [dict get $record $key]}]
    }
    lset composite21_slr_records $target $target_record
    if {!$soft} {
        set hard_target_record [lindex $composite21_hard_slr_records $target]
        foreach key {lut ff dsp ramb36 ramb18 uram} {
            dict set hard_target_record $key [expr {
                [dict get $hard_target_record $key] + [dict get $record $key]}]
        }
        lset composite21_hard_slr_records $target $hard_target_record
    }
    if {![dict get $record capacity_ok]} {
        set composite21_individual_capacity_ok 0
    }
    if {[dict get $record range_target] != $target} {
        set composite21_range_target_ok 0
    }
}
set composite21_unique_member_names \
    [lsort -dictionary -unique $composite21_member_names]
set composite21_member_overlap [expr {$composite21_member_sum -
    [llength $composite21_unique_member_names]}]
set composite21_covered_dsp \
    [hap_v5_floorplan::object_names $composite21_dsp]
set composite21_covered_uram \
    [hap_v5_floorplan::object_names $composite21_uram]
set composite21_dsp_coverage_ok [expr {
    $composite21_covered_dsp eq $design_dsp &&
    [llength $composite21_covered_dsp] == 5453}]
set composite21_uram_coverage_ok [expr {
    $composite21_covered_uram eq $design_uram &&
    [llength $composite21_covered_uram] == 752}]
set composite21_resource_distribution_ok [expr {
    $composite21_slr_dsp eq {1862 1781 1810} &&
    $composite21_slr_uram eq {224 224 304}}]
set composite21_member_cells [lsort -dictionary -unique \
    $composite21_member_cells]
set composite21_residual_primitives [hap_v5_floorplan::list_subtract \
    $all_design_primitives $composite21_member_cells]
set composite21_residual_record [hap_fine19_collection_record \
    residual_after_composite21 $composite21_residual_primitives]
set composite21_flexible_record $composite21_residual_record
set composite21_hard_capacity_ok 1
set composite21_outer_90pct_lut_headroom 0
for {set index 0} {$index < 3} {incr index} {
    set hard_demand [lindex $composite21_hard_slr_records $index]
    set capacity [lindex $slr_capacity $index]
    if {![hap_fine19_capacity_fit $hard_demand $capacity]} {
        set composite21_hard_capacity_ok 0
    }
    if {$index != 1} {
        incr composite21_outer_90pct_lut_headroom [expr {
            int([dict get $capacity lut] * 0.90) -
            [dict get $hard_demand lut]}]
    }
}
set composite21_flexible_outer_90pct_fit [expr {
    $composite21_outer_90pct_lut_headroom >=
        [dict get $composite21_flexible_record lut]}]
set composite21_aggregate_capacity_ok 1
for {set index 0} {$index < 3} {incr index} {
    set demand [lindex $composite21_slr_records $index]
    set capacity [lindex $slr_capacity $index]
    set fit [hap_fine19_capacity_fit $demand $capacity]
    if {!$fit} {set composite21_aggregate_capacity_ok 0}
    puts $composite21_fp "aggregate_slr=$index"
    foreach key {lut ff dsp ramb36 ramb18 uram} {
        puts $composite21_fp "${key}_demand=[dict get $demand $key]"
        puts $composite21_fp "${key}_capacity=[dict get $capacity $key]"
    }
    puts $composite21_fp "raw_capacity_ok=$fit"
    puts $composite21_fp ""
}
close $composite21_fp

set composite_fp [open [file join $out composite_capacity.txt] w]
foreach label {uncovered_all mlp_uncovered attention_compute_uncovered
        attention_shell_uncovered support_uncovered} {
    hap_fine19_write_collection $composite_fp \
        [dict get $collection_records $label]
}
for {set index 0} {$index < 3} {incr index} {
    puts $composite_fp "slr=$index"
    foreach key {lut ff dsp ramb36 ramb18 uram} {
        puts $composite_fp "pblocked_${key}_demand=[dict get \
            [lindex $slr_records $index] $key]"
        puts $composite_fp "${key}_capacity=[dict get \
            [lindex $slr_capacity $index] $key]"
    }
    puts $composite_fp ""
}
set attention_record [hap_fine19_add_record \
    [dict get $collection_records attention_compute_uncovered] \
    [dict get $collection_records attention_shell_uncovered]]
set mlp_record [dict get $collection_records mlp_uncovered]
set attention0_mlp2_capacity_ok [hap_fine19_write_candidate $composite_fp \
    attention0_mlp2 0 2 $slr_records $slr_capacity \
    $attention_record $mlp_record]
set attention2_mlp0_capacity_ok [hap_fine19_write_candidate $composite_fp \
    attention2_mlp0 2 0 $slr_records $slr_capacity \
    $attention_record $mlp_record]
close $composite_fp

set subgroup_fp [open [file join $out composite_subgroups.txt] w]
foreach label {attention_direct attention_kv_quant attention_rope
        attention_input attention_output attention_shell_other mlp_input
        mlp_gate mlp_down mlp_w4 mlp_down_cache mlp_shared mlp_other support} {
    hap_fine19_write_collection $subgroup_fp [dict get $subgroup_records $label]
}
close $subgroup_fp

set pblock_count_after [llength [get_pblocks -quiet]]
set capacity_audit_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]
set total_elapsed_ms [expr {[clock milliseconds] - $flow_start_ms}]
puts "HAP_FINE19_PHASE capacity_audit elapsed_ms=$capacity_audit_elapsed_ms"
puts "HAP_FINE19_PHASE total elapsed_ms=$total_elapsed_ms"
set status [expr {$member_overlap == 0 && $capacity_ok && $range_target_ok &&
    $dsp_coverage_ok && $uram_coverage_ok && $resource_distribution_ok &&
    $composite_partition_ok && $subgroup_partition_ok &&
    $uncovered_hard_resources_zero &&
    [dict get $composite21_plan exact_partition] &&
    [dict get $composite21_plan central_partition_ok] == 1 &&
    [dict get $composite21_plan owner_overlap] == 0 &&
    [dict get $composite21_plan hard_resource_intrusion] == 0 &&
    [dict get $composite21_plan attention_direct_constrained] == 0 &&
    $composite21_member_overlap == 0 &&
    $composite21_soft_pblock_count == 0 &&
    $composite21_individual_capacity_ok &&
    $composite21_aggregate_capacity_ok &&
    $composite21_hard_capacity_ok &&
    $composite21_flexible_outer_90pct_fit &&
    $composite21_range_target_ok && $composite21_dsp_coverage_ok &&
    $composite21_uram_coverage_ok &&
    $composite21_resource_distribution_ok &&
    $pblock_count_after == 0 ? "PASS" : "FAIL"}]

set summary [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] \
        part [get_property PART [current_design]] \
        top [get_property TOP [current_design]] \
        stage V5_PRODUCTION_FINE19_FLOORPLAN_PROBE \
        evidence_class READ_ONLY_POST_OPT_SELECTOR_CAPACITY \
        contract_variant [dict get $fine_plan contract_variant] jobs $jobs \
        input_dcp $dcp input_dcp_sha256 $expected_dcp_sha \
        input_manifest_sha256 $expected_manifest_sha \
        input_manifest_entries [dict size $frozen] provenance_verified 1 \
        post_opt_audit_manifest $post_opt_audit_sha \
        post_opt_audit_manifest_sha256 $expected_post_opt_audit_sha \
        post_opt_audit_entries [dict size $post_opt_audit_entries] \
        post_opt_audit_verified 1 \
        p9_diag_manifest $p9_diag_output_sha \
        p9_diag_manifest_sha256 $expected_p9_diag_output_sha \
        p9_diag_entries [dict size $p9_diag_entries] p9_diag_verified 1 \
        open_checkpoint_elapsed_ms $open_checkpoint_elapsed_ms \
        base_discovery_elapsed_ms $base_discovery_elapsed_ms \
        fine_discovery_elapsed_ms $fine_discovery_elapsed_ms \
        composite21_discovery_elapsed_ms \
            $composite21_discovery_elapsed_ms \
        capacity_audit_elapsed_ms $capacity_audit_elapsed_ms \
        total_elapsed_ms $total_elapsed_ms \
        pblock_spec_count [llength $specs] member_count $member_sum \
        unique_member_count [llength $unique_members] member_overlap $member_overlap \
        projection_primitives \
            [llength [dict get $fine_plan projection_primitives]] \
        projection_dsp48e2 \
            [hap_v5_floorplan::count_ref \
                [dict get $fine_plan projection_primitives] DSP48E2] \
        projection_pblockable_primitives \
            [llength [hap_v5_fine19::pblockable \
                [dict get $fine_plan projection_primitives]]] \
        frontend_primitives \
            [llength [dict get $fine_plan frontend_primitives]] \
        frontend_dsp48e2 \
            [hap_v5_floorplan::count_ref \
                [dict get $fine_plan frontend_primitives] DSP48E2] \
        left_primitives [llength [dict get $fine_plan left_primitives]] \
        center_primitives [llength [dict get $fine_plan center_primitives]] \
        right_primitives [llength [dict get $fine_plan right_primitives]] \
        center_region0_dsp48e2 \
            [hap_v5_floorplan::count_ref \
                [dict get $fine_plan center_region0_primitives] DSP48E2] \
        center_region1_dsp48e2 \
            [hap_v5_floorplan::count_ref \
                [dict get $fine_plan center_region1_primitives] DSP48E2] \
        center_region2_dsp48e2 \
            [hap_v5_floorplan::count_ref \
                [dict get $fine_plan center_region2_primitives] DSP48E2] \
        center_region3_dsp48e2 \
            [hap_v5_floorplan::count_ref \
                [dict get $fine_plan center_region3_primitives] DSP48E2] \
        center_region1_logic_primitives \
            [llength [dict get $fine_plan \
                center_region1_logic_residual_primitives]] \
        center_region1_logic_dsp48e2 \
            [hap_v5_floorplan::count_ref [dict get $fine_plan \
                center_region1_logic_residual_primitives] DSP48E2] \
        center_region1_logic_pblockable_primitives \
            [llength [hap_v5_fine19::pblockable [dict get $fine_plan \
                center_region1_logic_residual_primitives]]] \
        center_region1_cols4_5_dsp48e2 \
            [llength [dict get $fine_plan \
                center_region1_cols4_5_dsp_primitives]] \
        center_region1_cols6_7_dsp48e2 \
            [llength [dict get $fine_plan \
                center_region1_cols6_7_dsp_primitives]] \
        region3_input_primitives \
            [llength [dict get $fine_plan region3_input_primitives]] \
        owner_region2_weight_primitives \
            [llength [dict get $fine_plan owner_region2_weight_primitives]] \
        owner_residual_primitives \
            [llength [dict get $fine_plan owner_residual_primitives]] \
        nonprojection_center_dsp48e2 \
            [llength [dict get $fine_plan nonprojection_center_dsp]] \
        projection_exact_cover \
            [dict get $fine_plan projection_exact_cover] \
        region1_exact_cover [dict get $fine_plan region1_exact_cover] \
        owner_exact_cover [dict get $fine_plan owner_exact_cover] \
        weight_owner_residency_ok \
            [dict get $fine_plan weight_owner_residency_ok] \
        pblock_member_overlap $member_overlap \
        pblock_dsp_coverage [llength $covered_dsp] \
        pblock_uram_coverage [llength $covered_uram] \
        dsp_coverage_ok $dsp_coverage_ok uram_coverage_ok $uram_coverage_ok \
        slr0_dsp48e2 [lindex $slr_dsp 0] \
        slr1_dsp48e2 [lindex $slr_dsp 1] \
        slr2_dsp48e2 [lindex $slr_dsp 2] \
        slr0_uram288 [lindex $slr_uram 0] \
        slr1_uram288 [lindex $slr_uram 1] \
        slr2_uram288 [lindex $slr_uram 2] \
        resource_distribution_ok $resource_distribution_ok \
        design_pblockable_primitives [llength $all_design_primitives] \
        uncovered_pblockable_primitives [llength $uncovered_primitives] \
        uncovered_lut [dict get $uncovered_record lut] \
        uncovered_ff [dict get $uncovered_record ff] \
        uncovered_dsp48e2 [dict get $uncovered_record dsp] \
        uncovered_ramb36e2 [dict get $uncovered_record ramb36] \
        uncovered_ramb18e2 [dict get $uncovered_record ramb18] \
        uncovered_uram288 [dict get $uncovered_record uram] \
        mlp_uncovered_primitives [llength $mlp_uncovered] \
        attention_compute_uncovered_primitives \
            [llength $attention_compute_uncovered] \
        attention_shell_uncovered_primitives \
            [llength $attention_shell_uncovered] \
        support_uncovered_primitives [llength $support_uncovered] \
        composite_partition_ok $composite_partition_ok \
        subgroup_partition_ok $subgroup_partition_ok \
        uncovered_hard_resources_zero $uncovered_hard_resources_zero \
        attention0_mlp2_raw_capacity_ok $attention0_mlp2_capacity_ok \
        attention2_mlp0_raw_capacity_ok $attention2_mlp0_capacity_ok \
        composite21_contract_variant \
            [dict get $composite21_plan contract_variant] \
        composite21_pblock_spec_count [llength $composite21_specs] \
        composite21_member_count $composite21_member_sum \
        composite21_unique_member_count \
            [llength $composite21_unique_member_names] \
        composite21_member_overlap $composite21_member_overlap \
        composite21_fine_member_count \
            [dict get $composite21_plan fine_member_count] \
        composite21_mlp_residual_count \
            [dict get $composite21_plan mlp_residual_count] \
        composite21_central_anchor_range \
            [dict get $composite21_plan central_anchor_range] \
        composite21_central_island_count \
            [dict get $composite21_plan central_island_count] \
        composite21_central_island_dsp \
            [dict get $composite21_plan central_island_dsp] \
        composite21_mlp_remaining_count \
            [dict get $composite21_plan mlp_remaining_count] \
        composite21_center_dsp_remaining \
            [dict get $composite21_plan center_dsp_remaining_dsp] \
        composite21_central_partition_ok \
            [dict get $composite21_plan central_partition_ok] \
        composite21_attention_direct_count \
            [dict get $composite21_plan attention_direct_count] \
        composite21_owner_overlap \
            [dict get $composite21_plan owner_overlap] \
        composite21_hard_resource_intrusion \
            [dict get $composite21_plan hard_resource_intrusion] \
        composite21_exact_partition \
            [dict get $composite21_plan exact_partition] \
        composite21_attention_direct_constrained \
            [dict get $composite21_plan attention_direct_constrained] \
        composite21_soft_pblock_count $composite21_soft_pblock_count \
        composite21_residual_member_count \
            [dict get $composite21_residual_record member_count] \
        composite21_residual_lut [dict get $composite21_residual_record lut] \
        composite21_flexible_lut [dict get $composite21_flexible_record lut] \
        composite21_hard_slr0_lut \
            [dict get [lindex $composite21_hard_slr_records 0] lut] \
        composite21_hard_slr1_lut \
            [dict get [lindex $composite21_hard_slr_records 1] lut] \
        composite21_hard_slr2_lut \
            [dict get [lindex $composite21_hard_slr_records 2] lut] \
        composite21_hard_capacity_ok $composite21_hard_capacity_ok \
        composite21_outer_90pct_lut_headroom \
            $composite21_outer_90pct_lut_headroom \
        composite21_flexible_outer_90pct_fit \
            $composite21_flexible_outer_90pct_fit \
        composite21_individual_capacity_ok \
            $composite21_individual_capacity_ok \
        composite21_aggregate_capacity_ok \
            $composite21_aggregate_capacity_ok \
        composite21_all_ranges_single_slr $composite21_range_target_ok \
        composite21_dsp_coverage [llength $composite21_covered_dsp] \
        composite21_uram_coverage [llength $composite21_covered_uram] \
        composite21_dsp_coverage_ok $composite21_dsp_coverage_ok \
        composite21_uram_coverage_ok $composite21_uram_coverage_ok \
        composite21_slr0_dsp48e2 [lindex $composite21_slr_dsp 0] \
        composite21_slr1_dsp48e2 [lindex $composite21_slr_dsp 1] \
        composite21_slr2_dsp48e2 [lindex $composite21_slr_dsp 2] \
        composite21_slr0_uram288 [lindex $composite21_slr_uram 0] \
        composite21_slr1_uram288 [lindex $composite21_slr_uram 1] \
        composite21_slr2_uram288 [lindex $composite21_slr_uram 2] \
        composite21_resource_distribution_ok \
            $composite21_resource_distribution_ok \
        all_ranges_single_slr $range_target_ok raw_capacity_ok $capacity_ok \
        canonical_pblock_count_before 0 canonical_pblock_count_after \
            $pblock_count_after floorplan_mutated 0 \
        implementation_commands_run 0 checkpoint_written 0 status $status] {
    puts $summary "$key=$value"
}
close $summary
puts "V5_PRODUCTION_FINE19_FLOORPLAN_PROBE_COMPLETE STATUS=$status"
if {$status ne "PASS"} {
    error "V5 production fine19 floorplan probe failed"
}
