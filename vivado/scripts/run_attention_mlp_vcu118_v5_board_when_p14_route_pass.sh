#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WATCHER="$(readlink -e -- "${BASH_SOURCE[0]}")"
PROVENANCE_LIB="$ROOT/vivado/scripts/v5_board_build_provenance.sh"
BOARD_CONTRACT="$ROOT/vivado/scripts/check_attention_mlp_vcu118_v5_board_contract.sh"
BD_LAUNCHER="$ROOT/vivado/scripts/run_create_attention_mlp_vcu118_dual_ddr_v5_bd.sh"
BD_WRAPPER="$ROOT/vivado/scripts/create_attention_mlp_vcu118_dual_ddr_v5_bd.tcl"
BD_CONSTRUCTOR="$ROOT/vivado/scripts/create_attention_mlp_vcu118_dual_ddr_bd.tcl"
BOARD_LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_vcu118_v5_bitstream.sh"
BUILD_TCL="$ROOT/vivado/scripts/build_attention_mlp_vcu118_v5_bitstream.tcl"
BOARD_GATE="$ROOT/vivado/scripts/attention_mlp_vcu118_v5_post_route_gate.tcl"
INVENTORY_TCL="$ROOT/vivado/scripts/write_attention_mlp_vcu118_v5_xdc_inventory.tcl"
APPLY_FLOORPLAN="$ROOT/vivado/scripts/apply_attention_mlp_vcu118_v5_floorplan.tcl"
SELECTOR_LIB="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
GEOMETRY_LIB="$ROOT/vivado/scripts/projection_core16x16_w8_reuse_ooc_floorplan.tcl"
P5_LIB="$ROOT/vivado/scripts/v5_production_p5_input_partition_floorplan.tcl"
P9_POST_LIB="$ROOT/vivado/scripts/v5_production_p9_postprocess_partition_floorplan.tcl"
P9_QUANTIZER3_LIB="$ROOT/vivado/scripts/v5_production_p9_quantizer3_locality_floorplan.tcl"
P14_RELIEF_LIB="$ROOT/vivado/scripts/v5_production_p14_region2_x2_relief_floorplan.tcl"
P8_BOUNDARY_LIB="$ROOT/vivado/scripts/audit_mlp_p8_parent_ingress_boundary_replica_aware.tcl"
AUDIT_LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_vcu118_v5_post_route_audit.sh"
AUDIT_TCL="$ROOT/vivado/scripts/audit_attention_mlp_vcu118_v5_post_route.tcl"
BOARD_XDC="$ROOT/vivado/constraints/attention_mlp_vcu118_board_v5.xdc"
BOARD_MANIFEST="$ROOT/vivado/manifests/attention_mlp_board_core_v5_sources.list"

