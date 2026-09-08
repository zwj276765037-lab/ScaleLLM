#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
SIM=hap_mlp_weight_meta_resident_ab_sim
WORK="$ROOT/xsim_work/$SIM"
rm -rf "$WORK" "$ROOT/xsim.dir/$SIM"
mkdir -p "$WORK/work"
cd "$ROOT"
"$BIN/xvlog" -sv --work "work=$WORK/work" \
    rtl/mlp/hap_mlp_weight_meta_resident_ab.sv \
    tb/hap_mlp_weight_meta_resident_ab_tb.sv
"$BIN/xelab" -L "work=$WORK/work" \
    work.hap_mlp_weight_meta_resident_ab_tb -s "$SIM"
"$BIN/xsim" "$SIM" -runall --log "$WORK/xsim.log"
grep -Fq 'PASS hap_mlp_weight_meta_resident_ab' "$WORK/xsim.log"
