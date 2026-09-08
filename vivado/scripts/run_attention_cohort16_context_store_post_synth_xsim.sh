#!/usr/bin/env bash
set -euo pipefail

[[ "$#" -eq 1 ]] || {
    printf 'usage: %s CONTEXT_STORE_FUNCSIM_NETLIST\n' "$0" >&2
    exit 2
}
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
NETLIST="$(readlink -e -- "$1")" || { printf 'missing netlist: %s\n' "$1" >&2; exit 2; }
GLBL_V="${GLBL_V:-$BIN/../ids_lite/ISE/verilog/src/glbl.v}"
[[ -s "$GLBL_V" ]] || GLBL_V="$BIN/../data/verilog/src/glbl.v"
[[ -s "$GLBL_V" ]] || { printf 'missing Vivado glbl.v\n' >&2; exit 2; }
TB="$ROOT/tb/hap_attention_cohort16_context_store_post_synth_tb.sv"
LAUNCHER="$ROOT/vivado/scripts/run_attention_cohort16_context_store_post_synth_xsim.sh"
SIM=hap_attention_cohort16_context_store_post_synth_sim
WORK="$ROOT/xsim_work/$SIM"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="$(readlink -m -- "${HAP_REPORT_DIR:-$ROOT/vivado/reports/attention_cohort16_context_store_post_synth_xsim_$STAMP}")"

[[ ! -e "$REPORT_DIR" ]] || { printf 'evidence directory exists: %s\n' "$REPORT_DIR" >&2; exit 2; }
rm -rf "$WORK" "$ROOT/xsim.dir/$SIM"
mkdir "$REPORT_DIR" "$WORK" "$WORK/work"
status=1

archive() {
    set +e
    printf 'exit_status=%s\ntop=%s\n' "$status" \
        hap_attention_cohort16_context_store_post_synth_tb \
        > "$REPORT_DIR/summary.txt"
    mapfile -d '' outputs < <(find "$REPORT_DIR" -maxdepth 1 \
        -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
    [[ "${#outputs[@]}" -eq 0 ]] || \
        sha256sum -- "${outputs[@]}" > "$REPORT_DIR/OUTPUT_SHA256SUMS"
}
trap archive EXIT

sha256sum "$NETLIST" "$GLBL_V" "$TB" "$LAUNCHER" \
    > "$REPORT_DIR/INPUT_SHA256SUMS"
cd "$ROOT"
"$BIN/xvlog" --work "work=$WORK/work" "$NETLIST" \
    > "$REPORT_DIR/xvlog.log" 2>&1
"$BIN/xvlog" --work "work=$WORK/work" "$GLBL_V" \
    >> "$REPORT_DIR/xvlog.log" 2>&1
"$BIN/xvlog" -sv --work "work=$WORK/work" "$TB" \
    >> "$REPORT_DIR/xvlog.log" 2>&1
"$BIN/xelab" -mt "${HAP_XELAB_MT:-8}" -L unisims_ver \
    -L "work=$WORK/work" \
    work.hap_attention_cohort16_context_store_post_synth_tb work.glbl \
    -s "$SIM" \
    > "$REPORT_DIR/xelab.log" 2>&1
"$BIN/xsim" "$SIM" -runall --log "$REPORT_DIR/xsim.log" \
    > "$REPORT_DIR/xsim_stdout.log" 2>&1
if grep -q '^FAIL:' "$REPORT_DIR/xsim.log"; then
    exit 1
fi
grep -Fqx 'PASS: context_store_post_opt_funcsim checks=16' \
    "$REPORT_DIR/xsim.log"
status=0
printf '%s\n' "$REPORT_DIR"
