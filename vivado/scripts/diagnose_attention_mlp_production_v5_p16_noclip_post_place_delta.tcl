# Read-only Mission 0185 diagnosis for the retained P16 post-place checkpoint.
# The post-place image is reported first, then compared by primitive name with
# the authenticated post-opt image.  No implementation command is permitted.

set post_opt_dcp [file normalize $::env(HAP_P16_DELTA_POST_OPT_DCP)]
set post_place_dcp [file normalize $::env(HAP_P16_DELTA_POST_PLACE_DCP)]
set expected_post_opt_sha $::env(HAP_P16_DELTA_EXPECTED_POST_OPT_SHA256)
set expected_post_place_sha $::env(HAP_P16_DELTA_EXPECTED_POST_PLACE_SHA256)
set input_sha [file normalize $::env(HAP_P16_DELTA_INPUT_SHA)]
set out [file normalize $::env(HAP_P16_DELTA_OUT)]
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
set expected_removed_lut [expr {
    [info exists ::env(HAP_P16_DELTA_EXPECTED_REMOVED_LUT)] ?
    $::env(HAP_P16_DELTA_EXPECTED_REMOVED_LUT) : 1}]
set expected_ramb36 [expr {
    [info exists ::env(HAP_P16_DELTA_EXPECTED_RAMB36)] ?
    $::env(HAP_P16_DELTA_EXPECTED_RAMB36) : 801}]
set expected_manifest_count [expr {
    [info exists ::env(HAP_P16_DELTA_INPUT_COUNT)] ?
    $::env(HAP_P16_DELTA_INPUT_COUNT) : 4}]
set selector_lib [expr {
    [info exists ::env(HAP_P16_DELTA_SELECTOR_LIB)] &&
    $::env(HAP_P16_DELTA_SELECTOR_LIB) ne "" ?
    [file normalize $::env(HAP_P16_DELTA_SELECTOR_LIB)] : ""}]
set boundary_lib [expr {
    [info exists ::env(HAP_P16_DELTA_BOUNDARY_LIB)] &&
    $::env(HAP_P16_DELTA_BOUNDARY_LIB) ne "" ?
    [file normalize $::env(HAP_P16_DELTA_BOUNDARY_LIB)] : ""}]
set evidence_class [expr {
    [info exists ::env(HAP_P16_DELTA_EVIDENCE_CLASS)] ?
    $::env(HAP_P16_DELTA_EVIDENCE_CLASS) : "READ_ONLY_DCP_COMPARISON"}]
set pass_status [expr {
    [info exists ::env(HAP_P16_DELTA_PASS_STATUS)] ?
    $::env(HAP_P16_DELTA_PASS_STATUS) :
    "V5_P16_POST_PLACE_DELTA_DIAG_PASS"}]
set region2_name {u_compute/u_attention/u_compute/g_projection_rtl.u_projection/u_array/u_center12/u_region2_cols8_11}
file mkdir $out

proc hap_diag_read_nonempty {path label} {
    if {![file exists $path] || ![file isfile $path] || [file size $path] == 0} {
        error "Missing or empty $label: $path"
    }
    set fp [open $path r]
    set text [read $fp]
    close $fp
    return $text
}

proc hap_diag_sha256 {path} {
    set digest [lindex [exec sha256sum -- $path] 0]
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "Malformed SHA256 for $path"
    }
    return $digest
}

proc hap_diag_verify_manifest {path expected_count} {
    set count 0
    set seen [dict create]
    foreach raw [split [hap_diag_read_nonempty $path "input SHA manifest"] "\n"] {
        set line [string trim $raw]
        if {$line eq ""} {continue}
        if {![regexp {^([0-9a-f]{64})[[:space:]]+\*?(.+)$} \
                $line -> expected file_name]} {
            error "Malformed input SHA row: $line"
        }
        set normalized [file normalize [string trim $file_name]]
        if {[dict exists $seen $normalized]} {
            error "Duplicate input SHA path: $normalized"
        }
        hap_diag_read_nonempty $normalized "frozen diagnostic input"
        set actual [hap_diag_sha256 $normalized]
        if {$actual ne $expected} {
            error "Input SHA mismatch: file=$normalized expected=$expected actual=$actual"
        }
        dict set seen $normalized $expected
        incr count
    }
    if {$count != $expected_count} {
        error "Input SHA cardinality mismatch: expected=$expected_count actual=$count"
    }
    return $seen
}

