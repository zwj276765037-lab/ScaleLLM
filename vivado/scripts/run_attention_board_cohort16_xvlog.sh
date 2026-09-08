#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
WORK="$ROOT/xsim_work/hap_attention_board_cohort16_xvlog"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/attention_board_cohort16_xvlog_$STAMP}"
MANIFEST="$ROOT/vivado/manifests/attention_board_cohort16_sources.list"

rm -rf "$WORK"
mkdir -p "$WORK/work" "$REPORT_DIR"
mapfile -t sources < <(grep -vE '^[[:space:]]*(#|$)' "$MANIFEST")
inputs=("$MANIFEST" "$ROOT/vivado/scripts/run_attention_board_cohort16_xvlog.sh")
args=()
for source in "${sources[@]}"; do
    inputs+=("$ROOT/$source")
    args+=("$ROOT/$source")
done
sha256sum "${inputs[@]}" > "$REPORT_DIR/INPUT_SHA256SUMS"

set +e
"$BIN/xvlog" -sv --work "work=$WORK/work" "${args[@]}" \
    > >(tee "$REPORT_DIR/xvlog_console.log") 2>&1
status=$?
set -e
printf 'exit_status=%s\ntool=Vivado xvlog 2025.2\nsource_count=%s\n' \
    "$status" "${#sources[@]}" > "$REPORT_DIR/summary.txt"
find "$REPORT_DIR" -maxdepth 1 -type f \
    ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum \
    > "$REPORT_DIR/SHA256SUMS"
if [[ "$status" -ne 0 ]] || grep -Eq '^(ERROR|FATAL):' \
        "$REPORT_DIR/xvlog_console.log"; then
    exit 1
fi
printf 'PASS: hap_attention_board_cohort16_xvlog sources=%s\n%s\n' \
    "${#sources[@]}" "$REPORT_DIR"
