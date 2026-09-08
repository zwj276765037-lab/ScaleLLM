#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
PYTHON="${PYTHON:-python3}"
SIM=hap_softmax_row_128_sim
WORK="$ROOT/xsim_work/$SIM"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/softmax_row_128_xsim_$STAMP}"
rm -rf "$WORK" "$ROOT/xsim.dir/$SIM"
mkdir -p "$WORK/work" "$REPORT_DIR"
cd "$ROOT"
status=1
archive() {
  set +e
  for f in xvlog.log xvlog.pb xelab.log xelab.pb xsim.jou; do
    [[ -f "$ROOT/$f" ]] && cp -p "$ROOT/$f" "$REPORT_DIR/$f"
  done
  [[ -f "$WORK/xsim.log" ]] && cp -p "$WORK/xsim.log" "$REPORT_DIR/xsim.log"
  printf 'exit_status=%s\ntool=%s\ntop=%s\n' "$status" \
    "$("$BIN/xsim" -version 2>/dev/null | head -1)" \
    hap_softmax_row_128_tb > "$REPORT_DIR/summary.txt"
  (cd "$REPORT_DIR" && sha256sum ./* > SHA256SUMS)
}
trap archive EXIT

# Regenerate all golden inputs from the local FixBit model before simulation.
"$PYTHON" model/generate_softmax_exp_artifact.py
"$PYTHON" model/generate_softmax_row_vectors.py
cp -p data/softmax_exp_u17/exp_lut_u17.mem data/softmax_exp_u17.mem
cp -p tb/hap_softmax_row_128_tb.sv "$WORK/"
mapfile -t sources < <(sed -e '/^[[:space:]]*#/d' -e '/^[[:space:]]*$/d' \
  vivado/manifests/softmax_row_128_sources.list | grep -E '\.(sv|v)$')
sha256sum vivado/manifests/softmax_row_128_sources.list "${sources[@]}" \
  "$WORK/hap_softmax_row_128_tb.sv" data/softmax_row_128/*.mem \
  vivado/scripts/run_softmax_row_128_xsim.sh > "$REPORT_DIR/INPUT_SHA256SUMS"
"$BIN/xvlog" -sv --work "work=$WORK/work" \
  "${sources[@]}" "$WORK/hap_softmax_row_128_tb.sv"
"$BIN/xelab" -L "work=$WORK/work" work.hap_softmax_row_128_tb -s "$SIM"
"$BIN/xsim" "$SIM" -runall --log "$WORK/xsim.log"
! grep -q '^FAIL:' "$WORK/xsim.log"
grep -Fq 'PASS: Softmax row128 matched FixBit v2 golden and rejected all-masked row.' \
  "$WORK/xsim.log"
status=0
printf '%s\n' "$REPORT_DIR"
