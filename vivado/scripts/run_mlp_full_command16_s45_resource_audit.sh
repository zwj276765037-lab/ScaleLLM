#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
if [[ $# -ne 1 ]]; then
    printf 'usage: %s REPORT_DIRECTORY\n' "$0" >&2
    exit 2
fi
REPORT_DIR="$(readlink -f "$1")"
export HAP_CHECKPOINT="$REPORT_DIR/post_synth.dcp"
export HAP_OUTPUT="$REPORT_DIR/resource_audit.txt"
cd "$ROOT"
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/audit_mlp_full_command16_s45_synth.tcl \
    -log "$REPORT_DIR/resource_audit.log" \
    -journal "$REPORT_DIR/resource_audit.jou"
cat "$HAP_OUTPUT"
