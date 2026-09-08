#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
XELAB_MT="${HAP_XELAB_MT:-8}"
SIM=hap_attention_compute_cohort16_sim
WORK="$ROOT/xsim_work/$SIM"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/attention_compute_cohort16_xsim_$STAMP}"
MANIFEST="$ROOT/vivado/manifests/attention_compute_cohort16_sources.list"

rm -rf "$WORK" "$ROOT/xsim.dir/$SIM"
mkdir -p "$WORK/work" "$REPORT_DIR"
cd "$ROOT"
status=1

archive() {
    set +e
    for file in xvlog.log xvlog.pb xelab.log xelab.pb xsim.jou; do
        [[ -f "$ROOT/$file" ]] && cp -p "$ROOT/$file" "$REPORT_DIR/$file"
    done
    [[ -f "$WORK/xsim.log" ]] && cp -p "$WORK/xsim.log" "$REPORT_DIR/xsim.log"
    [[ -f "$WORK/console.log" ]] && cp -p "$WORK/console.log" "$REPORT_DIR/console.log"
    printf 'exit_status=%s\ntool=%s\ntop=%s\n' "$status" \
        "$("$BIN/xsim" -version 2>/dev/null | head -1)" \
        hap_attention_compute_cohort16_top_tb > "$REPORT_DIR/summary.txt"
    find "$REPORT_DIR" -maxdepth 1 -type f \
        ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum \
        > "$REPORT_DIR/SHA256SUMS"
}
trap archive EXIT

mapfile -t sources < <(grep -vE '^[[:space:]]*(#|$)' "$MANIFEST")
inputs=("$MANIFEST" "$ROOT/data/softmax_exp_u17.mem"
    "$ROOT/tb/hap_projection_core16x16_w8_reuse_stub.sv"
    "$ROOT/tb/hap_attention_compute_cohort16_top_tb.sv"
    "$ROOT/vivado/scripts/run_attention_compute_cohort16_xsim.sh")
for source in "${sources[@]}"; do
    inputs+=("$ROOT/$source")
done
sha256sum "${inputs[@]}" > "$REPORT_DIR/INPUT_SHA256SUMS"

xvlog_args=()
for source in "${sources[@]}"; do
    xvlog_args+=("$ROOT/$source")
done
"$BIN/xvlog" -sv --work "work=$WORK/work" "${xvlog_args[@]}" \
    "$ROOT/tb/hap_projection_core16x16_w8_reuse_stub.sv" \
    "$ROOT/tb/hap_attention_compute_cohort16_top_tb.sv"
"$BIN/xelab" -mt "$XELAB_MT" -L "work=$WORK/work" -L unisims_ver \
    work.hap_attention_compute_cohort16_top_tb -s "$SIM"
"$BIN/xsim" "$SIM" -runall --log "$WORK/xsim.log" \
    2>&1 | tee "$WORK/console.log"
if grep -q '^FAIL' "$WORK/console.log"; then
    exit 1
fi
grep -Fq 'PASS: hap_attention_compute_cohort16_top' "$WORK/console.log"
status=0
printf '%s\n' "$REPORT_DIR"
