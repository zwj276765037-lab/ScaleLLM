#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
: "${HAP_ROUTE_ARTIFACT:?set HAP_ROUTE_ARTIFACT to a completed OOC artifact}"
export HAP_ROUTE_ARTIFACT="$(realpath "$HAP_ROUTE_ARTIFACT")"
LOG="$HAP_ROUTE_ARTIFACT/fanout_route_audit.log"
JOU="$HAP_ROUTE_ARTIFACT/fanout_route_audit.jou"
cd "$ROOT"

"$VIVADO" -mode batch -notrace \
  -source vivado/scripts/audit_mlp_down_branch_elastic2_s24_ooc_route.tcl \
  -log "$LOG" -journal "$JOU"
if [[ "$(grep -c '^status=DOWN_ELASTIC2_READ_ONLY_AUDIT_PASS$' \
    "$HAP_ROUTE_ARTIFACT/fanout_route_audit.txt")" -ne 1 ]]; then
  echo "audit launcher requires exactly one trusted PASS marker" >&2
  exit 1
fi
sha256sum \
  vivado/scripts/audit_mlp_down_branch_elastic2_s24_ooc_route.tcl \
  vivado/scripts/run_audit_mlp_down_branch_elastic2_s24_ooc_route.sh \
  "$HAP_ROUTE_ARTIFACT/post_route.dcp" \
  "$HAP_ROUTE_ARTIFACT/fanout_route_audit.txt" \
  "$LOG" "$JOU" \
  >"$HAP_ROUTE_ARTIFACT/FANOUT_ROUTE_AUDIT_SHA256SUMS"
printf '%s\n' "$HAP_ROUTE_ARTIFACT"
