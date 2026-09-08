#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO_ROOT="${VIVADO_ROOT:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado}"
PYTHON="${PYTHON:-/home/user/anaconda3/envs/zhouwenjun/bin/python}"
SIM=hap_mlp_product_frontend16_q4_sim
cd "$ROOT"
PYTHONPATH=model "$PYTHON" model/generate_mlp_product_frontend16_q4_vectors.py
rm -rf "xsim_work/$SIM" "xsim.dir/$SIM"
mkdir -p "xsim_work/$SIM"
"$VIVADO_ROOT/bin/xvlog" -sv \
    rtl/attention/hap_u16_div_u8_seq.sv \
    rtl/mlp/hap_mlp_hadamard32_s32_norm_stream.sv \
    rtl/mlp/hap_mlp_robust_a8_quantizer_s35.sv \
    rtl/mlp/hap_mlp_product_frontend16_q4.sv \
    tb/hap_mlp_product_frontend16_q4_tb.sv
"$VIVADO_ROOT/bin/xelab" hap_mlp_product_frontend16_q4_tb -s "$SIM"
"$VIVADO_ROOT/bin/xsim" "$SIM" -runall
