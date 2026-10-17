set script_dir [file dirname [file normalize [info script]]]
set root [file normalize [file join $script_dir ../..]]
foreach name {HAP_JOBS HAP_PROJECT_DIR HAP_REPORT_DIR HAP_STAGE} {
    if {![info exists ::env($name)] || $::env($name) eq ""} {
        error "Missing required input $name"
    }
}
set jobs $::env(HAP_JOBS)
set project_dir [file normalize $::env(HAP_PROJECT_DIR)]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set stage $::env(HAP_STAGE)
set project_name scalellm_vcu118_f05
set bd_name scalellm_vcu118_f05_bd
set project_file [file join $project_dir $project_name.xpr]
if {![string is integer -strict $jobs] || $jobs < 1 || $jobs > 32} {
    error "HAP_JOBS must be in 1..32"
}
set synth_jobs [expr {$jobs < 2 ? $jobs : 2}]
if {[info exists ::env(HAP_SYNTH_JOBS)]} {
    set synth_jobs $::env(HAP_SYNTH_JOBS)
    if {![string is integer -strict $synth_jobs] || $synth_jobs < 1 || $synth_jobs > 2} {error "HAP_SYNTH_JOBS must be 1 or 2"}
}
if {$stage ni {synth place route}} {error "HAP_STAGE must be synth, place or route"}
if {$stage in {place route}} {
    error "M002 physical checks are not adapted to the dedicated DDR hierarchy; legacy partition and terminal-count checks are inapplicable"
}
if {![string match "2025.2*" [version -short]]} {
    error "Expected Vivado 2025.2, got [version -short]"
}
if {![string match [file join $root vivado project *] $project_dir] ||
    ![file isfile $project_file] ||
    ![string match [file join $root vivado reports *] $report_dir]} {
    error "Project or report directory is outside the new hardware root"
}
if {![file isdirectory $report_dir] ||
    [file exists [file join $report_dir inputs.sha256]]} {
    error "Report directory is missing or already used: $report_dir"
}
if {$stage in {place route} &&
    ![file isfile [file join $root vivado constraints board_clock_domains.xdc]]} {
    error "Route requires reviewed generated-clock CDC constraints"
}
if {$stage in {place route}} {
    if {![info exists ::env(HAP_SYNTH_REPORT_DIR)] ||
        $::env(HAP_SYNTH_REPORT_DIR) eq ""} {
        error "Physical stages require HAP_SYNTH_REPORT_DIR from completed fresh synthesis"
    }
    set synth_report_dir [file normalize $::env(HAP_SYNTH_REPORT_DIR)]
    if {![string match [file join $root vivado reports *] $synth_report_dir] ||
        ![file isfile [file join $synth_report_dir fresh_synth_complete.txt]] ||
        ![file isfile [file join $synth_report_dir inputs.sha256]] ||
        ![file isfile [file join $synth_report_dir build_identity.txt]]} {
        error "Route requires a completed same-root synthesis report: $synth_report_dir"
    }
}
set_param general.maxThreads $jobs

