#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
DIAG_TCL="$ROOT/vivado/scripts/diagnose_attention_mlp_production_v5_composite21_partition.tcl"
SELECTOR_LIB="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
FINE_LIB="$ROOT/vivado/scripts/v5_production_fine19_floorplan.tcl"
COMPOSITE_LIB="$ROOT/vivado/scripts/v5_production_composite21_floorplan.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_composite21_partition_diagnosis.sh"

[[ $# -eq 2 ]] || {
    printf 'usage: %s V5_POST_OPT_DCP FAILED_P4_PLACE_OUTPUT_SHA256SUMS\n' "$0" >&2
    exit 2
}
[[ -x "$VIVADO" ]] || { printf 'missing Vivado: %s\n' "$VIVADO" >&2; exit 2; }
export HAP_DCP="$(readlink -f -- "$1")"
export HAP_COMPOSITE21_FAILED_PLACE_SHA="$(readlink -f -- "$2")"
export HAP_JOBS="${HAP_JOBS:-32}"
[[ "$HAP_JOBS" == 32 ]] || {
    printf 'Composite21 partition diagnosis requires HAP_JOBS=32: %q\n' \
        "$HAP_JOBS" >&2
    exit 2
}
inputs=("$HAP_DCP" "$SELECTOR_LIB" "$FINE_LIB" "$COMPOSITE_LIB" \
    "$DIAG_TCL" "$LAUNCHER" "$HAP_COMPOSITE21_FAILED_PLACE_SHA")
for input in "${inputs[@]}"; do
    [[ -s "$input" ]] || {
        printf 'missing Composite21 partition input: %s\n' "$input" >&2
        exit 2
    }
    [[ "$input" != *$'\n'* && "$input" != *$'\r'* ]] || {
        printf 'newline is forbidden in partition input path: %q\n' "$input" >&2
        exit 2
    }
done
mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; partition diagnosis not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi

readonly_code="$(sed -E '/^[[:space:]]*#/d' "$DIAG_TCL")"
if grep -Eq \
    '(^|[^[:alnum:]_])(synth_design|opt_design|power_opt_design|place_design|phys_opt_design|route_design|link_design|read_xdc|create_pblock|resize_pblock|delete_pblock|add_cells_to_pblock|remove_cells_from_pblock|set_property|reset_property|write_checkpoint|write_bitstream|write_cfgmem|launch_runs|wait_on_run)([^[:alnum:]_]|$)' \
    <<<"$readonly_code"; then
    printf 'Composite21 partition diagnosis contains a forbidden command\n' >&2
    exit 2
fi
for forbidden in hap_v5_fine19::apply hap_v5_composite21::apply; do
    if grep -Fq "$forbidden" <<<"$readonly_code"; then
        printf 'Composite21 partition diagnosis calls forbidden apply proc: %s\n' \
            "$forbidden" >&2
        exit 2
    fi
done

failed_dir="$(dirname "$HAP_COMPOSITE21_FAILED_PLACE_SHA")"
failed_status="$failed_dir/launcher_status.txt"
failed_log="$failed_dir/vivado.log"
for evidence in "$failed_status" "$failed_log"; do
    [[ -s "$evidence" ]] || {
        printf 'missing failed P4 placement evidence: %s\n' "$evidence" >&2
        exit 2
    }
done
(cd / && sha256sum -c --strict "$HAP_COMPOSITE21_FAILED_PLACE_SHA") >/dev/null
for literal in status=FAIL acceptance_evidence=0 route_eligible=0 \
        final_exit_code=1 vivado_exit_code=1 checkpoint_written=0 \
        bitstream_generated=0; do
    [[ "$(grep -Fxc -- "$literal" "$failed_status" || true)" -eq 1 ]] || {
        printf 'failed P4 placement status gate failed: %s\n' "$literal" >&2
        exit 2
    }
done
grep -Fq '107.2% LUT utilization in SLR2' "$failed_log" || {
    printf 'failed P4 placement LUT signature is missing\n' >&2
    exit 2
}
grep -Fq '27211 SLLs required between SLR1 and SLR2 of 17280 SLLs available' \
    "$failed_log" || {
    printf 'failed P4 placement SLL signature is missing\n' >&2
    exit 2
}

STAMP="$(date +%Y%m%d_%H%M%S)"
requested="${HAP_COMPOSITE21_DIAG_DIR:-$ROOT/vivado/reports/production_v5_composite21_partition_diagnosis_$STAMP}"
export HAP_COMPOSITE21_DIAG_DIR="$(readlink -m -- "$requested")"
[[ ! -e "$HAP_COMPOSITE21_DIAG_DIR" ]] || {
    printf 'partition diagnosis evidence directory exists: %s\n' \
        "$HAP_COMPOSITE21_DIAG_DIR" >&2
    exit 2
}
mkdir "$HAP_COMPOSITE21_DIAG_DIR"
export HAP_COMPOSITE21_DIAG_INPUT_SHA="$HAP_COMPOSITE21_DIAG_DIR/INPUT_SHA256SUMS"
export HAP_COMPOSITE21_DIAG_SELECTOR_LIB="$SELECTOR_LIB"
export HAP_COMPOSITE21_DIAG_FINE_LIB="$FINE_LIB"
export HAP_COMPOSITE21_DIAG_COMPOSITE_LIB="$COMPOSITE_LIB"
export HAP_COMPOSITE21_DIAG_LAUNCHER="$LAUNCHER"
printf '%s\n' "${inputs[@]}" > "$HAP_COMPOSITE21_DIAG_DIR/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$HAP_COMPOSITE21_DIAG_INPUT_SHA"
export HAP_EXPECTED_DCP_SHA256
HAP_EXPECTED_DCP_SHA256="$(sha256sum -- "$HAP_DCP" | awk '{print $1}')"
export HAP_COMPOSITE21_FAILED_PLACE_SHA256
HAP_COMPOSITE21_FAILED_PLACE_SHA256="$(sha256sum -- \
    "$HAP_COMPOSITE21_FAILED_PLACE_SHA" | awk '{print $1}')"
export HAP_COMPOSITE21_DIAG_INPUT_MANIFEST_SHA256
HAP_COMPOSITE21_DIAG_INPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_COMPOSITE21_DIAG_INPUT_SHA" | awk '{print $1}')"
(cd / && sha256sum -c --strict "$HAP_COMPOSITE21_DIAG_INPUT_SHA") \
    > "$HAP_COMPOSITE21_DIAG_DIR/input_sha_precheck.txt" 2>&1

cd "$ROOT"
set +e
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/diagnose_attention_mlp_production_v5_composite21_partition.tcl \
    -log "$HAP_COMPOSITE21_DIAG_DIR/vivado.log" \
    -journal "$HAP_COMPOSITE21_DIAG_DIR/vivado.jou"
vivado_rc=$?
(cd / && sha256sum -c --strict "$HAP_COMPOSITE21_DIAG_INPUT_SHA") \
    > "$HAP_COMPOSITE21_DIAG_DIR/input_sha_postcheck.txt" 2>&1
sha_rc=$?
(cd / && sha256sum -c --strict "$HAP_COMPOSITE21_FAILED_PLACE_SHA") \
    > "$HAP_COMPOSITE21_DIAG_DIR/failed_place_postcheck.txt" 2>&1
failed_rc=$?
actual_manifest_sha="$(sha256sum -- "$HAP_COMPOSITE21_DIAG_INPUT_SHA" \
    2>/dev/null | awk '{print $1}')"
manifest_rc=$?
set -e
manifest_match=0
if [[ "$manifest_rc" -eq 0 && \
      "$actual_manifest_sha" == "$HAP_COMPOSITE21_DIAG_INPUT_MANIFEST_SHA256" ]]; then
    manifest_match=1
fi
for file in vivado.log vivado.jou; do
    [[ -e "$HAP_COMPOSITE21_DIAG_DIR/$file" ]] ||
        printf 'launcher_note=Vivado did not create %s\n' "$file" \
            > "$HAP_COMPOSITE21_DIAG_DIR/$file"
done

summary="$HAP_COMPOSITE21_DIAG_DIR/summary.txt"
top_groups="$HAP_COMPOSITE21_DIAG_DIR/attention_direct_top_groups.txt"
level2_groups="$HAP_COMPOSITE21_DIAG_DIR/attention_direct_level2_groups.txt"
gate_rc=125
if [[ "$vivado_rc" -eq 0 && "$sha_rc" -eq 0 && "$failed_rc" -eq 0 && \
      "$manifest_match" -eq 1 && -s "$summary" && -s "$top_groups" && \
      -s "$level2_groups" ]]; then
    set +e
    gate_rc=0
    awk -F= 'NF < 2 || seen[$1]++ {exit 1} END {exit 0}' "$summary" || gate_rc=1
    for literal in status=PASS stage=V5_COMPOSITE21_PARTITION_DIAGNOSIS \
        evidence_class=READ_ONLY_POST_OPT_HIERARCHY_CONNECTIVITY jobs=32 \
        "input_dcp=$HAP_DCP" "input_dcp_sha256=$HAP_EXPECTED_DCP_SHA256" \
        "input_manifest_sha256=$HAP_COMPOSITE21_DIAG_INPUT_MANIFEST_SHA256" \
        input_manifest_entries=7 \
        "failed_place_manifest=$HAP_COMPOSITE21_FAILED_PLACE_SHA" \
        "failed_place_manifest_sha256=$HAP_COMPOSITE21_FAILED_PLACE_SHA256" \
        failed_place_verified=1 contract_variant=P4_COHORT16_COMPOSITE21 \
        attention_direct_members=134527 attention_direct_lut=87667 \
        fixed_slr0_lut=273235 fixed_slr1_lut=312344 fixed_slr2_lut=263388 \
        physical_slr_lut_capacity=394080 failed_slr2_lut_percent=107.2 \
        failed_slr12_sll_required=27211 failed_slr12_sll_available=17280 \
        canonical_pblock_count_after=0 floorplan_mutated=0 \
        implementation_commands_run=0 checkpoint_written=0; do
        [[ "$(grep -Fxc -- "$literal" "$summary" 2>/dev/null || true)" -eq 1 ]] || {
            printf 'partition diagnosis summary gate failed: %s\n' "$literal" >&2
            gate_rc=1
        }
    done
    top_count="$(awk -F= '$1=="top_group_count" {print $2}' "$summary")"
    level2_count="$(awk -F= '$1=="level2_group_count" {print $2}' "$summary")"
    [[ "$top_count" =~ ^[1-9][0-9]*$ && "$level2_count" =~ ^[1-9][0-9]*$ ]] ||
        gate_rc=1
    [[ "$(grep -c '^group=' "$top_groups" || true)" -eq "$top_count" ]] || gate_rc=1
    [[ "$(grep -c '^group=' "$level2_groups" || true)" -eq "$level2_count" ]] || gate_rc=1
    set -e
fi

final_rc=0
if [[ "$vivado_rc" -ne 0 ]]; then
    final_rc="$vivado_rc"
elif [[ "$sha_rc" -ne 0 || "$failed_rc" -ne 0 || "$manifest_match" -ne 1 || \
        "$gate_rc" -ne 0 ]]; then
    final_rc=1
fi
printf '%s\n' \
    "status=$([[ "$final_rc" -eq 0 ]] && printf PASS || printf FAIL)" \
    "final_exit_code=$final_rc" "vivado_exit_code=$vivado_rc" \
    "input_sha_recheck_exit_code=$sha_rc" \
    "failed_place_recheck_exit_code=$failed_rc" \
    "input_manifest_sha_match=$manifest_match" "diagnosis_gate_exit_code=$gate_rc" \
    'floorplan_mutated=0' 'implementation_commands_run=0' \
    'checkpoint_written=0' > "$HAP_COMPOSITE21_DIAG_DIR/launcher_status.txt"
mapfile -d '' outputs < <(find "$HAP_COMPOSITE21_DIAG_DIR" -maxdepth 1 \
    -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
sha256sum -- "${outputs[@]}" > "$HAP_COMPOSITE21_DIAG_DIR/OUTPUT_SHA256SUMS"
(cd / && sha256sum -c --strict "$HAP_COMPOSITE21_DIAG_DIR/OUTPUT_SHA256SUMS")
if [[ "$final_rc" -ne 0 ]]; then
    printf 'Composite21 partition diagnosis failed; evidence: %s\n' \
        "$HAP_COMPOSITE21_DIAG_DIR" >&2
    printf '%s\n' "$HAP_COMPOSITE21_DIAG_DIR"
    exit "$final_rc"
fi
cat "$summary"
printf '%s\n' "$HAP_COMPOSITE21_DIAG_DIR"
