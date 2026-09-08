#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"

: "${HAP_POST_PLACE_DCP:?HAP_POST_PLACE_DCP must name an audited post_place.dcp}"
export HAP_POST_PLACE_DCP="$(realpath -e -- "$HAP_POST_PLACE_DCP")"
PLACE_DIR="$(dirname -- "$HAP_POST_PLACE_DCP")"
if [[ "$(basename -- "$HAP_POST_PLACE_DCP")" != post_place.dcp ]]; then
    echo "Route input must be named post_place.dcp" >&2
    exit 2
fi
PLACE_SUMMARY="$PLACE_DIR/summary.txt"
PLACE_SHA="$PLACE_DIR/SHA256SUMS"
[[ -f "$PLACE_SUMMARY" && -f "$PLACE_SHA" ]] || {
    echo "Placement summary/SHA manifest is missing from $PLACE_DIR" >&2
    exit 2
}
grep -Fxq 'status=TIMING_PLACE_COMPLETE' "$PLACE_SUMMARY"
grep -Fxq 'part=xcvu9p-flga2104-2L-e' "$PLACE_SUMMARY"
grep -Fxq 'unplaced_primitives=0' "$PLACE_SUMMARY"
grep -Fxq 'dsp48e2=6492' "$PLACE_SUMMARY"
grep -Fxq 'uram288=752' "$PLACE_SUMMARY"
grep -Fxq 'mlp_kernel_dsp48e2=4096' "$PLACE_SUMMARY"
grep -Fxq 'exact_resource_contract_ok=1' "$PLACE_SUMMARY"
(cd "$ROOT" && sha256sum -c --strict "$PLACE_SHA")
[[ "$(wc -l < "$PLACE_SHA")" -eq 6 ]] || {
    echo "Placement SHA manifest must contain exactly 6 entries" >&2
    exit 2
}
export HAP_ROUTE_DIR="${HAP_ROUTE_DIR:-$ROOT/vivado/reports/production_ooc_route_$STAMP}"
export HAP_PHYSOPT_DIRECTIVE="${HAP_PHYSOPT_DIRECTIVE:-AggressiveExplore}"
export HAP_ROUTE_DIRECTIVE="${HAP_ROUTE_DIRECTIVE:-AggressiveExplore}"
mkdir -p "$HAP_ROUTE_DIR"
cd "$ROOT"

"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/resume_attention_mlp_production_route.tcl \
    -log "$HAP_ROUTE_DIR/vivado.log" \
    -journal "$HAP_ROUTE_DIR/vivado.jou"

grep -Fxq 'status=OOC_POST_ROUTE_PASS' "$HAP_ROUTE_DIR/summary.txt"
grep -Fxq 'part=xcvu9p-flga2104-2L-e' "$HAP_ROUTE_DIR/summary.txt"
grep -Fxq 'core_clock_mhz=150' "$HAP_ROUTE_DIR/summary.txt"
grep -Fxq 'ddr0_clock_mhz=300' "$HAP_ROUTE_DIR/summary.txt"
grep -Fxq 'ddr1_clock_mhz=300' "$HAP_ROUTE_DIR/summary.txt"
grep -Fxq 'core_io_budget_ns=1.000' "$HAP_ROUTE_DIR/summary.txt"
grep -Fxq 'ddr_io_budget_ns=0.800' "$HAP_ROUTE_DIR/summary.txt"
grep -Fxq 'route_clean=1' "$HAP_ROUTE_DIR/summary.txt"
grep -Fxq 'explicit_gap_nets=0' "$HAP_ROUTE_DIR/summary.txt"
grep -Fxq 'unconstrained_paths=0' "$HAP_ROUTE_DIR/summary.txt"
grep -Fxq 'timing_coverage_ok=1' "$HAP_ROUTE_DIR/summary.txt"
grep -Fxq 'drc_errors=0' "$HAP_ROUTE_DIR/summary.txt"
grep -Fxq 'cdc_critical=0' "$HAP_ROUTE_DIR/summary.txt"
grep -Fxq 'dsp48e2=6492' "$HAP_ROUTE_DIR/summary.txt"
grep -Fxq 'mlp_kernel_dsp48e2=4096' "$HAP_ROUTE_DIR/summary.txt"
grep -Fxq 'uram288=752' "$HAP_ROUTE_DIR/summary.txt"
grep -Fxq 'projection_contract_ok=1' "$HAP_ROUTE_DIR/summary.txt"
grep -Fxq 'physical_contract_ok=1' "$HAP_ROUTE_DIR/summary.txt"
(cd "$ROOT" && sha256sum -c --strict "$PLACE_SHA")
sha256sum "$HAP_POST_PLACE_DCP" "$HAP_ROUTE_DIR/post_phys_opt.dcp" \
    "$HAP_ROUTE_DIR/post_route.dcp" \
    "$PLACE_SUMMARY" "$PLACE_SHA" \
    "$ROOT/vivado/constraints/attention_mlp_production_ooc_clocks.xdc" \
    "$ROOT/vivado/scripts/resume_attention_mlp_production_route.tcl" \
    "$ROOT/vivado/scripts/run_attention_mlp_production_route.sh" \
    > "$HAP_ROUTE_DIR/SHA256SUMS"
printf '%s\n' "$HAP_ROUTE_DIR"
