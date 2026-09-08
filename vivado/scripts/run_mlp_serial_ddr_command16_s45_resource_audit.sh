#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:?set HAP_REPORT_DIR}"
export HAP_SYNTH_DCP="${HAP_SYNTH_DCP:-$HAP_REPORT_DIR/post_synth.dcp}"
cd "$ROOT"
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/audit_mlp_serial_ddr_command16_s45_synth.tcl \
    -log "$HAP_REPORT_DIR/resource_audit_vivado.log" \
    -journal "$HAP_REPORT_DIR/resource_audit_vivado.jou"
