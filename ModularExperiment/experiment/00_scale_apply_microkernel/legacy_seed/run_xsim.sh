#!/usr/bin/env bash
set -euo pipefail
e="$(cd "$(dirname "${BASH_SOURCE[0]}")"&&pwd)"
root="$(cd "$e/../.."&&pwd)"
hap="$(cd "$root/../HAP_new"&&pwd)"
bin="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
out="$e/artifacts/xsim"
rm -rf "$out"
mkdir -p "$out"
cd "$e"
python3 generate_vectors.py
src=(
 "$hap/rtl/hap_a8w8_group32_lane_s42.sv"
 "$e/rtl/m3_precenter_mac_group32.sv"
 "$e/rtl/m3_s42_fifo.sv"
 "$e/rtl/m3_mac_only_lane.sv"
 "$e/tb/m3_fp_sim_models.sv"
 "$e/rtl/m3_fp_scale_lanes.sv"
 "$e/tb/m3_lane_tb.sv"
)
for spec in 'mac_only m3_mac_only_tb' 'scalecode m3_scalecode_tb'; do
 read -r name top <<<"$spec"
 lib="$out/$name/work"
 mkdir -p "$lib"
 "$bin/xvlog" -sv --work "work=$lib" "${src[@]}"
 "$bin/xelab" -L "work=$lib" "work.$top" -s "m3_${name}_sim" --debug typical
 "$bin/xsim" "m3_${name}_sim" -runall --log "$out/$name/xsim.log"
 grep -Fq 'PASS: M3 matched' "$out/$name/xsim.log"
 ! grep -q '^FAIL:' "$out/$name/xsim.log"
done
echo 'PASS: M3 MAC-only/ScaleCode XSim cases completed.'
