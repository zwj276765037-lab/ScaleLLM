#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
SIM=hap_mlp_axil_control_sim;WORK="$ROOT/xsim_work/$SIM"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/mlp_axil_control_xsim_$STAMP}"
mkdir -p "$REPORT_DIR"
rm -rf "$WORK" "$ROOT/xsim.dir/$SIM";mkdir -p "$WORK/work";cd "$ROOT"
status=1
archive() {
  set +e
  cp -p rtl/integration/hap_mlp_axil_control.sv \
    tb/hap_mlp_axil_control_tb.sv \
    vivado/scripts/run_mlp_axil_control_xsim.sh "$REPORT_DIR/"
  [[ -f "$WORK/xsim.log" ]] && cp -p "$WORK/xsim.log" "$REPORT_DIR/"
  [[ -f "$WORK/console.log" ]] && cp -p "$WORK/console.log" "$REPORT_DIR/"
  printf 'exit_status=%s\ntool=%s\n' "$status" \
    "$("$BIN/xsim" -version 2>/dev/null|head -1)" > "$REPORT_DIR/summary.txt"
  (cd "$REPORT_DIR" && sha256sum ./* > SHA256SUMS)
}
trap archive EXIT
"$BIN/xvlog" -sv --work "work=$WORK/work" rtl/integration/hap_mlp_axil_control.sv tb/hap_mlp_axil_control_tb.sv
# Keep this lightweight control test from contending with the single allowed
# implementation job on the shared server.
"$BIN/xelab" -mt 8 -L "work=$WORK/work" work.hap_mlp_axil_control_tb -s "$SIM"
"$BIN/xsim" "$SIM" -runall --log "$WORK/xsim.log" 2>&1 | tee "$WORK/console.log"
! grep -q '^FAIL' "$WORK/xsim.log"
! grep -q '^FAIL' "$WORK/console.log"
grep -Fq 'PASS hap_mlp_axil_control' "$WORK/xsim.log"
status=0
printf '%s\n' "$REPORT_DIR"
