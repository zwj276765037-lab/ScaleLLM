set sd [file dirname [file normalize [info script]]]
set root [file normalize [file join $sd ../..]]
set board_profile [expr {[info exists ::env(HAP_BOARD_PROFILE)] ?
    $::env(HAP_BOARD_PROFILE) : "V4_COMPAT"}]
set strict_v5 [expr {$board_profile eq "V5_FULL_BOARD"}]
set project_dir [expr {[info exists ::env(HAP_PROJECT_DIR)] ?
    [file normalize $::env(HAP_PROJECT_DIR)] :
    [file join $root vivado project attention_mlp_vcu118_dual_ddr]}]
set project_name [expr {[info exists ::env(HAP_PROJECT_NAME)] ?
    $::env(HAP_PROJECT_NAME) : "attention_mlp_vcu118_dual_ddr"}]
set bd [expr {[info exists ::env(HAP_BD_NAME)] ?
    $::env(HAP_BD_NAME) : "attention_mlp_vcu118_bd"}]
set board_manifest [expr {[info exists ::env(HAP_BOARD_MANIFEST)] ?
    [file normalize $::env(HAP_BOARD_MANIFEST)] :
    [file join $root vivado manifests attention_mlp_board_core_sources.list]}]
set board_xdc [expr {[info exists ::env(HAP_BOARD_XDC)] ?
    [file normalize $::env(HAP_BOARD_XDC)] :
    [file join $root vivado constraints attention_mlp_vcu118_board.xdc]}]
set board_defines [expr {[info exists ::env(HAP_BOARD_DEFINES)] ?
    $::env(HAP_BOARD_DEFINES) : [list HAP_BOARD_BUILD]}]
set core_clk_mhz 150.0
set expected_ddr_ui_clk_hz 300000000
if {$strict_v5} {
    if {[info exists ::env(HAP_BOARD_CORE_CLK_MHZ)]} {
        set core_clk_mhz $::env(HAP_BOARD_CORE_CLK_MHZ)
    }
    if {[info exists ::env(HAP_BOARD_DDR_UI_CLK_HZ)]} {
        set expected_ddr_ui_clk_hz $::env(HAP_BOARD_DDR_UI_CLK_HZ)
    }
}

if {[lsearch -exact {V4_COMPAT V5_FULL_BOARD} $board_profile] < 0} {
    error "Unsupported HAP_BOARD_PROFILE: $board_profile"
}

foreach {label value} [list project_name $project_name bd_name $bd] {
    if {![regexp {^[A-Za-z][A-Za-z0-9_]*$} $value]} {
        error "Unsafe $label: $value"
    }
}
foreach {label path} [list board_manifest $board_manifest board_xdc $board_xdc] {
    if {![file exists $path] || ![file isfile $path] || [file size $path] == 0} {
        error "Missing or empty $label: $path"
    }
}
if {[llength $board_defines] == 0} {error "HAP_BOARD_DEFINES is empty"}

# V4 compatibility remains the default for the historical entry point.  The
# dedicated V5 wrapper selects this strict profile and cannot silently replace
# any source graph, top name, define, XDC, clock, or reset-gate implementation.
if {$strict_v5} {
    if {![string match "2025.2*" [version -short]]} {
        error "V5 full-board construction requires Vivado 2025.2, got [version -short]"
    }
    set expected_manifest [file normalize [file join $root vivado manifests \
        attention_mlp_board_core_v5_sources.list]]
    set expected_xdc [file normalize [file join $root vivado constraints \
        attention_mlp_vcu118_board_v5.xdc]]
    if {$project_name ne "attention_mlp_vcu118_v5_dual_ddr" ||
        $bd ne "attention_mlp_vcu118_v5_bd"} {
        error "V5 project/BD identity mismatch: project=$project_name bd=$bd"
    }
    set v4_project_dir [file normalize [file join $root vivado project \
        attention_mlp_vcu118_dual_ddr]]
    if {$project_dir eq $v4_project_dir} {
        error "V5 construction refuses the preserved V4 project directory"
    }
    if {[file exists $project_dir] && ![file isdirectory $project_dir]} {
        error "V5 project path is not a directory: $project_dir"
    }
    foreach existing_xpr [glob -nocomplain -directory $project_dir *.xpr] {
        if {[file tail $existing_xpr] ne
            "attention_mlp_vcu118_v5_dual_ddr.xpr"} {
            error "V5 construction refuses directory containing another project: $existing_xpr"
        }
    }
    if {$board_manifest ne $expected_manifest} {
        error "V5 source manifest substitution rejected: $board_manifest"
    }
    if {$board_xdc ne $expected_xdc} {
        error "V5 board XDC substitution rejected: $board_xdc"
    }
    set expected_defines [list HAP_BOARD_BUILD HAP_BOARD_V5 \
        HAP_MLP_FULL_COMMAND_V5_MODULE=hap_mlp_full_command16_s46]
    if {[lsort $board_defines] ne [lsort $expected_defines]} {
        error "V5 define contract mismatch: expected=$expected_defines actual=$board_defines"
    }
    if {![string is double -strict $core_clk_mhz] ||
        abs(double($core_clk_mhz) - 100.0) > 0.000001} {
        error "V5 core clock must be exactly 100.0 MHz, got $core_clk_mhz"
    }
    if {![string is entier -strict $expected_ddr_ui_clk_hz] ||
        $expected_ddr_ui_clk_hz != 300000000} {
        error "V5 DDR UI clocks must be exactly 300000000 Hz"
    }
}