proc hap_diag_count_ref_glob {objects pattern} {
    set count 0
    foreach ref [get_property REF_NAME $objects] {
        if {[string match $pattern $ref]} {incr count}
    }
    return $count
}

proc hap_diag_names {objects} {
    if {[llength $objects] == 0} {return {}}
    return [lsort -dictionary -unique [get_property NAME $objects]]
}

proc hap_diag_subtract {left right} {
    array set excluded {}
    foreach item $right {set excluded($item) 1}
    set result {}
    foreach item $left {
        if {![info exists excluded($item)]} {lappend result $item}
    }
    return [lsort -dictionary -unique $result]
}

proc hap_diag_sanitize {value} {
    return [string map [list "\r" " " "\n" " " "\t" " "] $value]
}

proc hap_diag_property {object property_name} {
    if {[catch {get_property $property_name $object} value]} {
        return <unsupported>
    }
    if {$value eq ""} {return <empty>}
    return [hap_diag_sanitize $value]
}

proc hap_diag_slr_audit {cells expected_slr} {
    set counts {0 0 0}
    set wrong 0
    set unplaced 0
    foreach cell $cells {
        set slr [get_property SLR_INDEX $cell]
        if {$slr eq ""} {
            incr unplaced
            continue
        }
        if {![string is integer -strict $slr] || $slr < 0 || $slr > 2} {
            error "Invalid SLR_INDEX for [get_property NAME $cell]: $slr"
        }
        lset counts $slr [expr {[lindex $counts $slr] + 1}]
        if {$slr != $expected_slr} {incr wrong}
    }
    return [dict create counts $counts wrong $wrong unplaced $unplaced]
}

proc hap_diag_timing_totals {path} {
    set text [hap_diag_read_nonempty $path "timing summary report"]
    if {![regexp -line -expanded -- {
            ^[[:space:]]*(-?[0-9]+[.][0-9]+)[[:space:]]+
            (-?[0-9]+[.][0-9]+)[[:space:]]+[0-9]+[[:space:]]+[0-9]+[[:space:]]+
            (-?[0-9]+[.][0-9]+)[[:space:]]+
            (-?[0-9]+[.][0-9]+)[[:space:]]+[0-9]+[[:space:]]+[0-9]+[[:space:]]+
            -?[0-9]+[.][0-9]+[[:space:]]+-?[0-9]+[.][0-9]+} \
            $text -> wns tns whs ths]} {
        error "Cannot parse design timing totals from $path"
    }
    return [dict create wns $wns tns $tns whs $whs ths $ths]
}

