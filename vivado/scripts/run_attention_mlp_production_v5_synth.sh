#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_JOBS="${HAP_JOBS:-32}"
[[ "$HAP_JOBS" == 32 ]] || {
    printf 'V5 production synthesis requires HAP_JOBS=32\n' >&2
    exit 2
}
export HAP_PRODUCTION_PROFILE=cohort16
export HAP_ATTENTION_BOARD_MODULE=hap_attention_board_cohort16_core
export HAP_PRODUCTION_MANIFEST="$ROOT/vivado/manifests/attention_mlp_production_v5_cohort16_sources.list"
requested_report="${HAP_REPORT_DIR:-$ROOT/vivado/reports/production_v5_synth_$STAMP}"
requested_build="${HAP_BUILD_DIR:-$ROOT/vivado/build/production_v5_synth_$STAMP}"
export HAP_REPORT_DIR="$(readlink -m -- "$requested_report")"
export HAP_BUILD_DIR="$(readlink -m -- "$requested_build")"
ROWLOCAL_STATIC_CHECKER="$ROOT/vivado/scripts/check_mlp_swiglu_rowlocal_unique_central_static.sh"
COHORT16_STATIC_CHECKER="$ROOT/vivado/scripts/check_attention_mlp_production_v5_cohort16_static.sh"
P5_STATIC_CHECKER="$ROOT/vivado/scripts/check_attention_mlp_production_v5_p10_p5_static.sh"
FORMAT_V3_STATIC_CHECKER="$ROOT/vivado/scripts/check_mlp_v5_format_v3_static.sh"
[[ -n "${HAP_SWIGLU_OOC_ARTIFACT:-}" ]] || {
    printf 'HAP_SWIGLU_OOC_ARTIFACT is required\n' >&2
    exit 2
}
[[ -n "${HAP_PRODUCTION_ELABORATION_ARTIFACT:-}" ]] || {
    printf 'HAP_PRODUCTION_ELABORATION_ARTIFACT is required\n' >&2
    exit 2
}
SWIGLU_OOC_ARTIFACT="$(readlink -m -- "$HAP_SWIGLU_OOC_ARTIFACT")"
PRODUCTION_ELABORATION_ARTIFACT="$(readlink -m -- \
    "$HAP_PRODUCTION_ELABORATION_ARTIFACT")"

verify_upstream_artifact() {
    local dir="$1" label="$2" marker="$3" required
    [[ -d "$dir" ]] || {
        printf 'missing %s artifact directory: %s\n' "$label" "$dir" >&2
        return 1
    }
    for required in INPUT_FILES INPUT_SHA256SUMS OUTPUT_SHA256SUMS \
            summary.txt launcher_status.txt; do
        [[ -s "$dir/$required" ]] || {
            printf 'missing %s artifact file: %s/%s\n' \
                "$label" "$dir" "$required" >&2
            return 1
        }
    done
    (cd / && sha256sum -c --strict "$dir/INPUT_SHA256SUMS") || return 1
    (cd / && sha256sum -c --strict "$dir/OUTPUT_SHA256SUMS") || return 1
    [[ "$(grep -Fxc -- "$marker" "$dir/summary.txt")" -eq 1 ]] || {
        printf '%s artifact PASS marker missing or duplicated: %s\n' \
            "$label" "$marker" >&2
        return 1
    }
    [[ "$(grep -Fxc 'vivado_exit_code=0' \
        "$dir/launcher_status.txt")" -eq 1 ]] || return 1
    [[ "$(grep -Fxc 'input_sha_recheck_exit_code=0' \
        "$dir/launcher_status.txt")" -eq 1 ]] || return 1
}