proc latest_ip {name} {
    set x [get_ipdefs -quiet -all "xilinx.com:ip:${name}:*"]
    if {![llength $x]} {error "IP not found: $name"}
    return [lindex $x end]
}
proc setcfg {cell key val} {
    if {[catch {set_property CONFIG.$key $val [get_bd_cells $cell]} m]} {
        puts "INFO: skip $cell CONFIG.$key=$val ($m)"
    }
}
proc requirecfg {cell key expected} {
    set actual [get_property CONFIG.$key [get_bd_cells $cell]]
    if {$actual ne $expected} {
        error "$cell CONFIG.$key expected $expected, got $actual"
    }
}
proc requirecfg_number {cell key expected {tolerance 0.0}} {
    set actual [get_property CONFIG.$key [get_bd_cells $cell]]
    if {![string is double -strict $actual] ||
        abs(double($actual) - double($expected)) > double($tolerance)} {
        error "$cell CONFIG.$key expected $expected, got $actual"
    }
}
proc first_intf {cell names} {
    foreach n $names {
        set x [get_bd_intf_pins -quiet $cell/$n]
        if {[llength $x]} {return $x}
    }
    error "missing interface $cell $names"
}
proc first_pin {cell names} {
    foreach n $names {
        set x [get_bd_pins -quiet $cell/$n]
        if {[llength $x]} {return $x}
    }
    error "missing pin $cell $names"
}
proc create_mig_ready {tag calib ui_sync_rst} {
    set inv ${tag}_ui_sync_rst_inv
    set gate ${tag}_ready_and
    create_bd_cell -type ip -vlnv [latest_ip util_vector_logic] $inv
    set_property -dict [list CONFIG.C_SIZE 1 CONFIG.C_OPERATION not] \
        [get_bd_cells $inv]
    requirecfg $inv C_SIZE 1
    requirecfg $inv C_OPERATION not
    create_bd_cell -type ip -vlnv [latest_ip util_vector_logic] $gate
    set_property -dict [list CONFIG.C_SIZE 1 CONFIG.C_OPERATION and] \
        [get_bd_cells $gate]
    requirecfg $gate C_SIZE 1
    requirecfg $gate C_OPERATION and
    connect_bd_net $ui_sync_rst [get_bd_pins $inv/Op1]
    connect_bd_net $calib [get_bd_pins $gate/Op1]
    connect_bd_net [get_bd_pins $inv/Res] [get_bd_pins $gate/Op2]
    return [get_bd_pins $gate/Res]
}
proc bd_pin_freq_hz {pin} {
    set f [get_property -quiet CONFIG.FREQ_HZ $pin]
    if {$f eq ""} {set f [get_property -quiet FREQ_HZ $pin]}
    return $f
}
proc require_same_bd_net {label pins} {
    set expected {}
    foreach pin $pins {
        set nets [get_bd_nets -quiet -of_objects $pin]
        if {[llength $nets] != 1} {
            error "$label pin is not connected to exactly one net: $pin nets=$nets"
        }
        set net [lindex $nets 0]
        if {$expected eq {}} {set expected $net}
        if {$net ne $expected} {
            error "$label pins are not on one net: expected=$expected actual=$net pin=$pin"
        }
    }
}
proc require_one_bd_addr_space {label intf_pin} {
    set spaces [get_bd_addr_spaces -quiet -of_objects $intf_pin]
    if {[llength $spaces] != 1} {
        error "$label must expose exactly one address space: pin=$intf_pin spaces=$spaces"
    }
    return [lindex $spaces 0]
}
proc require_one_bd_slave_segment {label intf_pin} {
    set segments [get_bd_addr_segs -quiet -of_objects $intf_pin]
    if {[llength $segments] != 1} {
        error "$label must expose exactly one slave segment: pin=$intf_pin segments=$segments"
    }
    return [lindex $segments 0]
}
proc bd_address_number {label value} {
    if {[regexp -nocase {^([0-9]+)([KMG])$} $value -> count unit]} {
        set shift [dict get [dict create K 10 M 20 G 30] [string toupper $unit]]
        return [expr {wide($count) << $shift}]
    }
    if {[catch {expr {wide($value)}} number]} {
        error "$label is not an integer address value: $value"
    }
    return $number
}
proc require_bd_address_mapping {label space target_token expected_offset \
        expected_range expected_count} {
    set segments [get_bd_addr_segs -quiet -of_objects $space]
    if {[llength $segments] != $expected_count} {
        error "$label address-space segment count mismatch: expected=$expected_count actual=[llength $segments] segments=$segments"
    }
    set matches {}
    foreach segment $segments {
        if {[string match "*${target_token}*" $segment]} {
            lappend matches $segment
        }
    }
    if {[llength $matches] != 1} {
        error "$label target segment is not unique: token=$target_token matches=$matches all=$segments"
    }
    set segment [lindex $matches 0]
    set actual_offset [bd_address_number "$label OFFSET" \
        [get_property OFFSET $segment]]
    set actual_range [bd_address_number "$label RANGE" \
        [get_property RANGE $segment]]
    if {$actual_offset != [bd_address_number "$label expected OFFSET" \
            $expected_offset] ||
        $actual_range != [bd_address_number "$label expected RANGE" \
            $expected_range]} {
        error "$label address mismatch: expected=$expected_offset/$expected_range actual=[get_property OFFSET $segment]/[get_property RANGE $segment] segment=$segment"
    }
}
proc assign_v5_address_map {} {
    set host_data [require_one_bd_addr_space "V5 XDMA data" \
        [first_intf xdma_0 {M_AXI M_AXI_MM}]]
    set host_ctrl [require_one_bd_addr_space "V5 XDMA AXI-Lite" \
        [first_intf xdma_0 {M_AXI_LITE M_AXI_LITE_MASTER}]]
    set core_data [require_one_bd_addr_space "V5 core tensor" \
        [get_bd_intf_pins core/M_AXI_DATA]]
    set core_weight0 [require_one_bd_addr_space "V5 core DDR0 weight" \
        [get_bd_intf_pins core/M_AXI_WEIGHT_C0]]
    set core_weight1 [require_one_bd_addr_space "V5 core DDR1 weight" \
        [get_bd_intf_pins core/M_AXI_WEIGHT_C1]]
    set ddr0 [require_one_bd_slave_segment "V5 DDR0" \
        [first_intf ddr4_0 {C0_DDR4_S_AXI S_AXI c0_ddr4_s_axi}]]
    set ddr1 [require_one_bd_slave_segment "V5 DDR1" \
        [first_intf ddr4_1 {C0_DDR4_S_AXI S_AXI c0_ddr4_s_axi}]]
    set control [require_one_bd_slave_segment "V5 control" \
        [get_bd_intf_pins core/S_AXIL]]

    # XDMA uses one 4-GiB global aperture.  Compute masters retain 32-bit
    # channel-local addresses, so DDR1 bases programmed into RTL do not carry
    # the Host-only 0x80000000 translation.
    assign_bd_address -offset 0x00000000 -range 0x80000000 \
        -target_address_space $host_data $ddr0 -force
    assign_bd_address -offset 0x80000000 -range 0x80000000 \
        -target_address_space $host_data $ddr1 -force
    assign_bd_address -offset 0x00000000 -range 0x80000000 \
        -target_address_space $core_data $ddr0 -force
    assign_bd_address -offset 0x00000000 -range 0x80000000 \
        -target_address_space $core_weight0 $ddr0 -force
    assign_bd_address -offset 0x00000000 -range 0x80000000 \
        -target_address_space $core_weight1 $ddr1 -force
    assign_bd_address -offset 0x00000000 -range 0x00001000 \
        -target_address_space $host_ctrl $control -force

    require_bd_address_mapping "V5 XDMA DDR0" $host_data ddr4_0 \
        0x00000000 0x80000000 2
    require_bd_address_mapping "V5 XDMA DDR1" $host_data ddr4_1 \
        0x80000000 0x80000000 2
    require_bd_address_mapping "V5 core tensor DDR0" $core_data ddr4_0 \
        0x00000000 0x80000000 1
    require_bd_address_mapping "V5 core weight DDR0" $core_weight0 ddr4_0 \
        0x00000000 0x80000000 1
    require_bd_address_mapping "V5 core weight DDR1" $core_weight1 ddr4_1 \
        0x00000000 0x80000000 1
    require_bd_address_mapping "V5 XDMA control" $host_ctrl core \
        0x00000000 0x00001000 1
}
proc add_manifest {root manifest} {
    set fh [open $manifest r]
    foreach raw [split [read $fh] "\n"] {
        set line [string trim $raw]
        if {$line eq "" || [string index $line 0] eq "#"} {continue}
        set path [file normalize [file join $root $line]]
        if {[string match "*.list" $path]} {
            add_manifest $root $path
            continue
        }
        if {![file exists $path]} {error "Missing source $path"}
        if {[llength [get_files -quiet $path]] == 0} {
            add_files -fileset sources_1 $path
        }
        if {[string match "*.sv" $path]} {
            set_property file_type SystemVerilog [get_files $path]
        } elseif {[string match "*.mem" $path]} {
            set_property file_type {Memory Initialization Files} [get_files $path]
        }
    }
    close $fh
}

