#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 1 && ( "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s fp16|fp32\n' "$0" >&2
    exit 2
}
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/05_attention_qk_score"
RESULT="$ROOT/ModularExperiment/result/05_attention_qk_score"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
variant="$1"

python3 "$MODULE/model/verify_boundary_vectors.py"
stamp="$(date +%Y%m%d_%H%M%S)"
report="$RESULT/raw/$variant/xsim/${stamp}_qk_boundary_fp_group32_frontend"
build="${TMPDIR:-/tmp}/scalellm_modular_m05_boundary_frontend/${stamp}_${variant}"
mkdir -p "$report" "$build"
export HAP_SCALE_VARIANT="$variant" HAP_REPORT_DIR="$report"
export HAP_BUILD_DIR="$build"
printf 'RUNNING\n' > "$report/STATUS"

list="$MODULE/vivado/boundary_frontend.sources"
sources=("$MODULE/model/generate_boundary_vectors.py"
    "$MODULE/model/verify_boundary_vectors.py"
    "$MODULE/data_boundary/manifest.json"
    "$MODULE/tb/m05_boundary_frontend_tb.sv"
    "$MODULE/vivado/create_boundary_fp_ip.tcl"
    "$MODULE/vivado/run_boundary_frontend_xsim.tcl" "$list")
while IFS= read -r source; do
    [[ -n "$source" ]] && sources+=("$source")
done < "$list"
for data_file in query_group_s24.mem query_cache_fp16.mem \
    query_cache_fp32.mem key_group_s12.mem key_scale_fp16.mem \
    key_scale_fp32.mem key_cache_fp16.mem key_cache_fp32.mem; do
    sources+=("$MODULE/data_boundary/$data_file")
done
sha256sum "${sources[@]}" > "$report/INPUT_SHA256SUMS"

set +e
"$VIVADO" -mode batch -notrace \
    -source "$MODULE/vivado/run_boundary_frontend_xsim.tcl" \
    -journal "$report/vivado.jou" -log "$report/vivado.log" \
    > "$report/console.log" 2>&1
rc=$?
set -e
grep -E 'M05_BOUNDARY_FRONTEND_METRIC_JSON:|PASS: M05|FAIL: M05' \
    "$report/console.log" > "$report/summary.txt" || true
if [[ "$rc" -eq 0 ]] && \
        grep -Fq 'PASS: M05 boundary FP group32 frontend' \
            "$report/console.log" && \
        ! grep -Fq 'FAIL: M05' "$report/console.log"; then
    printf 'PASS\n' > "$report/STATUS"
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
