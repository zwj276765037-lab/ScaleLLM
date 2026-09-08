#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
[[ -x "$VIVADO" ]] || { printf 'Vivado executable is missing\n' >&2; exit 2; }
[[ $# -eq 2 ]] || {
    printf 'usage: %s FAILED_PLACE_DIR OUTPUT_DIR\n' "$0" >&2
    exit 2
}
export HAP_JOBS="${HAP_JOBS:-32}"
[[ "$HAP_JOBS" == 32 ]] || { printf 'HAP_JOBS must equal 32\n' >&2; exit 2; }

FAILED_DIR="$(readlink -f "$1")"
OUT="$(readlink -m "$2")"
[[ ! -e "$OUT" ]] || { printf 'output already exists: %s\n' "$OUT" >&2; exit 2; }
mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
[[ "${#active_batch[@]}" -eq 0 ]] || {
    printf 'another batch Vivado is active; diagnostic not started\n' >&2
    exit 75
}

SCRIPT="$ROOT/vivado/scripts/audit_attention_mlp_production_v5_p10_post_place_diagnostic.tcl"
SELECTOR="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
P10="$ROOT/vivado/scripts/place_attention_mlp_production_v5_p10_p2.tcl"
SNAPSHOT="$ROOT/vivado/reports/production_v5_p10_p2_place_20260903_mission0065_recovery_source_snapshot"
SELECTOR_SNAPSHOT="$SNAPSHOT/v5_production_floorplan_selectors.pre_recovery.tcl"
P10_SNAPSHOT="$SNAPSHOT/place_attention_mlp_production_v5_p10_p2.pre_recovery.tcl"
DCP="$FAILED_DIR/post_place_diagnostic_only.dcp"
FAILED_INPUT="$FAILED_DIR/INPUT_SHA256SUMS"
FAILED_OUTPUT="$FAILED_DIR/OUTPUT_SHA256SUMS"
FAILED_SUMMARY="$FAILED_DIR/summary.txt"
FAILED_STATUS="$FAILED_DIR/launcher_status.txt"
for file in "$SCRIPT" "$SELECTOR" "$P10" "$SELECTOR_SNAPSHOT" \
        "$P10_SNAPSHOT" "$DCP" "$FAILED_INPUT" "$FAILED_OUTPUT" \
        "$FAILED_SUMMARY" "$FAILED_STATUS"; do
    [[ -s "$file" ]] || { printf 'missing diagnostic input: %s\n' "$file" >&2; exit 2; }
done

mkdir -p "$OUT"
export HAP_DIAGNOSTIC_DCP="$DCP"
export HAP_FAILED_PLACE_DIR="$FAILED_DIR"
export HAP_DIAGNOSTIC_AUDIT_DIR="$OUT"
export HAP_RECOVERY_SNAPSHOT_DIR="$SNAPSHOT"
export HAP_EXPECTED_DIAGNOSTIC_DCP_SHA256=253417640187a0a8c4074b5e1a2f413334cd8244b0ed1174821c2bfc84f28a6f
export HAP_EXPECTED_FAILED_INPUT_SHA256=be0001a83350b611365272d5728357ba77c98d1c2b1025a3c0b77493469ae9cb
export HAP_EXPECTED_FAILED_OUTPUT_SHA256=864d0576ed71069cfa55a9ba015b0d81bc3cd6787b5e61b714b996bd865416ab
export HAP_DIAGNOSTIC_INPUT_SHA="$OUT/INPUT_SHA256SUMS"
sha256sum -- "$DCP" "$FAILED_INPUT" "$FAILED_OUTPUT" "$SELECTOR_SNAPSHOT" \
    "$P10_SNAPSHOT" "$SELECTOR" "$P10" "$SCRIPT" "$0" \
    > "$HAP_DIAGNOSTIC_INPUT_SHA"
export HAP_DIAGNOSTIC_INPUT_SHA256
HAP_DIAGNOSTIC_INPUT_SHA256="$(sha256sum "$HAP_DIAGNOSTIC_INPUT_SHA" | awk '{print $1}')"

set +e
"$VIVADO" -mode batch -notrace -source "$SCRIPT" \
    -log "$OUT/vivado.log" -journal "$OUT/vivado.jou"
vivado_rc=$?
set -e
input_rc=0
sha256sum -c --strict "$HAP_DIAGNOSTIC_INPUT_SHA" \
    > "$OUT/input_sha_postcheck.txt" 2>&1 || input_rc=$?
summary_ok=0
if [[ "$vivado_rc" -eq 0 && "$input_rc" -eq 0 && -s "$OUT/summary.txt" ]] &&
        grep -Fqx 'status=V5_P10_POST_PLACE_DIAGNOSTIC_COMPLETE' "$OUT/summary.txt"; then
    summary_ok=1
fi
final_rc=1
[[ "$summary_ok" -eq 1 ]] && final_rc=0
{
    printf 'status=%s\n' "$([[ "$final_rc" -eq 0 ]] && printf PASS || printf FAIL)"
    printf 'evidence_class=READ_ONLY_RECOVERY_DIAGNOSTIC\n'
    printf 'route_eligible=0\n'
    printf 'implementation_commands_run=0\n'
    printf 'vivado_exit_code=%d\n' "$vivado_rc"
    printf 'input_sha_recheck_exit_code=%d\n' "$input_rc"
    printf 'diagnostic_gate_exit_code=%d\n' "$((1 - summary_ok))"
    printf 'final_exit_code=%d\n' "$final_rc"
} > "$OUT/launcher_status.txt"
find "$OUT" -maxdepth 1 -type f -size +0c ! -name OUTPUT_SHA256SUMS \
    -print0 | sort -z | xargs -0 sha256sum -- > "$OUT/OUTPUT_SHA256SUMS"
exit "$final_rc"

