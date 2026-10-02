#!/usr/bin/env bash
set -euo pipefail
e="$(cd "$(dirname "${BASH_SOURCE[0]}")"&&pwd)"
vivado="${VIVADO_BIN:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
mkdir -p "$e/artifacts/fp_ip_xsim"
python3 "$e/generate_vectors.py"
for spec in '2 fp16' '3 fp32'; do
 read -r id name <<<"$spec"
 M3_CASE_ID="$id" M3_CASE_NAME="$name" \
  "$vivado" -mode batch -notrace -source "$e/run_fp_ip_xsim.tcl" \
  2>&1 | tee "$e/artifacts/fp_ip_xsim/$name.console.log"
 grep -Fq 'PASS: M3 matched' "$e/artifacts/fp_ip_xsim/$name.console.log"
 ! grep -q '^FAIL:' "$e/artifacts/fp_ip_xsim/$name.console.log"
done
echo 'PASS: M3 FP16/FP32 generated-IP XSim cases completed.'

