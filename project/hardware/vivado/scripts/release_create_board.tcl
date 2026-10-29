# SPDX-License-Identifier: Apache-2.0
# Portable constructor derived from the frozen reader011 board constructor.
# RTL/IP settings and all six constraints retain the original production values.
set script_dir [file dirname [file normalize [info script]]]
source [file join $script_dir m006_system_python.tcl]
set root [file normalize [file join $script_dir ../..]]
set project_name scalellm_final_decode16
set bd_name scalellm_final_decode16_bd
set manifest [file join $root vivado manifests final/board.list]
set board_xdc [file join $root vivado constraints attention_mlp_vcu118_board_v5.xdc]
set ddr_pin_xdc [file join $root vivado constraints vcu118_ddr4_explicit_pins.xdc]
set clock_xdc [file join $root vivado constraints final_clock_domains.xdc]
set status_cdc_xdc [file join $root vivado constraints final_attention_status_cdc.xdc]
set m002_xdc [file join $root vivado constraints final_ddr_timing.xdc]
set m006_xdc [file join $root vivado constraints final_physical.xdc]
set m006_inputs [split [m006_python [file join $script_dir final_entry.py] list-sources] "\n"]
set validate_only 0
if {[info exists ::env(HAP_BD_VALIDATE_ONLY)]} {set validate_only $::env(HAP_BD_VALIDATE_ONLY)}
if {$validate_only ni {0 1}} {error "HAP_BD_VALIDATE_ONLY must be 0 or 1"}
# Validation intentionally stops before IP output generation; create is separate.
set module_reference_sources [list \
    [file join $root rtl integration hap_scalellm_final_board_core.sv] \
    [file join $root rtl board hap_scalellm_final_reset_gate_xpm.sv] \
    [file join $root rtl board hap_scalellm_final_dual_async_ready_gate_xpm.sv]]
set defines [list HAP_BOARD_BUILD HAP_BOARD_V5]
set xdma_aperture_profile {
    pf0_bar0_enabled true pf0_bar0_64bit true
    pf0_bar0_scale Megabytes pf0_bar0_size 1
    pf0_bar2_enabled true pf0_bar2_64bit true
    pf0_bar2_scale Gigabytes pf0_bar2_size 4
}

foreach name {HAP_JOBS HAP_PROJECT_DIR HAP_REPORT_DIR HAP_BOARD_CORE_CLK_MHZ HAP_BOARD_DDR_UI_CLK_HZ} {
    if {![info exists ::env($name)] || $::env($name) eq ""} {
        error "Missing required input $name"
    }
}
set jobs $::env(HAP_JOBS)
set project_dir [file normalize $::env(HAP_PROJECT_DIR)]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set project_base [file dirname $project_dir]
set report_base [file dirname $report_dir]
if {![string is integer -strict $jobs] || $jobs < 1 || $jobs > 4} {
    error "HAP_JOBS (Vivado per-process threads) must be in 1..4"
}
if {$::env(HAP_BOARD_CORE_CLK_MHZ) ne "80.0" ||
    $::env(HAP_BOARD_DDR_UI_CLK_HZ) ne "200000000"} {
    error "Required clocks are core 80.0 MHz and dual DDR UI 200000000 Hz"
}
if {![string match "2025.2*" [version -short]]} {
    error "Expected Vivado 2025.2, got [version -short]"
}
if {![string match [file join $project_base *] $project_dir] ||
    [file exists $project_dir]} {
    error "Project must be a new directory below $project_base: $project_dir"
}
if {![string match [file join $report_base *] $report_dir] ||
    ![file isdirectory $report_dir] ||
    [file exists [file join $report_dir constructor_inputs.sha256]]} {
    error "Report directory is missing or already used: $report_dir"
}
foreach path [list $manifest $board_xdc $ddr_pin_xdc $clock_xdc $m002_xdc $m006_xdc {*}$m006_inputs] {
    if {![file isfile $path] || [file size $path] == 0} {
        error "Missing board input $path"
    }
}
set_param general.maxThreads $jobs

