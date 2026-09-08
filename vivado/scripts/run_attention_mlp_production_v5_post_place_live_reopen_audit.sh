#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
FIXED_DCP="$ROOT/vivado/reports/production_v5_place_20260817_223533/post_place.dcp"
EXPECTED_DCP_SHA=63aa1417c862419edb102e85da15e28cfc1b52bec2136ad8ae72a1084a450b7a
AUDIT_TCL="$ROOT/vivado/scripts/audit_attention_mlp_production_v5_post_place_live_reopen.tcl"
SELECTOR_LIB="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_post_place_live_reopen_audit.sh"

[[ $# -eq 0 ]] || {
    printf 'usage: %s\n' "$0" >&2
    exit 2
}
[[ -x "$VIVADO" ]] || {
    printf 'Vivado executable is missing: %s\n' "$VIVADO" >&2
    exit 2
}
for input in "$FIXED_DCP" "$AUDIT_TCL" "$SELECTOR_LIB" "$LAUNCHER"; do
    [[ -s "$input" ]] || {
        printf 'missing or empty reopen-audit input: %s\n' "$input" >&2
        exit 2
    }
done
[[ "$(sha256sum "$FIXED_DCP" | awk '{print $1}')" == \
    "$EXPECTED_DCP_SHA" ]] || {
    printf 'fixed Run 0138 post-place DCP SHA mismatch\n' >&2
    exit 2
}

# This audit must not compete with another batch implementation/query process.
mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; reopen audit not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi

# Fail closed if an implementation or checkpoint-write command is ever added
# to the read-only Tcl.  Comments are removed before this source audit.
audit_code="$(sed -E '/^[[:space:]]*#/d' "$AUDIT_TCL")"
if grep -Eq \
    '(^|[^[:alnum:]_])(place_design|route_design|phys_opt_design|write_checkpoint)([^[:alnum:]_]|$)' \
    <<<"$audit_code"; then
    printf 'reopen audit Tcl contains a forbidden state-changing command\n' >&2
    exit 2
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_REOPEN_AUDIT_DIR="${HAP_REOPEN_AUDIT_DIR:-$ROOT/vivado/reports/production_v5_place_20260817_223533/v5_post_place_live_reopen_audit_$STAMP}"
export HAP_REOPEN_INPUT_SHA="$HAP_REOPEN_AUDIT_DIR/INPUT_SHA256SUMS"
mkdir -p "$HAP_REOPEN_AUDIT_DIR"
printf '%s\n' "$FIXED_DCP" "$SELECTOR_LIB" "$AUDIT_TCL" "$LAUNCHER" \
    > "$HAP_REOPEN_AUDIT_DIR/INPUT_FILES"
sha256sum "$FIXED_DCP" "$SELECTOR_LIB" "$AUDIT_TCL" "$LAUNCHER" \
    > "$HAP_REOPEN_INPUT_SHA"
(cd / && sha256sum -c --strict "$HAP_REOPEN_INPUT_SHA")

archive_outputs() {
    local -a outputs=()
    mapfile -d '' outputs < <(find "$HAP_REOPEN_AUDIT_DIR" -maxdepth 1 \
        -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
    if [[ "${#outputs[@]}" -ne 0 ]]; then
        sha256sum "${outputs[@]}" > "$HAP_REOPEN_AUDIT_DIR/OUTPUT_SHA256SUMS"
    fi
}

cd "$ROOT"
set +e
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/audit_attention_mlp_production_v5_post_place_live_reopen.tcl \
    -log "$HAP_REOPEN_AUDIT_DIR/vivado.log" \
    -journal "$HAP_REOPEN_AUDIT_DIR/vivado.jou"
vivado_rc=$?
set -e
printf 'final_exit_code=%d\ncheckpoint_written=0\nimplementation_commands_run=0\n' \
    "$vivado_rc" > "$HAP_REOPEN_AUDIT_DIR/launcher_status.txt"
archive_outputs
if [[ "$vivado_rc" -ne 0 ]]; then
    printf 'V5 post-place read-only reopen failed; evidence retained in %s\n' \
        "$HAP_REOPEN_AUDIT_DIR" >&2
    printf '%s\n' "$HAP_REOPEN_AUDIT_DIR"
    exit "$vivado_rc"
fi

for required in summary.txt selectors_live_reopen.txt \
        pblocks_live_reopen.txt vivado.log launcher_status.txt; do
    [[ -s "$HAP_REOPEN_AUDIT_DIR/$required" ]] || {
        printf 'missing or empty reopen-audit output: %s\n' "$required" >&2
        exit 1
    }
done
SUMMARY="$HAP_REOPEN_AUDIT_DIR/summary.txt"
for literal in \
    'status=V5_POST_PLACE_LIVE_REOPEN_AUDIT_PASS' \
    'evidence_class=V5_POST_PLACE_READ_ONLY_REOPEN' \
    'live_rediscovery=1' 'pblock_contract_variant=legacy10' \
    'pblock_count=10' \
    'pblock_dsp_coverage=5469' 'pblock_uram_coverage=752' \
    'pblock_wrong_slr=0' 'dsp48e2=5469' 'uram288=752' \
    'slr0_dsp48e2=1791' 'slr1_dsp48e2=1870' \
    'slr2_dsp48e2=1808' 'slr0_uram288=224' \
    'slr1_uram288=224' 'slr2_uram288=304' \
    'unplaced_primitives=0' 'wrong_slr_primitives=0' \
    'exact_resource_ok=1' 'exact_distribution_ok=1' \
    'exact_pblock_ok=1' 'exact_placement_ok=1' \
    'checkpoint_written=0' 'implementation_commands_run=0'; do
    [[ "$(grep -Fxc "$literal" "$SUMMARY")" -eq 1 ]] || {
        printf 'reopen-audit summary gate failed: %s\n' "$literal" >&2
        exit 1
    }
done
if grep -Eiq '(^|[^[:alnum:]_])(FAIL|ERROR|FATAL)(:|\[|[[:space:]])' \
        "$SUMMARY" "$HAP_REOPEN_AUDIT_DIR/selectors_live_reopen.txt" \
        "$HAP_REOPEN_AUDIT_DIR/pblocks_live_reopen.txt"; then
    printf 'reopen audit rejected FAIL/Error/Fatal output marker\n' >&2
    exit 1
fi

(cd / && sha256sum -c --strict "$HAP_REOPEN_INPUT_SHA")
sha256sum "$SUMMARY" \
    "$HAP_REOPEN_AUDIT_DIR/selectors_live_reopen.txt" \
    "$HAP_REOPEN_AUDIT_DIR/pblocks_live_reopen.txt" \
    "$HAP_REOPEN_AUDIT_DIR/vivado.log" \
    "$HAP_REOPEN_AUDIT_DIR/vivado.jou" \
    "$HAP_REOPEN_AUDIT_DIR/launcher_status.txt" \
    > "$HAP_REOPEN_AUDIT_DIR/OUTPUT_SHA256SUMS"
(cd / && sha256sum -c --strict \
    "$HAP_REOPEN_AUDIT_DIR/OUTPUT_SHA256SUMS")
cat "$SUMMARY"
printf '%s\n' "$HAP_REOPEN_AUDIT_DIR"
