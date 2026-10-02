#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 1 && ( "$1" == sc || "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s sc|fp16|fp32\n' "$0" >&2
    exit 2
}
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/01_attention_input_hadamard_a8"
variant="$1"
case "$variant" in
    sc) top=hap_attention_frontend_8row ;;
    fp16) top=m1_fp16_attention_frontend_8row ;;
    fp32) top=m1_fp32_attention_frontend_8row ;;
esac
export HAP_OOC_MODULE=01_attention_input_hadamard_a8
export HAP_OOC_VARIANT="$variant"
export HAP_OOC_NAME="${variant}_attention_frontend_native_scale_cache_100mhz"
export HAP_OOC_TOP="$top"
if [[ "$variant" == sc ]]; then
    export HAP_OOC_SOURCES_FILE="$MODULE/vivado/sc.sources"
    unset HAP_OOC_PRE_SYNTH_TCL || true
else
    export HAP_OOC_SOURCES_FILE="$MODULE/vivado/fp.sources"
    export HAP_OOC_PRE_SYNTH_TCL="$MODULE/vivado/create_fp_ip.tcl"
fi
exec "$ROOT/ModularExperiment/tools/scripts/run_ooc_100mhz.sh"
