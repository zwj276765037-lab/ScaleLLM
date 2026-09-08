#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
SIM=hap_v4_ddr_mode_controller_sim
WORK="$ROOT/xsim_work/$SIM"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/v4_ddr_mode_controller_xsim_$STAMP}"
RTL=rtl/integration/hap_v4_ddr_mode_controller.sv
TB=tb/hap_v4_ddr_mode_controller_tb.sv
SCRIPT=vivado/scripts/run_v4_ddr_mode_controller_xsim.sh

mkdir -p "$REPORT_DIR"
rm -rf "$WORK" "$ROOT/xsim.dir/$SIM"
mkdir -p "$WORK/work"
cd "$ROOT"

status=1
archive() {
  set +e
  for f in xvlog.log xvlog.pb xelab.log xelab.pb xsim.jou; do
    [[ -f "$ROOT/$f" ]] && cp -p "$ROOT/$f" "$REPORT_DIR/$f"
  done
  [[ -f "$WORK/xsim.log" ]] && cp -p "$WORK/xsim.log" "$REPORT_DIR/xsim.log"
  cp -p "$RTL" "$TB" "$SCRIPT" "$REPORT_DIR/"
  checks="$(sed -n 's/.*PASS hap_v4_ddr_mode_controller checks=\([0-9][0-9]*\).*/\1/p' \
    "$WORK/xsim.log" 2>/dev/null | tail -1)"
  done_pulses="$(sed -n 's/.*done_pulses=\([0-9][0-9]*\).*/\1/p' \
    "$WORK/xsim.log" 2>/dev/null | tail -1)"
  {
    printf 'exit_status=%s\n' "$status"
    printf 'tool=%s\n' "$($BIN/xsim -version 2>/dev/null | head -1)"
    printf 'checks=%s\n' "${checks:-0}"
    printf 'done_pulses=%s\n' "${done_pulses:-0}"
    [[ "$status" -eq 0 ]] && printf 'status=PASS\n' || printf 'status=FAIL\n'
  } > "$REPORT_DIR/summary.txt"
  (cd "$REPORT_DIR" && sha256sum ./* > SHA256SUMS)
}
trap archive EXIT

"$BIN/xvlog" --sv --work work="$WORK/work" "$RTL" "$TB"
"$BIN/xvlog" --work work="$WORK/work" "$BIN/../data/verilog/src/glbl.v"
"$BIN/xelab" -L work="$WORK/work" \
  work.hap_v4_ddr_mode_controller_tb work.glbl -s "$SIM"
"$BIN/xsim" "$SIM" -runall --log "$WORK/xsim.log"
grep -Eq 'PASS hap_v4_ddr_mode_controller checks=[0-9]+ done_pulses=[0-9]+' \
  "$WORK/xsim.log"
status=0
printf '%s\n' "$REPORT_DIR"
