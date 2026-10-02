#!/usr/bin/env bash
set -euo pipefail
experiment_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "$experiment_dir/../.." && pwd)"
hap_root="$(cd "$project_root/../HAP_new" && pwd)"
bin="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
out="$experiment_dir/artifacts/single_xsim"
rm -rf "$out"
mkdir -p "$out"
cd "$experiment_dir"
ln -sfn "$hap_root/data" hap_data
run_one() {
    local case_name="$1" top="$2"
    local lib="$out/$case_name/work" sim="m1_${case_name}_sim"
    mkdir -p "$lib"
    "$bin/xvlog" -sv --work "work=$lib" \
        "$hap_root/rtl/hap_fixbit_v2_pkg.sv" \
        "$hap_root/rtl/hap_hadamard32_norm_stream.sv" \
        "$hap_root/rtl/hap_u16_div_u8_seq.sv" \
        "$hap_root/rtl/hap_robust_a8_quantizer.sv" \
        "$experiment_dir/tb/m1_single_module_benchmark_tb.sv"
    "$bin/xelab" -L "work=$lib" "work.$top" -s "$sim" --debug typical
    "$bin/xsim" "$sim" -runall --log "$out/$case_name/xsim.log"
    grep -Fq 'PASS: M1' "$out/$case_name/xsim.log"
    if grep -q '^FAIL:' "$out/$case_name/xsim.log"; then return 1; fi
}
run_one hadamard m1_hadamard_benchmark_tb
run_one robust_a8 m1_robust_a8_benchmark_tb
echo "PASS: M1 single-module intrinsic benchmarks completed."

