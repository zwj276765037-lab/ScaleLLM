#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
SIM=hap_attention_board_cohort16_contract_sim
WORK="$ROOT/xsim_work/$SIM"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/attention_board_cohort16_contract_xsim_$STAMP}"
SOURCES=(
    "$ROOT/rtl/attention/hap_attention_cohort16_axil_control.sv"
    "$ROOT/tb/hap_attention_board_cohort16_stubs.sv"
    "$ROOT/rtl/attention/hap_attention_board_cohort16_core.sv"
    "$ROOT/tb/hap_attention_board_cohort16_contract_tb.sv"
)

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
        hap_attention_board_cohort16_contract_tb > "$REPORT_DIR/summary.txt"
    find "$REPORT_DIR" -maxdepth 1 -type f \
        ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum \
        > "$REPORT_DIR/SHA256SUMS"
}
trap archive EXIT

sha256sum "${SOURCES[@]}" \
    "$ROOT/vivado/scripts/run_attention_board_cohort16_contract_xsim.sh" \
    > "$REPORT_DIR/INPUT_SHA256SUMS"
"$BIN/xvlog" -sv --work "work=$WORK/work" "${SOURCES[@]}"
"$BIN/xelab" -mt 8 -L "work=$WORK/work" -L unisims_ver \
    work.hap_attention_board_cohort16_contract_tb -s "$SIM"
"$BIN/xsim" "$SIM" -runall --log "$WORK/xsim.log" \
    2>&1 | tee "$WORK/console.log"
if grep -q '^FAIL' "$WORK/console.log"; then
    exit 1
fi
grep -Fq 'PASS: hap_attention_board_cohort16_contract' "$WORK/console.log"
status=0
printf '%s\n' "$REPORT_DIR"
