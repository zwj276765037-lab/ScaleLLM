#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
VIVADO_ROOT="${VIVADO_ROOT:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado}"
"$VIVADO_ROOT/bin/xvlog" -sv rtl/mlp/hap_mlp_silu_mul.sv tb/hap_mlp_silu_mul_tb.sv
"$VIVADO_ROOT/bin/xelab" hap_mlp_silu_mul_tb -s hap_mlp_silu_mul_sim
"$VIVADO_ROOT/bin/xsim" hap_mlp_silu_mul_sim -runall

