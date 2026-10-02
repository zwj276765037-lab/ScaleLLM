#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 1 && ( "$1" == sc || "$1" == sc_auto || \
                  "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s sc|sc_auto|fp16|fp32\n' "$0" >&2
    exit 2
}
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/13_scalecode_fp_recovery_array"
RESULT="$ROOT/ModularExperiment/result/13_scalecode_fp_recovery_array"
TOOLS="$ROOT/ModularExperiment/tools/scripts"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
XILINX_BIN="$(dirname "$VIVADO")"
variant="$1"

python3 "$MODULE/model/generate_power_vectors.py"
dcp=$(
    { find "$RESULT/raw/$variant/ooc" -mindepth 2 -maxdepth 2 \
        -type f -name post_route.dcp -printf '%T@ %p\n' 2>/dev/null || true; } \
        | sort -n | tail -n 1 | cut -d' ' -f2-
)
if [[ -z "$dcp" || ! -f "$dcp" || "$(<"$(dirname "$dcp")/STATUS")" != PASS ]]; then
    printf 'missing latest PASS routed checkpoint for M13 %s\n' "$variant" >&2
    exit 3
fi

# Fail before creating a RUNNING evidence directory if any other hardware job
# is active. The lock remains held by this shell and all child tools.
source "$MODULE/guard_vivado_slot.sh"

stamp="$(date +%Y%m%d_%H%M%S)"
report="$RESULT/raw/$variant/power/${stamp}_post_route_timesim_saif_100mhz"
build="${TMPDIR:-/tmp}/scalellm_modular_m13_power/${stamp}_${variant}"
netlist="$build/m13_${variant}_timesim.v"
sdf="$build/m13_${variant}_timesim.sdf"
raw_saif="$report/activity_raw.saif"
saif="$report/activity_100mhz.saif"
strip_file="$report/saif_strip_path.txt"
mkdir -p "$report" "$build"
printf 'RUNNING\n' > "$report/STATUS"

export HAP_POWER_DCP="$dcp" HAP_TIMESIM_NETLIST="$netlist"
export HAP_TIMESIM_SDF="$sdf"
set +e
"$VIVADO" -mode batch -notrace \
    -source "$MODULE/vivado/export_post_route_timesim.tcl" \
    -journal "$report/export.jou" -log "$report/export.log" \
    > "$report/export.console.log" 2>&1
export_rc=$?
set -e
printf '%s\n' "$export_rc" > "$report/export_exit_status.txt"
if [[ "$export_rc" -ne 0 || ! -s "$netlist" || ! -s "$sdf" ]]; then
    printf 'FAIL_NETLIST_EXPORT\n' > "$report/STATUS"
    exit 1
fi
sha256sum "$netlist" "$sdf" > "$report/NETLIST_SHA256SUMS"

case "$variant" in
    sc) define=M13_POWER_SC ;;
    sc_auto) define=M13_POWER_SC_AUTO ;;
    fp16) define=M13_POWER_FP16 ;;
    fp32) define=M13_POWER_FP32 ;;
esac
data_define="M13_POWER_DATA_DIR=\"$MODULE/data_power\""
glbl=/home/user/EDA-202/vivado/vivado_2025.2/2025.2/data/verilog/src/glbl.v
export HAP_SAIF_RAW_PATH="$raw_saif"

set +e
(
    cd "$build"
    "$XILINX_BIN/xvlog" --nolog "$netlist" "$glbl"
    "$XILINX_BIN/xvlog" --sv --nolog -d "$define" -d "$data_define" \
        "$MODULE/tb/m13_power_array_tb.sv"
    "$XILINX_BIN/xelab" --nolog --debug typical --mt auto \
        -L unisims_ver -L unimacro_ver -L secureip \
        m13_power_array_tb glbl -s m13_power_snapshot
    "$XILINX_BIN/xsim" m13_power_snapshot --nolog \
        --tclbatch "$MODULE/vivado/capture_netlist_saif.tcl"
) > "$report/xsim.console.log" 2>&1
sim_rc=$?
set -e
printf '%s\n' "$sim_rc" > "$report/sim_exit_status.txt"
grep -E 'M13_POWER_METRIC_JSON:|PASS: M13|FAIL: M13|POWER_SAIF_' \
    "$report/xsim.console.log" > "$report/simulation_summary.txt" || true
