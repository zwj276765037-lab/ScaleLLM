#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
XVLOG="${XVLOG:-$BIN/xvlog}"
XELAB="${XELAB:-$BIN/xelab}"
XSIM="${XSIM:-$BIN/xsim}"
WORK="$ROOT/xsim_work/ddr_read_owner_guard"

rm -rf "$WORK"
mkdir -p "$WORK"
cd "$WORK"
"$XVLOG" --sv -L xpm \
    "$ROOT/rtl/integration/hap_ddr_read_owner_guard.sv" \
    "$ROOT/tb/hap_ddr_read_owner_guard_tb.sv"
"$XVLOG" "$BIN/../data/verilog/src/glbl.v"
"$XELAB" -L xpm hap_ddr_read_owner_guard_tb glbl \
    -s hap_ddr_read_owner_guard_sim
"$XSIM" hap_ddr_read_owner_guard_sim -runall
