#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_PRODUCTION_PROFILE=cohort16
export HAP_ATTENTION_BOARD_MODULE=hap_attention_board_cohort16_core
export HAP_JOBS="${HAP_JOBS:-32}"
export HAP_PRODUCTION_MANIFEST="$ROOT/vivado/manifests/attention_mlp_production_v5_cohort16_sources.list"
MANIFEST="$HAP_PRODUCTION_MANIFEST"
COHORT16_STATIC_CHECKER="$ROOT/vivado/scripts/check_attention_mlp_production_v5_cohort16_static.sh"
requested_report="${HAP_REPORT_DIR:-$ROOT/vivado/reports/production_v5_elaboration_$STAMP}"
requested_build="${HAP_BUILD_DIR:-$ROOT/vivado/build/production_v5_elaboration_$STAMP}"
export HAP_REPORT_DIR="$(readlink -m -- "$requested_report")"
export HAP_BUILD_DIR="$(readlink -m -- "$requested_build")"

[[ -x "$VIVADO" ]] || {
    printf 'Vivado executable is missing: %s\n' "$VIVADO" >&2
    exit 2
}
[[ "$HAP_JOBS" == 32 ]] || {
    printf 'V5 production elaboration requires HAP_JOBS=32\n' >&2
    exit 2
}
[[ ! -e "$HAP_REPORT_DIR" ]] || {
    printf 'V5 elaboration evidence directory already exists: %s\n' \
        "$HAP_REPORT_DIR" >&2
    exit 2
}
[[ ! -e "$HAP_BUILD_DIR" ]] || {
    printf 'V5 elaboration build directory already exists: %s\n' \
        "$HAP_BUILD_DIR" >&2
    exit 2
}
mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; elaboration not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi
mkdir "$HAP_REPORT_DIR" "$HAP_BUILD_DIR"

