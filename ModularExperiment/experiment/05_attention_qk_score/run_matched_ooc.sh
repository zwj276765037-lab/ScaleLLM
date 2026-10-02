#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 1 && ( "$1" == sc || "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s sc|fp16|fp32\n' "$0" >&2
    exit 2
}

ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/05_attention_qk_score"
variant="$1"
case "$variant" in
    sc) top=hap_qk_score_row_128 ;;
    fp16) top=m5_fp16_qk_top ;;
    fp32) top=m5_fp32_qk_top ;;
esac

export HAP_OOC_MODULE=05_attention_qk_score
export HAP_OOC_VARIANT="$variant"
export HAP_OOC_NAME="${variant}_matched_qk_slot_operator_only_100mhz"
export HAP_OOC_TOP="$top"
if [[ "$variant" == sc ]]; then
    export HAP_OOC_SOURCES_FILE="$MODULE/vivado/sc.sources"
    unset HAP_OOC_PRE_SYNTH_TCL || true
else
    export HAP_OOC_SOURCES_FILE="$MODULE/vivado/fp.sources"
    export HAP_OOC_PRE_SYNTH_TCL="$MODULE/vivado/create_fp_ip.tcl"
fi
exec "$ROOT/ModularExperiment/tools/scripts/run_ooc_100mhz.sh"
