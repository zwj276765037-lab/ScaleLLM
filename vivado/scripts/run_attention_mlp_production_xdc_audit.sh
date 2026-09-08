#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_DCP="${HAP_DCP:?HAP_DCP must name the audited production post_opt.dcp}"
export HAP_XDC_AUDIT_DIR="${HAP_XDC_AUDIT_DIR:-$ROOT/vivado/reports/production_xdc_audit_$STAMP}"
export HAP_CLOCK_XDC="${HAP_CLOCK_XDC:-$ROOT/vivado/constraints/attention_mlp_production_ooc_clocks.xdc}"
export HAP_CORE_PERIOD_NS="${HAP_CORE_PERIOD_NS:-6.666}"
[[ -s "$HAP_CLOCK_XDC" ]] || {
  printf 'missing or empty production clock XDC: %s\n' "$HAP_CLOCK_XDC" >&2
  exit 2
}
mkdir -p "$HAP_XDC_AUDIT_DIR"
cd "$ROOT"
"$VIVADO" -mode batch -notrace \
  -source vivado/scripts/audit_attention_mlp_production_xdc.tcl \
  -log "$HAP_XDC_AUDIT_DIR/vivado.log" \
  -journal "$HAP_XDC_AUDIT_DIR/vivado.jou"
grep -Fq 'status=XDC_AUDIT_PASS' "$HAP_XDC_AUDIT_DIR/summary.txt"
sha256sum "$HAP_DCP" \
  "$HAP_CLOCK_XDC" \
  vivado/scripts/check_attention_mlp_production_io_selectors.tcl \
  vivado/scripts/audit_attention_mlp_production_xdc.tcl \
  vivado/scripts/run_attention_mlp_production_xdc_audit.sh \
  "$HAP_XDC_AUDIT_DIR/summary.txt" > "$HAP_XDC_AUDIT_DIR/SHA256SUMS"
printf '%s\n' "$HAP_XDC_AUDIT_DIR"
