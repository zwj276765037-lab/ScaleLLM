# Read-only P4 hierarchy and boundary diagnosis.  This script characterizes
# the soft logic that is still free to move around the frozen 5453-DSP plan;
# it never changes placement, routing, constraints, or checkpoints.

set dcp [file normalize $::env(HAP_P4_DEEP_DCP)]
set out [file normalize $::env(HAP_P4_DEEP_DIR)]
set input_sha [file normalize $::env(HAP_P4_DEEP_INPUT_SHA)]
set expected_input_sha $::env(HAP_P4_DEEP_INPUT_MANIFEST_SHA256)
set expected_dcp_sha $::env(HAP_P4_DEEP_DCP_SHA256)
set failed_output_sha [file normalize $::env(HAP_P4_FAILED_OUTPUT_SHA)]
set expected_failed_output_sha $::env(HAP_P4_FAILED_OUTPUT_SHA256)
set expected_launcher [file normalize $::env(HAP_P4_DEEP_LAUNCHER)]
set diagnosis_script [file normalize [info script]]
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
file mkdir $out

proc hap_p4_deep_nonempty {path label} {
    if {![file exists $path] || ![file isfile $path] ||
        [file size $path] == 0} {
        error "Missing or empty $label: $path"
    }
}

proc hap_p4_deep_read {path label} {
    hap_p4_deep_nonempty $path $label
    set fp [open $path r]
    set text [read $fp]
    close $fp
    return $text
}

proc hap_p4_deep_sha256 {path} {
    set digest [lindex [exec sha256sum -- $path] 0]
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "Malformed SHA256 for $path: $digest"
    }
    return $digest
}

proc hap_p4_deep_manifest {path expected_count expected_sha label} {
    if {[hap_p4_deep_sha256 $path] ne $expected_sha} {
        error "$label manifest identity mismatch"
    }
    set entries [dict create]
    foreach raw [split [hap_p4_deep_read $path $label] "\n"] {
        set line [string trim $raw]
        if {$line eq ""} {continue}
        if {![regexp {^([0-9a-f]{64})[[:space:]]+\*?(.+)$} \
                $line -> expected file_name]} {
            error "Malformed $label manifest row: $line"
        }
        set normalized [file normalize [string trim $file_name]]
        if {[dict exists $entries $normalized]} {
            error "Duplicate $label manifest path: $normalized"
        }
        hap_p4_deep_nonempty $normalized "$label member"
        if {[hap_p4_deep_sha256 $normalized] ne $expected} {
            error "$label member SHA mismatch: $normalized"
        }
        dict set entries $normalized $expected
    }
    if {$expected_count >= 0 && [dict size $entries] != $expected_count} {
        error "$label manifest cardinality mismatch: [dict size $entries]"
    }
    return $entries
}

proc hap_p4_deep_require_line {path literal} {
    set count 0
    foreach line [split [hap_p4_deep_read $path evidence] "\n"] {
        if {$line eq $literal} {incr count}
    }
    if {$count != 1} {
        error "P4 evidence mismatch: path=$path literal=$literal count=$count"
    }
}

proc hap_p4_deep_unique {objects} {
    return [lsort -dictionary -unique $objects]
}

proc hap_p4_deep_slr_counts {cells} {
    set counts {0 0 0 0}
    if {[llength $cells] == 0} {return $counts}
    foreach value [get_property SLR_INDEX $cells] {
        if {[regexp {([0-2])$} $value -> index]} {
            lset counts $index [expr {[lindex $counts $index] + 1}]
        } else {
            lset counts 3 [expr {[lindex $counts 3] + 1}]
        }
    }
    return $counts
}

proc hap_p4_deep_filter_ref {cells pattern} {
    if {[llength $cells] == 0} {return {}}
    return [filter $cells "REF_NAME =~ $pattern"]
}

