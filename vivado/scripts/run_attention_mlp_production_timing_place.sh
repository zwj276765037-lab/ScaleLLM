#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_DCP="${HAP_DCP:?HAP_DCP must name the audited production post_opt.dcp}"
export HAP_PLACE_DIR="${HAP_PLACE_DIR:-$ROOT/vivado/reports/production_timing_place_$STAMP}"
export HAP_PLACE_DIRECTIVE="${HAP_PLACE_DIRECTIVE:-SSI_SpreadLogic_high}"
mkdir -p "$HAP_PLACE_DIR"
cd "$ROOT"
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/place_attention_mlp_production_timing_floorplan.tcl \
    -log "$HAP_PLACE_DIR/vivado.log" \
    -journal "$HAP_PLACE_DIR/vivado.jou"
grep -Fq 'status=TIMING_PLACE_COMPLETE' "$HAP_PLACE_DIR/summary.txt"
grep -Fq 'part=xcvu9p-flga2104-2L-e' "$HAP_PLACE_DIR/summary.txt"
grep -Fq 'dsp48e2=6492' "$HAP_PLACE_DIR/summary.txt"
grep -Fq 'uram288=752' "$HAP_PLACE_DIR/summary.txt"
grep -Fq 'mlp_kernel_dsp48e2=4096' "$HAP_PLACE_DIR/summary.txt"
grep -Fq 'exact_resource_contract_ok=1' "$HAP_PLACE_DIR/summary.txt"
sha256sum "$HAP_DCP" "$HAP_PLACE_DIR/post_place.dcp" \
    "$ROOT/vivado/constraints/attention_mlp_production_ooc_clocks.xdc" \
    "$ROOT/vivado/scripts/check_attention_mlp_production_io_selectors.tcl" \
    "$ROOT/vivado/scripts/place_attention_mlp_production_timing_floorplan.tcl" \
    "$ROOT/vivado/scripts/run_attention_mlp_production_timing_place.sh" \
    > "$HAP_PLACE_DIR/SHA256SUMS"
printf '%s\n' "$HAP_PLACE_DIR"
