#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 1 && ( "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s fp16|fp32\n' "$0" >&2
    exit 2
}
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
variant="$1"
export HAP_OOC_MODULE=06_attention_softmax HAP_OOC_VARIANT="$variant"
export HAP_OOC_NAME="${variant}_softmax_operator_only_single_core_100mhz"
export HAP_OOC_TOP="m8_${variant}_softmax"
export HAP_OOC_SOURCES_FILE="$ROOT/ModularExperiment/experiment/06_attention_softmax/vivado/fp.sources"
export HAP_OOC_PRE_SYNTH_TCL="$ROOT/ModularExperiment/experiment/06_attention_softmax/vivado/create_fp_ip.tcl"
exec "$ROOT/ModularExperiment/tools/scripts/run_ooc_100mhz.sh"
