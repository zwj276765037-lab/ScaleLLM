#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 2 && ( "$1" == fp16 || "$1" == fp32 ) &&
   ( "$2" == single || "$2" == x2 ) ]] || {
    printf 'usage: %s fp16|fp32 single|x2\n' "$0" >&2
    exit 2
}
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
variant="$1"
shape="$2"
if [[ "$shape" == single ]]; then
    top="m10_${variant}_silu_mul"
else
    top="m10_${variant}_silu_mul_x2"
fi
export HAP_OOC_MODULE=10_mlp_silu_multiply HAP_OOC_VARIANT="$variant"
export HAP_OOC_NAME="${variant}_silu_operator_only_${shape}_100mhz"
export HAP_OOC_TOP="$top"
export HAP_OOC_SOURCES_FILE="$ROOT/ModularExperiment/experiment/10_mlp_silu_multiply/vivado/fp.sources"
export HAP_OOC_PRE_SYNTH_TCL="$ROOT/ModularExperiment/experiment/10_mlp_silu_multiply/vivado/create_fp_ip.tcl"
exec "$ROOT/ModularExperiment/tools/scripts/run_ooc_100mhz.sh"
