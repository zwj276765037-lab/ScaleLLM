#!/usr/bin/env bash
set -euo pipefail

[[ $# -ge 1 && $# -le 3 && ( "$1" == sc || "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s sc|fp16|fp32 [0|1 backpressure] [synthetic|trace]\n' "$0" >&2
    exit 2
}
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/01_attention_input_hadamard_a8"
RESULT="$ROOT/ModularExperiment/result/01_attention_input_hadamard_a8"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
variant="$1"
backpressure="${2:-0}"
dataset="${3:-synthetic}"
[[ "$backpressure" == 0 || "$backpressure" == 1 ]] || exit 2
[[ "$dataset" == synthetic || "$dataset" == trace ]] || {
    printf 'dataset must be synthetic or trace\n' >&2
    exit 2
}

if [[ "$dataset" == trace ]]; then
    data_dir="$MODULE/data_trace"
    python3 "$MODULE/model/verify_trace_vectors.py"
else
    data_dir="$MODULE/data"
    python3 "$MODULE/model/generate_vectors.py"
fi
stamp="$(date +%Y%m%d_%H%M%S)"
mode=continuous
[[ "$backpressure" == 1 ]] && mode=periodic_backpressure
report="$RESULT/raw/$variant/xsim/${stamp}_attention_frontend_native_scale_${dataset}_${mode}"
build="${TMPDIR:-/tmp}/scalellm_modular_m1_xsim/${stamp}_${variant}_${dataset}_${mode}"
mkdir -p "$report" "$build"
export HAP_SCALE_VARIANT="$variant" HAP_BACKPRESSURE="$backpressure"
export HAP_REPORT_DIR="$report" HAP_BUILD_DIR="$build" HAP_DATA_DIR="$data_dir"
printf 'RUNNING\n' > "$report/STATUS"

list="$MODULE/vivado/fp.sources"
[[ "$variant" == sc ]] && list="$MODULE/vivado/sc.sources"
sources=("$MODULE/README.md" "$MODULE/tb/m1_attention_frontend_tb.sv"
    "$MODULE/vivado/run_matched_xsim.tcl" "$list")
if [[ "$dataset" == trace ]]; then
    capture_dir="$ROOT/ModularExperiment/experiment/03_attention_rope/data_trace_projection_input"
    sources+=("$MODULE/model/generate_trace_vectors.py"
        "$MODULE/model/verify_trace_vectors.py"
        "$MODULE/model/generate_vectors.py"
        "$ROOT/model/fixbit_v2.py"
        "$data_dir/manifest.json"
        "$capture_dir/manifest.json" "$capture_dir/MANIFEST_SHA256"
        "$ROOT/ModularExperiment/experiment/03_attention_rope/model/capture_trace_projection_inputs.py"
        "$ROOT/ModularExperiment/experiment/03_attention_rope/model/verify_trace_projection_inputs.py")
    while IFS= read -r -d '' capture_file; do
        sources+=("$capture_file")
    done < <(find "$capture_dir" -maxdepth 1 -type f -name '*.npy' -print0 | sort -z)
else
    sources+=("$MODULE/model/generate_vectors.py" "$data_dir/manifest.json")
fi
while IFS= read -r source; do
    [[ -n "$source" && "$source" != \#* ]] && sources+=("$source")
done < "$list"
[[ "$variant" == sc ]] || sources+=("$MODULE/vivado/create_fp_ip.tcl")
while IFS= read -r -d '' data_file; do
    sources+=("$data_file")
done < <(find "$data_dir" -maxdepth 1 -type f ! -name manifest.json -print0 | sort -z)
sha256sum "${sources[@]}" > "$report/INPUT_SHA256SUMS"

set +e
"$VIVADO" -mode batch -notrace -source "$MODULE/vivado/run_matched_xsim.tcl" \
    -journal "$report/vivado.jou" -log "$report/vivado.log" \
    > "$report/console.log" 2>&1
rc=$?
set -e
grep -E 'M1_METRIC_JSON:|PASS: M1|FAIL: M1|M1_MISMATCH' \
    "$report/console.log" > "$report/summary.txt" || true
if [[ "$rc" -eq 0 ]] && \
        grep -Fq 'PASS: M1 Attention frontend native-scale boundary' \
        "$report/console.log" && ! grep -Fq 'FAIL: M1' "$report/console.log"; then
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
