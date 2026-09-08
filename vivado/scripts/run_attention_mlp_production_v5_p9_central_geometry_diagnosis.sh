#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
TCL="$ROOT/vivado/scripts/diagnose_attention_mlp_production_v5_p9_central_geometry.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_p9_central_geometry_diagnosis.sh"
export HAP_SELECTOR_LIB="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
export HAP_FINE19_LIB="$ROOT/vivado/scripts/v5_production_fine19_floorplan.tcl"
export HAP_COMPOSITE20_LIB="$ROOT/vivado/scripts/v5_production_composite21_floorplan.tcl"

[[ "$#" -eq 2 && "$(basename -- "$1")" == post_opt.dcp &&
    "$(basename -- "$2")" == OUTPUT_SHA256SUMS ]] || {
    printf 'usage: %s POST_OPT_DCP P8_PLACE_OUTPUT_SHA256SUMS\n' "$0" >&2
    exit 2
}
export HAP_DCP="$(readlink -f -- "$1")"
export HAP_P8_PLACE_OUTPUT_SHA="$(readlink -f -- "$2")"
export HAP_P9_LAUNCHER="$LAUNCHER"
export HAP_JOBS="${HAP_JOBS:-32}"
[[ "$HAP_JOBS" == 32 && -x "$VIVADO" ]] || exit 2

inputs=("$HAP_DCP" "$HAP_SELECTOR_LIB" "$HAP_FINE19_LIB"
    "$HAP_COMPOSITE20_LIB" "$HAP_P8_PLACE_OUTPUT_SHA" "$TCL" "$LAUNCHER")
for input in "${inputs[@]}"; do
    [[ -s "$input" && "$input" != *$'\n'* && "$input" != *$'\r'* ]] || {
        printf 'missing or unsafe P9 input: %q\n' "$input" >&2
        exit 2
    }
done

mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
[[ "${#active_batch[@]}" -eq 0 ]] || {
    printf 'another batch Vivado is active; P9 diagnosis not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
}

readonly_code="$(sed -E '/^[[:space:]]*#/d' "$TCL")"
if grep -Eq \
    '(^|[^[:alnum:]_])(synth_design|opt_design|power_opt_design|place_design|phys_opt_design|route_design|link_design|read_xdc|create_pblock|resize_pblock|delete_pblock|add_cells_to_pblock|remove_cells_from_pblock|set_property|reset_property|write_checkpoint|write_bitstream|write_cfgmem|launch_runs|wait_on_run)([^[:alnum:]_]|$)' \
        <<<"$readonly_code"; then
    printf 'P9 diagnosis contains a forbidden command\n' >&2
    exit 2
fi
for forbidden in hap_v5_fine19::apply hap_v5_composite21::apply; do
    if grep -Fq "$forbidden" <<<"$readonly_code"; then
        printf 'P9 diagnosis calls forbidden apply proc: %s\n' "$forbidden" >&2
        exit 2
    fi
done

(cd / && sha256sum -c --strict "$HAP_P8_PLACE_OUTPUT_SHA") >/dev/null
p8_dir="$(dirname "$HAP_P8_PLACE_OUTPUT_SHA")"
for literal in status=FAIL acceptance_evidence=0 route_eligible=0 \
        checkpoint_written=0 congestion_level5_or_higher_windows=24 \
        congestion_level6_or_higher_windows=12; do
    [[ "$(grep -Fxc -- "$literal" "$p8_dir/summary.txt" || true)" -eq 1 ]] || {
        printf 'P8 summary gate failed: %s\n' "$literal" >&2
        exit 2
    }
done

