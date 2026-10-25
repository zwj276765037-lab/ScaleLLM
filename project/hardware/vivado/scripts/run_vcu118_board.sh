#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 1 && ( "$1" == create || "$1" == synth || "$1" == place || "$1" == route ||
    "$1" == audit ) ]] || {
    printf 'usage: %s create|synth|place|route|audit\n' "$0" >&2
    exit 2
}
stage="$1"
root="$(cd "$(dirname "$0")/../.." && pwd)"
project_base="$root/vivado/project"
report_base="$root/vivado/reports"
export HAP_PROJECT_DIR="${HAP_PROJECT_DIR:-$project_base/scalellm_vcu118_f05}"
export HAP_BOARD_CORE_CLK_MHZ="${HAP_BOARD_CORE_CLK_MHZ:-100.0}"
export HAP_BOARD_DDR_UI_CLK_HZ="${HAP_BOARD_DDR_UI_CLK_HZ:-200000000}"
export HAP_JOBS="${HAP_JOBS:-32}"
export HAP_STAGE="$stage"

[[ "$HAP_JOBS" =~ ^[0-9]+$ ]] && (( HAP_JOBS >= 1 && HAP_JOBS <= 32 )) || {
    printf 'HAP_JOBS must be in 1..32\n' >&2
    exit 2
}
[[ "$HAP_BOARD_CORE_CLK_MHZ" == 100.0 &&
   "$HAP_BOARD_DDR_UI_CLK_HZ" == 200000000 ]] || {
    printf 'Required clocks are core100 and dual DDR UI200\n' >&2
    exit 2
}
HAP_PROJECT_DIR="$(readlink -m -- "$HAP_PROJECT_DIR")"
export HAP_PROJECT_DIR
[[ "$HAP_PROJECT_DIR" == "$project_base/"* ]] || {
    printf 'Project must be under %s\n' "$project_base" >&2
    exit 2
}
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:-$report_base/${stage}_$stamp}"
HAP_REPORT_DIR="$(readlink -m -- "$HAP_REPORT_DIR")"
export HAP_REPORT_DIR
[[ "$HAP_REPORT_DIR" == "$report_base/"* && ! -e "$HAP_REPORT_DIR" ]] || {
    printf 'Report directory is outside new root or already exists: %s\n' \
        "$HAP_REPORT_DIR" >&2
    exit 2
}
if [[ -n "${VIVADO_BIN:-}" ]]; then
    vivado="$VIVADO_BIN"
elif [[ -n "${XILINX_VIVADO:-}" ]]; then
    vivado="$XILINX_VIVADO/bin/vivado"
elif command -v vivado >/dev/null 2>&1; then
    vivado="$(command -v vivado)"
else
    vivado=/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado
fi
[[ -x "$vivado" ]] || {
    printf 'Vivado executable is missing: %s\n' "$vivado" >&2
    exit 2
}
if [[ "$stage" == create ]]; then
    [[ ! -e "$HAP_PROJECT_DIR" ]] || {
        printf 'Board project already exists: %s\n' "$HAP_PROJECT_DIR" >&2
        exit 2
    }
    source_tcl="$root/vivado/scripts/create_vcu118_board.tcl"
elif [[ "$stage" == audit ]]; then
    [[ -s "$HAP_PROJECT_DIR/scalellm_vcu118_f05.xpr" ]] || {
        printf 'Board project is missing: %s\n' "$HAP_PROJECT_DIR" >&2
        exit 2
    }
    [[ -n "${HAP_ROUTE_REPORT_DIR:-}" ]] || {
        printf 'HAP_ROUTE_REPORT_DIR is required for audit\n' >&2
        exit 2
    }
    HAP_ROUTE_REPORT_DIR="$(readlink -m -- "$HAP_ROUTE_REPORT_DIR")"
    export HAP_ROUTE_REPORT_DIR
    [[ "$HAP_ROUTE_REPORT_DIR" == "$report_base/"* &&
       -s "$HAP_ROUTE_REPORT_DIR/routed.dcp" &&
       -s "$HAP_ROUTE_REPORT_DIR/routed_checkpoint.sha256" &&
       -s "$HAP_ROUTE_REPORT_DIR/launcher_status.txt" &&
       "$HAP_ROUTE_REPORT_DIR" != "$HAP_REPORT_DIR" ]] || {
        printf 'No completed same-root routed checkpoint: %s\n' \
            "$HAP_ROUTE_REPORT_DIR" >&2
        exit 2
    }
    source_tcl="$root/vivado/scripts/audit_attention_mlp_vcu118_v5_post_route.tcl"
else
    [[ -s "$HAP_PROJECT_DIR/scalellm_vcu118_f05.xpr" ]] || {
        printf 'Board project is missing: %s\n' "$HAP_PROJECT_DIR" >&2
        exit 2
    }
    source_tcl="$root/vivado/scripts/build_vcu118_board.tcl"
fi
if [[ "$stage" == place || "$stage" == route ]]; then
    [[ -n "${HAP_SYNTH_REPORT_DIR:-}" ]] || {
        printf 'HAP_SYNTH_REPORT_DIR is required for route\n' >&2
        exit 2
    }
    HAP_SYNTH_REPORT_DIR="$(readlink -m -- "$HAP_SYNTH_REPORT_DIR")"
    export HAP_SYNTH_REPORT_DIR
    [[ "$HAP_SYNTH_REPORT_DIR" == "$report_base/"* &&
       -s "$HAP_SYNTH_REPORT_DIR/fresh_synth_complete.txt" ]] || {
        printf 'No current fresh synthesis report: %s\n' "$HAP_SYNTH_REPORT_DIR" >&2
        exit 2
    }
