set dcp [file normalize $::env(HAP_DCP)]
set out [file normalize $::env(HAP_SELECTOR_FILE)]
if {![string match "2025.2*" [version -short]]} {error "Vivado 2025.2 required"}
open_checkpoint $dcp
set roots [lsort -dictionary [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME =~ hap_mlp_shared_slice8x16_s43_s45* ||
    REF_NAME =~ hap_mlp_shared_slice8x16_s43_s45*
}]]
if {[llength $roots] != 2} {error "Expected two slices"}
set names [list slice0 slice1 gate0 gate1 down0 down1 projection0_0 \
    projection0_1 projection0_2 projection0_3 projection0_4 \
    projection0_5 projection0_6 projection0_7 \
    projection7_13 projection7_14 projection7_15]
set paths [list [lindex $roots 0] [lindex $roots 1] \
    u_meta_bank/u_gate_bank0 u_meta_bank/u_gate_bank1 \
    u_meta_bank/u_down_bank0 u_meta_bank/u_down_bank1 \
    u_compute/u_attention/u_compute/u_projection/u_array/g_row\[0\].g_col\[0\].u_lane \
    u_compute/u_attention/u_compute/u_projection/u_array/g_row\[0\].g_col\[1\].u_lane \
    u_compute/u_attention/u_compute/u_projection/u_array/g_row\[0\].g_col\[2\].u_lane \
    u_compute/u_attention/u_compute/u_projection/u_array/g_row\[0\].g_col\[3\].u_lane \
    u_compute/u_attention/u_compute/u_projection/u_array/g_row\[0\].g_col\[4\].u_lane \
    u_compute/u_attention/u_compute/u_projection/u_array/g_row\[0\].g_col\[5\].u_lane \
    u_compute/u_attention/u_compute/u_projection/u_array/g_row\[0\].g_col\[6\].u_lane \
    u_compute/u_attention/u_compute/u_projection/u_array/g_row\[0\].g_col\[7\].u_lane \
    u_compute/u_attention/u_compute/u_projection/u_array/g_row\[7\].g_col\[13\].u_lane \
    u_compute/u_attention/u_compute/u_projection/u_array/g_row\[7\].g_col\[14\].u_lane \
    u_compute/u_attention/u_compute/u_projection/u_array/g_row\[7\].g_col\[15\].u_lane]
set expected_dsp {2048 2048 0 0 0 0 17 17 17 17 17 17 17 17 17 17 17}
set expected_uram {0 0 224 224 112 112 0 0 0 0 0 0 0 0 0 0 0}
set f [open $out w]
set index 0
foreach name $names path $paths want_dsp $expected_dsp want_uram $expected_uram {
    set cells [get_cells -quiet -hierarchical -filter "NAME =~ $path/*"]
    set dsp [get_cells -quiet -hierarchical -filter \
        "REF_NAME == DSP48E2 && NAME =~ $path/*"]
    set uram [get_cells -quiet -hierarchical -filter \
        "REF_NAME == URAM288 && NAME =~ $path/*"]
    puts $f "$name root=$path descendants=[llength $cells] dsp=[llength $dsp] uram=[llength $uram]"
    if {[llength $cells] == 0 || [llength $dsp] != $want_dsp ||
        [llength $uram] != $want_uram} {
        close $f
        error "Selector $name failed expected DSP/URAM $want_dsp/$want_uram"
    }
    incr index
}
puts $f "status=SELECTORS_PASS"
close $f
close_design
