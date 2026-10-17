#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 0 ]] || { printf 'usage: %s\n' "$0" >&2; exit 2; }
root="$(cd "$(dirname "$0")/../.." && pwd)"
out="${HAP_ELAB_REPORT_DIR:-$root/vivado/reports/m002_elab_$(date -u +%Y%m%dT%H%M%SZ)_$$}"
out="$(readlink -m -- "$out")"
[[ "$out" == "$root/vivado/reports/"* && ! -e "$out" ]] || exit 2
jobs="${HAP_JOBS:-8}"
limit="${HAP_ELAB_TIMEOUT_SECONDS:-600}"
[[ "$jobs" =~ ^[1-8]$ && "$limit" =~ ^[1-9][0-9]*$ ]] || exit 2
if [[ -n "${VIVADO_BIN_DIR:-}" ]]; then
    bin="$VIVADO_BIN_DIR"
elif [[ -n "${XILINX_VIVADO:-}" ]]; then
    bin="$XILINX_VIVADO/bin"
elif command -v vivado >/dev/null 2>&1; then
    bin="$(dirname "$(command -v vivado)")"
else
    bin=/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin
fi
[[ -x "$bin/vivado" ]] || { printf 'Vivado is missing: %s\n' "$bin/vivado" >&2; exit 2; }
bin="$(readlink -f -- "$bin")"
mkdir -p "$out"
started="$(date -u +%FT%TZ)"
phase=prepare
status() {
    local rc="$?"
    trap - EXIT
    printf 'top=hap_attention_mlp_board_core\nmode=rtl_elaboration_only\nexit_code=%s\nphase=%s\nstarted_utc=%s\nended_utc=%s\nreports=%s\ntoolbin=%s\njobs=%s\ntimeout_seconds=%s\n' \
        "$rc" "$phase" "$started" "$(date -u +%FT%TZ)" "$out" "$bin" "$jobs" "$limit" > "$out/launcher_status.txt"
    exit "$rc"
}
trap status EXIT
sha256sum -- "$0" "$root/vivado/scripts/m002_elaborate_verify.tcl" > "$out/launcher_inputs.sha256"
ln -s "$root/data" "$out/data"
ln -s "$root/tb" "$out/tb"
export HAP_ELAB_REPORT_DIR="$out" HAP_JOBS="$jobs" OMP_NUM_THREADS="$jobs"
cd "$out"
phase=version
timeout --kill-after=10s 30 "$bin/vivado" -version > "$out/tool_versions.txt" 2>&1
args=(-mode batch -notrace -nojournal -log "$out/vivado.log" -source "$root/vivado/scripts/m002_elaborate_verify.tcl")
printf '%q ' timeout --kill-after=10s "$limit" "$bin/vivado" "${args[@]}" > "$out/argv.txt"
printf '\n' >> "$out/argv.txt"
phase=rtl_elaboration
timeout --kill-after=10s "$limit" "$bin/vivado" "${args[@]}" > "$out/console.log" 2>&1
phase=log_validation
if grep -Ein '(^|[^[:alnum:]_])(ERROR|FATAL|FAIL)([^[:alnum:]_]|$)|\$error' "$out/vivado.log" > "$out/fault_lines.txt"; then
    printf 'RTL elaboration log contains errors\n' >&2; exit 1
fi
[[ "$(grep -Fxc 'M002_FULL_ELABORATION_PASS' "$out/vivado.log" || true)" -eq 1 ]] || exit 1
sha256sum --status -c "$out/launcher_inputs.sha256"
sha256sum --status -c "$out/elab_inputs.sha256"
phase=complete
printf 'PASS: %s\n' "$out"
