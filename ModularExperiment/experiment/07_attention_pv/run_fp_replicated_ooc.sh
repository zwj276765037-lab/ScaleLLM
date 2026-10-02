#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 1 && ( "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s fp16|fp32\n' "$0" >&2
    exit 2
}
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
variant="$1"
if [[ "$variant" == fp16 ]]; then
    top=m9_fp16_pv_x19
    copies=19
else
    top=m9_fp32_pv_x21
    copies=21
fi
export HAP_OOC_MODULE=07_attention_pv HAP_OOC_VARIANT="$variant"
export HAP_OOC_NAME="${variant}_pv_operator_only_x${copies}_buffered_100mhz"
export HAP_OOC_TOP="$top"
export HAP_OOC_SOURCES_FILE="$ROOT/ModularExperiment/experiment/07_attention_pv/vivado/fp.sources"
export HAP_OOC_PRE_SYNTH_TCL="$ROOT/ModularExperiment/experiment/07_attention_pv/vivado/create_fp_ip.tcl"
exec "$ROOT/ModularExperiment/tools/scripts/run_ooc_100mhz.sh"
