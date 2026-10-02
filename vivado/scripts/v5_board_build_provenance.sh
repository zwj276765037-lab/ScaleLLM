#!/usr/bin/env bash
# Procedure-only provenance helpers for the V5 full-board bitstream launcher.
# Sourcing this file performs no build, implementation, or filesystem write.

HAP_V5_PROVENANCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

hap_v5_provenance_fail() {
    printf 'V5_BOARD_PROVENANCE_FAIL: %s\n' "$*" >&2
    return 1
}

hap_v5_trim() {
    local value="$1"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    printf '%s' "$value"
}

hap_v5_require_nonempty_file() {
    local path="$1" label="$2"
    [[ -f "$path" && -s "$path" ]] ||
        hap_v5_provenance_fail "missing or empty $label: $path"
}

hap_v5_require_exact_line() {
    local file="$1" literal="$2" label="$3" key count
    hap_v5_require_nonempty_file "$file" "$label" || return 1
    key="${literal%%=*}"
    count="$(grep -Fxc -- "$literal" "$file" || true)"
    [[ "$count" -eq 1 ]] ||
        hap_v5_provenance_fail \
            "$label does not contain exactly one '$literal'" || return 1
    count="$(awk -F= -v key="$key" '$1 == key {count++} END {print count + 0}' \
        "$file")"
    [[ "$count" -eq 1 ]] ||
        hap_v5_provenance_fail \
            "$label field is missing or duplicated: $key" || return 1
}

hap_v5_get_unique_value() {
    local file="$1" key="$2" label="$3" output_name="$4"
    local -n output_ref="$output_name"
    local -a values=()
    hap_v5_require_nonempty_file "$file" "$label" || return 1
    mapfile -t values < <(awk -F= -v key="$key" '$1 == key {
        print substr($0, length(key) + 2)
    }' "$file")
    [[ "${#values[@]}" -eq 1 && -n "${values[0]}" ]] ||
        hap_v5_provenance_fail \
            "$label field is missing, empty, or duplicated: $key" ||
        return 1
    output_ref="${values[0]}"
}

