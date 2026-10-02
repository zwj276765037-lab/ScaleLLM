#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 1 && ( "$1" == sc || "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s sc|fp16|fp32\n' "$0" >&2
    exit 2
}
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/03_attention_rope"
variant="$1"
case "$variant" in
    sc) top=m03_sc_projection_rope_pair ;;
    fp16) top=m03_fp16_projection_rope_pair ;;
    fp32) top=m03_fp32_projection_rope_pair ;;
esac
export HAP_OOC_MODULE=03_attention_rope
export HAP_OOC_VARIANT="$variant"
export HAP_OOC_NAME="${variant}_projection_tail_rope_boundary_inclusive_100mhz"
export HAP_OOC_TOP="$top"
if [[ "$variant" == sc ]]; then
    export HAP_OOC_SOURCES_FILE="$MODULE/vivado/boundary_sc.sources"
    unset HAP_OOC_PRE_SYNTH_TCL || true
else
    export HAP_OOC_SOURCES_FILE="$MODULE/vivado/boundary_fp.sources"
    export HAP_OOC_PRE_SYNTH_TCL="$MODULE/vivado/create_boundary_fp_ip.tcl"
fi
exec "$ROOT/ModularExperiment/tools/scripts/run_ooc_100mhz.sh"
