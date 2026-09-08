#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
SIM=hap_v4_production_control_contract_sim
WORK="$ROOT/xsim_work/$SIM";STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/v4_production_control_xsim_$STAMP}"
mkdir -p "$REPORT_DIR";rm -rf "$WORK" "$ROOT/xsim.dir/$SIM"
mkdir -p "$WORK/work";cd "$ROOT";status=1
archive() {
  set +e
  cp -p rtl/integration/hap_v4_ddr_mode_controller.sv \
    tb/hap_v4_production_control_contract_tb.sv \
    vivado/scripts/run_v4_production_control_contract_xsim.sh "$REPORT_DIR/"
  [[ -f "$WORK/xsim.log" ]] && cp -p "$WORK/xsim.log" "$REPORT_DIR/"
  printf 'exit_status=%s\ntool=%s\n' "$status" \
    "$("$BIN/xsim" -version 2>/dev/null|head -1)" > "$REPORT_DIR/summary.txt"
  (cd "$REPORT_DIR"&&sha256sum ./* > SHA256SUMS)
}
trap archive EXIT
"$BIN/xvlog" --sv --work work="$WORK/work" \
  rtl/integration/hap_v4_ddr_mode_controller.sv \
  tb/hap_v4_production_control_contract_tb.sv
"$BIN/xelab" -L work="$WORK/work" \
  work.hap_v4_production_control_contract_tb -s "$SIM"
"$BIN/xsim" "$SIM" -runall --log "$WORK/xsim.log"
grep -Eq 'PASS hap_v4_production_control_contract checks=[0-9]+' "$WORK/xsim.log"
status=0
printf '%s\n' "$REPORT_DIR"
