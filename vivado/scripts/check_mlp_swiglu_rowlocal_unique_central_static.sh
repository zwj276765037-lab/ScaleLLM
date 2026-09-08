#!/usr/bin/env bash
set -euo pipefail

# Text-only RTL contract gate for the cohort16 row-local SwiGLU frontend.
# This script does not elaborate/synthesize/place/route the design and cannot
# prove inferred or physical DSP count, fanout, timing, congestion, or CDC.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RTL="$ROOT/rtl/mlp/hap_mlp_swiglu_product_frontend16_q4.sv"
TOP=hap_mlp_swiglu_product_frontend16_q4

fail() {
    printf 'MLP SwiGLU row-local static contract failed: %s\n' "$*" >&2
    exit 1
}

[[ -s "$RTL" ]] || fail "missing ${RTL#"$ROOT/"}"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT
all_code="$tmpdir/all_code.sv"
top_code="$tmpdir/top_code.sv"
leaf_code="$tmpdir/leaf_code.sv"

# Comments are deliberately excluded: naming a contract item in prose is not
# structural evidence.  This remains a lexical checker, not an SV parser.
perl -0777 -pe 's{/\*.*?\*/}{}gs; s{//[^\n]*}{}g' "$RTL" > "$all_code"

# Extract exactly one lexical production-top body.  Helper modules in the same
# file must not satisfy the production-top instance or naming requirements.
extract_module() {
    local module_name="$1" destination="$2"
    awk -v module_name="$module_name" '
    $0 ~ "^[[:space:]]*module[[:space:]]+" module_name "([[:space:]#(]|$)" {
        seen++
        if (seen == 1) inside = 1
    }
    inside { print }
    inside && $0 ~ "^[[:space:]]*endmodule([[:space:]]|$)" {
        inside = 0
        done++
    }
    END {
        if (seen != 1 || done != 1 || inside) exit 1
    }
' "$all_code" > "$destination" ||
        fail "expected exactly one complete $module_name module"
}

LEAF=hap_mlp_swiglu_row_stream8_q4
extract_module "$TOP" "$top_code"
extract_module "$LEAF" "$leaf_code"

compact() {
    tr -d '[:space:]' < "$1"
}

top_compact="$(compact "$top_code")"
leaf_compact="$(compact "$leaf_code")"
all_compact="$(compact "$all_code")"

count_instances() {
    local source="$1" module_name="$2"
    awk -v module_name="$module_name" '
        $0 ~ "^[[:space:]]*" module_name "([[:space:]]|#)" {count++}
        END {print count + 0}
    ' "$source"
}

require_textual_instance_count() {
    local source="$1" scope="$2" module_name="$3" expected="$4" actual
    actual="$(count_instances "$source" "$module_name")"
    [[ "$actual" -eq "$expected" ]] ||
        fail "$scope requires exactly $expected textual $module_name instance declarations; found $actual"
}

require_compact_regex() {
    local description="$1" regex="$2"
    grep -Eq -- "$regex" <<< "$top_compact" ||
        fail "missing top-level $description evidence"
}

reject_all_compact_regex() {
    local description="$1" regex="$2"
    ! grep -Eq -- "$regex" <<< "$all_compact" ||
        fail "forbidden source $description"
}

count_fixed() {
    local source="$1" needle="$2"
    awk -v needle="$needle" '
        BEGIN {count = 0}
        {
            text = $0
            while ((at = index(text, needle)) != 0) {
                count++
                text = substr(text, at + length(needle))
            }
        }
        END {print count}
    ' "$source"
}

require_identifier_uses() {
    local identifier="$1" minimum="$2" actual
    actual="$(count_fixed "$top_code" "$identifier")"
    [[ "$actual" -ge "$minimum" ]] ||
        fail "$identifier requires declaration plus structural use; found $actual lexical uses"
}

# Static-expanded hierarchy contract:
#   * one direct central Hadamard;
#   * a strict 0..3 generate containing one quantizer declaration => four;
#   * a strict 0..1 row generate containing one leaf declaration, with exactly
#     one SiLU declaration in that leaf => two.
# These checks do not claim elaboration, inference, or physical DSP proof.
require_textual_instance_count "$top_code" "$TOP" \
    hap_mlp_hadamard32_s32_norm_stream 1
