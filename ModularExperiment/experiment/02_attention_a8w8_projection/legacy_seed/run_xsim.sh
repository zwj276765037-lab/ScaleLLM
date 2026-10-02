#!/usr/bin/env bash
set -euo pipefail
e="$(cd "$(dirname "${BASH_SOURCE[0]}")"&&pwd)"
vivado="${VIVADO_BIN:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
mkdir -p "$e/artifacts/xsim"
python3 "$e/generate_vectors.py"
for spec in '0 mac_only' '1 scalecode' '2 fp16' '3 fp32'; do
  read -r id name <<<"$spec"
  M4_CASE_ID="$id" M4_CASE_NAME="$name" \
    "$vivado" -mode batch -notrace -source "$e/run_xsim.tcl" \
    > "$e/artifacts/xsim/$name.console.log" 2>&1
  grep -Fq 'PASS: M4 matched tile' "$e/artifacts/xsim/$name.console.log"
  ! grep -q '^FAIL:' "$e/artifacts/xsim/$name.console.log"
done
echo 'PASS: M4 four matched XSim tile cases completed.'
