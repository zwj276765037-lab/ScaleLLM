#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO_ROOT="${VIVADO_ROOT:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado}"
SIM=hap_a8w4_pack2_dsp_exhaustive_sim
WORK="$ROOT/xsim_work/$SIM"
rm -rf "$WORK" "$ROOT/xsim.dir/$SIM"
mkdir -p "$WORK"
cd "$ROOT"
"$VIVADO_ROOT/bin/xvlog" -sv rtl/mlp/hap_a8w4_pack2_dsp.sv \
    tb/hap_a8w4_pack2_dsp_exhaustive_tb.sv
"$VIVADO_ROOT/bin/xelab" hap_a8w4_pack2_dsp_exhaustive_tb -s "$SIM"
"$VIVADO_ROOT/bin/xsim" "$SIM" -runall
