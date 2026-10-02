#!/usr/bin/env bash
set -euo pipefail
e="$(cd "$(dirname "${BASH_SOURCE[0]}")"&&pwd)"
v="${VIVADO_BIN:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
mkdir -p "$e/artifacts/ooc" "$e/artifacts/build"
for s in '0 quantizer2 m6_kv12_quantizer2' '1 cache_fp16 m6_kv16_fp16_cache' '2 cache_fp32 m6_kv16_fp32_cache';do
  read -r i n t<<<"$s"
  r="$e/artifacts/ooc/$n";b="$e/artifacts/build/$n";rm -rf "$r" "$b";mkdir -p "$r" "$b"
  M6_CASE_ID=$i M6_CASE_NAME=$n M6_TOP=$t M6_REPORT_DIR=$r M6_BUILD_DIR=$b \
    "$v" -mode batch -notrace -source "$e/ooc.tcl" >"$e/artifacts/ooc/$n.console.log" 2>&1
done
