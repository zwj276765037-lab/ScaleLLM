#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
export HAP_OOC_MODULE=06_attention_softmax HAP_OOC_VARIANT=sc
export HAP_OOC_NAME=sc_softmax_row128_100mhz HAP_OOC_TOP=hap_softmax_row_128
export HAP_OOC_SOURCES_FILE="$ROOT/ModularExperiment/experiment/06_attention_softmax/vivado/sc.sources"
exec "$ROOT/ModularExperiment/tools/scripts/run_ooc_100mhz.sh"
