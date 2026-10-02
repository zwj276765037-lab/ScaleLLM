set dcp [file normalize $::env(HAP_DCP)]
set out [file normalize $::env(HAP_AUDIT_DIR)]
set summary [file join $out audit.txt]
set input_sha [file normalize $::env(HAP_AUDIT_INPUT_SHA)]
set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)
set expected_manifest_sha $::env(HAP_AUDIT_INPUT_MANIFEST_SHA256)
set expected_launcher [file normalize $::env(HAP_AUDIT_LAUNCHER)]
set audit_script [file normalize [info script]]

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
    set actual_manifest_sha [hap_sha256 $path]
    if {$actual_manifest_sha ne $expected_manifest_sha} {
        error "Input SHA manifest identity mismatch: expected=$expected_manifest_sha actual=$actual_manifest_sha"
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
        hap_read_nonempty $normalized "frozen post-opt audit input"
        set actual [hap_sha256 $normalized]
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

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
if {[llength [get_designs -quiet]] != 0} {
    error "V5 post-opt reopen audit requires a fresh process with no open design"
}
if {![regexp {^[0-9a-f]{64}$} $expected_dcp_sha]} {
    error "Malformed expected DCP SHA256: $expected_dcp_sha"
}
if {![regexp {^[0-9a-f]{64}$} $expected_manifest_sha]} {
    error "Malformed expected input-manifest SHA256: $expected_manifest_sha"
}
hap_read_nonempty $dcp "V5 post-opt DCP"
set frozen [hap_verify_sha_manifest $input_sha 3 $expected_manifest_sha]
foreach required [list $dcp $audit_script $expected_launcher] {
    if {![dict exists $frozen [file normalize $required]]} {
        error "Required post-opt audit input is absent from SHA manifest: $required"
    }
}
set actual_dcp_sha [hap_sha256 $dcp]
if {$actual_dcp_sha ne $expected_dcp_sha} {
    error "V5 post-opt DCP identity mismatch: expected=$expected_dcp_sha actual=$actual_dcp_sha"
}

proc cells_of_module {module_name} {
    return [get_cells -quiet -hierarchical -filter \
        "ORIG_REF_NAME == $module_name || REF_NAME == $module_name"]
}

proc is_literal_descendant {root_name candidate_name} {
    return [expr {[string first "${root_name}/" $candidate_name] == 0}]
}

proc descendants_of_type {roots primitive} {
    set result {}
    set primitives [get_cells -quiet -hierarchical -filter \
        "REF_NAME == $primitive"]
    foreach primitive_cell $primitives {
        set primitive_name [get_property NAME $primitive_cell]
        foreach root_cell $roots {
            set root_name [get_property NAME $root_cell]
            if {[is_literal_descendant $root_name $primitive_name]} {
                lappend result $primitive_cell
                break
            }
        }
    }
    return [lsort -dictionary -unique $result]
}

proc descendants_of_glob {roots primitive_glob} {
    set result {}
    set primitives [get_cells -quiet -hierarchical -filter \
        "REF_NAME =~ $primitive_glob"]
    foreach primitive_cell $primitives {
        set primitive_name [get_property NAME $primitive_cell]
        foreach root_cell $roots {
            set root_name [get_property NAME $root_cell]
            if {[is_literal_descendant $root_name $primitive_name]} {
                lappend result $primitive_cell
                break
            }
        }
    }
    return [lsort -dictionary -unique $result]
}

proc cells_below_roots {roots candidates} {
    set result {}
    foreach cell $candidates {
        set cell_name [get_property NAME $cell]
        foreach root_cell $roots {
            set root_name [get_property NAME $root_cell]
            if {[is_literal_descendant $root_name $cell_name]} {
                lappend result $cell
                break
            }
        }
    }
    return [lsort -dictionary -unique $result]
}

proc named_descendants_of_glob {roots primitive_glob relative_glob} {
    set result {}
    foreach cell [descendants_of_glob $roots $primitive_glob] {
        set cell_name [get_property NAME $cell]
        foreach root_cell $roots {
            set root_name [get_property NAME $root_cell]
            if {![is_literal_descendant $root_name $cell_name]} {continue}
            set relative_name [string range $cell_name \
                [string length "${root_name}/"] end]
            if {[string match $relative_glob $relative_name]} {
                lappend result $cell
                break
            }
        }
    }
    return [lsort -dictionary -unique $result]
}

proc direct_children_of_type {roots primitive} {
    set result {}
    foreach cell [descendants_of_type $roots $primitive] {
        set cell_name [get_property NAME $cell]
        foreach root_cell $roots {
            set root_name [get_property NAME $root_cell]
            if {![is_literal_descendant $root_name $cell_name]} {continue}
            set relative_name [string range $cell_name \
                [string length "${root_name}/"] end]
            if {[string first "/" $relative_name] < 0} {
                lappend result $cell
            }
            break
        }
    }
    return [lsort -dictionary -unique $result]
}

proc require_count {label objects expected} {
    set actual [llength $objects]
    if {$actual != $expected} {
        error "$label count mismatch: expected=$expected actual=$actual"
    }
    return $actual
}

proc audit_weight_capture_class {root_name label stem expected_nets \
        expected_loads} {
    set nets [lsort -dictionary [get_nets -quiet -hierarchical -filter \
        "NAME =~ ${root_name}/${stem}*"]]
    require_count ${label}_capture_nets $nets $expected_nets
    set min_load 1000000000
    set max_load 0
    foreach net $nets {
        set driver_pins [get_pins -quiet -leaf -of_objects $net -filter \
            {DIRECTION == OUT}]
        require_count ${label}_capture_driver_pin $driver_pins 1
        set driver [get_cells -quiet -of_objects $driver_pins]
        require_count ${label}_capture_driver $driver 1
        if {[get_property REF_NAME $driver] ne "LUT2"} {
            error "$label capture driver is not a LUT2: $driver"
        }
        set loads [get_pins -quiet -leaf -of_objects $net -filter \
            {DIRECTION == IN}]
        require_count ${label}_capture_loads $loads $expected_loads
        set ce_loads [get_pins -quiet -leaf -of_objects $net -filter \
            {DIRECTION == IN && REF_PIN_NAME == CE}]
        require_count ${label}_capture_ce_loads $ce_loads $expected_loads
        set load_count [llength $loads]
        if {$load_count < $min_load} {set min_load $load_count}
        if {$load_count > $max_load} {set max_load $load_count}
    }
    return [dict create nets [llength $nets] min_load $min_load \
        max_load $max_load]
}

proc audit_projection_weight_capture {roots} {
    require_count projection_weight_capture_roots $roots 1
    set root_name [get_property NAME [lindex $roots 0]]
    set raw_weight_push [get_nets -quiet -hierarchical -filter \
        "NAME == ${root_name}/weight_push"]
    require_count raw_weight_push_net $raw_weight_push 1
    set raw_loads [get_pins -quiet -leaf -of_objects $raw_weight_push \
        -filter {DIRECTION == IN}]
    require_count raw_weight_push_loads $raw_loads 37
    set data [audit_weight_capture_class $root_name weight_data \
        weight_data_capture_enable 32 256]
    set meta [audit_weight_capture_class $root_name weight_meta \
        weight_meta_capture_enable 2 256]
    set group [audit_weight_capture_class $root_name weight_group \
        weight_group_capture_enable 2 7]
    return [dict create raw_loads [llength $raw_loads] \
        data_nets [dict get $data nets] \
        data_min [dict get $data min_load] data_max [dict get $data max_load] \
        meta_nets [dict get $meta nets] \
        meta_min [dict get $meta min_load] meta_max [dict get $meta max_load] \
        group_nets [dict get $group nets] \
        group_min [dict get $group min_load] \
        group_max [dict get $group max_load] ok 1]
}

proc actual_pin_loads {net} {
    return [llength [get_pins -quiet -leaf -of_objects $net \
        -filter {DIRECTION == IN}]]
}

proc property_is_true {object property_name} {
    set value [string tolower [get_property $property_name $object]]
    return [expr {$value eq "1" || $value eq "true" || $value eq "yes"}]
}

proc audit_mlp_local_clear {branches} {
    require_count mlp_local_clear_branch_roots $branches 2
    set all_clear_ff {}
    set protected_count 0
    set branch_counts {}
    foreach branch [lsort -dictionary $branches] {
        set clear_ff [named_descendants_of_glob [list $branch] FD* \
            clear_local_r_reg*]
        require_count mlp_local_clear_ff_per_branch $clear_ff 1
        lappend branch_counts [llength $clear_ff]
        foreach cell $clear_ff {
            if {![property_is_true $cell DONT_TOUCH]} {
                error "MLP local clear FF lost DONT_TOUCH: $cell"
            }
            incr protected_count
        }
        set all_clear_ff [concat $all_clear_ff $clear_ff]
    }
    set all_clear_ff [lsort -dictionary -unique $all_clear_ff]
    require_count mlp_local_clear_ff $all_clear_ff 2
    if {$protected_count != 2} {
        error "mlp_local_clear_protected_ff count mismatch: expected=2 actual=$protected_count"
    }
    return [list [llength $all_clear_ff] $protected_count \
        [lindex $branch_counts 0] [lindex $branch_counts 1]]
}

proc audit_swiglu_local_clear {frontends row_leaves} {
    require_count swiglu_clear_frontend $frontends 1
    require_count swiglu_clear_row_leaves $row_leaves 2
    set control [named_descendants_of_glob $frontends FD* \
        control_clear_local_r_reg*]
    set hadamard [named_descendants_of_glob $frontends FD* \
        hadamard_clear_local_r_reg*]
    set quantizer [named_descendants_of_glob $frontends FD* \
        quantizer_clear_local_r_reg*]
    require_count swiglu_control_clear_ff $control 1
    require_count swiglu_hadamard_clear_ff $hadamard 1
    require_count swiglu_quantizer_clear_ff $quantizer 4
    set row_candidates [get_cells -quiet -hierarchical -filter {
        NAME =~ */clear_local_r_reg* && REF_NAME =~ FD*}]
    set row_clear {}
    foreach leaf [lsort -dictionary $row_leaves] {
        set prefix "[get_property NAME $leaf]/"
        set local {}
        foreach cell $row_candidates {
            if {[string first $prefix [get_property NAME $cell]] == 0} {
                lappend local $cell
            }
        }
        require_count swiglu_row_clear_ff_per_leaf $local 1
        set row_clear [concat $row_clear $local]
    }
    set row_clear [lsort -dictionary -unique $row_clear]
    require_count swiglu_row_clear_ff $row_clear 2
    set all_clear [lsort -dictionary -unique \
        [concat $control $hadamard $quantizer $row_clear]]
    require_count swiglu_local_clear_ff $all_clear 8
    set protected 0
    foreach cell $all_clear {
        if {![property_is_true $cell DONT_TOUCH]} {
            error "SwiGLU local clear FF lost DONT_TOUCH: $cell"
        }
        incr protected
    }
    if {$protected != 8} {
        error "swiglu_local_clear_protected_ff count mismatch: expected=8 actual=$protected"
    }
    set d_pins [get_pins -quiet -of_objects $all_clear -filter \
        {REF_PIN_NAME == D}]
    require_count swiglu_local_clear_d_pins $d_pins 8
    set clear_nets [lsort -dictionary -unique \
        [get_nets -quiet -of_objects $d_pins]]
    set direct_cells [cells_below_roots $frontends \
        [lsort -dictionary -unique [get_cells -quiet -of_objects \
            [get_pins -quiet -leaf -of_objects $clear_nets -filter \
                {DIRECTION == IN}]]]]
    set bypass {}
    foreach cell $direct_cells {
        if {[lsearch -exact $all_clear $cell] < 0} {
            lappend bypass $cell
        }
    }
    set bypass [lsort -dictionary -unique $bypass]
    require_count swiglu_direct_clear_bypass_state $bypass 0
    return [list [llength $all_clear] $protected \
        [llength $control] [llength $hadamard] [llength $quantizer] \
        [llength $row_clear] [llength $clear_nets] [llength $bypass]]
}

proc audit_mlp_central_clear_boundary {branches} {
    set central [get_cells -quiet -hierarchical -filter {
        NAME =~ */maintenance_soft_clear_pulse_r_reg && REF_NAME =~ FD*}]
    require_count mlp_central_clear_ff $central 1
    set q [get_pins -quiet -of_objects $central -filter \
        {REF_PIN_NAME == Q}]
    require_count mlp_central_clear_q $q 1
    set endpoint_pins [all_fanout -flat -endpoints_only -from $q]
    set endpoint_cells [lsort -dictionary -unique \
        [get_cells -quiet -of_objects $endpoint_pins]]
    set clear_ff {}
    foreach branch $branches {
        set clear_ff [concat $clear_ff \
            [named_descendants_of_glob [list $branch] FD* \
                clear_local_r_reg*]]
    }
    set clear_ff [lsort -dictionary -unique $clear_ff]
    set clear_endpoints {}
    foreach cell $clear_ff {
        if {[lsearch -exact $endpoint_cells $cell] >= 0} {
            lappend clear_endpoints $cell
        }
    }
    set clear_endpoints [lsort -dictionary -unique $clear_endpoints]
    require_count mlp_central_clear_branch_endpoints $clear_endpoints 2

    # The central event also clears system-level Attention/DMA controllers.
    # all_fanout therefore continues through the asynchronous preset arc of
    # clear_local_r_reg and reports the branch state cleared by its Q.  That
    # transitive set cannot distinguish a bypass.  Check the central Q net's
    # direct leaf sinks instead: neither MLP branch may consume it directly.
    set central_nets [lsort -dictionary -unique \
        [get_nets -quiet -of_objects $q]]
    require_count mlp_central_clear_net $central_nets 1
    set direct_sink_pins [get_pins -quiet -leaf -of_objects $central_nets \
        -filter {DIRECTION == IN}]
    set direct_sink_cells [lsort -dictionary -unique \
        [get_cells -quiet -of_objects $direct_sink_pins]]
    set direct_branch_state \
        [cells_below_roots $branches $direct_sink_cells]
    require_count mlp_central_clear_direct_branch_state $direct_branch_state 0
    return [list [llength $central] [llength $clear_endpoints] \
        [llength $direct_branch_state]]
}

proc audit_metadata_local_write_boundaries {} {
    set leaves [get_cells -quiet -hierarchical -filter {
        REF_NAME == hap_mlp_weight_meta_uram_leaf ||
        ORIG_REF_NAME == hap_mlp_weight_meta_uram_leaf}]
    require_count metadata_leaf_instances $leaves 4
    set wr_en [get_cells -quiet -hierarchical -filter {
        NAME =~ */wr_en_local_r_reg* && REF_NAME =~ FD*}]
    set wr_addr [get_cells -quiet -hierarchical -filter {
        NAME =~ */wr_addr_local_r_reg* && REF_NAME =~ FD*}]
    set wr_data [get_cells -quiet -hierarchical -filter {
        NAME =~ */wr_data_local_r_reg* && REF_NAME =~ FD*}]
    require_count metadata_local_wr_en_ff $wr_en 4
    require_count metadata_local_wr_addr_ff $wr_addr 70
    require_count metadata_local_wr_data_ff $wr_data 896
    set protected 0
    foreach cell [concat $wr_en $wr_addr $wr_data] {
        if {![property_is_true $cell DONT_TOUCH]} {
            error "Metadata local write FF lost DONT_TOUCH: $cell"
        }
        incr protected
    }
    if {$protected != 970} {
        error "metadata_local_write_protected_ff count mismatch: expected=970 actual=$protected"
    }
    return [list [llength $leaves] [llength $wr_en] [llength $wr_addr] \
        [llength $wr_data] $protected]
}

proc audit_mlp_ingress_capture_leaves {branches} {
    require_count mlp_capture_leaf_branches $branches 2
    set leaves [get_cells -quiet -hierarchical -filter {
        REF_NAME == hap_a8w4_ingress_capture_leaf ||
        ORIG_REF_NAME == hap_a8w4_ingress_capture_leaf}]
    require_count mlp_capture_leaf_instances $leaves 1632
    set branch_leaf_counts {}
    set branch_lut_counts {}
    set total_lut 0
    foreach branch [lsort -dictionary $branches] {
        set branch_leaves [cells_below_roots [list $branch] $leaves]
        set branch_lut [named_descendants_of_glob [list $branch] LUT1 \
            */u_leaf]
        require_count mlp_capture_leaf_instances_per_branch $branch_leaves 816
        require_count mlp_capture_leaf_lut1_per_branch $branch_lut 816
        lappend branch_leaf_counts [llength $branch_leaves]
        lappend branch_lut_counts [llength $branch_lut]
        incr total_lut [llength $branch_lut]
    }
    if {$total_lut != 1632} {
        error "mlp_capture_leaf_lut1 count mismatch: expected=1632 actual=$total_lut"
    }
    return [list [llength $leaves] $total_lut \
        [lindex $branch_leaf_counts 0] [lindex $branch_leaf_counts 1] \
        [lindex $branch_lut_counts 0] [lindex $branch_lut_counts 1]]
}

proc classify_bufg {} {
    set clock_count 0
    set data_count 0
    foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}] {
        set outputs [get_pins -quiet -of_objects $cell -filter \
            {DIRECTION == OUT}]
        if {[llength [get_clocks -quiet -of_objects $outputs]] != 0} {
            incr clock_count
        } else {
            incr data_count
        }
    }
    return [list $clock_count $data_count]
}

