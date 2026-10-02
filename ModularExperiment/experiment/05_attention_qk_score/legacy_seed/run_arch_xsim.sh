#!/usr/bin/env bash
set -euo pipefail
e="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
v="${VIVADO_BIN:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
mkdir -p "$e/artifacts/xsim_arch"
workloads=("q0_v8 0 8")
if [[ "${M7_ALL_WORKLOADS:-0}" == 1 ]]; then
    workloads+=("q8_v16 8 16" "q120_v128 120 128")
fi
cases=("0 fixed" "1 fp16" "2 fp32")
for w in "${workloads[@]}"; do
    read -r wn qs vk <<<"$w"
    if [[ "${M7_WORKLOAD_FILTER:-all}" != all &&
          "${M7_WORKLOAD_FILTER}" != "$wn" ]]; then
        continue
    fi
    data_dir="$e/data_arch_$wn"
    M7_QUERY_START="$qs" M7_VALID_KEYS="$vk" M7_DATA_OUT="$data_dir" \
        python3 "$e/generate_arch_vectors.py"
    for c in "${cases[@]}"; do
        read -r id n <<<"$c"
        if [[ "${M7_CASE_FILTER:-all}" != all &&
              "${M7_CASE_FILTER}" != "$n" ]]; then
            continue
        fi
        log="$e/artifacts/xsim_arch/${n}_${wn}.console.log"
        M7_CASE_ID="$id" M7_CASE_NAME="${n}_${wn}" \
        M7_QUERY_START="$qs" M7_VALID_KEYS="$vk" \
        M7_DATA_DIR="$data_dir" \
            "$v" -mode batch -notrace -source "$e/run_arch_xsim.tcl" \
            >"$log" 2>&1
        grep -Fq 'PASS: M7 architecture-level attention launch' "$log"
        if grep -Fq 'FAIL: M7 ARCH' "$log"; then
            echo "M7 architecture XSIM rejected: FAIL marker in $log" >&2
            exit 1
        fi
        grep 'M7_QK_ARCH_METRIC_JSON:' "$log"
    done
done
