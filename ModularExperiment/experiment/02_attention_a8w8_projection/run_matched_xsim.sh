#!/usr/bin/env bash
set -euo pipefail

[[ $# -ge 1 && $# -le 3 && ( "$1" == sc || "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s sc|fp16|fp32 [0|1 backpressure] [synthetic|trace]\n' "$0" >&2
    exit 2
}

ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/02_attention_a8w8_projection"
RESULT="$ROOT/ModularExperiment/result/02_attention_a8w8_projection"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
variant="$1"
backpressure="${2:-1}"
dataset="${3:-synthetic}"
[[ "$backpressure" == 0 || "$backpressure" == 1 ]] || exit 2
[[ "$dataset" == synthetic || "$dataset" == trace ]] || {
    printf 'dataset must be synthetic or trace\n' >&2
    exit 2
}

if [[ "$dataset" == trace ]]; then
    data_dir="$MODULE/data_trace"
    if [[ ! -s "$data_dir/manifest.json" ]]; then
        python3 "$MODULE/model/generate_trace_vectors.py"
    fi
    python3 "$MODULE/model/verify_trace_vectors.py" --integrity-only
else
    data_dir="$MODULE/legacy_seed/data"
    python3 "$MODULE/legacy_seed/generate_vectors.py"
fi
stamp="$(date +%Y%m%d_%H%M%S)"
report="$RESULT/raw/$variant/xsim/${stamp}_matched_tile_boundary_inclusive_${dataset}_bp${backpressure}"
build="${TMPDIR:-/tmp}/scalellm_modular_projection_xsim/${stamp}_${variant}_${dataset}_bp${backpressure}"
mkdir -p "$report" "$build"
export HAP_SCALE_VARIANT="$variant" HAP_BACKPRESSURE="$backpressure"
export HAP_DATASET="$dataset" HAP_DATA_DIR="$data_dir"
export HAP_REPORT_DIR="$report" HAP_BUILD_DIR="$build"
printf 'RUNNING\n' > "$report/STATUS"

sources=(
    "$ROOT/rtl/attention/hap_a8w8_group32_lane_s42.sv"
    "$ROOT/rtl/attention/hap_linear_tile_accum_s42.sv"
    "$ROOT/ModularExperiment/experiment/00_scale_apply_microkernel/legacy_seed/rtl/m3_precenter_mac_group32.sv"
    "$ROOT/ModularExperiment/experiment/00_scale_apply_microkernel/legacy_seed/rtl/m3_s42_fifo.sv"
    "$ROOT/ModularExperiment/experiment/00_scale_apply_microkernel/legacy_seed/rtl/m3_mac_only_lane.sv"
    "$ROOT/ModularExperiment/experiment/00_scale_apply_microkernel/legacy_seed/rtl/m3_fp_scale_lanes.sv"
    "$MODULE/legacy_seed/rtl/m4_matched_tile.sv"
    "$MODULE/vivado/run_matched_xsim.tcl"
)
if [[ "$dataset" == trace ]]; then
    sources+=("$MODULE/tb/m02_projection_trace_tb.sv"
        "$MODULE/model/generate_trace_vectors.py"
        "$MODULE/model/verify_trace_vectors.py"
        "$MODULE/model/verify_fp16_nonfinite_probe.py"
        "$MODULE/data_trace/manifest.json"
        "$MODULE/data_trace/MANIFEST_SHA256")
    while IFS= read -r source; do
        sources+=("$source")
    done < <(python3 - "$MODULE/data_trace/manifest.json" <<'PY'
import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
capture = Path(manifest["projection_input_capture"])
trace = Path(manifest["source_trace_run"]) / "trace"
checkpoint = Path(manifest["checkpoint"])
paths = [
    Path(manifest["fp16_semantic_map"]),
    Path(manifest["fp16_semantic_map"]).parent / "STATUS",
    Path(manifest["fp16_semantic_map"]).parent / "exit_status.txt",
    Path(manifest["fp16_semantic_map"]).parent / "SHA256SUMS",
    capture / "manifest.json", capture / "MANIFEST_SHA256",
    trace / "manifest.json", trace / "MANIFEST_SHA256",
    checkpoint / "config.json",
    checkpoint / "model.safetensors.index.json",
]
for record in manifest["checkpoint_shards"]:
    paths.append(checkpoint / record["name"])
for record in manifest["source_tensors"]:
    root = capture if record["role"] == "attention_input_bf16" else trace
    paths.append(root / record["file"])
for path in sorted(set(path.resolve() for path in paths)):
    print(path)
PY
)
else
    sources+=("$MODULE/legacy_seed/tb/m4_tile_tb.sv"
        "$MODULE/legacy_seed/generate_vectors.py"
        "$data_dir/manifest.json")
fi
if [[ "$variant" != sc ]]; then
    sources+=("$ROOT/ModularExperiment/experiment/00_scale_apply_microkernel/vivado/create_fp_ip.tcl")
fi
sha256sum "${sources[@]}" > "$report/INPUT_SHA256SUMS"
while IFS= read -r -d '' data_file; do
    sha256sum "$data_file" >> "$report/INPUT_SHA256SUMS"
done < <(find "$data_dir" -maxdepth 1 -type f ! -name manifest.json \
    ! -name MANIFEST_SHA256 -print0 | sort -z)

set +e
"$VIVADO" -mode batch -notrace \
    -source "$MODULE/vivado/run_matched_xsim.tcl" \
    -journal "$report/vivado.jou" -log "$report/vivado.log" \
    > "$report/console.log" 2>&1
rc=$?
set -e
grep -E 'M4_TILE_METRIC_JSON:|M02_TRACE_METRIC_JSON:|PASS: M4|PASS: M02|FAIL: M4|FAIL: M02|M4_LANE_MISMATCH|M02_TRACE_(TILE|LANE)_MISMATCH' \
    "$report/console.log" > "$report/summary.txt" || true
pass_text='PASS: M4 matched tile'
[[ "$dataset" == trace ]] && pass_text='PASS: M02 real projection trace'
if [[ "$rc" -eq 0 ]] && grep -Fq "$pass_text" "$report/console.log" && \
        ! grep -Eq 'FAIL: M4|FAIL: M02' "$report/console.log"; then
    printf 'PASS\n' > "$report/STATUS"
else
    printf 'FAIL\n' > "$report/STATUS"
    rc=1
fi
find "$build" -type f -name '*.xci' -print0 | sort -z | xargs -0 -r sha256sum \
    > "$report/FP_XCI_SHA256SUMS"
printf '%s\n' "$rc" > "$report/exit_status.txt"
find "$report" -maxdepth 1 -type f ! -name SHA256SUMS -print0 \
    | sort -z | xargs -0 sha256sum > "$report/SHA256SUMS"
printf '%s\n' "$report"
exit "$rc"
