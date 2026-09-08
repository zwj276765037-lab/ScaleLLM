#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO_ROOT="${VIVADO_ROOT:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado}"
SIM=hap_mlp_gate_up_gather_pingpong12_sim
cd "$ROOT"
rm -rf "xsim_work/$SIM" "xsim.dir/$SIM"
mkdir -p "xsim_work/$SIM"
"$VIVADO_ROOT/bin/xvlog" -sv \
    rtl/mlp/hap_mlp_gate_up_gather_pingpong12.sv \
    tb/hap_mlp_gate_up_gather_pingpong12_tb.sv
"$VIVADO_ROOT/bin/xelab" hap_mlp_gate_up_gather_pingpong12_tb -s "$SIM"
LOG="xsim_work/$SIM/xsim.log"
"$VIVADO_ROOT/bin/xsim" "$SIM" -runall | tee "$LOG"
grep -q "PASS: gate/up gather ping-pong bit-exact groups=8" "$LOG"
if grep -Eq "Fatal:|FAIL" "$LOG"; then
    exit 1
fi

FULL_SIM=hap_mlp_gate_up_gather_pingpong12_full_groups_sim
rm -rf "xsim_work/$FULL_SIM" "xsim.dir/$FULL_SIM"
mkdir -p "xsim_work/$FULL_SIM"
"$VIVADO_ROOT/bin/xelab" \
    hap_mlp_gate_up_gather_pingpong12_full_groups_tb -s "$FULL_SIM"
FULL_LOG="xsim_work/$FULL_SIM/xsim.log"
"$VIVADO_ROOT/bin/xsim" "$FULL_SIM" -runall | tee "$FULL_LOG"
grep -q "PASS: gate/up gather ping-pong bit-exact groups=128" "$FULL_LOG"
if grep -Eq "Fatal:|FAIL" "$FULL_LOG"; then
    exit 1
fi
