#!/usr/bin/env bash
set -euo pipefail

experiment_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "$experiment_dir/../.." && pwd)"
hap_root="$(cd "$project_root/../HAP_new" && pwd)"
artifact_root="$experiment_dir/artifacts/fixed_current"
mkdir -p "$artifact_root/xsim" "$artifact_root/ooc" "$artifact_root/build"

run_xsim() {
    local name="$1"
    local script="$2"
    bash "$hap_root/vivado/scripts/$script" 2>&1 | tee "$artifact_root/xsim/$name.console.log"
    cp "$hap_root/xsim_work/${name}_sim/xsim.log" "$artifact_root/xsim/$name.xsim.log"
}

run_ooc() {
    local name="$1"
    local script="$2"
    local report_dir="$artifact_root/ooc/$name"
    local build_dir="$artifact_root/build/$name"
    rm -rf "$report_dir" "$build_dir"
    mkdir -p "$report_dir" "$build_dir"
    HAP_REPORT_DIR="$report_dir" HAP_BUILD_DIR="$build_dir" \
        bash "$hap_root/vivado/scripts/$script" 2>&1 | tee "$artifact_root/ooc/$name.console.log"
}

run_xsim hap_hadamard32_norm_stream run_hadamard32_norm_xsim.sh
run_xsim hap_robust_a8_quantizer run_robust_a8_xsim.sh
run_xsim hap_attention_frontend_8row run_attention_frontend_8row_xsim.sh

run_ooc hadamard_only run_hadamard32_norm_ooc.sh
run_ooc robust_a8_only run_robust_a8_ooc.sh
run_ooc hadamard_robust_a8 run_attention_frontend_8row_ooc.sh

echo "PASS: M1 fixed-current correctness and routed OOC gates completed."

