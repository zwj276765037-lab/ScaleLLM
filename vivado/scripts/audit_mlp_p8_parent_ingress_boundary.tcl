# P8 parent-ingress structural audit.  This file defines procedures only and
# may be sourced by pre-place, placement and independent reopen flows.

namespace eval hap_mlp_p8_parent_boundary {}

proc hap_mlp_p8_parent_boundary::require_count {label objects expected} {
    set actual [llength $objects]
    if {$actual != $expected} {
        error "$label count mismatch: expected=$expected actual=$actual"
    }
    return $actual
}

proc hap_mlp_p8_parent_boundary::cells_of_module {module_name} {
    return [lsort -dictionary -unique [get_cells -quiet -hierarchical \
        -filter "ORIG_REF_NAME == $module_name || REF_NAME == $module_name"]]
}

proc hap_mlp_p8_parent_boundary::named_ff {root pattern} {
    set root_name [get_property NAME $root]
    return [lsort -dictionary -unique [get_cells -quiet -hierarchical \
        -filter "NAME =~ ${root_name}/${pattern} && REF_NAME =~ FD*"]]
}

proc hap_mlp_p8_parent_boundary::q_pins {cells} {
    set result {}
    foreach cell $cells {
        set q [get_pins -quiet -of_objects $cell \
            -filter {REF_PIN_NAME == Q}]
        require_count state_q $q 1
        set result [concat $result $q]
    }
    return [lsort -dictionary -unique $result]
}

proc hap_mlp_p8_parent_boundary::intersection {left right} {
    set right_names {}
    foreach item $right {
        dict set right_names [get_property NAME $item] 1
    }
    set result {}
    foreach item $left {
        set name [get_property NAME $item]
        if {[dict exists $right_names $name]} {
            lappend result $item
        }
    }
    return [lsort -dictionary -unique $result]
}

proc hap_mlp_p8_parent_boundary::ready_startpoints {
        label net_patterns pin_patterns expected_nets expected_pins} {
    set nets {}
    foreach pattern $net_patterns {
        set nets [concat $nets [get_nets -quiet -hierarchical \
            -filter "NAME =~ $pattern"]]
    }
    set nets [lsort -dictionary -unique $nets]
    require_count ${label}_nets $nets $expected_nets

    set pins {}
    foreach pattern $pin_patterns {
        set pins [concat $pins [get_pins -quiet -hierarchical \
            -filter "NAME =~ $pattern"]]
    }
    set pins [lsort -dictionary -unique $pins]
    require_count ${label}_pins $pins $expected_pins

    set starts {}
    foreach net $nets {
        set net_pins [get_pins -quiet -of_objects $net]
        if {[llength $net_pins] != 0} {
            set starts [concat $starts [all_fanin -quiet -flat \
                -startpoints_only -to $net_pins]]
        }
    }
    foreach pin $pins {
        set starts [concat $starts [all_fanin -quiet -flat \
            -startpoints_only -to $pin]]
    }
    return [lsort -dictionary -unique $starts]
}

