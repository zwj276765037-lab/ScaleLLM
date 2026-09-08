#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
SIM=hap_mlp_w4_dual_ddr_frontend_sim
WORK="$ROOT/xsim_work/$SIM"
rm -rf "$WORK" "$ROOT/xsim.dir/$SIM"
mkdir -p "$WORK/work"
cd "$ROOT"
"$BIN/xvlog" -sv --work "work=$WORK/work" \
    rtl/mlp/hap_axi512_w4_weight_reader.sv \
    rtl/mlp/hap_ddr512_w4_halfgroup_async.sv \
    rtl/mlp/hap_mlp_w4_dual_channel_join.sv \
    rtl/mlp/hap_mlp_w4_dual_ddr_frontend.sv \
    tb/hap_mlp_w4_dual_ddr_frontend_tb.sv
GLBL_V="${GLBL_V:-$BIN/../ids_lite/ISE/verilog/src/glbl.v}"
"$BIN/xvlog" --work "work=$WORK/work" "$GLBL_V"
"$BIN/xelab" -L "work=$WORK/work" -L xpm \
    work.hap_mlp_w4_dual_ddr_frontend_tb work.glbl \
    -s "$SIM" --debug typical
"$BIN/xsim" "$SIM" -runall --log "$WORK/xsim.log"
! grep -q '^FAIL' "$WORK/xsim.log"
grep -Fq 'PASS: MLP W4 dual DDR frontend preserved payload/order across three clocks and returned atomic counter snapshots.' "$WORK/xsim.log"
echo 'PASS: MLP W4 dual DDR frontend xsim gate completed.'