if [[ "$sim_rc" -ne 0 ]] || \
   ! grep -Fq 'PASS: M13 post-route power workload' "$report/xsim.console.log" || \
   [[ ! -s "$raw_saif" ]]; then
    printf 'FAIL_NETLIST_SIM\n' > "$report/STATUS"
    exit 1
fi

python3 "$TOOLS/normalize_xsim_saif.py" \
    "$raw_saif" "$saif" m13_power_array_tb "$strip_file"
strip_path="$(<"$strip_file")"
export HAP_REPORT_DIR="$report" HAP_SAIF_PATH="$saif"
export HAP_SAIF_STRIP_PATH="$strip_path"
set +e
"$VIVADO" -mode batch -notrace \
    -source "$TOOLS/report_power_from_saif.tcl" \
    -journal "$report/power.jou" -log "$report/power.log" \
    > "$report/power.console.log" 2>&1
power_rc=$?
set -e
printf '%s\n' "$power_rc" > "$report/power_exit_status.txt"
if [[ "$power_rc" -ne 0 || ! -s "$report/power_post_route.rpt" ]]; then
    printf 'FAIL_POWER\n' > "$report/STATUS"
    exit 1
fi

matched_line=$(grep -F 'Design Nets Matched' "$report/power_post_route.rpt" \
    | head -n 1 || true)
matched_fraction=$(printf '%s\n' "$matched_line" \
    | grep -oE '\([0-9]+/[0-9]+\)' | head -n 1 | tr -d '()' || true)
matched_nets="${matched_fraction%%/*}"
design_nets="${matched_fraction##*/}"
if [[ -z "$matched_fraction" || "$matched_fraction" != */* || \
      -z "$design_nets" || "$design_nets" -eq 0 ]]; then
    matched_exact_pct=""
else
    matched_exact_pct=$(awk -v matched="$matched_nets" -v total="$design_nets" \
        'BEGIN { printf "%.6f", 100.0 * matched / total }')
fi

{
    printf 'module=13_scalecode_fp_recovery_array\n'
    printf 'variant=%s\n' "$variant"
    printf 'method=post_route_timing_netlist_saif\n'
    printf 'clock_mhz=100\n'
    printf 'active_cycles=65536\n'
    printf 'accepted_contributions=12582912\n'
    printf 'steady_contributions_per_cycle=192\n'
    printf 'steady_contributions_per_second=19200000000\n'
    printf 'saif_capture_mode=full_post_route_timing_netlist\n'
    printf 'checkpoint=%s\n' "$dcp"
    printf 'netlist_build_dir=%s\n' "$build"
    printf 'saif=%s\n' "$saif"
    printf 'saif_strip_path=%s\n' "$strip_path"
    printf 'design_nets_matched_exact_percent=%s\n' "$matched_exact_pct"
    printf 'design_nets_matched=%s\n' "$matched_nets"
    printf 'design_nets_total=%s\n' "$design_nets"
    printf 'vivado=%s\n' "$VIVADO"
} > "$report/run_manifest.txt"

sha256sum "$dcp" "$MODULE/model/generate_power_vectors.py" \
    "$MODULE/data_power/manifest.json" "$MODULE/tb/m13_power_array_tb.sv" \
    "$MODULE/vivado/export_post_route_timesim.tcl" \
    "$MODULE/vivado/capture_netlist_saif.tcl" \
    "$TOOLS/normalize_xsim_saif.py" "$TOOLS/report_power_from_saif.tcl" \
    > "$report/INPUT_SHA256SUMS"
if [[ -z "$matched_nets" || -z "$design_nets" ]] || \
   (( matched_nets * 100 < design_nets * 80 )); then
    printf 'INVALID_SAIF_COVERAGE\n' > "$report/STATUS"
    find "$report" -maxdepth 1 -type f ! -name SHA256SUMS -print0 \
        | sort -z | xargs -0 sha256sum > "$report/SHA256SUMS"
    printf 'M13 %s timing-netlist SAIF exact coverage below 80%%: %s%%\n' \
        "$variant" "${matched_exact_pct:-unknown}" >&2
    exit 1
fi

printf 'PASS\n' > "$report/STATUS"
find "$report" -maxdepth 1 -type f ! -name SHA256SUMS -print0 \
    | sort -z | xargs -0 sha256sum > "$report/SHA256SUMS"
printf '%s %s\n' "$variant" "$report"
