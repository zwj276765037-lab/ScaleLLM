#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.."&&pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_COMPILE_DIR="${HAP_COMPILE_DIR:-$ROOT/vivado/build/production_compile_$STAMP}"
mkdir -p "$HAP_COMPILE_DIR";cd "$ROOT"
"$VIVADO" -mode batch -notrace -source vivado/scripts/compile_attention_mlp_production_core.tcl \
 -log "$HAP_COMPILE_DIR/vivado.log" -journal "$HAP_COMPILE_DIR/vivado.jou"
grep -Fq 'status=ELABORATION_PASS' "$HAP_COMPILE_DIR/summary.txt"
printf '%s\n' "$HAP_COMPILE_DIR"
