#!/usr/bin/env bash
set -euo pipefail
e="$(cd "$(dirname "${BASH_SOURCE[0]}")"&&pwd)";x="$e/artifacts/xsim"
xb="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
mkdir -p "$x"
for c in fp16 fp32;do
  w="$e/artifacts/work_cache_$c";rm -rf "$w";mkdir -p "$w"
  d=();[[ "$c" == fp32 ]]&&d=(-d CASE_FP32)
  "$xb/xvlog" --work work="$w" -sv "${d[@]}" "$e/rtl/m6_kv16_cache.sv" "$e/tb/m6_kv16_cache_tb.sv" >"$x/cache_$c.xvlog.log" 2>&1
  "$xb/xelab" -L work="$w" work.m6_kv16_cache_tb -s "m6_cache_$c" >"$x/cache_$c.xelab.log" 2>&1
  "$xb/xsim" "m6_cache_$c" -runall -log "$x/cache_$c.log" >"$x/cache_$c.console.log" 2>&1
done