proc hap_p4_deep_resource_row {handle label selector cells} {
    if {[llength $cells] == 0} {
        error "P4 deep diagnosis selector is empty: $label $selector"
    }
    set lut [hap_p4_deep_filter_ref $cells LUT*]
    set ff [hap_p4_deep_filter_ref $cells FD*]
    set carry [hap_p4_deep_filter_ref $cells CARRY8]
    set f7 [hap_p4_deep_filter_ref $cells MUXF7]
    set f8 [hap_p4_deep_filter_ref $cells MUXF8]
    set ramb36 [hap_p4_deep_filter_ref $cells RAMB36E2]
    set ramb18 [hap_p4_deep_filter_ref $cells RAMB18E2]
    set dsp [hap_p4_deep_filter_ref $cells DSP48E2]
    set uram [hap_p4_deep_filter_ref $cells URAM288]
    puts $handle [join [list $label $selector [llength $cells] \
        [llength $lut] [llength $ff] [llength $carry] [llength $f7] \
        [llength $f8] [llength $ramb36] [llength $ramb18] \
        [llength $dsp] [llength $uram] [hap_p4_deep_slr_counts $cells] \
        [hap_p4_deep_slr_counts $lut] [hap_p4_deep_slr_counts $ff] \
        [hap_p4_deep_slr_counts $dsp] [hap_p4_deep_slr_counts $uram]] "\t"]
}

proc hap_p4_deep_cell_slrs {cells} {
    set result {}
    if {[llength $cells] == 0} {return $result}
    foreach value [get_property SLR_INDEX $cells] {
        if {[regexp {([0-2])$} $value -> index]} {
            lappend result $index
        }
    }
    return [lsort -integer -unique $result]
}

proc hap_p4_deep_net_metrics {nets} {
    set nets [hap_p4_deep_unique $nets]
    set cross 0
    set unresolved 0
    set driver_pins_total 0
    set sink_pins_total 0
    set pairs [dict create]
    foreach net $nets {
        set driver_pins [get_pins -quiet -leaf -of_objects $net \
            -filter {DIRECTION == OUT}]
        set sink_pins [get_pins -quiet -leaf -of_objects $net \
            -filter {DIRECTION == IN}]
        incr driver_pins_total [llength $driver_pins]
        incr sink_pins_total [llength $sink_pins]
        set driver_slrs [hap_p4_deep_cell_slrs \
            [get_cells -quiet -of_objects $driver_pins]]
        set sink_slrs [hap_p4_deep_cell_slrs \
            [get_cells -quiet -of_objects $sink_pins]]
        if {[llength $driver_slrs] == 0 || [llength $sink_slrs] == 0} {
            incr unresolved
        }
        set net_cross 0
        foreach source $driver_slrs {
            foreach sink $sink_slrs {
                dict incr pairs ${source}->${sink}
                if {$source != $sink} {set net_cross 1}
            }
        }
        if {$net_cross} {incr cross}
    }
    return [dict create nets [llength $nets] cross $cross \
        unresolved $unresolved driver_pins $driver_pins_total \
        sink_pins $sink_pins_total pairs $pairs]
}

proc hap_p4_deep_pairs_string {pairs} {
    set values {}
    foreach key [lsort -dictionary [dict keys $pairs]] {
        lappend values "$key:[dict get $pairs $key]"
    }
    if {[llength $values] == 0} {return NONE}
    return [join $values ,]
}

proc hap_p4_deep_boundary_row {handle label direction nets} {
    set metrics [hap_p4_deep_net_metrics $nets]
    puts $handle [join [list $label $direction [dict get $metrics nets] \
        [dict get $metrics cross] [dict get $metrics unresolved] \
        [dict get $metrics driver_pins] [dict get $metrics sink_pins] \
        [hap_p4_deep_pairs_string [dict get $metrics pairs]]] "\t"]
    return $metrics
}

proc hap_p4_deep_root_cells {root_name label} {
    set root [get_cells -quiet $root_name]
    if {[llength $root] != 1 || [get_property IS_PRIMITIVE $root]} {
        error "P4 deep hierarchy root mismatch: $label $root_name count=[llength $root]"
    }
    set cells [get_cells -quiet -hierarchical -filter \
        "NAME =~ ${root_name}/* && IS_PRIMITIVE"]
    if {[llength $cells] == 0} {
        error "P4 deep hierarchy primitives are empty: $label $root_name"
    }
    return [list $root $cells]
}

