#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPORT_ROOT="$ROOT/vivado/reports"

summary_value() {
    local file="$1" key="$2"
    awk -F= -v key="$key" '$1 == key {print substr($0, length(key) + 2); exit}' \
        "$file"
}

first_summary_value() {
    local file="$1" key value
    shift
    for key in "$@"; do
        value="$(summary_value "$file" "$key")"
        if [[ -n "$value" ]]; then
            printf '%s\n' "$value"
            return
        fi
    done
    printf '%s\n' '-'
}

command_elapsed() {
    local file="$1" command="$2"
    awk -v prefix="$command: Time (s):" '
        index($0, prefix) == 1 {
            value = $0
            sub(/^.*elapsed = /, "", value)
            sub(/[[:space:]].*$/, "", value)
            last = value
        }
        END {print last == "" ? "-" : last}
    ' "$file"
}

command_cpu() {
    local file="$1" command="$2"
    awk -v prefix="$command: Time (s):" '
        index($0, prefix) == 1 {
            value = $0
            sub(/^.*cpu = /, "", value)
            sub(/[[:space:]]*;.*/, "", value)
            last = value
        }
        END {print last == "" ? "-" : last}
    ' "$file"
}

effective_cores() {
    local cpu="$1" elapsed="$2"
    awk -v cpu="$cpu" -v elapsed="$elapsed" '
        function seconds(value, fields, count) {
            count = split(value, fields, ":")
            if (count != 3) return -1
            return fields[1] * 3600 + fields[2] * 60 + fields[3]
        }
        BEGIN {
            cpu_seconds = seconds(cpu)
            elapsed_seconds = seconds(elapsed)
            if (cpu_seconds < 0 || elapsed_seconds <= 0) {
                print "-"
            } else {
                printf "%.2f\n", cpu_seconds / elapsed_seconds
            }
        }
    '
}

command_effective_cores() {
    local file="$1" command="$2" cpu elapsed
    cpu="$(command_cpu "$file" "$command")"
    elapsed="$(command_elapsed "$file" "$command")"
    effective_cores "$cpu" "$elapsed"
}

peak_memory_mb() {
    local file="$1"
    awk '
        /Memory \(MB\): peak = / {
            value = $0
            sub(/^.*Memory \(MB\): peak = /, "", value)
            sub(/[[:space:]]*;.*/, "", value)
            if ((value + 0) > peak) peak = value + 0
        }
        END {print (peak > 0 ? peak : "-")}
    ' "$file"
}

if (( $# == 0 )); then
    mapfile -d '' run_dirs < <(find "$REPORT_ROOT" -mindepth 1 -maxdepth 1 \
        -type d \( -name 'production_v5_*' -o \
        -name 'projection_core16x16_w8_reuse_registered_ooc_*' \) \
        -print0 | sort -z)
else
    run_dirs=()
    for requested in "$@"; do
        if [[ "$requested" = /* ]]; then
            run_dirs+=("$requested")
        else
            run_dirs+=("$REPORT_ROOT/$requested")
        fi
    done
fi

printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    run stage mode status jobs directive synth opt place physopt route wns whs \
    data_bufg level6_plus synth_cores opt_cores place_cores physopt_cores \
    route_cores peak_mb

for dir in "${run_dirs[@]}"; do
    summary="$dir/summary.txt"
    log="$dir/vivado.log"
    [[ -s "$summary" && -s "$log" ]] || continue

    run="$(basename "$dir")"
    stage="$(first_summary_value "$summary" stage)"
    mode="$(first_summary_value "$summary" flow_mode)"
    status="$(first_summary_value "$summary" status)"
    jobs="$(first_summary_value "$summary" jobs)"
    directive="$(first_summary_value "$summary" place_directive route_directive)"
    wns="$(first_summary_value "$summary" post_place_wns_ns wns_ns)"
    whs="$(first_summary_value "$summary" post_place_whs_ns whs_ns)"
    data_bufg="$(first_summary_value "$summary" data_bufg post_opt_data_bufg)"
    level6="$(first_summary_value "$summary" \
        congestion_level6_or_higher_windows \
        level6_or_higher_congestion_windows)"

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$run" "$stage" "$mode" "$status" "$jobs" "$directive" \
        "$(command_elapsed "$log" synth_design)" \
        "$(command_elapsed "$log" opt_design)" \
        "$(command_elapsed "$log" place_design)" \
        "$(command_elapsed "$log" phys_opt_design)" \
        "$(command_elapsed "$log" route_design)" \
        "$wns" "$whs" "$data_bufg" "$level6" \
        "$(command_effective_cores "$log" synth_design)" \
        "$(command_effective_cores "$log" opt_design)" \
        "$(command_effective_cores "$log" place_design)" \
        "$(command_effective_cores "$log" phys_opt_design)" \
        "$(command_effective_cores "$log" route_design)" \
        "$(peak_memory_mb "$log")"
done
