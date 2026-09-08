# P8 parent-ingress structural audit with strict support for implementation
# replicas.  Procedures only; safe to source from reopen and route flows.

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

proc hap_mlp_p8_parent_boundary::object_names {objects} {
    set result {}
    foreach object $objects {
        lappend result [get_property NAME $object]
    }
    return [lsort -dictionary -unique $result]
}

proc hap_mlp_p8_parent_boundary::property {object name} {
    if {[lsearch -exact [list_property $object] $name] < 0} {
        error "missing property $name on [get_property NAME $object]"
    }
    return [get_property $name $object]
}

proc hap_mlp_p8_parent_boundary::pin_nets {cell ref_pin expected_pins} {
    set pins [get_pins -quiet -of_objects $cell \
        -filter "REF_PIN_NAME == $ref_pin"]
    require_count "[get_property NAME $cell].${ref_pin}_pins" \
        $pins $expected_pins
    set nets {}
    foreach pin $pins {
        set nets [concat $nets [get_nets -quiet -of_objects $pin]]
    }
    set nets [lsort -dictionary -unique $nets]
    require_count "[get_property NAME $cell].${ref_pin}_nets" \
        $nets $expected_pins
    return [object_names $nets]
}

proc hap_mlp_p8_parent_boundary::require_q_driver {cell} {
    set q_pins [get_pins -quiet -of_objects $cell \
        -filter {REF_PIN_NAME == Q}]
    require_count "[get_property NAME $cell].Q_pins" $q_pins 1
    set q_nets [get_nets -quiet -of_objects $q_pins]
    require_count "[get_property NAME $cell].Q_nets" $q_nets 1
    set drivers [get_pins -quiet -of_objects $q_nets \
        -filter {DIRECTION == OUT}]
    require_count "[get_property NAME $cell].Q_drivers" $drivers 1
    if {[get_property NAME [lindex $drivers 0]] ne \
            "[get_property NAME $cell]/Q"} {
        error "unexpected Q driver for [get_property NAME $cell]"
    }
    set loads [get_pins -quiet -of_objects $q_nets \
        -filter {DIRECTION == IN}]
    if {[llength $loads] == 0} {
        error "unused parent count replica: [get_property NAME $cell]"
    }
    return [get_property NAME [lindex $q_nets 0]]
}

proc hap_mlp_p8_parent_boundary::parent_count_contract {
        shared_root parent_count} {
    set root_name [get_property NAME $shared_root]
    set originals {}
    set replicas {}
    foreach cell $parent_count {
        if {[property $cell IS_ORIG_CELL]} {
            lappend originals $cell
        } else {
            lappend replicas $cell
        }
    }
    set originals [lsort -dictionary -unique $originals]
    set replicas [lsort -dictionary -unique $replicas]
    require_count parent_count_canonical_ff $originals 2

    set accounted {}
    set group_counts {}
    foreach bit {0 1} {
        set leaf [format {parent_count_r_reg[%d]} $bit]
        set canonical_name "${root_name}/${leaf}"
        set canonical [get_cells -quiet $canonical_name]
        require_count "parent_count_bit${bit}_canonical_ff" $canonical 1
        set canonical [lindex $canonical 0]
        if {![property $canonical IS_ORIG_CELL] ||
            [property $canonical ORIG_CELL_NAME] ne ""} {
            error "invalid canonical parent count identity: $canonical_name"
        }

        set expected_ref [property $canonical REF_NAME]
        set expected_orig_ref [property $canonical ORIG_REF_NAME]
        set expected_init [property $canonical INIT]
        if {$expected_ref ne "FDRE" || $expected_orig_ref ne "FDRE" ||
            $expected_init ne "1'b0"} {
            error "invalid canonical parent count primitive: $canonical_name"
        }
        set expected_d [pin_nets $canonical D 1]
        set expected_c [pin_nets $canonical C 1]
        set expected_ce [pin_nets $canonical CE 1]
        set expected_r [pin_nets $canonical R 1]
        foreach forbidden_pin {S CLR PRE} {
            require_count "${canonical_name}.${forbidden_pin}_pins" \
                [get_pins -quiet -of_objects $canonical \
                    -filter "REF_PIN_NAME == $forbidden_pin"] 0
        }

        set group [list $canonical]
        foreach replica $replicas {
            if {[property $replica ORIG_CELL_NAME] eq $leaf} {
                lappend group $replica
            }
        }
        set group [lsort -dictionary -unique $group]
        foreach cell $group {
            set name [get_property NAME $cell]
            if {$cell ne $canonical} {
                if {[property $cell IS_ORIG_CELL] ||
                    [string first "${canonical_name}_replica" $name] != 0} {
                    error "invalid parent count replica identity: $name"
                }
            }
            foreach prop {REF_NAME ORIG_REF_NAME INIT} expected \
                    [list $expected_ref $expected_orig_ref $expected_init] {
                if {[property $cell $prop] ne $expected} {
                    error "parent count replica $prop mismatch: $name"
                }
            }
            foreach ref_pin {D C CE R} expected \
                    [list $expected_d $expected_c $expected_ce $expected_r] {
                if {[pin_nets $cell $ref_pin 1] ne $expected} {
                    error "parent count replica $ref_pin mismatch: $name"
                }
            }
            foreach forbidden_pin {S CLR PRE} {
                require_count "${name}.${forbidden_pin}_pins" \
                    [get_pins -quiet -of_objects $cell \
                        -filter "REF_PIN_NAME == $forbidden_pin"] 0
            }
            require_q_driver $cell
            lappend accounted $cell
        }
        dict set group_counts $bit [llength $group]
    }

    set accounted [lsort -dictionary -unique $accounted]
    require_count parent_count_accounted_ff $accounted [llength $parent_count]
    return [dict create parent_count_ff 2 \
        parent_count_physical_ff [llength $parent_count] \
        parent_count_replica_ff [llength $replicas] \
        parent_count_bit0_physical_ff [dict get $group_counts 0] \
        parent_count_bit1_physical_ff [dict get $group_counts 1] \
        parent_count_replica_equivalence_ok 1]
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
    set parent_metrics [parent_count_contract $shared_root $parent_count]
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

    return [dict merge [dict create ok 1 \
        parent_head_ff [llength $parent_head] \
        parent_tail_ff [llength $parent_tail] \
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
            $branch_credit_input_cache_ready_paths] $parent_metrics]
}

proc hap_mlp_p8_parent_boundary::write_audit {metrics path marker} {
    set handle [open $path w]
    puts $handle $marker
    foreach key [lsort -dictionary [dict keys $metrics]] {
        puts $handle "$key=[dict get $metrics $key]"
    }
    close $handle
}