proc audit_compact_input_capture {roots} {
    require_count compact_input_root $roots 1
    set root_name [get_property NAME [lindex $roots 0]]
    set row_ff [named_descendants_of_glob $roots FD* \
        input_buffer_row_r_reg*]
    set leaves [named_descendants_of_glob $roots LUT1 \
        *u_input_capture_enable]
    require_count compact_input_payload_ff $row_ff 12288
    require_count compact_input_capture_leaf $leaves 48
    set row_ce_pins [get_pins -quiet -of_objects $row_ff -filter \
        {REF_PIN_NAME == CE}]
    require_count compact_input_payload_ce_pin $row_ce_pins 12288
    set nets [lsort -dictionary -unique \
        [get_nets -quiet -of_objects $row_ce_pins]]
    require_count compact_input_capture_unique_net $nets 48
    set local_drivers {}
    set min_load 1000000000
    set max_load 0
    foreach leaf $leaves {
        set output [get_pins -quiet -of_objects $leaf -filter \
            {DIRECTION == OUT}]
        require_count compact_input_protected_leaf_output $output 1
        set net [get_nets -quiet -of_objects $output]
        require_count compact_input_protected_leaf_net $net 1
        require_count compact_input_protected_leaf_load \
            [get_pins -quiet -leaf -of_objects $net -filter \
                {DIRECTION == IN}] 1
    }
    foreach net $nets {
        set ce_pins [get_pins -quiet -leaf -of_objects $net -filter \
            "REF_PIN_NAME == CE && \
             NAME =~ ${root_name}/input_buffer_row_r_reg*"]
        require_count compact_input_capture_ce_load $ce_pins 256
        require_count compact_input_capture_all_load \
            [get_pins -quiet -leaf -of_objects $net -filter \
                {DIRECTION == IN}] 256
        set driver_pin [get_pins -quiet -leaf -of_objects $net -filter \
            {DIRECTION == OUT}]
        require_count compact_input_capture_driver_pin $driver_pin 1
        set driver [get_cells -quiet -of_objects $driver_pin]
        require_count compact_input_capture_driver $driver 1
        if {![string match "LUT*" [get_property REF_NAME $driver]]} {
            error "compact input CE driver is not local LUT logic: $driver"
        }
        lappend local_drivers $driver
        set loads [llength $ce_pins]
        if {$loads < $min_load} {set min_load $loads}
        if {$loads > $max_load} {set max_load $loads}
    }
    require_count compact_input_capture_local_driver \
        [lsort -dictionary -unique $local_drivers] 48
    return [list [llength $row_ff] [llength $leaves] $min_load $max_load]
}

