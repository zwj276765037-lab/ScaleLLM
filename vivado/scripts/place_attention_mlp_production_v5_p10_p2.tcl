set hap_p10_source_procs_only [expr {
    [info exists ::env(HAP_P10_SOURCE_PROCS_ONLY)] &&
    $::env(HAP_P10_SOURCE_PROCS_ONLY) eq "1"}]
set place_script [file normalize [info script]]
set script_dir [file dirname $place_script]
if {!$hap_p10_source_procs_only} {
    set in_dcp [file normalize $::env(HAP_DCP)]
    set out [file normalize $::env(HAP_PLACE_DIR)]
    set input_sha [file normalize $::env(HAP_PLACE_INPUT_SHA)]
    set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)
    set expected_manifest_sha $::env(HAP_PLACE_INPUT_MANIFEST_SHA256)
    set selector_lib [file normalize $::env(HAP_PLACE_SELECTOR_LIB)]
    set geometry_lib [file normalize $::env(HAP_PLACE_GEOMETRY_LIB)]
    set expected_launcher [file normalize $::env(HAP_PLACE_LAUNCHER)]
    set io_audit [file normalize $::env(HAP_PLACE_IO_AUDIT)]
    set clock_xdc [file normalize $::env(HAP_PLACE_CLOCK_XDC)]
    set preplace_output_sha [file normalize $::env(HAP_P10_PREPLACE_OUTPUT_SHA)]
    set expected_preplace_output_sha $::env(HAP_P10_PREPLACE_OUTPUT_SHA256)
    set place_directive [expr {[info exists ::env(HAP_PLACE_DIRECTIVE)] ?
        $::env(HAP_PLACE_DIRECTIVE) : "AltSpreadLogic_high"}]
    set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
    set max_level5 [expr {
        [info exists ::env(HAP_MAX_POST_PLACE_LEVEL5_WINDOWS)] ?
        $::env(HAP_MAX_POST_PLACE_LEVEL5_WINDOWS) : 1}]
    set contract_variant P2_COHORT16_COL2_12_2
    set geometry_prefix p3_
    file mkdir $out
}

proc hap_p10_read_nonempty {path label} {
    if {![file exists $path] || ![file isfile $path] || [file size $path] == 0} {
        error "Missing or empty $label: $path"
    }
    set fp [open $path r]
    set text [read $fp]
    close $fp
    return $text
}

proc hap_p10_sha256 {path} {
    set digest [lindex [exec sha256sum -- $path] 0]
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "Malformed SHA256 for $path: $digest"
    }
    return $digest
}

proc hap_p10_verify_manifest {path expected_count expected_sha} {
    if {[hap_p10_sha256 $path] ne $expected_sha} {
        error "P10 manifest identity mismatch: $path"
    }
    set entries [dict create]
    foreach raw [split [hap_p10_read_nonempty $path manifest] "\n"] {
        set line [string trim $raw]
        if {$line eq ""} {continue}
        if {![regexp {^([0-9a-f]{64})[[:space:]]+\*?(.+)$} \
                $line -> expected file_name]} {
            error "Malformed P10 manifest row: $line"
        }
        set normalized [file normalize [string trim $file_name]]
        if {[dict exists $entries $normalized]} {
            error "Duplicate P10 manifest path: $normalized"
        }
        hap_p10_read_nonempty $normalized "frozen P10 input"
        if {[hap_p10_sha256 $normalized] ne $expected} {
            error "P10 manifest payload mismatch: $normalized"
        }
        dict set entries $normalized $expected
    }
    if {$expected_count >= 0 && [dict size $entries] != $expected_count} {
        error "P10 manifest cardinality mismatch: [dict size $entries]"
    }
    return $entries
}

proc hap_p10_parse_kv {path label} {
    set values [dict create]
    foreach raw [split [hap_p10_read_nonempty $path $label] "\n"] {
        set line [string trim $raw]
        if {$line eq ""} {continue}
        set split_at [string first = $line]
        if {$split_at < 1} {error "Malformed $label row: $line"}
        set key [string range $line 0 [expr {$split_at - 1}]]
        set value [string range $line [expr {$split_at + 1}] end]
        if {[dict exists $values $key]} {error "Duplicate $label key: $key"}
        dict set values $key $value
    }
    return $values
}

proc hap_p10_require_kv {values key expected label} {
    if {![dict exists $values $key] || [dict get $values $key] ne $expected} {
        set actual [expr {[dict exists $values $key] ? [dict get $values $key] : "<missing>"}]
        error "$label mismatch: $key expected=$expected actual=$actual"
    }
}

proc hap_p10_property_true {object property_name} {
    set value [string tolower [get_property $property_name $object]]
    return [expr {$value eq "1" || $value eq "true" || $value eq "yes"}]
}

proc hap_p10_cells_of_module {module_name} {
    return [get_cells -quiet -hierarchical -filter \
        "ORIG_REF_NAME == $module_name || REF_NAME == $module_name"]
}

proc hap_p10_check_timing_count {text category} {
    set pattern [format \
        {checking[[:space:]]+%s[[:space:]]+\(([0-9]+)\)} $category]
    if {![regexp -nocase -- $pattern $text -> count]} {
        error "P10 timing category is missing: $category"
    }
    return $count
}

proc hap_p10_create_hard_slr_pblock {name target cells} {
    if {[llength $cells] == 0} {error "P10 pblock is empty: $name"}
    create_pblock $name
    add_cells_to_pblock [get_pblocks $name] $cells
    resize_pblock [get_pblocks $name] -add [list SLR${target}]
    set_property IS_SOFT false [get_pblocks $name]
    set_property CONTAIN_ROUTING false [get_pblocks $name]
    set_property EXCLUDE_PLACEMENT false [get_pblocks $name]
}

