#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 1 && ( "$1" == sc || "$1" == sc_auto || \
                  "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s sc|sc_auto|fp16|fp32\n' "$0" >&2
    exit 2
}
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/13_scalecode_fp_recovery_array"
RESULT="$ROOT/ModularExperiment/result/13_scalecode_fp_recovery_array"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
variant="$1"

source "$MODULE/guard_vivado_slot.sh"
python3 "$MODULE/model/generate_vectors.py"
stamp="$(date +%Y%m%d_%H%M%S)"
report="$RESULT/raw/$variant/xsim/${stamp}_recovery_array96_4096vectors"
build="${TMPDIR:-/tmp}/scalellm_modular_m13_xsim/${stamp}_${variant}"
mkdir -p "$report" "$build"
export HAP_SCALE_VARIANT="$variant" HAP_REPORT_DIR="$report"
export HAP_BUILD_DIR="$build" HAP_DATA_DIR="$MODULE/data"
printf 'RUNNING\n' > "$report/STATUS"

list="$MODULE/vivado/fp.sources"
[[ "$variant" == sc ]] && list="$MODULE/vivado/sc.sources"
[[ "$variant" == sc_auto ]] && list="$MODULE/vivado/sc_auto.sources"
sources=("$MODULE/README.md" "$MODULE/model/generate_vectors.py"
    "$MODULE/data/manifest.json" "$MODULE/tb/m13_recovery_array_tb.sv"
    "$MODULE/vivado/run_xsim.tcl" "$MODULE/guard_vivado_slot.sh" "$list")
while IFS= read -r source; do
    [[ -n "$source" && "$source" != \#* ]] && sources+=("$source")
done < "$list"
[[ "$variant" == sc || "$variant" == sc_auto ]] || \
    sources+=("$MODULE/vivado/create_fp_ip.tcl")
while IFS= read -r -d '' data_file; do
    sources+=("$data_file")
done < <(find "$MODULE/data" -maxdepth 1 -type f ! -name manifest.json -print0 | sort -z)
sha256sum "${sources[@]}" > "$report/INPUT_SHA256SUMS"

set +e
"$VIVADO" -mode batch -notrace -source "$MODULE/vivado/run_xsim.tcl" \
    -journal "$report/vivado.jou" -log "$report/vivado.log" \
    > "$report/console.log" 2>&1
rc=$?
set -e
grep -E 'M13_METRIC_JSON:|PASS: M13|FAIL: M13|M13_MISMATCH' \
    "$report/console.log" > "$report/summary.txt" || true
if [[ "$rc" -eq 0 ]] && grep -Fq 'PASS: M13 recovery-only array' \
        "$report/console.log" && ! grep -Fq 'FAIL: M13' "$report/console.log"; then
    printf 'PASS\n' > "$report/STATUS"
else
    printf 'FAIL\n' > "$report/STATUS"
    rc=1
fi
printf '%s\n' "$rc" > "$report/exit_status.txt"
find "$report" -maxdepth 1 -type f ! -name SHA256SUMS -print0 \
    | sort -z | xargs -0 sha256sum > "$report/SHA256SUMS"
printf '%s\n' "$report"
exit "$rc"
