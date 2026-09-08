#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
TCL="$ROOT/vivado/scripts/diagnose_attention_mlp_production_v5_p10_p4_deep_partition.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_p10_p4_deep_partition_diagnosis.sh"
FAILED_DIR="$ROOT/vivado/reports/production_v5_p10_p4_place_20260904_mission0070_physical448_v1"
DCP="$FAILED_DIR/post_place_diagnostic_only.dcp"
FAILED_OUTPUT_SHA="$FAILED_DIR/OUTPUT_SHA256SUMS"
EXPECTED_DCP_SHA=bf42047eb60a55d186d4e2c6b6337fbeb248cce97a659bb3a92b15530ab5715c
EXPECTED_FAILED_OUTPUT_SHA=b3d0f2dc11dc5960d4eefa25c97fcb1f3c8fd4eddba0c026424c800bc971dadc
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_P4_DEEP_DIR="${HAP_P4_DEEP_DIR:-$ROOT/vivado/reports/production_v5_p10_p4_deep_partition_${STAMP}}"
export HAP_P4_DEEP_DCP="$DCP"
export HAP_P4_DEEP_DCP_SHA256="$EXPECTED_DCP_SHA"
export HAP_P4_FAILED_OUTPUT_SHA="$FAILED_OUTPUT_SHA"
export HAP_P4_FAILED_OUTPUT_SHA256="$EXPECTED_FAILED_OUTPUT_SHA"
export HAP_P4_DEEP_LAUNCHER="$LAUNCHER"
export HAP_JOBS="${HAP_JOBS:-32}"

[[ $# -eq 0 ]] || { printf 'usage: %s\n' "$0" >&2; exit 2; }
[[ "$HAP_JOBS" == 32 ]] || {
    printf 'P4 deep diagnosis requires HAP_JOBS=32\n' >&2
    exit 2
}
for path in "$VIVADO" "$TCL" "$LAUNCHER" "$DCP" "$FAILED_OUTPUT_SHA"; do
    [[ -s "$path" ]] || {
        printf 'missing P4 deep diagnosis input: %s\n' "$path" >&2
        exit 2
    }
done
[[ "$(sha256sum "$DCP" | awk '{print $1}')" == "$EXPECTED_DCP_SHA" ]] || {
    printf 'P4 diagnostic DCP SHA mismatch\n' >&2
    exit 2
}
[[ "$(sha256sum "$FAILED_OUTPUT_SHA" | awk '{print $1}')" == \
        "$EXPECTED_FAILED_OUTPUT_SHA" ]] || {
    printf 'P4 failed output manifest SHA mismatch\n' >&2
    exit 2
}
(cd / && sha256sum -c --strict "$FAILED_OUTPUT_SHA")

code="$(sed -E '/^[[:space:]]*#/d' "$TCL")"
if grep -Eq '(^|[^[:alnum:]_])(place_design|route_design|phys_opt_design|write_checkpoint)([^[:alnum:]_]|$)' \
        <<<"$code"; then
    printf 'P4 deep diagnosis contains a forbidden implementation command\n' >&2
    exit 2
fi
mapfile -t active < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; diagnosis not started:\n' >&2
    printf '  %s\n' "${active[@]}" >&2
    exit 75
fi

mkdir -p "$HAP_P4_DEEP_DIR"
inputs=("$DCP" "$FAILED_OUTPUT_SHA" "$TCL" "$LAUNCHER")
printf '%s\n' "${inputs[@]}" > "$HAP_P4_DEEP_DIR/INPUT_FILES"
sha256sum "${inputs[@]}" > "$HAP_P4_DEEP_DIR/INPUT_SHA256SUMS"
export HAP_P4_DEEP_INPUT_SHA="$HAP_P4_DEEP_DIR/INPUT_SHA256SUMS"
export HAP_P4_DEEP_INPUT_MANIFEST_SHA256
HAP_P4_DEEP_INPUT_MANIFEST_SHA256="$(sha256sum \
    "$HAP_P4_DEEP_DIR/INPUT_SHA256SUMS" | awk '{print $1}')"

archive() {
    local incoming="$?" final
    set +e
    final="$incoming"
    sha256sum "${inputs[@]}" > "$HAP_P4_DEEP_DIR/INPUT_SHA256SUMS_POST"
    if cmp -s "$HAP_P4_DEEP_DIR/INPUT_SHA256SUMS" \
            "$HAP_P4_DEEP_DIR/INPUT_SHA256SUMS_POST"; then
        input_stable=1
    else
        input_stable=0
        final=1
    fi
    {
        printf 'status=%s\n' "$([[ "$final" -eq 0 ]] && printf PASS || printf FAIL)"
        printf 'final_exit_code=%s\n' "$final"
        printf 'input_sha_stable=%s\n' "$input_stable"
        printf 'floorplan_mutated=0\n'
        printf 'implementation_commands_run=0\n'
        printf 'checkpoint_written=0\n'
        printf 'route_eligible=0\n'
    } > "$HAP_P4_DEEP_DIR/launcher_status.txt"
    find "$HAP_P4_DEEP_DIR" -maxdepth 1 -type f \
        ! -name OUTPUT_SHA256SUMS -print0 | sort -z | xargs -0 sha256sum \
        > "$HAP_P4_DEEP_DIR/OUTPUT_SHA256SUMS"
    trap - EXIT
    exit "$final"
}
trap archive EXIT

cd "$ROOT"
"$VIVADO" -mode batch -notrace -source "$TCL" \
    -log "$HAP_P4_DEEP_DIR/vivado.log" \
    -journal "$HAP_P4_DEEP_DIR/vivado.jou"

for output in summary.txt hierarchy_resources.tsv hierarchy_boundaries.tsv \
        pblock_intersections.tsv custom_resources.tsv custom_boundaries.tsv \
        custom_pblock_intersections.tsv discovered_storage_names.txt \
        vivado.log vivado.jou; do
    [[ -s "$HAP_P4_DEEP_DIR/$output" ]] || {
        printf 'missing P4 deep diagnosis output: %s\n' "$output" >&2
        exit 1
    }
done
grep -Fqx 'status=V5_P10_P4_DEEP_PARTITION_DIAGNOSIS_PASS' \
    "$HAP_P4_DEEP_DIR/summary.txt"
grep -Fqx 'hierarchy_root_count=16' "$HAP_P4_DEEP_DIR/summary.txt"
grep -Fqx 'input_row_group_count=16' "$HAP_P4_DEEP_DIR/summary.txt"
grep -Fqx 'swiglu_ring_group_count=32' "$HAP_P4_DEEP_DIR/summary.txt"
grep -Fqx 'dsp48e2=5453' "$HAP_P4_DEEP_DIR/summary.txt"
grep -Fqx 'uram288=752' "$HAP_P4_DEEP_DIR/summary.txt"
grep -Fqx 'implementation_commands_run=0' "$HAP_P4_DEEP_DIR/summary.txt"
grep -Fqx 'checkpoint_written=0' "$HAP_P4_DEEP_DIR/summary.txt"
grep -Fqx 'route_eligible=0' "$HAP_P4_DEEP_DIR/summary.txt"
if grep -Eq '^(ERROR|FATAL):' "$HAP_P4_DEEP_DIR/vivado.log"; then
    printf 'P4 deep diagnosis log contains ERROR/FATAL\n' >&2
    exit 1
fi
(cd / && sha256sum -c --strict "$HAP_P4_DEEP_DIR/INPUT_SHA256SUMS")
printf '%s\n' "$HAP_P4_DEEP_DIR"