# Freeze every recursive manifest input plus the launcher and Tcl driver.  A
# long Vivado run is rejected if any byte changes before it returns.
declare -A seen=()
inputs=()
collect_manifest() {
    local manifest="$1" raw line path
    [[ -f "$manifest" ]] || {
        printf 'missing V5 manifest: %s\n' "$manifest" >&2
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
            printf 'missing V5 production input: %s\n' "$path" >&2
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

collect_manifest "$MANIFEST"
for path in \
    "$ROOT/vivado/scripts/elaborate_attention_mlp_production_v5.tcl" \
    "$ROOT/vivado/scripts/run_attention_mlp_production_v5_elaboration.sh" \
    "$COHORT16_STATIC_CHECKER"; do
    [[ -f "$path" ]] || {
        printf 'missing V5 elaboration evidence input: %s\n' "$path" >&2
        exit 2
    }
    if [[ -z "${seen[$path]+x}" ]]; then
        seen["$path"]=1
        inputs+=("$path")
    fi
done
printf '%s\n' "${inputs[@]}" | LC_ALL=C sort -u \
    > "$HAP_REPORT_DIR/INPUT_FILES"
xargs -d '\n' sha256sum < "$HAP_REPORT_DIR/INPUT_FILES" \
    > "$HAP_REPORT_DIR/INPUT_SHA256SUMS"
(cd / && sha256sum -c --strict "$HAP_REPORT_DIR/INPUT_SHA256SUMS")

set +e
"$COHORT16_STATIC_CHECKER" \
    > "$HAP_REPORT_DIR/cohort16_production_static_check.txt" 2>&1
static_rc=$?
set -e
if (( static_rc != 0 )) || \
   [[ "$(grep -Fxc 'V5_COHORT16_STATIC_CONTRACT_PASS' \
        "$HAP_REPORT_DIR/cohort16_production_static_check.txt")" -ne 1 ]]; then
    mapfile -d '' early_outputs < <(find "$HAP_REPORT_DIR" -maxdepth 1 \
        -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
    if [[ "${#early_outputs[@]}" -ne 0 ]]; then
        sha256sum -- "${early_outputs[@]}" \
            > "$HAP_REPORT_DIR/OUTPUT_SHA256SUMS"
    fi
    printf 'V5 cohort16 elaboration static gate failed; evidence: %s\n' \
        "$HAP_REPORT_DIR" >&2
    exit 1
fi

cd "$ROOT"
set +e
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/elaborate_attention_mlp_production_v5.tcl \
    -log "$HAP_REPORT_DIR/vivado.log" \
    -journal "$HAP_REPORT_DIR/vivado.jou"
vivado_rc=$?
set -e

set +e
(cd / && sha256sum -c --strict "$HAP_REPORT_DIR/INPUT_SHA256SUMS") \
    > "$HAP_REPORT_DIR/input_sha_postcheck.txt" 2>&1
input_rc=$?
set -e
printf 'vivado_exit_code=%d\ninput_sha_recheck_exit_code=%d\n' \
    "$vivado_rc" "$input_rc" > "$HAP_REPORT_DIR/launcher_status.txt"

archive_outputs() {
    mapfile -d '' outputs < <(find "$HAP_REPORT_DIR" -maxdepth 1 \
        -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
    if [[ "${#outputs[@]}" -ne 0 ]]; then
        sha256sum -- "${outputs[@]}" > "$HAP_REPORT_DIR/OUTPUT_SHA256SUMS"
    fi
}
if (( vivado_rc != 0 || input_rc != 0 )); then
    archive_outputs
    printf 'V5 elaboration failed; evidence retained in %s\n' \
        "$HAP_REPORT_DIR" >&2
    printf '%s\n' "$HAP_REPORT_DIR"
    (( vivado_rc != 0 )) && exit "$vivado_rc"
    exit "$input_rc"
fi

for required in summary.txt cohort16_production_static_check.txt vivado.log \
        vivado.jou launcher_status.txt input_sha_postcheck.txt; do
    [[ -s "$HAP_REPORT_DIR/$required" ]] || {
        archive_outputs
        printf 'missing V5 elaboration output: %s\n' "$required" >&2
        exit 1
    }
done
if grep -Eiq '(^|[^[:alnum:]_])(FAIL|ERROR|FATAL)(:|\[|[[:space:]])' \
        "$HAP_REPORT_DIR/vivado.log" "$HAP_REPORT_DIR/summary.txt"; then
    archive_outputs
    printf 'V5 elaboration rejected FAIL/Error/Fatal marker\n' >&2
    exit 1
fi

for literal in \
    status=V5_PRODUCTION_ELABORATION_PASS \
    jobs=32 \
    production_profile=cohort16 \
    attention_board_module=hap_attention_board_cohort16_core \
    attention_cohort16_board_instances=1 attention_legacy_board_instances=0 \
    attention_cohort16_compute_instances=1 attention_legacy_compute_instances=0 \
    attention_projection16_instances=1 attention_projection8_instances=0 \
    attention_lane_instances=128 attention_dual_accumulator_instances=6 \
    attention_local_accumulator_contexts=12 \
    old_serial_instances=0 v5_serial_instances=1 \
    v5_shared_dual_instances=1 v5_local_branch_instances=2 \
    v4_shared_dual_instances=0 v4_kernel16_instances=0 \
    v5_kernel12_instances=2 history2_repack_instances=2 \
    generic_repack_instances=0 swiglu_frontend_instances=1 \
    swiglu_row_leaf_instances=2 swiglu_unique_hadamard_instances=1 \
    swiglu_fold2_hadamard_instances=0 swiglu_quantizer_instances=4 \
    swiglu_silu_instances=2 attention_col3_array_instances=1 \
    attention_old_array_instances=0 attention_left2_shard_instances=1 \
    attention_center12_shard_instances=1 attention_right2_shard_instances=1 \
    attention_center_subshard_instances=4 attention_leaf_shard_instances=6 \
    compact_input_frontend_instances=1 down_activation_cache_instances=1 \
    gate_accum_instances=2 down_accum_instances=2 \
    down_elastic2_instances=2; do
    [[ "$(grep -Fxc -- "$literal" "$HAP_REPORT_DIR/summary.txt")" -eq 1 ]] || {
        archive_outputs
        printf 'V5 elaboration summary contract missing or duplicated: %s\n' \
            "$literal" >&2
        exit 1
    }
done

archive_outputs
(cd / && sha256sum -c --strict "$HAP_REPORT_DIR/INPUT_SHA256SUMS")
(cd / && sha256sum -c --strict "$HAP_REPORT_DIR/OUTPUT_SHA256SUMS")
cat "$HAP_REPORT_DIR/summary.txt"
printf '%s\n' "$HAP_REPORT_DIR"