file mkdir $project_dir
create_project $project_name $project_dir -part xcvu9p-flga2104-2L-e -force
set bp [get_board_parts -quiet xilinx.com:vcu118:part0:2.0]
if {![llength $bp]} {error "VCU118 board part 2.0 is required"}
set_property board_part [lindex $bp 0] [current_project]
set_property target_language Verilog [current_project]
set_property verilog_define $board_defines [get_filesets sources_1]
add_manifest $root $board_manifest
add_files -fileset constrs_1 $board_xdc
update_compile_order -fileset sources_1

create_bd_design $bd
create_bd_port -dir I -type rst pcie_perstn
set_property CONFIG.POLARITY ACTIVE_LOW [get_bd_ports pcie_perstn]

create_bd_cell -type ip -vlnv [latest_ip xdma] xdma_0
foreach {k v} {
    mode_selection Advanced axilite_master_en true
    axisten_if_enable_msg_route true PCIE_BOARD_INTERFACE pci_express_x8
    pl_link_cap_max_link_speed 8.0_GT/s axi_data_width 256_bit
    SYS_RST_N_BOARD_INTERFACE pcie_perstn pf0_device_id 9018
    pciebar2axibar_0 0x00000000 pf0_bar0_enabled true
    pf0_bar0_scale Megabytes pf0_bar0_size 1 pf0_bar2_enabled true
    pf0_bar2_scale Gigabytes pf0_bar2_size 4 pf0_msix_enabled false
    pf0_msi_enabled true xdma_rnum_chnl 1 xdma_wnum_chnl 1
} {setcfg xdma_0 $k $v}
if {$strict_v5} {
    foreach {k v} {
        mode_selection Advanced
        axilite_master_en true
        axisten_if_enable_msg_route true
        PCIE_BOARD_INTERFACE pci_express_x8
        pl_link_cap_max_link_speed 8.0_GT/s
        axi_data_width 256_bit
        SYS_RST_N_BOARD_INTERFACE pcie_perstn
        pf0_device_id 9018
        pciebar2axibar_0 0x00000000
        pf0_bar0_enabled true
        pf0_bar0_scale Megabytes
        pf0_bar0_size 1
        pf0_bar2_enabled true
        pf0_bar2_scale Gigabytes
        pf0_bar2_size 4
        pf0_msix_enabled false
        pf0_msi_enabled true
        xdma_rnum_chnl 1
        xdma_wnum_chnl 1
    } {requirecfg xdma_0 $k $v}
}

