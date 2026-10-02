#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 1 && ( "$1" == sc || "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s sc|fp16|fp32\n' "$0" >&2
    exit 2
}
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/07_attention_pv"
variant="$1"
case "$variant" in
    sc) top=m07_sc_pv_boundary ;;
    fp16) top=m07_fp16_pv_boundary ;;
    fp32) top=m07_fp32_pv_boundary ;;
esac
export HAP_OOC_MODULE=07_attention_pv
export HAP_OOC_VARIANT="$variant"
export HAP_OOC_NAME="${variant}_probability_v_to_pv_boundary_ooc_100mhz"
export HAP_OOC_TOP="$top"
if [[ "$variant" == sc ]]; then
    export HAP_OOC_SOURCES_FILE="$MODULE/vivado/boundary_sc.sources"
    unset HAP_OOC_PRE_SYNTH_TCL || true
else
    export HAP_OOC_SOURCES_FILE="$MODULE/vivado/boundary_fp.sources"
    export HAP_OOC_PRE_SYNTH_TCL="$MODULE/vivado/create_boundary_all_fp_ip.tcl"
fi
exec "$ROOT/ModularExperiment/tools/scripts/run_ooc_100mhz.sh"
