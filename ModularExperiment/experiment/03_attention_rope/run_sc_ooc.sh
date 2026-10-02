#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
export HAP_OOC_MODULE=03_attention_rope HAP_OOC_VARIANT=sc
export HAP_OOC_NAME=sc_rope_pair_100mhz HAP_OOC_TOP=hap_rope_pair_s24
export HAP_OOC_SOURCES_FILE="$ROOT/ModularExperiment/experiment/03_attention_rope/vivado/sc.sources"
exec "$ROOT/ModularExperiment/tools/scripts/run_ooc_100mhz.sh"