proc hap_p4_deep_root_boundaries {handle label root} {
    set input_pins [get_pins -quiet -of_objects $root \
        -filter {DIRECTION == IN}]
    set output_pins [get_pins -quiet -of_objects $root \
        -filter {DIRECTION == OUT}]
    if {[llength $input_pins] == 0 || [llength $output_pins] == 0} {
        error "P4 deep hierarchy boundary is empty: $label"
    }
    set input_nets [get_nets -quiet -of_objects $input_pins]
    set output_nets [get_nets -quiet -of_objects $output_pins]
    set incoming [hap_p4_deep_boundary_row $handle $label IN $input_nets]
    set outgoing [hap_p4_deep_boundary_row $handle $label OUT $output_nets]
    return [list $incoming $outgoing]
}

proc hap_p4_deep_dict_set {objects} {
    set result [dict create]
    foreach object $objects {
        dict set result [get_property NAME $object] 1
    }
    return $result
}

proc hap_p4_deep_intersection {left right} {
    set left_names [hap_p4_deep_dict_set $left]
    set result {}
    foreach object $right {
        if {[dict exists $left_names [get_property NAME $object]]} {
            lappend result $object
        }
    }
    return $result
}

proc hap_p4_deep_pblock_rows {handle label cells} {
    set assigned [dict create]
    set pblocks [get_pblocks -quiet -of_objects $cells]
    foreach pblock [lsort -dictionary $pblocks] {
        set intersection [hap_p4_deep_intersection $cells \
            [get_cells -quiet -of_objects $pblock]]
        if {[llength $intersection] == 0} {continue}
        foreach cell $intersection {
            dict set assigned [get_property NAME $cell] 1
        }
        puts $handle [join [list $label [get_property NAME $pblock] \
            [llength $intersection] \
            [llength [hap_p4_deep_filter_ref $intersection LUT*]] \
            [llength [hap_p4_deep_filter_ref $intersection FD*]] \
            [llength [hap_p4_deep_filter_ref $intersection DSP48E2]] \
            [llength [hap_p4_deep_filter_ref $intersection RAMB36E2]] \
            [llength [hap_p4_deep_filter_ref $intersection RAMB18E2]] \
            [llength [hap_p4_deep_filter_ref $intersection URAM288]] \
            [hap_p4_deep_slr_counts $intersection] \
            [get_property GRID_RANGES $pblock]] "\t"]
    }
    set unassigned [expr {[llength $cells] - [dict size $assigned]}]
    puts $handle [join [list $label NONE $unassigned 0 0 0 0 0 0 \
        {0 0 0 0} NONE] "\t"]
    return [dict create assigned [dict size $assigned] \
        unassigned $unassigned pblocks [llength $pblocks]]
}

proc hap_p4_deep_custom_boundary_nets {cells direction} {
    set inside [hap_p4_deep_dict_set $cells]
    if {$direction eq "IN"} {
        set pins [get_pins -quiet -of_objects $cells \
            -filter {DIRECTION == IN}]
    } else {
        set pins [get_pins -quiet -of_objects $cells \
            -filter {DIRECTION == OUT}]
    }
    set result {}
    foreach net [hap_p4_deep_unique \
            [get_nets -quiet -of_objects $pins]] {
        set is_boundary 0
        if {$direction eq "IN"} {
            set drivers [get_cells -quiet -of_objects \
                [get_pins -quiet -leaf -of_objects $net \
                    -filter {DIRECTION == OUT}]]
            if {[llength $drivers] == 0} {
                set is_boundary 1
            } else {
                foreach driver $drivers {
                    if {![dict exists $inside [get_property NAME $driver]]} {
                        set is_boundary 1
                        break
                    }
                }
            }
        } else {
            set sinks [get_cells -quiet -of_objects \
                [get_pins -quiet -leaf -of_objects $net \
                    -filter {DIRECTION == IN}]]
            foreach sink $sinks {
                if {![dict exists $inside [get_property NAME $sink]]} {
                    set is_boundary 1
                    break
                }
            }
        }
        if {$is_boundary} {lappend result $net}
    }
    return [hap_p4_deep_unique $result]
}

