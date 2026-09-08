#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
SIM=hap_mlp_down_activation_cache16_sim
cd "$ROOT"
rm -rf "xsim_work/$SIM" "xsim.dir/$SIM"
mkdir -p "xsim_work/$SIM"
"$BIN/xvlog" -sv rtl/mlp/hap_mlp_down_activation_cache16.sv \
    tb/hap_mlp_down_activation_cache16_tb.sv
"$BIN/xelab" hap_mlp_down_activation_cache16_tb -s "$SIM"
"$BIN/xsim" "$SIM" -runall --log "xsim_work/$SIM/xsim.log"
grep -Fq 'PASS: hap_mlp_down_activation_cache16' \
    "xsim_work/$SIM/xsim.log"
echo 'PASS: MLP down activation cache xsim gate completed.'
