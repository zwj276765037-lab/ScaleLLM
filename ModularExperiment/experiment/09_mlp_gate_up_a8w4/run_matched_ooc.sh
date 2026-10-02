#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 1 && ( "$1" == sc || "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s sc|fp16|fp32\n' "$0" >&2
    exit 2
}
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/09_mlp_gate_up_a8w4"
variant="$1"
case "$variant" in
    sc) top=m09_sc_gate_up_serial_ooc_wrapper ;;
    fp16) top=m09_fp16_gate_up_serial_ooc_wrapper ;;
    fp32) top=m09_fp32_gate_up_serial_ooc_wrapper ;;
esac
export HAP_OOC_MODULE=09_mlp_gate_up_a8w4
export HAP_OOC_VARIANT="$variant"
export HAP_OOC_NAME="${variant}_gate_up_a8w4_native_scale_serial_ooc_100mhz"
export HAP_OOC_TOP="$top"
if [[ "$variant" == sc ]]; then
    export HAP_OOC_SOURCES_FILE="$MODULE/vivado/sc_ooc.sources"
    unset HAP_OOC_PRE_SYNTH_TCL || true
else
    export HAP_OOC_SOURCES_FILE="$MODULE/vivado/fp_ooc.sources"
    export HAP_OOC_PRE_SYNTH_TCL="$MODULE/vivado/create_fp_ip.tcl"
fi
exec "$ROOT/ModularExperiment/tools/scripts/run_ooc_100mhz.sh"
