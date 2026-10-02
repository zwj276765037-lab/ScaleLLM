#!/usr/bin/env bash
set -euo pipefail

[[ $# -ge 1 && $# -le 3 && ( "$1" == sc || "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s sc|fp16|fp32 [0|1 backpressure] [synthetic|trace]\n' "$0" >&2
    exit 2
}
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/09_mlp_gate_up_a8w4"
RESULT="$ROOT/ModularExperiment/result/09_mlp_gate_up_a8w4"
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
    run_tiles=6
    python3 "$MODULE/model/verify_trace_vectors.py"
else
    data_dir="$MODULE/data"
    run_tiles=12
    python3 "$MODULE/model/generate_vectors.py"
fi
stamp="$(date +%Y%m%d_%H%M%S)"
mode=continuous
[[ "$backpressure" == 1 ]] && mode=periodic_backpressure
report="$RESULT/raw/$variant/xsim/${stamp}_gate_up_a8w4_native_fp_accum_${dataset}_${mode}"
build="${TMPDIR:-/tmp}/scalellm_modular_m09_xsim/${stamp}_${variant}_${dataset}_${mode}"
mkdir -p "$report" "$build"
export HAP_SCALE_VARIANT="$variant" HAP_BACKPRESSURE="$backpressure"
export HAP_REPORT_DIR="$report" HAP_BUILD_DIR="$build"
export HAP_DATA_DIR="$data_dir" HAP_RUN_TILES="$run_tiles"
printf 'RUNNING\n' > "$report/STATUS"

list="$MODULE/vivado/fp.sources"
[[ "$variant" == sc ]] && list="$MODULE/vivado/sc.sources"
sources=("$MODULE/README.md" "$MODULE/tb/m09_gate_up_tile_tb.sv"
    "$MODULE/vivado/run_matched_xsim.tcl" "$list")
if [[ "$dataset" == trace ]]; then
    capture_dir="$ROOT/ModularExperiment/experiment/08_mlp_input_hadamard_a8/data_trace_mlp_input"
    sources+=("$MODULE/model/generate_trace_vectors.py"
        "$MODULE/model/verify_trace_vectors.py"
        "$MODULE/model/generate_vectors.py"
        "$ROOT/ModularExperiment/experiment/08_mlp_input_hadamard_a8/model/capture_trace_mlp_inputs.py"
        "$ROOT/ModularExperiment/experiment/08_mlp_input_hadamard_a8/model/verify_trace_mlp_inputs.py"
        "$ROOT/model/export_scalellm_llama31_artifacts.py"
        "$ROOT/model/fixbit_v2.py"
        "$data_dir/manifest.json"
        "$capture_dir/manifest.json" "$capture_dir/MANIFEST_SHA256")
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
grep -E 'M09_METRIC_JSON:|PASS: M09|FAIL: M09|M09_MISMATCH' \
    "$report/console.log" > "$report/summary.txt" || true
if [[ "$rc" -eq 0 ]] && \
        grep -Fq 'PASS: M09 Gate/Up A8W4 native-scale matched tile' \
        "$report/console.log" && ! grep -Fq 'FAIL: M09' "$report/console.log"; then
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
