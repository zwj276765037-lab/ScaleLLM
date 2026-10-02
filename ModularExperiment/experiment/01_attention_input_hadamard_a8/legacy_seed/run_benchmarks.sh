#!/usr/bin/env bash
set -euo pipefail

experiment_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "$experiment_dir/../.." && pwd)"
hap_root="$(cd "$project_root/../HAP_new" && pwd)"
vivado_bin_dir="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
work_root="$experiment_dir/artifacts/benchmark_xsim"
rm -rf "$work_root"
mkdir -p "$work_root"

cd "$experiment_dir"
python3 generate_vectors.py

sources=(
    "$hap_root/rtl/hap_fixbit_v2_pkg.sv"
    "$hap_root/rtl/hap_hadamard32_norm_stream.sv"
    "$hap_root/rtl/hap_u16_div_u8_seq.sv"
    "$hap_root/rtl/hap_robust_a8_quantizer.sv"
    "$hap_root/rtl/hap_activation_cache_8row.sv"
    "$hap_root/rtl/hap_attention_frontend_8row.sv"
    "$experiment_dir/rtl/hap_attention_frontend_direct_a8_8row.sv"
    "$experiment_dir/tb/m1_frontend_benchmark_tb.sv"
)

run_case() {
    local case_name="$1"
    local top="$2"
    local sim="m1_${case_name}_sim"
    local work="$work_root/$case_name/work"
    mkdir -p "$work"
    "$vivado_bin_dir/xvlog" -sv --work "work=$work" "${sources[@]}"
    "$vivado_bin_dir/xelab" -L "work=$work" "work.$top" \
        -s "$sim" --debug typical
    "$vivado_bin_dir/xsim" "$sim" -runall \
        --log "$work_root/$case_name/xsim.log"
    grep -Fq 'PASS: M1 frontend intrinsic benchmark' \
        "$work_root/$case_name/xsim.log"
    if grep -q '^FAIL:' "$work_root/$case_name/xsim.log"; then
        return 1
    fi
}

run_case proposed m1_frontend_proposed_tb
run_case direct m1_frontend_direct_tb
echo "PASS: M1 proposed/direct intrinsic benchmarks completed."

