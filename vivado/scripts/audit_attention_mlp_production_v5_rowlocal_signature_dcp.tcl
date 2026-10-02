set dcp [file normalize $::env(HAP_DCP)]
set out [file normalize $::env(HAP_SIGNATURE_DIR)]
set input_sha [file normalize $::env(HAP_SIGNATURE_INPUT_SHA)]
set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)
set expected_manifest_sha $::env(HAP_SIGNATURE_INPUT_MANIFEST_SHA256)
set expected_launcher [file normalize $::env(HAP_SIGNATURE_LAUNCHER)]
set audit_script [file normalize [info script]]
set summary [file join $out signature.txt]

file mkdir $out

proc hap_read_nonempty {path label} {
    if {![file exists $path] || ![file isfile $path] ||
        [file size $path] == 0} {
        error "Missing or empty $label: $path"
    }
    set handle [open $path r]
    set text [read $handle]
    close $handle
    return $text
}

proc hap_sha256 {path} {
    set digest [lindex [exec sha256sum -- $path] 0]
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "Malformed SHA256 digest for $path: $digest"
    }
    return $digest
}

proc hap_verify_sha_manifest {path expected_count expected_manifest_sha} {
    if {[hap_sha256 $path] ne $expected_manifest_sha} {
        error "Signature input manifest identity mismatch"
    }
    set count 0
    set seen [dict create]
    foreach raw [split [hap_read_nonempty $path "input SHA manifest"] "\n"] {
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
        hap_read_nonempty $normalized "frozen signature input"
        set actual [hap_sha256 $normalized]
        if {$actual ne $expected} {
            error "Signature input SHA mismatch: $normalized"
        }
        dict set seen $normalized $expected
        incr count
    }
    if {$count != $expected_count} {
        error "Signature input SHA cardinality mismatch: $count"
    }
    return $seen
}

proc cells_of_module {module_name} {
    return [lsort -dictionary [get_cells -quiet -hierarchical -filter \
        "ORIG_REF_NAME == $module_name || REF_NAME == $module_name"]]
}

proc require_count {label values expected} {
    if {[llength $values] != $expected} {
        error "$label count mismatch: expected=$expected actual=[llength $values]"
    }
}

proc primitive_descendants {root} {
    set root_name [get_property NAME $root]
    return [lsort -dictionary -unique \
        [get_cells -quiet -hierarchical -filter \
            "IS_PRIMITIVE && NAME =~ ${root_name}/*"]]
}

proc list_union {args} {
    set result {}
    foreach values $args {set result [concat $result $values]}
    return [lsort -dictionary -unique $result]
}

proc list_subtract {left right} {
    set rejected [dict create]
    foreach item $right {dict set rejected $item 1}
    set result {}
    foreach item $left {
        if {![dict exists $rejected $item]} {lappend result $item}
    }
    return [lsort -dictionary -unique $result]
}

proc intersection_count {left right} {
    set included [dict create]
    foreach item $right {dict set included $item 1}
    set count 0
    foreach item $left {
        if {[dict exists $included $item]} {incr count}
    }
    return $count
}

proc utilization_value {text pattern label} {
    if {![regexp $pattern $text unused value]} {
        error "Unable to parse $label from scoped report_utilization"
    }
    return $value
}

proc resource_signature {cells utilization_cells} {
    set signature [dict create primitive [llength $cells] lut_primitive 0 \
        srl16e 0 ff_primitive 0 dsp 0 ramb36 0 ramb18 0 uram 0]
    foreach cell $cells {
        set ref [get_property REF_NAME $cell]
        switch -glob -- $ref {
            LUT* {dict incr signature lut_primitive}
            FD* {dict incr signature ff_primitive}
            SRL16E {dict incr signature srl16e}
            DSP48E2 {dict incr signature dsp}
            RAMB36E2 {dict incr signature ramb36}
            RAMB18E2 {dict incr signature ramb18}
            URAM288 {dict incr signature uram}
        }
    }
    set util [report_utilization -cells $utilization_cells -return_string]
    dict set signature clb_lut [utilization_value $util \
        {\| CLB LUTs\*?\s+\|\s*([0-9]+)} "CLB LUTs"]
    dict set signature clb_register [utilization_value $util \
        {\| CLB Registers\s+\|\s*([0-9]+)} "CLB Registers"]
    return $signature
}