proc hap_mlp_p8_parent_boundary::audit {} {
    set shared [cells_of_module hap_mlp_shared_dual_slice16x12_s43_s45]
    set branches [cells_of_module hap_mlp_shared_local_slice8x12_s43_s45]
    require_count shared_root $shared 1
    require_count local_branch_roots $branches 2

    set shared_root [lindex $shared 0]
    set parent_head [named_ff $shared_root parent_head_r_reg*]
    set parent_tail [named_ff $shared_root parent_tail_r_reg*]
    set parent_count [named_ff $shared_root parent_count_r_reg*]
    set parent_pointer [concat \
        [named_ff $shared_root parent_wr_ptr_r_reg*] \
        [named_ff $shared_root parent_rd_ptr_r_reg*]]
    require_count parent_head_ff $parent_head 6560
    require_count parent_tail_ff $parent_tail 6560
    require_count parent_count_ff $parent_count 2
    require_count parent_pointer_ff $parent_pointer 0

    set clear_ff {}
    set ingress_count_ff {}
    foreach branch $branches {
        set branch_clear [named_ff $branch clear_local_r_reg*]
        set branch_count [named_ff $branch ingress_count_r_reg*]
        require_count branch_local_clear_ff $branch_clear 1
        require_count branch_ingress_count_ff $branch_count 2
        set clear_ff [concat $clear_ff $branch_clear]
        set ingress_count_ff [concat $ingress_count_ff $branch_count]
    }
    set clear_ff [lsort -dictionary -unique $clear_ff]
    set ingress_count_ff [lsort -dictionary -unique $ingress_count_ff]
    require_count local_clear_ff $clear_ff 2
    require_count branch_ingress_count_ff $ingress_count_ff 4

    set clear_q [q_pins $clear_ff]
    set credit_q [q_pins $ingress_count_ff]
    require_count local_clear_q $clear_q 2
    require_count branch_credit_q $credit_q 4

    set shared_name [get_property NAME $shared_root]
    set shared_ready_starts [ready_startpoints shared_upstream_ready \
        [list "${shared_name}/in_ready" "*/shared_input_ready"] \
        [list "${shared_name}/in_ready"] 2 1]
    set gate_ready_starts [ready_startpoints gate_compute_ready \
        [list "*/u_gate_scheduler/compute_ready"] \
        [list "*/u_gate_scheduler/compute_ready"] 1 1]
    set down_ready_starts [ready_startpoints down_compute_ready \
        [list "*/u_down_scheduler/compute_ready"] \
        [list "*/u_down_scheduler/compute_ready"] 1 1]
    set cache_ready_starts [ready_startpoints input_cache_ready \
        [list "*/u_input_frontend/*rd_rsp_ready" \
            "*/u_input_frontend/*rd_req_ready"] \
        [list "*/u_input_frontend/*rd_rsp_ready" \
            "*/u_input_frontend/*rd_req_ready"] 8 6]

    foreach source_label [list local_clear branch_credit] \
            sources [list $clear_q $credit_q] {
        foreach target_label [list shared_upstream_ready gate_compute_ready \
                down_compute_ready input_cache_ready] \
                starts [list $shared_ready_starts $gate_ready_starts \
                    $down_ready_starts $cache_ready_starts] {
            set forbidden [intersection $sources $starts]
            require_count ${source_label}_${target_label}_paths $forbidden 0
            set ${source_label}_${target_label}_paths [llength $forbidden]
        }
    }

    return [dict create ok 1 parent_head_ff [llength $parent_head] \
        parent_tail_ff [llength $parent_tail] \
        parent_count_ff [llength $parent_count] \
        parent_pointer_ff [llength $parent_pointer] \
        local_clear_ff [llength $clear_ff] \
        branch_ingress_count_ff [llength $ingress_count_ff] \
        local_clear_shared_upstream_ready_paths \
            $local_clear_shared_upstream_ready_paths \
        branch_credit_shared_upstream_ready_paths \
            $branch_credit_shared_upstream_ready_paths \
        local_clear_gate_compute_ready_paths \
            $local_clear_gate_compute_ready_paths \
        branch_credit_gate_compute_ready_paths \
            $branch_credit_gate_compute_ready_paths \
        local_clear_down_compute_ready_paths \
            $local_clear_down_compute_ready_paths \
        branch_credit_down_compute_ready_paths \
            $branch_credit_down_compute_ready_paths \
        local_clear_input_cache_ready_paths \
            $local_clear_input_cache_ready_paths \
        branch_credit_input_cache_ready_paths \
            $branch_credit_input_cache_ready_paths]
}

proc hap_mlp_p8_parent_boundary::write_audit {metrics path marker} {
    set handle [open $path w]
    puts $handle $marker
    foreach key [lsort -dictionary [dict keys $metrics]] {
        puts $handle "$key=[dict get $metrics $key]"
    }
    close $handle
}
