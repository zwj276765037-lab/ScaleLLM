#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
STAMP="$(date +%Y%m%d_%H%M%S)"
SIM=hap_weight_meta_resident_ready_boundary_sim
WORK="$ROOT/xsim_work/${SIM}_$STAMP"
REPORT="$ROOT/vivado/reports/weight_meta_ready_boundary_xsim_$STAMP"
mkdir -p "$WORK/work" "$REPORT"
cd "$ROOT"

"$BIN/xvlog" -sv --work "work=$WORK/work" \
    rtl/attention/hap_weight_meta_resident.sv \
    tb/hap_weight_meta_resident_ready_boundary_tb.sv \
    2>&1 | tee "$REPORT/xvlog.log"
"$BIN/xelab" -L "work=$WORK/work" \
    work.hap_weight_meta_resident_ready_boundary_tb -s "$SIM" \
    2>&1 | tee "$REPORT/xelab.log"
"$BIN/xsim" "$SIM" -runall --log "$REPORT/xsim.log"
grep -Fq 'PASS hap_weight_meta_resident_ready_boundary' \
    "$REPORT/xsim.log"
if grep -Eq '(^|[[:space:]])(FAIL|FATAL|ERROR)(:|[[:space:]])' \
        "$REPORT/xsim.log"; then
    echo "Attention metadata boundary regression reported a failure marker" >&2
    exit 1
fi

sha256sum rtl/attention/hap_weight_meta_resident.sv \
    tb/hap_weight_meta_resident_ready_boundary_tb.sv \
    "$REPORT/xsim.log" > "$REPORT/SHA256SUMS"
printf '%s\n' "$REPORT"