[[ $# -eq 1 ]] || {
    printf 'usage: %s P14_ROUTE_ARTIFACT_DIR\n' "$0" >&2
    exit 2
}
export HAP_JOBS="${HAP_JOBS:-32}"
[[ "$HAP_JOBS" == 32 ]] || {
    printf 'P14 board queue requires HAP_JOBS=32\n' >&2
    exit 2
}
poll_seconds="${HAP_POLL_SECONDS:-1800}"
[[ "$poll_seconds" =~ ^[0-9]+$ ]] &&
    (( poll_seconds >= 1800 && poll_seconds <= 3600 )) || {
    printf 'HAP_POLL_SECONDS must be in 1800..3600\n' >&2
    exit 2
}
route_service="${HAP_ROUTE_SERVICE:-mlpadd-mission0163-p14-route}"
[[ "$route_service" =~ ^[A-Za-z0-9_.@:-]+$ ]] || {
    printf 'invalid P14 route service: %q\n' "$route_service" >&2
    exit 2
}
route_dir="$(readlink -m -- "$1")"
for variable in HAP_BOARD_PROJECT_DIR HAP_BOARD_REPORT_DIR \
        HAP_BOARD_AUDIT_DIR; do
    [[ -n "${!variable:-}" ]] || {
        printf 'P14 board queue requires fixed %s\n' "$variable" >&2
        exit 2
    }
done
project_dir="$(readlink -m -- "$HAP_BOARD_PROJECT_DIR")"
board_dir="$(readlink -m -- "$HAP_BOARD_REPORT_DIR")"
audit_dir="$(readlink -m -- "$HAP_BOARD_AUDIT_DIR")"
for output in "$project_dir" "$board_dir" "$audit_dir"; do
    [[ ! -e "$output" ]] || {
        printf 'P14 board queue output already exists: %s\n' "$output" >&2
        exit 2
    }
done

for input in "$WATCHER" "$PROVENANCE_LIB" "$BOARD_CONTRACT" \
        "$BD_LAUNCHER" "$BD_WRAPPER" "$BD_CONSTRUCTOR" \
        "$BOARD_LAUNCHER" "$BUILD_TCL" "$BOARD_GATE" "$INVENTORY_TCL" \
        "$APPLY_FLOORPLAN" "$SELECTOR_LIB" "$GEOMETRY_LIB" "$P5_LIB" \
        "$P9_POST_LIB" "$P9_QUANTIZER3_LIB" "$P14_RELIEF_LIB" \
        "$P8_BOUNDARY_LIB" "$AUDIT_LAUNCHER" "$AUDIT_TCL" "$BOARD_XDC" \
        "$BOARD_MANIFEST"; do
    [[ -s "$input" ]] || {
        printf 'missing queued P14 board input: %s\n' "$input" >&2
        exit 2
    }
done

source "$PROVENANCE_LIB"
hap_v5_expand_source_manifest "$ROOT" "$BOARD_MANIFEST" \
    SOURCE_MANIFESTS RTL_SOURCES SOURCE_CLOSURE
[[ "${#SOURCE_MANIFESTS[@]}" -eq 3 && "${#RTL_SOURCES[@]}" -eq 87 &&
    "${#SOURCE_CLOSURE[@]}" -eq 90 ]] || {
    printf 'P14 board queue source closure drifted: %d/%d/%d\n' \
        "${#SOURCE_MANIFESTS[@]}" "${#RTL_SOURCES[@]}" \
        "${#SOURCE_CLOSURE[@]}" >&2
    exit 2
}

frozen_inputs=("$WATCHER" "$PROVENANCE_LIB" "$BOARD_CONTRACT"
    "$BD_LAUNCHER" "$BD_WRAPPER" "$BD_CONSTRUCTOR" "$BOARD_LAUNCHER"
    "$BUILD_TCL" "$BOARD_GATE" "$INVENTORY_TCL" "$APPLY_FLOORPLAN"
    "$SELECTOR_LIB" "$GEOMETRY_LIB" "$P5_LIB" "$P9_POST_LIB"
    "$P9_QUANTIZER3_LIB" "$P14_RELIEF_LIB" "$P8_BOUNDARY_LIB"
    "$AUDIT_LAUNCHER" "$AUDIT_TCL" "$BOARD_XDC" "${SOURCE_CLOSURE[@]}")
frozen_digest="$(sha256sum -- "${frozen_inputs[@]}" | sha256sum | awk '{print $1}')"

verify_frozen_inputs() {
    local current_digest
    current_digest="$(sha256sum -- "${frozen_inputs[@]}" | sha256sum | awk '{print $1}')"
    [[ "$current_digest" == "$frozen_digest" ]] || {
        printf 'P14_BOARD_QUEUE_INPUT_DRIFT time=%s expected=%s actual=%s\n' \
            "$(date --iso-8601=seconds)" "$frozen_digest" \
            "$current_digest" >&2
        exit 3
    }
}

wait_for_slot() {
    local -a active_batch
    while true; do
        verify_frozen_inputs
        mapfile -t active_batch < <(pgrep -af \
            '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
        if [[ "${#active_batch[@]}" -eq 0 ]]; then
            printf 'P14_BOARD_QUEUE_SLOT_FREE time=%s\n' \
                "$(date --iso-8601=seconds)"
            return 0
        fi
        printf 'P14_BOARD_QUEUE_SLOT_WAIT time=%s active_batch=%s\n' \
            "$(date --iso-8601=seconds)" "${#active_batch[@]}"
        sleep "$poll_seconds"
    done
}

printf 'P14_BOARD_QUEUE_READY time=%s poll_seconds=%s frozen_inputs=%s frozen_digest=%s\n' \
    "$(date --iso-8601=seconds)" "$poll_seconds" "${#frozen_inputs[@]}" \
    "$frozen_digest"

while true; do
    verify_frozen_inputs
    route_state="$(systemctl --user show "${route_service}.service" \
        -p ActiveState --value 2>/dev/null || true)"
    case "$route_state" in
        active|activating|reloading)
            printf 'P14_BOARD_QUEUE_ROUTE_WAIT time=%s route_service_state=%s\n' \
                "$(date --iso-8601=seconds)" "$route_state"
            sleep "$poll_seconds"
            continue
            ;;
    esac
    if ! hap_v5_verify_ooc_route_artifact "$route_dir"; then
        printf 'P14_BOARD_QUEUE_ABORT time=%s route_service_state=%s\n' \
            "$(date --iso-8601=seconds)" "${route_state:-unknown}" >&2
        exit 4
    fi
    printf 'P14_BOARD_QUEUE_ROUTE_PASS time=%s\n' \
        "$(date --iso-8601=seconds)"
    break
done

while true; do
    wait_for_slot
    set +e
    HAP_PROJECT_DIR="$project_dir" "$BD_LAUNCHER"
    rc=$?
    set -e
    if [[ "$rc" -eq 75 && ! -e "$project_dir" ]]; then
        printf 'P14_BOARD_QUEUE_BD_SLOT_RACE time=%s\n' \
            "$(date --iso-8601=seconds)"
        sleep "$poll_seconds"
        continue
    fi
    [[ "$rc" -eq 0 ]] || exit "$rc"
    break
done

project_file="$project_dir/attention_mlp_vcu118_v5_dual_ddr.xpr"
[[ -s "$project_file" ]] || {
    printf 'P14 board queue V5 project is missing: %s\n' "$project_file" >&2
    exit 5
}
verify_frozen_inputs

while true; do
    wait_for_slot
    set +e
    HAP_PROJECT_FILE="$project_file" HAP_REPORT_DIR="$board_dir" \
        "$BOARD_LAUNCHER" "$route_dir"
    rc=$?
    set -e
    if [[ "$rc" -eq 75 && ! -e "$board_dir" ]]; then
        printf 'P14_BOARD_QUEUE_BUILD_SLOT_RACE time=%s\n' \
            "$(date --iso-8601=seconds)"
        sleep "$poll_seconds"
        continue
    fi
    [[ "$rc" -eq 0 ]] || exit "$rc"
    break
done
verify_frozen_inputs

while true; do
    wait_for_slot
    set +e
    HAP_AUDIT_DIR="$audit_dir" "$AUDIT_LAUNCHER" \
        "$board_dir/attention_mlp_vcu118_v5_post_route.dcp" \
        "$board_dir/attention_mlp_vcu118_v5.bit" \
        "$board_dir/XDC_SOURCE_INVENTORY"
    rc=$?
    set -e
    if [[ "$rc" -eq 75 && ! -e "$audit_dir" ]]; then
        printf 'P14_BOARD_QUEUE_AUDIT_SLOT_RACE time=%s\n' \
            "$(date --iso-8601=seconds)"
        sleep "$poll_seconds"
        continue
    fi
    [[ "$rc" -eq 0 ]] || exit "$rc"
    break
done
verify_frozen_inputs

printf 'P14_BOARD_QUEUE_PASS time=%s project=%s board=%s audit=%s\n' \
    "$(date --iso-8601=seconds)" "$project_dir" "$board_dir" "$audit_dir"
