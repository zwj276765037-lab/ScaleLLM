#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 1 && ( "$1" == sc || "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s sc|fp16|fp32\n' "$0" >&2
    exit 2
}
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/11_mlp_product_hadamard_a8"
RESULT="$ROOT/ModularExperiment/result/11_mlp_product_hadamard_a8"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
variant="$1"

python3 "$MODULE/model/generate_vectors.py"
stamp="$(date +%Y%m%d_%H%M%S)"
report="$RESULT/raw/$variant/xsim/${stamp}_mlp_product_frontend_serial_ooc_wrapper"
build="${TMPDIR:-/tmp}/scalellm_modular_m11_wrapper_xsim/${stamp}_${variant}"
mkdir -p "$report" "$build"
export HAP_SCALE_VARIANT="$variant" HAP_REPORT_DIR="$report"
export HAP_BUILD_DIR="$build"
printf 'RUNNING\n' > "$report/STATUS"

sources=("$MODULE/model/generate_vectors.py"
    "$MODULE/tb/m11_ooc_wrapper_tb.sv"
    "$MODULE/vivado/run_ooc_wrapper_xsim.tcl" "$MODULE/data/manifest.json")
list="$MODULE/vivado/fp_ooc.sources"
[[ "$variant" == sc ]] && list="$MODULE/vivado/sc_ooc.sources"
sources+=("$list")
while IFS= read -r source; do
    [[ -n "$source" ]] && sources+=("$source")
done < "$list"
[[ "$variant" == sc ]] || sources+=("$MODULE/vivado/create_fp_ip.tcl")
while IFS= read -r -d '' data_file; do
    sources+=("$data_file")
done < <(find "$MODULE/data" -maxdepth 1 -type f -name '*.mem' -print0 | sort -z)
sha256sum "${sources[@]}" > "$report/INPUT_SHA256SUMS"

set +e
"$VIVADO" -mode batch -notrace \
    -source "$MODULE/vivado/run_ooc_wrapper_xsim.tcl" \
    -journal "$report/vivado.jou" -log "$report/vivado.log" \
    > "$report/console.log" 2>&1
rc=$?
set -e
grep -E 'M11_WRAPPER_METRIC_JSON:|PASS: M11|FAIL: M11' \
    "$report/console.log" > "$report/summary.txt" || true
if [[ "$rc" -eq 0 ]] && \
        grep -Fq 'PASS: M11 serial OOC wrapper' "$report/console.log" && \
        ! grep -Fq 'FAIL: M11' "$report/console.log"; then
    printf 'PASS\n' > "$report/STATUS"
else
    printf 'FAIL\n' > "$report/STATUS"
    rc=1
fi
printf '%s\n' "$rc" > "$report/exit_status.txt"
find "$report" -maxdepth 1 -type f ! -name SHA256SUMS -print0 \
    | sort -z | xargs -0 sha256sum > "$report/SHA256SUMS"
printf '%s\n' "$report"
exit "$rc"
