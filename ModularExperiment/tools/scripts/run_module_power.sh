#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
EXPERIMENT="$ROOT/ModularExperiment/experiment"
RESULT="$ROOT/ModularExperiment/result"
TOOLS="$ROOT/ModularExperiment/tools/scripts"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"

if [[ $# -ne 2 ]] ||
   [[ "$2" != sc && "$2" != fp16 && "$2" != fp32 ]]; then
    printf 'usage: %s MODULE sc|fp16|fp32\n' "$0" >&2
    exit 2
fi

module="$1"
variant="$2"
module_dir="$EXPERIMENT/$module"
result_dir="$RESULT/$module"
backpressure=0
scope_regex='([/.])dut$'
generator=()
saif_driver="$TOOLS/power_saif_xsim.tcl"
saif_capture_mode=full_dut_internal

case "$module" in
02_attention_a8w8_projection)
    sim_tcl="$module_dir/vivado/run_matched_xsim.tcl"
    sim_top=m4_tile_tb
    success_marker='PASS: M4 matched tile'
    generator=(python3 "$module_dir/legacy_seed/generate_vectors.py")
    export HAP_SCALE_VARIANT="$variant"
    export HAP_DATASET=synthetic
    export HAP_DATA_DIR="$module_dir/legacy_seed/data"
    export HAP_BACKPRESSURE=1
    case "$variant" in
    sc) dcp="$result_dir/raw/sc/ooc/20260908_222657_sc_matched_8x16x128_tile_boundary_inclusive_100mhz/post_route.dcp" ;;
    fp16) dcp="$result_dir/raw/fp16/ooc/20260908_225903_fp16_matched_8x16x128_tile_boundary_inclusive_100mhz/post_route.dcp" ;;
    fp32) dcp="$result_dir/raw/fp32/ooc/20260908_235041_fp32_matched_8x16x128_tile_boundary_inclusive_100mhz/post_route.dcp" ;;
    esac
    ;;
03_attention_rope)
    sim_tcl="$module_dir/vivado/run_fp_xsim.tcl"
    sim_top=m5_rope_tb
    success_marker='PASS: M5 RoPE'
    generator=(python3 "$module_dir/model/generate_vectors.py")
    export HAP_FP_VARIANT="$variant"
    case "$variant" in
    sc) dcp="$result_dir/raw/sc/ooc/20260908_152409_sc_rope_pair_100mhz/post_route.dcp" ;;
    fp16) dcp="$result_dir/raw/fp16/ooc/20260908_151442_fp16_rope_operator_only_100mhz/post_route.dcp" ;;
    fp32) dcp="$result_dir/raw/fp32/ooc/20260908_151958_fp32_rope_operator_only_100mhz/post_route.dcp" ;;
    esac
    ;;
04_attention_kv12_quantizer)
    sim_tcl="$module_dir/vivado/run_boundary_xsim.tcl"
    sim_top=m4_kv_boundary_tb
    success_marker='PASS: M4 KV boundary'
    generator=(python3 "$module_dir/model/generate_vectors.py")
    export HAP_SCALE_VARIANT="$variant"
    export HAP_BACKPRESSURE=0
    export HAP_DATA_DIR="$module_dir/data"
    case "$variant" in
    sc) dcp="$result_dir/raw/sc/ooc/20260909_014911_sc_kv_producer_cache_boundary_100mhz/post_route.dcp" ;;
    fp16) dcp="$result_dir/raw/fp16/ooc/20260909_015524_fp16_kv_producer_cache_boundary_100mhz/post_route.dcp" ;;
    fp32) dcp="$result_dir/raw/fp32/ooc/20260909_020009_fp32_kv_producer_cache_boundary_100mhz/post_route.dcp" ;;
    esac
    ;;
05_attention_qk_score)
    sim_tcl="$module_dir/vivado/run_matched_xsim.tcl"
    sim_top=m5_qk_matched_tb
    success_marker='PASS: M5 matched QK'
    generator=(python3 "$module_dir/model/generate_vectors.py")
    export HAP_SCALE_VARIANT="$variant"
    export HAP_BACKPRESSURE=1
    case "$variant" in
    sc) dcp="$result_dir/raw/sc/ooc/20260909_011120_sc_matched_qk_slot_operator_only_100mhz/post_route.dcp" ;;
    fp16) dcp="$result_dir/raw/fp16/ooc/20260909_011553_fp16_matched_qk_slot_operator_only_100mhz/post_route.dcp" ;;
    fp32) dcp="$result_dir/raw/fp32/ooc/20260909_012256_fp32_matched_qk_slot_operator_only_100mhz/post_route.dcp" ;;
    esac
    ;;
