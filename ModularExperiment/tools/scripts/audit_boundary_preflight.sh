#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment
cd "$ROOT"

modules=(
    01_attention_input_hadamard_a8
    02_attention_a8w8_projection
    03_attention_rope
    04_attention_kv12_quantizer
    05_attention_qk_score
    06_attention_softmax
    07_attention_pv
    08_mlp_input_hadamard_a8
    09_mlp_gate_up_a8w4
    10_mlp_silu_multiply
    11_mlp_product_hadamard_a8
    12_mlp_down_a8w4
)

shell_count=0
tcl_count=0
source_list_count=0
source_count=0
sv_count=0
inline_ip_driver_count=0

assert_exact_concat() {
    local combined="$1"
    local first_content_line="$2"
    shift 2
    diff -u <(awk 'FNR == 1 && NR != 1 {print ""} {print}' "$@") <(tail -n +"$first_content_line" "$combined")
    inline_ip_driver_count=$((inline_ip_driver_count + 1))
}

assert_exact_prefix() {
    local combined="$1"
    local first_content_line="$2"
    local original="$3"
    local original_lines
    original_lines=$(wc -l < "$original")
    diff -u "$original" <(tail -n +"$first_content_line" "$combined" | head -n "$original_lines")
    inline_ip_driver_count=$((inline_ip_driver_count + 1))
}

for module in "${modules[@]}"; do
    while IFS= read -r -d '' script; do
        bash -n "$script"
        if rg -n '\+[[:space:]]{2,}' "$script"; then
            printf 'PATCH_MARKER_CONTAMINATION %s\n' "$script" >&2
            exit 1
        fi
        [[ -x "$script" ]] || {
            printf 'NON_EXECUTABLE_SHELL %s\n' "$script" >&2
            exit 1
        }
        shell_count=$((shell_count + 1))
    done < <(find "experiment/$module" -maxdepth 1 -type f -name 'run*.sh' -print0 | sort -z)

    while IFS= read -r -d '' tcl; do
        tclsh <<EOF
set fd [open "$tcl" r]
set data [read \$fd]
close \$fd
if {![info complete \$data]} {
    puts stderr "INCOMPLETE_TCL $tcl"
    exit 1
}
EOF
        tcl_count=$((tcl_count + 1))
    done < <(find "experiment/$module/vivado" -maxdepth 1 -type f -name '*.tcl' -print0 | sort -z)

    while IFS= read -r -d '' list; do
        while IFS= read -r source; do
            [[ -z "$source" || "$source" == \#* ]] && continue
            [[ -f "$source" ]] || {
                printf 'MISSING_SOURCE list=%s source=%s\n' "$list" "$source" >&2
                exit 1
            }
            source_count=$((source_count + 1))
        done < "$list"
        source_list_count=$((source_list_count + 1))
    done < <(find "experiment/$module/vivado" -maxdepth 1 -type f -name '*.sources' -print0 | sort -z)

    sv_dirs=()
    [[ -d "experiment/$module/rtl" ]] && sv_dirs+=("experiment/$module/rtl")
    [[ -d "experiment/$module/tb" ]] && sv_dirs+=("experiment/$module/tb")
    while IFS= read -r -d '' sv; do
        python3 - "$sv" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
text = re.sub(r"//.*", "", text)
modules = len(re.findall(r"\bmodule\b", text))
endmodules = len(re.findall(r"\bendmodule\b", text))
if modules != endmodules or modules == 0:
    raise SystemExit(
        f"SV_MODULE_BALANCE_FAIL path={path} "
        f"modules={modules} endmodules={endmodules}")
PY
        sv_count=$((sv_count + 1))
    done < <(if ((${#sv_dirs[@]})); then
        find "${sv_dirs[@]}" -type f -name '*.sv' -print0 | sort -z
    fi)
done

m12_guard=experiment/12_mlp_down_a8w4/guard_vivado_slot.sh
bash -n "$m12_guard"
[[ -x "$m12_guard" ]] || {
    printf 'NON_EXECUTABLE_SHELL %s\n' "$m12_guard" >&2
    exit 1
}
shell_count=$((shell_count + 1))

while IFS= read -r -d '' combined; do
    if rg -n '^[[:space:]]*source[[:space:]]' "$combined"; then
        printf 'NESTED_SOURCE_IN_HASHED_COMBINED_TCL %s\n' "$combined" >&2
        exit 1
    fi
done < <(find experiment -type f -name 'create_boundary_all_fp_ip.tcl' -print0 | sort -z)

assert_exact_concat experiment/05_attention_qk_score/vivado/create_boundary_all_fp_ip.tcl 4 experiment/05_attention_qk_score/vivado/create_fp_ip.tcl experiment/05_attention_qk_score/vivado/create_boundary_fp_ip.tcl
assert_exact_prefix experiment/06_attention_softmax/vivado/create_boundary_all_fp_ip.tcl 3 experiment/06_attention_softmax/vivado/create_fp_ip.tcl
assert_exact_prefix experiment/07_attention_pv/vivado/create_boundary_all_fp_ip.tcl 3 experiment/07_attention_pv/vivado/create_fp_ip.tcl
assert_exact_concat experiment/10_mlp_silu_multiply/vivado/create_boundary_all_fp_ip.tcl 6 experiment/10_mlp_silu_multiply/vivado/create_fp_ip.tcl experiment/10_mlp_silu_multiply/vivado/create_boundary_fp_ip.tcl

python3 experiment/01_attention_input_hadamard_a8/model/verify_trace_vectors.py
python3 experiment/02_attention_a8w8_projection/model/verify_static_contracts.py
python3 experiment/03_attention_rope/model/verify_boundary_vectors.py
python3 experiment/03_attention_rope/model/verify_trace_vectors.py --integrity-only
python3 experiment/04_attention_kv12_quantizer/model/verify_trace_vectors.py
python3 experiment/05_attention_qk_score/model/verify_boundary_vectors.py
python3 experiment/05_attention_qk_score/model/verify_trace_vectors.py
python3 experiment/06_attention_softmax/model/verify_boundary_vectors.py
python3 experiment/06_attention_softmax/model/verify_trace_vectors.py
python3 experiment/07_attention_pv/model/verify_boundary_vectors.py
python3 experiment/07_attention_pv/model/verify_trace_vectors.py
python3 experiment/08_mlp_input_hadamard_a8/model/verify_trace_vectors.py
python3 experiment/09_mlp_gate_up_a8w4/model/verify_trace_vectors.py
python3 experiment/10_mlp_silu_multiply/model/verify_boundary_vectors.py
python3 experiment/10_mlp_silu_multiply/model/verify_trace_vectors.py
python3 experiment/11_mlp_product_hadamard_a8/model/verify_trace_vectors.py
python3 experiment/12_mlp_down_a8w4/model/verify_vectors.py
python3 experiment/12_mlp_down_a8w4/model/verify_trace_vectors.py --integrity-only
python3 experiment/12_mlp_down_a8w4/model/verify_mini_vectors.py
python3 experiment/12_mlp_down_a8w4/model/verify_fp16_correction.py
python3 experiment/12_mlp_down_a8w4/model/verify_static_contracts.py
python3 tools/scripts/verify_boundary_top_contracts.py

printf 'BOUNDARY_PREFLIGHT_PASS modules=%d shells=%d tcl=%d source_lists=%d sources=%d sv=%d inline_ip_drivers=%d\n' "${#modules[@]}" "$shell_count" "$tcl_count" "$source_list_count" "$source_count" "$sv_count" "$inline_ip_driver_count"
