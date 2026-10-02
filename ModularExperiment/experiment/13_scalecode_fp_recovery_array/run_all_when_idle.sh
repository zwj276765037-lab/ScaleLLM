#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/13_scalecode_fp_recovery_array"
RESULT="$ROOT/ModularExperiment/result/13_scalecode_fp_recovery_array"
queue_dir="${1:-}"
[[ -n "$queue_dir" ]] || {
    printf 'usage: %s QUEUE_RESULT_DIR\n' "$0" >&2
    exit 2
}
mkdir -p "$queue_dir"

queue_failed=1
finish_queue() {
    rc=$?
    if [[ "$queue_failed" == 0 && "$rc" == 0 ]]; then
        printf 'COMPLETE\n' > "$queue_dir/STATUS"
    else
        printf 'FAIL rc=%s\n' "$rc" > "$queue_dir/STATUS"
    fi
    printf 'finished_at=%s rc=%s\n' "$(date --iso-8601=seconds)" "$rc" \
        >> "$queue_dir/manifest.txt"
}
trap finish_queue EXIT

printf 'WAITING_FOR_IDLE\n' > "$queue_dir/STATUS"
printf 'started_at=%s\nmodule=13_scalecode_fp_recovery_array\n' \
    "$(date --iso-8601=seconds)" > "$queue_dir/manifest.txt"

wait_until_idle() {
    while true; do
        min_available_kb="${HAP_M13_MIN_AVAILABLE_KB:-100663296}"
        available_kb=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
        if [[ -n "$available_kb" && "$available_kb" -ge "$min_available_kb" ]]; then
            return 0
        fi
        printf '[%s] waiting for memory: available=%s KiB required=%s KiB\n' \
            "$(date --iso-8601=seconds)" "${available_kb:-unknown}" \
            "$min_available_kb"
        sleep 30
    done
}

has_pass_result() {
    variant="$1"
    kind="$2"
    find "$RESULT/raw/$variant/$kind" -mindepth 2 -maxdepth 2 \
        -type f -name STATUS -exec grep -lFx PASS {} + 2>/dev/null \
        | grep -q .
}

run_guarded() {
    phase="$1"
    shift
    while true; do
        printf 'WAITING_FOR_IDLE\n' > "$queue_dir/STATUS"
        wait_until_idle
        printf '%s\n' "$phase" > "$queue_dir/STATUS"
        set +e
        "$@"
        rc=$?
        set -e
        if [[ "$rc" == 75 ]]; then
            printf 'WAITING_FOR_IDLE\n' > "$queue_dir/STATUS"
            printf '[%s] slot raced; returning to wait\n' \
                "$(date --iso-8601=seconds)"
            sleep 30
            continue
        fi
        return "$rc"
    done
}

official_variants=(sc_auto fp16 fp32)

for variant in "${official_variants[@]}"; do
    if has_pass_result "$variant" xsim; then
        printf '[%s] skipping existing PASS XSIM %s\n' \
            "$(date --iso-8601=seconds)" "$variant"
        continue
    fi
    printf '[%s] starting XSIM %s\n' "$(date --iso-8601=seconds)" "$variant"
    run_guarded "XSIM_${variant}_RUNNING" "$MODULE/run_xsim.sh" "$variant"
done

for variant in "${official_variants[@]}"; do
    if has_pass_result "$variant" ooc; then
        printf '[%s] skipping existing PASS OOC %s\n' \
            "$(date --iso-8601=seconds)" "$variant"
        continue
    fi
    printf '[%s] starting OOC %s\n' "$(date --iso-8601=seconds)" "$variant"
    run_guarded "OOC_${variant}_RUNNING" "$MODULE/run_ooc.sh" "$variant"
done

for variant in "${official_variants[@]}"; do
    if has_pass_result "$variant" power; then
        printf '[%s] skipping existing PASS netlist power %s\n' \
            "$(date --iso-8601=seconds)" "$variant"
        continue
    fi
    printf '[%s] starting netlist power %s\n' \
        "$(date --iso-8601=seconds)" "$variant"
    run_guarded "POWER_${variant}_RUNNING" \
        "$MODULE/run_netlist_power.sh" "$variant"
done

queue_failed=0
printf '[%s] M13 OOC and power queue complete\n' "$(date --iso-8601=seconds)"
