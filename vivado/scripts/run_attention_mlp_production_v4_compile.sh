#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_PRODUCTION_MANIFEST="$ROOT/vivado/manifests/attention_mlp_production_v4_sources.list"
export HAP_COMPILE_DIR="${HAP_COMPILE_DIR:-$ROOT/vivado/build/v4_production_compile_$STAMP}"
mkdir -p "$HAP_COMPILE_DIR"
sha256sum \
  "$HAP_PRODUCTION_MANIFEST" \
  "$ROOT/rtl/integration/hap_attention_mlp_production_core.sv" \
  "$ROOT/rtl/integration/hap_attention_mlp_resource_top.sv" \
  "$ROOT/rtl/integration/hap_axi512_paired_2client_read_wrr.sv" \
  "$ROOT/rtl/integration/hap_v4_ddr_mode_controller.sv" \
  "$ROOT/rtl/integration/hap_mlp_axil_control.sv" \
  "$ROOT/rtl/attention/hap_softmax_exp_u17.sv" \
  "$ROOT/data/softmax_exp_u17.mem" \
  "$ROOT/data/mlp_silu_q16.mem" > "$HAP_COMPILE_DIR/INPUT_SHA256SUMS"
exec "$ROOT/vivado/scripts/run_attention_mlp_production_compile.sh"
