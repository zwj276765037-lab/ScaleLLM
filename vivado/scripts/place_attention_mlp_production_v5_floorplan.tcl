set script_dir [file dirname [file normalize [info script]]]
set root [file normalize [file join $script_dir ../..]]
set in_dcp [file normalize $::env(HAP_DCP)]
set out [file normalize $::env(HAP_PLACE_DIR)]
set input_sha [file normalize $::env(HAP_PLACE_INPUT_SHA)]
set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)
set expected_manifest_sha $::env(HAP_PLACE_INPUT_MANIFEST_SHA256)
set selector_lib [file normalize $::env(HAP_PLACE_SELECTOR_LIB)]
set fine_lib [file normalize $::env(HAP_PLACE_FINE_LIB)]
set composite_lib [file normalize $::env(HAP_PLACE_COMPOSITE_LIB)]
set expected_launcher [file normalize $::env(HAP_PLACE_LAUNCHER)]
set expected_io_audit [file normalize $::env(HAP_PLACE_IO_AUDIT)]
set preplace_output_sha [file normalize \
    $::env(HAP_PLACE_COMPOSITE21_PREPLACE_OUTPUT_SHA)]
set expected_preplace_output_sha \
    $::env(HAP_PLACE_COMPOSITE21_PREPLACE_OUTPUT_SHA256)
set expected_preplace_input_sha \
    $::env(HAP_PLACE_COMPOSITE21_PREPLACE_INPUT_SHA256)
set place_script [file normalize [info script]]
set place_directive [expr {[info exists ::env(HAP_PLACE_DIRECTIVE)] ?
    $::env(HAP_PLACE_DIRECTIVE) : "AltSpreadLogic_high"}]
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
set flow_mode [expr {[info exists ::env(HAP_PLACE_MODE)] ?
    $::env(HAP_PLACE_MODE) : "accept"}]
set clock_xdc [file normalize $::env(HAP_PLACE_CLOCK_XDC)]
file mkdir $out

proc hap_place_require_nonempty_file {path label} {
    if {![file exists $path] || ![file isfile $path] ||
        [file size $path] == 0} {
        error "Missing or empty $label: $path"
    }
}

proc hap_place_read_nonempty {path label} {
    hap_place_require_nonempty_file $path $label
    set fh [open $path r]
    set text [read $fh]
    close $fh
    return $text
}

proc hap_place_sha256 {path} {
    set digest [lindex [exec sha256sum -- $path] 0]
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "Malformed SHA256 for $path: $digest"
    }
    return $digest
}

proc hap_place_exact_line_count {text literal} {
    set count 0
    foreach line [split $text "\n"] {
        if {$line eq $literal} {incr count}
    }
    return $count
}

proc hap_place_verify_manifest {path expected_count expected_sha} {
    if {[hap_place_sha256 $path] ne $expected_sha} {
        error "V5 place input-manifest identity mismatch"
    }
    set entries [dict create]
    foreach raw [split [hap_place_read_nonempty $path \
            "place input SHA manifest"] "\n"] {
        set line [string trim $raw]
        if {$line eq ""} {continue}
        if {![regexp {^([0-9a-f]{64})[[:space:]]+\*?(.+)$} \
                $line -> expected file_name]} {
            error "Malformed V5 place input SHA row: $line"
        }
        set normalized [file normalize [string trim $file_name]]
        if {[dict exists $entries $normalized]} {
            error "Duplicate V5 place input SHA path: $normalized"
        }
        hap_place_require_nonempty_file $normalized "frozen place input"
        if {[hap_place_sha256 $normalized] ne $expected} {
            error "V5 place input SHA mismatch: $normalized"
        }
        dict set entries $normalized $expected
    }
    if {$expected_count >= 0 && [dict size $entries] != $expected_count} {
        error "V5 place input SHA cardinality mismatch: [dict size $entries]"
    }
    return $entries
}

proc hap_place_cells_of_module {module_name} {
    return [get_cells -quiet -hierarchical -filter \
        "ORIG_REF_NAME == $module_name || REF_NAME == $module_name"]
}

proc hap_place_property_is_true {object property_name} {
    set value [string tolower [get_property $property_name $object]]
    return [expr {$value eq "1" || $value eq "true" || $value eq "yes"}]
}

proc hap_place_mlp_local_clear_audit {require_placed} {
    set branches [lsort -dictionary [hap_place_cells_of_module \
        hap_mlp_shared_local_slice8x12_s44_s46]]
    if {[llength $branches] != 2} {
        error "Expected two MLP local branches, got [llength $branches]"
    }
    set total 0
    set protected 0
    set branch_counts {}
    set branch_slr_counts {}
    set all_clear_ff {}
    set wrong 0
    foreach branch $branches target {0 2} {
        set branch_name [get_property NAME $branch]
        set clear_ff [get_cells -quiet -hierarchical -filter \
            "NAME =~ ${branch_name}/clear_local_r_reg* && REF_NAME =~ FD*"]
        if {[llength $clear_ff] != 1} {
            error "MLP branch local-clear count mismatch: branch=$branch_name count=[llength $clear_ff]"
        }
        foreach cell $clear_ff {
            if {![hap_place_property_is_true $cell DONT_TOUCH]} {
                error "MLP local clear FF lost DONT_TOUCH: $cell"
            }
            incr protected
        }
        lappend branch_counts [llength $clear_ff]
        set all_clear_ff [concat $all_clear_ff $clear_ff]
        incr total [llength $clear_ff]
        if {$require_placed} {
            set audit [hap_v5_floorplan::wrong_slr_audit $clear_ff $target]
            if {[dict get $audit physical_count] != 1 ||
                [dict get $audit virtual_total] != 0 ||
                [dict get $audit direct_slr_empty] != 0 ||
                [dict get $audit is_placed_empty] != 0} {
                error "MLP local clear FF placement is unresolved: branch=$branch_name"
            }
            lappend branch_slr_counts [dict get $audit slr_counts]
            incr wrong [dict get $audit wrong]
        } else {
            lappend branch_slr_counts {0 0 0}
        }
    }
    set all_clear_ff [lsort -dictionary -unique $all_clear_ff]
    set central [get_cells -quiet -hierarchical -filter {
        NAME =~ */maintenance_soft_clear_pulse_r_reg && REF_NAME =~ FD*}]
    if {[llength $central] != 1} {
        error "Expected one central MLP maintenance clear FF, got [llength $central]"
    }
    set q [get_pins -quiet -of_objects $central -filter \
        {REF_PIN_NAME == Q}]
    if {[llength $q] != 1} {
        error "Central MLP maintenance clear Q-pin count mismatch"
    }
    set endpoint_cells [lsort -dictionary -unique [get_cells -quiet \
        -of_objects [all_fanout -flat -endpoints_only -from $q]]]
    set branch_endpoints {}
    foreach branch $branches {
        set branch_name [get_property NAME $branch]
        foreach cell $endpoint_cells {
            if {[string match "${branch_name}/*" \
                    [get_property NAME $cell]]} {
                lappend branch_endpoints $cell
            }
        }
    }
    set branch_endpoints [lsort -dictionary -unique $branch_endpoints]
    if {[llength $branch_endpoints] != 2 ||
        $branch_endpoints ne $all_clear_ff} {
        error "Central MLP clear bypasses local boundary: endpoints=$branch_endpoints expected=$all_clear_ff"
    }
    return [dict create total $total protected $protected \
        branch0 [lindex $branch_counts 0] branch1 [lindex $branch_counts 1] \
        branch0_slr [lindex $branch_slr_counts 0] \
        branch1_slr [lindex $branch_slr_counts 1] wrong $wrong \
        central [llength $central] \
        central_branch_endpoints [llength $branch_endpoints] \
        central_direct_branch_state 0]
}

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "V5 production placement requires HAP_JOBS=32: $jobs"
}
if {$flow_mode ni {screen accept}} {
    error "HAP_PLACE_MODE must be screen or accept: $flow_mode"
}
set_param general.maxThreads $jobs
if {[llength [get_designs -quiet]] != 0} {
    error "V5 placement requires a fresh Vivado process"
}
if {![regexp {^[0-9a-f]{64}$} $expected_dcp_sha] ||
    ![regexp {^[0-9a-f]{64}$} $expected_manifest_sha]} {
    error "V5 placement received a malformed expected SHA256"
}
if {![file exists $in_dcp] || ![file isfile $in_dcp] ||
    [file size $in_dcp] == 0} {
    error "Missing or empty V5 post-opt DCP: $in_dcp"
}
set frozen_inputs [hap_place_verify_manifest $input_sha 9 \
    $expected_manifest_sha]
