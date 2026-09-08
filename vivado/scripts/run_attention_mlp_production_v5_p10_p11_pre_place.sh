#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_JOBS="${HAP_JOBS:-32}"
[[ "$HAP_JOBS" == 32 ]] || {
    printf 'P11 pre-place requires HAP_JOBS=32\n' >&2
    exit 2
}
requested_report="${HAP_REPORT_DIR:-$ROOT/vivado/reports/production_v5_p10_p11_pre_place_$STAMP}"
export HAP_PREPLACE_DIR="$(readlink -m -- "$requested_report")"
export HAP_DCP="$(readlink -e -- "${HAP_DCP:?set HAP_DCP to a fresh V5 post_opt.dcp}")"
export HAP_PREPLACE_SELECTOR_LIB="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
export HAP_PREPLACE_GEOMETRY_LIB="$ROOT/vivado/scripts/projection_core16x16_w8_reuse_ooc_floorplan.tcl"
export HAP_PREPLACE_P5_LIB="$ROOT/vivado/scripts/v5_production_p5_input_partition_floorplan.tcl"
export HAP_PREPLACE_P9_POST_LIB="$ROOT/vivado/scripts/v5_production_p9_postprocess_partition_floorplan.tcl"
export HAP_PREPLACE_P11_QUANTIZER3_LIB="$ROOT/vivado/scripts/v5_production_p11_quantizer3_locality_floorplan.tcl"
export HAP_PREPLACE_BOUNDARY_LIB="$ROOT/vivado/scripts/audit_mlp_p8_parent_ingress_boundary_replica_aware.tcl"
export HAP_PREPLACE_P10_PROC_LIB="$ROOT/vivado/scripts/place_attention_mlp_production_v5_p10_p2.tcl"
export HAP_PREPLACE_LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_p10_p11_pre_place.sh"
export HAP_PREPLACE_CLOCK_XDC="$ROOT/vivado/constraints/attention_mlp_production_v5_ooc_clocks_100mhz.xdc"
export HAP_PREPLACE_IO_AUDIT="$ROOT/vivado/scripts/check_attention_mlp_production_io_selectors.tcl"
AUDIT="$ROOT/vivado/scripts/audit_attention_mlp_production_v5_p10_p11_pre_place.tcl"
export HAP_PREPLACE_P11_DECISION_SHA="$(readlink -e -- \
    "${HAP_P11_DECISION_SHA:?set HAP_P11_DECISION_SHA to Mission 0130 OUTPUT_SHA256SUMS}")"

[[ -x "$VIVADO" ]] || { printf 'Vivado missing: %s\n' "$VIVADO" >&2; exit 2; }
[[ ! -e "$HAP_PREPLACE_DIR" ]] || {
    printf 'P11 pre-place report already exists: %s\n' "$HAP_PREPLACE_DIR" >&2
    exit 2
}
mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; P11 pre-place not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi
mkdir "$HAP_PREPLACE_DIR"

inputs=("$HAP_DCP" "$HAP_PREPLACE_SELECTOR_LIB" \
    "$HAP_PREPLACE_GEOMETRY_LIB" "$HAP_PREPLACE_P5_LIB" \
    "$HAP_PREPLACE_P9_POST_LIB" "$HAP_PREPLACE_P11_QUANTIZER3_LIB" \
    "$HAP_PREPLACE_BOUNDARY_LIB" \
    "$HAP_PREPLACE_P10_PROC_LIB" "$AUDIT" "$HAP_PREPLACE_LAUNCHER" \
    "$HAP_PREPLACE_CLOCK_XDC" "$HAP_PREPLACE_IO_AUDIT" \
    "$HAP_PREPLACE_P11_DECISION_SHA")
printf '%s\n' "${inputs[@]}" > "$HAP_PREPLACE_DIR/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$HAP_PREPLACE_DIR/INPUT_SHA256SUMS"
export HAP_PREPLACE_INPUT_SHA="$HAP_PREPLACE_DIR/INPUT_SHA256SUMS"
export HAP_EXPECTED_DCP_SHA256="$(sha256sum -- "$HAP_DCP" | awk '{print $1}')"
export HAP_PREPLACE_INPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_PREPLACE_INPUT_SHA" | awk '{print $1}')"
export HAP_PREPLACE_P11_DECISION_SHA256="$(sha256sum -- \
    "$HAP_PREPLACE_P11_DECISION_SHA" | awk '{print $1}')"
(cd / && sha256sum -c --strict "$HAP_PREPLACE_INPUT_SHA") \
    > "$HAP_PREPLACE_DIR/input_sha_precheck.txt" 2>&1

set +e
"$VIVADO" -mode batch -notrace -source "$AUDIT" \
    -log "$HAP_PREPLACE_DIR/vivado.log" \
    -journal "$HAP_PREPLACE_DIR/vivado.jou"
vivado_rc=$?
(cd / && sha256sum -c --strict "$HAP_PREPLACE_INPUT_SHA") \
    > "$HAP_PREPLACE_DIR/input_sha_postcheck.txt" 2>&1
input_rc=$?
set -e

status=FAIL
if (( vivado_rc == 0 && input_rc == 0 )) && \
   [[ -s "$HAP_PREPLACE_DIR/summary.txt" ]] && \
   [[ "$(grep -Fxc 'status=V5_P10_P11_PRE_PLACE_PASS' \
        "$HAP_PREPLACE_DIR/summary.txt")" -eq 1 ]]; then
    status=PASS
fi
printf 'status=%s\nvivado_exit_code=%d\ninput_sha_recheck_exit_code=%d\n' \
    "$status" "$vivado_rc" "$input_rc" > "$HAP_PREPLACE_DIR/launcher_status.txt"
printf 'implementation_commands_run=0\ncheckpoint_written=0\nroute_eligible=0\nbitstream_generated=0\n' \
    >> "$HAP_PREPLACE_DIR/launcher_status.txt"

mapfile -d '' outputs < <(find "$HAP_PREPLACE_DIR" -maxdepth 1 \
    -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
sha256sum -- "${outputs[@]}" > "$HAP_PREPLACE_DIR/OUTPUT_SHA256SUMS"
if [[ "$status" != PASS ]]; then
    printf 'P11 pre-place failed; evidence: %s\n' "$HAP_PREPLACE_DIR" >&2
    (( vivado_rc != 0 )) && exit "$vivado_rc"
    exit 1
fi
(cd / && sha256sum -c --strict "$HAP_PREPLACE_DIR/INPUT_SHA256SUMS")
(cd / && sha256sum -c --strict "$HAP_PREPLACE_DIR/OUTPUT_SHA256SUMS")
printf '%s\n' "$HAP_PREPLACE_DIR"