proc audit_down_activation_capture {roots} {
    require_count down_activation_root $roots 1
    set owners [named_descendants_of_glob $roots FD* \
        output_capture_pending_bank_r_reg*]
    require_count down_activation_capture_owner $owners 16
    set owner_nets {}
    set all_payload_pins {}
    set min_load 1000000000
    set max_load 0
    foreach owner $owners {
        set q [get_pins -quiet -of_objects $owner -filter \
            {REF_PIN_NAME == Q}]
        require_count down_activation_capture_owner_q $q 1
        set owner_net [get_nets -quiet -of_objects $q]
        require_count down_activation_capture_owner_net $owner_net 1
        lappend owner_nets $owner_net
        set owner_loads [get_pins -quiet -leaf -of_objects $owner_net \
            -filter {DIRECTION == IN}]
        require_count down_activation_capture_owner_load $owner_loads 1
        set local_driver [get_cells -quiet -of_objects $owner_loads]
        require_count down_activation_capture_local_driver $local_driver 1
        if {![string match "LUT*" [get_property REF_NAME $local_driver]]} {
            error "down activation capture local driver is not a LUT: $local_driver"
        }
        set local_output [get_pins -quiet -of_objects $local_driver \
            -filter {DIRECTION == OUT}]
        require_count down_activation_capture_local_output $local_output 1
        set local_net [get_nets -quiet -of_objects $local_output]
        require_count down_activation_capture_local_net $local_net 1
        set payload_pins [get_pins -quiet -leaf -of_objects $local_net \
            -filter {DIRECTION == IN}]
        require_count down_activation_capture_payload_load $payload_pins 280
        set all_payload_pins [concat $all_payload_pins $payload_pins]
        set loads [llength $payload_pins]
        if {$loads < $min_load} {set min_load $loads}
        if {$loads > $max_load} {set max_load $loads}
    }
    require_count down_activation_capture_unique_owner_net \
        [lsort -dictionary -unique $owner_nets] 16
    set payload_ff [lsort -dictionary -unique \
        [get_cells -quiet -of_objects $all_payload_pins]]
    require_count down_activation_capture_payload_ff $payload_ff 4480
    return [list [llength $owners] [llength $payload_ff] \
        $min_load $max_load]
}

proc audit_gate_accum_controls {roots} {
    require_count gate_accum_root $roots 2
    set all_leaves {}
    set all_owners {}
    set gate_control_min 1000000000
    set gate_control_max 0
    set finalize_min 1000000000
    set finalize_max 0
    foreach root $roots {
        set leaves [named_descendants_of_glob [list $root] LUT1 \
            *u_accum_write_enable]
        set owners [named_descendants_of_glob [list $root] FD* \
            finalize_pending_bank_r_reg*]
        require_count gate_accum_write_leaf_per_root $leaves 8
        require_count gate_accum_finalize_owner_per_root $owners 8
        set all_leaves [concat $all_leaves $leaves]
        set all_owners [concat $all_owners $owners]
        foreach leaf $leaves {
            set output [get_pins -quiet -of_objects $leaf -filter \
                {DIRECTION == OUT}]
            require_count gate_accum_write_output $output 1
            set net [get_nets -quiet -of_objects $output]
            require_count gate_accum_write_net $net 1
            set loads [actual_pin_loads $net]
            if {$loads <= 0 || $loads > 600} {
                error "gate accumulator write-bank load out of range: $loads"
            }
            if {$loads < $gate_control_min} {set gate_control_min $loads}
            if {$loads > $gate_control_max} {set gate_control_max $loads}
        }
        foreach owner $owners {
            set q [get_pins -quiet -of_objects $owner -filter \
                {REF_PIN_NAME == Q}]
            require_count gate_accum_finalize_q $q 1
            set net [get_nets -quiet -of_objects $q]
            require_count gate_accum_finalize_net $net 1
            set loads [actual_pin_loads $net]
            if {$loads <= 0 || $loads > 400} {
                error "gate accumulator finalize-bank load out of range: $loads"
            }
            if {$loads < $finalize_min} {set finalize_min $loads}
            if {$loads > $finalize_max} {set finalize_max $loads}
        }
    }
    require_count gate_accum_write_leaf_total \
        [lsort -dictionary -unique $all_leaves] 16
    require_count gate_accum_finalize_owner_total \
        [lsort -dictionary -unique $all_owners] 16
    return [list 16 $gate_control_min $gate_control_max \
        16 $finalize_min $finalize_max]
}

proc audit_protected_capture_banks {roots relative_glob expected_loads \
        expected_total_ff label} {
    require_count ${label}_root $roots 2
    set all_leaves {}
    set all_ce_pins {}
    set all_nets {}
    set min_load 1000000000
    set max_load 0
    foreach root $roots {
        set leaves [named_descendants_of_glob [list $root] LUT1 \
            $relative_glob]
        require_count ${label}_leaf_per_root $leaves 8
        set all_leaves [concat $all_leaves $leaves]
        foreach leaf $leaves {
            set output [get_pins -quiet -of_objects $leaf -filter \
                {DIRECTION == OUT}]
            require_count ${label}_output $output 1
            set net [get_nets -quiet -of_objects $output]
            require_count ${label}_net $net 1
            lappend all_nets $net
            set ce_pins [get_pins -quiet -leaf -of_objects $net -filter \
                {REF_PIN_NAME == CE}]
            require_count ${label}_ce_load $ce_pins $expected_loads
            require_count ${label}_all_load \
                [get_pins -quiet -leaf -of_objects $net -filter \
                    {DIRECTION == IN}] $expected_loads
            set all_ce_pins [concat $all_ce_pins $ce_pins]
            set loads [llength $ce_pins]
            if {$loads < $min_load} {set min_load $loads}
            if {$loads > $max_load} {set max_load $loads}
        }
    }
    require_count ${label}_leaf_total \
        [lsort -dictionary -unique $all_leaves] 16
    require_count ${label}_unique_net \
        [lsort -dictionary -unique $all_nets] 16
    set capture_ff [lsort -dictionary -unique \
        [get_cells -quiet -of_objects $all_ce_pins]]
    require_count ${label}_capture_ff $capture_ff $expected_total_ff
    return [list 16 [llength $capture_ff] $min_load $max_load]
}

proc audit_serial_reset_domains {roots} {
    require_count serial_reset_root $roots 1
    set reset_cells {}
    set protected_cells 0
    foreach relative_name {u_control_reset u_gate_metrics_reset \
            u_down_metrics_reset} {
        set cells [named_descendants_of_glob $roots LUT2 $relative_name]
        require_count serial_reset_$relative_name $cells 1
        set cell [lindex $cells 0]
        lappend reset_cells $cell
        if {[property_is_true $cell DONT_TOUCH]} {incr protected_cells}
        set output [get_pins -quiet -of_objects $cell -filter \
            {DIRECTION == OUT}]
        require_count serial_reset_${relative_name}_output $output 1
        require_count serial_reset_${relative_name}_net \
            [get_nets -quiet -of_objects $output] 1
    }
    require_count serial_reset_domain_total \
        [lsort -dictionary -unique $reset_cells] 3
    if {$protected_cells != 3} {
        error "serial reset DONT_TOUCH count mismatch: expected=3 actual=$protected_cells"
    }
    return [list 3 $protected_cells]
}