proc hap_diag_region2_snapshot {root_name residual_path lane_path require_placed} {
    set root [get_cells -quiet $root_name]
    if {[llength $root] != 1} {
        error "Region2 root cardinality mismatch: [llength $root]"
    }
    set root_prefix "${root_name}/"
    set primitives [lsort -dictionary -unique [get_cells -quiet -hierarchical \
        -filter "IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL && \
                 REF_NAME != GND && REF_NAME != VCC && \
                 NAME =~ ${root_name}/*"]]
    set rows0_3 {}
    set rows4_7 {}
    set residual {}
    set lane_counts [dict create]
    set lane_cells [dict create]
    foreach row {0 1 2 3 4 5 6 7} {
        foreach col {0 1 2 3} {
            set lane_name \
                "${root_prefix}g_row\[$row\].g_col\[$col\].u_lane"
            dict set lane_counts $lane_name 0
            dict set lane_cells $lane_name {}
        }
    }
    foreach primitive $primitives {
        set name [get_property NAME $primitive]
        set relative [string range $name [string length $root_prefix] end]
        if {[regexp {^(g_row\[([0-7])\]\.g_col\[[0-3]\]\.u_lane)(/|$)} \
                $relative -> lane_relative row boundary]} {
            set lane_name "${root_prefix}${lane_relative}"
            if {![dict exists $lane_counts $lane_name]} {
                error "Primitive maps to an unknown region2 lane: $name"
            }
            dict incr lane_counts $lane_name
            dict lappend lane_cells $lane_name $primitive
            if {$row < 4} {
                lappend rows0_3 $primitive
            } else {
                lappend rows4_7 $primitive
            }
        } else {
            lappend residual $primitive
        }
    }
    set rows0_3 [lsort -dictionary -unique $rows0_3]
    set rows4_7 [lsort -dictionary -unique $rows4_7]
    set residual [lsort -dictionary -unique $residual]
    set fp [open $residual_path w]
    puts $fp "name\tref_name\torig_ref_name\tloc\tbel\tslr_index"
    foreach primitive $residual {
        puts $fp "[get_property NAME $primitive]\t[get_property REF_NAME $primitive]\t[hap_diag_property $primitive ORIG_REF_NAME]\t[hap_diag_property $primitive LOC]\t[hap_diag_property $primitive BEL]\t[hap_diag_property $primitive SLR_INDEX]"
    }
    close $fp
    set lane_signatures [dict create]
    set lane_wrong 0
    set lane_unplaced 0
    set lfp [open $lane_path w]
    puts $lfp "row\tcol\tprimitives\tlut\tff\tdsp\tslr0\tslr1\tslr2\twrong_slr\tunplaced"
    foreach row {0 1 2 3 4 5 6 7} {
        foreach col {0 1 2 3} {
            set lane_name \
                "${root_prefix}g_row\[$row\].g_col\[$col\].u_lane"
            set cells [lsort -dictionary -unique \
                [dict get $lane_cells $lane_name]]
            set slr [expr {$require_placed ? \
                [hap_diag_slr_audit $cells 1] : \
                [dict create counts {0 0 0} wrong 0 unplaced 0]}]
            set signature [dict create primitives [llength $cells] \
                lut [hap_diag_count_ref_glob $cells LUT*] \
                ff [hap_diag_count_ref_glob $cells FD*] \
                dsp [hap_diag_count_ref_glob $cells DSP48E2]]
            dict set lane_signatures $lane_name $signature
            incr lane_wrong [dict get $slr wrong]
            incr lane_unplaced [dict get $slr unplaced]
            set counts [dict get $slr counts]
            puts $lfp "$row\t$col\t[dict get $signature primitives]\t[dict get $signature lut]\t[dict get $signature ff]\t[dict get $signature dsp]\t[lindex $counts 0]\t[lindex $counts 1]\t[lindex $counts 2]\t[dict get $slr wrong]\t[dict get $slr unplaced]"
        }
    }
    close $lfp
    set residual_slr [expr {$require_placed ? \
        [hap_diag_slr_audit $residual 1] : \
        [dict create counts {0 0 0} wrong 0 unplaced 0]}]
    return [dict create \
        total_names [hap_diag_names $primitives] \
        total_primitives [llength $primitives] \
        total_lut [hap_diag_count_ref_glob $primitives LUT*] \
        total_ff [hap_diag_count_ref_glob $primitives FD*] \
        total_dsp [hap_diag_count_ref_glob $primitives DSP48E2] \
        rows0_3_names [hap_diag_names $rows0_3] \
        rows0_3_primitives [llength $rows0_3] \
        rows0_3_lut [hap_diag_count_ref_glob $rows0_3 LUT*] \
        rows0_3_ff [hap_diag_count_ref_glob $rows0_3 FD*] \
        rows0_3_dsp [hap_diag_count_ref_glob $rows0_3 DSP48E2] \
        rows4_7_names [hap_diag_names $rows4_7] \
        rows4_7_primitives [llength $rows4_7] \
        rows4_7_lut [hap_diag_count_ref_glob $rows4_7 LUT*] \
        rows4_7_ff [hap_diag_count_ref_glob $rows4_7 FD*] \
        rows4_7_dsp [hap_diag_count_ref_glob $rows4_7 DSP48E2] \
        residual_names [hap_diag_names $residual] \
        residual_primitives [llength $residual] \
        residual_lut [hap_diag_count_ref_glob $residual LUT*] \
        residual_ff [hap_diag_count_ref_glob $residual FD*] \
        residual_dsp [hap_diag_count_ref_glob $residual DSP48E2] \
        lane_counts [lsort -integer -unique [dict values $lane_counts]] \
        lane_signatures $lane_signatures exact_partition_cover 1 \
        wrong_slr [expr {$lane_wrong + [dict get $residual_slr wrong]}] \
        unplaced [expr {$lane_unplaced + [dict get $residual_slr unplaced]}]]
}