foreach required [list $in_dcp $selector_lib $fine_lib $composite_lib $place_script \
        $expected_launcher $clock_xdc $expected_io_audit \
        $preplace_output_sha] {
    if {![dict exists $frozen_inputs $required]} {
        error "Required V5 place input absent from SHA manifest: $required"
    }
}
if {![regexp {^[0-9a-f]{64}$} $expected_preplace_output_sha] ||
    ![regexp {^[0-9a-f]{64}$} $expected_preplace_input_sha]} {
    error "V5 placement received a malformed pre-place manifest SHA256"
}
set preplace_outputs [hap_place_verify_manifest $preplace_output_sha -1 \
    $expected_preplace_output_sha]
set preplace_dir [file dirname $preplace_output_sha]
set preplace_input_sha \
    [file normalize [file join $preplace_dir INPUT_SHA256SUMS]]
set preplace_summary [file normalize [file join $preplace_dir summary.txt]]
set preplace_launcher_status \
    [file normalize [file join $preplace_dir launcher_status.txt]]
foreach required [list $preplace_input_sha $preplace_summary \
        $preplace_launcher_status] {
    if {![dict exists $preplace_outputs $required]} {
        error "Required Composite21 pre-place evidence is absent from its output manifest: $required"
    }
}
if {[dict get $preplace_outputs $preplace_input_sha] ne
    $expected_preplace_input_sha} {
    error "Composite21 pre-place input-manifest identity disagrees with its output manifest"
}
set preplace_inputs [hap_place_verify_manifest $preplace_input_sha 7 \
    $expected_preplace_input_sha]
foreach required [list $in_dcp $selector_lib $fine_lib $composite_lib] {
    if {![dict exists $preplace_inputs $required]} {
        error "Composite21 pre-place input lineage is missing live placement input: $required"
    }
}
set preplace_summary_text [hap_place_read_nonempty $preplace_summary \
    "Composite21 pre-place summary"]
set preplace_launcher_text [hap_place_read_nonempty \
    $preplace_launcher_status "Composite21 pre-place launcher status"]
foreach literal {status=V5_COMPOSITE21_PRE_PLACE_AUDIT_PASS \
        stage=V5_PRODUCTION_COMPOSITE21_PRE_PLACE_AUDIT \
        contract_variant=P9_COHORT16_MLP_CENTRAL_X2X4_21 \
        pblock_count=21 \
        central_anchor_range=CLOCKREGION_X2Y5:CLOCKREGION_X4Y9 \
        central_island_count=197091 central_island_delta=0 \
        central_island_dsp=80 mlp_remaining_count=88785 \
        mlp_remaining_delta=0 center_dsp_remaining_count=5 \
        center_dsp_remaining_dsp=5 central_partition_ok=1 \
        member_overlap=0 optimizer_extra_count=0 pblock_dsp_coverage=5453 \
        pblock_uram_coverage=752 pblock_wrong_slr=0 \
        soft_pblock_count=0 soft_outside=0 \
        probe_verified=1 \
        pre_place_drc_errors=0 checkpoint_written=0 \
        implementation_commands_run=0} {
    if {[hap_place_exact_line_count $preplace_summary_text $literal] != 1} {
        error "Composite21 pre-place summary gate failed: $literal"
    }
}
foreach literal {status=PASS final_exit_code=0 vivado_exit_code=0 \
        probe_output_recheck_exit_code=0 audit_gate_exit_code=0 \
        checkpoint_written=0 \
        implementation_commands_run=0} {
    if {[hap_place_exact_line_count $preplace_launcher_text $literal] != 1} {
        error "Composite21 pre-place launcher gate failed: $literal"
    }
}
set actual_dcp_sha [hap_place_sha256 $in_dcp]
if {$actual_dcp_sha ne $expected_dcp_sha} {
    error "V5 placement DCP identity mismatch"
}