create_bd_cell -type module -reference vcu118_pcie_refclk_ibuf pcie_refclk_buf
connect_bd_net [get_bd_pins pcie_refclk_buf/sys_clk_gt] \
    [get_bd_pins xdma_0/sys_clk_gt]
connect_bd_net [get_bd_pins pcie_refclk_buf/sys_clk] \
    [get_bd_pins xdma_0/sys_clk]
foreach p {pcie_refclk_p pcie_refclk_n} {
    set before [get_bd_ports -quiet]
    make_bd_pins_external [get_bd_pins pcie_refclk_buf/$p]
    set ext {}
    foreach candidate [get_bd_ports -quiet] {
        if {[lsearch -exact $before $candidate] < 0} {
            set ext $candidate
            break
        }
    }
    if {$ext eq {}} {error "failed to externalize pcie_refclk_buf/$p"}
    set_property name $p $ext
}
set xclk [first_pin xdma_0 {axi_aclk axi_aclk_out}]
set xrstn [first_pin xdma_0 {axi_aresetn axi_aresetn_out}]
if {[llength [get_bd_pins -quiet xdma_0/sys_rst_n]]} {
    connect_bd_net [get_bd_ports pcie_perstn] [get_bd_pins xdma_0/sys_rst_n]
}

create_bd_cell -type ip -vlnv [latest_ip clk_wiz] clk_core
foreach {k v} {
    PRIMITIVE MMCM PRIM_SOURCE No_buffer CLKIN1_JITTER_PS 100.0
} {setcfg clk_core $k $v}
setcfg clk_core CLKOUT1_REQUESTED_OUT_FREQ $core_clk_mhz
setcfg clk_core USE_LOCKED true
setcfg clk_core USE_RESET false
if {$strict_v5} {
    requirecfg_number clk_core CLKOUT1_REQUESTED_OUT_FREQ 100.0 0.000001
}
connect_bd_net $xclk [get_bd_pins clk_core/clk_in1]
set cclk [get_bd_pins clk_core/clk_out1]