06_attention_softmax)
    generator=(python3 "$module_dir/model/generate_vectors.py")
    if [[ "$variant" == sc ]]; then
        sim_tcl="$module_dir/vivado/run_sc_power_xsim.tcl"
        sim_top=hap_softmax_row_128_long_tb
        success_marker='PASS: long Softmax row128'
        dcp="$result_dir/raw/sc/ooc/20260908_163651_sc_softmax_row128_100mhz/post_route.dcp"
    else
        sim_tcl="$module_dir/vivado/run_fp_replicated_xsim.tcl"
        sim_top=m8_softmax_replicated_tb
        success_marker='PASS: M8 replicated equal-throughput scheduler'
        export HAP_FP_VARIANT="$variant"
        if [[ "$variant" == fp16 ]]; then
            dcp="$result_dir/raw/fp16/ooc/20260908_164048_fp16_softmax_operator_only_x22_100mhz/post_route.dcp"
        else
            dcp="$result_dir/raw/fp32/ooc/20260908_170913_fp32_softmax_operator_only_x26_100mhz/post_route.dcp"
        fi
    fi
    ;;
07_attention_pv)
    generator=(python3 "$module_dir/model/generate_vectors.py")
    if [[ "$variant" == sc ]]; then
        sim_tcl="$module_dir/vivado/run_sc_power_xsim.tcl"
        sim_top=hap_pv_tile16_s43_tb
        success_marker='PASS: PV tile16 S43'
        dcp="$result_dir/raw/sc/ooc/20260908_191945_sc_pv_tile16_100mhz/post_route.dcp"
    else
        sim_tcl="$module_dir/vivado/run_fp_replicated_xsim.tcl"
        sim_top=m9_pv_replicated_tb
        success_marker='PASS: M9 buffered replicated equal-throughput scheduler'
        export HAP_FP_VARIANT="$variant"
        if [[ "$variant" == fp16 ]]; then
            dcp="$result_dir/raw/fp16/ooc/20260908_194949_fp16_pv_operator_only_x19_buffered_100mhz/post_route.dcp"
        else
            dcp="$result_dir/raw/fp32/ooc/20260908_204859_fp32_pv_operator_only_x21_buffered_100mhz/post_route.dcp"
        fi
    fi
    ;;
09_mlp_gate_up_a8w4)
    if [[ "$variant" == fp32 ]]; then
        printf '%s has no routed FP32 checkpoint\n' "$module" >&2
        exit 3
    fi
    sim_tcl="$module_dir/vivado/run_serial_xsim.tcl"
    sim_top=m09_gate_up_serial_ooc_wrapper_tb
    success_marker='PASS: M09 Gate/Up serial physical wrapper'
    generator=(python3 "$module_dir/model/generate_vectors.py")
    export HAP_SCALE_VARIANT="$variant"
    export HAP_BACKPRESSURE=1
    saif_driver="$module_dir/vivado/power_saif_xsim_m09_sampled.tcl"
    saif_capture_mode=sampled_internal_12_of_96_lanes
    if [[ "$variant" == sc ]]; then
        dcp="$result_dir/raw/sc/ooc/20260909_080025_sc_gate_up_a8w4_native_scale_serial_ooc_100mhz/post_route.dcp"
    else
        dcp="$result_dir/raw/fp16/ooc/20260909_102819_fp16_gate_up_a8w4_native_scale_serial_ooc_100mhz/post_route.dcp"
    fi
    ;;
10_mlp_silu_multiply)
    sim_tcl="$module_dir/vivado/run_power_x2_xsim.tcl"
    sim_top=m10_silu_mul_x2_tb
    success_marker='PASS: M10 x2 SiLU multiply'
    generator=(python3 "$module_dir/model/generate_boundary_vectors.py")
    export HAP_SCALE_VARIANT="$variant"
    export HAP_BACKPRESSURE=1
    case "$variant" in
    sc) dcp="$result_dir/raw/sc/ooc/20260908_155505_sc_mlp_silu_mul_x2_100mhz/post_route.dcp" ;;
    fp16) dcp="$result_dir/raw/fp16/ooc/20260908_155846_fp16_silu_operator_only_x2_100mhz/post_route.dcp" ;;
    fp32) dcp="$result_dir/raw/fp32/ooc/20260908_160449_fp32_silu_operator_only_x2_100mhz/post_route.dcp" ;;
    esac
    ;;
*)
    printf 'unsupported or stale module: %s\n' "$module" >&2
    exit 2
    ;;
esac

if [[ ! -f "$dcp" ]]; then
    printf 'missing routed checkpoint: %s\n' "$dcp" >&2
    exit 1
fi

"${generator[@]}"
stamp="$(date +%Y%m%d_%H%M%S)"
report="$result_dir/raw/$variant/power/${stamp}_saif_post_route_100mhz"
build="${TMPDIR:-/tmp}/scalellm_modular_power/${stamp}_${module}_${variant}"
raw_saif="$report/activity_raw.saif"
saif="$report/activity_100mhz.saif"
strip_file="$report/saif_strip_path.txt"
mkdir -p "$report" "$build"
printf 'RUNNING\n' > "$report/STATUS"

export HAP_REPORT_DIR="$report"
export HAP_BUILD_DIR="$build"
export HAP_SAIF_RAW_PATH="$raw_saif"
export HAP_SAIF_SCOPE_REGEX="$scope_regex"
export HAP_SAIF_WARMUP_NS=100