proc hap_p4_deep_custom_boundaries {handle label cells} {
    set incoming [hap_p4_deep_custom_boundary_nets $cells IN]
    set outgoing [hap_p4_deep_custom_boundary_nets $cells OUT]
    hap_p4_deep_boundary_row $handle $label IN $incoming
    hap_p4_deep_boundary_row $handle $label OUT $outgoing
}

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
if {[llength [get_designs -quiet]] != 0} {
    error "P4 deep diagnosis requires a fresh Vivado process"
}
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "P4 deep diagnosis requires HAP_JOBS=32"
}
foreach digest [list $expected_input_sha $expected_dcp_sha \
        $expected_failed_output_sha] {
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "P4 deep diagnosis received malformed SHA256"
    }
}
set_param general.maxThreads $jobs

set frozen [hap_p4_deep_manifest $input_sha 4 $expected_input_sha \
    p4_deep_input]
foreach required [list $dcp $failed_output_sha $diagnosis_script \
        $expected_launcher] {
    if {![dict exists $frozen $required]} {
        error "Required P4 deep input absent from manifest: $required"
    }
}
if {[hap_p4_deep_sha256 $dcp] ne $expected_dcp_sha} {
    error "P4 deep DCP identity mismatch"
}
set failed_entries [hap_p4_deep_manifest $failed_output_sha -1 \
    $expected_failed_output_sha p4_failed_output]
set failed_dir [file dirname $failed_output_sha]
set failed_summary [file join $failed_dir summary.txt]
set failed_launcher [file join $failed_dir launcher_status.txt]
foreach required [list $dcp $failed_summary $failed_launcher] {
    if {![dict exists $failed_entries $required]} {
        error "Required P4 failed evidence absent from output manifest: $required"
    }
}
foreach literal [list status=FAIL route_eligible=0 acceptance_evidence=0 \
        checkpoint_written=0 diagnostic_checkpoint_written=1 \
        dsp48e2=5453 uram288=752 slr_dsp48e2=2198\ 1173\ 2082 \
        slr_uram288=224\ 224\ 304 \
        congestion_level5_or_higher_windows=24 \
        congestion_level6_or_higher_windows=12 post_place_drc_errors=0] {
    hap_p4_deep_require_line $failed_summary $literal
}
foreach literal {status=FAIL route_eligible=0 acceptance_evidence=0
        checkpoint_written=0 bitstream_generated=0 final_exit_code=1} {
    hap_p4_deep_require_line $failed_launcher $literal
}

set flow_start_ms [clock milliseconds]
set phase_start_ms [clock milliseconds]
open_checkpoint $dcp
set open_checkpoint_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]
if {[get_property TOP [current_design]] ne \
        "hap_attention_mlp_production_core" ||
    [get_property PART [current_design]] ne "xcvu9p-flga2104-2L-e"} {
    error "P4 deep checkpoint design identity mismatch"
}
if {[llength [get_pblocks -quiet]] != 19} {
    error "P4 deep checkpoint must contain exactly 19 pblocks"
}

set input_root u_compute/u_mlp/u_input_frontend
set swiglu_root \
    u_compute/u_mlp/u_serial_command/u_gate_scheduler/u_swiglu
set root_specs [list \
    [list input_parent $input_root] \
    [list input_quant0 [format {%s/g_quant[0].u_quantizer} $input_root]] \
    [list input_quant1 [format {%s/g_quant[1].u_quantizer} $input_root]] \
    [list input_quant2 [format {%s/g_quant[2].u_quantizer} $input_root]] \
    [list input_quant3 [format {%s/g_quant[3].u_quantizer} $input_root]] \
    [list input_hadamard $input_root/u_hadamard] \
    [list input_cache0 $input_root/u_cache0] \
    [list input_cache1 $input_root/u_cache1] \
    [list swiglu_parent $swiglu_root] \
    [list swiglu_branch0 \
        [format {%s/g_row_branch[0].u_branch_leaf} $swiglu_root]] \
    [list swiglu_branch1 \
        [format {%s/g_row_branch[1].u_branch_leaf} $swiglu_root]] \
    [list swiglu_hadamard $swiglu_root/u_hadamard] \
    [list swiglu_quant0 \
        [format {%s/g_quantizer[0].u_quantizer} $swiglu_root]] \
    [list swiglu_quant1 \
        [format {%s/g_quantizer[1].u_quantizer} $swiglu_root]] \
    [list swiglu_quant2 \
        [format {%s/g_quantizer[2].u_quantizer} $swiglu_root]] \
    [list swiglu_quant3 \
        [format {%s/g_quantizer[3].u_quantizer} $swiglu_root]]]

