#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
AUDIT_TCL="$ROOT/vivado/scripts/audit_attention_mlp_production_v5_post_opt_dcp.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_post_opt_audit.sh"

if [[ $# -ne 1 ]]; then
    printf 'usage: %s V5_POST_OPT_DCP\n' "$0" >&2
    exit 2
fi
[[ -x "$VIVADO" ]] || {
    printf 'Vivado executable is missing: %s\n' "$VIVADO" >&2
    exit 2
}

# A V5 reopen audit accepts only the canonical post_opt.dcp emitted in the
# root of one timestamped or explicitly mission-labelled production synthesis
# artifact. A copied DCP, a post_synth checkpoint, or a checkpoint selected
# from an arbitrary directory is not an auditable upstream result even if its
# design contents look valid.
[[ "$(basename -- "$1")" == "post_opt.dcp" ]] || {
    printf 'V5 post-opt audit requires an explicit post_opt.dcp argument: %s\n' \
        "$1" >&2
    exit 2
}

export HAP_DCP="$(readlink -f -- "$1")"
for input in "$HAP_DCP" "$AUDIT_TCL" "$LAUNCHER"; do
    [[ -s "$input" ]] || {
        printf 'missing or empty V5 post-opt audit input: %s\n' "$input" >&2
        exit 2
    }
    [[ "$input" != *$'\n'* ]] || {
        printf 'newline is forbidden in audit input path: %q\n' "$input" >&2
        exit 2
    }
done

UPSTREAM_DIR="$(dirname -- "$HAP_DCP")"
UPSTREAM_NAME="$(basename -- "$UPSTREAM_DIR")"
UPSTREAM_PARENT="$(dirname -- "$UPSTREAM_DIR")"
if [[ "$UPSTREAM_PARENT" != "$ROOT/vivado/reports" || \
      ! "$UPSTREAM_NAME" =~ ^production_v5_synth_[0-9]{8}_([0-9]{6}|mission[0-9]{4}_[A-Za-z0-9_]+)$ || \
      "$HAP_DCP" != "$UPSTREAM_DIR/post_opt.dcp" ]]; then
    printf 'post_opt.dcp is not rooted in a canonical production_v5_synth artifact: %s\n' \
        "$HAP_DCP" >&2
    exit 2
fi

UPSTREAM_INPUT_FILES="$UPSTREAM_DIR/INPUT_FILES"
UPSTREAM_INPUT_SHA="$UPSTREAM_DIR/INPUT_SHA256SUMS"
UPSTREAM_OUTPUT_SHA="$UPSTREAM_DIR/OUTPUT_SHA256SUMS"
UPSTREAM_SUMMARY="$UPSTREAM_DIR/summary.txt"
UPSTREAM_LAUNCHER_STATUS="$UPSTREAM_DIR/launcher_status.txt"
for upstream_required in "$UPSTREAM_INPUT_FILES" "$UPSTREAM_INPUT_SHA" \
        "$UPSTREAM_OUTPUT_SHA" "$UPSTREAM_LAUNCHER_STATUS"; do
    [[ -s "$upstream_required" ]] || {
        printf 'missing or empty upstream production-synthesis evidence: %s\n' \
            "$upstream_required" >&2
        exit 2
    }
done

# A completed producer is the normal lineage. A producer that wrote both
# checkpoints and then failed only on a known in-memory structural-query
# discrepancy may be recovered by this independent reopen audit. Keep the two
# cases explicit so a recovered checkpoint is never represented as a
# successful synthesis launcher.
UPSTREAM_LINEAGE_MODE=completed_production_synth
UPSTREAM_SUMMARY_STATUS=V5_PRODUCTION_RESOURCE_PASS
UPSTREAM_VIVADO_EXIT_CODE=0
UPSTREAM_RECOVERY_FAILURE_SIGNATURE=NONE
if [[ ! -e "$UPSTREAM_SUMMARY" ]]; then
    UPSTREAM_LINEAGE_MODE=recovered_post_opt_after_in_memory_structural_audit
    UPSTREAM_SUMMARY_STATUS=ABSENT_AFTER_AUDIT_FAILURE
    UPSTREAM_VIVADO_EXIT_CODE=1
    recovery_signature_count=0
    for recovery_signature in \
        'mlp_local_clear_protected_ff count mismatch: expected=2 actual=1' \
        'mlp_central_clear_branch_endpoints count mismatch: expected=2 actual=9530' \
        'mlp_central_clear_branch_endpoints count mismatch: expected=2 actual=9528' \
        'swiglu_row_clear_ff_per_leaf count mismatch: expected=1 actual=0'; do
        signature_rows="$(grep -Fxc -- "$recovery_signature" \
            "$UPSTREAM_DIR/vivado.log" 2>/dev/null || true)"
        if [[ "$signature_rows" -gt 1 ]]; then
            printf 'duplicate recoverable synthesis failure signature: %s\n' \
                "$recovery_signature" >&2
            exit 2
        fi
        if [[ "$signature_rows" -eq 1 ]]; then
            UPSTREAM_RECOVERY_FAILURE_SIGNATURE="$recovery_signature"
            ((recovery_signature_count += 1))
        fi
    done
    if [[ "$recovery_signature_count" -ne 1 ]]; then
        printf 'synthesis failure is not one uniquely recoverable in-memory audit signature\n' >&2
        exit 2
    fi
elif [[ ! -s "$UPSTREAM_SUMMARY" ]]; then
    printf 'empty upstream synthesis summary is not recoverable: %s\n' \
        "$UPSTREAM_SUMMARY" >&2
    exit 2
fi

require_exact_line() {
    local literal="$1" file="$2" label="${3:-field}" key
    key="${literal%%=*}"
    if [[ "$(grep -Fxc -- "$literal" "$file" 2>/dev/null || true)" -ne 1 ]]; then
        printf '%s exact gate failed: %s\n' "$label" "$literal" >&2
        return 1
    fi
    if [[ "$(grep -Ec "^${key}=" "$file" 2>/dev/null || true)" -ne 1 ]]; then
        printf '%s field is missing or duplicated: %s\n' "$label" "$key" >&2
        return 1
    fi
}

validate_upstream_lineage() {
    local phase="$1" row path row_path row_sha required_output
    local input_count=0 output_count=0 actual_output_count=0 post_opt_count=0
    local -A listed_inputs=() output_paths=()

    if [[ "$UPSTREAM_LINEAGE_MODE" == completed_production_synth ]]; then
        require_exact_line 'status=V5_PRODUCTION_RESOURCE_PASS' \
            "$UPSTREAM_SUMMARY" 'upstream synthesis summary' || return 1
        for upstream_literal in \
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
            'attention_center_subshard_instances=4' \
            'attention_leaf_shard_instances=6' \
            'compact_input_frontend_dsp48e2=8' \
            'compact_input_base_frontend_dsp48e2=8' \
            'compact_input_quantizer_instances=4' \
            'compact_input_quantizer_dsp48e2=0' \
            'compact_input_capture_contract=48x256' \
            'compact_input_capture_ff=12288' \
            'compact_input_capture_controls=48' \
            'compact_input_capture_loads=256/256' \
            'down_activation_capture_contract=16x280' \
            'down_activation_capture_owners=16' \
            'down_activation_capture_ff=4480' \
            'down_activation_capture_loads=280/280' \
            'gate_accum_instances=2' \
            'gate_accum_write_controls=16' \
            'gate_accum_finalize_owners=16' \
            'down_accum_instances=2' \
            'down_guard_capture_contract=16x444' \
            'down_guard_capture_controls=16' \
            'down_guard_capture_ff=7104' \
            'down_guard_capture_loads=444/444' \
            'down_output_capture_contract=16x288' \
            'down_output_capture_controls=16' \
            'down_output_capture_ff=4608' \
            'down_output_capture_loads=288/288' \
            'serial_reset_lut2_domains=3' \
            'serial_reset_protected_domains=3' \
            'swiglu_frontend_dsp48e2=72' \
            'swiglu_hadamard_dsp48e2=64' \
            'swiglu_quantizer_dsp48e2=0' \
            'swiglu_silu_dsp48e2=4' \
            'swiglu_frontend_ramb36e2=40' \
            'swiglu_row_ring_ramb36e2=28' \
            'swiglu_silu_ramb36e2=12' \
            'swiglu_other_ramb36e2=0' \
            'dsp48e2=5449' \
            'dsp_required=5449' \
            'uram288=752' \
            'ramb36e2=829' \
            'ramb18e2=22' \
            'post_opt_data_bufg=0' \
            'protected_structure_ok=1' \
            'post_opt_data_bufg_ok=1' \
            'attention_projection_ok=1' \
            'compact_input_frontend_ok=1' \
            'swiglu_frontend_ok=1' \
            'swiglu_bram_ok=1' \
            'no_clip_quantizer_dsp_ok=1' \
            'attention_local_store_ok=1' \
            'hard_resource_ok=1'; do
            require_exact_line "$upstream_literal" "$UPSTREAM_SUMMARY" \
                'upstream synthesis summary' || return 1
        done
        require_exact_line 'vivado_exit_code=0' "$UPSTREAM_LAUNCHER_STATUS" \
            'upstream synthesis launcher' || return 1
    else
        require_exact_line 'vivado_exit_code=1' "$UPSTREAM_LAUNCHER_STATUS" \
            'recoverable synthesis launcher' || return 1
        [[ "$(grep -Fxc -- 'synth_design completed successfully' \
                "$UPSTREAM_DIR/vivado.log" 2>/dev/null || true)" -eq 1 ]] || {
            printf 'recoverable synthesis log lacks unique synth_design success (%s)\n' \
                "$phase" >&2
            return 1
        }
        [[ "$(grep -Fxc -- 'opt_design completed successfully' \
                "$UPSTREAM_DIR/vivado.log" 2>/dev/null || true)" -eq 1 ]] || {
            printf 'recoverable synthesis log lacks unique opt_design success (%s)\n' \
                "$phase" >&2
            return 1
        }
        [[ "$(grep -Fxc -- "$UPSTREAM_RECOVERY_FAILURE_SIGNATURE" \
                "$UPSTREAM_DIR/vivado.log" 2>/dev/null || true)" -eq 1 ]] || {
            printf 'recoverable synthesis log has an unexpected failure signature (%s)\n' \
                "$phase" >&2
            return 1
        }
        [[ "$(grep -Ec '^[A-Za-z0-9_]+ count mismatch: expected=[0-9]+ actual=[0-9]+$' \
                "$UPSTREAM_DIR/vivado.log" 2>/dev/null || true)" -eq 1 ]] || {
            printf 'recoverable synthesis log has multiple structural failures (%s)\n' \
                "$phase" >&2
            return 1
        }
        [[ "$(grep -Eic '^[[:space:]]*(ERROR|FATAL):' \
                "$UPSTREAM_DIR/vivado.log" 2>/dev/null || true)" -eq 0 ]] || {
            printf 'recoverable synthesis log contains ERROR/FATAL diagnostics (%s)\n' \
                "$phase" >&2
            return 1
        }
        [[ "$(grep -Fc -- "The checkpoint '$HAP_DCP' has been generated." \
                "$UPSTREAM_DIR/vivado.log" 2>/dev/null || true)" -eq 1 ]] || {
            printf 'recoverable synthesis log lacks unique post-opt checkpoint write (%s)\n' \
                "$phase" >&2
            return 1
        }
    fi
    require_exact_line 'input_sha_recheck_exit_code=0' \
        "$UPSTREAM_LAUNCHER_STATUS" 'upstream synthesis launcher' || return 1
    upstream_status_rows="$(grep -Ec \
        '^(vivado_exit_code|input_sha_recheck_exit_code|upstream_provenance_recheck_exit_code)=' \
        "$UPSTREAM_LAUNCHER_STATUS" 2>/dev/null || true)"
    if grep -q '^upstream_provenance_recheck_exit_code=' \
            "$UPSTREAM_LAUNCHER_STATUS"; then
        require_exact_line 'upstream_provenance_recheck_exit_code=0' \
            "$UPSTREAM_LAUNCHER_STATUS" \
            'upstream synthesis launcher' || return 1
        expected_upstream_status_rows=3
    else
        expected_upstream_status_rows=2
    fi
    [[ "$upstream_status_rows" -eq "$expected_upstream_status_rows" ]] || {
        printf 'upstream synthesis launcher contains unexpected status fields (%s)\n' \
            "$phase" >&2
        return 1
    }

    if ! (cd / && sha256sum -c --strict "$UPSTREAM_INPUT_SHA") \
            > "$HAP_AUDIT_DIR/upstream_input_sha_${phase}.txt" 2>&1; then
        printf 'upstream synthesis input SHA verification failed (%s)\n' \
            "$phase" >&2
        return 1
    fi
    if ! (cd / && sha256sum -c --strict "$UPSTREAM_OUTPUT_SHA") \
            > "$HAP_AUDIT_DIR/upstream_output_sha_${phase}.txt" 2>&1; then
        printf 'upstream synthesis output SHA verification failed (%s)\n' \
            "$phase" >&2
        return 1
    fi

    while IFS= read -r path || [[ -n "$path" ]]; do
        [[ -n "$path" && "$path" != *$'\n'* ]] || {
            printf 'malformed upstream INPUT_FILES row (%s)\n' "$phase" >&2
            return 1
        }
        [[ "$path" == /* && "$(readlink -f -- "$path")" == "$path" ]] || {
            printf 'non-canonical upstream input path (%s): %s\n' \
                "$phase" "$path" >&2
            return 1
        }
        [[ -z "${listed_inputs[$path]+x}" ]] || {
            printf 'duplicate upstream INPUT_FILES row (%s): %s\n' \
                "$phase" "$path" >&2
            return 1
        }
        listed_inputs["$path"]=1
        ((input_count += 1))
    done < "$UPSTREAM_INPUT_FILES"
    (( input_count > 0 )) || {
        printf 'upstream INPUT_FILES is empty (%s)\n' "$phase" >&2
        return 1
    }

    while IFS= read -r row || [[ -n "$row" ]]; do
        [[ "$row" =~ ^([0-9a-f]{64})[[:space:]][[:space:]](.+)$ ]] || {
            printf 'malformed upstream input SHA row (%s): %s\n' \
                "$phase" "$row" >&2
            return 1
        }
        row_path="${BASH_REMATCH[2]}"
        [[ -n "${listed_inputs[$row_path]+x}" ]] || {
            printf 'upstream input SHA path absent from INPUT_FILES (%s): %s\n' \
                "$phase" "$row_path" >&2
            return 1
        }
        unset 'listed_inputs[$row_path]'
    done < "$UPSTREAM_INPUT_SHA"
    if [[ "${#listed_inputs[@]}" -ne 0 ]]; then
        printf 'upstream INPUT_FILES has unhashed rows (%s)\n' "$phase" >&2
        return 1
    fi

    while IFS= read -r row || [[ -n "$row" ]]; do
        [[ "$row" =~ ^([0-9a-f]{64})[[:space:]][[:space:]](.+)$ ]] || {
            printf 'malformed upstream output SHA row (%s): %s\n' \
                "$phase" "$row" >&2
            return 1
        }
        row_sha="${BASH_REMATCH[1]}"
        row_path="${BASH_REMATCH[2]}"
        [[ "$row_path" == "$UPSTREAM_DIR/"* && \
           "$(dirname -- "$row_path")" == "$UPSTREAM_DIR" ]] || {
            printf 'upstream output escapes artifact root (%s): %s\n' \
                "$phase" "$row_path" >&2
            return 1
        }
        [[ -z "${output_paths[$row_path]+x}" ]] || {
            printf 'duplicate upstream output SHA path (%s): %s\n' \
                "$phase" "$row_path" >&2
            return 1
        }
        output_paths["$row_path"]="$row_sha"
        ((output_count += 1))
        [[ "$(basename -- "$row_path")" != 'post_opt.dcp' ]] || \
            ((post_opt_count += 1))
    done < "$UPSTREAM_OUTPUT_SHA"

    while IFS= read -r -d '' path; do
        ((actual_output_count += 1))
        [[ -n "${output_paths[$path]+x}" ]] || {
            printf 'upstream artifact has an unhashed output (%s): %s\n' \
                "$phase" "$path" >&2
            return 1
        }
    done < <(find "$UPSTREAM_DIR" -maxdepth 1 -type f -size +0c \
        ! -name OUTPUT_SHA256SUMS -print0)
    while IFS= read -r -d '' path; do
        [[ -s "$path" ]] || {
            printf 'upstream artifact contains an empty root file (%s): %s\n' \
                "$phase" "$path" >&2
            return 1
        }
    done < <(find "$UPSTREAM_DIR" -maxdepth 1 -type f -print0)
    (( output_count == actual_output_count )) || {
        printf 'upstream output manifest is not complete (%s): manifest=%d actual=%d\n' \
            "$phase" "$output_count" "$actual_output_count" >&2
        return 1
    }
    (( output_count > 0 && post_opt_count == 1 )) || {
        printf 'upstream output manifest requires exactly one post_opt.dcp (%s): %d\n' \
            "$phase" "$post_opt_count" >&2
        return 1
    }
    [[ -n "${output_paths[$HAP_DCP]+x}" && \
       "${output_paths[$HAP_DCP]}" == "$HAP_EXPECTED_DCP_SHA256" ]] || {
        printf 'selected DCP is not the unique upstream post_opt output (%s)\n' \
            "$phase" >&2
        return 1
    }
    local -a required_outputs=(INPUT_FILES INPUT_SHA256SUMS \
            post_synth.dcp post_opt.dcp utilization_post_synth.rpt \
            utilization_hier_post_synth.rpt utilization_post_opt.rpt \
            utilization_hier_post_opt.rpt timing_post_opt.rpt \
            swiglu_rowlocal_static_check.txt \
            cohort16_production_static_check.txt vivado.log vivado.jou \
            launcher_status.txt input_sha_postcheck.txt)
    if [[ "$UPSTREAM_LINEAGE_MODE" == completed_production_synth ]]; then
        required_outputs+=(summary.txt)
    fi
    for required_output in "${required_outputs[@]}"; do
        path="$UPSTREAM_DIR/$required_output"
        [[ -s "$path" && -n "${output_paths[$path]+x}" ]] || {
            printf 'required production-synthesis output is missing or unhashed (%s): %s\n' \
                "$phase" "$path" >&2
            return 1
        }
    done
    printf '%s\n' \
        'status=V5_UPSTREAM_PRODUCTION_SYNTH_LINEAGE_PASS' \
        "phase=$phase" \
        "lineage_mode=$UPSTREAM_LINEAGE_MODE" \
        "input_file_count=$input_count" \
        "output_file_count=$output_count" \
        "post_opt_manifest_match_count=$post_opt_count"
    return 0
}

fail_pre_lineage() {
    local rc="${1:-1}"
    if [[ -n "${HAP_AUDIT_DIR:-}" && -d "$HAP_AUDIT_DIR" ]]; then
        printf '%s\n' \
            'status=FAIL' \
            "final_exit_code=$rc" \
            'vivado_exit_code=NOT_STARTED' \
            'upstream_lineage_precheck=FAIL' \
            'checkpoint_written=0' \
            'implementation_commands_run=0' \
            > "$HAP_AUDIT_DIR/launcher_status.txt"
        mapfile -d '' pre_fail_outputs < <(find "$HAP_AUDIT_DIR" \
            -maxdepth 1 -type f ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
        if [[ "${#pre_fail_outputs[@]}" -ne 0 ]]; then
            sha256sum -- "${pre_fail_outputs[@]}" \
                > "$HAP_AUDIT_DIR/OUTPUT_SHA256SUMS"
            (cd / && sha256sum -c --strict \
                "$HAP_AUDIT_DIR/OUTPUT_SHA256SUMS") || true
        fi
        printf 'V5 post-opt upstream lineage precheck failed; evidence retained in %s\n' \
            "$HAP_AUDIT_DIR" >&2
        printf '%s\n' "$HAP_AUDIT_DIR"
    fi
    exit "$rc"
}

# This audit is an independent reopen and must never share a Vivado process or
# compete with a running batch implementation/query process.
mapfile -t active_batch < <(pgrep -u "$(id -u)" -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; post-opt audit not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi

# Fail closed if an implementation, constraint mutation, dynamic-dispatch, or
# design/checkpoint writer is ever introduced into the read-only audit Tcl.
# Full-line Tcl comments are removed so documentation cannot trip the gate.
audit_code="$(sed -E '/^[[:space:]]*#/d' "$AUDIT_TCL")"
if grep -Eq \
    '(^|[^[:alnum:]_])(synth_design|opt_design|power_opt_design|place_design|phys_opt_design|route_design|link_design|read_checkpoint|launch_runs|wait_on_run|open_run|reset_run|reset_runs|create_run|delete_runs|set_property|source|eval|uplevel|write_[[:alnum:]_]+)([^[:alnum:]_]|$)' \
    <<<"$audit_code"; then
    printf 'post-opt audit Tcl contains a forbidden mutation/dynamic command\n' >&2
    exit 2
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
audit_dir_requested="${HAP_AUDIT_DIR:-$(dirname "$HAP_DCP")/v5_post_opt_reopen_audit_$STAMP}"
export HAP_AUDIT_DIR="$(readlink -m -- "$audit_dir_requested")"
[[ "$HAP_AUDIT_DIR" != *$'\n'* ]] || {
    printf 'newline is forbidden in audit output path: %q\n' \
        "$HAP_AUDIT_DIR" >&2
    exit 2
}
if [[ -e "$HAP_AUDIT_DIR" ]]; then
    printf 'post-opt audit output already exists: %s\n' "$HAP_AUDIT_DIR" >&2
    exit 2
fi
mkdir "$HAP_AUDIT_DIR"

export HAP_AUDIT_INPUT_SHA="$HAP_AUDIT_DIR/INPUT_SHA256SUMS"
export HAP_AUDIT_LAUNCHER="$LAUNCHER"
export HAP_EXPECTED_DCP_SHA256
HAP_EXPECTED_DCP_SHA256="$(sha256sum -- "$HAP_DCP" | awk '{print $1}')"

# Validate the completed synthesis artifact before deriving a new audit
# manifest from it.  In addition to checking the producer's two manifests,
# freeze every recursive production input and every non-empty root artifact in
# a separate lineage manifest.  Including INPUT_SHA256SUMS and
# OUTPUT_SHA256SUMS here freezes the producer manifests' own digests, so an
# input/output plus its producer manifest cannot be replaced during Vivado.
validate_upstream_lineage pre \
    > "$HAP_AUDIT_DIR/upstream_contract_precheck.txt" 2>&1 || \
    fail_pre_lineage 1
declare -A lineage_seen=()
lineage_files=()
while IFS= read -r lineage_path || [[ -n "$lineage_path" ]]; do
    if [[ -z "${lineage_seen[$lineage_path]+x}" ]]; then
        lineage_seen["$lineage_path"]=1
        lineage_files+=("$lineage_path")
    fi
done < "$UPSTREAM_INPUT_FILES"
while IFS= read -r -d '' lineage_path; do
    [[ "$lineage_path" != *$'\n'* ]] || {
        printf 'newline is forbidden in upstream artifact path: %q\n' \
            "$lineage_path" >&2
        fail_pre_lineage 1
    }
    if [[ -z "${lineage_seen[$lineage_path]+x}" ]]; then
        lineage_seen["$lineage_path"]=1
        lineage_files+=("$lineage_path")
    fi
done < <(find "$UPSTREAM_DIR" -maxdepth 1 -type f -size +0c -print0)
printf '%s\n' "${lineage_files[@]}" | LC_ALL=C sort -u \
    > "$HAP_AUDIT_DIR/UPSTREAM_LINEAGE_FILES"
xargs -d '\n' sha256sum < "$HAP_AUDIT_DIR/UPSTREAM_LINEAGE_FILES" \
    > "$HAP_AUDIT_DIR/UPSTREAM_LINEAGE_SHA256SUMS"
UPSTREAM_LINEAGE_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_AUDIT_DIR/UPSTREAM_LINEAGE_SHA256SUMS" | awk '{print $1}')"
UPSTREAM_INPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$UPSTREAM_INPUT_SHA" | awk '{print $1}')"
UPSTREAM_OUTPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$UPSTREAM_OUTPUT_SHA" | awk '{print $1}')"
UPSTREAM_INPUT_FILES_SHA256="$(sha256sum -- \
    "$UPSTREAM_INPUT_FILES" | awk '{print $1}')"
# Close the pre-run race between producer-manifest verification and lineage
# construction: verify the producer contract again, then make the frozen
# lineage verification the last read of upstream data before Vivado starts.
validate_upstream_lineage frozen \
    > "$HAP_AUDIT_DIR/upstream_contract_frozen_precheck.txt" 2>&1 || \
    fail_pre_lineage 1
(cd / && sha256sum -c --strict \
    "$HAP_AUDIT_DIR/UPSTREAM_LINEAGE_SHA256SUMS") \
    > "$HAP_AUDIT_DIR/upstream_lineage_sha_precheck.txt" 2>&1 || \
    fail_pre_lineage 1
[[ "$(sha256sum -- "$HAP_AUDIT_DIR/UPSTREAM_LINEAGE_SHA256SUMS" | \
        awk '{print $1}')" == "$UPSTREAM_LINEAGE_MANIFEST_SHA256" ]] || \
    fail_pre_lineage 1
printf '%s\n' \
    'status=V5_UPSTREAM_PRODUCTION_SYNTH_LINEAGE_FROZEN' \
    "upstream_artifact=$UPSTREAM_DIR" \
    "upstream_post_opt_dcp=$HAP_DCP" \
    "upstream_post_opt_sha256=$HAP_EXPECTED_DCP_SHA256" \
    "upstream_input_files_sha256=$UPSTREAM_INPUT_FILES_SHA256" \
    "upstream_input_manifest_sha256=$UPSTREAM_INPUT_MANIFEST_SHA256" \
    "upstream_output_manifest_sha256=$UPSTREAM_OUTPUT_MANIFEST_SHA256" \
    "upstream_lineage_manifest_sha256=$UPSTREAM_LINEAGE_MANIFEST_SHA256" \
    "upstream_lineage_file_count=${#lineage_files[@]}" \
    "lineage_mode=$UPSTREAM_LINEAGE_MODE" \
    "recovery_failure_signature=$UPSTREAM_RECOVERY_FAILURE_SIGNATURE" \
    "summary_status=$UPSTREAM_SUMMARY_STATUS" \
    "vivado_exit_code=$UPSTREAM_VIVADO_EXIT_CODE" \
    'input_sha_recheck_exit_code=0' \
    'post_opt_manifest_match_count=1' \
    > "$HAP_AUDIT_DIR/upstream_lineage.txt"

printf '%s\n' "$HAP_DCP" "$AUDIT_TCL" "$LAUNCHER" \
    > "$HAP_AUDIT_DIR/INPUT_FILES"
sha256sum -- "$HAP_DCP" "$AUDIT_TCL" "$LAUNCHER" \
    > "$HAP_AUDIT_INPUT_SHA"
export HAP_AUDIT_INPUT_MANIFEST_SHA256
HAP_AUDIT_INPUT_MANIFEST_SHA256="$(sha256sum -- "$HAP_AUDIT_INPUT_SHA" | awk '{print $1}')"
(cd / && sha256sum -c --strict "$HAP_AUDIT_INPUT_SHA") \
    > "$HAP_AUDIT_DIR/input_sha_precheck.txt" 2>&1

cd "$ROOT"
set +e
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/audit_attention_mlp_production_v5_post_opt_dcp.tcl \
    -log "$HAP_AUDIT_DIR/vivado.log" \
    -journal "$HAP_AUDIT_DIR/vivado.jou"
vivado_rc=$?
set -e

# The inputs are checked after every Vivado return, including a failed return.
# The separately frozen manifest digest prevents replacing both an input and
# its manifest row during a long audit.
set +e
(cd / && sha256sum -c --strict "$HAP_AUDIT_INPUT_SHA") \
    > "$HAP_AUDIT_DIR/input_sha_postcheck.txt" 2>&1
input_recheck_rc=$?
actual_manifest_sha="$(sha256sum -- "$HAP_AUDIT_INPUT_SHA" 2>/dev/null | awk '{print $1}')"
manifest_sha_rc=$?
validate_upstream_lineage post \
    > "$HAP_AUDIT_DIR/upstream_contract_postcheck.txt" 2>&1
upstream_contract_recheck_rc=$?
(cd / && sha256sum -c --strict \
    "$HAP_AUDIT_DIR/UPSTREAM_LINEAGE_SHA256SUMS") \
    > "$HAP_AUDIT_DIR/upstream_lineage_sha_postcheck.txt" 2>&1
upstream_lineage_recheck_rc=$?
actual_lineage_manifest_sha="$(sha256sum -- \
    "$HAP_AUDIT_DIR/UPSTREAM_LINEAGE_SHA256SUMS" 2>/dev/null | awk '{print $1}')"
lineage_manifest_sha_rc=$?
set -e
manifest_sha_match=0
if [[ "$manifest_sha_rc" -eq 0 && \
      "$actual_manifest_sha" == "$HAP_AUDIT_INPUT_MANIFEST_SHA256" ]]; then
    manifest_sha_match=1
fi
upstream_lineage_manifest_sha_match=0
if [[ "$lineage_manifest_sha_rc" -eq 0 && \
      "$actual_lineage_manifest_sha" == \
      "$UPSTREAM_LINEAGE_MANIFEST_SHA256" ]]; then
    upstream_lineage_manifest_sha_match=1
fi

# Vivado normally creates both files.  Preserve an explicit marker if it
# returned before doing so, so failure evidence still has hashable log/journal
# artifacts rather than silently omitting them.
if [[ ! -e "$HAP_AUDIT_DIR/vivado.log" ]]; then
    printf 'launcher_note=Vivado did not create vivado.log\n' \
        > "$HAP_AUDIT_DIR/vivado.log"
fi
if [[ ! -e "$HAP_AUDIT_DIR/vivado.jou" ]]; then
    printf 'launcher_note=Vivado did not create vivado.jou\n' \
        > "$HAP_AUDIT_DIR/vivado.jou"
fi

validate_pass_outputs() {
    local required literal total_dsp clb_lut numeric_field
    local -a field_rows
    local -A numeric_values=()
    for required in audit.txt attention_local_store_boundaries.tsv \
            attention_local_store_resources.tsv utilization_reopen.rpt \
            utilization_hier_reopen.rpt vivado.log vivado.jou \
            UPSTREAM_LINEAGE_FILES UPSTREAM_LINEAGE_SHA256SUMS \
            upstream_lineage.txt upstream_contract_precheck.txt \
            upstream_contract_frozen_precheck.txt \
            upstream_contract_postcheck.txt upstream_input_sha_pre.txt \
            upstream_output_sha_pre.txt upstream_input_sha_frozen.txt \
            upstream_output_sha_frozen.txt \
            upstream_lineage_sha_precheck.txt \
            upstream_input_sha_post.txt upstream_output_sha_post.txt \
            upstream_lineage_sha_postcheck.txt; do
        [[ -s "$HAP_AUDIT_DIR/$required" ]] || {
            printf 'missing or empty post-opt audit output: %s\n' "$required" >&2
            return 1
        }
    done

    local summary="$HAP_AUDIT_DIR/audit.txt"
    local -a exact_lines=(
        'status=V5_POST_OPT_DCP_AUDIT_PASS'
        'evidence_class=V5_POST_OPT_READ_ONLY_REOPEN'
        "dcp=$HAP_DCP"
        "input_dcp_sha256=$HAP_EXPECTED_DCP_SHA256"
        "input_manifest_sha256=$HAP_AUDIT_INPUT_MANIFEST_SHA256"
        'top=hap_attention_mlp_production_core'
        'part=xcvu9p-flga2104-2L-e'
        'production_profile=cohort16'
        'attention_board_module=hap_attention_board_cohort16_core'
        'attention_cohort16_board_instances=1'
        'attention_legacy_board_instances=0'
        'attention_cohort16_compute_instances=1'
        'attention_legacy_compute_instances=0'
        'attention_query_store_instances=1'
        'attention_postprocess_store_instances=1'
        'attention_postprocess_row_bank_instances=16'
        'attention_context_store_instances=1'
        'attention_context_store_ramb36e2=44'
        'attention_context_store_ramb18e2=0'
        'attention_context_store_lutram_primitives=0'
        'attention_context_store_dsp48e2=0'
        'attention_context_store_uram288=0'
        'attention_projection16_instances=1'
        'attention_projection8_instances=0'
        'attention_lane_instances=128'
        'attention_dual_accumulator_instances=6'
        'attention_local_accumulator_contexts=12'
        'attention_region2_instances=1'
        'attention_region2_dual_accumulator_instances=1'
        'attention_region2_buffered_accumulator_instances=1'
        'attention_region2_lower_bank_instances=1'
        'attention_region2_upper_bank_instances=1'
        'attention_region2_g_buffered_input_present=1'
        'attention_region2_buffer_occupancy_ff=2'
        'attention_region2_buffer_partition_ok=1'
        'attention_region2_elastic_fifo_ok=1'
        'attention_projection_dsp48e2=2240'
        'attention_array_dsp48e2=2176'
        'attention_frontend_dsp48e2=64'
        'attention_base_frontend_dsp48e2=64'
        'no_clip_s27_quantizer_instances=12'
        'attention_quantizer_instances=8'
        'attention_quantizer_dsp48e2=0'
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
        'v5_serial_instances=1'
        'old_serial_instances=0'
        'v5_shared_instances=1'
        'v5_branch_instances=2'
        'v5_kernel12_instances=2'
        'old_kernel16_instances=0'
        'history2_repack_instances=2'
        'generic_repack_instances=0'
        'swiglu_frontend_instances=1'
        'swiglu_row_leaf_instances=2'
        'swiglu_unique_hadamard_instances=1'
        'swiglu_fold2_hadamard_instances=0'
        'swiglu_quantizer_instances=4'
        'swiglu_silu_instances=2'
        'swiglu_frontend_dsp48e2=72'
        'swiglu_hadamard_dsp48e2=64'
        'swiglu_quantizer_dsp48e2=0'
        'swiglu_silu_dsp48e2=4'
        'swiglu_metadata_address_dsp48e2=4'
        'swiglu_metadata_address_dsp_r1=3'
        'swiglu_metadata_address_dsp_r2=1'
        'swiglu_metadata_address_dsp_unexpected='
        'swiglu_metadata_address_dsp_identity_ok=1'
        'swiglu_other_dsp48e2=0'
        'swiglu_frontend_ramb36e2=40'
        'swiglu_row_ring_ramb36e2=28'
        'swiglu_silu_ramb36e2=12'
        'swiglu_other_ramb36e2=0'
        'attention_col3_array_instances=1'
        'attention_old_array_instances=0'
        'attention_left2_shard_instances=1'
        'attention_center12_shard_instances=1'
        'attention_right2_shard_instances=1'
        'attention_center_subshard_instances=4'
        'attention_leaf_shard_instances=6'
        'compact_input_frontend_instances=1'
        'compact_input_frontend_dsp48e2=8'
        'compact_input_base_frontend_dsp48e2=8'
        'compact_input_quantizer_instances=4'
        'compact_input_quantizer_dsp48e2=0'
        'compact_input_capture_contract=48x256'
        'compact_input_capture_ff=12288'
        'compact_input_capture_controls=48'
        'compact_input_capture_loads=256/256'
        'down_activation_cache_instances=1'
        'down_activation_capture_contract=16x280'
        'down_activation_capture_owners=16'
        'down_activation_capture_ff=4480'
        'down_activation_capture_loads=280/280'
        'gate_accum_instances=2'
        'gate_accum_write_controls=16'
        'gate_accum_finalize_owners=16'
        'down_accum_instances=2'
        'down_guard_capture_contract=16x444'
        'down_guard_capture_controls=16'
        'down_guard_capture_ff=7104'
        'down_guard_capture_loads=444/444'
        'down_output_capture_contract=16x288'
        'down_output_capture_controls=16'
        'down_output_capture_ff=4608'
        'down_output_capture_loads=288/288'
        'serial_reset_lut2_domains=3'
        'serial_reset_protected_domains=3'
        'down_elastic2_instances=2'
        'mlp_local_clear_ff=2'
        'mlp_local_clear_protected_ff=2'
        'branch0_local_clear_ff=1'
        'branch1_local_clear_ff=1'
        'swiglu_local_clear_ff=8'
        'swiglu_local_clear_protected_ff=8'
        'swiglu_control_clear_ff=1'
        'swiglu_hadamard_clear_ff=1'
        'swiglu_quantizer_clear_ff=4'
        'swiglu_row_clear_ff=2'
        'swiglu_direct_clear_bypass_state=0'
        'mlp_central_clear_ff=1'
        'mlp_central_clear_branch_endpoints=2'
        'mlp_central_clear_direct_branch_state=0'
        'metadata_leaf_instances=4'
        'metadata_local_wr_en_ff=4'
        'metadata_local_wr_addr_ff=70'
        'metadata_local_wr_data_ff=896'
        'metadata_local_write_protected_ff=970'
        'mlp_capture_leaf_instances=1632'
        'mlp_capture_leaf_lut1=1632'
        'branch0_capture_leaf_instances=816'
        'branch1_capture_leaf_instances=816'
        'branch0_capture_leaf_lut1=816'
        'branch1_capture_leaf_lut1=816'
        'kernel_dsp48e2=3072'
        'branch0_dsp48e2=1536'
        'branch1_dsp48e2=1536'
        'dsp48e2=5449'
        'dsp_required=5449'
        'dsp_limit=5500'
        'uram288=752'
        'uram_required=752'
        'ramb36e2=829'
        'ramb18e2=22'
        'clb_lut_limit=1064016'
        'post_opt_data_bufg=0'
        'hierarchy_ok=1'
        'protected_structure_ok=1'
        'post_opt_data_bufg_ok=1'
        'kernel_ok=1'
        'attention_projection_ok=1'
        'compact_input_frontend_ok=1'
        'swiglu_frontend_ok=1'
        'swiglu_bram_ok=1'
        'no_clip_quantizer_dsp_ok=1'
        'attention_local_store_ok=1'
        'resource_ok=1'
        'checkpoint_written=0'
        'implementation_commands_run=0'
    )
    for literal in "${exact_lines[@]}"; do
        require_exact_line "$literal" "$summary" 'post-opt audit' || return 1
    done
    if [[ "$(grep -Ec '^tool=2025\.2([^0-9].*)?$' "$summary" || true)" -ne 1 ]]; then
        printf 'post-opt audit tool-version gate failed\n' >&2
        return 1
    fi
    if [[ "$(grep -Ec '^tool=' "$summary" || true)" -ne 1 ]]; then
        printf 'post-opt audit tool field is missing or duplicated\n' >&2
        return 1
    fi

    for numeric_field in dsp48e2 uram288 ramb36e2 ramb18e2 clb_lut \
            lut_as_logic lut_as_memory clb_register \
            attention_query_store_lut_primitives \
            attention_query_store_srl16e \
            attention_query_store_ff_primitives \
            attention_query_store_ramb36e2 \
            attention_query_store_ramb18e2 \
            attention_query_store_lutram_primitives \
            attention_query_store_dsp48e2 \
            attention_query_store_uram288 \
            attention_query_store_input_pins \
            attention_query_store_output_pins \
            attention_query_store_boundary_nets \
            attention_postprocess_store_lut_primitives \
            attention_postprocess_store_srl16e \
            attention_postprocess_store_ff_primitives \
            attention_postprocess_store_ramb36e2 \
            attention_postprocess_store_ramb18e2 \
            attention_postprocess_store_lutram_primitives \
            attention_postprocess_store_dsp48e2 \
            attention_postprocess_store_uram288 \
            attention_postprocess_store_input_pins \
            attention_postprocess_store_output_pins \
            attention_postprocess_store_boundary_nets \
            attention_context_store_lut_primitives \
            attention_context_store_srl16e \
            attention_context_store_ff_primitives \
            attention_context_store_input_pins \
            attention_context_store_output_pins \
            attention_context_store_boundary_nets \
            attention_region2_buffer_primitives \
            attention_region2_buffer_ff \
            attention_region2_buffer_payload_ff \
            attention_region2_buffer_tag_ff \
            attention_region2_buffer_occupancy_ff; do
        mapfile -t field_rows < <(sed -n "s/^${numeric_field}=//p" "$summary")
        if [[ "${#field_rows[@]}" -ne 1 || ! "${field_rows[0]}" =~ ^[0-9]+$ ]]; then
            printf 'post-opt audit field is missing, duplicate, or non-numeric: %s\n' \
                "$numeric_field" >&2
            return 1
        fi
        numeric_values["$numeric_field"]="${field_rows[0]}"
    done
    total_dsp="${numeric_values[dsp48e2]}"
    clb_lut="${numeric_values[clb_lut]}"
    if (( total_dsp != 5449 )); then
        printf 'post-opt audit DSP identity rejected: %s != 5449\n' \
            "$total_dsp" >&2
        return 1
    fi
    for numeric_field in attention_query_store_input_pins \
            attention_query_store_output_pins \
            attention_query_store_boundary_nets \
            attention_postprocess_store_input_pins \
            attention_postprocess_store_output_pins \
            attention_postprocess_store_boundary_nets \
            attention_context_store_input_pins \
            attention_context_store_output_pins \
            attention_context_store_boundary_nets; do
        if (( numeric_values[$numeric_field] <= 0 )); then
            printf 'post-opt audit owner boundary is empty: %s=%s\n' \
                "$numeric_field" "${numeric_values[$numeric_field]}" >&2
            return 1
        fi
    done
    for numeric_field in attention_region2_buffer_primitives \
            attention_region2_buffer_ff \
            attention_region2_buffer_payload_ff \
            attention_region2_buffer_tag_ff; do
        if (( numeric_values[$numeric_field] <= 0 )); then
            printf 'post-opt audit region2 FIFO state is empty: %s=%s\n' \
                "$numeric_field" "${numeric_values[$numeric_field]}" >&2
            return 1
        fi
    done
    if (( numeric_values[attention_region2_buffer_occupancy_ff] != 2 )); then
        printf 'post-opt audit region2 FIFO occupancy identity rejected: %s != 2\n' \
            "${numeric_values[attention_region2_buffer_occupancy_ff]}" >&2
        return 1
    fi
    if (( numeric_values[attention_region2_buffer_ff] !=
          numeric_values[attention_region2_buffer_payload_ff] +
          numeric_values[attention_region2_buffer_tag_ff] +
          numeric_values[attention_region2_buffer_occupancy_ff] )); then
        printf 'post-opt audit region2 FIFO FF partition is inconsistent\n' >&2
        return 1
    fi
    if (( numeric_values[attention_region2_buffer_primitives] <
          numeric_values[attention_region2_buffer_ff] )); then
        printf 'post-opt audit region2 FIFO primitive count is inconsistent\n' >&2
        return 1
    fi
    if (( clb_lut > 1064016 )); then
        printf 'post-opt audit CLB LUT limit exceeded: %s > 1064016\n' \
            "$clb_lut" >&2
        return 1
    fi

    if grep -Eiq '(^|[^[:alnum:]_])(FAIL|ERROR|FATAL)(:|\[|[[:space:]])' \
            "$HAP_AUDIT_DIR/vivado.log" "$summary"; then
        printf 'post-opt audit rejected FAIL/Error/Fatal marker\n' >&2
        return 1
    fi
    return 0
}

audit_gate_rc=125
if [[ "$vivado_rc" -eq 0 && "$input_recheck_rc" -eq 0 && \
      "$manifest_sha_match" -eq 1 && \
      "$upstream_lineage_recheck_rc" -eq 0 && \
      "$upstream_lineage_manifest_sha_match" -eq 1 && \
      "$upstream_contract_recheck_rc" -eq 0 ]]; then
    set +e
    validate_pass_outputs
    audit_gate_rc=$?
    set -e
fi

final_rc=0
final_status=PASS
if [[ "$vivado_rc" -ne 0 ]]; then
    final_rc="$vivado_rc"
    final_status=FAIL
elif [[ "$input_recheck_rc" -ne 0 || "$manifest_sha_match" -ne 1 || \
        "$upstream_lineage_recheck_rc" -ne 0 || \
        "$upstream_lineage_manifest_sha_match" -ne 1 || \
        "$upstream_contract_recheck_rc" -ne 0 ]]; then
    final_rc=1
    final_status=FAIL
elif [[ "$audit_gate_rc" -ne 0 ]]; then
    final_rc=1
    final_status=FAIL
fi

printf '%s\n' \
    "status=$final_status" \
    "final_exit_code=$final_rc" \
    "vivado_exit_code=$vivado_rc" \
    "input_sha_recheck_exit_code=$input_recheck_rc" \
    "input_manifest_sha_match=$manifest_sha_match" \
    "upstream_lineage_sha_recheck_exit_code=$upstream_lineage_recheck_rc" \
    "upstream_lineage_manifest_sha_match=$upstream_lineage_manifest_sha_match" \
    "upstream_contract_recheck_exit_code=$upstream_contract_recheck_rc" \
    "upstream_artifact=$UPSTREAM_DIR" \
    "upstream_lineage_mode=$UPSTREAM_LINEAGE_MODE" \
    "upstream_recovery_failure_signature=$UPSTREAM_RECOVERY_FAILURE_SIGNATURE" \
    "upstream_post_opt_sha256=$HAP_EXPECTED_DCP_SHA256" \
    "upstream_input_manifest_sha256=$UPSTREAM_INPUT_MANIFEST_SHA256" \
    "upstream_output_manifest_sha256=$UPSTREAM_OUTPUT_MANIFEST_SHA256" \
    "upstream_lineage_manifest_sha256=$UPSTREAM_LINEAGE_MANIFEST_SHA256" \
    "audit_gate_exit_code=$audit_gate_rc" \
    'checkpoint_written=0' \
    'implementation_commands_run=0' \
    > "$HAP_AUDIT_DIR/launcher_status.txt"

# Hash every file produced in the fresh evidence directory, on both PASS and
# FAIL paths.  Verify that output manifest before returning to the caller.
mapfile -d '' audit_outputs < <(find "$HAP_AUDIT_DIR" -maxdepth 1 \
    -type f ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
if [[ "${#audit_outputs[@]}" -eq 0 ]]; then
    printf 'post-opt audit produced no hashable evidence\n' >&2
    exit 1
fi
sha256sum -- "${audit_outputs[@]}" > "$HAP_AUDIT_DIR/OUTPUT_SHA256SUMS"
(cd / && sha256sum -c --strict "$HAP_AUDIT_DIR/OUTPUT_SHA256SUMS")

if [[ "$final_rc" -ne 0 ]]; then
    printf 'V5 post-opt read-only audit failed; evidence retained in %s\n' \
        "$HAP_AUDIT_DIR" >&2
    printf '%s\n' "$HAP_AUDIT_DIR"
    exit "$final_rc"
fi

cat "$HAP_AUDIT_DIR/audit.txt"
printf '%s\n' "$HAP_AUDIT_DIR"
