set script_dir [file dirname [file normalize [info script]]]
set root [file normalize [file join $script_dir ../..]]
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "V5 board project creation requires HAP_JOBS=32"
}
set_param general.maxThreads $jobs

# This entry point selects V5 without changing the default V4 behavior of the
# shared BD constructor.  Every generated name/path is independent from V4.
set ::env(HAP_BOARD_PROFILE) V5_FULL_BOARD
set ::env(HAP_PROJECT_NAME) attention_mlp_vcu118_v5_dual_ddr
set ::env(HAP_BD_NAME) attention_mlp_vcu118_v5_bd
set ::env(HAP_BOARD_MANIFEST) [file join $root vivado manifests \
    attention_mlp_board_core_v5_sources.list]
set ::env(HAP_BOARD_XDC) [file join $root vivado constraints \
    attention_mlp_vcu118_board_v5.xdc]
set ::env(HAP_BOARD_DEFINES) [list \
    HAP_BOARD_BUILD \
    HAP_BOARD_V5 \
    HAP_MLP_FULL_COMMAND_V5_MODULE=hap_mlp_full_command16_s45]
set ::env(HAP_DUAL_RESET_GATE_MODULE) hap_v5_dual_async_ready_gate_xpm
set ::env(HAP_RESET_GATE_MODULE) hap_v5_reset_gate_xpm
set ::env(HAP_BOARD_CORE_CLK_MHZ) 100.0
set ::env(HAP_BOARD_DDR_UI_CLK_HZ) 300000000
if {![info exists ::env(HAP_PROJECT_DIR)]} {
    set ::env(HAP_PROJECT_DIR) [file join $root vivado project \
        attention_mlp_vcu118_v5_dual_ddr]
}

source [file join $script_dir create_attention_mlp_vcu118_dual_ddr_bd.tcl]
