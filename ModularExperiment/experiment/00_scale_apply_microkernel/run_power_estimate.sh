#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/00_scale_apply_microkernel"
RESULT="$ROOT/ModularExperiment/result/00_scale_apply_microkernel"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"

if [[ $# -gt 1 ]] ||
   [[ $# -eq 1 && "$1" != sc && "$1" != fp16 && "$1" != fp32 ]]; then
    printf 'usage: %s [sc|fp16|fp32]\n' "$0" >&2
    exit 2
fi

variants=(sc fp16 fp32)
if [[ $# -eq 1 ]]; then
    variants=("$1")
fi

declare -A dcp_by_variant=(
    [sc]="$RESULT/raw/sc/ooc/20260908_220106_sc_scale_apply_a8w8_100mhz/post_route.dcp"
    [fp16]="$RESULT/raw/fp16/ooc/20260908_220503_fp16_scale_apply_a8w8_boundary_inclusive_100mhz/post_route.dcp"
    [fp32]="$RESULT/raw/fp32/ooc/20260908_220917_fp32_scale_apply_a8w8_boundary_inclusive_100mhz/post_route.dcp"
)
declare -A strip_by_variant=(
    [sc]=m3_power_sc_tb/t/genblk1.dut
    [fp16]=m3_power_fp16_tb/t/g_fp16.dut
    [fp32]=m3_power_fp32_tb/t/genblk1.dut
)

python3 "$MODULE/legacy_seed/generate_vectors.py"
for variant in "${variants[@]}"; do
    dcp="${dcp_by_variant[$variant]}"
    if [[ ! -f "$dcp" ]]; then
        printf 'missing post-route checkpoint: %s\n' "$dcp" >&2
        exit 1
    fi

    stamp="$(date +%Y%m%d_%H%M%S)"
    report="$RESULT/raw/$variant/power/${stamp}_saif_post_route_100mhz"
    build="${TMPDIR:-/tmp}/scalellm_modular_power/${stamp}_${variant}"
    saif="$report/activity_100mhz.saif"
    mkdir -p "$report" "$build"
    printf 'RUNNING\n' > "$report/STATUS"

    export HAP_SCALE_VARIANT="$variant"
    export HAP_REPORT_DIR="$report"
    export HAP_BUILD_DIR="$build"
    export HAP_CLOCK_PERIOD_PS=10000
    export HAP_SAIF_PATH="$saif"

    sha256sum "$dcp" \
        "$MODULE/legacy_seed/tb/m3_lane_tb.sv" \
        "$MODULE/legacy_seed/generate_vectors.py" \
        "$MODULE/vivado/run_matched_xsim.tcl" \
        "$MODULE/vivado/report_power_from_saif.tcl" \
        > "$report/INPUT_SHA256SUMS"

    set +e
    "$VIVADO" -mode batch -notrace \
        -source "$MODULE/vivado/run_matched_xsim.tcl" \
        -journal "$report/xsim.jou" -log "$report/xsim.log" \
        > "$report/xsim.console.log" 2>&1
    sim_rc=$?
    set -e
    if [[ "$sim_rc" -ne 0 ]] ||
       ! grep -Fq 'PASS: M3 matched group32 lane' "$report/xsim.console.log" ||
       [[ ! -s "$saif" ]]; then
        printf 'FAIL_SIM\n' > "$report/STATUS"
        printf '%s\n' "$sim_rc" > "$report/sim_exit_status.txt"
        printf '%s %s\n' "$variant" "$report" >&2
        exit 1
    fi
    printf '0\n' > "$report/sim_exit_status.txt"
    grep -E 'M3_LANE_METRIC_JSON:|PASS: M3|FAIL: M3|MISMATCH' \
        "$report/xsim.console.log" > "$report/simulation_summary.txt" || true

    export HAP_POWER_DCP="$dcp"
    export HAP_SAIF_STRIP_PATH="${strip_by_variant[$variant]}"
    set +e
    "$VIVADO" -mode batch -notrace \
        -source "$MODULE/vivado/report_power_from_saif.tcl" \
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
    if [[ -z "$matched_pct" ]] || (( matched_pct < 5 )); then
        printf 'INVALID_SAIF_COVERAGE\n' > "$report/STATUS"
        printf 'SAIF coverage below 5%%: variant=%s matched=%s%% report=%s\n' \
            "$variant" "${matched_pct:-unknown}" "$report" >&2
        exit 1
    fi
    printf 'PASS\n' > "$report/STATUS"

    {
        printf 'module=00_scale_apply_microkernel\n'
        printf 'variant=%s\n' "$variant"
        printf 'method=post_route_report_power_with_behavioral_saif\n'
        printf 'clock_mhz=100\n'
        printf 'capture_window=continuous_workload_after_reset\n'
        printf 'checkpoint=%s\n' "$dcp"
        printf 'saif=%s\n' "$saif"
        printf 'saif_strip_path=%s\n' "${strip_by_variant[$variant]}"
        printf 'design_nets_matched_percent=%s\n' "$matched_pct"
        printf 'vivado=%s\n' "$VIVADO"
    } > "$report/run_manifest.txt"
    find "$report" -maxdepth 1 -type f ! -name SHA256SUMS -print0 \
        | sort -z | xargs -0 sha256sum > "$report/SHA256SUMS"
    printf '%s %s\n' "$variant" "$report"
done
