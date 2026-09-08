#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
export HAP_JOBS="${HAP_JOBS:-32}"
[[ "$HAP_JOBS" == 32 ]] || {
    printf 'V5 board project creation requires HAP_JOBS=32\n' >&2
    exit 2
}
PROJECT_DIR="${HAP_PROJECT_DIR:-$ROOT/vivado/project/attention_mlp_vcu118_v5_dual_ddr}"
V4_PROJECT_DIR="$ROOT/vivado/project/attention_mlp_vcu118_dual_ddr"
"$ROOT/vivado/scripts/check_attention_mlp_vcu118_v5_board_contract.sh"
[[ -x "$VIVADO" ]] || {
    printf 'Vivado 2025.2 executable is missing: %s\n' "$VIVADO" >&2
    exit 2
}
[[ "$(readlink -m "$PROJECT_DIR")" != "$(readlink -m "$V4_PROJECT_DIR")" ]] || {
    printf 'V5 launcher refuses the preserved V4 project directory: %s\n' \
        "$PROJECT_DIR" >&2
    exit 2
}
mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; V5 board project not created:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi
[[ ! -e "$PROJECT_DIR" ]] || {
    printf 'V5 board project directory already exists: %s\n' \
        "$PROJECT_DIR" >&2
    exit 2
}
mkdir "$PROJECT_DIR"
cd "$ROOT"
HAP_PROJECT_DIR="$PROJECT_DIR" "$VIVADO" -mode batch -notrace \
    -source vivado/scripts/create_attention_mlp_vcu118_dual_ddr_v5_bd.tcl \
    -log "$PROJECT_DIR/create.log" -journal "$PROJECT_DIR/create.jou"

XPR="$PROJECT_DIR/attention_mlp_vcu118_v5_dual_ddr.xpr"
[[ -s "$XPR" ]] || {
    printf 'missing V5 board project: %s\n' "$XPR" >&2
    exit 1
}
printf '%s\n' "$XPR"
