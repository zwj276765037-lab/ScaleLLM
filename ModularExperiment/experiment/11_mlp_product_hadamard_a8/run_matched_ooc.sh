#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 1 && ( "$1" == sc || "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s sc|fp16|fp32\n' "$0" >&2
    exit 2
}
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/11_mlp_product_hadamard_a8"
variant="$1"
case "$variant" in
    sc) top=hap_mlp_product_frontend16_q4_ooc_wrapper ;;
    fp16) top=m11_fp16_mlp_product_frontend16_q4_ooc_wrapper ;;
    fp32) top=m11_fp32_mlp_product_frontend16_q4_ooc_wrapper ;;
esac
export HAP_OOC_MODULE=11_mlp_product_hadamard_a8
export HAP_OOC_VARIANT="$variant"
export HAP_OOC_NAME="${variant}_mlp_product_frontend_native_scale_serial_ooc_100mhz"
export HAP_OOC_TOP="$top"
if [[ "$variant" == sc ]]; then
    export HAP_OOC_SOURCES_FILE="$MODULE/vivado/sc_ooc.sources"
    unset HAP_OOC_PRE_SYNTH_TCL || true
else
    export HAP_OOC_SOURCES_FILE="$MODULE/vivado/fp_ooc.sources"
    export HAP_OOC_PRE_SYNTH_TCL="$MODULE/vivado/create_fp_ip.tcl"
fi
exec "$ROOT/ModularExperiment/tools/scripts/run_ooc_100mhz.sh"