proc hap_diag_congestion_counts {path} {
    set text [hap_diag_read_nonempty $path "congestion report"]
    set rows 0
    set level5 0
    set level6 0
    foreach line [split $text "\n"] {
        if {![regexp {^[[:space:]]*\|[[:space:]]*(North|South|East|West)[[:space:]]*\|[[:space:]]*(Global|Long|Short)[[:space:]]*\|[[:space:]]*([0-9]+)[[:space:]]*\|[[:space:]]*\([^|]+\)[[:space:]]*\|} \
                $line -> direction type level]} {
            continue
        }
        incr rows
        if {$level >= 5} {incr level5}
        if {$level >= 6} {incr level6}
    }
    if {$rows == 0} {error "Congestion report contains no data rows"}
    return [dict create rows $rows level5 $level5 level6 $level6]
}

proc hap_diag_write_cell_details {names output_path} {
    set fp [open $output_path w]
    puts $fp "cell\tproperty\tvalue"
    foreach name $names {
        set cell [get_cells -quiet $name]
        if {[llength $cell] != 1} {
            error "Delta cell is absent from post-opt checkpoint: $name"
        }
        foreach property_name {REF_NAME ORIG_REF_NAME PRIMITIVE_GROUP \
                PRIMITIVE_SUBGROUP INIT DONT_TOUCH KEEP MARK_DEBUG LOC BEL} {
            puts $fp "$name\t$property_name\t[hap_diag_property $cell $property_name]"
        }
        foreach pin [lsort -dictionary [get_pins -quiet -of_objects $cell]] {
            set nets [get_nets -quiet -of_objects $pin]
            set net_names [expr {[llength $nets] == 0 ? "<none>" : \
                [join [hap_diag_names $nets] ,]}]
            puts $fp "$name\tpin:[get_property NAME $pin]\tDIRECTION=[hap_diag_property $pin DIRECTION] REF_PIN_NAME=[hap_diag_property $pin REF_PIN_NAME] NET=$net_names"
        }
    }
    close $fp
}

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
if {[llength [get_designs -quiet]] != 0} {
    error "P16 delta diagnosis requires a fresh Vivado process"
}
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "P16 delta diagnosis requires HAP_JOBS=32"
}
if {![string is integer -strict $expected_removed_lut] ||
    $expected_removed_lut < 0 || $expected_removed_lut > 2} {
    error "P16 delta diagnosis requires an expected removal count in 0..2"
}
if {![string is integer -strict $expected_ramb36] || $expected_ramb36 <= 0 ||
    ![string is integer -strict $expected_manifest_count] ||
    $expected_manifest_count < 4} {
    error "P16 delta diagnosis has an invalid frozen resource/input contract"
}
foreach digest [list $expected_post_opt_sha $expected_post_place_sha] {
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "Malformed expected DCP SHA256"
    }
}
set frozen [hap_diag_verify_manifest $input_sha $expected_manifest_count]
set required_inputs [list $post_opt_dcp $post_place_dcp \
    [file normalize [info script]]]
foreach optional [list $selector_lib $boundary_lib] {
    if {$optional ne ""} {lappend required_inputs $optional}
}
foreach required $required_inputs {
    if {![dict exists $frozen $required]} {
        error "Required diagnostic input is absent from SHA manifest: $required"
    }
}
if {$selector_lib ne ""} {source $selector_lib}
if {$boundary_lib ne ""} {source $boundary_lib}
set actual_post_opt_sha [hap_diag_sha256 $post_opt_dcp]
set actual_post_place_sha [hap_diag_sha256 $post_place_dcp]
if {$actual_post_opt_sha ne $expected_post_opt_sha ||
    $actual_post_place_sha ne $expected_post_place_sha} {
    error "P16 diagnostic DCP identity mismatch"
}
set_param general.maxThreads $jobs

