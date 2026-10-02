#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 1 && ( "$1" == sc || "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s sc|fp16|fp32\n' "$0" >&2
    exit 2
}
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/10_mlp_silu_multiply"
variant="$1"
case "$variant" in
    sc) top=m10_sc_silu_boundary_x2 ;;
    fp16) top=m10_fp16_silu_boundary_x2 ;;
    fp32) top=m10_fp32_silu_boundary_x2 ;;
esac
export HAP_OOC_MODULE=10_mlp_silu_multiply
export HAP_OOC_VARIANT="$variant"
export HAP_OOC_NAME="${variant}_gate_up_to_silu_boundary_x2_ooc_100mhz"
export HAP_OOC_TOP="$top"
if [[ "$variant" == sc ]]; then
    export HAP_OOC_SOURCES_FILE="$MODULE/vivado/boundary_sc.sources"
    unset HAP_OOC_PRE_SYNTH_TCL || true
else
    export HAP_OOC_SOURCES_FILE="$MODULE/vivado/boundary_fp.sources"
    export HAP_OOC_PRE_SYNTH_TCL="$MODULE/vivado/create_boundary_all_fp_ip.tcl"
fi
exec "$ROOT/ModularExperiment/tools/scripts/run_ooc_100mhz.sh"