create_bd_cell -type ip -vlnv [latest_ip proc_sys_reset] rst_core
if {$strict_v5} {
    setcfg rst_core C_EXT_RESET_HIGH 0
    requirecfg rst_core C_EXT_RESET_HIGH 0
}
connect_bd_net $cclk [get_bd_pins rst_core/slowest_sync_clk]
connect_bd_net [get_bd_ports pcie_perstn] [get_bd_pins rst_core/ext_reset_in]
connect_bd_net [get_bd_pins clk_core/locked] [get_bd_pins rst_core/dcm_locked]
set crstn [get_bd_pins rst_core/peripheral_aresetn]

create_bd_cell -type ip -vlnv [latest_ip ddr4] ddr4_0
# The VCU118 default_250mhz_clk1/2 board interfaces are the external MIG
# reference clocks, so their input period is 4000 ps.  DDR4_TimePeriod=833
# selects the memory rate; the generated 300 MHz c0_ddr4_ui_clk contract is
# checked independently below from the live BD pins.
foreach {k v} {
    C0_CLOCK_BOARD_INTERFACE default_250mhz_clk1
    C0_DDR4_BOARD_INTERFACE ddr4_sdram_c1 C0.DDR4_AxiAddressWidth 31
    C0.DDR4_AxiDataWidth 512 C0.DDR4_InputClockPeriod 4000
    C0.DDR4_TimePeriod 833
} {setcfg ddr4_0 $k $v}
create_bd_cell -type ip -vlnv [latest_ip ddr4] ddr4_1
foreach {k v} {
    C0_CLOCK_BOARD_INTERFACE default_250mhz_clk2
    C0_DDR4_BOARD_INTERFACE ddr4_sdram_c2 C0.DDR4_AxiAddressWidth 31
    C0.DDR4_AxiDataWidth 512 C0.DDR4_InputClockPeriod 4000
    C0.DDR4_TimePeriod 833
} {setcfg ddr4_1 $k $v}
if {$strict_v5} {
    foreach d {ddr4_0 ddr4_1} {
        requirecfg_number $d C0.DDR4_AxiAddressWidth 31
        requirecfg_number $d C0.DDR4_AxiDataWidth 512
        requirecfg_number $d C0.DDR4_InputClockPeriod 4000
        requirecfg_number $d C0.DDR4_TimePeriod 833
    }
    requirecfg ddr4_0 C0_CLOCK_BOARD_INTERFACE default_250mhz_clk1
    requirecfg ddr4_0 C0_DDR4_BOARD_INTERFACE ddr4_sdram_c1
    requirecfg ddr4_1 C0_CLOCK_BOARD_INTERFACE default_250mhz_clk2
    requirecfg ddr4_1 C0_DDR4_BOARD_INTERFACE ddr4_sdram_c2
}
set d0clk [first_pin ddr4_0 {c0_ddr4_ui_clk}]
set d1clk [first_pin ddr4_1 {c0_ddr4_ui_clk}]
set d0cal [first_pin ddr4_0 {c0_init_calib_complete init_calib_complete}]
set d1cal [first_pin ddr4_1 {c0_init_calib_complete init_calib_complete}]
set d0ready $d0cal
set d1ready $d1cal
if {$strict_v5} {
    set d0ui_sync_rst [first_pin ddr4_0 \
        {c0_ddr4_ui_clk_sync_rst ui_clk_sync_rst}]
    set d1ui_sync_rst [first_pin ddr4_1 \
        {c0_ddr4_ui_clk_sync_rst ui_clk_sync_rst}]
    set d0ready [create_mig_ready ddr0 $d0cal $d0ui_sync_rst]
    set d1ready [create_mig_ready ddr1 $d1cal $d1ui_sync_rst]
}

