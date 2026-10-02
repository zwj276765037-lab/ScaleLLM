#!/usr/bin/env bash
set -euo pipefail

[[ $# -ge 1 && $# -le 3 && ( "$1" == sc || "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s sc|fp16|fp32 [0|1 backpressure] [wave|nowave]\n' "$0" >&2
    exit 2
}
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/12_mlp_down_a8w4"
RESULT="$ROOT/ModularExperiment/result/12_mlp_down_a8w4"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
variant="$1"
backpressure="${2:-1}"
[[ "$backpressure" == 0 || "$backpressure" == 1 ]] || exit 2
wave_mode="${3:-wave}"
[[ "$wave_mode" == wave || "$wave_mode" == nowave ]] || exit 2
data_dir="$MODULE/data_mini"
source "$MODULE/guard_vivado_slot.sh"
vector_verify=$(python3 "$MODULE/model/verify_mini_vectors.py")

stamp="$(date +%Y%m%d_%H%M%S)"
mode=continuous
[[ "$backpressure" == 1 ]] && mode=periodic_backpressure
report="$RESULT/raw/$variant/xsim/${stamp}_down_a8w4_serial_ooc_wrapper_nonzero_${mode}_${wave_mode}"
build="${TMPDIR:-/tmp}/scalellm_modular_m12_serial_xsim/${stamp}_${variant}_${mode}_${wave_mode}"
mkdir -p "$report" "$build"
export HAP_SCALE_VARIANT="$variant" HAP_BACKPRESSURE="$backpressure"
export HAP_REPORT_DIR="$report" HAP_BUILD_DIR="$build"
export HAP_DATA_DIR="$data_dir" HAP_WAVE_MODE="$wave_mode"
printf 'RUNNING\n' > "$report/STATUS"
printf '%s\n' "$vector_verify" > "$report/VECTOR_VERIFY.txt"
printf '%s\n' "$wave_mode" > "$report/wave_mode.txt"

list="$MODULE/vivado/fp_ooc.sources"
[[ "$variant" == sc ]] && list="$MODULE/vivado/sc_ooc.sources"
sources=("$MODULE/model/generate_mini_vectors.py"
    "$MODULE/model/generate_vectors.py"
    "$MODULE/model/verify_mini_vectors.py"
    "$MODULE/guard_vivado_slot.sh"
    "$MODULE/tb/m12_down_serial_ooc_wrapper_tb.sv"
    "$MODULE/vivado/run_serial_xsim.tcl" "$list"
    "$data_dir/manifest.json")
[[ "$wave_mode" == nowave ]] && \
    sources+=("$MODULE/vivado/run_1000ns_no_wave.tcl")
while IFS= read -r source; do
    [[ -n "$source" ]] && sources+=("$source")
done < "$list"
[[ "$variant" == sc ]] || sources+=("$MODULE/vivado/create_fp_ip.tcl")
while IFS= read -r -d '' data_file; do
    sources+=("$data_file")
done < <(find "$data_dir" -maxdepth 1 -type f -name '*.mem' -print0 | sort -z)
sha256sum "${sources[@]}" > "$report/INPUT_SHA256SUMS"

started_at=$(date --iso-8601=seconds)
started_ns=$(date +%s%N)
set +e
"$VIVADO" -mode batch -notrace -source "$MODULE/vivado/run_serial_xsim.tcl" \
    -journal "$report/vivado.jou" -log "$report/vivado.log" \
    > "$report/console.log" 2>&1
rc=$?
set -e
finished_ns=$(date +%s%N)
finished_at=$(date --iso-8601=seconds)
wall_elapsed_ms=$(( (finished_ns-started_ns)/1000000 ))
grep -E 'M12_SERIAL_METRIC_JSON:|PASS: M12|FAIL: M12' \
    "$report/console.log" > "$report/summary.txt" || true
grep -F 'M12_SERIAL_METRIC_JSON:' "$report/console.log" \
    > "$report/functional_metrics.txt" || true
grep -F 'M12_SERIAL_WORD_HEX:' "$report/console.log" \
    > "$report/output_words.txt" || true
grep -F 'M12_SERIAL_INPUT_ACCEPT:' "$report/console.log" \
    > "$report/input_accepts.txt" || true
if [[ "$rc" -eq 0 ]] && grep -Fq 'PASS: M12 Down serial physical wrapper' \
        "$report/console.log" && ! grep -Fq 'FAIL: M12' "$report/console.log" &&
        [[ $(wc -l < "$report/output_words.txt") -eq 288 ]] &&
        [[ $(wc -l < "$report/input_accepts.txt") -eq 80 ]] &&
        [[ $(wc -l < "$report/functional_metrics.txt") -eq 1 ]] &&
        grep -Eq '"nonzero_result_words":[1-9][0-9]*' \
            "$report/functional_metrics.txt"; then
    printf 'PASS\n' > "$report/STATUS"
else
    printf 'FAIL\n' > "$report/STATUS"
    rc=1
fi
find "$build" -type f -name '*.xci' -print0 | sort -z | xargs -0 -r sha256sum \
    > "$report/FP_XCI_SHA256SUMS"
find "$build" -type f -name '*.wdb' -printf '%p\t%s\n' | sort \
    > "$report/WDB_FILES.txt"
find "$build" -type f -name '*.wdb' -print0 | sort -z | xargs -0 -r sha256sum \
    > "$report/WDB_SHA256SUMS"
awk -F '\t' '{sum += $2} END {print sum+0}' "$report/WDB_FILES.txt" \
    > "$report/wdb_total_bytes.txt"
{
    printf 'started_at=%s\n' "$started_at"
    printf 'finished_at=%s\n' "$finished_at"
    printf 'wall_elapsed_ms=%s\n' "$wall_elapsed_ms"
    printf 'variant=%s\n' "$variant"
    printf 'backpressure=%s\n' "$backpressure"
    printf 'wave_mode=%s\n' "$wave_mode"
    printf 'wdb_total_bytes=%s\n' "$(<"$report/wdb_total_bytes.txt")"
} > "$report/run_manifest.txt"
printf '%s\n' "$rc" > "$report/exit_status.txt"
find "$report" -maxdepth 1 -type f ! -name SHA256SUMS -print0 \
    | sort -z | xargs -0 sha256sum > "$report/SHA256SUMS"
printf '%s\n' "$report"
exit "$rc"
