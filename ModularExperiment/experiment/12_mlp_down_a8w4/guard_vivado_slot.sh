#!/usr/bin/env bash

# Source this file immediately before an M12 Vivado/XSIM launch.  One parent
# (for example run_serial_ab.sh) may hold and export the guard for its strictly
# sequential children.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    printf 'guard_vivado_slot.sh must be sourced\n' >&2
    exit 2
fi

if [[ "${HAP_M12_VIVADO_GUARD_HELD:-0}" != 1 ]]; then
    guard_module=/home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment/experiment/12_mlp_down_a8w4
    guard_active=$(ps -eo pid=,args= | grep -E \
        'Vivado/bin/(vivado|loader)|unwrapped/[^ ]*/(vivado|parallel_synth_helper)|xsim\.dir/[^ ]*/xsimk' \
        | grep -Fv 'grep -E' \
        | grep -Fv "$guard_module" || true)
    if [[ -n "$guard_active" ]]; then
        printf 'M12_VIVADO_GUARD_BLOCKED: unrelated Vivado/XSIM is active\n%s\n' \
            "$guard_active" >&2
        return 75
    fi

    command -v flock >/dev/null 2>&1 || {
        printf 'M12_VIVADO_GUARD_BLOCKED: flock is unavailable\n' >&2
        return 75
    }
    exec 9>/tmp/scalellm_modular_vivado.lock
    if ! flock -n 9; then
        printf 'M12_VIVADO_GUARD_BLOCKED: modular Vivado lock is held\n' >&2
        return 75
    fi
    export HAP_M12_VIVADO_GUARD_HELD=1
fi
