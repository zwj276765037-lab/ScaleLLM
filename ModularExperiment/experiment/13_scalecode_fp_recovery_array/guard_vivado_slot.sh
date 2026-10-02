#!/usr/bin/env bash

# Source immediately before M13 implementation/netlist-power launches.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    printf 'guard_vivado_slot.sh must be sourced\n' >&2
    exit 2
fi

if [[ "${HAP_M13_VIVADO_GUARD_HELD:-0}" != 1 ]]; then
    # Separate Vivado processes are acceptable when the host has sufficient
    # headroom.  M13 SC peaked at 6.56 GiB and the larger historical M09 FP
    # implementations peaked below 20 GiB.  Keep a conservative 96 GiB
    # MemAvailable floor so M13 cannot push an already constrained host into
    # swap/OOM, while not blocking merely because another Vivado exists.
    min_available_kb="${HAP_M13_MIN_AVAILABLE_KB:-100663296}"
    available_kb=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
    if [[ -z "$available_kb" || "$available_kb" -lt "$min_available_kb" ]]; then
        printf 'M13_VIVADO_GUARD_BLOCKED: available memory %s KiB is below required %s KiB\n' \
            "${available_kb:-unknown}" "$min_available_kb" >&2
        return 75
    fi
    command -v flock >/dev/null 2>&1 || {
        printf 'M13_VIVADO_GUARD_BLOCKED: flock is unavailable\n' >&2
        return 75
    }
    exec 9>/tmp/scalellm_modular_vivado.lock
    if ! flock -n 9; then
        printf 'M13_VIVADO_GUARD_BLOCKED: modular Vivado lock is held\n' >&2
        return 75
    fi
    export HAP_M13_VIVADO_GUARD_HELD=1
    export HAP_M13_AVAILABLE_KB_AT_LAUNCH="$available_kb"
fi
