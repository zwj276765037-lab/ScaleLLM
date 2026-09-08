#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO_ROOT="${VIVADO_ROOT:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado}"
SIM=hap_axi512_w4_weight_reader_sim
cd "$ROOT"
rm -rf "xsim_work/$SIM" "xsim.dir/$SIM"
mkdir -p "xsim_work/$SIM"
"$VIVADO_ROOT/bin/xvlog" -sv \
    rtl/mlp/hap_axi512_w4_weight_reader.sv \
    tb/hap_axi512_w4_weight_reader_tb.sv
"$VIVADO_ROOT/bin/xelab" hap_axi512_w4_weight_reader_tb -s "$SIM"
"$VIVADO_ROOT/bin/xsim" "$SIM" -runall
