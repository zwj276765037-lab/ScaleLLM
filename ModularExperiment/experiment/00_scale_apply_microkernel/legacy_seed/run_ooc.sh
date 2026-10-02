#!/usr/bin/env bash
set -euo pipefail
e="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
vivado="${VIVADO_BIN:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
mkdir -p "$e/artifacts/ooc" "$e/artifacts/build"
for spec in \
  'mac_only m3_mac_only_lane' \
  'scalecode hap_a8w8_group32_lane_s42' \
  'fp16 m3_fp16_scale_lane' \
  'fp32 m3_fp32_scale_lane'; do
  read -r name top <<<"$spec"
  report="$e/artifacts/ooc/$name"
  build="$e/artifacts/build/$name"
  (
    rm -rf "$report" "$build"
    mkdir -p "$report" "$build"
    M3_CASE_NAME="$name" M3_TOP="$top" M3_REPORT_DIR="$report" \
      M3_BUILD_DIR="$build" "$vivado" -mode batch -notrace \
      -source "$e/ooc_lane.tcl" \
      > "$e/artifacts/ooc/$name.console.log" 2>&1
  ) &
done
wait
echo 'PASS: M3 four routed OOC cases completed.'
