#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO_ROOT="${VIVADO_ROOT:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado}"
PYTHON="${PYTHON:-/home/user/anaconda3/envs/zhouwenjun/bin/python}"
SIM=hap_mlp_down_group_major_accum_s45_sim
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/mlp_down_group_major_accum_s45_v4_128_xsim_$STAMP}"
cd "$ROOT"
"$PYTHON" model/generate_mlp_down_group_major_accum_s45_vectors.py
rm -rf "xsim_work/$SIM" "xsim.dir/$SIM"
mkdir -p "xsim_work/$SIM" "$REPORT_DIR"
"$VIVADO_ROOT/bin/xvlog" -sv \
    rtl/mlp/hap_mlp_down_group_major_accum_s45.sv \
    tb/hap_mlp_down_group_major_accum_s45_tb.sv \
    2>&1 | tee "$REPORT_DIR/xvlog.log"
"$VIVADO_ROOT/bin/xelab" hap_mlp_down_group_major_accum_s45_tb \
    -s "$SIM" 2>&1 | tee "$REPORT_DIR/xelab.log"
"$VIVADO_ROOT/bin/xsim" "$SIM" -runall \
    2>&1 | tee "$REPORT_DIR/xsim.log"
grep -Eq 'PASS: hap_mlp_down_group_major_accum_s45 .*lanes=128 .*mismatches=0' \
    "$REPORT_DIR/xsim.log"
sha256sum rtl/mlp/hap_mlp_down_group_major_accum_s45.sv \
    tb/hap_mlp_down_group_major_accum_s45_tb.sv \
    model/generate_mlp_down_group_major_accum_s45_vectors.py \
    > "$REPORT_DIR/INPUT_SHA256SUMS"
printf 'exit_status=0\ntool=Vivado Simulator v2025.2\nlanes=128\n' \
    > "$REPORT_DIR/summary.txt"
printf '%s\n' "$REPORT_DIR"
