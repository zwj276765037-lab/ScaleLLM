#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
requested="${HAP_REPORT_DIR:-$ROOT/vivado/reports/mlp_swiglu_product_frontend16_q4_registered_ooc_${STAMP}}"
export HAP_REPORT_DIR="$(readlink -m -- "$requested")"
export HAP_JOBS="${HAP_JOBS:-32}"

[[ "$HAP_JOBS" == 32 ]] || { printf 'SwiGLU OOC requires HAP_JOBS=32\n' >&2; exit 2; }
[[ -x "$VIVADO" ]] || { printf 'missing Vivado: %s\n' "$VIVADO" >&2; exit 2; }
[[ ! -e "$HAP_REPORT_DIR" ]] || {
    printf 'SwiGLU OOC report directory exists: %s\n' "$HAP_REPORT_DIR" >&2
    exit 2
}
mapfile -t active_batch < <(pgrep -u "$(id -u)" -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another project-user batch Vivado is active; SwiGLU OOC not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi

mkdir "$HAP_REPORT_DIR"
inputs=(
    "$ROOT/rtl/attention/hap_u16_div_u8_seq.sv"
    "$ROOT/rtl/mlp/hap_mlp_silu_mul.sv"
    "$ROOT/rtl/mlp/hap_mlp_hadamard32_s32_norm_stream.sv"
    "$ROOT/rtl/mlp/hap_mlp_robust_a8_quantizer_s35.sv"
    "$ROOT/rtl/mlp/hap_mlp_swiglu_product_frontend16_q4.sv"
    "$ROOT/rtl/mlp/hap_mlp_swiglu_product_frontend16_q4_registered_ooc_harness.sv"
    "$ROOT/data/mlp_silu_q16.mem"
    "$ROOT/vivado/constraints/mlp_swiglu_product_frontend16_q4_registered_ooc_100mhz.xdc"
    "$ROOT/vivado/scripts/route_mlp_swiglu_product_frontend16_q4_registered_ooc.tcl"
    "$ROOT/vivado/scripts/run_mlp_swiglu_product_frontend16_q4_registered_ooc.sh"
)
printf '%s\n' "${inputs[@]}" > "$HAP_REPORT_DIR/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$HAP_REPORT_DIR/INPUT_SHA256SUMS"
(cd / && sha256sum -c --strict "$HAP_REPORT_DIR/INPUT_SHA256SUMS") \
    > "$HAP_REPORT_DIR/input_sha_precheck.txt" 2>&1

set +e
"$VIVADO" -mode batch -notrace \
    -source "$ROOT/vivado/scripts/route_mlp_swiglu_product_frontend16_q4_registered_ooc.tcl" \
    -log "$HAP_REPORT_DIR/vivado.log" \
    -journal "$HAP_REPORT_DIR/vivado.jou"
vivado_rc=$?
(cd / && sha256sum -c --strict "$HAP_REPORT_DIR/INPUT_SHA256SUMS") \
    > "$HAP_REPORT_DIR/input_sha_postcheck.txt" 2>&1
input_rc=$?
set -e

status=FAIL
if (( vivado_rc == 0 && input_rc == 0 )) && \
   [[ -s "$HAP_REPORT_DIR/summary.txt" ]] && \
   grep -Fqx 'status=REGISTERED_OOC_ROUTE_PASS' "$HAP_REPORT_DIR/summary.txt"; then
    status=PASS
fi
printf 'status=%s\nvivado_exit_code=%d\ninput_sha_recheck_exit_code=%d\n' \
    "$status" "$vivado_rc" "$input_rc" > "$HAP_REPORT_DIR/launcher_status.txt"
mapfile -d '' outputs < <(find "$HAP_REPORT_DIR" -maxdepth 1 -type f \
    -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
sha256sum -- "${outputs[@]}" > "$HAP_REPORT_DIR/OUTPUT_SHA256SUMS"
if [[ "$status" != PASS ]]; then
    printf 'SwiGLU registered OOC failed; evidence: %s\n' "$HAP_REPORT_DIR" >&2
    (( vivado_rc != 0 )) && exit "$vivado_rc"
    exit 1
fi
for literal in jobs=32 clock_mhz=100 clock_period_ns=10.000 \
    source_proxy_ff=6150 sink_proxy_ff=4611 dut_dsp48e2=68 \
    swiglu_hadamard_dsp48e2=64 swiglu_silu_dsp48e2=4 \
    swiglu_quantizer_dsp48e2=0 \
    dut_ramb36e2=40 post_synth_dut_ramb36e2=44 \
    post_synth_row_ring_ramb36e2=32 \
    post_synth_non_row_ring_ramb36e2=12 \
    post_route_dut_ramb36e2=40 post_route_row_ring_ramb36e2=28 \
    post_route_non_row_ring_ramb36e2=12 \
    dut_ramb18e2=0 dut_uram288=0 \
    swiglu_local_clear_ff=8 swiglu_local_clear_protected_ff=8 \
    swiglu_control_clear_ff=1 swiglu_hadamard_clear_ff=1 \
    swiglu_quantizer_clear_ff=4 swiglu_row_clear_ff=2 \
    swiglu_direct_clear_bypass_state=0 top_port_count=1 \
    nonclock_top_port_count=0 data_bufg=0 max_delay_exception_rows=0 \
    min_delay_exception_rows=0 false_path_exception_rows=0 \
    unrouted_or_partial_nets=0 conflict_nets=0 drc_errors=0 \
    status=REGISTERED_OOC_ROUTE_PASS; do
    grep -Fqx -- "$literal" "$HAP_REPORT_DIR/summary.txt"
done
awk -F= '/_wns_ns=|^wns_ns=|_whs_ns=|^whs_ns=/{n++; if ($2 < 0) bad=1} \
    END{exit n==8 && !bad ? 0 : 1}' "$HAP_REPORT_DIR/summary.txt"
(cd / && sha256sum -c --strict "$HAP_REPORT_DIR/INPUT_SHA256SUMS")
(cd / && sha256sum -c --strict "$HAP_REPORT_DIR/OUTPUT_SHA256SUMS")
cat "$HAP_REPORT_DIR/summary.txt"
printf '%s\n' "$HAP_REPORT_DIR"
