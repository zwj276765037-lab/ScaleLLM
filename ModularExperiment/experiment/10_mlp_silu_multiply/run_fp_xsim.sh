#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/10_mlp_silu_multiply"
RESULT="$ROOT/ModularExperiment/result/10_mlp_silu_multiply"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"

python3 "$MODULE/model/generate_vectors.py"
for variant in fp16 fp32; do
    stamp="$(date +%Y%m%d_%H%M%S)"
    report="$RESULT/raw/$variant/xsim/${stamp}_operator_only_single_leaf"
    build="${TMPDIR:-/tmp}/scalellm_modular_m10_silu_xsim/${stamp}_${variant}"
    mkdir -p "$report" "$build"
    export HAP_FP_VARIANT="$variant" HAP_REPORT_DIR="$report" HAP_BUILD_DIR="$build"
    printf 'RUNNING\n' > "$report/STATUS"
    sha256sum "$MODULE/rtl/fp_common/m10_fp_silu_mul.sv" \
        "$MODULE/tb/m10_fp_silu_mul_tb.sv" "$MODULE/model/generate_vectors.py" \
        "$MODULE/vivado/create_fp_ip.tcl" "$MODULE/vivado/run_fp_xsim.tcl" \
        > "$report/INPUT_SHA256SUMS"
    set +e
    "$VIVADO" -mode batch -notrace -source "$MODULE/vivado/run_fp_xsim.tcl" \
        -journal "$report/vivado.jou" -log "$report/vivado.log" \
        > "$report/console.log" 2>&1
    rc=$?
    set -e
    grep -E 'M10_FP_SILU_METRIC_JSON:|PASS: M10|FAIL: M10' \
        "$report/console.log" > "$report/summary.txt" || true
    if [[ "$rc" -eq 0 ]] && grep -Fq 'PASS: M10 FP SiLU multiply' "$report/console.log"; then
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