set resource_fp [open [file join $out hierarchy_resources.tsv] w]
puts $resource_fp "label\tselector\tprimitives\tlut\tff\tcarry8\tmuxf7\tmuxf8\tramb36\tramb18\tdsp\turam\tprimitive_slr012u\tlut_slr012u\tff_slr012u\tdsp_slr012u\turam_slr012u"
set boundary_fp [open [file join $out hierarchy_boundaries.tsv] w]
puts $boundary_fp "label\tdirection\tboundary_nets\tcross_slr_nets\tunresolved_nets\tleaf_driver_pins\tleaf_sink_pins\tslr_pairs"
set pblock_fp [open [file join $out pblock_intersections.tsv] w]
puts $pblock_fp "label\tpblock\tprimitives\tlut\tff\tdsp\tramb36\tramb18\turam\tprimitive_slr012u\tgrid_ranges"

set root_count 0
set root_crossing_nets 0
foreach spec $root_specs {
    lassign $spec label root_name
    lassign [hap_p4_deep_root_cells $root_name $label] root cells
    hap_p4_deep_resource_row $resource_fp $label $root_name $cells
    lassign [hap_p4_deep_root_boundaries $boundary_fp $label $root] \
        incoming outgoing
    incr root_crossing_nets [dict get $incoming cross]
    incr root_crossing_nets [dict get $outgoing cross]
    hap_p4_deep_pblock_rows $pblock_fp $label $cells
    incr root_count
}
close $resource_fp
close $boundary_fp
close $pblock_fp
if {$root_count != 16} {error "P4 deep root count mismatch: $root_count"}

set input_primitives [lindex \
    [hap_p4_deep_root_cells $input_root input_parent_reopen] 1]
set swiglu_primitives [lindex \
    [hap_p4_deep_root_cells $swiglu_root swiglu_parent_reopen] 1]
set discovery_fp [open [file join $out discovered_storage_names.txt] w]
foreach cell $input_primitives {
    set name [get_property NAME $cell]
    if {[string match *input_buffer_row_r_reg* $name] ||
        [string match *bundle_u8_bank_r_reg* $name] ||
        [string match *bundle_meta_bank_r_reg* $name] ||
        [string match *g_bundle_row* $name]} {
        puts $discovery_fp "input\t$name"
    }
}
foreach cell $swiglu_primitives {
    set name [get_property NAME $cell]
    if {[string match *row_ring_s32_r_reg* $name]} {
        puts $discovery_fp "swiglu\t$name"
    }
}
close $discovery_fp

set custom_resource_fp [open [file join $out custom_resources.tsv] w]
puts $custom_resource_fp "label\tselector\tprimitives\tlut\tff\tcarry8\tmuxf7\tmuxf8\tramb36\tramb18\tdsp\turam\tprimitive_slr012u\tlut_slr012u\tff_slr012u\tdsp_slr012u\turam_slr012u"
set custom_boundary_fp [open [file join $out custom_boundaries.tsv] w]
puts $custom_boundary_fp "label\tdirection\tboundary_nets\tcross_slr_nets\tunresolved_nets\tleaf_driver_pins\tleaf_sink_pins\tslr_pairs"
set custom_pblock_fp [open [file join $out custom_pblock_intersections.tsv] w]
puts $custom_pblock_fp "label\tpblock\tprimitives\tlut\tff\tdsp\tramb36\tramb18\turam\tprimitive_slr012u\tgrid_ranges"

