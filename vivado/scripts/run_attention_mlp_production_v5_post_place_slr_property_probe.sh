#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
TCL="$ROOT/vivado/scripts/probe_attention_mlp_production_v5_post_place_slr_properties.tcl"
DCP="$ROOT/vivado/reports/production_v5_place_20260817_223533/post_place.dcp"
SELECTOR="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_post_place_slr_property_probe.sh"
EXPECTED_DCP_SHA=63aa1417c862419edb102e85da15e28cfc1b52bec2136ad8ae72a1084a450b7a

[[ $# -eq 0 ]] || { printf 'usage: %s\n' "$0" >&2; exit 2; }
for path in "$VIVADO" "$TCL" "$DCP" "$SELECTOR" "$LAUNCHER"; do
    [[ -s "$path" ]] || { printf 'missing probe input: %s\n' "$path" >&2; exit 2; }
done
[[ "$(sha256sum "$DCP" | awk '{print $1}')" == "$EXPECTED_DCP_SHA" ]] || {
    printf 'fixed DCP SHA mismatch\n' >&2; exit 2;
}
code="$(sed -E '/^[[:space:]]*#/d' "$TCL")"
if grep -Eq '(^|[^[:alnum:]_])(place_design|route_design|phys_opt_design|write_checkpoint)([^[:alnum:]_]|$)' <<<"$code"; then
    printf 'SLR property probe contains forbidden implementation command\n' >&2
    exit 2
fi
mapfile -t active < <(pgrep -af '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; probe not started:\n' >&2
    printf '  %s\n' "${active[@]}" >&2
    exit 75
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_SLR_PROBE_DIR="${HAP_SLR_PROBE_DIR:-$ROOT/vivado/reports/production_v5_place_20260817_223533/v5_post_place_slr_property_probe_$STAMP}"
mkdir -p "$HAP_SLR_PROBE_DIR"
sha256sum "$DCP" "$SELECTOR" "$TCL" "$LAUNCHER" \
    > "$HAP_SLR_PROBE_DIR/INPUT_SHA256SUMS"
(cd / && sha256sum -c --strict "$HAP_SLR_PROBE_DIR/INPUT_SHA256SUMS")
cd "$ROOT"
"$VIVADO" -mode batch -notrace -source \
    vivado/scripts/probe_attention_mlp_production_v5_post_place_slr_properties.tcl \
    -log "$HAP_SLR_PROBE_DIR/vivado.log" \
    -journal "$HAP_SLR_PROBE_DIR/vivado.jou"
for output in summary.txt samples.txt vivado.log vivado.jou; do
    [[ -s "$HAP_SLR_PROBE_DIR/$output" ]] || {
        printf 'missing probe output: %s\n' "$output" >&2; exit 1;
    }
done
grep -Fqx 'status=V5_POST_PLACE_SLR_SAMPLE_PROBE_COMPLETE' \
    "$HAP_SLR_PROBE_DIR/summary.txt"
grep -Fqx 'samples=48' "$HAP_SLR_PROBE_DIR/summary.txt"
grep -Fqx 'global_physical_conclusion=0' "$HAP_SLR_PROBE_DIR/summary.txt"
grep -Fqx 'checkpoint_written=0' "$HAP_SLR_PROBE_DIR/summary.txt"
grep -Fqx 'implementation_commands_run=0' "$HAP_SLR_PROBE_DIR/summary.txt"
(cd / && sha256sum -c --strict "$HAP_SLR_PROBE_DIR/INPUT_SHA256SUMS")
sha256sum "$HAP_SLR_PROBE_DIR/summary.txt" \
    "$HAP_SLR_PROBE_DIR/samples.txt" "$HAP_SLR_PROBE_DIR/vivado.log" \
    "$HAP_SLR_PROBE_DIR/vivado.jou" \
    > "$HAP_SLR_PROBE_DIR/OUTPUT_SHA256SUMS"
(cd / && sha256sum -c --strict "$HAP_SLR_PROBE_DIR/OUTPUT_SHA256SUMS")
cat "$HAP_SLR_PROBE_DIR/summary.txt"
printf '%s\n' "$HAP_SLR_PROBE_DIR"
