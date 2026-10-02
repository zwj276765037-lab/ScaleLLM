#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/07_attention_pv"
RESULT="$ROOT/ModularExperiment/result/07_attention_pv"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
python3 "$MODULE/model/generate_vectors.py"
for variant in fp16 fp32; do
    stamp="$(date +%Y%m%d_%H%M%S)"
    report="$RESULT/raw/$variant/xsim/${stamp}_operator_only_single_core"
    build="${TMPDIR:-/tmp}/scalellm_modular_pv_xsim/${stamp}_${variant}"
    mkdir -p "$report" "$build"
    export HAP_FP_VARIANT="$variant" HAP_REPORT_DIR="$report" HAP_BUILD_DIR="$build"
    printf 'RUNNING\n' > "$report/STATUS"
    sha256sum "$MODULE/rtl/fp_common/m9_fp_pv.sv" "$MODULE/tb/m9_pv_tb.sv" \
        "$MODULE/model/generate_vectors.py" "$MODULE/vivado/create_fp_ip.tcl" \
        "$MODULE/vivado/run_fp_xsim.tcl" "$MODULE/data/SC_SOURCE_SHA256SUMS" \
        > "$report/INPUT_SHA256SUMS"
    set +e
    "$VIVADO" -mode batch -notrace -source "$MODULE/vivado/run_fp_xsim.tcl" \
        -journal "$report/vivado.jou" -log "$report/vivado.log" \
        > "$report/console.log" 2>&1
    rc=$?
    set -e
    grep -E 'M9_PV_METRIC_JSON:|PASS: M9|FAIL: M9' "$report/console.log" \
        > "$report/summary.txt" || true
    if [[ "$rc" -eq 0 ]] && grep -Fq 'PASS: M9 matched PV' "$report/console.log"; then
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
