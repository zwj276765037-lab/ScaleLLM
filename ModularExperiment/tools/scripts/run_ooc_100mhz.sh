#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
EXP="$ROOT/ModularExperiment"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"

for required in HAP_OOC_MODULE HAP_OOC_VARIANT HAP_OOC_NAME HAP_OOC_TOP HAP_OOC_SOURCES_FILE; do
    [[ -n "${!required:-}" ]] || { printf 'missing %s\n' "$required" >&2; exit 2; }
done

STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT="$EXP/result/$HAP_OOC_MODULE/raw/$HAP_OOC_VARIANT/ooc/${STAMP}_${HAP_OOC_NAME}"
BUILD="${TMPDIR:-/tmp}/scalellm_modular_ooc/${STAMP}_${HAP_OOC_NAME}"
mkdir -p "$REPORT" "$BUILD"
export HAP_OOC_REPORT_DIR="$REPORT"
export HAP_OOC_BUILD_DIR="$BUILD/project"

printf 'RUNNING\n' > "$REPORT/STATUS"
printf 'module=%s\nvariant=%s\nname=%s\ntop=%s\nstarted_at=%s\n' \
    "$HAP_OOC_MODULE" "$HAP_OOC_VARIANT" "$HAP_OOC_NAME" "$HAP_OOC_TOP" \
    "$(date --iso-8601=seconds)" > "$REPORT/run_manifest.txt"
git -C "$ROOT" rev-parse HEAD > "$REPORT/production_commit.txt"
git -C "$ROOT" status --short > "$REPORT/git_status.txt"
cp -p "$HAP_OOC_SOURCES_FILE" "$REPORT/sources.list"
{
    sha256sum "$EXP/tools/tcl/run_ooc_100mhz.tcl" "$HAP_OOC_SOURCES_FILE"
    if [[ -n "${HAP_OOC_PRE_SYNTH_TCL:-}" ]]; then
        sha256sum "$HAP_OOC_PRE_SYNTH_TCL"
    fi
} > "$REPORT/driver_sha256.txt"
if [[ -n "${HAP_OOC_PRE_SYNTH_TCL:-}" ]]; then
    cp -p "$HAP_OOC_PRE_SYNTH_TCL" "$REPORT/pre_synth_driver.tcl"
fi
{
    # Future validity must fail closed if the common OOC driver, source list,
    # module launcher or generated-IP recipe changes after this run.
    sha256sum "$EXP/tools/scripts/run_ooc_100mhz.sh"
    sha256sum "$EXP/tools/tcl/run_ooc_100mhz.tcl"
    sha256sum "$HAP_OOC_SOURCES_FILE"
    if [[ -n "${HAP_OOC_LAUNCHER:-}" ]]; then
        sha256sum "$HAP_OOC_LAUNCHER"
    fi
    if [[ -n "${HAP_OOC_GUARD:-}" ]]; then
        sha256sum "$HAP_OOC_GUARD"
    fi
    if [[ -n "${HAP_OOC_PRE_SYNTH_TCL:-}" ]]; then
        sha256sum "$HAP_OOC_PRE_SYNTH_TCL"
    fi
    while IFS= read -r source; do
        [[ -n "$source" && "$source" != \#* ]] && sha256sum "$source"
    done < "$HAP_OOC_SOURCES_FILE"
} > "$REPORT/INPUT_SHA256SUMS"

set +e
"$VIVADO" -mode batch -notrace \
    -source "$EXP/tools/tcl/run_ooc_100mhz.tcl" \
    -journal "$REPORT/vivado.jou" -log "$REPORT/vivado.log" \
    > "$REPORT/console.log" 2>&1
rc=$?
set -e

# Preserve generated IP configuration files in the result itself.  The Tcl
# source captures how the IP was requested; the copied XCI files capture what
# this Vivado version actually generated for the run.
if [[ -n "${HAP_OOC_PRE_SYNTH_TCL:-}" ]]; then
    mkdir -p "$REPORT/ip_xci"
    while IFS= read -r -d '' xci; do
        cp -p "$xci" "$REPORT/ip_xci/$(basename "$xci")"
    done < <(find "$HAP_OOC_BUILD_DIR" -type f -name '*.xci' -print0)
    find "$REPORT/ip_xci" -maxdepth 1 -type f -print0 \
        | sort -z | xargs -0 -r sha256sum > "$REPORT/IP_XCI_SHA256SUMS"
fi

printf 'finished_at=%s\nexit_status=%s\nbuild_dir=%s\n' \
    "$(date --iso-8601=seconds)" "$rc" "$BUILD" >> "$REPORT/run_manifest.txt"
printf '%s\n' "$rc" > "$REPORT/exit_status.txt"
if [[ "$rc" -eq 0 && -f "$REPORT/summary.json" ]]; then
    printf 'PASS\n' > "$REPORT/STATUS"
else
    printf 'FAIL\n' > "$REPORT/STATUS"
fi
find "$REPORT" -maxdepth 1 -type f ! -name SHA256SUMS -print0 \
    | sort -z | xargs -0 sha256sum > "$REPORT/SHA256SUMS"
printf '%s\n' "$REPORT"
exit "$rc"
