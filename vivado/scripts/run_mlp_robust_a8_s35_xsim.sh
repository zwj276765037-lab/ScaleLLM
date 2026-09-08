#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO_ROOT="${VIVADO_ROOT:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado}"
cd "$ROOT"
python3 model/generate_mlp_robust_a8_s35_vectors.py
"$VIVADO_ROOT/bin/xvlog" -sv \
    rtl/attention/hap_u16_div_u8_seq.sv \
    rtl/mlp/hap_mlp_robust_a8_quantizer_s35.sv \
    tb/hap_mlp_robust_a8_quantizer_s35_tb.sv \
    tb/hap_mlp_robust_a8_quantizer_s35_format_tb.sv
"$VIVADO_ROOT/bin/xelab" hap_mlp_robust_a8_quantizer_s35_tb \
    -s hap_mlp_robust_a8_s35_sim
"$VIVADO_ROOT/bin/xsim" hap_mlp_robust_a8_s35_sim -runall
"$VIVADO_ROOT/bin/xelab" hap_mlp_robust_a8_quantizer_s35_format_tb \
    -s hap_mlp_robust_a8_s35_format_sim
"$VIVADO_ROOT/bin/xsim" hap_mlp_robust_a8_s35_format_sim -runall
