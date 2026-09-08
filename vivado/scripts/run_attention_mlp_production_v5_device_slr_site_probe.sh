#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
PROBE_TCL="$ROOT/vivado/scripts/probe_attention_mlp_production_v5_device_slr_sites.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_device_slr_site_probe.sh"

[[ $# -eq 0 ]] || { printf 'usage: %s\n' "$0" >&2; exit 2; }
[[ -x "$VIVADO" ]] || { printf 'Vivado executable is missing: %s\n' "$VIVADO" >&2; exit 2; }
for input in "$PROBE_TCL" "$LAUNCHER"; do
    [[ -s "$input" ]] || { printf 'missing device probe input: %s\n' "$input" >&2; exit 2; }
done

probe_code="$(sed -E '/^[[:space:]]*#/d' "$PROBE_TCL")"
if grep -Eq \
        '(^|[^[:alnum:]_])(open_checkpoint|read_checkpoint|place_design|route_design|phys_opt_design|write_checkpoint)([^[:alnum:]_]|$)' \
        <<<"$probe_code"; then
    printf 'device probe contains a forbidden design/checkpoint command\n' >&2
    exit 2
fi
mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; device probe not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_V5_DEVICE_SLR_PROBE_DIR="${HAP_V5_DEVICE_SLR_PROBE_DIR:-$ROOT/vivado/reports/v5_device_slr_site_probe_$STAMP}"
mkdir -p "$HAP_V5_DEVICE_SLR_PROBE_DIR"
printf '%s\n' "$PROBE_TCL" "$LAUNCHER" > "$HAP_V5_DEVICE_SLR_PROBE_DIR/INPUT_FILES"
sha256sum "$PROBE_TCL" "$LAUNCHER" > "$HAP_V5_DEVICE_SLR_PROBE_DIR/INPUT_SHA256SUMS"

cd "$ROOT"
set +e
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/probe_attention_mlp_production_v5_device_slr_sites.tcl \
    -log "$HAP_V5_DEVICE_SLR_PROBE_DIR/vivado.log" \
    -journal "$HAP_V5_DEVICE_SLR_PROBE_DIR/vivado.jou"
vivado_rc=$?
set -e
printf 'final_exit_code=%d\ncheckpoint_opened=0\nimplementation_commands_run=0\ncheckpoint_written=0\n' \
    "$vivado_rc" > "$HAP_V5_DEVICE_SLR_PROBE_DIR/launcher_status.txt"

mapfile -d '' outputs < <(find "$HAP_V5_DEVICE_SLR_PROBE_DIR" -maxdepth 1 \
    -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
sha256sum "${outputs[@]}" > "$HAP_V5_DEVICE_SLR_PROBE_DIR/OUTPUT_SHA256SUMS"
if [[ "$vivado_rc" -ne 0 ]]; then
    printf 'V5 device SLR/site probe failed; evidence retained in %s\n' \
        "$HAP_V5_DEVICE_SLR_PROBE_DIR" >&2
    printf '%s\n' "$HAP_V5_DEVICE_SLR_PROBE_DIR"
    exit "$vivado_rc"
fi

SUMMARY="$HAP_V5_DEVICE_SLR_PROBE_DIR/summary.txt"
for literal in \
    'status=V5_DEVICE_SLR_SITE_API_PROBE_PASS' \
    'evidence_class=V5_DEVICE_ONLY_SLR_SITE_API_PROBE' \
    'slr_count=3' 'site_union_exact=1' 'cross_slr_site_overlap=0' \
    'reverse_relation_ok=1' 'site_has_slr_index_property=0' \
    'synthesis_run=1' 'disposable_probe_top=1' \
    'checkpoint_opened=0' 'implementation_commands_run=0' \
    'checkpoint_written=0'; do
    [[ "$(grep -Fxc "$literal" "$SUMMARY")" -eq 1 ]] || {
        printf 'device probe summary gate failed: %s\n' "$literal" >&2
        exit 1
    }
done
(cd / && sha256sum -c --strict "$HAP_V5_DEVICE_SLR_PROBE_DIR/INPUT_SHA256SUMS")
(cd / && sha256sum -c --strict "$HAP_V5_DEVICE_SLR_PROBE_DIR/OUTPUT_SHA256SUMS")
cat "$SUMMARY"
printf '%s\n' "$HAP_V5_DEVICE_SLR_PROBE_DIR"