create_bd_cell -type module -reference hap_attention_mlp_board_core core
connect_bd_net $cclk [get_bd_pins core/core_clk]
connect_bd_net $d0clk [get_bd_pins core/ddr0_clk]
connect_bd_net $d1clk [get_bd_pins core/ddr1_clk]

set dual_reset_gate_module [expr {[info exists ::env(HAP_DUAL_RESET_GATE_MODULE)] ?
    $::env(HAP_DUAL_RESET_GATE_MODULE) : "dual_async_ready_gate_sync"}]
set reset_gate_module [expr {[info exists ::env(HAP_RESET_GATE_MODULE)] ?
    $::env(HAP_RESET_GATE_MODULE) : "reset_gate_sync"}]
if {$strict_v5 &&
    ($dual_reset_gate_module ne "hap_v5_dual_async_ready_gate_xpm" ||
     $reset_gate_module ne "hap_v5_reset_gate_xpm")} {
    error "V5 reset gate module substitution rejected: dual=$dual_reset_gate_module single=$reset_gate_module"
}
create_bd_cell -type module -reference $dual_reset_gate_module core_gate
connect_bd_net $cclk [get_bd_pins core_gate/clk]
connect_bd_net $crstn [get_bd_pins core_gate/base_aresetn]
connect_bd_net $d0ready [get_bd_pins core_gate/async_ready0]
connect_bd_net $d1ready [get_bd_pins core_gate/async_ready1]
connect_bd_net [get_bd_pins core_gate/aresetn] [get_bd_pins core/core_rst_n]
create_bd_cell -type module -reference $reset_gate_module d0_gate
connect_bd_net $d0clk [get_bd_pins d0_gate/clk]
connect_bd_net $xrstn [get_bd_pins d0_gate/base_aresetn]
connect_bd_net $d0ready [get_bd_pins d0_gate/async_ready]
connect_bd_net [get_bd_pins d0_gate/aresetn] [get_bd_pins core/ddr0_rst_n]
create_bd_cell -type module -reference $reset_gate_module d1_gate
connect_bd_net $d1clk [get_bd_pins d1_gate/clk]
connect_bd_net $xrstn [get_bd_pins d1_gate/base_aresetn]
connect_bd_net $d1ready [get_bd_pins d1_gate/async_ready]
connect_bd_net [get_bd_pins d1_gate/aresetn] [get_bd_pins core/ddr1_rst_n]

create_bd_cell -type ip -vlnv [latest_ip proc_sys_reset] rst_ddr0
if {$strict_v5} {
    setcfg rst_ddr0 C_EXT_RESET_HIGH 0
    requirecfg rst_ddr0 C_EXT_RESET_HIGH 0
}
connect_bd_net $d0clk [get_bd_pins rst_ddr0/slowest_sync_clk]
connect_bd_net [get_bd_ports pcie_perstn] [get_bd_pins rst_ddr0/ext_reset_in]
connect_bd_net [get_bd_pins clk_core/locked] [get_bd_pins rst_ddr0/dcm_locked]
create_bd_cell -type ip -vlnv [latest_ip proc_sys_reset] rst_ddr1
if {$strict_v5} {
    setcfg rst_ddr1 C_EXT_RESET_HIGH 0
    requirecfg rst_ddr1 C_EXT_RESET_HIGH 0
}
connect_bd_net $d1clk [get_bd_pins rst_ddr1/slowest_sync_clk]
connect_bd_net [get_bd_ports pcie_perstn] [get_bd_pins rst_ddr1/ext_reset_in]
connect_bd_net [get_bd_pins clk_core/locked] [get_bd_pins rst_ddr1/dcm_locked]

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

create_bd_cell -type ip -vlnv [latest_ip smartconnect] host_split
set_property -dict [list CONFIG.NUM_SI 1 CONFIG.NUM_MI 2 CONFIG.NUM_CLKS 3] \
    [get_bd_cells host_split]
