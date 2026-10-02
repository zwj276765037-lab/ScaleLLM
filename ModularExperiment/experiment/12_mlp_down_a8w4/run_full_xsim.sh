#!/usr/bin/env bash
set -euo pipefail

[[ $# -ge 1 && $# -le 3 && ( "$1" == sc || "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s sc|fp16|fp32 [synthetic|trace_l00|trace_l15|trace_l31] [wave|nowave]\n' "$0" >&2
    exit 2
}
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/12_mlp_down_a8w4"
RESULT="$ROOT/ModularExperiment/result/12_mlp_down_a8w4"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
variant="$1"
dataset="${2:-synthetic}"
wave_mode="${3:-wave}"
[[ "$wave_mode" == wave || "$wave_mode" == nowave ]] || exit 2
source "$MODULE/guard_vivado_slot.sh"

case "$dataset" in
    synthetic)
        data_dir="$MODULE/data"
        data_manifest="$data_dir/manifest.json"
        if [[ ! -s "$data_manifest" ]]; then
            python3 "$MODULE/model/generate_vectors.py"
        fi
        python3 "$MODULE/model/verify_vectors.py"
        data_sources=("$MODULE/model/generate_vectors.py"
            "$MODULE/model/verify_vectors.py" "$data_manifest")
        ;;
    trace_l00|trace_l15|trace_l31)
        layer="${dataset#trace_l}"
        data_dir="$MODULE/data_trace/layer$layer"
        data_manifest="$MODULE/data_trace/manifest.json"
        python3 "$MODULE/model/verify_trace_vectors.py" --integrity-only
        data_sources=("$MODULE/model/generate_trace_vectors.py"
            "$MODULE/model/generate_vectors.py"
            "$MODULE/model/verify_trace_vectors.py" "$data_manifest")
        ;;
    *)
        printf 'unsupported M12 dataset: %s\n' "$dataset" >&2
        exit 2
        ;;
esac

stamp="$(date +%Y%m%d_%H%M%S)"
report="$RESULT/raw/$variant/xsim/${stamp}_down_a8w4_${dataset}_full_448x342_group_major_${wave_mode}"
build="${TMPDIR:-/tmp}/scalellm_modular_m12_full_xsim/${stamp}_${variant}_${dataset}_${wave_mode}"
mkdir -p "$report" "$build"
export HAP_SCALE_VARIANT="$variant"
export HAP_REPORT_DIR="$report" HAP_BUILD_DIR="$build"
export HAP_DATA_DIR="$data_dir" HAP_WAVE_MODE="$wave_mode"
printf 'RUNNING\n' > "$report/STATUS"
printf '%s\n' "$dataset" > "$report/dataset.txt"
printf '%s\n' "$wave_mode" > "$report/wave_mode.txt"

list="$MODULE/vivado/fp.sources"
[[ "$variant" == sc ]] && list="$MODULE/vivado/sc.sources"
sources=("${data_sources[@]}" "$MODULE/tb/m12_down_group_major_tb.sv"
    "$MODULE/vivado/run_full_xsim.tcl" "$MODULE/guard_vivado_slot.sh" "$list")
while IFS= read -r source; do
    [[ -n "$source" ]] && sources+=("$source")
done < "$list"
[[ "$variant" == sc ]] || sources+=("$MODULE/vivado/create_fp_ip.tcl")
[[ "$wave_mode" == nowave ]] && \
    sources+=("$MODULE/vivado/run_1000ns_no_wave.tcl")
data_files=(
    activation_s9x16x32.mem
    weights_s4x12x32.mem
    column_mask_u12.mem
)
case "$variant" in
    sc)
        data_files+=(activation_meta_sc_u224.mem weight_meta_sc_u168.mem
            expected_sc_s24x16x12.mem)
        ;;
    fp16)
        data_files+=(activation_scale_fp16x16.mem weight_scale_fp16x12.mem
            expected_fp16_s24x16x12.mem)
        ;;
    fp32)
        data_files+=(activation_scale_fp32x16.mem weight_scale_fp32x12.mem
            expected_fp32_s24x16x12.mem)
        ;;
esac
for data_file in "${data_files[@]}"; do
    sources+=("$data_dir/$data_file")
done
sha256sum "${sources[@]}" > "$report/INPUT_SHA256SUMS"

started_at=$(date --iso-8601=seconds)
started_ns=$(date +%s%N)
set +e
"$VIVADO" -mode batch -notrace -source "$MODULE/vivado/run_full_xsim.tcl" \
    -journal "$report/vivado.jou" -log "$report/vivado.log" \
    > "$report/console.log" 2>&1
rc=$?
set -e
finished_ns=$(date +%s%N)
finished_at=$(date --iso-8601=seconds)
wall_elapsed_ms=$(( (finished_ns-started_ns)/1000000 ))
grep -E 'M12_METRIC_JSON:|PASS: M12|FAIL: M12|MISMATCH: M12' \
    "$report/console.log" > "$report/summary.txt" || true
if [[ "$rc" -eq 0 ]] && grep -Fq 'PASS: M12 full Down group-major' \
        "$report/console.log" && ! grep -Fq 'FAIL: M12' "$report/console.log"; then
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
    printf 'dataset=%s\n' "$dataset"
    printf 'wave_mode=%s\n' "$wave_mode"
    printf 'wdb_total_bytes=%s\n' "$(<"$report/wdb_total_bytes.txt")"
} > "$report/run_manifest.txt"
printf '%s\n' "$rc" > "$report/exit_status.txt"
find "$report" -maxdepth 1 -type f ! -name SHA256SUMS -print0 \
    | sort -z | xargs -0 sha256sum > "$report/SHA256SUMS"
printf '%s\n' "$report"
exit "$rc"