set input_row_groups 0
for {set row 0} {$row < 16} {incr row} {
    set selected {}
    foreach cell $input_primitives {
        set name [get_property NAME $cell]
        if {[regexp [format {/(input_buffer_row_r_reg|bundle_u8_bank_r_reg|bundle_meta_bank_r_reg)\[%d\]} $row] $name] ||
            [regexp [format {/g_bundle_row\[%d\]\.} $row] $name]} {
            lappend selected $cell
        }
    }
    set label input_row$row
    hap_p4_deep_resource_row $custom_resource_fp $label ROW_STORAGE \
        $selected
    hap_p4_deep_custom_boundaries $custom_boundary_fp $label $selected
    hap_p4_deep_pblock_rows $custom_pblock_fp $label $selected
    incr input_row_groups
}

set ring_groups 0
for {set bank 0} {$bank < 2} {incr bank} {
    for {set row 0} {$row < 16} {incr row} {
        set selected {}
        foreach cell $swiglu_primitives {
            set name [get_property NAME $cell]
            if {[regexp [format {/row_ring_s32_r_reg\[%d\]\[%d\]} \
                    $bank $row] $name]} {
                lappend selected $cell
            }
        }
        set label swiglu_ring_b${bank}_r${row}
        hap_p4_deep_resource_row $custom_resource_fp $label ROW_RING \
            $selected
        hap_p4_deep_custom_boundaries $custom_boundary_fp $label $selected
        hap_p4_deep_pblock_rows $custom_pblock_fp $label $selected
        incr ring_groups
    }
}
close $custom_resource_fp
close $custom_boundary_fp
close $custom_pblock_fp
if {$input_row_groups != 16 || $ring_groups != 32} {
    error "P4 deep custom group count mismatch"
}

set dsp [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}]
set uram [get_cells -quiet -hierarchical -filter {REF_NAME == URAM288}]
set dsp_slr [hap_p4_deep_slr_counts $dsp]
set uram_slr [hap_p4_deep_slr_counts $uram]
if {[llength $dsp] != 5453 || [llength $uram] != 752 ||
    $dsp_slr ne {2198 1173 2082 0} ||
    $uram_slr ne {224 224 304 0}} {
    error "P4 deep physical identity mismatch: DSP=[llength $dsp]/$dsp_slr URAM=[llength $uram]/$uram_slr"
}

set total_elapsed_ms [expr {[clock milliseconds] - $flow_start_ms}]
set summary_fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] \
        stage V5_P10_P4_DEEP_PARTITION_DIAGNOSIS \
        evidence_class READ_ONLY_P4_PARTITION_DIAGNOSIS jobs $jobs \
        input_dcp $dcp input_dcp_sha256 $expected_dcp_sha \
        input_manifest_sha256 $expected_input_sha input_manifest_entries 4 \
        failed_output_manifest $failed_output_sha \
        failed_output_manifest_sha256 $expected_failed_output_sha \
        failed_output_entries [dict size $failed_entries] \
        failed_placement_verified 1 pblock_count 19 \
        hierarchy_root_count $root_count input_row_group_count $input_row_groups \
        swiglu_ring_group_count $ring_groups \
        hierarchy_boundary_cross_slr_net_sum $root_crossing_nets \
        dsp48e2 [llength $dsp] uram288 [llength $uram] \
        slr_dsp48e2 $dsp_slr slr_uram288 $uram_slr \
        acceptance_evidence 0 route_eligible 0 floorplan_mutated 0 \
        implementation_commands_run 0 checkpoint_written 0 \
        open_checkpoint_elapsed_ms $open_checkpoint_elapsed_ms \
        total_elapsed_ms $total_elapsed_ms \
        status V5_P10_P4_DEEP_PARTITION_DIAGNOSIS_PASS] {
    puts $summary_fp "$key=$value"
}
close $summary_fp
puts "V5_P10_P4_DEEP_PARTITION_DIAGNOSIS ROOTS=$root_count INPUT_ROWS=$input_row_groups RING_ROWS=$ring_groups CROSSING_SUM=$root_crossing_nets STATUS=PASS"
close_design
