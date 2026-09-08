#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
SIM=hap_tensor24_output_buffer_sim
WORK="$ROOT/xsim_work/$SIM"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/tensor24_output_buffer_xsim_$STAMP}"

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
        hap_tensor24_output_buffer_tb > "$REPORT_DIR/summary.txt"
    (cd "$REPORT_DIR" && sha256sum ./* > SHA256SUMS)
}
trap archive EXIT

sha256sum \
    rtl/attention/hap_tensor24_buffers.sv \
    tb/hap_tensor24_output_buffer_tb.sv \
    vivado/scripts/run_tensor24_output_buffer_xsim.sh \
    > "$REPORT_DIR/INPUT_SHA256SUMS"

"$BIN/xvlog" -sv --work "work=$WORK/work" \
    rtl/attention/hap_tensor24_buffers.sv \
    tb/hap_tensor24_output_buffer_tb.sv
"$BIN/xelab" -L "work=$WORK/work" -L unisims_ver \
    work.hap_tensor24_output_buffer_tb -s "$SIM"
"$BIN/xsim" "$SIM" -runall --log "$WORK/xsim.log" \
    2>&1 | tee "$WORK/console.log"
! grep -q '^FAIL' "$WORK/console.log"
grep -Fq 'PASS: hap_tensor24_output_buffer' "$WORK/console.log"
status=0
printf '%s\n' "$REPORT_DIR"