proc hap_p10_mlp_local_clear_audit {require_placed} {
    set branches [lsort -dictionary [hap_p10_cells_of_module \
        hap_mlp_shared_local_slice8x12_s43_s45]]
    if {[llength $branches] != 2} {
        error "P10 expected two MLP branches, got [llength $branches]"
    }
    set total 0
    set protected 0
    set branch_counts {}
    set branch_slr_counts {}
    set all_clear {}
    set wrong 0
    foreach branch $branches target {0 2} {
        set branch_name [get_property NAME $branch]
        set clear_ff [get_cells -quiet -hierarchical -filter \
            "NAME =~ ${branch_name}/clear_local_r_reg* && REF_NAME =~ FD*"]
        if {[llength $clear_ff] != 1} {
            error "P10 local-clear count mismatch: $branch_name"
        }
        foreach cell $clear_ff {
            if {![hap_p10_property_true $cell DONT_TOUCH]} {
                error "P10 local-clear FF lost DONT_TOUCH: $cell"
            }
            incr protected
        }
        incr total
        lappend branch_counts 1
        lappend all_clear {*}$clear_ff
        if {$require_placed} {
            set audit [hap_v5_floorplan::wrong_slr_audit $clear_ff $target]
            if {[dict get $audit wrong] != 0 ||
                [dict get $audit direct_slr_empty] != 0} {
                error "P10 local-clear FF has wrong/unresolved SLR: $branch_name"
            }
            lappend branch_slr_counts [dict get $audit slr_counts]
            incr wrong [dict get $audit wrong]
        } else {
            lappend branch_slr_counts {0 0 0}
        }
    }
    set central [get_cells -quiet -hierarchical -filter {
        NAME =~ */maintenance_soft_clear_pulse_r_reg && REF_NAME =~ FD*}]
    if {[llength $central] != 1} {
        error "P10 central maintenance-clear FF mismatch"
    }
    set q [get_pins -quiet -of_objects $central -filter {REF_PIN_NAME == Q}]
    if {[llength $q] != 1} {error "P10 central clear Q mismatch"}
    set endpoint_cells [lsort -dictionary -unique [get_cells -quiet \
        -of_objects [all_fanout -flat -endpoints_only -from $q]]]
    set clear_endpoints {}
    foreach cell $all_clear {
        if {[lsearch -exact $endpoint_cells $cell] >= 0} {
            lappend clear_endpoints $cell
        }
    }
    set clear_endpoints [lsort -dictionary -unique $clear_endpoints]
    set all_clear [lsort -dictionary -unique $all_clear]
    if {[llength $clear_endpoints] != 2 || $clear_endpoints ne $all_clear} {
        error "P10 central clear does not reach both local boundaries"
    }
    set central_nets [lsort -dictionary -unique \
        [get_nets -quiet -of_objects $q]]
    if {[llength $central_nets] != 1} {
        error "P10 central clear net count mismatch"
    }
    set direct_sink_cells [lsort -dictionary -unique [get_cells -quiet \
        -of_objects [get_pins -quiet -leaf -of_objects $central_nets \
            -filter {DIRECTION == IN}]]]
    set direct_branch_state {}
    foreach branch $branches {
        set branch_name [get_property NAME $branch]
        foreach cell $direct_sink_cells {
            if {[string match "${branch_name}/*" [get_property NAME $cell]]} {
                lappend direct_branch_state $cell
            }
        }
    }
    set direct_branch_state [lsort -dictionary -unique $direct_branch_state]
    if {[llength $direct_branch_state] != 0} {
        error "P10 central clear directly consumes branch state"
    }
    return [dict create total $total protected $protected \
        branch0 [lindex $branch_counts 0] branch1 [lindex $branch_counts 1] \
        branch0_slr [lindex $branch_slr_counts 0] \
        branch1_slr [lindex $branch_slr_counts 1] wrong $wrong \
        central [llength $central] \
        central_branch_endpoints [llength $clear_endpoints] \
        central_direct_branch_state [llength $direct_branch_state]]
}

proc hap_p10_metadata_local_write_audit {require_placed} {
    set leaves [get_cells -quiet -hierarchical -filter {
        REF_NAME == hap_mlp_weight_meta_uram_leaf ||
        ORIG_REF_NAME == hap_mlp_weight_meta_uram_leaf}]
    if {[llength $leaves] != 4} {error "P10 metadata leaf count mismatch"}
    set wr_en [get_cells -quiet -hierarchical -filter {
        NAME =~ */wr_en_local_r_reg* && REF_NAME =~ FD*}]
    set wr_addr [get_cells -quiet -hierarchical -filter {
        NAME =~ */wr_addr_local_r_reg* && REF_NAME =~ FD*}]
    set wr_data [get_cells -quiet -hierarchical -filter {
        NAME =~ */wr_data_local_r_reg* && REF_NAME =~ FD*}]
    if {[llength $wr_en] != 4 || [llength $wr_addr] != 70 ||
        [llength $wr_data] != 896} {
        error "P10 metadata write-boundary cardinality mismatch"
    }
    set protected 0
    foreach cell [concat $wr_en $wr_addr $wr_data] {
        if {![hap_p10_property_true $cell DONT_TOUCH]} {
            error "P10 metadata write FF lost DONT_TOUCH: $cell"
        }
        incr protected
    }
    if {$protected != 970} {error "P10 metadata protected-FF mismatch"}
    set leaf_counts {}
    set leaf_slr_counts {}
    set wrong 0
    foreach {leaf_name expected target} {
        u_gate_bank0 243 0
        u_gate_bank1 243 2
        u_down_bank0 242 1
        u_down_bank1 242 1
    } {
        set local_ff [get_cells -quiet -hierarchical -filter \
            "NAME =~ */${leaf_name}/wr_*_local_r_reg* && REF_NAME =~ FD*"]
        if {[llength $local_ff] != $expected} {
            error "P10 metadata leaf FF mismatch: $leaf_name expected=$expected actual=[llength $local_ff]"
        }
        lappend leaf_counts [llength $local_ff]
        if {$require_placed} {
            set audit [hap_v5_floorplan::wrong_slr_audit $local_ff $target]
            if {[dict get $audit wrong] != 0 ||
                [dict get $audit direct_slr_empty] != 0} {
                error "P10 metadata leaf has wrong/unresolved SLR: $leaf_name"
            }
            lappend leaf_slr_counts [dict get $audit slr_counts]
            incr wrong [dict get $audit wrong]
        } else {
            lappend leaf_slr_counts {0 0 0}
        }
    }
    return [dict create leaves 4 wr_en 4 wr_addr 70 wr_data 896 \
        protected $protected leaf_counts $leaf_counts \
        leaf_slr_counts $leaf_slr_counts wrong $wrong]
}

