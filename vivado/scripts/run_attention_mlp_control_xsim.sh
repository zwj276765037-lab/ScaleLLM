#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.."&&pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
run_one(){
 local name="$1";shift;local work="$ROOT/xsim_work/$name"
 rm -rf "$work" "$ROOT/xsim.dir/$name";mkdir -p "$work/work";cd "$ROOT"
 "$BIN/xvlog" -sv --work "work=$work/work" "$@"
 "$BIN/xelab" -L "work=$work/work" "work.${name%_sim}_tb" -s "$name"
 "$BIN/xsim" "$name" -runall --log "$work/xsim.log" 2>&1|tee "$work/console.log"
 if grep -q '^FAIL' "$work/console.log";then
  echo "functional FAIL marker in $work/console.log" >&2
  return 1
 fi
 grep -q '^PASS' "$work/console.log"
}
run_one hap_attention_mlp_axil_router_sim \
 rtl/integration/hap_attention_mlp_axil_router.sv tb/hap_attention_mlp_axil_router_tb.sv
run_one hap_mlp_metadata_scheduler_sim \
 rtl/integration/hap_mlp_metadata_scheduler.sv tb/hap_mlp_metadata_scheduler_tb.sv
