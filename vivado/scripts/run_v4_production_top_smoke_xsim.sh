#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
SIM=hap_v4_production_top_smoke_sim
WORK="$ROOT/xsim_work/$SIM"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/v4_production_top_smoke_xsim_$STAMP}"
MANIFEST="$ROOT/vivado/manifests/attention_mlp_production_v4_sources.list"
mkdir -p "$REPORT_DIR"
rm -rf "$WORK" "$ROOT/xsim.dir/$SIM"
mkdir -p "$WORK/work"
cd "$ROOT"
status=1

expand_manifest() {
  local manifest="$1" line path
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%%#*}"
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    [[ -z "$line" ]] && continue
    path="$ROOT/$line"
    [[ -f "$path" ]] || { printf 'Missing source %s\n' "$path" >&2; return 1; }
    if [[ "$path" == *.list ]]; then
      expand_manifest "$path"
    else
      printf '%s\n' "$path"
    fi
  done < "$manifest"
}

archive() {
  set +e
  for f in xvlog.log xvlog.pb xelab.log xelab.pb xsim.jou; do
    [[ -f "$ROOT/$f" ]] && cp -p "$ROOT/$f" "$REPORT_DIR/$f"
  done
  [[ -f "$WORK/xsim.log" ]] && cp -p "$WORK/xsim.log" "$REPORT_DIR/xsim.log"
  cp -p "$MANIFEST" \
    "$ROOT/tb/hap_v4_production_top_smoke_tb.sv" \
    "$ROOT/vivado/scripts/run_v4_production_top_smoke_xsim.sh" "$REPORT_DIR/"
  printf 'exit_status=%s\ntool=%s\ntop=%s\nmanifest=%s\n' "$status" \
    "$("$BIN/xsim" -version 2>/dev/null | head -1)" \
    hap_v4_production_top_smoke_tb \
    vivado/manifests/attention_mlp_production_v4_sources.list \
    > "$REPORT_DIR/summary.txt"
  (cd "$REPORT_DIR" && sha256sum ./* > SHA256SUMS)
}
trap archive EXIT

expand_manifest "$MANIFEST" > "$WORK/expanded_sources.list"
mapfile -t all_sources < "$WORK/expanded_sources.list"
sources=()
for path in "${all_sources[@]}"; do
  case "$path" in
    *.sv|*.v) sources+=("$path");;
  esac
done
cp -p "$WORK/expanded_sources.list" "$REPORT_DIR/expanded_sources.list"
sha256sum "$MANIFEST" "${all_sources[@]}" \
  "$ROOT/tb/hap_v4_production_top_smoke_tb.sv" \
  > "$REPORT_DIR/INPUT_SHA256SUMS"

"$BIN/xvlog" --sv -L xpm --work work="$WORK/work" \
  "${sources[@]}" tb/hap_v4_production_top_smoke_tb.sv
GLBL_V="${GLBL_V:-$BIN/../ids_lite/ISE/verilog/src/glbl.v}"
[[ -f "$GLBL_V" ]] || GLBL_V="$BIN/../data/verilog/src/glbl.v"
"$BIN/xvlog" --work work="$WORK/work" "$GLBL_V"
"$BIN/xelab" -L xpm -L unisims_ver -L work="$WORK/work" \
  work.hap_v4_production_top_smoke_tb work.glbl -s "$SIM"
"$BIN/xsim" "$SIM" -runall --log "$WORK/xsim.log"
grep -Eq 'PASS hap_v4_production_top_smoke checks=[0-9]+ soft_clear=[0-9]+' \
  "$WORK/xsim.log"
status=0
printf '%s\n' "$REPORT_DIR"
