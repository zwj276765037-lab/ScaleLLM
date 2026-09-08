# Read-only clock-region occupancy probe for the rejected P6 placement.

set dcp [file normalize $::env(HAP_P6_GRID_DCP)]
set out [file normalize $::env(HAP_P6_GRID_DIR)]
set expected_dcp_sha $::env(HAP_P6_GRID_DCP_SHA256)
set input_sha [file normalize $::env(HAP_P6_GRID_INPUT_SHA)]
set expected_input_sha $::env(HAP_P6_GRID_INPUT_SHA256)
set failed_output [file normalize $::env(HAP_P6_GRID_FAILED_OUTPUT_SHA)]
set expected_failed_output_sha $::env(HAP_P6_GRID_FAILED_OUTPUT_SHA256)
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
file mkdir $out

proc hap_p6_grid_sha256 {path} {
    set digest [lindex [exec sha256sum -- $path] 0]
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "Malformed SHA256 for $path"
    }
    return $digest
}

proc hap_p6_grid_require_count {label objects expected} {
    set actual [llength $objects]
    if {$actual != $expected} {
        error "$label count mismatch: expected=$expected actual=$actual"
    }
    return $actual
}

proc hap_p6_grid_count_ref {cells pattern} {
    if {[llength $cells] == 0} {return 0}
    set count 0
    foreach ref [get_property REF_NAME $cells] {
        if {[string match $pattern $ref]} {incr count}
    }
    return $count
}

proc hap_p6_grid_resource_row {handle clock_region group cells} {
    puts $handle [join [list $clock_region $group [llength $cells] \
        [hap_p6_grid_count_ref $cells LUT*] \
        [hap_p6_grid_count_ref $cells FD*] \
        [hap_p6_grid_count_ref $cells DSP48E2] \
        [hap_p6_grid_count_ref $cells RAMB36E2] \
        [hap_p6_grid_count_ref $cells RAMB18E2] \
        [hap_p6_grid_count_ref $cells URAM288]] "\t"]
}

proc hap_p6_grid_region2_groups {cells} {
    set groups [dict create residual {} rows0_3 {} rows4_7 {} \
        cols8_9 {} cols10_11 {} rows0_3_cols8_9 {} \
        rows0_3_cols10_11 {} rows4_7_cols8_9 {} rows4_7_cols10_11 {}]
    foreach cell $cells {
        set name [get_property NAME $cell]
        if {![regexp {/g_row\[([0-9]+)\]\.g_col\[([0-9]+)\]\.u_lane/} \
                $name -> row col]} {
            dict lappend groups residual $cell
            continue
        }
        set row_group [expr {$row < 4 ? "rows0_3" : "rows4_7"}]
        set col_group [expr {$col < 2 ? "cols8_9" : "cols10_11"}]
        dict lappend groups $row_group $cell
        dict lappend groups $col_group $cell
        dict lappend groups ${row_group}_${col_group} $cell
    }
    return $groups
}

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
if {[llength [get_designs -quiet]] != 0} {
    error "P6 region2 grid probe requires a fresh Vivado process"
}
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "P6 region2 grid probe requires HAP_JOBS=32"
}
foreach digest [list $expected_dcp_sha $expected_input_sha \
        $expected_failed_output_sha] {
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "P6 region2 grid probe received malformed SHA256"
    }
}
if {[hap_p6_grid_sha256 $dcp] ne $expected_dcp_sha ||
        [hap_p6_grid_sha256 $input_sha] ne $expected_input_sha ||
        [hap_p6_grid_sha256 $failed_output] ne $expected_failed_output_sha} {
    error "P6 region2 grid probe input identity mismatch"
}
if {[catch {exec sha256sum -c --strict $input_sha} message]} {
    error "P6 region2 grid input manifest failed: $message"
}
if {[catch {exec sha256sum -c --strict $failed_output} message]} {
    error "P6 failed-placement manifest failed: $message"
}

set_param general.maxThreads $jobs
set open_start [clock milliseconds]
open_checkpoint $dcp
set open_elapsed [expr {[clock milliseconds] - $open_start}]
if {[get_property PART [current_project]] ne "xcvu9p-flga2104-2L-e" ||
        [get_property TOP [current_design]] ne \
            "hap_attention_mlp_production_core"} {
    error "P6 region2 grid design identity mismatch"
}
hap_p6_grid_require_count pblocks [get_pblocks -quiet] 25
hap_p6_grid_require_count dsp48e2 \
    [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}] 5453
hap_p6_grid_require_count uram288 \
    [get_cells -quiet -hierarchical -filter {REF_NAME == URAM288}] 752

