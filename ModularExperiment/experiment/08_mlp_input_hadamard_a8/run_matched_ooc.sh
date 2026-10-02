#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 1 && ( "$1" == sc || "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s sc|fp16|fp32\n' "$0" >&2
    exit 2
}
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/08_mlp_input_hadamard_a8"
variant="$1"
case "$variant" in
    sc) top=hap_mlp_input_frontend16_compact_cache ;;
    fp16) top=m8_fp16_mlp_input_frontend16_compact_cache ;;
    fp32) top=m8_fp32_mlp_input_frontend16_compact_cache ;;
esac
export HAP_OOC_MODULE=08_mlp_input_hadamard_a8
export HAP_OOC_VARIANT="$variant"
export HAP_OOC_NAME="${variant}_mlp_input_frontend_native_scale_cache_100mhz"
export HAP_OOC_TOP="$top"
if [[ "$variant" == sc ]]; then
    export HAP_OOC_SOURCES_FILE="$MODULE/vivado/sc.sources"
    unset HAP_OOC_PRE_SYNTH_TCL || true
else
    export HAP_OOC_SOURCES_FILE="$MODULE/vivado/fp.sources"
    export HAP_OOC_PRE_SYNTH_TCL="$MODULE/vivado/create_fp_ip.tcl"
fi
exec "$ROOT/ModularExperiment/tools/scripts/run_ooc_100mhz.sh"
