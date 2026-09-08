#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIAG_DIR="$(readlink -e -- "${1:?usage: $0 DIAG_DIR VIVADO_PID}")"
VIVADO_PID="${2:?usage: $0 DIAG_DIR VIVADO_PID}"
SYNTH_LAUNCH="$ROOT/vivado/scripts/run_attention_mlp_production_v5_synth.sh"
P6_STATIC="$ROOT/vivado/scripts/check_attention_mlp_production_v5_p10_p6_static.sh"

[[ "$VIVADO_PID" =~ ^[1-9][0-9]*$ ]] || {
    printf 'invalid Vivado PID: %q\n' "$VIVADO_PID" >&2
    exit 2
}
[[ -d "$DIAG_DIR" && -x "$SYNTH_LAUNCH" && -x "$P6_STATIC" ]] || {
    printf 'P6 handoff input is missing\n' >&2
    exit 2
}
if [[ -r "/proc/$VIVADO_PID/cmdline" ]]; then
    tr '\0' ' ' < "/proc/$VIVADO_PID/cmdline" | \
        grep -Fq 'diagnose_attention_mlp_production_v5_p10_p5_redistribution.tcl' || {
        printf 'PID %s is not the expected diagnosis Vivado\n' "$VIVADO_PID" >&2
        exit 2
    }
fi

while kill -0 "$VIVADO_PID" 2>/dev/null; do
    sleep 60
done

ready=0
for _ in {1..10}; do
    if [[ -s "$DIAG_DIR/launcher_status.txt" && \
          -s "$DIAG_DIR/summary.txt" && \
          -s "$DIAG_DIR/INPUT_SHA256SUMS" && \
          -s "$DIAG_DIR/OUTPUT_SHA256SUMS" ]]; then
        ready=1
        break
    fi
    sleep 30
done
[[ "$ready" -eq 1 ]] || {
    printf 'P6 diagnosis evidence did not finalize: %s\n' "$DIAG_DIR" >&2
    exit 1
}
grep -Fqx 'status=PASS' "$DIAG_DIR/launcher_status.txt"
grep -Fqx 'final_exit_code=0' "$DIAG_DIR/launcher_status.txt"
grep -Fqx 'status=V5_P10_P5_REDISTRIBUTION_DIAGNOSIS_PASS' \
    "$DIAG_DIR/summary.txt"
grep -Fqx 'floorplan_mutated=0' "$DIAG_DIR/summary.txt"
grep -Fqx 'implementation_commands_run=0' "$DIAG_DIR/summary.txt"
grep -Fqx 'checkpoint_written=0' "$DIAG_DIR/summary.txt"
(cd / && sha256sum -c --strict "$DIAG_DIR/INPUT_SHA256SUMS") >/dev/null
(cd / && sha256sum -c --strict "$DIAG_DIR/OUTPUT_SHA256SUMS") >/dev/null
[[ -z "$(pgrep -af '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)" ]] || {
    printf 'another batch Vivado is active; fresh synthesis not started\n' >&2
    exit 75
}
"$P6_STATIC"

export HAP_JOBS=32
export HAP_REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/production_v5_synth_20260905_mission0085_p6_lockstep_v1}"
export HAP_BUILD_DIR="${HAP_BUILD_DIR:-$ROOT/vivado/build/production_v5_synth_20260905_mission0085_p6_lockstep_v1}"
printf 'P6_DIAGNOSIS_VERIFIED_STARTING_FRESH_SYNTH\n%s\n' "$HAP_REPORT_DIR"
exec "$SYNTH_LAUNCH"
