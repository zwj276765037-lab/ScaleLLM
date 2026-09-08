# Read-only hierarchy diagnosis for the failed P4 Composite21 SLR partition.
# It classifies Attention-direct primitives by natural hierarchy boundaries and
# records resources plus module-interface width. It creates no pblocks and runs
# no implementation command.

set dcp [file normalize $::env(HAP_DCP)]
set out [file normalize $::env(HAP_COMPOSITE21_DIAG_DIR)]
set input_sha [file normalize $::env(HAP_COMPOSITE21_DIAG_INPUT_SHA)]
set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)
set expected_input_sha $::env(HAP_COMPOSITE21_DIAG_INPUT_MANIFEST_SHA256)
set selector_lib [file normalize $::env(HAP_COMPOSITE21_DIAG_SELECTOR_LIB)]
set fine_lib [file normalize $::env(HAP_COMPOSITE21_DIAG_FINE_LIB)]
set composite_lib [file normalize $::env(HAP_COMPOSITE21_DIAG_COMPOSITE_LIB)]
set failed_place_sha [file normalize $::env(HAP_COMPOSITE21_FAILED_PLACE_SHA)]
set expected_failed_place_sha $::env(HAP_COMPOSITE21_FAILED_PLACE_SHA256)
set expected_launcher [file normalize $::env(HAP_COMPOSITE21_DIAG_LAUNCHER)]
set diag_script [file normalize [info script]]
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]

proc hap_partition_require_file {path label} {
    if {![file exists $path] || ![file isfile $path] || [file size $path] == 0} {
        error "Missing or empty $label: $path"
    }
}

proc hap_partition_read {path label} {
    hap_partition_require_file $path $label
    set fp [open $path r]
    set text [read $fp]
    close $fp
    return $text
}

proc hap_partition_sha256 {path} {
    set digest [lindex [exec sha256sum -- $path] 0]
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "Malformed SHA256 for $path: $digest"
    }
    return $digest
}

proc hap_partition_verify_manifest {path expected_count expected_sha label} {
    if {[hap_partition_sha256 $path] ne $expected_sha} {
        error "$label manifest identity mismatch"
    }
    set entries [dict create]
    foreach raw [split [hap_partition_read $path $label] "\n"] {
        set line [string trim $raw]
        if {$line eq ""} {continue}
        if {![regexp {^([0-9a-f]{64})[[:space:]]+\*?(.+)$} \
                $line -> expected file_name]} {
            error "Malformed $label row: $line"
        }
        set normalized [file normalize [string trim $file_name]]
        if {[dict exists $entries $normalized]} {
            error "Duplicate $label path: $normalized"
        }
        hap_partition_require_file $normalized "$label input"
        if {[hap_partition_sha256 $normalized] ne $expected} {
            error "$label SHA mismatch: $normalized"
        }
        dict set entries $normalized $expected
    }
    if {$expected_count >= 0 && [dict size $entries] != $expected_count} {
        error "$label cardinality mismatch: [dict size $entries]"
    }
    return $entries
}

proc hap_partition_require_line {path literal} {
    set count 0
    foreach line [split [hap_partition_read $path evidence] "\n"] {
        if {$line eq $literal} {incr count}
    }
    if {$count != 1} {
        error "Evidence line mismatch: $path literal=$literal count=$count"
    }
}

proc hap_partition_resource_record {cells} {
    set legal [hap_v5_fine19::pblockable $cells]
    set refs [get_property REF_NAME $legal]
    if {[llength $refs] != [llength $legal]} {
        error "Partition diagnostic REF_NAME cardinality mismatch"
    }
    set lut 0
    set ff 0
    set dsp 0
    set ramb36 0
    set ramb18 0
    set uram 0
    foreach ref_name $refs {
        if {[string match LUT* $ref_name]} {incr lut}
        if {[string match FD* $ref_name]} {incr ff}
        switch -- $ref_name {
            DSP48E2 {incr dsp}
            RAMB36E2 {incr ramb36}
            RAMB18E2 {incr ramb18}
            URAM288 {incr uram}
        }
    }
    return [dict create cells $legal member_count [llength $legal] \
        lut $lut ff $ff dsp $dsp ramb36 $ramb36 ramb18 $ramb18 uram $uram]
}

