#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PLAIN="$ROOT/vivado/scripts/audit_mlp_p8_parent_ingress_boundary.tcl"
REPLICA="$ROOT/vivado/scripts/audit_mlp_p8_parent_ingress_boundary_replica_aware.tcl"
PREPLACE="$ROOT/vivado/scripts/run_attention_mlp_production_v5_p16_noclip_pre_place.sh"

fail() {
    printf 'MLP_V5_FORMAT_V3_PHYSICAL_SELECTORS_STATIC_FAIL: %s\n' "$*" >&2
    exit 1
}

require_once() {
    local file="$1" text="$2" count
    [[ -s "$file" ]] || fail "missing or empty input: ${file#"$ROOT/"}"
    count="$(grep -Fxc -- "$text" "$file" || true)"
    [[ "$count" == 1 ]] ||
        fail "expected exactly one contract in ${file#"$ROOT/"}: $text (actual=$count)"
}

reject_fixed() {
    local file="$1" text="$2"
    ! grep -Fq -- "$text" "$file" ||
        fail "legacy format-v2 selector in ${file#"$ROOT/"}: $text"
}

for helper in "$PLAIN" "$REPLICA"; do
    require_once "$helper" \
        '    set shared [cells_of_module hap_mlp_shared_dual_slice16x12_s44_s46]'
    require_once "$helper" \
        '    set branches [cells_of_module hap_mlp_shared_local_slice8x12_s44_s46]'
    reject_fixed "$helper" 'hap_mlp_shared_dual_slice16x12_s43_s45'
    reject_fixed "$helper" 'hap_mlp_shared_local_slice8x12_s43_s45'
done

if [[ -e "$PREPLACE" ]]; then
    require_once "$PREPLACE" \
        'export HAP_PREPLACE_BOUNDARY_LIB="$ROOT/vivado/scripts/audit_mlp_p8_parent_ingress_boundary_replica_aware.tcl"'
fi

printf '%s\n' MLP_V5_FORMAT_V3_PHYSICAL_SELECTORS_STATIC_PASS \
    shared=hap_mlp_shared_dual_slice16x12_s44_s46 \
    branches=hap_mlp_shared_local_slice8x12_s44_s46
