#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
SIM=hap_mlp_metadata_bank_local_capture_sim
WORK="$ROOT/xsim_work/$SIM"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/mlp_metadata_bank_local_capture_xsim_$STAMP}"
rm -rf "$WORK" "$ROOT/xsim.dir/$SIM"
mkdir -p "$WORK/work" "$REPORT_DIR"
cd "$ROOT"
status=1
archive() {
  set +e
  for f in xvlog.log xvlog.pb xelab.log xelab.pb xsim.jou; do
    [[ -f "$ROOT/$f" ]] && cp -p "$ROOT/$f" "$REPORT_DIR/$f"
  done
  [[ -f "$WORK/xsim.log" ]] && cp -p "$WORK/xsim.log" "$REPORT_DIR/xsim.log"
  [[ -f "$WORK/console.log" ]] && cp -p "$WORK/console.log" "$REPORT_DIR/console.log"
  printf 'exit_status=%s\ntool=%s\ntop=%s\n' "$status" \
    "$("$BIN/xsim" -version 2>/dev/null | head -1)" \
    hap_mlp_metadata_bank_local_capture_tb > "$REPORT_DIR/summary.txt"
  (cd "$REPORT_DIR" && sha256sum ./* > SHA256SUMS)
}
trap archive EXIT
sha256sum rtl/mlp/hap_mlp_weight_meta_resident_ab.sv \
  rtl/integration/hap_mlp_metadata_scheduler.sv \
  tb/hap_mlp_metadata_bank_local_capture_tb.sv \
  vivado/scripts/run_mlp_metadata_bank_local_capture_xsim.sh \
  > "$REPORT_DIR/INPUT_SHA256SUMS"
"$BIN/xvlog" -sv --work "work=$WORK/work" \
  rtl/mlp/hap_mlp_weight_meta_resident_ab.sv \
  rtl/integration/hap_mlp_metadata_scheduler.sv \
  tb/hap_mlp_metadata_bank_local_capture_tb.sv
"$BIN/xelab" -L "work=$WORK/work" \
  work.hap_mlp_metadata_bank_local_capture_tb -s "$SIM"
"$BIN/xsim" "$SIM" -runall --log "$WORK/xsim.log" 2>&1 | tee "$WORK/console.log"
! grep -q '^FAIL' "$WORK/console.log"
grep -Eq '^PASS hap_mlp_metadata_bank_local_capture checks=[0-9]+ gate_ii_pairs=15 down_ii_pairs=7' \
  "$WORK/console.log"
status=0
printf '%s\n' "$REPORT_DIR"