proc hap_p10_mlp_capture_leaf_audit {branches require_placed} {
    if {[llength $branches] != 2} {
        error "P10 expected two MLP capture-leaf branches"
    }
    set leaves [get_cells -quiet -hierarchical -filter {
        REF_NAME == hap_a8w4_ingress_capture_leaf ||
        ORIG_REF_NAME == hap_a8w4_ingress_capture_leaf}]
    set leaf_lut [get_cells -quiet -hierarchical -filter {
        NAME =~ */u_leaf && REF_NAME == LUT1}]
    if {[llength $leaves] != 1632 || [llength $leaf_lut] != 1632} {
        error "P10 MLP capture-leaf total mismatch"
    }
    set branch_leaf_counts {}
    set branch_lut_counts {}
    set branch_slr_counts {}
    set wrong 0
    foreach branch [lsort -dictionary $branches] target {0 2} {
        set root [get_property NAME $branch]
        set local_leaves {}
        set local_lut {}
        foreach cell $leaves {
            if {[string match "${root}/*" [get_property NAME $cell]]} {
                lappend local_leaves $cell
            }
        }
        foreach cell $leaf_lut {
            if {[string match "${root}/*" [get_property NAME $cell]]} {
                lappend local_lut $cell
            }
        }
        if {[llength $local_leaves] != 816 || [llength $local_lut] != 816} {
            error "P10 MLP capture-leaf branch mismatch: $root"
        }
        lappend branch_leaf_counts [llength $local_leaves]
        lappend branch_lut_counts [llength $local_lut]
        if {$require_placed} {
            set audit [hap_v5_floorplan::wrong_slr_audit $local_lut $target]
            if {[dict get $audit wrong] != 0 ||
                [dict get $audit direct_slr_empty] != 0} {
                error "P10 MLP capture leaf has wrong/unresolved SLR: $root"
            }
            lappend branch_slr_counts [dict get $audit slr_counts]
            incr wrong [dict get $audit wrong]
        } else {
            lappend branch_slr_counts {0 0 0}
        }
    }
    return [dict create instances [llength $leaves] lut1 [llength $leaf_lut] \
        branch_instances $branch_leaf_counts branch_lut1 $branch_lut_counts \
        branch_slr_counts $branch_slr_counts wrong $wrong]
}

proc hap_p10_congestion_counts {text} {
    set header_count 0
    set data_rows 0
    set level5 0
    set level6 0
    foreach line [split $text "\n"] {
        if {[regexp {^[[:space:]]*\|[[:space:]]*Direction[[:space:]]*\|[[:space:]]*Type[[:space:]]*\|[[:space:]]*Level[[:space:]]*\|[[:space:]]*Window[[:space:]]*\|} \
                $line]} {
            incr header_count
            continue
        }
        if {![regexp {^[[:space:]]*\|[[:space:]]*(North|South|East|West)[[:space:]]*\|[[:space:]]*(Global|Long|Short)[[:space:]]*\|[[:space:]]*([0-9]+)[[:space:]]*\|[[:space:]]*\([^|]+\)[[:space:]]*\|} \
                $line -> direction type level]} {
            continue
        }
        incr data_rows
        if {$level >= 5} {incr level5}
        if {$level >= 6} {incr level6}
    }
    set clean_marker [expr {
        [string first "No congestion windows are found above level 5" $text] >= 0 ||
        [string first "No effective congestion windows are found above level 5" $text] >= 0}]
    set schema_ok [expr {$header_count == 1 && ($data_rows > 0 || $clean_marker)}]
    if {!$schema_ok} {error "P10 congestion report schema is unrecognized"}
    return [dict create header_count $header_count data_rows $data_rows \
        level5 $level5 level6 $level6 schema_ok $schema_ok]
}

proc hap_p10_write_summary {out values} {
    set fp [open [file join $out summary.txt] w]
    foreach {key value} $values {puts $fp "$key=$value"}
    close $fp
}

if {$hap_p10_source_procs_only} {return}

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
if {[llength [get_designs -quiet]] != 0} {
    error "P10 placement requires a fresh Vivado process"
}
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "P10 production placement requires HAP_JOBS=32"
}
if {![string is integer -strict $max_level5] || $max_level5 < 0 ||
    $max_level5 > 100} {
    error "P10 max Level-5 window count must be in 0..100"
}
foreach digest [list $expected_dcp_sha $expected_manifest_sha \
        $expected_preplace_output_sha] {
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "P10 received malformed SHA256"
    }
}
set_param general.maxThreads $jobs

set frozen_inputs [hap_p10_verify_manifest $input_sha 8 $expected_manifest_sha]
foreach required [list $in_dcp $selector_lib $geometry_lib $place_script \
        $expected_launcher $clock_xdc $io_audit $preplace_output_sha] {
    if {![dict exists $frozen_inputs $required]} {
        error "Required P10 input absent from manifest: $required"
    }
}
set actual_dcp_sha [hap_p10_sha256 $in_dcp]
if {$actual_dcp_sha ne $expected_dcp_sha} {
    error "P10 input DCP identity mismatch"
}

set preplace_outputs [hap_p10_verify_manifest $preplace_output_sha -1 \
    $expected_preplace_output_sha]
set preplace_dir [file dirname $preplace_output_sha]
set preplace_summary [file normalize [file join $preplace_dir summary.txt]]
set preplace_status [file normalize [file join $preplace_dir launcher_status.txt]]
set preplace_input_sha [file normalize [file join $preplace_dir INPUT_SHA256SUMS]]
foreach required [list $preplace_summary $preplace_status $preplace_input_sha] {
    if {![dict exists $preplace_outputs $required]} {
        error "P10 pre-place output manifest is incomplete: $required"
    }
}
set preplace_inputs [hap_p10_verify_manifest $preplace_input_sha 5 \
    [dict get $preplace_outputs $preplace_input_sha]]
foreach required [list $in_dcp $selector_lib $geometry_lib] {
    if {![dict exists $preplace_inputs $required]} {
        error "P10 pre-place lineage is missing $required"
    }
}
set preplace [hap_p10_parse_kv $preplace_summary "pre-place summary"]
foreach {key value} {
    status V5_PRE_PLACE_CONTRACT_AUDIT_PASS
    evidence_class V5_PRE_PLACE_READ_ONLY_CONTRACT
    contract_variant P2_COHORT16_COL2_12_2
    dsp48e2 5453
    uram288 752
    mlp_kernel_dsp48e2 3072
    metadata_leaf_instances 4
    metadata_local_wr_en_ff 4
    metadata_local_wr_addr_ff 70
    metadata_local_wr_data_ff 896
    metadata_local_write_protected_ff 970
    mlp_capture_leaf_instances 1632
    mlp_capture_leaf_lut1 1632
    branch0_capture_leaf_instances 816
    branch1_capture_leaf_instances 816
    branch0_capture_leaf_lut1 816
    branch1_capture_leaf_lut1 816
    compute_clock_buffer_none_ok 1
    geometry_pblock_prefix p3_
    canonical_pblock_count 11
    geometry_pblock_count 10
    geometry_region0_input_primitives 3136
    geometry_region3_input_primitives 2112
    geometry_owner_region2_weight_primitives 2048
    geometry_region0_input_ok 1
    geometry_region3_input_ok 1
    geometry_owner_region2_weight_ok 1
    pblock_count 21
    pblock_dsp_coverage 5453
    pblock_uram_coverage 752
    pblock_overlap 0
    pre_place_drc_errors 0
    checkpoint_written 0
    implementation_commands_run 0
} {
    hap_p10_require_kv $preplace $key $value "P10 pre-place summary"
}
hap_p10_require_kv $preplace input_dcp $in_dcp "P10 pre-place summary"
hap_p10_require_kv $preplace input_dcp_sha256 $actual_dcp_sha \
    "P10 pre-place summary"