STAMP="$(date +%Y%m%d_%H%M%S)"
requested="${HAP_P9_DIAG_DIR:-$ROOT/vivado/reports/production_v5_p9_central_geometry_diagnosis_$STAMP}"
export HAP_P9_DIAG_DIR="$(readlink -m -- "$requested")"
[[ ! -e "$HAP_P9_DIAG_DIR" ]] || {
    printf 'P9 diagnosis directory already exists: %s\n' "$HAP_P9_DIAG_DIR" >&2
    exit 2
}
mkdir "$HAP_P9_DIAG_DIR"
export HAP_P9_INPUT_SHA="$HAP_P9_DIAG_DIR/INPUT_SHA256SUMS"
printf '%s\n' "${inputs[@]}" > "$HAP_P9_DIAG_DIR/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$HAP_P9_INPUT_SHA"
export HAP_P9_INPUT_MANIFEST_SHA256
HAP_P9_INPUT_MANIFEST_SHA256="$(sha256sum -- "$HAP_P9_INPUT_SHA" | awk '{print $1}')"
export HAP_EXPECTED_DCP_SHA256
HAP_EXPECTED_DCP_SHA256="$(sha256sum -- "$HAP_DCP" | awk '{print $1}')"
export HAP_P8_PLACE_OUTPUT_SHA256
HAP_P8_PLACE_OUTPUT_SHA256="$(sha256sum -- "$HAP_P8_PLACE_OUTPUT_SHA" | awk '{print $1}')"
(cd / && sha256sum -c --strict "$HAP_P9_INPUT_SHA") \
    > "$HAP_P9_DIAG_DIR/input_sha_precheck.txt" 2>&1

set +e
"$VIVADO" -mode batch -notrace -source "$TCL" \
    -log "$HAP_P9_DIAG_DIR/vivado.log" \
    -journal "$HAP_P9_DIAG_DIR/vivado.jou"
vivado_rc=$?
set -e
set +e
(cd / && sha256sum -c --strict "$HAP_P9_INPUT_SHA") \
    > "$HAP_P9_DIAG_DIR/input_sha_postcheck.txt" 2>&1
input_rc=$?
(cd / && sha256sum -c --strict "$HAP_P8_PLACE_OUTPUT_SHA") \
    > "$HAP_P9_DIAG_DIR/p8_output_sha_postcheck.txt" 2>&1
p8_rc=$?
set -e

gate_rc=0
summary="$HAP_P9_DIAG_DIR/summary.txt"
for literal in status=P9_CENTRAL_GEOMETRY_DIAGNOSIS_PASS \
        proposed_pblock_count=21 proposed_member_overlap=0 \
        candidate_partition_ok=1 island_outside_source=0 \
        anchor_island_capacity_ok=1 anchor_envelope_capacity_ok=1 \
        dsp48e2=5453 uram288=752 resource_ok=1 \
        canonical_pblock_count_after=0 floorplan_mutated=0 \
        implementation_commands_run=0 checkpoint_written=0; do
    [[ "$(grep -Fxc -- "$literal" "$summary" 2>/dev/null || true)" -eq 1 ]] || {
        printf 'P9 diagnosis summary gate failed: %s\n' "$literal" >&2
        gate_rc=1
    }
done

final_rc=0
if (( vivado_rc != 0 )); then
    final_rc=$vivado_rc
elif (( input_rc != 0 || p8_rc != 0 || gate_rc != 0 )); then
    final_rc=1
fi
printf '%s\n' \
    "status=$([[ "$final_rc" -eq 0 ]] && printf PASS || printf FAIL)" \
    "final_exit_code=$final_rc" "vivado_exit_code=$vivado_rc" \
    "input_sha_recheck_exit_code=$input_rc" \
    "p8_output_sha_recheck_exit_code=$p8_rc" \
    "diagnosis_gate_exit_code=$gate_rc" 'floorplan_mutated=0' \
    'implementation_commands_run=0' 'checkpoint_written=0' \
    > "$HAP_P9_DIAG_DIR/launcher_status.txt"
mapfile -d '' outputs < <(find "$HAP_P9_DIAG_DIR" -maxdepth 1 -type f \
    -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
sha256sum -- "${outputs[@]}" > "$HAP_P9_DIAG_DIR/OUTPUT_SHA256SUMS"
(cd / && sha256sum -c --strict "$HAP_P9_DIAG_DIR/OUTPUT_SHA256SUMS")
printf '%s\n' "$HAP_P9_DIAG_DIR"
exit "$final_rc"

