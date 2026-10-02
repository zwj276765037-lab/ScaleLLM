#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO_ROOT="${VIVADO_ROOT:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado}"
STAMP="${HAP_RUN_STAMP:-$(date +%Y%m%d_%H%M%S)}"
SIM="hap_mlp_v5_shift20_recovery_sim"
OUT="$ROOT/vivado/reports/mlp_v5_shift20_recovery_$STAMP"
WORK="$ROOT/xsim_work/$SIM"

mkdir -p "$OUT"
rm -rf "$WORK" "$ROOT/xsim.dir/$SIM"
mkdir -p "$WORK"
cd "$ROOT"

SOURCES=(
    rtl/mlp/hap_a8w4_pack2_dsp.sv
    rtl/mlp/hap_a8w4_group32_pack2_s17.sv
    rtl/mlp/hap_a8w4_scalecode_recover2_lut.sv
    rtl/mlp/hap_a8w4_group32_lane2_s37.sv
    rtl/mlp/hap_a8w4_slice8x12_group_s37.sv
    rtl/mlp/hap_mlp_tile_accum_s37.sv
    rtl/mlp/hap_mlp_down_group_major_accum_s46.sv
    rtl/mlp/hap_mlp_shared_dual_slice16x12_s44_s46.sv
    tb/hap_mlp_v5_shift20_recovery_tb.sv
)

printf '%s\n' "${SOURCES[@]}" >"$OUT/INPUT_FILES"
sha256sum "${SOURCES[@]}" >"$OUT/INPUT_SHA256SUMS"
"$VIVADO_ROOT/bin/xvlog" -sv "${SOURCES[@]}" 2>&1 | tee "$OUT/xvlog.console.log"
"$VIVADO_ROOT/bin/xelab" -L unisims_ver hap_mlp_v5_shift20_recovery_tb \
    -s "$SIM" 2>&1 | tee "$OUT/xelab.console.log"
"$VIVADO_ROOT/bin/xsim" "$SIM" -runall 2>&1 | tee "$OUT/xsim.console.log"
grep -Fq \
    "PASS: MLP_V5_SHIFT20 raw_s24=56400 guard_s37=7219200 groups=2 zp=0 guard_overflow=0 accumulator_overflow=0" \
    "$OUT/xsim.console.log"
printf 'status=PASS\nformat_id=0x48384603\nexpected_raw_s24=56400\nguard_overflow=0\naccumulator_overflow=0\n' \
    >"$OUT/summary.txt"
sha256sum "$OUT/INPUT_FILES" "$OUT/INPUT_SHA256SUMS" \
    "$OUT/xvlog.console.log" "$OUT/xelab.console.log" \
    "$OUT/xsim.console.log" "$OUT/summary.txt" >"$OUT/OUTPUT_SHA256SUMS"
printf '%s\n' "$OUT"