proc require_signature {label signature expected} {
    foreach key [dict keys $expected] {
        if {[dict get $signature $key] != [dict get $expected $key]} {
            error "$label signature mismatch: key=$key expected=[dict get $expected $key] actual=[dict get $signature $key]"
        }
    }
}

proc emit_signature {handle prefix name signature} {
    puts $handle "${prefix}_name=$name"
    foreach key {primitive lut_primitive srl16e ff_primitive clb_lut
            clb_register dsp ramb36 ramb18 uram} {
        puts $handle "${prefix}_${key}=[dict get $signature $key]"
    }
}

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required"
}
if {[llength [get_designs -quiet]] != 0} {
    error "Row-local signature audit requires a fresh Vivado process"
}
foreach digest [list $expected_dcp_sha $expected_manifest_sha] {
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "Malformed frozen SHA256 digest"
    }
}
hap_read_nonempty $dcp "V5 post-opt DCP"
set frozen [hap_verify_sha_manifest $input_sha 3 $expected_manifest_sha]
foreach required [list $dcp $audit_script $expected_launcher] {
    if {![dict exists $frozen [file normalize $required]]} {
        error "Required signature input is absent from SHA manifest: $required"
    }
}
set actual_dcp_sha [hap_sha256 $dcp]
if {$actual_dcp_sha ne $expected_dcp_sha} {
    error "Row-local signature DCP identity mismatch"
}

open_checkpoint $dcp
if {[get_property TOP [current_design]] ne
        "hap_attention_mlp_production_core" ||
    [get_property PART [current_design]] ne "xcvu9p-flga2104-2L-e"} {
    error "Unexpected design identity in row-local signature audit"
}

set frontends [cells_of_module hap_mlp_swiglu_product_frontend16_q4]
set leaves [cells_of_module hap_mlp_swiglu_row_stream8_q4]
set hadamards [cells_of_module hap_mlp_hadamard32_s32_norm_stream]
set quantizers [cells_of_module hap_mlp_robust_a8_quantizer_s35]
set compute_branches [cells_of_module hap_mlp_shared_local_slice8x12_s44_s46]
set shared_roots [cells_of_module hap_mlp_shared_dual_slice16x12_s44_s46]
set attention_rows [cells_of_module hap_attention_row_head128]
set kv_caches [cells_of_module hap_kv12_cache]
require_count frontend $frontends 1
require_count row_leaf $leaves 2
require_count unique_hadamard $hadamards 1
require_count quantizer $quantizers 4
require_count compute_branch $compute_branches 2
require_count shared_compute $shared_roots 1
require_count attention_row $attention_rows 1
require_count kv_cache $kv_caches 1

