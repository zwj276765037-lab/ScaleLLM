#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 1 && ( "$1" == sc || "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s sc|fp16|fp32\n' "$0" >&2
    exit 2
}
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/04_attention_kv12_quantizer"
variant="$1"
case "$variant" in
    sc) top=m4_sc_kv_boundary_top ;;
    fp16) top=m4_fp16_kv_boundary_top ;;
    fp32) top=m4_fp32_kv_boundary_top ;;
esac
export HAP_OOC_MODULE=04_attention_kv12_quantizer
export HAP_OOC_VARIANT="$variant"
export HAP_OOC_NAME="${variant}_kv_producer_cache_boundary_100mhz"
export HAP_OOC_TOP="$top"
if [[ "$variant" == sc ]]; then
    export HAP_OOC_SOURCES_FILE="$MODULE/vivado/sc.sources"
    unset HAP_OOC_PRE_SYNTH_TCL || true
else
    export HAP_OOC_SOURCES_FILE="$MODULE/vivado/fp.sources"
    export HAP_OOC_PRE_SYNTH_TCL="$MODULE/vivado/create_fp_ip.tcl"
fi
exec "$ROOT/ModularExperiment/tools/scripts/run_ooc_100mhz.sh"
