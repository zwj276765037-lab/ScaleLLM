#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO_ROOT="${VIVADO_ROOT:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado}"
SIM=hap_mlp_w4_repack48_to12_sim
cd "$ROOT"
rm -rf "xsim_work/$SIM" "xsim.dir/$SIM"
mkdir -p "xsim_work/$SIM"
"$VIVADO_ROOT/bin/xvlog" -sv \
    rtl/mlp/hap_mlp_w4_repack48_to12.sv \
    tb/hap_mlp_w4_repack48_to12_tb.sv
"$VIVADO_ROOT/bin/xelab" -L unisims_ver \
    hap_mlp_w4_repack48_to12_tb -s "$SIM"
LOG="xsim_work/$SIM/xsim.log"
"$VIVADO_ROOT/bin/xsim" "$SIM" -runall | tee "$LOG"
grep -q "PASS: hap_mlp_w4_repack48_to12" "$LOG"
if grep -Eq "Fatal:|FAIL" "$LOG"; then
    exit 1
fi

TP_SIM=hap_mlp_w4_repack48_to12_throughput_sim
rm -rf "xsim_work/$TP_SIM" "xsim.dir/$TP_SIM"
mkdir -p "xsim_work/$TP_SIM"
"$VIVADO_ROOT/bin/xvlog" -sv \
    rtl/mlp/hap_mlp_w4_repack48_to12.sv \
    tb/hap_mlp_w4_repack48_to12_throughput_tb.sv
"$VIVADO_ROOT/bin/xelab" -L unisims_ver \
    hap_mlp_w4_repack48_to12_throughput_tb \
    -s "$TP_SIM"
TP_LOG="xsim_work/$TP_SIM/xsim.log"
"$VIVADO_ROOT/bin/xsim" "$TP_SIM" -runall | tee "$TP_LOG"
grep -q "PASS: repack48 compute stream 8 consecutive II=1 passes" \
    "$TP_LOG"
if grep -Eq "Fatal:|FAIL" "$TP_LOG"; then
    exit 1
fi