verify_upstream_artifacts() {
    verify_upstream_artifact "$SWIGLU_OOC_ARTIFACT" \
        swiglu_ooc status=REGISTERED_OOC_ROUTE_PASS
    verify_upstream_artifact "$PRODUCTION_ELABORATION_ARTIFACT" \
        production_elaboration status=V5_PRODUCTION_ELABORATION_PASS
}
[[ -x "$VIVADO" ]] || {
    printf 'Vivado executable is missing: %s\n' "$VIVADO" >&2
    exit 2
}
[[ ! -e "$HAP_REPORT_DIR" ]] || {
    printf 'V5 synthesis evidence directory already exists: %s\n' \
        "$HAP_REPORT_DIR" >&2
    exit 2
}
[[ ! -e "$HAP_BUILD_DIR" ]] || {
    printf 'V5 synthesis build directory already exists: %s\n' \
        "$HAP_BUILD_DIR" >&2
    exit 2
}
mapfile -t active_batch < <(pgrep -u "$(id -u)" -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another project-user batch Vivado is active; synthesis not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi
mkdir "$HAP_REPORT_DIR" "$HAP_BUILD_DIR"
printf 'swiglu_ooc_artifact=%s\nproduction_elaboration_artifact=%s\n' \
    "$SWIGLU_OOC_ARTIFACT" "$PRODUCTION_ELABORATION_ARTIFACT" \
    > "$HAP_REPORT_DIR/upstream_artifacts.txt"
if ! verify_upstream_artifacts \
        > "$HAP_REPORT_DIR/upstream_provenance_precheck.txt" 2>&1; then
    cat "$HAP_REPORT_DIR/upstream_provenance_precheck.txt" >&2
    printf 'V5 synthesis upstream provenance precheck failed\n' >&2
    exit 1
fi

# Freeze the complete recursive source graph before Vivado starts.  This is
# intentionally independent from the V4 evidence and build directories.
declare -A seen=()
inputs=()
collect_manifest() {
    local manifest="$1" raw line path
    [[ -f "$manifest" ]] || {
        echo "Missing V5 production manifest: $manifest" >&2
        exit 2
    }
    if [[ -z "${seen[$manifest]+x}" ]]; then
        seen["$manifest"]=1
        inputs+=("$manifest")
    fi
    while IFS= read -r raw || [[ -n "$raw" ]]; do
        line="${raw#"${raw%%[![:space:]]*}"}"
        line="${line%"${line##*[![:space:]]}"}"
        [[ -z "$line" || "${line:0:1}" == "#" ]] && continue
        path="$ROOT/$line"
        [[ -f "$path" ]] || {
            echo "Missing V5 production source: $path" >&2
            exit 2
        }
        if [[ "$path" == *.list ]]; then
            collect_manifest "$path"
        elif [[ -z "${seen[$path]+x}" ]]; then
            seen["$path"]=1
            inputs+=("$path")
        fi
    done < "$manifest"
}

collect_manifest "$HAP_PRODUCTION_MANIFEST"
for evidence_input in \
    "$ROOT/vivado/scripts/run_attention_mlp_production_v5_synth.sh" \
    "$ROOT/vivado/scripts/synth_attention_mlp_production_v5.tcl" \
    "$ROWLOCAL_STATIC_CHECKER" \
    "$COHORT16_STATIC_CHECKER" \
    "$P5_STATIC_CHECKER" \
    "$FORMAT_V3_STATIC_CHECKER"; do
    [[ -f "$evidence_input" ]] || {
        echo "Missing V5 production evidence input: $evidence_input" >&2
        exit 2
    }
    if [[ -z "${seen[$evidence_input]+x}" ]]; then
        seen["$evidence_input"]=1
        inputs+=("$evidence_input")
    fi
done
for artifact in "$SWIGLU_OOC_ARTIFACT" \
        "$PRODUCTION_ELABORATION_ARTIFACT"; do
    for evidence_input in "$artifact/INPUT_FILES" \
            "$artifact/INPUT_SHA256SUMS" "$artifact/OUTPUT_SHA256SUMS" \
            "$artifact/summary.txt" "$artifact/launcher_status.txt"; do
        if [[ -z "${seen[$evidence_input]+x}" ]]; then
            seen["$evidence_input"]=1
            inputs+=("$evidence_input")
        fi
    done
done
printf '%s\n' "${inputs[@]}" | LC_ALL=C sort -u \
    > "$HAP_REPORT_DIR/INPUT_FILES"
xargs -d '\n' sha256sum < "$HAP_REPORT_DIR/INPUT_FILES" \
    > "$HAP_REPORT_DIR/INPUT_SHA256SUMS"
(cd / && sha256sum -c --strict "$HAP_REPORT_DIR/INPUT_SHA256SUMS")

# Reject a stale branch-local/folded SwiGLU architecture or an old 8-row
# Attention production graph before the expensive fresh synthesis. Both
# checkers are part of the immutable input graph.
set +e
"$ROWLOCAL_STATIC_CHECKER" \
    > "$HAP_REPORT_DIR/swiglu_rowlocal_static_check.txt" 2>&1
rowlocal_static_rc=$?
"$COHORT16_STATIC_CHECKER" \
    > "$HAP_REPORT_DIR/cohort16_production_static_check.txt" 2>&1
cohort16_static_rc=$?
"$P5_STATIC_CHECKER" \
    > "$HAP_REPORT_DIR/p5_compact_static_check.txt" 2>&1
p5_static_rc=$?
"$FORMAT_V3_STATIC_CHECKER" \
    > "$HAP_REPORT_DIR/mlp_format_v3_static_check.txt" 2>&1
format_v3_static_rc=$?
set -e
if (( rowlocal_static_rc != 0 || cohort16_static_rc != 0 || \
      p5_static_rc != 0 || format_v3_static_rc != 0 )) || \
   [[ "$(grep -Fxc 'MLP_SWIGLU_ROWLOCAL_UNIQUE_CENTRAL_STATIC_PASS' \
        "$HAP_REPORT_DIR/swiglu_rowlocal_static_check.txt")" -ne 1 ]] || \
   [[ "$(grep -Fxc 'V5_COHORT16_STATIC_CONTRACT_PASS' \
        "$HAP_REPORT_DIR/cohort16_production_static_check.txt")" -ne 1 ]] || \
   [[ "$(grep -Fxc 'V5_P10_P5_STATIC_PASS' \
        "$HAP_REPORT_DIR/p5_compact_static_check.txt")" -ne 1 ]] || \
   [[ "$(grep -Fxc 'MLP_V5_FORMAT_V3_STATIC_PASS' \
        "$HAP_REPORT_DIR/mlp_format_v3_static_check.txt")" -ne 1 ]]; then
    printf 'V5 synthesis static architecture gate failed; evidence: %s\n' \
        "$HAP_REPORT_DIR" >&2
    mapfile -d '' early_outputs < <(find "$HAP_REPORT_DIR" -maxdepth 1 \
        -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
    if [[ "${#early_outputs[@]}" -ne 0 ]]; then
        sha256sum -- "${early_outputs[@]}" \
            > "$HAP_REPORT_DIR/OUTPUT_SHA256SUMS"
    fi
    exit 1
fi

cd "$ROOT"
set +e
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/synth_attention_mlp_production_v5.tcl \
    -log "$HAP_REPORT_DIR/vivado.log" \
    -journal "$HAP_REPORT_DIR/vivado.jou"
vivado_rc=$?
set -e

# Vivado may run for hours; reject every result if any frozen RTL, manifest,
# Tcl, launcher, or static checker changed while it was running.  This check
# deliberately runs after every Vivado return, including an error return.
set +e
(cd / && sha256sum -c --strict "$HAP_REPORT_DIR/INPUT_SHA256SUMS") \
    > "$HAP_REPORT_DIR/input_sha_postcheck.txt" 2>&1
input_rc=$?
verify_upstream_artifacts \
    > "$HAP_REPORT_DIR/upstream_provenance_postcheck.txt" 2>&1
upstream_rc=$?
set -e

archive_outputs() {
    mapfile -d '' outputs < <(find "$HAP_REPORT_DIR" -maxdepth 1 \
        -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
    if [[ "${#outputs[@]}" -ne 0 ]]; then
        sha256sum -- "${outputs[@]}" > "$HAP_REPORT_DIR/OUTPUT_SHA256SUMS"
    fi
}
printf 'vivado_exit_code=%d\ninput_sha_recheck_exit_code=%d\nupstream_provenance_recheck_exit_code=%d\n' \
    "$vivado_rc" "$input_rc" "$upstream_rc" \
    > "$HAP_REPORT_DIR/launcher_status.txt"
if (( vivado_rc != 0 || input_rc != 0 || upstream_rc != 0 )); then
    archive_outputs
    printf 'V5 production synthesis failed; evidence retained in %s\n' \
        "$HAP_REPORT_DIR" >&2
    printf '%s\n' "$HAP_REPORT_DIR"
    (( vivado_rc != 0 )) && exit "$vivado_rc"
    (( input_rc != 0 )) && exit "$input_rc"
    exit "$upstream_rc"
fi

for required in summary.txt post_synth.dcp post_opt.dcp \
        utilization_post_synth.rpt utilization_hier_post_synth.rpt \
        utilization_post_opt.rpt utilization_hier_post_opt.rpt \
        timing_post_opt.rpt swiglu_rowlocal_static_check.txt \
        cohort16_production_static_check.txt \
        p5_compact_static_check.txt \
        mlp_format_v3_static_check.txt \
        upstream_artifacts.txt upstream_provenance_precheck.txt \
        upstream_provenance_postcheck.txt \
        vivado.log vivado.jou launcher_status.txt input_sha_postcheck.txt; do
    [[ -s "$HAP_REPORT_DIR/$required" ]] || {
        archive_outputs
        printf 'missing or empty V5 synthesis output: %s\n' "$required" >&2
        exit 1
    }
done

if grep -Eiq '(^|[^[:alnum:]_])(FAIL|ERROR|FATAL)(:|\[|[[:space:]])' \
    "$HAP_REPORT_DIR/vivado.log" "$HAP_REPORT_DIR/summary.txt"; then
    archive_outputs
    echo "V5 production synth rejected FAIL/Error/Fatal marker" >&2
    exit 1
fi

gate_failed=0
[[ "$(grep -Fxc 'status=V5_PRODUCTION_RESOURCE_PASS' \
    "$HAP_REPORT_DIR/summary.txt")" -eq 1 ]] || {
    archive_outputs
    printf 'V5 synthesis requires exactly one resource PASS marker\n' >&2
    exit 1
}
for literal in \
    "jobs=$HAP_JOBS" \
    'production_profile=cohort16' \
    'attention_board_module=hap_attention_board_cohort16_core' \
    'attention_cohort16_board_instances=1' \
    'attention_legacy_board_instances=0' \
    'attention_cohort16_compute_instances=1' \
    'attention_legacy_compute_instances=0' \
    'attention_query_store_instances=1' \
    'attention_postprocess_store_instances=1' \
    'attention_postprocess_row_bank_instances=16' \
    'attention_context_store_instances=1' \
    'attention_context_ramb36e2=44' \
    'attention_context_ramb18e2=0' \
    'attention_context_lutram_primitives=0' \
    'attention_context_dsp48e2=0' \
    'attention_context_uram288=0' \
    'attention_projection16_instances=1' \
    'attention_projection8_instances=0' \
    'attention_lane_instances=128' \
    'attention_dual_accumulator_instances=6' \
    'attention_local_accumulator_contexts=12' \
    'attention_projection_dsp48e2=2240' \
    'attention_array_dsp48e2=2176' \
    'attention_frontend_dsp48e2=64' \
    'attention_base_frontend_dsp48e2=64' \
    'no_clip_s27_quantizer_instances=12' \
    'attention_quantizer_instances=8' \
    'attention_quantizer_dsp48e2=0' \
    'raw_weight_push_loads=37' \
    'weight_data_capture_contract=32x256' \
    'weight_data_capture_nets=32' \
    'weight_data_capture_loads=256/256' \
    'weight_meta_capture_contract=2x256' \
    'weight_meta_capture_nets=2' \
    'weight_meta_capture_loads=256/256' \
    'weight_group_capture_contract=2x7' \
    'weight_group_capture_nets=2' \
    'weight_group_capture_loads=7/7' \
    'projection_weight_capture_ok=1' \
    'v5_kernel12_instances=2' 'v4_kernel16_instances=0' \
    'mlp_kernel_dsp48e2=3072' 'branch0_dsp48e2=1536' \
    'branch1_dsp48e2=1536' 'history2_repack_instances=2' \
    'generic_repack_instances=0' 'swiglu_frontend_instances=1' \
    'swiglu_row_leaf_instances=2' 'swiglu_unique_hadamard_instances=1' \
    'swiglu_fold2_hadamard_instances=0' 'swiglu_quantizer_instances=4' \
    'swiglu_silu_instances=2' 'swiglu_frontend_dsp48e2=72' \
    'swiglu_hadamard_dsp48e2=64' 'swiglu_quantizer_dsp48e2=0' \
    'swiglu_silu_dsp48e2=4' 'swiglu_frontend_ramb36e2=40' \
    'swiglu_row_ring_ramb36e2=28' 'swiglu_silu_ramb36e2=12' \
    'swiglu_other_ramb36e2=0' 'attention_col3_array_instances=1' \
    'attention_old_array_instances=0' 'attention_left2_shard_instances=1' \
    'attention_center12_shard_instances=1' \
    'attention_right2_shard_instances=1' \
    'attention_center_subshard_instances=4' \
    'attention_leaf_shard_instances=6' \
    'compact_input_frontend_instances=1' \
    'compact_input_frontend_dsp48e2=8' \
    'compact_input_base_frontend_dsp48e2=8' \
    'compact_input_quantizer_instances=4' \
    'compact_input_quantizer_dsp48e2=0' \
    'compact_input_capture_contract=48x256' \
    'compact_input_capture_ff=12288' \
    'compact_input_capture_controls=48' \
    'compact_input_capture_loads=256/256' \
    'down_activation_cache_instances=1' \
    'down_activation_capture_contract=16x280' \
    'down_activation_capture_owners=16' \
    'down_activation_capture_ff=4480' \
    'down_activation_capture_loads=280/280' \
    'gate_accum_instances=2' 'gate_accum_write_controls=16' \
    'gate_accum_finalize_owners=16' \
    'down_accum_instances=2' 'down_guard_capture_contract=16x444' \
    'down_guard_capture_controls=16' 'down_guard_capture_ff=7104' \
    'down_guard_capture_loads=444/444' \
    'down_output_capture_contract=16x288' \
    'down_output_capture_controls=16' 'down_output_capture_ff=4608' \
    'down_output_capture_loads=288/288' \
    'serial_reset_lut2_domains=3' 'serial_reset_protected_domains=3' \
    'mlp_local_clear_ff=2' 'mlp_local_clear_protected_ff=2' \
    'branch0_local_clear_ff=1' 'branch1_local_clear_ff=1' \
    'swiglu_local_clear_ff=8' 'swiglu_local_clear_protected_ff=8' \
    'swiglu_control_clear_ff=1' 'swiglu_hadamard_clear_ff=1' \
    'swiglu_quantizer_clear_ff=4' 'swiglu_row_clear_ff=2' \
    'swiglu_direct_clear_bypass_state=0' \
    'mlp_central_clear_ff=1' \
    'mlp_central_clear_branch_endpoints=2' \
    'mlp_central_clear_direct_branch_state=0' \
    'metadata_leaf_instances=4' 'metadata_local_wr_en_ff=4' \
    'metadata_local_wr_addr_ff=70' 'metadata_local_wr_data_ff=896' \
    'metadata_local_write_protected_ff=970' \
    'mlp_capture_leaf_instances=1632' 'mlp_capture_leaf_lut1=1632' \
    'branch0_capture_leaf_instances=816' \
    'branch1_capture_leaf_instances=816' \
    'branch0_capture_leaf_lut1=816' 'branch1_capture_leaf_lut1=816' \
    'dsp48e2=5449' 'dsp_required=5449' 'uram288=752' \
    'ramb36e2=829' 'ramb18e2=22' \
    'post_opt_data_bufg=0' 'hierarchy_ok=1' \
    'protected_structure_ok=1' 'post_opt_data_bufg_ok=1' \
    'attention_projection_ok=1' 'compact_input_frontend_ok=1' \
    'swiglu_frontend_ok=1' 'swiglu_bram_ok=1' \
    'no_clip_quantizer_dsp_ok=1' \
    'attention_local_store_ok=1' 'hard_resource_ok=1' \
    'down_elastic2_instances=2'; do
    if [[ "$(grep -Fxc -- "$literal" "$HAP_REPORT_DIR/summary.txt")" -ne 1 ]]; then
        printf 'V5 synthesis summary contract missing or duplicated: %s\n' \
            "$literal" >&2
        gate_failed=1
    fi
done
if (( gate_failed != 0 )); then
    archive_outputs
    exit 1
fi
archive_outputs
(cd / && sha256sum -c --strict "$HAP_REPORT_DIR/INPUT_SHA256SUMS")
(cd / && sha256sum -c --strict "$HAP_REPORT_DIR/OUTPUT_SHA256SUMS")
cat "$HAP_REPORT_DIR/summary.txt"
printf '%s\n' "$HAP_REPORT_DIR"
