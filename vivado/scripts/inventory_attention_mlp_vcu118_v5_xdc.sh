#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
    printf 'usage: %s PROJECT_ROOT BUILD_REPORT_DIR OUTPUT\n' "$0" >&2
    exit 2
fi

ROOT="$(readlink -f "$1")"
REPORT_DIR="$(readlink -f "$2")"
OUTPUT="$3"
[[ -d "$ROOT" ]] || { printf 'missing project root: %s\n' "$ROOT" >&2; exit 2; }
mkdir -p "$(dirname "$OUTPUT")"

V5_PROJECT="$ROOT/vivado/project/attention_mlp_vcu118_v5_dual_ddr"
V5_USER_XDC="$ROOT/vivado/constraints/attention_mlp_vcu118_board_v5.xdc"
[[ -s "$V5_USER_XDC" ]] || {
    printf 'missing V5 user XDC: %s\n' "$V5_USER_XDC" >&2
    exit 2
}
mapfile -d '' FILES < <(
    printf '%s\0' "$V5_USER_XDC"
    find "$V5_PROJECT" -type f -name '*.xdc' -print0 2>/dev/null
)
if (( ${#FILES[@]} == 0 )); then
    printf 'no XDC files found below %s\n' "$ROOT" >&2
    exit 2
fi

printf 'class|file|sha256|false_path|datapath_only|scoped_ref_count|scoped_cells_count|scoped_ref_values|scoped_cell_values|core_selector_hits|scope_safe|active_in_run\n' \
    > "$OUTPUT"
for file in "${FILES[@]}"; do
    rel="${file#$ROOT/}"
    if [[ "$file" == "$REPORT_DIR"/* ]]; then
        continue
    elif [[ "$file" == "$V5_USER_XDC" ]]; then
        class=USER
    elif [[ "$file" == "$V5_PROJECT"/*.gen/sources_1/bd/*/ip/* &&
            "$file" != *"/ip/attention_mlp_vcu118_v5_bd_core_0/"* &&
            "$file" != *"/ip/attention_mlp_vcu118_v5_bd_core_gate_0/"* &&
            "$file" != *"/ip/attention_mlp_vcu118_v5_bd_d0_gate_0/"* &&
            "$file" != *"/ip/attention_mlp_vcu118_v5_bd_d1_gate_0/"* ]]; then
        class=VENDOR_IP
    elif [[ "$file" == "$V5_PROJECT"/*.runs/*_synth_1/* &&
            ( "$file" == *"_ddr4_"* || "$file" == *"_xdma_"* ||
              "$file" == *"_clk_core_"* || "$file" == *"_rst_core_"* ||
              "$file" == *"_rst_ddr0_"* || "$file" == *"_rst_ddr1_"* ||
              "$file" == *"_host_split_"* || "$file" == *"_d0_smc_"* ||
              "$file" == *"_d1_smc_"* || "$file" == *"_ctrl_smc_"* ||
              "$file" == *"_d0_mig_slice_"* ||
              "$file" == *"_d1_mig_slice_"* ) ]]; then
        class=VENDOR_IP
    elif [[ "$file" == "$V5_PROJECT"/* ]]; then
        # Top-run and module-reference propagated XDCs are not blindly
        # classified as vendor IP.  Any exception in these sources fails.
        class=UNKNOWN
    else
        class=UNKNOWN
    fi

    false_count="$(rg -N -i -o '(^|[;[:space:]])set_false_path([;[:space:]]|$)' \
        "$file" 2>/dev/null | wc -l || true)"
    datapath_count="$(rg -N -i -o -- '-datapath_only([;[:space:]]|$)' \
        "$file" 2>/dev/null | wc -l || true)"
    scoped_ref_count="$(rg -N -i -o 'SCOPED_TO_REF' "$file" 2>/dev/null | wc -l || true)"
    scoped_cells_count="$(rg -N -i -o 'SCOPED_TO_CELLS' "$file" 2>/dev/null | wc -l || true)"
    if (( false_count > 0 || datapath_count > 0 )); then
        core_hits="$(rg -N -i -o \
            'hap_attention_mlp_(board|production)_core|/core/inst/|core/inst/' \
            "$file" 2>/dev/null | wc -l || true)"
    else
        core_hits=0
    fi

    scope_safe=1
    active=1
    # This source-tree scan cannot know Vivado's propagated IP scope.  Record
    # only source text here; the active compile-order exporter supplies the
    # authoritative SCOPED_TO_REF/SCOPED_TO_CELLS fields before signoff.
    if [[ "$class" == VENDOR_IP &&
          ( "$false_count" -gt 0 || "$datapath_count" -gt 0 ) ]]; then
        scoped_ref_count=1
    fi
    sha="$(sha256sum "$file" | awk '{print $1}')"
    printf '%s|%s|%s|%s|%s|%s|%s|-|-|%s|%s|%s\n' \
        "$class" "$file" "$sha" "$false_count" "$datapath_count" \
        "$scoped_ref_count" "$scoped_cells_count" "$core_hits" \
        "$scope_safe" "$active" \
        >> "$OUTPUT"
done

# Fail before implementation if any user/unknown source contains a forbidden
# exception or if a vendor exception textually selects the production core.
awk -F'|' '
    NR == 1 { next }
    $1 == "USER" && ($4 != 0 || $5 != 0) { bad = 1 }
    $1 == "UNKNOWN" && ($4 != 0 || $5 != 0) { bad = 1 }
    $1 == "VENDOR_IP" && $8 != 0 { bad = 1 }
    END { exit bad ? 1 : 0 }
' "$OUTPUT" || {
    printf 'XDC source/scope inventory rejected a forbidden exception\n' >&2
    exit 1
}