create_bd_cell -type ip -vlnv [latest_ip smartconnect] d0_smc
set_property -dict [list CONFIG.NUM_SI 3 CONFIG.NUM_MI 1 CONFIG.NUM_CLKS 2] \
    [get_bd_cells d0_smc]
create_bd_cell -type ip -vlnv [latest_ip smartconnect] d1_smc
set_property -dict [list CONFIG.NUM_SI 2 CONFIG.NUM_MI 1 CONFIG.NUM_CLKS 1] \
    [get_bd_cells d1_smc]

foreach slice {d0_mig_slice d1_mig_slice} {
    create_bd_cell -type ip -vlnv [latest_ip axi_register_slice] $slice
    foreach ch {AW AR W R B} {setcfg $slice REG_$ch 15}
    setcfg $slice USE_AUTOPIPELINING 0
    setcfg $slice NUM_SLR_CROSSINGS 2
    foreach ch {AW AR W R B} {
        setcfg $slice PIPELINES_MASTER_$ch 1
        setcfg $slice PIPELINES_SLAVE_$ch 1
        setcfg $slice PIPELINES_MIDDLE_$ch 1
        requirecfg $slice REG_$ch 15
        requirecfg $slice PIPELINES_MASTER_$ch 1
        requirecfg $slice PIPELINES_SLAVE_$ch 1
        requirecfg $slice PIPELINES_MIDDLE_$ch 1
    }
    requirecfg $slice NUM_SLR_CROSSINGS 2
}

connect_bd_intf_net [first_intf xdma_0 {M_AXI M_AXI_MM}] \
    [get_bd_intf_pins host_split/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins core/M_AXI_DATA] \
    [get_bd_intf_pins d0_smc/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins core/M_AXI_WEIGHT_C0] \
    [get_bd_intf_pins d0_smc/S01_AXI]
connect_bd_intf_net [get_bd_intf_pins host_split/M00_AXI] \
    [get_bd_intf_pins d0_smc/S02_AXI]
connect_bd_intf_net [get_bd_intf_pins core/M_AXI_WEIGHT_C1] \
    [get_bd_intf_pins d1_smc/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins host_split/M01_AXI] \
    [get_bd_intf_pins d1_smc/S01_AXI]
connect_bd_intf_net [get_bd_intf_pins d0_smc/M00_AXI] \
    [get_bd_intf_pins d0_mig_slice/S_AXI]
connect_bd_intf_net [get_bd_intf_pins d0_mig_slice/M_AXI] \
    [first_intf ddr4_0 {C0_DDR4_S_AXI S_AXI c0_ddr4_s_axi}]
connect_bd_intf_net [get_bd_intf_pins d1_smc/M00_AXI] \
    [get_bd_intf_pins d1_mig_slice/S_AXI]
connect_bd_intf_net [get_bd_intf_pins d1_mig_slice/M_AXI] \
    [first_intf ddr4_1 {C0_DDR4_S_AXI S_AXI c0_ddr4_s_axi}]

connect_bd_net $xclk [get_bd_pins host_split/aclk]
connect_bd_net $d0clk [get_bd_pins host_split/aclk1]
connect_bd_net $d1clk [get_bd_pins host_split/aclk2]
connect_bd_net $xrstn [get_bd_pins host_split/aresetn]
connect_bd_net $d0clk [get_bd_pins d0_smc/aclk]
connect_bd_net $cclk [get_bd_pins d0_smc/aclk1]
connect_bd_net [get_bd_pins d0_gate/aresetn] [get_bd_pins d0_smc/aresetn]
connect_bd_net $d1clk [get_bd_pins d1_smc/aclk]
connect_bd_net [get_bd_pins d1_gate/aresetn] [get_bd_pins d1_smc/aresetn]
connect_bd_net $d0clk [get_bd_pins d0_mig_slice/aclk]
connect_bd_net [get_bd_pins d0_gate/aresetn] [get_bd_pins d0_mig_slice/aresetn]
connect_bd_net $d1clk [get_bd_pins d1_mig_slice/aclk]
connect_bd_net [get_bd_pins d1_gate/aresetn] [get_bd_pins d1_mig_slice/aresetn]

