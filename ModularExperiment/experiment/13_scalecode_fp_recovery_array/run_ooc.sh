#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 1 && ( "$1" == sc || "$1" == sc_auto || \
                  "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s sc|sc_auto|fp16|fp32\n' "$0" >&2
    exit 2
}
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/13_scalecode_fp_recovery_array"
variant="$1"
source "$MODULE/guard_vivado_slot.sh"
case "$variant" in
    sc) top=m13_sc_recovery_array96 ;;
    sc_auto) top=m13_sc_recovery_array96_auto ;;
    fp16) top=m13_fp16_recovery_array96 ;;
    fp32) top=m13_fp32_recovery_array96 ;;
esac
export HAP_OOC_MODULE=13_scalecode_fp_recovery_array
export HAP_OOC_VARIANT="$variant"
export HAP_OOC_NAME="${variant}_recovery_only_array96_100mhz"
export HAP_OOC_TOP="$top"
export HAP_OOC_LAUNCHER="$MODULE/run_ooc.sh"
export HAP_OOC_GUARD="$MODULE/guard_vivado_slot.sh"
if [[ "$variant" == sc || "$variant" == sc_auto ]]; then
    export HAP_OOC_SOURCES_FILE="$MODULE/vivado/${variant}.sources"
    unset HAP_OOC_PRE_SYNTH_TCL || true
else
    export HAP_OOC_SOURCES_FILE="$MODULE/vivado/fp.sources"
    export HAP_OOC_PRE_SYNTH_TCL="$MODULE/vivado/create_fp_ip.tcl"
fi
exec "$ROOT/ModularExperiment/tools/scripts/run_ooc_100mhz.sh"
