#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
: "${HAP_ROUTE_ARTIFACT:?set HAP_ROUTE_ARTIFACT to the completed route artifact}"
export HAP_ROUTE_ARTIFACT="$(realpath "$HAP_ROUTE_ARTIFACT")"

"$VIVADO" -mode batch -notrace \
    -source "$ROOT/vivado/scripts/audit_mlp_projection_repack12_to16_s24_history2_candidate_registered_ooc_route.tcl" \
    -log "$HAP_ROUTE_ARTIFACT/vivado_audit.log" \
    -journal "$HAP_ROUTE_ARTIFACT/vivado_audit.jou"

test -s "$HAP_ROUTE_ARTIFACT/audit_summary.txt"
grep -qx 'status=POST_ROUTE_CHECKPOINT_AUDIT_PASS_DIAGNOSTIC_NO_SHELL_BUDGET' \
    "$HAP_ROUTE_ARTIFACT/audit_summary.txt"
if grep -Eq '^(ERROR|FATAL):' "$HAP_ROUTE_ARTIFACT/vivado_audit.log"; then
    echo "Vivado audit log contains an ERROR/FATAL after nominal return" >&2
    exit 1
fi
cat "$HAP_ROUTE_ARTIFACT/audit_summary.txt"