if {[llength [get_bd_pins -quiet ddr4_0/c0_ddr4_aresetn]]} {
    connect_bd_net [get_bd_pins rst_ddr0/peripheral_aresetn] \
        [get_bd_pins ddr4_0/c0_ddr4_aresetn]
}
if {[llength [get_bd_pins -quiet ddr4_1/c0_ddr4_aresetn]]} {
    connect_bd_net [get_bd_pins rst_ddr1/peripheral_aresetn] \
        [get_bd_pins ddr4_1/c0_ddr4_aresetn]
}
foreach d {ddr4_0 ddr4_1} {
    if {[llength [get_bd_pins -quiet $d/sys_rst]]} {
        connect_bd_net [get_bd_pins rst_core/peripheral_reset] \
            [get_bd_pins $d/sys_rst]
    }
}
foreach {d bi} {ddr4_0 ddr4_sdram_c1 ddr4_1 ddr4_sdram_c2} {
    apply_board_connection -board_interface $bi \
        -ip_intf [get_bd_intf_pins $d/C0_DDR4] -diagram [current_bd_design]
}
foreach {d bi} {ddr4_0 default_250mhz_clk1 ddr4_1 default_250mhz_clk2} {
    apply_board_connection -board_interface $bi \
        -ip_intf [get_bd_intf_pins $d/C0_SYS_CLK] -diagram [current_bd_design]
}
set pcie [first_intf xdma_0 {pcie_mgt PCI_EXP}]
if {[catch {apply_board_connection -board_interface pci_express_x8 \
    -ip_intf $pcie -diagram [current_bd_design]}]} {
    make_bd_intf_pins_external $pcie
}

if {[llength [get_bd_pins -quiet xdma_0/usr_irq_req]]} {
    set iw [expr {abs([get_property LEFT [get_bd_pins xdma_0/usr_irq_req]] -
        [get_property RIGHT [get_bd_pins xdma_0/usr_irq_req]]) + 1}]
    create_bd_cell -type ip -vlnv [latest_ip xlconcat] irqcat
    setcfg irqcat NUM_PORTS $iw
    connect_bd_net [get_bd_pins core/irq] [get_bd_pins irqcat/In0]
    create_bd_cell -type ip -vlnv [latest_ip xlconstant] irq0
    for {set i 1} {$i < $iw} {incr i} {
        connect_bd_net [get_bd_pins irq0/dout] [get_bd_pins irqcat/In$i]
    }
    connect_bd_net [get_bd_pins irqcat/dout] [get_bd_pins xdma_0/usr_irq_req]
}

if {$strict_v5} {
    assign_v5_address_map
} else {
    assign_bd_address
}
validate_bd_design
if {$strict_v5} {
    foreach {label pin expected} [list \
        core [get_bd_pins core/core_clk] 100000000 \
        ddr0 [get_bd_pins core/ddr0_clk] $expected_ddr_ui_clk_hz \
        ddr1 [get_bd_pins core/ddr1_clk] $expected_ddr_ui_clk_hz] {
        set actual [bd_pin_freq_hz $pin]
        if {![string is entier -strict $actual] || $actual != $expected} {
            error "V5 $label clock contract mismatch: expected=$expected actual=$actual"
        }
    }
    require_same_bd_net "V5 core clock" [list $cclk \
        [get_bd_pins core/core_clk] [get_bd_pins core_gate/clk]]
    require_same_bd_net "V5 DDR0 UI clock" [list $d0clk \
        [get_bd_pins core/ddr0_clk] [get_bd_pins d0_gate/clk] \
        [get_bd_pins d0_smc/aclk] [get_bd_pins d0_mig_slice/aclk]]
    require_same_bd_net "V5 DDR1 UI clock" [list $d1clk \
        [get_bd_pins core/ddr1_clk] [get_bd_pins d1_gate/clk] \
        [get_bd_pins d1_smc/aclk] [get_bd_pins d1_mig_slice/aclk]]
    require_same_bd_net "V5 DDR0 calibrated/not-reset ready" [list $d0ready \
        [get_bd_pins core_gate/async_ready0] \
        [get_bd_pins d0_gate/async_ready]]
    require_same_bd_net "V5 DDR1 calibrated/not-reset ready" [list $d1ready \
        [get_bd_pins core_gate/async_ready1] \
        [get_bd_pins d1_gate/async_ready]]
}
save_bd_design
make_wrapper -files [get_files [file join $project_dir $project_name.srcs \
    sources_1 bd $bd $bd.bd]] -top
add_files -norecurse [file join $project_dir $project_name.gen \
    sources_1 bd $bd hdl ${bd}_wrapper.v]
set_property top ${bd}_wrapper [current_fileset]
close_project
puts "PASS: created independent Attention+MLP VCU118 dual-DDR/XDMA project at $project_dir"
