#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
PYTHON="${PYTHON:-/home/user/anaconda3/envs/zhouwenjun/bin/python}"
SIM=hap_mlp_serial_ddr_command16_s45_sim
WORK="$ROOT/xsim_work/$SIM"
cd "$ROOT"
"$PYTHON" model/generate_mlp_silu_artifacts.py >/dev/null
"$PYTHON" model/generate_mlp_serial_ddr_command16_s45_vectors.py
rm -rf "$WORK" "$ROOT/xsim.dir/$SIM"
mkdir -p "$WORK/work"
"$BIN/xvlog" -sv --work "work=$WORK/work" \
    rtl/mlp/hap_a8w4_pack2_dsp.sv \
    rtl/mlp/hap_a8w4_group32_pack2_s17.sv \
    rtl/mlp/hap_a8w4_scalecode_recover2_lut.sv \
    rtl/mlp/hap_a8w4_group32_lane2_s36.sv \
    rtl/mlp/hap_a8w4_slice8x16_group_s36.sv \
    rtl/mlp/hap_mlp_tile_accum_s36.sv \
    rtl/mlp/hap_mlp_silu_mul.sv \
    rtl/mlp/hap_mlp_hadamard32_s32_norm_stream.sv \
    rtl/mlp/hap_mlp_robust_a8_quantizer_s35.sv \
    rtl/mlp/hap_mlp_product_frontend16_q4.sv \
    rtl/mlp/hap_mlp_swiglu_product_frontend16_q4.sv \
    rtl/mlp/hap_mlp_gate_up_external_scheduler16_q4.sv \
    rtl/mlp/hap_mlp_down_activation_cache16.sv \
    rtl/mlp/hap_mlp_down_group_major_accum_s45.sv \
    rtl/mlp/hap_mlp_down_activation_replay16.sv \
    rtl/mlp/hap_mlp_shared_slice8x16_s43_s45.sv \
    rtl/mlp/hap_mlp_shared_dual_slice16x16_s43_s45.sv \
    rtl/mlp/hap_axi512_w4_weight_reader.sv \
    rtl/mlp/hap_ddr512_w4_halfgroup_async.sv \
    rtl/mlp/hap_mlp_w4_dual_channel_join.sv \
    rtl/mlp/hap_mlp_w4_dual_ddr_frontend.sv \
    rtl/mlp/hap_mlp_serial_ddr_command16_s45.sv \
    rtl/attention/hap_u16_div_u8_seq.sv \
    tb/hap_mlp_serial_ddr_command16_s45_tb.sv
GLBL_V="${GLBL_V:-$BIN/../ids_lite/ISE/verilog/src/glbl.v}"
"$BIN/xvlog" --work "work=$WORK/work" "$GLBL_V"
"$BIN/xelab" -L "work=$WORK/work" -L xpm \
    work.hap_mlp_serial_ddr_command16_s45_tb work.glbl \
    -s "$SIM" --debug typical
"$BIN/xsim" "$SIM" -runall --log "$WORK/xsim.log"
grep -Fq 'PASS: hap_mlp_serial_ddr_command16_s45' "$WORK/xsim.log"
echo 'PASS: serial gate/up+down DDR command xsim gate completed.'
