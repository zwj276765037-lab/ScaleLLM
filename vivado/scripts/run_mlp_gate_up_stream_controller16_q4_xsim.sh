#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
PYTHON="${PYTHON:-/home/user/anaconda3/envs/zhouwenjun/bin/python}"
SIM=hap_mlp_gate_up_stream_controller16_q4_sim
cd "$ROOT"
"$PYTHON" model/generate_mlp_silu_artifacts.py
"$PYTHON" model/generate_mlp_gate_up_stream_controller_vectors.py
rm -rf "xsim_work/$SIM" "xsim.dir/$SIM"
mkdir -p "xsim_work/$SIM"
"$BIN/xvlog" -sv \
    rtl/mlp/hap_a8w4_pack2_dsp.sv \
    rtl/mlp/hap_a8w4_group32_pack2_s17.sv \
    rtl/mlp/hap_a8w4_scalecode_recover2_lut.sv \
    rtl/mlp/hap_a8w4_group32_lane2_s36.sv \
    rtl/mlp/hap_a8w4_slice8x16_group_s36.sv \
    rtl/mlp/hap_mlp_tile_accum_s36.sv \
    rtl/mlp/hap_mlp_gate_up_slice8x16_s43.sv \
    rtl/mlp/hap_mlp_gate_up_dual_slice16x16_s43.sv \
    rtl/mlp/hap_mlp_silu_mul.sv \
    rtl/mlp/hap_mlp_hadamard32_s32_norm_stream.sv \
    rtl/mlp/hap_mlp_robust_a8_quantizer_s35.sv \
    rtl/mlp/hap_mlp_product_frontend16_q4.sv \
    rtl/mlp/hap_mlp_swiglu_product_frontend16_q4.sv \
    rtl/mlp/hap_mlp_gate_up_stream_controller16_q4.sv \
    rtl/attention/hap_u16_div_u8_seq.sv \
    tb/hap_mlp_gate_up_stream_controller16_q4_tb.sv
"$BIN/xelab" hap_mlp_gate_up_stream_controller16_q4_tb \
    -L unisims_ver -s "$SIM"
"$BIN/xsim" "$SIM" -runall
