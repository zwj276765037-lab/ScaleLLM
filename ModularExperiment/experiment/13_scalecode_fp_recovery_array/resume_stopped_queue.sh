#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 2 ]] || {
    printf 'usage: %s TARGET_SERVICE TIMER_UNIT\n' "$0" >&2
    exit 2
}
target_service="$1"
timer_unit="$2"

if ! systemctl --user is-active --quiet "$target_service"; then
    systemctl --user stop "$timer_unit" 2>/dev/null || true
    exit 0
fi

main_pid=$(systemctl --user show "$target_service" -p MainPID --value)
if [[ ! "$main_pid" =~ ^[0-9]+$ || "$main_pid" -eq 0 || \
      ! -r "/proc/$main_pid/stat" ]]; then
    exit 0
fi

state=$(awk '{print $3}' "/proc/$main_pid/stat")
if [[ "$state" == T || "$state" == t ]]; then
    kill -CONT "$main_pid"
    printf '[%s] resumed stopped queue pid=%s service=%s\n' \
        "$(date --iso-8601=seconds)" "$main_pid" "$target_service"
fi
