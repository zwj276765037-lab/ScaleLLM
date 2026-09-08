#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LIB="$ROOT/vivado/scripts/v5_board_build_provenance.sh"
source "$LIB"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

assert_rejected() {
    local label="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        printf 'V5_BOARD_PROVENANCE_TEST_FAIL: accepted %s\n' "$label" >&2
        exit 1
    fi
}

# Recursive manifest closure: prove nesting, exact counts and fail-closed
# handling of duplicate sources and root escape.
SRC="$TMP/source_root"
mkdir -p "$SRC/manifests" "$SRC/rtl"
printf 'module a; endmodule\n' > "$SRC/rtl/a.sv"
printf 'module b; endmodule\n' > "$SRC/rtl/b.sv"
printf 'rtl/b.sv\n' > "$SRC/manifests/leaf.list"
printf 'manifests/leaf.list\nrtl/a.sv\n' > "$SRC/manifests/root.list"
hap_v5_expand_source_manifest "$SRC" "$SRC/manifests/root.list" \
    manifests sources closure
[[ "${#manifests[@]}" -eq 2 && "${#sources[@]}" -eq 2 &&
    "${#closure[@]}" -eq 4 ]]
printf 'manifests/leaf.list\nrtl/b.sv\n' > "$SRC/manifests/duplicate.list"
assert_rejected duplicate_source hap_v5_expand_source_manifest \
    "$SRC" "$SRC/manifests/duplicate.list" dm ds dc
printf '/etc/hosts\n' > "$SRC/manifests/escape.list"
assert_rejected absolute_escape hap_v5_expand_source_manifest \
    "$SRC" "$SRC/manifests/escape.list" em es ec
printf '../outside.sv\n' > "$SRC/manifests/relative_escape.list"
printf 'module outside; endmodule\n' > "$TMP/outside.sv"
assert_rejected relative_escape hap_v5_expand_source_manifest \
    "$SRC" "$SRC/manifests/relative_escape.list" rm rs rc

GOOD="$TMP/route_good"
hap_v5_make_ooc_route_fixture "$GOOD"
hap_v5_verify_ooc_route_artifact "$GOOD"

# A single forged PASS summary cannot authorize a build without the complete
# exact 25-input/dynamically-complete output hash closure and physical reports.
FORGED="$TMP/route_forged"
mkdir "$FORGED"
hap_v5_route_required_summary_lines > "$FORGED/summary.txt"
printf 'wns_ns=0.1\nwhs_ns=0.1\n' >> "$FORGED/summary.txt"
assert_rejected summary_only hap_v5_verify_ooc_route_artifact "$FORGED"

cp -a "$GOOD" "$TMP/route_bad_status"
sed -i 's/status=V5_P10_P7_PRODUCTION_OOC_POST_ROUTE_PASS/status=FAIL/' \
    "$TMP/route_bad_status/summary.txt"