proc audit_attention_region2_elastic_fifo {region2 dual_accumulators} {
    require_count attention_region2_root $region2 1
    require_count attention_dual_accumulator_roots $dual_accumulators 6

    set region2_accumulators \
        [cells_below_roots $region2 $dual_accumulators]
    require_count attention_region2_dual_accumulator \
        $region2_accumulators 1

    set buffered_accumulators {}
    foreach accumulator $dual_accumulators {
        set buffered_ff [named_descendants_of_glob [list $accumulator] FD* \
            *g_buffered_input*]
        if {[llength $buffered_ff] != 0} {
            lappend buffered_accumulators $accumulator
        }
    }
    set buffered_accumulators \
        [lsort -dictionary -unique $buffered_accumulators]
    require_count attention_buffered_dual_accumulator \
        $buffered_accumulators 1
    if {[get_property NAME [lindex $buffered_accumulators 0]] ne \
            [get_property NAME [lindex $region2_accumulators 0]]} {
        error "The unique buffered Attention accumulator is not region2"
    }

    set accumulator [lindex $buffered_accumulators 0]
    set accumulator_name [get_property NAME $accumulator]
    set lower_banks [get_cells -quiet -hierarchical -filter \
        "NAME =~ ${accumulator_name}/*u_lower_bank && \
         (REF_NAME == hap_linear_tile_accum_dual_s42_bank || \
          ORIG_REF_NAME == hap_linear_tile_accum_dual_s42_bank)"]
    set upper_banks [get_cells -quiet -hierarchical -filter \
        "NAME =~ ${accumulator_name}/*u_upper_bank && \
         (REF_NAME == hap_linear_tile_accum_dual_s42_bank || \
          ORIG_REF_NAME == hap_linear_tile_accum_dual_s42_bank)"]
    require_count attention_region2_lower_bank $lower_banks 1
    require_count attention_region2_upper_bank $upper_banks 1

    set buffer_prefix "${accumulator_name}/*g_buffered_input"
    set buffer_primitives [lsort -dictionary -unique \
        [get_cells -quiet -hierarchical -filter \
        "IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL && \
         REF_NAME != GND && REF_NAME != VCC && \
         NAME =~ ${buffer_prefix}*"]]
    set buffer_ffs [named_descendants_of_glob [list $accumulator] FD* \
        *g_buffered_input*]
    set payload_ffs [named_descendants_of_glob [list $accumulator] FD* \
        *g_buffered_input*guard_s42_r_reg*]
    set occupancy_ffs [named_descendants_of_glob [list $accumulator] FD* \
        *g_buffered_input*buffer_count_r_reg*]
    set tag_ffs {}
    foreach stem {wave first last} {
        set tag_ffs [concat $tag_ffs \
            [named_descendants_of_glob [list $accumulator] FD* \
                *g_buffered_input*${stem}_r_reg*]]
    }
    set tag_ffs [lsort -dictionary -unique $tag_ffs]
    set classified_ffs [lsort -dictionary -unique \
        [concat $payload_ffs $tag_ffs $occupancy_ffs]]

    if {[llength $buffer_primitives] == 0 || [llength $buffer_ffs] == 0} {
        error "Attention region2 g_buffered_input has no synthesized state"
    }
    if {[llength $payload_ffs] == 0} {
        error "Attention region2 FIFO payload state is missing"
    }
    if {[llength $tag_ffs] == 0} {
        error "Attention region2 FIFO tag state is missing"
    }
    require_count attention_region2_fifo_occupancy_ff $occupancy_ffs 2
    if {[llength $classified_ffs] != [llength $buffer_ffs]} {
        error "Attention region2 FIFO FF partition mismatch: classified=[llength $classified_ffs] total=[llength $buffer_ffs]"
    }

    return [dict create region2_instances [llength $region2] \
        region2_accumulators [llength $region2_accumulators] \
        buffered_accumulators [llength $buffered_accumulators] \
        lower_banks [llength $lower_banks] \
        upper_banks [llength $upper_banks] \
        g_buffered_input_present 1 \
        buffer_primitives [llength $buffer_primitives] \
        buffer_ff [llength $buffer_ffs] \
        payload_ff [llength $payload_ffs] \
        tag_ff [llength $tag_ffs] \
        occupancy_ff [llength $occupancy_ffs] \
        partition_ok 1 ok 1]
}

proc utilization_value {text pattern label} {
    if {![regexp $pattern $text unused value]} {
        error "Unable to parse $label from report_utilization"
    }
    return $value
}

proc collect_owner_metrics {roots label boundary_handle} {
    require_count ${label}_owner $roots 1
    set root [lindex $roots 0]
    set pins [lsort -dictionary [get_pins -quiet -of_objects $root]]
    set input_pins [lsort -dictionary [get_pins -quiet -of_objects $root \
        -filter {DIRECTION == IN}]]
    set output_pins [lsort -dictionary [get_pins -quiet -of_objects $root \
        -filter {DIRECTION == OUT}]]
    if {[llength $pins] == 0 || [llength $input_pins] == 0 ||
        [llength $output_pins] == 0} {
        error "$label has an empty hierarchical boundary"
    }
    set boundary_nets [lsort -dictionary -unique \
        [get_nets -quiet -of_objects $pins]]
    if {[llength $boundary_nets] == 0} {
        error "$label has no boundary nets"
    }
    foreach pin $pins {
        set pin_nets [lsort -dictionary -unique \
            [get_nets -quiet -of_objects $pin]]
        puts $boundary_handle [join [list $label \
            [get_property NAME $root] [get_property DIRECTION $pin] \
            [get_property NAME $pin] [llength $pin_nets] \
            [join $pin_nets ,]] "\t"]
    }

    set lutram [lsort -dictionary -unique [concat \
        [descendants_of_glob $roots RAMD*] \
        [descendants_of_glob $roots RAMS*]]]
    return [dict create \
        instances [llength $roots] \
        lut [llength [descendants_of_glob $roots LUT*]] \
        srl16e [llength [descendants_of_type $roots SRL16E]] \
        ff [llength [descendants_of_glob $roots FD*]] \
        ramb36 [llength [descendants_of_type $roots RAMB36E2]] \
        ramb18 [llength [descendants_of_type $roots RAMB18E2]] \
        lutram [llength $lutram] \
        dsp [llength [descendants_of_type $roots DSP48E2]] \
        uram [llength [descendants_of_type $roots URAM288]] \
        input_pins [llength $input_pins] \
        output_pins [llength $output_pins] \
        boundary_nets [llength $boundary_nets]]
}

open_checkpoint $dcp
set design_top [get_property TOP [current_design]]
set design_part [get_property PART [current_design]]
if {$design_top ne "hap_attention_mlp_production_core"} {
    error "Unexpected V5 post-opt top: $design_top"
}
if {$design_part ne "xcvu9p-flga2104-2L-e"} {
    error "Unexpected V5 post-opt part: $design_part"
}

set v5_serial [cells_of_module hap_mlp_serial_ddr_command16_v5_s46]
set old_serial [cells_of_module hap_mlp_serial_ddr_command16_s45]
set v5_shared [cells_of_module hap_mlp_shared_dual_slice16x12_s44_s46]
set v5_branches [lsort -dictionary \
    [cells_of_module hap_mlp_shared_local_slice8x12_s44_s46]]
set v5_kernels [lsort -dictionary \
    [cells_of_module hap_a8w4_slice8x12_group_s37]]
set old_kernels [cells_of_module hap_a8w4_slice8x16_group_s36]
set history2_repack \
    [cells_of_module hap_mlp_projection_repack12_to16_s24_history2]
set generic_repack \
    [cells_of_module hap_mlp_projection_repack12_to16_s24]
set swiglu_frontend \
    [cells_of_module hap_mlp_swiglu_product_frontend16_q4]
set swiglu_row_leaf [cells_of_module hap_mlp_swiglu_row_stream8_q4]
set swiglu_hadamard \
    [cells_of_module hap_mlp_hadamard32_s32_norm_stream]
set swiglu_fold2 \
    [cells_of_module hap_mlp_hadamard32_s32_norm_fold2]
set swiglu_quantizer \
    [cells_of_module hap_mlp_robust_a8_quantizer_s35]
set swiglu_silu [cells_of_module hap_mlp_silu_mul]
set attention_col3_array \
    [cells_of_module hap_a8w8_array_16x16_s42_col3]
set attention_old_array \
    [cells_of_module hap_a8w8_array_16x16_s42]
set attention_left_shard \
    [cells_of_module hap_a8w8_col_shard_left2_s42]
set attention_center_shard \
    [cells_of_module hap_a8w8_col_shard_center12_s42]
set attention_right_shard \
    [cells_of_module hap_a8w8_col_shard_right2_s42]
set attention_leaf_shards \
    [cells_of_module hap_a8w8_col_shard_s42]
set attention_cohort16_board \
    [cells_of_module hap_attention_board_cohort16_core]
set attention_legacy_board [cells_of_module hap_attention_board_core]
set attention_cohort16_compute \
    [cells_of_module hap_attention_compute_cohort16_top]
set attention_query_store \
    [cells_of_module hap_attention_cohort16_query_store]
set attention_postprocess_store \
    [cells_of_module hap_attention_cohort16_postprocess_store]
set attention_postprocess_row_banks \
    [cells_of_module hap_attention_cohort16_postprocess_row_bank]
set attention_context_store \
    [cells_of_module hap_attention_cohort16_context_store]
set attention_legacy_compute [cells_of_module hap_attention_compute_top]
set attention_projection16 \
    [cells_of_module hap_projection_core16x16_w8_reuse]
set attention_projection8 [cells_of_module hap_projection_core8x16]
set attention_frontend [cells_of_module hap_attention_frontend_8row]
set attention_lanes [cells_of_module hap_a8w8_group32_lane_s42]
set attention_dual_accumulators \
    [cells_of_module hap_linear_tile_accum_dual_s42]
set attention_local_contexts [expr {2 *
    [llength $attention_dual_accumulators]}]
set attention_region2 [get_cells -quiet -hierarchical -filter {
    NAME =~ */u_center12/u_region2_cols8_11 &&
    (REF_NAME == hap_a8w8_col_shard_s42 ||
     ORIG_REF_NAME == hap_a8w8_col_shard_s42)}]
