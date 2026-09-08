#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
run_probe() {
  local top="$1" manifest="$2" expected="$3" label="$4"
  export HAP_TOP="$top" HAP_MANIFEST="$manifest" HAP_EXPECTED_DSP="$expected"
  export HAP_REPORT_DIR="${ROOT}/vivado/reports/${label}_synth_${STAMP}"
  export HAP_BUILD_DIR="${ROOT}/vivado/build/${label}_synth"
  mkdir -p "$HAP_REPORT_DIR" "$HAP_BUILD_DIR"
  "$VIVADO" -mode batch -notrace \
    -source "$ROOT/vivado/scripts/probe_a8w4_kernel12_synth.tcl" \
    -log "$HAP_REPORT_DIR/vivado.log" \
    -journal "$HAP_REPORT_DIR/vivado.jou"
  printf '%s\n' "$HAP_REPORT_DIR"
}
run_probe hap_a8w4_slice8x12_group_s36 \
  a8w4_slice8x12_group_sources.list 1536 a8w4_slice8x12_group
run_probe hap_a8w4_dual_slice16x12_group_s36 \
  a8w4_dual_slice16x12_group_sources.list 3072 a8w4_dual_slice16x12_group