fi
if [[ "$stage" == route ]]; then
    [[ -n "${HAP_PLACE_REPORT_DIR:-}" ]] || { printf 'HAP_PLACE_REPORT_DIR required\n' >&2; exit 2; }
    HAP_PLACE_REPORT_DIR="$(readlink -m -- "$HAP_PLACE_REPORT_DIR")"
    export HAP_PLACE_REPORT_DIR
    [[ "$HAP_PLACE_REPORT_DIR" == "$report_base/"* &&
       -s "$HAP_PLACE_REPORT_DIR/fresh_place_complete.txt" &&
       -s "$HAP_PLACE_REPORT_DIR/s3_screen.txt" ]] || {
        printf 'No completed screened S3 placement\n' >&2; exit 2
    }
fi
mkdir -p "$HAP_REPORT_DIR"
status() {
    local rc="$?"
    local native_rc="$rc"
    trap - EXIT
    printf 'stage=%s\nexit_code=%s\nnative_exit_code=%s\nproject=%s\nreports=%s\nsynth_reports=%s\nroute_reports=%s\nplace_reports=%s\n' \
        "$stage" "$rc" "$native_rc" "$HAP_PROJECT_DIR" "$HAP_REPORT_DIR" \
        "${HAP_SYNTH_REPORT_DIR:-}" "${HAP_ROUTE_REPORT_DIR:-}" "${HAP_PLACE_REPORT_DIR:-}" \
        > "$HAP_REPORT_DIR/launcher_status.txt"
    if (( rc == 0 )) && [[ "$stage" != create ]]; then
        if ! python3 "$root/vivado/scripts/emit_current_board_evidence.py" \
            "$stage" "$root" "$HAP_PROJECT_DIR" "$HAP_REPORT_DIR"; then
            rc=1
            printf 'stage=%s\nexit_code=%s\nnative_exit_code=%s\nproject=%s\nreports=%s\nsynth_reports=%s\nroute_reports=%s\nplace_reports=%s\n' \
                "$stage" "$rc" "$native_rc" "$HAP_PROJECT_DIR" "$HAP_REPORT_DIR" \
                "${HAP_SYNTH_REPORT_DIR:-}" "${HAP_ROUTE_REPORT_DIR:-}" "${HAP_PLACE_REPORT_DIR:-}" \
                > "$HAP_REPORT_DIR/launcher_status.txt"
        fi
    fi
    exit "$rc"
}
trap status EXIT
sha256sum -- "$0" "$source_tcl" \
    "$root/vivado/scripts/emit_current_board_evidence.py" \
    "$root/vivado/scripts/mission0004_metadata_physical.tcl" \
    "$root/vivado/scripts/mission0005_coordinated_physical.tcl" \
    "$root/vivado/manifests/attention_mlp_board_core_v5_sources.list" \
    "$root/vivado/constraints/attention_mlp_vcu118_board_v5.xdc" \
    "$root/vivado/constraints/vcu118_ddr4_explicit_pins.xdc" \
    "$root/vivado/constraints/board_clock_domains.xdc" \
    "$root/vivado/constraints/mission0004_metadata_width_local.xdc" \
    "$root/vivado/constraints/mission0005_coordinated_partition.xdc" \
    /home/user/EDA-202/vivado/vivado_2025.2/2025.2/data/xhub/boards/XilinxBoardStore/boards/Xilinx/vcu118/2.0/board.xml \
    /home/user/EDA-202/vivado/vivado_2025.2/2025.2/data/xhub/boards/XilinxBoardStore/boards/Xilinx/vcu118/2.0/part0_pins.xml \
    /home/user/EDA-202/vivado/vivado_2025.2/2025.2/data/xhub/boards/XilinxBoardStore/boards/Xilinx/vcu118/2.0/preset.xml \
    > "$HAP_REPORT_DIR/launcher_inputs.sha256"
if [[ "$stage" == audit ]]; then
    sha256sum -- "$HAP_ROUTE_REPORT_DIR/routed.dcp" \
        "$HAP_ROUTE_REPORT_DIR/routed_checkpoint.sha256" \
        "$HAP_ROUTE_REPORT_DIR/launcher_status.txt" \
        "$HAP_ROUTE_REPORT_DIR/inputs.sha256" \
        "$HAP_ROUTE_REPORT_DIR/build_identity.txt" \
        >> "$HAP_REPORT_DIR/launcher_inputs.sha256"
fi
printf 'HAP_PROJECT_DIR=%q HAP_REPORT_DIR=%q HAP_SYNTH_REPORT_DIR=%q HAP_ROUTE_REPORT_DIR=%q HAP_PLACE_REPORT_DIR=%q HAP_JOBS=%q HAP_STAGE=%q nice -n ${HAP_NICE_INCREMENT:-5} %q -mode batch -notrace -source %q -log %q -journal %q\n' \
    "$HAP_PROJECT_DIR" "$HAP_REPORT_DIR" "${HAP_SYNTH_REPORT_DIR:-}" "${HAP_ROUTE_REPORT_DIR:-}" \
    "${HAP_PLACE_REPORT_DIR:-}" "$HAP_JOBS" "$stage" "$vivado" "$source_tcl" \
    "$HAP_REPORT_DIR/vivado.log" "$HAP_REPORT_DIR/vivado.jou" \
    > "$HAP_REPORT_DIR/argv.txt"
cd "$root/vivado"
nice -n "${HAP_NICE_INCREMENT:-5}" "$vivado" -mode batch -notrace -source "$source_tcl" \
    -log "$HAP_REPORT_DIR/vivado.log" \
    -journal "$HAP_REPORT_DIR/vivado.jou"
