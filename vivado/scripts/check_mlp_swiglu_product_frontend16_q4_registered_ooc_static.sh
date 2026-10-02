#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HARNESS="$ROOT/rtl/mlp/hap_mlp_swiglu_product_frontend16_q4_registered_ooc_harness.sv"
SILU="$ROOT/rtl/mlp/hap_mlp_silu_mul.sv"
XDC="$ROOT/vivado/constraints/mlp_swiglu_product_frontend16_q4_registered_ooc_100mhz.xdc"
TCL="$ROOT/vivado/scripts/route_mlp_swiglu_product_frontend16_q4_registered_ooc.tcl"
RUN="$ROOT/vivado/scripts/run_mlp_swiglu_product_frontend16_q4_registered_ooc.sh"

fail() {
    printf 'SwiGLU registered OOC static contract failed: %s\n' "$*" >&2
    exit 1
}
require_literal() {
    local file="$1" literal="$2"
    grep -Fq -- "$literal" "$file" || fail "missing $(basename "$file"): $literal"
}

for file in "$HARNESS" "$SILU" "$XDC" "$TCL" "$RUN"; do
    [[ -s "$file" ]] || fail "missing ${file#"$ROOT/"}"
done
bash -n "$RUN"
[[ "$(grep -Ec '^[[:space:]]*(input|output|inout)[[:space:]]' "$HARNESS")" -eq 1 ]] ||
    fail 'harness must expose exactly one top-level port declaration'
require_literal "$HARNESS" 'input wire clk'
require_literal "$HARNESS" 'localparam integer SRC_W = 6150;'
require_literal "$HARNESS" 'localparam integer SINK_W = 4611;'
require_literal "$HARNESS" 'hap_mlp_swiglu_product_frontend16_q4 u_dut ('
require_literal "$SILU" 'module hap_mlp_silu_mul #('
require_literal "$XDC" 'create_clock -name core_clk -period 10.000 [get_ports clk]'
require_literal "$TCL" 'set top hap_mlp_swiglu_product_frontend16_q4_registered_ooc_harness'
require_literal "$TCL" 'cd $root'
require_literal "$TCL" 'read_verilog -sv [file join $root rtl mlp hap_mlp_silu_mul.sv]'
require_literal "$TCL" 'SwiGLU registered OOC requires HAP_JOBS=32'
require_literal "$TCL" 'require_count source_proxy_ff $src 6150'
require_literal "$TCL" 'require_count sink_proxy_ff $sink 4611'
require_literal "$TCL" '$dut_dsp == 68 && $hadamard_dsp == 64 && $silu_dsp == 4 &&'
require_literal "$TCL" '$quantizer_dsp == 0 &&'
require_literal "$TCL" 'swiglu_row_clear_ff_per_leaf $local 1'
require_literal "$TCL" 'swiglu_hadamard_dsp48e2 $hadamard_dsp'
require_literal "$TCL" 'swiglu_silu_dsp48e2 $silu_dsp'
require_literal "$TCL" 'swiglu_local_clear_protected_ff [dict get $post_clear protected]'
require_literal "$TCL" 'swiglu_direct_clear_bypass_state [dict get $post_clear bypass]'
require_literal "$TCL" 'status $status'
require_literal "$RUN" 'pgrep -u "$(id -u)" -af'
require_literal "$RUN" "'[u]nwrapped/lnx64.o/vivado .*[-]mode batch'"
require_literal "$RUN" 'INPUT_SHA256SUMS'
require_literal "$RUN" '"$ROOT/rtl/mlp/hap_mlp_silu_mul.sv"'
require_literal "$RUN" 'HAP_JOBS="${HAP_JOBS:-32}"'
require_literal "$RUN" 'status=REGISTERED_OOC_ROUTE_PASS'
require_literal "$RUN" 'dut_dsp48e2=68'
require_literal "$RUN" 'swiglu_quantizer_dsp48e2=0'
require_literal "$RUN" 'swiglu_hadamard_dsp48e2=64 swiglu_silu_dsp48e2=4'
if rg -n 'set_false_path|-datapath_only|set_max_delay|set_min_delay' \
        "$HARNESS" "$XDC" "$TCL"; then
    fail 'timing exception found in registered OOC sources'
fi

printf 'MLP_SWIGLU_REGISTERED_OOC_STATIC_PASS\n'
