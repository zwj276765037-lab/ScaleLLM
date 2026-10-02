#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
QUEUE="$ROOT/vivado/scripts/run_attention_mlp_vcu118_v5_board_when_p14_route_pass.sh"

fail() {
    printf 'V5_BOARD_QUEUE_STATIC_TEST_FAIL: %s\n' "$*" >&2
    exit 1
}

[[ -s "$QUEUE" ]] || fail "missing queue script"
bash -n "$QUEUE" || fail "queue Bash syntax"

for literal in \
        '[[ "$HAP_JOBS" == 32 ]]' \
        '(( poll_seconds >= 1800 && poll_seconds <= 3600 ))' \
        'mlpadd-mission0163-p14-route' \
        'hap_v5_verify_ooc_route_artifact "$route_dir"' \
        '"${#SOURCE_MANIFESTS[@]}" -eq 3' \
        '"${#RTL_SOURCES[@]}" -eq 87' \
        '"${#SOURCE_CLOSURE[@]}" -eq 90' \
        'P14_BOARD_QUEUE_INPUT_DRIFT' \
        'P14_BOARD_QUEUE_ROUTE_WAIT' \
        'P14_BOARD_QUEUE_ROUTE_PASS' \
        'HAP_PROJECT_DIR="$project_dir" "$BD_LAUNCHER"' \
        '"$BOARD_LAUNCHER" "$route_dir"' \
        'HAP_AUDIT_DIR="$audit_dir" "$AUDIT_LAUNCHER"' \
        'P14_BOARD_QUEUE_PASS'; do
    grep -Fq -- "$literal" "$QUEUE" || fail "missing contract: $literal"
done

bd_line="$(grep -nF 'HAP_PROJECT_DIR="$project_dir" "$BD_LAUNCHER"' \
    "$QUEUE" | cut -d: -f1)"
build_line="$(grep -nF '"$BOARD_LAUNCHER" "$route_dir"' \
    "$QUEUE" | cut -d: -f1)"
audit_line="$(grep -nF 'HAP_AUDIT_DIR="$audit_dir" "$AUDIT_LAUNCHER"' \
    "$QUEUE" | cut -d: -f1)"
[[ "$bd_line" =~ ^[0-9]+$ && "$build_line" =~ ^[0-9]+$ &&
    "$audit_line" =~ ^[0-9]+$ && "$bd_line" -lt "$build_line" &&
    "$build_line" -lt "$audit_line" ]] || fail "stage order is not BD/build/audit"

for forbidden in run_program_attention_mlp hw_server /dev/xdma set_false_path; do
    ! grep -Fq -- "$forbidden" "$QUEUE" || \
        fail "forbidden hardware/timing action present: $forbidden"
done

printf 'V5_BOARD_QUEUE_STATIC_TEST_PASS\n'
printf 'stage_order=route_verify,bd_create,board_build,independent_audit\n'
printf 'hardware_programming=0\n'