# Fail closed before reading constraints.  Genuine asynchronous clock-domain
# grouping remains legal; false paths, datapath-only delays and frequency
# relaxation do not.
set xdc_fh [open $clock_xdc r]
set xdc_text [read $xdc_fh]
close $xdc_fh
set xdc_code ""
foreach line [split $xdc_text "\n"] {
    if {![regexp {^[[:space:]]*#} $line]} {append xdc_code $line "\n"}
}
set forbidden_false_path [join {set false path} _]
set forbidden_datapath "-[join {datapath only} _]"
if {[regexp -nocase -- \
    [format {%s|%s} $forbidden_false_path $forbidden_datapath] \
    $xdc_code]} {
    error "V5 placement XDC contains a forbidden timing waiver"
}
if {[llength [regexp -all -inline \
    {create_clock[[:space:]]} $xdc_code]] != 3} {
    error "V5 placement requires exactly three create_clock commands"
}
proc require_regex_count {label text pattern expected} {
    set actual [llength [regexp -all -inline -- $pattern $text]]
    if {$actual != $expected} {
        error "V5 XDC contract mismatch: label=$label expected=$expected actual=$actual"
    }
}
require_regex_count input_delay_commands $xdc_code \
    {set_input_delay[[:space:]]} 6
require_regex_count output_delay_commands $xdc_code \
    {set_output_delay[[:space:]]} 6
foreach {command clock sense value} {
    set_input_delay core_clk max 1.000
    set_input_delay core_clk min 0.000
    set_output_delay core_clk max 1.000
    set_output_delay core_clk min 0.000
    set_input_delay ddr0_clk max 0.800
    set_input_delay ddr0_clk min 0.000
    set_output_delay ddr0_clk max 0.800
    set_output_delay ddr0_clk min 0.000
    set_input_delay ddr1_clk max 0.800
    set_input_delay ddr1_clk min 0.000
    set_output_delay ddr1_clk max 0.800
    set_output_delay ddr1_clk min 0.000
} {
    set pattern [format \
        {%s[[:space:]]+-clock[[:space:]]+%s[[:space:]]+-%s[[:space:]]+%s} \
        $command $clock $sense $value]
    require_regex_count ${command}_${clock}_${sense} $xdc_code $pattern 1
}

# The asynchronous grouping is the only legal CDC isolation policy.  Verify
# its exact one-command/three-domain shape before read_xdc.
require_regex_count asynchronous_clock_group_commands $xdc_code \
    {set_clock_groups[[:space:]]+-asynchronous} 1
require_regex_count asynchronous_clock_group_members $xdc_code \
    {-group[[:space:]]+\[get_clocks} 3

source $selector_lib
source $fine_lib
source $composite_lib
open_checkpoint $in_dcp
read_xdc $clock_xdc
source $expected_io_audit

foreach {name period} {core_clk 10.000 ddr0_clk 3.333 ddr1_clk 3.333} {
    set clocks [get_clocks -quiet $name]
    if {[llength $clocks] != 1 ||
        abs([get_property PERIOD $clocks] - $period) > 0.001} {
        error "V5 placement clock contract failed: $name"
    }
}

set contract_variant P9_COHORT16_MLP_CENTRAL_X2X4_21
set base_contract_variant P2_COHORT16_COL2_12_2
set plan [hap_v5_floorplan::discover $base_contract_variant]
set fine_plan [hap_v5_fine19::discover $plan]
set composite_plan [hap_v5_composite21::discover $plan $fine_plan]
if {[dict get $composite_plan contract_variant] ne $contract_variant} {
    error "V5 Composite21 placement contract variant mismatch"
}
set compact_input_frontend [hap_place_cells_of_module \
    hap_mlp_input_frontend16_compact_cache]
set down_elastic2 [hap_place_cells_of_module \
    hap_mlp_down_branch_elastic2_s24_v6]
set pre_mlp_local_clear [hap_place_mlp_local_clear_audit 0]
if {[llength $compact_input_frontend] != 1 ||
    [llength $down_elastic2] != 2 ||
    [dict get $pre_mlp_local_clear total] != 2 ||
    [dict get $pre_mlp_local_clear protected] != 2 ||
    [dict get $pre_mlp_local_clear central] != 1 ||
    [dict get $pre_mlp_local_clear central_branch_endpoints] != 2 ||
    [dict get $pre_mlp_local_clear central_direct_branch_state] != 0} {
    error "V5 pre-place compact/down-elastic identity mismatch"
}
hap_v5_floorplan::write_discovery $plan \
    [file join $out selectors_base_pre_place.txt] \
    V5_FLOORPLAN_SELECTORS_PASS
hap_v5_fine19::write_discovery $fine_plan \
    [file join $out selectors_fine19_pre_place.txt] \
    V5_FINE19_FLOORPLAN_SELECTORS_PASS
hap_v5_composite21::write_discovery $composite_plan \
    [file join $out selectors_pre_place.txt] \
    V5_COMPOSITE21_FLOORPLAN_SELECTORS_PASS

# Apply the same exact 21-hard-pblock contract qualified by the upstream read-only
# probe and in-memory pre-place DRC.  The production run does not reconstruct a
# second, loosely equivalent floorplan.
hap_v5_composite21::apply $plan $fine_plan $composite_plan

# Audit the just-created constraints before placement. This remains a strict
# pre-place failure: every pblock must be nonempty and hard, have its exact
# single-SLR range and live primitive membership, and
# cover every DSP/URAM exactly once.
set pre_pblock_audit [hap_v5_composite21::audit \
    $plan $fine_plan $composite_plan 0]
hap_v5_composite21::write_audit $pre_pblock_audit \
    [file join $out pblocks_pre_place.txt] \
    V5_COMPOSITE21_PBLOCK_PRE_PLACE_PASS

report_drc -file [file join $out drc_pre_place.rpt]
set pre_drc_errors [llength [get_drc_violations -quiet -filter \
    {SEVERITY == Error}]]
if {$pre_drc_errors != 0} {
    error "V5 pre-place DRC has $pre_drc_errors errors"
}

place_design -directive $place_directive

# place_design may rewrite or replicate the physical netlist and invalidate
# Tcl object handles captured in $plan.  Rebuild all hierarchy-descendant
# collections from the live post-place design before any wrong-SLR audit.
set post_rediscovery_rc [catch {
    set post_plan [hap_v5_floorplan::discover $base_contract_variant]
    set post_fine_plan [hap_v5_fine19::discover $post_plan 1]
    set fine19_post_optimizer_extras \
        [dict get $post_fine_plan optimizer_extra_count]
    set post_composite_plan \
        [hap_v5_composite21::discover $post_plan $post_fine_plan 1]
    set composite21_post_fine_delta \
        [dict get $post_composite_plan fine_member_delta]
    set composite21_post_mlp_delta \
        [dict get $post_composite_plan mlp_residual_delta]
    set composite21_post_central_island_delta \
        [dict get $post_composite_plan central_island_delta]
    set composite21_post_mlp_remaining_delta \
        [dict get $post_composite_plan mlp_remaining_delta]
    set composite21_post_central_partition_ok \
        [dict get $post_composite_plan central_partition_ok]
    set composite21_post_attention_delta \
        [dict get $post_composite_plan attention_direct_delta]
    set post_compact_input_frontend [hap_place_cells_of_module \
        hap_mlp_input_frontend16_compact_cache]
    set post_down_elastic2 [hap_place_cells_of_module \
        hap_mlp_down_branch_elastic2_s24_v6]
    set post_mlp_local_clear [hap_place_mlp_local_clear_audit 1]
    if {[llength $post_compact_input_frontend] != 1 ||
        [llength $post_down_elastic2] != 2 ||
        [dict get $post_mlp_local_clear total] != 2 ||
        [dict get $post_mlp_local_clear protected] != 2 ||
        [dict get $post_mlp_local_clear branch0] != 1 ||
        [dict get $post_mlp_local_clear branch1] != 1 ||
        [dict get $post_mlp_local_clear branch0_slr] ne {1 0 0} ||
        [dict get $post_mlp_local_clear branch1_slr] ne {0 0 1} ||
        [dict get $post_mlp_local_clear wrong] != 0 ||
        [dict get $post_mlp_local_clear central] != 1 ||
        [dict get $post_mlp_local_clear central_branch_endpoints] != 2 ||
        [dict get $post_mlp_local_clear central_direct_branch_state] != 0} {
        error "V5 post-place compact/down-elastic identity mismatch"
    }
    hap_v5_floorplan::write_discovery $post_plan \
        [file join $out selectors_base_post_place.txt] \
        V5_POST_PLACE_LIVE_SELECTORS_PASS
    hap_v5_fine19::write_discovery $post_fine_plan \
        [file join $out selectors_fine19_post_place.txt] \
        V5_FINE19_POST_PLACE_LIVE_SELECTORS_PASS
    hap_v5_composite21::write_discovery $post_composite_plan \
        [file join $out selectors_post_place.txt] \
        V5_COMPOSITE21_POST_PLACE_LIVE_SELECTORS_PASS
    set post_pblock_audit [hap_v5_composite21::audit \
        $post_plan $post_fine_plan $post_composite_plan 1]
    hap_v5_composite21::write_audit $post_pblock_audit \
        [file join $out pblocks_post_place.txt] \
        V5_COMPOSITE21_PBLOCK_POST_PLACE_PASS
    set physical_metrics \
        [hap_v5_composite21::physical_metrics $post_pblock_audit]
    set attention_direct_audit \
        [hap_v5_floorplan::physical_slr_audit_for_cells \
            [dict get $post_composite_plan attention_direct_primitives]]
    set attention_direct_slr_counts \
        [dict get $attention_direct_audit slr_counts]
    set attention_direct_placement_ok [expr {
        [dict get $attention_direct_audit total] ==
            [dict get $post_composite_plan attention_direct_count] &&
        [dict get $attention_direct_audit direct_slr_empty] == 0}]
    set attention_island_record [dict get $post_pblock_audit records \
        pb_v5_attention_row_kv_cache_slr0]
    dict set attention_island_record ramb36 \
        [dict get $post_plan attention_island_ramb36]
    dict set attention_island_record ramb18 \
        [dict get $post_plan attention_island_ramb18]
} post_rediscovery_error]
if {$post_rediscovery_rc != 0} {
    set diagnostic_dcp [file join $out post_place_diagnostic_only.dcp]
    set diagnostic_error ""
    set diagnostic_checkpoint_written [expr {
        ![catch {write_checkpoint -force $diagnostic_dcp} diagnostic_error]}]
    set summary_error [string map [list "\r" " " "\n" " "] \
        $post_rediscovery_error]
    set summary_diagnostic_error [string map [list "\r" " " "\n" " "] \
        $diagnostic_error]
    set fp [open [file join $out summary.txt] w]
    foreach {key value} [list \
        tool [version -short] flow_mode $flow_mode \
        failure_stage post_place_live_rediscovery \
        acceptance_evidence 0 route_eligible 0 checkpoint_written 0 \
        diagnostic_checkpoint_written $diagnostic_checkpoint_written \
        diagnostic_checkpoint $diagnostic_dcp \
        diagnostic_checkpoint_error $summary_diagnostic_error \
        place_design_completed 1 post_rediscovery_error $summary_error \
        input_dcp $in_dcp input_dcp_sha256 $actual_dcp_sha \
        input_manifest_sha256 [hap_place_sha256 $input_sha] \
        input_manifest_entries 9 provenance_verified 1 \
        composite21_pre_place_manifest $preplace_output_sha \
        composite21_pre_place_manifest_sha256 $expected_preplace_output_sha \
        composite21_pre_place_input_manifest_sha256 \
            $expected_preplace_input_sha \
        composite21_pre_place_verified 1 place_directive $place_directive \
        jobs $jobs status FAIL] {
        puts $fp "$key=$value"
    }
    close $fp
    error "V5 post-place live rediscovery failed: $post_rediscovery_error"
}

# Run the inexpensive physical gate before any checkpoint, timing, CDC or full
# post-place DRC work.  In accept mode a losing candidate therefore exits at
# the same boundary as screen mode, while a winner continues in this exact
# placed design state and is not placed a second time.
report_design_analysis -congestion -file \
    [file join $out congestion_post_place.rpt]

set unplaced [dict get $physical_metrics unplaced]
set slr_dsp [dict get $physical_metrics slr_dsp]
set slr_uram [dict get $physical_metrics slr_uram]
set slr_ramb36 [dict get $physical_metrics slr_ramb36]

set clock_bufg 0
set data_bufg 0
foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}] {
    set outputs [get_pins -quiet -of_objects $cell -filter \
        {DIRECTION == OUT}]
    if {[llength [get_clocks -quiet -of_objects $outputs]] != 0} {
        incr clock_bufg
    } else {
        incr data_bufg
    }
}

set branch0_wrong [dict get $physical_metrics branch0_wrong]
set branch2_wrong [dict get $physical_metrics branch2_wrong]
set lane0_wrong [dict get $physical_metrics lane0_wrong]
set lane2_wrong [dict get $physical_metrics lane2_wrong]
set center_dsp_wrong [dict get $physical_metrics center_wrong]
set gate0_wrong [dict get $physical_metrics gate0_wrong]
set gate2_wrong [dict get $physical_metrics gate2_wrong]
set down0_wrong [dict get $physical_metrics down0_wrong]
set down1_wrong [dict get $physical_metrics down1_wrong]
set attention_meta_wrong [dict get $physical_metrics attention_meta_wrong]
set attention_island_wrong \
    [dict get $physical_metrics attention_island_wrong]
set composite21_additional_wrong \
    [dict get $physical_metrics additional_wrong]
set p9_central_island_wrong \
    [dict get $physical_metrics central_island_wrong]
set p9_center_dsp_remaining_wrong \
    [dict get $physical_metrics center_dsp_remaining_wrong]
set p9_mlp_remaining_wrong \
    [dict get $physical_metrics mlp_remaining_wrong]
set wrong_total [dict get $physical_metrics wrong_total]

set congestion_path [file join $out congestion_post_place.rpt]
set congestion_fh [open $congestion_path r]
set congestion_text [read $congestion_fh]
close $congestion_fh
set congestion_schema_header_count 0
set congestion_data_row_count 0
set congestion_level5_count 0
set congestion_level6_count 0
foreach line [split $congestion_text "\n"] {
    if {[regexp {^[[:space:]]*\|[[:space:]]*Direction[[:space:]]*\|[[:space:]]*Type[[:space:]]*\|[[:space:]]*Level[[:space:]]*\|[[:space:]]*Window[[:space:]]*\|} \
            $line]} {
        incr congestion_schema_header_count
        continue
    }
    if {![regexp {^[[:space:]]*\|[[:space:]]*(North|South|East|West)[[:space:]]*\|[[:space:]]*(Global|Long|Short)[[:space:]]*\|[[:space:]]*([0-9]+)[[:space:]]*\|[[:space:]]*\([^|]+\)[[:space:]]*\|} \
            $line -> direction type level]} {
        continue
    }
    incr congestion_data_row_count
    if {$level >= 5} {incr congestion_level5_count}
    if {$level >= 6} {incr congestion_level6_count}
}
set congestion_clean_marker [expr {
    [string first "No congestion windows are found above level 5" \
        $congestion_text] >= 0 ||
    [string first "No effective congestion windows are found above level 5" \
        $congestion_text] >= 0}]
set congestion_schema_ok [expr {
    $congestion_schema_header_count == 1 &&
    ($congestion_data_row_count >= 1 || $congestion_clean_marker)}]
if {!$congestion_schema_ok} {
    error "V5 post-place fast-gate congestion report is unrecognized"
}
set no_level6 [expr {$congestion_level6_count == 0}]
set level5_screen_ok [expr {$congestion_level5_count <= 1}]

set resource_ok [expr {
    [dict get $post_plan total_dsp] <= 5500 &&
    [dict get $post_plan total_uram] == 752 &&
    [dict get $post_plan kernel_dsp] == 3072 &&
    [dict get $post_plan history2_count] == 2 &&
    [dict get $post_plan generic_repack_count] == 0 &&
    [dict get $post_plan projection_weight_capture_ok] == 1 &&
    [llength $post_compact_input_frontend] == 1 &&
    [llength $post_down_elastic2] == 2 &&
    [dict get $post_mlp_local_clear total] == 2 &&
    [dict get $post_mlp_local_clear protected] == 2 &&
    [dict get $post_mlp_local_clear central] == 1 &&
    [dict get $post_mlp_local_clear central_branch_endpoints] == 2 &&
    [dict get $post_mlp_local_clear central_direct_branch_state] == 0
}]
set uram_distribution_ok [expr {
    [lindex $slr_uram 0] == 224 &&
    [lindex $slr_uram 1] == 224 &&
    [lindex $slr_uram 2] == 304
}]
set placement_ok [expr {
    [hap_v5_composite21::physical_ok $physical_metrics] &&
    [dict get $post_pblock_audit ok] &&
    [dict get $pre_pblock_audit pblock_count] == 21 &&
    [dict get $post_pblock_audit pblock_count] == 21 &&
    [dict get $post_pblock_audit placed_wrong] == 0 &&
    $composite21_post_central_partition_ok == 1 &&
    $attention_direct_placement_ok &&
    [dict get $post_mlp_local_clear branch0_slr] eq {1 0 0} &&
    [dict get $post_mlp_local_clear branch1_slr] eq {0 0 1} &&
    [dict get $post_mlp_local_clear wrong] == 0 &&
    $uram_distribution_ok}]
set fast_policy_ok [expr {$pre_drc_errors == 0 && $data_bufg == 0}]
set fine19_optimizer_extras_ok [expr {
    $fine19_post_optimizer_extras >= 0 &&
    $fine19_post_optimizer_extras <= 4096}]
set composite21_selector_deltas_ok [expr {
    abs($composite21_post_fine_delta) <= 65536 &&
    abs($composite21_post_mlp_delta) <= 65536 &&
    abs($composite21_post_central_island_delta) <= 65536 &&
    abs($composite21_post_mlp_remaining_delta) <= 65536 &&
    abs($composite21_post_attention_delta) <= 65536}]
set composite21_pblock_optimizer_extras \
    [dict get $post_pblock_audit optimizer_extra_count]
set composite21_pblock_optimizer_extras_ok [expr {
    $composite21_pblock_optimizer_extras >= 0 &&
    $composite21_pblock_optimizer_extras <= 4096}]
set fast_gate_ok [expr {$resource_ok && $placement_ok && $fast_policy_ok &&
    $fine19_optimizer_extras_ok && $composite21_selector_deltas_ok &&
    $composite21_pblock_optimizer_extras_ok &&
    $no_level6 && $level5_screen_ok}]

if {$flow_mode eq "screen"} {
    set screen_policy_ok $fast_policy_ok
    set status [expr {$fast_gate_ok ?
        "V5_PRODUCTION_PLACE_SCREEN_PASS" : "FAIL"}]

    set fp [open [file join $out summary.txt] w]
    foreach {key value} [list \
        tool [version -short] part [dict get $post_plan part] \
        top [dict get $post_plan top] flow_mode $flow_mode \
        acceptance_evidence 0 route_eligible 0 checkpoint_written 0 \
        input_dcp $in_dcp input_dcp_sha256 $actual_dcp_sha \
        input_manifest_sha256 [hap_place_sha256 $input_sha] \
        input_manifest_entries 9 provenance_verified 1 \
        composite21_pre_place_manifest $preplace_output_sha \
        composite21_pre_place_manifest_sha256 $expected_preplace_output_sha \
        composite21_pre_place_input_manifest_sha256 \
            $expected_preplace_input_sha \
        composite21_pre_place_verified 1 \
        composite21_pre_place_central_anchor_range \
            [dict get $composite_plan central_anchor_range] \
        composite21_pre_place_central_island_count \
            [dict get $composite_plan central_island_count] \
        composite21_pre_place_central_island_dsp \
            [dict get $composite_plan central_island_dsp] \
        composite21_pre_place_mlp_remaining_count \
            [dict get $composite_plan mlp_remaining_count] \
        composite21_pre_place_center_dsp_remaining \
            [dict get $composite_plan center_dsp_remaining_dsp] \
        composite21_pre_place_central_partition_ok \
            [dict get $composite_plan central_partition_ok] \
        fine19_post_place_optimizer_extra_count \
            $fine19_post_optimizer_extras \
        fine19_post_place_optimizer_extras_ok \
            $fine19_optimizer_extras_ok \
        composite21_post_place_fine_member_delta \
            $composite21_post_fine_delta \
        composite21_post_place_mlp_residual_delta \
            $composite21_post_mlp_delta \
        composite21_post_place_central_anchor_range \
            [dict get $post_composite_plan central_anchor_range] \
        composite21_post_place_central_island_count \
            [dict get $post_composite_plan central_island_count] \
        composite21_post_place_central_island_delta \
            $composite21_post_central_island_delta \
        composite21_post_place_central_island_dsp \
            [dict get $post_composite_plan central_island_dsp] \
        composite21_post_place_mlp_remaining_count \
            [dict get $post_composite_plan mlp_remaining_count] \
        composite21_post_place_mlp_remaining_delta \
            $composite21_post_mlp_remaining_delta \
        composite21_post_place_center_dsp_remaining \
            [dict get $post_composite_plan center_dsp_remaining_dsp] \
        composite21_post_place_central_partition_ok \
            $composite21_post_central_partition_ok \
        composite21_post_place_attention_direct_delta \
            $composite21_post_attention_delta \
        composite21_post_place_selector_deltas_ok \
            $composite21_selector_deltas_ok \
        composite21_post_place_pblock_optimizer_extras \
            $composite21_pblock_optimizer_extras \
        composite21_post_place_pblock_optimizer_extras_ok \
            $composite21_pblock_optimizer_extras_ok \
        place_directive $place_directive jobs $jobs core_clock_mhz 100 \
        ddr0_clock_mhz 300 ddr1_clock_mhz 300 \
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
        compact_input_frontend_instances \
            [llength $post_compact_input_frontend] \
        down_elastic2_instances [llength $post_down_elastic2] \
        mlp_local_clear_ff [dict get $post_mlp_local_clear total] \
        mlp_local_clear_protected_ff \
            [dict get $post_mlp_local_clear protected] \
        branch0_local_clear_ff [dict get $post_mlp_local_clear branch0] \
        branch1_local_clear_ff [dict get $post_mlp_local_clear branch1] \
        branch0_local_clear_slr \
            [dict get $post_mlp_local_clear branch0_slr] \
        branch1_local_clear_slr \
            [dict get $post_mlp_local_clear branch1_slr] \
        mlp_local_clear_wrong_slr [dict get $post_mlp_local_clear wrong] \
        mlp_central_clear_ff [dict get $post_mlp_local_clear central] \
        mlp_central_clear_branch_endpoints \
            [dict get $post_mlp_local_clear central_branch_endpoints] \
        mlp_central_clear_direct_branch_state \
            [dict get $post_mlp_local_clear central_direct_branch_state] \
        pblock_contract_variant \
            [dict get $post_pblock_audit contract_variant] \
        projection_exact_cover [dict get $post_fine_plan projection_exact_cover] \
        region1_exact_cover [dict get $post_fine_plan region1_exact_cover] \
        owner_exact_cover [dict get $post_fine_plan owner_exact_cover] \
        weight_owner_residency_ok \
            [dict get $post_fine_plan weight_owner_residency_ok] \
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
        branch0_wrong_slr $branch0_wrong branch2_wrong_slr $branch2_wrong \
        attention_lane0_wrong_slr $lane0_wrong \
        attention_lane2_wrong_slr $lane2_wrong \
        center_dsp_wrong_slr $center_dsp_wrong \
        metadata_gate0_wrong_slr $gate0_wrong \
        metadata_gate2_wrong_slr $gate2_wrong \
        metadata_down0_wrong_slr $down0_wrong \
        metadata_down1_wrong_slr $down1_wrong \
        attention_metadata_wrong_slr $attention_meta_wrong \
        attention_island_wrong_slr $attention_island_wrong \
        composite21_additional_wrong_slr $composite21_additional_wrong \
        p9_central_island_wrong_slr $p9_central_island_wrong \
        p9_center_dsp_remaining_wrong_slr $p9_center_dsp_remaining_wrong \
        p9_mlp_remaining_wrong_slr $p9_mlp_remaining_wrong \
        attention_direct_unconstrained 1 \
        attention_direct_slr0_primitives \
            [lindex $attention_direct_slr_counts 0] \
        attention_direct_slr1_primitives \
            [lindex $attention_direct_slr_counts 1] \
        attention_direct_slr2_primitives \
            [lindex $attention_direct_slr_counts 2] \
        attention_direct_physical_primitives \
            [dict get $attention_direct_audit physical_count] \
        attention_direct_virtual_primitives \
            [dict get $attention_direct_audit virtual_total] \
        attention_direct_unresolved_primitives \
            [dict get $attention_direct_audit direct_slr_empty] \
        attention_direct_is_placed_empty \
            [dict get $attention_direct_audit is_placed_empty] \
        attention_direct_placement_ok $attention_direct_placement_ok \
        pre_place_drc_errors $pre_drc_errors post_place_drc_run 0 \
        timing_run 0 cdc_run 0 exception_coverage_run 0 \
        clock_bufg $clock_bufg data_bufg $data_bufg \
        congestion_level5_or_higher_windows $congestion_level5_count \
        congestion_level6_or_higher_windows $congestion_level6_count \
        congestion_schema_header_count $congestion_schema_header_count \
        congestion_data_rows_recognized $congestion_data_row_count \
        congestion_schema_ok $congestion_schema_ok \
        resource_ok $resource_ok placement_ok $placement_ok \
        uram_distribution_ok $uram_distribution_ok \
        pre_place_pblock_contract_ok [dict get $pre_pblock_audit ok] \
        post_place_live_rediscovery_ok 1 \
        post_place_pblock_contract_ok [dict get $post_pblock_audit ok] \
        post_place_pblock_count [dict get $post_pblock_audit pblock_count] \
        post_place_pblock_dsp_coverage \
            [dict get $post_pblock_audit dsp_coverage] \
        post_place_pblock_uram_coverage \
            [dict get $post_pblock_audit uram_coverage] \
        post_place_pblock_wrong_slr \
            [dict get $post_pblock_audit placed_wrong] \
        post_place_pblock_overlap \
            [dict get $post_pblock_audit member_overlap] \
        post_place_pblock_optimizer_extras \
            [dict get $post_pblock_audit optimizer_extra_count] \
        screen_policy_ok $screen_policy_ok \
        fast_gate_ok $fast_gate_ok level5_screen_ok $level5_screen_ok \
        level6_congestion_ok $no_level6 \
        status $status] {
        puts $fp "$key=$value"
    }
    close $fp

    puts "V5_PRODUCTION_PLACE_SCREEN DSP=$slr_dsp URAM=$slr_uram UNPLACED=$unplaced WRONG_SLR=$wrong_total DATA_BUFG=$data_bufg LEVEL5=$congestion_level5_count LEVEL6=$congestion_level6_count STATUS=$status"
    if {$status ne "V5_PRODUCTION_PLACE_SCREEN_PASS"} {
        error "V5 production placement screen failed"
    }
}

if {$flow_mode eq "accept"} {
if {!$fast_gate_ok} {
    set fp [open [file join $out summary.txt] w]
    foreach {key value} [list \
        tool [version -short] part [dict get $post_plan part] \
        top [dict get $post_plan top] flow_mode $flow_mode \
        failure_stage post_place_fast_gate acceptance_evidence 0 \
        route_eligible 0 checkpoint_written 0 timing_run 0 cdc_run 0 \
        post_place_drc_run 0 exception_coverage_run 0 \
        input_dcp $in_dcp input_dcp_sha256 $actual_dcp_sha \
        input_manifest_sha256 [hap_place_sha256 $input_sha] \
        input_manifest_entries 9 provenance_verified 1 \
        composite21_pre_place_manifest $preplace_output_sha \
        composite21_pre_place_manifest_sha256 $expected_preplace_output_sha \
        composite21_pre_place_input_manifest_sha256 \
            $expected_preplace_input_sha \
        composite21_pre_place_verified 1 \
        composite21_pre_place_central_anchor_range \
            [dict get $composite_plan central_anchor_range] \
        composite21_pre_place_central_island_count \
            [dict get $composite_plan central_island_count] \
        composite21_pre_place_central_island_dsp \
            [dict get $composite_plan central_island_dsp] \
        composite21_pre_place_mlp_remaining_count \
            [dict get $composite_plan mlp_remaining_count] \
        composite21_pre_place_center_dsp_remaining \
            [dict get $composite_plan center_dsp_remaining_dsp] \
        composite21_pre_place_central_partition_ok \
            [dict get $composite_plan central_partition_ok] \
        fine19_post_place_optimizer_extra_count \
            $fine19_post_optimizer_extras \
        fine19_post_place_optimizer_extras_ok \
            $fine19_optimizer_extras_ok \
        composite21_post_place_fine_member_delta \
            $composite21_post_fine_delta \
        composite21_post_place_mlp_residual_delta \
            $composite21_post_mlp_delta \
        composite21_post_place_central_anchor_range \
            [dict get $post_composite_plan central_anchor_range] \
        composite21_post_place_central_island_count \
            [dict get $post_composite_plan central_island_count] \
        composite21_post_place_central_island_delta \
            $composite21_post_central_island_delta \
        composite21_post_place_central_island_dsp \
            [dict get $post_composite_plan central_island_dsp] \
        composite21_post_place_mlp_remaining_count \
            [dict get $post_composite_plan mlp_remaining_count] \
        composite21_post_place_mlp_remaining_delta \
            $composite21_post_mlp_remaining_delta \
        composite21_post_place_center_dsp_remaining \
            [dict get $post_composite_plan center_dsp_remaining_dsp] \
        composite21_post_place_central_partition_ok \
            $composite21_post_central_partition_ok \
        composite21_post_place_attention_direct_delta \
            $composite21_post_attention_delta \
        composite21_post_place_selector_deltas_ok \
            $composite21_selector_deltas_ok \
        composite21_post_place_pblock_optimizer_extras \
            $composite21_pblock_optimizer_extras \
        composite21_post_place_pblock_optimizer_extras_ok \
            $composite21_pblock_optimizer_extras_ok \
        place_directive $place_directive jobs $jobs \
        dsp48e2 [dict get $post_plan total_dsp] \
        uram288 [dict get $post_plan total_uram] \
        mlp_kernel_dsp48e2 [dict get $post_plan kernel_dsp] \
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
        slr0_dsp48e2 [lindex $slr_dsp 0] \
        slr1_dsp48e2 [lindex $slr_dsp 1] \
        slr2_dsp48e2 [lindex $slr_dsp 2] \
        slr0_uram288 [lindex $slr_uram 0] \
        slr1_uram288 [lindex $slr_uram 1] \
        slr2_uram288 [lindex $slr_uram 2] \
        unplaced_primitives $unplaced wrong_slr_primitives $wrong_total \
        composite21_additional_wrong_slr $composite21_additional_wrong \
        p9_central_island_wrong_slr $p9_central_island_wrong \
        p9_center_dsp_remaining_wrong_slr $p9_center_dsp_remaining_wrong \
        p9_mlp_remaining_wrong_slr $p9_mlp_remaining_wrong \
        attention_direct_unconstrained 1 \
        attention_direct_slr0_primitives \
            [lindex $attention_direct_slr_counts 0] \
        attention_direct_slr1_primitives \
            [lindex $attention_direct_slr_counts 1] \
        attention_direct_slr2_primitives \
            [lindex $attention_direct_slr_counts 2] \
        attention_direct_physical_primitives \
            [dict get $attention_direct_audit physical_count] \
        attention_direct_virtual_primitives \
            [dict get $attention_direct_audit virtual_total] \
        attention_direct_unresolved_primitives \
            [dict get $attention_direct_audit direct_slr_empty] \
        attention_direct_is_placed_empty \
            [dict get $attention_direct_audit is_placed_empty] \
        attention_direct_placement_ok $attention_direct_placement_ok \
        pre_place_drc_errors $pre_drc_errors data_bufg $data_bufg \
        congestion_level5_or_higher_windows $congestion_level5_count \
        congestion_level6_or_higher_windows $congestion_level6_count \
        resource_ok $resource_ok placement_ok $placement_ok \
        uram_distribution_ok $uram_distribution_ok \
        fast_policy_ok $fast_policy_ok level5_screen_ok $level5_screen_ok \
        level6_congestion_ok $no_level6 fast_gate_ok 0 status FAIL] {
        puts $fp "$key=$value"
    }
    close $fp
    puts "V5_PRODUCTION_PLACE_FAST_GATE DATA_BUFG=$data_bufg LEVEL5=$congestion_level5_count LEVEL6=$congestion_level6_count STATUS=FAIL"
    error "V5 production placement rejected by the post-place fast gate"
}

write_checkpoint -force [file join $out post_place.dcp]
report_utilization -file [file join $out utilization_post_place.rpt]
report_utilization -hierarchical -hierarchical_depth 12 -file \
    [file join $out utilization_hier_post_place.rpt]
report_utilization -slr -file \
    [file join $out utilization_slr_post_place.rpt]
report_timing_summary -delay_type min_max -max_paths 100 \
    -report_unconstrained -file \
    [file join $out timing_post_place.rpt]
report_cdc -details -file [file join $out cdc_post_place.rpt]
report_clock_interaction -delay_type min_max -file \
    [file join $out clock_interaction_post_place.rpt]
report_clock_utilization -file \
    [file join $out clock_utilization_post_place.rpt]
report_drc -file [file join $out drc_post_place.rpt]

set unplaced [dict get $physical_metrics unplaced]
set post_drc_errors [llength [get_drc_violations -quiet -filter \
    {SEVERITY == Error}]]
set slr_dsp [dict get $physical_metrics slr_dsp]
set slr_uram [dict get $physical_metrics slr_uram]
set slr_ramb36 [dict get $physical_metrics slr_ramb36]

set clock_bufg 0
set data_bufg 0
foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}] {
    set outputs [get_pins -quiet -of_objects $cell -filter \
        {DIRECTION == OUT}]
    if {[llength [get_clocks -quiet -of_objects $outputs]] != 0} {
        incr clock_bufg
    } else {
        incr data_bufg
    }
}

set branch0_wrong [dict get $physical_metrics branch0_wrong]
set branch2_wrong [dict get $physical_metrics branch2_wrong]
set lane0_wrong [dict get $physical_metrics lane0_wrong]
set lane2_wrong [dict get $physical_metrics lane2_wrong]
set center_dsp_wrong [dict get $physical_metrics center_wrong]
set gate0_wrong [dict get $physical_metrics gate0_wrong]
set gate2_wrong [dict get $physical_metrics gate2_wrong]
set down0_wrong [dict get $physical_metrics down0_wrong]
set down1_wrong [dict get $physical_metrics down1_wrong]
set attention_meta_wrong [dict get $physical_metrics attention_meta_wrong]
set attention_island_wrong \
    [dict get $physical_metrics attention_island_wrong]
set composite21_additional_wrong \
    [dict get $physical_metrics additional_wrong]
set wrong_total [dict get $physical_metrics wrong_total]

set worst_setup [lindex [get_timing_paths -quiet -delay_type max \
    -max_paths 1] 0]
set worst_hold [lindex [get_timing_paths -quiet -delay_type min \
    -max_paths 1] 0]
if {[llength $worst_setup] == 0 || [llength $worst_hold] == 0} {
    error "V5 post-place timing queries returned no paths"
}
set wns [get_property SLACK $worst_setup]
set whs [get_property SLACK $worst_hold]
set setup_start [get_property STARTPOINT_PIN $worst_setup]
set setup_end [get_property ENDPOINT_PIN $worst_setup]
set hold_start [get_property STARTPOINT_PIN $worst_hold]
set hold_end [get_property ENDPOINT_PIN $worst_hold]

# Do not infer timing coverage from the existence of timing_post_place.rpt.
# Parse Vivado's canonical check_timing categories from a fresh return string;
# a format/category drift is an error rather than a zero-count assumption.
proc check_timing_count {text category} {
    set pattern [format \
        {checking[[:space:]]+%s[[:space:]]+\(([0-9]+)\)} $category]
    if {![regexp -nocase -- $pattern $text -> count]} {
        error "V5 post-place timing category is missing: $category"
    }
    return $count
}
set timing_coverage_text [report_timing_summary -delay_type min_max \
    -max_paths 10 -report_unconstrained -return_string]
set no_clock [check_timing_count $timing_coverage_text no_clock]
set unconstrained [check_timing_count $timing_coverage_text \
    unconstrained_internal_endpoints]
set no_input_delay [check_timing_count $timing_coverage_text no_input_delay]
set no_output_delay [check_timing_count $timing_coverage_text no_output_delay]
set partial_input_delay [check_timing_count $timing_coverage_text \
    partial_input_delay]
set partial_output_delay [check_timing_count $timing_coverage_text \
    partial_output_delay]
set timing_coverage_ok [expr {$no_clock == 0 && $unconstrained == 0 &&
    $no_input_delay == 3 && $no_output_delay == 0 &&
    $partial_input_delay == 0 && $partial_output_delay == 0}]

set cdc_path [file join $out cdc_post_place.rpt]
set cdc_fh [open $cdc_path r]
set cdc_text [read $cdc_fh]
close $cdc_fh
if {![regexp -line \
        {^[[:space:]]*ID[[:space:]]+Severity[[:space:]]+Count[[:space:]]+Description[[:space:]]*$} \
        $cdc_text]} {
    error "V5 post-place CDC report summary header is missing"
}
set cdc_critical 0
foreach {whole count} [regexp -all -inline -line -nocase \
        {^[^\n]*[[:space:]]Critical[[:space:]]+([1-9][0-9]*)[[:space:]]+[^\n]*$} \
        $cdc_text] {
    incr cdc_critical $count
}

set congestion_path [file join $out congestion_post_place.rpt]
set congestion_fh [open $congestion_path r]
set congestion_text [read $congestion_fh]
close $congestion_fh
set congestion_schema_header_count 0
set congestion_data_row_count 0
set congestion_level5_count 0
set congestion_level6_count 0
foreach line [split $congestion_text "\n"] {
    if {[regexp {^[[:space:]]*\|[[:space:]]*Direction[[:space:]]*\|[[:space:]]*Type[[:space:]]*\|[[:space:]]*Level[[:space:]]*\|[[:space:]]*Window[[:space:]]*\|} \
            $line]} {
        incr congestion_schema_header_count
        continue
    }
    if {![regexp {^[[:space:]]*\|[[:space:]]*(North|South|East|West)[[:space:]]*\|[[:space:]]*(Global|Long|Short)[[:space:]]*\|[[:space:]]*([0-9]+)[[:space:]]*\|[[:space:]]*\([^|]+\)[[:space:]]*\|} \
            $line -> direction type level]} {
        continue
    }
    incr congestion_data_row_count
    if {$level >= 5} {incr congestion_level5_count}
    if {$level >= 6} {incr congestion_level6_count}
}
set congestion_clean_marker [expr {
    [string first "No congestion windows are found above level 5" \
        $congestion_text] >= 0 ||
    [string first "No effective congestion windows are found above level 5" \
        $congestion_text] >= 0}]
set congestion_schema_ok [expr {$congestion_schema_header_count == 1 &&
    ($congestion_data_row_count >= 1 || $congestion_clean_marker)}]
if {!$congestion_schema_ok} {
    error "V5 post-place congestion report schema/data rows are unrecognized"
}
set no_level6 [expr {$congestion_level6_count == 0}]
set level5_screen_ok [expr {$congestion_level5_count <= 1}]

set exceptions_path [file join $out exceptions_coverage_post_place.rpt]
report_exceptions -coverage -file $exceptions_path
set exceptions_fh [open $exceptions_path r]
set exceptions_text [read $exceptions_fh]
close $exceptions_fh
set false_path_rows [regexp -all -line \
    {^[[:space:]]*[0-9]+[[:space:]]+False Path[[:space:]]} \
    $exceptions_text]
set datapath_only_rows [regexp -all -line \
    {^[[:space:]]*[0-9]+[[:space:]]+(Max|Min) Delay.*Datapath} \
    $exceptions_text]

set resource_ok [expr {
    [dict get $post_plan total_dsp] <= 5500 &&
    [dict get $post_plan total_uram] == 752 &&
    [dict get $post_plan kernel_dsp] == 3072 &&
    [dict get $post_plan history2_count] == 2 &&
    [dict get $post_plan generic_repack_count] == 0 &&
    [dict get $post_plan projection_weight_capture_ok] == 1 &&
    [llength $post_compact_input_frontend] == 1 &&
    [llength $post_down_elastic2] == 2
}]
set uram_distribution_ok [expr {
    [lindex $slr_uram 0] == 224 &&
    [lindex $slr_uram 1] == 224 &&
    [lindex $slr_uram 2] == 304
}]
set placement_ok [expr {
    [hap_v5_composite21::physical_ok $physical_metrics] &&
    [dict get $post_pblock_audit ok] &&
    [dict get $post_pblock_audit placed_wrong] == 0 &&
    $attention_direct_placement_ok &&
    $uram_distribution_ok}]
set policy_ok [expr {$pre_drc_errors == 0 && $post_drc_errors == 0 &&
    $false_path_rows == 0 && $datapath_only_rows == 0 && $data_bufg == 0 &&
    $timing_coverage_ok && $cdc_critical == 0}]
set status [expr {$resource_ok && $placement_ok && $policy_ok &&
    $fine19_optimizer_extras_ok && $composite21_selector_deltas_ok &&
    $composite21_pblock_optimizer_extras_ok &&
    $no_level6 && $level5_screen_ok ? "V5_PRODUCTION_PLACE_PASS" : "FAIL"}]
set route_eligible [expr {$status eq "V5_PRODUCTION_PLACE_PASS"}]

set fp [open [file join $out summary.txt] w]
foreach {key value} [list \
    tool [version -short] part [dict get $post_plan part] \
    top [dict get $post_plan top] flow_mode $flow_mode \
    acceptance_evidence $route_eligible route_eligible $route_eligible \
    checkpoint_written 1 input_dcp $in_dcp \
    input_dcp_sha256 $actual_dcp_sha \
    input_manifest_sha256 [hap_place_sha256 $input_sha] \
    input_manifest_entries 9 provenance_verified 1 \
    composite21_pre_place_manifest $preplace_output_sha \
    composite21_pre_place_manifest_sha256 $expected_preplace_output_sha \
    composite21_pre_place_input_manifest_sha256 $expected_preplace_input_sha \
    composite21_pre_place_verified 1 \
    composite21_pre_place_central_anchor_range \
        [dict get $composite_plan central_anchor_range] \
    composite21_pre_place_central_island_count \
        [dict get $composite_plan central_island_count] \
    composite21_pre_place_central_island_dsp \
        [dict get $composite_plan central_island_dsp] \
    composite21_pre_place_mlp_remaining_count \
        [dict get $composite_plan mlp_remaining_count] \
    composite21_pre_place_center_dsp_remaining \
        [dict get $composite_plan center_dsp_remaining_dsp] \
    composite21_pre_place_central_partition_ok \
        [dict get $composite_plan central_partition_ok] \
    fine19_post_place_optimizer_extra_count $fine19_post_optimizer_extras \
    fine19_post_place_optimizer_extras_ok $fine19_optimizer_extras_ok \
    composite21_post_place_fine_member_delta $composite21_post_fine_delta \
    composite21_post_place_mlp_residual_delta $composite21_post_mlp_delta \
    composite21_post_place_central_anchor_range \
        [dict get $post_composite_plan central_anchor_range] \
    composite21_post_place_central_island_count \
        [dict get $post_composite_plan central_island_count] \
    composite21_post_place_central_island_delta \
        $composite21_post_central_island_delta \
    composite21_post_place_central_island_dsp \
        [dict get $post_composite_plan central_island_dsp] \
    composite21_post_place_mlp_remaining_count \
        [dict get $post_composite_plan mlp_remaining_count] \
    composite21_post_place_mlp_remaining_delta \
        $composite21_post_mlp_remaining_delta \
    composite21_post_place_center_dsp_remaining \
        [dict get $post_composite_plan center_dsp_remaining_dsp] \
    composite21_post_place_central_partition_ok \
        $composite21_post_central_partition_ok \
    composite21_post_place_attention_direct_delta \
        $composite21_post_attention_delta \
    composite21_post_place_selector_deltas_ok $composite21_selector_deltas_ok \
    composite21_post_place_pblock_optimizer_extras \
        $composite21_pblock_optimizer_extras \
    composite21_post_place_pblock_optimizer_extras_ok \
        $composite21_pblock_optimizer_extras_ok \
    place_directive $place_directive jobs $jobs core_clock_mhz 100 \
    ddr0_clock_mhz 300 ddr1_clock_mhz 300 \
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
    compact_input_frontend_instances \
        [llength $post_compact_input_frontend] \
    down_elastic2_instances [llength $post_down_elastic2] \
    mlp_local_clear_ff [dict get $post_mlp_local_clear total] \
    mlp_local_clear_protected_ff [dict get $post_mlp_local_clear protected] \
    branch0_local_clear_ff [dict get $post_mlp_local_clear branch0] \
    branch1_local_clear_ff [dict get $post_mlp_local_clear branch1] \
    branch0_local_clear_slr [dict get $post_mlp_local_clear branch0_slr] \
    branch1_local_clear_slr [dict get $post_mlp_local_clear branch1_slr] \
    mlp_local_clear_wrong_slr [dict get $post_mlp_local_clear wrong] \
    mlp_central_clear_ff [dict get $post_mlp_local_clear central] \
    mlp_central_clear_branch_endpoints \
        [dict get $post_mlp_local_clear central_branch_endpoints] \
    mlp_central_clear_direct_branch_state \
        [dict get $post_mlp_local_clear central_direct_branch_state] \
    pblock_contract_variant \
        [dict get $post_pblock_audit contract_variant] \
    projection_exact_cover [dict get $post_fine_plan projection_exact_cover] \
    region1_exact_cover [dict get $post_fine_plan region1_exact_cover] \
    owner_exact_cover [dict get $post_fine_plan owner_exact_cover] \
    weight_owner_residency_ok \
        [dict get $post_fine_plan weight_owner_residency_ok] \
    attention_row_instances 1 kv_cache_instances 1 \
    kv_quantizer4_instances 1 \
    attention_island_target_slr \
        [dict get $post_plan attention_island_target] \
    attention_island_dsp48e2 \
        [dict get $post_plan attention_island_dsp] \
    attention_island_ramb36e2 \
        [dict get $post_plan attention_island_ramb36] \
    attention_island_ramb18e2 \
        [dict get $post_plan attention_island_ramb18] \
    attention_island_uram288 \
        [dict get $post_plan attention_island_uram] \
    attention_island_quantizer_overlap \
        [dict get $post_plan attention_island_quantizer_overlap] \
    attention_island_row_cache_overlap \
        [dict get $post_plan attention_island_row_cache_overlap] \
    outer0_dsp48e2 [dict get $post_plan outer0_dsp] \
    outer2_dsp48e2 [dict get $post_plan outer2_dsp] \
    outer0_ramb36e2 [dict get $post_plan outer0_ramb36] \
    outer2_ramb36e2 [dict get $post_plan outer2_ramb36] \
    attention_island_pblock_dsp48e2 \
        [dict get $attention_island_record dsp] \
    attention_island_pblock_ramb36e2 \
        [dict get $attention_island_record ramb36] \
    attention_island_pblock_ramb18e2 \
        [dict get $attention_island_record ramb18] \
    attention_island_pblock_uram288 \
        [dict get $attention_island_record uram] \
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
    branch0_wrong_slr $branch0_wrong branch2_wrong_slr $branch2_wrong \
    attention_lane0_wrong_slr $lane0_wrong \
    attention_lane2_wrong_slr $lane2_wrong \
    center_dsp_wrong_slr $center_dsp_wrong \
    metadata_gate0_wrong_slr $gate0_wrong \
    metadata_gate2_wrong_slr $gate2_wrong \
    metadata_down0_wrong_slr $down0_wrong \
    metadata_down1_wrong_slr $down1_wrong \
    attention_metadata_wrong_slr $attention_meta_wrong \
    attention_island_wrong_slr $attention_island_wrong \
    composite21_additional_wrong_slr $composite21_additional_wrong \
    p9_central_island_wrong_slr $p9_central_island_wrong \
    p9_center_dsp_remaining_wrong_slr $p9_center_dsp_remaining_wrong \
    p9_mlp_remaining_wrong_slr $p9_mlp_remaining_wrong \
    attention_direct_unconstrained 1 \
    attention_direct_slr0_primitives [lindex $attention_direct_slr_counts 0] \
    attention_direct_slr1_primitives [lindex $attention_direct_slr_counts 1] \
    attention_direct_slr2_primitives [lindex $attention_direct_slr_counts 2] \
    attention_direct_physical_primitives \
        [dict get $attention_direct_audit physical_count] \
    attention_direct_virtual_primitives \
        [dict get $attention_direct_audit virtual_total] \
    attention_direct_unresolved_primitives \
        [dict get $attention_direct_audit direct_slr_empty] \
    attention_direct_is_placed_empty \
        [dict get $attention_direct_audit is_placed_empty] \
    attention_direct_placement_ok $attention_direct_placement_ok \
    pre_place_drc_errors $pre_drc_errors \
    post_place_drc_errors $post_drc_errors \
    false_path_exception_rows $false_path_rows \
    datapath_only_exception_rows $datapath_only_rows \
    no_clock_endpoints $no_clock unconstrained_paths $unconstrained \
    no_input_delay_ports $no_input_delay \
    no_output_delay_ports $no_output_delay \
    partial_input_delay_ports $partial_input_delay \
    partial_output_delay_ports $partial_output_delay \
    timing_coverage_ok $timing_coverage_ok cdc_critical $cdc_critical \
    clock_bufg $clock_bufg data_bufg $data_bufg \
    congestion_level5_or_higher_windows $congestion_level5_count \
    congestion_level6_or_higher_windows $congestion_level6_count \
    congestion_schema_header_count $congestion_schema_header_count \
    congestion_data_rows_recognized $congestion_data_row_count \
    congestion_schema_ok $congestion_schema_ok \
    post_place_wns_ns $wns post_place_whs_ns $whs \
    worst_setup_start $setup_start worst_setup_end $setup_end \
    worst_hold_start $hold_start worst_hold_end $hold_end \
    resource_ok $resource_ok placement_ok $placement_ok \
    uram_distribution_ok $uram_distribution_ok \
    pre_place_pblock_contract_ok [dict get $pre_pblock_audit ok] \
    post_place_live_rediscovery_ok 1 \
    post_place_pblock_contract_ok [dict get $post_pblock_audit ok] \
    post_place_pblock_count [dict get $post_pblock_audit pblock_count] \
    post_place_pblock_dsp_coverage \
        [dict get $post_pblock_audit dsp_coverage] \
    post_place_pblock_uram_coverage \
        [dict get $post_pblock_audit uram_coverage] \
    post_place_pblock_wrong_slr \
        [dict get $post_pblock_audit placed_wrong] \
    post_place_pblock_overlap \
        [dict get $post_pblock_audit member_overlap] \
    post_place_pblock_optimizer_extras \
        [dict get $post_pblock_audit optimizer_extra_count] \
    global_virtual_gnd [dict get $physical_metrics global_virtual_gnd] \
    global_virtual_vcc [dict get $physical_metrics global_virtual_vcc] \
    global_virtual_total [dict get $physical_metrics global_virtual_total] \
    global_physical_primitives \
        [dict get $physical_metrics global_physical_count] \
    global_direct_slr_empty \
        [dict get $physical_metrics global_direct_slr_empty] \
    global_is_placed_empty \
        [dict get $physical_metrics global_is_placed_empty] \
    fast_gate_ok $fast_gate_ok policy_ok $policy_ok \
    level5_screen_ok $level5_screen_ok level6_congestion_ok $no_level6 \
    status $status] {
    puts $fp "$key=$value"
}
close $fp

puts "V5_PRODUCTION_PLACE DSP=$slr_dsp URAM=$slr_uram UNPLACED=$unplaced WRONG_SLR=$wrong_total DATA_BUFG=$data_bufg LEVEL5=$congestion_level5_count LEVEL6=$congestion_level6_count WNS=$wns WHS=$whs STATUS=$status"
if {$status ne "V5_PRODUCTION_PLACE_PASS"} {
    error "V5 production post-place acceptance gate failed"
}
}
close_design
