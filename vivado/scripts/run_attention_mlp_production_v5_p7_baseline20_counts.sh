#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
TCL="$ROOT/vivado/scripts/probe_attention_mlp_production_v5_p7_baseline20_counts.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_p7_baseline20_counts.sh"
export HAP_SELECTOR_LIB="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
export HAP_FINE19_LIB="$ROOT/vivado/scripts/v5_production_fine19_floorplan.tcl"
export HAP_COMPOSITE20_LIB="$ROOT/vivado/scripts/v5_production_composite21_floorplan.tcl"

[[ "$#" -eq 1 && "$(basename -- "$1")" == post_opt.dcp ]] || {
    printf 'usage: %s POST_OPT_DCP\n' "$0" >&2
    exit 2
}
export HAP_DCP="$(readlink -f -- "$1")"
[[ -s "$HAP_DCP" && -x "$VIVADO" ]] || exit 2
mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
[[ "${#active_batch[@]}" -eq 0 ]] || {
    printf 'another batch Vivado is active; P8 probe not started\n' >&2
    exit 75
}

STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_P7_PROBE_DIR="$(readlink -m -- \
    "${HAP_P7_PROBE_DIR:-$ROOT/vivado/reports/production_v5_p8_baseline20_counts_$STAMP}")"
[[ ! -e "$HAP_P7_PROBE_DIR" ]] || exit 2
mkdir "$HAP_P7_PROBE_DIR"
export HAP_P7_INPUT_SHA="$HAP_P7_PROBE_DIR/INPUT_SHA256SUMS"
printf '%s\n' "$HAP_DCP" "$HAP_SELECTOR_LIB" "$HAP_FINE19_LIB" \
    "$HAP_COMPOSITE20_LIB" "$TCL" "$LAUNCHER" \
    > "$HAP_P7_PROBE_DIR/INPUT_FILES"
sha256sum -- "$HAP_DCP" "$HAP_SELECTOR_LIB" "$HAP_FINE19_LIB" \
    "$HAP_COMPOSITE20_LIB" "$TCL" "$LAUNCHER" > "$HAP_P7_INPUT_SHA"
export HAP_P7_INPUT_MANIFEST_SHA256
HAP_P7_INPUT_MANIFEST_SHA256="$(sha256sum -- "$HAP_P7_INPUT_SHA" | awk '{print $1}')"
export HAP_EXPECTED_DCP_SHA256
HAP_EXPECTED_DCP_SHA256="$(sha256sum -- "$HAP_DCP" | awk '{print $1}')"

set +e
"$VIVADO" -mode batch -notrace -source "$TCL" \
    -log "$HAP_P7_PROBE_DIR/vivado.log" \
    -journal "$HAP_P7_PROBE_DIR/vivado.jou"
vivado_rc=$?
set -e
set +e
(cd / && sha256sum -c --strict "$HAP_P7_INPUT_SHA") \
    > "$HAP_P7_PROBE_DIR/input_sha_postcheck.txt" 2>&1
input_rc=$?
set -e
printf 'vivado_exit_code=%s\ninput_sha_recheck_exit_code=%s\n' \
    "$vivado_rc" "$input_rc" > "$HAP_P7_PROBE_DIR/launcher_status.txt"
mapfile -d '' outputs < <(find "$HAP_P7_PROBE_DIR" -maxdepth 1 \
    -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
sha256sum -- "${outputs[@]}" > "$HAP_P7_PROBE_DIR/OUTPUT_SHA256SUMS"
if (( vivado_rc != 0 || input_rc != 0 )); then
    printf '%s\n' "$HAP_P7_PROBE_DIR"
    exit 1
fi
expected_status=P8_BASELINE20_COUNTS_PASS
if [[ "${HAP_P8_DISCOVERY:-0}" == 1 ]]; then
    expected_status=P8_BASELINE20_DISCOVERY_PASS
fi
grep -Fqx "status=$expected_status" \
    "$HAP_P7_PROBE_DIR/summary.txt"
(cd / && sha256sum -c --strict "$HAP_P7_PROBE_DIR/OUTPUT_SHA256SUMS")
cat "$HAP_P7_PROBE_DIR/summary.txt"
printf '%s\n' "$HAP_P7_PROBE_DIR"
