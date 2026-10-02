#!/usr/bin/env bash
set -euo pipefail
e="$(cd "$(dirname "${BASH_SOURCE[0]}")"&&pwd)"
vivado="${VIVADO_BIN:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
mkdir -p "$e/artifacts/ooc" "$e/artifacts/build"
for spec in '0 mac_only m4_mac_only_tile' '1 scalecode m4_scalecode_tile' \
            '2 fp16 m4_fp16_tile' '3 fp32 m4_fp32_tile'; do
  read -r id name top <<<"$spec"
  report="$e/artifacts/ooc/$name";build="$e/artifacts/build/$name"
  (rm -rf "$report" "$build";mkdir -p "$report" "$build"
   M4_CASE_ID="$id" M4_CASE_NAME="$name" M4_TOP="$top" \
     M4_REPORT_DIR="$report" M4_BUILD_DIR="$build" \
     "$vivado" -mode batch -notrace -source "$e/ooc_tile.tcl" \
     > "$e/artifacts/ooc/$name.console.log" 2>&1) &
done
wait
echo 'PASS: M4 four routed OOC cases completed.'
