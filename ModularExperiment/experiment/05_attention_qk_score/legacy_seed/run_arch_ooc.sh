#!/usr/bin/env bash
set -euo pipefail
e="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
v="${VIVADO_BIN:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
for c in "0 fixed" "1 fp16" "2 fp32"; do
    read -r id n <<<"$c"
    final_rd="$e/artifacts/ooc_arch/$n"
    rd="$e/artifacts/ooc_arch/.${n}.tmp.$$"
    bd="$e/artifacts/build_arch/$n"
    rm -rf "$rd"
    mkdir -p "$rd"
    M7_CASE_ID="$id" M7_CASE_NAME="$n" M7_REPORT_DIR="$rd" \
    M7_BUILD_DIR="$bd" "$v" -mode batch -notrace \
        -source "$e/arch_ooc.tcl" >"$rd/console.log" 2>&1
    grep 'M7_ARCH_OOC_RESULT' "$rd/console.log"
    if grep -Eq 'CRITICAL WARNING:|\[Synth 8-6858\]|\[Synth 8-6859\]' \
            "$rd/console.log"; then
        echo "M7 architecture OOC rejected: critical/multi-driver synthesis warning" >&2
        exit 1
    fi
    backup="${final_rd}_previous_$(date +%Y%m%d_%H%M%S)"
    if [[ -d "$final_rd" ]]; then
        mv "$final_rd" "$backup"
    fi
    mv "$rd" "$final_rd"
done
