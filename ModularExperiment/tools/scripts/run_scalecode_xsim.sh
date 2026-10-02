#!/usr/bin/env bash
set -uo pipefail

ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
EXP="$ROOT/ModularExperiment"
STAMP="$(date +%Y%m%d_%H%M%S)"
INDEX="$EXP/result/_environment/scalecode_xsim_${STAMP}.tsv"

mkdir -p "$EXP/result/_environment"
printf 'module\tscript\texit_status\treport_dir\n' > "$INDEX"

run_one() {
    local module="$1"
    local script="$2"
    local label="$3"
    local report="$EXP/result/$module/raw/sc/xsim/${STAMP}_${label}"
    local rc

    mkdir -p "$report"
    touch "$report/run_started.marker"
    printf 'RUNNING\n' > "$report/STATUS"
    printf 'module=%s\nvariant=sc\nrun_kind=xsim\nstarted_at=%s\nscript=%s\n' \
        "$module" "$(date --iso-8601=seconds)" "$script" > "$report/run_manifest.txt"
    git -C "$ROOT" rev-parse HEAD >> "$report/production_commit.txt"
    git -C "$ROOT" status --short > "$report/git_status.txt"
    sha256sum "$ROOT/$script" > "$report/launcher_sha256.txt"

    printf '[%s] %s -> %s\n' "$(date --iso-8601=seconds)" "$module" "$report"
    (
        cd "$ROOT"
        HAP_REPORT_DIR="$report" bash "$ROOT/$script"
    ) > >(tee "$report/launcher_console.log") 2>&1
    rc=$?

    for artifact in xvlog.log xvlog.pb xelab.log xelab.pb xsim.log xsim.jou; do
        if [[ -f "$ROOT/$artifact" && "$ROOT/$artifact" -nt "$report/run_started.marker" && \
              ! -f "$report/$artifact" ]]; then
            cp -p "$ROOT/$artifact" "$report/$artifact"
        fi
    done
    printf '%s\n' "$rc" > "$report/exit_status.txt"
    printf 'finished_at=%s\nexit_status=%s\n' \
        "$(date --iso-8601=seconds)" "$rc" >> "$report/run_manifest.txt"
    if [[ "$rc" -eq 0 ]]; then
        printf 'PASS\n' > "$report/STATUS"
    else
        printf 'FAIL\n' > "$report/STATUS"
    fi
    find "$report" -maxdepth 1 -type f ! -name SHA256SUMS -print0 \
        | sort -z | xargs -0 sha256sum > "$report/SHA256SUMS"
    printf '%s\t%s\t%s\t%s\n' "$module" "$script" "$rc" "$report" >> "$INDEX"
    return 0
}

# Runs are deliberately serialized: several legacy launchers share root-level
# xvlog/xelab logs and xsim.dir, and concurrent runs would corrupt evidence.
run_one 00_scale_apply_microkernel \
    vivado/scripts/run_a8w4_scalecode_recover2_lut_xsim.sh a8w4_scalecode_recover2
run_one 02_attention_a8w8_projection \
    ModularExperiment/experiment/02_attention_a8w8_projection/run_sc_xsim.sh a8w8_col3
run_one 06_attention_softmax \
    vivado/scripts/run_softmax_row_128_xsim.sh softmax_row128
run_one 08_mlp_input_hadamard_a8 \
    vivado/scripts/run_mlp_input_frontend16_compact_cache_xsim.sh input_frontend_compact_cache
run_one 09_mlp_gate_up_a8w4 \
    vivado/scripts/run_mlp_shared_dual_slice16x12_s43_s45_xsim.sh shared_dual_slice_gate_up
run_one 10_mlp_silu_multiply \
    vivado/scripts/run_mlp_silu_mul_xsim.sh silu_mul
run_one 11_mlp_product_hadamard_a8 \
    vivado/scripts/run_mlp_product_frontend16_q4_xsim.sh product_frontend_q4
run_one 11_mlp_product_hadamard_a8 \
    vivado/scripts/run_mlp_swiglu_product_frontend16_q4_xsim.sh swiglu_product_frontend_q4
run_one 12_mlp_down_a8w4 \
    vivado/scripts/run_mlp_shared_dual_slice16x12_s43_s45_xsim.sh shared_dual_slice_down
run_one 12_mlp_down_a8w4 \
    vivado/scripts/run_mlp_down_group_major_accum_s45_v5_96_xsim.sh down_group_major_accum_v5_96

failures="$(awk -F '\t' 'NR > 1 && $3 != 0 {n++} END {print n+0}' "$INDEX")"
printf 'completed_at=%s\nfailures=%s\nindex=%s\n' \
    "$(date --iso-8601=seconds)" "$failures" "$INDEX"
[[ "$failures" -eq 0 ]]
