#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_vcu118_v5_post_route_audit.sh"
AUDIT_TCL="$ROOT/vivado/scripts/audit_attention_mlp_vcu118_v5_post_route.tcl"
GATE_TCL="$ROOT/vivado/scripts/attention_mlp_vcu118_v5_post_route_gate.tcl"
SELECTOR_TCL="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
GEOMETRY_TCL="$ROOT/vivado/scripts/projection_core16x16_w8_reuse_ooc_floorplan.tcl"
P5_INPUT_TCL="$ROOT/vivado/scripts/v5_production_p5_input_partition_floorplan.tcl"
P6_POSTPROCESS_TCL="$ROOT/vivado/scripts/v5_production_p6_postprocess_partition_floorplan.tcl"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fail() {
    printf 'V5_BOARD_AUDIT_PROVENANCE_TEST_FAIL: %s\n' "$*" >&2
    exit 1
}

make_inputs() {
    local dir="$1"
    mkdir -p "$dir"
    printf 'fixture dcp\n' > "$dir/board.dcp"
    printf 'fixture bitstream\n' > "$dir/board.bit"
    printf 'fixture xdc inventory\n' > "$dir/xdc_inventory.txt"
}

# A mock executable exercises launcher failure archival without invoking
# Vivado.  A mock pgrep prevents an unrelated real batch process on the host
# from making this deterministic static test return the concurrency guard.
mkdir -p "$TMP/mockbin"
apply_mock="$TMP/mockbin/vivado"
cat > "$apply_mock" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
log="" journal=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -log) log="$2"; shift 2 ;;
        -journal) journal="$2"; shift 2 ;;
        *) shift ;;
    esac
done
printf 'mock vivado failure log\n' > "$log"
printf 'mock vivado failure journal\n' > "$journal"
printf 'extra failure diagnostic\n' > "$(dirname "$log")/mock_failure.txt"
exit 43
MOCK
cat > "$TMP/mockbin/pgrep" <<'MOCK'
#!/usr/bin/env bash
exit 1
MOCK
chmod +x "$TMP/mockbin/vivado" "$TMP/mockbin/pgrep"

make_inputs "$TMP/launcher_inputs"
set +e
PATH="$TMP/mockbin:$PATH" VIVADO="$apply_mock" \
HAP_AUDIT_DIR="$TMP/launcher_failure" \
    "$LAUNCHER" "$TMP/launcher_inputs/board.dcp" \
    "$TMP/launcher_inputs/board.bit" \
    "$TMP/launcher_inputs/xdc_inventory.txt" >/dev/null 2>&1
launcher_rc=$?
set -e
[[ "$launcher_rc" -eq 43 ]] ||
    fail "mock failure exit code was not preserved: $launcher_rc"
for exact in status=FAIL final_exit_code=43 vivado_exit_code=43 \
        vivado_invoked=1 input_sha_precheck=1 input_sha_postcheck=1 \
        input_manifest_sha_match=1; do
    grep -Fqx -- "$exact" "$TMP/launcher_failure/launcher_status.txt" ||
        fail "launcher failure status is missing: $exact"
done
(cd / && sha256sum -c --strict \
    "$TMP/launcher_failure/OUTPUT_SHA256SUMS" >/dev/null) ||
    fail 'launcher failure output manifest does not verify'
mapfile -d '' expected_outputs < <(find "$TMP/launcher_failure" \
    -maxdepth 1 -type f -size +0c ! -name OUTPUT_SHA256SUMS \
    -print0 | sort -z)
mapfile -t manifested_outputs < <(awk '{sub(/^[0-9a-f]{64}[[:space:]]+\*?/, ""); print}' \
    "$TMP/launcher_failure/OUTPUT_SHA256SUMS" | sort)
[[ "${#expected_outputs[@]}" -eq "${#manifested_outputs[@]}" ]] ||
    fail 'launcher failure output-manifest cardinality mismatch'
for index in "${!expected_outputs[@]}"; do
    [[ "${expected_outputs[$index]}" == "${manifested_outputs[$index]}" ]] ||
        fail 'launcher failure output manifest is not dynamically complete'
done
for required in vivado.log vivado.jou mock_failure.txt INPUT_FILES \
        INPUT_SHA256SUMS launcher_status.txt; do
    grep -Fq -- "$TMP/launcher_failure/$required" \
        "$TMP/launcher_failure/OUTPUT_SHA256SUMS" ||
        fail "launcher failure archive omitted $required"
done

