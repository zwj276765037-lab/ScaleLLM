#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
TCL="$ROOT/vivado/scripts/program_attention_mlp_vcu118_v5_bitstream.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_program_attention_mlp_vcu118_v5_bitstream.sh"
REQUIRED_CONFIRM=PROGRAM_AUDITED_SCALELLM_V5_VCU118

[[ $# -eq 2 ]] || {
    printf 'usage: %s BOARD_REPORT_DIR BOARD_AUDIT_DIR\n' "$0" >&2
    exit 2
}
[[ "${HAP_PROGRAM_CONFIRM:-}" == "$REQUIRED_CONFIRM" ]] || {
    printf 'refusing hardware access; set HAP_PROGRAM_CONFIRM=%s only when VCU118 JTAG and PCIe power state are ready\n' \
        "$REQUIRED_CONFIRM" >&2
    exit 2
}
[[ -x "$VIVADO" && -s "$TCL" ]] || {
    printf 'missing V5 programming tool or Tcl\n' >&2
    exit 2
}

BOARD_DIR="$(readlink -e -- "$1")"
AUDIT_DIR="$(readlink -e -- "$2")"
mapfile -t evidence < <(PYTHONPATH="$ROOT" python3 - \
        "$BOARD_DIR" "$AUDIT_DIR" <<'PY'
import sys
from host.scalellm_board import BoardAuditEvidence, BoardBuildEvidence

board = BoardBuildEvidence.load(sys.argv[1])
audit = BoardAuditEvidence.load(sys.argv[2], board)
if audit.bitstream_sha256 != board.bitstream_sha256:
    raise SystemExit("independent audit bitstream SHA256 mismatch")
print(board.bitstream)
print(board.bitstream_sha256)
PY
)
[[ "${#evidence[@]}" -eq 2 ]] || {
    printf 'V5 board/audit preflight did not return exact bitstream identity\n' >&2
    exit 2
}
export HAP_BITSTREAM="$(readlink -e -- "${evidence[0]}")"
export HAP_EXPECTED_BITSTREAM_SHA256="${evidence[1]}"
[[ "$(sha256sum -- "$HAP_BITSTREAM" | awk '{print $1}')" == \
    "$HAP_EXPECTED_BITSTREAM_SHA256" ]] || {
    printf 'V5 bitstream SHA256 changed after evidence preflight\n' >&2
    exit 2
}

mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; VCU118 programming not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_PROGRAM_DIR="$(readlink -m -- \
    "${HAP_PROGRAM_DIR:-$ROOT/vivado/reports/attention_mlp_vcu118_v5_program_$STAMP}")"
[[ ! -e "$HAP_PROGRAM_DIR" ]] || {
    printf 'V5 programming evidence directory exists: %s\n' \
        "$HAP_PROGRAM_DIR" >&2
    exit 2
}
mkdir "$HAP_PROGRAM_DIR"
export HAP_PROGRAM_REPORT="$HAP_PROGRAM_DIR/summary.txt"
export HAP_HW_SERVER_URL="${HAP_HW_SERVER_URL:-localhost:3121}"
export HAP_HW_TARGET_INDEX="${HAP_HW_TARGET_INDEX:-0}"
export HAP_HW_DEVICE_FILTER="${HAP_HW_DEVICE_FILTER:-xcvu9p}"

inputs=(
    "$HAP_BITSTREAM" "$BOARD_DIR/OUTPUT_SHA256SUMS"
    "$AUDIT_DIR/OUTPUT_SHA256SUMS" "$TCL" "$LAUNCHER"
)
printf '%s\n' "${inputs[@]}" > "$HAP_PROGRAM_DIR/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$HAP_PROGRAM_DIR/INPUT_SHA256SUMS"
input_manifest_sha="$(sha256sum -- \
    "$HAP_PROGRAM_DIR/INPUT_SHA256SUMS" | awk '{print $1}')"
(cd / && sha256sum -c --strict \
    "$HAP_PROGRAM_DIR/INPUT_SHA256SUMS") >/dev/null

vivado_rc=255
input_postcheck=0
manifest_match=0
board_output_postcheck=0
audit_output_postcheck=0
write_status() {
    local status=FAIL
    [[ "$vivado_rc" -eq 0 && "$input_postcheck" -eq 1 && \
       "$manifest_match" -eq 1 && "$board_output_postcheck" -eq 1 && \
       "$audit_output_postcheck" -eq 1 ]] && status=PASS
    printf '%s\n' "status=$status" "vivado_exit_code=$vivado_rc" \
        "input_sha_postcheck=$input_postcheck" \
        "input_manifest_sha_match=$manifest_match" \
        "board_output_sha_postcheck=$board_output_postcheck" \
        "audit_output_sha_postcheck=$audit_output_postcheck" \
        "input_manifest_sha256=$input_manifest_sha" \
        > "$HAP_PROGRAM_DIR/launcher_status.txt"
}
archive_outputs() {
    mapfile -d '' outputs < <(find "$HAP_PROGRAM_DIR" -maxdepth 1 \
        -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
    [[ "${#outputs[@]}" -gt 0 ]] || return 1
    sha256sum -- "${outputs[@]}" > "$HAP_PROGRAM_DIR/OUTPUT_SHA256SUMS"
    (cd / && sha256sum -c --strict \
        "$HAP_PROGRAM_DIR/OUTPUT_SHA256SUMS") >/dev/null
}
finish() {
    local rc="$?"
    trap - EXIT
    write_status || rc=96
    archive_outputs || rc=97
    exit "$rc"
}
trap finish EXIT

set +e
"$VIVADO" -mode batch -notrace -source "$TCL" \
    -log "$HAP_PROGRAM_DIR/vivado.log" \
    -journal "$HAP_PROGRAM_DIR/vivado.jou"
vivado_rc=$?
set -e
(cd / && sha256sum -c --strict \
    "$HAP_PROGRAM_DIR/INPUT_SHA256SUMS") >/dev/null && input_postcheck=1
[[ "$(sha256sum -- "$HAP_PROGRAM_DIR/INPUT_SHA256SUMS" | awk '{print $1}')" \
    == "$input_manifest_sha" ]] && manifest_match=1
(cd / && sha256sum -c --strict \
    "$BOARD_DIR/OUTPUT_SHA256SUMS") >/dev/null && board_output_postcheck=1
(cd / && sha256sum -c --strict \
    "$AUDIT_DIR/OUTPUT_SHA256SUMS") >/dev/null && audit_output_postcheck=1
write_status
[[ "$vivado_rc" -eq 0 && "$input_postcheck" -eq 1 && \
   "$manifest_match" -eq 1 && "$board_output_postcheck" -eq 1 && \
   "$audit_output_postcheck" -eq 1 ]] || exit 1
for literal in status=V5_VCU118_PROGRAM_PASS part=xcvu9p \
        "program_file=$HAP_BITSTREAM" \
        "bitstream_sha256=$HAP_EXPECTED_BITSTREAM_SHA256" program_done=1; do
    if [[ "$literal" == part=xcvu9p ]]; then
        grep -Eiq '^part=.*xcvu9p' "$HAP_PROGRAM_REPORT"
    else
        grep -Fqx -- "$literal" "$HAP_PROGRAM_REPORT"
    fi
done
archive_outputs
printf 'V5_VCU118_PROGRAM_PASS\n%s\n' "$HAP_PROGRAM_DIR"
