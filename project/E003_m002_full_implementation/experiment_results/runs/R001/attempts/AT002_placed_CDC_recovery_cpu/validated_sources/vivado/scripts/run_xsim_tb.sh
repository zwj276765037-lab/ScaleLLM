#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 4 ]] || {
    printf 'usage: %s TOP TB_PATH SOURCES_MANIFEST PASS_MARKER\n' "$0" >&2
    exit 2
}
top="$1"
tb_arg="$2"
manifest_arg="$3"
pass_marker="$4"
[[ "$top" =~ ^[A-Za-z_][A-Za-z0-9_]*$ && -n "$pass_marker" ]] || exit 2
jobs="${HAP_JOBS:-8}"
limit="${HAP_XSIM_TIMEOUT_SECONDS:-300}"
[[ "$jobs" =~ ^[1-8]$ && "$limit" =~ ^[1-9][0-9]*$ ]] || exit 2
export OMP_NUM_THREADS="$jobs"
root="$(cd "$(dirname "$0")/../.." && pwd)"
reports="$root/vivado/reports"
resolve_input() {
    local candidate="$1" path
    if [[ "$candidate" == /* ]]; then
        path="$(readlink -m -- "$candidate")"
    else
        path="$(readlink -m -- "$root/$candidate")"
    fi
    [[ "$path" == "$root/"* && -s "$path" ]] || {
        printf 'Missing input or path outside hardware root: %s\n' "$candidate" >&2
        exit 2
    }
    printf '%s\n' "$path"
}
tb="$(resolve_input "$tb_arg")"
manifest="$(resolve_input "$manifest_arg")"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out="${HAP_XSIM_REPORT_DIR:-$reports/xsim_${top}_${stamp}_$$}"
out="$(readlink -m -- "$out")"
[[ "$out" == "$reports/"* && ! -e "$out" ]] || {
    printf 'XSim report path is outside new root or already exists: %s\n' "$out" >&2
    exit 2
}
if [[ -n "${VIVADO_BIN_DIR:-}" ]]; then
    bin="$VIVADO_BIN_DIR"
elif [[ -n "${XILINX_VIVADO:-}" ]]; then
    bin="$XILINX_VIVADO/bin"
elif command -v xvlog >/dev/null 2>&1; then
    bin="$(dirname "$(command -v xvlog)")"
else
    bin=/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin
fi
for tool in xvlog xelab xsim; do
    [[ -x "$bin/$tool" ]] || {
        printf 'XSim tool is missing: %s\n' "$bin/$tool" >&2
        exit 2
    }
done
bin="$(readlink -f -- "$bin")"
glbl="$bin/../data/verilog/src/glbl.v"
[[ -f "$glbl" && -s "$glbl" ]] || {
    printf 'Vivado glbl model is missing: %s\n' "$glbl" >&2
    exit 2
}
glbl="$(readlink -f -- "$glbl")"

declare -A seen_manifests=()
declare -A seen_inputs=()
declare -a inputs=("$glbl")
declare -a rtl=()
expand_manifest() {
    local list="$1" raw entry path
    [[ -z "${seen_manifests[$list]:-}" ]] || return 0
    seen_manifests[$list]=1
    inputs+=("$list")
    while IFS= read -r raw || [[ -n "$raw" ]]; do
        entry="${raw%%#*}"
        entry="${entry#"${entry%%[![:space:]]*}"}"
        entry="${entry%"${entry##*[![:space:]]}"}"
        [[ -n "$entry" ]] || continue
        path="$(resolve_input "$entry")"
        if [[ "$path" == *.list ]]; then
            expand_manifest "$path"
        elif [[ -z "${seen_inputs[$path]:-}" ]]; then
            seen_inputs[$path]=1
            inputs+=("$path")
            case "$path" in
                *.sv|*.v) rtl+=("$path") ;;
                *.mem) ;;
                *) printf 'Unsupported manifest input: %s\n' "$path" >&2; exit 2 ;;
            esac
        fi
    done < "$list"
}
expand_manifest "$manifest"
(( ${#rtl[@]} > 0 )) || { printf 'No RTL sources selected\n' >&2; exit 2; }
[[ -d "$root/data" && -d "$root/tb" ]] || {
    printf 'Hardware data or testbench directory is missing\n' >&2
    exit 2
}
# Linked runtime paths may select ROMs/vectors/includes not in a manifest.
# The selected TB is hashed explicitly above; unrelated .sv/.v testbench files
# are not inputs and can be edited by an independent test author.
while IFS= read -r -d '' path; do
    path="$(resolve_input "$path")"
    if [[ -z "${seen_inputs[$path]:-}" ]]; then
        seen_inputs[$path]=1
        inputs+=("$path")
    fi
done < <(find -L "$root/data" "$root/tb" -type f ! -name '*.sv' ! -name '*.v' -print0)
mkdir -p "$out"
started="$(date -u +%FT%TZ)"
phase=prepare
status() {
    local rc="$?"
    trap - EXIT
    printf 'top=%s\nexit_code=%s\nphase=%s\nreports=%s\ntoolbin=%s\nstarted_utc=%s\nended_utc=%s\njobs=%s\nstep_timeout_seconds=%s\n' \
        "$top" "$rc" "$phase" "$out" "$bin" "$started" "$(date -u +%FT%TZ)" "$jobs" "$limit" \
        > "$out/launcher_status.txt"
    exit "$rc"
}
trap status EXIT
sha256sum -- "$0" "$tb" "${inputs[@]}" > "$out/inputs.sha256"
ln -s "$root/data" "$out/data"
ln -s "$root/tb" "$out/tb"
cd "$out"
for tool in xvlog xelab xsim; do
    phase="version_$tool"
    printf '%s: ' "$bin/$tool" >> "$out/tool_versions.txt"
    timeout --kill-after=10s 30 "$bin/$tool" -version >> "$out/tool_versions.txt" 2>&1
done
xvlog_args=(-sv -L xpm -L unisims_ver
    -d HAP_BOARD_V5
    -d HAP_MLP_FULL_COMMAND_V5_MODULE=hap_mlp_full_command16_s54
    -d HAP_ATTENTION_BOARD_MODULE=hap_attention_board_cohort16_core
    "${rtl[@]}" "$tb" "$glbl")
xelab_args=(-mt "$jobs" -L xpm -L unisims_ver "$top" glbl -s "${top}_sim")
xsim_args=("${top}_sim" -runall)
{
    printf '%q ' "$bin/xvlog" "${xvlog_args[@]}"
    printf '\n'
    printf '%q ' "$bin/xelab" "${xelab_args[@]}"
    printf '\n'
    printf '%q ' "$bin/xsim" "${xsim_args[@]}"
    printf '\n'
} > "$out/argv.txt"
phase=xvlog
timeout --kill-after=10s "$limit" "$bin/xvlog" "${xvlog_args[@]}" > "$out/xvlog.log" 2>&1
phase=xelab
timeout --kill-after=10s "$limit" "$bin/xelab" "${xelab_args[@]}" > "$out/xelab.log" 2>&1
phase=xsim
timeout --kill-after=10s "$limit" "$bin/xsim" "${xsim_args[@]}" > "$out/xsim.log" 2>&1
phase=log_validation
if grep -Ein '(^|[^[:alnum:]_])(ERROR|FATAL|FAIL)([^[:alnum:]_]|$)|\$error' \
    "$out/xvlog.log" "$out/xelab.log" "$out/xsim.log" \
    > "$out/fault_lines.txt"; then
    printf 'XSim log contains FAIL, ERROR, FATAL, or $error\n' >&2
    exit 1
fi
[[ "$(grep -Fxc -- "$pass_marker" "$out/xsim.log" || true)" -eq 1 ]] || {
    printf 'Unique testbench pass marker not found: %s\n' "$pass_marker" >&2
    exit 1
}
sha256sum --status -c "$out/inputs.sha256"
phase=complete
printf 'PASS: %s\n' "$out"
