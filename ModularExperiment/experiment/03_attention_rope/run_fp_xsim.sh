#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/03_attention_rope"
RESULT="$ROOT/ModularExperiment/result/03_attention_rope"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"

python3 "$MODULE/model/generate_vectors.py"
for variant in fp16 fp32; do
    stamp="$(date +%Y%m%d_%H%M%S)"
    report="$RESULT/raw/$variant/xsim/${stamp}_operator_only"
    build="${TMPDIR:-/tmp}/scalellm_modular_rope_xsim/${stamp}_${variant}"
    mkdir -p "$report" "$build"
    export HAP_FP_VARIANT="$variant" HAP_REPORT_DIR="$report" HAP_BUILD_DIR="$build"
    printf 'RUNNING\n' > "$report/STATUS"
    sha256sum "$MODULE/rtl/fp_common/m5_fp32_rope.sv" \
        "$MODULE/tb/m5_rope_tb.sv" "$MODULE/model/generate_vectors.py" \
        "$MODULE/vivado/create_fp_ip.tcl" "$MODULE/vivado/run_fp_xsim.tcl" \
        > "$report/INPUT_SHA256SUMS"
    set +e
    "$VIVADO" -mode batch -notrace -source "$MODULE/vivado/run_fp_xsim.tcl" \
        -journal "$report/vivado.jou" -log "$report/vivado.log" \
        > "$report/console.log" 2>&1
    rc=$?
    set -e
    grep -E 'M5_ROPE_METRIC_JSON:|PASS: M5|FAIL: M5' "$report/console.log" \
        > "$report/summary.txt" || true
    if [[ "$rc" -eq 0 ]] && grep -Fq "PASS: M5 RoPE case=" "$report/console.log"; then
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