hap_v5_read_path_list() {
    local list_file="$1" expected_count="$2" output_name="$3"
    local raw path canonical
    local -n output_ref="$output_name"
    local -A seen=()
    output_ref=()
    hap_v5_require_nonempty_file "$list_file" "path list" || return 1
    while IFS= read -r raw || [[ -n "$raw" ]]; do
        path="$(hap_v5_trim "$raw")"
        [[ -n "$path" ]] ||
            hap_v5_provenance_fail "blank row in path list: $list_file" ||
            return 1
        [[ "$path" == /* ]] ||
            hap_v5_provenance_fail "non-absolute path-list row: $path" ||
            return 1
        canonical="$(readlink -e -- "$path")" ||
            hap_v5_provenance_fail "path-list input does not exist: $path" ||
            return 1
        [[ "$canonical" == "$path" ]] ||
            hap_v5_provenance_fail \
                "path-list input is not canonical: $path -> $canonical" ||
            return 1
        [[ -f "$path" && -s "$path" ]] ||
            hap_v5_provenance_fail "path-list input is empty: $path" ||
            return 1
        [[ -z "${seen[$path]:-}" ]] ||
            hap_v5_provenance_fail "duplicate path-list input: $path" ||
            return 1
        seen[$path]=1
        output_ref+=("$path")
    done < "$list_file"
    [[ "${#output_ref[@]}" -eq "$expected_count" ]] ||
        hap_v5_provenance_fail \
            "path-list cardinality mismatch: expected=$expected_count actual=${#output_ref[@]} file=$list_file" ||
        return 1
}

hap_v5_read_sha_manifest_paths() {
    local manifest="$1" expected_count="$2" output_name="$3"
    local raw hash path canonical
    local -n output_ref="$output_name"
    local -A seen=()
    output_ref=()
    hap_v5_require_nonempty_file "$manifest" "SHA256 manifest" || return 1
    while IFS= read -r raw || [[ -n "$raw" ]]; do
        [[ "$raw" =~ ^([0-9a-f]{64})[[:space:]]+(\*?/.+)$ ]] ||
            hap_v5_provenance_fail \
                "malformed SHA256 manifest row: $manifest: $raw" ||
            return 1
        hash="${BASH_REMATCH[1]}"
        path="${BASH_REMATCH[2]}"
        path="${path#\*}"
        canonical="$(readlink -e -- "$path")" ||
            hap_v5_provenance_fail \
                "SHA256 manifest input does not exist: $path" ||
            return 1
        [[ "$canonical" == "$path" ]] ||
            hap_v5_provenance_fail \
                "SHA256 manifest path is not canonical: $path -> $canonical" ||
            return 1
        [[ -f "$path" && -s "$path" ]] ||
            hap_v5_provenance_fail \
                "SHA256 manifest input is empty: $path" ||
            return 1
        [[ -z "${seen[$path]:-}" ]] ||
            hap_v5_provenance_fail \
                "duplicate SHA256 manifest path: $path" ||
            return 1
        [[ "$hash" == "$(sha256sum -- "$path" | awk '{print $1}')" ]] ||
            hap_v5_provenance_fail "SHA256 mismatch: $path" || return 1
        seen[$path]=1
        output_ref+=("$path")
    done < "$manifest"
    [[ "${#output_ref[@]}" -eq "$expected_count" ]] ||
        hap_v5_provenance_fail \
            "SHA256 manifest cardinality mismatch: expected=$expected_count actual=${#output_ref[@]} file=$manifest" ||
        return 1
    (cd / && sha256sum -c --strict "$manifest" >/dev/null) ||
        hap_v5_provenance_fail "sha256sum -c rejected: $manifest" ||
        return 1
}

hap_v5_read_sha_manifest_paths_dynamic() {
    local manifest="$1" output_name="$2"
    local count
    hap_v5_require_nonempty_file "$manifest" "dynamic SHA256 manifest" ||
        return 1
    count="$(wc -l < "$manifest")"
    [[ "$count" =~ ^[1-9][0-9]*$ ]] ||
        hap_v5_provenance_fail \
            "dynamic SHA256 manifest has no nonblank rows: $manifest" ||
        return 1
    hap_v5_read_sha_manifest_paths "$manifest" "$count" "$output_name"
}

hap_v5_require_same_path_set() {
    local left_name="$1" right_name="$2" label="$3" index
    local -n left_ref="$left_name"
    local -n right_ref="$right_name"
    local -a left_sorted right_sorted
    mapfile -t left_sorted < <(printf '%s\n' "${left_ref[@]}" | LC_ALL=C sort)
    mapfile -t right_sorted < <(printf '%s\n' "${right_ref[@]}" | LC_ALL=C sort)
    [[ "${#left_sorted[@]}" -eq "${#right_sorted[@]}" ]] ||
        hap_v5_provenance_fail \
            "$label set cardinality mismatch: ${#left_sorted[@]}/${#right_sorted[@]}" ||
        return 1
    for index in "${!left_sorted[@]}"; do
        [[ "${left_sorted[$index]}" == "${right_sorted[$index]}" ]] ||
            hap_v5_provenance_fail \
                "$label set mismatch: ${left_sorted[$index]} != ${right_sorted[$index]}" ||
            return 1
    done
}

hap_v5_require_path_member() {
    local paths_name="$1" required="$2" label="$3" path count=0
    local -n paths_ref="$paths_name"
    for path in "${paths_ref[@]}"; do
        [[ "$path" == "$required" ]] && ((count += 1))
    done
    [[ "$count" -eq 1 ]] ||
        hap_v5_provenance_fail \
            "$label required path missing or duplicated: $required" ||
        return 1
}

_hap_v5_expand_manifest_walk() {
    local root="$1" manifest="$2" raw line path
    manifest="$(readlink -e -- "$manifest")" ||
        hap_v5_provenance_fail "source manifest does not exist: $manifest" ||
        return 1
    [[ "$manifest" == "$root"/* ]] ||
        hap_v5_provenance_fail "source manifest escapes project root: $manifest" ||
        return 1
    [[ -f "$manifest" && -s "$manifest" ]] ||
        hap_v5_provenance_fail "source manifest is empty: $manifest" ||
        return 1
    [[ -z "${HAP_V5_SEEN_MANIFESTS[$manifest]:-}" ]] || return 0
    HAP_V5_SEEN_MANIFESTS[$manifest]=1
    HAP_V5_EXPANDED_MANIFESTS+=("$manifest")

    while IFS= read -r raw || [[ -n "$raw" ]]; do
        line="${raw%%#*}"
        line="$(hap_v5_trim "$line")"
        [[ -n "$line" ]] || continue
        [[ "$line" != /* ]] ||
            hap_v5_provenance_fail \
                "absolute source-manifest entry rejected: $line" ||
            return 1
        path="$(readlink -e -- "$root/$line")" ||
            hap_v5_provenance_fail \
                "source-manifest entry does not exist: $line" ||
            return 1
        [[ "$path" == "$root"/* ]] ||
            hap_v5_provenance_fail \
                "source-manifest entry escapes project root: $line" ||
            return 1
        [[ -f "$path" && -s "$path" ]] ||
            hap_v5_provenance_fail \
                "source-manifest entry is empty: $line" ||
            return 1
        if [[ "$line" == *.list ]]; then
            _hap_v5_expand_manifest_walk "$root" "$path" || return 1
        else
            [[ -z "${HAP_V5_SEEN_SOURCES[$path]:-}" ]] ||
                hap_v5_provenance_fail \
                    "duplicate source in recursive closure: $line" ||
                return 1
            HAP_V5_SEEN_SOURCES[$path]=1
            HAP_V5_EXPANDED_SOURCES+=("$path")
        fi
    done < "$manifest"
}

hap_v5_expand_source_manifest() {
    local root="$1" manifest="$2" manifests_name="$3"
    local sources_name="$4" closure_name="$5"
    local -n manifests_ref="$manifests_name"
    local -n sources_ref="$sources_name"
    local -n closure_ref="$closure_name"
    root="$(readlink -e -- "$root")" ||
        hap_v5_provenance_fail "project root does not exist: $root" ||
        return 1
    declare -gA HAP_V5_SEEN_MANIFESTS=()
    declare -gA HAP_V5_SEEN_SOURCES=()
    declare -ga HAP_V5_EXPANDED_MANIFESTS=()
    declare -ga HAP_V5_EXPANDED_SOURCES=()
    _hap_v5_expand_manifest_walk "$root" "$manifest" || return 1
    mapfile -t manifests_ref < <(printf '%s\n' \
        "${HAP_V5_EXPANDED_MANIFESTS[@]}" | LC_ALL=C sort)
    mapfile -t sources_ref < <(printf '%s\n' \
        "${HAP_V5_EXPANDED_SOURCES[@]}" | LC_ALL=C sort)
    mapfile -t closure_ref < <(printf '%s\n' \
        "${manifests_ref[@]}" "${sources_ref[@]}" | LC_ALL=C sort)
    unset HAP_V5_SEEN_MANIFESTS HAP_V5_SEEN_SOURCES
    unset HAP_V5_EXPANDED_MANIFESTS HAP_V5_EXPANDED_SOURCES
}

hap_v5_route_required_output_names() {
    printf '%s\n' \
        summary.txt selectors_input.txt selectors_post_route.txt \
        attention_geometry_input.txt attention_geometry_post_route.txt \
        attention_geometry_placement_input.txt \
        attention_geometry_placement_post_route.txt \
        base_pblocks_input.txt base_pblocks_post_route.txt \
        p5_input_plan_input.txt p5_input_plan_post_route.txt \
        p5_input_pblocks_input.txt p5_input_pblocks_post_route.txt \
        p9_postprocess_plan_input.txt p9_postprocess_plan_post_route.txt \
        p9_postprocess_pblocks_input.txt \
        p9_postprocess_pblocks_post_route.txt \
        p9_quantizer3_plan_input.txt p9_quantizer3_plan_post_route.txt \
        p9_quantizer3_pblock_input.txt p9_quantizer3_pblock_post_route.txt \
        p14_region2_relief_plan_input.txt \
        p14_region2_relief_plan_post_route.txt \
        p14_region2_relief_pblock_input.txt \
        p14_region2_relief_pblock_post_route.txt \
        p8_parent_ingress_boundary_input.txt \
        p8_parent_ingress_boundary_post_route.txt \
        architecture_boundaries_input.txt \
        architecture_boundaries_post_route.txt \
        post_phys_opt.dcp post_route.dcp post_route_diagnostic.dcp \
        utilization_post_route.rpt utilization_hier_post_route.rpt \
        utilization_slr_post_route.rpt timing_post_phys_opt.rpt \
        timing_post_route.rpt timing_setup_worst100_post_route.rpt \
        timing_hold_worst100_post_route.rpt route_status_post_route.rpt \
        drc_post_route.rpt cdc_post_route.rpt \
        clock_interaction_post_route.rpt clock_utilization_post_route.rpt \
        congestion_post_route.rpt exceptions_coverage_post_route.rpt \
        vivado.log vivado.jou launcher_status.txt INPUT_FILES \
        INPUT_SHA256SUMS
}

hap_v5_route_required_summary_lines() {
    local required_total_dsp="${expected_total_dsp:-5453}"
    local required_slr1_dsp="${expected_slr1_dsp:-1781}"
    local required_route_input_count="${expected_route_input_count:-33}"
    printf '%s\n' \
        status=V5_P10_P14_PRODUCTION_OOC_POST_ROUTE_PASS \
        evidence_class=P14_PRODUCTION_CORE_OOC_POST_ROUTE \
        part=xcvu9p-flga2104-2L-e \
        top=hap_attention_mlp_production_core \
        jobs=32 \
        core_clock_mhz=100 ddr0_clock_mhz=300 ddr1_clock_mhz=300 \
        input_sha_manifests_verified=1 \
        "route_input_manifest_entries=$required_route_input_count" \
        base_contract_variant=P2_COHORT16_COL2_12_2 \
        p5_contract=P5_INPUT_HALF_LOCAL_8_8 \
        p9_postprocess_contract=P9_POSTPROCESS_SPLIT_6_4_6 \
        p9_quantizer3_contract=P9_SWIGLU_QUANTIZER3_CR_X2Y5_X3Y6 \
        p14_region2_relief_contract=P14_ATTN_REGION2_SHARED_X0_X2 \
        history2_repack_instances=2 generic_repack_instances=0 \
        projection_weight_capture_ok=1 mlp_kernel_dsp48e2=3072 \
        "dsp48e2=$required_total_dsp" uram288=752 \
        metadata_local_write_protected_ff=970 \
        mlp_capture_leaf_instances=1632 mlp_capture_leaf_lut1=1632 \
        pblock_count=26 canonical_pblock_count=11 \
        geometry_pblock_count=10 p5_added_pblock_count=2 \
        p9_postprocess_added_pblock_count=2 \
        p9_quantizer3_added_pblock_count=1 \
        p14_region2_relief_added_pblock_count=0 \
        "pblock_dsp_coverage=$required_total_dsp" \
        pblock_uram_coverage=752 pblock_wrong_slr=0 \
        p5_center_wrong_slr=0 p5_outer_wrong_slr=0 \
        p9_postprocess_center_wrong_slr=0 \
        p9_postprocess_outer_wrong_slr=0 \
        p9_slr0_row_primitives=16044 \
        p9_center_row_primitives=10696 \
        p9_slr2_row_primitives=16044 \
        p9_quantizer3_grid_range=CLOCKREGION_X2Y5:CLOCKREGION_X3Y6 \
        p9_quantizer3_wrong_region=0 p9_quantizer3_unplaced=0 \
        p14_region2_relief_base_range=CLOCKREGION_X0Y5:CLOCKREGION_X1Y9 \
        p14_region2_relief_range=CLOCKREGION_X2Y5:CLOCKREGION_X2Y9 \
        p14_region2_expected_range=CLOCKREGION_X0Y5:CLOCKREGION_X2Y9 \
        p14_region2_relief_wrong=0 p14_region2_relief_unplaced=0 \
        parent_head_ff=6560 parent_tail_ff=6560 parent_count_ff=2 \
        parent_count_replica_equivalence_ok=1 parent_pointer_ff=0 \
        local_clear_shared_upstream_ready_paths=0 \
        branch_credit_shared_upstream_ready_paths=0 \
        local_clear_gate_compute_ready_paths=0 \
        branch_credit_gate_compute_ready_paths=0 \
        local_clear_down_compute_ready_paths=0 \
        branch_credit_down_compute_ready_paths=0 \
        local_clear_input_cache_ready_paths=0 \
        branch_credit_input_cache_ready_paths=0 \
        completed_u8_ff=4096 completed_meta_ff=352 \
        input_capture_ff=12288 input_capture_controls=48 \
        slr0_dsp48e2=1862 "slr1_dsp48e2=$required_slr1_dsp" \
        slr2_dsp48e2=1810 \
        slr0_uram288=224 slr1_uram288=224 slr2_uram288=304 \
        unplaced_primitives=0 wrong_slr_primitives=0 \
        pre_route_compute_missing_after=0 final_compute_missing_after=0 \
        route_error_nets=0 explicit_gap_nets=0 unrouted_nets=0 \
        some_unrouted_pin_nets=0 resource_conflict_nets=0 \
        antenna_island_nets=0 route_status_partial=0 \
        route_status_conflicts=0 route_clean=1 drc_errors=0 \
        drc_report_error_rows=0 timing_coverage_ok=1 cdc_critical=0 \
        data_bufg=0 false_path_exception_rows=0 \
        datapath_only_exception_rows=0 \
        congestion_level6_or_higher_windows=0 \
        operation_ok=1 report_ok=1 resource_ok=1 physical_ok=1 \
        architecture_boundary_ok=1 timing_ok=1 policy_ok=1 \
        route_eligible=1 checkpoint_written=1 bitstream_generated=0
}

hap_v5_route_required_boundary_lines() {
    local status="$1"
    printf '%s\n' \
        mlp_local_clear_ff=2 mlp_local_clear_protected_ff=2 \
        branch0_local_clear_ff=1 branch1_local_clear_ff=1 \
        'branch0_local_clear_slr=1 0 0' \
        'branch1_local_clear_slr=0 0 1' \
        mlp_local_clear_wrong_slr=0 mlp_central_clear_ff=1 \
        mlp_central_clear_branch_endpoints=2 \
        mlp_central_clear_direct_branch_state=0 \
        swiglu_local_clear_ff=8 swiglu_local_clear_protected_ff=8 \
        swiglu_control_clear_ff=1 swiglu_hadamard_clear_ff=1 \
        swiglu_quantizer_clear_ff=4 swiglu_row_clear_ff=2 \
        swiglu_direct_clear_bypass_state=0 \
        metadata_leaf_instances=4 metadata_local_wr_en_ff=4 \
        metadata_local_wr_addr_ff=70 metadata_local_wr_data_ff=896 \
        metadata_local_write_protected_ff=970 \
        'metadata_local_write_leaf_counts=243 243 242 242' \
        'metadata_local_write_leaf_slr_counts={243 0 0} {0 0 243} {0 242 0} {0 242 0}' \
        metadata_local_write_wrong_slr=0 \
        mlp_capture_leaf_instances=1632 mlp_capture_leaf_lut1=1632 \
        'mlp_capture_leaf_branch_instances=816 816' \
        'mlp_capture_leaf_branch_lut1=816 816' \
        'mlp_capture_leaf_branch_slr_counts={816 0 0} {0 0 816}' \
        mlp_capture_leaf_wrong_slr=0 \
        "status=$status"
}

hap_v5_route_required_selector_lines() {
    local required_total_dsp="${expected_total_dsp:-5453}"
    printf '%s\n' status=V5_P14_ROUTE_FINAL_SELECTORS_PASS \
        contract_variant=P2_COHORT16_COL2_12_2 \
        "total_dsp=$required_total_dsp" total_uram=752 \
        projection_weight_capture_audited=1 projection_weight_capture_ok=1 \
        raw_weight_push_loads=37 weight_data_capture_nets=32 \
        weight_data_capture_min=256 weight_data_capture_max=256 \
        weight_meta_capture_nets=2 weight_meta_capture_min=256 \
        weight_meta_capture_max=256 weight_group_capture_nets=2 \
        weight_group_capture_min=7 weight_group_capture_max=7 \
        outer0_dsp=1538 outer2_dsp=1538 outer0_ramb36=102 \
        outer2_ramb36=102
}

hap_v5_route_required_geometry_lines() {
    local rows0_3="${expected_region2_rows0_3_primitives:-26800}"
    local rows4_7="${expected_region2_rows4_7_primitives:-26800}"
    local residual="${expected_region2_residual_primitives:-15199}"
    printf '%s\n' status=V5_P14_ROUTE_FINAL_GEOMETRY_PASS \
        region0_input_primitives=3136 region3_input_primitives=2112 \
        owner_region2_weight_primitives=2048 \
        center_region1_bisect_exact_cover=1 \
        center_region1_dsp_stripe_exact_cover=1 \
        "center_region2_rows0_3_primitives=$rows0_3" \
        center_region2_rows0_3_primitives_dsp48e2=272 \
        "center_region2_rows4_7_primitives=$rows4_7" \
        center_region2_rows4_7_primitives_dsp48e2=272 \
        "center_region2_residual_primitives=$residual" \
        center_region2_residual_primitives_dsp48e2=0 \
        center_region2_row_exact_cover=1 \
        owner_region0_input_exact_cover=1 owner_region3_input_exact_cover=1 \
        owner_region2_weight_exact_cover=1 \
        region3_weight_owner_residency_ok=1
}

hap_v5_route_required_geometry_placement_lines() {
    printf '%s\n' status=V5_P14_ROUTE_FINAL_GEOMETRY_PLACEMENT_PASS \
        left_wrong=0 center_wrong=0 right_wrong=0 owner_wrong=0 \
        frontend_wrong=0 wrong_total=0 unplaced_total=0 \
        'slr_dsp=272 1696 272' ok=1
}

hap_v5_route_required_base_pblock_lines() {
    local required_total_dsp="${expected_total_dsp:-5453}"
    printf '%s\n' status=V5_P14_ROUTE_FINAL_BASE_PBLOCKS_PASS ok=1 \
        require_placed=1 contract_variant=P2_COHORT16_COL2_12_2 \
        pblock_count=11 "dsp_coverage=$required_total_dsp" \
        uram_coverage=752 placed_wrong=0 \
        pb_v5_mlp_branch_slr0_dsp=1538 \
        pb_v5_mlp_branch_slr0_ramb36=102 \
        pb_v5_mlp_branch_slr2_dsp=1538 \
        pb_v5_mlp_branch_slr2_ramb36=102 \
        pb_v5_attention_row_kv_cache_slr0_dsp=52 \
        pb_v5_attention_row_kv_cache_slr0_uram=0 \
        pb_v5_attention_row_kv_cache_slr0_ramb36=88 \
        pb_v5_attention_row_kv_cache_slr0_ramb18=2
}

hap_v5_route_required_input_plan_lines() {
    printf '%s\n' status=V5_P14_ROUTE_FINAL_INPUT_PLAN_PASS \
        contract=P5_INPUT_HALF_LOCAL_8_8 quantizer_count=4 cache_count=2 \
        hadamard_count=1 completed_u8_ff=4096 completed_meta_ff=352 \
        input_capture_ff=12288 capture_leaf_count=48 \
        center_canonical_overlap=8
}

hap_v5_route_required_input_pblock_lines() {
    printf '%s\n' status=V5_P14_ROUTE_FINAL_INPUT_PBLOCKS_PASS ok=1 \
        require_placed=1 pblock_count=2 center_missing=0 \
        center_outer_overlap=0 center_wrong=0 outer_wrong=0 \
        half0_target=0 half0_missing=0 half0_wrong=0 \
        half1_target=2 half1_missing=0 half1_wrong=0
}

hap_v5_route_required_p9_postprocess_plan_lines() {
    printf '%s\n' status=V5_P14_ROUTE_FINAL_POSTPROCESS_PLAN_PASS \
        contract=P9_POSTPROCESS_SPLIT_6_4_6 row_bank_count=16 \
        all_row_primitives=42784 slr0_row_primitives=16044 \
        center_row_primitives=10696 slr2_row_primitives=16044 \
        per_row_primitives=2674 per_row_lut=994 per_row_ff=1536
}

hap_v5_route_required_p9_postprocess_pblock_lines() {
    printf '%s\n' status=V5_P14_ROUTE_FINAL_POSTPROCESS_PBLOCKS_PASS ok=1 \
        require_placed=1 pblock_count=2 center_missing=0 \
        center_outer_overlap=0 center_wrong=0 outer_wrong=0 \
        slr0_target=0 slr0_missing=0 slr0_wrong=0 \
        slr2_target=2 slr2_missing=0 slr2_wrong=0
}

hap_v5_route_required_p9_quantizer3_plan_lines() {
    local primitive_count="${1:-11178}"
    printf '%s\n' status=V5_P14_ROUTE_FINAL_QUANTIZER3_PLAN_PASS \
        contract=P9_SWIGLU_QUANTIZER3_CR_X2Y5_X3Y6 \
        "primitive_count=$primitive_count" \
        grid_range=CLOCKREGION_X2Y5:CLOCKREGION_X3Y6
}

hap_v5_route_required_p9_quantizer3_pblock_lines() {
    local primitive_count="${1:-11178}"
    printf '%s\n' status=V5_P14_ROUTE_FINAL_QUANTIZER3_PBLOCK_PASS ok=1 \
        require_placed=1 contract=P9_SWIGLU_QUANTIZER3_CR_X2Y5_X3Y6 \
        "expected=$primitive_count" "members=$primitive_count" \
        missing=0 extras=0 wrong=0 unplaced=0
}

hap_v5_route_required_p14_relief_plan_lines() {
    local primitive_count="${1:-68799}"
    printf '%s\n' status=V5_P14_ROUTE_FINAL_REGION2_RELIEF_PLAN_PASS \
        contract=P14_ATTN_REGION2_SHARED_X0_X2 \
        "primitive_count=$primitive_count" \
        base_range=CLOCKREGION_X0Y5:CLOCKREGION_X1Y9 \
        relief_range=CLOCKREGION_X2Y5:CLOCKREGION_X2Y9 \
        expected_range=CLOCKREGION_X0Y5:CLOCKREGION_X2Y9
}

hap_v5_route_required_p14_relief_pblock_lines() {
    local primitive_count="${1:-68799}"
    printf '%s\n' status=V5_P14_ROUTE_FINAL_REGION2_RELIEF_PBLOCK_PASS \
        ok=1 contract=P14_ATTN_REGION2_SHARED_X0_X2 require_placed=1 \
        "primitive_count=$primitive_count" missing=0 wrong=0 unplaced=0
}

hap_v5_route_required_parent_lines() {
    local status="$1"
    printf '%s\n' status="$status" ok=1 parent_head_ff=6560 \
        parent_tail_ff=6560 parent_count_ff=2 \
        parent_count_replica_equivalence_ok=1 parent_pointer_ff=0 \
        local_clear_shared_upstream_ready_paths=0 \
        branch_credit_shared_upstream_ready_paths=0 \
        local_clear_gate_compute_ready_paths=0 \
        branch_credit_gate_compute_ready_paths=0 \
        local_clear_down_compute_ready_paths=0 \
        branch_credit_down_compute_ready_paths=0 \
        local_clear_input_cache_ready_paths=0 \
        branch_credit_input_cache_ready_paths=0
}

hap_v5_route_required_launcher_lines() {
    printf '%s\n' status=PASS final_exit_code=0 vivado_exit_code=0 \
        vivado_invoked=1 \
        route_input_sha_postcheck=1 place_input_sha_postcheck=1 \
        place_output_sha_postcheck=1 place_input_manifest_sha_match=1 \
        place_output_manifest_sha_match=1 \
        route_input_manifest_sha_match=1 bitstream_generated=0
}

hap_v5_verify_ooc_route_artifact() {
    local requested="$1" route_dir summary selectors geometry
    local geometry_placement base_pblocks input_plan input_pblocks
    local postprocess_plan postprocess_pblocks quantizer3_plan
    local quantizer3_pblock relief_plan relief_pblock parent_input parent_final
    local launcher_status
    local input_boundaries post_boundaries
    local input_files input_sha output_sha literal name count
    local input_dcp input_place_summary input_dcp_hash actual_input_dcp_hash
    local place_input_manifest_sha summary_place_input_manifest_sha
    local place_output_manifest_sha summary_place_output_manifest_sha
    local route_input_manifest_sha summary_route_input_manifest_sha
    local place_dir route_variant place_input_count quantizer3_primitives
    local expected_total_dsp expected_slr1_dsp expected_route_input_count
    local relief_primitives p16_post_opt_summary p16_post_opt_summary_sha
    local region2_signature_source actual_p16_post_opt_summary_sha
    local expected_region2_rows0_3_primitives=26800
    local expected_region2_rows4_7_primitives=26800
    local expected_region2_residual_primitives=15199
    local expected_region2_total_primitives=68799
    local region2_partition_sum
    local geometry_lib quantizer3_lib relief_lib
    local -a expected_outputs output_manifest_paths route_input_paths
    local -a current_route_outputs
    local -a input_manifest_paths expected_inputs place_input_paths
    local -a place_output_paths expected_place_output_paths
    local -a route_variant_rows=()
    local place_output_manifest_entries summary_place_output_manifest_entries
    route_dir="$(readlink -e -- "$requested")" ||
        hap_v5_provenance_fail \
            "OOC route artifact directory does not exist: $requested" ||
        return 1
    [[ -d "$route_dir" ]] ||
        hap_v5_provenance_fail \
            "OOC route artifact is not a directory: $route_dir" ||
        return 1

    summary="$route_dir/summary.txt"
    selectors="$route_dir/selectors_post_route.txt"
    geometry="$route_dir/attention_geometry_post_route.txt"
    geometry_placement="$route_dir/attention_geometry_placement_post_route.txt"
    base_pblocks="$route_dir/base_pblocks_post_route.txt"
    input_plan="$route_dir/p5_input_plan_post_route.txt"
    input_pblocks="$route_dir/p5_input_pblocks_post_route.txt"
    postprocess_plan="$route_dir/p9_postprocess_plan_post_route.txt"
    postprocess_pblocks="$route_dir/p9_postprocess_pblocks_post_route.txt"
    quantizer3_plan="$route_dir/p9_quantizer3_plan_post_route.txt"
    quantizer3_pblock="$route_dir/p9_quantizer3_pblock_post_route.txt"
    relief_plan="$route_dir/p14_region2_relief_plan_post_route.txt"
    relief_pblock="$route_dir/p14_region2_relief_pblock_post_route.txt"
    parent_input="$route_dir/p8_parent_ingress_boundary_input.txt"
    parent_final="$route_dir/p8_parent_ingress_boundary_post_route.txt"
    input_boundaries="$route_dir/architecture_boundaries_input.txt"
    post_boundaries="$route_dir/architecture_boundaries_post_route.txt"
    launcher_status="$route_dir/launcher_status.txt"
    input_files="$route_dir/INPUT_FILES"
    input_sha="$route_dir/INPUT_SHA256SUMS"
    output_sha="$route_dir/OUTPUT_SHA256SUMS"
    for literal in "$summary" "$selectors" "$geometry" \
            "$geometry_placement" "$base_pblocks" "$input_plan" \
            "$input_pblocks" "$postprocess_plan" "$postprocess_pblocks" \
            "$quantizer3_plan" "$quantizer3_pblock" \
            "$relief_plan" "$relief_pblock" "$parent_input" "$parent_final" \
            "$input_boundaries" \
            "$post_boundaries" "$launcher_status" \
            "$input_files" "$input_sha" "$output_sha" \
            "$route_dir/post_route.dcp"; do
        hap_v5_require_nonempty_file "$literal" \
            "OOC route authorization evidence" || return 1
    done

    mapfile -t route_variant_rows < <(awk -F= '$1 == "rtl_variant" {
        print substr($0, length($1) + 2)
    }' "$summary")
    if [[ "${#route_variant_rows[@]}" -eq 0 ]]; then
        route_variant=P14_LEGACY
    elif [[ "${#route_variant_rows[@]}" -eq 1 &&
            -n "${route_variant_rows[0]}" ]]; then
        route_variant="${route_variant_rows[0]}"
    else
        hap_v5_provenance_fail \
            "OOC route rtl_variant is empty or duplicated" || return 1
    fi
    case "$route_variant" in
        P14_LEGACY)
            place_input_count=14
            expected_route_input_count=33
            expected_total_dsp=5453
            expected_slr1_dsp=1781
            geometry_lib="$HAP_V5_PROVENANCE_ROOT/vivado/scripts/projection_core16x16_w8_reuse_ooc_floorplan.tcl"
            quantizer3_lib="$HAP_V5_PROVENANCE_ROOT/vivado/scripts/v5_production_p9_quantizer3_locality_floorplan.tcl"
            relief_lib="$HAP_V5_PROVENANCE_ROOT/vivado/scripts/v5_production_p14_region2_x2_relief_floorplan.tcl"
            ;;
        P16_NOCLIP)
            place_input_count=20
            expected_route_input_count=39
            expected_total_dsp=5449
            expected_slr1_dsp=1777
            geometry_lib="$HAP_V5_PROVENANCE_ROOT/vivado/scripts/projection_core16x16_w8_reuse_ooc_p16_bound_floorplan.tcl"
            quantizer3_lib="$HAP_V5_PROVENANCE_ROOT/vivado/scripts/v5_production_p16_noclip_quantizer3_locality_floorplan.tcl"
            relief_lib="$HAP_V5_PROVENANCE_ROOT/vivado/scripts/v5_production_p16_noclip_region2_x2_relief_floorplan.tcl"
            ;;
        *)
            hap_v5_provenance_fail \
                "unsupported OOC route rtl_variant: $route_variant" || return 1
            ;;
    esac
    hap_v5_get_unique_value "$summary" p9_quantizer3_primitives \
        "OOC route summary" quantizer3_primitives || return 1
    hap_v5_get_unique_value "$summary" p14_region2_relief_primitives \
        "OOC route summary" relief_primitives || return 1
    [[ "$quantizer3_primitives" =~ ^[1-9][0-9]*$ &&
       "$relief_primitives" =~ ^[1-9][0-9]*$ ]] ||
        hap_v5_provenance_fail \
            "OOC route dynamic primitive counts are malformed" || return 1
    if [[ "$route_variant" == P14_LEGACY ]]; then
        [[ "$quantizer3_primitives" -eq 11178 &&
           "$relief_primitives" -eq 68799 ]] ||
            hap_v5_provenance_fail \
                "legacy OOC route primitive identity changed" || return 1
    else
        hap_v5_get_unique_value "$summary" p16_post_opt_summary \
            "P16 no-clip OOC route summary" p16_post_opt_summary || return 1
        hap_v5_get_unique_value "$summary" p16_post_opt_summary_sha256 \
            "P16 no-clip OOC route summary" \
            p16_post_opt_summary_sha || return 1
        hap_v5_get_unique_value "$summary" region2_signature_source \
            "P16 no-clip OOC route summary" \
            region2_signature_source || return 1
        hap_v5_get_unique_value "$summary" p16_production_region2_summary \
            "P16 no-clip OOC route summary" \
            p16_production_region2_summary || return 1
        hap_v5_get_unique_value "$summary" \
            p16_production_region2_summary_sha256 \
            "P16 no-clip OOC route summary" \
            p16_production_region2_summary_sha || return 1
        hap_v5_get_unique_value "$summary" p16_production_dcp_sha256 \
            "P16 no-clip OOC route summary" \
            p16_production_dcp_sha || return 1
        p16_post_opt_summary="$(readlink -e -- "$p16_post_opt_summary")" ||
            return 1
        p16_production_region2_summary="$(readlink -e -- \
            "$p16_production_region2_summary")" || return 1
        actual_p16_post_opt_summary_sha="$(sha256sum -- \
            "$p16_post_opt_summary" | awk '{print $1}')"
        [[ "$p16_post_opt_summary_sha" =~ ^[0-9a-f]{64}$ &&
           "$actual_p16_post_opt_summary_sha" == \
                "$p16_post_opt_summary_sha" &&
           "$p16_production_region2_summary_sha" =~ ^[0-9a-f]{64}$ &&
           "$p16_production_dcp_sha" =~ ^[0-9a-f]{64}$ &&
           "$(sha256sum -- "$p16_production_region2_summary" | awk '{print $1}')" == \
                "$p16_production_region2_summary_sha" &&
           "$region2_signature_source" == \
                "P16_PRODUCTION_POST_OPT_SHA256:$p16_production_region2_summary_sha" ]] ||
            hap_v5_provenance_fail \
                "P16 no-clip OOC route signature binding failed" || return 1
        for literal in stage=P16_100MHZ_POST_OPT_STRUCTURE_PROBE \
                part=xcvu9p-flga2104-2L-e jobs=32 clock_mhz=100 \
                attention_lane_instances=128 \
                local_dual_accumulator_instances=6 \
                local_accumulator_contexts=12 dut_dsp48e2=2240 \
                array_dsp48e2=2176 frontend_dsp48e2=64 \
                frontend_hadamard_dsp48e2=64 \
                frontend_quantizer_dsp48e2=0 region2_dsp48e2=544 \
                region2_rows0_3_dsp48e2=272 \
                region2_rows4_7_dsp48e2=272 \
                region2_residual_dsp48e2=0 drc_errors=0 status=PASS; do
            hap_v5_require_exact_line "$p16_post_opt_summary" "$literal" \
                "P16 no-clip post-opt summary" || return 1
        done
        hap_v5_get_unique_value "$p16_production_region2_summary" input_dcp \
            "P16 production region2 summary" production_input_dcp || return 1
        hap_v5_get_unique_value "$p16_production_region2_summary" \
            input_dcp_sha256 "P16 production region2 summary" \
            production_input_dcp_sha || return 1
        production_input_dcp="$(readlink -e -- "$production_input_dcp")" ||
            return 1
        [[ "$production_input_dcp_sha" == "$p16_production_dcp_sha" &&
           "$(sha256sum -- "$production_input_dcp" | awk '{print $1}')" == \
                "$p16_production_dcp_sha" ]] ||
            hap_v5_provenance_fail \
                "P16 production region2 DCP binding failed" || return 1
        for literal in stage=P16_PRODUCTION_POST_OPT_REGION2_SIGNATURE_PROBE \
                part=xcvu9p-flga2104-2L-e \
                top=hap_attention_mlp_production_core jobs=32 \
                projection_instances=1 attention_lane_instances=128 \
                local_dual_accumulator_instances=6 \
                local_accumulator_contexts=12 dut_dsp48e2=2240 \
                array_dsp48e2=2176 frontend_dsp48e2=64 \
                frontend_quantizer_dsp48e2=0 region2_lane_instances=32 \
                region2_lower_bank_instances=1 region2_upper_bank_instances=1 \
                region2_dsp48e2=544 region2_rows0_3_dsp48e2=272 \
                region2_rows4_7_dsp48e2=272 region2_residual_dsp48e2=0 \
                region2_lane_min_dsp48e2=17 region2_lane_max_dsp48e2=17 \
                synthesized_buffer_primitives=4086 synthesized_buffer_ff=2696 \
                synthesized_buffer_payload_ff=2688 synthesized_buffer_tag_ff=6 \
                synthesized_buffer_occupancy_ff=2 drc_errors=0 \
                partition_exact_cover=1 implementation_commands_run=0 \
                checkpoint_written=0 place_authorized=0 route_authorized=0 \
                status=V5_P16_PRODUCTION_REGION2_POST_OPT_PROBE_PASS; do
            hap_v5_require_exact_line "$p16_production_region2_summary" \
                "$literal" "P16 production region2 summary" || return 1
        done
        hap_v5_get_unique_value "$p16_production_region2_summary" \
            region2_primitives "P16 production region2 summary" \
            expected_region2_total_primitives || return 1
        hap_v5_get_unique_value "$p16_production_region2_summary" \
            region2_rows0_3_primitives "P16 production region2 summary" \
            expected_region2_rows0_3_primitives || return 1
        hap_v5_get_unique_value "$p16_production_region2_summary" \
            region2_rows4_7_primitives "P16 production region2 summary" \
            expected_region2_rows4_7_primitives || return 1
        hap_v5_get_unique_value "$p16_production_region2_summary" \
            region2_residual_primitives "P16 production region2 summary" \
            expected_region2_residual_primitives || return 1
        for literal in "$expected_region2_total_primitives" \
                "$expected_region2_rows0_3_primitives" \
                "$expected_region2_rows4_7_primitives" \
                "$expected_region2_residual_primitives"; do
            [[ "$literal" =~ ^[1-9][0-9]*$ ]] ||
                hap_v5_provenance_fail \
                    "P16 no-clip region2 primitive signature is malformed" ||
                return 1
        done
        region2_partition_sum=$((expected_region2_rows0_3_primitives +
            expected_region2_rows4_7_primitives +
            expected_region2_residual_primitives))
        [[ "$expected_region2_total_primitives" -eq "$relief_primitives" &&
           "$region2_partition_sum" -eq "$expected_region2_total_primitives" ]] ||
            hap_v5_provenance_fail \
                "P16 no-clip region2 partition/relief identity mismatch" ||
            return 1
    fi

    mapfile -t expected_outputs < <(
        while IFS= read -r name; do printf '%s/%s\n' "$route_dir" "$name"; done \
            < <(hap_v5_route_required_output_names)
    )
    hap_v5_read_sha_manifest_paths_dynamic "$output_sha" \
        output_manifest_paths || return 1
    mapfile -d '' current_route_outputs < <(find "$route_dir" -maxdepth 1 \
        -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
    hap_v5_require_same_path_set current_route_outputs \
        output_manifest_paths \
        "complete OOC route output manifest" || return 1
    for literal in "${expected_outputs[@]}"; do
        hap_v5_require_path_member output_manifest_paths "$literal" \
            "OOC route output manifest" || return 1
    done
    hap_v5_read_path_list "$input_files" "$expected_route_input_count" \
        route_input_paths || return 1
    hap_v5_read_sha_manifest_paths "$input_sha" "$expected_route_input_count" \
        input_manifest_paths || return 1
    hap_v5_require_same_path_set route_input_paths input_manifest_paths \
        "OOC route input manifest" || return 1
    route_input_manifest_sha="$(sha256sum -- "$input_sha" | awk '{print $1}')"
    hap_v5_get_unique_value "$summary" route_input_manifest_sha256 \
        "OOC route summary" summary_route_input_manifest_sha || return 1
    [[ "$summary_route_input_manifest_sha" =~ ^[0-9a-f]{64}$ &&
       "$summary_route_input_manifest_sha" == "$route_input_manifest_sha" ]] ||
        hap_v5_provenance_fail \
            "OOC route INPUT_SHA256SUMS self-SHA mismatch: summary=$summary_route_input_manifest_sha actual=$route_input_manifest_sha" ||
        return 1

    hap_v5_get_unique_value "$summary" input_dcp "OOC route summary" \
        input_dcp || return 1
    hap_v5_get_unique_value "$summary" input_place_summary \
        "OOC route summary" input_place_summary || return 1
    hap_v5_get_unique_value "$summary" input_place_sha256 \
        "OOC route summary" input_dcp_hash || return 1
    input_dcp="$(readlink -e -- "$input_dcp")" ||
        hap_v5_provenance_fail \
            "OOC route input DCP no longer exists" || return 1
    input_place_summary="$(readlink -e -- "$input_place_summary")" ||
        hap_v5_provenance_fail \
            "OOC route input place summary no longer exists" || return 1
    place_dir="$(dirname "$input_place_summary")"
    [[ "$input_dcp" == "$place_dir/post_place.dcp" ]] ||
        hap_v5_provenance_fail \
            "OOC route input DCP/place summary directories differ" ||
        return 1
    [[ "$input_dcp_hash" =~ ^[0-9a-f]{64}$ ]] ||
        hap_v5_provenance_fail \
            "OOC route input DCP SHA256 is malformed" || return 1
    actual_input_dcp_hash="$(sha256sum -- "$input_dcp" | awk '{print $1}')"
    [[ "$input_dcp_hash" == "$actual_input_dcp_hash" ]] ||
        hap_v5_provenance_fail \
            "OOC route input DCP SHA256 no longer matches its summary" ||
        return 1

    expected_inputs=(
        "$input_dcp"
        "$input_place_summary"
        "$place_dir/INPUT_SHA256SUMS"
        "$place_dir/OUTPUT_SHA256SUMS"
        "$place_dir/INPUT_FILES"
        "$place_dir/launcher_status.txt"
        "$place_dir/selectors_post_place.txt"
        "$place_dir/attention_geometry_post_place.txt"
        "$place_dir/attention_geometry_placement.txt"
        "$place_dir/base_pblocks_post_place.txt"
        "$place_dir/p5_input_plan_post_place.txt"
        "$place_dir/p5_input_pblocks_post_place.txt"
        "$place_dir/p9_postprocess_plan_post_place.txt"
        "$place_dir/p9_postprocess_pblocks_post_place.txt"
        "$place_dir/p9_quantizer3_plan_post_place.txt"
        "$place_dir/p9_quantizer3_pblock_post_place.txt"
        "$place_dir/p14_region2_relief_plan_post_place.txt"
        "$place_dir/p14_region2_relief_pblock_post_place.txt"
        "$place_dir/p8_parent_ingress_boundary_post_place.txt"
        "$place_dir/pre_place_gate.txt"
        "$place_dir/post_place_fast_gate.txt"
        "$HAP_V5_PROVENANCE_ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
        "$geometry_lib"
        "$HAP_V5_PROVENANCE_ROOT/vivado/scripts/v5_production_p5_input_partition_floorplan.tcl"
        "$HAP_V5_PROVENANCE_ROOT/vivado/scripts/v5_production_p9_postprocess_partition_floorplan.tcl"
        "$quantizer3_lib"
        "$relief_lib"
        "$HAP_V5_PROVENANCE_ROOT/vivado/scripts/audit_mlp_p8_parent_ingress_boundary_replica_aware.tcl"
        "$HAP_V5_PROVENANCE_ROOT/vivado/scripts/check_attention_mlp_production_io_selectors.tcl"
        "$HAP_V5_PROVENANCE_ROOT/vivado/constraints/attention_mlp_production_v5_ooc_clocks_100mhz.xdc"
        "$HAP_V5_PROVENANCE_ROOT/vivado/scripts/resume_attention_mlp_production_v5_route.tcl"
        "$HAP_V5_PROVENANCE_ROOT/vivado/scripts/resume_attention_mlp_production_v5_p10_p14_route.tcl"
        "$HAP_V5_PROVENANCE_ROOT/vivado/scripts/run_attention_mlp_production_v5_p10_p14_route.sh"
    )
    if [[ "$route_variant" == P16_NOCLIP ]]; then
        expected_inputs+=(
            "$HAP_V5_PROVENANCE_ROOT/vivado/scripts/projection_core16x16_w8_reuse_ooc_p16_floorplan.tcl"
            "$HAP_V5_PROVENANCE_ROOT/vivado/scripts/projection_core16x16_w8_reuse_ooc_floorplan.tcl"
            "$HAP_V5_PROVENANCE_ROOT/vivado/scripts/v5_production_p9_quantizer3_locality_floorplan.tcl"
            "$HAP_V5_PROVENANCE_ROOT/vivado/scripts/v5_production_p14_region2_x2_relief_floorplan.tcl"
            "$p16_post_opt_summary"
            "$p16_production_region2_summary")
    fi
    hap_v5_require_same_path_set expected_inputs route_input_paths \
        "OOC route exact input closure" || return 1
    place_input_manifest_sha="$(sha256sum -- \
        "$place_dir/INPUT_SHA256SUMS" | awk '{print $1}')"
    hap_v5_get_unique_value "$summary" place_input_manifest_sha256 \
        "OOC route summary" summary_place_input_manifest_sha || return 1
    [[ "$summary_place_input_manifest_sha" =~ ^[0-9a-f]{64}$ &&
       "$summary_place_input_manifest_sha" == \
        "$place_input_manifest_sha" ]] ||
        hap_v5_provenance_fail \
            "OOC route/place INPUT_SHA256SUMS self-SHA mismatch: summary=$summary_place_input_manifest_sha actual=$place_input_manifest_sha" ||
        return 1
    place_output_manifest_sha="$(sha256sum -- \
        "$place_dir/OUTPUT_SHA256SUMS" | awk '{print $1}')"
    hap_v5_get_unique_value "$summary" place_output_manifest_sha256 \
        "OOC route summary" summary_place_output_manifest_sha || return 1
    [[ "$summary_place_output_manifest_sha" =~ ^[0-9a-f]{64}$ &&
       "$summary_place_output_manifest_sha" == \
        "$place_output_manifest_sha" ]] ||
        hap_v5_provenance_fail \
            "OOC route/place OUTPUT_SHA256SUMS self-SHA mismatch: summary=$summary_place_output_manifest_sha actual=$place_output_manifest_sha" ||
        return 1
    hap_v5_read_sha_manifest_paths "$place_dir/INPUT_SHA256SUMS" \
        "$place_input_count" \
        place_input_paths || return 1
    if [[ "$route_variant" == P16_NOCLIP ]]; then
        for required in "$p16_post_opt_summary" \
                "$p16_production_region2_summary" "$production_input_dcp"; do
            hap_v5_require_path_member place_input_paths "$required" \
                "P16 no-clip place input manifest" || return 1
        done
    fi
    hap_v5_read_sha_manifest_paths_dynamic \
        "$place_dir/OUTPUT_SHA256SUMS" place_output_paths || return 1
    place_output_manifest_entries="${#place_output_paths[@]}"
    hap_v5_get_unique_value "$summary" place_output_manifest_entries \
        "OOC route summary" summary_place_output_manifest_entries || return 1
    [[ "$summary_place_output_manifest_entries" =~ ^[1-9][0-9]*$ &&
       "$summary_place_output_manifest_entries" -eq \
        "$place_output_manifest_entries" ]] ||
        hap_v5_provenance_fail \
            "OOC route/place output-manifest count mismatch: summary=$summary_place_output_manifest_entries actual=$place_output_manifest_entries" ||
        return 1
    mapfile -d '' expected_place_output_paths < <(find "$place_dir" \
        -maxdepth 1 -type f -size +0c ! -name OUTPUT_SHA256SUMS \
        -print0 | sort -z)
    hap_v5_require_same_path_set expected_place_output_paths \
        place_output_paths "complete place output SHA manifest" || return 1
    hap_v5_require_path_member place_output_paths "$input_dcp" \
        "place output SHA manifest" || return 1
    hap_v5_require_path_member place_output_paths "$input_place_summary" \
        "place output SHA manifest" || return 1

    while IFS= read -r literal; do
        hap_v5_require_exact_line "$summary" "$literal" \
            "OOC route summary" || return 1
    done < <(hap_v5_route_required_summary_lines)
    for literal in \
            "place_input_manifest_entries=$place_input_count" \
            "p9_quantizer3_primitives=$quantizer3_primitives" \
            "p14_region2_relief_primitives=$relief_primitives" \
            "p14_region2_relief_placed=$relief_primitives"; do
        hap_v5_require_exact_line "$summary" "$literal" \
            "OOC route dynamic summary" || return 1
    done
    if [[ "$route_variant" == P16_NOCLIP ]]; then
        for literal in rtl_variant=P16_NOCLIP \
                rtl_resource_variant=P16_NOCLIP \
                "region2_signature_source=P16_PRODUCTION_POST_OPT_SHA256:$p16_production_region2_summary_sha" \
                "p16_post_opt_summary=$p16_post_opt_summary" \
                "p16_post_opt_summary_sha256=$p16_post_opt_summary_sha" \
                "p16_production_region2_summary=$p16_production_region2_summary" \
                "p16_production_region2_summary_sha256=$p16_production_region2_summary_sha" \
                "p16_production_dcp_sha256=$p16_production_dcp_sha"; do
            hap_v5_require_exact_line "$summary" "$literal" \
                "P16 no-clip OOC route summary" || return 1
        done
    fi
    awk -F= '
        /^wns_ns=|^whs_ns=/ {
            count[$1]++; total++
            if ($2 !~ /^[-+]?[0-9]+([.][0-9]+)?$/ || $2 + 0 < 0) bad=1
        }
        END {
            exit total == 2 && count["wns_ns"] == 1 &&
                count["whs_ns"] == 1 && !bad ? 0 : 1
        }' "$summary" ||
        hap_v5_provenance_fail \
            "OOC route WNS/WHS are missing, duplicated, malformed, or negative" ||
        return 1

    while IFS= read -r literal; do
        hap_v5_require_exact_line "$selectors" "$literal" \
            "OOC route live-selector report" || return 1
    done < <(hap_v5_route_required_selector_lines)
    if [[ "$route_variant" == P16_NOCLIP ]]; then
        hap_v5_require_exact_line "$selectors" \
            rtl_resource_variant=P16_NOCLIP \
            "P16 no-clip OOC route live-selector report" || return 1
    fi
    while IFS= read -r literal; do
        hap_v5_require_exact_line "$geometry" "$literal" \
            "OOC route Attention geometry report" || return 1
    done < <(hap_v5_route_required_geometry_lines)
    while IFS= read -r literal; do
        hap_v5_require_exact_line "$geometry_placement" "$literal" \
            "OOC route Attention geometry placement report" || return 1
    done < <(hap_v5_route_required_geometry_placement_lines)
    while IFS= read -r literal; do
        hap_v5_require_exact_line "$base_pblocks" "$literal" \
            "OOC route base-pblock report" || return 1
    done < <(hap_v5_route_required_base_pblock_lines)
    while IFS= read -r literal; do
        hap_v5_require_exact_line "$input_plan" "$literal" \
            "OOC route P5 input-plan report" || return 1
    done < <(hap_v5_route_required_input_plan_lines)
    while IFS= read -r literal; do
        hap_v5_require_exact_line "$input_pblocks" "$literal" \
            "OOC route P5 input-pblock report" || return 1
    done < <(hap_v5_route_required_input_pblock_lines)
    while IFS= read -r literal; do
        hap_v5_require_exact_line "$postprocess_plan" "$literal" \
            "OOC route P9 postprocess-plan report" || return 1
    done < <(hap_v5_route_required_p9_postprocess_plan_lines)
    while IFS= read -r literal; do
        hap_v5_require_exact_line "$postprocess_pblocks" "$literal" \
            "OOC route P9 postprocess-pblock report" || return 1
    done < <(hap_v5_route_required_p9_postprocess_pblock_lines)
    while IFS= read -r literal; do
        hap_v5_require_exact_line "$quantizer3_plan" "$literal" \
            "OOC route P9 quantizer3-plan report" || return 1
    done < <(hap_v5_route_required_p9_quantizer3_plan_lines \
        "$quantizer3_primitives")
    while IFS= read -r literal; do
        hap_v5_require_exact_line "$quantizer3_pblock" "$literal" \
            "OOC route P9 quantizer3-pblock report" || return 1
    done < <(hap_v5_route_required_p9_quantizer3_pblock_lines \
        "$quantizer3_primitives")
    while IFS= read -r literal; do
        hap_v5_require_exact_line "$relief_plan" "$literal" \
            "OOC route P14 region2-relief plan" || return 1
    done < <(hap_v5_route_required_p14_relief_plan_lines \
        "$relief_primitives")
    while IFS= read -r literal; do
        hap_v5_require_exact_line "$relief_pblock" "$literal" \
            "OOC route P14 region2-relief pblock" || return 1
    done < <(hap_v5_route_required_p14_relief_pblock_lines \
        "$relief_primitives")
    awk -F= -v maximum="$relief_primitives" '
        $1 == "relief_placed" {
            count++
            if ($2 !~ /^[0-9]+$/ || $2 + 0 > maximum) bad=1
        }
        END {exit count == 1 && !bad ? 0 : 1}
    ' "$relief_pblock" ||
        hap_v5_provenance_fail \
            "OOC route P14 relief_placed is missing, duplicated, or invalid" ||
        return 1
    while IFS= read -r literal; do
        hap_v5_require_exact_line "$parent_input" "$literal" \
            "OOC route input P8 parent-boundary report" || return 1
    done < <(hap_v5_route_required_parent_lines \
        V5_P14_ROUTE_INPUT_PARENT_INGRESS_BOUNDARY_PASS)
    while IFS= read -r literal; do
        hap_v5_require_exact_line "$parent_final" "$literal" \
            "OOC route final P8 parent-boundary report" || return 1
    done < <(hap_v5_route_required_parent_lines \
        V5_P14_ROUTE_FINAL_PARENT_INGRESS_BOUNDARY_PASS)
    while IFS= read -r literal; do
        hap_v5_require_exact_line "$input_boundaries" "$literal" \
            "OOC route input architecture-boundary report" || return 1
    done < <(hap_v5_route_required_boundary_lines \
        V5_P14_ROUTE_INPUT_BOUNDARIES_PASS)
    while IFS= read -r literal; do
        hap_v5_require_exact_line "$post_boundaries" "$literal" \
            "OOC route final architecture-boundary report" || return 1
    done < <(hap_v5_route_required_boundary_lines \
        V5_P14_ROUTE_FINAL_BOUNDARIES_PASS)
    while IFS= read -r literal; do
        hap_v5_require_exact_line "$launcher_status" "$literal" \
            "OOC route launcher status" || return 1
    done < <(hap_v5_route_required_launcher_lines)
    if [[ "$route_variant" == P16_NOCLIP ]]; then
        hap_v5_require_exact_line "$launcher_status" \
            rtl_variant=P16_NOCLIP \
            "P16 no-clip OOC route launcher status" || return 1
    fi
    hap_v5_require_exact_line "$launcher_status" \
        "route_input_manifest_sha256=$route_input_manifest_sha" \
        "OOC route launcher status" || return 1
    count="$(find "$route_dir" -maxdepth 1 -type f -name '*.bit' -print -quit | \
        wc -l)"
    [[ "$count" -eq 0 ]] ||
        hap_v5_provenance_fail \
            "OOC route authorization artifact unexpectedly contains a bitstream" ||
        return 1
}

# Test-only fixture constructor for the provenance gate.  It synthesizes no
# design and creates no checkpoint semantics; files contain plain fixture text
# while exercising the variant-specific place inputs, a dynamically complete
# place-output set, and the exact route provenance graph.
hap_v5_make_ooc_route_fixture() {
    local route_dir="$1" variant="${2:-P14_LEGACY}"
    local route_variant="$variant"
    local place_dir="$(dirname "$1")/place_fixture"
    local p16_dir="$(dirname "$1")/p16_post_opt_fixture"
    local p16_summary="" p16_summary_sha=""
    local p16_production_summary="" p16_production_summary_sha=""
    local p16_production_dcp="" p16_production_dcp_sha=""
    local place_dummy_count=14 quantizer3_primitives=11178
    local relief_primitives=68799 geometry_lib quantizer3_lib relief_lib
    local expected_total_dsp=5453 expected_slr1_dsp=1781
    local expected_route_input_count=33
    local expected_region2_rows0_3_primitives=26800
    local expected_region2_rows4_7_primitives=26800
    local expected_region2_residual_primitives=15199
    local name path hash
    local -a place_inputs=() place_outputs=() route_inputs=() route_outputs=()
    mkdir -p "$route_dir" "$place_dir"

    case "$variant" in
        P14_LEGACY)
            geometry_lib="$HAP_V5_PROVENANCE_ROOT/vivado/scripts/projection_core16x16_w8_reuse_ooc_floorplan.tcl"
            quantizer3_lib="$HAP_V5_PROVENANCE_ROOT/vivado/scripts/v5_production_p9_quantizer3_locality_floorplan.tcl"
            relief_lib="$HAP_V5_PROVENANCE_ROOT/vivado/scripts/v5_production_p14_region2_x2_relief_floorplan.tcl"
            ;;
        P16_NOCLIP)
            place_dummy_count=17
            expected_total_dsp=5449
            expected_slr1_dsp=1777
            expected_route_input_count=39
            expected_region2_rows0_3_primitives=26800
            expected_region2_rows4_7_primitives=26800
            expected_region2_residual_primitives=19296
            quantizer3_primitives=9000
            relief_primitives=72896
            geometry_lib="$HAP_V5_PROVENANCE_ROOT/vivado/scripts/projection_core16x16_w8_reuse_ooc_p16_bound_floorplan.tcl"
            quantizer3_lib="$HAP_V5_PROVENANCE_ROOT/vivado/scripts/v5_production_p16_noclip_quantizer3_locality_floorplan.tcl"
            relief_lib="$HAP_V5_PROVENANCE_ROOT/vivado/scripts/v5_production_p16_noclip_region2_x2_relief_floorplan.tcl"
            mkdir -p "$p16_dir"
            p16_summary="$p16_dir/summary.txt"
            printf '%s\n' \
                stage=P16_100MHZ_POST_OPT_STRUCTURE_PROBE \
                part=xcvu9p-flga2104-2L-e jobs=32 clock_mhz=100 \
                attention_lane_instances=128 \
                local_dual_accumulator_instances=6 \
                local_accumulator_contexts=12 dut_dsp48e2=2240 \
                array_dsp48e2=2176 frontend_dsp48e2=64 \
                frontend_hadamard_dsp48e2=64 \
                frontend_quantizer_dsp48e2=0 region2_dsp48e2=544 \
                "region2_primitives=$relief_primitives" \
                "region2_rows0_3_primitives=$expected_region2_rows0_3_primitives" \
                region2_rows0_3_dsp48e2=272 \
                "region2_rows4_7_primitives=$expected_region2_rows4_7_primitives" \
                region2_rows4_7_dsp48e2=272 \
                "region2_residual_primitives=$expected_region2_residual_primitives" \
                region2_residual_dsp48e2=0 drc_errors=0 status=PASS \
                fixture=P16_NOCLIP > "$p16_summary"
            p16_summary_sha="$(sha256sum -- "$p16_summary" | awk '{print $1}')"
            p16_production_dcp="$p16_dir/production_post_opt.dcp"
            printf 'fixture=P16_PRODUCTION_POST_OPT\n' > "$p16_production_dcp"
            p16_production_dcp_sha="$(sha256sum -- \
                "$p16_production_dcp" | awk '{print $1}')"
            p16_production_summary="$p16_dir/production_region2_summary.txt"
            printf '%s\n' \
                stage=P16_PRODUCTION_POST_OPT_REGION2_SIGNATURE_PROBE \
                part=xcvu9p-flga2104-2L-e \
                top=hap_attention_mlp_production_core jobs=32 \
                "input_dcp=$p16_production_dcp" \
                "input_dcp_sha256=$p16_production_dcp_sha" \
                projection_instances=1 attention_lane_instances=128 \
                local_dual_accumulator_instances=6 \
                local_accumulator_contexts=12 dut_dsp48e2=2240 \
                array_dsp48e2=2176 frontend_dsp48e2=64 \
                frontend_quantizer_dsp48e2=0 region2_lane_instances=32 \
                region2_lower_bank_instances=1 region2_upper_bank_instances=1 \
                "region2_primitives=$relief_primitives" \
                region2_lut_primitives=35269 region2_ff_primitives=34743 \
                region2_dsp48e2=544 \
                "region2_rows0_3_primitives=$expected_region2_rows0_3_primitives" \
                region2_rows0_3_lut=13504 region2_rows0_3_ff=12112 \
                region2_rows0_3_dsp48e2=272 \
                "region2_rows4_7_primitives=$expected_region2_rows4_7_primitives" \
                region2_rows4_7_lut=13504 region2_rows4_7_ff=12112 \
                region2_rows4_7_dsp48e2=272 \
                "region2_residual_primitives=$expected_region2_residual_primitives" \
                region2_residual_lut=8261 region2_residual_ff=10519 \
                region2_residual_dsp48e2=0 \
                region2_lane_min_primitives=1675 \
                region2_lane_max_primitives=1675 \
                region2_lane_min_dsp48e2=17 region2_lane_max_dsp48e2=17 \
                synthesized_buffer_primitives=4086 synthesized_buffer_ff=2696 \
                synthesized_buffer_payload_ff=2688 synthesized_buffer_tag_ff=6 \
                synthesized_buffer_occupancy_ff=2 drc_errors=0 \
                partition_exact_cover=1 implementation_commands_run=0 \
                checkpoint_written=0 place_authorized=0 route_authorized=0 \
                status=V5_P16_PRODUCTION_REGION2_POST_OPT_PROBE_PASS \
                fixture=P16_NOCLIP > "$p16_production_summary"
            p16_production_summary_sha="$(sha256sum -- \
                "$p16_production_summary" | awk '{print $1}')"
            ;;
        *) return 2 ;;
    esac

    for ((name = 0; name < place_dummy_count; name++)); do
        path="$place_dir/input_$name.txt"
        printf 'place_input=%s\n' "$name" > "$path"
        place_inputs+=("$path")
    done
    [[ "$variant" != P16_NOCLIP ]] || place_inputs+=(
        "$p16_production_dcp" "$p16_summary" "$p16_production_summary")
    printf '%s\n' "${place_inputs[@]}" > "$place_dir/INPUT_FILES"
    sha256sum "${place_inputs[@]}" > "$place_dir/INPUT_SHA256SUMS"

    for name in post_place.dcp summary.txt selectors_post_place.txt \
            attention_geometry_post_place.txt \
            attention_geometry_placement.txt base_pblocks_post_place.txt \
            p5_input_plan_post_place.txt p5_input_pblocks_post_place.txt \
            p9_postprocess_plan_post_place.txt \
            p9_postprocess_pblocks_post_place.txt \
            p9_quantizer3_plan_post_place.txt \
            p9_quantizer3_pblock_post_place.txt \
            p14_region2_relief_plan_post_place.txt \
            p14_region2_relief_pblock_post_place.txt \
            p8_parent_ingress_boundary_post_place.txt \
            pre_place_gate.txt post_place_fast_gate.txt launcher_status.txt \
            place_out_05 \
            place_out_06 place_out_07 place_out_08 place_out_09 \
            place_out_10 place_out_11 place_out_12 place_out_13 \
            place_out_14 place_out_15 place_out_16; do
        path="$place_dir/$name"
        printf 'place_output=%s\n' "$name" > "$path"
        place_outputs+=("$path")
    done
    # INPUT_FILES/INPUT_SHA256SUMS are also nonempty ordinary files in the
    # place artifact and therefore belong to the dynamically complete output
    # set.  OUTPUT_SHA256SUMS itself is the sole self-exclusion.
    mapfile -d '' place_outputs < <(find "$place_dir" -maxdepth 1 -type f \
        -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
    sha256sum "${place_outputs[@]}" > "$place_dir/OUTPUT_SHA256SUMS"

    route_inputs=(
        "$place_dir/post_place.dcp"
        "$place_dir/summary.txt"
        "$place_dir/INPUT_SHA256SUMS"
        "$place_dir/OUTPUT_SHA256SUMS"
        "$place_dir/INPUT_FILES"
        "$place_dir/launcher_status.txt"
        "$place_dir/selectors_post_place.txt"
        "$place_dir/attention_geometry_post_place.txt"
        "$place_dir/attention_geometry_placement.txt"
        "$place_dir/base_pblocks_post_place.txt"
        "$place_dir/p5_input_plan_post_place.txt"
        "$place_dir/p5_input_pblocks_post_place.txt"
        "$place_dir/p9_postprocess_plan_post_place.txt"
        "$place_dir/p9_postprocess_pblocks_post_place.txt"
        "$place_dir/p9_quantizer3_plan_post_place.txt"
        "$place_dir/p9_quantizer3_pblock_post_place.txt"
        "$place_dir/p14_region2_relief_plan_post_place.txt"
        "$place_dir/p14_region2_relief_pblock_post_place.txt"
        "$place_dir/p8_parent_ingress_boundary_post_place.txt"
        "$place_dir/pre_place_gate.txt"
        "$place_dir/post_place_fast_gate.txt"
        "$HAP_V5_PROVENANCE_ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
        "$geometry_lib"
        "$HAP_V5_PROVENANCE_ROOT/vivado/scripts/v5_production_p5_input_partition_floorplan.tcl"
        "$HAP_V5_PROVENANCE_ROOT/vivado/scripts/v5_production_p9_postprocess_partition_floorplan.tcl"
        "$quantizer3_lib"
        "$relief_lib"
        "$HAP_V5_PROVENANCE_ROOT/vivado/scripts/audit_mlp_p8_parent_ingress_boundary_replica_aware.tcl"
        "$HAP_V5_PROVENANCE_ROOT/vivado/scripts/check_attention_mlp_production_io_selectors.tcl"
        "$HAP_V5_PROVENANCE_ROOT/vivado/constraints/attention_mlp_production_v5_ooc_clocks_100mhz.xdc"
        "$HAP_V5_PROVENANCE_ROOT/vivado/scripts/resume_attention_mlp_production_v5_route.tcl"
        "$HAP_V5_PROVENANCE_ROOT/vivado/scripts/resume_attention_mlp_production_v5_p10_p14_route.tcl"
        "$HAP_V5_PROVENANCE_ROOT/vivado/scripts/run_attention_mlp_production_v5_p10_p14_route.sh"
    )
    if [[ "$variant" == P16_NOCLIP ]]; then
        route_inputs+=(
            "$HAP_V5_PROVENANCE_ROOT/vivado/scripts/projection_core16x16_w8_reuse_ooc_p16_floorplan.tcl"
            "$HAP_V5_PROVENANCE_ROOT/vivado/scripts/projection_core16x16_w8_reuse_ooc_floorplan.tcl"
            "$HAP_V5_PROVENANCE_ROOT/vivado/scripts/v5_production_p9_quantizer3_locality_floorplan.tcl"
            "$HAP_V5_PROVENANCE_ROOT/vivado/scripts/v5_production_p14_region2_x2_relief_floorplan.tcl"
            "$p16_summary"
            "$p16_production_summary")
    fi
    printf '%s\n' "${route_inputs[@]}" > "$route_dir/INPUT_FILES"
    sha256sum "${route_inputs[@]}" > "$route_dir/INPUT_SHA256SUMS"

    while IFS= read -r name; do
        path="$route_dir/$name"
        case "$name" in
            summary.txt)
                hap_v5_route_required_summary_lines > "$path"
                printf '%s\n' \
                    "place_input_manifest_entries=${#place_inputs[@]}" \
                    "p9_quantizer3_primitives=$quantizer3_primitives" \
                    "p14_region2_relief_primitives=$relief_primitives" \
                    "p14_region2_relief_placed=$relief_primitives" >> "$path"
                if [[ "$variant" == P16_NOCLIP ]]; then
                    printf '%s\n' rtl_variant=P16_NOCLIP \
                        rtl_resource_variant=P16_NOCLIP \
                        "region2_signature_source=P16_PRODUCTION_POST_OPT_SHA256:$p16_production_summary_sha" \
                        "p16_post_opt_summary=$p16_summary" \
                        "p16_post_opt_summary_sha256=$p16_summary_sha" \
                        "p16_production_region2_summary=$p16_production_summary" \
                        "p16_production_region2_summary_sha256=$p16_production_summary_sha" \
                        "p16_production_dcp_sha256=$p16_production_dcp_sha" >> "$path"
                fi
                printf 'place_output_manifest_entries=%d\n' \
                    "${#place_outputs[@]}" >> "$path"
                printf 'place_input_manifest_sha256=%s\n' \
                    "$(sha256sum -- "$place_dir/INPUT_SHA256SUMS" | \
                        awk '{print $1}')" >> "$path"
                printf 'place_output_manifest_sha256=%s\n' \
                    "$(sha256sum -- "$place_dir/OUTPUT_SHA256SUMS" | \
                        awk '{print $1}')" >> "$path"
                printf 'route_input_manifest_sha256=%s\n' \
                    "$(sha256sum -- "$route_dir/INPUT_SHA256SUMS" | \
                        awk '{print $1}')" >> "$path"
                hash="$(sha256sum "$place_dir/post_place.dcp" | awk '{print $1}')"
                printf 'input_dcp=%s\ninput_place_summary=%s\ninput_place_sha256=%s\n' \
                    "$place_dir/post_place.dcp" "$place_dir/summary.txt" \
                    "$hash" >> "$path"
                printf 'wns_ns=0.125\nwhs_ns=0.031\n' >> "$path"
                ;;
            selectors_post_route.txt)
                hap_v5_route_required_selector_lines > "$path"
                if [[ "$variant" == P16_NOCLIP ]]; then
                    printf 'rtl_resource_variant=P16_NOCLIP\n' >> "$path"
                fi
                ;;
            attention_geometry_post_route.txt)
                hap_v5_route_required_geometry_lines > "$path"
                ;;
            attention_geometry_placement_post_route.txt)
                hap_v5_route_required_geometry_placement_lines > "$path"
                ;;
            base_pblocks_post_route.txt)
                hap_v5_route_required_base_pblock_lines > "$path"
                ;;
            p5_input_plan_post_route.txt)
                hap_v5_route_required_input_plan_lines > "$path"
                ;;
            p5_input_pblocks_post_route.txt)
                hap_v5_route_required_input_pblock_lines > "$path"
                ;;
            p9_postprocess_plan_post_route.txt)
                hap_v5_route_required_p9_postprocess_plan_lines > "$path"
                ;;
            p9_postprocess_pblocks_post_route.txt)
                hap_v5_route_required_p9_postprocess_pblock_lines > "$path"
                ;;
            p9_quantizer3_plan_post_route.txt)
                hap_v5_route_required_p9_quantizer3_plan_lines \
                    "$quantizer3_primitives" > "$path"
                ;;
            p9_quantizer3_pblock_post_route.txt)
                hap_v5_route_required_p9_quantizer3_pblock_lines \
                    "$quantizer3_primitives" > "$path"
                ;;
            p14_region2_relief_plan_post_route.txt)
                hap_v5_route_required_p14_relief_plan_lines \
                    "$relief_primitives" > "$path"
                ;;
            p14_region2_relief_pblock_post_route.txt)
                hap_v5_route_required_p14_relief_pblock_lines \
                    "$relief_primitives" > "$path"
                printf 'relief_placed=12345\n' >> "$path"
                ;;
            p8_parent_ingress_boundary_input.txt)
                hap_v5_route_required_parent_lines \
                    V5_P14_ROUTE_INPUT_PARENT_INGRESS_BOUNDARY_PASS > "$path"
                ;;
            p8_parent_ingress_boundary_post_route.txt)
                hap_v5_route_required_parent_lines \
                    V5_P14_ROUTE_FINAL_PARENT_INGRESS_BOUNDARY_PASS > "$path"
                ;;
            architecture_boundaries_input.txt)
                hap_v5_route_required_boundary_lines \
                    V5_P14_ROUTE_INPUT_BOUNDARIES_PASS > "$path"
                ;;
            architecture_boundaries_post_route.txt)
                hap_v5_route_required_boundary_lines \
                    V5_P14_ROUTE_FINAL_BOUNDARIES_PASS > "$path"
                ;;
            launcher_status.txt)
                hap_v5_route_required_launcher_lines > "$path"
                [[ "$variant" != P16_NOCLIP ]] || \
                    printf 'rtl_variant=P16_NOCLIP\n' >> "$path"
                printf 'route_input_manifest_sha256=%s\n' \
                    "$(sha256sum -- "$route_dir/INPUT_SHA256SUMS" | \
                        awk '{print $1}')" >> "$path"
                printf 'recursive_source_post_build_sha_verified=1\n' >> "$path"
                printf 'ooc_route_authorization_post_build_verified=1\n' >> "$path"
                ;;
            INPUT_FILES|INPUT_SHA256SUMS)
                # These were frozen before fixture outputs were constructed.
                ;;
            *) printf 'fixture=%s\n' "$name" > "$path" ;;
        esac
        route_outputs+=("$path")
    done < <(hap_v5_route_required_output_names)
    sha256sum "${route_outputs[@]}" > "$route_dir/OUTPUT_SHA256SUMS"
}