open_checkpoint $post_place_dcp
set post_place [hap_diag_region2_snapshot $region2_name \
    [file join $out post_place_region2_residual.tsv] \
    [file join $out post_place_region2_lanes.tsv] 1]
set boundary_ok 1
if {$boundary_lib ne ""} {
    set boundary [hap_mlp_p8_parent_boundary::audit]
    hap_mlp_p8_parent_boundary::write_audit $boundary \
        [file join $out p8_parent_ingress_boundary_post_place.txt] \
        V5_M0194_PARENT_INGRESS_BOUNDARY_POST_PLACE_PASS
}
set timing_path [file join $out timing_post_place.rpt]
report_timing_summary -delay_type min_max -max_paths 100 \
    -report_unconstrained -warn_on_violation -file $timing_path
report_timing -delay_type max -max_paths 50 -file \
    [file join $out timing_setup_paths_post_place.rpt]
report_timing -delay_type min -max_paths 50 -file \
    [file join $out timing_hold_paths_post_place.rpt]
set setup_path [get_timing_paths -quiet -delay_type max -max_paths 1]
set hold_path [get_timing_paths -quiet -delay_type min -max_paths 1]
if {[llength $setup_path] != 1 || [llength $hold_path] != 1} {
    error "Post-place timing query returned no path"
}
set wns [get_property SLACK [lindex $setup_path 0]]
set whs [get_property SLACK [lindex $hold_path 0]]
set setup_start [get_property NAME [get_property STARTPOINT_PIN [lindex $setup_path 0]]]
set setup_end [get_property NAME [get_property ENDPOINT_PIN [lindex $setup_path 0]]]
set hold_start [get_property NAME [get_property STARTPOINT_PIN [lindex $hold_path 0]]]
set hold_end [get_property NAME [get_property ENDPOINT_PIN [lindex $hold_path 0]]]
set timing_totals [hap_diag_timing_totals $timing_path]
report_drc -file [file join $out drc_post_place.rpt]
set drc_errors [llength [get_drc_violations -quiet -filter {SEVERITY == Error}]]
set congestion_path [file join $out congestion_post_place.rpt]
report_design_analysis -congestion -file $congestion_path
set congestion [hap_diag_congestion_counts $congestion_path]
report_utilization -file [file join $out utilization_post_place.rpt]
report_utilization -slr -file [file join $out utilization_slr_post_place.rpt]
set pblock_fp [open [file join $out utilization_pblocks_post_place.rpt] w]
foreach pblock [lsort -dictionary [get_pblocks -quiet]] {
    puts $pblock_fp "PBlock: [get_property NAME $pblock]"
    puts $pblock_fp [report_utilization -pblocks $pblock -return_string]
}
close $pblock_fp
set total_dsp [llength [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}]]
set total_uram [llength [get_cells -quiet -hierarchical -filter {REF_NAME == URAM288}]]
set total_ramb36 [llength [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB36E2}]]
set total_ramb18 [llength [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB18E2}]]
set pblock_count [llength [get_pblocks -quiet]]
set slr_dsp {NA NA NA}
set slr_uram {NA NA NA}
set global_unplaced NA
if {$selector_lib ne ""} {
    set slr_dsp [hap_v5_floorplan::placed_slr_counts DSP48E2]
    set slr_uram [hap_v5_floorplan::placed_slr_counts URAM288]
    set all_primitives [get_cells -quiet -hierarchical -filter {IS_PRIMITIVE}]
    set global_physical \
        [hap_v5_floorplan::physical_slr_audit_for_cells $all_primitives]
    set global_unplaced [dict get $global_physical direct_slr_empty]
}
set data_bufg 0
set data_bufg_names {}
foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}] {
    set outputs [get_pins -quiet -of_objects $cell -filter {DIRECTION == OUT}]
    if {[llength [get_clocks -quiet -of_objects $outputs]] == 0} {
        incr data_bufg
        lappend data_bufg_names [get_property NAME $cell]
    }
}
set fp [open [file join $out data_bufg_post_place.txt] w]
foreach name [lsort -dictionary $data_bufg_names] {puts $fp $name}
close $fp
close_design