proc hash_file {path} {
    if {![file isfile $path] || [file size $path] == 0} {
        error "Missing or empty input $path"
    }
    return [lindex [exec sha256sum -- $path] 0]
}
proc source_files {root project_dir} {
    set paths [list \
        [file join $root vivado scripts create_vcu118_board.tcl] \
        [file join $root vivado scripts build_vcu118_board.tcl] \
        [file join $root vivado scripts run_vcu118_board.sh] \
        [file join $root vivado scripts emit_current_board_evidence.py] \
        [file join $root vivado scripts m002_synth_threads.tcl] \
        [file join $root vivado scripts m002_optimized_structure.tcl] \
        [file join $root vivado constraints attention_mlp_vcu118_board_v5.xdc] \
        /home/user/EDA-202/vivado/vivado_2025.2/2025.2/data/xhub/boards/XilinxBoardStore/boards/Xilinx/vcu118/2.0/board.xml \
        /home/user/EDA-202/vivado/vivado_2025.2/2025.2/data/xhub/boards/XilinxBoardStore/boards/Xilinx/vcu118/2.0/part0_pins.xml \
        /home/user/EDA-202/vivado/vivado_2025.2/2025.2/data/xhub/boards/XilinxBoardStore/boards/Xilinx/vcu118/2.0/preset.xml]
    foreach path [glob -nocomplain -directory [file join $root vivado manifests] *.list] {
        lappend paths $path
    }
    set clock_xdc [file join $root vivado constraints board_clock_domains.xdc]
    if {[file exists $clock_xdc]} {lappend paths $clock_xdc}
    foreach file [get_files -quiet -of_objects [get_filesets constrs_1]] {
        lappend paths [file normalize $file]
    }
    foreach file [get_files -quiet -of_objects [get_filesets sources_1]] {
        set path [file normalize $file]
        if {[string match [file join $root rtl *] $path] ||
            [string match [file join $root data *] $path] ||
            [file extension $path] eq ".bd"} {
            lappend paths $path
        }
    }
    set wrapper [file join $project_dir scalellm_vcu118_f05.gen sources_1 \
        bd scalellm_vcu118_f05_bd hdl scalellm_vcu118_f05_bd_wrapper.v]
    lappend paths $wrapper
    set generated [string trim [exec find $project_dir -type f -name *.xci]]
    if {$generated eq ""} {error "Generated XCI inputs are missing"}
    foreach path [split $generated "\n"] {lappend paths [file normalize $path]}
    return [lsort -unique $paths]
}
proc write_input_manifest {paths output} {
    set saved [dict create]
    set handle [open $output w]
    foreach path $paths {
        # Native file objects become invalid after project close; bind strings.
        set path [encoding convertfrom utf-8 [encoding convertto utf-8 $path]]
        set digest [hash_file $path]
        puts $handle "$digest  $path"
        dict set saved $path $digest
    }
    close $handle
    return $saved
}
proc verify_inputs {saved} {
    dict for {path expected} $saved {
        if {[hash_file $path] ne $expected} {
            error "Input changed during build: $path"
        }
    }
}
proc synth_rom_sources {root} {
    set pins [dict create \
        [file join $root data softmax_exp_u17.mem] \
            3af91ffa7ead647b42b8440c9a098d84b0abb81ffdc09c96550c724bf7248967 \
        [file join $root data mlp_silu_q16.mem] \
            8263e8981b637b00143c6dfd6674f2397a73c85c6ed8934f0ee839f76db6ea67]
    dict for {path expected} $pins {
        if {[hash_file $path] ne $expected} {
            error "Source ROM hash mismatch: $path"
        }
    }
    return $pins
}
proc synth_runs {} {
    set top [get_runs -quiet synth_1]
    if {[llength $top] != 1} {error "Top synthesis run is missing"}
    return [lsort -unique [concat $top \
        [get_runs -quiet -filter {NAME =~ *_synth_1}]]]
}
proc synth_rom_paths {} {
    set paths [list]
    foreach run [synth_runs] {
        set directory [get_property DIRECTORY $run]
        if {$directory eq ""} {
            error "Synthesis run has no DIRECTORY: [get_property NAME $run]"
        }
        foreach name {softmax_exp_u17.mem mlp_silu_q16.mem} {
            lappend paths [file join [file normalize $directory] data $name]
        }
    }
    return [lsort -unique $paths]
}
proc stage_synth_roms {root source_pins} {
    set expected_pins [synth_rom_sources $root]
    if {[dict size $source_pins] != [dict size $expected_pins]} {
        error "Source ROM pin set differs from frozen ROMs"
    }
    dict for {path expected} $expected_pins {
        if {![dict exists $source_pins $path] ||
            [dict get $source_pins $path] ne $expected} {
            error "Source ROM pin differs from frozen ROM: $path"
        }
    }
    set paths [synth_rom_paths]
    foreach path $paths {
        set source [file join $root data [file tail $path]]
        file mkdir [file dirname $path]
        file copy -force -- $source $path
        if {[hash_file $path] ne [dict get $expected_pins $source]} {
            error "Staged ROM hash mismatch: $path"
        }
    }
    return $paths
}
proc verify_synth_roms {root inputs} {
    set pins [synth_rom_sources $root]
    foreach path [concat [dict keys $pins] [synth_rom_paths]] {
        set source [file join $root data [file tail $path]]
        set expected [dict get $pins $source]
        if {![dict exists $inputs $path] ||
            [dict get $inputs $path] ne $expected ||
            [hash_file $path] ne $expected} {
            error "Source or staged ROM is missing or changed: $path"
        }
    }
}
proc reject_synth_rom_warnings {} {
    foreach run [synth_runs] {
        set directory [get_property DIRECTORY $run]
        if {$directory eq ""} {
            error "Synthesis run has no DIRECTORY: [get_property NAME $run]"
        }
        set log [file join [file normalize $directory] runme.log]
        if {![file isfile $log] || [file size $log] == 0} {
            error "Missing or empty synthesis runme.log: $log"
        }
        set handle [open $log r]
        while {[gets $handle line] >= 0} {
            if {[regexp -nocase {Synth[[:space:]]+8-4445} $line]} {
                close $handle
                error "Unresolved synthesis ROM warning in $log: $line"
            }
        }
        close $handle
    }
}
proc require_disabled_ip_cache {} {
    set policy [string tolower [get_property IP_CACHE_PERMISSIONS [current_project]]]
    if {$policy ne "disable"} {
        error "IP cache must be disabled, got: $policy"
    }
    return $policy
}
proc require_child_ip_cache_policy {require_scripts} {
    foreach run [synth_runs] {
        set directory [get_property DIRECTORY $run]
        if {$directory eq ""} {
            error "Synthesis run has no DIRECTORY: [get_property NAME $run]"
        }
        set scripts [glob -nocomplain -directory [file normalize $directory] *.tcl]
        if {$require_scripts && [llength $scripts] != 1} {
            error "Missing or ambiguous synthesis run Tcl: $directory"
        }
        foreach script $scripts {
            set handle [open $script r]
            set contents [read $handle]
            close $handle
            set assignments 0
            foreach line [split $contents "\n"] {
                set line [string trimright $line "\r"]
                if {![regexp -nocase \
                    {^[ \t]*set_property[ \t]+ip_cache_permissions([ \t]|$)} $line]} {
                    continue
                }
                incr assignments
                if {![regexp -nocase \
                    {^[ \t]*set_property[ \t]+ip_cache_permissions[ \t]+(\{disable\}|disable)[ \t]+\[current_project\][ \t]*$} \
                    $line]} {
                    error "Synthesis child IP cache is not disabled: $script"
                }
            }
            if {$assignments != 1} {
                error "Synthesis child IP cache assignment count is $assignments: $script"
            }
        }
    }
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
proc require_file {name} {
    set files [get_files -quiet -of_objects [get_filesets sources_1] \
        -filter "NAME =~ */$name"]
    if {[llength $files] != 1} {
        error "Required selected source is not unique: $name ($files)"
    }
}
proc reject_file {name} {
    set files [get_files -quiet -of_objects [get_filesets sources_1] \
        -filter "NAME =~ */$name"]
    if {[llength $files]} {error "Stale source selected: $name"}
}
proc require_bd_number {cell key expected} {
    set actual [get_property CONFIG.$key [get_bd_cells $cell]]
    if {![string is double -strict $actual] ||
        double($actual) != double($expected)} {
        error "$cell CONFIG.$key expected=$expected actual=$actual"
    }
}
proc require_bd_clock {pin expected} {
    set actual [get_property -quiet CONFIG.FREQ_HZ $pin]
    if {$actual eq ""} {set actual [get_property -quiet FREQ_HZ $pin]}
    if {![string is double -strict $actual] ||
        double($actual) != double($expected)} {
        error "$pin clock metadata expected=$expected actual=$actual"
    }
}
# Re-audit actual BD objects so stale two-input DDR1 projects cannot build.
proc require_m002_link {source target} {
    set a [get_bd_intf_pins -quiet $source]
    set b [get_bd_intf_pins -quiet $target]
    if {[llength $a] != 1 || [llength $b] != 1} {error "Missing M002 link $source -> $target"}
    set an [get_bd_intf_nets -quiet -of_objects $a]
    set bn [get_bd_intf_nets -quiet -of_objects $b]
    if {[llength $an] != 1 || $an ne $bn} {error "Wrong M002 link $source -> $target"}
}
proc require_m002_data_map {interface target} {
    set spaces [get_bd_addr_spaces -quiet -of_objects [get_bd_intf_pins $interface]]
    if {[llength $spaces] != 1} {error "Missing M002 address space $interface"}
    set segments [get_bd_addr_segs -quiet -of_objects $spaces]
    if {[llength $segments] != 1 || ![string match "*$target*" [lindex $segments 0]]} {
        error "M002 data interface $interface must target only $target: $segments"
    }
    set segment [lindex $segments 0]
    if {[expr {wide([get_property OFFSET $segment])}] != 0 ||
        [expr {wide([get_property RANGE $segment])}] != 0x80000000} {
        error "M002 data interface $interface requires a local 2 GiB address space"
    }
}
proc require_m002_bd {} {
    foreach cell {d0_smc d1_smc} {
        require_bd_number $cell NUM_SI 3
        require_bd_number $cell NUM_MI 1
        require_bd_number $cell NUM_CLKS 2
    }
    foreach {source target} {
        core/M_AXI_DATA d0_smc/S00_AXI
        core/M_AXI_MLP_DATA d1_smc/S00_AXI
        core/M_AXI_WEIGHT_C0 d0_smc/S01_AXI
        core/M_AXI_WEIGHT_C1 d1_smc/S02_AXI
        host_split/M00_AXI d0_smc/S02_AXI
        host_split/M01_AXI d1_smc/S01_AXI
    } {require_m002_link $source $target}
    require_m002_data_map core/M_AXI_DATA ddr4_0
    require_m002_data_map core/M_AXI_MLP_DATA ddr4_1
    foreach cell {d0_smc d1_smc} {
        set net [get_bd_nets -quiet -of_objects [get_bd_pins $cell/aclk1]]
        set core [get_bd_nets -quiet -of_objects [get_bd_pins core/core_clk]]
        if {[llength $net] != 1 || $net ne $core} {error "$cell lacks the core100 CDC clock"}
    }
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

open_project $project_file
config_ip_cache -disable_cache
require_disabled_ip_cache
foreach name {
    attention_mlp_vcu118_board_v5.xdc
    vcu118_ddr4_explicit_pins.xdc
    board_clock_domains.xdc
    ddr_timing_recovery.xdc
} {
    set path [file normalize [file join $root vivado constraints $name]]
    set active [get_files -quiet -of_objects [get_filesets constrs_1] $path]
    if {[llength $active] != 1} {
        error "Required board XDC is not active in constrs_1: $path"
    }
    if {$name eq "board_clock_domains.xdc" &&
        [get_property PROCESSING_ORDER $active] ne "LATE"} {
        error "Clock-domain XDC must follow the generated IP clock constraints"
    }

}
foreach name {mission0004_metadata_width_local.xdc mission0005_coordinated_partition.xdc} {
    set legacy [get_files -quiet -of_objects [get_filesets constrs_1] "*/$name"]
    if {[llength $legacy]} {error "Legacy native025 physical constraints are not M002 inputs: $name"}
}
if {[get_property PART [current_project]] ne "xcvu9p-flga2104-2L-e" ||
    [get_property BOARD_PART [current_project]] ne "xilinx.com:vcu118:part0:2.0" ||
    [get_property NAME [current_project]] ne $project_name ||
    [get_property TOP [current_fileset]] ne [format "%s_wrapper" $bd_name]} {
    error "Wrong VCU118 format05 project identity"
}
set actual_defines [get_property verilog_define [get_filesets sources_1]]
set expected_defines [list HAP_BOARD_BUILD HAP_BOARD_V5 \
    HAP_MLP_FULL_COMMAND_V5_MODULE=hap_mlp_full_command16_s54 \
    HAP_ATTENTION_BOARD_MODULE=hap_attention_board_cohort16_core]
if {[lsort $actual_defines] ne [lsort $expected_defines]} {
    error "Wrong format05/cohort16 compile definitions: $actual_defines"
}
foreach name {
    hap_attention_board_cohort16_core.sv
    hap_projection_core16x16_w8_reuse.sv
    hap_mlp_down_group_major_accum_s54.sv
    hap_axi512_dual_engine_dedicated_read.sv
    hap_axi256_dedicated_data_router.sv
    hap_mlp_down_v5_scheduler16_s54.sv
    hap_mlp_shared_dual_slice16x12_s44_s54.sv
    hap_mlp_serial_ddr_command16_v5_s54.sv
    hap_mlp_full_command16_v5_s54.sv
    hap_mlp_gate_up_v5_scheduler16_q4.sv
    hap_mlp_projection_repack12_to16_s24_history2.sv
    hap_mlp_projection_repack12_to16_s32_history2.sv
} {require_file $name}
foreach name {
    hap_attention_board_core.sv
    hap_projection_core8x16.sv
    hap_mlp_down_group_major_accum_s45.sv
    hap_mlp_down_v5_scheduler16_s45.sv
    hap_mlp_shared_dual_slice16x12_s43_s45.sv
    hap_mlp_serial_ddr_command16_v5_s45.sv
    hap_mlp_full_command16_v5_s45.sv
    hap_mlp_down_group_major_accum_s46.sv
    hap_mlp_down_v5_scheduler16_s46.sv
    hap_mlp_shared_dual_slice16x12_s44_s46.sv
    hap_mlp_serial_ddr_command16_v5_s46.sv
    hap_mlp_full_command16_v5_s46.sv
} {reject_file $name}
set bd_files [get_files -quiet "*/$bd_name.bd"]
if {[llength $bd_files] != 1} {error "Board BD is not unique: $bd_files"}
open_bd_design [lindex $bd_files 0]
foreach cell {ddr4_0 ddr4_1} {
    require_bd_number $cell C0.DDR4_TimePeriod 1250
    require_bd_number $cell C0.DDR4_AxiDataWidth 512
    require_bd_clock [get_bd_pins $cell/c0_ddr4_ui_clk] 200000000
}
require_bd_clock [get_bd_intf_ports default_250mhz_clk1] 250000000
require_bd_clock [get_bd_intf_ports default_250mhz_clk2] 250000000
require_bd_clock [get_bd_pins core/core_clk] 100000000
require_bd_clock [get_bd_pins core/ddr0_clk] 200000000
require_bd_clock [get_bd_pins core/ddr1_clk] 200000000
require_m002_bd
validate_bd_design
if {$stage eq "synth"} {generate_target all $bd_files}
update_compile_order -fileset sources_1
if {$stage eq "synth"} {
    require_disabled_ip_cache
    create_ip_run $bd_files
}
set core_runs [get_runs -quiet -filter \
    {NAME == scalellm_vcu118_f05_bd_core_0_synth_1}]
if {[llength $core_runs] != 1} {
    error "Current production core OOC synthesis run is missing"
}
set source_pins [synth_rom_sources $root]
if {$stage eq "synth"} {
    set thread_hook [file join $script_dir m002_synth_threads.tcl]
    foreach run [synth_runs] {
        set prior [get_property STEPS.SYNTH_DESIGN.TCL.PRE $run]
        if {$prior ne "" && $prior ne $thread_hook} {error "Unexpected synthesis pre-hook: $prior"}
        set_property STEPS.SYNTH_DESIGN.TCL.PRE $thread_hook $run
    }
    reset_run impl_1
    reset_run synth_1
    foreach run [get_runs -quiet -filter {NAME =~ *_synth_1}] {
        reset_run $run
    }
    # Vivado finalizes module-reference XCI permissions while preparing runs.
    # Do this before full-byte input binding; scripts_only requires a reset.
    launch_runs synth_1 -jobs $synth_jobs -scripts_only
    require_child_ip_cache_policy 1
    reset_run impl_1
    reset_run synth_1
    foreach run [get_runs -quiet -filter {NAME =~ *_synth_1}] {
        reset_run $run
    }
    # Freeze the persisted file registry, not transient sim-netlist promises.
    unset core_runs bd_files
    close_project
    open_project $project_file
    require_disabled_ip_cache
    set core_runs [get_runs -quiet -filter \
        {NAME == scalellm_vcu118_f05_bd_core_0_synth_1}]
    if {[llength $core_runs] != 1} {
        error "Reopened production core OOC synthesis run is missing"
    }
    puts "SYNTH_INPUT_FINALIZATION scripts_only_then_reset_before_input_binding"
    set staged_paths [stage_synth_roms $root $source_pins]
} else {
    set staged_paths [synth_rom_paths]
}
set inputs [write_input_manifest [lsort -unique [concat \
    [source_files $root $project_dir] [dict keys $source_pins] $staged_paths]] \
    [file join $report_dir inputs.sha256]]
write_identity [file join $report_dir build_identity.txt]
puts "BUILD_INPUT_MANIFEST_SHA256 [hash_file [file join $report_dir inputs.sha256]]"
if {$stage eq "synth"} {
    verify_inputs $inputs
    launch_runs synth_1 -jobs $synth_jobs
    wait_on_run synth_1
} else {
    set prior_manifest [file join $synth_report_dir inputs.sha256]
    set prior_identity [file join $synth_report_dir build_identity.txt]
    if {[hash_file $prior_manifest] ne
        [hash_file [file join $report_dir inputs.sha256]] ||
        [hash_file $prior_identity] ne
        [hash_file [file join $report_dir build_identity.txt]]} {
        error "Route inputs or build flags differ from fresh synthesis; rerun synth"
    }
    set handle [open [file join $synth_report_dir fresh_synth_complete.txt] r]
    set marker [read $handle]
    close $handle
    if {[dict get $marker project] ne $project_dir ||
        [dict get $marker inputs_sha256] ne [hash_file $prior_manifest] ||
        [dict get $marker identity_sha256] ne [hash_file $prior_identity]} {
        error "Fresh synthesis marker does not match this project and inputs"
    }
}
require_complete_run synth_1
require_complete_run [get_property NAME [lindex $core_runs 0]]
foreach run [get_runs -quiet -filter {NAME =~ *_synth_1}] {
    require_complete_run [get_property NAME $run]
}
require_child_ip_cache_policy 1
verify_synth_roms $root $inputs
reject_synth_rom_warnings
open_run synth_1
require_board_clock_groups
report_utilization -file [file join $report_dir utilization_post_synth.rpt]
report_utilization -hierarchical -file [file join $report_dir utilization_hierarchical_post_synth.rpt]
report_timing_summary -delay_type min_max -report_unconstrained \
    -file [file join $report_dir timing_post_synth.rpt]
check_timing -verbose -file [file join $report_dir check_timing_post_synth.rpt]
report_clocks -file [file join $report_dir clocks_post_synth.rpt]
report_clock_interaction -delay_type min_max \
    -file [file join $report_dir clock_interaction_post_synth.rpt]
report_cdc -details -file [file join $report_dir cdc_post_synth.rpt]
report_drc -file [file join $report_dir drc_pre_impl.rpt]
require_no_drc_blockers pre_implementation
if {$stage eq "synth" && [info exists ::env(HAP_EXECUTION_PROFILE)] && $::env(HAP_EXECUTION_PROFILE) eq "m002_optimized_implementation"} {
    source [file join $script_dir m002_optimized_structure.tcl]
    m002_optimized_structure synth $report_dir
}
close_design

if {$stage eq "place"} {
    reset_run impl_1
    set physical_started [clock seconds]
    set opt_launched_at [clock seconds]
    launch_runs impl_1 -to_step opt_design -jobs 1
    wait_on_run impl_1
    set opt_checkpoint [require_completed_impl_step opt_design \
        scalellm_vcu118_f05_bd_wrapper_opt.dcp $opt_launched_at]
    open_checkpoint $opt_checkpoint
    mission0005_require_partition 0 $report_dir
    mission0005_report_capacity $report_dir
    require_board_clock_groups
    mission0004_require_metadata 1
    report_timing_summary -delay_type min_max -report_unconstrained \
        -file [file join $report_dir timing_pre_place.rpt]
    check_timing -verbose -file [file join $report_dir check_timing_pre_place.rpt]
    report_clocks -file [file join $report_dir clocks_pre_place.rpt]
    report_clock_interaction -delay_type min_max \
        -file [file join $report_dir clock_interaction_pre_place.rpt]
    report_cdc -details -file [file join $report_dir cdc_pre_place.rpt]
    report_drc -file [file join $report_dir drc_pre_place.rpt]
    require_no_drc_blockers pre_place
    close_design
    close_project
    open_project $project_file
    require_disabled_ip_cache
    set place_launched_at [clock seconds]
    launch_runs impl_1 -to_step phys_opt_design -jobs 1
    wait_on_run impl_1
    set physical_checkpoint [require_completed_impl_step phys_opt_design \
        scalellm_vcu118_f05_bd_wrapper_physopt.dcp $place_launched_at]
    open_checkpoint $physical_checkpoint
    mission0005_require_partition 1 $report_dir
    require_board_clock_groups
    mission0004_report_metadata $report_dir
    report_utilization -slr -file [file join $report_dir utilization_physopt.rpt]
    report_control_sets -verbose -file [file join $report_dir control_sets_physopt.rpt]
    report_design_analysis -congestion -min_congestion_level 3 \
        -file [file join $report_dir congestion_physopt.rpt]
    report_slr_crossing -max_nets 32 -file [file join $report_dir slr_crossing_physopt.rpt]
    report_timing_summary -delay_type min_max -report_unconstrained \
        -file [file join $report_dir timing_physopt.rpt]
    check_timing -verbose -file [file join $report_dir check_timing_physopt.rpt]
    report_cdc -details -file [file join $report_dir cdc_physopt.rpt]
    report_drc -file [file join $report_dir drc_physopt.rpt]
    require_no_drc_blockers physopt
    mission0004_report_regions $report_dir
    set marker [dict create project $project_dir \
        inputs_sha256 [hash_file [file join $report_dir inputs.sha256]] \
        identity_sha256 [hash_file [file join $report_dir build_identity.txt]] \
        checkpoint $physical_checkpoint checkpoint_sha256 [hash_file $physical_checkpoint] \
        physical_started $physical_started]
    set handle [open [file join $report_dir fresh_place_complete.txt] w]
    puts $handle $marker
    close $handle
    close_design
    close_project
    open_project $project_file
    require_disabled_ip_cache
}
if {$stage eq "route"} {
    if {![info exists ::env(HAP_PLACE_REPORT_DIR)]} { error "Route requires current S3 reports" }
    set place_report_dir [file normalize $::env(HAP_PLACE_REPORT_DIR)]
    if {![string match [file join $root vivado reports *] $place_report_dir]} {
        error "S3 reports outside Hardware root"
    }
    set handle [open [file join $place_report_dir fresh_place_complete.txt] r]
    set marker [read $handle]
    close $handle
    set handle [open [file join $place_report_dir s3_screen.txt] r]
    set screen [read $handle]
    close $handle
    if {[dict get $marker project] ne $project_dir ||
        [dict get $marker inputs_sha256] ne [hash_file [file join $report_dir inputs.sha256]] ||
        [dict get $marker identity_sha256] ne [hash_file [file join $report_dir build_identity.txt]] ||
        [dict get $marker checkpoint_sha256] ne [hash_file [dict get $marker checkpoint]] ||
        [dict get $screen decision] ne "PASS" ||
        [dict get $screen place_marker_sha256] ne [hash_file [file join $place_report_dir fresh_place_complete.txt]]} {
        error "Route requires same-input S3 PASS"
    }
    set physical_checkpoint [require_completed_impl_step phys_opt_design \
        scalellm_vcu118_f05_bd_wrapper_physopt.dcp [dict get $marker physical_started]]
    if {$physical_checkpoint ne [dict get $marker checkpoint]} { error "S3 checkpoint changed" }
    set route_launched_at [clock seconds]
    launch_runs impl_1 -to_step route_design -jobs 1
    wait_on_run impl_1
    set routed_run_checkpoint [require_completed_impl_step route_design \
        scalellm_vcu118_f05_bd_wrapper_routed.dcp $route_launched_at]
    open_checkpoint $routed_run_checkpoint
    mission0005_require_partition 1 $report_dir
    require_board_clock_groups
    report_timing_summary -delay_type min_max -report_unconstrained \
        -file [file join $report_dir timing_post_route.rpt]
    check_timing -verbose -file [file join $report_dir check_timing_post_route.rpt]
    report_clocks -file [file join $report_dir clocks_post_route.rpt]
    report_clock_interaction -delay_type min_max \
        -file [file join $report_dir clock_interaction_post_route.rpt]
    report_cdc -details -file [file join $report_dir cdc_post_route.rpt]
    report_drc -file [file join $report_dir drc_post_route.rpt]
    report_route_status -file [file join $report_dir route_status_post_route.rpt]
    report_exceptions -coverage \
        -file [file join $report_dir exceptions_post_route.rpt]
    set setup [lindex [get_timing_paths -quiet -delay_type max -max_paths 1] 0]
    set hold [lindex [get_timing_paths -quiet -delay_type min -max_paths 1] 0]
    if {$setup eq "" || $hold eq "" ||
        [get_property SLACK $setup] < 0 || [get_property SLACK $hold] < 0} {
        error "Routed setup/hold gate failed"
    }
    require_no_drc_blockers post_route
    set checkpoint [file join $report_dir routed.dcp]
    write_checkpoint $checkpoint
    set handle [open [file join $report_dir routed_checkpoint.sha256] w]
    puts $handle "[hash_file $checkpoint]  $checkpoint"
    close $handle
    close_design
    close_project
    open_project $project_file
    require_disabled_ip_cache
}
verify_inputs $inputs
if {$stage eq "synth"} {
    set marker [dict create project $project_dir \
        inputs_sha256 [hash_file [file join $report_dir inputs.sha256]] \
        identity_sha256 [hash_file [file join $report_dir build_identity.txt]]]
    set handle [open [file join $report_dir fresh_synth_complete.txt] w]
    puts $handle $marker
    close $handle
}
close_project
puts "COMPLETED: $stage reports at $report_dir; no bitstream generated"
