#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
shape="${1:-single}"
[[ "$shape" == single || "$shape" == x2 ]] || {
    printf 'usage: %s [single|x2]\n' "$0" >&2
    exit 2
}
export HAP_OOC_MODULE=10_mlp_silu_multiply
export HAP_OOC_VARIANT=sc
export HAP_OOC_NAME="sc_mlp_silu_mul_${shape}_100mhz"
if [[ "$shape" == single ]]; then
    export HAP_OOC_TOP=m10_sc_silu_mul_single
else
    export HAP_OOC_TOP=m10_sc_silu_mul_x2
fi
export HAP_OOC_SOURCES_FILE="$ROOT/ModularExperiment/experiment/10_mlp_silu_multiply/vivado/sc_mlp_silu_mul.sources"
exec "$ROOT/ModularExperiment/tools/scripts/run_ooc_100mhz.sh"
