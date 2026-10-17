# M002 independent diagnostic implementation support. Original synth entry is frozen.
set ::m002_script_dir [file dirname [file normalize [info script]]]
set ::m002_report_dir [file normalize $::env(HAP_REPORT_DIR)]

proc m002_put {path text} {
    set h [open $path w]; puts $h $text; close $h
}
proc m002_prop {object property} {
    set value [get_property -quiet $property $object]
    return [string map [list "\t" " " "\n" " " "\r" " "] $value]
}
proc m002_dump_cells {handle cells} {
    foreach cell $cells {
        puts $handle "CELL\t$cell\t[m002_prop $cell REF_NAME]\tINIT=[m002_prop $cell INIT]\tASYNC_REG=[m002_prop $cell ASYNC_REG]\tBLACKBOX=[m002_prop $cell IS_BLACKBOX]\tIS_C_INVERTED=[m002_prop $cell IS_C_INVERTED]\tIS_CLR_INVERTED=[m002_prop $cell IS_CLR_INVERTED]\tIS_R_INVERTED=[m002_prop $cell IS_R_INVERTED]"
        foreach pin [get_pins -quiet -of_objects $cell] {
            set net [get_nets -quiet -of_objects $pin]
            puts $handle "PIN\t$pin\t[m002_prop $pin DIRECTION]\t$net\tCLOCKS=[m002_pin_clocks $pin]"
        }
    }
}
proc m002_debug_source_ips {} {
    set ips [list]
    # xsdbm is admitted only for the actual known dbg_hub core/cell/module.
    if {[catch {set core [get_debug_cores -quiet dbg_hub];set cell [m002_exact get_cells dbg_hub]} issue] || [llength $core] != 1 || [llength $cell] != 1} {return $ips}
    foreach ip [get_ips -quiet -all] {
        set definition [m002_prop $ip IPDEF]
        set component [m002_prop $ip CONFIG.Component_Name]
        set name [m002_prop $ip NAME]
        if {($name eq "dbg_hub" || $component eq "dbg_hub") && ([string match "*:dbg_hub:*" $definition] || $definition eq "xilinx.com:ip:xsdbm:3.0")} {lappend ips $ip}
    }
    return $ips
}
proc m002_dump_xdc_native {point} {
    set out [file join $::m002_report_dir xdc_registry_${point}.tsv]
    set h [open $out w]
    puts $h "path\tUSED_IN\tUSED_IN_SYNTHESIS\tUSED_IN_IMPLEMENTATION\tIS_ENABLED\tSCOPED_TO_REF\tSCOPED_TO_CELLS\tPROCESSING_ORDER\tSHA256"
    foreach source [lsort [get_files -all -quiet -filter {FILE_TYPE == XDC}]] {
        set path [file normalize [get_property NAME $source]]
        if {![file isfile $path]} {error "Registered XDC disappeared: $path"}
        set fields [list $path]
        foreach property {USED_IN USED_IN_SYNTHESIS USED_IN_IMPLEMENTATION IS_ENABLED SCOPED_TO_REF SCOPED_TO_CELLS PROCESSING_ORDER} {
            lappend fields [m002_prop $source $property]
        }
        # Hash once in a lightweight Python process after the hook. Registry is
        # not a claim that every OOC constraint is effective in this phase.
        puts $h "[join $fields \t]\tPENDING_BATCH_HASH"
    }
    close $h
    set h [open [file join $::m002_report_dir tool_debug_xdc_${point}.txt] w]
    set provenance [open [file join $::m002_report_dir tool_debug_xdc_ownership_${point}.tsv] w]
    foreach ip [m002_debug_source_ips] {
        foreach source [get_files -quiet -all -of_objects $ip -filter {FILE_TYPE == XDC}] {
            set path [file normalize [get_property NAME $source]]
            puts $h $path
            puts $provenance "$ip\t[get_property IPDEF $ip]\t$path\tactual_debug_core=dbg_hub;cell=dbg_hub;component=dbg_hub"
        }
    }
    close $h; close $provenance
    if {[catch {report_compile_order -constraints -file [file join $::m002_report_dir constraint_order_${point}.rpt]} issue]} {
        m002_put [file join $::m002_report_dir constraint_order_${point}_unavailable.txt] $issue
    }
}
# A restored DCP owns effective constraints. The current XPR candidate registry
# is checked before restore and carried separately from embedded tool objects.
proc m002_dump_xdc {point} {
    if {![info exists ::env(HAP_EXECUTION_MODE)] || $::env(HAP_EXECUTION_MODE) ne "checkpoint_restored_commands" || $point eq "project"} {
        return [m002_dump_xdc_native $point]
    }
    set header "path\tUSED_IN\tUSED_IN_SYNTHESIS\tUSED_IN_IMPLEMENTATION\tIS_ENABLED\tSCOPED_TO_REF\tSCOPED_TO_CELLS\tPROCESSING_ORDER\tSHA256"
    set h [open [file join $::m002_report_dir embedded_xdc_registry_${point}.tsv] w]
    puts $h $header
    foreach object [lsort [get_files -all -quiet -filter {FILE_TYPE == XDC}]] {
        set fields [list [m002_prop $object NAME]]
        foreach property {USED_IN USED_IN_SYNTHESIS USED_IN_IMPLEMENTATION IS_ENABLED SCOPED_TO_REF SCOPED_TO_CELLS PROCESSING_ORDER} {lappend fields [m002_prop $object $property]}
        puts $h "[join $fields \t]\tEMBEDDED_OBJECT_NOT_A_NEW_SOURCE_READ"
    }
    close $h
    file copy [file join $::m002_report_dir xdc_registry_project.tsv] [file join $::m002_report_dir xdc_registry_${point}.tsv]
    m002_put [file join $::m002_report_dir xdc_registry_${point}_mode.txt] "candidate_metadata=verified_original_project_registry\neffective_constraints=embedded_checkpoint_inherited\nembedded_objects=embedded_xdc_registry_${point}.tsv"
    set allowed [open [file join $::m002_report_dir tool_debug_xdc_${point}.txt] w]
    set ownership [open [file join $::m002_report_dir tool_debug_xdc_ownership_${point}.tsv] w]
    set registry [open [file join $::m002_report_dir tool_debug_registry_${point}.tsv] w]
    puts $registry $header
    foreach ip [m002_debug_source_ips] {
        foreach object [get_files -quiet -all -of_objects $ip -filter {FILE_TYPE == XDC}] {
            set path [file normalize [get_property NAME $object]]
            puts $allowed $path
            puts $ownership "$ip\t[get_property IPDEF $ip]\t$path\tactual_debug_core=dbg_hub;cell=dbg_hub;component=dbg_hub"
            set fields [list $path]
            foreach property {USED_IN USED_IN_SYNTHESIS USED_IN_IMPLEMENTATION IS_ENABLED SCOPED_TO_REF SCOPED_TO_CELLS PROCESSING_ORDER} {lappend fields [m002_prop $object $property]}
            puts $registry "[join $fields \t]\tPENDING_BATCH_HASH"
        }
    }
    close $allowed;close $ownership;close $registry
    if {[catch {report_compile_order -constraints -file [file join $::m002_report_dir constraint_order_${point}.rpt]} issue]} {
        m002_put [file join $::m002_report_dir constraint_order_${point}_unavailable.txt] $issue
    }
}
proc m002_debug_probe {point blackboxes} {
    set h [open [file join $::m002_report_dir debug_${point}.tsv] w]
    foreach object [get_debug_cores -quiet *] {
        puts $h "DEBUG_CORE\t$object"
        foreach property [lsort [list_property $object]] {
            puts $h "PROPERTY\t$object\t$property\t[m002_prop $object $property]"
        }
    }
    foreach object [get_debug_ports -quiet *] {
        puts $h "DEBUG_PORT\t$object"
        foreach property [lsort [list_property $object]] {
            puts $h "PROPERTY\t$object\t$property\t[m002_prop $object $property]"
        }
    }
    set hubs [get_cells -quiet dbg_hub]
    m002_dump_cells $h [lsort -unique [concat $blackboxes $hubs]]
    set families [list]
    set debug_clocks [list]
    foreach cell $hubs {
        foreach pin [get_pins -quiet -of_objects $cell] {
            set refpin [get_property REF_PIN_NAME $pin]
            set clocks [get_clocks -quiet -of_objects $pin]
            puts $h "DEBUG_PIN_CLOCKS\t$pin\t$clocks"
            set segments [get_nets -quiet -segments -of_objects $pin]
            puts $h "DEBUG_PIN_NETS\t$pin\t[lsort $segments]"
            set debug_clocks [concat $debug_clocks $clocks]
            if {![regexp {^sl_iport[01]_o\[1\]$} $refpin]} {continue}
            set drivers [get_pins -quiet -leaf -of_objects $segments -filter {DIRECTION == OUT}]
            foreach driver $drivers {
                set owner [get_cells -quiet -of_objects $driver]
                puts $h "DEBUG_OUTPUT_DRIVER\t$pin\t$driver\t[m002_prop $owner REF_NAME]\t[m002_prop $driver REF_PIN_NAME]"
            }
            puts $h "DEBUG_OUTPUT_STARTPOINTS\t$pin\t[all_fanin -quiet -flat -startpoints_only -to $pin]"
            set cone [all_fanin -quiet -flat -levels 6 -only_cells -to $pin]
            puts $h "DEBUG_OUTPUT_CONE\t$pin\tCELLS=[llength $cone]\tLIMIT=64"
            if {[llength $cone] <= 64} {m002_dump_cells $h $cone}
            foreach endpoint [all_fanout -quiet -flat -endpoints_only -from $pin] {
                puts $h "DEBUG_CLOCK_FANOUT\t$pin\t$endpoint"
                set clocks [get_clocks -quiet -of_objects $endpoint]
                puts $h "DEBUG_ENDPOINT_CLOCKS\t$pin\t$endpoint\t$clocks"
                set debug_clocks [concat $debug_clocks $clocks]
                if {[regexp {/ddr4_([01])/.*(U_XSDB_SLAVE|u_xsdb_arbiter)/} $endpoint -> ddr]} {
                    lappend families $ddr
                }
            }
        }
    }
    set remaining [lsort -unique $debug_clocks]
    set debug_clocks [list]
    while {[llength $remaining]} {
        set clock [lindex $remaining 0];set remaining [lrange $remaining 1 end]
        if {$clock in $debug_clocks} {continue}
        lappend debug_clocks $clock
        foreach master [get_clocks -quiet [m002_prop $clock MASTER_CLOCK]] {if {$master ni $debug_clocks} {lappend remaining $master}}
        if {[llength $debug_clocks] > 64} {error "Unbounded debug clock ancestry"}
    }
    foreach clock [lsort -unique $debug_clocks] {
        foreach property {PERIOD MASTER_CLOCK SOURCE_PINS IS_GENERATED WAVEFORM} {puts $h "DEBUG_ACTUAL_CLOCK\t$clock\t$property\t[m002_prop $clock $property]"}
    }
    if {$point eq "debug_materialized" && [llength $hubs] == 1} {
        set command [list write_xdc -cell $hubs -type timing -constraints ALL -write_id -force [file join $::m002_report_dir debug_hub_effective_${point}.xdc]]
        puts $h "DEBUG_EFFECTIVE_XDC_COMMAND\t$command"
        if {[catch {uplevel #0 $command} issue]} {puts $h "DEBUG_EFFECTIVE_XDC_UNKNOWN\t$issue"}
    }
    close $h
    set cores [get_debug_cores -quiet dbg_hub]
    set known_bb [expr {[llength $blackboxes] == 1 && [llength $hubs] == 1 &&
        [lindex $blackboxes 0] eq [lindex $hubs 0] && [lindex $hubs 0] eq "dbg_hub" &&
        [get_property REF_NAME [lindex $hubs 0]] eq "dbg_hub_CV"}]
    # get_debug_cores dbg_hub is a live debug-core object whose NAME is its
    # associated design cell. Preserve its entire property set above.
    set associated [expr {[llength $cores] == 1 && [get_property NAME $cores] eq "dbg_hub" &&
        [llength [get_debug_ports -quiet dbg_hub/*]] > 0}]
    m002_put [file join $::m002_report_dir debug_proof_${point}.txt] "verified=[expr {$known_bb && $associated && [lsort -unique $families] eq {0 1}}]\nblackbox_count=[llength $blackboxes]\ncell=$hubs\ncore=$cores\nsource=live_get_debug_cores_and_unique_associated_cell"
}

proc m002_probe_netlist {point} {
    source [file join $::m002_report_dir probe_targets.tcl]
    set h [open [file join $::m002_report_dir reset_cdc_and_io_probe_${point}.tsv] w]
    foreach target $::m002_cdc_targets {
        set pin [m002_exact get_pins $target]
        puts $h "CDC_TARGET\t$target\tMATCHES=[llength $pin]"
        if {[llength $pin] != 1} {error "CDC probe target missing: $target"}
        set cell [get_cells -quiet -of_objects $pin]
        set parent [file dirname $cell]
        set related [get_cells -quiet -hier -filter [format {NAME =~ %s/*} $parent]]
        puts $h "SIBLINGS\tTOTAL=[llength $related]\tLIMIT=64"
        m002_dump_cells $h [lrange $related 0 63]
        set cone [all_fanin -quiet -flat -levels 4 -to $pin -only_cells]
        puts $h "FANIN_CONE\t$target\tCELLS=[llength $cone]"
        m002_dump_cells $h $cone
    }
    foreach name {pcie_perstn ddr4_sdram_c1_reset_n ddr4_sdram_c2_reset_n} {
        set port [get_ports -quiet $name]
        puts $h "RESET_IO\t$name\tMATCHES=[llength $port]\tCLOCKS=[get_clocks -quiet -of_objects $port]"
        foreach net [get_nets -quiet -of_objects $port] {
            foreach pin [get_pins -quiet -leaf -of_objects $net] {puts $h "IO_PIN\t$pin"}
        }
        if {[get_property DIRECTION $port] eq "IN"} {
            foreach pin [all_fanout -quiet -flat -endpoints_only -from $port] {puts $h "IO_RECEIVER\t$pin"}
        } else {
            m002_dump_cells $h [all_fanin -quiet -flat -levels 3 -only_cells -to $port]
        }
    }
    close $h
    set h [open [file join $::m002_report_dir xpm_invalid_endpoint_probe_${point}.tsv] w]
    foreach ddr {0 1} {
        set pattern "*/d${ddr}_smc/inst/s00_nodes/s00_w_node/inst/inst_mi_handler/gen_normal_area.gen_fifo_req.inst_fifo_req/gen_xpm_memory_fifo.inst_fifo/gen_mem_rep*.inst_xpm_memory/xpm_memory_base_inst/*doutb*reg*"
        set targets [get_cells -quiet -hier -filter [format {NAME =~ %s} $pattern]]
        puts $h "VENDOR_ORIGINAL_QUERY_SCOPE\td${ddr}_smc/s00_w_node\tMATCHES=[llength $targets]"
        m002_dump_cells $h $targets
        foreach cell $targets {
            foreach pin [get_pins -quiet -of_objects $cell -filter {IS_CLOCK == 1}] {
                puts $h "TARGET_CLOCK\t$pin\t[m002_pin_clocks $pin]"
            }
            if {$point eq "debug_materialized" && [get_property IS_SEQUENTIAL $cell]} {
                set endpoint [get_pins -quiet -of_objects $cell -filter {REF_PIN_NAME == D}]
                puts $h "LEGAL_EXCEPTION_TARGET\t$cell\t$endpoint"
                if {[llength $endpoint] != 1} {puts $h "LEGAL_EXCEPTION_TARGET_UNKNOWN\t$cell";continue}
                set base [file join $::m002_report_dir xpm_d${ddr}_effective_${point}]
                # Keep actual object filtering and ignored-constraint precedence;
                # a global coverage count cannot identify these legal endpoints.
                foreach {label command} [list effective [list report_exceptions -to $cell -file ${base}_exceptions.rpt] ignored [list report_exceptions -to $cell -ignored -file ${base}_ignored.rpt] scope_override [list report_exceptions -to $cell -scope_override -file ${base}_scope_override.rpt] valid [list report_exceptions -to $cell -write_valid_exceptions -file ${base}_valid.xdc]] {
                    puts $h "EXCEPTION_QUERY\t$label\t$command"
                    if {[catch {uplevel #0 $command} issue]} {m002_put ${base}_${label}_unavailable.txt "command=$command\nissue=$issue"}
                }
                if {[catch {report_timing -to $endpoint -delay_type max -max_paths 4 -nworst 4 -input_pins -nets -file ${base}_timing.rpt} issue]} {m002_put ${base}_timing_unavailable.txt $issue}
                foreach path [get_timing_paths -quiet -to $endpoint -delay_type max -max_paths 4 -nworst 4] {
                    foreach property [lsort [list_property $path]] {puts $h "LEGAL_TIMING_PATH_PROPERTY\t$cell\t$property\t[m002_prop $path $property]"}
                }
            }
        }
    }
    close $h
    # A004's specific surviving instance; no new all-warning hierarchy scan.
    set parent scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_attention/u_compute/g_projection_rtl.u_projection/u_array/u_center12/u_region2_cols8_11/g_dual_accumulator.u_accumulator
    set h [open [file join $::m002_report_dir head_wave_local_${point}.tsv] w]
    foreach pattern {*head_wave* *tail_wave* *lockstep_error_r_reg*} {
        set cells [get_cells -quiet -hier -filter [format {NAME =~ %s/%s} $parent $pattern]]
        puts $h "LOCAL_CLASS\t$pattern\tACTUAL_CELLS=[llength $cells]"
        m002_dump_cells $h $cells
        foreach cell $cells {
            foreach pin [get_pins -quiet -of_objects $cell -filter {REF_PIN_NAME == D || REF_PIN_NAME == CE}] {
                set cone [all_fanin -quiet -flat -levels 3 -only_cells -to $pin]
                puts $h "CONTROL_CONE\t$pin\tTOTAL=[llength $cone]\tLIMIT=64"
                if {[llength $cone] <= 64} {m002_dump_cells $h $cone}
            }
        }
    }
    foreach side {u_lower_bank u_upper_bank} {
        set cells [get_cells -quiet -hier -filter [format {NAME =~ %s/g_physical_split.%s/in_ready_INST*} $parent $side]]
        puts $h "READY_CLASS\t$side\tACTUAL_CELLS=[llength $cells]"
        m002_dump_cells $h $cells
    }
    close $h
}
proc m002_counts {point} {
    set h [open [file join $::m002_report_dir check_timing_${point}.rpt] r]
    set text [read $h]; close $h
    set result [dict create]
    foreach line [split $text \n] {
        if {[regexp {^[0-9]+\. checking ([a-z_]+) \(([0-9]+)\)} $line -> name count]} {dict set result $name $count}
    }
    return $result
}
proc m002_exact {command name} {
    # NAME == is literal equality; Vivado's glob handling of escaped array
    # brackets differs from Tcl glob. Restrict pin queries to the exact cell.
    if {$command eq "get_pins"} {
        set parent [file dirname $name]
        set leaf [file tail $name]
        set cell [get_cells -quiet -hier -filter [format {NAME == "%s"} $parent]]
        if {[llength $cell] != 1} {return [list]}
        return [get_pins -quiet -of_objects $cell -filter [format {REF_PIN_NAME == "%s"} $leaf]]
    }
    return [$command -quiet -hier -filter [format {NAME == "%s"} $name]]
}
proc m002_pin_clocks {pin} {
    # Data pins do not establish the receiver clock. Preserve the actual C/CLK
    # clock and all D/CE/R/CLR nets without repeating timing walks per data pin.
    if {[m002_prop $pin IS_CLOCK] in {1 true TRUE} ||
        [regexp -nocase {^(C|CLK|CLKA|CLKB|RDCLK|WRCLK)$} [m002_prop $pin REF_PIN_NAME]]} {
        return [get_clocks -quiet -of_objects $pin]
    }
    return ""
}
proc m002_reset_snapshot {point} {
    source [file join $::m002_report_dir probe_targets.tcl]
    set cells [list]
    set h [open [file join $::m002_report_dir reset_graph_${point}.tsv] w]
    # Logical inversion properties may be absent. Export only the 11 small
    # reset blocks with all primitive overrides explicitly written by Vivado.
    set scopes [list]
    foreach {gate module} {core_gate u_base_reset_cdc core_gate u_ready0_cdc core_gate u_ready1_cdc d0_gate u_base_reset_cdc d0_gate u_ready_cdc d1_gate u_base_reset_cdc d1_gate u_ready_cdc} {
        lappend scopes scalellm_vcu118_f05_bd_i/$gate/inst/$module
    }
    foreach ddr {0 1} {
        foreach psr {psr0 psr_aclk1} {lappend scopes scalellm_vcu118_f05_bd_i/d${ddr}_smc/inst/clk_map/$psr/U0/EXT_LPF/ACTIVE_LOW_AUX.ACT_LO_AUX}
    }
    foreach psr {psr_aclk1 psr0 psr_aclk2} {
        set scope scalellm_vcu118_f05_bd_i/host_split/inst/clk_map/$psr/U0/EXT_LPF/ACTIVE_LOW_AUX.ACT_LO_AUX
        lappend scopes $scope
        set chain [get_cells -quiet -hier -filter [format {NAME =~ %s/*} $scope]]
        set cells [concat $cells [filter $chain {IS_PRIMITIVE == 1}]]
        set cells [concat $cells [m002_exact get_cells scalellm_vcu118_f05_bd_i/host_split/inst/clk_map/$psr/U0/EXT_LPF/lpf_asr_reg]]
        foreach pin [get_pins -quiet -of_objects [m002_exact get_cells $scope] -filter {DIRECTION == IN}] {
            puts $h "GATE_INPUT\t$pin\t[all_fanin -quiet -flat -startpoints_only -to $pin]"
            set segments [get_nets -quiet -segments -of_objects $pin]
            set drivers [get_pins -quiet -leaf -of_objects $segments -filter {DIRECTION == OUT}]
            puts $h "PIN\t$pin\t[m002_prop $pin REF_PIN_NAME]\t[m002_prop $pin DIRECTION]\t[lsort $segments]\t[m002_pin_clocks $pin]\t$drivers"
            set cells [concat $cells [all_fanin -quiet -flat -levels 5 -only_cells -to $pin]]
        }
    }
    set index 0
    foreach scope $scopes {
        set path [file join $::m002_report_dir reset_primitive_overrides_${point}_${index}.v]
        set object [m002_exact get_cells $scope]
        set command [list write_verilog -cell $object -mode funcsim -write_all_overrides true -force $path]
        puts $h "NETLIST_SCOPE_COMMAND\t$scope\t$command"
        if {[llength $object] != 1 || [catch {uplevel #0 $command} issue]} {
            puts $h "NETLIST_SCOPE_UNKNOWN\t$scope"
        } else {puts $h "NETLIST_SCOPE\t$scope\t$path"}
        incr index
    }
    foreach target $::m002_cdc_targets {
        set pin [m002_exact get_pins $target]
        if {[llength $pin] != 1} {error "CDC target no longer unique: $target"}
        set parent [file dirname [file dirname $target]]
        set chain [get_cells -quiet -hier -filter [format {NAME =~ %s/*} $parent]]
        set cells [concat $cells $chain [all_fanin -quiet -flat -levels 5 -only_cells -to $pin]]
        puts $h "TARGET\t$target"
    }
    # Include every stage and every source qualifier of all reset gates.
    foreach gate {core_gate d0_gate d1_gate} {
        foreach cell [get_cells -quiet -hier -filter [format {NAME =~ scalellm_vcu118_f05_bd_i/%s/inst/*} $gate]] {
            if {[get_property IS_PRIMITIVE $cell]} {lappend cells $cell}
        }
        foreach pin [get_pins -quiet scalellm_vcu118_f05_bd_i/$gate/inst/*] {
            if {[get_property DIRECTION $pin] eq "IN" && [get_property REF_PIN_NAME $pin] ne "clk"} {
                puts $h "GATE_INPUT\t$pin\t[all_fanin -quiet -flat -startpoints_only -to $pin]"
                set segments [get_nets -quiet -segments -of_objects $pin]
                set drivers [get_pins -quiet -leaf -of_objects $segments -filter {DIRECTION == OUT}]
                puts $h "PIN\t$pin\t[m002_prop $pin REF_PIN_NAME]\t[m002_prop $pin DIRECTION]\t[lsort $segments]\t[m002_pin_clocks $pin]\t$drivers"
                set cells [concat $cells [all_fanin -quiet -flat -levels 5 -only_cells -to $pin]]
            }
        }
    }
    foreach name {pcie_perstn ddr4_sdram_c1_reset_n ddr4_sdram_c2_reset_n} {
        set port [get_ports -quiet $name]
        if {[llength $port] != 1} {error "Missing reset IO $name"}
        if {[get_property DIRECTION $port] eq "IN"} {
            set endpoints [all_fanout -quiet -flat -endpoints_only -from $port]
            foreach pin $endpoints {
                set cell [get_cells -quiet -of_objects $pin]
                puts $h "IO_RECEIVER\t$name\t$pin\t[get_property REF_NAME $cell]"
                set cells [concat $cells $cell [all_fanin -quiet -flat -levels 2 -only_cells -to $pin]]
            }
        } else {
            set cone [all_fanin -quiet -flat -levels 3 -only_cells -to $port]
            puts $h "IO_OUTPUT\t$name\t[all_fanin -quiet -flat -startpoints_only -to $port]"
            set cells [concat $cells $cone]
        }
    }
    # CE/D/R constants may be shared outside a reset hierarchy. Retain their
    # actual immediate drivers rather than inferring constants from net names.
    foreach cell [lsort -unique $cells] {
        if {[m002_prop $cell REF_NAME] ni {FDCE FDRE}} {continue}
        foreach pin [get_pins -quiet -of_objects $cell -filter {REF_PIN_NAME == CE || REF_PIN_NAME == D || REF_PIN_NAME == CLR || REF_PIN_NAME == R}] {
            set cells [concat $cells [all_fanin -quiet -flat -levels 1 -only_cells -to $pin]]
        }
    }
    foreach cell [lsort -unique $cells] {
        puts $h "CELL\t$cell\t[m002_prop $cell REF_NAME]\t[m002_prop $cell INIT]\t[m002_prop $cell ASYNC_REG]\tIS_C_INVERTED=[m002_prop $cell IS_C_INVERTED]\tIS_CLR_INVERTED=[m002_prop $cell IS_CLR_INVERTED]\tIS_R_INVERTED=[m002_prop $cell IS_R_INVERTED]"
        if {[get_property REF_NAME $cell] in {FDCE FDRE}} {
            foreach property [lsort [list_property $cell]] {puts $h "CELL_PROPERTY\t$cell\t$property\t[m002_prop $cell $property]"}
        }
        foreach pin [get_pins -quiet -of_objects $cell] {
            set segments [get_nets -quiet -segments -of_objects $pin]
            set drivers [get_pins -quiet -leaf -of_objects $segments -filter {DIRECTION == OUT}]
            puts $h "PIN\t$pin\t[m002_prop $pin REF_PIN_NAME]\t[m002_prop $pin DIRECTION]\t[lsort $segments]\t[m002_pin_clocks $pin]\t$drivers"
            if {[get_property REF_NAME $cell] in {FDCE FDRE}} {
                foreach property [lsort [list_property $pin]] {puts $h "PIN_PROPERTY\t$pin\t$property\t[m002_prop $pin $property]"}
            }
        }
    }
    close $h
}
proc m002_endpoint_clocks {receiver} {
    if {[llength $receiver] != 1} {return ""}
    set clock_pins [get_pins -quiet -of_objects $receiver -filter {IS_CLOCK == 1}]
    if {![llength $clock_pins]} {return ""}
    return [get_clocks -quiet -of_objects $clock_pins]
}
proc m002_cdc_change_probe {point} {
    source [file join $::m002_report_dir probe_targets.tcl]
    set h [open [file join $::m002_report_dir cdc_changed_reset_${point}.tsv] w]
    if {![info exists ::m002_actual_critical_sources]} {
        puts $h "OBSERVED_SOURCE_SET_UNAVAILABLE\tno inherited completed actual CDC report"
        close $h
        return
    }
    # Actual report source Qs, not only the two newly numbered CDC-11 endpoints.
    set cells [list]
    foreach source $::m002_actual_critical_sources {
        set pin [m002_exact get_pins $source]
        puts $h "ACTUAL_CRITICAL_SOURCE\t$source\tMATCHES=[llength $pin]"
        if {[llength $pin] != 1} {puts $h "SOURCE_UNKNOWN\t$source";continue}
        set cell [get_cells -quiet -of_objects $pin]
        lappend cells $cell
        foreach q [get_pins -quiet -of_objects $cell -filter {REF_PIN_NAME == Q}] {
            puts $h "SOURCE_Q\t$source\t$q\tC_CLOCKS=[get_clocks -quiet -of_objects $pin]"
            set endpoints [all_fanout -quiet -flat -endpoints_only -from $q]
            puts $h "SOURCE_Q_FANOUT_COUNT\t$q\t[llength $endpoints]\tLIMIT=8192"
            if {[llength $endpoints] > 8192} {puts $h "SOURCE_Q_FANOUT_UNKNOWN\t$q\tbounded count exceeded";continue}
            foreach endpoint $endpoints {
                set receiver [get_cells -quiet -of_objects $endpoint]
                set clock_pins [get_pins -quiet -of_objects $receiver -filter {IS_CLOCK == 1}]
                puts $h "SOURCE_Q_ENDPOINT\t$q\t$endpoint\t[m002_prop $receiver REF_NAME]\tCLOCKS=[m002_endpoint_clocks $receiver]"
            }
        }
    }
    foreach target $::m002_actual_critical_targets {
        set pin [m002_exact get_pins $target]
        puts $h "ACTUAL_CRITICAL_TARGET\t$target\tMATCHES=[llength $pin]"
        if {[llength $pin] != 1} {puts $h "TARGET_UNKNOWN\t$target";continue}
        set cone [all_fanin -quiet -flat -levels 6 -only_cells -to $pin]
        puts $h "TARGET_SOURCE_CONE\t$target\t[llength $cone]\tLIMIT=128"
        if {[llength $cone] <= 128} {set cells [concat $cells $cone]}
    }
    foreach ddr {0 1} {
        set name scalellm_vcu118_f05_bd_i/d${ddr}_gate/inst/u_base_reset_cdc/arststages_ff_reg\[3\]
        set final [m002_exact get_cells $name]
        foreach q [get_pins -quiet -of_objects $final -filter {REF_PIN_NAME == Q}] {
            set endpoints [all_fanout -quiet -flat -endpoints_only -from $q]
            puts $h "BASE_RESET_Q_FANOUT_COUNT\t$q\t[llength $endpoints]\tLIMIT=8192"
            if {[llength $endpoints] > 8192} {puts $h "BASE_RESET_Q_FANOUT_UNKNOWN\t$q";continue}
            foreach endpoint $endpoints {
                set receiver [get_cells -quiet -of_objects $endpoint]
                set clock_pins [get_pins -quiet -of_objects $receiver -filter {IS_CLOCK == 1}]
                puts $h "BASE_RESET_Q_ENDPOINT\t$q\t$endpoint\t[m002_prop $receiver REF_NAME]\tCLOCKS=[m002_endpoint_clocks $receiver]"
            }
        }
    }
    # The three same-UI HostSplit reset chains identified in the actual report.
    set index 0
    foreach psr {psr_aclk1 psr0 psr_aclk2} {
        set scope scalellm_vcu118_f05_bd_i/host_split/inst/clk_map/$psr/U0/EXT_LPF/ACTIVE_LOW_AUX.ACT_LO_AUX
        set object [m002_exact get_cells $scope]
        set path [file join $::m002_report_dir cdc_host_reset_overrides_${point}_${index}.v]
        set command [list write_verilog -cell $object -mode funcsim -write_all_overrides true -force $path]
        puts $h "HOST_RESET_EXPORT_COMMAND\t$scope\t$command"
        if {[llength $object] != 1 || [catch {uplevel #0 $command} issue]} {
            puts $h "HOST_RESET_EXPORT_UNKNOWN\t$scope"
        } else {puts $h "HOST_RESET_EXPORT\t$scope\t$path"}
        set chain [get_cells -quiet -hier -filter [format {NAME =~ %s/syncstages_ff_reg*} $scope]]
        puts $h "HOST_RESET_CHAIN\t$scope\t[llength $chain]"
        set cells [concat $cells $chain]
        set final [m002_exact get_cells ${scope}/syncstages_ff_reg\[3\]]
        foreach q [get_pins -quiet -of_objects $final -filter {REF_PIN_NAME == Q}] {
            set endpoints [all_fanout -quiet -flat -endpoints_only -from $q]
            puts $h "HOST_RESET_Q_FANOUT_COUNT\t$q\t[llength $endpoints]\tLIMIT=8192"
            if {[llength $endpoints] > 8192} {puts $h "HOST_RESET_Q_FANOUT_UNKNOWN\t$q";continue}
            foreach endpoint $endpoints {
                set receiver [get_cells -quiet -of_objects $endpoint]
                set clock_pins [get_pins -quiet -of_objects $receiver -filter {IS_CLOCK == 1}]
                puts $h "HOST_RESET_Q_ENDPOINT\t$q\t$endpoint\t[m002_prop $receiver REF_NAME]\tCLOCKS=[m002_endpoint_clocks $receiver]"
            }
        }
        incr index
    }
    # Retain actual aliases/properties for sources, target cones and HostSplit.
    m002_dump_cells $h [lsort -unique $cells]
    if {$point ne "opt"} {close $h;return}
    set index 0
    foreach pair $::m002_actual_critical_clock_pairs {
        lassign $pair from to
        set name m002_changed_reset_${point}_${index}
        set command [list report_cdc -from [get_clocks -quiet $from] -to [get_clocks -quiet $to] -severity Critical -all_checks_per_endpoint -details -name $name -file [file join $::m002_report_dir cdc_changed_${point}_${index}.rpt]]
        puts $h "TARGETED_CDC_COMMAND\t$from\t$to\t$command"
        if {[catch {uplevel #0 $command} issue]} {puts $h "TARGETED_CDC_UNKNOWN\t$from\t$to\t$issue";incr index;continue}
        set violations [get_cdc_violations -quiet -name $name]
        puts $h "TARGETED_CDC_VIOLATION_COUNT\t$from\t$to\t[llength $violations]\tLIMIT=64"
        if {[llength $violations] > 64} {puts $h "TARGETED_CDC_VIOLATIONS_UNKNOWN\t$name";incr index;continue}
        foreach violation $violations {
            foreach property [lsort [list_property $violation]] {puts $h "CDC_VIOLATION_PROPERTY\t$name\t$violation\t$property\t[m002_prop $violation $property]"}
            foreach query {get_pins get_cells get_nets} {
                if {[catch {set objects [$query -quiet -of_objects $violation]} issue]} {puts $h "CDC_OBJECT_QUERY_UNKNOWN\t$violation\t$query\t$issue"} else {puts $h "CDC_ASSOCIATED_OBJECTS\t$violation\t$query\t$objects"}
            }
        }
        incr index
    }
    close $h
}
proc m002_post {point} {
    file mkdir $::m002_report_dir
    set inherited_opt [expr {[info exists ::env(HAP_RECOVERY_PHASE)] && $::env(HAP_RECOVERY_PHASE) eq "post_opt_pre_debug" && $point eq "opt" && $::env(HAP_RECOVERY_OPT_EVIDENCE_COMPLETE) eq "1"}]
    if {$inherited_opt} {
        # Exact same untransformed post-OPT DCP. These reports/command are inherited,
        # not fresh opt_design execution. Parent validation bound every source.
        foreach name {opt.dcp opt_command_result.txt timing_opt.rpt utilization_opt.rpt drc_opt.rpt check_timing_opt.rpt clocks_opt.rpt cdc_opt.rpt clock_interaction_opt.rpt exceptions_opt.rpt pulse_width_opt.rpt bus_skew_opt.rpt reset_cdc_and_io_probe_opt.tsv xpm_invalid_endpoint_probe_opt.tsv head_wave_local_opt.tsv} {
            file copy [file join $::env(HAP_RECOVERY_PARENT_REPORT) $name] [file join $::m002_report_dir $name]
        }
        set bb [get_cells -quiet -hier -filter {IS_BLACKBOX == 1}]
        m002_put [file join $::m002_report_dir opt_result.txt] "completed=0\nphase=opt\nblackboxes=[llength $bb]\nevidence_origin=inherited_identical_opt_checkpoint\nphysical_signoff=false"
        set h [open [file join $::m002_report_dir blackboxes_opt.tsv] w]
        m002_dump_cells $h $bb;close $h
        m002_dump_xdc opt
        m002_debug_probe opt $bb
        report_drc -file [file join $::m002_report_dir drc_opt_live.rpt]
        # New bounded evidence precedes the unchanged unknown-critical gate.
        m002_reset_snapshot opt
        m002_cdc_change_probe opt
        require_board_clock_groups
        require_no_drc_blockers physopt
        exec python3 [file join $::m002_script_dir m002_physical_evidence.py] hook-batch opt $::m002_report_dir
        set h [open [file join $::m002_report_dir admission_opt.txt] r];set admission [read $h];close $h
        m002_put [file join $::m002_report_dir opt_result.txt] "completed=1\ndiagnostic_eligible=0\ndebug_materialization_eligible=1\nphase=opt\nblackboxes=[llength $bb]\nclock_coverage=[dict get $admission clock_coverage]\nevidence_origin=inherited_identical_opt_checkpoint\nphysical_signoff=false"
        puts "M002_DIAGNOSTIC_OPT_INHERITED debug_materialization_only=true"
        return
    }
    set inherited_init [expr {[info exists ::env(HAP_EXECUTION_MODE)] && $::env(HAP_EXECUTION_MODE) eq "checkpoint_restored_commands" && $point eq "init"}]
    if {$inherited_init} {
        # Loaded, untransformed checkpoint and reports are explicitly inherited.
        foreach name {init.dcp utilization_init.rpt timing_init.rpt drc_init.rpt} {
            file copy [file join $::env(HAP_RECOVERY_PARENT_REPORT) $name] [file join $::m002_report_dir $name]
        }
    } else {
        write_checkpoint [file join $::m002_report_dir ${point}.dcp]
    }
    set bb [get_cells -quiet -hier -filter {IS_BLACKBOX == 1}]
    m002_put [file join $::m002_report_dir ${point}_result.txt] "completed=0\ndiagnostic_eligible=0\nphase=$point\nblackboxes=[llength $bb]\nphysical_signoff=false"
    set h [open [file join $::m002_report_dir blackboxes_${point}.tsv] w]
    m002_dump_cells $h $bb; close $h
    if {!$inherited_init} {
        report_utilization -file [file join $::m002_report_dir utilization_${point}.rpt]
        report_timing_summary -delay_type min_max -report_unconstrained -file [file join $::m002_report_dir timing_${point}.rpt]
        report_drc -file [file join $::m002_report_dir drc_${point}.rpt]
    } else {
        # Recreate live violation objects; the inherited text is historical.
        report_drc -file [file join $::m002_report_dir drc_init_live.rpt]
    }
    check_timing -verbose -file [file join $::m002_report_dir check_timing_${point}.rpt]
    report_clocks -file [file join $::m002_report_dir clocks_${point}.rpt]
    m002_dump_xdc $point
    if {$point in {init opt debug_materialized}} {m002_debug_probe $point $bb}
    report_cdc -details -file [file join $::m002_report_dir cdc_${point}.rpt]
    report_clock_interaction -delay_type min_max -file [file join $::m002_report_dir clock_interaction_${point}.rpt]
    report_exceptions -coverage -file [file join $::m002_report_dir exceptions_${point}.rpt]
    if {$point ne "init"} {
        report_pulse_width -all_violators -file [file join $::m002_report_dir pulse_width_${point}.rpt]
        report_bus_skew -file [file join $::m002_report_dir bus_skew_${point}.rpt]
    }
    if {$point in {place physopt route}} {
        report_utilization -slr -file [file join $::m002_report_dir utilization_slr_${point}.rpt]
        report_design_analysis -congestion -min_congestion_level 3 -file [file join $::m002_report_dir congestion_${point}.rpt]
        report_slr_crossing -max_nets 32 -file [file join $::m002_report_dir slr_crossing_${point}.rpt]
    }
    if {$point in {physopt route}} {
        report_control_sets -verbose -file [file join $::m002_report_dir control_sets_${point}.rpt]
        report_timing -delay_type max -max_paths 32 -nworst 1 -nets -input_pins -file [file join $::m002_report_dir paths_setup_${point}.rpt]
        report_timing -delay_type min -max_paths 32 -nworst 1 -nets -input_pins -file [file join $::m002_report_dir paths_hold_${point}.rpt]
        set h [open [file join $::m002_report_dir worst_per_clock_${point}.tsv] w]
        puts $h "destination_clock\tdelay_type\tstartpoint\tendpoint\tstart_clock\tend_clock\tslack\tlogic_delay\tnet_delay\tdata_path_delay\tlogic_levels"
        foreach clock [lsort [get_clocks -quiet]] {
            foreach type {max min} {
                set path [lindex [get_timing_paths -quiet -to $clock -delay_type $type -max_paths 1] 0]
                if {$path eq ""} {puts $h "$clock\t$type\tNO_PATH"; continue}
                set values [list $clock $type]
                foreach property {STARTPOINT_PIN ENDPOINT_PIN STARTPOINT_CLOCK ENDPOINT_CLOCK SLACK LOGIC_DELAY NET_DELAY DATAPATH_DELAY LOGIC_LEVELS} {
                    lappend values [m002_prop $path $property]
                }
                puts $h [join $values \t]
            }
        }
        close $h
    }
    if {$point eq "route"} {report_route_status -file [file join $::m002_report_dir route_status_route.rpt]}
    if {$point in {init opt debug_materialized}} {m002_probe_netlist $point}
    if {$point in {opt debug_materialized place physopt route}} {m002_reset_snapshot $point}
    if {$point in {opt debug_materialized place physopt route}} {m002_cdc_change_probe $point}
    # All available artifacts precede automatic structural/numeric admission.
    require_board_clock_groups
    require_no_drc_blockers [expr {$point eq "route" ? "post_route" : "physopt"}]
    exec python3 [file join $::m002_script_dir m002_physical_evidence.py] hook-batch $point $::m002_report_dir
    set h [open [file join $::m002_report_dir admission_${point}.txt] r]
    set admission [read $h]; close $h
    set coverage [dict get $admission clock_coverage]
    set eligible [dict get $admission diagnostic_eligible]
    set debug_eligible [dict get $admission debug_materialization_eligible]
    m002_put [file join $::m002_report_dir ${point}_result.txt] "completed=1\ndiagnostic_eligible=$eligible\ndebug_materialization_eligible=$debug_eligible\nphase=$point\nblackboxes=[llength $bb]\nclock_coverage=$coverage\nphysical_signoff=false\nreset_io_review=OPEN\ncdc_review=OPEN"
    puts "M002_DIAGNOSTIC_STEP_COMPLETED $point coverage=$coverage physical_signoff=false"
}
proc hash_file {path} {
    if {![file isfile $path] || [file size $path] == 0} {
        error "Missing or empty input $path"
    }
    return [lindex [exec sha256sum -- $path] 0]
}
proc require_disabled_ip_cache {} {
    set policy [string tolower [get_property IP_CACHE_PERMISSIONS [current_project]]]
    if {$policy ne "disable"} {
        error "IP cache must be disabled, got: $policy"
    }
    return $policy
}
proc write_identity {path} {
    set cache_policy [require_disabled_ip_cache]
    set handle [open $path w]
    puts $handle "vivado=[version -short]"
    puts $handle "project=[get_property NAME [current_project]]"
    puts $handle "part=[get_property PART [current_project]]"
    puts $handle "board=[get_property BOARD_PART [current_project]]"
    puts $handle "top=[get_property TOP [get_filesets sources_1]]"
    puts $handle "defines=[lsort [get_property verilog_define [get_filesets sources_1]]]"
    puts $handle "synth_strategy=[get_property -quiet STRATEGY [get_runs synth_1]]"
    puts $handle "synth_flow=[get_property -quiet FLOW [get_runs synth_1]]"
    puts $handle "ip_cache_permissions=$cache_policy"
    set index 0
    foreach kind {sources_1 constrs_1} {
        foreach file [lsort [get_files -quiet -of_objects [get_filesets $kind]]] {
            # Generated IP simulation outputs are not physical build inputs.
            # Synthesis materializes some and drops other promised outputs.
            if {$kind eq "sources_1" &&
                [regexp {/[^/]+\.gen/sources_1/bd/[^/]+/ip/[^/]+/[^/]+_sim_netlist\.(v|vhdl)$} $file] &&
                [get_property -quiet USED_IN_SYNTHESIS $file] eq "0" &&
                [get_property -quiet USED_IN_IMPLEMENTATION $file] in {"" "0"}} {
                continue
            }
            puts $handle "file.$index=$kind:$file:[get_property -quiet FILE_TYPE $file]:[get_property -quiet USED_IN_SYNTHESIS $file]:[get_property -quiet USED_IN_IMPLEMENTATION $file]"
            incr index
        }
    }
    close $handle
}
proc require_complete_run {name} {
    set run [get_runs -quiet $name]
    if {[llength $run] != 1} {
        error "Required fresh run is missing: $name"
    }
    set stale [string tolower [get_property -quiet NEEDS_REFRESH $run]]
    if {[get_property PROGRESS $run] ne "100%" ||
        ![string match "*Complete*" [get_property STATUS $run]] ||
        $stale in {1 true yes}} {
        error "Required fresh run is incomplete or stale: $name"
    }
}
proc require_completed_impl_step {step checkpoint launched_at} {
    set run [get_runs -quiet impl_1]
    if {[llength $run] != 1} {error "Board implementation run is missing"}
    set status [get_property STATUS $run]
    set stale [string tolower [get_property -quiet NEEDS_REFRESH $run]]
    set directory [file normalize [get_property DIRECTORY $run]]
    set done [file join $directory .$step.end.rst]
    set failed [file join $directory .$step.error.rst]
    set run_done [file join $directory .vivado.end.rst]
    set design [file join $directory $checkpoint]
    if {$stale ne "0" ||
        !([string match "Not started *" $status] ||
          [string match "*Complete*" $status]) ||
        ![file exists $done] || [file exists $failed] ||
        ![file exists $run_done] ||
        ![file isfile $design] || [file size $design] == 0 ||
        [file mtime $done] < $launched_at ||
        [file mtime $design] < $launched_at} {
        error "Board $step failed or is stale: status=$status"
    }
    return $design
}
proc require_no_drc_blockers {stage} {
    set blockers [list]
    foreach violation [get_drc_violations -quiet] {
        set severity [string tolower [get_property SEVERITY $violation]]
        if {$severity in {error {critical warning}}} {
            if {$stage in {pre_implementation pre_place physopt} &&
                $severity eq "critical warning" &&
                [regexp {^RTSTAT-13#[0-9]+$} $violation]} {
                puts "PRE_ROUTE_DRC_RETAINED stage=$stage violation=$violation severity=$severity"
                continue
            }
            lappend blockers $violation
        }
    }
    if {[llength $blockers]} {error "$stage DRC blockers: $blockers"}
}
proc require_clock_family {port_name primary_ns generated_ns} {
    set port [get_ports -quiet $port_name]
    if {[llength $port] != 1} {error "Missing physical clock port $port_name"}
    set primary [get_clocks -quiet -of_objects $port]
    if {[llength $primary] != 1} {
        error "$port_name needs one primary clock, found $primary"
    }
    set period [get_property PERIOD $primary]
    if {![string is double -strict $period] ||
        abs(double($period) - double($primary_ns)) > 0.001} {
        error "$port_name primary clock period is not $primary_ns ns: $period"
    }
    set family [get_clocks -quiet -include_generated_clocks -of_objects $port]
    if {[lsearch -exact $family $primary] < 0} {
        error "$port_name primary clock is absent from its family"
    }
    set found 0
    foreach clock $family {
        set period [get_property PERIOD $clock]
        if {$clock ne $primary && [string is double -strict $period] &&
            abs(double($period) - double($generated_ns)) <= 0.001} {
            set found 1
        }
    }
    if {!$found} {
        error "$port_name lacks a generated $generated_ns ns clock: $family"
    }
    return $family
}
proc require_board_clock_groups {} {
    set pcie [require_clock_family pcie_refclk_p 10.000 10.000]
    set ddr0 [require_clock_family default_250mhz_clk1_clk_p 4.000 5.000]
    set ddr1 [require_clock_family default_250mhz_clk2_clk_p 4.000 5.000]
    set combined [concat $pcie $ddr0 $ddr1]
    if {[llength [lsort -unique $combined]] != [llength $combined]} {
        error "PCIe, DDR0, and DDR1 clock families overlap"
    }
    puts "REAL_CLOCK_FAMILIES core=$pcie ddr0=$ddr0 ddr1=$ddr1"
}
