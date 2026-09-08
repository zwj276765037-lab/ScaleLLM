#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
AUDIT="$ROOT/vivado/scripts/audit_mlp_p8_parent_ingress_replica_aware_dcp.tcl"
BOUNDARY_LIB="$ROOT/vivado/scripts/audit_mlp_p8_parent_ingress_boundary_replica_aware.tcl"
P10_PROC_LIB="$ROOT/vivado/scripts/place_attention_mlp_production_v5_p10_p2.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_mlp_p8_parent_ingress_replica_aware_dcp_audit.sh"
STAMP="$(date +%Y%m%d_%H%M%S)"

[[ $# -eq 1 ]] || { printf 'usage: %s DCP\n' "$0" >&2; exit 2; }
[[ -x "$VIVADO" ]] || { printf 'missing Vivado: %s\n' "$VIVADO" >&2; exit 2; }
export HAP_DCP="$(readlink -e -- "$1")"
requested="${HAP_AUDIT_DIR:-$ROOT/vivado/reports/mlp_p8_parent_ingress_replica_aware_dcp_audit_$STAMP}"
export HAP_AUDIT_DIR="$(readlink -m -- "$requested")"
[[ ! -e "$HAP_AUDIT_DIR" ]] || {
    printf 'P8 replica-aware audit directory exists: %s\n' \
        "$HAP_AUDIT_DIR" >&2
    exit 2
}
mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; P8 audit not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi
mkdir "$HAP_AUDIT_DIR"
export HAP_P8_BOUNDARY_LIB="$BOUNDARY_LIB"
export HAP_P8_P10_PROC_LIB="$P10_PROC_LIB"
export HAP_AUDIT_LAUNCHER="$LAUNCHER"
inputs=("$HAP_DCP" "$BOUNDARY_LIB" "$P10_PROC_LIB" "$AUDIT" "$LAUNCHER")
printf '%s\n' "${inputs[@]}" > "$HAP_AUDIT_DIR/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$HAP_AUDIT_DIR/INPUT_SHA256SUMS"
export HAP_AUDIT_INPUT_SHA="$HAP_AUDIT_DIR/INPUT_SHA256SUMS"
export HAP_EXPECTED_DCP_SHA256
HAP_EXPECTED_DCP_SHA256="$(sha256sum -- "$HAP_DCP" | awk '{print $1}')"
export HAP_AUDIT_INPUT_MANIFEST_SHA256
HAP_AUDIT_INPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_AUDIT_INPUT_SHA" | awk '{print $1}')"
(cd / && sha256sum -c --strict "$HAP_AUDIT_INPUT_SHA") \
    > "$HAP_AUDIT_DIR/input_sha_precheck.txt" 2>&1

set +e
"$VIVADO" -mode batch -notrace -source "$AUDIT" \
    -log "$HAP_AUDIT_DIR/vivado.log" \
    -journal "$HAP_AUDIT_DIR/vivado.jou"
vivado_rc=$?
(cd / && sha256sum -c --strict "$HAP_AUDIT_INPUT_SHA") \
    > "$HAP_AUDIT_DIR/input_sha_postcheck.txt" 2>&1
input_rc=$?
set -e

status=FAIL
if (( vivado_rc == 0 && input_rc == 0 )) && \
   [[ -s "$HAP_AUDIT_DIR/summary.txt" ]] && \
   grep -Fqx 'status=V5_P8_PARENT_INGRESS_REPLICA_AWARE_DCP_AUDIT_PASS' \
        "$HAP_AUDIT_DIR/summary.txt"; then
    status=PASS
fi
printf 'status=%s\nvivado_exit_code=%d\ninput_sha_recheck_exit_code=%d\n' \
    "$status" "$vivado_rc" "$input_rc" \
    > "$HAP_AUDIT_DIR/launcher_status.txt"
mapfile -d '' outputs < <(find "$HAP_AUDIT_DIR" -maxdepth 1 -type f \
    -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
sha256sum -- "${outputs[@]}" > "$HAP_AUDIT_DIR/OUTPUT_SHA256SUMS"
if [[ "$status" != PASS ]]; then
    printf 'P8 replica-aware DCP audit failed; evidence: %s\n' \
        "$HAP_AUDIT_DIR" >&2
    (( vivado_rc != 0 )) && exit "$vivado_rc"
    exit 1
fi

for literal in parent_head_ff=6560 parent_tail_ff=6560 parent_count_ff=2 \
        parent_count_replica_equivalence_ok=1 parent_pointer_ff=0 \
        local_clear_ff=2 branch_ingress_count_ff=4 \
        local_clear_shared_upstream_ready_paths=0 \
        branch_credit_shared_upstream_ready_paths=0 \
        local_clear_gate_compute_ready_paths=0 \
        branch_credit_gate_compute_ready_paths=0 \
        local_clear_down_compute_ready_paths=0 \
        branch_credit_down_compute_ready_paths=0 \
        local_clear_input_cache_ready_paths=0 \
        branch_credit_input_cache_ready_paths=0 implementation_commands_run=0 \
        checkpoint_written=0 route_eligible=0; do
    grep -Fqx -- "$literal" "$HAP_AUDIT_DIR/summary.txt"
done
physical="$(awk -F= '$1 == "parent_count_physical_ff" {print $2}' \
    "$HAP_AUDIT_DIR/summary.txt")"
replicas="$(awk -F= '$1 == "parent_count_replica_ff" {print $2}' \
    "$HAP_AUDIT_DIR/summary.txt")"
bit0="$(awk -F= '$1 == "parent_count_bit0_physical_ff" {print $2}' \
    "$HAP_AUDIT_DIR/summary.txt")"
bit1="$(awk -F= '$1 == "parent_count_bit1_physical_ff" {print $2}' \
    "$HAP_AUDIT_DIR/summary.txt")"
[[ "$physical" =~ ^[0-9]+$ && "$replicas" =~ ^[0-9]+$ && \
   "$bit0" =~ ^[0-9]+$ && "$bit1" =~ ^[0-9]+$ ]]
(( physical == replicas + 2 && physical == bit0 + bit1 && \
   bit0 >= 1 && bit1 >= 1 ))
(cd / && sha256sum -c --strict "$HAP_AUDIT_DIR/INPUT_SHA256SUMS")
(cd / && sha256sum -c --strict "$HAP_AUDIT_DIR/OUTPUT_SHA256SUMS")
printf '%s\n' "$HAP_AUDIT_DIR"