set +e
"$VIVADO" -mode batch -notrace -source "$sim_tcl" \
    -journal "$report/xsim.jou" -log "$report/xsim.log" \
    > "$report/xsim.console.log" 2>&1
sim_rc=$?
set -e
printf '%s\n' "$sim_rc" > "$report/sim_exit_status.txt"
grep -E 'METRIC_JSON:|PASS:|FAIL:|MISMATCH' "$report/xsim.console.log" \
    > "$report/simulation_summary.txt" || true
if [[ "$sim_rc" -ne 0 ]] ||
   ! grep -Fq "$success_marker" "$report/xsim.console.log" ||
   [[ ! -s "$raw_saif" ]]; then
    printf 'FAIL_SIM\n' > "$report/STATUS"
    printf '%s %s\n' "$variant" "$report" >&2
    exit 1
fi

python3 "$TOOLS/normalize_xsim_saif.py" \
    "$raw_saif" "$saif" "$sim_top" "$strip_file"
strip_path="$(<"$strip_file")"
export HAP_POWER_DCP="$dcp"
export HAP_SAIF_PATH="$saif"
export HAP_SAIF_STRIP_PATH="$strip_path"

set +e
"$VIVADO" -mode batch -notrace -source "$TOOLS/report_power_from_saif.tcl" \
    -journal "$report/power.jou" -log "$report/power.log" \
    > "$report/power.console.log" 2>&1
power_rc=$?
set -e
printf '%s\n' "$power_rc" > "$report/power_exit_status.txt"
if [[ "$power_rc" -ne 0 ]] || [[ ! -s "$report/power_post_route.rpt" ]]; then
    printf 'FAIL_POWER\n' > "$report/STATUS"
    printf '%s %s\n' "$variant" "$report" >&2
    exit 1
fi

matched_pct="$(grep -F 'Design Nets Matched' "$report/power_post_route.rpt" \
    | grep -oE '[0-9]+%' | head -n 1 | tr -d '%')"
matched_fraction="$(grep -F 'Design Nets Matched' "$report/power_post_route.rpt" \
    | grep -oE '\([0-9]+/[0-9]+\)' | head -n 1 | tr -d '()')"
matched_nets="${matched_fraction%%/*}"
design_nets="${matched_fraction##*/}"
if [[ -n "$matched_fraction" && "$matched_fraction" == */* &&
      -n "$matched_nets" && -n "$design_nets" && "$design_nets" -ne 0 ]]; then
    matched_exact_pct="$(awk -v matched="$matched_nets" -v total="$design_nets" \
        'BEGIN { printf "%.6f", 100.0 * matched / total }')"
else
    matched_nets=""
    design_nets=""
    matched_exact_pct=""
fi
{
    printf 'module=%s\n' "$module"
    printf 'variant=%s\n' "$variant"
    printf 'method=post_route_report_power_with_behavioral_saif\n'
    printf 'clock_mhz=100\n'
    printf 'capture_window=after_100ns_warmup_until_testbench_finish\n'
    printf 'saif_capture_mode=%s\n' "$saif_capture_mode"
    printf 'checkpoint=%s\n' "$dcp"
    printf 'simulation_tcl=%s\n' "$sim_tcl"
    printf 'simulation_top=%s\n' "$sim_top"
    printf 'saif=%s\n' "$saif"
    printf 'saif_strip_path=%s\n' "$strip_path"
    printf 'design_nets_matched_percent=%s\n' "$matched_pct"
    printf 'design_nets_matched_exact_percent=%s\n' "$matched_exact_pct"
    printf 'design_nets_matched=%s\n' "$matched_nets"
    printf 'design_nets_total=%s\n' "$design_nets"
    printf 'vivado=%s\n' "$VIVADO"
} > "$report/run_manifest.txt"

if [[ -z "$matched_nets" || -z "$design_nets" ]] ||
   (( matched_nets * 100 < design_nets * 5 )); then
    printf 'INVALID_SAIF_COVERAGE\n' > "$report/STATUS"
    sha256sum "$dcp" "$sim_tcl" "$saif_driver" \
        "$TOOLS/normalize_xsim_saif.py" "$TOOLS/report_power_from_saif.tcl" \
        > "$report/INPUT_SHA256SUMS"
    find "$report" -maxdepth 1 -type f ! -name SHA256SUMS -print0 \
        | sort -z | xargs -0 sha256sum > "$report/SHA256SUMS"
    printf 'SAIF coverage below 5%%: %s %s%% (%s/%s) %s\n' \
        "$variant" "${matched_exact_pct:-unknown}" \
        "${matched_nets:-unknown}" "${design_nets:-unknown}" "$report" >&2
    exit 1
fi

printf 'PASS\n' > "$report/STATUS"
sha256sum "$dcp" "$sim_tcl" "$saif_driver" \
    "$TOOLS/normalize_xsim_saif.py" "$TOOLS/report_power_from_saif.tcl" \
    > "$report/INPUT_SHA256SUMS"
find "$report" -maxdepth 1 -type f ! -name SHA256SUMS -print0 \
    | sort -z | xargs -0 sha256sum > "$report/SHA256SUMS"
printf '%s %s\n' "$variant" "$report"