set compact_input_frontend \
    [cells_of_module hap_mlp_input_frontend16_compact_cache]
set down_activation_cache \
    [cells_of_module hap_mlp_down_activation_cache16]
set gate_accums [cells_of_module hap_mlp_tile_accum_s37]
set down_accums [cells_of_module hap_mlp_down_group_major_accum_s46]
set down_elastic2 \
    [cells_of_module hap_mlp_down_branch_elastic2_s24_v6]

set attention_center_subshards \
    [cells_below_roots $attention_center_shard $attention_leaf_shards]
set attention_left_leaf_shards \
    [cells_below_roots $attention_left_shard $attention_leaf_shards]
set attention_right_leaf_shards \
    [cells_below_roots $attention_right_shard $attention_leaf_shards]

set projection_weight_capture \
    [audit_projection_weight_capture $attention_projection16]
set attention_region2_fifo [audit_attention_region2_elastic_fifo \
    $attention_region2 $attention_dual_accumulators]
lassign [audit_compact_input_capture $compact_input_frontend] \
    compact_capture_ff compact_capture_controls \
    compact_capture_min compact_capture_max
lassign [audit_down_activation_capture $down_activation_cache] \
    down_activation_capture_owners down_activation_capture_ff \
    down_activation_capture_min down_activation_capture_max
lassign [audit_gate_accum_controls $gate_accums] \
    gate_write_controls gate_write_min gate_write_max \
    gate_finalize_owners gate_finalize_min gate_finalize_max
lassign [audit_protected_capture_banks $down_accums \
    *u_guard_capture_enable 444 7104 down_guard_capture] \
    down_guard_controls down_guard_ff down_guard_min down_guard_max
lassign [audit_protected_capture_banks $down_accums \
    *u_output_capture_enable 288 4608 down_output_capture] \
    down_output_controls down_output_ff down_output_min down_output_max
lassign [audit_serial_reset_domains $v5_serial] \
    serial_reset_domains serial_reset_protected
lassign [audit_mlp_local_clear $v5_branches] \
    mlp_local_clear_ff mlp_local_clear_protected_ff \
    branch0_local_clear_ff branch1_local_clear_ff
lassign [audit_swiglu_local_clear $swiglu_frontend $swiglu_row_leaf] \
    swiglu_local_clear_ff swiglu_local_clear_protected_ff \
    swiglu_control_clear_ff swiglu_hadamard_clear_ff \
    swiglu_quantizer_clear_ff swiglu_row_clear_ff \
    swiglu_clear_input_nets swiglu_direct_clear_bypass_state
lassign [audit_mlp_central_clear_boundary $v5_branches] \
    mlp_central_clear_ff mlp_central_clear_branch_endpoints \
    mlp_central_clear_direct_branch_state
lassign [audit_metadata_local_write_boundaries] \
    metadata_leaf_instances metadata_local_wr_en_ff \
    metadata_local_wr_addr_ff metadata_local_wr_data_ff \
    metadata_local_write_protected_ff
lassign [audit_mlp_ingress_capture_leaves $v5_branches] \
    mlp_capture_leaf_instances mlp_capture_leaf_lut1 \
    branch0_capture_leaf_instances branch1_capture_leaf_instances \
    branch0_capture_leaf_lut1 branch1_capture_leaf_lut1
lassign [classify_bufg] clock_bufg data_bufg

set owner_boundary_handle \
    [open [file join $out attention_local_store_boundaries.tsv] w]
puts $owner_boundary_handle \
    "owner\troot\tdirection\tpin\tnet_count\tnets"
set query_store_metrics [collect_owner_metrics $attention_query_store \
    query_store $owner_boundary_handle]
set postprocess_store_metrics [collect_owner_metrics \
    $attention_postprocess_store postprocess_store $owner_boundary_handle]
set context_store_metrics [collect_owner_metrics $attention_context_store \
    context_store $owner_boundary_handle]
close $owner_boundary_handle

set owner_resource_handle \
    [open [file join $out attention_local_store_resources.tsv] w]
puts $owner_resource_handle \
    "owner\tinstances\tlut\tsrl16e\tff\tramb36\tramb18\tlutram\tdsp\turam\tinput_pins\toutput_pins\tboundary_nets"
foreach {owner metrics} [list query_store $query_store_metrics \
        postprocess_store $postprocess_store_metrics \
        context_store $context_store_metrics] {
    puts $owner_resource_handle [join [list $owner \
        [dict get $metrics instances] [dict get $metrics lut] \
        [dict get $metrics srl16e] [dict get $metrics ff] \
        [dict get $metrics ramb36] [dict get $metrics ramb18] \
        [dict get $metrics lutram] [dict get $metrics dsp] \
        [dict get $metrics uram] [dict get $metrics input_pins] \
        [dict get $metrics output_pins] \
        [dict get $metrics boundary_nets]] "\t"]
}
close $owner_resource_handle

set total_dsp [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == DSP48E2}]]
set total_uram [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == URAM288}]]
set total_ramb36 [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == RAMB36E2}]]
set total_ramb18 [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == RAMB18E2}]]
set kernel_dsp_cells [descendants_of_type $v5_kernels DSP48E2]
set kernel_dsp [llength $kernel_dsp_cells]
set attention_projection_dsp [llength \
    [descendants_of_type $attention_projection16 DSP48E2]]
set attention_array_dsp [llength \
    [descendants_of_type $attention_col3_array DSP48E2]]
set attention_frontend_dsp [llength \
    [descendants_of_type $attention_frontend DSP48E2]]
set s27_quantizers [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_robust_a8_quantizer ||
    REF_NAME == hap_robust_a8_quantizer}]
set attention_s27_quantizers \
    [cells_below_roots $attention_frontend $s27_quantizers]
set compact_s27_quantizers \
    [cells_below_roots $compact_input_frontend $s27_quantizers]
set attention_quantizer_dsp [llength \
    [descendants_of_type $attention_s27_quantizers DSP48E2]]
set attention_base_frontend_dsp \
    [expr {$attention_frontend_dsp - $attention_quantizer_dsp}]
set compact_input_frontend_dsp [llength \
    [descendants_of_type $compact_input_frontend DSP48E2]]
set compact_input_quantizer_dsp [llength \
    [descendants_of_type $compact_s27_quantizers DSP48E2]]
set compact_input_base_frontend_dsp \
    [expr {$compact_input_frontend_dsp - $compact_input_quantizer_dsp}]
set swiglu_frontend_dsp [llength \
    [descendants_of_type $swiglu_frontend DSP48E2]]
set swiglu_hadamard_dsp [llength \
    [descendants_of_type $swiglu_hadamard DSP48E2]]
set swiglu_quantizer_dsp [llength \
    [descendants_of_type $swiglu_quantizer DSP48E2]]
set swiglu_silu_dsp [llength \
    [descendants_of_type $swiglu_silu DSP48E2]]
set swiglu_frontend_ramb36_cells \
    [descendants_of_type $swiglu_frontend RAMB36E2]
set swiglu_row_ring_ramb36_cells [named_descendants_of_glob \
    $swiglu_frontend RAMB36E2 *g_row_ring_column*]
set swiglu_silu_ramb36_cells \
    [descendants_of_type $swiglu_silu RAMB36E2]
set swiglu_recognized_ramb36_cells [lsort -dictionary -unique \
    [concat $swiglu_row_ring_ramb36_cells $swiglu_silu_ramb36_cells]]
set swiglu_frontend_ramb36 [llength $swiglu_frontend_ramb36_cells]
set swiglu_row_ring_ramb36 [llength $swiglu_row_ring_ramb36_cells]
set swiglu_silu_ramb36 [llength $swiglu_silu_ramb36_cells]
set swiglu_other_ramb36 [expr {$swiglu_frontend_ramb36 -
    [llength $swiglu_recognized_ramb36_cells]}]
set swiglu_metadata_address_dsp_cells \
    [direct_children_of_type $swiglu_frontend DSP48E2]
set swiglu_metadata_address_dsp \
    [llength $swiglu_metadata_address_dsp_cells]
set swiglu_metadata_address_dsp_names {}
if {[llength $swiglu_frontend] == 1} {
    set swiglu_root_name [get_property NAME [lindex $swiglu_frontend 0]]
    foreach cell $swiglu_metadata_address_dsp_cells {
        set cell_name [get_property NAME $cell]
        lappend swiglu_metadata_address_dsp_names [string range $cell_name \
            [string length "${swiglu_root_name}/"] end]
    }
}
set swiglu_metadata_address_dsp_names \
    [lsort -dictionary $swiglu_metadata_address_dsp_names]
set swiglu_metadata_address_dsp_r1 0
set swiglu_metadata_address_dsp_r2 0
set swiglu_metadata_address_dsp_unexpected {}
foreach relative_name $swiglu_metadata_address_dsp_names {
    if {[regexp {^activation_meta_r1(__[0-9]+)*$} $relative_name]} {
        incr swiglu_metadata_address_dsp_r1
    } elseif {[regexp {^activation_meta_r2(__[0-9]+)*$} $relative_name]} {
        incr swiglu_metadata_address_dsp_r2
    } else {
        lappend swiglu_metadata_address_dsp_unexpected $relative_name
    }
}
set swiglu_metadata_address_dsp_identity_ok [expr {
    $swiglu_metadata_address_dsp == 4 &&
    $swiglu_metadata_address_dsp_r1 == 3 &&
    $swiglu_metadata_address_dsp_r2 == 1 &&
    [llength $swiglu_metadata_address_dsp_unexpected] == 0
}]
set swiglu_other_dsp [expr {
    $swiglu_frontend_dsp - $swiglu_hadamard_dsp -
    $swiglu_quantizer_dsp - $swiglu_silu_dsp -
    $swiglu_metadata_address_dsp
}]
set branch_dsp_counts {}
foreach branch $v5_branches {
    lappend branch_dsp_counts \
        [llength [descendants_of_type [list $branch] DSP48E2]]
}
set branch0_dsp [expr {[llength $branch_dsp_counts] == 2 ?
    [lindex $branch_dsp_counts 0] : -1}]
