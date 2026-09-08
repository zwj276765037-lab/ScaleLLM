#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
SELECTOR_LIB="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
SELECTOR_TCL="$ROOT/vivado/scripts/check_attention_mlp_production_v5_floorplan_selectors.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_floorplan_selector_check.sh"

if [[ $# -ne 1 ]]; then
    printf 'usage: %s V5_POST_OPT_DCP\n' "$0" >&2
    exit 2
fi
[[ -x "$VIVADO" ]] || {
    printf 'Vivado executable is missing: %s\n' "$VIVADO" >&2
    exit 2
}

export HAP_DCP="$(readlink -f -- "$1")"
export HAP_SELECTOR_LIB="$SELECTOR_LIB"
export HAP_SELECTOR_LAUNCHER="$LAUNCHER"
for input in "$HAP_DCP" "$SELECTOR_LIB" "$SELECTOR_TCL" "$LAUNCHER"; do
    [[ -s "$input" ]] || {
        printf 'missing or empty V5 selector input: %s\n' "$input" >&2
        exit 2
    }
    if [[ "$input" == *$'\n'* || "$input" == *$'\r'* ||
          "$input" == *'\'* ]]; then
        printf 'newline, carriage return, and backslash are forbidden in selector input paths: %q\n' \
            "$input" >&2
        exit 2
    fi
done

# This must be a separate, read-only reopen and must not share a Vivado process
# or compete with any batch implementation/query process.
mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; selector audit not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi

# The audit Tcl may source exactly one canonical, manifest-frozen selector
# library.  It may open exactly the manifest-frozen DCP.  No implementation,
# constraint/pblock mutation, design writer, or dynamic-dispatch command is
# legal in either read-only source.
selector_code="$(sed -E '/^[[:space:]]*#/d' "$SELECTOR_TCL")"
if [[ "$(grep -Ec '^[[:space:]]*source[[:space:]]+\$selector_lib[[:space:]]*$' \
        <<<"$selector_code" || true)" -ne 1 ]] ||
   [[ "$(grep -Ec '^[[:space:]]*open_checkpoint[[:space:]]+\$dcp[[:space:]]*$' \
        <<<"$selector_code" || true)" -ne 1 ]]; then
    printf 'selector Tcl must contain one exact frozen source and checkpoint open\n' >&2
    exit 2
fi
selector_code="$(sed -E \
    -e '/^[[:space:]]*#/d' \
    -e '/^[[:space:]]*source[[:space:]]+\$selector_lib[[:space:]]*$/d' \
    -e '/^[[:space:]]*open_checkpoint[[:space:]]+\$dcp[[:space:]]*$/d' \
    "$SELECTOR_TCL")"
library_code="$(sed -E \
    -e '/^[[:space:]]*#/d' \
    -e '/^[[:space:]]*namespace[[:space:]]+eval[[:space:]]+hap_v5_floorplan[[:space:]]*\{/d' \
    "$SELECTOR_LIB")"
# The selector library has two text-report helpers.  Mask only their fully
# qualified, statically known names before rejecting every other write_* token.
# They can write external evidence files but cannot write a design/checkpoint.
selector_code="${selector_code//hap_v5_floorplan::write_discovery/hap_v5_floorplan::allowed_report_discovery}"
selector_code="${selector_code//hap_v5_floorplan::write_pblock_audit/hap_v5_floorplan::allowed_report_pblock_audit}"
library_code="${library_code//hap_v5_floorplan::write_discovery/hap_v5_floorplan::allowed_report_discovery}"
library_code="${library_code//hap_v5_floorplan::write_pblock_audit/hap_v5_floorplan::allowed_report_pblock_audit}"
for code in "$selector_code" "$library_code"; do
    if grep -Eq \
        '(^|[^[:alnum:]_])(synth_design|opt_design|power_opt_design|place_design|phys_opt_design|route_design|link_design|read_checkpoint|open_checkpoint|launch_runs|wait_on_run|open_run|reset_run|reset_runs|create_run|delete_run|delete_runs|read_xdc|create_pblock|resize_pblock|delete_pblock|add_cells_to_pblock|remove_cells_from_pblock|set_property|reset_property|write_[[:alnum:]_]+|source|eval|uplevel|interp|rename|unknown|load)([^[:alnum:]_]|$)' \
        <<<"$code"; then
        printf 'selector read-only source contains a forbidden command\n' >&2
        exit 2
    fi
done

STAMP="$(date +%Y%m%d_%H%M%S)"
requested_dir="${HAP_SELECTOR_DIR:-$(dirname "$HAP_DCP")/v5_floorplan_selector_check_$STAMP}"
export HAP_SELECTOR_DIR="$(readlink -m -- "$requested_dir")"
if [[ "$HAP_SELECTOR_DIR" == *$'\n'* || "$HAP_SELECTOR_DIR" == *$'\r'* ||
      "$HAP_SELECTOR_DIR" == *'\'* ]]; then
    printf 'illegal selector output path: %q\n' "$HAP_SELECTOR_DIR" >&2
    exit 2
fi
if [[ -e "$HAP_SELECTOR_DIR" ]]; then
    printf 'selector evidence directory already exists: %s\n' \
        "$HAP_SELECTOR_DIR" >&2
    exit 2
fi
mkdir "$HAP_SELECTOR_DIR"

export HAP_SELECTOR_INPUT_SHA="$HAP_SELECTOR_DIR/INPUT_SHA256SUMS"
printf '%s\n' "$HAP_DCP" "$SELECTOR_LIB" "$SELECTOR_TCL" "$LAUNCHER" \
    > "$HAP_SELECTOR_DIR/INPUT_FILES"
sha256sum -- "$HAP_DCP" "$SELECTOR_LIB" "$SELECTOR_TCL" "$LAUNCHER" \
    > "$HAP_SELECTOR_INPUT_SHA"
if [[ "$(wc -l < "$HAP_SELECTOR_INPUT_SHA")" -ne 4 ]]; then
    printf 'selector input SHA manifest must have exactly four rows\n' >&2
    exit 2
fi
export HAP_EXPECTED_DCP_SHA256
HAP_EXPECTED_DCP_SHA256="$(sha256sum -- "$HAP_DCP" | awk '{print $1}')"
export HAP_SELECTOR_INPUT_MANIFEST_SHA256
HAP_SELECTOR_INPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_SELECTOR_INPUT_SHA" | awk '{print $1}')"

set +e
(cd / && sha256sum -c --strict "$HAP_SELECTOR_INPUT_SHA") \
    > "$HAP_SELECTOR_DIR/input_sha_precheck.txt" 2>&1
precheck_rc=$?
set -e

vivado_rc=125
if [[ "$precheck_rc" -eq 0 ]]; then
    cd "$ROOT"
    set +e
    "$VIVADO" -mode batch -notrace \
        -source vivado/scripts/check_attention_mlp_production_v5_floorplan_selectors.tcl \
        -log "$HAP_SELECTOR_DIR/vivado.log" \
        -journal "$HAP_SELECTOR_DIR/vivado.jou"
    vivado_rc=$?
    set -e
fi

# Recheck every input after every Vivado return, including a failed return.
# The separately frozen manifest digest prevents replacing an input together
# with its manifest row during the audit.
set +e
(cd / && sha256sum -c --strict "$HAP_SELECTOR_INPUT_SHA") \
    > "$HAP_SELECTOR_DIR/input_sha_postcheck.txt" 2>&1
postcheck_rc=$?
actual_manifest_sha="$(sha256sum -- "$HAP_SELECTOR_INPUT_SHA" \
    2>/dev/null | awk '{print $1}')"
manifest_rc=$?
set -e
manifest_match=0
if [[ "$manifest_rc" -eq 0 &&
      "$actual_manifest_sha" == "$HAP_SELECTOR_INPUT_MANIFEST_SHA256" ]]; then
    manifest_match=1
fi

for file in vivado.log vivado.jou; do
    if [[ ! -e "$HAP_SELECTOR_DIR/$file" ]]; then
        printf 'launcher_note=Vivado did not create %s\n' "$file" \
            > "$HAP_SELECTOR_DIR/$file"
    fi
done

require_exact_line() {
    local literal="$1" file="$2" key
    key="${literal%%=*}"
    if [[ "$(grep -Fxc -- "$literal" "$file" 2>/dev/null || true)" -ne 1 ]]; then
        printf 'selector exact gate failed: %s\n' "$literal" >&2
        return 1
    fi
    if [[ "$(grep -Ec "^${key}=" "$file" 2>/dev/null || true)" -ne 1 ]]; then
        printf 'selector field is missing or duplicated: %s\n' "$key" >&2
        return 1
    fi
}

validate_pass_outputs() {
    local required literal summary selectors
    summary="$HAP_SELECTOR_DIR/summary.txt"
    selectors="$HAP_SELECTOR_DIR/selectors.txt"
    for required in summary.txt selectors.txt vivado.log vivado.jou; do
        [[ -s "$HAP_SELECTOR_DIR/$required" ]] || {
            printf 'missing or empty selector output: %s\n' "$required" >&2
            return 1
        }
    done

    local -a exact_lines=(
        'status=V5_FLOORPLAN_SELECTORS_PASS'
        'evidence_class=V5_FLOORPLAN_SELECTOR_READ_ONLY_REOPEN'
        "dcp=$HAP_DCP"
        "input_dcp_sha256=$HAP_EXPECTED_DCP_SHA256"
        "input_selector_library_sha256=$(sha256sum -- "$SELECTOR_LIB" | awk '{print $1}')"
        "input_selector_tcl_sha256=$(sha256sum -- "$SELECTOR_TCL" | awk '{print $1}')"
        "input_launcher_sha256=$(sha256sum -- "$LAUNCHER" | awk '{print $1}')"
        "input_manifest_sha256=$HAP_SELECTOR_INPUT_MANIFEST_SHA256"
        'input_sha_inprocess_verified=1'
        'part=xcvu9p-flga2104-2L-e'
        'top=hap_attention_mlp_production_core'
        'contract_variant=P2_COHORT16_COL2_12_2'
        'pblock_contract_variant=P2_COHORT16_COL2_12_2'
        'dsp48e2=5453'
        'uram288=752'
        'mlp_kernel_dsp48e2=3072'
        'attention_board_variant=cohort16'
        'attention_dsp48e2=2296'
        'center_projection_dsp48e2=1632'
        'center_nonprojection_dsp48e2=149'
        'history2_repack_instances=2'
        'generic_repack_instances=0'
        'swiglu_frontend_instances=1'
        'swiglu_row_leaf_instances=2'
        'swiglu_unique_hadamard_instances=1'
        'swiglu_fold2_hadamard_instances=0'
        'swiglu_quantizer_instances=4'
        'swiglu_silu_instances=2'
        'leaf0_dsp48e2=2'
        'leaf1_dsp48e2=2'
        'leaf0_ramb36e2=6'
        'leaf1_ramb36e2=6'
        'branch0_dsp48e2=1536'
        'branch2_dsp48e2=1536'
        'outer0_dsp48e2=1538'
        'outer2_dsp48e2=1538'
        'outer0_ramb36e2=102'
        'outer2_ramb36e2=102'
        'outer_set_equation_ok=1'
        'selected_set_overlap=0'
        'dsp_selector_overlap=0'
        'dsp_selector_coverage=5453'
        'attention_row_instances=1'
        'kv_cache_instances=1'
        'kv_quantizer4_instances=1'
        'attention_island_target_slr=0'
        'attention_island_dsp48e2=52'
        'attention_island_ramb36e2=88'
        'attention_island_ramb18e2=2'
        'attention_island_uram288=0'
        'attention_island_quantizer_overlap=0'
        'attention_island_row_cache_overlap=0'
        'projection_lane_instances=128'
        'projection_lane_dsp48e2=17'
        'raw_weight_push_loads=37'
        'weight_data_capture_contract=32x256'
        'weight_data_capture_nets=32'
        'weight_data_capture_loads=256/256'
        'weight_meta_capture_contract=2x256'
        'weight_meta_capture_nets=2'
        'weight_meta_capture_loads=256/256'
        'weight_group_capture_contract=2x7'
        'weight_group_capture_nets=2'
        'weight_group_capture_loads=7/7'
        'projection_weight_capture_ok=1'
        'attention_metadata_uram288=80'
        'moved_lanes_slr0=16'
        'center_lanes_slr1=96'
        'moved_lanes_slr2=16'
        'planned_slr0_dsp48e2=1862'
        'planned_slr1_dsp48e2=1781'
        'planned_slr2_dsp48e2=1810'
        'per_slr_dsp_limit=1900'
        'dsp_plan_equation_ok=1'
        'checkpoint_written=0'
        'implementation_commands_run=0'
    )
    for literal in "${exact_lines[@]}"; do
        require_exact_line "$literal" "$summary" || return 1
    done
    if [[ "$(grep -Ec '^tool=2025\.2([^0-9].*)?$' "$summary" || true)" -ne 1 ||
          "$(grep -Ec '^tool=' "$summary" || true)" -ne 1 ]]; then
        printf 'selector tool-version gate failed\n' >&2
        return 1
    fi

    # Exact plan fields above already prove the lane and DSP equations.  Keep
    # the redundant arithmetic gate in Bash to avoid mawk's multiline parser
    # portability differences.
    local move0 center move2 dsp0 dsp1 dsp2
    move0="$(sed -n 's/^moved_lanes_slr0=//p' "$summary")"
    center="$(sed -n 's/^center_lanes_slr1=//p' "$summary")"
    move2="$(sed -n 's/^moved_lanes_slr2=//p' "$summary")"
    dsp0="$(sed -n 's/^planned_slr0_dsp48e2=//p' "$summary")"
    dsp1="$(sed -n 's/^planned_slr1_dsp48e2=//p' "$summary")"
    dsp2="$(sed -n 's/^planned_slr2_dsp48e2=//p' "$summary")"
    if (( move0 + center + move2 != 128 ||
          dsp0 + dsp1 + dsp2 != 5453 ||
          dsp0 > 1900 || dsp1 > 1900 || dsp2 > 1900 )); then
        printf 'selector dynamic lane/DSP plan gate failed\n' >&2
        return 1
    fi
    if [[ "$(grep -Fxc 'status=V5_FLOORPLAN_SELECTORS_PASS' \
            "$selectors" || true)" -ne 1 ]]; then
        printf 'selector discovery output status gate failed\n' >&2
        return 1
    fi
    if grep -Eiq '(^|[^[:alnum:]_])(FAIL|ERROR|FATAL)(:|\[|[[:space:]])' \
            "$HAP_SELECTOR_DIR/vivado.log" "$summary" "$selectors"; then
        printf 'selector audit rejected FAIL/Error/Fatal marker\n' >&2
        return 1
    fi
    return 0
}

gate_rc=125
if [[ "$precheck_rc" -eq 0 && "$vivado_rc" -eq 0 &&
      "$postcheck_rc" -eq 0 && "$manifest_match" -eq 1 ]]; then
    set +e
    validate_pass_outputs
    gate_rc=$?
    set -e
fi

final_rc=0
final_status=PASS
if [[ "$precheck_rc" -ne 0 ]]; then
    final_rc=1
    final_status=FAIL
elif [[ "$vivado_rc" -ne 0 ]]; then
    final_rc="$vivado_rc"
    final_status=FAIL
elif [[ "$postcheck_rc" -ne 0 || "$manifest_match" -ne 1 ||
        "$gate_rc" -ne 0 ]]; then
    final_rc=1
    final_status=FAIL
fi
printf '%s\n' \
    "status=$final_status" \
    "final_exit_code=$final_rc" \
    "input_sha_precheck_exit_code=$precheck_rc" \
    "vivado_exit_code=$vivado_rc" \
    "input_sha_postcheck_exit_code=$postcheck_rc" \
    "input_manifest_sha_match=$manifest_match" \
    "selector_gate_exit_code=$gate_rc" \
    'evidence_class=V5_FLOORPLAN_SELECTOR_READ_ONLY_REOPEN' \
    'checkpoint_written=0' \
    'implementation_commands_run=0' \
    > "$HAP_SELECTOR_DIR/launcher_status.txt"

# Hash every file in the fresh evidence directory on both PASS and FAIL paths,
# including input checks, log, journal, and launcher status.  Verify the output
# manifest before returning to the caller.
mapfile -d '' outputs < <(find "$HAP_SELECTOR_DIR" -maxdepth 1 -type f \
    ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
if [[ "${#outputs[@]}" -eq 0 ]]; then
    printf 'selector audit produced no hashable evidence\n' >&2
    exit 1
fi
sha256sum -- "${outputs[@]}" > "$HAP_SELECTOR_DIR/OUTPUT_SHA256SUMS"
(cd / && sha256sum -c --strict "$HAP_SELECTOR_DIR/OUTPUT_SHA256SUMS")

if [[ "$final_rc" -ne 0 ]]; then
    printf 'V5 selector read-only audit failed; evidence retained in %s\n' \
        "$HAP_SELECTOR_DIR" >&2
    printf '%s\n' "$HAP_SELECTOR_DIR"
    exit "$final_rc"
fi

cat "$HAP_SELECTOR_DIR/summary.txt"
printf '%s\n' "$HAP_SELECTOR_DIR"
