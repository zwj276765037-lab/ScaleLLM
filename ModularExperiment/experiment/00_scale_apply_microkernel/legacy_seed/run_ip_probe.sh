#!/usr/bin/env bash
set -euo pipefail
experiment_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
vivado="${VIVADO_BIN:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
mkdir -p "$experiment_dir/artifacts"
"$vivado" -mode batch -notrace -source "$experiment_dir/probe_fp_ip.tcl" \
    2>&1 | tee "$experiment_dir/artifacts/ip_probe.log"

