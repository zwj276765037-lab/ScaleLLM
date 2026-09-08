#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
AUDIT_TCL="$ROOT/vivado/scripts/audit_attention_mlp_production_v5_rowlocal_signature_dcp.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_rowlocal_signature_audit.sh"

if [[ $# -ne 1 ]]; then
    printf 'usage: %s V5_POST_OPT_DCP\n' "$0" >&2
    exit 2
fi
export HAP_DCP="$(readlink -f -- "$1")"
for input in "$HAP_DCP" "$AUDIT_TCL" "$LAUNCHER" "$VIVADO"; do
    [[ -s "$input" ]] || {
        printf 'missing row-local signature input: %s\n' "$input" >&2
        exit 2
    }
done
if pgrep -f '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' >/dev/null; then
    printf 'another batch Vivado is active; signature audit not started\n' >&2
    exit 75
fi

audit_code="$(sed -E '/^[[:space:]]*#/d' "$AUDIT_TCL")"
if grep -Eq \
    '(^|[^[:alnum:]_])(synth_design|opt_design|power_opt_design|place_design|phys_opt_design|route_design|link_design|read_checkpoint|launch_runs|open_run|reset_runs|set_property|source|eval|uplevel|write_[[:alnum:]_]+)([^[:alnum:]_]|$)' \
    <<<"$audit_code"; then
    printf 'row-local signature Tcl contains a forbidden command\n' >&2
    exit 2
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
requested="${HAP_SIGNATURE_DIR:-$(dirname "$HAP_DCP")/v5_rowlocal_signature_audit_$STAMP}"
export HAP_SIGNATURE_DIR="$(readlink -m -- "$requested")"
[[ ! -e "$HAP_SIGNATURE_DIR" ]] || {
    printf 'signature output already exists: %s\n' "$HAP_SIGNATURE_DIR" >&2
    exit 2
}
mkdir "$HAP_SIGNATURE_DIR"
export HAP_SIGNATURE_INPUT_SHA="$HAP_SIGNATURE_DIR/INPUT_SHA256SUMS"
export HAP_SIGNATURE_LAUNCHER="$LAUNCHER"
printf '%s\n' "$HAP_DCP" "$AUDIT_TCL" "$LAUNCHER" \
    > "$HAP_SIGNATURE_DIR/INPUT_FILES"
sha256sum -- "$HAP_DCP" "$AUDIT_TCL" "$LAUNCHER" \
    > "$HAP_SIGNATURE_INPUT_SHA"
export HAP_EXPECTED_DCP_SHA256
HAP_EXPECTED_DCP_SHA256="$(sha256sum -- "$HAP_DCP" | awk '{print $1}')"
export HAP_SIGNATURE_INPUT_MANIFEST_SHA256
HAP_SIGNATURE_INPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_SIGNATURE_INPUT_SHA" | awk '{print $1}')"
(cd / && sha256sum -c --strict "$HAP_SIGNATURE_INPUT_SHA") \
    > "$HAP_SIGNATURE_DIR/input_sha_precheck.txt" 2>&1

cd "$ROOT"
set +e
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/audit_attention_mlp_production_v5_rowlocal_signature_dcp.tcl \
    -log "$HAP_SIGNATURE_DIR/vivado.log" \
    -journal "$HAP_SIGNATURE_DIR/vivado.jou"
vivado_rc=$?
set -e

set +e
(cd / && sha256sum -c --strict "$HAP_SIGNATURE_INPUT_SHA") \
    > "$HAP_SIGNATURE_DIR/input_sha_postcheck.txt" 2>&1
sha_rc=$?
actual_manifest_sha="$(sha256sum -- "$HAP_SIGNATURE_INPUT_SHA" 2>/dev/null | awk '{print $1}')"
manifest_rc=$?
set -e
manifest_match=0
if [[ "$manifest_rc" -eq 0 && \
      "$actual_manifest_sha" == "$HAP_SIGNATURE_INPUT_MANIFEST_SHA256" ]]; then
    manifest_match=1
fi
for file in vivado.log vivado.jou; do
    [[ -e "$HAP_SIGNATURE_DIR/$file" ]] || \
        printf 'launcher_note=Vivado did not create %s\n' "$file" \
        > "$HAP_SIGNATURE_DIR/$file"
done

gate_rc=125
if [[ "$vivado_rc" -eq 0 && "$sha_rc" -eq 0 && "$manifest_match" -eq 1 ]]; then
    set +e
    summary="$HAP_SIGNATURE_DIR/signature.txt"
    [[ -s "$summary" && -s "$HAP_SIGNATURE_DIR/utilization_hier_signature.rpt" ]] &&
    grep -Fqx 'status=V5_ROWLOCAL_SIGNATURE_PASS' "$summary" &&
    grep -Fqx "input_dcp_sha256=$HAP_EXPECTED_DCP_SHA256" "$summary" &&
    grep -Fqx 'leaf0_dsp=2' "$summary" &&
    grep -Fqx 'leaf1_dsp=2' "$summary" &&
    grep -Fqx 'leaf0_ramb36=6' "$summary" &&
    grep -Fqx 'leaf1_ramb36=6' "$summary" &&
    grep -Fqx 'central_hadamard_dsp=64' "$summary" &&
    grep -Fqx 'central_quantizers_dsp=4' "$summary" &&
    grep -Fqx 'frontend_dsp=76' "$summary" &&
    grep -Fqx 'leaf0_clb_lut=1886' "$summary" &&
    grep -Fqx 'leaf1_clb_lut=1886' "$summary" &&
    grep -Fqx 'central_hadamard_clb_lut=9019' "$summary" &&
    grep -Fqx 'central_quantizers_clb_lut=22517' "$summary" &&
    grep -Fqx 'frontend_clb_lut=54591' "$summary" &&
    grep -Fqx 'frontend_clb_register=66591' "$summary" &&
    grep -Fqx 'frontend_direct_clb_register=33479' "$summary" &&
    grep -Fqx 'compute_branch0_dsp=1536' "$summary" &&
    grep -Fqx 'compute_branch1_dsp=1536' "$summary" &&
    grep -Fqx 'attention_row_dsp=52' "$summary" &&
    grep -Fqx 'kv_cache_ramb36=88' "$summary" &&
    grep -Fqx 'kv_cache_ramb18=2' "$summary" &&
    grep -Fqx 'selected_set_overlap=0' "$summary" &&
    grep -Fqx 'checkpoint_written=0' "$summary" &&
    grep -Fqx 'implementation_commands_run=0' "$summary" &&
    ! grep -Eiq '(^|[^[:alnum:]_])(FAIL|ERROR|FATAL)(:|\[|[[:space:]])' \
        "$HAP_SIGNATURE_DIR/vivado.log" "$summary"
    gate_rc=$?
    set -e
fi

final_rc=0
status=PASS
if [[ "$vivado_rc" -ne 0 ]]; then final_rc="$vivado_rc"; status=FAIL
elif [[ "$sha_rc" -ne 0 || "$manifest_match" -ne 1 || "$gate_rc" -ne 0 ]]; then
    final_rc=1; status=FAIL
fi
printf '%s\n' "status=$status" "final_exit_code=$final_rc" \
    "vivado_exit_code=$vivado_rc" "input_sha_recheck_exit_code=$sha_rc" \
    "input_manifest_sha_match=$manifest_match" "audit_gate_exit_code=$gate_rc" \
    'checkpoint_written=0' 'implementation_commands_run=0' \
    > "$HAP_SIGNATURE_DIR/launcher_status.txt"
mapfile -d '' outputs < <(find "$HAP_SIGNATURE_DIR" -maxdepth 1 -type f \
    ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
sha256sum -- "${outputs[@]}" > "$HAP_SIGNATURE_DIR/OUTPUT_SHA256SUMS"
(cd / && sha256sum -c --strict "$HAP_SIGNATURE_DIR/OUTPUT_SHA256SUMS")
if [[ "$final_rc" -ne 0 ]]; then
    printf 'row-local signature audit failed; evidence: %s\n' \
        "$HAP_SIGNATURE_DIR" >&2
    exit "$final_rc"
fi
cat "$HAP_SIGNATURE_DIR/signature.txt"
printf '%s\n' "$HAP_SIGNATURE_DIR"
