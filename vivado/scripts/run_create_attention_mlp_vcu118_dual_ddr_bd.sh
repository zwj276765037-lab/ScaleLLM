#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
PROJECT_DIR="${HAP_PROJECT_DIR:-$ROOT/vivado/project/attention_mlp_vcu118_dual_ddr}"
mkdir -p "$PROJECT_DIR"
cd "$ROOT"
HAP_PROJECT_DIR="$PROJECT_DIR" "$VIVADO" -mode batch -notrace \
    -source vivado/scripts/create_attention_mlp_vcu118_dual_ddr_bd.tcl \
    -log "$PROJECT_DIR/create.log" -journal "$PROJECT_DIR/create.jou"
printf '%s\n' "$PROJECT_DIR"
