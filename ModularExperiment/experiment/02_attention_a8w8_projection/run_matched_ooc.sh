#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 1 && ( "$1" == sc || "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s sc|fp16|fp32\n' "$0" >&2
    exit 2
}

ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/02_attention_a8w8_projection"
variant="$1"
case "$variant" in
    sc) top=m4_scalecode_tile ;;
    fp16) top=m4_fp16_tile ;;
    fp32) top=m4_fp32_tile ;;
esac

export HAP_OOC_MODULE=02_attention_a8w8_projection
export HAP_OOC_VARIANT="$variant"
export HAP_OOC_NAME="${variant}_matched_8x16x128_tile_boundary_inclusive_100mhz"
export HAP_OOC_TOP="$top"
if [[ "$variant" == sc ]]; then
    export HAP_OOC_SOURCES_FILE="$MODULE/vivado/sc.sources"
    unset HAP_OOC_PRE_SYNTH_TCL || true
else
    export HAP_OOC_SOURCES_FILE="$MODULE/vivado/fp.sources"
    export HAP_OOC_PRE_SYNTH_TCL="$ROOT/ModularExperiment/experiment/00_scale_apply_microkernel/vivado/create_fp_ip.tcl"
fi
exec "$ROOT/ModularExperiment/tools/scripts/run_ooc_100mhz.sh"
