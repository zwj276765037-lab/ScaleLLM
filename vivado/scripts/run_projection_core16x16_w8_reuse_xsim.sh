#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
PYTHON="${PYTHON:-python3}"
SIM=hap_projection_core16x16_w8_reuse_sim
WORK="$ROOT/xsim_work/$SIM"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/projection_core16x16_w8_reuse_xsim_$STAMP}"
VECTOR_DIR="$ROOT/data/projection_core16x16_w8_reuse"
MANIFEST="$ROOT/vivado/manifests/attention_projection_core16x16_w8_reuse_sources.list"

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
    printf 'exit_status=%s\ntop=%s\n' "$status" \
        hap_projection_core16x16_w8_reuse_tb > "$REPORT_DIR/summary.txt"
    (cd "$REPORT_DIR" && sha256sum ./* > SHA256SUMS)
}
trap archive EXIT

"$PYTHON" -m unittest tests.test_attention_two_wave_reuse_contract
"$PYTHON" model/generate_projection_core16x16_w8_reuse_vectors.py

mapfile -t sources < <(grep -vE '^[[:space:]]*(#|$)' "$MANIFEST")
sources+=(tb/hap_projection_core16x16_w8_reuse_tb.sv)
sha256sum "${sources[@]}" "$MANIFEST" "$VECTOR_DIR"/*.mem \
    model/attention_two_wave_reuse_contract.py \
    model/generate_projection_core16x16_w8_reuse_vectors.py \
    tests/test_attention_two_wave_reuse_contract.py \
    vivado/scripts/run_projection_core16x16_w8_reuse_xsim.sh \
    > "$REPORT_DIR/INPUT_SHA256SUMS"

"$BIN/xvlog" -sv --work "work=$WORK/work" "${sources[@]}"
"$BIN/xelab" -L "work=$WORK/work" -L unisims_ver \
    work.hap_projection_core16x16_w8_reuse_tb -s "$SIM"
"$BIN/xsim" "$SIM" -runall --log "$WORK/xsim.log" \
    2>&1 | tee "$WORK/console.log"
! grep -q '^FAIL:' "$WORK/console.log"
grep -Fq 'PASS: cohort16 projection accepted 128 W8 groups' \
    "$WORK/console.log"
status=0
printf '%s\n' "$REPORT_DIR"
