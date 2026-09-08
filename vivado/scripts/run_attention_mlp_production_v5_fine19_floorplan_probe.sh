#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
SELECTOR_LIB="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
FINE_LIB="$ROOT/vivado/scripts/v5_production_fine19_floorplan.tcl"
COMPOSITE21_LIB="$ROOT/vivado/scripts/v5_production_composite21_floorplan.tcl"
PROBE_TCL="$ROOT/vivado/scripts/probe_attention_mlp_production_v5_fine19_floorplan.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_fine19_floorplan_probe.sh"

[[ $# -eq 3 ]] || {
    printf 'usage: %s V5_POST_OPT_DCP POST_OPT_AUDIT_OUTPUT_SHA256SUMS P9_DIAG_OUTPUT_SHA256SUMS\n' "$0" >&2
    exit 2
}
[[ -x "$VIVADO" ]] || { printf 'missing Vivado: %s\n' "$VIVADO" >&2; exit 2; }
export HAP_DCP="$(readlink -f -- "$1")"
export HAP_POST_OPT_AUDIT_OUTPUT_SHA="$(readlink -f -- "$2")"
export HAP_P9_DIAG_OUTPUT_SHA="$(readlink -f -- "$3")"
export HAP_JOBS="${HAP_JOBS:-32}"
[[ "$HAP_JOBS" == 32 ]] || {
    printf 'V5 production qualification requires HAP_JOBS=32: %q\n' \
        "$HAP_JOBS" >&2
    exit 2
}
for input in "$HAP_DCP" "$SELECTOR_LIB" "$FINE_LIB" "$COMPOSITE21_LIB" \
        "$PROBE_TCL" "$LAUNCHER" "$HAP_POST_OPT_AUDIT_OUTPUT_SHA" \
        "$HAP_P9_DIAG_OUTPUT_SHA"; do
    [[ -s "$input" ]] || { printf 'missing fine19 input: %s\n' "$input" >&2; exit 2; }
    [[ "$input" != *$'\n'* && "$input" != *$'\r'* ]] || {
        printf 'newline is forbidden in fine19 input path: %q\n' "$input" >&2
        exit 2
    }
done

p9_diag_dir="$(dirname "$HAP_P9_DIAG_OUTPUT_SHA")"
p9_diag_summary="$p9_diag_dir/summary.txt"
p9_diag_status="$p9_diag_dir/launcher_status.txt"
p9_diag_capacity="$p9_diag_dir/candidate_capacity.txt"
for evidence in "$p9_diag_summary" "$p9_diag_status" "$p9_diag_capacity"; do
    [[ -s "$evidence" ]] || {
        printf 'missing P9 diagnostic evidence: %s\n' "$evidence" >&2
        exit 2
    }
done
(cd / && sha256sum -c --strict "$HAP_P9_DIAG_OUTPUT_SHA") >/dev/null
for literal in status=P9_CENTRAL_GEOMETRY_DIAGNOSIS_PASS \
        proposed_pblock_count=21 proposed_member_overlap=0 \
        central_island_member_count=197091 central_island_dsp=80 \
        mlp_remaining_member_count=88785 center_dsp_remaining=5 \
        candidate_partition_ok=1 island_outside_source=0 \
        anchor_island_capacity_ok=1 anchor_envelope_capacity_ok=1 \
        dsp48e2=5453 uram288=752 resource_ok=1 \
        canonical_pblock_count_after=0 floorplan_mutated=0 \
        implementation_commands_run=0 checkpoint_written=0; do
    [[ "$(grep -Fxc -- "$literal" "$p9_diag_summary" || true)" -eq 1 ]] || {
        printf 'P9 diagnostic summary gate failed: %s\n' "$literal" >&2
        exit 2
    }
done

post_opt_audit_dir="$(dirname "$HAP_POST_OPT_AUDIT_OUTPUT_SHA")"
post_opt_audit_report="$post_opt_audit_dir/audit.txt"
post_opt_audit_status="$post_opt_audit_dir/launcher_status.txt"
for evidence in "$post_opt_audit_report" "$post_opt_audit_status"; do
    [[ -s "$evidence" ]] || {
        printf 'missing P8 post-opt audit evidence: %s\n' "$evidence" >&2
        exit 2
    }
done
(cd / && sha256sum -c --strict "$HAP_POST_OPT_AUDIT_OUTPUT_SHA") >/dev/null
for literal in evidence_class=V5_POST_OPT_READ_ONLY_REOPEN \
        "dcp=$HAP_DCP" status=V5_POST_OPT_DCP_AUDIT_PASS \
        attention_query_store_instances=1 \
        attention_postprocess_store_instances=1 \
        attention_postprocess_row_bank_instances=16 \
        attention_context_store_instances=1 attention_query_store_ramb36e2=44 \
        attention_postprocess_store_lut_primitives=19194 \
        attention_postprocess_store_ff_primitives=24580 \
        attention_postprocess_store_ramb36e2=0 \
        attention_postprocess_store_ramb18e2=0 \
        attention_postprocess_store_lutram_primitives=0 \
        attention_postprocess_store_dsp48e2=0 \
        attention_postprocess_store_uram288=0 \
        attention_context_store_ramb36e2=44 \
        attention_context_store_lutram_primitives=0 \
        dsp48e2=5453 uram288=752 ramb36e2=801 ramb18e2=22 \
        post_opt_data_bufg=0 attention_local_store_ok=1 resource_ok=1 \
        checkpoint_written=0 implementation_commands_run=0; do
    [[ "$(grep -Fxc -- "$literal" "$post_opt_audit_report" || true)" -eq 1 ]] || {
        printf 'P8 post-opt audit report gate failed: %s\n' "$literal" >&2
        exit 2
    }
done
for literal in status=PASS final_exit_code=0 vivado_exit_code=0 \
        input_sha_recheck_exit_code=0 input_manifest_sha_match=1 \
        upstream_lineage_sha_recheck_exit_code=0 \
        upstream_lineage_manifest_sha_match=1 \
        upstream_contract_recheck_exit_code=0 audit_gate_exit_code=0 \
        checkpoint_written=0 implementation_commands_run=0; do
    [[ "$(grep -Fxc -- "$literal" "$post_opt_audit_status" || true)" -eq 1 ]] || {
        printf 'P8 post-opt audit launcher gate failed: %s\n' "$literal" >&2
        exit 2
    }
done

mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; fine19 probe not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi

# The probe may open the frozen checkpoint and write text reports only.  The
# shared library also defines the separately consumed pre-place apply proc;
# mirror the proven OOC capacity policy by making that proc unreachable from
# this read-only Tcl and rejecting every mutation token in the probe itself.
readonly_code="$(sed -E '/^[[:space:]]*#/d' "$PROBE_TCL")"
if grep -Eq \
    '(^|[^[:alnum:]_])(synth_design|opt_design|power_opt_design|place_design|phys_opt_design|route_design|link_design|read_xdc|create_pblock|resize_pblock|delete_pblock|add_cells_to_pblock|remove_cells_from_pblock|set_property|reset_property|write_checkpoint|write_bitstream|write_cfgmem|launch_runs|wait_on_run)([^[:alnum:]_]|$)' \
    <<<"$readonly_code"; then
    printf 'fine19 read-only source contains a forbidden command\n' >&2
    exit 2
fi
if grep -Fq 'hap_v5_fine19::apply' <<<"$readonly_code"; then
    printf 'fine19 read-only probe must not call the floorplan apply proc\n' >&2
    exit 2
fi
if grep -Fq 'hap_v5_composite21::apply' <<<"$readonly_code"; then
    printf 'fine19 read-only probe must not call the composite21 apply proc\n' >&2
    exit 2
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
requested="${HAP_FINE19_PROBE_DIR:-$ROOT/vivado/reports/production_v5_fine19_floorplan_probe_$STAMP}"
export HAP_FINE19_PROBE_DIR="$(readlink -m -- "$requested")"
[[ ! -e "$HAP_FINE19_PROBE_DIR" ]] || {
    printf 'fine19 evidence directory exists: %s\n' "$HAP_FINE19_PROBE_DIR" >&2
    exit 2
}
mkdir "$HAP_FINE19_PROBE_DIR"

export HAP_FINE19_SELECTOR_LIB="$SELECTOR_LIB"
export HAP_FINE19_LIB="$FINE_LIB"
export HAP_COMPOSITE21_LIB="$COMPOSITE21_LIB"
export HAP_FINE19_LAUNCHER="$LAUNCHER"
export HAP_FINE19_INPUT_SHA="$HAP_FINE19_PROBE_DIR/INPUT_SHA256SUMS"
inputs=("$HAP_DCP" "$SELECTOR_LIB" "$FINE_LIB" "$COMPOSITE21_LIB" \
    "$PROBE_TCL" "$LAUNCHER" "$HAP_POST_OPT_AUDIT_OUTPUT_SHA" \
    "$HAP_P9_DIAG_OUTPUT_SHA")
printf '%s\n' "${inputs[@]}" > "$HAP_FINE19_PROBE_DIR/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$HAP_FINE19_INPUT_SHA"
export HAP_EXPECTED_DCP_SHA256
HAP_EXPECTED_DCP_SHA256="$(sha256sum -- "$HAP_DCP" | awk '{print $1}')"
export HAP_POST_OPT_AUDIT_OUTPUT_SHA256
HAP_POST_OPT_AUDIT_OUTPUT_SHA256="$(sha256sum -- \
    "$HAP_POST_OPT_AUDIT_OUTPUT_SHA" | awk '{print $1}')"
export HAP_P9_DIAG_OUTPUT_SHA256
HAP_P9_DIAG_OUTPUT_SHA256="$(sha256sum -- \
    "$HAP_P9_DIAG_OUTPUT_SHA" | awk '{print $1}')"
export HAP_FINE19_INPUT_MANIFEST_SHA256
HAP_FINE19_INPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_FINE19_INPUT_SHA" | awk '{print $1}')"
(cd / && sha256sum -c --strict "$HAP_FINE19_INPUT_SHA") \
    > "$HAP_FINE19_PROBE_DIR/input_sha_precheck.txt" 2>&1

cd "$ROOT"
set +e
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/probe_attention_mlp_production_v5_fine19_floorplan.tcl \
    -log "$HAP_FINE19_PROBE_DIR/vivado.log" \
    -journal "$HAP_FINE19_PROBE_DIR/vivado.jou"
vivado_rc=$?
(cd / && sha256sum -c --strict "$HAP_FINE19_INPUT_SHA") \
    > "$HAP_FINE19_PROBE_DIR/input_sha_postcheck.txt" 2>&1
sha_rc=$?
(cd / && sha256sum -c --strict "$HAP_POST_OPT_AUDIT_OUTPUT_SHA") \
    > "$HAP_FINE19_PROBE_DIR/post_opt_audit_postcheck.txt" 2>&1
post_opt_audit_rc=$?
(cd / && sha256sum -c --strict "$HAP_P9_DIAG_OUTPUT_SHA") \
    > "$HAP_FINE19_PROBE_DIR/p9_diag_postcheck.txt" 2>&1
p9_diag_rc=$?
actual_manifest_sha="$(sha256sum -- "$HAP_FINE19_INPUT_SHA" 2>/dev/null | awk '{print $1}')"
manifest_rc=$?
set -e
manifest_match=0
if [[ "$manifest_rc" -eq 0 &&
      "$actual_manifest_sha" == "$HAP_FINE19_INPUT_MANIFEST_SHA256" ]]; then
    manifest_match=1
fi

for file in vivado.log vivado.jou; do
    [[ -e "$HAP_FINE19_PROBE_DIR/$file" ]] ||
        printf 'launcher_note=Vivado did not create %s\n' "$file" \
            > "$HAP_FINE19_PROBE_DIR/$file"
done

summary="$HAP_FINE19_PROBE_DIR/summary.txt"
capacity="$HAP_FINE19_PROBE_DIR/pblock_capacity.txt"
composite_capacity="$HAP_FINE19_PROBE_DIR/composite_capacity.txt"
composite_subgroups="$HAP_FINE19_PROBE_DIR/composite_subgroups.txt"
composite21_capacity="$HAP_FINE19_PROBE_DIR/composite21_pblock_capacity.txt"
gate_rc=125
if [[ "$vivado_rc" -eq 0 && "$sha_rc" -eq 0 && "$post_opt_audit_rc" -eq 0 &&
      "$p9_diag_rc" -eq 0 &&
      "$manifest_match" -eq 1 &&
      -s "$summary" && -s "$capacity" && -s "$composite_capacity" &&
      -s "$composite_subgroups" && -s "$composite21_capacity" ]]; then
    set +e
    gate_rc=0
    for literal in \
        'status=PASS' \
        'stage=V5_PRODUCTION_FINE19_FLOORPLAN_PROBE' \
        'evidence_class=READ_ONLY_POST_OPT_SELECTOR_CAPACITY' \
        'contract_variant=P3_COHORT16_OOC10_19' \
        "input_dcp=$HAP_DCP" \
        "input_dcp_sha256=$HAP_EXPECTED_DCP_SHA256" \
        "input_manifest_sha256=$HAP_FINE19_INPUT_MANIFEST_SHA256" \
        'input_manifest_entries=8' 'provenance_verified=1' \
        "post_opt_audit_manifest=$HAP_POST_OPT_AUDIT_OUTPUT_SHA" \
        "post_opt_audit_manifest_sha256=$HAP_POST_OPT_AUDIT_OUTPUT_SHA256" \
        'post_opt_audit_verified=1' \
        "p9_diag_manifest=$HAP_P9_DIAG_OUTPUT_SHA" \
        "p9_diag_manifest_sha256=$HAP_P9_DIAG_OUTPUT_SHA256" \
        'p9_diag_verified=1' \
        'pblock_spec_count=19' 'member_overlap=0' \
        'projection_primitives=443480' 'projection_dsp48e2=2240' \
        'frontend_primitives=111217' 'frontend_dsp48e2=64' \
        'left_primitives=38909' 'center_primitives=227833' \
        'right_primitives=38909' \
        'center_region0_dsp48e2=272' 'center_region1_dsp48e2=544' \
        'center_region2_dsp48e2=544' 'center_region3_dsp48e2=272' \
        'center_region1_logic_primitives=74509' \
        'center_region1_logic_dsp48e2=0' \
        'center_region1_cols4_5_dsp48e2=272' \
        'center_region1_cols6_7_dsp48e2=272' \
        'region3_input_primitives=2112' \
        'owner_region2_weight_primitives=2048' \
        'nonprojection_center_dsp48e2=85' \
        'projection_exact_cover=1' 'region1_exact_cover=1' \
        'owner_exact_cover=1' 'weight_owner_residency_ok=1' \
        'pblock_member_overlap=0' 'pblock_dsp_coverage=5453' \
        'pblock_uram_coverage=752' 'dsp_coverage_ok=1' \
        'uram_coverage_ok=1' 'slr0_dsp48e2=1862' \
        'slr1_dsp48e2=1781' 'slr2_dsp48e2=1810' \
        'slr0_uram288=224' 'slr1_uram288=224' 'slr2_uram288=304' \
        'resource_distribution_ok=1' 'all_ranges_single_slr=1' \
        'raw_capacity_ok=1' 'canonical_pblock_count_before=0' \
        'canonical_pblock_count_after=0' 'floorplan_mutated=0' \
        'uncovered_dsp48e2=0' 'uncovered_uram288=0' \
        'composite_partition_ok=1' 'subgroup_partition_ok=1' \
        'uncovered_hard_resources_zero=1' \
        'composite21_contract_variant=P9_COHORT16_MLP_CENTRAL_X2X4_21' \
        'composite21_pblock_spec_count=21' \
        'composite21_member_count=1718643' \
        'composite21_unique_member_count=1718643' \
        'composite21_member_overlap=0' \
        'composite21_fine_member_count=1432847' \
        'composite21_mlp_residual_count=285796' \
        'composite21_central_anchor_range=CLOCKREGION_X2Y5:CLOCKREGION_X4Y9' \
        'composite21_central_island_count=197091' \
        'composite21_central_island_dsp=80' \
        'composite21_mlp_remaining_count=88785' \
        'composite21_center_dsp_remaining=5' \
        'composite21_central_partition_ok=1' \
        'composite21_attention_direct_count=71350' \
        'composite21_owner_overlap=0' \
        'composite21_hard_resource_intrusion=0' \
        'composite21_exact_partition=1' \
        'composite21_attention_direct_constrained=0' \
        'composite21_soft_pblock_count=0' \
        'composite21_residual_member_count=192495' \
        'composite21_residual_lut=80958' \
        'composite21_flexible_lut=80958' \
        'composite21_hard_slr0_lut=273205' \
        'composite21_hard_slr1_lut=312771' \
        'composite21_hard_slr2_lut=263359' \
        'composite21_hard_capacity_ok=1' \
        'composite21_outer_90pct_lut_headroom=172780' \
        'composite21_flexible_outer_90pct_fit=1' \
        'composite21_individual_capacity_ok=1' \
        'composite21_aggregate_capacity_ok=1' \
        'composite21_all_ranges_single_slr=1' \
        'composite21_dsp_coverage=5453' \
        'composite21_uram_coverage=752' \
        'composite21_dsp_coverage_ok=1' \
        'composite21_uram_coverage_ok=1' \
        'composite21_slr0_dsp48e2=1862' \
        'composite21_slr1_dsp48e2=1781' \
        'composite21_slr2_dsp48e2=1810' \
        'composite21_slr0_uram288=224' \
        'composite21_slr1_uram288=224' \
        'composite21_slr2_uram288=304' \
        'composite21_resource_distribution_ok=1' \
        'implementation_commands_run=0' 'checkpoint_written=0'; do
        if [[ "$(grep -Fxc -- "$literal" "$summary" 2>/dev/null || true)" -ne 1 ]]; then
            printf 'fine19 summary gate failed: %s\n' "$literal" >&2
            gate_rc=1
        fi
    done
    [[ "$(grep -c '^pblock=' "$capacity" || true)" -eq 19 ]] || gate_rc=1
    [[ "$(grep -c '^collection=' "$composite_capacity" || true)" -eq 5 ]] ||
        gate_rc=1
    [[ "$(grep -c '^candidate=' "$composite_capacity" || true)" -eq 2 ]] ||
        gate_rc=1
    [[ "$(grep -c '^collection=' "$composite_subgroups" || true)" -eq 14 ]] ||
        gate_rc=1
    [[ "$(grep -c '^pblock=' "$composite21_capacity" || true)" -eq 21 ]] ||
        gate_rc=1
    [[ "$(grep -c '^aggregate_slr=' "$composite21_capacity" || true)" -eq 3 ]] ||
        gate_rc=1
    for key in design_pblockable_primitives uncovered_pblockable_primitives \
            uncovered_lut uncovered_ff uncovered_ramb36e2 uncovered_ramb18e2 \
            mlp_uncovered_primitives attention_compute_uncovered_primitives \
            attention_shell_uncovered_primitives support_uncovered_primitives \
            attention0_mlp2_raw_capacity_ok attention2_mlp0_raw_capacity_ok; do
        if ! awk -F= -v key="$key" '
            $1 == key {count++; if ($2 !~ /^[0-9]+$/) bad=1}
            END {exit count == 1 && !bad ? 0 : 1}
        ' "$summary"; then
            printf 'fine19 composite summary gate failed: %s\n' "$key" >&2
            gate_rc=1
        fi
    done
    set -e
fi

final_rc=0
if [[ "$vivado_rc" -ne 0 ]]; then
    final_rc="$vivado_rc"
elif [[ "$sha_rc" -ne 0 || "$post_opt_audit_rc" -ne 0 ||
        "$p9_diag_rc" -ne 0 ||
        "$manifest_match" -ne 1 || "$gate_rc" -ne 0 ]]; then
    final_rc=1
fi
printf '%s\n' \
    "status=$([[ "$final_rc" -eq 0 ]] && printf PASS || printf FAIL)" \
    "final_exit_code=$final_rc" \
    "vivado_exit_code=$vivado_rc" \
    "input_sha_recheck_exit_code=$sha_rc" \
    "post_opt_audit_recheck_exit_code=$post_opt_audit_rc" \
    "p9_diag_recheck_exit_code=$p9_diag_rc" \
    "input_manifest_sha_match=$manifest_match" \
    "probe_gate_exit_code=$gate_rc" \
    'floorplan_mutated=0' 'implementation_commands_run=0' \
    'checkpoint_written=0' > "$HAP_FINE19_PROBE_DIR/launcher_status.txt"

mapfile -d '' outputs < <(find "$HAP_FINE19_PROBE_DIR" -maxdepth 1 \
    -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
sha256sum -- "${outputs[@]}" > "$HAP_FINE19_PROBE_DIR/OUTPUT_SHA256SUMS"
(cd / && sha256sum -c --strict \
    "$HAP_FINE19_PROBE_DIR/OUTPUT_SHA256SUMS")
if [[ "$final_rc" -ne 0 ]]; then
    printf 'V5 fine19 floorplan probe failed; evidence: %s\n' \
        "$HAP_FINE19_PROBE_DIR" >&2
    printf '%s\n' "$HAP_FINE19_PROBE_DIR"
    exit "$final_rc"
fi
cat "$summary"
printf '%s\n' "$HAP_FINE19_PROBE_DIR"
