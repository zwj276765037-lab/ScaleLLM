#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO_ROOT="${VIVADO_ROOT:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado}"
PYTHON="${PYTHON:-/home/user/anaconda3/envs/zhouwenjun/bin/python}"
SIM=hap_mlp_tile_accum_s43_sim
cd "$ROOT"
"$PYTHON" model/generate_mlp_tile_accum_s43_vectors.py
rm -rf "xsim_work/$SIM" "xsim.dir/$SIM"
mkdir -p "xsim_work/$SIM"
"$VIVADO_ROOT/bin/xvlog" -sv \
    rtl/mlp/hap_mlp_tile_accum_s36.sv \
    tb/hap_mlp_tile_accum_s43_tb.sv
"$VIVADO_ROOT/bin/xelab" hap_mlp_tile_accum_s43_tb -s "$SIM"
"$VIVADO_ROOT/bin/xsim" "$SIM" -runall
