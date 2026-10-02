#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
export HAP_OOC_MODULE=07_attention_pv HAP_OOC_VARIANT=sc
export HAP_OOC_NAME=sc_pv_tile16_100mhz HAP_OOC_TOP=hap_pv_tile16_s43
export HAP_OOC_SOURCES_FILE="$ROOT/ModularExperiment/experiment/07_attention_pv/vivado/sc.sources"
exec "$ROOT/ModularExperiment/tools/scripts/run_ooc_100mhz.sh"
