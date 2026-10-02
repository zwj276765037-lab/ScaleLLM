#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/02_attention_a8w8_projection"
RESULT="$ROOT/ModularExperiment/result/02_attention_a8w8_projection"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
stamp="$(date +%Y%m%d_%H%M%S)"
report="$RESULT/raw/fp16/semantic_probe/${stamp}_s21_to_fp16_to_s42"
build="${TMPDIR:-/tmp}/scalellm_modular_m02_fp16_probe/${stamp}"
mkdir -p "$report" "$build"
export HAP_REPORT_DIR="$report" HAP_BUILD_DIR="$build"
printf 'RUNNING\n' > "$report/STATUS"

sources=(
    "$MODULE/README.md"
    "$MODULE/run_fp16_nonfinite_probe.sh"
    "$MODULE/model/verify_fp16_nonfinite_probe.py"
    "$MODULE/vivado/run_fp16_nonfinite_probe.tcl"
    "$MODULE/tb/m02_fp16_nonfinite_probe_tb.sv"
    "$ROOT/ModularExperiment/experiment/00_scale_apply_microkernel/vivado/create_fp_ip.tcl"
    "$ROOT/ModularExperiment/experiment/00_scale_apply_microkernel/legacy_seed/rtl/m3_precenter_mac_group32.sv"
    "$ROOT/ModularExperiment/experiment/00_scale_apply_microkernel/legacy_seed/rtl/m3_s42_fifo.sv"
    "$ROOT/ModularExperiment/experiment/00_scale_apply_microkernel/legacy_seed/rtl/m3_fp_scale_lanes.sv"
)
sha256sum "${sources[@]}" > "$report/INPUT_SHA256SUMS"

set +e
"$VIVADO" -mode batch -notrace \
    -source "$MODULE/vivado/run_fp16_nonfinite_probe.tcl" \
    -journal "$report/vivado.jou" -log "$report/vivado.log" \
    > "$report/console.log" 2>&1
rc=$?
set -e
grep -E 'M02_FP16_SEMANTIC_(RECORD|SUMMARY)_JSON:|PASS: M02|FAIL: M02' \
    "$report/console.log" > "$report/summary.txt" || true
if [[ "$rc" -eq 0 ]] && \
        grep -Fq 'PASS: M02 FP16 nonfinite semantic probe' \
        "$report/console.log" && ! grep -Fq 'FAIL: M02' "$report/console.log"; then
    printf 'PASS\n' > "$report/STATUS"
    if ! python3 "$MODULE/model/verify_fp16_nonfinite_probe.py" \
            --run-dir "$report" --output "$report/semantic_map.json" \
            > "$report/semantic_verify.log" 2>&1; then
        printf 'FAIL\n' > "$report/STATUS"
        rc=1
    fi
else
    printf 'FAIL\n' > "$report/STATUS"
    rc=1
fi
find "$build" -type f -name '*.xci' -print0 | sort -z | xargs -0 -r sha256sum \
    > "$report/FP_XCI_SHA256SUMS"
printf '%s\n' "$rc" > "$report/exit_status.txt"
find "$report" -maxdepth 1 -type f ! -name SHA256SUMS -print0 \
    | sort -z | xargs -0 sha256sum > "$report/SHA256SUMS"
printf '%s\n' "$report"
exit "$rc"
