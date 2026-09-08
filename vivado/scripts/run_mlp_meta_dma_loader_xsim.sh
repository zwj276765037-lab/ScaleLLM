#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.."&&pwd)";BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}";SIM=hap_mlp_meta_dma_loader_sim;WORK="$ROOT/xsim_work/$SIM";rm -rf "$WORK" "$ROOT/xsim.dir/$SIM";mkdir -p "$WORK/work";cd "$ROOT"
"$BIN/xvlog" -sv --work "work=$WORK/work" rtl/attention/hap_axi256_dma.sv rtl/integration/hap_mlp_meta_dma_loader.sv tb/hap_mlp_meta_dma_loader_tb.sv
"$BIN/xelab" -L "work=$WORK/work" work.hap_mlp_meta_dma_loader_tb -s "$SIM"
"$BIN/xsim" "$SIM" -runall --log "$WORK/xsim.log" 2>&1|tee "$WORK/console.log"
! grep -q '^FAIL' "$WORK/console.log";grep -Fq 'PASS hap_mlp_meta_dma_loader' "$WORK/console.log"