set frontend [lindex $frontends 0]
set frontend_name [get_property NAME $frontend]
set shared [lindex $shared_roots 0]
set shared_name [get_property NAME $shared]
set leaf0_name [format {%s/g_row_branch[0].u_branch_leaf} $frontend_name]
set leaf1_name [format {%s/g_row_branch[1].u_branch_leaf} $frontend_name]
set hadamard_name [format {%s/u_hadamard} $frontend_name]
set branch0_name [format {%s/u_branch0} $shared_name]
set branch1_name [format {%s/u_branch1} $shared_name]
set leaf_by_name [dict create]
foreach leaf $leaves {dict set leaf_by_name [get_property NAME $leaf] $leaf}
set branch_by_name [dict create]
foreach branch $compute_branches {
    dict set branch_by_name [get_property NAME $branch] $branch
}
foreach required_name [list $leaf0_name $leaf1_name] {
    if {![dict exists $leaf_by_name $required_name]} {
        error "Missing exact row-local leaf hierarchy: $required_name"
    }
}
foreach required_name [list $branch0_name $branch1_name] {
    if {![dict exists $branch_by_name $required_name]} {
        error "Missing exact compute-branch hierarchy: $required_name"
    }
}
if {[get_property NAME [lindex $hadamards 0]] ne $hadamard_name} {
    error "Unique central Hadamard hierarchy mismatch"
}
set quantizer_by_name [dict create]
for {set index 0} {$index < 4} {incr index} {
    set expected [format {%s/g_quantizer[%d].u_quantizer} \
        $frontend_name $index]
    dict set quantizer_by_name $expected 0
}
foreach quantizer $quantizers {
    set name [get_property NAME $quantizer]
    if {![dict exists $quantizer_by_name $name]} {
        error "Unexpected central quantizer hierarchy: $name"
    }
    dict set quantizer_by_name $name 1
}
foreach name [dict keys $quantizer_by_name] {
    if {![dict get $quantizer_by_name $name]} {
        error "Missing central quantizer hierarchy: $name"
    }
}

set leaf0 [dict get $leaf_by_name $leaf0_name]
set leaf1 [dict get $leaf_by_name $leaf1_name]
set branch0 [dict get $branch_by_name $branch0_name]
set branch1 [dict get $branch_by_name $branch1_name]
set leaf0_cells [primitive_descendants $leaf0]
set leaf1_cells [primitive_descendants $leaf1]
set hadamard_cells [primitive_descendants [lindex $hadamards 0]]
set quantizer_cells {}
foreach quantizer $quantizers {
    set quantizer_cells [concat $quantizer_cells \
        [primitive_descendants $quantizer]]
}
set quantizer_cells [lsort -dictionary -unique $quantizer_cells]
set frontend_cells [primitive_descendants $frontend]
set child_cells [list_union $leaf0_cells $leaf1_cells $hadamard_cells \
    $quantizer_cells]
set frontend_direct_cells [list_subtract $frontend_cells $child_cells]
set branch0_cells [primitive_descendants $branch0]
set branch1_cells [primitive_descendants $branch1]
set attention_row_cells [primitive_descendants [lindex $attention_rows 0]]
set kv_cache_cells [primitive_descendants [lindex $kv_caches 0]]

set overlap_total 0
foreach {left right} [list \
        $leaf0_cells $leaf1_cells \
        $leaf0_cells $hadamard_cells \
        $leaf1_cells $hadamard_cells \
        $leaf0_cells $quantizer_cells \
        $leaf1_cells $quantizer_cells \
        $hadamard_cells $quantizer_cells \
        $frontend_cells $branch0_cells \
        $frontend_cells $branch1_cells \
        $attention_row_cells $kv_cache_cells] {
    incr overlap_total [intersection_count $left $right]
}
if {$overlap_total != 0 || [llength $child_cells] +
        [llength $frontend_direct_cells] != [llength $frontend_cells]} {
    error "Row-local resource sets overlap or do not cover the frontend"
}

set leaf0_sig [resource_signature $leaf0_cells $leaf0]
set leaf1_sig [resource_signature $leaf1_cells $leaf1]
set hadamard_sig [resource_signature $hadamard_cells [lindex $hadamards 0]]
set quantizer_sig [resource_signature $quantizer_cells $quantizers]
set frontend_sig [resource_signature $frontend_cells $frontend]
set direct_sig [resource_signature $frontend_direct_cells \
    $frontend_direct_cells]
set branch0_sig [resource_signature $branch0_cells $branch0]
set branch1_sig [resource_signature $branch1_cells $branch1]
set attention_row_sig [resource_signature $attention_row_cells \
    [lindex $attention_rows 0]]
set kv_cache_sig [resource_signature $kv_cache_cells [lindex $kv_caches 0]]

