#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
STAMP="$(date +%Y%m%d_%H%M%S)"
SIM="hap_v5_production_top_smoke_sim_$STAMP"
requested_report="${HAP_REPORT_DIR:-$ROOT/vivado/reports/v5_production_top_smoke_xsim_$STAMP}"
requested_work="${HAP_XSIM_WORK_DIR:-$ROOT/xsim_work/$SIM}"
REPORT_DIR="$(readlink -m -- "$requested_report")"
WORK="$(readlink -m -- "$requested_work")"
MANIFEST="$ROOT/vivado/manifests/attention_mlp_production_v5_cohort16_sources.list"
TB="$ROOT/tb/hap_v4_production_top_smoke_tb.sv"
LAUNCHER="$ROOT/vivado/scripts/run_v5_production_top_smoke_xsim.sh"
DEFINES=(
  HAP_BOARD_BUILD
  HAP_MLP_FULL_COMMAND_V5_MODULE=hap_mlp_full_command16_s46
  HAP_ATTENTION_BOARD_MODULE=hap_attention_board_cohort16_core
)

[[ ! -e "$REPORT_DIR" ]] || {
  printf 'V5 production smoke evidence directory already exists: %s\n' \
    "$REPORT_DIR" >&2
  exit 2
}
[[ ! -e "$WORK" ]] || {
  printf 'V5 production smoke work directory already exists: %s\n' \
    "$WORK" >&2
  exit 2
}
for tool in xvlog xelab xsim; do
  [[ -x "$BIN/$tool" ]] || {
    printf 'Vivado Simulator executable is missing: %s\n' "$BIN/$tool" >&2
    exit 2
  }
done
GLBL_V="${GLBL_V:-$BIN/../ids_lite/ISE/verilog/src/glbl.v}"
[[ -f "$GLBL_V" ]] || GLBL_V="$BIN/../data/verilog/src/glbl.v"
GLBL_V="$(readlink -e -- "$GLBL_V")" || {
  printf 'Vivado glbl.v input is missing\n' >&2
  exit 2
}
[[ -s "$GLBL_V" ]] || {
  printf 'Vivado glbl.v input is empty: %s\n' "$GLBL_V" >&2
  exit 2
}
mkdir "$REPORT_DIR" "$WORK" "$WORK/work"

