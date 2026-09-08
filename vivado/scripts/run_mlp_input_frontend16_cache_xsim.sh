#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
PYTHON="${PYTHON:-/home/user/anaconda3/envs/zhouwenjun/bin/python}"
SIM=hap_mlp_input_frontend16_cache_sim
cd "$ROOT"
"$PYTHON" model/generate_mlp_input_frontend16_cache_vectors.py
rm -rf "xsim_work/$SIM" "xsim.dir/$SIM"
mkdir -p "xsim_work/$SIM"
"$BIN/xvlog" -sv \
    rtl/attention/hap_fixbit_v2_pkg.sv \
    rtl/attention/hap_hadamard32_norm_stream.sv \
    rtl/attention/hap_u16_div_u8_seq.sv \
    rtl/attention/hap_robust_a8_quantizer.sv \
    rtl/attention/hap_activation_cache_8row.sv \
    rtl/attention/hap_attention_frontend_8row.sv \
    rtl/mlp/hap_mlp_input_frontend16_cache.sv \
    tb/hap_mlp_input_frontend16_cache_tb.sv
"$BIN/xelab" hap_mlp_input_frontend16_cache_tb -s "$SIM"
"$BIN/xsim" "$SIM" -runall