require_compact_regex 'unique central Hadamard instance u_hadamard' \
    'hap_mlp_hadamard32_s32_norm_stream(u_hadamard|#\([^;]*\)u_hadamard)\('

require_textual_instance_count "$top_code" "$TOP" \
    hap_mlp_robust_a8_quantizer_s35 1
require_compact_regex 'four-way g_quantizer generate bounds' \
    'for\(quantizer=0;quantizer<4;quantizer=quantizer\+1\)begin:g_quantizer'
require_compact_regex 'u_quantizer inside four-way g_quantizer generate' \
    'for\(quantizer=0;quantizer<4;quantizer=quantizer\+1\)begin:g_quantizer.*hap_mlp_robust_a8_quantizer_s35(u_quantizer|#\([^;]*\)u_quantizer)\('

require_textual_instance_count "$top_code" "$TOP" "$LEAF" 1
require_compact_regex 'two-way g_row_branch generate bounds' \
    'for\(row_branch=0;row_branch<2;row_branch=row_branch\+1\)begin:g_row_branch'
require_compact_regex 'u_branch_leaf inside two-way g_row_branch generate' \
    "for\\(row_branch=0;row_branch<2;row_branch=row_branch\\+1\\)begin:g_row_branch.*${LEAF}(u_branch_leaf|#\\([^;]*\\)u_branch_leaf)\\("
require_textual_instance_count "$leaf_code" "$LEAF" hap_mlp_silu_mul 1
[[ "$(count_instances "$top_code" hap_mlp_silu_mul)" -eq 0 ]] ||
    fail 'direct top-level hap_mlp_silu_mul instance bypasses the two row leaves'
[[ "$(count_instances "$all_code" hap_mlp_silu_mul)" -eq 1 ]] ||
    fail 'hap_mlp_silu_mul must occur only once textually inside the 2-way row leaf'
grep -Eq '^[[:space:]]*hap_mlp_silu_mul([[:space:]]|#).*u_silu([[:space:]]|\()' \
    "$leaf_code" || fail 'row leaf SiLU instance must be named u_silu'

# The command/abort clear may reach the wide SwiGLU state only through
# protected destination-local FFs: six central copies and one per generated
# row branch.  This lexical gate is followed by post-opt fanout auditing.
require_compact_regex 'protected central control clear FF' \
    '\(\*DONT_TOUCH="yes",KEEP="yes",SHREG_EXTRACT="NO"\*\)regcontrol_clear_local_r;'
require_compact_regex 'protected central Hadamard clear FF' \
    '\(\*DONT_TOUCH="yes",KEEP="yes",SHREG_EXTRACT="NO"\*\)reghadamard_clear_local_r;'
require_compact_regex 'protected four-way quantizer clear FF bank' \
    '\(\*DONT_TOUCH="yes",KEEP="yes",SHREG_EXTRACT="NO"\*\)reg\[3:0\]quantizer_clear_local_r;'
require_compact_regex 'Hadamard consumes only its local clear' \
    'u_hadamard\([^;]*\.clear\(hadamard_clear_local_r\)'
require_compact_regex 'each quantizer consumes its indexed local clear' \
    'u_quantizer\([^;]*\.clear\(quantizer_clear_local_r\[quantizer\]\)'
grep -Eq '\(\*[[:space:]]*DONT_TOUCH[[:space:]]*=[[:space:]]*"yes",[[:space:]]*KEEP[[:space:]]*=[[:space:]]*"yes",[[:space:]]*SHREG_EXTRACT[[:space:]]*=[[:space:]]*"NO"[[:space:]]*\*\)' \
    "$leaf_code" || fail 'row leaf local clear FF lacks preservation attributes'
grep -Eq '^[[:space:]]*reg[[:space:]]+clear_local_r[[:space:]]*;' \
    "$leaf_code" || fail 'row leaf local clear FF is missing'