set leaf_expected [dict create clb_lut 1886 clb_register 6317 dsp 2 \
    ramb36 6 ramb18 0 uram 0]
require_signature leaf0 $leaf0_sig $leaf_expected
require_signature leaf1 $leaf1_sig $leaf_expected
require_signature central_hadamard $hadamard_sig [dict create \
    clb_lut 9019 clb_register 4657 dsp 64 ramb36 0 ramb18 0 uram 0]
require_signature central_quantizers $quantizer_sig [dict create \
    clb_lut 22517 clb_register 15821 dsp 4 ramb36 0 ramb18 0 uram 0]
require_signature frontend $frontend_sig [dict create \
    clb_lut 54591 clb_register 66591 dsp 76 ramb36 12 ramb18 0 uram 0]
require_signature frontend_direct $direct_sig [dict create \
    clb_lut 19283 clb_register 33479 dsp 4 ramb36 0 ramb18 0 uram 0]
require_signature compute_branch0 $branch0_sig [dict create \
    clb_lut 188574 clb_register 216601 dsp 1536 \
    ramb36 96 ramb18 0 uram 0]
require_signature compute_branch1 $branch1_sig [dict create \
    clb_lut 188574 clb_register 216601 dsp 1536 \
    ramb36 96 ramb18 0 uram 0]
require_signature attention_row $attention_row_sig [dict create \
    clb_lut 8825 clb_register 7560 dsp 52 ramb36 0 ramb18 0 uram 0]
require_signature kv_cache $kv_cache_sig [dict create \
    clb_lut 303 clb_register 3 dsp 0 ramb36 88 ramb18 2 uram 0]

report_utilization -hierarchical -hierarchical_depth 12 \
    -file [file join $out utilization_hier_signature.rpt]
set handle [open $summary w]
puts $handle "tool=[version -short]"
puts $handle "evidence_class=V5_ROWLOCAL_POST_OPT_READ_ONLY_SIGNATURE"
puts $handle "dcp=$dcp"
puts $handle "input_dcp_sha256=$actual_dcp_sha"
puts $handle "input_manifest_sha256=[hap_sha256 $input_sha]"
emit_signature $handle frontend $frontend_name $frontend_sig
emit_signature $handle leaf0 $leaf0_name $leaf0_sig
emit_signature $handle leaf1 $leaf1_name $leaf1_sig
emit_signature $handle central_hadamard $hadamard_name $hadamard_sig
emit_signature $handle central_quantizers aggregate $quantizer_sig
emit_signature $handle frontend_direct direct_children_excluded $direct_sig
emit_signature $handle compute_branch0 $branch0_name $branch0_sig
emit_signature $handle compute_branch1 $branch1_name $branch1_sig
emit_signature $handle attention_row \
    [get_property NAME [lindex $attention_rows 0]] $attention_row_sig
emit_signature $handle kv_cache \
    [get_property NAME [lindex $kv_caches 0]] $kv_cache_sig
puts $handle "selected_set_overlap=$overlap_total"
puts $handle "frontend_child_coverage=[llength $child_cells]"
puts $handle "frontend_direct_coverage=[llength $frontend_direct_cells]"
puts $handle "frontend_total_coverage=[llength $frontend_cells]"
puts $handle "checkpoint_written=0"
puts $handle "implementation_commands_run=0"
puts $handle "status=V5_ROWLOCAL_SIGNATURE_PASS"
close $handle

puts "V5_ROWLOCAL_SIGNATURE LEAF_DSP=[dict get $leaf0_sig dsp]/[dict get $leaf1_sig dsp] LEAF_BRAM=[dict get $leaf0_sig ramb36]/[dict get $leaf1_sig ramb36] CENTRAL_H/Q_DSP=[dict get $hadamard_sig dsp]/[dict get $quantizer_sig dsp] FRONTEND_LUT_FF=[dict get $frontend_sig clb_lut]/[dict get $frontend_sig clb_register] STATUS=PASS"
close_design