set preplace_launcher [hap_p10_parse_kv $preplace_status \
    "pre-place launcher status"]
foreach {key value} {
    status PASS
    final_exit_code 0
    vivado_exit_code 0
    input_sha_recheck_exit_code 0
    input_manifest_sha_match 1
    audit_gate_exit_code 0
    checkpoint_written 0
    implementation_commands_run 0
} {
    hap_p10_require_kv $preplace_launcher $key $value \
        "P10 pre-place launcher"
}

set xdc_text [hap_p10_read_nonempty $clock_xdc "P10 clock XDC"]
set xdc_code ""
foreach line [split $xdc_text "\n"] {
    if {![regexp {^[[:space:]]*#} $line]} {append xdc_code $line "\n"}
}
set forbidden_false_path [join {set false path} _]
set forbidden_datapath "-[join {datapath only} _]"
if {[regexp -nocase -- [format {%s|%s} $forbidden_false_path \
        $forbidden_datapath] $xdc_code]} {
    error "P10 XDC contains a forbidden timing waiver"
}
if {[llength [regexp -all -inline {create_clock[[:space:]]} $xdc_code]] != 3 ||
    [llength [regexp -all -inline {set_input_delay[[:space:]]} $xdc_code]] != 6 ||
    [llength [regexp -all -inline {set_output_delay[[:space:]]} $xdc_code]] != 6 ||
    [llength [regexp -all -inline {set_clock_groups[[:space:]]+-asynchronous} \
        $xdc_code]] != 1} {
    error "P10 XDC command cardinality mismatch"
}

source $selector_lib
source $geometry_lib
open_checkpoint $in_dcp
read_xdc $clock_xdc
source $io_audit
foreach {name period} {core_clk 10.000 ddr0_clk 3.333 ddr1_clk 3.333} {
    set clocks [get_clocks -quiet $name]
    if {[llength $clocks] != 1 ||
        abs([get_property PERIOD $clocks] - $period) > 0.001} {
        error "P10 clock contract mismatch: $name"
    }
}

set compute_nets [get_nets -quiet -hierarchical -filter {NAME =~ u_compute/*}]
if {[llength $compute_nets] == 0} {
    error "P10 compute-net selector is empty"
}
set_property CLOCK_BUFFER_TYPE NONE $compute_nets
set compute_clock_buffer_none_count 0
foreach net $compute_nets {
    if {[get_property CLOCK_BUFFER_TYPE $net] ne "NONE"} {
        error "P10 compute net lost CLOCK_BUFFER_TYPE NONE: $net"
    }
    incr compute_clock_buffer_none_count
}

set plan [hap_v5_floorplan::discover $contract_variant]
set projection_root [file dirname \
    [get_property NAME [dict get $plan projection_array]]]
set geometry_plan [hap_projection_ooc_floorplan::discover $projection_root 1]
set compact_input [hap_p10_cells_of_module hap_mlp_input_frontend16_compact_cache]
set down_elastic [hap_p10_cells_of_module hap_mlp_down_branch_elastic2_s24]
set pre_clear [hap_p10_mlp_local_clear_audit 0]
set pre_metadata [hap_p10_metadata_local_write_audit 0]
set pre_capture [hap_p10_mlp_capture_leaf_audit \
    [hap_p10_cells_of_module hap_mlp_shared_local_slice8x12_s43_s45] 0]
if {[llength $compact_input] != 1 || [llength $down_elastic] != 2 ||
    [dict get $pre_clear total] != 2 || [dict get $pre_clear protected] != 2 ||
    [dict get $pre_metadata protected] != 970 ||
    [dict get $pre_capture instances] != 1632 ||
    [dict get $pre_capture lut1] != 1632} {
    error "P10 pre-place architecture identity mismatch"
}
hap_v5_floorplan::write_discovery $plan \
    [file join $out selectors_pre_place.txt] V5_P10_P2_SELECTORS_PASS
foreach spec [hap_v5_floorplan::pblock_specs $plan $contract_variant] {
    hap_p10_create_hard_slr_pblock [dict get $spec name] \
        [dict get $spec target] [dict get $plan [dict get $spec key]]
}
hap_projection_ooc_floorplan::apply $geometry_plan $geometry_prefix 0
set pre_geometry_audit [hap_projection_ooc_floorplan::audit_pblocks \
    $geometry_plan 1 $geometry_prefix 1]
set pre_audit [hap_v5_floorplan::audit_pblock_contract \
    $plan 0 $contract_variant \
    [hap_projection_ooc_floorplan::specs $geometry_plan $geometry_prefix]]
set pre_total_pblock_count [llength [get_pblocks -quiet]]
if {[dict get $pre_audit pblock_count] != 11 ||
    [dict get $pre_geometry_audit pblock_count] != 10 ||
    $pre_total_pblock_count != 21} {
    error "P10 pre-place pblock cardinality mismatch"
}
hap_v5_floorplan::write_pblock_audit $pre_audit \
    [file join $out pblocks_pre_place.txt] V5_P10_P2_PBLOCK_PRE_PLACE_PASS
report_drc -file [file join $out drc_pre_place.rpt]
set pre_drc_errors [llength [get_drc_violations -quiet -filter {
    SEVERITY == Error}]]
if {$pre_drc_errors != 0} {error "P10 pre-place DRC failed"}

place_design -directive $place_directive

set rediscovery_rc [catch {
    set post_plan [hap_v5_floorplan::discover $contract_variant]
    set post_projection_root [file dirname \
        [get_property NAME [dict get $post_plan projection_array]]]
    set post_geometry_plan \
        [hap_projection_ooc_floorplan::discover $post_projection_root 1]
    set post_geometry_audit [hap_projection_ooc_floorplan::audit_pblocks \
        $post_geometry_plan 0 $geometry_prefix 1]
    set post_audit [hap_v5_floorplan::audit_pblock_contract \
        $post_plan 1 $contract_variant \
        [hap_projection_ooc_floorplan::specs \
            $post_geometry_plan $geometry_prefix]]
    set post_geometry_placement \
        [hap_projection_ooc_floorplan::audit_placement $post_geometry_plan]
    set post_total_pblock_count [llength [get_pblocks -quiet]]
    set post_compute_nets \
        [get_nets -quiet -hierarchical -filter {NAME =~ u_compute/*}]
    if {[llength $post_compute_nets] == 0} {
        error "P10 post-place compute-net selector is empty"
    }
    set post_compute_clock_buffer_none_count 0
    foreach net $post_compute_nets {
        if {[get_property CLOCK_BUFFER_TYPE $net] ne "NONE"} {
            error "P10 post-place compute net lost CLOCK_BUFFER_TYPE NONE: $net"
        }
        incr post_compute_clock_buffer_none_count
    }
    set physical [hap_v5_floorplan::physical_metrics $post_plan $post_audit]
    set post_compact_input [hap_p10_cells_of_module \
        hap_mlp_input_frontend16_compact_cache]
    set post_down_elastic [hap_p10_cells_of_module \
        hap_mlp_down_branch_elastic2_s24]
    set post_clear [hap_p10_mlp_local_clear_audit 1]
    set post_metadata [hap_p10_metadata_local_write_audit 1]
    set post_capture [hap_p10_mlp_capture_leaf_audit \
        [hap_p10_cells_of_module hap_mlp_shared_local_slice8x12_s43_s45] 1]
    hap_v5_floorplan::write_discovery $post_plan \
        [file join $out selectors_post_place.txt] \
        V5_P10_P2_POST_PLACE_SELECTORS_PASS
    hap_v5_floorplan::write_pblock_audit $post_audit \
        [file join $out pblocks_post_place.txt] \
        V5_P10_P2_PBLOCK_POST_PLACE_PASS
    hap_projection_ooc_floorplan::write_plan $post_geometry_plan \
        [file join $out attention_geometry_post_place.txt] \
        V5_P10_P3_ATTENTION_GEOMETRY_POST_PLACE_PASS
    hap_projection_ooc_floorplan::write_placement $post_geometry_placement \
        [file join $out attention_geometry_placement.txt] \
        V5_P10_P3_ATTENTION_GEOMETRY_PLACEMENT_PASS
} rediscovery_error]
if {$rediscovery_rc != 0} {
    set diagnostic_dcp [file join $out post_place_diagnostic_only.dcp]
    set diagnostic_written [expr {![catch {
        write_checkpoint -force $diagnostic_dcp}]}]
    set clean_error [string map [list "\r" " " "\n" " "] \
        $rediscovery_error]
    hap_p10_write_summary $out [list tool [version -short] \
        stage V5_P10_P2_POST_PLACE_REDISCOVERY flow_mode accept \
        failure_stage post_place_live_rediscovery acceptance_evidence 0 \
        route_eligible 0 checkpoint_written 0 \
        diagnostic_checkpoint_written $diagnostic_written \
        input_dcp $in_dcp input_dcp_sha256 $actual_dcp_sha \
        input_manifest_sha256 [hap_p10_sha256 $input_sha] \
        input_manifest_entries 8 provenance_verified 1 \
        pre_place_verified 1 post_rediscovery_error $clean_error status FAIL]
    close_design
    error "P10 post-place rediscovery failed: $rediscovery_error"
}

set congestion_path [file join $out congestion_post_place.rpt]
report_design_analysis -congestion -file $congestion_path
set congestion [hap_p10_congestion_counts \
    [hap_p10_read_nonempty $congestion_path "P10 congestion report"]]
set level5 [dict get $congestion level5]
set level6 [dict get $congestion level6]
set slr_dsp [dict get $physical slr_dsp]
set slr_uram [dict get $physical slr_uram]
set slr_ramb36 [dict get $physical slr_ramb36]
set wrong_total [dict get $physical wrong_total]
set unplaced [dict get $physical unplaced]
set clock_bufg 0
set data_bufg 0
foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}] {
    set outputs [get_pins -quiet -of_objects $cell -filter {DIRECTION == OUT}]
    if {[llength [get_clocks -quiet -of_objects $outputs]] != 0} {
        incr clock_bufg
    } else {
        incr data_bufg
    }
}
set resource_ok [expr {[dict get $post_plan total_dsp] == 5453 &&
    [dict get $post_plan total_uram] == 752 &&
    [dict get $post_plan kernel_dsp] == 3072 &&
    [dict get $post_plan history2_count] == 2 &&
    [dict get $post_plan generic_repack_count] == 0 &&
    [dict get $post_plan projection_weight_capture_ok] == 1}]
set structure_ok [expr {[llength $post_compact_input] == 1 &&
    [llength $post_down_elastic] == 2 &&
    [dict get $post_clear total] == 2 &&
    [dict get $post_clear protected] == 2 &&
    [dict get $post_clear branch0_slr] eq {1 0 0} &&
    [dict get $post_clear branch1_slr] eq {0 0 1} &&
    [dict get $post_clear wrong] == 0 &&
    [dict get $post_metadata leaves] == 4 &&
    [dict get $post_metadata wr_en] == 4 &&
    [dict get $post_metadata wr_addr] == 70 &&
    [dict get $post_metadata wr_data] == 896 &&
    [dict get $post_metadata protected] == 970 &&
    [dict get $post_metadata leaf_counts] eq {243 243 242 242} &&
    [dict get $post_metadata leaf_slr_counts] eq \
        {{243 0 0} {0 0 243} {0 242 0} {0 242 0}} &&
    [dict get $post_metadata wrong] == 0 &&
    [dict get $post_capture instances] == 1632 &&
    [dict get $post_capture lut1] == 1632 &&
    [dict get $post_capture branch_instances] eq {816 816} &&
    [dict get $post_capture branch_lut1] eq {816 816} &&
    $post_compute_clock_buffer_none_count > 0 &&
    [dict get $post_capture branch_slr_counts] eq \
        {{816 0 0} {0 0 816}} && [dict get $post_capture wrong] == 0}]
set uram_distribution_ok [expr {$slr_uram eq {224 224 304}}]
set placement_ok [expr {[hap_v5_floorplan::physical_ok $post_plan $physical] &&
    [dict get $pre_audit ok] && [dict get $post_audit ok] &&
    [dict get $post_audit pblock_count] == 11 &&
    [dict get $pre_geometry_audit pblock_count] == 10 &&
    [dict get $post_geometry_audit pblock_count] == 10 &&
    $pre_total_pblock_count == 21 && $post_total_pblock_count == 21 &&
    [dict get $post_geometry_placement ok] &&
    [hap_projection_ooc_floorplan::region0_input_localization_ok \
        $post_geometry_plan] &&
    [hap_projection_ooc_floorplan::region3_input_localization_ok \
        $post_geometry_plan] &&
    [hap_projection_ooc_floorplan::owner_region2_weight_anchor_ok \
        $post_geometry_plan] &&
    [dict get $post_audit placed_wrong] == 0 && $wrong_total == 0 &&
    $unplaced == 0 && $uram_distribution_ok}]
set optimizer_extras_ok [expr {
    [dict get $post_audit optimizer_extra_count] >= 0 &&
    [dict get $post_audit optimizer_extra_count] <= 4096}]
set fast_gate_ok [expr {$resource_ok && $structure_ok && $placement_ok &&
    $optimizer_extras_ok && $pre_drc_errors == 0 && $data_bufg == 0 &&
    $level6 == 0 && $level5 <= $max_level5}]

set fast_fp [open [file join $out post_place_fast_gate.txt] w]
foreach {key value} [list resource_ok $resource_ok structure_ok $structure_ok \
    placement_ok $placement_ok optimizer_extras_ok $optimizer_extras_ok \
    pre_place_drc_errors $pre_drc_errors data_bufg $data_bufg \
    level5_or_higher_windows $level5 level6_or_higher_windows $level6 \
    max_level5_windows $max_level5 fast_gate_ok $fast_gate_ok] {
    puts $fast_fp "$key=$value"
}
close $fast_fp
if {!$fast_gate_ok} {
    set diagnostic_dcp [file join $out post_place_diagnostic_only.dcp]
    set diagnostic_written [expr {![catch {
        write_checkpoint -force $diagnostic_dcp}]}]
    hap_p10_write_summary $out [list tool [version -short] \
        part [dict get $post_plan part] top [dict get $post_plan top] \
        stage V5_P10_P2_POST_PLACE_FAST_GATE flow_mode accept \
        failure_stage post_place_fast_gate acceptance_evidence 0 \
        route_eligible 0 checkpoint_written 0 \
        diagnostic_checkpoint_written $diagnostic_written \
        input_dcp $in_dcp input_dcp_sha256 $actual_dcp_sha \
        input_manifest_sha256 [hap_p10_sha256 $input_sha] \
        input_manifest_entries 8 provenance_verified 1 \
        pre_place_verified 1 pblock_contract_variant $contract_variant \
        place_directive $place_directive jobs $jobs core_clock_mhz 100 \
        ddr0_clock_mhz 300 ddr1_clock_mhz 300 \
        dsp48e2 [dict get $post_plan total_dsp] \
        uram288 [dict get $post_plan total_uram] \
        slr0_dsp48e2 [lindex $slr_dsp 0] \
        slr1_dsp48e2 [lindex $slr_dsp 1] \
        slr2_dsp48e2 [lindex $slr_dsp 2] \
        slr0_uram288 [lindex $slr_uram 0] \
        slr1_uram288 [lindex $slr_uram 1] \
        slr2_uram288 [lindex $slr_uram 2] \
        unplaced_primitives $unplaced wrong_slr_primitives $wrong_total \
        metadata_local_write_wrong_slr [dict get $post_metadata wrong] \
        congestion_level5_or_higher_windows $level5 \
        congestion_level6_or_higher_windows $level6 \
        resource_ok $resource_ok structure_ok $structure_ok \
        placement_ok $placement_ok optimizer_extras_ok $optimizer_extras_ok \
        fast_gate_ok 0 status FAIL]
    close_design
    error "P10 placement rejected by post-place fast gate"
}

report_utilization -file [file join $out utilization_post_place.rpt]
report_utilization -hierarchical -hierarchical_depth 12 -file \
    [file join $out utilization_hier_post_place.rpt]
report_utilization -slr -file [file join $out utilization_slr_post_place.rpt]
set timing_text [report_timing_summary -delay_type min_max -max_paths 100 \
    -report_unconstrained -warn_on_violation -return_string]
set fp [open [file join $out timing_post_place.rpt] w]
puts $fp $timing_text
close $fp
report_cdc -details -file [file join $out cdc_post_place.rpt]
report_clock_interaction -delay_type min_max -file \
    [file join $out clock_interaction_post_place.rpt]
report_clock_utilization -file [file join $out clock_utilization_post_place.rpt]
report_drc -file [file join $out drc_post_place.rpt]
set post_drc_errors [llength [get_drc_violations -quiet -filter {
    SEVERITY == Error}]]
set exceptions_path [file join $out exceptions_coverage_post_place.rpt]
report_exceptions -coverage -file $exceptions_path

set no_clock [hap_p10_check_timing_count $timing_text no_clock]
set unconstrained [hap_p10_check_timing_count $timing_text \
    unconstrained_internal_endpoints]
set no_input_delay [hap_p10_check_timing_count $timing_text no_input_delay]
set no_output_delay [hap_p10_check_timing_count $timing_text no_output_delay]
set partial_input_delay [hap_p10_check_timing_count $timing_text \
    partial_input_delay]
set partial_output_delay [hap_p10_check_timing_count $timing_text \
    partial_output_delay]
set timing_coverage_ok [expr {$no_clock == 0 && $unconstrained == 0 &&
    $no_input_delay == 3 && $no_output_delay == 0 &&
    $partial_input_delay == 0 && $partial_output_delay == 0}]

set cdc_text [hap_p10_read_nonempty [file join $out cdc_post_place.rpt] \
    "P10 CDC report"]
if {![regexp -line \
        {^[[:space:]]*ID[[:space:]]+Severity[[:space:]]+Count[[:space:]]+Description[[:space:]]*$} \
        $cdc_text]} {
    error "P10 CDC report summary header is missing"
}
set cdc_critical 0
foreach {whole count} [regexp -all -inline -line -nocase \
        {^[^\n]*[[:space:]]Critical[[:space:]]+([1-9][0-9]*)[[:space:]]+[^\n]*$} \
        $cdc_text] {
    incr cdc_critical $count
}
set exception_text [hap_p10_read_nonempty $exceptions_path \
    "P10 exception report"]
set false_path_rows [regexp -all -line \
    {^[[:space:]]*[0-9]+[[:space:]]+False Path[[:space:]]} $exception_text]
set datapath_only_rows [regexp -all -line \
    {^[[:space:]]*[0-9]+[[:space:]]+(Max|Min) Delay.*Datapath} $exception_text]

set setup_path [get_timing_paths -quiet -delay_type max -max_paths 1]
set hold_path [get_timing_paths -quiet -delay_type min -max_paths 1]
if {[llength $setup_path] != 1 || [llength $hold_path] != 1} {
    error "P10 timing query returned no path"
}
set wns [get_property SLACK [lindex $setup_path 0]]
set whs [get_property SLACK [lindex $hold_path 0]]
set policy_ok [expr {$post_drc_errors == 0 && $false_path_rows == 0 &&
    $datapath_only_rows == 0 && $data_bufg == 0 && $timing_coverage_ok &&
    $cdc_critical == 0}]
set status [expr {$fast_gate_ok && $policy_ok ?
    "V5_PRODUCTION_PLACE_PASS" : "FAIL"}]
set route_eligible [expr {$status eq "V5_PRODUCTION_PLACE_PASS"}]
if {$route_eligible} {
    write_checkpoint -force [file join $out post_place.dcp]
}

set attention_island_record [dict get $post_audit records \
    pb_v5_attention_row_kv_cache_slr0]
hap_p10_write_summary $out [list tool [version -short] \
    part [dict get $post_plan part] top [dict get $post_plan top] \
    stage V5_P10_P2_POST_PLACE_ACCEPT flow_mode accept \
    acceptance_evidence $route_eligible route_eligible $route_eligible \
    checkpoint_written $route_eligible input_dcp $in_dcp \
    input_dcp_sha256 $actual_dcp_sha \
    input_manifest_sha256 [hap_p10_sha256 $input_sha] \
    input_manifest_entries 8 provenance_verified 1 \
    pre_place_manifest $preplace_output_sha \
    pre_place_manifest_sha256 $expected_preplace_output_sha \
    pre_place_verified 1 place_directive $place_directive jobs $jobs \
    core_clock_mhz 100 ddr0_clock_mhz 300 ddr1_clock_mhz 300 \
    dsp48e2 [dict get $post_plan total_dsp] \
    uram288 [dict get $post_plan total_uram] \
    mlp_kernel_dsp48e2 [dict get $post_plan kernel_dsp] \
    history2_repack_instances [dict get $post_plan history2_count] \
    generic_repack_instances [dict get $post_plan generic_repack_count] \
    raw_weight_push_loads [dict get $post_plan raw_weight_push_loads] \
    weight_data_capture_contract 32x256 \
    weight_data_capture_nets [dict get $post_plan weight_data_capture_nets] \
    weight_data_capture_loads \
        [dict get $post_plan weight_data_capture_min]/[dict get $post_plan weight_data_capture_max] \
    weight_meta_capture_contract 2x256 \
    weight_meta_capture_nets [dict get $post_plan weight_meta_capture_nets] \
    weight_meta_capture_loads \
        [dict get $post_plan weight_meta_capture_min]/[dict get $post_plan weight_meta_capture_max] \
    weight_group_capture_contract 2x7 \
    weight_group_capture_nets [dict get $post_plan weight_group_capture_nets] \
    weight_group_capture_loads \
        [dict get $post_plan weight_group_capture_min]/[dict get $post_plan weight_group_capture_max] \
    projection_weight_capture_ok \
        [dict get $post_plan projection_weight_capture_ok] \
    compute_clock_buffer_none_nets $post_compute_clock_buffer_none_count \
    compute_clock_buffer_none_ok 1 \
    projection_geometry_root $post_projection_root \
    geometry_pblock_prefix $geometry_prefix \
    canonical_pblock_count [dict get $post_audit pblock_count] \
    geometry_pblock_count [dict get $post_geometry_audit pblock_count] \
    geometry_region0_input_primitives \
        [llength [dict get $post_geometry_plan region0_input_primitives]] \
    geometry_region3_input_primitives \
        [llength [dict get $post_geometry_plan region3_input_primitives]] \
    geometry_owner_region2_weight_primitives \
        [llength [dict get $post_geometry_plan owner_region2_weight_primitives]] \
    geometry_region0_input_ok \
        [hap_projection_ooc_floorplan::region0_input_localization_ok \
            $post_geometry_plan] \
    geometry_region3_input_ok \
        [hap_projection_ooc_floorplan::region3_input_localization_ok \
            $post_geometry_plan] \
    geometry_owner_region2_weight_ok \
        [hap_projection_ooc_floorplan::owner_region2_weight_anchor_ok \
            $post_geometry_plan] \
    geometry_placement_ok [dict get $post_geometry_placement ok] \
    compact_input_frontend_instances [llength $post_compact_input] \
    down_elastic2_instances [llength $post_down_elastic] \
    mlp_local_clear_ff [dict get $post_clear total] \
    mlp_local_clear_protected_ff [dict get $post_clear protected] \
    branch0_local_clear_ff [dict get $post_clear branch0] \
    branch1_local_clear_ff [dict get $post_clear branch1] \
    branch0_local_clear_slr [dict get $post_clear branch0_slr] \
    branch1_local_clear_slr [dict get $post_clear branch1_slr] \
    mlp_local_clear_wrong_slr [dict get $post_clear wrong] \
    mlp_central_clear_ff [dict get $post_clear central] \
    mlp_central_clear_branch_endpoints \
        [dict get $post_clear central_branch_endpoints] \
    mlp_central_clear_direct_branch_state \
        [dict get $post_clear central_direct_branch_state] \
    metadata_leaf_instances [dict get $post_metadata leaves] \
    metadata_local_wr_en_ff [dict get $post_metadata wr_en] \
    metadata_local_wr_addr_ff [dict get $post_metadata wr_addr] \
    metadata_local_wr_data_ff [dict get $post_metadata wr_data] \
    metadata_local_write_protected_ff [dict get $post_metadata protected] \
    metadata_local_write_leaf_counts [dict get $post_metadata leaf_counts] \
    metadata_local_write_leaf_slr_counts \
        [dict get $post_metadata leaf_slr_counts] \
    metadata_local_write_wrong_slr [dict get $post_metadata wrong] \
    mlp_capture_leaf_instances [dict get $post_capture instances] \
    mlp_capture_leaf_lut1 [dict get $post_capture lut1] \
    mlp_capture_leaf_branch_instances \
        [dict get $post_capture branch_instances] \
    mlp_capture_leaf_branch_lut1 [dict get $post_capture branch_lut1] \
    mlp_capture_leaf_branch_slr_counts \
        [dict get $post_capture branch_slr_counts] \
    mlp_capture_leaf_wrong_slr [dict get $post_capture wrong] \
    pblock_contract_variant [dict get $post_audit contract_variant] \
    attention_row_instances 1 kv_cache_instances 1 kv_quantizer4_instances 1 \
    attention_island_target_slr [dict get $post_plan attention_island_target] \
    attention_island_dsp48e2 [dict get $post_plan attention_island_dsp] \
    attention_island_ramb36e2 [dict get $post_plan attention_island_ramb36] \
    attention_island_ramb18e2 [dict get $post_plan attention_island_ramb18] \
    attention_island_uram288 [dict get $post_plan attention_island_uram] \
    attention_island_quantizer_overlap \
        [dict get $post_plan attention_island_quantizer_overlap] \
    attention_island_row_cache_overlap \
        [dict get $post_plan attention_island_row_cache_overlap] \
    attention_island_pblock_dsp48e2 [dict get $attention_island_record dsp] \
    attention_island_pblock_ramb36e2 \
        [dict get $attention_island_record ramb36] \
    attention_island_pblock_ramb18e2 \
        [dict get $attention_island_record ramb18] \
    attention_island_pblock_uram288 [dict get $attention_island_record uram] \
    outer0_dsp48e2 [dict get $post_plan outer0_dsp] \
    outer2_dsp48e2 [dict get $post_plan outer2_dsp] \
    outer0_ramb36e2 [dict get $post_plan outer0_ramb36] \
    outer2_ramb36e2 [dict get $post_plan outer2_ramb36] \
    moved_lanes_slr0 [dict get $post_plan move0] \
    center_lanes_slr1 [dict get $post_plan center_lanes] \
    moved_lanes_slr2 [dict get $post_plan move2] \
    planned_slr0_dsp48e2 [dict get $post_plan planned_slr0_dsp] \
    planned_slr1_dsp48e2 [dict get $post_plan planned_slr1_dsp] \
    planned_slr2_dsp48e2 [dict get $post_plan planned_slr2_dsp] \
    slr0_dsp48e2 [lindex $slr_dsp 0] \
    slr1_dsp48e2 [lindex $slr_dsp 1] \
    slr2_dsp48e2 [lindex $slr_dsp 2] per_slr_dsp_limit 1900 \
    slr0_uram288 [lindex $slr_uram 0] \
    slr1_uram288 [lindex $slr_uram 1] \
    slr2_uram288 [lindex $slr_uram 2] \
    slr0_ramb36e2 [lindex $slr_ramb36 0] \
    slr1_ramb36e2 [lindex $slr_ramb36 1] \
    slr2_ramb36e2 [lindex $slr_ramb36 2] \
    unplaced_primitives $unplaced wrong_slr_primitives $wrong_total \
    branch0_wrong_slr [dict get $physical branch0_wrong] \
    branch2_wrong_slr [dict get $physical branch2_wrong] \
    attention_lane0_wrong_slr [dict get $physical lane0_wrong] \
    attention_lane2_wrong_slr [dict get $physical lane2_wrong] \
    center_dsp_wrong_slr [dict get $physical center_wrong] \
    metadata_gate0_wrong_slr [dict get $physical gate0_wrong] \
    metadata_gate2_wrong_slr [dict get $physical gate2_wrong] \
    metadata_down0_wrong_slr [dict get $physical down0_wrong] \
    metadata_down1_wrong_slr [dict get $physical down1_wrong] \
    attention_metadata_wrong_slr [dict get $physical attention_meta_wrong] \
    attention_island_wrong_slr [dict get $physical attention_island_wrong] \
    pre_place_drc_errors $pre_drc_errors \
    post_place_drc_errors $post_drc_errors \
    false_path_exception_rows $false_path_rows \
    datapath_only_exception_rows $datapath_only_rows \
    no_clock_endpoints $no_clock unconstrained_paths $unconstrained \
    no_input_delay_ports $no_input_delay no_output_delay_ports $no_output_delay \
    partial_input_delay_ports $partial_input_delay \
    partial_output_delay_ports $partial_output_delay \
    timing_coverage_ok $timing_coverage_ok cdc_critical $cdc_critical \
    clock_bufg $clock_bufg data_bufg $data_bufg \
    congestion_level5_or_higher_windows $level5 \
    congestion_level6_or_higher_windows $level6 \
    congestion_schema_header_count [dict get $congestion header_count] \
    congestion_data_rows_recognized [dict get $congestion data_rows] \
    congestion_schema_ok [dict get $congestion schema_ok] \
    post_place_wns_ns $wns post_place_whs_ns $whs \
    resource_ok $resource_ok structure_ok $structure_ok \
    placement_ok $placement_ok uram_distribution_ok $uram_distribution_ok \
    pre_place_pblock_contract_ok [dict get $pre_audit ok] \
    post_place_live_rediscovery_ok 1 \
    post_place_pblock_contract_ok [dict get $post_audit ok] \
    post_place_pblock_count $post_total_pblock_count \
    post_place_canonical_pblock_count [dict get $post_audit pblock_count] \
    post_place_geometry_pblock_count \
        [dict get $post_geometry_audit pblock_count] \
    post_place_pblock_dsp_coverage [dict get $post_audit dsp_coverage] \
    post_place_pblock_uram_coverage [dict get $post_audit uram_coverage] \
    post_place_pblock_wrong_slr [dict get $post_audit placed_wrong] \
    post_place_pblock_optimizer_extras \
        [dict get $post_audit optimizer_extra_count] \
    optimizer_extras_ok $optimizer_extras_ok fast_gate_ok $fast_gate_ok \
    policy_ok $policy_ok level5_screen_ok [expr {$level5 <= $max_level5}] \
    level6_congestion_ok [expr {$level6 == 0}] status $status]
close_design
if {$status ne "V5_PRODUCTION_PLACE_PASS"} {
    error "P10 production post-place acceptance gate failed"
}
