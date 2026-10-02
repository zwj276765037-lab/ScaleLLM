#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/00_scale_apply_microkernel"
RESULT="$ROOT/ModularExperiment/result/00_scale_apply_microkernel"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"

if [[ $# -gt 1 ]] ||
   [[ $# -eq 1 && "$1" != fp16 && "$1" != fp32 ]]; then
    printf 'usage: %s [fp16|fp32]\n' "$0" >&2
    exit 2
fi
variants=(fp16 fp32)
if [[ $# -eq 1 ]]; then
    variants=("$1")
fi

python3 "$MODULE/legacy_seed/generate_vectors.py"
for variant in "${variants[@]}"; do
    stamp="$(date +%Y%m%d_%H%M%S)"
    report="$RESULT/raw/$variant/xsim/${stamp}_boundary_inclusive_a8w8"
    build="${TMPDIR:-/tmp}/scalellm_modular_scale_apply_xsim/${stamp}_${variant}"
    mkdir -p "$report" "$build"
    export HAP_SCALE_VARIANT="$variant" HAP_REPORT_DIR="$report" HAP_BUILD_DIR="$build"
    printf 'RUNNING\n' > "$report/STATUS"
    sha256sum "$MODULE/legacy_seed/rtl/m3_precenter_mac_group32.sv" \
        "$MODULE/legacy_seed/rtl/m3_s42_fifo.sv" \
        "$MODULE/legacy_seed/rtl/m3_fp_scale_lanes.sv" \
        "$MODULE/legacy_seed/tb/m3_lane_tb.sv" \
        "$MODULE/legacy_seed/generate_vectors.py" \
        "$MODULE/vivado/create_fp_ip.tcl" \
        "$MODULE/vivado/run_matched_xsim.tcl" > "$report/INPUT_SHA256SUMS"
    set +e
    "$VIVADO" -mode batch -notrace \
        -source "$MODULE/vivado/run_matched_xsim.tcl" \
        -journal "$report/vivado.jou" -log "$report/vivado.log" \
        > "$report/console.log" 2>&1
    rc=$?
    set -e
    grep -E 'M3_LANE_METRIC_JSON:|PASS: M3|FAIL: M3|MISMATCH' \
        "$report/console.log" > "$report/summary.txt" || true
    if [[ "$rc" -eq 0 ]] && grep -Fq "PASS: M3 matched group32 lane" "$report/console.log"; then
        printf 'PASS\n' > "$report/STATUS"
    else
        printf 'FAIL\n' > "$report/STATUS"
        rc=1
    fi
    printf '%s\n' "$rc" > "$report/exit_status.txt"
    find "$report" -maxdepth 1 -type f ! -name SHA256SUMS -print0 \
        | sort -z | xargs -0 sha256sum > "$report/SHA256SUMS"
    printf '%s %s\n' "$variant" "$report"
    [[ "$rc" -eq 0 ]]
done