set branch1_dsp [expr {[llength $branch_dsp_counts] == 2 ?
    [lindex $branch_dsp_counts 1] : -1}]

set util [report_utilization -return_string]
set clb_lut [utilization_value $util \
    {\| CLB LUTs\*?\s+\|\s*([0-9]+)} "CLB LUTs"]
set lut_logic [utilization_value $util \
    {\|\s*LUT as Logic\s+\|\s*([0-9]+)} "LUT as Logic"]
set lut_memory [utilization_value $util \
    {\|\s*LUT as Memory\s+\|\s*([0-9]+)} "LUT as Memory"]
set clb_ff [utilization_value $util \
    {\| CLB Registers\s+\|\s*([0-9]+)} "CLB Registers"]

report_utilization -file [file join $out utilization_reopen.rpt]
report_utilization -hierarchical -hierarchical_depth 12 \
    -file [file join $out utilization_hier_reopen.rpt]

set hierarchy_ok [expr {
    [llength $v5_serial] == 1 && [llength $old_serial] == 0 &&
    [llength $v5_shared] == 1 && [llength $v5_branches] == 2 &&
    [llength $v5_kernels] == 2 && [llength $old_kernels] == 0 &&
    [llength $history2_repack] == 2 && [llength $generic_repack] == 0
    && [llength $swiglu_frontend] == 1
    && [llength $swiglu_row_leaf] == 2
    && [llength $swiglu_hadamard] == 1
    && [llength $swiglu_fold2] == 0
    && [llength $swiglu_quantizer] == 4
    && [llength $swiglu_silu] == 2
    && [llength $attention_cohort16_board] == 1
    && [llength $attention_legacy_board] == 0
    && [llength $attention_cohort16_compute] == 1
    && [llength $attention_legacy_compute] == 0
    && [llength $attention_query_store] == 1
    && [llength $attention_postprocess_store] == 1
    && [llength $attention_postprocess_row_banks] == 16
    && [llength $attention_context_store] == 1
    && [llength $attention_projection16] == 1
    && [llength $attention_projection8] == 0
    && [llength $attention_frontend] == 1
    && [llength $attention_lanes] == 128
    && [llength $attention_dual_accumulators] == 6
    && $attention_local_contexts == 12
    && [dict get $attention_region2_fifo region2_instances] == 1
    && [dict get $attention_region2_fifo region2_accumulators] == 1
    && [dict get $attention_region2_fifo buffered_accumulators] == 1
    && [dict get $attention_region2_fifo lower_banks] == 1
    && [dict get $attention_region2_fifo upper_banks] == 1
    && [llength $attention_col3_array] == 1
    && [llength $attention_old_array] == 0
    && [llength $attention_left_shard] == 1
    && [llength $attention_center_shard] == 1
    && [llength $attention_right_shard] == 1
    && [llength $attention_center_subshards] == 4
    && [llength $attention_left_leaf_shards] == 1
    && [llength $attention_right_leaf_shards] == 1
    && [llength $attention_leaf_shards] == 6
    && [llength $compact_input_frontend] == 1
    && [llength $s27_quantizers] == 12
    && [llength $attention_s27_quantizers] == 8
    && [llength $compact_s27_quantizers] == 4
    && [llength $down_activation_cache] == 1
    && [llength $gate_accums] == 2
    && [llength $down_accums] == 2
    && [llength $down_elastic2] == 2
}]
set protected_structure_ok [expr {
    [dict get $projection_weight_capture ok] == 1 &&
    [dict get $attention_region2_fifo g_buffered_input_present] == 1 &&
    [dict get $attention_region2_fifo buffer_primitives] > 0 &&
    [dict get $attention_region2_fifo buffer_ff] > 0 &&
    [dict get $attention_region2_fifo payload_ff] > 0 &&
    [dict get $attention_region2_fifo tag_ff] > 0 &&
    [dict get $attention_region2_fifo occupancy_ff] == 2 &&
    [dict get $attention_region2_fifo partition_ok] == 1 &&
    [dict get $attention_region2_fifo ok] == 1 &&
    [dict get $projection_weight_capture raw_loads] == 37 &&
    [dict get $projection_weight_capture data_nets] == 32 &&
    [dict get $projection_weight_capture data_min] == 256 &&
    [dict get $projection_weight_capture data_max] == 256 &&
    [dict get $projection_weight_capture meta_nets] == 2 &&
    [dict get $projection_weight_capture meta_min] == 256 &&
    [dict get $projection_weight_capture meta_max] == 256 &&
    [dict get $projection_weight_capture group_nets] == 2 &&
    [dict get $projection_weight_capture group_min] == 7 &&
    [dict get $projection_weight_capture group_max] == 7 &&
    $compact_capture_ff == 12288 &&
    $compact_capture_controls == 48 &&
    $compact_capture_min == 256 && $compact_capture_max == 256 &&
    $down_activation_capture_owners == 16 &&
    $down_activation_capture_ff == 4480 &&
    $down_activation_capture_min == 280 &&
    $down_activation_capture_max == 280 &&
    $gate_write_controls == 16 && $gate_finalize_owners == 16 &&
    $down_guard_controls == 16 && $down_guard_ff == 7104 &&
    $down_guard_min == 444 && $down_guard_max == 444 &&
    $down_output_controls == 16 && $down_output_ff == 4608 &&
    $down_output_min == 288 && $down_output_max == 288 &&
    $serial_reset_domains == 3 && $serial_reset_protected == 3 &&
    $mlp_local_clear_ff == 2 && $mlp_local_clear_protected_ff == 2 &&
    $branch0_local_clear_ff == 1 && $branch1_local_clear_ff == 1 &&
    $swiglu_local_clear_ff == 8 &&
    $swiglu_local_clear_protected_ff == 8 &&
    $swiglu_control_clear_ff == 1 && $swiglu_hadamard_clear_ff == 1 &&
    $swiglu_quantizer_clear_ff == 4 && $swiglu_row_clear_ff == 2 &&
    $swiglu_direct_clear_bypass_state == 0 &&
    $mlp_central_clear_ff == 1 &&
    $mlp_central_clear_branch_endpoints == 2 &&
    $mlp_central_clear_direct_branch_state == 0 &&
    $metadata_leaf_instances == 4 && $metadata_local_wr_en_ff == 4 &&
    $metadata_local_wr_addr_ff == 70 && $metadata_local_wr_data_ff == 896 &&
    $metadata_local_write_protected_ff == 970 &&
    $mlp_capture_leaf_instances == 1632 && $mlp_capture_leaf_lut1 == 1632 &&
    $branch0_capture_leaf_instances == 816 &&
    $branch1_capture_leaf_instances == 816 &&
    $branch0_capture_leaf_lut1 == 816 && $branch1_capture_leaf_lut1 == 816
}]
set post_opt_data_bufg_ok [expr {$data_bufg == 0}]
set kernel_ok [expr {
    $kernel_dsp == 3072 && $branch0_dsp == 1536 &&
    $branch1_dsp == 1536
}]
set attention_projection_ok [expr {
    $attention_projection_dsp == 2240 &&
    $attention_array_dsp == 2176 &&
    $attention_frontend_dsp == 64 &&
    $attention_base_frontend_dsp == 64 &&
    $attention_quantizer_dsp == 0
}]
set compact_input_frontend_ok [expr {
    $compact_input_frontend_dsp == 8 &&
    $compact_input_base_frontend_dsp == 8 &&
    $compact_input_quantizer_dsp == 0
}]
set swiglu_frontend_ok [expr {
    $swiglu_frontend_dsp == 72 &&
    $swiglu_hadamard_dsp == 64 &&
    $swiglu_quantizer_dsp == 0 &&
    $swiglu_silu_dsp == 4 &&
    $swiglu_metadata_address_dsp == 4 &&
    $swiglu_metadata_address_dsp_identity_ok &&
    $swiglu_other_dsp == 0
}]
set swiglu_bram_ok [expr {
    $swiglu_frontend_ramb36 == 40 &&
    $swiglu_row_ring_ramb36 == 28 &&
    $swiglu_silu_ramb36 == 12 &&
    $swiglu_other_ramb36 == 0
}]
set no_clip_quantizer_dsp_ok [expr {
    [llength $s27_quantizers] == 12 &&
    [llength $attention_s27_quantizers] == 8 &&
    [llength $compact_s27_quantizers] == 4 &&
    $attention_quantizer_dsp == 0 &&
    $compact_input_quantizer_dsp == 0 &&
    $swiglu_quantizer_dsp == 0
}]
set attention_local_store_ok [expr {
    [dict get $query_store_metrics instances] == 1 &&
    [dict get $postprocess_store_metrics instances] == 1 &&
    [llength $attention_postprocess_row_banks] == 16 &&
    [dict get $postprocess_store_metrics lut] <= 30000 &&
    [dict get $postprocess_store_metrics ff] == 24580 &&
    [dict get $postprocess_store_metrics ramb36] == 0 &&
    [dict get $postprocess_store_metrics ramb18] == 0 &&
    [dict get $postprocess_store_metrics lutram] == 0 &&
    [dict get $postprocess_store_metrics dsp] == 0 &&
    [dict get $postprocess_store_metrics uram] == 0 &&
    [dict get $context_store_metrics instances] == 1 &&
    [dict get $context_store_metrics ramb36] == 44 &&
    [dict get $context_store_metrics ramb18] == 0 &&
    [dict get $context_store_metrics lutram] == 0 &&
    [dict get $context_store_metrics dsp] == 0 &&
    [dict get $context_store_metrics uram] == 0
}]
set resource_ok [expr {
    $total_dsp == 5449 && $total_uram == 752 &&
    $total_ramb36 == 829 && $total_ramb18 == 22 &&
    $clb_lut <= 1064016
}]
set status [expr {$hierarchy_ok && $protected_structure_ok &&
    $post_opt_data_bufg_ok && $kernel_ok && $attention_projection_ok &&
    $compact_input_frontend_ok && $swiglu_frontend_ok && $swiglu_bram_ok &&
    $no_clip_quantizer_dsp_ok && $attention_local_store_ok && $resource_ok ?
    "V5_POST_OPT_DCP_AUDIT_PASS" : "FAIL"}]

