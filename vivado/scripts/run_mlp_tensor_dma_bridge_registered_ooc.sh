#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/mlp_tensor_dma_bridge_registered_ooc_$STAMP}"
mkdir -p "$HAP_REPORT_DIR"
cd "$ROOT"
status=1

archive() {
    set +e
    printf 'launcher_exit_status=%s\n' "$status" > "$HAP_REPORT_DIR/launcher_status.txt"
    sha256sum \
        rtl/attention/hap_axi256_dma.sv \
        rtl/integration/hap_mlp_tensor_dma_bridge.sv \
        rtl/integration/hap_mlp_tensor_dma_bridge_registered_ooc_harness.sv \
        vivado/constraints/mlp_tensor_dma_bridge_registered_ooc_150mhz.xdc \
        vivado/scripts/route_mlp_tensor_dma_bridge_registered_ooc.tcl \
        vivado/scripts/run_mlp_tensor_dma_bridge_registered_ooc.sh \
        > "$HAP_REPORT_DIR/INPUT_SHA256SUMS"
    (cd "$HAP_REPORT_DIR" && sha256sum ./* > SHA256SUMS)
}
trap archive EXIT

"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/route_mlp_tensor_dma_bridge_registered_ooc.tcl \
    -log "$HAP_REPORT_DIR/vivado.log" \
    -journal "$HAP_REPORT_DIR/vivado.jou"
cat "$HAP_REPORT_DIR/summary.txt"
status=0
printf '%s\n' "$HAP_REPORT_DIR"
