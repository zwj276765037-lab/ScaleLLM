#!/usr/bin/env bash
set -euo pipefail
e="$(cd "$(dirname "${BASH_SOURCE[0]}")"&&pwd)"
v="${VIVADO_BIN:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
mkdir -p "$e/artifacts/ooc_tm" "$e/artifacts/build_tm"
for s in '1 fp16 m7_fp16_qk_row_tm' '2 fp32 m7_fp32_qk_row_tm';do
    read -r i n t<<<"$s"
    r="$e/artifacts/ooc_tm/$n"
    b="$e/artifacts/build_tm/$n"
    rm -rf "$r" "$b"
    mkdir -p "$r" "$b"
    M7_CASE_ID=$i M7_CASE_NAME=$n M7_TOP=$t M7_REPORT_DIR=$r \
        M7_BUILD_DIR=$b "$v" -mode batch -notrace -source "$e/tm_ooc.tcl" \
        >"$e/artifacts/ooc_tm/$n.console.log" 2>&1
done