set handle [open $summary w]
set actual_manifest_sha [hap_sha256 $input_sha]
foreach {key value} [list \
    tool [version -short] evidence_class V5_POST_OPT_READ_ONLY_REOPEN \
    dcp $dcp input_dcp_sha256 $actual_dcp_sha \
    input_manifest_sha256 $actual_manifest_sha \
    top $design_top part $design_part \
    production_profile cohort16 \
    attention_board_module hap_attention_board_cohort16_core \
    attention_cohort16_board_instances [llength $attention_cohort16_board] \
    attention_legacy_board_instances [llength $attention_legacy_board] \
    attention_cohort16_compute_instances [llength $attention_cohort16_compute] \
    attention_legacy_compute_instances [llength $attention_legacy_compute] \
    attention_query_store_instances [llength $attention_query_store] \
    attention_postprocess_store_instances \
        [llength $attention_postprocess_store] \
    attention_postprocess_row_bank_instances \
        [llength $attention_postprocess_row_banks] \
    attention_context_store_instances [llength $attention_context_store] \
    attention_query_store_lut_primitives \
        [dict get $query_store_metrics lut] \
    attention_query_store_srl16e \
        [dict get $query_store_metrics srl16e] \
    attention_query_store_ff_primitives \
        [dict get $query_store_metrics ff] \
    attention_query_store_ramb36e2 \
        [dict get $query_store_metrics ramb36] \
    attention_query_store_ramb18e2 \
        [dict get $query_store_metrics ramb18] \
    attention_query_store_lutram_primitives \
        [dict get $query_store_metrics lutram] \
    attention_query_store_dsp48e2 [dict get $query_store_metrics dsp] \
    attention_query_store_uram288 [dict get $query_store_metrics uram] \
    attention_query_store_input_pins \
        [dict get $query_store_metrics input_pins] \
    attention_query_store_output_pins \
        [dict get $query_store_metrics output_pins] \
    attention_query_store_boundary_nets \
        [dict get $query_store_metrics boundary_nets] \
    attention_postprocess_store_lut_primitives \
        [dict get $postprocess_store_metrics lut] \
    attention_postprocess_store_srl16e \
        [dict get $postprocess_store_metrics srl16e] \
    attention_postprocess_store_ff_primitives \
        [dict get $postprocess_store_metrics ff] \
    attention_postprocess_store_ramb36e2 \
        [dict get $postprocess_store_metrics ramb36] \
    attention_postprocess_store_ramb18e2 \
        [dict get $postprocess_store_metrics ramb18] \
    attention_postprocess_store_lutram_primitives \
        [dict get $postprocess_store_metrics lutram] \
    attention_postprocess_store_dsp48e2 \
        [dict get $postprocess_store_metrics dsp] \
    attention_postprocess_store_uram288 \
        [dict get $postprocess_store_metrics uram] \
    attention_postprocess_store_input_pins \
        [dict get $postprocess_store_metrics input_pins] \
    attention_postprocess_store_output_pins \
        [dict get $postprocess_store_metrics output_pins] \
    attention_postprocess_store_boundary_nets \
        [dict get $postprocess_store_metrics boundary_nets] \
    attention_context_store_lut_primitives \
        [dict get $context_store_metrics lut] \
    attention_context_store_srl16e \
        [dict get $context_store_metrics srl16e] \
    attention_context_store_ff_primitives \
        [dict get $context_store_metrics ff] \
    attention_context_store_ramb36e2 \
        [dict get $context_store_metrics ramb36] \
    attention_context_store_ramb18e2 \
        [dict get $context_store_metrics ramb18] \
    attention_context_store_lutram_primitives \
        [dict get $context_store_metrics lutram] \
    attention_context_store_dsp48e2 [dict get $context_store_metrics dsp] \
    attention_context_store_uram288 [dict get $context_store_metrics uram] \
    attention_context_store_input_pins \
        [dict get $context_store_metrics input_pins] \
    attention_context_store_output_pins \
        [dict get $context_store_metrics output_pins] \
    attention_context_store_boundary_nets \
        [dict get $context_store_metrics boundary_nets] \
    attention_projection16_instances [llength $attention_projection16] \
    attention_projection8_instances [llength $attention_projection8] \
    attention_lane_instances [llength $attention_lanes] \
    attention_dual_accumulator_instances \
        [llength $attention_dual_accumulators] \
    attention_local_accumulator_contexts $attention_local_contexts \
    attention_region2_instances \
        [dict get $attention_region2_fifo region2_instances] \
    attention_region2_dual_accumulator_instances \
        [dict get $attention_region2_fifo region2_accumulators] \
    attention_region2_buffered_accumulator_instances \
        [dict get $attention_region2_fifo buffered_accumulators] \
    attention_region2_lower_bank_instances \
        [dict get $attention_region2_fifo lower_banks] \
    attention_region2_upper_bank_instances \
        [dict get $attention_region2_fifo upper_banks] \
    attention_region2_g_buffered_input_present \
        [dict get $attention_region2_fifo g_buffered_input_present] \
    attention_region2_buffer_primitives \
        [dict get $attention_region2_fifo buffer_primitives] \
    attention_region2_buffer_ff \
        [dict get $attention_region2_fifo buffer_ff] \
    attention_region2_buffer_payload_ff \
        [dict get $attention_region2_fifo payload_ff] \
    attention_region2_buffer_tag_ff \
        [dict get $attention_region2_fifo tag_ff] \
    attention_region2_buffer_occupancy_ff \
        [dict get $attention_region2_fifo occupancy_ff] \
    attention_region2_buffer_partition_ok \
        [dict get $attention_region2_fifo partition_ok] \
    attention_region2_elastic_fifo_ok \
        [dict get $attention_region2_fifo ok] \
    attention_projection_dsp48e2 $attention_projection_dsp \
    attention_array_dsp48e2 $attention_array_dsp \
    attention_frontend_dsp48e2 $attention_frontend_dsp \
    attention_base_frontend_dsp48e2 $attention_base_frontend_dsp \
    no_clip_s27_quantizer_instances [llength $s27_quantizers] \
    attention_quantizer_instances [llength $attention_s27_quantizers] \
    attention_quantizer_dsp48e2 $attention_quantizer_dsp \
    raw_weight_push_loads [dict get $projection_weight_capture raw_loads] \
    weight_data_capture_contract 32x256 \
    weight_data_capture_nets [dict get $projection_weight_capture data_nets] \
    weight_data_capture_loads \
        [dict get $projection_weight_capture data_min]/[dict get $projection_weight_capture data_max] \
    weight_meta_capture_contract 2x256 \
    weight_meta_capture_nets [dict get $projection_weight_capture meta_nets] \
    weight_meta_capture_loads \
        [dict get $projection_weight_capture meta_min]/[dict get $projection_weight_capture meta_max] \
    weight_group_capture_contract 2x7 \
    weight_group_capture_nets [dict get $projection_weight_capture group_nets] \
    weight_group_capture_loads \
        [dict get $projection_weight_capture group_min]/[dict get $projection_weight_capture group_max] \
    projection_weight_capture_ok [dict get $projection_weight_capture ok] \
    v5_serial_instances [llength $v5_serial] \
    old_serial_instances [llength $old_serial] \
    v5_shared_instances [llength $v5_shared] \
    v5_branch_instances [llength $v5_branches] \
    v5_kernel12_instances [llength $v5_kernels] \
    old_kernel16_instances [llength $old_kernels] \
    history2_repack_instances [llength $history2_repack] \
    generic_repack_instances [llength $generic_repack] \
    swiglu_frontend_instances [llength $swiglu_frontend] \
    swiglu_row_leaf_instances [llength $swiglu_row_leaf] \
    swiglu_unique_hadamard_instances [llength $swiglu_hadamard] \
    swiglu_fold2_hadamard_instances [llength $swiglu_fold2] \
    swiglu_quantizer_instances [llength $swiglu_quantizer] \
    swiglu_silu_instances [llength $swiglu_silu] \
    attention_col3_array_instances [llength $attention_col3_array] \
    attention_old_array_instances [llength $attention_old_array] \
    attention_left2_shard_instances [llength $attention_left_shard] \
    attention_center12_shard_instances [llength $attention_center_shard] \
    attention_right2_shard_instances [llength $attention_right_shard] \
    attention_center_subshard_instances [llength $attention_center_subshards] \
    attention_leaf_shard_instances [llength $attention_leaf_shards] \
    compact_input_frontend_instances [llength $compact_input_frontend] \
    compact_input_frontend_dsp48e2 $compact_input_frontend_dsp \
    compact_input_base_frontend_dsp48e2 \
        $compact_input_base_frontend_dsp \
    compact_input_quantizer_instances [llength $compact_s27_quantizers] \
    compact_input_quantizer_dsp48e2 $compact_input_quantizer_dsp \
    compact_input_capture_contract 48x256 \
    compact_input_capture_ff $compact_capture_ff \
    compact_input_capture_controls $compact_capture_controls \
    compact_input_capture_loads $compact_capture_min/$compact_capture_max \
    down_activation_cache_instances [llength $down_activation_cache] \
    down_activation_capture_contract 16x280 \
    down_activation_capture_owners $down_activation_capture_owners \
    down_activation_capture_ff $down_activation_capture_ff \
    down_activation_capture_loads \
        $down_activation_capture_min/$down_activation_capture_max \
    gate_accum_instances [llength $gate_accums] \
    gate_accum_write_controls $gate_write_controls \
    gate_accum_finalize_owners $gate_finalize_owners \
    gate_accum_write_loads $gate_write_min/$gate_write_max \
    gate_accum_finalize_loads $gate_finalize_min/$gate_finalize_max \
    down_accum_instances [llength $down_accums] \
    down_guard_capture_contract 16x444 \
    down_guard_capture_controls $down_guard_controls \
    down_guard_capture_ff $down_guard_ff \
    down_guard_capture_loads $down_guard_min/$down_guard_max \
    down_output_capture_contract 16x288 \
    down_output_capture_controls $down_output_controls \
    down_output_capture_ff $down_output_ff \
    down_output_capture_loads $down_output_min/$down_output_max \
    serial_reset_lut2_domains $serial_reset_domains \
    serial_reset_protected_domains $serial_reset_protected \
    mlp_local_clear_ff $mlp_local_clear_ff \
    mlp_local_clear_protected_ff $mlp_local_clear_protected_ff \
    branch0_local_clear_ff $branch0_local_clear_ff \
    branch1_local_clear_ff $branch1_local_clear_ff \
    swiglu_local_clear_ff $swiglu_local_clear_ff \
    swiglu_local_clear_protected_ff $swiglu_local_clear_protected_ff \
    swiglu_control_clear_ff $swiglu_control_clear_ff \
    swiglu_hadamard_clear_ff $swiglu_hadamard_clear_ff \
    swiglu_quantizer_clear_ff $swiglu_quantizer_clear_ff \
    swiglu_row_clear_ff $swiglu_row_clear_ff \
    swiglu_clear_input_nets $swiglu_clear_input_nets \
    swiglu_direct_clear_bypass_state $swiglu_direct_clear_bypass_state \
    swiglu_frontend_dsp48e2 $swiglu_frontend_dsp \
    swiglu_hadamard_dsp48e2 $swiglu_hadamard_dsp \
    swiglu_quantizer_dsp48e2 $swiglu_quantizer_dsp \
    swiglu_silu_dsp48e2 $swiglu_silu_dsp \
    swiglu_metadata_address_dsp48e2 $swiglu_metadata_address_dsp \
    swiglu_metadata_address_dsp_names \
        [join $swiglu_metadata_address_dsp_names ,] \
    swiglu_metadata_address_dsp_r1 $swiglu_metadata_address_dsp_r1 \
    swiglu_metadata_address_dsp_r2 $swiglu_metadata_address_dsp_r2 \
    swiglu_metadata_address_dsp_unexpected \
        [join $swiglu_metadata_address_dsp_unexpected ,] \
    swiglu_metadata_address_dsp_identity_ok \
        $swiglu_metadata_address_dsp_identity_ok \
    swiglu_other_dsp48e2 $swiglu_other_dsp \
    swiglu_frontend_ramb36e2 $swiglu_frontend_ramb36 \
    swiglu_row_ring_ramb36e2 $swiglu_row_ring_ramb36 \
    swiglu_silu_ramb36e2 $swiglu_silu_ramb36 \
    swiglu_other_ramb36e2 $swiglu_other_ramb36 \
    mlp_central_clear_ff $mlp_central_clear_ff \
    mlp_central_clear_branch_endpoints \
        $mlp_central_clear_branch_endpoints \
    mlp_central_clear_direct_branch_state \
        $mlp_central_clear_direct_branch_state \
    metadata_leaf_instances $metadata_leaf_instances \
    metadata_local_wr_en_ff $metadata_local_wr_en_ff \
    metadata_local_wr_addr_ff $metadata_local_wr_addr_ff \
    metadata_local_wr_data_ff $metadata_local_wr_data_ff \
    metadata_local_write_protected_ff $metadata_local_write_protected_ff \
    mlp_capture_leaf_instances $mlp_capture_leaf_instances \
    mlp_capture_leaf_lut1 $mlp_capture_leaf_lut1 \
    branch0_capture_leaf_instances $branch0_capture_leaf_instances \
    branch1_capture_leaf_instances $branch1_capture_leaf_instances \
    branch0_capture_leaf_lut1 $branch0_capture_leaf_lut1 \
    branch1_capture_leaf_lut1 $branch1_capture_leaf_lut1 \
    down_elastic2_instances [llength $down_elastic2] \
    kernel_dsp48e2 $kernel_dsp branch0_dsp48e2 $branch0_dsp \
    branch1_dsp48e2 $branch1_dsp dsp48e2 $total_dsp \
    dsp_required 5449 dsp_limit 5500 \
    uram288 $total_uram uram_required 752 \
    ramb36e2 $total_ramb36 ramb18e2 $total_ramb18 \
    post_opt_clock_bufg $clock_bufg post_opt_data_bufg $data_bufg \
    clb_lut $clb_lut clb_lut_limit 1064016 \
    lut_as_logic $lut_logic lut_as_memory $lut_memory \
    clb_register $clb_ff hierarchy_ok $hierarchy_ok \
    protected_structure_ok $protected_structure_ok \
    post_opt_data_bufg_ok $post_opt_data_bufg_ok \
    kernel_ok $kernel_ok attention_projection_ok $attention_projection_ok \
    compact_input_frontend_ok $compact_input_frontend_ok \
    swiglu_frontend_ok $swiglu_frontend_ok swiglu_bram_ok $swiglu_bram_ok \
    no_clip_quantizer_dsp_ok $no_clip_quantizer_dsp_ok \
    attention_local_store_ok $attention_local_store_ok \
    resource_ok $resource_ok checkpoint_written 0 \
    implementation_commands_run 0 status $status] {
    puts $handle "$key=$value"
}
close $handle

