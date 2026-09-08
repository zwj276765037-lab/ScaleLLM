#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.."&&pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
export HAP_DCP="${HAP_DCP:-$ROOT/vivado/reports/production_core_20260811_231932/post_opt.dcp}"
export HAP_AUDIT_DIR="${HAP_AUDIT_DIR:-$ROOT/vivado/reports/production_core_20260811_231932/dcp_audit}"
export HAP_EXPECT_DSP="${HAP_EXPECT_DSP:-6492}"
export HAP_EXPECT_URAM="${HAP_EXPECT_URAM:-752}"
export HAP_EXPECT_RAMB36="${HAP_EXPECT_RAMB36:-659}"
export HAP_EXPECT_RAMB18="${HAP_EXPECT_RAMB18:-24}"
export HAP_EXPECT_KERNELS="${HAP_EXPECT_KERNELS:-2}"
export HAP_EXPECT_KERNEL_DSP="${HAP_EXPECT_KERNEL_DSP:-4096}"
export HAP_EXPECT_LUT="${HAP_EXPECT_LUT:-883202}"
export HAP_EXPECT_FF="${HAP_EXPECT_FF:-974417}"
mkdir -p "$HAP_AUDIT_DIR";cd "$ROOT"
"$VIVADO" -mode batch -notrace -source vivado/scripts/audit_attention_mlp_production_dcp.tcl \
 -log "$HAP_AUDIT_DIR/vivado.log" -journal "$HAP_AUDIT_DIR/vivado.jou"
grep -Fq 'status=DCP_EXACT_AUDIT_PASS' "$HAP_AUDIT_DIR/audit.txt"