set region2_root \
    u_compute/u_attention/u_compute/g_projection_rtl.u_projection/u_array/u_center12/u_region2_cols8_11
hap_p6_grid_require_count region2_root [get_cells -quiet $region2_root] 1

set capacity_fh [open [file join $out clock_region_capacity.tsv] w]
puts $capacity_fh \
    "clock_region\tslice_sites\tdsp_sites\tramb36_sites\tramb18_sites\turam_sites"
set resource_fh [open [file join $out clock_region_resources.tsv] w]
puts $resource_fh \
    "clock_region\tgroup\ttotal\tlut\tff\tdsp\tramb36\tramb18\turam"
set clock_regions {}
set site_to_clock_region [dict create]
for {set x 0} {$x <= 1} {incr x} {
    for {set y 5} {$y <= 9} {incr y} {
        set cr_name CLOCKREGION_X${x}Y${y}
        set cr [get_clock_regions -quiet X${x}Y${y}]
        hap_p6_grid_require_count "clock region $cr_name" $cr 1
        lappend clock_regions $cr_name
        set sites [get_sites -quiet -of_objects $cr]
        foreach site_name [get_property NAME $sites] {
            if {[dict exists $site_to_clock_region $site_name]} {
                error "Clock-region site overlap: $site_name"
            }
            dict set site_to_clock_region $site_name $cr_name
        }
        puts $capacity_fh [join [list $cr_name \
            [llength [filter $sites {SITE_TYPE =~ SLICE*}]] \
            [llength [filter $sites {SITE_TYPE == DSP48E2}]] \
            [llength [filter $sites {SITE_TYPE == RAMB36E2}]] \
            [llength [filter $sites {SITE_TYPE == RAMB18E2}]] \
            [llength [filter $sites {SITE_TYPE == URAM288}]]] "\t"]
    }
}

# LOC is authoritative for transformed macros in this checkpoint class.  Map
# every physical primitive once instead of relying on incomplete reverse
# site/BEL relationships.
set placed_by_clock_region [dict create]
foreach cr_name $clock_regions {dict set placed_by_clock_region $cr_name {}}
set physical [get_cells -quiet -hierarchical -filter {
    IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL &&
    REF_NAME != GND && REF_NAME != VCC}]
set physical_locs [get_property LOC $physical]
if {[llength $physical_locs] != [llength $physical]} {
    error "Physical LOC cardinality mismatch"
}
foreach cell $physical loc $physical_locs {
    if {$loc eq ""} {error "Nonconstant primitive has no LOC: $cell"}
    if {[dict exists $site_to_clock_region $loc]} {
        dict lappend placed_by_clock_region \
            [dict get $site_to_clock_region $loc] $cell
    }
}

set region2_total 0
set region2_dsp 0
foreach cr_name $clock_regions {
        set placed [dict get $placed_by_clock_region $cr_name]
        hap_p6_grid_resource_row $resource_fh $cr_name all_placed $placed
        set region2 [filter $placed "NAME =~ ${region2_root}/*"]
        incr region2_total [llength $region2]
        incr region2_dsp [hap_p6_grid_count_ref $region2 DSP48E2]
        hap_p6_grid_resource_row $resource_fh $cr_name region2_total $region2
        set groups [hap_p6_grid_region2_groups $region2]
        foreach group [lsort -dictionary [dict keys $groups]] {
            hap_p6_grid_resource_row $resource_fh $cr_name \
                region2_$group [dict get $groups $group]
        }
}
close $capacity_fh
close $resource_fh

set status [expr {$region2_total == 68799 && $region2_dsp == 544 ?
    "V5_P10_P6_REGION2_GRID_DIAGNOSIS_PASS" : "FAIL"}]
set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] \
        stage V5_P10_P6_REGION2_GRID_DIAGNOSIS \
        evidence_class READ_ONLY_REJECTED_P6_PLACEMENT \
        input_dcp $dcp input_dcp_sha256 $expected_dcp_sha \
        input_manifest_sha256 $expected_input_sha \
        failed_output_manifest_sha256 $expected_failed_output_sha jobs $jobs \
        pblock_count 25 dsp48e2 5453 uram288 752 \
        region2_primitives $region2_total region2_dsp48e2 $region2_dsp \
        open_checkpoint_elapsed_ms $open_elapsed floorplan_mutated 0 \
        implementation_commands_run 0 checkpoint_written 0 route_eligible 0 \
        status $status] {
    puts $fp "$key=$value"
}
close $fp
close_design
if {$status eq "FAIL"} {error "P6 region2 grid diagnosis failed"}
puts "P6_REGION2_GRID_DIAGNOSIS_PASS"
