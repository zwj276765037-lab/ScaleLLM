#!/usr/bin/env bash
set -euo pipefail

[[ $# -ge 1 && $# -le 2 && ( "$1" == sc || "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s sc|fp16|fp32 [0|1 backpressure]\n' "$0" >&2
    exit 2
}

ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/12_mlp_down_a8w4"
RESULT="$ROOT/ModularExperiment/result/12_mlp_down_a8w4"
variant="$1"
backpressure="${2:-1}"
[[ "$backpressure" == 0 || "$backpressure" == 1 ]] || exit 2

# Hold the shared slot across both child runs; the children inherit the guard
# and execute strictly one after the other.
source "$MODULE/guard_vivado_slot.sh"

vector_verify=$(python3 "$MODULE/model/verify_mini_vectors.py")
stamp=$(date +%Y%m%d_%H%M%S)
report="$RESULT/raw/$variant/ab/${stamp}_down_a8w4_full_lane_nonzero_wave_equivalence_bp${backpressure}"
mkdir -p "$report"
printf 'RUNNING\n' > "$report/STATUS"
printf '%s\n' "$vector_verify" > "$report/VECTOR_VERIFY.txt"

verify_child() {
    local child="$1"
    [[ $(<"$child/STATUS") == PASS ]] &&
        [[ $(<"$child/exit_status.txt") == 0 ]] &&
        (cd "$child" && sha256sum -c SHA256SUMS >/dev/null) &&
        (cd "$child" && sha256sum -c INPUT_SHA256SUMS >/dev/null)
}

set +e
wave_output=$("$MODULE/run_serial_xsim.sh" "$variant" "$backpressure" wave)
wave_rc=$?
set -e
wave_report=$(printf '%s\n' "$wave_output" | tail -n 1)
printf '%s\n' "$wave_report" > "$report/wave_report.txt"

nowave_rc=1
nowave_report=""
if [[ "$wave_rc" -eq 0 && -d "$wave_report" ]]; then
    set +e
    nowave_output=$("$MODULE/run_serial_xsim.sh" \
        "$variant" "$backpressure" nowave)
    nowave_rc=$?
    set -e
    nowave_report=$(printf '%s\n' "$nowave_output" | tail -n 1)
fi
printf '%s\n' "$nowave_report" > "$report/nowave_report.txt"

rc=1
if [[ "$wave_rc" -eq 0 && "$nowave_rc" -eq 0 &&
        -d "$wave_report" && -d "$nowave_report" ]] &&
        verify_child "$wave_report" && verify_child "$nowave_report" &&
        cmp -s "$wave_report/input_accepts.txt" \
            "$nowave_report/input_accepts.txt" &&
        cmp -s "$wave_report/output_words.txt" \
            "$nowave_report/output_words.txt" &&
        cmp -s "$wave_report/functional_metrics.txt" \
            "$nowave_report/functional_metrics.txt" &&
        cmp -s "$wave_report/summary.txt" "$nowave_report/summary.txt"; then
    wave_wdb=$(<"$wave_report/wdb_total_bytes.txt")
    nowave_wdb=$(<"$nowave_report/wdb_total_bytes.txt")
    if (( wave_wdb > 0 && nowave_wdb < wave_wdb )); then
        rc=0
    fi
else
    wave_wdb=-1
    nowave_wdb=-1
fi

if [[ "$rc" -eq 0 ]]; then
    printf 'PASS\n' > "$report/STATUS"
else
    printf 'FAIL\n' > "$report/STATUS"
fi
printf '%s\n' "$rc" > "$report/exit_status.txt"

jq -n \
    --arg variant "$variant" \
    --argjson backpressure "$backpressure" \
    --arg wave_report "$wave_report" \
    --arg nowave_report "$nowave_report" \
    --argjson wave_rc "$wave_rc" \
    --argjson nowave_rc "$nowave_rc" \
    --argjson wave_wdb_bytes "$wave_wdb" \
    --argjson nowave_wdb_bytes "$nowave_wdb" \
    --argjson bit_exact "$([[ "$rc" -eq 0 ]] && printf 1 || printf 0)" \
    '{schema:"scalellm_m12_serial_wave_ab_v1", variant:$variant,
      backpressure:$backpressure, wave_report:$wave_report,
      nowave_report:$nowave_report, wave_rc:$wave_rc,
      nowave_rc:$nowave_rc, wave_wdb_bytes:$wave_wdb_bytes,
      nowave_wdb_bytes:$nowave_wdb_bytes,
      outputs_metrics_and_handshake_bit_exact:$bit_exact}' \
    > "$report/comparison.json"

sources=(
    "$MODULE/run_serial_ab.sh"
    "$MODULE/guard_vivado_slot.sh"
    "$MODULE/run_serial_xsim.sh"
    "$MODULE/vivado/run_serial_xsim.tcl"
    "$MODULE/vivado/run_1000ns_no_wave.tcl"
    "$MODULE/tb/m12_down_serial_ooc_wrapper_tb.sv"
    "$MODULE/model/generate_mini_vectors.py"
    "$MODULE/model/generate_vectors.py"
    "$MODULE/model/verify_mini_vectors.py"
    "$MODULE/data_mini/manifest.json"
)
sha256sum "${sources[@]}" > "$report/INPUT_SHA256SUMS"
if [[ -d "$wave_report" && -d "$nowave_report" ]]; then
    sha256sum "$wave_report/SHA256SUMS" "$nowave_report/SHA256SUMS" \
        > "$report/CHILD_SHA256SUMS"
fi
find "$report" -maxdepth 1 -type f ! -name SHA256SUMS -print0 \
    | sort -z | xargs -0 sha256sum > "$report/SHA256SUMS"

if [[ "$rc" -eq 0 ]]; then
    printf 'M12_SERIAL_AB_PASS variant=%s backpressure=%s wave_wdb=%s nowave_wdb=%s report=%s\n' \
        "$variant" "$backpressure" "$wave_wdb" "$nowave_wdb" "$report"
else
    printf 'M12_SERIAL_AB_FAIL variant=%s backpressure=%s wave_rc=%s nowave_rc=%s report=%s\n' \
        "$variant" "$backpressure" "$wave_rc" "$nowave_rc" "$report" >&2
fi
exit "$rc"