proc hap_partition_interface_record {path} {
    set cells [get_cells -quiet $path]
    if {[llength $cells] != 1 || [get_property IS_PRIMITIVE $cells]} {
        return [dict create ref direct pins 0 input_pins 0 output_pins 0 \
            inout_pins 0 nets 0]
    }
    set ref_name [get_property ORIG_REF_NAME $cells]
    if {$ref_name eq ""} {set ref_name [get_property REF_NAME $cells]}
    set pins [get_pins -quiet -of_objects $cells]
    set directions [get_property DIRECTION $pins]
    set input_pins 0
    set output_pins 0
    set inout_pins 0
    foreach direction $directions {
        switch -- $direction {
            IN {incr input_pins}
            OUT {incr output_pins}
            default {incr inout_pins}
        }
    }
    set nets [hap_v5_floorplan::object_names \
        [get_nets -quiet -of_objects $pins]]
    return [dict create ref $ref_name pins [llength $pins] \
        input_pins $input_pins output_pins $output_pins \
        inout_pins $inout_pins nets [llength $nets]]
}

proc hap_partition_write_groups {path root_name groups} {
    set fp [open $path w]
    foreach key [lsort -dictionary [dict keys $groups]] {
        set resources [hap_partition_resource_record [dict get $groups $key]]
        set hierarchy_path [expr {$key eq "__direct__" ? $root_name :
            "$root_name/$key"}]
        if {[string match "*/__direct__" $key]} {
            set hierarchy_path "$root_name/[string range $key 0 end-11]"
        }
        if {$key eq "__direct__"} {
            set interface [dict create ref direct pins 0 input_pins 0 \
                output_pins 0 inout_pins 0 nets 0]
        } else {
            set interface [hap_partition_interface_record $hierarchy_path]
        }
        puts $fp "group=$key"
        puts $fp "hierarchy_path=$hierarchy_path"
        foreach field {ref pins input_pins output_pins inout_pins nets} {
            puts $fp "interface_${field}=[dict get $interface $field]"
        }
        foreach field {member_count lut ff dsp ramb36 ramb18 uram} {
            puts $fp "$field=[dict get $resources $field]"
        }
        puts $fp ""
    }
    close $fp
}

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "Composite21 partition diagnosis requires HAP_JOBS=32: $jobs"
}
if {[llength [get_designs -quiet]] != 0} {
    error "Composite21 partition diagnosis requires a fresh Vivado process"
}
set_param general.maxThreads $jobs
set frozen [hap_partition_verify_manifest $input_sha 7 $expected_input_sha \
    composite21_partition_input]
foreach path [list $dcp $selector_lib $fine_lib $composite_lib \
        $failed_place_sha $diag_script $expected_launcher] {
    if {![dict exists $frozen $path]} {
        error "Required partition input absent from manifest: $path"
    }
}
if {[hap_partition_sha256 $dcp] ne $expected_dcp_sha} {
    error "Composite21 partition DCP identity mismatch"
}
set failed_entries [hap_partition_verify_manifest $failed_place_sha -1 \
    $expected_failed_place_sha composite21_failed_place_output]
set failed_dir [file dirname $failed_place_sha]
set failed_status [file join $failed_dir launcher_status.txt]
set failed_log [file join $failed_dir vivado.log]
foreach path [list $failed_status $failed_log] {
    if {![dict exists $failed_entries $path]} {
        error "Required failed-placement evidence absent from manifest: $path"
    }
}
foreach literal {status=FAIL acceptance_evidence=0 route_eligible=0
        final_exit_code=1 vivado_exit_code=1 checkpoint_written=0
        bitstream_generated=0} {
    hap_partition_require_line $failed_status $literal
}
set failed_log_text [hap_partition_read $failed_log failed_place_log]
foreach literal {107.2% {27211 SLLs required between SLR1 and SLR2 of 17280 SLLs available}} {
    if {[string first $literal $failed_log_text] < 0} {
        error "Failed-placement partition signature is missing: $literal"
    }
}

source $selector_lib
source $fine_lib
source $composite_lib
set flow_start_ms [clock milliseconds]
set phase_start_ms [clock milliseconds]
open_checkpoint $dcp
set open_checkpoint_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]
if {[llength [get_pblocks -quiet]] != 0} {
    error "Partition diagnosis input unexpectedly contains pblocks"
}
set phase_start_ms [clock milliseconds]
set base_plan [hap_v5_floorplan::discover P2_COHORT16_COL2_12_2]
set fine_plan [hap_v5_fine19::discover $base_plan]
set composite_plan [hap_v5_composite21::discover $base_plan $fine_plan]
set discovery_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]
set attention_direct [dict get $composite_plan attention_direct_primitives]
set attention_roots [hap_v5_floorplan::module_cells \
    hap_attention_compute_cohort16_top]
