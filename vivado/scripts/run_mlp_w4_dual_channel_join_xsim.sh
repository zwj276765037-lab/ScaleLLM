#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO_ROOT="${VIVADO_ROOT:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado}"
SIM=hap_mlp_w4_dual_channel_join_sim
cd "$ROOT"
rm -rf "xsim_work/$SIM" "xsim.dir/$SIM"
mkdir -p "xsim_work/$SIM"
"$VIVADO_ROOT/bin/xvlog" -sv \
    rtl/mlp/hap_w4_halfgroup2_assembler.sv \
    rtl/mlp/hap_mlp_w4_dual_channel_join.sv \
    tb/hap_mlp_w4_dual_channel_join_tb.sv
"$VIVADO_ROOT/bin/xelab" hap_mlp_w4_dual_channel_join_tb -s "$SIM"
"$VIVADO_ROOT/bin/xsim" "$SIM" -runall