archive_outputs() {
  mapfile -d '' outputs < <(find "$REPORT_DIR" -maxdepth 1 \
    -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
  if [[ "${#outputs[@]}" -ne 0 ]]; then
    sha256sum -- "${outputs[@]}" > "$REPORT_DIR/OUTPUT_SHA256SUMS"
  fi
}
trap archive_outputs EXIT

fail() {
  printf 'V5 production top smoke rejected: %s\n' "$1" >&2
  archive_outputs
  exit 1
}

# Recursively freeze both manifest files and all leaf sources.  Entries are
# rooted at ROOT, duplicate sources are rejected, and every byte is rechecked
# after xsim so the PASS cannot describe a graph that changed during the run.
declare -A seen_manifests=()
declare -A seen_sources=()
manifests=()
sources=()
collect_manifest() {
  local manifest="$1" raw line path
  manifest="$(readlink -e -- "$manifest")" || {
    printf 'missing V5 production manifest: %s\n' "$manifest" >&2
    exit 2
  }
  [[ "$manifest" == "$ROOT"/* && -s "$manifest" ]] || {
    printf 'invalid V5 production manifest: %s\n' "$manifest" >&2
    exit 2
  }
  [[ -z "${seen_manifests[$manifest]+x}" ]] || return 0
  seen_manifests["$manifest"]=1
  manifests+=("$manifest")
  while IFS= read -r raw || [[ -n "$raw" ]]; do
    line="${raw%%#*}"
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    [[ -n "$line" ]] || continue
    [[ "$line" != /* ]] || {
      printf 'absolute V5 source-manifest entry rejected: %s\n' "$line" >&2
      exit 2
    }
    path="$(readlink -e -- "$ROOT/$line")" || {
      printf 'missing V5 production input: %s\n' "$ROOT/$line" >&2
      exit 2
    }
    [[ "$path" == "$ROOT"/* && -s "$path" ]] || {
      printf 'V5 production input escapes root or is empty: %s\n' "$path" >&2
      exit 2
    }
    if [[ "$path" == *.list ]]; then
      collect_manifest "$path"
    else
      [[ -z "${seen_sources[$path]+x}" ]] || continue
      case "$path" in
        *.sv|*.v|*.mem) ;;
        *) printf 'unsupported V5 production input: %s\n' "$path" >&2; exit 2;;
      esac
      seen_sources["$path"]=1
      sources+=("$path")
    fi
  done < "$manifest"
}

collect_manifest "$MANIFEST"
[[ "${#manifests[@]}" -eq 4 ]] || \
  fail "recursive manifest count ${#manifests[@]} != 4"
[[ "${#sources[@]}" -eq 90 ]] || \
  fail "recursive leaf-source count ${#sources[@]} != 90"

printf '%s\n' "${manifests[@]}" | LC_ALL=C sort \
  > "$REPORT_DIR/expanded_manifests.list"
printf '%s\n' "${sources[@]}" > "$REPORT_DIR/expanded_sources.list"
printf '%s\n' "${DEFINES[@]}" > "$REPORT_DIR/verilog_defines.list"

inputs=("${manifests[@]}" "${sources[@]}" "$TB" "$LAUNCHER" "$GLBL_V")
printf '%s\n' "${inputs[@]}" | LC_ALL=C sort -u \
  > "$REPORT_DIR/INPUT_FILES"
xargs -d '\n' sha256sum < "$REPORT_DIR/INPUT_FILES" \
  > "$REPORT_DIR/INPUT_SHA256SUMS"
(cd / && sha256sum -c --strict "$REPORT_DIR/INPUT_SHA256SUMS") \
  > "$REPORT_DIR/input_sha_precheck.txt" 2>&1

rtl_sources=()
mem_sources=()
for path in "${sources[@]}"; do
  case "$path" in
    *.sv|*.v) rtl_sources+=("$path");;
    *.mem) mem_sources+=("$path");;
  esac
done
[[ "${#rtl_sources[@]}" -eq 88 ]] || \
  fail "recursive RTL-source count ${#rtl_sources[@]} != 88"
[[ "${#mem_sources[@]}" -eq 2 ]] || \
  fail "recursive memory-source count ${#mem_sources[@]} != 2"
define_args=()
for define in "${DEFINES[@]}"; do define_args+=(-d "$define"); done

# Production ROM initializers use project-root-relative paths.  Keep the
# simulator runtime in the same root used by synthesis and board builds.
cd "$ROOT"
set +e
"$BIN/xvlog" --sv -L xpm --work "work=$WORK/work" \
  "${define_args[@]}" "${rtl_sources[@]}" "$TB" \
  > "$REPORT_DIR/xvlog.log" 2>&1
xvlog_rc=$?
if (( xvlog_rc == 0 )); then
  "$BIN/xvlog" --work "work=$WORK/work" "$GLBL_V" \
    >> "$REPORT_DIR/xvlog.log" 2>&1
  glbl_rc=$?
else
  glbl_rc=125
fi
if (( xvlog_rc == 0 && glbl_rc == 0 )); then
  "$BIN/xelab" -mt 8 -L xpm -L unisims_ver -L "work=$WORK/work" \
    work.hap_v4_production_top_smoke_tb work.glbl -s "$SIM" \
    > "$REPORT_DIR/xelab.log" 2>&1
  xelab_rc=$?
else
  xelab_rc=125
fi
if (( xelab_rc == 0 )); then
  "$BIN/xsim" "$SIM" -runall --log "$REPORT_DIR/xsim.log" \
    > "$REPORT_DIR/xsim_stdout.log" 2>&1
  xsim_rc=$?
else
  xsim_rc=125
fi
set -e

set +e
(cd / && sha256sum -c --strict "$REPORT_DIR/INPUT_SHA256SUMS") \
  > "$REPORT_DIR/input_sha_postcheck.txt" 2>&1
input_rc=$?
set -e
printf 'xvlog_exit_code=%d\nglbl_xvlog_exit_code=%d\n' \
  "$xvlog_rc" "$glbl_rc" > "$REPORT_DIR/launcher_status.txt"
printf 'xelab_exit_code=%d\nxsim_exit_code=%d\ninput_sha_recheck_exit_code=%d\n' \
  "$xelab_rc" "$xsim_rc" "$input_rc" >> "$REPORT_DIR/launcher_status.txt"

(( xvlog_rc == 0 && glbl_rc == 0 && xelab_rc == 0 && xsim_rc == 0 && \
   input_rc == 0 )) || fail "compile/elaboration/simulation/input-integrity status"
for required in xvlog.log xelab.log xsim.log xsim_stdout.log \
    launcher_status.txt input_sha_precheck.txt input_sha_postcheck.txt; do
  [[ -s "$REPORT_DIR/$required" ]] || fail "missing/empty $required"
done
if grep -Eiq '(^|[^[:alnum:]_])(FAIL|ERROR|FATAL)(:|\[|[[:space:]])' \
    "$REPORT_DIR/xvlog.log" "$REPORT_DIR/xelab.log" \
    "$REPORT_DIR/xsim.log" "$REPORT_DIR/xsim_stdout.log"; then
  fail "FAIL/Error/Fatal marker in tool or testbench log"
fi
PASS_RE='^PASS hap_v4_production_top_smoke checks=[0-9]+ soft_clear=[0-9]+ cycles=[0-9]+$'
[[ "$(grep -Ec "$PASS_RE" "$REPORT_DIR/xsim.log")" -eq 1 ]] || \
  fail "trusted production-top PASS marker missing or duplicated"
[[ "$(grep -Ec '^PASS ' "$REPORT_DIR/xsim.log")" -eq 1 ]] || \
  fail "unexpected additional PASS marker"

{
  printf 'status=V5_PRODUCTION_TOP_SMOKE_PASS\n'
  printf 'production_profile=cohort16\n'
  tool_version="$("$BIN/xsim" -version 2>/dev/null)"
  tool_version="${tool_version%%$'\n'*}"
  printf 'tool=%s\n' "$tool_version"
  printf 'top=hap_v4_production_top_smoke_tb\n'
  printf 'manifest=vivado/manifests/attention_mlp_production_v5_cohort16_sources.list\n'
  printf 'recursive_manifest_count=%d\n' "${#manifests[@]}"
  printf 'recursive_leaf_source_count=%d\n' "${#sources[@]}"
  printf 'recursive_rtl_source_count=%d\n' "${#rtl_sources[@]}"
  printf 'recursive_memory_source_count=%d\n' "${#mem_sources[@]}"
  printf 'verilog_define=HAP_BOARD_BUILD\n'
  printf 'verilog_define=HAP_MLP_FULL_COMMAND_V5_MODULE=hap_mlp_full_command16_s46\n'
  printf 'verilog_define=HAP_ATTENTION_BOARD_MODULE=hap_attention_board_cohort16_core\n'
  grep -E "$PASS_RE" "$REPORT_DIR/xsim.log"
} > "$REPORT_DIR/summary.txt"
archive_outputs
(cd / && sha256sum -c --strict "$REPORT_DIR/INPUT_SHA256SUMS")
(cd / && sha256sum -c --strict "$REPORT_DIR/OUTPUT_SHA256SUMS")
printf '%s\n' "$REPORT_DIR"
