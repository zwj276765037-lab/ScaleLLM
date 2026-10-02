#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
export HAP_OOC_MODULE=00_scale_apply_microkernel HAP_OOC_VARIANT=sc
export HAP_OOC_NAME=sc_scale_apply_a8w8_100mhz
export HAP_OOC_TOP=hap_a8w8_group32_lane_s42
export HAP_OOC_SOURCES_FILE="$ROOT/ModularExperiment/experiment/00_scale_apply_microkernel/vivado/sc_a8w8.sources"
exec "$ROOT/ModularExperiment/tools/scripts/run_ooc_100mhz.sh"