mapfile -d '' outputs < <(find "$TMP/route_bad_status" -maxdepth 1 \
    -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
sha256sum -- "${outputs[@]}" > "$TMP/route_bad_status/OUTPUT_SHA256SUMS"
assert_rejected bad_status hap_v5_verify_ooc_route_artifact \
    "$TMP/route_bad_status"

cp -a "$GOOD" "$TMP/route_bad_timing"
sed -i 's/wns_ns=0.125/wns_ns=-0.001/' \
    "$TMP/route_bad_timing/summary.txt"
mapfile -d '' outputs < <(find "$TMP/route_bad_timing" -maxdepth 1 \
    -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
sha256sum -- "${outputs[@]}" > "$TMP/route_bad_timing/OUTPUT_SHA256SUMS"
assert_rejected negative_wns hap_v5_verify_ooc_route_artifact \
    "$TMP/route_bad_timing"

cp -a "$GOOD" "$TMP/route_mutated"
printf 'mutated\n' >> "$TMP/route_mutated/post_route.dcp"
assert_rejected mutated_output hap_v5_verify_ooc_route_artifact \
    "$TMP/route_mutated"

cp -a "$GOOD" "$TMP/route_bad_boundaries"
sed -i 's/mlp_capture_leaf_instances=1632/mlp_capture_leaf_instances=1631/' \
    "$TMP/route_bad_boundaries/architecture_boundaries_post_route.txt"
mapfile -d '' outputs < <(find "$TMP/route_bad_boundaries" -maxdepth 1 \
    -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
sha256sum -- "${outputs[@]}" > \
    "$TMP/route_bad_boundaries/OUTPUT_SHA256SUMS"
assert_rejected bad_architecture_boundaries \
    hap_v5_verify_ooc_route_artifact "$TMP/route_bad_boundaries"

cp -a "$GOOD" "$TMP/route_bit_leak"
printf 'not-a-real-bitstream\n' > "$TMP/route_bit_leak/leaked.bit"
assert_rejected bitstream_in_ooc_route hap_v5_verify_ooc_route_artifact \
    "$TMP/route_bit_leak"

# A nonempty route-side diagnostic that is not represented by the dynamic
# manifest must fail even when all required PASS outputs remain intact.
cp -a "$GOOD" "$TMP/route_untracked_output"
printf 'untracked route evidence\n' > \
    "$TMP/route_untracked_output/untracked_route.rpt"
assert_rejected untracked_route_output hap_v5_verify_ooc_route_artifact \
    "$TMP/route_untracked_output"

UNTRACKED_CASE="$TMP/untracked_case/route_good"
hap_v5_make_ooc_route_fixture "$UNTRACKED_CASE"
PLACE_UNTRACKED="$(dirname "$UNTRACKED_CASE")/place_fixture"
printf 'untracked place evidence\n' > "$PLACE_UNTRACKED/untracked.rpt"
assert_rejected untracked_place_output hap_v5_verify_ooc_route_artifact \
    "$UNTRACKED_CASE"

MISSING_CASE="$TMP/missing_case/route_good"
hap_v5_make_ooc_route_fixture "$MISSING_CASE"
PLACE_MISSING="$(dirname "$MISSING_CASE")/place_fixture"
sed -i '\|/launcher_status.txt$|d' "$PLACE_MISSING/OUTPUT_SHA256SUMS"
assert_rejected missing_place_manifest_member \
    hap_v5_verify_ooc_route_artifact "$MISSING_CASE"

BAD_MANIFEST_SHA_CASE="$TMP/bad_manifest_sha_case/route_good"
hap_v5_make_ooc_route_fixture "$BAD_MANIFEST_SHA_CASE"
sed -i 's/^place_output_manifest_sha256=.*/place_output_manifest_sha256=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/' \
    "$BAD_MANIFEST_SHA_CASE/summary.txt"
mapfile -d '' outputs < <(find "$BAD_MANIFEST_SHA_CASE" -maxdepth 1 \
    -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
sha256sum -- "${outputs[@]}" > "$BAD_MANIFEST_SHA_CASE/OUTPUT_SHA256SUMS"
assert_rejected bad_place_manifest_self_sha \
    hap_v5_verify_ooc_route_artifact "$BAD_MANIFEST_SHA_CASE"

BAD_PLACE_INPUT_SHA_CASE="$TMP/bad_place_input_sha_case/route_good"
hap_v5_make_ooc_route_fixture "$BAD_PLACE_INPUT_SHA_CASE"
sed -i 's/^place_input_manifest_sha256=.*/place_input_manifest_sha256=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/' \
    "$BAD_PLACE_INPUT_SHA_CASE/summary.txt"
mapfile -d '' outputs < <(find "$BAD_PLACE_INPUT_SHA_CASE" -maxdepth 1 \
    -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
sha256sum -- "${outputs[@]}" > "$BAD_PLACE_INPUT_SHA_CASE/OUTPUT_SHA256SUMS"
assert_rejected bad_place_input_manifest_self_sha \
    hap_v5_verify_ooc_route_artifact "$BAD_PLACE_INPUT_SHA_CASE"

BAD_ROUTE_INPUT_SHA_CASE="$TMP/bad_route_input_sha_case/route_good"
hap_v5_make_ooc_route_fixture "$BAD_ROUTE_INPUT_SHA_CASE"
sed -i 's/^route_input_manifest_sha256=.*/route_input_manifest_sha256=cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc/' \
    "$BAD_ROUTE_INPUT_SHA_CASE/summary.txt"
mapfile -d '' outputs < <(find "$BAD_ROUTE_INPUT_SHA_CASE" -maxdepth 1 \
    -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
sha256sum -- "${outputs[@]}" > "$BAD_ROUTE_INPUT_SHA_CASE/OUTPUT_SHA256SUMS"
assert_rejected bad_route_input_manifest_self_sha \
    hap_v5_verify_ooc_route_artifact "$BAD_ROUTE_INPUT_SHA_CASE"

printf 'V5_BOARD_BUILD_PROVENANCE_TEST_PASS\n'
printf 'recursive_manifest_fixture=2\n'
printf 'recursive_source_fixture=2\n'
printf 'route_input_manifest_entries=25\n'
printf 'route_output_manifest_mode=dynamic_complete\n'
printf 'negative_cases=15\n'