puts "V5_POST_OPT_DCP_AUDIT SERIAL=[llength $v5_serial]/[llength $old_serial] SHARED=[llength $v5_shared] BRANCH=[llength $v5_branches] KERNEL=[llength $v5_kernels]/[llength $old_kernels] ATTN_COL3_OLD=[llength $attention_col3_array]/[llength $attention_old_array] ATTN_SHARDS=[llength $attention_left_shard]/[llength $attention_center_shard]/[llength $attention_right_shard]:[llength $attention_center_subshards]/[llength $attention_leaf_shards] ATTN_REGION2_FIFO=[dict get $attention_region2_fifo buffered_accumulators]:[dict get $attention_region2_fifo payload_ff]/[dict get $attention_region2_fifo tag_ff]/[dict get $attention_region2_fifo occupancy_ff] ATTN_LOCAL_STORE=[dict get $query_store_metrics instances]/[dict get $postprocess_store_metrics instances]/[dict get $context_store_metrics instances]:[dict get $context_store_metrics ramb36]/[dict get $context_store_metrics lutram] ATTN_WEIGHT_CAPTURE=[dict get $projection_weight_capture raw_loads]:[dict get $projection_weight_capture data_nets]x[dict get $projection_weight_capture data_min]:[dict get $projection_weight_capture meta_nets]x[dict get $projection_weight_capture meta_min]:[dict get $projection_weight_capture group_nets]x[dict get $projection_weight_capture group_min] CAPTURE=$compact_capture_controls:$compact_capture_min/$compact_capture_max,$down_activation_capture_owners:$down_activation_capture_min/$down_activation_capture_max GATE_CTRL=$gate_write_controls/$gate_finalize_owners DOWN_CTRL=$down_guard_controls/$down_output_controls RESET=$serial_reset_domains LOCAL_CLEAR=$mlp_local_clear_ff/$mlp_local_clear_protected_ff DATA_BUFG=$data_bufg KERNEL_DSP=$kernel_dsp BRANCH_DSP=$branch0_dsp/$branch1_dsp DSP=$total_dsp URAM=$total_uram LUT=$clb_lut FF=$clb_ff BRAM=$total_ramb36/$total_ramb18 STATUS=$status"
if {$status ne "V5_POST_OPT_DCP_AUDIT_PASS"} {
    error "V5 post-opt DCP hierarchy/resource audit failed"
}
close_design
