#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_PRODUCTION_MANIFEST="$ROOT/vivado/manifests/attention_mlp_production_v4_sources.list"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/v4_production_core_$STAMP}"
export HAP_BUILD_DIR="${HAP_BUILD_DIR:-$ROOT/vivado/build/v4_production_synth_$STAMP}"
mkdir -p "$HAP_REPORT_DIR"

# Freeze the complete recursive source graph, not just a hand-picked subset.
# A successful DCP is admissible only when every manifest, RTL and memory file
# read by Vivado is bound to this run before Vivado starts.
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
for evidence_input in \
  "$ROOT/vivado/scripts/run_attention_mlp_production_v4_synth.sh" \
  "$ROOT/vivado/scripts/run_attention_mlp_production_synth.sh" \
  "$ROOT/vivado/scripts/synth_attention_mlp_production_core.tcl"; do
  if [[ -z "${seen[$evidence_input]+x}" ]]; then
    seen["$evidence_input"]=1
    inputs+=("$evidence_input")
  fi
done
printf '%s\n' "${inputs[@]}" | LC_ALL=C sort -u > "$HAP_REPORT_DIR/INPUT_FILES"
xargs -d '\n' sha256sum < "$HAP_REPORT_DIR/INPUT_FILES" \
  > "$HAP_REPORT_DIR/INPUT_SHA256SUMS"
exec "$ROOT/vivado/scripts/run_attention_mlp_production_synth.sh"
