#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
SIM=hap_mlp_tensor_dma_bridge_banked_stall_sim
WORK="$ROOT/xsim_work/$SIM"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/mlp_tensor_dma_bridge_banked_stall_xsim_$STAMP}"
mkdir -p "$REPORT_DIR"
rm -rf "$WORK"
mkdir -p "$WORK/work"
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
    hap_mlp_tensor_dma_bridge_banked_stall_tb > "$REPORT_DIR/summary.txt"
  (cd "$REPORT_DIR" && sha256sum ./* > SHA256SUMS)
}
trap archive EXIT
sha256sum \
  rtl/attention/hap_axi256_dma.sv \
  rtl/integration/hap_mlp_tensor_dma_bridge.sv \
  tb/hap_mlp_tensor_dma_bridge_banked_stall_tb.sv \
  vivado/scripts/run_mlp_tensor_dma_bridge_banked_stall_xsim.sh \
  > "$REPORT_DIR/INPUT_SHA256SUMS"
"$BIN/xvlog" -sv --work "work=$WORK/work" \
  rtl/attention/hap_axi256_dma.sv \
  rtl/integration/hap_mlp_tensor_dma_bridge.sv \
  tb/hap_mlp_tensor_dma_bridge_banked_stall_tb.sv
"$BIN/xelab" -L "work=$WORK/work" \
  work.hap_mlp_tensor_dma_bridge_banked_stall_tb -s "$SIM"
printf 'run -all\nexit\n' > "$WORK/xsim_script.tcl"
"$BIN/xsim" "$SIM" --runall --onerror quit \
  --log "$WORK/xsim.log" | tee "$WORK/console.log"
! grep -q '^FAIL' "$WORK/console.log"
grep -Fq 'PASS hap_mlp_tensor_dma_bridge_banked_stall' "$WORK/console.log"
status=0
printf '%s\n' "$REPORT_DIR"