proc collect_manifest {root path state} {
    set path [file normalize $path]
    if {![string match [file join $root *] $path] ||
        ![file isfile $path] || [file size $path] == 0} {
        error "Manifest is missing or outside the new root: $path"
    }
    if {[dict exists $state manifests $path]} {return $state}
    dict set state manifests $path 1
    set handle [open $path r]
    set lines [split [read $handle] "\n"]
    close $handle
    foreach raw $lines {
        set entry [string trim [lindex [split $raw #] 0]]
        if {$entry eq ""} {continue}
        set resolved [file normalize [file join $root $entry]]
        if {![string match [file join $root *] $resolved] ||
            ![file isfile $resolved] || [file size $resolved] == 0} {
            error "Source is missing or outside the new root: $entry"
        }
        if {[file extension $resolved] eq ".list"} {
            set state [collect_manifest $root $resolved $state]
        } else {
            dict set state sources $resolved 1
        }
    }
    return $state
}
proc latest_ip {name} {
    set defs [get_ipdefs -quiet -all "xilinx.com:ip:$name:*"]
    if {![llength $defs]} {error "Missing Vivado IP: $name"}
    return [lindex $defs end]
}
proc setcfg {cell key value} {
    set_property CONFIG.$key $value [get_bd_cells $cell]
}
proc require_cfg {cell key expected} {
    set actual [get_property CONFIG.$key [get_bd_cells $cell]]
    if {$actual ne $expected} {
        error "$cell CONFIG.$key expected=$expected actual=$actual"
    }
}
proc require_number {cell key expected} {
    set actual [get_property CONFIG.$key [get_bd_cells $cell]]
    if {![string is double -strict $actual] ||
        double($actual) != double($expected)} {
        error "$cell CONFIG.$key expected=$expected actual=$actual"
    }
}
proc config_snapshot {cell keys} {
    set snapshot [dict create]
    foreach key $keys {
        set value [get_property CONFIG.$key [get_bd_cells $cell]]
        if {$value eq ""} {error "$cell CONFIG.$key is absent"}
        dict set snapshot $key $value
    }
    return $snapshot
}
proc require_snapshot {cell snapshot} {
    dict for {key expected} $snapshot {
        require_cfg $cell $key $expected
    }
}
proc board_port_snapshot {cell pin_name port_name} {
    set pin [get_bd_intf_pins -quiet $cell/$pin_name]
    set port [get_bd_intf_ports -quiet $port_name]
    if {[llength $pin] != 1 || [llength $port] != 1} {
        error "$cell/$pin_name lost board port $port_name"
    }
    set pin_nets [get_bd_intf_nets -quiet -of_objects $pin]
    set port_nets [get_bd_intf_nets -quiet -of_objects $port]
    if {[llength $pin_nets] != 1 || $pin_nets ne $port_nets} {
        error "$cell/$pin_name is not connected to $port_name"
    }
    set available [list_property $port]
    set metadata [dict create]
    foreach property {
        BOARD_INTERFACE CONFIG.BOARD_INTERFACE
        FREQ_HZ CONFIG.FREQ_HZ CLK_DOMAIN CONFIG.CLK_DOMAIN
    } {
        if {[lsearch -exact $available $property] >= 0} {
            dict set metadata $property [get_property $property $port]
        }
    }
    return [dict create pin $pin port $port net $pin_nets metadata $metadata]
}
proc first_pin {cell choices} {
    foreach name $choices {
        set pin [get_bd_pins -quiet $cell/$name]
        if {[llength $pin] == 1} {return $pin}
    }
    error "Missing pin $cell/$choices"
}
proc first_intf {cell choices} {
    foreach name $choices {
        set pin [get_bd_intf_pins -quiet $cell/$name]
        if {[llength $pin] == 1} {return $pin}
    }
    error "Missing interface $cell/$choices"
}
proc externalize_named_pin {cell pin_name} {
    set before [get_bd_ports -quiet]
    make_bd_pins_external [get_bd_pins $cell/$pin_name]
    foreach candidate [get_bd_ports -quiet] {
        if {[lsearch -exact $before $candidate] < 0} {
            set_property name $pin_name $candidate
            return
        }
    }
    error "Could not externalize $cell/$pin_name"
}
proc make_ready {name calib ui_reset} {
    set inv [format "%s_not" $name]
    set gate [format "%s_and" $name]
    create_bd_cell -type ip -vlnv [latest_ip util_vector_logic] $inv
    set_property -dict [list CONFIG.C_SIZE 1 CONFIG.C_OPERATION not] \
        [get_bd_cells $inv]
    create_bd_cell -type ip -vlnv [latest_ip util_vector_logic] $gate
    set_property -dict [list CONFIG.C_SIZE 1 CONFIG.C_OPERATION and] \
        [get_bd_cells $gate]
    connect_bd_net $ui_reset [get_bd_pins $inv/Op1]
    connect_bd_net $calib [get_bd_pins $gate/Op1]
    connect_bd_net [get_bd_pins $inv/Res] [get_bd_pins $gate/Op2]
    return [get_bd_pins $gate/Res]
}
proc one_space {pin} {
    set spaces [get_bd_addr_spaces -quiet -of_objects $pin]
    if {[llength $spaces] != 1} {error "Expected one AXI space at $pin"}
    return [lindex $spaces 0]
}
proc one_segment {pin} {
    set segments [get_bd_addr_segs -quiet -of_objects $pin]
    if {[llength $segments] != 1} {error "Expected one AXI segment at $pin"}
    return [lindex $segments 0]
}
proc require_map {space token offset range count} {
    set segments [get_bd_addr_segs -quiet -of_objects $space]
    if {[llength $segments] != $count} {
        error "Address-map count at $space: expected=$count actual=[llength $segments]"
    }
    set matches {}
    foreach segment $segments {
        if {[string match "*$token*" $segment]} {lappend matches $segment}
    }
    if {[llength $matches] != 1} {error "Address-map target $token is not unique"}
    set segment [lindex $matches 0]
    if {[expr {wide([get_property OFFSET $segment])}] !=
            [expr {wide($offset)}] ||
        [expr {wide([get_property RANGE $segment])}] !=
            [expr {wide($range)}]} {
        error "Address-map mismatch at $segment"
    }
}
proc require_clock_metadata {label pin expected} {
    set value [get_property -quiet CONFIG.FREQ_HZ $pin]
    if {$value eq ""} {set value [get_property -quiet FREQ_HZ $pin]}
    if {![string is double -strict $value] ||
        double($value) != double($expected)} {
        error "$label clock metadata expected=$expected actual=$value"
    }
    puts "BD_CLOCK_METADATA $label $value"
    return $value
}
proc configure_active_low_reset {cell} {
    setcfg $cell RESET_BOARD_INTERFACE Custom
    # The connected ACTIVE_LOW port propagates the read-only pin/cell values.
}
proc interface_link_snapshot {left right} {
    set left_net [get_bd_intf_nets -quiet -of_objects $left]
    set right_net [get_bd_intf_nets -quiet -of_objects $right]
    if {[llength $left_net] != 1 || $left_net ne $right_net} {
        error "Interface link is missing: $left -> $right"
    }
    return [dict create left $left right $right net $left_net]
}
proc generated_file_identity {handle label path} {
    if {![file isfile $path] || [file size $path] == 0} {
        error "Missing generated $label: $path"
    }
    puts $handle "$label.path=$path"
    puts $handle "$label.sha256=[lindex [exec sha256sum -- $path] 0]"
}
proc unique_generated_file {pattern} {
    set files [glob -nocomplain -types f $pattern]
    if {[llength $files] != 1} {
        error "Expected one generated file matching $pattern; found [llength $files]"
    }
    return [lindex $files 0]
}
proc xci_component_value {path key} {
    return [string trim [exec jq -er --arg key $key \
        {.ip_inst.parameters.component_parameters[$key][0].value} $path]]
}
proc xci_model_value {path key} {
    return [string trim [exec jq -er --arg key $key \
        {.ip_inst.parameters.model_parameters[$key][0].value} $path]]
}
proc xci_interface_value {path interface key} {
    return [string trim [exec jq -er --arg interface $interface --arg key $key \
        {.ip_inst.boundary.interfaces[$interface].parameters[$key][0].value} $path]]
}

proc m006_visible_identity {path scope} {
    set out [open $path w]
    puts $out "scope=$scope"
    puts $out "parameter_values_source=static_bound_source"
    puts $out "actual_elaboration_parameters=unavailable"
    puts $out "hierarchy_scope=validated_block_design_module_reference; synthesized hierarchy is recorded by build"
    set fs [get_filesets sources_1]
    foreach property {TOP VERILOG_DEFINE GENERIC} {
        if {[lsearch -exact [list_property $fs] $property] >= 0} {
            puts $out "fileset.$property=[get_property $property $fs]"
        } else {puts $out "fileset.$property=unavailable"}
    }
    foreach cell [lsort [get_bd_cells -quiet -hierarchical]] {
        puts $out "bd_cell=$cell"
        foreach property [lsort [list_property $cell]] {
            if {[regexp {^(TYPE|VLNV|REF_NAME|CONFIG\.)} $property]} {
                if {![catch {get_property $property $cell} value]} {
                    puts $out "bd_cell.$cell.$property=$value"
                }
            }
        }
    }
    # Enumerate published properties rather than inventing parameter properties.
    # LEFT/RIGHT/vector widths, clocks and AXI widths are retained when visible.
    foreach object [concat [get_bd_pins -quiet core/*] [get_bd_intf_pins -quiet core/*]] {
        puts $out "visible_core_object=$object"
        foreach property [lsort [list_property $object]] {
            if {![catch {get_property $property $object} value]} {
                puts $out "visible_core_object.$object.$property=$value"
            }
        }
    }
    close $out
}

set closure [collect_manifest $root $manifest [dict create]]
if {![info exists ::env(HAP_BOARD_FILES)]} {error "HAP_BOARD_FILES must name the official VCU118 2.0 board directory"}
set board_files [list]
foreach name {board.xml part0_pins.xml preset.xml} {
    lappend board_files [file normalize [file join $::env(HAP_BOARD_FILES) $name]]
}
set inputs [concat [dict keys [dict get $closure manifests]] \
    [dict keys [dict get $closure sources]] $board_files \
    [list [info script] [file join $script_dir final_entry.py] \
        [file join $script_dir final_entry.py] \
        $board_xdc $ddr_pin_xdc $clock_xdc $status_cdc_xdc $m002_xdc $m006_xdc {*}$m006_inputs]]
set input_handle [open [file join $report_dir constructor_inputs.sha256] w]
foreach path [lsort -unique $inputs] {
    if {![file isfile $path] || [file size $path] == 0} {
        error "Missing constructor input $path"
    }
    puts $input_handle "[lindex [exec sha256sum -- $path] 0]  $path"
}
close $input_handle
set production_shape [open [file join $report_dir production_shape.json] w]
puts $production_shape [m006_python [file join $script_dir final_entry.py] shape]
close $production_shape
puts "CONSTRUCTOR_INPUT_MANIFEST_SHA256 [lindex \
    [exec sha256sum -- [file join $report_dir constructor_inputs.sha256]] 0]"
file mkdir $project_base
# Resolve the exact installed repository in this isolated Vivado process;
# availability must not depend on a user's prior interactive board settings.
set final_board_repo [file dirname [file dirname [file dirname [lindex $board_files 0]]]]
set final_board_repos [get_param board.repoPaths]
if {[lsearch -exact $final_board_repos $final_board_repo] < 0} {
    lappend final_board_repos $final_board_repo
    set_param board.repoPaths $final_board_repos
}
create_project $project_name $project_dir -part xcvu9p-flga2104-2L-e
config_ip_cache -disable_cache
set board [get_board_parts -quiet xilinx.com:vcu118:part0:2.0]
if {[llength $board] != 1} {error "VCU118 board part 2.0 is unavailable"}
set_property board_part [lindex $board 0] [current_project]
set_property target_language Verilog [current_project]
set_property verilog_define $defines [get_filesets sources_1]
set final_header_sources [list]
foreach path $m006_inputs {
    if {[file extension $path] in {.svh .vh}} {lappend final_header_sources $path}
}
if {![llength $final_header_sources]} {error "Final HDL include-header closure is empty"}
set final_project_sources [lsort -unique [concat [dict keys [dict get $closure sources]] $final_header_sources]]
add_files -norecurse -fileset sources_1 $final_project_sources
foreach path $final_project_sources {
    if {[lsearch -exact $module_reference_sources $path] >= 0} {
        set_property file_type Verilog [get_files $path]
    } elseif {[file extension $path] eq ".sv"} {
        set_property file_type SystemVerilog [get_files $path]
    } elseif {[file extension $path] in {.svh .vh}} {
        set_property file_type {Verilog Header} [get_files $path]
    } elseif {[file extension $path] eq ".mem"} {
        set_property file_type {Memory Initialization Files} [get_files $path]
    }
}
foreach path $final_header_sources {
    set file [get_files -quiet $path]
    if {[llength $file]!=1 || [get_property FILE_TYPE $file] ne "Verilog Header"} {
        error "Final include header is not registered before module resolution: $path"
    }
    puts "FINAL_EXPLICIT_INCLUDE_HEADER $path FILE_TYPE=[get_property FILE_TYPE $file]"
}
foreach path $module_reference_sources {
    if {![dict exists $closure sources $path] ||
        [get_property FILE_TYPE [get_files $path]] ne "Verilog"} {
        error "BD module-reference boundary is not selected as Verilog: $path"
    }
}
set_property include_dirs [list [file join $root rtl integration]] [get_filesets sources_1]
add_files -norecurse -fileset constrs_1 $board_xdc
add_files -norecurse -fileset constrs_1 $ddr_pin_xdc
add_files -norecurse -fileset constrs_1 $m002_xdc
add_files -norecurse -fileset constrs_1 $clock_xdc
add_files -norecurse -fileset constrs_1 $status_cdc_xdc
set_property USED_IN_SYNTHESIS false [get_files $status_cdc_xdc]
set_property USED_IN_IMPLEMENTATION true [get_files $status_cdc_xdc]
set_property PROCESSING_ORDER LATE [get_files $status_cdc_xdc]
set_property PROCESSING_ORDER LATE [get_files $clock_xdc]
add_files -norecurse -fileset constrs_1 $m006_xdc
set_property FILE_TYPE TCL [get_files $m006_xdc]
set_property USED_IN_SYNTHESIS false [get_files $m006_xdc]
set_property USED_IN_IMPLEMENTATION true [get_files $m006_xdc]
set_property PROCESSING_ORDER LATE [get_files $m006_xdc]
# Legacy native025 physical XDCs remain preserved, outside the M002 input set.
update_compile_order -fileset sources_1

create_bd_design $bd_name
create_bd_port -dir I -type rst pcie_perstn
set_property CONFIG.POLARITY ACTIVE_LOW [get_bd_ports pcie_perstn]
create_bd_cell -type ip -vlnv [latest_ip xdma] xdma_0
# The XDMA GUI enables BAR2 only after BAR0 consumes BAR1 as a 64-bit BAR.
foreach {key value} {
    mode_selection Advanced axilite_master_en true
    axisten_if_enable_msg_route true PCIE_BOARD_INTERFACE pci_express_x8
    pl_link_cap_max_link_speed 8.0_GT/s axi_data_width 256_bit
    SYS_RST_N_BOARD_INTERFACE pcie_perstn pf0_device_id 9018
    pciebar2axibar_0 0x00000000 pf0_bar0_enabled true
    pf0_bar0_64bit true pf0_bar0_scale Megabytes pf0_bar0_size 1
    pf0_bar2_enabled true pf0_bar2_64bit true
    pf0_bar2_scale Gigabytes pf0_bar2_size 4 pf0_msix_enabled false
    pf0_msi_enabled true xdma_rnum_chnl 1 xdma_wnum_chnl 1
} {
    setcfg xdma_0 $key $value
    require_cfg xdma_0 $key $value
}
create_bd_cell -type module -reference vcu118_pcie_refclk_ibuf pcie_refclk_buf
connect_bd_net [get_bd_pins pcie_refclk_buf/sys_clk_gt] \
    [get_bd_pins xdma_0/sys_clk_gt]
connect_bd_net [get_bd_pins pcie_refclk_buf/sys_clk] \
    [get_bd_pins xdma_0/sys_clk]
externalize_named_pin pcie_refclk_buf pcie_refclk_p
externalize_named_pin pcie_refclk_buf pcie_refclk_n
connect_bd_net [get_bd_ports pcie_perstn] [get_bd_pins xdma_0/sys_rst_n]
set xclk [first_pin xdma_0 {axi_aclk axi_aclk_out}]
set xrstn [first_pin xdma_0 {axi_aresetn axi_aresetn_out}]

create_bd_cell -type ip -vlnv [latest_ip clk_wiz] clk_core
foreach {key value} {
    PRIMITIVE MMCM PRIM_SOURCE No_buffer CLKIN1_JITTER_PS 100.0
    CLKOUT1_REQUESTED_OUT_FREQ 80.0 USE_LOCKED true USE_RESET false
} {setcfg clk_core $key $value}
require_number clk_core CLKOUT1_REQUESTED_OUT_FREQ 80.0
connect_bd_net $xclk [get_bd_pins clk_core/clk_in1]
set cclk [get_bd_pins clk_core/clk_out1]
create_bd_cell -type ip -vlnv [latest_ip proc_sys_reset] rst_core
configure_active_low_reset rst_core
connect_bd_net $cclk [get_bd_pins rst_core/slowest_sync_clk]
connect_bd_net [get_bd_ports pcie_perstn] [get_bd_pins rst_core/ext_reset_in]
connect_bd_net [get_bd_pins clk_core/locked] [get_bd_pins rst_core/dcm_locked]
set crstn [get_bd_pins rst_core/peripheral_aresetn]

set mig_structural_keys {
    C0.DDR4_MemoryType C0.DDR4_MemoryPart C0.DDR4_MemoryVoltage
    C0.DDR4_Slot C0.DDR4_Capacity C0.DDR4_DataWidth
    C0.DDR4_DataMask C0.DDR4_Ecc C0.DDR4_MCS_ECC
    C0.DDR4_PhyClockRatio C0.DDR4_ChipSelect C0.DDR4_Clamshell
    C0.DDR4_Mem_Add_Map C0.DDR4_AxiSelection
    C0.DDR4_AxiDataWidth C0.DDR4_AxiAddressWidth C0.DDR4_AxiIDWidth
    System_Clock
}
foreach {cell memory_interface reference_interface} {
    ddr4_0 ddr4_sdram_c1 default_250mhz_clk1
    ddr4_1 ddr4_sdram_c2 default_250mhz_clk2
} {
    create_bd_cell -type ip -vlnv [latest_ip ddr4] $cell
    setcfg $cell C0_CLOCK_BOARD_INTERFACE $reference_interface
    setcfg $cell C0_DDR4_BOARD_INTERFACE $memory_interface
    apply_board_connection -board_interface $memory_interface \
        -ip_intf [get_bd_intf_pins $cell/C0_DDR4] \
        -diagram [current_bd_design]
    apply_board_connection -board_interface $reference_interface \
        -ip_intf [get_bd_intf_pins $cell/C0_SYS_CLK] \
        -diagram [current_bd_design]
    set memory_port_before [board_port_snapshot $cell C0_DDR4 $memory_interface]
    set clock_port_before [board_port_snapshot $cell C0_SYS_CLK $reference_interface]
    dict set mig_board_ports $cell memory $memory_port_before
    dict set mig_board_ports $cell reference $clock_port_before
    set structure [config_snapshot $cell $mig_structural_keys]
    require_cfg $cell C0.DDR4_MemoryPart MT40A256M16GE-083E
    require_cfg $cell C0.DDR4_MemoryType Components
    require_cfg $cell C0.DDR4_Slot Single
    require_cfg $cell C0.DDR4_PhyClockRatio 4:1
    require_cfg $cell C0.DDR4_Ecc false
    require_cfg $cell C0.DDR4_MCS_ECC false
    require_cfg $cell System_Clock Differential
    foreach {key value} {
        C0.DDR4_DataWidth 64 C0.DDR4_AxiAddressWidth 31
        C0.DDR4_AxiDataWidth 512
    } {require_number $cell $key $value}
    set_property -dict [list \
        CONFIG.C0_DDR4_BOARD_INTERFACE Custom \
        CONFIG.C0_CLOCK_BOARD_INTERFACE Custom] [get_bd_cells $cell]
    set restore [list]
    dict for {key value} $structure {lappend restore CONFIG.$key $value}
    set_property -dict $restore [get_bd_cells $cell]
    set_property -dict [list \
        CONFIG.C0.DDR4_InputClockPeriod 4000 \
        CONFIG.C0.DDR4_TimePeriod 1250] [get_bd_cells $cell]
    require_cfg $cell C0_DDR4_BOARD_INTERFACE Custom
    require_cfg $cell C0_CLOCK_BOARD_INTERFACE Custom
    require_snapshot $cell $structure
    require_number $cell C0.DDR4_InputClockPeriod 4000
    require_number $cell C0.DDR4_TimePeriod 1250
    if {[board_port_snapshot $cell C0_DDR4 $memory_interface] ne
        $memory_port_before ||
        [board_port_snapshot $cell C0_SYS_CLK $reference_interface] ne
        $clock_port_before} {
        error "$cell board connection changed while unlocking MIG periods"
    }
    require_clock_metadata $reference_interface \
        [get_bd_intf_ports $reference_interface] 250000000
    require_clock_metadata $cell [get_bd_pins $cell/c0_ddr4_ui_clk] 200000000
}
set d0clk [first_pin ddr4_0 {c0_ddr4_ui_clk}]
set d1clk [first_pin ddr4_1 {c0_ddr4_ui_clk}]
set d0ready [make_ready ddr0 \
    [first_pin ddr4_0 {c0_init_calib_complete init_calib_complete}] \
    [first_pin ddr4_0 {c0_ddr4_ui_clk_sync_rst ui_clk_sync_rst}]]
set d1ready [make_ready ddr1 \
    [first_pin ddr4_1 {c0_init_calib_complete init_calib_complete}] \
    [first_pin ddr4_1 {c0_ddr4_ui_clk_sync_rst ui_clk_sync_rst}]]

create_bd_cell -type module -reference hap_scalellm_final_board_core core
connect_bd_net $cclk [get_bd_pins core/core_clk]
connect_bd_net $d0clk [get_bd_pins core/ddr0_clk]
connect_bd_net $d1clk [get_bd_pins core/ddr1_clk]
create_bd_cell -type module -reference hap_scalellm_final_dual_async_ready_gate_xpm core_gate
connect_bd_net $cclk [get_bd_pins core_gate/clk]
connect_bd_net $crstn [get_bd_pins core_gate/base_aresetn]
connect_bd_net $d0ready [get_bd_pins core_gate/async_ready0]
connect_bd_net $d1ready [get_bd_pins core_gate/async_ready1]
connect_bd_net [get_bd_pins core_gate/aresetn] [get_bd_pins core/core_rst_n]

foreach {tag clk ready reset_pin} [list \
    d0 $d0clk $d0ready ddr0_rst_n \
    d1 $d1clk $d1ready ddr1_rst_n] {
    set gate [format "%s_gate" $tag]
    set rst_cell [format "rst_ddr%s" [string index $tag 1]]
    create_bd_cell -type module -reference hap_scalellm_final_reset_gate_xpm $gate
    connect_bd_net $clk [get_bd_pins $gate/clk]
    connect_bd_net $xrstn [get_bd_pins $gate/base_aresetn]
    connect_bd_net $ready [get_bd_pins $gate/async_ready]
    connect_bd_net [get_bd_pins $gate/aresetn] [get_bd_pins core/$reset_pin]
    create_bd_cell -type ip -vlnv [latest_ip proc_sys_reset] $rst_cell
    configure_active_low_reset $rst_cell
    connect_bd_net $clk [get_bd_pins $rst_cell/slowest_sync_clk]
    connect_bd_net [get_bd_ports pcie_perstn] [get_bd_pins $rst_cell/ext_reset_in]
    connect_bd_net [get_bd_pins clk_core/locked] [get_bd_pins $rst_cell/dcm_locked]
}
connect_bd_net [get_bd_pins rst_ddr0/peripheral_aresetn] \
    [get_bd_pins ddr4_0/c0_ddr4_aresetn]
connect_bd_net [get_bd_pins rst_ddr1/peripheral_aresetn] \
    [get_bd_pins ddr4_1/c0_ddr4_aresetn]
foreach cell {ddr4_0 ddr4_1} {
    if {[llength [get_bd_pins -quiet $cell/sys_rst]] == 1} {
        connect_bd_net [get_bd_pins rst_core/peripheral_reset] \
            [get_bd_pins $cell/sys_rst]
    }
}

create_bd_cell -type ip -vlnv [latest_ip smartconnect] ctrl_smc
set_property -dict [list CONFIG.NUM_SI 1 CONFIG.NUM_MI 1 CONFIG.NUM_CLKS 2] \
    [get_bd_cells ctrl_smc]
connect_bd_intf_net [first_intf xdma_0 {M_AXI_LITE M_AXI_LITE_MASTER}] \
    [get_bd_intf_pins ctrl_smc/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins ctrl_smc/M00_AXI] \
    [get_bd_intf_pins core/S_AXIL]
connect_bd_net $cclk [get_bd_pins ctrl_smc/aclk]
connect_bd_net $xclk [get_bd_pins ctrl_smc/aclk1]
connect_bd_net $crstn [get_bd_pins ctrl_smc/aresetn]

foreach {cell si mi clocks} {
    host_split 1 2 3 d0_smc 3 1 2 d1_smc 3 1 2
} {
    create_bd_cell -type ip -vlnv [latest_ip smartconnect] $cell
    set_property -dict [list CONFIG.NUM_SI $si CONFIG.NUM_MI $mi \
        CONFIG.NUM_CLKS $clocks] [get_bd_cells $cell]
}
set slice_component_profile {
    REG_AW 15 REG_AR 15 REG_W 15 REG_R 15 REG_B 15
    USE_AUTOPIPELINING 0 NUM_SLR_CROSSINGS 2
    PIPELINES_MASTER_AW 1 PIPELINES_MASTER_AR 1 PIPELINES_MASTER_W 1
    PIPELINES_MASTER_R 1 PIPELINES_MASTER_B 1
    PIPELINES_SLAVE_AW 1 PIPELINES_SLAVE_AR 1 PIPELINES_SLAVE_W 1
    PIPELINES_SLAVE_R 1 PIPELINES_SLAVE_B 1
    PIPELINES_MIDDLE_AW 1 PIPELINES_MIDDLE_AR 1 PIPELINES_MIDDLE_W 1
    PIPELINES_MIDDLE_R 1 PIPELINES_MIDDLE_B 1
}
set slice_model_profile {
    C_REG_CONFIG_AW 15 C_REG_CONFIG_AR 15 C_REG_CONFIG_W 15
    C_REG_CONFIG_R 15 C_REG_CONFIG_B 15 C_NUM_SLR_CROSSINGS 2
    C_PIPELINES_MASTER_AW 1 C_PIPELINES_MASTER_AR 1 C_PIPELINES_MASTER_W 1
    C_PIPELINES_MASTER_R 1 C_PIPELINES_MASTER_B 1
    C_PIPELINES_SLAVE_AW 1 C_PIPELINES_SLAVE_AR 1 C_PIPELINES_SLAVE_W 1
    C_PIPELINES_SLAVE_R 1 C_PIPELINES_SLAVE_B 1
    C_PIPELINES_MIDDLE_AW 1 C_PIPELINES_MIDDLE_AR 1 C_PIPELINES_MIDDLE_W 1
    C_PIPELINES_MIDDLE_R 1 C_PIPELINES_MIDDLE_B 1
}
foreach slice {d0_mig_slice d1_mig_slice} {
    create_bd_cell -type ip -vlnv [latest_ip axi_register_slice] $slice
    # Vendor callbacks unlock crossings/pipelines only after REG15 and AUTO0.
    foreach channel {AW AR W R B} {
        setcfg $slice REG_$channel 15
        require_number $slice REG_$channel 15
    }
    setcfg $slice USE_AUTOPIPELINING 0
    require_number $slice USE_AUTOPIPELINING 0
    setcfg $slice NUM_SLR_CROSSINGS 2
    require_number $slice NUM_SLR_CROSSINGS 2
    foreach channel {AW AR W R B} {
        foreach side {MASTER SLAVE MIDDLE} {
            set key [format "PIPELINES_%s_%s" $side $channel]
            setcfg $slice $key 1
            require_number $slice $key 1
        }
    }
}
connect_bd_intf_net [first_intf xdma_0 {M_AXI M_AXI_MM}] \
    [get_bd_intf_pins host_split/S00_AXI]
foreach {source target} {
    core/M_AXI_DATA d0_smc/S00_AXI
    core/M_AXI_WEIGHT_C0 d0_smc/S01_AXI
    host_split/M00_AXI d0_smc/S02_AXI
    core/M_AXI_MLP_DATA d1_smc/S00_AXI
    core/M_AXI_WEIGHT_C1 d1_smc/S02_AXI
    host_split/M01_AXI d1_smc/S01_AXI
    d0_smc/M00_AXI d0_mig_slice/S_AXI
    d1_smc/M00_AXI d1_mig_slice/S_AXI
} {
    connect_bd_intf_net [get_bd_intf_pins $source] [get_bd_intf_pins $target]
}
connect_bd_intf_net [get_bd_intf_pins d0_mig_slice/M_AXI] \
    [first_intf ddr4_0 {C0_DDR4_S_AXI S_AXI c0_ddr4_s_axi}]
connect_bd_intf_net [get_bd_intf_pins d1_mig_slice/M_AXI] \
    [first_intf ddr4_1 {C0_DDR4_S_AXI S_AXI c0_ddr4_s_axi}]
foreach {pin clock} [list \
    host_split/aclk $xclk host_split/aclk1 $d0clk \
    host_split/aclk2 $d1clk d0_smc/aclk $d0clk \
    d0_smc/aclk1 $cclk d1_smc/aclk $d1clk d1_smc/aclk1 $cclk \
    d0_mig_slice/aclk $d0clk d1_mig_slice/aclk $d1clk] {
    connect_bd_net $clock [get_bd_pins $pin]
}
connect_bd_net $xrstn [get_bd_pins host_split/aresetn]
foreach {pin source} {
    d0_smc/aresetn d0_gate/aresetn
    d0_mig_slice/aresetn d0_gate/aresetn
    d1_smc/aresetn d1_gate/aresetn
    d1_mig_slice/aresetn d1_gate/aresetn
} {
    connect_bd_net [get_bd_pins $source] [get_bd_pins $pin]
}
apply_board_connection -board_interface pci_express_x8 \
    -ip_intf [first_intf xdma_0 {pcie_mgt PCI_EXP}] \
    -diagram [current_bd_design]
if {[llength [get_bd_pins -quiet xdma_0/usr_irq_req]] == 1} {
    set irq_width [expr {abs(
        [get_property LEFT [get_bd_pins xdma_0/usr_irq_req]] -
        [get_property RIGHT [get_bd_pins xdma_0/usr_irq_req]]) + 1}]
    # Host completion uses CSR polling. Do not drive a user IRQ without the
    # request/acknowledge lifecycle required by the XDMA user interface.
    create_bd_cell -type ip -vlnv [latest_ip xlconstant] irq0
    setcfg irq0 CONST_WIDTH $irq_width
    setcfg irq0 CONST_VAL 0
    connect_bd_net [get_bd_pins irq0/dout] [get_bd_pins xdma_0/usr_irq_req]
}

# These are module-interface checks. Never expand the complete leaf reset
# fanout of the arithmetic core to establish this BD connectivity contract.
set reset_irq_binding [open [file join $report_dir reset_irq_bd_bindings.txt] w]
foreach {gate consumers} {
    core_gate {core/core_rst_n}
    d0_gate {core/ddr0_rst_n d0_smc/aresetn d0_mig_slice/aresetn}
    d1_gate {core/ddr1_rst_n d1_smc/aresetn d1_mig_slice/aresetn}
} {
    set output [get_bd_pins $gate/aresetn]
    set net [get_bd_nets -of_objects $output]
    set actual {}
    foreach pin [get_bd_pins -of_objects $net -filter {DIR == I}] {lappend actual [string trimleft $pin /]}
    set actual [lsort $actual]
    puts $reset_irq_binding "gate=$gate vlnv=[get_property VLNV [get_bd_cells $gate]] output=$output net=$net expected_consumers=[lsort $consumers] actual_consumers=$actual"
    if {$actual ne [lsort $consumers]} {error "Final reset BD consumers differ for $gate"}
}
set irq_pin [get_bd_pins -quiet xdma_0/usr_irq_req]
if {[llength $irq_pin]!=1} {error "Final XDMA user-IRQ input is missing"}
set irq_net [get_bd_nets -of_objects $irq_pin]
set irq_sources [get_bd_pins -of_objects $irq_net -filter {DIR == O}]
set irq_source_names {}
foreach pin $irq_sources {lappend irq_source_names [string trimleft $pin /]}
puts $reset_irq_binding "usr_irq_req=$irq_pin left=[get_property LEFT $irq_pin] right=[get_property RIGHT $irq_pin] width=$irq_width net=$irq_net drivers=$irq_sources constant_width=[get_property CONFIG.CONST_WIDTH [get_bd_cells irq0]] constant_value=[get_property CONFIG.CONST_VAL [get_bd_cells irq0]]"
if {$irq_source_names ne {irq0/dout} ||
    [get_property CONFIG.CONST_WIDTH [get_bd_cells irq0]] != $irq_width ||
    [get_property CONFIG.CONST_VAL [get_bd_cells irq0]] != 0} {error "Final XDMA user-IRQ vector is not an explicit full-width zero"}
set core_irq_nets [get_bd_nets -quiet -of_objects [get_bd_pins core/irq]]
puts $reset_irq_binding "core_irq_diagnostic_nets=$core_irq_nets expected_unconnected=1"
if {[llength $core_irq_nets]} {error "Final core diagnostic IRQ unexpectedly connects into the BD"}
close $reset_irq_binding

set host_data [one_space [first_intf xdma_0 {M_AXI M_AXI_MM}]]
set host_ctrl [one_space [first_intf xdma_0 {M_AXI_LITE M_AXI_LITE_MASTER}]]
set core_data [one_space [get_bd_intf_pins core/M_AXI_DATA]]
set core_mlp_data [one_space [get_bd_intf_pins core/M_AXI_MLP_DATA]]
set core_weight0 [one_space [get_bd_intf_pins core/M_AXI_WEIGHT_C0]]
set core_weight1 [one_space [get_bd_intf_pins core/M_AXI_WEIGHT_C1]]
set mem0 [one_segment [first_intf ddr4_0 \
    {C0_DDR4_S_AXI S_AXI c0_ddr4_s_axi}]]
set mem1 [one_segment [first_intf ddr4_1 \
    {C0_DDR4_S_AXI S_AXI c0_ddr4_s_axi}]]
set control [one_segment [get_bd_intf_pins core/S_AXIL]]
foreach {space target offset range} [list \
    $host_data $mem0 0x00000000 0x80000000 \
    $host_data $mem1 0x80000000 0x80000000 \
    $core_data $mem0 0x00000000 0x80000000 \
    $core_mlp_data $mem1 0x00000000 0x80000000 \
    $core_weight0 $mem0 0x00000000 0x80000000 \
    $core_weight1 $mem1 0x00000000 0x80000000 \
    $host_ctrl $control 0x00000000 0x00001000] {
    assign_bd_address -offset $offset -range $range \
        -target_address_space $space $target -force
}
require_map $host_data ddr4_0 0x00000000 0x80000000 2
require_map $host_data ddr4_1 0x80000000 0x80000000 2
require_map $core_data ddr4_0 0x00000000 0x80000000 1
require_map $core_mlp_data ddr4_1 0x00000000 0x80000000 1
require_map $core_weight0 ddr4_0 0x00000000 0x80000000 1
require_map $core_weight1 ddr4_1 0x00000000 0x80000000 1
require_map $host_ctrl core 0x00000000 0x00001000 1

# Later board/connection callbacks can reset the BAR size ranges to defaults.
set_property -dict [list CONFIG.pf0_bar0_size 1 CONFIG.pf0_bar2_size 4] \
    [get_bd_cells xdma_0]
foreach {key expected} $xdma_aperture_profile {
    require_cfg xdma_0 $key $expected
}
foreach slice {d0_mig_slice d1_mig_slice} {
    set snapshot [config_snapshot $slice [dict keys $slice_component_profile]]
    dict for {key expected} $slice_component_profile {
        require_number $slice $key $expected
        if {[dict get $snapshot $key] ne $expected} {
            error "$slice pre-validation snapshot $key expected=$expected actual=[dict get $snapshot $key]"
        }
    }
    dict set slice_before_validation $slice $snapshot
}
validate_bd_design
foreach slice {d0_mig_slice d1_mig_slice} {
    set snapshot [config_snapshot $slice [dict keys $slice_component_profile]]
    dict for {key expected} $slice_component_profile {
        require_number $slice $key $expected
        if {[dict get $snapshot $key] ne $expected} {
            error "$slice post-validation snapshot $key expected=$expected actual=[dict get $snapshot $key]"
        }
    }
    require_snapshot $slice [dict get $slice_before_validation $slice]
}
foreach {key expected} $xdma_aperture_profile {
    require_cfg xdma_0 $key $expected
}
foreach cell {rst_core rst_ddr0 rst_ddr1} {
    require_cfg $cell RESET_BOARD_INTERFACE Custom
    if {[get_property CONFIG.POLARITY [get_bd_pins $cell/ext_reset_in]] ne
        "ACTIVE_LOW"} {
        error "$cell external reset pin lost ACTIVE_LOW polarity"
    }
    require_cfg $cell C_EXT_RESET_HIGH 0
}
require_clock_metadata core [get_bd_pins core/core_clk] 80000000
require_clock_metadata ddr0 [get_bd_pins core/ddr0_clk] 200000000
require_clock_metadata ddr1 [get_bd_pins core/ddr1_clk] 200000000
foreach cell {ddr4_0 ddr4_1} {
    require_number $cell C0.DDR4_TimePeriod 1250
    require_clock_metadata $cell [get_bd_pins $cell/c0_ddr4_ui_clk] 200000000
}
save_bd_design
set bd_file [file join $project_dir $project_name.srcs sources_1 bd \
    $bd_name $bd_name.bd]
if {$validate_only} {
    # This bounded construction mode stops before IP output generation or runs.
    require_map $core_data ddr4_0 0x00000000 0x80000000 1
    require_map $core_mlp_data ddr4_1 0x00000000 0x80000000 1
    require_number d1_smc NUM_SI 3
    require_number d1_smc NUM_CLKS 2
    require_clock_metadata mlp_data_cdc [get_bd_pins d1_smc/aclk1] 80000000
    set width [get_property CONFIG.DATA_WIDTH [get_bd_intf_pins core/M_AXI_MLP_DATA]]
    if {$width != 256} {error "MLP DATA width must be 256, got $width"}
    set summary [open [file join $report_dir bd_validation_summary.txt] w]
    puts $summary "scope=Vivado BD construction and validate_bd_design only"
    puts $summary "ip_output_generation=not_run"
    puts $summary "synthesis_implementation=not_run"
    puts $summary "bd=$bd_file"
    puts $summary "mlp_data_width=$width"
    puts $summary "mlp_data_target=DDR1 local 0x00000000 range 0x80000000"
    puts $summary "mlp_data_link=[interface_link_snapshot \
        [get_bd_intf_pins core/M_AXI_MLP_DATA] [get_bd_intf_pins d1_smc/S00_AXI]]"
    puts $summary "attention_data_link=[interface_link_snapshot \
        [get_bd_intf_pins core/M_AXI_DATA] [get_bd_intf_pins d0_smc/S00_AXI]]"
    puts $summary "core_hz=80000000"
    puts $summary "ddr_ui_hz=200000000"
    close $summary
    exec sha256sum --status -c [file join $report_dir constructor_inputs.sha256]
    puts {M002_BD_VALIDATION_PASS}
    close_project
    exit 0
}
generate_target all [get_files $bd_file]
make_wrapper -files [get_files $bd_file] -top
set wrapper [file join $project_dir $project_name.gen sources_1 bd \
    $bd_name hdl [format "%s_wrapper.v" $bd_name]]
add_files -norecurse $wrapper
set_property top [format "%s_wrapper" $bd_name] [current_fileset]
update_compile_order -fileset sources_1
if {[get_property TOP [get_filesets sources_1]] ne [format "%s_wrapper" $bd_name]} {
    error "M006 generated wrapper is not the actual synthesis top"
}
if {[lsort [get_property VERILOG_DEFINE [get_filesets sources_1]]] ne [lsort $defines]} {
    error "M006 actual source defines differ from the frozen production selection"
}
report_compile_order -sources -used_in synthesis -file [file join $report_dir compile_order_sources.rpt]
report_compile_order -constraints -used_in implementation -file [file join $report_dir compile_order_constraints.rpt]
m006_visible_identity [file join $report_dir elaboration_identity.txt] validated_bd_generated_ip_wrapper

set summary [open [file join $report_dir constructor_summary.txt] w]
puts $summary "scope=validated_bd_generated_ip_wrapper"
puts $summary "actual_top=[get_property TOP [get_filesets sources_1]]"
puts $summary "parameter_values_source=static_bound_source"
puts $summary "actual_elaboration_parameters=unavailable"
generated_file_identity $summary production_shape [file join $report_dir production_shape.json]
generated_file_identity $summary elaboration_identity [file join $report_dir elaboration_identity.txt]
generated_file_identity $summary compile_order_sources [file join $report_dir compile_order_sources.rpt]
generated_file_identity $summary compile_order_constraints [file join $report_dir compile_order_constraints.rpt]
puts $summary "vivado_version=[version -short]"
puts $summary "part=[get_property PART [current_project]]"
puts $summary "board_part=[get_property BOARD_PART [current_project]]"
puts $summary "project=$project_dir"
puts $summary "verilog_defines=$defines"
puts $summary "xci_json_parser=[exec jq --version]"
puts $summary "core_bd_clock_hz=[require_clock_metadata core \
    [get_bd_pins core/core_clk] 80000000]"
puts $summary "core_ddr0_bd_clock_hz=[require_clock_metadata core_ddr0 \
    [get_bd_pins core/ddr0_clk] 200000000]"
puts $summary "core_ddr1_bd_clock_hz=[require_clock_metadata core_ddr1 \
    [get_bd_pins core/ddr1_clk] 200000000]"
generated_file_identity $summary bd $bd_file
generated_file_identity $summary wrapper $wrapper
generated_file_identity $summary explicit_ddr_pins $ddr_pin_xdc
foreach slice {d0_mig_slice d1_mig_slice} {
    set slice_xci [unique_generated_file [file join $project_dir \
        ${project_name}.srcs sources_1 bd $bd_name ip \
        ${bd_name}_${slice}_* *.xci]]
    generated_file_identity $summary "$slice.xci" $slice_xci
    dict for {key expected} $slice_component_profile {
        require_number $slice $key $expected
        set bd_value [get_property CONFIG.$key [get_bd_cells $slice]]
        set xci_value [xci_component_value $slice_xci $key]
        if {$xci_value ne $expected} {
            error "$slice generated XCI component $key expected=$expected actual=$xci_value"
        }
        puts $summary "$slice.$key.bd=$bd_value"
        puts $summary "$slice.xci_component.$key=$xci_value"
    }
    dict for {key expected} $slice_model_profile {
        set value [xci_model_value $slice_xci $key]
        if {$value ne $expected} {
            error "$slice generated XCI model $key expected=$expected actual=$value"
        }
        puts $summary "$slice.xci_model.$key=$value"
    }
}
foreach {cell memory_interface reference_interface slice} {
    ddr4_0 ddr4_sdram_c1 default_250mhz_clk1 d0_mig_slice
    ddr4_1 ddr4_sdram_c2 default_250mhz_clk2 d1_mig_slice
} {
    set memory_port [board_port_snapshot $cell C0_DDR4 $memory_interface]
    set reference_port [board_port_snapshot $cell C0_SYS_CLK $reference_interface]
    if {$memory_port ne [dict get $mig_board_ports $cell memory] ||
        $reference_port ne [dict get $mig_board_ports $cell reference]} {
        error "$cell board connection changed after IP generation"
    }
    set xci [unique_generated_file [file join $project_dir \
        ${project_name}.srcs sources_1 bd $bd_name ip \
        ${bd_name}_${cell}_* *.xci]]
    set board_generated_xdc [unique_generated_file [file join $project_dir \
        ${project_name}.gen sources_1 bd $bd_name ip \
        ${bd_name}_${cell}_* *_board.xdc]]
    generated_file_identity $summary "$cell.xci" $xci
    generated_file_identity $summary "$cell.generated_board_xdc" $board_generated_xdc
    set xdc_handle [open $board_generated_xdc r]
    set xdc_text [read $xdc_handle]
    close $xdc_handle
    puts $summary "$cell.generated_board_xdc_pin_or_loc_tokens=[regexp -all -- {\m(PACKAGE_PIN|LOC)\M} $xdc_text]"
    puts $summary "$cell.memory_board_port=$memory_port"
    puts $summary "$cell.reference_board_port=$reference_port"
    puts $summary "$cell.axi_link=[interface_link_snapshot \
        [get_bd_intf_pins $slice/M_AXI] \
        [first_intf $cell {C0_DDR4_S_AXI S_AXI c0_ddr4_s_axi}]]"
    foreach {key expected} {
        C0.DDR4_MemoryType Components
        C0.DDR4_MemoryPart MT40A256M16GE-083E
        C0.DDR4_Slot Single
        C0.DDR4_Capacity 512
        C0.DDR4_DataWidth 64
        C0.DDR4_Ecc false
        C0.DDR4_MCS_ECC false
        C0.DDR4_PhyClockRatio 4:1
        C0.DDR4_AxiDataWidth 512
        C0.DDR4_AxiAddressWidth 31
        C0.DDR4_InputClockPeriod 4000
        C0.DDR4_TimePeriod 1250
    } {
        set bd_value [get_property CONFIG.$key [get_bd_cells $cell]]
        set xci_value [xci_component_value $xci $key]
        if {$bd_value ne $expected || $xci_value ne $expected} {
            error "$cell $key expected=$expected BD=$bd_value XCI=$xci_value"
        }
        puts $summary "$cell.$key.bd=$bd_value"
        puts $summary "$cell.$key.xci=$xci_value"
    }
    foreach {interface key expected} {
        C0_SYS_CLK FREQ_HZ 250000000
        C0_DDR4 TIMEPERIOD_PS 1250
        C0_DDR4 MEMORY_PART MT40A256M16GE-083E
        C0_DDR4 DATA_WIDTH 64
        C0_DDR4_CLOCK FREQ_HZ 200000000
    } {
        set value [xci_interface_value $xci $interface $key]
        if {$value ne $expected} {
            error "$cell generated XCI interface $interface/$key expected=$expected actual=$value"
        }
        puts $summary "$cell.xci_interface.$interface.$key=$value"
    }
    puts $summary "$cell.reference_bd_clock_hz=[require_clock_metadata \
        $reference_interface [get_bd_intf_ports $reference_interface] 250000000]"
    puts $summary "$cell.ui_bd_clock_hz=[require_clock_metadata \
        $cell [get_bd_pins $cell/c0_ddr4_ui_clk] 200000000]"
}
puts $summary "xdma_host_data_link=[interface_link_snapshot \
    [first_intf xdma_0 {M_AXI M_AXI_MM}] \
    [get_bd_intf_pins host_split/S00_AXI]]"
puts $summary "xdma_control_link=[interface_link_snapshot \
    [first_intf xdma_0 {M_AXI_LITE M_AXI_LITE_MASTER}] \
    [get_bd_intf_pins ctrl_smc/S00_AXI]]"
puts $summary "core_data_link=[interface_link_snapshot \
    [get_bd_intf_pins core/M_AXI_DATA] [get_bd_intf_pins d0_smc/S00_AXI]]"
puts $summary "core_mlp_data_link=[interface_link_snapshot \
    [get_bd_intf_pins core/M_AXI_MLP_DATA] [get_bd_intf_pins d1_smc/S00_AXI]]"
puts $summary "core_weight0_link=[interface_link_snapshot \
    [get_bd_intf_pins core/M_AXI_WEIGHT_C0] [get_bd_intf_pins d0_smc/S01_AXI]]"
puts $summary "core_weight1_link=[interface_link_snapshot \
    [get_bd_intf_pins core/M_AXI_WEIGHT_C1] [get_bd_intf_pins d1_smc/S02_AXI]]"
set xdma_xci [unique_generated_file [file join $project_dir \
    ${project_name}.srcs sources_1 bd $bd_name ip \
    ${bd_name}_xdma_0_* *.xci]]
generated_file_identity $summary xdma.xci $xdma_xci
foreach {key expected} [concat {
    mode_selection Advanced
    axi_data_width 256_bit
    xdma_rnum_chnl 1
    xdma_wnum_chnl 1
} $xdma_aperture_profile] {
    require_cfg xdma_0 $key $expected
    set xci_value [xci_component_value $xdma_xci $key]
    if {$xci_value ne $expected} {
        error "xdma_0 generated XCI $key expected=$expected actual=$xci_value"
    }
    puts $summary "xdma.$key=[get_property CONFIG.$key [get_bd_cells xdma_0]]"
    puts $summary "xdma.$key.xci=$xci_value"
}
puts $summary "physical_pin_application=HOLD_until_netlist_and_DRC"
puts $summary "generated_clock_timing=HOLD_until_synthesis_and_timing_reports"
close $summary
exec sha256sum --check --status [file join $report_dir constructor_inputs.sha256]
close_project
puts "SCALELLM_RELEASE_CREATE_PASS project=$project_dir"