grep -Eq '\.clear\(clear_local_r\)' "$leaf_code" || \
    fail 'row leaf SiLU does not consume the local clear FF'

# The superseded branch/folded architectures are forbidden anywhere in this
# source, including helper modules, so they cannot remain reachable by drift.
for forbidden in \
        hap_mlp_hadamard32_s32_norm_fold2 \
        hap_mlp_product_frontend8_q4; do
    ! grep -Eq "^[[:space:]]*(module[[:space:]]+)?${forbidden}([[:space:]#(]|$)" \
        "$all_code" || fail "forbidden source module/reference $forbidden"
done

# A branch-wide 8x32x32 S32 product array/bus recreates the prohibited wide
# product buffer.  Allow only narrow row/element S32 streams into the unique
# central Hadamard.  Match both packed arithmetic spellings and legacy names.
reject_all_compact_regex '8*32*32 packed product buffer declaration' \
    '(reg|logic|wire)(signed)?(\[8\*32\*32-1:0\]|\[32\*32\*8-1:0\]|\[8191:0\])[^;]*;'
reject_all_compact_regex '8-row by 32-column unpacked product buffer declaration' \
    '(reg|logic|wire)(signed)?\[31:0\][^;]*(product|s32)[^;]*\[0:7\]\[0:31\][^;]*;'
reject_all_compact_regex 'legacy branch product-group/product-buffer name' \
    '(reg|logic|wire)[^;]*(branch[^;]*(product_(group|buffer))|(product_(group|buffer))[^;]*branch)[^;]*;'

# Required, reviewable row-local bookkeeping contract.  Exact dimensions are
# independently required so a token in a comment cannot stand in for storage.
require_compact_regex 'narrow two-branch S32 stream declaration' \
    '(reg|logic|wire)(signed)?\[31:0\]branch_product_s32_stream\[0:1\];'
require_compact_regex 'two-branch 12-bit group sequence tag declaration' \
    '(reg|logic|wire)\[11:0\]branch_group_seq_tag\[0:1\];'
require_compact_regex 'two-branch 3-bit row tag declaration' \
    '(reg|logic|wire)\[2:0\]branch_row_tag\[0:1\];'
require_compact_regex 'two-branch 5-bit column tag declaration' \
    '(reg|logic|wire)\[4:0\]branch_column_tag\[0:1\];'
for declaration in branch_stream_valid branch_stream_ready; do
    require_compact_regex "two-branch $declaration declaration" \
        "(reg|logic|wire)\\[1:0\\]${declaration};"
done

require_compact_regex '2-bank x 16-row x 32-column S32 ring declaration' \
    '(reg|logic)(signed)?\[31:0\]row_ring_s32_r\[0:1\]\[0:15\]\[0:31\];'
require_compact_regex '2-bank x 16-row completion scoreboard declaration' \
    '(reg|logic)\[15:0\]row_complete_scoreboard_r\[0:1\];'
require_compact_regex '2-bank 12-bit group sequence declaration' \
    '(reg|logic)\[11:0\]bank_group_seq_r\[0:1\];'
for declaration in bank_valid_r bank_complete_r; do
    require_compact_regex "two-bank $declaration declaration" \
        "(reg|logic)\\[1:0\\]${declaration};"
done
require_compact_regex 'per-bank/per-branch beat-count declaration' \
    '(reg|logic)\[[^]]+\]bank_branch_beat_count_r\[0:1\]\[0:1\];'

# Each named object must be consumed beyond its declaration.  Physical
# existence and preservation still belong to later synth/post-opt gates.
for identifier in \
        branch_product_s32_stream branch_group_seq_tag \
        branch_row_tag branch_column_tag branch_stream_valid \
        branch_stream_ready row_ring_s32_r row_complete_scoreboard_r \
        bank_group_seq_r bank_valid_r bank_complete_r \
        bank_branch_beat_count_r; do
    require_identifier_uses "$identifier" 2
done

printf '%s\n' 'MLP_SWIGLU_ROWLOCAL_UNIQUE_CENTRAL_STATIC_PASS'
