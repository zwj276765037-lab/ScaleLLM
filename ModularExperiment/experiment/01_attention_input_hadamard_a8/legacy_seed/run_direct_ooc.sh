#!/usr/bin/env bash
set -euo pipefail
experiment_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
vivado="${VIVADO_BIN:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
report_dir="$experiment_dir/artifacts/direct_a8/ooc"
build_dir="$experiment_dir/artifacts/direct_a8/build"
rm -rf "$report_dir" "$build_dir"
mkdir -p "$report_dir" "$build_dir"
M1_REPORT_DIR="$report_dir" M1_BUILD_DIR="$build_dir" \
    "$vivado" -mode batch -notrace -source "$experiment_dir/ooc_direct_a8.tcl" \
    2>&1 | tee "$experiment_dir/artifacts/direct_a8/vivado.console.log"