hap_v5_fine19::require_count partition_attention_roots $attention_roots 1
set attention_root [lindex $attention_roots 0]
set root_name [get_property NAME $attention_root]
set prefix "$root_name/"
set direct_names [get_property NAME $attention_direct]
if {[llength $direct_names] != [llength $attention_direct]} {
    error "Partition diagnostic NAME cardinality mismatch"
}
set top_groups [dict create]
set level2_groups [dict create]
foreach cell $attention_direct name $direct_names {
    if {![string match "${prefix}*" $name]} {
        error "Attention-direct primitive is outside compute root: $name"
    }
    set relative [string range $name [string length $prefix] end]
    set parts [split $relative /]
    if {[llength $parts] >= 2} {
        set top_key [lindex $parts 0]
    } else {
        set top_key __direct__
    }
    if {[llength $parts] >= 3} {
        set level2_key "[lindex $parts 0]/[lindex $parts 1]"
    } elseif {[llength $parts] >= 2} {
        set level2_key "[lindex $parts 0]/__direct__"
    } else {
        set level2_key __direct__
    }
    dict lappend top_groups $top_key $cell
    dict lappend level2_groups $level2_key $cell
}
hap_partition_write_groups [file join $out attention_direct_top_groups.txt] \
    $root_name $top_groups
hap_partition_write_groups [file join $out attention_direct_level2_groups.txt] \
    $root_name $level2_groups

set fine_specs [hap_v5_fine19::full_specs $base_plan $fine_plan]
set fixed_lut {0 0 0}
foreach spec $fine_specs {
    set target [dict get $spec target]
    set record [hap_partition_resource_record [dict get $spec cells]]
    lset fixed_lut $target [expr {[lindex $fixed_lut $target] +
        [dict get $record lut]}]
}
set mlp_record [hap_partition_resource_record \
    [dict get $composite_plan mlp_residual_primitives]]
lset fixed_lut 1 [expr {[lindex $fixed_lut 1] + [dict get $mlp_record lut]}]
set direct_record [hap_partition_resource_record $attention_direct]
set pblock_count_after [llength [get_pblocks -quiet]]
set total_elapsed_ms [expr {[clock milliseconds] - $flow_start_ms}]
set status [expr {[dict size $top_groups] > 1 &&
    [dict size $level2_groups] >= [dict size $top_groups] &&
    [dict get $direct_record member_count] == 134527 &&
    [dict get $direct_record lut] == 87667 &&
    [dict get $direct_record dsp] == 0 && [dict get $direct_record uram] == 0 &&
    $fixed_lut eq {273235 312344 263388} && $pblock_count_after == 0 ?
    "PASS" : "FAIL"}]
set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] \
        stage V5_COMPOSITE21_PARTITION_DIAGNOSIS \
        evidence_class READ_ONLY_POST_OPT_HIERARCHY_CONNECTIVITY \
        jobs $jobs input_dcp $dcp input_dcp_sha256 $expected_dcp_sha \
        input_manifest_sha256 $expected_input_sha input_manifest_entries 7 \
        failed_place_manifest $failed_place_sha \
        failed_place_manifest_sha256 $expected_failed_place_sha \
        failed_place_entries [dict size $failed_entries] failed_place_verified 1 \
        contract_variant [dict get $composite_plan contract_variant] \
        attention_root $root_name \
        attention_direct_members [dict get $direct_record member_count] \
        attention_direct_lut [dict get $direct_record lut] \
        attention_direct_ff [dict get $direct_record ff] \
        attention_direct_ramb36 [dict get $direct_record ramb36] \
        top_group_count [dict size $top_groups] \
        level2_group_count [dict size $level2_groups] \
        fixed_slr0_lut [lindex $fixed_lut 0] \
        fixed_slr1_lut [lindex $fixed_lut 1] \
        fixed_slr2_lut [lindex $fixed_lut 2] \
        physical_slr_lut_capacity 394080 failed_slr2_lut_percent 107.2 \
        failed_slr12_sll_required 27211 failed_slr12_sll_available 17280 \
        open_checkpoint_elapsed_ms $open_checkpoint_elapsed_ms \
        discovery_elapsed_ms $discovery_elapsed_ms \
        total_elapsed_ms $total_elapsed_ms canonical_pblock_count_after \
            $pblock_count_after floorplan_mutated 0 \
        implementation_commands_run 0 checkpoint_written 0 status $status] {
    puts $fp "$key=$value"
}
close $fp
puts "V5_COMPOSITE21_PARTITION_DIAGNOSIS_COMPLETE STATUS=$status"
if {$status ne "PASS"} {error "Composite21 partition diagnosis failed"}
close_design
