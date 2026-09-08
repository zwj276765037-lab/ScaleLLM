# Read-only diagnostic for the P8 parent-ingress boundary.  This script does
# not run implementation commands or write a checkpoint.

if {$argc == 2} {
    set dcp [file normalize [lindex $argv 0]]
    set out [file normalize [lindex $argv 1]]
} elseif {[info exists ::env(HAP_DCP)] &&
          [info exists ::env(HAP_DIAG_DIR)]} {
    set dcp [file normalize $::env(HAP_DCP)]
    set out [file normalize $::env(HAP_DIAG_DIR)]
} else {
    error "set HAP_DCP/HAP_DIAG_DIR or pass POST_OPT_DCP OUT_DIR"
}
file mkdir $out

proc p8_cells_of_module {module_name} {
    return [lsort -dictionary -unique [get_cells -quiet -hierarchical \
        -filter "ORIG_REF_NAME == $module_name || REF_NAME == $module_name"]]
}

proc p8_named_ff {root pattern} {
    set root_name [get_property NAME $root]
    return [lsort -dictionary -unique [get_cells -quiet -hierarchical \
        -filter "NAME =~ ${root_name}/${pattern} && REF_NAME =~ FD*"]]
}

proc p8_q_pins {cells} {
    set result {}
    foreach cell $cells {
        set result [concat $result [get_pins -quiet -of_objects $cell \
            -filter {REF_PIN_NAME == Q}]]
    }
    return [lsort -dictionary -unique $result]
}

proc p8_intersection {left right} {
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

proc p8_target_startpoints {nets} {
    set result {}
    foreach net $nets {
        set pins [get_pins -quiet -of_objects $net]
        if {[llength $pins] != 0} {
            set result [concat $result [all_fanin -quiet -flat \
                -startpoints_only -to $pins]]
        }
    }
    return [lsort -dictionary -unique $result]
}

proc p8_write_names {handle label objects} {
    puts $handle "$label.count=[llength $objects]"
    foreach object $objects {
        puts $handle "$label.name=[get_property NAME $object]"
    }
}

open_checkpoint $dcp
set shared [p8_cells_of_module hap_mlp_shared_dual_slice16x12_s43_s45]
set branches [p8_cells_of_module hap_mlp_shared_local_slice8x12_s43_s45]
if {[llength $shared] != 1 || [llength $branches] != 2} {
    error "unexpected P8 hierarchy: shared=[llength $shared] branches=[llength $branches]"
}

set clear_ff {}
set credit_ff {}
foreach branch $branches {
    set clear_ff [concat $clear_ff [p8_named_ff $branch clear_local_r_reg*]]
    set credit_ff [concat $credit_ff [p8_named_ff $branch ingress_count_r_reg*]]
}
set clear_q [p8_q_pins [lsort -dictionary -unique $clear_ff]]
set credit_q [p8_q_pins [lsort -dictionary -unique $credit_ff]]
set local_sources [concat $clear_q $credit_q]

set shared_name [get_property NAME [lindex $shared 0]]
set target_specs [dict create \
    shared_upstream_ready [list "${shared_name}/in_ready" \
        "*/shared_input_ready"] \
    gate_compute_ready [list "*/u_gate_scheduler/compute_ready"] \
    down_compute_ready [list "*/u_down_scheduler/compute_ready"] \
    input_cache_ready [list "*/u_input_frontend/*rd_rsp_ready" \
        "*/u_input_frontend/*rd_req_ready"]]

set report [open [file join $out p8_parent_ingress_cone.txt] w]
puts $report "status=P8_PARENT_INGRESS_DIAGNOSIS"
p8_write_names $report local_clear_q $clear_q
p8_write_names $report branch_credit_q $credit_q

foreach label [dict keys $target_specs] {
    set nets {}
    set pins {}
    foreach pattern [dict get $target_specs $label] {
        set nets [concat $nets [get_nets -quiet -hierarchical \
            -filter "NAME =~ $pattern"]]
        set pins [concat $pins [get_pins -quiet -hierarchical \
            -filter "NAME =~ $pattern"]]
    }
    set nets [lsort -dictionary -unique $nets]
    set pins [lsort -dictionary -unique $pins]
    set starts [p8_target_startpoints $nets]
    foreach pin $pins {
        set starts [concat $starts [all_fanin -quiet -flat \
            -startpoints_only -to $pin]]
    }
    set starts [lsort -dictionary -unique $starts]
    set forbidden [p8_intersection $local_sources $starts]
    p8_write_names $report ${label}.net $nets
    p8_write_names $report ${label}.pin $pins
    p8_write_names $report ${label}.forbidden_source $forbidden
}

# Endpoint counts explain why the old scheduler-wide test was overbroad.
# These are evidence only; the exact ready-cone intersections above are the
# pass/fail boundary used by the corrected audit.
foreach source_class [list clear credit] sources [list $clear_q $credit_q] {
    set endpoints {}
    foreach source $sources {
        set endpoints [concat $endpoints [all_fanout -quiet -flat \
            -endpoints_only -from $source]]
    }
    set endpoints [lsort -dictionary -unique $endpoints]
    set scheduler_endpoints {}
    set valid_named {}
    set ready_named {}
    foreach endpoint $endpoints {
        set name [get_property NAME $endpoint]
        if {[string match "*/u_gate_scheduler/*" $name] ||
            [string match "*/u_down_scheduler/*" $name]} {
            lappend scheduler_endpoints $endpoint
            if {[regexp {gate|down|valid|gather|postprocess} $name]} {
                lappend valid_named $endpoint
            }
            if {[regexp {ready|cache|rd_req|rd_rsp} $name]} {
                lappend ready_named $endpoint
            }
        }
    }
    p8_write_names $report ${source_class}.scheduler_endpoint \
        $scheduler_endpoints
    puts $report "${source_class}.scheduler_valid_named_count=[llength $valid_named]"
    puts $report "${source_class}.scheduler_ready_named_count=[llength $ready_named]"
}

close $report
close_design
