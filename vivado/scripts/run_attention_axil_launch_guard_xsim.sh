#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.."&&pwd)";BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}";SIM=hap_attention_axil_launch_guard_sim;WORK="$ROOT/xsim_work/$SIM";rm -rf "$WORK" "$ROOT/xsim.dir/$SIM";mkdir -p "$WORK/work";cd "$ROOT"
"$BIN/xvlog" -sv --work "work=$WORK/work" rtl/attention/hap_attention_axil_control.sv tb/hap_attention_axil_launch_guard_tb.sv
"$BIN/xelab" -L "work=$WORK/work" work.hap_attention_axil_launch_guard_tb -s "$SIM"
"$BIN/xsim" "$SIM" -runall --log "$WORK/xsim.log" 2>&1|tee "$WORK/console.log";! grep -q '^FAIL' "$WORK/console.log";grep -Fq 'PASS hap_attention_axil_launch_guard' "$WORK/console.log"
