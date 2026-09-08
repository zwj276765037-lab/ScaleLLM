#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
: "${HAP_REPORT_DIR:?Set HAP_REPORT_DIR to the completed synth artifact}"
cd "$ROOT"
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/audit_mlp_gate_up_dual_local_accum16x12_s43_dcp.tcl \
    -log "$HAP_REPORT_DIR/audit_vivado.log" \
    -journal "$HAP_REPORT_DIR/audit_vivado.jou"