open_checkpoint $post_opt_dcp
set post_opt [hap_diag_region2_snapshot $region2_name \
    [file join $out post_opt_region2_residual.tsv] \
    [file join $out post_opt_region2_lanes.tsv] 0]
set removed [hap_diag_subtract [dict get $post_opt residual_names] \
    [dict get $post_place residual_names]]
set added [hap_diag_subtract [dict get $post_place residual_names] \
    [dict get $post_opt residual_names]]
set fp [open [file join $out residual_removed_names.txt] w]
foreach name $removed {puts $fp $name}
close $fp
set fp [open [file join $out residual_added_names.txt] w]
foreach name $added {puts $fp $name}
close $fp
hap_diag_write_cell_details $removed \
    [file join $out residual_removed_post_opt_details.tsv]

set removed_lut 0
set removed_non_lut 0
foreach name $removed {
    set cell [get_cells -quiet $name]
    if {[llength $cell] == 1 &&
        [string match LUT* [get_property REF_NAME $cell]]} {
        incr removed_lut
    } else {
        incr removed_non_lut
    }
}
set lane_identity_ok 1
foreach lane_name [dict keys [dict get $post_opt lane_signatures]] {
    if {![dict exists [dict get $post_place lane_signatures] $lane_name] ||
        [dict get $post_opt lane_signatures $lane_name] ne
            [dict get $post_place lane_signatures $lane_name]} {
        set lane_identity_ok 0
    }
}

set post_opt_signature_ok [expr {
    [dict get $post_opt total_primitives] == 72896 &&
    [dict get $post_opt total_lut] == 35269 &&
    [dict get $post_opt total_ff] == 34743 &&
    [dict get $post_opt total_dsp] == 544 &&
    [dict get $post_opt rows0_3_primitives] == 26800 &&
    [dict get $post_opt rows0_3_lut] == 13504 &&
    [dict get $post_opt rows0_3_ff] == 12112 &&
    [dict get $post_opt rows0_3_dsp] == 272 &&
    [dict get $post_opt rows4_7_primitives] == 26800 &&
    [dict get $post_opt rows4_7_lut] == 13504 &&
    [dict get $post_opt rows4_7_ff] == 12112 &&
    [dict get $post_opt rows4_7_dsp] == 272 &&
    [dict get $post_opt residual_primitives] == 19296 &&
    [dict get $post_opt residual_lut] == 8261 &&
    [dict get $post_opt residual_ff] == 10519 &&
    [dict get $post_opt residual_dsp] == 0 &&
    [dict get $post_opt lane_counts] eq {1675}
}]
set post_place_delta_ok [expr {
    [dict get $post_place total_primitives] == 72896 - $expected_removed_lut &&
    [dict get $post_place total_lut] == 35269 - $expected_removed_lut &&
    [dict get $post_place total_ff] == 34743 &&
    [dict get $post_place total_dsp] == 544 &&
    [dict get $post_place rows0_3_primitives] == 26800 &&
    [dict get $post_place rows0_3_lut] == 13504 &&
    [dict get $post_place rows0_3_ff] == 12112 &&
    [dict get $post_place rows0_3_dsp] == 272 &&
    [dict get $post_place rows4_7_primitives] == 26800 &&
    [dict get $post_place rows4_7_lut] == 13504 &&
    [dict get $post_place rows4_7_ff] == 12112 &&
    [dict get $post_place rows4_7_dsp] == 272 &&
    [dict get $post_place residual_primitives] == 19296 - $expected_removed_lut &&
    [dict get $post_place residual_lut] == 8261 - $expected_removed_lut &&
    [dict get $post_place residual_ff] == 10519 &&
    [dict get $post_place residual_dsp] == 0 &&
    [dict get $post_place lane_counts] eq {1675} &&
    [dict get $post_place exact_partition_cover] == 1 &&
    [dict get $post_place wrong_slr] == 0 &&
    [dict get $post_place unplaced] == 0 &&
    $lane_identity_ok &&
    [llength $removed] == $expected_removed_lut &&
    $removed_lut == $expected_removed_lut && $removed_non_lut == 0 &&
    [llength $added] == 0
}]
set diagnostic_ok [expr {$post_opt_signature_ok && $post_place_delta_ok &&
    $total_dsp == 5449 && $total_uram == 752 &&
    $total_ramb36 == $expected_ramb36 && $total_ramb18 == 22 &&
    $pblock_count == 26 &&
    ($selector_lib eq "" || ($slr_dsp eq {1862 1777 1810} &&
        $slr_uram eq {224 224 304} && $global_unplaced == 0)) &&
    $boundary_ok}]
