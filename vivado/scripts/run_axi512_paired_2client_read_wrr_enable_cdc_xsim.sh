#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.."&&pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
SIM=hap_axi512_paired_2client_read_wrr_enable_cdc_sim
WORK="$ROOT/xsim_work/$SIM"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/axi512_paired_wrr_enable_cdc_xsim_$STAMP}"
mkdir -p "$REPORT_DIR";rm -rf "$WORK" "$ROOT/xsim.dir/$SIM";mkdir -p "$WORK/work";cd "$ROOT"
status=1
archive() {
  set +e
  for f in xvlog.log xvlog.pb xelab.log xelab.pb xsim.jou; do
    [[ -f "$ROOT/$f" ]] && cp -p "$ROOT/$f" "$REPORT_DIR/$f"
  done
  [[ -f "$WORK/xsim.log" ]] && cp -p "$WORK/xsim.log" "$REPORT_DIR/xsim.log"
  cp -p rtl/integration/hap_axi512_paired_2client_read_wrr.sv \
    tb/hap_axi512_paired_2client_read_wrr_enable_cdc_tb.sv \
    vivado/scripts/run_axi512_paired_2client_read_wrr_enable_cdc_xsim.sh "$REPORT_DIR/"
  printf 'exit_status=%s\ntool=%s\n' "$status" "$($BIN/xsim -version 2>/dev/null|head -1)" \
    > "$REPORT_DIR/summary.txt"
  (cd "$REPORT_DIR"&&sha256sum ./* > SHA256SUMS)
}
trap archive EXIT
"$BIN/xvlog" --sv -L xpm --work work="$WORK/work" \
  rtl/integration/hap_axi512_paired_2client_read_wrr.sv \
  tb/hap_axi512_paired_2client_read_wrr_enable_cdc_tb.sv
"$BIN/xvlog" --work work="$WORK/work" "$BIN/../data/verilog/src/glbl.v"
"$BIN/xelab" -L xpm -L work="$WORK/work" \
  work.hap_axi512_paired_2client_read_wrr_enable_cdc_tb work.glbl -s "$SIM"
"$BIN/xsim" "$SIM" -runall --log "$WORK/xsim.log"
grep -Eq 'PASS hap_axi512_paired_2client_read_wrr_enable_cdc checks=[0-9]+' "$WORK/xsim.log"
status=0
printf '%s\n' "$REPORT_DIR"
