#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_PRODUCTION_MANIFEST="${HAP_PRODUCTION_MANIFEST:-$ROOT/vivado/manifests/attention_mlp_production_v4_sources.list}"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/production_registered_ooc_$STAMP}"
export HAP_BUILD_DIR="${HAP_BUILD_DIR:-$ROOT/vivado/build/production_registered_ooc_$STAMP}"
export HAP_PLACE_DIRECTIVE="${HAP_PLACE_DIRECTIVE:-SSI_SpreadLogic_high}"
export HAP_PHYSOPT_DIRECTIVE="${HAP_PHYSOPT_DIRECTIVE:-AggressiveExplore}"
export HAP_ROUTE_DIRECTIVE="${HAP_ROUTE_DIRECTIVE:-AggressiveExplore}"
mkdir -p "$HAP_REPORT_DIR" "$HAP_BUILD_DIR"

# Capture the complete recursive production source graph plus every proxy-only
# input before Vivado starts.  This never mutates the production manifest.
declare -A seen=()
inputs=()
collect_manifest() {
  local manifest="$1" raw line path
  [[ -f "$manifest" ]] || {
    echo "Missing production manifest: $manifest" >&2
    exit 2
  }
  if [[ -z "${seen[$manifest]+x}" ]]; then
    seen["$manifest"]=1
    inputs+=("$manifest")
  fi
  while IFS= read -r raw || [[ -n "$raw" ]]; do
    line="${raw#"${raw%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    [[ -z "$line" || "${line:0:1}" == "#" ]] && continue
    path="$ROOT/$line"
    [[ -f "$path" ]] || {
      echo "Missing production source: $path" >&2
      exit 2
    }
    if [[ "$path" == *.list ]]; then
      collect_manifest "$path"
    elif [[ -z "${seen[$path]+x}" ]]; then
      seen["$path"]=1
      inputs+=("$path")
    fi
  done < "$manifest"
}
collect_manifest "$HAP_PRODUCTION_MANIFEST"

for proxy_input in \
  "$ROOT/rtl/integration/hap_attention_mlp_production_registered_ooc_harness.sv" \
  "$ROOT/vivado/constraints/attention_mlp_production_registered_ooc_150_300_300.xdc" \
  "$ROOT/vivado/scripts/route_attention_mlp_production_registered_ooc.tcl" \
  "$ROOT/vivado/scripts/run_attention_mlp_production_registered_ooc.sh"; do
  [[ -f "$proxy_input" ]] || {
    echo "Missing registered proxy input: $proxy_input" >&2
    exit 2
  }
  if [[ -z "${seen[$proxy_input]+x}" ]]; then
    seen["$proxy_input"]=1
    inputs+=("$proxy_input")
  fi
done

printf '%s\n' "${inputs[@]}" | LC_ALL=C sort -u \
  > "$HAP_REPORT_DIR/INPUT_FILES"
xargs -d '\n' sha256sum < "$HAP_REPORT_DIR/INPUT_FILES" \
  > "$HAP_REPORT_DIR/INPUT_SHA256SUMS"

cd "$ROOT" || exit 2
"$VIVADO" -mode batch -notrace \
  -source vivado/scripts/route_attention_mlp_production_registered_ooc.tcl \
  -log "$HAP_REPORT_DIR/vivado.log" \
  -journal "$HAP_REPORT_DIR/vivado.jou"
rc=$?

find "$HAP_REPORT_DIR" -maxdepth 1 -type f ! -name ARTIFACT_SHA256SUMS \
  -print0 | sort -z | xargs -0 -r sha256sum \
  > "$HAP_REPORT_DIR/ARTIFACT_SHA256SUMS"
if [[ -f "$HAP_REPORT_DIR/summary.txt" ]]; then
  cat "$HAP_REPORT_DIR/summary.txt"
fi
printf '%s\n' "$HAP_REPORT_DIR"
exit "$rc"
