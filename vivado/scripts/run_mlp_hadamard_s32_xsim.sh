#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO_ROOT="${VIVADO_ROOT:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado}"
cd "$ROOT"
python3 model/generate_mlp_hadamard_s32_vectors.py
"$VIVADO_ROOT/bin/xvlog" -sv \
    rtl/mlp/hap_mlp_hadamard32_s32_norm_stream.sv \
    tb/hap_mlp_hadamard32_s32_norm_stream_tb.sv
"$VIVADO_ROOT/bin/xelab" hap_mlp_hadamard32_s32_norm_stream_tb \
    -s hap_mlp_hadamard_s32_sim
"$VIVADO_ROOT/bin/xsim" hap_mlp_hadamard_s32_sim -runall
