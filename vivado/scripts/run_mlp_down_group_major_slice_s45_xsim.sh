#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO_ROOT="${VIVADO_ROOT:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado}"
PYTHON="${PYTHON:-/home/user/anaconda3/envs/zhouwenjun/bin/python}"
SIM=hap_mlp_down_group_major_slice8x16_s45_sim
cd "$ROOT"
"$PYTHON" model/generate_mlp_down_group_major_slice_s45_vectors.py
rm -rf "xsim_work/$SIM" "xsim.dir/$SIM"
mkdir -p "xsim_work/$SIM"
"$VIVADO_ROOT/bin/xvlog" -sv \
    rtl/mlp/hap_a8w4_pack2_dsp.sv \
    rtl/mlp/hap_a8w4_group32_pack2_s17.sv \
    rtl/mlp/hap_a8w4_scalecode_recover2_lut.sv \
    rtl/mlp/hap_a8w4_group32_lane2_s36.sv \
    rtl/mlp/hap_a8w4_slice8x16_group_s36.sv \
    rtl/mlp/hap_mlp_down_group_major_accum_s45.sv \
    rtl/mlp/hap_mlp_down_group_major_slice8x16_s45.sv \
    tb/hap_mlp_down_group_major_slice8x16_s45_tb.sv
"$VIVADO_ROOT/bin/xelab" hap_mlp_down_group_major_slice8x16_s45_tb \
    -s "$SIM"
"$VIVADO_ROOT/bin/xsim" "$SIM" -runall