# The launcher must reject a reused evidence directory before invoking even
# the mock tool.
mkdir "$TMP/reused"
set +e
PATH="$TMP/mockbin:$PATH" VIVADO="$apply_mock" \
HAP_AUDIT_DIR="$TMP/reused" \
    "$LAUNCHER" "$TMP/launcher_inputs/board.dcp" \
    "$TMP/launcher_inputs/board.bit" \
    "$TMP/launcher_inputs/xdc_inventory.txt" >/dev/null 2>&1
fresh_rc=$?
set -e
[[ "$fresh_rc" -eq 2 && ! -e "$TMP/reused/vivado.log" ]] ||
    fail 'fresh-directory rejection did not occur before tool invocation'

make_tcl_fixture() {
    local dir="$1"
    make_inputs "$dir"
    mkdir -p "$dir/evidence"
    local -a exact=(
        "$dir/board.dcp" "$dir/board.bit" "$dir/xdc_inventory.txt"
        "$AUDIT_TCL" "$GATE_TCL" "$SELECTOR_TCL" "$GEOMETRY_TCL"
        "$P5_INPUT_TCL" "$P6_POSTPROCESS_TCL" "$LAUNCHER"
    )
    printf '%s\n' "${exact[@]}" > "$dir/evidence/INPUT_FILES"
    sha256sum -- "${exact[@]}" > "$dir/evidence/INPUT_SHA256SUMS"
    sha256sum -- "$dir/evidence/INPUT_SHA256SUMS" | awk '{print $1}' \
        > "$dir/manifest.digest"
}

run_tcl_rejection() {
    local dir="$1" expected_fragment="$2"
    cat > "$dir/runner.tcl" <<'TCL'
proc open_checkpoint {args} {
    set fh [open $::env(HAP_OPEN_MARKER) w]
    puts $fh invoked
    close $fh
    error "open_checkpoint must not be reached"
}
if {![catch {source $::env(HAP_AUDIT_TCL)} message]} {
    puts stderr "audit Tcl unexpectedly accepted invalid provenance"
    exit 1
}
if {[file exists $::env(HAP_OPEN_MARKER)]} {
    puts stderr "open_checkpoint was reached before provenance rejection"
    exit 2
}
if {[string first $::env(HAP_EXPECTED_ERROR) $message] < 0} {
    puts stderr "unexpected rejection: $message"
    exit 3
}
TCL
    HAP_DCP="$dir/board.dcp" HAP_BITSTREAM="$dir/board.bit" \
    HAP_XDC_INVENTORY="$dir/xdc_inventory.txt" \
    HAP_AUDIT_DIR="$dir/evidence" \
    HAP_AUDIT_INPUT_MANIFEST_SHA256="$(<"$dir/manifest.digest")" \
    HAP_AUDIT_TCL="$AUDIT_TCL" HAP_OPEN_MARKER="$dir/open.marker" \
    HAP_EXPECTED_ERROR="$expected_fragment" tclsh "$dir/runner.tcl"
}

# A payload mutation with an unchanged manifest must be rejected inside Tcl,
# before the board gate is sourced or the checkpoint is opened.
make_tcl_fixture "$TMP/tcl_mutated"
printf 'mutation\n' >> "$TMP/tcl_mutated/board.dcp"
run_tcl_rejection "$TMP/tcl_mutated" 'Audit frozen-input SHA mismatch'

# INPUT_FILES is independently exact: even a fully valid ten-row SHA
# manifest cannot authorize a different/missing path list.
make_tcl_fixture "$TMP/tcl_bad_paths"
sed -i "\|$LAUNCHER|d" "$TMP/tcl_bad_paths/evidence/INPUT_FILES"
run_tcl_rejection "$TMP/tcl_bad_paths" 'INPUT_FILES exact path mismatch'

normalized="$(sed -zE 's/\\[[:space:]]+/ /g; s/[[:space:]]+/ /g' \
    "$AUDIT_TCL")"
case "$normalized" in
    *'set frozen_inputs [hap_audit_verify_inputs $input_sha'*\
'source $gate_tcl'*'open_checkpoint $dcp'*) ;;
    *) fail 'Tcl provenance verification is not before source/open_checkpoint' ;;
esac

printf 'V5_BOARD_AUDIT_PROVENANCE_TEST_PASS\n'
printf 'launcher_failure_dynamic_archive=PASS\n'
printf 'fresh_directory_negative=PASS\n'
printf 'tcl_mutated_input_negative=PASS\n'
printf 'tcl_exact_path_negative=PASS\n'