set status [expr {$diagnostic_ok ? $pass_status : "FAIL"}]
set fp [open [file join $out summary.txt] w]
foreach {key value} [list \
    tool [version -short] stage V5_P16_POST_PLACE_DELTA_DIAG \
    evidence_class $evidence_class \
    input_post_opt_dcp $post_opt_dcp \
    input_post_opt_dcp_sha256 $actual_post_opt_sha \
    input_post_place_dcp $post_place_dcp \
    input_post_place_dcp_sha256 $actual_post_place_sha \
    implementation_commands_run 0 checkpoint_written 0 route_eligible 0 \
    post_opt_region2_primitives [dict get $post_opt total_primitives] \
    post_opt_region2_lut [dict get $post_opt total_lut] \
    post_opt_region2_ff [dict get $post_opt total_ff] \
    post_opt_region2_dsp48e2 [dict get $post_opt total_dsp] \
    post_place_region2_primitives [dict get $post_place total_primitives] \
    post_place_region2_lut [dict get $post_place total_lut] \
    post_place_region2_ff [dict get $post_place total_ff] \
    post_place_region2_dsp48e2 [dict get $post_place total_dsp] \
    post_opt_residual_primitives [dict get $post_opt residual_primitives] \
    post_opt_residual_lut [dict get $post_opt residual_lut] \
    post_opt_residual_ff [dict get $post_opt residual_ff] \
    post_place_residual_primitives [dict get $post_place residual_primitives] \
    post_place_residual_lut [dict get $post_place residual_lut] \
    post_place_residual_ff [dict get $post_place residual_ff] \
    expected_residual_removed_lut $expected_removed_lut \
    residual_removed_count [llength $removed] \
    residual_removed_lut $removed_lut residual_removed_non_lut $removed_non_lut \
    residual_removed_names [join $removed ,] \
    residual_added_count [llength $added] \
    lane_identity_ok $lane_identity_ok \
    region2_partition_exact_cover [dict get $post_place exact_partition_cover] \
    region2_wrong_slr [dict get $post_place wrong_slr] \
    region2_unplaced [dict get $post_place unplaced] \
    post_place_dsp48e2 $total_dsp post_place_uram288 $total_uram \
    post_place_ramb36e2 $total_ramb36 post_place_ramb18e2 $total_ramb18 \
    slr_dsp48e2 $slr_dsp slr_uram288 $slr_uram \
    global_unplaced_primitives $global_unplaced \
    post_place_pblock_count $pblock_count post_place_data_bufg $data_bufg \
    post_place_drc_errors $drc_errors \
    congestion_data_rows [dict get $congestion rows] \
    congestion_level5_or_higher_windows [dict get $congestion level5] \
    congestion_level6_or_higher_windows [dict get $congestion level6] \
    post_place_wns_ns [dict get $timing_totals wns] \
    post_place_tns_ns [dict get $timing_totals tns] \
    post_place_whs_ns [dict get $timing_totals whs] \
    post_place_ths_ns [dict get $timing_totals ths] \
    setup_startpoint $setup_start setup_endpoint $setup_end \
    hold_startpoint $hold_start hold_endpoint $hold_end \
    post_opt_signature_ok $post_opt_signature_ok \
    post_place_delta_ok $post_place_delta_ok status $status] {
    puts $fp "$key=[hap_diag_sanitize $value]"
}
close $fp
close_design
puts "P16_POST_PLACE_DELTA removed=[llength $removed] added=[llength $added] WNS=$wns WHS=$whs DRC=$drc_errors L5=[dict get $congestion level5] L6=[dict get $congestion level6] STATUS=$status"
if {!$diagnostic_ok} {error "P16 post-place delta diagnosis failed"}
