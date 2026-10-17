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
        puts $handle "CELL\t$cell\t[m002_prop $cell REF_NAME]\tINIT=[m002_prop $cell INIT]\tASYNC_REG=[m002_prop $cell ASYNC_REG]\tBLACKBOX=[m002_prop $cell IS_BLACKBOX]"
        foreach pin [get_pins -quiet -of_objects $cell] {
            set net [get_nets -quiet -of_objects $pin]
            puts $handle "PIN\t$pin\t[m002_prop $pin DIRECTION]\t$net\tCLOCKS=[get_clocks -quiet -of_objects $pin]"
        }
    }
}
proc m002_dump_xdc {point} {
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
    foreach ip [get_ips -quiet -all -filter {IPDEF =~ *:dbg_hub:*}] {
        foreach source [get_files -quiet -all -of_objects $ip -filter {FILE_TYPE == XDC}] {
            set path [file normalize [get_property NAME $source]]
            puts $h $path
            puts $provenance "$ip\t[get_property IPDEF $ip]\t$path"
        }
    }
    close $h; close $provenance
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
    foreach cell $hubs {
        foreach pin [get_pins -quiet -of_objects $cell] {
            set refpin [get_property REF_PIN_NAME $pin]
            if {![regexp {^sl_iport[01]_o\[1\]$} $refpin]} {continue}
            foreach endpoint [all_fanout -quiet -flat -endpoints_only -from $pin] {
                puts $h "DEBUG_CLOCK_FANOUT\t$pin\t$endpoint"
                if {[regexp {/ddr4_([01])/.*(U_XSDB_SLAVE|u_xsdb_arbiter)/} $endpoint -> ddr]} {
                    lappend families $ddr
                }
            }
        }
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
    set h [open [file join $::m002_report_dir reset_register_probe_${point}.tsv] w]
    foreach register $::m002_warning_registers {
        set cells [get_cells -quiet -hier -filter [format {NAME =~ *%s*} $register]]
        puts $h "REGISTER_CLASS\t$register\tACTUAL_CELLS=[llength $cells]"
        if {[string match *head_wave* $register]} {
            m002_dump_cells $h $cells
        } else {
            puts $h "REPRESENTATIVE_LIMIT\t16\tFULL_CLASS_COUNT=[llength $cells]"
            m002_dump_cells $h [lrange $cells 0 15]
        }
        foreach net [get_nets -quiet -hier -filter [format {NAME =~ *%s*} [string map {_reg {}} $register]]] {
            if {![string match *head_wave* $register]} {break}
            puts $h "HEAD_WAVE_NET\t$net"
            foreach pin [get_pins -quiet -leaf -of_objects $net] {puts $h "NET_PIN\t$pin"}
        }
    }
    close $h
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
                puts $h "TARGET_CLOCK\t$pin\t[get_clocks -quiet -of_objects $pin]"
            }
        }
    }
    close $h
    foreach pattern {*lockstep_error_r_reg* *head_wave*} {
        set cells [get_cells -quiet -hier -filter [format {NAME =~ %s} $pattern]]
        set h [open [file join $::m002_report_dir [string trim $pattern *]_fanin_${point}.tsv] w]
        foreach cell $cells {
            foreach pin [get_pins -quiet -of_objects $cell -filter {REF_PIN_NAME == D || REF_PIN_NAME == CE}] {
                puts $h "CONTROL\t$pin\t[get_nets -quiet -of_objects $pin]"
                m002_dump_cells $h [all_fanin -quiet -flat -levels 3 -only_cells -to $pin]
            }
        }
        close $h
    }
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
    regsub -all {([][?*\\])} $name {\\\1} pattern
    return [$command -quiet $pattern]
}
proc m002_reset_snapshot {point} {
    source [file join $::m002_report_dir probe_targets.tcl]
    set cells [list]
    set h [open [file join $::m002_report_dir reset_graph_${point}.tsv] w]
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
                puts $h "PIN\t$pin\t[m002_prop $pin REF_PIN_NAME]\t[m002_prop $pin DIRECTION]\t[lsort $segments]\t[get_clocks -quiet -of_objects $pin]\t$drivers"
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
    foreach cell [lsort -unique $cells] {
        puts $h "CELL\t$cell\t[m002_prop $cell REF_NAME]\t[m002_prop $cell INIT]\t[m002_prop $cell ASYNC_REG]"
        foreach pin [get_pins -quiet -of_objects $cell] {
            set segments [get_nets -quiet -segments -of_objects $pin]
            set drivers [get_pins -quiet -leaf -of_objects $segments -filter {DIRECTION == OUT}]
            puts $h "PIN\t$pin\t[m002_prop $pin REF_PIN_NAME]\t[m002_prop $pin DIRECTION]\t[lsort $segments]\t[get_clocks -quiet -of_objects $pin]\t$drivers"
        }
    }
    close $h
}
proc m002_post {point} {
    file mkdir $::m002_report_dir
    # Preserve the real state before any report or verdict can fail.
    write_checkpoint [file join $::m002_report_dir ${point}.dcp]
    set h [open [file join $::m002_report_dir ${point}_result.txt] w]
    puts $h "completed=0\ndiagnostic_eligible=0\nphase=$point\nphysical_signoff=false"; close $h
    set bb [get_cells -quiet -hier -filter {IS_BLACKBOX == 1}]
    set h [open [file join $::m002_report_dir blackboxes_${point}.tsv] w]
    m002_dump_cells $h $bb; close $h
    report_utilization -file [file join $::m002_report_dir utilization_${point}.rpt]
    report_timing_summary -delay_type min_max -report_unconstrained -file [file join $::m002_report_dir timing_${point}.rpt]
    check_timing -verbose -file [file join $::m002_report_dir check_timing_${point}.rpt]
    report_clocks -file [file join $::m002_report_dir clocks_${point}.rpt]
    report_drc -file [file join $::m002_report_dir drc_${point}.rpt]
    set counts [m002_counts $point]
    foreach name {no_clock unconstrained_internal_endpoints multiple_clock generated_clocks loops pulse_width_clock} {
        if {![dict exists $counts $name]} {error "Missing timing coverage category $name"}
    }
    # All phase records are preserved, including failed automatic admission.
    m002_put [file join $::m002_report_dir ${point}_result.txt] "completed=0\ndiagnostic_eligible=0\nphase=$point\nblackboxes=[llength $bb]\nphysical_signoff=false"
    m002_dump_xdc $point
    if {$point in {init opt}} {
        m002_debug_probe $point $bb
        m002_probe_netlist $point
        m002_reset_snapshot $point
    }
    report_cdc -details -file [file join $::m002_report_dir cdc_${point}.rpt]
    report_clock_interaction -delay_type min_max -file [file join $::m002_report_dir clock_interaction_${point}.rpt]
    report_exceptions -coverage -file [file join $::m002_report_dir exceptions_${point}.rpt]
    report_pulse_width -all_violators -file [file join $::m002_report_dir pulse_width_${point}.rpt]
    report_bus_skew -file [file join $::m002_report_dir bus_skew_${point}.rpt]
    require_board_clock_groups
    require_no_drc_blockers [expr {$point eq "route" ? "post_route" : "physopt"}]
    exec python3 [file join $::m002_script_dir m002_physical_evidence.py] hook-batch $point $::m002_report_dir
    set h [open [file join $::m002_report_dir admission_${point}.txt] r]
    set admission [read $h]; close $h
    set coverage [dict get $admission clock_coverage]
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
    m002_put [file join $::m002_report_dir ${point}_result.txt] "completed=1\ndiagnostic_eligible=1\ndiagnostic_opt_eligible=1\nphase=$point\nblackboxes=[llength $bb]\nclock_coverage=$coverage\nphysical_signoff=false\nreset_io_review=OPEN\ncdc_review=OPEN"
    puts "M002_DIAGNOSTIC_STEP_COMPLETED $point coverage=$coverage; timing is evaluated separately; physical_signoff=false"
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
