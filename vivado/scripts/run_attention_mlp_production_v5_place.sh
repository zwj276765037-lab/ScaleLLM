#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
if [[ $# -ne 2 ]]; then
    printf 'usage: %s V5_POST_OPT_DCP COMPOSITE21_PREPLACE_DIR\n' "$0" >&2
    exit 2
fi

export HAP_DCP="$(readlink -f -- "$1")"
[[ -s "$HAP_DCP" ]] || {
    printf 'missing or empty V5 post-opt DCP: %s\n' "$HAP_DCP" >&2
    exit 2
}
preplace_dir="$(readlink -f -- "$2")"
export HAP_PLACE_COMPOSITE21_PREPLACE_OUTPUT_SHA="$preplace_dir/OUTPUT_SHA256SUMS"
preplace_input_sha="$preplace_dir/INPUT_SHA256SUMS"
preplace_summary="$preplace_dir/summary.txt"
preplace_launcher_status="$preplace_dir/launcher_status.txt"
for input in "$HAP_PLACE_COMPOSITE21_PREPLACE_OUTPUT_SHA" "$preplace_input_sha" \
        "$preplace_summary" "$preplace_launcher_status"; do
    [[ -s "$input" ]] || {
        printf 'missing Composite21 pre-place evidence: %s\n' "$input" >&2
        exit 2
    }
done
(cd / && sha256sum -c --strict \
    "$HAP_PLACE_COMPOSITE21_PREPLACE_OUTPUT_SHA") >/dev/null
(cd / && sha256sum -c --strict "$preplace_input_sha") >/dev/null
for literal in status=V5_COMPOSITE21_PRE_PLACE_AUDIT_PASS \
        stage=V5_PRODUCTION_COMPOSITE21_PRE_PLACE_AUDIT \
        contract_variant=P9_COHORT16_MLP_CENTRAL_X2X4_21 \
        pblock_count=21 \
        central_anchor_range=CLOCKREGION_X2Y5:CLOCKREGION_X4Y9 \
        central_island_count=197091 central_island_delta=0 \
        central_island_dsp=80 mlp_remaining_count=88785 \
        mlp_remaining_delta=0 center_dsp_remaining_count=5 \
        center_dsp_remaining_dsp=5 central_partition_ok=1 \
        member_overlap=0 optimizer_extra_count=0 pblock_dsp_coverage=5453 \
        pblock_uram_coverage=752 pblock_wrong_slr=0 \
        soft_pblock_count=0 soft_outside=0 \
        probe_verified=1 \
        pre_place_drc_errors=0 checkpoint_written=0 \
        implementation_commands_run=0; do
    [[ "$(grep -Fxc -- "$literal" "$preplace_summary" || true)" -eq 1 ]] || {
        printf 'Composite21 pre-place summary gate failed: %s\n' "$literal" >&2
        exit 2
    }
done
for literal in status=PASS final_exit_code=0 vivado_exit_code=0 \
        probe_output_recheck_exit_code=0 audit_gate_exit_code=0 \
        checkpoint_written=0 \
        implementation_commands_run=0; do
    [[ "$(grep -Fxc -- "$literal" "$preplace_launcher_status" || true)" -eq 1 ]] || {
        printf 'Composite21 pre-place launcher gate failed: %s\n' "$literal" >&2
        exit 2
    }
done
export HAP_PLACE_COMPOSITE21_PREPLACE_OUTPUT_SHA256
HAP_PLACE_COMPOSITE21_PREPLACE_OUTPUT_SHA256="$(sha256sum -- \
    "$HAP_PLACE_COMPOSITE21_PREPLACE_OUTPUT_SHA" | awk '{print $1}')"
export HAP_PLACE_COMPOSITE21_PREPLACE_INPUT_SHA256
HAP_PLACE_COMPOSITE21_PREPLACE_INPUT_SHA256="$(sha256sum -- \
    "$preplace_input_sha" | awk '{print $1}')"

[[ -x "$VIVADO" ]] || {
    printf 'Vivado executable is missing: %s\n' "$VIVADO" >&2
    exit 2
}
mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; placement not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_PLACE_MODE="${HAP_PLACE_MODE:-accept}"
[[ "$HAP_PLACE_MODE" == "screen" || "$HAP_PLACE_MODE" == "accept" ]] || {
    printf 'HAP_PLACE_MODE must be screen or accept: %q\n' \
        "$HAP_PLACE_MODE" >&2
    exit 2
}
default_place_dir="$ROOT/vivado/reports/production_v5_place_$STAMP"
if [[ "$HAP_PLACE_MODE" == "screen" ]]; then
    default_place_dir="$ROOT/vivado/reports/production_v5_place_screen_$STAMP"
fi
requested_place_dir="${HAP_PLACE_DIR:-$default_place_dir}"
export HAP_PLACE_DIR="$(readlink -m -- "$requested_place_dir")"
export HAP_PLACE_DIRECTIVE="${HAP_PLACE_DIRECTIVE:-AltSpreadLogic_high}"
export HAP_JOBS="${HAP_JOBS:-32}"
[[ "$HAP_JOBS" == 32 ]] || {
    printf 'V5 production placement requires HAP_JOBS=32: %q\n' "$HAP_JOBS" >&2
    exit 2
}
[[ "$HAP_PLACE_DIR" != *$'\n'* && "$HAP_DCP" != *$'\n'* ]] || {
    printf 'newline is forbidden in V5 place input/output paths\n' >&2
    exit 2
}
[[ "$HAP_PLACE_DIRECTIVE" =~ ^[A-Za-z][A-Za-z0-9_]*$ ]] || {
    printf 'illegal V5 place directive: %q\n' "$HAP_PLACE_DIRECTIVE" >&2
    exit 2
}
[[ ! -e "$HAP_PLACE_DIR" ]] || {
    printf 'V5 place evidence directory already exists: %s\n' \
        "$HAP_PLACE_DIR" >&2
    exit 2
}
mkdir "$HAP_PLACE_DIR"

SELECTOR_LIB="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
FINE_LIB="$ROOT/vivado/scripts/v5_production_fine19_floorplan.tcl"
COMPOSITE_LIB="$ROOT/vivado/scripts/v5_production_composite21_floorplan.tcl"
PLACE_TCL="$ROOT/vivado/scripts/place_attention_mlp_production_v5_floorplan.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_place.sh"
CLOCK_XDC="$ROOT/vivado/constraints/attention_mlp_production_v5_ooc_clocks_100mhz.xdc"
IO_AUDIT="$ROOT/vivado/scripts/check_attention_mlp_production_io_selectors.tcl"
for input in "$SELECTOR_LIB" "$FINE_LIB" "$COMPOSITE_LIB" "$PLACE_TCL" "$LAUNCHER" \
        "$CLOCK_XDC" "$IO_AUDIT"; do
    [[ -s "$input" ]] || {
        printf 'missing or empty V5 place source: %s\n' "$input" >&2
        exit 2
    }
    [[ "$input" != *$'\n'* ]] || {
        printf 'newline is forbidden in V5 place source path: %q\n' "$input" >&2
        exit 2
    }
done
export HAP_PLACE_INPUT_SHA="$HAP_PLACE_DIR/INPUT_SHA256SUMS"
export HAP_PLACE_SELECTOR_LIB="$SELECTOR_LIB"
export HAP_PLACE_FINE_LIB="$FINE_LIB"
export HAP_PLACE_COMPOSITE_LIB="$COMPOSITE_LIB"
export HAP_PLACE_LAUNCHER="$LAUNCHER"
export HAP_PLACE_CLOCK_XDC="$CLOCK_XDC"
export HAP_PLACE_IO_AUDIT="$IO_AUDIT"
printf '%s\n' "$HAP_DCP" "$SELECTOR_LIB" "$FINE_LIB" "$COMPOSITE_LIB" "$PLACE_TCL" \
    "$LAUNCHER" "$CLOCK_XDC" "$IO_AUDIT" \
    "$HAP_PLACE_COMPOSITE21_PREPLACE_OUTPUT_SHA" > "$HAP_PLACE_DIR/INPUT_FILES"
sha256sum -- "$HAP_DCP" "$SELECTOR_LIB" "$FINE_LIB" "$COMPOSITE_LIB" "$PLACE_TCL" \
    "$LAUNCHER" "$CLOCK_XDC" "$IO_AUDIT" \
    "$HAP_PLACE_COMPOSITE21_PREPLACE_OUTPUT_SHA" > "$HAP_PLACE_INPUT_SHA"
export HAP_EXPECTED_DCP_SHA256
HAP_EXPECTED_DCP_SHA256="$(sha256sum -- "$HAP_DCP" | awk '{print $1}')"
export HAP_PLACE_INPUT_MANIFEST_SHA256
HAP_PLACE_INPUT_MANIFEST_SHA256="$(sha256sum -- "$HAP_PLACE_INPUT_SHA" | awk '{print $1}')"
(cd / && sha256sum -c --strict \
    "$HAP_PLACE_INPUT_SHA") > "$HAP_PLACE_DIR/input_sha_precheck.txt" 2>&1

cd "$ROOT"
set +e
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/place_attention_mlp_production_v5_floorplan.tcl \
    -log "$HAP_PLACE_DIR/vivado.log" \
    -journal "$HAP_PLACE_DIR/vivado.jou"
vivado_rc=$?
set -e

set +e
(cd / && sha256sum -c --strict \
    "$HAP_PLACE_INPUT_SHA") \
    > "$HAP_PLACE_DIR/input_sha_postcheck.txt" 2>&1
input_recheck_rc=$?
(cd / && sha256sum -c --strict \
    "$HAP_PLACE_COMPOSITE21_PREPLACE_OUTPUT_SHA" && \
    sha256sum -c --strict "$preplace_input_sha") \
    > "$HAP_PLACE_DIR/composite21_pre_place_postcheck.txt" 2>&1
preplace_recheck_rc=$?
actual_manifest_sha="$(sha256sum -- "$HAP_PLACE_INPUT_SHA" 2>/dev/null | awk '{print $1}')"
manifest_sha_rc=$?
set -e
manifest_sha_match=0
if [[ "$manifest_sha_rc" -eq 0 && \
      "$actual_manifest_sha" == "$HAP_PLACE_INPUT_MANIFEST_SHA256" ]]; then
    manifest_sha_match=1
fi

for vivado_artifact in vivado.log vivado.jou; do
    if [[ ! -e "$HAP_PLACE_DIR/$vivado_artifact" ]]; then
        printf 'launcher_note=Vivado did not create %s\n' "$vivado_artifact" \
            > "$HAP_PLACE_DIR/$vivado_artifact"
    fi
done

place_gate_rc=125
if [[ "$vivado_rc" -eq 0 && "$input_recheck_rc" -eq 0 && \
      "$preplace_recheck_rc" -eq 0 && "$manifest_sha_match" -eq 1 ]]; then
    place_gate_rc=0
fi

required_outputs=(summary.txt selectors_pre_place.txt selectors_post_place.txt
    selectors_fine19_pre_place.txt selectors_fine19_post_place.txt
    selectors_base_pre_place.txt selectors_base_post_place.txt
    pblocks_pre_place.txt pblocks_post_place.txt congestion_post_place.rpt
    drc_pre_place.rpt vivado.log vivado.jou input_sha_precheck.txt
    input_sha_postcheck.txt composite21_pre_place_postcheck.txt)
if [[ "$HAP_PLACE_MODE" == "accept" ]]; then
    required_outputs+=(post_place.dcp utilization_post_place.rpt
        utilization_hier_post_place.rpt utilization_slr_post_place.rpt
        timing_post_place.rpt clock_utilization_post_place.rpt
        cdc_post_place.rpt clock_interaction_post_place.rpt
        drc_post_place.rpt exceptions_coverage_post_place.rpt)
fi
for required in "${required_outputs[@]}"; do
    [[ -s "$HAP_PLACE_DIR/$required" ]] || {
        printf 'missing or empty V5 place output: %s\n' "$required" >&2
        place_gate_rc=1
    }
done
expected_summary_status=V5_PRODUCTION_PLACE_PASS
if [[ "$HAP_PLACE_MODE" == "screen" ]]; then
    expected_summary_status=V5_PRODUCTION_PLACE_SCREEN_PASS
fi
if [[ "$place_gate_rc" -eq 0 && \
      "$(grep -Fxc "status=$expected_summary_status" \
        "$HAP_PLACE_DIR/summary.txt")" -ne 1 ]]; then
    printf 'V5 place requires exactly one strict PASS status\n' >&2
    place_gate_rc=1
fi
if [[ "$place_gate_rc" -eq 0 ]] && \
   grep -Eiq '(^|[^[:alnum:]_])(FAIL|ERROR|FATAL)(:|\[|[[:space:]])' \
    "$HAP_PLACE_DIR/vivado.log" "$HAP_PLACE_DIR/summary.txt"; then
    printf 'V5 place rejected FAIL/Error/Fatal marker\n' >&2
    place_gate_rc=1
fi
if [[ "$place_gate_rc" -eq 0 ]]; then
if [[ "$HAP_PLACE_MODE" == "accept" ]]; then
set +e
(
set -e
awk -F= 'NF < 2 || seen[$1]++ {exit 1} END {exit 0}' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx "input_dcp=$HAP_DCP" "$HAP_PLACE_DIR/summary.txt"
grep -Fqx "input_dcp_sha256=$HAP_EXPECTED_DCP_SHA256" \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx "input_manifest_sha256=$HAP_PLACE_INPUT_MANIFEST_SHA256" \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'input_manifest_entries=9' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'provenance_verified=1' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx "composite21_pre_place_manifest=$HAP_PLACE_COMPOSITE21_PREPLACE_OUTPUT_SHA" \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx "composite21_pre_place_manifest_sha256=$HAP_PLACE_COMPOSITE21_PREPLACE_OUTPUT_SHA256" \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx "composite21_pre_place_input_manifest_sha256=$HAP_PLACE_COMPOSITE21_PREPLACE_INPUT_SHA256" \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'composite21_pre_place_verified=1' "$HAP_PLACE_DIR/summary.txt"
for exact in \
        composite21_pre_place_central_anchor_range=CLOCKREGION_X2Y5:CLOCKREGION_X4Y9 \
        composite21_pre_place_central_island_count=197091 \
        composite21_pre_place_central_island_dsp=80 \
        composite21_pre_place_mlp_remaining_count=88785 \
        composite21_pre_place_center_dsp_remaining=5 \
        composite21_pre_place_central_partition_ok=1; do
    grep -Fqx "$exact" "$HAP_PLACE_DIR/summary.txt"
done
awk -F= '/^fine19_post_place_optimizer_extra_count=/{n++; if ($2 < 0 || $2 > 4096) bad=1} \
    END{exit n==1 && !bad?0:1}' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'fine19_post_place_optimizer_extras_ok=1' \
    "$HAP_PLACE_DIR/summary.txt"
for key in composite21_post_place_fine_member_delta \
        composite21_post_place_mlp_residual_delta \
        composite21_post_place_central_island_delta \
        composite21_post_place_mlp_remaining_delta \
        composite21_post_place_attention_direct_delta; do
    awk -F= -v key="$key" '$1==key {n++; if ($2 < -65536 || $2 > 65536) bad=1} \
        END{exit n==1 && !bad?0:1}' "$HAP_PLACE_DIR/summary.txt"
done
for exact in \
        composite21_post_place_central_anchor_range=CLOCKREGION_X2Y5:CLOCKREGION_X4Y9 \
        composite21_post_place_central_island_dsp=80 \
        composite21_post_place_center_dsp_remaining=5 \
        composite21_post_place_central_partition_ok=1; do
    grep -Fqx "$exact" "$HAP_PLACE_DIR/summary.txt"
done
awk -F= '
    $1=="composite21_post_place_central_island_count" {c++; count=$2}
    $1=="composite21_post_place_central_island_delta" {d++; delta=$2}
    END{exit c==1 && d==1 && count==197091+delta?0:1}
' "$HAP_PLACE_DIR/summary.txt"
awk -F= '
    $1=="composite21_post_place_mlp_remaining_count" {c++; count=$2}
    $1=="composite21_post_place_mlp_remaining_delta" {d++; delta=$2}
    END{exit c==1 && d==1 && count==88785+delta?0:1}
' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'composite21_post_place_selector_deltas_ok=1' \
    "$HAP_PLACE_DIR/summary.txt"
awk -F= '/^composite21_post_place_pblock_optimizer_extras=/{n++; if ($2 < 0 || $2 > 4096) bad=1} \
    END{exit n==1 && !bad?0:1}' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'composite21_post_place_pblock_optimizer_extras_ok=1' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'flow_mode=accept' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'acceptance_evidence=1' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'route_eligible=1' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'checkpoint_written=1' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx "jobs=$HAP_JOBS" "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'mlp_kernel_dsp48e2=3072' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'uram288=752' "$HAP_PLACE_DIR/summary.txt"
for exact in raw_weight_push_loads=37 \
    weight_data_capture_contract=32x256 weight_data_capture_nets=32 \
    weight_data_capture_loads=256/256 \
    weight_meta_capture_contract=2x256 weight_meta_capture_nets=2 \
    weight_meta_capture_loads=256/256 \
    weight_group_capture_contract=2x7 weight_group_capture_nets=2 \
    weight_group_capture_loads=7/7 projection_weight_capture_ok=1; do
    grep -Fqx "$exact" "$HAP_PLACE_DIR/summary.txt"
done
grep -Fqx 'history2_repack_instances=2' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'generic_repack_instances=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'compact_input_frontend_instances=1' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'down_elastic2_instances=2' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'mlp_local_clear_ff=2' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'mlp_local_clear_protected_ff=2' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'branch0_local_clear_ff=1' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'branch1_local_clear_ff=1' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'branch0_local_clear_slr=1 0 0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'branch1_local_clear_slr=0 0 1' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'mlp_local_clear_wrong_slr=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'mlp_central_clear_ff=1' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'mlp_central_clear_branch_endpoints=2' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'mlp_central_clear_direct_branch_state=0' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'unplaced_primitives=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'wrong_slr_primitives=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'pre_place_pblock_contract_ok=1' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'pblock_contract_variant=P9_COHORT16_MLP_CENTRAL_X2X4_21' \
    "$HAP_PLACE_DIR/summary.txt"
for exact in projection_exact_cover=1 region1_exact_cover=1 \
        owner_exact_cover=1 weight_owner_residency_ok=1; do
    grep -Fqx "$exact" "$HAP_PLACE_DIR/summary.txt"
done
grep -Fqx 'attention_island_target_slr=0' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'attention_island_dsp48e2=52' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'attention_island_ramb36e2=88' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'attention_island_ramb18e2=2' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'attention_island_uram288=0' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'attention_island_quantizer_overlap=0' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'attention_island_row_cache_overlap=0' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'outer0_dsp48e2=1538' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'outer2_dsp48e2=1538' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'outer0_ramb36e2=102' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'outer2_ramb36e2=102' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'attention_island_pblock_dsp48e2=52' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'attention_island_pblock_ramb36e2=88' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'attention_island_pblock_ramb18e2=2' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'attention_island_pblock_uram288=0' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'dsp48e2=5453' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'moved_lanes_slr0=16' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'center_lanes_slr1=96' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'moved_lanes_slr2=16' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'planned_slr0_dsp48e2=1862' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'planned_slr1_dsp48e2=1781' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'planned_slr2_dsp48e2=1810' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'post_place_live_rediscovery_ok=1' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'post_place_pblock_contract_ok=1' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'post_place_pblock_count=21' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'post_place_pblock_dsp_coverage=5453' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'post_place_pblock_uram_coverage=752' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'post_place_pblock_wrong_slr=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'post_place_pblock_overlap=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'attention_island_wrong_slr=0' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'composite21_additional_wrong_slr=0' \
    "$HAP_PLACE_DIR/summary.txt"
for exact in p9_central_island_wrong_slr=0 \
        p9_center_dsp_remaining_wrong_slr=0 p9_mlp_remaining_wrong_slr=0; do
    grep -Fqx "$exact" "$HAP_PLACE_DIR/summary.txt"
done
grep -Fqx 'attention_direct_unconstrained=1' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'attention_direct_unresolved_primitives=0' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'attention_direct_placement_ok=1' "$HAP_PLACE_DIR/summary.txt"
awk -F= '/^attention_direct_slr[012]_primitives=/{n++; if ($2 < 0) bad=1; sum += $2} \
    /^attention_direct_physical_primitives=/{p++; physical=$2} \
    /^attention_direct_virtual_primitives=/{v++; virtual=$2} \
    END{exit n==3 && p==1 && v==1 && !bad && sum==physical && \
        physical+virtual>0?0:1}' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'congestion_level6_or_higher_windows=0' \
    "$HAP_PLACE_DIR/summary.txt"
awk -F= '/^congestion_level5_or_higher_windows=/{n++; if ($2 < 0 || $2 > 1) bad=1} \
    END{exit n==1 && !bad?0:1}' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'congestion_schema_header_count=1' \
    "$HAP_PLACE_DIR/summary.txt"
awk -F= '/^congestion_data_rows_recognized=/{n++; if ($2 < 0) bad=1} \
    END{exit n==1 && !bad?0:1}' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'congestion_schema_ok=1' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'pre_place_drc_errors=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'post_place_drc_errors=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'false_path_exception_rows=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'datapath_only_exception_rows=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'no_clock_endpoints=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'unconstrained_paths=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'no_input_delay_ports=3' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'no_output_delay_ports=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'partial_input_delay_ports=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'partial_output_delay_ports=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'timing_coverage_ok=1' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'cdc_critical=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'data_bufg=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'fast_gate_ok=1' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'level5_screen_ok=1' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'uram_distribution_ok=1' "$HAP_PLACE_DIR/summary.txt"
awk -F= '/^dsp48e2=/{n++; if ($2<=0 || $2>5500) bad=1} \
    END{exit n==1 && !bad?0:1}' \
    "$HAP_PLACE_DIR/summary.txt"
awk -F= '/^slr[012]_dsp48e2=/{n++; if ($2>1900) bad=1} \
    END{exit n==3 && !bad?0:1}' \
    "$HAP_PLACE_DIR/summary.txt"
)
place_gate_rc=$?
set -e
else
set +e
(
set -e
awk -F= 'NF < 2 || seen[$1]++ {exit 1} END {exit 0}' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx "input_dcp=$HAP_DCP" "$HAP_PLACE_DIR/summary.txt"
grep -Fqx "input_dcp_sha256=$HAP_EXPECTED_DCP_SHA256" \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx "input_manifest_sha256=$HAP_PLACE_INPUT_MANIFEST_SHA256" \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'input_manifest_entries=9' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx "composite21_pre_place_manifest=$HAP_PLACE_COMPOSITE21_PREPLACE_OUTPUT_SHA" \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx "composite21_pre_place_manifest_sha256=$HAP_PLACE_COMPOSITE21_PREPLACE_OUTPUT_SHA256" \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx "composite21_pre_place_input_manifest_sha256=$HAP_PLACE_COMPOSITE21_PREPLACE_INPUT_SHA256" \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'composite21_pre_place_verified=1' "$HAP_PLACE_DIR/summary.txt"
for exact in \
        composite21_pre_place_central_anchor_range=CLOCKREGION_X2Y5:CLOCKREGION_X4Y9 \
        composite21_pre_place_central_island_count=197091 \
        composite21_pre_place_central_island_dsp=80 \
        composite21_pre_place_mlp_remaining_count=88785 \
        composite21_pre_place_center_dsp_remaining=5 \
        composite21_pre_place_central_partition_ok=1; do
    grep -Fqx "$exact" "$HAP_PLACE_DIR/summary.txt"
done
awk -F= '/^fine19_post_place_optimizer_extra_count=/{n++; if ($2 < 0 || $2 > 4096) bad=1} \
    END{exit n==1 && !bad?0:1}' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'fine19_post_place_optimizer_extras_ok=1' \
    "$HAP_PLACE_DIR/summary.txt"
for key in composite21_post_place_fine_member_delta \
        composite21_post_place_mlp_residual_delta \
        composite21_post_place_central_island_delta \
        composite21_post_place_mlp_remaining_delta \
        composite21_post_place_attention_direct_delta; do
    awk -F= -v key="$key" '$1==key {n++; if ($2 < -65536 || $2 > 65536) bad=1} \
        END{exit n==1 && !bad?0:1}' "$HAP_PLACE_DIR/summary.txt"
done
for exact in \
        composite21_post_place_central_anchor_range=CLOCKREGION_X2Y5:CLOCKREGION_X4Y9 \
        composite21_post_place_central_island_dsp=80 \
        composite21_post_place_center_dsp_remaining=5 \
        composite21_post_place_central_partition_ok=1; do
    grep -Fqx "$exact" "$HAP_PLACE_DIR/summary.txt"
done
awk -F= '
    $1=="composite21_post_place_central_island_count" {c++; count=$2}
    $1=="composite21_post_place_central_island_delta" {d++; delta=$2}
    END{exit c==1 && d==1 && count==197091+delta?0:1}
' "$HAP_PLACE_DIR/summary.txt"
awk -F= '
    $1=="composite21_post_place_mlp_remaining_count" {c++; count=$2}
    $1=="composite21_post_place_mlp_remaining_delta" {d++; delta=$2}
    END{exit c==1 && d==1 && count==88785+delta?0:1}
' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'composite21_post_place_selector_deltas_ok=1' \
    "$HAP_PLACE_DIR/summary.txt"
awk -F= '/^composite21_post_place_pblock_optimizer_extras=/{n++; if ($2 < 0 || $2 > 4096) bad=1} \
    END{exit n==1 && !bad?0:1}' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'composite21_post_place_pblock_optimizer_extras_ok=1' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'flow_mode=screen' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'acceptance_evidence=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'route_eligible=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'checkpoint_written=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'timing_run=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'cdc_run=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'post_place_drc_run=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'exception_coverage_run=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx "jobs=$HAP_JOBS" "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'dsp48e2=5453' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'mlp_kernel_dsp48e2=3072' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'uram288=752' "$HAP_PLACE_DIR/summary.txt"
for exact in raw_weight_push_loads=37 \
    weight_data_capture_contract=32x256 weight_data_capture_nets=32 \
    weight_data_capture_loads=256/256 \
    weight_meta_capture_contract=2x256 weight_meta_capture_nets=2 \
    weight_meta_capture_loads=256/256 \
    weight_group_capture_contract=2x7 weight_group_capture_nets=2 \
    weight_group_capture_loads=7/7 projection_weight_capture_ok=1; do
    grep -Fqx "$exact" "$HAP_PLACE_DIR/summary.txt"
done
grep -Fqx 'pblock_contract_variant=P9_COHORT16_MLP_CENTRAL_X2X4_21' \
    "$HAP_PLACE_DIR/summary.txt"
for exact in projection_exact_cover=1 region1_exact_cover=1 \
        owner_exact_cover=1 weight_owner_residency_ok=1; do
    grep -Fqx "$exact" "$HAP_PLACE_DIR/summary.txt"
done
grep -Fqx 'slr0_dsp48e2=1862' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'slr1_dsp48e2=1781' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'slr2_dsp48e2=1810' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'slr0_uram288=224' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'slr1_uram288=224' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'slr2_uram288=304' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'unplaced_primitives=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'wrong_slr_primitives=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'post_place_pblock_contract_ok=1' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'post_place_pblock_wrong_slr=0' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'post_place_pblock_count=21' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'post_place_pblock_overlap=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'composite21_additional_wrong_slr=0' \
    "$HAP_PLACE_DIR/summary.txt"
for exact in p9_central_island_wrong_slr=0 \
        p9_center_dsp_remaining_wrong_slr=0 p9_mlp_remaining_wrong_slr=0; do
    grep -Fqx "$exact" "$HAP_PLACE_DIR/summary.txt"
done
grep -Fqx 'attention_direct_unconstrained=1' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'attention_direct_unresolved_primitives=0' \
    "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'attention_direct_placement_ok=1' "$HAP_PLACE_DIR/summary.txt"
awk -F= '/^attention_direct_slr[012]_primitives=/{n++; if ($2 < 0) bad=1; sum += $2} \
    /^attention_direct_physical_primitives=/{p++; physical=$2} \
    /^attention_direct_virtual_primitives=/{v++; virtual=$2} \
    END{exit n==3 && p==1 && v==1 && !bad && sum==physical && \
        physical+virtual>0?0:1}' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'pre_place_drc_errors=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'data_bufg=0' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'congestion_level6_or_higher_windows=0' \
    "$HAP_PLACE_DIR/summary.txt"
awk -F= '/^congestion_level5_or_higher_windows=/{n++; if ($2 < 0 || $2 > 1) bad=1} \
    END{exit n==1 && !bad?0:1}' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'congestion_schema_header_count=1' \
    "$HAP_PLACE_DIR/summary.txt"
awk -F= '/^congestion_data_rows_recognized=/{n++; if ($2 < 0) bad=1} \
    END{exit n==1 && !bad?0:1}' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'congestion_schema_ok=1' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'resource_ok=1' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'placement_ok=1' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'uram_distribution_ok=1' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'screen_policy_ok=1' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'fast_gate_ok=1' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'level5_screen_ok=1' "$HAP_PLACE_DIR/summary.txt"
grep -Fqx 'level6_congestion_ok=1' "$HAP_PLACE_DIR/summary.txt"
[[ ! -e "$HAP_PLACE_DIR/post_place.dcp" ]]
)
place_gate_rc=$?
set -e
fi
fi

final_rc=0
final_status=PASS
if [[ "$vivado_rc" -ne 0 ]]; then
    final_rc="$vivado_rc"
    final_status=FAIL
elif [[ "$input_recheck_rc" -ne 0 || "$preplace_recheck_rc" -ne 0 || \
        "$manifest_sha_match" -ne 1 || "$place_gate_rc" -ne 0 ]]; then
    final_rc=1
    final_status=FAIL
fi
checkpoint_written=0
[[ -s "$HAP_PLACE_DIR/post_place.dcp" ]] && checkpoint_written=1
route_eligible=0
acceptance_evidence=0
if [[ "$HAP_PLACE_MODE" == "accept" && "$final_rc" -eq 0 ]]; then
    acceptance_evidence=1
    route_eligible=1
fi
printf '%s\n' \
    "status=$final_status" \
    "flow_mode=$HAP_PLACE_MODE" \
    "acceptance_evidence=$acceptance_evidence" \
    "route_eligible=$route_eligible" \
    "final_exit_code=$final_rc" \
    "vivado_exit_code=$vivado_rc" \
    "input_sha_recheck_exit_code=$input_recheck_rc" \
    "composite21_pre_place_recheck_exit_code=$preplace_recheck_rc" \
    "input_manifest_sha_match=$manifest_sha_match" \
    "place_gate_exit_code=$place_gate_rc" \
    "checkpoint_written=$checkpoint_written" \
    'vivado_invoked=1' \
    'implementation_commands_requested=1' \
    'bitstream_generated=0' \
    > "$HAP_PLACE_DIR/launcher_status.txt"

# Freeze every nonempty artifact, not a hand-maintained subset.  This makes a
# newly added report part of the lineage automatically and prevents an
# untracked implementation output from being consumed downstream.
mapfile -d '' place_outputs < <(find "$HAP_PLACE_DIR" -maxdepth 1 \
    -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
[[ "${#place_outputs[@]}" -ne 0 ]] || {
    printf 'V5 place produced no hashable evidence\n' >&2
    exit 1
}
sha256sum -- "${place_outputs[@]}" > "$HAP_PLACE_DIR/OUTPUT_SHA256SUMS"
(cd / && sha256sum -c --strict "$HAP_PLACE_INPUT_SHA")
(cd / && sha256sum -c --strict \
    "$HAP_PLACE_DIR/OUTPUT_SHA256SUMS")
if [[ "$final_rc" -ne 0 ]]; then
    printf 'V5 place failed; evidence retained in %s\n' \
        "$HAP_PLACE_DIR" >&2
    printf '%s\n' "$HAP_PLACE_DIR"
    exit "$final_rc"
fi
cat "$HAP_PLACE_DIR/summary.txt"
printf '%s\n' "$HAP_PLACE_DIR"
